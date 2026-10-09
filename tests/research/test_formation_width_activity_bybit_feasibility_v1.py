"""Synthetic checks for the Bybit feasibility census. No market endpoint is scored."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from scripts.research.formation_width_activity_bybit_feasibility_v1 import constants as K
from scripts.research.formation_width_activity_bybit_feasibility_v1 import evaluate
from scripts.research.formation_width_activity_bybit_feasibility_v1 import support
from scripts.research.formation_width_activity_confirmation_v1 import support as CONFIRM
from scripts.research.formation_width_regime_v1 import amendment_a1 as A1


ROOT = Path(__file__).resolve().parents[2]
UTC = dt.timezone.utc


def _ms(day: dt.datetime) -> int:
    return int(day.timestamp() * 1000)


def _bind_short_window(monkeypatch, n_event_days: int):
    grid_start = dt.datetime(2020, 3, 31, tzinfo=UTC)
    event_start = grid_start + dt.timedelta(days=1)
    surface_end = event_start + dt.timedelta(days=n_event_days)
    monkeypatch.setattr(support, "GRID_START_MS", _ms(grid_start))
    monkeypatch.setattr(support, "EVENT_START_MS", _ms(event_start))
    monkeypatch.setattr(support, "SURFACE_END_MS", _ms(surface_end))
    monkeypatch.setattr(support, "GRID_DAYS", 1 + n_event_days)
    monkeypatch.setattr(support, "SPLIT_MS", _ms(event_start + dt.timedelta(days=n_event_days // 2)))
    return event_start


def _panel(n_days: int):
    n = n_days * K.BARS_PER_DAY
    close = np.linspace(100.0, 100.0 + n * 0.05, n)
    high = close + np.linspace(1.0, 3.0, n)
    low = close - np.linspace(1.0, 2.0, n)
    return high, low, close


def test_constants_match_the_selected_claim():
    assert K.PRACTICAL_RHO == 0.10
    assert K.POWER_FLOOR == 0.80
    assert K.BOOT_SEED == 20261108
    assert K.ENDPOINT == "ACTIVITY"
    assert K.INCREMENTAL_COVARIATE == "RV_FORMATION"
    assert K.EXPOSURE_CLASS == "SAME_CALENDAR_CROSS_VENUE_EXPOSED_REPLICATION"
    assert K.TIME_DISJOINT_FROM_DISCOVERY is False
    assert K.STABILITY_SPLIT == "2022-08-17"
    assert K.CANONICAL_SHA256 == "f7ef739f7d359056cbbf78a77993995f54e3303e50775b5aadf36b4ba68f507c"
    start = dt.date(2020, 4, 1)
    end = dt.date(2025, 1, 1)
    assert (end - start).days == 1736
    assert start + dt.timedelta(days=868) == dt.date(2022, 8, 17)
    assert support.GRID_DAYS == 1737


def test_evaluator_refuses_before_any_panel():
    source = (ROOT / "scripts/research/formation_width_activity_bybit_feasibility_v1/evaluate.py").read_text()
    assert "load_ohlc" not in source
    assert "realized_variation" not in source
    assert "partial_spearman" not in source
    with pytest.raises(SystemExit, match=K.REFUSAL_BEFORE_GO):
        evaluate.main()


def test_support_source_does_not_score_the_endpoint():
    source = (ROOT / "scripts/research/formation_width_activity_bybit_feasibility_v1/support.py").read_text()
    assert "realized_variation" not in source
    assert "log_returns" not in source
    assert "partial_spearman" not in source
    assert "future_return_pairs" not in source


def test_forecast_function_is_the_confirmation_function():
    assert support.information_forecast is CONFIRM.information_forecast


def test_route_priority_is_frozen():
    assert support.assign_route(False, 0.99) == K.ROUTE_LIMITED
    assert support.assign_route(True, 0.79) == K.ROUTE_WEAK
    assert support.assign_route(True, float("nan")) == K.ROUTE_WEAK
    assert support.assign_route(True, 0.80) == K.ROUTE_ADEQUATE


def test_rv_formation_span_is_the_discovery_index():
    form = 288
    start, count = A1.formation_close_span(form)
    assert (start, count) == (form - 1, 13)
    assert form + K.FORMATION_BARS - 1 == form + 11
    assert K.HORIZON_BARS + 1 == 13
    assert set(A1.formation_return_pairs(form)).isdisjoint(set(A1.future_return_pairs(form)))


def test_future_close_values_do_not_change_support(monkeypatch):
    _bind_short_window(monkeypatch, 6)
    high, low, close = _panel(7)
    base = support.summarize(support.collect(high, low, close))
    mutated = close.copy()
    mutated[K.BARS_PER_DAY + K.FORMATION_BARS + 3] *= 50.0
    other = support.summarize(support.collect(high, low, mutated))
    assert base["counts"] == other["counts"]
    assert base["relative_width"] == other["relative_width"]
    assert base["pre_outcome_route"] == other["pre_outcome_route"]
    assert base["outcome_read"] is False
    assert base["future_association_read"] is False


def test_path_holes_drop_the_row_without_scoring_it(monkeypatch):
    event_start = _bind_short_window(monkeypatch, 4)
    high, low, close = _panel(5)
    # Event day 0: the close before the formation hour is missing.
    form0 = K.BARS_PER_DAY
    close[form0 - 1] = np.nan
    # Event day 1: one close inside the next hour is missing.
    form1 = 2 * K.BARS_PER_DAY
    close[form1 + K.FORMATION_BARS + 2] = np.nan
    collected = support.collect(high, low, close)
    flags = {row["day_ms"]: row["in_sample"] for row in collected["rows"]}
    t0 = _ms(event_start)
    assert collected["counts"]["calendar_days"] == 4
    assert collected["counts"]["rv_formation_span_incomplete"] == 1
    assert collected["counts"]["next_hour_path_incomplete"] == 1
    assert flags[t0] is False
    assert flags[t0 + K.DAY_MS] is False
    assert flags[t0 + 2 * K.DAY_MS] is True
    assert flags[t0 + 3 * K.DAY_MS] is True
    payload = support.summarize(collected)
    support.assert_support_only(payload)
    assert payload["counts"]["analysis_sample"] == 2
    assert payload["outcome_read"] is False


def test_floor_fails_closed_on_a_short_panel(monkeypatch):
    _bind_short_window(monkeypatch, 8)
    high, low, close = _panel(9)
    payload = support.summarize(support.collect(high, low, close))
    support.assert_support_only(payload)
    assert payload["count_floor_met"] is False
    assert payload["pre_outcome_route"] == K.ROUTE_LIMITED
    assert payload["later_outcome_permitted_after_separate_go"] is False
    assert payload["owner_go_required_for_outcome"] is True
    assert payload["this_unit_reads_outcome"] is False


def test_support_rerun_refuses_before_load(monkeypatch, tmp_path):
    target = tmp_path / "already.json"
    target.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(support, "OUT_JSON", target)
    monkeypatch.setattr(support, "OUT_MD", tmp_path / "missing.md")
    monkeypatch.setattr(support, "OUT_MANIFEST", tmp_path / "missing-manifest.json")

    def explode():
        raise AssertionError("ohlc load is not allowed on a rerun")

    monkeypatch.setattr(support, "load_ohlc", explode)
    with pytest.raises(SystemExit, match=K.REFUSAL_RERUN):
        support.main()


def test_official_support_file_is_outcome_blind_and_adequate():
    payload = json.loads((
        ROOT / "docs/research/FORMATION_WIDTH_ACTIVITY_BYBIT_FEASIBILITY_V1_SUPPORT.json"
    ).read_text(encoding="utf-8"))
    support.assert_support_only(payload)
    assert payload["outcome_read"] is False
    assert payload["future_association_read"] is False
    assert payload["owner_go_required_for_outcome"] is True
    assert payload["this_unit_reads_outcome"] is False
    assert payload["claim_selected_pre_outcome"] is True
    assert payload["exact_cell_consumed_before_this_unit"] is False
    assert payload["exposure_class"] == K.EXPOSURE_CLASS
    assert payload["counts"]["calendar_days"] == 1736
    assert payload["counts"]["usable_formation"] == 1614
    assert payload["counts"]["formation_incomplete"] == 122
    assert payload["counts"]["rv_formation_span_incomplete"] == 0
    assert payload["counts"]["next_hour_path_incomplete"] == 1
    assert payload["counts"]["analysis_sample"] == 1613
    assert payload["analysis_iso_weeks"] == 240
    assert payload["first_half_n"] == 838
    assert payload["second_half_n"] == 775
    assert payload["count_floor_met"] is True
    assert payload["lag1_relative_width_rank_correlation"] == pytest.approx(0.5185063706050135)
    assert payload["information_forecast"]["effective_n"] == pytest.approx(645.3604432971196)
    assert payload["information_forecast"]["fisher_se"] == pytest.approx(0.03945577746287656)
    assert payload["information_forecast"]["minimum_detectable_association_80"] == pytest.approx(0.09810579876388723)
    assert payload["information_forecast"]["power_lower_bound_excludes_zero_at_practical_bar"] == pytest.approx(
        0.8131675544359748
    )
    assert payload["pre_outcome_route"] == K.ROUTE_ADEQUATE
    assert payload["later_outcome_permitted_after_separate_go"] is True
    assert payload["read_at"] == "2026-10-09T07:08:16Z"
    assert payload["code_digest"] == "49ef4758a2728ae585f32a3a39b5aeb3584ab744a5153e851a6f4530c7ed4ec7"
    assert payload["design_sha256"] == hashlib.sha256(
        (ROOT / "docs/research/FORMATION_WIDTH_ACTIVITY_BYBIT_FEASIBILITY_V1_DESIGN.md").read_bytes()
    ).hexdigest()
    assert payload["grid"]["present_bars"] == 476254
    assert payload["grid"]["canonical_sha256"] == K.CANONICAL_SHA256
