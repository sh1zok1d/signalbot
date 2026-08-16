"""Tests for analytics/forecasting_v2/context_snapshot.py (Stage 4 —
Context Engines, PR 3 of ~3, FINAL planned Stage 4 PR). No DB, no async —
pure combination over hand-built `V2AlignedInputs` fixtures, following
the existing V2 analytics test style
(tests/analytics/test_forecasting_v2_regime_4h.py,
tests/analytics/test_forecasting_v2_bias_1h.py).

Exercises: `build_v2_context_snapshot` consumes exactly ONE
`V2AlignedInputs` and derives both the 4h regime and 1h bias from its OWN
`by_timeframe["4h"]`/`["1h"]` entries (never two independent inputs);
`V2ContextSnapshot.__post_init__`'s load-bearing decision-boundary
anti-mixing defense (`regime_4h.bucket_ts`/`bias_1h.bucket_ts` must match
`selected_bucket("4h"|"1h", T)` exactly); that a legitimately-computed
`INSUFFICIENT_DATA` 4h regime or `"UNAVAILABLE"` 1h bias is a VALID
context result the snapshot still carries, never an error; that
`NEUTRAL_NOT_ESTABLISHED` and `"UNAVAILABLE"` remain distinct once
embedded in the snapshot; that the builder gives a clean
`V2ContextSnapshotError` for a malformed container rather than leaking a
bare `KeyError`/`AttributeError`/`TypeError`; and that classifier errors
are wrapped with their cause preserved.
"""
from __future__ import annotations

import ast
import dataclasses
import inspect
from datetime import datetime, timedelta, timezone
from types import MappingProxyType

import pytest

from analytics.forecasting_v2 import context_snapshot as snapshot_module
from analytics.forecasting_v2.aligned_inputs import V2AlignedInputs, V2TimeframeInputs
from analytics.forecasting_v2.alignment import selected_bucket
from analytics.forecasting_v2.bias_1h import (
    BEARISH,
    BIAS_UNAVAILABLE,
    BULLISH,
    NEUTRAL_NOT_ESTABLISHED,
    V2BiasError,
    V2BiasResult,
    classify_1h_bias,
)
from analytics.forecasting_v2.context_snapshot import (
    V2ContextSnapshot,
    V2ContextSnapshotError,
    build_v2_context_snapshot,
)
from analytics.forecasting_v2.regime_4h import (
    BULLISH_TRENDING,
    INSUFFICIENT_DATA,
    NON_DIRECTIONAL,
    V2RegimeError,
    V2RegimeResult,
    classify_4h_regime,
)

UTC = timezone.utc
H16 = "a" * 16
T = datetime(2026, 8, 15, 12, 10, tzinfo=UTC)
B4H = selected_bucket("4h", T)  # 2026-08-15 08:00 UTC
B1H = selected_bucket("1h", T)  # 2026-08-15 11:00 UTC


# ============================================================================
# fixtures
# ============================================================================
def make_price_row(*, timeframe, bucket_ts, window, value, rank, tier="mature", **over):
    base = dict(
        scope="consensus", exchange="", symbol="BTCUSDT", market_type="perp",
        metric="price_move_pct_median", timeframe=timeframe, percentile_window=window,
        bucket_ts=bucket_ts, value=value, percentile_rank=rank, sample_size=100,
        sample_window_start=bucket_ts - timedelta(days=30),
        sample_window_end=bucket_ts - timedelta(minutes=5),
        confidence_tier=tier, feature_schema_version=1, calculation_version=H16,
    )
    base.update(over)
    return base


def make_comp_row(*, timeframe, bucket_ts, window, rank=0.5, **over):
    base = dict(
        scope="consensus", exchange="", symbol="BTCUSDT", market_type="perp",
        metric="range_width_pct_median", timeframe=timeframe, percentile_window=window,
        bucket_ts=bucket_ts, value=2.0, percentile_rank=rank, sample_size=100,
        sample_window_start=bucket_ts - timedelta(days=30),
        sample_window_end=bucket_ts - timedelta(minutes=5),
        confidence_tier="mature", feature_schema_version=1, calculation_version=H16,
    )
    base.update(over)
    return base


def make_consensus(*, timeframe, bucket_ts, value=1.0, agreement=2.0 / 3.0,
                   confidence=50.0, coverage=2.0 / 3.0, **over):
    # Mirrors the REAL Stage 3 consensus row shape (aligned_inputs.py's
    # own `_check_provenance`): a genuine consensus row always carries
    # calculation_version/feature_schema_version too, even though the
    # regime/bias classifiers themselves never read them -- the final
    # context-snapshot builder's source-identity check does (see
    # context_snapshot.py's own docstring).
    base = dict(
        symbol="BTCUSDT", market_type="perp", timeframe=timeframe, bucket_ts=bucket_ts,
        price_move_pct_median=value, oi_change_pct_median=0.1, oi_direction_agreement=0.75,
        price_direction_agreement=agreement, consensus_confidence=confidence,
        min_coverage_ratio=coverage, calculation_version=H16, feature_schema_version=1,
    )
    base.update(over)
    return base


def make_4h_inputs(*, bucket_ts=B4H, value=1.0, rank=0.9, agreement=2.0 / 3.0,
                   percentiles_override=None, consensus_override=None):
    if percentiles_override is not None:
        percentiles = percentiles_override
    else:
        percentiles = [
            make_price_row(timeframe="4h", bucket_ts=bucket_ts, window="30d", value=value, rank=rank),
            make_comp_row(timeframe="4h", bucket_ts=bucket_ts, window="30d"),
        ]
    consensus = consensus_override if consensus_override is not None else make_consensus(
        timeframe="4h", bucket_ts=bucket_ts, value=value, agreement=agreement)
    return V2TimeframeInputs(
        timeframe="4h", bucket_ts=bucket_ts, bucket_end=bucket_ts + timedelta(hours=4),
        consensus=consensus, percentiles=tuple(percentiles), health={},
        reference_feature=None, reference_klines=None, reference_extrema=None,
    )


def make_1h_inputs(*, bucket_ts=B1H, value=1.0, rank=0.9, agreement=2.0 / 3.0,
                   percentiles_override=None, consensus_override=None):
    if percentiles_override is not None:
        percentiles = percentiles_override
    else:
        percentiles = [
            make_price_row(
                timeframe="1h", bucket_ts=bucket_ts, window="7d", value=value, rank=rank,
                tier="building"),
        ]
    consensus = consensus_override if consensus_override is not None else make_consensus(
        timeframe="1h", bucket_ts=bucket_ts, value=value, agreement=agreement)
    return V2TimeframeInputs(
        timeframe="1h", bucket_ts=bucket_ts, bucket_end=bucket_ts + timedelta(hours=1),
        consensus=consensus, percentiles=tuple(percentiles), health={},
        reference_feature=None, reference_klines=None, reference_extrema=None,
    )


def make_5m_inputs(bucket_ts=None):
    bucket_ts = bucket_ts if bucket_ts is not None else selected_bucket("5m", T)
    return V2TimeframeInputs(
        timeframe="5m", bucket_ts=bucket_ts, bucket_end=bucket_ts + timedelta(minutes=5),
        consensus=None, percentiles=(), health={},
        reference_feature=None, reference_klines=None, reference_extrema=None,
    )


def make_15m_inputs(bucket_ts=None):
    bucket_ts = bucket_ts if bucket_ts is not None else selected_bucket("15m", T)
    return V2TimeframeInputs(
        timeframe="15m", bucket_ts=bucket_ts, bucket_end=bucket_ts + timedelta(minutes=15),
        consensus=None, percentiles=(), health={},
        reference_feature=None, reference_klines=None, reference_extrema=None,
    )


def make_aligned(*, T=T, inputs_4h=None, inputs_1h=None, by_timeframe=None):
    if by_timeframe is None:
        by_timeframe = MappingProxyType({
            "5m": make_5m_inputs(),
            "15m": make_15m_inputs(),
            "1h": inputs_1h if inputs_1h is not None else make_1h_inputs(),
            "4h": inputs_4h if inputs_4h is not None else make_4h_inputs(),
        })
    return V2AlignedInputs(
        T=T, symbol="BTCUSDT", market_type="perp", calculation_version=H16,
        feature_schema_version=1, reference_exchange="binance", by_timeframe=by_timeframe,
    )


# ============================================================================
# 1. COMBINED HAPPY PATH (§52)
# ============================================================================
def test_happy_path_t_12_10_selects_exact_4h_1h_buckets():
    assert B4H == datetime(2026, 8, 15, 8, 0, tzinfo=UTC)
    assert B1H == datetime(2026, 8, 15, 11, 0, tzinfo=UTC)


def test_happy_path_bullish_regime_and_bullish_bias():
    aligned = make_aligned()
    snap = build_v2_context_snapshot(aligned)
    assert snap.T == T
    assert snap.regime_4h.bucket_ts == B4H
    assert snap.bias_1h.bucket_ts == B1H
    assert snap.regime_4h.regime == BULLISH_TRENDING
    assert snap.bias_1h.bias == BULLISH
    assert snap.symbol == aligned.symbol
    assert snap.market_type == aligned.market_type
    assert snap.calculation_version == aligned.calculation_version
    assert snap.feature_schema_version == aligned.feature_schema_version


# ============================================================================
# 2. COMBINED STATE-PRESERVATION MATRIX (§53) — these are context FACTS,
# never rejected at Stage 4.
# ============================================================================
def test_state_bullish_regime_neutral_bias():
    inputs_1h = make_1h_inputs(value=1.0, rank=0.55)  # usable, below BIAS_THRESHOLD
    snap = build_v2_context_snapshot(make_aligned(inputs_1h=inputs_1h))
    assert snap.regime_4h.regime == BULLISH_TRENDING
    assert snap.bias_1h.bias == NEUTRAL_NOT_ESTABLISHED


def test_state_bullish_regime_unavailable_bias():
    inputs_1h = make_1h_inputs(percentiles_override=[])
    snap = build_v2_context_snapshot(make_aligned(inputs_1h=inputs_1h))
    assert snap.regime_4h.regime == BULLISH_TRENDING
    assert snap.bias_1h.bias == BIAS_UNAVAILABLE


def test_state_non_directional_regime_bearish_bias():
    inputs_4h = make_4h_inputs(value=1.0, rank=0.5)  # price_evi == 0.0, below REGIME_TREND_THRESHOLD
    inputs_1h = make_1h_inputs(value=-1.0, rank=0.1)
    snap = build_v2_context_snapshot(make_aligned(inputs_4h=inputs_4h, inputs_1h=inputs_1h))
    assert snap.regime_4h.regime == NON_DIRECTIONAL
    assert snap.bias_1h.bias == BEARISH


def test_state_insufficient_data_regime_bullish_bias():
    inputs_4h = make_4h_inputs(percentiles_override=[])
    snap = build_v2_context_snapshot(make_aligned(inputs_4h=inputs_4h))
    assert snap.regime_4h.regime == INSUFFICIENT_DATA
    assert snap.bias_1h.bias == BULLISH


# ============================================================================
# 3. NEUTRAL VS UNAVAILABLE REGRESSION (§54)
# ============================================================================
def test_neutral_and_unavailable_bias_remain_distinct_in_snapshot():
    snap_neutral = build_v2_context_snapshot(
        make_aligned(inputs_1h=make_1h_inputs(value=1.0, rank=0.55)))
    snap_unavailable = build_v2_context_snapshot(
        make_aligned(inputs_1h=make_1h_inputs(percentiles_override=[])))
    assert snap_neutral.bias_1h.bias == NEUTRAL_NOT_ESTABLISHED
    assert snap_unavailable.bias_1h.bias == BIAS_UNAVAILABLE
    assert snap_neutral.bias_1h.bias != snap_unavailable.bias_1h.bias
    for snap in (snap_neutral, snap_unavailable):
        assert isinstance(snap.bias_1h.bias, str)
        assert snap.bias_1h.bias is not None
        assert snap.bias_1h.bias is not False


# ============================================================================
# 4. CROSS-BOUNDARY MIXING TESTS (§55) — selected_bucket() as the oracle
# ============================================================================
def test_mixed_4h_bucket_is_rejected():
    wrong_regime = V2RegimeResult(
        bucket_ts=B4H - timedelta(hours=4), regime=INSUFFICIENT_DATA, is_compressed=None)
    correct_bias = classify_1h_bias(make_1h_inputs())
    with pytest.raises(V2ContextSnapshotError):
        V2ContextSnapshot(
            T=T, symbol="BTCUSDT", market_type="perp", calculation_version=H16,
            feature_schema_version=1, regime_4h=wrong_regime, bias_1h=correct_bias)


def test_mixed_1h_bucket_is_rejected():
    correct_regime = classify_4h_regime(make_4h_inputs())
    wrong_bias = V2BiasResult(bucket_ts=B1H + timedelta(hours=1), bias=BIAS_UNAVAILABLE)
    with pytest.raises(V2ContextSnapshotError):
        V2ContextSnapshot(
            T=T, symbol="BTCUSDT", market_type="perp", calculation_version=H16,
            feature_schema_version=1, regime_4h=correct_regime, bias_1h=wrong_bias)


def test_context_from_a_different_T_cannot_be_paired_silently():
    T2 = T + timedelta(hours=4)
    regime_from_T2 = classify_4h_regime(make_4h_inputs(bucket_ts=selected_bucket("4h", T2)))
    bias_from_T = classify_1h_bias(make_1h_inputs())
    with pytest.raises(V2ContextSnapshotError):
        V2ContextSnapshot(
            T=T, symbol="BTCUSDT", market_type="perp", calculation_version=H16,
            feature_schema_version=1, regime_4h=regime_from_T2, bias_1h=bias_from_T)


def test_matching_buckets_via_build_v2_context_snapshot_never_mismatch():
    # The builder always derives both from the SAME aligned.T -- proves the
    # anti-mixing check passes for every legitimately-built snapshot too.
    snap = build_v2_context_snapshot(make_aligned())
    assert snap.regime_4h.bucket_ts == selected_bucket("4h", snap.T)
    assert snap.bias_1h.bucket_ts == selected_bucket("1h", snap.T)


# ============================================================================
# 4B. SOURCE IDENTITY VALIDATION — a hand-constructed V2AlignedInputs whose
# nested consensus/percentile rows disagree with its own top-level identity
# must be rejected by the builder BEFORE classification (pre-merge
# amendment; see context_snapshot.py's own "Source identity hardening"
# docstring section). The real load_v2_aligned_inputs() already guarantees
# this by construction -- this defends the same boundary against a
# hand-built V2AlignedInputs (tests, a future replay harness).
# ============================================================================
def test_4h_inputs_bucket_ts_mismatch_is_rejected():
    wrong_bucket_4h = make_4h_inputs(bucket_ts=B4H - timedelta(hours=4))
    with pytest.raises(V2ContextSnapshotError):
        build_v2_context_snapshot(make_aligned(inputs_4h=wrong_bucket_4h))


def test_1h_inputs_bucket_ts_mismatch_is_rejected():
    wrong_bucket_1h = make_1h_inputs(bucket_ts=B1H + timedelta(hours=1))
    with pytest.raises(V2ContextSnapshotError):
        build_v2_context_snapshot(make_aligned(inputs_1h=wrong_bucket_1h))


def test_A_consensus_symbol_mismatch_1h_is_rejected():
    bad_consensus = make_consensus(timeframe="1h", bucket_ts=B1H, symbol="ETHUSDT")
    bad_1h = make_1h_inputs(consensus_override=bad_consensus)
    with pytest.raises(V2ContextSnapshotError):
        build_v2_context_snapshot(make_aligned(inputs_1h=bad_1h))


def test_B_consensus_market_type_mismatch_4h_is_rejected():
    bad_consensus = make_consensus(timeframe="4h", bucket_ts=B4H, market_type="spot")
    bad_4h = make_4h_inputs(consensus_override=bad_consensus)
    with pytest.raises(V2ContextSnapshotError):
        build_v2_context_snapshot(make_aligned(inputs_4h=bad_4h))


def test_C_consensus_calculation_version_mismatch_1h_is_rejected():
    bad_consensus = make_consensus(
        timeframe="1h", bucket_ts=B1H, calculation_version="b" * 16)
    bad_1h = make_1h_inputs(consensus_override=bad_consensus)
    with pytest.raises(V2ContextSnapshotError):
        build_v2_context_snapshot(make_aligned(inputs_1h=bad_1h))


def test_D_consensus_feature_schema_version_mismatch_4h_is_rejected():
    bad_consensus = make_consensus(timeframe="4h", bucket_ts=B4H, feature_schema_version=2)
    bad_4h = make_4h_inputs(consensus_override=bad_consensus)
    with pytest.raises(V2ContextSnapshotError):
        build_v2_context_snapshot(make_aligned(inputs_4h=bad_4h))


def test_E_percentile_symbol_mismatch_1h_is_rejected():
    bad_row = make_price_row(
        timeframe="1h", bucket_ts=B1H, window="7d", value=1.0, rank=0.9, tier="building",
        symbol="ETHUSDT")
    bad_1h = make_1h_inputs(percentiles_override=[bad_row])
    with pytest.raises(V2ContextSnapshotError):
        build_v2_context_snapshot(make_aligned(inputs_1h=bad_1h))


def test_F_percentile_market_type_mismatch_4h_is_rejected():
    bad_row = make_price_row(
        timeframe="4h", bucket_ts=B4H, window="30d", value=1.0, rank=0.9, market_type="spot")
    comp_row = make_comp_row(timeframe="4h", bucket_ts=B4H, window="30d")
    bad_4h = make_4h_inputs(percentiles_override=[bad_row, comp_row])
    with pytest.raises(V2ContextSnapshotError):
        build_v2_context_snapshot(make_aligned(inputs_4h=bad_4h))


def test_G_percentile_calculation_version_mismatch_1h_is_rejected():
    bad_row = make_price_row(
        timeframe="1h", bucket_ts=B1H, window="7d", value=1.0, rank=0.9, tier="building",
        calculation_version="c" * 16)
    bad_1h = make_1h_inputs(percentiles_override=[bad_row])
    with pytest.raises(V2ContextSnapshotError):
        build_v2_context_snapshot(make_aligned(inputs_1h=bad_1h))


def test_H_percentile_feature_schema_version_mismatch_4h_is_rejected():
    bad_row = make_price_row(
        timeframe="4h", bucket_ts=B4H, window="30d", value=1.0, rank=0.9,
        feature_schema_version=2)
    comp_row = make_comp_row(timeframe="4h", bucket_ts=B4H, window="30d")
    bad_4h = make_4h_inputs(percentiles_override=[bad_row, comp_row])
    with pytest.raises(V2ContextSnapshotError):
        build_v2_context_snapshot(make_aligned(inputs_4h=bad_4h))


def test_I_percentile_row_from_wrong_bucket_1h_is_rejected():
    bad_row = make_price_row(
        timeframe="1h", bucket_ts=B1H - timedelta(hours=1), window="7d", value=1.0,
        rank=0.9, tier="building")
    bad_1h = make_1h_inputs(percentiles_override=[bad_row])
    with pytest.raises(V2ContextSnapshotError):
        build_v2_context_snapshot(make_aligned(inputs_1h=bad_1h))


@pytest.mark.parametrize("override", [
    {"scope": "exchange"},
    {"exchange": "binance"},
])
def test_J_percentile_row_wrong_scope_or_exchange_4h_is_rejected(override):
    bad_row = make_price_row(
        timeframe="4h", bucket_ts=B4H, window="30d", value=1.0, rank=0.9, **override)
    comp_row = make_comp_row(timeframe="4h", bucket_ts=B4H, window="30d")
    bad_4h = make_4h_inputs(percentiles_override=[bad_row, comp_row])
    with pytest.raises(V2ContextSnapshotError):
        build_v2_context_snapshot(make_aligned(inputs_4h=bad_4h))


def test_K_malformed_percentile_non_mapping_raises_domain_error_not_attributeerror():
    bad_1h = make_1h_inputs(percentiles_override=["not-a-mapping"])
    with pytest.raises(V2ContextSnapshotError):
        build_v2_context_snapshot(make_aligned(inputs_1h=bad_1h))


def test_L_empty_percentiles_remain_legitimate_for_both_4h_and_1h():
    empty_4h = make_4h_inputs(percentiles_override=[])
    empty_1h = make_1h_inputs(percentiles_override=[])
    snap = build_v2_context_snapshot(make_aligned(inputs_4h=empty_4h, inputs_1h=empty_1h))
    assert snap.regime_4h.regime == INSUFFICIENT_DATA
    assert snap.bias_1h.bias == BIAS_UNAVAILABLE


def test_consensus_none_remains_legitimate_for_both_4h_and_1h():
    no_consensus_4h = V2TimeframeInputs(
        timeframe="4h", bucket_ts=B4H, bucket_end=B4H + timedelta(hours=4),
        consensus=None, percentiles=(), health={},
        reference_feature=None, reference_klines=None, reference_extrema=None,
    )
    no_consensus_1h = V2TimeframeInputs(
        timeframe="1h", bucket_ts=B1H, bucket_end=B1H + timedelta(hours=1),
        consensus=None, percentiles=(), health={},
        reference_feature=None, reference_klines=None, reference_extrema=None,
    )
    snap = build_v2_context_snapshot(
        make_aligned(inputs_4h=no_consensus_4h, inputs_1h=no_consensus_1h))
    assert snap.regime_4h.regime == INSUFFICIENT_DATA
    assert snap.bias_1h.bias == BIAS_UNAVAILABLE


# ============================================================================
# 5. SNAPSHOT T VALIDATION (§56) — no silent flooring/normalization
# ============================================================================
def _valid_regime_bias():
    return classify_4h_regime(make_4h_inputs()), classify_1h_bias(make_1h_inputs())


def test_naive_T_is_rejected():
    regime, bias = _valid_regime_bias()
    with pytest.raises(V2ContextSnapshotError):
        V2ContextSnapshot(
            T=datetime(2026, 8, 15, 12, 10), symbol="BTCUSDT", market_type="perp",
            calculation_version=H16, feature_schema_version=1, regime_4h=regime, bias_1h=bias)


def test_non_utc_T_is_rejected():
    regime, bias = _valid_regime_bias()
    non_utc_T = datetime(2026, 8, 15, 15, 10, tzinfo=timezone(timedelta(hours=3)))
    with pytest.raises(V2ContextSnapshotError):
        V2ContextSnapshot(
            T=non_utc_T, symbol="BTCUSDT", market_type="perp", calculation_version=H16,
            feature_schema_version=1, regime_4h=regime, bias_1h=bias)


def test_non_whole_minute_T_is_rejected():
    regime, bias = _valid_regime_bias()
    with pytest.raises(V2ContextSnapshotError):
        V2ContextSnapshot(
            T=T.replace(second=1), symbol="BTCUSDT", market_type="perp",
            calculation_version=H16, feature_schema_version=1, regime_4h=regime, bias_1h=bias)


def test_non_5m_aligned_T_is_rejected():
    regime, bias = _valid_regime_bias()
    with pytest.raises(V2ContextSnapshotError):
        V2ContextSnapshot(
            T=T.replace(minute=11), symbol="BTCUSDT", market_type="perp",
            calculation_version=H16, feature_schema_version=1, regime_4h=regime, bias_1h=bias)


# ============================================================================
# 6. BUILDER MALFORMED CONTAINER TESTS (§57) — never a bare
# KeyError/AttributeError/TypeError
# ============================================================================
def test_wrong_top_level_type_raises_domain_error():
    with pytest.raises(V2ContextSnapshotError):
        build_v2_context_snapshot("not-an-aligned-inputs")


def test_by_timeframe_non_mapping_raises_domain_error():
    bad_aligned = V2AlignedInputs(
        T=T, symbol="BTCUSDT", market_type="perp", calculation_version=H16,
        feature_schema_version=1, reference_exchange="binance",
        by_timeframe=["not", "a", "mapping"],
    )
    with pytest.raises(V2ContextSnapshotError):
        build_v2_context_snapshot(bad_aligned)


def test_missing_4h_key_raises_domain_error():
    by_timeframe = MappingProxyType({
        "5m": make_5m_inputs(), "15m": make_15m_inputs(), "1h": make_1h_inputs(),
    })
    bad_aligned = make_aligned(by_timeframe=by_timeframe)
    with pytest.raises(V2ContextSnapshotError):
        build_v2_context_snapshot(bad_aligned)


def test_missing_1h_key_raises_domain_error():
    by_timeframe = MappingProxyType({
        "5m": make_5m_inputs(), "15m": make_15m_inputs(), "4h": make_4h_inputs(),
    })
    bad_aligned = make_aligned(by_timeframe=by_timeframe)
    with pytest.raises(V2ContextSnapshotError):
        build_v2_context_snapshot(bad_aligned)


def test_wrong_object_under_4h_key_raises_domain_error():
    by_timeframe = MappingProxyType({
        "5m": make_5m_inputs(), "15m": make_15m_inputs(), "1h": make_1h_inputs(),
        "4h": {"not": "a V2TimeframeInputs"},
    })
    bad_aligned = make_aligned(by_timeframe=by_timeframe)
    with pytest.raises(V2ContextSnapshotError):
        build_v2_context_snapshot(bad_aligned)


def test_wrong_object_under_1h_key_raises_domain_error():
    by_timeframe = MappingProxyType({
        "5m": make_5m_inputs(), "15m": make_15m_inputs(), "4h": make_4h_inputs(),
        "1h": "not-a-v2timeframeinputs",
    })
    bad_aligned = make_aligned(by_timeframe=by_timeframe)
    with pytest.raises(V2ContextSnapshotError):
        build_v2_context_snapshot(bad_aligned)


def test_wrong_nested_timeframe_field_raises_domain_error():
    # A V2TimeframeInputs whose OWN .timeframe disagrees with the key it
    # is stored under (a 1h inputs object placed under the "4h" key).
    mismatched = make_1h_inputs()
    by_timeframe = MappingProxyType({
        "5m": make_5m_inputs(), "15m": make_15m_inputs(), "1h": make_1h_inputs(),
        "4h": mismatched,
    })
    bad_aligned = make_aligned(by_timeframe=by_timeframe)
    with pytest.raises(V2ContextSnapshotError):
        build_v2_context_snapshot(bad_aligned)


def test_only_4h_and_1h_are_ever_dereferenced():
    # 5m/15m may be structurally absent/malformed -- the builder must
    # never even look at them.
    by_timeframe = MappingProxyType({
        "5m": "garbage", "15m": None, "1h": make_1h_inputs(), "4h": make_4h_inputs(),
    })
    bad_aligned = make_aligned(by_timeframe=by_timeframe)
    snap = build_v2_context_snapshot(bad_aligned)
    assert snap.regime_4h.regime == BULLISH_TRENDING
    assert snap.bias_1h.bias == BULLISH


# ============================================================================
# 7. CLASSIFIER ERROR WRAPPING (§58)
# ============================================================================
def test_regime_error_is_wrapped_with_cause_preserved():
    # Identity-correct (passes _validate_context_input_identity), but a
    # malformed PRESENT numeric field the identity check does not
    # inspect at all -- classify_4h_regime itself must reject it.
    bad_4h = make_4h_inputs(
        consensus_override=make_consensus(
            timeframe="4h", bucket_ts=B4H, confidence=float("nan")))
    with pytest.raises(V2ContextSnapshotError) as excinfo:
        build_v2_context_snapshot(make_aligned(inputs_4h=bad_4h))
    assert isinstance(excinfo.value.__cause__, V2RegimeError)


def test_bias_error_is_wrapped_with_cause_preserved():
    bad_1h = make_1h_inputs(
        consensus_override=make_consensus(
            timeframe="1h", bucket_ts=B1H, confidence=float("nan")))
    with pytest.raises(V2ContextSnapshotError) as excinfo:
        build_v2_context_snapshot(make_aligned(inputs_1h=bad_1h))
    assert isinstance(excinfo.value.__cause__, V2BiasError)


# ============================================================================
# 8. RESULT MODEL — immutability, exact fields
# ============================================================================
def test_snapshot_is_frozen():
    snap = build_v2_context_snapshot(make_aligned())
    with pytest.raises(Exception):
        snap.T = T + timedelta(minutes=5)  # type: ignore[misc]


def test_snapshot_dataclass_fields_are_exactly_expected():
    field_names = {f.name for f in dataclasses.fields(V2ContextSnapshot)}
    assert field_names == {
        "T", "symbol", "market_type", "calculation_version",
        "feature_schema_version", "regime_4h", "bias_1h",
    }


def test_same_aligned_snapshot_yields_the_same_context_result():
    aligned = make_aligned()
    snap1 = build_v2_context_snapshot(aligned)
    snap2 = build_v2_context_snapshot(aligned)
    assert snap1 == snap2


# ============================================================================
# 9. NO OVERALL DIRECTION (§61)
# ============================================================================
def test_snapshot_has_no_overall_direction_or_detector_fields():
    snap = build_v2_context_snapshot(make_aligned())
    forbidden_fields = (
        "direction", "overall_direction", "trade_direction", "recommended_direction",
        "score", "confidence", "setup_allowed", "trade_allowed",
    )
    for field in forbidden_fields:
        assert not hasattr(snap, field), f"unexpected field {field!r}"


# ============================================================================
# 10. PURITY / NO STAGE 5 LOGIC (§59, §60) — module-source checks
# ============================================================================
def _executable_body_source(module) -> str:
    """Source with every docstring stripped (mirrors the same helper in
    tests/analytics/test_forecasting_v2_regime_4h.py /
    tests/analytics/test_forecasting_v2_bias_1h.py)."""
    tree = ast.parse(inspect.getsource(module))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)):
                node.body = node.body[1:] or [ast.Pass()]
    return ast.unparse(tree)


def test_module_has_no_clock_random_uuid_network_filesystem_access():
    body_src = _executable_body_source(snapshot_module)
    forbidden = (
        "datetime.now(", "datetime.utcnow(", "time.time(", "time.monotonic(",
        "import random", "import uuid", "import yaml", "os.environ", "os.getenv",
        "requests.", "httpx.", "open(", "asyncpg", "subprocess",
    )
    for token in forbidden:
        assert token not in body_src, f"forbidden token found: {token!r}"


def test_module_imports_nothing_from_storage_runtime_main_notifications():
    tree = ast.parse(inspect.getsource(snapshot_module))
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        for name in names:
            for banned in ("storage", "runtime", "main", "notifications"):
                assert not name.startswith(banned), f"forbidden import: {name}"


def test_no_stage5_setup_detector_or_episode_logic_implemented_yet():
    body_src = _executable_body_source(snapshot_module)
    forbidden = (
        "directional_context_gate", "TREND_PULLBACK", "COMPRESSION_BREAKOUT",
        "CONFIRMED_BREAKOUT", "breakout_direction", "countertrend",
        "setup_allowed", "trade_allowed", "entry_zone", "invalidation",
        "protection_buffer", "RANGE_PROXY", "episode", "state_transition",
    )
    for token in forbidden:
        assert token not in body_src, f"forbidden Stage 5 token found: {token!r}"


def test_build_v2_context_snapshot_is_synchronous():
    assert not inspect.iscoroutinefunction(build_v2_context_snapshot)
