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
T0 = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)


def make_provenance(**over) -> V2DecisionProvenance:
    base = dict(
        run_kind=LIVE, run_id="live-shadow", decision_boundary=T0,
        model_family="v2", rules_version="v2-rules-v0.2.0",
        symbol="BTCUSDT", market_type="perp",
        feature_schema_version=1, calculation_version=H16, config_hash=H64,
        config_version="2.1.0", code_version="deadbeef",
        decision_code_version="decision-code-v1",
    )
    base.update(over)
    return V2DecisionProvenance(**base)


def _status(req, *, ready: bool) -> V2CoverageStatus:
    return V2CoverageStatus(requirement=req, ready=ready, reason="test", latest_bucket_ts=T0)


def make_readiness(*, ready: bool, calculation_version=H16, decision_boundary=T0
                    ) -> V2ActivationReadinessResult:
    statuses = tuple(
        _status(req, ready=ready) for req in MANDATORY_PERCENTILE_COVERAGE)
    return V2ActivationReadinessResult(
        calculation_version=calculation_version, decision_boundary=decision_boundary,
        ready=ready, statuses=statuses)


# ---- resolve_decision_view: happy path ---------------------------------------
def test_ready_view_composes_cleanly():
    prov = make_provenance()
    readiness = make_readiness(ready=True)
    view = resolve_decision_view(prov, readiness)
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


# ---- resolve_decision_view: mismatch refusal ---------------------------------
def test_calculation_version_mismatch_refused():
    prov = make_provenance(calculation_version=H16)
    readiness = make_readiness(ready=True, calculation_version="c" * 16)
    with pytest.raises(V2DecisionViewError, match="calculation_version"):
        resolve_decision_view(prov, readiness)


def test_decision_boundary_mismatch_refused():
    prov = make_provenance(decision_boundary=T0)
    other_t = datetime(2026, 8, 20, 12, 5, tzinfo=timezone.utc)
    readiness = make_readiness(ready=True, decision_boundary=other_t)
    with pytest.raises(V2DecisionViewError, match="decision_boundary"):
        resolve_decision_view(prov, readiness)


def test_wrong_type_provenance_rejected():
    with pytest.raises(V2DecisionViewError, match="V2DecisionProvenance"):
        resolve_decision_view("not-a-provenance", make_readiness(ready=True))  # type: ignore[arg-type]


def test_wrong_type_readiness_rejected():
    with pytest.raises(V2DecisionViewError, match="V2ActivationReadinessResult"):
        resolve_decision_view(make_provenance(), "not-a-readiness-result")  # type: ignore[arg-type]


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
