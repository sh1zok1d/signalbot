"""Stage 2 Database methods against a mocked pool/connection (no real DB)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from storage.db import Database, SCHEMA_PATH, STAGE2_SCHEMA_PATH

UTC = timezone.utc


class _NoOpTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakeConn:
    def __init__(self, fetchrow_result=None, revision_row=None, fetch_result=None):
        self.executed: list[tuple] = []
        self.executemany_calls: list[tuple] = []
        self.fetch_calls: list[tuple] = []
        self.fetchrow_result = fetchrow_result
        # (V2-H2e) raw writers now issue one `conn.fetch(...)` (an
        # unnest-based multi-row INSERT ... RETURNING) instead of
        # `executemany` -- defaults to "nothing was a correction" so
        # existing tests that don't care about DIRTY-marking need no
        # changes beyond this default.
        self.fetch_result = fetch_result if fetch_result is not None else []
        # (Tech-lead review 4991738511) `stage2_instrument_metadata_state`
        # is a SEPARATE table from `exchange_instruments`/
        # `exchange_instrument_history` -- routed to its own canned value
        # (defaulting to a live singleton at revision 1) rather than reusing
        # `fetchrow_result`, since several tests deliberately need the
        # LATTER to be None (no existing LKG/history row) while still
        # needing a REAL singleton row for the former.
        self.revision_row = revision_row if revision_row is not None else {"required_revision": 1}

    async def execute(self, sql, *args):
        self.executed.append((sql, args))
        return "OK"

    async def executemany(self, sql, rows):
        self.executemany_calls.append((sql, list(rows)))

    async def fetchrow(self, sql, *args):
        if "stage2_instrument_metadata_state" in sql:
            return self.revision_row
        return self.fetchrow_result

    async def fetchval(self, sql, *args):
        # (V2-H3 Blocker 2) _harden_v2_episode_events_id_constraints()
        # probes pg_constraint before ever issuing an ALTER TABLE --
        # default to "already present" so these mocked-pool tests exercise
        # the idempotent, already-hardened no-op path (matching a fresh
        # database, whose CREATE TABLE already added both constraints
        # inline); the real ALTER-TABLE-issuing branch is proven for real
        # in tests/storage/test_v2_episode_event_id_constraint_upgrade.py.
        if "pg_constraint" in sql:
            return 1
        return None

    async def fetch(self, sql, *args):
        self.fetch_calls.append((sql, args))
        if "market_type" in sql and "exchange_instruments" in sql:
            return []
        return self.fetch_result

    def transaction(self):
        # (V2-H2c) upsert_exchange_instrument() now runs inside
        # conn.transaction() -- a plain no-op async context manager here
        # is sufficient for these mocked-pool tests; real transactional
        # atomicity is proven for real in
        # tests/storage/test_v2_instrument_history_readers.py.
        return _NoOpTransaction()


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
def _inserts(conn, table: str) -> list:
    """Every `conn.executed` entry that actually INSERTs into `table` --
    filters out the (V2-H2c) transaction-scoped advisory-lock `execute()`
    call, which is not an insert at all."""
    return [(sql, args) for sql, args in conn.executed if f"INSERT INTO {table}" in sql]


def test_instrument_upsert_keeps_canonical_and_venue_id_separate():
    conn = FakeConn(fetchrow_result=None)     # no existing row
    db = _db(conn)
    _run(db.upsert_exchange_instrument(
        exchange="okx", symbol="BTCUSDT", market_type="perp",
        exchange_instrument_id="BTC-USDT-SWAP", quantity_unit="contracts",
        contract_multiplier=0.01, tick_size=0.1, price_precision=None,
        quantity_precision=None, metadata_source="exchange_api",
        fetched_at=None, is_stale=False))
    inserts = _inserts(conn, "exchange_instruments")
    assert len(inserts) == 1
    sql, args = inserts[0]
    assert "INSERT INTO exchange_instruments" in sql
    # canonical symbol and venue instrument id are distinct arguments
    assert "BTCUSDT" in args
    assert "BTC-USDT-SWAP" in args
    assert args.index("BTCUSDT") != args.index("BTC-USDT-SWAP")
    # fetched_at=None -- no history interval opened either (nothing honest
    # to record an effective_from from).
    assert _inserts(conn, "exchange_instrument_history") == []


# -- instrument upsert: history append (V2-H2c) ------------------------------
def test_instrument_upsert_with_fetched_at_opens_first_history_interval():
    conn = FakeConn(fetchrow_result=None)     # no existing row/interval at all
    db = _db(conn)
    observed_at = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
    _run(db.upsert_exchange_instrument(
        exchange="binance", symbol="BTCUSDT", market_type="perp",
        exchange_instrument_id="BTCUSDT", quantity_unit="base", contract_multiplier=None,
        tick_size=0.1, price_precision=1, quantity_precision=3,
        metadata_source="exchange_api", fetched_at=observed_at, is_stale=False))
    inserts = _inserts(conn, "exchange_instrument_history")
    assert len(inserts) == 1
    sql, args = inserts[0]
    assert observed_at in args   # observed_at/effective_from both == fetched_at
    # no prior open interval -- no UPDATE ... effective_until either.
    assert not any("UPDATE exchange_instrument_history" in sql for sql, _ in conn.executed)


def test_instrument_upsert_unchanged_values_opens_no_extra_history_interval():
    same_row = {
        "exchange_instrument_id": "BTC-USDT-SWAP", "quantity_unit": "contracts",
        "contract_multiplier": 0.01, "tick_size": 0.1,
        "price_precision": None, "quantity_precision": None,
        "effective_from": datetime(2026, 8, 1, tzinfo=UTC),
    }
    conn = FakeConn(fetchrow_result=same_row)
    db = _db(conn)
    _run(db.upsert_exchange_instrument(
        exchange="okx", symbol="BTCUSDT", market_type="perp",
        exchange_instrument_id="BTC-USDT-SWAP", quantity_unit="contracts",
        contract_multiplier=0.01, tick_size=0.1, price_precision=None,
        quantity_precision=None, metadata_source="exchange_api",
        fetched_at=datetime(2026, 8, 15, tzinfo=UTC), is_stale=False))
    # identical value fields -- idempotent refresh, no new/closed interval.
    assert _inserts(conn, "exchange_instrument_history") == []
    assert not any("UPDATE exchange_instrument_history" in sql for sql, _ in conn.executed)


def test_instrument_upsert_accepted_change_closes_old_and_opens_new_interval():
    old_row = {
        "exchange_instrument_id": "BTC-USDT-SWAP", "quantity_unit": "contracts",
        "contract_multiplier": 0.01, "tick_size": 0.1,
        "price_precision": None, "quantity_precision": None,
        "effective_from": datetime(2026, 8, 1, tzinfo=UTC),
    }
    conn = FakeConn(fetchrow_result=old_row)   # default revision_row: required_revision=1
    db = _db(conn)
    new_fetched_at = datetime(2026, 8, 15, tzinfo=UTC)
    _run(db.upsert_exchange_instrument(
        exchange="okx", symbol="BTCUSDT", market_type="perp",
        exchange_instrument_id="BTC-USDT-SWAP", quantity_unit="contracts",
        contract_multiplier=0.01, tick_size=0.2,          # changed
        price_precision=None, quantity_precision=None,
        metadata_source="exchange_api", fetched_at=new_fetched_at, is_stale=False,
        accept_mismatch=True, effective_from=new_fetched_at,
        target_metadata_revision=2))
    closes = [(sql, args) for sql, args in conn.executed
              if "UPDATE exchange_instrument_history" in sql]
    opens = _inserts(conn, "exchange_instrument_history")
    bumps = [(sql, args) for sql, args in conn.executed
             if "UPDATE stage2_instrument_metadata_state" in sql]
    assert len(closes) == 1 and new_fetched_at in closes[0][1]
    assert len(opens) == 1 and new_fetched_at in opens[0][1]
    assert len(bumps) == 1 and bumps[0][1] == (2,)


def test_instrument_upsert_fetched_at_none_never_touches_history():
    conn = FakeConn(fetchrow_result=None)
    db = _db(conn)
    _run(db.upsert_exchange_instrument(
        exchange="binance", symbol="BTCUSDT", market_type="perp",
        exchange_instrument_id="BTCUSDT", quantity_unit="base", contract_multiplier=None,
        tick_size=0.1, price_precision=None, quantity_precision=None,
        metadata_source="manual", fetched_at=None, is_stale=False))
    assert not any("exchange_instrument_history" in sql for sql, _ in conn.executed)


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
    assert _inserts(conn, "exchange_instruments") == []   # NO overwrite happened

    # deliberate acceptance performs the upsert
    _run(db.upsert_exchange_instrument(
        exchange="okx", symbol="BTCUSDT", market_type="perp",
        exchange_instrument_id="BTC-USDT-SWAP", quantity_unit="contracts",
        contract_multiplier=0.01, tick_size=0.2, price_precision=None,
        quantity_precision=None, metadata_source="exchange_api",
        fetched_at=None, is_stale=False, accept_mismatch=True,
        target_metadata_revision=2))
    assert len(_inserts(conn, "exchange_instruments")) == 1


def test_instrument_critical_accept_without_target_revision_raises():
    existing = {
        "exchange_instrument_id": "BTC-USDT-SWAP", "quantity_unit": "contracts",
        "contract_multiplier": 0.01, "tick_size": 0.1,
    }
    conn = FakeConn(fetchrow_result=existing)
    db = _db(conn)
    with pytest.raises(ValueError, match="target_metadata_revision"):
        _run(db.upsert_exchange_instrument(
            exchange="okx", symbol="BTCUSDT", market_type="perp",
            exchange_instrument_id="BTC-USDT-SWAP", quantity_unit="contracts",
            contract_multiplier=0.01, tick_size=0.2, price_precision=None,
            quantity_precision=None, metadata_source="exchange_api",
            fetched_at=None, is_stale=False, accept_mismatch=True))
    assert _inserts(conn, "exchange_instruments") == []


def test_instrument_critical_accept_reusing_current_revision_raises():
    existing = {
        "exchange_instrument_id": "BTC-USDT-SWAP", "quantity_unit": "contracts",
        "contract_multiplier": 0.01, "tick_size": 0.1,
    }
    conn = FakeConn(fetchrow_result=existing, revision_row={"required_revision": 3})
    db = _db(conn)
    with pytest.raises(ValueError, match="not strictly greater"):
        _run(db.upsert_exchange_instrument(
            exchange="okx", symbol="BTCUSDT", market_type="perp",
            exchange_instrument_id="BTC-USDT-SWAP", quantity_unit="contracts",
            contract_multiplier=0.01, tick_size=0.2, price_precision=None,
            quantity_precision=None, metadata_source="exchange_api",
            fetched_at=None, is_stale=False, accept_mismatch=True,
            effective_from=datetime(2026, 8, 15, tzinfo=UTC),
            target_metadata_revision=3))   # reuses the current value -- rejected
    assert _inserts(conn, "exchange_instruments") == []


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
    assert _inserts(conn, "exchange_instruments") == []   # no silent overwrite


# -- Stage 1 methods still present/unchanged --------------------------------
def test_stage1_methods_remain_callable():
    db = Database("postgresql://unused")
    for name in ("connect", "close", "init_schema", "insert_klines",
                 "seed_capabilities", "get_capabilities", "cancel_stale_backfill_runs"):
        assert callable(getattr(db, name))
    assert SCHEMA_PATH.name == "schema.sql"    # init_schema still targets Stage 1 file


# -- insert_klines conflict-clause shape (V2-H2d, §2.1b) --------------------
# A fast, DB-less sanity check that the SQL sent actually uses the intended
# per-column conflict clauses -- the REAL proof of the no-downgrade
# behavior is tests/storage/test_klines_no_downgrade.py's real-Postgres
# before/after row assertions; this only guards against the SQL text
# itself silently regressing back to a blanket EXCLUDED.* overwrite.
def test_insert_klines_conflict_clause_coalesces_optional_fields_not_ohlcv():
    conn = FakeConn()
    db = _db(conn)
    row = ("binance", "BTCUSDT", "2026-08-19T12:00:00Z", 1.0, 2.0, 0.5, 1.5, 100.0,
           None, None, None)
    _run(db.insert_klines([row], source="backfill"))
    assert len(conn.fetch_calls) == 1
    sql, _args = conn.fetch_calls[0]
    normalized_sql = " ".join(sql.split())  # collapse whitespace/newlines for substring checks
    # OHLCV: unconditional EXCLUDED.* overwrite (no downgrade risk -- these
    # columns are NOT NULL from every source).
    for col in ("open", "high", "low", "close", "volume"):
        assert f"{col} = EXCLUDED.{col}" in normalized_sql, (
            f"{col} must be unconditionally overwritten")
    # Optional fidelity fields: COALESCE(EXCLUDED.x, klines_1m.x) -- never
    # a blanket EXCLUDED.x overwrite.
    for col in ("taker_buy_volume", "taker_sell_volume", "trades_count"):
        assert f"{col} = EXCLUDED.{col}" not in normalized_sql, (
            f"{col} must NOT be unconditionally overwritten (no-downgrade)")
        assert f"COALESCE(EXCLUDED.{col}, klines_1m.{col})" in normalized_sql
    # source: CASE-guarded, never a blanket EXCLUDED.source overwrite.
    assert "source = EXCLUDED.source" not in normalized_sql
    assert "CASE" in normalized_sql and "klines_1m.source = 'live'" in normalized_sql
