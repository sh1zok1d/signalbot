"""Calibration freeze amendment V1: deterministic validation only (no simulation, no outcome)."""

from scripts.research.compiler_v3_estimator_calibration import amendment as A


def test_amendment_verifies():
    out = A.verify()
    assert out["OK"] is True, out["CHECKS"]


def test_coverage_regions_disjoint_and_escalate_between():
    for n in A.STAGE_SIZES:
        seen = {A.coverage_decision(s, n) for s in range(n + 1)}
        assert seen == {"PASS", "FAIL", "ESCALATE"}
        assert not any(A.cp_upper(s, n) <= A.MISS_TARGET and A.cp_lower(s, n) > A.MISS_UNACCEPTABLE for s in range(n + 1))


def test_utility_rule_and_confidence():
    assert abs(float(A.CONF_CANDIDATE) - 299 / 300) < 1e-15
    assert A.utility_decision(4000, 4000) == "PASS"
    assert A.utility_decision(2000, 4000) == "FAIL"
    assert A.utility_decision(3220, 4000) == "ESCALATE"


def test_envelope_and_application():
    env = A.envelope({8: 3.0, 15: 2.0, 25: 2.2, 40: 1.5})
    assert env == {8: 3.0, 15: 2.2, 25: 2.2, 40: 1.5}
    assert A.apply_factor(env, 7) is None
    assert A.apply_factor(env, 20) == 2.2 and A.apply_factor(env, 40) == 1.5 and A.apply_factor(env, 400) == 1.5
