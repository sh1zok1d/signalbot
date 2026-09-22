"""Schema/consistency tests for the post-Sprint03 decision and Sprint04 selection.

Outcome-blind. Reads JSON/Markdown only; opens no market data.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SPRINT = REPO / "docs/research/DISCOVERY_SPRINT_04.json"
ROTATION = REPO / "docs/research/HETEROGENEOUS_FAMILY_ROTATION_V3.json"
DECISION = REPO / "docs/research/POST_SPRINT03_PROGRAM_DECISION.json"
ROTATION_V2 = REPO / "docs/research/HETEROGENEOUS_FAMILY_ROTATION_V2.json"
NEXT_UNIT = "DISCOVERY_SPRINT_04_BATCH_FEASIBILITY_AND_OUTCOME_BLIND_IMPLEMENTATION"

CANDIDATE_FIELDS = (
    "ID",
    "PROVISIONAL_NAME",
    "MECHANISM_FAMILY",
    "MECHANISM",
    "INFORMATION_SOURCE",
    "OBSERVABLE",
    "FUNCTION",
    "PRIMARY_TARGET",
    "HORIZON",
    "BASELINE_OR_NULL",
    "FALSIFIER",
    "NEAREST_HISTORICAL_WORK",
    "WHY_NOT_A_RESCUE",
    "DATA_REQUIRED",
    "DATA_STATUS",
    "EXPECTED_IMPLEMENTATION_COST",
    "MAIN_CONFOUNDERS",
    "WHAT_POSITIVE_WOULD_TEACH",
    "WHAT_NULL_WOULD_ELIMINATE",
    "EXPECTED_INFORMATION_GAIN",
)
CARD_FIELDS = (
    "NAME",
    "FAMILY",
    "MECHANISM",
    "INFORMATION_SOURCE",
    "DATASET_OR_SOURCE_AUTHORITY",
    "LEGAL_TIME_RANGE",
    "DECISION_CLOCK",
    "SELECTOR",
    "FUNCTION",
    "PRIMARY_TARGET",
    "HORIZON",
    "PRIMARY_BASELINE",
    "MATCHING_STRATA_IF_ANY",
    "NULL_HYPOTHESIS",
    "PRIMARY_STATISTIC",
    "PRACTICAL_GATE_DIRECTION",
    "TEMPORAL_STABILITY_REQUIREMENT",
    "MINIMUM_SUPPORT",
    "FALSIFIER",
    "ALLOWED_CLAIM",
    "FORBIDDEN_CLAIMS",
    "NEAREST_PRIOR_WORK",
    "WHY_NOT_RESCUE",
    "NO_LOOKAHEAD_RULE",
    "PROTECTED_BOUNDARY",
    "SEARCH_SURFACE",
)
OUTCOME_FALSE = (
    "SCIENTIFIC_OUTCOMES_COMPUTED",
    "D12_EXECUTED",
    "D13_EXECUTED",
    "D7_RERUN_PERFORMED",
    "D8_EXECUTED",
    "D7_CONFIRMATION_EXECUTED",
    "D11_CONFIRMATION_EXECUTED",
    "PROTECTED_2025_OPENED",
    "PROTECTED_2026_OPENED",
    "MARKET_07_CREATED",
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_json_artifacts_are_canonical_sorted():
    for path in (SPRINT, ROTATION, DECISION):
        raw = path.read_text(encoding="utf-8")
        canonical = json.dumps(json.loads(raw), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        assert raw == canonical, path


def test_outcome_boundary_flags_everywhere():
    for path in (SPRINT, ROTATION, DECISION):
        blob = _load(path)
        for key in OUTCOME_FALSE:
            assert blob[key] is False, (path.name, key)
        assert blob["D14_EXECUTED"] == "NOT_SELECTED", path.name


def test_program_decision_records_exact_states():
    d = _load(DECISION)
    assert d["D9"] == "consumed NO_USEFUL_STRUCTURE"
    assert d["D10"] == "consumed NO_USEFUL_STRUCTURE"
    assert d["D11"] == "consumed PROMISING_PROTOTYPE"
    assert d["INTERNAL_DISCOVERY_CARDS_EXECUTED"] == 8
    assert d["INTERNAL_PROMISING_PROTOTYPES"] == 3
    assert d["D7_CONFIRMATION_SELECTED_NOW"] is False
    assert d["D11_CONFIRMATION_SELECTED_NOW"] is False
    assert "mechanism-space coverage" in d["CONFIRMATION_DEFERRAL_REASON"]
    assert d["POST_SPRINT04_AUTOMATION_MATURITY_DECISION_REQUIRED"] is True
    assert d["AUTOMATIC_SPRINT05"] is False
    assert set(d["POST_SPRINT04_DECISION_OPTIONS"].values()) == {
        "HYPOTHESIS_GENERATOR_V0_INFRA_READY",
        "AT_MOST_ONE_FINAL_SPRINT05",
    }
    assert d["GENERATOR_BUILT_NOW"] is False
    assert d["D9_D10_D11_RESULT_ARTIFACTS_MUTATED"] is False
    assert d["NEXT_UNIT"] == NEXT_UNIT


def test_candidate_pool_is_complete_and_diverse():
    s = _load(SPRINT)
    cands = s["CANDIDATES"]
    assert 8 <= len(cands) <= 12
    assert s["CANDIDATE_POOL_N"] == len(cands)
    for cid, row in cands.items():
        assert row["ID"] == cid
        for field in CANDIDATE_FIELDS:
            assert row[field], (cid, field)
        assert isinstance(row["SELECTED"], bool)
        if not row["SELECTED"]:
            assert row["REJECTION_REASON"], cid
    sources = {row["INFORMATION_SOURCE"] for row in cands.values()}
    families = {row["MECHANISM_FAMILY"].split(" ")[0] for row in cands.values()}
    assert len(sources) >= 5
    assert len(families) >= 5
    for row in cands.values():
        assert "probability of success" not in json.dumps(row).lower()


def test_selection_is_two_orthogonal_non_volatility_cards():
    s = _load(SPRINT)
    assert s["INTERNAL_CARDS"] == ["D12", "D13"]
    assert s["SPRINT04_SELECTED_COUNT"] == 2
    assert s["D14"] == "NOT_SELECTED"
    selected = [c for c in s["CANDIDATES"].values() if c["SELECTED"]]
    assert sorted(c["SELECTED_AS"] for c in selected) == ["D12", "D13"]
    cards = s["CARDS"]
    assert {cards["D12"]["FAMILY"], cards["D13"]["FAMILY"]} == {"J", "H"}
    for card in cards.values():
        for field in CARD_FIELDS:
            assert card[field], (card["NAME"], field)
        target = card["PRIMARY_TARGET"].lower()
        assert "rv" not in target.split() and "volatility" not in target
    assert s["EXPECTED_INTERNAL_DISCOVERY_CARDS_EXECUTED_AFTER_SPRINT04"] == 10
    assert s["AUTOMATIC_SPRINT05"] is False
    assert s["NEXT_UNIT"] == NEXT_UNIT


def _nth_sunday(year: int, month: int, n: int) -> dt.date:
    day = dt.date(year, month, 1)
    day += dt.timedelta((6 - day.weekday()) % 7)
    return day + dt.timedelta(7 * (n - 1))


def _last_sunday(year: int, month: int) -> dt.date:
    day = dt.date(year, month + 1, 1) - dt.timedelta(1)
    return day - dt.timedelta((day.weekday() - 6) % 7)


def test_d12_dst_calendar_matches_statutory_rules_and_windows_isolate_us():
    auth = _load(SPRINT)["CARDS"]["D12"]["DATASET_OR_SOURCE_AUTHORITY"]
    for year in range(2020, 2025):
        us = [_nth_sunday(year, 3, 2), _nth_sunday(year, 11, 1)]
        eu = [_last_sunday(year, 3), _last_sunday(year, 10)]
        assert auth["US_TRANSITION_DAYS"][str(year)] == [d.isoformat() for d in us]
        assert auth["EU_TRANSITION_DAYS"][str(year)] == [d.isoformat() for d in eu]
        # W=7 keeps the EU clock constant inside every US window.
        assert (us[1] - eu[1]).days >= 7
        assert (eu[0] - us[0]).days > 7


def test_d13_never_targets_protected_months_and_has_no_horizon_search():
    card = _load(SPRINT)["CARDS"]["D13"]
    auth = card["DATASET_OR_SOURCE_AUTHORITY"]
    assert "2019-12 .. 2024-12" in auth["MONTHS_ALLOWED"]
    assert card["DATA_STATUS"] == "FEASIBILITY_REQUIRED"
    assert "no alternate horizons" in card["SEARCH_SURFACE"].lower()
    assert "N" in card["VALUES_FROZEN_IN_NEXT_UNIT_BEFORE_OUTCOMES"]


def test_rotation_v3_separates_whole_family_from_subfamily_and_preserves_v2():
    r = _load(ROTATION)
    assert r["PARENT_POLICY"] == "HETEROGENEOUS_FAMILY_ROTATION_V2"
    assert r["WHOLE_FAMILY_CLOSED_BY_SINGLE_FORMULATION"] is False
    fams = r["FAMILY_STATUS"]
    assert set(fams) == set("ABCDEFGHIJ")
    for key, row in fams.items():
        assert row["WHOLE_FAMILY_STATUS"], key
        assert row["TESTED_OR_DEPRIORITIZED_SUBFAMILY"], key
    assert fams["J"]["NEW_FAMILY_PROPOSAL"] is True
    assert r["SELECTED_THIS_ROTATION"] == ["H", "J"]
    v2 = _load(ROTATION_V2)
    assert v2["STATUS"] == "FROZEN"
    assert v2["SELECTED_INTERNAL_CARDS"] == ["D9", "D10", "D11"]


def test_routing_docs_point_at_sprint04_next_unit():
    for rel in (
        "docs/CURRENT_RESEARCH_STATE.md",
        "docs/RESEARCH_ROADMAP.md",
        "docs/DOCUMENTATION_INDEX.md",
        "docs/RESEARCH_LEDGER.md",
    ):
        text = (REPO / rel).read_text(encoding="utf-8")
        assert NEXT_UNIT in text, rel
    index = (REPO / "docs/DOCUMENTATION_INDEX.md").read_text(encoding="utf-8")
    for name in (
        "POST_SPRINT03_PROGRAM_DECISION",
        "HETEROGENEOUS_FAMILY_ROTATION_V3",
        "DISCOVERY_SPRINT_04",
    ):
        assert name in index
