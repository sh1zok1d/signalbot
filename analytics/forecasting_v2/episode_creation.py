"""
Stage 6 Unit 2/5 — candidate routing, creation eligibility, family
precedence, and `EARLY_SIGNAL` creation
(`docs/FORECASTING_ROADMAP.md` §I stage 6 unit 2;
`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §7.4/§7.4.1/§7.4.2/§7.4.3,
§12.3/§12.4/§12.6/§12.7/§12.8/§12.11, §13.4, §3.1/§3.2/§3.3).

**What this module is.** The pure decision layer that turns
already-qualified Stage 5 candidates at ONE logical decision boundary `T`
into exactly one deterministic outcome per candidate:

    route to the existing active episode   (§12.3 case A / case B)
    suppressed                             (§12.6 / §12.8 / §7.4)
    accepted for new EARLY_SIGNAL creation (§7.4.2 winner)

and then builds the canonical creation event for each winner.

**What this module is NOT.** It never re-runs a Stage 5 detector, never
synthesizes a candidate a detector did not actually produce at `T`
(§7.4.2's cadence invariant), and never decides a lifecycle transition:
confirmation, false-break, expiry, weakening, recovery, structural
invalidation and completion are Stage 6 units 3-4, and the full §13.4
eight-step same-boundary coordinator is unit 5. It also never reads a
database or a clock — every fact it needs is passed in.

**The two §13.4 views are inputs, not something this module computes.**
§13.4 fixes two DIFFERENT views before creation eligibility runs:

    3a. surviving_active_set(T) -- the non-terminal episodes remaining
        AFTER that T's own lifecycle transitions. Used ONLY for same-slot
        ACTIVE occupancy (§12.6).
    3b. per-slot terminal/cooldown state as of T -- each slot's most
        recent terminal episode and its T_terminal, INCLUDING one that
        became terminal in step 2 of this same T. Used ONLY for cooldown
        eligibility (§12.8).

They are not interchangeable, and neither can be derived from the other:
a slot whose sole occupant became terminal at this very `T` is
simultaneously absent from 3a AND inside its just-started cooldown per 3b.
Computing 3a requires applying unit 3/4 transitions, which this unit
deliberately does not implement — so both views arrive as explicit
arguments (`V2SlotOccupancyView`, `V2SlotCooldownView`) and unit 5 will
compose them in the frozen order.

**Suppressed is never queued (§12.7).** Every suppression outcome here is
an ephemeral decision result. Nothing is stored as a pending candidate,
nothing carries a retry-at, and no suppressed candidate ever becomes an
episode later merely because its blocker cleared — creation always
requires a NEW independently-qualified Stage 5 candidate at a later `T`.

**Classification is not event necessity (§12.11).** Case A/B routing
answers "which episode does this candidate belong to", never "does this
boundary require a persisted event". This module therefore builds events
ONLY for §7.4.2 creation winners. A/B routing and every suppression are
pure decision results with no `V2EpisodeEvent` at all.

Pure only: no DB, network, filesystem, clock, `uuid`, or `random` access.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from types import MappingProxyType
from typing import Any, Mapping, Optional, Sequence

from analytics.forecasting_v2._validation import (
    nonblank, one_of, validate_market_type, validate_symbol,
)
from analytics.forecasting_v2.alignment import V2AlignmentError, selected_bucket
from analytics.forecasting_v2.decision_provenance import V2DecisionProvenance
from analytics.forecasting_v2.decision_view import V2DecisionView
from analytics.forecasting_v2.episode_history import (
    ANCHOR_BUCKET_TS, TERMINAL_EPISODE_STATES,
    V2EpisodeCreationIdentity, V2EpisodeHistory, build_compression_breakout_anchor,
    build_confirmed_breakout_anchor, build_trend_pullback_anchor,
    canonical_decimal_text, normalize_price_to_tick,
)
from analytics.forecasting_v2.event_factory import build_v2_episode_event
from analytics.forecasting_v2.events import (
    COMPLETED, COMPRESSION_BREAKOUT, CONFIRMED_BREAKOUT, DIRECTIONS,
    EARLY_SIGNAL, EXPIRED, INVALIDATED, SETUP_FAMILIES, TREND_PULLBACK,
    V2EpisodeEvent,
)
from analytics.forecasting_v2.provenance import V2EventProvenance
from analytics.forecasting_v2.version_switch import (
    V2VersionSwitchState, assert_provenance_authorized_for_new_creation,
)

__all__ = [
    "V2EpisodeCreationError",
    "ANCHOR_DRIFT_BUCKETS", "FAMILY_PRECEDENCE", "TERMINAL_COOLDOWN_BUCKETS",
    "DECISION_BUCKET",
    "ROUTE_EXISTING_EXACT", "ROUTE_EXISTING_NON_MATERIAL",
    "SUPPRESSED_ACTIVE_SLOT", "SUPPRESSED_COOLDOWN", "SUPPRESSED_FAMILY_PRECEDENCE",
    "CREATE_EARLY_SIGNAL", "CANDIDATE_OUTCOMES",
    "MATCH_EXACT", "MATCH_NON_MATERIAL", "MATCH_MATERIAL", "MATCH_CLASSES",
    "CREATION_FACTS_KEY", "PRECEDENCE_CROSSREF_KEY",
    "V2CandidateFacts", "V2CandidateOutcome",
    "V2SlotOccupancyView", "V2SlotCooldownView", "V2SlotTerminalFact",
    "V2CreationAuthorization", "V2BoundaryRoutingResult",
    "candidate_facts_from_trend_pullback", "candidate_facts_from_compression_breakout",
    "candidate_facts_from_confirmed_breakout",
    "classify_candidate_against_active_episode",
    "evaluate_terminal_cooldown", "arbitrate_new_candidates",
    "build_early_signal_creation", "route_candidates_at_boundary",
    "read_creation_protection_buffer", "read_creation_facts",
]


class V2EpisodeCreationError(ValueError):
    """Malformed input to Stage 6 unit 2, or an impossible view of the
    world: an unsupported family/direction, a candidate whose scope
    disagrees with the episode it is being classified against, a slot
    occupied by more than one active episode, a terminal fact without a
    usable `T_terminal`, or a missing persisted creation supporting fact.
    Never silently coerced, never resolved by picking a winner."""


# ---- frozen thresholds (§12.4, §12.8, §7.4) ---------------------------------
# §12.4: "ANCHOR_DRIFT_BUCKETS = 4, kept frozen from the prior text".
ANCHOR_DRIFT_BUCKETS = 4

# §12.1/§12.4: both 15m-anchored families compare EXACT integer bucket counts.
_ANCHOR_BUCKET_WIDTH = timedelta(minutes=15)

# The V2 decision grid (§12.8's cooldown is counted in CLOSED 5m buckets).
DECISION_BUCKET = timedelta(minutes=5)

# §12.8's frozen table, in 5m buckets:
#   INVALIDATED -> 3 closed 5m buckets (15 min)
#   EXPIRED / COMPLETED -> 1 closed 5m bucket (5 min)
TERMINAL_COOLDOWN_BUCKETS = MappingProxyType({
    INVALIDATED: 3,
    EXPIRED: 1,
    COMPLETED: 1,
})
assert set(TERMINAL_COOLDOWN_BUCKETS) == set(TERMINAL_EPISODE_STATES)

# §7.4: "COMPRESSION_BREAKOUT > CONFIRMED_BREAKOUT > TREND_PULLBACK",
# highest precedence first. Position in this tuple IS the precedence rank.
FAMILY_PRECEDENCE = (COMPRESSION_BREAKOUT, CONFIRMED_BREAKOUT, TREND_PULLBACK)
assert set(FAMILY_PRECEDENCE) == set(SETUP_FAMILIES)

# ---- per-candidate outcomes (§26: three suppression mechanisms stay apart) --
ROUTE_EXISTING_EXACT = "ROUTE_EXISTING_EXACT"                    # §12.3 case A
ROUTE_EXISTING_NON_MATERIAL = "ROUTE_EXISTING_NON_MATERIAL"      # §12.3 case B
SUPPRESSED_ACTIVE_SLOT = "SUPPRESSED_ACTIVE_SLOT"                # §12.3 case C / §12.6
SUPPRESSED_COOLDOWN = "SUPPRESSED_COOLDOWN"                      # §12.8
SUPPRESSED_FAMILY_PRECEDENCE = "SUPPRESSED_FAMILY_PRECEDENCE"    # §7.4.2
CREATE_EARLY_SIGNAL = "CREATE_EARLY_SIGNAL"                      # §7.4.2 winner
CANDIDATE_OUTCOMES = (
    ROUTE_EXISTING_EXACT, ROUTE_EXISTING_NON_MATERIAL,
    SUPPRESSED_ACTIVE_SLOT, SUPPRESSED_COOLDOWN, SUPPRESSED_FAMILY_PRECEDENCE,
    CREATE_EARLY_SIGNAL,
)

# ---- §12.3 classification classes ------------------------------------------
MATCH_EXACT = "EXACT"                 # case A
MATCH_NON_MATERIAL = "NON_MATERIAL"   # case B
MATCH_MATERIAL = "MATERIAL"           # case C
MATCH_CLASSES = (MATCH_EXACT, MATCH_NON_MATERIAL, MATCH_MATERIAL)

# ---- canonical creation-fact keys ------------------------------------------
# §12.5a's precedent: the contract freezes the required logical facts but
# leaves the physical JSON schema to implementation. Unit 2 owns the
# creation event, so it owns (and therefore must also enforce) this shape.
CREATION_FACTS_KEY = "creation_facts"
PRECEDENCE_CROSSREF_KEY = "family_precedence_suppressed"

_CF_T_DETECT = "t_detect"
_CF_ENTRY_ZONE_LOWER = "entry_zone_lower"
_CF_ENTRY_ZONE_UPPER = "entry_zone_upper"
_CF_INVALIDATION_PRICE = "invalidation_price"
_CF_PROTECTION_BUFFER = "protection_buffer"
_CF_DECISION_TICK_SIZE = "decision_tick_size"
_CF_SETUP_STRENGTH = "setup_strength"
_CF_DATA_CONFIDENCE = "data_confidence"
_CF_FAMILY_FACTS = "family_facts"


def _validate_decision_boundary_T(value: Any, name: str) -> datetime:
    """A legal V2 5m decision boundary, delegated to the same canonical
    `alignment.selected_bucket("5m", ...)` every other V2 module uses."""
    if not isinstance(value, datetime):
        raise V2EpisodeCreationError(f"{name} must be a datetime, got {type(value).__name__}")
    if value.tzinfo is None or value.utcoffset() is None:
        raise V2EpisodeCreationError(f"{name} must be timezone-aware, got naive {value!r}")
    if value.utcoffset() != timedelta(0):
        raise V2EpisodeCreationError(f"{name} must be UTC (offset 0), got {value!r}")
    try:
        selected_bucket("5m", value)
    except V2AlignmentError as exc:
        raise V2EpisodeCreationError(f"{name} is not a legal V2 5m decision boundary: {exc}") from exc
    return value


def _positive_finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise V2EpisodeCreationError(f"{name} must be a real number, got {type(value).__name__}")
    value = float(value)
    if value != value or value in (float("inf"), float("-inf")):
        raise V2EpisodeCreationError(f"{name} must be finite, got {value!r}")
    if value <= 0:
        raise V2EpisodeCreationError(f"{name} must be strictly positive, got {value!r}")
    return value


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise V2EpisodeCreationError(f"{name} must be a real number, got {type(value).__name__}")
    value = float(value)
    if value != value or value in (float("inf"), float("-inf")):
        raise V2EpisodeCreationError(f"{name} must be finite, got {value!r}")
    return value


# ============================================================================
# the Stage 5 candidate, as Unit 2 needs to see it
# ============================================================================
@dataclass(frozen=True)
class V2CandidateFacts:
    """One already-qualified Stage 5 candidate, projected into exactly the
    facts Unit 2's frozen rules consume.

    Deliberately a SEPARATE type from the three Stage 5 candidate
    dataclasses rather than duck-typing across them: the three families
    genuinely expose different structural anchors (a 15m bucket for two of
    them; a `(1h bucket, raw price)` pair for `CONFIRMED_BREAKOUT`), and a
    single explicit projection makes the family-specific handling total and
    reviewable. Build one with the `candidate_facts_from_*` adapters — this
    module never invents a candidate, and never recomputes a Stage 5 value
    (§7.4.2's cadence invariant: Unit 2 arbitrates only among the
    candidates a detector genuinely produced at `T`).

    `anchor_bucket` is the family's §12.1 structural anchor bucket: the 15m
    `trend_leg_extreme`/`compression_start_bucket` for the two 15m-anchored
    families, the 1h `level_anchor_bucket` for `CONFIRMED_BREAKOUT`.
    `raw_level_price` is populated for `CONFIRMED_BREAKOUT` only, at Stage
    5's full stored precision — §12.5's ordering constraint forbids
    normalizing before Stage 5's own extreme selection, so normalization
    happens strictly downstream, here."""
    symbol: str
    market_type: str
    direction: str
    setup_family: str
    T: datetime

    anchor_bucket: datetime
    raw_level_price: Optional[float]

    entry_zone_lower: float
    entry_zone_upper: float
    invalidation_price: float
    protection_buffer: float
    decision_tick_size: float

    setup_strength: Optional[float]
    data_confidence: Optional[float]

    family_facts: Mapping

    def __post_init__(self) -> None:
        validate_symbol(self.symbol, V2EpisodeCreationError)
        validate_market_type(self.market_type, V2EpisodeCreationError)
        one_of(self.direction, "direction", DIRECTIONS, V2EpisodeCreationError)
        one_of(self.setup_family, "setup_family", SETUP_FAMILIES, V2EpisodeCreationError)
        _validate_decision_boundary_T(self.T, "T")

        if not isinstance(self.anchor_bucket, datetime):
            raise V2EpisodeCreationError(
                f"anchor_bucket must be a datetime, got {type(self.anchor_bucket).__name__}")
        if self.setup_family == CONFIRMED_BREAKOUT:
            if self.raw_level_price is None:
                raise V2EpisodeCreationError(
                    "CONFIRMED_BREAKOUT candidate must carry raw_level_price (§12.1's anchor is "
                    "the (level_anchor_bucket, tick-normalized price) PAIR)")
            _positive_finite(self.raw_level_price, "raw_level_price")
        elif self.raw_level_price is not None:
            raise V2EpisodeCreationError(
                f"{self.setup_family} has a bucket-only structural anchor (§12.1); "
                "raw_level_price must be None")

        lower = _finite(self.entry_zone_lower, "entry_zone_lower")
        upper = _finite(self.entry_zone_upper, "entry_zone_upper")
        if lower > upper:
            raise V2EpisodeCreationError(
                f"entry_zone_lower ({lower}) must be <= entry_zone_upper ({upper}) (§9)")
        _finite(self.invalidation_price, "invalidation_price")
        _positive_finite(self.protection_buffer, "protection_buffer")
        _positive_finite(self.decision_tick_size, "decision_tick_size")
        for name in ("setup_strength", "data_confidence"):
            value = getattr(self, name)
            if value is not None:
                _finite(value, name)
        if not isinstance(self.family_facts, Mapping):
            raise V2EpisodeCreationError(
                f"family_facts must be a Mapping, got {type(self.family_facts).__name__}")
        object.__setattr__(self, "family_facts", MappingProxyType(dict(self.family_facts)))

    @property
    def slot(self) -> "tuple[str, str, str, str]":
        """§12.3's frozen `slot = (symbol, market_type, direction,
        setup_family)` — deliberately WITHOUT `structural_anchor`,
        `episode_id`, `run_kind` or `run_id`."""
        return (self.symbol, self.market_type, self.direction, self.setup_family)

    @property
    def region(self) -> "tuple[float, float]":
        """§7.4.1's structural region: exactly the closed interval
        `[entry_zone_lower, entry_zone_upper]` — "nothing else"."""
        return (self.entry_zone_lower, self.entry_zone_upper)


def _family_facts(**kw) -> Mapping:
    return MappingProxyType({k: v for k, v in kw.items() if v is not None})


def candidate_facts_from_trend_pullback(candidate) -> V2CandidateFacts:
    """Project a Stage 5 `V2TrendPullbackCandidate`. The §12.1 anchor is
    `trend_leg_extreme.bucket_ts`, exactly as
    `trend_pullback.py::structural_anchor` already exposes it."""
    return V2CandidateFacts(
        symbol=_symbol_of(candidate), market_type=_market_type_of(candidate),
        direction=candidate.direction, setup_family=TREND_PULLBACK, T=candidate.T,
        anchor_bucket=candidate.structural_anchor, raw_level_price=None,
        entry_zone_lower=candidate.entry_zone_lower,
        entry_zone_upper=candidate.entry_zone_upper,
        invalidation_price=candidate.invalidation_price,
        protection_buffer=candidate.protection_buffer,
        decision_tick_size=candidate.decision_tick_size,
        setup_strength=candidate.setup_strength,
        data_confidence=candidate.data_confidence,
        family_facts=_family_facts(
            bucket_15m=candidate.bucket_15m.isoformat(),
            trend_leg_extreme_bucket_ts=candidate.trend_leg_extreme.bucket_ts.isoformat(),
            trend_leg_extreme_price=candidate.trend_leg_extreme.price,
            pullback_extreme=candidate.pullback_extreme,
            retracement_pct=candidate.retracement_pct,
            range_proxy_pct=candidate.range_proxy_pct,
        ),
    )


def candidate_facts_from_compression_breakout(candidate) -> V2CandidateFacts:
    """Project a Stage 5 `V2CompressionBreakoutCandidate`. The §12.1 anchor
    is `compression_start_bucket`."""
    return V2CandidateFacts(
        symbol=_symbol_of(candidate), market_type=_market_type_of(candidate),
        direction=candidate.direction, setup_family=COMPRESSION_BREAKOUT, T=candidate.T,
        anchor_bucket=candidate.structural_anchor, raw_level_price=None,
        entry_zone_lower=candidate.entry_zone_lower,
        entry_zone_upper=candidate.entry_zone_upper,
        invalidation_price=candidate.invalidation_price,
        protection_buffer=candidate.protection_buffer,
        decision_tick_size=candidate.decision_tick_size,
        setup_strength=candidate.setup_strength,
        data_confidence=candidate.data_confidence,
        family_facts=_family_facts(
            compression_start_bucket=candidate.compression_start_bucket.isoformat(),
            compression_end_bucket=candidate.compression_end_bucket.isoformat(),
            compression_length=candidate.compression_length,
            range_low=candidate.range_low, range_high=candidate.range_high,
            range_proxy_pct=candidate.range_proxy_pct,
            breakout_close=candidate.breakout_close,
            previous_5m_close=candidate.previous_5m_close,
        ),
    )


def candidate_facts_from_confirmed_breakout(candidate) -> V2CandidateFacts:
    """Project a Stage 5 `V2ConfirmedBreakoutCandidate`. The §12.1 anchor
    is the PAIR `(level_anchor_bucket, tick-normalized price)`; Stage 5's
    `level_price` stays RAW here (§12.5's ordering constraint), and
    normalization happens downstream in this unit."""
    return V2CandidateFacts(
        symbol=_symbol_of(candidate), market_type=_market_type_of(candidate),
        direction=candidate.direction, setup_family=CONFIRMED_BREAKOUT, T=candidate.T,
        anchor_bucket=candidate.level_anchor_bucket,
        raw_level_price=candidate.level_price,
        entry_zone_lower=candidate.entry_zone_lower,
        entry_zone_upper=candidate.entry_zone_upper,
        invalidation_price=candidate.invalidation_price,
        protection_buffer=candidate.protection_buffer,
        decision_tick_size=candidate.decision_tick_size,
        setup_strength=candidate.setup_strength,
        data_confidence=getattr(candidate, "data_confidence", None),
        family_facts=_family_facts(
            level_anchor_bucket=candidate.level_anchor_bucket.isoformat(),
            raw_level_price=candidate.level_price,
            level_kind=candidate.level_kind,
            bucket_1h=candidate.bucket_1h.isoformat(),
            breakout_close=candidate.breakout_close,
            previous_5m_close=candidate.previous_5m_close,
            range_proxy_pct=candidate.range_proxy_pct,
        ),
    )


def _symbol_of(candidate) -> str:
    """Stage 5 candidates are scoped to the single supported V2 instrument
    (`_validation.SUPPORTED_SYMBOL`) and do not repeat it as a field; take
    it from the candidate when present, else from the frozen V2 scope."""
    from analytics.forecasting_v2._validation import SUPPORTED_SYMBOL
    return getattr(candidate, "symbol", SUPPORTED_SYMBOL)


def _market_type_of(candidate) -> str:
    from analytics.forecasting_v2._validation import SUPPORTED_MARKET_TYPE
    return getattr(candidate, "market_type", SUPPORTED_MARKET_TYPE)


# ============================================================================
# §13.4's two views, as explicit inputs
# ============================================================================
@dataclass(frozen=True)
class V2SlotOccupancyView:
    """§13.4 step 3a — `surviving_active_set(T)`: the non-terminal episodes
    remaining AFTER this `T`'s own lifecycle transitions, keyed by slot.

    Supplied by the caller (unit 5, once it exists) because deriving it
    requires applying unit 3/4 transitions, which this unit does not
    implement. Used ONLY for same-slot ACTIVE occupancy (§12.6) — never for
    cooldown, which is a different question with a different answer at the
    same `T`."""
    as_of: datetime
    active_by_slot: Mapping

    def __post_init__(self) -> None:
        _validate_decision_boundary_T(self.as_of, "as_of")
        if not isinstance(self.active_by_slot, Mapping):
            raise V2EpisodeCreationError(
                f"active_by_slot must be a Mapping, got {type(self.active_by_slot).__name__}")
        frozen = {}
        for slot, histories in self.active_by_slot.items():
            if not (isinstance(slot, tuple) and len(slot) == 4):
                raise V2EpisodeCreationError(
                    f"active_by_slot key must be a 4-tuple slot, got {slot!r}")
            entries = tuple(histories) if isinstance(histories, (list, tuple)) else (histories,)
            for entry in entries:
                if not isinstance(entry, V2EpisodeHistory):
                    raise V2EpisodeCreationError(
                        f"active_by_slot[{slot!r}] must contain V2EpisodeHistory, got "
                        f"{type(entry).__name__}")
                if entry.is_terminal:
                    raise V2EpisodeCreationError(
                        f"active_by_slot[{slot!r}] contains episode {entry.episode_id!r} whose "
                        f"persisted state is {entry.current_state!r} -- surviving_active_set(T) "
                        "holds only NON-terminal episodes (§13.4 step 3a)")
            frozen[slot] = entries
        object.__setattr__(self, "active_by_slot", MappingProxyType(frozen))

    def active_episode(self, slot) -> Optional[V2EpisodeHistory]:
        """The single active episode occupying `slot`, or `None`.

        §12.6 freezes "at most ONE active (non-terminal) episode per slot".
        More than one is an impossible state, so this FAILS CLOSED rather
        than picking the newest/oldest/highest-scoring one."""
        entries = self.active_by_slot.get(slot, ())
        if not entries:
            return None
        if len(entries) > 1:
            raise V2EpisodeCreationError(
                f"slot {slot!r} is occupied by {len(entries)} active episodes "
                f"({[e.episode_id for e in entries]!r}) -- §12.6 allows at most ONE active "
                "episode per slot; this is corrupt/impossible state, never an arbitrary choice")
        return entries[0]


@dataclass(frozen=True)
class V2SlotTerminalFact:
    """One slot's MOST RECENT terminal episode as of `T` (§13.4 step 3b):
    the terminal state and its `T_terminal` (§12.8: "the decision boundary
    of the terminal event")."""
    episode_id: str
    terminal_state: str
    t_terminal: datetime

    def __post_init__(self) -> None:
        nonblank(self.episode_id, "episode_id", V2EpisodeCreationError)
        one_of(self.terminal_state, "terminal_state", TERMINAL_EPISODE_STATES,
               V2EpisodeCreationError)
        _validate_decision_boundary_T(self.t_terminal, "t_terminal")

    @property
    def earliest_eligible_boundary(self) -> datetime:
        """§12.8's exact clock: `T_terminal + N * 5m`, where N is 3 for
        `INVALIDATED` and 1 for `EXPIRED`/`COMPLETED`. "A candidate arriving
        at exactly the first eligible decision boundary MAY create a new
        episode if it genuinely, independently qualifies at that boundary."""
        return self.t_terminal + TERMINAL_COOLDOWN_BUCKETS[self.terminal_state] * DECISION_BUCKET


@dataclass(frozen=True)
class V2SlotCooldownView:
    """§13.4 step 3b — per-slot terminal/cooldown state as of `T`, drawn
    from PERSISTED terminal-episode history and INCLUDING an episode that
    became terminal at this very `T` (`T_terminal = T` is "a valid,
    immediately-effective value", §12.8).

    Deliberately a SEPARATE view from `V2SlotOccupancyView`: excluding a
    same-`T` terminal episode from 3a must never be misread as excluding it
    from 3b's cooldown lookup."""
    as_of: datetime
    terminal_by_slot: Mapping

    def __post_init__(self) -> None:
        _validate_decision_boundary_T(self.as_of, "as_of")
        if not isinstance(self.terminal_by_slot, Mapping):
            raise V2EpisodeCreationError(
                f"terminal_by_slot must be a Mapping, got "
                f"{type(self.terminal_by_slot).__name__}")
        frozen = {}
        for slot, fact in self.terminal_by_slot.items():
            if not (isinstance(slot, tuple) and len(slot) == 4):
                raise V2EpisodeCreationError(
                    f"terminal_by_slot key must be a 4-tuple slot, got {slot!r}")
            if not isinstance(fact, V2SlotTerminalFact):
                raise V2EpisodeCreationError(
                    f"terminal_by_slot[{slot!r}] must be a V2SlotTerminalFact, got "
                    f"{type(fact).__name__}")
            if fact.t_terminal > self.as_of:
                raise V2EpisodeCreationError(
                    f"terminal_by_slot[{slot!r}] has t_terminal "
                    f"{fact.t_terminal.isoformat()!r} after as_of {self.as_of.isoformat()!r} -- "
                    "a future terminal event cannot be part of this boundary's cooldown view")
            frozen[slot] = fact
        object.__setattr__(self, "terminal_by_slot", MappingProxyType(frozen))

    def most_recent_terminal(self, slot) -> Optional[V2SlotTerminalFact]:
        return self.terminal_by_slot.get(slot)


# ============================================================================
# §12.3/§12.4 classification
# ============================================================================
def _anchor_bucket_distance(creation_anchor: datetime, candidate_anchor: datetime) -> int:
    """§12.4's exact integer 15m bucket-count distance.

    "`bucket_distance` MUST be computed as an exact integer count of aligned
    15m buckets ... never as an approximate wall-clock
    `abs(C - A).total_seconds() / 900` comparison, which is equivalent here
    but is not the frozen form." A pair of anchors whose separation is not
    a whole number of 15m buckets is malformed and is rejected, never
    coerced."""
    delta = abs(candidate_anchor - creation_anchor)
    buckets, remainder = divmod(delta, _ANCHOR_BUCKET_WIDTH)
    if remainder:
        raise V2EpisodeCreationError(
            f"anchors {creation_anchor.isoformat()!r} and {candidate_anchor.isoformat()!r} are "
            f"{delta} apart, which is not a whole number of 15m buckets -- both must be aligned "
            "15m bucket starts (§12.1/§12.4)")
    return int(buckets)


def _creation_anchor_bucket(creation: V2EpisodeCreationIdentity) -> datetime:
    raw = creation.structural_anchor.get(ANCHOR_BUCKET_TS)
    if not isinstance(raw, str):
        raise V2EpisodeCreationError(
            f"episode {creation.episode_id!r} has no usable persisted "
            f"structural_anchor.{ANCHOR_BUCKET_TS}")
    return datetime.fromisoformat(raw)


def classify_candidate_against_active_episode(
    candidate: V2CandidateFacts, active: V2EpisodeHistory,
) -> str:
    """§12.3's three-way classification of one candidate against the active
    same-slot episode's CREATION identity (§12.2) — never against a previous
    observation, a running average, or anything re-derived from current
    metadata.

    Returns `MATCH_EXACT` (case A), `MATCH_NON_MATERIAL` (case B) or
    `MATCH_MATERIAL` (case C). This function classifies only; it never
    mutates the episode, never creates one, and never decides whether a
    persisted event is required (§12.11)."""
    if not isinstance(candidate, V2CandidateFacts):
        raise V2EpisodeCreationError(
            f"candidate must be a V2CandidateFacts, got {type(candidate).__name__}")
    if not isinstance(active, V2EpisodeHistory):
        raise V2EpisodeCreationError(
            f"active must be a V2EpisodeHistory, got {type(active).__name__}")
    creation = active.creation_identity
    if candidate.slot != creation.slot:
        raise V2EpisodeCreationError(
            f"candidate slot {candidate.slot!r} does not match the active episode's slot "
            f"{creation.slot!r} -- §12.3 classifies a candidate only against an episode in its "
            "OWN slot")
    if active.is_terminal:
        raise V2EpisodeCreationError(
            f"episode {active.episode_id!r} is {active.current_state!r} (terminal) -- §12.3 "
            "classifies against an ACTIVE episode; a terminal one is a §12.8 cooldown question")

    if creation.setup_family == CONFIRMED_BREAKOUT:
        return _classify_confirmed_breakout(candidate, active)
    return _classify_bucket_anchored(candidate, creation)


def _classify_bucket_anchored(
    candidate: V2CandidateFacts, creation: V2EpisodeCreationIdentity,
) -> str:
    """§12.4 for the two 15m-anchored families (identical rule, applied
    independently to each family's own `structural_anchor`)."""
    distance = _anchor_bucket_distance(_creation_anchor_bucket(creation), candidate.anchor_bucket)
    if distance == 0:
        return MATCH_EXACT
    return MATCH_NON_MATERIAL if distance <= ANCHOR_DRIFT_BUCKETS else MATCH_MATERIAL


def _classify_confirmed_breakout(candidate: V2CandidateFacts, active: V2EpisodeHistory) -> str:
    """§12.3/§12.4/§12.5a for `CONFIRMED_BREAKOUT`.

    Case (A) requires BOTH dimensions of the `(level_anchor_bucket,
    tick-normalized price)` pair to match. A candidate whose tick matches
    but whose bucket differs is NOT case (A) — and, per §12.3's own worked
    example, `level_anchor_bucket` inequality by itself never makes it
    material either; it falls to (B)/(C) purely on the price-drift formula.

    The candidate's RAW level is normalized against the ACTIVE EPISODE'S
    `creation_identity_tick_size` (§12.5a) — never the candidate's own
    decision-time tick size, even if the instrument's tick has since
    changed. The whole comparison stays in `Decimal` (§12.4: "the
    comparison never crosses back into binary `float`, and never uses an
    epsilon/tolerance fudge")."""
    creation = active.creation_identity
    creation_tick = creation.creation_identity_tick_size
    creation_normalized = creation.creation_normalized_level_price
    creation_tick_index = creation.creation_level_tick_index
    if creation_tick is None or creation_normalized is None or creation_tick_index is None:
        raise V2EpisodeCreationError(
            f"episode {creation.episode_id!r} is CONFIRMED_BREAKOUT but its persisted creation "
            "identity is missing the §12.5a tick grid -- classification cannot proceed")

    candidate_tick_index, candidate_normalized = normalize_price_to_tick(
        candidate.raw_level_price, creation_tick)

    same_bucket = candidate.anchor_bucket == _creation_anchor_bucket(creation)
    if same_bucket and candidate_tick_index == creation_tick_index:
        return MATCH_EXACT

    buffer_decimal = Decimal(str(read_creation_protection_buffer(active)))
    level_drift = abs(candidate_normalized - creation_normalized)
    threshold = Decimal("2") * buffer_decimal
    return MATCH_NON_MATERIAL if level_drift <= threshold else MATCH_MATERIAL


# ============================================================================
# §12.8 cooldown
# ============================================================================
def evaluate_terminal_cooldown(
    terminal: Optional[V2SlotTerminalFact], *, T: datetime,
) -> bool:
    """§12.8: is a NEW same-slot episode creation-eligible at `T`?

    `True` iff there is no relevant terminal fact, or `T` has reached the
    slot's earliest eligible boundary. `T_terminal` itself is never
    eligible ("§12.8's cooldown is >= 1 bucket in every case"), and the
    earliest eligible boundary itself IS eligible.

    This answers only the cooldown question; the caller still applies
    same-slot ACTIVE occupancy and family precedence separately, because
    the three mechanisms have distinct clearing conditions (§12.7)."""
    _validate_decision_boundary_T(T, "T")
    if terminal is None:
        return True
    if not isinstance(terminal, V2SlotTerminalFact):
        raise V2EpisodeCreationError(
            f"terminal must be a V2SlotTerminalFact or None, got {type(terminal).__name__}")
    return T >= terminal.earliest_eligible_boundary


# ============================================================================
# §7.4 family precedence
# ============================================================================
def _regions_overlap(a: "tuple[float, float]", b: "tuple[float, float]") -> bool:
    """§7.4.1's exact predicate: `max(lower_A, lower_B) <= min(upper_A,
    upper_B)`. Boundary-touching counts as overlap (`<=`, not `<`). No
    percentage/tick/ATR tolerance and no epsilon is added."""
    return max(a[0], b[0]) <= min(a[1], b[1])


def arbitrate_new_candidates(
    candidates: Sequence[V2CandidateFacts],
) -> "tuple[tuple[V2CandidateFacts, ...], Mapping]":
    """§7.4.2's deterministic arbitration over creation-eligible NEW
    candidates at one `T`.

    Arbitrated SEPARATELY PER DIRECTION (§7.4: "Different-direction
    simultaneous qualifications are not deduplicated by this rule"), and
    within a direction walked strictly in frozen precedence order
    (`COMPRESSION_BREAKOUT > CONFIRMED_BREAKOUT > TREND_PULLBACK`),
    accepting a candidate iff its §7.4.1 region does not overlap any
    ALREADY-ACCEPTED candidate's region.

    Because the walk is precedence-ordered and each step compares only
    against already-accepted candidates, the result is independent of any
    incidental input ordering. Ties within one family+direction cannot
    occur here: a slot holds at most one creation-eligible candidate by
    construction (§12.6), and that is asserted rather than assumed.

    Returns `(accepted, suppressed_by_winner)` where `suppressed_by_winner`
    maps each winner's slot to the tuple of candidates suppressed against
    it, deterministically ordered by precedence."""
    ordered = []
    seen_slots = set()
    for candidate in candidates:
        if not isinstance(candidate, V2CandidateFacts):
            raise V2EpisodeCreationError(
                f"every candidate must be a V2CandidateFacts, got {type(candidate).__name__}")
        if candidate.slot in seen_slots:
            raise V2EpisodeCreationError(
                f"two creation-eligible candidates share slot {candidate.slot!r} at one decision "
                "boundary -- §12.6 allows at most one episode per slot, so this input is "
                "impossible, never arbitrated by an invented tie-break")
        seen_slots.add(candidate.slot)
        ordered.append(candidate)

    accepted: list = []
    suppressed: dict = {}
    for direction in DIRECTIONS:
        per_direction = [c for c in ordered if c.direction == direction]
        # Sort key is precedence rank ONLY -- see docstring for why no
        # incidental input property may participate.
        per_direction.sort(key=lambda c: FAMILY_PRECEDENCE.index(c.setup_family))
        accepted_here: list = []
        for candidate in per_direction:
            winner = next(
                (w for w in accepted_here if _regions_overlap(candidate.region, w.region)), None)
            if winner is None:
                accepted_here.append(candidate)
            else:
                suppressed.setdefault(winner.slot, []).append(candidate)
        accepted.extend(accepted_here)

    return (
        tuple(accepted),
        MappingProxyType({slot: tuple(losers) for slot, losers in suppressed.items()}),
    )


# ============================================================================
# creation facts: written by this unit, read back by this unit
# ============================================================================
def _creation_facts_payload(candidate: V2CandidateFacts) -> Mapping:
    """The canonical BY-VALUE creation facts a newly-created episode must
    carry so later units and a post-restart reconstruction never need to
    re-read today's market/instrument state.

    Every value here is already owned by the Stage 5 candidate — nothing is
    recomputed, and no Stage 2 read happens inside Stage 6. Identity facts
    that the event's own top-level columns already own (`symbol`,
    `market_type`, `direction`, `setup_family`, `structural_anchor`,
    `decision_boundary`) are deliberately NOT duplicated here.

    `protection_buffer` is load-bearing beyond bookkeeping: §12.4's
    `CONFIRMED_BREAKOUT` materiality threshold is `2 *
    active_creation_protection_buffer`, "the `protection_buffer` recorded
    when the active episode was created", so it MUST survive restart by
    value — `read_creation_protection_buffer()` reads exactly this key
    back."""
    return {
        _CF_T_DETECT: candidate.T.isoformat(),
        _CF_ENTRY_ZONE_LOWER: candidate.entry_zone_lower,
        _CF_ENTRY_ZONE_UPPER: candidate.entry_zone_upper,
        _CF_INVALIDATION_PRICE: candidate.invalidation_price,
        _CF_PROTECTION_BUFFER: canonical_decimal_text(
            Decimal(str(candidate.protection_buffer)), _CF_PROTECTION_BUFFER),
        _CF_DECISION_TICK_SIZE: canonical_decimal_text(
            Decimal(str(candidate.decision_tick_size)), _CF_DECISION_TICK_SIZE),
        _CF_SETUP_STRENGTH: candidate.setup_strength,
        _CF_DATA_CONFIDENCE: candidate.data_confidence,
        _CF_FAMILY_FACTS: dict(candidate.family_facts),
    }


def read_creation_facts(active: V2EpisodeHistory) -> Mapping:
    """The persisted creation facts of an existing episode, read back from
    its own creation event — never from a current candidate."""
    if not isinstance(active, V2EpisodeHistory):
        raise V2EpisodeCreationError(
            f"active must be a V2EpisodeHistory, got {type(active).__name__}")
    facts = active.creation_event.decision_snapshot.get(CREATION_FACTS_KEY)
    if not isinstance(facts, Mapping):
        raise V2EpisodeCreationError(
            f"episode {active.episode_id!r}'s creation event carries no "
            f"{CREATION_FACTS_KEY!r} mapping in its decision_snapshot -- Stage 6 unit 2 requires "
            "creation-time supporting facts recorded BY VALUE at creation")
    return facts


def read_creation_protection_buffer(active: V2EpisodeHistory) -> Decimal:
    """§12.4's `active_creation_protection_buffer`, reconstructed from the
    episode's persisted creation event.

    Deliberately NOT taken from the current candidate, current volatility,
    or current instrument metadata — §12.4 freezes it as "the
    `protection_buffer` recorded when the active episode was created ...
    never a buffer recomputed at the candidate's own decision boundary, so
    the threshold cannot move merely because a later candidate observed a
    different volatility environment"."""
    raw = read_creation_facts(active).get(_CF_PROTECTION_BUFFER)
    if not isinstance(raw, str):
        raise V2EpisodeCreationError(
            f"episode {active.episode_id!r}'s persisted creation facts carry no exact "
            f"{_CF_PROTECTION_BUFFER!r} decimal string -- §12.4's materiality threshold is "
            "unrecoverable, so classification fails closed rather than guessing")
    try:
        buffer = Decimal(raw)
    except Exception as exc:  # noqa: BLE001 - malformed persisted value, never leaked raw
        raise V2EpisodeCreationError(
            f"episode {active.episode_id!r}'s persisted {_CF_PROTECTION_BUFFER}={raw!r} is not a "
            f"valid decimal: {exc}") from exc
    if not buffer.is_finite() or buffer <= 0:
        raise V2EpisodeCreationError(
            f"episode {active.episode_id!r}'s persisted {_CF_PROTECTION_BUFFER}={raw!r} must be a "
            "finite, strictly positive decimal")
    return buffer


# ============================================================================
# creation authorization (§3.1/§3.3, H2 seams reused, never reimplemented)
# ============================================================================
@dataclass(frozen=True)
class V2CreationAuthorization:
    """Proof that new-episode creation is permitted for one decision view.

    The three H2 guards stay INDEPENDENT and each fail closed on its own
    terms — they are deliberately not collapsed into a single `is_ready`
    bool, because they answer different questions and clear under different
    conditions:

      1. **Activation readiness** (§3.3) — `V2DecisionView.ready`, H2a's
         own fail-closed predicate.
      2. **Version-switch authorization** (§3.1) — delegated verbatim to
         `version_switch.assert_provenance_authorized_for_new_creation()`,
         which is the ONLY thing that authorizes creation; during a drain
         `active_for_new_creation(state)` is `None`, so neither OLD nor NEW
         may create.
      3. **Stage 2 publication CLEAN** (§3.4) — proven by the caller
         having successfully opened an H2e coherent read session for this
         exact scope/version/boundary (which raises
         `V2PublicationDirtyError` rather than yielding when the scope is
         STALE). It is passed here as an explicit acknowledgement so the
         guard cannot be silently skipped.

    Constructing this object is the only way to reach
    `build_early_signal_creation()`, so a caller cannot accidentally create
    an event under a tuple that was not authorized at `T`."""
    decision_view: V2DecisionView
    switch_state: V2VersionSwitchState
    publication_clean: bool

    def __post_init__(self) -> None:
        if not isinstance(self.decision_view, V2DecisionView):
            raise V2EpisodeCreationError(
                f"decision_view must be a V2DecisionView, got "
                f"{type(self.decision_view).__name__}")
        if not isinstance(self.switch_state, V2VersionSwitchState):
            raise V2EpisodeCreationError(
                f"switch_state must be a V2VersionSwitchState, got "
                f"{type(self.switch_state).__name__}")
        if self.publication_clean is not True:
            raise V2EpisodeCreationError(
                "publication_clean must be True -- §3.4 requires the Stage 2 publication state "
                "for this scope/version to be CLEAN before a new episode may be created; a "
                "caller proves this by having opened an H2e coherent read session")
        if not self.decision_view.ready:
            not_ready = tuple(
                status.requirement for status in self.decision_view.readiness.statuses
                if not status.ready)
            raise V2EpisodeCreationError(
                "activation readiness is NOT_READY (§3.3) -- new-episode creation is refused; "
                f"unmet coverage requirements: {not_ready!r}")
        # §3.1: raises V2VersionSwitchError if this provenance is not the
        # tuple currently authorized for NEW creation in this stream.
        assert_provenance_authorized_for_new_creation(self.provenance, self.switch_state)

    @property
    def provenance(self) -> V2DecisionProvenance:
        """The SAME immutable provenance resolved before Stage 3/4/5/6
        computation began — never re-derived at event-construction time."""
        return self.decision_view.provenance

    def event_provenance(self) -> V2EventProvenance:
        """Project the already-resolved decision provenance into the
        narrower event-construction snapshot `build_v2_episode_event()`
        consumes.

        This is a pure PROJECTION of one immutable tuple, not a second
        resolution: every field is copied from `V2DecisionProvenance`,
        including `decision_code_version`. `decision_boundary` is dropped
        because it is the event's own `decision_boundary` argument, not
        provenance (`decision_provenance.py`'s own docstring frames the two
        types exactly this way)."""
        p = self.provenance
        return V2EventProvenance(
            run_kind=p.run_kind, run_id=p.run_id, model_family=p.model_family,
            rules_version=p.rules_version, symbol=p.symbol, market_type=p.market_type,
            feature_schema_version=p.feature_schema_version,
            calculation_version=p.calculation_version, config_hash=p.config_hash,
            config_version=p.config_version, code_version=p.code_version,
            decision_code_version=p.decision_code_version,
        )


# ============================================================================
# EARLY_SIGNAL creation
# ============================================================================
def _creation_structural_anchor(candidate: V2CandidateFacts) -> Mapping:
    """Reuse Unit 1's canonical per-family anchor builders — never a second
    set of builders, and never a second spelling of the same anchor."""
    if candidate.setup_family == TREND_PULLBACK:
        return build_trend_pullback_anchor(bucket_ts=candidate.anchor_bucket)
    if candidate.setup_family == COMPRESSION_BREAKOUT:
        return build_compression_breakout_anchor(bucket_ts=candidate.anchor_bucket)
    return build_confirmed_breakout_anchor(
        level_anchor_bucket=candidate.anchor_bucket,
        raw_level_price=candidate.raw_level_price,
        # §12.5a: the episode's OWN creation grid is the candidate's
        # decision-time validated tick_size, frozen here once and never
        # re-derived for the rest of the episode's life.
        creation_identity_tick_size=candidate.decision_tick_size,
    )


def _precedence_crossref(losers: Sequence[V2CandidateFacts]) -> tuple:
    """§7.4.2's cross-reference, aggregated into the winner's ONE creation
    event at `T`.

    H3 allows at most one persisted event per `(execution_stream,
    episode_id, decision_boundary)`, so a second same-`T` event for the
    cross-reference is impossible by construction — all losers are recorded
    together here. Losers are suppressed CANDIDATES, never episodes: they
    receive no `episode_id` and no event of their own. Ordered by frozen
    family precedence so the shape is deterministic and independent of
    input order."""
    ordered = sorted(losers, key=lambda c: FAMILY_PRECEDENCE.index(c.setup_family))
    return tuple(
        MappingProxyType({
            "setup_family": loser.setup_family,
            "direction": loser.direction,
            "reason": SUPPRESSED_FAMILY_PRECEDENCE,
            "entry_zone_lower": loser.entry_zone_lower,
            "entry_zone_upper": loser.entry_zone_upper,
        })
        for loser in ordered
    )


def build_early_signal_creation(
    candidate: V2CandidateFacts,
    *,
    authorization: V2CreationAuthorization,
    T: datetime,
    suppressed_by_precedence: Sequence[V2CandidateFacts] = (),
) -> V2EpisodeEvent:
    """Build the canonical `EARLY_SIGNAL` creation event for one accepted
    candidate.

    Uses `event_factory.build_v2_episode_event()` exclusively — this module
    never constructs a `V2EpisodeEvent` directly, never computes an
    `episode_id`/`event_id` itself, and never introduces a second factory.
    `t_create == decision_boundary == T` for a creation event, exactly as
    `event_factory.py` freezes it.

    The event carries the §22 by-value creation facts under
    `decision_snapshot[CREATION_FACTS_KEY]` and, when this candidate won a
    §7.4.2 arbitration, the aggregated precedence cross-reference under
    `event_payload[PRECEDENCE_CROSSREF_KEY]`."""
    if not isinstance(candidate, V2CandidateFacts):
        raise V2EpisodeCreationError(
            f"candidate must be a V2CandidateFacts, got {type(candidate).__name__}")
    if not isinstance(authorization, V2CreationAuthorization):
        raise V2EpisodeCreationError(
            "authorization must be a V2CreationAuthorization -- new-episode creation is only "
            "reachable through the §3.1/§3.3/§3.4 guards")
    _validate_decision_boundary_T(T, "T")
    if candidate.T != T:
        raise V2EpisodeCreationError(
            f"candidate.T {candidate.T.isoformat()!r} does not equal the creation boundary "
            f"{T.isoformat()!r} -- a candidate may only create an episode at its own boundary")
    provenance = authorization.provenance
    if provenance.decision_boundary != T:
        raise V2EpisodeCreationError(
            f"authorization provenance was resolved for "
            f"{provenance.decision_boundary.isoformat()!r}, not {T.isoformat()!r}")
    if (provenance.symbol, provenance.market_type) != (candidate.symbol, candidate.market_type):
        raise V2EpisodeCreationError(
            f"candidate scope {(candidate.symbol, candidate.market_type)!r} does not match the "
            f"authorized provenance scope {(provenance.symbol, provenance.market_type)!r}")

    event_payload = {"created_from": "STAGE5_CANDIDATE"}
    crossref = _precedence_crossref(suppressed_by_precedence)
    if crossref:
        event_payload[PRECEDENCE_CROSSREF_KEY] = crossref

    return build_v2_episode_event(
        authorization.event_provenance(),
        t_create=T,
        direction=candidate.direction,
        setup_family=candidate.setup_family,
        structural_anchor=_creation_structural_anchor(candidate),
        episode_state=EARLY_SIGNAL,
        decision_boundary=T,
        decision_snapshot={CREATION_FACTS_KEY: _creation_facts_payload(candidate)},
        event_payload=event_payload,
    )


# ============================================================================
# the one small compositional service
# ============================================================================
@dataclass(frozen=True)
class V2CandidateOutcome:
    """One candidate's deterministic Unit 2 outcome at `T`.

    `outcome` is one of `CANDIDATE_OUTCOMES`. `routed_episode_id` is set
    only for the two ROUTE outcomes; `creation_event` only for
    `CREATE_EARLY_SIGNAL`; `blocking_episode_id`/`cooldown_until` only for
    the corresponding suppression. Nothing here is persisted state — a
    suppression outcome is an ephemeral decision, never a queue entry
    (§12.7)."""
    candidate: V2CandidateFacts
    outcome: str
    match_class: Optional[str] = None
    routed_episode_id: Optional[str] = None
    blocking_episode_id: Optional[str] = None
    cooldown_until: Optional[datetime] = None
    suppressed_by_slot: Optional[tuple] = None
    creation_event: Optional[V2EpisodeEvent] = None

    def __post_init__(self) -> None:
        one_of(self.outcome, "outcome", CANDIDATE_OUTCOMES, V2EpisodeCreationError)
        if self.match_class is not None:
            one_of(self.match_class, "match_class", MATCH_CLASSES, V2EpisodeCreationError)


@dataclass(frozen=True)
class V2BoundaryRoutingResult:
    """Every candidate's outcome at one decision boundary, plus the
    creation events to persist (winners only)."""
    T: datetime
    outcomes: "tuple[V2CandidateOutcome, ...]"

    @property
    def creation_events(self) -> "tuple[V2EpisodeEvent, ...]":
        return tuple(
            o.creation_event for o in self.outcomes
            if o.outcome == CREATE_EARLY_SIGNAL and o.creation_event is not None)


def route_candidates_at_boundary(
    candidates: Sequence[V2CandidateFacts],
    *,
    T: datetime,
    occupancy: V2SlotOccupancyView,
    cooldown: V2SlotCooldownView,
    authorization: Optional[V2CreationAuthorization] = None,
) -> V2BoundaryRoutingResult:
    """Compose Unit 2's primitives in the frozen order for one `T`.

    Order (§13.4 steps 5-7, restricted to what this unit owns):

      1. Same-slot ACTIVE occupancy (§12.6): if the slot holds an active
         episode, classify (§12.3) — A/B route to it, C suppresses.
      2. Terminal cooldown (§12.8) for slots with no active episode.
      3. §7.4.2 family precedence among what survives, per direction.
      4. Build ONE canonical creation event per winner.

    `authorization` may be omitted to evaluate routing without creating
    anything (the eligibility answer is still exact); winners then carry no
    `creation_event`, and no event is ever fabricated without the §3.1/
    §3.3/§3.4 guards.

    This is NOT §13.4's full eight-step coordinator: it does not resolve
    lifecycle transitions, does not derive `surviving_active_set(T)` (it
    receives it), and does not emit `REVERSAL_CANDIDATE` cross-references.
    Unit 5 owns those."""
    _validate_decision_boundary_T(T, "T")
    if not isinstance(occupancy, V2SlotOccupancyView):
        raise V2EpisodeCreationError(
            f"occupancy must be a V2SlotOccupancyView, got {type(occupancy).__name__}")
    if not isinstance(cooldown, V2SlotCooldownView):
        raise V2EpisodeCreationError(
            f"cooldown must be a V2SlotCooldownView, got {type(cooldown).__name__}")
    for view, name in ((occupancy, "occupancy"), (cooldown, "cooldown")):
        if view.as_of != T:
            raise V2EpisodeCreationError(
                f"{name} view was resolved for {view.as_of.isoformat()!r}, not "
                f"{T.isoformat()!r} -- §13.4's views are fixed at THIS boundary")

    outcomes: list = []
    creation_eligible: list = []
    for candidate in candidates:
        if not isinstance(candidate, V2CandidateFacts):
            raise V2EpisodeCreationError(
                f"every candidate must be a V2CandidateFacts, got {type(candidate).__name__}")
        if candidate.T != T:
            raise V2EpisodeCreationError(
                f"candidate.T {candidate.T.isoformat()!r} does not equal the decision boundary "
                f"{T.isoformat()!r}")

        active = occupancy.active_episode(candidate.slot)
        if active is not None:
            match = classify_candidate_against_active_episode(candidate, active)
            if match == MATCH_MATERIAL:
                outcomes.append(V2CandidateOutcome(
                    candidate=candidate, outcome=SUPPRESSED_ACTIVE_SLOT, match_class=match,
                    blocking_episode_id=active.episode_id))
            else:
                outcomes.append(V2CandidateOutcome(
                    candidate=candidate,
                    outcome=(ROUTE_EXISTING_EXACT if match == MATCH_EXACT
                             else ROUTE_EXISTING_NON_MATERIAL),
                    match_class=match, routed_episode_id=active.episode_id))
            continue

        terminal = cooldown.most_recent_terminal(candidate.slot)
        if not evaluate_terminal_cooldown(terminal, T=T):
            outcomes.append(V2CandidateOutcome(
                candidate=candidate, outcome=SUPPRESSED_COOLDOWN,
                blocking_episode_id=terminal.episode_id,
                cooldown_until=terminal.earliest_eligible_boundary))
            continue

        creation_eligible.append(candidate)

    accepted, suppressed_by_winner = arbitrate_new_candidates(creation_eligible)
    accepted_slots = {c.slot for c in accepted}
    for slot, losers in suppressed_by_winner.items():
        for loser in losers:
            outcomes.append(V2CandidateOutcome(
                candidate=loser, outcome=SUPPRESSED_FAMILY_PRECEDENCE,
                suppressed_by_slot=slot))
    for candidate in creation_eligible:
        if candidate.slot not in accepted_slots:
            continue
        event = None
        if authorization is not None:
            event = build_early_signal_creation(
                candidate, authorization=authorization, T=T,
                suppressed_by_precedence=suppressed_by_winner.get(candidate.slot, ()))
        outcomes.append(V2CandidateOutcome(
            candidate=candidate, outcome=CREATE_EARLY_SIGNAL, creation_event=event))

    return V2BoundaryRoutingResult(T=T, outcomes=tuple(outcomes))
