"""Tests for analytics/forecasting_v2/bias_1h.py (Stage 4 — Context
Engines, PR 3 of ~3, FINAL planned Stage 4 PR). No DB, no async — pure
classification over hand-constructed `V2TimeframeInputs` fixtures,
following the existing V2 analytics test style
(tests/analytics/test_forecasting_v2_regime_4h.py).

Exercises §4.3's frozen decision tree: price alone decides direction;
cross-exchange agreement is a gate only; `NEUTRAL_NOT_ESTABLISHED` is a
real, successfully-computed result kept strictly distinct from
`"UNAVAILABLE"`; §4.3's unconditional "if bias_evi is UNAVAILABLE ->
bias = UNAVAILABLE" (deliberately NOT the 4h regime's missing-DATA-vs-
tier-only distinction); `consensus_confidence`/`min_coverage_ratio` as
mandatory hard gates; and the corruption-precedence posture (malformed
PRESENT data is never masked by an unrelated unavailable/threshold
short-circuit).

Floating-point note: unlike `regime_4h.py`'s `REGIME_TREND_THRESHOLD =
0.40`/`REGIME_OI_VETO = -0.40`, `BIAS_THRESHOLD = 0.25` needs no ULP
tolerance. Its own exact percentile boundaries are dyadic and land
bit-exact through `normalized_evidence`'s real arithmetic on BOTH signed
branches — verified directly below: `2.0*0.625 - 1.0 == 0.25` and
`-(1.0 - 2.0*0.375) == -0.25`, exactly, no rounding gap. The exact-boundary
tests below assert the REAL `normalized_evidence` primitive's actual
float result before asserting the classification, so this is verified
behaviorally, not merely asserted in prose.

Anti-double-counting (§4.4): `bias_1h.py` must never read
`oi_confirmation`/`oi_change_pct_median`/`oi_direction_agreement` or
`compression_score`/`range_width_pct_median` — OI/compression modulation
belongs to the 4h regime exclusively. Section 9 below is a source-level
regression protecting this.
"""
from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone

import pytest

from analytics.forecasting_v2 import bias_1h as bias_module
from analytics.forecasting_v2.aligned_inputs import V2TimeframeInputs
from analytics.forecasting_v2.context_evidence import V2ContextEvidenceError, normalized_evidence
from analytics.forecasting_v2.bias_1h import (
    BEARISH,
    BIAS_MIN_AGREEMENT,
    BIAS_MIN_COVERAGE,
    BIAS_MIN_CONFIDENCE,
    BIAS_THRESHOLD,
    BIAS_UNAVAILABLE,
    BIASES,
    BULLISH,
    NEUTRAL_NOT_ESTABLISHED,
    V2BiasError,
    V2BiasResult,
    classify_1h_bias,
)

UTC = timezone.utc
B = datetime(2026, 8, 15, 11, 0, tzinfo=UTC)
H16 = "a" * 16


# ============================================================================
# fixtures
# ============================================================================
def make_price_row(**over):
    base = dict(
        scope="consensus", exchange="", symbol="BTCUSDT", market_type="perp",
        metric="price_move_pct_median", timeframe="1h", percentile_window="7d",
        bucket_ts=B, value=1.0, percentile_rank=0.9, sample_size=100,
        sample_window_start=B - timedelta(days=7), sample_window_end=B - timedelta(minutes=5),
        confidence_tier="building", feature_schema_version=1, calculation_version=H16,
    )
    base.update(over)
    return base


_FAMILIES = ("price_structure", "volume", "taker_flow", "oi", "funding", "liquidations")


def make_consensus(**over):
    coverage = over.pop("min_coverage_ratio", 2.0 / 3.0)
    confidence = over.pop("consensus_confidence", 50.0)
    coverage_by_metric = {
        family: {"available": 3, "expected": 3, "ratio": (coverage if family == "price_structure" else 1.0)}
        for family in _FAMILIES
    }
    data_confidence_by_metric = {
        family: (confidence if family == "price_structure" else 100.0) for family in _FAMILIES
    }
    base = dict(
        symbol="BTCUSDT", market_type="perp", timeframe="1h", bucket_ts=B,
        price_move_pct_median=1.0, price_direction_agreement=2.0 / 3.0,
        consensus_confidence=confidence, min_coverage_ratio=coverage,
        coverage_by_metric=coverage_by_metric,
        data_confidence_by_metric=data_confidence_by_metric,
    )
    base.update(over)
    return base


def make_inputs(*, percentiles=(), consensus=None, timeframe="1h", bucket_ts=B):
    return V2TimeframeInputs(
        timeframe=timeframe, bucket_ts=bucket_ts, bucket_end=bucket_ts + timedelta(hours=1),
        consensus=consensus, percentiles=tuple(percentiles), health={},
        reference_feature=None, reference_klines=None, reference_extrema=None,
    )


# ============================================================================
# 1. CORE BIAS MATRIX (§4.3 steps 2-3) — bullish/bearish symmetry
# ============================================================================
def test_bullish_exact_threshold_boundary_is_inclusive():
    # §4.1's own arithmetic at percentile_rank=0.70's sibling boundary for
    # BIAS_THRESHOLD=0.25: p=0.625 is the mathematically-exact bullish
    # bias_evi>=0.25 boundary. Assert the REAL primitive's actual float
    # result first (never a faked evidence value), then classify.
    price_row = make_price_row(value=1.0, percentile_rank=0.625)
    inputs = make_inputs(percentiles=[price_row], consensus=make_consensus())
    actual_evi = normalized_evidence(
        inputs, metric="price_move_pct_median", percentile_window="7d")
    assert actual_evi == 0.25
    assert classify_1h_bias(inputs).bias == BULLISH


def test_bearish_exact_threshold_boundary_is_inclusive():
    price_row = make_price_row(value=-1.0, percentile_rank=0.375)
    inputs = make_inputs(
        percentiles=[price_row], consensus=make_consensus(price_move_pct_median=-1.0))
    actual_evi = normalized_evidence(
        inputs, metric="price_move_pct_median", percentile_window="7d")
    assert actual_evi == -0.25
    assert classify_1h_bias(inputs).bias == BEARISH


@pytest.mark.parametrize("value,rank,expected", [
    (1.0, 0.625, BULLISH),
    (-1.0, 0.375, BEARISH),
])
def test_bias_boundary_is_classified_symmetrically(value, rank, expected):
    price_row = make_price_row(value=value, percentile_rank=rank)
    consensus_over = {"price_move_pct_median": value} if value < 0 else {}
    inputs = make_inputs(
        percentiles=[price_row], consensus=make_consensus(**consensus_over))
    assert classify_1h_bias(inputs).bias == expected


def test_bullish_clears_threshold_with_margin():
    price_row = make_price_row(value=1.0, percentile_rank=0.9)
    inputs = make_inputs(percentiles=[price_row], consensus=make_consensus())
    assert classify_1h_bias(inputs).bias == BULLISH


def test_bearish_clears_threshold_with_margin():
    price_row = make_price_row(value=-1.0, percentile_rank=0.1)
    inputs = make_inputs(
        percentiles=[price_row], consensus=make_consensus(price_move_pct_median=-1.0))
    assert classify_1h_bias(inputs).bias == BEARISH


def test_raw_zero_price_is_neutral_not_unavailable():
    # A genuinely flat raw value -> normalized_evidence == 0.0 (real
    # neutral, §4.1), which cannot satisfy either directional threshold.
    price_row = make_price_row(value=0.0, percentile_rank=0.5)
    inputs = make_inputs(
        percentiles=[price_row], consensus=make_consensus(price_move_pct_median=0.0))
    result = classify_1h_bias(inputs)
    assert result.bias == NEUTRAL_NOT_ESTABLISHED


# ============================================================================
# 2. JUST-BELOW BIAS TESTS — no threshold smearing
# ============================================================================
def test_bullish_genuinely_just_below_threshold_is_neutral():
    price_row = make_price_row(value=1.0, percentile_rank=0.624999)
    inputs = make_inputs(percentiles=[price_row], consensus=make_consensus())
    assert classify_1h_bias(inputs).bias == NEUTRAL_NOT_ESTABLISHED


def test_bearish_genuinely_just_below_threshold_is_neutral():
    price_row = make_price_row(value=-1.0, percentile_rank=0.375001)
    inputs = make_inputs(
        percentiles=[price_row], consensus=make_consensus(price_move_pct_median=-1.0))
    assert classify_1h_bias(inputs).bias == NEUTRAL_NOT_ESTABLISHED


def test_bullish_comfortable_margin_below_threshold_is_neutral():
    price_row = make_price_row(value=1.0, percentile_rank=0.60)
    inputs = make_inputs(percentiles=[price_row], consensus=make_consensus())
    assert classify_1h_bias(inputs).bias == NEUTRAL_NOT_ESTABLISHED


def test_bearish_comfortable_margin_below_threshold_is_neutral():
    price_row = make_price_row(value=-1.0, percentile_rank=0.40)
    inputs = make_inputs(
        percentiles=[price_row], consensus=make_consensus(price_move_pct_median=-1.0))
    assert classify_1h_bias(inputs).bias == NEUTRAL_NOT_ESTABLISHED


# ============================================================================
# 3. MISSINGNESS MATRIX -> BIAS_UNAVAILABLE (§4.3's unconditional rule,
# deliberately NOT regime_4h.py's missing-DATA-vs-tier-only distinction)
# ============================================================================
def test_missing_exact_price_percentile_row_is_unavailable():
    inputs = make_inputs(percentiles=[], consensus=make_consensus())
    assert classify_1h_bias(inputs).bias == BIAS_UNAVAILABLE


def test_price_row_with_none_value_is_unavailable():
    price_row = make_price_row(value=None)
    inputs = make_inputs(percentiles=[price_row], consensus=make_consensus())
    assert classify_1h_bias(inputs).bias == BIAS_UNAVAILABLE


def test_price_row_with_none_rank_is_unavailable():
    price_row = make_price_row(percentile_rank=None)
    inputs = make_inputs(percentiles=[price_row], consensus=make_consensus())
    assert classify_1h_bias(inputs).bias == BIAS_UNAVAILABLE


def test_price_row_with_tier_none_is_unavailable():
    price_row = make_price_row(confidence_tier="none")
    inputs = make_inputs(percentiles=[price_row], consensus=make_consensus())
    assert classify_1h_bias(inputs).bias == BIAS_UNAVAILABLE


def test_price_row_with_tier_low_is_unavailable():
    # Deliberately DIFFERENT from regime_4h.py: a fully-PRESENT, merely
    # low-tier 1h row is UNAVAILABLE here, never NEUTRAL_NOT_ESTABLISHED.
    price_row = make_price_row(confidence_tier="low")
    inputs = make_inputs(percentiles=[price_row], consensus=make_consensus())
    assert classify_1h_bias(inputs).bias == BIAS_UNAVAILABLE


def test_consensus_none_is_unavailable():
    price_row = make_price_row()
    inputs = make_inputs(percentiles=[price_row], consensus=None)
    assert classify_1h_bias(inputs).bias == BIAS_UNAVAILABLE


def test_confidence_none_is_unavailable():
    price_row = make_price_row()
    inputs = make_inputs(
        percentiles=[price_row], consensus=make_consensus(consensus_confidence=None))
    assert classify_1h_bias(inputs).bias == BIAS_UNAVAILABLE


def test_coverage_none_is_unavailable():
    price_row = make_price_row()
    inputs = make_inputs(
        percentiles=[price_row], consensus=make_consensus(min_coverage_ratio=None))
    assert classify_1h_bias(inputs).bias == BIAS_UNAVAILABLE


def test_no_fallback_to_30d_window():
    # A 30d row present instead of the required 7d one is simply absent
    # for the exact (metric, "7d") lookup -- no cross-window fallback.
    price_row = make_price_row(percentile_window="30d")
    inputs = make_inputs(percentiles=[price_row], consensus=make_consensus())
    assert classify_1h_bias(inputs).bias == BIAS_UNAVAILABLE


def test_no_fallback_to_consensus_raw_price_without_percentile():
    # consensus carries a raw price_move_pct_median, but with no matching
    # exact percentile row at all -- bias_evi is still UNAVAILABLE; the
    # consensus raw value is never used as a substitute.
    inputs = make_inputs(percentiles=[], consensus=make_consensus(price_move_pct_median=5.0))
    assert classify_1h_bias(inputs).bias == BIAS_UNAVAILABLE


# ============================================================================
# 4. NEUTRAL MATRIX -> NEUTRAL_NOT_ESTABLISHED (a real, successfully-
# computed result -- never confused with BIAS_UNAVAILABLE)
# ============================================================================
def test_usable_evidence_below_threshold_is_neutral():
    price_row = make_price_row(value=1.0, percentile_rank=0.55)
    inputs = make_inputs(percentiles=[price_row], consensus=make_consensus())
    assert classify_1h_bias(inputs).bias == NEUTRAL_NOT_ESTABLISHED


def test_agreement_none_with_strong_evidence_is_neutral_not_unavailable():
    price_row = make_price_row(value=1.0, percentile_rank=0.9)
    inputs = make_inputs(
        percentiles=[price_row], consensus=make_consensus(price_direction_agreement=None))
    assert classify_1h_bias(inputs).bias == NEUTRAL_NOT_ESTABLISHED


def test_agreement_below_floor_with_strong_bullish_evidence_is_neutral():
    price_row = make_price_row(value=1.0, percentile_rank=0.9)
    inputs = make_inputs(
        percentiles=[price_row],
        consensus=make_consensus(price_direction_agreement=(2.0 / 3.0) - 0.01))
    assert classify_1h_bias(inputs).bias == NEUTRAL_NOT_ESTABLISHED


def test_agreement_below_floor_with_strong_bearish_evidence_is_neutral():
    price_row = make_price_row(value=-1.0, percentile_rank=0.1)
    inputs = make_inputs(
        percentiles=[price_row],
        consensus=make_consensus(
            price_move_pct_median=-1.0, price_direction_agreement=(2.0 / 3.0) - 0.01))
    assert classify_1h_bias(inputs).bias == NEUTRAL_NOT_ESTABLISHED


# ============================================================================
# 5. AGREEMENT BOUNDARY — a gate only, never itself a direction source
# ============================================================================
def test_bullish_agreement_exact_boundary_passes():
    price_row = make_price_row(value=1.0, percentile_rank=0.9)
    inputs = make_inputs(
        percentiles=[price_row],
        consensus=make_consensus(price_direction_agreement=2.0 / 3.0))
    assert classify_1h_bias(inputs).bias == BULLISH


def test_bullish_agreement_just_below_boundary_is_neutral():
    price_row = make_price_row(value=1.0, percentile_rank=0.9)
    inputs = make_inputs(
        percentiles=[price_row],
        consensus=make_consensus(price_direction_agreement=(2.0 / 3.0) - 1e-9))
    assert classify_1h_bias(inputs).bias == NEUTRAL_NOT_ESTABLISHED


def test_bearish_agreement_exact_boundary_passes():
    price_row = make_price_row(value=-1.0, percentile_rank=0.1)
    inputs = make_inputs(
        percentiles=[price_row],
        consensus=make_consensus(
            price_move_pct_median=-1.0, price_direction_agreement=2.0 / 3.0))
    assert classify_1h_bias(inputs).bias == BEARISH


def test_bearish_agreement_just_below_boundary_is_neutral():
    price_row = make_price_row(value=-1.0, percentile_rank=0.1)
    inputs = make_inputs(
        percentiles=[price_row],
        consensus=make_consensus(
            price_move_pct_median=-1.0, price_direction_agreement=(2.0 / 3.0) - 1e-9))
    assert classify_1h_bias(inputs).bias == NEUTRAL_NOT_ESTABLISHED


def test_agreement_equals_one_is_valid():
    price_row = make_price_row(value=1.0, percentile_rank=0.9)
    inputs = make_inputs(
        percentiles=[price_row], consensus=make_consensus(price_direction_agreement=1.0))
    assert classify_1h_bias(inputs).bias == BULLISH


# ============================================================================
# 6. CONFIDENCE / COVERAGE HARD GATES
# ============================================================================
def test_confidence_just_below_floor_is_unavailable():
    price_row = make_price_row(value=1.0, percentile_rank=0.9)
    inputs = make_inputs(
        percentiles=[price_row], consensus=make_consensus(consensus_confidence=49.999))
    assert classify_1h_bias(inputs).bias == BIAS_UNAVAILABLE


def test_confidence_at_floor_passes():
    price_row = make_price_row(value=1.0, percentile_rank=0.9)
    inputs = make_inputs(
        percentiles=[price_row], consensus=make_consensus(consensus_confidence=50.0))
    assert classify_1h_bias(inputs).bias == BULLISH


def test_coverage_just_below_floor_is_unavailable():
    price_row = make_price_row(value=1.0, percentile_rank=0.9)
    inputs = make_inputs(
        percentiles=[price_row],
        consensus=make_consensus(min_coverage_ratio=(2.0 / 3.0) - 1e-9))
    assert classify_1h_bias(inputs).bias == BIAS_UNAVAILABLE


def test_coverage_at_floor_passes():
    price_row = make_price_row(value=1.0, percentile_rank=0.9)
    inputs = make_inputs(
        percentiles=[price_row], consensus=make_consensus(min_coverage_ratio=2.0 / 3.0))
    assert classify_1h_bias(inputs).bias == BULLISH


@pytest.mark.parametrize("family", ["volume", "taker_flow", "oi", "funding", "liquidations"])
def test_gate_only_reads_price_structure_other_families_cannot_force_unavailable(family):
    # §6.3a required matrix: BIAS's quality gate is scoped to
    # price_structure ONLY. Zeroing coverage AND confidence for any other
    # family must have zero effect -- must still classify BULLISH, never
    # BIAS_UNAVAILABLE.
    price_row = make_price_row(value=1.0, percentile_rank=0.9)
    consensus = make_consensus()
    coverage_by_metric = dict(consensus["coverage_by_metric"])
    coverage_by_metric[family] = {"available": 0, "expected": 3, "ratio": 0.0}
    consensus["coverage_by_metric"] = coverage_by_metric
    data_confidence_by_metric = dict(consensus["data_confidence_by_metric"])
    data_confidence_by_metric[family] = 0.0
    consensus["data_confidence_by_metric"] = data_confidence_by_metric
    inputs = make_inputs(percentiles=[price_row], consensus=consensus)
    assert classify_1h_bias(inputs).bias == BULLISH


def test_confidence_and_coverage_dont_help_if_evidence_unavailable():
    # Even with maximally strong confidence/coverage, missing price
    # evidence still forces UNAVAILABLE.
    inputs = make_inputs(
        percentiles=[],
        consensus=make_consensus(consensus_confidence=100.0, min_coverage_ratio=1.0))
    assert classify_1h_bias(inputs).bias == BIAS_UNAVAILABLE


@pytest.mark.parametrize("bad", [-1.0, 100.01, float("nan"), float("inf"), True, "50"])
def test_malformed_confidence_raises(bad):
    price_row = make_price_row(value=1.0, percentile_rank=0.9)
    inputs = make_inputs(
        percentiles=[price_row], consensus=make_consensus(consensus_confidence=bad))
    with pytest.raises(V2BiasError):
        classify_1h_bias(inputs)


@pytest.mark.parametrize("bad", [-0.01, 1.01, float("nan"), float("inf"), True, "1"])
def test_malformed_coverage_raises(bad):
    price_row = make_price_row(value=1.0, percentile_rank=0.9)
    inputs = make_inputs(
        percentiles=[price_row], consensus=make_consensus(min_coverage_ratio=bad))
    with pytest.raises(V2BiasError):
        classify_1h_bias(inputs)


@pytest.mark.parametrize("bad", [-0.01, 1.01, float("nan"), float("inf"), True, "1"])
def test_malformed_agreement_raises(bad):
    price_row = make_price_row(value=1.0, percentile_rank=0.9)
    inputs = make_inputs(
        percentiles=[price_row], consensus=make_consensus(price_direction_agreement=bad))
    with pytest.raises(V2BiasError):
        classify_1h_bias(inputs)


# ============================================================================
# 7. CORRUPTION PRECEDENCE — malformed PRESENT data is never masked by an
# unrelated unavailable/threshold short-circuit
# ============================================================================
def test_low_tier_evidence_with_corrupt_confidence_raises_not_unavailable():
    price_row = make_price_row(confidence_tier="low")  # -> bias_evi None
    inputs = make_inputs(
        percentiles=[price_row], consensus=make_consensus(consensus_confidence=float("nan")))
    with pytest.raises(V2BiasError):
        classify_1h_bias(inputs)


def test_confidence_below_floor_with_corrupt_agreement_raises_not_unavailable():
    price_row = make_price_row(value=1.0, percentile_rank=0.9)
    inputs = make_inputs(
        percentiles=[price_row],
        consensus=make_consensus(
            consensus_confidence=20.0, price_direction_agreement=float("nan")))
    with pytest.raises(V2BiasError):
        classify_1h_bias(inputs)


def test_coverage_below_floor_with_corrupt_agreement_raises_not_unavailable():
    price_row = make_price_row(value=1.0, percentile_rank=0.9)
    inputs = make_inputs(
        percentiles=[price_row],
        consensus=make_consensus(min_coverage_ratio=0.1, price_direction_agreement=1.5))
    with pytest.raises(V2BiasError):
        classify_1h_bias(inputs)


def test_malformed_percentile_row_with_missing_consensus_raises():
    price_row = make_price_row(value=float("nan"))
    inputs = make_inputs(percentiles=[price_row], consensus=None)
    with pytest.raises(V2BiasError):
        classify_1h_bias(inputs)


def test_v2_context_evidence_error_never_swallowed_silently():
    price_row = make_price_row(value=float("nan"))
    inputs = make_inputs(percentiles=[price_row], consensus=make_consensus())
    with pytest.raises(V2BiasError) as excinfo:
        classify_1h_bias(inputs)
    assert isinstance(excinfo.value.__cause__, V2ContextEvidenceError)


# ============================================================================
# 8. INPUT / RESULT HARDENING
# ============================================================================
@pytest.mark.parametrize("bad_tf", ["5m", "15m", "4h", "1H", None])
def test_wrong_timeframe_raises(bad_tf):
    inputs = make_inputs(
        percentiles=[make_price_row()], consensus=make_consensus(), timeframe=bad_tf)
    with pytest.raises(V2BiasError):
        classify_1h_bias(inputs)


def test_consensus_not_mapping_raises():
    inputs = make_inputs(percentiles=[make_price_row()], consensus="not-a-mapping")
    with pytest.raises(V2BiasError):
        classify_1h_bias(inputs)


def test_consensus_wrong_timeframe_raises():
    inputs = make_inputs(
        percentiles=[make_price_row()], consensus=make_consensus(timeframe="4h"))
    with pytest.raises(V2BiasError):
        classify_1h_bias(inputs)


def test_consensus_wrong_bucket_raises():
    inputs = make_inputs(
        percentiles=[make_price_row()],
        consensus=make_consensus(bucket_ts=B + timedelta(hours=1)))
    with pytest.raises(V2BiasError):
        classify_1h_bias(inputs)


def test_inputs_not_v2timeframeinputs_raises():
    with pytest.raises(V2BiasError):
        classify_1h_bias("not-inputs")


_BIAS_EVI_FOR = {
    # NEUTRAL_NOT_ESTABLISHED requires a real, measured bias_evi (tech-lead
    # amendment round 2) -- 0.0 is a genuinely neutral measured value, never
    # a stand-in for missing evidence. BIAS_UNAVAILABLE may legitimately
    # carry None (the computation could not run at all).
    BULLISH: 0.5, BEARISH: -0.5, NEUTRAL_NOT_ESTABLISHED: 0.0, BIAS_UNAVAILABLE: None,
}


def test_result_is_frozen():
    result = V2BiasResult(bucket_ts=B, bias=NEUTRAL_NOT_ESTABLISHED, bias_evi=0.0)
    with pytest.raises(Exception):
        result.bias = BULLISH  # type: ignore[misc]


@pytest.mark.parametrize("bias", list(BIASES))
def test_result_accepts_all_four_valid_bias_states(bias):
    result = V2BiasResult(bucket_ts=B, bias=bias, bias_evi=_BIAS_EVI_FOR[bias])
    assert result.bias == bias


def test_result_rejects_invalid_bias_state():
    with pytest.raises(V2BiasError):
        V2BiasResult(bucket_ts=B, bias="WEAK_BULLISH", bias_evi=None)


# ============================================================================
# 4.5 Tech-lead amendment round 2 -- NEUTRAL_NOT_ESTABLISHED requires a
# measured bias_evi; BIAS_UNAVAILABLE may carry None OR numeric evidence.
# ============================================================================
def test_neutral_not_established_rejects_none_bias_evi():
    with pytest.raises(V2BiasError):
        V2BiasResult(bucket_ts=B, bias=NEUTRAL_NOT_ESTABLISHED, bias_evi=None)


def test_neutral_not_established_accepts_zero_bias_evi():
    result = V2BiasResult(bucket_ts=B, bias=NEUTRAL_NOT_ESTABLISHED, bias_evi=0.0)
    assert result.bias_evi == 0.0


def test_neutral_not_established_accepts_strong_numeric_evidence():
    # Proves NEUTRAL_NOT_ESTABLISHED is NOT assumed to mean below-threshold
    # evidence -- agreement (not carried by this result) could have failed
    # even with bias_evi well beyond BIAS_THRESHOLD.
    result = V2BiasResult(bucket_ts=B, bias=NEUTRAL_NOT_ESTABLISHED, bias_evi=0.8)
    assert result.bias_evi == 0.8


def test_bias_unavailable_accepts_none_bias_evi():
    result = V2BiasResult(bucket_ts=B, bias=BIAS_UNAVAILABLE, bias_evi=None)
    assert result.bias_evi is None


def test_bias_unavailable_accepts_numeric_bias_evi():
    # Preserves the family-quality-failure path: a numeric bias_evi can
    # exist while required price_structure family coverage/confidence
    # fails, producing BIAS_UNAVAILABLE with real evidence attached.
    result = V2BiasResult(bucket_ts=B, bias=BIAS_UNAVAILABLE, bias_evi=0.8)
    assert result.bias_evi == 0.8


def test_missing_bias_evidence_cannot_masquerade_as_measured_neutral():
    # Cross-stage regression: proves there is no path by which direct/
    # replay construction can convert missing bias evidence into the
    # NEUTRAL_NOT_ESTABLISHED label directional_context_gate() accepts.
    from analytics.forecasting_v2.alignment import selected_bucket
    from analytics.forecasting_v2.setup_common import directional_context_gate
    from analytics.forecasting_v2.context_snapshot import V2ContextSnapshot
    from analytics.forecasting_v2.regime_4h import NON_DIRECTIONAL, V2RegimeResult
    from analytics.forecasting_v2.events import LONG

    # A genuinely-measured neutral context is accepted, exactly as before.
    context = V2ContextSnapshot(
        T=B, symbol="BTCUSDT", market_type="perp", calculation_version="a" * 16,
        feature_schema_version=1,
        regime_4h=V2RegimeResult(
            bucket_ts=selected_bucket("4h", B), regime=NON_DIRECTIONAL, is_compressed=False,
            price_evi=None, compression_score=0.5),
        bias_1h=V2BiasResult(
            bucket_ts=selected_bucket("1h", B), bias=NEUTRAL_NOT_ESTABLISHED, bias_evi=0.0),
    )
    assert directional_context_gate(context, LONG).accepted is True

    # A missing-evidence "neutral" cannot even be constructed -- the seam
    # is closed at the Stage-4 result boundary, before it could ever reach
    # directional_context_gate().
    with pytest.raises(V2BiasError):
        V2BiasResult(bucket_ts=B, bias=NEUTRAL_NOT_ESTABLISHED, bias_evi=None)


def test_result_rejects_naive_bucket_ts():
    naive = datetime(2026, 8, 15, 11, 0)
    with pytest.raises(V2BiasError, match="timezone-aware"):
        V2BiasResult(bucket_ts=naive, bias=NEUTRAL_NOT_ESTABLISHED, bias_evi=0.0)


def test_result_rejects_non_utc_bucket_ts():
    non_utc = datetime(2026, 8, 15, 14, 0, tzinfo=timezone(timedelta(hours=3)))
    with pytest.raises(V2BiasError, match="must be UTC"):
        V2BiasResult(bucket_ts=non_utc, bias=NEUTRAL_NOT_ESTABLISHED, bias_evi=0.0)


def test_result_rejects_bucket_ts_with_seconds():
    with pytest.raises(V2BiasError, match="whole minute"):
        V2BiasResult(bucket_ts=B.replace(second=1), bias=NEUTRAL_NOT_ESTABLISHED, bias_evi=0.0)


def test_result_rejects_bucket_ts_with_microseconds():
    with pytest.raises(V2BiasError, match="whole minute"):
        V2BiasResult(
            bucket_ts=B.replace(microsecond=1), bias=NEUTRAL_NOT_ESTABLISHED, bias_evi=0.0)


def test_result_accepts_valid_utc_whole_minute_bucket_ts():
    result = V2BiasResult(bucket_ts=B, bias=BULLISH, bias_evi=0.5)
    assert result.bucket_ts == B


# ============================================================================
# 9. PURITY / ANTI-DOUBLE-COUNTING — module-source checks
# ============================================================================
def _executable_body_source(module) -> str:
    """Source with every docstring stripped (mirrors the same helper in
    tests/analytics/test_forecasting_v2_regime_4h.py /
    test_forecasting_v2_context_evidence.py)."""
    import ast
    tree = ast.parse(inspect.getsource(module))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)):
                node.body = node.body[1:] or [ast.Pass()]
    return ast.unparse(tree)


def test_module_never_reads_oi_or_compression():
    # §4.4 anti-double-counting: OI/compression modulation belongs to the
    # 4h regime exclusively. Checked on the DOCSTRING-STRIPPED executable
    # body so this only fails if bias_1h.py actually USES one of these,
    # not merely explains in prose why it deliberately does not.
    body_src = _executable_body_source(bias_module)
    forbidden = (
        "oi_confirmation", "oi_change_pct_median", "oi_direction_agreement",
        "compression_score", "range_width_pct_median",
    )
    for token in forbidden:
        assert token not in body_src, f"forbidden OI/compression token found: {token!r}"


def test_module_has_no_clock_random_uuid_network_filesystem_access():
    body_src = _executable_body_source(bias_module)
    forbidden = (
        "datetime.now(", "datetime.utcnow(", "time.time(", "time.monotonic(",
        "import random", "import uuid", "import yaml", "os.environ", "os.getenv",
        "requests.", "httpx.", "open(", "asyncpg", "subprocess",
    )
    for token in forbidden:
        assert token not in body_src, f"forbidden token found: {token!r}"


def test_module_imports_nothing_from_storage_runtime_main_notifications():
    import ast
    tree = ast.parse(inspect.getsource(bias_module))
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        for name in names:
            for banned in ("storage", "runtime", "main", "notifications"):
                assert not name.startswith(banned), f"forbidden import: {name}"


def test_no_stage5_or_snapshot_logic_implemented_yet():
    body_src = _executable_body_source(bias_module)
    forbidden = (
        "directional_context_gate", "V2ContextSnapshot",
        "TREND_PULLBACK", "COMPRESSION_BREAKOUT", "CONFIRMED_BREAKOUT",
        "entry_zone", "protection_buffer", "episode", "state_transition",
    )
    for token in forbidden:
        assert token not in body_src, f"forbidden Stage 5 token found: {token!r}"


def test_classify_1h_bias_is_synchronous():
    assert not inspect.iscoroutinefunction(classify_1h_bias)


def test_bias_thresholds_are_exact_frozen_values():
    assert BIAS_MIN_CONFIDENCE == 50.0
    assert BIAS_MIN_COVERAGE == 2.0 / 3.0
    assert BIAS_THRESHOLD == 0.25
    assert BIAS_MIN_AGREEMENT == 2.0 / 3.0


def test_bias_states_are_exact_frozen_strings():
    assert BULLISH == "BULLISH"
    assert BEARISH == "BEARISH"
    assert NEUTRAL_NOT_ESTABLISHED == "NEUTRAL_NOT_ESTABLISHED"
    assert BIAS_UNAVAILABLE == "UNAVAILABLE"
    assert BIASES == (BULLISH, BEARISH, NEUTRAL_NOT_ESTABLISHED, BIAS_UNAVAILABLE)
