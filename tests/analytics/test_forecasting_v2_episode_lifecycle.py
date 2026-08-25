"""Pure-domain tests for Stage 6 Unit 3 — `EARLY_SIGNAL` lifecycle
resolution (`analytics/forecasting_v2/episode_lifecycle.py`).

No database. Every episode under test is created by persisting a REAL Unit
2 `EARLY_SIGNAL` creation event and reading it back through Unit 1's
`reconstruct_episode_history()`, and every subsequent lifecycle event is
built through Unit 3's own canonical factory path and re-read the same way
— so every vector runs against exactly the persisted shape a restart sees,
never a hand-assembled in-memory stand-in.
"""
from __future__ import annotations

import pathlib
from datetime import datetime, timedelta, timezone

import pytest

from analytics.forecasting_v2.activation_readiness import (
    MANDATORY_PERCENTILE_COVERAGE, V2ActivationReadinessResult, V2CoverageStatus,
)
from analytics.forecasting_v2.decision_provenance import V2DecisionProvenance
from analytics.forecasting_v2.decision_view import V2DecisionView
from analytics.forecasting_v2.aligned_inputs import V2_REFERENCE_EXCHANGE
from analytics.forecasting_v2.alignment import TIMEFRAME_MINUTES, selected_bucket
from analytics.forecasting_v2.episode_creation import (
    V2CandidateFacts, V2CreationAuthorization, build_early_signal_creation,
)
from analytics.forecasting_v2.episode_history import (
    HISTORY_THROUGH_T, reconstruct_episode_history,
)
from analytics.forecasting_v2.episode_lifecycle import (
    CANDIDATE_MAX_AGE, LIFECYCLE_CONFIRMED, LIFECYCLE_EXPIRED_CANDIDATE_AGE,
    LIFECYCLE_INVALIDATED_FALSE_BREAK, LIFECYCLE_NO_CHANGE,
    LIFECYCLE_PRECONFIRMATION_UPDATE, LIFECYCLE_EVIDENCE_KEY, LIFECYCLE_TRANSITION_KEY,
    OPERATIONAL_FACTS_KEY, OPERATIONAL_SOURCE_CONFIRMATION, OPERATIONAL_SOURCE_CREATION,
    OPERATIONAL_SOURCE_REEVALUATION, REQUIRED_METRIC_FAMILY, RESUMPTION_MIN_AGREEMENT,
    SIGNAL_CONFIRM, SIGNAL_FALSE_BREAK, SIGNAL_HOLD, SIGNAL_REJECTED, SIGNAL_UNAVAILABLE,
    V2BoundaryFacts, V2EpisodeLifecycleError, V2LifecycleAuthorization,
    V2LifecycleDecision, V2TrendPullbackReevaluationWindow,
    build_episode_transition_event, derive_trend_pullback_reevaluation,
    evaluate_early_signal_transition, evaluate_family_signal, read_candidate_deadline,
    read_detection_boundary, read_operational_facts,
)
from analytics.forecasting_v2.events import (
    COMPRESSION_BREAKOUT, CONFIRMED, CONFIRMED_BREAKOUT, EARLY_SIGNAL, EXPIRED,
    INVALIDATED, LIVE, LONG, REPLAY, SHORT, TREND_PULLBACK,
)
from analytics.forecasting_v2.version_switch import (
    V2SemanticTuple, V2DrainFact, V2VersionSwitchError, active_for_new_creation,
    assert_provenance_authorized_for_new_creation, evaluate_version_switch_transition,
    initial_switch_state, provision_initial_tuple,
)
from common.v2_config import MODEL_FAMILY

UTC = timezone.utc
# A legal 5m, 15m, 1h and 4h boundary — every family's grid at once.
T0 = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
H64 = "a" * 64
H16 = "b" * 16
RULES = "v2-rules-v0.1.0"
DCV = "decision-code-1"
RUN_ID = "live-stream-1"
SYMBOL, MARKET = "BTCUSDT", "perp"
# Every TREND_PULLBACK fixture's frozen creation structural anchor
# (`trend_leg_extreme.bucket_ts`) -- the one bucket §7.1's retracement span
# must start from.
_TP_ANCHOR = T0 - timedelta(minutes=60)
# Span fillers that can never themselves be the retracement extreme: a LONG
# extreme is the span MINIMUM, a SHORT extreme is its MAXIMUM.
_LONG_FILLER, _SHORT_FILLER = 500.0, 1.0


def _t(n: int) -> datetime:
    """`n` 5m decision boundaries after T0 (negative goes back)."""
    return T0 + timedelta(minutes=5 * n)


def _q(n: int) -> datetime:
    """`n` 15m buckets after T0."""
    return T0 + timedelta(minutes=15 * n)


def _h(n: int) -> datetime:
    """`n` 1h buckets after T0."""
    return T0 + timedelta(hours=n)


# ---- provenance / authorization fixtures ------------------------------------
def _provenance(*, T=T0, run_kind=LIVE, run_id=RUN_ID, **over) -> V2DecisionProvenance:
    base = dict(
        run_kind=run_kind, run_id=run_id, decision_boundary=T, symbol=SYMBOL,
        market_type=MARKET, model_family=MODEL_FAMILY, rules_version=RULES,
        feature_schema_version=1, calculation_version=H16, config_hash=H64,
        config_version="2.1.0", code_version="feat-code-1", decision_code_version=DCV,
    )
    base.update(over)
    return V2DecisionProvenance(**base)


def _readiness(*, T=T0, ready=True) -> V2ActivationReadinessResult:
    statuses = tuple(
        V2CoverageStatus(requirement=req, ready=ready, reason="fixture", latest_bucket_ts=T)
        for req in MANDATORY_PERCENTILE_COVERAGE)
    return V2ActivationReadinessResult(
        symbol=SYMBOL, market_type=MARKET, calculation_version=H16,
        decision_boundary=T, ready=ready, statuses=statuses)


def _switch_state(*, T=T0, run_kind=LIVE, run_id=RUN_ID, tuple_=None):
    state = initial_switch_state(run_kind=run_kind, run_id=run_id)
    tuple_ = tuple_ or V2SemanticTuple(
        rules_version=RULES, calculation_version=H16, decision_code_version=DCV)
    return provision_initial_tuple(
        state, decision_boundary=T, tuple_=tuple_, candidate_ready=True).state


def _creation_authorization(*, T=T0, run_kind=LIVE, run_id=RUN_ID) -> V2CreationAuthorization:
    return V2CreationAuthorization(
        decision_view=V2DecisionView(
            provenance=_provenance(T=T, run_kind=run_kind, run_id=run_id),
            readiness=_readiness(T=T)),
        switch_state=_switch_state(T=T, run_kind=run_kind, run_id=run_id),
        publication_clean=True)


def _authorization(*, T=T0, run_kind=LIVE, run_id=RUN_ID, **over) -> V2LifecycleAuthorization:
    return V2LifecycleAuthorization(
        provenance=_provenance(T=T, run_kind=run_kind, run_id=run_id, **over),
        publication_clean=True)


# ---- candidate fixtures -----------------------------------------------------
def tp_candidate(*, T=T0, anchor=None, direction=LONG, pullback_extreme=None,
                 current_close=105.0, buffer=2.0, tick=0.1) -> V2CandidateFacts:
    """A §7.1-shaped TREND_PULLBACK candidate.

    LONG:  zone `[pullback_extreme_low, current_close]`, invalidation
           `extreme - buffer` (the retracement dipped BELOW the close).
    SHORT: zone `[current_close, pullback_extreme_high]`, invalidation
           `extreme + buffer` (the retracement rose ABOVE the close)."""
    if pullback_extreme is None:
        pullback_extreme = 100.0 if direction == LONG else 110.0
    if direction == LONG:
        lower, upper, invalidation = pullback_extreme, current_close, pullback_extreme - buffer
    else:
        lower, upper, invalidation = current_close, pullback_extreme, pullback_extreme + buffer
    return V2CandidateFacts(
        symbol=SYMBOL, market_type=MARKET, direction=direction,
        setup_family=TREND_PULLBACK, T=T,
        anchor_bucket=anchor if anchor is not None else _TP_ANCHOR, raw_level_price=None,
        entry_zone_lower=lower, entry_zone_upper=upper, invalidation_price=invalidation,
        protection_buffer=buffer, decision_tick_size=tick,
        setup_strength=0.7, data_confidence=0.9,
        family_facts={
            "bucket_15m": (T - timedelta(minutes=15)).isoformat(),
            "pullback_extreme": pullback_extreme,
            "retracement_pct": 1.2, "range_proxy_pct": 0.8,
        })


def comp_candidate(*, T=T0, anchor=None, direction=LONG, range_low=90.0,
                   range_high=100.0, buffer=2.0, tick=0.1) -> V2CandidateFacts:
    """A §7.2-shaped COMPRESSION_BREAKOUT candidate. LONG broke above
    `range_high`; zone is `[range_high, range_high + buffer]`."""
    if direction == LONG:
        lower, upper, invalidation = range_high, range_high + buffer, range_low - buffer
    else:
        lower, upper, invalidation = range_low - buffer, range_low, range_high + buffer
    return V2CandidateFacts(
        symbol=SYMBOL, market_type=MARKET, direction=direction,
        setup_family=COMPRESSION_BREAKOUT, T=T,
        anchor_bucket=anchor if anchor is not None else _q(-8), raw_level_price=None,
        entry_zone_lower=lower, entry_zone_upper=upper, invalidation_price=invalidation,
        protection_buffer=buffer, decision_tick_size=tick,
        setup_strength=0.8, data_confidence=0.9,
        family_facts={
            "compression_start_bucket": _q(-8).isoformat(),
            "compression_end_bucket": _q(-2).isoformat(),
            "compression_length": 6,
            "range_low": range_low, "range_high": range_high,
            "breakout_close": range_high + 0.5,
        })


def cb_candidate(*, T=T0, anchor=None, direction=LONG, level=100.0,
                 buffer=2.0, tick=0.1) -> V2CandidateFacts:
    """A §7.3-shaped CONFIRMED_BREAKOUT candidate; `level` is the frozen
    `resistance_level` (LONG) / `support_level` (SHORT)."""
    if direction == LONG:
        lower, upper, invalidation = level, level + buffer, level - buffer
    else:
        lower, upper, invalidation = level - buffer, level, level + buffer
    return V2CandidateFacts(
        symbol=SYMBOL, market_type=MARKET, direction=direction,
        setup_family=CONFIRMED_BREAKOUT, T=T,
        anchor_bucket=anchor if anchor is not None else _h(-4), raw_level_price=level,
        entry_zone_lower=lower, entry_zone_upper=upper, invalidation_price=invalidation,
        protection_buffer=buffer, decision_tick_size=tick,
        setup_strength=0.6, data_confidence=0.9,
        family_facts={
            "level_anchor_bucket": _h(-4).isoformat(), "raw_level_price": level,
            "level_kind": "RESISTANCE" if direction == LONG else "SUPPORT",
            "bucket_1h": _h(-1).isoformat(), "breakout_close": level + 0.5,
        })


# ---- persist-then-reconstruct helpers ---------------------------------------
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


def _history(events, *, as_of=None, run_kind=LIVE, run_id=RUN_ID):
    """Reconstruct the episode exactly as a fresh process would."""
    return reconstruct_episode_history(
        [_row(e) for e in events], run_kind=run_kind, run_id=run_id,
        episode_id=events[0].episode_id,
        as_of=as_of if as_of is not None else _t(500), boundary_mode=HISTORY_THROUGH_T)


def early_signal(candidate, *, run_kind=LIVE, run_id=RUN_ID):
    """One real Unit 2 EARLY_SIGNAL creation event."""
    return build_early_signal_creation(
        candidate,
        authorization=_creation_authorization(T=candidate.T, run_kind=run_kind, run_id=run_id),
        T=candidate.T)


def episode(candidate, *, run_kind=LIVE, run_id=RUN_ID, as_of=None):
    return _history([early_signal(candidate, run_kind=run_kind, run_id=run_id)],
                    as_of=as_of, run_kind=run_kind, run_id=run_id)


# ---- boundary facts ---------------------------------------------------------
def _quality_maps(*, price_structure_ok=True, degraded_families=(), null_families=()):
    """§6.3a's per-family coverage/confidence maps.

    `degraded_families` are PRESENT but below their floor (§21 Rejected);
    `null_families` are present-but-NULL (§21 Unavailable)."""
    coverage, confidence = {}, {}
    for family in ("price_structure", "volume", "taker_flow", "oi", "funding", "liquidations"):
        if family in null_families:
            coverage[family] = {"ratio": None}
            confidence[family] = None
            continue
        ok = family not in degraded_families and (
            price_structure_ok or family != "price_structure")
        coverage[family] = {"ratio": 1.0 if ok else 0.5}
        confidence[family] = 90.0 if ok else 20.0
    return coverage, confidence


def _consensus(*, T, median=None, agreement=None, price_structure_ok=True,
               degraded_families=(), null_families=(), scope=None, **extra):
    """A 5m consensus row carrying §6.3a's per-family maps and its own
    semantic identity."""
    coverage, confidence = _quality_maps(
        price_structure_ok=price_structure_ok, degraded_families=degraded_families,
        null_families=null_families)
    identity = dict(symbol=SYMBOL, market_type=MARKET, calculation_version=H16,
                    feature_schema_version=1)
    identity.update(scope or {})
    row = {
        "timeframe": "5m", "bucket_ts": T - timedelta(minutes=5),
        "price_move_pct_median": median, "price_direction_agreement": agreement,
        "coverage_by_metric": coverage, "data_confidence_by_metric": confidence,
        **identity,
    }
    row.update(extra)
    return row


def _reference(*, T, close, usable=True, has_gap=False, bars_present=5, bars_expected=5,
               scope=None, drop=()):
    identity = dict(exchange=V2_REFERENCE_EXCHANGE, symbol=SYMBOL, market_type=MARKET,
                    calculation_version=H16, feature_schema_version=1)
    identity.update(scope or {})
    row = {
        "timeframe": "5m", "bucket_ts": T - timedelta(minutes=5),
        "is_usable": usable, "has_gap": has_gap,
        "bars_present": bars_present, "bars_expected": bars_expected,
        "close_price": close, **identity,
    }
    for field in drop:
        row.pop(field, None)
    return row


def facts(*, T, close=None, median=None, agreement=None, price_structure_ok=True,
          degraded_families=(), null_families=(), consensus=True, reference=True,
          symbol=SYMBOL, market_type=MARKET, calculation_version=H16,
          feature_schema_version=1, reference_exchange=V2_REFERENCE_EXCHANGE,
          row_scope=None, **ref_over) -> V2BoundaryFacts:
    scope = dict(symbol=symbol, market_type=market_type,
                 calculation_version=calculation_version,
                 feature_schema_version=feature_schema_version)
    row_identity = dict(scope)
    row_identity.update(row_scope or {})
    ref_identity = dict(row_identity, exchange=reference_exchange)
    return V2BoundaryFacts(
        T=T, reference_exchange=reference_exchange, **scope,
        consensus_5m=(_consensus(
            T=T, median=median, agreement=agreement,
            price_structure_ok=price_structure_ok, degraded_families=degraded_families,
            null_families=null_families, scope=row_identity)
            if consensus else None),
        reference_feature_5m=(
            _reference(T=T, close=close, scope=ref_identity, **ref_over)
            if reference else None),
    )


def tp_facts(*, T, median=1.0, agreement=1.0, close=105.0, **kw) -> V2BoundaryFacts:
    """TP boundary facts whose resumption trigger holds by default."""
    return facts(T=T, median=median, agreement=agreement, close=close, **kw)


def _boundary(*, T, **kw) -> V2BoundaryFacts:
    """Raw `V2BoundaryFacts` with this suite's default scope -- for attacks
    that hand-build one of the two rows."""
    return V2BoundaryFacts(
        T=T, symbol=SYMBOL, market_type=MARKET, calculation_version=H16,
        feature_schema_version=1, reference_exchange=V2_REFERENCE_EXCHANGE, **kw)


def _decide(history, *, T, boundary, reevaluation=None) -> V2LifecycleDecision:
    return evaluate_early_signal_transition(
        history, T=T, facts=boundary, reevaluation_window=reevaluation)


# ---- §12.2a mechanism (1): canonical reference-history source windows -------
def _ref_15m_row(*, bucket_ts, close, usable=True, has_gap=False, bars_present=15,
                 bars_expected=15, scope=None, drop=()):
    identity = dict(exchange=V2_REFERENCE_EXCHANGE, symbol=SYMBOL, market_type=MARKET,
                    calculation_version=H16, feature_schema_version=1)
    identity.update(scope or {})
    row = {
        "timeframe": "15m", "bucket_ts": bucket_ts, "is_usable": usable,
        "has_gap": has_gap, "bars_present": bars_present, "bars_expected": bars_expected,
        "close_price": close, **identity,
    }
    for field in drop:
        row.pop(field, None)
    return row


def _window(*, T, closes, anchor=None, filler=None, scope=None, row_over=None, rows=None,
            symbol=SYMBOL, market_type=MARKET, calculation_version=H16,
            feature_schema_version=1) -> V2TrendPullbackReevaluationWindow:
    """A §7.1 re-evaluation span: contiguous 15m reference closes from the
    episode's frozen anchor bucket through `B15' = selected_bucket(15m, T)`.

    `closes` is oldest-first and its LAST element is `B15'`'s own close, so
    the span's END is pinned and its start is derived rather than guessed.
    When `anchor` is given with a `filler`, the span is left-padded with
    `filler` closes back to that anchor — pick a `filler` that can never be
    the extreme for the direction under test (high for `LONG`, low for
    `SHORT`), so each vector states only the closes it actually cares
    about."""
    if rows is None:
        b15 = selected_bucket("15m", T)
        if anchor is not None and filler is not None:
            span = int((b15 - anchor) / timedelta(minutes=15)) + 1
            closes = [filler] * (span - len(closes)) + list(closes)
        start = anchor if anchor is not None else b15 - timedelta(
            minutes=15 * (len(closes) - 1))
        rows = [
            _ref_15m_row(bucket_ts=start + timedelta(minutes=15 * i), close=close,
                         scope=scope, **(row_over or {}))
            for i, close in enumerate(closes)]
    return V2TrendPullbackReevaluationWindow(
        T=T, symbol=symbol, market_type=market_type,
        calculation_version=calculation_version,
        feature_schema_version=feature_schema_version,
        reference_15m_rows=tuple(rows))


# ============================================================================
# 1. §14 — frozen candidate-age deadlines
# ============================================================================
def test_frozen_candidate_max_ages_match_the_contract_table():
    assert CANDIDATE_MAX_AGE[TREND_PULLBACK] == timedelta(hours=2)
    assert CANDIDATE_MAX_AGE[COMPRESSION_BREAKOUT] == timedelta(minutes=15)
    assert CANDIDATE_MAX_AGE[CONFIRMED_BREAKOUT] == timedelta(minutes=40)


@pytest.mark.parametrize(("make", "age"), [
    (tp_candidate, timedelta(hours=2)),
    (comp_candidate, timedelta(minutes=15)),
    (cb_candidate, timedelta(minutes=40)),
])
def test_deadline_is_t_detect_plus_the_family_window(make, age):
    hist = episode(make(T=T0))
    assert read_detection_boundary(hist) == T0
    assert read_candidate_deadline(hist) == T0 + age


def test_detection_boundary_disagreement_fails_closed():
    """`t_create` and the persisted `creation_facts.t_detect` are two
    recordings of ONE fact; they must never drift into two deadlines."""
    event = early_signal(tp_candidate(T=T0))
    row = _row(event)
    snapshot = dict(row["decision_snapshot"])
    facts_block = dict(snapshot["creation_facts"])
    facts_block["t_detect"] = _t(9).isoformat()
    snapshot["creation_facts"] = facts_block
    row["decision_snapshot"] = snapshot
    hist = reconstruct_episode_history(
        [row], run_kind=LIVE, run_id=RUN_ID, episode_id=event.episode_id,
        as_of=_t(500), boundary_mode=HISTORY_THROUGH_T)
    with pytest.raises(V2EpisodeLifecycleError, match="exactly one origin"):
        read_candidate_deadline(hist)


# ============================================================================
# 2. §7.1/§14 — TREND_PULLBACK confirmation cadence and age window
# ============================================================================
def test_trigger_already_true_at_t_detect_does_not_confirm():
    """§7.1: confirmation is only ever EVALUATED at `T' > T_detect`, so the
    detection bucket can never also confirm."""
    hist = episode(tp_candidate(T=T0))
    with pytest.raises(V2EpisodeLifecycleError, match="strictly after"):
        _decide(hist, T=T0, boundary=tp_facts(T=T0))


def test_earliest_possible_confirmation_is_t_detect_plus_5m():
    hist = episode(tp_candidate(T=T0))
    decision = _decide(hist, T=_t(1), boundary=tp_facts(T=_t(1)))
    assert decision.outcome == LIFECYCLE_CONFIRMED
    assert decision.new_state == CONFIRMED
    assert decision.T == _t(1) == T0 + timedelta(minutes=5)


def test_trigger_false_at_the_next_boundary_holds_without_an_event():
    hist = episode(tp_candidate(T=T0))
    decision = _decide(hist, T=_t(1), boundary=tp_facts(T=_t(1), median=-1.0))
    assert decision.outcome == LIFECYCLE_NO_CHANGE
    assert decision.new_state == EARLY_SIGNAL
    assert decision.requires_event is False
    assert decision.signal.signal == SIGNAL_HOLD


def test_first_matching_later_boundary_confirms():
    hist = episode(tp_candidate(T=T0))
    for n in (1, 2, 3):
        assert _decide(
            hist, T=_t(n), boundary=tp_facts(T=_t(n), median=-1.0)
        ).outcome == LIFECYCLE_NO_CHANGE
    assert _decide(hist, T=_t(4), boundary=tp_facts(T=_t(4))).outcome == LIFECYCLE_CONFIRMED


def test_confirmation_is_checked_on_5m_only_boundaries_not_just_15m():
    """§14's amended vector: PULLBACK_MAX_AGE is an AGE WINDOW; confirmation
    is checked at EVERY later 5m boundary, not only at 15m boundaries."""
    hist = episode(tp_candidate(T=T0))
    for n in (1, 2, 4, 5, 7, 8):        # none of these is a 15m boundary
        assert (_t(n) - T0).total_seconds() % 900 != 0
        assert _decide(hist, T=_t(n), boundary=tp_facts(T=_t(n))).outcome == LIFECYCLE_CONFIRMED


def test_all_24_later_5m_boundaries_are_eligible_confirmation_opportunities():
    """T_detect=12:00, deadline=14:00 => exactly 24 later 5m opportunities,
    12:05 through 14:00 inclusive (§14's worked vector)."""
    hist = episode(tp_candidate(T=T0))
    eligible = [_t(n) for n in range(1, 25)]
    assert eligible[0] == datetime(2026, 8, 20, 12, 5, tzinfo=UTC)
    assert eligible[-1] == datetime(2026, 8, 20, 14, 0, tzinfo=UTC)
    assert eligible[-1] == read_candidate_deadline(hist)
    for T in eligible:
        assert _decide(hist, T=T, boundary=tp_facts(T=T)).outcome == LIFECYCLE_CONFIRMED


def test_no_expiry_before_the_deadline_boundary():
    hist = episode(tp_candidate(T=T0))
    for n in range(1, 24):              # 12:05 .. 13:55
        decision = _decide(hist, T=_t(n), boundary=tp_facts(T=_t(n), median=-1.0))
        assert decision.outcome == LIFECYCLE_NO_CHANGE, f"unexpected expiry at {_t(n)}"
    assert _t(23) == datetime(2026, 8, 20, 13, 55, tzinfo=UTC)


def test_trigger_holds_at_the_deadline_boundary_confirms_not_expires():
    """§13.1/§14: the deadline bucket is a fully valid confirmation
    opportunity, never an automatic expiry."""
    hist = episode(tp_candidate(T=T0))
    deadline = read_candidate_deadline(hist)
    assert deadline == datetime(2026, 8, 20, 14, 0, tzinfo=UTC)
    decision = _decide(hist, T=deadline, boundary=tp_facts(T=deadline))
    assert decision.outcome == LIFECYCLE_CONFIRMED
    assert decision.new_state == CONFIRMED


def test_trigger_absent_at_the_deadline_boundary_expires():
    hist = episode(tp_candidate(T=T0))
    deadline = read_candidate_deadline(hist)
    decision = _decide(hist, T=deadline, boundary=tp_facts(T=deadline, median=-1.0))
    assert decision.outcome == LIFECYCLE_EXPIRED_CANDIDATE_AGE
    assert decision.new_state == EXPIRED
    assert decision.requires_event is True


def test_trend_pullback_has_no_false_break_rule():
    """§7.1 defines no false-break; TP's pre-confirmation invalidation is
    §10's generic invalidation_price crossing, which Unit 4 owns."""
    hist = episode(tp_candidate(T=T0))
    for median in (-5.0, 0.0, 5.0):
        signal = evaluate_family_signal(hist, tp_facts(T=_t(1), median=median, agreement=0.2))
        assert signal.signal != SIGNAL_FALSE_BREAK


@pytest.mark.parametrize(("direction", "median", "confirms"), [
    (LONG, 1.0, True), (LONG, -1.0, False), (LONG, 0.0, False),
    (SHORT, -1.0, True), (SHORT, 1.0, False), (SHORT, 0.0, False),
])
def test_resumption_trigger_uses_the_ternary_sign(direction, median, confirms):
    """`STAGE2_SPEC.md` §11.2: exactly flat is sign 0 and matches NO
    direction."""
    hist = episode(tp_candidate(T=T0, direction=direction))
    signal = evaluate_family_signal(hist, tp_facts(T=_t(1), median=median, agreement=1.0))
    assert (signal.signal == SIGNAL_CONFIRM) is confirms


@pytest.mark.parametrize(("agreement", "confirms"), [
    (1.0, True), (2.0 / 3.0, True), (0.6666, False), (0.5, False), (0.0, False),
])
def test_resumption_agreement_threshold_is_inclusive_two_thirds(agreement, confirms):
    """§7.1's threshold is `>= 2/3`, INCLUSIVE — and deliberately unrelated
    to §13.2a's separate STRICT `> 0.5` WEAKENING threshold."""
    assert RESUMPTION_MIN_AGREEMENT == 2.0 / 3.0
    hist = episode(tp_candidate(T=T0))
    signal = evaluate_family_signal(hist, tp_facts(T=_t(1), agreement=agreement))
    assert (signal.signal == SIGNAL_CONFIRM) is confirms


# ============================================================================
# 3. §7.2 — COMPRESSION_BREAKOUT confirmation / HOLD / one-sided false break
# ============================================================================
def test_compression_long_boundary_equality_is_a_neutral_hold():
    hist = episode(comp_candidate(T=T0, range_high=100.0))
    decision = _decide(hist, T=_t(1), boundary=facts(T=_t(1), close=100.0))
    assert decision.signal.signal == SIGNAL_HOLD
    assert decision.outcome == LIFECYCLE_NO_CHANGE
    assert decision.requires_event is False


def test_compression_long_strictly_beyond_confirms():
    hist = episode(comp_candidate(T=T0, range_high=100.0))
    assert _decide(
        hist, T=_t(1), boundary=facts(T=_t(1), close=101.0)
    ).outcome == LIFECYCLE_CONFIRMED


def test_compression_long_wrong_side_by_one_tick_invalidates():
    hist = episode(comp_candidate(T=T0, range_high=100.0))
    decision = _decide(hist, T=_t(1), boundary=facts(T=_t(1), close=99.9))
    assert decision.outcome == LIFECYCLE_INVALIDATED_FALSE_BREAK
    assert decision.new_state == INVALIDATED


def test_compression_long_overshoot_through_the_opposite_side_invalidates():
    """§7.2's re-amendment: a close BELOW `range_low` is a STRONGER
    repudiation than re-entry, and the one-sided rule catches it — the old
    `range_low < close < range_high` predicate could not."""
    hist = episode(comp_candidate(T=T0, range_low=90.0, range_high=100.0))
    for close in (90.0, 89.0, 1.0):
        decision = _decide(hist, T=_t(1), boundary=facts(T=_t(1), close=close))
        assert decision.outcome == LIFECYCLE_INVALIDATED_FALSE_BREAK, close


def test_compression_short_mirrors_exactly():
    hist = episode(comp_candidate(T=T0, direction=SHORT, range_low=90.0, range_high=100.0))
    assert _decide(hist, T=_t(1), boundary=facts(T=_t(1), close=90.0)
                   ).signal.signal == SIGNAL_HOLD
    assert _decide(hist, T=_t(1), boundary=facts(T=_t(1), close=89.0)
                   ).outcome == LIFECYCLE_CONFIRMED
    assert _decide(hist, T=_t(1), boundary=facts(T=_t(1), close=90.1)
                   ).outcome == LIFECYCLE_INVALIDATED_FALSE_BREAK


def test_compression_short_overshoot_above_range_high_invalidates():
    hist = episode(comp_candidate(T=T0, direction=SHORT, range_low=90.0, range_high=100.0))
    for close in (100.0, 105.0, 1000.0):
        assert _decide(
            hist, T=_t(1), boundary=facts(T=_t(1), close=close)
        ).outcome == LIFECYCLE_INVALIDATED_FALSE_BREAK, close


def test_compression_deadline_is_the_third_5m_bucket():
    hist = episode(comp_candidate(T=T0))
    assert read_candidate_deadline(hist) == _t(3) == datetime(2026, 8, 20, 12, 15, tzinfo=UTC)


@pytest.mark.parametrize(("close", "outcome"), [
    (101.0, LIFECYCLE_CONFIRMED),
    (100.0, LIFECYCLE_EXPIRED_CANDIDATE_AGE),
    (99.0, LIFECYCLE_INVALIDATED_FALSE_BREAK),
])
def test_compression_deadline_bucket_resolves_three_ways(close, outcome):
    hist = episode(comp_candidate(T=T0, range_high=100.0))
    deadline = read_candidate_deadline(hist)
    assert _decide(hist, T=deadline, boundary=facts(T=deadline, close=close)).outcome == outcome


def test_compression_confirmation_need_not_be_adjacent_and_holds_do_not_reset_age():
    """§7.2: first breakout close + a LATER confirming close, with any number
    of intervening HOLD buckets. A HOLD consumes a bucket of the window; it
    never resets it and never requires adjacency."""
    hist = episode(comp_candidate(T=T0, range_high=100.0))
    assert _decide(hist, T=_t(1), boundary=facts(T=_t(1), close=100.0)
                   ).outcome == LIFECYCLE_NO_CHANGE
    assert _decide(hist, T=_t(2), boundary=facts(T=_t(2), close=100.0)
                   ).outcome == LIFECYCLE_NO_CHANGE
    assert _decide(hist, T=_t(3), boundary=facts(T=_t(3), close=100.5)
                   ).outcome == LIFECYCLE_CONFIRMED
    # The window did not grow: T+20m is beyond the deadline and fails closed.
    with pytest.raises(V2EpisodeLifecycleError, match="beyond its §14 candidate deadline"):
        _decide(hist, T=_t(4), boundary=facts(T=_t(4), close=100.5))


def test_compression_confirmation_ignores_taker_flow_state():
    """§7.2's taker-flow gate is a FORMATION requirement on the EARLY_SIGNAL
    bucket; §6.3a scopes confirmation to `price_structure` alone."""
    hist = episode(comp_candidate(T=T0, range_high=100.0))
    boundary = facts(
        T=_t(1), close=101.0,
        degraded_families=("taker_flow", "volume", "oi", "funding", "liquidations"))
    assert _decide(hist, T=_t(1), boundary=boundary).outcome == LIFECYCLE_CONFIRMED


# ============================================================================
# 4. §7.3 — CONFIRMED_BREAKOUT
# ============================================================================
def test_confirmed_breakout_long_three_way_comparison():
    hist = episode(cb_candidate(T=T0, level=100.0))
    assert _decide(hist, T=_t(1), boundary=facts(T=_t(1), close=100.0)
                   ).signal.signal == SIGNAL_HOLD
    assert _decide(hist, T=_t(1), boundary=facts(T=_t(1), close=100.01)
                   ).outcome == LIFECYCLE_CONFIRMED
    assert _decide(hist, T=_t(1), boundary=facts(T=_t(1), close=99.99)
                   ).outcome == LIFECYCLE_INVALIDATED_FALSE_BREAK


def test_confirmed_breakout_short_three_way_comparison():
    hist = episode(cb_candidate(T=T0, direction=SHORT, level=100.0))
    assert _decide(hist, T=_t(1), boundary=facts(T=_t(1), close=100.0)
                   ).signal.signal == SIGNAL_HOLD
    assert _decide(hist, T=_t(1), boundary=facts(T=_t(1), close=99.99)
                   ).outcome == LIFECYCLE_CONFIRMED
    assert _decide(hist, T=_t(1), boundary=facts(T=_t(1), close=100.01)
                   ).outcome == LIFECYCLE_INVALIDATED_FALSE_BREAK


def test_confirmed_breakout_later_strict_close_confirms_after_holds():
    hist = episode(cb_candidate(T=T0, level=100.0))
    for n in (1, 2, 3, 4):
        assert _decide(hist, T=_t(n), boundary=facts(T=_t(n), close=100.0)
                       ).outcome == LIFECYCLE_NO_CHANGE
    assert _decide(hist, T=_t(5), boundary=facts(T=_t(5), close=100.5)
                   ).outcome == LIFECYCLE_CONFIRMED


def test_confirmed_breakout_deadline_is_the_eighth_5m_bucket():
    hist = episode(cb_candidate(T=T0))
    assert read_candidate_deadline(hist) == _t(8) == datetime(2026, 8, 20, 12, 40, tzinfo=UTC)


@pytest.mark.parametrize(("close", "outcome"), [
    (100.5, LIFECYCLE_CONFIRMED),
    (100.0, LIFECYCLE_EXPIRED_CANDIDATE_AGE),
    (99.5, LIFECYCLE_INVALIDATED_FALSE_BREAK),
])
def test_confirmed_breakout_deadline_bucket_resolves_three_ways(close, outcome):
    hist = episode(cb_candidate(T=T0, level=100.0))
    deadline = read_candidate_deadline(hist)
    assert _decide(hist, T=deadline, boundary=facts(T=deadline, close=close)).outcome == outcome


def test_confirmed_breakout_confirmation_requires_no_taker_flow():
    """§7.3 carries NO taker-flow requirement at all — neither at formation
    nor at confirmation — and no current flow state may block it."""
    hist = episode(cb_candidate(T=T0, level=100.0))
    boundary = facts(
        T=_t(1), close=101.0,
        degraded_families=("taker_flow", "oi", "funding", "liquidations", "volume"))
    assert _decide(hist, T=_t(1), boundary=boundary).outcome == LIFECYCLE_CONFIRMED
    assert REQUIRED_METRIC_FAMILY[CONFIRMED_BREAKOUT] == ("price_structure",)


def test_breakout_confirmation_uses_the_frozen_creation_level_not_current_data():
    """§12.2a: later confirmation always checks the SAME creation boundary.
    A candidate detected later with a different level cannot move it."""
    hist = episode(cb_candidate(T=T0, level=100.0))
    # 100.5 is beyond the FROZEN level (100.0) but below a hypothetical
    # freshly-detected 101.0 level; the frozen one is what decides.
    assert _decide(hist, T=_t(1), boundary=facts(T=_t(1), close=100.5)
                   ).outcome == LIFECYCLE_CONFIRMED
    evidence = _decide(hist, T=_t(1), boundary=facts(T=_t(1), close=100.5)).signal.evidence
    assert evidence["structural_level"] == 100.0


# ============================================================================
# 5. §13.1/§14 — deadline precedence, mechanically, per family
# ============================================================================
@pytest.mark.parametrize("make", [tp_candidate, comp_candidate, cb_candidate])
def test_no_expiry_strictly_before_the_deadline_for_any_family(make):
    hist = episode(make(T=T0))
    deadline = read_candidate_deadline(hist)
    T = deadline - timedelta(minutes=5)
    # A boundary that neither confirms nor false-breaks: TP sign mismatch,
    # breakouts boundary-equality.
    boundary = (tp_facts(T=T, median=-1.0) if make is tp_candidate
                else facts(T=T, close=100.0))
    assert _decide(hist, T=T, boundary=boundary).outcome == LIFECYCLE_NO_CHANGE


@pytest.mark.parametrize("make", [tp_candidate, comp_candidate, cb_candidate])
def test_confirmation_wins_at_the_deadline_for_any_family(make):
    hist = episode(make(T=T0))
    deadline = read_candidate_deadline(hist)
    boundary = (tp_facts(T=deadline) if make is tp_candidate
                else facts(T=deadline, close=101.0))
    assert _decide(hist, T=deadline, boundary=boundary).outcome == LIFECYCLE_CONFIRMED


@pytest.mark.parametrize("make", [comp_candidate, cb_candidate])
def test_false_break_wins_at_the_deadline_for_breakout_families(make):
    hist = episode(make(T=T0))
    deadline = read_candidate_deadline(hist)
    assert _decide(hist, T=deadline, boundary=facts(T=deadline, close=50.0)
                   ).outcome == LIFECYCLE_INVALIDATED_FALSE_BREAK


@pytest.mark.parametrize("make", [tp_candidate, comp_candidate, cb_candidate])
def test_still_early_signal_beyond_the_deadline_fails_closed(make):
    hist = episode(make(T=T0))
    deadline = read_candidate_deadline(hist)
    T = deadline + timedelta(minutes=5)
    boundary = (tp_facts(T=T) if make is tp_candidate else facts(T=T, close=101.0))
    with pytest.raises(V2EpisodeLifecycleError, match="beyond its §14 candidate deadline"):
        _decide(hist, T=T, boundary=boundary)


def test_expiry_is_never_computed_as_an_independent_age_fact():
    """The failure mode §13.1 forbids: `if age >= max_age: expire()` before
    checking whether this exact boundary confirms."""
    hist = episode(comp_candidate(T=T0, range_high=100.0))
    deadline = read_candidate_deadline(hist)
    confirmed = _decide(hist, T=deadline, boundary=facts(T=deadline, close=100.01))
    assert confirmed.outcome == LIFECYCLE_CONFIRMED
    assert confirmed.T == deadline
    assert confirmed.candidate_deadline == deadline


# ============================================================================
# 6. §6.3a — metric-scoped quality
# ============================================================================
@pytest.mark.parametrize("make", [tp_candidate, comp_candidate, cb_candidate])
def test_unrelated_degraded_metric_family_never_suppresses_a_transition(make):
    hist = episode(make(T=T0))
    boundary = (
        tp_facts(T=_t(1), degraded_families=("liquidations", "funding", "oi", "volume"))
        if make is tp_candidate
        else facts(T=_t(1), close=101.0,
                   degraded_families=("liquidations", "funding", "oi", "volume", "taker_flow")))
    assert _decide(hist, T=_t(1), boundary=boundary).outcome == LIFECYCLE_CONFIRMED


@pytest.mark.parametrize("make", [tp_candidate, comp_candidate, cb_candidate])
def test_degraded_price_structure_is_rejected_not_confirmed(make):
    """§21: a PRESENT required family below its frozen floor is REJECTED --
    a real measurement a hard gate disqualified, never an absence."""
    hist = episode(make(T=T0))
    boundary = (tp_facts(T=_t(1), price_structure_ok=False) if make is tp_candidate
                else facts(T=_t(1), close=101.0, price_structure_ok=False))
    decision = _decide(hist, T=_t(1), boundary=boundary)
    assert decision.signal.signal == SIGNAL_REJECTED
    assert decision.outcome == LIFECYCLE_NO_CHANGE


def test_every_family_requires_only_price_structure():
    for family in (TREND_PULLBACK, COMPRESSION_BREAKOUT, CONFIRMED_BREAKOUT):
        assert REQUIRED_METRIC_FAMILY[family] == ("price_structure",)


def test_absent_consensus_row_is_unavailable_not_an_error():
    hist = episode(tp_candidate(T=T0))
    decision = _decide(
        hist, T=_t(1), boundary=facts(T=_t(1), consensus=False, reference=False))
    assert decision.signal.signal == SIGNAL_UNAVAILABLE
    assert decision.signal.reason == "CONSENSUS_ROW_ABSENT"
    assert decision.outcome == LIFECYCLE_NO_CHANGE


def test_reference_close_failing_the_11_gate_is_unavailable_never_a_failover():
    """§11 fails closed for any calculation needing the canonical reference
    price — never a silent switch to another exchange (§22)."""
    hist = episode(comp_candidate(T=T0, range_high=100.0))
    for over in ({"usable": False}, {"has_gap": True}, {"bars_present": 4}):
        boundary = facts(T=_t(1), close=101.0, **over)
        decision = _decide(hist, T=_t(1), boundary=boundary)
        assert decision.signal.signal == SIGNAL_UNAVAILABLE, over
        assert decision.outcome == LIFECYCLE_NO_CHANGE


def test_rejected_at_the_deadline_expires_with_the_category_preserved():
    """§14's amended rule: the hard age budget still ends, but the persisted
    resolution category says REJECTED -- never a fabricated neutral HOLD."""
    hist = episode(comp_candidate(T=T0, range_high=100.0))
    deadline = read_candidate_deadline(hist)
    decision = _decide(
        hist, T=deadline, boundary=facts(T=deadline, close=101.0, price_structure_ok=False))
    assert decision.outcome == LIFECYCLE_EXPIRED_CANDIDATE_AGE
    assert decision.signal.signal == SIGNAL_REJECTED
    assert decision.resolution_category == SIGNAL_REJECTED
    assert "REJECTED" in decision.reason


def test_unavailable_at_the_deadline_expires_with_the_category_preserved():
    hist = episode(comp_candidate(T=T0, range_high=100.0))
    deadline = read_candidate_deadline(hist)
    decision = _decide(
        hist, T=deadline, boundary=facts(T=deadline, consensus=False, reference=False))
    assert decision.outcome == LIFECYCLE_EXPIRED_CANDIDATE_AGE
    assert decision.signal.signal == SIGNAL_UNAVAILABLE
    assert decision.resolution_category == SIGNAL_UNAVAILABLE
    assert "UNAVAILABLE" in decision.reason


def test_hold_at_the_deadline_expires_with_the_neutral_category():
    hist = episode(comp_candidate(T=T0, range_high=100.0))
    deadline = read_candidate_deadline(hist)
    decision = _decide(hist, T=deadline, boundary=facts(T=deadline, close=100.0))
    assert decision.outcome == LIFECYCLE_EXPIRED_CANDIDATE_AGE
    assert decision.resolution_category == SIGNAL_HOLD


# ============================================================================
# 7. §7.1/§9/§12.2a — TREND_PULLBACK pre-confirmation operational updates
# ============================================================================
def _reevaluation(*, T, closes, anchor=None, **kw):
    return _window(T=T, closes=closes, anchor=anchor, **kw)


def test_creation_facts_are_the_initial_operational_facts():
    hist = episode(tp_candidate(T=T0, pullback_extreme=100.0, current_close=105.0, buffer=2.0))
    facts_now = read_operational_facts(hist)
    assert facts_now.pullback_extreme == 100.0
    assert facts_now.dynamic_bound == 105.0
    assert facts_now.entry_zone_lower == 100.0
    assert facts_now.entry_zone_upper == 105.0
    assert facts_now.invalidation_price == 98.0
    assert facts_now.source == OPERATIONAL_SOURCE_CREATION


def test_breakout_families_have_no_operational_facts_shape():
    """§12.2a: only TREND_PULLBACK has a pre-confirmation mutability
    mechanism."""
    for make in (comp_candidate, cb_candidate):
        assert read_operational_facts(episode(make(T=T0))) is None


def test_deeper_pullback_at_a_later_15m_boundary_updates_the_same_episode():
    creation = early_signal(tp_candidate(T=T0, pullback_extreme=100.0, current_close=105.0))
    hist = _history([creation])
    T = _t(3)                            # 12:15 — a legal 15m boundary
    # The span runs from the frozen creation anchor through B15'; 97.0 is the
    # deepest close in it, and 103.0 is B15' itself.
    window = _window(T=T, closes=[97.0, 103.0],
                             anchor=_TP_ANCHOR, filler=_LONG_FILLER)
    decision = _decide(hist, T=T, boundary=tp_facts(T=T, median=-1.0), reevaluation=window)
    assert decision.outcome == LIFECYCLE_PRECONFIRMATION_UPDATE
    assert decision.new_state == EARLY_SIGNAL
    assert decision.requires_event is True
    assert decision.operational_facts.pullback_extreme == 97.0    # DERIVED, not asserted
    assert decision.operational_facts.dynamic_bound == 103.0
    assert decision.operational_facts.entry_zone_lower == 97.0
    assert decision.operational_facts.entry_zone_upper == 103.0
    assert decision.operational_facts.invalidation_price == 95.0

    event = build_episode_transition_event(decision, hist, authorization=_authorization(T=T))
    assert event.episode_id == creation.episode_id          # same episode
    assert event.episode_state == EARLY_SIGNAL              # same state
    assert dict(event.structural_anchor) == dict(creation.structural_anchor)


def test_update_event_never_rewrites_the_creation_event():
    """§9's historical-truth rule: the EARLY_SIGNAL zone already published
    is immutable; an update is a NEW event."""
    creation = early_signal(tp_candidate(T=T0, pullback_extreme=100.0, current_close=105.0))
    hist = _history([creation])
    T = _t(3)
    decision = _decide(
        hist, T=T, boundary=tp_facts(T=T, median=-1.0),
        reevaluation=_window(T=T, closes=[97.0, 103.0],
                             anchor=_TP_ANCHOR, filler=_LONG_FILLER))
    update = build_episode_transition_event(decision, hist, authorization=_authorization(T=T))
    after = _history([creation, update])
    assert len(after.events) == 2
    original = after.events[0].decision_snapshot["creation_facts"]
    assert original["entry_zone_lower"] == 100.0
    assert original["entry_zone_upper"] == 105.0
    assert original["invalidation_price"] == 98.0
    assert read_operational_facts(after).pullback_extreme == 97.0


@pytest.mark.parametrize("n", [1, 2, 4, 5, 7, 8])
def test_a_5m_only_boundary_cannot_carry_a_structural_reevaluation(n):
    """§7.1 re-evaluates at LATER 15m boundaries; 15m is the re-measurement
    cadence and 5m is the confirmation cadence. Conflating them is exactly
    the error §14's amended vector calls out."""
    assert (_t(n) - T0).total_seconds() % 900 != 0
    with pytest.raises(V2EpisodeLifecycleError, match="reevaluation T"):
        _window(T=_t(n), closes=[100.0])


@pytest.mark.parametrize("n", [3, 6, 9])
def test_a_15m_boundary_may_carry_a_structural_reevaluation(n):
    window = _window(T=_t(n), closes=[100.0, 99.0])
    assert window.b15 == _t(n) - timedelta(minutes=15)


def test_a_window_that_does_not_end_at_b15_is_refused():
    """§7.1 re-evaluates against `B15' = selected_bucket(15m, T')`."""
    T = _t(6)
    rows = [_ref_15m_row(bucket_ts=_q(-2) + timedelta(minutes=15 * i), close=100.0)
            for i in range(2)]
    with pytest.raises(V2EpisodeLifecycleError, match="must run THROUGH that bucket"):
        _window(T=T, closes=[], rows=rows)


def test_shallower_derived_extreme_is_refused_not_walked_back():
    """§7.1: the extreme updates only if the retracement DEEPENS further."""
    creation = early_signal(tp_candidate(T=T0, pullback_extreme=100.0, current_close=105.0))
    hist = _history([creation])
    T = _t(3)
    with pytest.raises(V2EpisodeLifecycleError, match="SHALLOWER"):
        _decide(hist, T=T, boundary=tp_facts(T=T, median=-1.0),
                reevaluation=_window(T=T, closes=[101.0, 103.0],
                             anchor=_TP_ANCHOR, filler=_LONG_FILLER))


def test_reevaluation_that_reproduces_the_same_geometry_writes_no_event():
    """§12.11: a re-observation with no changed episode-visible fact is a
    legitimate no-op, not history spam."""
    hist = episode(tp_candidate(T=T0, pullback_extreme=100.0, current_close=105.0))
    T = _t(3)
    decision = _decide(
        hist, T=T, boundary=tp_facts(T=T, median=-1.0),
        reevaluation=_window(T=T, closes=[100.0, 105.0], anchor=_TP_ANCHOR, filler=_LONG_FILLER))
    assert decision.outcome == LIFECYCLE_NO_CHANGE
    assert decision.requires_event is False


def test_an_unchanged_extreme_with_a_moved_bound_still_requires_history():
    """§9: the published zone changed, so the change is recorded -- even
    though the running extreme did not move."""
    hist = episode(tp_candidate(T=T0, pullback_extreme=100.0, current_close=105.0))
    T = _t(3)
    decision = _decide(
        hist, T=T, boundary=tp_facts(T=T, median=-1.0),
        reevaluation=_window(T=T, closes=[100.0, 108.0], anchor=_TP_ANCHOR, filler=_LONG_FILLER))
    assert decision.outcome == LIFECYCLE_PRECONFIRMATION_UPDATE
    assert decision.operational_facts.pullback_extreme == 100.0
    assert decision.operational_facts.entry_zone_upper == 108.0


# ---- RT-65-02/03: no Stage 5 candidate substitution ------------------------
def test_the_candidate_substitution_path_no_longer_exists():
    """§12.2a's two mechanisms must never be conflated. A fresh Stage 5
    detector candidate is mechanism (2) BY DEFINITION -- even when its
    creation anchor matches exactly -- and Unit 2's A/B/C classification is
    dedup/routing evidence, never the source of an active episode's own
    operational facts. The old
    `trend_pullback_reevaluation_from_candidate(...)` entry point is gone,
    not merely discouraged."""
    import analytics.forecasting_v2.episode_lifecycle as unit3
    assert not hasattr(unit3, "trend_pullback_reevaluation_from_candidate")
    assert not hasattr(unit3, "V2TrendPullbackReevaluation")
    assert "trend_pullback_reevaluation_from_candidate" not in unit3.__all__
    # No MATCH_* vocabulary is even imported: a routing class cannot be
    # accepted as proof of a re-measurement it never performed.
    source = (
        pathlib.Path(__file__).resolve().parents[2]
        / "analytics" / "forecasting_v2" / "episode_lifecycle.py").read_text(encoding="utf-8")
    import ast
    tree = ast.parse(source)
    imported = {
        alias.asname or alias.name
        for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        for alias in node.names}
    assert not {n for n in imported if n.startswith("MATCH_")}
    assert "V2CandidateFacts" not in imported


def test_an_invented_extreme_with_no_source_rows_cannot_be_supplied():
    """The public path takes ROWS, not numbers: there is no field on which a
    caller can assert `pullback_extreme = 12.34`."""
    fields = set(V2TrendPullbackReevaluationWindow.__dataclass_fields__)
    assert "pullback_extreme" not in fields
    assert "current_close" not in fields
    assert "reference_15m_rows" in fields


def test_a_span_starting_at_a_foreign_anchor_is_refused():
    """§7.1 measures the retracement ONLY from the episode's OWN frozen
    `trend_leg_extreme` anchor. A span starting elsewhere is a DIFFERENT
    structural leg -- exactly the mechanism-(2) substitution §12.2a bans."""
    hist = episode(tp_candidate(T=T0, pullback_extreme=100.0, current_close=105.0))
    T = _t(3)
    foreign = _window(T=T, closes=[97.0, 103.0])      # starts one bucket late
    assert foreign.anchor_bucket != _TP_ANCHOR
    with pytest.raises(V2EpisodeLifecycleError, match="frozen creation anchor"):
        derive_trend_pullback_reevaluation(hist, foreign)


def test_a_window_from_a_foreign_calculation_version_is_refused():
    hist = episode(tp_candidate(T=T0))
    T = _t(3)
    window = _window(T=T, closes=[97.0, 103.0], anchor=_TP_ANCHOR, filler=_LONG_FILLER,
                     calculation_version="c" * 16,
                     scope={"calculation_version": "c" * 16})
    with pytest.raises(V2EpisodeLifecycleError, match="different semantic scope"):
        derive_trend_pullback_reevaluation(hist, window)


def test_a_window_row_from_a_foreign_exchange_is_refused():
    T = _t(3)
    with pytest.raises(V2EpisodeLifecycleError, match="may not re-measure"):
        _window(T=T, closes=[97.0, 103.0], anchor=_TP_ANCHOR, filler=_LONG_FILLER,
                scope={"exchange": "bybit"})


def test_a_window_row_from_a_foreign_symbol_is_refused():
    T = _t(3)
    with pytest.raises(V2EpisodeLifecycleError, match="may not re-measure"):
        _window(T=T, closes=[97.0, 103.0], anchor=_TP_ANCHOR, filler=_LONG_FILLER,
                scope={"symbol": "ETHUSDT"})


def test_a_window_row_missing_its_identity_is_refused():
    T = _t(3)
    with pytest.raises(V2EpisodeLifecycleError, match="missing identity field"):
        _window(T=T, closes=[97.0, 103.0], anchor=_TP_ANCHOR, filler=_LONG_FILLER,
                row_over={"drop": ("calculation_version",)})


def test_a_gap_in_the_span_is_refused():
    """§7.1's retracement span is CONTIGUOUS; a hole would silently change
    which close is deepest so far, and §22 forbids filling it."""
    T = _t(6)
    b15 = selected_bucket("15m", T)
    rows = [
        _ref_15m_row(bucket_ts=b15 - timedelta(minutes=45), close=104.0),
        # the -30m bucket is MISSING
        _ref_15m_row(bucket_ts=b15 - timedelta(minutes=15), close=97.0),
        _ref_15m_row(bucket_ts=b15, close=103.0),
    ]
    with pytest.raises(V2EpisodeLifecycleError, match="CONTIGUOUS"):
        _window(T=T, closes=[], rows=rows)


def test_a_duplicate_or_out_of_order_bucket_is_refused():
    T = _t(6)
    b15 = selected_bucket("15m", T)
    rows = [
        _ref_15m_row(bucket_ts=b15 - timedelta(minutes=15), close=104.0),
        _ref_15m_row(bucket_ts=b15 - timedelta(minutes=15), close=97.0),
        _ref_15m_row(bucket_ts=b15, close=103.0),
    ]
    with pytest.raises(V2EpisodeLifecycleError, match="CONTIGUOUS"):
        _window(T=T, closes=[], rows=rows)


def test_a_future_bucket_in_the_span_is_refused():
    """No-lookahead (§1/§2): a re-evaluation at T may never read a bucket
    later than the one §1.3 selects for it."""
    T = _t(3)
    b15 = selected_bucket("15m", T)
    rows = [
        _ref_15m_row(bucket_ts=b15, close=103.0),
        _ref_15m_row(bucket_ts=b15 + timedelta(minutes=15), close=99.0),
    ]
    with pytest.raises(V2EpisodeLifecycleError, match="no-lookahead"):
        _window(T=T, closes=[], rows=rows)


@pytest.mark.parametrize("over", [
    {"usable": False}, {"has_gap": True}, {"bars_present": 14},
])
def test_an_unusable_span_bucket_makes_the_whole_window_unusable(over):
    """§11's gate fails closed, and §7.1's span is complete by construction
    -- an unusable bucket is never silently skipped (§22)."""
    T = _t(6)
    b15 = selected_bucket("15m", T)
    rows = [
        _ref_15m_row(bucket_ts=b15 - timedelta(minutes=15), close=104.0, **over),
        _ref_15m_row(bucket_ts=b15, close=103.0),
    ]
    with pytest.raises(V2EpisodeLifecycleError):
        _window(T=T, closes=[], rows=rows)


def test_reevaluation_uses_the_frozen_creation_buffer_not_a_later_one():
    """§12.2a/§12.4: an existing episode's geometry is always derived from
    its OWN creation `protection_buffer`."""
    hist = episode(tp_candidate(T=T0, pullback_extreme=100.0, current_close=105.0, buffer=2.0))
    T = _t(3)
    decision = _decide(
        hist, T=T, boundary=tp_facts(T=T, median=-1.0),
        reevaluation=_window(T=T, closes=[97.0, 103.0],
                             anchor=_TP_ANCHOR, filler=_LONG_FILLER))
    assert decision.operational_facts.invalidation_price == 95.0     # 97.0 - 2.0
    assert decision.operational_facts.protection_buffer == "2"


def test_a_reevaluation_supplied_for_a_breakout_family_is_refused():
    hist = episode(comp_candidate(T=T0))
    T = _t(3)
    with pytest.raises(V2EpisodeLifecycleError, match="only TREND_PULLBACK"):
        _decide(hist, T=T, boundary=facts(T=T, close=100.0),
                reevaluation=_window(T=T, closes=[97.0, 103.0]))


def test_short_pullback_extreme_is_the_span_maximum():
    """§7.1 mirrors: a SHORT retracement deepens UPWARD."""
    hist = episode(tp_candidate(T=T0, direction=SHORT, pullback_extreme=110.0,
                                current_close=105.0))
    T = _t(3)
    derived = derive_trend_pullback_reevaluation(
        hist, _window(T=T, closes=[113.0, 107.0], anchor=_TP_ANCHOR, filler=_SHORT_FILLER))
    assert derived.pullback_extreme == 113.0
    assert derived.entry_zone_lower == 107.0
    assert derived.entry_zone_upper == 113.0
    assert derived.invalidation_price == 115.0       # extreme + buffer


# ============================================================================
# 8. §9/§12.2a — confirmation-time freeze
# ============================================================================
def test_confirmation_freezes_the_zone_against_the_confirming_5m_close():
    """§7.1: at CONFIRMED the zone updates ONE final time, now that
    `confirmation_close_price` exists, and is then frozen."""
    hist = episode(tp_candidate(T=T0, pullback_extreme=100.0, current_close=105.0))
    decision = _decide(hist, T=_t(1), boundary=tp_facts(T=_t(1), close=107.5))
    assert decision.outcome == LIFECYCLE_CONFIRMED
    assert decision.operational_facts.dynamic_bound == 107.5
    assert decision.operational_facts.entry_zone_lower == 100.0
    assert decision.operational_facts.entry_zone_upper == 107.5
    assert decision.operational_facts.invalidation_price == 98.0


def test_confirmation_freezes_the_latest_reevaluated_pullback_extreme():
    """The exact gap this unit must not have: confirming with STALE
    creation-time operational facts after the episode's own leg deepened."""
    creation = early_signal(tp_candidate(T=T0, pullback_extreme=100.0, current_close=105.0))
    hist = _history([creation])
    T_update = _t(3)
    update_decision = _decide(
        hist, T=T_update, boundary=tp_facts(T=T_update, median=-1.0),
        reevaluation=_window(T=T_update, closes=[97.0, 103.0],
                             anchor=_TP_ANCHOR, filler=_LONG_FILLER))
    update = build_episode_transition_event(
        update_decision, hist, authorization=_authorization(T=T_update))
    after = _history([creation, update])

    confirm = _decide(after, T=_t(4), boundary=tp_facts(T=_t(4), close=106.0))
    assert confirm.outcome == LIFECYCLE_CONFIRMED
    assert confirm.operational_facts.pullback_extreme == 97.0      # not the stale 100.0
    assert confirm.operational_facts.entry_zone_lower == 97.0
    assert confirm.operational_facts.entry_zone_upper == 106.0
    assert confirm.operational_facts.invalidation_price == 95.0


def test_a_same_boundary_update_and_confirmation_produce_exactly_one_event():
    """§36/H3: one event per (stream, episode, boundary). A boundary that is
    both a legal 15m re-evaluation and a legal 5m confirmation aggregates
    into the single CONFIRMED event."""
    creation = early_signal(tp_candidate(T=T0, pullback_extreme=100.0, current_close=105.0))
    hist = _history([creation])
    T = _t(3)                            # 12:15 — both a 15m and a 5m boundary
    decision = _decide(
        hist, T=T, boundary=tp_facts(T=T, close=104.0),
        reevaluation=_window(T=T, closes=[96.0, 103.0],
                             anchor=_TP_ANCHOR, filler=_LONG_FILLER))
    assert decision.outcome == LIFECYCLE_CONFIRMED
    # the SAME-T re-evaluation was aggregated, not emitted separately
    assert decision.operational_facts.pullback_extreme == 96.0
    assert decision.operational_facts.dynamic_bound == 104.0      # the confirming 5m close
    event = build_episode_transition_event(decision, hist, authorization=_authorization(T=T))
    after = _history([creation, event])
    assert len(after.events) == 2
    assert after.current_state == CONFIRMED


def test_a_same_boundary_update_and_expiry_produce_exactly_one_event():
    creation = early_signal(tp_candidate(T=T0, pullback_extreme=100.0, current_close=105.0))
    hist = _history([creation])
    deadline = read_candidate_deadline(hist)
    decision = _decide(
        hist, T=deadline, boundary=tp_facts(T=deadline, median=-1.0),
        reevaluation=_window(
            T=deadline, closes=[96.0, 103.0], anchor=_TP_ANCHOR, filler=_LONG_FILLER))
    assert decision.outcome == LIFECYCLE_EXPIRED_CANDIDATE_AGE
    event = build_episode_transition_event(
        decision, hist, authorization=_authorization(T=deadline))
    after = _history([creation, event])
    assert len(after.events) == 2
    assert after.current_state == EXPIRED


def test_confirmation_without_a_reference_close_does_not_freeze_a_zone():
    """§14 (amended): TREND_PULLBACK confirms only when the trigger holds AND
    §11's reference close needed to freeze the final zone is usable. The
    trigger DID hold, so the record must not call it a failed trigger -- the
    category is UNAVAILABLE with `resumption_trigger_held` preserved."""
    hist = episode(tp_candidate(T=T0))
    boundary = facts(T=_t(1), median=1.0, agreement=1.0, reference=False)
    decision = _decide(hist, T=_t(1), boundary=boundary)
    assert decision.outcome == LIFECYCLE_NO_CHANGE
    assert decision.resolution_category == SIGNAL_UNAVAILABLE
    assert decision.reason == "CONFIRMATION_CLOSE_UNAVAILABLE"
    assert decision.signal.evidence["resumption_trigger_held"] is True
    assert decision.signal.evidence["confirmation_close_available"] is False


def test_unit3_never_evaluates_a_confirmed_episode():
    """Unit 3 owns transitions OUT OF EARLY_SIGNAL only; everything after
    CONFIRMED is Unit 4's."""
    creation = early_signal(tp_candidate(T=T0))
    hist = _history([creation])
    decision = _decide(hist, T=_t(1), boundary=tp_facts(T=_t(1)))
    confirmed = build_episode_transition_event(
        decision, hist, authorization=_authorization(T=_t(1)))
    after = _history([creation, confirmed])
    with pytest.raises(V2EpisodeLifecycleError, match="post-confirmation lifecycle is Unit 4"):
        _decide(after, T=_t(2), boundary=tp_facts(T=_t(2)))


# ============================================================================
# 9. §34/§36 — canonical event construction
# ============================================================================
def test_transition_event_reuses_the_frozen_creation_identity():
    creation = early_signal(cb_candidate(T=T0, level=100.0))
    hist = _history([creation])
    decision = _decide(hist, T=_t(1), boundary=facts(T=_t(1), close=101.0))
    event = build_episode_transition_event(decision, hist, authorization=_authorization(T=_t(1)))
    assert event.episode_id == creation.episode_id
    assert event.direction == creation.direction
    assert event.setup_family == creation.setup_family
    assert dict(event.structural_anchor) == dict(creation.structural_anchor)
    assert event.decision_boundary == _t(1)
    assert event.episode_state == CONFIRMED


def test_transition_event_id_is_the_canonical_episode_boundary_pair():
    from analytics.forecasting_v2.episode_identity import compute_event_id
    creation = early_signal(cb_candidate(T=T0, level=100.0))
    hist = _history([creation])
    decision = _decide(hist, T=_t(1), boundary=facts(T=_t(1), close=101.0))
    event = build_episode_transition_event(decision, hist, authorization=_authorization(T=_t(1)))
    assert event.event_id == compute_event_id(
        episode_id=creation.episode_id, decision_boundary=_t(1))


def test_transition_event_records_auditable_by_value_evidence():
    creation = early_signal(comp_candidate(T=T0, range_high=100.0))
    hist = _history([creation])
    decision = _decide(hist, T=_t(1), boundary=facts(T=_t(1), close=99.0))
    event = build_episode_transition_event(decision, hist, authorization=_authorization(T=_t(1)))
    evidence = event.decision_snapshot[LIFECYCLE_EVIDENCE_KEY]
    assert evidence["setup_family"] == COMPRESSION_BREAKOUT
    assert evidence["t_detect"] == T0.isoformat()
    assert evidence["candidate_deadline"] == _t(3).isoformat()
    assert evidence["at_candidate_deadline"] is False
    assert evidence["signal"] == SIGNAL_FALSE_BREAK
    assert evidence["evidence"]["breakout_boundary"] == 100.0
    assert evidence["evidence"]["reference_close"] == 99.0
    transition = event.event_payload[LIFECYCLE_TRANSITION_KEY]
    assert transition["previous_state"] == EARLY_SIGNAL
    assert transition["new_state"] == INVALIDATED
    assert transition["outcome"] == LIFECYCLE_INVALIDATED_FALSE_BREAK


def test_breakout_transition_events_do_not_duplicate_creation_facts():
    """§12.2a freezes breakout operational facts at creation; re-recording
    them would create a second, competing representation."""
    creation = early_signal(comp_candidate(T=T0, range_high=100.0))
    hist = _history([creation])
    decision = _decide(hist, T=_t(1), boundary=facts(T=_t(1), close=101.0))
    event = build_episode_transition_event(decision, hist, authorization=_authorization(T=_t(1)))
    assert OPERATIONAL_FACTS_KEY not in event.event_payload


def test_no_change_never_produces_an_event():
    hist = episode(comp_candidate(T=T0, range_high=100.0))
    decision = _decide(hist, T=_t(1), boundary=facts(T=_t(1), close=100.0))
    assert decision.requires_event is False
    with pytest.raises(V2EpisodeLifecycleError, match="requires no persisted history event"):
        build_episode_transition_event(decision, hist, authorization=_authorization(T=_t(1)))


def test_publication_not_clean_is_refused():
    with pytest.raises(V2EpisodeLifecycleError, match="publication_clean must be True"):
        V2LifecycleAuthorization(provenance=_provenance(T=_t(1)), publication_clean=False)


def test_provenance_boundary_must_equal_the_decision_boundary():
    hist = episode(comp_candidate(T=T0, range_high=100.0))
    decision = _decide(hist, T=_t(1), boundary=facts(T=_t(1), close=101.0))
    with pytest.raises(V2EpisodeLifecycleError, match="does not equal this decision's T"):
        build_episode_transition_event(decision, hist, authorization=_authorization(T=_t(2)))


# ============================================================================
# 10. §3.1 — version draining must NOT block lifecycle evaluation
# ============================================================================
def _draining_state(*, T_request, run_id=RUN_ID):
    """OLD = DRAINING, NEW = PENDING, from a real switch-state machine run."""
    old = V2SemanticTuple(
        rules_version=RULES, calculation_version=H16, decision_code_version=DCV)
    new = V2SemanticTuple(
        rules_version=RULES, calculation_version="c" * 16, decision_code_version="decision-2")
    state = _switch_state(T=T0 - timedelta(minutes=30), run_id=run_id, tuple_=old)
    result = evaluate_version_switch_transition(
        state, decision_boundary=T_request, requested=new,
        drain_fact=V2DrainFact(
            run_kind=LIVE, run_id=run_id, old_tuple=old, as_of=T_request,
            non_terminal_episode_count=1, active_cooldown_count=0))
    return result.state, old, new


def test_old_episode_still_confirms_while_its_tuple_is_draining():
    """§3.1: while OLD is DRAINING it MAY and MUST continue lifecycle
    evaluation of episodes that already existed before `T_request`."""
    creation = early_signal(tp_candidate(T=T0))
    hist = _history([creation])
    state, old, _new = _draining_state(T_request=_t(1))

    # The drain is genuinely active: nothing may CREATE a new episode.
    assert active_for_new_creation(state) is None
    with pytest.raises(V2VersionSwitchError):
        assert_provenance_authorized_for_new_creation(_provenance(T=_t(2)), state)

    # ... yet the pre-existing OLD episode still transitions, under OLD's
    # own frozen tuple.
    decision = _decide(hist, T=_t(2), boundary=tp_facts(T=_t(2)))
    assert decision.outcome == LIFECYCLE_CONFIRMED
    event = build_episode_transition_event(decision, hist, authorization=_authorization(T=_t(2)))
    assert event.rules_version == old.rules_version
    assert event.calculation_version == old.calculation_version
    assert _history([creation, event]).current_state == CONFIRMED


def test_new_tuple_can_never_mutate_an_old_episode():
    """§3.1: an old episode is never reinterpreted under the new tuple.
    A NEW-tuple provenance recomputes a DIFFERENT episode_id and is refused."""
    creation = early_signal(tp_candidate(T=T0))
    hist = _history([creation])
    decision = _decide(hist, T=_t(2), boundary=tp_facts(T=_t(2)))
    new_tuple_auth = _authorization(T=_t(2), calculation_version="c" * 16)
    with pytest.raises(V2EpisodeLifecycleError, match="ORIGINAL frozen semantic tuple"):
        build_episode_transition_event(decision, hist, authorization=new_tuple_auth)


def test_a_later_decision_code_version_may_not_mutate_an_existing_episode():
    """§3.1 (amended): an episode is attributed to the semantic tuple its own
    CREATION event records, and EVERY later lifecycle transition continues
    under that tuple -- `decision_code_version` included. A
    decision-code-only release does not fork `episode_id` (§2.1a) and
    equally may not reinterpret an episode that already exists."""
    creation = early_signal(tp_candidate(T=T0))
    assert creation.decision_code_version == DCV
    hist = _history([creation])
    decision = _decide(hist, T=_t(2), boundary=tp_facts(T=_t(2)))
    with pytest.raises(V2EpisodeLifecycleError, match="CREATION semantic tuple"):
        build_episode_transition_event(
            decision, hist,
            authorization=_authorization(T=_t(2), decision_code_version="dcv-2"))


def test_the_creation_decision_code_version_is_the_one_that_continues():
    creation = early_signal(tp_candidate(T=T0))
    hist = _history([creation])
    decision = _decide(hist, T=_t(2), boundary=tp_facts(T=_t(2)))
    event = build_episode_transition_event(
        decision, hist, authorization=_authorization(T=_t(2), decision_code_version=DCV))
    assert event.episode_id == creation.episode_id
    assert event.decision_code_version == DCV == creation.decision_code_version


def test_decision_code_version_is_still_excluded_from_episode_identity():
    """The two facts are complementary: identity does not fork, and behavior
    does not drift. Two episodes differing ONLY in decision_code_version have
    the SAME episode_id -- which is exactly why §3.1's continuity rule has to
    be enforced separately."""
    a = early_signal(tp_candidate(T=T0))
    other_tuple = V2SemanticTuple(
        rules_version=RULES, calculation_version=H16, decision_code_version="dcv-2")
    b = build_early_signal_creation(
        tp_candidate(T=T0),
        authorization=V2CreationAuthorization(
            decision_view=V2DecisionView(
                provenance=_provenance(T=T0, decision_code_version="dcv-2"),
                readiness=_readiness(T=T0)),
            switch_state=_switch_state(T=T0, tuple_=other_tuple),
            publication_clean=True),
        T=T0)
    assert a.decision_code_version != b.decision_code_version
    assert a.episode_id == b.episode_id


# ============================================================================
# 11. §12.10 — LIVE/REPLAY physical isolation
# ============================================================================
def test_equivalent_episodes_in_two_streams_transition_identically():
    live = episode(cb_candidate(T=T0, level=100.0), run_kind=LIVE, run_id=RUN_ID)
    replay = episode(cb_candidate(T=T0, level=100.0), run_kind=REPLAY, run_id="replay-1")
    assert live.episode_id == replay.episode_id       # semantic ids coincide by design
    boundary = facts(T=_t(1), close=101.0)
    live_decision = _decide(live, T=_t(1), boundary=boundary)
    replay_decision = _decide(replay, T=_t(1), boundary=boundary)
    assert live_decision.outcome == replay_decision.outcome == LIFECYCLE_CONFIRMED


def test_one_stream_can_never_write_another_streams_transition():
    live = episode(cb_candidate(T=T0, level=100.0), run_kind=LIVE, run_id=RUN_ID)
    decision = _decide(live, T=_t(1), boundary=facts(T=_t(1), close=101.0))
    foreign = V2LifecycleAuthorization(
        provenance=_provenance(T=_t(1), run_kind=REPLAY, run_id="replay-1"),
        publication_clean=True)
    with pytest.raises(V2EpisodeLifecycleError, match="physically isolated"):
        build_episode_transition_event(decision, live, authorization=foreign)


def test_replay_run_id_isolation_is_preserved_in_the_event():
    replay = episode(cb_candidate(T=T0, level=100.0), run_kind=REPLAY, run_id="replay-1")
    decision = _decide(replay, T=_t(1), boundary=facts(T=_t(1), close=101.0))
    event = build_episode_transition_event(
        decision, replay,
        authorization=V2LifecycleAuthorization(
            provenance=_provenance(T=_t(1), run_kind=REPLAY, run_id="replay-1"),
            publication_clean=True))
    assert (event.run_kind, event.run_id) == (REPLAY, "replay-1")


# ============================================================================
# 12. restart equivalence — Unit 1's history is the only state
# ============================================================================
@pytest.mark.parametrize(("make", "boundary_kw"), [
    (tp_candidate, {"median": 1.0, "agreement": 1.0, "close": 106.0}),
    (comp_candidate, {"close": 101.0}),
    (cb_candidate, {"close": 101.0}),
])
def test_restart_reproduces_the_identical_transition(make, boundary_kw):
    """Persist, throw the process away, reconstruct from rows alone, and
    reach the same decision at the same T."""
    creation = early_signal(make(T=T0))
    uninterrupted = _decide(
        _history([creation]), T=_t(1), boundary=facts(T=_t(1), **boundary_kw))
    # A "fresh process": rows only, nothing carried over.
    rows = [_row(creation)]
    restarted_history = reconstruct_episode_history(
        rows, run_kind=LIVE, run_id=RUN_ID, episode_id=creation.episode_id,
        as_of=_t(500), boundary_mode=HISTORY_THROUGH_T)
    restarted = _decide(restarted_history, T=_t(1), boundary=facts(T=_t(1), **boundary_kw))
    assert restarted.outcome == uninterrupted.outcome
    assert restarted.new_state == uninterrupted.new_state
    assert restarted.t_detect == uninterrupted.t_detect
    assert restarted.candidate_deadline == uninterrupted.candidate_deadline


def test_restart_between_two_reevaluations_reproduces_the_next_result():
    creation = early_signal(tp_candidate(T=T0, pullback_extreme=100.0, current_close=105.0))
    hist = _history([creation])
    T1 = _t(3)
    d1 = _decide(hist, T=T1, boundary=tp_facts(T=T1, median=-1.0),
                 reevaluation=_window(T=T1, closes=[97.0, 103.0],
                             anchor=_TP_ANCHOR, filler=_LONG_FILLER))
    update = build_episode_transition_event(d1, hist, authorization=_authorization(T=T1))

    restarted = reconstruct_episode_history(
        [_row(creation), _row(update)], run_kind=LIVE, run_id=RUN_ID,
        episode_id=creation.episode_id, as_of=_t(500), boundary_mode=HISTORY_THROUGH_T)
    assert read_operational_facts(restarted).pullback_extreme == 97.0
    T2 = _t(6)
    d2 = _decide(restarted, T=T2, boundary=tp_facts(T=T2, median=-1.0),
                 reevaluation=_window(
                     T=T2, closes=[97.0, 95.0, 101.0], anchor=_TP_ANCHOR, filler=_LONG_FILLER))
    assert d2.outcome == LIFECYCLE_PRECONFIRMATION_UPDATE
    assert d2.operational_facts.pullback_extreme == 95.0
    assert d2.operational_facts.invalidation_price == 93.0


def test_restart_preserves_the_frozen_breakout_boundary():
    creation = early_signal(comp_candidate(T=T0, range_low=90.0, range_high=100.0))
    restarted = reconstruct_episode_history(
        [_row(creation)], run_kind=LIVE, run_id=RUN_ID, episode_id=creation.episode_id,
        as_of=_t(500), boundary_mode=HISTORY_THROUGH_T)
    signal = evaluate_family_signal(restarted, facts(T=_t(1), close=100.0))
    assert signal.signal == SIGNAL_HOLD
    assert signal.evidence["breakout_boundary"] == 100.0


# ============================================================================
# 13. fail-closed / corruption vectors
# ============================================================================
def test_terminal_episode_is_refused():
    creation = early_signal(comp_candidate(T=T0, range_high=100.0))
    hist = _history([creation])
    decision = _decide(hist, T=_t(1), boundary=facts(T=_t(1), close=50.0))
    invalidated = build_episode_transition_event(
        decision, hist, authorization=_authorization(T=_t(1)))
    after = _history([creation, invalidated])
    assert after.current_state == INVALIDATED
    with pytest.raises(V2EpisodeLifecycleError, match="terminal episodes never transition"):
        _decide(after, T=_t(2), boundary=facts(T=_t(2), close=101.0))


def test_history_must_be_a_reconstructed_unit_one_history():
    with pytest.raises(V2EpisodeLifecycleError, match="reconstructed through Unit 1"):
        evaluate_early_signal_transition(
            {"episode_state": EARLY_SIGNAL}, T=_t(1), facts=facts(T=_t(1), close=101.0))


def test_t_equal_to_t_create_is_refused():
    hist = episode(comp_candidate(T=T0))
    with pytest.raises(V2EpisodeLifecycleError, match="strictly after"):
        _decide(hist, T=T0, boundary=facts(T=T0, close=101.0))


def test_t_before_t_create_is_refused():
    hist = episode(comp_candidate(T=T0))
    with pytest.raises(V2EpisodeLifecycleError, match="strictly after"):
        _decide(hist, T=_t(-1), boundary=facts(T=_t(-1), close=101.0))


@pytest.mark.parametrize("bad", [
    T0 + timedelta(minutes=2),                    # off-grid
    T0.replace(tzinfo=None),                      # naive
    T0.astimezone(timezone(timedelta(hours=2))),  # non-UTC
])
def test_illegal_decision_boundaries_are_refused(bad):
    with pytest.raises(V2EpisodeLifecycleError):
        facts(T=bad, consensus=False, reference=False)


def test_facts_resolved_for_another_boundary_are_refused():
    hist = episode(comp_candidate(T=T0, range_high=100.0))
    with pytest.raises(V2EpisodeLifecycleError, match="ONE coherent data view"):
        evaluate_early_signal_transition(
            hist, T=_t(2), facts=facts(T=_t(1), close=101.0))


def test_facts_from_another_bucket_are_refused():
    """No-lookahead: a row for a newer/older bucket can never decide a
    transition at this T."""
    row = _reference(T=_t(1), close=101.0)
    row["bucket_ts"] = _t(1)                      # bucket END, not the selected START
    with pytest.raises(V2EpisodeLifecycleError, match="no-lookahead"):
        _boundary(T=_t(1), reference_feature_5m=row)


def test_facts_from_another_timeframe_are_refused():
    row = _reference(T=_t(1), close=101.0)
    row["timeframe"] = "15m"
    with pytest.raises(V2EpisodeLifecycleError, match="closed 5m bucket"):
        _boundary(T=_t(1), reference_feature_5m=row)


def test_missing_family_boundary_fact_fails_closed():
    """§22: a frozen structural fact is never recovered from current data."""
    event = early_signal(comp_candidate(T=T0, range_high=100.0))
    row = _row(event)
    snapshot = dict(row["decision_snapshot"])
    creation_facts = dict(snapshot["creation_facts"])
    family_facts = dict(creation_facts["family_facts"])
    del family_facts["range_high"]
    creation_facts["family_facts"] = family_facts
    snapshot["creation_facts"] = creation_facts
    row["decision_snapshot"] = snapshot
    hist = reconstruct_episode_history(
        [row], run_kind=LIVE, run_id=RUN_ID, episode_id=event.episode_id,
        as_of=_t(500), boundary_mode=HISTORY_THROUGH_T)
    with pytest.raises(V2EpisodeLifecycleError, match="refuses to re-derive it"):
        _decide(hist, T=_t(1), boundary=facts(T=_t(1), close=101.0))


def test_non_finite_confirmation_input_fails_closed():
    """A NaN/Inf is not a legal JSON leaf: it is refused at the boundary-facts
    construction boundary, never carried into a lifecycle comparison."""
    with pytest.raises(V2EpisodeLifecycleError, match="non-finite float"):
        _boundary(
            T=_t(1), consensus_5m=_consensus(T=_t(1), median=float("nan"), agreement=1.0))


def test_non_finite_reference_close_fails_closed():
    with pytest.raises(V2EpisodeLifecycleError, match="non-finite float"):
        _boundary(T=_t(1), reference_feature_5m=_reference(T=_t(1), close=float("inf")))


def test_out_of_domain_agreement_fails_closed():
    hist = episode(tp_candidate(T=T0))
    boundary = facts(T=_t(1), median=1.0, agreement=1.5)
    with pytest.raises(V2EpisodeLifecycleError, match=r"within \[0.0, 1.0\]"):
        _decide(hist, T=_t(1), boundary=boundary)


def test_decision_cannot_claim_an_edge_the_graph_forbids():
    hist = episode(tp_candidate(T=T0))
    decision = _decide(hist, T=_t(1), boundary=tp_facts(T=_t(1)))
    with pytest.raises(V2EpisodeLifecycleError, match="§13.2's graph is frozen"):
        V2LifecycleDecision(
            episode_id=decision.episode_id, T=decision.T, setup_family=TREND_PULLBACK,
            direction=LONG, previous_state=EARLY_SIGNAL, new_state="WEAKENING",
            outcome=LIFECYCLE_CONFIRMED, reason="x", signal=decision.signal,
            t_detect=T0, candidate_deadline=_t(24))


def test_false_break_outcome_is_refused_for_trend_pullback():
    hist = episode(tp_candidate(T=T0))
    decision = _decide(hist, T=_t(1), boundary=tp_facts(T=_t(1)))
    with pytest.raises(V2EpisodeLifecycleError, match="defined only for"):
        V2LifecycleDecision(
            episode_id=decision.episode_id, T=decision.T, setup_family=TREND_PULLBACK,
            direction=LONG, previous_state=EARLY_SIGNAL, new_state=INVALIDATED,
            outcome=LIFECYCLE_INVALIDATED_FALSE_BREAK, reason="x", signal=decision.signal,
            t_detect=T0, candidate_deadline=_t(24))


def test_preconfirmation_update_outcome_is_refused_for_breakout_families():
    hist = episode(comp_candidate(T=T0))
    decision = _decide(hist, T=_t(1), boundary=facts(T=_t(1), close=100.0))
    with pytest.raises(V2EpisodeLifecycleError, match="TREND_PULLBACK-only outcome"):
        V2LifecycleDecision(
            episode_id=decision.episode_id, T=decision.T, setup_family=COMPRESSION_BREAKOUT,
            direction=LONG, previous_state=EARLY_SIGNAL, new_state=EARLY_SIGNAL,
            outcome=LIFECYCLE_PRECONFIRMATION_UPDATE, reason="x", signal=decision.signal,
            t_detect=T0, candidate_deadline=_t(3))


def test_a_decision_for_another_episode_is_refused():
    a = episode(comp_candidate(T=T0, range_high=100.0))
    b = episode(cb_candidate(T=T0, level=100.0))
    decision = _decide(a, T=_t(1), boundary=facts(T=_t(1), close=101.0))
    with pytest.raises(V2EpisodeLifecycleError, match="does not describe episode"):
        build_episode_transition_event(decision, b, authorization=_authorization(T=_t(1)))


# ============================================================================
# 14. §49 — terminal episodes are never resurrected or queued
# ============================================================================
def test_unit3_queues_nothing_after_a_terminal_outcome():
    """A terminal outcome is a single immutable event; this unit has no
    retry, no queue, and no resurrection path."""
    creation = early_signal(comp_candidate(T=T0, range_high=100.0))
    hist = _history([creation])
    decision = _decide(hist, T=_t(1), boundary=facts(T=_t(1), close=99.0))
    assert decision.is_terminal is True
    event = build_episode_transition_event(decision, hist, authorization=_authorization(T=_t(1)))
    after = _history([creation, event])
    # Even a later, perfectly confirming close cannot revive it.
    with pytest.raises(V2EpisodeLifecycleError, match="terminal episodes never transition"):
        _decide(after, T=_t(2), boundary=facts(T=_t(2), close=999.0))


# ============================================================================
# 15. architecture guard
# ============================================================================
def test_unit3_never_constructs_v2_episode_event_directly():
    """The canonical construction path stays singular: this module must
    reach `V2EpisodeEvent` only through `build_v2_episode_event()`."""
    import ast
    import pathlib

    source = (
        pathlib.Path(__file__).resolve().parents[2]
        / "analytics" / "forecasting_v2" / "episode_lifecycle.py")
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


def test_unit3_reads_no_wall_clock():
    """Candidate age is logical (§1): `T - T_detect`, never processing time,
    `created_at`, or DB insertion order."""
    import ast
    import pathlib

    source = (
        pathlib.Path(__file__).resolve().parents[2]
        / "analytics" / "forecasting_v2" / "episode_lifecycle.py")
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    banned_calls = {"now", "utcnow", "today", "time", "monotonic", "perf_counter"}
    banned_names = {"created_at"}
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in banned_calls:
                offenders.append((node.func.attr, node.lineno))
        # Scanned as CODE, not prose: a docstring may legitimately explain
        # why `created_at` is never read.
        if isinstance(node, ast.Attribute) and node.attr in banned_names:
            offenders.append((node.attr, node.lineno))
        if isinstance(node, ast.Name) and node.id in banned_names:
            offenders.append((node.id, node.lineno))
        if isinstance(node, ast.Constant) and node.value in banned_names:
            offenders.append((node.value, node.lineno))
    assert offenders == []


def test_a_confirming_trigger_without_a_close_still_records_a_same_T_zone_change():
    """The trigger held but §11's reference close is UNAVAILABLE, so there is
    no `confirmation_close_price` to freeze — yet §9 still requires the
    same-`T` operational change to be recorded."""
    creation = early_signal(tp_candidate(T=T0, pullback_extreme=100.0, current_close=105.0))
    hist = _history([creation])
    T = _t(3)
    boundary = facts(T=T, median=1.0, agreement=1.0, reference=False)
    decision = _decide(
        hist, T=T, boundary=boundary,
        reevaluation=_window(T=T, closes=[96.0, 103.0],
                             anchor=_TP_ANCHOR, filler=_LONG_FILLER))
    assert decision.resolution_category == SIGNAL_UNAVAILABLE
    assert decision.signal.evidence["resumption_trigger_held"] is True
    assert decision.outcome == LIFECYCLE_PRECONFIRMATION_UPDATE
    assert decision.operational_facts.pullback_extreme == 96.0


def test_a_confirming_trigger_without_a_close_still_closes_the_deadline():
    """The deadline must never dangle: an unresolvable confirmation at the
    final eligible bucket expires, with the blocking reason recorded."""
    hist = episode(tp_candidate(T=T0))
    deadline = read_candidate_deadline(hist)
    boundary = facts(T=deadline, median=1.0, agreement=1.0, reference=False)
    decision = _decide(hist, T=deadline, boundary=boundary)
    assert decision.outcome == LIFECYCLE_EXPIRED_CANDIDATE_AGE
    assert decision.resolution_category == SIGNAL_UNAVAILABLE
    assert "CONFIRMATION_CLOSE_UNAVAILABLE" in decision.reason


# ============================================================================
# 16. the H2 aligned-input projection Unit 5 will compose through
# ============================================================================
def test_boundary_facts_project_from_a_real_aligned_input_snapshot():
    """`V2BoundaryFacts.from_aligned_inputs()` is a pure projection off the
    canonical H2 coherent read path — nothing is re-read, and the 5m rows
    arrive exactly as that snapshot resolved them for `T`."""
    from types import MappingProxyType

    from analytics.forecasting_v2.aligned_inputs import (
        ALIGNED_TIMEFRAMES, V2_REFERENCE_EXCHANGE, V2AlignedInputs, V2TimeframeInputs,
    )
    from analytics.forecasting_v2.alignment import selected_bucket

    T = _t(1)
    by_timeframe = {}
    for timeframe in ALIGNED_TIMEFRAMES:
        bucket_ts = selected_bucket(timeframe, T)
        by_timeframe[timeframe] = V2TimeframeInputs(
            timeframe=timeframe, bucket_ts=bucket_ts,
            # each timeframe's OWN bucket end, never `T` -- a 4h bucket does
            # not end at a 5m decision boundary.
            bucket_end=bucket_ts + timedelta(minutes=TIMEFRAME_MINUTES[timeframe]),
            consensus=(_consensus(T=T, median=1.0, agreement=1.0)
                       if timeframe == "5m" else None),
            percentiles=(), health={},
            reference_feature=(_reference(T=T, close=101.0) if timeframe == "5m" else None),
            reference_klines=None, reference_extrema=None)
        assert by_timeframe[timeframe].bucket_end > bucket_ts
    aligned = V2AlignedInputs(
        T=T, symbol=SYMBOL, market_type=MARKET, calculation_version=H16,
        feature_schema_version=1, reference_exchange=V2_REFERENCE_EXCHANGE,
        by_timeframe=MappingProxyType(by_timeframe))

    boundary = V2BoundaryFacts.from_aligned_inputs(aligned)
    assert boundary.T == T
    assert boundary.decision_bucket == selected_bucket("5m", T)
    assert boundary.reference_close == 101.0
    assert boundary.required_family_quality(TREND_PULLBACK) is None
    # RT-65-01: the snapshot's SEMANTIC SCOPE travels with the rows, so the
    # episode binding below has something real to check against.
    assert boundary.symbol == aligned.symbol == SYMBOL
    assert boundary.market_type == aligned.market_type == MARKET
    assert boundary.calculation_version == aligned.calculation_version == H16
    assert boundary.feature_schema_version == aligned.feature_schema_version == 1
    assert boundary.reference_exchange == aligned.reference_exchange == V2_REFERENCE_EXCHANGE

    hist = episode(cb_candidate(T=T0, level=100.0))
    assert _decide(hist, T=T, boundary=boundary).outcome == LIFECYCLE_CONFIRMED


# ============================================================================
# 17. RT-65-01 — boundary facts must retain, and be bound to, semantic scope
# ============================================================================
def test_foreign_calculation_version_facts_cannot_decide_an_episode():
    """§3.2: a decision computed from scope B may not be persisted under
    episode scope A. Checked on the INPUT side -- no downstream event
    authorization can repair an already-wrong decision."""
    hist = episode(cb_candidate(T=T0, level=100.0))
    foreign = facts(T=_t(1), close=101.0, calculation_version="c" * 16)
    with pytest.raises(V2EpisodeLifecycleError, match="different semantic scope"):
        _decide(hist, T=_t(1), boundary=foreign)


def test_foreign_feature_schema_version_facts_cannot_decide_an_episode():
    hist = episode(cb_candidate(T=T0, level=100.0))
    foreign = facts(T=_t(1), close=101.0, feature_schema_version=7)
    with pytest.raises(V2EpisodeLifecycleError, match="feature_schema_version"):
        _decide(hist, T=_t(1), boundary=foreign)


@pytest.mark.parametrize(("field", "value"), [
    ("symbol", "ETHUSDT"), ("market_type", "spot"),
])
def test_a_foreign_symbol_or_market_snapshot_is_refused(field, value):
    """V2's frozen initial scope is one instrument; a snapshot for another
    can never be constructed, let alone decide a transition."""
    with pytest.raises(V2EpisodeLifecycleError, match="unsupported"):
        facts(T=_t(1), close=101.0, **{field: value})


def test_a_foreign_reference_exchange_snapshot_is_refused():
    """§11 freezes ONE canonical V2 reference exchange and forbids silent
    switching for an exact price level."""
    with pytest.raises(V2EpisodeLifecycleError, match="canonical V2 reference exchange"):
        facts(T=_t(1), close=101.0, reference_exchange="bybit")


def test_a_row_whose_own_identity_contradicts_the_envelope_is_refused():
    """No scope laundering: a row that PHYSICALLY carries an identity field
    is checked against the envelope that claims to contain it."""
    with pytest.raises(V2EpisodeLifecycleError, match="different semantic scope"):
        facts(T=_t(1), close=101.0, row_scope={"calculation_version": "c" * 16})


def test_a_reference_row_from_a_foreign_exchange_is_refused():
    row = _reference(T=_t(1), close=101.0, scope={"exchange": "okx"})
    with pytest.raises(V2EpisodeLifecycleError, match="different semantic scope"):
        _boundary(T=_t(1), reference_feature_5m=row)


def test_matching_scope_transitions_normally():
    hist = episode(cb_candidate(T=T0, level=100.0))
    decision = _decide(hist, T=_t(1), boundary=facts(T=_t(1), close=101.0))
    assert decision.outcome == LIFECYCLE_CONFIRMED
    event = build_episode_transition_event(decision, hist, authorization=_authorization(T=_t(1)))
    assert event.calculation_version == hist.creation_identity.calculation_version


# ============================================================================
# 18. CR65-3 — a PRESENT §11 row missing a gate field is corruption
# ============================================================================
@pytest.mark.parametrize("field", ["bars_expected", "bars_present", "is_usable",
                                   "has_gap", "close_price"])
def test_a_present_reference_row_missing_a_gate_field_is_corruption(field):
    hist = episode(comp_candidate(T=T0, range_high=100.0))
    boundary = _boundary(
        T=_t(1), consensus_5m=_consensus(T=_t(1)),
        reference_feature_5m=_reference(T=_t(1), close=101.0, drop=(field,)))
    with pytest.raises(V2EpisodeLifecycleError, match="corruption, not absence"):
        _decide(hist, T=_t(1), boundary=boundary)


def test_a_wholly_absent_reference_row_stays_ordinary_unavailability():
    """The two categories must not be conflated: an ABSENT row is §21
    Unavailable, a PRESENT malformed one is corruption."""
    hist = episode(comp_candidate(T=T0, range_high=100.0))
    decision = _decide(hist, T=_t(1), boundary=facts(T=_t(1), reference=False))
    assert decision.signal.signal == SIGNAL_UNAVAILABLE
    assert decision.outcome == LIFECYCLE_NO_CHANGE


# ============================================================================
# 19. RT-65-05 — §21's categories stay distinct
# ============================================================================
def test_present_but_null_family_quality_is_unavailable():
    hist = episode(comp_candidate(T=T0, range_high=100.0))
    decision = _decide(
        hist, T=_t(1),
        boundary=facts(T=_t(1), close=101.0, null_families=("price_structure",)))
    assert decision.signal.signal == SIGNAL_UNAVAILABLE
    assert decision.signal.reason == "REQUIRED_FAMILY_QUALITY_UNAVAILABLE"


def test_coverage_below_the_floor_is_rejected_not_unavailable():
    hist = episode(comp_candidate(T=T0, range_high=100.0))
    boundary = _boundary(
        T=_t(1),
        consensus_5m=_consensus(T=_t(1), degraded_families=("price_structure",)),
        reference_feature_5m=_reference(T=_t(1), close=101.0))
    decision = _decide(hist, T=_t(1), boundary=boundary)
    assert decision.signal.signal == SIGNAL_REJECTED
    assert decision.signal.evidence["coverage_ratio"] == 0.5
    assert decision.signal.evidence["min_coverage"] == pytest.approx(2 / 3)


def test_confidence_below_the_floor_is_rejected():
    hist = episode(comp_candidate(T=T0, range_high=100.0))
    row = _consensus(T=_t(1))
    row["data_confidence_by_metric"] = dict(row["data_confidence_by_metric"])
    row["data_confidence_by_metric"]["price_structure"] = 20.0
    boundary = _boundary(
        T=_t(1), consensus_5m=row,
        reference_feature_5m=_reference(T=_t(1), close=101.0))
    decision = _decide(hist, T=_t(1), boundary=boundary)
    assert decision.signal.signal == SIGNAL_REJECTED
    assert decision.signal.reason == "REQUIRED_FAMILY_CONFIDENCE_BELOW_FLOOR"


def test_a_usable_reference_close_does_not_rescue_a_failed_family_gate():
    """§6.3a's frozen consequence: a failed REQUIRED-family gate makes the
    whole predicate unevaluable. Another present input does not
    independently rescue it."""
    hist = episode(comp_candidate(T=T0, range_high=100.0))
    boundary = facts(T=_t(1), close=101.0, price_structure_ok=False)
    assert boundary.reference_close == 101.0          # present and usable
    decision = _decide(hist, T=_t(1), boundary=boundary)
    assert decision.signal.signal == SIGNAL_REJECTED
    assert decision.outcome == LIFECYCLE_NO_CHANGE    # NOT confirmed


def test_intermediate_unevaluable_boundary_produces_no_transition():
    hist = episode(cb_candidate(T=T0, level=100.0))
    for boundary in (facts(T=_t(1), close=101.0, price_structure_ok=False),
                     facts(T=_t(1), consensus=False, reference=False)):
        decision = _decide(hist, T=_t(1), boundary=boundary)
        assert decision.outcome == LIFECYCLE_NO_CHANGE
        assert decision.requires_event is False


def test_the_persisted_event_records_the_resolution_category():
    """§14/§21: an EXPIRED event must not read as a neutral HOLD when the
    truth was a disqualified input."""
    hist = episode(comp_candidate(T=T0, range_high=100.0))
    deadline = read_candidate_deadline(hist)
    decision = _decide(
        hist, T=deadline, boundary=facts(T=deadline, close=101.0, price_structure_ok=False))
    event = build_episode_transition_event(
        decision, hist, authorization=_authorization(T=deadline))
    evidence = event.decision_snapshot[LIFECYCLE_EVIDENCE_KEY]
    assert evidence["resolution_category"] == SIGNAL_REJECTED
    assert evidence["at_candidate_deadline"] is True
    assert event.episode_state == EXPIRED


# ============================================================================
# 20. RT-65-07 — a public path may never persist contradictory history
# ============================================================================
def _signal(kind, reason="fixture"):
    return type(_decide(
        episode(comp_candidate(T=T0, range_high=100.0)), T=_t(1),
        boundary=facts(T=_t(1), close=100.0)).signal)(
            signal=kind, reason=reason, evidence={})


def _decision(**over):
    base = dict(
        episode_id="e" * 64, T=_t(1), setup_family=COMPRESSION_BREAKOUT, direction=LONG,
        previous_state=EARLY_SIGNAL, new_state=CONFIRMED, outcome=LIFECYCLE_CONFIRMED,
        reason="x", signal=_signal(SIGNAL_CONFIRM), t_detect=T0, candidate_deadline=_t(3))
    base.update(over)
    return V2LifecycleDecision(**base)


@pytest.mark.parametrize(("outcome", "new_state", "bad_signal"), [
    (LIFECYCLE_CONFIRMED, CONFIRMED, SIGNAL_HOLD),
    (LIFECYCLE_CONFIRMED, CONFIRMED, SIGNAL_UNAVAILABLE),
    (LIFECYCLE_CONFIRMED, CONFIRMED, SIGNAL_REJECTED),
    (LIFECYCLE_INVALIDATED_FALSE_BREAK, INVALIDATED, SIGNAL_CONFIRM),
    (LIFECYCLE_INVALIDATED_FALSE_BREAK, INVALIDATED, SIGNAL_HOLD),
    (LIFECYCLE_EXPIRED_CANDIDATE_AGE, EXPIRED, SIGNAL_CONFIRM),
    (LIFECYCLE_EXPIRED_CANDIDATE_AGE, EXPIRED, SIGNAL_FALSE_BREAK),
])
def test_a_transition_may_never_contradict_its_own_signal(outcome, new_state, bad_signal):
    with pytest.raises(V2EpisodeLifecycleError, match="not reachable from family signal"):
        _decision(outcome=outcome, new_state=new_state, signal=_signal(bad_signal),
                  T=_t(3) if outcome == LIFECYCLE_EXPIRED_CANDIDATE_AGE else _t(1))


def test_expiry_before_the_deadline_is_refused():
    with pytest.raises(V2EpisodeLifecycleError, match="deadline boundary itself closes"):
        _decision(outcome=LIFECYCLE_EXPIRED_CANDIDATE_AGE, new_state=EXPIRED,
                  signal=_signal(SIGNAL_HOLD), T=_t(1), candidate_deadline=_t(3))


def test_a_decision_beyond_the_deadline_is_refused():
    with pytest.raises(V2EpisodeLifecycleError, match="beyond the §14 candidate deadline"):
        _decision(T=_t(4), candidate_deadline=_t(3))


def test_a_decision_at_or_before_t_detect_is_refused():
    with pytest.raises(V2EpisodeLifecycleError, match="strictly after t_detect"):
        _decision(T=T0, t_detect=T0)


@pytest.mark.parametrize("field", ["setup_family", "direction", "t_detect",
                                   "candidate_deadline", "episode_id"])
def test_a_decision_contradicting_its_history_cannot_be_persisted(field):
    """The event's COLUMNS come from history while its EVIDENCE comes from the
    decision -- so a hand-built decision must not be able to make the two
    tell different stories."""
    hist = episode(comp_candidate(T=T0, range_high=100.0))
    good = _decide(hist, T=_t(1), boundary=facts(T=_t(1), close=101.0))
    over = {
        "setup_family": CONFIRMED_BREAKOUT, "direction": SHORT,
        "t_detect": _t(-1), "candidate_deadline": _t(2), "episode_id": "f" * 64,
    }[field]
    kwargs = dict(
        episode_id=good.episode_id, T=good.T, setup_family=good.setup_family,
        direction=good.direction, previous_state=EARLY_SIGNAL, new_state=CONFIRMED,
        outcome=LIFECYCLE_CONFIRMED, reason="x", signal=good.signal,
        t_detect=good.t_detect, candidate_deadline=good.candidate_deadline)
    kwargs[field] = over
    if field == "t_detect":
        kwargs["candidate_deadline"] = over + timedelta(minutes=15)
    forged = V2LifecycleDecision(**kwargs)
    with pytest.raises(V2EpisodeLifecycleError, match="does not describe episode"):
        build_episode_transition_event(forged, hist, authorization=_authorization(T=_t(1)))


def test_a_trend_pullback_confirmation_without_final_geometry_is_impossible():
    """§7.1/§9: the frozen final entry zone is part of the record."""
    with pytest.raises(V2EpisodeLifecycleError, match="carries no operational facts"):
        _decision(setup_family=TREND_PULLBACK, candidate_deadline=_t(24),
                  operational_facts=None)


def test_a_breakout_decision_may_not_carry_operational_facts():
    hist = episode(tp_candidate(T=T0))
    tp = _decide(hist, T=_t(1), boundary=tp_facts(T=_t(1)))
    with pytest.raises(V2EpisodeLifecycleError, match="no §12.2a pre-confirmation"):
        _decision(operational_facts=tp.operational_facts)


def test_a_confirmed_tp_must_freeze_against_the_confirming_close():
    hist = episode(tp_candidate(T=T0))
    reeval_sourced = derive_trend_pullback_reevaluation(
        hist, _window(T=_t(3), closes=[97.0, 103.0], anchor=_TP_ANCHOR,
                      filler=_LONG_FILLER))
    assert reeval_sourced.source == OPERATIONAL_SOURCE_REEVALUATION
    with pytest.raises(V2EpisodeLifecycleError, match="CONFIRMING 5m"):
        _decision(setup_family=TREND_PULLBACK, candidate_deadline=_t(24),
                  operational_facts=reeval_sourced)


# ============================================================================
# 21. RT-65-08 — persisted operational facts fail closed on contradiction
# ============================================================================
def _tp_update_event(*, extreme=97.0, T=_t(3)):
    creation = early_signal(tp_candidate(T=T0, pullback_extreme=100.0, current_close=105.0))
    hist = _history([creation])
    decision = _decide(
        hist, T=T, boundary=tp_facts(T=T, median=-1.0),
        reevaluation=_window(T=T, closes=[extreme, 103.0], anchor=_TP_ANCHOR,
                             filler=_LONG_FILLER))
    return creation, build_episode_transition_event(
        decision, hist, authorization=_authorization(T=T))


def _history_with_mutated_operational_block(mutate):
    creation, update = _tp_update_event()
    row = _row(update)
    payload = dict(row["event_payload"])
    block = dict(payload[OPERATIONAL_FACTS_KEY])
    mutate(block)
    payload[OPERATIONAL_FACTS_KEY] = block
    row["event_payload"] = payload
    return reconstruct_episode_history(
        [_row(creation), row], run_kind=LIVE, run_id=RUN_ID,
        episode_id=creation.episode_id, as_of=_t(500), boundary_mode=HISTORY_THROUGH_T)


def test_a_healthy_persisted_operational_block_reads_back_exactly():
    creation, update = _tp_update_event()
    after = _history([creation, update])
    now = read_operational_facts(after)
    assert now.pullback_extreme == 97.0
    assert now.invalidation_price == 95.0
    assert now.source == OPERATIONAL_SOURCE_REEVALUATION


@pytest.mark.parametrize(("field", "value", "match"), [
    ("invalidation_price", 1.0, "never silently normalized"),
    ("entry_zone_lower", 42.0, "never silently normalized"),
    ("entry_zone_upper", 999.0, "never silently normalized"),
    ("protection_buffer", "17", "frozen creation protection_buffer"),
])
def test_contradictory_persisted_geometry_fails_closed(field, value, match):
    hist = _history_with_mutated_operational_block(lambda b: b.__setitem__(field, value))
    with pytest.raises(V2EpisodeLifecycleError, match=match):
        read_operational_facts(hist)


@pytest.mark.parametrize("field", ["invalidation_price", "entry_zone_lower",
                                   "entry_zone_upper", "protection_buffer"])
def test_a_missing_persisted_geometry_field_fails_closed(field):
    hist = _history_with_mutated_operational_block(lambda b: b.pop(field))
    with pytest.raises(V2EpisodeLifecycleError, match="carry no"):
        read_operational_facts(hist)


def test_an_unknown_operational_source_fails_closed():
    hist = _history_with_mutated_operational_block(
        lambda b: b.__setitem__("source", "SOMETHING_ELSE"))
    with pytest.raises(V2EpisodeLifecycleError, match="not one of"):
        read_operational_facts(hist)


@pytest.mark.parametrize(("value", "match"), [
    ("2026-08-20T12:00:00", "is naive"),
    ("2026-08-20T14:00:00+02:00", "is not UTC"),
    ("not-a-timestamp", "not a parseable"),
    ("2026-08-20T12:07:00+00:00", "not a legal 15m bucket start"),
    ("2026-08-20T12:05:00+00:00", "15m bucket grid"),
])
def test_a_malformed_persisted_source_bucket_fails_closed(value, match):
    hist = _history_with_mutated_operational_block(
        lambda b: b.__setitem__("source_bucket", value))
    with pytest.raises(V2EpisodeLifecycleError, match=match):
        read_operational_facts(hist)


def test_a_future_persisted_source_bucket_fails_closed():
    """No-lookahead (§1/§2): a fact recorded at `T` cannot have been measured
    from a bucket that had not closed by `T`."""
    hist = _history_with_mutated_operational_block(
        lambda b: b.__setitem__("source_bucket", _q(4).isoformat()))
    with pytest.raises(V2EpisodeLifecycleError, match="had not closed by then"):
        read_operational_facts(hist)


def test_a_source_bucket_on_the_wrong_grid_for_its_source_fails_closed():
    """A CONFIRMATION records the confirming 5m bucket; a REEVALUATION
    records §7.1's 15m `B15'`. Mixing them is impossible history."""
    hist = _history_with_mutated_operational_block(
        lambda b: b.update(source=OPERATIONAL_SOURCE_CONFIRMATION))
    with pytest.raises(V2EpisodeLifecycleError, match="selected 5m bucket"):
        read_operational_facts(hist)


def test_a_source_bucket_from_another_boundary_fails_closed():
    hist = _history_with_mutated_operational_block(
        lambda b: b.__setitem__("source_bucket", _q(-4).isoformat()))
    with pytest.raises(V2EpisodeLifecycleError, match="selects exactly one bucket"):
        read_operational_facts(hist)


def test_a_missing_persisted_source_bucket_fails_closed():
    hist = _history_with_mutated_operational_block(lambda b: b.pop("source_bucket"))
    with pytest.raises(V2EpisodeLifecycleError, match="what makes it"):
        read_operational_facts(hist)


def test_contradictory_creation_geometry_fails_closed():
    """Unit 2's own persisted creation geometry is held to §7.1's formula
    too -- a creation event whose zone contradicts its own extreme/buffer is
    corrupt, not something to normalize away."""
    event = early_signal(tp_candidate(T=T0, pullback_extreme=100.0, current_close=105.0))
    row = _row(event)
    snapshot = dict(row["decision_snapshot"])
    creation_facts = dict(snapshot["creation_facts"])
    creation_facts["invalidation_price"] = 1.0
    snapshot["creation_facts"] = creation_facts
    row["decision_snapshot"] = snapshot
    hist = reconstruct_episode_history(
        [row], run_kind=LIVE, run_id=RUN_ID, episode_id=event.episode_id,
        as_of=_t(500), boundary_mode=HISTORY_THROUGH_T)
    with pytest.raises(V2EpisodeLifecycleError, match="never silently normalized"):
        read_operational_facts(hist)
