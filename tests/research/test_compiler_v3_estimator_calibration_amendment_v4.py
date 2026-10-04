"""Calibration freeze amendment V4: deterministic validation and reference definitions."""

import numpy as np

from scripts.research.compiler_v3_estimator_calibration import amendment_v4 as A4


def test_amendment_v4_verifies():
    out = A4.verify()
    assert out["OK"] is True, out["CHECKS"]


def test_preference_machine_owner_scenarios():
    S = lambda a, b, c: A4.class_decision({"A": a, "B": b, "C": c})
    E, U, N, P = "ELIGIBLE", "UNRESOLVED_STATE", "NOT_ELIGIBLE_DECISIVE", "ERROR_STATE"
    assert S(U, E, E) == ("CALIBRATION_CLASS_INDETERMINATE", None)
    assert S(P, E, E) == ("CALIBRATION_CLASS_EXECUTION_ERROR", None)
    assert S(N, U, E) == ("CALIBRATION_CLASS_INDETERMINATE", None)
    assert S(N, P, E) == ("CALIBRATION_CLASS_EXECUTION_ERROR", None)
    assert S(N, N, E) == ("CALIBRATION_CLASS_PASS", "C")
    assert S(E, P, P) == ("CALIBRATION_CLASS_PASS", "A")


def test_clustered_truth_properties():
    rng = np.random.default_rng(5)
    v = 0.02 + 0.98 / rng.integers(12, 37, size=40)
    assert abs(A4.clustered_truth(v, 0.0) - v.mean()) < 1e-12
    for phi in (0.0, 0.3, 0.6):
        assert abs(A4.clustered_truth(v, phi) - A4.clustered_truth_by_covariance(v, phi)) < 1e-10
    veq = np.full(40, 0.02 + 0.98 / 24)
    assert abs(A4.clustered_truth(veq, 0.6) - veq[0] * A4.ar_factor(40, 0.6)) < 1e-12


def test_rare_event_identity_and_df_rule():
    assert abs(A4.rare_event_truth_by_covariance(61, 0.6, 0.9, True) - A4.rare_event_truth_formula(61, 0.6, 0.9, True)) < 1e-9
    assert A4.nu_b_two_sample(30) == 10 and A4.nu_b_two_sample(60) == 2 * (60 // 5 - 1) and A4.nu_b_single(60) == 60 // 5 - 1
