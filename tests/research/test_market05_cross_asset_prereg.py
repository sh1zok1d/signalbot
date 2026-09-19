"""MARKET-05 exact outcome-blind preregistration checks.

Does not execute the experiment, inspect scientific outcomes, or
authorize ARM/RESULT.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MD = REPO / "docs/research/MARKET_05_CROSS_ASSET_PREREG.md"
JSON_PATH = REPO / "docs/research/MARKET_05_CROSS_ASSET_PREREG.json"
CAND_MD = REPO / "docs/research/MARKET_05_CROSS_ASSET_CANDIDATE.md"
CAND_JSON = REPO / "docs/research/MARKET_05_CROSS_ASSET_CANDIDATE.json"
FEAS_MD = REPO / "docs/research/MARKET_05_CROSS_ASSET_DATA_FEASIBILITY.md"
FEAS_JSON = REPO / "docs/research/MARKET_05_CROSS_ASSET_DATA_FEASIBILITY.json"

RESEARCH_ID = "MARKET-05_CROSS_ASSET_CONFIRMATION_ADVERSE_PATH_RISK"
CAND_MD_SHA256 = "f5017796af3e98abe15c87b6a15df9f51db2d649eba82300da8c60ac837f5958"
CAND_JSON_SHA256 = "e601069214284f30700b5c3f3b9391c3f4382762a5b08153a695bb68f09a81bb"
FEAS_MD_SHA256 = "fa09bdaaa4562da94cee4035f30033325b766934934f0093a39e96bc46f02aeb"
FEAS_JSON_SHA256 = "40092057179bdd3d1b78ebf0a01812f42be31bba4e2e2e4b2e90819594eb9a2c"

PRIMARY_CLAIM = (
    "Conditional on BTC's own recent directional displacement and volatility "
    "state, stronger contemporaneous ETH confirmation of BTC's direction predicts "
    "LOWER subsequent BTC adverse excursion against that direction."
)

# Explicitly authorized outcome-blind artifacts that are NOT a real ARM,
# RESULT or RESERVATION. A real MARKET_05_ARM.json / MARKET_05_RESULT.json /
# MARKET_05_RESERVATION.json remains forbidden by the globs below.
AUTHORIZED_NON_ARM_ARTIFACT_NAMES = {
    "MARKET_05_ARM_CONTRACT.md",
    "MARKET_05_ARM_CONTRACT.json",
    "MARKET_05_IMPLEMENTATION_REFREEZE.md",
    "MARKET_05_IMPLEMENTATION_REFREEZE.json",
}

FORBIDDEN_ARTIFACT_GLOBS = (
    "docs/research/MARKET_05_*RESULT*",
    "docs/research/MARKET_05_*ARM*",
    "docs/research/MARKET_05_*RESERVATION*",
    "scripts/research/market_05*",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load() -> dict:
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


def _md() -> str:
    return MD.read_text(encoding="utf-8")


def test_bound_candidate_and_feasibility_not_rewritten():
    payload = _load()
    assert _sha256(CAND_MD) == CAND_MD_SHA256
    assert _sha256(CAND_JSON) == CAND_JSON_SHA256
    assert _sha256(FEAS_MD) == FEAS_MD_SHA256
    assert _sha256(FEAS_JSON) == FEAS_JSON_SHA256
    assert payload["bound_candidate"]["md_sha256"] == CAND_MD_SHA256
    assert payload["bound_feasibility"]["json_sha256"] == FEAS_JSON_SHA256
    cand = json.loads(CAND_JSON.read_text(encoding="utf-8"))
    assert cand["research_id"] == RESEARCH_ID
    assert cand["full_preregistration_frozen"] is False


def test_identity_claim_and_development_window():
    payload = _load()
    md = _md()
    assert payload["research_id"] == RESEARCH_ID
    assert payload["primary_claim"] == PRIMARY_CLAIM
    assert PRIMARY_CLAIM in md
    assert payload["development_window"] == "[2020-01-01T00:00:00Z, 2025-01-01T00:00:00Z)"
    assert payload["protected_oos"] == "[2025-01-01T00:00:00Z, onward)"
    assert payload["development_window"].endswith("2025-01-01T00:00:00Z)")
    assert "SCIENTIFIC_DEVELOPMENT_WINDOW = [2020-01-01T00:00:00Z, 2025-01-01T00:00:00Z)" in md
    assert "PROTECTED_OOS = [2025-01-01T00:00:00Z, onward)" in md


def test_daily_midnight_utc_and_24h_windows():
    payload = _load()
    md = _md()
    assert payload["decision_grid"]["decision_time"] == "00:00:00 UTC"
    assert payload["decision_grid"]["decision_frequency"] == "DAILY"
    assert payload["decision_grid"]["intraday_decision_grid"] is False
    assert payload["feature_lookback"] == "24 hours"
    assert payload["outcome_horizon"] == "24 hours"
    assert payload["price_convention"]["future_outcome_window"] == "[T, T+24h)"
    assert payload["price_convention"]["no_bar_beginning_at_T_in_features"] is True
    assert payload["data"]["bar_availability"] == "bar_end_exclusive"
    assert "DECISION_TIME = 00:00:00 UTC" in md
    assert "DECISION_FREQUENCY = DAILY" in md
    assert "FEATURE_LOOKBACK = 24 hours" in md
    assert "OUTCOME_HORIZON = 24 hours" in md
    assert "future outcome uses [T, T+24h)" in md
    assert "BAR_AVAILABILITY = bar_end_exclusive" in md
    assert "FIRST_USABLE_DECISION_TIME = 2020-01-03T00:00:00Z" in md
    assert "LAST_USABLE_DECISION_TIME = 2024-12-31T00:00:00Z" in md


def test_exact_zero_exclusion_and_continuous_confirmation():
    payload = _load()
    md = _md()
    assert payload["btc_displacement"]["exact_zero_exclusion_only"] is True
    assert payload["btc_displacement"]["epsilon_threshold_permitted"] is False
    assert payload["btc_displacement"]["minimum_move_threshold_permitted"] is False
    assert payload["eth_confirmation"]["formula"] == "BTC_SIDE * Z_ETH"
    assert payload["eth_confirmation"]["continuous_feature_required"] is True
    assert payload["eth_confirmation"]["threshold_search_allowed"] is False
    assert payload["eth_confirmation"]["bucket_defines_primary_test"] is False
    assert "Exact-zero BTC displacement exclusion only" in md
    assert "ETH_CONFIRMATION = BTC_SIDE * Z_ETH" in md
    assert "continuous_feature_required = true" in md
    assert "threshold_search_allowed = false" in md
    assert "No threshold or bucket defines the primary test" in md


def test_exact_baseline_and_candidate():
    payload = _load()
    md = _md()
    assert payload["baseline_model"] == "Y ~ BTC_SIDE + ABS_Z_BTC + RV_BTC_24H"
    assert payload["candidate_model"] == (
        "Y ~ BTC_SIDE + ABS_Z_BTC + RV_BTC_24H + ETH_CONFIRMATION"
    )
    assert payload["baseline_regressors"] == [
        "INTERCEPT",
        "BTC_SIDE",
        "ABS_Z_BTC",
        "RV_BTC_24H",
    ]
    assert payload["candidate_adds_only"] == "ETH_CONFIRMATION"
    assert payload["interaction_terms"] is False
    assert payload["polynomial_terms"] is False
    assert payload["funding_oi_taker_contamination"] is False
    assert payload["ml_forbidden"] is True
    assert "BASELINE_MODEL = Y ~ BTC_SIDE + ABS_Z_BTC + RV_BTC_24H" in md
    assert "CANDIDATE_MODEL = Y ~ BTC_SIDE + ABS_Z_BTC + RV_BTC_24H + ETH_CONFIRMATION" in md
    assert "No interaction terms" in md
    assert "No funding" in md
    assert "No ML" in md


def test_chronological_folds_2022_2023_2024():
    payload = _load()
    md = _md()
    folds = payload["folds"]
    assert folds["heldout_years"] == [2022, 2023, 2024]
    assert folds["FOLD_1"]["test_year"] == 2022
    assert folds["FOLD_2"]["test_year"] == 2023
    assert folds["FOLD_3"]["test_year"] == 2024
    assert folds["FOLD_1"]["test"] == "[2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z)"
    assert folds["FOLD_2"]["test"] == "[2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z)"
    assert folds["FOLD_3"]["test"] == "[2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z)"
    assert folds["random_split"] is False
    assert "FOLD_1_TEST  = [2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z)" in md
    assert "FOLD_2_TEST  = [2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z)" in md
    assert "FOLD_3_TEST  = [2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z)" in md
    assert "calendar year 2022" in md
    assert "calendar year 2023" in md
    assert "calendar year 2024" in md


def test_materiality_beta_bootstrap_and_stability():
    payload = _load()
    md = _md()
    assert payload["materiality_threshold"] == 0.02
    assert payload["expected_beta_sign"] == "negative"
    assert payload["beta_gate"] == "BETA_ETH_CONFIRMATION < 0"
    assert payload["bootstrap"]["block_length"] == 14
    assert payload["bootstrap"]["replicates"] == 5000
    assert payload["bootstrap"]["random_seed"] == 2026091905
    assert payload["bootstrap"]["predictive_refit"] is False
    assert payload["gates"]["GATE_5_MATERIALITY"] == "RELATIVE_MAE_IMPROVEMENT >= 0.02"
    assert "at least 2 of 3" in payload["gates"]["TEMPORAL_STABILITY_GATE"]
    assert "YEAR_RELATIVE_MAE_IMPROVEMENT <= -0.02" in payload["gates"]["TEMPORAL_STABILITY_GATE"]
    assert "MATERIAL_RELATIVE_MAE_IMPROVEMENT = 0.02" in md
    assert "EXPECTED_BETA_SIGN = negative" in md
    assert "BETA_ETH_CONFIRMATION < 0" in md
    assert "BLOCK_LENGTH = 14 consecutive days" in md
    assert "BOOTSTRAP_REPLICATES = 5000" in md
    assert "RANDOM_SEED = 2026091905" in md
    assert "at least 2 of 3 test years" in md
    assert "YEAR_RELATIVE_MAE_IMPROVEMENT <= -0.02" in md


def test_classification_and_calibration():
    payload = _load()
    md = _md()
    assert payload["promotion_classification"] == "MARKET_05_PROMOTED_HISTORICAL_CANDIDATE"
    assert payload["fail_classification"] == "MARKET_05_NO_EVIDENCE"
    assert payload["integrity_fail_classification"] == "MARKET_05_INCOMPLETE_EXECUTION"
    assert payload["MARKET_05_TEST_CALIBRATED"] == "NO"
    assert payload["parameter_robustness_grid"] is False
    for name in ("NEAR_PASS", "MIXED", "PROMISING", "PARTIAL_PASS"):
        assert name in payload["forbidden_promotion_states"]
        assert name in md
    assert "MARKET_05_TEST_CALIBRATED = NO" in md
    assert "PROMOTION_CLASSIFICATION = MARKET_05_PROMOTED_HISTORICAL_CANDIDATE" in md
    assert "FAIL_CLASSIFICATION = MARKET_05_NO_EVIDENCE" in md


def test_no_arm_result_evaluator_and_oos_untouched():
    payload = _load()
    md = _md()
    dumped = json.dumps(payload)
    assert payload["full_preregistration_frozen"] is True
    assert payload["implementation_frozen"] is False
    assert payload["armed"] is False
    assert payload["execution_authorized"] is False
    assert payload["scientific_outcomes_inspected"] is False
    assert payload["protected_oos_touched"] is False
    assert payload["lifecycle"]["result_created"] is False
    assert payload["lifecycle"]["arm_created"] is False
    assert payload["lifecycle"]["evaluator_implemented"] is False
    assert payload["next_unit"] == "OUTCOME_BLIND_MARKET_05_IMPLEMENTATION"
    assert "FULL_PREREGISTRATION_FROZEN = true" in md
    assert "ARMED = false" in md
    assert "EXECUTION_AUTHORIZED = false" in md
    assert "SCIENTIFIC_OUTCOMES_INSPECTED = false" in md
    assert "PROTECTED_OOS_TOUCHED = false" in md
    assert "SIGNALBOT_PROTECTED_OOS_UNTOUCHED = YES" in md
    matches = []
    for pattern in FORBIDDEN_ARTIFACT_GLOBS:
        matches.extend(
            path
            for path in REPO.glob(pattern)
            if path.name not in AUTHORIZED_NON_ARM_ARTIFACT_NAMES
        )
    assert matches == []
    # The real ARM/RESULT/RESERVATION artifacts must still be absent.
    for forbidden in (
        "docs/research/MARKET_05_ARM.json",
        "docs/research/MARKET_05_ARM.md",
        "docs/research/MARKET_05_RESERVATION.json",
        "docs/research/MARKET_05_RESULT.json",
        "docs/research/MARKET_05_RESULT.md",
    ):
        assert not (REPO / forbidden).exists(), forbidden
    assert not (REPO / "docs/research/MARKET_05_RESULT.json").exists()
    assert not (REPO / "docs/research/MARKET_05_ARM.json").exists()
    for needle in (
        "beta_candidate",
        "MAE_mean",
        "POOLED_MAE_CANDIDATE_VALUE",
        "confirmation_correlation",
        "market_05_beta_hat",
    ):
        assert needle not in dumped
        assert needle not in md
    assert "calculate future MAE" in md
    assert "calculate future BTC returns for hypothesis evaluation" in md
