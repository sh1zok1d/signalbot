"""GV0V03L40 shortlist readiness. Outcome-blind stop rules only."""

import json
from pathlib import Path

from scripts.research.gv0v03l40_shortlist_e2e import (
    C033_RESULT,
    LEDGER,
    REPORT_JSON,
    build_report,
    c024_record,
    c037_record,
)

REPO = Path(__file__).resolve().parents[2]


def test_open_cards_stop_before_planning_and_c033_is_only_read():
    report = build_report()
    assert report["MARKET_OUTCOMES_OPENED"] is False
    assert report["PROTECTED_2025_2026_OPENED"] is False
    assert report["LLM_CALLS"] == 0
    assert report["PAID_DATA_SPEND_USD"] == 0
    assert report["TEST_QUEUE"] == []
    assert report["PREREG_DRAFTS_CREATED"] == []
    assert report["READY_CARDS"] == []
    assert report["TERMINAL_CARDS"] == ["C033"]
    expected = {
        "C005": "PIT_BLOCKED",
        "C024": "DATA_BLOCKED",
        "C031": "PIT_BLOCKED",
        "C033": "TERMINAL_NOT_PREREGISTRABLE",
        "C037": "PIT_BLOCKED",
    }
    for card_id, status in expected.items():
        row = report["CARDS"][card_id]
        assert row["FINAL_READINESS"] == status
        assert row["PRIMARY_VARIANT"] is None or card_id == "C033"
        assert row["MARKET_OUTCOMES_OPENED"] is False
    for card_id in ("C005", "C024", "C031", "C037"):
        row = report["CARDS"][card_id]
        assert row["GV0R02_V2_STATUS"] == "NOT_COMPILED"
        assert row["COMPILED"] is False
        assert row["NOMINAL_N"] is None
        assert row["MECHANISM_ACTIVE_N"] is None
        assert row["STAGE_STOPPED"] == "B"
        assert row["VARIANT_MATRIX"]
        assert all(item["ELIGIBLE"] is False for item in row["VARIANT_MATRIX"])
    c033 = report["CARDS"]["C033"]
    sealed = json.loads(C033_RESULT.read_text())
    assert c033["RECOMPILED_IN_THIS_UNIT"] is False
    assert c033["GV0R02_V2_STATUS"] == "DEFINITION_INCOMPLETE"
    assert c033["MECHANISM_ACTIVE_N"] == 0
    assert c033["MECHANISM_INACTIVE_N"] == 1383
    assert c033["PRIMARY_LABEL_ORBIT_SIZE"] == 1
    assert c033["MIN_ATTAINABLE_P"] == 1.0
    assert c033["ALPHA_ATTAINABLE"] is False
    assert c033["BLOCKERS"] == [row["BLOCKER_CODE"] for row in sealed["BLOCKERS"]]
    assert c033["NEXT_UNIT"] == "STOP / NOT_PREREGISTRABLE_UNDER_FROZEN_DESIGN"


def test_variant_matrices_cover_the_frozen_search_surface_in_listed_order():
    ledger = json.loads(LEDGER.read_text())
    cards = {row["CANDIDATE_ID"]: row for row in ledger["PARSED_CARD"]}
    report = build_report()
    expected_n = {"C005": 4, "C024": 8, "C031": 8, "C037": 8}
    for card_id, count in expected_n.items():
        params = cards[card_id]["SEARCH_SURFACE"]["PARAMETERS"]
        matrix = report["CARDS"][card_id]["VARIANT_MATRIX"]
        assert len(matrix) == count
        assert matrix[0]["VARIANT"] == {name: values[0] for name, values in params.items()}
        assert report["CARDS"][card_id]["PRIMARY_VARIANT"] is None


def test_c024_does_not_shorten_the_window_and_c037_does_not_invent_a_proxy():
    ledger = json.loads(LEDGER.read_text())
    cards = {row["CANDIDATE_ID"]: row for row in ledger["PARSED_CARD"]}
    c024 = c024_record(cards["C024"])
    assert c024["EVIDENCE"]["WINDOW_CHANGED"] is False
    assert c024["EVIDENCE"]["TARDIS_PURCHASED"] is False
    assert c024["EVIDENCE"]["PAYLOADS_OPENED"] is False
    assert c024["FINAL_READINESS"] == "DATA_BLOCKED"
    assert "2023" not in c024["NEXT_UNIT"] or "Do not shorten" in c024["NEXT_UNIT"]
    c037 = c037_record(cards["C037"])
    proxy_rows = [row for row in c037["VARIANT_MATRIX"] if row["VARIANT"]["TURNOVER_SOURCE"] == "volume_share_proxy"]
    supply_rows = [row for row in c037["VARIANT_MATRIX"] if row["VARIANT"]["TURNOVER_SOURCE"] == "circulating_supply"]
    assert len(proxy_rows) == 4 and len(supply_rows) == 4
    assert all(row["ELIGIBLE"] is False for row in proxy_rows + supply_rows)
    assert c037["EVIDENCE"]["VOLUME_SHARE_PROXY_SELECTED"] is False
    assert c037["EVIDENCE"]["VOLUME_SHARE_PROXY_ARITHMETIC_IN_FROZEN_CARD"] is False
    assert c037["FINAL_READINESS"] == "PIT_BLOCKED"


def test_written_report_matches_the_builder_and_opens_no_outcomes():
    stored = json.loads(REPORT_JSON.read_text())
    fresh = build_report()
    assert stored["CARDS"].keys() == fresh["CARDS"].keys()
    for card_id in fresh["CARDS"]:
        assert stored["CARDS"][card_id]["FINAL_READINESS"] == fresh["CARDS"][card_id]["FINAL_READINESS"]
        assert stored["CARDS"][card_id]["BLOCKERS"] == fresh["CARDS"][card_id]["BLOCKERS"]
    assert stored["TEST_QUEUE"] == []
    source = (REPO / "scripts/research/gv0v03l40_shortlist_e2e.py").read_text()
    assert "compile_proposal_v2" not in source
    assert "RV_DECAY" not in source
