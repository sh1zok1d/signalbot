"""Schema checks for the Level Engine discovery synthesis. No market outcome is read."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JSON_PATH = ROOT / "docs" / "research" / "LEVEL_ENGINE_DISCOVERY_SYNTHESIS_V1.json"
DOCS = (
    ROOT / "docs" / "research" / "LEVEL_ENGINE_DISCOVERY_SYNTHESIS_V1.md",
    ROOT / "docs" / "research" / "LEVEL_ENGINE_CONFIRMATION_PORTFOLIO_V1.md",
    ROOT / "docs" / "research" / "LEVEL_ENGINE_CLOSED_NEIGHBORHOODS_V1.md",
)

REQUIRED_UNITS = {
    "LEVEL_TOUCH_DEGRADATION_V1",
    "LEVEL_REJECTION_MEMORY_V1",
    "LEVEL_APPROACH_STATE_DISCOVERY_V1",
    "LEVEL_STRUCTURE_DISCOVERY_V1",
    "LEVEL_FIRST_TOUCH_RESOLUTION_CONFIRMATION_V1",
    "LEVEL_POSITIONING_FLOW_DISCOVERY_V1",
    "LEVEL_FLOW_RESPONSE_STATE_DISCOVERY_V1",
    "LEVEL_LIQUIDITY_STATE_DISCOVERY_V1",
    "LEVEL_POST_TOUCH_REACTION_DISCOVERY_V1",
    "LEVEL_ACCEPTANCE_PATH_DISCOVERY_V1",
    "LEVEL_CROSS_VENUE_REACTION_DISCOVERY_V1",
    "LEVEL_SPOT_PERP_REACTION_DISCOVERY_V1",
    "LEVEL_TIME_TO_RESOLUTION_DISCOVERY_V1",
    "LEVEL_BREAK_REJECT_SEQUENCE_DISCOVERY_V1",
    "LEVEL_ZONE_TRADED_ACTIVITY_DISCOVERY_V1",
    "LEVEL_VOLATILITY_TRANSITION_DISCOVERY_V1",
}

ALLOWED_CLASSES = {
    "FOUNDATION_CONFIRMED",
    "DISCOVERY_CANDIDATE_STRONG",
    "DISCOVERY_CANDIDATE_METHOD_LIMITED",
    "GENERIC_MARKET_STRUCTURE_NOT_LEVEL_SPECIFIC",
    "REDUNDANT_WITH_STRONGER_OBJECT",
    "NULL_NO_INCREMENTAL_INFORMATION",
    "INFORMATION_LIMITED",
    "CLOSED_NEIGHBORHOOD",
}

REQUIRED_FIELDS = {
    "unit",
    "object",
    "input_source",
    "decision_time",
    "outcome",
    "comparator",
    "effect",
    "uncertainty",
    "practical_bar",
    "stability",
    "pseudo_or_negative_control",
    "incremental_to",
    "discovery_or_confirmation",
    "claim_ceiling",
    "product_integration_status",
    "major_limitation",
    "final_synthesis_class",
}


def _load():
    return json.loads(JSON_PATH.read_text())


def test_documents_exist():
    assert JSON_PATH.is_file()
    for path in DOCS:
        assert path.is_file()
        assert path.stat().st_size > 0


def test_synthesis_is_not_an_outcome_unit():
    payload = _load()
    assert payload["mode"] == "SYNTHESIS"
    assert payload["posture"] == "NO_NEW_MARKET_OUTCOMES"
    assert payload["scientific_outcome_unit"] is False
    assert payload["new_market_outcomes_computed"] is False
    assert payload["confirmation_executed"] is False
    assert payload["composite_score"] is None
    assert payload["windows_consumed"] == []
    assert payload["atlas"]["updated"] is False
    assert payload["findings_registry_changed"] is False
    assert payload["product_change"] is False
    assert payload["claim_ladder_redefined"] is False
    assert payload["governing_decision"]["evidence_map_row"] is False
    assert payload["governing_decision"]["unit_number"] == 354


def test_evidence_map_covers_the_chain():
    payload = _load()
    rows = payload["evidence_map"]
    units = [row["unit"] for row in rows]
    assert set(units) == REQUIRED_UNITS
    assert len(units) == len(REQUIRED_UNITS)
    assert "DISCOVERY_FIRST" not in units
    for row in rows:
        missing = REQUIRED_FIELDS - row.keys()
        assert not missing, row["unit"]
        assert row["final_synthesis_class"] in ALLOWED_CLASSES
        assert row["claim_ceiling"] == "L2"
        assert "NOT_INTEGRATED" in row["product_integration_status"]


def test_foundation_and_portfolio_bounds():
    payload = _load()
    foundation = [
        row for row in payload["evidence_map"]
        if row["final_synthesis_class"] == "FOUNDATION_CONFIRMED"
    ]
    assert [row["unit"] for row in foundation] == [
        "LEVEL_FIRST_TOUCH_RESOLUTION_CONFIRMATION_V1"
    ]
    portfolio = payload["confirmation_portfolio"]
    assert portfolio["p1"] == []
    assert portfolio["p2"] == []
    assert portfolio["p0"] == ["LEVEL_FIRST_TOUCH_RESOLUTION_CONFIRMATION_V1"]
    assert len(portfolio["targets"]) <= 4
    assert [item["priority"] for item in portfolio["targets"]] == [
        "P3_PROSPECTIVE_ONLY",
        "P3_PROSPECTIVE_ONLY",
    ]
    assert portfolio["targets"][0]["unit"] == "LEVEL_VOLATILITY_TRANSITION_DISCOVERY_V1"
    assert portfolio["targets"][1]["unit"] == "LEVEL_CROSS_VENUE_REACTION_DISCOVERY_V1"
    blob = json.dumps(payload)
    assert "LEVEL_SCORE" not in blob
    assert "BUY" not in blob
    assert "SELL" not in blob


def test_bitmex_clock_is_not_called_independent():
    payload = _load()
    clock = payload["bitmex_audit"]["candidates"]["LEVEL_TIME_TO_RESOLUTION_DISCOVERY_V1"]
    assert clock["status"] == "BITMEX_CLOCK_NOT_INDEPENDENT_ENOUGH"
    assert clock["exact_minute_persisted"] is False
    vol = payload["bitmex_audit"]["candidates"]["LEVEL_VOLATILITY_TRANSITION_DISCOVERY_V1"]
    assert vol["scheduled_as_confirmation"] is False
    assert vol["exact_rv_computed"] is False
    assert vol["later_exact_rv_computed"] is True
    assert vol["later_pristine"] is False
    assert vol["later_surface_class"] == "TIME_DISJOINT_EXPOSED_SURFACE_REPLICATION"


def test_bitmex_replication_status_does_not_rewrite_the_discovery_class():
    payload = _load()
    row = next(
        item for item in payload["evidence_map"]
        if item["unit"] == "LEVEL_VOLATILITY_TRANSITION_DISCOVERY_V1"
    )
    assert row["final_synthesis_class"] == "DISCOVERY_CANDIDATE_STRONG"
    assert row["post_synthesis_status"] == "TIME_DISJOINT_REPLICATED_EXPOSED_SURFACE"
    assert row["frozen_route"].startswith("LEVEL_VOLATILITY_TRANSITION_CANDIDATE")
    later = payload["later_replication"]
    assert later["unit"] == "LEVEL_VOLATILITY_TRANSITION_BITMEX_REPLICATION_V1"
    assert later["surface_evidence_class"] == "TIME_DISJOINT_EXPOSED_SURFACE_REPLICATION"
    assert later["routing"] == "REPLICATION_SUPPORTS_LEVEL_VOLATILITY_TRANSITION"
    assert later["pristine"] is False
    assert later["claim_ceiling"] == "L2"
    assert later["prospective_started"] is False
    assert later["cross_venue_started"] is False
    assert later["product_change"] is False
    assert later["pooled_with_discovery"] is False
    obj = next(item for item in payload["objects"] if item["id"] == "EVENT_VOLATILITY_TRANSITION")
    assert obj["status"] == "TIME_DISJOINT_REPLICATED_EXPOSED_SURFACE"
    assert "PRISTINE_CONFIRMATION" not in json.dumps(payload)
