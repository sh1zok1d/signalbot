"""Tests for the outcome-blind D2 excess path-risk implementation review.

Asserts the review artifacts record the frozen contract faithfully and that
every firewall flag stays closed. No scientific outcome is computed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.research import d2_excess_path_risk_implementation_review as R
from scripts.research.d2_excess_path_risk_beyond_vol_clustering_design import (
    CLASSIFICATION_ORDER,
    verify_design_authorities,
)
from scripts.research.d2_excess_path_risk_evaluator import (
    EXECUTION_PERMIT_REL,
    IMPLEMENTATION_FILES,
    REVIEW_JSON_REL,
    REVIEW_MD_REL,
    UNIT,
)

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def review() -> dict:
    return json.loads((REPO / REVIEW_JSON_REL).read_text(encoding="utf-8"))


def test_review_artifacts_exist(review):
    assert (REPO / REVIEW_JSON_REL).is_file()
    assert (REPO / REVIEW_MD_REL).is_file()
    assert review["unit"] == UNIT
    assert review["kind"] == "OUTCOME_BLIND_IMPLEMENTATION_REVIEW"


def test_canonical_unit_identity_is_exact(review):
    assert review["unit"] == (
        "D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_IMPLEMENTATION_AND_OUTCOME_BLIND_REVIEW"
    )


def test_review_passes_with_no_blocking_findings(review):
    assert review["IMPLEMENTATION_REVIEW"] == "PASS"
    assert review["BLOCKING_FINDINGS"] == []
    assert all(
        body["status"] in {"NOT_CONFIRMED", "CONFIRMED_AND_REPAIRED"}
        for body in review["RED_TEAM_FINDINGS"].values()
    )


def test_review_status_is_derived_from_capability_probes_not_the_findings_table(review):
    """PASS must be earned by the code, not asserted by a dictionary."""

    caps = review["CAPABILITY_PROBES"]
    assert caps["CANONICAL_ORCHESTRATION_IMPLEMENTED"] is True
    assert caps["EXECUTE_IS_TERMINAL_STUB"] is False
    assert caps["PERMIT_GATE_TAKES_ONLY_REPO"] is True
    assert caps["PERMIT_GATE_DERIVES_AUTHORITY_FROM_REPO"] is True
    assert caps["CANONICAL_SELECTOR_DIGEST_IMPLEMENTED"] is True
    assert caps["CONTROL_P95_METHOD_EXPLICIT"] is True
    assert all(caps["CANONICAL_ROUTE_STEPS"].values())
    assert review["SCIENTIFIC_KERNEL_READY"] is True
    assert review["CANONICAL_ORCHESTRATION_READY"] is True
    assert review["AUTHORITY_VERIFICATION_READY"] is True


def test_execution_ready_is_false_because_the_digest_is_not_frozen(review):
    """EXECUTION_READY must not be a synonym for a passing review."""

    assert review["EXECUTION_READY"] is False
    assert "EXPECTED_CANONICAL_SELECTOR_DIGEST_NOT_FROZEN" in review[
        "EXECUTION_BLOCKED_BY"
    ]
    assert "NO_EXECUTION_PERMIT" in review["EXECUTION_BLOCKED_BY"]


def test_exact_selector_identity_is_distinguished_from_row_counts(review):
    assert review["ROW_COUNT_IDENTITY_IMPLEMENTED"] is True
    assert review["EXACT_SELECTOR_IDENTITY_VERIFIED"] is False
    assert review["EXACT_SELECTOR_IDENTITY_STATUS"] == (
        "DIGEST_FUNCTION_IMPLEMENTED_EXPECTED_VALUE_NOT_YET_FROZEN"
    )
    assert review["FROZEN_EXPECTED_SELECTOR_DIGEST"] is None
    assert review["CANONICAL_SELECTOR_DIGEST_VERSION"] == (
        "D2_EXCESS_PATH_RISK_SELECTOR_DIGEST_V1"
    )


def test_frozen_selector_census_separates_population_from_abstentions(review):
    census = review["FROZEN_SELECTOR_CENSUS"]
    assert census["CONSTRUCTED_N"] == 1791
    assert census["ABSTAIN_N"] == 163
    assert census["ABSTAIN_N"] != census["CONSTRUCTED_N"]


def test_control_percentile_convention_is_recorded(review):
    assert review["CONTROL_P95_METHOD"] == "NUMPY_LINEAR_INHERITED_FROM_D2"


def test_repaired_findings_are_recorded_as_confirmed(review):
    for name in (
        "F21_EXECUTION_READY_OVERSTATED_STUB_ROUTE",
        "F22_PERMIT_AUTHORITY_UNDER_BOUND",
        "F23_SELECTOR_IDENTITY_PROVED_COUNTS_NOT_IDENTITY",
        "F24_FROZEN_1791_MISREAD_AS_THE_ABSTAIN_COUNT",
        "F25_CONTROL_PERCENTILE_CONVENTION_IMPLICIT",
    ):
        assert name in review["RED_TEAM_FINDINGS"], f"missing finding {name}"
        assert review["RED_TEAM_FINDINGS"][name]["status"] == "CONFIRMED_AND_REPAIRED"


def test_permit_required_fields_are_published(review):
    for field in (
        "UNIT",
        "DESIGN_JSON_SHA256",
        "IMPLEMENTATION_REVIEW_JSON_SHA256",
        "EVALUATOR_SHA256",
        "CORE_BTC_SNAPSHOT",
        "RUN_IDENTITY",
        "EXPECTED_CANONICAL_SELECTOR_DIGEST",
        "RANDOM_SEED",
        "N_RANDOM_CONTROLS",
        "EXECUTION_AUTHORIZED",
        "ONE_SHOT",
        "RERUN_AUTHORIZED",
    ):
        assert field in review["PERMIT_REQUIRED_FIELDS"]


def test_every_required_failure_class_is_reviewed(review):
    keys = " ".join(review["RED_TEAM_FINDINGS"]).upper()
    for token in (
        "LOOKAHEAD",
        "WRONG_FUTURE_BAR_WINDOW",
        "CLOSES_INSTEAD_OF_HIGH_LOW",
        "DIFFERENT_PATHS_FOR_SIDE_AND_MIRROR",
        "SELECTOR_DRIFT",
        "SIDE_DRIFT",
        "TARGET_INELIGIBILITY_HANDLING",
        "POOLED_K_OR_YEAR_ONLY_FALLBACK",
        "LONG_SHORT_COMPOSITION_MISMATCH",
        "RNG_SEED_DRIFT",
        "REPLACEMENT_SAMPLING",
        "DIFFERENT_MASKS_FOR_SHARE_AND_SCALE",
        "SEPARATE_YEARLY_CONTROL_GENERATION",
        "FUTURE_INFORMATION_MATCHING",
        "GATE_OR_CLASSIFICATION_RESCUE",
        "AUTHORITY_HASH_DRIFT",
        "ACCIDENTAL_REAL_OUTCOME_EXECUTION",
        "PROTECTED_2025_2026_ACCESS",
        "BITMEX_REUSE_FOR_NEW_TARGET",
    ):
        assert token in keys, f"unreviewed failure class: {token}"


def test_frozen_scientific_contract_is_recorded_unchanged(review):
    assert review["PRIMARY_SELECTOR"] == "D2_RULE_1_RV_ABSTENTION"
    assert review["PRIMARY_TARGET"] == "ADVERSE_SHARE"
    assert review["PRIMARY_COMPARATOR"] == (
        "YEAR_SIDE_MATCHED_RATE_MATCHED_RANDOM_ABSTENTION"
    )
    assert review["CONTROL_STRATA"] == "calendar_year × frozen_SIDE"
    assert review["ADVERSE_SHARE_FORMULA"] == "MAE_SIDE / (MAE_SIDE + MAE_OPPOSITE)"
    assert review["PATH_SCALE_FORMULA"] == "MAE_SIDE + MAE_OPPOSITE"
    assert review["STATISTICAL_GATE"] == "MU_SHARE_RULE > CONTROL_SHARE_P95"
    assert review["PRACTICAL_GATE"] == "DELTA_SHARE >= 0.05"
    assert review["TEMPORAL_GATE"] == (
        "DELTA_SHARE > 0 in at least 3 of 5 years"
    )
    assert review["RANDOM_SEED"] == 20260922131
    assert review["N_RANDOM_CONTROLS"] == 10000
    assert review["FROZEN_RULE1_N"] == 1791
    assert review["FROZEN_RULE1_YEAR_N"] == {
        "2020": 334,
        "2021": 364,
        "2022": 364,
        "2023": 364,
        "2024": 365,
    }
    assert review["TARGET_SPECIFIC_INELIGIBILITY"] == (
        "TARGET_ROW_INELIGIBLE_PATH_SCALE_NONPOSITIVE"
    )
    assert review["PATH_SCALE_RELATIVE_BAR"] == 0.2


def test_classification_order_is_frozen_and_unassigned(review):
    assert review["CLASSIFICATION_ORDER"] == list(CLASSIFICATION_ORDER)
    assert review["CLASSIFICATION_ORDER"] == [
        "D2_DECOMPOSITION_INVALID",
        "D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_PROMISING",
        "D2_VOLATILITY_SCALE_COMPATIBLE_NO_EXCESS_ALIGNMENT",
        "D2_DECOMPOSITION_NO_USEFUL_STRUCTURE",
    ]
    assert review["CLASSIFICATION_ASSIGNED"] is None
    assert review["CLASSIFICATIONS_UNASSIGNED"] == list(CLASSIFICATION_ORDER)


def test_firewall_flags_are_all_closed(review):
    assert review["REAL_DECOMPOSITION_OUTCOME_COMPUTED"] is False
    assert review["EXECUTION_AUTHORIZED"] is False
    assert review["EXECUTION_AUTHORIZED_FLAG"] is False
    assert review["EXECUTION_PERMIT_PRESENT"] is False
    assert review["EXECUTION_PERMIT_CREATED"] is False
    assert review["RESULT_CREATED"] is False
    assert review["ARM_CREATED"] is False
    assert review["MARKET_07_CREATED"] is False
    assert review["PROTECTED_2025_OPENED"] is False
    assert review["PROTECTED_2026_OPENED"] is False
    assert review["2025_OPEN_AUTHORIZED"] is False
    assert review["2026_OPEN_AUTHORIZED"] is False
    assert review["BITMEX_2017_2019_REUSED_FOR_NEW_TARGET"] is False
    assert review["SYNTHETIC_TESTS_ONLY"] is True


def test_no_primary_quantity_is_populated(review):
    for key in ("MU_SHARE_RULE", "DELTA_SHARE", "MU_PATH_SCALE_RULE", "DELTA_PATH_SCALE"):
        assert review[key] is None


def test_no_execution_permit_file_was_created():
    assert not (REPO / EXECUTION_PERMIT_REL).is_file()


def test_no_result_artifact_was_created():
    for name in (
        "D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_RESULT.json",
        "D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_RESULT.md",
    ):
        assert not (REPO / "docs/research" / name).exists()


def test_authorities_are_bound_without_drift(review):
    assert review["DESIGN_AUTHORITY_BLOCKERS"] == []
    assert review["FROZEN_AUTHORITY_STATUS"] == "BOUND_NO_DRIFT"
    assert verify_design_authorities(REPO) == []
    assert len(review["DESIGN_JSON_SHA256"]) == 64
    assert set(review["IMPLEMENTATION_FILE_SHA256"]) == set(IMPLEMENTATION_FILES)
    assert len(review["RUN_IDENTITY"]) == 64


def test_design_was_not_redesigned(review):
    assert review["DESIGN_NOT_REDESIGNED"] is True
    assert review["DESIGN_STATUS"] == "FROZEN"
    assert review["SCIENTIFIC_AMBIGUITY_FOUND"] is False
    assert review["NEW_RESEARCHER_CONVENTION_INTRODUCED"] is False


def test_next_unit_freezes_the_selector_digest_before_the_one_shot(review):
    assert review["NEXT_UNIT"] == (
        "D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_PRE_OUTCOME_SELECTOR_IDENTITY_COMMIT"
    )
    assert review["UNIT_AFTER_NEXT"] == (
        "D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_ONE_SHOT_EXECUTION"
    )
    assert "BEFORE any ADVERSE_SHARE" in review["NEXT_UNIT_REQUIREMENT"]
    assert "RESULT" in review["NOT_CREATED"]
    assert "execution permit" in review["NOT_CREATED"]


def test_markdown_mirror_states_not_executed():
    text = (REPO / REVIEW_MD_REL).read_text(encoding="utf-8")
    assert "was NOT executed" in text
    assert "REAL_DECOMPOSITION_OUTCOME_COMPUTED = False" in text
    assert "D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_ONE_SHOT_EXECUTION" in text


def test_review_is_byte_reproducible_from_the_implementation_commit(review):
    """A future permit binds this artifact's hash, so it must regenerate exactly.

    The identity is a function of repository content and the implementation
    commit only. It must not drift with whatever HEAD happens to be.
    """

    rebuilt = R.build_review(
        repo=REPO, implementation_commit=review["FINAL_IMPLEMENTATION_COMMIT"]
    )
    assert rebuilt["RUN_IDENTITY"] == review["RUN_IDENTITY"]
    assert rebuilt["FINAL_IMPLEMENTATION_TREE"] == review["FINAL_IMPLEMENTATION_TREE"]
    assert rebuilt == review, "review artifact is not byte-reproducible"


def test_run_identity_binds_the_implementation_commit_and_tree(review):
    inputs = review["RUN_IDENTITY_INPUTS"]
    assert inputs["FINAL_IMPLEMENTATION_COMMIT"] == review["FINAL_IMPLEMENTATION_COMMIT"]
    assert inputs["FINAL_IMPLEMENTATION_TREE"] == review["FINAL_IMPLEMENTATION_TREE"]
    assert len(review["FINAL_IMPLEMENTATION_COMMIT"]) == 40
    assert len(review["FINAL_IMPLEMENTATION_TREE"]) == 40
    assert inputs["CORE_BTC_SNAPSHOT"] == (
        "717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415"
    )
    assert inputs["RANDOM_SEED"] == 20260922131
