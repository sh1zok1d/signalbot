"""Synthetic checks. The Binance 2025-2026 outcome file is not loaded."""

from __future__ import annotations

import gzip
import json
from datetime import datetime, timezone

import numpy as np
import pytest

from beta.history_data import url_refusal
from scripts.research.range_position_4h_binance_2025_2026_temporal_replication_v1 import constants as K
from scripts.research.range_position_4h_binance_2025_2026_temporal_replication_v1.evaluate import assert_frozen
from scripts.research.range_position_4h_binance_2025_2026_temporal_replication_v1.sample import (
    build_grid,
    classify,
    load_rows,
    phase_residue,
)
from scripts.research.range_position_4h_binance_2025_2026_temporal_replication_v1.stats import assign_route
from scripts.research.range_position_4h_incremental_replication_v1.grid import features


def _ms(text: str) -> int:
    return int(datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp() * 1000)


def _ci(lo, hi, valid=2000):
    return {"lo": lo, "hi": hi, "valid": valid, "draws": 2000}


def _grid(open_ms, close, high=None, low=None):
    close = np.asarray(close, dtype=np.float64)
    high = close + 1.0 if high is None else np.asarray(high, dtype=np.float64)
    low = close - 1.0 if low is None else np.asarray(low, dtype=np.float64)
    return build_grid(np.asarray(open_ms, dtype=np.int64), high, low, close)


def test_clock_constants_match_the_declared_instants():
    assert K.PARENT_EPOCH_MS == _ms("2020-01-01T00:00:00Z")
    assert K.SURFACE_START_MS == _ms("2025-01-01T00:00:00Z")
    assert K.SURFACE_END_MS == _ms("2026-10-09T00:00:00Z")
    assert K.E1_START_MS == _ms("2026-08-16T00:00:00Z")
    assert K.E1_END_MS == _ms("2026-08-25T17:20:00Z")
    assert K.OBJECT_HOLE_END_MS == _ms("2026-08-26T00:00:00Z")
    assert K.BOOT_SEED == 20261119


def test_protected_archive_urls_are_refused_and_the_neighbouring_days_are_not():
    root = "https://data.binance.vision/data/futures/um/"
    assert url_refusal(root + "monthly/klines/BTCUSDT/5m/BTCUSDT-5m-2026-08.zip")
    assert url_refusal(root + "daily/klines/BTCUSDT/5m/BTCUSDT-5m-2026-08-16.zip")
    assert url_refusal(root + "daily/klines/BTCUSDT/5m/BTCUSDT-5m-2026-08-25.zip")
    assert url_refusal(root + "daily/klines/BTCUSDT/5m/BTCUSDT-5m-2026-08-15.zip") is None
    assert url_refusal(root + "daily/klines/BTCUSDT/5m/BTCUSDT-5m-2026-08-26.zip") is None


def test_a_protected_open_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(K, "SERIES_SHA256", "PENDING_SERIES_HASH")
    path = tmp_path / "bars.jsonl.gz"
    row = {"open_time_ms": K.E1_START_MS, "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5}
    with gzip.open(path, "wt") as handle:
        handle.write(json.dumps(row) + "\n")
    with pytest.raises(SystemExit, match="PROTECTED_ROW_IN_SERIES"):
        load_rows(path)


def test_phase_residue_is_the_15_minute_close():
    grid_open = K.SURFACE_START_MS + np.arange(0, 30, dtype=np.int64) * K.BAR_MS
    residue = phase_residue(grid_open)
    assert np.all((grid_open[residue] + K.BAR_MS) % 900_000 == 0)
    assert not np.all((grid_open + K.BAR_MS) % 900_000 == 0)


def test_object_hole_is_not_bridged():
    start = K.OBJECT_HOLE_START_MS - 60 * K.BAR_MS
    n = 80
    open_ms = start + np.arange(n, dtype=np.int64) * K.BAR_MS
    keep = open_ms < K.OBJECT_HOLE_START_MS
    # keep a tail after the hole so the dense grid contains the hole
    tail = K.OBJECT_HOLE_END_MS + np.arange(0, 20, dtype=np.int64) * K.BAR_MS
    kept = np.concatenate([open_ms[keep], tail])
    close = np.linspace(100.0, 140.0, kept.size)
    grid = _grid(kept, close)
    masks = classify(grid)
    assert masks["hole"].any()
    assert not masks["eligible"][masks["excluded"]].any()
    assert masks["excluded"].any()


def test_eligible_indexes_match_the_imported_feature():
    start = _ms("2025-03-01T00:00:00Z")
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
    i = int(np.flatnonzero(masks["eligible"])[0])
    window = slice(i - 47, i + 1)
    hi = grid["high"][window].max()
    lo = grid["low"][window].min()
    assert feat["rp"][i] == pytest.approx((grid["close"][i] - lo) / (hi - lo))


def test_routes_follow_the_frozen_order():
    below = _ci(-0.06, -0.04)
    around = _ci(-0.02, 0.01)
    above = _ci(0.01, 0.03)
    assert assign_route(-0.05, around, -0.02, below) == K.ROUTE_SUPPORTED
    assert assign_route(-0.05, below, -0.01, around) == K.ROUTE_RAW_ONLY
    assert assign_route(-0.02, around, -0.01, around) == K.ROUTE_COMPATIBLE
    assert assign_route(0.01, above, -0.02, below) == K.ROUTE_NOT
    assert assign_route(-0.05, below, 0.02, above) == K.ROUTE_NOT
    assert assign_route(-0.05, below, -0.02, _ci(-0.03, -0.01, valid=10)) == K.ROUTE_UNAVAILABLE


def test_hash_gate_refuses_until_the_census_is_pinned():
    if K.DESIGN_SHA256 == "PENDING_DESIGN_HASH":
        with pytest.raises(SystemExit, match="DESIGN_HASH_UNSET"):
            assert_frozen()
    else:
        frozen = assert_frozen()
        assert frozen["design"] == K.DESIGN_SHA256


def test_a_wrong_design_hash_refuses_before_the_series(monkeypatch):
    monkeypatch.setattr(K, "DESIGN_SHA256", "0" * 64)
    monkeypatch.setattr(K, "DESIGN_JSON_SHA256", "1" * 64)
    monkeypatch.setattr(K, "SUPPORT_SHA256", "2" * 64)
    monkeypatch.setattr(K, "OBJECTS_SHA256", "3" * 64)
    monkeypatch.setattr(K, "SERIES_SHA256", "4" * 64)
    with pytest.raises(SystemExit, match="DESIGN_HASH_MISMATCH"):
        assert_frozen()
