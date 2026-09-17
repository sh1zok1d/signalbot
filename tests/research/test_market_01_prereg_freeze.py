"""Outcome-blind MARKET-01 prereg freeze identity checks.

Does not inspect MARKET outcomes, execute MARKET-01, or implement the
evaluator. Binds freeze-authority hashes to the frozen prereg bytes.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PREREG_MD = REPO_ROOT / "docs" / "research" / "MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG.md"
PREREG_JSON = REPO_ROOT / "docs" / "research" / "MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG.json"
FREEZE_JSON = REPO_ROOT / "docs" / "research" / "MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG_FREEZE.json"
FREEZE_MD = REPO_ROOT / "docs" / "research" / "MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG_FREEZE.md"

EXPECTED_MD_SHA256 = "d82b60e1a923e8eb897252abc4a9013b6535357004f2dc7dc08f56f072542866"
EXPECTED_JSON_SHA256 = "6885abaf178401a1307e9adc5c02c69dac4fb5f3034bfddebfafc2439dde2ce4"
MATERIALIZATION_HEAD = "9c1a661c52ad1ee7295cb898c1e1a048d5281d2f"
MATERIALIZATION_TREE = "1928969ed4d12896a3793a7048aff163dc1b3dac"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _freeze() -> dict:
    return json.loads(FREEZE_JSON.read_text(encoding="utf-8"))


def test_market_01_prereg_byte_identity_matches_materialization():
    assert _sha256(PREREG_MD) == EXPECTED_MD_SHA256
    assert _sha256(PREREG_JSON) == EXPECTED_JSON_SHA256
    assert PREREG_MD.stat().st_size == 21718
    assert PREREG_JSON.stat().st_size == 22576


def test_market_01_freeze_authority_binds_exact_paths_and_hashes():
    freeze = _freeze()
    md = freeze["frozen_prereg_artifacts"]["MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG.md"]
    js = freeze["frozen_prereg_artifacts"]["MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG.json"]
    assert md["path"] == "docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG.md"
    assert js["path"] == "docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG.json"
    assert md["sha256"] == EXPECTED_MD_SHA256
    assert js["sha256"] == EXPECTED_JSON_SHA256
    assert md["sha256"] == _sha256(PREREG_MD)
    assert js["sha256"] == _sha256(PREREG_JSON)
    assert freeze["accepted_prereg_content"]["head"] == MATERIALIZATION_HEAD
    assert freeze["accepted_prereg_content"]["tree"] == MATERIALIZATION_TREE
    assert freeze["freeze_commit_head"] == "UNSET_UNTIL_THIS_COMMIT"
    assert freeze["freeze_commit_tree"] == "UNSET_UNTIL_THIS_COMMIT"


def test_market_01_freeze_status_is_frozen_outcome_blind_not_executed():
    freeze = _freeze()
    assert freeze["status"] == "FROZEN_OUTCOME_BLIND"
    assert freeze["research_id"] == "MARKET-01_OI_EXPANSION_WEAK_CONTINUATION"
    state = freeze["explicit_state"]
    assert state["market_01_prereg_frozen"] is True
    assert state["market_01_freeze_required"] is False
    assert state["market_01_prereg_materialized"] is True
    assert state["market_01_prereg_ready"] is True
    assert state["market_01_outcome_inspected"] is False
    assert state["market_01_executed"] is False
    assert state["market_01_armed"] is False
    assert state["market_01_execution_authorized"] is False
    assert state["market_01_test_calibrated"] is False
    assert state["protected_oos_touched"] is False
    assert state["v3_reused_as_market_01_test"] is False
    assert state["b2_06_execution_authorized"] is False
    assert state["default_v4"] is False
    assert freeze["not_an_arm"] is True
    assert freeze["not_market_01_execution"] is True
    assert freeze["not_v3"] is True
    assert freeze["not_v4"] is True
    for forbidden in freeze["forbidden_outcome_dependent_labels"]:
        assert freeze["status"] != forbidden
        assert freeze["next_lifecycle_state"] != forbidden
    assert freeze["next_lifecycle_state"] == "MARKET-01_IMPLEMENTATION"


def test_market_01_freeze_preserves_uncalibrated_and_v3_non_applicability():
    freeze = _freeze()
    limits = freeze["limitations_preserved"]
    assert limits["market_01_confirmatory_identity_is_not_v3"] is True
    assert limits["market_01_test_calibrated"] is False
    assert limits["v3_synthetic_calibration_validates_market_01"] is False
    assert limits["new_synthetic_calibration_authorized"] is False
    assert limits["default_v4"] is False
    md = FREEZE_MD.read_text(encoding="utf-8")
    assert "MARKET_01_TEST_CALIBRATED = NO" in md
    assert "**not** V3" in md
    assert "DEFAULT_V4 = NO" in md
    assert "BLOCKED_MISSING_OBSERVABLE" in md
