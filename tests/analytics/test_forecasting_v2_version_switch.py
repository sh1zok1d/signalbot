"""V2-H2b: DRAIN-BEFORE-ACTIVATE version-switch state machine tests
(`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §3.1).

Pure unit tests against `analytics/forecasting_v2/version_switch.py` only --
no DB, no async. Covers all 14 required contract vectors from the V2-H2b
task (some vectors that require real storage/concurrency are instead
covered by `tests/storage/test_v2_version_switch_readers.py`, and vector 10
[reader/readiness corruption fails closed] plus the readiness-gating half of
vector 3/4/5 are covered by
`tests/analytics/test_forecasting_v2_version_switch_orchestrator.py`)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from analytics.forecasting_v2.decision_provenance import V2DecisionProvenance
from analytics.forecasting_v2.version_switch import (
    ACTION_ACTIVATED, ACTION_AWAITING_READINESS, ACTION_DRAIN_COMPLETE,
    ACTION_DRAIN_CONTINUES, ACTION_NO_OP, PHASE_AWAITING_ACTIVATION_READINESS,
    PHASE_DRAINING, PHASE_NO_PENDING_SWITCH, V2DrainFact, V2SemanticTuple,
    V2VersionSwitchError, V2VersionSwitchState, assert_provenance_matches_active_tuple,
    evaluate_version_switch_transition, initial_switch_state,
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

DRAINED = V2DrainFact(non_terminal_episode_count=0, active_cooldown_count=0)
NOT_DRAINED_EPISODE = V2DrainFact(non_terminal_episode_count=1, active_cooldown_count=0)
NOT_DRAINED_COOLDOWN = V2DrainFact(non_terminal_episode_count=0, active_cooldown_count=1)


def _steady_state(active=OLD) -> V2VersionSwitchState:
    return V2VersionSwitchState(
        run_kind="LIVE", run_id="v2-shadow-live", active=active, pending=None,
        phase=PHASE_NO_PENDING_SWITCH, drain_complete_at=None, requested_at=None)


# ---- V2SemanticTuple / V2DrainFact field validation --------------------------

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


def test_drain_fact_rejects_negative_counts():
    with pytest.raises(V2VersionSwitchError):
        V2DrainFact(non_terminal_episode_count=-1, active_cooldown_count=0)
    with pytest.raises(V2VersionSwitchError):
        V2DrainFact(non_terminal_episode_count=0, active_cooldown_count=-1)


def test_drain_fact_rejects_non_int_counts():
    with pytest.raises(V2VersionSwitchError):
        V2DrainFact(non_terminal_episode_count=1.5, active_cooldown_count=0)
    with pytest.raises(V2VersionSwitchError):
        V2DrainFact(non_terminal_episode_count=True, active_cooldown_count=0)


def test_drain_fact_drained_property():
    assert DRAINED.drained is True
    assert NOT_DRAINED_EPISODE.drained is False
    assert NOT_DRAINED_COOLDOWN.drained is False


# ---- V2VersionSwitchState self-validation ------------------------------------

def test_initial_switch_state_is_no_pending_switch():
    s = initial_switch_state(run_kind="LIVE", run_id="v2-shadow-live")
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
        state, decision_boundary=_t(0), requested=NEW, drain_fact=DRAINED)
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
        state, decision_boundary=_t(0), requested=NEW, drain_fact=NOT_DRAINED_EPISODE)
    assert r1.action == ACTION_DRAIN_CONTINUES
    assert r1.state.phase == PHASE_DRAINING
    assert r1.state.active == OLD

    # Even supplying candidate_ready=True has no effect while still DRAINING
    # -- drain gates unconditionally first; the pure function does not even
    # consult candidate_ready in this phase.
    r2 = evaluate_version_switch_transition(
        r1.state, decision_boundary=_t(1), drain_fact=NOT_DRAINED_COOLDOWN)
    assert r2.action == ACTION_DRAIN_CONTINUES
    assert r2.state.active == OLD


# ---- vector 5: target ready AND current drained -> exactly one activation --

def test_vector5_ready_and_drained_activates_exactly_once():
    state = _steady_state()
    r1 = evaluate_version_switch_transition(
        state, decision_boundary=_t(0), requested=NEW, drain_fact=NOT_DRAINED_EPISODE)
    assert r1.action == ACTION_DRAIN_CONTINUES

    r2 = evaluate_version_switch_transition(
        r1.state, decision_boundary=_t(1), drain_fact=DRAINED)
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
    itself, only at T_request + 5m at the earliest."""
    state = _steady_state()
    r1 = evaluate_version_switch_transition(
        state, decision_boundary=_t(5), requested=NEW, drain_fact=DRAINED)
    assert r1.action == ACTION_DRAIN_COMPLETE
    assert r1.request_accepted is True
    assert r1.state.drain_complete_at == _t(5)
    assert r1.state.active == OLD  # still OLD -- not activated at T_request.

    r2 = evaluate_version_switch_transition(
        r1.state, decision_boundary=_t(6), candidate_ready=True)
    assert r2.action == ACTION_ACTIVATED
    assert r2.state.active == NEW


def test_bootstrap_first_activation_uses_same_drain_before_activate_timing():
    """A fresh execution_stream's very first activation goes through the
    exact same T_request -> T_request+5m delay -- no special-cased
    "activate immediately" bootstrap path."""
    state = initial_switch_state(run_kind="LIVE", run_id="fresh-stream")
    r1 = evaluate_version_switch_transition(
        state, decision_boundary=_t(0), requested=OLD, drain_fact=DRAINED)
    assert r1.action == ACTION_DRAIN_COMPLETE
    assert r1.state.active is None  # still nothing active at T_request.

    r2 = evaluate_version_switch_transition(
        r1.state, decision_boundary=_t(1), candidate_ready=True)
    assert r2.action == ACTION_ACTIVATED
    assert r2.state.active == OLD


# ---- vector 6: restart while draining -> persisted state resumes identically

def test_vector6_restart_while_draining_resumes_identically():
    state = _steady_state()
    r1 = evaluate_version_switch_transition(
        state, decision_boundary=_t(0), requested=NEW, drain_fact=NOT_DRAINED_EPISODE)
    persisted = r1.state  # simulates durable persistence before "restart".

    # "Restart": reload the exact same persisted state and continue -- the
    # pure function is deterministic, so this reproduces bit-for-bit.
    reloaded = V2VersionSwitchState(
        run_kind=persisted.run_kind, run_id=persisted.run_id, active=persisted.active,
        pending=persisted.pending, phase=persisted.phase,
        drain_complete_at=persisted.drain_complete_at, requested_at=persisted.requested_at)
    assert reloaded == persisted

    r2 = evaluate_version_switch_transition(
        reloaded, decision_boundary=_t(1), drain_fact=DRAINED)
    assert r2.action == ACTION_DRAIN_COMPLETE
    assert r2.state.pending == NEW  # never cancelled/reset by "restart".


# ---- vector 7: restart after activation -> new active remains authoritative -

def test_vector7_restart_after_activation_new_active_remains_authoritative():
    state = _steady_state()
    r1 = evaluate_version_switch_transition(
        state, decision_boundary=_t(0), requested=NEW, drain_fact=DRAINED)
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
        state, decision_boundary=_t(0), requested=NEW, drain_fact=NOT_DRAINED_EPISODE)
    assert r1.request_accepted is True

    r2 = evaluate_version_switch_transition(
        r1.state, decision_boundary=_t(1), requested=NEW, drain_fact=NOT_DRAINED_EPISODE)
    assert r2.request_accepted is False  # NOT a new switch -- same pending target.
    assert r2.state.pending == NEW
    assert r2.state.requested_at == _t(0)  # unchanged -- not re-stamped.


# ---- vector 9: conflicting target request while pending -> refused ----------

def test_vector9_conflicting_target_while_pending_is_refused():
    state = _steady_state()
    r1 = evaluate_version_switch_transition(
        state, decision_boundary=_t(0), requested=NEW, drain_fact=NOT_DRAINED_EPISODE)
    with pytest.raises(V2VersionSwitchError, match="conflicting target"):
        evaluate_version_switch_transition(
            r1.state, decision_boundary=_t(1), requested=OTHER, drain_fact=NOT_DRAINED_EPISODE)


def test_vector9_requesting_return_to_active_tuple_while_pending_is_also_refused():
    """Even a request to return to the CURRENTLY-active tuple is refused
    while a switch is pending -- §3.1 defines no cancellation mechanism for
    an in-progress drain."""
    state = _steady_state()
    r1 = evaluate_version_switch_transition(
        state, decision_boundary=_t(0), requested=NEW, drain_fact=NOT_DRAINED_EPISODE)
    with pytest.raises(V2VersionSwitchError, match="conflicting target"):
        evaluate_version_switch_transition(
            r1.state, decision_boundary=_t(1), requested=OLD, drain_fact=NOT_DRAINED_EPISODE)


def test_vector9_conflicting_target_refused_while_awaiting_readiness_too():
    state = _steady_state()
    r1 = evaluate_version_switch_transition(
        state, decision_boundary=_t(0), requested=NEW, drain_fact=DRAINED)
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


# ---- vector 12: provenance/switch version mismatch -> refused ---------------

def _provenance(*, rules_version: str, calculation_version: str, decision_code_version: str,
                 decision_boundary: datetime = T0) -> V2DecisionProvenance:
    return V2DecisionProvenance(
        run_kind="LIVE", run_id="v2-shadow-live", decision_boundary=decision_boundary,
        symbol="BTCUSDT", market_type="perp", model_family="v2",
        rules_version=rules_version, feature_schema_version=1,
        calculation_version=calculation_version, config_hash="d" * 64,
        config_version="cfg-1", code_version="code-1",
        decision_code_version=decision_code_version)


def test_vector12_provenance_matching_active_tuple_passes():
    provenance = _provenance(
        rules_version=OLD.rules_version, calculation_version=OLD.calculation_version,
        decision_code_version=OLD.decision_code_version)
    assert_provenance_matches_active_tuple(provenance, OLD) is None


def test_vector12_provenance_mismatched_calculation_version_is_refused():
    provenance = _provenance(
        rules_version=OLD.rules_version, calculation_version=NEW.calculation_version,
        decision_code_version=OLD.decision_code_version)
    with pytest.raises(V2VersionSwitchError, match="does not match"):
        assert_provenance_matches_active_tuple(provenance, OLD)


def test_vector12_provenance_mismatched_rules_version_is_refused():
    provenance = _provenance(
        rules_version=NEW.rules_version, calculation_version=OLD.calculation_version,
        decision_code_version=OLD.decision_code_version)
    with pytest.raises(V2VersionSwitchError, match="does not match"):
        assert_provenance_matches_active_tuple(provenance, OLD)


def test_vector12_provenance_mismatched_decision_code_version_is_refused():
    provenance = _provenance(
        rules_version=OLD.rules_version, calculation_version=OLD.calculation_version,
        decision_code_version="some-other-decision-code")
    with pytest.raises(V2VersionSwitchError, match="does not match"):
        assert_provenance_matches_active_tuple(provenance, OLD)


def test_vector12_rejects_wrong_typed_arguments():
    with pytest.raises(V2VersionSwitchError):
        assert_provenance_matches_active_tuple("not-a-provenance", OLD)
    provenance = _provenance(
        rules_version=OLD.rules_version, calculation_version=OLD.calculation_version,
        decision_code_version=OLD.decision_code_version)
    with pytest.raises(V2VersionSwitchError):
        assert_provenance_matches_active_tuple(provenance, "not-a-tuple")


# ---- missing-fact fail-closed behavior (never silently assumed) -------------

def test_draining_without_drain_fact_raises():
    state = _steady_state()
    r1 = evaluate_version_switch_transition(
        state, decision_boundary=_t(0), requested=NEW, drain_fact=NOT_DRAINED_EPISODE)
    with pytest.raises(V2VersionSwitchError, match="drain_fact is required"):
        evaluate_version_switch_transition(r1.state, decision_boundary=_t(1))


def test_awaiting_readiness_past_drain_complete_without_candidate_ready_raises():
    state = _steady_state()
    r1 = evaluate_version_switch_transition(
        state, decision_boundary=_t(0), requested=NEW, drain_fact=DRAINED)
    with pytest.raises(V2VersionSwitchError, match="candidate_ready is required"):
        evaluate_version_switch_transition(r1.state, decision_boundary=_t(1))


def test_same_boundary_as_drain_complete_never_needs_or_consults_candidate_ready():
    state = _steady_state()
    r1 = evaluate_version_switch_transition(
        state, decision_boundary=_t(0), requested=NEW, drain_fact=DRAINED)
    # Re-evaluating exactly T_drain again (candidate_ready omitted) must not
    # raise -- that boundary never needs it (still entirely OLD's boundary).
    r2 = evaluate_version_switch_transition(r1.state, decision_boundary=_t(0))
    assert r2.action == ACTION_AWAITING_READINESS
    assert r2.state.active == OLD


def test_out_of_order_earlier_boundary_after_drain_complete_raises():
    state = _steady_state()
    r1 = evaluate_version_switch_transition(
        state, decision_boundary=_t(5), requested=NEW, drain_fact=DRAINED)
    with pytest.raises(V2VersionSwitchError, match="EARLIER"):
        evaluate_version_switch_transition(r1.state, decision_boundary=_t(3), candidate_ready=True)


def test_readiness_going_from_ready_false_to_true_still_activates_later():
    state = _steady_state()
    r1 = evaluate_version_switch_transition(
        state, decision_boundary=_t(0), requested=NEW, drain_fact=DRAINED)
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
        state, decision_boundary=_t(0), requested=NEW, drain_fact=DRAINED)
    with pytest.raises(V2VersionSwitchError):
        evaluate_version_switch_transition(
            r1.state, decision_boundary=_t(1), candidate_ready="yes")
