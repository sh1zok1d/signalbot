"""Outcome-blind C004 design. Must not open a price file."""

import json
from pathlib import Path

from scripts.research import gv0r01_c004_design as D

DOC = json.loads(Path("docs/research/GV0R01_C004_OUTCOME_BLIND_DESIGN.json").read_text())


def test_claim_is_fomc_residual_share_and_not_c012():
    assert DOC["C004_DEFINITION_STATUS"] == "UNAMBIGUOUS"
    assert "FOMC" in DOC["C004_CANONICAL_CLAIM"]
    assert "idiosyncratic" in DOC["C004_CANONICAL_CLAIM"]
    assert DOC["CPI_POOLED_IN_PRIMARY"] is False
    assert DOC["EVENT_FAMILIES"] == ["SCHEDULED_FOMC_MONETARY_POLICY_ANNOUNCEMENTS"]
    assert DOC["PRIMARY_ENDPOINT"].startswith("DELTA_SHARE")
    assert "DELTA_24" not in DOC["PRIMARY_ENDPOINT"]


def test_universe_and_calendars_are_deterministic():
    events, blocked = D.load_events()
    again, _ = D.load_events()
    assert [e["EVENT_ID"] for e in events] == [e["EVENT_ID"] for e in again]
    assert len(events) == 39
    pairs = D.assign(events, blocked)
    assert len(pairs) == 38
    assert DOC["EVENT_COUNT_COVERED"] == 38
    assert DOC["UNCOVERED_EVENT_IDS"] == ["20200129"]
    assert DOC["CALENDAR_AUTHORITIES"]["CPI_DIGEST"].startswith("760ed2c5")
    assert all(not i.startswith("BLS_") for i in DOC["EVENT_IDS"])


def test_dependence_graph_and_gate():
    assert DOC["OVERLAP_GRAPH_NODES"] == 76
    assert DOC["OUTCOME_EDGES"] == 0
    assert DOC["OVERLAP_GRAPH_EDGES"] == 260
    assert DOC["OVERLAP_GRAPH_COMPONENTS"] == 1
    assert DOC["MAX_OVERLAP_COMPONENT_SIZE"] == 76
    assert DOC["PRIMARY_LABEL_ORBIT_SIZE"] == "16"
    assert DOC["ALPHA_ATTAINABLE"] is False
    assert DOC["OUTCOME_BLIND_GATE_RESULT"] == "EXECUTION_INFORMATIONALLY_WEAK"
    assert DOC["EXECUTION_MDE_THRESHOLD"] == 0.10
    assert DOC["SCIENTIFIC_DEGREES_OF_FREEDOM_REMAINING"] == 0
    assert DOC["MARKET_DATA_OPENED_FOR_C004"] is False
    assert DOC["PROTECTED_2025_VALUES_OPENED"] is False
    src = Path(D.__file__).read_text()
    assert "read_parquet" not in src
    assert "load_btc" not in src
