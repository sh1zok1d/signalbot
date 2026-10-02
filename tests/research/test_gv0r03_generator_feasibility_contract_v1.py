"""GV0R03 generator feasibility contract, V1 mapping. No LLM calls and no market outcomes."""
import copy
import json
from pathlib import Path

import pytest

from scripts.research.generator_v0 import feasibility_contract as v0
from scripts.research.generator_v0.context import ContractError
from scripts.research.generator_v0.feasibility_contract_v1 import (
    CONTRACT_VERSION,
    SEALED_FIELDS,
    V1_FIELDS,
    reject_downstream_edit_v1,
    to_compiler_proposal_v1,
    validate_planning_v1,
    window_of,
)
from scripts.research.gv0r02_feasibility_compiler_v1 import V1_REQUIRED_FIELDS, compile_proposal_v1
from tests.research.test_gv0r03_generator_feasibility_contract import planning as v0_planning

REPO = Path(__file__).resolve().parents[2]


def planning(**overrides):
    p = v0_planning()
    p["CONTRACT_VERSION"] = CONTRACT_VERSION
    p["PROPOSAL_ID"] = "GV0R03_V1_SYNTHETIC_PLANNING"
    p["NOMINAL_OBSERVATION_COUNT_CONSTRUCTION"]["DECLARED_COUNT_BY_YEAR"] = {
        "2020": 2000, "2021": 2000, "2022": 2000, "2023": 2000, "2024": 2000}
    p.update({
        "CLAIM_TYPE": "INCREMENTAL",
        "TARGET_CLASS": "UNCONDITIONAL",
        "INTRADAY": False,
        "VARIABLE_ROLES": {
            "REGIME_VARIABLES": [],
            "MECHANISM_VARIABLES": ["SYNTHETIC_STATE"],
            "NUISANCE_BASELINE_VARIABLES": ["PRIOR_REALIZED_VOLATILITY", "LAGGED_TARGET"],
        },
        "PRIMARY_CELLS": [{"REGIME": None, "ESTIMAND": "standardized second-moment shift", "HORIZON": "one decision bar"}],
        "PRACTICAL_BAR_BASIS": "PRODUCT_RELEVANCE",
        "DISCOVERY_SURFACE": {"ID": "BINANCE_2020_2024", "START": "2020-01-01", "END": "2025-01-01"},
        "REPLICATION_SURFACE": {"KIND": "HISTORICAL", "ID": "BITMEX_2016_2019", "START": "2016-01-01",
                                "END": "2020-01-01", "NOMINAL_OBSERVATION_COUNT": 8000},
        "EPOCHS": "CALENDAR_YEAR",
        "COMPLEXITY_CLASS": "ATOMIC",
        "COMPONENTS": [],
    })
    p.update(overrides)
    return p


def codes(result):
    return {b["BLOCKER_CODE"] for b in result["BLOCKERS"]}


def test_v1_planning_maps_without_interpretation_and_compiles_feasible():
    source = planning()
    mapped = to_compiler_proposal_v1(source)
    assert mapped["COMPILER_SCHEMA_VERSION"] == "GV0R02_SCHEMA_V1"
    assert mapped["COMPILER_POLICY_VERSION"] == "GV0R02_POLICY_V1"
    assert set(V1_REQUIRED_FIELDS) <= set(mapped)
    for field in V1_FIELDS:
        assert mapped[field] == source[field]
    assert mapped["OUTCOME_BLIND_SAMPLE"]["COUNT_BY_YEAR"] == {"2020": 2000, "2021": 2000, "2022": 2000,
                                                               "2023": 2000, "2024": 2000}
    assert "FEASIBILITY_STATUS" not in mapped and "MDE_STRESS" not in mapped
    result = compile_proposal_v1(mapped)
    assert result["FEASIBILITY_STATUS"] == "FEASIBLE_FOR_PREREGISTRATION", result["BLOCKERS"]
    assert result["HETEROGENEITY_ASSESSABILITY"]["NOT_EVIDENCE_OF_STABILITY"] is True
    assert result["MARKET_OUTCOMES_OPENED"] is False


def test_mapping_does_not_alias_the_planning_object():
    source = planning()
    mapped = to_compiler_proposal_v1(source)
    mapped["PRIMARY_CELLS"][0]["HORIZON"] = "changed"
    mapped["VARIABLE_ROLES"]["NUISANCE_BASELINE_VARIABLES"].append("X")
    assert source == planning()


def test_v0_contract_and_v0_mapping_are_unchanged():
    mapped = v0.to_compiler_proposal(v0_planning())
    assert mapped["COMPILER_SCHEMA_VERSION"] == "GV0R02_SCHEMA_V0"
    assert not set(V1_FIELDS) & set(mapped)
    with pytest.raises(ContractError, match="CONTRACT_VERSION"):
        validate_planning_v1(v0_planning())


@pytest.mark.parametrize("field", V1_FIELDS)
def test_each_omitted_v1_field_is_rejected(field):
    broken = planning()
    broken.pop(field)
    with pytest.raises(ContractError, match=field):
        validate_planning_v1(broken)


def test_intraday_false_is_a_value_not_an_omission():
    validate_planning_v1(planning(INTRADAY=False))
    with pytest.raises(ContractError, match="INTRADAY"):
        validate_planning_v1(planning(INTRADAY="no"))


@pytest.mark.parametrize("field,value", [
    ("CLAIM_TYPE", "PREDICTIVE"),
    ("TARGET_CLASS", "SOMETIMES"),
    ("PRACTICAL_BAR_BASIS", "PNL_TARGET"),
    ("VARIABLE_ROLES", {"MECHANISM_VARIABLES": ["A"]}),
    ("PRIMARY_CELLS", [{"REGIME": None, "ESTIMAND": "e", "HORIZON": "h"}] * 4),
    ("PRIMARY_CELLS", [{"ESTIMAND": "e", "HORIZON": "h"}]),
    ("EPOCHS", [{"ID": "A"}, {"ID": "B"}]),
    ("NUISANCE_EXCLUSIONS", [{"VARIABLE": "LAGGED_TARGET"}]),
    ("NUISANCE_DIAGNOSTIC_PLANNED", "yes"),
])
def test_shape_violations_are_rejected(field, value):
    with pytest.raises(ContractError, match=field):
        validate_planning_v1(planning(**{field: value}))


def test_surfaces_follow_the_frozen_era_roles():
    wrong_era = planning(DISCOVERY_SURFACE={"ID": "BITMEX_2016_2019", "START": "2016-01-01", "END": "2020-01-01"},
                         HISTORICAL_WINDOW="2016-01..2019-12")
    wrong_era["NOMINAL_OBSERVATION_COUNT_CONSTRUCTION"]["WINDOW"] = "2016-01..2019-12"
    wrong_era["NOMINAL_OBSERVATION_COUNT_CONSTRUCTION"].pop("DECLARED_COUNT_BY_YEAR")
    with pytest.raises(ContractError, match="DISCOVERY_SURFACE"):      # replication era used for discovery
        validate_planning_v1(wrong_era)
    with pytest.raises(ContractError, match="DISCOVERY_SURFACE"):      # outside its era
        validate_planning_v1(planning(DISCOVERY_SURFACE={"ID": "BINANCE_2020_2024", "START": "2020-01-01", "END": "2025-07-01"}))
    with pytest.raises(ContractError, match="DISCOVERY_SURFACE"):      # disagrees with the V0 window
        validate_planning_v1(planning(DISCOVERY_SURFACE={"ID": "BINANCE_2020_2024", "START": "2021-01-01", "END": "2025-01-01"}))
    with pytest.raises(ContractError, match="DISCOVERY_SURFACE"):      # not a month boundary
        validate_planning_v1(planning(DISCOVERY_SURFACE={"ID": "BINANCE_2020_2024", "START": "2020-01-15", "END": "2025-01-01"}))
    rep = dict(planning()["REPLICATION_SURFACE"], ID="BINANCE_2020_2024", START="2020-01-01", END="2021-01-01")
    with pytest.raises(ContractError, match="REPLICATION_SURFACE"):
        validate_planning_v1(planning(REPLICATION_SURFACE=rep))
    rep = dict(planning()["REPLICATION_SURFACE"], NOMINAL_OBSERVATION_COUNT=0)
    with pytest.raises(ContractError, match="REPLICATION_SURFACE"):
        validate_planning_v1(planning(REPLICATION_SURFACE=rep))


def test_window_of_matches_the_v0_window_form():
    import datetime as dt
    assert window_of((dt.date(2020, 1, 1), dt.date(2025, 1, 1))) == "2020-01..2024-12"
    assert window_of((dt.date(2021, 3, 1), dt.date(2023, 7, 1))) == "2021-03..2023-06"


def test_count_by_year_must_be_outcome_blind_and_inside_discovery():
    p = planning()
    p["NOMINAL_OBSERVATION_COUNT_CONSTRUCTION"]["DECLARED_COUNT_BY_YEAR"] = {"2019": 100}
    with pytest.raises(ContractError, match="NOMINAL_OBSERVATION_COUNT_CONSTRUCTION"):
        validate_planning_v1(p)
    p["NOMINAL_OBSERVATION_COUNT_CONSTRUCTION"]["DECLARED_COUNT_BY_YEAR"] = {"2020": 0}
    with pytest.raises(ContractError, match="NOMINAL_OBSERVATION_COUNT_CONSTRUCTION"):
        validate_planning_v1(p)


def test_outcome_keys_are_rejected_inside_v1_fields():
    rule = {"MAX_EPISODES": 200, "MIN_N": 100, "COUNTS_ONLY_MONITORING": True,
            "PRODUCT_EXPOSURE_HANDLING": "hidden", "RETURN": 0.01}
    rep = {"KIND": "PROSPECTIVE", "ID": "BINANCE_LIVE", "START": "2027-01-01", "STARTS_AFTER_FREEZE": True,
           "STOPPING_RULE": rule}
    with pytest.raises(ContractError, match="RETURN"):
        validate_planning_v1(planning(REPLICATION_SURFACE=rep))


def test_the_compiler_stays_the_single_adjudicator_of_v1_rules():
    """Well-shaped but V1-inconsistent declarations pass the contract and are blocked by the compiler."""
    directional_context = planning(CLAIM_TYPE="CONTEXT_DESCRIPTIVE", ENDPOINT_MOMENT="FIRST_MOMENT")
    result = compile_proposal_v1(to_compiler_proposal_v1(directional_context))
    assert result["FEASIBILITY_STATUS"] == "DEFINITION_INCOMPLETE"
    assert "CONTEXT_CLAIM_DIRECTIONAL" in codes(result)

    roles = {"REGIME_VARIABLES": [], "MECHANISM_VARIABLES": ["SYNTHETIC_STATE"], "NUISANCE_BASELINE_VARIABLES": []}
    result = compile_proposal_v1(to_compiler_proposal_v1(planning(VARIABLE_ROLES=roles, INTRADAY=True)))
    assert "STANDARD_NUISANCE_MISSING" in codes(result)

    conditional = planning(TARGET_CLASS="CONDITIONAL", COMPLEXITY_CLASS="CONDITIONAL")
    assert "REGIME_MISSING_FOR_CONDITIONAL_CLAIM" in codes(compile_proposal_v1(to_compiler_proposal_v1(conditional)))


def test_prospective_replication_reaches_the_compiler_and_the_protected_window_is_its_decision():
    rule = {"MAX_EPISODES": 200, "MIN_N": 100, "COUNTS_ONLY_MONITORING": True,
            "PRODUCT_EXPOSURE_HANDLING": "statement hidden from users until the stopping rule fires"}
    early = {"KIND": "PROSPECTIVE", "ID": "BINANCE_LIVE", "START": "2026-11-01", "STARTS_AFTER_FREEZE": True,
             "STOPPING_RULE": rule}
    result = compile_proposal_v1(to_compiler_proposal_v1(planning(REPLICATION_SURFACE=early)))
    assert result["FEASIBILITY_STATUS"] == "DATA_BLOCKED"
    assert "PROTECTED_SURFACE_DECISION_REQUIRED" in codes(result)
    later = dict(early, START="2027-01-01")
    result = compile_proposal_v1(to_compiler_proposal_v1(planning(REPLICATION_SURFACE=later)))
    assert "PROTECTED_SURFACE_DECISION_REQUIRED" not in codes(result)
    with pytest.raises(ContractError, match="REPLICATION_SURFACE"):
        validate_planning_v1(planning(REPLICATION_SURFACE=dict(early, EXTRA=1)))


def test_downstream_cannot_rewrite_v1_design_fields():
    source = planning()
    assert set(v0.SEALED_FIELDS) <= set(SEALED_FIELDS) and set(V1_FIELDS) <= set(SEALED_FIELDS)
    for field, value in (("CLAIM_TYPE", "CONTEXT_DESCRIPTIVE"), ("PRACTICAL_BAR_BASIS", "COSTS"),
                         ("PRIMARY_CELLS", [{"REGIME": None, "ESTIMAND": "other", "HORIZON": "h"}]),
                         ("NUISANCE_EXCLUSIONS", [{"VARIABLE": "LAGGED_TARGET", "MECHANISM_ARGUMENT": "added later"}])):
        edited = copy.deepcopy(source)
        edited[field] = value
        with pytest.raises(ContractError, match=field):
            reject_downstream_edit_v1(source, edited)
    edited = copy.deepcopy(source)
    edited["REPLICATION_SURFACE"]["NOMINAL_OBSERVATION_COUNT"] = 99999
    with pytest.raises(ContractError, match="REPLICATION_SURFACE"):
        reject_downstream_edit_v1(source, edited)
    reject_downstream_edit_v1(source, copy.deepcopy(source))


def test_the_generator_card_schema_stays_frozen():
    design = json.loads((REPO / "docs/research/HYPOTHESIS_GENERATOR_V0_DESIGN.json").read_text())
    assert design["CANDIDATE_SCHEMA_FROZEN"] is True
    assert not set(V1_FIELDS) & set(design["CANDIDATE_SCHEMA"]["REQUIRED_FIELDS"])
