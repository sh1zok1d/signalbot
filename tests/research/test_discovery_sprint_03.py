"""Contract tests for Discovery Sprint 03 card definition (amended).

Outcome-blind. Does not load MARKET-06/CORE OHLC, does not execute
D9/D10/D11, does not rerun D7, and does not open protected 2025/2026.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
POLICY_JSON = REPO / "docs/research/HETEROGENEOUS_FAMILY_ROTATION_V2.json"
SPRINT_JSON = REPO / "docs/research/DISCOVERY_SPRINT_03.json"
MEMORY_JSON = REPO / "docs/research/MECHANISM_MEMORY_V0.json"
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
    "DATA_FEASIBILITY_CLASS",
    "NEAREST_H_PRIOR",
    "NEAREST_B2_PRIOR",
    "NEAREST_MARKET_PRIOR",
    "NEAREST_D_PRIOR",
    "WHY_NOT_NEIGHBOR_RESCUE",
)
PRIOR_FIELDS = (
    "NEAREST_H_PRIOR",
    "NEAREST_B2_PRIOR",
    "NEAREST_MARKET_PRIOR",
    "NEAREST_D_PRIOR",
    "WHY_NOT_NEIGHBOR_RESCUE",
    "WHAT_ALREADY_FAILED_NEARBY",
    "WHAT_NEW_INFORMATION_THIS_CARD_WOULD_ADD",
)


def _policy() -> dict:
    return json.loads(POLICY_JSON.read_text(encoding="utf-8"))


def _sprint() -> dict:
    return json.loads(SPRINT_JSON.read_text(encoding="utf-8"))


def _memory() -> dict:
    return json.loads(MEMORY_JSON.read_text(encoding="utf-8"))


def d9_relative_resolution(d_u: float, rp: float, rs: float) -> dict:
    """Frozen D9 algebra. Synthetic only. No market data."""

    if d_u == 0 or not math.isfinite(d_u):
        return {
            "eligible": False,
            "reason": "D_ZERO_OR_NONFINITE",
            "total_closure": None,
            "perp_resolution_share": None,
        }
    s = math.copysign(1.0, d_u)
    total_closure = -s * (rp - rs)
    if total_closure <= 0:
        return {
            "eligible": False,
            "reason": "NO_GENUINE_CLOSURE",
            "total_closure": total_closure,
            "perp_resolution_share": None,
        }
    share = (-s * rp) / total_closure
    return {
        "eligible": True,
        "reason": "GENUINE_CLOSURE",
        "total_closure": total_closure,
        "perp_resolution_share": share,
    }


def test_mechanism_memory_covers_required_history():
    memory = _memory()
    assert memory["UNIT"] == "MECHANISM_MEMORY_V0"
    assert memory["NOT_A_NEW_FRAMEWORK"] is True
    entries = memory["ENTRIES"]
    for key in (
        "H01",
        "H02",
        "H03",
        "H04",
        "H05",
        "B2-01",
        "B2-02",
        "B2-03",
        "B2-04",
        "B2-05",
        "B2-06",
        "MARKET-01",
        "MARKET-02",
        "MARKET-03",
        "MARKET-04",
        "MARKET-05",
        "MARKET-06",
        "D1",
        "D2",
        "D3",
        "D4",
        "D5",
        "D6",
        "D7",
        "D8",
    ):
        assert key in entries, key
        row = entries[key]
        for field in (
            "ID",
            "GENERATION",
            "MECHANISM",
            "INFORMATION_SOURCE",
            "FUNCTION",
            "TARGET_FAMILY",
            "STATUS_EVIDENCE_CLASS",
            "WHAT_WAS_ACTUALLY_TESTED",
            "WHAT_THE_RESULT_DEPRIORITIZES_OR_CLOSES",
            "WHAT_REMAINS_OPEN",
            "NEIGHBOR_RESCUE_WARNING",
            "DATA_STATE",
        ):
            assert row[field], f"{key}.{field}"
    assert entries["H01"]["STATUS_EVIDENCE_CLASS"].startswith("H01_KILL")
    assert memory["BATCH01_PROMOTED"] == "0 / 5"
    assert "CLOSED_NO_PROMOTION" in entries["B2-01"]["STATUS_EVIDENCE_CLASS"]
    assert "DEVELOPMENT_CONSUMED" in entries["B2-05"]["STATUS_EVIDENCE_CLASS"]
    assert "not cryptographically proven" in entries["B2-05"]["WHAT_WAS_ACTUALLY_TESTED"]
    assert entries["B2-06"]["STATUS_EVIDENCE_CLASS"] == "BLOCKED_MISSING_OBSERVABLE"
    assert "NOT count as negative" in entries["B2-06"]["WHAT_THE_RESULT_DEPRIORITIZES_OR_CLOSES"]
    assert "EXTERNAL" in entries["MARKET-03"]["STATUS_EVIDENCE_CLASS"]
    assert memory["MARKET_03_COUNTS_AS_INTERNAL_DISCOVERY"] is False
    assert "PROMISING_PROTOTYPE" in entries["D2"]["STATUS_EVIDENCE_CLASS"]
    assert "BitMEX" in entries["D2"]["STATUS_EVIDENCE_CLASS"]
    assert "PROMISING_PROTOTYPE" in entries["D7"]["STATUS_EVIDENCE_CLASS"]
    assert "NOT independently replicated" in entries["D7"]["STATUS_EVIDENCE_CLASS"]
    assert "DEFERRED_INSUFFICIENT_CONTROL_SUPPORT" in entries["D8"]["STATUS_EVIDENCE_CLASS"]
    assert "NOT NO_USEFUL_STRUCTURE" in entries["D8"]["STATUS_EVIDENCE_CLASS"]


def test_rotation_v2_selects_three_families():
    policy = _policy()
    assert policy["SELECTED_INTERNAL_CARDS"] == ["D9", "D10", "D11"]
    assert policy["SELECTED_THIS_ROTATION"] == ["D", "G", "H"]
    assert policy["FAMILY_STATUS"]["E"]["STATUS"] == "COOLDOWN_AFTER_POSITIVE"
    assert policy["FAMILY_STATUS"]["A"]["STATUS"] == "NOT_SELECTED_THIS_ROTATION"
    assert policy["FAMILY_STATUS"]["D"]["STATUS"] == "SELECTED_THIS_ROTATION"
    assert policy["FAMILY_STATUS"]["G"]["STATUS"] == "SELECTED_THIS_ROTATION"
    assert policy["FAMILY_STATUS"]["H"]["STATUS"] == "SELECTED_THIS_ROTATION"
    assert policy["FAMILY_STATUS"]["H"]["TRUE_CROSS_SECTIONAL_PANEL"] is False
    assert policy["D9_ALGEBRAIC_IDENTIFICATION_FIXED"] is True
    assert policy["SCIENTIFIC_OUTCOMES_COMPUTED"] is False
    assert policy["MARKET_07_CREATED"] is False
    assert policy["MANDATE_V1_ON_MAIN"] is True


def test_sprint_defines_three_heterogeneous_internal_cards():
    sprint = _sprint()
    assert sprint["INTERNAL_CARDS"] == ["D9", "D10", "D11"]
    assert set(sprint["CARDS"]) == {"D9", "D10", "D11"}
    assert sprint["SPRINT03_SELECTION_INCOMPLETE"] is False
    assert sprint["NEXT_UNIT"] == (
        "DISCOVERY_SPRINT_03_BATCH_FEASIBILITY_AND_OUTCOME_BLIND_IMPLEMENTATION"
    )
    families = {sprint["CARDS"][k]["FAMILY"] for k in ("D9", "D10", "D11")}
    assert families == {"H", "D", "G"}
    assert sprint["CARDS"]["D9"]["FAMILY"] == "H"
    assert sprint["CARDS"]["D10"]["FAMILY"] == "D"
    assert sprint["CARDS"]["D11"]["FAMILY"] == "G"
    assert sprint["D9_EXECUTED"] is False
    assert sprint["D10_EXECUTED"] is False
    assert sprint["D11_EXECUTED"] is False
    assert sprint["SCIENTIFIC_OUTCOMES_COMPUTED"] is False
    assert sprint["D7_RERUN_PERFORMED"] is False
    assert sprint["D8_EXECUTED"] is False
    assert sprint["MARKET_07_CREATED"] is False
    assert sprint["PROTECTED_2025_OPENED"] is False
    assert sprint["PROTECTED_2026_OPENED"] is False
    assert "heavy D7-style one-shot infrastructure" in " ".join(
        sprint["NEXT_UNIT_MUST_NOT"]
    )


def test_six_candidates_query_mechanism_memory():
    sprint = _sprint()
    cands = sprint["CANDIDATES"]
    assert len(cands) >= 6
    selected = [
        key for key, row in cands.items() if row["SELECTION_STATUS"].startswith("SELECTED")
    ]
    assert len(selected) == 3
    families = {cands[key]["FAMILY"] for key in selected}
    assert len(families) == 3
    h_only = all(cands[key]["FAMILY"] == "H" for key in selected)
    assert h_only is False
    for row in cands.values():
        for field in PRIOR_FIELDS:
            assert row[field], field


def test_selected_cards_record_nearest_priors_and_contract():
    sprint = _sprint()
    for disc_id in ("D9", "D10", "D11"):
        card = sprint["CARDS"][disc_id]
        for field in CONTRACT_FIELDS:
            assert field in card, f"{disc_id}.{field}"
            assert card[field], f"{disc_id}.{field}"
        for field in PRIOR_FIELDS:
            assert card[field], f"{disc_id}.{field}"


def test_d9_estimand_is_relative_resolution_not_common_mode_imbalance():
    d9 = _sprint()["CARDS"]["D9"]
    assert d9["CHOSEN_ESTIMAND"] == "RELATIVE_RESOLUTION_ATTRIBUTION"
    assert d9["PRIMARY_TARGET"] == "PERP_RESOLUTION_SHARE"
    assert d9["OLD_RESOLUTION_IMBALANCE_REJECTED"] is True
    assert "-s*(rp+rs)" in d9["OLD_RESOLUTION_IMBALANCE_ALGEBRA"]
    assert d9["ALGEBRA"]["TOTAL_CLOSURE"] == "-s * (rp - rs)"
    assert d9["ALGEBRA"]["DELTA_D"] == "rp - rs"
    assert "INELIGIBLE" in d9["ALGEBRA"]["COMMON_MODE_RP_EQ_RS"]
    assert "24h MAE" not in d9["PRIMARY_TARGET"]
    assert "FUTURE_CONSENSUS" in d9["REJECTED_ESTIMAND_B"]


def test_d9_common_mode_and_attribution_invariants():
    # 1. rp == rs: dislocation unchanged; must not claim a closer.
    out = d9_relative_resolution(d_u=0.01, rp=0.004, rs=0.004)
    assert out["eligible"] is False
    assert out["perp_resolution_share"] is None
    assert math.isclose(out["total_closure"], 0.0)

    # 2. D>0, rp<0, rs==0: perp-only convergence.
    out = d9_relative_resolution(d_u=0.02, rp=-0.005, rs=0.0)
    assert out["eligible"] is True
    assert math.isclose(out["perp_resolution_share"], 1.0)

    # 3. D>0, rp==0, rs>0: spot-only convergence.
    out = d9_relative_resolution(d_u=0.02, rp=0.0, rs=0.005)
    assert out["eligible"] is True
    assert math.isclose(out["perp_resolution_share"], 0.0)

    # 4. D>0, rp==-a, rs==+a: symmetric convergence.
    out = d9_relative_resolution(d_u=0.02, rp=-0.003, rs=0.003)
    assert out["eligible"] is True
    assert math.isclose(out["perp_resolution_share"], 0.5)

    # 5. widening must never silently become positive resolution.
    out = d9_relative_resolution(d_u=0.02, rp=0.004, rs=0.0)
    assert out["eligible"] is False
    assert out["perp_resolution_share"] is None
    assert out["total_closure"] < 0

    both_widen = d9_relative_resolution(d_u=0.02, rp=0.003, rs=-0.003)
    assert both_widen["eligible"] is False
    assert both_widen["perp_resolution_share"] is None


def test_old_imbalance_is_not_the_primary_and_fails_common_mode():
    """Document the rejected -s*(rp+rs) functional without using it."""

    s, rp, rs = 1.0, 0.004, 0.004
    old_imbalance = -s * (rp + rs)
    new = d9_relative_resolution(d_u=0.01, rp=rp, rs=rs)
    assert old_imbalance != 0
    assert new["eligible"] is False
    assert _sprint()["CARDS"]["D9"]["PRIMARY_TARGET"] != "RESOLUTION_IMBALANCE"


def test_no_outcomes_no_implementations():
    sprint = _sprint()
    blob = json.dumps(sprint).upper()
    assert sprint["SCIENTIFIC_OUTCOMES_COMPUTED"] is False
    assert "CLASSIFICATION_ASSIGNED" not in sprint
    assert not list((REPO / "scripts/research").glob("*sprint_03*"))
    assert not (
        REPO / "docs/research/discovery_results/D9_DISCOVERY_RESULT.json"
    ).exists()
    assert not (REPO / "docs/research/MARKET_07_RESULT.json").exists()
    assert "D9_DISCOVERY_RESULT" not in blob


def test_json_is_deterministic_sorted():
    for path in (POLICY_JSON, SPRINT_JSON, MEMORY_JSON):
        raw = path.read_text(encoding="utf-8")
        obj = json.loads(raw)
        canonical = json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        assert raw == canonical, path


def test_routing_docs_point_at_batch_next_unit():
    next_unit = (
        "DISCOVERY_SPRINT_03_BATCH_FEASIBILITY_AND_OUTCOME_BLIND_IMPLEMENTATION"
    )
    stale = "DISCOVERY_SPRINT_03_D9_FEASIBILITY_AND_OUTCOME_BLIND_IMPLEMENTATION"
    for rel in (
        "docs/CURRENT_RESEARCH_STATE.md",
        "docs/RESEARCH_ROADMAP.md",
        "docs/PROJECT_STATUS.md",
        "docs/DOCUMENTATION_INDEX.md",
    ):
        text = (REPO / rel).read_text(encoding="utf-8")
        assert next_unit in text, rel
        assert stale not in text, rel
    index = (REPO / "docs/DOCUMENTATION_INDEX.md").read_text(encoding="utf-8")
    assert "MECHANISM_MEMORY_V0" in index
    state = (REPO / "docs/CURRENT_RESEARCH_STATE.md").read_text(encoding="utf-8")
    assert "DISCOVERY_SPRINT_03_INTERNAL_CARDS = 3" in state
    assert "RELATIVE_RESOLUTION_ATTRIBUTION" in state
