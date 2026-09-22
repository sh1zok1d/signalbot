"""Outcome-blind implementation tests for Discovery Sprint 04.

Synthetic/adversarial only except identity/guard tests that do not compute
scientific target values. Real D12 A_k / D13 IC/returns are never inspected.
"""

from __future__ import annotations

import json
import math
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest

from scripts.research.discovery_sprint_04 import common as C
from scripts.research.discovery_sprint_04 import d12 as D12
from scripts.research.discovery_sprint_04 import d13 as D13
from scripts.research.discovery_sprint_04 import d13_acquire as ACQ
from scripts.research.discovery_sprint_04 import d13_exclusions as EX
from scripts.research.discovery_sprint_04 import d13_panel as P
from scripts.research.discovery_sprint_04 import evaluate as E
from scripts.research.discovery_sprint_04.d13_terminal_mark import (
    DEFERRED_TERMINAL_MARK_UNRESOLVED,
    FULL_WEEK,
    INTRAWEEK_FINAL_CLOSE,
    NO_POST_T_CLOSE,
    D13TerminalMarkUnresolved,
    assert_terminal_marks_resolved,
    no_post_t_close_selected_n,
    terminal_mark,
)

REPO = Path(__file__).resolve().parents[2]
SPRINT_JSON = REPO / "docs/research/DISCOVERY_SPRINT_04.json"
FREEZE_JSON = REPO / "docs/research/DISCOVERY_SPRINT_04_IMPLEMENTATION_FREEZE.json"
FEE_PIN = REPO / C.D13_FEE_AUTHORITY_REL


def test_import_does_not_read_market_data_and_execution_is_false():
    assert C.EXECUTION_AUTHORIZED is False
    assert C.UNIT == "DISCOVERY_SPRINT_04_BATCH_FEASIBILITY_AND_OUTCOME_BLIND_IMPLEMENTATION"


def test_execution_guard_refuses_real_outcomes():
    with pytest.raises(C.RealScientificOutcomeForbidden):
        E.evaluate_d12_real()
    with pytest.raises(C.RealScientificOutcomeForbidden):
        E.evaluate_d13_real()
    with pytest.raises(C.RealScientificOutcomeForbidden):
        E.evaluate_supplied_arrays("D12", support={"IDENTITY_OK": True}, us_a=[0.1])
    with pytest.raises(C.RealScientificOutcomeForbidden):
        E.main()
    with pytest.raises(C.RealScientificOutcomeForbidden):
        P.load_price_panel_real()


def test_flags_remain_unexecuted():
    sprint = json.loads(SPRINT_JSON.read_text(encoding="utf-8"))
    for key in (
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
    ):
        assert sprint[key] is False
    if FREEZE_JSON.is_file():
        freeze = json.loads(FREEZE_JSON.read_text(encoding="utf-8"))
        for key in (
            "SCIENTIFIC_OUTCOMES_COMPUTED",
            "D12_EXECUTED",
            "D13_EXECUTED",
            "EXECUTION_AUTHORIZED",
            "PROTECTED_2025_OPENED",
            "PROTECTED_2026_OPENED",
        ):
            assert freeze[key] is False
    assert not (REPO / "docs/research/MARKET_07_RESULT.json").exists()
    # Canonical D12/D13 RESULT artifacts are persisted by the one-shot
    # execution unit. The freeze/selection JSON themselves remain unexecuted.


def test_d12_weekdays_identical_for_real_and_pseudo():
    us = C.us_transition_dates()
    eu = C.eu_transition_dates()
    for sunday in us + eu + D12.pseudo_sundays(us, eu)[:12]:
        before, after = D12.assert_weekday_matched_windows(sunday)
        assert [d.weekday() for d in before] == [0, 1, 2, 3, 4, 5]
        assert [d.weekday() for d in after] == [0, 1, 2, 3, 4, 5]
        assert sunday not in before and sunday not in after


def test_d12_us_dst_changes_and_eu_constant():
    for sunday in C.us_transition_dates():
        before, after = C.window_days(sunday)
        assert C.us_in_dst(before[-1]) != C.us_in_dst(after[0])
        assert len({C.eu_in_dst(d) for d in before + after}) == 1


def test_d12_predicted_shift_sign():
    assert C.predicted_delta(date(2020, 3, 8), kind="US") == 1
    assert C.predicted_delta(date(2020, 11, 1), kind="US") == -1
    assert C.predicted_delta(date(2021, 3, 14), kind="US") == 1
    assert C.predicted_delta(date(2021, 11, 7), kind="US") == -1


def test_d12_shift_distance_matches_frozen_algebra():
    before = np.zeros(24)
    after = np.zeros(24)
    before[10] = 1.0
    after[9] = 1.0
    d0 = D12.shifted_distance(after, before, 0)
    d1 = D12.shifted_distance(after, before, 1)
    assert d1 < d0
    a = D12.clock_anchoring_index(after, before, 1)
    assert a > 0
    # fall: after should match before shifted by -1
    after_fall = np.zeros(24)
    after_fall[11] = 1.0
    a_fall = D12.clock_anchoring_index(after_fall, before, -1)
    assert a_fall > 0


def test_d12_missing_day_equal_weights_not_zero_filled():
    p1 = [1.0] + [0.0] * 23
    p2 = [0.0, 1.0] + [0.0] * 22
    mean_two = D12.mean_profile([p1, p2])
    with pytest.raises(C.Sprint04IntegrityError):
        D12.normalized_profile([0.0] * 24)
    assert math.isclose(float(mean_two[0]), 0.5)
    assert math.isclose(float(mean_two[1]), 0.5)


def test_d12_classification_precedence():
    summary = D12.evaluate_d12_scientific(
        [0.2] * 8,
        [1, -1] * 4,
        [2020, 2021, 2022, 2023, 2024, 2020, 2021, 2022],
        [0.0] * 50,
        [0.0] * 50,
        support={"IDENTITY_OK": False, "SUPPORT_PASS": True},
    )
    assert summary["CLASSIFICATION"] == "INVALID_DISCOVERY"
    summary = D12.evaluate_d12_scientific(
        [0.2] * 8,
        [1, -1] * 4,
        [2020] * 8,
        [0.0] * 50,
        [0.0] * 50,
        support={"IDENTITY_OK": True, "SUPPORT_PASS": False},
    )
    assert summary["CLASSIFICATION"] == "INCONCLUSIVE_DISCOVERY"


def test_d12_protected_year_refused():
    with pytest.raises(C.ProtectedYearRefused):
        C.assert_openable(Path("canonical/1m/monthly/2025-01.parquet"))
    with pytest.raises(C.ProtectedYearRefused):
        C.assert_openable(Path("/tmp/2026-03/x.parquet"))
    with pytest.raises(ACQ.ProtectedYearRefused):
        ACQ.refuse_protected_key("data/spot/monthly/klines/BTCUSDT/1d/BTCUSDT-1d-2025-01.zip")
    with pytest.raises(ACQ.ProtectedYearRefused):
        ACQ.refuse_protected_key("data/spot/monthly/klines/BTCUSDT/1d/BTCUSDT-1d-2026-06.zip")


def test_d12_feasibility_census_does_not_need_profiles():
    flags = {date(2020, 1, 1) + timedelta(days=i): True for i in range(366 * 5)}
    census = D12.census_complete_days(flags)
    assert census["US_TRANSITIONS_TOTAL"] == 10
    assert census["US_TRANSITIONS_FEASIBLE"] == 10
    assert census["PSEUDO_SUNDAY_N"] >= 100
    assert "MEAN_A" not in census
    assert "US_A" not in census
    assert census["RANDOM_SEED"] == 20260922196


def test_d12_mc_is_one_sided_and_deterministic():
    plus = [0.01] * 40
    minus = [-0.01] * 40
    a = [0.2] * 5 + [0.2] * 5
    s1 = D12.evaluate_d12_scientific(
        a,
        [1] * 5 + [-1] * 5,
        [2020, 2021, 2022, 2023, 2024] * 2,
        plus,
        minus,
        support={"IDENTITY_OK": True, "SUPPORT_PASS": True},
    )
    s2 = D12.evaluate_d12_scientific(
        a,
        [1] * 5 + [-1] * 5,
        [2020, 2021, 2022, 2023, 2024] * 2,
        plus,
        minus,
        support={"IDENTITY_OK": True, "SUPPORT_PASS": True},
    )
    assert s1["MC_P"] == s2["MC_P"]
    assert s1["RANDOM_SEED"] == C.D12_RANDOM_SEED


def test_d13_momentum_reversal_and_null_ic():
    n = 40
    form = np.linspace(-1, 1, n)
    hold_mom = form.copy()
    hold_rev = -form
    ic_null = D13.spearman_rank_ic(form, np.random.default_rng(0).permutation(form))
    assert D13.spearman_rank_ic(form, hold_mom) > 0.99
    assert D13.spearman_rank_ic(form, hold_rev) < -0.99
    assert abs(ic_null) < 0.4


def test_d13_sign_is_reported_not_chosen():
    form = np.linspace(-1, 1, 50)
    hold_rev = -form
    raw = D13.top_minus_bottom_spread(form, hold_rev)
    pooled = D13.spearman_rank_ic(form, hold_rev)
    signed = D13.signed_practical_spread(raw, pooled)
    # reversal: raw Q5-Q1 is negative; signed uses pooled sign so spread is positive
    assert pooled < 0
    assert raw < 0
    assert signed > 0
    both = max(raw, -raw)
    chosen = both
    assert signed == pytest.approx(-raw)
    assert signed != chosen or signed == -raw


def test_d13_does_not_take_max_of_momentum_and_reversal():
    raw = 0.02
    pooled_pos = 0.1
    pooled_neg = -0.1
    assert D13.signed_practical_spread(raw, pooled_pos) == pytest.approx(0.02)
    assert D13.signed_practical_spread(raw, pooled_neg) == pytest.approx(-0.02)
    assert D13.signed_practical_spread(-0.03, pooled_neg) == pytest.approx(0.03)


def test_d13_exclusions_name_only():
    enumerated = ["BTCUSDT", "ETHUSDT", "USDCUSDT", "BUSDUSDT", "BTCUPUSDT", "ETHBULLUSDT", "BULLUSDT"]
    frozen = EX.freeze_exclusion_lists(enumerated)
    assert "USDCUSDT" in frozen["EXCLUDED_SYMBOLS"]
    assert "BUSDUSDT" in frozen["EXCLUDED_SYMBOLS"]
    assert frozen["EXCLUDED_SYMBOLS"]["BTCUPUSDT"] == "LEVERAGED_TOKEN"
    assert frozen["EXCLUDED_SYMBOLS"]["ETHBULLUSDT"] == "LEVERAGED_TOKEN"
    assert "BULLUSDT" not in frozen["EXCLUDED_SYMBOLS"]
    assert "BTCUSDT" not in frozen["EXCLUDED_SYMBOLS"]


def test_d13_n_from_counts_not_returns():
    counts = [80, 90, 120, 40]
    assert D13.n_from_eligible_counts(counts) == 40
    assert D13.n_from_eligible_counts([150, 200]) == 100
    mondays = D13.decision_mondays()
    assert mondays[0] == date(2020, 2, 3)
    assert mondays[-1] == date(2024, 12, 23)
    assert all(d.weekday() == 0 for d in mondays)
    assert len(mondays) >= 200


def test_d13_liquidity_uses_strictly_prior_28d():
    t = C.date_to_ms(date(2020, 3, 2))
    quotes = {}
    for k in range(40):
        quotes[t - k * C.DAY_MS] = float(k)
    quotes[t] = 9999.0
    quotes[t + C.DAY_MS] = 9999.0
    total = D13.trailing_quote_volume(quotes, t)
    # includes t-28d .. t-1d, excludes t and after
    expected = sum(float(k) for k in range(1, 29))
    assert math.isclose(total, expected)


def test_d13_point_in_time_eligibility_and_no_survival_to_t7():
    t = C.date_to_ms(date(2020, 3, 2))
    days = {}
    first = t - 40 * C.DAY_MS
    for k in range(40):
        open_ms = first + k * C.DAY_MS
        days[open_ms] = P.PresenceDay(open_ms, 1.0, True)
    # missing T+7 survival must not affect eligibility at T
    assert D13.listing_age_ok(first, t)
    assert D13.completeness_ok({ms: True for ms in days}, t)
    assert P.eligible_at_t("AAAUSDT", t, days, {})
    assert P.no_post_t_from_presence(days, t) is True  # no holding-week candles
    # adding holding-week candles does not change eligibility
    holding = dict(days)
    holding[t] = P.PresenceDay(t, 1.0, True)
    assert P.eligible_at_t("AAAUSDT", t, days, {}) == P.eligible_at_t("AAAUSDT", t, holding, {})


def test_d13_terminal_mark_intraweek_and_no_post_and_relisting():
    t = C.date_to_ms(date(2020, 3, 2))
    entry = t - C.DAY_MS
    closes = {entry: 10.0}
    mark = terminal_mark("XUSDT", t, closes)
    assert mark.status == NO_POST_T_CLOSE
    assert no_post_t_close_selected_n([mark]) == 1
    with pytest.raises(D13TerminalMarkUnresolved):
        assert_terminal_marks_resolved([mark])
    # intraweek last close
    closes_mid = {entry: 10.0, t + 2 * C.DAY_MS: 11.0}
    mid = terminal_mark("XUSDT", t, closes_mid)
    assert mid.status == INTRAWEEK_FINAL_CLOSE
    assert mid.terminal_close == 11.0
    full = terminal_mark("XUSDT", t, {entry: 10.0, t + 6 * C.DAY_MS: 12.0})
    assert full.status == FULL_WEEK
    # later relisting after holding week is ignored
    leaked = {entry: 10.0, t + 10 * C.DAY_MS: 99.0}
    leak_mark = terminal_mark("XUSDT", t, leaked)
    assert leak_mark.status == NO_POST_T_CLOSE
    D13.assert_no_relisting_leakage([t + 10 * C.DAY_MS], leak_mark.terminal_candle_open_ms, t)


def test_d13_classification_precedence_and_deferred_terminal():
    weekly = [0.1] * 200
    years = [2020] * 40 + [2021] * 40 + [2022] * 40 + [2023] * 40 + [2024] * 40
    spreads = [0.01] * 200
    s = D13.evaluate_d13_scientific(
        weekly,
        years,
        spreads,
        support={"IDENTITY_OK": False, "SUPPORT_PASS": True},
        n=100,
        no_post_t_close_selected_n=0,
        pinned_taker_fee=0.001,
    )
    assert s["CLASSIFICATION"] == "INVALID_DISCOVERY"
    s = D13.evaluate_d13_scientific(
        weekly,
        years,
        spreads,
        support={"IDENTITY_OK": True, "SUPPORT_PASS": True},
        n=100,
        no_post_t_close_selected_n=3,
        pinned_taker_fee=0.001,
    )
    assert s["STATUS"] == DEFERRED_TERMINAL_MARK_UNRESOLVED
    assert s["CLASSIFICATION"] == "INCONCLUSIVE_DISCOVERY"


def test_d13_mc_deterministic_and_limitation_recorded():
    weekly = [0.05] * 200
    years = ([2020, 2021, 2022, 2023, 2024] * 40)
    spreads = [0.01] * 200
    a = D13.evaluate_d13_scientific(
        weekly,
        years,
        spreads,
        support={"IDENTITY_OK": True, "SUPPORT_PASS": True},
        n=40,
        no_post_t_close_selected_n=0,
        pinned_taker_fee=0.001,
    )
    b = D13.evaluate_d13_scientific(
        weekly,
        years,
        spreads,
        support={"IDENTITY_OK": True, "SUPPORT_PASS": True},
        n=40,
        no_post_t_close_selected_n=0,
        pinned_taker_fee=0.001,
    )
    assert a["MC_P"] == b["MC_P"]
    assert a["RANDOM_SEED"] == C.D13_RANDOM_SEED
    assert "block bootstrap" in a["TEMPORAL_DEPENDENCE_LIMITATION"]


def test_d13_protected_year_on_timestamps_and_months():
    with pytest.raises(C.ProtectedYearRefused):
        D13.refuse_protected_year_timestamp(C.PROTECTED_START_MS)
    assert ACQ.month_allowed("2024-12")
    assert not ACQ.month_allowed("2025-01")
    assert not ACQ.month_allowed("2026-01")
    assert ACQ.month_allowed("2019-12")
    assert not ACQ.month_allowed("2019-11")
    # rare archive microseconds normalize to ms inside legal 2024
    assert P.normalize_open_ms(1730160000000000) == 1730160000000
    with pytest.raises(C.ProtectedYearRefused):
        P.normalize_open_ms(C.PROTECTED_START_MS * 1000)


def test_d13_fee_pin_is_first_party_regular_user():
    pin = json.loads(FEE_PIN.read_text(encoding="utf-8"))
    html = (REPO / pin["HTML_REL"]).read_bytes()
    assert C.sha256_bytes(html) == pin["HTML_SHA256"]
    text = html.decode("utf-8")
    assert pin["SOURCE_HOST"] == "www.binance.info"
    assert pin["TIER"] == "Regular User"
    assert pin["VIP_NOT_USED"] is True
    assert pin["BNB_DISCOUNT_NOT_USED"] is True
    assert pin["PINNED_TAKER_FEE"] == 0.001
    assert pin["FRICTION_FLOOR"] == 0.004
    assert "0.100% / 0.100%" in text
    assert C.D13_PINNED_TAKER_FEE == 0.001
    assert C.D13_FRICTION_FLOOR == 0.004


def test_d13_seeds_frozen_before_outcomes():
    assert C.D12_RANDOM_SEED == 20260922196
    assert C.D13_RANDOM_SEED == 20260922197


def test_implementation_freeze_binds_hashes_and_forbids_execution():
    freeze = json.loads(FREEZE_JSON.read_text(encoding="utf-8"))
    assert freeze["EXECUTION_AUTHORIZED"] is False
    assert freeze["SCIENTIFIC_OUTCOMES_COMPUTED"] is False
    assert freeze["D12_EXECUTED"] is False
    assert freeze["D13_EXECUTED"] is False
    assert freeze["D12_STATUS"] == "OUTCOME_BLIND_IMPLEMENTATION_READY"
    assert freeze["D13_STATUS"] == "OUTCOME_BLIND_IMPLEMENTATION_READY"
    assert freeze["D13_N"] == 82
    assert freeze["D13_NO_POST_T_CLOSE_SELECTED_N"] == 0
    assert freeze["NEXT_UNIT"] == "DISCOVERY_SPRINT_04_D12_D13_ONE_SHOT_SCIENTIFIC_EXECUTION_DECISION"
    current = C.implementation_hashes(REPO)
    assert freeze["IMPLEMENTATION_HASHES"] == current
    for finding in freeze["RED_TEAM"].values():
        assert finding["STATUS"] in {
            "CONFIRMED",
            "NOT_CONFIRMED",
            "CONFIRMED_AND_FIXED_PRE_OUTCOME",
        }
    assert freeze["RED_TEAM"]["F20"]["STATUS"] == "CONFIRMED_AND_FIXED_PRE_OUTCOME"
    assert freeze["F20_STATUS"] == "CONFIRMED_AND_FIXED_PRE_OUTCOME"
    assert freeze["D13_RUNTIME_FILE_AUTHORITY"] == "SNAPSHOT_BOUND_OBJECT_LEDGER"
    assert freeze["DATA_DURABILITY"]["D13_INDEX_LEDGER_EXACT_SET_VERIFIED"] is True



def test_d12_pseudo_uses_same_window_helper_as_real():
    sunday = date(2020, 1, 12)
    b1, a1 = C.window_days(sunday)
    b2, a2 = D12.assert_weekday_matched_windows(sunday)
    assert b1 == b2 and a1 == a2
