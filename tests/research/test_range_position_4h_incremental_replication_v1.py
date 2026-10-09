"""Synthetic checks. No Bybit outcome is loaded."""

from __future__ import annotations

import numpy as np
import pytest

from scripts.research.range_position_4h_incremental_replication_v1 import constants as K
from scripts.research.range_position_4h_incremental_replication_v1.evaluate import assert_design_frozen
from scripts.research.range_position_4h_incremental_replication_v1.grid import anchor_mask, features, place
from scripts.research.range_position_4h_incremental_replication_v1.stats import (
    assign_route,
    matches_canonical_one_covariate,
    ranks_match_reference,
)


def _ci(lo, hi, valid=2000):
    return {"lo": lo, "hi": hi, "valid": valid, "draws": 2000}


def test_fast_ranks_match_the_project_function():
    rng = np.random.default_rng(4)
    values = rng.normal(size=500)
    values[:30] = values[0]
    assert ranks_match_reference(values)


def test_one_covariate_matches_the_canonical_helper():
    rng = np.random.default_rng(5)
    x = rng.normal(size=800)
    z = rng.normal(size=800)
    y = -0.4 * x + 0.7 * z + rng.normal(size=800)
    assert matches_canonical_one_covariate(x, y, z)


def test_parent_window_includes_the_decision_bar_and_ignores_the_future():
    rng = np.random.default_rng(6)
    n = 80
    close = 100.0 + np.cumsum(rng.normal(0.0, 0.2, n))
    close = np.abs(close) + 10.0
    high = close + 0.4
    low = close - 0.4
    feat = features(high, low, close)
    i = 60
    hi = high[i - 47 : i + 1].max()
    lo = low[i - 47 : i + 1].min()
    assert feat["rp"][i] == pytest.approx((close[i] - lo) / (hi - lo))
    assert feat["ret4"][i] == pytest.approx(np.log(close[i] / close[i - 48]))
    rets = np.diff(np.log(close[i - 48 : i + 1]))
    assert feat["rv4"][i] == pytest.approx(np.sqrt(np.sum(rets * rets)))
    changed = close.copy()
    changed[-1] = close[-1] * 1.5
    later = features(high, low, changed)
    assert later["rp"][i] == feat["rp"][i]
    assert later["ret4"][i] == feat["ret4"][i]
    assert later["rv4"][i] == feat["rv4"][i]
    assert later["r1"][i] == feat["r1"][i]


def test_a_hole_is_not_filled():
    open_ms = np.arange(0, 70, dtype=np.int64) * K.BAR_MS + K.DATA_START_MS
    keep = np.ones(open_ms.size, dtype=bool)
    keep[40] = False
    close = np.linspace(100.0, 130.0, open_ms.size)
    high = close + 1.0
    low = close - 1.0
    grid = place(open_ms[keep], high[keep], low[keep], close[keep])
    assert grid["holes"] == 1
    assert not np.isfinite(grid["close"][40])
    feat = features(grid["high"], grid["low"], grid["close"])
    assert not np.isfinite(feat["rp"][50])
    assert not np.isfinite(feat["rv4"][50])


def test_anchor_phase_matches_the_parent_clock():
    grid_open = K.DATA_START_MS + np.arange(0, 120, dtype=np.int64) * K.BAR_MS
    mask = anchor_mask(grid_open)
    chosen = np.flatnonzero(mask)
    assert chosen.size
    assert np.all(chosen >= 96)
    assert np.all(chosen % 3 == 2)
    assert not mask[96]
    assert mask[98]


def test_routes_follow_the_frozen_order():
    below = _ci(-0.06, -0.04)
    around = _ci(-0.02, 0.01)
    above = _ci(0.01, 0.03)
    assert assign_route(-0.05, around, -0.02, below) == K.ROUTE_SUPPORTED
    assert assign_route(-0.05, below, -0.01, around) == K.ROUTE_RAW_ONLY
    assert assign_route(-0.02, around, 0.01, around) == K.ROUTE_COMPATIBLE
    assert assign_route(0.01, above, -0.02, below) == K.ROUTE_NOT
    assert assign_route(0.0, around, -0.02, below) == K.ROUTE_NOT
    assert assign_route(-0.05, below, 0.02, above) == K.ROUTE_OPPOSES
    assert assign_route(-0.05, below, -0.02, _ci(-0.03, -0.01, valid=10)) == K.ROUTE_UNAVAILABLE


def test_the_frozen_design_hash_matches_the_file():
    assert assert_design_frozen() == K.DESIGN_SHA256


def test_a_wrong_design_hash_refuses_before_the_series(monkeypatch):
    monkeypatch.setattr(K, "DESIGN_SHA256", "0" * 64)
    with pytest.raises(SystemExit, match="DESIGN_HASH_MISMATCH"):
        assert_design_frozen()
