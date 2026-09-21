"""Outcome-blind MARKET-06 preregistration contract checks.

Does not inspect OHLC, dislocation values, eligible-row counts from
price data, future returns, MAE, or betas. Does not implement a runner,
ARM, or RESULT.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
PREREG_MD = REPO / "docs" / "research" / "MARKET_06_CROSS_VENUE_DISLOCATION_PREREG.md"
PREREG_JSON = REPO / "docs" / "research" / "MARKET_06_CROSS_VENUE_DISLOCATION_PREREG.json"
V0_MD = REPO / "docs" / "research" / "MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_V0.md"
V0_JSON = REPO / "docs" / "research" / "MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_V0.json"
HASHES = (
    REPO
    / "docs"
    / "research_data"
    / "MARKET_06_OKX_BINANCE_FEASIBILITY_V0"
    / "HASHES.json"
)
RETENTION = (
    REPO / "docs" / "research" / "MARKET_06_OKX_BINANCE_FEASIBILITY_V0_DURABLE_RETENTION.json"
)

PRE_PREREG_HEAD = "a75a5272f994f9728308c47c524f2839b73762a7"
PRE_PREREG_TREE = "7272614b7a2799aaf82a80f5d7c9cb1207af01ac"
OLD_PREREG_CONTENT_HEAD = "b21bf46dcc39a2b9243c4172f731cd4d3fbf79b1"
OLD_FREEZE_HEAD = "5f14411abc926a2b486d83de5b696ec3cf362488"
OLD_MD_SHA256 = "0489fc71e999b48a7a82223615bd0acd50b1f69af8bc9901d1c681834e55cfcc"
OLD_JSON_SHA256 = "332d91140c7ead87f4539b49c8a5647064f9c5e1d0bb8178c16dcc7eaf7a88f4"
SNAPSHOT_ID = "e0403e40a9b1e2903f15fb9283ec6caf54788e48153038982e364d4318183e68"
DURABLE_ROOT = "f4b9e16a62707c70e782cc318399f3ba53ebb85c792e96cd12c164a98f0cdc6f"


def _payload() -> dict:
    return json.loads(PREREG_JSON.read_text(encoding="utf-8"))


def _md() -> str:
    return PREREG_MD.read_text(encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_research_identity_and_incremental_claim():
    p = _payload()
    md = _md()
    assert p["research_id"] == "MARKET-06_CROSS_VENUE_DISLOCATION_ADVERSE_PATH_RISK"
    assert p["unit_id"] == "MARKET_06_CROSS_VENUE_DISLOCATION_PREREG"
    assert p["status"] == "PREREGISTERED_OUTCOME_BLIND_UNFROZEN"
    assert p["claim_type"] == "INCREMENTAL_INFORMATION_ONLY"
    assert p["simple_direction_predictor"] is False
    assert p["market_01_rescue"] is False
    assert p["market_05_rescue"] is False
    assert "incremental information" in p["primary_claim"]
    assert p["full_preregistration_frozen"] is False
    assert p["MARKET_06_FREEZE_REQUIRED"] is True
    assert p["amendment_of"]["amendment_id"] == (
        "MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_AMENDMENT_002"
    )
    assert p["amendment_of"]["old_live_prereg_head"] == (
        "b4459ab96addd6c39d4baec35248410a8f5cf8e0"
    )
    assert p["amendment_of"]["old_live_freeze_head"] == (
        "371f71dd49e2c2c445269aeed1b75a39f33b3422"
    )
    assert p["amendment_of"]["previous_amendment_id"] == (
        "MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_AMENDMENT_001"
    )
    assert p["amendment_of"]["old_prereg_content_head"] == OLD_PREREG_CONTENT_HEAD
    assert p["amendment_of"]["old_freeze_head"] == OLD_FREEZE_HEAD
    assert p["amendment_of"]["outcomes_inspected_before_amendment"] is False
    assert p["amendment_of"]["amendment_reason"] == (
        "PRE_OUTCOME_PREDICTIVE_BOOTSTRAP_STRATIFICATION_CORRECTION"
    )
    assert "amendment 002" in md


def test_decision_clock_and_feature_cutoff_unchanged():
    p = _payload()
    grid = p["decision_grid"]
    assert grid["decision_frequency"] == "DAILY"
    assert grid["decision_time_T"] == "00:05:00 UTC"
    assert grid["feature_cutoff"] == "T - 5 minutes"
    assert grid["feature_cutoff_clock"] == "00:00:00 UTC"
    assert grid["intraday_decision_grid"] is False
    md = _md()
    assert "FEATURE_CUTOFF     = T - 5 minutes" in md
    assert "00:05:00 UTC" in md


def test_f1_mad_uses_1_4826_robust_scale_not_raw_mad():
    p = _payload()
    d = p["dislocation"]
    md = _md()
    assert d["mad_consistency_constant_1_4826"] is True
    assert d["MAD_CONSISTENCY_CONSTANT"] == 1.4826
    assert d["MAD_CONSISTENCY_CONSTANT_ENABLED"] is True
    assert d["raw_mad_as_denominator"] is False
    assert d["ROBUST_SCALE_T"] == "1.4826 * MAD_T"
    assert d["Z_denominator"] == "1.4826 * MAD_T"
    assert d["DISLOCATION_Z_T"] == "(D_E - CENTER_T) / ROBUST_SCALE_T"
    assert d["ABS_DISLOCATION_Z"] == "abs(DISLOCATION_Z_T)"
    assert d["PRIMARY_FEATURE"] == "ABS_DISLOCATION_Z"
    assert d["reference_count"] == 8640
    assert d["reference_excludes_D_e"] is True
    assert d["MAD_le_0"] == "ROW_NOT_ELIGIBLE"
    assert "/ MAD_e" not in d["DISLOCATION_Z_T"]
    assert "/ MAD_T)" not in d["DISLOCATION_Z_T"] or "1.4826 * MAD_T" in d["Z_denominator"]
    assert "1.4826 * MAD_T" in md
    assert "Do **not** use raw `MAD_T` as the z-score denominator" in md
    blob = json.dumps(d)
    assert "1.4826 * MAD_T" in blob


def test_f2_abs_btc_ret_control_not_abs_z_btc():
    p = _payload()
    md = _md()
    assert p["baseline_model"] == "Y ~ 1 + BTC_SIDE + ABS_BTC_RET_24H + RV_BTC_24H"
    assert p["candidate_model"] == (
        "Y ~ 1 + BTC_SIDE + ABS_BTC_RET_24H + RV_BTC_24H + ABS_DISLOCATION_Z"
    )
    assert p["baseline_regressors"] == [
        "INTERCEPT",
        "BTC_SIDE",
        "ABS_BTC_RET_24H",
        "RV_BTC_24H",
    ]
    assert "ABS_Z_BTC" not in p["baseline_regressors"]
    assert "ABS_BTC_RET_24H" in p["baseline_regressors"]
    assert p["btc_own_state"]["ABS_BTC_RET_24H"] == "abs(BTC_RET_24H)"
    assert p["btc_own_state"]["ABS_Z_BTC_regressor"] is False
    assert "ABS_Z_BTC" not in p["baseline_model"]
    assert "ABS_Z_BTC" not in p["candidate_model"]
    assert "ABS_BTC_RET_24H" in p["baseline_model"]
    assert p["standardization"]["continuous_features"] == [
        "ABS_BTC_RET_24H",
        "RV_BTC_24H",
        "ABS_DISLOCATION_Z",
    ]
    assert "ABS_Z_BTC" not in p["standardization"]["continuous_features"]
    assert "Y ~ 1 + BTC_SIDE + ABS_BTC_RET_24H + RV_BTC_24H" in md
    assert "`ABS_Z_BTC` is **not** a scientific control" in md


def test_f3_arithmetic_fractional_mae_not_logarithmic():
    p = _payload()
    y = p["primary_outcome"]
    md = _md()
    assert y["name"] == "24H_DIRECTION_ALIGNED_BTC_MAE"
    assert y["future_bars"] == 288
    assert y["scale"] == "ARITHMETIC_FRACTIONAL_EXCURSION"
    assert y["logarithmic_adverse_excursion"] is False
    assert y["ENTRY_PRICE"] == (
        "open of the Binance perpetual 5m bar with bar_start == T"
    )
    assert y["BTC_SIDE_plus"] == (
        "Y_T = max(0, (ENTRY_PRICE - min(FUTURE_LOW)) / ENTRY_PRICE)"
    )
    assert y["BTC_SIDE_minus"] == (
        "Y_T = max(0, (max(FUTURE_HIGH) - ENTRY_PRICE) / ENTRY_PRICE)"
    )
    assert "ln(ENTRY / min_low" not in y["BTC_SIDE_plus"]
    assert "ln(max_high / ENTRY)" not in y["BTC_SIDE_minus"]
    assert "Y_T = max(0, (ENTRY_PRICE - min(FUTURE_LOW)) / ENTRY_PRICE)" in md
    assert "Y = max(0, ln(ENTRY / ADVERSE_PRICE))" not in md
    assert "Y = max(0, ln(ADVERSE_PRICE / ENTRY))" not in md


def test_f4_gate2_uses_lower_ci_bound_not_upper():
    p = _payload()
    g = p["gates"]
    md = _md()
    assert g["GATE_2_DIRECTION_UNCERTAINTY"] == (
        "95% block-bootstrap lower confidence bound for BETA_ABS_DISLOCATION_Z > 0"
    )
    assert "upper" not in g["GATE_2_DIRECTION_UNCERTAINTY"].lower()
    assert p["gate_2_exact_predicate"] == "BETA_ABS_DISLOCATION_Z_CI95_LOW > 0"
    assert p["gate_2_exact_predicate"] != "BETA_ABS_DISLOCATION_Z_CI95_HIGH > 0"
    assert "GATE_2_EXACT_PREDICATE        = BETA_ABS_DISLOCATION_Z_CI95_LOW > 0" in md
    assert "upper confidence bound for BETA_ABS_DISLOCATION_Z" not in md


def test_ols_and_frozen_constants_otherwise_unchanged():
    p = _payload()
    assert p["candidate_adds_only"] == "ABS_DISLOCATION_Z"
    assert p["model_class"] == "ORDINARY_LEAST_SQUARES_LINEAR_REGRESSION"
    assert p["solver"]["method"] == "numpy.linalg.solve"
    assert p["interaction_terms"] is False
    assert p["ml_forbidden"] is True
    assert p["splits"]["refit_on_holdout"] is False
    assert p["splits"]["TRAIN_START_T"] == "2022-02-01T00:05:00Z"
    assert p["splits"]["TRAIN_END_T"] == "2022-12-30T00:05:00Z"
    assert p["splits"]["HOLDOUT_2023_START_T"] == "2023-01-01T00:05:00Z"
    assert p["splits"]["HOLDOUT_2023_END_T"] == "2023-12-30T00:05:00Z"
    assert p["splits"]["HOLDOUT_2024_START_T"] == "2024-01-01T00:05:00Z"
    assert p["splits"]["HOLDOUT_2024_END_T"] == "2024-12-30T00:05:00Z"
    assert p["splits"]["december_31_decision_forbidden"] is True
    assert p["materiality_threshold"] == 0.02
    assert p["gates"]["GATE_5_MATERIALITY"] == "RELATIVE_MAE_IMPROVEMENT >= 0.02"
    assert p["gate_count"] == 6
    assert p["expected_beta_sign"] == "positive"
    b = p["bootstrap"]
    assert b["kind"] == "CIRCULAR_MOVING_BLOCK"
    assert b["block_length"] == 14
    assert b["replicates"] == 5000
    assert b["random_seed"] == 2026092106
    assert b["PREDICTIVE_BOOTSTRAP_STRATIFIED_BY_YEAR"] is True
    assert b["CROSS_YEAR_BOOTSTRAP_BLOCKS_ALLOWED"] is False
    assert b["YEAR_SAMPLE_SIZE_PRESERVED_PER_REPLICATE"] is True
    assert b["PREDICTIVE_MODEL_REFIT_IN_BOOTSTRAP"] is False
    assert b["predictive_refit"] is False
    assert b["predictive_concatenated_sequence_before_sampling"] is False
    assert b["PREDICTIVE_BOOTSTRAP_2023_N"] == "original eligible N_2023"
    assert b["PREDICTIVE_BOOTSTRAP_2024_N"] == "original eligible N_2024"
    assert p["protected_oos"] == "[2025-01-01T00:00:00Z, onward)"
    assert p["boundaries"]["protected_oos_authorized"] is False
    md = _md()
    assert "concatenated 2023+2024 holdout sequence" not in md
    assert "PREDICTIVE_BOOTSTRAP_STRATIFIED_BY_YEAR = true" in md
    assert "CROSS_YEAR_BOOTSTRAP_BLOCKS_ALLOWED = false" in md


def test_bound_dataset_snapshot_and_durable_root_unchanged():
    p = _payload()
    hashes = json.loads(HASHES.read_text(encoding="utf-8"))
    retention = json.loads(RETENTION.read_text(encoding="utf-8"))
    assert p["data"]["dataset_id"] == "MARKET_06_OKX_BINANCE_FEASIBILITY_V0"
    assert p["data"]["snapshot_id"] == SNAPSHOT_ID
    assert hashes["snapshot_id"] == SNAPSHOT_ID
    assert p["data"]["durable_evidence_root_sha256"] == DURABLE_ROOT
    assert retention["durable_evidence_root_sha256"] == DURABLE_ROOT
    assert p["pre_prereg_head"] == PRE_PREREG_HEAD
    assert p["pre_prereg_tree"] == PRE_PREREG_TREE
    assert p["data"]["spot_leg"]["binance_spot_adopted"] is False
    assert p["data"]["perp_leg"]["price_basis"] == "TRADE_PRICE"


def test_v0_historical_bytes_preserved_exact():
    assert _sha256(V0_MD) == OLD_MD_SHA256
    assert _sha256(V0_JSON) == OLD_JSON_SHA256
    v0 = json.loads(V0_JSON.read_text(encoding="utf-8"))
    assert v0["dislocation"]["mad_consistency_constant_1_4826"] is False
    assert "ABS_Z_BTC" in v0["baseline_regressors"]
    assert "ln(ENTRY / min_low_of_288)" in v0["primary_outcome"]["BTC_SIDE_plus"]
    assert "upper" in v0["gates"]["GATE_2_DIRECTION_UNCERTAINTY"]


def test_no_execution_arm_result_or_outcome_inspection():
    p = _payload()
    b = p["boundaries"]
    assert b["prereg_frozen"] is False
    assert b["arm_authorized"] is False
    assert b["market_06_execution_authorized"] is False
    assert b["evaluator_implemented"] is False
    assert b["result_created"] is False
    assert b["arm_created"] is False
    assert b["outcome_inspection_authorized"] is False
    assert b["protected_oos_authorized"] is False
    assert b["default_v4"] is False
    assert p["scientific_outcomes_inspected"] is False
    research = REPO / "docs" / "research"
    for name in (
        "MARKET_06_ARM.md",
        "MARKET_06_ARM.json",
        "MARKET_06_RESULT.md",
        "MARKET_06_RESULT.json",
        "MARKET_06.md",
    ):
        assert not (research / name).exists()
    scripts = REPO / "scripts" / "research"
    assert not (scripts / "market_06_cross_venue_dislocation_runner.py").exists()
    assert not (scripts / "market_06_evaluator.py").exists()


def test_payload_contains_no_empirical_outcome_numbers():
    p = _payload()
    forbidden_keys = {
        "eligible_n",
        "n_train",
        "n_holdout",
        "mae_baseline",
        "mae_candidate",
        "beta_hat",
        "pooled_mae",
        "year_relative_mae_improvement",
    }
    assert forbidden_keys.isdisjoint(p.keys())
    blob = json.dumps(p)
    assert "eligible_n" not in blob
    md = _md()
    assert "Do not compute eligible-row counts in this unit." in md
    sha = hashlib.sha256(PREREG_JSON.read_bytes()).hexdigest()
    assert len(sha) == 64
