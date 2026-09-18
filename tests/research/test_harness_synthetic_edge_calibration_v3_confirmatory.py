"""Focused implementation tests for the frozen V3 confirmatory calibration.

Every test uses disposable, non-canonical world identities. None consumes
world_index 10000..10399 (the frozen fresh-acceptance range) or 0..399 (the
V1/V2 canonical grid). No test interprets output as scientific evidence;
each is a narrow proof that the implementation matches the frozen prereg's
literal text.
"""

from __future__ import annotations

import ast
import inspect
import math
from unittest import mock

import numpy as np
import pytest

from scripts.research import harness_synthetic_edge_calibration_v1_lib as v1lib
from scripts.research import harness_synthetic_edge_calibration_v3_confirmatory as v3c
from scripts.research.harness_synthetic_edge_calibration_v3_rng import (
    V3_NAMESPACE,
    v3_namespace_seed,
)

# Disposable world_index pool, far from both canonical ranges (0..399 and
# 10000..10399). Distinct constants per test to avoid any cross-test reuse
# ambiguity.
_DISPOSABLE = iter(range(900_000, 901_000))


def _next_disposable() -> int:
    return next(_DISPOSABLE)


def _assert_disposable(world_index: int) -> None:
    assert not v3c.is_fresh_v3_world_index(world_index)
    assert not (0 <= world_index <= 399)


# =============================================================================
# 1-4: Clark-West / nested construction / no overlay
# =============================================================================


def test_clark_west_adjustment_arithmetic_on_toy_input():
    e_base = np.array([2.0, -3.0, 1.0])
    e_cand = np.array([1.0, -1.0, 0.5])
    yhat_base = np.array([10.0, 20.0, 30.0])
    yhat_cand = np.array([10.5, 19.0, 30.5])

    d = e_base**2 - e_cand**2
    expected_d_star = e_base**2 - (e_cand**2 - (yhat_base - yhat_cand) ** 2)

    y = yhat_base + e_base  # Y = BASE_PRED + e_base by construction
    diff = v3c.ScoredDifferential(
        d=d,
        d_star=expected_d_star,
        support=np.array([1.0, 0.0, 1.0]),
        era_index=np.array([0, 0, 0]),
    )
    assert np.allclose(diff.d, d)
    assert np.allclose(diff.d_star, expected_d_star)
    # hand-derived reference value for the middle observation
    manual = (-3.0) ** 2 - ((-1.0) ** 2 - (20.0 - 19.0) ** 2)
    assert math.isclose(expected_d_star[1], manual)


def test_base_cand_construction_is_nested_by_source():
    src = inspect.getsource(v1lib.expanding_era_predictions)
    assert "_design_matrix(x1[train], x2[train])" in src
    assert "_design_matrix(x1[train], x2[train], feature[train])" in src


def test_base_cand_construction_is_nested_numerically():
    world = v1lib.simulate_dgp(scenario_id="EASY", n_rows=5000, world_index=_next_disposable())
    y = np.asarray(world["Y"], dtype=np.float64)
    x1 = np.asarray(world["X1"], dtype=np.float64)
    x2 = np.asarray(world["X2"], dtype=np.float64)
    feature = np.asarray(world["S"], dtype=np.float64)
    base_design = v1lib._design_matrix(x1[:1000], x2[:1000])
    cand_design = v1lib._design_matrix(x1[:1000], x2[:1000], feature[:1000])
    assert base_design.shape[1] + 1 == cand_design.shape[1]
    assert np.array_equal(base_design, cand_design[:, :-1])


def test_expanding_era_primitive_reused_correctly():
    world = v1lib.simulate_dgp(scenario_id="EASY", n_rows=5000, world_index=_next_disposable())
    y, preds = v3c._candidate_predictions(world, "F03", 5000)
    direct = v1lib.expanding_era_predictions(
        y, np.asarray(world["X1"]), np.asarray(world["X2"]), np.asarray(world["S"]), 5000
    )
    assert np.array_equal(preds["BASE_PRED"], direct["BASE_PRED"], equal_nan=True)
    assert np.array_equal(preds["CAND_PRED"], direct["CAND_PRED"], equal_nan=True)


def test_overlay_fallback_construction_absent():
    src = inspect.getsource(v3c)
    assert "fallback" not in src.lower() or "no hand-picked rescue" in src.lower()
    assert "np.where(" not in src  # no post-hoc CAND=BASE-outside-support patch
    assert "overlay" not in src.lower().replace("# no overlay", "")


# =============================================================================
# 5: theta_hat ratio arithmetic
# =============================================================================


def test_theta_hat_ratio_arithmetic():
    support = np.array([1.0, 0.0, 1.0, 1.0, 0.0])
    d_star = np.array([2.0, 100.0, 4.0, -1.0, -50.0])
    theta = v3c.compute_theta_hat(support, d_star)
    assert math.isclose(theta, (2.0 + 4.0 - 1.0) / 3.0)


def test_theta_hat_raises_on_zero_support():
    with pytest.raises(v3c.V3WorldInvalid) as exc:
        v3c.compute_theta_hat(np.zeros(5), np.zeros(5))
    assert exc.value.guard == v3c.VALIDITY_SUPPORT


# =============================================================================
# 6-7: support validity / effective_N is diagnostic only
# =============================================================================


def _world_with_forced_support(scenario_id, n_rows, world_index, scored_positive_indices):
    """Real DGP world with S overwritten so only the given SCORED-window
    positions (0-based within the scored E2..E5 concatenation) are positive.

    Pre-scored (training-only) rows of S are left exactly as the real
    simulation produced them: F03 IS S (candidate_features()["F03"] ==
    S.copy()), so zeroing S across the whole array -- including the
    training history each expanding-era OLS fit uses -- would make F03
    a constant-zero regressor there and trigger an unrelated rank-deficiency
    failure instead of exercising the support-count guard under test.
    """
    real_world = v1lib.simulate_dgp(scenario_id=scenario_id, n_rows=n_rows, world_index=world_index)
    mask = v1lib.scored_mask(n_rows)
    scored_idx = np.flatnonzero(mask)
    s_new = np.array(real_world["S"], dtype=np.float64, copy=True)
    s_new[scored_idx] = 0.0
    for i in scored_positive_indices:
        s_new[scored_idx[i]] = 1.0
    forced = dict(real_world)
    forced["S"] = s_new
    return forced


def test_support_count_below_50_fails_validity_exactly():
    wi = _next_disposable()
    _assert_disposable(wi)
    forced = _world_with_forced_support("NULL", 5000, wi, range(10))
    with mock.patch.object(v3c, "simulate_dgp", return_value=forced):
        rec = v3c.evaluate_v3_world("NULL", 5000, wi)
    assert rec.world_valid is False
    assert rec.validity_guard_failed == v3c.VALIDITY_SUPPORT
    assert "support_count" in rec.validity_reason


def test_support_count_at_and_above_floor_is_not_support_invalid():
    wi = _next_disposable()
    _assert_disposable(wi)
    forced = _world_with_forced_support("NULL", 5000, wi, range(50))
    with mock.patch.object(v3c, "simulate_dgp", return_value=forced):
        rec = v3c.evaluate_v3_world("NULL", 5000, wi)
    # exactly at the floor: must not be rejected for support_count
    assert rec.validity_guard_failed != v3c.VALIDITY_SUPPORT


def test_effective_n_is_diagnostic_only_not_a_detected_veto():
    wi = _next_disposable()
    rec = v3c.evaluate_v3_world("EASY", 5000, wi)
    assert rec.world_valid is True
    assert rec.effective_n is not None
    assert rec.effective_n < rec.support_count  # persistent Markov support: eff_N << raw count
    # DETECTED must be derivable purely from theta_hat/p, independent of effective_n's magnitude
    assert rec.detected == bool(rec.theta_hat > 0 and rec.p_one_sided <= v3c.V3_ALPHA_ONE_SIDED)
    src = inspect.getsource(v3c.evaluate_v3_world)
    detected_line = [l for l in src.splitlines() if "detected = bool(" in l][0]
    assert "effective_n" not in detected_line and "eff_n" not in detected_line


def _old_divergent_paired_effective_n(support: np.ndarray) -> float:
    """The DELETED, non-frozen local V3 estimator this repair removes
    (non-overlapping paired-lag truncation, step=2). Reference-only, kept
    solely to prove the fixture below actually exercises a case where it
    diverges from the frozen V1 authority -- this function is not part of
    the implementation under test."""
    support = np.asarray(support, dtype=np.float64)
    support_count = int(np.sum(support))
    n = support.shape[0]
    eps = support - support.mean()
    gamma0 = float(eps @ eps) / n
    rhos = np.array([float(eps[k:] @ eps[: n - k]) / n / gamma0 for k in range(1, n)])
    total = 0.0
    k = 0
    while k + 1 < len(rhos):
        pair = rhos[k] + rhos[k + 1]
        if pair <= 0:
            break
        total += pair
        k += 2
    denom = 1.0 + 2.0 * total
    raw = support_count / denom
    return min(max(raw, 1.0), support_count)


def test_effective_n_uses_frozen_v1_authority_exactly():
    # Deterministic fixture, sized to the real n_rows=5000 scored window
    # (4 scored eras * 1000 rows = 4000), where the deleted paired (step=2)
    # estimator and the frozen V1 overlapping (step=1) estimator disagree --
    # proving this is a real regression guard, not a vacuous equality.
    n_rows = 5000
    mask = v1lib.scored_mask(n_rows)
    scored_idx = np.flatnonzero(mask)
    rng = np.random.default_rng(2)
    support = (rng.random(scored_idx.shape[0]) < 0.15).astype(np.float64)

    frozen = v1lib.effective_support_n(support)
    divergent_old = _old_divergent_paired_effective_n(support)
    assert not math.isclose(frozen, divergent_old), (
        "fixture does not exercise a real divergence between the frozen "
        "and the deleted estimator; pick a different seed"
    )

    wi = _next_disposable()
    _assert_disposable(wi)
    real_world = v1lib.simulate_dgp(scenario_id="NULL", n_rows=n_rows, world_index=wi)
    s_new = np.array(real_world["S"], dtype=np.float64, copy=True)
    s_new[scored_idx] = support
    forced = dict(real_world)
    forced["S"] = s_new
    with mock.patch.object(v3c, "simulate_dgp", return_value=forced):
        rec = v3c.evaluate_v3_world("NULL", n_rows, wi)

    assert rec.world_valid is True
    assert math.isclose(rec.effective_n, frozen)


def test_effective_n_ordinary_disposable_support_series_matches_frozen_v1():
    wi = _next_disposable()
    rec = v3c.evaluate_v3_world("EASY", 5000, wi)
    assert rec.world_valid is True
    mask = v1lib.scored_mask(5000)
    world = v3c.simulate_dgp(scenario_id="EASY", n_rows=5000, world_index=wi)
    support = np.asarray(world["S"], dtype=np.float64)[mask]
    assert math.isclose(rec.effective_n, v1lib.effective_support_n(support))


# =============================================================================
# 8: full-time-axis z_t retains S=0 positions as zeros
# =============================================================================


def test_full_time_axis_z_t_retains_zero_support_positions():
    support = np.array([0.0, 1.0, 0.0, 0.0, 1.0])
    d_star = np.array([5.0, 5.0, 5.0, 5.0, 5.0])
    theta_hat = 1.0
    z_t = support * (d_star - theta_hat)
    assert z_t.shape[0] == 5  # no gap-closing: same length as input
    assert z_t[0] == 0.0 and z_t[2] == 0.0 and z_t[3] == 0.0
    assert z_t[1] == 4.0 and z_t[4] == 4.0


# =============================================================================
# 9-11: block-length selector arithmetic
# =============================================================================


def test_selector_matches_frozen_reference_arithmetic_multiple_vectors():
    rng = np.random.default_rng(2026)
    for trial in range(4):
        x = rng.standard_normal(500).cumsum() * 0.0 + rng.standard_normal(500)
        ours = v3c.optimal_stationary_block_length(x)
        ref = _reference_single_optimal_block_sb(x)
        assert math.isclose(ours, ref, rel_tol=1e-9), (trial, ours, ref)


def _reference_single_optimal_block_sb(x: np.ndarray) -> float:
    """Independent re-derivation of arch==8.0.0's b_sb formula, used only to
    cross-check our literal port -- not imported from our implementation."""
    nobs = x.shape[0]
    eps = x - x.mean(0)
    b_max = np.ceil(min(3 * np.sqrt(nobs), nobs / 3))
    kn = max(5, int(np.log10(nobs)))
    m_max = int(np.ceil(np.sqrt(nobs))) + kn
    cv = 2 * np.sqrt(np.log10(nobs) / nobs)
    acv = np.zeros(m_max + 1)
    abs_acorr = np.zeros(m_max + 1)
    opt_m = None
    for i in range(m_max + 1):
        v1 = eps[i + 1 :] @ eps[i + 1 :]
        v2 = eps[: -(i + 1)] @ eps[: -(i + 1)]
        cross_prod = eps[i:] @ eps[: nobs - i]
        acv[i] = cross_prod / nobs
        abs_acorr[i] = np.abs(cross_prod) / np.sqrt(v1 * v2)
        if i >= kn:
            if np.all(abs_acorr[i - kn : i] < cv) and opt_m is None:
                opt_m = i - kn
    m = 2 * max(opt_m, 1) if opt_m is not None else m_max
    m = min(m, m_max)
    g = 0.0
    lr_acv = acv[0]
    for k in range(1, m + 1):
        lam = 1 if k / m <= 1 / 2 else 2 * (1 - k / m)
        g += 2 * lam * k * acv[k]
        lr_acv += 2 * lam * acv[k]
    d_sb = 2 * lr_acv**2
    b_sb = ((2 * g**2) / d_sb) ** (1 / 3) * nobs ** (1 / 3)
    return float(min(b_sb, b_max))


def test_biased_autocovariance_convention_exact():
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 2.0, 1.0, 3.0])
    eps = x - x.mean()
    nobs = x.shape[0]
    for lag in [0, 1, 2, 3]:
        expected = float(eps[lag:] @ eps[: nobs - lag]) / nobs
        got_num = eps[lag:] @ eps[: nobs - lag]
        assert math.isclose(got_num / nobs, expected)


def test_selector_degenerate_cases_fail_closed():
    assert math.isnan(v3c.optimal_stationary_block_length(np.array([1.0])))
    assert math.isnan(v3c.optimal_stationary_block_length(np.array([], dtype=np.float64).reshape(0)))
    assert math.isnan(v3c.optimal_stationary_block_length(np.zeros(500)))  # zero variance
    with pytest.raises(v3c.V3WorldInvalid):
        v3c.run_stationary_bootstrap(
            v3c.ScoredDifferential(
                d=np.zeros(4000), d_star=np.zeros(4000),
                support=np.zeros(4000), era_index=np.zeros(4000, dtype=np.int64),
            ),
            theta_hat=0.0, world_seed_int=1, feature_id="F03",
        )


def test_selector_tiny_nobs_fails_closed_no_uncaught_exception():
    # nobs=2..7: the pinned arch==8.0.0 reference algorithm itself throws a
    # shape-mismatch ValueError for these (m_max > nobs there too -- this is
    # not an implementation gap, it's the reference algorithm's own
    # degenerate regime). The literal port must fail closed instead.
    rng = np.random.default_rng(99)
    for nobs in range(2, 8):
        x = rng.normal(size=nobs)
        result = v3c.optimal_stationary_block_length(x)  # must not raise
        assert math.isnan(result)


def test_selector_tiny_nobs_maps_to_identifiability_guard_in_bootstrap():
    # SCORED_ERAS has exactly 4 eras, so the full-time-axis nobs is always a
    # multiple of 4; era width 1 -> nobs=4, squarely in the 2..7 degenerate
    # regime the selector must now fail closed on.
    n_e = 1
    rng = np.random.default_rng(100)
    d_star = rng.normal(size=4 * n_e)
    support = np.ones(4 * n_e)
    diff = v3c.ScoredDifferential(
        d=d_star.copy(),
        d_star=d_star,
        support=support,
        era_index=np.repeat(np.arange(4), n_e),
    )
    with pytest.raises(v3c.V3WorldInvalid) as exc:
        v3c.run_stationary_bootstrap(diff, theta_hat=0.0, world_seed_int=1, feature_id="F03")
    assert exc.value.guard == v3c.VALIDITY_IDENTIFIABILITY


def test_selector_valid_vectors_still_match_pinned_arch_reference_after_repair():
    # F3's fail-closed guard must not alter arithmetic for ordinary valid
    # series (only tiny/degenerate nobs gains new behavior).
    arch_base = pytest.importorskip("arch.bootstrap.base")
    rng = np.random.default_rng(2024)
    for nobs in (8, 9, 10, 20, 50, 137, 999):
        x = rng.normal(size=nobs).cumsum() * 0.1 + rng.normal(size=nobs)
        mine = v3c.optimal_stationary_block_length(x)
        ref_sb, _ = arch_base._single_optimal_block(x)
        assert mine == float(ref_sb)


def test_selector_called_once_per_world():
    wi = _next_disposable()
    calls = []
    original = v3c.optimal_stationary_block_length

    def counting(x):
        calls.append(1)
        return original(x)

    with mock.patch.object(v3c, "optimal_stationary_block_length", side_effect=counting):
        v3c.evaluate_v3_world("EASY", 5000, wi)
    assert len(calls) == 1


# =============================================================================
# 12-17: stationary bootstrap mechanics
# =============================================================================


def test_paired_bootstrap_keeps_dstar_and_support_together():
    n_e = 200
    d_star_era = np.arange(n_e, dtype=np.float64)
    support_era = (np.arange(n_e) % 7 == 0).astype(np.float64)
    rng = np.random.default_rng(99)
    idx = v3c._draw_era_block_indices(n_e, p=0.1, rng=rng)
    resampled_d = d_star_era[idx]
    resampled_s = support_era[idx]
    # every resampled row's (d*, S) pair must equal the ORIGINAL pair at that
    # same original index -- proves joint resampling, not independent shuffles
    for orig_i, d_val, s_val in zip(idx, resampled_d, resampled_s):
        assert d_val == d_star_era[orig_i]
        assert s_val == support_era[orig_i]


def test_no_block_crosses_era_boundary():
    n_e = 50
    rng = np.random.default_rng(7)
    idx = v3c._draw_era_block_indices(n_e, p=0.2, rng=rng)
    assert idx.min() >= 0
    assert idx.max() < n_e  # never references a row outside this era's own window


def test_circular_wrap_remains_within_era():
    n_e = 10
    rng = np.random.default_rng(3)
    for _ in range(20):
        idx = v3c._draw_era_block_indices(n_e, p=0.05, rng=rng)
        assert np.all((idx >= 0) & (idx < n_e))


def test_same_b_hat_reused_across_eras():
    wi = _next_disposable()
    world = v1lib.simulate_dgp(scenario_id="MODERATE", n_rows=5000, world_index=wi)
    y, preds = v3c._candidate_predictions(world, "F03", 5000)
    diff = v3c._scored_differential(world, y, preds, 5000)
    theta_hat = v3c.compute_theta_hat(diff.support, diff.d_star)
    z_t = diff.support * (diff.d_star - theta_hat)
    b_hat = v3c.optimal_stationary_block_length(z_t)
    width = diff.d_star.shape[0] // len(v1lib.SCORED_ERAS)
    ps = [v3c.block_continuation_probability(b_hat, width) for _ in range(4)]
    assert len(set(ps)) == 1  # identical clamp/round applied identically to every era


def test_exact_per_era_clamp_round_behavior():
    assert v3c.block_continuation_probability(10.4, 1000) == 1.0 / 10
    assert v3c.block_continuation_probability(0.2, 1000) == 1.0 / 1  # clamped to floor 1
    assert v3c.block_continuation_probability(5000.0, 1000) == 1.0 / 1000  # clamped to n_e


def test_B_exactly_999():
    assert v3c.V3_STATIONARY_BOOTSTRAP_REPLICATES == 999


# =============================================================================
# 18-22: RNG
# =============================================================================


def test_deterministic_v3_rng_replay():
    wi = _next_disposable()
    world = v1lib.simulate_dgp(scenario_id="EASY", n_rows=5000, world_index=wi)
    y, preds = v3c._candidate_predictions(world, "F03", 5000)
    diff = v3c._scored_differential(world, y, preds, 5000)
    theta_hat = v3c.compute_theta_hat(diff.support, diff.d_star)
    w_seed = int(v1lib.world_seed(v1lib.world_identity("EASY", 5000, wi)))
    ev1 = v3c.run_stationary_bootstrap(diff, theta_hat, world_seed_int=w_seed, feature_id="F03")
    ev2 = v3c.run_stationary_bootstrap(diff, theta_hat, world_seed_int=w_seed, feature_id="F03")
    assert np.array_equal(ev1.theta_star, ev2.theta_star)
    assert ev1.b_hat == ev2.b_hat
    assert ev1.p_one_sided == ev2.p_one_sided


def test_v3_rng_authority_used_not_v1_bootstrap_or_placebo():
    src = inspect.getsource(v3c)
    tree = ast.parse(src)
    bare_namespace_seed_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "namespace_seed"
    ]
    assert bare_namespace_seed_calls == []
    assert '"BOOTSTRAP"' not in src
    assert '"PLACEBO"' not in src
    assert "v3_namespace_seed" in src


def test_v3_namespace_token_is_v3_confirmatory():
    assert V3_NAMESPACE == "V3_CONFIRMATORY"


def test_v1_lib_namespaces_unchanged_by_this_implementation():
    assert v1lib.NAMESPACES == ("DGP", "BOOTSTRAP", "PLACEBO", "VISIBILITY")


def test_v3_rng_stream_distinct_from_v1_bootstrap_placebo_for_same_world():
    w_seed = int(v1lib.world_seed("disposable-test-identity"))
    v3_seed = v3_namespace_seed(w_seed, "F03")
    bootstrap_seed = v1lib.namespace_seed(w_seed, "BOOTSTRAP", "F03")
    placebo_seed = v1lib.namespace_seed(w_seed, "PLACEBO", "F03")
    assert v3_seed != bootstrap_seed
    assert v3_seed != placebo_seed


# =============================================================================
# 21-22: zero-support replicate invalidates whole world, no redraw
# =============================================================================


def test_zero_support_replicate_invalidates_whole_world_no_redraw():
    # Support is concentrated in the first 10 rows of era 0 only, so the
    # full-time-axis z_t series is non-degenerate (the selector yields a
    # finite b_hat) -- unlike an all-zero series, which the selector itself
    # rejects as degenerate before any bootstrap replicate is even drawn.
    n_e = 100
    n_eras = 4
    support = np.zeros(n_eras * n_e)
    support[:10] = 1.0
    d_star = np.zeros(n_eras * n_e)
    rng_seed_data = np.random.default_rng(0)
    d_star[:10] = rng_seed_data.normal(size=10)
    diff = v3c.ScoredDifferential(
        d=d_star.copy(),
        d_star=d_star,
        support=support,
        era_index=np.repeat(np.arange(n_eras), n_e),
    )
    calls = {"n": 0}

    def forced_zero_support_draw(n_e_, p, rng):
        # Deterministically excludes the only-supported rows (indices 0-9 of
        # era 0), regardless of drawn block positions, forcing every
        # replicate's resampled support to be zero.
        calls["n"] += 1
        return np.arange(10, n_e_)

    with mock.patch.object(v3c, "_draw_era_block_indices", side_effect=forced_zero_support_draw):
        with pytest.raises(v3c.V3WorldInvalid) as exc:
            v3c.run_stationary_bootstrap(diff, theta_hat=0.0, world_seed_int=42, feature_id="F03")
    assert exc.value.guard == v3c.VALIDITY_IDENTIFIABILITY
    assert "zero resampled support" in exc.value.reason
    # fails on replicate b=0 after its one draw per era -- exactly n_eras
    # calls, proving no redraw/retry is attempted for the whole world.
    assert calls["n"] == n_eras


# =============================================================================
# 23-27: studentization / p-value
# =============================================================================


def test_se_hat_uses_ddof_1_exactly():
    theta_star = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    expected = np.std(theta_star, ddof=1)
    assert not math.isclose(expected, np.std(theta_star, ddof=0))
    assert math.isclose(expected, math.sqrt(np.sum((theta_star - theta_star.mean()) ** 2) / (5 - 1)))


def test_t_obs_arithmetic():
    theta_hat, se_hat = 0.4, 0.1
    assert math.isclose(theta_hat / se_hat, 4.0)


def test_recentered_t_star_arithmetic():
    theta_hat, se_hat = 0.4, 0.1
    theta_star = np.array([0.3, 0.5, 0.4, 0.45])
    t_star = (theta_star - theta_hat) / se_hat
    assert np.allclose(t_star, [-1.0, 1.0, 0.0, 0.5])


def test_exact_finite_sample_p_value_arithmetic():
    t_obs = 2.0
    t_star = np.array([1.0, 2.0, 2.5, -1.0, 3.0] * 200)  # 1000 values, trim to 999
    t_star = t_star[:999]
    p = (1.0 + np.sum(t_star >= t_obs)) / (999.0 + 1.0)
    manual_count = int(np.sum(t_star >= 2.0))
    assert math.isclose(p, (1 + manual_count) / 1000.0)


def test_p_boundary_behavior_at_alpha():
    # exactly 49 of 999 exceed t_obs -> p = 50/1000 = 0.05 -> DETECTED boundary is <=, so this PASSES
    t_star = np.zeros(999)
    t_star[:49] = 100.0  # 49 values >= t_obs
    t_obs = 1.0
    p = (1.0 + np.sum(t_star >= t_obs)) / 1000.0
    assert math.isclose(p, 0.05)
    assert p <= v3c.V3_ALPHA_ONE_SIDED  # boundary is inclusive per frozen DETECTED rule


# =============================================================================
# 28-30: DETECTED logic and diagnostic non-interference
# =============================================================================


def test_theta_hat_zero_is_not_detected():
    world_valid = True
    theta_hat = 0.0
    p = 0.001
    detected = bool(world_valid and theta_hat > 0 and p <= v3c.V3_ALPHA_ONE_SIDED)
    assert detected is False


def test_positive_theta_and_significant_p_and_valid_implies_detected():
    world_valid = True
    theta_hat = 0.01
    p = 0.04
    detected = bool(world_valid and theta_hat > 0 and p <= v3c.V3_ALPHA_ONE_SIDED)
    assert detected is True


def test_diagnostic_fields_cannot_veto_detected():
    rec = v3c.evaluate_v3_world("EASY", 5000, _next_disposable())
    assert rec.world_valid
    recomputed = bool(rec.theta_hat > 0 and rec.p_one_sided <= v3c.V3_ALPHA_ONE_SIDED)
    assert rec.detected == recomputed
    # no placebo/materiality/era-stability field participates in the formula
    src = inspect.getsource(v3c.evaluate_v3_world)
    line = [l for l in src.splitlines() if l.strip().startswith("detected = bool(")][0]
    for forbidden in ("relative_mae", "era_effects", "placebo", "strict_pass", "support_count"):
        assert forbidden not in line


# =============================================================================
# F2 repair: required miss-explaining diagnostics are persisted, losslessly,
# and cannot influence DETECTED.
# =============================================================================


def test_f2_required_evidence_fields_exist_and_are_populated():
    rec = v3c.evaluate_v3_world("EASY", 5000, _next_disposable())
    assert rec.world_valid is True
    assert rec.world_seed_int is not None and isinstance(rec.world_seed_int, int)
    assert rec.raw_conditional_effect is not None and math.isfinite(rec.raw_conditional_effect)
    assert rec.p_margin_to_alpha is not None and math.isfinite(rec.p_margin_to_alpha)
    assert rec.bootstrap_evidence is not None


def test_f2_world_seed_persisted_even_when_world_invalid():
    # Replay identity must be recoverable even for a rejected world.
    wi = _next_disposable()
    _assert_disposable(wi)
    forced = _world_with_forced_support("NULL", 5000, wi, range(10))  # below support floor
    with mock.patch.object(v3c, "simulate_dgp", return_value=forced):
        rec = v3c.evaluate_v3_world("NULL", 5000, wi)
    assert rec.world_valid is False
    assert rec.world_seed_int == int(v1lib.world_seed(rec.world_id))


def test_f2_persisted_evidence_exactly_matches_computed_objects():
    wi = _next_disposable()
    rec = v3c.evaluate_v3_world("EASY", 5000, wi)
    assert rec.world_valid is True

    # Recompute independently from the same disposable identity and check
    # every persisted diagnostic matches bit-for-bit -- not just "exists".
    world = v3c.simulate_dgp(scenario_id="EASY", n_rows=5000, world_index=wi)
    y, preds = v3c._candidate_predictions(world, "F03", 5000)
    diff = v3c._scored_differential(world, y, preds, 5000)
    theta_hat = v3c.compute_theta_hat(diff.support, diff.d_star)
    w_seed = int(v1lib.world_seed(rec.world_id))
    evidence = v3c.run_stationary_bootstrap(
        diff, theta_hat, world_seed_int=w_seed, feature_id="F03"
    )

    assert rec.world_seed_int == w_seed
    expected_raw_conditional = float(np.mean(diff.d[diff.support == 1.0]))
    assert math.isclose(rec.raw_conditional_effect, expected_raw_conditional)
    assert math.isclose(rec.p_margin_to_alpha, rec.p_one_sided - v3c.V3_ALPHA_ONE_SIDED)

    assert rec.bootstrap_evidence is not None
    assert rec.bootstrap_evidence.b_hat == evidence.b_hat
    assert rec.bootstrap_evidence.se_hat == evidence.se_hat
    assert rec.bootstrap_evidence.t_obs == evidence.t_obs
    assert rec.bootstrap_evidence.p_one_sided == evidence.p_one_sided
    np.testing.assert_array_equal(rec.bootstrap_evidence.theta_star, evidence.theta_star)
    np.testing.assert_array_equal(rec.bootstrap_evidence.t_star, evidence.t_star)
    # And the record's own top-level fields are exactly the evidence's.
    assert rec.b_hat == rec.bootstrap_evidence.b_hat
    assert rec.se_hat == rec.bootstrap_evidence.se_hat
    assert rec.t_obs == rec.bootstrap_evidence.t_obs
    assert rec.p_one_sided == rec.bootstrap_evidence.p_one_sided


def test_f2_diagnostic_persistence_cannot_change_detected():
    rec = v3c.evaluate_v3_world("EASY", 5000, _next_disposable())
    assert rec.world_valid is True
    recomputed = bool(rec.theta_hat > 0 and rec.p_one_sided <= v3c.V3_ALPHA_ONE_SIDED)
    assert rec.detected == recomputed
    src = inspect.getsource(v3c.evaluate_v3_world)
    line = [l for l in src.splitlines() if l.strip().startswith("detected = bool(")][0]
    for forbidden in (
        "world_seed_int", "raw_conditional_effect", "bootstrap_evidence", "p_margin_to_alpha",
    ):
        assert forbidden not in line


# =============================================================================
# 31: exactly three scientific validity guard classes
# =============================================================================


def test_exactly_three_scientific_validity_guard_classes():
    assert v3c.VALIDITY_GUARDS == (
        v3c.VALIDITY_CHRONOLOGY,
        v3c.VALIDITY_SUPPORT,
        v3c.VALIDITY_IDENTIFIABILITY,
    )
    assert len(v3c.VALIDITY_GUARDS) == 3
    with pytest.raises(ValueError):
        v3c.V3WorldInvalid("NONSTATIONARY_TRAP", "must not be a fourth guard")


# =============================================================================
# 32-37: aggregate Wilson / cell boundaries / TRAP uses DETECTED
# =============================================================================


def test_one_sided_wilson_arithmetic():
    lower, upper = v3c.one_sided_wilson_bounds(370, 400)
    assert math.isclose(lower, 0.9003675517007089, rel_tol=1e-9)
    lower2, upper2 = v3c.one_sided_wilson_bounds(350, 400)
    assert math.isclose(upper2, 0.899705108254052, rel_tol=1e-9)


def test_easy_n400_integer_boundary_behavior():
    assert v3c.aggregate_verdict("EASY", 370) == "PASS"
    assert v3c.aggregate_verdict("EASY", 350) == "FAIL"
    assert v3c.aggregate_verdict("EASY", 360) == "INDETERMINATE"


def test_moderate_n400_integer_boundary_behavior():
    assert v3c.aggregate_verdict("MODERATE", 296) == "PASS"
    assert v3c.aggregate_verdict("MODERATE", 264) == "FAIL"
    assert v3c.aggregate_verdict("MODERATE", 280) == "INDETERMINATE"


def test_null_n400_integer_boundary_behavior():
    assert v3c.aggregate_verdict("NULL", 12) == "PASS"
    assert v3c.aggregate_verdict("NULL", 28) == "FAIL"
    assert v3c.aggregate_verdict("NULL", 20) == "INDETERMINATE"


def test_trap_n400_integer_boundary_behavior():
    assert v3c.aggregate_verdict("NONSTATIONARY_TRAP", 66) == "PASS"
    assert v3c.aggregate_verdict("NONSTATIONARY_TRAP", 94) == "FAIL"
    assert v3c.aggregate_verdict("NONSTATIONARY_TRAP", 80) == "INDETERMINATE"


def test_trap_uses_v3_detected_not_v2_strict_pass():
    src = inspect.getsource(v3c)
    assert "STRICT_PASS" not in src
    assert "compose_gates" not in src
    assert "MODEL_DETECTED" not in src
    assert "v3_namespace_seed(" in inspect.getsource(v3c.run_stationary_bootstrap)


def test_v2_strict_pass_cannot_affect_v3_acceptance():
    from scripts.research import harness_synthetic_edge_calibration_v2_rank_policy as v2rp

    assert not hasattr(v3c, "STRICT_PASS")
    assert v2rp.__name__ not in inspect.getsource(v3c)


# =============================================================================
# 39-41: authority authentication
# =============================================================================


def test_amended_prereg_identity_authenticated():
    import hashlib

    md = open("docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PREREG.md", "rb").read()
    js = open("docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PREREG.json", "rb").read()
    assert hashlib.sha256(md).hexdigest() == "ab03c68a3781c13cf5ba74d08d6c212dd9da42b87f7642700cf79294147918e0"
    assert hashlib.sha256(js).hexdigest() == "194fed692018560661879dc67e14a4d139c79978fc0dac00aa6e0f934bd399b5"


def test_current_freeze_authority_authenticated():
    import json

    fz = json.load(open("docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PREREG_FREEZE.json"))
    assert fz["accepted_prereg_content"]["head"] == "543687fe79ba2e6254e879b0574e58a1909c15fe"
    assert fz["explicit_state"]["v3_prereg_frozen"] is True
    assert fz["explicit_state"]["v3_run_authorized"] is False
    assert fz["explicit_state"]["v3_armed"] is False


def test_historical_superseded_freeze_cannot_become_current_authority():
    import subprocess

    raw = subprocess.run(
        ["git", "cat-file", "-p", "4136f530378e91d545e2644a650f0a7a07a731c3:docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PREREG_FREEZE.json"],
        capture_output=True,
    ).stdout
    import json

    historical = json.loads(raw)
    assert historical["accepted_prereg_content"]["head"] == "4b7e0d6dfda1cb9475a610f51ccbec0906fd0133"
    # the CURRENT freeze at HEAD must differ from the historical one
    current = json.load(open("docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PREREG_FREEZE.json"))
    assert current["accepted_prereg_content"]["head"] != historical["accepted_prereg_content"]["head"]
    assert current["supersedes"]["previous_freeze_head"] == "4136f530378e91d545e2644a650f0a7a07a731c3"


# =============================================================================
# 42: disposable test helpers reject the reserved canonical identity range
# =============================================================================


def test_disposable_helper_rejects_reserved_canonical_range():
    with pytest.raises(AssertionError):
        _assert_disposable(10000)
    with pytest.raises(AssertionError):
        _assert_disposable(10399)
    with pytest.raises(AssertionError):
        _assert_disposable(200)  # V1/V2 canonical grid
    _assert_disposable(900123)  # genuinely disposable: must not raise


def test_world_index_range_constants_match_frozen_prereg():
    assert v3c.V3_WORLD_INDEX_START == 10000
    assert v3c.V3_WORLD_INDEX_END == 10399
    assert v3c.is_fresh_v3_world_index(10000)
    assert v3c.is_fresh_v3_world_index(10399)
    assert not v3c.is_fresh_v3_world_index(9999)
    assert not v3c.is_fresh_v3_world_index(10400)


# =============================================================================
# Extra: end-to-end sanity across all four primary scenarios (disposable only)
# =============================================================================


@pytest.mark.parametrize("scenario", ["EASY", "MODERATE", "NULL", "NONSTATIONARY_TRAP"])
def test_end_to_end_disposable_world_produces_well_formed_record(scenario):
    wi = _next_disposable()
    _assert_disposable(wi)
    rec = v3c.evaluate_v3_world(scenario, 5000, wi)
    assert rec.world_valid is True
    assert rec.support_count >= v3c.V3_SUPPORT_COUNT_MIN
    assert isinstance(rec.detected, bool)
    assert 0.0 <= rec.p_one_sided <= 1.0
    assert rec.b_hat > 0
    assert rec.se_hat > 0
    assert set(rec.era_effects) == set(v1lib.SCORED_ERAS)
