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
    from storage.stage2_publication_state import Stage2PublicationResult
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

# (V2-H2c) The full value-field set exchange_instrument_history compares to
# decide whether an upsert actually changed anything -- wider than
# _INSTRUMENT_CRITICAL_FIELDS above (which gates the LKG mismatch ALARM
# only): price_precision/quantity_precision are not alarm-worthy on their
# own, but a historical replay must still see the exact value that was
# actually in effect, so a change to either of them still opens a new
# history interval.
_INSTRUMENT_HISTORY_VALUE_FIELDS = (
    "exchange_instrument_id", "quantity_unit", "contract_multiplier",
    "tick_size", "price_precision", "quantity_precision")


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


# ---------------------------------------------------------------
# V2-H2e raw-writer hardening helpers (tech-lead review round 2, finding 7).
#
# The unnest-based multi-row raw writers (`insert_klines`/`insert_open_interest`/
# `insert_funding`) replaced per-row `executemany` with ONE
# `INSERT ... SELECT * FROM unnest(...)` statement -- a real behavior change
# in two respects a per-row `executemany` never had to worry about:
#   1. A malformed/ragged input (rows of inconsistent length) used to fail
#      inside asyncpg's own per-row parameter binding; `zip(*rows)` instead
#      silently TRUNCATES to the shortest row's length, which could hide a
#      caller bug instead of failing loudly.
#   2. Postgres rejects `INSERT ... ON CONFLICT DO UPDATE` if the SAME
#      conflict target (here: the (exchange, symbol, ts) logical key)
#      appears twice in one statement's input set
#      (`CardinalityViolation: ON CONFLICT DO UPDATE command cannot affect
#      row a second time`) -- `executemany` never hit this, since each row
#      was its own independent statement (last one submitted simply won).
# ---------------------------------------------------------------
def _validate_row_arity(rows: Sequence[tuple], expected_len: int, writer_name: str) -> None:
    """Every row in `rows` must have EXACTLY `expected_len` fields. Raises
    `ValueError` immediately (before any DB call) naming the first
    offending row's index/length -- never silently truncated/padded via
    `zip(*rows)`'s shortest-iterable behavior."""
    for i, row in enumerate(rows):
        if len(row) != expected_len:
            raise ValueError(
                f"{writer_name}: row {i} has {len(row)} fields, expected exactly "
                f"{expected_len} -- refusing a ragged/malformed batch"
            )


def _dedupe_last_write_wins(rows: Sequence[tuple], key_indices: "tuple[int, ...]") -> list:
    """If `rows` contains more than one row sharing the SAME logical key
    (`key_indices` into each row tuple), keep only the LAST occurrence of
    each key -- deterministically preserving the exact observable result
    the OLD per-row `executemany` path had (each row was its own `INSERT
    ... ON CONFLICT DO UPDATE` statement issued in order, so a later
    duplicate key's values always won over an earlier one in the same
    batch). This also sidesteps Postgres's `CardinalityViolation` for the
    new single-statement `unnest` writers, which cannot affect the same
    conflict target twice in one statement.

    Relative row order is otherwise preserved (by each SURVIVING row's
    original index), so this is a pure "drop the shadowed duplicates" op,
    not a reorder."""
    last_index_by_key: "dict" = {}
    for i, row in enumerate(rows):
        key = tuple(row[k] for k in key_indices)
        last_index_by_key[key] = i   # later occurrences overwrite earlier ones
    keep_indices = sorted(last_index_by_key.values())
    return [rows[i] for i in keep_indices]


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
        connection is acquired; all SEVEN reads (klines, open_interest,
        funding, liquidations, instrument, liquidation capability,
        required_metadata_revision) run inside ONE `REPEATABLE READ`
        read-only transaction on a single acquired connection -- never as
        separate autocommit statements.

        (CodeRabbit finding, tech-lead-classified BLOCKER) Under plain
        `READ COMMITTED` autocommit, each of the seven SELECTs could observe
        a DIFFERENT PostgreSQL snapshot: e.g. `INSTRUMENT_SQL` reads OLD
        instrument metadata, then a concurrent transaction deliberately
        accepts a critical metadata change and commits (NEW
        `exchange_instruments` + NEW history interval + NEW
        `stage2_instrument_metadata_state.required_revision`) before
        `REQUIRED_METADATA_REVISION_SQL` runs -- the returned bundle would
        then mix OLD instrument metadata with the NEW required revision,
        exactly the incoherence the H2c calculation_version fork gate
        (`analytics/feature_engine/input_adapter.py::
        assemble_exchange_feature_request`) depends on never happening. A
        `REPEATABLE READ` transaction takes ONE consistent snapshot at its
        first statement and every subsequent statement in it sees that SAME
        snapshot, so all seven reads are guaranteed internally coherent
        (either all-OLD or all-NEW, never mixed) regardless of what any
        concurrent transaction commits in between. `readonly=True` is a
        genuine safety property here (this method issues seven SELECTs and
        nothing else) and lets PostgreSQL avoid serialization-failure
        bookkeeping it would otherwise do for a read/write REPEATABLE READ
        transaction. This does NOT change `compute_calculation_version`'s
        formula or `stage2_instrument_metadata_state`'s revision semantics
        -- it only guarantees the bundle the analytics layer receives is a
        single, self-consistent point-in-time view. No analytics, no
        writes, no wall clock. SQL lives in storage/stage2_readers.py
        (static/trusted)."""
        from storage.stage2_readers import (  # local import: no analytics coupling
            read_exchange_feature_raw_bundle, validate_raw_bundle_args)
        validate_raw_bundle_args(exchange=exchange, symbol=symbol,
                                 market_type=market_type, bucket_start=bucket_start,
                                 bucket_end=bucket_end)
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            async with conn.transaction(isolation="repeatable_read", readonly=True):
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
        effective_from=None,
        target_metadata_revision: "Optional[int]" = None,
    ) -> str:
        """Upsert an instrument row. The canonical `symbol` and the venue-native
        `exchange_instrument_id` are stored in SEPARATE columns. Stale flag and
        provenance are stored explicitly.

        A change on a critical field (exchange_instrument_id, quantity_unit,
        contract_multiplier, tick_size) versus the existing row is NOT silently
        overwritten: unless `accept_mismatch=True`, this raises so the change is
        a deliberate decision.

        **`calculation_version` fork enforcement, connected end-to-end
        (tech-lead review 4991738511; supersedes review 4990482334's
        `accepted_code_version`, which proved only that two STORED LABELS
        differed, never that the live Stage-2 feature-assembly path was
        mechanically prevented from consuming NEW critical metadata under
        an OLD `calculation_version` -- that column/parameter is REMOVED,
        not kept alongside this one).** Accepting (`accept_mismatch=True`)
        a genuine change on any `_INSTRUMENT_CRITICAL_FIELDS` field
        additionally REQUIRES `target_metadata_revision` (a plain int,
        never a timestamp): the new value for the ONE global,
        Stage-2-wide `stage2_instrument_metadata_state.required_revision`
        row this deliberate acceptance is declaring. It MUST be strictly
        GREATER than that row's own CURRENT value (read here under
        `SELECT ... FOR UPDATE`, serializing against any OTHER identity's
        concurrent critical acceptance too, not just this one) -- the
        same or a lower value raises, refusing the acceptance outright.
        On success this method atomically UPDATEs that row to the new
        value, in the SAME transaction as the LKG upsert and the history
        interval close/open below, so no external observer can ever see
        NEW metadata paired with the OLD required revision or vice versa.

        This is what actually closes the loop to feature computation:
        `defaults.instrument_metadata_revision` (`config/stage2.yaml`) is
        part of the RESOLVED per-symbol config, hence part of
        `config_hash`, hence part of `calculation_version` -- with ZERO
        change to `compute_calculation_version`'s formula/format. Every
        live feature computation's raw-bundle read
        (`storage/stage2_readers.py::read_exchange_feature_raw_bundle`)
        reads this SAME `stage2_instrument_metadata_state` row, and
        `analytics/feature_engine/input_adapter.py::
        assemble_exchange_feature_request` FAILS CLOSED
        (`FeatureInputError`, before constructing any
        `ExchangeFeatureRequest`) the instant the resolved config's own
        `instrument_metadata_revision` no longer matches it -- i.e. the
        moment this method bumps this row, EVERY exchange/symbol's Stage 2
        computation (not just this identity's) refuses to persist a
        feature vector until an operator explicitly updates
        `config/stage2.yaml` to adopt the new revision (which is exactly
        what forks `calculation_version` for real). Deliberately ONE
        GLOBAL row, not one per identity: `calculation_version` is a
        SHARED Stage-2 computation namespace, so an accepted critical
        change on any single venue must fork it for ALL venues together.
        See `storage/stage2_schema.sql::stage2_instrument_metadata_state`'s
        own comment for the full mechanism and
        `tests/analytics/test_stage2_metadata_revision_fork.py`'s executable
        end-to-end proof (old config+new metadata fails closed; updated
        config+new metadata succeeds with a genuinely different
        `calculation_version`).

        A non-critical value change (e.g. price_precision-only) never
        requires or bumps `target_metadata_revision` -- it inherits
        whatever the CURRENT global `required_revision` already is,
        stamped onto its own history row's `accepted_metadata_revision`
        purely for provenance (never reset to NULL/None -- finding 10).

        Runs inside ONE transaction, serialized by a transaction-scoped
        Postgres advisory lock keyed to `(exchange, symbol, market_type)`
        -- this closes a pre-existing TOCTOU (the mismatch check
        previously read the current LKG row via a SEPARATE, unlocked
        `pool.acquire()`/`get_exchange_instrument()` call before writing)
        and gives the `exchange_instrument_history` append below the same
        serialization guarantee, without requiring a placeholder row to
        lock before this call's final accepted values are known (an
        advisory lock works even when no `exchange_instruments` row
        exists yet, e.g. this identity's very first bootstrap).

        **`fetched_at` vs `effective_from` (tech-lead review 4990482334,
        finding 1) -- two DISTINCT timestamps, never conflated.**
        `fetched_at` is `observed_at`: PROVENANCE ONLY, when this value
        was actually fetched/observed -- it does NOT by itself determine
        when the value becomes eligible for V2 decision boundaries to
        use. `effective_from` is the EXPLICIT V2 decision-time activation
        boundary. Whenever this call's own value fields
        (`exchange_instrument_id`/`quantity_unit`/`contract_multiplier`/
        `tick_size`/`price_precision`/`quantity_precision`) genuinely
        differ from the currently-open `exchange_instrument_history`
        interval:

          - if an interval is ALREADY open (a real value CHANGE, not a
            first-ever value) and `effective_from` was not explicitly
            supplied, this RAISES rather than silently defaulting to
            `fetched_at` -- auto-backdating a deliberately-accepted
            mismatch to its (possibly much earlier) observation time
            would let a REPLAY see the new value at decision boundaries
            where the actual LIVE run still correctly used the OLD one.
            The caller MUST supply the real acceptance boundary
            explicitly.
          - if NO interval is open yet (this identity's first-ever
            accepted value) and `effective_from` is not supplied, it
            safely defaults to `fetched_at` -- there is no OLD value's
            already-made LIVE decisions to protect against.
          - `fetched_at` (`observed_at`) MUST be `<= effective_from` when
            both are given (a value cannot become effective before it
            was even observed) -- raises otherwise.
          - `fetched_at=None` (no honest observation timestamp -- e.g. a
            bare `manual`/`declared_fallback` value) is legal PROVIDED
            `effective_from` is supplied explicitly; with neither given,
            no interval is opened or closed at all.

        The previously-open interval (if any) is closed at the NEW
        interval's own `effective_from` (never at `fetched_at`), in the
        SAME transaction as opening the next one. An idempotent refresh
        whose value fields are unchanged never opens a spurious extra
        interval, regardless of what `fetched_at`/`effective_from` were
        passed."""
        assert self.pool is not None
        new_vals = {
            "exchange_instrument_id": exchange_instrument_id,
            "quantity_unit": quantity_unit,
            "contract_multiplier": contract_multiplier,
            "tick_size": tick_size,
            "price_precision": price_precision,
            "quantity_precision": quantity_precision,
        }
        history_vals = tuple(new_vals[f] for f in _INSTRUMENT_HISTORY_VALUE_FIELDS)
        if fetched_at is not None and effective_from is not None and fetched_at > effective_from:
            raise ValueError(
                f"instrument history for {exchange}/{symbol}/{market_type}: fetched_at "
                f"(observed_at) {fetched_at!r} is AFTER effective_from {effective_from!r} -- "
                "a value cannot become effective before it was even observed")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "SELECT pg_advisory_xact_lock(hashtext($1))",
                    f"{exchange}:{symbol}:{market_type}")
                existing = await conn.fetchrow(
                    "SELECT * FROM exchange_instruments "
                    "WHERE exchange=$1 AND symbol=$2 AND market_type=$3",
                    exchange, symbol, market_type)
                critical_diff = (
                    [f for f in _INSTRUMENT_CRITICAL_FIELDS if existing[f] != new_vals[f]]
                    if existing is not None else [])
                if existing is not None and not accept_mismatch:
                    if critical_diff:
                        raise ValueError(
                            f"instrument metadata mismatch on {critical_diff} for "
                            f"{exchange}/{symbol}/{market_type}; refusing silent overwrite "
                            f"(pass accept_mismatch=True to accept deliberately)")
                revision_for_history_row = None
                if critical_diff:
                    # (tech-lead review 4991738511) A genuine deliberately-
                    # accepted CRITICAL metadata change must declare a NEW,
                    # strictly-greater required instrument-metadata revision
                    # -- never silently continue under the OLD one. This is
                    # the REAL, end-to-end fork mechanism: bumping this ONE
                    # global row is what the live Stage 2 feature-assembly
                    # path (analytics/feature_engine/input_adapter.py::
                    # assemble_exchange_feature_request) checks against and
                    # fails closed on for EVERY exchange/symbol, until an
                    # operator explicitly updates config/stage2.yaml's
                    # defaults.instrument_metadata_revision to match (which
                    # forks calculation_version for real, since that config
                    # value is part of config_hash).
                    if target_metadata_revision is None:
                        raise ValueError(
                            f"instrument metadata critical-field change on {critical_diff} for "
                            f"{exchange}/{symbol}/{market_type} is being accepted, but no "
                            "target_metadata_revision was supplied -- a genuine critical "
                            "metadata acceptance must declare the NEW required instrument-"
                            "metadata revision, so calculation_version can fork end-to-end; "
                            "refusing to silently continue under the old revision")
                    if not isinstance(target_metadata_revision, int) or isinstance(
                            target_metadata_revision, bool):
                        raise ValueError(
                            f"target_metadata_revision must be an int, got "
                            f"{type(target_metadata_revision).__name__}")
                    if target_metadata_revision <= 0:
                        raise ValueError(
                            f"target_metadata_revision must be > 0, got {target_metadata_revision!r}")
                    current_revision_row = await conn.fetchrow(
                        "SELECT required_revision FROM stage2_instrument_metadata_state "
                        "FOR UPDATE")
                    if current_revision_row is None:
                        raise ValueError(
                            "stage2_instrument_metadata_state has no row -- schema not "
                            "bootstrapped (call Database.bootstrap_instrument_metadata_revision "
                            "first)")
                    current_revision = current_revision_row["required_revision"]
                    if target_metadata_revision <= current_revision:
                        raise ValueError(
                            f"instrument metadata critical-field change on {critical_diff} for "
                            f"{exchange}/{symbol}/{market_type}: target_metadata_revision "
                            f"{target_metadata_revision!r} is not strictly greater than the "
                            f"currently required instrument-metadata revision "
                            f"{current_revision!r} -- a genuine critical metadata change must "
                            "fork to a NEW, higher revision, never reuse or lower the current "
                            "one, or subsequent Stage 2 computations could silently continue "
                            "under the OLD calculation_version")
                    await conn.execute(
                        "UPDATE stage2_instrument_metadata_state "
                        "SET required_revision = $1, updated_at = now()",
                        target_metadata_revision)
                    revision_for_history_row = target_metadata_revision
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

                if fetched_at is not None or effective_from is not None:
                    current = await conn.fetchrow(
                        "SELECT effective_from, exchange_instrument_id, quantity_unit, "
                        "contract_multiplier, tick_size, price_precision, quantity_precision "
                        "FROM exchange_instrument_history "
                        "WHERE exchange=$1 AND symbol=$2 AND market_type=$3 "
                        "AND effective_until IS NULL",
                        exchange, symbol, market_type)
                    current_vals = None
                    if current is not None:
                        current_vals = tuple(current[f] for f in _INSTRUMENT_HISTORY_VALUE_FIELDS)
                    if current_vals != history_vals:
                        resolved_effective_from = effective_from
                        if resolved_effective_from is None:
                            if current is not None:
                                raise ValueError(
                                    f"instrument history for {exchange}/{symbol}/{market_type}: "
                                    "this is a genuine value CHANGE against an already-open "
                                    "interval -- effective_from must be supplied explicitly "
                                    "(the real V2 decision-time acceptance boundary); refusing "
                                    "to silently backdate to fetched_at (observed_at)")
                            resolved_effective_from = fetched_at   # first-ever value: safe default
                        if current is not None:
                            if resolved_effective_from <= current["effective_from"]:
                                raise ValueError(
                                    f"instrument history for {exchange}/{symbol}/{market_type}: "
                                    f"effective_from {resolved_effective_from!r} is not strictly "
                                    f"after the currently-open interval's own effective_from "
                                    f"{current['effective_from']!r} -- history must be appended "
                                    "in non-decreasing effective_from order, never reordered")
                            # (CodeRabbit finding, harmless semantic hardening --
                            # NOT a fix for duplicate-effective_from corruption:
                            # the table's own PRIMARY KEY (exchange, symbol,
                            # market_type, effective_from) already makes that
                            # impossible.) `AND effective_until IS NULL` makes
                            # this UPDATE's intent explicit: it only ever closes
                            # the ONE currently-open interval this same
                            # transaction just read as `current`, never an
                            # already-closed row that happens to share this
                            # identity's `effective_from`.
                            await conn.execute(
                                "UPDATE exchange_instrument_history SET effective_until = $1 "
                                "WHERE exchange=$2 AND symbol=$3 AND market_type=$4 "
                                "AND effective_from=$5 AND effective_until IS NULL",
                                resolved_effective_from, exchange, symbol, market_type,
                                current["effective_from"])
                        if revision_for_history_row is None:
                            # Non-critical value change (e.g. price_precision-
                            # only): inherit whatever the CURRENT global
                            # required revision already is, for provenance
                            # only -- never reset to NULL/None (finding 10).
                            rev_row = await conn.fetchrow(
                                "SELECT required_revision FROM stage2_instrument_metadata_state")
                            if rev_row is None:
                                raise ValueError(
                                    "stage2_instrument_metadata_state has no row -- schema not "
                                    "bootstrapped (call "
                                    "Database.bootstrap_instrument_metadata_revision first)")
                            revision_for_history_row = rev_row["required_revision"]
                        await conn.execute(
                            """
                            INSERT INTO exchange_instrument_history
                                (exchange, symbol, market_type, exchange_instrument_id,
                                 quantity_unit, contract_multiplier, tick_size,
                                 price_precision, quantity_precision, metadata_source,
                                 observed_at, effective_from, effective_until, note,
                                 accepted_metadata_revision)
                            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,NULL,$13,$14)
                            """,
                            exchange, symbol, market_type, exchange_instrument_id,
                            quantity_unit, contract_multiplier, tick_size,
                            price_precision, quantity_precision, metadata_source,
                            fetched_at, resolved_effective_from, note,
                            revision_for_history_row,
                        )
        return "OK"

    async def seed_current_instrument_history(
        self, *, exchange: str, symbol: str, market_type: str, effective_from,
    ) -> str:
        """(Tech-lead review 4990482334, finding 3) Explicit, conservative,
        idempotent bootstrap: seeds `exchange_instrument_history` from an
        ALREADY-ACCEPTED, pre-existing `exchange_instruments` LKG row that
        has no history yet -- without this, a production identity that was
        accepted before H2c landed would have a real current LKG row but
        `fetch_v2_instrument(..., as_of=T)` would return `None` forever
        (never falling back to the LKG row -- that remains correct; this
        method is the honest way to give it real history instead).

        `effective_from` is the caller's own EXPLICIT, truthful V2
        decision-time boundary from which the LKG's current value is
        actually known/willing to be treated as historically valid --
        this method NEVER extrapolates backward past it (no `-infinity`,
        no project-start date, no hidden `now()`); a historical `as_of`
        earlier than `effective_from` still correctly resolves to `None`.

        Returns `"NO_LKG"` if no `exchange_instruments` row exists for
        this identity (nothing to seed). Returns `"ALREADY_HAS_HISTORY"`
        without writing anything if this identity already has ANY
        `exchange_instrument_history` row (open or closed) -- this method
        NEVER overwrites/duplicates real history; safe to call repeatedly
        (idempotent), including after a prior successful seed. Returns
        `"SEEDED"` when it actually inserted the one new open interval.

        Runs inside ONE transaction, serialized by the SAME
        transaction-scoped advisory lock `upsert_exchange_instrument` uses
        for this identity. Never modifies `exchange_instruments` itself --
        the existing LKG row is preserved exactly as-is."""
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "SELECT pg_advisory_xact_lock(hashtext($1))",
                    f"{exchange}:{symbol}:{market_type}")
                lkg = await conn.fetchrow(
                    "SELECT * FROM exchange_instruments "
                    "WHERE exchange=$1 AND symbol=$2 AND market_type=$3",
                    exchange, symbol, market_type)
                if lkg is None:
                    return "NO_LKG"
                any_history = await conn.fetchrow(
                    "SELECT 1 FROM exchange_instrument_history "
                    "WHERE exchange=$1 AND symbol=$2 AND market_type=$3 LIMIT 1",
                    exchange, symbol, market_type)
                if any_history is not None:
                    return "ALREADY_HAS_HISTORY"
                # (Tech-lead review 4991738511) Stamp the CURRENT global
                # required revision onto this seeded row for provenance
                # ONLY -- bootstrapping never forks anything itself, so it
                # simply records whatever revision is already live.
                rev_row = await conn.fetchrow(
                    "SELECT required_revision FROM stage2_instrument_metadata_state")
                if rev_row is None:
                    raise ValueError(
                        "stage2_instrument_metadata_state has no row -- schema not "
                        "bootstrapped (call Database.bootstrap_instrument_metadata_revision "
                        "before seeding instrument history)")
                await conn.execute(
                    """
                    INSERT INTO exchange_instrument_history
                        (exchange, symbol, market_type, exchange_instrument_id,
                         quantity_unit, contract_multiplier, tick_size,
                         price_precision, quantity_precision, metadata_source,
                         observed_at, effective_from, effective_until, note,
                         accepted_metadata_revision)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,NULL,$13,$14)
                    """,
                    exchange, symbol, market_type, lkg["exchange_instrument_id"],
                    lkg["quantity_unit"], lkg["contract_multiplier"], lkg["tick_size"],
                    lkg["price_precision"], lkg["quantity_precision"], lkg["metadata_source"],
                    lkg["fetched_at"], effective_from,
                    f"seeded from pre-existing exchange_instruments LKG row "
                    f"(its own fetched_at={lkg['fetched_at']!r})",
                    rev_row["required_revision"],
                )
        return "SEEDED"

    async def bootstrap_instrument_metadata_revision(self, *, initial_revision: int) -> str:
        """(Tech-lead review 4991738511, finding 11; tightened by tech-lead
        review 4992495660, finding 3) Explicit, conservative bootstrap AND
        verification of the ONE global `stage2_instrument_metadata_state`
        row -- the durable current required instrument-metadata revision
        every Stage 2 feature computation (any exchange, any symbol) must
        agree with. Mirrors `seed_current_instrument_history`'s own
        explicit/conservative shape.

        `initial_revision` MUST be established explicitly from the caller's
        own resolved Stage 2 configuration (`stage2_config.
        instrument_metadata_revision`) -- never invented, never a
        timestamp, never hardcoded silently in this method or in schema
        DDL. This is a RUNTIME BOOTSTRAP BOUNDARY, not a passive read, so
        it verifies as well as seeds:

          - no row exists yet -> inserts `initial_revision` -> `"SEEDED"`.
          - a row exists and its `required_revision` EQUALS
            `initial_revision` -> `"ALREADY_INITIALIZED"`, no write
            (idempotent restart/re-run).
          - a row exists and its `required_revision` DIFFERS from
            `initial_revision` -> raises `ValueError`, NO overwrite. This
            is deliberately NOT silently tolerated: the durable value may
            have been bumped by a deliberately-accepted critical metadata
            change (`Database.upsert_exchange_instrument`'s
            `accept_mismatch=True` path) that this deployment's
            `config/stage2.yaml` has not yet been updated to adopt --
            continuing under a stale `initial_revision` would let this
            runtime silently compute under the WRONG resolved
            `instrument_metadata_revision` (and therefore the wrong
            `calculation_version`) instead of failing closed, exactly the
            gap `analytics/feature_engine/input_adapter.py::
            assemble_exchange_feature_request`'s own fail-closed gate
            exists to prevent. The operator must reconcile
            `config/stage2.yaml` (or investigate why the durable value
            changed) before retrying."""
        if not isinstance(initial_revision, int) or isinstance(initial_revision, bool):
            raise ValueError(
                f"initial_revision must be an int, got {type(initial_revision).__name__}")
        if initial_revision <= 0:
            raise ValueError(f"initial_revision must be > 0, got {initial_revision!r}")
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "SELECT pg_advisory_xact_lock(hashtext('stage2_instrument_metadata_state'))")
                existing = await conn.fetchrow(
                    "SELECT required_revision FROM stage2_instrument_metadata_state")
                if existing is None:
                    await conn.execute(
                        "INSERT INTO stage2_instrument_metadata_state "
                        "(singleton, required_revision, updated_at) VALUES (TRUE, $1, now())",
                        initial_revision)
                    return "SEEDED"
                persisted = existing["required_revision"]
                if persisted != initial_revision:
                    raise ValueError(
                        f"stage2_instrument_metadata_state.required_revision is "
                        f"{persisted!r}, but this deployment's resolved "
                        f"instrument_metadata_revision is {initial_revision!r} -- "
                        "refusing to silently overwrite the durable value (it may "
                        "have been legitimately bumped by an accepted critical "
                        "metadata change this config has not yet adopted); update "
                        "config/stage2.yaml's defaults.instrument_metadata_revision "
                        "to match, or investigate why it differs, before retrying")
        return "ALREADY_INITIALIZED"

    # ---------------------------------------------------------------
    # V2-H2e: raw-revision bumping for raw writers.
    #
    # Amended per tech-lead review (round 2, findings 1/2): a raw write can
    # invalidate already-published derived history in TWO distinct ways --
    # not just an `ON CONFLICT DO UPDATE` hit against an already-existing
    # row (a "correction"), but ALSO a genuinely first-ever insert
    # (`xmax = 0`) whose timestamp lands inside a bucket
    # `exchange_feature_vectors` has ALREADY published a row for (a late
    # gap-fill arriving after Stage 2 already computed -- and persisted --
    # that bucket as `has_gap=True`/partial). Treating "row already
    # existed" as the ONLY correction signal (finding 2) was wrong: a first
    # insert can be just as invalidating as an update.
    # ---------------------------------------------------------------
    async def _fresh_rows_affect_published_bucket(
        self, conn, *, exchange: str, symbol: str, fresh_ts: "Sequence[datetime]",
    ) -> bool:
        """True if ANY of `fresh_ts` (timestamps of rows that were genuinely
        first-ever inserts, `xmax = 0`, in this batch) falls inside the
        half-open `[bucket_ts, bucket_ts + timeframe)` interval of an
        EXISTING `exchange_feature_vectors` row for `(exchange, symbol)`, at
        ANY timeframe. Checking the exchange-scoped feature table (rather
        than consensus/percentiles) is the narrowest predicate that is
        still safe: every downstream family is itself derived from this
        one, so if an exchange-scoped bucket already exists here, treating
        the scope as invalidated is a safe, conservative signal regardless
        of whether consensus/percentiles happen to exist yet too. One
        query for the whole `fresh_ts` batch (never one query per row).

        Fail-closed for an unrecognized `timeframe` (CodeRabbit finding,
        tech-lead review round 3): `exchange_feature_vectors.timeframe` is
        NOT structurally constrained anywhere today -- no DB `CHECK`, no
        dataclass validation (`analytics/feature_engine/models.py`'s own
        `TIMEFRAME_MINUTES` is an unenforced, phase-scoped "supported
        dimensions" constant, not a frozen contract this PR is positioned
        to encode as new schema DDL with its own legacy-migration story).
        A row whose `timeframe` is NOT one of the five known values
        (`'1m'`, `'5m'`, `'15m'`, `'1h'`, `'4h'`) is therefore treated as
        an UNCONDITIONAL match for its `(exchange, symbol)` -- never
        silently excluded via an `ELSE interval '0'` containment window
        that would always evaluate to false. This mirrors the same
        "over-marking is always safe, silently under-marking never is"
        discipline `storage/stage2_publication_state.py` already documents
        for the correction-detection side."""
        if not fresh_ts:
            return False
        return bool(await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM exchange_feature_vectors efv
                WHERE efv.exchange = $1 AND efv.symbol = $2
                  AND (
                    efv.timeframe NOT IN ('1m', '5m', '15m', '1h', '4h')
                    OR EXISTS (
                        SELECT 1 FROM unnest($3::timestamptz[]) AS fresh(ts)
                        WHERE fresh.ts >= efv.bucket_ts
                          AND fresh.ts < efv.bucket_ts + (CASE efv.timeframe
                                WHEN '1m'  THEN interval '1 minute'
                                WHEN '5m'  THEN interval '5 minutes'
                                WHEN '15m' THEN interval '15 minutes'
                                WHEN '1h'  THEN interval '1 hour'
                                WHEN '4h'  THEN interval '4 hours'
                            END)
                    )
                  )
            )
            """,
            exchange, symbol, list(fresh_ts),
        ))

    async def _bump_raw_revision_for_write(
        self, conn, *, corrected_pairs: "set", fresh_ts_by_pair: "dict", reason: str,
    ) -> None:
        """For every `(exchange, symbol)` pair this raw write touched,
        decide whether it invalidates already-published derived history --
        unconditionally true if the pair is in `corrected_pairs` (an
        `ON CONFLICT DO UPDATE` hit against an already-existing row --
        deliberately conservative, no old-vs-new value diff: an
        identical-value idempotent re-write still counts), otherwise true
        only if `_fresh_rows_affect_published_bucket` proves it for that
        pair's `fresh_ts_by_pair` entry. If so, resolve every `market_type`
        `exchange_instruments` maps that pair to and bump
        `stage2_raw_revision` for `(symbol, market_type)` -- all on `conn`,
        i.e. inside the SAME transaction as the raw write (one COMMIT
        covers both, per §3.4's atomicity requirement).

        An `(exchange, symbol)` pair with NO `exchange_instruments` row is
        logged and otherwise skipped, never raised -- raw ingestion must
        stay available even for an instrument whose metadata has not been
        seeded yet; that instrument cannot be a V2 input until it is seeded
        (H2c), so there is no coherence fact to protect for it yet.

        A Stage-1-only deployment (`exchange_instruments`/
        `exchange_feature_vectors`/`stage2_raw_revision` not created at all
        -- Stage 2 schema never initialized) is handled the same way: each
        pair's work runs inside its OWN nested transaction (`conn.transaction()`
        called while already inside the caller's transaction opens a
        SAVEPOINT, per asyncpg's documented nesting behavior) so an
        `UndefinedTableError` here rolls back only that savepoint, never
        the outer transaction -- the raw write this method is called from
        MUST still commit even when Stage 2 schema does not exist yet."""
        all_pairs = set(corrected_pairs) | set(fresh_ts_by_pair)
        if not all_pairs:
            return
        from storage.stage2_publication_state import bump_raw_revision
        for exchange, symbol in sorted(all_pairs):
            try:
                async with conn.transaction():
                    if (exchange, symbol) in corrected_pairs:
                        should_bump = True
                    else:
                        should_bump = await self._fresh_rows_affect_published_bucket(
                            conn, exchange=exchange, symbol=symbol,
                            fresh_ts=fresh_ts_by_pair.get((exchange, symbol), ()))
                    if not should_bump:
                        continue
                    market_type_rows = await conn.fetch(
                        "SELECT DISTINCT market_type FROM exchange_instruments "
                        "WHERE exchange=$1 AND symbol=$2",
                        exchange, symbol,
                    )
                    if not market_type_rows:
                        logger.warning(
                            "stage2_raw_revision: invalidating raw write for exchange=%s symbol=%s "
                            "could not be mapped to a market_type (no exchange_instruments row) "
                            "-- raw-revision bump skipped for this write",
                            exchange, symbol,
                        )
                        continue
                    for mt_row in market_type_rows:
                        await bump_raw_revision(
                            conn, symbol=symbol, market_type=mt_row["market_type"], reason=reason)
            except asyncpg.exceptions.UndefinedTableError:
                logger.warning(
                    "stage2_raw_revision: Stage 2 schema not initialized yet "
                    "(exchange_instruments/exchange_feature_vectors/stage2_raw_revision absent) "
                    "-- raw-revision bump skipped for exchange=%s symbol=%s (Stage-1-only deployment)",
                    exchange, symbol,
                )

    # ---------------------------------------------------------------
    # Writers
    # ---------------------------------------------------------------
    async def insert_klines(self, rows: Sequence[tuple], source: str) -> int:
        """rows: (exchange, symbol, ts, open, high, low, close, volume,
        taker_buy_volume, taker_sell_volume, trades_count)

        Conflict semantics (V2-H2d, docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md
        §2.1b) -- per-column, NOT a blanket COALESCE-everything rule:

        - open/high/low/close/volume: unconditionally overwritten with
          EXCLUDED.* on every write, live or backfill. `klines_1m` declares
          all five NOT NULL (schema.sql), so no source ever supplies NULL
          here -- there is no "downgrade" risk for these columns, and a
          later write (e.g. a backfill re-read of the exchange's own
          authoritative closed-bar REST data) legitimately correcting an
          earlier live-computed aggregate MUST still be able to overwrite,
          exactly as the frozen contract requires.
        - taker_buy_volume/taker_sell_volume/trades_count: OPTIONAL
          fidelity fields (nullable) -- only Binance backfill and live
          ingestion populate them; Bybit/OKX/Bitget historical klines never
          carry a taker-buy/sell split, so their backfill rows always pass
          NULL for these three (backfill/backfill.py). `COALESCE(EXCLUDED.x,
          klines_1m.x)` prefers the INCOMING value whenever it is
          non-NULL (a genuine upgrade from unknown, or a legitimate
          correction of an already-known value) and otherwise preserves
          the already-known stored value -- an incoming NULL (a
          lower-fidelity backfill row) can never erase already-known data.
        - source: 'live' | 'backfill' provenance tag. Because the three
          optional fields above can now survive an overwriting write, the
          tag must not silently relabel a row 'backfill' when its retained
          optional fields are still exclusively live-sourced -- that would
          misrepresent where the row's actual (surviving) data came from.
          The CASE below preserves the stored 'live' tag only when the
          incoming row supplies NO taker-fidelity data of its own (all
          three columns NULL) -- i.e. exactly the case where every
          retained optional-field value came from the OLD row. The moment
          the incoming row supplies real data in ANY of the three columns
          (a genuine upgrade or correction) -- or the stored row was never
          'live' to begin with -- the incoming write's own source label is
          trusted, since it is now genuinely contributing to (or fully
          re-asserting) the row's content.

        V2-H2e: this write and its invalidation detection are ONE
        transaction. `RETURNING ... (xmax <> 0) AS was_correction` reports,
        per row, whether the row already existed (a genuine correction —
        `_on_bar_closed` only ever calls this on a bar's own close, so a
        live re-hit of an existing key is never a still-forming-bar
        rewrite). Deliberately conservative: this does NOT compare old vs.
        new values (an identical-value re-write still counts as a
        correction). A genuinely first-ever insert (`xmax = 0`) is ALSO
        checked (`_fresh_rows_affect_published_bucket`) -- a late gap-fill
        landing inside an already-published bucket invalidates it just as
        much as an update would (finding 2, tech-lead review round 2).
        Every invalidating `(exchange, symbol)` bumps its mapped `(symbol,
        market_type)` scope(s)' `stage2_raw_revision` in the SAME
        transaction/COMMIT as this write (§3.4). Malformed/ragged rows and
        in-batch duplicate keys are handled BEFORE any DB call (see
        `_validate_row_arity`/`_dedupe_last_write_wins`) -- the returned
        count reflects the DEDUPED row count (the number of distinct
        `(exchange, symbol, ts)` identities actually written), not the raw
        input length, since a shadowed in-batch duplicate was never a
        separate persisted row under either the old or new writer shape."""
        if not rows:
            return 0
        _validate_row_arity(rows, 11, "insert_klines")
        rows = _dedupe_last_write_wins(rows, key_indices=(0, 1, 2))
        assert self.pool is not None
        cols = list(zip(*rows))
        (exchanges, symbols, tss, opens, highs, lows, closes, volumes,
         taker_buys, taker_sells, trades_counts) = cols
        sources = [source] * len(rows)
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                returned = await conn.fetch(
                    """
                    INSERT INTO klines_1m
                        (exchange, symbol, ts, open, high, low, close, volume,
                         taker_buy_volume, taker_sell_volume, trades_count, source)
                    SELECT * FROM unnest(
                        $1::text[], $2::text[], $3::timestamptz[], $4::float8[],
                        $5::float8[], $6::float8[], $7::float8[], $8::float8[],
                        $9::float8[], $10::float8[], $11::int[], $12::text[])
                    ON CONFLICT (exchange, symbol, ts) DO UPDATE SET
                        open = EXCLUDED.open, high = EXCLUDED.high,
                        low = EXCLUDED.low, close = EXCLUDED.close,
                        volume = EXCLUDED.volume,
                        taker_buy_volume = COALESCE(EXCLUDED.taker_buy_volume,
                                                     klines_1m.taker_buy_volume),
                        taker_sell_volume = COALESCE(EXCLUDED.taker_sell_volume,
                                                      klines_1m.taker_sell_volume),
                        trades_count = COALESCE(EXCLUDED.trades_count,
                                                 klines_1m.trades_count),
                        source = CASE
                            WHEN klines_1m.source = 'live'
                                 AND EXCLUDED.taker_buy_volume IS NULL
                                 AND EXCLUDED.taker_sell_volume IS NULL
                                 AND EXCLUDED.trades_count IS NULL
                            THEN klines_1m.source
                            ELSE EXCLUDED.source
                        END
                    RETURNING exchange, symbol, ts, (xmax <> 0) AS was_correction
                    """,
                    list(exchanges), list(symbols), list(tss), list(opens),
                    list(highs), list(lows), list(closes), list(volumes),
                    list(taker_buys), list(taker_sells), list(trades_counts), sources,
                )
                corrected_pairs = {
                    (r["exchange"], r["symbol"]) for r in returned if r["was_correction"]
                }
                fresh_ts_by_pair: "dict" = {}
                for r in returned:
                    if not r["was_correction"]:
                        fresh_ts_by_pair.setdefault((r["exchange"], r["symbol"]), []).append(r["ts"])
                await self._bump_raw_revision_for_write(
                    conn, corrected_pairs=corrected_pairs, fresh_ts_by_pair=fresh_ts_by_pair,
                    reason="RAW_KLINE_WRITE")
        return len(rows)

    async def insert_open_interest(self, rows: Sequence[tuple], source: str) -> int:
        """rows: (exchange, symbol, ts, oi_raw, oi_unit, contract_value,
        oi_base_asset, oi_notional_usd). Legacy oi_contracts/oi_notional are
        kept populated (oi_contracts=oi_raw, oi_notional=oi_notional_usd) for
        continuity, but the oi_unit-tagged columns are the authoritative ones —
        never sum oi_raw across exchanges (units differ).

        V2-H2e: same one-transaction write + `xmax <> 0`/first-insert-into-
        published-bucket invalidation detection + same-COMMIT raw-revision
        bump discipline as `insert_klines` (see its docstring) --
        deliberately conservative, no old-vs-new value comparison for the
        correction case. Malformed/ragged rows and in-batch duplicate keys
        are handled BEFORE any DB call."""
        if not rows:
            return 0
        _validate_row_arity(rows, 8, "insert_open_interest")
        rows = _dedupe_last_write_wins(rows, key_indices=(0, 1, 2))
        assert self.pool is not None
        cols = list(zip(*rows))
        (exchanges, symbols, tss, oi_raws, oi_units, contract_values,
         oi_base_assets, oi_notional_usds) = cols
        sources = [source] * len(rows)
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                returned = await conn.fetch(
                    """
                    INSERT INTO open_interest
                        (exchange, symbol, ts, oi_raw, oi_unit, contract_value,
                         oi_base_asset, oi_notional_usd, oi_contracts, oi_notional, source)
                    SELECT exchange, symbol, ts, oi_raw, oi_unit, contract_value,
                           oi_base_asset, oi_notional_usd, oi_raw, oi_notional_usd, source
                    FROM unnest(
                        $1::text[], $2::text[], $3::timestamptz[], $4::float8[],
                        $5::text[], $6::float8[], $7::text[], $8::float8[], $9::text[])
                        AS t(exchange, symbol, ts, oi_raw, oi_unit, contract_value,
                             oi_base_asset, oi_notional_usd, source)
                    ON CONFLICT (exchange, symbol, ts) DO UPDATE SET
                        oi_raw = EXCLUDED.oi_raw,
                        oi_unit = EXCLUDED.oi_unit,
                        contract_value = EXCLUDED.contract_value,
                        oi_base_asset = EXCLUDED.oi_base_asset,
                        oi_notional_usd = EXCLUDED.oi_notional_usd,
                        oi_contracts = EXCLUDED.oi_contracts,
                        oi_notional = EXCLUDED.oi_notional,
                        source = EXCLUDED.source
                    RETURNING exchange, symbol, ts, (xmax <> 0) AS was_correction
                    """,
                    list(exchanges), list(symbols), list(tss), list(oi_raws),
                    list(oi_units), list(contract_values), list(oi_base_assets),
                    list(oi_notional_usds), sources,
                )
                corrected_pairs = {
                    (r["exchange"], r["symbol"]) for r in returned if r["was_correction"]
                }
                fresh_ts_by_pair: "dict" = {}
                for r in returned:
                    if not r["was_correction"]:
                        fresh_ts_by_pair.setdefault((r["exchange"], r["symbol"]), []).append(r["ts"])
                await self._bump_raw_revision_for_write(
                    conn, corrected_pairs=corrected_pairs, fresh_ts_by_pair=fresh_ts_by_pair,
                    reason="RAW_OPEN_INTEREST_WRITE")
        return len(rows)

    async def insert_funding(self, rows: Sequence[tuple], source: str) -> int:
        """rows: (exchange, symbol, ts, funding_rate, next_funding_time)

        V2-H2e: same one-transaction write + `xmax <> 0`/first-insert-into-
        published-bucket invalidation detection + same-COMMIT raw-revision
        bump discipline as `insert_klines` (see its docstring) --
        deliberately conservative, no old-vs-new value comparison for the
        correction case. Malformed/ragged rows and in-batch duplicate keys
        are handled BEFORE any DB call."""
        if not rows:
            return 0
        _validate_row_arity(rows, 5, "insert_funding")
        rows = _dedupe_last_write_wins(rows, key_indices=(0, 1, 2))
        assert self.pool is not None
        cols = list(zip(*rows))
        exchanges, symbols, tss, funding_rates, next_funding_times = cols
        sources = [source] * len(rows)
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                returned = await conn.fetch(
                    """
                    INSERT INTO funding_rate
                        (exchange, symbol, ts, funding_rate, next_funding_time, source)
                    SELECT * FROM unnest(
                        $1::text[], $2::text[], $3::timestamptz[], $4::float8[],
                        $5::timestamptz[], $6::text[])
                    ON CONFLICT (exchange, symbol, ts) DO UPDATE SET
                        funding_rate = EXCLUDED.funding_rate,
                        next_funding_time = EXCLUDED.next_funding_time,
                        source = EXCLUDED.source
                    RETURNING exchange, symbol, ts, (xmax <> 0) AS was_correction
                    """,
                    list(exchanges), list(symbols), list(tss), list(funding_rates),
                    list(next_funding_times), sources,
                )
                corrected_pairs = {
                    (r["exchange"], r["symbol"]) for r in returned if r["was_correction"]
                }
                fresh_ts_by_pair: "dict" = {}
                for r in returned:
                    if not r["was_correction"]:
                        fresh_ts_by_pair.setdefault((r["exchange"], r["symbol"]), []).append(r["ts"])
                await self._bump_raw_revision_for_write(
                    conn, corrected_pairs=corrected_pairs, fresh_ts_by_pair=fresh_ts_by_pair,
                    reason="RAW_FUNDING_WRITE")
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

    # ---------------------------------------------------------------
    # V2-H2e: correction-publication coherence barrier
    # (docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md §3.4). See
    # storage/stage2_publication_state.py and storage/v2_coherent_read_session.py
    # module docstrings for the full design rationale (revision-comparison
    # model, tech-lead review round 2).
    # ---------------------------------------------------------------
    async def bootstrap_stage2_raw_revision(self, *, symbol: str, market_type: str) -> str:
        """Idempotently seed `(symbol, market_type)`'s `stage2_raw_revision`
        counter at 0 if it has never been bootstrapped. Returns `"SEEDED"`
        or `"ALREADY_INITIALIZED"`. Safe to call on every startup, mirroring
        `bootstrap_instrument_metadata_revision`.

        Deliberately does NOT touch `stage2_publication_state` -- there is
        no automatic CLEAN bootstrap for any `calculation_version` (fresh
        namespace or legacy pre-H2e database alike); see
        `storage/stage2_publication_state.py`'s module docstring."""
        from storage.stage2_publication_state import bootstrap_raw_revision
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            return await bootstrap_raw_revision(conn, symbol=symbol, market_type=market_type)

    async def fetch_stage2_raw_revision(self, *, symbol: str, market_type: str) -> "Optional[int]":
        """Read-only: the current authoritative `raw_revision` for
        `(symbol, market_type)`, or `None` if never bootstrapped. A future
        publisher reads this BEFORE starting its (possibly slow) derived
        recomputation, then passes the SAME value as
        `expected_raw_revision` to `publish_stage2_correction` -- the
        compare-and-swap that rejects a stale publish (finding 1)."""
        from storage.stage2_publication_state import read_raw_revision
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            return await read_raw_revision(conn, symbol=symbol, market_type=market_type)

    async def fetch_stage2_publication_state(
        self, *, symbol: str, market_type: str, calculation_version: str,
    ):
        """Read-only: the current `PublicationState` for `(symbol,
        market_type, calculation_version)`, or `None` if
        `stage2_raw_revision` itself has never been bootstrapped for this
        `(symbol, market_type)`. For status/CLI reporting only — NOT the
        fail-closed gate a V2 read session uses (that check happens inside
        `open_v2_coherent_read_session`'s own transaction, not via this
        method)."""
        from storage.stage2_publication_state import read_publication_state
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            return await read_publication_state(
                conn, symbol=symbol, market_type=market_type,
                calculation_version=calculation_version)

    @staticmethod
    def _check_publication_batch_scope(
        rows: "Sequence", *, family_name: str, symbol: str, market_type: str,
        calculation_version: str,
    ) -> None:
        """Every row in a `publish_stage2_correction` batch MUST belong to
        the EXACT declared `(symbol, market_type, calculation_version)`
        scope -- checked against the raw dataclass instances, BEFORE
        `serialize_batch`/any connection is acquired (finding 5B/5C). A
        caller must never be able to declare scope BTC/perp, silently
        write rows for a different scope inside the same batch, and mark
        BTC/perp CLEAN."""
        for i, row in enumerate(rows):
            if getattr(row, "symbol", None) != symbol:
                raise ValueError(
                    f"publish_stage2_correction: {family_name}[{i}].symbol="
                    f"{getattr(row, 'symbol', None)!r} does not match declared symbol={symbol!r}")
            if getattr(row, "market_type", None) != market_type:
                raise ValueError(
                    f"publish_stage2_correction: {family_name}[{i}].market_type="
                    f"{getattr(row, 'market_type', None)!r} does not match declared "
                    f"market_type={market_type!r}")
            if getattr(row, "calculation_version", None) != calculation_version:
                raise ValueError(
                    f"publish_stage2_correction: {family_name}[{i}].calculation_version="
                    f"{getattr(row, 'calculation_version', None)!r} does not match declared "
                    f"calculation_version={calculation_version!r} -- mixed/wrong-version "
                    "batches are rejected before any connection is acquired")

    async def publish_stage2_correction(
        self, *, symbol: str, market_type: str, calculation_version: str,
        expected_raw_revision: int,
        exchange_feature_vectors: "Sequence[ExchangeFeatureVector]",
        consensus_feature_vectors: "Sequence[ConsensusFeatureVector]",
        percentile_snapshots: "Sequence[PercentileSnapshot]" = (),
        data_health_snapshots: "Sequence[DataHealthSnapshot]" = (),
        percentile_snapshots_absent_reason: "Optional[str]" = None,
        data_health_snapshots_absent_reason: "Optional[str]" = None,
    ) -> "Stage2PublicationResult":
        """Atomically publish ONE complete Stage 2 correction generation for
        `(symbol, market_type, calculation_version)`, CAS'd against
        `expected_raw_revision`, in ONE transaction — the narrowest new
        write primitive §3.4 requires ("V2 MAY only consume a Stage 2
        correction generation/publication that is complete as a coherent
        published unit"). Reuses the existing `Stage2WriterSpec`/
        `serialize_batch` validation contracts unchanged for row shape;
        this method ADDS scope/version-binding and completeness validation
        of its own (tech-lead review round 2, finding 5).

        Compare-and-swap (finding 1): `expected_raw_revision` MUST be the
        `stage2_raw_revision` value the caller's derived computation was
        performed against (read earlier via `fetch_stage2_raw_revision`).
        Inside this transaction, `mark_publication_clean_cas` locks the
        authoritative row (`SELECT ... FOR UPDATE`) and compares it against
        `expected_raw_revision` — if a LATER correction committed in the
        meantime, this raises `V2StalePublicationError` and the WHOLE
        transaction (every family write already issued) rolls back. A
        stale publisher can therefore never clean a newer correction.

        Every batch is validated (arity/type via `serialize_batch`, AND
        scope/version binding via `_check_publication_batch_scope`) BEFORE
        any connection is acquired, so a malformed or wrong-scope batch can
        never partially write. `exchange_feature_vectors`/
        `consensus_feature_vectors` are MANDATORY (finding 5A) — an empty
        sequence for either raises before any connection is acquired; call
        this method only once real recomputed rows exist for both.

        Truthful-absence discipline (§13/§14, hardened per finding 5D): an
        empty `percentile_snapshots`/`data_health_snapshots` is accepted
        ONLY if, INSIDE this same transaction, this exact `(symbol,
        market_type, calculation_version)` genuinely has ZERO existing rows
        in that family — i.e. the family has never applied to this
        scope+version at all, a real DB-provable N/A, not a caller's
        say-so. If rows already exist for this scope+version, an empty
        batch is REJECTED regardless of any `..._absent_reason` string —
        "no orchestrator implemented" is a reason the family is not
        computed, never proof that already-published percentile/health
        history remains correct after the correction. The `..._absent_reason`
        string is retained as required, human-readable context (for D-008
        traceability) but is NOT itself the completeness proof."""
        from storage.stage2_publication_state import Stage2PublicationResult, mark_publication_clean_cas
        from storage.stage2_serialization import (
            CONSENSUS_FEATURE_SPEC, DATA_HEALTH_SNAPSHOT_SPEC, EXCHANGE_FEATURE_SPEC,
            PERCENTILE_SNAPSHOT_SPEC, serialize_batch)

        if not exchange_feature_vectors:
            raise ValueError(
                "publish_stage2_correction: exchange_feature_vectors is empty -- this family is "
                "mandatory (finding 5A); call this method only once real recomputed rows exist")
        if not consensus_feature_vectors:
            raise ValueError(
                "publish_stage2_correction: consensus_feature_vectors is empty -- this family is "
                "mandatory (finding 5A); call this method only once real recomputed rows exist")

        self._check_publication_batch_scope(
            exchange_feature_vectors, family_name="exchange_feature_vectors",
            symbol=symbol, market_type=market_type, calculation_version=calculation_version)
        self._check_publication_batch_scope(
            consensus_feature_vectors, family_name="consensus_feature_vectors",
            symbol=symbol, market_type=market_type, calculation_version=calculation_version)
        self._check_publication_batch_scope(
            percentile_snapshots, family_name="percentile_snapshots",
            symbol=symbol, market_type=market_type, calculation_version=calculation_version)
        self._check_publication_batch_scope(
            data_health_snapshots, family_name="data_health_snapshots",
            symbol=symbol, market_type=market_type, calculation_version=calculation_version)

        if not percentile_snapshots and not (
            isinstance(percentile_snapshots_absent_reason, str)
            and percentile_snapshots_absent_reason.strip()
        ):
            raise ValueError(
                "publish_stage2_correction: percentile_snapshots is empty and no "
                "percentile_snapshots_absent_reason was given -- publication must not "
                "silently omit the percentile family (§13)")
        if not data_health_snapshots and not (
            isinstance(data_health_snapshots_absent_reason, str)
            and data_health_snapshots_absent_reason.strip()
        ):
            raise ValueError(
                "publish_stage2_correction: data_health_snapshots is empty and no "
                "data_health_snapshots_absent_reason was given -- publication must not "
                "silently omit the health-snapshot family (§14)")

        efv_params = serialize_batch(EXCHANGE_FEATURE_SPEC, exchange_feature_vectors)
        cfv_params = serialize_batch(CONSENSUS_FEATURE_SPEC, consensus_feature_vectors)
        ps_params = serialize_batch(PERCENTILE_SNAPSHOT_SPEC, percentile_snapshots)
        dhs_params = serialize_batch(DATA_HEALTH_SNAPSHOT_SPEC, data_health_snapshots)

        assert self.pool is not None
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                if not ps_params:
                    affected = await conn.fetchval(
                        "SELECT EXISTS (SELECT 1 FROM percentile_snapshots "
                        "WHERE symbol=$1 AND market_type=$2 AND calculation_version=$3)",
                        symbol, market_type, calculation_version)
                    if affected:
                        raise ValueError(
                            "publish_stage2_correction: percentile_snapshots is empty but "
                            f"percentile_snapshots ALREADY has rows for symbol={symbol!r} "
                            f"market_type={market_type!r} calculation_version="
                            f"{calculation_version!r} -- this family is NOT provably N/A for this "
                            "correction; an absent_reason string cannot substitute for a real "
                            "recompute (finding 5D)")
                if not dhs_params:
                    affected = await conn.fetchval(
                        "SELECT EXISTS (SELECT 1 FROM data_health_snapshots "
                        "WHERE symbol=$1 AND market_type=$2 AND calculation_version=$3)",
                        symbol, market_type, calculation_version)
                    if affected:
                        raise ValueError(
                            "publish_stage2_correction: data_health_snapshots is empty but "
                            f"data_health_snapshots ALREADY has rows for symbol={symbol!r} "
                            f"market_type={market_type!r} calculation_version="
                            f"{calculation_version!r} -- this family is NOT provably N/A for this "
                            "correction; an absent_reason string cannot substitute for a real "
                            "recompute (finding 5D)")

                await conn.executemany(EXCHANGE_FEATURE_SPEC.insert_sql, efv_params)
                await conn.executemany(CONSENSUS_FEATURE_SPEC.insert_sql, cfv_params)
                if ps_params:
                    await conn.executemany(PERCENTILE_SNAPSHOT_SPEC.insert_sql, ps_params)
                if dhs_params:
                    await conn.executemany(DATA_HEALTH_SNAPSHOT_SPEC.insert_sql, dhs_params)
                generation = await mark_publication_clean_cas(
                    conn, symbol=symbol, market_type=market_type,
                    calculation_version=calculation_version,
                    expected_raw_revision=expected_raw_revision)
        return Stage2PublicationResult(
            symbol=symbol, market_type=market_type, calculation_version=calculation_version,
            published_raw_revision=expected_raw_revision, publication_generation=generation,
            exchange_feature_vectors_written=len(efv_params),
            consensus_feature_vectors_written=len(cfv_params),
            percentile_snapshots_written=len(ps_params),
            data_health_snapshots_written=len(dhs_params),
            percentile_snapshots_absent_reason=(None if ps_params else percentile_snapshots_absent_reason),
            data_health_snapshots_absent_reason=(None if dhs_params else data_health_snapshots_absent_reason),
        )

    @contextlib.asynccontextmanager
    async def open_v2_coherent_read_session(
        self, *, symbol: str, market_type: str, calculation_version: str,
    ):
        """The canonical ONE-coherent-V2-read-session context manager (§3.4).

        `async with db.open_v2_coherent_read_session(symbol=..., market_type=..., calculation_version=...) as session:`
        acquires ONE connection, opens ONE `REPEATABLE READ, readonly`
        transaction on it, and — as the FIRST read inside that transaction,
        before anything else — reads the combined `PublicationState` for
        `(symbol, market_type, calculation_version)`. If it is missing or
        not CLEAN, this raises `V2PublicationDirtyError` immediately (fail
        closed) and the transaction is rolled back without ever yielding a
        session — no Stage 3/5 read is ever attempted for a non-CLEAN
        scope+version.

        Otherwise it yields a `V2CoherentReadSession` BOUND to this exact
        `(symbol, market_type, calculation_version)` identity (tech-lead
        review round 2, finding 4 -- "session identity binding"): every
        read method checks its OWN `symbol`/`market_type`/
        `calculation_version` arguments against the session's bound
        identity BEFORE issuing any SQL, and raises if they differ. This
        closes the gap where a session proven CLEAN for calculation_version
        A could otherwise be used, unchecked, to read calculation_version B
        (which might be STALE) through the very same object. Every read
        issued through the session (structurally satisfying both
        `V2AlignedInputReader` and `V2SetupHistoryReader`,
        `analytics/forecasting_v2/ports.py`) observes the exact snapshot
        pinned when the state check ran, so a correction committed after
        this session opened is invisible to it, and there is no code path
        that re-acquires a second connection mid-session."""
        from storage.stage2_publication_state import (
            V2PublicationDirtyError, read_publication_state)
        from storage.v2_coherent_read_session import V2CoherentReadSession

        assert self.pool is not None
        async with self.pool.acquire() as conn:
            async with conn.transaction(isolation="repeatable_read", readonly=True):
                state = await read_publication_state(
                    conn, symbol=symbol, market_type=market_type,
                    calculation_version=calculation_version)
                if state is None or not state.is_clean:
                    raise V2PublicationDirtyError(
                        symbol=symbol, market_type=market_type,
                        calculation_version=calculation_version,
                        status=(state.status if state is not None else "UNINITIALIZED"))
                yield V2CoherentReadSession(
                    conn, symbol=symbol, market_type=market_type,
                    calculation_version=calculation_version)

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
    # V2-H2b: DRAIN-BEFORE-ACTIVATE version-switch state
    # (docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md §3.1). Delegates all
    # SQL/row-parsing to storage/v2_version_switch_readers.py and the pure
    # transition decision to
    # analytics/forecasting_v2/version_switch_orchestrator.py — this
    # method owns ONLY the real transactional row lock/atomicity.
    # ---------------------------------------------------------------
    async def evaluate_v2_version_switch(
        self, *, run_kind: str, run_id: str, decision_boundary: datetime,
        symbol: str, market_type: str, requested=None,
        readiness_reader, drain_reader,
    ):
        """Real, atomic entry point for one legal 5m decision boundary's
        version-switch evaluation. Wraps `bootstrap_and_lock_v2_version_
        switch_state()` (idempotent bootstrap + `SELECT ... FOR UPDATE`
        row lock) and `resolve_version_switch_transition()` (the async
        orchestration boundary, which itself calls the PURE
        `version_switch.evaluate_version_switch_transition()`) inside ONE
        transaction on ONE connection, then persists the resolved next
        state on the SAME connection/transaction before releasing the
        lock. A concurrent caller evaluating the SAME `(run_kind, run_id)`
        blocks at the row lock until this transaction commits or rolls
        back — no torn/interleaved read, no partial-write state ever
        becomes visible (a raised exception anywhere inside this method
        rolls the whole transaction back; the row is left exactly as it
        was before this call — `conn.transaction()`'s own guarantee, not
        anything this method implements itself).

        Returns the `V2VersionSwitchTransitionResult` — see
        `analytics/forecasting_v2/version_switch.py`/
        `version_switch_orchestrator.py` for its shape and the exact
        contract semantics this implements."""
        from analytics.forecasting_v2.version_switch_orchestrator import (
            resolve_version_switch_transition)
        from storage.v2_version_switch_readers import (
            bootstrap_and_lock_v2_version_switch_state, persist_v2_version_switch_state)
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                state = await bootstrap_and_lock_v2_version_switch_state(
                    conn, run_kind=run_kind, run_id=run_id)
                result = await resolve_version_switch_transition(
                    state=state, decision_boundary=decision_boundary, symbol=symbol,
                    market_type=market_type, requested=requested,
                    readiness_reader=readiness_reader, drain_reader=drain_reader)
                if result.state != state:
                    await persist_v2_version_switch_state(conn, result.state)
                return result

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

    async def fetch_v2_reference_feature(
        self, *, exchange: str, symbol: str, market_type: str, timeframe: str,
        bucket_ts: datetime, calculation_version: str,
    ) -> "Optional[Mapping]":
        """Read-only: the ONE `exchange_feature_vectors` row at the EXACT
        `(exchange, symbol, market_type, timeframe, bucket_ts,
        calculation_version)` identity, or `None` if absent — never an
        older bucket. This wrapper is generic about `exchange`; pinning it
        to the canonical V2 reference exchange is the analytics layer's
        job (`analytics/forecasting_v2/aligned_inputs.py`, §11). See
        `storage/v2_alignment_readers.py::read_v2_reference_feature` for
        the full contract."""
        from storage.v2_alignment_readers import (
            read_v2_reference_feature, validate_reference_feature_args)
        validate_reference_feature_args(
            exchange=exchange, symbol=symbol, market_type=market_type, timeframe=timeframe,
            bucket_ts=bucket_ts, calculation_version=calculation_version)
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            return await read_v2_reference_feature(
                conn, exchange=exchange, symbol=symbol, market_type=market_type,
                timeframe=timeframe, bucket_ts=bucket_ts, calculation_version=calculation_version)

    async def fetch_v2_reference_klines(
        self, *, exchange: str, symbol: str, bucket_start: datetime, bucket_end: datetime,
    ) -> "tuple[Mapping, ...]":
        """Read-only: raw `klines_1m` bars for one `exchange`/`symbol`
        inside the caller-supplied half-open interval `[bucket_start,
        bucket_end)` — deterministic historical boundaries only, never a
        wall clock. See
        `storage/v2_alignment_readers.py::read_v2_reference_klines` for
        the full contract."""
        from storage.v2_alignment_readers import (
            read_v2_reference_klines, validate_reference_klines_args)
        validate_reference_klines_args(
            exchange=exchange, symbol=symbol, bucket_start=bucket_start, bucket_end=bucket_end)
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            return await read_v2_reference_klines(
                conn, exchange=exchange, symbol=symbol,
                bucket_start=bucket_start, bucket_end=bucket_end)

    # ---------------------------------------------------------------
    # V2 setup-detector historical-window readers (Stage 5 — Setup
    # Detectors PR 1, ADDITIVE, READ-ONLY). Delegates all SQL/row-parsing
    # to storage/v2_setup_readers.py; arguments are validated BEFORE a
    # connection is acquired. No analytics decision is made here — these
    # wrappers exist to return exactly the requested historical Stage 2
    # rows, or whichever subset physically exists, never a fabricated or
    # wall-clock "latest" substitute.
    # ---------------------------------------------------------------
    async def fetch_v2_consensus_feature_window(
        self, *, symbol: str, market_type: str, timeframe: str,
        bucket_start: datetime, bucket_end: datetime, calculation_version: str,
    ) -> "tuple[Mapping, ...]":
        """Read-only: every `consensus_feature_vectors` row for one exact
        `(symbol, market_type, timeframe, calculation_version)` identity
        whose `bucket_ts` falls inside the INCLUSIVE `[bucket_start,
        bucket_end]` interval, ordered ascending by `bucket_ts`. Only
        physically present rows are returned. See
        `storage/v2_setup_readers.py::read_v2_consensus_feature_window`
        for the full contract."""
        from storage.v2_setup_readers import (
            read_v2_consensus_feature_window, validate_consensus_feature_window_args)
        validate_consensus_feature_window_args(
            symbol=symbol, market_type=market_type, timeframe=timeframe,
            bucket_start=bucket_start, bucket_end=bucket_end,
            calculation_version=calculation_version)
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            return await read_v2_consensus_feature_window(
                conn, symbol=symbol, market_type=market_type, timeframe=timeframe,
                bucket_start=bucket_start, bucket_end=bucket_end,
                calculation_version=calculation_version)

    async def fetch_v2_consensus_percentile_window(
        self, *, symbol: str, market_type: str, metric: str, timeframe: str,
        percentile_window: str, bucket_start: datetime, bucket_end: datetime,
        calculation_version: str,
    ) -> "tuple[Mapping, ...]":
        """Read-only: every consensus-scope `percentile_snapshots` row for
        one exact `(symbol, market_type, metric, timeframe,
        percentile_window, calculation_version)` identity whose
        `bucket_ts` falls inside the INCLUSIVE `[bucket_start,
        bucket_end]` interval, ordered ascending by `bucket_ts`. See
        `storage/v2_setup_readers.py::read_v2_consensus_percentile_window`
        for the full contract."""
        from storage.v2_setup_readers import (
            read_v2_consensus_percentile_window, validate_consensus_percentile_window_args)
        validate_consensus_percentile_window_args(
            symbol=symbol, market_type=market_type, metric=metric, timeframe=timeframe,
            percentile_window=percentile_window, bucket_start=bucket_start,
            bucket_end=bucket_end, calculation_version=calculation_version)
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            return await read_v2_consensus_percentile_window(
                conn, symbol=symbol, market_type=market_type, metric=metric,
                timeframe=timeframe, percentile_window=percentile_window,
                bucket_start=bucket_start, bucket_end=bucket_end,
                calculation_version=calculation_version)

    async def fetch_v2_reference_feature_window(
        self, *, exchange: str, symbol: str, market_type: str, timeframe: str,
        bucket_start: datetime, bucket_end: datetime, calculation_version: str,
    ) -> "tuple[Mapping, ...]":
        """Read-only: every `exchange_feature_vectors` row for one exact
        `(exchange, symbol, market_type, timeframe, calculation_version)`
        identity whose `bucket_ts` falls inside the INCLUSIVE
        `[bucket_start, bucket_end]` interval, ordered ascending by
        `bucket_ts`. This wrapper is generic about `exchange`; pinning it
        to the canonical V2 reference exchange remains the analytics
        layer's job (§11). See
        `storage/v2_setup_readers.py::read_v2_reference_feature_window`
        for the full contract."""
        from storage.v2_setup_readers import (
            read_v2_reference_feature_window, validate_reference_feature_window_args)
        validate_reference_feature_window_args(
            exchange=exchange, symbol=symbol, market_type=market_type, timeframe=timeframe,
            bucket_start=bucket_start, bucket_end=bucket_end,
            calculation_version=calculation_version)
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            return await read_v2_reference_feature_window(
                conn, exchange=exchange, symbol=symbol, market_type=market_type,
                timeframe=timeframe, bucket_start=bucket_start, bucket_end=bucket_end,
                calculation_version=calculation_version)

    async def fetch_v2_instrument(
        self, *, exchange: str, symbol: str, market_type: str, as_of: datetime,
    ) -> "Optional[Mapping]":
        """Read-only (V2-H2c): the ONE `exchange_instrument_history` row
        whose validity interval covers `as_of`, for the EXACT `(exchange,
        symbol, market_type)` identity, or `None` if no such historical
        version exists — never the current `exchange_instruments` LKG
        row, never a future version. See
        `storage/v2_setup_readers.py::read_v2_instrument` for the full
        contract."""
        from storage.v2_setup_readers import read_v2_instrument, validate_instrument_args
        validate_instrument_args(exchange=exchange, symbol=symbol, market_type=market_type, as_of=as_of)
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            return await read_v2_instrument(
                conn, exchange=exchange, symbol=symbol, market_type=market_type, as_of=as_of)

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
