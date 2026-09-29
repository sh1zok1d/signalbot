"""Frozen coverage predicates for the live-archive replay preflight.

These functions mirror the current beta/feature semantics. They do not compute
percentiles, events, or market magnitudes.

Bar coverage: ``config/stage2.yaml`` ``minimum_metric_coverage`` 0.95 on a 5m
bucket requires all 5 exact minute slots (allowed missing bars = 0).

Open interest: ``analytics/feature_engine/exchange_features.py`` ``_oi_feature``.
Evaluable only with at least two distinct timestamps, one unit, a non-zero
first usable value, and no duplicate timestamp.

Notional: ``metadata_notional_eligible``. Missing PIT history is not replaced
with the current instrument table. More than one as-of history row fails closed.

Heartbeat: ``beta.health.outage_overlaps`` on the same 6h event lookaround
``storage/beta_v0_store.py`` uses, then ``venue_heartbeat_healthy``
(live bar count == 5 and no overlapping logged outage). Zero liquidation rows
are not a heartbeat and are not a measured zero unless the feed is available.

Maturity span is not computed here. Each bucket carries the non-null input
flags a later analyzer needs for ``[B-30d, B)`` and ``building_below_days`` 30.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Mapping, Optional, Sequence

from beta.health import outage_intervals, outage_overlaps

UTC = timezone.utc
BUCKET = timedelta(minutes=5)
EVENT_LOOKAROUND = timedelta(hours=6)
EXPECTED_LIVE_MINUTES = 5
HEARTBEAT_LIVE_BARS = 5
OI_MIN_DISTINCT_TIMESTAMPS = 2
MATURITY_DAYS = 30
EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def floor_5m(ts: datetime) -> datetime:
    """UTC 5-minute floor using the Unix epoch origin, matching date_bin."""
    aware = _aware(ts)
    seconds = (aware - EPOCH).total_seconds()
    if seconds != int(seconds):
        # Sub-second stamps still floor by exact 300s steps.
        pass
    floored = (seconds // 300) * 300
    return EPOCH + timedelta(seconds=floored)


def in_half_open_bucket(ts: datetime, bucket_start: datetime) -> bool:
    start = _aware(bucket_start)
    stamp = _aware(ts)
    return start <= stamp < start + BUCKET


def is_expected_minute(ts: datetime, bucket_start: datetime) -> bool:
    start = _aware(bucket_start)
    stamp = _aware(ts)
    if stamp.second or stamp.microsecond:
        return False
    delta = stamp - start
    return delta in {timedelta(minutes=n) for n in range(EXPECTED_LIVE_MINUTES)}


def production_event_subset(events: Sequence[Mapping], bucket_start: datetime) -> list:
    """Events the beta store loads for one bucket: the latest event before the
    lookaround, plus events in ``[B-6h, B+5m+6h)``."""
    start = _aware(bucket_start)
    look_lo = start - EVENT_LOOKAROUND
    look_hi = start + BUCKET + EVENT_LOOKAROUND
    ordered = sorted(events, key=lambda event: (event["ts"], int(event.get("id") or 0)))
    prior = None
    inside = []
    for event in ordered:
        stamp = event["ts"]
        if stamp < look_lo:
            prior = event
        elif stamp < look_hi:
            inside.append(event)
    subset = []
    if prior is not None:
        subset.append(prior)
    subset.extend(inside)
    return subset


def production_outage_overlap(events: Sequence[Mapping], bucket_start: datetime) -> bool:
    start = _aware(bucket_start)
    subset = production_event_subset(events, start)
    return outage_overlaps(subset, start, start + BUCKET)


def full_replay_intervals(events: Sequence[Mapping]) -> list:
    return outage_intervals(events)


def declared_liquidation_available(row: Optional[Mapping]) -> Optional[bool]:
    """Same predicate as ``read_shadow_liquidation_availability``.

    ``None`` means the capability row is absent or duplicated. That is not
    silently filled with False inside the flag itself; callers still fail
    closed when they combine it with the heartbeat.
    """
    if row is None:
        return None
    live = row.get("live_supported")
    enabled = row.get("enabled")
    coverage_type = row.get("coverage_type")
    if not isinstance(live, bool) or not isinstance(enabled, bool):
        return None
    if not isinstance(coverage_type, str) or not coverage_type.strip():
        return None
    return bool(live and enabled and coverage_type != "unavailable")


def notional_eligible(quantity_unit: Optional[str], multiplier_present: Optional[bool]) -> bool:
    if quantity_unit == "base":
        return True
    if quantity_unit == "contracts":
        return multiplier_present is True
    return False


def pit_status(table_present: bool, row_count: Optional[int]) -> str:
    if not table_present:
        return "TABLE_ABSENT"
    if row_count is None:
        return "TABLE_ABSENT"
    if row_count <= 0:
        return "NO_ROW"
    if row_count > 1:
        return "OVERLAP_FAIL_CLOSED"
    return "OK"


def derive_coverage_row(
    atomic: Mapping,
    *,
    outage_overlap: Optional[bool],
    outage_status: str,
    capability: Optional[Mapping],
) -> dict:
    """Attach frozen booleans to one server-side aggregate row."""
    distinct = _int(atomic.get("distinct_expected_live_minutes"), default=0)
    live_bars = _int(atomic.get("live_bar_row_count"), default=0)
    first_present = _bool(atomic.get("first_expected_bar_present"), default=False)
    open_is_zero = _optional_bool(atomic.get("first_expected_open_is_zero"))
    taker_complete = _int(atomic.get("taker_split_complete_expected_minutes"), default=0)
    usable_oi = _int(atomic.get("usable_oi_distinct_timestamps"), default=0)
    oi_units_n = _int(atomic.get("oi_distinct_unit_count"), default=0)
    oi_dups = _int(atomic.get("oi_duplicate_timestamp_count"), default=0)
    first_oi_bad = _optional_bool(atomic.get("first_usable_oi_is_zero_or_null"))
    if first_oi_bad is None:
        first_oi_bad = True

    pit_table = _bool(atomic.get("pit_table_present"), default=False)
    pit_rows = _optional_int(atomic.get("pit_row_count"))
    status = pit_status(pit_table, pit_rows if pit_table else None)
    if status == "OK":
        unit = atomic.get("pit_quantity_unit") or None
        multiplier = _optional_bool(atomic.get("pit_multiplier_present"))
        notional = notional_eligible(unit, multiplier)
    else:
        unit = None
        notional = False
    all_five = distinct == EXPECTED_LIVE_MINUTES
    price_non_null = all_five and first_present and open_is_zero is False
    volume_non_null = all_five and notional
    taker_non_null = all_five and notional and taker_complete == EXPECTED_LIVE_MINUTES
    oi_mixed = oi_units_n > 1
    oi_evaluable = (
        usable_oi >= OI_MIN_DISTINCT_TIMESTAMPS
        and oi_units_n == 1
        and first_oi_bad is False
        and oi_dups == 0
    )
    heartbeat = live_bars == HEARTBEAT_LIVE_BARS and outage_overlap is False
    declared = declared_liquidation_available(capability)
    capability_present = capability is not None
    prereq = declared is True and heartbeat
    liq_table = _bool(atomic.get("liquidation_table_present"), default=False)
    liq_count = _optional_int(atomic.get("liquidation_event_count"))
    if liq_table and liq_count is not None:
        liq_rows_present: Optional[bool] = liq_count > 0
    else:
        liq_rows_present = None

    in_requested = _bool(atomic.get("in_requested_interval"), default=False)
    row = dict(atomic)
    row.update(
        grid_role="requested_interval" if in_requested else "maturity_lookback",
        all_five_exact_live_minutes=all_five,
        bar_coverage_eligible=all_five,
        price_feature_non_null=price_non_null,
        notional_eligible=notional,
        pit_history_present=status == "OK",
        pit_overlap_fail_closed=status == "OVERLAP_FAIL_CLOSED",
        pit_status=status,
        missing_pit_history=status in {"TABLE_ABSENT", "NO_ROW"},
        volume_notional_non_null=volume_non_null,
        taker_notional_non_null=taker_non_null,
        oi_mixed_units=oi_mixed,
        oi_evaluable=oi_evaluable,
        oi_feature_non_null=oi_evaluable,
        outage_overlap=outage_overlap,
        outage_status=outage_status,
        heartbeat_healthy=heartbeat,
        liquidation_capability_row_present=capability_present,
        liquidation_live_supported=None if capability is None else capability.get("live_supported"),
        liquidation_enabled=None if capability is None else capability.get("enabled"),
        liquidation_coverage_type=None if capability is None else capability.get("coverage_type"),
        liquidation_declared_available=declared,
        liquidation_vote_prereq_without_percentile=prereq,
        liquidation_feature_non_null=prereq,
        liquidation_rows_present=liq_rows_present,
        pit_quantity_unit=unit if status == "OK" else atomic.get("pit_quantity_unit"),
    )
    return row


def _aware(ts: datetime) -> datetime:
    if not isinstance(ts, datetime) or ts.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return ts.astimezone(UTC)


def _optional_int(value) -> Optional[int]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError("boolean is not an integer count")
    return int(value)


def _int(value, *, default: int) -> int:
    parsed = _optional_int(value)
    return default if parsed is None else parsed


def _optional_bool(value) -> Optional[bool]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
    raise ValueError(f"expected a boolean, got {value!r}")


def _bool(value, *, default: bool) -> bool:
    parsed = _optional_bool(value)
    return default if parsed is None else parsed
