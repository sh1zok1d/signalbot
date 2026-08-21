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
                            await conn.execute(
                                "UPDATE exchange_instrument_history SET effective_until = $1 "
                                "WHERE exchange=$2 AND symbol=$3 AND market_type=$4 "
                                "AND effective_from=$5",
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
        """(Tech-lead review 4991738511, finding 11) Explicit, conservative,
        idempotent bootstrap of the ONE global
        `stage2_instrument_metadata_state` row -- the durable current
        required instrument-metadata revision every Stage 2 feature
        computation (any exchange, any symbol) must agree with. Mirrors
        `seed_current_instrument_history`'s own explicit/conservative/
        idempotent shape exactly.

        `initial_revision` MUST be established explicitly from the caller's
        own resolved Stage 2 configuration (e.g.
        `stage2_config.instrument_metadata_revision`) -- never invented,
        never a timestamp, never hardcoded silently in this method or in
        schema DDL. Returns `"SEEDED"` when it actually inserted the row
        (fresh deployment); returns `"ALREADY_INITIALIZED"` without writing
        anything if a row already exists -- this method NEVER overwrites an
        already-live required revision, however different `initial_revision`
        is on a repeated call; safe to call repeatedly."""
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
                if existing is not None:
                    return "ALREADY_INITIALIZED"
                await conn.execute(
                    "INSERT INTO stage2_instrument_metadata_state "
                    "(singleton, required_revision, updated_at) VALUES (TRUE, $1, now())",
                    initial_revision)
        return "SEEDED"

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
          re-asserting) the row's content."""
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
