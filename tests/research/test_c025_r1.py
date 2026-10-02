"""C025-R1 design locks. Synthetic panels only; no discovery outcome is opened."""

from __future__ import annotations

import ast
import inspect

import numpy as np
import pytest

from scripts.research import gv0r02_feasibility_compiler as v0
from scripts.research import gv0r02_feasibility_compiler_v1 as v1
from scripts.research.c025_r1 import constants, events, inference, matching, outcomes, verdict
from scripts.research.c025_r1.constants import NON_PRIMARY_VARIANTS, PRIMARY_VARIANT
from scripts.research.c025_r1.data import legal_months
from scripts.research.c025_r1.events import detect_events, trailing_quantile_thresholds
from scripts.research.c025_r1.outcomes import attach_outcomes, contamination_flags


def _panel(n, quote, taker_share, open0=1577836800000):
    open_ms = open0 + np.arange(n, dtype=np.int64) * 60_000
    price = np.full(n, 100.0)
    # Give every bar a small inside return so pre-impact is positive.
    close = price * np.exp(0.001)
    quote = np.asarray(quote, dtype=np.float64)
    taker = quote * np.asarray(taker_share, dtype=np.float64)
    return {
        "open_ms": open_ms,
        "open": price,
        "close": close,
        "quote": quote,
        "taker_quote": taker,
    }


def test_trailing_quantile_matches_numpy_and_ignores_the_future():
    rng = np.random.default_rng(7)
    volume = rng.random(600)
    trail, q = 80, 0.999
    got = trailing_quantile_thresholds(volume, trail, q)
    for i in range(trail, 600, 40):
        expect = float(np.quantile(volume[i - trail:i], q, method="linear"))
        assert got[i] == pytest.approx(expect)
    spiked = volume.copy()
    spiked[-1] = 1e12
    later = trailing_quantile_thresholds(spiked, trail, q)
    assert np.nanmax(np.abs(got[:-1] - later[:-1])) == 0.0


def test_future_burst_does_not_remove_an_admitted_event():
    n = 400
    quote = np.full(n, 1.0)
    # Baseline one-sidedness is neither arm, so a constant burst history does
    # not start the refractory. Only the marked spikes are eligible.
    share = np.full(n, 0.70)
    quote[200] = 100.0
    quote[210] = 100.0
    share[200] = 0.95
    share[210] = 0.95
    found = detect_events(_panel(n, quote, share), trail=50, quantile=0.90, theta=0.70)
    assert found["summary"]["ONE_SIDED_N"] == 1
    assert int(found["events"]["index"][0]) == 200
    flags = contamination_flags(found["burst"], found["events"]["index"], 30)
    assert bool(flags[0]) is True
    ratio = attach_outcomes(
        found["abs_ret"], found["events"]["quote"] * 0 + _panel(n, quote, share)["quote"],
        found["burst"], found["events"]["index"], found["events"]["pre_impact"],
    )
    # Flipping the descriptive flag does not change the target.
    assert np.isfinite(ratio["impact_ratio"][0])
    held = ratio["impact_ratio"].copy()
    ratio["contamination"][0] = False
    assert ratio["impact_ratio"][0] == held[0]


def test_neither_arm_does_not_start_the_refractory():
    n = 400
    quote = np.full(n, 1.0)
    share = np.full(n, 0.70)  # neither arm
    quote[200] = 50.0
    quote[230] = 50.0
    quote[270] = 50.0
    share[200] = 0.95  # one-sided
    share[230] = 0.70  # neither: one_side = 0.40, between 0.30 and 0.70
    share[270] = 0.95  # 70 minutes after the first accepted event
    found = detect_events(_panel(n, quote, share), trail=40, quantile=0.80, theta=0.70)
    assert list(found["events"]["index"]) == [200, 270]


def test_matching_inputs_are_pre_t_only():
    source = inspect.getsource(matching.choose_matching)
    for banned in ("impact_ratio", "post_abs", "post_quote", "contamination"):
        assert banned not in source
    events_source = inspect.getsource(events.detect_events)
    assert "attach_outcomes" not in events_source


def test_legal_months_stop_before_2025():
    months = legal_months()
    assert months[0] == "2020-01" and months[-1] == "2024-12"
    assert all("2025" not in m and "2026" not in m for m in months)


def test_primary_variant_cannot_be_overridden_and_eleven_are_excluded():
    assert len(NON_PRIMARY_VARIANTS) == 11
    assert PRIMARY_VARIANT not in NON_PRIMARY_VARIANTS
    with pytest.raises(RuntimeError):
        constants.assert_locked_primary(theta=0.8)
    with pytest.raises(TypeError):
        events.detect_primary({"open_ms": np.zeros(1)}, theta=0.8)


def test_seeds_and_bar_are_fixed():
    assert constants.PERMUTATION_SEED == 250251
    assert constants.PLACEBO_SEED == 250252
    assert constants.PERMUTATION_DRAWS == 10_000
    assert constants.MIN_MEANINGFUL_EFFECT == 0.30
    assert constants.PRIMARY_W_MINUTES == 30


def test_permutation_is_deterministic_and_within_stratum():
    y = np.array([0.0, 1.0, 0.2, 0.4, 0.1, 0.5])
    arm = np.array([1, 0, 1, 0, 1, 0])
    keys = np.array([1, 1, 2, 2, 3, 3])
    observed = inference.delta_impact(y, arm)
    first = inference.permutation_pvalue(y, arm, keys, observed)
    second = inference.permutation_pvalue(y, arm, keys, observed)
    assert first == second
    assert 0.0 < first["PRIMARY_PERMUTATION_P"] <= 1.0


def test_verdict_conjunction_and_no_variant_search():
    base = {
        "POOLED_DELTA_IMPACT_RAW": 0.1,
        "POOLED_DELTA_IMPACT_STANDARDIZED": 0.40,
        "PRIMARY_PERMUTATION_P": 0.01,
        "PLACEBO_PASS": True,
        "STABILITY_PASS": True,
        "ANALYSIS_ONE_SIDED_N": 800,
        "ANALYSIS_TWO_SIDED_N": 800,
        "PREFLIGHT_EFFECTIVE_N": 400.0,
        "REALIZED_EFFECTIVE_N": 400.0,
        "INVALID_EXECUTION_REASON": None,
    }
    assert verdict.classify(base) == "SUPPORTED_DISCOVERY"
    weaker = dict(base, POOLED_DELTA_IMPACT_STANDARDIZED=0.2)
    assert verdict.classify(weaker) == "NO_SUPPORT_FOR_PREREGISTERED_C025_R1"
    thin = dict(base, REALIZED_EFFECTIVE_N=10.0)
    assert verdict.classify(thin) == "INFORMATIONALLY_WEAK"
    broken = dict(base, INVALID_EXECUTION_REASON="DATA")
    assert verdict.classify(broken) == "INVALID_EXECUTION"
    tree = ast.parse(inspect.getsource(verdict))
    dumped = ast.dump(tree)
    assert "0.8" not in dumped
    assert "0.9995" not in dumped


def test_prospective_floors_match_the_frozen_stress_profile():
    z = v1.z_two_sided(v0.POWER_PROFILE["ALPHA"])
    stress = v0.POWER_PROFILE["BASE_SD"] * v0.POWER_PROFILE["STRESS_SD_MULTIPLIER"]
    effect = 0.30
    target = v0.POWER_PROFILE["TARGET_POWER"]
    arm = constants.PROSPECTIVE_ARM_FLOOR
    n_eff = arm / 2.0
    assert v1._power(effect, stress, n_eff, z) >= target
    assert v1._mde(stress, n_eff, z) <= effect
    assert v1._power(effect, stress, (arm - 1) / 2.0, z) < target
    assert constants.PROSPECTIVE_MIN_N == arm * 2


def test_contamination_is_not_an_input_to_the_ratio():
    abs_ret = np.full(80, 0.01)
    quote = np.full(80, 2.0)
    burst = np.zeros(80, dtype=bool)
    burst[50] = True  # outside (10, 40]
    pre = np.array([0.005])
    first = attach_outcomes(abs_ret, quote, burst, np.array([10]), pre)
    burst2 = burst.copy()
    burst2[20] = True
    second = attach_outcomes(abs_ret, quote, burst2, np.array([10]), pre)
    assert first["impact_ratio"][0] == pytest.approx(second["impact_ratio"][0])
    assert bool(first["contamination"][0]) is False
    assert bool(second["contamination"][0]) is True


def test_outcome_width_is_locked():
    with pytest.raises(RuntimeError):
        outcomes.window_sums(np.ones(10), np.ones(10), np.array([1]), 15)
