"""Synthetic routing checks for amendment A2. No market panel and no future association."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.research.formation_width_regime_v1 import amendment_a1 as A1
from scripts.research.formation_width_regime_v1 import amendment_a2 as A2
from scripts.research.formation_width_regime_v1 import constants as K
from scripts.research.formation_width_regime_v1 import evaluate

DESIGN_SHA = "64407200533eec23abe63391f546ba83c3fae69c30d4a4f83a6d468300985ae6"
A1_SHA = "a2e00c68e4360fe08db89ade31e4f222dc148ace0aea58e9143a27d4d386d49e"


def _row(**kwargs):
    base = {
        "foundation_clears": False,
        "year_unstable": False,
        "incremental_formation_clears": False,
        "foundation_abs": 0.20,
        "lag_placebo_abs": 0.01,
    }
    base.update(kwargs)
    return base


def test_case_a_null_endpoint_does_not_veto_a_qualifying_endpoint():
    endpoints = {
        "ACTIVITY": _row(
            foundation_clears=True,
            incremental_formation_clears=True,
            foundation_abs=0.30,
            lag_placebo_abs=0.05,
            foundation_rho=0.30,
            incremental_rho=0.12,
            lag_placebo_rho=0.05,
        ),
        "DISPLACEMENT": _row(
            foundation_clears=False,
            foundation_abs=0.04,
            lag_placebo_abs=0.20,
            foundation_rho=0.04,
            incremental_rho=0.01,
            lag_placebo_rho=-0.20,
        ),
    }
    old = A1.assign_route(endpoints, information_limited=False)
    assert old["route"] == A1.ROUTE_NOT_SPECIFIC
    got = A2.assign_route(endpoints, information_limited=False)
    assert got["route"] == A2.ROUTE_PRESENT
    assert got["route_supporting_endpoints"] == ["ACTIVITY"]
    assert got["incremental_qualified_but_not_specific_endpoints"] == []
    by_name = {row["endpoint"]: row for row in got["endpoints"]}
    assert by_name["ACTIVITY"]["current_state_specific"] is True
    assert by_name["DISPLACEMENT"]["current_state_specific"] is False
    assert by_name["DISPLACEMENT"]["foundation_clears"] is False


def test_case_b_specificity_applies_only_to_the_incremental_qualified_endpoint():
    endpoints = {
        "ACTIVITY": _row(
            foundation_clears=True,
            incremental_formation_clears=True,
            foundation_abs=0.20,
            lag_placebo_abs=0.20,
        ),
        "DISPLACEMENT": _row(foundation_clears=False, foundation_abs=0.02, lag_placebo_abs=0.40),
    }
    got = A2.assign_route(endpoints, information_limited=False)
    assert got["route"] == A2.ROUTE_NOT_SPECIFIC
    assert got["interpretable_as_current_state"] is False
    assert got["route_supporting_endpoints"] == []
    assert got["incremental_qualified_but_not_specific_endpoints"] == ["ACTIVITY"]


def test_case_c_one_incremental_pass_is_enough():
    endpoints = {
        "ACTIVITY": _row(foundation_clears=True, incremental_formation_clears=False),
        "DISPLACEMENT": _row(
            foundation_clears=True,
            incremental_formation_clears=True,
            foundation_abs=0.15,
            lag_placebo_abs=0.02,
            foundation_rho=0.90,
        ),
    }
    got = A2.assign_route(endpoints, information_limited=False)
    assert got["route"] == A2.ROUTE_PRESENT
    assert got["route_supporting_endpoints"] == ["DISPLACEMENT"]


def test_case_d_stable_foundation_candidates_that_fail_incremental_are_redundant():
    endpoints = {
        "ACTIVITY": _row(foundation_clears=True, incremental_formation_clears=False, lag_placebo_abs=0.01),
        "DISPLACEMENT": _row(foundation_clears=True, incremental_formation_clears=False, lag_placebo_abs=0.50),
    }
    got = A2.assign_route(endpoints, information_limited=False)
    assert got["route"] == A2.ROUTE_REDUNDANT
    assert got["route_supporting_endpoints"] == []


def test_case_e_no_foundation_clear_has_no_detectable_structure():
    endpoints = {
        "ACTIVITY": _row(foundation_clears=False, incremental_formation_clears=True, lag_placebo_abs=0.90),
        "DISPLACEMENT": _row(foundation_clears=False, lag_placebo_abs=0.90),
    }
    got = A2.assign_route(endpoints, information_limited=False)
    assert got["route"] == A2.ROUTE_NO_DETECTABLE


def test_supporting_names_follow_endpoint_order_and_rv_prev_cannot_enter():
    endpoints = {
        "ACTIVITY": _row(
            foundation_clears=True,
            incremental_formation_clears=True,
            foundation_rho=0.11,
        ),
        "DISPLACEMENT": _row(
            foundation_clears=True,
            incremental_formation_clears=True,
            foundation_rho=0.80,
        ),
    }
    got = A2.assign_route(endpoints, information_limited=False)
    assert got["route_supporting_endpoints"] == ["ACTIVITY", "DISPLACEMENT"]
    with pytest.raises(RuntimeError):
        A2.assign_route(
            {"ACTIVITY": _row(rv_prev_clears=True), "DISPLACEMENT": _row()},
            information_limited=False,
        )


def test_outcome_evaluator_still_refuses_and_sample_is_unchanged(monkeypatch, tmp_path):
    monkeypatch.setattr(evaluate, "OUT_JSON", tmp_path / "result.json")
    monkeypatch.setattr(evaluate, "OUT_MD", tmp_path / "result.md")
    monkeypatch.setattr(evaluate, "OUT_MANIFEST", tmp_path / "manifest.json")
    (tmp_path / "result.json").write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        evaluate.main()
    assert str(exc.value) == "REFUSING_RERUN"
    design = hashlib.sha256(Path("docs/research/FORMATION_WIDTH_REGIME_V1_DESIGN.md").read_bytes()).hexdigest()
    a1 = hashlib.sha256(Path("docs/research/FORMATION_WIDTH_REGIME_V1_AMENDMENT_A1.md").read_bytes()).hexdigest()
    support = json.loads(
        Path("docs/research/FORMATION_WIDTH_REGIME_V1_AMENDMENT_A1_SUPPORT.json").read_text(encoding="utf-8")
    )
    census = json.loads(
        Path("docs/research/FORMATION_WIDTH_REGIME_V1_FEASIBILITY.json").read_text(encoding="utf-8")
    )
    assert design == DESIGN_SHA
    assert a1 == A1_SHA
    assert support["outcome_read"] is False
    assert support["future_association_read"] is False
    assert support["a1_analysis_sample"] == 1820
    assert support["a1_iso_weeks"] == 262
    assert census["counts"]["analysis_sample"] == 1820
    assert census["analysis_iso_weeks"] == 262
    assert census["outcome_read"] is False
    assert K.PRACTICAL_ABS_RHO == 0.10
    assert K.BOOT_SEED == 20261107
    assert K.HORIZON_BARS == 12
    assert K.ANCHOR == "UTC_00"
