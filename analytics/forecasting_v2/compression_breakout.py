"""
V2 `COMPRESSION_BREAKOUT` setup detector (Stage 5 — Setup Detectors, PR 3
of ~4, docs/FORECASTING_ROADMAP.md §I stage 5).

#39 (merged) built the shared detector foundation; #40 (merged) built the
first concrete qualification, `TREND_PULLBACK`. This PR implements the
SECOND, per `docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §7.2:

    At the CURRENT closed 5m decision boundary `T`, does the already-
    observed 15m compression structure plus the current closed 5m
    breakout observation qualify as a new `COMPRESSION_BREAKOUT`
    candidate, and what are its deterministic structural facts
    (`detect_compression_breakout()` returns a
    `V2CompressionBreakoutCandidate`)?

**Load-bearing Stage 5 / Stage 6 boundary (mirrors `trend_pullback.py`,
do not blur).** This module answers ONLY the qualification question
above — the moment §7.2 calls "the first qualifying breakout close" is
represented here as a `V2CompressionBreakoutCandidate`: a qualification
WORTHY of `EARLY_SIGNAL` creation, never the `EARLY_SIGNAL` itself. It
does NOT:

  - create or persist an `EARLY_SIGNAL` event, `episode_id`, or
    `event_id`;
  - decide whether another ALREADY-ACTIVE episode already owns this
    exact structural anchor (`structural_anchor`, §12's
    `episode_logical_key`) — that requires querying episode history,
    which this stateless module never does;
  - evaluate `CONFIRMED`/`WEAKENING`/`INVALIDATED`/`EXPIRED`/`COMPLETED`
    transitions, the direction-aware false-break rule, or the boundary-
    equality HOLD convention (§7.2) — all of those are only meaningful
    relative to an ALREADY-EXISTING `EARLY_SIGNAL`'s own `T_detect`,
    which this module never constructs;
  - count `COMPRESSION_CONFIRMATION_MAX_AGE_5M_BUCKETS` against episode
    age, or a candidate's `EXPECTED_HORIZON` — both exposed below only as
    frozen family metadata, never evaluated by anything in this module;
  - apply family precedence/dedup against `CONFIRMED_BREAKOUT`/
    `TREND_PULLBACK` (§7.4) — this module never calls
    `detect_trend_pullback()`, never inspects a `CONFIRMED_BREAKOUT`
    result, and never suppresses anything.

Every one of those is Stage 6 (Episode State Machine) or later. Repeated
calls across consecutive qualifying `T`s each independently return a
fresh candidate; deduplicating those into one episode is Stage 6's job.

**Decision clock — DIFFERENT from `TREND_PULLBACK` (load-bearing).**
`TREND_PULLBACK` is evaluated ONLY on 15m formation boundaries.
`COMPRESSION_BREAKOUT` is evaluated at EVERY legal 5m V2 decision
boundary `T` — the breakout trigger is a 5m-close event, not a 15m one.
Given `context.T`: `B5 = selected_bucket("5m", T)`,
`B15 = selected_bucket("15m", T)`. There is NO `B15 + 15m == T`
restriction here (e.g. `T=12:20` is a perfectly legal evaluation instant,
`B5=[12:15,12:20)`, `B15=[12:00,12:15)` — `B15` need not have just
closed).

**Compression evidence (§7.2, exact `COMPRESSION_LOOKBACK=16`-bucket
grid ending at `B15`).** For each of the 16 expected 15m buckets `b`, a
bucket counts as `compressed_b` iff ALL of: (1) `b`'s own 15m consensus
row's `min_coverage_ratio >= SETUP_MIN_COVERAGE` and
`consensus_confidence >= SETUP_MIN_CONFIDENCE` (§6.2/§6.3's frozen
timeframe-invariant gate, reused unchanged); (2) `compression_score(15m,
COMPRESSION_PERCENTILE_WINDOW="30d", b)` (reusing
`context_evidence.compression_score()` UNCHANGED — never a private
`1.0 - percentile_rank` reimplementation) is available; (3) that score
`>= COMPRESSION_THRESHOLD=0.75` (boundary-inclusive: exactly `0.75`
qualifies). A degraded/unavailable bucket at EITHER layer does not count
as compressed with score `0.0` — it simply breaks a consecutive run,
exactly like a legitimately-missing bucket would.

**`compression_score()` takes a `V2TimeframeInputs`, not raw rows —
this module owns an EXTRA identity pre-validation layer
`find_consensus_percentile()` does not perform.**
`context_evidence.find_consensus_percentile()` only re-checks
`scope`/`exchange`/`timeframe`/`bucket_ts`/`sample_window_end` against
the `V2TimeframeInputs` it is handed — it has no `symbol`/`market_type`/
`calculation_version`/`feature_schema_version` to compare against (a bare
`V2TimeframeInputs` does not carry those fields), and a row with the
WRONG `metric`/`percentile_window` is simply excluded from its match
search rather than raising. This module therefore independently
validates every PRESENT percentile row's full identity (`scope`,
`exchange`, `symbol`, `market_type`, `metric`, `timeframe`,
`percentile_window`, `calculation_version`, `feature_schema_version`,
`bucket_ts`) BEFORE ever constructing a per-bucket `V2TimeframeInputs` to
hand to `compression_score()` — so a wrong-metric/wrong-symbol/
wrong-window row raises here, not merely gets silently ignored.

**Deterministic maximal-run selection (§7.2, new algorithm relative to
#40).** Partition the 16 chronological buckets into MAXIMAL consecutive
`compressed_b == True` runs (a run ends at the first `False`/unavailable
bucket or the lookback's right edge). A run qualifies iff its length
`>= COMPRESSION_MIN_DURATION=6` — using the FULL run length, never
truncated to the most recent 6. Among ALL qualifying runs, the one with
the MOST RECENT end bucket (closest to `B15`) is selected — precedence,
in order: (1) most recent end; (2) if ambiguous, longest; (3) if still
ambiguous, latest end again. In an ordinary maximal-run partition no two
runs can share an end bucket, so criterion (1) already uniquely
determines the winner; (2)/(3) exist purely for deterministic robustness.
`B15` itself is NOT required to be part of, or adjacent to, the selected
run — a qualifying run may have ended one or more buckets before `B15`
if no newer qualifying run exists (`B15` still separately participates in
its own current-quality gate, `RANGE_PROXY`, and reference-price lookups
below). Zero qualifying runs -> no candidate (`None`).

**Structural range (§7.0a, over ONLY the selected run's own buckets).**
For every 15m bucket in the SELECTED run, `HTF_high`/`HTF_low` are
derived via `aligned_inputs.derive_reference_extrema()` UNCHANGED (never
a private high/low reimplementation from `close_price`/
`range_width_pct`/consensus fields) — this module owns identity
pre-validation of each PRESENT reference-feature row
(`exchange`/`symbol`/`market_type`/`timeframe`/`calculation_version`/
`feature_schema_version`/`bucket_ts` against the exact 16-bucket grid;
`derive_reference_extrema()` itself only re-checks the completeness gate
and the raw bar grid, not this identity). `range_high = max(HTF_high)`,
`range_low = min(HTF_low)` over EXACTLY the selected run's buckets — an
enormous high/low from an UNSELECTED older run never leaks in. Any
selected-run bucket's structural extrema being unavailable makes the
WHOLE structural range unavailable (`None`, fail closed, §7.0a);
`derive_reference_extrema()` raising `V2AlignedInputError` (reference
feature claims full/usable coverage but the raw 1m bar set does not
actually match) is wrapped as `V2CompressionBreakoutError`, never
silently downgraded to missingness.

**Fresh 5m crossing (§7.2) — distinguishes a NEW cross from merely
remaining outside an already-broken level.** Requires the current AND
immediately-previous closed Binance 5m reference closes:

    LONG  fresh cross: previous_close <= range_high AND current_close > range_high
    SHORT fresh cross: previous_close >= range_low  AND current_close < range_low

Boundary equality at the CURRENT close never creates a candidate (`==
range_high`/`== range_low` fails the strict `>`/`<`). If price was
already beyond the boundary on the PREVIOUS close too, this is not a
fresh crossing (`None`) — this module never repeatedly emits the same
outside-range condition every 5m tick, and never infers "first episode
globally" from episode storage (it only ever looks at this one
observable two-close transition).

**5m trigger validation (§7.2's three simultaneous EARLY_SIGNAL
requirements).** Once a fresh breakout direction is derived: (1) the
current `B5` consensus row's own `min_coverage_ratio`/
`consensus_confidence` must pass the same frozen §6.2/§6.3 gate; (2)
`price_direction_agreement >= BREAKOUT_MIN_AGREEMENT=2/3` (a quality/
directional-consensus gate only — direction itself is NEVER derived from
agreement); (3) `taker_delta_notional_usd_sum` must match the breakout
direction's sign exactly (`> 0` for LONG, `< 0` for SHORT — zero matches
neither; raw sign only, never percentile-scored/normalized). Finally,
the shared `setup_common.directional_context_gate(context, direction)`
(§7.0b, reused UNCHANGED — never reimplemented, never `TREND_PULLBACK`'s
own stricter precondition) must return `accepted is True`.

**Protection buffer / entry zone / invalidation (§7, §9, §10) — structural
facts only, no lifecycle activation.** The 15m reference price for
`protection_buffer()` is the canonical Binance 15m `close_price` AT
`B15` (from the same reference-feature window this module already reads
for the structural range) — NEVER the 5m breakout close itself
(§7 scopes the buffer to `timeframe=15m, B=B15`). `RANGE_PROXY_pct(15m,
14, B15)` reuses the FINAL 14 rows of the already-fetched 16-bucket 15m
consensus window (no second storage read). Entry zone/invalidation are
STRUCTURAL FACTS computed once at `T`:

    LONG:  entry_zone = [range_high, range_high + buffer]
           invalidation_price = range_low - buffer
    SHORT: entry_zone = [range_low - buffer, range_low]
           invalidation_price = range_high + buffer

This module never checks whether `invalidation_price` has since been
crossed, never applies the direction-aware false-break rule, and never
uses a future `confirmation_close_price` — all Stage 6.

**`V2CompressionBreakoutInputs` is a bare container, not self-validating**
(mirrors `V2TrendPullbackInputs`'s precedent) — `detect_compression_
breakout()` never trusts it blindly, whether built by `load_compression_
breakout_inputs()` or hand-constructed directly (tests, a future replay
harness).

Pure module: no DB, no `asyncpg`, no network, no filesystem, no clock (no
`datetime.now()`/`utcnow()`/`time.time()`), no config loading, no
`random`/`uuid`/`subprocess`. `detect_compression_breakout()` is
synchronous; the same `inputs` always yields the same result.
"""
from __future__ import annotations

from collections.abc import Mapping as _AbcMapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Mapping, Optional

from analytics.forecasting_v2.aligned_inputs import (
    V2_REFERENCE_EXCHANGE, V2AlignedInputError, V2TimeframeInputs, derive_reference_extrema,
)
from analytics.forecasting_v2.alignment import (
    TIMEFRAME_MINUTES, V2AlignmentError, selected_bucket,
)
from analytics.forecasting_v2.context_evidence import V2ContextEvidenceError, compression_score
from analytics.forecasting_v2.context_snapshot import V2ContextSnapshot
from analytics.forecasting_v2.events import DIRECTIONS, LONG, SHORT
from analytics.forecasting_v2.family_quality import V2FamilyQualityError, family_quality
from analytics.forecasting_v2.setup_common import (
    MIN_TICK_BUFFER_TICKS, RANGE_PROXY_N, SETUP_MIN_CONFIDENCE, SETUP_MIN_COVERAGE,
    V2SetupFoundationError, directional_context_gate, protection_buffer, range_proxy_pct,
)

__all__ = [
    "V2CompressionBreakoutError",
    "COMPRESSION_LOOKBACK",
    "COMPRESSION_MIN_DURATION",
    "COMPRESSION_THRESHOLD",
    "COMPRESSION_PERCENTILE_WINDOW",
    "BREAKOUT_MIN_AGREEMENT",
    "COMPRESSION_CONFIRMATION_MAX_AGE_5M_BUCKETS",
    "EXPECTED_HORIZON",
    "V2CompressionBreakoutInputs",
    "V2CompressionBreakoutCandidate",
    "detect_compression_breakout",
]


class V2CompressionBreakoutError(ValueError):
    """Malformed PRESENT input to this module: a non-
    `V2CompressionBreakoutInputs` argument, a non-`V2ContextSnapshot`
    `inputs.context`, a non-Mapping or identity-mismatched/duplicate/
    out-of-grid history row, a required field missing entirely from a
    returned row, a non-finite/non-positive/`bool` numeric value where a
    real number is required, malformed PRESENT quality/percentile/
    agreement/taker-flow data, an impossible simultaneous LONG+SHORT
    fresh-cross, an identity-mismatched/incomplete instrument row, or a
    wrapped `V2SetupFoundationError`/`V2ContextEvidenceError`/
    `V2AlignedInputError` from one of the shared primitives this module
    reuses, for genuinely corrupted (not missing) data. Never raised for
    a legitimate non-qualification — see module docstring's exhaustive
    list of `None` cases."""


# ============================================================================
# frozen V2-v0 COMPRESSION_BREAKOUT family constants (not runtime-tunable;
# every value here is already-frozen contract behavior, never a new or
# config-tuned parameter; no rules_version bump).
# ============================================================================
COMPRESSION_LOOKBACK = 16
COMPRESSION_MIN_DURATION = 6
COMPRESSION_THRESHOLD = 0.75
COMPRESSION_PERCENTILE_WINDOW = "30d"
BREAKOUT_MIN_AGREEMENT = 2.0 / 3.0
# Stage 6 (Episode State Machine) owns COUNTING an EARLY_SIGNAL's age
# against this and evaluating the CONFIRMED transition -- exposed here
# only as shared family metadata, never evaluated by anything in this
# module (see module docstring).
COMPRESSION_CONFIRMATION_MAX_AGE_5M_BUCKETS = 3
# Expected trade horizon FROM `CONFIRMED` (§14) -- Stage 6/7/8 metadata;
# this module never computes or reads a horizon deadline itself. Exported
# at package level as `COMPRESSION_BREAKOUT_EXPECTED_HORIZON` (never a
# second ambiguous package-level `EXPECTED_HORIZON` -- `trend_pullback.py`
# already claims that name at package scope, see `__init__.py`).
EXPECTED_HORIZON = timedelta(minutes=90)

_FIVE_MIN = timedelta(minutes=TIMEFRAME_MINUTES["5m"])
_FIFTEEN_MIN = timedelta(minutes=TIMEFRAME_MINUTES["15m"])
_FULL_15M_BAR_COUNT = TIMEFRAME_MINUTES["15m"]
_FULL_5M_BAR_COUNT = TIMEFRAME_MINUTES["5m"]
_COMPRESSION_METRIC = "range_width_pct_median"


# ---- shared numeric/identity validation (small local private copy, matching
# the established codebase precedent -- see trend_pullback.py's own
# docstring) ------------------------------------------------------------------
def _is_finite(value: float) -> bool:
    return value == value and value not in (float("inf"), float("-inf"))  # NaN != NaN


def _validate_finite_numeric(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise V2CompressionBreakoutError(
            f"{name} must be a real number, got {type(value).__name__}: {value!r}")
    v = float(value)
    if not _is_finite(v):
        raise V2CompressionBreakoutError(f"{name} must be finite, got {value!r}")
    return v


def _validate_nonnegative_finite(value: Any, name: str) -> float:
    v = _validate_finite_numeric(value, name)
    if v < 0.0:
        raise V2CompressionBreakoutError(f"{name} must be >= 0.0, got {v!r}")
    return v


def _validate_positive_finite(value: Any, name: str) -> float:
    v = _validate_finite_numeric(value, name)
    if not (v > 0.0):
        raise V2CompressionBreakoutError(f"{name} must be > 0, got {v!r}")
    return v


def _validate_utc_whole_minute(value: Any, name: str) -> datetime:
    if type(value) is not datetime:
        raise V2CompressionBreakoutError(f"{name} must be a datetime, got {type(value).__name__}")
    if value.tzinfo is None or value.utcoffset() is None:
        raise V2CompressionBreakoutError(f"{name} must be timezone-aware")
    if value.utcoffset() != timedelta(0):
        raise V2CompressionBreakoutError(f"{name} must be UTC (offset 0), got {value.utcoffset()}")
    if value.second != 0 or value.microsecond != 0:
        raise V2CompressionBreakoutError(f"{name} must be a whole minute (no seconds/microseconds)")
    return value


def _validate_15m_bucket_start(value: Any, name: str) -> datetime:
    """A legal 15m bucket START on the canonical V2 grid -- reuses
    `alignment.selected_bucket()`'s own round-trip technique (never a
    second, competing grid convention): `value` is a legal 15m bucket
    start iff selecting the 15m bucket for `T = value + 15m` round-trips
    back to `value` exactly."""
    v = _validate_utc_whole_minute(value, name)
    try:
        canonical = selected_bucket("15m", v + _FIFTEEN_MIN)
    except V2AlignmentError as exc:
        raise V2CompressionBreakoutError(f"{name} is not a legal 15m bucket start: {exc}") from exc
    if canonical != v:
        raise V2CompressionBreakoutError(f"{name} is not aligned to the canonical 15m bucket grid")
    return v


def _validate_row_container(rows: Any, name: str) -> Any:
    if rows is None or isinstance(rows, (str, bytes, bytearray)):
        raise V2CompressionBreakoutError(
            f"{name} must be a Sequence of Mapping rows (not None/str/bytes), got "
            f"{type(rows).__name__}")
    try:
        iter(rows)
    except TypeError as exc:
        raise V2CompressionBreakoutError(
            f"{name} must be an iterable Sequence of Mapping rows, got "
            f"{type(rows).__name__}: {exc}") from exc
    return rows


def _require_fields(row: Any, required_fields: "tuple[str, ...]", label: str) -> None:
    if not isinstance(row, _AbcMapping):
        raise V2CompressionBreakoutError(
            f"{label} must be a Mapping, got {type(row).__name__}: {row!r}")
    missing = [f for f in required_fields if f not in row]
    if missing:
        raise V2CompressionBreakoutError(f"{label} is missing required field(s) {missing!r}")


# ============================================================================
# input value object -- bare container, no self-validation (see module
# docstring's "V2CompressionBreakoutInputs is a bare container" section).
# ============================================================================
@dataclass(frozen=True)
class V2CompressionBreakoutInputs:
    """Everything `detect_compression_breakout()` needs for ONE
    `context.T`: the already-computed `V2ContextSnapshot`, the exact
    `COMPRESSION_LOOKBACK=16`-bucket 15m consensus window
    (`consensus_15m_rows`, dual-purpose -- also feeds `RANGE_PROXY_pct`'s
    final 14 rows), the matching 15m compression-percentile window
    (`percentile_15m_rows`), the same 16-bucket 15m reference-feature
    window (`reference_15m_rows`), the raw 1m klines covering that whole
    lookback plus one extra 15m bucket (`reference_1m_rows`, half-open
    `[B15-15*15m, B15+15m)`), the two closed 5m reference-feature buckets
    needed for the fresh-cross check (`reference_5m_rows`), the single
    current-B5 5m consensus row (`consensus_5m_rows`), and the single
    `exchange_instruments` row for `protection_buffer()`'s `tick_size`
    (`instrument`, `None` if absent). No DB handle, no pool, no reader is
    retained here -- rows are plain, already-detached `Mapping`s (as
    `storage/v2_setup_readers.py`'s readers already return them).
    `detect_compression_breakout()` never mutates any row it reads from
    this object."""
    context: V2ContextSnapshot
    consensus_15m_rows: "tuple[Mapping, ...]"
    percentile_15m_rows: "tuple[Mapping, ...]"
    reference_15m_rows: "tuple[Mapping, ...]"
    reference_1m_rows: "tuple[Mapping, ...]"
    reference_5m_rows: "tuple[Mapping, ...]"
    consensus_5m_rows: "tuple[Mapping, ...]"
    instrument: Optional[Mapping]


# ============================================================================
# result value object -- public Stage 5 API, self-validates on ANY direct
# construction (mirrors V2TrendPullbackCandidate's established
# frozen-dataclass __post_init__ pattern).
# ============================================================================
@dataclass(frozen=True)
class V2CompressionBreakoutCandidate:
    """One deterministic `COMPRESSION_BREAKOUT` qualification at `T`
    (§7.2). A QUALIFICATION only -- see module docstring's Stage 5/6
    boundary section for everything this is deliberately NOT: not an
    episode, not an `EARLY_SIGNAL`, not confirmed, not scored, not
    persisted.

    `structural_anchor` (the `bucket_ts` `episode_logical_key`, §12, will
    later use) is intentionally exposed only as a read-only property
    derived from `compression_start_bucket` -- never a second,
    independently-settable field that could silently disagree with it.

    `setup_strength` (§8.2, LOAD-BEARING) is `mean(compression_score)`
    over the ENTIRE SELECTED MAXIMAL COMPRESSION RUN
    (`compression_start_bucket` through `compression_end_bucket`
    inclusive) -- explicitly NOT the current-B15 score, NOT
    `compression_end_bucket`-only score, NOT a mean over the whole
    16-bucket lookback, and NOT a mean from `compression_end_bucket` to
    now. `data_confidence` (§9) is `min(price_structure, taker_flow)`
    family confidence at the SAME fresh 5m trigger bucket, `/100.0` --
    never `consensus_confidence`/`data_confidence_overall`, and never a
    different bucket for either family. Both carried BY VALUE, never
    recomputed downstream.

    **`decision_tick_size` (V2-H2c, tech-lead review 4990482334, finding
    5).** `docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §12.5a freezes that
    every Stage 5 candidate depending on `tick_size` MUST carry the
    actual validated decision-time `tick_size` BY VALUE. Stage 5 owns
    and exposes it; Stage 6 will later freeze `candidate.
    decision_tick_size` into the episode's OWN `creation_identity_
    tick_size` (§12.5a) once an `EARLY_SIGNAL` is actually created --
    never re-reading instrument metadata for that identity."""
    T: datetime
    direction: str
    bucket_5m: datetime
    bucket_15m: datetime
    previous_5m_close: float
    breakout_close: float
    compression_start_bucket: datetime
    compression_end_bucket: datetime
    compression_length: int
    range_high: float
    range_low: float
    range_proxy_pct: float
    protection_buffer: float
    decision_tick_size: float
    entry_zone_lower: float
    entry_zone_upper: float
    invalidation_price: float
    price_direction_agreement: float
    taker_delta_notional_usd_sum: float
    setup_strength: float
    data_confidence: float

    def __post_init__(self) -> None:
        if self.direction not in DIRECTIONS:
            raise V2CompressionBreakoutError(
                f"direction must be one of {DIRECTIONS}, got {self.direction!r}")

        t = _validate_utc_whole_minute(self.T, "T")
        try:
            b5 = selected_bucket("5m", t)
        except V2AlignmentError as exc:
            raise V2CompressionBreakoutError(
                f"T={t.isoformat()} is not a legal V2 5m decision boundary: {exc}") from exc
        b15 = selected_bucket("15m", t)
        if self.bucket_5m != b5:
            raise V2CompressionBreakoutError(
                f"bucket_5m does not match selected_bucket('5m', T) -- expected {b5!r}, "
                f"got {self.bucket_5m!r}")
        if self.bucket_15m != b15:
            raise V2CompressionBreakoutError(
                f"bucket_15m does not match selected_bucket('15m', T) -- expected {b15!r}, "
                f"got {self.bucket_15m!r}")

        start = _validate_15m_bucket_start(self.compression_start_bucket, "compression_start_bucket")
        end = _validate_15m_bucket_start(self.compression_end_bucket, "compression_end_bucket")
        if start > end:
            raise V2CompressionBreakoutError(
                "compression_start_bucket must be <= compression_end_bucket")
        lookback_start = b15 - (COMPRESSION_LOOKBACK - 1) * _FIFTEEN_MIN
        if not (lookback_start <= start <= b15):
            raise V2CompressionBreakoutError(
                f"compression_start_bucket {start!r} is outside the {COMPRESSION_LOOKBACK}-bucket "
                f"lookback [{lookback_start!r}, {b15!r}]")
        if not (lookback_start <= end <= b15):
            raise V2CompressionBreakoutError(
                f"compression_end_bucket {end!r} is outside the {COMPRESSION_LOOKBACK}-bucket "
                f"lookback [{lookback_start!r}, {b15!r}]")

        if isinstance(self.compression_length, bool) or not isinstance(self.compression_length, int):
            raise V2CompressionBreakoutError(
                f"compression_length must be an int, got {type(self.compression_length).__name__}")
        if self.compression_length < COMPRESSION_MIN_DURATION:
            raise V2CompressionBreakoutError(
                f"compression_length must be >= {COMPRESSION_MIN_DURATION}, got "
                f"{self.compression_length!r}")
        expected_length = int((end - start) / _FIFTEEN_MIN) + 1
        if self.compression_length != expected_length:
            raise V2CompressionBreakoutError(
                f"compression_length ({self.compression_length!r}) does not match the inclusive "
                f"15m grid distance between compression_start_bucket and compression_end_bucket "
                f"({expected_length!r})")

        range_high = _validate_positive_finite(self.range_high, "range_high")
        range_low = _validate_positive_finite(self.range_low, "range_low")
        if not (range_low <= range_high):
            raise V2CompressionBreakoutError(
                f"range_low ({range_low!r}) must be <= range_high ({range_high!r})")

        previous_close = _validate_positive_finite(self.previous_5m_close, "previous_5m_close")
        breakout_close = _validate_positive_finite(self.breakout_close, "breakout_close")

        buf = _validate_positive_finite(self.protection_buffer, "protection_buffer")
        decision_tick = _validate_positive_finite(self.decision_tick_size, "decision_tick_size")
        if buf < MIN_TICK_BUFFER_TICKS * decision_tick:
            raise V2CompressionBreakoutError(
                f"protection_buffer ({buf!r}) is inconsistent with decision_tick_size "
                f"({decision_tick!r}) -- protection_buffer() can never be smaller than "
                f"MIN_TICK_BUFFER_TICKS * decision_tick_size "
                f"({MIN_TICK_BUFFER_TICKS * decision_tick!r})")
        _validate_nonnegative_finite(self.range_proxy_pct, "range_proxy_pct")

        agreement = _validate_finite_numeric(
            self.price_direction_agreement, "price_direction_agreement")
        if not (0.0 <= agreement <= 1.0):
            raise V2CompressionBreakoutError(
                f"price_direction_agreement must be within [0.0, 1.0], got {agreement!r}")
        if agreement < BREAKOUT_MIN_AGREEMENT:
            raise V2CompressionBreakoutError(
                f"price_direction_agreement ({agreement!r}) must be >= {BREAKOUT_MIN_AGREEMENT!r}")

        taker = _validate_finite_numeric(
            self.taker_delta_notional_usd_sum, "taker_delta_notional_usd_sum")

        entry_lower = _validate_positive_finite(self.entry_zone_lower, "entry_zone_lower")
        entry_upper = _validate_positive_finite(self.entry_zone_upper, "entry_zone_upper")
        if not (entry_lower <= entry_upper):
            raise V2CompressionBreakoutError(
                f"entry_zone_lower ({entry_lower!r}) must be <= entry_zone_upper "
                f"({entry_upper!r})")

        invalidation = _validate_positive_finite(self.invalidation_price, "invalidation_price")

        if self.direction == LONG:
            if not (previous_close <= range_high and breakout_close > range_high):
                raise V2CompressionBreakoutError(
                    "LONG fresh-cross invariant violated: require previous_5m_close <= "
                    f"range_high ({range_high!r}) and breakout_close > range_high, got "
                    f"previous_5m_close={previous_close!r}, breakout_close={breakout_close!r}")
            if not (taker > 0):
                raise V2CompressionBreakoutError(
                    f"LONG requires taker_delta_notional_usd_sum > 0, got {taker!r}")
            if entry_lower != range_high or entry_upper != range_high + buf:
                raise V2CompressionBreakoutError(
                    "LONG entry zone is inconsistent with range_high/protection_buffer -- "
                    f"expected [{range_high!r}, {range_high + buf!r}], got "
                    f"[{entry_lower!r}, {entry_upper!r}]")
            if invalidation != range_low - buf:
                raise V2CompressionBreakoutError(
                    "LONG invalidation_price is inconsistent with range_low/protection_buffer "
                    f"-- expected {range_low - buf!r}, got {invalidation!r}")
            if not (invalidation < range_low):
                raise V2CompressionBreakoutError(
                    f"LONG invalidation_price must be < range_low ({range_low!r}), got "
                    f"{invalidation!r}")
        else:
            if not (previous_close >= range_low and breakout_close < range_low):
                raise V2CompressionBreakoutError(
                    "SHORT fresh-cross invariant violated: require previous_5m_close >= "
                    f"range_low ({range_low!r}) and breakout_close < range_low, got "
                    f"previous_5m_close={previous_close!r}, breakout_close={breakout_close!r}")
            if not (taker < 0):
                raise V2CompressionBreakoutError(
                    f"SHORT requires taker_delta_notional_usd_sum < 0, got {taker!r}")
            if entry_upper != range_low or entry_lower != range_low - buf:
                raise V2CompressionBreakoutError(
                    "SHORT entry zone is inconsistent with range_low/protection_buffer -- "
                    f"expected [{range_low - buf!r}, {range_low!r}], got "
                    f"[{entry_lower!r}, {entry_upper!r}]")
            if invalidation != range_high + buf:
                raise V2CompressionBreakoutError(
                    "SHORT invalidation_price is inconsistent with range_high/protection_buffer "
                    f"-- expected {range_high + buf!r}, got {invalidation!r}")
            if not (invalidation > range_high):
                raise V2CompressionBreakoutError(
                    f"SHORT invalidation_price must be > range_high ({range_high!r}), got "
                    f"{invalidation!r}")

        # §8.2/§9 setup_strength/data_confidence -- canonical creation-time
        # scoring/quality facts. setup_strength's exact full-selected-run
        # mean-compression-score formula is a function of the SELECTED
        # RUN's own per-bucket compression_score values, which this
        # candidate deliberately does not carry as a separate array (no
        # duplicate representation of Stage 5 raw evidence beyond what §8
        # requires) -- so, unlike TREND_PULLBACK's setup_strength (fully
        # reconstructible from this candidate's own retracement_pct/
        # range_proxy_pct fields), direct construction here is checked only
        # to its exact [0,1] domain, not cross-checked against a formula.
        setup_strength = _validate_finite_numeric(self.setup_strength, "setup_strength")
        if not (0.0 <= setup_strength <= 1.0):
            raise V2CompressionBreakoutError(
                f"setup_strength must be within [0.0, 1.0], got {setup_strength!r}")

        data_confidence = _validate_finite_numeric(self.data_confidence, "data_confidence")
        if not (0.0 <= data_confidence <= 1.0):
            raise V2CompressionBreakoutError(
                f"data_confidence must be within [0.0, 1.0], got {data_confidence!r}")

    @property
    def structural_anchor(self) -> datetime:
        """§12's `episode_logical_key` structural anchor for
        `COMPRESSION_BREAKOUT` -- always exactly `compression_start_bucket`,
        never an independently stored/settable value."""
        return self.compression_start_bucket


# ============================================================================
# the pure detector
# ============================================================================
_PERCENTILE_IDENTITY_FIELDS = (
    "scope", "exchange", "symbol", "market_type", "metric", "timeframe",
    "percentile_window", "calculation_version", "feature_schema_version", "bucket_ts",
)
_CONSENSUS_15M_IDENTITY_FIELDS = (
    "symbol", "market_type", "timeframe", "calculation_version", "feature_schema_version",
    "bucket_ts",
)
_REFERENCE_IDENTITY_FIELDS = (
    "exchange", "symbol", "market_type", "timeframe", "calculation_version",
    "feature_schema_version", "bucket_ts",
)
_REFERENCE_GATE_FIELDS = ("is_usable", "has_gap", "bars_present", "bars_expected", "close_price")
_REFERENCE_REQUIRED_FIELDS = _REFERENCE_IDENTITY_FIELDS + _REFERENCE_GATE_FIELDS
_RAW_BAR_REQUIRED_FIELDS = ("exchange", "symbol", "ts", "high", "low")
_TRIGGER_5M_IDENTITY_FIELDS = (
    "symbol", "market_type", "timeframe", "bucket_ts", "calculation_version",
    "feature_schema_version",
)
_TRIGGER_5M_VALUE_FIELDS = (
    "min_coverage_ratio", "consensus_confidence", "price_direction_agreement",
    "taker_delta_notional_usd_sum",
)
_TRIGGER_5M_REQUIRED_FIELDS = _TRIGGER_5M_IDENTITY_FIELDS + _TRIGGER_5M_VALUE_FIELDS
_INSTRUMENT_REQUIRED_FIELDS = ("exchange", "symbol", "market_type", "tick_size")


def _validate_percentile_row_identity(
    row: Any, *, context: V2ContextSnapshot, expected_set: frozenset,
) -> datetime:
    """§10: full PRESENT identity re-check for one compression percentile
    row, BEFORE it is ever grouped into a per-bucket `V2TimeframeInputs`
    for `compression_score()` -- `find_consensus_percentile()` alone does
    not check `symbol`/`market_type`/`metric`/`percentile_window`/
    `calculation_version`/`feature_schema_version` (see module
    docstring). No cross-window/exchange-scoped fallback of any kind."""
    _require_fields(row, _PERCENTILE_IDENTITY_FIELDS, "compression percentile row")
    if row["scope"] != "consensus":
        raise V2CompressionBreakoutError(
            f"compression percentile row scope must be 'consensus', got {row['scope']!r}")
    if row["exchange"] != "":
        raise V2CompressionBreakoutError(
            f"compression percentile row exchange must be '' for consensus scope, got "
            f"{row['exchange']!r}")
    if row["symbol"] != context.symbol:
        raise V2CompressionBreakoutError(
            f"compression percentile row symbol must be {context.symbol!r}, got "
            f"{row['symbol']!r}")
    if row["market_type"] != context.market_type:
        raise V2CompressionBreakoutError(
            f"compression percentile row market_type must be {context.market_type!r}, got "
            f"{row['market_type']!r}")
    if row["metric"] != _COMPRESSION_METRIC:
        raise V2CompressionBreakoutError(
            f"compression percentile row metric must be {_COMPRESSION_METRIC!r}, got "
            f"{row['metric']!r}")
    if row["timeframe"] != "15m":
        raise V2CompressionBreakoutError(
            f"compression percentile row timeframe must be '15m', got {row['timeframe']!r}")
    if row["percentile_window"] != COMPRESSION_PERCENTILE_WINDOW:
        raise V2CompressionBreakoutError(
            f"compression percentile row percentile_window must be "
            f"{COMPRESSION_PERCENTILE_WINDOW!r}, got {row['percentile_window']!r}")
    if row["calculation_version"] != context.calculation_version:
        raise V2CompressionBreakoutError(
            f"compression percentile row calculation_version must be "
            f"{context.calculation_version!r}, got {row['calculation_version']!r}")
    if row["feature_schema_version"] != context.feature_schema_version:
        raise V2CompressionBreakoutError(
            f"compression percentile row feature_schema_version must be "
            f"{context.feature_schema_version!r}, got {row['feature_schema_version']!r}")

    bucket_ts = _validate_utc_whole_minute(row["bucket_ts"], "compression percentile row bucket_ts")
    if bucket_ts not in expected_set:
        raise V2CompressionBreakoutError(
            f"compression percentile row bucket_ts {bucket_ts.isoformat()} is outside the "
            f"expected {COMPRESSION_LOOKBACK}-bucket 15m lookback")

    sample_window_end = row.get("sample_window_end")
    if sample_window_end is not None:
        swe = _validate_utc_whole_minute(
            sample_window_end, "compression percentile row sample_window_end")
        if not (swe < bucket_ts):
            raise V2CompressionBreakoutError(
                "compression percentile row sample_window_end must be strictly before "
                "bucket_ts (no-lookahead defense) -- equality is not allowed")
    return bucket_ts


def _validate_consensus_15m_row_identity(
    row: Any, *, context: V2ContextSnapshot, expected_set: frozenset,
) -> datetime:
    _require_fields(row, _CONSENSUS_15M_IDENTITY_FIELDS, "15m consensus row")
    if row["symbol"] != context.symbol:
        raise V2CompressionBreakoutError(
            f"15m consensus row symbol must be {context.symbol!r}, got {row['symbol']!r}")
    if row["market_type"] != context.market_type:
        raise V2CompressionBreakoutError(
            f"15m consensus row market_type must be {context.market_type!r}, got "
            f"{row['market_type']!r}")
    if row["timeframe"] != "15m":
        raise V2CompressionBreakoutError(
            f"15m consensus row timeframe must be '15m', got {row['timeframe']!r}")
    if row["calculation_version"] != context.calculation_version:
        raise V2CompressionBreakoutError(
            f"15m consensus row calculation_version must be {context.calculation_version!r}, "
            f"got {row['calculation_version']!r}")
    if row["feature_schema_version"] != context.feature_schema_version:
        raise V2CompressionBreakoutError(
            f"15m consensus row feature_schema_version must be "
            f"{context.feature_schema_version!r}, got {row['feature_schema_version']!r}")
    bucket_ts = _validate_utc_whole_minute(row["bucket_ts"], "15m consensus row bucket_ts")
    if bucket_ts not in expected_set:
        raise V2CompressionBreakoutError(
            f"15m consensus row bucket_ts {bucket_ts.isoformat()} is outside the expected "
            f"{COMPRESSION_LOOKBACK}-bucket 15m lookback")
    return bucket_ts


def _validate_quality_fields(row: Mapping, *, family: str) -> "Optional[tuple[float, float]]":
    """§6.3a's per-family metric-scoped quality gate, applied at whichever
    bucket the caller is currently evaluating (a 15m compression-lookback
    bucket, or the 5m trigger bucket) for exactly `family` -- sourced from
    the row's own `coverage_by_metric`/`data_confidence_by_metric` maps,
    never the global `min_coverage_ratio`/`consensus_confidence` rollup a
    family this decision does not consume could otherwise drag down. A
    malformed PRESENT per-family map raises `V2CompressionBreakoutError`
    (chained from `V2FamilyQualityError`), never silently downgraded to
    ordinary unavailability."""
    try:
        quality = family_quality(row, family=family)
    except V2FamilyQualityError as exc:
        raise V2CompressionBreakoutError(
            f"malformed {family} family quality: {exc}") from exc
    if quality.coverage_ratio is None or quality.confidence is None:
        return None
    return quality.coverage_ratio, quality.confidence


def _validate_reference_row(
    row: Any, *, context: V2ContextSnapshot, timeframe: str, full_bar_count: int,
    expected_set: frozenset,
) -> "tuple[datetime, Optional[float]]":
    """Validate one PRESENT reference row's exact identity and apply
    §11's exact reference-vector usability gate, reused unchanged.
    Returns `(bucket_ts, close_price_or_None)` -- `None` for a bucket
    that legitimately fails the usability gate, while every PRESENT
    numeric/count/bool field is still validated for corruption regardless
    of whether the gate would fail anyway (corruption precedence)."""
    _require_fields(row, _REFERENCE_REQUIRED_FIELDS, f"reference {timeframe} row")

    if row["exchange"] != V2_REFERENCE_EXCHANGE:
        raise V2CompressionBreakoutError(
            f"reference {timeframe} row exchange must be {V2_REFERENCE_EXCHANGE!r}, got "
            f"{row['exchange']!r}")
    if row["symbol"] != context.symbol:
        raise V2CompressionBreakoutError(
            f"reference {timeframe} row symbol must be {context.symbol!r}, got "
            f"{row['symbol']!r}")
    if row["market_type"] != context.market_type:
        raise V2CompressionBreakoutError(
            f"reference {timeframe} row market_type must be {context.market_type!r}, got "
            f"{row['market_type']!r}")
    if row["timeframe"] != timeframe:
        raise V2CompressionBreakoutError(
            f"reference row timeframe must be {timeframe!r}, got {row['timeframe']!r}")
    if row["calculation_version"] != context.calculation_version:
        raise V2CompressionBreakoutError(
            f"reference {timeframe} row calculation_version must be "
            f"{context.calculation_version!r}, got {row['calculation_version']!r}")
    if row["feature_schema_version"] != context.feature_schema_version:
        raise V2CompressionBreakoutError(
            f"reference {timeframe} row feature_schema_version must be "
            f"{context.feature_schema_version!r}, got {row['feature_schema_version']!r}")

    bucket_ts = _validate_utc_whole_minute(row["bucket_ts"], f"reference {timeframe} row bucket_ts")
    if bucket_ts not in expected_set:
        raise V2CompressionBreakoutError(
            f"reference {timeframe} row bucket_ts {bucket_ts.isoformat()} is outside the "
            f"expected lookback")

    is_usable = row["is_usable"]
    if not isinstance(is_usable, bool):
        raise V2CompressionBreakoutError(
            f"reference {timeframe} row is_usable must be a bool, got "
            f"{type(is_usable).__name__}")
    has_gap = row["has_gap"]
    if not isinstance(has_gap, bool):
        raise V2CompressionBreakoutError(
            f"reference {timeframe} row has_gap must be a bool, got {type(has_gap).__name__}")

    bars_present = row["bars_present"]
    bars_expected = row["bars_expected"]
    for name, value in (("bars_present", bars_present), ("bars_expected", bars_expected)):
        if isinstance(value, bool) or not isinstance(value, int):
            raise V2CompressionBreakoutError(
                f"reference {timeframe} row {name} must be an int, got {type(value).__name__}")
    if bars_expected != full_bar_count:
        raise V2CompressionBreakoutError(
            f"reference {timeframe} row bars_expected must be exactly {full_bar_count}, got "
            f"{bars_expected!r}")
    if bars_present < 0:
        raise V2CompressionBreakoutError(
            f"reference {timeframe} row bars_present must be >= 0, got {bars_present!r}")
    if bars_present > bars_expected:
        raise V2CompressionBreakoutError(
            f"reference {timeframe} row bars_present ({bars_present!r}) must not exceed "
            f"bars_expected ({bars_expected!r})")

    close_price = row["close_price"]
    if close_price is not None:
        close_price = _validate_positive_finite(close_price, f"reference {timeframe} row close_price")

    gate_passes = (
        is_usable is True and has_gap is False
        and bars_present == bars_expected and close_price is not None
    )
    return bucket_ts, (close_price if gate_passes else None)


def _validate_raw_1m_row_identity(
    row: Any, *, context: V2ContextSnapshot, window_start: datetime, window_end: datetime,
) -> datetime:
    """§49: validate ONLY the fields a raw `klines_1m` row physically
    carries (`exchange`/`symbol`/`ts` -- no `market_type` column exists
    on this table). High/low PRICE validation and per-bucket minute-grid/
    gap/duplicate checks remain `derive_reference_extrema()`'s own job,
    never duplicated here."""
    _require_fields(row, _RAW_BAR_REQUIRED_FIELDS, "raw reference 1m row")
    if row["exchange"] != V2_REFERENCE_EXCHANGE:
        raise V2CompressionBreakoutError(
            f"raw reference 1m row exchange must be {V2_REFERENCE_EXCHANGE!r}, got "
            f"{row['exchange']!r}")
    if row["symbol"] != context.symbol:
        raise V2CompressionBreakoutError(
            f"raw reference 1m row symbol must be {context.symbol!r}, got {row['symbol']!r}")
    ts = _validate_utc_whole_minute(row["ts"], "raw reference 1m row ts")
    if not (window_start <= ts < window_end):
        raise V2CompressionBreakoutError(
            f"raw reference 1m row ts {ts.isoformat()} is outside the requested half-open "
            f"interval [{window_start.isoformat()}, {window_end.isoformat()})")
    return ts


def _validate_trigger_5m_row_identity(row: Any, *, context: V2ContextSnapshot) -> datetime:
    _require_fields(row, _TRIGGER_5M_REQUIRED_FIELDS, "current 5m consensus row")
    if row["symbol"] != context.symbol:
        raise V2CompressionBreakoutError(
            f"current 5m consensus row symbol must be {context.symbol!r}, got {row['symbol']!r}")
    if row["market_type"] != context.market_type:
        raise V2CompressionBreakoutError(
            f"current 5m consensus row market_type must be {context.market_type!r}, got "
            f"{row['market_type']!r}")
    if row["timeframe"] != "5m":
        raise V2CompressionBreakoutError(
            f"current 5m consensus row timeframe must be '5m', got {row['timeframe']!r}")
    if row["calculation_version"] != context.calculation_version:
        raise V2CompressionBreakoutError(
            f"current 5m consensus row calculation_version must be "
            f"{context.calculation_version!r}, got {row['calculation_version']!r}")
    if row["feature_schema_version"] != context.feature_schema_version:
        raise V2CompressionBreakoutError(
            f"current 5m consensus row feature_schema_version must be "
            f"{context.feature_schema_version!r}, got {row['feature_schema_version']!r}")
    return _validate_utc_whole_minute(row["bucket_ts"], "current 5m consensus row bucket_ts")


def _select_compression_run(
    grid: "tuple[datetime, ...]", compressed_flags: "Mapping[datetime, bool]",
) -> "Optional[tuple[datetime, datetime, int]]":
    """§7.2's deterministic maximal-run partition + selection. `grid` is
    chronological (oldest first). Returns `(run_start, run_end,
    run_length)` for the selected run, or `None` if zero runs meet
    `COMPRESSION_MIN_DURATION`. Precedence: (1) most recent `run_end`;
    (2) if ambiguous, longest; (3) if still ambiguous, latest `run_end`
    again -- in an ordinary maximal-run partition no two runs can share
    an end bucket, so (1) alone already uniquely determines the winner;
    (2)/(3) exist purely for deterministic robustness."""
    runs: "list[tuple[datetime, datetime, int]]" = []
    run_start: Optional[datetime] = None
    run_length = 0
    prev_ts: Optional[datetime] = None
    for ts in grid:
        if compressed_flags.get(ts, False):
            if run_start is None:
                run_start = ts
                run_length = 1
            else:
                run_length += 1
        else:
            if run_start is not None:
                runs.append((run_start, prev_ts, run_length))
                run_start = None
                run_length = 0
        prev_ts = ts
    if run_start is not None:
        runs.append((run_start, prev_ts, run_length))

    qualifying = [r for r in runs if r[2] >= COMPRESSION_MIN_DURATION]
    if not qualifying:
        return None
    return max(qualifying, key=lambda r: (r[1], r[2], r[1]))


def detect_compression_breakout(
    inputs: V2CompressionBreakoutInputs,
) -> Optional[V2CompressionBreakoutCandidate]:
    """Deterministically qualify (or not) `COMPRESSION_BREAKOUT` at
    `inputs.context.T` (see module docstring for the complete formula/
    precondition set and the exhaustive Stage 5/6 boundary this
    respects). Pure, synchronous; the same `inputs` always yields the
    same result.

    Evaluation order (load-bearing, §7.2/§21 corruption precedence):
    (1) top-level input/context validation; (2) derive B5/B15; (3)
    validate the exact 16-bucket 15m consensus + percentile windows'
    identity in full (so malformed PRESENT data anywhere in either family
    always raises, independent of the eventual run-selection outcome);
    (4) per-bucket §6.2/§6.3 quality gate, then `compression_score()`
    ONLY for buckets that already pass quality (a failed quality gate is
    itself a "preceding deterministic gate" that makes that bucket's
    score irrelevant, §21); (5) select the qualifying compression run --
    zero qualifying runs is a legitimate non-qualification, `None`; (6)
    derive the selected run's structural range; (7) current-B15 quality +
    `RANGE_PROXY_pct` (reusing the final 14 rows of the already-validated
    16-bucket window) + the B15 reference close; (8) the two closed 5m
    reference closes; (9)-(10) the fresh-crossing direction, or `None`;
    (11)-(13) the 5m trigger's quality/agreement/taker-flow gates,
    corruption-validated together before any one of the three can
    short-circuit the others; (14) `directional_context_gate`; (15) the
    instrument/tick lookup; (16) `protection_buffer`; (17) construct the
    candidate.

    Returns `None` for every legitimate non-qualification (see module
    docstring for the full inventory). Raises `V2CompressionBreakoutError`
    for malformed PRESENT input of any kind."""
    if not isinstance(inputs, V2CompressionBreakoutInputs):
        raise V2CompressionBreakoutError(
            f"inputs must be a V2CompressionBreakoutInputs, got {type(inputs).__name__}")
    context = inputs.context
    if not isinstance(context, V2ContextSnapshot):
        raise V2CompressionBreakoutError(
            f"inputs.context must be a V2ContextSnapshot, got {type(context).__name__}")

    # ---- §1/§7.2 decision clock: EVERY legal 5m boundary, no 15m-formation
    # restriction (unlike TREND_PULLBACK) -----------------------------------
    T = context.T
    B5 = selected_bucket("5m", T)
    B15 = selected_bucket("15m", T)

    # ---- §7.2/§15/§16 exact 16-bucket 15m compression-evidence grid -------
    lookback_grid = tuple(
        B15 - (COMPRESSION_LOOKBACK - 1 - i) * _FIFTEEN_MIN for i in range(COMPRESSION_LOOKBACK))
    lookback_set = frozenset(lookback_grid)

    consensus_rows = _validate_row_container(inputs.consensus_15m_rows, "consensus_15m_rows")
    consensus_by_bucket: "dict[datetime, Mapping]" = {}
    for row in consensus_rows:
        bucket_ts = _validate_consensus_15m_row_identity(
            row, context=context, expected_set=lookback_set)
        if bucket_ts in consensus_by_bucket:
            raise V2CompressionBreakoutError(
                f"duplicate 15m consensus row for bucket_ts {bucket_ts.isoformat()}")
        consensus_by_bucket[bucket_ts] = row

    percentile_rows = _validate_row_container(inputs.percentile_15m_rows, "percentile_15m_rows")
    percentile_by_bucket: "dict[datetime, Mapping]" = {}
    for row in percentile_rows:
        bucket_ts = _validate_percentile_row_identity(
            row, context=context, expected_set=lookback_set)
        if bucket_ts in percentile_by_bucket:
            raise V2CompressionBreakoutError(
                f"duplicate compression percentile row for bucket_ts {bucket_ts.isoformat()}")
        percentile_by_bucket[bucket_ts] = row

    # ---- per-bucket §6.3a price_structure-family quality gate +
    # compression_score() -- `score_by_bucket` retains each bucket's own
    # already-computed canonical compression_score (§8.2: the later
    # full-selected-run setup_strength mean reuses these exact values, no
    # second DB read, no silent use of an unrelated latest bucket). -------
    quality_by_bucket: "dict[datetime, Optional[tuple[float, float]]]" = {}
    compressed_flags: "dict[datetime, bool]" = {}
    score_by_bucket: "dict[datetime, Optional[float]]" = {}
    for b in lookback_grid:
        row = consensus_by_bucket.get(b)
        quality = (
            _validate_quality_fields(row, family="price_structure")
            if row is not None else None)
        quality_by_bucket[b] = quality
        if quality is None:
            compressed_flags[b] = False
            score_by_bucket[b] = None
            continue
        coverage, confidence = quality
        if coverage < SETUP_MIN_COVERAGE or confidence < SETUP_MIN_CONFIDENCE:
            compressed_flags[b] = False
            score_by_bucket[b] = None
            continue

        percentile_row = percentile_by_bucket.get(b)
        percentiles_tuple = (percentile_row,) if percentile_row is not None else ()
        tf_inputs = V2TimeframeInputs(
            timeframe="15m", bucket_ts=b, bucket_end=b + _FIFTEEN_MIN,
            consensus=None, percentiles=percentiles_tuple, health={},
            reference_feature=None, reference_klines=None, reference_extrema=None)
        try:
            score = compression_score(tf_inputs, percentile_window=COMPRESSION_PERCENTILE_WINDOW)
        except V2ContextEvidenceError as exc:
            raise V2CompressionBreakoutError(
                f"compression_score failed for 15m bucket {b.isoformat()}: {exc}") from exc
        score_by_bucket[b] = score
        compressed_flags[b] = (score is not None and score >= COMPRESSION_THRESHOLD)

    # ---- §7.2 deterministic maximal-run selection --------------------------
    selected = _select_compression_run(lookback_grid, compressed_flags)
    if selected is None:
        return None
    run_start, run_end, run_length = selected
    run_buckets = tuple(run_start + i * _FIFTEEN_MIN for i in range(run_length))

    # ---- §8.2 setup_strength (LOAD-BEARING): mean(compression_score) over
    # the ENTIRE selected maximal run -- explicitly NOT current-B15 score,
    # NOT compression_end_bucket-only score, NOT mean-of-whole-lookback,
    # NOT mean-from-compression_end-to-now. Every bucket in `run_buckets`
    # was required to have `compressed_flags[b] is True` to be part of a
    # qualifying run at all, which itself required `score_by_bucket[b]` to
    # be a real float >= COMPRESSION_THRESHOLD (see the per-bucket loop
    # above) -- so this reuses each bucket's already-computed canonical
    # score from already-read data, never a second DB read.
    run_scores = [score_by_bucket[b] for b in run_buckets]
    if any(s is None for s in run_scores):
        raise V2CompressionBreakoutError(
            "selected compression run contains a bucket with no compression_score -- "
            "impossible for a qualifying run (compressed_flags requires a real score)")
    setup_strength = sum(run_scores) / len(run_scores)

    # ---- §7.0a selected-run structural range -------------------------------
    reference_15m_rows = _validate_row_container(inputs.reference_15m_rows, "reference_15m_rows")
    reference_row_by_bucket_15m: "dict[datetime, Mapping]" = {}
    close_by_bucket_15m: "dict[datetime, float]" = {}
    seen_15m_bucket_ts: set = set()
    for row in reference_15m_rows:
        bucket_ts, close = _validate_reference_row(
            row, context=context, timeframe="15m", full_bar_count=_FULL_15M_BAR_COUNT,
            expected_set=lookback_set)
        if bucket_ts in seen_15m_bucket_ts:
            raise V2CompressionBreakoutError(
                f"duplicate reference 15m row for bucket_ts {bucket_ts.isoformat()}")
        seen_15m_bucket_ts.add(bucket_ts)
        reference_row_by_bucket_15m[bucket_ts] = row
        if close is not None:
            close_by_bucket_15m[bucket_ts] = close

    raw_window_start = lookback_grid[0]
    raw_window_end = B15 + _FIFTEEN_MIN
    raw_rows = _validate_row_container(inputs.reference_1m_rows, "reference_1m_rows")
    raw_by_bucket: "dict[datetime, list]" = {}
    seen_raw_ts: set = set()
    for row in raw_rows:
        ts = _validate_raw_1m_row_identity(
            row, context=context, window_start=raw_window_start, window_end=raw_window_end)
        if ts in seen_raw_ts:
            raise V2CompressionBreakoutError(f"duplicate raw reference 1m row for ts {ts.isoformat()}")
        seen_raw_ts.add(ts)
        minutes = (ts - raw_window_start) // timedelta(minutes=1)
        owning_bucket = raw_window_start + (minutes // _FULL_15M_BAR_COUNT) * _FIFTEEN_MIN
        raw_by_bucket.setdefault(owning_bucket, []).append(row)

    range_high: Optional[float] = None
    range_low: Optional[float] = None
    for b in run_buckets:
        ref_row = reference_row_by_bucket_15m.get(b)
        bars = raw_by_bucket.get(b, ())
        try:
            extrema = derive_reference_extrema(
                timeframe="15m", bucket_ts=b, reference_feature=ref_row, reference_klines=bars)
        except V2AlignedInputError as exc:
            raise V2CompressionBreakoutError(
                f"derive_reference_extrema failed for selected-run bucket {b.isoformat()}: "
                f"{exc}") from exc
        if extrema is None:
            return None  # selected-run structural range unavailable
        if range_high is None or extrema.high > range_high:
            range_high = extrema.high
        if range_low is None or extrema.low < range_low:
            range_low = extrema.low

    range_high = _validate_positive_finite(range_high, "range_high")
    range_low = _validate_positive_finite(range_low, "range_low")
    if not (range_low <= range_high):
        raise V2CompressionBreakoutError(
            f"impossible structural range: range_low ({range_low!r}) > range_high "
            f"({range_high!r})")

    # ---- §19 current-B15 quality + §7 RANGE_PROXY_pct + §11/§34 B15 close -
    current_quality = quality_by_bucket.get(B15)
    if current_quality is None:
        return None
    current_coverage, current_confidence = current_quality
    if current_coverage < SETUP_MIN_COVERAGE or current_confidence < SETUP_MIN_CONFIDENCE:
        return None

    # §7 RANGE_PROXY_pct(15m,14,B15) reuses the final RANGE_PROXY_N=14 rows
    # of the already-validated 16-bucket consensus window -- no second
    # storage read. A bucket in that exact 14-bucket grid legitimately
    # missing from `consensus_by_bucket` (present identity-validated rows
    # don't cover every expected bucket) is UNAVAILABLE input, exactly like
    # any other incomplete historical window (§21) -- but the completeness
    # check and the PRESENT-row corruption check both belong to
    # `range_proxy_pct()` itself, which already validates every PRESENT
    # row's `range_width_pct_median` BEFORE its own exact-grid-completeness
    # check runs (corruption precedence). Filtering to only the PRESENT
    # rows here (never indexing a missing bucket) avoids a bare `KeyError`
    # while still handing the shared primitive every PRESENT row to
    # validate -- a manual "any missing -> None" short-circuit here would
    # incorrectly mask a malformed PRESENT peer whenever a DIFFERENT peer
    # also happens to be missing, bypassing that corruption-precedence
    # contract. No fabricated/substituted row, no shortened or re-anchored
    # window.
    proxy_grid = lookback_grid[-RANGE_PROXY_N:]
    proxy_input_rows = tuple(
        consensus_by_bucket[b] for b in proxy_grid if b in consensus_by_bucket)
    try:
        proxy = range_proxy_pct(proxy_input_rows, timeframe="15m", bucket_ts=B15)
    except V2SetupFoundationError as exc:
        raise V2CompressionBreakoutError(f"range_proxy_pct failed: {exc}") from exc
    if proxy is None:
        return None

    b15_close = close_by_bucket_15m.get(B15)
    if b15_close is None:
        return None  # §34: no failover -- the 15m reference price is required

    # ---- §26 previous/current closed 5m Binance reference closes ----------
    b5_expected_set = frozenset({B5 - _FIVE_MIN, B5})
    reference_5m_rows = _validate_row_container(inputs.reference_5m_rows, "reference_5m_rows")
    close_by_bucket_5m: "dict[datetime, float]" = {}
    seen_5m_bucket_ts: set = set()
    for row in reference_5m_rows:
        bucket_ts, close = _validate_reference_row(
            row, context=context, timeframe="5m", full_bar_count=_FULL_5M_BAR_COUNT,
            expected_set=b5_expected_set)
        if bucket_ts in seen_5m_bucket_ts:
            raise V2CompressionBreakoutError(
                f"duplicate reference 5m row for bucket_ts {bucket_ts.isoformat()}")
        seen_5m_bucket_ts.add(bucket_ts)
        if close is not None:
            close_by_bucket_5m[bucket_ts] = close

    previous_close = close_by_bucket_5m.get(B5 - _FIVE_MIN)
    current_close = close_by_bucket_5m.get(B5)
    if previous_close is None or current_close is None:
        return None

    # ---- §27 fresh breakout direction --------------------------------------
    long_fresh = previous_close <= range_high and current_close > range_high
    short_fresh = previous_close >= range_low and current_close < range_low
    if long_fresh and short_fresh:
        raise V2CompressionBreakoutError(
            "impossible: both LONG and SHORT fresh-cross conditions are simultaneously true "
            f"(range_low={range_low!r}, range_high={range_high!r}, "
            f"previous_close={previous_close!r}, current_close={current_close!r})")
    if long_fresh:
        direction = LONG
    elif short_fresh:
        direction = SHORT
    else:
        return None  # no fresh crossing -- legitimate non-qualification

    # ---- §28/§29/§30/§31 current-B5 5m trigger row -------------------------
    trigger_rows = _validate_row_container(inputs.consensus_5m_rows, "consensus_5m_rows")
    trigger_row: Optional[Mapping] = None
    for row in trigger_rows:
        bucket_ts = _validate_trigger_5m_row_identity(row, context=context)
        if bucket_ts != B5:
            raise V2CompressionBreakoutError(
                f"unexpected current 5m consensus row bucket_ts {bucket_ts.isoformat()}, "
                f"expected exactly {B5.isoformat()}")
        if trigger_row is not None:
            raise V2CompressionBreakoutError("duplicate current 5m consensus row")
        trigger_row = row
    if trigger_row is None:
        return None  # current B5 trigger row entirely missing

    # Corruption precedence: validate every PRESENT trigger value BEFORE any
    # missingness/threshold short-circuit applies any of the sequential gates.
    # §5.2/§6.3a: the fresh 5m trigger requires price_structure AND
    # taker_flow to BOTH independently pass their own family-scoped
    # quality gate -- neither alone is sufficient, and this is the ONE
    # place in the three Stage 5 families where two families are
    # mandatory simultaneously.
    price_trigger_quality = _validate_quality_fields(trigger_row, family="price_structure")
    taker_trigger_quality = _validate_quality_fields(trigger_row, family="taker_flow")
    agreement_raw = trigger_row["price_direction_agreement"]
    agreement = (
        _validate_finite_numeric(agreement_raw, "price_direction_agreement")
        if agreement_raw is not None else None)
    if agreement is not None and not (0.0 <= agreement <= 1.0):
        raise V2CompressionBreakoutError(
            f"price_direction_agreement must be within [0.0, 1.0], got {agreement!r}")
    taker_raw = trigger_row["taker_delta_notional_usd_sum"]
    taker = (
        _validate_finite_numeric(taker_raw, "taker_delta_notional_usd_sum")
        if taker_raw is not None else None)

    if price_trigger_quality is None or taker_trigger_quality is None:
        return None
    price_trigger_coverage, price_trigger_confidence = price_trigger_quality
    taker_trigger_coverage, taker_trigger_confidence = taker_trigger_quality
    if (
        price_trigger_coverage < SETUP_MIN_COVERAGE
        or price_trigger_confidence < SETUP_MIN_CONFIDENCE
        or taker_trigger_coverage < SETUP_MIN_COVERAGE
        or taker_trigger_confidence < SETUP_MIN_CONFIDENCE
    ):
        return None

    if agreement is None:
        return None
    if agreement < BREAKOUT_MIN_AGREEMENT:
        return None

    if taker is None:
        return None
    if direction == LONG and not (taker > 0):
        return None
    if direction == SHORT and not (taker < 0):
        return None

    # ---- §9 data_confidence: min(price_structure, taker_flow) family
    # confidence at this SAME fresh 5m trigger bucket, /100.0 -- reuses the
    # two family-confidences already read above for the quality gate,
    # never a second lookup or a different bucket. ------------------------
    data_confidence = min(price_trigger_confidence, taker_trigger_confidence) / 100.0

    # ---- §7.0b canonical directional-context compatibility gate -----------
    decision = directional_context_gate(context, direction)
    if not decision.accepted:
        return None

    # ---- §11/§33 instrument identity / tick_size ---------------------------
    instrument = inputs.instrument
    if instrument is None:
        return None
    _require_fields(instrument, _INSTRUMENT_REQUIRED_FIELDS, "instrument row")
    if instrument["exchange"] != V2_REFERENCE_EXCHANGE:
        raise V2CompressionBreakoutError(
            f"instrument row exchange must be {V2_REFERENCE_EXCHANGE!r}, got "
            f"{instrument['exchange']!r}")
    if instrument["symbol"] != context.symbol:
        raise V2CompressionBreakoutError(
            f"instrument row symbol must be {context.symbol!r}, got {instrument['symbol']!r}")
    if instrument["market_type"] != context.market_type:
        raise V2CompressionBreakoutError(
            f"instrument row market_type must be {context.market_type!r}, got "
            f"{instrument['market_type']!r}")
    tick_size_raw = instrument["tick_size"]
    if tick_size_raw is None:
        return None
    tick_size = _validate_positive_finite(tick_size_raw, "instrument tick_size")

    # ---- §7/§34/§35 protection_buffer, via the shared primitive ------------
    try:
        buffer = protection_buffer(
            reference_price=b15_close, range_proxy_pct_value=proxy, tick_size=tick_size)
    except V2SetupFoundationError as exc:
        raise V2CompressionBreakoutError(f"protection_buffer failed: {exc}") from exc
    if buffer is None:
        return None  # should not normally occur once proxy is already available

    # ---- §9/§10/§36/§37 entry zone + planned structural invalidation ------
    if direction == LONG:
        entry_zone_lower = range_high
        entry_zone_upper = range_high + buffer
        invalidation_price = range_low - buffer
    else:
        entry_zone_lower = range_low - buffer
        entry_zone_upper = range_low
        invalidation_price = range_high + buffer
    if entry_zone_lower > entry_zone_upper:
        raise V2CompressionBreakoutError(
            f"entry_zone_lower ({entry_zone_lower!r}) exceeds entry_zone_upper "
            f"({entry_zone_upper!r})")

    return V2CompressionBreakoutCandidate(
        T=T,
        direction=direction,
        bucket_5m=B5,
        bucket_15m=B15,
        previous_5m_close=previous_close,
        breakout_close=current_close,
        compression_start_bucket=run_start,
        compression_end_bucket=run_end,
        compression_length=run_length,
        range_high=range_high,
        range_low=range_low,
        range_proxy_pct=proxy,
        protection_buffer=buffer,
        decision_tick_size=tick_size,
        entry_zone_lower=entry_zone_lower,
        entry_zone_upper=entry_zone_upper,
        invalidation_price=invalidation_price,
        price_direction_agreement=agreement,
        taker_delta_notional_usd_sum=taker,
        setup_strength=setup_strength,
        data_confidence=data_confidence,
    )
