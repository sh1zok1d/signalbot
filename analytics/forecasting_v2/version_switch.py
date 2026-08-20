"""
V2-H2b: DRAIN-BEFORE-ACTIVATE version-switch state machine
(`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §3.1).

Closes risk `C-001` (`docs/PROJECT_RISK_AND_DEBT_REGISTER.md`): a version
switch must never mix old/new model semantics mid-episode. One logical
episode stays tied to ONE semantic tuple from creation through terminal
resolution; a newer tuple can never become active for new-episode creation
merely because config changed, a process restarted, or a newer
`calculation_version` exists -- the OLD tuple must satisfy the frozen drain
condition first.

**Exact §3.1 semantics implemented, restated precisely:**

The semantic tuple that is switched is `(rules_version, calculation_version,
decision_code_version)` -- `model_family` is excluded because it is always
the frozen constant `"v2"` and never varies (§3). The scope of one switch's
state is exactly one `execution_stream = (run_kind, run_id)` (§12.10) --
NOT `symbol`/`market_type`: §3.1 frames the policy in terms of "a logical
LIVE stream", and §12.10 freezes `execution_stream` as exactly that scope
for every other per-stream state (same-slot occupancy, cooldowns,
`preexisting_opposite_active_set`). `symbol`/`market_type` participate only
in the SEPARATE §3.3 activation-readiness check this module composes with
(via the orchestration layer, `version_switch_orchestrator.py`), never in
the switch state itself.

At `T_request`, OLD unconditionally enters `DRAINING` and NEW becomes
`PENDING` -- OLD MUST NOT create any new episode from `T_request` onward,
not even one that would otherwise have qualified under its own rules
("no grandfathering"); NEW MUST NOT create any episode until OLD has fully
drained. Therefore `active_for_new_creation_tuple_count == 0` throughout an
active drain -- never 1 ("OLD, until NEW takes over"), never more than 1.
"Drained" means BOTH OLD's non-terminal (`ACTIVE`) episode count AND OLD's
active same-slot-cooldown count (§12.8) are exactly zero, evaluated at a
legal 5m decision boundary. The boundary that FIRST observes zero-zero is
`drain_complete_at` (`T_drain`) -- that boundary's own computation belongs
entirely to OLD's provenance; NEW never activates at `T_drain` itself, only
at a STRICTLY LATER legal boundary (`T_activate`, normally `T_drain + 5m`)
-- this avoids a same-boundary OLD/NEW provenance ambiguity (§3.1's
"exact drain-completion / activation boundary" clause). If OLD is already
fully drained at `T_request` itself (including the vacuous case where OLD
has never had an active tuple at all -- a fresh execution_stream's very
first activation), `drain_complete_at = T_request` and NEW still does not
activate until `T_request + 5m` -- same reasoning, no exception for "there
was nothing to actually wait for" (§3.1 vector C).

This module additionally requires NEW's §3.3 activation-readiness verdict
to be `True` before activating -- §3.1 itself is silent on readiness (it is
a separate contract clause), but the task this module implements requires
composing the two: a drained-for OLD does not, by itself, make NEW eligible
to create episodes if NEW's own historical/percentile prerequisites are not
yet materialized. Readiness is consulted ONLY once drain is already known
complete (`AWAITING_ACTIVATION_READINESS`) and the boundary being evaluated
is strictly later than `drain_complete_at` -- it can never affect an
in-progress drain (drain gates unconditionally first), and it is never
queried before it could possibly matter.

Restart durability: this module is a PURE, deterministic function of
`(persisted state, decision_boundary, facts)` -- reloading the same
persisted `V2VersionSwitchState` and calling `evaluate_version_switch_
transition()` again with the same boundary/facts always reproduces the same
result. A caller (the storage-backed orchestration layer) is responsible for
actually persisting `V2VersionSwitchTransitionResult.state` durably before
acting on it; this module has no I/O of its own and cannot durably persist
anything by itself.

**Conflicting-request policy (contract wording left open; smallest durable
representation chosen per this module's own task, not invented product
semantics):** while a switch is already `PENDING` (`DRAINING` or
`AWAITING_ACTIVATION_READINESS`), a repeat request for the SAME pending
target is a no-op (idempotent); any OTHER target -- including a request to
return to the currently-`active` tuple -- is REFUSED with
`V2VersionSwitchError`, never silently overwritten. §3.1 describes no
cancellation/override mechanism for an in-progress drain, and inventing one
here would risk exactly the "OLD replenishing itself" failure mode §3.1's
own re-amendment closed by construction.

**Stage-6 non-scope.** This module answers only "which semantic tuple is
active for new-episode creation, and what should the persisted switch state
become, given these facts" -- it does NOT implement candidate arbitration,
`EARLY_SIGNAL` creation, confirmation, `WEAKENING`, invalidation, horizon
expiry, reversal semantics, or any other Stage 6 episode-lifecycle logic.
The `non_terminal_episode_count`/`active_cooldown_count` OLD-drain fact this
module consumes (`V2DrainFact`) is supplied by the CALLER as an already-
computed integer pair -- this module never queries a database, never reads
`v2_episode_events`, and never decides what counts as non-terminal or an
active cooldown; that is Stage 6's job, once it exists. See
`analytics/forecasting_v2/ports.py`'s `V2VersionDrainStatusReader` for the
narrow read-port abstraction the orchestration layer depends on instead of
a real Stage-6 query.

Pure only: no DB, network, filesystem, clock (`datetime.now()`/
`datetime.utcnow()`), `uuid`, or `random` access anywhere in this module --
identical purity discipline to every other V2-H2a module
(`decision_provenance.py`, `decision_view.py`, `activation_readiness.py`'s
own value objects). `decision_boundary`/`requested_at`/`drain_complete_at`
are all caller-supplied, already-resolved values.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from analytics.forecasting_v2._validation import nonblank, one_of, validate_calculation_version
from analytics.forecasting_v2.alignment import V2AlignmentError, selected_bucket
from analytics.forecasting_v2.decision_provenance import V2DecisionProvenance
from analytics.forecasting_v2.events import RUN_KINDS
from common.v2_config import validate_rules_version

__all__ = [
    "V2VersionSwitchError",
    "V2SemanticTuple",
    "V2DrainFact",
    "PHASE_NO_PENDING_SWITCH", "PHASE_DRAINING", "PHASE_AWAITING_ACTIVATION_READINESS",
    "SWITCH_PHASES",
    "V2VersionSwitchState",
    "initial_switch_state",
    "ACTION_NO_OP", "ACTION_DRAIN_CONTINUES", "ACTION_DRAIN_COMPLETE",
    "ACTION_AWAITING_READINESS", "ACTION_ACTIVATED",
    "SWITCH_ACTIONS",
    "V2VersionSwitchTransitionResult",
    "evaluate_version_switch_transition",
    "assert_provenance_matches_active_tuple",
]


class V2VersionSwitchError(ValueError):
    """Malformed version-switch input: bad run identity, a non-legal-5m
    decision boundary, an inconsistent/impossible persisted state, a
    conflicting switch request while one is already pending, a scope
    mismatch, or a missing fact the current phase requires (`drain_fact`
    while `DRAINING`, `candidate_ready` once drain is complete and the
    boundary is strictly later than `drain_complete_at`). Never raised
    merely because a candidate is legitimately NOT_READY or OLD is
    legitimately NOT_DRAINED -- those are ordinary `ACTION_DRAIN_CONTINUES`/
    `ACTION_AWAITING_READINESS` results, not errors."""


def _validate_decision_boundary(value: Any) -> datetime:
    """A legal V2 5m decision boundary -- delegated to
    `alignment.selected_bucket("5m", value)`, the same canonical source of
    truth every other H2a/H2b module uses (see `decision_provenance.py`'s
    identically-shaped helper for the full rationale: this is the single
    implementation of "is T a legal V2 5m decision boundary", and it never
    itself calls `.utcoffset()` so a malformed/malicious custom `tzinfo`
    can never leak a raw exception past this module's boundary)."""
    try:
        selected_bucket("5m", value)
    except V2AlignmentError as exc:
        raise V2VersionSwitchError(f"decision_boundary: {exc}") from exc
    except Exception as exc:  # noqa: BLE001 - malformed/malicious tzinfo, or any
        # other unexpected failure inside the delegated alignment check --
        # never leaked past this module's boundary as a raw exception.
        raise V2VersionSwitchError(
            f"decision_boundary failed alignment validation: "
            f"{type(exc).__name__}: {exc}") from exc
    return value


@dataclass(frozen=True)
class V2SemanticTuple:
    """The exact §3.1 semantic tuple: `(rules_version, calculation_version,
    decision_code_version)`. Deliberately excludes `model_family` (always
    the frozen constant `"v2"`, never a switch dimension) and excludes
    `feature_schema_version`/`config_hash`/`config_version`/`code_version`
    (these are already fully determined BY `calculation_version` --
    `common.versioning.compute_calculation_version` -- so including them
    here would let a caller construct a self-contradictory tuple with a
    `calculation_version` that does not match its own accompanying
    identity fields; the switch machinery only ever needs to compare
    `calculation_version` values, never re-derive them)."""
    rules_version: str
    calculation_version: str
    decision_code_version: str

    def __post_init__(self) -> None:
        try:
            validate_rules_version(self.rules_version)
        except ValueError as exc:
            raise V2VersionSwitchError(str(exc)) from exc
        validate_calculation_version(self.calculation_version, V2VersionSwitchError)
        nonblank(self.decision_code_version, "decision_code_version", V2VersionSwitchError)


@dataclass(frozen=True)
class V2DrainFact:
    """OLD's population as of one decision boundary, scoped to exactly one
    `execution_stream` and exactly the OLD semantic tuple (§3.1: "any
    non-terminal (ACTIVE) episodes OR active same-slot cooldowns (§12.8)").
    Both counts must be non-negative integers -- a negative or non-int
    count is malformed input, never silently coerced. `drained` is `True`
    iff BOTH are exactly zero; a caller may not report "drained" via any
    other channel (e.g. a bare bool with no underlying counts) so that a
    corrupted/fabricated drain signal can never masquerade as this type."""
    non_terminal_episode_count: int
    active_cooldown_count: int

    def __post_init__(self) -> None:
        for name in ("non_terminal_episode_count", "active_cooldown_count"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise V2VersionSwitchError(f"{name} must be a non-negative int, got {value!r}")

    @property
    def drained(self) -> bool:
        return self.non_terminal_episode_count == 0 and self.active_cooldown_count == 0


PHASE_NO_PENDING_SWITCH = "NO_PENDING_SWITCH"
PHASE_DRAINING = "DRAINING"
PHASE_AWAITING_ACTIVATION_READINESS = "AWAITING_ACTIVATION_READINESS"
SWITCH_PHASES = (PHASE_NO_PENDING_SWITCH, PHASE_DRAINING, PHASE_AWAITING_ACTIVATION_READINESS)


@dataclass(frozen=True)
class V2VersionSwitchState:
    """Durable per-`execution_stream` version-switch state. Exactly ONE
    logical row per `(run_kind, run_id)` scope represents this -- see
    `storage/stage2_schema.sql`'s `v2_version_switch_state` table, whose
    `PRIMARY KEY (run_kind, run_id)` enforces "at most one active identity
    and at most one pending target per scope" (§9) trivially, by
    construction, rather than via a second uniqueness constraint across
    multiple rows.

    `active` is `None` only before this execution_stream's first-ever
    activation (a fresh `LIVE`/`REPLAY` stream that has never had a tuple
    become active for new-episode creation) -- NOT a legal state for any
    stream that has ever activated a tuple.

    `pending`/`drain_complete_at`/`requested_at` are all `None` together
    (`PHASE_NO_PENDING_SWITCH`) or all meaningfully set together (during a
    switch) -- see `__post_init__` for the exact per-phase shape this
    enforces. `pending` is never equal to `active` (that would not be a
    switch at all -- see `evaluate_version_switch_transition`'s "same
    identity requested" no-op handling, which never persists such a
    state)."""
    run_kind: str
    run_id: str
    active: Optional[V2SemanticTuple]
    pending: Optional[V2SemanticTuple]
    phase: str
    drain_complete_at: Optional[datetime]
    requested_at: Optional[datetime]

    def __post_init__(self) -> None:
        one_of(self.run_kind, "run_kind", RUN_KINDS, V2VersionSwitchError)
        nonblank(self.run_id, "run_id", V2VersionSwitchError)
        one_of(self.phase, "phase", SWITCH_PHASES, V2VersionSwitchError)

        if self.active is not None and not isinstance(self.active, V2SemanticTuple):
            raise V2VersionSwitchError(
                f"active must be None or a V2SemanticTuple, got {type(self.active).__name__}")
        if self.pending is not None and not isinstance(self.pending, V2SemanticTuple):
            raise V2VersionSwitchError(
                f"pending must be None or a V2SemanticTuple, got {type(self.pending).__name__}")

        if self.phase == PHASE_NO_PENDING_SWITCH:
            if self.pending is not None:
                raise V2VersionSwitchError("PHASE_NO_PENDING_SWITCH requires pending=None")
            if self.drain_complete_at is not None:
                raise V2VersionSwitchError(
                    "PHASE_NO_PENDING_SWITCH requires drain_complete_at=None")
            if self.requested_at is not None:
                raise V2VersionSwitchError(
                    "PHASE_NO_PENDING_SWITCH requires requested_at=None")
            return

        # DRAINING or AWAITING_ACTIVATION_READINESS: a switch is in progress.
        if self.pending is None:
            raise V2VersionSwitchError(f"phase {self.phase!r} requires a non-None pending tuple")
        if self.pending == self.active:
            raise V2VersionSwitchError(
                "pending must not equal active -- that is not a switch")
        if self.requested_at is None:
            raise V2VersionSwitchError(f"phase {self.phase!r} requires a non-None requested_at")
        _validate_decision_boundary(self.requested_at)

        if self.phase == PHASE_DRAINING:
            if self.drain_complete_at is not None:
                raise V2VersionSwitchError("PHASE_DRAINING requires drain_complete_at=None")
        else:  # PHASE_AWAITING_ACTIVATION_READINESS
            if self.drain_complete_at is None:
                raise V2VersionSwitchError(
                    "PHASE_AWAITING_ACTIVATION_READINESS requires a non-None drain_complete_at")
            _validate_decision_boundary(self.drain_complete_at)
            if self.drain_complete_at < self.requested_at:
                raise V2VersionSwitchError("drain_complete_at must be >= requested_at")


def initial_switch_state(*, run_kind: str, run_id: str) -> V2VersionSwitchState:
    """The state for an `execution_stream` that has never activated a tuple
    and has no pending switch -- the durable row's bootstrap identity, NOT
    itself a switch. `evaluate_version_switch_transition()` treats a fresh
    request against this state exactly like any other switch request
    (drain gates first) -- OLD's vacuous "population" (`active is None`) is
    represented by the caller supplying `V2DrainFact(0, 0)` (see
    `version_switch_orchestrator.py`), never by a special-cased code path
    here, so `T_request + 5m` activation timing (never `T_request` itself)
    applies uniformly, including to a stream's very first activation."""
    return V2VersionSwitchState(
        run_kind=run_kind, run_id=run_id, active=None, pending=None,
        phase=PHASE_NO_PENDING_SWITCH, drain_complete_at=None, requested_at=None)


ACTION_NO_OP = "NO_OP"
ACTION_DRAIN_CONTINUES = "DRAIN_CONTINUES"
ACTION_DRAIN_COMPLETE = "DRAIN_COMPLETE"
ACTION_AWAITING_READINESS = "AWAITING_READINESS"
ACTION_ACTIVATED = "ACTIVATED"
SWITCH_ACTIONS = (
    ACTION_NO_OP, ACTION_DRAIN_CONTINUES, ACTION_DRAIN_COMPLETE,
    ACTION_AWAITING_READINESS, ACTION_ACTIVATED,
)


@dataclass(frozen=True)
class V2VersionSwitchTransitionResult:
    """The outcome of evaluating one legal 5m decision boundary against a
    persisted `V2VersionSwitchState`: the NEW state a caller MUST durably
    persist (atomically, before acting on it further -- this module has no
    opinion on HOW; see `version_switch_orchestrator.py`), which `action`
    occurred, and whether THIS call's `requested` argument started a
    genuinely new pending switch (`request_accepted`) -- `False` for a
    no-request call, an idempotent same-identity/duplicate-pending request,
    or (implicitly, via a raised `V2VersionSwitchError`) a refused
    conflicting request."""
    state: V2VersionSwitchState
    action: str
    request_accepted: bool

    def __post_init__(self) -> None:
        if not isinstance(self.state, V2VersionSwitchState):
            raise V2VersionSwitchError(
                f"state must be a V2VersionSwitchState, got {type(self.state).__name__}")
        one_of(self.action, "action", SWITCH_ACTIONS, V2VersionSwitchError)
        if not isinstance(self.request_accepted, bool):
            raise V2VersionSwitchError(
                f"request_accepted must be a bool, got {type(self.request_accepted).__name__}")


def evaluate_version_switch_transition(
    state: V2VersionSwitchState,
    *,
    decision_boundary: datetime,
    requested: Optional[V2SemanticTuple] = None,
    drain_fact: Optional[V2DrainFact] = None,
    candidate_ready: Optional[bool] = None,
) -> V2VersionSwitchTransitionResult:
    """Evaluate exactly ONE legal 5m decision boundary `T` against the
    persisted `state`, per the exact §3.1 semantics this module's docstring
    restates. Pure: no I/O, no clock, deterministic in its explicit
    arguments.

    `requested`: a caller-supplied target tuple IF an operator/runtime is
    requesting a switch to it at this boundary; `None` if no request is
    being made this call (the normal case -- most boundaries do not carry a
    request; this function still must be called for them to advance any
    ALREADY-pending drain).

    `drain_fact`: OLD's population as of `T`, REQUIRED whenever this
    evaluation could depend on it (`state.phase == PHASE_DRAINING`, or a
    genuinely new request is being made from `PHASE_NO_PENDING_SWITCH`) --
    omitting it in that case is a caller bug, not a legitimate "assume
    drained", and raises `V2VersionSwitchError`.

    `candidate_ready`: NEW's §3.3 activation-readiness verdict as of `T`,
    REQUIRED only once drain is already known complete
    (`PHASE_AWAITING_ACTIVATION_READINESS`) AND `T` is strictly later than
    `state.drain_complete_at` -- omitting it in that case is likewise a
    caller bug, never a silent "assume not ready" or "assume ready".

    Raises `V2VersionSwitchError` for: a non-legal `decision_boundary`; a
    wrong-typed `requested`/`drain_fact`/`candidate_ready`; a conflicting
    switch request while one is already pending for a DIFFERENT target; or
    a missing required fact for the current phase. Never raises merely
    because OLD is legitimately not yet drained or NEW is legitimately not
    yet ready -- those produce `ACTION_DRAIN_CONTINUES`/
    `ACTION_AWAITING_READINESS` results."""
    T = _validate_decision_boundary(decision_boundary)
    if requested is not None and not isinstance(requested, V2SemanticTuple):
        raise V2VersionSwitchError(
            f"requested must be None or a V2SemanticTuple, got {type(requested).__name__}")
    if drain_fact is not None and not isinstance(drain_fact, V2DrainFact):
        raise V2VersionSwitchError(
            f"drain_fact must be None or a V2DrainFact, got {type(drain_fact).__name__}")
    if candidate_ready is not None and not isinstance(candidate_ready, bool):
        raise V2VersionSwitchError(
            f"candidate_ready must be None or a bool, got {type(candidate_ready).__name__}")

    working = state
    request_accepted = False

    # ---- step 1: handle an incoming request, if any -------------------------
    if requested is not None:
        if working.phase == PHASE_NO_PENDING_SWITCH:
            if working.active == requested:
                pass  # vector 2: same identity requested -> idempotent no-op.
            else:
                working = V2VersionSwitchState(
                    run_kind=working.run_kind, run_id=working.run_id,
                    active=working.active, pending=requested,
                    phase=PHASE_DRAINING, drain_complete_at=None, requested_at=T)
                request_accepted = True
        else:
            # A switch is already pending (DRAINING or
            # AWAITING_ACTIVATION_READINESS).
            if requested == working.pending:
                pass  # vector 8: duplicate identical request -> idempotent.
            else:
                raise V2VersionSwitchError(
                    "a version switch is already pending for execution_stream "
                    f"(run_kind={working.run_kind!r}, run_id={working.run_id!r}): "
                    f"pending={working.pending!r}; a conflicting target "
                    f"{requested!r} was requested (even if it equals the currently-"
                    "active tuple) -- refusing to silently overwrite or cancel the "
                    "in-progress switch; §3.1 defines no such override")

    # ---- step 2: advance drain / attempt activation for any pending switch --
    if working.phase == PHASE_NO_PENDING_SWITCH:
        return V2VersionSwitchTransitionResult(
            state=working, action=ACTION_NO_OP, request_accepted=request_accepted)

    if working.phase == PHASE_DRAINING:
        if drain_fact is None:
            raise V2VersionSwitchError(
                "drain_fact is required while a switch is pending (phase=DRAINING) -- "
                "the caller must supply OLD's real non-terminal-episode/active-cooldown "
                "counts; this function never silently assumes OLD is drained")
        if drain_fact.drained:
            new_state = V2VersionSwitchState(
                run_kind=working.run_kind, run_id=working.run_id,
                active=working.active, pending=working.pending,
                phase=PHASE_AWAITING_ACTIVATION_READINESS,
                drain_complete_at=T, requested_at=working.requested_at)
            return V2VersionSwitchTransitionResult(
                state=new_state, action=ACTION_DRAIN_COMPLETE, request_accepted=request_accepted)
        return V2VersionSwitchTransitionResult(
            state=working, action=ACTION_DRAIN_CONTINUES, request_accepted=request_accepted)

    # working.phase == PHASE_AWAITING_ACTIVATION_READINESS
    if T < working.drain_complete_at:
        raise V2VersionSwitchError(
            f"decision_boundary {T.isoformat()} is EARLIER than the already-persisted "
            f"drain_complete_at {working.drain_complete_at.isoformat()} -- decision "
            "boundaries must be evaluated in non-decreasing order; this is a caller "
            "ordering bug, never silently accepted")
    if T == working.drain_complete_at:
        # The boundary that observed drain completion is entirely OLD's own
        # provenance boundary (§3.1) -- NEW never activates here, even if
        # this is somehow re-evaluated. No fact is needed to know this.
        return V2VersionSwitchTransitionResult(
            state=working, action=ACTION_AWAITING_READINESS, request_accepted=request_accepted)
    if candidate_ready is None:
        raise V2VersionSwitchError(
            "candidate_ready is required once drain is complete and this boundary is "
            "strictly later than drain_complete_at -- the caller must supply NEW's real "
            "§3.3 activation-readiness verdict; this function never silently assumes "
            "ready or not-ready")
    if not candidate_ready:
        return V2VersionSwitchTransitionResult(
            state=working, action=ACTION_AWAITING_READINESS, request_accepted=request_accepted)

    activated = V2VersionSwitchState(
        run_kind=working.run_kind, run_id=working.run_id,
        active=working.pending, pending=None,
        phase=PHASE_NO_PENDING_SWITCH, drain_complete_at=None, requested_at=None)
    return V2VersionSwitchTransitionResult(
        state=activated, action=ACTION_ACTIVATED, request_accepted=request_accepted)


def assert_provenance_matches_active_tuple(
    provenance: V2DecisionProvenance, active: V2SemanticTuple,
) -> None:
    """§3.4/§12 integration guard (task vector 12): a resolved
    `V2DecisionProvenance` (`decision_provenance.py`, already-merged H2a)
    MUST carry exactly the switch-resolved `active` semantic tuple -- never
    a stale/mismatched `rules_version`/`calculation_version`/
    `decision_code_version` combination. This module never mutates or
    re-derives `V2DecisionProvenance` itself (H2a's own construction/
    validation is untouched); it only asserts the two already-independently-
    validated objects AGREE, so a caller cannot accidentally compute/persist
    a Stage 3/4/5/6 result under a provenance tuple that does not match
    what H2b actually resolved as active for this boundary. Raises
    `V2VersionSwitchError` on any mismatch across the three switch-relevant
    fields; raises for a wrong-typed argument too."""
    if not isinstance(provenance, V2DecisionProvenance):
        raise V2VersionSwitchError(
            f"provenance must be a V2DecisionProvenance, got {type(provenance).__name__}")
    if not isinstance(active, V2SemanticTuple):
        raise V2VersionSwitchError(
            f"active must be a V2SemanticTuple, got {type(active).__name__}")
    provenance_tuple = (
        provenance.rules_version, provenance.calculation_version, provenance.decision_code_version)
    active_tuple = (active.rules_version, active.calculation_version, active.decision_code_version)
    if provenance_tuple != active_tuple:
        raise V2VersionSwitchError(
            "provenance (rules_version, calculation_version, decision_code_version) "
            f"{provenance_tuple!r} does not match the switch-resolved active tuple "
            f"{active_tuple!r} -- refusing to compose a decision view under the wrong "
            "version identity")
