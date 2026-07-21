"""Adversarial unit tests for analytics/percentile_engine (pure, no I/O).

Covers Percentile Contract Revision 0.2.4 (docs/STAGE2_SPEC.md §12). No DB,
Docker, Redis, network, real clock, env, sleep, or subprocess.
"""
from __future__ import annotations

import dataclasses
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from analytics.feature_engine.models import ExchangeFeatureVector
from analytics.feature_engine.consensus_models import ConsensusFeatureVector
from analytics.percentile_engine import (
    compute_percentile_snapshot, ConfidenceTierThresholds, PercentileError,
    PercentileRequest, PercentileSample, PercentileSnapshot,
    EXCHANGE_SCOPE_METRICS, CONSENSUS_SCOPE_METRICS, VALID_WINDOWS,
)

B = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
CV16 = "0123456789abcdef"
CH64 = "a" * 64
THR = ConfidenceTierThresholds(3, 7, 30)
DAY = timedelta(days=1)
MIN = timedelta(minutes=1)


def _sample(ts, value, *, scope="exchange", exchange="binance", symbol="BTCUSDT",
            market_type="perp", metric="price_move_pct", timeframe="5m",
            fsv=1, cv=CV16):
    return PercentileSample(scope=scope, exchange=exchange, symbol=symbol,
        market_type=market_type, metric=metric, timeframe=timeframe,
        bucket_ts=ts, value=value, feature_schema_version=fsv, calculation_version=cv)


def _req(value, samples, *, scope="exchange", exchange="binance", symbol="BTCUSDT",
         market_type="perp", metric="price_move_pct", timeframe="5m",
         window="30d", bucket_ts=B, fsv=1, cv=CV16, config_hash=CH64,
         thresholds=THR):
    return PercentileRequest(scope=scope, exchange=exchange, symbol=symbol,
        market_type=market_type, metric=metric, timeframe=timeframe,
        percentile_window=window, bucket_ts=bucket_ts, value=value, samples=samples,
        confidence_tier_thresholds=thresholds, config_hash=config_hash,
        config_version="2.1.0", code_version="t", feature_schema_version=fsv,
        calculation_version=cv)


def _spread(values, *, start_offset=MIN, metric="price_move_pct"):
    """Distinct earlier timestamps (1 min apart, well inside the window)."""
    return [_sample(B - start_offset - i * MIN, v, metric=metric)
            for i, v in enumerate(values)]


# ================================ rank (§12.1) ==============================
@pytest.mark.parametrize("vals, cur, expected", [
    ([1, 2, 3], 1, 0.5 / 3),
    ([1, 2, 3], 2, 0.5),
    ([1, 2, 3], 3, 2.5 / 3),
    ([1, 2, 2, 3], 2, 0.5),
    ([5, 5, 5], 5, 0.5),
])
def test_rank_worked_examples(vals, cur, expected):
    r = compute_percentile_snapshot(_req(cur, _spread(vals))).percentile_rank
    assert r == expected           # exact, no rounding


def test_rank_below_min_is_zero_above_max_is_one():
    assert compute_percentile_snapshot(_req(0.0, _spread([2, 3, 4]))).percentile_rank == 0.0
    assert compute_percentile_snapshot(_req(9.0, _spread([2, 3, 4]))).percentile_rank == 1.0


def test_rank_negative_and_zero_values():
    r = compute_percentile_snapshot(_req(0.0, _spread([-2.0, -1.0, 1.0]))).percentile_rank
    assert r == (2 + 0.5 * 0) / 3    # two strictly-less, zero is valid current value


def test_rank_not_rounded():
    r = compute_percentile_snapshot(_req(1.0, _spread([1, 2, 3, 4, 5, 6, 7]))).percentile_rank
    assert r == 0.5 / 7              # a value that is not a round decimal


# ============================== windows (§12.2) =============================
@pytest.mark.parametrize("window", ["7d", "30d"])
def test_lower_boundary_included(window):
    w = timedelta(days=7 if window == "7d" else 30)
    s = [_sample(B - w, 1.0), _sample(B - w + MIN, 2.0)]
    snap = compute_percentile_snapshot(_req(1.5, s, window=window))
    assert snap.sample_size == 2
    assert snap.sample_window_start == B - w


@pytest.mark.parametrize("delta", [timedelta(microseconds=1), timedelta(seconds=1)])
def test_just_before_lower_boundary_rejected(delta):
    s = [_sample(B - timedelta(days=30) - delta, 1.0)]
    with pytest.raises(PercentileError):
        compute_percentile_snapshot(_req(1.0, s, window="30d"))


def test_current_bucket_sample_rejected():
    with pytest.raises(PercentileError):
        compute_percentile_snapshot(_req(1.0, [_sample(B, 1.0)]))


def test_future_bucket_sample_rejected():
    with pytest.raises(PercentileError):
        compute_percentile_snapshot(_req(1.0, [_sample(B + MIN, 1.0)]))


def test_newest_sample_strictly_earlier():
    snap = compute_percentile_snapshot(_req(1.0, _spread([1, 2, 3])))
    assert snap.sample_window_end < B


def test_empty_distribution_output():
    snap = compute_percentile_snapshot(_req(1.0, []))
    assert snap.sample_size == 0 and snap.percentile_rank is None
    assert snap.sample_window_start is None and snap.sample_window_end is None
    assert snap.confidence_tier == "none"


# ========================= scope & identity (§12.3) =========================
def test_exchange_scope_valid():
    snap = compute_percentile_snapshot(_req(1.0, _spread([1, 2, 3])))
    assert snap.scope == "exchange" and snap.exchange == "binance"


def test_consensus_scope_valid():
    s = _spread([1, 2, 3], metric="price_move_pct_median")
    s = [dataclasses.replace(x, scope="consensus", exchange="") for x in s]
    snap = compute_percentile_snapshot(_req(
        1.5, s, scope="consensus", exchange="", metric="price_move_pct_median"))
    assert snap.scope == "consensus" and snap.exchange == ""


def test_exchange_scope_empty_exchange_rejected():
    with pytest.raises(PercentileError):
        compute_percentile_snapshot(_req(1.0, [], exchange=""))


def test_consensus_scope_nonempty_exchange_rejected():
    with pytest.raises(PercentileError):
        compute_percentile_snapshot(_req(1.0, [], scope="consensus", exchange="binance",
                                          metric="price_move_pct_median"))


def test_inactive_exchange_rejected():
    with pytest.raises(PercentileError):
        compute_percentile_snapshot(_req(1.0, [], exchange="bitget"))


def test_cross_exchange_pooling_rejected():
    # a bybit sample supplied to a binance request must fail loudly, not pool
    s = [_sample(B - MIN, 1.0, exchange="bybit")]
    with pytest.raises(PercentileError):
        compute_percentile_snapshot(_req(1.0, s, exchange="binance"))


@pytest.mark.parametrize("field, bad", [
    ("scope", "consensus"), ("symbol", "ETHUSDT"), ("market_type", "spot"),
    ("metric", "range_width_pct"), ("timeframe", "1m"),
    ("feature_schema_version", 2), ("calculation_version", "f" * 16),
    ("exchange", "okx"),
])
def test_sample_identity_mismatch_rejected(field, bad):
    good = _sample(B - MIN, 1.0)
    bad_sample = dataclasses.replace(good, **{field: bad})
    with pytest.raises(PercentileError):
        compute_percentile_snapshot(_req(1.0, [good, bad_sample]))


def test_unknown_metric_rejected():
    with pytest.raises(PercentileError):
        compute_percentile_snapshot(_req(1.0, [], metric="not_a_metric"))


def test_exchange_metric_rejected_at_consensus_scope():
    with pytest.raises(PercentileError):
        compute_percentile_snapshot(_req(1.0, [], scope="consensus", exchange="",
                                          metric="price_move_pct"))


def test_consensus_metric_rejected_at_exchange_scope():
    with pytest.raises(PercentileError):
        compute_percentile_snapshot(_req(1.0, [], metric="price_move_pct_median"))


@pytest.mark.parametrize("metric", EXCHANGE_SCOPE_METRICS)
def test_all_exchange_metrics_accepted(metric):
    s = _spread([1.0, 2.0], metric=metric)
    snap = compute_percentile_snapshot(_req(1.5, s, metric=metric))
    assert snap.metric == metric and snap.sample_size == 2


@pytest.mark.parametrize("metric", CONSENSUS_SCOPE_METRICS)
def test_all_consensus_metrics_accepted(metric):
    s = [dataclasses.replace(x, scope="consensus", exchange="")
         for x in _spread([1.0, 2.0], metric=metric)]
    snap = compute_percentile_snapshot(_req(
        1.5, s, scope="consensus", exchange="", metric=metric))
    assert snap.metric == metric and snap.sample_size == 2


def test_invalid_window_rejected():
    with pytest.raises(PercentileError):
        compute_percentile_snapshot(_req(1.0, [], window="14d"))


def test_bad_config_hash_rejected():
    with pytest.raises(PercentileError):
        compute_percentile_snapshot(_req(1.0, [], config_hash="bad"))


def test_bad_calculation_version_rejected():
    with pytest.raises(PercentileError):
        compute_percentile_snapshot(_req(1.0, [], cv="XYZ"))


def test_naive_bucket_ts_rejected():
    with pytest.raises(PercentileError):
        compute_percentile_snapshot(_req(1.0, [], bucket_ts=datetime(2026, 2, 1)))


def test_non_utc_bucket_ts_rejected():
    tz = timezone(timedelta(hours=2))
    with pytest.raises(PercentileError):
        compute_percentile_snapshot(_req(1.0, [], bucket_ts=datetime(2026, 2, 1, tzinfo=tz)))


# ===================== NULL & invalid numbers (§12.5) =======================
def test_current_null_gives_null_rank_but_valid_snapshot():
    snap = compute_percentile_snapshot(_req(None, _spread([1, 2, 3])))
    assert snap.value is None and snap.percentile_rank is None
    assert snap.sample_size == 3          # distribution still computed


def test_historical_null_excluded_and_not_counted():
    s = _spread([1.0, None, 3.0])
    snap = compute_percentile_snapshot(_req(2.0, s))
    assert snap.sample_size == 2          # the NULL is absent, not zero
    r = snap.percentile_rank
    assert r == (1 + 0.5 * 0) / 2         # ranked against {1.0, 3.0}


def test_all_historical_null():
    snap = compute_percentile_snapshot(_req(2.0, _spread([None, None, None])))
    assert snap.sample_size == 0 and snap.percentile_rank is None
    assert snap.confidence_tier == "none"


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_nan_inf_current_rejected(bad):
    with pytest.raises(PercentileError):
        compute_percentile_snapshot(_req(bad, _spread([1, 2, 3])))


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_nan_inf_historical_rejected(bad):
    with pytest.raises(PercentileError):
        compute_percentile_snapshot(_req(1.0, [_sample(B - MIN, bad)]))


def test_bool_rejected_as_value():
    with pytest.raises(PercentileError):
        compute_percentile_snapshot(_req(True, _spread([1, 2, 3])))
    with pytest.raises(PercentileError):
        compute_percentile_snapshot(_req(1.0, [_sample(B - MIN, True)]))


def test_zero_is_counted():
    snap = compute_percentile_snapshot(_req(1.0, _spread([0.0, 0.0, 0.0])))
    assert snap.sample_size == 3
    assert snap.percentile_rank == 1.0    # 1.0 > all three zeros


# =============================== duplicates (§12.5) =========================
def test_identical_numeric_duplicate_collapses():
    ts = B - MIN
    snap = compute_percentile_snapshot(_req(1.0, [
        _sample(ts, 5.0), _sample(ts, 5.0), _sample(B - 2 * MIN, 6.0)]))
    assert snap.sample_size == 2          # the identical pair collapsed to one


def test_duplicate_null_collapses():
    ts = B - MIN
    snap = compute_percentile_snapshot(_req(1.0, [
        _sample(ts, None), _sample(ts, None), _sample(B - 2 * MIN, 6.0)]))
    assert snap.sample_size == 1          # collapsed NULL contributes nothing


def test_conflicting_numeric_duplicate_rejected():
    ts = B - MIN
    with pytest.raises(PercentileError):
        compute_percentile_snapshot(_req(1.0, [_sample(ts, 5.0), _sample(ts, 6.0)]))


def test_null_vs_numeric_duplicate_rejected():
    ts = B - MIN
    with pytest.raises(PercentileError):
        compute_percentile_snapshot(_req(1.0, [_sample(ts, None), _sample(ts, 6.0)]))


def test_shuffled_input_identical_output():
    s = _spread([3.0, 1.0, 2.0, 5.0, 4.0])
    a = compute_percentile_snapshot(_req(2.5, s))
    b = compute_percentile_snapshot(_req(2.5, list(reversed(s))))
    assert a == b


# ============================ confidence tier (§12.6) =======================
def _tier(earliest_delta, *, n=5, window="30d"):
    s = [_sample(B - earliest_delta, 1.0)]
    for i in range(1, n):
        s.append(_sample(B - earliest_delta + i * MIN, 1.0 + i))
    return compute_percentile_snapshot(_req(1.0, s, window=window)).confidence_tier


def test_tier_one_sample_is_none():
    assert compute_percentile_snapshot(
        _req(1.0, [_sample(B - 10 * DAY, 1.0)])).confidence_tier == "none"


def test_tier_exact_3d_is_low():
    assert _tier(3 * DAY) == "low"


def test_tier_just_below_3d_is_none():
    assert _tier(3 * DAY - MIN) == "none"


def test_tier_exact_7d_is_building():
    assert _tier(7 * DAY) == "building"


def test_tier_just_below_7d_is_low():
    assert _tier(7 * DAY - MIN) == "low"


def test_tier_exact_30d_is_mature():
    assert _tier(30 * DAY) == "mature"


def test_tier_one_minute_below_30d_is_building():
    assert _tier(30 * DAY - MIN) == "building"


def test_7d_window_max_is_building():
    # oldest possible 7d sample is at B-7d -> span 7 -> building (never mature)
    assert _tier(7 * DAY, window="7d") == "building"


def test_30d_window_can_mature():
    assert _tier(30 * DAY, window="30d") == "mature"


def test_sparse_long_span_follows_span_contract():
    # only two samples but spanning ~30 days -> mature by the frozen span rule
    s = [_sample(B - 30 * DAY, 1.0), _sample(B - MIN, 2.0)]
    assert compute_percentile_snapshot(_req(1.5, s)).confidence_tier == "mature"


# ===================== ConfidenceTierThresholds validation ==================
@pytest.mark.parametrize("args", [
    (7, 3, 30), (3, 7, 7), (3, 3, 30),          # not strictly increasing
    (0, 7, 30), (-1, 7, 30),                     # not > 0
    (3.0, 7, 30), (True, 7, 30),                 # not int / bool
])
def test_confidence_thresholds_rejected(args):
    with pytest.raises(PercentileError):
        ConfidenceTierThresholds(*args)


# ========================= structural guarantees ===========================
def test_models_are_frozen():
    snap = compute_percentile_snapshot(_req(1.0, _spread([1, 2, 3])))
    for obj in (snap, _sample(B - MIN, 1.0), THR):
        with pytest.raises(dataclasses.FrozenInstanceError):
            obj.scope = "x" if hasattr(obj, "scope") else None


def test_request_samples_frozen_to_tuple():
    lst = [_sample(B - MIN, 1.0)]
    req = _req(1.0, lst)
    assert isinstance(req.samples, tuple)
    lst.append(_sample(B - 2 * MIN, 2.0))     # mutating caller's list...
    assert len(req.samples) == 1              # ...never affects the request


def test_output_fields_match_schema_minus_computed_at():
    sql = Path("storage/stage2_schema.sql").read_text(encoding="utf-8")
    m = re.search(
        r"CREATE TABLE IF NOT EXISTS percentile_snapshots\s*\((.*?)\n\s*PRIMARY KEY",
        sql, re.S)
    assert m
    cols = re.findall(
        r"^\s+([a-z_]+)\s+(?:TEXT|JSONB|INTEGER|DOUBLE PRECISION|TIMESTAMPTZ|BOOLEAN)",
        m.group(1), re.M)
    schema_cols = {c for c in cols if c != "computed_at"}
    fields = {f.name for f in dataclasses.fields(PercentileSnapshot)}
    assert fields == schema_cols
    assert "computed_at" not in fields


def test_metric_constants_match_feature_vector_fields():
    efv = {f.name for f in dataclasses.fields(ExchangeFeatureVector)}
    cons = {f.name for f in dataclasses.fields(ConsensusFeatureVector)}
    assert set(EXCHANGE_SCOPE_METRICS) <= efv
    assert set(CONSENSUS_SCOPE_METRICS) <= cons


def test_forbidden_metrics_absent():
    forbidden = {"volume_raw", "volume_raw_unit", "close_price", "oi_unit",
                 "price_move_pct_mad", "oi_change_pct_mad", "funding_rate_mad",
                 "price_direction_agreement", "flow_direction_agreement",
                 "oi_direction_agreement", "consensus_confidence",
                 "min_coverage_ratio", "exchanges_expected_max",
                 "is_partial_consensus", "coverage_by_metric",
                 "provenance_by_metric", "outlier_exchanges",
                 "liquidation_feed_quality_by_exchange"}
    allowed = set(EXCHANGE_SCOPE_METRICS) | set(CONSENSUS_SCOPE_METRICS)
    assert forbidden.isdisjoint(allowed)


def test_no_forbidden_imports_in_core():
    forbidden = ("import asyncio", "import subprocess", "import socket",
                 "import os", "import requests", "aiohttp", "asyncpg", "redis",
                 "datetime.now", "utcnow", "time.time", "getenv", "environ", "open(")
    for name in ("models.py", "compute.py"):
        src = Path("analytics/percentile_engine") / name
        text = src.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{name} contains forbidden token {token!r}"


def test_replay_same_logical_input_matches_field_for_field():
    s1 = _spread([1.0, 2.0, 3.0, 4.0])
    # a second, independently-constructed set of samples in a different order
    s2 = [_sample(x.bucket_ts, x.value) for x in reversed(s1)]
    a = compute_percentile_snapshot(_req(2.5, s1))
    b = compute_percentile_snapshot(_req(2.5, s2))
    assert a == b
    assert dataclasses.astuple(a) == dataclasses.astuple(b)


def test_valid_windows_constant():
    assert VALID_WINDOWS == ("7d", "30d")
