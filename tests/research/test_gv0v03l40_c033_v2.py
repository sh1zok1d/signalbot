"""Sealed C033 planning object recompiled under GV0R02 V2. No new design numbers."""

import json
from pathlib import Path

from scripts.research.gv0v03l40_c033_v2 import (
    FROZEN_PRIMARY,
    FROZEN_STOPPING_RULE,
    PLANNING_PATH,
    RESULT_PATH,
    compile_sealed_planning,
)

REPO = Path(__file__).resolve().parents[2]


def test_sealed_c033_recompile_blocks_on_zero_support_without_editing_the_design():
    raw = PLANNING_PATH.read_bytes()
    planning = json.loads(raw)
    result = compile_sealed_planning(planning)
    assert PLANNING_PATH.read_bytes() == raw
    assert planning["PRIMARY_FREEZE"] == FROZEN_PRIMARY
    assert planning["EXPECTED_EFFECT"]["MIN_MEANINGFUL_EFFECT"] == 0.2
    assert planning["REPLICATION_SURFACE"]["STOPPING_RULE"] == FROZEN_STOPPING_RULE
    assert result["MECHANISM_ACTIVE_N"] == 0
    assert result["MECHANISM_INACTIVE_N"] == 1383
    assert result["FEASIBILITY_STATUS"] != "FEASIBLE_FOR_PREREGISTRATION"
    assert result["FEASIBILITY_STATUS"] == "DEFINITION_INCOMPLETE"
    codes = [b["BLOCKER_CODE"] for b in result["BLOCKERS"]]
    assert "PRIMARY_MECHANISM_SUPPORT_ZERO" in codes
    assert "ALPHA_UNATTAINABLE" in codes
    assert "PROSPECTIVE_MECHANISM_SUPPORT_UNGUARANTEED" in codes
    assert result["ALPHA_ATTAINABLE"] is False
    assert result["MIN_ATTAINABLE_P"] == 1.0
    assert result["PRIMARY_LABEL_ORBIT_SIZE"] == 1
    assert result["DISCOVERY_SCREEN"]["MDE_STRESS"] is None
    assert result["DISCOVERY_SCREEN"]["POWER_STRESS"] is None
    assert result["DISCOVERY_SCREEN"]["NON_IDENTIFIABLE"] is True
    assert result["C033_NEXT"] == "STOP / NOT_PREREGISTRABLE_UNDER_FROZEN_DESIGN"
    assert result["MARKET_OUTCOMES_OPENED"] is False
    assert result["PROTECTED_2025_2026_OPENED"] is False
    assert result["SCIENTIFIC_DESIGN_CHANGED"] is False
    assert result["V1_LAYER"]["FEASIBILITY_STATUS"] == "FEASIBLE_FOR_PREREGISTRATION"
    assert result["COMPILER_SCHEMA_VERSION"] == "GV0R02_SCHEMA_V2"
    assert result["COMPILER_POLICY_VERSION"] == "GV0R02_POLICY_V2"


def test_written_v2_artifact_matches_the_recompile():
    stored = json.loads(RESULT_PATH.read_text())
    fresh = compile_sealed_planning(json.loads(PLANNING_PATH.read_text()))
    for key in (
        "FEASIBILITY_STATUS",
        "BLOCKERS",
        "ALPHA_ATTAINABLE",
        "MIN_ATTAINABLE_P",
        "PRIMARY_LABEL_ORBIT_SIZE",
        "DISCOVERY_SCREEN",
        "REPLICATION_SCREEN",
        "MECHANISM_ACTIVE_N",
        "MECHANISM_INACTIVE_N",
        "C033_NEXT",
        "RESULT_ID",
    ):
        assert stored[key] == fresh[key]
    assert stored["SOURCE_PLANNING_SHA256"]
    assert (REPO / "docs/research/GV0V03L40_C033_V1_FEASIBILITY.json").read_text()
