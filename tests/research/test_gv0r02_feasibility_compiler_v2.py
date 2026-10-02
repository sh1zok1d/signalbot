"""GV0R02 compiler V2. Outcome-blind support checks only. No market targets."""

import json
from pathlib import Path

import pytest

from scripts.research import gv0r02_feasibility_compiler as v0
from scripts.research import gv0r02_feasibility_compiler_v1 as v1
from scripts.research.generator_v0.feasibility_contract_v1 import to_compiler_proposal_v1
from scripts.research.gv0r02_feasibility_compiler_v2 import (
    COMPILER_POLICY_VERSION,
    COMPILER_SCHEMA_VERSION,
    SPARSE_STATE_MINORITY_FRACTION,
    binary_contrast_effective_n,
    compile_proposal_v2,
)
from tests.research.test_gv0r02_feasibility_compiler_v1 import codes, positive_control

REPO = Path(__file__).resolve().parents[2]
V2_SOURCE = REPO / "scripts/research/gv0r02_feasibility_compiler_v2.py"


def support(active, inactive, variable="FIXTURE_MECHANISM"):
    return {
        "KIND": "BINARY",
        "MECHANISM_VARIABLE": variable,
        "MECHANISM_ACTIVE_N": active,
        "MECHANISM_INACTIVE_N": inactive,
    }


def v2_proposal(active, inactive, **overrides):
    nominal = overrides.pop("nominal", active + inactive)
    sample = {
        **positive_control()["OUTCOME_BLIND_SAMPLE"],
        "NOMINAL_OBSERVATION_COUNT": nominal,
    }
    proposal = positive_control(
        COMPILER_SCHEMA_VERSION=COMPILER_SCHEMA_VERSION,
        COMPILER_POLICY_VERSION=COMPILER_POLICY_VERSION,
        OUTCOME_BLIND_SAMPLE=sample,
        PRIMARY_MECHANISM_SUPPORT=[support(active, inactive)],
    )
    proposal.update(overrides)
    return proposal


def prospective_rule(**extra):
    rule = {
        "MIN_N": 1000,
        "MAX_EPISODES": 1500,
        "END_DATE": "2028-12-31",
        "COUNTS_ONLY_MONITORING": True,
        "PRODUCT_EXPOSURE_HANDLING": "hidden until the rule fires",
    }
    rule.update(extra)
    return {
        "KIND": "PROSPECTIVE",
        "ID": "BINANCE_PROSPECTIVE_FIXTURE",
        "START": "2027-01-01",
        "STARTS_AFTER_FREEZE": True,
        "STOPPING_RULE": rule,
    }


def test_versions_are_explicit_and_v1_is_untouched():
    assert COMPILER_SCHEMA_VERSION == "GV0R02_SCHEMA_V2"
    assert COMPILER_POLICY_VERSION == "GV0R02_POLICY_V2"
    assert v1.COMPILER_SCHEMA_VERSION == "GV0R02_SCHEMA_V1"
    assert v1.COMPILER_POLICY_VERSION == "GV0R02_POLICY_V1"
    assert v0.COMPILER_SCHEMA_VERSION == "GV0R02_SCHEMA_V0"
    assert SPARSE_STATE_MINORITY_FRACTION == 0.05


def test_active_zero_blocks_before_power():
    result = compile_proposal_v2(v2_proposal(0, 1383, nominal=1383))
    assert result["FEASIBILITY_STATUS"] == "INFERENCE_SUPPORT_INSUFFICIENT"
    assert "PRIMARY_MECHANISM_SUPPORT_ZERO" in codes(result)
    assert result["PRIMARY_MECHANISM_SUPPORT"][0]["ZERO_SIDE"] == "ACTIVE"
    assert result["DISCOVERY_SCREEN"]["NON_IDENTIFIABLE"] is True
    assert result["DISCOVERY_SCREEN"]["MDE_STRESS"] is None
    assert result["DISCOVERY_SCREEN"]["POWER_STRESS"] is None
    assert "MDE_TOO_LARGE" not in codes(result)
    assert result["MARKET_OUTCOMES_OPENED"] is False


def test_inactive_zero_blocks():
    result = compile_proposal_v2(v2_proposal(1383, 0, nominal=1383))
    assert result["FEASIBILITY_STATUS"] == "INFERENCE_SUPPORT_INSUFFICIENT"
    assert "PRIMARY_MECHANISM_SUPPORT_ZERO" in codes(result)
    assert result["PRIMARY_MECHANISM_SUPPORT"][0]["ZERO_SIDE"] == "INACTIVE"
    assert result["ALPHA_ATTAINABLE"] is False
    assert result["MIN_ATTAINABLE_P"] == 1.0
    assert result["PRIMARY_LABEL_ORBIT_SIZE"] == 1


def test_sparse_active_count_does_not_inherit_nominal_power():
    nominal_power = v1.compile_proposal_v1(positive_control())["DISCOVERY_SCREEN"]["POWER_BASE"]
    result = compile_proposal_v2(v2_proposal(1, 9999, nominal=10000))
    screen = result["DISCOVERY_SCREEN"]
    assert nominal_power > 0.99
    assert screen["EFFECTIVE_N"] == pytest.approx(binary_contrast_effective_n(1, 9999))
    assert screen["EFFECTIVE_N"] == pytest.approx(0.9999)
    assert screen["POWER_BASE"] < 0.05
    assert screen["POWER_BASE"] != pytest.approx(nominal_power)
    assert result["FEASIBILITY_STATUS"] != "FEASIBLE_FOR_PREREGISTRATION"
    assert "MDE_TOO_LARGE" in codes(result)


def test_balanced_support_uses_contrast_effective_n():
    result = compile_proposal_v2(v2_proposal(5000, 5000, nominal=10000))
    screen = result["DISCOVERY_SCREEN"]
    assert result["FEASIBILITY_STATUS"] == "FEASIBLE_FOR_PREREGISTRATION", result["BLOCKERS"]
    assert screen["NON_IDENTIFIABLE"] is False
    assert screen["EFFECTIVE_N"] == pytest.approx(2500)
    assert screen["POWER_STRESS"] == pytest.approx(
        v1._power(0.20, v0.POWER_PROFILE["BASE_SD"] * v0.POWER_PROFILE["STRESS_SD_MULTIPLIER"], 2500, v1.z_two_sided(0.05))
    )
    assert screen["POWER_BASE"] < 1.0
    assert result["ALPHA_ATTAINABLE"] is None


def test_all_zero_permutation_label_has_orbit_one():
    result = compile_proposal_v2(v2_proposal(0, 100))
    assert result["PRIMARY_LABEL_ORBIT_SIZE"] == 1
    assert result["MIN_ATTAINABLE_P"] == 1.0
    assert result["ALPHA_ATTAINABLE"] is False
    assert "ALPHA_UNATTAINABLE" in codes(result)
    blocker = next(b for b in result["BLOCKERS"] if b["BLOCKER_CODE"] == "ALPHA_UNATTAINABLE")
    assert blocker["BLOCKER_OBJECT"]["PRIMARY_LABEL_ORBIT_SIZE"] == 1


def test_v1_results_stay_reproducible_under_the_v1_policy():
    planning = json.loads((REPO / "docs/research/GV0V03L40_C033_V1_PLANNING.json").read_text())
    stored = json.loads((REPO / "docs/research/GV0V03L40_C033_V1_FEASIBILITY.json").read_text())
    proposal = to_compiler_proposal_v1(planning)
    result = v1.compile_proposal_v1(proposal)
    for key in (
        "FEASIBILITY_STATUS",
        "BLOCKERS",
        "DISCOVERY_SCREEN",
        "REPLICATION_SCREEN",
        "RESULT_ID",
        "PROPOSAL_DIGEST",
        "FEATURE_REGISTRY_DIGEST",
        "COMPILER_SCHEMA_VERSION",
        "COMPILER_POLICY_VERSION",
        "HETEROGENEITY_ASSESSABILITY",
    ):
        assert result[key] == stored[key]
    assert result["FEASIBILITY_STATUS"] == "FEASIBLE_FOR_PREREGISTRATION"
    assert result["V0_PASSES"]["ALPHA_ATTAINABLE"] is None
    assert v1.compile_proposal_v1(positive_control())["FEASIBILITY_STATUS"] == "FEASIBLE_FOR_PREREGISTRATION"
    refused = v1.compile_proposal_v1({**proposal, "COMPILER_SCHEMA_VERSION": COMPILER_SCHEMA_VERSION})
    assert refused["FEASIBILITY_STATUS"] == "DEFINITION_INCOMPLETE"


def test_support_checks_need_no_market_outcome():
    source = V2_SOURCE.read_text()
    assert "RV_DECAY" not in source
    assert "kline" not in source.lower()
    proposal = v2_proposal(0, 50)
    assert "TARGET_VALUE" not in proposal
    result = compile_proposal_v2(proposal)
    assert result["MARKET_OUTCOMES_OPENED"] is False
    assert result["PROTECTED_2025_VALUES_OPENED"] is False
    assert result["PROTECTED_2026_VALUES_OPENED"] is False
    assert "PRIMARY_MECHANISM_SUPPORT_ZERO" in codes(result)


def test_prospective_sparse_state_without_a_support_floor_fails_closed():
    sparse = compile_proposal_v2(v2_proposal(
        2, 10000, nominal=10002, REPLICATION_SURFACE=prospective_rule(),
    ))
    assert "PROSPECTIVE_MECHANISM_SUPPORT_UNGUARANTEED" in codes(sparse)
    assert sparse["FEASIBILITY_STATUS"] == "DEFINITION_INCOMPLETE"
    assert sparse["REPLICATION_SCREEN"]["NON_IDENTIFIABLE"] is True
    assert sparse["REPLICATION_SCREEN"]["POWER_STRESS"] is None

    guaranteed = compile_proposal_v2(v2_proposal(
        2, 10000, nominal=10002,
        REPLICATION_SURFACE=prospective_rule(MIN_MECHANISM_ACTIVE_N=40, MIN_MECHANISM_INACTIVE_N=40),
    ))
    assert "PROSPECTIVE_MECHANISM_SUPPORT_UNGUARANTEED" not in codes(guaranteed)

    balanced = compile_proposal_v2(v2_proposal(
        5000, 5000, nominal=10000, REPLICATION_SURFACE=prospective_rule(),
    ))
    assert "PROSPECTIVE_MECHANISM_SUPPORT_UNGUARANTEED" not in codes(balanced)
    assert balanced["FEASIBILITY_STATUS"] == "FEASIBLE_FOR_PREREGISTRATION"


def test_missing_support_does_not_fall_back_to_nominal_power():
    proposal = v2_proposal(5000, 5000)
    del proposal["PRIMARY_MECHANISM_SUPPORT"]
    result = compile_proposal_v2(proposal)
    assert result["FEASIBILITY_STATUS"] == "DEFINITION_INCOMPLETE"
    assert "PRIMARY_MECHANISM_SUPPORT_MISSING" in codes(result)
    assert result["DISCOVERY_SCREEN"]["POWER_BASE"] is None
    assert result["DISCOVERY_SCREEN"]["MDE_BASE"] is None
