"""Tests for analytics/forecasting_v2/decision_view.py's V2DecisionView /
resolve_decision_view()."""
from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

import pytest

from analytics.forecasting_v2.activation_readiness import (
    MANDATORY_PERCENTILE_COVERAGE, V2ActivationReadinessResult, V2CoverageStatus,
)
from analytics.forecasting_v2.decision_provenance import V2DecisionProvenance
from analytics.forecasting_v2.decision_view import (
    V2DecisionView, V2DecisionViewError, resolve_decision_view,
)
from analytics.forecasting_v2.events import LIVE

H64 = "a" * 64
H16 = "b" * 16
SYMBOL = "BTCUSDT"
MARKET_TYPE = "perp"
T0 = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)


def make_provenance(**over) -> V2DecisionProvenance:
    base = dict(
        run_kind=LIVE, run_id="live-shadow", decision_boundary=T0,
        model_family="v2", rules_version="v2-rules-v0.2.0",
        symbol=SYMBOL, market_type=MARKET_TYPE,
        feature_schema_version=1, calculation_version=H16, config_hash=H64,
        config_version="2.1.0", code_version="deadbeef",
        decision_code_version="decision-code-v1",
    )
    base.update(over)
    return V2DecisionProvenance(**base)


def _status(req, *, ready: bool) -> V2CoverageStatus:
    return V2CoverageStatus(requirement=req, ready=ready, reason="test", latest_bucket_ts=T0)


def make_readiness(*, ready: bool, symbol=SYMBOL, market_type=MARKET_TYPE,
                    calculation_version=H16, decision_boundary=T0
                    ) -> V2ActivationReadinessResult:
    statuses = tuple(
        _status(req, ready=ready) for req in MANDATORY_PERCENTILE_COVERAGE)
    return V2ActivationReadinessResult(
        symbol=symbol, market_type=market_type,
        calculation_version=calculation_version, decision_boundary=decision_boundary,
        ready=ready, statuses=statuses)


# ---- happy path: both resolve_decision_view() AND direct construction ------
@pytest.mark.parametrize("build", [
    lambda p, r: resolve_decision_view(p, r),
    lambda p, r: V2DecisionView(provenance=p, readiness=r),
], ids=["resolve_decision_view", "direct_construction"])
def test_ready_view_composes_cleanly(build):
    prov = make_provenance()
    readiness = make_readiness(ready=True)
    view = build(prov, readiness)
    assert view.provenance is prov
    assert view.readiness is readiness
    assert view.ready is True


def test_not_ready_view_composes_cleanly_never_raises():
    prov = make_provenance()
    readiness = make_readiness(ready=False)
    view = resolve_decision_view(prov, readiness)
    assert view.ready is False
    assert view.readiness.ready is False


def test_is_frozen_dataclass():
    view = resolve_decision_view(make_provenance(), make_readiness(ready=True))
    with pytest.raises(dataclasses.FrozenInstanceError):
        view.provenance = make_provenance()  # type: ignore[misc]


def test_ready_property_never_independently_computed():
    """view.ready always mirrors readiness.ready -- proven for both
    True/False so this isn't vacuously true."""
    for flag in (True, False):
        view = resolve_decision_view(make_provenance(), make_readiness(ready=flag))
        assert view.ready == flag == view.readiness.ready


# ---- Qodo amendment round 1, finding 5: direct construction cannot bypass
# the coherence checks -- __post_init__ enforces them, not only the resolver
@pytest.mark.parametrize("build", [
    lambda p, r: resolve_decision_view(p, r),
    lambda p, r: V2DecisionView(provenance=p, readiness=r),
], ids=["resolve_decision_view", "direct_construction"])
def test_calculation_version_mismatch_refused_on_every_construction_path(build):
    prov = make_provenance(calculation_version=H16)
    readiness = make_readiness(ready=True, calculation_version="c" * 16)
    with pytest.raises(V2DecisionViewError, match="calculation_version"):
        build(prov, readiness)


@pytest.mark.parametrize("build", [
    lambda p, r: resolve_decision_view(p, r),
    lambda p, r: V2DecisionView(provenance=p, readiness=r),
], ids=["resolve_decision_view", "direct_construction"])
def test_decision_boundary_mismatch_refused_on_every_construction_path(build):
    prov = make_provenance(decision_boundary=T0)
    other_t = datetime(2026, 8, 20, 12, 5, tzinfo=timezone.utc)
    readiness = make_readiness(ready=True, decision_boundary=other_t)
    with pytest.raises(V2DecisionViewError, match="decision_boundary"):
        build(prov, readiness)


def test_wrong_type_provenance_rejected_on_direct_construction():
    """The core finding-5 regression: bypassing resolve_decision_view()
    entirely and constructing V2DecisionView directly must STILL raise --
    __post_init__ is the actual enforcement point, not the wrapper
    function."""
    with pytest.raises(V2DecisionViewError, match="V2DecisionProvenance"):
        V2DecisionView(provenance="not-a-provenance",  # type: ignore[arg-type]
                        readiness=make_readiness(ready=True))


def test_wrong_type_readiness_rejected_on_direct_construction():
    with pytest.raises(V2DecisionViewError, match="V2ActivationReadinessResult"):
        V2DecisionView(provenance=make_provenance(),
                        readiness="not-a-readiness-result")  # type: ignore[arg-type]


def test_wrong_type_provenance_rejected():
    with pytest.raises(V2DecisionViewError, match="V2DecisionProvenance"):
        resolve_decision_view("not-a-provenance", make_readiness(ready=True))  # type: ignore[arg-type]


def test_wrong_type_readiness_rejected():
    with pytest.raises(V2DecisionViewError, match="V2ActivationReadinessResult"):
        resolve_decision_view(make_provenance(), "not-a-readiness-result")  # type: ignore[arg-type]


# ---- Qodo amendment round 1, finding 3: symbol/market_type binding --------
@pytest.mark.parametrize("build", [
    lambda p, r: resolve_decision_view(p, r),
    lambda p, r: V2DecisionView(provenance=p, readiness=r),
], ids=["resolve_decision_view", "direct_construction"])
def test_symbol_mismatch_refused_even_when_version_and_boundary_match(build):
    """The core finding-3 regression: readiness computed for a DIFFERENT
    symbol must be refused even though calculation_version and
    decision_boundary both match -- those two fields alone are not a
    complete scope identity (percentile_snapshots is also scoped by
    symbol/market_type)."""
    prov = make_provenance(symbol="BTCUSDT")
    # V2's initial product scope only supports BTCUSDT/perp, so a
    # different-symbol readiness result cannot itself be constructed via
    # SUPPORTED_SYMBOL validation on V2DecisionProvenance -- but
    # V2ActivationReadinessResult has NO such symbol allow-list (it is not
    # scoped to V2's initial product symbol the way provenance is), so a
    # readiness result for a different symbol is a legitimate value this
    # module must still defend against.
    readiness = make_readiness(ready=True, symbol="ETHUSDT")
    with pytest.raises(V2DecisionViewError, match="symbol"):
        build(prov, readiness)


@pytest.mark.parametrize("build", [
    lambda p, r: resolve_decision_view(p, r),
    lambda p, r: V2DecisionView(provenance=p, readiness=r),
], ids=["resolve_decision_view", "direct_construction"])
def test_market_type_mismatch_refused_even_when_version_and_boundary_match(build):
    prov = make_provenance(market_type="perp")
    readiness = make_readiness(ready=True, market_type="spot")
    with pytest.raises(V2DecisionViewError, match="market_type"):
        build(prov, readiness)


def test_determinism_same_inputs_equal_views():
    prov = make_provenance()
    readiness = make_readiness(ready=True)
    assert resolve_decision_view(prov, readiness) == resolve_decision_view(prov, readiness)


# ---- purity -------------------------------------------------------------------
def test_no_io_or_clock_access():
    import inspect
    src = inspect.getsource(
        __import__("analytics.forecasting_v2.decision_view", fromlist=["decision_view"]))
    forbidden = (
        "datetime.now(", "time.time(", "uuid.uuid4(", "random.",
        "open(", "os.environ", "os.getenv", "asyncpg", "await ",
    )
    for token in forbidden:
        assert token not in src, f"forbidden token found in decision_view.py: {token!r}"
