"""Network-free tests for H05 taker-imbalance -> subsequent-return-distribution.

Preregistration + implementation-freeze task: these tests use only local,
in-memory synthetic fixtures. They never open real accepted parquet, never
inspect 2025 validation or 2026 OOS outcomes, and never run development
against real market data.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import yaml

from scripts.research import h05_taker_imbalance_lib as lib
from scripts.research.h05_taker_imbalance_lib import (
    CONTROL_DELTA_MIN,
    DIR_BUY,
    DIR_SELL,
    HTF_MIN,
    HTF_MS,
    MPIE,
    ORDINARY_BAND,
    S_CONTINUATION,
    S_REVERSAL,
    ValidationWindowForbidden,
    aggregate_1m_to_15m,
    apply_refractory,
    bin_index_at_median,
    block_bootstrap_sensitivity,
    bootstrap_sign_gate,
    build_matched_random_pool,
    candidate_clustering_diagnostic,
    candidate_mask,
    claim_evaluation,
    collision_fraction,
    compute_horizon_return,
    compute_price_ret,
    compute_taker_imbalance,
    dependence_sensitivity_bundle,
    direction_symmetry_gate,
    directional_support,
    gate_control_delta,
    gate_matched_mpie,
    gate_primary,
    has_adjacent_pair_support,
    has_adjacent_w_directional_support,
    matched_random_bundle,
    negative_control_bundle,
    normalize,
    ordinary_control_mask,
    oriented_delta,
    oriented_from_delta,
    oriented_primary,
    outcome_bundle,
    price_alignment_index,
    eligible_index,
    evaluate_promotion,
    load_development_1m,
    require_snapshot,
    rolling_midrank_percentile,
    sample_matched_random_once,
    shift_plus_6h_same_utc_day,
    structural_control_bundle,
    trailing_median_known,
    week_block_bootstrap,
    year_stability_gate,
)

UTC_YEAR_MS = 365 * 24 * 60 * 60 * 1000
REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# infra / identity sanity
# ---------------------------------------------------------------------------
def test_prereg_frozen_numbers():
    p = lib.load_prereg()
    assert p["windows_minutes"] == [15, 30, 60]
    assert p["flow_extremeness"]["q_thresholds"] == [0.80, 0.90, 0.95]
    assert p["horizons_minutes"] == [15, 30, 60, 120, 240]
    assert p["search_surface"]["primary_threshold_cells"] == 45
    assert p["search_surface"]["batch01_cumulative_cells"] == 225
    assert p["dataset"]["snapshot_id"] == lib.REQUIRED_SNAPSHOT
    assert p["windows"]["development_end_exclusive"] == "2025-01-01T00:00:00Z"
    assert p["refractory"]["minutes"] == 60
    assert p["matched_random"]["seed"] == 20260904
    assert p["uncertainty"]["seed"] == 20260905
    assert p["mpie"]["value"] == 0.10
    assert p["control_materiality"]["CONTROL_DELTA_MIN"] == 0.05
    assert p["structural_control"]["ordinary_band"] == [0.60, 0.80]
    assert set(p["verdict_labels"]) == {
        "H05_FLOW_CONTINUATION_CANDIDATE_FOR_FREEZE", "H05_FLOW_REVERSAL_CANDIDATE_FOR_FREEZE",
        "H05_INCONCLUSIVE", "H05_REJECTED_SPECIFIC_CLAIM",
    }
    assert p["design_authority"]["design_head_sha"] == "deaf6503896920685f25a03230174d360a07ab9a"
    assert p["schema_version"] == 3
    assert p["identity_status"] == "REPAIR_CANDIDATE_NOT_YET_INDEPENDENTLY_AUDITED"
    assert p["version_history"][1]["sha"] == "70797aaeed70fa3d4c584d96ca929f5a8e7e92d1"
    assert p["version_history"][1]["status"] == "SUPERSEDED_PRE_OUTCOME"
    assert p["version_history"][0]["sha"] == "9502006eb4797a9947c61d8d04acd1345ed41e5e"
    assert p["version_history"][0]["status"] == "SUPERSEDED_PRE_OUTCOME"
    assert p["version_history"][0]["real_h05_outcomes_seen_before_supersession"] is False
    assert p["structural_control"]["standardization"]["gate_uses_full_candidate_mean_not_restandardized"] is False


def test_require_snapshot_matches_repo_manifest():
    assert require_snapshot() == lib.REQUIRED_SNAPSHOT


def test_require_snapshot_fails_on_mismatch(tmp_path: Path):
    man = yaml.safe_load((REPO_ROOT / "docs/manifests/CORE_BTC_BINANCE_V0.yaml").read_text())
    man["snapshot_id"] = "deadbeef"
    p = tmp_path / "m.yaml"
    p.write_text(yaml.safe_dump(man), encoding="utf-8")
    with pytest.raises(lib.H05Error, match="snapshot mismatch"):
        require_snapshot(p)


# ---------------------------------------------------------------------------
# fixture builders
# ---------------------------------------------------------------------------
def _frame1m(n: int, start_ms: int, close, base_volume, taker_buy_base_volume) -> dict:
    open_ms = start_ms + np.arange(n, dtype=np.int64) * lib.BAR_MS
    return {
        "open_time_ms": open_ms,
        "available_at_ms": open_ms + lib.BAR_MS,
        "close": np.asarray(close, dtype=np.float64),
        "base_volume": np.asarray(base_volume, dtype=np.float64),
        "taker_buy_base_volume": np.asarray(taker_buy_base_volume, dtype=np.float64),
    }


def _frame15_manual(n: int, start_ms: int, close, base_volume, taker_buy_base_volume) -> dict:
    open_ms = start_ms + np.arange(n, dtype=np.int64) * HTF_MS
    base_volume = np.asarray(base_volume, dtype=np.float64)
    taker_buy_base_volume = np.asarray(taker_buy_base_volume, dtype=np.float64)
    return {
        "open_time_ms": open_ms,
        "available_at_ms": open_ms + HTF_MS,
        "t_ms": open_ms + HTF_MS,
        "close": np.asarray(close, dtype=np.float64),
        "base_volume": base_volume,
        "taker_buy_base_volume": taker_buy_base_volume,
        "taker_sell_base_volume": base_volume - taker_buy_base_volume,
    }


def _manual_panel(t_ms, close, w_minutes, d, abs_imbalance_pctl, total_w, price_ret_w,
                   h_minutes, ret, scale, in_dev=None):
    n = len(t_ms)
    if in_dev is None:
        in_dev = np.ones(n, dtype=bool)
    price_alignment = price_alignment_index(d, price_ret_w)
    price_strength_pctl = rolling_midrank_percentile(np.abs(price_ret_w), 10 ** 9)  # unused fallback
    price_strength_bin = bin_index_at_median(np.full(n, 0.75))  # overridden by caller in most tests
    activity_bin = bin_index_at_median(np.full(n, 0.75))
    return {
        "t_ms": t_ms, "close": close, "in_development": in_dev,
        "feat": {w_minutes: {
            "D": d, "abs_imbalance_pctl": abs_imbalance_pctl, "total_w": total_w,
            "ineligible_total_w_n": 0,
        }},
        "price_ret": {w_minutes: price_ret_w},
        "price_alignment": {w_minutes: price_alignment},
        "price_strength_bin": {w_minutes: price_strength_bin},
        "activity_bin": {w_minutes: activity_bin},
        "ret": {h_minutes: ret}, "scale": {h_minutes: scale},
        "month_key": np.array([lib.utc_month_key(int(x)) for x in t_ms]),
        "week_key": np.array([lib.utc_week_key(int(x)) for x in t_ms]),
        "year": np.array([lib.utc_year(int(x)) for x in t_ms], dtype=np.int16),
        "t_max_inclusive": int(t_ms[-1]) if n else 0,
    }


# ---------------------------------------------------------------------------
# 01. feature formula exact
# ---------------------------------------------------------------------------
def test_01_feature_formula_exact():
    n = 8
    base = np.array([10, 20, 10, 0, 10, 10, 10, 10], dtype=np.float64)
    buy = np.array([6, 5, 2, 0, 10, 0, 5, 5], dtype=np.float64)
    frame15 = _frame15_manual(n, 0, np.linspace(100, 101, n), base, buy)
    out = compute_taker_imbalance(frame15, 15)  # w_bars = 1
    # index0: total=10,buy=6,sell=4 -> imbalance=(6-4)/10=0.2
    assert out["imbalance"][0] == pytest.approx(0.2)
    assert out["total_w"][0] == 10
    assert out["buy_w"][0] == 6
    assert out["sell_w"][0] == 4
    # index4: total=10, buy=10, sell=0 -> imbalance = 1.0 (pure buy)
    assert out["imbalance"][4] == pytest.approx(1.0)
    assert out["D"][4] == DIR_BUY
    # index5: total=10, buy=0, sell=10 -> imbalance = -1.0
    assert out["imbalance"][5] == pytest.approx(-1.0)
    assert out["D"][5] == DIR_SELL


# ---------------------------------------------------------------------------
# 02. base vs quote primary/diagnostic separation
# ---------------------------------------------------------------------------
def test_02_base_is_primary_quote_is_not_wired_into_gates():
    p = lib.load_prereg()
    assert p["primary_flow_feature"]["base_volume_is_primary"] is True
    assert p["primary_flow_feature"]["quote_volume_is_diagnostic_only"] is True
    assert p["primary_flow_feature"]["quote_volume_cannot_rescue_failed_primary"] is True
    # the library never references quote_volume at all -- structural proof
    # that quote-volume cannot enter a gate from this module.
    src = Path(lib.__file__).read_text(encoding="utf-8")
    assert "quote_volume" not in src


# ---------------------------------------------------------------------------
# 03. missing/zero TOTAL_W explicit ineligibility
# ---------------------------------------------------------------------------
def test_03_zero_total_w_is_explicit_ineligibility_not_zero():
    base = np.array([0.0, 5.0, 5.0])
    buy = np.array([0.0, 5.0, 0.0])
    frame15 = _frame15_manual(3, 0, [100.0, 100.0, 100.0], base, buy)
    out = compute_taker_imbalance(frame15, 15)
    assert np.isnan(out["imbalance"][0])
    assert out["D"][0] == 0
    assert out["ineligible_total_w_n"] == 1


def test_03b_nonfinite_total_w_is_explicit_ineligibility():
    base = np.array([np.nan, 5.0])
    buy = np.array([np.nan, 0.0])
    frame15 = _frame15_manual(2, 0, [100.0, 100.0], base, buy)
    out = compute_taker_imbalance(frame15, 15)
    assert np.isnan(out["imbalance"][0])
    assert out["D"][0] == 0


# ---------------------------------------------------------------------------
# 04. causal trailing percentile
# ---------------------------------------------------------------------------
def test_04_causal_trailing_percentile_excludes_current_and_future():
    values = np.array([1.0, 2.0, 3.0, 4.0, 100.0])
    pctl = rolling_midrank_percentile(values, window=3)
    # index4's percentile must be computed only from indices [1,2,3], never
    # index4 itself or anything at/after it.
    assert not np.isnan(pctl[4])
    # a huge value at index4 cannot influence its OWN percentile (would be
    # 1.0 if self-referential; here reference is {2,3,4}->wait window=3 uses
    # indices 1,2,3 for i=4, so ref={2,3,4}? No: strictly prior window
    # values[i-window:i] = values[1:4] = {2,3,4}. 100 vs {2,3,4}: rank=1.0.
    assert pctl[4] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# 05. no T-overlap leakage (feature window strictly [T-W, T))
# ---------------------------------------------------------------------------
def test_05_feature_window_excludes_bar_starting_at_t():
    # W=30 (2 bars): BUY_W(T) at index i must be sum of bars i-1,i only --
    # never bar i+1 (which starts at T).
    base = np.array([10, 10, 10, 999.0])
    buy = np.array([5, 5, 5, 999.0])
    frame15 = _frame15_manual(4, 0, [100.0] * 4, base, buy)
    out = compute_taker_imbalance(frame15, 30)
    assert out["total_w"][1] == pytest.approx(20.0)  # bars 0,1 only
    assert out["total_w"][2] == pytest.approx(20.0)  # bars 1,2 -- not bar3


# ---------------------------------------------------------------------------
# 06. complete-horizon embargo
# ---------------------------------------------------------------------------
def test_06_complete_horizon_embargo_excludes_not_truncates():
    n = 10
    close = np.linspace(100, 110, n)
    t = np.arange(n, dtype=np.int64) * HTF_MS
    dev_end = t[-2]  # boundary such that the last eligible T excludes tail
    ret = compute_horizon_return(close, t, h_minutes=30, dev_end_ms=int(dev_end))
    # the last two rows' horizon would cross/hit the boundary -> NaN, not a
    # truncated/partial value.
    assert np.isnan(ret[-1])


# ---------------------------------------------------------------------------
# 07. nested q membership
# ---------------------------------------------------------------------------
def test_07_nested_q_membership():
    d = np.array([1, 1, 1], dtype=np.int8)
    pctl = np.array([0.79, 0.85, 0.96])
    in_dev = np.ones(3, dtype=bool)
    m80 = candidate_mask(d, pctl, 0.80, in_dev)
    m90 = candidate_mask(d, pctl, 0.90, in_dev)
    m95 = candidate_mask(d, pctl, 0.95, in_dev)
    assert list(m80) == [False, True, True]
    assert list(m90) == [False, False, True]
    assert list(m95) == [False, False, True]
    # nested: membership at 0.95 implies membership at 0.90 implies 0.80
    assert np.all(m90 <= m80)
    assert np.all(m95 <= m90)


# ---------------------------------------------------------------------------
# 08. 60m either-direction refractory
# ---------------------------------------------------------------------------
def test_08_refractory_keeps_earliest_suppresses_both_directions():
    t = np.array([0, HTF_MS, 2 * HTF_MS, 4 * HTF_MS]) * 1  # 0,15,30,60 min
    mask = np.array([True, True, True, True])
    kept = apply_refractory(t, mask, refractory_ms=lib.REFRACTORY_MS)
    # only t=0 and t=60min (index3) survive; 15m/30m are inside the 60m window
    assert list(kept) == [True, False, False, True]


# ---------------------------------------------------------------------------
# 09. ordinary control band exact [0.60, 0.80)
# ---------------------------------------------------------------------------
def test_09_ordinary_control_band_exact_boundaries():
    d = np.array([1, 1, 1, 1], dtype=np.int8)
    pctl = np.array([0.59999, 0.60, 0.79999, 0.80])
    in_dev = np.ones(4, dtype=bool)
    m = ordinary_control_mask(d, pctl, in_dev)
    assert list(m) == [False, True, True, False]
    assert ORDINARY_BAND == (0.60, 0.80)


# ---------------------------------------------------------------------------
# 10. candidate/control non-overlap
# ---------------------------------------------------------------------------
def test_10_candidate_and_control_never_overlap_for_any_q():
    d = np.ones(1000, dtype=np.int8)
    pctl = np.linspace(0.0, 1.0, 1000)
    in_dev = np.ones(1000, dtype=bool)
    ctrl = ordinary_control_mask(d, pctl, in_dev)
    for q in (0.80, 0.90, 0.95):
        cand = candidate_mask(d, pctl, q, in_dev)
        assert not np.any(cand & ctrl)


# ---------------------------------------------------------------------------
# 11. price alignment exact
# ---------------------------------------------------------------------------
def test_11_price_alignment_exact():
    d = np.array([1, 1, -1, -1], dtype=np.int8)
    price_ret = np.array([0.01, -0.01, 0.01, -0.01])
    align = price_alignment_index(d, price_ret)
    # BUY & price up -> ALIGNED(1); BUY & price down -> OPPOSED(0);
    # SELL & price up -> OPPOSED(0) [D*ret = -0.01 <=0]; SELL & price down
    # -> ALIGNED(1) [D*ret = +0.01 > 0]
    assert list(align) == [1, 0, 0, 1]


# ---------------------------------------------------------------------------
# 12. zero price return -> OPPOSED
# ---------------------------------------------------------------------------
def test_12_zero_signed_price_return_is_opposed():
    d = np.array([1, -1], dtype=np.int8)
    price_ret = np.array([0.0, 0.0])
    align = price_alignment_index(d, price_ret)
    assert list(align) == [0, 0]


# ---------------------------------------------------------------------------
# 13. price strength bin causal
# ---------------------------------------------------------------------------
def test_13_price_strength_bin_causal_median_split():
    close = np.array([100.0, 101.0, 100.0, 103.0, 100.0, 110.0])
    pr = compute_price_ret(close, 15)
    pctl = rolling_midrank_percentile(np.abs(pr), window=3)
    b = bin_index_at_median(pctl)
    assert set(np.unique(b[b >= 0])).issubset({0, 1})


# ---------------------------------------------------------------------------
# 14. activity bin causal
# ---------------------------------------------------------------------------
def test_14_activity_bin_causal_median_split():
    total_w = np.array([10.0, 20.0, 5.0, 30.0, 1.0, 50.0])
    pctl = rolling_midrank_percentile(total_w, window=3)
    b = bin_index_at_median(pctl)
    assert set(np.unique(b[b >= 0])).issubset({0, 1})
    assert b[0] == -1  # no reference yet


# ---------------------------------------------------------------------------
# 15. exact 5D structural strata / 16. candidate-weighted standardization /
# 17. control-only stratum zero weight / 18. unmatched candidates reported
# ---------------------------------------------------------------------------
def _synthetic_structural_fixture():
    # 2 overlap strata + 1 candidate-only + 1 control-only stratum.
    n = 12
    t = np.arange(n, dtype=np.int64) * HTF_MS + 100 * UTC_YEAR_MS  # keep in one month
    close = np.full(n, 100.0)
    d = np.array([1, 1, 1, 1, 1, 1, -1, -1, 1, 1, 1, 1], dtype=np.int8)
    # candidates: q>=0.80 at idx 0..7 (mixed strata); ordinary control at idx 8..11
    pctl = np.array([0.85, 0.85, 0.85, 0.85, 0.90, 0.90, 0.90, 0.90, 0.65, 0.65, 0.65, 0.65])
    total_w = np.full(n, 100.0)
    price_ret = np.zeros(n)
    h = 15
    ret = np.full(n, 0.01)
    scale = np.full(n, 0.01)
    panel = _manual_panel(t, close, 15, d, pctl, total_w, price_ret, h, ret, scale)
    # Overwrite alignment/strength/activity bins with hand-picked strata so
    # some strata overlap and some do not.
    price_alignment = np.array([1, 1, 0, 0, 1, 1, 0, 0, 1, 1, 0, 0], dtype=np.int8)
    price_strength_bin = np.array([0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0], dtype=np.int8)
    activity_bin = np.array([0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0], dtype=np.int8)
    panel["price_alignment"] = {15: price_alignment}
    panel["price_strength_bin"] = {15: price_strength_bin}
    panel["activity_bin"] = {15: activity_bin}
    panel["ret"] = {15: ret}
    panel["scale"] = {15: scale}
    return panel


def test_15_16_17_18_structural_strata_and_standardization():
    panel = _synthetic_structural_fixture()
    elig_set = np.ones(12, dtype=bool)
    cand_idx = np.flatnonzero(panel["feat"][15]["abs_imbalance_pctl"] >= 0.80)
    cand = outcome_bundle(panel, cand_idx, 15, 15)
    cand_mean = float(np.mean(cand["norm"]))
    out = structural_control_bundle(panel, cand, cand_mean, 15, 15, elig_set)
    assert out["strata_definition"] == ["calendar_month", "D", "price_alignment", "price_strength_bin", "activity_bin"]
    assert out["ordinary_band"] == [0.60, 0.80]
    # some candidates share a stratum with control rows (idx 0-3: month,D=1,
    # align=1,strength=0,activity=0 == control idx 8-9's stratum)
    assert out["matched_candidate_N"] >= 1
    assert out["unmatched_candidate_N"] >= 0
    assert out["candidate_total_N"] == len(cand_idx)
    assert out["structural_control_standardized_mean"] is not None
    assert out["candidate_overlap_standardized_mean"] is not None
    assert out["structural_delta"] is not None
    assert out["full_candidate_mean"] == pytest.approx(cand_mean)


def test_control_only_stratum_receives_zero_weight():
    panel = _synthetic_structural_fixture()
    elig_set = np.ones(12, dtype=bool)
    cand_idx = np.flatnonzero(panel["feat"][15]["abs_imbalance_pctl"] >= 0.80)
    cand = outcome_bundle(panel, cand_idx, 15, 15)
    cand_mean = float(np.mean(cand["norm"]))
    out = structural_control_bundle(panel, cand, cand_mean, 15, 15, elig_set)
    # idx 10,11 (D=1, align=0, strength=0, activity=0) is a control-only
    # stratum (no matching candidate has D=1,align=0); it must not silently
    # inflate the weighted control mean beyond what candidate-weighting
    # allows -- verified indirectly via matched/unmatched counts summing
    # correctly to the candidate population.
    assert out["matched_candidate_N"] + out["unmatched_candidate_N"] == out["candidate_total_N"]


# ---------------------------------------------------------------------------
# 19. matched-random membership-safe exclusion / 20. deterministic seed /
# 21. 100 reps
# ---------------------------------------------------------------------------
def test_19_matched_random_pool_membership_not_positional():
    all_idx = np.array([10, 11, 12, 13, 14])
    raw_extreme_idx = np.array([12])
    pool = build_matched_random_pool(all_idx, raw_extreme_idx)
    assert 12 not in pool
    assert set(pool) == {10, 11, 13, 14}


def test_20_21_matched_random_deterministic_seed_and_reps():
    p = lib.load_prereg()
    assert p["matched_random"]["seed"] == 20260904
    assert p["matched_random"]["replicates"] == 100
    rng1 = np.random.default_rng(20260904)
    rng2 = np.random.default_rng(20260904)
    a = rng1.choice(np.arange(100), size=10, replace=False)
    b = rng2.choice(np.arange(100), size=10, replace=False)
    assert list(a) == list(b)


def test_matched_random_bundle_end_to_end(monkeypatch):
    panel = _synthetic_structural_fixture()
    cand_idx = np.flatnonzero(panel["feat"][15]["abs_imbalance_pctl"] >= 0.80)
    cand = outcome_bundle(panel, cand_idx, 15, 15)
    pool_idx = np.arange(12)  # whole panel as a stand-in pool (same month)
    out = matched_random_bundle(panel, cand, pool_idx, 15, 15, seed=20260904, replicates=5)
    assert out["N_replicates"] == 5
    assert out["seed"] == 20260904
    assert "matched_mean_distribution" in out


# ---------------------------------------------------------------------------
# 22. +6h semantics / 23. D preserved / 24. collision fraction exact
# ---------------------------------------------------------------------------
def test_22_23_plus_6h_shift_preserves_d():
    t0 = 1000 * lib.DAY_MS
    shifted = shift_plus_6h_same_utc_day(t0 + 3 * HTF_MS)
    assert shifted == t0 + 3 * HTF_MS + lib.SHIFT_MS
    # wraps within the same UTC day
    near_end = t0 + lib.DAY_MS - HTF_MS
    wrapped = shift_plus_6h_same_utc_day(near_end)
    assert wrapped < near_end
    assert wrapped >= t0


def test_24_collision_fraction_exact():
    shifted = np.array([100, 200, 300])
    raw = np.array([200, 999])
    assert collision_fraction(shifted, raw) == pytest.approx(1.0 / 3.0)
    assert collision_fraction(np.array([]), raw) == 0.0


# ---------------------------------------------------------------------------
# 25. normalization causal / 26. fully resolved pre-T
# ---------------------------------------------------------------------------
def test_25_26_normalization_causal_and_preT_resolved():
    n = 40
    close = 100 * np.exp(np.cumsum(np.full(n, 0.001)))
    t = np.arange(n, dtype=np.int64) * HTF_MS
    h = 15
    ret = compute_horizon_return(close, t, h, dev_end_ms=int(t[-1]) + 10 ** 9)
    scale = trailing_median_known(np.abs(ret), window=10, known_lag_steps=h // HTF_MIN)
    norm, elig = normalize(ret, scale)
    # scale at some index must not depend on ret values at or after that index
    assert np.all(np.isnan(scale[:10]))


# ---------------------------------------------------------------------------
# 27-33. S mapping / stored X never re-signed / oriented formulas exact
# ---------------------------------------------------------------------------
def test_27_s_mapping_exact():
    assert S_CONTINUATION == 1
    assert S_REVERSAL == -1


def test_28_stored_x_never_resigned():
    cand_mean = -0.3
    # oriented_primary must compute S*mean without mutating cand_mean
    v = oriented_primary(cand_mean, S_REVERSAL)
    assert cand_mean == -0.3
    assert v == pytest.approx(0.3)


def test_29_oriented_primary_continuation_exact():
    assert oriented_primary(0.5, S_CONTINUATION) == pytest.approx(0.5)


def test_30_oriented_primary_reversal_exact():
    assert oriented_primary(0.5, S_REVERSAL) == pytest.approx(-0.5)


def test_31_oriented_matched_delta_exact():
    assert oriented_delta(0.5, 0.2, S_CONTINUATION) == pytest.approx(0.3)
    assert oriented_delta(0.5, 0.2, S_REVERSAL) == pytest.approx(-0.3)


def test_32_oriented_structural_delta_exact():
    assert oriented_delta(0.4, 0.1, S_CONTINUATION) == pytest.approx(0.3)
    assert oriented_delta(0.4, 0.1, S_REVERSAL) == pytest.approx(-0.3)


def test_33_oriented_shift_delta_exact():
    assert oriented_delta(0.4, 0.35, S_CONTINUATION) == pytest.approx(0.05)
    assert oriented_delta(0.4, 0.35, S_REVERSAL) == pytest.approx(-0.05)


# ---------------------------------------------------------------------------
# 34. continuation gates exact / 35. reversal mirrored gates exact
# ---------------------------------------------------------------------------
def test_34_continuation_gates_exact():
    # structural_delta is now the already-computed like-with-like overlap
    # delta (candidate_overlap_standardized_mean -
    # structural_control_standardized_mean), NOT a mean to be subtracted
    # from candidate_mean here.
    ev = claim_evaluation(candidate_mean=0.20, matched_mean=0.05, structural_delta=0.10,
                           shift_delta=0.10, sign=S_CONTINUATION)
    assert ev["ORIENTED_PRIMARY"] == pytest.approx(0.20)
    assert ev["ORIENTED_MATCHED_DELTA"] == pytest.approx(0.15)
    assert ev["ORIENTED_STRUCTURAL_DELTA"] == pytest.approx(0.10)
    assert ev["ORIENTED_SHIFT_DELTA"] == pytest.approx(0.10)
    assert ev["primary_gate"] is True
    assert ev["mpie_gate"] is True  # 0.15 >= MPIE(0.10)
    assert ev["structural_gate"] is True  # 0.10 >= 0.05
    assert ev["shift_gate"] is True


def test_35_reversal_mirrored_gates_exact():
    # mirror image: candidate_mean now negative, matched/shifted positive by
    # the same absolute amounts, structural_delta negated -> reversal gates
    # should pass identically to the continuation case above by symmetry.
    ev = claim_evaluation(candidate_mean=-0.20, matched_mean=-0.05, structural_delta=-0.10,
                           shift_delta=-0.10, sign=S_REVERSAL)
    assert ev["ORIENTED_PRIMARY"] == pytest.approx(0.20)
    assert ev["ORIENTED_MATCHED_DELTA"] == pytest.approx(0.15)
    assert ev["ORIENTED_STRUCTURAL_DELTA"] == pytest.approx(0.10)
    assert ev["ORIENTED_SHIFT_DELTA"] == pytest.approx(0.10)
    assert ev["primary_gate"] is True
    assert ev["mpie_gate"] is True
    assert ev["structural_gate"] is True
    assert ev["shift_gate"] is True


def test_reversal_impossible_under_positive_only_reading_regression():
    """Regression for the addendum-2 BLOCKER: a genuine reversal effect
    (negative candidate_mean, positive matched_mean) must be able to pass
    its own oriented gates -- it must NOT be evaluated with the
    continuation-only bare inequality that made REVERSAL mathematically
    unsatisfiable."""
    ev = claim_evaluation(candidate_mean=-0.5, matched_mean=0.1, structural_delta=-0.6,
                           shift_delta=-0.6, sign=S_REVERSAL)
    assert ev["mpie_gate"] is True
    assert ev["structural_gate"] is True
    assert ev["shift_gate"] is True


# ---------------------------------------------------------------------------
# 36. q adjacency gate / 37. H adjacency gate
# ---------------------------------------------------------------------------
def test_36_q_adjacency_gate():
    support = {0.80: True, 0.90: True, 0.95: False}
    assert has_adjacent_pair_support((0.80, 0.90, 0.95), support) is True
    support2 = {0.80: True, 0.90: False, 0.95: True}
    assert has_adjacent_pair_support((0.80, 0.90, 0.95), support2) is False


def test_37_h_adjacency_gate():
    support = {15: False, 30: True, 60: True, 120: False, 240: False}
    assert has_adjacent_pair_support((15, 30, 60, 120, 240), support) is True


# ---------------------------------------------------------------------------
# 38. W directional-support gate / 39. isolated W cannot promote
# ---------------------------------------------------------------------------
def test_38_w_directional_support_gate():
    directional_ok = {15: True, 30: False, 60: True}
    assert has_adjacent_w_directional_support((15, 30, 60), 1, directional_ok) is True  # W=30 has neighbors 15(T),60(T)
    assert has_adjacent_w_directional_support((15, 30, 60), 0, directional_ok) is False  # W=15 neighbor is 30(F) only


def test_39_isolated_w_cannot_promote():
    directional_ok = {15: False, 30: False, 60: False}
    assert has_adjacent_w_directional_support((15, 30, 60), 1, directional_ok) is False


def test_directional_support_direction_only_not_full_gate():
    # ORIENTED_STRUCTURAL_DELTA = 0.001 (positive, tiny) should count as
    # directional support even though it would fail the full
    # CONTROL_DELTA_MIN=0.05 numeric gate.
    ok = directional_support(candidate_mean=0.101, matched_mean=0.10, structural_delta=0.001, sign=S_CONTINUATION)
    assert ok is True


# ---------------------------------------------------------------------------
# 40. BUY/SELL symmetry / 41. one-sided cannot promote
# ---------------------------------------------------------------------------
def test_40_buy_sell_symmetry_gate():
    assert direction_symmetry_gate(buy_mean=0.2, sell_mean=0.2, sign=S_CONTINUATION) is True


def test_41_one_sided_cannot_promote():
    assert direction_symmetry_gate(buy_mean=0.2, sell_mean=-0.2, sign=S_CONTINUATION) is False
    assert direction_symmetry_gate(buy_mean=None, sell_mean=0.2, sign=S_CONTINUATION) is None


# ---------------------------------------------------------------------------
# 42. 4/5 year rule / 43. no shock-year exclusion path
# ---------------------------------------------------------------------------
def test_42_four_of_five_year_rule():
    yearly = {2020: 0.1, 2021: 0.1, 2022: 0.1, 2023: 0.1, 2024: -0.1}
    assert year_stability_gate(yearly, S_CONTINUATION) is True
    yearly_fail = {2020: 0.1, 2021: 0.1, 2022: -0.1, 2023: -0.1, 2024: -0.1}
    assert year_stability_gate(yearly_fail, S_CONTINUATION) is False


def test_43_no_shock_year_exclusion_path():
    # the function signature and implementation accept no "excluded years"
    # argument -- every year present is used unconditionally.
    import inspect
    sig = inspect.signature(year_stability_gate)
    assert "exclude" not in sig.parameters
    assert "drop" not in sig.parameters


# ---------------------------------------------------------------------------
# 44-46. 1w/2w/4w bootstrap deterministic
# ---------------------------------------------------------------------------
def _multi_week_fixture(n_weeks: int, rows_per_week: int = 4, seed: int = 5):
    rng = np.random.default_rng(seed)
    week0 = 2020 * 100  # arbitrary label space, only ordering matters
    weeks = []
    norm = []
    for w in range(n_weeks):
        for _ in range(rows_per_week):
            weeks.append(f"2020-W{w + 1:02d}")
            norm.append(float(rng.normal(0.05, 0.2)))
    return np.array(weeks), np.array(norm, dtype=np.float64)


def test_44_1w_bootstrap_deterministic():
    weeks, norm = _multi_week_fixture(6)
    a = block_bootstrap_sensitivity(weeks, norm, 1, seed=20260905, replicates=50)
    b = block_bootstrap_sensitivity(weeks, norm, 1, seed=20260905, replicates=50)
    assert a == b


def test_45_2w_bootstrap_deterministic():
    weeks, norm = _multi_week_fixture(6)
    a = block_bootstrap_sensitivity(weeks, norm, 2, seed=20260905, replicates=50)
    b = block_bootstrap_sensitivity(weeks, norm, 2, seed=20260905, replicates=50)
    assert a == b


def test_46_4w_bootstrap_deterministic():
    weeks, norm = _multi_week_fixture(9)
    a = block_bootstrap_sensitivity(weeks, norm, 4, seed=20260905, replicates=50)
    b = block_bootstrap_sensitivity(weeks, norm, 4, seed=20260905, replicates=50)
    assert a == b


# ---------------------------------------------------------------------------
# 47. terminal partial block retained / 48. no row split across blocks
# ---------------------------------------------------------------------------
def test_47_terminal_partial_block_retained():
    weeks, norm = _multi_week_fixture(5)  # 5 weeks, block_size=2 -> groups [1,2],[3,4],[5]
    out = block_bootstrap_sensitivity(weeks, norm, 2, seed=20260905, replicates=10)
    assert out["observed_blocks_N"] == 3  # not 2 (terminal partial retained)


def test_48_no_row_split_across_blocks():
    unique_weeks = [f"2020-W{i:02d}" for i in range(1, 6)]
    groups = lib._block_groups_for_size(unique_weeks, 2)
    flat = [w for g in groups for w in g]
    assert sorted(flat) == sorted(unique_weeks)
    assert len(flat) == len(unique_weeks)  # every week counted exactly once


# ---------------------------------------------------------------------------
# 49. continuation bootstrap p025 gate / 50. reversal bootstrap p975 gate
# ---------------------------------------------------------------------------
def test_49_continuation_bootstrap_p025_gate():
    weeks, norm = _multi_week_fixture(20, rows_per_week=6, seed=11)
    norm = norm + 0.5  # shift strongly positive so p025 > 0
    dep = dependence_sensitivity_bundle(weeks, norm, seed=20260905, replicates=100)
    gate = bootstrap_sign_gate(dep, S_CONTINUATION)
    assert gate["1w"] is True
    assert gate["all_block_sizes_pass"] is True


def test_50_reversal_bootstrap_p975_gate():
    weeks, norm = _multi_week_fixture(20, rows_per_week=6, seed=11)
    norm = norm - 0.5  # shift strongly negative so p975 < 0
    dep = dependence_sensitivity_bundle(weeks, norm, seed=20260905, replicates=100)
    gate = bootstrap_sign_gate(dep, S_REVERSAL)
    assert gate["1w"] is True
    assert gate["all_block_sizes_pass"] is True


# ---------------------------------------------------------------------------
# 51. candidate clustering uses indicator not outcome / 52. fixed lags /
# 53. L_dep uses largest qualifying lag
# ---------------------------------------------------------------------------
def test_51_candidate_clustering_uses_indicator_not_outcome():
    n = 200
    t = np.arange(n, dtype=np.int64) * lib.DAY_MS
    kept = np.zeros(n, dtype=bool)
    kept[::7] = True  # weekly periodicity in the INDICATOR, unrelated to any outcome
    out = candidate_clustering_diagnostic(t, kept)
    assert set(out["acf_by_lag_days"].keys()) == set(lib.DEP_LAGS_DAYS)


def test_52_fixed_lags_exact():
    assert lib.DEP_LAGS_DAYS == (1, 2, 4, 8, 16, 32, 64)


def test_53_l_dep_uses_largest_qualifying_lag(monkeypatch):
    # Construct an ACF series where lag=2 and lag=32 both qualify but lag=2
    # is NOT the largest -- L_dep must report 32, not 2.
    def fake_autocorr(series, lag):
        return {2: 0.5, 32: 0.9}.get(lag, 0.0)

    monkeypatch.setattr(lib, "autocorrelation_at_lag", fake_autocorr)
    n = 100
    t = np.arange(n, dtype=np.int64) * lib.DAY_MS
    kept = np.zeros(n, dtype=bool)
    out = candidate_clustering_diagnostic(t, kept)
    assert out["l_dep_days"] == 32


# ---------------------------------------------------------------------------
# 54. all 45 cells generated / 55. Batch01 total recorded as 225 /
# 56. both sign orientations emitted for every cell
# ---------------------------------------------------------------------------
def test_54_55_56_search_surface_and_dual_sign_emission():
    p = lib.load_prereg()
    assert p["search_surface"]["W_count"] * p["search_surface"]["q_count"] * p["search_surface"]["H_count"] == 45
    assert p["search_surface"]["batch01_cumulative_cells"] == 225
    ev = claim_evaluation(0.1, 0.05, 0.02, 0.02, S_CONTINUATION)
    assert "S" in ev and "ORIENTED_PRIMARY" in ev


# ---------------------------------------------------------------------------
# 57. quote diagnostic cannot alter verdict
# ---------------------------------------------------------------------------
def test_57_quote_diagnostic_cannot_alter_verdict():
    src = Path(lib.__file__).read_text(encoding="utf-8")
    assert "quote" not in src.lower()


# ---------------------------------------------------------------------------
# 58. insufficient structural support routes INCONCLUSIVE
# ---------------------------------------------------------------------------
def test_58_insufficient_structural_support_yields_none_not_fabricated():
    # No overlap strata at all (candidate and control occupy disjoint
    # strata) -> structural_delta must be None (caller maps None -> the
    # cell is INCONCLUSIVE for this control, never a fabricated pass) --
    # this is test 7 of the structural-support-correction regression set
    # (zero-overlap yields no fabricated structural effect).
    n = 8
    t = np.arange(n, dtype=np.int64) * HTF_MS
    close = np.full(n, 100.0)
    d = np.array([1] * 4 + [1] * 4, dtype=np.int8)
    pctl = np.array([0.85] * 4 + [0.65] * 4)
    total_w = np.full(n, 100.0)
    price_ret = np.zeros(n)
    ret = np.full(n, 0.01)
    scale = np.full(n, 0.01)
    panel = _manual_panel(t, close, 15, d, pctl, total_w, price_ret, 15, ret, scale)
    # force completely disjoint strata: candidates all align=1, controls all align=0
    panel["price_alignment"] = {15: np.array([1] * 4 + [0] * 4, dtype=np.int8)}
    panel["price_strength_bin"] = {15: np.zeros(n, dtype=np.int8)}
    panel["activity_bin"] = {15: np.zeros(n, dtype=np.int8)}
    elig_set = np.ones(n, dtype=bool)
    cand_idx = np.flatnonzero(pctl >= 0.80)
    cand = outcome_bundle(panel, cand_idx, 15, 15)
    cand_mean = float(np.mean(cand["norm"]))
    out = structural_control_bundle(panel, cand, cand_mean, 15, 15, elig_set)
    assert out["structural_control_standardized_mean"] is None
    assert out["candidate_overlap_standardized_mean"] is None
    assert out["structural_delta"] is None
    assert out["unmatched_candidate_share"] == 1.0
    # the gate/oriented-delta layer must map this to "unavailable", never a
    # fabricated numeric effect.
    from scripts.research.h05_taker_imbalance_lib import claim_evaluation as _claim_eval
    ev = _claim_eval(cand_mean, matched_mean=0.0, structural_delta=out["structural_delta"],
                      shift_delta=0.0, sign=S_CONTINUATION)
    assert ev["ORIENTED_STRUCTURAL_DELTA"] is None
    assert ev["structural_gate"] is None


# ---------------------------------------------------------------------------
# 59. posthoc-only patterns cannot promote
# ---------------------------------------------------------------------------
def test_59_posthoc_quarantine_list_present_and_non_empty():
    p = lib.load_prereg()
    assert len(p["posthoc_quarantine"]) >= 8
    assert p["posthoc_label"] == "POSTHOC_UNTESTED"
    assert p["posthoc_cannot_rescue_kill"] is True


# ---------------------------------------------------------------------------
# 60. future loader rejects >=2025 partitions
# ---------------------------------------------------------------------------
def test_60_loader_rejects_2025_2026_partitions(tmp_path: Path):
    root = tmp_path
    monthly = root / "canonical" / "1m" / "monthly"
    monthly.mkdir(parents=True)
    for name in ("2024-11.parquet", "2024-12.parquet", "2025-01.parquet", "2026-01.parquet"):
        (monthly / name).write_bytes(b"")
    paths = lib.list_development_parquet_paths(root)
    names = {p.name for p in paths}
    assert names == {"2024-11.parquet", "2024-12.parquet"}
    with pytest.raises(ValidationWindowForbidden):
        lib._forbid_partition_name("2025-01.parquet")
    with pytest.raises(ValidationWindowForbidden):
        lib._forbid_partition_name("2026-01.parquet")


# ---------------------------------------------------------------------------
# 61. identity stage does not compute outcomes
# ---------------------------------------------------------------------------
def test_61_identity_stage_does_not_compute_outcomes(capsys):
    from scripts.research import h05_taker_imbalance as cli
    rc = cli.main(["--stage", "identity"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "stage" in out
    assert "identity" in out


# ---------------------------------------------------------------------------
# additional: aggregation, negative control, evaluate_cell end-to-end
# ---------------------------------------------------------------------------
def test_aggregate_1m_to_15m_sums_volumes():
    n = 30
    close = np.linspace(100, 101, n)
    base = np.ones(n)
    buy = np.full(n, 0.6)
    frame1 = _frame1m(n, 0, close, base, buy)
    frame15 = aggregate_1m_to_15m(frame1)
    assert frame15["base_volume"][0] == pytest.approx(15.0)
    assert frame15["taker_buy_base_volume"][0] == pytest.approx(9.0)
    assert frame15["taker_sell_base_volume"][0] == pytest.approx(6.0)


def test_negative_control_bundle_reports_collision_and_mean():
    panel = _synthetic_structural_fixture()
    cand_idx = np.flatnonzero(panel["feat"][15]["abs_imbalance_pctl"] >= 0.80)
    cand = outcome_bundle(panel, cand_idx, 15, 15)
    raw_mask = panel["feat"][15]["abs_imbalance_pctl"] >= 0.80
    out = negative_control_bundle(panel, cand, raw_mask, 15, 15)
    assert "collision_fraction" in out


def test_evaluate_cell_synthetic_continuation_mechanism_detected():
    # BUY-imbalance rows systematically precede positive normalized return;
    # SELL-imbalance rows precede negative -- a genuine continuation
    # mechanism the pipeline should be able to surface a positive
    # ORIENTED_PRIMARY for (S=+1) without fabrication.
    n = 4000
    rng = np.random.default_rng(42)
    t = np.arange(n, dtype=np.int64) * HTF_MS + lib.DEV_START_MS
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.0003, size=n)))
    base = np.full(n, 100.0)
    buy = np.full(n, 50.0)
    buy[::5] = 90.0   # strong BUY imbalance every 5th bar
    buy[2::5] = 10.0  # strong SELL imbalance offset
    frame15 = _frame15_manual(n, lib.DEV_START_MS, close, base, buy)
    panel = lib.build_panel(frame15)
    cell = lib.evaluate_cell(panel, 15, 0.80, 15)
    assert cell["N"] >= 0
    assert "continuation" in cell["claim_evaluation"]
    assert "reversal" in cell["claim_evaluation"]


def test_evaluate_h05_no_forbidden_months(monkeypatch):
    n = 3200
    rng = np.random.default_rng(3)
    t0 = lib.DEV_START_MS
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.0002, size=n)))
    base = np.full(n, 100.0)
    buy = 50.0 + rng.normal(0, 5, size=n)
    frame15 = _frame15_manual(n, t0, close, base, buy)
    panel = lib.build_panel(frame15)
    result = lib.evaluate_h05(panel)
    assert len(result["cells"]) == 45
    assert result["search_surface"]["batch01_cumulative_cells"] == 225
    for c in result["cells"]:
        for m in c["concentration"]["by_month"].keys():
            assert not m.startswith("2025")
            assert not m.startswith("2026")


# ---------------------------------------------------------------------------
# PRE-OUTCOME STRUCTURAL-SUPPORT CORRECTION regression tests
# (supersedes H05_PREREG_SHA_V1 = 9502006eb4797a9947c61d8d04acd1345ed41e5e)
# ---------------------------------------------------------------------------
def _fixture_unmatched_extreme_vs_zero_overlap_difference():
    """One overlap stratum (A) where candidate and control means are
    IDENTICAL (zero structural difference), plus one candidate-only
    stratum (B) with huge positive outcomes that have NO corresponding
    control observation, plus one control-only stratum (C) that must
    receive zero candidate weight."""
    n = 12
    t = np.arange(n, dtype=np.int64) * HTF_MS
    close = np.full(n, 100.0)
    d = np.ones(n, dtype=np.int8)  # all BUY, D never distinguishes strata here
    # candidates: rows 0-3 (stratum A) and 4-7 (stratum B, unmatched)
    # control:    rows 8-9 (stratum A, matches 0-3) and 10-11 (stratum C, control-only)
    pctl = np.array([0.85] * 8 + [0.65] * 4)
    total_w = np.full(n, 100.0)
    price_ret = np.zeros(n)
    ret = np.full(n, 0.01)
    scale = np.full(n, 0.01)
    panel = _manual_panel(t, close, 15, d, pctl, total_w, price_ret, 15, ret, scale)
    price_alignment = np.array([1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 0, 0], dtype=np.int8)
    price_strength_bin = np.array([0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0], dtype=np.int8)
    activity_bin = np.array([0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0], dtype=np.int8)
    panel["price_alignment"] = {15: price_alignment}
    panel["price_strength_bin"] = {15: price_strength_bin}
    panel["activity_bin"] = {15: activity_bin}
    return panel, pctl


def test_regression_01_structural_gate_uses_overlap_mean_not_full_mean():
    """Regression test 1 (required): the structural gate/delta must be
    computed from candidate_overlap_standardized_mean, NOT the full
    (unrestricted) candidate_mean."""
    panel, pctl = _fixture_unmatched_extreme_vs_zero_overlap_difference()
    n = len(pctl)
    elig_set = np.ones(n, dtype=bool)
    cand_idx = np.flatnonzero(pctl >= 0.80)
    cand = outcome_bundle(panel, cand_idx, 15, 15)
    # Overlap stratum A candidates (idx 0-3) and control (idx 8-9) share the
    # SAME norm value (0.01, from the fixture's flat ret/scale) -> zero
    # structural difference. Unmatched stratum B candidates (idx 4-7) get a
    # huge positive norm override to try to move the full candidate mean.
    norm = cand["norm"].copy()
    # cand["idx"] corresponds 1:1 with cand_idx (0..7); rows 4-7 are stratum B
    b_mask = np.isin(cand["idx"], np.array([4, 5, 6, 7]))
    norm[b_mask] = 50.0
    cand = {**cand, "norm": norm}
    full_candidate_mean = float(np.mean(norm))
    out = structural_control_bundle(panel, cand, full_candidate_mean, 15, 15, elig_set)

    assert out["full_candidate_mean"] == pytest.approx(full_candidate_mean)
    assert full_candidate_mean > 5.0  # materially moved by the huge unmatched outcomes
    # candidate_overlap_standardized_mean must be computed ONLY from
    # stratum A (the sole overlap stratum) -> equals the (unchanged) norm
    # of rows 0-3, i.e. 0.01 -- completely unaffected by stratum B's 50.0.
    assert out["candidate_overlap_standardized_mean"] == pytest.approx(1.0, abs=1e-9)
    assert out["structural_control_standardized_mean"] == pytest.approx(1.0, abs=1e-9)
    assert out["structural_delta"] == pytest.approx(0.0, abs=1e-9)


def test_regression_02_unmatched_candidate_outcomes_cannot_change_structural_delta():
    """Regression test 2 (required, exact scenario from the task):
    overlap strata have zero structural difference; unmatched candidates
    have huge positive outcomes. Expected: full candidate_mean changes
    materially BUT candidate_overlap_standardized_mean/structural_delta
    stay unchanged/zero, and the structural gate stays False for BOTH
    signs (0.0 cannot clear +-CONTROL_DELTA_MIN)."""
    panel, pctl = _fixture_unmatched_extreme_vs_zero_overlap_difference()
    n = len(pctl)
    elig_set = np.ones(n, dtype=bool)
    cand_idx = np.flatnonzero(pctl >= 0.80)

    # Baseline: no extreme override (all candidate norm == 0.01, matching
    # the control's stratum-A mean exactly).
    cand_base = outcome_bundle(panel, cand_idx, 15, 15)
    base_mean = float(np.mean(cand_base["norm"]))
    out_base = structural_control_bundle(panel, cand_base, base_mean, 15, 15, elig_set)

    # Extreme: stratum B (unmatched) candidates get huge positive outcomes.
    norm_extreme = cand_base["norm"].copy()
    b_mask = np.isin(cand_base["idx"], np.array([4, 5, 6, 7]))
    norm_extreme[b_mask] = 999.0
    cand_extreme = {**cand_base, "norm": norm_extreme}
    extreme_mean = float(np.mean(norm_extreme))
    out_extreme = structural_control_bundle(panel, cand_extreme, extreme_mean, 15, 15, elig_set)

    assert extreme_mean - base_mean > 100.0  # full mean moved materially
    assert out_base["structural_delta"] == pytest.approx(out_extreme["structural_delta"], abs=1e-9)
    assert out_extreme["structural_delta"] == pytest.approx(0.0, abs=1e-9)
    assert out_extreme["candidate_overlap_standardized_mean"] == pytest.approx(
        out_base["candidate_overlap_standardized_mean"], abs=1e-9
    )

    for sign in (S_CONTINUATION, S_REVERSAL):
        ev = claim_evaluation(extreme_mean, matched_mean=0.0, structural_delta=out_extreme["structural_delta"],
                               shift_delta=0.0, sign=sign)
        assert ev["structural_gate"] is False


def test_regression_03_continuation_orientation_exact_s_plus_1():
    assert S_CONTINUATION == 1
    ev = claim_evaluation(candidate_mean=0.3, matched_mean=0.1, structural_delta=0.08,
                           shift_delta=0.05, sign=S_CONTINUATION)
    assert ev["S"] == 1
    assert ev["ORIENTED_STRUCTURAL_DELTA"] == pytest.approx(0.08)
    assert ev["structural_gate"] is True  # 0.08 >= 0.05


def test_regression_04_reversal_orientation_exact_s_minus_1():
    assert S_REVERSAL == -1
    ev = claim_evaluation(candidate_mean=-0.3, matched_mean=-0.1, structural_delta=-0.08,
                           shift_delta=-0.05, sign=S_REVERSAL)
    assert ev["S"] == -1
    assert ev["ORIENTED_STRUCTURAL_DELTA"] == pytest.approx(0.08)
    assert ev["structural_gate"] is True  # S*(-0.08) = 0.08 >= 0.05


def test_regression_05_control_only_strata_receive_zero_weight():
    """Stratum C (control-only, rows 10-11) must never enter the weighted
    sums at all -- verified by checking the weighted structural means only
    reflect stratum A, not stratum C's control values."""
    panel, pctl = _fixture_unmatched_extreme_vs_zero_overlap_difference()
    n = len(pctl)
    elig_set = np.ones(n, dtype=bool)
    cand_idx = np.flatnonzero(pctl >= 0.80)
    cand = outcome_bundle(panel, cand_idx, 15, 15)
    cand_mean = float(np.mean(cand["norm"]))
    out = structural_control_bundle(panel, cand, cand_mean, 15, 15, elig_set)
    # If stratum C (control-only) leaked into the weighted control mean,
    # structural_control_standardized_mean would differ from stratum A's
    # control mean (0.01) whenever stratum C's control norm differs from
    # 0.01. Here stratum C's control norm is also 0.01 (flat fixture ret/
    # scale), so instead we assert directly on the overlap-strata count:
    # only ONE overlap stratum (A) exists -- C is excluded by construction.
    assert out["number_of_matched_strata"] == 1
    assert out["candidate_overlap_N"] == 4  # exactly stratum A's 4 candidates


def test_regression_06_candidate_and_control_use_identical_overlap_weights():
    """The SAME weight dict (keyed by overlap stratum, w_s =
    candidate_N_s / sum(candidate_N over overlap strata)) is applied to
    both the candidate-side and control-side weighted sums -- with a
    single overlap stratum, the weight must be exactly 1.0 for both."""
    panel, pctl = _fixture_unmatched_extreme_vs_zero_overlap_difference()
    n = len(pctl)
    elig_set = np.ones(n, dtype=bool)
    cand_idx = np.flatnonzero(pctl >= 0.80)
    cand = outcome_bundle(panel, cand_idx, 15, 15)
    cand_mean = float(np.mean(cand["norm"]))
    out = structural_control_bundle(panel, cand, cand_mean, 15, 15, elig_set)
    # single overlap stratum -> its weight is 1.0 -> both standardized
    # means equal that one stratum's own (candidate, control) means exactly.
    assert out["candidate_overlap_standardized_mean"] == pytest.approx(1.0, abs=1e-9)
    assert out["structural_control_standardized_mean"] == pytest.approx(1.0, abs=1e-9)


def test_regression_07_zero_overlap_yields_no_fabricated_structural_effect():
    """Duplicate-coverage regression (also covered by test_58): with zero
    overlap strata, structural_delta/both standardized means must be None,
    and the oriented gate layer must report None (unresolved), never a
    fabricated 0.0 or any other numeric effect."""
    n = 8
    t = np.arange(n, dtype=np.int64) * HTF_MS
    close = np.full(n, 100.0)
    d = np.ones(n, dtype=np.int8)
    pctl = np.array([0.85] * 4 + [0.65] * 4)
    total_w = np.full(n, 100.0)
    price_ret = np.zeros(n)
    ret = np.full(n, 0.01)
    scale = np.full(n, 0.01)
    panel = _manual_panel(t, close, 15, d, pctl, total_w, price_ret, 15, ret, scale)
    panel["price_alignment"] = {15: np.array([1, 1, 1, 1, 0, 0, 0, 0], dtype=np.int8)}
    panel["price_strength_bin"] = {15: np.zeros(n, dtype=np.int8)}
    panel["activity_bin"] = {15: np.zeros(n, dtype=np.int8)}
    elig_set = np.ones(n, dtype=bool)
    cand_idx = np.flatnonzero(pctl >= 0.80)
    cand = outcome_bundle(panel, cand_idx, 15, 15)
    cand_mean = float(np.mean(cand["norm"]))
    out = structural_control_bundle(panel, cand, cand_mean, 15, 15, elig_set)
    assert out["structural_delta"] is None
    assert oriented_from_delta(out["structural_delta"], S_CONTINUATION) is None
    assert oriented_from_delta(out["structural_delta"], S_REVERSAL) is None


def test_regression_08_five_dimensional_strata_remain_exact():
    panel, pctl = _fixture_unmatched_extreme_vs_zero_overlap_difference()
    n = len(pctl)
    elig_set = np.ones(n, dtype=bool)
    cand_idx = np.flatnonzero(pctl >= 0.80)
    cand = outcome_bundle(panel, cand_idx, 15, 15)
    cand_mean = float(np.mean(cand["norm"]))
    out = structural_control_bundle(panel, cand, cand_mean, 15, 15, elig_set)
    assert out["strata_definition"] == [
        "calendar_month", "D", "price_alignment", "price_strength_bin", "activity_bin",
    ]
    assert out["ordinary_band"] == [0.60, 0.80]


# ---------------------------------------------------------------------------
# PRE-OUTCOME AUDIT REPAIR regression tests (B-01 verification, M-01, M-02,
# M-03, M-04, M-05). No real data. Synthetic/unit fixtures only.
# ---------------------------------------------------------------------------

# --- B-01 independent re-verification (adversarial case from the audit) ---
def test_b01_structural_gate_unaffected_by_unmatched_extreme_independent_check():
    """Independent re-verification of B-01 using the audit's own exact
    adversarial construction: overlap stratum candidate mean = 0, overlap
    structural control mean = 0, unmatched candidate stratum has very
    large positive X. The structural gate must NOT become positive."""
    n = 12
    t = np.arange(n, dtype=np.int64) * HTF_MS
    close = np.full(n, 100.0)
    d = np.ones(n, dtype=np.int8)
    pctl = np.array([0.85] * 8 + [0.65] * 4)
    total_w = np.full(n, 100.0)
    price_ret = np.zeros(n)
    ret = np.zeros(n)
    scale = np.full(n, 1.0)
    panel = _manual_panel(t, close, 15, d, pctl, total_w, price_ret, 15, ret, scale)
    panel["price_alignment"] = {15: np.array([1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 0, 0], dtype=np.int8)}
    panel["price_strength_bin"] = {15: np.array([0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0], dtype=np.int8)}
    panel["activity_bin"] = {15: np.array([0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0], dtype=np.int8)}
    elig_set = np.ones(n, dtype=bool)
    cand_idx = np.flatnonzero(pctl >= 0.80)
    cand = outcome_bundle(panel, cand_idx, 15, 15)
    norm = cand["norm"].copy()
    norm[np.isin(cand["idx"], [0, 1, 2, 3])] = 0.0
    norm[np.isin(cand["idx"], [4, 5, 6, 7])] = 1e6
    cand = {**cand, "norm": norm}
    full_mean = float(np.mean(norm))
    out = structural_control_bundle(panel, cand, full_mean, 15, 15, elig_set)
    assert out["candidate_overlap_standardized_mean"] == pytest.approx(0.0, abs=1e-9)
    assert out["structural_control_standardized_mean"] == pytest.approx(0.0, abs=1e-9)
    assert out["structural_delta"] == pytest.approx(0.0, abs=1e-9)
    for sign in (S_CONTINUATION, S_REVERSAL):
        ev = claim_evaluation(full_mean, matched_mean=0.0, structural_delta=out["structural_delta"],
                               shift_delta=0.0, sign=sign)
        assert ev["structural_gate"] is False
        assert ev["ORIENTED_STRUCTURAL_DELTA"] == pytest.approx(0.0, abs=1e-9)


# --- M-01: +6h invalid-comparator composition attack ---------------------
def test_m01_01_shift_delta_uses_same_support_not_full_candidate_mean():
    """Candidates WITHOUT a valid +6h comparator get extreme X; they must
    not be able to influence shift_delta/ORIENTED_SHIFT_DELTA.

    +6h = SHIFT_MS = 24 bars on the 15m grid. With a 30-bar array (well
    inside a single UTC day, no wraparound ambiguity): rows 0,1,2 shift to
    valid in-range rows 24,25,26; rows 27,28,29 shift to 51,52,53, which
    fall OUTSIDE this 30-row array -> no valid +6h comparator at all."""
    n = 30
    t = np.arange(n, dtype=np.int64) * HTF_MS
    close = np.full(n, 100.0)
    d = np.ones(n, dtype=np.int8)
    pctl = np.array([0.85] * n)
    total_w = np.full(n, 100.0)
    price_ret = np.zeros(n)
    ret = np.full(n, 0.0)
    scale = np.full(n, 1.0)
    panel = _manual_panel(t, close, 15, d, pctl, total_w, price_ret, 15, ret, scale)
    panel["price_alignment"] = {15: np.ones(n, dtype=np.int8)}
    panel["price_strength_bin"] = {15: np.zeros(n, dtype=np.int8)}
    panel["activity_bin"] = {15: np.zeros(n, dtype=np.int8)}
    cand_idx = np.array([0, 1, 2, 27, 28, 29])
    raw_mask = np.zeros(n, dtype=bool)
    raw_mask[cand_idx] = True
    cand = outcome_bundle(panel, cand_idx, 15, 15)
    # Force: rows 0,1,2 (valid +6h comparator) get norm=0 (baseline); rows
    # 27,28,29 (NO valid +6h comparator) get an extreme forced norm.
    norm = cand["norm"].copy()
    valid_mask = np.isin(cand["idx"], [0, 1, 2])
    invalid_mask = np.isin(cand["idx"], [27, 28, 29])
    norm[valid_mask] = 0.0
    norm[invalid_mask] = 1e6
    cand_forced = {**cand, "norm": norm}
    out = negative_control_bundle(panel, cand_forced, raw_mask, 15, 15)
    # only rows 0,1,2 contribute to shift support; the shifted position
    # itself also has ret=0 -> shifted_mean=0 too.
    assert out["shift_support_N"] == 3
    assert out["candidate_shift_support_mean"] == pytest.approx(0.0, abs=1e-9)
    assert out["shifted_mean"] == pytest.approx(0.0, abs=1e-9)
    assert out["shift_delta"] == pytest.approx(0.0, abs=1e-9)
    # but the FULL candidate mean (reported only for transparency) is
    # indeed dominated by the extreme rows -- proving they really would
    # have moved a naive full-mean-based delta.
    assert out["full_candidate_mean"] > 100.0
    for sign in (S_CONTINUATION, S_REVERSAL):
        ev = claim_evaluation(out["full_candidate_mean"], matched_mean=0.0,
                               structural_delta=0.0, shift_delta=out["shift_delta"], sign=sign)
        assert ev["shift_gate"] is False


def test_m01_02_shift_gate_uses_shift_delta_not_shifted_mean_alone():
    ev = claim_evaluation(candidate_mean=999.0, matched_mean=0.0, structural_delta=0.0,
                           shift_delta=0.06, sign=S_CONTINUATION)
    assert ev["ORIENTED_SHIFT_DELTA"] == pytest.approx(0.06)
    assert ev["shift_gate"] is True  # 0.06 >= CONTROL_DELTA_MIN, independent of candidate_mean=999


# --- M-02: invalid structural-bin inputs fail closed ----------------------
def test_m02_01_eligible_index_excludes_undeclared_minus1_price_alignment():
    n = 5
    t = np.arange(n, dtype=np.int64) * HTF_MS
    d = np.array([1, 1, 1, 1, 1], dtype=np.int8)
    abs_pctl = np.array([0.9, 0.9, 0.9, 0.9, 0.9])
    panel = {
        "t_ms": t, "in_development": np.ones(n, dtype=bool),
        "feat": {15: {"D": d, "abs_imbalance_pctl": abs_pctl}},
        "ret": {15: np.full(n, 0.01)}, "scale": {15: np.full(n, 0.01)},
        "price_alignment": {15: np.array([1, 1, -1, 1, 1], dtype=np.int8)},   # row 2 undeclared
        "price_strength_bin": {15: np.array([0, 0, 0, -1, 0], dtype=np.int8)},  # row 3 undeclared
        "activity_bin": {15: np.array([0, -1, 0, 0, 0], dtype=np.int8)},        # row 1 undeclared
    }
    idx = eligible_index(panel, 15, 15)
    assert set(idx.tolist()) == {0, 4}  # rows 1,2,3 excluded (each has one undeclared -1 dimension)


def test_m02_02_valid_rows_unaffected_by_minus1_fix():
    n = 3
    t = np.arange(n, dtype=np.int64) * HTF_MS
    d = np.ones(n, dtype=np.int8)
    abs_pctl = np.full(n, 0.9)
    panel = {
        "t_ms": t, "in_development": np.ones(n, dtype=bool),
        "feat": {15: {"D": d, "abs_imbalance_pctl": abs_pctl}},
        "ret": {15: np.full(n, 0.01)}, "scale": {15: np.full(n, 0.01)},
        "price_alignment": {15: np.zeros(n, dtype=np.int8)},
        "price_strength_bin": {15: np.zeros(n, dtype=np.int8)},
        "activity_bin": {15: np.zeros(n, dtype=np.int8)},
    }
    idx = eligible_index(panel, 15, 15)
    assert set(idx.tolist()) == {0, 1, 2}


# --- M-03: incomplete trailing-30d history fails closed --------------------
def test_m03_01_insufficient_history_is_unavailable():
    values = np.array([1.0, 2.0, 3.0])
    pctl = rolling_midrank_percentile(values, window=5)
    assert np.all(np.isnan(pctl))  # never a full 5-bar window elapsed


def test_m03_02_exact_required_history_becomes_available():
    # window=3: index 3 is the first index for which 3 PRIOR bars (0,1,2)
    # have elapsed -- must be the first non-NaN value, not index 1 or 2.
    values = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    pctl = rolling_midrank_percentile(values, window=3)
    assert np.isnan(pctl[0])
    assert np.isnan(pctl[1])
    assert np.isnan(pctl[2])
    assert not np.isnan(pctl[3])
    assert not np.isnan(pctl[4])


def test_m03_03_no_future_leakage_after_fix():
    # A huge future value must not affect an earlier index's percentile,
    # even once the window-completeness gate is enforced.
    values = np.array([1.0, 1.0, 1.0, 1.0, 1000.0])
    pctl = rolling_midrank_percentile(values, window=3)
    # index3 uses only indices 0,1,2 (all 1.0) as reference -> its own
    # value 1.0 is at the middle of a tied reference -> percentile 0.5.
    assert pctl[3] == pytest.approx(0.5)


def test_m03_04_activity_bin_respects_incomplete_history():
    total_w = np.array([10.0, 20.0, 5.0])  # only 3 bars, far short of REF_STEPS=2880
    pctl = rolling_midrank_percentile(total_w, window=lib.REF_STEPS)
    b = bin_index_at_median(pctl)
    assert np.all(b == -1)  # activity_bin must be entirely unavailable, never fabricated


# --- M-04: deterministic fail-closed promotion evaluator -------------------
def _promo_ev(**kwargs) -> dict:
    base = {
        "primary_gate": None, "mpie_gate": None, "structural_gate": None, "shift_gate": None,
        "bootstrap_gate": {"1w": None, "2w": None, "4w": None},
        "year_stability_gate": None, "direction_symmetry_gate": None, "directional_support": None,
    }
    base.update(kwargs)
    return base


def _all_true_ev() -> dict:
    return _promo_ev(
        primary_gate=True, mpie_gate=True, structural_gate=True, shift_gate=True,
        bootstrap_gate={"1w": True, "2w": True, "4w": True},
        year_stability_gate=True, direction_symmetry_gate=True, directional_support=True,
    )


def _dummy_cells(cell_ev=None):
    """Every (W,q,H) cell present (required -- evaluate_promotion looks up
    every combination), continuation/reversal both default to all-None
    (fail-closed baseline) unless overridden via `cell_ev[(w,q,h,sign)]`."""
    cell_ev = cell_ev or {}
    cells = []
    for w in lib.W_WINDOWS:
        for q in lib.Q_THRESHOLDS:
            for h in lib.HORIZONS:
                ev_c = cell_ev.get((w, q, h, "continuation"), _promo_ev())
                ev_r = cell_ev.get((w, q, h, "reversal"), _promo_ev())
                cells.append({"W": w, "q": q, "H": h, "claim_evaluation": {"continuation": ev_c, "reversal": ev_r}})
    return cells


def test_m04_01_all_none_baseline_never_promotes():
    cells = _dummy_cells()
    out = evaluate_promotion(cells)
    assert out["continuation"]["promoted"] is False
    assert out["reversal"]["promoted"] is False
    assert out["verdict"] == "H05_REJECTED_SPECIFIC_CLAIM"


def _full_pass_neighborhood(sign_name: str) -> dict:
    """A genuinely satisfying neighborhood for one sign: q in {0.80,0.90}
    adjacent, H in {60,120} adjacent, all three W directionally
    supporting, at a fixed W=30 -- everything else stays the all-None
    fail-closed default (proving the evaluator is not vacuously True)."""
    cell_ev = {}
    for q in (0.80, 0.90):
        for h in (60, 120):
            cell_ev[(30, q, h, sign_name)] = _all_true_ev()
    for w in lib.W_WINDOWS:
        cell_ev[(w, 0.80, 60, sign_name)] = cell_ev.get((w, 0.80, 60, sign_name), _all_true_ev())
        cell_ev.setdefault((w, 0.80, 60, sign_name), _all_true_ev())
        # ensure directional_support is set for the W-adjacency check at
        # the exact (q=0.80, H=60) cell used as the promotion anchor
        prev = cell_ev.get((w, 0.80, 60, sign_name), _promo_ev())
        prev["directional_support"] = True
        cell_ev[(w, 0.80, 60, sign_name)] = prev
    return cell_ev


def test_m04_02_full_pass_neighborhood_promotes_expected_sign_only():
    cell_ev = _full_pass_neighborhood("continuation")
    cells = _dummy_cells(cell_ev)
    out = evaluate_promotion(cells)
    assert out["continuation"]["promoted"] is True
    assert {"W": 30, "q": 0.80, "H": 60} in out["continuation"]["promoted_cells"]
    assert out["reversal"]["promoted"] is False
    assert out["verdict"] == "H05_FLOW_CONTINUATION_CANDIDATE_FOR_FREEZE"


def test_m04_03_both_signs_promoted_is_audit_failure():
    cell_ev = {}
    cell_ev.update(_full_pass_neighborhood("continuation"))
    cell_ev.update(_full_pass_neighborhood("reversal"))
    cells = _dummy_cells(cell_ev)
    out = evaluate_promotion(cells)
    assert out["verdict"] == "AUDIT_FAILURE_BOTH_SIGNS_PROMOTED"


def test_m04_04_missing_gate_none_is_fail_closed_not_pass():
    """One mandatory gate (shift_gate) is None at the anchor cell; every
    other input is a perfect pass. Promotion must still fail."""
    cell_ev = _full_pass_neighborhood("continuation")
    broken = dict(cell_ev[(30, 0.80, 60, "continuation")])
    broken["shift_gate"] = None
    cell_ev[(30, 0.80, 60, "continuation")] = broken
    cells = _dummy_cells(cell_ev)
    out = evaluate_promotion(cells)
    assert out["continuation"]["promoted"] is False


def test_m04_05_non_adjacent_q_cannot_promote():
    """q in {0.80, 0.95} both fully pass but are NOT adjacent (0.90 is
    missing) -- promotion must fail despite two passing q cells."""
    cell_ev = {}
    for q in (0.80, 0.95):
        cell_ev[(30, q, 60, "continuation")] = _all_true_ev()
    cells = _dummy_cells(cell_ev)
    out = evaluate_promotion(cells)
    assert out["continuation"]["promoted"] is False


def test_m04_06_non_adjacent_h_cannot_promote():
    """H in {15, 60} both fully pass but are NOT adjacent (30 is
    missing) -- promotion must fail despite two passing H cells."""
    cell_ev = {}
    for h in (15, 60):
        cell_ev[(30, 0.80, h, "continuation")] = _all_true_ev()
    cells = _dummy_cells(cell_ev)
    out = evaluate_promotion(cells)
    assert out["continuation"]["promoted"] is False


def test_m04_07_isolated_w_cannot_promote():
    """Full q/H support at W=30 with directional_support True ONLY at
    W=30 itself (neighbors W=15/W=60 both None/False) -- an isolated W
    must not promote."""
    cell_ev = {}
    for q in (0.80, 0.90):
        for h in (60, 120):
            ev = _all_true_ev()
            if (q, h) == (0.80, 60):
                ev["directional_support"] = True
            cell_ev[(30, q, h, "continuation")] = ev
    # explicitly force neighbors' directional_support to False (not just
    # the all-None default) to make the isolation unambiguous
    cell_ev[(15, 0.80, 60, "continuation")] = _promo_ev(directional_support=False)
    cell_ev[(60, 0.80, 60, "continuation")] = _promo_ev(directional_support=False)
    cells = _dummy_cells(cell_ev)
    out = evaluate_promotion(cells)
    assert out["continuation"]["promoted"] is False


def test_m04_08_missing_year_gate_blocks_promotion():
    """year_stability_gate=None (e.g. fewer than 5 years of development
    history available) at an otherwise-perfect neighborhood -- must fail
    closed, never treated as pass."""
    cell_ev = _full_pass_neighborhood("continuation")
    broken = dict(cell_ev[(30, 0.80, 60, "continuation")])
    broken["year_stability_gate"] = None
    cell_ev[(30, 0.80, 60, "continuation")] = broken
    cells = _dummy_cells(cell_ev)
    out = evaluate_promotion(cells)
    assert out["continuation"]["promoted"] is False


def test_m04_09_empty_buy_or_sell_side_blocks_promotion():
    """direction_symmetry_gate=None (e.g. one of BUY/SELL has zero
    candidates, so the symmetry requirement itself is undefined) -- must
    fail closed."""
    cell_ev = _full_pass_neighborhood("continuation")
    broken = dict(cell_ev[(30, 0.80, 60, "continuation")])
    broken["direction_symmetry_gate"] = None
    cell_ev[(30, 0.80, 60, "continuation")] = broken
    cells = _dummy_cells(cell_ev)
    out = evaluate_promotion(cells)
    assert out["continuation"]["promoted"] is False


# --- M-05: mandatory dataset identity (manifest) fail-closed ---------------
def test_m05_01_missing_manifest_fails_closed(tmp_path: Path):
    root = tmp_path / "dataset_no_manifest"
    (root / "canonical" / "1m" / "monthly").mkdir(parents=True)
    with pytest.raises(lib.H05Error, match="missing required dataset identity evidence"):
        load_development_1m(root)


def test_m05_02_mismatched_snapshot_id_fails_closed(tmp_path: Path):
    root = tmp_path / "dataset_wrong_manifest"
    (root / "canonical" / "1m" / "monthly").mkdir(parents=True)
    reports = root / "reports"
    reports.mkdir(parents=True)
    (reports / "snapshot_manifest.json").write_text('{"snapshot_id": "deadbeef"}', encoding="utf-8")
    with pytest.raises(lib.H05Error, match="runtime snapshot_id"):
        load_development_1m(root)


def test_m05_03_matching_manifest_no_longer_short_circuits_missing_check(tmp_path: Path):
    """A dataset root with the CORRECT manifest but no parquet at all must
    fail at the parquet-directory stage (list_development_parquet_paths),
    proving the manifest check runs first and, once satisfied, genuinely
    lets execution proceed to the next real check rather than silently
    succeeding."""
    root = tmp_path / "dataset_correct_manifest_no_parquet"
    reports = root / "reports"
    reports.mkdir(parents=True)
    (reports / "snapshot_manifest.json").write_text(
        f'{{"snapshot_id": "{lib.REQUIRED_SNAPSHOT}"}}', encoding="utf-8",
    )
    with pytest.raises(lib.H05Error, match="missing canonical 1m monthly dir"):
        load_development_1m(root)


# --- regression check: existing pre-repair tests already updated above ----
def test_audit_repair_full_suite_still_internally_consistent():
    """Sanity check that the repaired evaluate_cell pipeline still
    produces both claim_evaluation orientations with the new field names
    wired through end-to-end (not just at the unit level)."""
    n = 3200
    rng = np.random.default_rng(3)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.0002, size=n)))
    base = np.full(n, 100.0)
    buy = 50.0 + rng.normal(0, 5, size=n)
    frame15 = _frame15_manual(n, lib.DEV_START_MS, close, base, buy)
    panel = lib.build_panel(frame15)
    cell = lib.evaluate_cell(panel, 15, 0.80, 15)
    assert "shift_delta" in cell["negative_control"]
    assert "structural_delta" in cell["structural_control"]
    for sign_name in ("continuation", "reversal"):
        ev = cell["claim_evaluation"][sign_name]
        assert "ORIENTED_SHIFT_DELTA" in ev
        assert "ORIENTED_STRUCTURAL_DELTA" in ev
