"""Outcome-blind guards for the D7 dependence-inference design. No network."""
from __future__ import annotations

import ast
import json
from pathlib import Path

import numpy as np
import pytest

import math

from scripts.research.d7_bitmex_dependence_inference_review_v0 import (
    DesignError,
    confirmation_estimator,
    render_markdown,
    ALPHA,
    BINANCE_DELTA_D7,
    BLOCK_LENGTH,
    CONFIRMATION_YEARS,
    METHOD_BOOT,
    METHOD_NW,
    METHOD_NW_SHORT,
    METHOD_SHIFT,
    NW_LAG_PRIMARY,
    TEMPORAL_POSITIVE_YEARS_REQUIRED,
    PredictorDesign,
    Segment,
    Stratum,
    bartlett_lrv,
    build_predictor_design,
    choose_primary_method,
    contrast_scale,
    delta_from_means,
    deltas_from_targets,
    draw_targets,
    norm_cdf,
    feasibility_decision,
    joint_power_passes,
    nw_reject,
    stratum_weights,
    sum_autocovariance,
    wilson_lower_accepts,
    _circular_lag_dots,
)
from scripts.research.d7_bitmex_support_and_power_v0 import HOUR_MS

MODULE = Path("scripts/research/d7_bitmex_dependence_inference_review_v0.py")


def test_source_does_not_call_real_scientific_evaluators():
    src = MODULE.read_text(encoding="utf-8")
    tree = ast.parse(src)
    called: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            called.add(func.id)
        elif isinstance(func, ast.Attribute):
            called.add(func.attr)
    forbidden = {
        "construct_d7_scientific_arrays",
        "evaluate_d7_scientific",
        "call_reviewed_d7_evaluator",
    }
    assert forbidden.isdisjoint(called)
    assert "state_at_t[i + 1]" not in src
    assert "frame.state[i + 1]" not in src


def test_exact_contrast_matches_hand_weights():
    # Two strata, common structure: K=2, N=4, K_total=4.
    # Candidate means 1 and 0.5, pool means 0.5 and 0.25.
    delta = delta_from_means([2, 2], [1.0, 0.5], [0.5, 0.25])
    assert delta == pytest.approx(0.375)
    w_c, w_n = stratum_weights(2, 4, 4)
    assert w_c == pytest.approx(0.125)
    assert w_n == pytest.approx(-0.125)
    scale = contrast_scale([2, 2], [4, 4])
    assert scale == pytest.approx(0.5)
    # Pool mean is the mixture, so delta = c * (mean_1 - mean_0).
    assert scale * 0.5 == pytest.approx(
        delta_from_means([2, 2], [0.5, 0.5], [0.25, 0.25])
    )


def test_autocovariance_and_bartlett_are_linear():
    v = np.array([1.0, 2.0, 3.0, 4.0])
    gamma = sum_autocovariance(v, 3)
    assert gamma[0] == pytest.approx(30.0)
    assert gamma[1] == pytest.approx(20.0)
    assert gamma[2] == pytest.approx(11.0)
    assert gamma[3] == pytest.approx(4.0)
    lrv = float(bartlett_lrv(gamma, 1))
    # lag 1 kernel weight 1 - 1/2 = 0.5; LRV = gamma0 + 2*0.5*gamma1
    assert lrv == pytest.approx(30.0 + 20.0)
    assert nw_reject(np.array([0.0]), np.array([lrv])).tolist() == [False]


def test_circular_residual_dots_match_roll():
    w = np.array([0.2, -0.1, 0.4, -0.5])
    e = np.array([1.0, 0.0, 1.0, 0.0])
    dots = _circular_lag_dots(w, e)
    for k in range(4):
        assert dots[k] == pytest.approx(float(np.dot(w, np.roll(e, k))))


def test_design_uses_same_index_state_only():
    hour = np.arange(6, dtype=np.int64) * HOUR_MS
    year = np.array([2017, 2017, 2017, 2018, 2018, 2018])
    bucket = np.zeros(6, dtype=np.int64)
    defined = np.array([True, True, True, True, True, False])
    state = [True, False, True, False, True, True]
    design = build_predictor_design(hour, year, bucket, state, defined)
    # Last hour is not eligible because its next hour does not exist.
    assert design.candidate[-1] is False or bool(design.candidate[-1]) is False
    flipped = list(state)
    flipped[-1] = not flipped[-1]
    flipped_design = build_predictor_design(hour, year, bucket, flipped, defined)
    assert flipped_design.candidate[:-1].tolist() == design.candidate[:-1].tolist()
    assert flipped_design.k_total == design.k_total


def test_synthetic_draw_is_deterministic_and_ignores_real_target_channel():
    hour = np.arange(48, dtype=np.int64) * HOUR_MS
    year = np.full(48, 2017)
    bucket = np.array([i % 2 for i in range(48)], dtype=np.int64)
    defined = np.ones(48, dtype=bool)
    defined[-1] = False
    state = [i % 5 == 0 for i in range(48)]
    design = build_predictor_design(hour, year, bucket, state, defined)
    from scripts.research.d7_bitmex_dependence_inference_review_v0 import _rng

    a = draw_targets(design, "NULL_1_MARKOV_MODERATE", 1.0, _rng("unit"), 4)
    b = draw_targets(design, "NULL_1_MARKOV_MODERATE", 1.0, _rng("unit"), 4)
    assert a.shape == (4, 48)
    assert np.array_equal(a, b)
    assert set(np.unique(a)).issubset({0.0, 1.0})
    z = np.array([-1.6448536269514722, 0.0, 1.6448536269514722])
    got = norm_cdf(z)
    ref = 0.5 * (1.0 + np.vectorize(math.erf)(z / math.sqrt(2.0)))
    assert got == pytest.approx(ref, abs=1e-6)
    assert got[1] == pytest.approx(0.5)


def test_primary_selector_cannot_choose_shift_or_short_lag():
    def passing():
        return {
            "support_eligible": True,
            "regimes": {
                name: {"accepted": True}
                for name in (
                    "NULL_0_IID",
                    "NULL_1_MARKOV_MODERATE",
                    "NULL_2_MARKOV_STRONG",
                    "NULL_3_LATENT_30D",
                    "NULL_4_YEAR_HETERO",
                )
            },
        }

    failing = passing()
    failing = {
        "support_eligible": True,
        "regimes": {
            name: {"accepted": name != "NULL_3_LATENT_30D"}
            for name in passing()["regimes"]
        },
    }
    assert choose_primary_method({METHOD_NW: failing, METHOD_BOOT: passing()}) == METHOD_BOOT
    assert (
        choose_primary_method(
            {
                METHOD_NW: failing,
                METHOD_BOOT: failing,
                METHOD_SHIFT: passing(),
                METHOD_NW_SHORT: passing(),
            }
        )
        is None
    )
    assert METHOD_SHIFT not in (METHOD_NW, METHOD_BOOT)
    assert choose_primary_method({METHOD_NW: passing(), METHOD_BOOT: passing()}) == METHOD_NW


def test_acceptance_rules_are_not_the_old_iid_bar():
    assert wilson_lower_accepts(250, 5000) is True
    assert wilson_lower_accepts(400, 5000) is False
    view = {
        "NULL_1_MARKOV_MODERATE": {"joint_full": 0.80},
        "NULL_2_MARKOV_STRONG": {"joint_full": 0.50},
        "NULL_3_LATENT_30D": {"joint_full": 0.50},
        "NULL_4_YEAR_HETERO": {"joint_full": 0.50},
    }
    assert joint_power_passes(view) is True
    view["NULL_0_IID"] = {"joint_full": 1.0}
    view["NULL_3_LATENT_30D"] = {"joint_full": 0.49}
    assert joint_power_passes(view) is False
    assert (
        feasibility_decision(primary=METHOD_NW, power_ok=False, any_support_eligible=True)
        == "DEPENDENCE_ROBUST_POWER_INSUFFICIENT"
    )
    assert (
        feasibility_decision(primary=None, power_ok=False, any_support_eligible=True)
        == "NO_VALID_EQUIVALENT_INFERENCE_DESIGN"
    )
    assert TEMPORAL_POSITIVE_YEARS_REQUIRED == 3
    assert CONFIRMATION_YEARS == (2016, 2017, 2018, 2019)
    assert NW_LAG_PRIMARY == 721
    assert BLOCK_LENGTH == 1440
    assert ALPHA == 0.05
    assert BINANCE_DELTA_D7 > 0.05


def test_joint_temporal_gate_uses_year_sign_only():
    # Four hours in one year, all eligible except we force a tiny design by
    # calling deltas_from_targets on a hand-built PredictorDesign.
    cand = np.array([0, 1])
    pool = np.array([0, 1, 2, 3])
    design = PredictorDesign(
        year=np.array([2017, 2017, 2017, 2017, 2018, 2018, 2018, 2018]),
        in_contrast=np.ones(8, dtype=bool),
        candidate=np.array([1, 1, 0, 0, 1, 0, 0, 0], dtype=bool),
        weights=np.zeros(8),
        strata=[
            Stratum(2017, 0, np.array([0, 1]), np.array([0, 1, 2, 3])),
            Stratum(2018, 0, np.array([4]), np.array([4, 5, 6, 7])),
        ],
        segments=[Segment(0, 8, [(0, 8)])],
        gap_breaks=(),
        k_total=3,
        scale_c=0.5,
        k_year={2016: 0, 2017: 2, 2018: 1, 2019: 0},
        effective_blocks=1,
    )
    y = np.array([[1, 1, 0, 0, 0, 0, 0, 0]], dtype=np.float64)
    delta, yearly = deltas_from_targets(y, design)
    assert delta[0] == pytest.approx(
        (2 / 3) * (1.0 - 0.5) + (1 / 3) * (0.0 - 0.0)
    )
    assert yearly[2017][0] > 0.0
    assert yearly[2018][0] == pytest.approx(0.0)
    assert cand.size == 2 and pool.size == 4


def test_review_markdown_prints_frozen_calibration_without_reselection():
    payload = json.loads(
        Path("docs/research/D7_BITMEX_DEPENDENCE_INFERENCE_REVIEW_V0.json").read_text(
            encoding="utf-8"
        )
    )
    text = render_markdown(payload)
    assert payload["PRIMARY_INFERENCE_METHOD"] == METHOD_NW
    assert "EXACT_DELTA_NW_BARTLETT_LAG_721" in text
    # Lag 721 and lag 720 differ on NULL_3. The note must keep that count.
    assert "NULL_3_LATENT_30D: 241/5000 = 0.0482" in text
    assert "NULL_4_YEAR_HETERO: 258/5000 = 0.0516" in text
    assert "NULL_1_MARKOV_MODERATE: full joint 1.0; 75pct joint 0.9994; 50pct joint 0.2138" in text
    assert "NOT_EQUIVALENT" in text
    assert "SENSITIVITY_NOT_SELECTABLE" not in payload["PRIMARY_INFERENCE_METHOD"]
    for token in ("hour_start_ms", "autocorrelation", "run_length", "next_d7", "REPLICATED"):
        assert token not in text
    gate = payload["CONFIRMATION_STATISTICAL_GATE"]
    assert confirmation_estimator() == METHOD_NW
    assert METHOD_NW in gate
    assert "not selectable at confirmation" in gate
    assert "otherwise" not in gate
    with pytest.raises(DesignError, match="ALTERNATE_PRIMARY_NOT_SELECTABLE"):
        confirmation_estimator(METHOD_BOOT)
    with pytest.raises(DesignError, match="ALTERNATE_PRIMARY_NOT_SELECTABLE"):
        confirmation_estimator(METHOD_NW_SHORT)
    with pytest.raises(DesignError, match="ALTERNATE_PRIMARY_NOT_SELECTABLE"):
        confirmation_estimator(METHOD_SHIFT)
