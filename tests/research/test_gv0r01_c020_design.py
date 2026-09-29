"""Outcome-blind C020 design. No BTC price or volume is read."""

import datetime as dt
import math

from scripts.research.gv0r01_c020_design import (
    ALPHA,
    BASE_LOG_VOLUME_SD,
    CONTROL_WINDOW_WEEKS,
    EXECUTION_MDE_THRESHOLD,
    EXPECTED_DIGESTS,
    LEGAL_FIRST,
    LEGAL_LAST,
    NULL_DRAWS,
    POWER_REPS,
    POWER_SEED,
    STRESS_LOG_VOLUME_SD,
    TARGET_POWER,
    UNRESOLVED_OPM_DATE,
    build_calendar,
    CN_DIR,
    load_json,
    simulate_power,
    us_session_utc,
    utc_offset_hours,
    OUT_JSON,
)

PRIMARY_DATES = [
    "2020-01-01", "2020-01-20", "2020-02-17", "2020-04-10", "2020-05-25",
    "2020-07-03", "2020-09-07", "2020-11-26", "2020-12-25", "2021-01-01",
    "2021-01-18", "2021-02-15", "2021-04-02", "2021-05-31", "2021-07-05",
    "2021-09-06", "2021-11-25", "2021-12-24", "2022-01-17", "2022-02-21",
    "2022-04-15", "2022-05-30", "2022-06-20", "2022-07-04", "2022-09-05",
    "2022-11-24", "2022-12-26", "2023-01-02", "2023-01-16", "2023-02-20",
    "2023-04-07", "2023-05-29", "2023-06-19", "2023-07-04", "2023-09-04",
    "2023-11-23", "2023-12-25", "2024-01-01", "2024-01-15", "2024-02-19",
    "2024-03-29", "2024-05-27", "2024-06-19", "2024-07-04", "2024-09-02",
    "2024-11-28", "2024-12-25",
]


def test_pinned_digests_and_primary_closures():
    calendar = build_calendar()
    assert calendar["DIGESTS"] == EXPECTED_DIGESTS
    assert [pair["EVENT_DATE"] for pair in calendar["COVERED"]] == PRIMARY_DATES
    assert len(PRIMARY_DATES) == 47
    assert calendar["UNRESOLVED_NYSE"] == [{
        "EVENT_ID": "NYSE:2021:OTHER:NONE:Juneteenth_National_Independence_Day",
        "EVENT_TYPE": "OTHER",
        "EVENT_DATE": None,
    }]
    assert "2021-06-18" not in PRIMARY_DATES
    assert "2021-06-19" not in PRIMARY_DATES


def test_early_closes_and_china_workdays_stay_out_of_the_lead_arm():
    calendar = build_calendar()
    dates = set(PRIMARY_DATES)
    assert len(calendar["EARLY_CLOSE_DATES"]) == 9
    assert dates.isdisjoint(calendar["EARLY_CLOSE_DATES"])
    design = load_json(OUT_JSON)
    controls = {day for pair in design["PRIMARY_PAIRS"] for day in pair["CONTROL_DATES"]}
    assert controls.isdisjoint(dates)
    assert controls.isdisjoint(set(calendar["EARLY_CLOSE_DATES"]))
    rows = load_json(CN_DIR / "EVENTS.json")
    work = {row["EVENT_DATE"] for row in rows if row["EVENT_TYPE"] == "COMPENSATING_WORKING"}
    off = {row["EVENT_DATE"] for row in rows if row["EVENT_TYPE"] == "NON_WORKING"}
    assert work.isdisjoint(off)
    assert "2020-01-19" in work
    assert controls.isdisjoint(work)
    assert controls.isdisjoint(off)
    assert dates.isdisjoint(work)


def test_opm_juneteenth_is_not_a_primary_or_f3_event():
    design = load_json(OUT_JSON)
    f3_dates = {row["OBSERVED_DATE"] for row in design["F3_EVENTS"]}
    assert UNRESOLVED_OPM_DATE not in f3_dates
    assert UNRESOLVED_OPM_DATE not in design["PRIMARY_EVENT_DATES"]
    assert design["F3_EVENT_COUNT"] == len(design["F3_EVENTS"]) == 11
    assert "not a primary exclusion" in design["CONTROL_CONTAMINATION_RULE"]


def test_session_bounds_follow_statutory_dst():
    calendar = build_calendar()
    transitions = {
        int(year): (dt.date.fromisoformat(pair[0]), dt.date.fromisoformat(pair[1]))
        for year, pair in calendar["TRANSITIONS"].items()
    }
    assert utc_offset_hours(dt.date(2020, 1, 1), transitions) == -5
    assert utc_offset_hours(dt.date(2020, 7, 3), transitions) == -4
    assert us_session_utc(dt.date(2020, 1, 1), transitions) == ("2020-01-01T14:30:00Z", "2020-01-01T21:00:00Z")
    assert us_session_utc(dt.date(2020, 7, 3), transitions) == ("2020-07-03T13:30:00Z", "2020-07-03T20:00:00Z")
    # Spring-forward Sunday 2020-03-08 is already EDT at 09:30. Fall-back Sunday is EST at 09:30.
    assert us_session_utc(dt.date(2020, 3, 8), transitions)[0] == "2020-03-08T13:30:00Z"
    assert us_session_utc(dt.date(2020, 11, 1), transitions)[0] == "2020-11-01T14:30:00Z"
    for pair in calendar["COVERED"]:
        assert pair["US_SESSION_UTC_START"] < pair["US_SESSION_UTC_END"]
        assert pair["US_SESSION_UTC_START"].startswith(pair["EVENT_DATE"])


def test_controls_match_and_do_not_reuse_a_redraw_seed():
    calendar = build_calendar()
    again = build_calendar()
    assert calendar["PAIRS"] == again["PAIRS"]
    assert calendar["SUPPORT"] == again["SUPPORT"]
    for pair in calendar["COVERED"]:
        event = dt.date.fromisoformat(pair["EVENT_DATE"])
        assert pair["CONTROL_DATES"]
        assert len(pair["CONTROL_DATES"]) <= 4
        for iso in pair["CONTROL_DATES"]:
            control = dt.date.fromisoformat(iso)
            assert control.weekday() == event.weekday()
            assert abs((control - event).days) in {7, 14}
            assert LEGAL_FIRST <= control <= LEGAL_LAST
    design = load_json(OUT_JSON)
    assert design["CONTROL_SELECTION_SEED"] is None
    assert design["CONTROL_WINDOW_WEEKS_PRIMARY"] == CONTROL_WINDOW_WEEKS == 2
    assert design["CONTROL_REUSE_COUNT"] == 13
    assert design["UNIQUE_CONTROL_DAYS"] == 143


def test_inference_support_and_frozen_bar():
    calendar = build_calendar()
    design = load_json(OUT_JSON)
    assert design["GLOBAL_INFERENCE_VALIDITY_STATUS"] == "PASS"
    assert design["SIDEDNESS"] == "TWO_SIDED"
    assert design["ALPHA"] == ALPHA == 0.05
    assert design["ALPHA_ATTAINABLE"] is True
    assert calendar["MIN_P"] <= ALPHA
    assert design["MIN_ATTAINABLE_EXACT_P"] == calendar["MIN_P"]
    assert design["PRIMARY_SUPPORT_SIZE"] == str(calendar["SUPPORT"])
    assert design["PRIMARY_LABEL_ORBIT_SIZE"] == str(calendar["SUPPORT"])
    assert design["MONTE_CARLO_ESTIMATION_FLOOR"] == 1.0 / (1.0 + NULL_DRAWS)
    assert design["DEPENDENCE_GRAPH_NODES"] == 47
    assert design["DEPENDENCE_GRAPH_EDGES"] == 12
    assert design["DEPENDENCE_GRAPH_COMPONENTS"] == 37
    assert design["MAX_COMPONENT_SIZE"] == 3
    assert EXECUTION_MDE_THRESHOLD == math.log(0.90)
    assert design["EXECUTION_MDE_THRESHOLD"] == EXECUTION_MDE_THRESHOLD
    assert design["TARGET_POWER"] == TARGET_POWER == 0.80
    names = [row["NAME"] for row in design["FALSIFIERS"]]
    assert names == ["F1_PSEUDO_HOLIDAY_NULL", "F2_YEARLY_SIGN_CONSISTENCY", "F3_NYSE_OPEN_FEDERAL_HOLIDAYS"]
    assert design["FALSIFIERS"][0]["POWER_CALIBRATED"] is True
    assert design["FALSIFIERS"][1]["POWER_CALIBRATED"] is False
    assert design["FALSIFIERS"][2]["POWER_CALIBRATED"] is False
    assert design["CHINA_EXTENSION"] == "NON_DECISIVE"
    assert design["EARLY_CLOSE_ARM"] == "NON_DECISIVE"
    assert design["PRIMARY_ENDPOINT"].startswith("mean over covered")
    assert "log(session_share_event / mean" in design["SHARE_TRANSFORMATION"]


def test_market_boundary_and_gate():
    design = load_json(OUT_JSON)
    assert design["BTC_PRICE_VALUES_OPENED"] is False
    assert design["BTC_VOLUME_VALUES_OPENED"] is False
    assert design["MARKET_DATA_OPENED_FOR_C020"] is False
    assert design["MARKET_OUTCOMES_COMPUTED"] is False
    assert design["C020_PRIMARY_TEST_EXECUTED"] is False
    assert design["PROTECTED_2025_VALUES_OPENED"] is False
    assert design["PROTECTED_2026_VALUES_OPENED"] is False
    assert design["C012_C004_OUTCOMES_USED"] is False
    assert design["OUTCOME_BLIND_GATE_RESULT"] == "EXECUTION_INFORMATIONALLY_WEAK"
    assert design["NEXT_UNIT"] == "NO_C020_EXECUTION_AUTHORIZED"
    assert all(2020 <= int(day[:4]) <= 2024 for day in design["PRIMARY_EVENT_DATES"])
    assert design["POWER_SIMULATION_PERFORMED"] is True
    assert design["NULL_REJECTION_RATE"] == 0.055
    stress_at_bar = next(
        row for row in design["POWER_CURVE"]["STRESS"]
        if abs(row["NOISE_FREE_LOG_SHARE_DISPLACEMENT"] - EXECUTION_MDE_THRESHOLD) < 1e-12
    )
    assert stress_at_bar["POWER"] == 0.4
    assert stress_at_bar["POWER"] < TARGET_POWER


def test_power_reproducibility(monkeypatch):
    import scripts.research.gv0r01_c020_design as mod
    calendar = build_calendar()
    official = simulate_power(calendar)
    written = load_json(OUT_JSON)
    assert official["BASE"] == written["POWER"]["BASE"]
    assert official["STRESS"] == written["POWER"]["STRESS"]
    monkeypatch.setattr(mod, "POWER_REPS", 2)
    monkeypatch.setattr(mod, "NULL_DRAWS", 50)
    first = simulate_power(calendar)
    second = simulate_power(calendar)
    assert first == second
    assert POWER_SEED == 20020
    assert POWER_REPS == 200
    assert BASE_LOG_VOLUME_SD == 0.25
    assert STRESS_LOG_VOLUME_SD == 0.50
    written = load_json(OUT_JSON)
    assert written["POWER"]["NULL_REJECTION_BASE"] == 0.055
    assert written["POWER"]["BASE"][2]["POWER"] == 0.79
