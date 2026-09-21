"""Stored-artifact tests for the post-D2 program decision.

Does not run another D2 experiment.
Does not open Binance 2025/2026.
Does not create MARKET-07 or a nearby D2 variant.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.research.d2_bitmex_replication_prereg import file_sha256
from scripts.research.market_06_result_persistence import result_payload_sha256

REPO = Path(__file__).resolve().parents[2]
DECISION_JSON = "docs/research/PROGRAM_DECISION_POST_D2_BITMEX_REPLICATION_SUPPORTED.json"
DECISION_MD = "docs/research/PROGRAM_DECISION_POST_D2_BITMEX_REPLICATION_SUPPORTED.md"
CORRECTED_RESULT = "docs/research/D2_BITMEX_REPLICATION_CORRECTED_RESULT.json"
ORIGINAL_RESULT = "docs/research/D2_BITMEX_REPLICATION_RESULT.json"
ORIGINAL_PREREG = "docs/research/D2_BITMEX_REPLICATION_PREREG.json"
EVALUATOR = "scripts/research/d2_bitmex_replication_evaluator.py"

FROZEN_PREREG_SHA256 = "939fe29243956195f2ca97723a7b94b666ce59359c55e096f8fba4d65c7d9044"
FROZEN_IMPLEMENTATION_SHA256 = "087e7ea5892f2ab81f26bd61c82b2709b6812b6916554e5c92846a52496d77aa"
ORIGINAL_INVALID_PAYLOAD = "9af98e72e7afc2c3e8af7f2d359401110e1e9c9829e69185ab23519e06fba48a"
CORRECTED_PAYLOAD = "b7c53bf343936da652c987212575ade962e32c57cc1eed01907621c6f1ad4273"


def _decision() -> dict:
    return json.loads((REPO / DECISION_JSON).read_text(encoding="utf-8"))


def test_historical_d2_result_bytes_unmutated() -> None:
    original = json.loads((REPO / ORIGINAL_RESULT).read_text(encoding="utf-8"))
    hashed = {k: v for k, v in original.items() if k != "RESULT_PAYLOAD_SHA256"}
    assert original["CLASSIFICATION"] == "D2_BITMEX_REPLICATION_INVALID"
    assert original["RESULT_PAYLOAD_SHA256"] == ORIGINAL_INVALID_PAYLOAD
    assert result_payload_sha256(hashed) == ORIGINAL_INVALID_PAYLOAD
    corrected = json.loads((REPO / CORRECTED_RESULT).read_text(encoding="utf-8"))
    hashed_c = {k: v for k, v in corrected.items() if k != "CORRECTED_RESULT_PAYLOAD_SHA256"}
    assert corrected["CLASSIFICATION"] == "D2_BITMEX_REPLICATION_SUPPORTED"
    assert corrected["CORRECTED_RESULT_PAYLOAD_SHA256"] == CORRECTED_PAYLOAD
    assert result_payload_sha256(hashed_c) == CORRECTED_PAYLOAD
    assert file_sha256(REPO / ORIGINAL_PREREG) == FROZEN_PREREG_SHA256
    assert file_sha256(REPO / EVALUATOR) == FROZEN_IMPLEMENTATION_SHA256


def test_claim_ladder_and_program_class() -> None:
    decision = _decision()
    ladder = decision["CLAIM_LADDER"]
    assert ladder["DISCOVERY_CLAIM"]["STATUS"] == "SUPPORTED"
    assert ladder["REPLICATION_CLAIM"]["STATUS"] == "SUPPORTED"
    assert ladder["MARKET_MECHANISM_CLAIM"]["STATUS"] == "NOT_YET_SUPPORTED"
    assert ladder["TRADING_EDGE_CLAIM"]["STATUS"] == "NOT_TESTED"
    assert ladder["PRODUCT_CLAIM"]["STATUS"] == "NOT_TESTED"
    assert decision["D2_PROGRAM_CLASS"] == "INDEPENDENTLY_REPLICATED_MECHANISM_CANDIDATE"
    assert decision["D2_PROGRAM_CLASS"] != "PROVEN_EDGE"
    assert decision["D2_PROGRAM_CLASS"] != "VALIDATED_CANDIDATE"
    assert "PROVEN_ALPHA" in decision["UNJUSTIFIED_CLAIMS"]
    assert "VALIDATED_TRADING_EDGE" in decision["UNJUSTIFIED_CLAIMS"]
    assert "EXACT_BINANCE_CONFIRMATION" in decision["UNJUSTIFIED_CLAIMS"]
    assert decision["INTERNAL_HISTORICAL_CANDIDATES_PROMOTED"] == 0
    assert decision["INTERNAL_INDEPENDENTLY_REPLICATED_MECHANISM_CANDIDATES"] == 1


def test_binance_sealed_no_market_07_no_d2_variant_execution() -> None:
    decision = _decision()
    assert decision["BINANCE_2025_2026_DECISION"] == "KEEP_SEALED"
    assert decision["PROTECTED_2025_OPENED"] is False
    assert decision["PROTECTED_2026_OPENED"] is False
    assert decision["2025_OPEN_AUTHORIZED"] is False
    assert decision["2026_OPEN_AUTHORIZED"] is False
    assert decision["MARKET_07_CREATED"] is False
    assert decision["D2_NEXT_SCIENTIFIC_QUESTION_EXECUTED"] is False
    assert decision["NO_THRESHOLD_HORIZON_OR_RV_WINDOW_VARIANT"] is True
    assert decision["PRODUCT_BUILD_FROZEN"] is True
    assert decision["HYPOTHESIS_GENERATION_POLICY_CHANGED"] is True
    assert decision["NEXT_UNIT"] == (
        "D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_BEYOND_VOLATILITY_CLUSTERING_DESIGN"
    )
    market_07 = list((REPO / "docs").rglob("*MARKET_07*")) + list(
        (REPO / "docs").rglob("*MARKET-07*")
    )
    assert market_07 == []
    md = (REPO / DECISION_MD).read_text(encoding="utf-8")
    assert "INDEPENDENTLY_REPLICATED_MECHANISM_CANDIDATE" in md
    assert "KEEP_SEALED" in md
    assert "PROVEN_ALPHA" in md


def test_generation_policy_rotates_families_not_d2_neighbors() -> None:
    policy = _decision()["HYPOTHESIS_GENERATION_POLICY"]
    families = policy["FAMILIES"]
    assert set(families) == set("ABCDEFGHI")
    assert policy["FAMILY_A_IMMEDIATE_NEIGHBORS_FORBIDDEN"] is True
    assert policy["NO_MARKET_07_FROM_THIS_POLICY"] is True
    assert _decision()["D2_NEXT_SCIENTIFIC_QUESTION"] != "D2_RULE_1_THRESHOLD_VARIANT"
    assert "VOLATILITY_CLUSTERING" in _decision()["D2_NEXT_SCIENTIFIC_QUESTION"]


def test_decision_does_not_invoke_scientific_kernels() -> None:
    source = (REPO / DECISION_JSON).read_text(encoding="utf-8")
    md = (REPO / DECISION_MD).read_text(encoding="utf-8")
    for blob in (source, md):
        assert "execute_corrected_one_shot" not in blob
        assert "evaluate_constructed_rows" not in blob
    scientific_scripts = list((REPO / "scripts" / "research").glob("*program_decision_post_d2*"))
    assert scientific_scripts == []
