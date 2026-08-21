"""Unit tests for storage/stage2_readers.py + Database.fetch_exchange_feature_raw_bundle.

Uses a fake asyncpg-style pool/connection — no DB, Docker, or network. Async is
driven with asyncio.run (matching tests/storage/test_stage2_writers.py); no
pytest-asyncio dependency. Verifies argument validation before acquire, exact
static reads/boundaries/ordering, and an immutable detached bundle.
"""
from __future__ import annotations

import asyncio
import dataclasses
from datetime import datetime, timedelta, timezone
from types import MappingProxyType

import pytest

from storage.db import Database
from storage.stage2_readers import (
    ExchangeFeatureRawBundle, KLINES_SQL, LATEST_FUNDING_SQL, LIQUIDATIONS_SQL,
    OPEN_INTEREST_SQL, INSTRUMENT_SQL, LIQUIDATION_CAPABILITY_SQL,
    REQUIRED_METADATA_REVISION_SQL, Stage2ReaderError,
)

B0 = datetime(2026, 3, 1, 0, 0, 0, tzinfo=timezone.utc)
B1 = B0 + timedelta(minutes=5)
RAW_SQL = (KLINES_SQL, OPEN_INTEREST_SQL, LATEST_FUNDING_SQL, LIQUIDATIONS_SQL)
META_SQL = (INSTRUMENT_SQL, LIQUIDATION_CAPABILITY_SQL)


def _run(coro):
    return asyncio.run(coro)


class FakeConn:
    def __init__(self, fetch_results, fetchrow_results):
        self.fetch_calls = []
        self.fetchrow_calls = []
        self._fetch = list(fetch_results)
        self._fetchrow = list(fetchrow_results)

    async def fetch(self, sql, *args):
        self.fetch_calls.append((sql, args))
        return self._fetch.pop(0)

    async def fetchrow(self, sql, *args):
        self.fetchrow_calls.append((sql, args))
        return self._fetchrow.pop(0)

    async def execute(self, *a, **k):          # pragma: no cover - must never run
        raise AssertionError("execute() must not be called")

    async def executemany(self, *a, **k):      # pragma: no cover
        raise AssertionError("executemany() must not be called")


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


def _db(conn) -> Database:
    db = Database("postgresql://ignored")
    db.pool = FakePool(conn)
    return db


def _default_conn():
    # fetch order: klines, open_interest, liquidations ; fetchrow: funding,
    # instrument, capability, required_metadata_revision
    return FakeConn(
        fetch_results=[[{"exchange": "binance", "symbol": "BTCUSDT", "ts": B0}], [], []],
        fetchrow_results=[None, None, None, {"required_revision": 1}])


def _call(db, **over):
    kw = dict(exchange="binance", symbol="BTCUSDT", market_type="perp",
              bucket_start=B0, bucket_end=B1)
    kw.update(over)
    return _run(db.fetch_exchange_feature_raw_bundle(**kw))


# ============================ A. input validation ===========================
@pytest.mark.parametrize("over", [
    {"exchange": ""}, {"exchange": "  "}, {"exchange": 5}, {"exchange": True},
    {"symbol": ""}, {"market_type": ""},
    {"bucket_start": datetime(2026, 3, 1)},              # naive
    {"bucket_end": datetime(2026, 3, 1)},                # naive
    {"bucket_start": datetime(2026, 3, 1, tzinfo=timezone(timedelta(hours=2)))},  # non-UTC
    {"bucket_start": B1, "bucket_end": B1},              # start == end
    {"bucket_start": B1, "bucket_end": B0},              # start > end
    {"bucket_start": 123}, {"bucket_end": True},         # not datetimes
])
def test_invalid_args_rejected_before_acquire(over):
    conn = _default_conn()
    db = _db(conn)
    with pytest.raises(Stage2ReaderError):
        _call(db, **over)
    assert db.pool.acquire_count == 0                     # never acquired


# ============================== B. execution ================================
def test_execution_one_acquire_seven_reads_exact_sql_and_args():
    conn = _default_conn()
    db = _db(conn)
    _call(db)
    assert db.pool.acquire_count == 1                     # exactly one acquisition
    assert len(conn.fetch_calls) == 3                     # klines, oi, liquidations
    assert len(conn.fetchrow_calls) == 4                  # funding, instrument, capability,
                                                           # required_metadata_revision

    (k_sql, k_args), (oi_sql, oi_args), (liq_sql, liq_args) = conn.fetch_calls
    (f_sql, f_args), (i_sql, i_args), (c_sql, c_args), (r_sql, r_args) = conn.fetchrow_calls

    assert k_sql == KLINES_SQL and k_args == ("binance", "BTCUSDT", B0, B1)
    assert oi_sql == OPEN_INTEREST_SQL and oi_args == ("binance", "BTCUSDT", B0, B1)
    assert liq_sql == LIQUIDATIONS_SQL and liq_args == ("binance", "BTCUSDT", B0, B1)
    assert f_sql == LATEST_FUNDING_SQL and f_args == ("binance", "BTCUSDT", B1)   # < end only
    assert i_sql == INSTRUMENT_SQL and i_args == ("binance", "BTCUSDT", "perp")
    assert c_sql == LIQUIDATION_CAPABILITY_SQL
    assert c_args == ("binance", "BTCUSDT", "perp", "liquidations")
    assert r_sql == REQUIRED_METADATA_REVISION_SQL and r_args == ()


def test_static_sql_shape():
    for sql in RAW_SQL + META_SQL:
        assert "SELECT *" not in sql                      # explicit columns only
    for sql in (KLINES_SQL, OPEN_INTEREST_SQL, LIQUIDATIONS_SQL):
        assert "ts >= $3" in sql and "ts < $4" in sql     # [start, end)
        assert "ORDER BY ts ASC" in sql
    assert "ts < $3" in LATEST_FUNDING_SQL and "LIMIT 1" in LATEST_FUNDING_SQL
    assert "ORDER BY ts DESC" in LATEST_FUNDING_SQL       # strict < end, no lower bound
    assert "ORDER BY ts ASC, id ASC" in LIQUIDATIONS_SQL  # liquidation order includes id
    for sql in RAW_SQL:                                   # raw Stage 1 SQL: no market_type, no source filter
        assert "market_type" not in sql
        assert "source" not in sql
    for sql in META_SQL:                                  # Stage 2 metadata/capability SQL: market_type
        assert "market_type = $3" in sql


# =============================== C. bundle ==================================
def test_bundle_empty_collections_and_none_scalars():
    conn = FakeConn(fetch_results=[[], [], []],
                    fetchrow_results=[None, None, None, {"required_revision": 1}])
    db = _db(conn)
    bundle = _call(db)
    assert isinstance(bundle, ExchangeFeatureRawBundle)
    assert bundle.klines == () and bundle.open_interest == () and bundle.liquidations == ()
    assert bundle.latest_funding is None
    assert bundle.instrument is None
    assert bundle.liquidation_capability is None          # preserved for the adapter to reject
    assert bundle.required_metadata_revision == 1


def test_bundle_rows_detached_immutable_and_isolated():
    krow = {"exchange": "binance", "symbol": "BTCUSDT", "ts": B0, "close": 1.0}
    klist = [krow]
    frow = {"exchange": "binance", "symbol": "BTCUSDT", "ts": B0, "funding_rate": 0.1}
    conn = FakeConn(fetch_results=[klist, [], []],
                    fetchrow_results=[frow, None, None, {"required_revision": 1}])
    db = _db(conn)
    bundle = _call(db)

    assert isinstance(bundle.klines, tuple)
    assert isinstance(bundle.klines[0], MappingProxyType)
    assert isinstance(bundle.latest_funding, MappingProxyType)
    with pytest.raises(TypeError):
        bundle.klines[0]["close"] = 9.0                   # immutable row
    krow["close"] = 9.0                                   # mutate source record...
    klist.append({"x": 1})                                # ...and source list
    assert bundle.klines[0]["close"] == 1.0 and len(bundle.klines) == 1   # bundle isolated
    with pytest.raises(dataclasses.FrozenInstanceError):
        bundle.klines = ()


# ==================== D. required_metadata_revision (review 4991738511) ====
def test_bundle_carries_required_metadata_revision_from_singleton_row():
    conn = FakeConn(fetch_results=[[], [], []],
                    fetchrow_results=[None, None, None, {"required_revision": 7}])
    db = _db(conn)
    bundle = _call(db)
    assert bundle.required_metadata_revision == 7


def test_missing_singleton_row_fails_closed():
    """No `stage2_instrument_metadata_state` row at all (schema created but
    never bootstrapped) must raise -- never silently default to `1` or any
    other value on the read side; only the dataclass's own OWN default
    (for hand-built bundles that predate this mechanism) is `1`, never
    the real reader's own behavior on a genuinely missing row."""
    conn = FakeConn(fetch_results=[[], [], []], fetchrow_results=[None, None, None, None])
    db = _db(conn)
    with pytest.raises(Stage2ReaderError, match="not properly bootstrapped"):
        _call(db)
