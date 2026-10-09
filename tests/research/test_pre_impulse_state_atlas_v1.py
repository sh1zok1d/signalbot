"""Synthetic checks for the pre-impulse atlas. No market load."""

from __future__ import annotations

import numpy as np
import pytest

from scripts.research.pre_impulse_state_atlas_v1 import constants as K
from scripts.research.pre_impulse_state_atlas_v1.evaluate import refuse_if_scored
from scripts.research.pre_impulse_state_atlas_v1.features import compute_features
from scripts.research.pre_impulse_state_atlas_v1.stats import (
    discovery_score,
    hour_adjust,
    quintile_table,
    ranks_match_reference,
    spearman,
)


def _series(n=240, seed=1):
    rng = np.random.default_rng(seed)
    close = 100.0 + np.cumsum(rng.normal(0.0, 0.2, n))
    close = np.abs(close) + 10.0
    open_ = close + rng.normal(0.0, 0.05, n)
    high = np.maximum(open_, close) + 0.05
    low = np.minimum(open_, close) - 0.05
    quote = np.full(n, 1_000.0)
    taker = np.full(n, 600.0)
    return open_, high, low, close, quote, taker


def test_fast_ranks_match_the_project_function():
    rng = np.random.default_rng(4)
    values = rng.normal(size=400)
    values[:20] = values[0]
    assert ranks_match_reference(values)


def test_future_close_does_not_change_a_feature():
    open_, high, low, close, quote, taker = _series()
    before = compute_features(open_, high, low, close, quote, taker)
    changed = close.copy()
    changed[180:] += 50.0
    high2 = high.copy()
    high2[180:] += 50.0
    low2 = low.copy()
    low2[180:] += 50.0
    after = compute_features(open_, high2, low2, changed, quote, taker)
    for key in before:
        assert np.allclose(before[key][:180], after[key][:180], equal_nan=True)


def test_anchor_rule_and_surface_end():
    index = np.arange(0, 300)
    assert list(index[(index >= K.MIN_INDEX) & (index % 3 == 2)][:3]) == [98, 101, 104]
    close_ms = K.DATA_START_MS + (index + 1) * K.BAR_MS
    keep = close_ms < K.SURFACE_END_MS
    assert keep.all()
    assert not (K.SURFACE_END_MS < K.SURFACE_END_MS)


def test_score_has_no_correlation_floor():
    years = [{"year": 2020, "n": 200, "spearman": 0.01}, {"year": 2021, "n": 200, "spearman": 0.02}]
    small = discovery_score(0.01, years, n_weeks=100)
    assert small == pytest.approx(0.01)
    assert discovery_score(0.0, years, n_weeks=100) == 0.0
    assert discovery_score(0.2, [{"year": 2020, "n": 199, "spearman": 0.2}], n_weeks=100) == 0.0


def test_flow_is_ineligible_and_mirrors_are_paired():
    flow = [row for row in K.FEATURES if row["family"] == "flow"]
    assert flow and all(row["eligible"] is False for row in flow)
    assert K.OI_OPENED is False and K.LEVEL_ENGINE_USED is False
    ids = {row["id"] for row in K.FEATURES}
    for row in K.FEATURES:
        if row["mirror"]:
            other = K.FEATURE_BY_ID[row["mirror"]]
            assert other["mirror"] == row["id"]
            assert row["expect"] == "opposite"
            assert row["mirror"] in ids


def test_quintiles_cover_every_bin_and_degenerate_ties():
    rng = np.random.default_rng(2)
    x = rng.normal(size=500)
    y = x + rng.normal(size=500)
    table = quintile_table(x, y)
    assert table["degenerate"] is False
    assert sum(b["n"] for b in table["bins"]) == 500
    tied = quintile_table(np.ones(50), y[:50])
    assert tied["degenerate"] is True
    assert tied["delta_p"] is None


def test_hour_adjustment_removes_the_hour_mean():
    y = np.array([1.0, 3.0, 10.0, 30.0])
    hour = np.array([0, 0, 1, 1])
    adj = hour_adjust(y, hour)
    assert adj[hour == 0].mean() == pytest.approx(0.0)
    assert adj[hour == 1].mean() == pytest.approx(0.0)


def test_increasing_path_sits_near_the_high():
    n = 160
    close = np.linspace(100.0, 160.0, n)
    open_ = close - 0.4
    high = close + 0.2
    low = open_ - 0.2
    quote = np.full(n, 100.0)
    taker = np.full(n, 40.0)
    feat = compute_features(open_, high, low, close, quote, taker)
    assert feat["close_pos_4h"][120] > 0.9
    assert feat["dist_upper_4h"][120] < 0.1
    assert feat["efficiency_4h"][120] > 0.9
    assert np.isfinite(feat["compression_slope_1h"][120])


def test_last_bar_upper_touch_has_zero_rejection():
    n = 80
    close = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    close[-1] = 101.8
    high[-1] = 102.0
    open_ = close.copy()
    quote = np.full(n, 100.0)
    taker = np.full(n, 50.0)
    feat = compute_features(open_, high, low, close, quote, taker)
    assert feat["touch_count_upper_4h"][-1] >= 1
    assert feat["bars_since_upper_4h"][-1] == pytest.approx(0.0)
    assert feat["last_rejection_upper_4h"][-1] == pytest.approx(0.0)


def test_refuse_when_an_output_exists(tmp_path):
    marker = tmp_path / "PRE_IMPULSE_STATE_ATLAS_V1.json"
    marker.write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit) as caught:
        refuse_if_scored([marker])
    assert str(caught.value) == K.REFUSAL_RERUN


def test_spearman_sign_on_a_monotone_pair():
    x = np.arange(30, dtype=float)
    assert spearman(x, x) == pytest.approx(1.0)
    assert spearman(x, -x) == pytest.approx(-1.0)
