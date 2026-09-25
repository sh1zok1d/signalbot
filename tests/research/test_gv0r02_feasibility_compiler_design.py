"""Schema contract for the GV0R02 feasibility compiler design. No engine."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "docs" / "research" / "GV0R02_FEASIBILITY_COMPILER_SCHEMA.json"
CASES = ROOT / "docs" / "research" / "GV0R02_FEASIBILITY_COMPILER_GOLDEN_CASES.json"
STATUSES = [
    "FEASIBLE_FOR_PREREGISTRATION",
    "INFORMATIONALLY_WEAK",
    "INFERENCE_SUPPORT_INSUFFICIENT",
    "STRUCTURAL_INFERENCE_RISK",
    "DATA_BLOCKED",
    "PIT_BLOCKED",
    "DEFINITION_INCOMPLETE",
]


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def test_schema_required_contract():
    schema = _load(SCHEMA)
    assert schema["COMPILER_SCHEMA_VERSION"] == "GV0R02_SCHEMA_V0"
    assert schema["COMPILER_POLICY_VERSION"] == "GV0R02_POLICY_V0"
    assert schema["FEASIBILITY_COMPILER_IMPLEMENTED"] is False
    assert schema["POSITIVE_CONTROL_EXECUTED"] is False
    assert schema["FEASIBILITY_STATUSES"] == STATUSES
    assert set(schema["STATUS_PRIORITY"]) == set(STATUSES)
    assert schema["STATUS_PRIORITY"][0] == "DEFINITION_INCOMPLETE"
    assert schema["STATUS_PRIORITY"][-1] == "FEASIBLE_FOR_PREREGISTRATION"
    assert "PORTABILITY" in schema["FEATURE_REGISTRY_FORBIDDEN_FIELDS"]
    assert schema["RARE_EVENT_HEURISTIC"]["NOT_A_REJECTION"] is True
    assert schema["BOUNDED_REVISION"]["MAX_REVISIONS"] == 1
    assert "MIN_MEANINGFUL_EFFECT" in schema["BOUNDED_REVISION"]["FORBIDDEN_AFTER_FIRST_RESULT"]
    assert "NAMED_INFERENCE_CLASS" in schema["BOUNDED_REVISION"]["FORBIDDEN_AFTER_FIRST_RESULT"]
    roles = schema["COMPILER_PASSES"][5]["DEFAULT_ROLES"]
    assert roles["BINANCE_2020_2024"] == "DISCOVERY"
    assert roles["BITMEX_2016_2019"] == "HISTORICAL_REPLICATION_CANDIDATE"
    assert roles["Y2025_2026"] == "PROTECTED_HOLDOUT"
    for field in ("PROPOSAL_ID", "MIN_MEANINGFUL_EFFECT", "NAMED_INFERENCE_CLASS"):
        assert field in schema["PROPOSAL_REQUIRED_FIELDS"]
    for forbidden in ("exact event count", "power", "exact MDE"):
        assert forbidden in schema["LLM_MUST_NOT_SUPPLY"]
    assert "REFERENCE_SUPPORT_RESOLUTION" in schema["OUTPUT_REQUIRED_FIELDS"]
    assert "MIN_ATTAINABLE_P" in schema["OUTPUT_REQUIRED_FIELDS"]


def test_golden_cases_match_closed_records():
    cases = {row["CASE_ID"]: row for row in _load(CASES)["CASES"]}
    c012 = cases["GOLDEN_C012"]
    assert c012["MDE_SINGLE_WINDOW_SD"] == 0.6093023255813953
    assert c012["FROZEN_EXECUTION_THRESHOLD"] == 0.5
    assert c012["EXPECTED_FEASIBILITY_STATUS"] == "INFORMATIONALLY_WEAK"
    c004 = cases["GOLDEN_C004"]
    assert c004["PRIMARY_LABEL_ORBIT_SIZE"] == 16
    assert c004["MIN_ATTAINABLE_P"] == 0.0625
    assert c004["ALPHA_ATTAINABLE"] is False
    assert c004["EXPECTED_FEASIBILITY_STATUS"] == "INFERENCE_SUPPORT_INSUFFICIENT"
    c020 = cases["GOLDEN_C020"]
    assert c020["INFERENCE_CLASSIFICATION"] == "PLACEBO_REFERENCE_DISTRIBUTION"
    assert c020["REFERENCE_SUPPORT_RESOLUTION"] == 1.6473952425747334e-59
    assert c020["POWER_AT_FROZEN_BAR_STRESS"] == 0.4
    assert c020["EXPECTED_FEASIBILITY_STATUS"] == "INFORMATIONALLY_WEAK"
    assert c020["MUST_NOT_LABEL_REFERENCE_RESOLUTION_AS"] == "MIN_ATTAINABLE_EXACT_P"
    assert _load(CASES)["MARKET_OUTCOMES_RECOMPUTED"] is False


def test_no_compiler_engine_or_generator_edit():
    research = ROOT / "scripts" / "research"
    engines = list(research.glob("*feasibility_compiler*.py"))
    assert engines == []
    assert not (research / "gv0r02").exists()
