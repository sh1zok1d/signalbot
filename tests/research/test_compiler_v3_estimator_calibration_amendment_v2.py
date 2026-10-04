"""Calibration freeze amendment V2 (option B): deterministic validation and reference definitions."""

import numpy as np
import pytest

from scripts.research.compiler_v3_estimator_calibration import amendment_v2 as V2
from scripts.research.compiler_v3_estimator_calibration import build_probe_cells as P


def test_amendment_v2_verifies():
    out = V2.verify()
    assert out["OK"] is True, out["CHECKS"]


def test_probes_deterministic_and_match_committed():
    import json
    assert json.dumps(P.build(), sort_keys=True) == json.dumps(json.loads(P.OUT.read_text()), sort_keys=True)


def test_bartlett_matches_literal_formula():
    rng = np.random.default_rng(1)
    x = rng.standard_normal(27)
    n, L = 27, 3
    d = x - x.mean()
    gamma = [sum(d[t] * d[t - l] for t in range(l, n)) / n for l in range(L + 1)]
    omega = gamma[0] + 2 * sum((1 - l / (L + 1)) * gamma[l] for l in range(1, L + 1))
    assert abs(V2.bartlett_omega(x) - omega) < 1e-12
    y = rng.standard_normal(40)
    assert abs(V2.two_sample_long_run_variance(x, y) - (26 * V2.bartlett_omega(x) + 39 * V2.bartlett_omega(y)) / 65) < 1e-12


def test_bartlett_error_rule_not_repaired():
    with pytest.raises(V2.CalibrationExecutionError):
        V2.bartlett_omega(np.ones(30))


def test_domain_rule_no_extrapolation():
    sizes = [8, 15, 25, 40]
    assert not V2.supported(41, sizes, set(sizes), {8: True, 15: True, 25: True})
    assert V2.supported(30, sizes, {25}, {25: True})
    assert not V2.supported(30, sizes, {25}, {25: False})
