"""Contract tests for Discovery Sprint 03 card definition.

Outcome-blind. Does not load MARKET-06 OHLC, does not execute D9, does
not rerun D7, and does not open protected 2025/2026.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
POLICY_JSON = REPO / "docs/research/HETEROGENEOUS_FAMILY_ROTATION_V2.json"
SPRINT_JSON = REPO / "docs/research/DISCOVERY_SPRINT_03.json"
CONTRACT_FIELDS = (
    "DISCOVERY_ID",
    "MECHANISM_CLASS",
    "INFORMATION_SOURCE",
    "FUNCTION",
    "TARGET_FAMILY",
    "TIME_SCALE",
    "UNIT_OF_OBSERVATION",
    "MARKET_RELATIONSHIP",
    "SIMPLE_BASELINE",
    "SMALL_SEARCH_SURFACE",
    "KNOWN_PRIOR_EXPOSURE",
    "WHAT_A_NULL_DEPRIORITIZES",
    "WHAT_A_POSITIVE_WOULD_JUSTIFY_NEXT",
    "RESEARCHER_DOF",
    "MAX_ENGINEERING_SCOPE",
)
FORBIDDEN_M06 = (
    "24H_DIRECTION_ALIGNED_BTC_MAE",
    "additive incremental regression beside BTC controls",
    "ABS_DISLOCATION_Z predicts adverse BTC path",
    "BTC terminal-return prediction",
    "D2 dislocation-abstention filtering",
    "threshold rescue of MARKET-06",
    "another MARKET-06 predictive model",
)


def _policy() -> dict:
    return json.loads(POLICY_JSON.read_text(encoding="utf-8"))


def _sprint() -> dict:
    return json.loads(SPRINT_JSON.read_text(encoding="utf-8"))


def test_rotation_v2_selects_only_family_h_as_d9():
    policy = _policy()
    assert policy["NAME"] == "HETEROGENEOUS_FAMILY_ROTATION_V2"
    assert policy["STATUS"] == "FROZEN"
    assert policy["SELECTED_THIS_ROTATION"] == ["H"]
    assert policy["SELECTED_INTERNAL_CARDS"] == ["D9"]
    assert policy["FAMILY_STATUS"]["E"]["STATUS"] == "COOLDOWN_AFTER_POSITIVE"
    assert policy["FAMILY_STATUS"]["A"]["STATUS"] == "NOT_SELECTED_THIS_ROTATION"
    assert policy["FAMILY_STATUS"]["F"]["STATUS"] == "DEFERRED_BLOCKER_UNRESOLVED"
    assert policy["FAMILY_STATUS"]["G"]["STATUS"] == "NOT_SELECTED_THIS_ROTATION"
    assert policy["FAMILY_STATUS"]["H"]["STATUS"] == "SELECTED_THIS_ROTATION"
    assert policy["FAMILY_STATUS"]["H"]["TRUE_CROSS_SECTIONAL_PANEL"] is False
    assert policy["FAMILY_STATUS"]["I"]["STATUS"] == "DEFERRED_SOURCE_NOT_PINNED"
    assert policy["INTERNAL_DISCOVERY_CARDS_EXECUTED"] == 5
    assert policy["INTERNAL_PROMISING_PROTOTYPES"] == 2
    assert policy["INTERNAL_DISCOVERY_WARNING"] is None
    assert policy["INTERNAL_HYPOTHESIS_GENERATION_NOT_DEMONSTRATED"] is False
    assert policy["D7_CONFIRMATION_CANDIDATE"] is True
    assert policy["D7_CONFIRMATION_SELECTED_NOW"] is False
    assert policy["SCIENTIFIC_OUTCOMES_COMPUTED"] is False
    assert policy["MARKET_07_CREATED"] is False
    assert policy["PROTECTED_2025_OPENED"] is False
    assert policy["PROTECTED_2026_OPENED"] is False
    assert policy["D9_EXECUTED"] is False
    assert policy["FAMILY_H_TRUE_CROSS_SECTIONAL_PANEL_STILL_ABSENT"] is True
    assert policy["FAMILY_H_VENUE_STRUCTURE_SUBFAMILY_HAS_EXISTING_PIT_SURFACE"] is True


def test_sprint_defines_exactly_one_internal_card():
    sprint = _sprint()
    assert sprint["UNIT"] == "DISCOVERY_SPRINT_03"
    assert sprint["STATUS"] == "DEFINED"
    assert sprint["INTERNAL_CARDS"] == ["D9"]
    assert set(sprint["CARDS"]) == {"D9"}
    assert sprint["D9_STATUS"] == "DEFINED_NOT_EXECUTED"
    assert sprint["D9_EXECUTED"] is False
    assert sprint["D9_SCIENTIFIC_OUTCOME_COMPUTED"] is False
    assert sprint["SCIENTIFIC_OUTCOMES_COMPUTED"] is False
    assert sprint["MARKET_07_CREATED"] is False
    assert sprint["PROTECTED_2025_OPENED"] is False
    assert sprint["PROTECTED_2026_OPENED"] is False
    assert sprint["NO_CONFIRMATORY_PREREGISTRATION"] is True
    assert sprint["NEXT_UNIT"] == (
        "DISCOVERY_SPRINT_03_D9_FEASIBILITY_AND_OUTCOME_BLIND_IMPLEMENTATION"
    )
    assert "execute D9 scientific outcomes automatically" in sprint["NEXT_UNIT_MUST_NOT"]
    assert "rerun D7" in sprint["NEXT_UNIT_MUST_NOT"]
    assert "execute D8" in sprint["NEXT_UNIT_MUST_NOT"]
    assert sprint["D7_STATUS"] == "PROMISING_PROTOTYPE"
    assert sprint["D8_STATUS"] == "DEFERRED_INSUFFICIENT_CONTROL_SUPPORT"
    assert sprint["D8_NOT_A_NEGATIVE_SCIENTIFIC_RESULT"] is True
    assert sprint["D7_CONFIRMATION_CANDIDATE"] is True
    assert sprint["D7_CONFIRMATION_SELECTED_NOW"] is False
    assert sprint["D7_RERUN_PERFORMED"] is False
    assert sprint["INTERNAL_DISCOVERY_CARDS_EXECUTED"] == 5
    assert sprint["INTERNAL_PROMISING_PROTOTYPES"] == 2
    assert sprint["RESEARCH_DATA_DURABILITY_V1_REQUIRED"] is True
    assert sprint["RESEARCH_DATA_DURABILITY_V1_IMPLEMENTED"] is False


def test_three_family_h_candidates_and_h1_selected():
    sprint = _sprint()
    cands = sprint["CANDIDATES"]
    assert set(cands) == {
        "H1_VENUE_DISLOCATION_RESOLUTION_STRUCTURE",
        "H2_CROSS_VENUE_SHOCK_TRANSMISSION",
        "H3_DISLOCATION_PROCESS_DYNAMICS",
    }
    required = (
        "MECHANISM_CLASS",
        "INFORMATION_SOURCE",
        "FUNCTION",
        "TARGET_FAMILY",
        "TIME_SCALE",
        "UNIT_OF_OBSERVATION",
        "SIMPLE_BASELINE_OR_NULL",
        "KNOWN_PRIOR_EXPOSURE",
        "WHAT_A_NULL_DEPRIORITIZES",
        "WHAT_A_POSITIVE_WOULD_JUSTIFY_NEXT",
        "RESEARCHER_DOF",
        "DATA_REQUIREMENT",
        "DATA_FEASIBILITY_CLASS",
        "MAX_ENGINEERING_SCOPE",
    )
    for cand in cands.values():
        for field in required:
            assert cand[field], field
        assert cand["DATA_FEASIBILITY_CLASS"] == "DATA_READY"
    assert cands["H1_VENUE_DISLOCATION_RESOLUTION_STRUCTURE"]["SELECTION_STATUS"] == (
        "SELECTED_AS_D9"
    )
    assert cands["H2_CROSS_VENUE_SHOCK_TRANSMISSION"]["SELECTION_STATUS"] == (
        "NOT_SELECTED"
    )
    assert cands["H3_DISLOCATION_PROCESS_DYNAMICS"]["SELECTION_STATUS"] == (
        "NOT_SELECTED"
    )
    assert sprint["SELECTED_CANDIDATE"] == "H1_VENUE_DISLOCATION_RESOLUTION_STRUCTURE"


def test_d9_card_contract_and_frozen_surface():
    d9 = _sprint()["CARDS"]["D9"]
    assert d9["DISCOVERY_ID"] == "D9"
    assert d9["NAME"] == "VENUE_DISLOCATION_RESOLUTION_STRUCTURE"
    assert d9["FAMILY"] == "H"
    assert d9["FAMILY_NAME"] == "CROSS_SECTIONAL_OR_VENUE_STRUCTURE"
    assert d9["SUBFAMILY"] == "VENUE_STRUCTURE"
    assert d9["NOT_CROSS_SECTIONAL_PANEL"] is True
    assert d9["NOT_MARKET06_RESCUE"] is True
    assert d9["NOT_D7_NEIGHBOR"] is True
    assert d9["DATA_FEASIBILITY_CLASS"] == "DATA_READY"
    assert d9["DATASET_ID"] == "MARKET_06_OKX_BINANCE_FEASIBILITY_V0"
    assert d9["SNAPSHOT_ID"] == (
        "e0403e40a9b1e2903f15fb9283ec6caf54788e48153038982e364d4318183e68"
    )
    assert d9["PRIMARY_TARGET"] == "RESOLUTION_IMBALANCE"
    assert d9["STATUS"] == "DEFINED_NOT_EXECUTED"
    construction = d9["FROZEN_CONSTRUCTION"]
    assert construction["TRAILING_WINDOW_BARS"] == 8640
    assert construction["RESOLUTION_HORIZON_BARS"] == 12
    assert construction["EVENT"].startswith("|D(u)| > P90")
    assert "P85" not in construction["EVENT"]
    assert "P95" not in construction["EVENT"]
    assert construction["NO_ALTERNATE_THRESHOLDS"] is True
    assert construction["NO_HORIZON_SWEEP"] is True
    assert construction["PROTECTED_BOUND_STRICT"] is True
    assert "YEAR_SIGN_RV_MATCHED_RATE_MATCHED_RANDOM_NON_EVENT" in d9["SIMPLE_BASELINE"]
    assert d9["DATA_LABEL"] == "ADAPTIVE_DISCOVERY_ON_HISTORICALLY_EXPOSED_DATA"
    census = d9["STRUCTURAL_SUPPORT_FROM_EXISTING_CENSUS"]
    assert census["ALIGNED_TIMESTAMPS"] == 315648
    assert census["NATIVE_GRAIN"] == "5m"
    assert "does not compute" in census["NOTE"]
    for field in CONTRACT_FIELDS:
        assert field in d9, field
        assert d9[field]


def test_d9_is_not_market06_or_d7_rescue():
    d9 = _sprint()["CARDS"]["D9"]
    for item in FORBIDDEN_M06:
        assert item in d9["FORBIDDEN_MARKET06_RESCUE"]
    assert d9["PRIMARY_TARGET"] != "24H_DIRECTION_ALIGNED_BTC_MAE"
    assert "MAE" not in d9["PRIMARY_TARGET"]
    assert "IMPACT_PROXY" not in json.dumps(d9["FROZEN_CONSTRUCTION"])
    assert d9["FROZEN_CONSTRUCTION"]["TRAILING_WINDOW_BARS"] != 720
    assert "NEXT_HOUR_HIGH_IMPACT_STATE" not in d9["PRIMARY_TARGET"]
    matrix = _sprint()["ANTI_RESCUE_MATRIX"]
    for key in ("D9_NE_MARKET_06", "D9_NE_D7", "D9_NE_D2"):
        body = matrix[key]
        for field in (
            "INFORMATION_SOURCE_FUNCTION",
            "SELECTOR_OR_EVENT",
            "TARGET_FAMILY",
            "BASELINE",
            "NULL_ELIMINATES",
        ):
            assert body[field]


def test_no_outcomes_no_market_07_no_protected_open_claimed():
    sprint = _sprint()
    blob = json.dumps(sprint).upper()
    assert sprint["SCIENTIFIC_OUTCOMES_COMPUTED"] is False
    assert "D9_DISCOVERY_RESULT" not in blob
    assert "CLASSIFICATION_ASSIGNED" not in sprint
    assert sprint["MARKET_07_CREATED"] is False
    assert sprint["PROTECTED_2025_OPENED"] is False
    assert sprint["PROTECTED_2026_OPENED"] is False
    assert not (
        REPO / "docs/research/discovery_results/D9_DISCOVERY_RESULT.json"
    ).exists()
    assert not (REPO / "docs/research/MARKET_07_RESULT.json").exists()
    impl = list((REPO / "scripts/research").glob("*sprint_03*"))
    assert impl == []


def test_json_is_deterministic_sorted():
    for path in (POLICY_JSON, SPRINT_JSON):
        raw = path.read_text(encoding="utf-8")
        obj = json.loads(raw)
        canonical = json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        assert raw == canonical
