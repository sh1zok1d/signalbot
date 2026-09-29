"""Phase A coverage-analysis tests. Synthetic frames only; no database and no export."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

import pytest

from beta.config import BetaConfig
from scripts.audit.live_archive_replay_preflight.analyze_coverage import (
    analyze_export,
    analyze_frames,
    history_is_mature,
    verify_manifest,
)

UTC = timezone.utc
VENUES = ("binance", "bybit", "okx")
T0 = datetime(2026, 7, 17, 19, 30, tzinfo=UTC)
DAY = timedelta(days=1)
BUCKET = timedelta(minutes=5)


def test_maturity_requires_exact_30_day_span_and_two_samples():
    samples = [T0, T0 + BUCKET]
    assert history_is_mature(samples, T0 + 30 * DAY, maturity_days=30)
    assert not history_is_mature(samples, T0 + 30 * DAY - BUCKET, maturity_days=30)
    assert not history_is_mature([T0], T0 + 30 * DAY, maturity_days=30)
    assert not history_is_mature([], T0 + 30 * DAY, maturity_days=30)


def test_price_oi_interval_does_not_make_the_full_detector_eligible():
    first = T0 + 30 * DAY - 2 * BUCKET
    requested_n = 8
    lookback = _history(T0, first, price=True, oi=True, heartbeat=True)
    requested = []
    for index in range(requested_n):
        bucket = first + index * BUCKET
        price = index in {2, 3, 6, 7}
        oi = index >= 2
        for venue in VENUES:
            contribute = venue != "okx"
            requested.append(_row(
                bucket, venue,
                price=price and contribute,
                oi=oi and contribute,
                heartbeat=contribute and index >= 2,
                oi_count=2 if oi and contribute else 0,
                bars=5 if price and contribute else 0,
            ))
    result = _analyze(requested, lookback)
    down = result["events"]["PRICE_OI_CONTRACTION_DOWN"]
    up = result["events"]["PRICE_OI_CONTRACTION_UP"]
    assert down["status"] == "PARTIALLY_REPLAYABLE_WITH_INTERVAL"
    assert up["status"] == down["status"]
    assert down["replayable_bucket_count"] == 4
    assert down["replayable_interval_count"] == 2
    assert down["interior_gap_runs"] == 1
    assert down["number_of_gap_runs_gt_1_bucket"] == 1
    assert down["number_of_gap_runs_gt_1_hour"] == 0
    assert down["number_of_gap_runs_gt_1_day"] == 0
    assert down["blockers"] == ["INTERIOR_COVERAGE_GAPS"]
    assert "VOLUME" not in "".join(down["blockers"])
    assert result["events"]["POSITION_BUILDUP_COMPRESSION"]["status"] == "BLOCKED"
    assert result["events"]["POSITION_BUILDUP_COMPRESSION"]["blockers"] == ["VOLUME_PIT_NOTIONAL_NEVER_ELIGIBLE"]
    assert result["events"]["TAKER_FLOW_EXTREME_BUY"]["status"] == "BLOCKED"
    assert result["events"]["TAKER_FLOW_EXTREME_BUY"]["blockers"] == ["TAKER_FLOW_PIT_NOTIONAL_NEVER_ELIGIBLE"]
    assert result["events"]["TAKER_FLOW_EXTREME_SELL"]["status"] == "BLOCKED"
    liquidation = result["events"]["LIQUIDATION_STRESS_LONG"]
    assert liquidation["status"] == "INSUFFICIENT_EVIDENCE"
    assert liquidation["replayable_bucket_count"] == 0
    assert liquidation["blockers"] == ["CONNECTIVITY_LOG_EMPTY_HEARTBEAT_NOT_HISTORICALLY_PROVABLE"]
    assert liquidation["code_path_quorum_buckets"] == 6
    assert result["first_mature"]["liquidation"] is None
    assert result["first_mature"]["price"] == _iso(T0 + 30 * DAY)
    assert result["first_mature"]["volume"] is None
    assert result["families"]["volume"]["eligible_buckets"] == 0
    assert result["families"]["price_structure"]["venue_quorum_eligible_buckets"] == 4
    assert result["full_current_detector_replay_eligibility"] == "NOT_ELIGIBLE"
    assert result["simultaneous_enabled_family_buckets"] == 0
    assert result["phase_a_decision"] == "ARCHIVE_PARTIALLY_ELIGIBLE_FOR_EVENT_FAMILY_REPLAY"
    assert result["next_unit"]["unit"] == "LIVE_ARCHIVE_PRICE_OI_FAMILY_REPLAY_ISOLATED_NON_PRODUCTION"
    assert result["next_unit"]["replay_authorized"] is False
    assert result["replay_authorized"] is False
    assert result["product_semantics"]["no_active_events_reproducible"] is False
    assert result["product_semantics"]["no_active_events_blocker"] == "FAMILY_UNUSABLE:volume"
    assert result["oi_units"]["live_unit_transitions"] == {"binance": 0, "bybit": 0, "okx": 0}
    assert result["eligible_before_observed_live_kline_start"]["price_structure"]["count"] == 0


def test_one_venue_never_meets_quorum_and_disabled_taker_is_not_a_coverage_blocker():
    bucket = datetime(2026, 8, 16, 19, 30, tzinfo=UTC)
    rows = []
    for venue in VENUES:
        rows.append(_row(
            bucket, venue,
            price=venue == "binance",
            oi=venue == "binance",
            oi_count=2 if venue == "binance" else 1,
            oi_mixed=venue == "bybit",
            bars=4,
        ))
    result = _analyze(rows, [], cfg=_DisabledTaker())
    assert result["families"]["price_structure"]["eligible_buckets"] == 0
    assert result["per_venue"]["binance"]["oi_ge_2_count"] == 1
    assert result["families"]["oi"]["eligible_buckets"] == 0
    assert result["events"]["PRICE_OI_CONTRACTION_DOWN"]["status"] == "BLOCKED"
    assert "PRICE_STRUCTURE_QUORUM_NEVER_MET" in result["events"]["PRICE_OI_CONTRACTION_DOWN"]["blockers"]
    assert result["events"]["TAKER_FLOW_EXTREME_BUY"]["status"] == "DISABLED_IN_CURRENT_CONFIG"
    assert "RULE_DISABLED" not in result["top_coverage_blockers"]
    assert result["phase_a_decision"] == "ARCHIVE_NOT_ELIGIBLE_FOR_USEFUL_DETECTOR_REPLAY"
    assert result["next_unit"] is None
    assert result["full_current_detector_replay_eligibility"] == "NOT_ELIGIBLE"


def test_overlapping_replayable_families_with_a_gap_are_partial_for_the_full_detector():
    first = T0 + 30 * DAY
    lookback = _history(T0, first, price=True, oi=True, volume=True, taker=True, heartbeat=True)
    requested = []
    for index in range(3):
        usable = index != 1
        for venue in VENUES:
            contribute = venue != "okx"
            requested.append(_row(
                first + index * BUCKET, venue,
                price=usable and contribute,
                oi=usable and contribute,
                volume=usable and contribute,
                taker=usable and contribute,
                heartbeat=usable and contribute,
                oi_count=2 if usable and contribute else 0,
                bars=5 if usable and contribute else 0,
                taker_minutes=5 if usable and contribute else 0,
            ))
    result = _analyze(requested, lookback, connectivity=[{
        "record_type": "event",
        "exchange": "binance",
        "event_type": "disconnect",
        "note": "",
    }])
    assert result["connectivity"]["historical_heartbeat_provable"] is True
    for name in (
        "PRICE_OI_CONTRACTION_DOWN",
        "POSITION_BUILDUP_COMPRESSION",
        "TAKER_FLOW_EXTREME_BUY",
        "LIQUIDATION_STRESS_LONG",
        "LIQUIDATION_STRESS_SHORT",
    ):
        assert result["events"][name]["status"] == "PARTIALLY_REPLAYABLE_WITH_INTERVAL"
        assert result["events"][name]["replayable_bucket_count"] == 2
        assert result["events"][name]["number_of_gap_runs_gt_1_bucket"] == 0
    assert result["full_current_detector_replay_eligibility"] == "PARTIAL"
    assert result["simultaneous_enabled_family_buckets"] == 2
    assert result["phase_a_decision"] == "ARCHIVE_PARTIALLY_ELIGIBLE_FOR_EVENT_FAMILY_REPLAY"
    assert result["next_unit"]["unit"] == "LIVE_ARCHIVE_EVENT_FAMILY_REPLAY_ISOLATED_NON_PRODUCTION"


def test_manifest_hash_and_row_count_fail_closed(tmp_path):
    body = "a,b\n1,2\n"
    (tmp_path / "tiny.csv").write_bytes(body.encode())
    digest = hashlib.sha256(body.encode()).hexdigest()
    manifest = {"files": [{"name": "tiny.csv", "sha256": digest, "rows": 1}]}
    (tmp_path / "export_manifest.json").write_text(json.dumps(manifest))
    verified = verify_manifest(tmp_path)
    assert verified["ok"] is True
    manifest["files"][0]["rows"] = 2
    (tmp_path / "export_manifest.json").write_text(json.dumps(manifest))
    assert verify_manifest(tmp_path)["ok"] is False
    with pytest.raises(SystemExit):
        analyze_export(tmp_path)


def test_duplicate_bucket_venue_is_rejected():
    bucket = datetime(2026, 8, 1, tzinfo=UTC)
    rows = [_row(bucket, venue) for venue in VENUES]
    rows.append(_row(bucket, "binance"))
    with pytest.raises(SystemExit, match="duplicate"):
        _analyze(rows, [])


class _DisabledTaker:
    symbol = "BTCUSDT"

    def __getitem__(self, key):
        if key == "percentile_window":
            return "30d"
        raise KeyError(key)

    @property
    def min_venues(self):
        return 2

    def rule(self, name):
        if name == "TAKER_FLOW_EXTREME":
            return {"enabled": False}
        if name == "LIQUIDATION_STRESS":
            return {"enabled": True, "min_eligible_venues": 2}
        return {}


def _analyze(requested, lookback, *, connectivity=None, cfg=None):
    return analyze_frames(
        coverage_rows=requested,
        lookback_rows=lookback,
        archive_rows=[{
            "table_name": "klines_1m",
            "exchange": "binance",
            "source": "live",
            "row_count": "1",
            "min_ts": "2026-07-17T19:27:00Z",
            "max_ts": "2026-09-29T07:26:00Z",
            "note": "",
        }],
        oi_unit_rows=[
            {"exchange": "binance", "source": "live", "oi_unit": "base"},
            {"exchange": "bybit", "source": "live", "oi_unit": "base"},
            {"exchange": "okx", "source": "live", "oi_unit": "contracts"},
        ],
        instrument_rows=[{"exchange": venue, "note": "no_history_rows"} for venue in VENUES],
        connectivity_rows=connectivity or [{
            "record_type": "note",
            "note": "no_disconnect_or_restore_events",
        }],
        capability_rows=[{
            "exchange": venue,
            "declared_available": "true",
            "coverage_type": "full",
            "note": "current_row_not_pit",
        } for venue in VENUES],
        manifest={},
        verification={"ok": True, "files": []},
        cfg=cfg or BetaConfig.load(),
    )


def _history(start, stop, **flags):
    rows = []
    cursor = start
    while cursor < stop:
        for venue in ("binance", "bybit"):
            rows.append(_row(cursor, venue, oi_count=2, bars=5, taker_minutes=5, **flags))
        cursor += BUCKET
    return rows


def _row(ts, venue, *, price=False, oi=False, volume=False, taker=False, heartbeat=False,
         oi_count=0, oi_mixed=False, bars=0, taker_minutes=0):
    def flag(value):
        return "true" if value else "false"

    return {
        "bucket_start": _iso(ts),
        "exchange": venue,
        "bar_coverage_eligible": flag(bars == 5),
        "price_feature_non_null": flag(price),
        "oi_feature_non_null": flag(oi),
        "oi_evaluable": flag(oi),
        "oi_mixed_units": flag(oi_mixed),
        "volume_notional_non_null": flag(volume),
        "taker_notional_non_null": flag(taker),
        "pit_history_present": "false",
        "heartbeat_healthy": flag(heartbeat),
        "liquidation_feature_non_null": flag(heartbeat),
        "liquidation_declared_available": "true",
        "missing_pit_history": "true",
        "usable_oi_distinct_timestamps": str(oi_count),
        "taker_split_complete_expected_minutes": str(taker_minutes),
        "liquidation_rows_present": "false",
    }


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
