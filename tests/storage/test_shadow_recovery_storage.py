"""Storage-layer tests for shadow recovery: additive watermark DDL, explicit
recovery SQL, reader validation + anti-join, and the advisory-lock connection
ownership on the Database method. No real DB / Docker / network.
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType

import pytest

from storage.db import Database
from storage.shadow_recovery_readers import (
    DUE_OUTCOME_ANTIJOIN_SQL, NEWEST_PREDICTION_BUCKET_SQL,
    RECOVERY_PREDICTION_CANDIDATES_SQL, SHADOW_WATERMARK_SELECT_SQL,
    SHADOW_WATERMARK_UPSERT_SQL, ShadowRecoveryReaderError,
    advance_shadow_watermark, read_missing_outcome_identities,
    read_recovery_prediction_candidates, read_shadow_watermark,
)

UTC = timezone.utc
B = datetime(2026, 3, 1, 0, 0, tzinfo=UTC)
SCHEMA = Path("storage/stage2_schema.sql").read_text(encoding="utf-8")


def _run(coro):
    return asyncio.run(coro)


# ============================================================================
# A. additive watermark DDL
# ============================================================================
def test_watermark_table_is_additive_and_idempotent():
    assert "CREATE TABLE IF NOT EXISTS shadow_recovery_watermarks" in SCHEMA
    body = re.search(
        r"CREATE TABLE IF NOT EXISTS shadow_recovery_watermarks \((.*?)\n\);",
        SCHEMA, re.DOTALL).group(1)
    for col in ("runner_name", "symbol", "market_type", "timeframe",
                "last_completed_bucket_ts", "updated_at"):
        assert col in body, col
    assert "PRIMARY KEY (runner_name, symbol, market_type, timeframe)" in body
    assert "ck_srw_bucket_5m" in body            # 5m alignment CHECK
    assert "length(btrim(runner_name)) > 0" in body


def test_watermark_ddl_touches_no_stage1_table():
    # additive only: never ALTER/DROP a Stage 1 raw table
    section = SCHEMA[SCHEMA.index("shadow_recovery_watermarks"):]
    for t in ("klines_1m", "open_interest", "funding_rate", "liquidations",
              "exchange_capabilities"):
        assert not re.search(r"(ALTER|DROP)\s+TABLE[^\n]*" + t, SCHEMA)
    assert "ALTER TABLE" not in section and "DROP TABLE" not in section


# ============================================================================
# B. recovery SQL is explicit + anti-join
# ============================================================================
def test_recovery_sql_explicit_no_star():
    for sql in (SHADOW_WATERMARK_SELECT_SQL, SHADOW_WATERMARK_UPSERT_SQL,
                NEWEST_PREDICTION_BUCKET_SQL, RECOVERY_PREDICTION_CANDIDATES_SQL,
                DUE_OUTCOME_ANTIJOIN_SQL):
        assert "*" not in sql


def test_watermark_upsert_is_monotonic():
    assert "GREATEST(" in SHADOW_WATERMARK_UPSERT_SQL
    assert "ON CONFLICT (runner_name, symbol, market_type, timeframe) DO UPDATE" in SHADOW_WATERMARK_UPSERT_SQL


def test_due_outcome_sql_is_a_real_anti_join():
    sql = DUE_OUTCOME_ANTIJOIN_SQL
    assert "LEFT JOIN forecast_outcomes" in sql
    assert "WHERE fo.bucket_ts IS NULL" in sql       # anti-join
    assert "ORDER BY cand.ord ASC" in sql            # deterministic caller order


def test_candidates_sql_deterministic_order_and_limit():
    sql = RECOVERY_PREDICTION_CANDIDATES_SQL
    assert "ORDER BY bucket_ts ASC, calculation_version ASC, rule_version ASC" in sql
    assert "LIMIT $5" in sql
    assert "consensus_snapshot" in sql               # needed for hydration


# ============================================================================
# C. reader validation before I/O (fake conn)
# ============================================================================
class FakeConn:
    def __init__(self, *, fetch=None, fetchval=None):
        self.fetch_calls = []
        self.fetchval_calls = []
        self.execute_calls = []
        self._fetch = fetch if fetch is not None else []
        self._fetchval = fetchval

    async def fetch(self, sql, *args):
        self.fetch_calls.append((sql, args))
        return self._fetch

    async def fetchval(self, sql, *args):
        self.fetchval_calls.append((sql, args))
        return self._fetchval

    async def execute(self, sql, *args):
        self.execute_calls.append((sql, args))


@pytest.mark.parametrize("over", [
    {"runner_name": ""}, {"symbol": ""}, {"market_type": "  "}, {"timeframe": ""},
])
def test_watermark_read_validates_before_io(over):
    conn = FakeConn(fetchval=B)
    kw = dict(runner_name="r", symbol="BTCUSDT", market_type="perp", timeframe="5m")
    kw.update(over)
    with pytest.raises(ShadowRecoveryReaderError):
        _run(read_shadow_watermark(conn, **kw))
    assert conn.fetchval_calls == []


@pytest.mark.parametrize("bucket", [
    datetime(2026, 3, 1, 0, 2, tzinfo=UTC),                       # not 5m aligned
    datetime(2026, 3, 1, 0, 0),                                   # naive
    datetime(2026, 3, 1, 0, 0, 30, tzinfo=UTC),                   # seconds
])
def test_watermark_advance_rejects_bad_bucket_before_io(bucket):
    conn = FakeConn()
    with pytest.raises(ShadowRecoveryReaderError):
        _run(advance_shadow_watermark(conn, runner_name="r", symbol="BTCUSDT",
                                      market_type="perp", timeframe="5m", bucket_ts=bucket))
    assert conn.execute_calls == []


def test_candidates_reader_detaches_and_parses_json():
    rec = {"symbol": "BTCUSDT", "market_type": "perp", "timeframe": "5m",
           "bucket_ts": B, "feature_schema_version": 1, "calculation_version": "c",
           "rule_version": "r", "direction": "LONG", "confidence": 0.4,
           "horizon_set": '["15m","1h"]', "reasons": '["X"]',
           "component_scores": '{"price":0.1}', "final_score": 0.3,
           "reference_price": 105.0, "reference_price_source": "binance_close_5m",
           "exchanges_expected_max": 3, "min_coverage_ratio": 1.0,
           "data_confidence_overall": 80.0, "consensus_confidence": 80.0,
           "is_partial_consensus": False, "consensus_snapshot": '{"a":1}',
           "config_hash": "h", "config_version": "v", "code_version": "cv"}
    conn = FakeConn(fetch=[rec])
    rows = _run(read_recovery_prediction_candidates(
        conn, symbol="BTCUSDT", market_type="perp", timeframe="5m",
        lookback_start=B, limit=10))
    assert isinstance(rows, tuple) and isinstance(rows[0], MappingProxyType)
    assert rows[0]["horizon_set"] == ["15m", "1h"]        # JSON parsed
    assert rows[0]["consensus_snapshot"] == {"a": 1}


def test_missing_outcome_empty_candidates_no_fetch():
    conn = FakeConn(fetch=[])
    out = _run(read_missing_outcome_identities(
        conn, symbol="BTCUSDT", market_type="perp", timeframe="5m",
        candidates=[], evaluation_price_source="klines_1m"))
    assert out == () and conn.fetch_calls == []


def test_missing_outcome_antijoin_passes_zipped_arrays_and_detaches():
    cands = [(B, "c1", "r1", "15m", "binance", "v"),
             (B, "c1", "r1", "1h", "binance", "v")]
    ret = [{"bucket_ts": B, "calculation_version": "c1", "rule_version": "r1",
            "horizon": "15m", "evaluation_exchange": "binance", "outcome_version": "v"}]
    conn = FakeConn(fetch=ret)
    out = _run(read_missing_outcome_identities(
        conn, symbol="BTCUSDT", market_type="perp", timeframe="5m",
        candidates=cands, evaluation_price_source="klines_1m"))
    sql, args = conn.fetch_calls[0]
    # symbol/mt/tf + 6 zipped arrays + price source = 10 args
    assert len(args) == 10
    assert args[3] == [B, B] and args[6] == ["15m", "1h"]        # bucket_ts[], horizon[]
    assert args[9] == "klines_1m"
    assert isinstance(out[0], MappingProxyType) and out[0]["horizon"] == "15m"


# ============================================================================
# D. advisory lock — Database connection ownership
# ============================================================================
class LockConn:
    def __init__(self, try_result=True):
        self.try_result = try_result
        self.calls = []

    async def fetchval(self, sql, *args):
        self.calls.append((sql, args))
        if "pg_try_advisory_lock" in sql:
            return self.try_result
        if "pg_advisory_unlock" in sql:
            return True
        raise AssertionError(sql)


class LockPool:
    def __init__(self, conn):
        self.conn = conn
        self.acquired = 0
        self.released = 0

    async def acquire(self):
        self.acquired += 1
        return self.conn

    async def release(self, conn):
        assert conn is self.conn
        self.released += 1


def _lock_db(conn):
    db = Database("postgresql://ignored")
    db.pool = LockPool(conn)
    return db


def test_advisory_lock_acquired_holds_one_conn_and_releases():
    conn = LockConn(try_result=True)
    db = _lock_db(conn)

    async def scenario():
        async with db.shadow_recovery_lock(123) as acquired:
            assert acquired is True
            assert db.pool.acquired == 1 and db.pool.released == 0   # held
        return True

    assert _run(scenario()) is True
    assert db.pool.released == 1                              # released after success
    verbs = [s for s, _ in conn.calls]
    assert any("pg_try_advisory_lock" in v for v in verbs)
    assert any("pg_advisory_unlock" in v for v in verbs)     # unlocked


def test_advisory_lock_held_yields_false_no_unlock_but_releases():
    conn = LockConn(try_result=False)
    db = _lock_db(conn)

    async def scenario():
        async with db.shadow_recovery_lock(123) as acquired:
            assert acquired is False
        return True

    _run(scenario())
    assert db.pool.released == 1                              # connection still returned
    assert not any("pg_advisory_unlock" in s for s, _ in conn.calls)   # never locked -> no unlock


def test_advisory_lock_released_after_exception():
    conn = LockConn(try_result=True)
    db = _lock_db(conn)

    async def scenario():
        async with db.shadow_recovery_lock(123) as acquired:
            assert acquired is True
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        _run(scenario())
    assert db.pool.released == 1                              # released in finally
    assert any("pg_advisory_unlock" in s for s, _ in conn.calls)   # unlocked in finally


def test_advisory_lock_key_must_be_int():
    db = _lock_db(LockConn())

    async def scenario():
        async with db.shadow_recovery_lock("not-an-int"):
            pass

    with pytest.raises(ValueError):
        _run(scenario())


# ============================================================================
# E. no analytics import in the storage reader
# ============================================================================
def test_reader_module_imports_no_analytics():
    import ast
    src = Path("storage/shadow_recovery_readers.py").read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith("analytics")
        if isinstance(node, ast.Import):
            for a in node.names:
                assert not a.name.startswith("analytics")
