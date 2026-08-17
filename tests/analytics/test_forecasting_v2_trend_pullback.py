"""Tests for analytics/forecasting_v2/trend_pullback.py (Stage 5 — Setup
Detectors, PR 2 of ~4, THE FIRST actual V2 setup detector). No DB, no
async — pure detection over hand-built `V2TrendPullbackInputs`/
`V2ContextSnapshot` fixtures, following the existing V2 analytics test
style (tests/analytics/test_forecasting_v2_setup_common.py,
tests/analytics/test_forecasting_v2_context_snapshot.py).

Exercises: the strict §7.1 context precondition (4h regime AND 1h bias
must both firmly agree with the candidate direction — `directional_
context_gate` is never called); the §7 15m formation-boundary clock
(`B15 + 15m == T`, no flooring); the exact `LOOKBACK_15M=48` reference-
close window with §11's usability gate; §7.0c's tie-broken trend-leg
extreme via the real merged `select_extreme_anchor()`; the exact
retracement formulas and inclusive `[0.5,3.0] * RANGE_PROXY_pct` band;
the §23 anchor->B15 pullback-extreme span (never the full 48-bucket
extreme); the shared `range_proxy_pct()`/`protection_buffer()` primitives
wired in unchanged; the exact contract worked vector (§29.6); and the
Stage 5/6 boundary — this module produces a qualification only, never an
episode/persistence/confirmation/expiry decision."""
from __future__ import annotations

import ast
import inspect
from datetime import datetime, timedelta, timezone

import pytest

from analytics.forecasting_v2 import trend_pullback as tp_module
from analytics.forecasting_v2.bias_1h import (
    BEARISH, BIAS_UNAVAILABLE, BULLISH, NEUTRAL_NOT_ESTABLISHED, V2BiasResult,
)
from analytics.forecasting_v2.context_snapshot import V2ContextSnapshot
from analytics.forecasting_v2.events import LONG, SHORT
from analytics.forecasting_v2.regime_4h import (
    BEARISH_TRENDING, BULLISH_TRENDING, INSUFFICIENT_DATA, NON_DIRECTIONAL, V2RegimeResult,
)
from analytics.forecasting_v2.setup_common import (
    RANGE_PROXY_N, SETUP_MIN_CONFIDENCE, SETUP_MIN_COVERAGE, V2ExtremeAnchor,
)
from analytics.forecasting_v2.trend_pullback import (
    EXPECTED_HORIZON,
    LOOKBACK_15M,
    PULLBACK_MAX_AGE_15M_BUCKETS,
    PULLBACK_MAX_MULT,
    PULLBACK_MIN_MULT,
    RESUMPTION_MIN_BUCKETS,
    V2TrendPullbackCandidate,
    V2TrendPullbackError,
    V2TrendPullbackInputs,
    detect_trend_pullback,
)

UTC = timezone.utc
H16 = "a" * 16
SYMBOL = "BTCUSDT"
MARKET_TYPE = "perp"

T = datetime(2026, 8, 15, 12, 15, tzinfo=UTC)  # legal 15m formation boundary
B15 = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
B4H = datetime(2026, 8, 15, 8, 0, tzinfo=UTC)
B1H = datetime(2026, 8, 15, 11, 0, tzinfo=UTC)
FIFTEEN = timedelta(minutes=15)


# ============================================================================
# fixtures
# ============================================================================
def make_context(regime, bias, *, t=T, b4h=B4H, b1h=B1H, is_compressed=None) -> V2ContextSnapshot:
    if is_compressed is None and regime == NON_DIRECTIONAL:
        is_compressed = False
    return V2ContextSnapshot(
        T=t, symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=H16,
        feature_schema_version=1,
        regime_4h=V2RegimeResult(bucket_ts=b4h, regime=regime, is_compressed=is_compressed),
        bias_1h=V2BiasResult(bucket_ts=b1h, bias=bias),
    )


def make_reference_row(bucket_ts, close_price=64_000.0, **over):
    base = dict(
        exchange="binance", symbol=SYMBOL, market_type=MARKET_TYPE, timeframe="15m",
        bucket_ts=bucket_ts, calculation_version=H16, feature_schema_version=1,
        is_usable=True, has_gap=False, bars_present=15, bars_expected=15,
        close_price=close_price,
    )
    base.update(over)
    return base


def make_proxy_row(bucket_ts, value=0.4, *, min_coverage_ratio=1.0, consensus_confidence=100.0,
                   **over):
    base = dict(
        symbol=SYMBOL, market_type=MARKET_TYPE, timeframe="15m",
        calculation_version=H16, feature_schema_version=1,
        bucket_ts=bucket_ts, range_width_pct_median=value,
        min_coverage_ratio=min_coverage_ratio, consensus_confidence=consensus_confidence,
    )
    base.update(over)
    return base


def make_instrument(tick_size=0.1, **over):
    base = dict(exchange="binance", symbol=SYMBOL, market_type=MARKET_TYPE, tick_size=tick_size)
    base.update(over)
    return base


def build_lookback_rows(*, b15=B15, closes_by_offset=None, default_close=64_800.0):
    """`closes_by_offset`: {offset_from_b15_in_15m_units (<=0): close}. Any
    expected bucket not explicitly given gets `default_close`."""
    closes_by_offset = closes_by_offset or {}
    start = b15 - (LOOKBACK_15M - 1) * FIFTEEN
    rows = []
    for i in range(LOOKBACK_15M):
        ts = start + i * FIFTEEN
        offset = (ts - b15) // FIFTEEN
        close = closes_by_offset.get(offset, default_close)
        rows.append(make_reference_row(ts, close_price=close))
    return tuple(rows)


def build_proxy_rows(*, b15=B15, value=0.4):
    start = b15 - (RANGE_PROXY_N - 1) * FIFTEEN
    return tuple(make_proxy_row(start + i * FIFTEEN, value=value) for i in range(RANGE_PROXY_N))


# The exact §29.6 worked LONG vector: trend_leg_extreme(high)=65,000 at
# anchor 5 buckets before B15; deepest post-anchor close (pullback_extreme)
# =64,300 two buckets before B15; current close=64,350; proxy=0.4%.
_LONG_CLOSES = {
    -5: 65_000.0,   # trend_leg_extreme anchor
    -2: 64_300.0,   # pullback_extreme (deepest close during retracement)
    0: 64_350.0,    # current close (B15)
}
_SHORT_CLOSES = {
    -5: 60_000.0,   # trend_leg_extreme anchor (low)
    -2: 60_700.0,   # pullback_extreme (highest close during retracement)
    0: 60_650.0,    # current close (B15)
}


def make_valid_long_inputs(**over):
    kwargs = dict(
        context=make_context(BULLISH_TRENDING, BULLISH),
        reference_15m_rows=build_lookback_rows(closes_by_offset=_LONG_CLOSES),
        range_proxy_15m_rows=build_proxy_rows(),
        instrument=make_instrument(),
    )
    kwargs.update(over)
    return V2TrendPullbackInputs(**kwargs)


def make_valid_short_inputs(**over):
    kwargs = dict(
        context=make_context(BEARISH_TRENDING, BEARISH),
        reference_15m_rows=build_lookback_rows(b15=B15, closes_by_offset=_SHORT_CLOSES,
                                               default_close=60_200.0),
        range_proxy_15m_rows=build_proxy_rows(),
        instrument=make_instrument(),
    )
    kwargs.update(over)
    return V2TrendPullbackInputs(**kwargs)


# ============================================================================
# 1. CONTRACT WORKED VECTOR — §29.6 exact LONG lifecycle formation
# ============================================================================
def test_worked_vector_long_qualifies_exact_contract_numbers():
    candidate = detect_trend_pullback(make_valid_long_inputs())
    assert candidate is not None
    assert candidate.direction == LONG
    assert candidate.T == T
    assert candidate.bucket_15m == B15
    assert candidate.bucket_5m_at_T == datetime(2026, 8, 15, 12, 10, tzinfo=UTC)
    assert candidate.current_close == 64_350.0
    assert candidate.retracement_pct == pytest.approx(1.0, abs=1e-9)
    assert candidate.range_proxy_pct == pytest.approx(0.4, abs=1e-9)
    assert candidate.pullback_extreme == 64_300.0
    assert candidate.protection_buffer == pytest.approx(128.7, abs=1e-9)
    assert candidate.entry_zone_lower == 64_300.0
    assert candidate.entry_zone_upper == 64_350.0
    assert candidate.invalidation_price == pytest.approx(64_171.3, abs=1e-9)
    assert candidate.structural_anchor == B15 - 5 * FIFTEEN
    assert candidate.trend_leg_extreme == V2ExtremeAnchor(bucket_ts=B15 - 5 * FIFTEEN, value=65_000.0)


def test_worked_vector_short_symmetry():
    candidate = detect_trend_pullback(make_valid_short_inputs())
    assert candidate is not None
    assert candidate.direction == SHORT
    assert candidate.current_close == 60_650.0
    assert candidate.pullback_extreme == 60_700.0
    assert candidate.trend_leg_extreme.value == 60_000.0
    assert candidate.entry_zone_lower == 60_650.0
    assert candidate.entry_zone_upper == 60_700.0
    assert candidate.invalidation_price > candidate.pullback_extreme
    assert candidate.retracement_pct == pytest.approx(
        (60_650.0 - 60_000.0) / 60_000.0 * 100.0, abs=1e-9)


def test_rejected_retracement_too_large_no_candidate():
    # §29.6: retracement_pct=1.8% against [0.20%,1.20%] -> exceeds
    # PULLBACK_MAX_MULT -> no candidate ever formed.
    closes = dict(_LONG_CLOSES)
    closes[-2] = 65_000.0 * (1 - 0.018)  # ~63,830 -> retracement ~1.8%
    closes[0] = closes[-2]
    inputs = make_valid_long_inputs(
        reference_15m_rows=build_lookback_rows(closes_by_offset=closes))
    assert detect_trend_pullback(inputs) is None


# ============================================================================
# 2. STRICT CONTEXT PRECONDITION — §7.1, never directional_context_gate
# ============================================================================
@pytest.mark.parametrize("regime,bias,expect_direction", [
    (BULLISH_TRENDING, BULLISH, LONG),
    (BEARISH_TRENDING, BEARISH, SHORT),
])
def test_context_matches_derives_expected_direction(regime, bias, expect_direction):
    closes = _LONG_CLOSES if expect_direction == LONG else _SHORT_CLOSES
    default = 64_800.0 if expect_direction == LONG else 60_200.0
    inputs = V2TrendPullbackInputs(
        context=make_context(regime, bias),
        reference_15m_rows=build_lookback_rows(closes_by_offset=closes, default_close=default),
        range_proxy_15m_rows=build_proxy_rows(),
        instrument=make_instrument(),
    )
    candidate = detect_trend_pullback(inputs)
    assert candidate is not None
    assert candidate.direction == expect_direction


@pytest.mark.parametrize("regime,bias", [
    (BULLISH_TRENDING, BEARISH),
    (BEARISH_TRENDING, BULLISH),
    (BULLISH_TRENDING, NEUTRAL_NOT_ESTABLISHED),
    (BULLISH_TRENDING, BIAS_UNAVAILABLE),
    (BEARISH_TRENDING, NEUTRAL_NOT_ESTABLISHED),
    (BEARISH_TRENDING, BIAS_UNAVAILABLE),
    (NON_DIRECTIONAL, BULLISH),
    (NON_DIRECTIONAL, BEARISH),
    (NON_DIRECTIONAL, NEUTRAL_NOT_ESTABLISHED),
    (NON_DIRECTIONAL, BIAS_UNAVAILABLE),
    (INSUFFICIENT_DATA, BULLISH),
    (INSUFFICIENT_DATA, BEARISH),
    (INSUFFICIENT_DATA, NEUTRAL_NOT_ESTABLISHED),
    (INSUFFICIENT_DATA, BIAS_UNAVAILABLE),
])
def test_context_mismatch_never_qualifies(regime, bias):
    inputs = V2TrendPullbackInputs(
        context=make_context(regime, bias),
        reference_15m_rows=(), range_proxy_15m_rows=(), instrument=None)
    assert detect_trend_pullback(inputs) is None


def test_directional_context_gate_never_imported_or_called():
    body_src = _executable_body_source(tp_module)
    assert "directional_context_gate" not in body_src


# ============================================================================
# 3. FORMATION BOUNDARY CLOCK — §7, no flooring
# ============================================================================
@pytest.mark.parametrize("t,should_evaluate", [
    (datetime(2026, 8, 15, 12, 15, tzinfo=UTC), True),
    (datetime(2026, 8, 15, 12, 20, tzinfo=UTC), False),
    (datetime(2026, 8, 15, 12, 25, tzinfo=UTC), False),
    (datetime(2026, 8, 15, 12, 30, tzinfo=UTC), True),
    (datetime(2026, 8, 15, 13, 0, tzinfo=UTC), True),
    (datetime(2020, 3, 1, 5, 15, tzinfo=UTC), True),
    (datetime(2020, 3, 1, 5, 20, tzinfo=UTC), False),
])
def test_formation_boundary_examples(t, should_evaluate):
    # Build a context/rows set aligned to whatever B15 this T selects.
    from analytics.forecasting_v2.alignment import selected_bucket
    b15 = selected_bucket("15m", t)
    context = make_context(BULLISH_TRENDING, BULLISH, t=t,
                           b4h=selected_bucket("4h", t), b1h=selected_bucket("1h", t))
    if should_evaluate:
        inputs = V2TrendPullbackInputs(
            context=context,
            reference_15m_rows=build_lookback_rows(b15=b15, closes_by_offset={
                offset: close for offset, close in _shift_closes(_LONG_CLOSES).items()
            }),
            range_proxy_15m_rows=build_proxy_rows(b15=b15),
            instrument=make_instrument(),
        )
        candidate = detect_trend_pullback(inputs)
        assert candidate is not None
        assert candidate.bucket_15m == b15
    else:
        inputs = V2TrendPullbackInputs(
            context=context, reference_15m_rows=(), range_proxy_15m_rows=(), instrument=None)
        assert detect_trend_pullback(inputs) is None


def _shift_closes(closes_by_offset):
    return dict(closes_by_offset)


# ============================================================================
# 4. TREND-LEG EXTREME — real select_extreme_anchor(), latest-tie proof
# ============================================================================
def test_extreme_tie_selects_most_recent_bucket_long():
    closes = dict(_LONG_CLOSES)
    # Older bucket b[10] and newer bucket b[30] (0-indexed from oldest, so
    # offsets are i-47) both close at the same tied max 65,000.
    older_offset = 10 - (LOOKBACK_15M - 1)  # -37
    newer_offset = 30 - (LOOKBACK_15M - 1)  # -17
    closes[older_offset] = 65_000.0
    closes[newer_offset] = 65_000.0
    closes[-5] = 64_900.0  # not the extreme anymore
    inputs = make_valid_long_inputs(
        reference_15m_rows=build_lookback_rows(closes_by_offset=closes))
    candidate = detect_trend_pullback(inputs)
    assert candidate is not None
    assert candidate.trend_leg_extreme.value == 65_000.0
    assert candidate.trend_leg_extreme.bucket_ts == B15 + newer_offset * FIFTEEN


def test_extreme_tie_selects_most_recent_bucket_short():
    closes = dict(_SHORT_CLOSES)
    older_offset = 10 - (LOOKBACK_15M - 1)
    newer_offset = 30 - (LOOKBACK_15M - 1)
    closes[older_offset] = 60_000.0
    closes[newer_offset] = 60_000.0
    closes[-5] = 60_100.0
    inputs = make_valid_short_inputs(
        reference_15m_rows=build_lookback_rows(closes_by_offset=closes, default_close=60_200.0))
    candidate = detect_trend_pullback(inputs)
    assert candidate is not None
    assert candidate.trend_leg_extreme.value == 60_000.0
    assert candidate.trend_leg_extreme.bucket_ts == B15 + newer_offset * FIFTEEN


def test_extreme_uses_real_select_extreme_anchor_primitive():
    # Assert the shared primitive is actually imported/used, not
    # re-implemented privately.
    src = inspect.getsource(tp_module)
    assert "select_extreme_anchor(" in src


# ============================================================================
# 5. PULLBACK-EXTREME STRUCTURAL SPAN — §23, anchor -> B15 only
# ============================================================================
def test_pullback_extreme_span_excludes_pre_anchor_buckets_long():
    closes = dict(_LONG_CLOSES)
    # An OLD bucket well before the anchor with an even deeper close must
    # NOT influence pullback_extreme.
    closes[-40] = 50_000.0  # far pre-anchor, deep low -- must be ignored
    inputs = make_valid_long_inputs(
        reference_15m_rows=build_lookback_rows(closes_by_offset=closes))
    candidate = detect_trend_pullback(inputs)
    assert candidate is not None
    assert candidate.pullback_extreme == 64_300.0  # NOT 50,000.0


def test_pullback_extreme_span_excludes_pre_anchor_buckets_short():
    closes = dict(_SHORT_CLOSES)
    closes[-40] = 70_000.0  # far pre-anchor, deep high -- must be ignored
    inputs = make_valid_short_inputs(
        reference_15m_rows=build_lookback_rows(closes_by_offset=closes, default_close=60_200.0))
    candidate = detect_trend_pullback(inputs)
    assert candidate is not None
    assert candidate.pullback_extreme == 60_700.0  # NOT 70,000.0


# ============================================================================
# 6. EXACT RETRACEMENT BOUNDARIES — inclusive, no arbitrary epsilon
# ============================================================================
def _long_inputs_with_retracement_mult(mult):
    # trend_leg_extreme = 100,000; proxy = 0.4 -> retracement_pct target =
    # mult * 0.4. current_close = 100,000 * (1 - target/100).
    extreme = 100_000.0
    proxy = 0.4
    target_pct = mult * proxy
    current = extreme * (1 - target_pct / 100.0)
    closes = {-5: extreme, -2: current, 0: current}
    return make_valid_long_inputs(
        reference_15m_rows=build_lookback_rows(closes_by_offset=closes, default_close=extreme - 1))


def test_retracement_exactly_min_mult_qualifies():
    inputs = _long_inputs_with_retracement_mult(PULLBACK_MIN_MULT)
    assert detect_trend_pullback(inputs) is not None


def test_retracement_exactly_max_mult_qualifies():
    inputs = _long_inputs_with_retracement_mult(PULLBACK_MAX_MULT)
    assert detect_trend_pullback(inputs) is not None


def test_retracement_slightly_below_min_mult_rejected():
    inputs = _long_inputs_with_retracement_mult(PULLBACK_MIN_MULT - 0.05)
    assert detect_trend_pullback(inputs) is None


def test_retracement_slightly_above_max_mult_rejected():
    inputs = _long_inputs_with_retracement_mult(PULLBACK_MAX_MULT + 0.05)
    assert detect_trend_pullback(inputs) is None


def _short_inputs_with_retracement_mult(mult):
    extreme = 50_000.0
    proxy = 0.4
    target_pct = mult * proxy
    current = extreme * (1 + target_pct / 100.0)
    closes = {-5: extreme, -2: current, 0: current}
    return make_valid_short_inputs(
        reference_15m_rows=build_lookback_rows(
            closes_by_offset=closes, default_close=extreme + 1))


def test_retracement_boundaries_short_symmetric():
    assert detect_trend_pullback(_short_inputs_with_retracement_mult(PULLBACK_MIN_MULT)) is not None
    assert detect_trend_pullback(_short_inputs_with_retracement_mult(PULLBACK_MAX_MULT)) is not None
    assert detect_trend_pullback(_short_inputs_with_retracement_mult(PULLBACK_MIN_MULT - 0.05)) is None
    assert detect_trend_pullback(_short_inputs_with_retracement_mult(PULLBACK_MAX_MULT + 0.05)) is None


# ============================================================================
# 7. REFERENCE HISTORY MISSINGNESS — exact 48, no partial window
# ============================================================================
def test_missing_oldest_bucket_is_unavailable():
    rows = list(build_lookback_rows(closes_by_offset=_LONG_CLOSES))
    del rows[0]
    inputs = make_valid_long_inputs(reference_15m_rows=tuple(rows))
    assert detect_trend_pullback(inputs) is None


def test_missing_middle_bucket_is_unavailable():
    rows = list(build_lookback_rows(closes_by_offset=_LONG_CLOSES))
    del rows[20]
    inputs = make_valid_long_inputs(reference_15m_rows=tuple(rows))
    assert detect_trend_pullback(inputs) is None


def test_missing_current_b15_bucket_is_unavailable():
    rows = list(build_lookback_rows(closes_by_offset=_LONG_CLOSES))
    del rows[-1]
    inputs = make_valid_long_inputs(reference_15m_rows=tuple(rows))
    assert detect_trend_pullback(inputs) is None


def test_duplicate_reference_bucket_raises():
    rows = list(build_lookback_rows(closes_by_offset=_LONG_CLOSES))
    rows.append(rows[0])
    inputs = make_valid_long_inputs(reference_15m_rows=tuple(rows))
    with pytest.raises(V2TrendPullbackError):
        detect_trend_pullback(inputs)


def test_unexpected_out_of_grid_reference_bucket_raises():
    rows = list(build_lookback_rows(closes_by_offset=_LONG_CLOSES))
    rows.append(make_reference_row(B15 + FIFTEEN, close_price=64_000.0))
    inputs = make_valid_long_inputs(reference_15m_rows=tuple(rows))
    with pytest.raises(V2TrendPullbackError):
        detect_trend_pullback(inputs)


# ============================================================================
# 8. REFERENCE ROW IDENTITY — §16
# ============================================================================
def test_reference_row_wrong_symbol_raises():
    rows = list(build_lookback_rows(closes_by_offset=_LONG_CLOSES))
    rows[0] = {**rows[0], "symbol": "ETHUSDT"}
    inputs = make_valid_long_inputs(reference_15m_rows=tuple(rows))
    with pytest.raises(V2TrendPullbackError):
        detect_trend_pullback(inputs)


def test_reference_row_wrong_exchange_raises_no_failover():
    rows = list(build_lookback_rows(closes_by_offset=_LONG_CLOSES))
    rows[0] = {**rows[0], "exchange": "bybit"}
    inputs = make_valid_long_inputs(reference_15m_rows=tuple(rows))
    with pytest.raises(V2TrendPullbackError):
        detect_trend_pullback(inputs)


def test_reference_row_wrong_calculation_version_raises():
    rows = list(build_lookback_rows(closes_by_offset=_LONG_CLOSES))
    rows[0] = {**rows[0], "calculation_version": "c" * 16}
    inputs = make_valid_long_inputs(reference_15m_rows=tuple(rows))
    with pytest.raises(V2TrendPullbackError):
        detect_trend_pullback(inputs)


@pytest.mark.parametrize("missing_field", [
    "exchange", "symbol", "market_type", "timeframe", "calculation_version",
    "feature_schema_version", "bucket_ts", "is_usable", "has_gap",
    "bars_present", "bars_expected", "close_price",
])
def test_reference_row_missing_required_field_raises(missing_field):
    rows = list(build_lookback_rows(closes_by_offset=_LONG_CLOSES))
    row = dict(rows[0])
    del row[missing_field]
    rows[0] = row
    inputs = make_valid_long_inputs(reference_15m_rows=tuple(rows))
    with pytest.raises(V2TrendPullbackError, match=missing_field):
        detect_trend_pullback(inputs)


def test_reference_row_non_mapping_raises():
    rows = list(build_lookback_rows(closes_by_offset=_LONG_CLOSES))
    rows[0] = "not-a-row"
    inputs = make_valid_long_inputs(reference_15m_rows=tuple(rows))
    with pytest.raises(V2TrendPullbackError):
        detect_trend_pullback(inputs)


# ============================================================================
# 9. REFERENCE FAIL-CLOSED GATE — §11/§17
# ============================================================================
def test_reference_row_is_usable_false_is_unavailable():
    rows = list(build_lookback_rows(closes_by_offset=_LONG_CLOSES))
    rows[5] = {**rows[5], "is_usable": False}
    inputs = make_valid_long_inputs(reference_15m_rows=tuple(rows))
    assert detect_trend_pullback(inputs) is None


def test_reference_row_has_gap_true_is_unavailable():
    rows = list(build_lookback_rows(closes_by_offset=_LONG_CLOSES))
    rows[5] = {**rows[5], "has_gap": True}
    inputs = make_valid_long_inputs(reference_15m_rows=tuple(rows))
    assert detect_trend_pullback(inputs) is None


def test_reference_row_bars_mismatch_is_unavailable():
    rows = list(build_lookback_rows(closes_by_offset=_LONG_CLOSES))
    rows[5] = {**rows[5], "bars_present": 14}
    inputs = make_valid_long_inputs(reference_15m_rows=tuple(rows))
    assert detect_trend_pullback(inputs) is None


def test_reference_row_close_price_none_is_unavailable():
    rows = list(build_lookback_rows(closes_by_offset=_LONG_CLOSES))
    rows[5] = {**rows[5], "close_price": None}
    inputs = make_valid_long_inputs(reference_15m_rows=tuple(rows))
    assert detect_trend_pullback(inputs) is None


@pytest.mark.parametrize("bad_close", [float("nan"), float("inf"), 0.0, -1.0, True, "64000"])
def test_reference_row_malformed_present_close_raises(bad_close):
    rows = list(build_lookback_rows(closes_by_offset=_LONG_CLOSES))
    rows[5] = {**rows[5], "close_price": bad_close}
    inputs = make_valid_long_inputs(reference_15m_rows=tuple(rows))
    with pytest.raises(V2TrendPullbackError):
        detect_trend_pullback(inputs)


@pytest.mark.parametrize("field,bad_value", [
    ("is_usable", "yes"), ("is_usable", 1),
    ("has_gap", "no"), ("has_gap", 0),
    ("bars_present", True), ("bars_present", 15.0), ("bars_present", -1),
    ("bars_expected", True), ("bars_expected", 15.0), ("bars_expected", -1),
])
def test_reference_row_malformed_present_gate_field_raises(field, bad_value):
    rows = list(build_lookback_rows(closes_by_offset=_LONG_CLOSES))
    rows[5] = {**rows[5], field: bad_value}
    inputs = make_valid_long_inputs(reference_15m_rows=tuple(rows))
    with pytest.raises(V2TrendPullbackError):
        detect_trend_pullback(inputs)


def test_malformed_present_value_never_masked_by_a_different_missing_bucket():
    # Corruption precedence: one expected bucket missing entirely AND one
    # present row malformed -- must raise, never silently return None.
    rows = list(build_lookback_rows(closes_by_offset=_LONG_CLOSES))
    rows[5] = {**rows[5], "close_price": float("nan")}
    del rows[10]
    inputs = make_valid_long_inputs(reference_15m_rows=tuple(rows))
    with pytest.raises(V2TrendPullbackError):
        detect_trend_pullback(inputs)


# ============================================================================
# 9b. FULL 15m REFERENCE BAR COUNT — §11/§12/§13
# ============================================================================
def test_reference_row_bars_expected_15_present_15_is_usable():
    rows = list(build_lookback_rows(closes_by_offset=_LONG_CLOSES))
    rows[5] = {**rows[5], "bars_expected": 15, "bars_present": 15}
    inputs = make_valid_long_inputs(reference_15m_rows=tuple(rows))
    assert detect_trend_pullback(inputs) is not None


def test_reference_row_bars_expected_15_present_14_is_unavailable():
    rows = list(build_lookback_rows(closes_by_offset=_LONG_CLOSES))
    rows[5] = {**rows[5], "bars_expected": 15, "bars_present": 14}
    inputs = make_valid_long_inputs(reference_15m_rows=tuple(rows))
    assert detect_trend_pullback(inputs) is None


def test_reference_row_bars_expected_14_is_impossible_identity_raises():
    # bars_expected != 15 for a 15m bucket is corrupted/impossible
    # identity metadata -- not ordinary "one bar missing" -- so it must
    # raise even though bars_present == bars_expected (14 == 14).
    rows = list(build_lookback_rows(closes_by_offset=_LONG_CLOSES))
    rows[5] = {**rows[5], "bars_expected": 14, "bars_present": 14}
    inputs = make_valid_long_inputs(reference_15m_rows=tuple(rows))
    with pytest.raises(V2TrendPullbackError):
        detect_trend_pullback(inputs)


def test_reference_row_bars_expected_16_raises():
    rows = list(build_lookback_rows(closes_by_offset=_LONG_CLOSES))
    rows[5] = {**rows[5], "bars_expected": 16, "bars_present": 16}
    inputs = make_valid_long_inputs(reference_15m_rows=tuple(rows))
    with pytest.raises(V2TrendPullbackError):
        detect_trend_pullback(inputs)


def test_reference_row_bars_present_exceeds_bars_expected_raises():
    rows = list(build_lookback_rows(closes_by_offset=_LONG_CLOSES))
    rows[5] = {**rows[5], "bars_expected": 15, "bars_present": 16}
    inputs = make_valid_long_inputs(reference_15m_rows=tuple(rows))
    with pytest.raises(V2TrendPullbackError):
        detect_trend_pullback(inputs)


# ============================================================================
# 10. RANGE PROXY THROUGH THE REAL DETECTOR — §18/§50
# ============================================================================
def test_range_proxy_exact_14_rows_may_qualify():
    inputs = make_valid_long_inputs(range_proxy_15m_rows=build_proxy_rows())
    assert detect_trend_pullback(inputs) is not None


def test_range_proxy_13_rows_is_unavailable():
    rows = list(build_proxy_rows())
    del rows[0]
    inputs = make_valid_long_inputs(range_proxy_15m_rows=tuple(rows))
    assert detect_trend_pullback(inputs) is None


def test_range_proxy_one_value_none_is_unavailable():
    rows = list(build_proxy_rows())
    rows[0] = {**rows[0], "range_width_pct_median": None}
    inputs = make_valid_long_inputs(range_proxy_15m_rows=tuple(rows))
    assert detect_trend_pullback(inputs) is None


def test_range_proxy_malformed_present_row_wraps_v2setupfoundationerror():
    from analytics.forecasting_v2.setup_common import V2SetupFoundationError
    rows = list(build_proxy_rows())
    rows[0] = {**rows[0], "range_width_pct_median": float("nan")}
    inputs = make_valid_long_inputs(range_proxy_15m_rows=tuple(rows))
    with pytest.raises(V2TrendPullbackError) as excinfo:
        detect_trend_pullback(inputs)
    assert isinstance(excinfo.value.__cause__, V2SetupFoundationError)


def test_range_proxy_row_wrong_symbol_raises_before_shared_math():
    rows = list(build_proxy_rows())
    rows[0] = {**rows[0], "symbol": "ETHUSDT"}
    inputs = make_valid_long_inputs(range_proxy_15m_rows=tuple(rows))
    with pytest.raises(V2TrendPullbackError):
        detect_trend_pullback(inputs)


def test_range_proxy_row_wrong_calculation_version_raises():
    rows = list(build_proxy_rows())
    rows[0] = {**rows[0], "calculation_version": "c" * 16}
    inputs = make_valid_long_inputs(range_proxy_15m_rows=tuple(rows))
    with pytest.raises(V2TrendPullbackError):
        detect_trend_pullback(inputs)


@pytest.mark.parametrize("missing_field", [
    "symbol", "market_type", "timeframe", "calculation_version", "feature_schema_version",
    "bucket_ts",
])
def test_range_proxy_row_missing_identity_field_raises(missing_field):
    rows = list(build_proxy_rows())
    row = dict(rows[0])
    del row[missing_field]
    rows[0] = row
    inputs = make_valid_long_inputs(range_proxy_15m_rows=tuple(rows))
    with pytest.raises(V2TrendPullbackError, match=missing_field):
        detect_trend_pullback(inputs)


@pytest.mark.parametrize("bad_bucket_ts", [
    "not-a-datetime",
    datetime(2026, 8, 15, 12, 0),  # naive
    datetime(2026, 8, 15, 15, 0, tzinfo=timezone(timedelta(hours=3))),  # non-UTC
    B15.replace(second=1),
    B15.replace(microsecond=1),
])
def test_range_proxy_row_malformed_bucket_ts_raises(bad_bucket_ts):
    rows = list(build_proxy_rows())
    rows[0] = {**rows[0], "bucket_ts": bad_bucket_ts}
    inputs = make_valid_long_inputs(range_proxy_15m_rows=tuple(rows))
    with pytest.raises(V2TrendPullbackError):
        detect_trend_pullback(inputs)


def test_range_proxy_row_bucket_ts_never_normalized_or_floored():
    # A malformed bucket_ts must raise, never be silently floored to a
    # legal grid instant on the caller's behalf.
    rows = list(build_proxy_rows())
    rows[0] = {**rows[0], "bucket_ts": B15.replace(second=1)}
    inputs = make_valid_long_inputs(range_proxy_15m_rows=tuple(rows))
    with pytest.raises(V2TrendPullbackError):
        detect_trend_pullback(inputs)


def _set_current_b15_proxy_row(rows, **over):
    """Replace the row whose bucket_ts == B15 (the last one, per
    build_proxy_rows' ascending construction) with an overridden copy."""
    rows = list(rows)
    for i, row in enumerate(rows):
        if row["bucket_ts"] == B15:
            rows[i] = {**row, **over}
            return rows
    raise AssertionError("no proxy row at bucket_ts == B15 to override")


# ============================================================================
# 10b. SETUP-TIMEFRAME CONSENSUS QUALITY GATE — §6.2/§6.3, current B15
# consensus row only, no extra storage read.
# ============================================================================
def test_quality_exact_min_coverage_and_min_confidence_qualifies():
    rows = _set_current_b15_proxy_row(
        build_proxy_rows(), min_coverage_ratio=SETUP_MIN_COVERAGE,
        consensus_confidence=SETUP_MIN_CONFIDENCE)
    inputs = make_valid_long_inputs(range_proxy_15m_rows=tuple(rows))
    assert detect_trend_pullback(inputs) is not None


def test_quality_coverage_just_below_minimum_is_none():
    rows = _set_current_b15_proxy_row(
        build_proxy_rows(), min_coverage_ratio=SETUP_MIN_COVERAGE - 0.01)
    inputs = make_valid_long_inputs(range_proxy_15m_rows=tuple(rows))
    assert detect_trend_pullback(inputs) is None


def test_quality_confidence_just_below_minimum_is_none():
    rows = _set_current_b15_proxy_row(build_proxy_rows(), consensus_confidence=49.999)
    inputs = make_valid_long_inputs(range_proxy_15m_rows=tuple(rows))
    assert detect_trend_pullback(inputs) is None


def test_quality_coverage_none_is_unavailable():
    rows = _set_current_b15_proxy_row(build_proxy_rows(), min_coverage_ratio=None)
    inputs = make_valid_long_inputs(range_proxy_15m_rows=tuple(rows))
    assert detect_trend_pullback(inputs) is None


def test_quality_confidence_none_is_unavailable():
    rows = _set_current_b15_proxy_row(build_proxy_rows(), consensus_confidence=None)
    inputs = make_valid_long_inputs(range_proxy_15m_rows=tuple(rows))
    assert detect_trend_pullback(inputs) is None


@pytest.mark.parametrize("bad_coverage", [
    float("nan"), float("inf"), -0.1, 1.1, True, "0.8",
])
def test_quality_malformed_present_coverage_raises(bad_coverage):
    rows = _set_current_b15_proxy_row(build_proxy_rows(), min_coverage_ratio=bad_coverage)
    inputs = make_valid_long_inputs(range_proxy_15m_rows=tuple(rows))
    with pytest.raises(V2TrendPullbackError):
        detect_trend_pullback(inputs)


@pytest.mark.parametrize("bad_confidence", [
    float("nan"), float("inf"), -1, 101, True, "80",
])
def test_quality_malformed_present_confidence_raises(bad_confidence):
    rows = _set_current_b15_proxy_row(build_proxy_rows(), consensus_confidence=bad_confidence)
    inputs = make_valid_long_inputs(range_proxy_15m_rows=tuple(rows))
    with pytest.raises(V2TrendPullbackError):
        detect_trend_pullback(inputs)


@pytest.mark.parametrize("missing_field", ["min_coverage_ratio", "consensus_confidence"])
def test_quality_missing_required_field_raises(missing_field):
    rows = build_proxy_rows()
    new_rows = []
    for row in rows:
        if row["bucket_ts"] == B15:
            row = dict(row)
            del row[missing_field]
        new_rows.append(row)
    inputs = make_valid_long_inputs(range_proxy_15m_rows=tuple(new_rows))
    with pytest.raises(V2TrendPullbackError, match=missing_field):
        detect_trend_pullback(inputs)


def test_quality_corruption_precedence_malformed_confidence_plus_missing_historical_peer():
    # Malformed PRESENT current-B15 confidence AND a DIFFERENT, older
    # RANGE_PROXY peer bucket entirely missing -- must raise, never
    # silently return None because of the unrelated missing peer.
    rows = _set_current_b15_proxy_row(build_proxy_rows(), consensus_confidence=float("nan"))
    rows = [r for r in rows if r["bucket_ts"] != B15 - 5 * FIFTEEN]
    inputs = make_valid_long_inputs(range_proxy_15m_rows=tuple(rows))
    with pytest.raises(V2TrendPullbackError):
        detect_trend_pullback(inputs)


def test_quality_current_row_entirely_absent_is_legitimate_none():
    # No fabrication: if the current B15 row is missing entirely, the
    # window is incomplete anyway -- legitimate None, not an error.
    rows = [r for r in build_proxy_rows() if r["bucket_ts"] != B15]
    inputs = make_valid_long_inputs(range_proxy_15m_rows=tuple(rows))
    assert detect_trend_pullback(inputs) is None


def test_quality_gate_applies_to_short_direction_too():
    rows = _set_current_b15_proxy_row(build_proxy_rows(), consensus_confidence=10.0)
    inputs = make_valid_short_inputs(range_proxy_15m_rows=tuple(rows))
    assert detect_trend_pullback(inputs) is None


# ============================================================================
# 11. INSTRUMENT / TICK SIZE — §12/§51
# ============================================================================
def test_instrument_none_is_unavailable():
    inputs = make_valid_long_inputs(instrument=None)
    assert detect_trend_pullback(inputs) is None


def test_instrument_valid_tick_qualifies():
    inputs = make_valid_long_inputs(instrument=make_instrument(tick_size=0.5))
    candidate = detect_trend_pullback(inputs)
    assert candidate is not None


def test_instrument_tick_size_none_is_unavailable():
    inputs = make_valid_long_inputs(instrument=make_instrument(tick_size=None))
    assert detect_trend_pullback(inputs) is None


@pytest.mark.parametrize("bad_tick", [float("nan"), float("inf"), 0.0, -0.1, True, "0.1"])
def test_instrument_malformed_present_tick_raises(bad_tick):
    inputs = make_valid_long_inputs(instrument=make_instrument(tick_size=bad_tick))
    with pytest.raises(V2TrendPullbackError):
        detect_trend_pullback(inputs)


def test_instrument_missing_tick_size_key_raises():
    inputs = make_valid_long_inputs(instrument={"exchange": "binance"})
    with pytest.raises(V2TrendPullbackError):
        detect_trend_pullback(inputs)


def test_instrument_non_mapping_raises():
    inputs = make_valid_long_inputs(instrument="not-a-row")
    with pytest.raises(V2TrendPullbackError):
        detect_trend_pullback(inputs)


def test_instrument_no_hard_coded_tick_fallback():
    # A tick_size deliberately different from any conventional BTC tick
    # must be used verbatim, proving no hard-coded fallback exists.
    inputs = make_valid_long_inputs(instrument=make_instrument(tick_size=1.2345))
    candidate = detect_trend_pullback(inputs)
    assert candidate is not None
    assert candidate.protection_buffer >= 3 * 1.2345


def test_instrument_wrong_exchange_raises_no_foreign_influence():
    # A foreign (non-Binance) instrument must never silently influence a
    # BTCUSDT/perp/Binance-reference candidate's protection buffer.
    inputs = make_valid_long_inputs(instrument=make_instrument(exchange="bybit"))
    with pytest.raises(V2TrendPullbackError):
        detect_trend_pullback(inputs)


def test_instrument_wrong_symbol_raises():
    inputs = make_valid_long_inputs(instrument=make_instrument(symbol="ETHUSDT"))
    with pytest.raises(V2TrendPullbackError):
        detect_trend_pullback(inputs)


def test_instrument_wrong_market_type_raises():
    inputs = make_valid_long_inputs(instrument=make_instrument(market_type="spot"))
    with pytest.raises(V2TrendPullbackError):
        detect_trend_pullback(inputs)


@pytest.mark.parametrize("missing_field", ["exchange", "symbol", "market_type", "tick_size"])
def test_instrument_missing_identity_field_raises(missing_field):
    row = make_instrument()
    del row[missing_field]
    inputs = make_valid_long_inputs(instrument=row)
    with pytest.raises(V2TrendPullbackError, match=missing_field):
        detect_trend_pullback(inputs)


def test_instrument_full_hand_built_foreign_row_cannot_influence_candidate():
    # The exact scenario the amendment closes: a hand-built instrument
    # for a completely different exchange/symbol/market_type must not be
    # silently accepted just because tick_size is present and valid.
    foreign = dict(exchange="bybit", symbol="ETHUSDT", market_type="spot", tick_size=0.1)
    inputs = make_valid_long_inputs(instrument=foreign)
    with pytest.raises(V2TrendPullbackError):
        detect_trend_pullback(inputs)


# ============================================================================
# 12. TOP-LEVEL CONTAINER / TYPE HARDENING
# ============================================================================
def test_detect_rejects_non_v2trendpullbackinputs():
    with pytest.raises(V2TrendPullbackError):
        detect_trend_pullback("not-inputs")  # type: ignore[arg-type]


def test_detect_rejects_wrong_context_type():
    inputs = V2TrendPullbackInputs(
        context="not-a-context", reference_15m_rows=(), range_proxy_15m_rows=(), instrument=None)
    with pytest.raises(V2TrendPullbackError):
        detect_trend_pullback(inputs)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad_rows", [None, "not rows"])
def test_reference_rows_container_hardening(bad_rows):
    inputs = make_valid_long_inputs(reference_15m_rows=bad_rows)
    with pytest.raises(V2TrendPullbackError):
        detect_trend_pullback(inputs)


@pytest.mark.parametrize("bad_rows", [None, "not rows"])
def test_range_proxy_rows_container_hardening(bad_rows):
    inputs = make_valid_long_inputs(range_proxy_15m_rows=bad_rows)
    with pytest.raises(V2TrendPullbackError):
        detect_trend_pullback(inputs)


# ============================================================================
# 13. RESULT SELF-VALIDATION — V2TrendPullbackCandidate direct construction
# ============================================================================
def _valid_candidate_kwargs():
    return dict(
        T=T, direction=LONG, bucket_15m=B15,
        bucket_5m_at_T=datetime(2026, 8, 15, 12, 10, tzinfo=UTC),
        trend_leg_extreme=V2ExtremeAnchor(bucket_ts=B15 - 5 * FIFTEEN, value=65_000.0),
        current_close=64_350.0, retracement_pct=1.0, range_proxy_pct=0.4,
        pullback_extreme=64_300.0, protection_buffer=128.7,
        entry_zone_lower=64_300.0, entry_zone_upper=64_350.0,
        invalidation_price=64_171.3,
    )


def test_candidate_valid_direct_construction_accepted():
    candidate = V2TrendPullbackCandidate(**_valid_candidate_kwargs())
    assert candidate.direction == LONG
    assert candidate.structural_anchor == B15 - 5 * FIFTEEN


def test_candidate_rejects_wrong_direction():
    kwargs = _valid_candidate_kwargs()
    kwargs["direction"] = "UP"
    with pytest.raises(V2TrendPullbackError):
        V2TrendPullbackCandidate(**kwargs)


def test_candidate_rejects_naive_T():
    kwargs = _valid_candidate_kwargs()
    kwargs["T"] = datetime(2026, 8, 15, 12, 15)
    with pytest.raises(V2TrendPullbackError):
        V2TrendPullbackCandidate(**kwargs)


def test_candidate_rejects_non_formation_T():
    kwargs = _valid_candidate_kwargs()
    kwargs["T"] = datetime(2026, 8, 15, 12, 20, tzinfo=UTC)
    with pytest.raises(V2TrendPullbackError):
        V2TrendPullbackCandidate(**kwargs)


def test_candidate_rejects_wrong_bucket_15m():
    kwargs = _valid_candidate_kwargs()
    kwargs["bucket_15m"] = B15 - FIFTEEN
    with pytest.raises(V2TrendPullbackError):
        V2TrendPullbackCandidate(**kwargs)


def test_candidate_rejects_wrong_bucket_5m_at_T():
    kwargs = _valid_candidate_kwargs()
    kwargs["bucket_5m_at_T"] = datetime(2026, 8, 15, 12, 5, tzinfo=UTC)
    with pytest.raises(V2TrendPullbackError):
        V2TrendPullbackCandidate(**kwargs)


@pytest.mark.parametrize("bad_price", [float("nan"), float("inf"), 0.0, -1.0, True])
def test_candidate_rejects_non_finite_or_nonpositive_prices(bad_price):
    for field in ("current_close", "pullback_extreme", "protection_buffer",
                  "entry_zone_lower", "entry_zone_upper", "invalidation_price"):
        kwargs = _valid_candidate_kwargs()
        kwargs[field] = bad_price
        with pytest.raises(V2TrendPullbackError):
            V2TrendPullbackCandidate(**kwargs)


def test_candidate_rejects_negative_retracement_pct():
    kwargs = _valid_candidate_kwargs()
    kwargs["retracement_pct"] = -1.0
    with pytest.raises(V2TrendPullbackError):
        V2TrendPullbackCandidate(**kwargs)


def test_candidate_rejects_negative_range_proxy_pct():
    kwargs = _valid_candidate_kwargs()
    kwargs["range_proxy_pct"] = -0.1
    with pytest.raises(V2TrendPullbackError):
        V2TrendPullbackCandidate(**kwargs)


def test_candidate_rejects_entry_lower_above_upper():
    kwargs = _valid_candidate_kwargs()
    kwargs["entry_zone_lower"] = 64_400.0
    kwargs["entry_zone_upper"] = 64_300.0
    with pytest.raises(V2TrendPullbackError):
        V2TrendPullbackCandidate(**kwargs)


def test_candidate_rejects_anchor_outside_lookback():
    kwargs = _valid_candidate_kwargs()
    kwargs["trend_leg_extreme"] = V2ExtremeAnchor(
        bucket_ts=B15 - (LOOKBACK_15M + 5) * FIFTEEN, value=65_000.0)
    with pytest.raises(V2TrendPullbackError):
        V2TrendPullbackCandidate(**kwargs)


def test_candidate_rejects_long_invalidation_not_below_pullback_extreme():
    kwargs = _valid_candidate_kwargs()
    kwargs["invalidation_price"] = kwargs["pullback_extreme"] + 1.0
    with pytest.raises(V2TrendPullbackError):
        V2TrendPullbackCandidate(**kwargs)


def test_candidate_rejects_short_invalidation_not_above_pullback_extreme():
    kwargs = _valid_candidate_kwargs()
    kwargs["direction"] = SHORT
    kwargs["invalidation_price"] = kwargs["pullback_extreme"] - 1.0
    with pytest.raises(V2TrendPullbackError):
        V2TrendPullbackCandidate(**kwargs)


def test_candidate_is_frozen():
    candidate = V2TrendPullbackCandidate(**_valid_candidate_kwargs())
    with pytest.raises(Exception):
        candidate.direction = SHORT  # type: ignore[misc]


def test_candidate_trend_leg_extreme_must_be_v2extremeanchor():
    kwargs = _valid_candidate_kwargs()
    kwargs["trend_leg_extreme"] = {"bucket_ts": B15, "value": 65_000.0}
    with pytest.raises(V2TrendPullbackError):
        V2TrendPullbackCandidate(**kwargs)


# ============================================================================
# 14. FROZEN CONSTANTS
# ============================================================================
def test_frozen_family_constants():
    assert LOOKBACK_15M == 48
    assert PULLBACK_MIN_MULT == 0.5
    assert PULLBACK_MAX_MULT == 3.0
    assert PULLBACK_MAX_AGE_15M_BUCKETS == 8
    assert RESUMPTION_MIN_BUCKETS == 1
    assert EXPECTED_HORIZON == timedelta(hours=2)


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
    body_src = _executable_body_source(tp_module)
    forbidden = (
        "EARLY_SIGNAL", "CONFIRMED", "WEAKENING", "INVALIDATED", "EXPIRED", "COMPLETED",
        "episode_id", "event_id", "persist_v2_episode_event", "active episode",
        "cooldown", "dedup", "model_confidence",
    )
    for token in forbidden:
        assert token not in body_src, f"forbidden Stage 6 token found: {token!r}"


def test_no_other_setup_families_implemented():
    body_src = _executable_body_source(tp_module)
    forbidden = ("COMPRESSION_BREAKOUT", "CONFIRMED_BREAKOUT", "compression_score", "range_high",
                "range_low", "resistance_level", "support_level")
    for token in forbidden:
        assert token not in body_src, f"forbidden other-family token found: {token!r}"


def test_no_confirmation_or_expiry_evaluated():
    # PULLBACK_MAX_AGE_15M_BUCKETS/RESUMPTION_MIN_BUCKETS are exposed as
    # metadata only -- never counted/evaluated by detect_trend_pullback.
    src = inspect.getsource(tp_module.detect_trend_pullback)
    assert "PULLBACK_MAX_AGE_15M_BUCKETS" not in src
    assert "RESUMPTION_MIN_BUCKETS" not in src


# ============================================================================
# 16. PURITY
# ============================================================================
def test_module_has_no_clock_random_uuid_network_filesystem_access():
    body_src = _executable_body_source(tp_module)
    forbidden = (
        "datetime.now(", "datetime.utcnow(", "time.time(", "time.monotonic(",
        "import random", "import uuid", "import yaml", "os.environ", "os.getenv",
        "requests.", "httpx.", "open(", "asyncpg", "subprocess",
    )
    for token in forbidden:
        assert token not in body_src, f"forbidden token found: {token!r}"


def test_module_imports_nothing_from_storage_runtime_main_notifications():
    tree = ast.parse(inspect.getsource(tp_module))
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        for name in names:
            for banned in ("storage", "runtime", "main", "notifications"):
                assert not name.startswith(banned), f"forbidden import: {name}"


def test_detect_trend_pullback_is_synchronous():
    assert not inspect.iscoroutinefunction(detect_trend_pullback)
