"""
Stage 2.1 Data Quality & Gap Detection core — a pure, deterministic computation
(Data Quality Contract Revision 0.2.5, docs/STAGE2_SPEC.md §13).

`compute_data_health_snapshot(request) -> DataHealthSnapshot` classifies exactly
one live-operational-health row for a single `(identity, snapshot_ts,
calculation_version)`. `derive_data_health_status(...)` is the report-layer label
helper (§13.5); it never adds a `status` column to the persisted snapshot.

No DB, no network, no asyncio, no clock/env/subprocess/filesystem, no global
mutable state, and NO internal rounding beyond the frozen integer quantisations
(`lateness_ms` floor-to-ms, gap ceil). Same logical input -> same output;
observation order does not matter; a replay of the same originally-live
observations at the same `snapshot_ts` yields a field-for-field identical row.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from symbols.registry import ACTIVE_EXCHANGES, SymbolRegistryError, get_symbol

from .gaps import compute_gap_summary
from .models import (
    CONTINUOUS_METRICS, DataHealthSnapshot, DataQualityError, DataQualityObservation,
    DataQualityRequest, DataQualityThresholds, EVENT_DRIVEN_METRICS,
    LIVE_EXPECTED_INTERVAL_S, VALID_BACKFILL_STATUSES, VALID_COVERAGE_TYPES,
    VALID_METRICS,
)

_HEX16 = re.compile(r"^[0-9a-f]{16}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
_MS_PER_SECOND = 1_000

# Identity fields every observation must match the request on exactly (§13.4).
_OBS_IDENTITY_FIELDS = ("exchange", "symbol", "market_type", "metric")


# ---- small validators ------------------------------------------------------
def _nonblank(value, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DataQualityError(f"{name} must be a non-empty string")
    return value


def _tz_utc(dt, name: str) -> datetime:
    if not isinstance(dt, datetime):
        raise DataQualityError(f"{name} must be a datetime, got {type(dt).__name__}")
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise DataQualityError(f"{name} must be timezone-aware")
    if dt.utcoffset() != timedelta(0):
        raise DataQualityError(f"{name} must be UTC (offset 0), got offset {dt.utcoffset()}")
    return dt


def _epoch_seconds_int(dt: datetime) -> int:
    """Whole epoch seconds as an int (dt already validated UTC, zero micros).
    Integer timedelta arithmetic only — no float `timestamp()`/`total_seconds()`."""
    d = dt - _EPOCH
    return d.days * 86_400 + d.seconds


# ---- identity / version / snapshot_ts (§13.1 / §13.5) ----------------------
def _validate_identity(req: DataQualityRequest) -> None:
    _nonblank(req.exchange, "exchange")
    _nonblank(req.symbol, "symbol")
    _nonblank(req.market_type, "market_type")
    _nonblank(req.metric, "metric")

    if req.exchange not in ACTIVE_EXCHANGES:
        raise DataQualityError(
            f"inactive/unknown exchange {req.exchange!r} (active: {list(ACTIVE_EXCHANGES)})")
    try:
        symdef = get_symbol(req.symbol)
    except SymbolRegistryError:
        raise DataQualityError(f"unknown symbol {req.symbol!r}") from None
    if not (symdef.enabled and symdef.status == "ACTIVE"):
        raise DataQualityError(f"symbol {req.symbol!r} is not active")
    if req.market_type not in symdef.market_types:
        raise DataQualityError(
            f"market_type {req.market_type!r} not allowed for {req.symbol!r} "
            f"(allowed: {list(symdef.market_types)})")
    if req.metric not in VALID_METRICS:
        raise DataQualityError(
            f"metric {req.metric!r} is not a Stage 2 health metric "
            f"(valid: {list(VALID_METRICS)})")

    _nonblank(req.config_version, "config_version")
    _nonblank(req.code_version, "code_version")
    if not isinstance(req.feature_schema_version, int) or isinstance(req.feature_schema_version, bool) \
            or req.feature_schema_version <= 0:
        raise DataQualityError("feature_schema_version must be an int > 0")
    if not isinstance(req.config_hash, str) or not _HEX64.match(req.config_hash):
        raise DataQualityError("config_hash must be 64 lowercase hex chars")
    if not isinstance(req.calculation_version, str) or not _HEX16.match(req.calculation_version):
        raise DataQualityError("calculation_version must be 16 lowercase hex chars")


def _validate_snapshot_ts(req: DataQualityRequest) -> None:
    ts = _tz_utc(req.snapshot_ts, "snapshot_ts")
    if ts.microsecond != 0:
        raise DataQualityError("snapshot_ts must have zero microseconds")
    if _epoch_seconds_int(ts) % req.thresholds.cadence_s != 0:
        raise DataQualityError(
            f"snapshot_ts must be aligned to cadence_s={req.thresholds.cadence_s}")


# ---- capability / backfill / interval / freshness (§13.3 / §13.7 / §13.10) --
def _validate_capabilities(req: DataQualityRequest) -> None:
    if not isinstance(req.live_supported, bool):
        raise DataQualityError("live_supported must be a bool")
    if not isinstance(req.historical_supported, bool):
        raise DataQualityError("historical_supported must be a bool")
    if req.coverage_type not in VALID_COVERAGE_TYPES:
        raise DataQualityError(
            f"invalid coverage_type {req.coverage_type!r} (expected {list(VALID_COVERAGE_TYPES)})")
    # connection_up is strictly True / False / None (bool-or-none, never int/str).
    if not (req.connection_up is True or req.connection_up is False or req.connection_up is None):
        raise DataQualityError("connection_up must be True, False, or None")
    if req.backfill_status not in VALID_BACKFILL_STATUSES:
        raise DataQualityError(
            f"invalid backfill_status {req.backfill_status!r} "
            f"(expected {list(VALID_BACKFILL_STATUSES)})")

    # Backfill consistency (§13.10) — supplied + echoed, never inferred, and
    # historical support never affects live is_usable.
    if req.historical_supported is False and req.backfill_status != "not_applicable":
        raise DataQualityError(
            "historical_supported=False requires backfill_status='not_applicable'")
    if req.historical_supported is True and req.backfill_status == "not_applicable":
        raise DataQualityError(
            "historical_supported=True is inconsistent with backfill_status='not_applicable'")


def _validate_interval_and_freshness(req: DataQualityRequest) -> None:
    expected = LIVE_EXPECTED_INTERVAL_S[req.metric]  # metric already validated
    if req.metric in EVENT_DRIVEN_METRICS:
        if req.expected_interval_s is not None:
            raise DataQualityError(
                f"expected_interval_s must be None for {req.metric}, got {req.expected_interval_s!r}")
        if req.expected_freshness_s is not None:
            raise DataQualityError(
                f"expected_freshness_s must be None for {req.metric}, got {req.expected_freshness_s!r}")
    else:
        if not isinstance(req.expected_interval_s, int) or isinstance(req.expected_interval_s, bool):
            raise DataQualityError(
                f"expected_interval_s must be an int for {req.metric}, "
                f"got {req.expected_interval_s!r}")
        if req.expected_interval_s != expected:
            raise DataQualityError(
                f"expected_interval_s for {req.metric} must equal the frozen live "
                f"mapping value {expected}, got {req.expected_interval_s}")
        if not isinstance(req.expected_freshness_s, int) or isinstance(req.expected_freshness_s, bool) \
                or req.expected_freshness_s <= 0:
            raise DataQualityError(
                f"expected_freshness_s must be a positive int for {req.metric}, "
                f"got {req.expected_freshness_s!r}")


# ---- observations (§13.4 / §13.9) ------------------------------------------
def _collect_observation_ts(req: DataQualityRequest, window_start: datetime) -> list[datetime]:
    """Validate every observation's type, identity, provenance, and window
    membership; raise on any invalid request (never silently drop). Returns the
    sorted, de-duplicated accepted timestamps (order-independent)."""
    snapshot_ts = req.snapshot_ts
    seen: set[datetime] = set()
    for obs in req.observations:
        if not isinstance(obs, DataQualityObservation):
            raise DataQualityError(
                f"observations must be DataQualityObservation, got {type(obs).__name__}")
        for f in _OBS_IDENTITY_FIELDS:
            if getattr(obs, f) != getattr(req, f):
                raise DataQualityError(
                    f"observation {f} mismatch: {getattr(obs, f)!r} != request {getattr(req, f)!r}")
        if obs.raw_source == "backfill":
            raise DataQualityError(
                "backfill observation rejected: the live-health core is live-only (§13.4)")
        if obs.raw_source != "live":
            raise DataQualityError(f"invalid raw_source {obs.raw_source!r} (expected 'live')")
        _tz_utc(obs.ts, "observation.ts")
        # coverage membership: [window_start, snapshot_ts) — never silently dropped.
        if not (window_start <= obs.ts < snapshot_ts):
            raise DataQualityError(
                f"observation.ts {obs.ts.isoformat()} outside coverage window "
                f"[{window_start.isoformat()}, {snapshot_ts.isoformat()})")
        seen.add(obs.ts)  # duplicate timestamps collapse deterministically
    return sorted(seen)


# ---- freshness (§13.7) -----------------------------------------------------
def _lateness_ms(snapshot_ts: datetime, last_event_at: datetime) -> int:
    """Floor-to-millisecond via integer timedelta components — never
    int(total_seconds()*1000) (§13.7)."""
    delta = snapshot_ts - last_event_at
    return (delta.days * 86_400_000
            + delta.seconds * _MS_PER_SECOND
            + delta.microseconds // _MS_PER_SECOND)


# ---- derived report status (§13.5) -----------------------------------------
def _derive_status(
    metric: str,
    last_event_at: Optional[datetime],
    is_stale: bool,
    largest_gap_s: Optional[int],
    *,
    live_supported: bool,
    coverage_type: str,
    connection_up: Optional[bool],
    max_usable_gap_s: int,
) -> str:
    """First matching rule wins, in the frozen precedence order (§13.5)."""
    is_continuous = metric in CONTINUOUS_METRICS
    # 1. structural live availability
    if not live_supported or coverage_type == "unavailable":
        return "not_available"
    # 2-3. connection labels apply ONLY to event-driven metrics
    if metric in EVENT_DRIVEN_METRICS:
        if connection_up is False:
            return "disconnected"
        if connection_up is None:
            return "connection_unknown"
    # 4-6. continuous live-health labels
    if is_continuous:
        if last_event_at is None:
            return "no_data"
        if is_stale:
            return "stale"
        if largest_gap_s is not None and largest_gap_s > max_usable_gap_s:
            return "gap_exceeded"
    # 7.
    return "ok"


def derive_data_health_status(
    snapshot: DataHealthSnapshot,
    *,
    live_supported: bool,
    coverage_type: str,
    connection_up: Optional[bool],
    max_usable_gap_s: int,
) -> str:
    """Report-layer label for a persisted snapshot (§13.5). Reads only fields on
    the snapshot plus the supplied capability/connection facts; adds NO `status`
    column to the row."""
    return _derive_status(
        snapshot.metric, snapshot.last_event_at, snapshot.is_stale, snapshot.largest_gap_s,
        live_supported=live_supported, coverage_type=coverage_type,
        connection_up=connection_up, max_usable_gap_s=max_usable_gap_s,
    )


# ---- entry point -----------------------------------------------------------
def compute_data_health_snapshot(req: DataQualityRequest) -> DataHealthSnapshot:
    if not isinstance(req, DataQualityRequest):
        raise DataQualityError(f"request must be a DataQualityRequest, got {type(req).__name__}")
    if not isinstance(req.thresholds, DataQualityThresholds):
        raise DataQualityError("thresholds must be a DataQualityThresholds")

    _validate_identity(req)
    _validate_snapshot_ts(req)
    _validate_capabilities(req)
    _validate_interval_and_freshness(req)

    thr = req.thresholds
    coverage_window_end = req.snapshot_ts
    coverage_window_start = req.snapshot_ts - timedelta(seconds=thr.coverage_window_s)

    accepted_ts = _collect_observation_ts(req, coverage_window_start)

    last_event_at: Optional[datetime] = accepted_ts[-1] if accepted_ts else None
    lateness_ms: Optional[int] = (
        None if last_event_at is None else _lateness_ms(req.snapshot_ts, last_event_at))

    is_event_driven = req.metric in EVENT_DRIVEN_METRICS

    # Freshness (§13.7). Liquidations are never stale; absence is not staleness.
    if is_event_driven:
        is_stale = False
    else:
        is_stale = (
            last_event_at is not None
            and req.expected_freshness_s is not None
            and lateness_ms > req.expected_freshness_s * _MS_PER_SECOND
        )

    # Gaps (§13.8) — continuous metrics only.
    if is_event_driven:
        gap_count = 0
        largest_gap_s: Optional[int] = None
    else:
        summary = compute_gap_summary(
            accepted_ts, req.expected_interval_s, thr.gap_tolerance_factor)
        gap_count = summary.gap_count
        largest_gap_s = summary.largest_gap_s

    # Derived status -> usability (§13.5 / §13.10). No status column persisted.
    status = _derive_status(
        req.metric, last_event_at, is_stale, largest_gap_s,
        live_supported=req.live_supported, coverage_type=req.coverage_type,
        connection_up=req.connection_up, max_usable_gap_s=thr.max_usable_gap_s,
    )
    is_usable = (status == "ok")

    return DataHealthSnapshot(
        symbol=req.symbol, exchange=req.exchange, market_type=req.market_type,
        metric=req.metric, snapshot_ts=req.snapshot_ts,
        last_event_at=last_event_at, expected_interval_s=req.expected_interval_s,
        lateness_ms=lateness_ms, gap_count=gap_count, largest_gap_s=largest_gap_s,
        backfill_status=req.backfill_status,
        coverage_window_start=coverage_window_start, coverage_window_end=coverage_window_end,
        is_stale=is_stale, is_usable=is_usable,
        config_hash=req.config_hash, config_version=req.config_version,
        code_version=req.code_version,
        feature_schema_version=req.feature_schema_version,
        calculation_version=req.calculation_version,
    )
