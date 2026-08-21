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

**§3.1's DRAIN-BEFORE-ACTIVATE switch machine is LIVE-only (tech-lead
amendment round 1, finding 1).** §3.1's own opening lines: "`REPLAY`: one
replay `execution_stream` pins **exactly one** semantic tuple ... for its
**entire run**. A replay run never switches versions mid-run; a version
change requires a new, separately-identified replay run." A `REPLAY`
`V2VersionSwitchState` can therefore NEVER legally hold `phase in
(PHASE_DRAINING, PHASE_AWAITING_ACTIVATION_READINESS)` -- enforced both at
`V2VersionSwitchState.__post_init__` (so no such instance can even be
constructed) and, redundantly, as an explicit early rejection in
`evaluate_version_switch_transition()` before any switch-initiating state
would be built (fail fast with a specific reason, not a generic
`__post_init__` failure). `REPLAY` still needs its ONE pinned tuple
provisioned -- see `provision_initial_tuple()` below, a deliberately
SEPARATE, non-switch operation both run kinds share.

**Initial tuple provisioning is a SEPARATE concept from OLD->NEW switching
(tech-lead amendment round 1, finding 2).** An earlier draft of this module
incorrectly treated a fresh `execution_stream`'s first-ever activation
(`active is None`) as an instance of §3.1's own worked vector C ("OLD
already drained at `T_request`") and therefore imposed the SAME
`T_request + 5m` drain-completion delay on it. That claim is NOT supported
by §3.1: vector C is about an EXISTING OLD tuple that happens to already
have zero non-terminal episodes/cooldowns at the moment a NEW tuple is
requested -- it presupposes an OLD/NEW pair and a genuine switch in
progress. A stream that has never had ANY active tuple is not "OLD,
already drained" -- there is no OLD, no mixing-of-semantics risk to guard
against, and therefore no textual basis in §3.1 for imposing its
same-boundary-provenance-ambiguity delay. `provision_initial_tuple()` sets
`active` directly, at the first boundary its candidate's §3.3 readiness
holds -- no drain concept, no persisted intermediate "pending" state, no
`+5m` delay. It is intentionally usable by BOTH `LIVE` and `REPLAY` (every
stream, of either kind, needs its first tuple set exactly once), while
`evaluate_version_switch_transition()`'s OLD->NEW switching path remains
`LIVE`-only and requires `state.active` to already be set.

At `T_request` (a genuine switch, `state.active` already set), OLD
unconditionally enters `DRAINING` and NEW becomes `PENDING` -- OLD MUST NOT
create any new episode from `T_request` onward, not even one that would
otherwise have qualified under its own rules ("no grandfathering"); NEW
MUST NOT create any episode until OLD has fully drained. Therefore
`active_for_new_creation_tuple_count == 0` throughout an active drain --
never 1 ("OLD, until NEW takes over"), never more than 1.
"Drained" means BOTH OLD's non-terminal (`ACTIVE`) episode count AND OLD's
active same-slot-cooldown count (§12.8) are exactly zero, evaluated at a
legal 5m decision boundary FOR THE EXACT SAME `execution_stream` and OLD
semantic tuple this switch is draining (see `V2DrainFact`'s own docstring
for the self-scoping this module now REQUIRES, tech-lead amendment round 1
finding 3). The boundary that FIRST observes zero-zero is
`drain_complete_at` (`T_drain`) -- that boundary's own computation belongs
entirely to OLD's provenance; NEW never activates at `T_drain` itself, only
at a STRICTLY LATER legal boundary (`T_activate`, normally `T_drain + 5m`)
-- this avoids a same-boundary OLD/NEW provenance ambiguity (§3.1's
"exact drain-completion / activation boundary" clause).

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

**Fail-closed `active_for_new_creation` surface (tech-lead amendment round
1, finding 4).** `active_for_new_creation(state)` is the single, explicit
answer to "which semantic tuple, if any, may create a NEW episode right
now": the steady-state tuple (`state.active`, which generalizes correctly
to `REPLAY` too -- a `REPLAY` stream is always steady by construction, per
finding 1 above) when `phase == PHASE_NO_PENDING_SWITCH`, and `None`
(zero tuples eligible) throughout `DRAINING`/`AWAITING_ACTIVATION_
READINESS`. `assert_provenance_authorized_for_new_creation()` is the
companion guard a future Stage 6 new-episode-creation boundary MUST call:
it verifies `execution_stream` scope (`run_kind`/`run_id`) agreement AND
that the provenance's tuple equals `active_for_new_creation(state)` --
critically, it REJECTS new-episode creation during an active drain even
when the supplied provenance's tuple exactly equals the OLD tuple being
drained (a provenance match against OLD is never sufficient by itself;
only `active_for_new_creation` being non-`None` is).

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

**Non-decreasing decision-boundary discipline (tech-lead amendment round 1,
finding 5).** Whenever a switch is pending (`DRAINING` or
`AWAITING_ACTIVATION_READINESS`), `decision_boundary` MUST NOT be earlier
than `state.requested_at` -- evaluating a boundary that predates the switch
request itself would be a caller ordering bug (decision boundaries must be
processed in non-decreasing order), never silently accepted.

**A pending switch always has an OLD active tuple (tech-lead amendment
round 2, finding 1).** Since initial provisioning is now a wholly SEPARATE
operation from OLD->NEW switching (finding 2 above), the states `active=
None, pending=NEW, phase=DRAINING` and `active=None, pending=NEW, phase=
AWAITING_ACTIVATION_READINESS` are impossible by construction: a pending
H2b switch always means OLD exists (`state.active`) and NEW is `state.
pending`. `V2VersionSwitchState.__post_init__` enforces `phase !=
PHASE_NO_PENDING_SWITCH => active is not None` unconditionally -- this is
NOT merely a refusal by `evaluate_version_switch_transition()` to START
such a state; a persisted/reloaded row claiming to be mid-switch with no
OLD active tuple can never even be CONSTRUCTED as a `V2VersionSwitchState`,
regardless of caller. `storage/stage2_schema.sql`'s `v2_version_switch_
state` table mirrors this exact invariant with a `CHECK` constraint (see
that file's own comments) so a corrupted/hand-crafted row can never be
persisted in Postgres either.

**Stage-6 non-scope.** This module answers only "which semantic tuple is
active for new-episode creation, and what should the persisted switch state
become, given these facts" -- it does NOT implement candidate arbitration,
`EARLY_SIGNAL` creation, confirmation, `WEAKENING`, invalidation, horizon
expiry, reversal semantics, or any other Stage 6 episode-lifecycle logic.
The `non_terminal_episode_count`/`active_cooldown_count` OLD-drain fact this
module consumes (`V2DrainFact`) is supplied by the CALLER as an already-
computed integer pair (plus the self-scoping identity fields this module now
verifies before trusting them) -- this module never queries a database,
never reads `v2_episode_events`, and never decides what counts as
non-terminal or an active cooldown; that is Stage 6's job, once it exists.
See `analytics/forecasting_v2/ports.py`'s `V2VersionDrainStatusReader` for
the narrow read-port abstraction the orchestration layer depends on instead
of a real Stage-6 query.

Pure only: no DB, network, filesystem, clock (`datetime.now()`/
`datetime.utcnow()`), `uuid`, or `random` access anywhere in this module --
identical purity discipline to every other V2-H2a module
(`decision_provenance.py`, `decision_view.py`, `activation_readiness.py`'s
own value objects). `decision_boundary`/`requested_at`/`drain_complete_at`/
`as_of` are all caller-supplied, already-resolved values.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from analytics.forecasting_v2._validation import nonblank, one_of, validate_calculation_version
from analytics.forecasting_v2.alignment import V2AlignmentError, selected_bucket
from analytics.forecasting_v2.decision_provenance import V2DecisionProvenance
from analytics.forecasting_v2.events import LIVE, REPLAY, RUN_KINDS
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
    "ACTION_INITIAL_PROVISION_AWAITING_READINESS", "ACTION_INITIAL_ACTIVATED",
    "SWITCH_ACTIONS",
    "V2VersionSwitchTransitionResult",
    "evaluate_version_switch_transition",
    "provision_initial_tuple",
    "active_for_new_creation",
    "assert_provenance_authorized_for_new_creation",
]


class V2VersionSwitchError(ValueError):
    """Malformed version-switch input: bad run identity, a non-legal-5m
    decision boundary, an inconsistent/impossible persisted state, a
    conflicting switch request while one is already pending, a scope
    mismatch (execution_stream, OLD tuple, or as_of boundary between a
    `V2DrainFact` and the switch it claims to describe), an attempted
    switch on a `REPLAY` execution_stream, an attempted OLD->NEW switch
    request routed to `provision_initial_tuple()` (or vice versa), an
    out-of-order decision boundary, or a missing fact the current phase
    requires (`drain_fact` while `DRAINING`, `candidate_ready` once drain
    is complete and the boundary is strictly later than
    `drain_complete_at`). Never raised merely because a candidate is
    legitimately NOT_READY or OLD is legitimately NOT_DRAINED -- those are
    ordinary `ACTION_DRAIN_CONTINUES`/`ACTION_AWAITING_READINESS` results,
    not errors."""


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
    """OLD's population as of one decision boundary, SELF-SCOPED (tech-lead
    amendment round 1, finding 3) to exactly the `execution_stream` and OLD
    semantic tuple it claims to describe -- `run_kind`, `run_id`,
    `old_tuple`, and `as_of`, alongside the two counts (§3.1: "any
    non-terminal (ACTIVE) episodes OR active same-slot cooldowns
    (§12.8)"). `evaluate_version_switch_transition()` verifies ALL FOUR
    scope fields match the switch it is being consulted for BEFORE ever
    consulting `.drained` -- a `V2DrainFact` computed for the wrong
    execution_stream, the wrong OLD tuple, or the wrong boundary can never
    be silently accepted as this switch's own drain status; a mismatch
    raises `V2VersionSwitchError` immediately, never a silent
    misattribution of some OTHER switch's population as this one's.

    Both counts must be non-negative integers -- a negative or non-int
    count is malformed input, never silently coerced. `drained` is `True`
    iff BOTH are exactly zero; a caller may not report "drained" via any
    other channel (e.g. a bare bool with no underlying counts) so that a
    corrupted/fabricated drain signal can never masquerade as this type."""
    run_kind: str
    run_id: str
    old_tuple: V2SemanticTuple
    as_of: datetime
    non_terminal_episode_count: int
    active_cooldown_count: int

    def __post_init__(self) -> None:
        one_of(self.run_kind, "run_kind", RUN_KINDS, V2VersionSwitchError)
        nonblank(self.run_id, "run_id", V2VersionSwitchError)
        if not isinstance(self.old_tuple, V2SemanticTuple):
            raise V2VersionSwitchError(
                f"old_tuple must be a V2SemanticTuple, got {type(self.old_tuple).__name__}")
        _validate_decision_boundary(self.as_of)
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

# §3.1: "REPLAY: one replay execution_stream pins exactly one semantic
# tuple ... for its entire run" -- a REPLAY stream may NEVER be mid-switch.
_SWITCH_ELIGIBLE_RUN_KINDS = (LIVE,)


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
    stream that has ever activated a tuple. Setting `active` from `None`
    is `provision_initial_tuple()`'s job, a SEPARATE operation from
    OLD->NEW switching (see module docstring, finding 2).

    `pending`/`drain_complete_at`/`requested_at` are all `None` together
    (`PHASE_NO_PENDING_SWITCH`) or all meaningfully set together (during a
    switch) -- see `__post_init__` for the exact per-phase shape this
    enforces. `pending` is never equal to `active` (that would not be a
    switch at all -- see `evaluate_version_switch_transition`'s "same
    identity requested" no-op handling, which never persists such a
    state).

    A `run_kind == "REPLAY"` instance can NEVER legally hold `phase !=
    PHASE_NO_PENDING_SWITCH` (finding 1) -- `__post_init__` enforces this
    unconditionally, so no `REPLAY` state mid-switch can ever be
    constructed, by any caller, through any path.

    Likewise, `phase != PHASE_NO_PENDING_SWITCH` REQUIRES `active is not
    None` (amendment round 2, finding 1) -- a pending switch always means
    an OLD tuple exists (`state.active`) and NEW is `state.pending`;
    `active=None, pending=NEW, phase=DRAINING` (or `AWAITING_ACTIVATION_
    READINESS`) can never be constructed, by any caller, through any
    path -- including a reload of a persisted/malformed row."""
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

        if (self.run_kind not in _SWITCH_ELIGIBLE_RUN_KINDS
                and self.phase != PHASE_NO_PENDING_SWITCH):
            raise V2VersionSwitchError(
                f"run_kind {self.run_kind!r} must never hold phase {self.phase!r} -- §3.1's "
                "DRAIN-BEFORE-ACTIVATE switch machine is LIVE-only; one REPLAY "
                "execution_stream pins exactly one semantic tuple for its entire run "
                "and never enters DRAINING/AWAITING_ACTIVATION_READINESS")

        if self.phase != PHASE_NO_PENDING_SWITCH and self.active is None:
            raise V2VersionSwitchError(
                f"phase {self.phase!r} requires a non-None active tuple -- a pending H2b "
                "switch always means OLD exists (state.active) and NEW is state.pending; "
                "initial provisioning (active=None) is a SEPARATE operation "
                "(provision_initial_tuple()) and can never itself hold a pending-switch "
                "phase (tech-lead amendment round 2, finding 1)")

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

        # DRAINING or AWAITING_ACTIVATION_READINESS: a switch is in progress
        # (LIVE only -- REPLAY already rejected above).
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
    itself a switch. Legal for both `LIVE` and `REPLAY`. Use
    `provision_initial_tuple()` to set this stream's first tuple; use
    `evaluate_version_switch_transition()` (LIVE-only) only once `active`
    is already set."""
    return V2VersionSwitchState(
        run_kind=run_kind, run_id=run_id, active=None, pending=None,
        phase=PHASE_NO_PENDING_SWITCH, drain_complete_at=None, requested_at=None)


ACTION_NO_OP = "NO_OP"
ACTION_DRAIN_CONTINUES = "DRAIN_CONTINUES"
ACTION_DRAIN_COMPLETE = "DRAIN_COMPLETE"
ACTION_AWAITING_READINESS = "AWAITING_READINESS"
ACTION_ACTIVATED = "ACTIVATED"
ACTION_INITIAL_PROVISION_AWAITING_READINESS = "INITIAL_PROVISION_AWAITING_READINESS"
ACTION_INITIAL_ACTIVATED = "INITIAL_ACTIVATED"
SWITCH_ACTIONS = (
    ACTION_NO_OP, ACTION_DRAIN_CONTINUES, ACTION_DRAIN_COMPLETE,
    ACTION_AWAITING_READINESS, ACTION_ACTIVATED,
    ACTION_INITIAL_PROVISION_AWAITING_READINESS, ACTION_INITIAL_ACTIVATED,
)


@dataclass(frozen=True)
class V2VersionSwitchTransitionResult:
    """The outcome of evaluating one legal 5m decision boundary against a
    persisted `V2VersionSwitchState` -- returned by BOTH
    `evaluate_version_switch_transition()` (OLD->NEW switching) and
    `provision_initial_tuple()` (initial provisioning): the NEW state a
    caller MUST durably persist (atomically, before acting on it further --
    this module has no opinion on HOW; see `version_switch_orchestrator.py`),
    which `action` occurred, and whether THIS call's request started a
    genuinely new pending switch or genuinely activated a fresh tuple
    (`request_accepted`) -- `False` for a no-request call, an idempotent
    same-identity/duplicate-pending request, or (implicitly, via a raised
    `V2VersionSwitchError`) a refused conflicting request."""
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


def provision_initial_tuple(
    state: V2VersionSwitchState,
    *,
    decision_boundary: datetime,
    tuple_: V2SemanticTuple,
    candidate_ready: bool,
) -> V2VersionSwitchTransitionResult:
    """Set an `execution_stream`'s FIRST-EVER active tuple -- a SEPARATE
    operation from `evaluate_version_switch_transition()`'s OLD->NEW
    switching (module docstring, finding 2). Legal for both `LIVE` and
    `REPLAY` (every stream needs its one tuple provisioned exactly once).

    Requires `state.active is None` and `state.pending is None` (phase
    `PHASE_NO_PENDING_SWITCH`) -- raises `V2VersionSwitchError` otherwise,
    directing the caller to `evaluate_version_switch_transition()` instead
    (this stream already has an active tuple; provisioning is not the
    right operation).

    No drain concept applies here -- there is no OLD tuple to protect
    against mixing with. `candidate_ready` (§3.3 activation readiness,
    REQUIRED, never optional/defaulted -- fail-closed) gates activation
    directly: if `True`, `tuple_` becomes `active` immediately, AT
    `decision_boundary` itself (no `+5m` delay -- there is no same-
    boundary OLD/NEW provenance ambiguity to avoid, since there is no
    OLD). If `False`, the state is returned UNCHANGED (`active` stays
    `None`) -- no persisted "pending" bookkeeping is introduced; the
    caller simply calls this function again at a later boundary."""
    if not isinstance(state, V2VersionSwitchState):
        raise V2VersionSwitchError(
            f"state must be a V2VersionSwitchState, got {type(state).__name__}")
    T = _validate_decision_boundary(decision_boundary)
    if not isinstance(tuple_, V2SemanticTuple):
        raise V2VersionSwitchError(
            f"tuple_ must be a V2SemanticTuple, got {type(tuple_).__name__}")
    if not isinstance(candidate_ready, bool):
        raise V2VersionSwitchError(
            f"candidate_ready must be a bool, got {type(candidate_ready).__name__}")
    if state.phase != PHASE_NO_PENDING_SWITCH or state.active is not None or state.pending is not None:
        raise V2VersionSwitchError(
            "provision_initial_tuple() requires an execution_stream with no active tuple and "
            f"no pending switch yet (got active={state.active!r}, pending={state.pending!r}, "
            f"phase={state.phase!r}) -- this stream already has an identity; use "
            "evaluate_version_switch_transition() to switch it instead")

    if not candidate_ready:
        return V2VersionSwitchTransitionResult(
            state=state, action=ACTION_INITIAL_PROVISION_AWAITING_READINESS,
            request_accepted=False)

    activated = V2VersionSwitchState(
        run_kind=state.run_kind, run_id=state.run_id, active=tuple_, pending=None,
        phase=PHASE_NO_PENDING_SWITCH, drain_complete_at=None, requested_at=None)
    return V2VersionSwitchTransitionResult(
        state=activated, action=ACTION_INITIAL_ACTIVATED, request_accepted=True)


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

    `LIVE`-only: raises `V2VersionSwitchError` immediately if `state.
    run_kind != "LIVE"` and a NEW switch would be initiated (finding 1).
    Requires `state.active` to already be set -- a request against a
    never-activated stream (`state.active is None`) raises, directing the
    caller to `provision_initial_tuple()` instead (finding 2).

    `requested`: a caller-supplied target tuple IF an operator/runtime is
    requesting a switch to it at this boundary; `None` if no request is
    being made this call (the normal case -- most boundaries do not carry a
    request; this function still must be called for them to advance any
    ALREADY-pending drain).

    `drain_fact`: OLD's population as of `T`, REQUIRED whenever this
    evaluation could depend on it (`state.phase == PHASE_DRAINING`, or a
    genuinely new request is being made from `PHASE_NO_PENDING_SWITCH`) --
    omitting it in that case is a caller bug, not a legitimate "assume
    drained", and raises `V2VersionSwitchError`. Its `run_kind`/`run_id`/
    `old_tuple`/`as_of` MUST match this switch's own scope/OLD tuple/`T`
    exactly (finding 3) -- a mismatch raises before `.drained` is ever
    consulted.

    `candidate_ready`: NEW's §3.3 activation-readiness verdict as of `T`,
    REQUIRED only once drain is already known complete
    (`PHASE_AWAITING_ACTIVATION_READINESS`) AND `T` is strictly later than
    `state.drain_complete_at` -- omitting it in that case is likewise a
    caller bug, never a silent "assume not ready" or "assume ready".

    Whenever a switch is pending (`DRAINING`/`AWAITING_ACTIVATION_
    READINESS`), `T` earlier than `state.requested_at` raises immediately
    (finding 5) -- decision boundaries must be evaluated in non-decreasing
    order relative to when the switch was requested.

    Raises `V2VersionSwitchError` for: a non-legal `decision_boundary`; a
    wrong-typed `requested`/`drain_fact`/`candidate_ready`; a conflicting
    switch request while one is already pending for a DIFFERENT target; a
    scope-mismatched `drain_fact`; an out-of-order `decision_boundary`; a
    switch attempted on `REPLAY`; a request against a never-activated
    stream; or a missing required fact for the current phase. Never raises
    merely because OLD is legitimately not yet drained or NEW is
    legitimately not yet ready -- those produce `ACTION_DRAIN_CONTINUES`/
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

    # (finding 5) Whenever a switch is already pending, T must never be
    # earlier than the boundary that requested it -- checked BEFORE any
    # phase-specific logic, covering DRAINING (not just AWAITING_...).
    if working.phase != PHASE_NO_PENDING_SWITCH and T < working.requested_at:
        raise V2VersionSwitchError(
            f"decision_boundary {T.isoformat()} is EARLIER than this switch's own "
            f"requested_at {working.requested_at.isoformat()} -- decision boundaries must be "
            "evaluated in non-decreasing order; this is a caller ordering bug, never silently "
            "accepted")

    # ---- step 1: handle an incoming request, if any -------------------------
    if requested is not None:
        if working.phase == PHASE_NO_PENDING_SWITCH:
            if working.active is None:
                raise V2VersionSwitchError(
                    "cannot request a switch on an execution_stream with no active tuple yet "
                    f"(run_kind={working.run_kind!r}, run_id={working.run_id!r}) -- use "
                    "provision_initial_tuple() to set this stream's first tuple; initial "
                    "provisioning is a separate operation from OLD->NEW switching")
            if working.active == requested:
                pass  # vector 2: same identity requested -> idempotent no-op.
            else:
                if working.run_kind not in _SWITCH_ELIGIBLE_RUN_KINDS:
                    raise V2VersionSwitchError(
                        f"run_kind {working.run_kind!r} execution_stream "
                        f"(run_id={working.run_id!r}) cannot be switched -- §3.1's "
                        "DRAIN-BEFORE-ACTIVATE switch machine is LIVE-only; one REPLAY "
                        "execution_stream pins exactly one semantic tuple for its entire run "
                        "(a version change requires a new, separately-identified replay run)")
                working = V2VersionSwitchState(
                    run_kind=working.run_kind, run_id=working.run_id,
                    active=working.active, pending=requested,
                    phase=PHASE_DRAINING, drain_complete_at=None, requested_at=T)
                request_accepted = True
        else:
            # A switch is already pending (DRAINING or
            # AWAITING_ACTIVATION_READINESS) -- always LIVE here, by
            # construction (V2VersionSwitchState.__post_init__ forbids a
            # REPLAY instance in either phase).
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
        _assert_drain_fact_scope_matches(drain_fact, working, T)
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
    if T == working.drain_complete_at:
        # The boundary that observed drain completion is entirely OLD's own
        # provenance boundary (§3.1) -- NEW never activates here, even if
        # this is somehow re-evaluated. No fact is needed to know this.
        return V2VersionSwitchTransitionResult(
            state=working, action=ACTION_AWAITING_READINESS, request_accepted=request_accepted)
    if T < working.drain_complete_at:
        raise V2VersionSwitchError(
            f"decision_boundary {T.isoformat()} is EARLIER than the already-persisted "
            f"drain_complete_at {working.drain_complete_at.isoformat()} -- decision "
            "boundaries must be evaluated in non-decreasing order; this is a caller "
            "ordering bug, never silently accepted")
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


def _assert_drain_fact_scope_matches(
    drain_fact: V2DrainFact, state: V2VersionSwitchState, decision_boundary: datetime,
) -> None:
    """(finding 3) Reject any `V2DrainFact` whose self-reported scope does
    not EXACTLY match the switch it is being consulted for -- BEFORE its
    `.drained` verdict is ever trusted. A mismatch on any one of
    `run_kind`/`run_id`/`old_tuple`/`as_of` means this fact describes a
    DIFFERENT execution_stream, a DIFFERENT OLD tuple, or a DIFFERENT
    boundary than the one currently being evaluated -- consuming it as if
    it were this switch's own drain status would be exactly the kind of
    misattribution this check exists to make impossible."""
    if drain_fact.run_kind != state.run_kind or drain_fact.run_id != state.run_id:
        raise V2VersionSwitchError(
            f"drain_fact execution_stream (run_kind={drain_fact.run_kind!r}, "
            f"run_id={drain_fact.run_id!r}) does not match the switch being evaluated "
            f"(run_kind={state.run_kind!r}, run_id={state.run_id!r}) -- refusing to "
            "consume a drain fact computed for a different execution_stream")
    if drain_fact.old_tuple != state.active:
        raise V2VersionSwitchError(
            f"drain_fact.old_tuple {drain_fact.old_tuple!r} does not match the OLD tuple "
            f"actually being drained {state.active!r} -- refusing to consume a drain fact "
            "computed for a different semantic tuple")
    if drain_fact.as_of != decision_boundary:
        raise V2VersionSwitchError(
            f"drain_fact.as_of {drain_fact.as_of.isoformat()} does not match the "
            f"decision_boundary being evaluated {decision_boundary.isoformat()} -- refusing "
            "to consume a drain fact computed for a different boundary")


def active_for_new_creation(state: V2VersionSwitchState) -> Optional[V2SemanticTuple]:
    """(finding 4) The single, explicit, fail-closed answer to "which
    semantic tuple, if any, may create a NEW episode in this
    execution_stream right now": `state.active` when steady
    (`PHASE_NO_PENDING_SWITCH` -- this also correctly covers `REPLAY`,
    which is always steady by construction per finding 1, and covers a
    never-yet-provisioned stream, which correctly yields `None`), or
    `None` throughout `DRAINING`/`AWAITING_ACTIVATION_READINESS` (§3.1:
    zero tuples are active for new-episode creation during an active
    drain -- never OLD, never NEW, never both)."""
    if not isinstance(state, V2VersionSwitchState):
        raise V2VersionSwitchError(
            f"state must be a V2VersionSwitchState, got {type(state).__name__}")
    if state.phase == PHASE_NO_PENDING_SWITCH:
        return state.active
    return None


def assert_provenance_authorized_for_new_creation(
    provenance: V2DecisionProvenance, state: V2VersionSwitchState,
) -> None:
    """(finding 4) The guard a future Stage 6 new-episode-creation boundary
    MUST call before persisting a new `V2EpisodeEvent`: verifies the
    resolved `V2DecisionProvenance` (`decision_provenance.py`, already-
    merged H2a, untouched by this module) is actually AUTHORIZED to create
    a new episode under `state`'s current switch status.

    Two independent checks, both required:
      1. `execution_stream` scope agreement -- `provenance.run_kind`/
         `provenance.run_id` must equal `state.run_kind`/`state.run_id`.
         A provenance resolved for one execution_stream can never
         authorize new-episode creation in another.
      2. `provenance`'s own `(rules_version, calculation_version,
         decision_code_version)` must equal `active_for_new_creation(
         state)` -- which is `None` throughout an active drain. This is
         the critical, explicit rejection: a provenance whose tuple
         happens to equal the OLD tuple currently being drained is NOT
         authorized to create a new episode while that drain is in
         progress -- `active_for_new_creation` being non-`None` is the
         ONLY thing that authorizes creation, never a bare tuple-value
         match against OLD by itself.

    Raises `V2VersionSwitchError` on either failure; raises for a
    wrong-typed argument too. Never mutates or re-derives `provenance` or
    `state` -- read-only composition, exactly like H2a's own `V2DecisionView`
    coherence checks."""
    if not isinstance(provenance, V2DecisionProvenance):
        raise V2VersionSwitchError(
            f"provenance must be a V2DecisionProvenance, got {type(provenance).__name__}")
    if not isinstance(state, V2VersionSwitchState):
        raise V2VersionSwitchError(
            f"state must be a V2VersionSwitchState, got {type(state).__name__}")
    if provenance.run_kind != state.run_kind or provenance.run_id != state.run_id:
        raise V2VersionSwitchError(
            f"provenance execution_stream (run_kind={provenance.run_kind!r}, "
            f"run_id={provenance.run_id!r}) does not match the switch state's own "
            f"execution_stream (run_kind={state.run_kind!r}, run_id={state.run_id!r}) -- "
            "refusing to authorize new-episode creation under a mismatched scope")

    active = active_for_new_creation(state)
    if active is None:
        raise V2VersionSwitchError(
            f"no semantic tuple is active for new-episode creation right now "
            f"(execution_stream run_kind={state.run_kind!r}, run_id={state.run_id!r}, "
            f"phase={state.phase!r}) -- refusing to authorize new-episode creation, even "
            "though the supplied provenance's own tuple may equal the OLD tuple currently "
            "being drained; a provenance match against OLD is never sufficient by itself "
            "during an active drain")

    provenance_tuple = (
        provenance.rules_version, provenance.calculation_version, provenance.decision_code_version)
    active_tuple = (active.rules_version, active.calculation_version, active.decision_code_version)
    if provenance_tuple != active_tuple:
        raise V2VersionSwitchError(
            "provenance (rules_version, calculation_version, decision_code_version) "
            f"{provenance_tuple!r} does not match the switch-resolved active-for-new-creation "
            f"tuple {active_tuple!r} -- refusing to authorize new-episode creation under the "
            "wrong version identity")
