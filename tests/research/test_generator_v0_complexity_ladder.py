"""Complexity ladder: planning rules and the shortlist quota. No LLM calls and no market outcomes."""
import copy

import pytest

from scripts.research.generator_v0.complexity import COMPLEXITY_CLASSES, complexity_shortlist
from scripts.research.generator_v0.context import ContractError
from scripts.research.generator_v0.feasibility_contract_v1 import (
    reject_downstream_edit_v1,
    to_compiler_proposal_v1,
    validate_planning_v1,
)
from scripts.research.gv0r02_feasibility_compiler_v1 import compile_proposal_v1
from tests.research.test_gv0r03_generator_feasibility_contract_v1 import planning

BASE_NUISANCE = ["PRIOR_REALIZED_VOLATILITY", "LAGGED_TARGET"]


def roles(mechanism, nuisance=(), regime=()):
    return {"REGIME_VARIABLES": list(regime), "MECHANISM_VARIABLES": list(mechanism),
            "NUISANCE_BASELINE_VARIABLES": BASE_NUISANCE + list(nuisance)}


def interaction(**overrides):
    p = planning(COMPLEXITY_CLASS="INTERACTION", COMPONENTS=["TWAP_FOOTPRINT", "DIVERGENCE"],
                 VARIABLE_ROLES=roles(["TWAP_FOOTPRINT_X_DIVERGENCE"], ["TWAP_FOOTPRINT", "DIVERGENCE"]))
    p.update(overrides)
    return p


def test_atomic_and_conditional_rungs():
    validate_planning_v1(planning())
    with pytest.raises(ContractError, match="COMPLEXITY_CLASS"):
        validate_planning_v1(planning(VARIABLE_ROLES=roles(["A", "B"])))
    with pytest.raises(ContractError, match="COMPLEXITY_CLASS"):
        validate_planning_v1(planning(TARGET_CLASS="CONDITIONAL"))           # ATOMIC is unconditional
    with pytest.raises(ContractError, match="COMPLEXITY_CLASS"):
        validate_planning_v1(planning(COMPLEXITY_CLASS="CONDITIONAL"))       # CONDITIONAL needs a conditional target
    cond = planning(COMPLEXITY_CLASS="CONDITIONAL", TARGET_CLASS="CONDITIONAL",
                    VARIABLE_ROLES=roles(["OI_RECOVERY_SPEED"], regime=["POST_LIQUIDATION_SHOCK"]),
                    PRIMARY_CELLS=[{"REGIME": "POST_LIQUIDATION_SHOCK", "ESTIMAND": "e", "HORIZON": "h"}])
    validate_planning_v1(cond)
    assert compile_proposal_v1(to_compiler_proposal_v1(cond))["FEASIBILITY_STATUS"] == "FEASIBLE_FOR_PREREGISTRATION"
    with pytest.raises(ContractError, match="COMPONENTS"):
        validate_planning_v1(planning(COMPONENTS=["A"]))                     # simple rungs have no components


def test_interaction_must_beat_both_main_effects():
    p = interaction()
    validate_planning_v1(p)
    mapped = to_compiler_proposal_v1(p)
    assert mapped["COMPLEXITY_CLASS"] == "INTERACTION" and mapped["COMPONENTS"] == ["TWAP_FOOTPRINT", "DIVERGENCE"]
    assert compile_proposal_v1(mapped)["FEASIBILITY_STATUS"] == "FEASIBLE_FOR_PREREGISTRATION"
    with pytest.raises(ContractError, match="COMPONENTS"):                   # a main effect not controlled
        validate_planning_v1(interaction(VARIABLE_ROLES=roles(["TWAP_FOOTPRINT_X_DIVERGENCE"], ["TWAP_FOOTPRINT"])))
    with pytest.raises(ContractError, match="COMPLEXITY_CLASS"):             # a component is not the joint term
        validate_planning_v1(interaction(VARIABLE_ROLES=roles(["DIVERGENCE"], ["TWAP_FOOTPRINT", "DIVERGENCE"])))
    with pytest.raises(ContractError, match="COMPLEXITY_CLASS"):             # interaction is incremental by definition
        validate_planning_v1(interaction(CLAIM_TYPE="CONTEXT_DESCRIPTIVE", NUISANCE_DIAGNOSTIC_PLANNED=True))
    with pytest.raises(ContractError, match="COMPONENTS"):
        validate_planning_v1(interaction(COMPONENTS=["TWAP_FOOTPRINT", "DIVERGENCE", "OI"]))
    with pytest.raises(ContractError, match="COMPONENTS"):
        validate_planning_v1(interaction(COMPONENTS=["TWAP_FOOTPRINT", "TWAP_FOOTPRINT"]))


def test_composite_has_three_to_five_controlled_components():
    comps = ["OI_CONTRACTION", "BID_IMBALANCE", "CVD_DIVERGENCE"]
    p = planning(COMPLEXITY_CLASS="COMPOSITE", COMPONENTS=comps, VARIABLE_ROLES=roles(["EXHAUSTION_STATE"], comps))
    validate_planning_v1(p)
    with pytest.raises(ContractError, match="COMPONENTS"):
        validate_planning_v1(dict(p, COMPONENTS=comps[:2]))
    six = [f"C{i}" for i in range(6)]
    with pytest.raises(ContractError, match="COMPONENTS"):
        validate_planning_v1(dict(p, COMPONENTS=six, VARIABLE_ROLES=roles(["EXHAUSTION_STATE"], six)))


def test_ladder_fields_are_required_and_sealed():
    for field in ("COMPLEXITY_CLASS", "COMPONENTS"):
        broken = planning()
        broken.pop(field)
        with pytest.raises(ContractError, match=field):
            validate_planning_v1(broken)
    with pytest.raises(ContractError, match="COMPLEXITY_CLASS"):
        validate_planning_v1(planning(COMPLEXITY_CLASS="SIMPLE"))
    source = interaction()
    edited = copy.deepcopy(source)
    edited["COMPLEXITY_CLASS"] = "COMPOSITE"
    with pytest.raises(ContractError, match="COMPLEXITY_CLASS"):
        reject_downstream_edit_v1(source, edited)


def _classes(spec):
    return {cid: cls for cid, cls in spec}


def test_shortlist_quota_two_atomic_two_conditional_one_complex():
    order = ["C01", "C02", "C03", "C04", "C05", "C06", "C07", "C08"]
    classes = _classes([("C01", "INTERACTION"), ("C02", "COMPOSITE"), ("C03", "ATOMIC"), ("C04", "CONDITIONAL"),
                        ("C05", "ATOMIC"), ("C06", "ATOMIC"), ("C07", "CONDITIONAL"), ("C08", "CONDITIONAL")])
    picks = complexity_shortlist(order, classes)
    assert [(p["CANDIDATE_ID"], p["SEAT"]) for p in picks] == [
        ("C03", "ATOMIC"), ("C05", "ATOMIC"), ("C04", "CONDITIONAL"), ("C07", "CONDITIONAL"), ("C01", "COMPLEX")]


def test_unfilled_seats_pass_down_the_ladder_never_up():
    order = ["C01", "C02", "C03", "C04", "C05"]
    no_complex = _classes([("C01", "ATOMIC"), ("C02", "CONDITIONAL"), ("C03", "CONDITIONAL"), ("C04", "CONDITIONAL"),
                           ("C05", "ATOMIC")])
    picks = complexity_shortlist(order, no_complex)
    assert [(p["CANDIDATE_ID"], p["SEAT"]) for p in picks] == [
        ("C01", "ATOMIC"), ("C05", "ATOMIC"), ("C02", "CONDITIONAL"), ("C03", "CONDITIONAL"), ("C04", "COMPLEX")]
    only_complex = _classes([(c, "INTERACTION") for c in order])
    assert [p["CANDIDATE_ID"] for p in complexity_shortlist(order, only_complex)] == ["C01"]
    simple_only = _classes([(c, "ATOMIC") for c in order])
    assert len(complexity_shortlist(order, simple_only)) == 5          # every seat cascades down to ATOMIC
    assert complexity_shortlist([], {}) == []


def test_shortlist_needs_a_class_for_every_survivor():
    with pytest.raises(ContractError, match="C02"):
        complexity_shortlist(["C01", "C02"], {"C01": "ATOMIC"})
    assert set(COMPLEXITY_CLASSES) == {"ATOMIC", "CONDITIONAL", "INTERACTION", "COMPOSITE"}
