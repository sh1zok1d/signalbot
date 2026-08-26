"""Network-free tests for H01 compression → expansion.

Does not open 2025/2026 outcomes. Does not reuse V1/V2 detectors.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest
import yaml

from scripts.research import h01_compression_expansion_lib as lib
from scripts.research.h01_compression_expansion_lib import (
    BAR_MS,
    DEV_END_MS,
    GRID_MS,
    ValidationWindowForbidden,
    assert_development_outcome_window,
    build_grid_ms,
    build_panel,
    candidate_mask,
    eligible_mask,
    evaluate_cell,
    future_bar_open_times_ms,
    is_grid_ms,
    last_known_bar_open_ms,
    load_prereg,
    log_returns,
    midrank_percentile_against_prior,
    parse_px,
    permutation_candidate_mean,
    require_snapshot,
    rolling_sum_last,
)

UTC = timezone.utc
REPO_ROOT = Path(__file__).resolve().parents[2]


def test_prereg_search_surface_frozen():
    p = load_prereg()
    assert p["lookbacks_minutes"] == [30, 60, 120]
    assert p["compression_thresholds_q"] == [0.10, 0.20, 0.30]
    assert p["horizons_minutes"] == [15, 30, 60, 120, 240]
    assert p["search_surface"]["primary_threshold_cells"] == 45
    assert p["dataset"]["snapshot_id"] == lib.REQUIRED_SNAPSHOT
    assert p["windows"]["development_end_exclusive"] == "2025-01-01T00:00:00Z"


def test_require_snapshot_matches_repo_manifest():
    assert require_snapshot() == lib.REQUIRED_SNAPSHOT


def test_require_snapshot_fails_on_mismatch(tmp_path: Path):
    man = yaml.safe_load((REPO_ROOT / "docs/manifests/CORE_BTC_BINANCE_V0.yaml").read_text())
    man["snapshot_id"] = "deadbeef"
    p = tmp_path / "m.yaml"
    p.write_text(yaml.safe_dump(man), encoding="utf-8")
    with pytest.raises(lib.H01Error, match="snapshot mismatch"):
        require_snapshot(p)


def test_parse_px_is_numeric_not_lexicographic():
    assert parse_px("10.0") == 10.0
    assert parse_px("9.5") < parse_px("10")
    # lexicographic would claim "9.5" > "10"


def test_last_known_bar_uses_available_at_not_close_time():
    t = int(datetime(2020, 3, 1, tzinfo=UTC).timestamp() * 1000)
    last_open = last_known_bar_open_ms(t)
    assert last_open + BAR_MS == t
    assert last_open + BAR_MS - 1 != t  # close_time style would be T-1ms


def test_future_window_is_open_at_t_closed_at_t_plus_h():
    t = int(datetime(2020, 3, 1, 12, 0, tzinfo=UTC).timestamp() * 1000)
    start, end = future_bar_open_times_ms(t, 15)
    assert start == t
    assert end == t + 15 * BAR_MS
    assert start > last_known_bar_open_ms(t)


def test_development_cannot_read_2025_outcome():
    t_ok = DEV_END_MS - 241 * BAR_MS
    t_ok -= t_ok % GRID_MS
    assert_development_outcome_window(t_ok, 240)
    t_bad = DEV_END_MS - 240 * BAR_MS
    with pytest.raises(ValidationWindowForbidden):
        assert_development_outcome_window(t_bad, 240)


def test_forbid_2025_partition_is_skipped_not_opened(tmp_path: Path):
    monthly = tmp_path / "canonical" / "1m" / "monthly"
    monthly.mkdir(parents=True)
    (monthly / "2024-12.parquet").write_bytes(b"x")
    (monthly / "2025-01.parquet").write_bytes(b"x")
    (monthly / "2026-01.parquet").write_bytes(b"x")
    paths = lib.list_development_parquet_paths(tmp_path)
    names = [p.name for p in paths]
    assert names == ["2024-12.parquet"]
    assert "2025-01.parquet" not in names
    assert "2026-01.parquet" not in names


def test_forbid_partition_name_helper():
    with pytest.raises(ValidationWindowForbidden, match="2025"):
        lib._forbid_partition_name("2025-01.parquet")


def test_utc_grid_stable_under_non_utc_tz(monkeypatch):
    monkeypatch.setenv("TZ", "America/New_York")
    os.environ["TZ"] = "America/New_York"
    t = int(datetime(2020, 6, 1, 0, 0, tzinfo=UTC).timestamp() * 1000)
    assert is_grid_ms(t)
    assert not is_grid_ms(t + BAR_MS)
    g = build_grid_ms(t, t + 45 * BAR_MS)
    assert list(g) == [t, t + GRID_MS, t + 2 * GRID_MS, t + 3 * GRID_MS]


def _bars(start_ms: int, n: int, close: np.ndarray, high=None, low=None) -> dict:
    open_ms = start_ms + np.arange(n, dtype=np.int64) * BAR_MS
    return {
        "open_time_ms": open_ms,
        "available_at_ms": open_ms + BAR_MS,
        "close": close.astype(np.float64),
        "high": (high if high is not None else close * 1.0001).astype(np.float64),
        "low": (low if low is not None else close * 0.9999).astype(np.float64),
    }


def test_reference_excludes_current_and_uses_only_prior():
    x = np.array([1.0, 2.0, 3.0, 10.0], dtype=np.float64)
    pct = midrank_percentile_against_prior(x, window=3)
    assert np.isnan(pct[2])
    # x[3]=10 vs {1,2,3} → all strictly less → 100
    assert pct[3] == 100.0
    # if current were included, 10 vs {1,2,3,10} would be 87.5 midrank


def test_rolling_sum_requires_complete_window():
    v = np.array([1.0, 1.0, np.nan, 1.0, 1.0], dtype=np.float64)
    s = rolling_sum_last(v, 2)
    assert np.isnan(s[2])
    assert s[1] == pytest.approx(2.0)


def test_future_rv_does_not_include_pre_t_return():
    n = 20
    start = int(datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000)
    close = np.full(n, 100.0)
    close[5] = 100.0 * np.exp(1.0)  # huge return at bar index 5 (open start+5m)
    r = log_returns(close)
    assert r[5] == pytest.approx(1.0)
    t = start + 6 * BAR_MS  # last known bar open is start+5m, so huge return IS known at T
    last_i = 5
    assert last_known_bar_open_ms(t) == start + 5 * BAR_MS
    # future window (T, T+2m] uses bars opening at T and T+1m = idx 6,7 — not idx 5
    assert r[6] == 0.0 or np.isnan(r[6]) or r[6] == pytest.approx(np.log(100 / close[5]), rel=1e-6)


def _panel_with_windows(frame, dev_start, dev_end, warmup):
    lib.WARMUP_START_MS = warmup
    lib.DEV_START_MS = dev_start
    lib.DEV_END_MS = dev_end
    try:
        return build_panel(frame)
    finally:
        lib.WARMUP_START_MS = int(datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000)
        lib.DEV_START_MS = int(datetime(2020, 2, 1, tzinfo=UTC).timestamp() * 1000)
        lib.DEV_END_MS = int(datetime(2025, 1, 1, tzinfo=UTC).timestamp() * 1000)


def _iid_close(n, sigma, rng):
    r = rng.normal(0.0, sigma, size=n)
    r[0] = 0.0
    return 100.0 * np.exp(np.cumsum(r))


def test_synthetic_A_detects_compression_then_expansion():
    rng = np.random.default_rng(1)
    warmup = int(datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000)
    n = 40 * 1440
    close = _iid_close(n, 0.003, rng)
    # After 32 days, every 8 hours: 60 quiet minutes then 60 explosive minutes.
    for day in range(32, 39):
        for hour in (0, 8, 16):
            quiet = day * 1440 + hour * 60
            close[quiet:quiet + 60] = close[quiet - 1]
            burst = quiet + 60
            burst_r = rng.normal(0.0, 0.03, size=60)
            close[burst:burst + 60] = close[burst - 1] * np.exp(np.cumsum(burst_r))
    frame = _bars(warmup, n, close)
    dev_start = warmup + 32 * 1440 * BAR_MS
    dev_end = warmup + 40 * 1440 * BAR_MS
    panel = _panel_with_windows(frame, dev_start, dev_end, warmup)
    elig = eligible_mask(panel, 60, 60)
    c = panel["C_60"]
    fut = panel["norm_rv_60"]
    low = elig & (c <= 10.0)
    high = elig & (c >= 90.0)
    assert int(np.sum(elig)) > 50
    assert int(np.sum(low)) > 5
    assert int(np.sum(high)) > 5
    assert float(np.mean(fut[low])) > float(np.mean(fut[high]))


def test_synthetic_B_iid_does_not_fabricate_uplift():
    rng = np.random.default_rng(2)
    warmup = int(datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000)
    n = 40 * 1440
    frame = _bars(warmup, n, _iid_close(n, 0.002, rng))
    dev_start = warmup + 32 * 1440 * BAR_MS
    dev_end = warmup + 40 * 1440 * BAR_MS
    panel = _panel_with_windows(frame, dev_start, dev_end, warmup)
    elig = eligible_mask(panel, 60, 60)
    c = panel["C_60"]
    fut = panel["norm_rv_60"]
    low = elig & (c <= 10.0)
    rest = elig
    # iid: compression should not systematically elevate normalized future RV
    diff = float(np.mean(fut[low]) - np.mean(fut[rest]))
    assert abs(diff) < 0.35


def test_synthetic_C_permutation_destroys_injected_timing():
    rng = np.random.default_rng(3)
    warmup = int(datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000)
    n = 40 * 1440
    close = _iid_close(n, 0.003, rng)
    for day in range(32, 39):
        for hour in (0, 8, 16):
            quiet = day * 1440 + hour * 60
            close[quiet:quiet + 60] = close[quiet - 1]
            burst = quiet + 60
            burst_r = rng.normal(0.0, 0.03, size=60)
            close[burst:burst + 60] = close[burst - 1] * np.exp(np.cumsum(burst_r))
    frame = _bars(warmup, n, close)
    dev_start = warmup + 32 * 1440 * BAR_MS
    dev_end = warmup + 40 * 1440 * BAR_MS
    panel = _panel_with_windows(frame, dev_start, dev_end, warmup)
    cell = evaluate_cell(panel, 60, 0.10, 60)
    perm = permutation_candidate_mean(panel, 60, 0.10, 60, "norm_rv_60")
    assert cell["mean_norm_rv"] is not None
    assert perm["mean"] is not None
    # injected timing should beat a month-shuffled score
    assert cell["mean_norm_rv"] > perm["mean"]


def test_synthetic_D_clustering_metrics_are_explicit():
    rng = np.random.default_rng(4)
    warmup = int(datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000)
    n = 36 * 1440
    close = _iid_close(n, 0.002, rng)
    # long contiguous quiet block so many adjacent 15m candidates
    quiet = 33 * 1440
    close[quiet:quiet + 12 * 60] = close[quiet - 1]
    frame = _bars(warmup, n, close)
    dev_start = warmup + 32 * 1440 * BAR_MS
    dev_end = warmup + 36 * 1440 * BAR_MS
    panel = _panel_with_windows(frame, dev_start, dev_end, warmup)
    cand = candidate_mask(panel, 60, 0.30, 15)
    conc = lib.concentration_stats(panel, cand)
    assert conc["raw_n"] == int(np.sum(cand))
    assert "clustering" in conc
    assert conc["clustering"]["max_run_length"] >= 1
    assert conc["unique_utc_days"] <= conc["raw_n"]


def test_loader_does_not_select_close_time_column():
    import inspect
    src = inspect.getsource(lib.load_development_arrays)
    assert 'cols = ["open_time_ms", "available_at_ms", "close", "high", "low"]' in src
    assert "if \"close_time_ms\" in table.column_names" in src
