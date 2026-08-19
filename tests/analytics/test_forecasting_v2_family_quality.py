"""Tests for analytics/forecasting_v2/family_quality.py (§6.3a per-family
metric-scoped quality gate primitive -- the shared core PR #44's per-
family hardening is built on). Pure, synchronous, no DB/clock/network --
hand-built consensus-row Mappings only.

Exercises: the frozen `FAMILY_MIN_COVERAGE`/`FAMILY_MIN_CONFIDENCE`
thresholds; every family name; `consensus is None` -> legitimate
`(None, None)`, never an error; a genuinely-missing nested map or missing
per-family key -> `V2FamilyQualityError` (corruption, never legitimate
absence); a PRESENT per-family entry whose `ratio`/confidence leaf value
is itself `None` (SQL NULL) -> legitimate per-fact unavailability, never
an error -- the same present-key-but-null-value convention every other
V2 quality gate in this codebase already uses; malformed PRESENT non-
`None` values (wrong type, out of domain, NaN/inf) -> always raise;
`family_quality_ok()`'s exact boundary semantics."""
from __future__ import annotations

import pytest

from analytics.forecasting_v2.family_quality import (
    FAMILIES,
    FAMILY_MIN_CONFIDENCE,
    FAMILY_MIN_COVERAGE,
    V2FamilyQuality,
    V2FamilyQualityError,
    family_quality,
    family_quality_ok,
)


def make_consensus(*, coverage=0.9, confidence=80.0, family="price_structure", **over):
    coverage_by_metric = {
        f: {"available": 3, "expected": 3, "ratio": (coverage if f == family else 1.0)}
        for f in FAMILIES
    }
    data_confidence_by_metric = {
        f: (confidence if f == family else 100.0) for f in FAMILIES
    }
    base = {
        "coverage_by_metric": coverage_by_metric,
        "data_confidence_by_metric": data_confidence_by_metric,
    }
    base.update(over)
    return base


# ============================================================================
# 1. frozen constants
# ============================================================================
def test_frozen_thresholds():
    assert FAMILY_MIN_COVERAGE == 2.0 / 3.0
    assert FAMILY_MIN_CONFIDENCE == 50.0


def test_families_frozen_order_and_membership():
    assert FAMILIES == (
        "price_structure", "volume", "taker_flow", "oi", "funding", "liquidations")


# ============================================================================
# 2. unknown family
# ============================================================================
def test_unknown_family_raises():
    with pytest.raises(V2FamilyQualityError):
        family_quality(make_consensus(), family="not_a_real_family")


def test_unknown_family_raises_even_for_none_consensus():
    with pytest.raises(V2FamilyQualityError):
        family_quality(None, family="not_a_real_family")


# ============================================================================
# 3. whole-row legitimate absence
# ============================================================================
@pytest.mark.parametrize("family", FAMILIES)
def test_consensus_none_is_legitimate_unavailable(family):
    assert family_quality(None, family=family) == V2FamilyQuality(None, None)
    assert family_quality_ok(None, family=family) is False


# ============================================================================
# 4. non-Mapping consensus
# ============================================================================
@pytest.mark.parametrize("bad", ["not-a-mapping", 42, 3.14, ["a", "list"], object()])
def test_consensus_not_a_mapping_raises(bad):
    with pytest.raises(V2FamilyQualityError):
        family_quality(bad, family="price_structure")


# ============================================================================
# 5. exact-boundary/gate semantics
# ============================================================================
def test_exact_min_coverage_and_min_confidence_qualifies():
    consensus = make_consensus(coverage=FAMILY_MIN_COVERAGE, confidence=FAMILY_MIN_CONFIDENCE)
    q = family_quality(consensus, family="price_structure")
    assert q.coverage_ratio == FAMILY_MIN_COVERAGE
    assert q.confidence == FAMILY_MIN_CONFIDENCE
    assert family_quality_ok(consensus, family="price_structure") is True


def test_coverage_just_below_minimum_fails_gate():
    consensus = make_consensus(coverage=FAMILY_MIN_COVERAGE - 1e-9)
    assert family_quality_ok(consensus, family="price_structure") is False


def test_confidence_just_below_minimum_fails_gate():
    consensus = make_consensus(confidence=FAMILY_MIN_CONFIDENCE - 1e-9)
    assert family_quality_ok(consensus, family="price_structure") is False


def test_full_coverage_and_confidence_qualifies():
    consensus = make_consensus(coverage=1.0, confidence=100.0)
    assert family_quality_ok(consensus, family="price_structure") is True


# ============================================================================
# 6. per-family isolation -- reading one family never touches another
# ============================================================================
@pytest.mark.parametrize("family", FAMILIES)
def test_each_family_reads_only_its_own_entry(family):
    other = next(f for f in FAMILIES if f != family)
    coverage_by_metric = {
        f: {"available": 3, "expected": 3, "ratio": 1.0} for f in FAMILIES
    }
    coverage_by_metric[other] = {"available": 0, "expected": 3, "ratio": 0.0}
    data_confidence_by_metric = {f: 100.0 for f in FAMILIES}
    data_confidence_by_metric[other] = 0.0
    consensus = {
        "coverage_by_metric": coverage_by_metric,
        "data_confidence_by_metric": data_confidence_by_metric,
    }
    assert family_quality_ok(consensus, family=family) is True


# ============================================================================
# 7. present-key-but-null-value leaf semantics (legitimate unavailability)
# ============================================================================
def test_present_ratio_null_leaf_is_legitimate_none_not_error():
    consensus = make_consensus()
    coverage_by_metric = dict(consensus["coverage_by_metric"])
    coverage_by_metric["price_structure"] = {"available": 0, "expected": 3, "ratio": None}
    consensus["coverage_by_metric"] = coverage_by_metric
    q = family_quality(consensus, family="price_structure")
    assert q.coverage_ratio is None
    assert q.confidence == 80.0
    assert family_quality_ok(consensus, family="price_structure") is False


def test_present_confidence_null_leaf_is_legitimate_none_not_error():
    consensus = make_consensus()
    data_confidence_by_metric = dict(consensus["data_confidence_by_metric"])
    data_confidence_by_metric["price_structure"] = None
    consensus["data_confidence_by_metric"] = data_confidence_by_metric
    q = family_quality(consensus, family="price_structure")
    assert q.coverage_ratio == 0.9
    assert q.confidence is None
    assert family_quality_ok(consensus, family="price_structure") is False


def test_both_leaves_null_is_legitimate_none_not_error():
    consensus = make_consensus()
    coverage_by_metric = dict(consensus["coverage_by_metric"])
    coverage_by_metric["price_structure"] = {"available": 0, "expected": 3, "ratio": None}
    consensus["coverage_by_metric"] = coverage_by_metric
    data_confidence_by_metric = dict(consensus["data_confidence_by_metric"])
    data_confidence_by_metric["price_structure"] = None
    consensus["data_confidence_by_metric"] = data_confidence_by_metric
    assert family_quality(consensus, family="price_structure") == V2FamilyQuality(None, None)


# ============================================================================
# 8. missing-KEY corruption (never confused with legitimate null-value
# absence above)
# ============================================================================
def test_missing_coverage_by_metric_map_entirely_raises():
    consensus = make_consensus()
    del consensus["coverage_by_metric"]
    with pytest.raises(V2FamilyQualityError):
        family_quality(consensus, family="price_structure")


def test_missing_data_confidence_by_metric_map_entirely_raises():
    consensus = make_consensus()
    del consensus["data_confidence_by_metric"]
    with pytest.raises(V2FamilyQualityError):
        family_quality(consensus, family="price_structure")


def test_missing_family_key_within_coverage_map_raises():
    consensus = make_consensus()
    coverage_by_metric = dict(consensus["coverage_by_metric"])
    del coverage_by_metric["price_structure"]
    consensus["coverage_by_metric"] = coverage_by_metric
    with pytest.raises(V2FamilyQualityError):
        family_quality(consensus, family="price_structure")


def test_missing_family_key_within_confidence_map_raises():
    consensus = make_consensus()
    data_confidence_by_metric = dict(consensus["data_confidence_by_metric"])
    del data_confidence_by_metric["price_structure"]
    consensus["data_confidence_by_metric"] = data_confidence_by_metric
    with pytest.raises(V2FamilyQualityError):
        family_quality(consensus, family="price_structure")


def test_missing_ratio_field_within_present_coverage_entry_raises():
    consensus = make_consensus()
    coverage_by_metric = dict(consensus["coverage_by_metric"])
    coverage_by_metric["price_structure"] = {"available": 3, "expected": 3}  # no "ratio" key
    consensus["coverage_by_metric"] = coverage_by_metric
    with pytest.raises(V2FamilyQualityError):
        family_quality(consensus, family="price_structure")


@pytest.mark.parametrize("bad_map", ["not-a-mapping", 42, ["a", "list"]])
def test_coverage_by_metric_wrong_type_raises(bad_map):
    consensus = make_consensus(coverage_by_metric=bad_map)
    with pytest.raises(V2FamilyQualityError):
        family_quality(consensus, family="price_structure")


@pytest.mark.parametrize("bad_map", ["not-a-mapping", 42, ["a", "list"]])
def test_data_confidence_by_metric_wrong_type_raises(bad_map):
    consensus = make_consensus(data_confidence_by_metric=bad_map)
    with pytest.raises(V2FamilyQualityError):
        family_quality(consensus, family="price_structure")


@pytest.mark.parametrize("bad_entry", ["not-a-mapping", 42, ["a", "list"]])
def test_coverage_entry_wrong_type_raises(bad_entry):
    consensus = make_consensus()
    coverage_by_metric = dict(consensus["coverage_by_metric"])
    coverage_by_metric["price_structure"] = bad_entry
    consensus["coverage_by_metric"] = coverage_by_metric
    with pytest.raises(V2FamilyQualityError):
        family_quality(consensus, family="price_structure")


# ============================================================================
# 9. malformed PRESENT non-None leaf values -- always raise
# ============================================================================
@pytest.mark.parametrize("bad_ratio", [
    float("nan"), float("inf"), float("-inf"), -0.001, 1.001, True, "0.8", None,
])
def test_malformed_present_ratio_raises_except_none(bad_ratio):
    consensus = make_consensus()
    coverage_by_metric = dict(consensus["coverage_by_metric"])
    coverage_by_metric["price_structure"] = {"available": 3, "expected": 3, "ratio": bad_ratio}
    consensus["coverage_by_metric"] = coverage_by_metric
    if bad_ratio is None:
        # None is legitimate unavailability, not malformed -- covered by
        # its own dedicated test above; excluded from the raise assertion.
        q = family_quality(consensus, family="price_structure")
        assert q.coverage_ratio is None
        return
    with pytest.raises(V2FamilyQualityError):
        family_quality(consensus, family="price_structure")


@pytest.mark.parametrize("bad_confidence", [
    float("nan"), float("inf"), float("-inf"), -0.001, 100.001, True, "80",
])
def test_malformed_present_confidence_raises(bad_confidence):
    consensus = make_consensus()
    data_confidence_by_metric = dict(consensus["data_confidence_by_metric"])
    data_confidence_by_metric["price_structure"] = bad_confidence
    consensus["data_confidence_by_metric"] = data_confidence_by_metric
    with pytest.raises(V2FamilyQualityError):
        family_quality(consensus, family="price_structure")


# ============================================================================
# 10. corruption precedence -- a malformed field must raise even alongside
# an unrelated legitimately-null sibling field
# ============================================================================
def test_malformed_confidence_raises_even_with_null_ratio_sibling():
    consensus = make_consensus()
    coverage_by_metric = dict(consensus["coverage_by_metric"])
    coverage_by_metric["price_structure"] = {"available": 0, "expected": 3, "ratio": None}
    consensus["coverage_by_metric"] = coverage_by_metric
    data_confidence_by_metric = dict(consensus["data_confidence_by_metric"])
    data_confidence_by_metric["price_structure"] = 200.0  # malformed
    consensus["data_confidence_by_metric"] = data_confidence_by_metric
    with pytest.raises(V2FamilyQualityError):
        family_quality(consensus, family="price_structure")


# ============================================================================
# 11. never fabricates a sentinel 0.0 for unavailable facts
# ============================================================================
def test_unavailable_never_returns_sentinel_zero():
    q = family_quality(None, family="price_structure")
    assert q.coverage_ratio is None
    assert q.confidence is None
    assert q.coverage_ratio != 0.0
    assert q.confidence != 0.0
