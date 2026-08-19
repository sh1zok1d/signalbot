"""Tests for analytics/forecasting_v2/regime_4h.py (Stage 4 — Context
Engines, PR 2 of ~3). No DB, no async — pure classification over
hand-constructed `V2TimeframeInputs` fixtures, following the existing V2
analytics test style (tests/analytics/test_forecasting_v2_context_evidence.py).

Exercises §4.2's frozen decision tree: price alone decides direction;
cross-exchange agreement is a gate only; OI is an optional, symmetric
veto only, consulted ONLY once a price+agreement candidate exists;
`consensus_confidence`/`min_coverage_ratio` are mandatory step-1 hard
gates; the missing-DATA-vs-tier-only-unavailable distinction that decides
`INSUFFICIENT_DATA` vs. falling through to `NON_DIRECTIONAL`; the
`is_compressed` flag belonging exclusively to `NON_DIRECTIONAL`; and the
corruption-precedence posture (malformed PRESENT data is never masked by
an unrelated missing-field/threshold short-circuit).

Floating-point note (amended — the bullish boundary IS directly tested,
not merely inferred from the bearish one). `docs/V2_CORRECTNESS_ACCEPTANCE_
CONTRACT.md` §23.1 freezes the mathematical equivalence `price_evi >= 0.40
iff percentile_rank >= 0.70` for the POSITIVE `normalized_evidence` branch
(`max(0.0, 2.0*p-1.0)`). Evaluating that formula at `p=0.70` in Python
double arithmetic produces `0.3999999999999999` — one to a few ULPs below
the literal `0.4` (0.4 is not a dyadic rational, so it has no exact
IEEE-754 double representation, and this specific arithmetic chain does
not round back to it). The NEGATIVE branch (`-max(0.0, 1.0-2.0*p)`)
happens to round-trip to exactly `-0.4` at `p=0.30`, which is precisely
why this class of bug does not reproduce symmetrically and is easy to
miss if only the negative branch is exercised: a naive plain
`abs(price_evi) >= REGIME_TREND_THRESHOLD` comparison REJECTS the
mathematically-exact bullish boundary while ACCEPTING the mathematically-
exact bearish one. `regime_4h.py` fixes this with `_ge_inclusive`/
`_le_inclusive` — a narrow (`_BOUNDARY_ULP_TOLERANCE`-wide) IEEE-754 ULP
comparison derived solely from the threshold literal's own representable
neighbors (see that module's docstring for the full rationale), applied
ONLY to `abs(price_evi) >= REGIME_TREND_THRESHOLD` and `oi_confirmation <=
REGIME_OI_VETO`. The tests below therefore exercise BOTH signs directly,
using the real `normalized_evidence`/`oi_confirmation` primitives (never a
faked evidence value) — the positive branch at `p=0.70`, and the negative
branch at `p=0.30` — to prove the fix restores symmetric inclusive
behavior, plus explicit below-boundary vectors proving the tolerance does
not swallow genuinely non-trending values.
"""
from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone

import pytest

from analytics.forecasting_v2 import regime_4h as regime_module
from analytics.forecasting_v2.aligned_inputs import V2TimeframeInputs
from analytics.forecasting_v2.context_evidence import V2ContextEvidenceError
from analytics.forecasting_v2.regime_4h import (
    BEARISH_TRENDING,
    BULLISH_TRENDING,
    INSUFFICIENT_DATA,
    NON_DIRECTIONAL,
    REGIME_COMPRESSION,
    REGIME_MIN_AGREEMENT,
    REGIME_MIN_COVERAGE,
    REGIME_MIN_CONFIDENCE,
    REGIME_OI_VETO,
    REGIME_TREND_THRESHOLD,
    REGIMES,
    V2RegimeError,
    V2RegimeResult,
    classify_4h_regime,
)

UTC = timezone.utc
B = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
H16 = "a" * 16


# ============================================================================
# fixtures
# ============================================================================
def make_price_row(**over):
    base = dict(
        scope="consensus", exchange="", symbol="BTCUSDT", market_type="perp",
        metric="price_move_pct_median", timeframe="4h", percentile_window="30d",
        bucket_ts=B, value=1.0, percentile_rank=0.9, sample_size=100,
        sample_window_start=B - timedelta(days=30), sample_window_end=B - timedelta(minutes=5),
        confidence_tier="mature", feature_schema_version=1, calculation_version=H16,
    )
    base.update(over)
    return base


def make_comp_row(**over):
    base = make_price_row(metric="range_width_pct_median", value=2.0, percentile_rank=0.5)
    base.update(over)
    return base


def make_oi_row(**over):
    base = make_price_row(metric="oi_change_pct_median", value=0.1, percentile_rank=0.9)
    base.update(over)
    return base


_FAMILIES = ("price_structure", "volume", "taker_flow", "oi", "funding", "liquidations")


def _family_maps(*, price_coverage, price_confidence, oi_coverage=None, oi_confidence=None):
    """§6.3a per-family `coverage_by_metric`/`data_confidence_by_metric`
    maps for all six families -- `price_structure` (STEP 1's own gate) and
    `oi` (the OI-veto gate) driven by the given ratio/confidence (`oi_*`
    defaults to the SAME values as `price_*` unless overridden, so a bare
    `make_consensus(consensus_confidence=X, min_coverage_ratio=Y)` call
    keeps clearing both gates exactly like before this module's per-family
    hardening); the four families `regime_4h.py` never reads
    (volume/taker_flow/funding/liquidations) are always fully healthy --
    proving THEY can never influence any test in this file."""
    if oi_coverage is None:
        oi_coverage = price_coverage
    if oi_confidence is None:
        oi_confidence = price_confidence
    per_family = {
        "price_structure": (price_coverage, price_confidence),
        "oi": (oi_coverage, oi_confidence),
    }
    coverage_by_metric = {}
    data_confidence_by_metric = {}
    for family in _FAMILIES:
        ratio, confidence = per_family.get(family, (1.0, 100.0))
        coverage_by_metric[family] = {"available": 3, "expected": 3, "ratio": ratio}
        data_confidence_by_metric[family] = confidence
    return coverage_by_metric, data_confidence_by_metric


def make_consensus(**over):
    coverage = over.pop("min_coverage_ratio", 2.0 / 3.0)
    confidence = over.pop("consensus_confidence", 50.0)
    oi_coverage = over.pop("oi_coverage_ratio", None)
    oi_confidence = over.pop("oi_confidence", None)
    coverage_by_metric, data_confidence_by_metric = _family_maps(
        price_coverage=coverage, price_confidence=confidence,
        oi_coverage=oi_coverage, oi_confidence=oi_confidence)
    base = dict(
        symbol="BTCUSDT", market_type="perp", timeframe="4h", bucket_ts=B,
        price_move_pct_median=1.0, oi_change_pct_median=0.1,
        oi_direction_agreement=0.75, price_direction_agreement=2.0 / 3.0,
        consensus_confidence=confidence, min_coverage_ratio=coverage,
        coverage_by_metric=coverage_by_metric,
        data_confidence_by_metric=data_confidence_by_metric,
    )
    base.update(over)
    return base


def make_inputs(*, percentiles=(), consensus=None, timeframe="4h", bucket_ts=B):
    return V2TimeframeInputs(
        timeframe=timeframe, bucket_ts=bucket_ts, bucket_end=bucket_ts + timedelta(hours=4),
        consensus=consensus, percentiles=tuple(percentiles), health={},
        reference_feature=None, reference_klines=None, reference_extrema=None,
    )


# A "neutral" compression row: present, mid-rank, mature tier -- satisfies
# step 1's mandatory-compression-data requirement without itself driving
# is_compressed True/False in tests that don't care about it.
NEUTRAL_COMP_ROW = make_comp_row(percentile_rank=0.5)


def _default_gates(**consensus_over):
    """A consensus row that clears every step-1/step-2 gate on its own,
    for tests that only want to vary ONE input."""
    return make_consensus(**consensus_over)


# ============================================================================
# 1. CORE TREND MATRIX (§4.2 step 2) — bullish/bearish symmetry
# ============================================================================
def test_bullish_exact_threshold_boundary_is_inclusive():
    # §23.1's own frozen equivalence: percentile_rank=0.70 IS the
    # mathematically-exact bullish price_evi>=0.40 boundary. The REAL
    # normalized_evidence primitive computes 2.0*0.70-1.0 ==
    # 0.3999999999999999 (a few ULPs below the 0.4 literal) -- a plain
    # `>=` comparison would incorrectly reject this. This is the primary
    # regression this amendment exists to lock in.
    price_row = make_price_row(value=1.0, percentile_rank=0.70)
    inputs = make_inputs(percentiles=[price_row, NEUTRAL_COMP_ROW], consensus=make_consensus())
    result = classify_4h_regime(inputs)
    assert result.regime == BULLISH_TRENDING
    assert result.is_compressed is None


def test_bearish_exact_threshold_boundary_is_inclusive():
    # -0.40 EXACTLY (bit-for-bit) via the negative branch at rank=0.30 --
    # see module docstring's floating-point note.
    price_row = make_price_row(value=-1.0, percentile_rank=0.30)
    inputs = make_inputs(
        percentiles=[price_row, NEUTRAL_COMP_ROW],
        consensus=make_consensus(price_move_pct_median=-1.0))
    result = classify_4h_regime(inputs)
    assert result.regime == BEARISH_TRENDING
    assert result.is_compressed is None


@pytest.mark.parametrize("value,rank,expected", [
    (1.0, 0.70, BULLISH_TRENDING),
    (-1.0, 0.30, BEARISH_TRENDING),
])
def test_trend_boundary_is_classified_symmetrically(value, rank, expected):
    # Behavioral proof (not merely "same source comparison"): the
    # mathematically-symmetric +0.40/-0.40 boundary must classify
    # symmetrically, using the real evidence primitive both times.
    price_row = make_price_row(value=value, percentile_rank=rank)
    consensus_over = {"price_move_pct_median": value} if value < 0 else {}
    inputs = make_inputs(
        percentiles=[price_row, NEUTRAL_COMP_ROW], consensus=make_consensus(**consensus_over))
    assert classify_4h_regime(inputs).regime == expected


def test_bullish_clears_trend_threshold_with_margin():
    price_row = make_price_row(value=1.0, percentile_rank=0.71)  # price_evi ~= 0.42
    inputs = make_inputs(percentiles=[price_row, NEUTRAL_COMP_ROW], consensus=make_consensus())
    result = classify_4h_regime(inputs)
    assert result.regime == BULLISH_TRENDING
    assert result.is_compressed is None


def test_bullish_just_below_threshold_is_non_directional():
    price_row = make_price_row(value=1.0, percentile_rank=0.69)  # price_evi ~= 0.38
    inputs = make_inputs(percentiles=[price_row, NEUTRAL_COMP_ROW], consensus=make_consensus())
    assert classify_4h_regime(inputs).regime == NON_DIRECTIONAL


def test_bullish_genuinely_just_below_threshold_is_non_directional():
    # A percentile rank fractionally below 0.70 -- the tolerance fix must
    # NOT smear the boundary: this is meaningfully (many ULPs) below 0.4
    # in real terms, not floating-point noise at the exact boundary.
    price_row = make_price_row(value=1.0, percentile_rank=0.699999)
    inputs = make_inputs(percentiles=[price_row, NEUTRAL_COMP_ROW], consensus=make_consensus())
    assert classify_4h_regime(inputs).regime == NON_DIRECTIONAL


def test_bearish_just_below_threshold_is_non_directional():
    price_row = make_price_row(value=-1.0, percentile_rank=0.31)  # price_evi ~= -0.38
    inputs = make_inputs(
        percentiles=[price_row, NEUTRAL_COMP_ROW],
        consensus=make_consensus(price_move_pct_median=-1.0))
    assert classify_4h_regime(inputs).regime == NON_DIRECTIONAL


def test_direction_is_decided_by_price_sign_alone_not_agreement_or_oi():
    # agreement=1.0 (max) and strong confirming OI must not themselves
    # create direction for a below-threshold price.
    price_row = make_price_row(value=1.0, percentile_rank=0.69)
    oi_row = make_oi_row(value=0.5, percentile_rank=0.99)
    inputs = make_inputs(
        percentiles=[price_row, NEUTRAL_COMP_ROW, oi_row],
        consensus=make_consensus(
            price_direction_agreement=1.0, oi_change_pct_median=0.5, oi_direction_agreement=1.0))
    assert classify_4h_regime(inputs).regime == NON_DIRECTIONAL


# ============================================================================
# 2. OI VETO MATRIX (§4.2 step 2's OI modulation)
# ============================================================================
def test_oi_veto_exact_boundary_vetoes_bullish_candidate():
    # oi_confirmation == -0.40 EXACTLY (oi_raw=-0.1, rank=0.30, agreement=1.0)
    price_row = make_price_row(value=1.0, percentile_rank=0.71)
    oi_row = make_oi_row(value=-0.1, percentile_rank=0.30)
    inputs = make_inputs(
        percentiles=[price_row, NEUTRAL_COMP_ROW, oi_row],
        consensus=make_consensus(oi_change_pct_median=-0.1, oi_direction_agreement=1.0))
    result = classify_4h_regime(inputs)
    assert result.regime == NON_DIRECTIONAL


def test_oi_just_above_veto_threshold_does_not_veto():
    price_row = make_price_row(value=1.0, percentile_rank=0.71)
    oi_row = make_oi_row(value=-0.1, percentile_rank=0.35)  # oi_confirmation ~= -0.30
    inputs = make_inputs(
        percentiles=[price_row, NEUTRAL_COMP_ROW, oi_row],
        consensus=make_consensus(oi_change_pct_median=-0.1, oi_direction_agreement=1.0))
    assert classify_4h_regime(inputs).regime == BULLISH_TRENDING


def test_oi_veto_symmetric_for_bearish_candidate():
    price_row = make_price_row(value=-1.0, percentile_rank=0.30)  # price_evi == -0.40
    oi_row = make_oi_row(value=-0.1, percentile_rank=0.30)  # oi_confirmation == -0.40
    inputs = make_inputs(
        percentiles=[price_row, NEUTRAL_COMP_ROW, oi_row],
        consensus=make_consensus(
            price_move_pct_median=-1.0, oi_change_pct_median=-0.1, oi_direction_agreement=1.0))
    assert classify_4h_regime(inputs).regime == NON_DIRECTIONAL


def test_oi_veto_boundary_vector_2_vetoes_bullish_candidate():
    # A DIFFERENT arithmetic shape reaching the same mathematically exact
    # -0.40 veto boundary: oi_rank=0.20, agreement=2/3 ->
    # strength=1-2*0.20=0.60, oi_confirmation=0.60*(2/3)==-0.40 exactly in
    # real terms. The float product (max(0.0, 1.0-2.0*0.20) * (2.0/3.0))
    # lands one ULP ABOVE -0.40, which a plain `<=` comparison would
    # incorrectly treat as a non-veto.
    price_row = make_price_row(value=1.0, percentile_rank=0.71)
    oi_row = make_oi_row(value=-0.1, percentile_rank=0.20)
    inputs = make_inputs(
        percentiles=[price_row, NEUTRAL_COMP_ROW, oi_row],
        consensus=make_consensus(oi_change_pct_median=-0.1, oi_direction_agreement=2.0 / 3.0))
    assert classify_4h_regime(inputs).regime == NON_DIRECTIONAL


def test_oi_veto_boundary_vector_2_vetoes_bearish_candidate():
    price_row = make_price_row(value=-1.0, percentile_rank=0.30)
    oi_row = make_oi_row(value=-0.1, percentile_rank=0.20)
    inputs = make_inputs(
        percentiles=[price_row, NEUTRAL_COMP_ROW, oi_row],
        consensus=make_consensus(
            price_move_pct_median=-1.0, oi_change_pct_median=-0.1,
            oi_direction_agreement=2.0 / 3.0))
    assert classify_4h_regime(inputs).regime == NON_DIRECTIONAL


def test_oi_slightly_weaker_than_boundary_vector_2_does_not_veto():
    # rank=0.21 (vs. the boundary's 0.20) -> strength=1-2*0.21=0.58,
    # oi_confirmation ~= -0.3866..., comfortably (not by ULPs) above
    # -0.40 -- the tolerance must not swallow this.
    price_row = make_price_row(value=1.0, percentile_rank=0.71)
    oi_row = make_oi_row(value=-0.1, percentile_rank=0.21)
    inputs = make_inputs(
        percentiles=[price_row, NEUTRAL_COMP_ROW, oi_row],
        consensus=make_consensus(oi_change_pct_median=-0.1, oi_direction_agreement=2.0 / 3.0))
    assert classify_4h_regime(inputs).regime == BULLISH_TRENDING


def test_strong_positive_oi_never_vetoes_bearish_candidate():
    price_row = make_price_row(value=-1.0, percentile_rank=0.30)
    oi_row = make_oi_row(value=0.5, percentile_rank=0.99)
    inputs = make_inputs(
        percentiles=[price_row, NEUTRAL_COMP_ROW, oi_row],
        consensus=make_consensus(
            price_move_pct_median=-1.0, oi_change_pct_median=0.5, oi_direction_agreement=1.0))
    assert classify_4h_regime(inputs).regime == BEARISH_TRENDING


def test_unavailable_oi_does_not_block_a_valid_bullish_candidate():
    price_row = make_price_row(value=1.0, percentile_rank=0.71)
    # no oi_change_pct_median percentile row at all -> oi_confirmation is None
    inputs = make_inputs(percentiles=[price_row, NEUTRAL_COMP_ROW], consensus=make_consensus())
    result = classify_4h_regime(inputs)
    assert result.regime == BULLISH_TRENDING


def test_unavailable_oi_does_not_block_a_valid_bearish_candidate():
    price_row = make_price_row(value=-1.0, percentile_rank=0.30)
    inputs = make_inputs(
        percentiles=[price_row, NEUTRAL_COMP_ROW],
        consensus=make_consensus(price_move_pct_median=-1.0))
    assert classify_4h_regime(inputs).regime == BEARISH_TRENDING


def test_oi_family_own_poor_quality_never_forces_insufficient_data():
    # §6.3a required matrix: OI unavailable/poor-quality gates OUT the veto
    # itself (no veto applied), it must NEVER force the overall regime to
    # INSUFFICIENT_DATA -- that outcome is reserved for price_structure's
    # own gate alone. A strong confirming OI percentile row is present, but
    # the OI FAMILY's own coverage/confidence are both zeroed.
    price_row = make_price_row(value=1.0, percentile_rank=0.71)
    oi_row = make_oi_row(value=0.5, percentile_rank=0.99)
    inputs = make_inputs(
        percentiles=[price_row, NEUTRAL_COMP_ROW, oi_row],
        consensus=make_consensus(oi_coverage_ratio=0.0, oi_confidence=0.0))
    result = classify_4h_regime(inputs)
    assert result.regime == BULLISH_TRENDING


def test_strong_positive_oi_with_weak_price_is_non_directional():
    price_row = make_price_row(value=1.0, percentile_rank=0.69)
    oi_row = make_oi_row(value=0.5, percentile_rank=0.99)
    inputs = make_inputs(
        percentiles=[price_row, NEUTRAL_COMP_ROW, oi_row],
        consensus=make_consensus(oi_change_pct_median=0.5, oi_direction_agreement=1.0))
    assert classify_4h_regime(inputs).regime == NON_DIRECTIONAL


# ============================================================================
# 3. MANDATORY MISSINGNESS — missing DATA forces INSUFFICIENT_DATA
# ============================================================================
def test_missing_price_percentile_row_is_insufficient_data():
    inputs = make_inputs(percentiles=[NEUTRAL_COMP_ROW], consensus=make_consensus())
    assert classify_4h_regime(inputs).regime == INSUFFICIENT_DATA


def test_price_value_none_is_insufficient_data():
    price_row = make_price_row(value=None)
    inputs = make_inputs(percentiles=[price_row, NEUTRAL_COMP_ROW], consensus=make_consensus())
    assert classify_4h_regime(inputs).regime == INSUFFICIENT_DATA


def test_price_rank_none_is_insufficient_data():
    price_row = make_price_row(percentile_rank=None)
    inputs = make_inputs(percentiles=[price_row, NEUTRAL_COMP_ROW], consensus=make_consensus())
    assert classify_4h_regime(inputs).regime == INSUFFICIENT_DATA


def test_missing_price_data_forces_insufficient_even_with_strong_other_signals():
    # strong OI/agreement cannot compensate for missing MANDATORY price data.
    oi_row = make_oi_row(value=0.9, percentile_rank=0.99)
    inputs = make_inputs(
        percentiles=[NEUTRAL_COMP_ROW, oi_row],
        consensus=make_consensus(price_direction_agreement=1.0))
    assert classify_4h_regime(inputs).regime == INSUFFICIENT_DATA


def test_missing_compression_percentile_row_is_insufficient_data():
    price_row = make_price_row(value=1.0, percentile_rank=0.9)  # obvious trend
    inputs = make_inputs(percentiles=[price_row], consensus=make_consensus())
    assert classify_4h_regime(inputs).regime == INSUFFICIENT_DATA


def test_compression_value_none_is_insufficient_data():
    price_row = make_price_row(value=1.0, percentile_rank=0.9)
    comp_row = make_comp_row(value=None)
    inputs = make_inputs(percentiles=[price_row, comp_row], consensus=make_consensus())
    assert classify_4h_regime(inputs).regime == INSUFFICIENT_DATA


def test_compression_rank_none_is_insufficient_data():
    price_row = make_price_row(value=1.0, percentile_rank=0.9)
    comp_row = make_comp_row(percentile_rank=None)
    inputs = make_inputs(percentiles=[price_row, comp_row], consensus=make_consensus())
    assert classify_4h_regime(inputs).regime == INSUFFICIENT_DATA


def test_consensus_none_is_insufficient_data():
    price_row = make_price_row(value=1.0, percentile_rank=0.9)
    inputs = make_inputs(percentiles=[price_row, NEUTRAL_COMP_ROW], consensus=None)
    assert classify_4h_regime(inputs).regime == INSUFFICIENT_DATA


def test_confidence_none_is_insufficient_data():
    price_row = make_price_row(value=1.0, percentile_rank=0.9)
    inputs = make_inputs(
        percentiles=[price_row, NEUTRAL_COMP_ROW],
        consensus=make_consensus(consensus_confidence=None))
    assert classify_4h_regime(inputs).regime == INSUFFICIENT_DATA


def test_coverage_none_is_insufficient_data():
    price_row = make_price_row(value=1.0, percentile_rank=0.9)
    inputs = make_inputs(
        percentiles=[price_row, NEUTRAL_COMP_ROW],
        consensus=make_consensus(min_coverage_ratio=None))
    assert classify_4h_regime(inputs).regime == INSUFFICIENT_DATA


# ============================================================================
# 4. TIER-ONLY UNAVAILABLE — NOT "missing data" (§4.2's "not merely tier")
# ============================================================================
def test_price_tier_only_unavailable_is_non_directional_not_insufficient():
    price_row = make_price_row(value=1.0, percentile_rank=0.9, confidence_tier="low")
    inputs = make_inputs(percentiles=[price_row, NEUTRAL_COMP_ROW], consensus=make_consensus())
    result = classify_4h_regime(inputs)
    assert result.regime == NON_DIRECTIONAL
    assert result.regime != INSUFFICIENT_DATA


def test_price_tier_none_unavailable_is_non_directional_not_insufficient():
    price_row = make_price_row(value=1.0, percentile_rank=0.9, confidence_tier="none")
    inputs = make_inputs(percentiles=[price_row, NEUTRAL_COMP_ROW], consensus=make_consensus())
    assert classify_4h_regime(inputs).regime == NON_DIRECTIONAL


def test_compression_tier_only_unavailable_is_not_insufficient():
    price_row = make_price_row(value=1.0, percentile_rank=0.9, confidence_tier="low")
    comp_row = make_comp_row(confidence_tier="low")
    inputs = make_inputs(percentiles=[price_row, comp_row], consensus=make_consensus())
    result = classify_4h_regime(inputs)
    assert result.regime != INSUFFICIENT_DATA
    assert result.regime == NON_DIRECTIONAL


def test_compression_tier_only_unavailable_yields_is_compressed_false():
    # comp is None (tier-only unavailable, not missing DATA) -> is_compressed
    # must be False, never treated as compressed.
    price_row = make_price_row(value=1.0, percentile_rank=0.69)  # below trend threshold
    comp_row = make_comp_row(value=5.0, percentile_rank=0.01, confidence_tier="low")
    inputs = make_inputs(percentiles=[price_row, comp_row], consensus=make_consensus())
    result = classify_4h_regime(inputs)
    assert result.regime == NON_DIRECTIONAL
    assert result.is_compressed is False


# ============================================================================
# 5. AGREEMENT — a gate only, never mandatory for step 1
# ============================================================================
def test_agreement_none_is_non_directional_not_insufficient():
    price_row = make_price_row(value=-1.0, percentile_rank=0.30)
    inputs = make_inputs(
        percentiles=[price_row, NEUTRAL_COMP_ROW],
        consensus=make_consensus(price_move_pct_median=-1.0, price_direction_agreement=None))
    result = classify_4h_regime(inputs)
    assert result.regime == NON_DIRECTIONAL


def test_agreement_below_threshold_is_non_directional():
    price_row = make_price_row(value=-1.0, percentile_rank=0.30)
    inputs = make_inputs(
        percentiles=[price_row, NEUTRAL_COMP_ROW],
        consensus=make_consensus(
            price_move_pct_median=-1.0, price_direction_agreement=REGIME_MIN_AGREEMENT - 1e-9))
    assert classify_4h_regime(inputs).regime == NON_DIRECTIONAL


def test_agreement_exactly_at_threshold_allows_candidate():
    price_row = make_price_row(value=-1.0, percentile_rank=0.30)
    inputs = make_inputs(
        percentiles=[price_row, NEUTRAL_COMP_ROW],
        consensus=make_consensus(
            price_move_pct_median=-1.0, price_direction_agreement=REGIME_MIN_AGREEMENT))
    assert classify_4h_regime(inputs).regime == BEARISH_TRENDING


@pytest.mark.parametrize("bad_agreement", [-0.01, 1.01, float("nan"), float("inf"), True, "0.8"])
def test_agreement_malformed_raises(bad_agreement):
    price_row = make_price_row(value=1.0, percentile_rank=0.9)
    inputs = make_inputs(
        percentiles=[price_row, NEUTRAL_COMP_ROW],
        consensus=make_consensus(price_direction_agreement=bad_agreement))
    with pytest.raises(V2RegimeError):
        classify_4h_regime(inputs)


# ============================================================================
# 6. CONFIDENCE / COVERAGE — mandatory hard gates
# ============================================================================
def test_confidence_just_below_threshold_is_insufficient():
    price_row = make_price_row(value=-1.0, percentile_rank=0.30)
    inputs = make_inputs(
        percentiles=[price_row, NEUTRAL_COMP_ROW],
        consensus=make_consensus(
            price_move_pct_median=-1.0, consensus_confidence=REGIME_MIN_CONFIDENCE - 0.001))
    assert classify_4h_regime(inputs).regime == INSUFFICIENT_DATA


def test_confidence_exactly_at_threshold_passes():
    price_row = make_price_row(value=-1.0, percentile_rank=0.30)
    inputs = make_inputs(
        percentiles=[price_row, NEUTRAL_COMP_ROW],
        consensus=make_consensus(
            price_move_pct_median=-1.0, consensus_confidence=REGIME_MIN_CONFIDENCE))
    assert classify_4h_regime(inputs).regime == BEARISH_TRENDING


def test_confidence_full_100_is_valid():
    price_row = make_price_row(value=-1.0, percentile_rank=0.30)
    inputs = make_inputs(
        percentiles=[price_row, NEUTRAL_COMP_ROW],
        consensus=make_consensus(price_move_pct_median=-1.0, consensus_confidence=100.0))
    assert classify_4h_regime(inputs).regime == BEARISH_TRENDING


@pytest.mark.parametrize("bad_confidence", [-1.0, 101.0, float("nan"), float("inf"), True, "50"])
def test_confidence_malformed_raises(bad_confidence):
    price_row = make_price_row(value=1.0, percentile_rank=0.9)
    inputs = make_inputs(
        percentiles=[price_row, NEUTRAL_COMP_ROW],
        consensus=make_consensus(consensus_confidence=bad_confidence))
    with pytest.raises(V2RegimeError):
        classify_4h_regime(inputs)


def test_coverage_just_below_threshold_is_insufficient():
    price_row = make_price_row(value=-1.0, percentile_rank=0.30)
    inputs = make_inputs(
        percentiles=[price_row, NEUTRAL_COMP_ROW],
        consensus=make_consensus(
            price_move_pct_median=-1.0, min_coverage_ratio=REGIME_MIN_COVERAGE - 1e-9))
    assert classify_4h_regime(inputs).regime == INSUFFICIENT_DATA


def test_coverage_exactly_at_threshold_passes():
    price_row = make_price_row(value=-1.0, percentile_rank=0.30)
    inputs = make_inputs(
        percentiles=[price_row, NEUTRAL_COMP_ROW],
        consensus=make_consensus(price_move_pct_median=-1.0, min_coverage_ratio=REGIME_MIN_COVERAGE))
    assert classify_4h_regime(inputs).regime == BEARISH_TRENDING


def test_coverage_full_1_is_valid():
    price_row = make_price_row(value=-1.0, percentile_rank=0.30)
    inputs = make_inputs(
        percentiles=[price_row, NEUTRAL_COMP_ROW],
        consensus=make_consensus(price_move_pct_median=-1.0, min_coverage_ratio=1.0))
    assert classify_4h_regime(inputs).regime == BEARISH_TRENDING


@pytest.mark.parametrize("bad_coverage", [-0.1, 1.1, float("nan"), float("inf"), True, "0.7"])
def test_coverage_malformed_raises(bad_coverage):
    price_row = make_price_row(value=1.0, percentile_rank=0.9)
    inputs = make_inputs(
        percentiles=[price_row, NEUTRAL_COMP_ROW],
        consensus=make_consensus(min_coverage_ratio=bad_coverage))
    with pytest.raises(V2RegimeError):
        classify_4h_regime(inputs)


@pytest.mark.parametrize("family", ["volume", "taker_flow", "funding", "liquidations"])
def test_step1_gate_only_reads_price_structure_other_families_cannot_force_insufficient(family):
    # §6.3a required matrix: STEP 1's quality gate (direction + compression)
    # is scoped to price_structure ONLY. Zeroing coverage AND confidence
    # for any of the four families this module never reads must have zero
    # effect -- must still classify normally, never INSUFFICIENT_DATA.
    price_row = make_price_row(value=-1.0, percentile_rank=0.30)
    consensus = make_consensus(price_move_pct_median=-1.0)
    coverage_by_metric = dict(consensus["coverage_by_metric"])
    coverage_by_metric[family] = {"available": 0, "expected": 3, "ratio": 0.0}
    consensus["coverage_by_metric"] = coverage_by_metric
    data_confidence_by_metric = dict(consensus["data_confidence_by_metric"])
    data_confidence_by_metric[family] = 0.0
    consensus["data_confidence_by_metric"] = data_confidence_by_metric
    inputs = make_inputs(percentiles=[price_row, NEUTRAL_COMP_ROW], consensus=consensus)
    assert classify_4h_regime(inputs).regime == BEARISH_TRENDING


# ============================================================================
# 7. COMPRESSION FLAG — belongs only to NON_DIRECTIONAL
# ============================================================================
def test_compression_exact_threshold_boundary_is_inclusive():
    price_row = make_price_row(value=1.0, percentile_rank=0.69)  # below trend threshold
    comp_row = make_comp_row(value=2.0, percentile_rank=1.0 - REGIME_COMPRESSION)  # comp == 0.75 exactly
    inputs = make_inputs(percentiles=[price_row, comp_row], consensus=make_consensus())
    result = classify_4h_regime(inputs)
    assert result.regime == NON_DIRECTIONAL
    assert result.is_compressed is True


def test_compression_just_below_threshold_is_false():
    price_row = make_price_row(value=1.0, percentile_rank=0.69)
    comp_row = make_comp_row(value=2.0, percentile_rank=0.26)  # comp == 0.74
    inputs = make_inputs(percentiles=[price_row, comp_row], consensus=make_consensus())
    result = classify_4h_regime(inputs)
    assert result.is_compressed is False


def test_compression_flag_present_even_when_candidate_is_vetoed():
    price_row = make_price_row(value=1.0, percentile_rank=0.71)
    comp_row = make_comp_row(value=2.0, percentile_rank=0.25)  # comp == 0.75
    oi_row = make_oi_row(value=-0.1, percentile_rank=0.30)  # vetoes
    inputs = make_inputs(
        percentiles=[price_row, comp_row, oi_row],
        consensus=make_consensus(oi_change_pct_median=-0.1, oi_direction_agreement=1.0))
    result = classify_4h_regime(inputs)
    assert result.regime == NON_DIRECTIONAL
    assert result.is_compressed is True


def test_compression_cannot_create_direction():
    price_row = make_price_row(value=1.0, percentile_rank=0.69)
    comp_row = make_comp_row(value=2.0, percentile_rank=0.0)  # comp == 1.0, max compression
    inputs = make_inputs(percentiles=[price_row, comp_row], consensus=make_consensus())
    result = classify_4h_regime(inputs)
    assert result.regime == NON_DIRECTIONAL
    assert result.is_compressed is True


@pytest.mark.parametrize("value,rank", [(1.0, 0.71), (-1.0, 0.30)])
def test_trending_regimes_have_is_compressed_none(value, rank):
    price_row = make_price_row(value=value, percentile_rank=rank)
    consensus_over = {"price_move_pct_median": value} if value < 0 else {}
    inputs = make_inputs(
        percentiles=[price_row, NEUTRAL_COMP_ROW], consensus=make_consensus(**consensus_over))
    result = classify_4h_regime(inputs)
    assert result.regime in (BULLISH_TRENDING, BEARISH_TRENDING)
    assert result.is_compressed is None


def test_insufficient_data_has_is_compressed_none():
    inputs = make_inputs(percentiles=[], consensus=None)
    result = classify_4h_regime(inputs)
    assert result.regime == INSUFFICIENT_DATA
    assert result.is_compressed is None


# ============================================================================
# 8. INPUT TYPE / TIMEFRAME / CONSENSUS IDENTITY
# ============================================================================
@pytest.mark.parametrize("bad_timeframe", ["5m", "15m", "1h", "", "4H", None, 5])
def test_wrong_timeframe_raises(bad_timeframe):
    inputs = make_inputs(percentiles=[], consensus=None, timeframe=bad_timeframe)
    with pytest.raises(V2RegimeError, match="timeframe"):
        classify_4h_regime(inputs)


def test_non_v2timeframeinputs_argument_raises():
    with pytest.raises(V2RegimeError, match="V2TimeframeInputs"):
        classify_4h_regime({"timeframe": "4h"})  # type: ignore[arg-type]


def test_consensus_not_a_mapping_raises():
    price_row = make_price_row(value=1.0, percentile_rank=0.9)
    inputs = V2TimeframeInputs(
        timeframe="4h", bucket_ts=B, bucket_end=B + timedelta(hours=4),
        consensus="not-a-mapping", percentiles=(price_row, NEUTRAL_COMP_ROW), health={},
        reference_feature=None, reference_klines=None, reference_extrema=None)
    with pytest.raises(V2RegimeError, match="Mapping"):
        classify_4h_regime(inputs)


def test_consensus_wrong_timeframe_raises():
    price_row = make_price_row(value=1.0, percentile_rank=0.9)
    inputs = make_inputs(
        percentiles=[price_row, NEUTRAL_COMP_ROW], consensus=make_consensus(timeframe="1h"))
    with pytest.raises(V2RegimeError, match="timeframe"):
        classify_4h_regime(inputs)


def test_consensus_wrong_bucket_ts_raises():
    price_row = make_price_row(value=1.0, percentile_rank=0.9)
    inputs = make_inputs(
        percentiles=[price_row, NEUTRAL_COMP_ROW],
        consensus=make_consensus(bucket_ts=B - timedelta(hours=4)))
    with pytest.raises(V2RegimeError, match="bucket_ts"):
        classify_4h_regime(inputs)


# ============================================================================
# 9. CORRUPTION PRECEDENCE — malformed PRESENT data beats an unrelated gate
# ============================================================================
def test_confidence_below_threshold_and_malformed_agreement_raises():
    price_row = make_price_row(value=1.0, percentile_rank=0.9)
    inputs = make_inputs(
        percentiles=[price_row, NEUTRAL_COMP_ROW],
        consensus=make_consensus(consensus_confidence=20.0, price_direction_agreement=float("nan")))
    with pytest.raises(V2RegimeError):
        classify_4h_regime(inputs)


def test_coverage_below_threshold_and_malformed_agreement_raises():
    price_row = make_price_row(value=1.0, percentile_rank=0.9)
    inputs = make_inputs(
        percentiles=[price_row, NEUTRAL_COMP_ROW],
        consensus=make_consensus(min_coverage_ratio=0.1, price_direction_agreement=1.5))
    with pytest.raises(V2RegimeError):
        classify_4h_regime(inputs)


def test_low_tier_price_and_malformed_confidence_raises():
    price_row = make_price_row(value=1.0, percentile_rank=0.9, confidence_tier="low")
    inputs = make_inputs(
        percentiles=[price_row, NEUTRAL_COMP_ROW],
        consensus=make_consensus(consensus_confidence=float("nan")))
    with pytest.raises(V2RegimeError):
        classify_4h_regime(inputs)


# ============================================================================
# 10. OI CALL-ORDER REGRESSION — OI only consulted once a candidate exists
# ============================================================================
def test_malformed_oi_not_evaluated_without_a_price_candidate():
    # price below threshold -> no candidate -> malformed OI fields must
    # never even be consulted; result is a plain NON_DIRECTIONAL, not an error.
    price_row = make_price_row(value=1.0, percentile_rank=0.69)
    oi_row = make_oi_row(value=float("nan"), percentile_rank=0.9)
    inputs = make_inputs(
        percentiles=[price_row, NEUTRAL_COMP_ROW, oi_row],
        consensus=make_consensus(oi_change_pct_median=float("nan"), oi_direction_agreement=0.75))
    assert classify_4h_regime(inputs).regime == NON_DIRECTIONAL


def test_malformed_oi_raises_once_a_price_candidate_exists():
    price_row = make_price_row(value=1.0, percentile_rank=0.71)  # clears threshold
    oi_row = make_oi_row(value=float("nan"), percentile_rank=0.9)
    inputs = make_inputs(
        percentiles=[price_row, NEUTRAL_COMP_ROW, oi_row],
        consensus=make_consensus(oi_change_pct_median=float("nan"), oi_direction_agreement=0.75))
    with pytest.raises(V2RegimeError):
        classify_4h_regime(inputs)


# ============================================================================
# 11. RESULT MODEL
# ============================================================================
def test_result_is_frozen():
    result = V2RegimeResult(
        bucket_ts=B, regime=NON_DIRECTIONAL, is_compressed=True,
        price_evi=None, compression_score=0.9)
    with pytest.raises((AttributeError, TypeError)):
        result.regime = BULLISH_TRENDING  # type: ignore[misc]


def test_result_accepts_valid_utc_whole_minute_bucket_ts():
    result = V2RegimeResult(
        bucket_ts=B, regime=NON_DIRECTIONAL, is_compressed=True,
        price_evi=None, compression_score=0.9)
    assert result.bucket_ts == B


def test_result_rejects_naive_bucket_ts():
    naive = datetime(2026, 8, 15, 12, 0)  # no tzinfo
    with pytest.raises(V2RegimeError, match="timezone-aware"):
        V2RegimeResult(
            bucket_ts=naive, regime=NON_DIRECTIONAL, is_compressed=True,
            price_evi=None, compression_score=0.9)


def test_result_rejects_non_utc_bucket_ts():
    non_utc = datetime(2026, 8, 15, 15, 0, tzinfo=timezone(timedelta(hours=3)))
    with pytest.raises(V2RegimeError, match="must be UTC"):
        V2RegimeResult(
            bucket_ts=non_utc, regime=NON_DIRECTIONAL, is_compressed=True,
            price_evi=None, compression_score=0.9)


def test_result_rejects_bucket_ts_with_seconds():
    with pytest.raises(V2RegimeError, match="whole minute"):
        V2RegimeResult(
            bucket_ts=B.replace(second=1), regime=NON_DIRECTIONAL, is_compressed=True,
            price_evi=None, compression_score=0.9)


def test_result_rejects_bucket_ts_with_microseconds():
    with pytest.raises(V2RegimeError, match="whole minute"):
        V2RegimeResult(
            bucket_ts=B.replace(microsecond=1), regime=NON_DIRECTIONAL, is_compressed=True,
            price_evi=None, compression_score=0.9)


@pytest.mark.parametrize("is_compressed", [True, False])
def test_non_directional_accepts_bool_is_compressed(is_compressed):
    comp = 0.9 if is_compressed else 0.5
    result = V2RegimeResult(
        bucket_ts=B, regime=NON_DIRECTIONAL, is_compressed=is_compressed,
        price_evi=None, compression_score=comp)
    assert result.is_compressed is is_compressed


def test_non_directional_rejects_none_is_compressed():
    with pytest.raises(V2RegimeError, match="is_compressed"):
        V2RegimeResult(
            bucket_ts=B, regime=NON_DIRECTIONAL, is_compressed=None,
            price_evi=None, compression_score=None)


@pytest.mark.parametrize("regime", [BULLISH_TRENDING, BEARISH_TRENDING, INSUFFICIENT_DATA])
def test_non_nondirectional_regimes_reject_bool_is_compressed(regime):
    with pytest.raises(V2RegimeError, match="is_compressed"):
        V2RegimeResult(
            bucket_ts=B, regime=regime, is_compressed=True,
            price_evi=None, compression_score=None)


@pytest.mark.parametrize("regime", [BULLISH_TRENDING, BEARISH_TRENDING, INSUFFICIENT_DATA])
def test_non_nondirectional_regimes_accept_none_is_compressed(regime):
    price_evi = {BULLISH_TRENDING: 0.5, BEARISH_TRENDING: -0.5, INSUFFICIENT_DATA: None}[regime]
    result = V2RegimeResult(
        bucket_ts=B, regime=regime, is_compressed=None,
        price_evi=price_evi, compression_score=None)
    assert result.is_compressed is None


def test_bullish_trending_rejects_price_evi_below_trend_threshold():
    # Tech-lead amendment round 1, item 4: classify_4h_regime() requires
    # abs(price_evi) >= REGIME_TREND_THRESHOLD to ever produce a trending
    # label -- a direct result claiming BULLISH_TRENDING with evidence
    # below that threshold is impossible under the owning classifier.
    with pytest.raises(V2RegimeError):
        V2RegimeResult(
            bucket_ts=B, regime=BULLISH_TRENDING, is_compressed=None,
            price_evi=0.01, compression_score=None)


def test_bearish_trending_rejects_price_evi_above_negative_trend_threshold():
    with pytest.raises(V2RegimeError):
        V2RegimeResult(
            bucket_ts=B, regime=BEARISH_TRENDING, is_compressed=None,
            price_evi=-0.01, compression_score=None)


def test_bullish_trending_accepts_exact_representation_sensitive_threshold_vector():
    # The SAME representation-sensitive value classify_4h_regime() itself
    # accepts (§23.1's own frozen equivalence: percentile_rank=0.70 ->
    # price_evi == 2.0*0.70-1.0 == 0.3999999999999999, a few ULPs below the
    # 0.4 literal) -- a direct result with this exact value must also be
    # accepted via the SAME _ge_inclusive() primitive, never rejected by
    # an invented stricter/exact comparison here.
    price_evi = 2.0 * 0.70 - 1.0
    assert price_evi != 0.4  # confirms this genuinely exercises the ULP tolerance
    result = V2RegimeResult(
        bucket_ts=B, regime=BULLISH_TRENDING, is_compressed=None,
        price_evi=price_evi, compression_score=None)
    assert result.price_evi == price_evi


def test_bearish_trending_accepts_exact_representation_sensitive_threshold_vector():
    price_evi = -(2.0 * 0.70 - 1.0)
    assert price_evi != -0.4
    result = V2RegimeResult(
        bucket_ts=B, regime=BEARISH_TRENDING, is_compressed=None,
        price_evi=price_evi, compression_score=None)
    assert result.price_evi == price_evi


def test_bullish_bearish_trending_accept_normal_half_evidence():
    bullish = V2RegimeResult(
        bucket_ts=B, regime=BULLISH_TRENDING, is_compressed=None,
        price_evi=0.5, compression_score=None)
    assert bullish.price_evi == 0.5
    bearish = V2RegimeResult(
        bucket_ts=B, regime=BEARISH_TRENDING, is_compressed=None,
        price_evi=-0.5, compression_score=None)
    assert bearish.price_evi == -0.5


def test_invalid_regime_string_raises():
    with pytest.raises(V2RegimeError, match="regime"):
        V2RegimeResult(
            bucket_ts=B, regime="SIDEWAYS", is_compressed=None,
            price_evi=None, compression_score=None)


def test_regimes_tuple_is_exactly_four():
    assert REGIMES == (BULLISH_TRENDING, BEARISH_TRENDING, NON_DIRECTIONAL, INSUFFICIENT_DATA)


# ============================================================================
# 12. PURITY — module-source checks
# ============================================================================
def _executable_body_source(module) -> str:
    """Source with every docstring stripped (mirrors the same helper in
    tests/analytics/test_forecasting_v2_context_evidence.py)."""
    import ast
    tree = ast.parse(inspect.getsource(module))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)):
                node.body = node.body[1:] or [ast.Pass()]
    return ast.unparse(tree)


def test_module_has_no_clock_random_uuid_network_filesystem_access():
    body_src = _executable_body_source(regime_module)
    forbidden = (
        "datetime.now(", "datetime.utcnow(", "time.time(", "time.monotonic(",
        "import random", "import uuid", "import yaml", "os.environ", "os.getenv",
        "requests.", "httpx.", "open(", "asyncpg", "subprocess",
    )
    for token in forbidden:
        assert token not in body_src, f"forbidden token found: {token!r}"


def test_module_imports_nothing_from_storage_runtime_main_notifications():
    import ast
    tree = ast.parse(inspect.getsource(regime_module))
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        for name in names:
            for banned in ("storage", "runtime", "main", "notifications"):
                assert not name.startswith(banned), f"forbidden import: {name}"


def test_classify_4h_regime_is_synchronous():
    assert not inspect.iscoroutinefunction(classify_4h_regime)


# ============================================================================
# 13. NO FUTURE LOGIC — source-level guarantee this PR does ZERO bias/
# detector/episode/state-machine work.
# ============================================================================
def test_no_bias_detector_or_episode_logic_implemented_yet():
    body_src = _executable_body_source(regime_module)
    forbidden = (
        "BIAS_", "NEUTRAL_NOT_ESTABLISHED", "directional_context_gate",
        "TREND_PULLBACK", "COMPRESSION_BREAKOUT", "CONFIRMED_BREAKOUT",
        "entry_zone", "protection_buffer", "episode", "state_transition",
    )
    for token in forbidden:
        assert token not in body_src, f"forbidden Stage 4 PR3/Stage 5 token found: {token!r}"


def test_v2_context_evidence_error_never_swallowed_silently():
    # A direct regression proving the module never catches
    # V2ContextEvidenceError without re-raising: the OI-malformed-with-
    # candidate test above already proves this behaviorally: verify the
    # cause chain is preserved.
    price_row = make_price_row(value=1.0, percentile_rank=0.71)
    oi_row = make_oi_row(value=float("nan"), percentile_rank=0.9)
    inputs = make_inputs(
        percentiles=[price_row, NEUTRAL_COMP_ROW, oi_row],
        consensus=make_consensus(oi_change_pct_median=float("nan"), oi_direction_agreement=0.75))
    with pytest.raises(V2RegimeError) as exc_info:
        classify_4h_regime(inputs)
    assert isinstance(exc_info.value.__cause__, V2ContextEvidenceError)
