"""Real-Postgres proof of `Database.insert_klines`'s ON CONFLICT no-downgrade
semantics (V2-H2d, docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md §2.1b).

Deliberately NOT a FakeConn/SQL-string-inspection test (see
tests/storage/test_stage2_db.py's existing style for that layer) — the
whole point of §2.1b is real PostgreSQL `ON CONFLICT ... DO UPDATE`
row-merge behavior, which a mocked connection cannot exercise. This module
runs `insert_klines` against a REAL, ephemeral `klines_1m` table and reads
the row back with a real `SELECT`, asserting on actual before/after column
values -- not on the SQL text sent.

Requires a reachable PostgreSQL server. Configure via the `KLINES_TEST_DSN`
environment variable; defaults to a local throwaway database
(`postgresql://postgres:postgres@127.0.0.1:5432/signalbot_test`, matching
this repo's existing `POSTGRES_DSN` convention in common/config.py). If no
server is reachable, every test in this module is SKIPPED (not failed) at
setup time, exactly the same posture as any other environment-dependent
integration suite -- there is no proof value in ALSO exercising this
against a FakeConn, since a fake cannot execute real SQL.

Each test runs its whole setup/body/teardown inside ONE `asyncio.run()` /
ONE event loop deliberately -- `asyncpg.Pool` (and the `Database` wrapping
it) is bound to the loop that created it, so acquiring/using it from a
DIFFERENT loop (e.g. a fixture's own separate `asyncio.run()` call) hangs
rather than raising, which is exactly why this module does not use a
pytest fixture returning an already-connected `Database`.
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone

import asyncpg
import pytest

from storage.db import Database

DSN = os.environ.get(
    "KLINES_TEST_DSN", "postgresql://postgres:postgres@127.0.0.1:5432/signalbot_test")

_KLINES_1M_DDL = """
CREATE TABLE IF NOT EXISTS klines_1m (
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


def _ts(minute: int) -> datetime:
    return datetime(2026, 8, 19, 12, minute, tzinfo=timezone.utc)


async def _fetch_row(db: Database, *, exchange: str, symbol: str, ts: datetime) -> dict:
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM klines_1m WHERE exchange=$1 AND symbol=$2 AND ts=$3",
            exchange, symbol, ts)
    assert row is not None, "expected row to exist"
    return dict(row)


async def _with_fresh_klines_table(body):
    """Connect, (re)create a fresh klines_1m table, run `body(db)`, then
    drop the table and disconnect -- all inside the SAME event loop.
    Skips the whole test (not a failure) if no server is reachable."""
    try:
        conn = await asyncpg.connect(DSN, timeout=3)
    except Exception as exc:  # noqa: BLE001 - any connection failure -> skip
        pytest.skip(f"no reachable PostgreSQL test server at {DSN!r}: {exc}")
        return
    try:
        await conn.execute("DROP TABLE IF EXISTS klines_1m")
        await conn.execute(_KLINES_1M_DDL)
    finally:
        await conn.close()

    db = Database(DSN)
    await db.connect()
    try:
        await body(db)
    finally:
        async with db.pool.acquire() as conn:
            await conn.execute("DROP TABLE IF EXISTS klines_1m")
        await db.close()


def _run(body):
    asyncio.run(_with_fresh_klines_table(body))


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
