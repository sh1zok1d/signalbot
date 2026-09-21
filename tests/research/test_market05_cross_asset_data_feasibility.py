"""MARKET-05 BTC/ETH temporal-feasibility checks.

Outcome-blind coverage and availability only. Does not inspect future
returns, MAE, or ETH-confirmation predictive metrics.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MD = REPO / "docs/research/MARKET_05_CROSS_ASSET_DATA_FEASIBILITY.md"
JSON_PATH = REPO / "docs/research/MARKET_05_CROSS_ASSET_DATA_FEASIBILITY.json"
CAND_JSON = REPO / "docs/research/MARKET_05_CROSS_ASSET_CANDIDATE.json"
INVENTORY = REPO / "docs/research_data/CORE_ETH_BINANCE_V0/SOURCE_INVENTORY.json"
MANIFEST = REPO / "docs/manifests/CORE_ETH_BINANCE_V0.yaml"
CORE_BTC_MANIFEST = REPO / "docs/manifests/CORE_BTC_BINANCE_V0.yaml"

INVENTORY_SHA256 = "033a06428d5d2a56fcde23a8fe64ebe4d8afa2f57d5d3263e3d0b9c6db38e49e"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load() -> dict:
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


def _md() -> str:
    return MD.read_text(encoding="utf-8")


def test_feasibility_classification_and_datasets():
    payload = _load()
    md = _md()
    assert payload["feasibility_classification"] == (
        "MARKET_05_CANDIDATE_FROZEN_DATA_FEASIBLE"
    )
    assert payload["btc_dataset"] == "CORE_BTC_BINANCE_V0"
    assert payload["eth_dataset"] == "CORE_ETH_BINANCE_V0"
    assert payload["core_btc_redefined"] is False
    assert payload["preferred_construction_failed"] is False
    assert payload["mixed_venue_or_instrument_class"] is False
    assert "btc_dataset = CORE_BTC_BINANCE_V0" in md
    assert "eth_dataset = CORE_ETH_BINANCE_V0" in md
    assert "MARKET_05_CANDIDATE_FROZEN_DATA_FEASIBLE" in md
    assert CORE_BTC_MANIFEST.exists()
    assert "dataset_id: CORE_BTC_BINANCE_V0" in CORE_BTC_MANIFEST.read_text(
        encoding="utf-8"
    )


def test_common_coverage_and_bar_end_exclusive():
    payload = _load()
    md = _md()
    assert payload["btc_coverage"] == "[2020-01-01T00:00:00Z, 2026-08-26T00:00:00Z)"
    assert payload["eth_coverage"] == "[2020-01-01T00:00:00Z, 2026-08-26T00:00:00Z)"
    assert payload["common_coverage"] == "[2020-01-01T00:00:00Z, 2026-08-26T00:00:00Z)"
    assert payload["btc_bar_availability_semantics"] == "bar_end_exclusive"
    assert payload["eth_bar_availability_semantics"] == "bar_end_exclusive"
    assert payload["common_decision_timestamps_feasible"] is True
    assert payload["same_support_required"] is True
    assert payload["scientific_development_window_selected"] is False
    assert "COMMON_COVERAGE = [2020-01-01T00:00:00Z, 2026-08-26T00:00:00Z)" in md
    assert "BTC_BAR_AVAILABILITY_SEMANTICS = bar_end_exclusive" in md
    assert "ETH_BAR_AVAILABILITY_SEMANTICS = bar_end_exclusive" in md
    assert "COMMON_DECISION_TIMESTAMPS_FEASIBLE = true" in md
    assert "close_time is not available_at" in md
    assert "same_support_required = true" in md


def test_eth_companion_inventory_identity_preserved():
    payload = _load()
    inv = json.loads(INVENTORY.read_text(encoding="utf-8"))
    manifest = MANIFEST.read_text(encoding="utf-8")
    assert _sha256(INVENTORY) == INVENTORY_SHA256
    assert payload["eth_companion"]["source_inventory_sha256"] == INVENTORY_SHA256
    assert payload["eth_companion"]["status"] == (
        "SOURCE_INVENTORY_BOUND_NOT_MATERIALIZED_NOT_ACCEPTED"
    )
    assert payload["eth_companion"]["accepted_for_discovery"] is False
    assert payload["eth_companion"]["listed_zip_objects"] == 104
    assert payload["eth_companion"]["missing_zip_objects"] == 0
    assert payload["full_eth_snapshot_materialized"] is False
    assert inv["dataset_id"] == "CORE_ETH_BINANCE_V0"
    assert inv["does_not_redefine_core_btc_binance_v0"] is True
    assert inv["scientific_outcomes_inspected"] is False
    assert "does_not_redefine_core_btc_binance_v0: true" in manifest
    if "status: ACCEPTED_FOR_DISCOVERY" in manifest:
        assert "snapshot_id:" in manifest
        assert INVENTORY_SHA256 in manifest
        assert "companion_of: CORE_BTC_BINANCE_V0" in manifest
    else:
        assert "SOURCE_INVENTORY_BOUND_NOT_MATERIALIZED_NOT_ACCEPTED" in manifest
        assert "research_authorized: false" in manifest


def test_probe_is_timestamp_only_and_complete():
    payload = _load()
    probe = payload["probe"]
    assert probe["kind"] == "OUTCOME_BLIND_TIMESTAMP_AND_COMPLETENESS_ONLY"
    assert probe["returns_computed"] is False
    assert probe["mae_computed"] is False
    assert probe["future_outcomes_computed"] is False
    assert probe["correlation_with_future_outcome_computed"] is False
    assert probe["regression_scientific_result_computed"] is False
    assert probe["identifiability_diagnostic_performed"] is False
    assert probe["price_values_retained"] is False
    assert all(row["missing_bucket_count"] == 0 for row in probe["periods"])
    assert all(row["duplicate_count"] == 0 for row in probe["periods"])
    assert all(row["checksum_verification"] == "VERIFIED" for row in probe["periods"])
    md = _md()
    assert "Returns, MAE, future outcomes" in md
    assert "outcome_blind_identifiability_diagnostic_performed = false" in md


def test_no_scientific_outcome_artifacts_or_oos_touch():
    payload = _load()
    md = _md()
    dumped = json.dumps(payload)
    assert payload["scientific_outcomes_inspected"] is False
    assert payload["protected_oos_touched"] is False
    assert payload["execution_authorized"] is False
    assert payload["armed"] is False
    assert "SIGNALBOT_PROTECTED_OOS_UNTOUCHED = YES" in md
    for needle in (
        "beta_candidate",
        "MAE_mean",
        "future_return_mean",
        "confirmation_correlation",
        "regression_coefficient",
        "aligned_future_return_mean",
    ):
        assert needle not in dumped
        assert needle not in md
    cand = json.loads(CAND_JSON.read_text(encoding="utf-8"))
    assert cand["execution_authorized"] is False
    assert cand["protected_oos_touched"] is False
    assert payload["next_unit"] == "OUTCOME_BLIND_MARKET_05_EXACT_PREREGISTRATION"
