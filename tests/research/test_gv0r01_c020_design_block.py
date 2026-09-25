"""C020 stops before design because the holiday calendars are unpinned."""

import json
from pathlib import Path

BLOCK = json.loads(Path("docs/research/GV0R01_C020_DESIGN_BLOCK.json").read_text())


def test_definition_is_unambiguous_and_blocked_on_calendars():
    assert BLOCK["C020_DEFINITION_STATUS"] == "UNAMBIGUOUS"
    assert "holiday" in BLOCK["C020_CANONICAL_CLAIM"].lower()
    assert BLOCK["OUTCOME_BLIND_GATE_RESULT"] == "BLOCKED_BY_MISSING_INPUT"
    missing = {row["DATASET"] for row in BLOCK["MISSING_INPUTS"]}
    assert missing == {
        "NYSE_HOLIDAY_CALENDAR_ARCHIVE",
        "CN_STATE_COUNCIL_HOLIDAY_NOTICES",
        "US_OPM_FEDERAL_HOLIDAY_LIST",
    }
    assert all(row["PINNED"] is False for row in BLOCK["MISSING_INPUTS"])
    for name in missing:
        assert not list(Path("docs/research_data").glob(f"**/{name}/**"))


def test_no_market_access_and_no_power():
    assert BLOCK["MARKET_DATA_OPENED_FOR_C020"] is False
    assert BLOCK["C020_PRIMARY_TEST_EXECUTED"] is False
    assert BLOCK["POWER_SIMULATION_PERFORMED"] is False
    assert BLOCK["PROTECTED_2025_VALUES_OPENED"] is False
    assert BLOCK["PROTECTED_2026_VALUES_OPENED"] is False
    assert BLOCK["PRIMARY_LABEL_ORBIT_SIZE"] == "NOT COMPUTED"
    assert BLOCK["ALPHA_ATTAINABLE"] == "NOT COMPUTED"
    assert BLOCK["C012_C004_OUTCOMES_USED"] is False
    assert BLOCK["NEXT_UNIT"] == "GV0R01_C020_HOLIDAY_CALENDAR_PINNING"
