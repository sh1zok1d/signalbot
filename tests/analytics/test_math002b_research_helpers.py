"""Pure unit tests for `scripts/research/math002b_lib.py` -- the MATH-002B
historical-study computation helpers.

These tests exercise HARNESS CODE ONLY with tiny synthetic fixtures. They
are NOT historical evidence and must never be cited as such -- see
`docs/V2_CONSENSUS_ROBUSTNESS_HISTORICAL_AUDIT.md` for the actual (blocked)
historical study status.
"""
from __future__ import annotations

import pytest

from scripts.research.math002b_lib import (
    BB,
    BO,
    PairComparison,
    family_quality_gate_flip_rate,
    outlier_report_flip_rate,
    sign_flip_rate,
    summarize,
)


def _cmp(**over):
    base = dict(
        bucket_ts=None, timeframe="4h", family="price_structure", pair_name=BB,
        omitted_venue="okx", full3_median=1.0, pair_median=1.0,
        full3_mad=0.0, pair_mad=0.0, full3_agreement=1.0, pair_agreement=1.0,
        full3_confidence=100.0, pair_confidence=100.0,
        full3_has_outlier=False, pair_has_outlier=False,
        full3_family_quality_gate_pass=True, pair_family_quality_gate_pass=True,
    )
    base.update(over)
    return PairComparison(**base)


def test_pair_name_must_be_a_controlled_pair():
    with pytest.raises(ValueError, match="pair_name"):
        _cmp(pair_name="FULL3")


def test_absolute_median_delta():
    c = _cmp(full3_median=1.0, pair_median=50.5)
    assert c.absolute_median_delta == pytest.approx(49.5)


def test_absolute_median_delta_none_when_missing():
    c = _cmp(full3_median=None)
    assert c.absolute_median_delta is None


def test_absolute_median_delta_is_true_magnitude_for_negative_signed_difference():
    """Tech-lead review round 1, finding 1: a negative signed difference
    (pair_median < full3_median) must still report a POSITIVE
    absolute_median_delta -- the prior implementation silently returned the
    signed value under an "absolute" name."""
    c = _cmp(full3_median=100.0, pair_median=1.0)
    signed = c.signed_median_delta
    assert signed == pytest.approx(-99.0)
    assert signed < 0
    assert c.absolute_median_delta == pytest.approx(99.0)
    assert c.absolute_median_delta > 0


def test_signed_median_delta_preserves_direction():
    c = _cmp(full3_median=1.0, pair_median=100.0)
    assert c.signed_median_delta == pytest.approx(99.0)
    c2 = _cmp(full3_median=100.0, pair_median=1.0)
    assert c2.signed_median_delta == pytest.approx(-99.0)
    # Both directions collapse to the same magnitude.
    assert c.absolute_median_delta == c2.absolute_median_delta == pytest.approx(99.0)


def test_signed_median_delta_none_when_missing():
    c = _cmp(pair_median=None)
    assert c.signed_median_delta is None
    assert c.absolute_median_delta is None


def test_relative_median_delta_stable_case():
    c = _cmp(full3_median=10.0, pair_median=15.0)
    assert c.relative_median_delta == pytest.approx(0.5)


def test_relative_median_delta_none_when_full3_near_zero():
    """LOAD-BEARING: near-zero FULL3 must never produce an unstable/huge
    relative percentage -- it must be None, not a fabricated large number."""
    c = _cmp(full3_median=0.0, pair_median=5.0)
    assert c.relative_median_delta is None
    c2 = _cmp(full3_median=1e-12, pair_median=5.0)
    assert c2.relative_median_delta is None


def test_sign_flip_detected():
    c = _cmp(full3_median=1.0, pair_median=-1.0)
    assert c.sign_flipped is True


def test_sign_flip_not_detected_same_sign():
    c = _cmp(full3_median=1.0, pair_median=50.0)
    assert c.sign_flipped is False


def test_sign_flip_zero_is_its_own_sign():
    c = _cmp(full3_median=0.0, pair_median=0.0)
    assert c.sign_flipped is False
    c2 = _cmp(full3_median=0.0, pair_median=1.0)
    assert c2.sign_flipped is True


def test_agreement_and_confidence_deltas():
    c = _cmp(full3_agreement=1.0, pair_agreement=0.5, full3_confidence=100.0, pair_confidence=58.23)
    assert c.agreement_delta == pytest.approx(-0.5)
    assert c.confidence_delta == pytest.approx(-41.77)


def test_outlier_report_flip():
    c = _cmp(full3_has_outlier=True, pair_has_outlier=False)
    assert c.outlier_report_flip is True
    c2 = _cmp(full3_has_outlier=True, pair_has_outlier=True)
    assert c2.outlier_report_flip is False


def test_family_quality_gate_flip():
    c = _cmp(full3_family_quality_gate_pass=True, pair_family_quality_gate_pass=False)
    assert c.family_quality_gate_flip is True
    c2 = _cmp(full3_family_quality_gate_pass=None, pair_family_quality_gate_pass=False)
    assert c2.family_quality_gate_flip is None


def test_summarize_empty():
    s = summarize([])
    assert s.count == 0
    assert s.median is None
    assert s.p99 is None


def test_summarize_small_sample_no_p99():
    s = summarize([1.0, 2.0, 3.0])
    assert s.count == 3
    assert s.median == 2.0
    assert s.max == 3.0
    assert s.p99 is None  # sample too small (< 100) for a meaningful p99


def test_summarize_large_sample_has_p99():
    values = list(range(1, 201))  # 200 points
    s = summarize([float(v) for v in values])
    assert s.count == 200
    assert s.p99 is not None
    assert s.p99 <= 200


def test_summarize_ignores_non_finite():
    s = summarize([1.0, float("nan"), float("inf"), 2.0])
    assert s.count == 2


def test_sign_flip_rate_across_comparisons():
    comparisons = [
        _cmp(full3_median=1.0, pair_median=2.0),   # no flip
        _cmp(full3_median=1.0, pair_median=-2.0),  # flip
        _cmp(full3_median=-1.0, pair_median=-2.0),  # no flip
    ]
    assert sign_flip_rate(comparisons) == pytest.approx(1.0 / 3.0)


def test_sign_flip_rate_none_when_no_data():
    assert sign_flip_rate([]) is None


def test_outlier_report_flip_rate():
    comparisons = [
        _cmp(full3_has_outlier=True, pair_has_outlier=False),
        _cmp(full3_has_outlier=False, pair_has_outlier=False),
    ]
    assert outlier_report_flip_rate(comparisons) == pytest.approx(0.5)


def test_family_quality_gate_flip_rate():
    comparisons = [
        _cmp(full3_family_quality_gate_pass=True, pair_family_quality_gate_pass=False),
        _cmp(full3_family_quality_gate_pass=True, pair_family_quality_gate_pass=True),
        _cmp(pair_name=BO, full3_family_quality_gate_pass=None, pair_family_quality_gate_pass=None),
    ]
    assert family_quality_gate_flip_rate(comparisons) == pytest.approx(0.5)
