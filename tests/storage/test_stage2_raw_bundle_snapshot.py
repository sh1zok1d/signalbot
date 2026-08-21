"""Real-PostgreSQL proof that `Database.fetch_exchange_feature_raw_bundle`'s
seven fixed reads (klines, open_interest, funding, liquidations, instrument,
liquidation capability, required_metadata_revision) observe ONE consistent
PostgreSQL snapshot -- CodeRabbit's independently-classified BLOCKER finding
on the H2c amendment round.

Under plain `READ COMMITTED` autocommit, each of the seven SELECTs could
observe a DIFFERENT snapshot: a concurrent transaction could deliberately
accept a critical metadata change (atomically committing NEW
`exchange_instruments` + a NEW history interval + a NEW
`stage2_instrument_metadata_state.required_revision`) in the gap between two
of this reader's own SELECTs, producing an internally-INCOHERENT bundle
(e.g. OLD instrument metadata paired with the NEW required revision) --
exactly the state the H2c calculation_version fork gate
(`analytics/feature_engine/input_adapter.py::assemble_exchange_feature_request`)
assumes can never happen.

The fix (`storage/db.py::Database.fetch_exchange_feature_raw_bundle`) wraps
all seven reads in one `REPEATABLE READ, readonly` transaction. This file
proves, against a REAL PostgreSQL instance with two genuinely concurrent
connections, that this transaction shape actually delivers the guarantee:

  1. `test_repeatable_read_snapshot_isolates_concurrent_critical_acceptance`
     -- connection A opens a REPEATABLE READ read-only transaction and reads
     OLD instrument metadata; connection B then independently accepts a
     critical metadata change (NEW instrument + NEW history interval + NEW
     required_revision) and COMMITS it; connection A then reads
     required_metadata_revision INSIDE THE SAME (still-open) transaction and
     must still see the OLD revision -- proving the two reads can never be
     split across the commit boundary, i.e. the returned bundle can never be
     OLD instrument + NEW required_revision.
  2. `test_fetch_raw_bundle_before_and_after_commit_never_mixes_snapshots`
     -- calls the REAL, unmodified `Database.fetch_exchange_feature_raw_bundle`
     (the actual production method, no manual interleaving) once BEFORE and
     once AFTER connection B's commit, proving the simpler "all-OLD then
     all-NEW, never mixed" halves of the same invariant.

Mirrors the established real-Postgres pattern (per-test uniquely-named
schema, one `asyncio.run()` per test, `V2_INSTRUMENT_HISTORY_TEST_DSN`
fail-vs-skip contract) from `tests/storage/test_v2_instrument_history_readers.py`,
including reusing that module's OWN `exchange_instruments`/
`exchange_instrument_history`/`stage2_instrument_metadata_state` DDL constants
directly (never a third independently-drifting copy -- see that module's
`test_hand_copied_ddl_matches_production_schema` for the parity proof against
`storage/stage2_schema.sql`). The remaining Stage 1 raw tables (klines_1m,
open_interest, funding_rate, liquidations) and `symbol_exchange_capabilities`
are hand-copied here (plain, no `create_hypertable()`), not via
`Database.init_stage2_schema()`/`init_schema()` (would attempt `CREATE
EXTENSION IF NOT EXISTS timescaledb` and `create_hypertable()` calls neither
this test nor a vanilla `postgres:16` CI image can satisfy)."""
from __future__ import annotations

import asyncio
import os
import urllib.parse
import uuid
from datetime import datetime, timedelta, timezone

import asyncpg
import pytest

from storage.db import Database
from storage.stage2_readers import (
    INSTRUMENT_SQL, REQUIRED_METADATA_REVISION_SQL, read_exchange_feature_raw_bundle,
)
# Reuse the SAME hand-copied exchange_instruments/exchange_instrument_history/
# stage2_instrument_metadata_state DDL as tests/storage/test_v2_instrument_history_readers.py
# -- ONE copy of each table definition across the whole test suite (plus the
# real storage/stage2_schema.sql), never a third independently-drifting one.
# See that module's own drift-guard test (test_hand_copied_ddl_matches_production_schema)
# for the parity proof against production.
from tests.storage.test_v2_instrument_history_readers import (
    _EXCHANGE_INSTRUMENTS_DDL, _EXCHANGE_INSTRUMENT_HISTORY_DDL,
    _STAGE2_INSTRUMENT_METADATA_STATE_DDL,
)

_EXPLICIT_DSN = os.environ.get("V2_INSTRUMENT_HISTORY_TEST_DSN")
BASE_DSN = _EXPLICIT_DSN or "postgresql://postgres:postgres@127.0.0.1:5432/signalbot_test"

UTC = timezone.utc
EXCHANGE = "binance"
SYMBOL = "BTCUSDT"
MARKET_TYPE = "perp"
T0 = datetime(2026, 8, 15, 0, 0, tzinfo=UTC)


def _t(hours: int) -> datetime:
    return T0 + timedelta(hours=hours)


# ---- minimal hand-copied DDL for every table the raw-bundle reader touches --
# (Stage 1 raw tables, plain -- no create_hypertable(), matching every other
# real-Postgres test file's own reason for hand-copying: no TimescaleDB
# dependency needed for these SELECT-only reads.)
_KLINES_1M_DDL = """
CREATE TABLE klines_1m (
    exchange TEXT NOT NULL, symbol TEXT NOT NULL, ts TIMESTAMPTZ NOT NULL,
    open DOUBLE PRECISION NOT NULL, high DOUBLE PRECISION NOT NULL,
    low DOUBLE PRECISION NOT NULL, close DOUBLE PRECISION NOT NULL,
    volume DOUBLE PRECISION NOT NULL,
    taker_buy_volume DOUBLE PRECISION, taker_sell_volume DOUBLE PRECISION,
    trades_count INTEGER, source TEXT NOT NULL DEFAULT 'backfill',
    PRIMARY KEY (exchange, symbol, ts)
);
"""

_OPEN_INTEREST_DDL = """
CREATE TABLE open_interest (
    exchange TEXT NOT NULL, symbol TEXT NOT NULL, ts TIMESTAMPTZ NOT NULL,
    oi_raw DOUBLE PRECISION, oi_unit TEXT, source TEXT NOT NULL DEFAULT 'backfill',
    PRIMARY KEY (exchange, symbol, ts)
);
"""

_FUNDING_RATE_DDL = """
CREATE TABLE funding_rate (
    exchange TEXT NOT NULL, symbol TEXT NOT NULL, ts TIMESTAMPTZ NOT NULL,
    funding_rate DOUBLE PRECISION NOT NULL, next_funding_time TIMESTAMPTZ,
    source TEXT NOT NULL DEFAULT 'backfill',
    PRIMARY KEY (exchange, symbol, ts)
);
"""

_LIQUIDATIONS_DDL = """
CREATE TABLE liquidations (
    id BIGSERIAL, exchange TEXT NOT NULL, symbol TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL, side TEXT NOT NULL,
    price DOUBLE PRECISION NOT NULL, qty DOUBLE PRECISION NOT NULL,
    notional DOUBLE PRECISION, is_snapshot_feed BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (id, ts)
);
"""

_SYMBOL_EXCHANGE_CAPABILITIES_DDL = """
CREATE TABLE symbol_exchange_capabilities (
    exchange TEXT NOT NULL, symbol TEXT NOT NULL, market_type TEXT NOT NULL DEFAULT 'perp',
    metric TEXT NOT NULL, live_supported BOOLEAN NOT NULL, historical_supported BOOLEAN NOT NULL,
    coverage_type TEXT NOT NULL, expected_freshness_s INTEGER, enabled BOOLEAN NOT NULL DEFAULT TRUE,
    note TEXT, updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (exchange, symbol, market_type, metric)
);
"""

_ALL_DDL = (
    _KLINES_1M_DDL, _OPEN_INTEREST_DDL, _FUNDING_RATE_DDL, _LIQUIDATIONS_DDL,
    _SYMBOL_EXCHANGE_CAPABILITIES_DDL, _EXCHANGE_INSTRUMENTS_DDL,
    _EXCHANGE_INSTRUMENT_HISTORY_DDL, _STAGE2_INSTRUMENT_METADATA_STATE_DDL,
)


def _scoped_dsn(base_dsn: str, schema: str) -> str:
    parts = urllib.parse.urlsplit(base_dsn)
    query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    query.append(("options", f"-csearch_path={schema}"))
    new_query = urllib.parse.urlencode(query)
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))


async def _connect_admin() -> asyncpg.Connection:
    try:
        return await asyncpg.connect(BASE_DSN, timeout=3)
    except Exception as exc:  # noqa: BLE001
        if _EXPLICIT_DSN:
            raise
        pytest.skip(f"no reachable PostgreSQL test server at {BASE_DSN!r}: {exc}")
        raise AssertionError("unreachable")  # pragma: no cover


def _unique_schema_name() -> str:
    return "s2rb_test_" + uuid.uuid4().hex[:16]


async def _with_isolated_raw_bundle_schema(body):
    """Create a fresh, uniquely-named schema with every table the raw-bundle
    reader touches, seed a first-ever instrument (tick=0.10) + bootstrap the
    revision singleton at 1, run `body(db, scoped_dsn)`, then unconditionally
    drop the schema -- all inside the SAME event loop."""
    schema = _unique_schema_name()
    admin = await _connect_admin()
    try:
        await admin.execute(f'CREATE SCHEMA "{schema}"')
    finally:
        await admin.close()

    scoped_dsn = _scoped_dsn(BASE_DSN, schema)
    db = Database(scoped_dsn)
    await db.connect()
    try:
        async with db.pool.acquire() as conn:
            for ddl in _ALL_DDL:
                await conn.execute(ddl)
        await db.bootstrap_instrument_metadata_revision(initial_revision=1)
        await db.upsert_exchange_instrument(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE,
            exchange_instrument_id=SYMBOL, quantity_unit="base",
            contract_multiplier=None, tick_size=0.10, price_precision=1,
            quantity_precision=3, metadata_source="exchange_api",
            fetched_at=_t(0), is_stale=False)
        await body(db, scoped_dsn)
    finally:
        await db.close()
        cleanup = await _connect_admin()
        try:
            await cleanup.execute(f'DROP SCHEMA "{schema}" CASCADE')
        finally:
            await cleanup.close()


def _run(body):
    asyncio.run(_with_isolated_raw_bundle_schema(body))


async def _accept_critical_change(db, *, tick_size, target_metadata_revision, effective_from):
    await db.upsert_exchange_instrument(
        exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE,
        exchange_instrument_id=SYMBOL, quantity_unit="base",
        contract_multiplier=None, tick_size=tick_size, price_precision=1,
        quantity_precision=3, metadata_source="exchange_api",
        fetched_at=effective_from, is_stale=False, accept_mismatch=True,
        effective_from=effective_from, target_metadata_revision=target_metadata_revision)


# ============================================================================
# 1. The core snapshot-coherence proof: a REPEATABLE READ read-only
# transaction's two relevant reads (instrument, required_metadata_revision)
# can NEVER be split across a concurrent commit -- the exact invariant
# storage/db.py::Database.fetch_exchange_feature_raw_bundle now relies on.
# ============================================================================
def test_repeatable_read_snapshot_isolates_concurrent_critical_acceptance():
    async def body(db, scoped_dsn):
        conn_a = await asyncpg.connect(scoped_dsn)
        try:
            tx = conn_a.transaction(isolation="repeatable_read", readonly=True)
            await tx.start()
            try:
                # Connection A's FIRST read inside the snapshot: OLD instrument.
                inst_row = await conn_a.fetchrow(
                    INSTRUMENT_SQL, EXCHANGE, SYMBOL, MARKET_TYPE)
                assert inst_row["tick_size"] == 0.10

                # Connection B independently, fully, and SUCCESSFULLY accepts
                # a critical metadata change WHILE A's transaction is still
                # open -- a completely separate connection/transaction.
                await _accept_critical_change(
                    db, tick_size=0.50, target_metadata_revision=2,
                    effective_from=_t(12))
                async with db.pool.acquire() as verify_conn:
                    committed = await verify_conn.fetchrow(
                        "SELECT tick_size FROM exchange_instruments "
                        "WHERE exchange=$1 AND symbol=$2 AND market_type=$3",
                        EXCHANGE, SYMBOL, MARKET_TYPE)
                assert committed["tick_size"] == 0.50   # B's change really did commit

                # Connection A's SECOND read, INSIDE THE SAME still-open
                # transaction -- must still see the OLD revision, proving the
                # two reads were never split across B's commit boundary.
                revision_row = await conn_a.fetchrow(REQUIRED_METADATA_REVISION_SQL)
                assert revision_row["required_revision"] == 1

                # And re-reading the instrument again, still inside A's
                # transaction, must ALSO still be OLD -- the whole snapshot is
                # frozen, not just the first read.
                inst_row_again = await conn_a.fetchrow(
                    INSTRUMENT_SQL, EXCHANGE, SYMBOL, MARKET_TYPE)
                assert inst_row_again["tick_size"] == 0.10
            finally:
                await tx.commit()   # read-only transaction; commit just ends it

            # A FRESH read (new transaction) now correctly sees the NEW,
            # fully-committed state -- both instrument AND revision together.
            async with db.pool.acquire() as conn:
                fresh_inst = await conn.fetchrow(
                    INSTRUMENT_SQL, EXCHANGE, SYMBOL, MARKET_TYPE)
                fresh_revision = await conn.fetchrow(REQUIRED_METADATA_REVISION_SQL)
            assert fresh_inst["tick_size"] == 0.50
            assert fresh_revision["required_revision"] == 2
        finally:
            await conn_a.close()

    _run(body)


# ============================================================================
# 2. The real, unmodified production method, called twice (before/after a
# concurrent commit, no manual interleaving) -- proves the simpler
# "all-OLD then all-NEW, never mixed" halves of the same invariant using the
# EXACT code path Stage 2 feature computation actually calls.
# ============================================================================
def test_fetch_raw_bundle_before_and_after_commit_never_mixes_snapshots():
    async def body(db, _dsn):
        bundle_before = await db.fetch_exchange_feature_raw_bundle(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE,
            bucket_start=_t(0), bucket_end=_t(1))
        assert bundle_before.instrument["tick_size"] == 0.10
        assert bundle_before.required_metadata_revision == 1

        await _accept_critical_change(
            db, tick_size=0.50, target_metadata_revision=2, effective_from=_t(12))

        bundle_after = await db.fetch_exchange_feature_raw_bundle(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE,
            bucket_start=_t(0), bucket_end=_t(1))
        assert bundle_after.instrument["tick_size"] == 0.50
        assert bundle_after.required_metadata_revision == 2
        # never a mixed OLD/NEW combination in either bundle
        old_pair = (bundle_before.instrument["tick_size"], bundle_before.required_metadata_revision)
        new_pair = (bundle_after.instrument["tick_size"], bundle_after.required_metadata_revision)
        assert old_pair == (0.10, 1)
        assert new_pair == (0.50, 2)

    _run(body)
