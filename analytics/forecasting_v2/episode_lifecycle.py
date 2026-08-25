"""
Stage 6 Unit 3 — `EARLY_SIGNAL` lifecycle resolution: family confirmation,
breakout false-break invalidation, candidate-age expiry, and
`TREND_PULLBACK`'s pre-confirmation same-episode operational updates
(`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §7.1/§7.2/§7.3, §9, §12.2a,
§12.11, §13.1/§13.2, §14, §6.3a, §3.1).

Unit 2 (`episode_creation.py`) decides WHICH episode a Stage 5 candidate
belongs to and creates `EARLY_SIGNAL`s. This unit answers the next
question, for ONE already-existing `EARLY_SIGNAL` episode at ONE legal 5m
decision boundary `T`:

```text
does this boundary resolve the episode, and if so, how?

    CONFIRMED                 §7.1/§7.2/§7.3 family confirmation
    INVALIDATED               breakout false-break (§7.2/§7.3 only)
    EXPIRED                   candidate-age deadline closed unconfirmed (§14)
    EARLY_SIGNAL (unchanged)  TREND_PULLBACK operational update (§7.1/§9/§12.2a)
    nothing at all            no episode-visible fact changed (§12.11)
```

**Exactly three transitions out of `EARLY_SIGNAL`, plus one same-state
update.** §13.2's graph is frozen and this module invents no edge:
`EARLY_SIGNAL -> CONFIRMED | INVALIDATED | EXPIRED`. The fourth outcome is
NOT a transition — it is `TREND_PULLBACK`'s own §12.2a mechanism-(1)
re-measurement of its structural leg, persisted as a further, immutable
`EARLY_SIGNAL` event on the SAME episode.

**Hard scope boundary — this is not Unit 4 or Unit 5.** This module owns
transitions out of `EARLY_SIGNAL` and nothing else. It never evaluates
`CONFIRMED`/`WEAKENING`, never implements §10's generic post-confirmation
structural-invalidation engine (the two breakout false-break rules here
are §7.2/§7.3's *own* frozen pre-confirmation checks, deliberately
assigned to this unit by the roadmap — they are not a §10 engine and must
not be generalized into one), never resolves a horizon, never orchestrates
§13.4's same-boundary order across episodes, and never composes multiple
episodes. It also never reaches `TREND_PULLBACK`'s own §10
`invalidation_price`-crossing check, which is generic-§10 work Unit 4
owns; a `TREND_PULLBACK` episode whose planned invalidation has been
breached is therefore NOT terminalized here.

**Purity.** No DB, no network, no filesystem, no clock (no
`datetime.now()`/`utcnow()`/`time.time()`), no `random`/`uuid`. Every
decision is a deterministic function of (a) the episode's persisted
history, reconstructed through Unit 1, and (b) one already-resolved,
coherent snapshot of the current boundary's facts. The same inputs always
produce the same outcome, which is precisely what makes restart/replay
equivalence provable rather than hoped for.

**The decision clock is logical, never wall-clock (§1).** Candidate age is
`T - T_detect`, where `T_detect` is the episode's own frozen creation
decision boundary and `T` is the logical boundary being evaluated. Nothing
in this module reads `created_at`, insertion order, or processing time.

**The deadline boundary is a confirmation opportunity, not an automatic
expiry (§13.1/§14).** `EXPIRED` fires iff the deadline boundary is reached
AND that same boundary's own confirmation check did not hold. The `N`-th
eligible bucket confirms exactly like every earlier one. This module never
computes "age reached the limit" as an independent fact blind to the same
boundary's confirmation result — the two are mutually exclusive by
construction, exactly as §13.1 freezes.

**Per-family metric scoping (§6.3a).** All three families' confirmation /
false-break / HOLD decisions consume the `price_structure` family only.
An unrelated degraded family (`volume`, `taker_flow`, `oi`, `funding`,
`liquidations`) can never suppress a transition here — in particular
`CONFIRMED_BREAKOUT` confirmation carries NO taker-flow requirement
(§7.3), and `COMPRESSION_BREAKOUT`'s taker-flow gate is a FORMATION-time
requirement (§7.2's `EARLY_SIGNAL` trigger) that deliberately does not
carry over to confirmation.

**Version draining (§3.1) — deliberately NOT gated on new-episode
creation authorization.** §3.1 is explicit that while `OLD` is `DRAINING`,
`OLD` *MAY and MUST* continue lifecycle evaluation of episodes that
already existed before `T_request` (confirmation, invalidation, horizon
resolution) under its own frozen semantics, even though it MUST NOT create
any new episode. `version_switch.assert_provenance_authorized_for_new_creation()`
returns `None`/raises throughout a drain BY DESIGN — reusing it as a
lifecycle gate would freeze exactly the episodes §3.1 requires to keep
progressing, and drain would never complete. This module therefore does
not consult the version-switch state at all. What it enforces instead is
**semantic-tuple continuity**: the transition event must recompute the
SAME `episode_id`, which (per §2.1a's identity inputs) forces
`model_family`/`rules_version`/`calculation_version`/`symbol`/
`market_type`/`direction`/`setup_family`/`structural_anchor`/`t_create`
to be the episode's own frozen creation values. A `NEW`-tuple provenance
therefore cannot mutate an `OLD` episode: it would produce a different
`episode_id` and is refused. `decision_code_version` is also required to
equal the creation event's value (§3.1): exclusion from `episode_id`
prevents identity forking, it does not authorize reinterpretation. The
concrete drain-status query remains deferred (`ports.py`); this unit does
not consume drain status.

**Unit 1's persisted history is the only state (§12.10/§32).** There is no
in-memory lifecycle cache, no "last seen" object, no notification state.
Given the same reconstructed `V2EpisodeHistory` and the same boundary
facts, a freshly-started process reaches the identical decision.

**Storage.** None added. No new table, no migration, no new reader: the
episode side is Unit 1's `reconstruct_episode_history()`, and the current
boundary's facts are the already-merged H2 aligned-input snapshot
(`aligned_inputs.py`), projected here by value.
"""
from __future__ import annotations

import math
from collections.abc import Mapping as _AbcMapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from typing import Any, Mapping, Optional, Sequence

from analytics.forecasting_v2._validation import (
    nonblank, one_of, validate_calculation_version, validate_feature_schema_version,
    validate_market_type, validate_symbol,
)
from analytics.forecasting_v2.aligned_inputs import V2_REFERENCE_EXCHANGE
from analytics.forecasting_v2.alignment import (
    V2AlignmentError, TIMEFRAME_MINUTES, selected_bucket,
)
from analytics.forecasting_v2.compression_breakout import (
    COMPRESSION_CONFIRMATION_MAX_AGE_5M_BUCKETS,
)
from analytics.forecasting_v2.confirmed_breakout import (
    CONFIRMED_BREAKOUT_CONFIRMATION_MAX_AGE_5M_BUCKETS,
)
from analytics.forecasting_v2.decision_provenance import V2DecisionProvenance
from analytics.forecasting_v2.episode_creation import (
    CREATION_FACTS_KEY, read_creation_facts,
)
from analytics.forecasting_v2.episode_history import (
    ANCHOR_BUCKET_TS, NON_TERMINAL_EPISODE_STATES, V2EpisodeHistory,
    V2EpisodeHistoryError, canonical_decimal_text, deep_freeze_json,
)
from analytics.forecasting_v2.event_factory import build_v2_episode_event
from analytics.forecasting_v2.events import (
    COMPRESSION_BREAKOUT, CONFIRMED, CONFIRMED_BREAKOUT, EARLY_SIGNAL, EXPIRED,
    INVALIDATED, LONG, SHORT, TREND_PULLBACK, V2EpisodeEvent,
)
from analytics.forecasting_v2.family_quality import (
    FAMILY_MIN_CONFIDENCE, FAMILY_MIN_COVERAGE, family_quality,
)
from analytics.forecasting_v2.provenance import V2EventProvenance
from analytics.forecasting_v2.trend_pullback import PULLBACK_MAX_AGE_15M_BUCKETS

__all__ = [
    "V2EpisodeLifecycleError",
    # frozen family constants (§14/§7.1)
    "CANDIDATE_MAX_AGE", "RESUMPTION_MIN_AGREEMENT", "REQUIRED_METRIC_FAMILY",
    "REEVALUATION_TIMEFRAME", "DECISION_TIMEFRAME", "DECISION_BUCKET",
    # family signal vocabulary
    "SIGNAL_CONFIRM", "SIGNAL_FALSE_BREAK", "SIGNAL_HOLD", "SIGNAL_UNAVAILABLE",
    "SIGNAL_REJECTED", "FAMILY_SIGNALS",
    # outcome vocabulary
    "LIFECYCLE_NO_CHANGE", "LIFECYCLE_PRECONFIRMATION_UPDATE", "LIFECYCLE_CONFIRMED",
    "LIFECYCLE_INVALIDATED_FALSE_BREAK", "LIFECYCLE_EXPIRED_CANDIDATE_AGE",
    "LIFECYCLE_OUTCOMES", "OUTCOME_NEW_STATE",
    # persisted keys
    "LIFECYCLE_EVIDENCE_KEY", "LIFECYCLE_TRANSITION_KEY", "OPERATIONAL_FACTS_KEY",
    # value objects
    "V2BoundaryFacts", "V2FamilySignal", "V2TrendPullbackReevaluationWindow",
    "V2OperationalFacts", "V2LifecycleDecision", "V2LifecycleAuthorization",
    # readers over persisted history
    "read_candidate_deadline", "read_detection_boundary", "read_operational_facts",
    # family evaluators
    "evaluate_trend_pullback_confirmation",
    "evaluate_compression_breakout_confirmation",
    "evaluate_confirmed_breakout_confirmation",
    "evaluate_family_signal",
    # composition
    "derive_trend_pullback_reevaluation",
    "evaluate_early_signal_transition",
    "build_episode_transition_event",
]


class V2EpisodeLifecycleError(ValueError):
    """Malformed or impossible Stage 6 unit 3 input: a non-`EARLY_SIGNAL`
    (or terminal) episode handed to the `EARLY_SIGNAL` evaluator, an
    off-grid/naive/non-UTC decision boundary, a boundary at or before the
    episode's own `T_detect`, a boundary strictly beyond the episode's
    candidate-age deadline while the persisted state is still
    `EARLY_SIGNAL`, boundary facts resolved for a different bucket/scope
    than `T`, a persisted creation payload missing a frozen fact this
    unit's own family rule requires, a re-evaluation that does not belong
    to this episode, or a provenance that would not reproduce this
    episode's own identity. Never raised for an ordinary non-event: HOLD,
    UNAVAILABLE required-family quality, and "nothing changed" are all
    legitimate results, not errors."""


# ============================================================================
# §14/§7.1 — frozen candidate-age deadlines and confirmation thresholds
# ============================================================================
DECISION_TIMEFRAME = "5m"
DECISION_BUCKET = timedelta(minutes=TIMEFRAME_MINUTES[DECISION_TIMEFRAME])
# §7.1/§12.2a mechanism (1): TREND_PULLBACK's own structural leg is
# re-measured at LATER 15m boundaries. This is the RE-EVALUATION cadence and
# is deliberately NOT the confirmation cadence -- confirmation is checked at
# every later 5m boundary (§14's own amended worked vector says so in as many
# words: "§7.1's 15m-only cadence governs NEW-CANDIDATE FORMATION, never
# confirmation of an already-EARLY_SIGNAL episode").
REEVALUATION_TIMEFRAME = "15m"
_REEVALUATION_BUCKET = timedelta(minutes=TIMEFRAME_MINUTES[REEVALUATION_TIMEFRAME])

# §14's frozen per-family max candidate age (EARLY_SIGNAL -> CONFIRMED
# deadline), each derived from the family detector's OWN already-frozen
# bucket-count constant rather than re-typed as a second literal, so a
# family's window can never drift between Stage 5 and Stage 6.
CANDIDATE_MAX_AGE = MappingProxyType({
    # 8 x 15m = 2h -- an AGE WINDOW, never "8 confirmation attempts" (§14).
    TREND_PULLBACK: PULLBACK_MAX_AGE_15M_BUCKETS * _REEVALUATION_BUCKET,
    # 3 x 5m = 15m
    COMPRESSION_BREAKOUT: COMPRESSION_CONFIRMATION_MAX_AGE_5M_BUCKETS * DECISION_BUCKET,
    # 8 x 5m = 40m
    CONFIRMED_BREAKOUT: CONFIRMED_BREAKOUT_CONFIRMATION_MAX_AGE_5M_BUCKETS * DECISION_BUCKET,
})
assert CANDIDATE_MAX_AGE[TREND_PULLBACK] == timedelta(hours=2)
assert CANDIDATE_MAX_AGE[COMPRESSION_BREAKOUT] == timedelta(minutes=15)
assert CANDIDATE_MAX_AGE[CONFIRMED_BREAKOUT] == timedelta(minutes=40)

# §7.1's frozen TREND_PULLBACK resumption trigger threshold. INCLUSIVE
# (">= 2/3"), and deliberately unrelated to §13.2a's separate STRICT "> 0.5"
# WEAKENING threshold -- §14's own worked vector states that in as many words.
RESUMPTION_MIN_AGREEMENT = 2.0 / 3.0

# §6.3a's required metric family per Unit 3 decision. Every family's
# confirmation / false-break / HOLD check is a pure `price_structure` fact:
# TREND_PULLBACK reads `price_move_pct_median`/`price_direction_agreement`;
# both breakout families read the reference exchange's own closed 5m close.
# Deliberately a per-family map rather than one constant, so a future
# family with a different required set changes ONE entry.
REQUIRED_METRIC_FAMILY = MappingProxyType({
    TREND_PULLBACK: ("price_structure",),
    COMPRESSION_BREAKOUT: ("price_structure",),
    CONFIRMED_BREAKOUT: ("price_structure",),
})

_SETUP_FAMILIES = (TREND_PULLBACK, COMPRESSION_BREAKOUT, CONFIRMED_BREAKOUT)
assert set(CANDIDATE_MAX_AGE) == set(REQUIRED_METRIC_FAMILY) == set(_SETUP_FAMILIES)

# The two breakout families are exactly the ones whose §7 text defines a
# pre-confirmation false-break rule. TREND_PULLBACK has none: its
# pre-confirmation invalidation is §10's generic invalidation_price crossing,
# which Unit 4 owns and this module never evaluates.
_FALSE_BREAK_FAMILIES = (COMPRESSION_BREAKOUT, CONFIRMED_BREAKOUT)


# ---- family signal vocabulary (§21's four-category discipline) --------------
SIGNAL_CONFIRM = "CONFIRM"
SIGNAL_FALSE_BREAK = "FALSE_BREAK"
# §21's NEUTRAL category: a real measured value that indicates no qualifying
# condition (a §7.2/§7.3 boundary-equality close, a §7.1 trigger that did not
# hold). The market DID produce this observation.
SIGNAL_HOLD = "HOLD"
# §21's UNAVAILABLE category: the required input does not exist / cannot be
# computed at this boundary (an absent consensus row, a NULL family quality
# value, a §11 reference close that fails its fail-closed gate).
SIGNAL_UNAVAILABLE = "UNAVAILABLE"
# §21's REJECTED category: the required input EXISTS but a hard gate
# disqualifies it (§6.3a coverage/confidence below its frozen floor).
# Deliberately NOT a spelling of UNAVAILABLE -- coverage 0.50 against a 2/3
# floor is a real, present measurement, and a reader of the persisted event
# must be able to tell the two apart.
SIGNAL_REJECTED = "REJECTED"
FAMILY_SIGNALS = (
    SIGNAL_CONFIRM, SIGNAL_FALSE_BREAK, SIGNAL_HOLD, SIGNAL_UNAVAILABLE, SIGNAL_REJECTED)
# The two categories that mean "this boundary's family predicate was not
# successfully evaluated at all" (§21, §6.3a). Distinct from HOLD, which IS a
# successful evaluation that happened to be neutral.
_UNEVALUABLE_SIGNALS = frozenset({SIGNAL_UNAVAILABLE, SIGNAL_REJECTED})


# ---- outcome vocabulary ----------------------------------------------------
LIFECYCLE_NO_CHANGE = "NO_CHANGE"
LIFECYCLE_PRECONFIRMATION_UPDATE = "PRECONFIRMATION_UPDATE"
LIFECYCLE_CONFIRMED = "CONFIRMED"
LIFECYCLE_INVALIDATED_FALSE_BREAK = "INVALIDATED_FALSE_BREAK"
LIFECYCLE_EXPIRED_CANDIDATE_AGE = "EXPIRED_CANDIDATE_AGE"
LIFECYCLE_OUTCOMES = (
    LIFECYCLE_NO_CHANGE, LIFECYCLE_PRECONFIRMATION_UPDATE, LIFECYCLE_CONFIRMED,
    LIFECYCLE_INVALIDATED_FALSE_BREAK, LIFECYCLE_EXPIRED_CANDIDATE_AGE,
)

# The §13.2 state each outcome lands the episode in. PRECONFIRMATION_UPDATE
# and NO_CHANGE both stay in EARLY_SIGNAL -- the first records a changed
# operational fact as a new immutable event (§9), the second writes nothing
# at all (§12.11).
OUTCOME_NEW_STATE = MappingProxyType({
    LIFECYCLE_NO_CHANGE: EARLY_SIGNAL,
    LIFECYCLE_PRECONFIRMATION_UPDATE: EARLY_SIGNAL,
    LIFECYCLE_CONFIRMED: CONFIRMED,
    LIFECYCLE_INVALIDATED_FALSE_BREAK: INVALIDATED,
    LIFECYCLE_EXPIRED_CANDIDATE_AGE: EXPIRED,
})
assert set(OUTCOME_NEW_STATE) == set(LIFECYCLE_OUTCOMES)

# Outcomes that require a new immutable history event (§12.11: routing/
# re-observation alone never does; a lifecycle transition or a §9 zone change
# always does).
_EVENT_REQUIRED = frozenset({
    LIFECYCLE_PRECONFIRMATION_UPDATE, LIFECYCLE_CONFIRMED,
    LIFECYCLE_INVALIDATED_FALSE_BREAK, LIFECYCLE_EXPIRED_CANDIDATE_AGE,
})

# Which family signals each outcome is REACHABLE FROM. A persisted history
# event states both what was observed and what followed; the two must agree,
# or the record is self-contradictory (a "CONFIRMED" whose own evidence block
# says the trigger never held is worse than no record at all).
#
# EXPIRED is the one outcome reachable from several: §14's amended deadline
# rule closes the hard age budget on a real neutral HOLD, on an UNAVAILABLE
# input, AND on a REJECTED one -- while requiring the persisted evidence to
# say WHICH. It is deliberately NOT reachable from CONFIRM or FALSE_BREAK:
# those resolve the deadline boundary themselves.
_OUTCOME_ALLOWED_SIGNALS = MappingProxyType({
    LIFECYCLE_CONFIRMED: frozenset({SIGNAL_CONFIRM}),
    LIFECYCLE_INVALIDATED_FALSE_BREAK: frozenset({SIGNAL_FALSE_BREAK}),
    LIFECYCLE_EXPIRED_CANDIDATE_AGE: frozenset(
        {SIGNAL_HOLD, SIGNAL_UNAVAILABLE, SIGNAL_REJECTED}),
    # A §12.2a operational update and a no-op are both reached only when the
    # boundary did NOT resolve the episode -- so neither is reachable from a
    # CONFIRM signal either. (§14's "the trigger held but §11's confirmation
    # close is unavailable" case does not reach here carrying CONFIRM: it is
    # re-categorised as UNAVAILABLE, with `resumption_trigger_held: True`
    # preserved in its evidence, because the transition was not materialized
    # and the record must say so without calling it a failed trigger.)
    LIFECYCLE_PRECONFIRMATION_UPDATE: frozenset(
        {SIGNAL_HOLD, SIGNAL_UNAVAILABLE, SIGNAL_REJECTED}),
    LIFECYCLE_NO_CHANGE: frozenset(
        {SIGNAL_HOLD, SIGNAL_UNAVAILABLE, SIGNAL_REJECTED}),
})
assert set(_OUTCOME_ALLOWED_SIGNALS) == set(LIFECYCLE_OUTCOMES)


# ---- persisted payload keys ------------------------------------------------
# What this boundary decided FROM (evidence/inputs) vs what it decided
# (the transition and the operational facts it froze/updated) -- the same
# decision_snapshot/event_payload split events.py itself defines.
LIFECYCLE_EVIDENCE_KEY = "lifecycle_evidence"
LIFECYCLE_TRANSITION_KEY = "lifecycle_transition"
OPERATIONAL_FACTS_KEY = "operational_facts"

# Persisted operational-fact field names (TREND_PULLBACK's §12.2a mutable
# shape). Named constants so the writer and the reader below can never drift.
_OF_PULLBACK_EXTREME = "pullback_extreme"
_OF_DYNAMIC_BOUND = "dynamic_bound"
_OF_ENTRY_ZONE_LOWER = "entry_zone_lower"
_OF_ENTRY_ZONE_UPPER = "entry_zone_upper"
_OF_INVALIDATION_PRICE = "invalidation_price"
_OF_PROTECTION_BUFFER = "protection_buffer"
_OF_SOURCE_BUCKET = "source_bucket"
_OF_SOURCE = "source"

OPERATIONAL_SOURCE_CREATION = "CREATION"
OPERATIONAL_SOURCE_REEVALUATION = "REEVALUATION"
OPERATIONAL_SOURCE_CONFIRMATION = "CONFIRMATION"

# Unit 2's own creation-facts field names, read back here. Deliberately
# re-declared as this module's own read-side names rather than importing
# Unit 2's private constants: they are the persisted JSON contract, and a
# reader that silently followed a writer's private rename would be worse
# than one that fails a test.
_CF_T_DETECT = "t_detect"
_CF_ENTRY_ZONE_LOWER = "entry_zone_lower"
_CF_ENTRY_ZONE_UPPER = "entry_zone_upper"
_CF_INVALIDATION_PRICE = "invalidation_price"
_CF_PROTECTION_BUFFER = "protection_buffer"
_CF_FAMILY_FACTS = "family_facts"

_FF_PULLBACK_EXTREME = "pullback_extreme"
_FF_BUCKET_15M = "bucket_15m"
_FF_RANGE_LOW = "range_low"
_FF_RANGE_HIGH = "range_high"
_FF_RAW_LEVEL_PRICE = "raw_level_price"


# ============================================================================
# small local validation helpers
# ============================================================================
def _validate_decision_boundary(value: Any, name: str) -> datetime:
    """A legal V2 5m decision boundary `T` (§1.3), delegated to
    `alignment.selected_bucket` -- the same canonical source of truth every
    other V2 module uses, never a local minute-arithmetic copy."""
    if not isinstance(value, datetime):
        raise V2EpisodeLifecycleError(
            f"{name} must be a datetime, got {type(value).__name__}")
    if value.tzinfo is None or value.utcoffset() is None:
        raise V2EpisodeLifecycleError(f"{name} must be timezone-aware, got naive {value!r}")
    if value.utcoffset() != timedelta(0):
        raise V2EpisodeLifecycleError(
            f"{name} must be UTC (offset 0), got {value!r} (offset {value.utcoffset()})")
    try:
        selected_bucket(DECISION_TIMEFRAME, value)
    except V2AlignmentError as exc:
        raise V2EpisodeLifecycleError(
            f"{name} is not a legal V2 5m decision boundary: {exc}") from exc
    except Exception as exc:  # noqa: BLE001 - adversarial tzinfo, never leaked raw
        raise V2EpisodeLifecycleError(
            f"{name} failed decision-boundary validation: "
            f"{type(exc).__name__}: {exc}") from exc
    return value


def _validate_bucket_start(value: Any, name: str, *, timeframe: str) -> datetime:
    """An exact bucket START on `timeframe`'s canonical grid, using
    `selected_bucket`'s own round-trip technique (`v` is a legal start iff
    `selected_bucket(tf, v + tf) == v`) -- the identical technique
    `episode_history.py` and both breakout detectors already use."""
    if not isinstance(value, datetime):
        raise V2EpisodeLifecycleError(
            f"{name} must be a datetime, got {type(value).__name__}")
    if value.tzinfo is None or value.utcoffset() is None or value.utcoffset() != timedelta(0):
        raise V2EpisodeLifecycleError(f"{name} must be a UTC-aware datetime, got {value!r}")
    if value.second or value.microsecond:
        raise V2EpisodeLifecycleError(f"{name} must be a whole minute, got {value!r}")
    delta = timedelta(minutes=TIMEFRAME_MINUTES[timeframe])
    try:
        canonical = selected_bucket(timeframe, value + delta)
    except V2AlignmentError as exc:
        raise V2EpisodeLifecycleError(
            f"{name} is not a legal {timeframe} bucket start: {exc}") from exc
    if canonical != value:
        raise V2EpisodeLifecycleError(
            f"{name}={value.isoformat()!r} is not aligned to the canonical {timeframe} bucket "
            f"grid (the containing bucket starts at {canonical.isoformat()!r})")
    return value


def _finite_price(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise V2EpisodeLifecycleError(
            f"{name} must be a real number, got {type(value).__name__}: {value!r}")
    v = float(value)
    if not math.isfinite(v):
        raise V2EpisodeLifecycleError(f"{name} must be finite, got {value!r}")
    if v <= 0:
        raise V2EpisodeLifecycleError(f"{name} must be strictly positive, got {value!r}")
    return v


def _exact(value: float, name: str) -> Decimal:
    """The exact decimal value of a persisted/observed price, for the
    strict/equality three-way comparisons §7.2/§7.3 freeze.

    `Decimal(str(x))` is the same canonical float->exact conversion §12.5
    already mandates for tick normalization: `str()` of a float is its
    shortest round-tripping representation, so this is lossless AND
    deterministic across processes. Comparing raw floats would make
    `close == range_high` -- a real, frozen, neutral HOLD outcome -- depend
    on binary representation accidents."""
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise V2EpisodeLifecycleError(
            f"{name}={value!r} is not an exact decimal: {exc}") from exc


def _mapping(value: Any, name: str) -> Mapping:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, _AbcMapping):
        raise V2EpisodeLifecycleError(
            f"{name} must be a Mapping, got {type(value).__name__}")
    return value


def _freeze(value: Any, name: str) -> Any:
    """Deep-freeze one JSON-shaped payload under Unit 1's single freeze
    semantics, re-raised in this module's own error hierarchy."""
    try:
        return deep_freeze_json(value, name)
    except V2EpisodeHistoryError as exc:
        raise V2EpisodeLifecycleError(f"{name} is not JSON-shaped: {exc}") from exc


def _direction_sign(direction: str) -> int:
    """The ternary sign a `price_move_pct_median` must carry to agree with
    the episode's direction (`STAGE2_SPEC.md` §11.2's ternary convention)."""
    return 1 if direction == LONG else -1


def _ternary_sign(value: float) -> int:
    """`STAGE2_SPEC.md` §11.2: negative -> -1, exactly flat -> 0, positive
    -> +1. A flat median is genuinely neutral and matches NO direction."""
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


# ============================================================================
# one boundary's already-resolved, coherent current facts
# ============================================================================
# The §11 reference-vector gate, verbatim: a reference close is usable only
# when `is_usable is True`, `has_gap is False`, `bars_present ==
# bars_expected`, and `close_price is not None`. A small local copy, matching
# the established codebase precedent (`aligned_inputs.py`,
# `confirmed_breakout.py` each carry their own) rather than importing another
# module's private helper.
_REFERENCE_GATE_FIELDS = ("is_usable", "has_gap", "bars_present", "bars_expected", "close_price")


@dataclass(frozen=True)
class V2BoundaryFacts:
    """ONE logical decision boundary's already-resolved current facts, by
    value (§3.4's "one coherent data view per logical decision") -- WITH the
    semantic scope that produced them.

    This module reads nothing itself. The caller resolves exactly one
    coherent view for `T` -- in production, inside an H2e coherent read
    session over one publication-CLEAN scope -- and hands the two 5m rows
    every Unit 3 predicate consumes:

      - `consensus_5m`: the consensus row at `selected_bucket("5m", T)`,
        source of `TREND_PULLBACK`'s resumption trigger and of §6.3a's
        per-family `coverage_by_metric`/`data_confidence_by_metric` gate.
      - `reference_feature_5m`: the REFERENCE EXCHANGE's own 5m row at the
        same bucket, source of both breakout families' closed-bucket close
        (§11: exact tradable price levels come from the single canonical
        reference exchange, never a consensus aggregate).

    Either may be `None` -- legitimately UNAVAILABLE, never an error (§21's
    Unavailable category).

    **The scope fields are not decoration; they are what makes §3.2
    enforceable.** §3.2 forbids a result computed under provenance tuple A
    from being persisted as tuple B, and an earlier draft of this type
    discarded the aligned snapshot's identity entirely -- which let a
    decision be computed from `calculation_version` B's data and then
    stamped onto an episode whose own frozen identity is A. That is the
    same violation arriving from the INPUT side, and no amount of
    event-construction authorization downstream can repair a decision that
    was already computed from foreign data. So this type carries the exact
    snapshot identity by value (`symbol`, `market_type`,
    `calculation_version`, `feature_schema_version`, `reference_exchange`),
    `from_aligned_inputs()` preserves it, and
    `evaluate_early_signal_transition()` binds it to the episode BEFORE any
    predicate runs.

    A row that IS present is held to its own identity twice over: its
    `timeframe`/`bucket_ts` must be exactly `"5m"` and
    `selected_bucket("5m", T)` (the no-lookahead/coherence guard, §1/§2 --
    a caller cannot hand this unit a newer or older bucket), and any
    identity field the row itself physically carries (`symbol`,
    `market_type`, `calculation_version`, `feature_schema_version`, and the
    reference row's own `exchange`) must equal this object's declared
    scope. A row cannot be laundered through a mismatched envelope."""
    T: datetime
    symbol: str
    market_type: str
    calculation_version: str
    feature_schema_version: int
    reference_exchange: str = V2_REFERENCE_EXCHANGE
    consensus_5m: Optional[Mapping] = None
    reference_feature_5m: Optional[Mapping] = None

    def __post_init__(self) -> None:
        T = _validate_decision_boundary(self.T, "T")
        object.__setattr__(self, "T", T)
        validate_symbol(self.symbol, V2EpisodeLifecycleError)
        validate_market_type(self.market_type, V2EpisodeLifecycleError)
        validate_calculation_version(self.calculation_version, V2EpisodeLifecycleError)
        validate_feature_schema_version(self.feature_schema_version, V2EpisodeLifecycleError)
        # §11 freezes ONE canonical V2 reference exchange, and forbids
        # silent switching. A snapshot resolved against any other exchange
        # cannot supply this unit's exact price levels.
        if self.reference_exchange != V2_REFERENCE_EXCHANGE:
            raise V2EpisodeLifecycleError(
                f"reference_exchange must be the canonical V2 reference exchange "
                f"{V2_REFERENCE_EXCHANGE!r}, got {self.reference_exchange!r} -- §11 forbids "
                "silently sourcing an exact price level from another exchange")
        expected_bucket = selected_bucket(DECISION_TIMEFRAME, T)
        for name in ("consensus_5m", "reference_feature_5m"):
            row = getattr(self, name)
            if row is None:
                continue
            row = _mapping(row, name)
            self._assert_row_identity(row, name=name, expected_bucket=expected_bucket)
            object.__setattr__(self, name, _freeze(dict(row), name))
        # A PRESENT reference row is inspected now, not lazily inside a
        # later predicate. Missing/malformed §11 gate fields are corruption
        # and must not be skippable by a quality-gate short-circuit.
        if self.reference_feature_5m is not None:
            _ = self.reference_close

    def _assert_row_identity(
        self, row: Mapping, *, name: str, expected_bucket: datetime,
    ) -> None:
        timeframe = row.get("timeframe")
        if timeframe != DECISION_TIMEFRAME:
            raise V2EpisodeLifecycleError(
                f"{name} must be a {DECISION_TIMEFRAME!r} row, got timeframe={timeframe!r} -- "
                "Unit 3's confirmation/false-break checks are defined on the closed 5m bucket "
                "only (§7.1/§7.2/§7.3), never inferred from another timeframe (§22)")
        bucket_ts = row.get("bucket_ts")
        if bucket_ts != expected_bucket:
            raise V2EpisodeLifecycleError(
                f"{name} carries bucket_ts={bucket_ts!r} but this decision boundary's own "
                f"selected 5m bucket is {expected_bucket.isoformat()!r} -- a lifecycle "
                "transition is never decided from a bucket other than the one §1.3 selects "
                "for T (no-lookahead, §1/§2)")
        # Identity fields the row PHYSICALLY carries are validated against
        # this envelope's declared scope -- never ignored. A row absent a
        # field is not evidence of agreement, but a row that carries a
        # DIFFERENT value is proof of a mismatched snapshot.
        declared = {
            "symbol": self.symbol, "market_type": self.market_type,
            "calculation_version": self.calculation_version,
            "feature_schema_version": self.feature_schema_version,
        }
        if name == "reference_feature_5m":
            declared["exchange"] = self.reference_exchange
        for field, expected in declared.items():
            if field in row and row[field] != expected:
                raise V2EpisodeLifecycleError(
                    f"{name} carries {field}={row[field]!r} but this boundary snapshot declares "
                    f"{expected!r} -- a decision may not be computed from a row belonging to a "
                    "different semantic scope (§3.2)")

    @property
    def decision_bucket(self) -> datetime:
        """`selected_bucket("5m", T)` -- the ONE closed 5m bucket every Unit
        3 predicate reads (`bucket_ts = T - 5m`, `bucket_end = T`)."""
        return selected_bucket(DECISION_TIMEFRAME, self.T)

    @property
    def reference_close(self) -> Optional[float]:
        """The reference exchange's closed 5m `close_price`, or `None` when
        §11's fail-closed gate does not pass.

        `None` is UNAVAILABLE, never a fallback: §11 forbids silently
        switching to another exchange for an exact price level, and §22
        forbids substituting a consensus aggregate for it. A row that is
        PRESENT but missing a gate field is corruption, not absence, and
        raises."""
        row = self.reference_feature_5m
        if row is None:
            return None
        missing = [f for f in _REFERENCE_GATE_FIELDS if f not in row]
        if missing:
            raise V2EpisodeLifecycleError(
                f"reference_feature_5m is missing §11 gate field(s) {missing!r} -- a genuinely "
                "written reference row always carries them, so this is corruption, not absence")
        is_usable, has_gap = row["is_usable"], row["has_gap"]
        for field, value in (("is_usable", is_usable), ("has_gap", has_gap)):
            if not isinstance(value, bool):
                raise V2EpisodeLifecycleError(
                    f"reference_feature_5m {field} must be a bool, got {type(value).__name__}")
        bars_present, bars_expected = row["bars_present"], row["bars_expected"]
        for field, value in (("bars_present", bars_present), ("bars_expected", bars_expected)):
            if isinstance(value, bool) or not isinstance(value, int):
                raise V2EpisodeLifecycleError(
                    f"reference_feature_5m {field} must be an int, got {type(value).__name__}")
        close_price = row["close_price"]
        if close_price is not None:
            close_price = _finite_price(close_price, "reference_feature_5m close_price")
        gate_passes = (
            is_usable is True and has_gap is False
            and bars_present == bars_expected and close_price is not None)
        return close_price if gate_passes else None

    def required_family_quality(self, setup_family: str) -> "Optional[V2FamilySignal]":
        """§6.3a's per-family gate, resolved into §21's DISTINCT categories
        -- or `None` when every required family passes.

        Deliberately NOT a boolean. `family_quality_ok()` collapses "the
        consensus row is absent", "this family's own value is NULL",
        "coverage is below the floor" and "confidence is below the floor"
        into one `False`, which destroys exactly the distinction §21 exists
        to preserve: an ABSENT input (Unavailable) and a PRESENT input a
        hard gate disqualified (Rejected) are different facts, and a reader
        of the persisted event cannot recover which one occurred. This
        reads the richer `family_quality()` primitive and reports the real
        category.

        Scoped strictly to `REQUIRED_METRIC_FAMILY[setup_family]` -- an
        unrelated degraded family can never suppress a Unit 3 transition,
        and the global `min_coverage_ratio`/`consensus_confidence` rollup is
        never read."""
        one_of(setup_family, "setup_family", _SETUP_FAMILIES, V2EpisodeLifecycleError)
        base = {"decision_bucket": self.decision_bucket.isoformat(),
                "required_families": list(REQUIRED_METRIC_FAMILY[setup_family])}
        if self.consensus_5m is None:
            return V2FamilySignal(
                signal=SIGNAL_UNAVAILABLE, reason="CONSENSUS_ROW_ABSENT", evidence=base)
        for family in REQUIRED_METRIC_FAMILY[setup_family]:
            try:
                quality = family_quality(self.consensus_5m, family=family)
            except ValueError as exc:      # V2FamilyQualityError: malformed PRESENT data
                raise V2EpisodeLifecycleError(
                    f"consensus_5m carries malformed per-family quality data for {family!r}: "
                    f"{exc}") from exc
            evidence = dict(base, family=family, coverage_ratio=quality.coverage_ratio,
                            confidence=quality.confidence,
                            min_coverage=FAMILY_MIN_COVERAGE,
                            min_confidence=FAMILY_MIN_CONFIDENCE)
            # PRESENT-but-NULL is genuine unavailability for that fact;
            # PRESENT-and-below-floor is a hard gate rejecting real data.
            if quality.coverage_ratio is None or quality.confidence is None:
                return V2FamilySignal(
                    signal=SIGNAL_UNAVAILABLE, reason="REQUIRED_FAMILY_QUALITY_UNAVAILABLE",
                    evidence=evidence)
            if quality.coverage_ratio < FAMILY_MIN_COVERAGE:
                return V2FamilySignal(
                    signal=SIGNAL_REJECTED, reason="REQUIRED_FAMILY_COVERAGE_BELOW_FLOOR",
                    evidence=evidence)
            if quality.confidence < FAMILY_MIN_CONFIDENCE:
                return V2FamilySignal(
                    signal=SIGNAL_REJECTED, reason="REQUIRED_FAMILY_CONFIDENCE_BELOW_FLOOR",
                    evidence=evidence)
        return None

    @classmethod
    def from_aligned_inputs(cls, aligned) -> "V2BoundaryFacts":
        """Project an already-loaded `aligned_inputs.V2AlignedInputs`
        snapshot -- the canonical H2 coherent read path -- into this unit's
        narrow by-value input.

        A pure projection that preserves the snapshot's full semantic scope:
        nothing is re-read, the 5m rows arrive exactly as that snapshot
        resolved them for `T`, and `symbol`/`market_type`/
        `calculation_version`/`feature_schema_version`/`reference_exchange`
        travel with them so the episode binding below has something real to
        check against."""
        tf = aligned.by_timeframe[DECISION_TIMEFRAME]
        return cls(
            T=aligned.T, symbol=aligned.symbol, market_type=aligned.market_type,
            calculation_version=aligned.calculation_version,
            feature_schema_version=aligned.feature_schema_version,
            reference_exchange=aligned.reference_exchange,
            consensus_5m=tf.consensus, reference_feature_5m=tf.reference_feature)


@dataclass(frozen=True)
class V2FamilySignal:
    """One family's own verdict for this boundary, BEFORE deadline/expiry
    composition: `CONFIRM`, `FALSE_BREAK`, `HOLD`, `UNAVAILABLE`, or
    `REJECTED` -- §21's categories, kept distinct rather than collapsed.

    `evidence` is the by-value input this verdict was computed from --
    persisted verbatim into the transition event's `decision_snapshot` so
    the decision is independently auditable after restart without re-reading
    market data."""
    signal: str
    reason: str
    evidence: Mapping

    def __post_init__(self) -> None:
        one_of(self.signal, "signal", FAMILY_SIGNALS, V2EpisodeLifecycleError)
        nonblank(self.reason, "reason", V2EpisodeLifecycleError)
        object.__setattr__(
            self, "evidence", _freeze(dict(_mapping(self.evidence, "evidence")), "evidence"))


# ============================================================================
# reading the episode's own frozen creation facts
# ============================================================================
def read_detection_boundary(history: V2EpisodeHistory) -> datetime:
    """The episode's own `T_detect` -- its immutable creation decision
    boundary (§12.2), which is what §14's candidate age is measured from.

    Sourced from the creation IDENTITY (`t_create`), which participates in
    `episode_id` and is therefore already proven self-consistent by Unit 1's
    reconstruction. Unit 2's separately-persisted `creation_facts.t_detect`
    is cross-checked against it and a disagreement fails closed -- two
    recorded spellings of one fact must never be allowed to drift into two
    different deadlines."""
    _require_history(history)
    t_create = history.creation_identity.t_create
    facts = _creation_facts(history)
    raw = facts.get(_CF_T_DETECT)
    if raw is not None:
        if not isinstance(raw, str):
            raise V2EpisodeLifecycleError(
                f"episode {history.episode_id!r} persisted {_CF_T_DETECT}={raw!r} must be an "
                f"ISO-8601 string, got {type(raw).__name__}")
        try:
            recorded = datetime.fromisoformat(raw)
        except (TypeError, ValueError) as exc:
            raise V2EpisodeLifecycleError(
                f"episode {history.episode_id!r} persisted {_CF_T_DETECT}={raw!r} is not a "
                f"parseable ISO-8601 datetime: {exc}") from exc
        if recorded != t_create:
            raise V2EpisodeLifecycleError(
                f"episode {history.episode_id!r} records {_CF_T_DETECT}={recorded.isoformat()!r} "
                f"but its creation identity's t_create is {t_create.isoformat()!r} -- §14's "
                "candidate age has exactly one origin, and these two disagree")
    return t_create


def read_candidate_deadline(history: V2EpisodeHistory) -> datetime:
    """§14's frozen `EARLY_SIGNAL -> CONFIRMED` deadline for this episode:
    `T_detect + CANDIDATE_MAX_AGE[setup_family]`.

    The deadline boundary is INCLUSIVE -- it is itself a fully valid
    confirmation opportunity (§13.1/§14), never an automatic expiry."""
    t_detect = read_detection_boundary(history)
    family = history.creation_identity.setup_family
    deadline = t_detect + CANDIDATE_MAX_AGE[family]
    # A frozen family window added to a legal 5m boundary is always another
    # legal 5m boundary; assert it rather than assume it, since every
    # eligible confirmation opportunity is a 5m boundary by construction.
    return _validate_decision_boundary(deadline, "candidate deadline")


def _creation_facts(history: V2EpisodeHistory) -> Mapping:
    try:
        return read_creation_facts(history)
    except ValueError as exc:      # V2EpisodeCreationError
        raise V2EpisodeLifecycleError(
            f"episode {history.episode_id!r} carries no usable Unit 2 "
            f"{CREATION_FACTS_KEY!r} payload, so its frozen family facts are unrecoverable: "
            f"{exc}") from exc


def _creation_family_facts(history: V2EpisodeHistory) -> Mapping:
    facts = _creation_facts(history)
    family_facts = facts.get(_CF_FAMILY_FACTS)
    if family_facts is None:
        raise V2EpisodeLifecycleError(
            f"episode {history.episode_id!r}'s creation facts carry no {_CF_FAMILY_FACTS!r} "
            "mapping -- this unit's family rules read only frozen creation-time facts and never "
            "recover them from current market data (§22)")
    return _mapping(family_facts, _CF_FAMILY_FACTS)


def _frozen_family_price(history: V2EpisodeHistory, key: str) -> float:
    """One frozen creation-time price fact (§12.2a) a breakout family's own
    confirmation/false-break rule evaluates against, BY VALUE from the
    episode's creation event -- never re-derived from current data, and
    never taken from a later independently-detected candidate."""
    family_facts = _creation_family_facts(history)
    if key not in family_facts:
        raise V2EpisodeLifecycleError(
            f"episode {history.episode_id!r} is {history.creation_identity.setup_family!r} but "
            f"its persisted creation facts carry no {key!r} -- §7.2/§7.3's confirmation boundary "
            "is a frozen creation-time fact and this unit refuses to re-derive it")
    return _finite_price(family_facts[key], f"creation {key}")


def _creation_protection_buffer(history: V2EpisodeHistory) -> Decimal:
    raw = _creation_facts(history).get(_CF_PROTECTION_BUFFER)
    if not isinstance(raw, str):
        raise V2EpisodeLifecycleError(
            f"episode {history.episode_id!r}'s persisted creation facts carry no exact "
            f"{_CF_PROTECTION_BUFFER!r} decimal string")
    try:
        buffer = Decimal(raw)
    except (InvalidOperation, ValueError) as exc:
        raise V2EpisodeLifecycleError(
            f"episode {history.episode_id!r}'s persisted {_CF_PROTECTION_BUFFER}={raw!r} is not "
            f"a valid decimal: {exc}") from exc
    if not buffer.is_finite() or buffer <= 0:
        raise V2EpisodeLifecycleError(
            f"episode {history.episode_id!r}'s persisted {_CF_PROTECTION_BUFFER}={raw!r} must be "
            "a finite, strictly positive decimal")
    return buffer


def _require_history(history: Any) -> V2EpisodeHistory:
    if not isinstance(history, V2EpisodeHistory):
        raise V2EpisodeLifecycleError(
            "history must be a V2EpisodeHistory reconstructed through Unit 1 -- a lifecycle "
            "decision is only sound if the whole persisted episode it acts on was proven valid; "
            f"got {type(history).__name__}")
    return history


def _require_early_signal(history: V2EpisodeHistory) -> V2EpisodeHistory:
    """This unit owns transitions OUT OF `EARLY_SIGNAL` and nothing else."""
    _require_history(history)
    state = history.current_state
    if state != EARLY_SIGNAL:
        raise V2EpisodeLifecycleError(
            f"episode {history.episode_id!r} is {state!r}, not {EARLY_SIGNAL!r} -- Stage 6 unit 3 "
            f"owns only transitions out of {EARLY_SIGNAL!r}; "
            + ("terminal episodes never transition again (§13.2)"
               if state not in NON_TERMINAL_EPISODE_STATES
               else "post-confirmation lifecycle is Unit 4's"))
    return history


# ============================================================================
# §7.1/§9/§12.2a — TREND_PULLBACK operational facts (the one mutable family)
# ============================================================================
@dataclass(frozen=True)
class V2OperationalFacts:
    """`TREND_PULLBACK`'s §12.2a mechanism-(1) operational shape: the facts
    its own structural leg keeps re-measuring while the episode is still
    `EARLY_SIGNAL`, and which freeze at `CONFIRMED`.

    `dynamic_bound` is §7.1's moving zone bound -- `close_price(B15')` at a
    pre-confirmation 15m re-evaluation, and `confirmation_close_price =
    close_price(B5_confirm)` at `CONFIRMED`, exactly as §7.1's three-stage
    zone formula freezes. `entry_zone_*`/`invalidation_price` are DERIVED
    here from `pullback_extreme`/`dynamic_bound`/the frozen creation
    `protection_buffer` using §7.1's exact geometry -- never accepted from a
    caller, so no caller can publish a zone the frozen formula does not
    produce.

    `COMPRESSION_BREAKOUT`/`CONFIRMED_BREAKOUT` have NO such shape: §12.2a
    freezes every one of their operational facts at creation, so this unit
    never constructs these for them."""
    direction: str
    pullback_extreme: float
    dynamic_bound: float
    entry_zone_lower: float
    entry_zone_upper: float
    invalidation_price: float
    protection_buffer: str
    source: str
    source_bucket: Optional[datetime]

    def as_payload(self) -> Mapping:
        return MappingProxyType({
            _OF_PULLBACK_EXTREME: self.pullback_extreme,
            _OF_DYNAMIC_BOUND: self.dynamic_bound,
            _OF_ENTRY_ZONE_LOWER: self.entry_zone_lower,
            _OF_ENTRY_ZONE_UPPER: self.entry_zone_upper,
            _OF_INVALIDATION_PRICE: self.invalidation_price,
            _OF_PROTECTION_BUFFER: self.protection_buffer,
            _OF_SOURCE: self.source,
            _OF_SOURCE_BUCKET: (
                None if self.source_bucket is None else self.source_bucket.isoformat()),
        })

    def same_geometry(self, other: "V2OperationalFacts") -> bool:
        """Do two operational shapes describe the SAME published geometry?

        §9 requires a pre-`CONFIRMED` zone CHANGE to be recorded as a new
        event; §12.11 forbids minting one when nothing episode-visible
        changed. Compared on the published facts only -- `source`/
        `source_bucket` are provenance, not user-visible geometry, so a
        re-evaluation that re-derives the identical zone is a no-op."""
        return (
            self.pullback_extreme == other.pullback_extreme
            and self.dynamic_bound == other.dynamic_bound
            and self.entry_zone_lower == other.entry_zone_lower
            and self.entry_zone_upper == other.entry_zone_upper
            and self.invalidation_price == other.invalidation_price)


def _build_trend_pullback_operational_facts(
    *, direction: str, pullback_extreme: float, dynamic_bound: float,
    protection_buffer: Decimal, source: str, source_bucket: Optional[datetime],
) -> V2OperationalFacts:
    """Apply §7.1's EXACT zone/invalidation geometry. LONG:
    `[pullback_extreme_low, dynamic_bound]`, `invalidation = extreme -
    buffer`. SHORT: `[dynamic_bound, pullback_extreme_high]`,
    `invalidation = extreme + buffer`."""
    extreme = _exact(pullback_extreme, "pullback_extreme")
    buffer = protection_buffer
    if direction == LONG:
        lower, upper = pullback_extreme, dynamic_bound
        invalidation = extreme - buffer
    else:
        lower, upper = dynamic_bound, pullback_extreme
        invalidation = extreme + buffer
    if invalidation <= 0:
        raise V2EpisodeLifecycleError(
            f"§7.1 invalidation_price for {direction} pullback_extreme={pullback_extreme!r} and "
            f"protection_buffer={buffer} is {invalidation} -- not a usable price level")
    if lower > upper:
        raise V2EpisodeLifecycleError(
            f"§7.1 entry zone for {direction} is inverted: [{lower!r}, {upper!r}] -- "
            f"pullback_extreme={pullback_extreme!r}, dynamic_bound={dynamic_bound!r}")
    return V2OperationalFacts(
        direction=direction, pullback_extreme=pullback_extreme, dynamic_bound=dynamic_bound,
        entry_zone_lower=lower, entry_zone_upper=upper,
        invalidation_price=float(invalidation),
        protection_buffer=canonical_decimal_text(buffer, _OF_PROTECTION_BUFFER),
        source=source, source_bucket=source_bucket)


def read_operational_facts(history: V2EpisodeHistory) -> Optional[V2OperationalFacts]:
    """The episode's CURRENTLY-VALID `TREND_PULLBACK` operational facts,
    read from its own persisted history -- the latest event that recorded
    them, falling back to the creation event's own creation facts.

    Returns `None` for the two breakout families, which have no such shape
    (§12.2a freezes all of their operational facts at creation).

    Reading them from history rather than from a cache is what makes
    restart equivalence provable: §9 requires every pre-`CONFIRMED` zone
    change to be recorded as a new immutable event, so the newest recorded
    shape IS the current one, and a fresh process reconstructs it exactly.

    **Corruption stays corruption -- nothing is silently repaired.** An
    earlier draft rebuilt the geometry from the persisted
    `pullback_extreme`/`dynamic_bound` and simply IGNORED the persisted
    `entry_zone_*`/`invalidation_price`/`protection_buffer`, so a stored
    block claiming `invalidation_price = 1` where §7.1's formula gives `95`
    was quietly "corrected" on read and the contradiction never surfaced.
    That is exactly the silent normalization §22 forbids. Every persisted
    field is now validated against what the canonical formula produces, and
    every disagreement raises. The block's own provenance
    (`source`/`source_bucket`) is validated too: an unknown source, a naive/
    non-UTC/off-grid bucket, a bucket on the wrong grid for its source type,
    or a bucket LATER than the event that recorded it are all impossible
    history."""
    _require_history(history)
    identity = history.creation_identity
    if identity.setup_family != TREND_PULLBACK:
        return None
    buffer = _creation_protection_buffer(history)
    for event in reversed(history.events):
        payload = event.event_payload.get(OPERATIONAL_FACTS_KEY)
        if payload is None:
            continue
        return _validated_persisted_operational_facts(
            history, event=event, payload=_mapping(payload, OPERATIONAL_FACTS_KEY),
            buffer=buffer)

    # No recorded update yet: the creation event's own facts are current.
    creation = _creation_facts(history)
    family_facts = _creation_family_facts(history)
    dynamic_bound = (
        creation.get(_CF_ENTRY_ZONE_UPPER) if identity.direction == LONG
        else creation.get(_CF_ENTRY_ZONE_LOWER))
    raw_bucket = family_facts.get(_FF_BUCKET_15M)
    source_bucket = None
    if isinstance(raw_bucket, str):
        source_bucket = _parse_persisted_bucket(
            history, raw_bucket, name=f"creation {_FF_BUCKET_15M}")
    derived = _build_trend_pullback_operational_facts(
        direction=identity.direction,
        pullback_extreme=_finite_price(
            family_facts.get(_FF_PULLBACK_EXTREME), f"creation {_FF_PULLBACK_EXTREME}"),
        dynamic_bound=_finite_price(dynamic_bound, "creation dynamic entry-zone bound"),
        protection_buffer=buffer, source=OPERATIONAL_SOURCE_CREATION,
        source_bucket=source_bucket)
    # Unit 2's own persisted creation geometry must agree with §7.1's formula
    # too -- a creation event whose recorded zone/invalidation contradicts its
    # own extreme/buffer is corrupt, not something to normalize away.
    _assert_persisted_geometry_agrees(
        history, derived=derived, persisted={
            _OF_ENTRY_ZONE_LOWER: creation.get(_CF_ENTRY_ZONE_LOWER),
            _OF_ENTRY_ZONE_UPPER: creation.get(_CF_ENTRY_ZONE_UPPER),
            _OF_INVALIDATION_PRICE: creation.get(_CF_INVALIDATION_PRICE),
        }, where="creation facts")
    return derived


def _parse_persisted_bucket(
    history: V2EpisodeHistory, raw: Any, *, name: str,
) -> datetime:
    if not isinstance(raw, str):
        raise V2EpisodeLifecycleError(
            f"episode {history.episode_id!r}'s persisted {name}={raw!r} must be an ISO-8601 "
            f"string, got {type(raw).__name__}")
    try:
        parsed = datetime.fromisoformat(raw)
    except (TypeError, ValueError) as exc:
        raise V2EpisodeLifecycleError(
            f"episode {history.episode_id!r}'s persisted {name}={raw!r} is not a parseable "
            f"ISO-8601 datetime: {exc}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise V2EpisodeLifecycleError(
            f"episode {history.episode_id!r}'s persisted {name}={raw!r} is naive -- every "
            "persisted V2 timestamp is timezone-aware UTC")
    if parsed.utcoffset() != timedelta(0):
        raise V2EpisodeLifecycleError(
            f"episode {history.episode_id!r}'s persisted {name}={raw!r} is not UTC "
            f"(offset {parsed.utcoffset()})")
    return parsed


# Which grid each operational-fact source's own bucket must sit on. A
# REEVALUATION records §7.1's 15m `B15'`; a CONFIRMATION records the
# confirming 5m `B5_confirm`; CREATION records the creation 15m bucket.
_SOURCE_BUCKET_TIMEFRAME = MappingProxyType({
    OPERATIONAL_SOURCE_CREATION: REEVALUATION_TIMEFRAME,
    OPERATIONAL_SOURCE_REEVALUATION: REEVALUATION_TIMEFRAME,
    OPERATIONAL_SOURCE_CONFIRMATION: DECISION_TIMEFRAME,
})


def _validated_persisted_operational_facts(
    history: V2EpisodeHistory, *, event, payload: Mapping, buffer: Decimal,
) -> V2OperationalFacts:
    """Validate one persisted operational block against its own event and
    against §7.1's canonical geometry. Every failure is corruption."""
    episode_id = history.episode_id
    source = payload.get(_OF_SOURCE)
    if source not in _SOURCE_BUCKET_TIMEFRAME:
        raise V2EpisodeLifecycleError(
            f"episode {episode_id!r}'s persisted operational facts carry "
            f"{_OF_SOURCE}={source!r}, which is not one of "
            f"{sorted(_SOURCE_BUCKET_TIMEFRAME)!r} -- an unrecognized provenance cannot be "
            "validated and is never assumed benign")
    raw_bucket = payload.get(_OF_SOURCE_BUCKET)
    if raw_bucket is None:
        raise V2EpisodeLifecycleError(
            f"episode {episode_id!r}'s persisted operational facts carry no "
            f"{_OF_SOURCE_BUCKET!r} -- the bucket a {source} was measured from is what makes it "
            "auditable after restart")
    source_bucket = _parse_persisted_bucket(
        history, raw_bucket, name=f"operational {_OF_SOURCE_BUCKET}")
    timeframe = _SOURCE_BUCKET_TIMEFRAME[source]
    _validate_bucket_start(
        source_bucket, f"episode {episode_id!r} operational {_OF_SOURCE_BUCKET}",
        timeframe=timeframe)
    # No-lookahead (§1/§2): a fact recorded at decision boundary `T` can only
    # have been measured from a bucket that had already closed by `T`.
    if source_bucket >= event.decision_boundary:
        raise V2EpisodeLifecycleError(
            f"episode {episode_id!r} records a {source} operational block at decision boundary "
            f"{event.decision_boundary.isoformat()!r} measured from {timeframe} bucket "
            f"{source_bucket.isoformat()!r}, which had not closed by then -- a decision may "
            "never read a future bucket (§1/§2)")
    expected_bucket = selected_bucket(timeframe, event.decision_boundary)
    if source in (OPERATIONAL_SOURCE_REEVALUATION, OPERATIONAL_SOURCE_CONFIRMATION) and (
            source_bucket != expected_bucket):
        raise V2EpisodeLifecycleError(
            f"episode {episode_id!r}'s {source} operational block was recorded at "
            f"{event.decision_boundary.isoformat()!r}, whose selected {timeframe} bucket is "
            f"{expected_bucket.isoformat()!r}, but it names {source_bucket.isoformat()!r} -- "
            "§1.3 selects exactly one bucket per boundary")

    derived = _build_trend_pullback_operational_facts(
        direction=history.creation_identity.direction,
        pullback_extreme=_finite_price(
            payload.get(_OF_PULLBACK_EXTREME), f"persisted {_OF_PULLBACK_EXTREME}"),
        dynamic_bound=_finite_price(
            payload.get(_OF_DYNAMIC_BOUND), f"persisted {_OF_DYNAMIC_BOUND}"),
        protection_buffer=buffer, source=source, source_bucket=source_bucket)
    _assert_persisted_geometry_agrees(
        history, derived=derived, persisted={
            _OF_ENTRY_ZONE_LOWER: payload.get(_OF_ENTRY_ZONE_LOWER),
            _OF_ENTRY_ZONE_UPPER: payload.get(_OF_ENTRY_ZONE_UPPER),
            _OF_INVALIDATION_PRICE: payload.get(_OF_INVALIDATION_PRICE),
            _OF_PROTECTION_BUFFER: payload.get(_OF_PROTECTION_BUFFER),
        }, where="operational facts")
    return derived


def _assert_persisted_geometry_agrees(
    history: V2EpisodeHistory, *, derived: V2OperationalFacts, persisted: Mapping, where: str,
) -> None:
    """Compare every persisted geometry field against what §7.1's canonical
    formula produces from the same extreme/bound/buffer.

    A missing field is not silently accepted either: what §7.1 publishes is
    what the record must contain. A DISAGREEING field raises rather than
    being recomputed away -- silent normalization would hide the exact
    corruption this validation exists to surface (§22)."""
    expected = {
        _OF_ENTRY_ZONE_LOWER: derived.entry_zone_lower,
        _OF_ENTRY_ZONE_UPPER: derived.entry_zone_upper,
        _OF_INVALIDATION_PRICE: derived.invalidation_price,
        _OF_PROTECTION_BUFFER: derived.protection_buffer,
    }
    for field, stored in persisted.items():
        want = expected[field]
        if stored is None:
            raise V2EpisodeLifecycleError(
                f"episode {history.episode_id!r}'s persisted {where} carry no {field!r} -- §7.1's "
                "published geometry is part of the immutable record, not something a reader "
                "reconstructs")
        if field == _OF_PROTECTION_BUFFER:
            if stored != want:
                raise V2EpisodeLifecycleError(
                    f"episode {history.episode_id!r}'s persisted {where} record {field}="
                    f"{stored!r} but this episode's frozen creation protection_buffer is "
                    f"{want!r} -- §12.2a/§12.4 freeze the creation value for the episode's whole "
                    "life")
            continue
        stored_value = _finite_price(stored, f"persisted {field}")
        if _exact(stored_value, field) != _exact(want, field):
            raise V2EpisodeLifecycleError(
                f"episode {history.episode_id!r}'s persisted {where} record {field}="
                f"{stored_value!r}, but §7.1's geometry for pullback_extreme="
                f"{derived.pullback_extreme!r} / dynamic_bound={derived.dynamic_bound!r} / "
                f"protection_buffer={derived.protection_buffer} gives {want!r}. Corruption is "
                "reported, never silently normalized (§22)")


# ---- §12.2a mechanism (1): the episode's OWN reference-history re-measurement
_REFERENCE_ROW_IDENTITY = (
    "exchange", "symbol", "market_type", "timeframe", "calculation_version",
    "feature_schema_version",
)


@dataclass(frozen=True)
class V2TrendPullbackReevaluationWindow:
    """§12.2a mechanism (1): the canonical source data for re-measuring THIS
    episode's own structural leg at a later legal 15m boundary.

    **This type exists because mechanism (1) and mechanism (2) must never be
    conflated, and an earlier draft of this unit conflated them.** §12.2a
    distinguishes (1) an active episode's own continuous re-evaluation of
    its own leg from (2) a freshly, independently-run Stage 5 detector
    invocation producing a brand-new candidate that §12.3 classifies A/B/C.
    The earlier draft accepted a Stage 5 candidate plus a caller-supplied
    `MATCH_EXACT` as proof of mechanism (1). That was wrong on two counts: a
    fresh detector candidate is mechanism (2) *by definition*, even when its
    creation anchor happens to match exactly; and Unit 2's A/B/C
    classification is dedup/ROUTING evidence, never the source of an active
    episode's operational facts. A `MATCH_EXACT` label also proved nothing
    about the candidate's own numbers -- a caller could hand over any
    `pullback_extreme` at all.

    Mechanism (1) is therefore sourced from what §7.1 actually names: the
    REFERENCE EXCHANGE's own closed 15m `close_price` series, over the
    CONTIGUOUS span from the episode's frozen creation anchor bucket
    (`trend_leg_extreme.bucket_ts`) THROUGH `B15' = selected_bucket("15m",
    T)` inclusive. Nothing is taken on trust: the caller supplies the
    ROWS, and this type proves they are the right rows before any value is
    derived from them. `pullback_extreme` and the dynamic zone bound are
    then DERIVED here -- a caller cannot assert either.

    `reference_15m_rows` are `exchange_feature_vectors`-shaped mappings
    (whatever reader produced them; this module imports no storage). Every
    row must:

      - carry this window's exact identity (`exchange` == the canonical §11
        reference exchange, `symbol`, `market_type`, `timeframe == "15m"`,
        `calculation_version`, `feature_schema_version`);
      - sit on the exact 15m grid, strictly ascending, CONTIGUOUS with no
        gap and no duplicate -- §7.1's span is a complete one, and a hole in
        it would silently change which close is "deepest so far";
      - end exactly at `B15'`, and contain no bucket after it (no-lookahead,
        §1/§2);
      - pass §11's own fail-closed reference gate. A single unusable bucket
        makes the whole span unusable -- §22 forbids filling the hole.

    Episode binding (frozen leg, direction, slot) is checked separately by
    `derive_trend_pullback_reevaluation()`, which is the only way to turn
    this window into operational facts."""
    T: datetime
    symbol: str
    market_type: str
    calculation_version: str
    feature_schema_version: int
    reference_15m_rows: "tuple[Mapping, ...]"
    reference_exchange: str = V2_REFERENCE_EXCHANGE

    def __post_init__(self) -> None:
        T = _validate_decision_boundary(self.T, "reevaluation T")
        object.__setattr__(self, "T", T)
        validate_symbol(self.symbol, V2EpisodeLifecycleError)
        validate_market_type(self.market_type, V2EpisodeLifecycleError)
        validate_calculation_version(self.calculation_version, V2EpisodeLifecycleError)
        validate_feature_schema_version(self.feature_schema_version, V2EpisodeLifecycleError)
        if self.reference_exchange != V2_REFERENCE_EXCHANGE:
            raise V2EpisodeLifecycleError(
                f"reference_exchange must be {V2_REFERENCE_EXCHANGE!r}, got "
                f"{self.reference_exchange!r} -- §7.1 measures the retracement on the canonical "
                "reference exchange's own closes, and §11 forbids substituting another")
        # §7.1 re-evaluates at LATER 15m decision boundaries. A 5m-only
        # boundary is not one: 15m is the re-measurement cadence, 5m is the
        # confirmation cadence, and §14 is explicit that conflating them is
        # wrong.
        b15 = _validate_bucket_start(
            T - _REEVALUATION_BUCKET, "reevaluation T", timeframe=REEVALUATION_TIMEFRAME)

        rows = self.reference_15m_rows
        if isinstance(rows, (str, bytes)) or not isinstance(rows, Sequence):
            raise V2EpisodeLifecycleError(
                f"reference_15m_rows must be a sequence of row mappings, got "
                f"{type(rows).__name__}")
        if not rows:
            raise V2EpisodeLifecycleError(
                "reference_15m_rows is empty -- §7.1's retracement span always contains at "
                "least the episode's own anchor bucket; an empty span proves nothing")

        frozen_rows, previous = [], None
        for index, raw in enumerate(rows):
            row = _mapping(raw, f"reference_15m_rows[{index}]")
            self._assert_reference_row_identity(row, index=index)
            bucket_ts = _validate_bucket_start(
                row.get("bucket_ts"), f"reference_15m_rows[{index}].bucket_ts",
                timeframe=REEVALUATION_TIMEFRAME)
            if previous is not None and bucket_ts != previous + _REEVALUATION_BUCKET:
                raise V2EpisodeLifecycleError(
                    f"reference_15m_rows[{index}].bucket_ts={bucket_ts.isoformat()!r} does not "
                    f"immediately follow {previous.isoformat()!r} -- §7.1's retracement span is "
                    "CONTIGUOUS and complete; a gap, a duplicate or an out-of-order bucket would "
                    "silently change which close is deepest so far (§22 forbids filling it)")
            if bucket_ts > b15:
                raise V2EpisodeLifecycleError(
                    f"reference_15m_rows[{index}].bucket_ts={bucket_ts.isoformat()!r} is after "
                    f"B15' = {b15.isoformat()!r} -- a re-evaluation at T may never read a bucket "
                    "later than the one §1.3 selects for it (no-lookahead, §1/§2)")
            close = self._gated_close(row, index=index)
            frozen_rows.append(MappingProxyType(
                {"bucket_ts": bucket_ts, "close_price": close}))
            previous = bucket_ts

        if previous != b15:
            raise V2EpisodeLifecycleError(
                f"reference_15m_rows ends at {previous.isoformat()!r} but §7.1 re-evaluates "
                f"against B15' = selected_bucket('15m', {T.isoformat()}) = {b15.isoformat()!r} "
                "-- the span must run THROUGH that bucket inclusive")
        object.__setattr__(self, "reference_15m_rows", tuple(frozen_rows))

    def _assert_reference_row_identity(self, row: Mapping, *, index: int) -> None:
        expected = {
            "exchange": self.reference_exchange, "symbol": self.symbol,
            "market_type": self.market_type, "timeframe": REEVALUATION_TIMEFRAME,
            "calculation_version": self.calculation_version,
            "feature_schema_version": self.feature_schema_version,
        }
        for field in _REFERENCE_ROW_IDENTITY:
            if field not in row:
                raise V2EpisodeLifecycleError(
                    f"reference_15m_rows[{index}] is missing identity field {field!r} -- an "
                    "unidentified row can never be proven to belong to this episode's own "
                    "structural leg")
            if row[field] != expected[field]:
                raise V2EpisodeLifecycleError(
                    f"reference_15m_rows[{index}] carries {field}={row[field]!r} but this "
                    f"re-evaluation window declares {expected[field]!r} -- a foreign row may not "
                    "re-measure this episode's leg (§3.2/§11)")

    @staticmethod
    def _gated_close(row: Mapping, *, index: int) -> float:
        """§11's fail-closed reference gate, applied to one span bucket.

        Unlike the 5m boundary close (where a failed gate is ordinary
        UNAVAILABLE), a failed gate HERE is fatal to the whole window: §7.1's
        span is complete by construction, so a hole cannot be tolerated and
        must not be silently skipped (§22)."""
        missing = [f for f in _REFERENCE_GATE_FIELDS if f not in row]
        if missing:
            raise V2EpisodeLifecycleError(
                f"reference_15m_rows[{index}] is missing §11 gate field(s) {missing!r}")
        if row["is_usable"] is not True or row["has_gap"] is not False:
            raise V2EpisodeLifecycleError(
                f"reference_15m_rows[{index}] fails §11's reference gate "
                f"(is_usable={row['is_usable']!r}, has_gap={row['has_gap']!r}) -- §7.1's "
                "retracement span must be complete; an unusable bucket makes the whole "
                "re-evaluation unavailable rather than silently shortened")
        bars_present, bars_expected = row["bars_present"], row["bars_expected"]
        for field, value in (("bars_present", bars_present), ("bars_expected", bars_expected)):
            if isinstance(value, bool) or not isinstance(value, int):
                raise V2EpisodeLifecycleError(
                    f"reference_15m_rows[{index}] {field} must be an int, got "
                    f"{type(value).__name__}")
        if bars_present != bars_expected:
            raise V2EpisodeLifecycleError(
                f"reference_15m_rows[{index}] is incomplete (bars_present={bars_present!r}, "
                f"bars_expected={bars_expected!r}) -- §11's gate fails closed")
        return _finite_price(
            row["close_price"], f"reference_15m_rows[{index}].close_price")

    @property
    def anchor_bucket(self) -> datetime:
        """The span's FIRST bucket -- which must be the episode's own frozen
        creation anchor (checked in `derive_trend_pullback_reevaluation`)."""
        return self.reference_15m_rows[0]["bucket_ts"]

    @property
    def b15(self) -> datetime:
        """`selected_bucket("15m", T)` -- the span's last bucket."""
        return self.reference_15m_rows[-1]["bucket_ts"]

    @property
    def closes(self) -> "tuple[float, ...]":
        return tuple(row["close_price"] for row in self.reference_15m_rows)


def derive_trend_pullback_reevaluation(
    history: V2EpisodeHistory, window: V2TrendPullbackReevaluationWindow,
) -> V2OperationalFacts:
    """§12.2a mechanism (1), derived -- never asserted.

    Binds `window` to THIS episode before reading a single close:

      - the episode must be `TREND_PULLBACK` (no other family has a
        pre-confirmation mutability mechanism);
      - the window's semantic scope must equal the episode's own frozen
        `symbol`/`market_type`/`calculation_version`/`feature_schema_version`
        (§3.2 -- a foreign snapshot may not re-measure this leg);
      - the span's FIRST bucket must be the episode's frozen creation
        `structural_anchor.bucket_ts`, i.e. `trend_leg_extreme`'s own
        anchor. §7.1 derives `pullback_extreme` "ONLY from the CONTIGUOUS
        span from `trend_leg_extreme`'s own anchor bucket THROUGH `B15`
        inclusive" -- buckets strictly older than the anchor helped select
        the anchor but are not part of the subsequent retracement.

    Then derives, per §7.1:

        pullback_extreme = min(close) over the span   (LONG)
                         = max(close) over the span   (SHORT)
        dynamic_bound    = close_price(B15')

    and re-derives the entry zone / planned `invalidation_price` from
    §7.1's exact geometry and the episode's OWN frozen creation
    `protection_buffer` -- so a later drifted decision-time buffer can never
    rewrite an existing episode's published geometry (§12.2a/§12.4)."""
    _require_history(history)
    if not isinstance(window, V2TrendPullbackReevaluationWindow):
        raise V2EpisodeLifecycleError(
            "window must be a V2TrendPullbackReevaluationWindow, got "
            f"{type(window).__name__}")
    identity = history.creation_identity
    if identity.setup_family != TREND_PULLBACK:
        raise V2EpisodeLifecycleError(
            f"episode {history.episode_id!r} is {identity.setup_family!r}; §12.2a gives only "
            "TREND_PULLBACK a pre-confirmation operational-update mechanism")
    _assert_scope_binding(
        history, symbol=window.symbol, market_type=window.market_type,
        calculation_version=window.calculation_version, what="re-evaluation window")
    _assert_feature_schema_binding(
        history, window.feature_schema_version, what="re-evaluation window")

    creation_anchor = _creation_anchor_bucket(history)
    if window.anchor_bucket != creation_anchor:
        raise V2EpisodeLifecycleError(
            f"the re-evaluation span starts at {window.anchor_bucket.isoformat()!r} but episode "
            f"{history.episode_id!r}'s frozen creation anchor (trend_leg_extreme.bucket_ts) is "
            f"{creation_anchor.isoformat()!r} -- §7.1 measures the retracement ONLY from the "
            "episode's OWN anchor through B15'. A span starting anywhere else is a different "
            "structural leg, which §12.2a forbids substituting for this episode's")

    closes = window.closes
    direction = identity.direction
    return _build_trend_pullback_operational_facts(
        direction=direction,
        pullback_extreme=(min(closes) if direction == LONG else max(closes)),
        dynamic_bound=closes[-1],
        protection_buffer=_creation_protection_buffer(history),
        source=OPERATIONAL_SOURCE_REEVALUATION, source_bucket=window.b15)


def _apply_monotonic_extreme(
    history: V2EpisodeHistory, current: V2OperationalFacts, derived: V2OperationalFacts,
) -> V2OperationalFacts:
    """§7.1's monotonic "deepest close so far" rule, enforced against the
    episode's own currently-valid persisted facts.

    `derived` is already computed from proven reference rows, so this is not
    a trust check on a caller's number -- it is the §7.1 invariant that the
    retracement extreme "update[s] only if the retracement deepens further".
    A DERIVED value that is shallower than the persisted one means the two
    disagree about the same span, which is corrupt history or a truncated
    window, never a reason to walk an already-published structural level
    back.

    The dynamic 15m bound may move freely in either direction: it is
    `close_price(B15')`, a fresh observation, not a running extreme. A
    changed bound with an UNCHANGED extreme still changes the published
    zone, and therefore still requires a §9 history event."""
    direction = history.creation_identity.direction
    deepens = (
        derived.pullback_extreme < current.pullback_extreme if direction == LONG
        else derived.pullback_extreme > current.pullback_extreme)
    same = derived.pullback_extreme == current.pullback_extreme
    if not (deepens or same):
        raise V2EpisodeLifecycleError(
            f"episode {history.episode_id!r} ({direction}) currently records "
            f"pullback_extreme={current.pullback_extreme!r}; the re-evaluation window derives "
            f"{derived.pullback_extreme!r}, which is SHALLOWER. §7.1 lets this fact update only "
            "if the retracement deepens further, so the two disagree about the same span -- "
            "refused, never silently walked back")
    return derived


def _creation_anchor_bucket(history: V2EpisodeHistory) -> datetime:
    """The episode's frozen `trend_leg_extreme` anchor bucket, parsed from
    its immutable creation `structural_anchor` (§12.1/§12.2)."""
    raw = history.creation_identity.structural_anchor.get(ANCHOR_BUCKET_TS)
    if not isinstance(raw, str):
        raise V2EpisodeLifecycleError(
            f"episode {history.episode_id!r} has no usable persisted "
            f"structural_anchor.{ANCHOR_BUCKET_TS}")
    try:
        parsed = datetime.fromisoformat(raw)
    except (TypeError, ValueError) as exc:
        raise V2EpisodeLifecycleError(
            f"episode {history.episode_id!r}'s persisted structural_anchor.{ANCHOR_BUCKET_TS}="
            f"{raw!r} is not a parseable ISO-8601 datetime: {exc}") from exc
    return _validate_bucket_start(
        parsed, f"episode {history.episode_id!r} creation anchor",
        timeframe=REEVALUATION_TIMEFRAME)


def _assert_scope_binding(
    history: V2EpisodeHistory, *, symbol: str, market_type: str,
    calculation_version: str, what: str,
) -> None:
    """§3.2: a decision may not be COMPUTED from one semantic scope and
    PERSISTED under another. Checked on the INPUT side, before any predicate
    runs -- no downstream event authorization can repair a decision already
    computed from foreign data."""
    identity = history.creation_identity
    mismatches = [
        (field, actual, expected)
        for field, actual, expected in (
            ("symbol", symbol, identity.symbol),
            ("market_type", market_type, identity.market_type),
            ("calculation_version", calculation_version, identity.calculation_version))
        if actual != expected]
    if mismatches:
        detail = ", ".join(f"{f}={a!r} (episode: {e!r})" for f, a, e in mismatches)
        raise V2EpisodeLifecycleError(
            f"this {what} belongs to a different semantic scope than episode "
            f"{history.episode_id!r}: {detail}. §3.2 forbids computing a decision from one "
            "scope's data and persisting it under another's")


def _assert_feature_schema_binding(
    history: V2EpisodeHistory, feature_schema_version: int, *, what: str,
) -> None:
    """§3.2 feature-schema half of input-side scope binding.

    `feature_schema_version` lives on the creation EVENT, not on
    `creation_identity` (it is not an `episode_id` input), so it cannot
    ride inside `_assert_scope_binding`. Both current-boundary DATA
    surfaces -- `V2BoundaryFacts` and the TP re-evaluation window -- must
    still match it before any predicate runs."""
    expected = history.creation_event.feature_schema_version
    if feature_schema_version != expected:
        raise V2EpisodeLifecycleError(
            f"{what} feature_schema_version={feature_schema_version!r} does not "
            f"equal episode {history.episode_id!r}'s own {expected!r} -- §3.2 forbids "
            "computing a decision from one feature-schema scope and persisting it under "
            "another")


# ============================================================================
# §7.1/§7.2/§7.3 — the three family confirmation predicates
# ============================================================================
def evaluate_trend_pullback_confirmation(
    history: V2EpisodeHistory, facts: V2BoundaryFacts,
) -> V2FamilySignal:
    """§7.1's 5m resumption trigger, evaluated on `B5 = selected_bucket("5m",
    T)`:

    ```text
    CONFIRM iff  ternary_sign(price_move_pct_median) == direction sign
                 AND price_direction_agreement >= 2/3
    ```

    `RESUMPTION_MIN_BUCKETS = 1` -- one closed 5m bucket is sufficient, by
    frozen design (5m's role here is trigger, not strength-scoring).

    Three things this predicate deliberately does NOT do:
      - it never reads `trend_leg_extreme`/`pullback_extreme` (§12.2a says
        so explicitly: confirmation is independent of the structural-fact
        tracking by construction);
      - it never returns `FALSE_BREAK` -- `TREND_PULLBACK` has no
        false-break rule at all; its pre-confirmation invalidation is §10's
        generic `invalidation_price` crossing, which Unit 4 owns;
      - it never consumes `volume`/`taker_flow`/`oi`/`funding`/
        `liquidations` (§6.3a: `price_structure` only)."""
    _require_history(history)
    _require_boundary_facts(facts)
    direction = history.creation_identity.direction
    # §6.3a/§21: a required family that is UNAVAILABLE or REJECTED makes the
    # predicate unevaluable at this boundary, and WHICH of the two it was is
    # carried through rather than flattened.
    gate = facts.required_family_quality(TREND_PULLBACK)
    if gate is not None:
        return gate
    consensus = facts.consensus_5m
    median = consensus.get("price_move_pct_median")
    agreement = consensus.get("price_direction_agreement")
    if median is None or agreement is None:
        return V2FamilySignal(
            signal=SIGNAL_UNAVAILABLE, reason="RESUMPTION_INPUT_UNAVAILABLE",
            evidence={"price_move_pct_median": median,
                      "price_direction_agreement": agreement,
                      "decision_bucket": facts.decision_bucket.isoformat()})
    median = _finite_numeric(median, "price_move_pct_median")
    agreement = _finite_numeric(agreement, "price_direction_agreement")
    if not 0.0 <= agreement <= 1.0:
        raise V2EpisodeLifecycleError(
            f"price_direction_agreement must be within [0.0, 1.0], got {agreement!r}")
    sign_matches = _ternary_sign(median) == _direction_sign(direction)
    agrees = agreement >= RESUMPTION_MIN_AGREEMENT
    evidence = {
        "direction": direction,
        "price_move_pct_median": median,
        "price_move_ternary_sign": _ternary_sign(median),
        "price_direction_agreement": agreement,
        "min_agreement": RESUMPTION_MIN_AGREEMENT,
        "decision_bucket": facts.decision_bucket.isoformat(),
    }
    if sign_matches and agrees:
        return V2FamilySignal(
            signal=SIGNAL_CONFIRM, reason="RESUMPTION_TRIGGER_HELD", evidence=evidence)
    return V2FamilySignal(
        signal=SIGNAL_HOLD,
        reason=("RESUMPTION_SIGN_MISMATCH" if not sign_matches
                else "RESUMPTION_AGREEMENT_BELOW_THRESHOLD"),
        evidence=evidence)


def _breakout_signal(
    history: V2EpisodeHistory, facts: V2BoundaryFacts, *, boundary_key_long: str,
    boundary_key_short: str, boundary_label: str, family: str,
) -> V2FamilySignal:
    """The ONE canonical direction-aware, one-sided, three-way breakout
    comparison both §7.2 and §7.3 freeze, against the episode's own FROZEN
    creation boundary:

    ```text
    LONG   close > boundary   CONFIRM
           close == boundary  HOLD          (neutral: retested, not reclaimed)
           close < boundary   FALSE_BREAK   (covers ordinary re-entry AND
                                             overshoot clean through the
                                             opposite side, one check)
    SHORT  mirrored
    ```

    The one-sided form is load-bearing (§7.2's own re-amendment): an earlier
    "back inside the range" predicate (`range_low < close < range_high`)
    could not fire for a violent reversal that closed THROUGH the range and
    beyond its opposite boundary -- a stronger repudiation of the breakout
    than an ordinary re-entry, yet invisible to the two-sided test. Checking
    only whether the BREAKOUT SIDE still holds covers both with one
    comparison.

    CONFIRM and FALSE_BREAK are logical complements of one comparison, so
    they can never both hold -- which is exactly why §13.1's "invalidation
    always wins" never has to arbitrate between them (§14).

    Confirmation is NOT required to be adjacent to the breakout bucket: any
    number of intervening HOLD buckets may sit between them, and a HOLD
    never resets the age clock."""
    _require_history(history)
    _require_boundary_facts(facts)
    direction = history.creation_identity.direction
    # §6.3a/§21, frozen consequence: a failed REQUIRED-family gate makes the
    # whole predicate unevaluable. A usable §11 reference close does NOT
    # independently rescue it merely by being present.
    gate = facts.required_family_quality(family)
    if gate is not None:
        return gate
    boundary_key = boundary_key_long if direction == LONG else boundary_key_short
    boundary = _frozen_family_price(history, boundary_key)
    close = facts.reference_close
    if close is None:
        # §11 fails closed for any calculation needing the canonical
        # reference price -- never a silent failover to another exchange,
        # and never a consensus aggregate standing in for an exact level.
        return V2FamilySignal(
            signal=SIGNAL_UNAVAILABLE, reason="REFERENCE_CLOSE_UNAVAILABLE",
            evidence={boundary_label: boundary, "direction": direction,
                      "boundary_fact": boundary_key,
                      "decision_bucket": facts.decision_bucket.isoformat()})
    close_exact, boundary_exact = _exact(close, "reference close"), _exact(boundary, boundary_key)
    evidence = {
        "direction": direction, "boundary_fact": boundary_key,
        boundary_label: boundary, "reference_close": close,
        "decision_bucket": facts.decision_bucket.isoformat(),
    }
    if close_exact == boundary_exact:
        return V2FamilySignal(
            signal=SIGNAL_HOLD, reason="BOUNDARY_EQUALITY_HOLD", evidence=evidence)
    beyond = close_exact > boundary_exact if direction == LONG else close_exact < boundary_exact
    if beyond:
        return V2FamilySignal(
            signal=SIGNAL_CONFIRM, reason="CLOSE_STRICTLY_BEYOND_BOUNDARY", evidence=evidence)
    return V2FamilySignal(
        signal=SIGNAL_FALSE_BREAK, reason="CLOSE_NO_LONGER_HOLDS_BREAKOUT_SIDE",
        evidence=evidence)


def evaluate_compression_breakout_confirmation(
    history: V2EpisodeHistory, facts: V2BoundaryFacts,
) -> V2FamilySignal:
    """§7.2's confirmation / boundary-equality HOLD / one-sided false break,
    against the SAME creation `range_high` (`LONG`) / `range_low` (`SHORT`)
    the episode originally broke.

    §12.2a freezes every `COMPRESSION_BREAKOUT` operational fact at
    creation: the range bounds are read BY VALUE from the episode's own
    creation event and are never re-derived from a current compression
    window, nor taken from a later non-materially-drifted case-(B)
    candidate's own freshly-detected range.

    §7.2's taker-flow gate is a FORMATION requirement on the `EARLY_SIGNAL`
    trigger bucket and deliberately does NOT carry over to confirmation
    (§6.3a scopes confirmation to `price_structure` alone)."""
    return _breakout_signal(
        history, facts, boundary_key_long=_FF_RANGE_HIGH, boundary_key_short=_FF_RANGE_LOW,
        boundary_label="breakout_boundary", family=COMPRESSION_BREAKOUT)


def evaluate_confirmed_breakout_confirmation(
    history: V2EpisodeHistory, facts: V2BoundaryFacts,
) -> V2FamilySignal:
    """§7.3's confirmation / boundary-equality HOLD / false-break re-entry,
    against the episode's FROZEN creation structural level
    (`resistance_level` for `LONG`, `support_level` for `SHORT` -- one
    persisted raw level price, read by value).

    Never selects a new 1h extreme, never uses current instrument metadata
    to redefine the level, and never adopts a later candidate's own level
    (§12.2a).

    **No taker-flow requirement (§7.3, frozen).** `COMPRESSION_BREAKOUT`'s
    formation-time volume/flow gate is explicitly NOT carried over to this
    family at all, at formation or at confirmation; nor may current
    `taker_flow`/`funding`/`oi`/`liquidations`/`volume` availability block
    this transition (§6.3a)."""
    return _breakout_signal(
        history, facts, boundary_key_long=_FF_RAW_LEVEL_PRICE,
        boundary_key_short=_FF_RAW_LEVEL_PRICE, boundary_label="structural_level",
        family=CONFIRMED_BREAKOUT)


_FAMILY_EVALUATORS = MappingProxyType({
    TREND_PULLBACK: evaluate_trend_pullback_confirmation,
    COMPRESSION_BREAKOUT: evaluate_compression_breakout_confirmation,
    CONFIRMED_BREAKOUT: evaluate_confirmed_breakout_confirmation,
})
assert set(_FAMILY_EVALUATORS) == set(_SETUP_FAMILIES)


def evaluate_family_signal(
    history: V2EpisodeHistory, facts: V2BoundaryFacts,
) -> V2FamilySignal:
    """Dispatch to the episode's OWN family's frozen predicate. The family
    comes from the episode's immutable creation identity, never from a
    caller argument, so no episode can be evaluated under another family's
    rule."""
    _require_history(history)
    family = history.creation_identity.setup_family
    return _FAMILY_EVALUATORS[family](history, facts)


def _finite_numeric(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise V2EpisodeLifecycleError(
            f"{name} must be a real number, got {type(value).__name__}: {value!r}")
    v = float(value)
    if not math.isfinite(v):
        raise V2EpisodeLifecycleError(f"{name} must be finite, got {value!r}")
    return v


def _require_boundary_facts(facts: Any) -> V2BoundaryFacts:
    if not isinstance(facts, V2BoundaryFacts):
        raise V2EpisodeLifecycleError(
            f"facts must be a V2BoundaryFacts, got {type(facts).__name__}")
    return facts


# ============================================================================
# the composed EARLY_SIGNAL boundary decision
# ============================================================================
@dataclass(frozen=True)
class V2LifecycleDecision:
    """One `EARLY_SIGNAL` episode's deterministic outcome at one `T`.

    Deliberately carries NO event. "This boundary resolves the episode" and
    "an authorized canonical event was built" are different facts, and only
    `build_episode_transition_event()` produces the second -- so a decision
    can never be mistaken for a persisted transition that never happened.

    `requires_event` implements §12.11's separation: a lifecycle transition
    or a §9 operational change always requires a new immutable event; a
    boundary where nothing episode-visible changed requires none, and
    minting one would be exactly the every-5m history spam §12.11 forbids."""
    episode_id: str
    T: datetime
    setup_family: str
    direction: str
    previous_state: str
    new_state: str
    outcome: str
    reason: str
    signal: V2FamilySignal
    t_detect: datetime
    candidate_deadline: datetime
    operational_facts: Optional[V2OperationalFacts] = None

    def __post_init__(self) -> None:
        one_of(self.outcome, "outcome", LIFECYCLE_OUTCOMES, V2EpisodeLifecycleError)
        if self.new_state != OUTCOME_NEW_STATE[self.outcome]:
            raise V2EpisodeLifecycleError(
                f"outcome {self.outcome!r} lands in {OUTCOME_NEW_STATE[self.outcome]!r}, not "
                f"{self.new_state!r} -- §13.2's graph is frozen and this unit invents no edge")
        if self.previous_state != EARLY_SIGNAL:
            raise V2EpisodeLifecycleError(
                f"previous_state must be {EARLY_SIGNAL!r}, got {self.previous_state!r}")
        if not isinstance(self.signal, V2FamilySignal):
            raise V2EpisodeLifecycleError(
                f"signal must be a V2FamilySignal, got {type(self.signal).__name__}")
        if (self.outcome == LIFECYCLE_PRECONFIRMATION_UPDATE
                and self.setup_family != TREND_PULLBACK):
            raise V2EpisodeLifecycleError(
                f"{LIFECYCLE_PRECONFIRMATION_UPDATE} is a TREND_PULLBACK-only outcome (§12.2a "
                f"gives the breakout families no pre-confirmation mutability), got "
                f"{self.setup_family!r}")
        if (self.outcome == LIFECYCLE_INVALIDATED_FALSE_BREAK
                and self.setup_family not in _FALSE_BREAK_FAMILIES):
            raise V2EpisodeLifecycleError(
                f"{LIFECYCLE_INVALIDATED_FALSE_BREAK} is defined only for "
                f"{_FALSE_BREAK_FAMILIES!r} (§7.2/§7.3), got {self.setup_family!r}")
        if self.operational_facts is not None and not isinstance(
                self.operational_facts, V2OperationalFacts):
            raise V2EpisodeLifecycleError(
                "operational_facts must be a V2OperationalFacts, got "
                f"{type(self.operational_facts).__name__}")

        # ---- signal/outcome coherence -----------------------------------
        # A decision is a claim about WHAT WAS OBSERVED and WHAT FOLLOWED.
        # A directly-constructed object must not be able to state a
        # transition its own recorded signal contradicts -- otherwise a
        # public persist path could write "CONFIRMED" onto history whose
        # evidence block says the trigger never held.
        allowed = _OUTCOME_ALLOWED_SIGNALS[self.outcome]
        if self.signal.signal not in allowed:
            raise V2EpisodeLifecycleError(
                f"outcome {self.outcome!r} is not reachable from family signal "
                f"{self.signal.signal!r} (reachable from {sorted(allowed)!r}) -- a transition may "
                "never contradict the observation it records")
        # §14: EXPIRED means the DEADLINE boundary closed. Never earlier.
        if self.outcome == LIFECYCLE_EXPIRED_CANDIDATE_AGE and self.T != self.candidate_deadline:
            raise V2EpisodeLifecycleError(
                f"{LIFECYCLE_EXPIRED_CANDIDATE_AGE} at T={self.T.isoformat()!r} but this "
                f"episode's §14 candidate deadline is {self.candidate_deadline.isoformat()!r} -- "
                "candidate-age expiry fires only when the deadline boundary itself closes")
        if self.T <= self.t_detect:
            raise V2EpisodeLifecycleError(
                f"T={self.T.isoformat()!r} is not strictly after t_detect="
                f"{self.t_detect.isoformat()!r}")
        if self.T > self.candidate_deadline:
            raise V2EpisodeLifecycleError(
                f"T={self.T.isoformat()!r} is beyond the §14 candidate deadline "
                f"{self.candidate_deadline.isoformat()!r}")
        _validate_decision_boundary(self.T, "T")
        _validate_decision_boundary(self.t_detect, "t_detect")
        _validate_decision_boundary(self.candidate_deadline, "candidate_deadline")
        one_of(self.setup_family, "setup_family", _SETUP_FAMILIES, V2EpisodeLifecycleError)
        one_of(self.direction, "direction", (LONG, SHORT), V2EpisodeLifecycleError)
        nonblank(self.episode_id, "episode_id", V2EpisodeLifecycleError)
        nonblank(self.reason, "reason", V2EpisodeLifecycleError)

        # §7.1/§9: a TREND_PULLBACK event that publishes or freezes geometry
        # must actually carry it. A CONFIRMED TP episode with no final zone
        # is exactly the record §9's freeze rule exists to guarantee.
        if (self.setup_family == TREND_PULLBACK
                and self.outcome in (LIFECYCLE_CONFIRMED, LIFECYCLE_PRECONFIRMATION_UPDATE)
                and self.operational_facts is None):
            raise V2EpisodeLifecycleError(
                f"a TREND_PULLBACK {self.outcome} carries no operational facts -- §7.1/§9 "
                "require the entry zone this boundary publishes (or freezes) to be recorded")
        if self.operational_facts is not None:
            if self.setup_family != TREND_PULLBACK:
                raise V2EpisodeLifecycleError(
                    f"{self.setup_family!r} has no §12.2a pre-confirmation operational shape, so "
                    "a decision for it must not carry operational_facts")
            if self.operational_facts.direction != self.direction:
                raise V2EpisodeLifecycleError(
                    f"operational_facts direction {self.operational_facts.direction!r} does not "
                    f"match this decision's {self.direction!r}")
            if (self.outcome == LIFECYCLE_CONFIRMED
                    and self.operational_facts.source != OPERATIONAL_SOURCE_CONFIRMATION):
                raise V2EpisodeLifecycleError(
                    "a TREND_PULLBACK CONFIRMED must freeze its zone against the CONFIRMING 5m "
                    f"close (§7.1), so its operational facts' source must be "
                    f"{OPERATIONAL_SOURCE_CONFIRMATION!r}, got "
                    f"{self.operational_facts.source!r}")
            if (self.outcome == LIFECYCLE_PRECONFIRMATION_UPDATE
                    and self.operational_facts.source != OPERATIONAL_SOURCE_REEVALUATION):
                raise V2EpisodeLifecycleError(
                    f"a {LIFECYCLE_PRECONFIRMATION_UPDATE} records a §12.2a mechanism-(1) "
                    f"re-measurement, so its operational facts' source must be "
                    f"{OPERATIONAL_SOURCE_REEVALUATION!r}, got "
                    f"{self.operational_facts.source!r}")

    @property
    def resolution_category(self) -> str:
        """§21's category this boundary actually resolved under -- carried
        into the persisted event so a later reader can tell a real neutral
        observation from an absent or disqualified input (§14/§21)."""
        return self.signal.signal

    @property
    def requires_event(self) -> bool:
        return self.outcome in _EVENT_REQUIRED

    @property
    def is_terminal(self) -> bool:
        return self.outcome in (
            LIFECYCLE_INVALIDATED_FALSE_BREAK, LIFECYCLE_EXPIRED_CANDIDATE_AGE)


def evaluate_early_signal_transition(
    history: V2EpisodeHistory, *, T: datetime, facts: V2BoundaryFacts,
    reevaluation_window: Optional[V2TrendPullbackReevaluationWindow] = None,
) -> V2LifecycleDecision:
    """Resolve ONE `EARLY_SIGNAL` episode at ONE legal 5m decision boundary.

    Evaluation order, implementing §13.1's precedence exactly:

    ```text
    0. scope/state/clock validation  (fail closed, never coerce)
    1. family signal on B5 = selected_bucket("5m", T)
    2. FALSE_BREAK  -> INVALIDATED             §13.1 level 1 (§7.2/§7.3's own
                                                pre-confirmation invalidation)
    3. CONFIRM      -> CONFIRMED               §13.1 level 3
    4. otherwise, at the deadline boundary -> EXPIRED     §13.1 level 2, §14
    5. otherwise, a changed TP operational fact -> EARLY_SIGNAL update  §9
    6. otherwise -> nothing                    §12.11
    ```

    Steps 2-4 look inverted against §13.1's numbered list only if the
    deadline is read as an independent fact. It is not: §14 freezes expiry
    as "the deadline boundary is reached AND that same boundary's own
    confirmation check did not hold", so confirmation is *part of* the
    expiry condition and the two can never both be true. Checking the
    family signal first is the only way to implement that; testing
    `age >= max_age` before the signal would expire episodes that legitimately
    confirm on their final eligible bucket, which §13.1/§14 explicitly forbid.

    Likewise, FALSE_BREAK and CONFIRM are logical complements of one
    one-sided comparison, so ordering never actually arbitrates between them
    either -- it is written in precedence order for composition safety, not
    because a tie can occur.

    `T > candidate_deadline` while the persisted state is still
    `EARLY_SIGNAL` FAILS CLOSED. Under these rules the deadline boundary
    always resolves the episode, so a still-`EARLY_SIGNAL` episode past its
    deadline means that boundary was never processed -- an orchestration
    defect for Unit 5 to surface, never something this unit may paper over
    by inventing a late expiry that no frozen rule defines."""
    _require_early_signal(history)
    _require_boundary_facts(facts)
    T = _validate_decision_boundary(T, "T")
    if facts.T != T:
        raise V2EpisodeLifecycleError(
            f"boundary facts were resolved for {facts.T.isoformat()!r} but this decision is at "
            f"{T.isoformat()!r} -- §3.4 requires ONE coherent data view per logical decision")
    # §3.2, checked on the INPUT side: the current-boundary data must belong
    # to the same semantic scope the resulting event will be stamped with.
    # Nothing downstream can repair a decision already computed from a
    # foreign snapshot, so this runs BEFORE any predicate.
    _assert_scope_binding(
        history, symbol=facts.symbol, market_type=facts.market_type,
        calculation_version=facts.calculation_version, what="boundary snapshot")
    _assert_feature_schema_binding(
        history, facts.feature_schema_version, what="boundary snapshot")

    identity = history.creation_identity
    family, direction = identity.setup_family, identity.direction
    t_detect = read_detection_boundary(history)
    deadline = read_candidate_deadline(history)

    if T <= t_detect:
        raise V2EpisodeLifecycleError(
            f"T={T.isoformat()!r} is not strictly after episode {history.episode_id!r}'s own "
            f"T_detect={t_detect.isoformat()!r} -- §7.1/§7.2/§7.3 all evaluate confirmation only "
            "at a LATER boundary, so a newly-created episode can never be confirmed from the "
            "same already-known bucket that created it")
    if T > deadline:
        raise V2EpisodeLifecycleError(
            f"episode {history.episode_id!r} is still {EARLY_SIGNAL!r} at T={T.isoformat()!r}, "
            f"strictly beyond its §14 candidate deadline {deadline.isoformat()!r} "
            f"({family}, max age {CANDIDATE_MAX_AGE[family]}). Under §13.1/§14 the deadline "
            "boundary always resolves the episode, so this state means the deadline boundary was "
            "never evaluated -- refused rather than resolved by an invented late-expiry rule")

    # §12.2a mechanism (1): bind and derive the currently-valid TP operational
    # facts BEFORE the family predicate, so a foreign-scope window cannot
    # produce a decision that is later refused. A confirming boundary still
    # freezes the facts valid AT that exact decision -- including this
    # boundary's own update.
    current_facts = read_operational_facts(history)
    updated_facts: Optional[V2OperationalFacts] = None
    if reevaluation_window is not None:
        if not isinstance(reevaluation_window, V2TrendPullbackReevaluationWindow):
            raise V2EpisodeLifecycleError(
                "reevaluation_window must be a V2TrendPullbackReevaluationWindow, got "
                f"{type(reevaluation_window).__name__}")
        if family != TREND_PULLBACK:
            raise V2EpisodeLifecycleError(
                f"a pre-confirmation re-evaluation was supplied for a {family!r} episode -- "
                "§12.2a gives only TREND_PULLBACK a pre-confirmation mutability mechanism")
        if reevaluation_window.T != T:
            raise V2EpisodeLifecycleError(
                f"reevaluation_window is for {reevaluation_window.T.isoformat()!r} but this "
                f"decision is at {T.isoformat()!r}")
        derived = derive_trend_pullback_reevaluation(history, reevaluation_window)
        updated_facts = _apply_monotonic_extreme(history, current_facts, derived)

    signal = evaluate_family_signal(history, facts)

    def decide(outcome: str, reason: str,
               operational: Optional[V2OperationalFacts] = None) -> V2LifecycleDecision:
        return V2LifecycleDecision(
            episode_id=history.episode_id, T=T, setup_family=family, direction=direction,
            previous_state=EARLY_SIGNAL, new_state=OUTCOME_NEW_STATE[outcome], outcome=outcome,
            reason=reason, signal=signal, t_detect=t_detect, candidate_deadline=deadline,
            operational_facts=operational)

    # 2. §13.1 level 1 -- the breakout families' own pre-confirmation
    #    invalidation. A broken structural premise cannot be confirmed.
    if signal.signal == SIGNAL_FALSE_BREAK:
        return decide(LIFECYCLE_INVALIDATED_FALSE_BREAK, signal.reason,
                      updated_facts or current_facts)

    # 3. §13.1 level 3 -- confirmation. §9/§12.2a: the zone updates ONE final
    #    time here, now that confirmation_close_price exists, then freezes.
    if signal.signal == SIGNAL_CONFIRM:
        frozen = updated_facts or current_facts
        if family == TREND_PULLBACK:
            confirmation_close = facts.reference_close
            if confirmation_close is None:
                # §14 (amended): TREND_PULLBACK reaches CONFIRMED only when
                # BOTH the resumption trigger holds AND §11's canonical
                # reference close needed to freeze the final zone is usable.
                # The trigger DID hold -- recording this as a failed trigger
                # would be a false record of what the market did -- but the
                # transition could not be MATERIALIZED, so the boundary's
                # resolution category is UNAVAILABLE, with the trigger's own
                # evidence preserved verbatim. Falling through (rather than
                # returning) keeps a same-`T` §9 zone change recordable and
                # still closes the deadline.
                signal = V2FamilySignal(
                    signal=SIGNAL_UNAVAILABLE, reason="CONFIRMATION_CLOSE_UNAVAILABLE",
                    evidence=dict(
                        signal.evidence, resumption_trigger_held=True,
                        confirmation_close_available=False))
            else:
                frozen = _build_trend_pullback_operational_facts(
                    direction=direction, pullback_extreme=frozen.pullback_extreme,
                    dynamic_bound=confirmation_close,
                    protection_buffer=_creation_protection_buffer(history),
                    source=OPERATIONAL_SOURCE_CONFIRMATION,
                    source_bucket=facts.decision_bucket)
                # §36/H3: one event per (stream, episode, boundary). A
                # same-`T` operational update is AGGREGATED into this single
                # CONFIRMED event, never emitted as a second EARLY_SIGNAL
                # event at the same boundary.
                return decide(LIFECYCLE_CONFIRMED, signal.reason, frozen)
        else:
            return decide(LIFECYCLE_CONFIRMED, signal.reason, frozen)

    # 4. §13.1 level 2 / §14 -- the deadline boundary closed without this
    #    boundary's own confirmation check holding. §14's amended rule: the
    #    age window is a HARD budget that ends here whether or not the
    #    predicate was evaluable, and the persisted evidence MUST retain
    #    WHICH resolution category applied (HOLD vs UNAVAILABLE vs REJECTED)
    #    rather than laundering an unknown into a measured neutral (§21).
    if T == deadline:
        return decide(
            LIFECYCLE_EXPIRED_CANDIDATE_AGE,
            f"CANDIDATE_AGE_DEADLINE_{signal.signal}_{signal.reason}",
            updated_facts or current_facts)

    # 5. §9 -- a genuinely CHANGED pre-`CONFIRMED` operational fact is
    #    recorded as a new immutable event (never a rewrite of an earlier one).
    if updated_facts is not None and not updated_facts.same_geometry(current_facts):
        return decide(
            LIFECYCLE_PRECONFIRMATION_UPDATE, "OPERATIONAL_FACTS_UPDATED", updated_facts)

    # 6. §12.11 -- nothing episode-visible changed; no event, no heartbeat.
    return decide(LIFECYCLE_NO_CHANGE, signal.reason, current_facts)


# ============================================================================
# §3.1/§3.2/§34 — building the canonical transition event
# ============================================================================
@dataclass(frozen=True)
class V2LifecycleAuthorization:
    """What a Unit 3 boundary needs in order to PERSIST its decision.

    Deliberately NARROWER than Unit 2's `V2CreationAuthorization`, and the
    difference is the whole point:

      - **No version-switch gate.** §3.1 requires an existing `OLD`-tuple
        episode to keep progressing through confirmation/invalidation/
        horizon while `OLD` is `DRAINING` -- that is the mechanism which
        makes drain finite. `assert_provenance_authorized_for_new_creation()`
        rejects `OLD` throughout a drain BY DESIGN, so reusing it here would
        freeze exactly the episodes §3.1 requires to keep moving, and drain
        could never complete. Continuity is instead enforced by identity
        (below).
      - **No activation-readiness gate.** §3.3 readiness governs ACTIVATING
        a `calculation_version` for new work; an episode already running
        under an already-active version does not re-ask that question, and
        gating on it would freeze existing episodes for the same reason.

    What IS enforced: §3.4's publication-CLEAN acknowledgement (this unit's
    decisions read current Stage 2 facts at `T`, so the same coherent-view
    requirement Unit 2 has applies), and §3.2 provenance whose identity
    reproduces the episode's own.

    **Publication CLEAN is an acknowledgement, not a proof.** This type
    refuses to build anything unless `publication_clean is True`, so the
    guard cannot be silently skipped. It cannot verify that an H2e coherent
    read session was really opened -- the frozen contract defines no
    capability-token mechanism, and inventing one would couple this pure
    module to the database. **Unit 5 composition obligation (recorded, not
    implemented):** the production coordinator must produce this
    acknowledgement only from inside a successfully-opened H2e coherent read
    session for the exact same `(symbol, market_type, calculation_version,
    decision_boundary)` scope. No runtime composition exists yet."""
    provenance: V2DecisionProvenance
    publication_clean: bool

    def __post_init__(self) -> None:
        if not isinstance(self.provenance, V2DecisionProvenance):
            raise V2EpisodeLifecycleError(
                f"provenance must be a V2DecisionProvenance, got "
                f"{type(self.provenance).__name__}")
        if self.publication_clean is not True:
            raise V2EpisodeLifecycleError(
                "publication_clean must be True -- §3.4 requires the Stage 2 publication state "
                "for this scope/version to be CLEAN before a lifecycle decision is persisted. "
                "This check enforces the acknowledgement; establishing that it is only produced "
                "inside a successful H2e coherent CLEAN session for this exact scope/T is the "
                "composing caller's (Unit 5's) obligation")

    def event_provenance(self) -> V2EventProvenance:
        """Pure projection of the already-resolved decision provenance into
        the narrower snapshot `build_v2_episode_event()` consumes -- never a
        second resolution."""
        p = self.provenance
        return V2EventProvenance(
            run_kind=p.run_kind, run_id=p.run_id, model_family=p.model_family,
            rules_version=p.rules_version, symbol=p.symbol, market_type=p.market_type,
            feature_schema_version=p.feature_schema_version,
            calculation_version=p.calculation_version, config_hash=p.config_hash,
            config_version=p.config_version, code_version=p.code_version,
            decision_code_version=p.decision_code_version,
        )


def _assert_decision_matches_history(
    decision: V2LifecycleDecision, history: V2EpisodeHistory,
) -> None:
    """Re-derive every fact the decision asserts about the episode, straight
    from the episode's own persisted history, and refuse any disagreement.

    `V2LifecycleDecision` is public and directly constructible, and the event
    columns come from the HISTORY while the evidence block comes from the
    DECISION -- so without this check a hand-built decision could persist an
    event whose columns say `COMPRESSION_BREAKOUT`/`LONG` while its own
    snapshot says `TREND_PULLBACK`/`SHORT`. Nothing downstream would notice:
    both halves are internally well-formed. The canonical evaluator remains
    the normal path; this makes the abnormal one impossible rather than
    merely discouraged."""
    identity = history.creation_identity
    expected = (
        ("episode_id", decision.episode_id, history.episode_id),
        ("setup_family", decision.setup_family, identity.setup_family),
        ("direction", decision.direction, identity.direction),
        ("t_detect", decision.t_detect, read_detection_boundary(history)),
        ("candidate_deadline", decision.candidate_deadline, read_candidate_deadline(history)),
    )
    mismatches = [
        (field, actual, want) for field, actual, want in expected if actual != want]
    if mismatches:
        detail = ", ".join(f"{f}={a!r} (history: {w!r})" for f, a, w in mismatches)
        raise V2EpisodeLifecycleError(
            f"this decision does not describe episode {history.episode_id!r}'s own persisted "
            f"facts: {detail} -- refusing to persist an event whose columns and whose evidence "
            "would tell different stories")
    if history.current_state != EARLY_SIGNAL:
        raise V2EpisodeLifecycleError(
            f"episode {history.episode_id!r} is {history.current_state!r}; Stage 6 unit 3 "
            f"persists only transitions out of {EARLY_SIGNAL!r}")


def build_episode_transition_event(
    decision: V2LifecycleDecision, history: V2EpisodeHistory, *,
    authorization: V2LifecycleAuthorization,
) -> V2EpisodeEvent:
    """Build the ONE canonical history event this boundary requires.

    Always via `build_v2_episode_event()` -- the single construction path
    that recomputes `episode_id`/`event_id` deterministically. This module
    never constructs a `V2EpisodeEvent` directly, and never accepts either
    id as an opaque caller string.

    The transition event reuses the episode's frozen creation identity
    verbatim: the ORIGINAL `t_create`, `direction`, `setup_family` and
    `structural_anchor`, with `decision_boundary = T`. Because
    `compute_episode_id()` hashes exactly those (plus `model_family`/
    `rules_version`/`calculation_version`/`symbol`/`market_type`), the
    resulting `episode_id` MUST equal the episode's own -- and this function
    asserts it does. That single check is what enforces §3.1's semantic-tuple
    continuity: a provenance carrying a different `rules_version` or
    `calculation_version` (a `NEW` tuple trying to mutate an `OLD` episode)
    produces a different `episode_id` and is refused here. It deliberately
    does NOT constrain `decision_code_version`, which §2.1a excludes from
    identity precisely so a decision-code-only release does not fork an
    episode; the acting value is recorded on the event as ordinary
    provenance.

    `execution_stream` (`run_kind`/`run_id`) is NOT part of `episode_id`
    (§12.10 makes it the physical namespace only), so it is checked
    separately against the history's own -- otherwise one stream could write
    a transition for another stream's episode."""
    if not isinstance(decision, V2LifecycleDecision):
        raise V2EpisodeLifecycleError(
            f"decision must be a V2LifecycleDecision, got {type(decision).__name__}")
    _require_history(history)
    if not isinstance(authorization, V2LifecycleAuthorization):
        raise V2EpisodeLifecycleError(
            "authorization must be a V2LifecycleAuthorization, got "
            f"{type(authorization).__name__}")
    if not decision.requires_event:
        raise V2EpisodeLifecycleError(
            f"outcome {decision.outcome!r} requires no persisted history event (§12.11) -- "
            "refusing to mint one; an every-boundary heartbeat event is exactly what §12.11 "
            "forbids")
    _assert_decision_matches_history(decision, history)

    provenance = authorization.provenance
    if provenance.run_kind != history.run_kind or provenance.run_id != history.run_id:
        raise V2EpisodeLifecycleError(
            f"provenance execution_stream (run_kind={provenance.run_kind!r}, "
            f"run_id={provenance.run_id!r}) does not match episode {history.episode_id!r}'s own "
            f"(run_kind={history.run_kind!r}, run_id={history.run_id!r}) -- §12.10 keeps LIVE and "
            "REPLAY physically isolated; one stream never writes another's history")
    if provenance.decision_boundary != decision.T:
        raise V2EpisodeLifecycleError(
            f"provenance decision_boundary {provenance.decision_boundary.isoformat()!r} does not "
            f"equal this decision's T {decision.T.isoformat()!r}")
    # §3.1 (amended): an episode is attributed to the semantic tuple its own
    # CREATION event records, and EVERY later lifecycle transition continues
    # under that tuple -- decision_code_version included. rules_version and
    # calculation_version are forced by the episode_id recomputation below;
    # decision_code_version is NOT (§2.1a excludes it from the identity hash
    # precisely so a decision-code-only release does not fork an episode), so
    # it is the one member of the tuple that must be checked explicitly here.
    creation_event = history.creation_event
    if provenance.decision_code_version != creation_event.decision_code_version:
        raise V2EpisodeLifecycleError(
            f"provenance decision_code_version {provenance.decision_code_version!r} does not "
            f"equal episode {history.episode_id!r}'s own creation value "
            f"{creation_event.decision_code_version!r}. §3.1 requires an existing episode to "
            "continue through its terminal state under its CREATION semantic tuple: a "
            "decision-code-only release does not fork episode_id (§2.1a) and equally may not "
            "reinterpret an episode that already exists")

    identity = history.creation_identity
    event = build_v2_episode_event(
        authorization.event_provenance(),
        t_create=identity.t_create,
        direction=identity.direction,
        setup_family=identity.setup_family,
        structural_anchor=dict(identity.structural_anchor),
        episode_state=decision.new_state,
        decision_boundary=decision.T,
        decision_snapshot=_transition_decision_snapshot(decision),
        event_payload=_transition_event_payload(decision),
    )
    if event.episode_id != history.episode_id:
        raise V2EpisodeLifecycleError(
            f"the transition event recomputes episode_id {event.episode_id!r}, which is not "
            f"episode {history.episode_id!r}'s own. §3.1 requires an existing episode to continue "
            "under its ORIGINAL frozen semantic tuple; a provenance whose rules_version/"
            "calculation_version differs describes a DIFFERENT episode and may never mutate this "
            "one")
    return event


def _transition_decision_snapshot(decision: V2LifecycleDecision) -> Mapping:
    """What this boundary decided FROM: the family signal, its by-value
    evidence, and the frozen clock facts, so the decision is independently
    auditable after restart without re-reading any market data."""
    return {
        LIFECYCLE_EVIDENCE_KEY: {
            "setup_family": decision.setup_family,
            "direction": decision.direction,
            "t_detect": decision.t_detect.isoformat(),
            "candidate_deadline": decision.candidate_deadline.isoformat(),
            "at_candidate_deadline": decision.T == decision.candidate_deadline,
            "signal": decision.signal.signal,
            "signal_reason": decision.signal.reason,
            # §14/§21: the resolution CATEGORY this boundary closed under, in
            # its own named field. An EXPIRED event must not read as "the
            # market produced a neutral HOLD" when the truth was that a
            # required input was absent (UNAVAILABLE) or disqualified
            # (REJECTED) -- the three are different facts and a later reader
            # must be able to tell them apart without parsing prose.
            "resolution_category": decision.resolution_category,
            "evidence": dict(decision.signal.evidence),
        },
    }


def _transition_event_payload(decision: V2LifecycleDecision) -> Mapping:
    """What this boundary decided/emitted: the transition itself and, for
    `TREND_PULLBACK`, the operational facts this event updates or freezes.

    The operational block is written for `TREND_PULLBACK` only -- the two
    breakout families' operational facts are frozen at creation (§12.2a), so
    re-recording them on every transition would create a second, competing
    representation of an already-immutable creation fact."""
    payload: dict = {
        LIFECYCLE_TRANSITION_KEY: {
            "previous_state": decision.previous_state,
            "new_state": decision.new_state,
            "outcome": decision.outcome,
            "reason": decision.reason,
        },
    }
    if decision.operational_facts is not None and decision.setup_family == TREND_PULLBACK:
        payload[OPERATIONAL_FACTS_KEY] = dict(decision.operational_facts.as_payload())
    return payload
