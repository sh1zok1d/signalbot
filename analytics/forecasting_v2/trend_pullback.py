"""
V2 `TREND_PULLBACK` setup detector (Stage 5 — Setup Detectors, PR 2 of
~4, docs/FORECASTING_ROADMAP.md §I stage 5).

#39 (merged) built the detector-independent shared foundation
(`setup_common.py`'s `range_proxy_pct`/`protection_buffer`/
`select_extreme_anchor`, `storage/v2_setup_readers.py`'s historical-window
reads). This PR turns that foundation into the FIRST actual V2 setup
qualification, per `docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §7.1:

    At exactly one 15m decision boundary `T`, does the current market
    structure qualify as `TREND_PULLBACK`, and if so, what are the
    deterministic structural facts (`detect_trend_pullback()` returns a
    `V2TrendPullbackCandidate`) needed to create/update that candidate?

**Load-bearing Stage 5 / Stage 6 boundary (§13, do not blur).** This
module answers ONLY the qualification question above. It does NOT decide:

  - whether this `T` is the episode's `T_detect` (the FIRST qualifying
    15m boundary) or a pre-confirmation re-evaluation of an ALREADY
    ACTIVE `EARLY_SIGNAL` episode — a stateless detector cannot know
    that without querying episode history, and this module never does;
  - `episode_id`/`event_id` construction;
  - `EARLY_SIGNAL`/`CONFIRMED`/`WEAKENING`/`INVALIDATED`/`EXPIRED`/
    `COMPLETED` transitions, or the 5m resumption/confirmation trigger
    (§7.1's `T_confirm > T_detect` rule) that promotes `EARLY_SIGNAL` to
    `CONFIRMED` — that trigger reads 5m consensus history this module
    never fetches, and is itself only meaningful relative to an
    ALREADY-EXISTING episode's own `T_detect`, which Stage 6 owns;
  - candidate age/expiry (`PULLBACK_MAX_AGE_15M_BUCKETS`, exposed below
    as a frozen constant but never counted against episode age here);
  - `model_confidence` (§8) — this module exposes the raw structural
    facts (`retracement_pct`, `range_proxy_pct`) a later composite score
    will read, but never computes that score itself.

Every one of those is Stage 6 (Episode State Machine) or later. This
module produces a `V2TrendPullbackCandidate` qualification at the CURRENT
`T` only — repeated calls across consecutive qualifying 15m boundaries
each independently return a fresh candidate; deduplicating those into one
episode is Stage 6's `episode_logical_key` (§12) job, not this module's.

**Formation clock (§7.1, §1.3).** `TREND_PULLBACK` formation is evaluated
ONLY on 15m decision boundaries. Given `context.T`, let `B15 =
selected_bucket("15m", T)`. `T` is a legal 15m FORMATION boundary iff
`B15 + 15m == T` — i.e. `T` is the exact instant the 15m bucket `B15`
closed, not merely some later `T` for which `B15` still happens to be the
latest available bucket. `T=12:15` is a formation boundary (`B15=12:00`,
`B15+15m=12:15==T`); `T=12:20`/`T=12:25` are NOT (`B15` is still `12:00`,
`B15+15m=12:15 != T`) — this is exactly what prevents the same closed 15m
structure from being independently "detected" three times as `T` walks
`12:15 -> 12:20 -> 12:25`. A non-formation `T` is a legitimate
non-qualification (`None`), never `V2TrendPullbackError` — `selected_bucket`
is never floored/re-derived to force a match.

**Strict context precondition (§7.1) — deliberately NOT §7.0b's
`directional_context_gate`.** `TREND_PULLBACK` requires 4h regime and 1h
bias to both FIRMLY AGREE with the candidate direction, stricter than the
breakout families' gate, which permits genuinely measured neutral/
non-directional context (`NON_DIRECTIONAL` 4h regime,
`NEUTRAL_NOT_ESTABLISHED` 1h bias) but fails closed on
`INSUFFICIENT_DATA`/`UNAVAILABLE` context (§7.0b's own distinct
data-availability rejection reasons):

    LONG  iff regime_4h.regime == BULLISH_TRENDING and bias_1h.bias == BULLISH
    SHORT iff regime_4h.regime == BEARISH_TRENDING and bias_1h.bias == BEARISH
    every other combination (NON_DIRECTIONAL, INSUFFICIENT_DATA,
    NEUTRAL_NOT_ESTABLISHED, UNAVAILABLE, or an opposite-direction
    regime/bias) -> no qualification, None.

Direction is ALWAYS derived from `context` this way — `detect_trend_
pullback()` accepts no caller-supplied direction parameter, and
`directional_context_gate` is never imported here (§7.0b explicitly
excludes `TREND_PULLBACK`: a gate that permits neutral/non-directional
context would still be insufficient for `TREND_PULLBACK`'s stronger
firm-agreement requirement, since permitting a merely-non-opposing
context is not the same as requiring the candidate direction to be
firmly established).

**Retracement structure (§7.1, over `LOOKBACK_15M=48` closed 15m
buckets, the reference exchange's own `close_price`).**
`trend_leg_extreme` = `max(close_price)` (LONG) / `min(close_price)`
(SHORT) over the lookback, tie-broken per §7.0c via the shared `select_
extreme_anchor()` (most-recent tie wins, full stored precision, no
private re-implementation of the tie-break here). `retracement_pct =
(trend_leg_extreme - current_close) / trend_leg_extreme * 100` (LONG) /
`(current_close - trend_leg_extreme) / trend_leg_extreme * 100` (SHORT);
valid iff `PULLBACK_MIN_MULT * RANGE_PROXY_pct(15m,14,B15) <=
retracement_pct <= PULLBACK_MAX_MULT * RANGE_PROXY_pct(15m,14,B15)`
(both bounds INCLUSIVE, reusing `setup_common.range_proxy_pct()`
unchanged). `pullback_extreme` (the deepest close reached DURING the
retracement, §7.1) is derived ONLY from the CONTIGUOUS span from
`trend_leg_extreme`'s own anchor bucket THROUGH `B15` inclusive — buckets
strictly OLDER than the anchor contributed to selecting the anchor itself
but are not part of the subsequent retracement, so they never participate
in `pullback_extreme`.

**Exact required history (§7.1/§21, no partial windows, no failover).**
Requires ALL `LOOKBACK_15M=48` expected reference 15m closes AND a usable
`RANGE_PROXY_pct(15m,14,B15)` (`setup_common.range_proxy_pct()`
unchanged, itself requiring its own exact 14-bucket window) — one or more
legitimately missing/gate-failed buckets in either window is UNAVAILABLE
setup input (`None`), never a partial computation. Every reference 15m
bucket is gated by §11's exact reference-vector usability rule
(`is_usable is True`, `has_gap is False`, `bars_present == bars_expected`,
`close_price is not None`) — reused unchanged, never re-derived. A 15m
bucket's `bars_expected` must additionally equal EXACTLY the canonical
full constituent-bar count for that timeframe (`15`, §11) — any other
value is corrupted/impossible identity metadata (`V2TrendPullbackError`),
never merely "one bar missing" (`bars_present < bars_expected` remains
the ordinary, legitimate incompleteness case). No failover to a
non-canonical exchange anywhere (`V2_REFERENCE_EXCHANGE`,
`aligned_inputs.py`, reused unchanged).

**Setup-timeframe consensus quality gate (§6.2/§6.3) — the SAME frozen
numeric gate reused at every V2 timeframe.** The PRESENT consensus row
whose `bucket_ts == B15` (found among the SAME `range_proxy_15m_rows`
window `RANGE_PROXY_pct` already consumes — no fourth storage read) must
satisfy `min_coverage_ratio >= SETUP_MIN_COVERAGE (2/3)` AND
`consensus_confidence >= SETUP_MIN_CONFIDENCE (50.0)`; otherwise no
candidate forms (`None`) — the same currently-degraded-data posture §6.3
already freezes for every other timeframe. A missing required key is
corruption (`V2TrendPullbackError`); a present key that is legitimately
SQL `NULL` is unavailable quality (`None`), validated for corruption
BEFORE any unrelated missing historical `RANGE_PROXY` peer bucket can
short-circuit the result (corruption precedence, mirrors #36-#40's
posture). A current-B15 row that is entirely absent is not fabricated —
`RANGE_PROXY_pct` itself will also legitimately return `None` for the
same incomplete window.

**Instrument identity (§11) — no foreign instrument can influence a
candidate.** The `tick_size` source is validated for EXACT
`exchange`/`symbol`/`market_type` identity against `V2_REFERENCE_
EXCHANGE`/`context.symbol`/`context.market_type` before its `tick_size`
is ever trusted — a hand-built instrument row for a different exchange/
symbol/market cannot silently feed this candidate's `protection_buffer`.
Only the identity fields this module actually relies on are checked here
(the storage reader already validates its own full SQL row shape).

**Structural facts only, no future data (§9/§10).** `protection_buffer`
(`setup_common.protection_buffer()` unchanged) and `invalidation_price =
pullback_extreme -/+ protection_buffer` (LONG/SHORT) are STRUCTURAL FACTS
computed at `T` from already-closed data — this module never checks
whether `invalidation_price` has since been crossed (that is Stage 6's
5m-close invalidation-transition job, §10). The entry zone uses ONLY data
already known at `T` (`current_close = close_price(B15)`), never a future
`confirmation_close_price` (which does not exist until a later `T_confirm`
Stage 6 alone determines).

**Frozen V2-v0 constants (§4/§14/§23) — not runtime-tunable, no
`rules_version` bump; every formula/threshold here is already-frozen
contract behavior, not a new or tuned parameter.**

Pure module: no DB, no `asyncpg`, no network, no filesystem, no clock
(no `datetime.now()`/`utcnow()`/`time.time()`), no config loading, no
`random`/`uuid`/`subprocess`. Consumes only an already-assembled
`V2TrendPullbackInputs` (built by `trend_pullback_inputs.py`, this
module's own sibling, or hand-constructed directly in tests) and Stage
4's `V2ContextSnapshot`. `detect_trend_pullback()` is synchronous; the
same `inputs` always yields the same result.

**`V2TrendPullbackInputs` is a bare container, not self-validating
(mirrors `aligned_inputs.py`'s `V2AlignedInputs` precedent) — the
DETECTOR, not the input container, defends row identity/shape, exactly
like `context_snapshot.py` re-validates `V2AlignedInputs` rather than
trusting a bare dataclass.** This means `detect_trend_pullback()` never
trusts `inputs` blindly, whether it was built by `load_trend_pullback_
inputs()` or hand-constructed directly (tests, a future replay harness):
every reference/range-proxy row is re-checked for exact identity
(`exchange`/`symbol`/`market_type`/`timeframe`/`calculation_version`/
`feature_schema_version`) and required-field presence before any value is
trusted, and a malformed/wrong-shaped row raises `V2TrendPullbackError`
rather than leaking a bare `KeyError`/`AttributeError`/`TypeError`.
"""
from __future__ import annotations

from collections.abc import Mapping as _AbcMapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Mapping, Optional

from analytics.forecasting_v2.aligned_inputs import V2_REFERENCE_EXCHANGE
from analytics.forecasting_v2.alignment import TIMEFRAME_MINUTES, selected_bucket
from analytics.forecasting_v2.bias_1h import BEARISH, BULLISH
from analytics.forecasting_v2.context_snapshot import V2ContextSnapshot
from analytics.forecasting_v2.events import DIRECTIONS, LONG, SHORT
from analytics.forecasting_v2.family_quality import V2FamilyQualityError, family_quality
from analytics.forecasting_v2.regime_4h import BEARISH_TRENDING, BULLISH_TRENDING
from analytics.forecasting_v2.setup_common import (
    MIN_TICK_BUFFER_TICKS, SETUP_MIN_CONFIDENCE, SETUP_MIN_COVERAGE, V2ExtremeAnchor,
    V2SetupFoundationError, protection_buffer, range_proxy_pct, select_extreme_anchor,
)

__all__ = [
    "V2TrendPullbackError",
    "LOOKBACK_15M",
    "PULLBACK_MIN_MULT",
    "PULLBACK_MAX_MULT",
    "PULLBACK_MAX_AGE_15M_BUCKETS",
    "RESUMPTION_MIN_BUCKETS",
    "EXPECTED_HORIZON",
    "V2TrendPullbackInputs",
    "V2TrendPullbackCandidate",
    "detect_trend_pullback",
]


class V2TrendPullbackError(ValueError):
    """Malformed PRESENT input to this module: a non-`V2TrendPullbackInputs`
    argument, a non-`V2ContextSnapshot` `inputs.context` (or, in
    `trend_pullback_inputs.py`, `context`), a non-Mapping or
    identity-mismatched/duplicate/out-of-grid history row, a required
    field missing entirely from a returned row, a non-finite/non-positive/
    `bool` numeric value where a real number is required, an impossible
    negative retracement, a `bars_expected` that is not exactly the
    canonical full 15m constituent-bar count, a malformed PRESENT
    `min_coverage_ratio`/`consensus_confidence` on the current-B15
    consensus row, an identity-mismatched/incomplete instrument row, or a
    wrapped `V2SetupFoundationError` from one of the shared #39 primitives
    (`range_proxy_pct`/`protection_buffer`/`select_extreme_anchor`) for
    genuinely corrupted (not missing) data. Never raised for a legitimate
    non-qualification — see module docstring's exhaustive list of `None`
    cases (not a 15m formation boundary, context precondition not met,
    incomplete required history, unavailable `RANGE_PROXY_pct`, degraded
    current-B15 consensus quality, retracement outside the valid band,
    unavailable instrument/tick metadata)."""


# ============================================================================
# §4/§14/§23 — frozen V2-v0 TREND_PULLBACK family constants (not
# runtime-tunable; every value here is already-frozen contract behavior,
# never a new or config-tuned parameter; no rules_version bump).
# ============================================================================
LOOKBACK_15M = 48
PULLBACK_MIN_MULT = 0.5
PULLBACK_MAX_MULT = 3.0
# Stage 6 (Episode State Machine) owns COUNTING episode age against this
# and returning EXPIRED -- exposed here only as shared family metadata,
# never evaluated by anything in this module (see module docstring).
PULLBACK_MAX_AGE_15M_BUCKETS = 8
# Stage 6 owns evaluating the 5m resumption/confirmation trigger this
# governs (§7.1's "one closed 5m bucket" rule) -- exposed here only as
# shared family metadata, never evaluated by anything in this module.
RESUMPTION_MIN_BUCKETS = 1
# Expected trade horizon FROM `CONFIRMED` (§14) -- Stage 6/7/8 metadata;
# this module never computes or reads a horizon deadline itself.
EXPECTED_HORIZON = timedelta(hours=2)

_FIFTEEN_MIN = timedelta(minutes=TIMEFRAME_MINUTES["15m"])
# The FULL expected constituent 1m-bar count for a complete 15m
# ExchangeFeatureVector bucket (§11) -- canonical, not a magic second
# value: a 15m bucket is exactly 15 one-minute bars by construction.
_FULL_15M_BAR_COUNT = TIMEFRAME_MINUTES["15m"]


# ---- shared numeric validation (small local private copy, matching the
# established codebase precedent of not cross-module-importing another
# module's private helpers -- see setup_common.py's own docstring) ---------
def _is_finite(value: float) -> bool:
    return value == value and value not in (float("inf"), float("-inf"))  # NaN != NaN


def _validate_finite_numeric(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise V2TrendPullbackError(
            f"{name} must be a real number, got {type(value).__name__}: {value!r}")
    v = float(value)
    if not _is_finite(v):
        raise V2TrendPullbackError(f"{name} must be finite, got {value!r}")
    return v


def _validate_nonnegative_finite(value: Any, name: str) -> float:
    v = _validate_finite_numeric(value, name)
    if v < 0.0:
        raise V2TrendPullbackError(f"{name} must be >= 0.0, got {v!r}")
    return v


def _validate_positive_finite(value: Any, name: str) -> float:
    v = _validate_finite_numeric(value, name)
    if not (v > 0.0):
        raise V2TrendPullbackError(f"{name} must be > 0, got {v!r}")
    return v


def _validate_utc_whole_minute(value: Any, name: str) -> datetime:
    if type(value) is not datetime:
        raise V2TrendPullbackError(f"{name} must be a datetime, got {type(value).__name__}")
    if value.tzinfo is None or value.utcoffset() is None:
        raise V2TrendPullbackError(f"{name} must be timezone-aware")
    if value.utcoffset() != timedelta(0):
        raise V2TrendPullbackError(f"{name} must be UTC (offset 0), got {value.utcoffset()}")
    if value.second != 0 or value.microsecond != 0:
        raise V2TrendPullbackError(f"{name} must be a whole minute (no seconds/microseconds)")
    return value


def _trend_pullback_setup_strength(
    retracement_pct: float, range_proxy_pct_value: float,
) -> Optional[float]:
    """§8.1's exact `setup_strength` formula: `1 - (retracement_pct /
    (PULLBACK_MAX_MULT * range_proxy_pct))`, clamped to `[0.0, 1.0]`,
    using the candidate's own already-computed canonical
    `retracement_pct`/`range_proxy_pct` -- never a reload/recompute from
    historical rows.

    The formation band check (`min_retracement <= retracement_pct <=
    max_retracement`, both derived from the SAME `range_proxy_pct_value`)
    guarantees `retracement_pct == 0.0` whenever `range_proxy_pct_value ==
    0.0` (a genuinely flat reference window collapses the band to the
    single point `0`) -- but the frozen contract does NOT define a value
    for this `0/0` case, and §8 explicitly allows a scoring component to
    be `[0,1]` OR UNAVAILABLE. This is therefore genuinely UNAVAILABLE
    (`None`), never a fabricated `1.0` (or any other invented numeric
    confidence) -- the setup ITSELF (the structural qualification) and
    this scoring component are separate facts; a `None` here does not by
    itself reject the candidate."""
    denom = PULLBACK_MAX_MULT * range_proxy_pct_value
    if denom == 0.0:
        return None
    raw = 1.0 - (retracement_pct / denom)
    return min(1.0, max(0.0, raw))


def _validate_row_container(rows: Any, name: str) -> Any:
    """Reject a top-level rows argument that is not a legitimate
    iterable-of-rows container -- `None`, or a bare `str`/`bytes`/
    `bytearray` (iterable character-by-character, never a row sequence)."""
    if rows is None or isinstance(rows, (str, bytes, bytearray)):
        raise V2TrendPullbackError(
            f"{name} must be a Sequence of Mapping rows (not None/str/bytes), got "
            f"{type(rows).__name__}")
    try:
        iter(rows)
    except TypeError as exc:
        raise V2TrendPullbackError(
            f"{name} must be an iterable Sequence of Mapping rows, got "
            f"{type(rows).__name__}: {exc}") from exc
    return rows


def _require_fields(row: Any, required_fields: "tuple[str, ...]", label: str) -> None:
    if not isinstance(row, _AbcMapping):
        raise V2TrendPullbackError(
            f"{label} must be a Mapping, got {type(row).__name__}: {row!r}")
    missing = [f for f in required_fields if f not in row]
    if missing:
        raise V2TrendPullbackError(f"{label} is missing required field(s) {missing!r}")


# ============================================================================
# input value object -- bare container, no self-validation (see module
# docstring's "V2TrendPullbackInputs is a bare container" section).
# ============================================================================
@dataclass(frozen=True)
class V2TrendPullbackInputs:
    """Everything `detect_trend_pullback()` needs for ONE `context.T`:
    the already-computed `V2ContextSnapshot`, the exact `LOOKBACK_15M=48`
    reference 15m window (`reference_15m_rows`), the exact `RANGE_PROXY_N
    =14` consensus 15m window (`range_proxy_15m_rows`), and the single
    `exchange_instruments` row for `protection_buffer()`'s `tick_size`
    input (`instrument`, `None` if absent). No DB handle, no pool, no
    reader is retained here -- rows are plain, already-detached `Mapping`s
    (as `storage/v2_setup_readers.py`'s readers already return them).
    `detect_trend_pullback()` never mutates any row it reads from this
    object."""
    context: V2ContextSnapshot
    reference_15m_rows: "tuple[Mapping, ...]"
    range_proxy_15m_rows: "tuple[Mapping, ...]"
    instrument: Optional[Mapping]


# ============================================================================
# result value object -- public Stage 5 API, self-validates on ANY direct
# construction (mirrors V2RegimeResult/V2BiasResult/V2ContextSnapshot/
# V2ExtremeAnchor's established frozen-dataclass __post_init__ pattern).
# ============================================================================
@dataclass(frozen=True)
class V2TrendPullbackCandidate:
    """One deterministic `TREND_PULLBACK` qualification at `T` (§7.1). A
    QUALIFICATION only -- see module docstring's Stage 5/6 boundary
    section for everything this is deliberately NOT: not an episode, not
    an `EARLY_SIGNAL`, not confirmed, not scored, not persisted.

    `structural_anchor` (the `bucket_ts` `episode_logical_key`, §12, will
    later use) is intentionally exposed only as a read-only property
    derived from `trend_leg_extreme.bucket_ts` -- never a second,
    independently-settable field that could silently disagree with it.

    **`decision_tick_size` (V2-H2c, tech-lead review 4990482334, finding
    5).** `docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §12.5a freezes that
    every Stage 5 candidate depending on `tick_size` MUST carry the actual
    validated decision-time `tick_size` BY VALUE in its own output, so a
    future Stage 6 never re-reads today's instrument metadata for episode
    creation identity. `decision_tick_size` is EXACTLY the as-of instrument
    metadata value (`inputs.instrument["tick_size"]`, resolved as-of
    `context.T` by the caller) this candidate's own `protection_buffer`
    was computed from -- Stage 5 owns and exposes it; Stage 6 will later
    freeze `candidate.decision_tick_size` into the episode's OWN
    `creation_identity_tick_size` (§12.5a) once an `EARLY_SIGNAL` is
    actually created -- `decision_tick_size` itself is NOT
    `creation_identity_tick_size` (that is specifically the Stage-6
    episode-creation supporting fact; this is the Stage-5 candidate's own
    decision-time input fact, upstream of any episode existing yet).

    `setup_strength`/`data_confidence` (§8/§9) are canonical creation-time
    scoring/quality facts, carried BY VALUE from this candidate's own
    already-computed `retracement_pct`/`range_proxy_pct` and the
    setup-formation 15m bucket's own `price_structure` family confidence
    -- never recomputed by a later stage. `setup_strength` is `Optional`:
    genuinely UNAVAILABLE (`None`), never a fabricated numeric value,
    whenever `PULLBACK_MAX_MULT * range_proxy_pct == 0.0` (the frozen
    formula defines no value for that degenerate case; §8 explicitly
    allows a scoring component to be `[0,1]` OR UNAVAILABLE) -- this does
    not by itself reject the candidate, since the setup's own structural
    qualification and this scoring component are separate facts.
    `__post_init__` cross-checks both against the candidate's own
    canonical fields (never silently trusting a directly-constructed
    value, including the None-vs-numeric branch itself), and enforces
    the EXACT §7.1
    entry-zone/invalidation geometry (not merely `lower <= upper`/
    "invalidation is on the correct side") -- a directly-constructed
    candidate whose fields are internally inconsistent with the
    detector's own arithmetic fails closed."""
    T: datetime
    direction: str
    bucket_15m: datetime
    bucket_5m_at_T: datetime
    trend_leg_extreme: V2ExtremeAnchor
    current_close: float
    retracement_pct: float
    range_proxy_pct: float
    pullback_extreme: float
    protection_buffer: float
    decision_tick_size: float
    entry_zone_lower: float
    entry_zone_upper: float
    invalidation_price: float
    setup_strength: Optional[float]
    data_confidence: float

    def __post_init__(self) -> None:
        if self.direction not in DIRECTIONS:
            raise V2TrendPullbackError(
                f"direction must be one of {DIRECTIONS}, got {self.direction!r}")

        t = _validate_utc_whole_minute(self.T, "T")
        b15 = selected_bucket("15m", t)
        if b15 + _FIFTEEN_MIN != t:
            raise V2TrendPullbackError(
                f"T={t.isoformat()} is not a legal 15m TREND_PULLBACK formation boundary")
        if self.bucket_15m != b15:
            raise V2TrendPullbackError(
                f"bucket_15m does not match selected_bucket('15m', T) -- expected "
                f"{b15!r}, got {self.bucket_15m!r}")
        b5 = selected_bucket("5m", t)
        if self.bucket_5m_at_T != b5:
            raise V2TrendPullbackError(
                f"bucket_5m_at_T does not match selected_bucket('5m', T) -- expected "
                f"{b5!r}, got {self.bucket_5m_at_T!r}")

        if not isinstance(self.trend_leg_extreme, V2ExtremeAnchor):
            raise V2TrendPullbackError(
                f"trend_leg_extreme must be a V2ExtremeAnchor, got "
                f"{type(self.trend_leg_extreme).__name__}")
        lookback_start = self.bucket_15m - (LOOKBACK_15M - 1) * _FIFTEEN_MIN
        anchor_ts = self.trend_leg_extreme.bucket_ts
        if not (lookback_start <= anchor_ts <= self.bucket_15m):
            raise V2TrendPullbackError(
                f"trend_leg_extreme.bucket_ts {anchor_ts!r} is outside the exact "
                f"{LOOKBACK_15M}-bucket lookback [{lookback_start!r}, {self.bucket_15m!r}]")

        current_close = _validate_positive_finite(self.current_close, "current_close")
        pullback_extreme = _validate_positive_finite(self.pullback_extreme, "pullback_extreme")
        buf = _validate_positive_finite(self.protection_buffer, "protection_buffer")
        decision_tick = _validate_positive_finite(self.decision_tick_size, "decision_tick_size")
        # (V2-H2c, finding 5) Cheap, exact, deterministic cross-check --
        # protection_buffer() is max(MIN_TICK_BUFFER_TICKS * tick_size, ...),
        # so it can NEVER be smaller than the tick floor computed from THIS
        # candidate's own decision_tick_size. Never duplicates the detector's
        # own volatility-term arithmetic (which would require range_proxy_pct
        # domain knowledge this __post_init__ has no business re-deriving).
        if buf < MIN_TICK_BUFFER_TICKS * decision_tick:
            raise V2TrendPullbackError(
                f"protection_buffer ({buf!r}) is inconsistent with decision_tick_size "
                f"({decision_tick!r}) -- protection_buffer() can never be smaller than "
                f"MIN_TICK_BUFFER_TICKS * decision_tick_size "
                f"({MIN_TICK_BUFFER_TICKS * decision_tick!r})")
        entry_lower = _validate_positive_finite(self.entry_zone_lower, "entry_zone_lower")
        entry_upper = _validate_positive_finite(self.entry_zone_upper, "entry_zone_upper")
        invalidation_price = _validate_positive_finite(
            self.invalidation_price, "invalidation_price")
        retracement_pct = _validate_nonnegative_finite(self.retracement_pct, "retracement_pct")
        proxy = _validate_nonnegative_finite(self.range_proxy_pct, "range_proxy_pct")

        if not (entry_lower <= entry_upper):
            raise V2TrendPullbackError(
                f"entry_zone_lower ({entry_lower!r}) must be <= entry_zone_upper "
                f"({entry_upper!r})")

        # §7.1/§10 exact entry-zone/invalidation geometry -- NOT merely
        # "lower <= upper"/"invalidation is on the correct side": every
        # field must equal the detector's own exact arithmetic bit-for-bit
        # (deterministic numeric comparison, no invented tolerance).
        if self.direction == LONG:
            if entry_lower != pullback_extreme:
                raise V2TrendPullbackError(
                    "LONG entry_zone_lower must exactly equal pullback_extreme -- expected "
                    f"{pullback_extreme!r}, got {entry_lower!r}")
            if entry_upper != current_close:
                raise V2TrendPullbackError(
                    "LONG entry_zone_upper must exactly equal current_close -- expected "
                    f"{current_close!r}, got {entry_upper!r}")
            expected_invalidation = pullback_extreme - buf
            if invalidation_price != expected_invalidation:
                raise V2TrendPullbackError(
                    "LONG invalidation_price is inconsistent with pullback_extreme/"
                    f"protection_buffer -- expected {expected_invalidation!r}, got "
                    f"{invalidation_price!r}")
            if not (invalidation_price < pullback_extreme):
                raise V2TrendPullbackError(
                    "LONG invalidation_price must be < pullback_extreme, got "
                    f"invalidation_price={invalidation_price!r}, "
                    f"pullback_extreme={pullback_extreme!r}")
        else:
            if entry_lower != current_close:
                raise V2TrendPullbackError(
                    "SHORT entry_zone_lower must exactly equal current_close -- expected "
                    f"{current_close!r}, got {entry_lower!r}")
            if entry_upper != pullback_extreme:
                raise V2TrendPullbackError(
                    "SHORT entry_zone_upper must exactly equal pullback_extreme -- expected "
                    f"{pullback_extreme!r}, got {entry_upper!r}")
            expected_invalidation = pullback_extreme + buf
            if invalidation_price != expected_invalidation:
                raise V2TrendPullbackError(
                    "SHORT invalidation_price is inconsistent with pullback_extreme/"
                    f"protection_buffer -- expected {expected_invalidation!r}, got "
                    f"{invalidation_price!r}")
            if not (invalidation_price > pullback_extreme):
                raise V2TrendPullbackError(
                    "SHORT invalidation_price must be > pullback_extreme, got "
                    f"invalidation_price={invalidation_price!r}, "
                    f"pullback_extreme={pullback_extreme!r}")

        # §8.1/§9 setup_strength/data_confidence -- canonical creation-time
        # scoring/quality facts, cross-checked against this candidate's own
        # already-computed retracement_pct/range_proxy_pct (setup_strength).
        # setup_strength is genuinely UNAVAILABLE (`None`) whenever
        # PULLBACK_MAX_MULT * range_proxy_pct == 0.0 (the frozen contract
        # does not define a value for that 0/0 case, and §8 explicitly
        # allows a scoring component to be [0,1] OR UNAVAILABLE) -- never
        # a fabricated numeric value in that case. Cross-checked exactly
        # against `_trend_pullback_setup_strength()`'s own real formula
        # either way, so a directly-constructed candidate whose
        # setup_strength disagrees with the denominator-zero-ness of its
        # own retracement_pct/range_proxy_pct fails closed in BOTH
        # directions (a numeric value when it must be None; a None when a
        # real numeric value is expected).
        expected_setup_strength = _trend_pullback_setup_strength(retracement_pct, proxy)
        if expected_setup_strength is None:
            if self.setup_strength is not None:
                raise V2TrendPullbackError(
                    "setup_strength must be None (UNAVAILABLE) when "
                    "PULLBACK_MAX_MULT * range_proxy_pct == 0.0 -- the frozen formula defines "
                    f"no numeric value for this case, got {self.setup_strength!r}")
        else:
            if self.setup_strength is None:
                raise V2TrendPullbackError(
                    "setup_strength must be a numeric value (not None) when "
                    "PULLBACK_MAX_MULT * range_proxy_pct != 0.0")
            setup_strength = _validate_finite_numeric(self.setup_strength, "setup_strength")
            if not (0.0 <= setup_strength <= 1.0):
                raise V2TrendPullbackError(
                    f"setup_strength must be within [0.0, 1.0], got {setup_strength!r}")
            if setup_strength != expected_setup_strength:
                raise V2TrendPullbackError(
                    "setup_strength is inconsistent with retracement_pct/range_proxy_pct -- "
                    f"expected {expected_setup_strength!r}, got {setup_strength!r}")

        data_confidence = _validate_finite_numeric(self.data_confidence, "data_confidence")
        if not (0.0 <= data_confidence <= 1.0):
            raise V2TrendPullbackError(
                f"data_confidence must be within [0.0, 1.0], got {data_confidence!r}")

    @property
    def structural_anchor(self) -> datetime:
        """§12's `episode_logical_key` structural anchor for `TREND_PULLBACK`
        -- always exactly `trend_leg_extreme.bucket_ts`, never an
        independently stored/settable value."""
        return self.trend_leg_extreme.bucket_ts


# ============================================================================
# the pure detector
# ============================================================================
_REFERENCE_IDENTITY_FIELDS = (
    "exchange", "symbol", "market_type", "timeframe", "calculation_version",
    "feature_schema_version", "bucket_ts",
)
_REFERENCE_GATE_FIELDS = ("is_usable", "has_gap", "bars_present", "bars_expected", "close_price")
_REFERENCE_REQUIRED_FIELDS = _REFERENCE_IDENTITY_FIELDS + _REFERENCE_GATE_FIELDS

_PROXY_IDENTITY_FIELDS = (
    "symbol", "market_type", "timeframe", "calculation_version", "feature_schema_version",
    "bucket_ts",
)
_INSTRUMENT_REQUIRED_FIELDS = ("exchange", "symbol", "market_type", "tick_size")


def _validate_reference_row(
    row: Any, *, context: V2ContextSnapshot, expected_set: frozenset,
) -> "tuple[datetime, Optional[float]]":
    """Validate one PRESENT reference 15m row's exact identity (§16) and
    apply §11's exact reference-vector usability gate (§17), reused
    unchanged. Returns `(bucket_ts, close_price_or_None)` -- `None` for a
    bucket that legitimately fails the usability gate (excluded from the
    exact-48 completeness count downstream, never an error), while every
    PRESENT numeric/count/bool field is still validated for corruption
    regardless of whether the gate would fail anyway (corruption
    precedence, mirrors #36-#39's posture)."""
    _require_fields(row, _REFERENCE_REQUIRED_FIELDS, "reference 15m row")

    if row["exchange"] != V2_REFERENCE_EXCHANGE:
        raise V2TrendPullbackError(
            f"reference row exchange must be {V2_REFERENCE_EXCHANGE!r}, got "
            f"{row['exchange']!r}")
    if row["symbol"] != context.symbol:
        raise V2TrendPullbackError(
            f"reference row symbol must be {context.symbol!r}, got {row['symbol']!r}")
    if row["market_type"] != context.market_type:
        raise V2TrendPullbackError(
            f"reference row market_type must be {context.market_type!r}, got "
            f"{row['market_type']!r}")
    if row["timeframe"] != "15m":
        raise V2TrendPullbackError(f"reference row timeframe must be '15m', got {row['timeframe']!r}")
    if row["calculation_version"] != context.calculation_version:
        raise V2TrendPullbackError(
            f"reference row calculation_version must be {context.calculation_version!r}, "
            f"got {row['calculation_version']!r}")
    if row["feature_schema_version"] != context.feature_schema_version:
        raise V2TrendPullbackError(
            f"reference row feature_schema_version must be {context.feature_schema_version!r}, "
            f"got {row['feature_schema_version']!r}")

    bucket_ts = _validate_utc_whole_minute(row["bucket_ts"], "reference row bucket_ts")
    if bucket_ts not in expected_set:
        raise V2TrendPullbackError(
            f"reference row bucket_ts {bucket_ts.isoformat()} is outside the expected "
            f"{LOOKBACK_15M}-bucket 15m lookback")

    is_usable = row["is_usable"]
    if not isinstance(is_usable, bool):
        raise V2TrendPullbackError(
            f"reference row is_usable must be a bool, got {type(is_usable).__name__}")
    has_gap = row["has_gap"]
    if not isinstance(has_gap, bool):
        raise V2TrendPullbackError(
            f"reference row has_gap must be a bool, got {type(has_gap).__name__}")

    bars_present = row["bars_present"]
    bars_expected = row["bars_expected"]
    for name, value in (("bars_present", bars_present), ("bars_expected", bars_expected)):
        if isinstance(value, bool) or not isinstance(value, int):
            raise V2TrendPullbackError(
                f"reference row {name} must be an int, got {type(value).__name__}")
    # §11: a complete 15m ExchangeFeatureVector bucket has EXACTLY
    # _FULL_15M_BAR_COUNT=15 expected constituent 1m bars -- any other
    # bars_expected is corrupted/impossible identity metadata (not
    # ordinary "one bar missing"), so it raises rather than merely
    # failing the usability gate.
    if bars_expected != _FULL_15M_BAR_COUNT:
        raise V2TrendPullbackError(
            f"reference row bars_expected must be exactly {_FULL_15M_BAR_COUNT} for a "
            f"15m bucket, got {bars_expected!r}")
    if bars_present < 0:
        raise V2TrendPullbackError(
            f"reference row bars_present must be >= 0, got {bars_present!r}")
    if bars_present > bars_expected:
        raise V2TrendPullbackError(
            f"reference row bars_present ({bars_present!r}) must not exceed bars_expected "
            f"({bars_expected!r})")

    close_price = row["close_price"]
    if close_price is not None:
        close_price = _validate_positive_finite(close_price, "reference row close_price")

    gate_passes = (
        is_usable is True and has_gap is False
        and bars_present == bars_expected and close_price is not None
    )
    return bucket_ts, (close_price if gate_passes else None)


def _validate_proxy_row_identity(row: Any, *, context: V2ContextSnapshot) -> datetime:
    """Defensively re-validate a PRESENT range-proxy 15m row's identity
    (§18) BEFORE it ever reaches `range_proxy_pct()` -- exact bucket
    GRID/completeness/value validation remains that shared primitive's own
    job, never duplicated here; this only checks that PRESENT `bucket_ts`
    is a well-formed aware/UTC/whole-minute `datetime` (never normalized/
    floored), so the caller can also use it to locate the current B15 row
    for the §6.2/§6.3 setup-quality gate without a second storage read.
    Returns the validated `bucket_ts`."""
    _require_fields(row, _PROXY_IDENTITY_FIELDS, "range-proxy 15m row")
    if row["symbol"] != context.symbol:
        raise V2TrendPullbackError(
            f"range-proxy row symbol must be {context.symbol!r}, got {row['symbol']!r}")
    if row["market_type"] != context.market_type:
        raise V2TrendPullbackError(
            f"range-proxy row market_type must be {context.market_type!r}, got "
            f"{row['market_type']!r}")
    if row["timeframe"] != "15m":
        raise V2TrendPullbackError(
            f"range-proxy row timeframe must be '15m', got {row['timeframe']!r}")
    if row["calculation_version"] != context.calculation_version:
        raise V2TrendPullbackError(
            f"range-proxy row calculation_version must be {context.calculation_version!r}, "
            f"got {row['calculation_version']!r}")
    if row["feature_schema_version"] != context.feature_schema_version:
        raise V2TrendPullbackError(
            f"range-proxy row feature_schema_version must be "
            f"{context.feature_schema_version!r}, got {row['feature_schema_version']!r}")
    return _validate_utc_whole_minute(row["bucket_ts"], "range-proxy row bucket_ts")


def _validate_setup_quality_row(row: Mapping) -> "Optional[tuple[float, float]]":
    """§6.3a: the current-B15 setup-quality gate is scoped to the
    `price_structure` FAMILY alone -- sourced from the row's own
    `coverage_by_metric`/`data_confidence_by_metric` per-family maps,
    never the global `min_coverage_ratio`/`consensus_confidence` rollup a
    family this detector does not consume (e.g. `liquidations`) could
    otherwise drag down. A malformed PRESENT per-family map raises
    `V2TrendPullbackError` (chained from `V2FamilyQualityError`), never
    silently downgraded to ordinary unavailability. Returns `(coverage,
    confidence)` if both are present and valid, or `None` if either is
    legitimately unavailable."""
    try:
        price_family = family_quality(row, family="price_structure")
    except V2FamilyQualityError as exc:
        raise V2TrendPullbackError(f"malformed price_structure family quality: {exc}") from exc
    if price_family.coverage_ratio is None or price_family.confidence is None:
        return None
    return price_family.coverage_ratio, price_family.confidence


def detect_trend_pullback(inputs: V2TrendPullbackInputs) -> Optional[V2TrendPullbackCandidate]:
    """Deterministically qualify (or not) `TREND_PULLBACK` at `inputs.
    context.T` (see module docstring for the complete formula/precondition
    set and the exhaustive Stage 5/6 boundary this respects). Pure,
    synchronous; the same `inputs` always yields the same result.

    Returns `None` for every legitimate non-qualification (see module
    docstring's `V2TrendPullbackError` list for the full inventory: not a
    15m formation boundary, context precondition not met, incomplete
    required 48-bucket history, an unavailable `RANGE_PROXY_pct`, degraded
    or unavailable current-B15 consensus quality (§6.2/§6.3), a
    retracement outside `[0.5,3.0] * RANGE_PROXY_pct`, or unavailable
    instrument/tick metadata). Raises `V2TrendPullbackError` for malformed
    PRESENT input of any kind."""
    if not isinstance(inputs, V2TrendPullbackInputs):
        raise V2TrendPullbackError(
            f"inputs must be a V2TrendPullbackInputs, got {type(inputs).__name__}")
    context = inputs.context
    if not isinstance(context, V2ContextSnapshot):
        raise V2TrendPullbackError(
            f"inputs.context must be a V2ContextSnapshot, got {type(context).__name__}")

    # ---- §7 formation clock: 15m boundaries only, no flooring ----------
    T = context.T
    B15 = selected_bucket("15m", T)
    B5_at_T = selected_bucket("5m", T)
    if B15 + _FIFTEEN_MIN != T:
        return None  # legal 5m boundary, but not a 15m formation boundary

    # ---- §7.1 strict context precondition (NOT directional_context_gate) ---
    regime = context.regime_4h.regime
    bias = context.bias_1h.bias
    if regime == BULLISH_TRENDING and bias == BULLISH:
        direction = LONG
    elif regime == BEARISH_TRENDING and bias == BEARISH:
        direction = SHORT
    else:
        return None

    # ---- §7.1/§16/§17 exact 48-bucket reference-close history ----------
    reference_rows = _validate_row_container(inputs.reference_15m_rows, "reference_15m_rows")
    expected_grid = tuple(
        B15 - (LOOKBACK_15M - 1 - i) * _FIFTEEN_MIN for i in range(LOOKBACK_15M))
    expected_set = frozenset(expected_grid)

    closes_by_bucket: "dict[datetime, float]" = {}
    seen_bucket_ts: set = set()
    for row in reference_rows:
        bucket_ts, close = _validate_reference_row(
            row, context=context, expected_set=expected_set)
        if bucket_ts in seen_bucket_ts:
            raise V2TrendPullbackError(
                f"duplicate reference row for bucket_ts {bucket_ts.isoformat()}")
        seen_bucket_ts.add(bucket_ts)
        if close is not None:
            closes_by_bucket[bucket_ts] = close

    if len(closes_by_bucket) != LOOKBACK_15M:
        return None  # one or more expected buckets legitimately missing/unusable

    current_close = closes_by_bucket[B15]

    # ---- §7.0c trend-leg extreme, via the shared tie-break primitive ----
    candidates = tuple({"bucket_ts": ts, "value": closes_by_bucket[ts]} for ts in expected_grid)
    mode = "max" if direction == LONG else "min"
    try:
        anchor = select_extreme_anchor(candidates, mode=mode)
    except V2SetupFoundationError as exc:
        raise V2TrendPullbackError(f"select_extreme_anchor failed: {exc}") from exc
    if anchor is None:
        raise V2TrendPullbackError(
            "select_extreme_anchor unexpectedly returned None for a non-empty candidate set")

    trend_leg_value = anchor.value
    if direction == LONG:
        retracement_pct = (trend_leg_value - current_close) / trend_leg_value * 100.0
    else:
        retracement_pct = (current_close - trend_leg_value) / trend_leg_value * 100.0
    if retracement_pct < 0:
        raise V2TrendPullbackError(
            f"impossible negative retracement_pct={retracement_pct!r} from trend_leg_value="
            f"{trend_leg_value!r}, current_close={current_close!r}")

    # ---- §7.1/§18 RANGE_PROXY_pct(15m,14,B15), via the shared primitive -
    proxy_rows = _validate_row_container(inputs.range_proxy_15m_rows, "range_proxy_15m_rows")
    quality_row_by_bucket_ts: "dict[datetime, Mapping]" = {}
    for row in proxy_rows:
        row_bucket_ts = _validate_proxy_row_identity(row, context=context)
        quality_row_by_bucket_ts.setdefault(row_bucket_ts, row)

    # ---- §6.2/§6.3 setup-timeframe consensus quality gate, at the SAME
    # current B15 row range_proxy_pct's own window already carries -- no
    # fourth storage read. Validated BEFORE the range_proxy_pct() call so
    # a malformed PRESENT quality field is never masked by some OTHER,
    # unrelated historical RANGE_PROXY peer bucket happening to be
    # missing (corruption precedence). A B15 row that is entirely absent
    # is legitimate incompleteness -- range_proxy_pct() will itself
    # return None for the same reason below; no quality is fabricated
    # here for it.
    current_quality_row = quality_row_by_bucket_ts.get(B15)
    quality = (
        _validate_setup_quality_row(current_quality_row)
        if current_quality_row is not None else None)

    try:
        proxy = range_proxy_pct(proxy_rows, timeframe="15m", bucket_ts=B15)
    except V2SetupFoundationError as exc:
        raise V2TrendPullbackError(f"range_proxy_pct failed: {exc}") from exc
    if proxy is None:
        return None

    if quality is None:
        return None  # current B15 consensus quality legitimately unavailable
    current_coverage, current_confidence = quality
    if current_coverage < SETUP_MIN_COVERAGE or current_confidence < SETUP_MIN_CONFIDENCE:
        return None  # degraded current 15m consensus quality -- no candidate

    min_retracement = PULLBACK_MIN_MULT * proxy
    max_retracement = PULLBACK_MAX_MULT * proxy
    if not (min_retracement <= retracement_pct <= max_retracement):
        return None

    # ---- §23 pullback-extreme structural span: anchor -> B15 inclusive -
    span_bucket_ts = [ts for ts in expected_grid if ts >= anchor.bucket_ts]
    span_closes = [closes_by_bucket[ts] for ts in span_bucket_ts]
    pullback_extreme = min(span_closes) if direction == LONG else max(span_closes)

    # ---- §7/§11 tick_size (instrument metadata, identity-checked so no
    # foreign exchange/symbol/market_type instrument row can silently
    # influence this candidate's protection buffer) ----------------------
    instrument = inputs.instrument
    if instrument is None:
        return None  # no protection buffer can be constructed
    _require_fields(instrument, _INSTRUMENT_REQUIRED_FIELDS, "instrument row")
    if instrument["exchange"] != V2_REFERENCE_EXCHANGE:
        raise V2TrendPullbackError(
            f"instrument row exchange must be {V2_REFERENCE_EXCHANGE!r}, got "
            f"{instrument['exchange']!r}")
    if instrument["symbol"] != context.symbol:
        raise V2TrendPullbackError(
            f"instrument row symbol must be {context.symbol!r}, got {instrument['symbol']!r}")
    if instrument["market_type"] != context.market_type:
        raise V2TrendPullbackError(
            f"instrument row market_type must be {context.market_type!r}, got "
            f"{instrument['market_type']!r}")
    tick_size_raw = instrument["tick_size"]
    if tick_size_raw is None:
        return None  # tick_size genuinely unavailable
    tick_size = _validate_positive_finite(tick_size_raw, "instrument tick_size")

    # ---- §7 protection_buffer, via the shared primitive -----------------
    try:
        buffer = protection_buffer(
            reference_price=current_close, range_proxy_pct_value=proxy, tick_size=tick_size)
    except V2SetupFoundationError as exc:
        raise V2TrendPullbackError(f"protection_buffer failed: {exc}") from exc
    if buffer is None:
        return None  # should not normally occur once proxy is already available

    # ---- §9/§10 entry zone + structural invalidation --------------------
    if direction == LONG:
        invalidation_price = pullback_extreme - buffer
        entry_zone_lower = pullback_extreme
        entry_zone_upper = current_close
    else:
        invalidation_price = pullback_extreme + buffer
        entry_zone_lower = current_close
        entry_zone_upper = pullback_extreme
    if entry_zone_lower > entry_zone_upper:
        raise V2TrendPullbackError(
            f"entry_zone_lower ({entry_zone_lower!r}) exceeds entry_zone_upper "
            f"({entry_zone_upper!r})")

    # ---- §8.1/§9 setup_strength/data_confidence, canonical creation-time
    # scoring/quality facts carried BY VALUE on the candidate -- never
    # recomputed downstream. setup_strength reuses this candidate's own
    # already-computed retracement_pct/range_proxy_pct (no reload/
    # recompute from historical rows); data_confidence is the SAME
    # price_structure family confidence already read for the current-B15
    # quality gate above (current_confidence), never a second lookup.
    setup_strength = _trend_pullback_setup_strength(retracement_pct, proxy)
    data_confidence = current_confidence / 100.0

    return V2TrendPullbackCandidate(
        T=T,
        direction=direction,
        bucket_15m=B15,
        bucket_5m_at_T=B5_at_T,
        trend_leg_extreme=anchor,
        current_close=current_close,
        retracement_pct=retracement_pct,
        range_proxy_pct=proxy,
        pullback_extreme=pullback_extreme,
        protection_buffer=buffer,
        decision_tick_size=tick_size,
        entry_zone_lower=entry_zone_lower,
        entry_zone_upper=entry_zone_upper,
        setup_strength=setup_strength,
        data_confidence=data_confidence,
        invalidation_price=invalidation_price,
    )
