"""Synthetic checks for the formation-width evaluator. No historical panel is opened."""

from __future__ import annotations

import math

import numpy as np
import pytest

from scripts.research.formation_width_regime_v1 import amendment_a1 as A1
from scripts.research.formation_width_regime_v1 import amendment_a2 as A2
from scripts.research.formation_width_regime_v1 import constants as K
from scripts.research.formation_width_regime_v1 import evaluate as ev
from scripts.research.opening_range_object_v1 import constants as PARENT

FORM = 48
T0 = 1577750400000  # 2019-12-31T00:00:00Z


def _paint(high, low, close, day: int, level_high: float, level_low: float, p0: float) -> None:
    start = day * PARENT.BARS_PER_DAY
    high[start:start + PARENT.BARS_PER_DAY] = p0 + 1.0
    low[start:start + PARENT.BARS_PER_DAY] = p0 - 1.0
    close[start:start + PARENT.BARS_PER_DAY] = p0
    high[start:start + 12] = level_high
    low[start:start + 12] = level_low
    close[start:start + 12] = p0


def _panel():
    n = 5 * PARENT.BARS_PER_DAY
    high = np.full(n, np.nan)
    low = np.full(n, np.nan)
    close = np.full(n, np.nan)
    _paint(high, low, close, 0, 110.0, 90.0, 100.0)
    _paint(high, low, close, 1, 112.0, 88.0, 100.0)
    _paint(high, low, close, 2, 108.0, 92.0, 100.0)
    _paint(high, low, close, 3, 111.0, 89.0, 100.0)
    _paint(high, low, close, 4, 109.0, 91.0, 100.0)
    return high, low, close


def test_future_activity_and_displacement_use_the_frozen_indexes():
    close = np.arange(1, 400, dtype=np.float64)
    future = A1.log_returns(close, A1.future_return_pairs(FORM))
    assert len(future) == 12
    activity = A1.realized_variation(future)
    end = FORM + K.FORMATION_BARS + K.HORIZON_BARS - 1
    displacement = abs(math.log(close[end] / close[FORM + K.FORMATION_BARS - 1]))
    assert activity == pytest.approx(math.sqrt(float(np.dot(future, future))))
    assert displacement == pytest.approx(abs(math.log(close[FORM + 23] / close[FORM + 11])))
    formation_ends = {right for _left, right in A1.formation_return_pairs(FORM)}
    future_ends = {right for _left, right in A1.future_return_pairs(FORM)}
    assert formation_ends.isdisjoint(future_ends)
    assert ev.DRAW_STAT_ORDER == (
        "foundation_activity",
        "foundation_displacement",
        "incremental_activity",
        "incremental_displacement",
    )


def test_eligible_days_drop_a_missing_future_close_without_scoring_it():
    high, low, close = _panel()
    close[PARENT.BARS_PER_DAY + 23] = np.nan
    rows = ev.eligible_forms(high, low, close, T0)
    assert len(rows) == 3
    assert "activity" not in rows[0]
    fresh_high, fresh_low, fresh_close = _panel()
    values = ev.values_from_forms(fresh_close, ev.eligible_forms(fresh_high, fresh_low, fresh_close, T0))
    assert values["activity"] == pytest.approx(np.zeros(4))
    assert values["displacement"] == pytest.approx(np.zeros(4))
    assert values["v"] == pytest.approx([0.24, 0.16, 0.22, 0.18])


def test_spearman_and_partial_match_average_ranks():
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    y = np.array([1.0, 2.0, 4.0, 3.0, 6.0, 5.0])
    z = np.array([2.0, 1.0, 4.0, 3.0, 6.0, 5.0])
    assert ev.spearman(x, x) == pytest.approx(1.0)
    assert ev.spearman(x, x[::-1]) == pytest.approx(-1.0)
    assert ev.partial_rho(x, y, z) == pytest.approx(A1.partial_spearman(x, y, z)["rho"])
    assert math.isnan(ev.partial_rho(x, y, x))


def test_family_interval_and_clear_rule():
    samples = np.arange(100, dtype=np.float64)
    bounds = ev.family_bounds(samples)
    expected = np.quantile(samples, [0.0125, 0.9875], method="linear")
    assert bounds["lo"] == pytest.approx(expected[0])
    assert bounds["hi"] == pytest.approx(expected[1])
    assert ev.cell_clears(0.10, {"lo": 0.01, "hi": 0.20, "interpretable": True}) is True
    assert ev.cell_clears(0.09, {"lo": 0.01, "hi": 0.20, "interpretable": True}) is False
    assert ev.cell_clears(0.20, {"lo": -0.01, "hi": 0.20, "interpretable": True}) is False
    thin = np.array([1.0] * 5 + [np.nan] * 95)
    assert ev.family_bounds(thin)["interpretable"] is False
    assert ev.cell_clears(0.50, ev.family_bounds(thin)) is False


def test_year_rule_and_lag_alignment():
    table = {
        "2020": {"counts_for_stability": True, "rho": 0.20},
        "2021": {"counts_for_stability": True, "rho": -0.05},
        "2022": {"counts_for_stability": False, "rho": None},
        "2023": {"counts_for_stability": True, "rho": 0.10},
        "2024": {"counts_for_stability": True, "rho": 0.0},
    }
    assert ev.year_is_unstable(table) is True
    same = {key: {"counts_for_stability": True, "rho": 0.1} for key in table}
    assert ev.year_is_unstable(same) is False
    day = PARENT.DAY_MS
    stamps = np.array([0, 2 * day, 3 * day])
    assert ev.lag_day_pairs(stamps) == [(2 * day, 0), (3 * day, 2 * day)]
    state = np.array([1.0, 2.0, 3.0, 4.0])
    outcome = np.array([10.0, 20.0, 30.0, 40.0])
    assert ev.lag_placebo(state, outcome) == pytest.approx(ev.spearman(state[1:], outcome[:-1]))


def test_bootstrap_redraws_weeks_on_one_stream_and_recomputes_ranks():
    week_keys = [(2020, 1), (2020, 1), (2020, 2), (2020, 2)]
    state = np.array([1.0, 2.0, 3.0, 4.0])
    activity = np.array([1.0, 3.0, 2.0, 4.0])
    displacement = np.array([4.0, 1.0, 2.0, 3.0])
    rv_formation = np.array([1.0, 4.0, 2.0, 3.0])
    columns = ev.bootstrap(
        state, activity, displacement, rv_formation, week_keys, draws=1, seed=20261107,
    )
    rng = np.random.default_rng(20261107)
    choice = rng.choice(2, size=2, replace=True)
    indexes = ev.draw_indices(week_keys, choice)
    expected = ev.one_draw_stats(state, activity, displacement, rv_formation, indexes)
    for name in ev.DRAW_STAT_ORDER:
        assert columns[name][0] == pytest.approx(expected[name])
    assert len(indexes) == 4


def test_route_call_is_amendment_a2_and_ignores_rv_prev(monkeypatch):
    endpoints = {
        "ACTIVITY": {
            "foundation_clears": True,
            "year_unstable": False,
            "incremental_formation_clears": True,
            "foundation_abs": 0.30,
            "lag_placebo_abs": 0.05,
            "foundation_rho": 0.30,
            "incremental_rho": 0.12,
            "lag_placebo_rho": 0.05,
        },
        "DISPLACEMENT": {
            "foundation_clears": False,
            "year_unstable": False,
            "incremental_formation_clears": False,
            "foundation_abs": 0.04,
            "lag_placebo_abs": 0.20,
            "foundation_rho": 0.04,
            "incremental_rho": 0.01,
            "lag_placebo_rho": -0.20,
        },
    }
    got = ev.apply_route(endpoints, information_limited_flag=False)
    assert got == A2.assign_route(endpoints, information_limited=False)
    assert got["route"] == A2.ROUTE_PRESENT
    assert got["route_supporting_endpoints"] == ["ACTIVITY"]
    seen = {}
    original_route = A2.assign_route

    def _capture(payload, *, information_limited):
        seen["payload"] = payload
        seen["flag"] = information_limited
        return original_route(payload, information_limited=information_limited)

    monkeypatch.setattr(A2, "assign_route", _capture)
    state = np.arange(1, 7, dtype=np.float64)
    sample = {
        "v": state,
        "activity": state * 2,
        "displacement": state[::-1].astype(np.float64),
        "rv_formation": state + 3,
        "rv_prev": state + 4,
        "year": np.array([2020, 2020, 2020, 2021, 2021, 2021]),
        "week_keys": [(2020, 1)] * 6,
    }
    scored = ev.score_sample(sample, draws=4, seed=11)
    assert seen["flag"] is True
    assert "rv_prev_clears" not in seen["payload"]["ACTIVITY"]
    assert scored["rv_prev"]["route_input"] is False
    assert math.isfinite(scored["rv_prev"]["spearman_v"])
    assert scored["route"] == A2.ROUTE_INFORMATION_LIMITED


def test_second_write_refuses_before_a_panel_load(monkeypatch, tmp_path):
    monkeypatch.setattr(ev, "OUT_JSON", tmp_path / "result.json")
    monkeypatch.setattr(ev, "OUT_MD", tmp_path / "result.md")
    monkeypatch.setattr(ev, "OUT_MANIFEST", tmp_path / "manifest.json")
    (tmp_path / "manifest.json").write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        ev.main()
    assert str(exc.value) == K.REFUSAL_RERUN
    assert ev.DESIGN_SHA == "64407200533eec23abe63391f546ba83c3fae69c30d4a4f83a6d468300985ae6"
    assert ev.A1_SHA == "a2e00c68e4360fe08db89ade31e4f222dc148ace0aea58e9143a27d4d386d49e"
    assert ev.A2_SHA == "a76c0a891fedb7a907544878ef49cd136d3831fb6782d89e56a00ce96e49e07a"
