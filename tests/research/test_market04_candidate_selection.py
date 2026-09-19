"""MARKET-04 candidate-selection freeze checks.

Outcome-blind identity freeze only. Does not open protected OOS, inspect
MARKET-04 outcomes, or authorize execution.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MD = REPO / "docs/research/MARKET_04_CANDIDATE_SELECTION.md"
JSON_PATH = REPO / "docs/research/MARKET_04_CANDIDATE_SELECTION.json"
REGISTRY_MD = REPO / "docs/research/EVIDENCE_REGISTRY_H_B_M01_M03.md"
REGISTRY_JSON = REPO / "docs/research/EVIDENCE_REGISTRY_H_B_M01_M03.json"

CANDIDATE = "MARKET-04_FUNDING_STATE_ADVERSE_PATH_RISK"
REGISTRY_HEAD = "ec7960d5cad47682fec1fa5d33b1a03997a8b62b"
REGISTRY_TREE = "293e6d338b0cde1e9859435036f6bef4c427520f"
REGISTRY_MD_SHA256 = "f30b44a2d333600e3e6417f517e65c5dc1bde81fb03a6d1870cfcf19576c83c2"
REGISTRY_JSON_SHA256 = "0892f66db94cc679cb938980127985ab9a81efece62b2adb755c1b7e8a048c72"

FORBIDDEN_ARTIFACT_GLOBS = (
    "docs/research/MARKET_04_*RESULT*",
    "docs/research/MARKET_04_*ARM*",
    "docs/research/MARKET_04_*RESERVATION*",
    "docs/research/MARKET_04_*PREREG*",
    "docs/research/MARKET_04_*IMPLEMENTATION*",
    "scripts/research/market_04*",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load() -> dict:
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


def _md() -> str:
    return MD.read_text(encoding="utf-8")


def test_candidate_identity_and_role():
    payload = _load()
    md = _md()
    assert payload["candidate"] == CANDIDATE
    assert payload["research_id"] == CANDIDATE
    assert payload["short_name"] == "MARKET-04"
    assert payload["role"] == "RISK_STATE_FILTER"
    assert payload["candidate_role"] == "RISK_STATE_FILTER"
    assert payload["not_role"] == "DIRECTION_PREDICTOR"
    assert payload["direction_predictor"] is False
    assert payload["mechanism_family"] == "F5_POSITIONING_OI_FUNDING"
    assert payload["status"] == "SELECTED_OUTCOME_BLIND_NOT_PREREGISTERED_NOT_AUTHORIZED"
    assert payload["market_04_selected"] is True
    assert payload["candidate_identity_frozen"] is True
    assert "candidate = MARKET-04_FUNDING_STATE_ADVERSE_PATH_RISK" in md
    assert "role = RISK_STATE_FILTER" in md
    assert "direction_predictor = false" in md
    assert "CANDIDATE_ROLE = RISK_STATE_FILTER" in md
    assert "NOT_ROLE = DIRECTION_PREDICTOR" in md


def test_market_03_adaptive_lineage_not_independent():
    payload = _load()
    md = _md()
    assert (
        payload["market_03_lineage"]
        == "ADAPTIVE_HYPOTHESIS_GENERATION_FROM_EXTERNAL_REPRODUCTION"
    )
    assert payload["independent_replication_of_market_03"] is False
    assert payload["lineage"]["kind"] == (
        "ADAPTIVE_HYPOTHESIS_GENERATION_FROM_EXTERNAL_REPRODUCTION"
    )
    assert payload["lineage"]["independent_replication_of_market_03"] is False
    assert payload["lineage"]["parent"] == "MARKET-03"
    assert payload["lineage"]["child"] == "MARKET-04"
    assert "independent_replication_of_market_03 = false" in md
    assert (
        "kind = ADAPTIVE_HYPOTHESIS_GENERATION_FROM_EXTERNAL_REPRODUCTION"
        in md
    )
    assert "MARKET-04 positive ≠ independent replication of MARKET-03" in md
    assert "MARKET-04 negative ≠ MARKET-03 reproduction was invalid" in md


def test_m01_m02_are_not_positive_support():
    payload = _load()
    md = _md()
    assert payload["market_01_02_rescue"] is False
    assert payload["novelty_vs_market_01_02"]["market_01_02_are_positive_support"] is False
    assert payload["novelty_vs_market_01_02"]["market_01_02_rescue"] is False
    assert payload["novelty_vs_market_01_02"][
        "negative_directional_tests_are_not_positive_evidence_for_market_04"
    ] is True
    assert "market_01_02_rescue = false" in md
    assert "market_01_02_are_positive_support = false" in md
    assert "positive support" in md


def test_primary_family_is_adverse_path_risk_not_pnl():
    payload = _load()
    md = _md()
    assert payload["primary_outcome_family"] == "FUTURE_ADVERSE_PATH_RISK"
    assert payload["pnl_is_primary_outcome"] is False
    assert payload["final_horizon_return_is_primary"] is False
    assert payload["outcome_family"]["pnl_must_not_be_primary"] is True
    assert "PRIMARY_OUTCOME_FAMILY = FUTURE_ADVERSE_PATH_RISK" in md
    assert "pnl_is_primary_outcome = false" in md
    assert "PnL must" in md or "pnl must" in md.lower()


def test_ema600_and_threshold_55_are_not_inherited():
    payload = _load()
    md = _md()
    assert payload["novelty_vs_market_03"]["ema600_is_defining_population"] is False
    assert payload["novelty_vs_market_03"]["threshold_55_inherited"] is False
    assert "ema600_is_defining_population = false" in md
    assert "threshold_55_inherited = false" in md
    assert "EMA600 entry population" in md
    assert "author threshold 55 as inherited authority" in md
    forbidden = payload["novelty_vs_market_03"]["forbidden_defining_design"]
    assert any("EMA600" in item for item in forbidden)
    assert any("threshold 55" in item for item in forbidden)


def test_funding_publication_unresolved_and_execution_unauthorized():
    payload = _load()
    md = _md()
    assert payload["funding_publication_latency_proven"] is False
    assert payload["funding_legal_historical_availability_resolved"] is False
    assert payload["execution_authorized"] is False
    assert payload["funding_availability"]["funding_legal_historical_availability"] == (
        "UNRESOLVED"
    )
    assert payload["funding_availability"]["market_04_execution_authorized"] is False
    assert payload["funding_availability"]["if_availability_cannot_be_established"] == (
        "BLOCKED_OBSERVABLE"
    )
    assert "funding_publication_latency_proven = false" in md
    assert "funding_legal_historical_availability_resolved = false" in md
    assert "execution_authorized = false" in md
    assert "FUNDING_LEGAL_HISTORICAL_AVAILABILITY = UNRESOLVED" in md
    assert "MARKET_04_EXECUTION_AUTHORIZED = NO" in md


def test_no_result_arm_or_prereg_implementation_created():
    payload = _load()
    assert payload["full_preregistration_frozen"] is False
    assert payload["implementation_frozen"] is False
    assert payload["armed"] is False
    assert payload["lifecycle"]["result_created"] is False
    assert payload["lifecycle"]["arm_created"] is False
    assert payload["lifecycle"]["evaluator_implemented"] is False
    matches = []
    for pattern in FORBIDDEN_ARTIFACT_GLOBS:
        matches.extend(REPO.glob(pattern))
    assert matches == []
    assert not (REPO / "docs/research/MARKET_04_FUNDING_STATE_ADVERSE_PATH_RISK_PREREG.md").exists()
    assert not (REPO / "docs/research/MARKET_04_FUNDING_STATE_ADVERSE_PATH_RISK_RESULT.json").exists()
    assert not (REPO / "docs/research/MARKET_04_FUNDING_STATE_ADVERSE_PATH_RISK_ARM.json").exists()


def test_protected_oos_untouched_and_no_market04_outcome_numbers():
    payload = _load()
    md = _md()
    dumped = json.dumps(payload)
    assert payload["protected_oos_touched"] is False
    assert payload["scientific_outcomes_inspected"] is False
    assert "protected_oos_touched = false" in md
    assert "scientific_outcomes_inspected = false" in md
    assert "SIGNALBOT_PROTECTED_OOS_UNTOUCHED = YES" in md
    for needle in (
        "MDD_filtered",
        "beta_candidate",
        "beta_confirmation",
        "MAE_mean",
        "market_04_beta",
        "market_04_p",
    ):
        assert needle not in dumped
        assert needle not in md
    assert "-0.337755" not in md
    assert "-0.493553" not in md
    assert "-0.000163" not in md
    assert "-0.000183" not in dumped


def test_bound_registry_identity_and_next_unit():
    payload = _load()
    md = _md()
    bound = payload["bound_evidence_registry"]
    assert bound["registry_head"] == REGISTRY_HEAD
    assert bound["registry_tree"] == REGISTRY_TREE
    assert _sha256(REGISTRY_MD) == REGISTRY_MD_SHA256
    assert _sha256(REGISTRY_JSON) == REGISTRY_JSON_SHA256
    assert bound["registry_md_sha256"] == REGISTRY_MD_SHA256
    assert bound["registry_json_sha256"] == REGISTRY_JSON_SHA256
    assert payload["pre_m04_selection_head"] == REGISTRY_HEAD
    assert payload["pre_m04_selection_tree"] == REGISTRY_TREE
    assert payload["next_unit"] == (
        "OUTCOME_BLIND_FUNDING_AVAILABILITY_AND_MARKET04_DESIGN_FEASIBILITY"
    )
    assert (
        "NEXT_UNIT = OUTCOME_BLIND_FUNDING_AVAILABILITY_AND_MARKET04_DESIGN_FEASIBILITY"
        in md
    )


def test_markdown_json_semantic_consistency():
    payload = _load()
    md = _md()
    assert payload["scientific_question"] in md
    assert payload["primary_mechanism"] in md
    assert "CORE_PRICE_STATE + FUNDING_STATE" in md
    assert payload["interpretation_boundary"]["numeric_success_thresholds_created_in_this_unit"] is False
    assert "funding is useless" in md
    assert payload["next_unit"] in md
    for flag in (
        "market_04_selected = true",
        "candidate_identity_frozen = true",
        "full_preregistration_frozen = false",
        "implementation_frozen = false",
        "armed = false",
    ):
        assert flag in md
