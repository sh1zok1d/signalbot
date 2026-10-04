"""Grid builder of COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_V1: deterministic,
seed ranges disjoint from Official Run 1, MUST truths inside the fallback domain.
No simulation; no calibration outcome is produced or read here."""

import json

from scripts.research.compiler_v3_estimator_calibration import build_calibration_grid as B


def test_grid_deterministic_and_valid():
    g1, g2 = B.build(), B.build()
    assert json.dumps(g1, sort_keys=True) == json.dumps(g2, sort_keys=True)
    assert g1["GRID_VALIDATION"]["GRID_OK"] is True
    assert g1["COUNTS"]["CELLS"] == len(g1["CELLS"]) == 621
    assert all(r["K_IN_DOMAIN"] is True for r in g1["CELLS"] if r["LABEL"] == "MUST" and r["TRUTH"]["VAR_TRUE"] is not None)
    assert min(r["SEED_RANGE"]["CAL"][0] for r in g1["CELLS"]) > 6001068009999


def test_committed_grid_matches_builder():
    committed = json.loads(B.OUT.read_text())
    assert json.dumps(committed, sort_keys=True) == json.dumps(B.build(), sort_keys=True)


def test_ar_factor_limits():
    assert B.ar_factor(100, 0.0) == 1.0
    assert abs(B.ar_factor(100000, 0.6) - (1.6 / 0.4)) < 1e-3
