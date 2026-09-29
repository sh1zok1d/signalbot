"""Deterministic PRICE_OI semantic-replay tests. No database and no network."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from analytics.percentile_engine.compute import compute_percentile_snapshot
from analytics.percentile_engine.models import (
    ConfidenceTierThresholds,
    PercentileError,
    PercentileRequest,
    PercentileSample,
)
from beta.config import PRICE_OI_CONTRACTION_DOWN, PRICE_OI_CONTRACTION_UP, BetaConfig
from beta.models import NOT_EVALUABLE, NOT_QUALIFIES, QUALIFIES, Episode
from beta.rules import _threshold_rule
from beta.state_tape import compute_percentiles, metric_key
from common.stage2_config import STAGE2_CONFIG_PATH, Stage2Config
from scripts.audit.live_archive_replay_preflight import price_oi_semantic_replay as semantic
from scripts.audit.live_archive_replay_preflight import run_price_oi_semantic_replay as runner
from scripts.audit.live_archive_replay_preflight.extract_sql import assert_text_read_only

UTC = timezone.utc
BUCKET = timedelta(minutes=5)
CODE = "replay-test"
PRICE_KEY = metric_key(None, "price_move_pct_median")
OI_KEY = metric_key(None, "oi_change_pct_median")


@pytest.fixture(scope="module")
def configs():
    return BetaConfig.load(), Stage2Config.load(STAGE2_CONFIG_PATH)


def _bars(bucket: datetime, open_: float, close: float) -> list:
    from analytics.feature_engine.models import KlineBar

    rows = []
    for minute in range(5):
        ts = bucket + timedelta(minutes=minute)
        bar_open = open_
        bar_close = close if minute == 4 else open_
        rows.append(KlineBar(
            ts, bar_open, max(bar_open, bar_close), min(bar_open, bar_close), bar_close, 1.0,
        ))
    return rows


def _oi(bucket: datetime, values: list[float], unit: str = "base") -> list:
    from analytics.feature_engine.models import OpenInterestObservation

    return [
        OpenInterestObservation(bucket + timedelta(minutes=index), value, unit)
        for index, value in enumerate(values)
    ]


def _reconstruct(stage2, bucket, venues: dict):
    bars = {name: spec["bars"] for name, spec in venues.items()}
    oi = {name: spec["oi"] for name, spec in venues.items()}
    return semantic.reconstruct_bucket(stage2, bucket, bars, oi, code_version=CODE)


def _venue(stage2, bucket, *, price=(100.0, 110.0), oi=(200.0, 210.0), unit="base"):
    return {"bars": _bars(bucket, *price), "oi": _oi(bucket, list(oi), unit)}


def _prepared(bucket, *, price_rank, oi_rank, price_tier="mature", oi_tier="mature",
              price_available=2, oi_available=2, price_median=1.0, oi_median=-1.0,
              venues=("binance", "bybit")):
    reconstruction = semantic.BucketReconstruction(
        bucket_ts=bucket,
        price_median=price_median,
        oi_median=oi_median,
        price_available=price_available,
        oi_available=oi_available,
        price_venues=tuple(venues),
        oi_venues=tuple(venues),
        calculation_version="0123456789abcdef",
        venue_failures=(),
    )
    return semantic.PreparedBucket(
        reconstruction, price_rank, oi_rank, price_tier, oi_tier,
    )


def _down_checks(cfg):
    rule = cfg.rule(PRICE_OI_CONTRACTION_DOWN)
    return (
        ("price_move_pct_median", "<=", rule["price_move_pct_median_max"]),
        ("oi_change_pct_median", "<=", rule["oi_change_pct_median_max"]),
    )


def test_authorized_intervals_match_phase_a():
    buckets = semantic.authorized_buckets()
    assert len(buckets) == semantic.PHASE_A_AUTHORIZED_BUCKETS == 12434
    assert buckets[0] == datetime(2026, 8, 16, 19, 30, tzinfo=UTC)
    assert datetime(2026, 9, 25, 12, 40, tzinfo=UTC) in buckets
    assert datetime(2026, 9, 25, 13, 5, tzinfo=UTC) in buckets
    assert buckets[-1] == datetime(2026, 9, 28, 23, 55, tzinfo=UTC)
    assert all(not semantic.in_frozen_gap(bucket) for bucket in buckets)
    gap = []
    cursor = semantic.GAP_START
    while cursor <= semantic.GAP_END:
        gap.append(cursor)
        cursor += BUCKET
    assert gap == [
        datetime(2026, 9, 25, 12, 45, tzinfo=UTC),
        datetime(2026, 9, 25, 12, 50, tzinfo=UTC),
        datetime(2026, 9, 25, 12, 55, tzinfo=UTC),
        datetime(2026, 9, 25, 13, 0, tzinfo=UTC),
    ]
    assert all(bucket not in buckets for bucket in gap)
    assert semantic.source_interval(buckets[0]) == "interval_1"
    assert semantic.source_interval(datetime(2026, 9, 25, 12, 40, tzinfo=UTC)) == "interval_1"
    assert semantic.source_interval(datetime(2026, 9, 25, 13, 5, tzinfo=UTC)) == "interval_2"
    assert semantic.source_interval(semantic.GAP_START) is None
    assert semantic.HISTORY_START == datetime(2026, 7, 17, 19, 30, tzinfo=UTC)
    assert semantic.HISTORY_START not in buckets
    history = semantic.history_buckets()
    assert history[0] == semantic.HISTORY_START
    assert history[-1] == buckets[-1]
    assert all(item in history for item in gap)


def test_exact_price_and_oi_reconstruction(configs):
    _cfg, stage2 = configs
    bucket = datetime(2026, 8, 16, 19, 30, tzinfo=UTC)
    vector = semantic._venue_feature(
        stage2, "binance", bucket, _bars(bucket, 100.0, 110.0), _oi(bucket, [200.0, 210.0]),
        code_version=CODE,
    )
    assert vector.price_move_pct == pytest.approx((110.0 - 100.0) / 100.0 * 100.0)
    assert vector.oi_change_pct == pytest.approx((210.0 - 200.0) / 200.0 * 100.0)
    assert vector.volume_notional_usd is None
    assert vector.taker_delta_notional_usd is None
    assert vector.long_liquidation_notional is None

    same = _reconstruct(stage2, bucket, {
        "binance": _venue(stage2, bucket),
        "bybit": _venue(stage2, bucket),
    })
    assert same.price_median == pytest.approx(10.0)
    assert same.oi_median == pytest.approx(5.0)
    assert same.price_available == 2
    assert same.oi_available == 2
    assert same.calculation_version

    one_obs = semantic._venue_feature(
        stage2, "binance", bucket, _bars(bucket, 100.0, 110.0), _oi(bucket, [200.0]),
        code_version=CODE,
    )
    zero_base = semantic._venue_feature(
        stage2, "binance", bucket, _bars(bucket, 100.0, 110.0), _oi(bucket, [0.0, 210.0]),
        code_version=CODE,
    )
    from analytics.feature_engine.models import OpenInterestObservation

    mixed_unit = semantic._venue_feature(
        stage2, "binance", bucket, _bars(bucket, 100.0, 110.0),
        [
            OpenInterestObservation(bucket, 200.0, "base"),
            OpenInterestObservation(bucket + timedelta(minutes=1), 210.0, "contracts"),
        ],
        code_version=CODE,
    )
    middle = semantic._venue_feature(
        stage2, "binance", bucket, _bars(bucket, 100.0, 110.0), _oi(bucket, [200.0, 999.0, 210.0]),
        code_version=CODE,
    )
    assert one_obs.oi_change_pct is None
    assert zero_base.oi_change_pct is None
    assert mixed_unit.oi_change_pct is None
    assert middle.oi_change_pct == pytest.approx(5.0)

    broken = _reconstruct(stage2, bucket, {
        "binance": {"bars": _bars(bucket, 0.0, 110.0), "oi": _oi(bucket, [200.0, 210.0])},
        "bybit": _venue(stage2, bucket),
        "okx": _venue(stage2, bucket),
    })
    assert "binance" in broken.venue_failures
    assert "binance" not in broken.price_venues
    assert broken.price_median == pytest.approx(10.0)


def test_two_of_three_venue_consensus(configs):
    _cfg, stage2 = configs
    bucket = datetime(2026, 8, 16, 19, 30, tzinfo=UTC)
    two = _reconstruct(stage2, bucket, {
        "binance": _venue(stage2, bucket, price=(100.0, 101.0), oi=(100.0, 101.0)),
        "bybit": _venue(stage2, bucket, price=(100.0, 103.0), oi=(100.0, 103.0)),
    })
    assert two.price_available == 2
    assert two.oi_available == 2
    assert two.price_median == pytest.approx(2.0)
    assert two.oi_median == pytest.approx(2.0)
    assert two.price_venues == ("binance", "bybit")

    three = _reconstruct(stage2, bucket, {
        "binance": _venue(stage2, bucket, price=(100.0, 101.0), oi=(100.0, 101.0)),
        "bybit": _venue(stage2, bucket, price=(100.0, 103.0), oi=(100.0, 103.0)),
        "okx": _venue(stage2, bucket, price=(100.0, 110.0), oi=(100.0, 110.0)),
    })
    assert three.price_available == 3
    assert three.price_median == pytest.approx(3.0)
    assert three.oi_median == pytest.approx(3.0)

    one = _reconstruct(stage2, bucket, {
        "binance": _venue(stage2, bucket, price=(100.0, 101.0), oi=(100.0, 101.0)),
    })
    assert one.price_available == 1
    assert one.oi_available == 1
    assert one.price_median is None
    assert one.oi_median is None


def test_current_percentile_implementation_and_no_future_leak(configs):
    cfg, stage2 = configs
    bucket = datetime(2026, 8, 16, 19, 30, tzinfo=UTC)
    reconstruction = _reconstruct(stage2, bucket, {
        "binance": _venue(stage2, bucket, price=(100.0, 102.0), oi=(100.0, 100.0)),
        "bybit": _venue(stage2, bucket, price=(100.0, 102.0), oi=(100.0, 100.0)),
    })
    assert reconstruction.price_median == pytest.approx(2.0)
    early = bucket - timedelta(days=30)
    previous = bucket - BUCKET
    history = [
        (early, {PRICE_KEY: 1.0, OI_KEY: -2.0}),
        (previous, {PRICE_KEY: 3.0, OI_KEY: -1.0}),
    ]
    got = semantic.current_percentiles(
        stage2, cfg, reconstruction, history, code_version=CODE,
    )
    tiers = stage2.resolve(cfg.symbol)["percentiles"]["confidence_tiers"]
    thresholds = ConfidenceTierThresholds(
        none_below_days=tiers["none_below_days"],
        low_below_days=tiers["low_below_days"],
        building_below_days=tiers["building_below_days"],
    )
    direct = compute_percentile_snapshot(PercentileRequest(
        scope="consensus", exchange="", symbol=cfg.symbol, market_type=cfg.market_type,
        metric="price_move_pct_median", timeframe=cfg.timeframe, percentile_window="30d",
        bucket_ts=bucket, value=reconstruction.price_median,
        samples=(
            PercentileSample(
                "consensus", "", cfg.symbol, cfg.market_type, "price_move_pct_median",
                cfg.timeframe, early, 1.0, stage2.feature_schema_version,
                reconstruction.calculation_version,
            ),
            PercentileSample(
                "consensus", "", cfg.symbol, cfg.market_type, "price_move_pct_median",
                cfg.timeframe, previous, 3.0, stage2.feature_schema_version,
                reconstruction.calculation_version,
            ),
        ),
        confidence_tier_thresholds=thresholds,
        config_hash=stage2.resolve(cfg.symbol).config_hash(),
        config_version=stage2.config_version,
        code_version=CODE,
        feature_schema_version=stage2.feature_schema_version,
        calculation_version=reconstruction.calculation_version,
    ))
    assert got[PRICE_KEY]["rank"] == direct.percentile_rank == pytest.approx(0.5)
    assert got[PRICE_KEY]["tier"] == direct.confidence_tier == "mature"
    reused = compute_percentiles(
        stage2, cfg, bucket_ts=bucket, metrics=semantic.metrics_of(reconstruction),
        ident={
            "calculation_version": reconstruction.calculation_version,
            "config_hash": stage2.resolve(cfg.symbol).config_hash(),
            "config_version": stage2.config_version,
            "feature_schema_version": stage2.feature_schema_version,
        },
        code_version=CODE, history=history,
    )
    assert got[PRICE_KEY] == reused[PRICE_KEY]
    assert got[OI_KEY] == reused[OI_KEY]

    leaked = history + [
        (bucket, {PRICE_KEY: 0.0, OI_KEY: 0.0}),
        (bucket + BUCKET, {PRICE_KEY: 9.0, OI_KEY: 9.0}),
    ]
    window = semantic.samples_before(leaked, bucket, maturity_days=30)
    assert [ts for ts, _metrics in window] == [early, previous]
    assert all(ts < bucket for ts, _metrics in window)
    with pytest.raises(ValueError, match="current bucket or a later bucket"):
        semantic.current_percentiles(stage2, cfg, reconstruction, leaked, code_version=CODE)
    with pytest.raises(PercentileError, match="outside window"):
        compute_percentiles(
            stage2, cfg, bucket_ts=bucket, metrics=semantic.metrics_of(reconstruction),
            ident={
                "calculation_version": reconstruction.calculation_version,
                "config_hash": stage2.resolve(cfg.symbol).config_hash(),
                "config_version": stage2.config_version,
                "feature_schema_version": stage2.feature_schema_version,
            },
            code_version=CODE, history=leaked,
        )


def test_non_mature_percentile_is_not_evaluable(configs):
    cfg, stage2 = configs
    bucket = datetime(2026, 8, 16, 19, 30, tzinfo=UTC)
    reconstruction = _reconstruct(stage2, bucket, {
        "binance": _venue(stage2, bucket, price=(100.0, 100.1), oi=(100.0, 99.0)),
        "bybit": _venue(stage2, bucket, price=(100.0, 100.1), oi=(100.0, 99.0)),
    })
    history = [
        (bucket - timedelta(days=1), {PRICE_KEY: 5.0, OI_KEY: 5.0}),
        (bucket - BUCKET, {PRICE_KEY: 4.0, OI_KEY: 4.0}),
    ]
    prepared = runner._prepare(
        reconstruction,
        semantic.current_percentiles(stage2, cfg, reconstruction, history, code_version=CODE),
    )
    assert prepared.price_tier != "mature"
    assert prepared.oi_tier != "mature"
    status, reason, _detail = semantic.semantic_rule(cfg, PRICE_OI_CONTRACTION_DOWN, prepared)
    assert status == NOT_EVALUABLE
    assert reason.startswith(f"PERCENTILE_NOT_MATURE:{PRICE_KEY}:")


def test_down_up_and_not_qualifies_use_current_thresholds(configs):
    cfg, _stage2 = configs
    down = cfg.rule(PRICE_OI_CONTRACTION_DOWN)
    up = cfg.rule(PRICE_OI_CONTRACTION_UP)
    assert down["price_move_pct_median_max"] == 0.05
    assert down["oi_change_pct_median_max"] == 0.10
    assert up["price_move_pct_median_min"] == 0.95
    assert up["oi_change_pct_median_max"] == 0.10
    assert down["armed_at_streak"] == 1
    assert down["triggered_at_streak"] == 2
    assert cfg.min_venues == 2
    bucket = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)

    qualifies_down = _prepared(bucket, price_rank=0.05, oi_rank=0.10)
    down_status, down_reason, _ = semantic.semantic_rule(cfg, PRICE_OI_CONTRACTION_DOWN, qualifies_down)
    up_on_down, up_on_down_reason, _ = semantic.semantic_rule(
        cfg, PRICE_OI_CONTRACTION_UP, qualifies_down,
    )
    assert down_status == QUALIFIES
    assert down_reason == "CONDITION_MET"
    assert up_on_down == NOT_QUALIFIES
    assert up_on_down_reason == "CONDITION_NOT_MET"

    qualifies_up = _prepared(bucket, price_rank=0.95, oi_rank=0.10)
    up_status, up_reason, _ = semantic.semantic_rule(cfg, PRICE_OI_CONTRACTION_UP, qualifies_up)
    down_on_up, _, _ = semantic.semantic_rule(cfg, PRICE_OI_CONTRACTION_DOWN, qualifies_up)
    assert up_status == QUALIFIES
    assert up_reason == "CONDITION_MET"
    assert down_on_up == NOT_QUALIFIES

    neutral = _prepared(bucket, price_rank=0.50, oi_rank=0.05)
    neutral_status, neutral_reason, _ = semantic.semantic_rule(
        cfg, PRICE_OI_CONTRACTION_DOWN, neutral,
    )
    assert neutral_status == NOT_QUALIFIES
    assert neutral_reason == "CONDITION_NOT_MET"

    with pytest.raises(ValueError, match="refusing to evaluate"):
        semantic.semantic_rule(cfg, "TAKER_FLOW_EXTREME_BUY", neutral)
    with pytest.raises(ValueError, match="refusing to evaluate"):
        semantic.semantic_rule(cfg, "POSITION_BUILDUP_COMPRESSION", neutral)


def test_adapter_matches_threshold_rule_without_claiming_runtime_gates(configs):
    cfg, _stage2 = configs
    prepared = _prepared(datetime(2026, 9, 1, 12, 0, tzinfo=UTC), price_rank=0.01, oi_rank=0.02)
    projection = semantic._projection(cfg, prepared)
    assert "evaluation_fresh" not in projection
    assert "materialized" not in projection
    assert "stale_barrier" not in projection
    adapter_status, adapter_reason, adapter_detail = semantic.semantic_rule(
        cfg, PRICE_OI_CONTRACTION_DOWN, prepared,
    )
    bare_status, bare_reason, _ = _threshold_rule(
        projection, ("price_structure", "oi"), _down_checks(cfg),
    )
    assert adapter_status == QUALIFIES
    assert bare_status == NOT_EVALUABLE
    assert bare_reason == "NOT_MATERIALIZED"

    fresh_missing = {**projection, "materialized": True, "stale_barrier": False}
    fresh_status, fresh_reason, _ = _threshold_rule(
        fresh_missing, ("price_structure", "oi"), _down_checks(cfg),
    )
    assert fresh_status == NOT_EVALUABLE
    assert fresh_reason == "EVALUATION_NOT_FRESH"
    assert adapter_status == QUALIFIES

    runtime = {**fresh_missing, "evaluation_fresh": True}
    runtime_status, runtime_reason, runtime_detail = _threshold_rule(
        runtime, ("price_structure", "oi"), _down_checks(cfg),
    )
    assert (adapter_status, adapter_reason, adapter_detail) == (
        runtime_status, runtime_reason, runtime_detail,
    )


def test_coverage_gap_breaks_streak_and_episode(configs):
    cfg, _stage2 = configs
    first = datetime(2026, 9, 25, 12, 35, tzinfo=UTC)
    second = datetime(2026, 9, 25, 12, 40, tzinfo=UTC)
    after = datetime(2026, 9, 25, 13, 5, tzinfo=UTC)
    series = [
        _prepared(first, price_rank=0.01, oi_rank=0.01),
        _prepared(second, price_rank=0.01, oi_rank=0.01),
        _prepared(after, price_rank=0.01, oi_rank=0.01),
    ]
    result = semantic.replay_series(cfg, series)
    down_rows = [row for row in result["evaluations"] if row["event_type"] == PRICE_OI_CONTRACTION_DOWN]
    assert [row["bucket_ts"] for row in down_rows] == [
        "2026-09-25T12:35:00Z", "2026-09-25T12:40:00Z", "2026-09-25T13:05:00Z",
    ]
    assert [row["streak"] for row in down_rows] == [1, 2, 1]
    assert all(row["rule_status"] == QUALIFIES for row in down_rows)
    episodes = [item for item in result["episodes"] if item.episode.event_type == PRICE_OI_CONTRACTION_DOWN]
    assert len(episodes) == 2
    opened, restarted = episodes
    assert opened.episode.last_bucket == second
    assert opened.episode.state == "ENDED"
    assert opened.episode.terminal_reason == "DETECTION_GAP"
    assert opened.qualifying_bucket_count == 2
    assert opened.source_interval == "interval_1"
    assert semantic.source_interval(opened.episode.opened_bucket) == "interval_1"
    assert semantic.source_interval(opened.episode.last_bucket) == "interval_1"
    assert restarted.episode.opened_bucket == after
    assert restarted.episode.state == "ARMED"
    assert restarted.episode.triggered_at is None
    assert restarted.episode.terminal_at is None
    assert restarted.qualifying_bucket_count == 1
    assert restarted.source_interval == "interval_2"
    assert opened.episode.triggered_at == second + BUCKET
    assert {item.episode.event_type for item in result["episodes"]} <= set(semantic.AUTHORIZED_FAMILIES)
    assert result["event_outcomes_computed"] is False
    assert result["p4_performance_computed"] is False

    with pytest.raises(ValueError, match="frozen gap"):
        semantic.replay_series(cfg, [
            _prepared(second, price_rank=0.01, oi_rank=0.01),
            _prepared(semantic.GAP_START, price_rank=0.01, oi_rank=0.01),
            _prepared(after, price_rank=0.01, oi_rank=0.01),
        ])


def test_not_qualifies_ends_episode_without_extending_it(configs):
    cfg, _stage2 = configs
    start = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
    series = [
        _prepared(start, price_rank=0.01, oi_rank=0.01),
        _prepared(start + BUCKET, price_rank=0.01, oi_rank=0.01),
        _prepared(start + 2 * BUCKET, price_rank=0.50, oi_rank=0.01),
    ]
    result = semantic.replay_series(cfg, series)
    rows = [row for row in result["evaluations"] if row["event_type"] == PRICE_OI_CONTRACTION_DOWN]
    assert [row["rule_status"] for row in rows] == [QUALIFIES, QUALIFIES, NOT_QUALIFIES]
    assert [row["streak"] for row in rows] == [1, 2, 0]
    episodes = [item for item in result["episodes"] if item.episode.event_type == PRICE_OI_CONTRACTION_DOWN]
    assert len(episodes) == 1
    assert episodes[0].episode.terminal_reason == "CONDITION_FAILED"
    assert episodes[0].qualifying_bucket_count == 2
    assert episodes[0].episode.last_bucket == start + BUCKET


def test_reject_cross_gap_episode(configs):
    cfg, _stage2 = configs
    crossed = Episode(
        episode_pk=None, public_id="EV-CROSS", symbol=cfg.symbol,
        event_type=PRICE_OI_CONTRACTION_DOWN, state="ARMED",
        opened_bucket=datetime(2026, 9, 25, 12, 40, tzinfo=UTC),
        opened_at=datetime(2026, 9, 25, 12, 45, tzinfo=UTC),
        armed_at=datetime(2026, 9, 25, 12, 45, tzinfo=UTC),
        triggered_at=None, terminal_at=None, terminal_reason=None,
        rules_version=cfg.rules_version, rules_digest=cfg.rules_digest,
        code_version="semantic-reconstruction", calculation_version="0123456789abcdef",
        opening_tape_digest="abc", trigger_tape_digest=None,
        last_bucket=datetime(2026, 9, 25, 13, 5, tzinfo=UTC), last_streak=2,
    )
    with pytest.raises(ValueError, match="crosses the frozen coverage gap"):
        semantic._reject_cross_gap([semantic.ReplayEpisode(crossed, 2, "interval_1")])


def test_provenance_and_p4_sample_gate_arithmetic(configs):
    cfg, _stage2 = configs
    bucket = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
    result = semantic.replay_series(cfg, [_prepared(bucket, price_rank=0.50, oi_rank=0.50)])
    assert result["replay_class"] == "CURRENT_RULE_SEMANTIC_RECONSTRUCTION"
    assert result["provenance"] == "RECONSTRUCTED_FROM_SIGNALBOT_LIVE_ARCHIVE"
    assert "not a record of" in result["disclaimer"]
    assert "not proven" in result["disclaimer"]
    families = {row["event_type"] for row in result["evaluations"]}
    assert families == set(semantic.AUTHORIZED_FAMILIES)
    for row in result["evaluations"]:
        assert row["provenance"] == semantic.PROVENANCE
        assert row["replay_class"] == semantic.REPLAY_CLASS
        assert row["historical_freshness_state"] == "NOT_IN_ARCHIVE"
        assert row["historical_coherence_race_state"] == "NOT_IN_ARCHIVE"
        assert row["historical_alert_delivery"] == "NOT_PROVEN"
        assert "open" not in row
        assert "oi_raw" not in row

    def episode(day: int, *, armed=True, triggered=False, streak=1):
        opened = datetime(2026, 9, day, 0, 0, tzinfo=UTC)
        item = Episode(
            episode_pk=None, public_id=f"EV-{day}-{armed}-{triggered}", symbol="BTCUSDT",
            event_type=PRICE_OI_CONTRACTION_DOWN, state="TRIGGERED" if triggered else "ARMED",
            opened_bucket=opened, opened_at=opened + BUCKET,
            armed_at=(opened + BUCKET) if armed else None,
            triggered_at=(opened + BUCKET) if triggered else None,
            terminal_at=None, terminal_reason=None, rules_version="v", rules_digest="d",
            code_version="semantic-reconstruction", calculation_version="0123456789abcdef",
            opening_tape_digest="o", trigger_tape_digest=None,
            last_bucket=opened, last_streak=streak,
        )
        return semantic.ReplayEpisode(item, streak, "interval_1")

    passing = [episode(day, triggered=True, streak=streak)
               for day in range(1, 6) for streak in (1, 2)]
    gate = semantic.sample_gate(passing)
    assert gate["total_episodes"] == 10
    assert gate["distinct_episode_dates_utc"] == 5
    assert gate["p4_sample_gate"] == "PASS"
    assert gate["early_only_episodes"] == 0
    assert gate["armed_episodes"] == 0
    assert gate["triggered_episodes"] == 10
    assert gate["median_qualifying_buckets_per_episode"] == 1.5
    assert gate["max_qualifying_buckets_per_episode"] == 2
    assert "sample availability only" in gate["gate_meaning"]
    assert semantic.sample_gate(passing[:9])["p4_sample_gate"] == "FAIL"
    four_dates = [episode(day, triggered=True) for day in range(1, 5) for _copy in range(3)]
    assert len(four_dates) == 12
    assert semantic.sample_gate(four_dates)["distinct_episode_dates_utc"] == 4
    assert semantic.sample_gate(four_dates)["p4_sample_gate"] == "FAIL"
    early = semantic.sample_gate([episode(1, armed=False, triggered=False)])
    assert early["early_only_episodes"] == 1
    assert early["armed_episodes"] == 0
    assert early["p4_sample_gate"] == "FAIL"


def test_sql_is_select_only_and_main_does_not_write(tmp_path, monkeypatch):
    kline_sql, oi_sql = runner.replay_sql()
    for text in (kline_sql, oi_sql):
        assert_text_read_only(text)
        assert "source = 'live'" in text
        assert "backfill" not in text.lower()
        assert text.lstrip().startswith("SELECT")
    assert "2026-07-17 19:30:00+00" in kline_sql
    assert "2026-09-29 00:00:00+00" in kline_sql
    module_text = Path(runner.__file__).read_text()
    semantic_text = Path(semantic.__file__).read_text()
    for forbidden in ("INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE", "CREATE TABLE", "psycopg"):
        assert forbidden not in module_text
        assert forbidden not in semantic_text
    assert "SIGNALBOT_DSN" not in semantic_text

    called = {"connect": 0}

    def explode(_dsn):
        called["connect"] += 1
        raise AssertionError("missing DSN must not connect")

    monkeypatch.delenv("SIGNALBOT_DSN", raising=False)
    assert runner.main(["--out-dir", str(tmp_path)], connect=explode) == 2
    assert called["connect"] == 0

    statements = []

    class Conn:
        def close(self):
            called["closed"] = True

        def execute(self, *_args, **_kwargs):
            raise AssertionError("runner must not execute SQL itself")

    def capture(_dsn):
        return Conn(), "fake"

    def capture_select(_conn, _driver, sql):
        statements.append(sql)
        if "klines_1m" in sql:
            return [], [row for row in _kline_rows()]
        return [], [row for row in _oi_rows()]

    monkeypatch.setenv("SIGNALBOT_DSN", "postgresql://replay-test")
    monkeypatch.setattr(runner, "_run_select", capture_select)
    monkeypatch.setattr(runner, "PHASE_A_AUTHORIZED_BUCKETS", 2)
    before = datetime(2026, 9, 25, 12, 40, tzinfo=UTC)
    after = datetime(2026, 9, 25, 13, 5, tzinfo=UTC)
    monkeypatch.setattr(runner, "authorized_buckets", lambda: [before, after])
    monkeypatch.setattr(runner, "history_buckets", lambda: [before, semantic.GAP_START, after])
    seen = []
    real_percentiles = runner.current_percentiles

    def spy(stage2, cfg, reconstruction, history, *, code_version):
        seen.append((reconstruction.bucket_ts, [ts for ts, _metrics in history]))
        return real_percentiles(stage2, cfg, reconstruction, history, code_version=code_version)

    monkeypatch.setattr(runner, "current_percentiles", spy)
    assert runner.main(["--out-dir", str(tmp_path)], connect=capture, code_version=CODE) == 0
    assert called["closed"] is True
    assert statements == [runner.KLINE_SQL, runner.OI_SQL]
    for ts, window in seen:
        assert all(item < ts for item in window)
        assert semantic.GAP_START not in (ts,)
    assert seen[0][0] == before and seen[0][1] == []
    assert seen[1][0] == after and semantic.GAP_START in seen[1][1]
    assert after not in seen[1][1]
    evaluations = (tmp_path / "rule_evaluations.csv").read_text()
    assert "\r" not in evaluations
    assert semantic.GAP_START.strftime("%Y-%m-%dT%H:%M:%SZ") not in evaluations
    assert semantic.PROVENANCE in evaluations
    assert semantic.REPLAY_CLASS in evaluations
    manifest = json.loads((tmp_path / "replay_manifest.json").read_text())
    gate = json.loads((tmp_path / "p4_sample_gate.json").read_text())
    assert manifest["production_tables_written"] is False
    assert manifest["backfill_rows_read"] == 0
    assert manifest["event_outcomes_computed"] is False
    assert manifest["p4_performance_computed"] is False
    assert manifest["replay_class"] == semantic.REPLAY_CLASS
    assert manifest["unexpected_gap_quorum_buckets"] == ["2026-09-25T12:45:00Z"]
    assert gate["event_outcomes_computed"] is False
    assert gate["p4_performance_computed"] is False
    assert set(gate["families"]) == set(semantic.AUTHORIZED_FAMILIES)


def _kline_rows():
    def rows(bucket):
        for exchange in ("binance", "bybit"):
            for minute in range(5):
                ts = bucket + timedelta(minutes=minute)
                yield (exchange, ts, 100.0, 101.0, 99.0, 100.5, 1.0)
    before = datetime(2026, 9, 25, 12, 40, tzinfo=UTC)
    gap = semantic.GAP_START
    after = datetime(2026, 9, 25, 13, 5, tzinfo=UTC)
    yield from rows(before)
    yield from rows(gap)
    yield from rows(after)
    yield ("binance", before + timedelta(minutes=1, seconds=30), 1, 1, 1, 1, 1)


def _oi_rows():
    def rows(bucket):
        for exchange in ("binance", "bybit"):
            for minute, value in ((0, 200.0), (4, 210.0)):
                yield (exchange, bucket + timedelta(minutes=minute), value, "base")
    before = datetime(2026, 9, 25, 12, 40, tzinfo=UTC)
    yield from rows(before)
    yield from rows(semantic.GAP_START)
    yield from rows(datetime(2026, 9, 25, 13, 5, tzinfo=UTC))
    yield ("binance", semantic.HISTORY_START - BUCKET, 1.0, "base")
    yield ("binance", runner.HISTORY_END_EXCLUSIVE, 1.0, "base")
    yield ("binance", before, None, "base")


def test_grouping_drops_offslot_and_out_of_window_rows():
    bars, offslot = runner._group_bars(list(_kline_rows()))
    assert offslot == 1
    gap = semantic.GAP_START
    assert set(bars[gap]) == {"binance", "bybit"}
    assert len(bars[gap]["binance"]) == 5
    oi = runner._group_oi(list(_oi_rows()))
    assert semantic.HISTORY_START - BUCKET not in oi
    assert runner.HISTORY_END_EXCLUSIVE not in oi
    assert len(oi[datetime(2026, 9, 25, 12, 40, tzinfo=UTC)]["binance"]) == 2
    with pytest.raises(SystemExit, match="naive timestamp"):
        runner._utc(datetime(2026, 9, 25, 12, 40))
