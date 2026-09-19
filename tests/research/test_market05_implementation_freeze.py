"""MARKET-05 implementation-freeze identity checks.

Does not execute scientific MARKET-05 or inspect real outcomes.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MD = REPO / "docs/research/MARKET_05_IMPLEMENTATION_FREEZE.md"
JSON_PATH = REPO / "docs/research/MARKET_05_IMPLEMENTATION_FREEZE.json"
PREREG_MD = REPO / "docs/research/MARKET_05_CROSS_ASSET_PREREG.md"
PREREG_JSON = REPO / "docs/research/MARKET_05_CROSS_ASSET_PREREG.json"

PREREG_MD_SHA256 = "31349f8863be3a79604d0c8dc93ca7037451ab16edb83a432d31af81f8a0193e"
PREREG_JSON_SHA256 = "f2b2f6b98a3674412b584e6bd2686efa8fb9ce08b5d936e503e5d570a2428b25"
ETH_SNAPSHOT = "4b9c113f659e1c1ca71498096dfdc2628a1016346aed40e19020efb64c85ad15"
BTC_SNAPSHOT = "717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_freeze_flags_and_prereg_binding():
    payload = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    md = MD.read_text(encoding="utf-8")
    assert payload["research_id"] == "MARKET-05_CROSS_ASSET_CONFIRMATION_ADVERSE_PATH_RISK"
    assert payload["full_preregistration_frozen"] is True
    assert payload["implementation_frozen"] is True
    assert payload["armed"] is False
    assert payload["execution_authorized"] is False
    assert payload["scientific_outcomes_inspected"] is False
    assert payload["protected_oos_touched"] is False
    assert payload["result_created"] is False
    assert payload["arm_created"] is False
    assert payload["prereg_md_sha256"] == PREREG_MD_SHA256
    assert payload["prereg_json_sha256"] == PREREG_JSON_SHA256
    assert _sha256(PREREG_MD) == PREREG_MD_SHA256
    assert _sha256(PREREG_JSON) == PREREG_JSON_SHA256
    assert "IMPLEMENTATION_FROZEN = true" in md
    assert "ARMED = false" in md
    assert "EXECUTION_AUTHORIZED = false" in md
    assert payload["next_unit"] == "OUTCOME_BLIND_MARKET_05_IMPLEMENTATION_RED_TEAM_AUDIT"


def test_eth_accepted_and_constants_bound():
    payload = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    data = payload["data"]
    assert data["btc_dataset"] == "CORE_BTC_BINANCE_V0"
    assert data["btc_snapshot_id"] == BTC_SNAPSHOT
    assert data["eth_dataset"] == "CORE_ETH_BINANCE_V0"
    assert data["eth_snapshot_id"] == ETH_SNAPSHOT
    assert data["eth_dataset_accepted"] is True
    assert data["core_btc_redefined"] is False
    consts = payload["scientific_constants"]
    assert consts["decision_time"] == "00:00:00 UTC"
    assert consts["feature_lookback"] == "24 hours"
    assert consts["outcome_horizon"] == "24 hours"
    assert consts["eth_confirmation"] == "BTC_SIDE * Z_ETH"
    assert consts["materiality"] == 0.02
    assert consts["block_length"] == 14
    assert consts["bootstrap_replicates"] == 5000
    assert consts["random_seed"] == 2026091905
    assert consts["predictive_bootstrap_refit"] is False
    assert consts["coefficient_bootstrap_refit"] is True
    assert consts["invalid_replicate_dropping_authorized"] is False
    for rel, digest in payload["implementation_files"].items():
        assert _sha256(REPO / rel) == digest
    for rel, digest in payload["test_files"].items():
        assert _sha256(REPO / rel) == digest


def test_no_arm_or_result_and_audit_answers_are_no_for_invalid_paths():
    payload = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    assert not (REPO / "docs/research/MARKET_05_ARM.json").exists()
    assert not (REPO / "docs/research/MARKET_05_RESULT.json").exists()
    answers = payload["audit_answers"]
    assert answers["ordinary_test_import_triggers_scientific_execution"] is False
    assert answers["evaluator_can_read_protected_oos"] is False
    assert answers["missing_eth_can_drop_candidate_only"] is False
    assert answers["test_fold_can_affect_training_standardization"] is False
    assert answers["bootstrap_randomness_can_vary_between_runs"] is False
    assert answers["promotion_with_materiality_below_2pct"] is False
    assert answers["one_third_positive_years_pass_temporal_gate"] is False
    assert answers["year_exactly_minus_2pct_passes"] is False
    assert answers["predictive_bootstrap_can_refit"] is False
    assert answers["coefficient_bootstrap_can_skip_refit"] is False
    assert answers["real_data_outcomes_before_arm"] is False
    dumped = json.dumps(payload)
    for needle in (
        "beta_candidate",
        "POOLED_MAE_CANDIDATE_VALUE",
        "market_05_beta_hat",
        "confirmation_correlation",
    ):
        assert needle not in dumped
