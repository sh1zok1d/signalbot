"""Tests for the Tardis free-overlap tooling. No network and no database."""
from __future__ import annotations

import asyncio
import csv
import gzip
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from analytics.feature_engine.exchange_features import FeatureError, _oi_feature
from analytics.feature_engine.models import KlineBar, OpenInterestObservation
from data_ingestion.bar_builder import LiveBarBuilder
from data_ingestion.base_client import Trade
from scripts.audit.tardis_free_overlap_v0.compare import (
    evaluate_principles,
    numeric_diagnostics,
    overall_decision,
    scale_failure,
)
from scripts.audit.tardis_free_overlap_v0.constants import VENUE_BY_SIGNALBOT
from scripts.audit.tardis_free_overlap_v0.extract_sql import STATEMENTS, assert_sql_is_read_only
from scripts.audit.tardis_free_overlap_v0.features import (
    compute_bucket_features,
    consensus_for_vectors,
    minute_bar_to_kline,
    oi_endpoint_facts,
    production_identity,
    structural_metadata,
    vector_public_dict,
)
from scripts.audit.tardis_free_overlap_v0.gaps import bucket_tags
from scripts.audit.tardis_free_overlap_v0.gold import load_gold_dir
from scripts.audit.tardis_free_overlap_v0.inventory import inventory_file
from scripts.audit.tardis_free_overlap_v0.parsing import (
    SchemaError,
    TradeRow,
    aggregate_trades,
    in_half_open_bucket,
    is_buyer_maker_from_tardis_side,
    minute_start_from_us,
)
from scripts.audit.tardis_free_overlap_v0.__main__ import main as cli_main

UTC = timezone.utc
BUCKET = datetime(2026, 8, 1, tzinfo=UTC)
EDGE = BUCKET + timedelta(minutes=5)


def _identity():
    return production_identity()


def _bars(n=5, *, open_px=100.0, close_px=110.0, buy=0.6, sell=0.4, volume=1.0):
    bars = []
    for i in range(n):
        px = open_px if i == 0 else close_px
        bars.append(KlineBar(
            ts=BUCKET + timedelta(minutes=i),
            open=px, high=px + 1.0, low=px - 0.5, close=px,
            volume=volume, taker_buy_volume=buy, taker_sell_volume=sell,
        ))
    return bars


def _oi(raws, *, unit="base", seconds=(10, 200)):
    return [
        OpenInterestObservation(
            ts=BUCKET + timedelta(seconds=sec), oi_raw=raw, oi_unit=unit,
        )
        for raw, sec in zip(raws, seconds)
    ]


def _meta(exchange="binance", multiplier=None):
    venue = VENUE_BY_SIGNALBOT[exchange]
    return structural_metadata(
        venue, contract_multiplier=multiplier, metadata_source="manual", note="test",
    )


def test_allowed_missing_bars_matches_production_coverage():
    assert _identity()["allowed_missing_bars_5m"] == 0


def test_right_boundary_is_excluded_from_oi_and_trades():
    inside = OpenInterestObservation(ts=BUCKET, oi_raw=100.0, oi_unit="base")
    edge = OpenInterestObservation(ts=EDGE, oi_raw=999.0, oi_unit="base")
    later = OpenInterestObservation(
        ts=BUCKET + timedelta(seconds=30), oi_raw=110.0, oi_unit="base",
    )
    facts = oi_endpoint_facts((inside, edge, later), BUCKET)
    assert facts["observation_count"] == 2
    assert facts["first_oi"] == 100.0
    assert facts["last_oi"] == 110.0
    assert facts["oi_change_pct"] == pytest.approx(10.0)
    assert not in_half_open_bucket(EDGE, BUCKET)
    assert in_half_open_bucket(EDGE - timedelta(microseconds=1), BUCKET)
    # A trade exactly on the next minute is not in the previous minute.
    us = int(EDGE.timestamp()) * 1_000_000
    assert minute_start_from_us(us) == EDGE
    assert minute_start_from_us(us - 1) == BUCKET + timedelta(minutes=4)


def test_future_bar_is_rejected():
    future = KlineBar(
        ts=EDGE, open=1, high=1, low=1, close=1, volume=1,
        taker_buy_volume=1, taker_sell_volume=0,
    )
    with pytest.raises(FeatureError, match="future bar"):
        compute_bucket_features(
            identity=_identity(), exchange="binance", bucket_ts=BUCKET,
            bars=_bars() + [future], oi=_oi((100, 110)), metadata=_meta(),
        )


def test_duplicate_identical_oi_collapses_and_conflict_fails_closed():
    dup = (
        OpenInterestObservation(ts=BUCKET, oi_raw=100.0, oi_unit="base"),
        OpenInterestObservation(ts=BUCKET, oi_raw=100.0, oi_unit="base"),
        OpenInterestObservation(ts=BUCKET + timedelta(seconds=20), oi_raw=110.0, oi_unit="base"),
    )
    facts = oi_endpoint_facts(dup, BUCKET)
    assert facts["observation_count"] == 2
    assert facts["oi_change_pct"] == pytest.approx(10.0)
    only_dups = dup[:2]
    alone = oi_endpoint_facts(only_dups, BUCKET)
    assert alone["observation_count"] == 1
    assert alone["oi_change_pct"] is None
    conflict = (
        OpenInterestObservation(ts=BUCKET, oi_raw=100.0, oi_unit="base"),
        OpenInterestObservation(ts=BUCKET, oi_raw=101.0, oi_unit="base"),
        OpenInterestObservation(ts=BUCKET + timedelta(seconds=20), oi_raw=110.0, oi_unit="base"),
    )
    with pytest.raises(FeatureError, match="conflicting"):
        _oi_feature(
            __import__(
                "scripts.audit.tardis_free_overlap_v0.features",
                fromlist=["_oi_probe"],
            )._oi_probe(BUCKET, conflict),
            EDGE,
        )
    vector, diagnostic = compute_bucket_features(
        identity=_identity(), exchange="binance", bucket_ts=BUCKET,
        bars=_bars(), oi=conflict, metadata=_meta(),
    )
    assert diagnostic["oi_reason"] == "CONFLICTING_OI"
    assert vector.oi_change_pct is None
    assert vector.price_move_pct is not None


def test_fewer_than_two_timestamps_and_unit_mismatch_are_not_evaluable():
    vector, diagnostic = compute_bucket_features(
        identity=_identity(), exchange="binance", bucket_ts=BUCKET,
        bars=_bars(), oi=_oi((100,), seconds=(10,)), metadata=_meta(),
    )
    assert vector.oi_change_pct is None
    assert diagnostic["oi_reason"] == "FEWER_THAN_TWO_DISTINCT_TIMESTAMPS"
    mixed = (
        OpenInterestObservation(ts=BUCKET, oi_raw=100.0, oi_unit="base"),
        OpenInterestObservation(
            ts=BUCKET + timedelta(seconds=20), oi_raw=100.0, oi_unit="contracts",
        ),
    )
    vector, diagnostic = compute_bucket_features(
        identity=_identity(), exchange="binance", bucket_ts=BUCKET,
        bars=_bars(), oi=mixed, metadata=_meta(),
    )
    assert vector.oi_change_pct is None
    assert diagnostic["oi_reason"] == "UNIT_MISMATCH_WITHIN_BUCKET"


def test_taker_side_matches_live_bar_builder_and_buy_sell_sums():
    assert is_buyer_maker_from_tardis_side("sell") is True
    assert is_buyer_maker_from_tardis_side("buy") is False
    assert is_buyer_maker_from_tardis_side("unknown") is None
    with pytest.raises(SchemaError):
        is_buyer_maker_from_tardis_side("ask")

    async def _live():
        closed = []

        async def on_bar(bar):
            closed.append(bar)

        builder = LiveBarBuilder("binance", "BTCUSDT", on_bar)
        start = BUCKET.timestamp()
        await builder.add_trade(Trade("binance", "BTCUSDT", start + 1, 10.0, 2.0, False))
        await builder.add_trade(Trade("binance", "BTCUSDT", start + 2, 12.0, 1.0, True))
        await builder.add_trade(Trade("binance", "BTCUSDT", start + 61, 11.0, 4.0, False))
        await builder.flush()
        return closed

    live = asyncio.run(_live())
    trades = [
        TradeRow("binance-futures", "BTCUSDT", int((BUCKET.timestamp() + 2) * 1_000_000),
                 0, "b", "sell", 12.0, 1.0, "abc", "2026-08-01"),
        TradeRow("binance-futures", "BTCUSDT", int((BUCKET.timestamp() + 1) * 1_000_000),
                 0, "a", "buy", 10.0, 2.0, "abc", "2026-08-01"),
        TradeRow("binance-futures", "BTCUSDT", int((BUCKET.timestamp() + 61) * 1_000_000),
                 0, "c", "buy", 11.0, 4.0, "abc", "2026-08-01"),
    ]
    bars = aggregate_trades(list(reversed(trades)))
    first = bars[BUCKET]
    second = bars[BUCKET + timedelta(minutes=1)]
    assert live[0].open == first.open == 10.0
    assert live[0].close == first.close == 12.0
    assert live[0].volume == first.volume == pytest.approx(3.0)
    assert live[0].taker_buy_volume == first.taker_buy_volume == pytest.approx(2.0)
    assert live[0].taker_sell_volume == first.taker_sell_volume == pytest.approx(1.0)
    assert second.taker_buy_volume == pytest.approx(4.0)
    assert second.taker_sell_volume == pytest.approx(0.0)
    # unknown side fails the minute closed instead of guessing or flipping.
    unknown = aggregate_trades([
        TradeRow("binance-futures", "BTCUSDT", int(BUCKET.timestamp() * 1_000_000),
                 0, "u", "unknown", 10.0, 1.0, "abc", "2026-08-01"),
    ])
    kline = minute_bar_to_kline(unknown[BUCKET])
    assert kline.volume == pytest.approx(1.0)
    assert kline.taker_buy_volume is None and kline.taker_sell_volume is None


def test_okx_missing_multiplier_fails_notional_closed_and_keeps_price():
    vector, _ = compute_bucket_features(
        identity=_identity(), exchange="okx", bucket_ts=BUCKET,
        bars=_bars(), oi=_oi((100, 110), unit="contracts"),
        metadata=_meta("okx", multiplier=None),
    )
    assert vector.price_move_pct is not None
    assert vector.volume_notional_usd is None
    assert vector.taker_delta_notional_usd is None
    assert vector.is_usable is True
    priced, _ = compute_bucket_features(
        identity=_identity(), exchange="okx", bucket_ts=BUCKET,
        bars=_bars(), oi=_oi((100, 110), unit="contracts"),
        metadata=_meta("okx", multiplier=0.01),
    )
    assert priced.volume_notional_usd is not None
    assert priced.volume_notional_usd != pytest.approx(priced.volume_raw * priced.close_price)


def test_incomplete_minute_coverage_is_not_usable_for_consensus():
    vector, _ = compute_bucket_features(
        identity=_identity(), exchange="binance", bucket_ts=BUCKET,
        bars=_bars(4), oi=_oi((100, 110)), metadata=_meta(),
    )
    assert vector.bars_present == 4
    assert vector.is_usable is False
    complete, _ = compute_bucket_features(
        identity=_identity(), exchange="bybit", bucket_ts=BUCKET,
        bars=_bars(), oi=_oi((100, 110)), metadata=_meta("bybit"),
    )
    okx, _ = compute_bucket_features(
        identity=_identity(), exchange="okx", bucket_ts=BUCKET,
        bars=_bars(), oi=_oi((100, 110), unit="contracts"),
        metadata=_meta("okx", multiplier=0.01),
    )
    consensus, exclusions = consensus_for_vectors(
        _identity(), BUCKET, (vector, complete, okx),
    )
    assert exclusions["price_structure"]["binance"] == "BAR_DATA_UNUSABLE"
    assert "binance" not in consensus.provenance_by_metric["price_structure"].contributing
    assert consensus.provenance_by_metric["price_structure"].contributing == ("bybit", "okx")


def test_aggregation_is_deterministic():
    base = int(BUCKET.timestamp() * 1_000_000)
    trades = [
        TradeRow("bybit", "BTCUSDT", base + i * 1000, i, str(i),
                 "buy" if i % 2 == 0 else "sell", 100.0 + (i % 3), 0.1, "h", "2026-08-01")
        for i in range(10)
    ]
    forward = aggregate_trades(trades)
    backward = aggregate_trades(list(reversed(trades)))
    assert forward.keys() == backward.keys()
    for minute in forward:
        assert forward[minute].open == backward[minute].open
        assert forward[minute].close == backward[minute].close
        assert forward[minute].volume == backward[minute].volume
        assert forward[minute].taker_buy_volume == backward[minute].taker_buy_volume


def test_documented_gap_is_tagged_and_not_zero_filled():
    incident = {
        "from": "2026-08-01T00:00:00.000Z",
        "to": "2026-08-01T00:10:00.000Z",
        "status": "resolved",
        "details": "Missing trade data caused by a recorder failure.",
    }
    assert bucket_tags([incident], BUCKET, EDGE) == ["VENDOR_DOCUMENTED_GAP"]
    stats_only = {
        "from": "2023-06-09T15:30:00.000Z",
        "to": "2026-08-04T11:16:00.000Z",
        "status": "resolved",
        "details": (
            "Some generated OKX statistics channels were collected less frequently. "
            "Other OKX channels were unaffected."
        ),
    }
    assert bucket_tags([stats_only], BUCKET, EDGE) == []
    # A missing observation stays missing. It is not inserted as a zero pair.
    diag = numeric_diagnostics([(None, None), (1.0, 2.0)])
    assert diag["both_null"] == 1
    assert diag["comparable_count"] == 1
    assert diag["median_absolute_difference"] == pytest.approx(1.0)


def test_provenance_is_not_live_observed():
    vector, _ = compute_bucket_features(
        identity=_identity(), exchange="binance", bucket_ts=BUCKET,
        bars=_bars(), oi=_oi((100, 110)), metadata=_meta(),
    )
    record = vector_public_dict(
        vector, source="TARDIS_FREE_SAMPLE", instrument="BTCUSDT",
        sample_date="2026-08-01", source_file_sha256="abc",
        exchange_timestamp_role="exchange_event_time",
    )
    assert record["source"] == "TARDIS_FREE_SAMPLE"
    assert record["called_live_observed"] is False
    assert record["source_file_sha256"] == "abc"


def test_scale_bug_is_a_failure_and_is_not_normalized_away():
    assert scale_failure(100.0) == "METADATA_SCALE_SUSPECT"
    assert scale_failure(0.01) == "METADATA_SCALE_SUSPECT"
    assert scale_failure(1.0) is None
    pairs = [(1.0, 100.0) for _ in range(25)]
    stats = {"volume_notional_usd": numeric_diagnostics(pairs)}
    findings = evaluate_principles(
        stats, oi_strata=None, evaluable_disagreement_fraction=0.0,
        quorum_disagreement_fraction=0.0, unit_mismatch_count=0,
        post_hoc_transform_applied=False,
    )
    assert any(item["code"] == "METADATA_SCALE_SUSPECT" for item in findings)
    assert numeric_diagnostics(pairs)["median_scale_ratio_tardis_over_gold"] == pytest.approx(100.0)


def test_taker_inversion_rejects_and_missing_gold_stays_incomplete():
    pairs = [(1.0, -1.0) for _ in range(25)]
    stats = {"taker_delta_notional_usd": numeric_diagnostics(pairs)}
    findings = evaluate_principles(
        stats, oi_strata=None, evaluable_disagreement_fraction=0.0,
        quorum_disagreement_fraction=0.0, unit_mismatch_count=0,
        post_hoc_transform_applied=False,
    )
    assert any(item["code"] == "PERSISTENT_TAKER_INVERSION" for item in findings)
    assert overall_decision(comparison_performed=True, findings=findings) == (
        "REJECT_TARDIS_FOR_CURRENT_REPLAY"
    )
    assert overall_decision(comparison_performed=False, findings=[]) == (
        "INCOMPLETE_NO_SIGNALBOT_EXPORT"
    )


def test_extract_sql_is_read_only_and_package_does_not_touch_beta(tmp_path):
    text = Path(
        "scripts/audit/tardis_free_overlap_v0/extract_signalbot_readonly.sql"
    ).read_text()
    statements = assert_sql_is_read_only(text)
    assert statements == list(STATEMENTS)
    assert len(statements) == 6
    assert all(item.lstrip().upper().startswith("SELECT") for item in statements)
    package = Path("scripts/audit/tardis_free_overlap_v0")
    blob = "\n".join(path.read_text() for path in package.glob("*.py"))
    assert "import beta" not in blob
    assert "beta.detector" not in blob
    assert "beta.rules" not in blob
    assert "insert_klines" not in blob
    assert "insert_open_interest" not in blob
    # A non-live gold row is refused.
    root = tmp_path / "gold"
    root.mkdir()
    (root / "klines_1m.csv").write_text(
        "exchange,symbol,ts,open,high,low,close,volume,taker_buy_volume,taker_sell_volume,trades_count,source\n"
        "binance,BTCUSDT,2026-08-01T00:00:00+00:00,1,1,1,1,1,1,0,1,backfill\n"
    )
    (root / "open_interest.csv").write_text(
        "exchange,symbol,ts,oi_raw,oi_unit,contract_value,oi_base_asset,oi_notional_usd,source\n"
    )
    (root / "exchange_instrument_history.csv").write_text("note\n")
    with pytest.raises(ValueError, match="source=live"):
        load_gold_dir(root)


def test_schema_change_stops_the_source(tmp_path):
    path = tmp_path / "bad.csv.gz"
    with gzip.open(path, "wt", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["not", "the", "schema"])
        writer.writerow(["a", "b", "c"])
    venue = VENUE_BY_SIGNALBOT["binance"]
    record = inventory_file(
        str(path), venue=venue, data_type="trades", sample_date="2026-08-01",
    )
    assert record["status"] == "SCHEMA_CHANGED"
    assert record["schema_ok"] is False


def test_vendor_cache_is_gitignored():
    result = subprocess.run(
        ["git", "check-ignore", "-q",
         "artifacts/audit/tardis_free_overlap_v0/vendor/example.csv.gz"],
        check=False,
    )
    assert result.returncode == 0


def test_compare_cli_without_gold_does_not_invent_results(tmp_path):
    code = cli_main([
        "compare",
        "--vendor-dir", str(tmp_path),
        "--out-dir", str(tmp_path / "out"),
    ])
    assert code == 2
    assert not (tmp_path / "out").exists()


def test_okx_history_without_multiplier_stays_fail_closed(tmp_path):
    root = tmp_path / "gold"
    root.mkdir()
    (root / "klines_1m.csv").write_text(
        "exchange,symbol,ts,open,high,low,close,volume,taker_buy_volume,"
        "taker_sell_volume,trades_count,source\n"
    )
    (root / "open_interest.csv").write_text(
        "exchange,symbol,ts,oi_raw,oi_unit,contract_value,oi_base_asset,oi_notional_usd,source\n"
    )
    (root / "exchange_instrument_history.csv").write_text(
        "exchange,symbol,market_type,exchange_instrument_id,quantity_unit,"
        "contract_multiplier,tick_size,price_precision,quantity_precision,"
        "metadata_source,observed_at,effective_from,effective_until,note,"
        "accepted_metadata_revision\n"
        "okx,BTCUSDT,perp,BTC-USDT-SWAP,contracts,,0.1,1,1,exchange_api,"
        "2026-07-01T00:00:00+00:00,2026-07-01T00:00:00+00:00,,pit,\n"
    )
    gold = load_gold_dir(root)
    meta = gold.metadata_asof("okx", BUCKET)
    assert meta.quantity_unit == "contracts"
    assert meta.contract_multiplier is None
