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
