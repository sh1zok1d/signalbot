"""
TimescaleDB access layer (asyncpg). Owns schema init + batch writers used by
both backfill/ and data_ingestion/.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence

import asyncpg

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def _split_sql_statements(sql: str) -> list[str]:
    """Split a plain-DDL script into individual statements.

    Why we don't just `conn.execute(whole_file)`: asyncpg sends a
    multi-statement string via the simple-query protocol, which Postgres runs
    as ONE implicit transaction. TimescaleDB's continuous-aggregate statements
    (`CREATE MATERIALIZED VIEW ... WITH (timescaledb.continuous)` and
    `add_continuous_aggregate_policy(...)`) cannot run inside a transaction
    block, so the whole init would fail. Executing each statement on its own
    puts every one in its own implicit transaction (autocommit), which is what
    those statements need.

    This schema is plain DDL with no dollar-quoted function bodies, so stripping
    line comments and splitting on ';' is safe here. If PL/pgSQL bodies are ever
    added, switch to a real parser.
    """
    no_comments = re.sub(r"--[^\n]*", "", sql)
    return [s.strip() for s in no_comments.split(";") if s.strip()]


class Database:
    def __init__(self, dsn: str):
        self._dsn = dsn
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self.pool = await asyncpg.create_pool(self._dsn, min_size=2, max_size=10)
        logger.info("Connected to TimescaleDB")

    async def close(self) -> None:
        """Close the pool, rolling back any in-flight work. On a normal
        shutdown pool.close() waits for connections to be released (each
        `async with pool.acquire()` block rolls back on exit). If something is
        wedged we force-terminate so we never leave server-side backends
        'idle in transaction' holding locks after SIGINT."""
        if not self.pool:
            return
        try:
            await asyncio.wait_for(self.pool.close(), timeout=5.0)
        except (asyncio.TimeoutError, Exception) as exc:  # noqa: BLE001
            logger.warning("Pool graceful close failed (%s); terminating connections", exc)
            self.pool.terminate()
        finally:
            self.pool = None

    # ---------------------------------------------------------------
    # Read helpers (used by storage/validate.py and, later, the engines)
    # ---------------------------------------------------------------
    async def fetch(self, query: str, *args) -> list[asyncpg.Record]:
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchval(self, query: str, *args):
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args)

    async def init_schema(self) -> None:
        assert self.pool is not None
        sql = SCHEMA_PATH.read_text(encoding="utf-8")
        statements = _split_sql_statements(sql)
        async with self.pool.acquire() as conn:
            # One statement per execute() => each runs in its own implicit
            # transaction. Required for the TimescaleDB continuous-aggregate
            # statements, which cannot run inside a transaction block.
            # All statements are idempotent (IF NOT EXISTS / if_not_exists),
            # so re-running init on an existing DB is a no-op.
            for stmt in statements:
                await conn.execute(stmt)
        logger.info("Schema initialized / verified (%d statements)", len(statements))

    async def seed_capabilities(self, rows: Sequence[tuple],
                                enabled_exchanges: Sequence[str] | None = None) -> int:
        """Upsert the structural exchange x metric capability registry from the
        declarative source (common/capabilities.py). Idempotent; refreshes
        coverage_type/freshness/note/enabled if the declaration or the active
        set changed. rows: (exchange, metric, live_supported,
        historical_supported, coverage_type, expected_freshness_s, note).
        `enabled_exchanges` marks which exchanges are active (None => all)."""
        if not rows:
            return 0
        assert self.pool is not None
        enabled_set = None if enabled_exchanges is None else set(enabled_exchanges)
        params = [r + ((enabled_set is None or r[0] in enabled_set),) for r in rows]
        async with self.pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO exchange_capabilities
                    (exchange, metric, live_supported, historical_supported,
                     coverage_type, expected_freshness_s, note, enabled, updated_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8, now())
                ON CONFLICT (exchange, metric) DO UPDATE SET
                    live_supported = EXCLUDED.live_supported,
                    historical_supported = EXCLUDED.historical_supported,
                    coverage_type = EXCLUDED.coverage_type,
                    expected_freshness_s = EXCLUDED.expected_freshness_s,
                    note = EXCLUDED.note,
                    enabled = EXCLUDED.enabled,
                    updated_at = now()
                """,
                params,
            )
        return len(rows)

    async def get_capabilities(self) -> list[asyncpg.Record]:
        """Read the capability registry (used by validate.py and, later, the
        signal_engine — so neither imports the WS client classes)."""
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                "SELECT exchange, metric, live_supported, historical_supported, "
                "coverage_type, expected_freshness_s, note, enabled FROM exchange_capabilities")

    # ---------------------------------------------------------------
    # Writers
    # ---------------------------------------------------------------
    async def insert_klines(self, rows: Sequence[tuple], source: str) -> int:
        """rows: (exchange, symbol, ts, open, high, low, close, volume,
        taker_buy_volume, taker_sell_volume, trades_count)"""
        if not rows:
            return 0
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO klines_1m
                    (exchange, symbol, ts, open, high, low, close, volume,
                     taker_buy_volume, taker_sell_volume, trades_count, source)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
                ON CONFLICT (exchange, symbol, ts) DO UPDATE SET
                    open = EXCLUDED.open, high = EXCLUDED.high,
                    low = EXCLUDED.low, close = EXCLUDED.close,
                    volume = EXCLUDED.volume,
                    taker_buy_volume = EXCLUDED.taker_buy_volume,
                    taker_sell_volume = EXCLUDED.taker_sell_volume,
                    trades_count = EXCLUDED.trades_count,
                    source = EXCLUDED.source
                """,
                [r + (source,) for r in rows],
            )
        return len(rows)

    async def insert_open_interest(self, rows: Sequence[tuple], source: str) -> int:
        """rows: (exchange, symbol, ts, oi_raw, oi_unit, contract_value,
        oi_base_asset, oi_notional_usd). Legacy oi_contracts/oi_notional are
        kept populated (oi_contracts=oi_raw, oi_notional=oi_notional_usd) for
        continuity, but the oi_unit-tagged columns are the authoritative ones —
        never sum oi_raw across exchanges (units differ)."""
        if not rows:
            return 0
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO open_interest
                    (exchange, symbol, ts, oi_raw, oi_unit, contract_value,
                     oi_base_asset, oi_notional_usd, oi_contracts, oi_notional, source)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$4,$8,$9)
                ON CONFLICT (exchange, symbol, ts) DO UPDATE SET
                    oi_raw = EXCLUDED.oi_raw,
                    oi_unit = EXCLUDED.oi_unit,
                    contract_value = EXCLUDED.contract_value,
                    oi_base_asset = EXCLUDED.oi_base_asset,
                    oi_notional_usd = EXCLUDED.oi_notional_usd,
                    oi_contracts = EXCLUDED.oi_contracts,
                    oi_notional = EXCLUDED.oi_notional,
                    source = EXCLUDED.source
                """,
                [r + (source,) for r in rows],
            )
        return len(rows)

    async def insert_funding(self, rows: Sequence[tuple], source: str) -> int:
        """rows: (exchange, symbol, ts, funding_rate, next_funding_time)"""
        if not rows:
            return 0
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO funding_rate (exchange, symbol, ts, funding_rate, next_funding_time, source)
                VALUES ($1,$2,$3,$4,$5,$6)
                ON CONFLICT (exchange, symbol, ts) DO UPDATE SET
                    funding_rate = EXCLUDED.funding_rate,
                    next_funding_time = EXCLUDED.next_funding_time,
                    source = EXCLUDED.source
                """,
                [r + (source,) for r in rows],
            )
        return len(rows)

    async def insert_mark_price(self, rows: Sequence[tuple], source: str) -> int:
        """rows: (exchange, symbol, ts, mark_price)"""
        if not rows:
            return 0
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO mark_price (exchange, symbol, ts, mark_price, source)
                VALUES ($1,$2,$3,$4,$5)
                ON CONFLICT (exchange, symbol, ts) DO UPDATE SET
                    mark_price = EXCLUDED.mark_price,
                    source = EXCLUDED.source
                """,
                [r + (source,) for r in rows],
            )
        return len(rows)

    async def insert_liquidations(self, rows: Sequence[tuple]) -> int:
        """rows: (exchange, symbol, ts, side, price, qty, notional, is_snapshot_feed)
        Live-only, no upsert needed (each event is unique)."""
        if not rows:
            return 0
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO liquidations
                    (exchange, symbol, ts, side, price, qty, notional, is_snapshot_feed)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                """,
                rows,
            )
        return len(rows)

    async def log_connectivity_event(self, exchange: str, event_type: str, detail: dict) -> None:
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO connectivity_events (exchange, event_type, detail) VALUES ($1,$2,$3)",
                exchange, event_type, detail,
            )

    # ---------------------------------------------------------------
    # Backfill bookkeeping
    # ---------------------------------------------------------------
    async def start_backfill_run(self, exchange: str, symbol: str, source: str,
                                  window_start: datetime, window_end: datetime) -> int:
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO backfill_runs (exchange, symbol, source, window_start, window_end)
                VALUES ($1,$2,$3,$4,$5) RETURNING id
                """,
                exchange, symbol, source, window_start, window_end,
            )
        return row["id"]

    async def finish_backfill_run(self, run_id: int, status: str, rows_written: int, note: str = "") -> None:
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE backfill_runs
                SET status=$2, rows_written=$3, finished_at=now(), note=$4
                WHERE id=$1
                """,
                run_id, status, rows_written, note,
            )

    async def cancel_stale_backfill_runs(self) -> str:
        """Any backfill_run still 'running' at startup is a leftover from a
        previous interrupted/killed process (SIGINT during backfill, crash,
        etc.) — its coro never reached finish_backfill_run. Sweep them to
        'cancelled' so bookkeeping is honest and has_complete_backfill re-runs
        them. Idempotent; safe to call on every startup. No data is touched."""
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            return await conn.execute(
                "UPDATE backfill_runs SET status='cancelled', finished_at=now(), "
                "note = coalesce(note,'') || ' [auto-cancelled: leftover running run at startup]' "
                "WHERE status='running'")

    async def has_complete_backfill(self, exchange: str, symbol: str, source: str,
                                     window_start: datetime) -> bool:
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT 1 FROM backfill_runs
                WHERE exchange=$1 AND symbol=$2 AND source=$3
                  AND window_start <= $4 AND status = 'complete'
                ORDER BY finished_at DESC LIMIT 1
                """,
                exchange, symbol, source, window_start,
            )
        return row is not None
