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
`episode_id` and is refused. `decision_code_version` is deliberately NOT
required to match, because §2.1a deliberately EXCLUDES it from
`episode_id` precisely so a decision-code-only release does not fork
identity — this module records the acting value and invents no
attribution rule beyond what is frozen (see `ports.py`'s
`V2VersionDrainStatusReader` note for the still-open drain-counting gap,
which this unit does not need and does not solve).

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

from collections.abc import Mapping as _AbcMapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from typing import Any, Mapping, Optional

from analytics.forecasting_v2._validation import nonblank, one_of
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
    CREATION_FACTS_KEY, MATCH_EXACT, V2CandidateFacts, read_creation_facts,
)
from analytics.forecasting_v2.episode_history import (
    NON_TERMINAL_EPISODE_STATES, V2EpisodeHistory, V2EpisodeHistoryError,
    canonical_decimal_text, deep_freeze_json,
)
from analytics.forecasting_v2.event_factory import build_v2_episode_event
from analytics.forecasting_v2.events import (
    COMPRESSION_BREAKOUT, CONFIRMED, CONFIRMED_BREAKOUT, EARLY_SIGNAL, EXPIRED,
    INVALIDATED, LONG, TREND_PULLBACK, V2EpisodeEvent,
)
from analytics.forecasting_v2.family_quality import family_quality_ok
from analytics.forecasting_v2.provenance import V2EventProvenance
from analytics.forecasting_v2.trend_pullback import PULLBACK_MAX_AGE_15M_BUCKETS

__all__ = [
    "V2EpisodeLifecycleError",
    # frozen family constants (§14/§7.1)
    "CANDIDATE_MAX_AGE", "RESUMPTION_MIN_AGREEMENT", "REQUIRED_METRIC_FAMILY",
    "REEVALUATION_TIMEFRAME", "DECISION_TIMEFRAME", "DECISION_BUCKET",
    # family signal vocabulary
    "SIGNAL_CONFIRM", "SIGNAL_FALSE_BREAK", "SIGNAL_HOLD", "SIGNAL_UNAVAILABLE",
    "FAMILY_SIGNALS",
    # outcome vocabulary
    "LIFECYCLE_NO_CHANGE", "LIFECYCLE_PRECONFIRMATION_UPDATE", "LIFECYCLE_CONFIRMED",
    "LIFECYCLE_INVALIDATED_FALSE_BREAK", "LIFECYCLE_EXPIRED_CANDIDATE_AGE",
    "LIFECYCLE_OUTCOMES", "OUTCOME_NEW_STATE",
    # persisted keys
    "LIFECYCLE_EVIDENCE_KEY", "LIFECYCLE_TRANSITION_KEY", "OPERATIONAL_FACTS_KEY",
    # value objects
    "V2BoundaryFacts", "V2FamilySignal", "V2TrendPullbackReevaluation",
    "V2OperationalFacts", "V2LifecycleDecision", "V2LifecycleAuthorization",
    # readers over persisted history
    "read_candidate_deadline", "read_detection_boundary", "read_operational_facts",
    # family evaluators
    "evaluate_trend_pullback_confirmation",
    "evaluate_compression_breakout_confirmation",
    "evaluate_confirmed_breakout_confirmation",
    "evaluate_family_signal",
    # composition
    "trend_pullback_reevaluation_from_candidate",
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
SIGNAL_HOLD = "HOLD"
# §21 requires UNAVAILABLE to be DISTINGUISHED, never collapsed into
# "evaluated and false": the required input does not exist at this boundary.
SIGNAL_UNAVAILABLE = "UNAVAILABLE"
FAMILY_SIGNALS = (SIGNAL_CONFIRM, SIGNAL_FALSE_BREAK, SIGNAL_HOLD, SIGNAL_UNAVAILABLE)


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
def _is_finite(value: float) -> bool:
    return value == value and value not in (float("inf"), float("-inf"))  # NaN != NaN


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
    if not _is_finite(v):
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
    value (§3.4's "one coherent data view per logical decision").

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
    Unavailable category). A row that IS present is held to its own
    identity: its `timeframe`/`bucket_ts` must be exactly `"5m"` and
    `selected_bucket("5m", T)`. That is the no-lookahead/coherence guard
    (§1/§2) -- a caller cannot hand this unit a newer bucket, an older
    bucket, or another timeframe's row and have it silently decide a
    lifecycle transition from it."""
    T: datetime
    consensus_5m: Optional[Mapping] = None
    reference_feature_5m: Optional[Mapping] = None

    def __post_init__(self) -> None:
        T = _validate_decision_boundary(self.T, "T")
        object.__setattr__(self, "T", T)
        expected_bucket = selected_bucket(DECISION_TIMEFRAME, T)
        for name in ("consensus_5m", "reference_feature_5m"):
            row = getattr(self, name)
            if row is None:
                continue
            row = _mapping(row, name)
            self._assert_row_identity(row, name=name, expected_bucket=expected_bucket)
            object.__setattr__(self, name, _freeze(dict(row), name))

    @staticmethod
    def _assert_row_identity(row: Mapping, *, name: str, expected_bucket: datetime) -> None:
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
        forbids substituting a consensus aggregate for it."""
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

    def required_family_quality_ok(self, setup_family: str) -> bool:
        """§6.3a: does every metric family THIS decision consumes satisfy
        its own family-scoped coverage/confidence floor?

        Scoped strictly to `REQUIRED_METRIC_FAMILY[setup_family]` -- an
        unrelated degraded family can never suppress a Unit 3 transition,
        and the global `min_coverage_ratio`/`consensus_confidence` rollup is
        never read."""
        one_of(setup_family, "setup_family", _SETUP_FAMILIES, V2EpisodeLifecycleError)
        try:
            return all(
                family_quality_ok(self.consensus_5m, family=family)
                for family in REQUIRED_METRIC_FAMILY[setup_family])
        except ValueError as exc:      # V2FamilyQualityError: malformed PRESENT data
            raise V2EpisodeLifecycleError(
                f"consensus_5m carries malformed per-family quality data: {exc}") from exc

    @classmethod
    def from_aligned_inputs(cls, aligned) -> "V2BoundaryFacts":
        """Project an already-loaded `aligned_inputs.V2AlignedInputs`
        snapshot -- the canonical H2 coherent read path -- into this unit's
        narrow by-value input. A pure projection: nothing is re-read, and
        the 5m rows arrive exactly as that snapshot resolved them for `T`."""
        tf = aligned.by_timeframe[DECISION_TIMEFRAME]
        return cls(
            T=aligned.T, consensus_5m=tf.consensus,
            reference_feature_5m=tf.reference_feature)


@dataclass(frozen=True)
class V2FamilySignal:
    """One family's own verdict for this boundary, BEFORE deadline/expiry
    composition: `CONFIRM`, `FALSE_BREAK`, `HOLD`, or `UNAVAILABLE`.

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
    shape IS the current one, and a fresh process reconstructs it exactly."""
    _require_history(history)
    identity = history.creation_identity
    if identity.setup_family != TREND_PULLBACK:
        return None
    buffer = _creation_protection_buffer(history)
    for event in reversed(history.events):
        payload = event.event_payload.get(OPERATIONAL_FACTS_KEY)
        if payload is None:
            continue
        payload = _mapping(payload, OPERATIONAL_FACTS_KEY)
        raw_bucket = payload.get(_OF_SOURCE_BUCKET)
        source_bucket = None
        if raw_bucket is not None:
            if not isinstance(raw_bucket, str):
                raise V2EpisodeLifecycleError(
                    f"episode {history.episode_id!r}'s persisted {_OF_SOURCE_BUCKET}="
                    f"{raw_bucket!r} must be an ISO-8601 string")
            try:
                source_bucket = datetime.fromisoformat(raw_bucket)
            except (TypeError, ValueError) as exc:
                raise V2EpisodeLifecycleError(
                    f"episode {history.episode_id!r}'s persisted {_OF_SOURCE_BUCKET}="
                    f"{raw_bucket!r} is not a parseable ISO-8601 datetime: {exc}") from exc
        return _build_trend_pullback_operational_facts(
            direction=identity.direction,
            pullback_extreme=_finite_price(
                payload.get(_OF_PULLBACK_EXTREME), _OF_PULLBACK_EXTREME),
            dynamic_bound=_finite_price(payload.get(_OF_DYNAMIC_BOUND), _OF_DYNAMIC_BOUND),
            protection_buffer=buffer,
            source=str(payload.get(_OF_SOURCE, OPERATIONAL_SOURCE_REEVALUATION)),
            source_bucket=source_bucket)

    # No recorded update yet: the creation event's own facts are current.
    creation = _creation_facts(history)
    family_facts = _creation_family_facts(history)
    dynamic_bound = (
        creation.get(_CF_ENTRY_ZONE_UPPER) if identity.direction == LONG
        else creation.get(_CF_ENTRY_ZONE_LOWER))
    raw_bucket = family_facts.get(_FF_BUCKET_15M)
    source_bucket = None
    if isinstance(raw_bucket, str):
        try:
            source_bucket = datetime.fromisoformat(raw_bucket)
        except (TypeError, ValueError) as exc:
            raise V2EpisodeLifecycleError(
                f"episode {history.episode_id!r}'s creation {_FF_BUCKET_15M}={raw_bucket!r} is "
                f"not a parseable ISO-8601 datetime: {exc}") from exc
    return _build_trend_pullback_operational_facts(
        direction=identity.direction,
        pullback_extreme=_finite_price(
            family_facts.get(_FF_PULLBACK_EXTREME), f"creation {_FF_PULLBACK_EXTREME}"),
        dynamic_bound=_finite_price(dynamic_bound, "creation dynamic entry-zone bound"),
        protection_buffer=buffer, source=OPERATIONAL_SOURCE_CREATION,
        source_bucket=source_bucket)


@dataclass(frozen=True)
class V2TrendPullbackReevaluation:
    """§12.2a mechanism (1): the SAME `TREND_PULLBACK` episode's own
    structural leg, re-measured at a later legal 15m boundary.

    This is emphatically NOT mechanism (2). §12.2a forbids substituting a
    later, independently-detected candidate's own freshly-computed
    `trend_leg_extreme`/geometry into the episode's operational logic. The
    two mechanisms are told apart by exactly one fact: whether the
    observation re-measures THIS episode's frozen creation leg (§12.3 case
    A, an exact anchor match) or reports a DIFFERENT leg (case B/C). Only
    the former is a legitimate mechanism-(1) re-measurement, which is why
    `trend_pullback_reevaluation_from_candidate()` refuses anything but
    `MATCH_EXACT`.

    `pullback_extreme` is §7.1's "deepest close so far" over the contiguous
    span from the frozen anchor bucket through `B15'`; `current_close` is
    `close_price(B15', reference_exchange)`, §7.1's dynamic zone bound. The
    derived zone/invalidation geometry is NOT taken from the caller -- this
    unit re-derives it from §7.1's exact formula and the episode's own
    frozen creation `protection_buffer`."""
    T: datetime
    bucket_15m: datetime
    pullback_extreme: float
    current_close: float

    def __post_init__(self) -> None:
        T = _validate_decision_boundary(self.T, "reevaluation T")
        object.__setattr__(self, "T", T)
        # §7.1's re-evaluation happens at LATER 15m decision boundaries. A
        # 5m-only boundary is not one, and must not run structural
        # re-evaluation -- 15m is the FORMATION/re-measurement cadence, 5m
        # is the confirmation cadence, and §14 is explicit that conflating
        # them is wrong. Checked FIRST so a 5m-only boundary is reported as
        # what it is, rather than as a derived-bucket complaint.
        _validate_bucket_start(
            T - _REEVALUATION_BUCKET, "reevaluation T", timeframe=REEVALUATION_TIMEFRAME)
        if self.bucket_15m != T - _REEVALUATION_BUCKET:
            raise V2EpisodeLifecycleError(
                f"reevaluation bucket_15m={self.bucket_15m!r} is not "
                f"selected_bucket('15m', {T.isoformat()}) = "
                f"{(T - _REEVALUATION_BUCKET).isoformat()!r} -- §7.1 re-evaluates against "
                "B15' = selected_bucket(15m, T'), never another bucket")
        object.__setattr__(self, "pullback_extreme", _finite_price(
            self.pullback_extreme, "reevaluation pullback_extreme"))
        object.__setattr__(self, "current_close", _finite_price(
            self.current_close, "reevaluation current_close"))


def trend_pullback_reevaluation_from_candidate(
    candidate: V2CandidateFacts, history: V2EpisodeHistory, *, match_class: str,
) -> V2TrendPullbackReevaluation:
    """Build a mechanism-(1) re-evaluation from a Stage 5 `TREND_PULLBACK`
    observation that Unit 2 classified as §12.3 case A against THIS episode.

    `match_class` MUST be `MATCH_EXACT`. §12.2a forbids feeding a case-(B)
    candidate's own independently-detected leg into the episode's
    operational facts, and this refusal is structural rather than
    documentary: a non-exact match cannot be turned into a re-evaluation at
    all. An exact match, by definition, re-measures the episode's OWN frozen
    creation anchor -- which is precisely §7.1's mechanism-(1) process
    observed through the detector, not a substitution of a different leg.

    Only `pullback_extreme` and the 15m close are taken from the candidate.
    Its own zone/invalidation values are deliberately ignored: this unit
    re-derives them from §7.1's formula and the episode's frozen creation
    `protection_buffer`, so a drifted decision-time buffer can never rewrite
    an existing episode's geometry (§12.2a/§12.4's "always the creation
    value")."""
    _require_history(history)
    if not isinstance(candidate, V2CandidateFacts):
        raise V2EpisodeLifecycleError(
            f"candidate must be a V2CandidateFacts, got {type(candidate).__name__}")
    identity = history.creation_identity
    if identity.setup_family != TREND_PULLBACK:
        raise V2EpisodeLifecycleError(
            f"episode {history.episode_id!r} is {identity.setup_family!r}; only TREND_PULLBACK "
            "has a §12.2a pre-confirmation operational-update mechanism")
    if candidate.setup_family != TREND_PULLBACK:
        raise V2EpisodeLifecycleError(
            f"candidate is {candidate.setup_family!r}, not TREND_PULLBACK")
    if candidate.slot != identity.slot:
        raise V2EpisodeLifecycleError(
            f"candidate slot {candidate.slot!r} does not belong to episode "
            f"{history.episode_id!r} (slot {identity.slot!r})")
    if match_class != MATCH_EXACT:
        raise V2EpisodeLifecycleError(
            f"match_class={match_class!r} -- only a §12.3 case-A (exact structural-anchor match) "
            "observation is a mechanism-(1) re-measurement of THIS episode's own leg. §12.2a "
            "forbids substituting a differently-anchored candidate's freshly-detected "
            "trend_leg_extreme into the episode's operational facts; it may be RECORDED as an "
            "observation, never operationally substituted")
    family_facts = _mapping(candidate.family_facts, "candidate.family_facts")
    if _FF_PULLBACK_EXTREME not in family_facts:
        raise V2EpisodeLifecycleError(
            f"candidate carries no {_FF_PULLBACK_EXTREME!r} fact -- §7.1's re-evaluation needs "
            "the re-measured deepest close, and this unit never recovers it elsewhere")
    return V2TrendPullbackReevaluation(
        T=candidate.T, bucket_15m=candidate.T - _REEVALUATION_BUCKET,
        pullback_extreme=_finite_price(
            family_facts[_FF_PULLBACK_EXTREME], f"candidate {_FF_PULLBACK_EXTREME}"),
        current_close=_finite_price(
            candidate.entry_zone_upper if candidate.direction == LONG
            else candidate.entry_zone_lower,
            "candidate dynamic entry-zone bound"))


def _apply_reevaluation(
    history: V2EpisodeHistory, current: V2OperationalFacts,
    reevaluation: V2TrendPullbackReevaluation,
) -> V2OperationalFacts:
    """§7.1's monotonic "deepest close so far" rule, applied to the
    episode's own currently-valid facts.

    `pullback_extreme` MAY only deepen (lower for `LONG`, higher for
    `SHORT`). A re-measurement that reports a SHALLOWER extreme is refused
    rather than accepted: §7.1 says the extreme "update[s] only if the
    retracement deepens further", so a shallower value is either a
    mechanism-(2) leak or corrupt input, and silently walking the level back
    would rewrite an already-published structural fact."""
    direction = history.creation_identity.direction
    deepens = (
        reevaluation.pullback_extreme < current.pullback_extreme if direction == LONG
        else reevaluation.pullback_extreme > current.pullback_extreme)
    same = reevaluation.pullback_extreme == current.pullback_extreme
    if not (deepens or same):
        raise V2EpisodeLifecycleError(
            f"episode {history.episode_id!r} ({direction}) currently records "
            f"pullback_extreme={current.pullback_extreme!r}; the re-evaluation reports "
            f"{reevaluation.pullback_extreme!r}, which is SHALLOWER. §7.1 lets this fact update "
            "only if the retracement deepens further -- a shallower value is refused, never "
            "silently walked back")
    return _build_trend_pullback_operational_facts(
        direction=direction,
        pullback_extreme=(
            reevaluation.pullback_extreme if deepens else current.pullback_extreme),
        dynamic_bound=reevaluation.current_close,
        protection_buffer=_creation_protection_buffer(history),
        source=OPERATIONAL_SOURCE_REEVALUATION, source_bucket=reevaluation.bucket_15m)


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
    if not facts.required_family_quality_ok(TREND_PULLBACK):
        return V2FamilySignal(
            signal=SIGNAL_UNAVAILABLE, reason="REQUIRED_METRIC_FAMILY_UNAVAILABLE",
            evidence={"required_families": list(REQUIRED_METRIC_FAMILY[TREND_PULLBACK]),
                      "decision_bucket": facts.decision_bucket.isoformat()})
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
    if not facts.required_family_quality_ok(family):
        return V2FamilySignal(
            signal=SIGNAL_UNAVAILABLE, reason="REQUIRED_METRIC_FAMILY_UNAVAILABLE",
            evidence={"required_families": list(REQUIRED_METRIC_FAMILY[family]),
                      "decision_bucket": facts.decision_bucket.isoformat()})
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
    if not _is_finite(v):
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

    @property
    def requires_event(self) -> bool:
        return self.outcome in _EVENT_REQUIRED

    @property
    def is_terminal(self) -> bool:
        return self.outcome in (
            LIFECYCLE_INVALIDATED_FALSE_BREAK, LIFECYCLE_EXPIRED_CANDIDATE_AGE)


def evaluate_early_signal_transition(
    history: V2EpisodeHistory, *, T: datetime, facts: V2BoundaryFacts,
    reevaluation: Optional[V2TrendPullbackReevaluation] = None,
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

    signal = evaluate_family_signal(history, facts)

    def decide(outcome: str, reason: str,
               operational: Optional[V2OperationalFacts] = None) -> V2LifecycleDecision:
        return V2LifecycleDecision(
            episode_id=history.episode_id, T=T, setup_family=family, direction=direction,
            previous_state=EARLY_SIGNAL, new_state=OUTCOME_NEW_STATE[outcome], outcome=outcome,
            reason=reason, signal=signal, t_detect=t_detect, candidate_deadline=deadline,
            operational_facts=operational)

    # §12.2a mechanism (1): resolve the currently-valid TP operational facts
    # BEFORE branching, because a confirming boundary must freeze the facts
    # valid AT that exact decision -- including this boundary's own update.
    current_facts = read_operational_facts(history)
    updated_facts: Optional[V2OperationalFacts] = None
    if reevaluation is not None:
        if family != TREND_PULLBACK:
            raise V2EpisodeLifecycleError(
                f"a pre-confirmation re-evaluation was supplied for a {family!r} episode -- "
                "§12.2a gives only TREND_PULLBACK a pre-confirmation mutability mechanism")
        if not isinstance(reevaluation, V2TrendPullbackReevaluation):
            raise V2EpisodeLifecycleError(
                "reevaluation must be a V2TrendPullbackReevaluation, got "
                f"{type(reevaluation).__name__}")
        if reevaluation.T != T:
            raise V2EpisodeLifecycleError(
                f"reevaluation is for {reevaluation.T.isoformat()!r} but this decision is at "
                f"{T.isoformat()!r}")
        updated_facts = _apply_reevaluation(history, current_facts, reevaluation)

    # 2. §13.1 level 1 -- the breakout families' own pre-confirmation
    #    invalidation. A broken structural premise cannot be confirmed.
    if signal.signal == SIGNAL_FALSE_BREAK:
        return decide(LIFECYCLE_INVALIDATED_FALSE_BREAK, signal.reason,
                      updated_facts or current_facts)

    # 3. §13.1 level 3 -- confirmation. §9/§12.2a: the zone updates ONE final
    #    time here, now that confirmation_close_price exists, then freezes.
    blocked_reason: Optional[str] = None
    if signal.signal == SIGNAL_CONFIRM:
        frozen = updated_facts or current_facts
        confirmable = True
        if family == TREND_PULLBACK:
            confirmation_close = facts.reference_close
            if confirmation_close is None:
                # §7.1's CONFIRMED zone is [pullback_extreme,
                # confirmation_close_price]; without §11's canonical
                # reference close there is no confirmation_close_price to
                # freeze, and §22 forbids substituting anything for it. The
                # boundary falls through to the deadline/update ladder below
                # rather than returning early, so a same-`T` §9 zone change
                # is still recorded and the deadline still closes.
                confirmable = False
                blocked_reason = "CONFIRMATION_CLOSE_UNAVAILABLE"
            else:
                frozen = _build_trend_pullback_operational_facts(
                    direction=direction, pullback_extreme=frozen.pullback_extreme,
                    dynamic_bound=confirmation_close,
                    protection_buffer=_creation_protection_buffer(history),
                    source=OPERATIONAL_SOURCE_CONFIRMATION,
                    source_bucket=facts.decision_bucket)
        if confirmable:
            # §36/H3: one event per (stream, episode, boundary). A same-`T`
            # operational update is AGGREGATED into this single CONFIRMED
            # event, never emitted as a second EARLY_SIGNAL event at the
            # same boundary.
            return decide(LIFECYCLE_CONFIRMED, signal.reason, frozen)

    # 4. §13.1 level 2 / §14 -- the deadline boundary closed without this
    #    boundary's own confirmation check holding.
    if T == deadline:
        return decide(
            LIFECYCLE_EXPIRED_CANDIDATE_AGE,
            f"CANDIDATE_AGE_DEADLINE_{blocked_reason or signal.reason}",
            updated_facts or current_facts)

    # 5. §9 -- a genuinely CHANGED pre-`CONFIRMED` operational fact is
    #    recorded as a new immutable event (never a rewrite of an earlier one).
    if updated_facts is not None and not updated_facts.same_geometry(current_facts):
        return decide(
            LIFECYCLE_PRECONFIRMATION_UPDATE, "OPERATIONAL_FACTS_UPDATED", updated_facts)

    # 6. §12.11 -- nothing episode-visible changed; no event, no heartbeat.
    return decide(LIFECYCLE_NO_CHANGE, blocked_reason or signal.reason, current_facts)


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
    if decision.episode_id != history.episode_id:
        raise V2EpisodeLifecycleError(
            f"decision describes episode {decision.episode_id!r} but history is "
            f"{history.episode_id!r}")

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
