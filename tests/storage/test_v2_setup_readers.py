"""Tests for storage/v2_setup_readers.py (Stage 5 — Setup Detectors PR 1)
and its storage.db.Database wrappers. No real DB — fake asyncpg-like
connections/pools only, following the existing storage test style
(tests/storage/test_v2_alignment_readers.py).

Exercises the four read primitives' central contract: INCLUSIVE
bucket-START `[bucket_start, bucket_end]` interval semantics (deliberately
different from Stage 3's half-open kline convention), explicit identity
(symbol/market_type/timeframe/metric/percentile_window/exchange/
calculation_version) at both the SQL and post-fetch validation layers,
no-lookahead preservation for percentile rows, missing historical rows
preserved as absence (never fabricated), fail-closed argument validation
before any connection is acquired, and negative SQL-shape checks proving
no forbidden "latest now"/wall-clock/write semantics.
"""
from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone

import pytest

from storage.db import Database
from storage.v2_setup_readers import (
    V2SetupReaderError,
    read_v2_consensus_feature_window, read_v2_consensus_percentile_window,
    read_v2_reference_feature_window, read_v2_instrument,
    validate_consensus_feature_window_args, validate_consensus_percentile_window_args,
    validate_reference_feature_window_args, validate_instrument_args,
)
from storage import v2_setup_readers as readers_module

UTC = timezone.utc
B = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
H16 = "a" * 16
H64 = "b" * 64


# ============================================================================
# fake asyncpg pool (Database wrapper tests) — mirrors
# tests/storage/test_v2_alignment_readers.py's own fakes
# ============================================================================
class FakeConn:
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
# row fixtures
# ============================================================================
def make_consensus_row(bucket_ts=B, **over):
    base = dict(
        symbol="BTCUSDT", market_type="perp", timeframe="15m", bucket_ts=bucket_ts,
        feature_schema_version=1, calculation_version=H16,
        coverage_by_metric="{}", provenance_by_metric="{}", data_confidence_by_metric="{}",
        exchanges_expected_max=3, min_coverage_ratio=1.0, data_confidence_overall=90.0,
        price_direction_agreement=1.0, flow_direction_agreement=1.0, oi_direction_agreement=1.0,
        price_move_pct_median=1.0, range_width_pct_median=1.0, oi_change_pct_median=0.1,
        funding_rate_median=0.0001, funding_rate_mad=0.0,
        volume_notional_usd_sum=1.0, taker_buy_notional_usd_sum=1.0,
        taker_sell_notional_usd_sum=1.0, taker_delta_notional_usd_sum=0.0,
        cvd_delta_notional_usd_sum=0.0,
        observed_long_liquidation_notional_sum=0.0, observed_short_liquidation_notional_sum=0.0,
        observed_liquidation_event_count_sum=0, liquidation_feed_quality_by_exchange="{}",
        price_move_pct_mad=0.0, oi_change_pct_mad=0.0, outlier_exchanges="[]",
        consensus_confidence=90.0, is_partial_consensus=False,
        computed_at=B, config_hash=H64, config_version=1, code_version="v1",
    )
    base.update(over)
    return base


def make_percentile_row(bucket_ts=B, sample_window_end=None, **over):
    base = dict(
        scope="consensus", exchange="", symbol="BTCUSDT", market_type="perp",
        metric="range_width_pct_median", timeframe="15m", percentile_window="30d",
        bucket_ts=bucket_ts, value=1.0, percentile_rank=0.5, sample_size=100,
        sample_window_start=bucket_ts - timedelta(days=30),
        sample_window_end=(sample_window_end if sample_window_end is not None
                          else bucket_ts - timedelta(minutes=5)),
        confidence_tier="mature", computed_at=B, config_hash=H64, config_version=1,
        code_version="v1", feature_schema_version=1, calculation_version=H16,
    )
    base.update(over)
    return base


def make_reference_row(bucket_ts=B, **over):
    base = dict(
        exchange="binance", symbol="BTCUSDT", market_type="perp", timeframe="15m",
        bucket_ts=bucket_ts, feature_schema_version=1, calculation_version=H16,
        price_move_pct=1.0, range_width_pct=1.0, close_price=65000.0,
        volume_raw=1.0, volume_raw_unit="base", volume_notional_usd=1.0,
        taker_buy_notional_usd=1.0, taker_sell_notional_usd=1.0, taker_delta_notional_usd=0.0,
        cvd_delta_notional_usd=0.0, oi_change_pct=0.1, oi_unit="usd", funding_rate=0.0001,
        long_liquidation_notional=0.0, short_liquidation_notional=0.0, liquidation_event_count=0,
        liquidation_feed_quality="full", is_snapshot_feed=False,
        bars_expected=15, bars_present=15, has_gap=False, is_usable=True,
        computed_at=B, config_hash=H64, config_version=1, code_version="v1",
    )
    base.update(over)
    return base


def make_instrument_row(**over):
    base = dict(
        exchange="binance", symbol="BTCUSDT", market_type="perp",
        exchange_instrument_id="BTCUSDT", quantity_unit="base", contract_multiplier=1.0,
        tick_size=0.1, price_precision=1, quantity_precision=3, metadata_source="exchange_api",
        fetched_at=B, is_stale=False, note=None, updated_at=B,
    )
    base.update(over)
    return base


# ============================================================================
# 1. read_v2_consensus_feature_window
# ============================================================================
def test_consensus_window_inclusive_both_ends():
    start = B - timedelta(minutes=15 * 13)
    rows = [make_consensus_row(bucket_ts=start + timedelta(minutes=15 * i)) for i in range(14)]
    conn = FakeConn(rows)
    result = _run(read_v2_consensus_feature_window(
        conn, symbol="BTCUSDT", market_type="perp", timeframe="15m",
        bucket_start=start, bucket_end=B, calculation_version=H16))
    assert len(result) == 14
    assert result[0]["bucket_ts"] == start
    assert result[-1]["bucket_ts"] == B


def test_consensus_window_missing_rows_preserved_as_absence():
    start = B - timedelta(minutes=15 * 13)
    rows = [make_consensus_row(bucket_ts=start + timedelta(minutes=15 * i)) for i in range(13)]
    conn = FakeConn(rows)
    result = _run(read_v2_consensus_feature_window(
        conn, symbol="BTCUSDT", market_type="perp", timeframe="15m",
        bucket_start=start, bucket_end=B, calculation_version=H16))
    assert len(result) == 13  # never fabricated up to 14


def test_consensus_window_empty_result_is_empty_tuple():
    conn = FakeConn([])
    result = _run(read_v2_consensus_feature_window(
        conn, symbol="BTCUSDT", market_type="perp", timeframe="15m",
        bucket_start=B, bucket_end=B, calculation_version=H16))
    assert result == ()


def test_consensus_window_wrong_identity_rejected():
    conn = FakeConn([make_consensus_row(symbol="ETHUSDT")])
    with pytest.raises(V2SetupReaderError):
        _run(read_v2_consensus_feature_window(
            conn, symbol="BTCUSDT", market_type="perp", timeframe="15m",
            bucket_start=B, bucket_end=B, calculation_version=H16))


def test_consensus_window_wrong_calculation_version_rejected():
    conn = FakeConn([make_consensus_row(calculation_version="c" * 16)])
    with pytest.raises(V2SetupReaderError):
        _run(read_v2_consensus_feature_window(
            conn, symbol="BTCUSDT", market_type="perp", timeframe="15m",
            bucket_start=B, bucket_end=B, calculation_version=H16))


def test_consensus_window_bucket_before_start_rejected():
    conn = FakeConn([make_consensus_row(bucket_ts=B - timedelta(minutes=15))])
    with pytest.raises(V2SetupReaderError):
        _run(read_v2_consensus_feature_window(
            conn, symbol="BTCUSDT", market_type="perp", timeframe="15m",
            bucket_start=B, bucket_end=B, calculation_version=H16))


def test_consensus_window_bucket_after_end_rejected():
    conn = FakeConn([make_consensus_row(bucket_ts=B + timedelta(minutes=15))])
    with pytest.raises(V2SetupReaderError):
        _run(read_v2_consensus_feature_window(
            conn, symbol="BTCUSDT", market_type="perp", timeframe="15m",
            bucket_start=B, bucket_end=B, calculation_version=H16))


def test_consensus_window_duplicate_bucket_rejected():
    conn = FakeConn([make_consensus_row(), make_consensus_row()])
    with pytest.raises(V2SetupReaderError):
        _run(read_v2_consensus_feature_window(
            conn, symbol="BTCUSDT", market_type="perp", timeframe="15m",
            bucket_start=B, bucket_end=B, calculation_version=H16))


def test_consensus_window_non_ascending_rejected():
    conn = FakeConn([make_consensus_row(bucket_ts=B), make_consensus_row(bucket_ts=B - timedelta(minutes=15))])
    with pytest.raises(V2SetupReaderError):
        _run(read_v2_consensus_feature_window(
            conn, symbol="BTCUSDT", market_type="perp", timeframe="15m",
            bucket_start=B - timedelta(minutes=15), bucket_end=B, calculation_version=H16))


def test_consensus_window_json_columns_detached():
    conn = FakeConn([make_consensus_row(coverage_by_metric='{"binance": 1.0}')])
    result = _run(read_v2_consensus_feature_window(
        conn, symbol="BTCUSDT", market_type="perp", timeframe="15m",
        bucket_start=B, bucket_end=B, calculation_version=H16))
    assert result[0]["coverage_by_metric"]["binance"] == 1.0


# ============================================================================
# 2. read_v2_consensus_percentile_window
# ============================================================================
def test_percentile_window_inclusive_interval():
    start = B - timedelta(minutes=15 * 15)
    rows = [make_percentile_row(bucket_ts=start + timedelta(minutes=15 * i)) for i in range(16)]
    conn = FakeConn(rows)
    result = _run(read_v2_consensus_percentile_window(
        conn, symbol="BTCUSDT", market_type="perp", metric="range_width_pct_median",
        timeframe="15m", percentile_window="30d", bucket_start=start, bucket_end=B,
        calculation_version=H16))
    assert len(result) == 16


def test_percentile_window_no_lookahead_violation_rejected():
    conn = FakeConn([make_percentile_row(sample_window_end=B)])  # equal -> violation
    with pytest.raises(V2SetupReaderError):
        _run(read_v2_consensus_percentile_window(
            conn, symbol="BTCUSDT", market_type="perp", metric="range_width_pct_median",
            timeframe="15m", percentile_window="30d", bucket_start=B, bucket_end=B,
            calculation_version=H16))


def test_percentile_window_sample_window_end_strictly_before_bucket_ts_passes():
    conn = FakeConn([make_percentile_row(sample_window_end=B - timedelta(minutes=1))])
    result = _run(read_v2_consensus_percentile_window(
        conn, symbol="BTCUSDT", market_type="perp", metric="range_width_pct_median",
        timeframe="15m", percentile_window="30d", bucket_start=B, bucket_end=B,
        calculation_version=H16))
    assert len(result) == 1


def test_percentile_window_none_sample_window_end_passes():
    row = dict(make_percentile_row())
    row["sample_window_end"] = None
    conn = FakeConn([row])
    result = _run(read_v2_consensus_percentile_window(
        conn, symbol="BTCUSDT", market_type="perp", metric="range_width_pct_median",
        timeframe="15m", percentile_window="30d", bucket_start=B, bucket_end=B,
        calculation_version=H16))
    assert len(result) == 1


def test_percentile_window_wrong_metric_rejected():
    conn = FakeConn([make_percentile_row(metric="price_move_pct_median")])
    with pytest.raises(V2SetupReaderError):
        _run(read_v2_consensus_percentile_window(
            conn, symbol="BTCUSDT", market_type="perp", metric="range_width_pct_median",
            timeframe="15m", percentile_window="30d", bucket_start=B, bucket_end=B,
            calculation_version=H16))


def test_percentile_window_wrong_percentile_window_rejected():
    conn = FakeConn([make_percentile_row(percentile_window="7d")])
    with pytest.raises(V2SetupReaderError):
        _run(read_v2_consensus_percentile_window(
            conn, symbol="BTCUSDT", market_type="perp", metric="range_width_pct_median",
            timeframe="15m", percentile_window="30d", bucket_start=B, bucket_end=B,
            calculation_version=H16))


def test_percentile_window_wrong_scope_rejected():
    conn = FakeConn([make_percentile_row(scope="exchange")])
    with pytest.raises(V2SetupReaderError):
        _run(read_v2_consensus_percentile_window(
            conn, symbol="BTCUSDT", market_type="perp", metric="range_width_pct_median",
            timeframe="15m", percentile_window="30d", bucket_start=B, bucket_end=B,
            calculation_version=H16))


def test_percentile_window_wrong_exchange_rejected():
    conn = FakeConn([make_percentile_row(exchange="binance")])
    with pytest.raises(V2SetupReaderError):
        _run(read_v2_consensus_percentile_window(
            conn, symbol="BTCUSDT", market_type="perp", metric="range_width_pct_median",
            timeframe="15m", percentile_window="30d", bucket_start=B, bucket_end=B,
            calculation_version=H16))


def test_percentile_window_duplicate_bucket_rejected():
    conn = FakeConn([make_percentile_row(), make_percentile_row()])
    with pytest.raises(V2SetupReaderError):
        _run(read_v2_consensus_percentile_window(
            conn, symbol="BTCUSDT", market_type="perp", metric="range_width_pct_median",
            timeframe="15m", percentile_window="30d", bucket_start=B, bucket_end=B,
            calculation_version=H16))


def test_percentile_window_empty_result_is_empty_tuple():
    conn = FakeConn([])
    result = _run(read_v2_consensus_percentile_window(
        conn, symbol="BTCUSDT", market_type="perp", metric="range_width_pct_median",
        timeframe="15m", percentile_window="30d", bucket_start=B, bucket_end=B,
        calculation_version=H16))
    assert result == ()


# ============================================================================
# 3. read_v2_reference_feature_window
# ============================================================================
def test_reference_window_inclusive_interval():
    start = B - timedelta(minutes=15 * 47)
    rows = [make_reference_row(bucket_ts=start + timedelta(minutes=15 * i)) for i in range(48)]
    conn = FakeConn(rows)
    result = _run(read_v2_reference_feature_window(
        conn, exchange="binance", symbol="BTCUSDT", market_type="perp", timeframe="15m",
        bucket_start=start, bucket_end=B, calculation_version=H16))
    assert len(result) == 48


def test_reference_window_wrong_exchange_rejected():
    conn = FakeConn([make_reference_row(exchange="bybit")])
    with pytest.raises(V2SetupReaderError):
        _run(read_v2_reference_feature_window(
            conn, exchange="binance", symbol="BTCUSDT", market_type="perp", timeframe="15m",
            bucket_start=B, bucket_end=B, calculation_version=H16))


def test_reference_window_generic_about_exchange_binance_not_hardcoded():
    conn = FakeConn([make_reference_row(exchange="bybit")])
    result = _run(read_v2_reference_feature_window(
        conn, exchange="bybit", symbol="BTCUSDT", market_type="perp", timeframe="15m",
        bucket_start=B, bucket_end=B, calculation_version=H16))
    assert len(result) == 1


def test_reference_window_bucket_outside_interval_rejected():
    conn = FakeConn([make_reference_row(bucket_ts=B + timedelta(minutes=15))])
    with pytest.raises(V2SetupReaderError):
        _run(read_v2_reference_feature_window(
            conn, exchange="binance", symbol="BTCUSDT", market_type="perp", timeframe="15m",
            bucket_start=B, bucket_end=B, calculation_version=H16))


def test_reference_window_duplicate_bucket_rejected():
    conn = FakeConn([make_reference_row(), make_reference_row()])
    with pytest.raises(V2SetupReaderError):
        _run(read_v2_reference_feature_window(
            conn, exchange="binance", symbol="BTCUSDT", market_type="perp", timeframe="15m",
            bucket_start=B, bucket_end=B, calculation_version=H16))


def test_reference_window_empty_result_is_empty_tuple():
    conn = FakeConn([])
    result = _run(read_v2_reference_feature_window(
        conn, exchange="binance", symbol="BTCUSDT", market_type="perp", timeframe="15m",
        bucket_start=B, bucket_end=B, calculation_version=H16))
    assert result == ()


# ============================================================================
# 4. read_v2_instrument
# ============================================================================
def test_instrument_hit_returns_tick_size():
    conn = FakeConn([make_instrument_row(tick_size=0.5)])
    result = _run(read_v2_instrument(
        conn, exchange="binance", symbol="BTCUSDT", market_type="perp"))
    assert result["tick_size"] == 0.5


def test_instrument_missing_returns_none():
    conn = FakeConn([])
    result = _run(read_v2_instrument(
        conn, exchange="binance", symbol="BTCUSDT", market_type="perp"))
    assert result is None


def test_instrument_more_than_one_row_fails_loudly():
    conn = FakeConn([make_instrument_row(), make_instrument_row()])
    with pytest.raises(V2SetupReaderError):
        _run(read_v2_instrument(
            conn, exchange="binance", symbol="BTCUSDT", market_type="perp"))


def test_instrument_identity_mismatch_rejected():
    conn = FakeConn([make_instrument_row(symbol="ETHUSDT")])
    with pytest.raises(V2SetupReaderError):
        _run(read_v2_instrument(
            conn, exchange="binance", symbol="BTCUSDT", market_type="perp"))


def test_instrument_result_is_immutable():
    from types import MappingProxyType
    conn = FakeConn([make_instrument_row()])
    result = _run(read_v2_instrument(
        conn, exchange="binance", symbol="BTCUSDT", market_type="perp"))
    assert isinstance(result, MappingProxyType)
    with pytest.raises(TypeError):
        result["tick_size"] = 999.0  # type: ignore[index]


# ============================================================================
# 5. FAIL-CLOSED ARGUMENT VALIDATION (before any conn.fetch)
# ============================================================================
@pytest.mark.parametrize("bad_start", [
    datetime(2026, 8, 15, 12, 0),  # naive
    datetime(2026, 8, 15, 15, 0, tzinfo=timezone(timedelta(hours=3))),  # non-UTC
    B.replace(second=1),
    B.replace(microsecond=1),
])
def test_consensus_window_rejects_malformed_start_zero_fetches(bad_start):
    conn = FakeConn([])
    with pytest.raises(V2SetupReaderError):
        _run(read_v2_consensus_feature_window(
            conn, symbol="BTCUSDT", market_type="perp", timeframe="15m",
            bucket_start=bad_start, bucket_end=B, calculation_version=H16))
    assert conn.fetch_calls == []


def test_consensus_window_rejects_start_after_end_zero_fetches():
    conn = FakeConn([])
    with pytest.raises(V2SetupReaderError):
        _run(read_v2_consensus_feature_window(
            conn, symbol="BTCUSDT", market_type="perp", timeframe="15m",
            bucket_start=B, bucket_end=B - timedelta(minutes=15), calculation_version=H16))
    assert conn.fetch_calls == []


def test_consensus_window_start_equals_end_is_valid():
    conn = FakeConn([])
    result = _run(read_v2_consensus_feature_window(
        conn, symbol="BTCUSDT", market_type="perp", timeframe="15m",
        bucket_start=B, bucket_end=B, calculation_version=H16))
    assert result == ()
    assert len(conn.fetch_calls) == 1


@pytest.mark.parametrize("field", ["symbol", "market_type", "timeframe"])
def test_consensus_window_rejects_blank_identifiers(field):
    conn = FakeConn([])
    kwargs = dict(symbol="BTCUSDT", market_type="perp", timeframe="15m",
                 bucket_start=B, bucket_end=B, calculation_version=H16)
    kwargs[field] = ""
    with pytest.raises(V2SetupReaderError, match=field):
        _run(read_v2_consensus_feature_window(conn, **kwargs))
    assert conn.fetch_calls == []


def test_consensus_window_rejects_malformed_calculation_version():
    conn = FakeConn([])
    with pytest.raises(V2SetupReaderError):
        _run(read_v2_consensus_feature_window(
            conn, symbol="BTCUSDT", market_type="perp", timeframe="15m",
            bucket_start=B, bucket_end=B, calculation_version="not-hex"))
    assert conn.fetch_calls == []


@pytest.mark.parametrize("field", ["symbol", "market_type", "metric", "timeframe", "percentile_window"])
def test_percentile_window_rejects_blank_identifiers(field):
    conn = FakeConn([])
    kwargs = dict(symbol="BTCUSDT", market_type="perp", metric="range_width_pct_median",
                 timeframe="15m", percentile_window="30d", bucket_start=B, bucket_end=B,
                 calculation_version=H16)
    kwargs[field] = ""
    with pytest.raises(V2SetupReaderError, match=field):
        _run(read_v2_consensus_percentile_window(conn, **kwargs))
    assert conn.fetch_calls == []


@pytest.mark.parametrize("field", ["exchange", "symbol", "market_type", "timeframe"])
def test_reference_window_rejects_blank_identifiers(field):
    conn = FakeConn([])
    kwargs = dict(exchange="binance", symbol="BTCUSDT", market_type="perp", timeframe="15m",
                 bucket_start=B, bucket_end=B, calculation_version=H16)
    kwargs[field] = ""
    with pytest.raises(V2SetupReaderError, match=field):
        _run(read_v2_reference_feature_window(conn, **kwargs))
    assert conn.fetch_calls == []


@pytest.mark.parametrize("field", ["exchange", "symbol", "market_type"])
def test_instrument_rejects_blank_identifiers(field):
    conn = FakeConn([])
    kwargs = dict(exchange="binance", symbol="BTCUSDT", market_type="perp")
    kwargs[field] = ""
    with pytest.raises(V2SetupReaderError, match=field):
        _run(read_v2_instrument(conn, **kwargs))
    assert conn.fetch_calls == []


def test_validate_consensus_feature_window_args_valid_passes():
    validate_consensus_feature_window_args(
        symbol="BTCUSDT", market_type="perp", timeframe="15m",
        bucket_start=B, bucket_end=B, calculation_version=H16)


def test_validate_consensus_percentile_window_args_valid_passes():
    validate_consensus_percentile_window_args(
        symbol="BTCUSDT", market_type="perp", metric="range_width_pct_median",
        timeframe="15m", percentile_window="30d", bucket_start=B, bucket_end=B,
        calculation_version=H16)


def test_validate_reference_feature_window_args_valid_passes():
    validate_reference_feature_window_args(
        exchange="binance", symbol="BTCUSDT", market_type="perp", timeframe="15m",
        bucket_start=B, bucket_end=B, calculation_version=H16)


def test_validate_instrument_args_valid_passes():
    validate_instrument_args(exchange="binance", symbol="BTCUSDT", market_type="perp")


# ============================================================================
# 6. RETURN HARDENING — never a bare KeyError/AttributeError/TypeError
# ============================================================================
def test_consensus_window_malformed_bucket_ts_from_broken_conn_rejected():
    conn = FakeConn([make_consensus_row(bucket_ts="not-a-datetime")])
    with pytest.raises(V2SetupReaderError):
        _run(read_v2_consensus_feature_window(
            conn, symbol="BTCUSDT", market_type="perp", timeframe="15m",
            bucket_start=B, bucket_end=B, calculation_version=H16))


def test_percentile_window_malformed_sample_window_end_rejected():
    conn = FakeConn([make_percentile_row(sample_window_end="not-a-datetime")])
    with pytest.raises(V2SetupReaderError):
        _run(read_v2_consensus_percentile_window(
            conn, symbol="BTCUSDT", market_type="perp", metric="range_width_pct_median",
            timeframe="15m", percentile_window="30d", bucket_start=B, bucket_end=B,
            calculation_version=H16))


def test_reference_window_naive_bucket_ts_from_broken_conn_rejected():
    conn = FakeConn([make_reference_row(bucket_ts=datetime(2026, 8, 15, 12, 0))])
    with pytest.raises(V2SetupReaderError):
        _run(read_v2_reference_feature_window(
            conn, exchange="binance", symbol="BTCUSDT", market_type="perp", timeframe="15m",
            bucket_start=B, bucket_end=B, calculation_version=H16))


# ============================================================================
# 7. SQL SHAPE
# ============================================================================
def test_consensus_window_sql_shape():
    sql = readers_module._CONSENSUS_FEATURE_WINDOW_SQL
    assert "bucket_ts >= $5" in sql
    assert "bucket_ts <= $6" in sql
    assert "calculation_version = $4" in sql
    assert "ORDER BY bucket_ts ASC" in sql
    assert "SELECT *" not in sql


def test_percentile_window_sql_shape():
    sql = readers_module._CONSENSUS_PERCENTILE_WINDOW_SQL
    assert "bucket_ts >= $7" in sql
    assert "bucket_ts <= $8" in sql
    assert "scope = 'consensus'" in sql
    assert "exchange = ''" in sql
    assert "calculation_version = $6" in sql
    assert "ORDER BY bucket_ts ASC" in sql
    assert "SELECT *" not in sql


def test_reference_window_sql_shape():
    sql = readers_module._REFERENCE_FEATURE_WINDOW_SQL
    assert "bucket_ts >= $6" in sql
    assert "bucket_ts <= $7" in sql
    assert "calculation_version = $5" in sql
    assert "ORDER BY bucket_ts ASC" in sql
    assert "SELECT *" not in sql


def test_instrument_sql_shape():
    sql = readers_module._INSTRUMENT_SQL
    assert "exchange = $1" in sql
    assert "symbol = $2" in sql
    assert "market_type = $3" in sql
    assert "SELECT *" not in sql
    assert "bucket_ts" not in sql  # not time-bucketed


@pytest.mark.parametrize("sql_const", [
    "_CONSENSUS_FEATURE_WINDOW_SQL", "_CONSENSUS_PERCENTILE_WINDOW_SQL",
    "_REFERENCE_FEATURE_WINDOW_SQL", "_INSTRUMENT_SQL",
])
def test_no_writes_in_any_reader_sql(sql_const):
    import re
    sql = getattr(readers_module, sql_const).upper()
    # Word-boundary match -- a returned column literally named
    # "updated_at" (exchange_instruments) must not false-positive on the
    # substring "UPDATE".
    for forbidden in ("INSERT", "UPDATE", "DELETE", "UPSERT", "ON CONFLICT", "TRUNCATE", "DROP"):
        assert not re.search(rf"\b{re.escape(forbidden)}\b", sql), f"{forbidden!r} found in {sql_const}"


@pytest.mark.parametrize("sql_const", [
    "_CONSENSUS_FEATURE_WINDOW_SQL", "_CONSENSUS_PERCENTILE_WINDOW_SQL",
    "_REFERENCE_FEATURE_WINDOW_SQL", "_INSTRUMENT_SQL",
])
def test_no_wall_clock_in_any_reader_sql(sql_const):
    sql = getattr(readers_module, sql_const).lower()
    assert "now()" not in sql
    assert "current_timestamp" not in sql
    assert "computed_at" not in sql or sql_const in (
        "_CONSENSUS_FEATURE_WINDOW_SQL", "_REFERENCE_FEATURE_WINDOW_SQL",
        "_CONSENSUS_PERCENTILE_WINDOW_SQL",
    )  # computed_at is a returned metadata column, never a WHERE-clause cutoff


@pytest.mark.parametrize("sql_const", [
    "_CONSENSUS_FEATURE_WINDOW_SQL", "_CONSENSUS_PERCENTILE_WINDOW_SQL",
    "_REFERENCE_FEATURE_WINDOW_SQL",
])
def test_reader_sql_uses_no_limit_as_semantic_substitute(sql_const):
    sql = getattr(readers_module, sql_const).upper()
    assert "LIMIT" not in sql


# ============================================================================
# 8. PURITY / LAYERING
# ============================================================================
def _executable_body_source(module) -> str:
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
    assert inspect.iscoroutinefunction(read_v2_consensus_feature_window)
    assert inspect.iscoroutinefunction(read_v2_consensus_percentile_window)
    assert inspect.iscoroutinefunction(read_v2_reference_feature_window)
    assert inspect.iscoroutinefunction(read_v2_instrument)


def test_validators_are_plain_sync_functions():
    assert not inspect.iscoroutinefunction(validate_consensus_feature_window_args)
    assert not inspect.iscoroutinefunction(validate_consensus_percentile_window_args)
    assert not inspect.iscoroutinefunction(validate_reference_feature_window_args)
    assert not inspect.iscoroutinefunction(validate_instrument_args)


# ============================================================================
# 9. Database WRAPPERS
# ============================================================================
def test_wrapper_consensus_feature_window_validates_before_acquire():
    db = _db()
    with pytest.raises(V2SetupReaderError):
        _run(db.fetch_v2_consensus_feature_window(
            symbol="", market_type="perp", timeframe="15m",
            bucket_start=B, bucket_end=B, calculation_version=H16))
    assert db.pool.acquire_count == 0


def test_wrapper_consensus_feature_window_delegates_correct_sql():
    conn = FakeConn([])
    db = _db(conn)
    _run(db.fetch_v2_consensus_feature_window(
        symbol="BTCUSDT", market_type="perp", timeframe="15m",
        bucket_start=B, bucket_end=B, calculation_version=H16))
    assert conn.fetch_calls[0][0] == readers_module._CONSENSUS_FEATURE_WINDOW_SQL
    assert db.pool.acquire_count == 1


def test_wrapper_consensus_percentile_window_validates_before_acquire():
    db = _db()
    with pytest.raises(V2SetupReaderError):
        _run(db.fetch_v2_consensus_percentile_window(
            symbol="BTCUSDT", market_type="perp", metric="range_width_pct_median",
            timeframe="", percentile_window="30d", bucket_start=B, bucket_end=B,
            calculation_version=H16))
    assert db.pool.acquire_count == 0


def test_wrapper_consensus_percentile_window_returns_detached_tuple():
    conn = FakeConn([make_percentile_row()])
    db = _db(conn)
    result = _run(db.fetch_v2_consensus_percentile_window(
        symbol="BTCUSDT", market_type="perp", metric="range_width_pct_median",
        timeframe="15m", percentile_window="30d", bucket_start=B, bucket_end=B,
        calculation_version=H16))
    assert isinstance(result, tuple) and len(result) == 1
    assert db.pool.acquire_count == 1


def test_wrapper_reference_feature_window_validates_before_acquire():
    db = _db()
    with pytest.raises(V2SetupReaderError):
        _run(db.fetch_v2_reference_feature_window(
            exchange="", symbol="BTCUSDT", market_type="perp", timeframe="15m",
            bucket_start=B, bucket_end=B, calculation_version=H16))
    assert db.pool.acquire_count == 0


def test_wrapper_reference_feature_window_delegates_correct_sql():
    conn = FakeConn([])
    db = _db(conn)
    _run(db.fetch_v2_reference_feature_window(
        exchange="binance", symbol="BTCUSDT", market_type="perp", timeframe="15m",
        bucket_start=B, bucket_end=B, calculation_version=H16))
    assert conn.fetch_calls[0][0] == readers_module._REFERENCE_FEATURE_WINDOW_SQL


def test_wrapper_instrument_validates_before_acquire():
    db = _db()
    with pytest.raises(V2SetupReaderError):
        _run(db.fetch_v2_instrument(exchange="binance", symbol="", market_type="perp"))
    assert db.pool.acquire_count == 0


def test_wrapper_instrument_returns_none_on_empty():
    db = _db(FakeConn([]))
    result = _run(db.fetch_v2_instrument(exchange="binance", symbol="BTCUSDT", market_type="perp"))
    assert result is None
    assert db.pool.acquire_count == 1


def test_wrapper_instrument_delegates_correct_sql():
    conn = FakeConn([make_instrument_row()])
    db = _db(conn)
    _run(db.fetch_v2_instrument(exchange="binance", symbol="BTCUSDT", market_type="perp"))
    assert conn.fetch_calls[0][0] == readers_module._INSTRUMENT_SQL


def test_wrapper_no_pool_raises_assertion_after_validation():
    db = Database("postgresql://unused")  # pool is None
    with pytest.raises(AssertionError):
        _run(db.fetch_v2_consensus_feature_window(
            symbol="BTCUSDT", market_type="perp", timeframe="15m",
            bucket_start=B, bucket_end=B, calculation_version=H16))


# ============================================================================
# 10. DIRECT READERS SELF-VALIDATE (fail-closed even without the Database
# wrapper)
# ============================================================================
def test_direct_consensus_feature_window_reader_rejects_malformed_symbol_zero_fetches():
    conn = FakeConn([])
    with pytest.raises(V2SetupReaderError, match="symbol"):
        _run(read_v2_consensus_feature_window(
            conn, symbol="", market_type="perp", timeframe="15m",
            bucket_start=B, bucket_end=B, calculation_version=H16))
    assert conn.fetch_calls == []


def test_direct_percentile_window_reader_rejects_malformed_metric_zero_fetches():
    conn = FakeConn([])
    with pytest.raises(V2SetupReaderError, match="metric"):
        _run(read_v2_consensus_percentile_window(
            conn, symbol="BTCUSDT", market_type="perp", metric="",
            timeframe="15m", percentile_window="30d", bucket_start=B, bucket_end=B,
            calculation_version=H16))
    assert conn.fetch_calls == []


def test_direct_reference_window_reader_rejects_malformed_exchange_zero_fetches():
    conn = FakeConn([])
    with pytest.raises(V2SetupReaderError, match="exchange"):
        _run(read_v2_reference_feature_window(
            conn, exchange="", symbol="BTCUSDT", market_type="perp", timeframe="15m",
            bucket_start=B, bucket_end=B, calculation_version=H16))
    assert conn.fetch_calls == []


def test_direct_instrument_reader_rejects_malformed_market_type_zero_fetches():
    conn = FakeConn([])
    with pytest.raises(V2SetupReaderError, match="market_type"):
        _run(read_v2_instrument(conn, exchange="binance", symbol="BTCUSDT", market_type=""))
    assert conn.fetch_calls == []


# ============================================================================
# 11. RETURNED-ROW SHAPE HARDENING (pre-merge amendment) — a broken/fake
# connection returning {}, a partial dict, or a bare non-Mapping value must
# never leak a bare KeyError/AttributeError/TypeError: it must always
# surface as this module's own V2SetupReaderError. "Missing key" (a
# structurally incomplete row) is a categorically different failure from
# "present key, SQL NULL" — the latter remains legitimate and unaffected by
# this hardening (see the pre-existing nullable-JSON/sample_window_end
# tests above, all still passing unchanged).
# ============================================================================
def _drop(row: dict, *keys: str) -> dict:
    row = dict(row)
    for k in keys:
        row.pop(k, None)
    return row


@pytest.mark.parametrize("bad_row", [
    {},
    "not-a-row",
    None,
    ["symbol", "BTCUSDT"],
])
def test_consensus_window_rejects_malformed_row_shape(bad_row):
    conn = FakeConn([bad_row])
    with pytest.raises(V2SetupReaderError):
        _run(read_v2_consensus_feature_window(
            conn, symbol="BTCUSDT", market_type="perp", timeframe="15m",
            bucket_start=B, bucket_end=B, calculation_version=H16))


@pytest.mark.parametrize("missing_field", ["symbol", "bucket_ts"])
def test_consensus_window_rejects_row_missing_required_field(missing_field):
    conn = FakeConn([_drop(make_consensus_row(), missing_field)])
    with pytest.raises(V2SetupReaderError, match=missing_field):
        _run(read_v2_consensus_feature_window(
            conn, symbol="BTCUSDT", market_type="perp", timeframe="15m",
            bucket_start=B, bucket_end=B, calculation_version=H16))


@pytest.mark.parametrize("bad_row", [{}, "not-a-row", None])
def test_percentile_window_rejects_malformed_row_shape(bad_row):
    conn = FakeConn([bad_row])
    with pytest.raises(V2SetupReaderError):
        _run(read_v2_consensus_percentile_window(
            conn, symbol="BTCUSDT", market_type="perp", metric="range_width_pct_median",
            timeframe="15m", percentile_window="30d", bucket_start=B, bucket_end=B,
            calculation_version=H16))


@pytest.mark.parametrize("missing_field", ["scope", "sample_window_end", "bucket_ts"])
def test_percentile_window_rejects_row_missing_required_field(missing_field):
    conn = FakeConn([_drop(make_percentile_row(), missing_field)])
    with pytest.raises(V2SetupReaderError, match=missing_field):
        _run(read_v2_consensus_percentile_window(
            conn, symbol="BTCUSDT", market_type="perp", metric="range_width_pct_median",
            timeframe="15m", percentile_window="30d", bucket_start=B, bucket_end=B,
            calculation_version=H16))


@pytest.mark.parametrize("bad_row", [{}, "not-a-row", None])
def test_reference_window_rejects_malformed_row_shape(bad_row):
    conn = FakeConn([bad_row])
    with pytest.raises(V2SetupReaderError):
        _run(read_v2_reference_feature_window(
            conn, exchange="binance", symbol="BTCUSDT", market_type="perp", timeframe="15m",
            bucket_start=B, bucket_end=B, calculation_version=H16))


@pytest.mark.parametrize("missing_field", ["exchange", "bucket_ts"])
def test_reference_window_rejects_row_missing_required_field(missing_field):
    conn = FakeConn([_drop(make_reference_row(), missing_field)])
    with pytest.raises(V2SetupReaderError, match=missing_field):
        _run(read_v2_reference_feature_window(
            conn, exchange="binance", symbol="BTCUSDT", market_type="perp", timeframe="15m",
            bucket_start=B, bucket_end=B, calculation_version=H16))


@pytest.mark.parametrize("bad_row", [{}, "not-a-row", None])
def test_instrument_rejects_malformed_row_shape(bad_row):
    conn = FakeConn([bad_row])
    with pytest.raises(V2SetupReaderError):
        _run(read_v2_instrument(conn, exchange="binance", symbol="BTCUSDT", market_type="perp"))


@pytest.mark.parametrize("missing_field", ["exchange", "tick_size"])
def test_instrument_rejects_row_missing_required_field(missing_field):
    conn = FakeConn([_drop(make_instrument_row(), missing_field)])
    with pytest.raises(V2SetupReaderError, match=missing_field):
        _run(read_v2_instrument(conn, exchange="binance", symbol="BTCUSDT", market_type="perp"))


def test_instrument_missing_row_still_returns_none_unchanged():
    # Unchanged behavior: an entirely absent row is NOT a shape error.
    conn = FakeConn([])
    result = _run(read_v2_instrument(
        conn, exchange="binance", symbol="BTCUSDT", market_type="perp"))
    assert result is None


def test_instrument_duplicate_rows_still_fails_loudly_unchanged():
    # Unchanged behavior: more than one row remains its own distinct error,
    # not something the new shape check should ever mask or alter.
    conn = FakeConn([make_instrument_row(), make_instrument_row()])
    with pytest.raises(V2SetupReaderError):
        _run(read_v2_instrument(
            conn, exchange="binance", symbol="BTCUSDT", market_type="perp"))
