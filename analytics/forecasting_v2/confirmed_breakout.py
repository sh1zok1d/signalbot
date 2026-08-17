"""
V2 `CONFIRMED_BREAKOUT` setup detector (Stage 5 — Setup Detectors, PR 4
of ~4, FINAL planned Stage 5 detector PR,
docs/FORECASTING_ROADMAP.md §I stage 5).

#39 (merged) built the shared detector foundation; #40 (merged) built
`TREND_PULLBACK`; #41 (merged) built `COMPRESSION_BREAKOUT`. This PR
implements the THIRD and final frozen setup family, per
`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §7.3:

    At the CURRENT closed 5m decision boundary `T`, does the already-
    observed 48h structural 1h resistance/support level plus the
    CURRENT closed 5m price transition qualify as a new
    `CONFIRMED_BREAKOUT` candidate, and what are its deterministic
    structural facts (`detect_confirmed_breakout()` returns a
    `V2ConfirmedBreakoutCandidate`)?

**Load-bearing Stage 5 / Stage 6 boundary (mirrors `compression_
breakout.py`, do not blur).** This module answers ONLY the
qualification question above — the moment §7.3 calls "the first breaking
close" is represented here as a `V2ConfirmedBreakoutCandidate`: a
qualification WORTHY of `EARLY_SIGNAL` creation, never the `EARLY_SIGNAL`
itself. It does NOT: create/persist an `EARLY_SIGNAL` event, `episode_id`,
or `event_id`; construct `episode_logical_key` (§12, Stage 6's job); decide
whether another already-active episode already owns this exact structural
anchor; evaluate `CONFIRMED`/`WEAKENING`/`INVALIDATED`/`EXPIRED`/
`COMPLETED` transitions, the direction-aware false-break rule, or the
boundary-equality HOLD convention (§7.3); count
`CONFIRMED_BREAKOUT_CONFIRMATION_MAX_AGE_5M_BUCKETS` against episode age,
or a candidate's `EXPECTED_HORIZON` — both exposed below only as frozen
family metadata, never evaluated by anything in this module; or apply
§7.4 family precedence/dedup against `COMPRESSION_BREAKOUT`/
`TREND_PULLBACK` — this module never calls `detect_compression_breakout()`
or `detect_trend_pullback()`, and never suppresses anything. Every one of
those is Stage 6 (Episode State Machine) or later.

**`CONFIRMED_BREAKOUT` is NOT `COMPRESSION_BREAKOUT` without compression —
its EARLY_SIGNAL qualification is intentionally lighter (load-bearing,
§7.3, do not cargo-cult #41).** There is no preceding-compression
precondition, no taker-flow confirmation requirement, and no invented
`price_direction_agreement` hard gate at this stage — §7.3 freezes exactly
two EARLY_SIGNAL requirements: (1) the first closed reference-exchange 5m
bucket whose close crosses beyond the structural level, and (2)
`directional_context_gate(candidate_direction, context) == ACCEPT`.
`CONFIRMED_BREAKOUT` has NO taker-flow requirement under the frozen
contract, at EITHER `EARLY_SIGNAL` or the later `EARLY_SIGNAL ->
CONFIRMED` evaluation (§7.3: "no taker-flow confirmation requirement...
compression's volume-confirmation gate does not carry over"). This Stage
5 detector therefore reads no current-B5 5m CONSENSUS row at all (only
the reference-exchange 5m CLOSE, for the fresh-cross check). Later
(Stage 6) stages MAY read the confirming closed 5m bucket's own consensus
row for the frozen §6.3 quality gate applicable at confirmation time,
§8's future `trigger_strength`/`setup_strength` scoring, and lifecycle
evidence more generally — but must NOT invent either a taker-flow
requirement or a `price_direction_agreement >= 2/3` confirmation
threshold for this family; no such gate exists anywhere in §7.3's frozen
`CONFIRMED_BREAKOUT` lifecycle.

**Decision clock — every legal 5m boundary, like `COMPRESSION_BREAKOUT`.**
Given `context.T`: `B5 = selected_bucket("5m", T)`,
`B1h = selected_bucket("1h", T)`. There is NO `B1h + 1h == T` restriction
— e.g. `T=13:05` is a natural, legal evaluation instant
(`B1h=[12:00,13:00)`, `B5=[13:00,13:05)`): the 1h structural history has
already closed, and the newly closed 5m bucket after it may now break
that level.

**Structural level (§7.3, exact `LEVEL_LOOKBACK=48`-bucket 1h grid ending
at `B1h`).** `resistance_level = max(HTF_high(1h, b))`,
`support_level = min(HTF_low(1h, b))` over ALL 48 buckets — derived via
`aligned_inputs.derive_reference_extrema()` UNCHANGED (never a private
high/low reimplementation from `close_price`/consensus fields; this
module owns identity pre-validation of each PRESENT reference-feature row
that `derive_reference_extrema()` itself does not check). ANY one of the
48 buckets being unavailable makes the WHOLE level unavailable (`None`) —
intentionally stricter than `COMPRESSION_BREAKOUT`'s selected-run subset,
because there is no "selected run" concept here: every one of the 48
buckets structurally contributes. The tie-broken anchor `bucket_ts` (§7.0c)
uses the REAL shared `select_extreme_anchor()` for both `mode="max"`
(resistance) and `mode="min"` (support) — never a private tie-break.

**Structural-anchor boundary (§12/§15, load-bearing).** §12 later defines
`CONFIRMED_BREAKOUT`'s actual `episode_logical_key` from `(bucket_ts,
price)` of the broken level, with price TICK-NORMALIZED for episode
identity. This PR is Stage 5, not episode identity — it never constructs
`episode_logical_key` and never invents a tick-rounding algorithm. The
candidate exposes the RAW Stage 5 structural facts at full stored
precision (`level_anchor_bucket`, `level_price`); `structural_anchor`
(mirroring #40/#41's naming) is a read-only property returning exactly
`level_anchor_bucket` — Stage 6 alone owns the final episode-key
construction/tick normalization built from these raw facts.

**Fresh 5m crossing (§7.3, same clean interpretation as #41's §7.2).**
Requires the current AND immediately-previous closed Binance 5m reference
closes:

    LONG  fresh cross: previous_close <= resistance_level AND current_close > resistance_level
    SHORT fresh cross: previous_close >= support_level    AND current_close < support_level

Boundary equality at the CURRENT close never creates a candidate. Already
outside on the PREVIOUS close too is not a fresh crossing. This module
never consults episode storage to decide "first globally" — only this one
observable two-close transition.

**Directional context (§7.0b, reused unchanged).** Once a fresh direction
is derived, `setup_common.directional_context_gate(context, direction)`
must return `accepted is True` — the ONLY context gate this family uses
(never `TREND_PULLBACK`'s stricter firm-agreement precondition).

**Protection buffer / entry zone / invalidation (§7, §9, §10) — structural
facts only.** The 1h reference price for `protection_buffer()` is the
canonical Binance 1h `close_price` AT `B1h` (already inside the 48-bucket
structural window — no extra current-1h read). `RANGE_PROXY_pct(1h, 14,
B1h)` uses a SEPARATE, smaller 14-bucket 1h consensus window (distinct
from the 48-bucket structural window, which carries no consensus rows at
all):

    LONG:  entry_zone = [resistance_level, resistance_level + buffer]
           invalidation_price = resistance_level - buffer
    SHORT: entry_zone = [support_level - buffer, support_level]
           invalidation_price = support_level + buffer

This module never checks whether `invalidation_price` has since been
crossed, never applies the false-break rule, and never uses a future
`confirmation_close_price` — all Stage 6.

**`V2ConfirmedBreakoutInputs` is a bare container, not self-validating**
(mirrors #40/#41's precedent) — `detect_confirmed_breakout()` never
trusts it blindly.

Pure module: no DB, no `asyncpg`, no network, no filesystem, no clock (no
`datetime.now()`/`utcnow()`/`time.time()`), no config loading, no
`random`/`uuid`/`subprocess`. `detect_confirmed_breakout()` is
synchronous; the same `inputs` always yields the same result.
"""
from __future__ import annotations

from collections.abc import Mapping as _AbcMapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Mapping, Optional

from analytics.forecasting_v2.aligned_inputs import (
    V2_REFERENCE_EXCHANGE, V2AlignedInputError, derive_reference_extrema,
)
from analytics.forecasting_v2.alignment import (
    TIMEFRAME_MINUTES, V2AlignmentError, selected_bucket,
)
from analytics.forecasting_v2.context_snapshot import V2ContextSnapshot
from analytics.forecasting_v2.events import DIRECTIONS, LONG, SHORT
from analytics.forecasting_v2.setup_common import (
    RANGE_PROXY_N, SETUP_MIN_CONFIDENCE, SETUP_MIN_COVERAGE, V2ExtremeAnchor,
    V2SetupFoundationError, directional_context_gate, protection_buffer, range_proxy_pct,
    select_extreme_anchor,
)

__all__ = [
    "V2ConfirmedBreakoutError",
    "LEVEL_LOOKBACK",
    "CONFIRMED_BREAKOUT_CONFIRMATION_MAX_AGE_5M_BUCKETS",
    "EXPECTED_HORIZON",
    "V2ConfirmedBreakoutInputs",
    "V2ConfirmedBreakoutCandidate",
    "detect_confirmed_breakout",
]


class V2ConfirmedBreakoutError(ValueError):
    """Malformed PRESENT input to this module: a non-
    `V2ConfirmedBreakoutInputs` argument, a non-`V2ContextSnapshot`
    `inputs.context`, a non-Mapping or identity-mismatched/duplicate/
    out-of-grid history row, a required field missing entirely from a
    returned row, a non-finite/non-positive/`bool` numeric value where a
    real number is required, an impossible structural level
    (`support_level > resistance_level`), an impossible simultaneous
    LONG+SHORT fresh-cross, an identity-mismatched/incomplete instrument
    row, or a wrapped `V2SetupFoundationError`/`V2AlignedInputError` from
    one of the shared primitives this module reuses, for genuinely
    corrupted (not missing) data. Never raised for a legitimate
    non-qualification — see module docstring's exhaustive list of `None`
    cases."""


# ============================================================================
# frozen V2-v0 CONFIRMED_BREAKOUT family constants (not runtime-tunable;
# every value here is already-frozen contract behavior, never a new or
# config-tuned parameter; no rules_version bump).
# ============================================================================
LEVEL_LOOKBACK = 48
# Stage 6 (Episode State Machine) owns COUNTING an EARLY_SIGNAL's age
# against this and evaluating the CONFIRMED transition -- exposed here
# only as shared family metadata, never evaluated by anything in this
# module (see module docstring). Already family-prefixed at module scope
# (no collision risk, unlike EXPECTED_HORIZON below), so no separate
# __init__.py alias is needed for this one.
CONFIRMED_BREAKOUT_CONFIRMATION_MAX_AGE_5M_BUCKETS = 8
# Expected trade horizon FROM `CONFIRMED` (§14) -- Stage 6/7/8 metadata;
# this module never computes or reads a horizon deadline itself. Exported
# at package level as `CONFIRMED_BREAKOUT_EXPECTED_HORIZON` (never a
# second ambiguous package-level `EXPECTED_HORIZON` -- both
# `trend_pullback.py` and `compression_breakout.py` already claim that
# name at package scope under their own family prefixes, see
# `__init__.py`).
EXPECTED_HORIZON = timedelta(minutes=150)

_FIVE_MIN = timedelta(minutes=TIMEFRAME_MINUTES["5m"])
_ONE_HOUR = timedelta(minutes=TIMEFRAME_MINUTES["1h"])
_FULL_1H_BAR_COUNT = TIMEFRAME_MINUTES["1h"]
_FULL_5M_BAR_COUNT = TIMEFRAME_MINUTES["5m"]


# ---- shared numeric/identity validation (small local private copy, matching
# the established codebase precedent -- see compression_breakout.py's own
# docstring) ------------------------------------------------------------------
def _is_finite(value: float) -> bool:
    return value == value and value not in (float("inf"), float("-inf"))  # NaN != NaN


def _validate_finite_numeric(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise V2ConfirmedBreakoutError(
            f"{name} must be a real number, got {type(value).__name__}: {value!r}")
    v = float(value)
    if not _is_finite(v):
        raise V2ConfirmedBreakoutError(f"{name} must be finite, got {value!r}")
    return v


def _validate_nonnegative_finite(value: Any, name: str) -> float:
    v = _validate_finite_numeric(value, name)
    if v < 0.0:
        raise V2ConfirmedBreakoutError(f"{name} must be >= 0.0, got {v!r}")
    return v


def _validate_positive_finite(value: Any, name: str) -> float:
    v = _validate_finite_numeric(value, name)
    if not (v > 0.0):
        raise V2ConfirmedBreakoutError(f"{name} must be > 0, got {v!r}")
    return v


def _validate_utc_whole_minute(value: Any, name: str) -> datetime:
    if type(value) is not datetime:
        raise V2ConfirmedBreakoutError(f"{name} must be a datetime, got {type(value).__name__}")
    if value.tzinfo is None or value.utcoffset() is None:
        raise V2ConfirmedBreakoutError(f"{name} must be timezone-aware")
    if value.utcoffset() != timedelta(0):
        raise V2ConfirmedBreakoutError(f"{name} must be UTC (offset 0), got {value.utcoffset()}")
    if value.second != 0 or value.microsecond != 0:
        raise V2ConfirmedBreakoutError(f"{name} must be a whole minute (no seconds/microseconds)")
    return value


def _validate_1h_bucket_start(value: Any, name: str) -> datetime:
    """A legal 1h bucket START on the canonical V2 grid -- reuses
    `alignment.selected_bucket()`'s own round-trip technique (never a
    second, competing grid convention): `value` is a legal 1h bucket
    start iff selecting the 1h bucket for `T = value + 1h` round-trips
    back to `value` exactly."""
    v = _validate_utc_whole_minute(value, name)
    try:
        canonical = selected_bucket("1h", v + _ONE_HOUR)
    except V2AlignmentError as exc:
        raise V2ConfirmedBreakoutError(f"{name} is not a legal 1h bucket start: {exc}") from exc
    if canonical != v:
        raise V2ConfirmedBreakoutError(f"{name} is not aligned to the canonical 1h bucket grid")
    return v


def _validate_row_container(rows: Any, name: str) -> Any:
    if rows is None or isinstance(rows, (str, bytes, bytearray)):
        raise V2ConfirmedBreakoutError(
            f"{name} must be a Sequence of Mapping rows (not None/str/bytes), got "
            f"{type(rows).__name__}")
    try:
        iter(rows)
    except TypeError as exc:
        raise V2ConfirmedBreakoutError(
            f"{name} must be an iterable Sequence of Mapping rows, got "
            f"{type(rows).__name__}: {exc}") from exc
    return rows


def _require_fields(row: Any, required_fields: "tuple[str, ...]", label: str) -> None:
    if not isinstance(row, _AbcMapping):
        raise V2ConfirmedBreakoutError(
            f"{label} must be a Mapping, got {type(row).__name__}: {row!r}")
    missing = [f for f in required_fields if f not in row]
    if missing:
        raise V2ConfirmedBreakoutError(f"{label} is missing required field(s) {missing!r}")


# ============================================================================
# input value object -- bare container, no self-validation (see module
# docstring's "V2ConfirmedBreakoutInputs is a bare container" section).
# ============================================================================
@dataclass(frozen=True)
class V2ConfirmedBreakoutInputs:
    """Everything `detect_confirmed_breakout()` needs for ONE
    `context.T`: the already-computed `V2ContextSnapshot`, the exact
    `RANGE_PROXY_N=14`-bucket 1h consensus window (`consensus_1h_rows`,
    dual-purpose -- also carries the current-B1h setup-quality row; a
    SEPARATE, smaller window from the 48-bucket structural lookback
    below), the exact `LEVEL_LOOKBACK=48`-bucket 1h reference-feature
    window (`reference_1h_rows`), the raw 1m klines covering that whole
    48h lookback plus one extra 1h bucket (`reference_1m_rows`, half-open
    `[B1h-47h, B1h+1h)`), the two closed 5m reference-feature buckets
    needed for the fresh-cross check (`reference_5m_rows`), and the
    single `exchange_instruments` row for `protection_buffer()`'s
    `tick_size` (`instrument`, `None` if absent). Deliberately carries NO
    current-B5 5m CONSENSUS rows and no percentile rows at all (§7.3 has
    no taker-flow/agreement EARLY_SIGNAL requirement for this family, see
    module docstring). No DB handle, no pool, no reader is retained here
    -- rows are plain, already-detached `Mapping`s (as `storage/
    v2_setup_readers.py`'s readers already return them).
    `detect_confirmed_breakout()` never mutates any row it reads from
    this object."""
    context: V2ContextSnapshot
    consensus_1h_rows: "tuple[Mapping, ...]"
    reference_1h_rows: "tuple[Mapping, ...]"
    reference_1m_rows: "tuple[Mapping, ...]"
    reference_5m_rows: "tuple[Mapping, ...]"
    instrument: Optional[Mapping]


# ============================================================================
# result value object -- public Stage 5 API, self-validates on ANY direct
# construction (mirrors V2CompressionBreakoutCandidate's established
# frozen-dataclass __post_init__ pattern).
# ============================================================================
@dataclass(frozen=True)
class V2ConfirmedBreakoutCandidate:
    """One deterministic `CONFIRMED_BREAKOUT` qualification at `T`
    (§7.3). A QUALIFICATION only -- see module docstring's Stage 5/6
    boundary section for everything this is deliberately NOT: not an
    episode, not an `EARLY_SIGNAL`, not confirmed, not scored, not
    persisted.

    Direction determines `level_price`'s meaning: `resistance_level` for
    `LONG`, `support_level` for `SHORT` -- no redundant resistance/
    support field pair is carried in a one-direction candidate
    (`level_kind` exposes this as a read-only derived label). No
    `price_direction_agreement`/`taker_delta_notional_usd_sum` fields
    exist on this candidate at all -- §7.3 freezes no such EARLY_SIGNAL
    gate for this family (load-bearing difference from
    `V2CompressionBreakoutCandidate`, see module docstring)."""
    T: datetime
    direction: str
    bucket_5m: datetime
    bucket_1h: datetime
    previous_5m_close: float
    breakout_close: float
    level_anchor_bucket: datetime
    level_price: float
    range_proxy_pct: float
    protection_buffer: float
    entry_zone_lower: float
    entry_zone_upper: float
    invalidation_price: float

    def __post_init__(self) -> None:
        if self.direction not in DIRECTIONS:
            raise V2ConfirmedBreakoutError(
                f"direction must be one of {DIRECTIONS}, got {self.direction!r}")

        t = _validate_utc_whole_minute(self.T, "T")
        try:
            b5 = selected_bucket("5m", t)
        except V2AlignmentError as exc:
            raise V2ConfirmedBreakoutError(
                f"T={t.isoformat()} is not a legal V2 5m decision boundary: {exc}") from exc
        b1h = selected_bucket("1h", t)
        if self.bucket_5m != b5:
            raise V2ConfirmedBreakoutError(
                f"bucket_5m does not match selected_bucket('5m', T) -- expected {b5!r}, "
                f"got {self.bucket_5m!r}")
        if self.bucket_1h != b1h:
            raise V2ConfirmedBreakoutError(
                f"bucket_1h does not match selected_bucket('1h', T) -- expected {b1h!r}, "
                f"got {self.bucket_1h!r}")

        anchor_bucket = _validate_1h_bucket_start(self.level_anchor_bucket, "level_anchor_bucket")
        lookback_start = b1h - (LEVEL_LOOKBACK - 1) * _ONE_HOUR
        if not (lookback_start <= anchor_bucket <= b1h):
            raise V2ConfirmedBreakoutError(
                f"level_anchor_bucket {anchor_bucket!r} is outside the {LEVEL_LOOKBACK}-bucket "
                f"lookback [{lookback_start!r}, {b1h!r}]")

        level_price = _validate_positive_finite(self.level_price, "level_price")
        previous_close = _validate_positive_finite(self.previous_5m_close, "previous_5m_close")
        breakout_close = _validate_positive_finite(self.breakout_close, "breakout_close")

        buf = _validate_positive_finite(self.protection_buffer, "protection_buffer")
        _validate_nonnegative_finite(self.range_proxy_pct, "range_proxy_pct")

        entry_lower = _validate_positive_finite(self.entry_zone_lower, "entry_zone_lower")
        entry_upper = _validate_positive_finite(self.entry_zone_upper, "entry_zone_upper")
        if not (entry_lower <= entry_upper):
            raise V2ConfirmedBreakoutError(
                f"entry_zone_lower ({entry_lower!r}) must be <= entry_zone_upper "
                f"({entry_upper!r})")

        invalidation = _validate_positive_finite(self.invalidation_price, "invalidation_price")

        if self.direction == LONG:
            if not (previous_close <= level_price and breakout_close > level_price):
                raise V2ConfirmedBreakoutError(
                    "LONG fresh-cross invariant violated: require previous_5m_close <= "
                    f"level_price ({level_price!r}) and breakout_close > level_price, got "
                    f"previous_5m_close={previous_close!r}, breakout_close={breakout_close!r}")
            if entry_lower != level_price or entry_upper != level_price + buf:
                raise V2ConfirmedBreakoutError(
                    "LONG entry zone is inconsistent with level_price/protection_buffer -- "
                    f"expected [{level_price!r}, {level_price + buf!r}], got "
                    f"[{entry_lower!r}, {entry_upper!r}]")
            if invalidation != level_price - buf:
                raise V2ConfirmedBreakoutError(
                    "LONG invalidation_price is inconsistent with level_price/protection_buffer "
                    f"-- expected {level_price - buf!r}, got {invalidation!r}")
            if not (invalidation < level_price):
                raise V2ConfirmedBreakoutError(
                    f"LONG invalidation_price must be < level_price ({level_price!r}), got "
                    f"{invalidation!r}")
        else:
            if not (previous_close >= level_price and breakout_close < level_price):
                raise V2ConfirmedBreakoutError(
                    "SHORT fresh-cross invariant violated: require previous_5m_close >= "
                    f"level_price ({level_price!r}) and breakout_close < level_price, got "
                    f"previous_5m_close={previous_close!r}, breakout_close={breakout_close!r}")
            if entry_upper != level_price or entry_lower != level_price - buf:
                raise V2ConfirmedBreakoutError(
                    "SHORT entry zone is inconsistent with level_price/protection_buffer -- "
                    f"expected [{level_price - buf!r}, {level_price!r}], got "
                    f"[{entry_lower!r}, {entry_upper!r}]")
            if invalidation != level_price + buf:
                raise V2ConfirmedBreakoutError(
                    "SHORT invalidation_price is inconsistent with level_price/protection_buffer "
                    f"-- expected {level_price + buf!r}, got {invalidation!r}")
            if not (invalidation > level_price):
                raise V2ConfirmedBreakoutError(
                    f"SHORT invalidation_price must be > level_price ({level_price!r}), got "
                    f"{invalidation!r}")

    @property
    def structural_anchor(self) -> datetime:
        """RAW Stage 5 structural anchor fact -- always exactly
        `level_anchor_bucket`, at full stored precision. §12 later
        defines `CONFIRMED_BREAKOUT`'s actual `episode_logical_key` from
        `(bucket_ts, price)` of this broken level with the price
        TICK-NORMALIZED -- Stage 6 alone owns that final episode-key
        construction/rounding; this property is NOT that key, only the
        raw fact it will be built from. Never an independently
        stored/settable second value."""
        return self.level_anchor_bucket

    @property
    def level_kind(self) -> str:
        """`"RESISTANCE"` for `LONG` (a broken resistance level),
        `"SUPPORT"` for `SHORT` (a broken support level) -- a read-only
        derived label, not a second contradictable field."""
        return "RESISTANCE" if self.direction == LONG else "SUPPORT"

    @property
    def level_anchor(self) -> V2ExtremeAnchor:
        """Convenience reconstruction of the `V2ExtremeAnchor` this
        candidate's `level_anchor_bucket`/`level_price` were derived
        from -- computed on demand, never stored as a duplicate field
        that could silently disagree with the two raw ones above."""
        return V2ExtremeAnchor(bucket_ts=self.level_anchor_bucket, value=self.level_price)

    @property
    def breakout_distance_beyond_level(self) -> float:
        """§8's future `setup_strength` component
        (`breakout_distance_beyond_level / protection_buffer`) needs this
        raw distance -- exposed here as a read-only derived fact, NEVER
        as `confidence`/`probability`/`win_probability`. This module
        computes only the raw structural facts a later scoring layer
        will read; it never computes `model_confidence` itself."""
        if self.direction == LONG:
            return self.breakout_close - self.level_price
        return self.level_price - self.breakout_close


# ============================================================================
# the pure detector
# ============================================================================
_CONSENSUS_1H_IDENTITY_FIELDS = (
    "symbol", "market_type", "timeframe", "calculation_version", "feature_schema_version",
    "bucket_ts",
)
_CONSENSUS_1H_VALUE_FIELDS = (
    "min_coverage_ratio", "consensus_confidence", "range_width_pct_median",
)
_CONSENSUS_1H_REQUIRED_FIELDS = _CONSENSUS_1H_IDENTITY_FIELDS + _CONSENSUS_1H_VALUE_FIELDS
_QUALITY_FIELDS = ("min_coverage_ratio", "consensus_confidence")
_REFERENCE_IDENTITY_FIELDS = (
    "exchange", "symbol", "market_type", "timeframe", "calculation_version",
    "feature_schema_version", "bucket_ts",
)
_REFERENCE_GATE_FIELDS = ("is_usable", "has_gap", "bars_present", "bars_expected", "close_price")
_REFERENCE_REQUIRED_FIELDS = _REFERENCE_IDENTITY_FIELDS + _REFERENCE_GATE_FIELDS
_RAW_BAR_REQUIRED_FIELDS = ("exchange", "symbol", "ts", "high", "low")
_INSTRUMENT_REQUIRED_FIELDS = ("exchange", "symbol", "market_type", "tick_size")


def _validate_consensus_1h_row_identity(
    row: Any, *, context: V2ContextSnapshot, expected_set: frozenset,
) -> datetime:
    """§18: full PRESENT identity re-check for one 1h RANGE_PROXY/current-
    quality consensus row, including the required VALUE keys
    (`min_coverage_ratio`/`consensus_confidence`/`range_width_pct_median`)
    -- a row structurally missing any of these three is corruption
    (raises), independent of whether their VALUES are legitimately SQL
    NULL (handled separately, at the point each value is actually
    needed)."""
    _require_fields(row, _CONSENSUS_1H_REQUIRED_FIELDS, "1h consensus row")
    if row["symbol"] != context.symbol:
        raise V2ConfirmedBreakoutError(
            f"1h consensus row symbol must be {context.symbol!r}, got {row['symbol']!r}")
    if row["market_type"] != context.market_type:
        raise V2ConfirmedBreakoutError(
            f"1h consensus row market_type must be {context.market_type!r}, got "
            f"{row['market_type']!r}")
    if row["timeframe"] != "1h":
        raise V2ConfirmedBreakoutError(
            f"1h consensus row timeframe must be '1h', got {row['timeframe']!r}")
    if row["calculation_version"] != context.calculation_version:
        raise V2ConfirmedBreakoutError(
            f"1h consensus row calculation_version must be {context.calculation_version!r}, "
            f"got {row['calculation_version']!r}")
    if row["feature_schema_version"] != context.feature_schema_version:
        raise V2ConfirmedBreakoutError(
            f"1h consensus row feature_schema_version must be "
            f"{context.feature_schema_version!r}, got {row['feature_schema_version']!r}")
    bucket_ts = _validate_utc_whole_minute(row["bucket_ts"], "1h consensus row bucket_ts")
    if bucket_ts not in expected_set:
        raise V2ConfirmedBreakoutError(
            f"1h consensus row bucket_ts {bucket_ts.isoformat()} is outside the expected "
            f"{RANGE_PROXY_N}-bucket 1h RANGE_PROXY window")
    return bucket_ts


def _validate_quality_fields(row: Mapping) -> "Optional[tuple[float, float]]":
    """§6.2/§6.3's frozen timeframe-invariant consensus-quality gate,
    applied to the current-B1h row. A missing required key is corruption
    (raises, though `_validate_consensus_1h_row_identity` already
    guarantees presence for every row in this family). A present key
    whose value is SQL NULL is legitimate unavailable quality -- but BOTH
    fields are validated for corruption BEFORE either's missingness can
    short-circuit the other (corruption precedence)."""
    missing = [f for f in _QUALITY_FIELDS if f not in row]
    if missing:
        raise V2ConfirmedBreakoutError(
            f"1h consensus row is missing required field(s) {missing!r}")

    coverage_raw = row["min_coverage_ratio"]
    coverage: Optional[float] = None
    if coverage_raw is not None:
        coverage = _validate_finite_numeric(coverage_raw, "min_coverage_ratio")
        if not (0.0 <= coverage <= 1.0):
            raise V2ConfirmedBreakoutError(
                f"min_coverage_ratio must be within [0.0, 1.0], got {coverage!r}")

    confidence_raw = row["consensus_confidence"]
    confidence: Optional[float] = None
    if confidence_raw is not None:
        confidence = _validate_finite_numeric(confidence_raw, "consensus_confidence")
        if not (0.0 <= confidence <= 100.0):
            raise V2ConfirmedBreakoutError(
                f"consensus_confidence must be within [0.0, 100.0], got {confidence!r}")

    if coverage is None or confidence is None:
        return None
    return coverage, confidence


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
        raise V2ConfirmedBreakoutError(
            f"reference {timeframe} row exchange must be {V2_REFERENCE_EXCHANGE!r}, got "
            f"{row['exchange']!r}")
    if row["symbol"] != context.symbol:
        raise V2ConfirmedBreakoutError(
            f"reference {timeframe} row symbol must be {context.symbol!r}, got "
            f"{row['symbol']!r}")
    if row["market_type"] != context.market_type:
        raise V2ConfirmedBreakoutError(
            f"reference {timeframe} row market_type must be {context.market_type!r}, got "
            f"{row['market_type']!r}")
    if row["timeframe"] != timeframe:
        raise V2ConfirmedBreakoutError(
            f"reference row timeframe must be {timeframe!r}, got {row['timeframe']!r}")
    if row["calculation_version"] != context.calculation_version:
        raise V2ConfirmedBreakoutError(
            f"reference {timeframe} row calculation_version must be "
            f"{context.calculation_version!r}, got {row['calculation_version']!r}")
    if row["feature_schema_version"] != context.feature_schema_version:
        raise V2ConfirmedBreakoutError(
            f"reference {timeframe} row feature_schema_version must be "
            f"{context.feature_schema_version!r}, got {row['feature_schema_version']!r}")

    bucket_ts = _validate_utc_whole_minute(row["bucket_ts"], f"reference {timeframe} row bucket_ts")
    if bucket_ts not in expected_set:
        raise V2ConfirmedBreakoutError(
            f"reference {timeframe} row bucket_ts {bucket_ts.isoformat()} is outside the "
            f"expected lookback")

    is_usable = row["is_usable"]
    if not isinstance(is_usable, bool):
        raise V2ConfirmedBreakoutError(
            f"reference {timeframe} row is_usable must be a bool, got "
            f"{type(is_usable).__name__}")
    has_gap = row["has_gap"]
    if not isinstance(has_gap, bool):
        raise V2ConfirmedBreakoutError(
            f"reference {timeframe} row has_gap must be a bool, got {type(has_gap).__name__}")

    bars_present = row["bars_present"]
    bars_expected = row["bars_expected"]
    for name, value in (("bars_present", bars_present), ("bars_expected", bars_expected)):
        if isinstance(value, bool) or not isinstance(value, int):
            raise V2ConfirmedBreakoutError(
                f"reference {timeframe} row {name} must be an int, got {type(value).__name__}")
    if bars_expected != full_bar_count:
        raise V2ConfirmedBreakoutError(
            f"reference {timeframe} row bars_expected must be exactly {full_bar_count}, got "
            f"{bars_expected!r}")
    if bars_present < 0:
        raise V2ConfirmedBreakoutError(
            f"reference {timeframe} row bars_present must be >= 0, got {bars_present!r}")
    if bars_present > bars_expected:
        raise V2ConfirmedBreakoutError(
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
    """Validate ONLY the fields a raw `klines_1m` row physically carries
    (`exchange`/`symbol`/`ts` -- no `market_type` column exists on this
    table). High/low PRICE validation and per-bucket minute-grid/gap/
    duplicate checks remain `derive_reference_extrema()`'s own job, never
    duplicated here."""
    _require_fields(row, _RAW_BAR_REQUIRED_FIELDS, "raw reference 1m row")
    if row["exchange"] != V2_REFERENCE_EXCHANGE:
        raise V2ConfirmedBreakoutError(
            f"raw reference 1m row exchange must be {V2_REFERENCE_EXCHANGE!r}, got "
            f"{row['exchange']!r}")
    if row["symbol"] != context.symbol:
        raise V2ConfirmedBreakoutError(
            f"raw reference 1m row symbol must be {context.symbol!r}, got {row['symbol']!r}")
    ts = _validate_utc_whole_minute(row["ts"], "raw reference 1m row ts")
    if not (window_start <= ts < window_end):
        raise V2ConfirmedBreakoutError(
            f"raw reference 1m row ts {ts.isoformat()} is outside the requested half-open "
            f"interval [{window_start.isoformat()}, {window_end.isoformat()})")
    return ts


def detect_confirmed_breakout(
    inputs: V2ConfirmedBreakoutInputs,
) -> Optional[V2ConfirmedBreakoutCandidate]:
    """Deterministically qualify (or not) `CONFIRMED_BREAKOUT` at
    `inputs.context.T` (see module docstring for the complete formula/
    precondition set and the exhaustive Stage 5/6 boundary this
    respects). Pure, synchronous; the same `inputs` always yields the
    same result.

    Evaluation order (load-bearing, §7.3/§21 corruption precedence):
    (1) top-level input/context validation; (2) derive B5/B1h; (3)
    validate the exact 14-row 1h consensus/RANGE_PROXY window's identity
    in full (so malformed PRESENT data anywhere in that family always
    raises); (4) current-B1h §6.2/§6.3 quality gate -- a failed/missing
    gate here is itself a "preceding deterministic gate" that makes the
    48-bucket structural derivation below semantically irrelevant, so it
    short-circuits to `None` first (§21); (5) validate the exact 48-bucket
    1h reference-feature window's identity in full; (6) validate the raw
    1m family; (7) derive all 48 `HTF_high`/`HTF_low` extrema -- any ONE
    unavailable bucket makes the WHOLE level unavailable; (8) select
    resistance/support anchors via the real `select_extreme_anchor()`;
    (9) compute `RANGE_PROXY_pct` from the already-validated 14-row window
    (missing peer -> `None`, never a bare `KeyError`); (10) require the
    B1h canonical reference close; (11) validate the two closed 5m
    reference closes; (12)-(13) derive the fresh LONG/SHORT direction, or
    `None`; (14) `directional_context_gate` -- the ONLY context/consensus
    gate this family uses (no taker-flow, no agreement threshold); (15)
    the instrument/tick lookup; (16) `protection_buffer`; (17) construct
    the candidate.

    Returns `None` for every legitimate non-qualification (see module
    docstring for the full inventory). Raises `V2ConfirmedBreakoutError`
    for malformed PRESENT input of any kind."""
    if not isinstance(inputs, V2ConfirmedBreakoutInputs):
        raise V2ConfirmedBreakoutError(
            f"inputs must be a V2ConfirmedBreakoutInputs, got {type(inputs).__name__}")
    context = inputs.context
    if not isinstance(context, V2ContextSnapshot):
        raise V2ConfirmedBreakoutError(
            f"inputs.context must be a V2ContextSnapshot, got {type(context).__name__}")

    # ---- §1/§7.3 decision clock: EVERY legal 5m boundary, no 1h-boundary
    # restriction --------------------------------------------------------
    T = context.T
    B5 = selected_bucket("5m", T)
    B1h = selected_bucket("1h", T)

    # ---- §16/§17/§18 exact 14-bucket 1h RANGE_PROXY/current-quality window
    proxy_grid = tuple(
        B1h - (RANGE_PROXY_N - 1 - i) * _ONE_HOUR for i in range(RANGE_PROXY_N))
    proxy_set = frozenset(proxy_grid)

    consensus_rows = _validate_row_container(inputs.consensus_1h_rows, "consensus_1h_rows")
    consensus_by_bucket: "dict[datetime, Mapping]" = {}
    for row in consensus_rows:
        bucket_ts = _validate_consensus_1h_row_identity(
            row, context=context, expected_set=proxy_set)
        if bucket_ts in consensus_by_bucket:
            raise V2ConfirmedBreakoutError(
                f"duplicate 1h consensus row for bucket_ts {bucket_ts.isoformat()}")
        consensus_by_bucket[bucket_ts] = row

    # ---- §16 current-B1h §6.2/§6.3 quality gate ----------------------------
    current_row = consensus_by_bucket.get(B1h)
    current_quality = _validate_quality_fields(current_row) if current_row is not None else None
    if current_quality is None:
        return None
    current_coverage, current_confidence = current_quality
    if current_coverage < SETUP_MIN_COVERAGE or current_confidence < SETUP_MIN_CONFIDENCE:
        return None

    # ---- §8/§9/§10 exact 48-bucket 1h structural reference-feature window -
    level_grid = tuple(
        B1h - (LEVEL_LOOKBACK - 1 - i) * _ONE_HOUR for i in range(LEVEL_LOOKBACK))
    level_set = frozenset(level_grid)

    reference_1h_rows = _validate_row_container(inputs.reference_1h_rows, "reference_1h_rows")
    reference_row_by_bucket: "dict[datetime, Mapping]" = {}
    close_by_bucket_1h: "dict[datetime, float]" = {}
    seen_1h_bucket_ts: set = set()
    for row in reference_1h_rows:
        bucket_ts, close = _validate_reference_row(
            row, context=context, timeframe="1h", full_bar_count=_FULL_1H_BAR_COUNT,
            expected_set=level_set)
        if bucket_ts in seen_1h_bucket_ts:
            raise V2ConfirmedBreakoutError(
                f"duplicate reference 1h row for bucket_ts {bucket_ts.isoformat()}")
        seen_1h_bucket_ts.add(bucket_ts)
        reference_row_by_bucket[bucket_ts] = row
        if close is not None:
            close_by_bucket_1h[bucket_ts] = close

    # ---- §11/§12 raw 1m history covering the whole 48h lookback -----------
    raw_window_start = level_grid[0]
    raw_window_end = B1h + _ONE_HOUR
    raw_rows = _validate_row_container(inputs.reference_1m_rows, "reference_1m_rows")
    raw_by_bucket: "dict[datetime, list]" = {}
    seen_raw_ts: set = set()
    for row in raw_rows:
        ts = _validate_raw_1m_row_identity(
            row, context=context, window_start=raw_window_start, window_end=raw_window_end)
        if ts in seen_raw_ts:
            raise V2ConfirmedBreakoutError(f"duplicate raw reference 1m row for ts {ts.isoformat()}")
        seen_raw_ts.add(ts)
        minutes = (ts - raw_window_start) // timedelta(minutes=1)
        owning_bucket = raw_window_start + (minutes // _FULL_1H_BAR_COUNT) * _ONE_HOUR
        raw_by_bucket.setdefault(owning_bucket, []).append(row)

    # ---- §13/§7.0a all 48 HTF_high/HTF_low extrema -------------------------
    resistance_candidates: "list[Mapping]" = []
    support_candidates: "list[Mapping]" = []
    for b in level_grid:
        ref_row = reference_row_by_bucket.get(b)
        bars = raw_by_bucket.get(b, ())
        try:
            extrema = derive_reference_extrema(
                timeframe="1h", bucket_ts=b, reference_feature=ref_row, reference_klines=bars)
        except V2AlignedInputError as exc:
            raise V2ConfirmedBreakoutError(
                f"derive_reference_extrema failed for structural bucket {b.isoformat()}: "
                f"{exc}") from exc
        if extrema is None:
            return None  # any one of the 48 structural buckets unavailable -> level unavailable
        resistance_candidates.append({"bucket_ts": b, "value": extrema.high})
        support_candidates.append({"bucket_ts": b, "value": extrema.low})

    # ---- §13/§7.0c deterministic latest-tie resistance/support anchors ----
    try:
        resistance_anchor = select_extreme_anchor(resistance_candidates, mode="max")
        support_anchor = select_extreme_anchor(support_candidates, mode="min")
    except V2SetupFoundationError as exc:
        raise V2ConfirmedBreakoutError(f"select_extreme_anchor failed: {exc}") from exc
    if resistance_anchor is None or support_anchor is None:
        raise V2ConfirmedBreakoutError(
            "select_extreme_anchor unexpectedly returned None for a non-empty candidate set")

    resistance_level = _validate_positive_finite(resistance_anchor.value, "resistance_level")
    support_level = _validate_positive_finite(support_anchor.value, "support_level")
    if not (support_level <= resistance_level):
        raise V2ConfirmedBreakoutError(
            f"impossible structural level: support_level ({support_level!r}) > "
            f"resistance_level ({resistance_level!r})")

    # ---- §17/§18 RANGE_PROXY_pct(1h,14,B1h), via the shared primitive -----
    # A bucket in the exact 14-bucket grid legitimately missing from
    # `consensus_by_bucket` is UNAVAILABLE input, exactly like any other
    # incomplete historical window (§21) -- but the completeness check
    # and the PRESENT-row corruption check both belong to `range_proxy_
    # pct()` itself, which already validates every PRESENT row's
    # `range_width_pct_median` BEFORE its own exact-grid-completeness
    # check runs (corruption precedence). Filtering to only the PRESENT
    # rows here (never indexing a missing bucket) avoids a bare
    # `KeyError` while still handing the shared primitive every PRESENT
    # row to validate -- a manual "any missing -> None" short-circuit
    # here would incorrectly mask a malformed PRESENT peer whenever a
    # DIFFERENT peer also happens to be missing, bypassing that
    # corruption-precedence contract.
    proxy_input_rows = tuple(
        consensus_by_bucket[b] for b in proxy_grid if b in consensus_by_bucket)
    try:
        proxy = range_proxy_pct(proxy_input_rows, timeframe="1h", bucket_ts=B1h)
    except V2SetupFoundationError as exc:
        raise V2ConfirmedBreakoutError(f"range_proxy_pct failed: {exc}") from exc
    if proxy is None:
        return None

    # ---- §19 canonical B1h reference close (protection_buffer reference) --
    b1h_close = close_by_bucket_1h.get(B1h)
    if b1h_close is None:
        return None  # no failover -- the 1h reference price is required

    # ---- §20 previous/current closed 5m Binance reference closes ----------
    b5_expected_set = frozenset({B5 - _FIVE_MIN, B5})
    reference_5m_rows = _validate_row_container(inputs.reference_5m_rows, "reference_5m_rows")
    close_by_bucket_5m: "dict[datetime, float]" = {}
    seen_5m_bucket_ts: set = set()
    for row in reference_5m_rows:
        bucket_ts, close = _validate_reference_row(
            row, context=context, timeframe="5m", full_bar_count=_FULL_5M_BAR_COUNT,
            expected_set=b5_expected_set)
        if bucket_ts in seen_5m_bucket_ts:
            raise V2ConfirmedBreakoutError(
                f"duplicate reference 5m row for bucket_ts {bucket_ts.isoformat()}")
        seen_5m_bucket_ts.add(bucket_ts)
        if close is not None:
            close_by_bucket_5m[bucket_ts] = close

    previous_close = close_by_bucket_5m.get(B5 - _FIVE_MIN)
    current_close = close_by_bucket_5m.get(B5)
    if previous_close is None or current_close is None:
        return None

    # ---- §21/§22 fresh breakout direction ----------------------------------
    long_fresh = previous_close <= resistance_level and current_close > resistance_level
    short_fresh = previous_close >= support_level and current_close < support_level
    if long_fresh and short_fresh:
        raise V2ConfirmedBreakoutError(
            "impossible: both LONG and SHORT fresh-cross conditions are simultaneously true "
            f"(support_level={support_level!r}, resistance_level={resistance_level!r}, "
            f"previous_close={previous_close!r}, current_close={current_close!r})")
    if long_fresh:
        direction = LONG
        level_anchor = resistance_anchor
        level_price = resistance_level
    elif short_fresh:
        direction = SHORT
        level_anchor = support_anchor
        level_price = support_level
    else:
        return None  # no fresh crossing -- legitimate non-qualification

    # ---- §7.0b/§24 canonical directional-context compatibility gate -------
    # The ONLY context/consensus gate this family uses at EARLY_SIGNAL --
    # deliberately NO current-B5 5m consensus read, NO taker-flow sign
    # gate, NO price_direction_agreement threshold (§7.3, load-bearing
    # difference from COMPRESSION_BREAKOUT -- see module docstring).
    decision = directional_context_gate(context, direction)
    if not decision.accepted:
        return None

    # ---- §11/§25 instrument identity / tick_size ---------------------------
    instrument = inputs.instrument
    if instrument is None:
        return None
    _require_fields(instrument, _INSTRUMENT_REQUIRED_FIELDS, "instrument row")
    if instrument["exchange"] != V2_REFERENCE_EXCHANGE:
        raise V2ConfirmedBreakoutError(
            f"instrument row exchange must be {V2_REFERENCE_EXCHANGE!r}, got "
            f"{instrument['exchange']!r}")
    if instrument["symbol"] != context.symbol:
        raise V2ConfirmedBreakoutError(
            f"instrument row symbol must be {context.symbol!r}, got {instrument['symbol']!r}")
    if instrument["market_type"] != context.market_type:
        raise V2ConfirmedBreakoutError(
            f"instrument row market_type must be {context.market_type!r}, got "
            f"{instrument['market_type']!r}")
    tick_size_raw = instrument["tick_size"]
    if tick_size_raw is None:
        return None
    tick_size = _validate_positive_finite(tick_size_raw, "instrument tick_size")

    # ---- §7/§26 protection_buffer, via the shared primitive ---------------
    try:
        buffer = protection_buffer(
            reference_price=b1h_close, range_proxy_pct_value=proxy, tick_size=tick_size)
    except V2SetupFoundationError as exc:
        raise V2ConfirmedBreakoutError(f"protection_buffer failed: {exc}") from exc
    if buffer is None:
        return None  # should not normally occur once proxy is already available

    # ---- §27/§28 entry zone + planned structural invalidation -------------
    if direction == LONG:
        entry_zone_lower = level_price
        entry_zone_upper = level_price + buffer
        invalidation_price = level_price - buffer
    else:
        entry_zone_lower = level_price - buffer
        entry_zone_upper = level_price
        invalidation_price = level_price + buffer
    if entry_zone_lower > entry_zone_upper:
        raise V2ConfirmedBreakoutError(
            f"entry_zone_lower ({entry_zone_lower!r}) exceeds entry_zone_upper "
            f"({entry_zone_upper!r})")

    return V2ConfirmedBreakoutCandidate(
        T=T,
        direction=direction,
        bucket_5m=B5,
        bucket_1h=B1h,
        previous_5m_close=previous_close,
        breakout_close=current_close,
        level_anchor_bucket=level_anchor.bucket_ts,
        level_price=level_price,
        range_proxy_pct=proxy,
        protection_buffer=buffer,
        entry_zone_lower=entry_zone_lower,
        entry_zone_upper=entry_zone_upper,
        invalidation_price=invalidation_price,
    )
