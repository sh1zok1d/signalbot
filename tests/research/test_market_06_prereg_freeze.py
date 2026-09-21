"""Historical V0 MARKET-06 freeze identity (superseded, not live authority).

Live freeze authority is rebound in the amendment re-freeze unit.
This file only proves the first freeze bytes were retained exactly.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
V0_PREREG_MD = REPO_ROOT / "docs" / "research" / "MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_V0.md"
V0_PREREG_JSON = REPO_ROOT / "docs" / "research" / "MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_V0.json"
V0_FREEZE_JSON = REPO_ROOT / "docs" / "research" / "MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_FREEZE_V0.json"
V0_FREEZE_MD = REPO_ROOT / "docs" / "research" / "MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_FREEZE_V0.md"
AMENDMENT_JSON = (
    REPO_ROOT / "docs" / "research" / "MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_AMENDMENT_001.json"
)

EXPECTED_MD_SHA256 = "0489fc71e999b48a7a82223615bd0acd50b1f69af8bc9901d1c681834e55cfcc"
EXPECTED_JSON_SHA256 = "332d91140c7ead87f4539b49c8a5647064f9c5e1d0bb8178c16dcc7eaf7a88f4"
OLD_PREREG_CONTENT_HEAD = "b21bf46dcc39a2b9243c4172f731cd4d3fbf79b1"
OLD_FREEZE_HEAD = "5f14411abc926a2b486d83de5b696ec3cf362488"
MATERIALIZATION_TREE = "ce436bf3d025340752f5afea765ea0cbe50e499e"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_v0_prereg_byte_identity_matches_first_materialization():
    assert _sha256(V0_PREREG_MD) == EXPECTED_MD_SHA256
    assert _sha256(V0_PREREG_JSON) == EXPECTED_JSON_SHA256
    assert V0_PREREG_MD.stat().st_size == 19122
    assert V0_PREREG_JSON.stat().st_size == 12248


def test_v0_freeze_still_binds_old_payload_hashes():
    freeze = json.loads(V0_FREEZE_JSON.read_text(encoding="utf-8"))
    md = freeze["frozen_prereg_artifacts"]["MARKET_06_CROSS_VENUE_DISLOCATION_PREREG.md"]
    js = freeze["frozen_prereg_artifacts"]["MARKET_06_CROSS_VENUE_DISLOCATION_PREREG.json"]
    assert md["sha256"] == EXPECTED_MD_SHA256
    assert js["sha256"] == EXPECTED_JSON_SHA256
    assert freeze["accepted_prereg_content"]["head"] == OLD_PREREG_CONTENT_HEAD
    assert freeze["accepted_prereg_content"]["tree"] == MATERIALIZATION_TREE
    assert freeze["freeze_commit_head"] == "UNSET_UNTIL_THIS_COMMIT"


def test_amendment_records_old_heads_and_pre_outcome_reason():
    amendment = json.loads(AMENDMENT_JSON.read_text(encoding="utf-8"))
    assert amendment["old_prereg_content_head"] == OLD_PREREG_CONTENT_HEAD
    assert amendment["old_freeze_head"] == OLD_FREEZE_HEAD
    assert amendment["amendment_reason"] == (
        "PRE_OUTCOME_SCIENTIFIC_DEFINITION_DRIFT_CORRECTION"
    )
    assert amendment["outcomes_inspected_before_amendment"] is False
    assert amendment["scientific_outcomes_inspected"] is False
    assert amendment["market_06_executed"] is False
    assert amendment["market_06_armed"] is False
    assert amendment["market_06_result_created"] is False
    assert amendment["protected_2025_opened"] is False
    assert amendment["protected_2026_opened"] is False
    md = V0_FREEZE_MD.read_text(encoding="utf-8")
    assert "FROZEN_OUTCOME_BLIND" in md


LIVE_PREREG_MD = REPO_ROOT / "docs" / "research" / "MARKET_06_CROSS_VENUE_DISLOCATION_PREREG.md"
LIVE_PREREG_JSON = REPO_ROOT / "docs" / "research" / "MARKET_06_CROSS_VENUE_DISLOCATION_PREREG.json"
LIVE_FREEZE_JSON = REPO_ROOT / "docs" / "research" / "MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_FREEZE.json"
LIVE_FREEZE_MD = REPO_ROOT / "docs" / "research" / "MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_FREEZE.md"

AMENDED_MD_SHA256 = "55f6f3525a4a3a5878f870a757e890faba336e8d944f6b751087a68e94102d06"
AMENDED_JSON_SHA256 = "191dfcf48996953f5c78873eb54b24e88430dea2307f22adb6120be4e893c7ae"
AMENDED_PREREG_HEAD = "b4459ab96addd6c39d4baec35248410a8f5cf8e0"
AMENDED_PREREG_TREE = "be3cf4739b0e810105403d12d2d543383d34c912"


def test_live_prereg_byte_identity_matches_amended_materialization():
    assert _sha256(LIVE_PREREG_MD) == AMENDED_MD_SHA256
    assert _sha256(LIVE_PREREG_JSON) == AMENDED_JSON_SHA256
    assert LIVE_PREREG_MD.stat().st_size == 20019
    assert LIVE_PREREG_JSON.stat().st_size == 13307


def test_live_freeze_authority_binds_amended_payload_and_old_heads():
    freeze = json.loads(LIVE_FREEZE_JSON.read_text(encoding="utf-8"))
    md = freeze["frozen_prereg_artifacts"]["MARKET_06_CROSS_VENUE_DISLOCATION_PREREG.md"]
    js = freeze["frozen_prereg_artifacts"]["MARKET_06_CROSS_VENUE_DISLOCATION_PREREG.json"]
    assert md["path"] == "docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG.md"
    assert js["path"] == "docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG.json"
    assert md["sha256"] == AMENDED_MD_SHA256
    assert js["sha256"] == AMENDED_JSON_SHA256
    assert md["sha256"] == _sha256(LIVE_PREREG_MD)
    assert js["sha256"] == _sha256(LIVE_PREREG_JSON)
    assert freeze["accepted_prereg_content"]["head"] == AMENDED_PREREG_HEAD
    assert freeze["accepted_prereg_content"]["tree"] == AMENDED_PREREG_TREE
    assert freeze["freeze_commit_head"] == "UNSET_UNTIL_THIS_COMMIT"
    assert freeze["freeze_commit_tree"] == "UNSET_UNTIL_THIS_COMMIT"
    hist = freeze["supersedes_historical_freeze"]
    assert hist["old_prereg_content_head"] == OLD_PREREG_CONTENT_HEAD
    assert hist["old_freeze_head"] == OLD_FREEZE_HEAD
    assert hist["outcomes_inspected_before_amendment"] is False
    corr = freeze["amendment_corrections_bound"]
    assert corr["F1_ROBUST_SCALE_1_4826_FIXED"] is True
    assert corr["F2_ABS_BTC_RET_CONTROL_FIXED"] is True
    assert corr["F3_ARITHMETIC_MAE_FIXED"] is True
    assert corr["F4_GATE2_LOWER_BOUND_FIXED"] is True
    assert corr["GATE_2_EXACT_PREDICATE"] == "BETA_ABS_DISLOCATION_Z_CI95_LOW > 0"
    assert "upper" not in corr["GATE_2_EXACT_PREDICATE"].lower()


def test_live_freeze_status_is_frozen_outcome_blind_not_executed():
    freeze = json.loads(LIVE_FREEZE_JSON.read_text(encoding="utf-8"))
    assert freeze["status"] == "FROZEN_OUTCOME_BLIND"
    state = freeze["explicit_state"]
    assert state["market_06_prereg_frozen"] is True
    assert state["market_06_outcome_inspected"] is False
    assert state["market_06_executed"] is False
    assert state["market_06_armed"] is False
    assert state["market_06_execution_authorized"] is False
    assert state["protected_oos_authorized"] is False
    assert freeze["not_an_arm"] is True
    assert freeze["not_v3"] is True
    assert freeze["not_v4"] is True
    assert freeze["next_lifecycle_state"] == "MARKET_06_IMPLEMENTATION_OUTCOME_BLIND"
    md = LIVE_FREEZE_MD.read_text(encoding="utf-8")
    assert "MARKET_06_TEST_CALIBRATED = NO" in md
    assert "DEFAULT_V4 = NO" in md
    assert "BETA_ABS_DISLOCATION_Z_CI95_LOW > 0" in md
    assert "1.4826" in md
