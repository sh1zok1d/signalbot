"""Network-free tests for H04 trend-pullback continuation.

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

from scripts.research import h04_trend_pullback_continuation_lib as lib
from scripts.research.h04_trend_pullback_continuation_lib import (
    BAR_MS,
    DEPTH_BAND_ORDER,
    DIR_DOWN,
    DIR_UP,
    HORIZONS,
    HTF_MIN,
    HTF_MS,
    MAX_H_MIN,
    P_STEPS,
    ValidationWindowForbidden,
    aggregate_1m_to_15m,
    apply_refractory,
    assert_development_outcome_window,
    build_matched_random_pool,
    build_panel,
    collision_fraction,
    compute_horizon_return,
    compute_pullback_depth,
    compute_raw_pullback_return,
    compute_recent_ratio,
    compute_trend_returns,
    control_gate,
    depth_band_index,
    development_t_max_ms,
    direction_of,
    established_trend_mask,
    has_adjacent_pair_support,
    is_grid_ms,
    load_prereg,
    long_dependence_diagnostic,
    matched_random_bundle,
    mpie_gate,
    negative_control_bundle,
    normalize,
    outcome_bundle,
    parse_px,
    pullback_candidate_mask,
    require_snapshot,
    rolling_midrank_percentile,
    sample_matched_random_once,
    shift_plus_6h_same_utc_day,
    structural_control_bundle,
    structural_control_mask,
    symmetric_claim_verdict,
    total_variation_distance,
    trailing_median_known,
    trend_strength_bin_index,
    utc_day_key,
    utc_dom_key,
    utc_dow_key,
    week_block_bootstrap,
    year_breakdown,
)

UTC = timezone.utc
REPO_ROOT = Path(__file__).resolve().parents[2]
DAY_BARS = 24 * 60 // HTF_MIN  # 96 fifteen-minute bars per UTC day


# ---------------------------------------------------------------------------
# infra / identity sanity
# ---------------------------------------------------------------------------
def test_prereg_frozen_numbers():
    p = load_prereg()
    assert p["trend_lookbacks_minutes"] == [240, 480, 960]
    assert p["horizons_minutes"] == [15, 30, 60, 120, 240]
    assert p["trend_strength"]["established_trend_threshold_q"] == 0.80
    assert p["search_surface"]["primary_threshold_cells"] == 45
    assert p["dataset"]["snapshot_id"] == lib.REQUIRED_SNAPSHOT
    assert p["windows"]["development_end_exclusive"] == "2025-01-01T00:00:00Z"
    assert p["refractory"]["minutes"] == 60
    assert p["matched_random"]["seed"] == 20260902
    assert p["uncertainty"]["seed"] == 20260903
    assert p["mpie"]["primary_normalized_threshold"] == 0.10
    assert p["control_materiality"]["CONTROL_DELTA_MIN"] == 0.05
    assert p["primary_depth_bands"]["bands"]["shallow"] == [0.10, 0.25]
    assert p["primary_depth_bands"]["bands"]["moderate"] == [0.25, 0.40]
    assert p["primary_depth_bands"]["bands"]["deep"] == [0.40, 1.00]
    assert p["structural_control"]["control_rule"] == "TREND_PCTL_L(T) >= 0.80 AND abs(RECENT_RATIO(T)) < 0.10"
    assert set(p["verdict_labels"]) == {
        "H04_CONTINUATION_CANDIDATE_FOR_FREEZE", "H04_INCONCLUSIVE", "H04_REJECTED_SPECIFIC_CLAIM",
    }
    assert p["no_exhaustion_candidate"] is True


def test_require_snapshot_matches_repo_manifest():
    assert require_snapshot() == lib.REQUIRED_SNAPSHOT


def test_require_snapshot_fails_on_mismatch(tmp_path: Path):
    man = yaml.safe_load((REPO_ROOT / "docs/manifests/CORE_BTC_BINANCE_V0.yaml").read_text())
    man["snapshot_id"] = "deadbeef"
    p = tmp_path / "m.yaml"
    p.write_text(yaml.safe_dump(man), encoding="utf-8")
    with pytest.raises(lib.H04Error, match="snapshot mismatch"):
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


def _apply_episode_and_rebase(opn, high, low, close, start_idx, multipliers, pad=0.01):
    """Apply per-step multiplicative moves sequentially at
    start_idx+1..start_idx+len(multipliers), then rebase the remainder of
    the arrays so the untouched background continues smoothly from the new
    level instead of artificially snapping back to the pre-episode
    trajectory (see H03 test lessons)."""
    last_idx = start_idx + len(multipliers)
    orig_last = close[last_idx]
    j = start_idx
    for m in multipliers:
        j += 1
        close[j] = close[j - 1] * m
        opn[j] = close[j - 1]
        high[j] = max(close[j], opn[j]) + pad
        low[j] = min(close[j], opn[j]) - pad
    ratio = close[last_idx] / orig_last
    close[last_idx + 1:] *= ratio
    opn[last_idx + 1:] *= ratio
    high[last_idx + 1:] *= ratio
    low[last_idx + 1:] *= ratio


def _inject_trend_pullback_resume(opn, high, low, close, t_idx, l_steps,
                                   trend_mult, pullback_mult, resume_mult, resume_steps=4):
    """Build one T-anchored episode: established trend leg over
    [t_idx-P_STEPS-l_steps, t_idx-P_STEPS), pullback leg over
    [t_idx-P_STEPS, t_idx), then `resume_steps` of post-T drift at
    resume_mult (continuation/reversal/flat depending on sign)."""
    start_idx = t_idx - P_STEPS - l_steps
    multipliers = [trend_mult] * l_steps + [pullback_mult] * P_STEPS + [resume_mult] * resume_steps
    _apply_episode_and_rebase(opn, high, low, close, start_idx, multipliers)


def _manual_panel(t_ms, close, high, low, l_minutes, trend_pctl, trend_ret, signed_pb_ret, depth, recent_ratio,
                   h_minutes, ret, scale, in_dev=None):
    n = len(t_ms)
    if in_dev is None:
        in_dev = np.ones(n, dtype=bool)
    direction = direction_of(trend_ret)
    return {
        "t_ms": t_ms, "close": close, "high": high, "low": low,
        "in_development": in_dev,
        "trend_ret": {l_minutes: trend_ret}, "trend_pctl": {l_minutes: trend_pctl},
        "direction": {l_minutes: direction}, "signed_pb_ret": {l_minutes: signed_pb_ret},
        "depth": {l_minutes: depth}, "recent_ratio": {l_minutes: recent_ratio},
        "band_idx": {l_minutes: depth_band_index(depth)},
        "strength_bin": {l_minutes: trend_strength_bin_index(trend_pctl)},
        "ret": {h_minutes: ret}, "scale": {h_minutes: scale},
        "month_key": np.array([lib.utc_month_key(int(x)) for x in t_ms]),
        "week_key": np.array([lib.utc_week_key(int(x)) for x in t_ms]),
        "year": np.array([lib.utc_year(int(x)) for x in t_ms], dtype=np.int16),
        "dow_key": np.array([lib.utc_dow_key(int(x)) for x in t_ms]),
        "dom_key": np.array([lib.utc_dom_key(int(x)) for x in t_ms]),
    }


def _patch_dev(monkeypatch, start_ms, dev_start_ms, dev_end_ms, ref_steps, l_windows=(240,), horizons=(60,)):
    monkeypatch.setattr(lib, "WARMUP_START_MS", start_ms)
    monkeypatch.setattr(lib, "DEV_START_MS", dev_start_ms)
    monkeypatch.setattr(lib, "DEV_END_MS", dev_end_ms)
    monkeypatch.setattr(lib, "REF_STEPS", ref_steps)
    monkeypatch.setattr(lib, "L_WINDOWS", l_windows)
    monkeypatch.setattr(lib, "HORIZONS", horizons)


# ---------------------------------------------------------------------------
# 1. T == bar_end_exclusive
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
# 2. trend interval exactly [T-P-L, T-P)
# ---------------------------------------------------------------------------
def test_02_trend_interval_exact():
    close = np.array([100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0])
    # l_minutes=30 -> l_step=2; P_STEPS=4; lag_near=4, lag_far=6
    tr = compute_trend_returns(close, 30)
    assert np.isnan(tr[5])  # i=5 < lag_far(6)
    # i=6: close(T-P)=close[6-4]=close[2]=102, close(T-P-L)=close[6-6]=close[0]=100
    assert tr[6] == pytest.approx(np.log(close[2] / close[0]))
    # i=7: close(T-P)=close[3]=103, close(T-P-L)=close[1]=101
    assert tr[7] == pytest.approx(np.log(close[3] / close[1]))


# ---------------------------------------------------------------------------
# 3. pullback interval exactly [T-P, T)
# ---------------------------------------------------------------------------
def test_03_pullback_interval_exact():
    close = np.array([100.0, 101.0, 102.0, 103.0, 104.0, 105.0])
    raw = compute_raw_pullback_return(close)
    assert np.isnan(raw[3])  # i=3 < P_STEPS(4)
    # i=4: close(T)=close[4], close(T-P)=close[0]
    assert raw[4] == pytest.approx(np.log(close[4] / close[0]))
    assert raw[5] == pytest.approx(np.log(close[5] / close[1]))


# ---------------------------------------------------------------------------
# 4. shared pivot close(T-P) exact
# ---------------------------------------------------------------------------
def test_04_shared_pivot_close_exact():
    close = np.array([100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0])
    tr = compute_trend_returns(close, 30)  # uses close(T-P) as its near endpoint
    raw = compute_raw_pullback_return(close)  # uses close(T-P) as its starting point
    # at i=6: trend leg's near endpoint is close[2]; pullback leg's start is close[2] too
    i = 6
    pivot_from_trend = close[i - P_STEPS]
    pivot_from_pullback = close[i - P_STEPS]
    assert pivot_from_trend == pivot_from_pullback == close[2]
    assert tr[i] == pytest.approx(np.log(close[i - P_STEPS] / close[i - P_STEPS - 2]))
    assert raw[i] == pytest.approx(np.log(close[i] / close[i - P_STEPS]))


# ---------------------------------------------------------------------------
# 5. no pullback-window contamination of trend leg
# ---------------------------------------------------------------------------
def test_05_pullback_window_does_not_contaminate_trend_leg():
    close = np.array([100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0])
    tr_a = compute_trend_returns(close, 30)
    close2 = close.copy()
    close2[6:] = 999.0  # perturb only inside/after the pullback window [T-P, T) at i=6
    tr_b = compute_trend_returns(close2, 30)
    assert tr_a[6] == pytest.approx(tr_b[6])  # trend leg (ends at close[2]) is unaffected


# ---------------------------------------------------------------------------
# 6 & 7. trend percentile uses only prior timestamps; midrank ties exact
# ---------------------------------------------------------------------------
def test_06_07_percentile_prior_only_and_midrank_ties_exact():
    values = np.array([1.0, 2.0, 2.0, 2.0, 3.0, 2.0])
    p = rolling_midrank_percentile(values, window=5)
    # ref = values[0:5] = [1,2,2,2,3], x = values[5] = 2
    assert p[5] == pytest.approx((1 + 0.5 * 3) / 5)
    values2 = values.copy()
    values2[6:] = 500.0 if len(values2) > 6 else values2[6:]
    p2 = rolling_midrank_percentile(np.r_[values, 500.0], window=5)
    assert p2[5] == pytest.approx(p[5])  # future values cannot change it


# ---------------------------------------------------------------------------
# 8. q=0.80 boundary exact
# ---------------------------------------------------------------------------
def test_08_established_trend_threshold_boundary_exact():
    trend_pctl = np.array([0.79, 0.80, 0.81, np.nan])
    trend_ret = np.array([0.01, 0.01, -0.01, 0.01])
    mask = established_trend_mask(trend_pctl, trend_ret, q=0.80)
    assert list(mask) == [False, True, True, False]


# ---------------------------------------------------------------------------
# 9. trend direction exact
# ---------------------------------------------------------------------------
def test_09_trend_direction_exact():
    trend_ret = np.array([0.01, -0.01, 0.0, np.nan])
    d = direction_of(trend_ret)
    assert list(d) == [DIR_UP, DIR_DOWN, 0, 0]


# ---------------------------------------------------------------------------
# 10. pullback sign exact
# ---------------------------------------------------------------------------
def test_10_pullback_sign_exact():
    close = np.array([100.0, 99.0, 98.0, 97.0, 96.0])  # raw pullback ret negative (price falling)
    raw = compute_raw_pullback_return(close)
    direction = DIR_UP  # uptrend
    signed = direction * raw
    assert signed[4] < 0  # counter-trend (price fell while trend is UP)
    direction2 = DIR_DOWN  # downtrend, same raw price fall is now "same-direction extension"
    signed2 = direction2 * raw
    assert signed2[4] > 0


# ---------------------------------------------------------------------------
# 11. depth formula exact
# ---------------------------------------------------------------------------
def test_11_depth_formula_exact():
    signed_pb_ret = np.array([-0.02, 0.02, -0.02])
    trend_ret = np.array([0.10, 0.10, -0.10])
    depth = compute_pullback_depth(signed_pb_ret, trend_ret)
    assert depth[0] == pytest.approx(0.02 / 0.10)
    assert np.isnan(depth[1])  # not counter-trend (signed_pb_ret > 0)
    assert depth[2] == pytest.approx(0.02 / 0.10)  # abs(trend_ret) used in denominator


# ---------------------------------------------------------------------------
# 12 & 13. depth<1 boundary exact / depth=1 excluded
# ---------------------------------------------------------------------------
def test_12_13_depth_one_boundary_excluded():
    band = depth_band_index(np.array([0.9999, 1.0, 1.0001]))
    assert band[0] == 2  # deep band, still < 1.0
    assert band[1] == -1  # depth == 1.0 excluded
    assert band[2] == -1  # depth > 1.0 excluded


# ---------------------------------------------------------------------------
# 14. depth<0.10 excluded from primary
# ---------------------------------------------------------------------------
def test_14_depth_below_point_10_excluded():
    band = depth_band_index(np.array([0.0, 0.05, 0.0999, 0.10]))
    assert list(band) == [-1, -1, -1, 0]


# ---------------------------------------------------------------------------
# 15/16/17. shallow/moderate/deep band boundaries exact
# ---------------------------------------------------------------------------
def test_15_16_17_band_boundaries_exact():
    depths = np.array([0.10, 0.2499, 0.25, 0.3999, 0.40, 0.9999])
    band = depth_band_index(depths)
    assert list(band) == [0, 0, 1, 1, 2, 2]
    assert DEPTH_BAND_ORDER[0] == "shallow"
    assert DEPTH_BAND_ORDER[1] == "moderate"
    assert DEPTH_BAND_ORDER[2] == "deep"


# ---------------------------------------------------------------------------
# 18. one event cannot belong to multiple primary bands
# ---------------------------------------------------------------------------
def test_18_depth_bands_mutually_exclusive():
    depths = np.linspace(0.0, 1.2, 500)
    band = depth_band_index(depths)
    # every non -1 value is exactly one of {0,1,2}; scalar assignment
    # guarantees exclusivity by construction, but assert no depth maps to
    # more than one band definition by checking the band edges partition.
    for b, (lo, hi) in zip((0, 1, 2), ((0.10, 0.25), (0.25, 0.40), (0.40, 1.00))):
        sel = band == b
        assert np.all(depths[sel] >= lo) and np.all(depths[sel] < hi)


# ---------------------------------------------------------------------------
# 19 & 20. refractory keeps earliest, suppresses both trend directions
# ---------------------------------------------------------------------------
def test_19_20_refractory_keeps_earliest_suppresses_both_directions():
    n = 10
    t = np.arange(n, dtype=np.int64) * HTF_MS
    mask = np.zeros(n, dtype=bool)
    mask[[1, 2, 3, 7]] = True
    kept = apply_refractory(t, mask, refractory_ms=lib.REFRACTORY_MS)
    assert list(np.flatnonzero(kept)) == [1, 7]
    assert not kept[2] and not kept[3]


# ---------------------------------------------------------------------------
# 21. H outcome boundary rejects 2025
# ---------------------------------------------------------------------------
def test_21_boundary_embargo_rejects_crossing_2025():
    t_ok = development_t_max_ms()
    assert_development_outcome_window(t_ok, MAX_H_MIN)
    t_bad = t_ok + HTF_MS
    with pytest.raises(ValidationWindowForbidden):
        assert_development_outcome_window(t_bad, MAX_H_MIN)


# ---------------------------------------------------------------------------
# 22. no horizon truncation
# ---------------------------------------------------------------------------
def test_22_horizon_return_no_truncation_at_boundary():
    n = 20
    close = 100.0 + np.arange(n, dtype=np.float64)
    t_ms = np.arange(n, dtype=np.int64) * HTF_MS
    dev_end = t_ms[10] + 60 * BAR_MS
    r = compute_horizon_return(close, t_ms, 60, dev_end_ms=dev_end)
    for i in range(10):
        assert np.isfinite(r[i])
    for i in range(10, 16):
        assert np.isnan(r[i])


# ---------------------------------------------------------------------------
# 23. normalization only uses fully resolved pre-T outcomes
# ---------------------------------------------------------------------------
def test_23_trailing_scale_uses_only_resolved_pre_t():
    values = np.array([1.0, 2.0, 3.0, 4.0, 100.0, 5.0], dtype=np.float64)
    med = trailing_median_known(values, window=4, known_lag_steps=1)
    assert med[5] == pytest.approx(3.5)


# ---------------------------------------------------------------------------
# 24. zero/nonfinite normalization denominator ineligible
# ---------------------------------------------------------------------------
def test_24_normalize_zero_or_nonfinite_denominator_is_ineligible():
    cont_ret = np.array([0.01, 0.02, 0.03, 0.04])
    scale = np.array([0.0, np.nan, -1.0, 0.5])
    norm, elig = normalize(cont_ret, scale)
    assert list(elig) == [False, False, False, True]
    assert norm[3] == pytest.approx(0.08)


# ---------------------------------------------------------------------------
# 25. no full-development floor
# ---------------------------------------------------------------------------
def test_25_no_full_development_floor():
    cont_ret = np.array([0.01])
    scale = np.array([1e-9])
    norm, elig = normalize(cont_ret, scale)
    assert elig[0]
    assert norm[0] == pytest.approx(0.01 / 1e-9)
    p = load_prereg()
    assert p["normalization"]["full_development_floor_used"] is False


# ---------------------------------------------------------------------------
# 26. RECENT_RATIO exact
# ---------------------------------------------------------------------------
def test_26_recent_ratio_exact():
    signed_pb_ret = np.array([-0.02, 0.02, -0.02, np.nan])
    trend_ret = np.array([0.10, 0.10, -0.10, 0.10])
    ratio = compute_recent_ratio(signed_pb_ret, trend_ret)
    assert ratio[0] == pytest.approx(-0.2)
    assert ratio[1] == pytest.approx(0.2)
    assert ratio[2] == pytest.approx(-0.2)  # abs(trend_ret) in denominator
    assert np.isnan(ratio[3])


# ---------------------------------------------------------------------------
# 27/28/29. structural control accepts near-neutral, rejects pullback>=0.10
# and extension ratio>=0.10
# ---------------------------------------------------------------------------
def test_27_28_29_structural_control_mask_exact():
    trend_pctl = np.array([0.85, 0.85, 0.85, 0.85, 0.70])
    trend_ret = np.array([0.10, 0.10, 0.10, 0.10, 0.10])
    recent_ratio = np.array([0.05, -0.05, -0.10, 0.10, 0.05])
    mask = structural_control_mask(trend_pctl, trend_ret, recent_ratio)
    assert mask[0]  # near-neutral positive ratio: accepted
    assert mask[1]  # near-neutral negative ratio: accepted
    assert not mask[2]  # ratio == -0.10 -> abs==0.10, rejected (pullback-scale move)
    assert not mask[3]  # ratio == 0.10 -> rejected (extension-scale move)
    assert not mask[4]  # trend not established (q<0.80)


# ---------------------------------------------------------------------------
# 30/31. structural matching month/direction/trend-bin exact; unmatched counted
# ---------------------------------------------------------------------------
def test_30_31_structural_matching_and_unmatched_counted():
    n = 20
    start = int(datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000)
    t = start + np.arange(n, dtype=np.int64) * HTF_MS
    close = np.full(n, 100.0)
    high = close + 1
    low = close - 1
    trend_pctl = np.full(n, np.nan)
    trend_ret = np.full(n, np.nan)
    signed_pb_ret = np.full(n, np.nan)
    ret60 = np.full(n, 0.01)
    scale = np.full(n, 1.0)
    # two candidates (pullback) in month/direction/bin (2020-01, UP, [0.80,0.90))
    for i in (2, 4):
        trend_pctl[i] = 0.85
        trend_ret[i] = 0.10
        signed_pb_ret[i] = -0.02  # depth = 0.2 (shallow)
    depth = compute_pullback_depth(signed_pb_ret, trend_ret)
    recent_ratio = compute_recent_ratio(signed_pb_ret, trend_ret)
    # structural (near-neutral) observations: one matches candidate key,
    # one has a different trend-strength bin (unmatched)
    for i in (6, 8):
        trend_pctl[i] = 0.85  # same bin as candidates -> matched
        trend_ret[i] = 0.10
        signed_pb_ret[i] = 0.0  # placeholder; ratio computed directly below
    trend_pctl[10] = 0.95  # different trend-strength bin -> unmatched
    trend_ret[10] = 0.10
    recent_ratio[6] = 0.02
    recent_ratio[8] = -0.02
    recent_ratio[10] = 0.02
    panel = _manual_panel(t, close, high, low, 240, trend_pctl, trend_ret, signed_pb_ret, depth, recent_ratio,
                           60, ret60, scale)
    elig_set = np.ones(n, dtype=bool)
    cand_idx = np.flatnonzero(pullback_candidate_mask(trend_pctl, trend_ret, signed_pb_ret, depth_band_index(depth), 0))
    cand = outcome_bundle(panel, cand_idx, 240, 60)
    out = structural_control_bundle(panel, cand, 240, 60, elig_set)
    # index 8 is suppressed by the control's OWN independent 60m refractory
    # (it is within 60m of kept index 6); post-refractory eligible = {6, 10}.
    assert out["structural_eligible_N"] == 2
    assert out["matched_N"] == 1  # index 6 shares (month, direction, bin) with candidates
    assert out["unmatched_N"] == 1  # index 10 (different trend-strength bin)
    assert out["unmatched_share"] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# 32/33. matched-random exclusion uses membership not position; non-contiguous regression
# ---------------------------------------------------------------------------
def test_32_33_matched_random_pool_membership_not_position():
    elig = np.array([2976, 2977, 10000, 172400, 172517], dtype=np.int64)
    raw = np.array([172517, 2976], dtype=np.int64)
    pool = build_matched_random_pool(elig, raw)
    assert 172517 not in pool.tolist() and 2976 not in pool.tolist()
    assert sorted(pool.tolist()) == [2977, 10000, 172400]

    def _pre_fix_fancy_index(all_grid_idx, raw_extreme_idx):
        excluded = np.zeros(len(all_grid_idx), dtype=bool)
        excluded[raw_extreme_idx] = True
        return all_grid_idx[~excluded]

    with pytest.raises(IndexError):
        _pre_fix_fancy_index(elig, raw)  # the exact H03 bug class

    grid = np.arange(20, dtype=np.int64)
    raw_small = np.array([3, 7, 12], dtype=np.int64)
    np.testing.assert_array_equal(
        _pre_fix_fancy_index(grid, raw_small), build_matched_random_pool(grid, raw_small),
    )


# ---------------------------------------------------------------------------
# 34/35/36. matched random without replacement; month/direction composition preserved
# ---------------------------------------------------------------------------
def test_34_35_36_matched_random_sampling_and_composition():
    rng = np.random.default_rng(1)
    pool_by_month = {"2020-01": np.arange(10), "2020-02": np.arange(10, 20)}
    need_up = {"2020-01": 2, "2020-02": 1}
    need_down = {"2020-01": 1, "2020-02": 2}
    picked, labels = sample_matched_random_once(rng, pool_by_month, need_up, need_down)
    assert picked.size == 6
    assert len(set(picked.tolist())) == 6  # without replacement
    assert int(np.sum(labels == DIR_UP)) == 3
    assert int(np.sum(labels == DIR_DOWN)) == 3
    jan_picked = picked[np.isin(picked, pool_by_month["2020-01"])]
    assert jan_picked.size == 3


# ---------------------------------------------------------------------------
# 37/38. DOW / DOM TVD exact
# ---------------------------------------------------------------------------
def test_37_38_dow_dom_tvd_exact():
    a = {"0": 3, "1": 1}
    b = {"0": 2, "1": 2}
    assert total_variation_distance(a, b) == pytest.approx(0.25)
    a2 = {"01": 100}
    b2 = {"01": 50, "02": 50}
    assert total_variation_distance(a2, b2) == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# 39. timestamp-vs-panel-id H03 regression
# ---------------------------------------------------------------------------
def test_39_matched_random_uses_real_timestamps_not_panel_ids():
    # panel ids like 172517 interpreted as epoch ms would collapse to
    # 1970-01-01 (Thursday='3', DOM='01') -- the exact H03 TVD erratum.
    for idx in (100, 172400, 172517, 200000):
        assert utc_dow_key(int(idx)) == "3"
        assert utc_dom_key(int(idx)) == "01"

    n = 40
    start = int(datetime(2020, 6, 1, tzinfo=UTC).timestamp() * 1000)
    t = start + np.arange(n, dtype=np.int64) * HTF_MS
    close = np.full(n, 100.0)
    high = close + 1
    low = close - 1
    trend_pctl = np.full(n, np.nan)
    trend_ret = np.full(n, np.nan)
    signed_pb_ret = np.full(n, np.nan)
    for i in (5, 15, 25):
        trend_pctl[i] = 0.90
        trend_ret[i] = 0.10
        signed_pb_ret[i] = -0.02
    depth = compute_pullback_depth(signed_pb_ret, trend_ret)
    recent_ratio = compute_recent_ratio(signed_pb_ret, trend_ret)
    ret60 = np.full(n, 0.01)
    scale = np.full(n, 1.0)
    panel = _manual_panel(t, close, high, low, 240, trend_pctl, trend_ret, signed_pb_ret, depth, recent_ratio,
                           60, ret60, scale)
    cand_idx = np.array([5, 15, 25])
    cand = outcome_bundle(panel, cand_idx, 240, 60)
    pool = np.setdiff1d(np.arange(n), cand_idx)
    out = matched_random_bundle(panel, cand, pool, 60, seed=1, replicates=5)
    # if panel ids leaked as ms, dow/dom TVD would sit near the ~0.857/~0.967
    # pathological values found in H03; real timestamps should not.
    assert out["residual_diagnostic"]["dow_tvd"] < 0.8
    assert out["residual_diagnostic"]["dom_tvd"] < 0.9


# ---------------------------------------------------------------------------
# 40/41. +6h wrap exact; collision reporting exact
# ---------------------------------------------------------------------------
def test_40_41_plus_6h_wrap_and_collision_exact():
    t = int(datetime(2020, 6, 1, 22, 0, tzinfo=UTC).timestamp() * 1000)
    s = shift_plus_6h_same_utc_day(t)
    assert s == int(datetime(2020, 6, 1, 4, 0, tzinfo=UTC).timestamp() * 1000)
    shifted = np.array([100, 200, 300, 400])
    raw = np.array([200, 400, 999])
    assert collision_fraction(shifted, raw) == pytest.approx(0.5)
    assert collision_fraction(np.array([]), raw) == 0.0


# ---------------------------------------------------------------------------
# 42. MPIE=0.10 exact boundary
# ---------------------------------------------------------------------------
def test_42_mpie_gate_exact_boundary():
    assert mpie_gate(0.20, 0.10, DIR_UP) is True
    assert mpie_gate(0.199, 0.10, DIR_UP) is False
    assert mpie_gate(None, 0.10, DIR_UP) is None


# ---------------------------------------------------------------------------
# 43/44. CONTROL_DELTA_MIN=0.05 structural and negative-control exact
# ---------------------------------------------------------------------------
def test_43_44_control_delta_min_gate_exact():
    assert control_gate(0.20, 0.10, DIR_UP) is True
    assert control_gate(0.14, 0.10, DIR_UP) is False
    assert control_gate(0.10 + lib.CONTROL_DELTA_MIN + 1e-9, 0.10, DIR_UP) is True
    assert control_gate(0.10 + lib.CONTROL_DELTA_MIN - 1e-9, 0.10, DIR_UP) is False


# ---------------------------------------------------------------------------
# 45/46. two-adjacent-depth-band promotion logic; one-band-only cannot promote
# ---------------------------------------------------------------------------
def test_45_46_adjacent_depth_band_promotion_logic():
    assert has_adjacent_pair_support(DEPTH_BAND_ORDER, {"shallow": True, "moderate": True, "deep": False}) is True
    assert has_adjacent_pair_support(DEPTH_BAND_ORDER, {"shallow": True, "moderate": False, "deep": True}) is False
    assert has_adjacent_pair_support(DEPTH_BAND_ORDER, {"shallow": True, "moderate": False, "deep": False}) is False


# ---------------------------------------------------------------------------
# 47/48. two adjacent H logic; one-H-only cannot promote
# ---------------------------------------------------------------------------
def test_47_48_adjacent_horizon_promotion_logic():
    support = {15: True, 30: True, 60: False, 120: False, 240: False}
    assert has_adjacent_pair_support(HORIZONS, support) is True
    support2 = {15: True, 30: False, 60: False, 120: False, 240: True}
    assert has_adjacent_pair_support(HORIZONS, support2) is False


# ---------------------------------------------------------------------------
# 49/50. UPTREND/DOWNTREND symmetry; one-sided cannot promote
# ---------------------------------------------------------------------------
def test_49_50_symmetric_claim_verdict():
    assert symmetric_claim_verdict(True, True) == {"symmetric_claim": "SUPPORTED", "posthoc_untested": False}
    r = symmetric_claim_verdict(True, False)
    assert r["symmetric_claim"] == "REJECTED_SPECIFIC_CLAIM"
    assert r["posthoc_untested"] is True
    assert r["asymmetric_side"] == "UPTREND"


# ---------------------------------------------------------------------------
# 51. 4/5-year gate
# ---------------------------------------------------------------------------
def test_51_year_breakdown_four_of_five_gate():
    n = 5
    years = np.array([2020, 2021, 2022, 2023, 2024], dtype=np.int16)
    cand = {
        "year": years,
        "norm": np.array([0.2, 0.2, 0.2, 0.2, -0.2]),
        "cont_ret": np.array([0.01, 0.01, 0.01, 0.01, -0.01]),
    }
    out = year_breakdown(cand)
    positive_years = sum(1 for y in (2020, 2021, 2022, 2023, 2024)
                         if out[str(y)]["mean_norm_trend_cont_ret"] is not None and out[str(y)]["mean_norm_trend_cont_ret"] > 0)
    assert positive_years == 4  # meets the >=4/5 requirement


# ---------------------------------------------------------------------------
# 52/53/54/55. synthetic mechanism detection
# ---------------------------------------------------------------------------
def test_52_synthetic_continuation_mechanism_detected(monkeypatch):
    n = 40 * DAY_BARS
    start = int(datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000)
    opn, high, low, close = _tiny_noise_background(n, seed=11)
    l_steps = 16  # L=240m
    for day in range(10, 38):
        t_idx = day * DAY_BARS + 40
        _inject_trend_pullback_resume(opn, high, low, close, t_idx, l_steps,
                                       trend_mult=1.006, pullback_mult=0.997, resume_mult=1.006, resume_steps=4)
    frame = _frame15(n, start, opn, high, low, close)
    dev_start = start + 4 * DAY_BARS * HTF_MS
    dev_end = start + 40 * DAY_BARS * HTF_MS
    _patch_dev(monkeypatch, start, dev_start, dev_end, ref_steps=3 * DAY_BARS, l_windows=(240,), horizons=(60,))
    panel = build_panel(frame)
    band_idx = panel["band_idx"][240]
    # use whichever band the constructed pullback actually landed in
    bands_present = sorted(set(int(b) for b in band_idx[band_idx >= 0]))
    assert bands_present, "fixture produced no eligible pullback band"
    band = bands_present[0]
    raw_mask = pullback_candidate_mask(
        panel["trend_pctl"][240], panel["trend_ret"][240], panel["signed_pb_ret"][240], band_idx, band,
    ) & panel["in_development"]
    kept = apply_refractory(panel["t_ms"], raw_mask)
    elig = np.isfinite(panel["ret"][60]) & np.isfinite(panel["scale"][60])
    idx = np.flatnonzero(kept & elig)
    assert idx.size >= 8
    b = outcome_bundle(panel, idx, 240, 60)
    assert float(np.mean(b["cont_ret"])) > 0
    assert float(np.median(b["norm"])) > 0
    assert float(np.mean(b["cont_ret"] > 0)) > 0.5


def test_53_generic_trend_without_pullback_specific_value_fails_structural_gate():
    n = 20
    t = np.arange(n, dtype=np.int64) * HTF_MS
    close = np.full(n, 100.0)
    high = close + 1
    low = close - 1
    trend_pctl = np.full(n, np.nan)
    trend_ret = np.full(n, np.nan)
    signed_pb_ret = np.full(n, np.nan)
    ret60 = np.full(n, np.nan)
    scale = np.full(n, 1.0)
    # pullback candidates: same continuation strength as the "structural"
    # near-neutral population -- no incremental value from the pullback itself.
    for i in (2, 4, 6):
        trend_pctl[i] = 0.90
        trend_ret[i] = 0.10
        signed_pb_ret[i] = -0.02  # depth=0.2 (shallow)
        ret60[i] = 0.02
    for i in (8, 10, 12):
        trend_pctl[i] = 0.90
        trend_ret[i] = 0.10
        signed_pb_ret[i] = 0.005  # near-neutral recent move -> structural control
        ret60[i] = 0.02  # SAME continuation strength
    depth = compute_pullback_depth(signed_pb_ret, trend_ret)
    recent_ratio = compute_recent_ratio(signed_pb_ret, trend_ret)
    panel = _manual_panel(t, close, high, low, 240, trend_pctl, trend_ret, signed_pb_ret, depth, recent_ratio,
                           60, ret60, scale)
    elig_set = np.isfinite(ret60)
    cand_idx = np.flatnonzero(pullback_candidate_mask(trend_pctl, trend_ret, signed_pb_ret, depth_band_index(depth), 0) & elig_set)
    cand = outcome_bundle(panel, cand_idx, 240, 60)
    ctrl = structural_control_bundle(panel, cand, 240, 60, elig_set)
    mean_cand = cand_mean = float(np.mean(cand["norm"]))
    mean_ctrl = ctrl["mean_norm_trend_cont_ret"]
    assert mean_cand == pytest.approx(mean_ctrl)
    assert control_gate(mean_cand, mean_ctrl, DIR_UP) is False


def test_54_synthetic_null_mechanism_no_fabricated_candidate(monkeypatch):
    n = 30 * DAY_BARS
    start = int(datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000)
    rng = np.random.default_rng(43)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.0006, size=n)))
    opn = np.r_[close[0], close[:-1]]
    high = np.maximum(opn, close) * (1 + rng.uniform(0.0002, 0.001, size=n))
    low = np.minimum(opn, close) * (1 - rng.uniform(0.0002, 0.001, size=n))
    frame = _frame15(n, start, opn, high, low, close)
    dev_start = start + 4 * DAY_BARS * HTF_MS
    dev_end = start + 30 * DAY_BARS * HTF_MS
    _patch_dev(monkeypatch, start, dev_start, dev_end, ref_steps=3 * DAY_BARS, l_windows=(240,), horizons=(60,))
    panel = build_panel(frame)
    band_idx = panel["band_idx"][240]
    raw_mask = np.zeros(n, dtype=bool)
    for band in range(3):
        raw_mask |= pullback_candidate_mask(
            panel["trend_pctl"][240], panel["trend_ret"][240], panel["signed_pb_ret"][240], band_idx, band,
        )
    raw_mask &= panel["in_development"]
    kept = apply_refractory(panel["t_ms"], raw_mask)
    elig = np.isfinite(panel["ret"][60]) & np.isfinite(panel["scale"][60])
    idx = np.flatnonzero(kept & elig)
    if idx.size < 5:
        pytest.skip("not enough random pullback events in this random-walk fixture")
    b = outcome_bundle(panel, idx, 240, 60)
    assert abs(float(np.mean(b["norm"]))) < 0.5


def test_55_reversal_mechanism_cannot_become_h04_candidate(monkeypatch):
    n = 40 * DAY_BARS
    start = int(datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000)
    opn, high, low, close = _tiny_noise_background(n, seed=12)
    l_steps = 16
    for day in range(10, 38):
        t_idx = day * DAY_BARS + 40
        # established trend, shallow pullback, then REVERSAL (not resumption)
        _inject_trend_pullback_resume(opn, high, low, close, t_idx, l_steps,
                                       trend_mult=1.006, pullback_mult=0.997, resume_mult=0.994, resume_steps=4)
    frame = _frame15(n, start, opn, high, low, close)
    dev_start = start + 4 * DAY_BARS * HTF_MS
    dev_end = start + 40 * DAY_BARS * HTF_MS
    _patch_dev(monkeypatch, start, dev_start, dev_end, ref_steps=3 * DAY_BARS, l_windows=(240,), horizons=(60,))
    panel = build_panel(frame)
    band_idx = panel["band_idx"][240]
    bands_present = sorted(set(int(b) for b in band_idx[band_idx >= 0]))
    assert bands_present
    band = bands_present[0]
    raw_mask = pullback_candidate_mask(
        panel["trend_pctl"][240], panel["trend_ret"][240], panel["signed_pb_ret"][240], band_idx, band,
    ) & panel["in_development"]
    kept = apply_refractory(panel["t_ms"], raw_mask)
    elig = np.isfinite(panel["ret"][60]) & np.isfinite(panel["scale"][60])
    idx = np.flatnonzero(kept & elig)
    assert idx.size >= 8
    b = outcome_bundle(panel, idx, 240, 60)
    # H04 only has a continuation candidate sign; a reversal mechanism must
    # show negative continuation and therefore cannot satisfy the MPIE gate.
    assert float(np.mean(b["cont_ret"])) < 0
    assert mpie_gate(float(np.mean(b["norm"])), 0.0, DIR_UP) is False


# ---------------------------------------------------------------------------
# 56/57. week-block bootstrap present in per-cell output; deterministic seed
# ---------------------------------------------------------------------------
def test_56_57_week_block_bootstrap_wired_and_deterministic():
    n = 40
    start = int(datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000)
    week = np.array([lib.utc_week_key(int(start + i * HTF_MS)) for i in range(n)])
    norm = np.linspace(0.5, 1.5, n)  # solidly positive, avoids near-zero float-ordering noise
    cont_ret = np.linspace(0.01, 0.02, n)
    out1 = week_block_bootstrap(week, norm, cont_ret, seed=123, replicates=50)
    out2 = week_block_bootstrap(week, norm, cont_ret, seed=123, replicates=50)
    assert out1 == out2  # deterministic given the same seed
    assert out1["norm_mean"] is not None
    assert out1["norm_p025"] <= out1["norm_mean"] <= out1["norm_p975"]

    # present in the actual evaluate_cell output schema
    close = np.full(n, 100.0)
    high = close + 1
    low = close - 1
    trend_pctl = np.full(n, np.nan)
    trend_ret = np.full(n, np.nan)
    signed_pb_ret = np.full(n, np.nan)
    for i in (5, 15, 25, 35):
        trend_pctl[i] = 0.90
        trend_ret[i] = 0.10
        signed_pb_ret[i] = -0.02
    depth = compute_pullback_depth(signed_pb_ret, trend_ret)
    recent_ratio = compute_recent_ratio(signed_pb_ret, trend_ret)
    ret60 = np.full(n, 0.01)
    scale = np.full(n, 1.0)
    t = start + np.arange(n, dtype=np.int64) * HTF_MS
    panel = _manual_panel(t, close, high, low, 240, trend_pctl, trend_ret, signed_pb_ret, depth, recent_ratio,
                           60, ret60, scale)
    cell = lib.evaluate_cell(panel, 240, 0, 60)
    assert "week_block_bootstrap" in cell
    assert cell["week_block_bootstrap"]["seed"] == lib.SEED_BOOT
    assert cell["week_block_bootstrap"]["replicates"] == lib.N_BOOT


# ---------------------------------------------------------------------------
# 58/59. largest-qualifying-lag ACF logic; non-monotone ACF regression
# ---------------------------------------------------------------------------
def test_58_l_dep_uses_largest_qualifying_lag(monkeypatch):
    fake_acf = {1: 0.25, 2: 0.10, 4: 0.05, 8: 0.22, 16: 0.01, 32: 0.01, 64: 0.01}
    monkeypatch.setattr(lib, "autocorrelation_at_lag", lambda series, lag: fake_acf[lag])
    out = long_dependence_diagnostic(np.zeros(10))
    assert out["l_dep_days"] == 8


def test_59_non_monotone_acf_first_crossing_would_be_wrong(monkeypatch):
    fake_acf = {1: 0.21, 2: 0.05, 4: 0.05, 8: 0.05, 16: 0.05, 32: 0.25, 64: 0.05}
    monkeypatch.setattr(lib, "autocorrelation_at_lag", lambda series, lag: fake_acf[lag])
    out = long_dependence_diagnostic(np.zeros(10))
    assert out["l_dep_days"] == 32
    assert out["l_dep_days"] != 1


# ---------------------------------------------------------------------------
# 60/61. 2025/2026 partition read rejected
# ---------------------------------------------------------------------------
def test_60_61_2025_and_2026_development_reads_rejected(tmp_path: Path):
    monthly = tmp_path / "canonical" / "1m" / "monthly"
    monthly.mkdir(parents=True)
    (monthly / "2024-12.parquet").write_bytes(b"x")
    (monthly / "2025-01.parquet").write_bytes(b"x")
    (monthly / "2026-01.parquet").write_bytes(b"x")
    paths = lib.list_development_parquet_paths(tmp_path)
    assert [p.name for p in paths] == ["2024-12.parquet"]
    with pytest.raises(ValidationWindowForbidden, match="2025"):
        lib._forbid_partition_name("2025-01.parquet")
    with pytest.raises(ValidationWindowForbidden, match="2026"):
        lib._forbid_partition_name("2026-01.parquet")


# ---------------------------------------------------------------------------
# 62. non-UTC process timezone does not change UTC semantics
# ---------------------------------------------------------------------------
def test_62_utc_grid_stable_under_non_utc_process_tz(monkeypatch):
    monkeypatch.setenv("TZ", "America/New_York")
    os.environ["TZ"] = "America/New_York"
    t = int(datetime(2020, 6, 1, 0, 0, tzinfo=UTC).timestamp() * 1000)
    assert is_grid_ms(t)
    assert not is_grid_ms(t + BAR_MS)
    assert is_grid_ms(t + HTF_MS)
    assert development_t_max_ms() % HTF_MS == 0
    assert utc_day_key(t) == "2020-06-01"


# ---------------------------------------------------------------------------
# bonus: negative control sanity (mirrors H03's precedent; not separately
# numbered above but exercises negative_control_bundle directly)
# ---------------------------------------------------------------------------
def test_negative_control_bundle_reports_collision_and_mean():
    n = 40
    start = int(datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000)
    t = start + np.arange(n, dtype=np.int64) * HTF_MS
    close = np.full(n, 100.0)
    high = close + 1
    low = close - 1
    trend_pctl = np.full(n, np.nan)
    trend_ret = np.full(n, np.nan)
    signed_pb_ret = np.full(n, np.nan)
    for i in (5, 15):
        trend_pctl[i] = 0.90
        trend_ret[i] = 0.10
        signed_pb_ret[i] = -0.02
    depth = compute_pullback_depth(signed_pb_ret, trend_ret)
    recent_ratio = compute_recent_ratio(signed_pb_ret, trend_ret)
    ret60 = np.full(n, 0.01)
    scale = np.full(n, 1.0)
    panel = _manual_panel(t, close, high, low, 240, trend_pctl, trend_ret, signed_pb_ret, depth, recent_ratio,
                           60, ret60, scale)
    cand_idx = np.array([5, 15])
    cand = outcome_bundle(panel, cand_idx, 240, 60)
    raw_mask = np.zeros(n, dtype=bool)
    raw_mask[cand_idx] = True
    out = negative_control_bundle(panel, cand, raw_mask, 60)
    assert out["collision_fraction"] >= 0.0
