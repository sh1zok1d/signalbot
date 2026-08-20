"""V2-H2b: DRAIN-BEFORE-ACTIVATE version-switch state machine tests
(`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §3.1).

Pure unit tests against `analytics/forecasting_v2/version_switch.py` only --
no DB, no async. Covers all 14 required contract vectors from the V2-H2b
task, PLUS tech-lead amendment round 1's five findings:

  1. LIVE-only switch machine (REPLAY never DRAINING/AWAITING/switches).
  2. Initial tuple provisioning is a separate, non-delayed operation from
     OLD->NEW switching.
  3. V2DrainFact is self-scoped and its scope is verified before trusting
     `.drained`.
  4. `active_for_new_creation`/`assert_provenance_authorized_for_new_
     creation` fail-closed surface, including the "matches OLD but still
     rejected during drain" case.
  5. decision_boundary < requested_at is rejected while ANY switch phase
     is pending (not just AWAITING_ACTIVATION_READINESS).

(Some vectors that require real storage/concurrency are instead covered by
`tests/storage/test_v2_version_switch_readers.py`, and vector 10 [reader/
readiness corruption fails closed] plus the readiness-gating half of
vector 3/4/5 are covered by
`tests/analytics/test_forecasting_v2_version_switch_orchestrator.py`)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from analytics.forecasting_v2.decision_provenance import V2DecisionProvenance
from analytics.forecasting_v2.version_switch import (
    ACTION_ACTIVATED, ACTION_AWAITING_READINESS, ACTION_DRAIN_COMPLETE,
    ACTION_DRAIN_CONTINUES, ACTION_INITIAL_ACTIVATED,
    ACTION_INITIAL_PROVISION_AWAITING_READINESS, ACTION_NO_OP,
    PHASE_AWAITING_ACTIVATION_READINESS, PHASE_DRAINING, PHASE_NO_PENDING_SWITCH,
    V2DrainFact, V2SemanticTuple, V2VersionSwitchError, V2VersionSwitchState,
    active_for_new_creation, assert_provenance_authorized_for_new_creation,
    evaluate_version_switch_transition, initial_switch_state, provision_initial_tuple,
)

UTC = timezone.utc
T0 = datetime(2026, 8, 20, 0, 0, tzinfo=UTC)


def _t(n: int) -> datetime:
    """The n-th legal 5m decision boundary after T0 (n=0 -> T0 itself)."""
    return T0 + timedelta(minutes=5 * n)


OLD = V2SemanticTuple(
    rules_version="v2-rules-v0.1.0", calculation_version="a" * 16,
    decision_code_version="decision-code-1")
NEW = V2SemanticTuple(
    rules_version="v2-rules-v0.2.0", calculation_version="b" * 16,
    decision_code_version="decision-code-2")
OTHER = V2SemanticTuple(
    rules_version="v2-rules-v0.3.0", calculation_version="c" * 16,
    decision_code_version="decision-code-3")

RUN_KIND = "LIVE"
RUN_ID = "v2-shadow-live"


def _drain(*, non_terminal=0, cooldown=0, run_kind=RUN_KIND, run_id=RUN_ID,
           old_tuple=OLD, as_of=None) -> V2DrainFact:
    return V2DrainFact(
        run_kind=run_kind, run_id=run_id, old_tuple=old_tuple,
        as_of=as_of if as_of is not None else T0,
        non_terminal_episode_count=non_terminal, active_cooldown_count=cooldown)


DRAINED = lambda as_of=None, old_tuple=OLD: _drain(as_of=as_of, old_tuple=old_tuple)  # noqa: E731
NOT_DRAINED_EPISODE = lambda as_of=None, old_tuple=OLD: _drain(  # noqa: E731
    non_terminal=1, as_of=as_of, old_tuple=old_tuple)
NOT_DRAINED_COOLDOWN = lambda as_of=None, old_tuple=OLD: _drain(  # noqa: E731
    cooldown=1, as_of=as_of, old_tuple=old_tuple)


def _steady_state(active=OLD, run_kind=RUN_KIND, run_id=RUN_ID) -> V2VersionSwitchState:
    return V2VersionSwitchState(
        run_kind=run_kind, run_id=run_id, active=active, pending=None,
        phase=PHASE_NO_PENDING_SWITCH, drain_complete_at=None, requested_at=None)


# ---- V2SemanticTuple field validation ----------------------------------------

def test_semantic_tuple_rejects_malformed_rules_version():
    with pytest.raises(V2VersionSwitchError):
        V2SemanticTuple(rules_version="v1-rules-0.1.0", calculation_version="a" * 16,
                         decision_code_version="x")


def test_semantic_tuple_rejects_malformed_calculation_version():
    with pytest.raises(V2VersionSwitchError):
        V2SemanticTuple(rules_version="v2-rules-v0.1.0", calculation_version="not-hex",
                         decision_code_version="x")


def test_semantic_tuple_rejects_blank_decision_code_version():
    with pytest.raises(V2VersionSwitchError):
        V2SemanticTuple(rules_version="v2-rules-v0.1.0", calculation_version="a" * 16,
                         decision_code_version="  ")


# ---- V2DrainFact: self-scoped (finding 3) ------------------------------------

def test_drain_fact_requires_valid_scope_fields():
    with pytest.raises(V2VersionSwitchError):
        V2DrainFact(run_kind="BOGUS", run_id=RUN_ID, old_tuple=OLD, as_of=T0,
                    non_terminal_episode_count=0, active_cooldown_count=0)
    with pytest.raises(V2VersionSwitchError):
        V2DrainFact(run_kind=RUN_KIND, run_id="  ", old_tuple=OLD, as_of=T0,
                    non_terminal_episode_count=0, active_cooldown_count=0)
    with pytest.raises(V2VersionSwitchError):
        V2DrainFact(run_kind=RUN_KIND, run_id=RUN_ID, old_tuple="not-a-tuple", as_of=T0,
                    non_terminal_episode_count=0, active_cooldown_count=0)
    with pytest.raises(V2VersionSwitchError):
        V2DrainFact(run_kind=RUN_KIND, run_id=RUN_ID, old_tuple=OLD,
                    as_of=T0 + timedelta(minutes=1),  # not 5m-aligned
                    non_terminal_episode_count=0, active_cooldown_count=0)


def test_drain_fact_rejects_negative_counts():
    with pytest.raises(V2VersionSwitchError):
        _drain(non_terminal=-1)
    with pytest.raises(V2VersionSwitchError):
        _drain(cooldown=-1)


def test_drain_fact_rejects_non_int_counts():
    with pytest.raises(V2VersionSwitchError):
        V2DrainFact(run_kind=RUN_KIND, run_id=RUN_ID, old_tuple=OLD, as_of=T0,
                    non_terminal_episode_count=1.5, active_cooldown_count=0)
    with pytest.raises(V2VersionSwitchError):
        V2DrainFact(run_kind=RUN_KIND, run_id=RUN_ID, old_tuple=OLD, as_of=T0,
                    non_terminal_episode_count=True, active_cooldown_count=0)


def test_drain_fact_drained_property():
    assert DRAINED(as_of=_t(0)).drained is True
    assert NOT_DRAINED_EPISODE(as_of=_t(0)).drained is False
    assert NOT_DRAINED_COOLDOWN(as_of=_t(0)).drained is False


def test_evaluate_rejects_drain_fact_with_wrong_execution_stream():
    state = _steady_state()
    r1 = evaluate_version_switch_transition(
        state, decision_boundary=_t(0), requested=NEW,
        drain_fact=NOT_DRAINED_EPISODE(as_of=_t(0)))
    assert r1.action == ACTION_DRAIN_CONTINUES
    wrong_scope = _drain(non_terminal=0, as_of=_t(1), run_id="some-other-stream")
    with pytest.raises(V2VersionSwitchError, match="execution_stream"):
        evaluate_version_switch_transition(
            r1.state, decision_boundary=_t(1), drain_fact=wrong_scope)


def test_evaluate_rejects_drain_fact_with_wrong_old_tuple():
    state = _steady_state()
    r1 = evaluate_version_switch_transition(
        state, decision_boundary=_t(0), requested=NEW,
        drain_fact=NOT_DRAINED_EPISODE(as_of=_t(0)))
    wrong_old = _drain(non_terminal=0, as_of=_t(1), old_tuple=OTHER)
    with pytest.raises(V2VersionSwitchError, match="old_tuple"):
        evaluate_version_switch_transition(
            r1.state, decision_boundary=_t(1), drain_fact=wrong_old)


def test_evaluate_rejects_drain_fact_with_wrong_as_of():
    state = _steady_state()
    r1 = evaluate_version_switch_transition(
        state, decision_boundary=_t(0), requested=NEW,
        drain_fact=NOT_DRAINED_EPISODE(as_of=_t(0)))
    wrong_as_of = _drain(non_terminal=0, as_of=_t(2))  # evaluating at _t(1), fact says _t(2)
    with pytest.raises(V2VersionSwitchError, match="as_of"):
        evaluate_version_switch_transition(
            r1.state, decision_boundary=_t(1), drain_fact=wrong_as_of)


def test_evaluate_accepts_correctly_scoped_drain_fact():
    state = _steady_state()
    r1 = evaluate_version_switch_transition(
        state, decision_boundary=_t(0), requested=NEW,
        drain_fact=NOT_DRAINED_EPISODE(as_of=_t(0)))
    r2 = evaluate_version_switch_transition(
        r1.state, decision_boundary=_t(1), drain_fact=DRAINED(as_of=_t(1)))
    assert r2.action == ACTION_DRAIN_COMPLETE


# ---- V2VersionSwitchState self-validation ------------------------------------

def test_initial_switch_state_is_no_pending_switch():
    s = initial_switch_state(run_kind="LIVE", run_id=RUN_ID)
    assert s.phase == PHASE_NO_PENDING_SWITCH
    assert s.active is None
    assert s.pending is None


def test_state_rejects_pending_without_requested_at():
    with pytest.raises(V2VersionSwitchError):
        V2VersionSwitchState(
            run_kind="LIVE", run_id="x", active=OLD, pending=NEW,
            phase=PHASE_DRAINING, drain_complete_at=None, requested_at=None)


def test_state_rejects_no_pending_switch_with_pending_set():
    with pytest.raises(V2VersionSwitchError):
        V2VersionSwitchState(
            run_kind="LIVE", run_id="x", active=OLD, pending=NEW,
            phase=PHASE_NO_PENDING_SWITCH, drain_complete_at=None, requested_at=_t(0))


def test_state_rejects_pending_equal_to_active():
    with pytest.raises(V2VersionSwitchError):
        V2VersionSwitchState(
            run_kind="LIVE", run_id="x", active=OLD, pending=OLD,
            phase=PHASE_DRAINING, drain_complete_at=None, requested_at=_t(0))


def test_state_rejects_draining_with_drain_complete_at_set():
    with pytest.raises(V2VersionSwitchError):
        V2VersionSwitchState(
            run_kind="LIVE", run_id="x", active=OLD, pending=NEW,
            phase=PHASE_DRAINING, drain_complete_at=_t(0), requested_at=_t(0))


def test_state_rejects_awaiting_readiness_without_drain_complete_at():
    with pytest.raises(V2VersionSwitchError):
        V2VersionSwitchState(
            run_kind="LIVE", run_id="x", active=OLD, pending=NEW,
            phase=PHASE_AWAITING_ACTIVATION_READINESS, drain_complete_at=None,
            requested_at=_t(0))


def test_state_rejects_drain_complete_before_requested_at():
    with pytest.raises(V2VersionSwitchError):
        V2VersionSwitchState(
            run_kind="LIVE", run_id="x", active=OLD, pending=NEW,
            phase=PHASE_AWAITING_ACTIVATION_READINESS,
            drain_complete_at=_t(0), requested_at=_t(1))


def test_state_rejects_bad_run_kind():
    with pytest.raises(V2VersionSwitchError):
        V2VersionSwitchState(
            run_kind="BOGUS", run_id="x", active=None, pending=None,
            phase=PHASE_NO_PENDING_SWITCH, drain_complete_at=None, requested_at=None)


# ---- finding 1: REPLAY is switch-ineligible by construction ------------------

def test_replay_state_cannot_be_constructed_in_draining_phase():
    with pytest.raises(V2VersionSwitchError, match="LIVE-only|DRAIN-BEFORE-ACTIVATE"):
        V2VersionSwitchState(
            run_kind="REPLAY", run_id="replay-2026-08-20-001", active=OLD, pending=NEW,
            phase=PHASE_DRAINING, drain_complete_at=None, requested_at=_t(0))


def test_replay_state_cannot_be_constructed_in_awaiting_readiness_phase():
    with pytest.raises(V2VersionSwitchError, match="LIVE-only|DRAIN-BEFORE-ACTIVATE"):
        V2VersionSwitchState(
            run_kind="REPLAY", run_id="replay-2026-08-20-001", active=OLD, pending=NEW,
            phase=PHASE_AWAITING_ACTIVATION_READINESS, drain_complete_at=_t(0),
            requested_at=_t(0))


def test_replay_state_no_pending_switch_is_fine():
    s = V2VersionSwitchState(
        run_kind="REPLAY", run_id="replay-2026-08-20-001", active=OLD, pending=None,
        phase=PHASE_NO_PENDING_SWITCH, drain_complete_at=None, requested_at=None)
    assert s.active == OLD


def test_replay_switch_request_is_refused_via_evaluate_version_switch_transition():
    state = _steady_state(run_kind="REPLAY", run_id="replay-2026-08-20-001")
    with pytest.raises(V2VersionSwitchError, match="LIVE-only|REPLAY"):
        evaluate_version_switch_transition(state, decision_boundary=_t(0), requested=NEW)


def test_replay_same_identity_requested_is_still_a_harmless_no_op():
    """Requesting REPLAY's OWN already-active tuple is not a switch at all
    -- must stay a no-op, never raise."""
    state = _steady_state(run_kind="REPLAY", run_id="replay-2026-08-20-001")
    result = evaluate_version_switch_transition(state, decision_boundary=_t(0), requested=OLD)
    assert result.action == ACTION_NO_OP
    assert result.state.active == OLD


# ---- finding 2: initial provisioning is separate from switching -------------

def test_provision_initial_tuple_activates_immediately_when_ready_no_delay():
    state = initial_switch_state(run_kind="LIVE", run_id=RUN_ID)
    result = provision_initial_tuple(
        state, decision_boundary=_t(0), tuple_=OLD, candidate_ready=True)
    assert result.action == ACTION_INITIAL_ACTIVATED
    assert result.request_accepted is True
    assert result.state.active == OLD
    assert result.state.phase == PHASE_NO_PENDING_SWITCH
    # No drain/delay bookkeeping introduced anywhere.
    assert result.state.pending is None
    assert result.state.drain_complete_at is None
    assert result.state.requested_at is None


def test_provision_initial_tuple_stays_none_when_not_ready_no_persisted_pending():
    state = initial_switch_state(run_kind="LIVE", run_id=RUN_ID)
    result = provision_initial_tuple(
        state, decision_boundary=_t(0), tuple_=OLD, candidate_ready=False)
    assert result.action == ACTION_INITIAL_PROVISION_AWAITING_READINESS
    assert result.request_accepted is False
    assert result.state.active is None
    assert result.state == state  # entirely unchanged -- no intermediate state persisted.


def test_provision_initial_tuple_retried_until_ready_activates_same_boundary_it_becomes_ready():
    state = initial_switch_state(run_kind="LIVE", run_id=RUN_ID)
    r1 = provision_initial_tuple(state, decision_boundary=_t(0), tuple_=OLD, candidate_ready=False)
    assert r1.state.active is None
    r2 = provision_initial_tuple(r1.state, decision_boundary=_t(1), tuple_=OLD, candidate_ready=True)
    assert r2.action == ACTION_INITIAL_ACTIVATED
    assert r2.state.active == OLD  # activates at T=_t(1) itself -- no extra delay.


def test_provision_initial_tuple_works_for_replay_too():
    state = initial_switch_state(run_kind="REPLAY", run_id="replay-2026-08-20-001")
    result = provision_initial_tuple(
        state, decision_boundary=_t(0), tuple_=OLD, candidate_ready=True)
    assert result.action == ACTION_INITIAL_ACTIVATED
    assert result.state.active == OLD


def test_provision_initial_tuple_rejects_stream_that_already_has_active_tuple():
    state = _steady_state()
    with pytest.raises(V2VersionSwitchError, match="already has an identity"):
        provision_initial_tuple(state, decision_boundary=_t(0), tuple_=NEW, candidate_ready=True)


def test_provision_initial_tuple_rejects_stream_with_pending_switch():
    state = V2VersionSwitchState(
        run_kind="LIVE", run_id=RUN_ID, active=OLD, pending=NEW,
        phase=PHASE_DRAINING, drain_complete_at=None, requested_at=_t(0))
    with pytest.raises(V2VersionSwitchError):
        provision_initial_tuple(state, decision_boundary=_t(1), tuple_=OTHER, candidate_ready=True)


def test_evaluate_version_switch_transition_rejects_request_on_never_provisioned_stream():
    """A switch request against active=None must be refused -- the caller
    must use provision_initial_tuple() instead (finding 2)."""
    state = initial_switch_state(run_kind="LIVE", run_id=RUN_ID)
    with pytest.raises(V2VersionSwitchError, match="provision_initial_tuple"):
        evaluate_version_switch_transition(state, decision_boundary=_t(0), requested=OLD)


def test_evaluate_version_switch_transition_with_no_request_on_never_provisioned_stream_is_no_op():
    state = initial_switch_state(run_kind="LIVE", run_id=RUN_ID)
    result = evaluate_version_switch_transition(state, decision_boundary=_t(0))
    assert result.action == ACTION_NO_OP
    assert result.state.active is None


# ---- vector 1: no switch requested -> current ACTIVE remains active ---------

def test_vector1_no_switch_requested_stays_active():
    state = _steady_state()
    result = evaluate_version_switch_transition(state, decision_boundary=_t(0))
    assert result.action == ACTION_NO_OP
    assert result.request_accepted is False
    assert result.state.active == OLD
    assert result.state.phase == PHASE_NO_PENDING_SWITCH


# ---- vector 2: same identity requested -> idempotent no-op ------------------

def test_vector2_same_identity_requested_is_idempotent_no_op():
    state = _steady_state()
    result = evaluate_version_switch_transition(
        state, decision_boundary=_t(0), requested=OLD)
    assert result.action == ACTION_NO_OP
    assert result.request_accepted is False
    assert result.state == state


# ---- vector 3: new target requested but NOT_READY -> cannot activate --------

def test_vector3_target_ready_flag_false_blocks_activation_after_drain():
    # OLD already drained at request time -> drain completes THIS boundary,
    # but activation still requires a strictly later boundary; at that later
    # boundary, candidate_ready=False must keep it pending.
    state = _steady_state()
    r1 = evaluate_version_switch_transition(
        state, decision_boundary=_t(0), requested=NEW, drain_fact=DRAINED(as_of=_t(0)))
    assert r1.action == ACTION_DRAIN_COMPLETE
    assert r1.state.phase == PHASE_AWAITING_ACTIVATION_READINESS
    assert r1.state.drain_complete_at == _t(0)

    r2 = evaluate_version_switch_transition(
        r1.state, decision_boundary=_t(1), candidate_ready=False)
    assert r2.action == ACTION_AWAITING_READINESS
    assert r2.state.active == OLD
    assert r2.state.pending == NEW


# ---- vector 4: target ready but current NOT_DRAINED -> cannot activate -----

def test_vector4_ready_candidate_blocked_while_old_not_drained():
    state = _steady_state()
    r1 = evaluate_version_switch_transition(
        state, decision_boundary=_t(0), requested=NEW,
        drain_fact=NOT_DRAINED_EPISODE(as_of=_t(0)))
    assert r1.action == ACTION_DRAIN_CONTINUES
    assert r1.state.phase == PHASE_DRAINING
    assert r1.state.active == OLD

    # Even supplying candidate_ready=True has no effect while still DRAINING
    # -- drain gates unconditionally first; the pure function does not even
    # consult candidate_ready in this phase.
    r2 = evaluate_version_switch_transition(
        r1.state, decision_boundary=_t(1), drain_fact=NOT_DRAINED_COOLDOWN(as_of=_t(1)))
    assert r2.action == ACTION_DRAIN_CONTINUES
    assert r2.state.active == OLD


# ---- vector 5: target ready AND current drained -> exactly one activation --

def test_vector5_ready_and_drained_activates_exactly_once():
    state = _steady_state()
    r1 = evaluate_version_switch_transition(
        state, decision_boundary=_t(0), requested=NEW,
        drain_fact=NOT_DRAINED_EPISODE(as_of=_t(0)))
    assert r1.action == ACTION_DRAIN_CONTINUES

    r2 = evaluate_version_switch_transition(
        r1.state, decision_boundary=_t(1), drain_fact=DRAINED(as_of=_t(1)))
    assert r2.action == ACTION_DRAIN_COMPLETE
    assert r2.state.drain_complete_at == _t(1)
    assert r2.state.active == OLD  # NOT activated at the drain-complete boundary itself.

    r3 = evaluate_version_switch_transition(
        r2.state, decision_boundary=_t(2), candidate_ready=True)
    assert r3.action == ACTION_ACTIVATED
    assert r3.state.active == NEW
    assert r3.state.pending is None
    assert r3.state.phase == PHASE_NO_PENDING_SWITCH

    # A further call with no request is a stable no-op on the new identity.
    r4 = evaluate_version_switch_transition(r3.state, decision_boundary=_t(3))
    assert r4.action == ACTION_NO_OP
    assert r4.state.active == NEW


def test_vector_c_already_drained_at_request_still_delays_activation_one_boundary():
    """§3.1 worked vector C: OLD already fully drained at T_request ->
    drain_complete_at = T_request, but NEW never activates at T_request
    itself, only at T_request + 5m at the earliest. NOTE (finding 2): this
    is a GENUINE switch (OLD already active) -- distinct from a fresh
    stream's initial provisioning, which never goes through this delay at
    all (see provision_initial_tuple tests above)."""
    state = _steady_state()
    r1 = evaluate_version_switch_transition(
        state, decision_boundary=_t(5), requested=NEW, drain_fact=DRAINED(as_of=_t(5)))
    assert r1.action == ACTION_DRAIN_COMPLETE
    assert r1.request_accepted is True
    assert r1.state.drain_complete_at == _t(5)
    assert r1.state.active == OLD  # still OLD -- not activated at T_request.

    r2 = evaluate_version_switch_transition(
        r1.state, decision_boundary=_t(6), candidate_ready=True)
    assert r2.action == ACTION_ACTIVATED
    assert r2.state.active == NEW


# ---- vector 6: restart while draining -> persisted state resumes identically

def test_vector6_restart_while_draining_resumes_identically():
    state = _steady_state()
    r1 = evaluate_version_switch_transition(
        state, decision_boundary=_t(0), requested=NEW,
        drain_fact=NOT_DRAINED_EPISODE(as_of=_t(0)))
    persisted = r1.state  # simulates durable persistence before "restart".

    # "Restart": reload the exact same persisted state and continue -- the
    # pure function is deterministic, so this reproduces bit-for-bit.
    reloaded = V2VersionSwitchState(
        run_kind=persisted.run_kind, run_id=persisted.run_id, active=persisted.active,
        pending=persisted.pending, phase=persisted.phase,
        drain_complete_at=persisted.drain_complete_at, requested_at=persisted.requested_at)
    assert reloaded == persisted

    r2 = evaluate_version_switch_transition(
        reloaded, decision_boundary=_t(1), drain_fact=DRAINED(as_of=_t(1)))
    assert r2.action == ACTION_DRAIN_COMPLETE
    assert r2.state.pending == NEW  # never cancelled/reset by "restart".


# ---- vector 7: restart after activation -> new active remains authoritative -

def test_vector7_restart_after_activation_new_active_remains_authoritative():
    state = _steady_state()
    r1 = evaluate_version_switch_transition(
        state, decision_boundary=_t(0), requested=NEW, drain_fact=DRAINED(as_of=_t(0)))
    r2 = evaluate_version_switch_transition(
        r1.state, decision_boundary=_t(1), candidate_ready=True)
    assert r2.action == ACTION_ACTIVATED
    persisted = r2.state

    # "Restart": reload the same persisted (now-steady) state.
    reloaded = V2VersionSwitchState(
        run_kind=persisted.run_kind, run_id=persisted.run_id, active=persisted.active,
        pending=persisted.pending, phase=persisted.phase,
        drain_complete_at=persisted.drain_complete_at, requested_at=persisted.requested_at)
    r3 = evaluate_version_switch_transition(reloaded, decision_boundary=_t(2))
    assert r3.action == ACTION_NO_OP
    assert r3.state.active == NEW  # never silently reverted to OLD or config/"latest".


# ---- vector 8: duplicate identical request -> idempotent --------------------

def test_vector8_duplicate_identical_pending_request_is_idempotent():
    state = _steady_state()
    r1 = evaluate_version_switch_transition(
        state, decision_boundary=_t(0), requested=NEW,
        drain_fact=NOT_DRAINED_EPISODE(as_of=_t(0)))
    assert r1.request_accepted is True

    r2 = evaluate_version_switch_transition(
        r1.state, decision_boundary=_t(1), requested=NEW,
        drain_fact=NOT_DRAINED_EPISODE(as_of=_t(1)))
    assert r2.request_accepted is False  # NOT a new switch -- same pending target.
    assert r2.state.pending == NEW
    assert r2.state.requested_at == _t(0)  # unchanged -- not re-stamped.


# ---- vector 9: conflicting target request while pending -> refused ----------

def test_vector9_conflicting_target_while_pending_is_refused():
    state = _steady_state()
    r1 = evaluate_version_switch_transition(
        state, decision_boundary=_t(0), requested=NEW,
        drain_fact=NOT_DRAINED_EPISODE(as_of=_t(0)))
    with pytest.raises(V2VersionSwitchError, match="conflicting target"):
        evaluate_version_switch_transition(
            r1.state, decision_boundary=_t(1), requested=OTHER,
            drain_fact=NOT_DRAINED_EPISODE(as_of=_t(1)))


def test_vector9_requesting_return_to_active_tuple_while_pending_is_also_refused():
    """Even a request to return to the CURRENTLY-active tuple is refused
    while a switch is pending -- §3.1 defines no cancellation mechanism for
    an in-progress drain."""
    state = _steady_state()
    r1 = evaluate_version_switch_transition(
        state, decision_boundary=_t(0), requested=NEW,
        drain_fact=NOT_DRAINED_EPISODE(as_of=_t(0)))
    with pytest.raises(V2VersionSwitchError, match="conflicting target"):
        evaluate_version_switch_transition(
            r1.state, decision_boundary=_t(1), requested=OLD,
            drain_fact=NOT_DRAINED_EPISODE(as_of=_t(1)))


def test_vector9_conflicting_target_refused_while_awaiting_readiness_too():
    state = _steady_state()
    r1 = evaluate_version_switch_transition(
        state, decision_boundary=_t(0), requested=NEW, drain_fact=DRAINED(as_of=_t(0)))
    assert r1.state.phase == PHASE_AWAITING_ACTIVATION_READINESS
    with pytest.raises(V2VersionSwitchError, match="conflicting target"):
        evaluate_version_switch_transition(
            r1.state, decision_boundary=_t(1), requested=OTHER, candidate_ready=False)


# ---- vector 11: scope mismatch -> rejected -----------------------------------

def test_vector11_run_kind_mismatch_between_states_rejected_by_construction():
    with pytest.raises(V2VersionSwitchError):
        V2VersionSwitchState(
            run_kind="NOT_A_RUN_KIND", run_id="x", active=None, pending=None,
            phase=PHASE_NO_PENDING_SWITCH, drain_complete_at=None, requested_at=None)


def test_vector11_blank_run_id_rejected():
    with pytest.raises(V2VersionSwitchError):
        V2VersionSwitchState(
            run_kind="LIVE", run_id="   ", active=None, pending=None,
            phase=PHASE_NO_PENDING_SWITCH, drain_complete_at=None, requested_at=None)


# ---- vector 12 / finding 4: active_for_new_creation + provenance guard -----

def _provenance(*, run_kind=RUN_KIND, run_id=RUN_ID, rules_version: str,
                 calculation_version: str, decision_code_version: str,
                 decision_boundary: datetime = T0) -> V2DecisionProvenance:
    return V2DecisionProvenance(
        run_kind=run_kind, run_id=run_id, decision_boundary=decision_boundary,
        symbol="BTCUSDT", market_type="perp", model_family="v2",
        rules_version=rules_version, feature_schema_version=1,
        calculation_version=calculation_version, config_hash="d" * 64,
        config_version="cfg-1", code_version="code-1",
        decision_code_version=decision_code_version)


def test_active_for_new_creation_steady_returns_active_tuple():
    assert active_for_new_creation(_steady_state()) == OLD


def test_active_for_new_creation_never_provisioned_returns_none():
    assert active_for_new_creation(initial_switch_state(run_kind="LIVE", run_id=RUN_ID)) is None


def test_active_for_new_creation_draining_returns_none():
    state = V2VersionSwitchState(
        run_kind="LIVE", run_id=RUN_ID, active=OLD, pending=NEW,
        phase=PHASE_DRAINING, drain_complete_at=None, requested_at=_t(0))
    assert active_for_new_creation(state) is None


def test_active_for_new_creation_awaiting_readiness_returns_none():
    state = V2VersionSwitchState(
        run_kind="LIVE", run_id=RUN_ID, active=OLD, pending=NEW,
        phase=PHASE_AWAITING_ACTIVATION_READINESS, drain_complete_at=_t(0),
        requested_at=_t(0))
    assert active_for_new_creation(state) is None


def test_active_for_new_creation_replay_is_always_steady():
    state = V2VersionSwitchState(
        run_kind="REPLAY", run_id="replay-2026-08-20-001", active=OLD, pending=None,
        phase=PHASE_NO_PENDING_SWITCH, drain_complete_at=None, requested_at=None)
    assert active_for_new_creation(state) == OLD


def test_active_for_new_creation_rejects_wrong_typed_state():
    with pytest.raises(V2VersionSwitchError):
        active_for_new_creation("not-a-state")


def test_vector12_provenance_matching_active_tuple_passes_when_steady():
    provenance = _provenance(
        rules_version=OLD.rules_version, calculation_version=OLD.calculation_version,
        decision_code_version=OLD.decision_code_version)
    assert assert_provenance_authorized_for_new_creation(provenance, _steady_state()) is None


def test_vector12_provenance_mismatched_calculation_version_is_refused():
    provenance = _provenance(
        rules_version=OLD.rules_version, calculation_version=NEW.calculation_version,
        decision_code_version=OLD.decision_code_version)
    with pytest.raises(V2VersionSwitchError, match="does not match"):
        assert_provenance_authorized_for_new_creation(provenance, _steady_state())


def test_vector12_provenance_mismatched_rules_version_is_refused():
    provenance = _provenance(
        rules_version=NEW.rules_version, calculation_version=OLD.calculation_version,
        decision_code_version=OLD.decision_code_version)
    with pytest.raises(V2VersionSwitchError, match="does not match"):
        assert_provenance_authorized_for_new_creation(provenance, _steady_state())


def test_vector12_provenance_mismatched_decision_code_version_is_refused():
    provenance = _provenance(
        rules_version=OLD.rules_version, calculation_version=OLD.calculation_version,
        decision_code_version="some-other-decision-code")
    with pytest.raises(V2VersionSwitchError, match="does not match"):
        assert_provenance_authorized_for_new_creation(provenance, _steady_state())


def test_vector12_scope_run_kind_mismatch_is_refused():
    provenance = _provenance(
        run_kind="REPLAY", rules_version=OLD.rules_version,
        calculation_version=OLD.calculation_version,
        decision_code_version=OLD.decision_code_version)
    with pytest.raises(V2VersionSwitchError, match="execution_stream"):
        assert_provenance_authorized_for_new_creation(provenance, _steady_state())


def test_vector12_scope_run_id_mismatch_is_refused():
    provenance = _provenance(
        run_id="some-other-stream", rules_version=OLD.rules_version,
        calculation_version=OLD.calculation_version,
        decision_code_version=OLD.decision_code_version)
    with pytest.raises(V2VersionSwitchError, match="execution_stream"):
        assert_provenance_authorized_for_new_creation(provenance, _steady_state())


def test_vector12_finding4_provenance_matching_old_tuple_still_refused_during_drain():
    """(finding 4, the critical case) A provenance whose OWN tuple exactly
    equals the OLD tuple currently being drained must STILL be refused --
    a bare tuple-value match against OLD is never sufficient by itself
    during an active drain; only active_for_new_creation being non-None
    authorizes creation."""
    state = V2VersionSwitchState(
        run_kind="LIVE", run_id=RUN_ID, active=OLD, pending=NEW,
        phase=PHASE_DRAINING, drain_complete_at=None, requested_at=_t(0))
    provenance = _provenance(
        rules_version=OLD.rules_version, calculation_version=OLD.calculation_version,
        decision_code_version=OLD.decision_code_version)
    with pytest.raises(V2VersionSwitchError, match="no semantic tuple is active"):
        assert_provenance_authorized_for_new_creation(provenance, state)


def test_vector12_finding4_provenance_matching_old_tuple_still_refused_awaiting_readiness():
    state = V2VersionSwitchState(
        run_kind="LIVE", run_id=RUN_ID, active=OLD, pending=NEW,
        phase=PHASE_AWAITING_ACTIVATION_READINESS, drain_complete_at=_t(0),
        requested_at=_t(0))
    provenance = _provenance(
        rules_version=OLD.rules_version, calculation_version=OLD.calculation_version,
        decision_code_version=OLD.decision_code_version)
    with pytest.raises(V2VersionSwitchError, match="no semantic tuple is active"):
        assert_provenance_authorized_for_new_creation(provenance, state)


def test_vector12_rejects_wrong_typed_arguments():
    with pytest.raises(V2VersionSwitchError):
        assert_provenance_authorized_for_new_creation("not-a-provenance", _steady_state())
    provenance = _provenance(
        rules_version=OLD.rules_version, calculation_version=OLD.calculation_version,
        decision_code_version=OLD.decision_code_version)
    with pytest.raises(V2VersionSwitchError):
        assert_provenance_authorized_for_new_creation(provenance, "not-a-state")


# ---- missing-fact fail-closed behavior (never silently assumed) -------------

def test_draining_without_drain_fact_raises():
    state = _steady_state()
    r1 = evaluate_version_switch_transition(
        state, decision_boundary=_t(0), requested=NEW,
        drain_fact=NOT_DRAINED_EPISODE(as_of=_t(0)))
    with pytest.raises(V2VersionSwitchError, match="drain_fact is required"):
        evaluate_version_switch_transition(r1.state, decision_boundary=_t(1))


def test_awaiting_readiness_past_drain_complete_without_candidate_ready_raises():
    state = _steady_state()
    r1 = evaluate_version_switch_transition(
        state, decision_boundary=_t(0), requested=NEW, drain_fact=DRAINED(as_of=_t(0)))
    with pytest.raises(V2VersionSwitchError, match="candidate_ready is required"):
        evaluate_version_switch_transition(r1.state, decision_boundary=_t(1))


def test_same_boundary_as_drain_complete_never_needs_or_consults_candidate_ready():
    state = _steady_state()
    r1 = evaluate_version_switch_transition(
        state, decision_boundary=_t(0), requested=NEW, drain_fact=DRAINED(as_of=_t(0)))
    # Re-evaluating exactly T_drain again (candidate_ready omitted) must not
    # raise -- that boundary never needs it (still entirely OLD's boundary).
    r2 = evaluate_version_switch_transition(r1.state, decision_boundary=_t(0))
    assert r2.action == ACTION_AWAITING_READINESS
    assert r2.state.active == OLD


def test_out_of_order_earlier_boundary_after_drain_complete_raises():
    state = _steady_state()
    r1 = evaluate_version_switch_transition(
        state, decision_boundary=_t(5), requested=NEW, drain_fact=DRAINED(as_of=_t(5)))
    with pytest.raises(V2VersionSwitchError, match="EARLIER"):
        evaluate_version_switch_transition(r1.state, decision_boundary=_t(3), candidate_ready=True)


def test_readiness_going_from_ready_false_to_true_still_activates_later():
    state = _steady_state()
    r1 = evaluate_version_switch_transition(
        state, decision_boundary=_t(0), requested=NEW, drain_fact=DRAINED(as_of=_t(0)))
    r2 = evaluate_version_switch_transition(
        r1.state, decision_boundary=_t(1), candidate_ready=False)
    assert r2.action == ACTION_AWAITING_READINESS
    r3 = evaluate_version_switch_transition(
        r2.state, decision_boundary=_t(2), candidate_ready=True)
    assert r3.action == ACTION_ACTIVATED
    assert r3.state.active == NEW


def test_evaluate_rejects_non_legal_decision_boundary():
    state = _steady_state()
    with pytest.raises(V2VersionSwitchError):
        evaluate_version_switch_transition(state, decision_boundary=_t(0) + timedelta(minutes=1))


def test_evaluate_rejects_wrong_typed_requested():
    state = _steady_state()
    with pytest.raises(V2VersionSwitchError):
        evaluate_version_switch_transition(state, decision_boundary=_t(0), requested="not-a-tuple")


def test_evaluate_rejects_wrong_typed_drain_fact():
    state = _steady_state()
    with pytest.raises(V2VersionSwitchError):
        evaluate_version_switch_transition(
            state, decision_boundary=_t(0), requested=NEW, drain_fact="not-a-drain-fact")


def test_evaluate_rejects_wrong_typed_candidate_ready():
    state = _steady_state()
    r1 = evaluate_version_switch_transition(
        state, decision_boundary=_t(0), requested=NEW, drain_fact=DRAINED(as_of=_t(0)))
    with pytest.raises(V2VersionSwitchError):
        evaluate_version_switch_transition(
            r1.state, decision_boundary=_t(1), candidate_ready="yes")


# ---- finding 5: decision_boundary < requested_at rejected while pending -----

def test_finding5_boundary_before_requested_at_rejected_while_draining():
    """Previously only checked in AWAITING_ACTIVATION_READINESS -- now
    checked immediately whenever ANY switch phase is pending, including
    DRAINING itself."""
    state = _steady_state()
    r1 = evaluate_version_switch_transition(
        state, decision_boundary=_t(5), requested=NEW,
        drain_fact=NOT_DRAINED_EPISODE(as_of=_t(5)))
    assert r1.state.requested_at == _t(5)
    with pytest.raises(V2VersionSwitchError, match="EARLIER"):
        evaluate_version_switch_transition(
            r1.state, decision_boundary=_t(3), drain_fact=NOT_DRAINED_EPISODE(as_of=_t(3)))


def test_finding5_boundary_equal_to_requested_at_is_fine_while_draining():
    state = _steady_state()
    r1 = evaluate_version_switch_transition(
        state, decision_boundary=_t(5), requested=NEW,
        drain_fact=NOT_DRAINED_EPISODE(as_of=_t(5)))
    # Re-evaluating exactly requested_at again must not raise.
    r2 = evaluate_version_switch_transition(
        r1.state, decision_boundary=_t(5), drain_fact=NOT_DRAINED_EPISODE(as_of=_t(5)))
    assert r2.action == ACTION_DRAIN_CONTINUES


def test_finding5_boundary_before_requested_at_rejected_while_awaiting_readiness():
    state = _steady_state()
    r1 = evaluate_version_switch_transition(
        state, decision_boundary=_t(5), requested=NEW, drain_fact=DRAINED(as_of=_t(5)))
    assert r1.state.phase == PHASE_AWAITING_ACTIVATION_READINESS
    with pytest.raises(V2VersionSwitchError, match="EARLIER"):
        evaluate_version_switch_transition(r1.state, decision_boundary=_t(2), candidate_ready=True)
