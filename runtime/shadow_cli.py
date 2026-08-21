"""
Operational one-shot shadow CLI: --shadow-once / --shadow-dry-run /
--shadow-status.

This is the deliberate MANUAL operational boundary over the pure composition
core `process_shadow_cycle(...)`. It is the layer allowed to read the wall clock,
load configs, resolve the code version, open a network session for one-time
instrument-metadata bootstrap, render human/JSON output, and perform Database
I/O. It duplicates NO analytics formula (features, consensus, forecast, outcome),
contains NO SQL, and adds NO loop/scheduler/recovery/discovery/Telegram/trading.

The one-shot execution APIs here stay bounded to exactly ONE caller-selected
closed 5m bucket, always with `due_outcome_jobs=()`. The bounded automatic
recovery pass (advisory lock, prediction catch-up, outcome maturation) lives in
runtime/shadow_recovery.py; `run_shadow_cli_command` routes an automatic
`--shadow-once` (no explicit bucket) to it, while an explicit `--shadow-bucket-ts`
keeps the deterministic one-bucket behavior here.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import MappingProxyType
from typing import Mapping, Optional, Sequence

from common.config import Config, Secrets
from common.instrument_metadata import InstrumentMetadata, fetch_instrument_metadata
from common.stage2_config import Stage2Config
from common.versioning import resolve_feature_code_version
from storage.db import Database
from symbols.registry import (
    ACTIVE_EXCHANGES, symbol_exchange_capability_seed_rows, symbol_seed_rows,
)

from analytics.forecasting.shadow_cycle import (
    PREDICTION_DUPLICATE, PREDICTION_INSERTED,
    PREDICTION_SKIPPED_NO_CONSENSUS, PREDICTION_SKIPPED_REFERENCE_UNAVAILABLE,
    ShadowCycleResult, process_shadow_cycle,
)

# ---- stable command / bucket / status constants ----------------------------
SHADOW_ONCE = "SHADOW_ONCE"
SHADOW_DRY_RUN = "SHADOW_DRY_RUN"
SHADOW_STATUS = "SHADOW_STATUS"

BUCKET_AUTO = "AUTO"
BUCKET_EXPLICIT = "EXPLICIT"

STATUS_NOT_INITIALIZED = "NOT_INITIALIZED"
STATUS_PARTIAL_SCHEMA = "PARTIAL_SCHEMA"
STATUS_EMPTY = "EMPTY"
STATUS_READY = "READY"
_STATUS_STATES = (STATUS_NOT_INITIALIZED, STATUS_PARTIAL_SCHEMA, STATUS_EMPTY, STATUS_READY)

_MARKET_TYPE = "perp"
_TIMEFRAME = "5m"
_BUCKET_MINUTES = 5


class ShadowCliError(RuntimeError):
    """Operational shadow-CLI failure: invalid CLI/config/time input, a missing
    prerequisite, or an impossible operational state. Analytics/model validation
    errors and metadata errors propagate unchanged (never swallowed)."""


# ============================================================================
# Pure time helpers
# ============================================================================
def _is_utc_aware(dt) -> bool:
    return isinstance(dt, datetime) and dt.tzinfo is not None \
        and dt.utcoffset() == timedelta(0)


def select_latest_closed_5m_bucket(now: datetime, *, soft_grace_s: int) -> datetime:
    """Pure: the OPEN timestamp of the most recent fully-closed 5m bucket at
    `now`, applying a soft grace. No I/O. Result is UTC, whole-minute, 5m aligned.

        effective = now - soft_grace_s
        closed_boundary = floor(effective to 5m)
        bucket_ts = closed_boundary - 5m
    """
    if type(now) is not datetime or now.tzinfo is None or now.utcoffset() != timedelta(0):
        raise ShadowCliError("now must be a timezone-aware UTC datetime")
    if type(soft_grace_s) is not int:  # exact int; reject bool
        raise ShadowCliError("soft_grace_s must be an int")
    if soft_grace_s < 0:
        raise ShadowCliError("soft_grace_s must be >= 0")
    effective = now - timedelta(seconds=soft_grace_s)
    floored_minute = (effective.minute // _BUCKET_MINUTES) * _BUCKET_MINUTES
    closed_boundary = effective.replace(minute=floored_minute, second=0, microsecond=0)
    return closed_boundary - timedelta(minutes=_BUCKET_MINUTES)


def parse_shadow_bucket_ts(value: str, *, now: datetime) -> datetime:
    """Parse an explicit ISO-8601 UTC bucket-open timestamp. Accepts `Z` or
    `+00:00`. Rejects blank/malformed/naive/non-UTC/seconds/non-5m and any bucket
    whose end (open + 5m) is after `now`. Historical closed buckets are allowed.
    Never silently rounds the supplied value."""
    if not _is_utc_aware(now):
        raise ShadowCliError("now must be a timezone-aware UTC datetime")
    if not isinstance(value, str) or not value.strip():
        raise ShadowCliError("shadow-bucket-ts must be a non-empty ISO-8601 UTC timestamp")
    text = value.strip()
    iso = (text[:-1] + "+00:00") if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(iso)
    except ValueError:
        raise ShadowCliError(f"malformed shadow-bucket-ts {value!r}") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ShadowCliError("shadow-bucket-ts must include a timezone (Z or +00:00)")
    if parsed.utcoffset() != timedelta(0):
        raise ShadowCliError("shadow-bucket-ts must be UTC (offset 0)")
    parsed = parsed.astimezone(timezone.utc)  # identity for offset 0 (no shift)
    if parsed.second != 0 or parsed.microsecond != 0:
        raise ShadowCliError("shadow-bucket-ts must be on a whole minute (no seconds)")
    if parsed.minute % _BUCKET_MINUTES != 0:
        raise ShadowCliError("shadow-bucket-ts must be aligned to the 5m grid")
    if parsed + timedelta(minutes=_BUCKET_MINUTES) > now:
        raise ShadowCliError("shadow-bucket-ts is not a closed bucket (bucket end is after now)")
    return parsed


# ============================================================================
# Config scope resolution
# ============================================================================
def _validate_active_exchanges(active) -> tuple[str, ...]:
    if isinstance(active, (str, bytes, bytearray)) or not isinstance(active, Sequence):
        raise ShadowCliError("active_exchanges must be a non-empty sequence")
    values = tuple(active)
    if not values:
        raise ShadowCliError("active_exchanges must be non-empty")
    seen: set[str] = set()
    for ex in values:
        if not isinstance(ex, str) or ex not in ACTIVE_EXCHANGES:
            raise ShadowCliError(
                f"active_exchanges contains a non-canonical exchange {ex!r} "
                f"(canonical: {list(ACTIVE_EXCHANGES)})")
        if ex in seen:
            raise ShadowCliError(f"duplicate active exchange {ex!r}")
        seen.add(ex)
    return values


def _resolve_shadow_scope(stage1_config, stage2_config, *, reference_exchange=None):
    """Resolve and validate the operational scope from the real configs (no
    fallback to BTCUSDT/Binance). Returns (symbol, active_exchanges, resolved)."""
    symbol = stage1_config.symbol
    if not isinstance(symbol, str) or not symbol.strip():
        raise ShadowCliError("stage1 symbol must be a non-empty string")
    resolved = stage2_config.resolve(symbol)  # Stage2ConfigError if unknown/malformed
    if resolved.enabled is not True:
        raise ShadowCliError(f"symbol {symbol!r} is not enabled in Stage 2 config")
    if _MARKET_TYPE not in tuple(resolved.market_types):
        raise ShadowCliError(f"symbol {symbol!r} does not declare market_type {_MARKET_TYPE!r}")
    if _TIMEFRAME not in tuple(resolved.get("timeframes", ())):
        raise ShadowCliError(f"symbol {symbol!r} does not declare timeframe {_TIMEFRAME!r}")

    active_raw = stage2_config.get("active_exchanges")
    if active_raw is None:
        raise ShadowCliError("stage2 config is missing active_exchanges")
    exchanges = _validate_active_exchanges(active_raw)

    enabled1 = set(stage1_config.enabled_exchanges)
    for ex in exchanges:
        if ex not in enabled1:
            raise ShadowCliError(
                f"Stage 2 active exchange {ex!r} is not in Stage 1 enabled_exchanges")

    if reference_exchange is not None:
        if not isinstance(reference_exchange, str) or reference_exchange not in ACTIVE_EXCHANGES:
            raise ShadowCliError(f"reference_exchange {reference_exchange!r} is not canonical")
        if reference_exchange not in exchanges:
            raise ShadowCliError(
                f"reference_exchange {reference_exchange!r} is not among the active "
                f"exchanges {list(exchanges)}")
    return symbol, exchanges, resolved


def _resolve_bucket(now, explicit_bucket_ts, resolved) -> tuple[str, datetime]:
    if explicit_bucket_ts is not None:
        return BUCKET_EXPLICIT, parse_shadow_bucket_ts(explicit_bucket_ts, now=now)
    soft_grace_s = resolved["bucket_close"]["soft_grace_s"]
    return BUCKET_AUTO, select_latest_closed_5m_bucket(now, soft_grace_s=soft_grace_s)


# ============================================================================
# Instrument metadata bootstrap (one-shot only)
# ============================================================================
def _record_to_metadata(row) -> InstrumentMetadata:
    """Convert an existing exchange_instruments row into a real InstrumentMetadata
    last-known-good, so a failed refresh can fall back to it (as stale)."""
    return InstrumentMetadata(
        exchange=row["exchange"], symbol=row["symbol"], market_type=row["market_type"],
        exchange_instrument_id=row["exchange_instrument_id"],
        quantity_unit=row["quantity_unit"], contract_multiplier=row["contract_multiplier"],
        tick_size=row["tick_size"], price_precision=row["price_precision"],
        quantity_precision=row["quantity_precision"], metadata_source=row["metadata_source"],
        fetched_at=row["fetched_at"], is_stale=row["is_stale"], note=row["note"] or "")


async def _bootstrap_one_instrument(db, exchange, symbol, fetch_json) -> None:
    existing = await db.get_exchange_instrument(exchange, symbol, _MARKET_TYPE)
    if existing is not None and existing["is_stale"] is False:
        return  # a fresh row is retained as-is: no network, no rewrite
    lkg = _record_to_metadata(existing) if existing is not None else None
    # common.instrument_metadata owns parsing / shared symbol mapping / mismatch
    # detection / fail-closed OKX ctVal behavior — all of it propagates unchanged.
    fresh = await fetch_instrument_metadata(
        exchange, symbol, fetch_json, market_type=_MARKET_TYPE, lkg=lkg)
    await db.upsert_exchange_instrument(
        exchange=fresh.exchange, symbol=fresh.symbol, market_type=fresh.market_type,
        exchange_instrument_id=fresh.exchange_instrument_id,
        quantity_unit=fresh.quantity_unit, contract_multiplier=fresh.contract_multiplier,
        tick_size=fresh.tick_size, price_precision=fresh.price_precision,
        quantity_precision=fresh.quantity_precision, metadata_source=fresh.metadata_source,
        fetched_at=fresh.fetched_at, is_stale=fresh.is_stale, note=fresh.note or "",
        accept_mismatch=False,
        # V2-H2c (tech-lead review 4990482334, finding 1): this bootstrap
        # path never deliberately accepts a CRITICAL mismatch (accept_
        # mismatch=False -- fetch_instrument_metadata() itself already
        # raised MetadataMismatchError upstream before fresh could differ
        # on any critical field vs the existing LKG), so there is no OLD
        # value's already-made LIVE decisions to protect against here --
        # effective_from safely equals this fetch's own observation time.
        effective_from=fresh.fetched_at)


async def _bootstrap_instrument_metadata(db, exchanges, symbol, *, metadata_fetch_json) -> None:
    """Sequentially bootstrap missing/stale instrument metadata for each exchange,
    over ONE shared HTTP session (when no fetcher is injected)."""
    if metadata_fetch_json is not None:
        for exchange in exchanges:
            await _bootstrap_one_instrument(db, exchange, symbol, metadata_fetch_json)
        return
    import aiohttp  # operational dependency; imported only when actually fetching

    async with aiohttp.ClientSession() as session:
        async def fetch_json(url, params):
            async with session.get(url, params=params) as resp:
                resp.raise_for_status()
                return await resp.json()

        for exchange in exchanges:
            await _bootstrap_one_instrument(db, exchange, symbol, fetch_json)


async def _bootstrap_stage2_schema_and_revision(
    db, stage2_config: Stage2Config, symbol: str,
) -> None:
    """(Tech-lead review 4992495660, findings 1/2) The ONE shared bootstrap
    order both write-capable Stage 2 entry points (`execute_shadow_once` and
    `runtime/shadow_recovery.py::execute_shadow_recovery`) must follow --
    never duplicated separately, never reordered.

    `stage2_instrument_metadata_state` is now a MANDATORY prerequisite for
    every Stage-2 raw-bundle read (`storage/stage2_readers.py::
    read_exchange_feature_raw_bundle` raises if its one singleton row is
    absent) and for every deliberate critical-metadata acceptance
    (`Database.upsert_exchange_instrument`'s `accept_mismatch=True` path).
    `init_stage2_schema()` only CREATEs the table -- it does not, and must
    not, seed a row (no hardcoded DDL literal; see that table's own
    schema comment). This helper establishes/verifies that row explicitly,
    from `stage2_config.instrument_metadata_revision`, immediately after
    schema init and strictly BEFORE any structural seed, any instrument-
    metadata upsert, or any Stage-2 raw-bundle read -- never bootstrapped
    separately per exchange/symbol (it is one GLOBAL row, not a per-
    identity fact).

    `Database.bootstrap_instrument_metadata_revision` itself fails closed
    (raises) if a persisted `required_revision` already exists and differs
    from `stage2_config.instrument_metadata_revision` -- this helper does
    not swallow or soften that; a stale deployed config must be fixed by
    the operator, never silently overwritten.

    (V2-H2e) Also idempotently bootstraps `stage2_raw_revision` for
    `(symbol, _MARKET_TYPE)` at revision 0 if it has never been seeded --
    ONLY that counter, never `stage2_publication_state`. This does NOT
    make the correction-publication coherence barrier
    (`Database.open_v2_coherent_read_session`, §3.4) report CLEAN: a scope
    with no `stage2_publication_state` row for a given
    `calculation_version` reads `NEVER_PUBLISHED` (fail-closed,
    structurally identical to STALE) regardless of what `stage2_raw_revision`
    says. Only a real, CAS-verified `Database.publish_stage2_correction`
    call ever creates/updates a `stage2_publication_state` row -- there is
    no automatic CLEAN bootstrap for any scope, fresh or legacy (see
    `storage/stage2_publication_state.py`'s module docstring)."""
    await db.init_stage2_schema()
    await db.bootstrap_instrument_metadata_revision(
        initial_revision=stage2_config.instrument_metadata_revision)
    await db.bootstrap_stage2_raw_revision(symbol=symbol, market_type=_MARKET_TYPE)


# ============================================================================
# Dry-run in-memory writer (structurally satisfies ShadowCycleWriter)
# ============================================================================
class _InMemoryShadowWriter:
    """Captures detached copies of everything the cycle would persist and performs
    NO DB call. insert_forecast_prediction simulates a first insert (returns True);
    the CLI labels that unambiguously as WOULD_INSERT with writes_enabled=false."""

    def __init__(self) -> None:
        self.exchange_feature_batches: list[tuple] = []
        self.consensus_batches: list[tuple] = []
        self.predictions: list = []
        self.outcome_batches: list[tuple] = []

    @staticmethod
    def _detach(rows):
        if isinstance(rows, (str, bytes, bytearray)) or not isinstance(rows, Sequence):
            raise ShadowCliError("writer rows must be a real sequence")
        return tuple(rows)

    async def upsert_exchange_feature_vectors(self, rows) -> int:
        detached = self._detach(rows)
        self.exchange_feature_batches.append(detached)
        return len(detached)

    async def upsert_consensus_feature_vectors(self, rows) -> int:
        detached = self._detach(rows)
        self.consensus_batches.append(detached)
        return len(detached)

    async def upsert_forecast_outcomes(self, rows) -> int:
        detached = self._detach(rows)
        self.outcome_batches.append(detached)
        return len(detached)

    async def insert_forecast_prediction(self, row) -> bool:
        self.predictions.append(row)
        return True  # simulate a first insert; never touches the DB


# ============================================================================
# Typed reports
# ============================================================================
@dataclass(frozen=True)
class ShadowExecutionReport:
    command: str
    bucket_selection: str
    bucket_ts: datetime
    stage2_global_enabled: bool
    writes_enabled: bool
    reference_exchange: str
    code_version: str
    result: ShadowCycleResult

    def __post_init__(self) -> None:
        if self.command not in (SHADOW_ONCE, SHADOW_DRY_RUN):
            raise ShadowCliError(f"invalid execution command {self.command!r}")
        if self.bucket_selection not in (BUCKET_AUTO, BUCKET_EXPLICIT):
            raise ShadowCliError(f"invalid bucket_selection {self.bucket_selection!r}")
        if not _is_utc_aware(self.bucket_ts) or self.bucket_ts.second != 0 \
                or self.bucket_ts.microsecond != 0 or self.bucket_ts.minute % _BUCKET_MINUTES != 0:
            raise ShadowCliError("bucket_ts must be a UTC, 5m-aligned datetime")
        if type(self.stage2_global_enabled) is not bool:
            raise ShadowCliError("stage2_global_enabled must be a bool")
        if type(self.writes_enabled) is not bool:
            raise ShadowCliError("writes_enabled must be a bool")
        if self.command == SHADOW_ONCE and self.writes_enabled is not True:
            raise ShadowCliError("SHADOW_ONCE requires writes_enabled=True")
        if self.command == SHADOW_DRY_RUN and self.writes_enabled is not False:
            raise ShadowCliError("SHADOW_DRY_RUN requires writes_enabled=False")
        if self.reference_exchange not in ACTIVE_EXCHANGES:
            raise ShadowCliError("reference_exchange must be canonical")
        if not isinstance(self.code_version, str) or not self.code_version.strip():
            raise ShadowCliError("code_version must be a non-empty string")
        if type(self.result) is not ShadowCycleResult:
            raise ShadowCliError("result must be exactly ShadowCycleResult")


@dataclass(frozen=True)
class ShadowStatusReport:
    state: str
    stage2_global_enabled: bool
    symbol: str
    market_type: str
    timeframe: str
    exchanges: Sequence[str]
    prerequisites: Sequence[Mapping]
    latest_prediction: Optional[Mapping]
    outcomes: Sequence[Mapping]
    # (Tech-lead review 4992495660, finding 7) Read-only diagnostics for the
    # instrument_metadata_revision fork-enforcement mechanism -- surfaced
    # here so an operator can see WHY a dry-run/live run is about to fail
    # closed without needing direct DB access. `durable_instrument_metadata_
    # revision` is `None` exactly when the singleton row is absent (missing
    # table or an interrupted bootstrap; see storage/shadow_cli_readers.py).
    configured_instrument_metadata_revision: int
    durable_instrument_metadata_revision: Optional[int]

    def __post_init__(self) -> None:
        if self.state not in _STATUS_STATES:
            raise ShadowCliError(f"invalid status state {self.state!r}")
        if type(self.stage2_global_enabled) is not bool:
            raise ShadowCliError("stage2_global_enabled must be a bool")
        if not isinstance(self.configured_instrument_metadata_revision, int) or isinstance(
                self.configured_instrument_metadata_revision, bool):
            raise ShadowCliError("configured_instrument_metadata_revision must be an int")
        if self.durable_instrument_metadata_revision is not None and (
                not isinstance(self.durable_instrument_metadata_revision, int)
                or isinstance(self.durable_instrument_metadata_revision, bool)):
            raise ShadowCliError(
                "durable_instrument_metadata_revision must be an int or None")
        object.__setattr__(self, "exchanges", tuple(self.exchanges))
        object.__setattr__(self, "prerequisites",
                           tuple(MappingProxyType(dict(p)) for p in self.prerequisites))
        if self.latest_prediction is not None:
            object.__setattr__(self, "latest_prediction",
                               MappingProxyType(dict(self.latest_prediction)))
        object.__setattr__(self, "outcomes",
                           tuple(MappingProxyType(dict(o)) for o in self.outcomes))
        if self.state in (STATUS_NOT_INITIALIZED, STATUS_PARTIAL_SCHEMA, STATUS_EMPTY):
            if self.latest_prediction is not None or self.outcomes != ():
                raise ShadowCliError(f"{self.state} must have no prediction/outcomes")
        elif self.state == STATUS_READY:
            if self.latest_prediction is None:
                raise ShadowCliError("READY requires a latest_prediction")


# ============================================================================
# Execution APIs
# ============================================================================
async def execute_shadow_once(
    db,
    stage1_config: Config,
    stage2_config: Stage2Config,
    *,
    now: datetime,
    explicit_bucket_ts: Optional[str],
    reference_exchange: str,
    explicit_code_version: Optional[str],
    metadata_fetch_json=None,
) -> ShadowExecutionReport:
    """One-shot: init Stage 2 schema + the instrument-metadata-revision
    singleton (`_bootstrap_stage2_schema_and_revision`), structural seed,
    metadata bootstrap, then ONE `process_shadow_cycle` with
    due_outcome_jobs=(). All CLI/config/time validation happens before any
    DB write. Does not call Stage 1 init_schema."""
    symbol, exchanges, resolved = _resolve_shadow_scope(
        stage1_config, stage2_config, reference_exchange=reference_exchange)
    bucket_selection, bucket_ts = _resolve_bucket(now, explicit_bucket_ts, resolved)
    code_version = resolve_feature_code_version(explicit=explicit_code_version)

    await _bootstrap_stage2_schema_and_revision(db, stage2_config, symbol)
    await db.seed_symbols(symbol_seed_rows())
    await db.seed_symbol_exchange_capabilities(symbol_exchange_capability_seed_rows())
    await _bootstrap_instrument_metadata(
        db, exchanges, symbol, metadata_fetch_json=metadata_fetch_json)

    availability = await db.fetch_shadow_liquidation_availability(
        exchanges=exchanges, symbol=symbol, market_type=_MARKET_TYPE)

    result = await process_shadow_cycle(
        db, db, stage2_config,
        exchanges=exchanges, symbol=symbol, market_type=_MARKET_TYPE,
        timeframe=_TIMEFRAME, bucket_ts=bucket_ts, code_version=code_version,
        liquidation_feed_available_by_exchange=availability,
        reference_exchange=reference_exchange, due_outcome_jobs=())

    return ShadowExecutionReport(
        command=SHADOW_ONCE, bucket_selection=bucket_selection, bucket_ts=bucket_ts,
        stage2_global_enabled=stage2_config.enabled, writes_enabled=True,
        reference_exchange=reference_exchange, code_version=code_version, result=result)


async def execute_shadow_dry_run(
    db,
    stage1_config: Config,
    stage2_config: Stage2Config,
    *,
    now: datetime,
    explicit_bucket_ts: Optional[str],
    reference_exchange: str,
    explicit_code_version: Optional[str],
    metadata_fetch_json=None,
) -> ShadowExecutionReport:
    """Dry-run: real reads, an in-memory writer, and ZERO writes. No schema init,
    no seeds, no metadata network/write, and NEVER calls
    `Database.bootstrap_instrument_metadata_revision` (tech-lead review
    4992495660, finding 6 -- dry-run must remain read-only). Requires the
    Stage 2 reader prerequisites to already exist AND the durable
    `stage2_instrument_metadata_state.required_revision` to match this
    deployment's resolved `instrument_metadata_revision` (explicit
    ShadowCliError listing what is missing/mismatched otherwise)."""
    symbol, exchanges, resolved = _resolve_shadow_scope(
        stage1_config, stage2_config, reference_exchange=reference_exchange)
    bucket_selection, bucket_ts = _resolve_bucket(now, explicit_bucket_ts, resolved)
    code_version = resolve_feature_code_version(explicit=explicit_code_version)

    status = await db.fetch_shadow_status(
        exchanges=exchanges, symbol=symbol, market_type=_MARKET_TYPE, timeframe=_TIMEFRAME)
    _require_dry_run_prerequisites(status, exchanges, stage2_config)

    availability = await db.fetch_shadow_liquidation_availability(
        exchanges=exchanges, symbol=symbol, market_type=_MARKET_TYPE)

    sink = _InMemoryShadowWriter()
    result = await process_shadow_cycle(
        db, sink, stage2_config,
        exchanges=exchanges, symbol=symbol, market_type=_MARKET_TYPE,
        timeframe=_TIMEFRAME, bucket_ts=bucket_ts, code_version=code_version,
        liquidation_feed_available_by_exchange=availability,
        reference_exchange=reference_exchange, due_outcome_jobs=())

    return ShadowExecutionReport(
        command=SHADOW_DRY_RUN, bucket_selection=bucket_selection, bucket_ts=bucket_ts,
        stage2_global_enabled=stage2_config.enabled, writes_enabled=False,
        reference_exchange=reference_exchange, code_version=code_version, result=result)


def _require_dry_run_prerequisites(status, exchanges, stage2_config: Stage2Config) -> None:
    """`--shadow-dry-run` is read-only: it NEVER bootstraps or writes anything
    (tech-lead review 4992495660, finding 6) -- it only validates, against
    the already-persisted state, that a raw-bundle read/feature computation
    could actually succeed, failing closed with a clear `ShadowCliError`
    otherwise. `status["state"] in (NOT_INITIALIZED, PARTIAL_SCHEMA)` already
    catches BOTH a missing `stage2_instrument_metadata_state` table AND a
    present-but-empty singleton row (see `storage/shadow_cli_readers.py`'s
    own state-machine fold, finding 5) -- both correctly refuse here with no
    write ever attempted. What that state check does NOT catch is a
    genuinely PRESENT but STALE revision (finding 6): the durable required
    revision resolves fine, but this deployment's OWN resolved config no
    longer matches it (e.g. a critical metadata change was accepted after
    this config was last updated) -- checked explicitly below."""
    if status["state"] in (STATUS_NOT_INITIALIZED, STATUS_PARTIAL_SCHEMA):
        raise ShadowCliError(
            f"Stage 2 schema is not fully initialized (state={status['state']}); "
            f"run --shadow-once first")
    durable_revision = status["instrument_metadata_revision"]
    configured_revision = stage2_config.instrument_metadata_revision
    if durable_revision != configured_revision:
        raise ShadowCliError(
            f"instrument_metadata_revision mismatch: durable "
            f"required_revision={durable_revision!r} but this deployment's "
            f"resolved config has instrument_metadata_revision="
            f"{configured_revision!r}; update config/stage2.yaml (or "
            f"investigate why the durable value changed) before retrying "
            f"-- refusing to read/compute under a stale revision")
    prereq_by_exchange = {p["exchange"]: p for p in status["prerequisites"]}
    missing: list[str] = []
    for ex in exchanges:
        p = prereq_by_exchange.get(ex)
        if p is None or not p["instrument_present"]:
            missing.append(f"{ex}: instrument metadata")
        if p is None or not p["liquidation_capability_present"]:
            missing.append(f"{ex}: liquidation capability")
    if missing:
        raise ShadowCliError("missing Stage 2 prerequisites: " + "; ".join(missing))


async def execute_shadow_status(
    db,
    stage1_config: Config,
    stage2_config: Stage2Config,
) -> ShadowStatusReport:
    """Read-only status. No clock, code-version, schema init, seeding, network, or
    writers. Reports only the latest stored prediction and its recorded outcomes —
    never scans for missing outcomes, never decides an outcome is due."""
    symbol, exchanges, _resolved = _resolve_shadow_scope(stage1_config, stage2_config)
    snapshot = await db.fetch_shadow_status(
        exchanges=exchanges, symbol=symbol, market_type=_MARKET_TYPE, timeframe=_TIMEFRAME)
    return ShadowStatusReport(
        state=snapshot["state"], stage2_global_enabled=stage2_config.enabled,
        symbol=symbol, market_type=_MARKET_TYPE, timeframe=_TIMEFRAME,
        exchanges=exchanges, prerequisites=snapshot["prerequisites"],
        latest_prediction=snapshot["latest_prediction"], outcomes=snapshot["outcomes"],
        configured_instrument_metadata_revision=stage2_config.instrument_metadata_revision,
        durable_instrument_metadata_revision=snapshot["instrument_metadata_revision"])


# ============================================================================
# Persistence-effect labelling (dry-run never claims a real write)
# ============================================================================
def _persistence_effect(command: str, prediction_status: str) -> str:
    if command == SHADOW_ONCE:
        return {PREDICTION_INSERTED: "INSERTED",
                PREDICTION_DUPLICATE: "DUPLICATE"}.get(prediction_status, prediction_status)
    # dry-run: never say "inserted"
    if prediction_status == PREDICTION_INSERTED:
        return "WOULD_INSERT"
    if prediction_status == PREDICTION_DUPLICATE:
        return "WOULD_BE_DUPLICATE"
    return f"DRY_RUN_{prediction_status}"  # skipped statuses keep their name w/ prefix


def _prediction_summary(result: ShadowCycleResult) -> Optional[dict]:
    decision, prediction = result.decision, result.prediction
    if decision is None and prediction is None:
        return None
    src = decision if decision is not None else prediction
    return {
        "direction": src.direction,
        "confidence": src.confidence,
        "final_score": src.final_score,
        "reasons": list(src.reasons),
        "reference_price": (prediction.reference_price if prediction is not None else None),
        "reference_price_source": (
            prediction.reference_price_source if prediction is not None else None),
    }


# ============================================================================
# JSON views (deterministic; secrets/consensus-snapshot never included)
# ============================================================================
def _iso_utc(dt: datetime) -> str:
    if not isinstance(dt, datetime) or dt.tzinfo is None:
        raise ShadowCliError("expected a timezone-aware datetime in a report")
    return dt.astimezone(timezone.utc).isoformat()


def _to_jsonable(value):
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ShadowCliError("non-finite float is not allowed in a report")
        return value
    if isinstance(value, datetime):
        return _iso_utc(value)
    if isinstance(value, Mapping):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    raise ShadowCliError(f"unsupported value type in report: {type(value).__name__}")


def execution_report_to_jsonable(report: ShadowExecutionReport) -> dict:
    result = report.result
    bucket = result.bucket_result
    return {
        "command": report.command,
        "bucket_selection": report.bucket_selection,
        "bucket_ts": _iso_utc(report.bucket_ts),
        "stage2_global_enabled": report.stage2_global_enabled,
        "writes_enabled": report.writes_enabled,
        "reference_exchange": report.reference_exchange,
        "code_version": report.code_version,
        "core_prediction_status": result.prediction_status,
        "persistence_effect": _persistence_effect(report.command, result.prediction_status),
        "prediction": _to_jsonable(_prediction_summary(result)),
        "exchange_features": [
            {
                "exchange": efv.exchange,
                "bars_present": efv.bars_present,
                "bars_expected": efv.bars_expected,
                "is_usable": efv.is_usable,
                "has_gap": efv.has_gap,
                "close_price": _to_jsonable(efv.close_price),
            }
            for efv in bucket.exchange_features
        ],
        "failures": [
            {"exchange": f.exchange, "reason": f.reason, "error_type": f.error_type}
            for f in bucket.failures
        ],
        "outcomes_attempted": 0,
    }


def _outcomes_by_horizon(report: ShadowStatusReport) -> dict:
    if report.latest_prediction is None:
        return {}
    by: dict = {}
    for horizon in report.latest_prediction["horizon_set"]:
        recorded = [o for o in report.outcomes if o["horizon"] == horizon]
        by[str(horizon)] = {
            "status": "RECORDED" if recorded else "NOT_RECORDED",
            "outcomes": [_to_jsonable(o) for o in recorded],
        }
    return by


def status_report_to_jsonable(report: ShadowStatusReport) -> dict:
    return {
        "state": report.state,
        "stage2_global_enabled": report.stage2_global_enabled,
        "symbol": report.symbol,
        "market_type": report.market_type,
        "timeframe": report.timeframe,
        "exchanges": list(report.exchanges),
        "configured_instrument_metadata_revision":
            report.configured_instrument_metadata_revision,
        "durable_instrument_metadata_revision":
            report.durable_instrument_metadata_revision,
        "prerequisites": [_to_jsonable(p) for p in report.prerequisites],
        "latest_prediction": _to_jsonable(report.latest_prediction),
        "outcomes_by_horizon": _outcomes_by_horizon(report),
    }


def render_execution_report_json(report: ShadowExecutionReport) -> str:
    return json.dumps(execution_report_to_jsonable(report),
                      sort_keys=True, separators=(",", ":"), allow_nan=False)


def render_status_report_json(report: ShadowStatusReport) -> str:
    return json.dumps(status_report_to_jsonable(report),
                      sort_keys=True, separators=(",", ":"), allow_nan=False)


# ============================================================================
# Human views (same report object as JSON; no secrets, no consensus snapshot)
# ============================================================================
def _fmt(value) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.4f}"
    if isinstance(value, datetime):
        return _iso_utc(value)
    return str(value)


def render_shadow_execution_report(report: ShadowExecutionReport) -> str:
    result = report.result
    bucket = result.bucket_result
    header = "SHADOW ONCE" if report.command == SHADOW_ONCE else "SHADOW DRY RUN"
    effect = _persistence_effect(report.command, result.prediction_status)
    lines = [
        f"=== {header} ===",
        f"bucket_ts:        {_iso_utc(report.bucket_ts)} ({report.bucket_selection})",
        f"stage2_enabled:   {report.stage2_global_enabled}",
        f"writes_enabled:   {_fmt(report.writes_enabled)}",
        f"reference:        {report.reference_exchange}",
        f"code_version:     {report.code_version}",
        f"prediction:       {result.prediction_status} -> {effect}",
    ]
    summary = _prediction_summary(result)
    if summary is None:
        lines.append("  (no consensus / no prediction)")
    else:
        lines.append(f"  direction:      {summary['direction']}")
        lines.append(f"  confidence:     {_fmt(summary['confidence'])}")
        lines.append(f"  final_score:    {_fmt(summary['final_score'])}")
        lines.append(
            f"  reference:      {_fmt(summary['reference_price'])} "
            f"({summary['reference_price_source'] or 'n/a'})")
        reasons = ", ".join(summary["reasons"]) if summary["reasons"] else "(none)"
        lines.append(f"  reasons:        {reasons}")
    lines.append("exchange features:")
    if bucket.exchange_features:
        for efv in bucket.exchange_features:
            lines.append(
                f"  {efv.exchange:<8} {efv.bars_present}/{efv.bars_expected} "
                f"usable={_fmt(efv.is_usable)} gap={_fmt(efv.has_gap)} "
                f"close={_fmt(efv.close_price)}")
    else:
        lines.append("  (none)")
    lines.append("failures:")
    if bucket.failures:
        for f in bucket.failures:
            lines.append(f"  {f.exchange:<8} {f.reason} ({f.error_type})")
    else:
        lines.append("  (none)")
    lines.append("outcomes attempted: 0")
    return "\n".join(lines)


def render_shadow_status_report(report: ShadowStatusReport) -> str:
    lines = [
        "=== SHADOW STATUS ===",
        f"state:            {report.state}",
        f"stage2_enabled:   {report.stage2_global_enabled}",
        f"scope:            {report.symbol} / {report.market_type} / {report.timeframe}",
        f"exchanges:        {', '.join(report.exchanges)}",
        f"instrument_metadata_revision: configured="
        f"{report.configured_instrument_metadata_revision} "
        f"durable={_fmt(report.durable_instrument_metadata_revision)}"
        + ("  (MISMATCH)" if report.durable_instrument_metadata_revision is not None
           and report.durable_instrument_metadata_revision
           != report.configured_instrument_metadata_revision else ""),
        "prerequisites:",
    ]
    if report.prerequisites:
        for p in report.prerequisites:
            instrument = "present" if p["instrument_present"] else "MISSING"
            if p["instrument_present"]:
                instrument += "(stale)" if p["instrument_is_stale"] else "(fresh)"
            cap = "present" if p["liquidation_capability_present"] else "MISSING"
            lines.append(
                f"  {p['exchange']:<8} instrument={instrument} "
                f"liquidations={cap} live={_fmt(p['liquidation_live_supported'])} "
                f"enabled={_fmt(p['liquidation_enabled'])} "
                f"coverage={p['liquidation_coverage_type'] or 'n/a'}")
    else:
        lines.append("  (schema not initialized)")
    lines.append("latest prediction:")
    pred = report.latest_prediction
    if pred is None:
        lines.append("  (none)")
    else:
        lines.append(f"  bucket_ts:      {_iso_utc(pred['bucket_ts'])}")
        lines.append(
            f"  direction:      {pred['direction']}  "
            f"confidence: {_fmt(pred['confidence'])}  final_score: {_fmt(pred['final_score'])}")
        lines.append(
            f"  reference:      {_fmt(pred['reference_price'])} "
            f"({pred['reference_price_source']})")
        lines.append(f"  created_at:     {_iso_utc(pred['created_at'])}")
    lines.append("horizons:")
    if pred is None:
        lines.append("  (none)")
    else:
        outcomes_by = {o["horizon"]: o for o in report.outcomes}
        for horizon in pred["horizon_set"]:
            match = [o for o in report.outcomes if o["horizon"] == horizon]
            if match:
                o = match[0]
                lines.append(
                    f"  {str(horizon):<4} RECORDED   return={_fmt(o['market_return_pct'])} "
                    f"mfe={_fmt(o['mfe_pct'])} mae={_fmt(o['mae_pct'])}")
            else:
                lines.append(f"  {str(horizon):<4} NOT_RECORDED")
    return "\n".join(lines)


# ============================================================================
# CLI command dispatch (connection lifecycle)
# ============================================================================
def is_shadow_command(args) -> bool:
    return bool(getattr(args, "shadow_once", False)
                or getattr(args, "shadow_dry_run", False)
                or getattr(args, "shadow_status", False))


async def run_shadow_cli_command(args, stage1_config: Config, secrets: Secrets) -> None:
    """Load Stage2Config, connect a Database (PostgreSQL only — never Redis), run
    exactly one selected shadow command, render+print, and always close the pool.
    Command failures propagate; no success report is printed after an exception."""
    stage2_config = Stage2Config.load()
    reference_exchange = getattr(args, "shadow_reference_exchange", None) or "binance"
    db = Database(secrets.postgres_dsn)
    await db.connect()
    try:
        use_json = bool(getattr(args, "shadow_json", False))
        if args.shadow_status:
            status = await execute_shadow_status(db, stage1_config, stage2_config)
            output = (render_status_report_json(status) if use_json
                      else render_shadow_status_report(status))
        elif args.shadow_dry_run:
            report = await execute_shadow_dry_run(
                db, stage1_config, stage2_config, now=datetime.now(timezone.utc),
                explicit_bucket_ts=args.shadow_bucket_ts,
                reference_exchange=reference_exchange,
                explicit_code_version=args.shadow_code_version)
            output = (render_execution_report_json(report) if use_json
                      else render_shadow_execution_report(report))
        elif args.shadow_once:
            if args.shadow_bucket_ts is None:
                # Automatic bucket selection -> ONE bounded recovery pass
                # (advisory lock, prediction catch-up, outcome maturation).
                from runtime.shadow_recovery import (
                    execute_shadow_recovery, render_shadow_recovery_report,
                    render_shadow_recovery_report_json,
                    DEFAULT_MAX_CATCHUP_BUCKETS, DEFAULT_MAX_OUTCOME_JOBS)
                # Explicit `is None` fallback: a genuinely omitted option gets the
                # default; a supplied 0 (or any invalid value) is passed through and
                # rejected by execute_shadow_recovery BEFORE any lock/DB work — it is
                # never silently coerced to the default.
                catchup = getattr(args, "shadow_max_catchup_buckets", None)
                outcomes = getattr(args, "shadow_max_outcome_jobs", None)
                recovery = await execute_shadow_recovery(
                    db, stage1_config, stage2_config, now=datetime.now(timezone.utc),
                    reference_exchange=reference_exchange,
                    explicit_code_version=args.shadow_code_version,
                    max_catchup_buckets=(DEFAULT_MAX_CATCHUP_BUCKETS if catchup is None else catchup),
                    max_outcome_jobs=(DEFAULT_MAX_OUTCOME_JOBS if outcomes is None else outcomes))
                output = (render_shadow_recovery_report_json(recovery) if use_json
                          else render_shadow_recovery_report(recovery))
            else:
                # Explicit --shadow-bucket-ts -> deterministic ONE-bucket run under
                # the SAME advisory lock as automatic recovery (a manual write run
                # and the timer must never run concurrently). No watermark, no
                # catch-up, no broad outcome discovery.
                from runtime.shadow_recovery import (
                    execute_shadow_once_locked, render_locked_once_report,
                    render_locked_once_report_json)
                locked = await execute_shadow_once_locked(
                    db, stage1_config, stage2_config, now=datetime.now(timezone.utc),
                    explicit_bucket_ts=args.shadow_bucket_ts,
                    reference_exchange=reference_exchange,
                    explicit_code_version=args.shadow_code_version)
                output = (render_locked_once_report_json(locked) if use_json
                          else render_locked_once_report(locked))
        else:
            raise ShadowCliError("no shadow command selected")
        print(output)
    finally:
        await db.close()
