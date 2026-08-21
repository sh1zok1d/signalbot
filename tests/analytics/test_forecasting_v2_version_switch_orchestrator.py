"""V2-H2b orchestration-boundary tests
(`analytics/forecasting_v2/version_switch_orchestrator.py`).

No real DB -- deterministic fakes for `V2SetupHistoryReader` (readiness)
and `V2VersionDrainStatusReader` (drain), matching the existing V2 fake-
reader test style (`test_forecasting_v2_activation_readiness.py`'s
`FakePercentileReader`/`RaisingReader`). Covers: the readiness-gating half
of task vectors 3/4/5, vector 10 (reader/readiness corruption fails
closed, never interpreted as NOT_READY/NOT_DRAINED) for BOTH ports this
orchestration layer depends on, and tech-lead amendment round 1's
findings 1/2/3 as they surface at the orchestration boundary (LIVE-only
routing, initial-provisioning routing, self-scoped V2DrainFact
construction)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from analytics.forecasting_v2.activation_readiness import MANDATORY_PERCENTILE_COVERAGE
from analytics.forecasting_v2.alignment import selected_bucket
from analytics.forecasting_v2.version_switch import (
    ACTION_ACTIVATED, ACTION_AWAITING_READINESS, ACTION_DRAIN_COMPLETE,
    ACTION_DRAIN_CONTINUES, ACTION_INITIAL_ACTIVATED,
    ACTION_INITIAL_PROVISION_AWAITING_READINESS, ACTION_NO_OP,
    PHASE_AWAITING_ACTIVATION_READINESS, PHASE_DRAINING, PHASE_NO_PENDING_SWITCH,
    V2DrainFact, V2SemanticTuple, V2VersionSwitchError, V2VersionSwitchState,
    initial_switch_state,
)
from analytics.forecasting_v2.version_switch_orchestrator import (
    resolve_version_switch_transition,
)

UTC = timezone.utc
SYMBOL = "BTCUSDT"
MARKET_TYPE = "perp"
T0 = datetime(2026, 8, 20, 0, 0, tzinfo=UTC)
RUN_KIND = "LIVE"
RUN_ID = "v2-shadow-live"

OLD = V2SemanticTuple(
    rules_version="v2-rules-v0.1.0", calculation_version="a" * 16,
    decision_code_version="decision-code-1")
NEW = V2SemanticTuple(
    rules_version="v2-rules-v0.2.0", calculation_version="b" * 16,
    decision_code_version="decision-code-2")


def _t(n: int) -> datetime:
    return T0 + timedelta(minutes=5 * n)


def _run(coro):
    return asyncio.run(coro)


def _steady_state(active=OLD, run_kind=RUN_KIND, run_id=RUN_ID) -> V2VersionSwitchState:
    return V2VersionSwitchState(
        run_kind=run_kind, run_id=run_id, active=active, pending=None,
        phase=PHASE_NO_PENDING_SWITCH, drain_complete_at=None, requested_at=None)


def _drain(*, non_terminal=0, cooldown=0, run_kind=RUN_KIND, run_id=RUN_ID,
           old_tuple=OLD, as_of) -> V2DrainFact:
    return V2DrainFact(
        run_kind=run_kind, run_id=run_id, old_tuple=old_tuple, as_of=as_of,
        non_terminal_episode_count=non_terminal, active_cooldown_count=cooldown)


# ---- fake readiness reader (V2SetupHistoryReader) ----------------------------

def _pctl_row(*, bucket_ts, value=1.0, percentile_rank=0.5, confidence_tier="mature"):
    return {"bucket_ts": bucket_ts, "value": value, "percentile_rank": percentile_rank,
            "confidence_tier": confidence_tier}


def _ready_rows_for_all(*, decision_boundary: datetime) -> dict:
    return {
        (req.metric, req.timeframe, req.percentile_window):
            (_pctl_row(bucket_ts=selected_bucket(req.timeframe, decision_boundary)),)
        for req in MANDATORY_PERCENTILE_COVERAGE
    }


class FakeReadinessReader:
    """Satisfies `V2SetupHistoryReader` structurally. `ready=True` returns a
    usable row for every mandatory requirement at `decision_boundary`;
    `ready=False` returns nothing for all of them (NOT_READY, legitimately
    -- never an error)."""
    def __init__(self, *, ready: bool, decision_boundary: datetime):
        self._rows = _ready_rows_for_all(decision_boundary=decision_boundary) if ready else {}
        self.calls: list = []

    async def fetch_v2_consensus_percentile_window(self, **kw):
        self.calls.append(kw)
        key = (kw["metric"], kw["timeframe"], kw["percentile_window"])
        return self._rows.get(key, ())

    async def fetch_v2_consensus_feature_window(self, **kw):
        raise AssertionError("must not be called")

    async def fetch_v2_reference_feature_window(self, **kw):
        raise AssertionError("must not be called")

    async def fetch_v2_reference_klines(self, **kw):
        raise AssertionError("must not be called")

    async def fetch_v2_instrument(self, **kw):
        raise AssertionError("must not be called")


class RaisingReadinessReader:
    """A genuinely corrupted/erroring reader -- must propagate, never be
    downgraded to a soft NOT_READY."""
    class Boom(RuntimeError):
        pass

    async def fetch_v2_consensus_percentile_window(self, **kw):
        raise self.Boom("corrupted percentile_snapshots row")

    async def fetch_v2_consensus_feature_window(self, **kw):
        raise AssertionError("must not be called")

    async def fetch_v2_reference_feature_window(self, **kw):
        raise AssertionError("must not be called")

    async def fetch_v2_reference_klines(self, **kw):
        raise AssertionError("must not be called")

    async def fetch_v2_instrument(self, **kw):
        raise AssertionError("must not be called")


def _never_called_readiness_reader():
    class _Reader:
        async def fetch_v2_consensus_percentile_window(self, **kw):
            raise AssertionError("readiness must not be queried in this scenario")
    return _Reader()


# ---- fake drain reader (V2VersionDrainStatusReader) --------------------------

class FakeDrainReader:
    """Returns a properly SELF-SCOPED V2DrainFact (finding 3) -- matching
    the exact run_kind/run_id/old_tuple/as_of it was called with, as a
    real Stage-6-backed implementation would have to."""
    def __init__(self, *, non_terminal=0, cooldown=0):
        self._non_terminal = non_terminal
        self._cooldown = cooldown
        self.calls: list = []

    async def fetch_v2_version_drain_status(self, **kw):
        self.calls.append(kw)
        return V2DrainFact(
            run_kind=kw["run_kind"], run_id=kw["run_id"],
            old_tuple=V2SemanticTuple(
                rules_version=kw["rules_version"],
                calculation_version=kw["calculation_version"],
                decision_code_version=kw["decision_code_version"]),
            as_of=kw["as_of"],
            non_terminal_episode_count=self._non_terminal,
            active_cooldown_count=self._cooldown)


class MisscopedDrainReader:
    """A misbehaving reader that returns a V2DrainFact for the WRONG
    as_of boundary -- must be caught and rejected by the pure function's
    own scope check, never silently trusted (finding 3)."""
    async def fetch_v2_version_drain_status(self, **kw):
        return V2DrainFact(
            run_kind=kw["run_kind"], run_id=kw["run_id"],
            old_tuple=V2SemanticTuple(
                rules_version=kw["rules_version"],
                calculation_version=kw["calculation_version"],
                decision_code_version=kw["decision_code_version"]),
            as_of=kw["as_of"] + timedelta(minutes=5),  # WRONG on purpose.
            non_terminal_episode_count=0, active_cooldown_count=0)


class RaisingDrainReader:
    class Boom(RuntimeError):
        pass

    async def fetch_v2_version_drain_status(self, **kw):
        raise self.Boom("corrupted episode-history state")


def _never_called_drain_reader():
    class _Reader:
        async def fetch_v2_version_drain_status(self, **kw):
            raise AssertionError("drain status must not be queried in this scenario")
    return _Reader()


# ---- end-to-end: DRAINING -> AWAITING_ACTIVATION_READINESS -> ACTIVATED -----

def test_orchestrator_full_flow_drains_then_activates_once_ready():
    state = _steady_state()
    drain_reader = FakeDrainReader(non_terminal=1)

    r1 = _run(resolve_version_switch_transition(
        state=state, decision_boundary=_t(0), symbol=SYMBOL, market_type=MARKET_TYPE,
        requested=NEW, readiness_reader=_never_called_readiness_reader(),
        drain_reader=drain_reader))
    assert r1.action == ACTION_DRAIN_CONTINUES
    assert len(drain_reader.calls) == 1

    drain_reader_2 = FakeDrainReader()
    r2 = _run(resolve_version_switch_transition(
        state=r1.state, decision_boundary=_t(1), symbol=SYMBOL, market_type=MARKET_TYPE,
        requested=None, readiness_reader=_never_called_readiness_reader(),
        drain_reader=drain_reader_2))
    assert r2.action == ACTION_DRAIN_COMPLETE
    assert r2.state.phase == PHASE_AWAITING_ACTIVATION_READINESS

    readiness_reader = FakeReadinessReader(ready=True, decision_boundary=_t(2))
    r3 = _run(resolve_version_switch_transition(
        state=r2.state, decision_boundary=_t(2), symbol=SYMBOL, market_type=MARKET_TYPE,
        requested=None, readiness_reader=readiness_reader,
        drain_reader=_never_called_drain_reader()))
    assert r3.action == ACTION_ACTIVATED
    assert r3.state.active == NEW
    # Readiness was queried for NEW's calculation_version, not OLD's.
    assert all(c["calculation_version"] == NEW.calculation_version for c in readiness_reader.calls)


def test_orchestrator_stays_awaiting_when_not_ready():
    state = V2VersionSwitchState(
        run_kind=RUN_KIND, run_id=RUN_ID, active=OLD, pending=NEW,
        phase=PHASE_AWAITING_ACTIVATION_READINESS, drain_complete_at=_t(0),
        requested_at=_t(0))
    readiness_reader = FakeReadinessReader(ready=False, decision_boundary=_t(1))
    result = _run(resolve_version_switch_transition(
        state=state, decision_boundary=_t(1), symbol=SYMBOL, market_type=MARKET_TYPE,
        requested=None, readiness_reader=readiness_reader,
        drain_reader=_never_called_drain_reader()))
    assert result.action == ACTION_AWAITING_READINESS
    assert result.state.active == OLD


# ---- efficiency: never query a fact this call could not possibly need ------

def test_orchestrator_never_queries_readiness_while_draining():
    state = _steady_state()
    drain_reader = FakeDrainReader(non_terminal=1)
    result = _run(resolve_version_switch_transition(
        state=state, decision_boundary=_t(0), symbol=SYMBOL, market_type=MARKET_TYPE,
        requested=NEW, readiness_reader=_never_called_readiness_reader(),
        drain_reader=drain_reader))
    assert result.action == ACTION_DRAIN_CONTINUES


def test_orchestrator_never_queries_drain_once_awaiting_readiness():
    state = V2VersionSwitchState(
        run_kind=RUN_KIND, run_id=RUN_ID, active=OLD, pending=NEW,
        phase=PHASE_AWAITING_ACTIVATION_READINESS, drain_complete_at=_t(0),
        requested_at=_t(0))
    readiness_reader = FakeReadinessReader(ready=True, decision_boundary=_t(1))
    result = _run(resolve_version_switch_transition(
        state=state, decision_boundary=_t(1), symbol=SYMBOL, market_type=MARKET_TYPE,
        requested=None, readiness_reader=readiness_reader,
        drain_reader=_never_called_drain_reader()))
    assert result.action == ACTION_ACTIVATED


def test_orchestrator_no_op_queries_nothing():
    state = _steady_state()
    result = _run(resolve_version_switch_transition(
        state=state, decision_boundary=_t(0), symbol=SYMBOL, market_type=MARKET_TYPE,
        requested=None, readiness_reader=_never_called_readiness_reader(),
        drain_reader=_never_called_drain_reader()))
    assert result.action == ACTION_NO_OP


def test_orchestrator_same_boundary_as_drain_complete_never_queries_readiness():
    state = _steady_state()
    drain_reader = FakeDrainReader()
    result = _run(resolve_version_switch_transition(
        state=state, decision_boundary=_t(0), symbol=SYMBOL, market_type=MARKET_TYPE,
        requested=NEW, readiness_reader=_never_called_readiness_reader(),
        drain_reader=drain_reader))
    assert result.action == ACTION_DRAIN_COMPLETE
    assert result.state.active == OLD


# ---- finding 2: initial provisioning routed separately, always via readiness

def test_orchestrator_routes_fresh_stream_request_to_initial_provisioning():
    state = initial_switch_state(run_kind=RUN_KIND, run_id=RUN_ID)
    readiness_reader = FakeReadinessReader(ready=True, decision_boundary=_t(0))
    result = _run(resolve_version_switch_transition(
        state=state, decision_boundary=_t(0), symbol=SYMBOL, market_type=MARKET_TYPE,
        requested=OLD, readiness_reader=readiness_reader,
        drain_reader=_never_called_drain_reader()))
    assert result.action == ACTION_INITIAL_ACTIVATED
    assert result.state.active == OLD  # no drain phase, no +5m delay.


def test_orchestrator_initial_provisioning_not_ready_stays_none():
    state = initial_switch_state(run_kind=RUN_KIND, run_id=RUN_ID)
    readiness_reader = FakeReadinessReader(ready=False, decision_boundary=_t(0))
    result = _run(resolve_version_switch_transition(
        state=state, decision_boundary=_t(0), symbol=SYMBOL, market_type=MARKET_TYPE,
        requested=OLD, readiness_reader=readiness_reader,
        drain_reader=_never_called_drain_reader()))
    assert result.action == ACTION_INITIAL_PROVISION_AWAITING_READINESS
    assert result.state.active is None


def test_orchestrator_initial_provisioning_works_for_replay():
    state = initial_switch_state(run_kind="REPLAY", run_id="replay-2026-08-20-001")
    readiness_reader = FakeReadinessReader(ready=True, decision_boundary=_t(0))
    result = _run(resolve_version_switch_transition(
        state=state, decision_boundary=_t(0), symbol=SYMBOL, market_type=MARKET_TYPE,
        requested=OLD, readiness_reader=readiness_reader,
        drain_reader=_never_called_drain_reader()))
    assert result.action == ACTION_INITIAL_ACTIVATED
    assert result.state.active == OLD


def test_orchestrator_no_request_on_fresh_stream_is_no_op_queries_nothing():
    state = initial_switch_state(run_kind=RUN_KIND, run_id=RUN_ID)
    result = _run(resolve_version_switch_transition(
        state=state, decision_boundary=_t(0), symbol=SYMBOL, market_type=MARKET_TYPE,
        requested=None, readiness_reader=_never_called_readiness_reader(),
        drain_reader=_never_called_drain_reader()))
    assert result.action == ACTION_NO_OP
    assert result.state.active is None


# ---- finding 1: REPLAY never routed through switch machinery ---------------

def test_orchestrator_replay_switch_request_propagates_refusal():
    state = _steady_state(run_kind="REPLAY", run_id="replay-2026-08-20-001")
    with pytest.raises(V2VersionSwitchError, match="LIVE-only|REPLAY"):
        _run(resolve_version_switch_transition(
            state=state, decision_boundary=_t(0), symbol=SYMBOL, market_type=MARKET_TYPE,
            requested=NEW, readiness_reader=_never_called_readiness_reader(),
            drain_reader=_never_called_drain_reader()))


# ---- vector 10: reader/readiness corruption fails closed --------------------

def test_orchestrator_propagates_drain_reader_exception_unchanged():
    state = _steady_state()
    with pytest.raises(RaisingDrainReader.Boom):
        _run(resolve_version_switch_transition(
            state=state, decision_boundary=_t(0), symbol=SYMBOL, market_type=MARKET_TYPE,
            requested=NEW, readiness_reader=_never_called_readiness_reader(),
            drain_reader=RaisingDrainReader()))


def test_orchestrator_propagates_readiness_reader_exception_unchanged():
    state = V2VersionSwitchState(
        run_kind=RUN_KIND, run_id=RUN_ID, active=OLD, pending=NEW,
        phase=PHASE_AWAITING_ACTIVATION_READINESS, drain_complete_at=_t(0),
        requested_at=_t(0))
    with pytest.raises(RaisingReadinessReader.Boom):
        _run(resolve_version_switch_transition(
            state=state, decision_boundary=_t(1), symbol=SYMBOL, market_type=MARKET_TYPE,
            requested=None, readiness_reader=RaisingReadinessReader(),
            drain_reader=_never_called_drain_reader()))


# ---- finding 3: a misscoped drain fact is rejected by the pure function ----

def test_orchestrator_propagates_scope_mismatch_from_misbehaving_drain_reader():
    state = _steady_state()
    with pytest.raises(V2VersionSwitchError, match="as_of"):
        _run(resolve_version_switch_transition(
            state=state, decision_boundary=_t(0), symbol=SYMBOL, market_type=MARKET_TYPE,
            requested=NEW, readiness_reader=_never_called_readiness_reader(),
            drain_reader=MisscopedDrainReader()))


# ---- scope: drain query never carries symbol/market_type --------------------

def test_orchestrator_drain_query_scoped_only_to_execution_stream_and_old_tuple():
    state = _steady_state()
    drain_reader = FakeDrainReader(non_terminal=1)
    _run(resolve_version_switch_transition(
        state=state, decision_boundary=_t(0), symbol=SYMBOL, market_type=MARKET_TYPE,
        requested=NEW, readiness_reader=_never_called_readiness_reader(),
        drain_reader=drain_reader))
    assert len(drain_reader.calls) == 1
    call = drain_reader.calls[0]
    assert call["run_kind"] == RUN_KIND
    assert call["run_id"] == RUN_ID
    assert call["rules_version"] == OLD.rules_version
    assert call["calculation_version"] == OLD.calculation_version
    assert call["decision_code_version"] == OLD.decision_code_version
    assert call["as_of"] == _t(0)
    assert "symbol" not in call
    assert "market_type" not in call
