"""Tests for storage/v2_alignment_readers.py (Stage 3 — Multi-timeframe
Alignment PR 2/PR 3) and its storage.db.Database wrappers. No real DB —
fake asyncpg-like connections/pools only, following the existing storage
test style (tests/storage/test_stage2_writers.py,
tests/storage/test_v2_episode_event_writers.py).

Exercises the five read primitives' central contract: EXACT-bucket
consensus/percentile/reference-feature identity (no older-bucket
fallback), bounded-latest health-at-cutoff (never a row after the cutoff,
exact-cutoff eligible), half-open `[bucket_start, bucket_end)` raw
`klines_1m` reads, explicit calculation_version everywhere (except raw
klines, which carry none), JSONB detachment/immutability, fail-closed
argument validation before any connection is acquired, and negative
SQL-shape checks proving no forbidden "latest now"/fallback semantics.
"""
from __future__ import annotations

import inspect
import json
from datetime import datetime, timedelta, timezone
from types import MappingProxyType

import pytest

from storage.db import Database
from storage.v2_alignment_readers import (
    V2AlignmentReaderError,
    read_v2_consensus_feature, read_v2_consensus_percentiles,
    read_v2_data_health_at_cutoff, read_v2_reference_feature,
    read_v2_reference_klines, validate_consensus_feature_args,
    validate_data_health_args, validate_reference_feature_args,
    validate_reference_klines_args,
)
from storage import v2_alignment_readers as readers_module

UTC = timezone.utc
B = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
H16 = "a" * 16
H64 = "b" * 64


# ============================================================================
# fake asyncpg pool (Database wrapper tests)
# ============================================================================
class FakeConn:
    """Dumb fake: returns exactly the canned rows given, ignoring args.
    Used to prove the reader's OWN defensive row-identity checks fire when
    a connection returns something it should not (a broken DB or a
    misbehaving test double) — never assume a returned row is trustworthy."""
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.fetch_calls: list[tuple] = []

    async def fetch(self, sql, *args):
        self.fetch_calls.append((sql, args))
        return self.rows


class _Acquire:
    def __init__(self, pool):
        self.pool = pool

    async def __aenter__(self):
        self.pool.acquire_count += 1
        return self.pool.conn

    async def __aexit__(self, *exc):
        return False


class FakePool:
    def __init__(self, conn=None):
        self.conn = conn if conn is not None else FakeConn()
        self.acquire_count = 0

    def acquire(self):
        return _Acquire(self)


def _db(conn=None):
    db = Database("postgresql://unused")
    db.pool = FakePool(conn)
    return db


def _run(coro):
    import asyncio
    return asyncio.run(coro)


# ============================================================================
# behavior-simulating fake connections — prove "no fallback"/"bounded
# cutoff" BEHAVIORALLY (not merely by inspecting SQL text), by replicating
# the real WHERE-clause semantics in Python against a candidate row set.
# ============================================================================
class ExactMatchConsensusConn:
    """Simulates consensus_feature_vectors' exact-identity WHERE clause."""
    def __init__(self, rows):
        self.rows = rows
        self.fetch_calls = []

    async def fetch(self, sql, symbol, market_type, timeframe, bucket_ts, calculation_version):
        self.fetch_calls.append((sql, (symbol, market_type, timeframe, bucket_ts, calculation_version)))
        return [r for r in self.rows if (
            r["symbol"], r["market_type"], r["timeframe"], r["bucket_ts"], r["calculation_version"]
        ) == (symbol, market_type, timeframe, bucket_ts, calculation_version)]


class ExactMatchPercentileConn:
    """Simulates percentile_snapshots' WHERE clause, INCLUDING the
    hardcoded scope='consensus'/exchange='' literals — a row with any
    other scope/exchange is filtered out exactly as real SQL would,
    proving exchange-scoped rows are structurally unreachable here."""
    def __init__(self, rows):
        self.rows = rows
        self.fetch_calls = []

    async def fetch(self, sql, symbol, market_type, timeframe, bucket_ts, calculation_version):
        self.fetch_calls.append((sql, (symbol, market_type, timeframe, bucket_ts, calculation_version)))
        matched = [r for r in self.rows if (
            r["scope"], r["exchange"], r["symbol"], r["market_type"], r["timeframe"],
            r["bucket_ts"], r["calculation_version"]
        ) == ("consensus", "", symbol, market_type, timeframe, bucket_ts, calculation_version)]
        return sorted(matched, key=lambda r: (r["metric"], r["percentile_window"]))


class BoundedLatestHealthConn:
    """Simulates data_health_snapshots' DISTINCT ON (exchange, metric) ...
    ORDER BY snapshot_ts DESC bounded-latest query."""
    def __init__(self, rows):
        self.rows = rows
        self.fetch_calls = []

    async def fetch(self, sql, symbol, market_type, calculation_version, exchanges, metrics, cutoff_ts):
        self.fetch_calls.append((sql, (symbol, market_type, calculation_version, exchanges, metrics, cutoff_ts)))
        eligible = [r for r in self.rows if (
            r["symbol"] == symbol and r["market_type"] == market_type
            and r["calculation_version"] == calculation_version
            and r["exchange"] in exchanges and r["metric"] in metrics
            and r["snapshot_ts"] <= cutoff_ts
        )]
        best: dict[tuple, dict] = {}
        for r in eligible:
            key = (r["exchange"], r["metric"])
            if key not in best or r["snapshot_ts"] > best[key]["snapshot_ts"]:
                best[key] = r
        return list(best.values())


# ============================================================================
# row factories
# ============================================================================
def make_consensus_row(**over):
    base = dict(
        symbol="BTCUSDT", market_type="perp", timeframe="5m", bucket_ts=B,
        feature_schema_version=1, calculation_version=H16,
        coverage_by_metric=json.dumps({"oi": {"available": 2, "expected": 3}}),
        provenance_by_metric=json.dumps({}),
        data_confidence_by_metric=json.dumps({"oi": 0.81}),
        exchanges_expected_max=3, min_coverage_ratio=0.66, data_confidence_overall=0.8,
        price_direction_agreement=1.0, flow_direction_agreement=0.5, oi_direction_agreement=None,
        price_move_pct_median=0.1, range_width_pct_median=1.0, oi_change_pct_median=None,
        funding_rate_median=0.0001, funding_rate_mad=0.00001,
        volume_notional_usd_sum=1.0, taker_buy_notional_usd_sum=1.0,
        taker_sell_notional_usd_sum=1.0, taker_delta_notional_usd_sum=1.0,
        cvd_delta_notional_usd_sum=1.0,
        observed_long_liquidation_notional_sum=None, observed_short_liquidation_notional_sum=None,
        observed_liquidation_event_count_sum=None, liquidation_feed_quality_by_exchange=None,
        price_move_pct_mad=0.01, oi_change_pct_mad=None, outlier_exchanges=None,
        consensus_confidence=87.5, is_partial_consensus=False,
        computed_at=B, config_hash=H64, config_version="2.1.0", code_version="deadbeef",
    )
    base.update(over)
    return base


def make_percentile_row(**over):
    base = dict(
        scope="consensus", exchange="", symbol="BTCUSDT", market_type="perp",
        metric="oi_change_pct", timeframe="5m", percentile_window="7d", bucket_ts=B,
        value=0.5, percentile_rank=0.9, sample_size=100,
        sample_window_start=B - timedelta(days=7), sample_window_end=B - timedelta(minutes=5),
        confidence_tier="mature", computed_at=B, config_hash=H64, config_version="2.1.0",
        code_version="deadbeef", feature_schema_version=1, calculation_version=H16,
    )
    base.update(over)
    return base


def make_health_row(**over):
    base = dict(
        symbol="BTCUSDT", exchange="binance", market_type="perp", metric="price",
        snapshot_ts=B, last_event_at=B, expected_interval_s=60, lateness_ms=100,
        gap_count=0, largest_gap_s=None, backfill_status="complete",
        coverage_window_start=None, coverage_window_end=None, is_stale=False, is_usable=True,
        computed_at=B, config_hash=H64, config_version="2.1.0", code_version="deadbeef",
        feature_schema_version=1, calculation_version=H16,
    )
    base.update(over)
    return base


# ============================================================================
# 1. CONSENSUS
# ============================================================================
def test_consensus_exact_identity_hit():
    conn = ExactMatchConsensusConn([make_consensus_row()])
    result = _run(read_v2_consensus_feature(
        conn, symbol="BTCUSDT", market_type="perp", timeframe="5m",
        bucket_ts=B, calculation_version=H16))
    assert result is not None
    assert result["symbol"] == "BTCUSDT" and result["bucket_ts"] == B
    assert isinstance(result, MappingProxyType)


def test_consensus_exact_identity_missing_returns_none():
    conn = ExactMatchConsensusConn([])
    result = _run(read_v2_consensus_feature(
        conn, symbol="BTCUSDT", market_type="perp", timeframe="5m",
        bucket_ts=B, calculation_version=H16))
    assert result is None


def test_consensus_older_bucket_no_fallback():
    older = make_consensus_row(bucket_ts=B - timedelta(minutes=15))
    conn = ExactMatchConsensusConn([older])
    result = _run(read_v2_consensus_feature(
        conn, symbol="BTCUSDT", market_type="perp", timeframe="5m",
        bucket_ts=B, calculation_version=H16))
    assert result is None


def test_consensus_future_bucket_no_fallback():
    future = make_consensus_row(bucket_ts=B + timedelta(minutes=15))
    conn = ExactMatchConsensusConn([future])
    result = _run(read_v2_consensus_feature(
        conn, symbol="BTCUSDT", market_type="perp", timeframe="5m",
        bucket_ts=B, calculation_version=H16))
    assert result is None


def test_consensus_wrong_calculation_version_excluded():
    row = make_consensus_row(calculation_version="c" * 16)
    conn = ExactMatchConsensusConn([row])
    result = _run(read_v2_consensus_feature(
        conn, symbol="BTCUSDT", market_type="perp", timeframe="5m",
        bucket_ts=B, calculation_version=H16))
    assert result is None


def test_consensus_json_columns_detached_and_immutable():
    conn = ExactMatchConsensusConn([make_consensus_row()])
    result = _run(read_v2_consensus_feature(
        conn, symbol="BTCUSDT", market_type="perp", timeframe="5m",
        bucket_ts=B, calculation_version=H16))
    assert isinstance(result["coverage_by_metric"], MappingProxyType)
    assert isinstance(result["coverage_by_metric"]["oi"], MappingProxyType)
    assert result["coverage_by_metric"]["oi"]["available"] == 2
    assert result["liquidation_feed_quality_by_exchange"] is None  # nullable, absent


def test_consensus_json_already_decoded_dict_also_accepted():
    row = make_consensus_row(coverage_by_metric={"oi": {"available": 1}})
    conn = ExactMatchConsensusConn([row])
    result = _run(read_v2_consensus_feature(
        conn, symbol="BTCUSDT", market_type="perp", timeframe="5m",
        bucket_ts=B, calculation_version=H16))
    assert dict(result["coverage_by_metric"]) == {"oi": MappingProxyType({"available": 1})}


def test_consensus_malformed_json_text_rejected():
    row = make_consensus_row(coverage_by_metric="{not valid json")
    conn = ExactMatchConsensusConn([row])
    with pytest.raises(V2AlignmentReaderError, match="malformed JSON"):
        _run(read_v2_consensus_feature(
            conn, symbol="BTCUSDT", market_type="perp", timeframe="5m",
            bucket_ts=B, calculation_version=H16))


def test_consensus_required_json_null_rejected():
    row = make_consensus_row(coverage_by_metric=None)
    conn = ExactMatchConsensusConn([row])
    with pytest.raises(V2AlignmentReaderError, match="must not be NULL"):
        _run(read_v2_consensus_feature(
            conn, symbol="BTCUSDT", market_type="perp", timeframe="5m",
            bucket_ts=B, calculation_version=H16))


def test_consensus_more_than_one_row_fails_loudly():
    conn = FakeConn([make_consensus_row(), make_consensus_row()])
    with pytest.raises(V2AlignmentReaderError, match="expected at most one"):
        _run(read_v2_consensus_feature(
            conn, symbol="BTCUSDT", market_type="perp", timeframe="5m",
            bucket_ts=B, calculation_version=H16))


def test_consensus_row_identity_mismatch_rejected():
    # A broken/misbehaving connection returns a row that does not actually
    # match the requested identity — must never be trusted blindly.
    conn = FakeConn([make_consensus_row(timeframe="15m")])
    with pytest.raises(V2AlignmentReaderError, match="does not match"):
        _run(read_v2_consensus_feature(
            conn, symbol="BTCUSDT", market_type="perp", timeframe="5m",
            bucket_ts=B, calculation_version=H16))


# ============================================================================
# 2. PERCENTILES
# ============================================================================
def test_percentiles_exact_consensus_scope_rows_returned():
    rows = [make_percentile_row(metric="oi_change_pct", percentile_window="7d"),
            make_percentile_row(metric="oi_change_pct", percentile_window="30d")]
    conn = ExactMatchPercentileConn(rows)
    result = _run(read_v2_consensus_percentiles(
        conn, symbol="BTCUSDT", market_type="perp", timeframe="5m",
        bucket_ts=B, calculation_version=H16))
    assert len(result) == 2
    assert all(isinstance(r, MappingProxyType) for r in result)


def test_percentiles_exchange_scoped_rows_never_selected():
    exchange_row = make_percentile_row(scope="exchange", exchange="binance")
    conn = ExactMatchPercentileConn([exchange_row])
    result = _run(read_v2_consensus_percentiles(
        conn, symbol="BTCUSDT", market_type="perp", timeframe="5m",
        bucket_ts=B, calculation_version=H16))
    assert result == ()


def test_percentiles_no_older_bucket_fallback():
    older = make_percentile_row(bucket_ts=B - timedelta(minutes=15))
    conn = ExactMatchPercentileConn([older])
    result = _run(read_v2_consensus_percentiles(
        conn, symbol="BTCUSDT", market_type="perp", timeframe="5m",
        bucket_ts=B, calculation_version=H16))
    assert result == ()


def test_percentiles_wrong_calculation_version_excluded():
    row = make_percentile_row(calculation_version="c" * 16)
    conn = ExactMatchPercentileConn([row])
    result = _run(read_v2_consensus_percentiles(
        conn, symbol="BTCUSDT", market_type="perp", timeframe="5m",
        bucket_ts=B, calculation_version=H16))
    assert result == ()


def test_percentiles_deterministic_metric_window_ordering():
    rows = [
        make_percentile_row(metric="price_move_pct", percentile_window="30d"),
        make_percentile_row(metric="oi_change_pct", percentile_window="30d"),
        make_percentile_row(metric="oi_change_pct", percentile_window="7d"),
    ]
    conn = ExactMatchPercentileConn(rows)
    result = _run(read_v2_consensus_percentiles(
        conn, symbol="BTCUSDT", market_type="perp", timeframe="5m",
        bucket_ts=B, calculation_version=H16))
    got = [(r["metric"], r["percentile_window"]) for r in result]
    # ORDER BY metric ASC, percentile_window ASC is plain lexical text
    # ordering — "30d" sorts before "7d" ('3' < '7'), not numeric order.
    assert got == [("oi_change_pct", "30d"), ("oi_change_pct", "7d"), ("price_move_pct", "30d")]


def test_percentiles_empty_result_is_empty_tuple():
    conn = ExactMatchPercentileConn([])
    result = _run(read_v2_consensus_percentiles(
        conn, symbol="BTCUSDT", market_type="perp", timeframe="5m",
        bucket_ts=B, calculation_version=H16))
    assert result == ()
    assert isinstance(result, tuple)


def test_percentiles_row_identity_mismatch_rejected():
    conn = FakeConn([make_percentile_row(exchange="binance")])  # scope stays 'consensus' but exchange set
    with pytest.raises(V2AlignmentReaderError, match="does not match"):
        _run(read_v2_consensus_percentiles(
            conn, symbol="BTCUSDT", market_type="perp", timeframe="5m",
            bucket_ts=B, calculation_version=H16))


def test_percentiles_duplicate_logical_row_rejected():
    conn = FakeConn([make_percentile_row(), make_percentile_row()])
    with pytest.raises(V2AlignmentReaderError, match="duplicate"):
        _run(read_v2_consensus_percentiles(
            conn, symbol="BTCUSDT", market_type="perp", timeframe="5m",
            bucket_ts=B, calculation_version=H16))


# ============================================================================
# 3. HEALTH — bounded-latest at explicit cutoff
# ============================================================================
def test_health_snapshot_before_cutoff_eligible():
    row = make_health_row(snapshot_ts=B - timedelta(minutes=5))
    conn = BoundedLatestHealthConn([row])
    result = _run(read_v2_data_health_at_cutoff(
        conn, symbol="BTCUSDT", market_type="perp", exchanges=["binance"],
        metrics=["price"], cutoff_ts=B, calculation_version=H16))
    assert result[("binance", "price")] is not None


def test_health_snapshot_exactly_at_cutoff_eligible():
    row = make_health_row(snapshot_ts=B)
    conn = BoundedLatestHealthConn([row])
    result = _run(read_v2_data_health_at_cutoff(
        conn, symbol="BTCUSDT", market_type="perp", exchanges=["binance"],
        metrics=["price"], cutoff_ts=B, calculation_version=H16))
    assert result[("binance", "price")]["snapshot_ts"] == B


def test_health_snapshot_after_cutoff_forbidden():
    row = make_health_row(snapshot_ts=B + timedelta(minutes=5))
    conn = BoundedLatestHealthConn([row])
    result = _run(read_v2_data_health_at_cutoff(
        conn, symbol="BTCUSDT", market_type="perp", exchanges=["binance"],
        metrics=["price"], cutoff_ts=B, calculation_version=H16))
    assert result[("binance", "price")] is None


def test_health_newest_eligible_row_per_pair_selected():
    rows = [
        make_health_row(snapshot_ts=B - timedelta(minutes=10)),
        make_health_row(snapshot_ts=B - timedelta(minutes=5)),
        make_health_row(snapshot_ts=B + timedelta(minutes=5)),  # ineligible
    ]
    conn = BoundedLatestHealthConn(rows)
    result = _run(read_v2_data_health_at_cutoff(
        conn, symbol="BTCUSDT", market_type="perp", exchanges=["binance"],
        metrics=["price"], cutoff_ts=B, calculation_version=H16))
    assert result[("binance", "price")]["snapshot_ts"] == B - timedelta(minutes=5)


def test_health_historical_cutoff_never_sees_newer_row():
    rows = [make_health_row(snapshot_ts=B - timedelta(hours=1)),
            make_health_row(snapshot_ts=B + timedelta(hours=1))]
    conn = BoundedLatestHealthConn(rows)
    result = _run(read_v2_data_health_at_cutoff(
        conn, symbol="BTCUSDT", market_type="perp", exchanges=["binance"],
        metrics=["price"], cutoff_ts=B, calculation_version=H16))
    assert result[("binance", "price")]["snapshot_ts"] == B - timedelta(hours=1)


def test_health_missing_requested_pair_explicit_none():
    conn = BoundedLatestHealthConn([make_health_row(exchange="binance")])
    result = _run(read_v2_data_health_at_cutoff(
        conn, symbol="BTCUSDT", market_type="perp", exchanges=["binance", "bybit"],
        metrics=["price"], cutoff_ts=B, calculation_version=H16))
    assert set(result.keys()) == {("binance", "price"), ("bybit", "price")}
    assert result[("binance", "price")] is not None
    assert result[("bybit", "price")] is None


def test_health_missing_pair_never_fabricated_healthy_default():
    conn = BoundedLatestHealthConn([])
    result = _run(read_v2_data_health_at_cutoff(
        conn, symbol="BTCUSDT", market_type="perp", exchanges=["binance"],
        metrics=["price"], cutoff_ts=B, calculation_version=H16))
    assert result[("binance", "price")] is None  # never a fabricated is_stale=False row


def test_health_cross_product_of_exchanges_and_metrics():
    rows = [make_health_row(exchange="binance", metric="price"),
            make_health_row(exchange="binance", metric="oi")]
    conn = BoundedLatestHealthConn(rows)
    result = _run(read_v2_data_health_at_cutoff(
        conn, symbol="BTCUSDT", market_type="perp", exchanges=["binance", "bybit"],
        metrics=["price", "oi"], cutoff_ts=B, calculation_version=H16))
    assert set(result.keys()) == {
        ("binance", "price"), ("binance", "oi"), ("bybit", "price"), ("bybit", "oi")}


def test_health_wrong_calculation_version_excluded():
    row = make_health_row(calculation_version="c" * 16)
    conn = BoundedLatestHealthConn([row])
    result = _run(read_v2_data_health_at_cutoff(
        conn, symbol="BTCUSDT", market_type="perp", exchanges=["binance"],
        metrics=["price"], cutoff_ts=B, calculation_version=H16))
    assert result[("binance", "price")] is None


def test_health_unexpected_pair_rejected():
    conn = FakeConn([make_health_row(exchange="okx")])  # not in requested exchanges
    with pytest.raises(V2AlignmentReaderError, match="unrequested pair"):
        _run(read_v2_data_health_at_cutoff(
            conn, symbol="BTCUSDT", market_type="perp", exchanges=["binance"],
            metrics=["price"], cutoff_ts=B, calculation_version=H16))


def test_health_duplicate_pair_rejected():
    conn = FakeConn([make_health_row(), make_health_row()])
    with pytest.raises(V2AlignmentReaderError, match="duplicate"):
        _run(read_v2_data_health_at_cutoff(
            conn, symbol="BTCUSDT", market_type="perp", exchanges=["binance"],
            metrics=["price"], cutoff_ts=B, calculation_version=H16))


def test_health_future_snapshot_from_broken_conn_rejected():
    conn = FakeConn([make_health_row(snapshot_ts=B + timedelta(minutes=1))])
    with pytest.raises(V2AlignmentReaderError, match="after cutoff_ts"):
        _run(read_v2_data_health_at_cutoff(
            conn, symbol="BTCUSDT", market_type="perp", exchanges=["binance"],
            metrics=["price"], cutoff_ts=B, calculation_version=H16))


def test_health_row_result_is_immutable():
    conn = BoundedLatestHealthConn([make_health_row()])
    result = _run(read_v2_data_health_at_cutoff(
        conn, symbol="BTCUSDT", market_type="perp", exchanges=["binance"],
        metrics=["price"], cutoff_ts=B, calculation_version=H16))
    assert isinstance(result, MappingProxyType)
    assert isinstance(result[("binance", "price")], MappingProxyType)


# ============================================================================
# 4. ARGUMENT VALIDATION
# ============================================================================
@pytest.mark.parametrize("field", ["symbol", "market_type", "timeframe"])
@pytest.mark.parametrize("bad", ["", "   ", None, 5])
def test_consensus_args_nonblank_strings(field, bad):
    kwargs = dict(symbol="BTCUSDT", market_type="perp", timeframe="5m",
                  bucket_ts=B, calculation_version=H16)
    kwargs[field] = bad
    with pytest.raises(V2AlignmentReaderError, match=field):
        validate_consensus_feature_args(**kwargs)


@pytest.mark.parametrize("bad_ts", [
    datetime(2026, 8, 15, 12, 0),                                        # naive
    datetime(2026, 8, 15, 12, 0, tzinfo=timezone(timedelta(hours=2))),   # non-UTC
    B.replace(second=1),
    B.replace(microsecond=1),
    "2026-08-15T12:00:00Z",
    None,
])
def test_consensus_args_bucket_ts_validation(bad_ts):
    with pytest.raises(V2AlignmentReaderError, match="bucket_ts"):
        validate_consensus_feature_args(
            symbol="BTCUSDT", market_type="perp", timeframe="5m",
            bucket_ts=bad_ts, calculation_version=H16)


@pytest.mark.parametrize("bad_cv", ["", "A" * 16, "g" * 16, "a" * 15, "a" * 17, None, 123])
def test_consensus_args_calculation_version_validation(bad_cv):
    with pytest.raises(V2AlignmentReaderError, match="calculation_version"):
        validate_consensus_feature_args(
            symbol="BTCUSDT", market_type="perp", timeframe="5m",
            bucket_ts=B, calculation_version=bad_cv)


def test_consensus_args_valid_passes():
    validate_consensus_feature_args(
        symbol="BTCUSDT", market_type="perp", timeframe="5m",
        bucket_ts=B, calculation_version=H16)  # no raise


@pytest.mark.parametrize("bad_seq", ["binance", b"binance", 5, None, [], ["binance", "binance"],
                                     ["binance", ""], ["binance", None]])
def test_health_args_exchanges_validation(bad_seq):
    with pytest.raises(V2AlignmentReaderError, match="exchanges"):
        validate_data_health_args(
            symbol="BTCUSDT", market_type="perp", exchanges=bad_seq,
            metrics=["price"], cutoff_ts=B, calculation_version=H16)


@pytest.mark.parametrize("bad_seq", ["price", 5, None, [], ["price", "price"]])
def test_health_args_metrics_validation(bad_seq):
    with pytest.raises(V2AlignmentReaderError, match="metrics"):
        validate_data_health_args(
            symbol="BTCUSDT", market_type="perp", exchanges=["binance"],
            metrics=bad_seq, cutoff_ts=B, calculation_version=H16)


def test_health_args_valid_passes():
    validate_data_health_args(
        symbol="BTCUSDT", market_type="perp", exchanges=["binance", "bybit"],
        metrics=["price"], cutoff_ts=B, calculation_version=H16)  # no raise


def test_health_args_preserve_caller_order():
    # order matters for the cross-product output shape
    conn = BoundedLatestHealthConn([])
    result = _run(read_v2_data_health_at_cutoff(
        conn, symbol="BTCUSDT", market_type="perp", exchanges=["bybit", "binance"],
        metrics=["oi", "price"], cutoff_ts=B, calculation_version=H16))
    assert list(result.keys()) == [
        ("bybit", "oi"), ("bybit", "price"), ("binance", "oi"), ("binance", "price")]


# ============================================================================
# 5. NEGATIVE SQL-SHAPE TESTS (§19)
# ============================================================================
def test_consensus_sql_uses_exact_bucket_ts_equality():
    sql = readers_module._CONSENSUS_FEATURE_SQL
    assert "bucket_ts = $4" in sql
    assert "bucket_ts <=" not in sql
    assert "ORDER BY bucket_ts DESC" not in sql
    assert "LIMIT 1" not in sql
    assert "calculation_version = $5" in sql


def test_percentiles_sql_uses_exact_bucket_ts_and_pinned_scope():
    sql = readers_module._CONSENSUS_PERCENTILES_SQL
    assert "bucket_ts = $4" in sql
    assert "bucket_ts <=" not in sql
    assert "scope = 'consensus'" in sql
    assert "exchange = ''" in sql
    assert "calculation_version = $5" in sql


def test_health_sql_uses_bounded_cutoff_never_wall_clock():
    sql = readers_module._DATA_HEALTH_AT_CUTOFF_SQL
    assert "snapshot_ts <= $6" in sql
    assert "now()" not in sql.lower()
    assert "current_timestamp" not in sql.lower()
    assert "DISTINCT ON (exchange, metric)" in sql
    assert "calculation_version = $3" in sql


@pytest.mark.parametrize("sql_const", [
    "_CONSENSUS_FEATURE_SQL", "_CONSENSUS_PERCENTILES_SQL", "_DATA_HEALTH_AT_CUTOFF_SQL"])
def test_no_writes_in_any_reader_sql(sql_const):
    sql = getattr(readers_module, sql_const).upper()
    for forbidden in ("INSERT", "UPDATE", "DELETE", "UPSERT", "ON CONFLICT", "TRUNCATE", "DROP"):
        assert forbidden not in sql


@pytest.mark.parametrize("sql_const", [
    "_CONSENSUS_FEATURE_SQL", "_CONSENSUS_PERCENTILES_SQL", "_DATA_HEALTH_AT_CUTOFF_SQL"])
def test_no_select_star(sql_const):
    sql = getattr(readers_module, sql_const).upper()
    assert "SELECT *" not in sql


# ============================================================================
# 6. PURITY / LAYERING
# ============================================================================
def _executable_body_source(module) -> str:
    """Source with every docstring stripped so a prose mention inside
    documentation cannot false-positive a forbidden-token scan."""
    import ast
    tree = ast.parse(inspect.getsource(module))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)):
                node.body = node.body[1:] or [ast.Pass()]
    return ast.unparse(tree)


def test_module_imports_nothing_from_runtime_main_notifications_analytics():
    import ast
    tree = ast.parse(inspect.getsource(readers_module))
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        for name in names:
            for banned in ("runtime", "main", "notifications", "analytics"):
                assert not name.startswith(banned), f"forbidden import: {name}"


def test_module_has_no_clock_random_uuid_network_config_access():
    body_src = _executable_body_source(readers_module)
    forbidden = (
        "datetime.now(", "datetime.utcnow(", "time.time(", "time.monotonic(",
        "import random", "import uuid", "import yaml", "os.environ", "os.getenv",
        "requests.", "httpx.", "open(",
    )
    for token in forbidden:
        assert token not in body_src, f"forbidden token found: {token!r}"


def test_functions_are_coroutines():
    assert inspect.iscoroutinefunction(read_v2_consensus_feature)
    assert inspect.iscoroutinefunction(read_v2_consensus_percentiles)
    assert inspect.iscoroutinefunction(read_v2_data_health_at_cutoff)


def test_validators_are_plain_sync_functions():
    assert not inspect.iscoroutinefunction(validate_consensus_feature_args)
    assert not inspect.iscoroutinefunction(validate_data_health_args)


# ============================================================================
# 7. Database WRAPPERS
# ============================================================================
def test_wrapper_consensus_feature_validates_before_acquire():
    db = _db()
    with pytest.raises(V2AlignmentReaderError):
        _run(db.fetch_v2_consensus_feature(
            symbol="", market_type="perp", timeframe="5m",
            bucket_ts=B, calculation_version=H16))
    assert db.pool.acquire_count == 0


def test_wrapper_consensus_feature_acquires_and_returns_none_on_empty():
    db = _db(FakeConn([]))
    result = _run(db.fetch_v2_consensus_feature(
        symbol="BTCUSDT", market_type="perp", timeframe="5m",
        bucket_ts=B, calculation_version=H16))
    assert result is None
    assert db.pool.acquire_count == 1


def test_wrapper_consensus_feature_delegates_correct_sql():
    conn = FakeConn([])
    db = _db(conn)
    _run(db.fetch_v2_consensus_feature(
        symbol="BTCUSDT", market_type="perp", timeframe="5m",
        bucket_ts=B, calculation_version=H16))
    assert conn.fetch_calls[0][0] == readers_module._CONSENSUS_FEATURE_SQL


def test_wrapper_consensus_percentiles_validates_before_acquire():
    db = _db()
    with pytest.raises(V2AlignmentReaderError):
        _run(db.fetch_v2_consensus_percentiles(
            symbol="BTCUSDT", market_type="perp", timeframe="",
            bucket_ts=B, calculation_version=H16))
    assert db.pool.acquire_count == 0


def test_wrapper_consensus_percentiles_returns_detached_tuple():
    conn = FakeConn([make_percentile_row()])
    db = _db(conn)
    result = _run(db.fetch_v2_consensus_percentiles(
        symbol="BTCUSDT", market_type="perp", timeframe="5m",
        bucket_ts=B, calculation_version=H16))
    assert isinstance(result, tuple) and len(result) == 1
    assert db.pool.acquire_count == 1


def test_wrapper_health_validates_before_acquire():
    db = _db()
    with pytest.raises(V2AlignmentReaderError):
        _run(db.fetch_v2_data_health_at_cutoff(
            symbol="BTCUSDT", market_type="perp", exchanges=[], metrics=["price"],
            cutoff_ts=B, calculation_version=H16))
    assert db.pool.acquire_count == 0


def test_wrapper_health_empty_exchanges_fails_closed_no_query_issued():
    db = _db(FakeConn([]))
    with pytest.raises(V2AlignmentReaderError):
        _run(db.fetch_v2_data_health_at_cutoff(
            symbol="BTCUSDT", market_type="perp", exchanges=[], metrics=["price"],
            cutoff_ts=B, calculation_version=H16))
    assert db.pool.acquire_count == 0
    assert db.pool.conn.fetch_calls == []


def test_wrapper_health_returns_explicit_missing_mapping():
    conn = FakeConn([])
    db = _db(conn)
    result = _run(db.fetch_v2_data_health_at_cutoff(
        symbol="BTCUSDT", market_type="perp", exchanges=["binance"], metrics=["price"],
        cutoff_ts=B, calculation_version=H16))
    assert result[("binance", "price")] is None
    assert db.pool.acquire_count == 1


def test_wrapper_no_pool_raises_assertion_after_validation():
    db = Database("postgresql://unused")  # pool is None
    with pytest.raises(AssertionError):
        _run(db.fetch_v2_consensus_feature(
            symbol="BTCUSDT", market_type="perp", timeframe="5m",
            bucket_ts=B, calculation_version=H16))


# ============================================================================
# 8. DIRECT READERS SELF-VALIDATE (fail-closed even without the Database
# wrapper) — a direct caller must never be able to issue a malformed query.
# ============================================================================
def test_direct_consensus_feature_reader_rejects_malformed_symbol_zero_fetches():
    conn = FakeConn([])
    with pytest.raises(V2AlignmentReaderError, match="symbol"):
        _run(read_v2_consensus_feature(
            conn, symbol="", market_type="perp", timeframe="5m",
            bucket_ts=B, calculation_version=H16))
    assert conn.fetch_calls == []


def test_direct_consensus_percentiles_reader_rejects_malformed_timeframe_zero_fetches():
    conn = FakeConn([])
    with pytest.raises(V2AlignmentReaderError, match="timeframe"):
        _run(read_v2_consensus_percentiles(
            conn, symbol="BTCUSDT", market_type="perp", timeframe="",
            bucket_ts=B, calculation_version=H16))
    assert conn.fetch_calls == []


def test_direct_consensus_percentiles_reader_rejects_malformed_bucket_ts_zero_fetches():
    conn = FakeConn([])
    naive = datetime(2026, 8, 15, 12, 0)  # no tzinfo
    with pytest.raises(V2AlignmentReaderError, match="bucket_ts"):
        _run(read_v2_consensus_percentiles(
            conn, symbol="BTCUSDT", market_type="perp", timeframe="5m",
            bucket_ts=naive, calculation_version=H16))
    assert conn.fetch_calls == []


def test_direct_health_reader_rejects_empty_exchanges_zero_fetches():
    conn = FakeConn([])
    with pytest.raises(V2AlignmentReaderError, match="exchanges"):
        _run(read_v2_data_health_at_cutoff(
            conn, symbol="BTCUSDT", market_type="perp", exchanges=[],
            metrics=["price"], cutoff_ts=B, calculation_version=H16))
    assert conn.fetch_calls == []


def test_direct_health_reader_rejects_empty_metrics_zero_fetches():
    conn = FakeConn([])
    with pytest.raises(V2AlignmentReaderError, match="metrics"):
        _run(read_v2_data_health_at_cutoff(
            conn, symbol="BTCUSDT", market_type="perp", exchanges=["binance"],
            metrics=[], cutoff_ts=B, calculation_version=H16))
    assert conn.fetch_calls == []


def test_direct_health_reader_rejects_str_as_exchanges_zero_fetches():
    conn = FakeConn([])
    with pytest.raises(V2AlignmentReaderError, match="exchanges"):
        _run(read_v2_data_health_at_cutoff(
            conn, symbol="BTCUSDT", market_type="perp", exchanges="binance",
            metrics=["price"], cutoff_ts=B, calculation_version=H16))
    assert conn.fetch_calls == []


def test_direct_health_reader_rejects_duplicate_exchanges_zero_fetches():
    conn = FakeConn([])
    with pytest.raises(V2AlignmentReaderError, match="exchanges"):
        _run(read_v2_data_health_at_cutoff(
            conn, symbol="BTCUSDT", market_type="perp",
            exchanges=["binance", "binance"], metrics=["price"],
            cutoff_ts=B, calculation_version=H16))
    assert conn.fetch_calls == []


def test_direct_health_reader_rejects_blank_metric_zero_fetches():
    conn = FakeConn([])
    with pytest.raises(V2AlignmentReaderError, match="metrics"):
        _run(read_v2_data_health_at_cutoff(
            conn, symbol="BTCUSDT", market_type="perp", exchanges=["binance"],
            metrics=["price", "   "], cutoff_ts=B, calculation_version=H16))
    assert conn.fetch_calls == []


def test_direct_readers_still_succeed_on_valid_args_after_self_validation():
    # Self-validation must not become double work that breaks the happy path.
    conn = ExactMatchConsensusConn([make_consensus_row()])
    result = _run(read_v2_consensus_feature(
        conn, symbol="BTCUSDT", market_type="perp", timeframe="5m",
        bucket_ts=B, calculation_version=H16))
    assert result is not None
    assert len(conn.fetch_calls) == 1


def test_validate_data_health_args_returns_detached_tuples_preserving_order():
    from storage.v2_alignment_readers import validate_data_health_args
    exchanges = ["bybit", "binance"]
    metrics = ["oi", "price"]
    result_exchanges, result_metrics = validate_data_health_args(
        symbol="BTCUSDT", market_type="perp", exchanges=exchanges, metrics=metrics,
        cutoff_ts=B, calculation_version=H16)
    assert result_exchanges == ("bybit", "binance")
    assert result_metrics == ("oi", "price")
    assert isinstance(result_exchanges, tuple) and isinstance(result_metrics, tuple)
    # mutating the caller's original lists afterward must not affect the
    # already-returned detached tuples.
    exchanges.append("okx")
    metrics.append("funding")
    assert result_exchanges == ("bybit", "binance")
    assert result_metrics == ("oi", "price")


# ============================================================================
# 9. TOCTOU: Database health wrapper must not use caller-owned mutable
# sequences after its own pre-acquire validation.
# ============================================================================
class _MutatingAcquire:
    """Simulates a caller mutating its own exchanges/metrics lists during
    the window between Database-wrapper validation and the connection
    actually being acquired/used — deterministic, no sleep/timing involved."""
    def __init__(self, pool, exchanges_list, metrics_list):
        self.pool = pool
        self.exchanges_list = exchanges_list
        self.metrics_list = metrics_list

    async def __aenter__(self):
        self.pool.acquire_count += 1
        self.exchanges_list[:] = ["okx"]
        self.metrics_list[:] = ["funding"]
        return self.pool.conn

    async def __aexit__(self, *exc):
        return False


class _MutatingPool:
    def __init__(self, conn, exchanges_list, metrics_list):
        self.conn = conn
        self.exchanges_list = exchanges_list
        self.metrics_list = metrics_list
        self.acquire_count = 0

    def acquire(self):
        return _MutatingAcquire(self, self.exchanges_list, self.metrics_list)


def test_wrapper_health_query_unaffected_by_post_validation_list_mutation():
    exchanges = ["binance"]
    metrics = ["ohlcv"]
    conn = FakeConn([])
    db = Database("postgresql://unused")
    db.pool = _MutatingPool(conn, exchanges, metrics)

    _run(db.fetch_v2_data_health_at_cutoff(
        symbol="BTCUSDT", market_type="perp", exchanges=exchanges, metrics=metrics,
        cutoff_ts=B, calculation_version=H16))

    # the original caller lists WERE mutated during acquire (proving the
    # test setup is real), but the actual query must reflect only the
    # PRE-mutation validated values.
    assert exchanges == ["okx"]
    assert metrics == ["funding"]
    sql, args = conn.fetch_calls[0]
    assert args[3] == ["binance"]
    assert args[4] == ["ohlcv"]


# ============================================================================
# 10. REFERENCE FEATURE / REFERENCE KLINES — row factories + behavior-
# simulating fake connections (PR 3: the two new canonical-reference-
# exchange read primitives)
# ============================================================================
def make_reference_feature_row(**over):
    base = dict(
        exchange="binance", symbol="BTCUSDT", market_type="perp", timeframe="15m",
        bucket_ts=B, feature_schema_version=1, calculation_version=H16,
        price_move_pct=0.1, range_width_pct=1.0, close_price=65000.0,
        volume_raw=100.0, volume_raw_unit="base", volume_notional_usd=1000.0,
        taker_buy_notional_usd=600.0, taker_sell_notional_usd=400.0,
        taker_delta_notional_usd=200.0, cvd_delta_notional_usd=200.0,
        oi_change_pct=0.02, oi_unit="usd", funding_rate=0.0001,
        long_liquidation_notional=None, short_liquidation_notional=None,
        liquidation_event_count=None, liquidation_feed_quality=None, is_snapshot_feed=False,
        bars_expected=15, bars_present=15, has_gap=False, is_usable=True,
        computed_at=B, config_hash=H64, config_version="2.1.0", code_version="deadbeef",
    )
    base.update(over)
    return base


def make_kline_row(**over):
    base = dict(exchange="binance", symbol="BTCUSDT", ts=B,
                open=64900.0, high=65100.0, low=64800.0, close=65000.0)
    base.update(over)
    return base


class ExactMatchReferenceFeatureConn:
    """Simulates exchange_feature_vectors' exact-identity WHERE clause."""
    def __init__(self, rows):
        self.rows = rows
        self.fetch_calls = []

    async def fetch(self, sql, exchange, symbol, market_type, timeframe, bucket_ts,
                    calculation_version):
        self.fetch_calls.append(
            (sql, (exchange, symbol, market_type, timeframe, bucket_ts, calculation_version)))
        return [r for r in self.rows if (
            r["exchange"], r["symbol"], r["market_type"], r["timeframe"], r["bucket_ts"],
            r["calculation_version"]
        ) == (exchange, symbol, market_type, timeframe, bucket_ts, calculation_version)]


class HalfOpenKlinesConn:
    """Simulates klines_1m's half-open [bucket_start, bucket_end) WHERE
    clause, returning rows ordered by ts ASC."""
    def __init__(self, rows):
        self.rows = rows
        self.fetch_calls = []

    async def fetch(self, sql, exchange, symbol, bucket_start, bucket_end):
        self.fetch_calls.append((sql, (exchange, symbol, bucket_start, bucket_end)))
        matched = [r for r in self.rows if (
            r["exchange"] == exchange and r["symbol"] == symbol
            and bucket_start <= r["ts"] < bucket_end)]
        return sorted(matched, key=lambda r: r["ts"])


# ============================================================================
# 11. REFERENCE FEATURE
# ============================================================================
def test_reference_feature_exact_identity_hit():
    conn = ExactMatchReferenceFeatureConn([make_reference_feature_row()])
    result = _run(read_v2_reference_feature(
        conn, exchange="binance", symbol="BTCUSDT", market_type="perp", timeframe="15m",
        bucket_ts=B, calculation_version=H16))
    assert result is not None
    assert result["exchange"] == "binance" and result["bucket_ts"] == B
    assert isinstance(result, MappingProxyType)


def test_reference_feature_missing_returns_none():
    conn = ExactMatchReferenceFeatureConn([])
    result = _run(read_v2_reference_feature(
        conn, exchange="binance", symbol="BTCUSDT", market_type="perp", timeframe="15m",
        bucket_ts=B, calculation_version=H16))
    assert result is None


def test_reference_feature_older_bucket_no_fallback():
    older = make_reference_feature_row(bucket_ts=B - timedelta(minutes=15))
    conn = ExactMatchReferenceFeatureConn([older])
    result = _run(read_v2_reference_feature(
        conn, exchange="binance", symbol="BTCUSDT", market_type="perp", timeframe="15m",
        bucket_ts=B, calculation_version=H16))
    assert result is None


def test_reference_feature_wrong_exchange_no_fallback():
    # a bybit row exists at the exact bucket, but "binance" was requested —
    # storage stays generic; the analytics layer pins the canonical
    # exchange, but this reader itself must never substitute exchanges.
    other = make_reference_feature_row(exchange="bybit")
    conn = ExactMatchReferenceFeatureConn([other])
    result = _run(read_v2_reference_feature(
        conn, exchange="binance", symbol="BTCUSDT", market_type="perp", timeframe="15m",
        bucket_ts=B, calculation_version=H16))
    assert result is None


def test_reference_feature_wrong_calculation_version_excluded():
    row = make_reference_feature_row(calculation_version="c" * 16)
    conn = ExactMatchReferenceFeatureConn([row])
    result = _run(read_v2_reference_feature(
        conn, exchange="binance", symbol="BTCUSDT", market_type="perp", timeframe="15m",
        bucket_ts=B, calculation_version=H16))
    assert result is None


def test_reference_feature_more_than_one_row_fails_loudly():
    conn = FakeConn([make_reference_feature_row(), make_reference_feature_row()])
    with pytest.raises(V2AlignmentReaderError, match="expected at most one"):
        _run(read_v2_reference_feature(
            conn, exchange="binance", symbol="BTCUSDT", market_type="perp", timeframe="15m",
            bucket_ts=B, calculation_version=H16))


def test_reference_feature_row_identity_mismatch_rejected():
    conn = FakeConn([make_reference_feature_row(timeframe="1h")])
    with pytest.raises(V2AlignmentReaderError, match="does not match"):
        _run(read_v2_reference_feature(
            conn, exchange="binance", symbol="BTCUSDT", market_type="perp", timeframe="15m",
            bucket_ts=B, calculation_version=H16))


def test_reference_feature_result_is_immutable():
    conn = ExactMatchReferenceFeatureConn([make_reference_feature_row()])
    result = _run(read_v2_reference_feature(
        conn, exchange="binance", symbol="BTCUSDT", market_type="perp", timeframe="15m",
        bucket_ts=B, calculation_version=H16))
    assert isinstance(result, MappingProxyType)
    with pytest.raises(TypeError):
        result["close_price"] = 0.0


# ============================================================================
# 12. REFERENCE KLINES — half-open interval, no market_type/calculation_version
# ============================================================================
BUCKET_START = B
BUCKET_END = B + timedelta(minutes=15)


def test_reference_klines_half_open_interval_start_included_end_excluded():
    rows = [
        make_kline_row(ts=BUCKET_START),                          # included: == start
        make_kline_row(ts=BUCKET_START + timedelta(minutes=5)),   # included: inside
        make_kline_row(ts=BUCKET_END - timedelta(minutes=1)),     # included: last minute
        make_kline_row(ts=BUCKET_END),                            # excluded: == end
        make_kline_row(ts=BUCKET_END + timedelta(minutes=5)),     # excluded: after end
        make_kline_row(ts=BUCKET_START - timedelta(minutes=1)),   # excluded: before start
    ]
    conn = HalfOpenKlinesConn(rows)
    result = _run(read_v2_reference_klines(
        conn, exchange="binance", symbol="BTCUSDT",
        bucket_start=BUCKET_START, bucket_end=BUCKET_END))
    assert [r["ts"] for r in result] == [
        BUCKET_START, BUCKET_START + timedelta(minutes=5), BUCKET_END - timedelta(minutes=1)]


def test_reference_klines_empty_result_is_empty_tuple():
    conn = HalfOpenKlinesConn([])
    result = _run(read_v2_reference_klines(
        conn, exchange="binance", symbol="BTCUSDT",
        bucket_start=BUCKET_START, bucket_end=BUCKET_END))
    assert result == ()
    assert isinstance(result, tuple)


def test_reference_klines_wrong_exchange_or_symbol_rejected():
    conn = FakeConn([make_kline_row(exchange="bybit")])
    with pytest.raises(V2AlignmentReaderError, match="does not match"):
        _run(read_v2_reference_klines(
            conn, exchange="binance", symbol="BTCUSDT",
            bucket_start=BUCKET_START, bucket_end=BUCKET_END))


def test_reference_klines_ts_at_bucket_end_rejected():
    conn = FakeConn([make_kline_row(ts=BUCKET_END)])
    with pytest.raises(V2AlignmentReaderError, match="outside the requested half-open"):
        _run(read_v2_reference_klines(
            conn, exchange="binance", symbol="BTCUSDT",
            bucket_start=BUCKET_START, bucket_end=BUCKET_END))


def test_reference_klines_ts_after_bucket_end_rejected():
    conn = FakeConn([make_kline_row(ts=BUCKET_END + timedelta(minutes=1))])
    with pytest.raises(V2AlignmentReaderError, match="outside the requested half-open"):
        _run(read_v2_reference_klines(
            conn, exchange="binance", symbol="BTCUSDT",
            bucket_start=BUCKET_START, bucket_end=BUCKET_END))


def test_reference_klines_ts_before_bucket_start_rejected():
    conn = FakeConn([make_kline_row(ts=BUCKET_START - timedelta(minutes=1))])
    with pytest.raises(V2AlignmentReaderError, match="outside the requested half-open"):
        _run(read_v2_reference_klines(
            conn, exchange="binance", symbol="BTCUSDT",
            bucket_start=BUCKET_START, bucket_end=BUCKET_END))


def test_reference_klines_duplicate_ts_rejected():
    conn = FakeConn([make_kline_row(ts=BUCKET_START), make_kline_row(ts=BUCKET_START)])
    with pytest.raises(V2AlignmentReaderError, match="duplicate"):
        _run(read_v2_reference_klines(
            conn, exchange="binance", symbol="BTCUSDT",
            bucket_start=BUCKET_START, bucket_end=BUCKET_END))


def test_reference_klines_non_ascending_ts_from_broken_conn_rejected():
    conn = FakeConn([
        make_kline_row(ts=BUCKET_START + timedelta(minutes=2)),
        make_kline_row(ts=BUCKET_START + timedelta(minutes=1)),
    ])
    with pytest.raises(V2AlignmentReaderError, match="non-descending"):
        _run(read_v2_reference_klines(
            conn, exchange="binance", symbol="BTCUSDT",
            bucket_start=BUCKET_START, bucket_end=BUCKET_END))


def test_reference_klines_rows_are_immutable():
    conn = HalfOpenKlinesConn([make_kline_row(ts=BUCKET_START)])
    result = _run(read_v2_reference_klines(
        conn, exchange="binance", symbol="BTCUSDT",
        bucket_start=BUCKET_START, bucket_end=BUCKET_END))
    assert isinstance(result[0], MappingProxyType)
    with pytest.raises(TypeError):
        result[0]["close"] = 0.0


def test_reference_klines_full_15m_bucket_returns_exactly_15_ascending_bars():
    rows = [make_kline_row(ts=BUCKET_START + timedelta(minutes=i)) for i in range(15)]
    conn = HalfOpenKlinesConn(rows)
    result = _run(read_v2_reference_klines(
        conn, exchange="binance", symbol="BTCUSDT",
        bucket_start=BUCKET_START, bucket_end=BUCKET_END))
    assert len(result) == 15
    assert [r["ts"] for r in result] == [BUCKET_START + timedelta(minutes=i) for i in range(15)]


# ============================================================================
# 13. ARGUMENT VALIDATION — reference feature / reference klines
# ============================================================================
@pytest.mark.parametrize("field", ["exchange", "symbol", "market_type", "timeframe"])
@pytest.mark.parametrize("bad", ["", "   ", None, 5])
def test_reference_feature_args_nonblank_strings(field, bad):
    kwargs = dict(exchange="binance", symbol="BTCUSDT", market_type="perp", timeframe="15m",
                  bucket_ts=B, calculation_version=H16)
    kwargs[field] = bad
    with pytest.raises(V2AlignmentReaderError, match=field):
        validate_reference_feature_args(**kwargs)


def test_reference_feature_args_valid_passes():
    validate_reference_feature_args(
        exchange="binance", symbol="BTCUSDT", market_type="perp", timeframe="15m",
        bucket_ts=B, calculation_version=H16)  # no raise


@pytest.mark.parametrize("field", ["exchange", "symbol"])
@pytest.mark.parametrize("bad", ["", "   ", None, 5])
def test_reference_klines_args_nonblank_strings(field, bad):
    kwargs = dict(exchange="binance", symbol="BTCUSDT",
                  bucket_start=BUCKET_START, bucket_end=BUCKET_END)
    kwargs[field] = bad
    with pytest.raises(V2AlignmentReaderError, match=field):
        validate_reference_klines_args(**kwargs)


def test_reference_klines_args_bucket_start_not_before_end_rejected():
    with pytest.raises(V2AlignmentReaderError, match="bucket_start"):
        validate_reference_klines_args(
            exchange="binance", symbol="BTCUSDT",
            bucket_start=BUCKET_END, bucket_end=BUCKET_START)


def test_reference_klines_args_equal_bounds_rejected():
    with pytest.raises(V2AlignmentReaderError, match="bucket_start"):
        validate_reference_klines_args(
            exchange="binance", symbol="BTCUSDT",
            bucket_start=B, bucket_end=B)


def test_reference_klines_args_valid_passes():
    validate_reference_klines_args(
        exchange="binance", symbol="BTCUSDT",
        bucket_start=BUCKET_START, bucket_end=BUCKET_END)  # no raise


# ============================================================================
# 14. NEGATIVE SQL-SHAPE TESTS — reference feature / reference klines
# ============================================================================
def test_reference_feature_sql_uses_exact_bucket_ts_equality():
    sql = readers_module._REFERENCE_FEATURE_SQL
    assert "bucket_ts = $5" in sql
    assert "bucket_ts <=" not in sql
    assert "ORDER BY bucket_ts DESC" not in sql
    assert "LIMIT 1" not in sql
    assert "calculation_version = $6" in sql
    assert "exchange = $1" in sql


def test_reference_klines_sql_is_half_open_no_market_type_no_calculation_version():
    sql = readers_module._REFERENCE_KLINES_SQL
    assert "ts >= $3" in sql
    assert "ts < $4" in sql
    assert "ts <= " not in sql
    assert "market_type" not in sql
    assert "calculation_version" not in sql
    assert "ORDER BY ts ASC" in sql


@pytest.mark.parametrize("sql_const", ["_REFERENCE_FEATURE_SQL", "_REFERENCE_KLINES_SQL"])
def test_no_writes_in_reference_sql(sql_const):
    sql = getattr(readers_module, sql_const).upper()
    for forbidden in ("INSERT", "UPDATE", "DELETE", "UPSERT", "ON CONFLICT", "TRUNCATE", "DROP"):
        assert forbidden not in sql


@pytest.mark.parametrize("sql_const", ["_REFERENCE_FEATURE_SQL", "_REFERENCE_KLINES_SQL"])
def test_no_select_star_reference_sql(sql_const):
    sql = getattr(readers_module, sql_const).upper()
    assert "SELECT *" not in sql


def test_reference_feature_and_klines_functions_are_coroutines():
    assert inspect.iscoroutinefunction(read_v2_reference_feature)
    assert inspect.iscoroutinefunction(read_v2_reference_klines)


def test_reference_validators_are_plain_sync_functions():
    assert not inspect.iscoroutinefunction(validate_reference_feature_args)
    assert not inspect.iscoroutinefunction(validate_reference_klines_args)


# ============================================================================
# 15. Database WRAPPERS — reference feature / reference klines
# ============================================================================
def test_wrapper_reference_feature_validates_before_acquire():
    db = _db()
    with pytest.raises(V2AlignmentReaderError):
        _run(db.fetch_v2_reference_feature(
            exchange="", symbol="BTCUSDT", market_type="perp", timeframe="15m",
            bucket_ts=B, calculation_version=H16))
    assert db.pool.acquire_count == 0


def test_wrapper_reference_feature_acquires_and_returns_none_on_empty():
    db = _db(FakeConn([]))
    result = _run(db.fetch_v2_reference_feature(
        exchange="binance", symbol="BTCUSDT", market_type="perp", timeframe="15m",
        bucket_ts=B, calculation_version=H16))
    assert result is None
    assert db.pool.acquire_count == 1


def test_wrapper_reference_feature_delegates_correct_sql():
    conn = FakeConn([])
    db = _db(conn)
    _run(db.fetch_v2_reference_feature(
        exchange="binance", symbol="BTCUSDT", market_type="perp", timeframe="15m",
        bucket_ts=B, calculation_version=H16))
    assert conn.fetch_calls[0][0] == readers_module._REFERENCE_FEATURE_SQL


def test_wrapper_reference_klines_validates_before_acquire():
    db = _db()
    with pytest.raises(V2AlignmentReaderError):
        _run(db.fetch_v2_reference_klines(
            exchange="binance", symbol="BTCUSDT",
            bucket_start=BUCKET_END, bucket_end=BUCKET_START))  # inverted
    assert db.pool.acquire_count == 0


def test_wrapper_reference_klines_acquires_and_returns_detached_tuple():
    conn = FakeConn([make_kline_row(ts=BUCKET_START)])
    db = _db(conn)
    result = _run(db.fetch_v2_reference_klines(
        exchange="binance", symbol="BTCUSDT",
        bucket_start=BUCKET_START, bucket_end=BUCKET_END))
    assert isinstance(result, tuple) and len(result) == 1
    assert db.pool.acquire_count == 1


def test_wrapper_reference_klines_delegates_correct_sql():
    conn = FakeConn([])
    db = _db(conn)
    _run(db.fetch_v2_reference_klines(
        exchange="binance", symbol="BTCUSDT",
        bucket_start=BUCKET_START, bucket_end=BUCKET_END))
    assert conn.fetch_calls[0][0] == readers_module._REFERENCE_KLINES_SQL


def test_wrapper_reference_feature_no_pool_raises_assertion_after_validation():
    db = Database("postgresql://unused")  # pool is None
    with pytest.raises(AssertionError):
        _run(db.fetch_v2_reference_feature(
            exchange="binance", symbol="BTCUSDT", market_type="perp", timeframe="15m",
            bucket_ts=B, calculation_version=H16))


def test_wrapper_reference_klines_no_pool_raises_assertion_after_validation():
    db = Database("postgresql://unused")  # pool is None
    with pytest.raises(AssertionError):
        _run(db.fetch_v2_reference_klines(
            exchange="binance", symbol="BTCUSDT",
            bucket_start=BUCKET_START, bucket_end=BUCKET_END))


# ============================================================================
# 16. DIRECT READERS SELF-VALIDATE — reference feature / reference klines
# ============================================================================
def test_direct_reference_feature_reader_rejects_malformed_exchange_zero_fetches():
    conn = FakeConn([])
    with pytest.raises(V2AlignmentReaderError, match="exchange"):
        _run(read_v2_reference_feature(
            conn, exchange="", symbol="BTCUSDT", market_type="perp", timeframe="15m",
            bucket_ts=B, calculation_version=H16))
    assert conn.fetch_calls == []


def test_direct_reference_klines_reader_rejects_malformed_symbol_zero_fetches():
    conn = FakeConn([])
    with pytest.raises(V2AlignmentReaderError, match="symbol"):
        _run(read_v2_reference_klines(
            conn, exchange="binance", symbol="",
            bucket_start=BUCKET_START, bucket_end=BUCKET_END))
    assert conn.fetch_calls == []


def test_direct_reference_klines_reader_rejects_inverted_bounds_zero_fetches():
    conn = FakeConn([])
    with pytest.raises(V2AlignmentReaderError, match="bucket_start"):
        _run(read_v2_reference_klines(
            conn, exchange="binance", symbol="BTCUSDT",
            bucket_start=BUCKET_END, bucket_end=BUCKET_START))
    assert conn.fetch_calls == []


def test_direct_readers_still_succeed_on_valid_reference_args_after_self_validation():
    conn = ExactMatchReferenceFeatureConn([make_reference_feature_row()])
    result = _run(read_v2_reference_feature(
        conn, exchange="binance", symbol="BTCUSDT", market_type="perp", timeframe="15m",
        bucket_ts=B, calculation_version=H16))
    assert result is not None
    assert len(conn.fetch_calls) == 1
