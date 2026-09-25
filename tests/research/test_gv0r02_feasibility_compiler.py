"""GV0R02 compiler implementation. Golden cases use frozen planning records only."""

import json

import pytest

from scripts.research.gv0r02_feasibility_compiler import (
    COMPILER_POLICY_VERSION,
    COMPILER_SCHEMA_VERSION,
    POWER_PROFILE,
    check_revision,
    compile_golden,
    compile_proposal,
    derive_feature_registry,
    golden_proposals,
)

RESOLUTION = 1.6473952425747334e-59


def test_registry_is_deterministic_and_has_no_portability_grade():
    first = derive_feature_registry()
    second = derive_feature_registry()
    assert first == second
    assert first["FEATURE_REGISTRY_VERSION"] == "GV0R02_FEATURE_REGISTRY_V0"
    assert first["FEATURES"]
    for row in first["FEATURES"]:
        assert "PORTABILITY" not in row
        assert row["definition_digest"]


def test_missing_fields_and_version_mismatch():
    proposal = golden_proposals()["GOLDEN_C004"]
    broken = {key: value for key, value in proposal.items() if key != "MECHANISM"}
    result = compile_proposal(broken)
    assert result["FEASIBILITY_STATUS"] == "DEFINITION_INCOMPLETE"
    mismatched = {**proposal, "COMPILER_SCHEMA_VERSION": "GV0R02_SCHEMA_V9"}
    assert compile_proposal(mismatched)["FEASIBILITY_STATUS"] == "DEFINITION_INCOMPLETE"


def test_pass_a_missing_feature_blocks():
    proposal = golden_proposals()["GOLDEN_C012"]
    proposal = {**proposal, "PROPOSAL_ID": "MISSING", "FEATURE_REQUIREMENTS": ["OPEN_INTEREST"]}
    result = compile_proposal(proposal)
    assert result["FEASIBILITY_STATUS"] == "DATA_BLOCKED"
    assert result["BLOCKERS"][0]["BLOCKER_CODE"] == "MISSING_FEATURE"


def test_era_pooling_stays_off_unless_expected():
    result = compile_proposal(golden_proposals()["GOLDEN_C012"])
    assert result["ERA_POLICY"]["BITMEX_ADDED_TO_DISCOVERY_N"] is False
    assert result["ERA_POLICY"]["POOLED_INTO_DISCOVERY"] is False
    pooled = {**golden_proposals()["GOLDEN_C012"], "ERA_INVARIANCE_PRIOR": "EXPECTED"}
    both = compile_proposal(pooled)["ERA_POLICY"]
    assert both["HOMOGENEOUS_EFFECT_SCREEN"] == "REPORTED"
    assert both["ZERO_EFFECT_IN_ONE_ERA_STRESS"] == "REPORTED"
    assert both["BITMEX_ADDED_TO_DISCOVERY_N"] is False


def test_power_profile_is_not_mutated():
    before = json.dumps(POWER_PROFILE, sort_keys=True)
    compile_proposal(golden_proposals()["GOLDEN_C012"])
    assert json.dumps(POWER_PROFILE, sort_keys=True) == before
    assert POWER_PROFILE["SIMULATION_SEED"] == 20020


def test_revision_provenance_rejects_a_second_change_and_a_forbidden_field():
    parent = golden_proposals()["GOLDEN_C004"]
    result = compile_proposal(parent)
    record = check_revision(parent, {**parent, "EVENT_OR_STATE_DEFINITION": "wider"}, revision_number=1, reason="structural", parent_result_id=result["RESULT_ID"])
    assert record["REVISION_NUMBER"] == 1
    assert record["ORIGINAL_RESULT_ID"] == result["RESULT_ID"]
    with pytest.raises(ValueError):
        check_revision(parent, parent, revision_number=2, reason="again", parent_result_id=result["RESULT_ID"])
    with pytest.raises(ValueError):
        check_revision(parent, {**parent, "NAMED_INFERENCE_CLASS": "PLACEBO_REFERENCE_DISTRIBUTION"}, revision_number=1, reason="shop", parent_result_id=result["RESULT_ID"])


def test_result_identity_includes_versions():
    result = compile_proposal(golden_proposals()["GOLDEN_C004"])
    assert result["COMPILER_SCHEMA_VERSION"] == COMPILER_SCHEMA_VERSION
    assert result["COMPILER_POLICY_VERSION"] == COMPILER_POLICY_VERSION
    assert result["POWER_ASSUMPTION_PROFILE_VERSION"] == "GV0R02_POWER_PROFILE_V0"
    assert result["PROTECTED_HOLDOUT_COMPATIBILITY"]["PROTECTED_VALUES_OPENED"] is False
    assert result["MARKET_OUTCOMES_OPENED"] is False
    again = compile_proposal(golden_proposals()["GOLDEN_C004"])
    assert again["RESULT_ID"] == result["RESULT_ID"]


def test_golden_cases():
    compiled = compile_golden()
    results = compiled["RESULTS"]
    c012 = results["GOLDEN_C012"]
    assert c012["FEASIBILITY_STATUS"] == "INFORMATIONALLY_WEAK"
    assert c012["MDE_STRESS"] == 0.6093023255813953
    assert c012["ALPHA_ATTAINABLE"] is True
    c004 = results["GOLDEN_C004"]
    assert c004["FEASIBILITY_STATUS"] == "INFERENCE_SUPPORT_INSUFFICIENT"
    assert c004["PRIMARY_SUPPORT_SIZE"] == 16
    assert c004["MIN_ATTAINABLE_P"] == 0.0625
    assert c004["ALPHA_ATTAINABLE"] is False
    c020 = results["GOLDEN_C020"]
    assert c020["FEASIBILITY_STATUS"] == "INFORMATIONALLY_WEAK"
    assert c020["NAMED_INFERENCE_CLASS"] == "PLACEBO_REFERENCE_DISTRIBUTION"
    assert c020["REFERENCE_SUPPORT_RESOLUTION"] == RESOLUTION
    assert c020["MIN_ATTAINABLE_P"] is None
    assert c020["MONTE_CARLO_P_FLOOR"] == pytest.approx(1 / 1001)
    assert c020["POWER_AT_MIN_MEANINGFUL_EFFECT_BASE"] == 0.79
    assert c020["POWER_AT_MIN_MEANINGFUL_EFFECT_STRESS"] == 0.4
    assert compiled["FAST_PASS_RUNTIME_SECONDS"] < 5
    assert compiled["MARKET_OUTCOMES_OPENED"] is False
