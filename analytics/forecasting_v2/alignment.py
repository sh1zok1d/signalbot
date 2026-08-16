"""
V2 multi-timeframe decision-clock/bucket-alignment primitives (Stage 3 —
Multi-timeframe Alignment, PR 1 of ~3,
docs/FORECASTING_ROADMAP.md §I stage 3).

Implements exactly the two pure timestamp-selection layers
`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §1 freezes — nothing else:

  - **Layer 1 (impure boundary, still explicit-input-only here)** —
    `decision_boundary(now, soft_grace_s=...)`: wall-clock processing time
    `now` -> the logical closed-5m decision boundary `T` a V2 decision run
    is allowed to act on. §1.2: "Reused unchanged from the already-frozen
    and already-implemented `runtime/shadow_cli.py::
    select_latest_closed_5m_bucket`, generalized only in name." This
    module does NOT import that V1 helper (that would create the wrong
    `analytics -> runtime` dependency direction) — it re-implements the
    identical frozen algorithm locally; `tests/analytics/
    test_forecasting_v2_alignment.py` proves the two agree on every input,
    from the test side only.
  - **Layer 2 (pure)** — `selected_bucket(timeframe, T)`: given `T`,
    deterministically selects the ONE legal closed bucket's START
    (`bucket_ts`) for one of the four V2 semantic timeframes. Never reads
    a clock; the same `T` always yields the same bucket, on any machine,
    at any wall-clock time (§1.1's core invariant: processing delay MUST
    NOT change which buckets a decision is computed from).

`decision_boundary` returns `T` — the CLOSE INSTANT of the freshest legal
5m bucket, NOT that bucket's start. `selected_bucket` returns the bucket's
START. Conflating the two is exactly the mistake §1.2/§1.3 guard against;
see each function's own docstring for the worked distinction.

This module answers only "which closed bucket timestamps are legal" — it
does not read `exchange_feature_vectors`/`consensus_feature_vectors`/
`percentile_snapshots`/`data_health_snapshots`, does not decide what to do
with a selected bucket (context/regime/bias/setup/episode logic), and does
not itself read `now` or any config file. Those are for later Multi-
timeframe Alignment PRs and the future Context Engines / Setup Detectors /
Episode State Machine stages.

Pure only: no DB, network, filesystem, config loading, environment access,
clock read (`datetime.now()`/`datetime.utcnow()`/`time.time()`/
`time.monotonic()`), `random`, `uuid`, `asyncio`, `sleep`, or `subprocess`
anywhere in this module. Both public functions are deterministic total
functions of their explicit arguments; there is no module-level mutable
state. `soft_grace_s` is reused unchanged from the existing, frozen
`stage2.bucket_close.soft_grace_s` (`config/stage2.yaml`) — this module
never reads that file itself; a future orchestration layer resolves the
active value and passes it in explicitly, exactly like every other V2
value object in this package (`V2EventProvenance`, `V2EpisodeEvent`) takes
its provenance by explicit argument rather than resolving it internally.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import MappingProxyType
from typing import Any

__all__ = ["V2AlignmentError", "TIMEFRAME_MINUTES", "decision_boundary", "selected_bucket"]


class V2AlignmentError(ValueError):
    """Malformed alignment input: a non-UTC/naive/non-datetime `now` or
    `T`, an out-of-range `soft_grace_s`, an unsupported V2 timeframe, or a
    `T` that is not itself an already-5m-aligned whole-minute decision
    boundary. Never silently coerced or floored on the caller's behalf —
    see `selected_bucket`'s own docstring for why `T` is validated, not
    re-floored."""


# ---- exact V2 semantic timeframes (§1.3's TF_MINUTES) -----------------------
# Stage 2 also computes 1m features (analytics/feature_engine/models.py's own
# TIMEFRAME_MINUTES includes "1m") — that does NOT make "1m" a V2 semantic
# timeframe. V2's four timeframes are a deliberately separate, smaller,
# case-sensitive namespace with no aliases: "1H"/"4H"/"05m"/"15M"/"60m"/
# "240m"/"1m" are all unsupported by construction (simply absent as keys).
# Exposed as a MappingProxyType so a caller cannot mutate the shared mapping.
TIMEFRAME_MINUTES = MappingProxyType({
    "5m": 5,
    "15m": 15,
    "1h": 60,
    "4h": 240,
})

_UTC = timezone.utc
# 1970-01-01T00:00:00Z — the anchor every grid boundary (5m/15m/1h/4h) is
# computed from. Using minutes-since-epoch (never minute-of-hour) is what
# makes the 4h grid land on 00:00/04:00/08:00/12:00/16:00/20:00 UTC without
# any special-casing of hours: the epoch is itself UTC midnight, hours
# divide evenly into a day, and 240 (4h in minutes) divides a day (1440
# minutes) evenly (§1.3).
_EPOCH = datetime(1970, 1, 1, tzinfo=_UTC)


def _minutes_since_epoch_floor(dt: datetime) -> int:
    """Whole integer minutes between the UTC epoch and `dt`, floored — any
    sub-minute (second/microsecond) remainder is dropped. Pure integer
    arithmetic (`timedelta.days`/`.seconds`), never float timestamp
    arithmetic, so there is no floating-point rounding risk at any scale."""
    delta = dt - _EPOCH
    total_seconds = delta.days * 86400 + delta.seconds
    return total_seconds // 60


def _floor_minutes_to_grid(total_minutes: int, grid_minutes: int) -> int:
    return (total_minutes // grid_minutes) * grid_minutes


def _validate_utc_datetime(value: Any, name: str) -> datetime:
    # Exact type check (not isinstance), matching
    # runtime/shadow_cli.py::select_latest_closed_5m_bucket's own posture —
    # a datetime subclass is not silently accepted as if it were the same
    # a bool is never mistaken for a datetime either.
    if type(value) is not datetime:
        raise V2AlignmentError(
            f"{name} must be a datetime, got {type(value).__name__}")
    if value.tzinfo is None or value.utcoffset() is None:
        raise V2AlignmentError(f"{name} must be timezone-aware")
    if value.utcoffset() != timedelta(0):
        raise V2AlignmentError(f"{name} must be UTC (offset 0), got {value.utcoffset()}")
    return value


def _validate_soft_grace_s(value: Any) -> int:
    # Exact type check so a bool (a subclass of int) is rejected, exactly
    # like runtime/shadow_cli.py::select_latest_closed_5m_bucket's own
    # `type(soft_grace_s) is not int` check. No arbitrary upper bound is
    # imposed — a deliberately large grace legitimately selects an older
    # boundary (§1.2).
    if type(value) is not int:
        raise V2AlignmentError(
            f"soft_grace_s must be an int, got {type(value).__name__}")
    if value < 0:
        raise V2AlignmentError("soft_grace_s must be >= 0")
    return value


def _validate_decision_boundary_T(T: Any) -> datetime:
    """Validate that `T` is already a legal V2 5m decision boundary — a
    datetime `decision_boundary()` itself could have produced. This is a
    FAIL-CLOSED check, never a floor: `selected_bucket` must not accept an
    arbitrary event timestamp and silently round it down to the nearest 5m
    decision boundary, because that would hide a caller bug (passing the
    wrong kind of timestamp) behind seemingly-correct output. Only
    `decision_boundary()` performs the Layer 1 floor from wall-clock time;
    Layer 2 only ever consumes an already-valid `T`."""
    _validate_utc_datetime(T, "T")
    if T.second != 0 or T.microsecond != 0:
        raise V2AlignmentError("T must be a whole minute (no seconds/microseconds)")
    if _minutes_since_epoch_floor(T) % 5 != 0:
        raise V2AlignmentError(
            "T must be aligned to the 5m grid (a logical V2 decision boundary, "
            "not an arbitrary timestamp)")
    return T


def decision_boundary(now: datetime, *, soft_grace_s: int) -> datetime:
    """Layer 1 (§1.2): map wall-clock processing time `now` to the logical
    V2 decision boundary `T` this processing run is allowed to act on.

        effective = now - soft_grace_s
        T = floor_to_grid(effective, 5m)     # latest 5m-grid instant <= effective
        return T

    `T` is the CLOSE INSTANT of the most recently closed 5m bucket eligible
    for a decision — i.e. the 5m bucket `[T - 5m, T)` is the freshest legal
    5m input. `T` is NOT that bucket's start; call
    `selected_bucket("5m", T)` to get the bucket start.

    `soft_grace_s` is reused unchanged from the existing, frozen
    `stage2.bucket_close.soft_grace_s` (`config/stage2.yaml`) — it is NOT a
    new V2 parameter and this function does not read that config file
    itself; a caller resolves the active value and passes it in. There is
    no arbitrary upper bound: a deliberately large grace legitimately
    selects an older boundary. This is NOT `stage2.bucket_close.
    hard_deadline_s` — that is an orthogonal write-path concept (§1.2) this
    function never reads or uses.

    This function takes `now` explicitly and never reads a clock itself
    (no `datetime.now()`/`datetime.utcnow()`/`time.time()` anywhere in this
    module) — the same `now` + the same `soft_grace_s` always produce the
    same `T`, which is what keeps live and replay decisions identical
    (§1.1). The actual future runtime owns reading the real wall clock and
    supplying it here.

    Raises `V2AlignmentError` for a non-datetime/naive/non-UTC `now`, or a
    non-`int`/bool/negative `soft_grace_s`."""
    now = _validate_utc_datetime(now, "now")
    soft_grace_s = _validate_soft_grace_s(soft_grace_s)
    effective = now - timedelta(seconds=soft_grace_s)
    total_minutes = _minutes_since_epoch_floor(effective)
    grid_minutes = _floor_minutes_to_grid(total_minutes, 5)
    return _EPOCH + timedelta(minutes=grid_minutes)


def selected_bucket(timeframe: str, T: datetime) -> datetime:
    """Layer 2 (§1.3, pure): given the logical decision boundary `T`,
    deterministically select the START (`bucket_ts`) of the ONE legal
    fully-closed bucket for `timeframe`.

        m = TIMEFRAME_MINUTES[timeframe]
        boundary = floor_to_grid(T, m)   # latest multiple-of-m-minutes
                                          # instant since the UTC epoch <= T
        return boundary - m               # the bucket's START

    The bucket returned represents `[bucket_ts, bucket_ts + m)`, and its
    closing instant (`boundary`) is always `<= T` by construction — a
    partially-formed bucket can never be selected (§1.3). For
    `timeframe="5m"` this always reduces to exactly `T - 5m`.

    `timeframe` must be exactly one of `"5m"`, `"15m"`, `"1h"`, `"4h"`
    (`TIMEFRAME_MINUTES`'s keys) — case-sensitive, no aliases. Stage 2 also
    computes 1m features, but `"1m"` is not a V2 semantic timeframe and is
    rejected here like any other unsupported value.

    `T` must already be a legal V2 5m decision boundary — timezone-aware
    UTC, a whole minute, and itself aligned to the 5m grid. A malformed `T`
    is REJECTED, never silently floored to the nearest legal boundary; only
    `decision_boundary()` performs that floor, so a caller cannot
    accidentally pass an arbitrary event timestamp here and have this
    function hide the mistake.

    Never reads a clock, config, or any external state — deterministic in
    `(timeframe, T)` alone. Raises `V2AlignmentError` for an unsupported
    `timeframe` or a malformed `T`."""
    # Exact-type check FIRST (consistent with this module's exact-type
    # validation posture elsewhere — `_validate_utc_datetime`,
    # `_validate_soft_grace_s`): an unhashable value (list/dict/set) would
    # otherwise raise TypeError from the `in` membership check below before
    # this function's own fail-closed V2AlignmentError ever gets a chance
    # to fire, silently widening the public API's error surface.
    if type(timeframe) is not str or timeframe not in TIMEFRAME_MINUTES:
        raise V2AlignmentError(
            f"unsupported timeframe {timeframe!r} "
            f"(supported: {sorted(TIMEFRAME_MINUTES)})")
    T = _validate_decision_boundary_T(T)
    m = TIMEFRAME_MINUTES[timeframe]
    total_minutes = _minutes_since_epoch_floor(T)
    boundary_minutes = _floor_minutes_to_grid(total_minutes, m)
    bucket_start_minutes = boundary_minutes - m
    return _EPOCH + timedelta(minutes=bucket_start_minutes)
