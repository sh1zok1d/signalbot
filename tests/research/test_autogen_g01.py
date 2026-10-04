"""AUTOGEN_G01: calendar rules, unit construction and the outcome-blind feasibility record.

Offline; no market value is read (BitMEX bar open times only in the record test).
"""

from __future__ import annotations

import ast
import datetime as dt
import json
from pathlib import Path

from scripts.research.autogen_g01 import candidates as C
from scripts.research.autogen_g01 import constants as K
from scripts.research.autogen_g01 import states as S
from scripts.research.owner_cards_r03 import windows as RW

REPO = Path(__file__).resolve().parents[2]
UTC = dt.timezone.utc


def _d(s: str) -> dt.date:
    return dt.date.fromisoformat(s)


def test_holiday_windows_wrap_the_year_and_cover_golden_week():
    for day in ("2021-12-24", "2021-12-31", "2022-01-01", "2022-01-02", "2023-10-01", "2023-10-07"):
        assert S.in_holiday_window(_d(day)), day
    for day in ("2021-12-23", "2022-01-03", "2023-09-30", "2023-10-08"):
        assert not S.in_holiday_window(_d(day)), day


def test_turn_of_month_state_days_exclude_expiry_holidays_and_out_of_surface_days():
    start, end = K.DISCOVERY_START_MS, K.DISCOVERY_END_MS
    # 2021-05: 2021-04-30 is the last Friday of April -> excluded
    assert S.tom_state_days(2021, 5, start, end) == [_d("2021-05-01"), _d("2021-05-02"), _d("2021-05-03")]
    # 2021-06: 2021-05-31 is a Monday -> included
    assert S.tom_state_days(2021, 6, start, end)[0] == _d("2021-05-31")
    # 2020-01: 2019-12-31 out of surface and in the year-end window; Jan 1-2 in the window
    assert S.tom_state_days(2020, 1, start, end) == [_d("2020-01-03")]
    # 2022-10: Sep 30 is the last Friday and Oct 1-3 are Golden Week -> no state day, unit dropped
    assert S.tom_state_days(2022, 10, start, end) == []
    assert "2022-10" not in {u["UNIT_ID"] for u in S.units_card_a("G01-A1", start, end)}
    assert S.comparator_days(2021, 6, start, end) == [_d(f"2021-06-{k:02d}") for k in range(8, 22)]


def test_card_a_units_and_standardization_keys():
    units = S.units_card_a("G01-A1", K.DISCOVERY_START_MS, K.DISCOVERY_END_MS)
    assert len(units) == 59
    for u in units:
        for w in u["STATE"] + u["COMPARATOR"]:
            assert w[1] == 1440 and w[2] in ("UTC_DAY:WD", "UTC_DAY:WE")
            assert K.DISCOVERY_START_MS <= w[0] < K.DISCOVERY_END_MS
    a3 = S.units_card_a("G01-A3", K.DISCOVERY_START_MS, K.DISCOVERY_END_MS)
    assert len(a3) == 55 and not any(u["UNIT_ID"].endswith("-12") for u in a3)
    w = a3[0]["STATE"][0]
    assert w[1] == 60 and (w[0] // K.HOUR_MS) % 24 == 23
    rep = S.units_card_a("G01-A1", K.BITMEX_START_MS, K.BITMEX_END_MS)
    assert rep[0]["UNIT_ID"] == "2017-01" and rep[-1]["UNIT_ID"] == "2019-12"


def test_card_b_eras_trading_days_and_dst():
    from scripts.research.owner_cards_r03 import data as RD
    units = S.units_card_b(K.DISCOVERY_START_MS, K.DISCOVERY_END_MS, RD.nyse_events())
    days = {d["DATE"]: u["ERA"] for u in units for d in u["DAYS"]}
    assert days["2024-01-05"] == "PRE" and days["2024-01-16"] == "POST"
    for dropped in ("2024-01-08", "2024-01-09", "2024-01-10", "2024-01-11", "2024-01-12"):
        assert dropped not in days
    assert "2024-07-04" not in days and "2024-07-03" not in days  # closure and early close
    assert all(_d(x).weekday() < 5 and x < "2025-01-01" for x in days)
    assert all(u["YEAR"] <= 2024 for u in units)
    winter = next(d for u in units for d in u["DAYS"] if d["DATE"] == "2024-01-16")
    summer = next(d for u in units for d in u["DAYS"] if d["DATE"] == "2024-07-16")
    assert dt.datetime.fromtimestamp(winter["FIX"][0] / 1000, tz=UTC).hour == 20
    assert dt.datetime.fromtimestamp(summer["FIX"][0] / 1000, tz=UTC).hour == 19
    assert [dt.datetime.fromtimestamp(w[0] / 1000, tz=UTC).hour for w in winter["ADJ"]] == [18, 19]


def test_candidate_inventory_counts_and_fields():
    body = json.loads((REPO / "docs/research/AUTOGEN_G01_CANDIDATES.json").read_text())
    assert body["MARKET_VALUES_READ"] is False
    assert body["COUNTS"] == {C.SURVIVES: 4, C.RED_TEAM: 8, C.DEDUPE: 2}
    survivors = [c for c in body["CANDIDATES"] if c["STAGE"] == C.SURVIVES]
    assert {c["ID"] for c in survivors} == {h["ID"] for h in K.HYPOTHESES}
    for c in survivors:
        for key in ("MECHANISM", "EXACT_CLAIM", "INFERENCE_CLASS", "UNIT", "EXPOSURE", "OUTCOME", "COMPARATOR", "DATA",
                    "EXPECTED_NOMINAL_N", "DEPENDENCE", "CONFOUNDERS", "PRACTICAL_BAR", "PRODUCT_RELEVANCE",
                    "PRIOR_OVERLAP", "WHY_NOT_DUPLICATE", "RED_TEAM"):
            assert c[key], (c["ID"], key)
    assert all(c["CLOSE_REASON"] for c in body["CANDIDATES"] if c["STAGE"] != C.SURVIVES)


def test_feasibility_record_closes_every_hypothesis_without_market_values():
    feas = json.loads((REPO / "docs/research/AUTOGEN_G01_FEASIBILITY.json").read_text())
    assert feas["MARKET_OUTCOMES_OPENED"] is False and feas["MARKET_VALUES_READ"] is False
    summary = feas["SUMMARY"]
    assert set(summary) == {h["ID"] for h in K.HYPOTHESES}
    assert not any(s["EXECUTABLE"] for s in summary.values())
    assert {s["STATUS"] for s in summary.values()} == {"INFORMATIONALLY_WEAK"}
    assert summary["G01-B1"]["MDE_STRESS_UNITS"] > K.MIN_MEANINGFUL_EFFECT
    assert "REPLICATION_MDE_TOO_LARGE" in summary["G01-A1"]["BLOCKERS"]
    assert K.PROSPECTIVE_B["STOPPING_RULE"]["MIN_N"] <= K.PROSPECTIVE_B["STOPPING_RULE"]["MAX_EPISODES"]


def test_feasibility_code_reads_no_market_values():
    src = (REPO / "scripts/research/autogen_g01/support.py").read_text()
    names = {n.attr for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Attribute)}
    assert "load_btc_1m" not in names and "load_bitmex_5m" not in names and "load_panel_daily" not in names
    data_src = (REPO / "scripts/research/autogen_g01/data.py").read_text()
    assert "def load_" not in data_src
    assert not (REPO / "scripts/research/autogen_g01/outcomes.py").exists()


def test_design_constants_locked():
    K.assert_locked()
    assert K.MIN_MEANINGFUL_EFFECT == 0.5 and K.DISCOVERY_END_MS == RW.date_ms(_d("2025-01-01"))


def test_closure_record_is_final_and_does_not_rescue_b1():
    decision = (REPO / "docs/research/AUTOGEN_G01_DECISION.md").read_text()
    for line in ("G01_STATUS             = CLOSED_NO_SURVIVORS", "CANDIDATES_FROZEN      = 0",
                 "CANDIDATES_EXECUTED    = 0", "MARKET_OUTCOMES_OPENED = NO",
                 "G01-B1                 = FUTURE_CANDIDATE / NATURAL_DATA_ACCUMULATION"):
        assert line in decision, line
    assert "PRE_FREEZE_DEFINITIONAL_CORRECTION" in decision and "did not rescue the hypothesis" in decision
    assert "not a claim that the high-frequency mechanism space is exhausted" in decision
    state = (REPO / "docs/CURRENT_RESEARCH_STATE.md").read_text()
    assert "\n## Autonomous research generation G01 — CLOSED_NO_SURVIVORS" in "\n" + state
    assert "`G01_STATUS = CLOSED_NO_SURVIVORS (owner-accepted)`" in state
    assert not (REPO / "docs/research/AUTOGEN_G01_PREREG.json").exists()
    assert not (REPO / "docs/research/AUTOGEN_G01_RESULT.json").exists()
