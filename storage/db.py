"""
TimescaleDB access layer (asyncpg). Owns schema init + batch writers used by
both backfill/ and data_ingestion/.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Iterable, Mapping, Optional, Sequence

import asyncpg

if TYPE_CHECKING:  # annotation-only; keeps Stage 2 analytics out of Stage 1 startup
    from analytics.data_quality.models import DataHealthSnapshot
    from analytics.feature_engine.consensus_models import ConsensusFeatureVector
    from analytics.feature_engine.models import ExchangeFeatureVector
    from analytics.forecasting.outcomes import ForecastOutcome
    from analytics.forecasting.persistence import ForecastPrediction
    from analytics.forecasting_v2.events import V2EpisodeEvent
    from analytics.percentile_engine.models import PercentileSnapshot
    from storage.stage2_readers import ExchangeFeatureRawBundle
    from storage.stage2_serialization import Stage2WriterSpec

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"
STAGE2_SCHEMA_PATH = Path(__file__).resolve().parent / "stage2_schema.sql"

# Critical instrument-metadata fields whose change must NOT silently overwrite a
# stored row (mirrors common.instrument_metadata.CRITICAL_FIELDS; duplicated as a
# plain literal so db.py needs no import of the Stage 2 module).
_INSTRUMENT_CRITICAL_FIELDS = (
    "exchange_instrument_id", "quantity_unit", "contract_multiplier", "tick_size")


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

    # ===============================================================
    # Stage 2 (ADDITIVE). All of this is gated behind stage2.enabled by the
    # caller and is NEVER invoked from connect()/init_schema() or any Stage 1
    # path — with stage2.enabled=false Stage 1 does not touch these at all.
    # ===============================================================
    async def init_stage2_schema(self) -> None:
        """Apply storage/stage2_schema.sql (the Stage 2 tables). Separate file,
        same statement-splitting/per-statement autocommit pattern as
        init_schema() (needed for create_hypertable, which cannot run inside a
        transaction block). Idempotent; must be called EXPLICITLY — it is not
        wired into connect() or init_schema()."""
        assert self.pool is not None
        sql = STAGE2_SCHEMA_PATH.read_text(encoding="utf-8")
        statements = _split_sql_statements(sql)
        async with self.pool.acquire() as conn:
            for stmt in statements:
                await conn.execute(stmt)
        logger.info("Stage 2 schema initialized / verified (%d statements)", len(statements))

    async def fetch_exchange_feature_raw_bundle(
        self, *, exchange: str, symbol: str, market_type: str,
        bucket_start: datetime, bucket_end: datetime,
    ) -> "ExchangeFeatureRawBundle":
        """Read-only: fetch the fixed raw inputs for ONE ExchangeFeatureRequest
        (one exchange/symbol/market_type/bucket) and return an immutable,
        connection-independent bundle. Arguments are validated BEFORE a
        connection is acquired; all six reads run on a single acquired
        connection. No analytics, no writes, no wall clock. SQL lives in
        storage/stage2_readers.py (static/trusted)."""
        from storage.stage2_readers import (  # local import: no analytics coupling
            read_exchange_feature_raw_bundle, validate_raw_bundle_args)
        validate_raw_bundle_args(exchange=exchange, symbol=symbol,
                                 market_type=market_type, bucket_start=bucket_start,
                                 bucket_end=bucket_end)
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            return await read_exchange_feature_raw_bundle(
                conn, exchange=exchange, symbol=symbol, market_type=market_type,
                bucket_start=bucket_start, bucket_end=bucket_end)

    async def seed_symbols(self, rows: Sequence[tuple]) -> int:
        """Upsert the symbol registry. rows: (symbol, base_asset, quote_asset,
        asset_tier, status, enabled, disable_policy). Idempotent."""
        if not rows:
            return 0
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO symbols
                    (symbol, base_asset, quote_asset, asset_tier, status,
                     enabled, disable_policy, updated_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7, now())
                ON CONFLICT (symbol) DO UPDATE SET
                    base_asset = EXCLUDED.base_asset,
                    quote_asset = EXCLUDED.quote_asset,
                    asset_tier = EXCLUDED.asset_tier,
                    status = EXCLUDED.status,
                    enabled = EXCLUDED.enabled,
                    disable_policy = EXCLUDED.disable_policy,
                    updated_at = now()
                """,
                rows,
            )
        return len(rows)

    async def seed_symbol_exchange_capabilities(self, rows: Sequence[tuple]) -> int:
        """Upsert per-(exchange, symbol, market_type, metric) capabilities.
        rows: (exchange, symbol, market_type, metric, live_supported,
        historical_supported, coverage_type, expected_freshness_s, enabled,
        note). Idempotent."""
        if not rows:
            return 0
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO symbol_exchange_capabilities
                    (exchange, symbol, market_type, metric, live_supported,
                     historical_supported, coverage_type, expected_freshness_s,
                     enabled, note, updated_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10, now())
                ON CONFLICT (exchange, symbol, market_type, metric) DO UPDATE SET
                    live_supported = EXCLUDED.live_supported,
                    historical_supported = EXCLUDED.historical_supported,
                    coverage_type = EXCLUDED.coverage_type,
                    expected_freshness_s = EXCLUDED.expected_freshness_s,
                    enabled = EXCLUDED.enabled,
                    note = EXCLUDED.note,
                    updated_at = now()
                """,
                rows,
            )
        return len(rows)

    async def get_exchange_instrument(self, exchange: str, symbol: str,
                                      market_type: str = "perp"):
        """Read one instrument row (canonical symbol + venue id kept separate),
        or None."""
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT * FROM exchange_instruments "
                "WHERE exchange=$1 AND symbol=$2 AND market_type=$3",
                exchange, symbol, market_type)

    async def upsert_exchange_instrument(
        self, *, exchange: str, symbol: str, market_type: str = "perp",
        exchange_instrument_id: str, quantity_unit, contract_multiplier,
        tick_size, price_precision, quantity_precision, metadata_source: str,
        fetched_at, is_stale: bool = False, note: str = "",
        accept_mismatch: bool = False,
    ) -> str:
        """Upsert an instrument row. The canonical `symbol` and the venue-native
        `exchange_instrument_id` are stored in SEPARATE columns. Stale flag and
        provenance are stored explicitly.

        A change on a critical field (exchange_instrument_id, quantity_unit,
        contract_multiplier, tick_size) versus the existing row is NOT silently
        overwritten: unless `accept_mismatch=True`, this raises so the change is
        a deliberate decision (and forks calculation_version upstream)."""
        assert self.pool is not None
        new_vals = {
            "exchange_instrument_id": exchange_instrument_id,
            "quantity_unit": quantity_unit,
            "contract_multiplier": contract_multiplier,
            "tick_size": tick_size,
        }
        existing = await self.get_exchange_instrument(exchange, symbol, market_type)
        if existing is not None and not accept_mismatch:
            diff = [f for f in _INSTRUMENT_CRITICAL_FIELDS if existing[f] != new_vals[f]]
            if diff:
                raise ValueError(
                    f"instrument metadata mismatch on {diff} for "
                    f"{exchange}/{symbol}/{market_type}; refusing silent overwrite "
                    f"(pass accept_mismatch=True to accept deliberately)")
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO exchange_instruments
                    (exchange, symbol, market_type, exchange_instrument_id,
                     quantity_unit, contract_multiplier, tick_size,
                     price_precision, quantity_precision, metadata_source,
                     fetched_at, is_stale, note, updated_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13, now())
                ON CONFLICT (exchange, symbol, market_type) DO UPDATE SET
                    exchange_instrument_id = EXCLUDED.exchange_instrument_id,
                    quantity_unit = EXCLUDED.quantity_unit,
                    contract_multiplier = EXCLUDED.contract_multiplier,
                    tick_size = EXCLUDED.tick_size,
                    price_precision = EXCLUDED.price_precision,
                    quantity_precision = EXCLUDED.quantity_precision,
                    metadata_source = EXCLUDED.metadata_source,
                    fetched_at = EXCLUDED.fetched_at,
                    is_stale = EXCLUDED.is_stale,
                    note = EXCLUDED.note,
                    updated_at = now()
                """,
                exchange, symbol, market_type, exchange_instrument_id,
                quantity_unit, contract_multiplier, tick_size,
                price_precision, quantity_precision, metadata_source,
                fetched_at, is_stale, note,
            )
        return "OK"

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

    # ---------------------------------------------------------------
    # Stage 2 output writers. Two disciplines:
    #   * DERIVED feature snapshots (the four upsert_* methods below) — a
    #     correction-friendly upsert: ON CONFLICT (…, calculation_version)
    #     DO UPDATE refreshes the derived values and stamps computed_at=now(), so
    #     a deterministic replay keeps one logical row and a legitimate late-data
    #     correction updates it.
    #   * FORECAST PREDICTIONS (insert_forecast_prediction) — an immutable
    #     insert-once EVENT: INSERT ... ON CONFLICT DO NOTHING. A stored prediction
    #     is historical truth; late data must NOT rewrite it, so it is never routed
    #     through _upsert_stage2.
    # All read no raw market data and are never called from connect()/init_schema().
    # The serialization bridge is imported lazily so Stage 1 startup never eagerly
    # pulls in the Stage 2 analytics packages.
    # ---------------------------------------------------------------
    async def _upsert_stage2(self, spec: "Stage2WriterSpec",
                             rows: Sequence) -> int:
        """Shared batch upsert. The batch container + every row are validated and
        serialized FIRST (raising before any pool assertion, acquire, or DB call),
        so a malformed container / wrong type can never partially write. An empty
        (but valid) list/tuple returns 0 without acquiring a connection. The
        returned count comes from the validated parameters — there is no
        post-write `len(rows)` path that could fail after the executemany."""
        from storage.stage2_serialization import serialize_batch
        params = serialize_batch(spec, rows)   # container + whole-batch validation
        if not params:
            return 0
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            await conn.executemany(spec.insert_sql, params)
        return len(params)

    async def upsert_exchange_feature_vectors(
        self, rows: "Sequence[ExchangeFeatureVector]") -> int:
        from storage.stage2_serialization import EXCHANGE_FEATURE_SPEC
        return await self._upsert_stage2(EXCHANGE_FEATURE_SPEC, rows)

    async def upsert_consensus_feature_vectors(
        self, rows: "Sequence[ConsensusFeatureVector]") -> int:
        from storage.stage2_serialization import CONSENSUS_FEATURE_SPEC
        return await self._upsert_stage2(CONSENSUS_FEATURE_SPEC, rows)

    async def upsert_percentile_snapshots(
        self, rows: "Sequence[PercentileSnapshot]") -> int:
        from storage.stage2_serialization import PERCENTILE_SNAPSHOT_SPEC
        return await self._upsert_stage2(PERCENTILE_SNAPSHOT_SPEC, rows)

    async def upsert_data_health_snapshots(
        self, rows: "Sequence[DataHealthSnapshot]") -> int:
        from storage.stage2_serialization import DATA_HEALTH_SNAPSHOT_SPEC
        return await self._upsert_stage2(DATA_HEALTH_SNAPSHOT_SPEC, rows)

    async def insert_forecast_prediction(self, row: "ForecastPrediction") -> bool:
        """Insert ONE immutable forecast prediction as an event. Validates +
        serializes before acquiring a connection, then runs exactly one
        INSERT ... ON CONFLICT DO NOTHING RETURNING TRUE. Returns True on a first
        insert and False on a duplicate logical identity; it never overwrites a
        prior prediction (no _upsert_stage2, no DO UPDATE) and never reads back.
        DB exceptions propagate unchanged."""
        from storage.stage2_serialization import FORECAST_PREDICTION_SPEC, serialize_batch
        params = serialize_batch(FORECAST_PREDICTION_SPEC, (row,))[0]  # validation before any DB call
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            inserted = await conn.fetchval(FORECAST_PREDICTION_SPEC.insert_sql, *params)
        return inserted is True

    async def upsert_forecast_outcomes(
        self, rows: "Sequence[ForecastOutcome]") -> int:
        """Correction-friendly upsert of DERIVED forecast outcomes. Unlike the
        immutable insert_forecast_prediction event, an outcome measures future raw
        bars, so a corrected/filled bar may legitimately correct it — routed
        through the shared ON CONFLICT DO UPDATE path (computed_at=now())."""
        from storage.stage2_serialization import FORECAST_OUTCOME_SPEC
        return await self._upsert_stage2(FORECAST_OUTCOME_SPEC, rows)

    # ---------------------------------------------------------------
    # V2 (Multi-model Framework, ADDITIVE). Immutable episode-event
    # persistence boundary only (docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md
    # §2.1) — this method does NOT decide when an event should exist, what
    # state an episode transitions to, or how any detector value is
    # computed; it validates and stores an already-decided V2EpisodeEvent.
    # NOT called from connect()/init_schema()/init_stage2_schema(), and NOT
    # wired into any runtime path in this PR — v2.enabled has no bearing on
    # whether this method exists, only on whether anything ever calls it.
    # ---------------------------------------------------------------
    async def insert_v2_episode_events(
        self, rows: "Sequence[V2EpisodeEvent]") -> int:
        """Batch insert-once write for immutable V2 episode events. The whole
        batch is validated and serialized BEFORE any connection is acquired
        (same discipline as `_upsert_stage2`/`insert_forecast_prediction`), so
        a malformed container or a wrong-typed row can never partially write.
        An empty (but valid) list/tuple returns 0 without acquiring a
        connection.

        Each row is inserted with its own
        `ON CONFLICT (run_kind, run_id, event_id) DO NOTHING RETURNING TRUE`
        — the returned count is an HONEST count of rows actually inserted; a
        duplicate `(run_kind, run_id, event_id)` is silently skipped, never
        overwritten, and not counted. Rows are inserted one at a time (not
        `executemany`) specifically so each row's own TRUE/NULL RETURNING
        result is observable — `executemany` would only tell us the batch
        ran, not which rows were duplicates. There is no `DO UPDATE` path for
        this table anywhere in this codebase; historical event truth is
        immutable. DB exceptions propagate unchanged."""
        from storage.v2_serialization import V2_EPISODE_EVENT_SPEC, serialize_batch
        params = serialize_batch(V2_EPISODE_EVENT_SPEC, rows)  # validation before any DB call
        if not params:
            return 0
        assert self.pool is not None
        inserted = 0
        async with self.pool.acquire() as conn:
            for row_params in params:
                result = await conn.fetchval(V2_EPISODE_EVENT_SPEC.insert_sql, *row_params)
                if result is True:
                    inserted += 1
        return inserted

    # ---------------------------------------------------------------
    # V2 aligned-input readers (Stage 3 — Multi-timeframe Alignment PR 2,
    # ADDITIVE, READ-ONLY). Delegates all SQL/row-parsing to
    # storage/v2_alignment_readers.py; arguments are validated BEFORE a
    # connection is acquired. No analytics decision is made here — these
    # wrappers exist to return exactly the requested Stage 2 identity, or
    # an explicit absence, never a wall-clock "latest".
    # ---------------------------------------------------------------
    async def fetch_v2_consensus_feature(
        self, *, symbol: str, market_type: str, timeframe: str,
        bucket_ts: datetime, calculation_version: str,
    ) -> "Optional[Mapping]":
        """Read-only: the ONE `consensus_feature_vectors` row at the EXACT
        `(symbol, market_type, timeframe, bucket_ts, calculation_version)`
        identity, or `None` if absent — never an older bucket. See
        `storage/v2_alignment_readers.py::read_v2_consensus_feature` for
        the full contract."""
        from storage.v2_alignment_readers import (
            read_v2_consensus_feature, validate_consensus_feature_args)
        validate_consensus_feature_args(
            symbol=symbol, market_type=market_type, timeframe=timeframe,
            bucket_ts=bucket_ts, calculation_version=calculation_version)
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            return await read_v2_consensus_feature(
                conn, symbol=symbol, market_type=market_type, timeframe=timeframe,
                bucket_ts=bucket_ts, calculation_version=calculation_version)

    async def fetch_v2_consensus_percentiles(
        self, *, symbol: str, market_type: str, timeframe: str,
        bucket_ts: datetime, calculation_version: str,
    ) -> "tuple[Mapping, ...]":
        """Read-only: every consensus-scope `percentile_snapshots` row at
        the EXACT `(symbol, market_type, timeframe, bucket_ts,
        calculation_version)` identity — never an older bucket, never an
        exchange-scoped row. `()` if none exist. See
        `storage/v2_alignment_readers.py::read_v2_consensus_percentiles`
        for the full contract."""
        from storage.v2_alignment_readers import (
            read_v2_consensus_percentiles, validate_consensus_feature_args)
        validate_consensus_feature_args(
            symbol=symbol, market_type=market_type, timeframe=timeframe,
            bucket_ts=bucket_ts, calculation_version=calculation_version)
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            return await read_v2_consensus_percentiles(
                conn, symbol=symbol, market_type=market_type, timeframe=timeframe,
                bucket_ts=bucket_ts, calculation_version=calculation_version)

    async def fetch_v2_data_health_at_cutoff(
        self, *, symbol: str, market_type: str, exchanges: "Sequence[str]",
        metrics: "Sequence[str]", cutoff_ts: datetime, calculation_version: str,
    ) -> "Mapping":
        """Read-only: for every requested `(exchange, metric)` pair, the
        LATEST `data_health_snapshots` row with `snapshot_ts <= cutoff_ts`
        (an explicit, caller-supplied historical cutoff — never
        `now()`/wall clock), or `None` for that pair if none is eligible.
        See `storage/v2_alignment_readers.py::read_v2_data_health_at_cutoff`
        for the full contract.

        `exchanges`/`metrics` are validated — and their DETACHED tuple
        values captured — BEFORE `pool.acquire()`. Only those detached
        tuples are passed onward, never the caller's original (possibly
        mutable) sequences: this closes a TOCTOU window where a caller
        could otherwise mutate its own `exchanges`/`metrics` list between
        this validation and the connection actually being acquired,
        changing the query's identity out from under the validation that
        already ran. The reader itself validates again from the detached
        tuples it is given; that double validation is intentional."""
        from storage.v2_alignment_readers import (
            read_v2_data_health_at_cutoff, validate_data_health_args)
        validated_exchanges, validated_metrics = validate_data_health_args(
            symbol=symbol, market_type=market_type, exchanges=exchanges,
            metrics=metrics, cutoff_ts=cutoff_ts, calculation_version=calculation_version)
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            return await read_v2_data_health_at_cutoff(
                conn, symbol=symbol, market_type=market_type,
                exchanges=validated_exchanges, metrics=validated_metrics,
                cutoff_ts=cutoff_ts, calculation_version=calculation_version)

    async def fetch_shadow_liquidation_availability(
        self,
        *,
        exchanges: "Sequence[str]",
        symbol: str,
        market_type: str,
    ) -> "Mapping[str, bool]":
        """Read the operational-CLI liquidation availability mapping for the
        shadow cycle. Validates args BEFORE acquiring, then one fetch on one
        connection; returns a detached immutable {exchange: bool} in caller order.
        No analytics import, no writes, no clock."""
        from storage.shadow_cli_readers import (
            read_shadow_liquidation_availability, validate_liquidation_availability_args)
        # Snapshot the validated, detached exchange tuple BEFORE acquire, then use
        # only it — never the caller-owned `exchanges` container, which could be
        # mutated across the await.
        validated_exchanges = validate_liquidation_availability_args(
            exchanges=exchanges, symbol=symbol, market_type=market_type)
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            return await read_shadow_liquidation_availability(
                conn, exchanges=validated_exchanges, symbol=symbol, market_type=market_type)

    async def fetch_shadow_status(
        self,
        *,
        exchanges: "Sequence[str]",
        symbol: str,
        market_type: str,
        timeframe: str,
    ) -> "Mapping":
        """Read-only shadow status snapshot. Validates args BEFORE acquiring, then
        runs the fixed status reads on ONE acquired connection; returns a detached
        immutable snapshot. No transaction, no writes, no clock, no analytics
        import. A fresh DB yields NOT_INITIALIZED rather than raising."""
        from storage.shadow_cli_readers import (
            read_shadow_status, validate_shadow_status_args)
        # Snapshot the validated, detached exchange tuple BEFORE acquire, then use
        # only it — never the caller-owned `exchanges` container.
        validated_exchanges = validate_shadow_status_args(
            exchanges=exchanges, symbol=symbol, market_type=market_type,
            timeframe=timeframe)
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            return await read_shadow_status(
                conn, exchanges=validated_exchanges, symbol=symbol,
                market_type=market_type, timeframe=timeframe)

    # ---------------------------------------------------------------
    # Shadow recovery (advisory lock + watermark + bounded discovery)
    # ---------------------------------------------------------------
    @contextlib.asynccontextmanager
    async def shadow_recovery_lock(self, key: int):
        """Hold a SESSION-scoped PostgreSQL advisory lock on ONE dedicated
        connection for the whole recovery pass. Yields True if acquired (this
        runner may proceed) or False if another runner holds it (skip, zero
        writes). The lock is always released (pg_advisory_unlock) and the
        connection returned to the pool on every exit path. It is NOT acquired
        through a helper that immediately releases the connection — the same
        connection is held for the lifetime of the `async with`."""
        if type(key) is not int:
            raise ValueError("advisory lock key must be an int")
        assert self.pool is not None
        conn = await self.pool.acquire()
        acquired = False
        try:
            acquired = bool(await conn.fetchval(
                "SELECT pg_try_advisory_lock($1)", key))
            yield acquired
        finally:
            try:
                if acquired:
                    await conn.fetchval("SELECT pg_advisory_unlock($1)", key)
            finally:
                await self.pool.release(conn)

    async def fetch_shadow_watermark(
        self, *, runner_name: str, symbol: str, market_type: str, timeframe: str,
    ) -> "Optional[datetime]":
        """Read the automatic runner's last completed bucket (or None). Validates
        before acquire; one connection; no writes."""
        from storage.shadow_recovery_readers import read_shadow_watermark, validate_runner_scope
        validate_runner_scope(runner_name=runner_name, symbol=symbol,
                              market_type=market_type, timeframe=timeframe)
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            return await read_shadow_watermark(
                conn, runner_name=runner_name, symbol=symbol,
                market_type=market_type, timeframe=timeframe)

    async def advance_shadow_watermark(
        self, *, runner_name: str, symbol: str, market_type: str, timeframe: str,
        bucket_ts: datetime,
    ) -> None:
        """Monotonically advance the runner watermark (GREATEST — never backwards).
        Validates before acquire; one connection."""
        from storage.shadow_recovery_readers import advance_shadow_watermark, validate_runner_scope
        validate_runner_scope(runner_name=runner_name, symbol=symbol,
                              market_type=market_type, timeframe=timeframe)
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            await advance_shadow_watermark(
                conn, runner_name=runner_name, symbol=symbol, market_type=market_type,
                timeframe=timeframe, bucket_ts=bucket_ts)

    async def fetch_newest_prediction_bucket(
        self, *, symbol: str, market_type: str, timeframe: str,
    ) -> "Optional[datetime]":
        """Newest persisted prediction bucket_ts for this scope (or None). One
        connection; no writes; used only to bootstrap the recovery position."""
        from storage.shadow_recovery_readers import read_newest_prediction_bucket, validate_scope
        validate_scope(symbol=symbol, market_type=market_type, timeframe=timeframe)
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            return await read_newest_prediction_bucket(
                conn, symbol=symbol, market_type=market_type, timeframe=timeframe)

    async def fetch_recovery_prediction_candidates(
        self, *, symbol: str, market_type: str, timeframe: str,
        lookback_start: datetime, limit: int,
    ) -> tuple:
        """Bounded, deterministically-ordered candidate prediction rows within the
        recovery lookback (detached MappingProxyType, JSONB parsed). No analytics,
        no writes."""
        from storage.shadow_recovery_readers import (
            read_recovery_prediction_candidates, validate_scope)
        validate_scope(symbol=symbol, market_type=market_type, timeframe=timeframe)
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            return await read_recovery_prediction_candidates(
                conn, symbol=symbol, market_type=market_type, timeframe=timeframe,
                lookback_start=lookback_start, limit=limit)

    async def fetch_missing_outcome_identities(
        self, *, symbol: str, market_type: str, timeframe: str,
        candidates: "Sequence", evaluation_price_source: str,
    ) -> tuple:
        """Anti-join the caller's candidate outcome identities against
        forecast_outcomes; return the MISSING subset in caller order (detached)."""
        from storage.shadow_recovery_readers import (
            read_missing_outcome_identities, validate_scope)
        validate_scope(symbol=symbol, market_type=market_type, timeframe=timeframe)
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            return await read_missing_outcome_identities(
                conn, symbol=symbol, market_type=market_type, timeframe=timeframe,
                candidates=candidates, evaluation_price_source=evaluation_price_source)

    async def fetch_forecast_outcome_klines(
        self,
        *,
        exchange: str,
        symbol: str,
        window_start: datetime,
        window_end: datetime,
    ) -> tuple:
        """Read the future 1m klines for one horizon evaluation window. Validates
        args before acquiring, then one fetch on one connection; returns a detached
        tuple of MappingProxyType rows in chronological order. No analytics, no
        writes, no clock. (forecast_predictions are NOT read from DB in this path —
        the shadow cycle already holds the ForecastPrediction in memory.)"""
        from storage.forecast_outcome_readers import (
            read_forecast_outcome_klines, validate_forecast_outcome_reader_args)
        validate_forecast_outcome_reader_args(
            exchange=exchange, symbol=symbol,
            window_start=window_start, window_end=window_end)
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            return await read_forecast_outcome_klines(
                conn, exchange=exchange, symbol=symbol,
                window_start=window_start, window_end=window_end)

    # ---------------------------------------------------------------
    # Telegram forecast notifier (independent advisory lock + durable outbox)
    # ---------------------------------------------------------------
    @contextlib.asynccontextmanager
    async def telegram_notifier_lock(self, key: int):
        """Hold a SESSION-scoped PostgreSQL advisory lock on ONE dedicated
        connection for the whole Telegram notifier pass. Intentionally a
        SEPARATE lock namespace from `shadow_recovery_lock` (a different key
        space entirely — Telegram reading/sending must never block shadow
        prediction/outcome processing). Yields True if acquired, False if
        another notifier runner holds it. Always released; the connection is
        always returned to the pool."""
        if type(key) is not int:
            raise ValueError("advisory lock key must be an int")
        assert self.pool is not None
        conn = await self.pool.acquire()
        acquired = False
        try:
            acquired = bool(await conn.fetchval(
                "SELECT pg_try_advisory_lock($1)", key))
            yield acquired
        finally:
            try:
                if acquired:
                    await conn.fetchval("SELECT pg_advisory_unlock($1)", key)
            finally:
                await self.pool.release(conn)

    async def fetch_telegram_schema_state(self) -> "Mapping[str, bool]":
        """Read-only: which of the two Telegram tables exist. No lock, no writes."""
        from storage.telegram_notification_readers import read_telegram_schema_state
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            return await read_telegram_schema_state(conn)

    async def ensure_telegram_notifier_state(
        self, *, runner_name: str, channel: str, recipient_fingerprint: str,
        now: datetime,
    ) -> tuple:
        """Return (started_at, bootstrapped). Validates before acquire; one
        connection for the read + (if needed) insert + re-read."""
        from storage.telegram_notification_readers import (
            ensure_notifier_started_at, validate_notifier_scope)
        validate_notifier_scope(runner_name=runner_name, channel=channel,
                                recipient_fingerprint=recipient_fingerprint)
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            return await ensure_notifier_started_at(
                conn, runner_name=runner_name, channel=channel,
                recipient_fingerprint=recipient_fingerprint, now=now)

    async def materialize_telegram_deliveries(
        self, *, channel: str, recipient_fingerprint: str, symbol: str,
        market_type: str, timeframe: str, started_at: datetime, limit: int,
    ) -> int:
        """Insert missing pending delivery rows for LONG/SHORT predictions with
        created_at >= started_at (real NOT EXISTS anti-join, ON CONFLICT DO
        NOTHING, capped, oldest-first). Validates before acquire."""
        from storage.telegram_notification_readers import (
            materialize_telegram_deliveries, validate_recipient_scope)
        validate_recipient_scope(channel=channel, recipient_fingerprint=recipient_fingerprint)
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            return await materialize_telegram_deliveries(
                conn, channel=channel, recipient_fingerprint=recipient_fingerprint,
                symbol=symbol, market_type=market_type, timeframe=timeframe,
                started_at=started_at, limit=limit)

    async def fetch_pending_telegram_deliveries(
        self, *, channel: str, recipient_fingerprint: str, now: datetime, limit: int,
    ) -> tuple:
        """Due unsent deliveries joined to their prediction (explicit columns, no
        consensus_snapshot), deterministic oldest-next_attempt_at-first order,
        capped, detached. Validates before acquire."""
        from storage.telegram_notification_readers import (
            read_pending_telegram_deliveries, validate_recipient_scope)
        validate_recipient_scope(channel=channel, recipient_fingerprint=recipient_fingerprint)
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            return await read_pending_telegram_deliveries(
                conn, channel=channel, recipient_fingerprint=recipient_fingerprint,
                now=now, limit=limit)

    async def record_telegram_attempt_start(
        self, *, channel: str, recipient_fingerprint: str, symbol: str, market_type: str,
        timeframe: str, bucket_ts: datetime, calculation_version: str, rule_version: str,
    ) -> int:
        from storage.telegram_notification_readers import record_delivery_attempt_start
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            return await record_delivery_attempt_start(
                conn, channel=channel, recipient_fingerprint=recipient_fingerprint,
                symbol=symbol, market_type=market_type, timeframe=timeframe,
                bucket_ts=bucket_ts, calculation_version=calculation_version,
                rule_version=rule_version)

    async def record_telegram_sent(
        self, *, channel: str, recipient_fingerprint: str, symbol: str, market_type: str,
        timeframe: str, bucket_ts: datetime, calculation_version: str, rule_version: str,
        telegram_message_id: int,
    ) -> None:
        from storage.telegram_notification_readers import record_delivery_sent
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            await record_delivery_sent(
                conn, channel=channel, recipient_fingerprint=recipient_fingerprint,
                symbol=symbol, market_type=market_type, timeframe=timeframe,
                bucket_ts=bucket_ts, calculation_version=calculation_version,
                rule_version=rule_version, telegram_message_id=telegram_message_id)

    async def record_telegram_failure(
        self, *, channel: str, recipient_fingerprint: str, symbol: str, market_type: str,
        timeframe: str, bucket_ts: datetime, calculation_version: str, rule_version: str,
        next_attempt_at: datetime, error_class: str, error_summary: str,
    ) -> None:
        from storage.telegram_notification_readers import record_delivery_failure
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            await record_delivery_failure(
                conn, channel=channel, recipient_fingerprint=recipient_fingerprint,
                symbol=symbol, market_type=market_type, timeframe=timeframe,
                bucket_ts=bucket_ts, calculation_version=calculation_version,
                rule_version=rule_version, next_attempt_at=next_attempt_at,
                error_class=error_class, error_summary=error_summary)

    async def fetch_telegram_notifier_status(
        self, *, channel: str, recipient_fingerprint: str, now: datetime,
    ) -> "Mapping":
        """Read-only aggregate status (no schema init, no lock, no writes)."""
        from storage.telegram_notification_readers import (
            read_notifier_status_aggregate, validate_recipient_scope)
        validate_recipient_scope(channel=channel, recipient_fingerprint=recipient_fingerprint)
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            return await read_notifier_status_aggregate(
                conn, channel=channel, recipient_fingerprint=recipient_fingerprint, now=now)

    async def fetch_telegram_notifier_started_at(
        self, *, runner_name: str, channel: str, recipient_fingerprint: str,
    ) -> "Optional[datetime]":
        """READ-ONLY started_at lookup (no insert/bootstrap side effect) — used by
        --telegram-status, which must never write."""
        from storage.telegram_notification_readers import (
            read_notifier_started_at, validate_notifier_scope)
        validate_notifier_scope(runner_name=runner_name, channel=channel,
                                recipient_fingerprint=recipient_fingerprint)
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            return await read_notifier_started_at(
                conn, runner_name=runner_name, channel=channel,
                recipient_fingerprint=recipient_fingerprint)
