"""Stage 2 Database methods against a mocked pool/connection (no real DB)."""
from __future__ import annotations

import asyncio

import pytest

from storage.db import Database, SCHEMA_PATH, STAGE2_SCHEMA_PATH


class FakeConn:
    def __init__(self, fetchrow_result=None):
        self.executed: list[tuple] = []
        self.executemany_calls: list[tuple] = []
        self.fetchrow_result = fetchrow_result

    async def execute(self, sql, *args):
        self.executed.append((sql, args))
        return "OK"

    async def executemany(self, sql, rows):
        self.executemany_calls.append((sql, list(rows)))

    async def fetchrow(self, sql, *args):
        return self.fetchrow_result


class _Acquire:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *exc):
        return False


class FakePool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        return _Acquire(self.conn)


def _db(conn):
    db = Database("postgresql://unused")
    db.pool = FakePool(conn)
    return db


def _run(coro):
    return asyncio.run(coro)


# -- init_stage2_schema ------------------------------------------------------
def test_init_stage2_reads_separate_file_and_is_explicit():
    assert STAGE2_SCHEMA_PATH.name == "stage2_schema.sql"
    assert SCHEMA_PATH.name == "schema.sql"
    conn = FakeConn()
    db = _db(conn)
    _run(db.init_stage2_schema())
    joined = " ".join(sql for sql, _ in conn.executed)
    assert "stage2_recompute_queue" in joined
    assert "exchange_instruments" in joined
    # did NOT run the Stage 1 schema: its klines_1m TABLE is absent. (The Stage 2
    # forecast_outcomes CHECK references the string literal 'klines_1m' as its
    # evaluation price source, which is not the Stage 1 table DDL.)
    assert "CREATE TABLE IF NOT EXISTS klines_1m" not in joined
    assert len(conn.executed) >= 10


def test_init_stage2_does_not_call_init_schema(monkeypatch):
    conn = FakeConn()
    db = _db(conn)

    async def _boom():
        raise AssertionError("init_schema must not be called by init_stage2_schema")

    monkeypatch.setattr(db, "init_schema", _boom)
    _run(db.init_stage2_schema())   # must not raise


def test_init_stage2_idempotent_against_mock():
    conn = FakeConn()
    db = _db(conn)
    _run(db.init_stage2_schema())
    first = len(conn.executed)
    _run(db.init_stage2_schema())   # second run, no error
    assert len(conn.executed) == 2 * first


# -- seed methods use upsert -------------------------------------------------
def test_seed_symbols_uses_upsert():
    conn = FakeConn()
    db = _db(conn)
    n = _run(db.seed_symbols([("BTCUSDT", "BTC", "USDT", "major", "ACTIVE", True, "drain")]))
    assert n == 1
    sql = conn.executemany_calls[0][0]
    assert "INSERT INTO symbols" in sql
    assert "ON CONFLICT (symbol) DO UPDATE" in sql


def test_seed_symbol_exchange_capabilities_uses_upsert():
    conn = FakeConn()
    db = _db(conn)
    rows = [("okx", "BTCUSDT", "perp", "oi", True, False, "full", 60, True, "")]
    n = _run(db.seed_symbol_exchange_capabilities(rows))
    assert n == 1
    sql = conn.executemany_calls[0][0]
    assert "INSERT INTO symbol_exchange_capabilities" in sql
    assert "ON CONFLICT (exchange, symbol, market_type, metric) DO UPDATE" in sql


# -- instrument upsert: canonical symbol + venue id separate -----------------
def test_instrument_upsert_keeps_canonical_and_venue_id_separate():
    conn = FakeConn(fetchrow_result=None)     # no existing row
    db = _db(conn)
    _run(db.upsert_exchange_instrument(
        exchange="okx", symbol="BTCUSDT", market_type="perp",
        exchange_instrument_id="BTC-USDT-SWAP", quantity_unit="contracts",
        contract_multiplier=0.01, tick_size=0.1, price_precision=None,
        quantity_precision=None, metadata_source="exchange_api",
        fetched_at=None, is_stale=False))
    assert len(conn.executed) == 1
    sql, args = conn.executed[0]
    assert "INSERT INTO exchange_instruments" in sql
    # canonical symbol and venue instrument id are distinct arguments
    assert "BTCUSDT" in args
    assert "BTC-USDT-SWAP" in args
    assert args.index("BTCUSDT") != args.index("BTC-USDT-SWAP")


def test_instrument_mismatch_does_not_silently_overwrite():
    existing = {
        "exchange_instrument_id": "BTC-USDT-SWAP", "quantity_unit": "contracts",
        "contract_multiplier": 0.01, "tick_size": 0.1,
    }
    conn = FakeConn(fetchrow_result=existing)
    db = _db(conn)
    with pytest.raises(ValueError):
        _run(db.upsert_exchange_instrument(
            exchange="okx", symbol="BTCUSDT", market_type="perp",
            exchange_instrument_id="BTC-USDT-SWAP", quantity_unit="contracts",
            contract_multiplier=0.01, tick_size=0.2,   # tick changed
            price_precision=None, quantity_precision=None,
            metadata_source="exchange_api", fetched_at=None, is_stale=False))
    assert conn.executed == []                 # NO overwrite happened

    # deliberate acceptance performs the upsert
    _run(db.upsert_exchange_instrument(
        exchange="okx", symbol="BTCUSDT", market_type="perp",
        exchange_instrument_id="BTC-USDT-SWAP", quantity_unit="contracts",
        contract_multiplier=0.01, tick_size=0.2, price_precision=None,
        quantity_precision=None, metadata_source="exchange_api",
        fetched_at=None, is_stale=False, accept_mismatch=True))
    assert len(conn.executed) == 1


def test_instrument_contract_multiplier_mismatch_blocked():
    # LKG multiplier 0.01, caller passes 0.1 -> must be blocked at the DB layer
    existing = {
        "exchange_instrument_id": "BTC-USDT-SWAP", "quantity_unit": "contracts",
        "contract_multiplier": 0.01, "tick_size": 0.1,
    }
    conn = FakeConn(fetchrow_result=existing)
    db = _db(conn)
    with pytest.raises(ValueError):
        _run(db.upsert_exchange_instrument(
            exchange="okx", symbol="BTCUSDT", market_type="perp",
            exchange_instrument_id="BTC-USDT-SWAP", quantity_unit="contracts",
            contract_multiplier=0.1,                # changed 0.01 -> 0.1
            tick_size=0.1, price_precision=None, quantity_precision=None,
            metadata_source="exchange_api", fetched_at=None, is_stale=False))
    assert conn.executed == []                      # no silent overwrite


# -- Stage 1 methods still present/unchanged --------------------------------
def test_stage1_methods_remain_callable():
    db = Database("postgresql://unused")
    for name in ("connect", "close", "init_schema", "insert_klines",
                 "seed_capabilities", "get_capabilities", "cancel_stale_backfill_runs"):
        assert callable(getattr(db, name))
    assert SCHEMA_PATH.name == "schema.sql"    # init_schema still targets Stage 1 file
