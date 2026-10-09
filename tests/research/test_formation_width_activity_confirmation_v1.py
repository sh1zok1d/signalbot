"""Synthetic checks for the confirmation design. No market endpoint is scored."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
import pytest

from scripts.research.formation_width_activity_confirmation_v1 import constants as K
from scripts.research.formation_width_activity_confirmation_v1 import evaluate
from scripts.research.formation_width_activity_confirmation_v1 import support
from scripts.research.formation_width_regime_v1 import amendment_a1 as A1


ROOT = Path(__file__).resolve().parents[2]
UTC = dt.timezone.utc


def _panel(n_days: int, *, break_future_day: int | None = None, break_prev_day: int | None = None):
    n = n_days * K.BARS_PER_DAY
    close = np.linspace(100.0, 100.0 + n * 0.01, n)
    high = close + 1.0
    low = close - 1.0
    if break_future_day is not None:
        form = break_future_day * K.BARS_PER_DAY
        close[form + K.FORMATION_BARS + 2] = np.nan
    if break_prev_day is not None:
        form = break_prev_day * K.BARS_PER_DAY
        close[form - 1] = np.nan
    return high, low, close


def test_constants_match_the_selected_claim():
    assert K.PRACTICAL_RHO == 0.10
    assert K.BOOT_SEED == 20261108
    assert K.BOOT_QUANTILE_LO == 0.05
    assert K.STABILITY_SPLIT == "2018-11-01"
    assert K.ENDPOINT == "ACTIVITY"
    assert K.HORIZON_BARS == 12
    assert K.DISCOVERY_INCREMENTAL_ACTIVITY == pytest.approx(0.10245095315584887)
    assert K.EXPOSURE_CLASS == "TIME_DISJOINT_EXPOSED_SURFACE_REPLICATION"
    start = dt.datetime(2017, 9, 1, tzinfo=UTC)
    end = dt.datetime(2020, 1, 1, tzinfo=UTC)
    assert (end - start).days == 852
    assert start + dt.timedelta(days=426) == dt.datetime(2018, 11, 1, tzinfo=UTC)


def test_evaluator_refuses_before_any_panel():
    source = (ROOT / "scripts/research/formation_width_activity_confirmation_v1/evaluate.py").read_text()
    assert "load_panel" not in source
    assert "realized_variation" not in source
    assert "partial_spearman" not in source
    with pytest.raises(SystemExit, match=K.REFUSAL_BEFORE_GO):
        evaluate.main()


def test_support_source_does_not_score_the_endpoint():
    source = (ROOT / "scripts/research/formation_width_activity_confirmation_v1/support.py").read_text()
    assert "realized_variation" not in source
    assert "log_returns" not in source
    assert "partial_spearman" not in source
    assert "future_return_pairs" not in source


def test_future_close_values_do_not_change_support():
    high, low, close = _panel(4)
    t0 = support._ms(K.EVENT_START)
    base = support.summarize(support.collect(high, low, close, t0))
    mutated = close.copy()
    mutated[K.BARS_PER_DAY + K.FORMATION_BARS + 3] *= 50.0
    other = support.summarize(support.collect(high, low, mutated, t0))
    assert base["counts"] == other["counts"]
    assert base["relative_width"] == other["relative_width"]
    assert base["information_status"] == other["information_status"]


def test_path_holes_drop_the_row_without_scoring_it():
    high, low, close = _panel(4, break_future_day=2, break_prev_day=1)
    t0 = support._ms(K.EVENT_START)
    collected = support.collect(high, low, close, t0)
    flags = {row["day_ms"]: row["in_sample"] for row in collected["rows"]}
    # day 0 has no bar before the grid, so the covariate span is incomplete
    assert collected["counts"]["calendar_days"] == 4
    assert flags[t0] is False
    assert flags[t0 + K.DAY_MS] is False
    assert flags[t0 + 2 * K.DAY_MS] is False
    assert flags[t0 + 3 * K.DAY_MS] is True
    payload = support.summarize(collected)
    support.assert_support_only(payload)
    assert payload["outcome_read"] is False
    assert payload["counts"]["analysis_sample"] == 1


def test_rv_formation_span_is_the_discovery_index():
    form = 288
    start, count = A1.formation_close_span(form)
    assert (start, count) == (287, 13)
    future_start = form + K.FORMATION_BARS - 1
    assert future_start == form + 11
    assert K.HORIZON_BARS + 1 == 13
    assert set(A1.formation_return_pairs(form)).isdisjoint(set(A1.future_return_pairs(form)))


def test_information_forecast_independence_and_power_floor():
    sizes = [7] * 100
    quiet = support.information_forecast(sizes, 0.0)
    assert quiet["effective_n"] == pytest.approx(700.0)
    assert quiet["fisher_se"] == pytest.approx(1.0 / np.sqrt(697.0))
    assert quiet["power_lower_bound_excludes_zero_at_practical_bar"] > 0.80
    dependent = support.information_forecast(sizes, 0.9)
    assert dependent["effective_n"] < quiet["effective_n"]
    assert dependent["fisher_se"] > quiet["fisher_se"]
    assert support.ar1_average_pairwise(0.5, 2) == pytest.approx(0.5)
    point_prob = support.probability_point_and_bound(0.01)
    assert point_prob == pytest.approx(0.5)


def test_floor_fails_closed_on_a_short_panel():
    high, low, close = _panel(6)
    payload = support.summarize(support.collect(high, low, close, support._ms(K.EVENT_START)))
    assert payload["information_status"] == K.WEAK
    assert payload["pre_outcome_route"] == K.ROUTE_WEAK
    assert payload["awaiting_separate_owner_go"] is False
    assert payload["information_authorizes_outcome"] is False


def test_support_rerun_refuses_before_load(monkeypatch, tmp_path):
    target = tmp_path / "already.json"
    target.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(support, "OUT_JSON", target)
    monkeypatch.setattr(support, "OUT_MD", tmp_path / "missing.md")

    def explode():
        raise AssertionError("panel load is not allowed on a rerun")

    monkeypatch.setattr(support.spot_data, "load_panel", explode)
    with pytest.raises(SystemExit, match=K.REFUSAL_RERUN):
        support.main()
