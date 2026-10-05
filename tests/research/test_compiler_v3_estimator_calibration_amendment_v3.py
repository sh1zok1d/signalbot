"""Calibration freeze amendment V3: deterministic validation and reference state machines."""

import json

from scripts.research.compiler_v3_estimator_calibration import amendment_v3 as V3
from scripts.research.compiler_v3_estimator_calibration import build_dense_support_cells as Dn


def test_amendment_v3_verifies():
    out = V3.verify()
    assert out["OK"] is True, out["CHECKS"]


def test_dense_deterministic_and_matches_committed():
    assert json.dumps(Dn.build(), sort_keys=True) == json.dumps(json.loads(Dn.OUT.read_text()), sort_keys=True)


def test_thresholds_at_1199_over_1200():
    t = V3.thresholds()
    assert t["4000"]["COVERAGE_PASS_IF_MISSES_LE"] == 21 and t["4000"]["COVERAGE_FAIL_IF_MISSES_GE"] == 110
    assert t["20000"]["COVERAGE_PASS_IF_MISSES_LE"] == 156 and t["20000"]["COVERAGE_FAIL_IF_MISSES_GE"] == 465
    assert t["4000"]["UTILITY_PASS_IF_SUCCESSES_GE"] == 3280 and t["4000"]["UTILITY_FAIL_IF_SUCCESSES_LE"] == 3119
    assert all(not v["OVERLAP"] for v in t.values())


def test_per_class_selection_is_independent():
    ok_util = {x: {40: ["PASS"]} for x in V3.CANDIDATES}
    a = V3.class_state({x: ["PASS"] for x in V3.CANDIDATES}, ok_util, {}, 260)
    c = V3.class_state({"A": ["FAIL"], "B": ["FAIL"], "C": ["PASS"]}, ok_util, {}, 40)
    assert a["SELECTED_CANDIDATE"] == "A" and c["SELECTED_CANDIDATE"] == "C"
    assert V3.global_status({"TWO_SAMPLE": a["CLASS_STATUS"], "PAIRED_UNITS": a["CLASS_STATUS"],
                             "CLUSTERED": c["CLASS_STATUS"], "RARE_EVENT": a["CLASS_STATUS"]}) == "ESTIMATOR_CALIBRATION_PASS"
