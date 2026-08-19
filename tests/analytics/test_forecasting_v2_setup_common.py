"""Tests for analytics/forecasting_v2/setup_common.py (Stage 5 — Setup
Detectors, PR 1 of ~4, shared foundation only — no detector logic
exists). No DB, no async — pure math/gate tests over hand-constructed
`V2ContextSnapshot`/`Mapping` fixtures, following the existing V2
analytics test style (tests/analytics/test_forecasting_v2_regime_4h.py,
tests/analytics/test_forecasting_v2_context_snapshot.py).

Exercises: §7.0b's `directional_context_gate` frozen decision tree
(4h availability, 4h opposition, 1h availability, 1h opposition,
otherwise ACCEPT, evaluated in that exact order, preserving all four
distinct rejection categories); §7's `RANGE_PROXY_pct` exact-14-bucket
grid (no partial mean, corruption precedence); §7's `protection_buffer`
(tick floor vs. volatility term, `None` propagation); §7.0c's
deterministic most-recent-tie extreme selection (full-precision
comparison, input-order independence).
"""
from __future__ import annotations

import ast
import inspect
from datetime import datetime, timedelta, timezone

import pytest

from analytics.forecasting_v2 import setup_common as setup_common_module
from analytics.forecasting_v2.bias_1h import BEARISH, BIAS_UNAVAILABLE, BULLISH, NEUTRAL_NOT_ESTABLISHED
from analytics.forecasting_v2.bias_1h import V2BiasResult
from analytics.forecasting_v2.context_snapshot import V2ContextSnapshot
from analytics.forecasting_v2.events import LONG, SHORT
from analytics.forecasting_v2.regime_4h import (
    BEARISH_TRENDING, BULLISH_TRENDING, INSUFFICIENT_DATA, NON_DIRECTIONAL, V2RegimeResult,
)
from analytics.forecasting_v2.setup_common import (
    BUFFER_MULTIPLIER,
    CONTEXT_ACCEPT,
    MIN_TICK_BUFFER_TICKS,
    RANGE_PROXY_N,
    REJECT_BIAS_OPPOSES,
    REJECT_BIAS_UNAVAILABLE,
    REJECT_REGIME_OPPOSES,
    REJECT_REGIME_UNAVAILABLE,
    SETUP_MIN_CONFIDENCE,
    SETUP_MIN_COVERAGE,
    SETUP_RANGE_TIMEFRAMES,
    V2DirectionalContextDecision,
    V2ExtremeAnchor,
    V2SetupFoundationError,
    directional_context_gate,
    protection_buffer,
    range_proxy_pct,
    select_extreme_anchor,
)

UTC = timezone.utc
H16 = "a" * 16
T = datetime(2026, 8, 15, 12, 10, tzinfo=UTC)
B4H = datetime(2026, 8, 15, 8, 0, tzinfo=UTC)
B1H = datetime(2026, 8, 15, 11, 0, tzinfo=UTC)
B15 = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
B1H_GRID = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)


# ============================================================================
# fixtures
# ============================================================================
_PRICE_EVI_FOR_REGIME = {
    BULLISH_TRENDING: 0.5, BEARISH_TRENDING: -0.5, NON_DIRECTIONAL: None, INSUFFICIENT_DATA: None,
}
_BIAS_EVI_FOR_BIAS = {
    BULLISH: 0.5, BEARISH: -0.5, NEUTRAL_NOT_ESTABLISHED: None, BIAS_UNAVAILABLE: None,
}


def make_snapshot(regime: str, bias: str, *, is_compressed=None) -> V2ContextSnapshot:
    if is_compressed is None and regime == NON_DIRECTIONAL:
        is_compressed = False
    compression_score = None
    if regime == NON_DIRECTIONAL:
        compression_score = 0.9 if is_compressed else 0.5
    return V2ContextSnapshot(
        T=T, symbol="BTCUSDT", market_type="perp", calculation_version=H16,
        feature_schema_version=1,
        regime_4h=V2RegimeResult(
            bucket_ts=B4H, regime=regime, is_compressed=is_compressed,
            price_evi=_PRICE_EVI_FOR_REGIME[regime], compression_score=compression_score),
        bias_1h=V2BiasResult(bucket_ts=B1H, bias=bias, bias_evi=_BIAS_EVI_FOR_BIAS[bias]),
    )


# ============================================================================
# 1. DIRECTIONAL CONTEXT GATE — §7.0b exact matrix (§37)
# ============================================================================
@pytest.mark.parametrize("regime,bias,direction,expected_accept,expected_reason", [
    # ---- LONG ----
    (BULLISH_TRENDING, BULLISH, LONG, True, CONTEXT_ACCEPT),
    (BEARISH_TRENDING, BULLISH, LONG, False, REJECT_REGIME_OPPOSES),
    (BEARISH_TRENDING, BEARISH, LONG, False, REJECT_REGIME_OPPOSES),
    (BEARISH_TRENDING, NEUTRAL_NOT_ESTABLISHED, LONG, False, REJECT_REGIME_OPPOSES),
    (BEARISH_TRENDING, BIAS_UNAVAILABLE, LONG, False, REJECT_REGIME_OPPOSES),
    (NON_DIRECTIONAL, BULLISH, LONG, True, CONTEXT_ACCEPT),
    (NON_DIRECTIONAL, BEARISH, LONG, False, REJECT_BIAS_OPPOSES),
    (NON_DIRECTIONAL, NEUTRAL_NOT_ESTABLISHED, LONG, True, CONTEXT_ACCEPT),
    (NON_DIRECTIONAL, BIAS_UNAVAILABLE, LONG, False, REJECT_BIAS_UNAVAILABLE),
    (INSUFFICIENT_DATA, BULLISH, LONG, False, REJECT_REGIME_UNAVAILABLE),
    (INSUFFICIENT_DATA, BEARISH, LONG, False, REJECT_REGIME_UNAVAILABLE),
    (INSUFFICIENT_DATA, NEUTRAL_NOT_ESTABLISHED, LONG, False, REJECT_REGIME_UNAVAILABLE),
    (INSUFFICIENT_DATA, BIAS_UNAVAILABLE, LONG, False, REJECT_REGIME_UNAVAILABLE),
    (BULLISH_TRENDING, NEUTRAL_NOT_ESTABLISHED, LONG, True, CONTEXT_ACCEPT),
    (BULLISH_TRENDING, BIAS_UNAVAILABLE, LONG, False, REJECT_BIAS_UNAVAILABLE),
    # ---- SHORT (symmetric) ----
    (BEARISH_TRENDING, BEARISH, SHORT, True, CONTEXT_ACCEPT),
    (BULLISH_TRENDING, BEARISH, SHORT, False, REJECT_REGIME_OPPOSES),
    (BULLISH_TRENDING, BULLISH, SHORT, False, REJECT_REGIME_OPPOSES),
    (BULLISH_TRENDING, NEUTRAL_NOT_ESTABLISHED, SHORT, False, REJECT_REGIME_OPPOSES),
    (BULLISH_TRENDING, BIAS_UNAVAILABLE, SHORT, False, REJECT_REGIME_OPPOSES),
    (NON_DIRECTIONAL, BEARISH, SHORT, True, CONTEXT_ACCEPT),
    (NON_DIRECTIONAL, BULLISH, SHORT, False, REJECT_BIAS_OPPOSES),
    (NON_DIRECTIONAL, NEUTRAL_NOT_ESTABLISHED, SHORT, True, CONTEXT_ACCEPT),
    (NON_DIRECTIONAL, BIAS_UNAVAILABLE, SHORT, False, REJECT_BIAS_UNAVAILABLE),
    (INSUFFICIENT_DATA, BEARISH, SHORT, False, REJECT_REGIME_UNAVAILABLE),
    (BEARISH_TRENDING, NEUTRAL_NOT_ESTABLISHED, SHORT, True, CONTEXT_ACCEPT),
    (BEARISH_TRENDING, BIAS_UNAVAILABLE, SHORT, False, REJECT_BIAS_UNAVAILABLE),
])
def test_gate_exact_matrix(regime, bias, direction, expected_accept, expected_reason):
    decision = directional_context_gate(make_snapshot(regime, bias), direction)
    assert decision.accepted is expected_accept
    assert decision.reason == expected_reason


def test_gate_precedence_regime_insufficient_beats_bias_opposite():
    # §7.0b evaluates 4h BEFORE 1h -- regime unavailability wins even when
    # bias would separately have opposed.
    decision = directional_context_gate(make_snapshot(INSUFFICIENT_DATA, BEARISH), LONG)
    assert decision.accepted is False
    assert decision.reason == REJECT_REGIME_UNAVAILABLE


def test_gate_precedence_regime_opposes_beats_bias_unavailable():
    decision = directional_context_gate(make_snapshot(BEARISH_TRENDING, BIAS_UNAVAILABLE), LONG)
    assert decision.accepted is False
    assert decision.reason == REJECT_REGIME_OPPOSES


def test_gate_neutral_context_both_directions_accept():
    for direction in (LONG, SHORT):
        decision = directional_context_gate(
            make_snapshot(NON_DIRECTIONAL, NEUTRAL_NOT_ESTABLISHED), direction)
        assert decision.accepted is True
        assert decision.reason == CONTEXT_ACCEPT


# ============================================================================
# 2. GATE HARDENING (§38)
# ============================================================================
@pytest.mark.parametrize("bad_direction", ["long", "BUY", None, "LONG ", "short", 1, ()])
def test_gate_rejects_malformed_direction(bad_direction):
    with pytest.raises(V2SetupFoundationError):
        directional_context_gate(make_snapshot(NON_DIRECTIONAL, NEUTRAL_NOT_ESTABLISHED),
                                 bad_direction)


@pytest.mark.parametrize("bad_context", ["not-a-snapshot", None, 123, {}])
def test_gate_rejects_malformed_context(bad_context):
    with pytest.raises(V2SetupFoundationError):
        directional_context_gate(bad_context, LONG)


def test_gate_does_not_infer_direction_from_context():
    # Both directions must be independently evaluated against the SAME
    # context -- the gate never derives breakout_direction on its own.
    snap = make_snapshot(BULLISH_TRENDING, BULLISH)
    long_decision = directional_context_gate(snap, LONG)
    short_decision = directional_context_gate(snap, SHORT)
    assert long_decision.accepted is True
    assert short_decision.accepted is False
    assert short_decision.reason == REJECT_REGIME_OPPOSES


# ============================================================================
# 3. RESULT MODEL — V2DirectionalContextDecision self-validation
# ============================================================================
def test_decision_accept_requires_context_accept_reason():
    with pytest.raises(V2SetupFoundationError):
        V2DirectionalContextDecision(accepted=True, reason="something else")


def test_decision_accept_true_with_correct_reason_is_valid():
    d = V2DirectionalContextDecision(accepted=True, reason=CONTEXT_ACCEPT)
    assert d.accepted is True


@pytest.mark.parametrize("reason", [
    REJECT_REGIME_UNAVAILABLE, REJECT_REGIME_OPPOSES,
    REJECT_BIAS_UNAVAILABLE, REJECT_BIAS_OPPOSES,
])
def test_decision_reject_accepts_all_four_reasons(reason):
    d = V2DirectionalContextDecision(accepted=False, reason=reason)
    assert d.accepted is False
    assert d.reason == reason


def test_decision_reject_rejects_accept_reason():
    with pytest.raises(V2SetupFoundationError):
        V2DirectionalContextDecision(accepted=False, reason=CONTEXT_ACCEPT)


def test_decision_reject_rejects_none_reason():
    with pytest.raises(V2SetupFoundationError):
        V2DirectionalContextDecision(accepted=False, reason=None)


def test_decision_rejects_non_bool_accepted():
    with pytest.raises(V2SetupFoundationError):
        V2DirectionalContextDecision(accepted=1, reason=CONTEXT_ACCEPT)  # type: ignore[arg-type]


def test_decision_is_frozen():
    d = V2DirectionalContextDecision(accepted=True, reason=CONTEXT_ACCEPT)
    with pytest.raises(Exception):
        d.accepted = False  # type: ignore[misc]


# ============================================================================
# 4. RANGE PROXY — exact 14-bucket grid (§10-14, §39)
# ============================================================================
def _grid_rows(base: datetime, timeframe: str, minutes: int, values):
    tf = timedelta(minutes=minutes)
    n = len(values)
    return [
        {"timeframe": timeframe, "bucket_ts": base - (n - 1 - i) * tf,
         "range_width_pct_median": values[i]}
        for i in range(n)
    ]


def test_range_proxy_all_equal_values():
    rows = _grid_rows(B15, "15m", 15, [1.0] * RANGE_PROXY_N)
    assert range_proxy_pct(rows, timeframe="15m", bucket_ts=B15) == 1.0


def test_range_proxy_known_sequence_exact_mean():
    values = [float(i) for i in range(RANGE_PROXY_N)]
    rows = _grid_rows(B15, "15m", 15, values)
    result = range_proxy_pct(rows, timeframe="15m", bucket_ts=B15)
    assert result == sum(values) / RANGE_PROXY_N


def test_range_proxy_1h_timeframe():
    rows = _grid_rows(B1H_GRID, "1h", 60, [2.0] * RANGE_PROXY_N)
    assert range_proxy_pct(rows, timeframe="1h", bucket_ts=B1H_GRID) == 2.0


def test_range_proxy_missing_first_bucket_is_unavailable():
    rows = _grid_rows(B15, "15m", 15, [1.0] * RANGE_PROXY_N)[1:]
    assert range_proxy_pct(rows, timeframe="15m", bucket_ts=B15) is None


def test_range_proxy_missing_middle_bucket_is_unavailable():
    rows = _grid_rows(B15, "15m", 15, [1.0] * RANGE_PROXY_N)
    del rows[7]
    assert range_proxy_pct(rows, timeframe="15m", bucket_ts=B15) is None


def test_range_proxy_missing_last_bucket_is_unavailable():
    rows = _grid_rows(B15, "15m", 15, [1.0] * RANGE_PROXY_N)[:-1]
    assert range_proxy_pct(rows, timeframe="15m", bucket_ts=B15) is None


def test_range_proxy_duplicate_bucket_raises():
    rows = _grid_rows(B15, "15m", 15, [1.0] * RANGE_PROXY_N)
    rows.append(rows[0])
    with pytest.raises(V2SetupFoundationError):
        range_proxy_pct(rows, timeframe="15m", bucket_ts=B15)


def test_range_proxy_unexpected_extra_bucket_raises():
    rows = _grid_rows(B15, "15m", 15, [1.0] * RANGE_PROXY_N)
    rows.append({"timeframe": "15m", "bucket_ts": B15 + timedelta(minutes=15),
                 "range_width_pct_median": 1.0})
    with pytest.raises(V2SetupFoundationError):
        range_proxy_pct(rows, timeframe="15m", bucket_ts=B15)


def test_range_proxy_wrong_requested_timeframe_raises():
    rows = _grid_rows(B15, "15m", 15, [1.0] * RANGE_PROXY_N)
    with pytest.raises(V2SetupFoundationError):
        range_proxy_pct(rows, timeframe="4h", bucket_ts=B15)


def test_range_proxy_row_with_wrong_own_timeframe_field_raises():
    rows = _grid_rows(B15, "15m", 15, [1.0] * RANGE_PROXY_N)
    rows[-1] = {**rows[-1], "timeframe": "1h"}
    with pytest.raises(V2SetupFoundationError):
        range_proxy_pct(rows, timeframe="15m", bucket_ts=B15)


def test_range_proxy_row_outside_expected_grid_raises():
    rows = _grid_rows(B15, "15m", 15, [1.0] * RANGE_PROXY_N)
    rows[0] = {**rows[0], "bucket_ts": B15 - timedelta(minutes=15 * 20)}
    with pytest.raises(V2SetupFoundationError):
        range_proxy_pct(rows, timeframe="15m", bucket_ts=B15)


def test_range_proxy_value_none_is_unavailable():
    rows = _grid_rows(B15, "15m", 15, [1.0] * RANGE_PROXY_N)
    rows[-1] = {**rows[-1], "range_width_pct_median": None}
    assert range_proxy_pct(rows, timeframe="15m", bucket_ts=B15) is None


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1.0, True, "1.0"])
def test_range_proxy_malformed_value_raises(bad):
    rows = _grid_rows(B15, "15m", 15, [1.0] * RANGE_PROXY_N)
    rows[-1] = {**rows[-1], "range_width_pct_median": bad}
    with pytest.raises(V2SetupFoundationError):
        range_proxy_pct(rows, timeframe="15m", bucket_ts=B15)


def test_range_proxy_corruption_precedence_missing_plus_malformed_raises_not_none():
    # One expected bucket missing entirely AND one present row malformed
    # -- must raise, never silently return None.
    rows = _grid_rows(B15, "15m", 15, [1.0] * RANGE_PROXY_N)[1:]  # drop first
    rows[-1] = {**rows[-1], "range_width_pct_median": float("nan")}
    with pytest.raises(V2SetupFoundationError):
        range_proxy_pct(rows, timeframe="15m", bucket_ts=B15)


def test_range_proxy_non_mapping_row_raises():
    rows = _grid_rows(B15, "15m", 15, [1.0] * RANGE_PROXY_N)
    rows[0] = "not-a-mapping"
    with pytest.raises(V2SetupFoundationError):
        range_proxy_pct(rows, timeframe="15m", bucket_ts=B15)


def test_range_proxy_naive_bucket_ts_raises():
    rows = _grid_rows(B15, "15m", 15, [1.0] * RANGE_PROXY_N)
    with pytest.raises(V2SetupFoundationError):
        range_proxy_pct(rows, timeframe="15m", bucket_ts=datetime(2026, 8, 15, 12, 0))


def test_setup_range_timeframes_is_exactly_15m_and_1h():
    assert SETUP_RANGE_TIMEFRAMES == ("15m", "1h")


def test_range_proxy_n_is_exactly_14():
    assert RANGE_PROXY_N == 14


# ============================================================================
# 3b. SHARED SETUP-TIMEFRAME CONSENSUS QUALITY GATE — §6.2/§6.3, reused
# at every timeframe (not a new parameter).
# ============================================================================
def test_setup_min_coverage_is_exactly_two_thirds():
    assert SETUP_MIN_COVERAGE == pytest.approx(2.0 / 3.0)


def test_setup_min_confidence_is_exactly_50():
    assert SETUP_MIN_CONFIDENCE == 50.0


# ============================================================================
# 4b. RANGE PROXY — bucket-grid alignment hardening (pre-merge amendment).
# bucket_ts must be a legal CLOSED-bucket START on timeframe's own
# canonical UTC grid, not merely aware/UTC/whole-minute. Illegal vectors
# are exercised with rows=[] -- the grid check runs BEFORE any row
# iteration, so an illegal bucket_ts raises regardless of what `rows`
# contains. Legal vectors (including non-midnight/historical ones) are
# exercised the same way and must NOT raise -- an empty `rows` still
# legitimately returns None (incomplete window), never an error.
# ============================================================================
def test_range_proxy_15m_legal_bucket_start_accepted():
    assert range_proxy_pct([], timeframe="15m", bucket_ts=B15) is None  # no exception


@pytest.mark.parametrize("bad_minute", [1, 7, 14])
def test_range_proxy_15m_illegal_bucket_start_raises(bad_minute):
    bad_bucket_ts = B15.replace(minute=bad_minute)
    with pytest.raises(V2SetupFoundationError):
        range_proxy_pct([], timeframe="15m", bucket_ts=bad_bucket_ts)


def test_range_proxy_1h_legal_bucket_start_accepted():
    assert range_proxy_pct([], timeframe="1h", bucket_ts=B1H_GRID) is None  # no exception


@pytest.mark.parametrize("bad_minute", [5, 30])
def test_range_proxy_1h_illegal_bucket_start_raises(bad_minute):
    bad_bucket_ts = B1H_GRID.replace(minute=bad_minute)
    with pytest.raises(V2SetupFoundationError):
        range_proxy_pct([], timeframe="1h", bucket_ts=bad_bucket_ts)


def test_range_proxy_15m_legal_non_midnight_historical_bucket_accepted():
    # A legal 15m bucket start far from the module's default fixture time
    # and not on the hour -- proves the grid check is a real grid
    # invariant, not merely "matches B15 by coincidence."
    historical = datetime(2020, 3, 1, 13, 45, tzinfo=UTC)
    rows = _grid_rows(historical, "15m", 15, [3.0] * RANGE_PROXY_N)
    assert range_proxy_pct(rows, timeframe="15m", bucket_ts=historical) == 3.0


def test_range_proxy_1h_legal_non_midnight_historical_bucket_accepted():
    historical = datetime(2020, 3, 1, 5, 0, tzinfo=UTC)
    rows = _grid_rows(historical, "1h", 60, [4.0] * RANGE_PROXY_N)
    assert range_proxy_pct(rows, timeframe="1h", bucket_ts=historical) == 4.0


def test_range_proxy_illegal_bucket_start_never_silently_floored():
    # The bucket-grid check must reject, never floor bucket_ts=12:07 down
    # to 12:00 on the caller's behalf -- confirmed by the fact this raises
    # rather than silently returning the same result as bucket_ts=12:00
    # would (see test_range_proxy_15m_illegal_bucket_start_raises above).
    with pytest.raises(V2SetupFoundationError):
        range_proxy_pct([], timeframe="15m", bucket_ts=B15.replace(minute=7))


# ============================================================================
# 4c. TOP-LEVEL ROW/CANDIDATE CONTAINER HARDENING (pre-merge amendment) --
# range_proxy_pct(rows=...)/select_extreme_anchor(candidates=...) must
# reject a top-level argument that is not a legitimate row/candidate
# container (None, a bare str) with V2SetupFoundationError rather than an
# incidental Python iteration error -- never treating a string/bytes value
# as if it were a sequence of rows.
# ============================================================================
@pytest.mark.parametrize("bad_rows", [None, "not rows"])
def test_range_proxy_rejects_non_sequence_rows(bad_rows):
    with pytest.raises(V2SetupFoundationError):
        range_proxy_pct(bad_rows, timeframe="15m", bucket_ts=B15)


@pytest.mark.parametrize("bad_candidates", [None, "not candidates"])
def test_extreme_rejects_non_sequence_candidates(bad_candidates):
    with pytest.raises(V2SetupFoundationError):
        select_extreme_anchor(bad_candidates, mode="max")


def test_extreme_empty_list_still_returns_none_unchanged():
    # A legitimate empty sequence remains distinct from a malformed
    # top-level container -- must not be swept up by the new hardening.
    assert select_extreme_anchor([], mode="max") is None


# ============================================================================
# 5. PROTECTION BUFFER — §15-17
# ============================================================================
def test_protection_buffer_tick_floor_wins():
    result = protection_buffer(reference_price=100.0, range_proxy_pct_value=0.001, tick_size=1.0)
    assert result == 3.0 * 1.0


def test_protection_buffer_volatility_term_wins():
    result = protection_buffer(
        reference_price=100000.0, range_proxy_pct_value=1.0, tick_size=0.01)
    assert result == 500.0


def test_protection_buffer_exact_equality():
    # tick_floor = 3*1.0 = 3.0; volatility = 600*1.0/100*0.5 = 3.0
    result = protection_buffer(reference_price=600.0, range_proxy_pct_value=1.0, tick_size=1.0)
    assert result == 3.0


def test_protection_buffer_range_proxy_zero_is_tick_floor():
    result = protection_buffer(reference_price=100.0, range_proxy_pct_value=0.0, tick_size=2.0)
    assert result == 6.0


def test_protection_buffer_range_proxy_none_is_none():
    result = protection_buffer(reference_price=100.0, range_proxy_pct_value=None, tick_size=1.0)
    assert result is None


@pytest.mark.parametrize("kwargs", [
    dict(reference_price=0.0, range_proxy_pct_value=1.0, tick_size=1.0),
    dict(reference_price=-1.0, range_proxy_pct_value=1.0, tick_size=1.0),
    dict(reference_price=100.0, range_proxy_pct_value=1.0, tick_size=0.0),
    dict(reference_price=100.0, range_proxy_pct_value=1.0, tick_size=-1.0),
    dict(reference_price=float("nan"), range_proxy_pct_value=1.0, tick_size=1.0),
    dict(reference_price=float("inf"), range_proxy_pct_value=1.0, tick_size=1.0),
    dict(reference_price=True, range_proxy_pct_value=1.0, tick_size=1.0),
    dict(reference_price="100", range_proxy_pct_value=1.0, tick_size=1.0),
    dict(reference_price=100.0, range_proxy_pct_value=-1.0, tick_size=1.0),
    dict(reference_price=100.0, range_proxy_pct_value=float("nan"), tick_size=1.0),
    dict(reference_price=100.0, range_proxy_pct_value=1.0, tick_size=True),
])
def test_protection_buffer_malformed_raises(kwargs):
    with pytest.raises(V2SetupFoundationError):
        protection_buffer(**kwargs)


def test_protection_buffer_malformed_price_raises_even_when_proxy_none():
    # Corruption precedence: malformed PRESENT price/tick must raise
    # regardless of whether the volatility input is unavailable.
    with pytest.raises(V2SetupFoundationError):
        protection_buffer(reference_price=-1.0, range_proxy_pct_value=None, tick_size=1.0)


def test_protection_buffer_frozen_constants():
    assert MIN_TICK_BUFFER_TICKS == 3
    assert BUFFER_MULTIPLIER == 0.5


def test_protection_buffer_does_not_quantize_to_tick_size():
    # The formula is max(...), never a rounding/quantization step.
    result = protection_buffer(reference_price=333.0, range_proxy_pct_value=0.3, tick_size=0.7)
    volatility_term = 333.0 * 0.3 / 100.0 * 0.5
    assert result == max(3 * 0.7, volatility_term)
    assert result % 0.7 != 0  # not quantized to a tick multiple


# ============================================================================
# 6. EXTREME TIE-BREAK — §7.0c (§40)
# ============================================================================
def _cand(bucket_ts, value):
    return {"bucket_ts": bucket_ts, "value": value}


def test_extreme_max_tie_selects_most_recent():
    older = _cand(datetime(2026, 8, 15, 10, 0, tzinfo=UTC), 65000.0)
    newer = _cand(datetime(2026, 8, 15, 11, 0, tzinfo=UTC), 65000.0)
    result = select_extreme_anchor([older, newer], mode="max")
    assert result == V2ExtremeAnchor(bucket_ts=newer["bucket_ts"], value=65000.0)


def test_extreme_min_tie_selects_most_recent():
    older = _cand(datetime(2026, 8, 15, 10, 0, tzinfo=UTC), 100.0)
    newer = _cand(datetime(2026, 8, 15, 11, 0, tzinfo=UTC), 100.0)
    result = select_extreme_anchor([older, newer], mode="min")
    assert result == V2ExtremeAnchor(bucket_ts=newer["bucket_ts"], value=100.0)


def test_extreme_input_order_reversed_same_result():
    older = _cand(datetime(2026, 8, 15, 10, 0, tzinfo=UTC), 65000.0)
    newer = _cand(datetime(2026, 8, 15, 11, 0, tzinfo=UTC), 65000.0)
    mid = _cand(datetime(2026, 8, 15, 10, 30, tzinfo=UTC), 64000.0)
    forward = select_extreme_anchor([older, mid, newer], mode="max")
    reversed_ = select_extreme_anchor([newer, mid, older], mode="max")
    shuffled = select_extreme_anchor([mid, newer, older], mode="max")
    assert forward == reversed_ == shuffled


def test_extreme_three_way_tie_latest_wins():
    c1 = _cand(datetime(2026, 8, 15, 9, 0, tzinfo=UTC), 5.0)
    c2 = _cand(datetime(2026, 8, 15, 10, 0, tzinfo=UTC), 5.0)
    c3 = _cand(datetime(2026, 8, 15, 11, 0, tzinfo=UTC), 5.0)
    result = select_extreme_anchor([c2, c1, c3], mode="max")
    assert result.bucket_ts == c3["bucket_ts"]


def test_extreme_true_max_wins_irrespective_of_recency():
    early_high = _cand(datetime(2026, 8, 15, 9, 0, tzinfo=UTC), 999.0)
    late_low = _cand(datetime(2026, 8, 15, 11, 0, tzinfo=UTC), 500.0)
    result = select_extreme_anchor([early_high, late_low], mode="max")
    assert result.value == 999.0
    assert result.bucket_ts == early_high["bucket_ts"]


def test_extreme_full_precision_no_rounding():
    a = _cand(datetime(2026, 8, 15, 9, 0, tzinfo=UTC), 65000.00000001)
    b = _cand(datetime(2026, 8, 15, 10, 0, tzinfo=UTC), 65000.00000002)
    result = select_extreme_anchor([a, b], mode="max")
    # b is NOT a tie with a at full precision -- b wins outright, and its
    # own bucket_ts is selected (not merely "the more recent one" by
    # tie-break, since there is no tie here at all).
    assert result.value == 65000.00000002
    assert result.bucket_ts == b["bucket_ts"]


def test_extreme_duplicate_bucket_raises():
    ts = datetime(2026, 8, 15, 10, 0, tzinfo=UTC)
    with pytest.raises(V2SetupFoundationError):
        select_extreme_anchor([_cand(ts, 1.0), _cand(ts, 2.0)], mode="max")


def test_extreme_empty_sequence_returns_none():
    assert select_extreme_anchor([], mode="max") is None
    assert select_extreme_anchor([], mode="min") is None


def test_extreme_invalid_mode_raises():
    with pytest.raises(V2SetupFoundationError):
        select_extreme_anchor([_cand(datetime(2026, 8, 15, 10, 0, tzinfo=UTC), 1.0)], mode="MAX")


def test_extreme_non_mapping_candidate_raises():
    with pytest.raises(V2SetupFoundationError):
        select_extreme_anchor(["not-a-mapping"], mode="max")


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), True, "1.0"])
def test_extreme_malformed_value_raises(bad_value):
    with pytest.raises(V2SetupFoundationError):
        select_extreme_anchor(
            [{"bucket_ts": datetime(2026, 8, 15, 10, 0, tzinfo=UTC), "value": bad_value}],
            mode="max")


def test_extreme_naive_bucket_ts_raises():
    with pytest.raises(V2SetupFoundationError):
        select_extreme_anchor([{"bucket_ts": datetime(2026, 8, 15, 10, 0), "value": 1.0}],
                              mode="max")


def test_extreme_anchor_is_frozen():
    anchor = V2ExtremeAnchor(bucket_ts=datetime(2026, 8, 15, 10, 0, tzinfo=UTC), value=1.0)
    with pytest.raises(Exception):
        anchor.value = 2.0  # type: ignore[misc]


# ============================================================================
# 6b. V2ExtremeAnchor DIRECT-CONSTRUCTION SELF-VALIDATION (pre-merge
# amendment) -- public Stage 5 API; must self-validate on ANY direct
# construction, not only via select_extreme_anchor()'s own builder path.
# ============================================================================
def test_extreme_anchor_valid_direct_construction_accepted():
    anchor = V2ExtremeAnchor(bucket_ts=datetime(2026, 8, 15, 10, 0, tzinfo=UTC), value=65000.5)
    assert anchor.bucket_ts == datetime(2026, 8, 15, 10, 0, tzinfo=UTC)
    assert anchor.value == 65000.5


def test_extreme_anchor_rejects_naive_bucket_ts():
    with pytest.raises(V2SetupFoundationError):
        V2ExtremeAnchor(bucket_ts=datetime(2026, 8, 15, 10, 0), value=1.0)


def test_extreme_anchor_rejects_non_utc_bucket_ts():
    with pytest.raises(V2SetupFoundationError):
        V2ExtremeAnchor(
            bucket_ts=datetime(2026, 8, 15, 13, 0, tzinfo=timezone(timedelta(hours=3))),
            value=1.0)


def test_extreme_anchor_rejects_seconds_bucket_ts():
    with pytest.raises(V2SetupFoundationError):
        V2ExtremeAnchor(bucket_ts=datetime(2026, 8, 15, 10, 0, 1, tzinfo=UTC), value=1.0)


def test_extreme_anchor_rejects_microseconds_bucket_ts():
    with pytest.raises(V2SetupFoundationError):
        V2ExtremeAnchor(bucket_ts=datetime(2026, 8, 15, 10, 0, 0, 1, tzinfo=UTC), value=1.0)


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf"), True, False, "1.0"])
def test_extreme_anchor_rejects_malformed_value(bad_value):
    with pytest.raises(V2SetupFoundationError):
        V2ExtremeAnchor(bucket_ts=datetime(2026, 8, 15, 10, 0, tzinfo=UTC), value=bad_value)


def test_extreme_anchor_does_not_restrict_value_sign():
    # An abstract extreme helper may legitimately select any finite
    # numeric value -- negative values are not rejected.
    anchor = V2ExtremeAnchor(bucket_ts=datetime(2026, 8, 15, 10, 0, tzinfo=UTC), value=-500.0)
    assert anchor.value == -500.0


# ============================================================================
# 7. PURITY (§46)
# ============================================================================
def _executable_body_source(module) -> str:
    """Source with every docstring stripped (mirrors the same helper in
    tests/analytics/test_forecasting_v2_regime_4h.py /
    tests/analytics/test_forecasting_v2_bias_1h.py /
    tests/analytics/test_forecasting_v2_context_snapshot.py)."""
    tree = ast.parse(inspect.getsource(module))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)):
                node.body = node.body[1:] or [ast.Pass()]
    return ast.unparse(tree)


def test_module_has_no_clock_random_uuid_network_filesystem_access():
    body_src = _executable_body_source(setup_common_module)
    forbidden = (
        "datetime.now(", "datetime.utcnow(", "time.time(", "time.monotonic(",
        "import random", "import uuid", "import yaml", "os.environ", "os.getenv",
        "requests.", "httpx.", "open(", "asyncpg", "subprocess",
    )
    for token in forbidden:
        assert token not in body_src, f"forbidden token found: {token!r}"


def test_module_imports_nothing_from_storage_runtime_main_notifications():
    tree = ast.parse(inspect.getsource(setup_common_module))
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        for name in names:
            for banned in ("storage", "runtime", "main", "notifications"):
                assert not name.startswith(banned), f"forbidden import: {name}"


def test_all_public_functions_are_synchronous():
    for name in ("directional_context_gate", "range_proxy_pct", "protection_buffer",
                 "select_extreme_anchor"):
        fn = getattr(setup_common_module, name)
        assert not inspect.iscoroutinefunction(fn), f"{name} must be synchronous"


# ============================================================================
# 8. NO SETUP-DETECTOR LOGIC REGRESSION (§47) — source-level guarantee this
# PR does ZERO detector/episode/lifecycle work.
# ============================================================================
def test_no_detector_or_episode_logic_implemented_yet():
    body_src = _executable_body_source(setup_common_module)
    forbidden = (
        "detect_trend_pullback", "detect_compression_breakout", "detect_confirmed_breakout",
        "EARLY_SIGNAL", "CONFIRMED", "entry_zone", "invalidation_price",
        "structural_anchor", "confirmation_deadline", "false_break", "episode",
        "state_transition", "TREND_PULLBACK", "COMPRESSION_BREAKOUT", "CONFIRMED_BREAKOUT",
    )
    for token in forbidden:
        assert token not in body_src, f"forbidden Stage 5 detector token found: {token!r}"
