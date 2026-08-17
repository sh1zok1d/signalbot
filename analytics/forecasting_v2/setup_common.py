"""
V2 shared setup-detector foundation (Stage 5 — Setup Detectors, PR 1 of
~4, docs/FORECASTING_ROADMAP.md §I stage 5).

Stage 4 (complete) gives every future detector one immutable
`V2ContextSnapshot` per decision boundary `T`: the already-computed 4h
regime and 1h bias, tied to the same `T`. This module answers a
DIFFERENT question — not "what is the context," but "what shared,
detector-independent MATH and CONTEXT-COMPATIBILITY logic do all three
Stage 5 detector families (`TREND_PULLBACK`, `COMPRESSION_BREAKOUT`,
`CONFIRMED_BREAKOUT`) need, computed exactly once rather than reinvented
per family":

  - `directional_context_gate()` — §7.0b's canonical breakout
    directional-context compatibility gate. Used by `COMPRESSION_BREAKOUT`
    and `CONFIRMED_BREAKOUT` only (never `TREND_PULLBACK`, which has its
    own stricter "4h trending AND 1h same direction" precondition, §7.1).
  - `range_proxy_pct()` — §7's `RANGE_PROXY_pct(timeframe, N=14, B)`, the
    rolling-mean volatility proxy substituting for a literal ATR field
    this codebase does not have.
  - `protection_buffer()` — §7's `max(3*tick_size, reference_price *
    RANGE_PROXY_pct/100*0.5)` structural-invalidation buffer, shared by
    all three families' invalidation-price formulas.
  - `select_extreme_anchor()` — §7.0c's deterministic most-recent-tie
    rule for identity-bearing lookback extrema (`TREND_PULLBACK`'s
    `trend_leg_extreme`, `CONFIRMED_BREAKOUT`'s `resistance_level`/
    `support_level` — never `COMPRESSION_BREAKOUT`'s `range_high`/
    `range_low`, which are plain numeric extrema with no bucket-identity
    ambiguity, §7.0c).

This PR implements ZERO setup detection. No `TREND_PULLBACK`,
`COMPRESSION_BREAKOUT`, or `CONFIRMED_BREAKOUT` candidate can be produced
by anything in this module — no `EARLY_SIGNAL`/`CONFIRMED` transition, no
entry zone, no invalidation PRICE for a specific episode (only the
generic `protection_buffer` primitive those prices will later be built
from), no `structural_anchor`/episode-identity construction, no episode
lifecycle/state machine, no confidence scoring, no entry feasibility, no
runtime wiring. Those are PR 2/~4 (`TREND_PULLBACK`), PR 3/~4
(`COMPRESSION_BREAKOUT`), and PR 4/~4 (`CONFIRMED_BREAKOUT` + Stage 5
completion).

**`V2SetupFoundationError` vs. `None` (§21, mirrors #36-#38's posture).**
Malformed/impossible PRESENT input (a non-`Mapping` row, a row whose
identity does not match what was requested, a non-finite/negative/bool
numeric value, an unsupported `timeframe`/`mode`/`breakout_direction`)
always raises `V2SetupFoundationError` — never silently becomes `None`.
Legitimately UNAVAILABLE derived input (an incomplete historical window,
an absent `range_proxy_pct` feeding `protection_buffer`) returns `None` —
never a fabricated `0.0`/fallback value. This module never conflates the
two (§22's "no silent fallback" rule).

**Pure module.** No DB, no `asyncpg`, no network, no filesystem, no
clock, no config loading, no `random`/`uuid`/`subprocess`. Consumes only
already-fetched `Mapping` rows (a future detector-specific assembler owns
turning `storage/v2_setup_readers.py` reads into these rows — this
module does not fetch anything itself) and Stage 4's `V2ContextSnapshot`.
Every public function is synchronous.

**Why `RANGE_PROXY_N`/`SETUP_RANGE_TIMEFRAMES` are not caller-tunable
(load-bearing).** §23 freezes `RANGE_PROXY_N = 14` and `BUFFER_MULTIPLIER
= 0.5` as VERSIONED parameters — their V2-v0 *values* are frozen, and any
future change is a `rules_version` bump, never a silent runtime choice.
Exposing `n`/timeframe as an unconstrained keyword here would let a
future caller accidentally (or silently) tune production semantics
outside that versioning discipline. `range_proxy_pct()` therefore hard-
codes `N=14` internally (no `n=...` parameter at all) and restricts
`timeframe` to exactly the two values the frozen detectors actually use
(`SETUP_RANGE_TIMEFRAMES = ("15m", "1h")`, §7.1/§7.3) — an unsupported
timeframe is a caller error (`V2SetupFoundationError`), not a silently
broadened capability.
"""
from __future__ import annotations

from collections.abc import Mapping as _AbcMapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Mapping, Optional, Sequence

from analytics.forecasting_v2.alignment import (
    TIMEFRAME_MINUTES, V2AlignmentError, selected_bucket,
)
from analytics.forecasting_v2.bias_1h import (
    BEARISH as BIAS_BEARISH,
    BIAS_UNAVAILABLE,
    BULLISH as BIAS_BULLISH,
)
from analytics.forecasting_v2.context_snapshot import V2ContextSnapshot
from analytics.forecasting_v2.events import DIRECTIONS, LONG, SHORT
from analytics.forecasting_v2.regime_4h import (
    BEARISH_TRENDING, BULLISH_TRENDING, INSUFFICIENT_DATA,
)

__all__ = [
    "V2SetupFoundationError",
    "CONTEXT_ACCEPT",
    "REJECT_REGIME_UNAVAILABLE",
    "REJECT_REGIME_OPPOSES",
    "REJECT_BIAS_UNAVAILABLE",
    "REJECT_BIAS_OPPOSES",
    "V2DirectionalContextDecision",
    "directional_context_gate",
    "RANGE_PROXY_N",
    "SETUP_RANGE_TIMEFRAMES",
    "range_proxy_pct",
    "MIN_TICK_BUFFER_TICKS",
    "BUFFER_MULTIPLIER",
    "protection_buffer",
    "V2ExtremeAnchor",
    "select_extreme_anchor",
]


class V2SetupFoundationError(ValueError):
    """Malformed/impossible PRESENT input to any primitive in this module:
    a non-`Mapping` row, a row whose identity (`timeframe`/`bucket_ts`)
    does not match what was requested, a duplicate/out-of-window bucket, a
    non-finite/negative/bool numeric value, an unsupported `timeframe`/
    `mode`/`breakout_direction`, or a non-`V2ContextSnapshot` `context`.
    Never raised for legitimately UNAVAILABLE derived data — that returns
    `None`; see module docstring."""


# ---- shared numeric/identity validation (mirrors context_evidence.py/
# regime_4h.py/bias_1h.py's own posture; a small local, private copy —
# not a cross-module import of their private helpers, consistent with
# this codebase's established small-duplication-over-cross-module-
# private-import precedent) -------------------------------------------------
def _validate_utc_datetime(value: Any, name: str) -> datetime:
    if type(value) is not datetime:
        raise V2SetupFoundationError(
            f"{name} must be a datetime, got {type(value).__name__}: {value!r}")
    if value.tzinfo is None or value.utcoffset() is None:
        raise V2SetupFoundationError(f"{name} must be timezone-aware, got {value!r}")
    if value.utcoffset() != timedelta(0):
        raise V2SetupFoundationError(f"{name} must be UTC (offset 0), got offset {value.utcoffset()}")
    if value.second != 0 or value.microsecond != 0:
        raise V2SetupFoundationError(
            f"{name} must be a whole minute (no seconds/microseconds), got {value!r}")
    return value


def _is_finite(value: float) -> bool:
    return value == value and value not in (float("inf"), float("-inf"))  # NaN != NaN


def _validate_finite_numeric(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise V2SetupFoundationError(
            f"{name} must be a real number, got {type(value).__name__}: {value!r}")
    v = float(value)
    if not _is_finite(v):
        raise V2SetupFoundationError(f"{name} must be finite, got {value!r}")
    return v


def _validate_positive_finite(value: Any, name: str) -> float:
    v = _validate_finite_numeric(value, name)
    if not (v > 0.0):
        raise V2SetupFoundationError(f"{name} must be > 0, got {v!r}")
    return v


def _validate_nonnegative_finite(value: Any, name: str) -> float:
    v = _validate_finite_numeric(value, name)
    if v < 0.0:
        raise V2SetupFoundationError(f"{name} must be >= 0.0, got {v!r}")
    return v


def _validate_row_sequence(rows: Any, name: str) -> Any:
    """Fail closed on a top-level `rows`/`candidates` argument that is not
    even a legitimate iterable-of-rows container — `None`, or a bare
    `str`/`bytes`/`bytearray` (which *is* iterable, character-by-character,
    and would otherwise silently produce a confusing per-character
    "row must be a Mapping" error instead of a clear container-shape
    error). A genuinely empty sequence (`[]`/`()`) is NOT rejected here —
    that remains each caller's own legitimate "no rows"/"no candidates"
    case, handled by that caller's own downstream logic."""
    if rows is None or isinstance(rows, (str, bytes, bytearray)):
        raise V2SetupFoundationError(
            f"{name} must be a Sequence of Mapping rows (not None/str/bytes), got "
            f"{type(rows).__name__}: {rows!r}")
    try:
        iter(rows)
    except TypeError as exc:
        raise V2SetupFoundationError(
            f"{name} must be an iterable Sequence of Mapping rows, got "
            f"{type(rows).__name__}: {exc}") from exc
    return rows


# ============================================================================
# §7.0b — canonical directional-context compatibility gate
# ============================================================================
CONTEXT_ACCEPT = "ACCEPT"
REJECT_REGIME_UNAVAILABLE = "REJECT_REGIME_UNAVAILABLE"
REJECT_REGIME_OPPOSES = "REJECT_REGIME_OPPOSES"
REJECT_BIAS_UNAVAILABLE = "REJECT_BIAS_UNAVAILABLE"
REJECT_BIAS_OPPOSES = "REJECT_BIAS_OPPOSES"

_REJECT_REASONS = (
    REJECT_REGIME_UNAVAILABLE, REJECT_REGIME_OPPOSES,
    REJECT_BIAS_UNAVAILABLE, REJECT_BIAS_OPPOSES,
)


@dataclass(frozen=True)
class V2DirectionalContextDecision:
    """§7.0b's gate result. Deliberately preserves the FOUR distinct
    rejection categories (§21: "Unavailable" is a different failure class
    from "Rejected"/countertrend opposition) rather than collapsing them
    into an opaque `bool` — a future caller that needs to distinguish
    "the context data wasn't there" from "the context firmly disagreed"
    (e.g. for observability/notification wording) can do so directly from
    `reason`, without recomputing the gate. `reason` labels are
    implementation observability only, not a new model threshold — they
    do not participate in `rules_version`."""
    accepted: bool
    reason: Optional[str]

    def __post_init__(self) -> None:
        if not isinstance(self.accepted, bool):
            raise V2SetupFoundationError(
                f"accepted must be a bool, got {type(self.accepted).__name__}")
        if self.accepted:
            if self.reason != CONTEXT_ACCEPT:
                raise V2SetupFoundationError(
                    f"reason must be {CONTEXT_ACCEPT!r} when accepted is True, "
                    f"got {self.reason!r}")
        elif self.reason not in _REJECT_REASONS:
            raise V2SetupFoundationError(
                f"reason must be one of {_REJECT_REASONS} when accepted is False, "
                f"got {self.reason!r}")


def directional_context_gate(
    context: V2ContextSnapshot, breakout_direction: str,
) -> V2DirectionalContextDecision:
    """§7.0b's frozen decision tree, evaluated in order (4h availability,
    4h opposition, 1h availability, 1h opposition, otherwise ACCEPT) —
    never reordered. Consumes ONLY `context` (a `V2ContextSnapshot`,
    already self-validated by Stage 4 to belong to one `T`) and
    `breakout_direction` — it never recomputes `regime_4h`/`bias_1h`
    itself and never accepts separate `regime`/`bias`/`B4h`/`B1h`
    arguments (a `V2ContextSnapshot` already guarantees both results
    belong to the same decision boundary; see
    `context_snapshot.py`'s own docstring for why that guarantee exists).

    This gate is for the TWO breakout families only
    (`COMPRESSION_BREAKOUT`/`CONFIRMED_BREAKOUT`, §7.2/§7.3) —
    `TREND_PULLBACK` never calls this; it has its own stricter "4h
    trending AND 1h same direction" precondition (§7.1), which this gate
    would be redundant against.

    `NON_DIRECTIONAL` 4h regime and `NEUTRAL_NOT_ESTABLISHED` 1h bias are
    NOT countertrend signals (`V2_PRODUCT_CONTRACT.md` §4.4) and PASS
    each of their respective layers — only a firmly-established OPPOSITE
    regime/bias rejects, and only `INSUFFICIENT_DATA`/`"UNAVAILABLE"`
    (a required input that could not be computed at all) rejects for
    data-availability reasons, a distinct category from countertrend
    opposition (§21).

    Raises `V2SetupFoundationError` for a non-`V2ContextSnapshot`
    `context` or a `breakout_direction` not exactly `"LONG"`/`"SHORT"`
    (canonical `analytics.forecasting_v2.events.LONG`/`SHORT` — no
    case-insensitive matching, no `"BUY"`/`"long"` aliasing, never
    inferred from `context` itself)."""
    if not isinstance(context, V2ContextSnapshot):
        raise V2SetupFoundationError(
            f"context must be a V2ContextSnapshot, got {type(context).__name__}")
    if breakout_direction not in DIRECTIONS:
        raise V2SetupFoundationError(
            f"breakout_direction must be one of {DIRECTIONS}, got {breakout_direction!r}")

    # ---- 4h layer: availability, then opposition -----------------------
    regime = context.regime_4h.regime
    if regime == INSUFFICIENT_DATA:
        return V2DirectionalContextDecision(accepted=False, reason=REJECT_REGIME_UNAVAILABLE)
    if regime == BULLISH_TRENDING and breakout_direction == SHORT:
        return V2DirectionalContextDecision(accepted=False, reason=REJECT_REGIME_OPPOSES)
    if regime == BEARISH_TRENDING and breakout_direction == LONG:
        return V2DirectionalContextDecision(accepted=False, reason=REJECT_REGIME_OPPOSES)
    # NON_DIRECTIONAL, or a trending regime ALIGNED with breakout_direction: PASS.

    # ---- 1h layer: availability, then opposition -----------------------
    bias = context.bias_1h.bias
    if bias == BIAS_UNAVAILABLE:
        return V2DirectionalContextDecision(accepted=False, reason=REJECT_BIAS_UNAVAILABLE)
    if bias == BIAS_BULLISH and breakout_direction == SHORT:
        return V2DirectionalContextDecision(accepted=False, reason=REJECT_BIAS_OPPOSES)
    if bias == BIAS_BEARISH and breakout_direction == LONG:
        return V2DirectionalContextDecision(accepted=False, reason=REJECT_BIAS_OPPOSES)
    # NEUTRAL_NOT_ESTABLISHED, or a firm bias ALIGNED with breakout_direction: PASS.

    return V2DirectionalContextDecision(accepted=True, reason=CONTEXT_ACCEPT)


# ============================================================================
# §7 — RANGE_PROXY_pct(timeframe, N=14, B)
# ============================================================================
RANGE_PROXY_N = 14

# Only the two timeframes the CURRENT frozen detectors actually use
# (TREND_PULLBACK/COMPRESSION_BREAKOUT: 15m; CONFIRMED_BREAKOUT: 1h,
# §7.1/§7.3) — deliberately not the full V2 timeframe set.
SETUP_RANGE_TIMEFRAMES = ("15m", "1h")

_RANGE_METRIC = "range_width_pct_median"


def range_proxy_pct(
    rows: Sequence[Mapping], *, timeframe: str, bucket_ts: datetime,
) -> Optional[float]:
    """§7's `RANGE_PROXY_pct(timeframe, 14, bucket_ts)`: the ordinary
    arithmetic mean of `range_width_pct_median` (consensus scope) over
    EXACTLY the `RANGE_PROXY_N=14` most recent closed `timeframe` buckets
    ending at (and including) `bucket_ts` — `bucket_ts - 13*tf, ...,
    bucket_ts - tf, bucket_ts`. `rows` is caller-supplied, already-fetched
    data (this function performs no I/O of its own; a future detector
    assembler owns fetching exactly this window via
    `storage/v2_setup_readers.py::read_v2_consensus_feature_window`).

    Returns `None` (UNAVAILABLE) if one or more of the 14 expected
    buckets is legitimately missing from `rows` entirely, OR if a
    present expected row's own `range_width_pct_median` is `None` — NEVER
    a partial/incomplete-window mean, and never a fallback to the latest/
    nearest available bucket.

    Raises `V2SetupFoundationError` for: an unsupported `timeframe` (not
    in `SETUP_RANGE_TIMEFRAMES`); a non-`Mapping` row; a row whose own
    `timeframe` field does not match the requested `timeframe`; a row
    `bucket_ts` outside the exact expected 14-bucket grid (an
    "unexpected"/out-of-window bucket, e.g. from a caller-side query bug)
    — never silently dropped; a duplicate row for the same expected
    bucket; or a PRESENT `range_width_pct_median` that is non-finite,
    negative, or a `bool`. **Corruption precedence (load-bearing,
    mirrors #36-#38's posture):** every PRESENT row is validated for
    corruption BEFORE the exact-grid-completeness check ever runs — a
    malformed present value is never masked merely because a DIFFERENT
    expected bucket happens to be legitimately missing elsewhere in the
    same window."""
    rows = _validate_row_sequence(rows, "rows")
    if timeframe not in SETUP_RANGE_TIMEFRAMES:
        raise V2SetupFoundationError(
            f"timeframe must be one of {SETUP_RANGE_TIMEFRAMES}, got {timeframe!r}")
    bucket_ts = _validate_utc_datetime(bucket_ts, "bucket_ts")

    # bucket_ts must be a legal CLOSED-bucket START on timeframe's own
    # canonical UTC grid (§7), not merely an aware/UTC/whole-minute
    # datetime — e.g. 12:07 is whole-minute-valid but not a legal 15m
    # bucket start. Reuses alignment.py's existing pure grid primitives
    # rather than inventing a second, competing grid convention here:
    # bucket_ts is a legal timeframe bucket start iff treating
    # (bucket_ts + one timeframe interval) as a decision boundary T and
    # selecting timeframe's bucket for that T round-trips back to
    # bucket_ts exactly. selected_bucket() itself already enforces T is a
    # legal 5m-grid-aligned decision boundary, so many misalignments raise
    # V2AlignmentError from inside selected_bucket(); any remaining
    # misalignment (still 5m-aligned, but not aligned to the LARGER
    # timeframe's own grid) is caught by the explicit inequality check
    # below. Never floors/normalizes bucket_ts on the caller's behalf.
    try:
        canonical_start = selected_bucket(
            timeframe, bucket_ts + timedelta(minutes=TIMEFRAME_MINUTES[timeframe]))
    except V2AlignmentError as exc:
        raise V2SetupFoundationError(
            f"bucket_ts {bucket_ts.isoformat()} is not a legal {timeframe} bucket start: "
            f"{exc}") from exc
    if canonical_start != bucket_ts:
        raise V2SetupFoundationError(
            f"bucket_ts {bucket_ts.isoformat()} is not aligned to the canonical {timeframe} "
            f"bucket grid (expected bucket start {canonical_start.isoformat()})")

    tf_delta = timedelta(minutes=TIMEFRAME_MINUTES[timeframe])
    expected_grid = tuple(
        bucket_ts - (RANGE_PROXY_N - 1 - i) * tf_delta for i in range(RANGE_PROXY_N))
    expected_set = frozenset(expected_grid)

    values_by_bucket: "dict[datetime, Optional[float]]" = {}
    for row in rows:
        if not isinstance(row, _AbcMapping):
            raise V2SetupFoundationError(
                f"range_proxy_pct row must be a Mapping, got {type(row).__name__}: {row!r}")
        row_timeframe = row.get("timeframe")
        if row_timeframe != timeframe:
            raise V2SetupFoundationError(
                f"range_proxy_pct row timeframe does not match the requested "
                f"{timeframe!r}, got {row_timeframe!r}")
        row_bucket_ts = _validate_utc_datetime(row.get("bucket_ts"), "row bucket_ts")
        if row_bucket_ts not in expected_set:
            raise V2SetupFoundationError(
                f"range_proxy_pct row bucket_ts {row_bucket_ts.isoformat()} is outside the "
                f"expected {RANGE_PROXY_N}-bucket {timeframe} grid ending at "
                f"{bucket_ts.isoformat()}")
        if row_bucket_ts in values_by_bucket:
            raise V2SetupFoundationError(
                f"duplicate range_proxy_pct row for expected bucket_ts "
                f"{row_bucket_ts.isoformat()}")

        raw_value = row.get(_RANGE_METRIC)
        value = (_validate_nonnegative_finite(raw_value, _RANGE_METRIC)
                 if raw_value is not None else None)
        values_by_bucket[row_bucket_ts] = value

    if len(values_by_bucket) != RANGE_PROXY_N:
        return None  # one or more expected buckets legitimately missing entirely
    values = [values_by_bucket[b] for b in expected_grid]
    if any(v is None for v in values):
        return None  # a present row's own metric value is legitimately missing
    return sum(values) / RANGE_PROXY_N


# ============================================================================
# §7 — protection_buffer(timeframe, B, reference_price)
# ============================================================================
MIN_TICK_BUFFER_TICKS = 3
BUFFER_MULTIPLIER = 0.5


def protection_buffer(
    *, reference_price: float, range_proxy_pct_value: Optional[float], tick_size: float,
) -> Optional[float]:
    """§7's `protection_buffer(timeframe, B, reference_price) =
    max(MIN_TICK_BUFFER_TICKS * tick_size, reference_price *
    RANGE_PROXY_pct(timeframe, 14, B) / 100 * BUFFER_MULTIPLIER)` —
    expressed as a pure function of the already-computed
    `range_proxy_pct_value` (this module's own `range_proxy_pct()`
    output) rather than re-deriving it from `timeframe`/`bucket_ts`/raw
    rows itself, so this primitive has no I/O and no timeframe/window
    concept of its own. Does NOT quantize/round the result to
    `tick_size` — the frozen formula is a `max(...)`, not a rounding
    rule.

    `reference_price`/`tick_size` are validated BEFORE the
    `range_proxy_pct_value is None` short-circuit (corruption precedence
    — a malformed PRESENT price/tick is never masked merely because the
    volatility input happens to be legitimately unavailable). Returns
    `None` (UNAVAILABLE) only after both PRESENT numeric inputs are
    confirmed valid, and only because the required volatility input
    itself could not be computed.

    Raises `V2SetupFoundationError` for a non-finite/non-positive/`bool`
    `reference_price` or `tick_size`, or a non-finite/negative/`bool`
    PRESENT `range_proxy_pct_value`."""
    price = _validate_positive_finite(reference_price, "reference_price")
    tick = _validate_positive_finite(tick_size, "tick_size")
    if range_proxy_pct_value is None:
        return None
    proxy = _validate_nonnegative_finite(range_proxy_pct_value, "range_proxy_pct_value")

    tick_floor = MIN_TICK_BUFFER_TICKS * tick
    volatility_term = price * proxy / 100.0 * BUFFER_MULTIPLIER
    return max(tick_floor, volatility_term)


# ============================================================================
# §7.0c — deterministic most-recent-tie extreme selection
# ============================================================================
@dataclass(frozen=True)
class V2ExtremeAnchor:
    """One identity-bearing extreme: the `bucket_ts` that ACHIEVED the
    max/min `value` over some caller-defined lookback, tie-broken per
    §7.0c. Used ONLY for anchors where *which* bucket achieved the
    extreme is itself identity-bearing (`TREND_PULLBACK`'s
    `trend_leg_extreme`, `CONFIRMED_BREAKOUT`'s `resistance_level`/
    `support_level`) — NEVER for `COMPRESSION_BREAKOUT`'s `range_high`/
    `range_low`, which are plain numeric extrema with no bucket-identity
    ambiguity (§7.0c explicitly excludes them).

    Public Stage 5 API — self-validates on ANY direct construction (not
    only via `select_extreme_anchor()`), reusing this module's own
    existing `_validate_utc_datetime`/`_validate_finite_numeric`
    primitives so a hand-built instance can never carry a naive/non-UTC/
    non-whole-minute `bucket_ts` or a non-finite/`bool` `value`. `value`
    is deliberately NOT restricted to positive/nonnegative — an abstract
    extreme helper may legitimately select any finite numeric value — and
    is validated but never coerced/reassigned."""
    bucket_ts: datetime
    value: float

    def __post_init__(self) -> None:
        _validate_utc_datetime(self.bucket_ts, "bucket_ts")
        _validate_finite_numeric(self.value, "value")


def select_extreme_anchor(
    candidates: Sequence[Mapping], *, mode: str,
) -> Optional[V2ExtremeAnchor]:
    """§7.0c's frozen tie-break rule: the max (`mode="max"`) or min
    (`mode="min"`) `value` among `candidates`, compared at FULL stored
    precision (no rounding before comparison) — and when two or more
    candidates share the identical extreme value, the MOST RECENT
    `bucket_ts` among the tied candidates is selected as the anchor.
    Input order never influences the result (the tie-break is a pure
    function of the candidate SET, not iteration order).

    Each candidate is a `Mapping` with `bucket_ts` (an aware, UTC,
    whole-minute `datetime`) and `value` (a finite, non-`bool` real
    number) — mirroring this module's other primitives' `Mapping`-row
    convention rather than requiring a caller to pre-construct
    `V2ExtremeAnchor` instances just to call this function.

    Returns `None` for an empty `candidates` sequence — legitimately "no
    extreme exists yet," mirroring this module's/PR 1-3's general
    missing-vs-malformed posture (never an error for genuine absence).

    Raises `V2SetupFoundationError` for: `mode` not exactly `"max"`/
    `"min"`; a non-`Mapping` candidate; a malformed `bucket_ts`/`value`;
    or a duplicate `bucket_ts` among the candidates (two candidates
    cannot legitimately claim the same bucket)."""
    if mode not in ("max", "min"):
        raise V2SetupFoundationError(f"mode must be 'max' or 'min', got {mode!r}")
    candidates = _validate_row_sequence(candidates, "candidates")

    validated: "list[tuple[datetime, float]]" = []
    seen_bucket_ts: set = set()
    for candidate in candidates:
        if not isinstance(candidate, _AbcMapping):
            raise V2SetupFoundationError(
                f"candidate must be a Mapping, got {type(candidate).__name__}: {candidate!r}")
        bucket_ts = _validate_utc_datetime(candidate.get("bucket_ts"), "candidate bucket_ts")
        value = _validate_finite_numeric(candidate.get("value"), "candidate value")
        if bucket_ts in seen_bucket_ts:
            raise V2SetupFoundationError(
                f"duplicate candidate bucket_ts {bucket_ts.isoformat()}")
        seen_bucket_ts.add(bucket_ts)
        validated.append((bucket_ts, value))

    if not validated:
        return None

    extreme_value = max(v for _, v in validated) if mode == "max" else min(v for _, v in validated)
    tied_bucket_ts = [bucket_ts for bucket_ts, v in validated if v == extreme_value]
    anchor_bucket_ts = max(tied_bucket_ts)  # most recent among ties, §7.0c
    return V2ExtremeAnchor(bucket_ts=anchor_bucket_ts, value=extreme_value)
