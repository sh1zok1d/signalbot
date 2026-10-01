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
    assign_qrel_buckets,
    classify_inference_sensitivity,
    confirmation_estimator,
    render_markdown,
    rv_qrel_support_from_buckets,
    temporal_gate_passes,
    wilson_upper_accepts,
    ALPHA,
    AMENDMENT_MASTER_SEED,
    BINANCE_DELTA_D7,
    BLOCK_LENGTH,
    DESIGN_YEARS,
    METHOD_BOOT,
    METHOD_NW,
    METHOD_NW_SHORT,
    METHOD_SHIFT,
    MIN_CELL_ARM,
    N_BOOT_OUTER,
    N_OUTER,
    NW_LAG_PRIMARY,
    REVIEWED_CALIBRATION_SEED,
    TEMPORAL_GATE_YEARS,
    TEMPORAL_POSITIVE_YEARS_REQUIRED,
    TYPE_I_CEILING,
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
    assert choose_primary_method({METHOD_NW: failing, METHOD_BOOT: passing()}) is None
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


def test_wilson_upper_bound_is_the_type_i_rule():
    assert TYPE_I_CEILING == 0.06
    assert ALPHA == 0.05
    assert wilson_upper_accepts(250, 5000) is True
    assert wilson_upper_accepts(400, 5000) is False
    # Point estimate equals the ceiling. The upper bound still exceeds it.
    assert wilson_upper_accepts(300, 5000) is False


def test_acceptance_rules_are_not_the_old_iid_bar():
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
    assert TEMPORAL_POSITIVE_YEARS_REQUIRED == 2
    assert TEMPORAL_GATE_YEARS == (2017, 2018, 2019)
    assert DESIGN_YEARS == (2016, 2017, 2018, 2019)
    assert AMENDMENT_MASTER_SEED == 20260930211
    assert REVIEWED_CALIBRATION_SEED == 20260930181
    assert AMENDMENT_MASTER_SEED != REVIEWED_CALIBRATION_SEED
    assert N_OUTER == 5000
    assert N_BOOT_OUTER == 5000
    assert MIN_CELL_ARM == 50
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


def test_temporal_gate_is_two_of_three_full_years_and_ignores_2016():
    assert temporal_gate_passes({2017: True, 2018: True, 2019: False}) is True
    assert temporal_gate_passes({2017: True, 2018: False, 2019: False}) is False
    passed = {2017: True, 2018: True, 2019: False}
    failed = {2017: True, 2018: False, 2019: False}
    assert temporal_gate_passes({**passed, 2016: False}) is True
    assert temporal_gate_passes({**passed, 2016: True}) is True
    assert temporal_gate_passes({**failed, 2016: False}) is False
    assert temporal_gate_passes({**failed, 2016: True}) is False
    assert set(TEMPORAL_GATE_YEARS) == {2017, 2018, 2019}


def test_bootstrap_disagreement_does_not_change_primary_decision():
    agree_pass = classify_inference_sensitivity(True, True)
    disagree_pass = classify_inference_sensitivity(True, False)
    agree_fail = classify_inference_sensitivity(False, False)
    disagree_fail = classify_inference_sensitivity(False, True)
    assert agree_pass["INFERENCE_SENSITIVE"] is False
    assert disagree_pass["INFERENCE_SENSITIVE"] is True
    assert disagree_pass["PRIMARY_INFERENCE_RESULT"] == "PASS"
    assert disagree_pass["PRIMARY_DECISION"] == agree_pass["PRIMARY_DECISION"] == "PASS"
    assert disagree_pass["BLOCK_BOOTSTRAP_SENSITIVITY_RESULT"] == "FAIL"
    assert disagree_fail["INFERENCE_SENSITIVE"] is True
    assert disagree_fail["PRIMARY_INFERENCE_RESULT"] == agree_fail["PRIMARY_INFERENCE_RESULT"] == "FAIL"
    assert disagree_fail["PRIMARY_DECISION"] == "FAIL"


def _support_arrays(pattern: str):
    rows = []
    for rv_id in range(4):
        for qrel_id in range(4):
            controls = 60
            candidates = 60
            if pattern == "fine_gap" and rv_id == 0 and qrel_id == 0:
                controls = 10
            if pattern == "coarse_gap" and rv_id == 1 and qrel_id in (0, 1):
                controls = 0
            rows.extend((rv_id, qrel_id, True) for _ in range(candidates))
            rows.extend((rv_id, qrel_id, False) for _ in range(controls))
    rv = np.array([row[0] for row in rows], dtype=np.int64)
    qrel = np.array([row[1] for row in rows], dtype=np.int64)
    candidate = np.array([row[2] for row in rows], dtype=bool)
    mask = np.ones(rv.size, dtype=bool)
    return rv, qrel, candidate, mask


def test_rv_qrel_support_overlap_coarsening_and_failure():
    rv, qrel, candidate, mask = _support_arrays("ok")
    ok = rv_qrel_support_from_buckets(rv, qrel, candidate, mask)
    assert ok["STATUS"] == "SUPPORTED"
    assert len(ok["FINE_CELLS"]) == 16
    assert all(cell["candidates"] == 60 and cell["controls"] == 60 for cell in ok["FINE_CELLS"])
    rv, qrel, candidate, mask = _support_arrays("fine_gap")
    coarsened = rv_qrel_support_from_buckets(rv, qrel, candidate, mask)
    assert coarsened["STATUS"] == "SUPPORTED_AFTER_COARSENING"
    assert any(cell["arm_support_ok"] is False for cell in coarsened["FINE_CELLS"])
    assert all(cell["arm_support_ok"] is True for cell in coarsened["COARSE_CELLS"])
    rv, qrel, candidate, mask = _support_arrays("coarse_gap")
    blocked = rv_qrel_support_from_buckets(rv, qrel, candidate, mask)
    assert blocked["STATUS"] == "NOT_SUPPORTED"
    assert MIN_CELL_ARM == 50


def test_support_path_does_not_require_a_target():
    import inspect

    params = set(inspect.signature(rv_qrel_support_from_buckets).parameters)
    assert params == {"rv_bucket", "qrel_bucket", "is_candidate", "in_contrast"}
    src = MODULE.read_text(encoding="utf-8")
    start = src.index("def assign_qrel_buckets")
    stop = src.index("def load_real_predictor_design")
    body = src[start:stop]
    assert "state_at_t[i + 1]" not in body
    assert "frame.state[i + 1]" not in body
    buckets = assign_qrel_buckets([1.0] * 5)
    assert buckets.tolist() == [-1, -1, -1, -1, -1]


def test_review_markdown_prints_frozen_calibration_without_reselection():
    payload = json.loads(
        Path("docs/research/D7_BITMEX_DEPENDENCE_INFERENCE_REVIEW_V0.json").read_text(
            encoding="utf-8"
        )
    )
    text = render_markdown(payload)
    assert payload["PRIMARY_INFERENCE_METHOD"] == METHOD_NW
    assert payload["AMENDMENT_MASTER_SEED"] == AMENDMENT_MASTER_SEED
    assert payload["TYPE_I_CEILING"] == 0.06
    assert payload["N_OUTER_HAC"] == 5000
    assert payload["N_OUTER_BOOT"] == 5000
    assert payload["D7_BITMEX_PRIMARY_TARGET_OPENED"] is False
    assert payload["D7_PRIMARY_EFFECT_COMPUTED"] is False
    assert payload["D7_AMENDMENT_OUTCOME_BLIND"] is True
    assert payload["TEMPORAL_GATE_YEARS"] == [2017, 2018, 2019]
    for cell in payload["TYPE_I_RESULTS"][METHOD_NW].values():
        assert cell["n"] == 5000
        assert cell["accepted"] is (cell["wilson_95"][1] <= 0.06)
    for cell in payload["TYPE_I_RESULTS"][METHOD_BOOT].values():
        assert cell["n"] == 5000
        assert cell["accepted"] is (cell["wilson_95"][1] <= 0.06)
    assert "NOT_EQUIVALENT" in text
    assert "Wilson 95% upper bound" in text
    assert payload["RV_QREL_SUPPORT"]["STATUS"] in {
        "SUPPORTED",
        "SUPPORTED_AFTER_COARSENING",
        "NOT_SUPPORTED",
    }
    gate = payload["CONFIRMATION_STATISTICAL_GATE"]
    assert confirmation_estimator() == METHOD_NW
    assert METHOD_NW in gate
    assert "not selectable at confirmation" in gate
    assert "otherwise" not in gate
    with pytest.raises(DesignError, match="ALTERNATE_PRIMARY_NOT_SELECTABLE"):
        confirmation_estimator(METHOD_BOOT)
    with pytest.raises(DesignError, match="ALTERNATE_PRIMARY_NOT_SELECTABLE"):
        confirmation_estimator(METHOD_SHIFT)
