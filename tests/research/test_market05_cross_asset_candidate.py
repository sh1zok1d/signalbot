"""MARKET-05 candidate-selection freeze checks.

Outcome-blind identity freeze only. Does not open protected OOS, inspect
MARKET-05 scientific outcomes, or authorize execution.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MD = REPO / "docs/research/MARKET_05_CROSS_ASSET_CANDIDATE.md"
JSON_PATH = REPO / "docs/research/MARKET_05_CROSS_ASSET_CANDIDATE.json"
M04_MD = REPO / "docs/research/MARKET_04_CANDIDATE_SELECTION.md"
M04_JSON = REPO / "docs/research/MARKET_04_CANDIDATE_SELECTION.json"
M04H_MD = REPO / "docs/research/MARKET_04H_PREMIUM_OBSERVABLE_ADJUDICATION.md"
M04H_JSON = REPO / "docs/research/MARKET_04H_PREMIUM_OBSERVABLE_ADJUDICATION.json"

CANDIDATE = "MARKET-05_CROSS_ASSET_CONFIRMATION_ADVERSE_PATH_RISK"
M04_ID = "MARKET-04_FUNDING_STATE_ADVERSE_PATH_RISK"
M04H_ID = "MARKET-04H_PREMIUM_INDEX_ADVERSE_PATH_RISK"
M04_MD_SHA256 = "bab848737137e9a9eebd6ef6565c5b74134d94310ebe20496621aba92a20a936"
M04_JSON_SHA256 = "e1c4270d89d891846fefbe3d14a6389c9d6ed747cb00f8bfc9906300f18d30a6"
M04H_MD_SHA256 = "fa0518941751fb491481e2d9c395005cdf89c106ddedbb7a4d331015472a00bc"
M04H_JSON_SHA256 = "52f1cb939a2e9289fdc061f4243637e243be2196b3c2026132996e7350690c6b"

FORBIDDEN_ARTIFACT_GLOBS = (
    "docs/research/MARKET_05_*RESULT*",
    "docs/research/MARKET_05_*ARM*",
    "docs/research/MARKET_05_*RESERVATION*",
    "scripts/research/market_05*",
)
AUTHORIZED_PREREG_NAMES = {
    "MARKET_05_CROSS_ASSET_PREREG.md",
    "MARKET_05_CROSS_ASSET_PREREG.json",
}
AUTHORIZED_IMPLEMENTATION_FREEZE_NAMES = {
    "MARKET_05_IMPLEMENTATION_FREEZE.md",
    "MARKET_05_IMPLEMENTATION_FREEZE.json",
}

H_B_FORMULATIONS = (
    "H01_COMPRESSION_EXPANSION",
    "H02_FAILED_BREAKOUT_MEAN_REVERSION",
    "H03_EXTREME_IMPULSE",
    "H04_TREND_PULLBACK",
    "H05_TAKER_IMBALANCE",
    "B2-01_VOLATILITY_TRANSITION",
    "B2-02_BOUNDARY_INTERACTION_PATH",
    "B2-03_IMPULSE_MORPHOLOGY",
    "B2-04_MODERATE_PULLBACK_STRUCTURE",
    "B2-05_FLOW_ABSORPTION",
    "B2-06_LEVERAGE_CROWDING",
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
    assert payload["research_id"] == CANDIDATE
    assert payload["short_name"] == "MARKET-05"
    assert payload["mechanism_family"] == "F7_CROSS_ASSET_MARKET_CONTEXT"
    assert payload["primary_role"] == "MARKET_BREADTH_CONFIRMATION_STATE"
    assert payload["not_role"] == "SIMPLE_DIRECTION_PREDICTOR"
    assert payload["simple_direction_predictor"] is False
    assert payload["status"] == "SELECTED_OUTCOME_BLIND_NOT_PREREGISTERED_NOT_AUTHORIZED"
    assert payload["market_05_selected"] is True
    assert "research_id = MARKET-05_CROSS_ASSET_CONFIRMATION_ADVERSE_PATH_RISK" in md
    assert "MECHANISM_FAMILY = F7_CROSS_ASSET_MARKET_CONTEXT" in md
    assert "PRIMARY_ROLE = MARKET_BREADTH_CONFIRMATION_STATE" in md
    assert "NOT_ROLE = SIMPLE_DIRECTION_PREDICTOR" in md
    assert "simple_direction_predictor = false" in md
    assert "market_05_selected = true" in md


def test_btc_target_eth_context_not_independent_replication():
    payload = _load()
    md = _md()
    assert payload["target_market"] == "BTCUSDT"
    assert payload["context_market"] == "ETHUSDT"
    assert payload["target_feature_distinction"]["target"] == "BTCUSDT"
    assert payload["target_feature_distinction"]["context_feature_market"] == "ETHUSDT"
    assert payload["target_feature_distinction"]["eth_is_independent_replication"] is False
    assert payload["target_feature_distinction"]["one_btc_experiment"] is True
    assert "TARGET_MARKET = BTCUSDT" in md
    assert "CONTEXT_MARKET = ETHUSDT" in md
    assert "eth_is_independent_replication = false" in md
    assert "one_btc_experiment = true" in md
    assert "not** an independent asset replication" in md or "not an independent asset replication" in md.lower()
    assert "one BTC experiment" in md


def test_continuous_confirmation_no_optimized_threshold():
    payload = _load()
    md = _md()
    assert payload["context_feature_family"] == "ETH_CONFIRMATION_STATE"
    assert payload["continuous_feature_required"] is True
    assert payload["threshold_search_allowed"] is False
    assert payload["conceptual_feature"]["normalization_formula_frozen"] is False
    forbidden = payload["conceptual_feature"]["forbidden_in_first_formulation"]
    assert "threshold search" in forbidden
    assert "percentile bucket selection" in forbidden
    assert "context_feature_family = ETH_CONFIRMATION_STATE" in md
    assert "continuous_feature_required = true" in md
    assert "threshold_search_allowed = false" in md
    assert "No magic threshold" in md


def test_same_support_and_baseline_candidate_architecture():
    payload = _load()
    md = _md()
    assert payload["same_support_required"] is True
    assert payload["baseline_architecture"]["baseline"] == "BTC-only information available at T"
    assert payload["baseline_architecture"]["candidate"] == (
        "exact BASELINE + continuous ETH_CONFIRMATION_STATE"
    )
    assert payload["baseline_architecture"]["ml_forbidden_in_first_formulation"] is True
    assert payload["baseline_architecture"]["funding_oi_taker_contamination_forbidden"] is True
    assert payload["baseline_architecture"]["large_indicator_library_forbidden"] is True
    assert "BASELINE  = BTC-only information available at T" in md
    assert "CANDIDATE = exact BASELINE + continuous ETH_CONFIRMATION_STATE" in md
    assert "same_support_required = true" in md
    assert "ml_forbidden_in_first_formulation = true" in md
    assert "funding_oi_taker_contamination_forbidden = true" in md
    assert "No ML" in md
    assert "No order-flow" in md or "no order-flow" in md.lower()


def test_primary_outcome_family_not_computed():
    payload = _load()
    md = _md()
    assert payload["primary_outcome_family"] == (
        "FUTURE_BTC_DIRECTION_ALIGNED_ADVERSE_PATH_RISK"
    )
    assert payload["pnl_is_primary_outcome"] is False
    assert payload["final_horizon_return_is_primary"] is False
    assert payload["outcome_family"]["computed_in_this_unit"] is False
    assert "PRIMARY_OUTCOME_FAMILY = FUTURE_BTC_DIRECTION_ALIGNED_ADVERSE_PATH_RISK" in md
    assert "pnl_is_primary_outcome = false" in md
    dumped = json.dumps(payload)
    for needle in (
        "beta_candidate",
        "MAE_mean",
        "market_05_beta",
        "future_return_mean",
        "confirmation_correlation",
        "regression_coefficient",
    ):
        assert needle not in dumped
        assert needle not in md


def test_no_result_arm_or_prereg_created():
    payload = _load()
    assert payload["full_preregistration_frozen"] is False
    assert payload["implementation_frozen"] is False
    assert payload["armed"] is False
    assert payload["execution_authorized"] is False
    assert payload["lifecycle"]["result_created"] is False
    assert payload["lifecycle"]["arm_created"] is False
    assert payload["lifecycle"]["prereg_created"] is False
    matches = []
    for pattern in FORBIDDEN_ARTIFACT_GLOBS:
        matches.extend(REPO.glob(pattern))
    assert matches == []
    prereg_matches = [
        path
        for path in REPO.glob("docs/research/MARKET_05_*PREREG*")
        if path.name not in AUTHORIZED_PREREG_NAMES
    ]
    assert prereg_matches == []
    impl_matches = [
        path
        for path in REPO.glob("docs/research/MARKET_05_*IMPLEMENTATION*")
        if path.name not in AUTHORIZED_IMPLEMENTATION_FREEZE_NAMES
    ]
    assert impl_matches == []
    assert not (REPO / "docs/research/MARKET_05_RESULT.json").exists()
    assert not (REPO / "docs/research/MARKET_05_ARM.json").exists()
    assert "full_preregistration_frozen = false" in _md()
    assert "execution_authorized = false" in _md()


def test_protected_oos_untouched_and_question_exact():
    payload = _load()
    md = _md()
    question = (
        "When BTC has a directional displacement, does contemporaneous ETH "
        "confirmation add stable incremental information about BTC's subsequent "
        "adverse-path risk beyond BTC's own price / path / volatility state?"
    )
    assert payload["scientific_question"] == question
    assert question in md
    assert payload["protected_oos_touched"] is False
    assert payload["scientific_outcomes_inspected"] is False
    assert "protected_oos_touched = false" in md
    assert "scientific_outcomes_inspected = false" in md
    assert "SIGNALBOT_PROTECTED_OOS_UNTOUCHED = YES" in md


def test_lineage_not_rescue_or_replication():
    payload = _load()
    md = _md()
    assert payload["lineage_kind"] == (
        "NEW_MECHANISM_SELECTED_FROM_PROGRAM_LEVEL_INFORMATION_GAP"
    )
    assert payload["parent_scientific_unit"] is None
    assert payload["market_01_02_rescue"] is False
    assert payload["market_03_replication"] is False
    assert payload["market_04_rescue"] is False
    assert payload["posthoc_child_of_h01_h05"] is False
    assert "LINEAGE_KIND = NEW_MECHANISM_SELECTED_FROM_PROGRAM_LEVEL_INFORMATION_GAP" in md
    assert "parent_scientific_unit = null" in md
    assert "market_01_02_rescue = false" in md
    assert "market_03_replication = false" in md
    assert "market_04_rescue = false" in md


def test_market04_remains_blocked_observable_not_scientifically_rejected():
    payload = _load()
    md = _md()
    assert _sha256(M04_MD) == M04_MD_SHA256
    assert _sha256(M04_JSON) == M04_JSON_SHA256
    assert _sha256(M04H_MD) == M04H_MD_SHA256
    assert _sha256(M04H_JSON) == M04H_JSON_SHA256
    m04 = json.loads(M04_JSON.read_text(encoding="utf-8"))
    m04h = json.loads(M04H_JSON.read_text(encoding="utf-8"))
    assert m04["research_id"] == M04_ID
    assert m04h["research_id"] == M04H_ID
    assert m04h["adjudication_outcome"] == "MARKET_04H_PREMIUM_OBSERVABLE_BLOCKED"
    parent = payload["market_04_parent_state"]
    assert parent["status"] == "SELECTED"
    assert parent["tested"] is False
    assert parent["rejected"] is False
    assert parent["blocked_observable"] is True
    assert parent["scientific_failure"] is False
    assert "BLOCKED_OBSERVABLE" in md
    assert "NOT_TESTED" in md
    assert "NOT_REJECTED" in md
    assert "MARKET_04H_PREMIUM_OBSERVABLE_BLOCKED" in md
    assert "scientific failure" in md


def test_earlier_hb_formulations_are_not_renamed_into_m05():
    payload = _load()
    md = _md()
    dumped = json.dumps(payload)
    for name in H_B_FORMULATIONS:
        assert dumped.count(name) == 0
    assert "Earlier H/B exact formulations are not renamed into MARKET-05" in md
    assert payload["research_id"] != "H01_COMPRESSION_EXPANSION"
    assert payload["lineage"]["independent_replication_of_earlier_units"] is False


def test_scientific_question_and_flags_present_in_md():
    md = _md()
    payload = _load()
    assert payload["scientific_question"] in md
    assert "inspect future BTC returns" in md
    assert "inspect future MAE" in md
    assert "execution_authorized = false" in md
    assert payload["next_unit"] == "OUTCOME_BLIND_MARKET_05_EXACT_PREREGISTRATION"
