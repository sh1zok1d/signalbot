"""Tests for analytics/forecasting_v2/compression_breakout.py (Stage 5 —
Setup Detectors, PR 3 of ~4). No DB, no async — pure detection over
hand-built `V2CompressionBreakoutInputs`/`V2ContextSnapshot` fixtures,
following the existing V2 analytics test style
(tests/analytics/test_forecasting_v2_trend_pullback.py).

Exercises: the 5m decision clock (every legal 5m boundary, NOT restricted
to 15m formation boundaries, unlike TREND_PULLBACK); the exact
`COMPRESSION_LOOKBACK=16`-bucket compression evidence grid and its
§6.2/§6.3 quality gate + `compression_score()` (>= 0.75) `compressed_b`
boolean; the deterministic maximal-run partition + most-recent-end
selection; the selected-run structural range via
`derive_reference_extrema()`; the fresh 5m-crossing check; the 5m
trigger's quality/agreement/taker-flow gates; the shared
`directional_context_gate()`; entry-zone/invalidation formulas; the
worked SHORT/LONG vectors; `V2CompressionBreakoutCandidate` self-
validation; and the Stage 5/6 boundary — this module produces a
qualification only, never an episode/persistence/confirmation/expiry
decision."""
from __future__ import annotations

import ast
import inspect
from datetime import datetime, timedelta, timezone

import pytest

from analytics.forecasting_v2 import compression_breakout as cb_module
from analytics.forecasting_v2.bias_1h import (
    BEARISH, BIAS_UNAVAILABLE, BULLISH, NEUTRAL_NOT_ESTABLISHED, V2BiasResult,
)
from analytics.forecasting_v2.context_snapshot import V2ContextSnapshot
from analytics.forecasting_v2.events import LONG, SHORT
from analytics.forecasting_v2.regime_4h import (
    BEARISH_TRENDING, BULLISH_TRENDING, INSUFFICIENT_DATA, NON_DIRECTIONAL, V2RegimeResult,
)
from analytics.forecasting_v2.setup_common import (
    MIN_TICK_BUFFER_TICKS, SETUP_MIN_CONFIDENCE, SETUP_MIN_COVERAGE,
)
from analytics.forecasting_v2.compression_breakout import (
    BREAKOUT_MIN_AGREEMENT,
    COMPRESSION_CONFIRMATION_MAX_AGE_5M_BUCKETS,
    COMPRESSION_LOOKBACK,
    COMPRESSION_MIN_DURATION,
    COMPRESSION_PERCENTILE_WINDOW,
    COMPRESSION_THRESHOLD,
    EXPECTED_HORIZON,
    V2CompressionBreakoutCandidate,
    V2CompressionBreakoutError,
    V2CompressionBreakoutInputs,
    detect_compression_breakout,
)

UTC = timezone.utc
H16 = "a" * 16
SYMBOL = "BTCUSDT"
MARKET_TYPE = "perp"

T = datetime(2024, 1, 1, 12, 20, tzinfo=UTC)  # legal 5m boundary, NOT a 15m formation boundary
B5 = datetime(2024, 1, 1, 12, 15, tzinfo=UTC)
B15 = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
B4H = datetime(2024, 1, 1, 8, 0, tzinfo=UTC)
B1H = datetime(2024, 1, 1, 11, 0, tzinfo=UTC)
FIVE = timedelta(minutes=5)
FIFTEEN = timedelta(minutes=15)

LOOKBACK_START = B15 - (COMPRESSION_LOOKBACK - 1) * FIFTEEN
LOOKBACK_GRID = tuple(LOOKBACK_START + i * FIFTEEN for i in range(COMPRESSION_LOOKBACK))

RANGE_LOW = 63_800.0
RANGE_HIGH = 64_100.0


# ============================================================================
# fixtures
# ============================================================================
_FAMILIES = ("price_structure", "volume", "taker_flow", "oi", "funding", "liquidations")
_PRICE_EVI_FOR_REGIME = {
    BULLISH_TRENDING: 0.5, BEARISH_TRENDING: -0.5, NON_DIRECTIONAL: None, INSUFFICIENT_DATA: None,
}
_BIAS_EVI_FOR_BIAS = {
    # NEUTRAL_NOT_ESTABLISHED requires a real, measured bias_evi (tech-lead
    # amendment round 2) -- 0.0 is genuinely neutral, never a stand-in for
    # missing evidence. BIAS_UNAVAILABLE may legitimately carry None.
    BULLISH: 0.5, BEARISH: -0.5, NEUTRAL_NOT_ESTABLISHED: 0.0, BIAS_UNAVAILABLE: None,
}


def make_context(regime=NON_DIRECTIONAL, bias=NEUTRAL_NOT_ESTABLISHED, *, t=T, b4h=B4H, b1h=B1H,
                 is_compressed=None) -> V2ContextSnapshot:
    if is_compressed is None and regime == NON_DIRECTIONAL:
        is_compressed = False
    compression_score = None
    if regime == NON_DIRECTIONAL:
        compression_score = 0.9 if is_compressed else 0.5
    return V2ContextSnapshot(
        T=t, symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=H16,
        feature_schema_version=1,
        regime_4h=V2RegimeResult(
            bucket_ts=b4h, regime=regime, is_compressed=is_compressed,
            price_evi=_PRICE_EVI_FOR_REGIME[regime], compression_score=compression_score),
        bias_1h=V2BiasResult(bucket_ts=b1h, bias=bias, bias_evi=_BIAS_EVI_FOR_BIAS[bias]),
    )


def _family_maps(*, price_coverage, price_confidence, taker_coverage=None, taker_confidence=None):
    """§6.3a per-family maps -- `price_structure` (every gate in this
    family) and `taker_flow` (the fresh 5m trigger's SECOND mandatory
    family, `taker_*` defaults to the SAME values as `price_*` unless
    overridden) driven explicitly; the other four families always fully
    healthy (irrelevant to every test in this file)."""
    if taker_coverage is None:
        taker_coverage = price_coverage
    if taker_confidence is None:
        taker_confidence = price_confidence
    per_family = {
        "price_structure": (price_coverage, price_confidence),
        "taker_flow": (taker_coverage, taker_confidence),
    }
    coverage_by_metric = {}
    data_confidence_by_metric = {}
    for family in _FAMILIES:
        ratio, confidence = per_family.get(family, (1.0, 100.0))
        coverage_by_metric[family] = {"available": 3, "expected": 3, "ratio": ratio}
        data_confidence_by_metric[family] = confidence
    return coverage_by_metric, data_confidence_by_metric


def make_consensus_15m_row(bucket_ts, *, coverage=0.9, confidence=80.0, range_width=0.3, **over):
    coverage_by_metric, data_confidence_by_metric = _family_maps(
        price_coverage=coverage, price_confidence=confidence)
    base = dict(
        symbol=SYMBOL, market_type=MARKET_TYPE, timeframe="15m",
        calculation_version=H16, feature_schema_version=1, bucket_ts=bucket_ts,
        min_coverage_ratio=coverage, consensus_confidence=confidence,
        range_width_pct_median=range_width,
        coverage_by_metric=coverage_by_metric,
        data_confidence_by_metric=data_confidence_by_metric,
    )
    base.update(over)
    return base


def make_percentile_row(bucket_ts, *, score=0.82, tier="mature", **over):
    rank = None if score is None else 1.0 - score
    base = dict(
        scope="consensus", exchange="", symbol=SYMBOL, market_type=MARKET_TYPE,
        metric="range_width_pct_median", timeframe="15m", percentile_window="30d",
        calculation_version=H16, feature_schema_version=1, bucket_ts=bucket_ts,
        value=0.01, percentile_rank=rank, confidence_tier=tier,
        sample_window_end=bucket_ts - timedelta(minutes=1),
    )
    base.update(over)
    return base


def make_reference_15m_row(bucket_ts, *, close=64_000.0, bars_expected=15, bars_present=15,
                           is_usable=True, has_gap=False, **over):
    base = dict(
        exchange="binance", symbol=SYMBOL, market_type=MARKET_TYPE, timeframe="15m",
        calculation_version=H16, feature_schema_version=1, bucket_ts=bucket_ts,
        is_usable=is_usable, has_gap=has_gap, bars_present=bars_present,
        bars_expected=bars_expected, close_price=close,
    )
    base.update(over)
    return base


def make_reference_5m_row(bucket_ts, *, close=64_000.0, bars_expected=5, bars_present=5,
                          is_usable=True, has_gap=False, **over):
    base = dict(
        exchange="binance", symbol=SYMBOL, market_type=MARKET_TYPE, timeframe="5m",
        calculation_version=H16, feature_schema_version=1, bucket_ts=bucket_ts,
        is_usable=is_usable, has_gap=has_gap, bars_present=bars_present,
        bars_expected=bars_expected, close_price=close,
    )
    base.update(over)
    return base


def make_raw_1m_rows(bucket_ts, *, high=64_050.0, low=63_950.0, count=15):
    return tuple(
        {"exchange": "binance", "symbol": SYMBOL, "ts": bucket_ts + timedelta(minutes=m),
         "high": high, "low": low}
        for m in range(count)
    )


def make_trigger_5m_row(bucket_ts=B5, *, coverage=0.9, confidence=80.0, agreement=0.8,
                        taker=-1000.0, taker_coverage=None, taker_confidence=None, **over):
    coverage_by_metric, data_confidence_by_metric = _family_maps(
        price_coverage=coverage, price_confidence=confidence,
        taker_coverage=taker_coverage, taker_confidence=taker_confidence)
    base = dict(
        symbol=SYMBOL, market_type=MARKET_TYPE, timeframe="5m",
        calculation_version=H16, feature_schema_version=1, bucket_ts=bucket_ts,
        min_coverage_ratio=coverage, consensus_confidence=confidence,
        price_direction_agreement=agreement, taker_delta_notional_usd_sum=taker,
        coverage_by_metric=coverage_by_metric,
        data_confidence_by_metric=data_confidence_by_metric,
    )
    base.update(over)
    return base


def make_instrument(tick_size=0.1, **over):
    base = dict(exchange="binance", symbol=SYMBOL, market_type=MARKET_TYPE, tick_size=tick_size)
    base.update(over)
    return base


# The exact selected run for the shared worked-vector scaffold: the most
# recent 7 consecutive buckets (indices 9..15, i.e. the run ending exactly
# at B15) score >= COMPRESSION_THRESHOLD; every other bucket scores well
# below it.
_RUN_INDICES = tuple(range(9, 16))
RUN_START = LOOKBACK_GRID[_RUN_INDICES[0]]
RUN_END = LOOKBACK_GRID[_RUN_INDICES[-1]]
RUN_LENGTH = len(_RUN_INDICES)


def build_compression_grid_rows(*, compressed_indices=_RUN_INDICES, compressed_score=0.82,
                                uncompressed_score=0.10):
    consensus_rows = []
    percentile_rows = []
    for i, b in enumerate(LOOKBACK_GRID):
        consensus_rows.append(make_consensus_15m_row(b))
        score = compressed_score if i in compressed_indices else uncompressed_score
        percentile_rows.append(make_percentile_row(b, score=score))
    return tuple(consensus_rows), tuple(percentile_rows)


def build_structural_rows(*, run_indices=_RUN_INDICES, range_high=RANGE_HIGH, range_low=RANGE_LOW,
                          b15_close=64_000.0):
    reference_15m_rows = []
    raw_1m_rows = []
    run_start_ts = LOOKBACK_GRID[run_indices[0]]
    run_end_ts = LOOKBACK_GRID[run_indices[-1]]
    for i in run_indices:
        b = LOOKBACK_GRID[i]
        reference_15m_rows.append(make_reference_15m_row(b, close=b15_close))
        for m in range(15):
            ts = b + timedelta(minutes=m)
            high = range_high if (b == run_end_ts and m == 0) else (range_high - 50.0)
            low = range_low if (b == run_start_ts and m == 0) else (range_low + 50.0)
            raw_1m_rows.append({"exchange": "binance", "symbol": SYMBOL, "ts": ts,
                               "high": high, "low": low})
    return tuple(reference_15m_rows), tuple(raw_1m_rows)


def build_valid_short_inputs(**overrides):
    consensus_rows, percentile_rows = build_compression_grid_rows()
    reference_15m_rows, raw_1m_rows = build_structural_rows()
    kwargs = dict(
        context=make_context(),
        consensus_15m_rows=consensus_rows,
        percentile_15m_rows=percentile_rows,
        reference_15m_rows=reference_15m_rows,
        reference_1m_rows=raw_1m_rows,
        reference_5m_rows=(
            make_reference_5m_row(B5 - FIVE, close=63_820.0),
            make_reference_5m_row(B5, close=63_740.0),
        ),
        consensus_5m_rows=(make_trigger_5m_row(taker=-1000.0),),
        instrument=make_instrument(),
    )
    kwargs.update(overrides)
    return V2CompressionBreakoutInputs(**kwargs)


def build_valid_long_inputs(**overrides):
    consensus_rows, percentile_rows = build_compression_grid_rows()
    reference_15m_rows, raw_1m_rows = build_structural_rows()
    kwargs = dict(
        context=make_context(),
        consensus_15m_rows=consensus_rows,
        percentile_15m_rows=percentile_rows,
        reference_15m_rows=reference_15m_rows,
        reference_1m_rows=raw_1m_rows,
        reference_5m_rows=(
            make_reference_5m_row(B5 - FIVE, close=64_090.0),
            make_reference_5m_row(B5, close=64_110.0),
        ),
        consensus_5m_rows=(make_trigger_5m_row(taker=1000.0),),
        instrument=make_instrument(),
    )
    kwargs.update(overrides)
    return V2CompressionBreakoutInputs(**kwargs)


# ============================================================================
# 1. decision clock — every legal 5m boundary, NOT restricted to 15m formation
# ============================================================================
def test_qualifies_at_a_non_15m_formation_boundary():
    # T=12:20 is a legal 5m boundary but NOT a 15m formation boundary
    # (B15=12:00, B15+15m=12:15 != T) -- COMPRESSION_BREAKOUT still evaluates.
    result = detect_compression_breakout(build_valid_short_inputs())
    assert result is not None
    assert result.T == T
    assert result.bucket_5m == B5
    assert result.bucket_15m == B15


def test_qualifies_exactly_at_a_15m_formation_boundary_too():
    # Physically-coherent T=12:15 vector. A 5m close INSIDE B15's own
    # [12:00,12:15) window can never legitimately fall below B15's own
    # raw-1m-derived HTF_low if B15 itself were part of the selected
    # compression run -- so the selected run here ends BEFORE B15
    # (indices 8..14, i.e. up to B15-15m) and B15's own raw 1m bars never
    # participate in range_high/range_low. B15 itself stays healthy
    # (valid consensus quality + valid reference close for RANGE_PROXY/
    # protection_buffer) but is deliberately NOT compressed, so it cannot
    # extend the selected run. Only then may the current B5 (contained
    # inside B15) legitimately cross the already-established range.
    t2 = datetime(2024, 1, 1, 12, 15, tzinfo=UTC)  # B15=12:00, B15+15m==t2
    b5_t2 = datetime(2024, 1, 1, 12, 10, tzinfo=UTC)  # selected_bucket("5m", t2)
    run_indices = tuple(range(8, 15))  # length 7, ends at LOOKBACK_GRID[14] == B15 - 15m
    consensus_rows, percentile_rows = build_compression_grid_rows(compressed_indices=run_indices)
    reference_15m_rows, raw_1m_rows = build_structural_rows(run_indices=run_indices)
    # B15 itself is required for RANGE_PROXY's current-bucket gate and the
    # protection_buffer reference price, even though it is NOT part of the
    # selected run and contributes zero raw 1m bars to the structural range.
    reference_15m_rows = reference_15m_rows + (make_reference_15m_row(B15, close=64_000.0),)
    context = make_context(t=t2)
    result = detect_compression_breakout(build_valid_short_inputs(
        context=context,
        consensus_15m_rows=consensus_rows, percentile_15m_rows=percentile_rows,
        reference_15m_rows=reference_15m_rows, reference_1m_rows=raw_1m_rows,
        reference_5m_rows=(
            make_reference_5m_row(b5_t2 - FIVE, close=63_820.0),
            make_reference_5m_row(b5_t2, close=63_740.0),
        ),
        consensus_5m_rows=(make_trigger_5m_row(bucket_ts=b5_t2, taker=-1000.0),)))
    assert result is not None
    assert result.compression_end_bucket == LOOKBACK_GRID[14]
    assert result.compression_end_bucket < B15
    assert result.range_high == RANGE_HIGH
    assert result.range_low == RANGE_LOW


def test_wrong_inputs_type_raises():
    with pytest.raises(V2CompressionBreakoutError):
        detect_compression_breakout("not inputs")


def test_wrong_context_type_raises():
    inputs = build_valid_short_inputs()
    bad = V2CompressionBreakoutInputs(
        context="not a context", consensus_15m_rows=inputs.consensus_15m_rows,
        percentile_15m_rows=inputs.percentile_15m_rows,
        reference_15m_rows=inputs.reference_15m_rows,
        reference_1m_rows=inputs.reference_1m_rows,
        reference_5m_rows=inputs.reference_5m_rows,
        consensus_5m_rows=inputs.consensus_5m_rows, instrument=inputs.instrument)
    with pytest.raises(V2CompressionBreakoutError):
        detect_compression_breakout(bad)


# ============================================================================
# 2. compression run tests (A-G)
# ============================================================================
def test_exactly_6_consecutive_qualifies():
    consensus_rows, percentile_rows = build_compression_grid_rows(
        compressed_indices=tuple(range(10, 16)))  # length 6
    reference_15m_rows, raw_1m_rows = build_structural_rows(run_indices=tuple(range(10, 16)))
    result = detect_compression_breakout(build_valid_short_inputs(
        consensus_15m_rows=consensus_rows, percentile_15m_rows=percentile_rows,
        reference_15m_rows=reference_15m_rows, reference_1m_rows=raw_1m_rows))
    assert result is not None
    assert result.compression_length == 6


def test_5_consecutive_does_not_qualify():
    consensus_rows, percentile_rows = build_compression_grid_rows(
        compressed_indices=tuple(range(11, 16)))  # length 5
    reference_15m_rows, raw_1m_rows = build_structural_rows(run_indices=tuple(range(11, 16)))
    result = detect_compression_breakout(build_valid_short_inputs(
        consensus_15m_rows=consensus_rows, percentile_15m_rows=percentile_rows,
        reference_15m_rows=reference_15m_rows, reference_1m_rows=raw_1m_rows))
    assert result is None


def test_7_consecutive_selects_full_length_7():
    result = detect_compression_breakout(build_valid_short_inputs())
    assert result is not None
    assert result.compression_length == 7
    assert result.compression_start_bucket == RUN_START
    assert result.compression_end_bucket == RUN_END


def test_9_consecutive_uses_full_length_not_truncated():
    run9 = tuple(range(7, 16))
    consensus_rows, percentile_rows = build_compression_grid_rows(compressed_indices=run9)
    reference_15m_rows, raw_1m_rows = build_structural_rows(run_indices=run9)
    result = detect_compression_breakout(build_valid_short_inputs(
        consensus_15m_rows=consensus_rows, percentile_15m_rows=percentile_rows,
        reference_15m_rows=reference_15m_rows, reference_1m_rows=raw_1m_rows))
    assert result is not None
    assert result.compression_length == 9
    assert result.compression_start_bucket == LOOKBACK_GRID[7]


def test_setup_strength_is_full_run_mean_not_end_bucket_only():
    # §8.2 LOAD-BEARING: setup_strength = mean(compression_score) over the
    # ENTIRE selected run, never just the end bucket's own score. Every
    # bucket in the 7-long run gets a DIFFERENT compression_score (still
    # all >= COMPRESSION_THRESHOLD so the run itself still qualifies) --
    # if the implementation regressed to "end-bucket-only", the assertion
    # against the true mean would fail, and it would visibly differ from
    # the (wrong) end-bucket-only value asserted separately below.
    per_bucket_scores = [0.80, 0.99, 0.76, 0.93, 0.75, 0.88, 0.97]  # indices 9..15
    assert len(per_bucket_scores) == RUN_LENGTH
    consensus_rows = []
    percentile_rows = []
    for i, b in enumerate(LOOKBACK_GRID):
        consensus_rows.append(make_consensus_15m_row(b))
        if i in _RUN_INDICES:
            score = per_bucket_scores[_RUN_INDICES.index(i)]
        else:
            score = 0.10
        percentile_rows.append(make_percentile_row(b, score=score))
    result = detect_compression_breakout(build_valid_short_inputs(
        consensus_15m_rows=tuple(consensus_rows), percentile_15m_rows=tuple(percentile_rows)))
    assert result is not None
    true_mean = sum(per_bucket_scores) / len(per_bucket_scores)
    end_bucket_only = per_bucket_scores[-1]
    assert true_mean != end_bucket_only  # the vector is only meaningful if these differ
    assert result.setup_strength == pytest.approx(true_mean)
    assert result.setup_strength != pytest.approx(end_bucket_only)


def test_setup_strength_full_run_mean_when_run_ends_before_current_b15():
    # Adversarial vector B: the qualifying run ends strictly BEFORE the
    # current B15 bucket (buckets after the run are simply below
    # threshold, not fabricated/extended) -- setup_strength must still be
    # the mean over exactly the selected run's own buckets, not smeared
    # across the gap to B15.
    older_run = tuple(range(0, 9))  # indices 0..8, ends well before B15 (index 15)
    per_bucket_scores = [0.80, 0.99, 0.76, 0.93, 0.75, 0.88, 0.97, 0.79, 0.82]
    assert len(per_bucket_scores) == len(older_run)
    consensus_rows = []
    percentile_rows = []
    for i, b in enumerate(LOOKBACK_GRID):
        consensus_rows.append(make_consensus_15m_row(b))
        if i in older_run:
            score = per_bucket_scores[older_run.index(i)]
        else:
            score = 0.10
        percentile_rows.append(make_percentile_row(b, score=score))
    reference_15m_rows, raw_1m_rows = build_structural_rows(run_indices=older_run)
    # B15 itself still needs its own reference-feature row for the §34 15m
    # close lookup, independent of run membership.
    reference_15m_rows = reference_15m_rows + (make_reference_15m_row(B15, close=64_000.0),)
    result = detect_compression_breakout(build_valid_short_inputs(
        consensus_15m_rows=tuple(consensus_rows), percentile_15m_rows=tuple(percentile_rows),
        reference_15m_rows=reference_15m_rows, reference_1m_rows=raw_1m_rows))
    assert result is not None
    assert result.compression_end_bucket == LOOKBACK_GRID[8]
    assert result.compression_end_bucket != B15
    assert result.setup_strength == pytest.approx(sum(per_bucket_scores) / len(per_bucket_scores))


def test_setup_strength_selects_newer_runs_own_scores_not_older_runs():
    # Adversarial vector C: two separated qualifying runs. The selection
    # itself already picks the most recent one (proven elsewhere) -- this
    # vector proves setup_strength is computed from the SELECTED (newer)
    # run's own scores, not accidentally averaged with (or substituted by)
    # the older run's scores.
    older_run = tuple(range(0, 9))
    newer_run = tuple(range(10, 16))
    older_scores = [0.90] * len(older_run)  # deliberately a different constant
    newer_scores = [0.80, 0.99, 0.76, 0.93, 0.75, 0.88]
    assert len(newer_scores) == len(newer_run)
    consensus_rows = []
    percentile_rows = []
    for i, b in enumerate(LOOKBACK_GRID):
        consensus_rows.append(make_consensus_15m_row(b))
        if i in older_run:
            score = older_scores[older_run.index(i)]
        elif i in newer_run:
            score = newer_scores[newer_run.index(i)]
        else:
            score = 0.10
        percentile_rows.append(make_percentile_row(b, score=score))
    reference_15m_rows, raw_1m_rows = build_structural_rows(run_indices=newer_run)
    result = detect_compression_breakout(build_valid_short_inputs(
        consensus_15m_rows=tuple(consensus_rows), percentile_15m_rows=tuple(percentile_rows),
        reference_15m_rows=reference_15m_rows, reference_1m_rows=raw_1m_rows))
    assert result is not None
    assert result.compression_start_bucket == LOOKBACK_GRID[10]
    assert result.setup_strength == pytest.approx(sum(newer_scores) / len(newer_scores))
    assert result.setup_strength != pytest.approx(0.90)  # never the older run's constant


def test_two_qualifying_runs_selects_newer_even_if_shorter():
    # older run: indices 0..8 (length 9); newer run: indices 10..15 (length 6).
    older_run = tuple(range(0, 9))
    newer_run = tuple(range(10, 16))
    all_compressed = older_run + newer_run
    consensus_rows, percentile_rows = build_compression_grid_rows(compressed_indices=all_compressed)
    reference_15m_rows, raw_1m_rows = build_structural_rows(run_indices=newer_run)
    result = detect_compression_breakout(build_valid_short_inputs(
        consensus_15m_rows=consensus_rows, percentile_15m_rows=percentile_rows,
        reference_15m_rows=reference_15m_rows, reference_1m_rows=raw_1m_rows))
    assert result is not None
    assert result.compression_length == 6
    assert result.compression_start_bucket == LOOKBACK_GRID[10]
    assert result.compression_end_bucket == LOOKBACK_GRID[15]


def test_unavailable_bucket_splits_apparent_long_run():
    # indices 8..15 would be an 8-long run, but index 12 has degraded
    # quality (breaks the run into 8..11 (len4) and 13..15 (len3) -- neither
    # qualifies at MIN_DURATION=6).
    consensus_rows, percentile_rows = build_compression_grid_rows(
        compressed_indices=tuple(range(8, 16)))
    consensus_rows = list(consensus_rows)
    consensus_rows[12] = make_consensus_15m_row(LOOKBACK_GRID[12], coverage=0.1)  # below threshold
    result = detect_compression_breakout(build_valid_short_inputs(
        consensus_15m_rows=tuple(consensus_rows), percentile_15m_rows=percentile_rows))
    assert result is None


def test_score_just_below_threshold_breaks_run():
    # Break the MIDDLE bucket (index 12) of the 9..15 run: splits it into
    # 9..11 (len3) and 13..15 (len3), neither of which reaches
    # COMPRESSION_MIN_DURATION=6 -- no qualifying run remains.
    consensus_rows, percentile_rows = build_compression_grid_rows(
        compressed_indices=tuple(range(9, 16)))
    percentile_rows = list(percentile_rows)
    percentile_rows[12] = make_percentile_row(LOOKBACK_GRID[12], score=COMPRESSION_THRESHOLD - 1e-9)
    result = detect_compression_breakout(build_valid_short_inputs(
        consensus_15m_rows=consensus_rows, percentile_15m_rows=tuple(percentile_rows)))
    assert result is None


def test_breaking_the_oldest_bucket_shrinks_but_does_not_eliminate_the_run():
    # Breaking bucket 9 (the OLDEST bucket of the 9..15 run) shrinks the
    # run to 10..15 -- still exactly COMPRESSION_MIN_DURATION=6, so it
    # still qualifies (using the shrunk run's own boundaries).
    consensus_rows, percentile_rows = build_compression_grid_rows(
        compressed_indices=tuple(range(9, 16)))
    percentile_rows = list(percentile_rows)
    percentile_rows[9] = make_percentile_row(LOOKBACK_GRID[9], score=COMPRESSION_THRESHOLD - 1e-9)
    reference_15m_rows, raw_1m_rows = build_structural_rows(run_indices=tuple(range(10, 16)))
    result = detect_compression_breakout(build_valid_short_inputs(
        consensus_15m_rows=consensus_rows, percentile_15m_rows=tuple(percentile_rows),
        reference_15m_rows=reference_15m_rows, reference_1m_rows=raw_1m_rows))
    assert result is not None
    assert result.compression_length == 6
    assert result.compression_start_bucket == LOOKBACK_GRID[10]
    assert result.compression_end_bucket == RUN_END


def test_score_exactly_threshold_qualifies():
    consensus_rows, percentile_rows = build_compression_grid_rows()
    percentile_rows = list(percentile_rows)
    for i in _RUN_INDICES:
        percentile_rows[i] = make_percentile_row(LOOKBACK_GRID[i], score=COMPRESSION_THRESHOLD)
    result = detect_compression_breakout(build_valid_short_inputs(
        consensus_15m_rows=consensus_rows, percentile_15m_rows=tuple(percentile_rows)))
    assert result is not None


# ============================================================================
# 3. percentile identity tests
# ============================================================================
@pytest.mark.parametrize("field,bad_value", [
    ("scope", "exchange"),
    ("exchange", "binance"),
    ("metric", "price_move_pct_median"),
    ("timeframe", "5m"),
    ("percentile_window", "7d"),
    ("symbol", "ETHUSDT"),
    ("market_type", "spot"),
    ("calculation_version", "b" * 16),
    ("feature_schema_version", 999),
])
def test_percentile_row_wrong_identity_raises(field, bad_value):
    consensus_rows, percentile_rows = build_compression_grid_rows()
    percentile_rows = list(percentile_rows)
    percentile_rows[9] = make_percentile_row(LOOKBACK_GRID[9], **{field: bad_value})
    with pytest.raises(V2CompressionBreakoutError):
        detect_compression_breakout(build_valid_short_inputs(
            consensus_15m_rows=consensus_rows, percentile_15m_rows=tuple(percentile_rows)))


def test_percentile_sample_window_end_at_bucket_ts_raises():
    consensus_rows, percentile_rows = build_compression_grid_rows()
    percentile_rows = list(percentile_rows)
    percentile_rows[9] = make_percentile_row(
        LOOKBACK_GRID[9], sample_window_end=LOOKBACK_GRID[9])
    with pytest.raises(V2CompressionBreakoutError):
        detect_compression_breakout(build_valid_short_inputs(
            consensus_15m_rows=consensus_rows, percentile_15m_rows=tuple(percentile_rows)))


def test_percentile_tier_none_breaks_run():
    consensus_rows, percentile_rows = build_compression_grid_rows()
    percentile_rows = list(percentile_rows)
    percentile_rows[12] = make_percentile_row(LOOKBACK_GRID[12], tier="none")
    result = detect_compression_breakout(build_valid_short_inputs(
        consensus_15m_rows=consensus_rows, percentile_15m_rows=tuple(percentile_rows)))
    assert result is None  # splits 9..15 into 9..11 (len3) and 13..15 (len3) -- neither qualifies


def test_percentile_tier_building_is_eligible():
    consensus_rows, percentile_rows = build_compression_grid_rows()
    percentile_rows = list(percentile_rows)
    for i in _RUN_INDICES:
        percentile_rows[i] = make_percentile_row(LOOKBACK_GRID[i], tier="building")
    result = detect_compression_breakout(build_valid_short_inputs(
        consensus_15m_rows=consensus_rows, percentile_15m_rows=tuple(percentile_rows)))
    assert result is not None


def test_percentile_malformed_rank_raises():
    consensus_rows, percentile_rows = build_compression_grid_rows()
    percentile_rows = list(percentile_rows)
    percentile_rows[9] = make_percentile_row(LOOKBACK_GRID[9], percentile_rank=1.5)
    with pytest.raises(V2CompressionBreakoutError):
        detect_compression_breakout(build_valid_short_inputs(
            consensus_15m_rows=consensus_rows, percentile_15m_rows=tuple(percentile_rows)))


def test_percentile_malformed_value_raises():
    consensus_rows, percentile_rows = build_compression_grid_rows()
    percentile_rows = list(percentile_rows)
    percentile_rows[9] = make_percentile_row(LOOKBACK_GRID[9], value=-1.0)
    with pytest.raises(V2CompressionBreakoutError):
        detect_compression_breakout(build_valid_short_inputs(
            consensus_15m_rows=consensus_rows, percentile_15m_rows=tuple(percentile_rows)))


def test_malformed_percentile_row_raises_even_if_no_qualifying_run_anyway():
    # §51: a malformed PRESENT percentile row must raise even though the
    # resulting compression grid would legitimately have no qualifying run.
    consensus_rows, percentile_rows = build_compression_grid_rows(compressed_indices=())
    percentile_rows = list(percentile_rows)
    percentile_rows[3] = make_percentile_row(LOOKBACK_GRID[3], scope="exchange")
    with pytest.raises(V2CompressionBreakoutError):
        detect_compression_breakout(build_valid_short_inputs(
            consensus_15m_rows=consensus_rows, percentile_15m_rows=tuple(percentile_rows)))


# ============================================================================
# 4. 15m quality tests
# ============================================================================
def test_compression_bucket_quality_at_exact_boundaries_may_count():
    consensus_rows, percentile_rows = build_compression_grid_rows()
    consensus_rows = list(consensus_rows)
    for i in _RUN_INDICES:
        consensus_rows[i] = make_consensus_15m_row(
            LOOKBACK_GRID[i], coverage=SETUP_MIN_COVERAGE, confidence=SETUP_MIN_CONFIDENCE)
    result = detect_compression_breakout(build_valid_short_inputs(
        consensus_15m_rows=tuple(consensus_rows), percentile_15m_rows=percentile_rows))
    assert result is not None


def test_compression_bucket_quality_just_below_breaks_run():
    # Break the MIDDLE bucket (index 12): splits 9..15 into two 3-long
    # pieces, below COMPRESSION_MIN_DURATION=6 -- no qualifying run remains.
    consensus_rows, percentile_rows = build_compression_grid_rows()
    consensus_rows = list(consensus_rows)
    consensus_rows[12] = make_consensus_15m_row(LOOKBACK_GRID[12], coverage=SETUP_MIN_COVERAGE - 1e-9)
    result = detect_compression_breakout(build_valid_short_inputs(
        consensus_15m_rows=tuple(consensus_rows), percentile_15m_rows=percentile_rows))
    assert result is None


def test_compression_bucket_quality_none_breaks_run():
    consensus_rows, percentile_rows = build_compression_grid_rows()
    consensus_rows = list(consensus_rows)
    consensus_rows[12] = make_consensus_15m_row(LOOKBACK_GRID[12], coverage=None)
    result = detect_compression_breakout(build_valid_short_inputs(
        consensus_15m_rows=tuple(consensus_rows), percentile_15m_rows=percentile_rows))
    assert result is None  # splits 9..15 into 9..11 (len3) and 13..15 (len3) -- neither qualifies


def test_compression_bucket_malformed_quality_raises():
    consensus_rows, percentile_rows = build_compression_grid_rows()
    consensus_rows = list(consensus_rows)
    consensus_rows[9] = make_consensus_15m_row(LOOKBACK_GRID[9], coverage=1.5)
    with pytest.raises(V2CompressionBreakoutError):
        detect_compression_breakout(build_valid_short_inputs(
            consensus_15m_rows=tuple(consensus_rows), percentile_15m_rows=percentile_rows))


def test_current_b15_quality_exact_boundaries_pass():
    consensus_rows, percentile_rows = build_compression_grid_rows()
    consensus_rows = list(consensus_rows)
    consensus_rows[15] = make_consensus_15m_row(
        B15, coverage=SETUP_MIN_COVERAGE, confidence=SETUP_MIN_CONFIDENCE)
    result = detect_compression_breakout(build_valid_short_inputs(
        consensus_15m_rows=tuple(consensus_rows), percentile_15m_rows=percentile_rows))
    assert result is not None


def test_current_b15_quality_below_threshold_no_candidate_even_if_older_run_qualifies():
    older_run = tuple(range(0, 9))  # ends well before B15
    consensus_rows, percentile_rows = build_compression_grid_rows(compressed_indices=older_run)
    consensus_rows = list(consensus_rows)
    consensus_rows[15] = make_consensus_15m_row(B15, coverage=0.1)  # B15 itself degraded
    reference_15m_rows, raw_1m_rows = build_structural_rows(run_indices=older_run)
    result = detect_compression_breakout(build_valid_short_inputs(
        consensus_15m_rows=tuple(consensus_rows), percentile_15m_rows=percentile_rows,
        reference_15m_rows=reference_15m_rows, reference_1m_rows=raw_1m_rows))
    assert result is None


@pytest.mark.parametrize("family", ["volume", "taker_flow", "oi", "funding", "liquidations"])
def test_formation_window_only_reads_price_structure_other_families_cannot_break_run(family):
    # §6.3a required matrix: the formation-window per-bucket quality gate
    # (COMPRESSION_BREAKOUT's run detection) is scoped to price_structure
    # ONLY, even though the fresh 5m trigger later ALSO reads taker_flow --
    # the two gates are on different rows/timeframes. Zeroing any other
    # family at the CURRENT B15 formation bucket must have zero effect.
    consensus_rows, percentile_rows = build_compression_grid_rows()
    consensus_rows = list(consensus_rows)
    current = dict(consensus_rows[15])
    assert current["bucket_ts"] == B15
    coverage_by_metric = dict(current["coverage_by_metric"])
    coverage_by_metric[family] = {"available": 0, "expected": 3, "ratio": 0.0}
    current["coverage_by_metric"] = coverage_by_metric
    data_confidence_by_metric = dict(current["data_confidence_by_metric"])
    data_confidence_by_metric[family] = 0.0
    current["data_confidence_by_metric"] = data_confidence_by_metric
    consensus_rows[15] = current
    result = detect_compression_breakout(build_valid_short_inputs(
        consensus_15m_rows=tuple(consensus_rows), percentile_15m_rows=percentile_rows))
    assert result is not None


def test_current_b15_row_missing_no_candidate():
    consensus_rows, percentile_rows = build_compression_grid_rows()
    consensus_rows = tuple(r for r in consensus_rows if r["bucket_ts"] != B15)
    result = detect_compression_breakout(build_valid_short_inputs(
        consensus_15m_rows=consensus_rows, percentile_15m_rows=percentile_rows))
    assert result is None


def test_missing_non_run_range_proxy_peer_returns_none_not_keyerror():
    # LOOKBACK_GRID[2] is inside the final RANGE_PROXY_N=14 grid
    # (indices 2..15) but OUTSIDE the selected compression run (9..15).
    # The qualifying run is untouched, B15 itself is healthy, but this
    # ONE other RANGE_PROXY peer bucket is entirely missing -- that must
    # be legitimate UNAVAILABLE input (None), never a bare KeyError.
    consensus_rows, percentile_rows = build_compression_grid_rows()
    consensus_rows = tuple(r for r in consensus_rows if r["bucket_ts"] != LOOKBACK_GRID[2])
    result = detect_compression_breakout(build_valid_short_inputs(
        consensus_15m_rows=consensus_rows, percentile_15m_rows=percentile_rows))
    assert result is None


def test_malformed_present_range_proxy_value_raises_even_with_different_missing_peer():
    # A missing peer must NEVER mask a malformed PRESENT peer elsewhere in
    # the same exact final-14 RANGE_PROXY grid (indices 2..15) --
    # range_proxy_pct() itself validates every PRESENT row's range_width_
    # pct_median BEFORE its own exact-grid-completeness check runs; the
    # caller must hand it every PRESENT row (filtered only by presence,
    # never short-circuited by a separate "any missing" check) so that
    # contract actually holds.
    consensus_rows, percentile_rows = build_compression_grid_rows()
    consensus_rows = [r for r in consensus_rows if r["bucket_ts"] != LOOKBACK_GRID[2]]  # missing peer
    consensus_rows = [
        make_consensus_15m_row(r["bucket_ts"], range_width="not-a-number")
        if r["bucket_ts"] == LOOKBACK_GRID[5] else r  # a DIFFERENT present peer, corrupted
        for r in consensus_rows
    ]
    with pytest.raises(V2CompressionBreakoutError):
        detect_compression_breakout(build_valid_short_inputs(
            consensus_15m_rows=tuple(consensus_rows), percentile_15m_rows=percentile_rows))


def test_malformed_present_range_proxy_value_nan_raises_even_with_different_missing_peer():
    consensus_rows, percentile_rows = build_compression_grid_rows()
    consensus_rows = [r for r in consensus_rows if r["bucket_ts"] != LOOKBACK_GRID[2]]
    consensus_rows = [
        make_consensus_15m_row(r["bucket_ts"], range_width=float("nan"))
        if r["bucket_ts"] == LOOKBACK_GRID[5] else r
        for r in consensus_rows
    ]
    with pytest.raises(V2CompressionBreakoutError):
        detect_compression_breakout(build_valid_short_inputs(
            consensus_15m_rows=tuple(consensus_rows), percentile_15m_rows=percentile_rows))


def test_malformed_present_range_proxy_value_negative_raises_even_with_different_missing_peer():
    consensus_rows, percentile_rows = build_compression_grid_rows()
    consensus_rows = [r for r in consensus_rows if r["bucket_ts"] != LOOKBACK_GRID[2]]
    consensus_rows = [
        make_consensus_15m_row(r["bucket_ts"], range_width=-1.0)
        if r["bucket_ts"] == LOOKBACK_GRID[5] else r
        for r in consensus_rows
    ]
    with pytest.raises(V2CompressionBreakoutError):
        detect_compression_breakout(build_valid_short_inputs(
            consensus_15m_rows=tuple(consensus_rows), percentile_15m_rows=percentile_rows))


# ============================================================================
# 5. structural extrema tests
# ============================================================================
def test_selected_run_range_high_low_from_raw_bars_not_feature_close():
    result = detect_compression_breakout(build_valid_short_inputs())
    assert result is not None
    assert result.range_high == RANGE_HIGH
    assert result.range_low == RANGE_LOW


def test_massive_extrema_in_unselected_older_run_does_not_leak_in():
    older_run = tuple(range(0, 6))  # qualifies (len6) but is NOT selected (older)
    newer_run = _RUN_INDICES
    all_compressed = older_run + newer_run
    consensus_rows, percentile_rows = build_compression_grid_rows(compressed_indices=all_compressed)
    reference_15m_rows, raw_1m_rows = build_structural_rows(run_indices=newer_run)
    # add wildly-out-of-range structural rows for the OLDER, unselected run
    extra_ref = tuple(make_reference_15m_row(LOOKBACK_GRID[i], close=999_999.0) for i in older_run)
    extra_raw = tuple(
        row for i in older_run
        for row in make_raw_1m_rows(LOOKBACK_GRID[i], high=999_999.0, low=1.0))
    result = detect_compression_breakout(build_valid_short_inputs(
        consensus_15m_rows=consensus_rows, percentile_15m_rows=percentile_rows,
        reference_15m_rows=reference_15m_rows + extra_ref,
        reference_1m_rows=raw_1m_rows + extra_raw))
    assert result is not None
    assert result.range_high == RANGE_HIGH
    assert result.range_low == RANGE_LOW


def test_selected_run_bucket_missing_reference_feature_no_candidate():
    reference_15m_rows, raw_1m_rows = build_structural_rows()
    reference_15m_rows = tuple(r for r in reference_15m_rows if r["bucket_ts"] != RUN_START)
    result = detect_compression_breakout(build_valid_short_inputs(
        reference_15m_rows=reference_15m_rows, reference_1m_rows=raw_1m_rows))
    assert result is None


def test_selected_run_bucket_raw_bars_incomplete_despite_usable_claim_raises():
    reference_15m_rows, raw_1m_rows = build_structural_rows()
    # Drop one raw bar for RUN_START -- reference_feature still CLAIMS full/usable.
    raw_1m_rows = tuple(r for r in raw_1m_rows if not (r["ts"] == RUN_START))
    with pytest.raises(V2CompressionBreakoutError):
        detect_compression_breakout(build_valid_short_inputs(
            reference_15m_rows=reference_15m_rows, reference_1m_rows=raw_1m_rows))


def test_full_15_raw_bars_present_14_expected_raises():
    reference_15m_rows, raw_1m_rows = build_structural_rows()
    reference_15m_rows = tuple(
        {**r, "bars_expected": 14} if r["bucket_ts"] == RUN_START else r
        for r in reference_15m_rows)
    with pytest.raises(V2CompressionBreakoutError):
        detect_compression_breakout(build_valid_short_inputs(
            reference_15m_rows=reference_15m_rows, reference_1m_rows=raw_1m_rows))


def test_bars_expected_15_present_14_unavailable_no_candidate():
    reference_15m_rows, raw_1m_rows = build_structural_rows()
    reference_15m_rows = tuple(
        {**r, "bars_present": 14, "is_usable": False} if r["bucket_ts"] == RUN_START else r
        for r in reference_15m_rows)
    result = detect_compression_breakout(build_valid_short_inputs(
        reference_15m_rows=reference_15m_rows, reference_1m_rows=raw_1m_rows))
    assert result is None


# ============================================================================
# 6. fresh 5m crossing tests
# ============================================================================
def test_fresh_long_cross_from_below_qualifies():
    result = detect_compression_breakout(build_valid_long_inputs())
    assert result is not None
    assert result.direction == LONG


def test_fresh_long_cross_from_further_below_qualifies():
    result = detect_compression_breakout(build_valid_long_inputs(
        reference_5m_rows=(
            make_reference_5m_row(B5 - FIVE, close=64_050.0),
            make_reference_5m_row(B5, close=64_110.0),
        )))
    assert result is not None
    assert result.direction == LONG


def test_already_outside_high_not_fresh_no_candidate():
    result = detect_compression_breakout(build_valid_long_inputs(
        reference_5m_rows=(
            make_reference_5m_row(B5 - FIVE, close=64_110.0),
            make_reference_5m_row(B5, close=64_120.0),
        )))
    assert result is None


def test_current_close_equals_range_high_no_candidate():
    result = detect_compression_breakout(build_valid_long_inputs(
        reference_5m_rows=(
            make_reference_5m_row(B5 - FIVE, close=64_090.0),
            make_reference_5m_row(B5, close=RANGE_HIGH),
        )))
    assert result is None


def test_current_close_below_high_no_long_candidate():
    result = detect_compression_breakout(build_valid_long_inputs(
        reference_5m_rows=(
            make_reference_5m_row(B5 - FIVE, close=64_050.0),
            make_reference_5m_row(B5, close=64_090.0),
        )))
    assert result is None


def test_fresh_short_cross_qualifies():
    result = detect_compression_breakout(build_valid_short_inputs())
    assert result is not None
    assert result.direction == SHORT


def test_already_outside_low_not_fresh_no_candidate():
    result = detect_compression_breakout(build_valid_short_inputs(
        reference_5m_rows=(
            make_reference_5m_row(B5 - FIVE, close=63_750.0),
            make_reference_5m_row(B5, close=63_740.0),
        )))
    assert result is None


def test_current_close_equals_range_low_no_candidate():
    result = detect_compression_breakout(build_valid_short_inputs(
        reference_5m_rows=(
            make_reference_5m_row(B5 - FIVE, close=63_820.0),
            make_reference_5m_row(B5, close=RANGE_LOW),
        )))
    assert result is None


def test_previous_or_current_5m_close_missing_no_candidate():
    result = detect_compression_breakout(build_valid_short_inputs(
        reference_5m_rows=(make_reference_5m_row(B5, close=63_740.0),)))
    assert result is None


# ============================================================================
# 7. 5m trigger tests
# ============================================================================
def test_short_trigger_exact_agreement_boundary_passes():
    result = detect_compression_breakout(build_valid_short_inputs(
        consensus_5m_rows=(make_trigger_5m_row(agreement=BREAKOUT_MIN_AGREEMENT, taker=-1000.0),)))
    assert result is not None


def test_agreement_below_threshold_no_candidate():
    result = detect_compression_breakout(build_valid_short_inputs(
        consensus_5m_rows=(make_trigger_5m_row(agreement=BREAKOUT_MIN_AGREEMENT - 1e-9),)))
    assert result is None


def test_short_positive_taker_flow_rejected():
    result = detect_compression_breakout(build_valid_short_inputs(
        consensus_5m_rows=(make_trigger_5m_row(taker=500.0),)))
    assert result is None


def test_short_zero_taker_flow_rejected():
    result = detect_compression_breakout(build_valid_short_inputs(
        consensus_5m_rows=(make_trigger_5m_row(taker=0.0),)))
    assert result is None


def test_long_negative_taker_flow_rejected():
    result = detect_compression_breakout(build_valid_long_inputs(
        consensus_5m_rows=(make_trigger_5m_row(taker=-500.0),)))
    assert result is None


def test_missing_agreement_no_candidate():
    result = detect_compression_breakout(build_valid_short_inputs(
        consensus_5m_rows=(make_trigger_5m_row(agreement=None),)))
    assert result is None


def test_missing_taker_no_candidate():
    result = detect_compression_breakout(build_valid_short_inputs(
        consensus_5m_rows=(make_trigger_5m_row(taker=None),)))
    assert result is None


def test_malformed_agreement_raises():
    with pytest.raises(V2CompressionBreakoutError):
        detect_compression_breakout(build_valid_short_inputs(
            consensus_5m_rows=(make_trigger_5m_row(agreement=1.5),)))


def test_malformed_taker_raises():
    with pytest.raises(V2CompressionBreakoutError):
        detect_compression_breakout(build_valid_short_inputs(
            consensus_5m_rows=(make_trigger_5m_row(taker=float("nan")),)))


def test_5m_trigger_quality_exact_boundaries_pass():
    result = detect_compression_breakout(build_valid_short_inputs(
        consensus_5m_rows=(make_trigger_5m_row(
            coverage=SETUP_MIN_COVERAGE, confidence=SETUP_MIN_CONFIDENCE),)))
    assert result is not None


def test_5m_trigger_quality_below_threshold_no_candidate():
    result = detect_compression_breakout(build_valid_short_inputs(
        consensus_5m_rows=(make_trigger_5m_row(coverage=SETUP_MIN_COVERAGE - 1e-9),)))
    assert result is None


def test_current_5m_trigger_row_missing_no_candidate():
    result = detect_compression_breakout(build_valid_short_inputs(consensus_5m_rows=()))
    assert result is None


def test_duplicate_trigger_row_raises():
    with pytest.raises(V2CompressionBreakoutError):
        detect_compression_breakout(build_valid_short_inputs(
            consensus_5m_rows=(make_trigger_5m_row(), make_trigger_5m_row())))


def test_5m_trigger_taker_flow_poor_alone_rejects_even_with_healthy_price_structure():
    # §6.3a required matrix: the fresh 5m trigger requires price_structure
    # AND taker_flow BOTH independently passing. price_structure healthy,
    # taker_flow below floor -- must still reject.
    result = detect_compression_breakout(build_valid_short_inputs(
        consensus_5m_rows=(make_trigger_5m_row(
            coverage=SETUP_MIN_COVERAGE, confidence=SETUP_MIN_CONFIDENCE,
            taker_coverage=SETUP_MIN_COVERAGE - 1e-9, taker_confidence=SETUP_MIN_CONFIDENCE),)))
    assert result is None


def test_5m_trigger_price_structure_poor_alone_rejects_even_with_healthy_taker_flow():
    # Symmetric case: taker_flow healthy, price_structure below floor --
    # must still reject.
    result = detect_compression_breakout(build_valid_short_inputs(
        consensus_5m_rows=(make_trigger_5m_row(
            coverage=SETUP_MIN_COVERAGE - 1e-9, confidence=SETUP_MIN_CONFIDENCE,
            taker_coverage=SETUP_MIN_COVERAGE, taker_confidence=SETUP_MIN_CONFIDENCE),)))
    assert result is None


@pytest.mark.parametrize("family", ["volume", "oi", "funding", "liquidations"])
def test_5m_trigger_other_families_cannot_suppress(family):
    # Only price_structure and taker_flow are read for the fresh 5m
    # trigger -- zeroing any other family must have zero effect.
    row = make_trigger_5m_row(coverage=SETUP_MIN_COVERAGE, confidence=SETUP_MIN_CONFIDENCE)
    coverage_by_metric = dict(row["coverage_by_metric"])
    coverage_by_metric[family] = {"available": 0, "expected": 3, "ratio": 0.0}
    row = dict(row, coverage_by_metric=coverage_by_metric)
    data_confidence_by_metric = dict(row["data_confidence_by_metric"])
    data_confidence_by_metric[family] = 0.0
    row["data_confidence_by_metric"] = data_confidence_by_metric
    result = detect_compression_breakout(build_valid_short_inputs(consensus_5m_rows=(row,)))
    assert result is not None


# ============================================================================
# 8. directional-context gate tests
# ============================================================================
def test_context_4h_non_directional_1h_neutral_accepted():
    result = detect_compression_breakout(build_valid_short_inputs(
        context=make_context(NON_DIRECTIONAL, NEUTRAL_NOT_ESTABLISHED)))
    assert result is not None


def test_context_aligned_firm_accepted():
    result = detect_compression_breakout(build_valid_short_inputs(
        context=make_context(BEARISH_TRENDING, BEARISH)))
    assert result is not None


def test_context_4h_insufficient_data_rejected():
    result = detect_compression_breakout(build_valid_short_inputs(
        context=make_context(INSUFFICIENT_DATA, NEUTRAL_NOT_ESTABLISHED, is_compressed=None)))
    assert result is None


def test_context_1h_unavailable_rejected():
    result = detect_compression_breakout(build_valid_short_inputs(
        context=make_context(NON_DIRECTIONAL, BIAS_UNAVAILABLE)))
    assert result is None


def test_context_opposite_4h_rejected():
    result = detect_compression_breakout(build_valid_short_inputs(
        context=make_context(BULLISH_TRENDING, NEUTRAL_NOT_ESTABLISHED)))
    assert result is None


def test_context_opposite_1h_rejected():
    result = detect_compression_breakout(build_valid_short_inputs(
        context=make_context(NON_DIRECTIONAL, BULLISH)))
    assert result is None


def test_directional_context_gate_is_the_real_shared_primitive():
    src = inspect.getsource(cb_module.detect_compression_breakout)
    assert "directional_context_gate(context, direction)" in src


# ============================================================================
# 9. instrument / tick_size tests
# ============================================================================
def test_instrument_wrong_exchange_raises():
    with pytest.raises(V2CompressionBreakoutError):
        detect_compression_breakout(build_valid_short_inputs(
            instrument=make_instrument(exchange="okx")))


def test_instrument_missing_no_candidate():
    result = detect_compression_breakout(build_valid_short_inputs(instrument=None))
    assert result is None


def test_instrument_tick_size_none_no_candidate():
    result = detect_compression_breakout(build_valid_short_inputs(
        instrument=make_instrument(tick_size=None)))
    assert result is None


def test_instrument_tick_size_negative_raises():
    with pytest.raises(V2CompressionBreakoutError):
        detect_compression_breakout(build_valid_short_inputs(
            instrument=make_instrument(tick_size=-0.1)))


@pytest.mark.parametrize(("tick_a", "tick_b"), [(0.10, 0.50), (1.0, 2.5)])
def test_decision_tick_size_matches_instrument_row_exactly_for_two_versions(tick_a, tick_b):
    """V2-H2c, tech-lead review 4990482334, findings 5/6: instrument tick
    A -> candidate.decision_tick_size == A, instrument tick B ->
    candidate.decision_tick_size == B."""
    candidate_a = detect_compression_breakout(
        build_valid_short_inputs(instrument=make_instrument(tick_size=tick_a)))
    candidate_b = detect_compression_breakout(
        build_valid_short_inputs(instrument=make_instrument(tick_size=tick_b)))
    assert candidate_a.decision_tick_size == tick_a
    assert candidate_b.decision_tick_size == tick_b
    assert candidate_a.protection_buffer >= MIN_TICK_BUFFER_TICKS * tick_a
    assert candidate_b.protection_buffer >= MIN_TICK_BUFFER_TICKS * tick_b


# ============================================================================
# 10. worked vectors
# ============================================================================
def test_worked_short_vector_matches_frozen_formula_not_contract_prose_approximation():
    result = detect_compression_breakout(build_valid_short_inputs())
    assert result is not None
    assert result.direction == SHORT
    assert result.compression_start_bucket == RUN_START
    assert result.compression_end_bucket == RUN_END
    assert result.compression_length == 7
    assert result.range_low == 63_800.0
    assert result.range_high == 64_100.0
    assert result.previous_5m_close == 63_820.0
    assert result.breakout_close == 63_740.0
    assert result.price_direction_agreement == 0.8
    assert result.taker_delta_notional_usd_sum == -1000.0
    # proxy = mean(range_width_pct_median) over the final 14 buckets = 0.3
    assert result.range_proxy_pct == pytest.approx(0.3)
    # buffer = max(3*0.1, 64000 * 0.3/100 * 0.5) = max(0.3, 96.0) = 96.0
    assert result.protection_buffer == pytest.approx(96.0)
    # entry zone = [range_low - buffer, range_low]
    assert result.entry_zone_lower == pytest.approx(63_800.0 - 96.0)
    assert result.entry_zone_upper == pytest.approx(63_800.0)
    # frozen formula: SHORT invalidation_price = range_high + buffer
    # (NOT range_low + buffer -- the §29.6 prose's own ~63,930 illustration
    # uses range_low as its base, which conflicts with the frozen formula
    # stated earlier in the same section; the frozen formula wins).
    assert result.invalidation_price == pytest.approx(64_100.0 + 96.0)
    assert result.structural_anchor == RUN_START


def test_worked_long_vector_is_symmetric():
    result = detect_compression_breakout(build_valid_long_inputs())
    assert result is not None
    assert result.direction == LONG
    assert result.range_low == 63_800.0
    assert result.range_high == 64_100.0
    assert result.previous_5m_close == 64_090.0
    assert result.breakout_close == 64_110.0
    proxy = result.range_proxy_pct
    buffer = result.protection_buffer
    assert result.entry_zone_lower == pytest.approx(64_100.0)
    assert result.entry_zone_upper == pytest.approx(64_100.0 + buffer)
    assert result.invalidation_price == pytest.approx(63_800.0 - buffer)


def test_entry_zone_and_invalidation_never_use_breakout_close():
    result = detect_compression_breakout(build_valid_short_inputs())
    assert result.breakout_close not in (result.entry_zone_lower, result.entry_zone_upper)
    assert result.invalidation_price != result.breakout_close


# ============================================================================
# 11. V2CompressionBreakoutCandidate direct-construction self-validation
# ============================================================================
def _valid_candidate_kwargs(**over):
    base = dict(
        T=T, direction=SHORT, bucket_5m=B5, bucket_15m=B15,
        previous_5m_close=63_820.0, breakout_close=63_740.0,
        compression_start_bucket=RUN_START, compression_end_bucket=RUN_END,
        compression_length=7, range_high=RANGE_HIGH, range_low=RANGE_LOW,
        range_proxy_pct=0.3, protection_buffer=96.0, decision_tick_size=0.1,
        entry_zone_lower=RANGE_LOW - 96.0, entry_zone_upper=RANGE_LOW,
        invalidation_price=RANGE_HIGH + 96.0,
        price_direction_agreement=0.8, taker_delta_notional_usd_sum=-1000.0,
        setup_strength=0.5, data_confidence=0.5,
    )
    base.update(over)
    return base


def test_valid_candidate_constructs():
    c = V2CompressionBreakoutCandidate(**_valid_candidate_kwargs())
    assert c.structural_anchor == RUN_START


def test_candidate_rejects_wrong_direction():
    with pytest.raises(V2CompressionBreakoutError):
        V2CompressionBreakoutCandidate(**_valid_candidate_kwargs(direction="UP"))


def test_candidate_rejects_bad_T():
    with pytest.raises(V2CompressionBreakoutError):
        V2CompressionBreakoutCandidate(**_valid_candidate_kwargs(
            T=datetime(2024, 1, 1, 12, 20)))  # naive


def test_candidate_rejects_wrong_bucket_5m():
    with pytest.raises(V2CompressionBreakoutError):
        V2CompressionBreakoutCandidate(**_valid_candidate_kwargs(bucket_5m=B5 - FIVE))


def test_candidate_rejects_wrong_bucket_15m():
    with pytest.raises(V2CompressionBreakoutError):
        V2CompressionBreakoutCandidate(**_valid_candidate_kwargs(bucket_15m=B15 - FIFTEEN))


def test_candidate_rejects_invalid_compression_timestamps():
    with pytest.raises(V2CompressionBreakoutError):
        V2CompressionBreakoutCandidate(**_valid_candidate_kwargs(
            compression_start_bucket=RUN_START + timedelta(minutes=1)))  # not 15m aligned


def test_candidate_rejects_start_after_end():
    with pytest.raises(V2CompressionBreakoutError):
        V2CompressionBreakoutCandidate(**_valid_candidate_kwargs(
            compression_start_bucket=RUN_END, compression_end_bucket=RUN_START))


def test_candidate_rejects_length_inconsistent_with_grid():
    with pytest.raises(V2CompressionBreakoutError):
        V2CompressionBreakoutCandidate(**_valid_candidate_kwargs(compression_length=8))


def test_candidate_rejects_length_below_minimum():
    with pytest.raises(V2CompressionBreakoutError):
        V2CompressionBreakoutCandidate(**_valid_candidate_kwargs(
            compression_start_bucket=LOOKBACK_GRID[12], compression_end_bucket=RUN_END,
            compression_length=4))


def test_candidate_rejects_range_low_above_high():
    with pytest.raises(V2CompressionBreakoutError):
        V2CompressionBreakoutCandidate(**_valid_candidate_kwargs(
            range_low=RANGE_HIGH + 1, range_high=RANGE_LOW))


def test_candidate_rejects_nan_prices():
    with pytest.raises(V2CompressionBreakoutError):
        V2CompressionBreakoutCandidate(**_valid_candidate_kwargs(range_high=float("nan")))


def test_candidate_rejects_nonpositive_buffer():
    with pytest.raises(V2CompressionBreakoutError):
        V2CompressionBreakoutCandidate(**_valid_candidate_kwargs(protection_buffer=0.0))


@pytest.mark.parametrize("bad_tick", [0, 0.0, -0.1, float("nan"), float("inf"), True])
def test_candidate_rejects_malformed_decision_tick_size(bad_tick):
    with pytest.raises(V2CompressionBreakoutError):
        V2CompressionBreakoutCandidate(**_valid_candidate_kwargs(decision_tick_size=bad_tick))


def test_candidate_rejects_protection_buffer_inconsistent_with_decision_tick_size():
    with pytest.raises(V2CompressionBreakoutError, match="inconsistent with decision_tick_size"):
        V2CompressionBreakoutCandidate(**_valid_candidate_kwargs(decision_tick_size=1000.0))


def test_candidate_rejects_agreement_below_threshold():
    with pytest.raises(V2CompressionBreakoutError):
        V2CompressionBreakoutCandidate(**_valid_candidate_kwargs(
            price_direction_agreement=BREAKOUT_MIN_AGREEMENT - 0.01))


def test_candidate_rejects_wrong_taker_sign_for_short():
    with pytest.raises(V2CompressionBreakoutError):
        V2CompressionBreakoutCandidate(**_valid_candidate_kwargs(taker_delta_notional_usd_sum=100.0))


def test_candidate_rejects_wrong_taker_sign_for_long():
    long_kwargs = dict(
        direction=LONG, previous_5m_close=64_090.0, breakout_close=64_110.0,
        entry_zone_lower=RANGE_HIGH, entry_zone_upper=RANGE_HIGH + 96.0,
        invalidation_price=RANGE_LOW - 96.0, taker_delta_notional_usd_sum=-100.0,
    )
    with pytest.raises(V2CompressionBreakoutError):
        V2CompressionBreakoutCandidate(**_valid_candidate_kwargs(**long_kwargs))


def test_candidate_rejects_entry_zone_inconsistent_with_range_and_buffer():
    with pytest.raises(V2CompressionBreakoutError):
        V2CompressionBreakoutCandidate(**_valid_candidate_kwargs(entry_zone_lower=RANGE_LOW - 50.0))


def test_candidate_rejects_invalidation_on_wrong_side():
    with pytest.raises(V2CompressionBreakoutError):
        V2CompressionBreakoutCandidate(**_valid_candidate_kwargs(invalidation_price=RANGE_LOW - 1.0))


def test_candidate_rejects_fresh_cross_invariant_violation():
    with pytest.raises(V2CompressionBreakoutError):
        V2CompressionBreakoutCandidate(**_valid_candidate_kwargs(breakout_close=RANGE_LOW + 10.0))


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), -0.001, 1.001, True, "0.5"])
def test_candidate_rejects_malformed_setup_strength(bad):
    with pytest.raises(V2CompressionBreakoutError):
        V2CompressionBreakoutCandidate(**_valid_candidate_kwargs(setup_strength=bad))


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), -0.001, 1.001, True, "0.5"])
def test_candidate_rejects_malformed_data_confidence(bad):
    with pytest.raises(V2CompressionBreakoutError):
        V2CompressionBreakoutCandidate(**_valid_candidate_kwargs(data_confidence=bad))


def test_candidate_accepts_setup_strength_and_data_confidence_at_domain_boundaries():
    c = V2CompressionBreakoutCandidate(**_valid_candidate_kwargs(
        setup_strength=0.0, data_confidence=0.0))
    assert c.setup_strength == 0.0
    assert c.data_confidence == 0.0
    c = V2CompressionBreakoutCandidate(**_valid_candidate_kwargs(
        setup_strength=1.0, data_confidence=1.0))
    assert c.setup_strength == 1.0
    assert c.data_confidence == 1.0


def test_candidate_is_frozen():
    c = V2CompressionBreakoutCandidate(**_valid_candidate_kwargs())
    with pytest.raises(Exception):
        c.direction = LONG


# ============================================================================
# 12. frozen family constants
# ============================================================================
def test_frozen_family_constants():
    assert COMPRESSION_LOOKBACK == 16
    assert COMPRESSION_MIN_DURATION == 6
    assert COMPRESSION_THRESHOLD == 0.75
    assert COMPRESSION_PERCENTILE_WINDOW == "30d"
    assert BREAKOUT_MIN_AGREEMENT == pytest.approx(2.0 / 3.0)
    assert COMPRESSION_CONFIRMATION_MAX_AGE_5M_BUCKETS == 3
    assert EXPECTED_HORIZON == timedelta(minutes=90)


# ============================================================================
# 13. STAGE 5/6 BOUNDARY — no episode/lifecycle/persistence logic anywhere
# ============================================================================
def _executable_body_source(module) -> str:
    tree = ast.parse(inspect.getsource(module))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)):
                node.body = node.body[1:] or [ast.Pass()]
    return ast.unparse(tree)


def test_no_stage6_lifecycle_logic_implemented_yet():
    body_src = _executable_body_source(cb_module)
    forbidden = (
        "EARLY_SIGNAL", "CONFIRMED", "WEAKENING", "INVALIDATED", "EXPIRED", "COMPLETED",
        "episode_id", "event_id", "persist_v2_episode_event", "active episode",
        "cooldown", "dedup", "model_confidence",
    )
    for token in forbidden:
        assert token not in body_src, f"forbidden Stage 6 token found: {token!r}"


def test_no_false_break_or_hold_lifecycle_evaluated():
    src = inspect.getsource(cb_module.detect_compression_breakout)
    # The frozen family metadata constants are exposed at module scope,
    # never counted/evaluated inside the detector function itself.
    assert "COMPRESSION_CONFIRMATION_MAX_AGE_5M_BUCKETS" not in src
    assert "EXPECTED_HORIZON" not in src


def test_no_trend_pullback_or_confirmed_breakout_called():
    body_src = _executable_body_source(cb_module)
    forbidden = ("detect_trend_pullback", "detect_confirmed_breakout", "resistance_level",
                "support_level", "trend_leg_extreme")
    for token in forbidden:
        assert token not in body_src, f"forbidden other-family token found: {token!r}"


# ============================================================================
# 14. PURITY
# ============================================================================
def test_module_has_no_clock_random_uuid_network_filesystem_access():
    body_src = _executable_body_source(cb_module)
    forbidden = (
        "datetime.now(", "datetime.utcnow(", "time.time(", "time.monotonic(",
        "import random", "import uuid", "import yaml", "os.environ", "os.getenv",
        "requests.", "httpx.", "open(", "asyncpg", "subprocess",
    )
    for token in forbidden:
        assert token not in body_src, f"forbidden token found: {token!r}"


def test_module_imports_nothing_from_storage_runtime_main_notifications():
    tree = ast.parse(inspect.getsource(cb_module))
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        for name in names:
            for banned in ("storage", "runtime", "main", "notifications"):
                assert not name.startswith(banned), f"forbidden import: {name}"


def test_detect_compression_breakout_is_synchronous():
    assert not inspect.iscoroutinefunction(detect_compression_breakout)


def test_same_inputs_yield_same_result():
    inputs = build_valid_short_inputs()
    r1 = detect_compression_breakout(inputs)
    r2 = detect_compression_breakout(inputs)
    assert r1 == r2
