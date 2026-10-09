"""Synthetic checks for the formation-width census. No market panel is opened."""

from __future__ import annotations

import numpy as np
import pytest

from scripts.research.formation_width_regime_v1 import constants as K
from scripts.research.formation_width_regime_v1 import census as census_mod
from scripts.research.formation_width_regime_v1.census import (
    assert_support_only,
    collect,
    summarize,
    write_outputs,
)
from scripts.research.opening_range_object_v1 import constants as PARENT

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
    # Day 0 is 2019-12-31 warm-up. Days 1-4 are the first four UTC days of 2020.
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


def test_census_counts_width_and_does_not_score_a_future_path():
    high, low, close = _panel()
    collected = collect(high, low, close, T0)
    assert collected["counts"]["calendar_days"] == 4
    assert collected["counts"]["usable_formation"] == 4
    assert collected["counts"]["analysis_sample"] == 4
    payload = summarize(collected)
    assert payload["outcome_read"] is False
    assert payload["future_association_read"] is False
    assert payload["anchor"] == "UTC_00"
    assert payload["horizon_bars"] == 12
    widths = sorted(row["relative_width"] for row in collected["rows"])
    assert widths == pytest.approx([0.16, 0.18, 0.22, 0.24])
    assert_support_only(payload)
    assert payload["information_status"] == K.LIMITED


def test_a_missing_future_close_drops_the_day_without_filling():
    high, low, close = _panel()
    # 2020-01-01 formation ends at day 1, bar 11. The next-hour path needs that close and 12 more.
    close[PARENT.BARS_PER_DAY + 23] = np.nan
    collected = collect(high, low, close, T0)
    assert collected["counts"]["usable_formation"] == 4
    assert collected["counts"]["future_path_incomplete"] == 1
    assert collected["counts"]["analysis_sample"] == 3


def test_second_write_refuses(tmp_path):
    json_path = tmp_path / "feasibility.json"
    md_path = tmp_path / "feasibility.md"
    json_path.write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        write_outputs({"outcome_read": False}, json_path, md_path)
    assert str(exc.value) == census_mod.K.REFUSAL_RERUN


def test_future_association_key_is_rejected():
    with pytest.raises(RuntimeError):
        assert_support_only({"outcome_read": False, "future_association_read": False, "activity_rho": 0.2})
