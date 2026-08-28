"""Network-free tests for H03 extreme-impulse continuation/exhaustion.

Preregistration + implementation-freeze task: these tests use only local,
in-memory synthetic fixtures. They never open real accepted parquet, never
inspect 2025 validation or 2026 OOS outcomes, and never run development
against real market data.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest
import yaml

from scripts.research import h03_extreme_impulse_lib as lib
from scripts.research.h03_extreme_impulse_lib import (
    BAR_MS,
    DIR_DOWN,
    DIR_UP,
    HTF_MIN,
    HTF_MS,
    MAX_H_MIN,
    ValidationWindowForbidden,
    aggregate_1m_to_15m,
    apply_refractory,
    assert_development_outcome_window,
    build_matched_random_pool,
    build_panel,
    collision_fraction,
    compute_horizon_return,
    compute_impulse_returns,
    control_gate,
    decile_bin,
    decile_diagnostic_for_cell,
    development_t_max_ms,
    direction_of,
    extreme_candidate_mask,
    is_grid_ms,
    load_prereg,
    long_dependence_diagnostic,
    moderate_band_mask,
    mpie_gate,
    negative_control_bundle,
    normalize,
    n_eff_h,
    n_eff_w,
    outcome_bundle,
    parse_px,
    require_snapshot,
    rolling_midrank_percentile,
    sample_matched_random_once,
    shift_plus_6h_same_utc_day,
    symmetric_claim_verdict,
    total_variation_distance,
    trailing_median_known,
    utc_day_key,
    utc_dom_key,
    utc_dow_key,
)

UTC = timezone.utc
REPO_ROOT = Path(__file__).resolve().parents[2]
DAY_BARS = 24 * 60 // HTF_MIN  # 96 fifteen-minute bars per UTC day


# ---------------------------------------------------------------------------
# infra / identity sanity (not one of the 36 enumerated scenarios, but
# minimal hygiene matching H01/H02 precedent)
# ---------------------------------------------------------------------------
def test_prereg_frozen_numbers():
    p = load_prereg()
    assert p["impulse_windows_minutes"] == [15, 30, 60]
    assert p["horizons_minutes"] == [15, 30, 60, 120, 240]
    assert p["extremeness"]["thresholds_q"] == [0.90, 0.95, 0.98]
    assert p["search_surface"]["primary_threshold_cells"] == 45
    assert p["dataset"]["snapshot_id"] == lib.REQUIRED_SNAPSHOT
    assert p["windows"]["development_end_exclusive"] == "2025-01-01T00:00:00Z"
    assert p["refractory"]["minutes"] == 60
    assert p["matched_random"]["seed"] == 20260831
    assert p["uncertainty"]["seed"] == 20260901


def test_require_snapshot_matches_repo_manifest():
    assert require_snapshot() == lib.REQUIRED_SNAPSHOT


def test_require_snapshot_fails_on_mismatch(tmp_path: Path):
    man = yaml.safe_load((REPO_ROOT / "docs/manifests/CORE_BTC_BINANCE_V0.yaml").read_text())
    man["snapshot_id"] = "deadbeef"
    p = tmp_path / "m.yaml"
    p.write_text(yaml.safe_dump(man), encoding="utf-8")
    with pytest.raises(lib.H03Error, match="snapshot mismatch"):
        require_snapshot(p)


def test_parse_px_is_numeric_not_lexicographic():
    assert parse_px("10.0") == 10.0
    assert parse_px("9.5") < parse_px("10")


# ---------------------------------------------------------------------------
# fixture builders
# ---------------------------------------------------------------------------
def _frame15(n: int, start_ms: int, open_, high, low, close) -> dict:
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


def _tiny_noise_background(n: int, px: float = 100.0, seed: int = 7):
    rng = np.random.default_rng(seed)
    close = px * np.exp(np.cumsum(rng.normal(0, 0.00005, size=n)))
    opn = np.r_[close[0], close[:-1]]
    high = np.maximum(opn, close) + 0.01
    low = np.minimum(opn, close) - 0.01
    return opn, high, low, close


def _inject_and_rebase(opn, high, low, close, i, jump_mult, drift_mult, k_steps=4, pad=0.01):
    """Inject an impulse at i (jump_mult) followed by k_steps of per-bar
    drift (drift_mult), then rebase everything after the injected window by
    the realized ratio so the untouched background continues smoothly from
    the new level -- without this, the original (pre-injection) background
    at i+k_steps+1 would create an artificial snap back to the old level,
    fabricating a spurious reversal/continuation unrelated to the injected
    mechanism."""
    j = i + k_steps
    orig_j = close[j]
    pre = close[i - 1]
    close[i] = pre * jump_mult
    opn[i] = pre
    high[i] = max(close[i], opn[i]) + pad
    low[i] = min(close[i], opn[i]) - pad
    for k in range(1, k_steps + 1):
        close[i + k] = close[i + k - 1] * drift_mult
        opn[i + k] = close[i + k - 1]
        high[i + k] = close[i + k] + pad
        low[i + k] = close[i + k] - pad
    ratio = close[j] / orig_j
    close[j + 1:] *= ratio
    opn[j + 1:] *= ratio
    high[j + 1:] *= ratio
    low[j + 1:] *= ratio


def _manual_panel(t_ms, close, high, low, w_minutes, p_w, impulse, h_minutes, ret, scale, in_dev=None):
    n = len(t_ms)
    if in_dev is None:
        in_dev = np.ones(n, dtype=bool)
    return {
        "t_ms": t_ms, "close": close, "high": high, "low": low,
        "in_development": in_dev,
        "impulse": {w_minutes: impulse},
        "p_w": {w_minutes: p_w},
        "direction": {w_minutes: direction_of(impulse)},
        "ret": {h_minutes: ret},
        "scale": {h_minutes: scale},
        "month_key": np.array([lib.utc_month_key(int(x)) for x in t_ms]),
        "week_key": np.array([lib.utc_week_key(int(x)) for x in t_ms]),
        "year": np.array([lib.utc_year(int(x)) for x in t_ms], dtype=np.int16),
        "dow_key": np.array([lib.utc_dow_key(int(x)) for x in t_ms]),
        "dom_key": np.array([lib.utc_dom_key(int(x)) for x in t_ms]),
    }


def _patch_dev(monkeypatch, start_ms, dev_start_ms, dev_end_ms, ref_steps, w_windows=(15,), horizons=(60,)):
    monkeypatch.setattr(lib, "WARMUP_START_MS", start_ms)
    monkeypatch.setattr(lib, "DEV_START_MS", dev_start_ms)
    monkeypatch.setattr(lib, "DEV_END_MS", dev_end_ms)
    monkeypatch.setattr(lib, "REF_STEPS", ref_steps)
    monkeypatch.setattr(lib, "W_WINDOWS", w_windows)
    monkeypatch.setattr(lib, "HORIZONS", horizons)


# ---------------------------------------------------------------------------
# 1. T == bar_end_exclusive semantics
# ---------------------------------------------------------------------------
def test_01_t_is_bar_end_exclusive():
    n = 30
    start = int(datetime(2020, 3, 1, tzinfo=UTC).timestamp() * 1000)
    open_ms = start + np.arange(n, dtype=np.int64) * BAR_MS
    frame1 = {
        "open_time_ms": open_ms,
        "available_at_ms": open_ms + BAR_MS,
        "open": np.linspace(100, 101, n),
        "high": np.linspace(100, 101, n) + 0.1,
        "low": np.linspace(100, 101, n) - 0.1,
        "close": np.linspace(100, 101, n),
    }
    f15 = aggregate_1m_to_15m(frame1)
    assert f15["t_ms"][0] == open_ms[0] + HTF_MS
    assert np.array_equal(f15["t_ms"], f15["available_at_ms"])
    assert np.array_equal(f15["t_ms"], f15["open_time_ms"] + HTF_MS)


# ---------------------------------------------------------------------------
# 2. close(T) and close(T-W) off-by-one correctness
# ---------------------------------------------------------------------------
def test_02_impulse_close_offsets_exact():
    close = np.array([100.0, 101.0, 102.0, 103.0, 105.0, 108.0])
    imp = compute_impulse_returns(close, 30)  # step = 30/15 = 2
    assert np.isnan(imp[0])
    assert np.isnan(imp[1])
    assert imp[2] == pytest.approx(np.log(close[2] / close[0]))
    assert imp[5] == pytest.approx(np.log(close[5] / close[3]))


# ---------------------------------------------------------------------------
# 3. impulse uses no data after T
# ---------------------------------------------------------------------------
def test_03_impulse_no_lookahead():
    close = np.array([100.0, 101.0, 102.0, 103.0, 104.0, 105.0])
    imp_a = compute_impulse_returns(close, 15)  # step = 1
    close2 = close.copy()
    close2[4:] = 999.0
    imp_b = compute_impulse_returns(close2, 15)
    assert imp_a[3] == pytest.approx(imp_b[3])


# ---------------------------------------------------------------------------
# 4 & 5. percentile reference contains only timestamps < T; current T excluded
# ---------------------------------------------------------------------------
def test_04_05_percentile_reference_excludes_current_and_future():
    values = np.concatenate([np.zeros(5), np.array([100.0]), np.zeros(4)])
    p = rolling_midrank_percentile(values, window=5)
    assert p[5] == pytest.approx(1.0)
    values2 = values.copy()
    values2[6:] = 500.0
    p2 = rolling_midrank_percentile(values2, window=5)
    assert p2[5] == pytest.approx(p[5])


# ---------------------------------------------------------------------------
# 6. percentile midrank tie handling exact
# ---------------------------------------------------------------------------
def test_06_percentile_midrank_ties_exact():
    values = np.array([1.0, 2.0, 2.0, 2.0, 3.0, 2.0])
    p = rolling_midrank_percentile(values, window=5)
    # ref = values[0:5] = [1,2,2,2,3], x = values[5] = 2
    # (count(ref<x) + 0.5*count(ref==x)) / N_ref = (1 + 0.5*3) / 5 = 0.5
    assert p[5] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# 7. q90/q95/q98 qualification exact
# ---------------------------------------------------------------------------
def test_07_extreme_candidate_mask_thresholds_exact():
    p_w = np.array([0.85, 0.90, 0.95, 0.98, 1.0, np.nan])
    imp = np.array([0.01, 0.01, -0.01, 0.02, 0.02, 0.02])
    cases = {
        0.90: [False, True, True, True, True, False],
        0.95: [False, False, True, True, True, False],
        0.98: [False, False, False, True, True, False],
    }
    for q, expect in cases.items():
        mask = extreme_candidate_mask(p_w, imp, q)
        assert list(mask) == expect


# ---------------------------------------------------------------------------
# 8. 60m refractory keeps earliest and suppresses either direction
# ---------------------------------------------------------------------------
def test_08_refractory_keeps_earliest_suppresses_either_direction():
    n = 10
    t = np.arange(n, dtype=np.int64) * HTF_MS
    mask = np.zeros(n, dtype=bool)
    mask[[1, 2, 3, 7]] = True
    direction = np.zeros(n, dtype=np.int8)
    direction[1] = DIR_UP
    direction[2] = DIR_DOWN  # opposite direction, still inside the refractory window
    direction[3] = DIR_UP
    direction[7] = DIR_DOWN
    kept = apply_refractory(t, mask, refractory_ms=lib.REFRACTORY_MS)
    assert list(np.flatnonzero(kept)) == [1, 7]
    assert not kept[2]  # suppressed despite opposite sign from index 1
    assert not kept[3]


# ---------------------------------------------------------------------------
# 9. T+H boundary cannot read 2025
# ---------------------------------------------------------------------------
def test_09_boundary_embargo_rejects_crossing_2025():
    t_ok = development_t_max_ms()
    assert_development_outcome_window(t_ok, MAX_H_MIN)
    t_bad = t_ok + HTF_MS
    with pytest.raises(ValidationWindowForbidden):
        assert_development_outcome_window(t_bad, MAX_H_MIN)


# ---------------------------------------------------------------------------
# 10. no horizon truncation
# ---------------------------------------------------------------------------
def test_10_horizon_return_no_truncation_at_boundary():
    n = 20
    close = 100.0 + np.arange(n, dtype=np.float64)
    t_ms = np.arange(n, dtype=np.int64) * HTF_MS
    dev_end = t_ms[10] + 60 * BAR_MS
    r = compute_horizon_return(close, t_ms, 60, dev_end_ms=dev_end)
    for i in range(10):
        assert np.isfinite(r[i])
    # within array bounds (dst = i+4 < 20 up to i=15) but crosses/at dev_end:
    # must be NaN, never a truncated shorter-horizon value.
    for i in range(10, 16):
        assert np.isnan(r[i])


# ---------------------------------------------------------------------------
# 11. normalization history contains only fully resolved pre-T H outcomes
# ---------------------------------------------------------------------------
def test_11_trailing_scale_uses_only_resolved_pre_t():
    values = np.array([1.0, 2.0, 3.0, 4.0, 100.0, 5.0], dtype=np.float64)
    med = trailing_median_known(values, window=4, known_lag_steps=1)
    assert med[5] == pytest.approx(3.5)
    med2 = trailing_median_known(values, window=3, known_lag_steps=2)
    assert med2[5] == pytest.approx(3.5)


# ---------------------------------------------------------------------------
# 12. zero/non-finite denominator becomes explicitly ineligible
# ---------------------------------------------------------------------------
def test_12_normalize_zero_or_nonfinite_denominator_is_ineligible():
    cont_ret = np.array([0.01, 0.02, 0.03, 0.04])
    scale = np.array([0.0, np.nan, -1.0, 0.5])
    norm, elig = normalize(cont_ret, scale)
    assert list(elig) == [False, False, False, True]
    assert np.isnan(norm[0]) and np.isnan(norm[1]) and np.isnan(norm[2])
    assert norm[3] == pytest.approx(0.08)


# ---------------------------------------------------------------------------
# 13. no full-development normalization floor exists
# ---------------------------------------------------------------------------
def test_13_no_full_development_floor_tiny_scale_still_used():
    cont_ret = np.array([0.01])
    scale = np.array([1e-9])
    norm, elig = normalize(cont_ret, scale)
    assert elig[0]
    assert norm[0] == pytest.approx(0.01 / 1e-9)
    p = load_prereg()
    assert p["normalization"]["full_development_floor_used"] is False
    assert p["normalization"]["post_outcome_floor_or_winsorization_allowed"] is False


# ---------------------------------------------------------------------------
# 14. N_eff_W calculation exact
# ---------------------------------------------------------------------------
def test_14_n_eff_w_exact():
    assert n_eff_w(15) == 2880
    assert n_eff_w(30) == 1440
    assert n_eff_w(60) == 720


# ---------------------------------------------------------------------------
# 15. N_eff_H calculation exact
# ---------------------------------------------------------------------------
def test_15_n_eff_h_exact():
    assert n_eff_h(15) == 2880
    assert n_eff_h(30) == 1440
    assert n_eff_h(60) == 720
    assert n_eff_h(120) == 360
    assert n_eff_h(240) == 180


# ---------------------------------------------------------------------------
# 16. matched-random raw extreme timestamps excluded
# ---------------------------------------------------------------------------
def test_16_matched_random_pool_excludes_raw_extremes():
    all_idx = np.arange(20)
    raw_idx = np.array([3, 7, 12])
    pool = build_matched_random_pool(all_idx, raw_idx)
    assert 3 not in pool and 7 not in pool and 12 not in pool
    assert pool.size == 17

    # evaluate_cell passes eligible *panel* indices, not 0..n-1 positions.
    # Fancy-indexing those ids into len(elig) IndexErrors on real data
    # (eligible development length 172400; panel ids such as 172517).
    panel_idx = np.array([100, 250, 172400, 172517, 200000], dtype=np.int64)
    raw_panel = np.array([172517, 100], dtype=np.int64)
    pool_panel = build_matched_random_pool(panel_idx, raw_panel)
    assert 172517 not in pool_panel and 100 not in pool_panel
    assert 250 in pool_panel and 172400 in pool_panel and 200000 in pool_panel
    assert pool_panel.size == 3


def test_16c_original_fancy_index_crash_and_membership_semantics():
    """Synthetic reproduction of the e2c370d IndexError class.

    evaluate_cell passes eligible *panel ids* (not 0..n-1 positions) into
    build_matched_random_pool. The pre-fix body fancy-indexed those ids into
    len(elig) and crashed on real development (elig length 172400, panel id
    172517). The frozen intended semantics are membership exclusion of the
    exact raw extreme ids, with no surrounding-regime deletion.

    Does not open parquet. Does not change production research parameters.
    """
    def _pre_fix_fancy_index(all_grid_idx, raw_extreme_idx):
        excluded = np.zeros(len(all_grid_idx), dtype=bool)
        excluded[raw_extreme_idx] = True
        return all_grid_idx[~excluded]

    elig = np.array([2976, 2977, 10000, 172400, 172517], dtype=np.int64)
    raw = np.array([172517, 2976], dtype=np.int64)

    with pytest.raises(IndexError):
        _pre_fix_fancy_index(elig, raw)

    pool = build_matched_random_pool(elig, raw)
    assert 172517 not in pool.tolist() and 2976 not in pool.tolist()
    assert 2977 in pool.tolist() and 10000 in pool.tolist() and 172400 in pool.tolist()
    assert pool.size == 3
    assert sorted(pool.tolist()) == [2977, 10000, 172400]

    # On a 0..n-1 grid the two implementations agree (semantics-preserving
    # for the original synthetic fixtures).
    grid = np.arange(20, dtype=np.int64)
    raw_small = np.array([3, 7, 12], dtype=np.int64)
    np.testing.assert_array_equal(
        _pre_fix_fancy_index(grid, raw_small),
        build_matched_random_pool(grid, raw_small),
    )


# ---------------------------------------------------------------------------
# 17. matched-random sampling is without replacement within replicate
# ---------------------------------------------------------------------------
def test_17_matched_random_sampling_without_replacement():
    rng = np.random.default_rng(1)
    pool_by_month = {"2020-01": np.arange(5)}
    need_up = {"2020-01": 3}
    need_down = {"2020-01": 2}
    picked, labels = sample_matched_random_once(rng, pool_by_month, need_up, need_down)
    assert picked.size == 5
    assert len(set(picked.tolist())) == 5
    assert sorted(picked.tolist()) == [0, 1, 2, 3, 4]
    assert labels.size == 5


# ---------------------------------------------------------------------------
# 18. random pool does not delete surrounding regime timestamps
# ---------------------------------------------------------------------------
def test_18_pool_preserves_surrounding_regime_timestamps():
    all_idx = np.arange(10)
    raw_idx = np.array([5])
    pool = build_matched_random_pool(all_idx, raw_idx)
    assert 4 in pool and 6 in pool
    assert 5 not in pool


# ---------------------------------------------------------------------------
# 19. month/direction composition preservation
# ---------------------------------------------------------------------------
def test_19_matched_random_preserves_month_direction_composition():
    rng = np.random.default_rng(2)
    pool_by_month = {"2020-01": np.arange(10), "2020-02": np.arange(10, 20)}
    need_up = {"2020-01": 2, "2020-02": 1}
    need_down = {"2020-01": 1, "2020-02": 2}
    picked, labels = sample_matched_random_once(rng, pool_by_month, need_up, need_down)
    assert int(np.sum(labels == DIR_UP)) == 3
    assert int(np.sum(labels == DIR_DOWN)) == 3
    jan_picked = picked[np.isin(picked, pool_by_month["2020-01"])]
    assert jan_picked.size == 3


# ---------------------------------------------------------------------------
# 20. TVD diagnostic exact
# ---------------------------------------------------------------------------
def test_20_total_variation_distance_exact():
    a = {"0": 3, "1": 1}
    b = {"0": 2, "1": 2}
    assert total_variation_distance(a, b) == pytest.approx(0.25)


def test_20b_tvd_identical_distributions_zero():
    a = {"0": 10, "1": 20, "2": 30}
    b = {"0": 10, "1": 20, "2": 30}
    assert total_variation_distance(a, b) == pytest.approx(0.0)


def test_20c_tvd_disjoint_distributions_one():
    a = {"Mon": 5, "Tue": 5}
    b = {"Wed": 3, "Thu": 7}
    assert total_variation_distance(a, b) == pytest.approx(1.0)


def test_20d_tvd_small_perturbation_between_zero_and_one():
    a = {"0": 50, "1": 50}
    b = {"0": 55, "1": 45}
    tvd = total_variation_distance(a, b)
    assert 0.0 < tvd < 1.0
    assert tvd == pytest.approx(0.05)


def test_20e_tvd_same_proportions_different_n_zero():
    a = {"0": 1, "1": 2, "2": 3}
    b = {"0": 10, "1": 20, "2": 30}
    assert total_variation_distance(a, b) == pytest.approx(0.0)


def test_20f_tvd_missing_category_union_handling():
    # b lacks key "2"; explicit zero on a is equivalent to a missing key on b.
    a = {"0": 50, "1": 50, "2": 0}
    b = {"0": 50, "1": 50}
    assert total_variation_distance(a, b) == pytest.approx(0.0)
    a2 = {"0": 100}
    b2 = {"0": 50, "1": 50}
    assert total_variation_distance(a2, b2) == pytest.approx(0.5)


def test_20g_panel_index_as_ms_explains_reported_huge_tvd():
    """Forensic (synthetic): utc_dow_key/utc_dom_key of typical panel ids
    all collapse to 1970-01-01 (Thursday='3', DOM='01'). A near-uniform
    candidate DOW vs a point mass on '3' has TVD = 6/7 ≈ 0.857; a 30-day
    uniform DOM vs point mass on '01' has TVD = 29/30 ≈ 0.967. These match
    the reported residual TVD magnitudes. The TVD *formula* is correct; the
    matched-side *keys* in matched_random_bundle were panel ids, not
    timestamps. Descriptive only — this test does not invoke real parquet.
    """
    for idx in (100, 172400, 172517, 200000):
        assert utc_dow_key(int(idx)) == "3"
        assert utc_dom_key(int(idx)) == "01"
    real_dow = {str(i): 1000 for i in range(7)}
    buggy_dow = {"3": 7000}
    assert total_variation_distance(real_dow, buggy_dow) == pytest.approx(6.0 / 7.0)
    real_dom = {f"{d:02d}": 100 for d in range(1, 31)}
    buggy_dom = {"01": 3000}
    assert total_variation_distance(real_dom, buggy_dom) == pytest.approx(29.0 / 30.0)


# ---------------------------------------------------------------------------
# 21. +6h circular wrap exact
# ---------------------------------------------------------------------------
def test_21_plus_6h_circular_wrap_exact():
    t = int(datetime(2020, 6, 1, 22, 0, tzinfo=UTC).timestamp() * 1000)
    s = shift_plus_6h_same_utc_day(t)
    assert s == int(datetime(2020, 6, 1, 4, 0, tzinfo=UTC).timestamp() * 1000)
    t2 = int(datetime(2020, 6, 1, 1, 0, tzinfo=UTC).timestamp() * 1000)
    s2 = shift_plus_6h_same_utc_day(t2)
    assert s2 == int(datetime(2020, 6, 1, 7, 0, tzinfo=UTC).timestamp() * 1000)


# ---------------------------------------------------------------------------
# 22. +6h collision-rate reporting exact
# ---------------------------------------------------------------------------
def test_22_collision_fraction_exact():
    shifted = np.array([100, 200, 300, 400])
    raw = np.array([200, 400, 999])
    assert collision_fraction(shifted, raw) == pytest.approx(0.5)
    assert collision_fraction(np.array([]), raw) == 0.0


# ---------------------------------------------------------------------------
# 23. moderate-momentum structural control exact
# ---------------------------------------------------------------------------
def test_23_moderate_band_mask_exact():
    p_w = np.array([0.59, 0.60, 0.75, 0.80, np.nan])
    imp = np.array([0.01, 0.01, -0.01, 0.01, 0.01])
    mask = moderate_band_mask(p_w, imp)
    assert list(mask) == [False, True, True, False, False]


# ---------------------------------------------------------------------------
# 24. CONTROL_DELTA_MIN=0.05 gate exact
# ---------------------------------------------------------------------------
def test_24_control_delta_min_gate_exact_boundary():
    assert control_gate(0.20, 0.10, DIR_UP) is True     # diff 0.10 >> delta_min, passes
    assert control_gate(0.149, 0.10, DIR_UP) is False   # diff 0.049, just under
    # boundary itself, avoiding float64 (0.15 - 0.10) rounding to 0.049999...
    assert control_gate(0.10 + lib.CONTROL_DELTA_MIN + 1e-9, 0.10, DIR_UP) is True
    assert control_gate(0.10 + lib.CONTROL_DELTA_MIN - 1e-9, 0.10, DIR_UP) is False
    assert control_gate(0.10, 0.20, DIR_DOWN) is True   # sign flips the comparison, diff 0.10
    assert control_gate(None, 0.10, DIR_UP) is None
    p = load_prereg()
    assert p["control_materiality"]["CONTROL_DELTA_MIN"] == 0.05


# ---------------------------------------------------------------------------
# 25. MPIE=0.10 gate exact
# ---------------------------------------------------------------------------
def test_25_mpie_gate_exact_boundary():
    assert mpie_gate(0.20, 0.10, DIR_UP) is True
    assert mpie_gate(0.199, 0.10, DIR_UP) is False
    assert mpie_gate(None, 0.10, DIR_UP) is None
    p = load_prereg()
    assert p["mpie"]["primary_normalized_threshold"] == 0.10


# ---------------------------------------------------------------------------
# 26. ACF L_dep uses LARGEST qualifying lag
# ---------------------------------------------------------------------------
def test_26_l_dep_uses_largest_qualifying_lag(monkeypatch):
    fake_acf = {1: 0.25, 2: 0.10, 4: 0.05, 8: 0.22, 16: 0.01, 32: 0.01, 64: 0.01}
    monkeypatch.setattr(lib, "autocorrelation_at_lag", lambda series, lag: fake_acf[lag])
    out = long_dependence_diagnostic(np.zeros(10))
    assert out["l_dep_days"] == 8


# ---------------------------------------------------------------------------
# 27. non-monotone ACF fixture catches why first-crossing would be wrong
# ---------------------------------------------------------------------------
def test_27_non_monotone_acf_first_crossing_would_be_wrong(monkeypatch):
    # ACF crosses threshold early (lag=1), dips below for several lags, then
    # re-crosses at a much larger lag (lag=32). A first-crossing rule would
    # wrongly report short (1-day) dependence and hide the true long lag.
    fake_acf = {1: 0.21, 2: 0.05, 4: 0.05, 8: 0.05, 16: 0.05, 32: 0.25, 64: 0.05}
    monkeypatch.setattr(lib, "autocorrelation_at_lag", lambda series, lag: fake_acf[lag])
    out = long_dependence_diagnostic(np.zeros(10))
    assert out["l_dep_days"] == 32
    assert out["l_dep_days"] != 1


# ---------------------------------------------------------------------------
# 28. candidate-side symmetry check
# ---------------------------------------------------------------------------
def test_28_symmetric_claim_verdict_branches():
    assert symmetric_claim_verdict(True, True) == {"symmetric_claim": "SUPPORTED", "posthoc_untested": False}
    r = symmetric_claim_verdict(True, False)
    assert r["symmetric_claim"] == "REJECTED_SPECIFIC_CLAIM"
    assert r["posthoc_untested"] is True
    assert r["asymmetric_side"] == "UP"
    r2 = symmetric_claim_verdict(False, True)
    assert r2["asymmetric_side"] == "DOWN"
    r3 = symmetric_claim_verdict(False, False)
    assert r3["symmetric_claim"] == "REJECTED_SPECIFIC_CLAIM"
    assert r3["posthoc_untested"] is False


# ---------------------------------------------------------------------------
# 29. one-side-only synthetic result cannot promote symmetric H03
# ---------------------------------------------------------------------------
def test_29_one_side_only_cannot_promote_symmetric_claim():
    r = symmetric_claim_verdict(up_supports_sign=True, down_supports_sign=False)
    assert r["symmetric_claim"] == "REJECTED_SPECIFIC_CLAIM"
    assert r["posthoc_untested"] is True
    p = load_prereg()
    assert set(p["verdict_labels"]) == {
        "H03_CONTINUATION_CANDIDATE_FOR_FREEZE",
        "H03_EXHAUSTION_CANDIDATE_FOR_FREEZE",
        "H03_INCONCLUSIVE",
        "H03_REJECTED_SPECIFIC_CLAIM",
    }
    assert p["direction_symmetry"]["one_side_only_enters_batch01_validation"] is False


# ---------------------------------------------------------------------------
# 30. continuation synthetic mechanism detected
# ---------------------------------------------------------------------------
def test_30_synthetic_continuation_mechanism_detected(monkeypatch):
    n = 40 * DAY_BARS
    start = int(datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000)
    opn, high, low, close = _tiny_noise_background(n, seed=7)
    for day in range(10, 38):
        i = day * DAY_BARS + 12
        # extreme up impulse (W=15m => 1 bar step) followed by continuation
        # drift over H=60m (4 bars)
        _inject_and_rebase(opn, high, low, close, i, 1.05, 1.01, k_steps=4)
    frame = _frame15(n, start, opn, high, low, close)
    dev_start = start + 4 * DAY_BARS * HTF_MS
    dev_end = start + 40 * DAY_BARS * HTF_MS
    _patch_dev(monkeypatch, start, dev_start, dev_end, ref_steps=3 * DAY_BARS)
    panel = build_panel(frame)
    raw_mask = extreme_candidate_mask(panel["p_w"][15], panel["impulse"][15], 0.90) & panel["in_development"]
    kept = apply_refractory(panel["t_ms"], raw_mask)
    elig = np.isfinite(panel["ret"][60]) & np.isfinite(panel["scale"][60])
    idx = np.flatnonzero(kept & elig)
    assert idx.size >= 10
    b = outcome_bundle(panel, idx, 15, 60)
    assert b["norm"].size >= 10
    # Use robust (median / positive-share) checks rather than the raw mean:
    # by design NORM_CONT_RET_H has no floor, so a single near-zero trailing
    # scale can legitimately dominate the raw mean (the exact risk the
    # preregistration's denominator diagnostics exist to surface) without
    # meaning the underlying continuation mechanism was not detected.
    assert float(np.mean(b["cont_ret"])) > 0
    assert float(np.median(b["norm"])) > 0
    assert float(np.mean(b["cont_ret"] > 0)) > 0.5


# ---------------------------------------------------------------------------
# 31. exhaustion synthetic mechanism detected
# ---------------------------------------------------------------------------
def test_31_synthetic_exhaustion_mechanism_detected(monkeypatch):
    n = 40 * DAY_BARS
    start = int(datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000)
    opn, high, low, close = _tiny_noise_background(n, seed=8)
    for day in range(10, 38):
        i = day * DAY_BARS + 12
        # extreme up impulse followed by reversal over H=60m (4 bars)
        _inject_and_rebase(opn, high, low, close, i, 1.05, 0.99, k_steps=4)
    frame = _frame15(n, start, opn, high, low, close)
    dev_start = start + 4 * DAY_BARS * HTF_MS
    dev_end = start + 40 * DAY_BARS * HTF_MS
    _patch_dev(monkeypatch, start, dev_start, dev_end, ref_steps=3 * DAY_BARS)
    panel = build_panel(frame)
    raw_mask = extreme_candidate_mask(panel["p_w"][15], panel["impulse"][15], 0.90) & panel["in_development"]
    kept = apply_refractory(panel["t_ms"], raw_mask)
    elig = np.isfinite(panel["ret"][60]) & np.isfinite(panel["scale"][60])
    idx = np.flatnonzero(kept & elig)
    assert idx.size >= 10
    b = outcome_bundle(panel, idx, 15, 60)
    assert float(np.mean(b["cont_ret"])) < 0
    assert float(np.median(b["norm"])) < 0
    assert float(np.mean(b["cont_ret"] > 0)) < 0.5


# ---------------------------------------------------------------------------
# 32. null synthetic mechanism does not fabricate a candidate
# ---------------------------------------------------------------------------
def test_32_synthetic_null_mechanism_no_fabricated_candidate(monkeypatch):
    n = 30 * DAY_BARS
    start = int(datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000)
    rng = np.random.default_rng(42)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.0006, size=n)))
    opn = np.r_[close[0], close[:-1]]
    high = np.maximum(opn, close) * (1 + rng.uniform(0.0002, 0.001, size=n))
    low = np.minimum(opn, close) * (1 - rng.uniform(0.0002, 0.001, size=n))
    frame = _frame15(n, start, opn, high, low, close)
    dev_start = start + 4 * DAY_BARS * HTF_MS
    dev_end = start + 30 * DAY_BARS * HTF_MS
    _patch_dev(monkeypatch, start, dev_start, dev_end, ref_steps=3 * DAY_BARS)
    panel = build_panel(frame)
    raw_mask = extreme_candidate_mask(panel["p_w"][15], panel["impulse"][15], 0.90) & panel["in_development"]
    kept = apply_refractory(panel["t_ms"], raw_mask)
    elig = np.isfinite(panel["ret"][60]) & np.isfinite(panel["scale"][60])
    idx = np.flatnonzero(kept & elig)
    if idx.size < 5:
        pytest.skip("not enough random extreme events in this random-walk fixture")
    b = outcome_bundle(panel, idx, 15, 60)
    assert abs(float(np.mean(b["norm"]))) < 0.5


# ---------------------------------------------------------------------------
# 33. moderate momentum without extreme incremental effect fails structural gate
# ---------------------------------------------------------------------------
def test_33_moderate_momentum_without_incremental_effect_fails_structural_gate():
    n = 20
    t = np.arange(n, dtype=np.int64) * HTF_MS
    close = np.full(n, 100.0)
    high = close + 1.0
    low = close - 1.0
    p_w = np.full(n, np.nan)
    impulse = np.full(n, np.nan)
    ret = np.full(n, np.nan)
    scale = np.full(n, 1.0)
    for i in (2, 4, 6):  # extreme-band candidates
        p_w[i] = 0.95
        impulse[i] = 0.03
        ret[i] = 0.02
    for i in (8, 10, 12):  # moderate-band candidates: SAME continuation strength
        p_w[i] = 0.70
        impulse[i] = 0.02
        ret[i] = 0.02
    panel = _manual_panel(t, close, high, low, 15, p_w, impulse, 60, ret, scale)
    extreme_idx = np.flatnonzero(extreme_candidate_mask(p_w, impulse, 0.90))
    moderate_idx = np.flatnonzero(moderate_band_mask(p_w, impulse))
    extreme = outcome_bundle(panel, extreme_idx, 15, 60)
    moderate = outcome_bundle(panel, moderate_idx, 15, 60)
    mean_extreme = float(np.mean(extreme["norm"]))
    mean_moderate = float(np.mean(moderate["norm"]))
    assert mean_extreme == pytest.approx(mean_moderate)
    assert control_gate(mean_extreme, mean_moderate, DIR_UP) is False


# ---------------------------------------------------------------------------
# 34. negative-control timing destroys injected effect
# ---------------------------------------------------------------------------
def test_34_negative_control_destroys_injected_effect(monkeypatch):
    n = 40 * DAY_BARS
    start = int(datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000)
    opn, high, low, close = _tiny_noise_background(n, seed=9)
    for day in range(10, 38):
        i = day * DAY_BARS + 12
        _inject_and_rebase(opn, high, low, close, i, 1.05, 1.01, k_steps=4)
    frame = _frame15(n, start, opn, high, low, close)
    dev_start = start + 4 * DAY_BARS * HTF_MS
    dev_end = start + 40 * DAY_BARS * HTF_MS
    _patch_dev(monkeypatch, start, dev_start, dev_end, ref_steps=3 * DAY_BARS)
    panel = build_panel(frame)
    raw_mask = extreme_candidate_mask(panel["p_w"][15], panel["impulse"][15], 0.90) & panel["in_development"]
    kept = apply_refractory(panel["t_ms"], raw_mask)
    elig = np.isfinite(panel["ret"][60]) & np.isfinite(panel["scale"][60])
    idx = np.flatnonzero(kept & elig)
    assert idx.size >= 10
    cand = outcome_bundle(panel, idx, 15, 60)
    median_cand = float(np.median(cand["norm"]))
    p_pos_cand = float(np.mean(cand["cont_ret"] > 0))
    assert median_cand > 0
    assert p_pos_cand > 0.5
    shifted = negative_control_bundle(panel, cand, raw_mask, 60)
    assert shifted["mean_norm_cont_ret"] is not None
    # the +6h shifted timestamps land on the untouched background (no
    # injected continuation), so the timing-specific effect must be
    # destroyed: its positive-share collapses toward chance, unlike the
    # real candidates' majority-positive share.
    assert shifted["p_cont_ret_pos"] is not None
    assert shifted["p_cont_ret_pos"] < p_pos_cand


# ---------------------------------------------------------------------------
# 35. UTC behavior unchanged under non-UTC process timezone
# ---------------------------------------------------------------------------
def test_35_utc_grid_stable_under_non_utc_process_tz(monkeypatch):
    monkeypatch.setenv("TZ", "America/New_York")
    os.environ["TZ"] = "America/New_York"
    t = int(datetime(2020, 6, 1, 0, 0, tzinfo=UTC).timestamp() * 1000)
    assert is_grid_ms(t)
    assert not is_grid_ms(t + BAR_MS)
    assert is_grid_ms(t + HTF_MS)
    assert development_t_max_ms() % HTF_MS == 0
    assert utc_day_key(t) == "2020-06-01"


# ---------------------------------------------------------------------------
# 36. 2025 and 2026 development reads rejected
# ---------------------------------------------------------------------------
def test_36_2025_and_2026_development_reads_rejected(tmp_path: Path):
    monthly = tmp_path / "canonical" / "1m" / "monthly"
    monthly.mkdir(parents=True)
    (monthly / "2024-12.parquet").write_bytes(b"x")
    (monthly / "2025-01.parquet").write_bytes(b"x")
    (monthly / "2026-01.parquet").write_bytes(b"x")
    paths = lib.list_development_parquet_paths(tmp_path)
    names = [p.name for p in paths]
    assert names == ["2024-12.parquet"]
    with pytest.raises(ValidationWindowForbidden, match="2025"):
        lib._forbid_partition_name("2025-01.parquet")
    with pytest.raises(ValidationWindowForbidden, match="2026"):
        lib._forbid_partition_name("2026-01.parquet")


# ---------------------------------------------------------------------------
# bonus: decile_diagnostic_for_cell must use the cell's actual H, not an
# arbitrary/first key of panel["ret"] -- regression test for a bug caught
# and fixed before this preregistration freeze.
# ---------------------------------------------------------------------------
def test_decile_diagnostic_uses_actual_h_not_first_key():
    n = 20
    t = np.arange(n, dtype=np.int64) * HTF_MS
    close = np.full(n, 100.0)
    high = close + 1
    low = close - 1
    p_w = np.linspace(0.0, 1.0, n)
    impulse = np.full(n, 0.01)
    ret15 = np.full(n, 0.001)
    ret60 = np.full(n, 0.05)
    scale = np.full(n, 1.0)
    panel = {
        "t_ms": t, "close": close, "high": high, "low": low,
        "in_development": np.ones(n, dtype=bool),
        "impulse": {15: impulse}, "p_w": {15: p_w}, "direction": {15: direction_of(impulse)},
        "decile": {15: decile_bin(p_w)},
        "ret": {15: ret15, 60: ret60}, "scale": {15: scale, 60: scale},
    }
    elig_set = np.ones(n, dtype=bool)
    out15 = decile_diagnostic_for_cell(panel, 15, 15, elig_set)
    out60 = decile_diagnostic_for_cell(panel, 15, 60, elig_set)
    means15 = [b["mean_norm_cont_ret"] for b in out15 if b["N"] > 0]
    means60 = [b["mean_norm_cont_ret"] for b in out60 if b["N"] > 0]
    assert means15 and means60
    assert means15[0] == pytest.approx(0.001)
    assert means60[0] == pytest.approx(0.05)
