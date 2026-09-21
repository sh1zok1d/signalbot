"""Outcome-blind MARKET-06 prereg freeze identity checks.

Does not inspect MARKET outcomes, execute MARKET-06, or implement the
evaluator. Binds freeze-authority hashes to the frozen prereg bytes.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PREREG_MD = REPO_ROOT / "docs" / "research" / "MARKET_06_CROSS_VENUE_DISLOCATION_PREREG.md"
PREREG_JSON = REPO_ROOT / "docs" / "research" / "MARKET_06_CROSS_VENUE_DISLOCATION_PREREG.json"
FREEZE_JSON = REPO_ROOT / "docs" / "research" / "MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_FREEZE.json"
FREEZE_MD = REPO_ROOT / "docs" / "research" / "MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_FREEZE.md"

EXPECTED_MD_SHA256 = "0489fc71e999b48a7a82223615bd0acd50b1f69af8bc9901d1c681834e55cfcc"
EXPECTED_JSON_SHA256 = "332d91140c7ead87f4539b49c8a5647064f9c5e1d0bb8178c16dcc7eaf7a88f4"
MATERIALIZATION_HEAD = "b21bf46dcc39a2b9243c4172f731cd4d3fbf79b1"
MATERIALIZATION_TREE = "ce436bf3d025340752f5afea765ea0cbe50e499e"
PRE_PREREG_HEAD = "a75a5272f994f9728308c47c524f2839b73762a7"
PRE_PREREG_TREE = "7272614b7a2799aaf82a80f5d7c9cb1207af01ac"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _freeze() -> dict:
    return json.loads(FREEZE_JSON.read_text(encoding="utf-8"))


def test_market_06_prereg_byte_identity_matches_materialization():
    assert _sha256(PREREG_MD) == EXPECTED_MD_SHA256
    assert _sha256(PREREG_JSON) == EXPECTED_JSON_SHA256
    assert PREREG_MD.stat().st_size == 19122
    assert PREREG_JSON.stat().st_size == 12248


def test_market_06_freeze_authority_binds_exact_paths_and_hashes():
    freeze = _freeze()
    md = freeze["frozen_prereg_artifacts"]["MARKET_06_CROSS_VENUE_DISLOCATION_PREREG.md"]
    js = freeze["frozen_prereg_artifacts"]["MARKET_06_CROSS_VENUE_DISLOCATION_PREREG.json"]
    assert md["path"] == "docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG.md"
    assert js["path"] == "docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG.json"
    assert md["sha256"] == EXPECTED_MD_SHA256
    assert js["sha256"] == EXPECTED_JSON_SHA256
    assert md["sha256"] == _sha256(PREREG_MD)
    assert js["sha256"] == _sha256(PREREG_JSON)
    assert freeze["accepted_prereg_content"]["head"] == MATERIALIZATION_HEAD
    assert freeze["accepted_prereg_content"]["tree"] == MATERIALIZATION_TREE
    assert freeze["pre_prereg"]["head"] == PRE_PREREG_HEAD
    assert freeze["pre_prereg"]["tree"] == PRE_PREREG_TREE
    assert freeze["freeze_commit_head"] == "UNSET_UNTIL_THIS_COMMIT"
    assert freeze["freeze_commit_tree"] == "UNSET_UNTIL_THIS_COMMIT"
    assert freeze["freeze_parent_expected_head"] == MATERIALIZATION_HEAD


def test_market_06_freeze_status_is_frozen_outcome_blind_not_executed():
    freeze = _freeze()
    assert freeze["status"] == "FROZEN_OUTCOME_BLIND"
    assert freeze["research_id"] == "MARKET-06_CROSS_VENUE_DISLOCATION_ADVERSE_PATH_RISK"
    state = freeze["explicit_state"]
    assert state["market_06_prereg_frozen"] is True
    assert state["market_06_freeze_required"] is False
    assert state["market_06_prereg_materialized"] is True
    assert state["market_06_prereg_ready"] is True
    assert state["market_06_outcome_inspected"] is False
    assert state["market_06_executed"] is False
    assert state["market_06_armed"] is False
    assert state["market_06_execution_authorized"] is False
    assert state["market_06_test_calibrated"] is False
    assert state["protected_oos_touched"] is False
    assert state["v3_reused_as_market_06_test"] is False
    assert state["b2_06_execution_authorized"] is False
    assert state["default_v4"] is False
    assert freeze["not_an_arm"] is True
    assert freeze["not_market_06_execution"] is True
    assert freeze["not_v3"] is True
    assert freeze["not_v4"] is True
    for forbidden in freeze["forbidden_outcome_dependent_labels"]:
        assert freeze["status"] != forbidden
        assert freeze["next_lifecycle_state"] != forbidden
    assert freeze["next_lifecycle_state"] == "MARKET_06_IMPLEMENTATION_OUTCOME_BLIND"


def test_market_06_freeze_preserves_uncalibrated_and_v3_non_applicability():
    freeze = _freeze()
    limits = freeze["limitations_preserved"]
    assert limits["market_06_confirmatory_identity_is_not_v3"] is True
    assert limits["market_06_test_calibrated"] is False
    assert limits["v3_synthetic_calibration_validates_market_06"] is False
    assert limits["new_synthetic_calibration_authorized"] is False
    assert limits["default_v4"] is False
    md = FREEZE_MD.read_text(encoding="utf-8")
    assert "MARKET_06_TEST_CALIBRATED = NO" in md
    assert "**not** V3" in md
    assert "DEFAULT_V4 = NO" in md
    assert "BLOCKED_MISSING_OBSERVABLE" in md
    assert "`G5>=0.02`" in md
