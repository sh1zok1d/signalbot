"""Real-Postgres proof of `Database.insert_klines`'s ON CONFLICT no-downgrade
semantics (V2-H2d, docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md §2.1b).

Deliberately NOT a FakeConn/SQL-string-inspection test (see
tests/storage/test_stage2_db.py's existing style for that layer) — the
whole point of §2.1b is real PostgreSQL `ON CONFLICT ... DO UPDATE`
row-merge behavior, which a mocked connection cannot exercise. This module
runs `insert_klines` against a REAL `klines_1m` table and reads the row
back with a real `SELECT`, asserting on actual before/after column values
— not on the SQL text sent.

Isolation (Qodo amendment, finding 2): every test runs inside its OWN
uniquely-named PostgreSQL SCHEMA, never the connection's default/shared
schema. A per-test schema is created via an unscoped "admin" connection,
then `Database` itself is connected via a DSN carrying the libpq
`options=-csearch_path=<schema>` query parameter — every connection
`asyncpg.create_pool()` opens for that DSN (including every connection
`Database.insert_klines()` internally acquires) therefore resolves the
unqualified `klines_1m` name inside that one schema, with zero production
code changes. Cleanup issues exactly one `DROP SCHEMA "<generated-name>"
CASCADE` against that same generated name — never a bare `DROP TABLE
klines_1m` against whatever schema happened to be default. A concurrently
running test process gets its own `uuid4`-suffixed schema name, so two
runs against the same server cannot collide.

Fail-vs-skip contract (Qodo amendment, finding 3): if `KLINES_TEST_DSN` is
NOT set, this suite is a best-effort local convenience — a connection
failure SKIPS (the default local DSN points at a throwaway database that
may simply not exist on a given machine). If `KLINES_TEST_DSN` IS
explicitly set (as CI now does, see .github/workflows/ci.yml), a
connection/setup failure is a genuine TEST FAILURE, never a skip — CI must
not silently pass without ever having exercised this SQL.
"""
from __future__ import annotations

import asyncio
import os
import urllib.parse
import uuid
from datetime import datetime, timezone

import asyncpg
import pytest

from storage.db import Database

_EXPLICIT_DSN = os.environ.get("KLINES_TEST_DSN")
BASE_DSN = _EXPLICIT_DSN or "postgresql://postgres:postgres@127.0.0.1:5432/signalbot_test"

_KLINES_1M_DDL = """
CREATE TABLE klines_1m (
    exchange            TEXT NOT NULL,
    symbol              TEXT NOT NULL,
    ts                  TIMESTAMPTZ NOT NULL,
    open                DOUBLE PRECISION NOT NULL,
    high                DOUBLE PRECISION NOT NULL,
    low                 DOUBLE PRECISION NOT NULL,
    close               DOUBLE PRECISION NOT NULL,
    volume              DOUBLE PRECISION NOT NULL,
    taker_buy_volume    DOUBLE PRECISION,
    taker_sell_volume   DOUBLE PRECISION,
    trades_count        INTEGER,
    source              TEXT NOT NULL DEFAULT 'backfill',
    PRIMARY KEY (exchange, symbol, ts)
);
"""
# Exact column-for-column mirror of storage/schema.sql's real klines_1m
# definition, minus the TimescaleDB `create_hypertable()` call -- ON
# CONFLICT row-merge semantics are identical on a plain table, and this
# suite must not require the timescaledb extension to be installed.
# Deliberately unqualified (no "public." / "<schema>." prefix) -- it is
# created through a search_path-scoped connection, so it lands inside
# that one connection's resolved schema, never a shared default.


def _scoped_dsn(base_dsn: str, schema: str) -> str:
    """`base_dsn` + the libpq `options=-csearch_path=<schema>` query
    parameter, merged onto whatever query string `base_dsn` already
    carries (e.g. `sslmode=...`) rather than clobbering it."""
    parts = urllib.parse.urlsplit(base_dsn)
    query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    query.append(("options", f"-csearch_path={schema}"))
    new_query = urllib.parse.urlencode(query)
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))


async def _connect_admin() -> asyncpg.Connection:
    """A plain connection to `BASE_DSN` (the caller's default/whatever
    schema `search_path` normally resolves to) -- used ONLY to create and
    later drop this test's own uniquely-named schema. Never issues any
    statement against `klines_1m` itself."""
    try:
        return await asyncpg.connect(BASE_DSN, timeout=3)
    except Exception as exc:  # noqa: BLE001 - any connection failure
        if _EXPLICIT_DSN:
            # KLINES_TEST_DSN was deliberately configured (CI) -- a
            # connection failure here is a genuine test FAILURE, not a
            # skip; CI must not silently pass without ever running this.
            raise
        pytest.skip(f"no reachable PostgreSQL test server at {BASE_DSN!r}: {exc}")
        raise AssertionError("unreachable")  # pragma: no cover - pytest.skip() always raises


def _unique_schema_name() -> str:
    return "v2h2d_test_" + uuid.uuid4().hex[:16]


async def _with_isolated_klines_table(body):
    """Create a fresh, uniquely-named schema, connect `Database` to it via
    `_scoped_dsn`, create ONE `klines_1m` table inside that schema, run
    `body(db)`, then unconditionally drop that exact schema (and nothing
    else) -- all inside the SAME event loop (asyncpg pools are bound to
    the loop that created them, so a fixture using a SEPARATE
    `asyncio.run()` call would hang trying to reuse a pool across loops)."""
    schema = _unique_schema_name()
    admin = await _connect_admin()
    try:
        await admin.execute(f'CREATE SCHEMA "{schema}"')
    finally:
        await admin.close()

    db = Database(_scoped_dsn(BASE_DSN, schema))
    await db.connect()
    try:
        async with db.pool.acquire() as conn:
            await conn.execute(_KLINES_1M_DDL)
        await body(db)
    finally:
        await db.close()
        cleanup = await _connect_admin()
        try:
            # Exactly one statement, targeting exactly the schema THIS
            # run created above -- never a bare "klines_1m" name, never
            # any other schema.
            await cleanup.execute(f'DROP SCHEMA "{schema}" CASCADE')
        finally:
            await cleanup.close()


def _ts(minute: int) -> datetime:
    return datetime(2026, 8, 19, 12, minute, tzinfo=timezone.utc)


async def _fetch_row(db: Database, *, exchange: str, symbol: str, ts: datetime) -> dict:
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM klines_1m WHERE exchange=$1 AND symbol=$2 AND ts=$3",
            exchange, symbol, ts)
    assert row is not None, "expected row to exist"
    return dict(row)


def _run(body):
    asyncio.run(_with_isolated_klines_table(body))


# ============================================================================
# 1. rich live -> poor backfill: optional fidelity fields must NOT downgrade
# ============================================================================
def test_rich_live_then_poor_backfill_does_not_downgrade_optional_fields():
    async def body(db):
        ts = _ts(0)
        live_row = ("binance", "BTCUSDT", ts, 100.0, 101.0, 99.0, 100.5, 1000.0,
                    600.0, 400.0, 50)
        await db.insert_klines([live_row], source="live")

        # A poorer backfill row for the SAME bucket (Bybit/OKX/Bitget-style:
        # taker_buy_volume/taker_sell_volume/trades_count all NULL) arrives
        # later -- e.g. a recovery/gap-fill re-run of a window live already
        # covered.
        poor_backfill_row = ("binance", "BTCUSDT", ts, 100.0, 101.0, 99.0, 100.5, 1000.0,
                              None, None, None)
        await db.insert_klines([poor_backfill_row], source="backfill")

        after = await _fetch_row(db, exchange="binance", symbol="BTCUSDT", ts=ts)
        assert after["taker_buy_volume"] == 600.0, "known live taker_buy_volume must survive"
        assert after["taker_sell_volume"] == 400.0, "known live taker_sell_volume must survive"
        assert after["trades_count"] == 50, "known live trades_count must survive"
        # The row's optional fields are still exclusively live-sourced --
        # the provenance tag must not be silently relabeled 'backfill'.
        assert after["source"] == "live"

    _run(body)


# ============================================================================
# 2. poor existing -> rich incoming: NULL must upgrade to the real value
# ============================================================================
def test_poor_existing_then_rich_incoming_upgrades_optional_fields():
    async def body(db):
        ts = _ts(1)
        poor_backfill_row = ("bybit", "BTCUSDT", ts, 200.0, 202.0, 199.0, 201.0, 500.0,
                              None, None, None)
        await db.insert_klines([poor_backfill_row], source="backfill")

        before = await _fetch_row(db, exchange="bybit", symbol="BTCUSDT", ts=ts)
        assert before["taker_buy_volume"] is None
        assert before["source"] == "backfill"

        rich_live_row = ("bybit", "BTCUSDT", ts, 200.0, 202.0, 199.0, 201.0, 500.0,
                          300.0, 200.0, 30)
        await db.insert_klines([rich_live_row], source="live")

        after = await _fetch_row(db, exchange="bybit", symbol="BTCUSDT", ts=ts)
        assert after["taker_buy_volume"] == 300.0
        assert after["taker_sell_volume"] == 200.0
        assert after["trades_count"] == 30
        assert after["source"] == "live"

    _run(body)


# ============================================================================
# 3. rich -> rich legitimate correction: a real non-null value must still
#    be able to overwrite an already-known real non-null value
# ============================================================================
def test_rich_to_rich_legitimate_correction_overwrites():
    async def body(db):
        ts = _ts(2)
        original = ("binance", "BTCUSDT", ts, 300.0, 305.0, 299.0, 304.0, 2000.0,
                    1200.0, 800.0, 100)
        await db.insert_klines([original], source="live")

        # A deliberate correction: OHLCV AND the optional fields all
        # change to different, still-real, non-null values (e.g. a later
        # authoritative backfill re-read proves the live-computed
        # aggregate was slightly off).
        corrected = ("binance", "BTCUSDT", ts, 300.1, 305.2, 298.9, 304.3, 2010.0,
                     1210.0, 800.0, 101)
        await db.insert_klines([corrected], source="backfill")

        after = await _fetch_row(db, exchange="binance", symbol="BTCUSDT", ts=ts)
        assert after["open"] == 300.1
        assert after["high"] == 305.2
        assert after["low"] == 298.9
        assert after["close"] == 304.3
        assert after["volume"] == 2010.0
        assert after["taker_buy_volume"] == 1210.0
        assert after["taker_sell_volume"] == 800.0
        assert after["trades_count"] == 101
        # incoming supplied real taker-fidelity data of its own -> trust
        # its own source label, not a stale 'live' tag
        assert after["source"] == "backfill"

    _run(body)


# ============================================================================
# 4. repeated identical backfill: idempotent, no spurious change
# ============================================================================
def test_repeated_identical_backfill_is_idempotent():
    async def body(db):
        ts = _ts(3)
        row = ("okx", "BTCUSDT", ts, 400.0, 404.0, 398.0, 402.0, 750.0, None, None, None)
        await db.insert_klines([row], source="backfill")
        first = await _fetch_row(db, exchange="okx", symbol="BTCUSDT", ts=ts)

        await db.insert_klines([row], source="backfill")
        second = await _fetch_row(db, exchange="okx", symbol="BTCUSDT", ts=ts)

        assert first == second

    _run(body)


# ============================================================================
# 5. mixed optional NULL/non-NULL fields: each of the three optional
#    columns is protected/upgraded INDEPENDENTLY of the other two
# ============================================================================
def test_mixed_optional_fields_are_protected_independently():
    async def body(db):
        ts = _ts(4)
        # stored: taker_buy_volume known, taker_sell_volume/trades_count unknown
        stored = ("binance", "BTCUSDT", ts, 500.0, 505.0, 499.0, 503.0, 900.0,
                  550.0, None, None)
        await db.insert_klines([stored], source="live")

        # incoming: taker_buy_volume NULL (must not erase 550.0), but
        # taker_sell_volume/trades_count now supplied (must upgrade)
        incoming = ("binance", "BTCUSDT", ts, 500.0, 505.0, 499.0, 503.0, 900.0,
                    None, 350.0, 40)
        await db.insert_klines([incoming], source="backfill")

        after = await _fetch_row(db, exchange="binance", symbol="BTCUSDT", ts=ts)
        assert after["taker_buy_volume"] == 550.0, "must preserve the field the incoming row omitted"
        assert after["taker_sell_volume"] == 350.0, "must upgrade the field the incoming row supplied"
        assert after["trades_count"] == 40, "must upgrade the field the incoming row supplied"
        # incoming supplied real data in 2 of the 3 optional columns ->
        # trust its own source label
        assert after["source"] == "backfill"

    _run(body)


# ============================================================================
# 6. source semantics, isolated: stored='backfill' (never 'live') is never
#    protected by the CASE guard, regardless of the incoming row's fields
# ============================================================================
def test_source_never_protected_when_stored_row_was_never_live():
    async def body(db):
        ts = _ts(5)
        stored = ("bitget", "BTCUSDT", ts, 600.0, 606.0, 598.0, 604.0, 300.0,
                  None, None, None)
        await db.insert_klines([stored], source="backfill")

        incoming_still_poor = ("bitget", "BTCUSDT", ts, 600.0, 606.0, 598.0, 604.0, 300.0,
                                None, None, None)
        await db.insert_klines([incoming_still_poor], source="backfill")

        after = await _fetch_row(db, exchange="bitget", symbol="BTCUSDT", ts=ts)
        assert after["source"] == "backfill"

    _run(body)


# ============================================================================
# 7. isolation-harness safety (Qodo amendment, finding 2): a pre-existing
# klines_1m table in the DEFAULT/shared schema this DSN normally resolves
# to (simulating a real shared/production table) must survive a full
# isolated test cycle -- setup, insert_klines calls, and cleanup --
# completely untouched: same row count, same sentinel row.
# ============================================================================
def test_isolated_harness_does_not_touch_a_preexisting_shared_klines_1m_table():
    async def scenario():
        admin = await _connect_admin()
        we_created_it = False
        try:
            existing = await admin.fetchval(
                "SELECT to_regclass('klines_1m')")
            if existing is None:
                we_created_it = True
                await admin.execute(_KLINES_1M_DDL)
                sentinel = ("sentinel-exchange", "SENTINELUSDT", _ts(59),
                            1.0, 2.0, 0.5, 1.5, 10.0, None, None, None, "backfill")
                await admin.execute(
                    """INSERT INTO klines_1m
                       (exchange, symbol, ts, open, high, low, close, volume,
                        taker_buy_volume, taker_sell_volume, trades_count, source)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)""",
                    *sentinel)
            before_count = await admin.fetchval("SELECT count(*) FROM klines_1m")
            before_rows = {tuple(r.values())
                           for r in await admin.fetch("SELECT * FROM klines_1m")}
        finally:
            await admin.close()

        # Run one full isolated cycle -- its own schema, its own
        # klines_1m, real insert_klines calls -- completely separate from
        # the "shared" table above.
        async def body(db):
            row = ("binance", "BTCUSDT", _ts(58), 1.0, 2.0, 0.5, 1.5, 10.0,
                   3.0, 2.0, 5)
            await db.insert_klines([row], source="live")

        await _with_isolated_klines_table(body)

        admin2 = await _connect_admin()
        try:
            after_count = await admin2.fetchval("SELECT count(*) FROM klines_1m")
            after_rows = {tuple(r.values())
                          for r in await admin2.fetch("SELECT * FROM klines_1m")}
            assert after_count == before_count, (
                "the shared klines_1m row count must be unchanged by an isolated test cycle")
            assert after_rows == before_rows, (
                "the shared klines_1m row CONTENTS must be byte-for-byte unchanged")
            if we_created_it:
                # disposable scaffold this test itself created for the
                # proof -- safe to remove; a table that already existed
                # before this test ran is left completely alone.
                await admin2.execute("DROP TABLE klines_1m")
        finally:
            await admin2.close()

    asyncio.run(scenario())


def test_core_isolation_helper_never_issues_a_bare_drop_against_the_default_schema():
    """Structural regression: `_with_isolated_klines_table` -- the ONE
    setup/teardown helper every no-downgrade test above routes through --
    must never contain the fixed word sequence naming a direct removal of
    the shared table by its bare name. Its only DROP statement must be
    `DROP SCHEMA "<generated-name>" CASCADE`, scoped to the dynamically-
    generated `schema` variable. (Scoped to this ONE function, not the
    whole module, because the separate harness-safety proof test above
    legitimately drops a table it created ITSELF as disposable scaffolding
    -- that is not the regression this checks for.)"""
    import inspect
    source = inspect.getsource(_with_isolated_klines_table)
    forbidden = "DROP" + " " + "TABLE" + " klines_1m"
    assert forbidden.lower() not in source.lower()
    assert 'DROP SCHEMA "{schema}"' in source
