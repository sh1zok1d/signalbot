"""Unit tests for storage/forecast_outcome_readers.py + Database.fetch_forecast_outcome_klines.

Fake asyncpg-style pool/connection — no DB, Docker, or network. Async is driven
with asyncio.run (matching tests/storage/test_stage2_writers.py). Verifies static
SQL (no SELECT *, half-open window, chronological order, no market_type), a single
fetch, a detached/immutable result, arg validation before acquire, and that the
reader module imports no analytics.
"""
from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType

import asyncio

import pytest

from storage.db import Database
from storage.forecast_outcome_readers import (
    FORECAST_OUTCOME_KLINES_SQL, ForecastOutcomeReaderError,
    read_forecast_outcome_klines, validate_forecast_outcome_reader_args,
)

UTC = timezone.utc
START = datetime(2026, 3, 1, 0, 5, 0, tzinfo=UTC)     # evaluation_start (bucket + 5m)
END_15 = START + timedelta(minutes=15)


def _run(coro):
    return asyncio.run(coro)


class FakeConn:
    def __init__(self, fetch_result):
        self.fetch_calls = []
        self._fetch_result = fetch_result

    async def fetch(self, sql, *args):
        self.fetch_calls.append((sql, args))
        return self._fetch_result

    async def execute(self, *a, **k):          # pragma: no cover - must never run
        raise AssertionError("execute() must not be called")

    async def executemany(self, *a, **k):      # pragma: no cover
        raise AssertionError("executemany() must not be called")

    async def fetchval(self, *a, **k):         # pragma: no cover
        raise AssertionError("fetchval() must not be called")


class FakePool:
    def __init__(self, conn):
        self.conn = conn
        self.acquire_count = 0

    def acquire(self):
        pool = self

        class _Acq:
            async def __aenter__(self_):
                pool.acquire_count += 1
                return pool.conn

            async def __aexit__(self_, *a):
                return False
        return _Acq()


class BoomConn:
    def __init__(self):
        self.fetch_calls = 0

    async def fetch(self, *a, **k):
        self.fetch_calls += 1
        raise RuntimeError("db boom")


def _db(conn) -> Database:
    db = Database("postgresql://ignored")
    db.pool = FakePool(conn)
    return db


def _records(n):
    return [{"exchange": "binance", "symbol": "BTCUSDT",
             "ts": START + timedelta(minutes=i),
             "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}
            for i in range(n)]


# ============================================================================
# static SQL shape
# ============================================================================
def test_sql_has_explicit_columns_no_star():
    sql = FORECAST_OUTCOME_KLINES_SQL
    assert "SELECT exchange, symbol, ts, open, high, low, close" in sql
    assert "*" not in sql
    assert "FROM klines_1m" in sql


def test_sql_is_half_open_ordered_and_has_no_market_type():
    sql = FORECAST_OUTCOME_KLINES_SQL
    assert "ts >= $3" in sql and "ts < $4" in sql       # [start, end)
    assert "ORDER BY ts ASC" in sql
    assert "market_type" not in sql                     # klines_1m has none


# ============================================================================
# reader execution (module-level function against a fake conn)
# ============================================================================
def test_read_one_fetch_exact_sql_and_args():
    conn = FakeConn(_records(15))
    rows = _run(read_forecast_outcome_klines(
        conn, exchange="binance", symbol="BTCUSDT",
        window_start=START, window_end=END_15))
    assert len(conn.fetch_calls) == 1
    sql, args = conn.fetch_calls[0]
    assert sql == FORECAST_OUTCOME_KLINES_SQL
    assert args == ("binance", "BTCUSDT", START, END_15)
    assert len(rows) == 15


def test_read_returns_detached_immutable_mappings():
    conn = FakeConn(_records(3))
    rows = _run(read_forecast_outcome_klines(
        conn, exchange="binance", symbol="BTCUSDT",
        window_start=START, window_end=END_15))
    assert isinstance(rows, tuple)
    assert all(isinstance(r, MappingProxyType) for r in rows)
    with pytest.raises(TypeError):
        rows[0]["close"] = 1.0                          # read-only


def test_read_mutation_isolation_from_source_records():
    src = _records(2)
    conn = FakeConn(src)
    rows = _run(read_forecast_outcome_klines(
        conn, exchange="binance", symbol="BTCUSDT",
        window_start=START, window_end=END_15))
    src[0]["close"] = 999.0                              # mutate original after read
    assert rows[0]["close"] == 100.0                     # detached copy unaffected


def test_read_empty_returns_empty_tuple():
    conn = FakeConn([])
    rows = _run(read_forecast_outcome_klines(
        conn, exchange="binance", symbol="BTCUSDT",
        window_start=START, window_end=END_15))
    assert rows == ()


# ============================================================================
# arg validation (validate_forecast_outcome_reader_args)
# ============================================================================
@pytest.mark.parametrize("over", [
    {"exchange": ""}, {"exchange": "  "}, {"exchange": 5}, {"exchange": None},
    {"symbol": ""}, {"symbol": "   "}, {"symbol": 7},
    {"window_start": datetime(2026, 3, 1, 0, 5)},                 # naive
    {"window_end": datetime(2026, 3, 1, 0, 20)},                  # naive
    {"window_start": datetime(2026, 3, 1, 0, 5, tzinfo=timezone(timedelta(hours=2)))},  # non-UTC
    {"window_start": datetime(2026, 3, 1, 0, 5, 30, tzinfo=UTC)},  # not whole minute
    {"window_start": END_15, "window_end": START},                # start > end
    {"window_start": START, "window_end": START},                 # start == end
    {"window_end": START + timedelta(minutes=30)},                # duration not in {15,60,240}
    {"window_end": START + timedelta(minutes=1)},                 # too short
])
def test_validate_rejects_bad_args(over):
    kw = dict(exchange="binance", symbol="BTCUSDT",
              window_start=START, window_end=END_15)
    kw.update(over)
    with pytest.raises(ForecastOutcomeReaderError):
        validate_forecast_outcome_reader_args(**kw)


@pytest.mark.parametrize("minutes", [15, 60, 240])
def test_validate_accepts_all_horizon_durations(minutes):
    validate_forecast_outcome_reader_args(
        exchange="binance", symbol="BTCUSDT",
        window_start=START, window_end=START + timedelta(minutes=minutes))


# ============================================================================
# Database.fetch_forecast_outcome_klines
# ============================================================================
def test_db_validates_before_acquire():
    conn = FakeConn(_records(15))
    db = _db(conn)
    with pytest.raises(ForecastOutcomeReaderError):
        _run(db.fetch_forecast_outcome_klines(
            exchange="", symbol="BTCUSDT", window_start=START, window_end=END_15))
    assert db.pool.acquire_count == 0                    # never acquired
    assert conn.fetch_calls == []                        # never queried


def test_db_one_acquire_one_fetch_returns_detached():
    conn = FakeConn(_records(15))
    db = _db(conn)
    rows = _run(db.fetch_forecast_outcome_klines(
        exchange="binance", symbol="BTCUSDT", window_start=START, window_end=END_15))
    assert db.pool.acquire_count == 1
    assert len(conn.fetch_calls) == 1
    assert isinstance(rows, tuple) and len(rows) == 15
    assert all(isinstance(r, MappingProxyType) for r in rows)


def test_db_fetch_exception_propagates():
    conn = BoomConn()
    db = _db(conn)
    with pytest.raises(RuntimeError, match="db boom"):
        _run(db.fetch_forecast_outcome_klines(
            exchange="binance", symbol="BTCUSDT", window_start=START, window_end=END_15))
    assert db.pool.acquire_count == 1
    assert conn.fetch_calls == 1


# ============================================================================
# architecture: reader module imports no analytics, does no writes/clock
# ============================================================================
_READER_SRC = Path("storage/forecast_outcome_readers.py")


def test_reader_module_imports_no_analytics():
    tree = ast.parse(_READER_SRC.read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                imported.add(a.name)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    assert not any(m.startswith("analytics") for m in imported), imported


def test_reader_module_has_no_write_or_clock_calls():
    src = _READER_SRC.read_text()
    for banned in ("execute", "executemany", "INSERT", "UPDATE", "now()",
                   "datetime.now", "utcnow", "time.time"):
        assert banned not in src, f"reader must not reference {banned}"
