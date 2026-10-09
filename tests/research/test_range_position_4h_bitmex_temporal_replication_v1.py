"""Synthetic checks. The BitMEX outcome file is not loaded."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pytest

from scripts.research.range_position_4h_bitmex_temporal_replication_v1 import constants as K
from scripts.research.range_position_4h_bitmex_temporal_replication_v1.evaluate import assert_frozen
from scripts.research.range_position_4h_bitmex_temporal_replication_v1.sample import (
    build_grid,
    classify,
    phase_residue,
    rows_to_arrays,
)
from scripts.research.range_position_4h_bitmex_temporal_replication_v1.stats import assign_route
from scripts.research.range_position_4h_incremental_replication_v1.grid import anchor_mask, features
from scripts.research.range_position_4h_incremental_replication_v1 import constants as BK


def _ms(text: str) -> int:
    return int(datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp() * 1000)


def _ci(lo, hi, valid=2000):
    return {"lo": lo, "hi": hi, "valid": valid, "draws": 2000}


def _grid(open_ms, close, high=None, low=None):
    close = np.asarray(close, dtype=np.float64)
    high = close + 1.0 if high is None else np.asarray(high, dtype=np.float64)
    low = close - 1.0 if low is None else np.asarray(low, dtype=np.float64)
    return build_grid(
        np.asarray(open_ms, dtype=np.int64),
        high,
        low,
        close,
    )


def test_gap_constants_match_the_declared_instants():
    assert K.GAP_START_MS == _ms("2016-12-06T23:55:00Z")
    assert K.GAP_END_MS == _ms("2016-12-07T23:50:00Z")
    assert K.PARENT_EPOCH_MS == _ms("2020-01-01T00:00:00Z")
    assert K.SURFACE_END_MS == _ms("2020-01-01T00:00:00Z")
    assert (K.GAP_END_MS - K.GAP_START_MS) // K.BAR_MS + 1 == 288


def test_prices_are_not_inverted():
    opened = K.PARENT_EPOCH_MS - 10 * K.BAR_MS
    rows = [
        {"open_time_ms": opened + i * K.BAR_MS, "high": 50.0 + i, "low": 40.0 + i, "close": 45.0 + i}
        for i in range(4)
    ]
    _opens, highs, lows, closes = rows_to_arrays(rows)
    assert closes.tolist() == [45.0, 46.0, 47.0, 48.0]
    assert highs[0] == 50.0
    assert lows[0] == 40.0


def test_a_bar_at_the_surface_end_is_refused():
    with pytest.raises(SystemExit, match="SERIES_CROSSES_2020"):
        rows_to_arrays([{"open_time_ms": K.SURFACE_END_MS, "high": 2.0, "low": 1.0, "close": 1.5}])


def test_phase_residue_matches_bybit_after_the_warmup_floor():
    grid_open = BK.DATA_START_MS + np.arange(0, 400, dtype=np.int64) * BK.BAR_MS
    residue = phase_residue(grid_open)
    global_i = (grid_open - BK.DATA_START_MS) // BK.BAR_MS
    theirs = anchor_mask(grid_open)
    assert np.array_equal(residue[global_i >= 96], theirs[global_i >= 96])
    assert np.all((grid_open[residue] + K.BAR_MS) % 900_000 == 0)


def test_pre_2020_closes_on_a_15_minute_boundary_keep_the_same_residue():
    close_ms = _ms("2019-06-15T12:15:00Z")
    opened = close_ms - K.BAR_MS
    assert phase_residue(np.asarray([opened]))[0]
    off = close_ms - 2 * K.BAR_MS
    assert not phase_residue(np.asarray([off]))[0]
    last = _ms("2019-12-31T23:55:00Z")
    assert phase_residue(np.asarray([last]))[0]
    grid = _grid(np.asarray([last]), np.asarray([100.0]))
    masks = classify(grid)
    assert not masks["phase"][0]


def test_known_gap_bar_excludes_the_anchor_and_is_not_bridged():
    start = K.GAP_START_MS - 60 * K.BAR_MS
    n = 140
    open_ms = start + np.arange(n, dtype=np.int64) * K.BAR_MS
    keep = open_ms != K.GAP_START_MS
    close = np.linspace(100.0, 120.0, n)
    grid = _grid(open_ms[keep], close[keep])
    masks = classify(grid)
    hole_at = int(np.flatnonzero(open_ms == K.GAP_START_MS)[0])
    touched = np.arange(n)
    window = (touched >= hole_at - K.HORIZON) & (touched <= hole_at + K.LOOKBACK)
    assert masks["gap"][window & masks["phase"]].all()
    assert not masks["eligible"][window].any()
    feat = features(grid["high"], grid["low"], grid["close"])
    assert not np.isfinite(feat["rp"][hole_at + 10])


def test_an_interior_future_hole_is_future_incomplete_even_if_the_endpoint_exists():
    start = _ms("2018-03-01T00:00:00Z")
    n = 90
    open_ms = start + np.arange(n, dtype=np.int64) * K.BAR_MS
    close = np.linspace(100.0, 130.0, n)
    high = close + 1.0
    low = close - 1.0
    full = classify(_grid(open_ms, close, high, low))
    candidates = np.flatnonzero(full["phase"] & (np.arange(n) > 50) & (np.arange(n) + K.HORIZON < n))
    anchor = int(candidates[0])
    drop = anchor + 6
    keep = np.ones(n, dtype=bool)
    keep[drop] = False
    grid = _grid(open_ms[keep], close[keep], high[keep], low[keep])
    masks = classify(grid)
    feat = features(grid["high"], grid["low"], grid["close"])
    assert np.isfinite(feat["r1"][anchor])
    assert masks["future"][anchor]
    assert not masks["eligible"][anchor]


def test_zero_span_is_lookback_incomplete_and_features_agree():
    start = _ms("2018-04-01T00:00:00Z")
    n = 80
    open_ms = start + np.arange(n, dtype=np.int64) * K.BAR_MS
    close = np.full(n, 100.0)
    grid = _grid(open_ms, close, high=close, low=close)
    masks = classify(grid)
    feat = features(grid["high"], grid["low"], grid["close"])
    i = int(np.flatnonzero(masks["phase"] & (np.arange(n) >= K.LOOKBACK))[0])
    assert masks["phase"][i]
    assert masks["lookback"][i]
    assert not np.isfinite(feat["rp"][i])
    assert not masks["eligible"].any()


def test_eligible_indexes_match_finite_imported_features():
    start = _ms("2018-05-01T00:00:00Z")
    n = 100
    open_ms = start + np.arange(n, dtype=np.int64) * K.BAR_MS
    close = 100.0 + np.cumsum(np.linspace(-0.2, 0.3, n))
    grid = _grid(open_ms, close)
    masks = classify(grid)
    feat = features(grid["high"], grid["low"], grid["close"])
    finite = (
        np.isfinite(feat["rp"])
        & np.isfinite(feat["ret4"])
        & np.isfinite(feat["rv4"])
        & np.isfinite(feat["r1"])
    )
    assert np.all(finite[masks["eligible"]])
    assert int(masks["phase"].sum()) == int(
        masks["eligible"].sum() + masks["gap"].sum() + masks["lookback"].sum() + masks["future"].sum()
    )


def test_routes_follow_the_frozen_order():
    below = _ci(-0.06, -0.04)
    around = _ci(-0.02, 0.01)
    above = _ci(0.01, 0.03)
    assert assign_route(-0.05, around, -0.02, below) == K.ROUTE_SUPPORTED
    assert assign_route(-0.05, below, -0.01, around) == K.ROUTE_RAW_ONLY
    assert assign_route(-0.05, below, 0.01, around) == K.ROUTE_RAW_ONLY
    assert assign_route(-0.02, around, -0.01, around) == K.ROUTE_COMPATIBLE
    assert assign_route(0.01, above, -0.02, below) == K.ROUTE_NOT
    assert assign_route(0.0, around, -0.02, below) == K.ROUTE_NOT
    assert assign_route(-0.05, below, 0.02, above) == K.ROUTE_NOT
    assert assign_route(-0.05, below, -0.02, _ci(-0.03, -0.01, valid=10)) == K.ROUTE_UNAVAILABLE
    assert assign_route(-0.01, around, 0.01, around) == K.ROUTE_UNAVAILABLE


def test_hash_gate_refuses_until_the_census_is_pinned():
    if K.DESIGN_SHA256 == "PENDING_DESIGN_HASH":
        with pytest.raises(SystemExit, match="DESIGN_HASH_UNSET"):
            assert_frozen()
    else:
        frozen = assert_frozen()
        assert frozen["design"] == K.DESIGN_SHA256
        assert frozen["design_json"] == K.DESIGN_JSON_SHA256
        assert frozen["support"] == K.SUPPORT_SHA256


def test_a_wrong_design_hash_refuses_before_the_series(monkeypatch):
    monkeypatch.setattr(K, "DESIGN_SHA256", "0" * 64)
    monkeypatch.setattr(K, "DESIGN_JSON_SHA256", "1" * 64)
    monkeypatch.setattr(K, "SUPPORT_SHA256", "2" * 64)
    with pytest.raises(SystemExit, match="DESIGN_HASH_MISMATCH"):
        assert_frozen()
