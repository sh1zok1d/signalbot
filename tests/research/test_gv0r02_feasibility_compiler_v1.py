"""GV0R02 compiler mapped to HYPOTHESIS_EVALUATION_CONTRACT_V1. Structural fixtures only."""

import copy

import pytest

from scripts.research import gv0r02_feasibility_compiler as v0
from scripts.research.gv0r02_feasibility_compiler_v1 import (
    COMPILER_POLICY_VERSION,
    COMPILER_SCHEMA_VERSION,
    MAX_PRIMARY_CELLS,
    compile_proposal_v1,
    golden_proposals_v1,
    v1_fields,
    z_two_sided,
)


def codes(result):
    return [b["BLOCKER_CODE"] for b in result["BLOCKERS"]]


def positive_control(**overrides):
    """Same synthetic feasible fixture as the V0 positive control, with a V1 declaration."""
    p = v0._base_proposal(
        PROPOSAL_ID="GV0R02_V1_POSITIVE_CONTROL_SYNTHETIC",
        MECHANISM="synthetic frequent second-moment shift used only to exercise the feasible path",
        FALSIFIABLE_CLAIM="a predeclared 0.20 standardized shift is detectable at the frozen stress screen",
        EXPECTED_DIRECTION="POSITIVE",
        EVENT_OR_STATE_DEFINITION="synthetic state observed on every decision bar",
        PRIMARY_OBSERVABLE="synthetic standardized second moment",
        ENDPOINT_MOMENT="SECOND_MOMENT",
        COUNTERFACTUAL_CLASS="within-sample sign symmetry",
        MIN_MEANINGFUL_EFFECT=0.20,
        MIN_MEANINGFUL_EFFECT_UNITS="STANDARDIZED_SECOND_MOMENT",
        MIN_MEANINGFUL_EFFECT_RATIONALE="planning magnitude chosen so the frozen stress MDE is inside the bar",
        OUTCOME_BLIND_SAMPLE={
            "NOMINAL_OBSERVATION_COUNT": 10000,
            "COUNT_BY_YEAR": {"2020": 2000, "2021": 2000, "2022": 2000, "2023": 2000, "2024": 2000},
            "COUNT_BY_ERA": {"BINANCE_2020_2024": 10000},
            "COUNT_BY_VENUE": {"BINANCE": 10000},
            "COUNT_BY_EVENT_FAMILY": {},
        },
    )
    p.update(v1_fields())
    p.update(overrides)
    return p


def test_versions_are_new_and_v0_is_untouched():
    assert COMPILER_SCHEMA_VERSION == "GV0R02_SCHEMA_V1"
    assert COMPILER_POLICY_VERSION == "GV0R02_POLICY_V1"
    assert v0.COMPILER_SCHEMA_VERSION == "GV0R02_SCHEMA_V0"
    assert v0.COMPILER_POLICY_VERSION == "GV0R02_POLICY_V0"


def test_golden_cases_keep_their_binding_constraint_under_v1():
    expected = {"GOLDEN_C012": "INFORMATIONALLY_WEAK", "GOLDEN_C004": "INFERENCE_SUPPORT_INSUFFICIENT",
                "GOLDEN_C020": "INFORMATIONALLY_WEAK"}
    for name, proposal in golden_proposals_v1().items():
        result = compile_proposal_v1(proposal)
        assert result["FEASIBILITY_STATUS"] == expected[name], (name, result["BLOCKERS"])
        assert result["MARKET_OUTCOMES_OPENED"] is False
        assert v0.compile_proposal(v0.golden_proposals()[name])["FEASIBILITY_STATUS"] == expected[name]


def test_positive_control_is_feasible_and_records_heterogeneity_assessability():
    result = compile_proposal_v1(positive_control())
    assert result["FEASIBILITY_STATUS"] == "FEASIBLE_FOR_PREREGISTRATION", result["BLOCKERS"]
    het = result["HETEROGENEITY_ASSESSABILITY"]
    assert het["STATUS"] == "ASSESSABLE" and het["NOT_EVIDENCE_OF_STABILITY"] is True


def test_v0_proposal_without_v1_fields_is_incomplete():
    p = v0._base_proposal(PROPOSAL_ID="V0_ONLY")
    result = compile_proposal_v1(p)
    assert result["FEASIBILITY_STATUS"] == "DEFINITION_INCOMPLETE"
    assert "V1_FIELDS_MISSING" in codes(result)


def test_context_claim_may_not_be_directional():
    p = positive_control(CLAIM_TYPE="CONTEXT_DESCRIPTIVE", ENDPOINT_MOMENT="FIRST_MOMENT",
                         PRACTICAL_BAR_BASIS="PRODUCT_RELEVANCE", NUISANCE_DIAGNOSTIC_PLANNED=True)
    result = compile_proposal_v1(p)
    assert result["FEASIBILITY_STATUS"] == "DEFINITION_INCOMPLETE"
    assert "CONTEXT_CLAIM_DIRECTIONAL" in codes(result)


def test_context_claim_needs_the_nuisance_diagnostic_and_product_basis():
    p = positive_control(CLAIM_TYPE="CONTEXT_DESCRIPTIVE")
    result = compile_proposal_v1(p)
    assert "CONTEXT_NUISANCE_DIAGNOSTIC_MISSING" in codes(result)
    assert "PRACTICAL_BAR_BASIS_INVALID" in codes(result)
    ok = positive_control(CLAIM_TYPE="CONTEXT_DESCRIPTIVE", NUISANCE_DIAGNOSTIC_PLANNED=True,
                          PRACTICAL_BAR_BASIS="PRODUCT_RELEVANCE")
    assert compile_proposal_v1(ok)["FEASIBILITY_STATUS"] == "FEASIBLE_FOR_PREREGISTRATION"


def test_incremental_claim_needs_standard_nuisance_or_a_written_exclusion():
    roles = {"REGIME_VARIABLES": [], "MECHANISM_VARIABLES": ["M"], "NUISANCE_BASELINE_VARIABLES": ["LAGGED_TARGET"]}
    p = positive_control(VARIABLE_ROLES=roles, INTRADAY=True)
    result = compile_proposal_v1(p)
    blocker = next(b for b in result["BLOCKERS"] if b["BLOCKER_CODE"] == "STANDARD_NUISANCE_MISSING")
    assert set(blocker["BLOCKER_OBJECT"]["VARIABLES"]) == {"PRIOR_REALIZED_VOLATILITY", "TIME_OF_DAY"}
    excluded = positive_control(
        VARIABLE_ROLES={**roles, "NUISANCE_BASELINE_VARIABLES": ["LAGGED_TARGET", "TIME_OF_DAY"]}, INTRADAY=True,
        NUISANCE_EXCLUSIONS=[{"VARIABLE": "PRIOR_REALIZED_VOLATILITY",
                              "MECHANISM_ARGUMENT": "the mechanism is defined as a volatility state"}])
    assert "STANDARD_NUISANCE_MISSING" not in codes(compile_proposal_v1(excluded))
    empty_argument = positive_control(
        VARIABLE_ROLES={**roles, "NUISANCE_BASELINE_VARIABLES": ["LAGGED_TARGET", "TIME_OF_DAY"]}, INTRADAY=True,
        NUISANCE_EXCLUSIONS=[{"VARIABLE": "PRIOR_REALIZED_VOLATILITY", "MECHANISM_ARGUMENT": "  "}])
    assert "STANDARD_NUISANCE_MISSING" in codes(compile_proposal_v1(empty_argument))


def test_mechanism_may_not_be_conditioned_away():
    roles = {"REGIME_VARIABLES": [], "MECHANISM_VARIABLES": ["PRIOR_REALIZED_VOLATILITY"],
             "NUISANCE_BASELINE_VARIABLES": ["PRIOR_REALIZED_VOLATILITY", "LAGGED_TARGET"]}
    assert "MECHANISM_CONDITIONED_AWAY" in codes(compile_proposal_v1(positive_control(VARIABLE_ROLES=roles)))


def test_directional_incremental_claim_needs_a_cost_based_bar():
    p = positive_control(ENDPOINT_MOMENT="FIRST_MOMENT", PRACTICAL_BAR_BASIS="PRODUCT_RELEVANCE")
    assert "PRACTICAL_BAR_BASIS_INVALID" in codes(compile_proposal_v1(p))


def test_regime_rules_follow_the_target_class():
    conditional = positive_control(TARGET_CLASS="CONDITIONAL")
    assert "REGIME_MISSING_FOR_CONDITIONAL_CLAIM" in codes(compile_proposal_v1(conditional))
    roles = {"REGIME_VARIABLES": ["R"], "MECHANISM_VARIABLES": ["M"],
             "NUISANCE_BASELINE_VARIABLES": ["PRIOR_REALIZED_VOLATILITY", "LAGGED_TARGET"]}
    unconditional = positive_control(VARIABLE_ROLES=roles)
    assert "REGIME_DECLARED_FOR_UNCONDITIONAL_CLAIM" in codes(compile_proposal_v1(unconditional))
    cells_without_regime = positive_control(TARGET_CLASS="CONDITIONAL", VARIABLE_ROLES=roles)
    assert "PRIMARY_CELLS_INVALID" in codes(compile_proposal_v1(cells_without_regime))


def test_at_most_three_primary_cells():
    cells = [{"REGIME": None, "ESTIMAND": "E", "HORIZON": f"H{i}"} for i in range(MAX_PRIMARY_CELLS + 1)]
    assert "PRIMARY_CELLS_INVALID" in codes(compile_proposal_v1(positive_control(PRIMARY_CELLS=cells)))


def test_holm_adjustment_lowers_power_and_can_flip_to_weak():
    def borderline(k):
        cells = [{"REGIME": None, "ESTIMAND": "E", "HORIZON": f"H{i}"} for i in range(k)]
        sample = {**positive_control()["OUTCOME_BLIND_SAMPLE"], "NOMINAL_OBSERVATION_COUNT": 850}
        return compile_proposal_v1(positive_control(PRIMARY_CELLS=cells, OUTCOME_BLIND_SAMPLE=sample))
    one, three = borderline(1), borderline(3)
    assert one["ALPHA_PER_CELL_HOLM_FIRST_STEP"] == pytest.approx(0.05)
    assert three["ALPHA_PER_CELL_HOLM_FIRST_STEP"] == pytest.approx(0.05 / 3)
    assert three["DISCOVERY_SCREEN"]["POWER_STRESS"] < one["DISCOVERY_SCREEN"]["POWER_STRESS"]
    assert one["FEASIBILITY_STATUS"] == "FEASIBLE_FOR_PREREGISTRATION"
    assert three["FEASIBILITY_STATUS"] == "INFORMATIONALLY_WEAK"
    assert z_two_sided(0.05) == pytest.approx(v0.POWER_PROFILE["Z_ALPHA"], abs=1e-9)


def test_frozen_screen_with_several_cells_must_declare_multiplicity_adjustment():
    cells = [{"REGIME": None, "ESTIMAND": "E", "HORIZON": f"H{i}"} for i in range(2)]
    screen = {"POWER": {"MDE_BASE": 0.05, "MDE_STRESS": 0.1, "POWER_BASE": 0.99, "POWER_STRESS": 0.95}}
    p = positive_control(PRIMARY_CELLS=cells, FROZEN_OUTCOME_BLIND_SCREEN=screen)
    assert "MULTIPLICITY_NOT_ADJUSTED" in codes(compile_proposal_v1(p))
    adjusted = copy.deepcopy(screen)
    adjusted["POWER"]["MULTIPLICITY_ADJUSTED"] = True
    p = positive_control(PRIMARY_CELLS=cells, FROZEN_OUTCOME_BLIND_SCREEN=adjusted)
    assert compile_proposal_v1(p)["FEASIBILITY_STATUS"] == "FEASIBLE_FOR_PREREGISTRATION"


def test_historical_replication_must_be_time_disjoint_and_powered():
    overlap = v1_fields()["REPLICATION_SURFACE"] | {"START": "2019-01-01", "END": "2021-01-01"}
    assert "REPLICATION_NOT_TIME_DISJOINT" in codes(compile_proposal_v1(positive_control(REPLICATION_SURFACE=overlap)))
    small = v1_fields()["REPLICATION_SURFACE"] | {"NOMINAL_OBSERVATION_COUNT": 100}
    result = compile_proposal_v1(positive_control(REPLICATION_SURFACE=small))
    assert result["FEASIBILITY_STATUS"] == "INFORMATIONALLY_WEAK"
    assert "REPLICATION_MDE_TOO_LARGE" in codes(result)
    missing = {k: v for k, v in v1_fields()["REPLICATION_SURFACE"].items() if k != "NOMINAL_OBSERVATION_COUNT"}
    assert "REPLICATION_COUNT_MISSING" in codes(compile_proposal_v1(positive_control(REPLICATION_SURFACE=missing)))


def prospective(**rule_overrides):
    rule = {"MAX_EPISODES": 5000, "END_DATE": "2028-06-01", "MIN_N": 3000,
            "COUNTS_ONLY_MONITORING": True, "PRODUCT_EXPOSURE_HANDLING": "no product statistic from these episodes"}
    rule.update(rule_overrides)
    return {"KIND": "PROSPECTIVE", "ID": "FUTURE", "START": "2027-01-01", "STARTS_AFTER_FREEZE": True,
            "STOPPING_RULE": rule}


def test_prospective_replication_needs_a_fixed_stopping_rule():
    ok = compile_proposal_v1(positive_control(REPLICATION_SURFACE=prospective()))
    assert ok["FEASIBILITY_STATUS"] == "FEASIBLE_FOR_PREREGISTRATION", ok["BLOCKERS"]
    no_rule = {k: v for k, v in prospective().items() if k != "STOPPING_RULE"}
    assert "STOPPING_RULE_MISSING" in codes(compile_proposal_v1(positive_control(REPLICATION_SURFACE=no_rule)))
    for override in ({"COUNTS_ONLY_MONITORING": False}, {"PRODUCT_EXPOSURE_HANDLING": ""},
                     {"MIN_N": None}, {"MAX_EPISODES": None, "END_DATE": None}):
        result = compile_proposal_v1(positive_control(REPLICATION_SURFACE=prospective(**override)))
        assert "STOPPING_RULE_MISSING" in codes(result), override
    bad = compile_proposal_v1(positive_control(REPLICATION_SURFACE=prospective(MIN_N=9000)))
    assert "STOPPING_RULE_INVALID" in codes(bad)
    not_after_freeze = prospective() | {"STARTS_AFTER_FREEZE": False}
    assert "PROSPECTIVE_NOT_AFTER_FREEZE" in codes(compile_proposal_v1(positive_control(REPLICATION_SURFACE=not_after_freeze)))


def test_prospective_power_uses_the_minimum_n():
    result = compile_proposal_v1(positive_control(REPLICATION_SURFACE=prospective(MIN_N=50, MAX_EPISODES=60)))
    assert "REPLICATION_MDE_TOO_LARGE" in codes(result)


def test_protected_window_overlap_needs_its_own_decision():
    live = prospective() | {"START": "2026-11-01"}
    result = compile_proposal_v1(positive_control(REPLICATION_SURFACE=live))
    assert result["FEASIBILITY_STATUS"] == "DATA_BLOCKED"
    assert "PROTECTED_SURFACE_DECISION_REQUIRED" in codes(result)
    disc = compile_proposal_v1(positive_control(DISCOVERY_SURFACE={"ID": "X", "START": "2024-01-01", "END": "2025-06-01"}))
    assert "PROTECTED_SURFACE_DECISION_REQUIRED" in codes(disc)


def test_low_heterogeneity_power_is_recorded_not_blocking():
    sample = {**positive_control()["OUTCOME_BLIND_SAMPLE"], "COUNT_BY_YEAR": {"2020": 2, "2021": 2, "2022": 9996}}
    result = compile_proposal_v1(positive_control(OUTCOME_BLIND_SAMPLE=sample))
    assert result["HETEROGENEITY_ASSESSABILITY"]["STATUS"] == "NOT_ASSESSABLE"
    assert result["HETEROGENEITY_ASSESSABILITY"]["NOT_EVIDENCE_OF_STABILITY"] is True
    assert result["FEASIBILITY_STATUS"] == "FEASIBLE_FOR_PREREGISTRATION"
    two_epochs = {**sample, "COUNT_BY_YEAR": {"2020": 5000, "2021": 5000}}
    het = compile_proposal_v1(positive_control(OUTCOME_BLIND_SAMPLE=two_epochs))["HETEROGENEITY_ASSESSABILITY"]
    assert het["STATUS"] == "NOT_ASSESSABLE" and het["REASON"] == "FEWER_THAN_3_EPOCHS_WITH_COUNTS"


def test_result_identity_changes_with_v1_fields_and_is_deterministic():
    a = compile_proposal_v1(positive_control())
    b = compile_proposal_v1(positive_control())
    c = compile_proposal_v1(positive_control(CLAIM_TYPE="CONTEXT_DESCRIPTIVE", NUISANCE_DIAGNOSTIC_PLANNED=True,
                                             PRACTICAL_BAR_BASIS="PRODUCT_RELEVANCE"))
    assert a["RESULT_ID"] == b["RESULT_ID"] != c["RESULT_ID"]


def test_wrong_schema_version_is_incomplete():
    result = compile_proposal_v1(positive_control(COMPILER_SCHEMA_VERSION="GV0R02_SCHEMA_V0"))
    assert result["FEASIBILITY_STATUS"] == "DEFINITION_INCOMPLETE"
