"""Contract tests for Discovery Sprint 02 card definition.

Outcome-blind. Does not load CORE OHLC, does not execute D7/D8, and does
not open protected 2025/2026.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
POLICY_JSON = REPO / "docs/research/HETEROGENEOUS_FAMILY_ROTATION_V1.json"
SPRINT_JSON = REPO / "docs/research/DISCOVERY_SPRINT_02.json"
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


def _policy() -> dict:
    return json.loads(POLICY_JSON.read_text(encoding="utf-8"))


def _sprint() -> dict:
    return json.loads(SPRINT_JSON.read_text(encoding="utf-8"))


def test_policy_is_frozen_and_selects_only_e_and_g():
    policy = _policy()
    assert policy["NAME"] == "HETEROGENEOUS_FAMILY_ROTATION_V1"
    assert policy["STATUS"] == "FROZEN"
    assert policy["SELECTED_THIS_ROTATION"] == ["E", "G"]
    assert policy["SELECTED_INTERNAL_CARDS"] == ["D7", "D8"]
    assert policy["SCIENTIFIC_OUTCOMES_COMPUTED"] is False
    assert policy["MARKET_07_CREATED"] is False
    assert policy["PROTECTED_2025_OPENED"] is False
    assert policy["PROTECTED_2026_OPENED"] is False
    assert policy["FAMILY_STATUS"]["F"]["STATUS"] == "DEFERRED_BLOCKER_UNRESOLVED"
    assert policy["FAMILY_STATUS"]["H"]["STATUS"] == "DEFERRED_DATA_LIMITATION"
    assert policy["FAMILY_STATUS"]["I"]["STATUS"] == "DEFERRED_SOURCE_NOT_PINNED"
    for letter in ("A", "B", "C", "D"):
        assert policy["FAMILY_STATUS"][letter]["STATUS"] == "NOT_SELECTED_THIS_ROTATION"


def test_sprint_defines_exactly_two_internal_cards():
    sprint = _sprint()
    assert sprint["UNIT"] == "DISCOVERY_SPRINT_02"
    assert sprint["STATUS"] == "DEFINED"
    assert sprint["INTERNAL_CARDS"] == ["D7", "D8"]
    assert set(sprint["CARDS"]) == {"D7", "D8"}
    assert sprint["D7_STATUS"] == "DEFINED_NOT_EXECUTED"
    assert sprint["D8_STATUS"] == "DEFINED_NOT_EXECUTED"
    assert sprint["D7_EXECUTED"] is False
    assert sprint["D8_EXECUTED"] is False
    assert sprint["SCIENTIFIC_OUTCOMES_COMPUTED"] is False
    assert sprint["MARKET_07_CREATED"] is False
    assert sprint["PROTECTED_2025_OPENED"] is False
    assert sprint["PROTECTED_2026_OPENED"] is False
    assert sprint["NO_CONFIRMATORY_PREREGISTRATION"] is True
    assert sprint["NEXT_UNIT"] == "DISCOVERY_SPRINT_02_FEASIBILITY_AND_IMPLEMENTATION"
    assert "execute D7/D8 scientific outcomes automatically" in sprint["NEXT_UNIT_MUST_NOT"]


def test_d7_is_family_e_kline_proxy_with_one_frozen_state():
    d7 = _sprint()["CARDS"]["D7"]
    assert d7["DISCOVERY_ID"] == "D7"
    assert d7["NAME"] == "KLINE_FLOW_IMPACT_STATE"
    assert d7["FAMILY"] == "E"
    assert d7["FAMILY_NAME"] == "LIQUIDITY_EXECUTION_STATE"
    assert d7["KLINE_PROXY_ONLY"] is True
    assert d7["NOT_ORDERBOOK_LIQUIDITY"] is True
    assert d7["NOT_REALIZED_SLIPPAGE"] is True
    construction = d7["FROZEN_CONSTRUCTION"]
    assert construction["TRAILING_WINDOW_HOURS"] == 720
    assert "P90" in construction["STATE"]
    assert "P85" not in construction["STATE"]
    assert "P95" not in construction["STATE"]
    assert construction["IMPACT_PROXY"] == "RET_ABS_1H / QREL_1H"
    assert "No epsilon" in construction["INELIGIBLE_IF"]
    assert d7["PRIMARY_TARGET"] == "NEXT_HOUR_HIGH_IMPACT_STATE"
    assert "calendar_year" in d7["SIMPLE_BASELINE"]
    assert "RV_BUCKET" in d7["SIMPLE_BASELINE"]
    assert d7["DATA_LABEL"] == "ADAPTIVE_DISCOVERY_ON_HISTORICALLY_EXPOSED_DATA"
    for field in CONTRACT_FIELDS:
        assert field in d7, field
        assert d7[field]


def test_d8_is_family_g_with_one_frozen_shock():
    d8 = _sprint()["CARDS"]["D8"]
    assert d8["DISCOVERY_ID"] == "D8"
    assert d8["NAME"] == "ENDOGENOUS_SHOCK_RECOVERY"
    assert d8["FAMILY"] == "G"
    assert d8["FAMILY_NAME"] == "EVENT_RESPONSE_RECOVERY"
    assert d8["NO_EXOGENOUS_CALENDAR"] is True
    event = d8["EVENT_DEFINITION"]
    assert event["RETURN_THRESHOLD"].startswith("ABS_EVENT_RETURN_t > P99")
    assert event["VOLUME_THRESHOLD"].startswith("EVENT_VOLUME_t > P90")
    assert event["AND"] is True
    assert event["NO_ALTERNATE_THRESHOLDS"] is True
    assert event["NO_HORIZON_SWEEP"] is True
    assert event["TRAILING_WINDOW_HOURS"] == 720
    assert event["MIN_EVENT_GAP_HOURS"] == 6
    assert d8["PRIMARY_TARGET"] == "RECOVERY_6H"
    assert "RECOVERY_24H" in d8["DIAGNOSTIC_ONLY_TARGET"]
    assert d8["MINIMUM_SUPPORT_RULE"]["IF_INADEQUATE"] == (
        "DEFERRED_INSUFFICIENT_EVENT_SUPPORT"
    )
    assert d8["MINIMUM_SUPPORT_RULE"]["NO_THRESHOLD_WEAKENING"] is True
    assert "non-event" in d8["SIMPLE_BASELINE"]
    for field in CONTRACT_FIELDS:
        assert field in d8, field
        assert d8[field]


def test_not_a_d2_or_m05_m06_variant():
    d7 = _sprint()["CARDS"]["D7"]
    d8 = _sprint()["CARDS"]["D8"]
    state = d7["FROZEN_CONSTRUCTION"]["STATE"]
    assert "RV_ABSTENTION" not in state
    assert "RULE_1" not in state
    assert "250" not in state
    assert d7["FROZEN_CONSTRUCTION"]["TRAILING_WINDOW_HOURS"] == 720
    assert d7["FROZEN_CONSTRUCTION"]["TRAILING_WINDOW_HOURS"] != 250
    assert "MAE" not in d7["PRIMARY_TARGET"]
    assert "ADVERSE_SHARE" not in d7["PRIMARY_TARGET"]
    assert "RULE_1" not in d8["EVENT_DEFINITION"]["RETURN_THRESHOLD"]
    assert "250" not in d8["EVENT_DEFINITION"]["RETURN_THRESHOLD"]
    assert d8["PRIMARY_TARGET"] == "RECOVERY_6H"
    assert d8["NO_EXOGENOUS_CALENDAR"] is True
    for key in (
        "D7_NE_D2",
        "D7_NE_MARKET_05_06",
        "D8_NE_D3",
        "D8_NE_H02_MEAN_REVERSION",
        "D7_NE_D8",
    ):
        body = _sprint()["ANTI_RESCUE_MATRIX"][key]
        for field in (
            "INFORMATION_SOURCE_FUNCTION",
            "SELECTOR_OR_EVENT",
            "TARGET_FAMILY",
            "BASELINE",
            "NULL_ELIMINATES",
        ):
            assert body[field]
    assert "Protected 2025/2026 sealed" in d7["LEGAL_INTERVAL"]
    assert "Protected 2025/2026 sealed" in d8["LEGAL_INTERVAL"]


def test_d7_does_not_claim_orderbook_or_l2():
    d7 = _sprint()["CARDS"]["D7"]
    info = d7["INFORMATION_SOURCE"].upper()
    assert d7["KLINE_PROXY_ONLY"] is True
    assert d7["NOT_ORDERBOOK_LIQUIDITY"] is True
    assert d7["NOT_REALIZED_SLIPPAGE"] is True
    assert "NO L2" in info
    assert "order-book liquidity dataset" in d7["WHAT_A_POSITIVE_WOULD_JUSTIFY_NEXT"]
    assert "No L2 ingestion" in d7["MAX_ENGINEERING_SCOPE"]
    assert "Kline-derived" in d7["MECHANISM_CLASS"]
    assert "execution simulator" in d7["MAX_ENGINEERING_SCOPE"]


def test_no_outcomes_no_market_07_no_protected_open_claimed():
    sprint = _sprint()
    blob = json.dumps(sprint).upper()
    assert sprint["SCIENTIFIC_OUTCOMES_COMPUTED"] is False
    assert "D7_DISCOVERY_RESULT" not in blob
    assert "CLASSIFICATION_ASSIGNED" not in sprint
    assert sprint["MARKET_07_CREATED"] is False
    assert sprint["PROTECTED_2025_OPENED"] is False
    assert sprint["PROTECTED_2026_OPENED"] is False
    assert not (REPO / "docs/research/discovery_results/D7_DISCOVERY_RESULT.json").exists()
    assert not (REPO / "docs/research/discovery_results/D8_DISCOVERY_RESULT.json").exists()
    assert not (REPO / "docs/research/MARKET_07_RESULT.json").exists()


def test_json_is_deterministic_sorted():
    for path in (POLICY_JSON, SPRINT_JSON):
        raw = path.read_text(encoding="utf-8")
        obj = json.loads(raw)
        canonical = json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        assert raw == canonical
