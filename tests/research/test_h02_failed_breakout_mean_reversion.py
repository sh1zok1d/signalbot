"""Network-free tests for H02 failed-breakout mean reversion.

Does not open 2025/2026 outcomes. Does not reuse V1/V2 detectors.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest
import yaml

from scripts.research import h02_failed_breakout_mean_reversion_lib as lib
from scripts.research.h02_failed_breakout_mean_reversion_lib import (
    BAR_MS,
    DEV_END_MS,
    DIR_LOWER,
    DIR_UPPER,
    HTF_MS,
    ValidationWindowForbidden,
    aggregate_1m_to_5m,
    apply_refractory,
    assert_development_outcome_window,
    classify_events,
    development_t_max_ms,
    event_bar_open_ms,
    is_grid_ms,
    load_prereg,
    parse_px,
    prior_range,
    require_snapshot,
    shift_plus_6h_same_utc_day,
)

UTC = timezone.utc
REPO_ROOT = Path(__file__).resolve().parents[2]


def test_prereg_search_surface_frozen():
    p = load_prereg()
    assert p["lookbacks_minutes"] == [60, 120, 240]
    assert p["overshoot_thresholds_s"] == [0.0, 0.05, 0.1]
    assert p["horizons_minutes"] == [15, 30, 60, 120, 240]
    assert p["search_surface"]["primary_threshold_cells"] == 45
    assert p["dataset"]["snapshot_id"] == lib.REQUIRED_SNAPSHOT
    assert p["windows"]["development_end_exclusive"] == "2025-01-01T00:00:00Z"
    assert p["refractory"]["minutes"] == 30
    assert "volume" in p["forbidden_gates"]


def test_require_snapshot_matches_repo_manifest():
    assert require_snapshot() == lib.REQUIRED_SNAPSHOT


def test_require_snapshot_fails_on_mismatch(tmp_path: Path):
    man = yaml.safe_load((REPO_ROOT / "docs/manifests/CORE_BTC_BINANCE_V0.yaml").read_text())
    man["snapshot_id"] = "deadbeef"
    p = tmp_path / "m.yaml"
    p.write_text(yaml.safe_dump(man), encoding="utf-8")
    with pytest.raises(lib.H02Error, match="snapshot mismatch"):
        require_snapshot(p)


def test_parse_px_is_numeric_not_lexicographic():
    assert parse_px("10.0") == 10.0
    assert parse_px("9.5") < parse_px("10")


def test_event_bar_fully_known_at_t_not_close_time():
    t = int(datetime(2020, 3, 1, 12, 0, tzinfo=UTC).timestamp() * 1000)
    open_ms = event_bar_open_ms(t)
    assert open_ms + HTF_MS == t
    assert open_ms + HTF_MS - 1 != t


def test_development_cannot_read_2025_outcome():
    t_ok = development_t_max_ms()
    assert t_ok % HTF_MS == 0
    assert_development_outcome_window(t_ok, 240)
    t_bad = t_ok + HTF_MS
    with pytest.raises(ValidationWindowForbidden):
        assert_development_outcome_window(t_bad, 240)
    assert t_ok + 240 * BAR_MS < DEV_END_MS
    assert t_bad + 240 * BAR_MS >= DEV_END_MS


def test_forbid_2025_partition_is_skipped_not_opened(tmp_path: Path):
    monthly = tmp_path / "canonical" / "1m" / "monthly"
    monthly.mkdir(parents=True)
    (monthly / "2024-12.parquet").write_bytes(b"x")
    (monthly / "2025-01.parquet").write_bytes(b"x")
    (monthly / "2026-01.parquet").write_bytes(b"x")
    paths = lib.list_development_parquet_paths(tmp_path)
    names = [p.name for p in paths]
    assert names == ["2024-12.parquet"]


def test_forbid_partition_name_helper():
    with pytest.raises(ValidationWindowForbidden, match="2025"):
        lib._forbid_partition_name("2025-01.parquet")
    with pytest.raises(ValidationWindowForbidden, match="2026"):
        lib._forbid_partition_name("2026-07.parquet")


def test_utc_grid_stable_under_non_utc_tz(monkeypatch):
    monkeypatch.setenv("TZ", "America/New_York")
    os.environ["TZ"] = "America/New_York"
    t = int(datetime(2020, 6, 1, 0, 0, tzinfo=UTC).timestamp() * 1000)
    assert is_grid_ms(t)
    assert not is_grid_ms(t + BAR_MS)
    assert is_grid_ms(t + HTF_MS)
    assert development_t_max_ms() % HTF_MS == 0


def test_plus_6h_wraps_inside_same_utc_day():
    t = int(datetime(2020, 6, 1, 22, 0, tzinfo=UTC).timestamp() * 1000)
    s = shift_plus_6h_same_utc_day(t)
    assert s == int(datetime(2020, 6, 1, 4, 0, tzinfo=UTC).timestamp() * 1000)
    t2 = int(datetime(2020, 6, 1, 1, 0, tzinfo=UTC).timestamp() * 1000)
    s2 = shift_plus_6h_same_utc_day(t2)
    assert s2 == int(datetime(2020, 6, 1, 7, 0, tzinfo=UTC).timestamp() * 1000)


def _frame5(n: int, start_ms: int, open_, high, low, close) -> dict:
    open_ms = start_ms + np.arange(n, dtype=np.int64) * HTF_MS
    return {
        "open_time_ms": open_ms,
        "available_at_ms": open_ms + HTF_MS,
        "t_ms": open_ms + HTF_MS,
        "open": np.asarray(open_, dtype=np.float64),
        "high": np.asarray(high, dtype=np.float64),
        "low": np.asarray(low, dtype=np.float64),
        "close": np.asarray(close, dtype=np.float64),
    }


def _flat_range(n: int, px: float = 100.0, half: float = 1.0):
    opn = np.full(n, px)
    close = np.full(n, px)
    high = np.full(n, px + half)
    low = np.full(n, px - half)
    return opn, high, low, close


def test_prior_range_excludes_event_bar():
    n = 20
    opn, high, low, close = _flat_range(n, 100.0, 1.0)
    high[15] = 150.0
    rh, rl = prior_range(high, low, n_bars=12)
    assert rh[15] == pytest.approx(101.0)
    assert rl[15] == pytest.approx(99.0)
    assert rh[16] == pytest.approx(150.0)


def test_double_sided_breach_excluded():
    n = 30
    opn, high, low, close = _flat_range(n)
    i = 20
    high[i] = 103.0
    low[i] = 97.0
    close[i] = 100.0
    start = int(datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000)
    cl = classify_events(_frame5(n, start, opn, high, low, close), L=60)
    assert bool(cl["double"][i])
    assert not bool(cl["failed"][i])
    assert not bool(cl["success"][i])


def test_open_outside_range_excluded():
    n = 30
    opn, high, low, close = _flat_range(n)
    i = 20
    opn[i] = 102.5
    high[i] = 103.0
    close[i] = 100.0
    start = int(datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000)
    cl = classify_events(_frame5(n, start, opn, high, low, close), L=60)
    assert not bool(cl["open_inside"][i])
    assert not bool(cl["failed"][i])
    assert not bool(cl["success"][i])


def test_breach_and_close_outside_is_successful_not_failed():
    n = 30
    opn, high, low, close = _flat_range(n)
    i = 20
    high[i] = 103.0
    close[i] = 102.2
    start = int(datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000)
    cl = classify_events(_frame5(n, start, opn, high, low, close), L=60)
    assert bool(cl["success_upper"][i])
    assert not bool(cl["failed"][i])
    assert cl["side_success"][i] == DIR_UPPER


def test_failed_upper_and_lower_classification():
    n = 30
    opn, high, low, close = _flat_range(n)
    u, l = 18, 22
    high[u] = 103.0
    close[u] = 100.2
    low[l] = 97.0
    close[l] = 99.8
    start = int(datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000)
    cl = classify_events(_frame5(n, start, opn, high, low, close), L=60)
    assert bool(cl["failed_upper"][u])
    assert cl["side"][u] == DIR_UPPER
    assert cl["overshoot"][u] > 0
    assert bool(cl["failed_lower"][l])
    assert cl["side"][l] == DIR_LOWER


def test_refractory_keeps_earliest_and_collapses_adjacent():
    n = 20
    t = np.arange(n, dtype=np.int64) * HTF_MS
    mask = np.zeros(n, dtype=bool)
    mask[2:10] = True
    kept = apply_refractory(t, mask, refractory_ms=30 * BAR_MS)
    assert list(np.flatnonzero(kept)) == [2, 8]


def test_trailing_scale_uses_only_known_past():
    values = np.array([1.0, 2.0, 3.0, 4.0, 100.0, 5.0], dtype=np.float64)
    med = lib.trailing_median_known(values, window=4, known_lag_steps=1)
    assert med[5] == pytest.approx(3.5)
    med2 = lib.trailing_median_known(values, window=3, known_lag_steps=2)
    assert med2[5] == pytest.approx(3.5)


def test_aggregate_1m_to_5m_ohlc_and_available_at():
    n = 10
    start = int(datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000)
    open_ms = start + np.arange(n) * BAR_MS
    frame1 = {
        "open_time_ms": open_ms,
        "available_at_ms": open_ms + BAR_MS,
        "open": np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], dtype=float),
        "high": np.array([10, 9, 8, 7, 6, 20, 1, 2, 3, 4], dtype=float),
        "low": np.array([0.5, 1, 1, 1, 1, 5, 0.1, 1, 1, 1], dtype=float),
        "close": np.array([2, 3, 4, 5, 6, 7, 8, 9, 10, 11], dtype=float),
    }
    f5 = aggregate_1m_to_5m(frame1)
    assert len(f5["close"]) == 2
    assert f5["open"][0] == 1
    assert f5["close"][0] == 6
    assert f5["high"][0] == 10
    assert f5["low"][0] == 0.5
    assert f5["available_at_ms"][0] == start + HTF_MS
    assert f5["high"][1] == 20
    assert f5["low"][1] == 0.1
    assert "close_time_ms" not in f5


def _patch_windows(start, dev_start, dev_end):
    lib.WARMUP_START_MS = start
    lib.DEV_START_MS = dev_start
    lib.DEV_END_MS = dev_end


def _restore_windows():
    lib.WARMUP_START_MS = int(datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000)
    lib.DEV_START_MS = int(datetime(2020, 2, 1, tzinfo=UTC).timestamp() * 1000)
    lib.DEV_END_MS = int(datetime(2025, 1, 1, tzinfo=UTC).timestamp() * 1000)


def _sine_background(n: int, px: float = 100.0):
    """Non-zero |RET_H| so trailing scale is defined; range stays tight."""
    close = px + 0.04 * np.sin(np.arange(n) / 4.0)
    opn = np.r_[close[0], close[:-1]]
    high = np.maximum(opn, close) + 0.5
    low = np.minimum(opn, close) - 0.5
    return opn, high, low, close


def test_synthetic_A_failed_breakout_mean_reversion_detected():
    start = int(datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000)
    n = 40 * 288
    opn, high, low, close = _sine_background(n)
    for day in range(32, 39):
        for hour in (0, 6, 12, 18):
            i = day * 288 + hour * 12
            # flatten prior 12 bars so the event has a clean range
            opn[i - 12:i] = 100.0
            close[i - 12:i] = 100.0
            high[i - 12:i] = 101.0
            low[i - 12:i] = 99.0
            high[i] = 103.5
            close[i] = 100.1
            opn[i] = 100.0
            low[i] = 99.2
            for k in range(1, 13):
                close[i + k] = 100.0 - 0.15 * k
                opn[i + k] = close[i + k - 1]
                high[i + k] = max(close[i + k], opn[i + k]) + 0.05
                low[i + k] = min(close[i + k], opn[i + k]) - 0.05
    frame = _frame5(n, start, opn, high, low, close)
    _patch_windows(start, start + 32 * 1440 * BAR_MS, start + 40 * 1440 * BAR_MS)
    try:
        panel = lib.build_panel(frame)
        kept = lib.select_population(panel, 60, 0.0, "failed")
        idx = np.flatnonzero(kept)
        assert idx.size >= 8
        b = lib.outcome_bundle(panel, idx, 60, 60, "failed")
        assert b["norm"].size >= 8
        assert float(np.mean(b["rev"])) > 0
        assert float(np.mean(b["norm"])) > 0
    finally:
        _restore_windows()


def test_synthetic_B_successful_breakout_control_weaker_or_adverse():
    start = int(datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000)
    n = 40 * 288
    opn, high, low, close = _sine_background(n)
    for day in range(32, 39):
        for hour in (1, 7, 13, 19):
            i = day * 288 + hour * 12
            opn[i - 12:i] = 100.0
            close[i - 12:i] = 100.0
            high[i - 12:i] = 101.0
            low[i - 12:i] = 99.0
            opn[i] = 100.0
            high[i] = 108.0
            close[i] = 105.0
            low[i] = 99.2
            for k in range(1, 13):
                close[i + k] = 105.0 + 0.4 * k
                opn[i + k] = close[i + k - 1]
                high[i + k] = close[i + k] + 0.05
                low[i + k] = close[i + k] - 0.05
    frame = _frame5(n, start, opn, high, low, close)
    _patch_windows(start, start + 32 * 1440 * BAR_MS, start + 40 * 1440 * BAR_MS)
    try:
        panel = lib.build_panel(frame)
        kept = lib.select_population(panel, 60, 0.10, "success")
        idx = np.flatnonzero(kept)
        assert idx.size >= 4
        b = lib.outcome_bundle(panel, idx, 60, 60, "success")
        assert b["rev"].size >= 4
        assert float(np.mean(b["rev"])) < 0
    finally:
        _restore_windows()


def test_synthetic_C_random_failed_break_timing_no_fabricated_uplift():
    start = int(datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000)
    n = 36 * 288
    rng = np.random.default_rng(11)
    r = rng.normal(0, 0.0004, size=n)
    close = 100.0 * np.exp(np.cumsum(r))
    opn = np.r_[close[0], close[:-1]]
    high = np.maximum(opn, close) * (1 + rng.uniform(0.0005, 0.003, size=n))
    low = np.minimum(opn, close) * (1 - rng.uniform(0.0005, 0.003, size=n))
    frame = _frame5(n, start, opn, high, low, close)
    _patch_windows(start, start + 32 * 1440 * BAR_MS, start + 36 * 1440 * BAR_MS)
    try:
        panel = lib.build_panel(frame)
        kept = lib.select_population(panel, 60, 0.0, "failed")
        idx = np.flatnonzero(kept)
        if idx.size < 5:
            pytest.skip("not enough random failed breaks in fixture")
        b = lib.outcome_bundle(panel, idx, 60, 15, "failed")
        assert abs(float(np.mean(b["norm"]))) < 1.5
    finally:
        _restore_windows()


def test_synthetic_D_time_shift_destroys_injected_timing():
    start = int(datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000)
    n = 40 * 288
    opn, high, low, close = _sine_background(n)
    for day in range(32, 39):
        i = day * 288 + 2 * 12
        opn[i - 12:i] = 100.0
        close[i - 12:i] = 100.0
        high[i - 12:i] = 101.0
        low[i - 12:i] = 99.0
        opn[i] = 100.0
        high[i] = 103.5
        close[i] = 100.1
        low[i] = 99.2
        for k in range(1, 13):
            close[i + k] = 100.0 - 0.2 * k
            opn[i + k] = close[i + k - 1]
            high[i + k] = close[i + k] + 0.02
            low[i + k] = close[i + k] - 0.02
    frame = _frame5(n, start, opn, high, low, close)
    _patch_windows(start, start + 32 * 1440 * BAR_MS, start + 40 * 1440 * BAR_MS)
    try:
        panel = lib.build_panel(frame)
        kept = lib.select_population(panel, 60, 0.0, "failed")
        idx = np.flatnonzero(kept)
        cand = lib.outcome_bundle(panel, idx, 60, 60, "failed")
        assert float(np.mean(cand["rev"])) > 0
        shifted = lib.time_shift_bundle(panel, cand, 60, 60)
        assert shifted["N"] >= 1
        assert shifted["mean_norm_rev"] < float(np.mean(cand["norm"]))
    finally:
        _restore_windows()


def test_future_return_reads_only_after_t():
    start = int(datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000)
    n = 50
    close = np.full(n, 100.0)
    close[10] = 120.0
    close[13] = 80.0
    opn = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    frame = _frame5(n, start, opn, high, low, close)
    _patch_windows(start, start, start + (n + 200) * HTF_MS)
    try:
        lib.DEV_END_MS = start + (n + 400) * HTF_MS
        panel = lib.build_panel(frame)
        i = 10
        ret = np.log(close[i + 3] / close[i])
        assert ret == pytest.approx(np.log(80.0 / 120.0))
        assert panel["ret"][15][i] == pytest.approx(ret)
        close2 = close.copy()
        close2[9] = 50.0
        frame2 = _frame5(n, start, opn, high, low, close2)
        panel2 = lib.build_panel(frame2)
        assert panel2["ret"][15][i] == pytest.approx(ret)
    finally:
        _restore_windows()
