"""C020 close: terminology audit only. The frozen design is not redesigned."""

import datetime as dt
import json
from pathlib import Path

from scripts.research.gv0r01_c020_design import build_calendar

ROOT = Path(__file__).resolve().parents[2]
CLOSE = ROOT / "docs" / "research" / "GV0R01_C020_CLOSE.json"
DESIGN = ROOT / "docs" / "research" / "GV0R01_C020_OUTCOME_BLIND_DESIGN.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def test_observed_assignment_is_outside_the_pseudo_set():
    calendar = build_calendar()
    events = [pair["EVENT_DATE"] for pair in calendar["COVERED"]]
    weeks = set()
    for iso in events:
        day = dt.date.fromisoformat(iso)
        monday = day - dt.timedelta(days=day.weekday())
        weeks.update(monday + dt.timedelta(days=offset) for offset in range(7))
    assert all(dt.date.fromisoformat(iso) in weeks for iso in events)
    close = _load(CLOSE)
    assert close["OBSERVED_ASSIGNMENT_IN_REFERENCE_SUPPORT"] is False
    assert close["OBSERVED_ASSIGNMENT_IN_TRANSFORMATION_ORBIT"] is False
    assert close["EXACT_RANDOMIZATION_CLAIM_STATUS"] == "NOT_JUSTIFIED"
    assert close["INFERENCE_CLASSIFICATION"] == "PLACEBO_REFERENCE_DISTRIBUTION"
    assert close["REFERENCE_SUPPORT_SIZE"] == str(calendar["SUPPORT"])
    assert close["REFERENCE_SUPPORT_RESOLUTION"] == calendar["MIN_P"]


def test_close_does_not_reopen_execution_or_market_data():
    close = _load(CLOSE)
    design = _load(DESIGN)
    assert close["C020_STATUS"] == "CLOSED_OUTCOME_BLIND_INFORMATIONALLY_WEAK_REFERENCE_TEST"
    assert close["C020_EXECUTION_AUTHORIZED"] is False
    assert close["DESIGN_CHANGED"] is False
    assert close["POWER_GATE_REOPENED"] is False
    assert close["STRESS_POWER_AT_FROZEN_BAR"] == 0.4
    assert close["FROZEN_EXECUTION_EFFECT"] == design["EXECUTION_MDE_THRESHOLD"]
    assert close["OUTCOME_BLIND_GATE_RESULT"] == "EXECUTION_INFORMATIONALLY_WEAK"
    assert close["BTC_PRICE_VALUES_OPENED"] is False
    assert close["BTC_VOLUME_VALUES_OPENED"] is False
    assert close["MARKET_OUTCOMES_COMPUTED"] is False
    assert close["C020_PRIMARY_TEST_EXECUTED"] is False
    assert close["SCIENTIFIC_DEGREES_OF_FREEDOM_REMAINING"] == 0
    assert close["NEXT_CANDIDATE"] == "NONE_READY"
    assert "exact two-sided pseudo-holiday randomization" in design["INFERENCE_METHOD"]
    assert close["MONTE_CARLO_P_FLOOR"] == 1.0 / 1001.0
