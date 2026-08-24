"""Pure-domain tests for Stage 6 Unit 2 — candidate routing, creation
eligibility, family precedence and `EARLY_SIGNAL` creation
(`analytics/forecasting_v2/episode_creation.py`).

No database. Existing episodes are built by persisting a REAL Unit 2
creation event and reconstructing it through Unit 1's
`reconstruct_episode_history()`, so every classification vector runs
against exactly the persisted shape a restart would see — never a
hand-assembled in-memory stand-in.
"""
from __future__ import annotations

import itertools
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from analytics.forecasting_v2.activation_readiness import (
    MANDATORY_PERCENTILE_COVERAGE, V2ActivationReadinessResult, V2CoverageStatus,
)
from analytics.forecasting_v2.decision_provenance import V2DecisionProvenance
from analytics.forecasting_v2.decision_view import V2DecisionView
from analytics.forecasting_v2.episode_creation import (
    ANCHOR_DRIFT_BUCKETS, CREATE_EARLY_SIGNAL, CREATION_FACTS_KEY,
    ELIGIBLE_FOR_CREATION, FAMILY_PRECEDENCE,
    MATCH_EXACT, MATCH_MATERIAL, MATCH_NON_MATERIAL, PRECEDENCE_CROSSREF_KEY,
    ROUTE_EXISTING_EXACT, ROUTE_EXISTING_NON_MATERIAL, SUPPRESSED_ACTIVE_SLOT,
    SUPPRESSED_COOLDOWN, SUPPRESSED_FAMILY_PRECEDENCE, TERMINAL_COOLDOWN_BUCKETS,
    V2BoundaryRoutingResult, V2CandidateFacts, V2CandidateOutcome,
    V2CreationAuthorization, V2EpisodeCreationError,
    V2SlotCooldownView, V2SlotOccupancyView, V2SlotTerminalFact,
    arbitrate_new_candidates, build_early_signal_creation,
    classify_candidate_against_active_episode, evaluate_terminal_cooldown,
    read_creation_protection_buffer, route_candidates_at_boundary,
)
from analytics.forecasting_v2.episode_history import (
    HISTORY_THROUGH_T, V2EpisodeHistoryCorruptionError, reconstruct_episode_history,
)
from analytics.forecasting_v2.event_factory import build_v2_episode_event
from analytics.forecasting_v2.events import (
    COMPLETED, COMPRESSION_BREAKOUT, CONFIRMED, CONFIRMED_BREAKOUT, EARLY_SIGNAL,
    EXPIRED, INVALIDATED, LIVE, LONG, SHORT, TREND_PULLBACK,
)
from analytics.forecasting_v2.provenance import V2EventProvenance
from analytics.forecasting_v2.version_switch import (
    V2SemanticTuple, initial_switch_state, provision_initial_tuple,
)
from common.v2_config import MODEL_FAMILY

UTC = timezone.utc
T0 = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)      # legal 5m, 15m and 1h boundary
H64 = "a" * 64
H16 = "b" * 16
RULES = "v2-rules-v0.1.0"
DCV = "decision-code-1"
RUN_ID = "live-stream-1"


def _t(n: int) -> datetime:
    """`n` 5m decision boundaries after T0."""
    return T0 + timedelta(minutes=5 * n)


def _q(n: int) -> datetime:
    """`n` 15m anchor buckets after T0."""
    return T0 + timedelta(minutes=15 * n)


def _h(n: int) -> datetime:
    """`n` 1h anchor buckets after T0."""
    return T0 + timedelta(hours=n)


# ---- authorization fixtures -------------------------------------------------
def _provenance(*, T=T0, run_kind=LIVE, run_id=RUN_ID, **over) -> V2DecisionProvenance:
    base = dict(
        run_kind=run_kind, run_id=run_id, decision_boundary=T, symbol="BTCUSDT",
        market_type="perp", model_family=MODEL_FAMILY, rules_version=RULES,
        feature_schema_version=1, calculation_version=H16, config_hash=H64,
        config_version="2.1.0", code_version="feat-code-1", decision_code_version=DCV,
    )
    base.update(over)
    return V2DecisionProvenance(**base)


def _readiness(*, T=T0, ready=True) -> V2ActivationReadinessResult:
    """A §3.3 readiness result whose per-requirement statuses agree with its
    own `ready` verdict (the result validates that agreement itself)."""
    statuses = tuple(
        V2CoverageStatus(requirement=req, ready=ready, reason="fixture", latest_bucket_ts=T)
        for req in MANDATORY_PERCENTILE_COVERAGE)
    return V2ActivationReadinessResult(
        symbol="BTCUSDT", market_type="perp", calculation_version=H16,
        decision_boundary=T, ready=ready, statuses=statuses)


def _switch_state(*, T=T0, run_kind=LIVE, run_id=RUN_ID, tuple_=None):
    state = initial_switch_state(run_kind=run_kind, run_id=run_id)
    tuple_ = tuple_ or V2SemanticTuple(
        rules_version=RULES, calculation_version=H16, decision_code_version=DCV)
    return provision_initial_tuple(
        state, decision_boundary=T, tuple_=tuple_, candidate_ready=True).state


def _authorization(*, T=T0, ready=True, run_kind=LIVE, run_id=RUN_ID,
                   publication_clean=True, **prov_over) -> V2CreationAuthorization:
    return V2CreationAuthorization(
        decision_view=V2DecisionView(
            provenance=_provenance(T=T, run_kind=run_kind, run_id=run_id, **prov_over),
            readiness=_readiness(T=T, ready=ready)),
        switch_state=_switch_state(T=T, run_kind=run_kind, run_id=run_id),
        publication_clean=publication_clean,
    )


# ---- candidate fixtures -----------------------------------------------------
def tp_candidate(*, T=T0, anchor=None, direction=LONG, lower=100.0, upper=110.0,
                 buffer=50.0, tick=0.1) -> V2CandidateFacts:
    return V2CandidateFacts(
        symbol="BTCUSDT", market_type="perp", direction=direction,
        setup_family=TREND_PULLBACK, T=T,
        anchor_bucket=anchor if anchor is not None else T0, raw_level_price=None,
        entry_zone_lower=lower, entry_zone_upper=upper, invalidation_price=95.0,
        protection_buffer=buffer, decision_tick_size=tick,
        setup_strength=0.7, data_confidence=0.9, family_facts={"pullback_extreme": 101.0})


def comp_candidate(*, T=T0, anchor=None, direction=LONG, lower=100.0, upper=110.0,
                   buffer=50.0, tick=0.1) -> V2CandidateFacts:
    return V2CandidateFacts(
        symbol="BTCUSDT", market_type="perp", direction=direction,
        setup_family=COMPRESSION_BREAKOUT, T=T,
        anchor_bucket=anchor if anchor is not None else T0, raw_level_price=None,
        entry_zone_lower=lower, entry_zone_upper=upper, invalidation_price=95.0,
        protection_buffer=buffer, decision_tick_size=tick,
        setup_strength=0.8, data_confidence=0.9, family_facts={"range_low": 99.0})


def cb_candidate(*, T=T0, anchor=None, raw_level=66200.04, direction=LONG,
                 lower=100.0, upper=110.0, buffer=50.0, tick=0.1) -> V2CandidateFacts:
    return V2CandidateFacts(
        symbol="BTCUSDT", market_type="perp", direction=direction,
        setup_family=CONFIRMED_BREAKOUT, T=T,
        anchor_bucket=anchor if anchor is not None else T0, raw_level_price=raw_level,
        entry_zone_lower=lower, entry_zone_upper=upper, invalidation_price=95.0,
        protection_buffer=buffer, decision_tick_size=tick,
        setup_strength=0.6, data_confidence=0.9, family_facts={"level_kind": "RESISTANCE"})


# ---- persist-then-reconstruct helper ---------------------------------------
def _row(event) -> dict:
    return {
        "run_kind": event.run_kind, "run_id": event.run_id, "event_id": event.event_id,
        "episode_id": event.episode_id, "model_family": event.model_family,
        "rules_version": event.rules_version, "symbol": event.symbol,
        "market_type": event.market_type, "direction": event.direction,
        "setup_family": event.setup_family,
        "structural_anchor": dict(event.structural_anchor),
        "episode_state": event.episode_state, "decision_boundary": event.decision_boundary,
        "feature_schema_version": event.feature_schema_version,
        "calculation_version": event.calculation_version, "config_hash": event.config_hash,
        "config_version": event.config_version, "code_version": event.code_version,
        "decision_code_version": event.decision_code_version,
        "decision_snapshot": dict(event.decision_snapshot),
        "event_payload": dict(event.event_payload),
    }


def existing_episode(candidate, *, T=T0, as_of=None, run_kind=LIVE, run_id=RUN_ID):
    """Create a real Unit 2 EARLY_SIGNAL event, then read it back through
    Unit 1 exactly as a fresh process would."""
    event = build_early_signal_creation(
        candidate, authorization=_authorization(T=T, run_kind=run_kind, run_id=run_id), T=T)
    return reconstruct_episode_history(
        [_row(event)], run_kind=run_kind, run_id=run_id, episode_id=event.episode_id,
        as_of=as_of if as_of is not None else _t(100), boundary_mode=HISTORY_THROUGH_T)


def _event_provenance(*, T=T0, run_kind=LIVE, run_id=RUN_ID) -> V2EventProvenance:
    p = _provenance(T=T, run_kind=run_kind, run_id=run_id)
    return V2EventProvenance(
        run_kind=p.run_kind, run_id=p.run_id, model_family=p.model_family,
        rules_version=p.rules_version, symbol=p.symbol, market_type=p.market_type,
        feature_schema_version=p.feature_schema_version,
        calculation_version=p.calculation_version, config_hash=p.config_hash,
        config_version=p.config_version, code_version=p.code_version,
        decision_code_version=p.decision_code_version)


def _follow_up(creation, *, episode_state, decision_boundary, t_create,
               run_kind=LIVE, run_id=RUN_ID):
    """A later lifecycle event of the SAME episode: identical frozen creation
    identity (§12.2), a new decision boundary."""
    return build_v2_episode_event(
        _event_provenance(T=decision_boundary, run_kind=run_kind, run_id=run_id),
        t_create=t_create, direction=creation.direction,
        setup_family=creation.setup_family,
        structural_anchor=dict(creation.structural_anchor),
        episode_state=episode_state, decision_boundary=decision_boundary,
        decision_snapshot={}, event_payload={})


def terminal_history(make=tp_candidate, *, terminal_state=INVALIDATED, t_terminal=T0,
                     run_kind=LIVE, run_id=RUN_ID, as_of=None, **candidate_kw):
    """A REAL terminal episode: creation event, the §13.2-legal transitions
    that reach `terminal_state`, then read back through Unit 1 — never a
    hand-made terminal summary."""
    lead = 2 if terminal_state == COMPLETED else 1
    t_create = t_terminal - lead * timedelta(minutes=5)
    candidate = make(T=t_create, **candidate_kw)
    creation = build_early_signal_creation(
        candidate, authorization=_authorization(T=t_create, run_kind=run_kind, run_id=run_id),
        T=t_create)
    events = [creation]
    if terminal_state == COMPLETED:
        events.append(_follow_up(
            creation, episode_state=CONFIRMED,
            decision_boundary=t_terminal - timedelta(minutes=5), t_create=t_create,
            run_kind=run_kind, run_id=run_id))
    events.append(_follow_up(
        creation, episode_state=terminal_state, decision_boundary=t_terminal,
        t_create=t_create, run_kind=run_kind, run_id=run_id))
    return reconstruct_episode_history(
        [_row(e) for e in events], run_kind=run_kind, run_id=run_id,
        episode_id=creation.episode_id,
        as_of=as_of if as_of is not None else _t(100), boundary_mode=HISTORY_THROUGH_T)


def terminal_fact(**kw) -> V2SlotTerminalFact:
    return V2SlotTerminalFact(history=terminal_history(**kw))


def _occupancy(*histories, T=T0):
    by_slot = {}
    for h in histories:
        by_slot.setdefault(h.creation_identity.slot, []).append(h)
    return V2SlotOccupancyView(as_of=T, active_by_slot=by_slot)


def _cooldown(*facts, T=T0):
    return V2SlotCooldownView(
        as_of=T, terminal_by_slot={slot: fact for slot, fact in facts})


# ============================================================================
# 1. §12.4 — TREND_PULLBACK / COMPRESSION_BREAKOUT bucket drift
# ============================================================================
@pytest.mark.parametrize("make", [tp_candidate, comp_candidate])
@pytest.mark.parametrize(("buckets", "expected"), [
    (0, MATCH_EXACT),
    (1, MATCH_NON_MATERIAL),
    (4, MATCH_NON_MATERIAL),      # §12.4: exactly 4 passes as non-material
    (5, MATCH_MATERIAL),          # §12.4: 5 buckets away is material
    (9, MATCH_MATERIAL),
])
def test_bucket_anchored_family_drift_thresholds(make, buckets, expected):
    active = existing_episode(make(anchor=_q(0)))
    candidate = make(T=_t(1), anchor=_q(buckets))
    assert classify_candidate_against_active_episode(candidate, active) == expected


@pytest.mark.parametrize("make", [tp_candidate, comp_candidate])
def test_drift_is_symmetric_backwards_in_time(make):
    """§12.4 uses `abs(C - A)` -- an earlier anchor drifts identically."""
    active = existing_episode(make(anchor=_q(9)))
    assert classify_candidate_against_active_episode(
        make(T=_t(1), anchor=_q(5)), active) == MATCH_NON_MATERIAL
    assert classify_candidate_against_active_episode(
        make(T=_t(1), anchor=_q(4)), active) == MATCH_MATERIAL


def test_anchor_drift_bucket_constant_is_four():
    assert ANCHOR_DRIFT_BUCKETS == 4


def test_off_grid_candidate_anchor_is_rejected_not_coerced():
    """An off-grid anchor never reaches classification at all: it is refused
    when the candidate is built (§12.1's family grid)."""
    with pytest.raises(V2EpisodeCreationError, match="structural anchor"):
        tp_candidate(T=_t(1), anchor=T0 + timedelta(minutes=7))


# ============================================================================
# 2. §12.3/§12.4/§12.5a — CONFIRMED_BREAKOUT
# ============================================================================
def test_confirmed_breakout_exact_match_needs_both_bucket_and_tick():
    active = existing_episode(cb_candidate(anchor=_h(0), raw_level=66200.04, tick=0.1))
    same = cb_candidate(T=_t(1), anchor=_h(0), raw_level=66200.04)
    assert classify_candidate_against_active_episode(same, active) == MATCH_EXACT


def test_confirmed_breakout_same_tick_different_bucket_is_not_exact_but_non_material():
    """§12.3's own worked example: same tick, different `level_anchor_bucket`
    -> NOT case (A); `level_drift = 0 <= 2*buffer` -> case (B)."""
    active = existing_episode(cb_candidate(anchor=_h(0), raw_level=66200.04, tick=0.1))
    other_bucket = cb_candidate(T=_t(1), anchor=_h(1), raw_level=66200.04)
    assert classify_candidate_against_active_episode(other_bucket, active) == MATCH_NON_MATERIAL


def test_confirmed_breakout_drift_exactly_two_buffers_is_non_material():
    """§12.4: `level_drift <= 2 * creation_buffer` -> NON-MATERIAL."""
    active = existing_episode(cb_candidate(anchor=_h(0), raw_level=66000.0, buffer=150.0, tick=0.1))
    at_threshold = cb_candidate(T=_t(1), anchor=_h(0), raw_level=66300.0)   # drift 300 == 2*150
    assert classify_candidate_against_active_episode(at_threshold, active) == MATCH_NON_MATERIAL


def test_confirmed_breakout_drift_above_two_buffers_is_material():
    active = existing_episode(cb_candidate(anchor=_h(0), raw_level=66000.0, buffer=150.0, tick=0.1))
    over = cb_candidate(T=_t(1), anchor=_h(0), raw_level=66300.1)           # drift 300.1 > 300
    assert classify_candidate_against_active_episode(over, active) == MATCH_MATERIAL


def test_confirmed_breakout_uses_creation_grid_not_current_tick_size():
    """§12.5a: the candidate's raw level is normalized against the ACTIVE
    EPISODE'S creation tick grid, never today's instrument tick."""
    active = existing_episode(cb_candidate(anchor=_h(0), raw_level=66200.04, tick=0.1))
    assert active.creation_identity.creation_identity_tick_size == Decimal("0.1")

    # The instrument's tick has since become finer. On the CREATION grid
    # (0.1) this candidate is still tick_index 662000 -> exact match; on the
    # candidate's own current grid (0.01) it would be 6620004 -> not exact.
    finer = cb_candidate(T=_t(1), anchor=_h(0), raw_level=66200.04, tick=0.01)
    assert classify_candidate_against_active_episode(finer, active) == MATCH_EXACT


def test_confirmed_breakout_threshold_uses_persisted_creation_buffer():
    """§12.4: the threshold is 2x the buffer recorded AT CREATION -- a later
    candidate observing a different volatility environment cannot move it."""
    active = existing_episode(cb_candidate(anchor=_h(0), raw_level=66000.0, buffer=150.0))
    assert read_creation_protection_buffer(active) == Decimal("150")

    # Candidate carries a much larger current buffer; the threshold must
    # still be 2*150 = 300, so a drift of 400 is MATERIAL.
    wide = cb_candidate(T=_t(1), anchor=_h(0), raw_level=66400.0, buffer=5000.0)
    assert classify_candidate_against_active_episode(wide, active) == MATCH_MATERIAL


def test_missing_persisted_creation_buffer_fails_closed():
    active = existing_episode(cb_candidate(anchor=_h(0), raw_level=66000.0))
    stripped = dict(active.creation_event.decision_snapshot[CREATION_FACTS_KEY])
    stripped.pop("protection_buffer")
    row = _row(active.creation_event)
    row["decision_snapshot"] = {CREATION_FACTS_KEY: stripped}
    broken = reconstruct_episode_history(
        [row], run_kind=LIVE, run_id=RUN_ID, episode_id=active.episode_id,
        as_of=_t(100), boundary_mode=HISTORY_THROUGH_T)
    with pytest.raises(V2EpisodeCreationError, match="protection_buffer"):
        classify_candidate_against_active_episode(
            cb_candidate(T=_t(1), anchor=_h(1), raw_level=66000.0), broken)


# ============================================================================
# 3. classification never mutates or duplicates
# ============================================================================
@pytest.mark.parametrize("buckets", [0, 3, 4])
def test_route_outcomes_never_create_a_second_episode(buckets):
    active = existing_episode(tp_candidate(anchor=_q(0)))
    result = route_candidates_at_boundary(
        [tp_candidate(T=_t(1), anchor=_q(buckets))], T=_t(1),
        occupancy=_occupancy(active, T=_t(1)), cooldown=_cooldown(T=_t(1)),
        authorization=_authorization(T=_t(1)))
    assert result.creation_events == ()
    assert result.outcomes[0].routed_episode_id == active.episode_id
    assert result.outcomes[0].outcome in (ROUTE_EXISTING_EXACT, ROUTE_EXISTING_NON_MATERIAL)


def test_material_drift_creates_nothing_and_leaves_identity_untouched():
    active = existing_episode(tp_candidate(anchor=_q(0)))
    before = active.creation_identity
    result = route_candidates_at_boundary(
        [tp_candidate(T=_t(1), anchor=_q(9))], T=_t(1),
        occupancy=_occupancy(active, T=_t(1)), cooldown=_cooldown(T=_t(1)),
        authorization=_authorization(T=_t(1)))
    assert result.outcomes[0].outcome == SUPPRESSED_ACTIVE_SLOT
    assert result.creation_events == ()
    assert active.creation_identity == before


def test_ab_routing_writes_no_event_at_all():
    """§12.11: identity classification is not event necessity."""
    active = existing_episode(tp_candidate(anchor=_q(0)))
    for buckets in (0, 2, 4):
        result = route_candidates_at_boundary(
            [tp_candidate(T=_t(1), anchor=_q(buckets))], T=_t(1),
            occupancy=_occupancy(active, T=_t(1)), cooldown=_cooldown(T=_t(1)),
            authorization=_authorization(T=_t(1)))
        assert result.creation_events == ()
        assert all(o.creation_event is None for o in result.outcomes)


# ============================================================================
# 4. §12.6 — one active episode per slot
# ============================================================================
def test_two_active_episodes_in_one_slot_fail_closed():
    a = existing_episode(tp_candidate(anchor=_q(0)))
    b = existing_episode(tp_candidate(anchor=_q(7)))
    assert a.creation_identity.slot == b.creation_identity.slot
    view = _occupancy(a, b, T=_t(1))
    with pytest.raises(V2EpisodeCreationError, match="at most ONE active"):
        view.active_episode(a.creation_identity.slot)


def test_occupancy_view_rejects_a_terminal_episode():
    active = existing_episode(tp_candidate(anchor=_q(0)))
    row = _row(active.creation_event)
    terminal_row = dict(row)
    terminal_row["episode_state"] = INVALIDATED
    with pytest.raises(V2EpisodeCreationError):
        V2SlotOccupancyView(
            as_of=T0,
            active_by_slot={active.creation_identity.slot: [
                reconstruct_episode_history(
                    [row, {**terminal_row,
                           "decision_boundary": _t(1),
                           "event_id": _terminal_event_id(active.episode_id, _t(1))}],
                    run_kind=LIVE, run_id=RUN_ID, episode_id=active.episode_id,
                    as_of=_t(5), boundary_mode=HISTORY_THROUGH_T)]})


def _terminal_event_id(episode_id, boundary):
    from analytics.forecasting_v2.episode_identity import compute_event_id
    return compute_event_id(episode_id=episode_id, decision_boundary=boundary)


# ============================================================================
# 5. §12.8 — terminal cooldown exact clock
# ============================================================================
@pytest.mark.parametrize(("terminal_state", "buckets"), [
    (INVALIDATED, 3), (EXPIRED, 1), (COMPLETED, 1)])
def test_cooldown_table_matches_the_frozen_contract(terminal_state, buckets):
    assert TERMINAL_COOLDOWN_BUCKETS[terminal_state] == buckets
    fact = terminal_fact(terminal_state=terminal_state, t_terminal=T0)
    assert fact.terminal_state == terminal_state
    assert fact.t_terminal == T0
    assert fact.earliest_eligible_boundary == T0 + timedelta(minutes=5 * buckets)


@pytest.mark.parametrize(("terminal_state", "blocked", "eligible"), [
    (INVALIDATED, (0, 1, 2), 3),     # T, T+5m, T+10m blocked; T+15m eligible
    (EXPIRED, (0,), 1),              # T blocked; T+5m eligible
    (COMPLETED, (0,), 1),
])
def test_cooldown_boundaries(terminal_state, blocked, eligible):
    fact = terminal_fact(terminal_state=terminal_state, t_terminal=T0)
    for n in blocked:
        assert evaluate_terminal_cooldown(fact, T=_t(n)) is False, f"T+{5*n}m must be blocked"
    assert evaluate_terminal_cooldown(fact, T=_t(eligible)) is True
    assert evaluate_terminal_cooldown(fact, T=_t(eligible + 1)) is True


def test_t_terminal_itself_is_never_eligible():
    """§12.8's cooldown is >= 1 bucket in every case."""
    for state in TERMINAL_COOLDOWN_BUCKETS:
        fact = terminal_fact(terminal_state=state, t_terminal=T0)
        assert evaluate_terminal_cooldown(fact, T=T0) is False


def test_no_terminal_fact_means_eligible():
    assert evaluate_terminal_cooldown(None, T=T0) is True


def test_same_T_terminal_blocks_by_cooldown_even_though_slot_is_empty():
    """§13.4's critical two-view vector: the episode became terminal AT T,
    so `surviving_active_set(T)` no longer holds it (ACTIVE check passes)
    while 3b's cooldown, whose `T_terminal = T`, still blocks."""
    candidate = tp_candidate(T=_t(0), anchor=_q(0))
    slot = candidate.slot
    result = route_candidates_at_boundary(
        [candidate], T=T0,
        occupancy=V2SlotOccupancyView(as_of=T0, active_by_slot={}),        # 3a: empty
        cooldown=_cooldown((slot, terminal_fact(
            terminal_state=INVALIDATED, t_terminal=T0)), T=T0),
        authorization=_authorization(T=T0))
    assert result.outcomes[0].outcome == SUPPRESSED_COOLDOWN
    assert result.outcomes[0].cooldown_until == _t(3)
    assert result.creation_events == ()


def test_cooldown_view_rejects_a_future_terminal_fact():
    with pytest.raises(V2EpisodeCreationError, match="after as_of"):
        V2SlotCooldownView(
            as_of=T0,
            terminal_by_slot={tp_candidate().slot: terminal_fact(
                terminal_state=EXPIRED, t_terminal=_t(3))})


def test_off_grid_terminal_boundary_fails_closed():
    """An off-grid `T_terminal` cannot even be persisted into a history, so
    no terminal fact can be built from one."""
    with pytest.raises(V2EpisodeCreationError, match="5m decision boundary"):
        terminal_fact(terminal_state=EXPIRED, t_terminal=T0 + timedelta(minutes=2))


# ============================================================================
# 6. §12.7 — suppressed is never queued
# ============================================================================
def test_suppressed_candidate_is_not_resurrected_when_the_blocker_clears():
    slot = tp_candidate().slot
    blocked = route_candidates_at_boundary(
        [tp_candidate(T=T0, anchor=_q(0))], T=T0,
        occupancy=V2SlotOccupancyView(as_of=T0, active_by_slot={}),
        cooldown=_cooldown((slot, terminal_fact(
            terminal_state=INVALIDATED, t_terminal=T0)), T=T0),
        authorization=_authorization(T=T0))
    assert blocked.outcomes[0].outcome == SUPPRESSED_COOLDOWN

    # The blocker has cleared at T+15m, but Stage 5 supplied NO candidate.
    cleared = route_candidates_at_boundary(
        [], T=_t(3),
        occupancy=V2SlotOccupancyView(as_of=_t(3), active_by_slot={}),
        cooldown=_cooldown((slot, terminal_fact(
            terminal_state=INVALIDATED, t_terminal=T0)), T=_t(3)),
        authorization=_authorization(T=_t(3)))
    assert cleared.outcomes == ()
    assert cleared.creation_events == ()

    # Only a NEW independently-qualified candidate creates anything.
    fresh = route_candidates_at_boundary(
        [tp_candidate(T=_t(6), anchor=_q(0))], T=_t(6),
        occupancy=V2SlotOccupancyView(as_of=_t(6), active_by_slot={}),
        cooldown=_cooldown((slot, terminal_fact(
            terminal_state=INVALIDATED, t_terminal=T0)), T=_t(6)),
        authorization=_authorization(T=_t(6)))
    assert fresh.outcomes[0].outcome == CREATE_EARLY_SIGNAL
    assert len(fresh.creation_events) == 1


# ============================================================================
# 7. §7.4 — family precedence
# ============================================================================
def test_frozen_precedence_order():
    assert FAMILY_PRECEDENCE == (COMPRESSION_BREAKOUT, CONFIRMED_BREAKOUT, TREND_PULLBACK)


def test_worked_vector_from_the_contract():
    """§7.4.2's own worked example: Compression [100,110], Confirmed
    [105,115], Trend [150,160] -> create Compression, suppress Confirmed,
    create Trend."""
    comp = comp_candidate(lower=100.0, upper=110.0)
    conf = cb_candidate(lower=105.0, upper=115.0)
    trend = tp_candidate(lower=150.0, upper=160.0)
    accepted, suppressed = arbitrate_new_candidates([comp, conf, trend])
    assert [c.setup_family for c in accepted] == [COMPRESSION_BREAKOUT, TREND_PULLBACK]
    assert suppressed[comp.slot] == (conf,)


def test_all_three_overlapping_leaves_only_compression():
    comp = comp_candidate(lower=100.0, upper=110.0)
    conf = cb_candidate(lower=101.0, upper=111.0)
    trend = tp_candidate(lower=102.0, upper=112.0)
    accepted, suppressed = arbitrate_new_candidates([comp, conf, trend])
    assert [c.setup_family for c in accepted] == [COMPRESSION_BREAKOUT]
    assert suppressed[comp.slot] == (conf, trend)     # deterministic precedence order


def test_boundary_touching_regions_overlap():
    """§7.4.1: the predicate uses `<=`, so touching at 110 counts."""
    comp = comp_candidate(lower=100.0, upper=110.0)
    trend = tp_candidate(lower=110.0, upper=120.0)
    accepted, suppressed = arbitrate_new_candidates([comp, trend])
    assert [c.setup_family for c in accepted] == [COMPRESSION_BREAKOUT]
    assert suppressed[comp.slot] == (trend,)


def test_non_overlapping_regions_both_accepted():
    comp = comp_candidate(lower=100.0, upper=109.9)
    trend = tp_candidate(lower=110.0, upper=120.0)
    accepted, suppressed = arbitrate_new_candidates([comp, trend])
    assert len(accepted) == 2
    assert suppressed == {}


def test_opposite_directions_never_suppress_each_other():
    """§7.4: different-direction qualifications are not deduplicated by
    this rule -- that is the separate REVERSAL_CANDIDATE mechanism."""
    long_comp = comp_candidate(direction=LONG, lower=100.0, upper=110.0)
    short_trend = tp_candidate(direction=SHORT, lower=100.0, upper=110.0)
    accepted, suppressed = arbitrate_new_candidates([long_comp, short_trend])
    assert len(accepted) == 2
    assert suppressed == {}


def test_lower_precedence_compared_only_against_accepted_not_all_earlier():
    """§7.4.2 step 4: a candidate is compared against ALREADY-ACCEPTED
    candidates. Trend overlaps the SUPPRESSED Confirmed but not the
    accepted Compression, so Trend is accepted."""
    comp = comp_candidate(lower=100.0, upper=110.0)
    conf = cb_candidate(lower=108.0, upper=130.0)      # overlaps comp -> suppressed
    trend = tp_candidate(lower=120.0, upper=140.0)     # overlaps conf only -> accepted
    accepted, _ = arbitrate_new_candidates([comp, conf, trend])
    assert sorted(c.setup_family for c in accepted) == sorted(
        [COMPRESSION_BREAKOUT, TREND_PULLBACK])


def test_arbitration_is_input_order_independent():
    comp = comp_candidate(lower=100.0, upper=110.0)
    conf = cb_candidate(lower=105.0, upper=115.0)
    trend = tp_candidate(lower=150.0, upper=160.0)
    short_comp = comp_candidate(direction=SHORT, lower=100.0, upper=110.0)
    baseline = None
    for perm in itertools.permutations([comp, conf, trend, short_comp]):
        accepted, suppressed = arbitrate_new_candidates(list(perm))
        signature = (
            tuple(sorted((c.setup_family, c.direction) for c in accepted)),
            tuple(sorted(
                (slot, tuple(sorted(loser.setup_family for loser in losers)))
                for slot, losers in suppressed.items())),
        )
        if baseline is None:
            baseline = signature
        assert signature == baseline, f"permutation changed the outcome: {perm}"


def test_two_candidates_in_one_slot_fail_closed():
    with pytest.raises(V2EpisodeCreationError, match="share slot"):
        arbitrate_new_candidates([tp_candidate(anchor=_q(0)), tp_candidate(anchor=_q(1))])


def test_precedence_does_not_persist_across_boundaries():
    """§7.4.3: precedence arbitrates simultaneous NEW candidates at ONE T;
    it is not a persistent cross-family blocker. At a later T, Trend may
    create even though the Compression episode from T0 is still active."""
    comp = comp_candidate(T=T0, lower=100.0, upper=110.0)
    trend_t0 = tp_candidate(T=T0, lower=105.0, upper=115.0)
    first = route_candidates_at_boundary(
        [comp, trend_t0], T=T0,
        occupancy=V2SlotOccupancyView(as_of=T0, active_by_slot={}),
        cooldown=_cooldown(T=T0), authorization=_authorization(T=T0))
    by_family = {o.candidate.setup_family: o.outcome for o in first.outcomes}
    assert by_family[COMPRESSION_BREAKOUT] == CREATE_EARLY_SIGNAL
    assert by_family[TREND_PULLBACK] == SUPPRESSED_FAMILY_PRECEDENCE

    comp_episode = existing_episode(comp, T=T0)
    later = route_candidates_at_boundary(
        [tp_candidate(T=_t(6), lower=105.0, upper=115.0)], T=_t(6),
        occupancy=_occupancy(comp_episode, T=_t(6)),   # compression still ACTIVE
        cooldown=_cooldown(T=_t(6)), authorization=_authorization(T=_t(6)))
    assert later.outcomes[0].outcome == CREATE_EARLY_SIGNAL


# ============================================================================
# 8. §7.4.2 cadence invariant — Unit 2 never synthesizes a candidate
# ============================================================================
def test_no_trend_pullback_is_invented_at_a_five_minute_only_boundary():
    """`_t(1)` = 12:05 is a legal 5m boundary but not a 15m one, so
    TREND_PULLBACK has no new candidate to submit. Unit 2 arbitrates only
    what Stage 5 actually returned."""
    T = _t(1)
    assert T != _q(0) and (T - T0) % timedelta(minutes=15) != timedelta(0)
    result = route_candidates_at_boundary(
        [comp_candidate(T=T, lower=100.0, upper=110.0)], T=T,
        occupancy=V2SlotOccupancyView(as_of=T, active_by_slot={}),
        cooldown=_cooldown(T=T), authorization=_authorization(T=T))
    assert len(result.outcomes) == 1
    assert result.outcomes[0].candidate.setup_family == COMPRESSION_BREAKOUT
    assert all(o.candidate.setup_family != TREND_PULLBACK for o in result.outcomes)


# ============================================================================
# 9. EARLY_SIGNAL creation
# ============================================================================
def test_creation_event_is_canonical_and_anchored_at_T():
    candidate = tp_candidate(T=T0, anchor=_q(0))
    event = build_early_signal_creation(candidate, authorization=_authorization(T=T0), T=T0)
    assert event.episode_state == EARLY_SIGNAL
    assert event.decision_boundary == T0
    assert len(event.episode_id) == 64 and len(event.event_id) == 64

    history = existing_episode(candidate, T=T0)
    assert history.creation_identity.t_create == T0
    assert history.creation_identity.episode_id == event.episode_id


def test_creation_event_carries_by_value_creation_facts():
    candidate = cb_candidate(T=T0, anchor=_h(0), raw_level=66000.0, buffer=150.0, tick=0.1)
    event = build_early_signal_creation(candidate, authorization=_authorization(T=T0), T=T0)
    facts = event.decision_snapshot[CREATION_FACTS_KEY]
    assert facts["t_detect"] == T0.isoformat()
    assert facts["entry_zone_lower"] == candidate.entry_zone_lower
    assert facts["entry_zone_upper"] == candidate.entry_zone_upper
    assert facts["invalidation_price"] == candidate.invalidation_price
    assert facts["protection_buffer"] == "150"          # exact decimal string
    assert facts["decision_tick_size"] == "0.1"
    assert facts["family_facts"]["level_kind"] == "RESISTANCE"


def test_creation_facts_do_not_duplicate_top_level_identity():
    event = build_early_signal_creation(
        tp_candidate(T=T0, anchor=_q(0)), authorization=_authorization(T=T0), T=T0)
    facts = event.decision_snapshot[CREATION_FACTS_KEY]
    for owned_by_columns in ("symbol", "market_type", "direction", "setup_family",
                            "structural_anchor", "decision_boundary", "episode_id"):
        assert owned_by_columns not in facts


def test_creation_uses_the_resolved_provenance_unchanged():
    auth = _authorization(T=T0)
    event = build_early_signal_creation(
        tp_candidate(T=T0, anchor=_q(0)), authorization=auth, T=T0)
    p = auth.provenance
    assert (event.rules_version, event.calculation_version, event.decision_code_version) == (
        p.rules_version, p.calculation_version, p.decision_code_version)
    assert (event.run_kind, event.run_id) == (p.run_kind, p.run_id)
    assert event.config_hash == p.config_hash and event.code_version == p.code_version


@pytest.mark.parametrize("bad_T", [_t(1), _t(2)])
def test_candidate_cannot_create_at_a_different_boundary(bad_T):
    with pytest.raises(V2EpisodeCreationError, match="does not equal the creation boundary"):
        build_early_signal_creation(
            tp_candidate(T=T0, anchor=_q(0)), authorization=_authorization(T=bad_T), T=bad_T)


# ============================================================================
# 10. §3.1/§3.3/§3.4 creation authorization
# ============================================================================
def test_not_ready_refuses_authorization():
    with pytest.raises(V2EpisodeCreationError, match="NOT_READY"):
        _authorization(ready=False)


def test_dirty_publication_refuses_authorization():
    with pytest.raises(V2EpisodeCreationError, match="publication_clean"):
        _authorization(publication_clean=False)


def test_draining_tuple_cannot_create():
    """§3.1: `active_for_new_creation(state)` is None throughout a drain,
    so neither OLD nor NEW may create."""
    from analytics.forecasting_v2.version_switch import (
        evaluate_version_switch_transition, V2DrainFact, V2VersionSwitchError)
    state = _switch_state(T=T0)
    new_tuple = V2SemanticTuple(
        rules_version=RULES, calculation_version="c" * 16, decision_code_version=DCV)
    draining = evaluate_version_switch_transition(
        state, decision_boundary=_t(1), requested=new_tuple,
        drain_fact=V2DrainFact(
            run_kind=LIVE, run_id=RUN_ID, old_tuple=state.active, as_of=_t(1),
            non_terminal_episode_count=1, active_cooldown_count=0),
        candidate_ready=True).state
    with pytest.raises(V2VersionSwitchError):
        V2CreationAuthorization(
            decision_view=V2DecisionView(
                provenance=_provenance(T=_t(1)), readiness=_readiness(T=_t(1))),
            switch_state=draining, publication_clean=True)


def test_routing_without_authorization_reports_eligible_not_created():
    """RT-64-09: "survived Unit 2 eligibility" and "an authorized episode was
    created" are different facts and get different outcomes."""
    result = route_candidates_at_boundary(
        [tp_candidate(T=T0, anchor=_q(0))], T=T0,
        occupancy=V2SlotOccupancyView(as_of=T0, active_by_slot={}),
        cooldown=_cooldown(T=T0), authorization=None)
    assert result.outcomes[0].outcome == ELIGIBLE_FOR_CREATION
    assert result.outcomes[0].creation_event is None
    assert result.creation_events == ()


# ============================================================================
# 11. §7.4.2 cross-reference aggregated into the winner's ONE event
# ============================================================================
def test_winner_gets_one_event_aggregating_all_precedence_losers():
    comp = comp_candidate(T=T0, lower=100.0, upper=110.0)
    conf = cb_candidate(T=T0, lower=101.0, upper=111.0)
    trend = tp_candidate(T=T0, lower=102.0, upper=112.0)
    result = route_candidates_at_boundary(
        [comp, conf, trend], T=T0,
        occupancy=V2SlotOccupancyView(as_of=T0, active_by_slot={}),
        cooldown=_cooldown(T=T0), authorization=_authorization(T=T0))

    assert len(result.creation_events) == 1
    winner = result.creation_events[0]
    assert winner.setup_family == COMPRESSION_BREAKOUT

    crossref = winner.event_payload[PRECEDENCE_CROSSREF_KEY]
    assert [c["setup_family"] for c in crossref] == [CONFIRMED_BREAKOUT, TREND_PULLBACK]
    assert all(c["reason"] == SUPPRESSED_FAMILY_PRECEDENCE for c in crossref)
    # losers are suppressed CANDIDATES -- never episodes
    assert all("episode_id" not in c for c in crossref)
    losers = [o for o in result.outcomes if o.outcome == SUPPRESSED_FAMILY_PRECEDENCE]
    assert len(losers) == 2
    assert all(o.creation_event is None for o in losers)


def test_crossref_shape_is_input_order_independent():
    comp = comp_candidate(T=T0, lower=100.0, upper=110.0)
    conf = cb_candidate(T=T0, lower=101.0, upper=111.0)
    trend = tp_candidate(T=T0, lower=102.0, upper=112.0)
    signatures = set()
    for perm in itertools.permutations([comp, conf, trend]):
        result = route_candidates_at_boundary(
            list(perm), T=T0,
            occupancy=V2SlotOccupancyView(as_of=T0, active_by_slot={}),
            cooldown=_cooldown(T=T0), authorization=_authorization(T=T0))
        winner = result.creation_events[0]
        signatures.add((
            winner.event_id,
            tuple(c["setup_family"] for c in winner.event_payload[PRECEDENCE_CROSSREF_KEY]),
        ))
    assert len(signatures) == 1


def test_winner_without_losers_carries_no_crossref_key():
    result = route_candidates_at_boundary(
        [comp_candidate(T=T0, lower=100.0, upper=110.0)], T=T0,
        occupancy=V2SlotOccupancyView(as_of=T0, active_by_slot={}),
        cooldown=_cooldown(T=T0), authorization=_authorization(T=T0))
    assert PRECEDENCE_CROSSREF_KEY not in result.creation_events[0].event_payload


# ============================================================================
# 12. restart: classification survives a process boundary
# ============================================================================
def test_classification_after_restart_matches_pre_restart():
    candidate = cb_candidate(T=T0, anchor=_h(0), raw_level=66200.04, buffer=150.0, tick=0.1)
    event = build_early_signal_creation(candidate, authorization=_authorization(T=T0), T=T0)

    later = cb_candidate(T=_t(1), anchor=_h(0), raw_level=66200.04, tick=0.01)
    in_process = classify_candidate_against_active_episode(
        later, existing_episode(candidate, T=T0))

    # A fresh process: only the persisted row survives.
    rebuilt = reconstruct_episode_history(
        [_row(event)], run_kind=LIVE, run_id=RUN_ID, episode_id=event.episode_id,
        as_of=_t(1), boundary_mode=HISTORY_THROUGH_T)
    assert classify_candidate_against_active_episode(later, rebuilt) == in_process == MATCH_EXACT
    assert rebuilt.creation_identity.creation_identity_tick_size == Decimal("0.1")
    assert read_creation_protection_buffer(rebuilt) == Decimal("150")


# ============================================================================
# 13. execution-namespace isolation
# ============================================================================
def test_same_facts_reproduce_the_same_episode_id_across_streams():
    candidate = tp_candidate(T=T0, anchor=_q(0))
    live = build_early_signal_creation(
        candidate, authorization=_authorization(T=T0, run_kind=LIVE, run_id="live-a"), T=T0)
    replay = build_early_signal_creation(
        candidate, authorization=_authorization(T=T0, run_kind="REPLAY", run_id="replay-b"), T=T0)
    assert live.episode_id == replay.episode_id
    assert (live.run_kind, live.run_id) != (replay.run_kind, replay.run_id)


def test_another_streams_active_episode_does_not_suppress_this_stream():
    """Occupancy/cooldown views are built per execution stream; a blocker
    from REPLAY/run-b can never reach LIVE/run-a."""
    replay_episode = existing_episode(
        tp_candidate(anchor=_q(0)), run_kind="REPLAY", run_id="replay-b")
    live_view = V2SlotOccupancyView(as_of=_t(1), active_by_slot={})   # LIVE sees nothing
    result = route_candidates_at_boundary(
        [tp_candidate(T=_t(1), anchor=_q(0))], T=_t(1),
        occupancy=live_view, cooldown=_cooldown(T=_t(1)),
        authorization=_authorization(T=_t(1), run_kind=LIVE, run_id="live-a"))
    assert result.outcomes[0].outcome == CREATE_EARLY_SIGNAL
    assert replay_episode.run_kind == "REPLAY"


# ============================================================================
# 14. malformed / mismatched input fails closed
# ============================================================================
def test_candidate_from_a_different_slot_is_refused():
    active = existing_episode(tp_candidate(anchor=_q(0), direction=LONG))
    with pytest.raises(V2EpisodeCreationError, match="does not match the active episode's slot"):
        classify_candidate_against_active_episode(
            tp_candidate(T=_t(1), anchor=_q(0), direction=SHORT), active)


def test_classifying_against_a_terminal_episode_is_refused():
    active = existing_episode(tp_candidate(anchor=_q(0)))
    row = _row(active.creation_event)
    terminal = dict(row)
    terminal.update(
        episode_state=INVALIDATED, decision_boundary=_t(1),
        event_id=_terminal_event_id(active.episode_id, _t(1)))
    history = reconstruct_episode_history(
        [row, terminal], run_kind=LIVE, run_id=RUN_ID, episode_id=active.episode_id,
        as_of=_t(5), boundary_mode=HISTORY_THROUGH_T)
    with pytest.raises(V2EpisodeCreationError, match="terminal"):
        classify_candidate_against_active_episode(tp_candidate(T=_t(2), anchor=_q(0)), history)


@pytest.mark.parametrize(("field", "value"), [
    ("direction", "SIDEWAYS"),
    ("setup_family", "NOT_A_FAMILY"),
    ("symbol", "ETHUSDT"),
    ("market_type", "spot"),
])
def test_malformed_candidate_scope_is_refused(field, value):
    kwargs = dict(
        symbol="BTCUSDT", market_type="perp", direction=LONG,
        setup_family=TREND_PULLBACK, T=T0, anchor_bucket=T0, raw_level_price=None,
        entry_zone_lower=100.0, entry_zone_upper=110.0, invalidation_price=95.0,
        protection_buffer=50.0, decision_tick_size=0.1, setup_strength=0.5,
        data_confidence=0.9, family_facts={})
    kwargs[field] = value
    with pytest.raises(V2EpisodeCreationError):
        V2CandidateFacts(**kwargs)


def test_inverted_entry_zone_is_refused():
    with pytest.raises(V2EpisodeCreationError, match="entry_zone_lower"):
        tp_candidate(lower=120.0, upper=100.0)


def test_confirmed_breakout_requires_raw_level_price():
    with pytest.raises(V2EpisodeCreationError, match="raw_level_price"):
        V2CandidateFacts(
            symbol="BTCUSDT", market_type="perp", direction=LONG,
            setup_family=CONFIRMED_BREAKOUT, T=T0, anchor_bucket=T0, raw_level_price=None,
            entry_zone_lower=100.0, entry_zone_upper=110.0, invalidation_price=95.0,
            protection_buffer=50.0, decision_tick_size=0.1, setup_strength=0.5,
            data_confidence=0.9, family_facts={})


def test_bucket_only_family_must_not_carry_a_raw_level():
    with pytest.raises(V2EpisodeCreationError, match="bucket-only"):
        V2CandidateFacts(
            symbol="BTCUSDT", market_type="perp", direction=LONG,
            setup_family=TREND_PULLBACK, T=T0, anchor_bucket=T0, raw_level_price=100.0,
            entry_zone_lower=100.0, entry_zone_upper=110.0, invalidation_price=95.0,
            protection_buffer=50.0, decision_tick_size=0.1, setup_strength=0.5,
            data_confidence=0.9, family_facts={})


def test_view_resolved_for_another_boundary_is_refused():
    with pytest.raises(V2EpisodeCreationError, match="views are fixed at THIS boundary"):
        route_candidates_at_boundary(
            [tp_candidate(T=_t(1), anchor=_q(0))], T=_t(1),
            occupancy=V2SlotOccupancyView(as_of=T0, active_by_slot={}),
            cooldown=_cooldown(T=_t(1)), authorization=None)


def test_candidate_from_another_boundary_is_refused():
    with pytest.raises(V2EpisodeCreationError, match="does not equal the decision boundary"):
        route_candidates_at_boundary(
            [tp_candidate(T=T0, anchor=_q(0))], T=_t(1),
            occupancy=V2SlotOccupancyView(as_of=_t(1), active_by_slot={}),
            cooldown=_cooldown(T=_t(1)), authorization=None)


# ============================================================================
# 15. architecture guard
# ============================================================================
def test_unit2_never_constructs_v2_episode_event_directly():
    """The canonical construction path stays singular: this module must
    reach `V2EpisodeEvent` only through `build_v2_episode_event()`."""
    import ast
    import pathlib

    # Located relative to THIS file, never the process working directory:
    # a cwd-relative path silently resolves to a non-existent file (or, worse,
    # a different repo's copy) depending on where pytest was invoked from.
    source = (
        pathlib.Path(__file__).resolve().parents[2]
        / "analytics" / "forecasting_v2" / "episode_creation.py")
    assert source.is_file(), f"architecture guard could not locate {source}"
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        called = (
            func.id if isinstance(func, ast.Name)
            else func.attr if isinstance(func, ast.Attribute) else None)
        if called == "V2EpisodeEvent":
            offenders.append(node.lineno)
    assert offenders == []


# ============================================================================
# 16. amendment regressions — integrity hardening (RT-64-01..12, CR64-1..5)
# ============================================================================
# ---- §12.1 candidate structural-anchor family grid (RT-64-01/02/03, CR64-1)
@pytest.mark.parametrize("offset", [
    timedelta(minutes=15),                  # legal 15m start, illegal 1h start
    timedelta(minutes=30),
    timedelta(minutes=45),
    timedelta(seconds=1),
    timedelta(microseconds=1),
])
def test_confirmed_breakout_anchor_must_be_an_exact_1h_bucket_start(offset):
    """§12.1 gives CONFIRMED_BREAKOUT a 1h `level_anchor_bucket`. A 15m/30m/
    45m/sub-second value is malformed input, never something that falls
    through into §12.4's price-drift branch."""
    with pytest.raises(V2EpisodeCreationError, match="structural anchor"):
        cb_candidate(anchor=T0 + offset)


def test_confirmed_breakout_legal_hour_anchors_are_accepted():
    for n in (0, 1, 5):
        assert cb_candidate(anchor=_h(n)).anchor_bucket == _h(n)


def test_confirmed_breakout_naive_anchor_is_rejected():
    with pytest.raises(V2EpisodeCreationError, match="structural anchor"):
        cb_candidate(anchor=T0.replace(tzinfo=None))


@pytest.mark.parametrize("make", [tp_candidate, comp_candidate])
@pytest.mark.parametrize("offset", [
    timedelta(minutes=7),
    timedelta(minutes=1),
    timedelta(seconds=1),
    timedelta(microseconds=1),
])
def test_bucket_anchored_families_require_an_exact_15m_bucket_start(make, offset):
    with pytest.raises(V2EpisodeCreationError, match="structural anchor"):
        make(anchor=T0 + offset)


@pytest.mark.parametrize("make", [tp_candidate, comp_candidate])
def test_bucket_anchored_families_accept_legal_15m_starts(make):
    for n in (0, 1, 7):
        assert make(anchor=_q(n)).anchor_bucket == _q(n)


@pytest.mark.parametrize("make", [tp_candidate, comp_candidate, cb_candidate])
def test_naive_anchor_never_leaks_a_raw_type_error(make):
    """RT-64-02: a naive anchor used to reach `abs(C - A)` and escape as a
    bare `TypeError` from aware/naive subtraction."""
    with pytest.raises(V2EpisodeCreationError) as excinfo:
        make(anchor=T0.replace(tzinfo=None))
    assert not isinstance(excinfo.value, TypeError)


@pytest.mark.parametrize("make", [tp_candidate, comp_candidate, cb_candidate])
def test_non_utc_anchor_is_rejected(make):
    with pytest.raises(V2EpisodeCreationError, match="structural anchor"):
        make(anchor=T0.astimezone(timezone(timedelta(hours=2))))


def test_off_grid_confirmed_breakout_anchor_never_reaches_price_drift():
    """RT-64-01's exact attack: an off-grid CB anchor used to be classified
    NON_MATERIAL on price alone. It must now be impossible to even build."""
    active = existing_episode(cb_candidate(anchor=_h(0), raw_level=66200.04, tick=0.1))
    with pytest.raises(V2EpisodeCreationError, match="structural anchor"):
        classify_candidate_against_active_episode(
            cb_candidate(T=_t(1), anchor=_h(0) + timedelta(minutes=15), raw_level=66200.04),
            active)


# ---- RT-64-04 / CR64-2: persisted anchor parse stays in this hierarchy -----
def _identity_with_anchor(base, **anchor_over):
    from analytics.forecasting_v2.episode_history import V2EpisodeCreationIdentity
    identity = base.creation_identity
    anchor = dict(identity.structural_anchor)
    anchor.update(anchor_over)
    return V2EpisodeCreationIdentity(
        episode_id=identity.episode_id, t_create=identity.t_create,
        model_family=identity.model_family, rules_version=identity.rules_version,
        calculation_version=identity.calculation_version, symbol=identity.symbol,
        market_type=identity.market_type, direction=identity.direction,
        setup_family=identity.setup_family, structural_anchor=anchor)


@pytest.mark.parametrize("raw", ["not-a-timestamp", "", "2026-13-99T00:00:00+00:00"])
def test_malformed_persisted_anchor_parse_stays_in_the_domain_error(raw):
    from analytics.forecasting_v2.episode_creation import _creation_anchor_bucket
    identity = _identity_with_anchor(existing_episode(tp_candidate(anchor=_q(0))), bucket_ts=raw)
    with pytest.raises(V2EpisodeCreationError) as excinfo:
        _creation_anchor_bucket(identity)
    assert not isinstance(excinfo.value, (TypeError,))
    assert excinfo.value.__cause__ is not None


def test_off_grid_persisted_anchor_stays_in_the_domain_error():
    from analytics.forecasting_v2.episode_creation import _creation_anchor_bucket
    identity = _identity_with_anchor(
        existing_episode(tp_candidate(anchor=_q(0))),
        bucket_ts=(T0 + timedelta(minutes=7)).isoformat())
    with pytest.raises(V2EpisodeCreationError, match="structural anchor"):
        _creation_anchor_bucket(identity)


def test_naive_persisted_anchor_cannot_leak_a_type_error():
    from analytics.forecasting_v2.episode_creation import _creation_anchor_bucket
    identity = _identity_with_anchor(
        existing_episode(tp_candidate(anchor=_q(0))), bucket_ts="2026-08-20T12:00:00")
    with pytest.raises(V2EpisodeCreationError):
        _creation_anchor_bucket(identity)


# ---- RT-64-06: occupancy key must be the episode's own slot ---------------
def test_occupancy_history_keyed_under_a_foreign_slot_is_rejected():
    active = existing_episode(tp_candidate(anchor=_q(0), direction=LONG))
    with pytest.raises(V2EpisodeCreationError, match="filed under a foreign slot"):
        V2SlotOccupancyView(
            as_of=T0,
            active_by_slot={("BTCUSDT", "perp", SHORT, TREND_PULLBACK): [active]})


def test_mis_keyed_occupancy_cannot_make_the_real_slot_appear_empty():
    """RT-64-06's exact attack: a LONG TP episode filed under the SHORT TP
    key would let a second LONG TP episode be created."""
    active = existing_episode(tp_candidate(anchor=_q(0), direction=LONG))
    with pytest.raises(V2EpisodeCreationError, match="filed under a foreign slot"):
        route_candidates_at_boundary(
            [tp_candidate(T=_t(1), anchor=_q(0), direction=LONG)], T=_t(1),
            occupancy=V2SlotOccupancyView(
                as_of=_t(1),
                active_by_slot={("BTCUSDT", "perp", SHORT, TREND_PULLBACK): [active]}),
            cooldown=_cooldown(T=_t(1)), authorization=_authorization(T=_t(1)))


def test_occupancy_from_histories_keys_by_the_episodes_own_slot():
    long_tp = existing_episode(tp_candidate(anchor=_q(0), direction=LONG))
    short_tp = existing_episode(tp_candidate(anchor=_q(0), direction=SHORT))
    view = V2SlotOccupancyView.from_histories(as_of=T0, histories=[long_tp, short_tp])
    assert view.active_episode(("BTCUSDT", "perp", LONG, TREND_PULLBACK)) is long_tp
    assert view.active_episode(("BTCUSDT", "perp", SHORT, TREND_PULLBACK)) is short_tp


# ---- RT-64-07 / RT-64-11: cooldown facts are proven, and slot-bound -------
def test_terminal_fact_requires_a_reconstructed_history():
    with pytest.raises(V2EpisodeCreationError, match="reconstructed through Unit 1"):
        V2SlotTerminalFact(history={"episode_state": INVALIDATED})


def test_terminal_fact_refuses_a_non_terminal_history():
    with pytest.raises(V2EpisodeCreationError, match="not a terminal state"):
        V2SlotTerminalFact(history=existing_episode(tp_candidate(anchor=_q(0))))


def test_malformed_full_history_cannot_become_a_trusted_cooldown_fact():
    """RT-64-11: a latest-row summary of an IMPOSSIBLE history used to look
    like a valid terminal fact. Unit 1 rejects the history outright, so
    there is nothing to wrap."""
    candidate = tp_candidate(T=T0, anchor=_q(0))
    creation = build_early_signal_creation(
        candidate, authorization=_authorization(T=T0), T=T0)
    # §13.2 gives terminal states no outgoing edges: INVALIDATED -> CONFIRMED
    # is impossible history, yet its LATEST row alone reads as CONFIRMED and
    # its earlier row alone reads as a clean terminal fact.
    rows = [
        _row(creation),
        _row(_follow_up(creation, episode_state=INVALIDATED,
                        decision_boundary=_t(1), t_create=T0)),
        _row(_follow_up(creation, episode_state=CONFIRMED,
                        decision_boundary=_t(2), t_create=T0)),
    ]
    with pytest.raises(V2EpisodeHistoryCorruptionError):
        reconstruct_episode_history(
            rows, run_kind=LIVE, run_id=RUN_ID, episode_id=creation.episode_id,
            as_of=_t(50), boundary_mode=HISTORY_THROUGH_T)


def test_terminal_fact_filed_under_a_foreign_slot_is_rejected():
    fact = terminal_fact(terminal_state=INVALIDATED, t_terminal=T0, direction=LONG)
    assert fact.slot == ("BTCUSDT", "perp", LONG, TREND_PULLBACK)
    with pytest.raises(V2EpisodeCreationError, match="may only serve the slot"):
        V2SlotCooldownView(
            as_of=T0,
            terminal_by_slot={("BTCUSDT", "perp", SHORT, TREND_PULLBACK): fact})


def test_wrong_slot_terminal_fact_cannot_suppress_a_foreign_candidate():
    fact = terminal_fact(terminal_state=INVALIDATED, t_terminal=T0, direction=LONG)
    with pytest.raises(V2EpisodeCreationError, match="may only serve the slot"):
        route_candidates_at_boundary(
            [tp_candidate(T=T0, anchor=_q(0), direction=SHORT)], T=T0,
            occupancy=V2SlotOccupancyView(as_of=T0, active_by_slot={}),
            cooldown=V2SlotCooldownView(
                as_of=T0,
                terminal_by_slot={("BTCUSDT", "perp", SHORT, TREND_PULLBACK): fact}),
            authorization=_authorization(T=T0))


def test_cooldown_view_from_histories_keys_by_the_episodes_own_slot():
    long_terminal = terminal_history(terminal_state=INVALIDATED, t_terminal=T0, direction=LONG)
    short_terminal = terminal_history(terminal_state=EXPIRED, t_terminal=T0, direction=SHORT)
    view = V2SlotCooldownView.from_terminal_histories(
        as_of=T0, histories=[long_terminal, short_terminal])
    assert view.most_recent_terminal(
        ("BTCUSDT", "perp", LONG, TREND_PULLBACK)).terminal_state == INVALIDATED
    assert view.most_recent_terminal(
        ("BTCUSDT", "perp", SHORT, TREND_PULLBACK)).terminal_state == EXPIRED


def test_two_terminal_histories_in_one_slot_fail_closed():
    """The domain twin of the reader's RT-64-10 guard: no invented tie-break
    when one slot is handed two terminal episodes."""
    a = terminal_history(terminal_state=INVALIDATED, t_terminal=T0, anchor=_q(0))
    b = terminal_history(terminal_state=COMPLETED, t_terminal=T0, anchor=_q(1))
    assert a.episode_id != b.episode_id
    with pytest.raises(V2EpisodeCreationError, match="two terminal episodes"):
        V2SlotCooldownView.from_terminal_histories(as_of=T0, histories=[a, b])


# ---- RT-64-09 / §6: ELIGIBLE is not CREATED -------------------------------
def test_every_create_outcome_carries_a_canonical_creation_event():
    result = route_candidates_at_boundary(
        [comp_candidate(T=T0, anchor=_q(0), lower=100.0, upper=110.0),
         tp_candidate(T=T0, anchor=_q(0), lower=105.0, upper=115.0),
         cb_candidate(T=T0, anchor=_h(0), lower=200.0, upper=210.0)],
        T=T0, occupancy=V2SlotOccupancyView(as_of=T0, active_by_slot={}),
        cooldown=_cooldown(T=T0), authorization=_authorization(T=T0))
    created = [o for o in result.outcomes if o.outcome == CREATE_EARLY_SIGNAL]
    assert created, "fixture must produce at least one winner"
    for outcome in created:
        assert outcome.creation_event is not None
        assert outcome.creation_event.episode_state == EARLY_SIGNAL
    assert len(result.creation_events) == len(created)
    assert all(event is not None for event in result.creation_events)


def test_create_early_signal_outcome_without_an_event_is_impossible():
    with pytest.raises(V2EpisodeCreationError, match="requires 'creation_event'"):
        V2CandidateOutcome(candidate=tp_candidate(), outcome=CREATE_EARLY_SIGNAL)


def test_eligible_outcome_must_not_carry_an_event():
    event = build_early_signal_creation(
        tp_candidate(T=T0, anchor=_q(0)), authorization=_authorization(T=T0), T=T0)
    with pytest.raises(V2EpisodeCreationError, match="must not carry 'creation_event'"):
        V2CandidateOutcome(
            candidate=tp_candidate(), outcome=ELIGIBLE_FOR_CREATION, creation_event=event)


# ---- §6: outcome field invariants ----------------------------------------
@pytest.mark.parametrize(("outcome", "field"), [
    (ROUTE_EXISTING_EXACT, "routed_episode_id"),
    (ROUTE_EXISTING_NON_MATERIAL, "routed_episode_id"),
    (SUPPRESSED_ACTIVE_SLOT, "blocking_episode_id"),
    (SUPPRESSED_COOLDOWN, "blocking_episode_id"),
    (SUPPRESSED_COOLDOWN, "cooldown_until"),
    (SUPPRESSED_FAMILY_PRECEDENCE, "suppressed_by_slot"),
    (CREATE_EARLY_SIGNAL, "creation_event"),
])
def test_outcome_requires_its_own_field(outcome, field):
    kwargs = {
        "routed_episode_id": "e" * 64, "blocking_episode_id": "f" * 64,
        "cooldown_until": _t(3), "suppressed_by_slot": comp_candidate().slot,
        "creation_event": build_early_signal_creation(
            tp_candidate(T=T0, anchor=_q(0)), authorization=_authorization(T=T0), T=T0),
        "match_class": {
            ROUTE_EXISTING_EXACT: MATCH_EXACT,
            ROUTE_EXISTING_NON_MATERIAL: MATCH_NON_MATERIAL,
            SUPPRESSED_ACTIVE_SLOT: MATCH_MATERIAL,
        }.get(outcome),
    }
    required = {
        ROUTE_EXISTING_EXACT: ("routed_episode_id",),
        ROUTE_EXISTING_NON_MATERIAL: ("routed_episode_id",),
        SUPPRESSED_ACTIVE_SLOT: ("blocking_episode_id",),
        SUPPRESSED_COOLDOWN: ("blocking_episode_id", "cooldown_until"),
        SUPPRESSED_FAMILY_PRECEDENCE: ("suppressed_by_slot",),
        CREATE_EARLY_SIGNAL: ("creation_event",),
    }[outcome]
    complete = {k: v for k, v in kwargs.items() if k in required or k == "match_class"}
    # Complete is fine ...
    V2CandidateOutcome(candidate=tp_candidate(), outcome=outcome, **complete)
    # ... and dropping the field under test is not.
    del complete[field]
    with pytest.raises(V2EpisodeCreationError, match=f"requires {field!r}"):
        V2CandidateOutcome(candidate=tp_candidate(), outcome=outcome, **complete)


def test_outcome_rejects_a_field_belonging_to_another_outcome():
    with pytest.raises(V2EpisodeCreationError, match="must not carry 'cooldown_until'"):
        V2CandidateOutcome(
            candidate=tp_candidate(), outcome=ROUTE_EXISTING_EXACT,
            match_class=MATCH_EXACT, routed_episode_id="e" * 64, cooldown_until=_t(3))


def test_outcome_rejects_material_classification_on_a_route():
    """MATCH_MATERIAL is §12.3 case C: the case that EXCLUDES routing."""
    with pytest.raises(V2EpisodeCreationError, match="reachable only from §12.3 class"):
        V2CandidateOutcome(
            candidate=tp_candidate(), outcome=ROUTE_EXISTING_EXACT,
            match_class=MATCH_MATERIAL, routed_episode_id="e" * 64)


def test_outcome_rejects_a_match_class_on_a_non_classified_outcome():
    with pytest.raises(V2EpisodeCreationError, match="not reached through §12.3"):
        V2CandidateOutcome(
            candidate=tp_candidate(), outcome=SUPPRESSED_FAMILY_PRECEDENCE,
            match_class=MATCH_EXACT, suppressed_by_slot=comp_candidate().slot)


def test_outcome_rejects_a_non_candidate():
    with pytest.raises(V2EpisodeCreationError, match="must be a V2CandidateFacts"):
        V2CandidateOutcome(candidate="not a candidate", outcome=ELIGIBLE_FOR_CREATION)


def test_outcome_rejects_an_off_grid_cooldown_until():
    with pytest.raises(V2EpisodeCreationError, match="5m decision boundary"):
        V2CandidateOutcome(
            candidate=tp_candidate(), outcome=SUPPRESSED_COOLDOWN,
            blocking_episode_id="e" * 64, cooldown_until=T0 + timedelta(minutes=2))


# ---- §7: boundary routing result integrity --------------------------------
def test_routing_result_rejects_an_illegal_boundary():
    with pytest.raises(V2EpisodeCreationError, match="5m decision boundary"):
        V2BoundaryRoutingResult(T=T0 + timedelta(minutes=2), outcomes=())


def test_routing_result_rejects_an_outcome_from_another_boundary():
    outcome = V2CandidateOutcome(
        candidate=tp_candidate(T=_t(3), anchor=_q(0)), outcome=ELIGIBLE_FOR_CREATION)
    with pytest.raises(V2EpisodeCreationError, match="does not belong to boundary"):
        V2BoundaryRoutingResult(T=T0, outcomes=(outcome,))


def test_routing_result_rejects_two_outcomes_for_one_slot():
    outcome = V2CandidateOutcome(
        candidate=tp_candidate(T=T0, anchor=_q(0)), outcome=ELIGIBLE_FOR_CREATION)
    with pytest.raises(V2EpisodeCreationError, match="more than one outcome"):
        V2BoundaryRoutingResult(T=T0, outcomes=(outcome, outcome))


def test_routing_result_rejects_non_outcomes():
    with pytest.raises(V2EpisodeCreationError, match="must contain V2CandidateOutcome"):
        V2BoundaryRoutingResult(T=T0, outcomes=("junk",))


def test_routing_result_freezes_its_outcomes():
    result = V2BoundaryRoutingResult(T=T0, outcomes=[])
    assert isinstance(result.outcomes, tuple)


# ---- RT-64-05 / CR64-3: duplicate same-slot candidate input ---------------
def test_duplicate_same_slot_candidates_fail_closed_before_any_routing():
    with pytest.raises(V2EpisodeCreationError, match="two candidates share slot"):
        route_candidates_at_boundary(
            [tp_candidate(T=T0, anchor=_q(0)), tp_candidate(T=T0, anchor=_q(1))],
            T=T0, occupancy=V2SlotOccupancyView(as_of=T0, active_by_slot={}),
            cooldown=_cooldown(T=T0), authorization=_authorization(T=T0))


def test_duplicate_same_slot_candidates_fail_closed_on_the_route_path():
    """Previously produced TWO ROUTE outcomes for one slot at one `T`."""
    active = existing_episode(tp_candidate(anchor=_q(0)))
    with pytest.raises(V2EpisodeCreationError, match="two candidates share slot"):
        route_candidates_at_boundary(
            [tp_candidate(T=_t(1), anchor=_q(0)), tp_candidate(T=_t(1), anchor=_q(1))],
            T=_t(1), occupancy=_occupancy(active, T=_t(1)),
            cooldown=_cooldown(T=_t(1)), authorization=_authorization(T=_t(1)))


def test_duplicate_same_slot_candidates_fail_closed_on_the_cooldown_path():
    """Previously produced TWO SUPPRESSED_COOLDOWN outcomes for one slot."""
    slot = tp_candidate().slot
    with pytest.raises(V2EpisodeCreationError, match="two candidates share slot"):
        route_candidates_at_boundary(
            [tp_candidate(T=T0, anchor=_q(0)), tp_candidate(T=T0, anchor=_q(1))],
            T=T0, occupancy=V2SlotOccupancyView(as_of=T0, active_by_slot={}),
            cooldown=_cooldown(
                (slot, terminal_fact(terminal_state=INVALIDATED, t_terminal=T0)), T=T0),
            authorization=_authorization(T=T0))


def test_distinct_slots_are_still_routed_together():
    """The duplicate guard must not affect legitimate multi-slot batches."""
    result = route_candidates_at_boundary(
        [tp_candidate(T=T0, anchor=_q(0), direction=LONG, lower=100.0, upper=110.0),
         tp_candidate(T=T0, anchor=_q(0), direction=SHORT, lower=100.0, upper=110.0)],
        T=T0, occupancy=V2SlotOccupancyView(as_of=T0, active_by_slot={}),
        cooldown=_cooldown(T=T0), authorization=_authorization(T=T0))
    assert [o.outcome for o in result.outcomes] == [CREATE_EARLY_SIGNAL] * 2
    assert len(result.creation_events) == 2


# ---- RT-64-12: nested immutability ---------------------------------------
def test_nested_family_facts_cannot_be_mutated_after_construction():
    nested = {"levels": [1.0, 2.0], "meta": {"kind": "RESISTANCE"}}
    candidate = V2CandidateFacts(
        symbol="BTCUSDT", market_type="perp", direction=LONG,
        setup_family=TREND_PULLBACK, T=T0, anchor_bucket=_q(0), raw_level_price=None,
        entry_zone_lower=100.0, entry_zone_upper=110.0, invalidation_price=95.0,
        protection_buffer=50.0, decision_tick_size=0.1, setup_strength=0.7,
        data_confidence=0.9, family_facts=nested)

    assert candidate.family_facts["levels"] == (1.0, 2.0)
    with pytest.raises((AttributeError, TypeError)):
        candidate.family_facts["levels"].append(99.0)
    with pytest.raises(TypeError):
        candidate.family_facts["meta"]["kind"] = "MUTATED"

    # Mutating the ORIGINAL dict must not reach the candidate either.
    nested["levels"].append(99.0)
    nested["meta"]["kind"] = "MUTATED"
    assert candidate.family_facts["levels"] == (1.0, 2.0)
    assert candidate.family_facts["meta"]["kind"] == "RESISTANCE"


def test_non_json_family_facts_are_rejected():
    with pytest.raises(V2EpisodeCreationError, match="not JSON-shaped"):
        tp_candidate_with_facts = V2CandidateFacts(
            symbol="BTCUSDT", market_type="perp", direction=LONG,
            setup_family=TREND_PULLBACK, T=T0, anchor_bucket=_q(0), raw_level_price=None,
            entry_zone_lower=100.0, entry_zone_upper=110.0, invalidation_price=95.0,
            protection_buffer=50.0, decision_tick_size=0.1, setup_strength=0.7,
            data_confidence=0.9, family_facts={"bad": {1, 2}})
        assert tp_candidate_with_facts is None


def test_deeply_frozen_family_facts_still_reach_the_creation_event():
    candidate = V2CandidateFacts(
        symbol="BTCUSDT", market_type="perp", direction=LONG,
        setup_family=TREND_PULLBACK, T=T0, anchor_bucket=_q(0), raw_level_price=None,
        entry_zone_lower=100.0, entry_zone_upper=110.0, invalidation_price=95.0,
        protection_buffer=50.0, decision_tick_size=0.1, setup_strength=0.7,
        data_confidence=0.9, family_facts={"levels": [1.0, 2.0]})
    event = build_early_signal_creation(
        candidate, authorization=_authorization(T=T0), T=T0)
    facts = event.decision_snapshot[CREATION_FACTS_KEY]["family_facts"]
    assert facts["levels"] == (1.0, 2.0)
