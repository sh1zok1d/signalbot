"""Tests for analytics/forecasting_v2/confirmed_breakout.py (Stage 5 —
Setup Detectors, PR 4 of ~4, FINAL planned Stage 5 detector PR). No DB,
no async — pure detection over hand-built `V2ConfirmedBreakoutInputs`/
`V2ContextSnapshot` fixtures, following the existing V2 analytics test
style (tests/analytics/test_forecasting_v2_compression_breakout.py).

Exercises: the 5m decision clock (every legal 5m boundary, no 1h-boundary
restriction); the exact `LEVEL_LOOKBACK=48`-bucket 1h structural lookback
and its all-or-nothing availability rule; the deterministic latest-tie
resistance/support anchor selection via the real `select_extreme_anchor()`;
the fresh 5m-crossing check; the shared `directional_context_gate()`;
entry-zone/invalidation formulas; the load-bearing family difference from
`COMPRESSION_BREAKOUT` (no taker-flow gate, no invented agreement
threshold, no current-B5 5m consensus read at all); `V2ConfirmedBreakout
Candidate` self-validation; and the Stage 5/6 boundary."""
from __future__ import annotations

import ast
import inspect
from datetime import datetime, timedelta, timezone

import pytest

from analytics.forecasting_v2 import confirmed_breakout as cb_module
from analytics.forecasting_v2.bias_1h import (
    BEARISH, BIAS_UNAVAILABLE, BULLISH, NEUTRAL_NOT_ESTABLISHED, V2BiasResult,
)
from analytics.forecasting_v2.context_snapshot import V2ContextSnapshot
from analytics.forecasting_v2.events import LONG, SHORT
from analytics.forecasting_v2.alignment import selected_bucket
from analytics.forecasting_v2.regime_4h import (
    BEARISH_TRENDING, BULLISH_TRENDING, INSUFFICIENT_DATA, NON_DIRECTIONAL, V2RegimeResult,
)
from analytics.forecasting_v2.setup_common import RANGE_PROXY_N, SETUP_MIN_CONFIDENCE, SETUP_MIN_COVERAGE
from analytics.forecasting_v2.confirmed_breakout import (
    CONFIRMED_BREAKOUT_CONFIRMATION_MAX_AGE_5M_BUCKETS,
    EXPECTED_HORIZON,
    LEVEL_LOOKBACK,
    V2ConfirmedBreakoutCandidate,
    V2ConfirmedBreakoutError,
    V2ConfirmedBreakoutInputs,
    detect_confirmed_breakout,
)

UTC = timezone.utc
H16 = "a" * 16
SYMBOL = "BTCUSDT"
MARKET_TYPE = "perp"

T = datetime(2024, 1, 1, 13, 5, tzinfo=UTC)  # legal 5m boundary, NOT a 1h boundary
B5 = selected_bucket("5m", T)
B1H = selected_bucket("1h", T)
B4H = selected_bucket("4h", T)
FIVE = timedelta(minutes=5)
ONE_HOUR = timedelta(hours=1)

LEVEL_GRID = tuple(B1H - (LEVEL_LOOKBACK - 1 - i) * ONE_HOUR for i in range(LEVEL_LOOKBACK))
RESISTANCE_BUCKET = LEVEL_GRID[-3]
SUPPORT_BUCKET = LEVEL_GRID[0]
RESISTANCE_LEVEL = 66_200.0
SUPPORT_LEVEL = 65_000.0
BASELINE_HIGH = 65_900.0
BASELINE_LOW = 65_700.0
BASELINE_CLOSE = 65_800.0


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


def make_context(regime=NON_DIRECTIONAL, bias=NEUTRAL_NOT_ESTABLISHED, *, t=T, b4h=None, b1h=None,
                 is_compressed=None) -> V2ContextSnapshot:
    if b4h is None:
        b4h = selected_bucket("4h", t)
    if b1h is None:
        b1h = selected_bucket("1h", t)
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


def make_consensus_1h_row(bucket_ts, *, coverage=0.9, confidence=80.0, range_width=0.5, **over):
    coverage_by_metric = {
        family: {
            "available": 3, "expected": 3,
            "ratio": (coverage if family == "price_structure" else 1.0),
        }
        for family in _FAMILIES
    }
    data_confidence_by_metric = {
        family: (confidence if family == "price_structure" else 100.0) for family in _FAMILIES
    }
    base = dict(
        symbol=SYMBOL, market_type=MARKET_TYPE, timeframe="1h",
        calculation_version=H16, feature_schema_version=1, bucket_ts=bucket_ts,
        min_coverage_ratio=coverage, consensus_confidence=confidence,
        range_width_pct_median=range_width,
        coverage_by_metric=coverage_by_metric,
        data_confidence_by_metric=data_confidence_by_metric,
    )
    base.update(over)
    return base


def make_reference_1h_row(bucket_ts, *, close=BASELINE_CLOSE, bars_expected=60, bars_present=60,
                          is_usable=True, has_gap=False, **over):
    base = dict(
        exchange="binance", symbol=SYMBOL, market_type=MARKET_TYPE, timeframe="1h",
        calculation_version=H16, feature_schema_version=1, bucket_ts=bucket_ts,
        is_usable=is_usable, has_gap=has_gap, bars_present=bars_present,
        bars_expected=bars_expected, close_price=close,
    )
    base.update(over)
    return base


def make_reference_5m_row(bucket_ts, *, close=BASELINE_CLOSE, bars_expected=5, bars_present=5,
                          is_usable=True, has_gap=False, **over):
    base = dict(
        exchange="binance", symbol=SYMBOL, market_type=MARKET_TYPE, timeframe="5m",
        calculation_version=H16, feature_schema_version=1, bucket_ts=bucket_ts,
        is_usable=is_usable, has_gap=has_gap, bars_present=bars_present,
        bars_expected=bars_expected, close_price=close,
    )
    base.update(over)
    return base


def make_instrument(tick_size=0.1, **over):
    base = dict(exchange="binance", symbol=SYMBOL, market_type=MARKET_TYPE, tick_size=tick_size)
    base.update(over)
    return base


def build_proxy_rows(*, b1h=B1H, coverage=0.9, confidence=80.0, range_width=0.5):
    start = b1h - (RANGE_PROXY_N - 1) * ONE_HOUR
    return tuple(
        make_consensus_1h_row(start + i * ONE_HOUR, coverage=coverage, confidence=confidence,
                              range_width=range_width)
        for i in range(RANGE_PROXY_N))


def build_structural_rows(*, buckets=LEVEL_GRID, resistance_bucket=RESISTANCE_BUCKET,
                          resistance_value=RESISTANCE_LEVEL, support_bucket=SUPPORT_BUCKET,
                          support_value=SUPPORT_LEVEL, baseline_high=BASELINE_HIGH,
                          baseline_low=BASELINE_LOW, extra_ties=()):
    """`extra_ties`: iterable of (bucket, "high"|"low", value) additional
    single-minute extrema to embed, for tie-break tests."""
    reference_1h_rows = []
    raw_1m_rows = []
    tie_map = {}
    for b, kind, value in extra_ties:
        tie_map.setdefault(b, {})[kind] = value
    for b in buckets:
        reference_1h_rows.append(make_reference_1h_row(b))
        for m in range(60):
            ts = b + timedelta(minutes=m)
            high = baseline_high
            low = baseline_low
            if b == resistance_bucket and m == 0:
                high = resistance_value
            if b == support_bucket and m == 0:
                low = support_value
            if b in tie_map and m == 0:
                high = tie_map[b].get("high", high)
                low = tie_map[b].get("low", low)
            raw_1m_rows.append({"exchange": "binance", "symbol": SYMBOL, "ts": ts,
                               "high": high, "low": low})
    return tuple(reference_1h_rows), tuple(raw_1m_rows)


def build_valid_long_inputs(**overrides):
    reference_1h_rows, raw_1m_rows = build_structural_rows()
    kwargs = dict(
        context=make_context(),
        consensus_1h_rows=build_proxy_rows(),
        reference_1h_rows=reference_1h_rows,
        reference_1m_rows=raw_1m_rows,
        reference_5m_rows=(
            make_reference_5m_row(B5 - FIVE, close=66_180.0),
            make_reference_5m_row(B5, close=66_240.0),
        ),
        instrument=make_instrument(),
    )
    kwargs.update(overrides)
    return V2ConfirmedBreakoutInputs(**kwargs)


def build_valid_short_inputs(**overrides):
    reference_1h_rows, raw_1m_rows = build_structural_rows()
    kwargs = dict(
        context=make_context(),
        consensus_1h_rows=build_proxy_rows(),
        reference_1h_rows=reference_1h_rows,
        reference_1m_rows=raw_1m_rows,
        reference_5m_rows=(
            make_reference_5m_row(B5 - FIVE, close=65_020.0),
            make_reference_5m_row(B5, close=64_980.0),
        ),
        instrument=make_instrument(),
    )
    kwargs.update(overrides)
    return V2ConfirmedBreakoutInputs(**kwargs)


# ============================================================================
# 1. decision clock — every legal 5m boundary, no 1h-boundary restriction
# ============================================================================
def test_qualifies_at_a_non_1h_boundary():
    result = detect_confirmed_breakout(build_valid_long_inputs())
    assert result is not None
    assert result.T == T
    assert result.bucket_5m == B5
    assert result.bucket_1h == B1H


def test_exact_1h_boundary_coherent_data_cannot_fresh_cross_own_b1h_extreme():
    # T=13:00 -- a legal 1h boundary too. B1h=[12:00,13:00), B5=[12:55,13:00)
    # is CONTAINED inside B1h. The structural level is max/min over ALL
    # 48 buckets INCLUDING B1h itself -- it does NOT matter that a
    # winning anchor bucket happens to be older; B1h's own raw high/low
    # still PARTICIPATES in that max()/min(). So if a 5m close of 66,240
    # legitimately occurred within B1h's own window, B1h's own raw high
    # must physically be >=66,240 too, which means resistance_level (a
    # max over a set that includes B1h) must ALSO be >=66,240 -- the same
    # close can therefore never satisfy `current_close > resistance_level`.
    # A physically coherent fresh LONG breakout at the exact 1h boundary
    # is structurally impossible; this follows from the frozen §7.3
    # formula itself, not from any executable 1h-boundary special-case
    # (there is none -- see test_detector_still_processes_and_validates_
    # at_exact_1h_boundary_not_skipped below).
    t2 = datetime(2024, 1, 1, 13, 0, tzinfo=UTC)
    b5_t2 = selected_bucket("5m", t2)   # 12:55
    assert selected_bucket("1h", t2) == B1H
    # Make the vector coherent: B1h's own raw high >= the current 5m close.
    reference_1h_rows, raw_1m_rows = build_structural_rows(
        resistance_bucket=B1H, resistance_value=66_240.0)
    context = make_context(t=t2)
    result = detect_confirmed_breakout(build_valid_long_inputs(
        context=context,
        reference_1h_rows=reference_1h_rows, reference_1m_rows=raw_1m_rows,
        reference_5m_rows=(
            make_reference_5m_row(b5_t2 - FIVE, close=66_180.0),
            make_reference_5m_row(b5_t2, close=66_240.0),
        )))
    assert result is None


def test_exact_1h_boundary_coherent_data_cannot_fresh_cross_own_b1h_extreme_short():
    # Symmetric SHORT case: a 5m close of 64,980 occurring within B1h's
    # own window means B1h's own raw low must physically be <=64,980,
    # which forces support_level <=64,980 too -- the same close can
    # never satisfy `current_close < support_level` either.
    t2 = datetime(2024, 1, 1, 13, 0, tzinfo=UTC)
    b5_t2 = selected_bucket("5m", t2)
    reference_1h_rows, raw_1m_rows = build_structural_rows(
        support_bucket=B1H, support_value=64_980.0)
    context = make_context(t=t2)
    result = detect_confirmed_breakout(build_valid_short_inputs(
        context=context,
        reference_1h_rows=reference_1h_rows, reference_1m_rows=raw_1m_rows,
        reference_5m_rows=(
            make_reference_5m_row(b5_t2 - FIVE, close=65_020.0),
            make_reference_5m_row(b5_t2, close=64_980.0),
        )))
    assert result is None


def test_detector_still_processes_and_validates_at_exact_1h_boundary_not_skipped():
    # Prove T=13:00 (an exact 1h boundary) is genuinely EVALUATED, not
    # silently skipped by some executable "if bucket_1h + 1h == T: return
    # None" special-case: inject a malformed structural row and confirm
    # detect_confirmed_breakout() still raises. A skip-branch would have
    # returned None before ever reaching (and rejecting) this row --
    # "evaluated at every legal T" is not the same claim as "capable of
    # qualifying on every legal T" (module docstring).
    t2 = datetime(2024, 1, 1, 13, 0, tzinfo=UTC)
    b5_t2 = selected_bucket("5m", t2)
    reference_1h_rows, raw_1m_rows = build_structural_rows()
    reference_1h_rows = tuple(
        {**r, "bars_expected": 59, "bars_present": 59} if r["bucket_ts"] == LEVEL_GRID[10] else r
        for r in reference_1h_rows)
    context = make_context(t=t2)
    with pytest.raises(V2ConfirmedBreakoutError):
        detect_confirmed_breakout(build_valid_long_inputs(
            context=context, reference_1h_rows=reference_1h_rows, reference_1m_rows=raw_1m_rows,
            reference_5m_rows=(
                make_reference_5m_row(b5_t2 - FIVE, close=66_180.0),
                make_reference_5m_row(b5_t2, close=66_240.0),
            )))


def test_physically_coherent_vector_inside_b1h_cannot_cross_its_own_extrema():
    # If the resistance anchor IS B1h itself, a 5m close strictly inside
    # B1h's own window cannot legitimately exceed B1h's own raw high --
    # this hand-built vector (deliberately setting resistance = B1h's own
    # high, then trying to "cross" it from within B1h) should NOT create
    # a fresh breakout once the vector is physically coherent (current
    # close capped at the same high used to derive the level).
    reference_1h_rows, raw_1m_rows = build_structural_rows(
        resistance_bucket=B1H, resistance_value=RESISTANCE_LEVEL)
    t2 = datetime(2024, 1, 1, 13, 0, tzinfo=UTC)
    b5_t2 = selected_bucket("5m", t2)
    context = make_context(t=t2)
    result = detect_confirmed_breakout(build_valid_long_inputs(
        context=context,
        reference_1h_rows=reference_1h_rows, reference_1m_rows=raw_1m_rows,
        reference_5m_rows=(
            make_reference_5m_row(b5_t2 - FIVE, close=RESISTANCE_LEVEL - 20.0),
            make_reference_5m_row(b5_t2, close=RESISTANCE_LEVEL),  # equality, not a fresh cross
        )))
    assert result is None


def test_wrong_inputs_type_raises():
    with pytest.raises(V2ConfirmedBreakoutError):
        detect_confirmed_breakout("not inputs")


def test_wrong_context_type_raises():
    inputs = build_valid_long_inputs()
    bad = V2ConfirmedBreakoutInputs(
        context="not a context", consensus_1h_rows=inputs.consensus_1h_rows,
        reference_1h_rows=inputs.reference_1h_rows, reference_1m_rows=inputs.reference_1m_rows,
        reference_5m_rows=inputs.reference_5m_rows, instrument=inputs.instrument)
    with pytest.raises(V2ConfirmedBreakoutError):
        detect_confirmed_breakout(bad)


# ============================================================================
# 2. structural lookback tests (A-G)
# ============================================================================
def test_exact_48_complete_buckets_computable():
    result = detect_confirmed_breakout(build_valid_long_inputs())
    assert result is not None
    assert result.level_price == RESISTANCE_LEVEL


def test_47_of_48_structural_reference_features_returns_none():
    reference_1h_rows, raw_1m_rows = build_structural_rows()
    reference_1h_rows = tuple(r for r in reference_1h_rows if r["bucket_ts"] != LEVEL_GRID[5])
    result = detect_confirmed_breakout(build_valid_long_inputs(
        reference_1h_rows=reference_1h_rows, reference_1m_rows=raw_1m_rows))
    assert result is None


def test_one_structural_bucket_unavailable_returns_none():
    reference_1h_rows, raw_1m_rows = build_structural_rows()
    reference_1h_rows = tuple(
        {**r, "is_usable": False} if r["bucket_ts"] == LEVEL_GRID[10] else r
        for r in reference_1h_rows)
    result = detect_confirmed_breakout(build_valid_long_inputs(
        reference_1h_rows=reference_1h_rows, reference_1m_rows=raw_1m_rows))
    assert result is None


def test_bars_expected_59_raises():
    reference_1h_rows, raw_1m_rows = build_structural_rows()
    reference_1h_rows = tuple(
        {**r, "bars_expected": 59, "bars_present": 59} if r["bucket_ts"] == LEVEL_GRID[10] else r
        for r in reference_1h_rows)
    with pytest.raises(V2ConfirmedBreakoutError):
        detect_confirmed_breakout(build_valid_long_inputs(
            reference_1h_rows=reference_1h_rows, reference_1m_rows=raw_1m_rows))


def test_bars_present_59_of_60_unusable_returns_none():
    reference_1h_rows, raw_1m_rows = build_structural_rows()
    reference_1h_rows = tuple(
        {**r, "bars_present": 59, "is_usable": False} if r["bucket_ts"] == LEVEL_GRID[10] else r
        for r in reference_1h_rows)
    result = detect_confirmed_breakout(build_valid_long_inputs(
        reference_1h_rows=reference_1h_rows, reference_1m_rows=raw_1m_rows))
    assert result is None


def test_feature_claims_full_60_but_raw_bar_missing_raises_wrapping_alignederror():
    reference_1h_rows, raw_1m_rows = build_structural_rows()
    raw_1m_rows = tuple(r for r in raw_1m_rows if not (r["ts"] == LEVEL_GRID[10]))
    with pytest.raises(V2ConfirmedBreakoutError):
        detect_confirmed_breakout(build_valid_long_inputs(
            reference_1h_rows=reference_1h_rows, reference_1m_rows=raw_1m_rows))


def test_duplicate_raw_bar_raises():
    reference_1h_rows, raw_1m_rows = build_structural_rows()
    dup = raw_1m_rows[0]
    with pytest.raises(V2ConfirmedBreakoutError):
        detect_confirmed_breakout(build_valid_long_inputs(
            reference_1h_rows=reference_1h_rows, reference_1m_rows=raw_1m_rows + (dup,)))


def test_raw_bar_out_of_window_raises():
    reference_1h_rows, raw_1m_rows = build_structural_rows()
    outside = {"exchange": "binance", "symbol": SYMBOL,
              "ts": LEVEL_GRID[0] - timedelta(minutes=1), "high": 1.0, "low": 1.0}
    with pytest.raises(V2ConfirmedBreakoutError):
        detect_confirmed_breakout(build_valid_long_inputs(
            reference_1h_rows=reference_1h_rows, reference_1m_rows=raw_1m_rows + (outside,)))


# ============================================================================
# 3. extreme / tie-break tests
# ============================================================================
def test_resistance_from_raw_high_support_from_raw_low_not_feature_close():
    result = detect_confirmed_breakout(build_valid_long_inputs())
    assert result is not None
    assert result.level_price == RESISTANCE_LEVEL
    assert result.level_price != BASELINE_CLOSE


def test_resistance_tie_latest_bucket_wins():
    older_tie_bucket = LEVEL_GRID[5]
    # LEVEL_GRID[47] == B1H -- the newest possible bucket in the 48-grid,
    # guaranteed newer than the baseline RESISTANCE_BUCKET (index 45) so
    # the tie-break winner is unambiguous regardless of the baseline tie.
    newest_tie_bucket = LEVEL_GRID[47]
    reference_1h_rows, raw_1m_rows = build_structural_rows(
        extra_ties=((older_tie_bucket, "high", RESISTANCE_LEVEL),
                   (newest_tie_bucket, "high", RESISTANCE_LEVEL)))
    result = detect_confirmed_breakout(build_valid_long_inputs(
        reference_1h_rows=reference_1h_rows, reference_1m_rows=raw_1m_rows))
    assert result is not None
    assert result.level_price == RESISTANCE_LEVEL
    # the newest of ALL tied buckets (including the baseline RESISTANCE_BUCKET
    # and both extra ties) must win.
    assert result.level_anchor_bucket == newest_tie_bucket


def test_support_tie_latest_bucket_wins():
    older_tie_bucket = LEVEL_GRID[3]
    newest_tie_bucket = LEVEL_GRID[47]  # B1H -- guaranteed the newest bucket
    reference_1h_rows, raw_1m_rows = build_structural_rows(
        extra_ties=((older_tie_bucket, "low", SUPPORT_LEVEL),
                   (newest_tie_bucket, "low", SUPPORT_LEVEL)))
    result = detect_confirmed_breakout(build_valid_short_inputs(
        reference_1h_rows=reference_1h_rows, reference_1m_rows=raw_1m_rows))
    assert result is not None
    assert result.level_price == SUPPORT_LEVEL
    assert result.level_anchor_bucket == newest_tie_bucket


def test_tie_break_input_order_does_not_affect_result():
    reference_1h_rows, raw_1m_rows = build_structural_rows(
        extra_ties=((LEVEL_GRID[5], "high", RESISTANCE_LEVEL),
                   (LEVEL_GRID[20], "high", RESISTANCE_LEVEL)))
    result_forward = detect_confirmed_breakout(build_valid_long_inputs(
        reference_1h_rows=reference_1h_rows, reference_1m_rows=raw_1m_rows))
    result_reversed = detect_confirmed_breakout(build_valid_long_inputs(
        reference_1h_rows=tuple(reversed(reference_1h_rows)),
        reference_1m_rows=tuple(reversed(raw_1m_rows))))
    assert result_forward.level_anchor_bucket == result_reversed.level_anchor_bucket
    assert result_forward.level_price == result_reversed.level_price


# ============================================================================
# 4. valid LONG / SHORT worked vectors
# ============================================================================
def test_worked_long_vector():
    result = detect_confirmed_breakout(build_valid_long_inputs())
    assert result is not None
    assert result.direction == LONG
    assert result.level_price == 66_200.0
    assert result.level_anchor_bucket == RESISTANCE_BUCKET
    assert result.previous_5m_close == 66_180.0
    assert result.breakout_close == 66_240.0
    # proxy = mean(range_width_pct_median) over 14 buckets = 0.5
    assert result.range_proxy_pct == pytest.approx(0.5)
    # buffer = max(3*0.1, 65800*0.5/100*0.5) = max(0.3, 164.5) = 164.5
    assert result.protection_buffer == pytest.approx(164.5)
    assert result.entry_zone_lower == pytest.approx(66_200.0)
    assert result.entry_zone_upper == pytest.approx(66_364.5)
    assert result.invalidation_price == pytest.approx(66_035.5)
    assert result.structural_anchor == RESISTANCE_BUCKET
    assert result.level_kind == "RESISTANCE"
    assert result.breakout_distance_beyond_level == pytest.approx(40.0)


def test_worked_short_vector_symmetric():
    result = detect_confirmed_breakout(build_valid_short_inputs())
    assert result is not None
    assert result.direction == SHORT
    assert result.level_price == 65_000.0
    assert result.level_anchor_bucket == SUPPORT_BUCKET
    assert result.previous_5m_close == 65_020.0
    assert result.breakout_close == 64_980.0
    buffer = result.protection_buffer
    assert result.entry_zone_lower == pytest.approx(65_000.0 - buffer)
    assert result.entry_zone_upper == pytest.approx(65_000.0)
    assert result.invalidation_price == pytest.approx(65_000.0 + buffer)
    assert result.level_kind == "SUPPORT"
    assert result.breakout_distance_beyond_level == pytest.approx(20.0)


def test_entry_zone_and_invalidation_never_use_breakout_close():
    result = detect_confirmed_breakout(build_valid_long_inputs())
    assert result.breakout_close not in (result.entry_zone_lower, result.entry_zone_upper)
    assert result.invalidation_price != result.breakout_close


def test_level_anchor_property_reconstructs_extreme_anchor():
    result = detect_confirmed_breakout(build_valid_long_inputs())
    assert result.level_anchor.bucket_ts == result.level_anchor_bucket
    assert result.level_anchor.value == result.level_price


# ============================================================================
# 5. fresh LONG cross tests
# ============================================================================
def test_fresh_long_cross_equality_at_previous_qualifies():
    result = detect_confirmed_breakout(build_valid_long_inputs(
        reference_5m_rows=(
            make_reference_5m_row(B5 - FIVE, close=RESISTANCE_LEVEL),
            make_reference_5m_row(B5, close=RESISTANCE_LEVEL + 10.0),
        )))
    assert result is not None


def test_fresh_long_cross_from_further_below_qualifies():
    result = detect_confirmed_breakout(build_valid_long_inputs(
        reference_5m_rows=(
            make_reference_5m_row(B5 - FIVE, close=RESISTANCE_LEVEL - 50.0),
            make_reference_5m_row(B5, close=RESISTANCE_LEVEL + 40.0),
        )))
    assert result is not None


def test_long_already_outside_not_fresh():
    result = detect_confirmed_breakout(build_valid_long_inputs(
        reference_5m_rows=(
            make_reference_5m_row(B5 - FIVE, close=RESISTANCE_LEVEL + 20.0),
            make_reference_5m_row(B5, close=RESISTANCE_LEVEL + 40.0),
        )))
    assert result is None


def test_long_current_equals_level_no_candidate():
    result = detect_confirmed_breakout(build_valid_long_inputs(
        reference_5m_rows=(
            make_reference_5m_row(B5 - FIVE, close=RESISTANCE_LEVEL - 20.0),
            make_reference_5m_row(B5, close=RESISTANCE_LEVEL),
        )))
    assert result is None


def test_long_current_below_level_no_candidate():
    result = detect_confirmed_breakout(build_valid_long_inputs(
        reference_5m_rows=(
            make_reference_5m_row(B5 - FIVE, close=RESISTANCE_LEVEL - 40.0),
            make_reference_5m_row(B5, close=RESISTANCE_LEVEL - 10.0),
        )))
    assert result is None


# ============================================================================
# 6. fresh SHORT cross tests
# ============================================================================
def test_fresh_short_cross_equality_at_previous_qualifies():
    result = detect_confirmed_breakout(build_valid_short_inputs(
        reference_5m_rows=(
            make_reference_5m_row(B5 - FIVE, close=SUPPORT_LEVEL),
            make_reference_5m_row(B5, close=SUPPORT_LEVEL - 10.0),
        )))
    assert result is not None


def test_fresh_short_cross_from_further_above_qualifies():
    result = detect_confirmed_breakout(build_valid_short_inputs(
        reference_5m_rows=(
            make_reference_5m_row(B5 - FIVE, close=SUPPORT_LEVEL + 50.0),
            make_reference_5m_row(B5, close=SUPPORT_LEVEL - 40.0),
        )))
    assert result is not None


def test_short_already_outside_not_fresh():
    result = detect_confirmed_breakout(build_valid_short_inputs(
        reference_5m_rows=(
            make_reference_5m_row(B5 - FIVE, close=SUPPORT_LEVEL - 20.0),
            make_reference_5m_row(B5, close=SUPPORT_LEVEL - 40.0),
        )))
    assert result is None


def test_short_current_equals_level_no_candidate():
    result = detect_confirmed_breakout(build_valid_short_inputs(
        reference_5m_rows=(
            make_reference_5m_row(B5 - FIVE, close=SUPPORT_LEVEL + 20.0),
            make_reference_5m_row(B5, close=SUPPORT_LEVEL),
        )))
    assert result is None


def test_previous_or_current_5m_close_missing_no_candidate():
    result = detect_confirmed_breakout(build_valid_long_inputs(
        reference_5m_rows=(make_reference_5m_row(B5, close=66_240.0),)))
    assert result is None


# ============================================================================
# 7. context tests
# ============================================================================
def test_context_4h_bullish_1h_bullish_long_accepted():
    result = detect_confirmed_breakout(build_valid_long_inputs(
        context=make_context(BULLISH_TRENDING, BULLISH)))
    assert result is not None


def test_context_neutral_long_accepted():
    result = detect_confirmed_breakout(build_valid_long_inputs(
        context=make_context(NON_DIRECTIONAL, NEUTRAL_NOT_ESTABLISHED)))
    assert result is not None


def test_context_4h_insufficient_data_rejected():
    result = detect_confirmed_breakout(build_valid_long_inputs(
        context=make_context(INSUFFICIENT_DATA, NEUTRAL_NOT_ESTABLISHED, is_compressed=None)))
    assert result is None


def test_context_1h_unavailable_rejected():
    result = detect_confirmed_breakout(build_valid_long_inputs(
        context=make_context(NON_DIRECTIONAL, BIAS_UNAVAILABLE)))
    assert result is None


def test_context_opposite_4h_rejected():
    result = detect_confirmed_breakout(build_valid_long_inputs(
        context=make_context(BEARISH_TRENDING, NEUTRAL_NOT_ESTABLISHED)))
    assert result is None


def test_context_opposite_1h_rejected():
    result = detect_confirmed_breakout(build_valid_long_inputs(
        context=make_context(NON_DIRECTIONAL, BEARISH)))
    assert result is None


def test_context_short_symmetric_accept_and_reject():
    assert detect_confirmed_breakout(build_valid_short_inputs(
        context=make_context(BEARISH_TRENDING, BEARISH))) is not None
    assert detect_confirmed_breakout(build_valid_short_inputs(
        context=make_context(BULLISH_TRENDING, NEUTRAL_NOT_ESTABLISHED))) is None
    assert detect_confirmed_breakout(build_valid_short_inputs(
        context=make_context(NON_DIRECTIONAL, BULLISH))) is None


def test_directional_context_gate_is_the_real_shared_primitive():
    src = inspect.getsource(cb_module.detect_confirmed_breakout)
    assert "directional_context_gate(context, direction)" in src


# ============================================================================
# 8. LOAD-BEARING FAMILY-DIFFERENCE REGRESSION -- no taker/agreement gate
# ============================================================================
def test_no_taker_flow_or_agreement_hard_gate_in_executable_module():
    src = _executable_body_source(cb_module)
    forbidden = (
        "taker_delta_notional_usd_sum",
        "price_direction_agreement",
        "BREAKOUT_MIN_AGREEMENT",
        "consensus_5m",
    )
    for token in forbidden:
        assert token not in src, f"forbidden #41-style token found in confirmed_breakout.py: {token!r}"


def test_candidate_has_no_taker_or_agreement_fields():
    import dataclasses
    field_names = {f.name for f in dataclasses.fields(V2ConfirmedBreakoutCandidate)}
    assert "taker_delta_notional_usd_sum" not in field_names
    assert "price_direction_agreement" not in field_names


def test_inputs_carries_no_5m_consensus_or_percentile_rows():
    import dataclasses
    field_names = {f.name for f in dataclasses.fields(V2ConfirmedBreakoutInputs)}
    assert "consensus_5m_rows" not in field_names
    assert "percentile_1h_rows" not in field_names
    assert "percentile_15m_rows" not in field_names


def test_candidate_qualifies_with_no_volume_confirmation_whatsoever():
    # A vector where a taker-flow gate (if mistakenly implemented) would
    # have rejected -- must still qualify, proving no such gate exists.
    result = detect_confirmed_breakout(build_valid_long_inputs())
    assert result is not None


# ============================================================================
# 9. current 1h quality tests
# ============================================================================
def test_current_1h_quality_exact_boundaries_pass():
    result = detect_confirmed_breakout(build_valid_long_inputs(
        consensus_1h_rows=build_proxy_rows(coverage=SETUP_MIN_COVERAGE, confidence=SETUP_MIN_CONFIDENCE)))
    assert result is not None


def test_current_1h_quality_just_below_returns_none():
    proxy_rows = list(build_proxy_rows())
    proxy_rows[-1] = make_consensus_1h_row(B1H, coverage=SETUP_MIN_COVERAGE - 1e-9)
    result = detect_confirmed_breakout(build_valid_long_inputs(consensus_1h_rows=tuple(proxy_rows)))
    assert result is None


def test_current_1h_quality_present_none_returns_none():
    proxy_rows = list(build_proxy_rows())
    proxy_rows[-1] = make_consensus_1h_row(B1H, coverage=None)
    result = detect_confirmed_breakout(build_valid_long_inputs(consensus_1h_rows=tuple(proxy_rows)))
    assert result is None


def test_current_1h_quality_malformed_raises():
    proxy_rows = list(build_proxy_rows())
    proxy_rows[-1] = make_consensus_1h_row(B1H, confidence=200.0)
    with pytest.raises(V2ConfirmedBreakoutError):
        detect_confirmed_breakout(build_valid_long_inputs(consensus_1h_rows=tuple(proxy_rows)))


def test_current_1h_row_missing_returns_none():
    proxy_rows = tuple(r for r in build_proxy_rows() if r["bucket_ts"] != B1H)
    result = detect_confirmed_breakout(build_valid_long_inputs(consensus_1h_rows=proxy_rows))
    assert result is None


@pytest.mark.parametrize("family", ["volume", "taker_flow", "oi", "funding", "liquidations"])
def test_quality_only_price_structure_family_is_read_other_families_cannot_suppress(family):
    # §6.3a required matrix: CONFIRMED_BREAKOUT's quality gate is scoped
    # to price_structure ONLY, explicitly never taker_flow. Zeroing out
    # coverage AND confidence for any non-price_structure family at the
    # current 1h bucket must have zero effect on the decision.
    proxy_rows = list(build_proxy_rows())
    current = dict(proxy_rows[-1])
    assert current["bucket_ts"] == B1H
    coverage_by_metric = dict(current["coverage_by_metric"])
    coverage_by_metric[family] = {"available": 0, "expected": 3, "ratio": 0.0}
    current["coverage_by_metric"] = coverage_by_metric
    data_confidence_by_metric = dict(current["data_confidence_by_metric"])
    data_confidence_by_metric[family] = 0.0
    current["data_confidence_by_metric"] = data_confidence_by_metric
    proxy_rows[-1] = current
    result = detect_confirmed_breakout(build_valid_long_inputs(consensus_1h_rows=tuple(proxy_rows)))
    assert result is not None


# ============================================================================
# 10. RANGE_PROXY missing-peer regression (#41 hardening carried forward)
# ============================================================================
def test_missing_non_current_range_proxy_peer_returns_none_not_keyerror():
    proxy_start = B1H - (RANGE_PROXY_N - 1) * ONE_HOUR
    proxy_rows = tuple(r for r in build_proxy_rows() if r["bucket_ts"] != proxy_start)
    result = detect_confirmed_breakout(build_valid_long_inputs(consensus_1h_rows=proxy_rows))
    assert result is None


def test_malformed_present_range_proxy_value_raises_even_with_different_missing_peer():
    # A missing peer must NEVER mask a malformed PRESENT peer elsewhere in
    # the same exact 14-bucket RANGE_PROXY window -- range_proxy_pct()
    # itself validates every PRESENT row's range_width_pct_median BEFORE
    # its own exact-grid-completeness check runs; the caller must hand it
    # every PRESENT row (filtered only by presence, never short-circuited
    # by a separate "any missing" check) so that contract actually holds.
    proxy_start = B1H - (RANGE_PROXY_N - 1) * ONE_HOUR
    corrupt_bucket = proxy_start + 5 * ONE_HOUR
    assert corrupt_bucket != proxy_start
    proxy_rows = [r for r in build_proxy_rows() if r["bucket_ts"] != proxy_start]  # drop one peer
    proxy_rows = [
        make_consensus_1h_row(r["bucket_ts"], range_width="not-a-number")
        if r["bucket_ts"] == corrupt_bucket else r
        for r in proxy_rows
    ]
    with pytest.raises(V2ConfirmedBreakoutError):
        detect_confirmed_breakout(build_valid_long_inputs(consensus_1h_rows=tuple(proxy_rows)))


def test_malformed_present_range_proxy_value_nan_raises_even_with_different_missing_peer():
    proxy_start = B1H - (RANGE_PROXY_N - 1) * ONE_HOUR
    corrupt_bucket = proxy_start + 5 * ONE_HOUR
    proxy_rows = [r for r in build_proxy_rows() if r["bucket_ts"] != proxy_start]
    proxy_rows = [
        make_consensus_1h_row(r["bucket_ts"], range_width=float("nan"))
        if r["bucket_ts"] == corrupt_bucket else r
        for r in proxy_rows
    ]
    with pytest.raises(V2ConfirmedBreakoutError):
        detect_confirmed_breakout(build_valid_long_inputs(consensus_1h_rows=tuple(proxy_rows)))


def test_malformed_present_range_proxy_value_negative_raises_even_with_different_missing_peer():
    proxy_start = B1H - (RANGE_PROXY_N - 1) * ONE_HOUR
    corrupt_bucket = proxy_start + 5 * ONE_HOUR
    proxy_rows = [r for r in build_proxy_rows() if r["bucket_ts"] != proxy_start]
    proxy_rows = [
        make_consensus_1h_row(r["bucket_ts"], range_width=-1.0)
        if r["bucket_ts"] == corrupt_bucket else r
        for r in proxy_rows
    ]
    with pytest.raises(V2ConfirmedBreakoutError):
        detect_confirmed_breakout(build_valid_long_inputs(consensus_1h_rows=tuple(proxy_rows)))


def test_malformed_current_b1h_quality_raises_even_with_missing_peer_elsewhere():
    # §39's own worked example: "malformed B1h consensus quality + missing
    # an older RANGE_PROXY peer: error, not None" -- the current-B1h
    # quality gate is validated (and raises for corruption) BEFORE the
    # separate completeness check for the OTHER 13 RANGE_PROXY peers ever
    # runs. (Only the CURRENT B1h row's coverage/confidence VALUES are
    # corruption-checked at all, per §16 -- the other 13 rows' own
    # coverage/confidence values are irrelevant to RANGE_PROXY, which
    # only reads range_width_pct_median.)
    proxy_rows = [r for r in build_proxy_rows()
                 if r["bucket_ts"] != B1H - (RANGE_PROXY_N - 1) * ONE_HOUR]  # drop oldest peer
    proxy_rows = [
        make_consensus_1h_row(r["bucket_ts"], coverage="not-a-number") if r["bucket_ts"] == B1H
        else r
        for r in proxy_rows
    ]
    with pytest.raises(V2ConfirmedBreakoutError):
        detect_confirmed_breakout(build_valid_long_inputs(consensus_1h_rows=tuple(proxy_rows)))


# ============================================================================
# 11. instrument tests
# ============================================================================
def test_instrument_none_no_candidate():
    result = detect_confirmed_breakout(build_valid_long_inputs(instrument=None))
    assert result is None


def test_instrument_tick_none_no_candidate():
    result = detect_confirmed_breakout(build_valid_long_inputs(
        instrument=make_instrument(tick_size=None)))
    assert result is None


def test_instrument_wrong_exchange_raises():
    with pytest.raises(V2ConfirmedBreakoutError):
        detect_confirmed_breakout(build_valid_long_inputs(
            instrument=make_instrument(exchange="okx")))


def test_instrument_wrong_symbol_raises():
    with pytest.raises(V2ConfirmedBreakoutError):
        detect_confirmed_breakout(build_valid_long_inputs(
            instrument=make_instrument(symbol="ETHUSDT")))


def test_instrument_tick_bool_raises():
    with pytest.raises(V2ConfirmedBreakoutError):
        detect_confirmed_breakout(build_valid_long_inputs(instrument=make_instrument(tick_size=True)))


def test_instrument_tick_nan_raises():
    with pytest.raises(V2ConfirmedBreakoutError):
        detect_confirmed_breakout(build_valid_long_inputs(
            instrument=make_instrument(tick_size=float("nan"))))


def test_instrument_tick_negative_raises():
    with pytest.raises(V2ConfirmedBreakoutError):
        detect_confirmed_breakout(build_valid_long_inputs(instrument=make_instrument(tick_size=-1.0)))


def test_instrument_tick_zero_raises():
    with pytest.raises(V2ConfirmedBreakoutError):
        detect_confirmed_breakout(build_valid_long_inputs(instrument=make_instrument(tick_size=0.0)))


# ============================================================================
# 12. protection buffer tests
# ============================================================================
def test_buffer_volatility_term_wins():
    result = detect_confirmed_breakout(build_valid_long_inputs())
    assert result is not None
    assert result.protection_buffer == pytest.approx(164.5)  # volatility term > 3*tick floor


def test_buffer_tick_floor_wins():
    proxy_rows = build_proxy_rows(range_width=0.001)  # tiny volatility -> tick floor dominates
    result = detect_confirmed_breakout(build_valid_long_inputs(
        consensus_1h_rows=proxy_rows, instrument=make_instrument(tick_size=100.0)))
    assert result is not None
    assert result.protection_buffer == pytest.approx(300.0)  # 3 * 100


def test_buffer_uses_b1h_close_not_breakout_close():
    reference_1h_rows, raw_1m_rows = build_structural_rows()
    reference_1h_rows = tuple(
        {**r, "close_price": 50_000.0} if r["bucket_ts"] == B1H else r for r in reference_1h_rows)
    result = detect_confirmed_breakout(build_valid_long_inputs(
        reference_1h_rows=reference_1h_rows, reference_1m_rows=raw_1m_rows))
    assert result is not None
    # buffer = max(0.3, 50000*0.5/100*0.5) = 125.0, not derived from 66,240 breakout close
    assert result.protection_buffer == pytest.approx(125.0)


# ============================================================================
# 13. V2ConfirmedBreakoutCandidate direct-construction self-validation
# ============================================================================
def _valid_candidate_kwargs(**over):
    breakout_close = 66_240.0
    level_price = 66_200.0
    protection_buffer = 164.5
    base = dict(
        T=T, direction=LONG, bucket_5m=B5, bucket_1h=B1H,
        previous_5m_close=66_180.0, breakout_close=breakout_close,
        level_anchor_bucket=RESISTANCE_BUCKET, level_price=level_price,
        range_proxy_pct=0.5, protection_buffer=protection_buffer,
        entry_zone_lower=level_price, entry_zone_upper=66_364.5,
        invalidation_price=66_035.5,
        # §8.3's real formula, via the module's own helper -- keeps this
        # fixture self-consistent with __post_init__'s exact-formula
        # cross-check without hand-duplicating/hardcoding the arithmetic.
        setup_strength=cb_module._confirmed_breakout_setup_strength(
            breakout_close - level_price, protection_buffer),
        data_confidence=0.5,
    )
    base.update(over)
    return base


def test_valid_candidate_constructs():
    c = V2ConfirmedBreakoutCandidate(**_valid_candidate_kwargs())
    assert c.structural_anchor == RESISTANCE_BUCKET
    assert c.level_kind == "RESISTANCE"


def test_candidate_rejects_wrong_direction():
    with pytest.raises(V2ConfirmedBreakoutError):
        V2ConfirmedBreakoutCandidate(**_valid_candidate_kwargs(direction="UP"))


def test_candidate_rejects_naive_T():
    with pytest.raises(V2ConfirmedBreakoutError):
        V2ConfirmedBreakoutCandidate(**_valid_candidate_kwargs(T=datetime(2024, 1, 1, 13, 5)))


def test_candidate_rejects_misaligned_T():
    with pytest.raises(V2ConfirmedBreakoutError):
        V2ConfirmedBreakoutCandidate(**_valid_candidate_kwargs(T=T + timedelta(minutes=1)))


def test_candidate_rejects_wrong_bucket_5m():
    with pytest.raises(V2ConfirmedBreakoutError):
        V2ConfirmedBreakoutCandidate(**_valid_candidate_kwargs(bucket_5m=B5 - FIVE))


def test_candidate_rejects_wrong_bucket_1h():
    with pytest.raises(V2ConfirmedBreakoutError):
        V2ConfirmedBreakoutCandidate(**_valid_candidate_kwargs(bucket_1h=B1H - ONE_HOUR))


def test_candidate_rejects_anchor_outside_48h():
    with pytest.raises(V2ConfirmedBreakoutError):
        V2ConfirmedBreakoutCandidate(**_valid_candidate_kwargs(
            level_anchor_bucket=LEVEL_GRID[0] - ONE_HOUR))


def test_candidate_rejects_anchor_not_1h_aligned():
    with pytest.raises(V2ConfirmedBreakoutError):
        V2ConfirmedBreakoutCandidate(**_valid_candidate_kwargs(
            level_anchor_bucket=RESISTANCE_BUCKET + timedelta(minutes=15)))


def test_candidate_rejects_nan_level_price():
    with pytest.raises(V2ConfirmedBreakoutError):
        V2ConfirmedBreakoutCandidate(**_valid_candidate_kwargs(level_price=float("nan")))


def test_candidate_rejects_inf_close():
    with pytest.raises(V2ConfirmedBreakoutError):
        V2ConfirmedBreakoutCandidate(**_valid_candidate_kwargs(breakout_close=float("inf")))


def test_candidate_rejects_nonpositive_level_price():
    with pytest.raises(V2ConfirmedBreakoutError):
        V2ConfirmedBreakoutCandidate(**_valid_candidate_kwargs(level_price=-1.0))


def test_candidate_rejects_fresh_cross_invariant_violation():
    with pytest.raises(V2ConfirmedBreakoutError):
        V2ConfirmedBreakoutCandidate(**_valid_candidate_kwargs(breakout_close=66_100.0))


def test_candidate_rejects_negative_proxy():
    with pytest.raises(V2ConfirmedBreakoutError):
        V2ConfirmedBreakoutCandidate(**_valid_candidate_kwargs(range_proxy_pct=-0.1))


def test_candidate_rejects_nonpositive_buffer():
    with pytest.raises(V2ConfirmedBreakoutError):
        V2ConfirmedBreakoutCandidate(**_valid_candidate_kwargs(protection_buffer=0.0))


def test_candidate_rejects_entry_zone_mismatch():
    with pytest.raises(V2ConfirmedBreakoutError):
        V2ConfirmedBreakoutCandidate(**_valid_candidate_kwargs(entry_zone_lower=66_150.0))


def test_candidate_rejects_invalidation_mismatch():
    with pytest.raises(V2ConfirmedBreakoutError):
        V2ConfirmedBreakoutCandidate(**_valid_candidate_kwargs(invalidation_price=66_200.0))


def test_candidate_rejects_nonpositive_invalidation():
    short_kwargs = dict(
        direction=SHORT, previous_5m_close=65_020.0, breakout_close=64_980.0,
        level_anchor_bucket=SUPPORT_BUCKET, level_price=65_000.0,
        entry_zone_lower=64_900.0, entry_zone_upper=65_000.0,
    )
    with pytest.raises(V2ConfirmedBreakoutError):
        V2ConfirmedBreakoutCandidate(**_valid_candidate_kwargs(
            **short_kwargs, invalidation_price=-1.0))


def test_candidate_short_symmetric_construction():
    c = V2ConfirmedBreakoutCandidate(
        T=T, direction=SHORT, bucket_5m=B5, bucket_1h=B1H,
        previous_5m_close=65_020.0, breakout_close=64_980.0,
        level_anchor_bucket=SUPPORT_BUCKET, level_price=65_000.0,
        range_proxy_pct=0.5, protection_buffer=100.0,
        entry_zone_lower=64_900.0, entry_zone_upper=65_000.0,
        invalidation_price=65_100.0,
        setup_strength=cb_module._confirmed_breakout_setup_strength(20.0, 100.0),
        data_confidence=0.5,
    )
    assert c.level_kind == "SUPPORT"
    assert c.breakout_distance_beyond_level == pytest.approx(20.0)


def test_candidate_rejects_setup_strength_mismatching_the_exact_formula():
    # §8.3 exact-formula cross-check (LOAD-BEARING): a setup_strength that
    # does NOT equal min(1.0, breakout_distance_beyond_level /
    # protection_buffer) for the candidate's own facts must be rejected,
    # even though it is itself a perfectly in-domain [0,1] float.
    kwargs = _valid_candidate_kwargs()
    real = cb_module._confirmed_breakout_setup_strength(
        kwargs["breakout_close"] - kwargs["level_price"], kwargs["protection_buffer"])
    kwargs["setup_strength"] = min(1.0, real + 0.2)  # in-domain but wrong
    assert kwargs["setup_strength"] != real
    with pytest.raises(V2ConfirmedBreakoutError):
        V2ConfirmedBreakoutCandidate(**kwargs)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), -0.001, 1.001, True, "0.5"])
def test_candidate_rejects_malformed_setup_strength(bad):
    kwargs = _valid_candidate_kwargs()
    kwargs["setup_strength"] = bad
    with pytest.raises(V2ConfirmedBreakoutError):
        V2ConfirmedBreakoutCandidate(**kwargs)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), -0.001, 1.001, True, "0.5"])
def test_candidate_rejects_malformed_data_confidence(bad):
    kwargs = _valid_candidate_kwargs()
    kwargs["data_confidence"] = bad
    with pytest.raises(V2ConfirmedBreakoutError):
        V2ConfirmedBreakoutCandidate(**kwargs)


def test_confirmed_breakout_setup_strength_clamps_at_one():
    # §8.3's formula: min(1.0, distance/buffer) -- a distance far beyond
    # the buffer must clamp to exactly 1.0, never exceed it.
    assert cb_module._confirmed_breakout_setup_strength(1000.0, 10.0) == 1.0


def test_confirmed_breakout_setup_strength_exact_formula_values():
    assert cb_module._confirmed_breakout_setup_strength(20.0, 100.0) == pytest.approx(0.2)
    assert cb_module._confirmed_breakout_setup_strength(100.0, 100.0) == pytest.approx(1.0)
    assert cb_module._confirmed_breakout_setup_strength(0.0, 100.0) == pytest.approx(0.0)


def test_candidate_is_frozen():
    c = V2ConfirmedBreakoutCandidate(**_valid_candidate_kwargs())
    with pytest.raises(Exception):
        c.direction = SHORT


# ============================================================================
# 14. frozen family constants
# ============================================================================
def test_frozen_family_constants():
    assert LEVEL_LOOKBACK == 48
    assert CONFIRMED_BREAKOUT_CONFIRMATION_MAX_AGE_5M_BUCKETS == 8
    assert EXPECTED_HORIZON == timedelta(minutes=150)


# ============================================================================
# 15. STAGE 5/6 BOUNDARY — no episode/lifecycle/persistence logic anywhere
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
    # NOTE: bare "CONFIRMED" is deliberately excluded from this list --
    # it is unavoidably a substring of this family's OWN frozen names
    # (`V2ConfirmedBreakoutError`, `CONFIRMED_BREAKOUT_CONFIRMATION_MAX_
    # AGE_5M_BUCKETS`), not a Stage 6 state-transition token. The other
    # five lifecycle-state tokens below never legitimately appear in this
    # family's own naming and still give strong coverage.
    body_src = _executable_body_source(cb_module)
    forbidden = (
        "EARLY_SIGNAL", "WEAKENING", "INVALIDATED", "EXPIRED", "COMPLETED",
        "episode_id", "event_id", "episode_logical_key", "persist_v2_episode_event",
        "active episode", "cooldown", "dedup", "model_confidence",
    )
    for token in forbidden:
        assert token not in body_src, f"forbidden Stage 6 token found: {token!r}"


def test_no_confirmation_deadline_counted():
    src = inspect.getsource(cb_module.detect_confirmed_breakout)
    assert "CONFIRMED_BREAKOUT_CONFIRMATION_MAX_AGE_5M_BUCKETS" not in src
    assert "EXPECTED_HORIZON" not in src


def test_no_other_setup_family_or_family_precedence_called():
    body_src = _executable_body_source(cb_module)
    forbidden = ("detect_trend_pullback", "detect_compression_breakout",
                "compression_score", "COMPRESSION_LOOKBACK")
    for token in forbidden:
        assert token not in body_src, f"forbidden other-family token found: {token!r}"


# ============================================================================
# 16. PURITY
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


def test_detect_confirmed_breakout_is_synchronous():
    assert not inspect.iscoroutinefunction(detect_confirmed_breakout)


def test_same_inputs_yield_same_result():
    inputs = build_valid_long_inputs()
    r1 = detect_confirmed_breakout(inputs)
    r2 = detect_confirmed_breakout(inputs)
    assert r1 == r2
