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
SNAPSHOT_ID = "e0403e40a9b1e2903f15fb9283ec6caf54788e48153038982e364d4318183e68"
DURABLE_ROOT = "f4b9e16a62707c70e782cc318399f3ba53ebb85c792e96cd12c164a98f0cdc6f"


def _payload() -> dict:
    return json.loads(PREREG_JSON.read_text(encoding="utf-8"))


def _md() -> str:
    return PREREG_MD.read_text(encoding="utf-8")


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
    assert "INCREMENTAL_INFORMATION_ONLY" in md or "Incremental-information" in md
    assert p["full_preregistration_frozen"] is False
    assert p["MARKET_06_FREEZE_REQUIRED"] is True


def test_decision_clock_and_feature_cutoff():
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


def test_dislocation_definition_and_8640_refs():
    p = _payload()
    d = p["dislocation"]
    assert d["D_u"] == "ln(perp_close(u) / spot_close(u))"
    assert d["D_e"] == "D(FEATURE_CUTOFF)"
    assert d["reference_count"] == 8640
    assert d["reference_excludes_D_e"] is True
    assert d["PRIMARY_FEATURE"] == "ABS_DISLOCATION_Z"
    assert d["ABS_DISLOCATION_Z"] == "abs(Z_e)"
    assert d["Z_e"] == "(D_e - MED_e) / MAD_e"
    assert d["MAD_le_0"] == "ROW_NOT_ELIGIBLE"
    assert d["mad_consistency_constant_1_4826"] is False
    assert d["threshold_search_allowed"] is False
    assert p["btc_own_state"]["BTC_RET_24H_eq_0"] == "ROW_NOT_ELIGIBLE"
    assert p["btc_own_state"]["exact_zero_exclusion_only"] is True


def test_outcome_mae_288_bars_entry_open_at_T():
    p = _payload()
    y = p["primary_outcome"]
    assert y["name"] == "24H_DIRECTION_ALIGNED_BTC_MAE"
    assert y["future_bars"] == 288
    assert y["ENTRY"] == "open of the Binance perp 5m bar with open_time = T"
    assert y["horizon"] == "24 hours"
    assert y["final_return_substitution"] is False
    assert y["mfe_pnl_substitution"] is False
    assert "Y = max(0, ln(ENTRY / min_low_of_288))" in y["BTC_SIDE_plus"]
    assert "Y = max(0, ln(max_high_of_288 / ENTRY))" in y["BTC_SIDE_minus"]


def test_ols_baseline_versus_candidate_plus_abs_dislocation_z():
    p = _payload()
    assert p["baseline_model"] == "Y ~ BTC_SIDE + ABS_Z_BTC + RV_BTC_24H"
    assert (
        p["candidate_model"]
        == "Y ~ BTC_SIDE + ABS_Z_BTC + RV_BTC_24H + ABS_DISLOCATION_Z"
    )
    assert p["candidate_adds_only"] == "ABS_DISLOCATION_Z"
    assert p["baseline_regressors"] == [
        "INTERCEPT",
        "BTC_SIDE",
        "ABS_Z_BTC",
        "RV_BTC_24H",
    ]
    assert p["model_class"] == "ORDINARY_LEAST_SQUARES_LINEAR_REGRESSION"
    assert p["solver"]["method"] == "numpy.linalg.solve"
    assert p["interaction_terms"] is False
    assert p["signed_D_e_as_candidate_regressor"] is False
    assert p["ml_forbidden"] is True
    assert p["splits"]["refit_on_holdout"] is False


def test_train_holdout_calendar_no_dec_31_no_refit():
    p = _payload()
    s = p["splits"]
    assert s["TRAIN_START_T"] == "2022-02-01T00:05:00Z"
    assert s["TRAIN_END_T"] == "2022-12-30T00:05:00Z"
    assert s["HOLDOUT_2023_START_T"] == "2023-01-01T00:05:00Z"
    assert s["HOLDOUT_2023_END_T"] == "2023-12-30T00:05:00Z"
    assert s["HOLDOUT_2024_START_T"] == "2024-01-01T00:05:00Z"
    assert s["HOLDOUT_2024_END_T"] == "2024-12-30T00:05:00Z"
    assert s["december_31_decision_forbidden"] is True
    assert s["refit_on_holdout"] is False
    assert s["expanding_window"] is False
    assert s["year_2022_never_heldout_evidence"] is True
    assert p["standardization"]["learned_from"] == "eligible TRAIN rows only"
    assert p["standardization"]["refit_on_holdout"] is False


def test_six_gates_g5_materiality_and_classifications():
    p = _payload()
    g = p["gates"]
    assert p["gate_count"] == 6
    assert set(g) == {
        "GATE_1_DIRECTION",
        "GATE_2_DIRECTION_UNCERTAINTY",
        "GATE_3_PREDICTIVE_SIGN",
        "GATE_4_PREDICTIVE_UNCERTAINTY",
        "GATE_5_MATERIALITY",
        "GATE_6_TEMPORAL_STABILITY",
    }
    assert g["GATE_5_MATERIALITY"] == "RELATIVE_MAE_IMPROVEMENT >= 0.02"
    assert p["materiality_threshold"] == 0.02
    assert p["relative_mae_improvement"] == (
        "1 - (POOLED_MAE_CANDIDATE / POOLED_MAE_BASELINE)"
    )
    assert p["expected_beta_sign"] == "positive"
    assert p["beta_gate"] == "BETA_ABS_DISLOCATION_Z > 0"
    assert p["promotion_classification"] == "MARKET_06_PROMOTED_HISTORICAL_CANDIDATE"
    assert p["fail_classification"] == "MARKET_06_NO_EVIDENCE"
    assert p["integrity_fail_classification"] == "MARKET_06_INCOMPLETE_EXECUTION"
    assert "NEAR_PASS" in p["forbidden_promotion_states"]


def test_circular_mbb_identity():
    p = _payload()
    b = p["bootstrap"]
    assert b["kind"] == "CIRCULAR_MOVING_BLOCK"
    assert b["block_length"] == 14
    assert b["replicates"] == 5000
    assert b["random_seed"] == 2026092106
    assert b["predictive_refit"] is False
    assert b["rng"] == "numpy.random.Generator(numpy.random.PCG64(2026092106))"
    assert b["python_hash"] is False
    assert b["reroll"] is False


def test_bound_dataset_snapshot_and_durable_root_match_frozen_identity():
    p = _payload()
    hashes = json.loads(HASHES.read_text(encoding="utf-8"))
    retention = json.loads(RETENTION.read_text(encoding="utf-8"))
    assert p["data"]["dataset_id"] == "MARKET_06_OKX_BINANCE_FEASIBILITY_V0"
    assert p["data"]["snapshot_id"] == SNAPSHOT_ID
    assert hashes["snapshot_id"] == SNAPSHOT_ID
    assert p["data"]["durable_evidence_root_sha256"] == DURABLE_ROOT
    assert retention["durable_evidence_root_sha256"] == DURABLE_ROOT
    assert p["data"]["identity_file_sha256"] == {
        "binance_object_ledger.json": hashes["binance_object_ledger.json"]["sha256"],
        "okx_page_manifest.json": hashes["okx_page_manifest.json"]["sha256"],
        "timestamp_census.json": hashes["timestamp_census.json"]["sha256"],
        "snapshot.json": hashes["snapshot.json"]["sha256"],
    }
    assert p["pre_prereg_head"] == PRE_PREREG_HEAD
    assert p["pre_prereg_tree"] == PRE_PREREG_TREE
    assert p["data"]["spot_leg"]["binance_spot_adopted"] is False
    assert p["data"]["spot_leg"]["bybit_spot_adopted"] is False
    assert p["data"]["perp_leg"]["price_basis"] == "TRADE_PRICE"


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
    assert b["b2_06_execution_authorized"] is False
    assert p["scientific_outcomes_inspected"] is False
    assert p["eligibility"]["eligible_row_counts_computed_in_this_unit"] is False
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
