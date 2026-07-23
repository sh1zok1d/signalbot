"""Unit tests for analytics/forecasting/outcomes.py.

Pure/deterministic — no DB, network, clock. Real ForecastPrediction objects built
through compute_forecast_decision -> build_forecast_prediction; real price bars.
"""
from __future__ import annotations

import ast
import dataclasses
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import pytest

from analytics.feature_engine.consensus_models import ConsensusFeatureVector
from analytics.forecasting import (
    LONG, NEUTRAL, SHORT, compute_forecast_decision, build_forecast_prediction,
)
from analytics.forecasting.outcomes import (
    DEFAULT_OUTCOME_VERSION, EVALUATION_PRICE_SOURCE, ForecastOutcome,
    ForecastOutcomeEvaluation, ForecastOutcomeInputError, ForecastOutcomeWindow,
    OUTCOME_COMPLETE, OUTCOME_HORIZON_MINUTES, OUTCOME_INCOMPLETE, OutcomePriceBar,
    build_forecast_outcome_window, evaluate_forecast_outcome,
)

UTC = timezone.utc
B = datetime(2026, 3, 1, 0, 0, 0, tzinfo=UTC)          # bucket OPEN (5m aligned)
REF = 100.0
SRC = "binance_close_5m"


def _cv(**over) -> ConsensusFeatureVector:
    base = dict(
        symbol="BTCUSDT", market_type="perp", timeframe="5m", bucket_ts=B,
        feature_schema_version=1, calculation_version="0123456789abcdef",
        coverage_by_metric=MappingProxyType({}), provenance_by_metric=MappingProxyType({}),
        data_confidence_by_metric=MappingProxyType({}),
        exchanges_expected_max=3, min_coverage_ratio=1.0, data_confidence_overall=80.0,
        price_direction_agreement=1.0, flow_direction_agreement=1.0, oi_direction_agreement=1.0,
        price_move_pct_median=0.4, range_width_pct_median=1.0, oi_change_pct_median=0.5,
        funding_rate_median=0.0001, funding_rate_mad=0.0,
        volume_notional_usd_sum=1000.0, taker_buy_notional_usd_sum=800.0,
        taker_sell_notional_usd_sum=200.0, taker_delta_notional_usd_sum=600.0,
        cvd_delta_notional_usd_sum=600.0,
        observed_long_liquidation_notional_sum=100.0,
        observed_short_liquidation_notional_sum=900.0,
        observed_liquidation_event_count_sum=5,
        liquidation_feed_quality_by_exchange=MappingProxyType({}),
        price_move_pct_mad=0.0, oi_change_pct_mad=0.0, outlier_exchanges=MappingProxyType({}),
        consensus_confidence=80.0, is_partial_consensus=False,
        config_hash="a" * 64, config_version="2.1.0", code_version="code-v1")
    base.update(over)
    return ConsensusFeatureVector(**base)


def _pred(cv, *, reference_price=REF, reference_price_source=SRC):
    return build_forecast_prediction(
        compute_forecast_decision(cv), cv,
        reference_price=reference_price, reference_price_source=reference_price_source)


def _pred_long(**o):
    return _pred(_cv(), **o)


def _pred_short(**o):
    return _pred(_cv(price_move_pct_median=-0.4, taker_buy_notional_usd_sum=200.0,
                     taker_sell_notional_usd_sum=800.0, taker_delta_notional_usd_sum=-600.0,
                     observed_long_liquidation_notional_sum=900.0,
                     observed_short_liquidation_notional_sum=100.0,
                     funding_rate_median=-0.0001), **o)


def _pred_neutral(**o):
    return _pred(_cv(min_coverage_ratio=1.0 / 3.0), **o)


def _bar(ts, o, h, low, c, *, exchange="binance", symbol="BTCUSDT"):
    return OutcomePriceBar(exchange, symbol, ts, o, h, low, c)


def _grid(window, ohlc=lambda i: (100.0, 100.0, 100.0, 100.0)):
    start = window.evaluation_start_ts
    return [_bar(start + timedelta(minutes=i), *ohlc(i)) for i in range(window.bars_expected)]


# Deterministic 15m OHLC: window high 110 (bar0), low 95 (bar0), target close 105 (bar14).
def _ohlc_known(i):
    if i == 0:
        return (100.0, 110.0, 95.0, 100.0)
    if i == 14:
        return (104.0, 106.0, 103.0, 105.0)
    return (100.0, 101.0, 99.0, 100.0)


# ============================================================================
# A. window boundaries
# ============================================================================
@pytest.mark.parametrize("horizon,end_min,target_min,bars", [
    ("15m", 20, 19, 15), ("1h", 65, 64, 60), ("4h", 245, 244, 240)])
def test_window_boundaries(horizon, end_min, target_min, bars):
    w = build_forecast_outcome_window(_pred_long(), horizon=horizon, evaluation_exchange="binance")
    assert w.evaluation_start_ts == B + timedelta(minutes=5)
    assert w.evaluation_end_ts == B + timedelta(minutes=end_min)
    assert w.target_bar_ts == B + timedelta(minutes=target_min)
    assert w.bars_expected == bars == OUTCOME_HORIZON_MINUTES[horizon]
    assert w.evaluation_price_source == EVALUATION_PRICE_SOURCE
    assert w.outcome_version == DEFAULT_OUTCOME_VERSION


# ============================================================================
# B. request validation
# ============================================================================
def test_window_rejects_non_prediction():
    with pytest.raises(ForecastOutcomeInputError):
        build_forecast_outcome_window(object(), horizon="15m", evaluation_exchange="binance")


@pytest.mark.parametrize("over", [
    dict(horizon="30m"), dict(horizon="5m"),
    dict(evaluation_exchange="kraken"), dict(outcome_version="  "),
])
def test_window_rejects_bad_args(over):
    kw = dict(horizon="15m", evaluation_exchange="binance")
    kw.update(over)
    with pytest.raises(ForecastOutcomeInputError):
        build_forecast_outcome_window(_pred_long(), **kw)


def test_window_rejects_horizon_not_in_prediction():
    # Build a prediction whose horizon_set excludes "15m" (via a custom rule set),
    # then request "15m": the builder must reject it even though "15m" is a valid
    # outcome horizon.
    from analytics.forecasting.models import DEFAULT_FORECAST_RULES
    cv = _cv()
    rules = dataclasses.replace(DEFAULT_FORECAST_RULES, horizons=("1h", "4h"))
    decision = compute_forecast_decision(cv, rules)
    p = build_forecast_prediction(decision, cv, reference_price=REF, reference_price_source=SRC)
    assert "15m" not in p.horizon_set
    with pytest.raises(ForecastOutcomeInputError):
        build_forecast_outcome_window(p, horizon="15m", evaluation_exchange="binance")


def test_window_source_alignment_required():
    p = _pred_long(reference_price_source="binance_close_5m")
    build_forecast_outcome_window(p, horizon="15m", evaluation_exchange="binance")  # ok
    with pytest.raises(ForecastOutcomeInputError):
        build_forecast_outcome_window(p, horizon="15m", evaluation_exchange="bybit")  # mismatch


# ============================================================================
# C. OutcomePriceBar validation
# ============================================================================
@pytest.mark.parametrize("over", [
    dict(exchange="kraken"), dict(symbol="ETHUSDT"),
    dict(ts=datetime(2026, 3, 1, 0, 5, 0)),                       # naive
    dict(ts=datetime(2026, 3, 1, 0, 5, 30, tzinfo=UTC)),         # not whole minute
    dict(open=True), dict(high="x"), dict(low=float("nan")),
    dict(close=float("inf")), dict(open=0.0), dict(low=-1.0),
])
def test_price_bar_rejects_bad_fields(over):
    kw = dict(exchange="binance", symbol="BTCUSDT",
              ts=datetime(2026, 3, 1, 0, 5, tzinfo=UTC),
              o=100.0, h=101.0, low=99.0, c=100.0)
    # map override keys to constructor
    args = dict(exchange=kw["exchange"], symbol=kw["symbol"], ts=kw["ts"],
                open=kw["o"], high=kw["h"], low=kw["low"], close=kw["c"])
    args.update(over)
    with pytest.raises(ForecastOutcomeInputError):
        OutcomePriceBar(**args)


@pytest.mark.parametrize("o,h,low,c", [
    (100.0, 99.0, 100.0, 100.0),        # high < low
    (100.0, 101.0, 99.0, 102.0),        # close > high
    (98.0, 101.0, 99.0, 100.0),         # open < low
])
def test_price_bar_ohlc_ordering(o, h, low, c):
    with pytest.raises(ForecastOutcomeInputError):
        OutcomePriceBar("binance", "BTCUSDT", datetime(2026, 3, 1, 0, 5, tzinfo=UTC), o, h, low, c)


# ============================================================================
# D. complete LONG
# ============================================================================
def test_complete_long_exact_metrics():
    p = _pred_long()
    assert p.direction == LONG
    w = build_forecast_outcome_window(p, horizon="15m", evaluation_exchange="binance")
    ev = evaluate_forecast_outcome(p, w, price_bars=_grid(w, _ohlc_known))
    assert ev.status == OUTCOME_COMPLETE and ev.missing_bar_ts == ()
    o = ev.outcome
    assert o.target_close_price == 105.0        # bar 00:19 close
    assert o.window_high_price == 110.0 and o.window_low_price == 95.0
    assert o.market_return_pct == pytest.approx(5.0)
    assert o.peak_return_pct == pytest.approx(10.0) and o.trough_return_pct == pytest.approx(-5.0)
    assert o.directional_return_pct == pytest.approx(5.0)      # == market return
    assert o.mfe_pct == pytest.approx(10.0) and o.mae_pct == pytest.approx(-5.0)
    assert o.bars_present == 15 == o.bars_expected


# ============================================================================
# E. complete SHORT
# ============================================================================
def test_complete_short_metrics():
    p = _pred_short()
    assert p.direction == SHORT
    w = build_forecast_outcome_window(p, horizon="15m", evaluation_exchange="binance")
    o = evaluate_forecast_outcome(p, w, price_bars=_grid(w, _ohlc_known)).outcome
    assert o.market_return_pct == pytest.approx(5.0)
    assert o.directional_return_pct == pytest.approx(-5.0)
    assert o.mfe_pct == pytest.approx(5.0)                      # max(0, -trough) = max(0, 5)
    assert o.mae_pct == pytest.approx(-10.0)                    # min(0, -peak) = min(0, -10)


# ============================================================================
# F. complete NEUTRAL
# ============================================================================
def test_complete_neutral_metrics():
    p = _pred_neutral()
    assert p.direction == NEUTRAL
    w = build_forecast_outcome_window(p, horizon="15m", evaluation_exchange="binance")
    o = evaluate_forecast_outcome(p, w, price_bars=_grid(w, _ohlc_known)).outcome
    assert o.market_return_pct == pytest.approx(5.0) and o.peak_return_pct == pytest.approx(10.0) and o.trough_return_pct == pytest.approx(-5.0)
    assert o.directional_return_pct is None and o.mfe_pct is None and o.mae_pct is None


# ============================================================================
# G. excursion edge cases
# ============================================================================
def test_long_mfe_zero_when_all_below_reference():
    p = _pred_long()
    w = build_forecast_outcome_window(p, horizon="15m", evaluation_exchange="binance")
    # all prices below 100 -> peak_return < 0 -> MFE clamps to 0
    o = evaluate_forecast_outcome(p, w, price_bars=_grid(w, lambda i: (95.0, 96.0, 94.0, 95.0))).outcome
    assert o.peak_return_pct < 0 and o.mfe_pct == 0.0 and o.mae_pct < 0


def test_short_mfe_zero_when_all_above_reference():
    p = _pred_short()
    w = build_forecast_outcome_window(p, horizon="15m", evaluation_exchange="binance")
    o = evaluate_forecast_outcome(p, w, price_bars=_grid(w, lambda i: (105.0, 106.0, 104.0, 105.0))).outcome
    assert o.trough_return_pct > 0 and o.mfe_pct == 0.0     # max(0, -trough) = 0


def test_exact_reference_path_zero_returns():
    p = _pred_long()
    w = build_forecast_outcome_window(p, horizon="15m", evaluation_exchange="binance")
    o = evaluate_forecast_outcome(p, w, price_bars=_grid(w)).outcome     # flat 100
    assert o.market_return_pct == 0.0 and o.peak_return_pct == 0.0 and o.trough_return_pct == 0.0
    assert o.directional_return_pct == 0.0 and o.mfe_pct == 0.0 and o.mae_pct == 0.0


# ============================================================================
# H. incomplete windows
# ============================================================================
def _full(p):
    w = build_forecast_outcome_window(p, horizon="15m", evaluation_exchange="binance")
    return w, _grid(w, _ohlc_known)


@pytest.mark.parametrize("drop", ["empty", "first", "middle", "target", "multiple"])
def test_incomplete_windows(drop):
    p = _pred_long()
    w, bars = _full(p)
    start = w.evaluation_start_ts
    if drop == "empty":
        supplied, expected_missing = [], list(range(15))
    elif drop == "first":
        supplied, expected_missing = bars[1:], [0]
    elif drop == "middle":
        supplied, expected_missing = bars[:7] + bars[8:], [7]
    elif drop == "target":
        supplied, expected_missing = bars[:14], [14]
    else:
        supplied, expected_missing = bars[2:13], [0, 1, 13, 14]
    ev = evaluate_forecast_outcome(p, w, price_bars=supplied)
    assert ev.status == OUTCOME_INCOMPLETE and ev.outcome is None
    assert ev.bars_present == 15 - len(expected_missing)
    assert list(ev.missing_bar_ts) == [start + timedelta(minutes=i) for i in expected_missing]


# ============================================================================
# I. invalid bar sets
# ============================================================================
@pytest.mark.parametrize("bad", [
    "abc", b"x", bytearray(b"x"), {"a": 1}, {1, 2}, (x for x in ()), iter([]), object(),
])
def test_reject_bad_price_bars_container(bad):
    p = _pred_long()
    w = build_forecast_outcome_window(p, horizon="15m", evaluation_exchange="binance")
    with pytest.raises(ForecastOutcomeInputError):
        evaluate_forecast_outcome(p, w, price_bars=bad)


def test_reject_wrong_member_type():
    p = _pred_long()
    w = build_forecast_outcome_window(p, horizon="15m", evaluation_exchange="binance")
    bars = _grid(w, _ohlc_known)
    with pytest.raises(ForecastOutcomeInputError):
        evaluate_forecast_outcome(p, w, price_bars=bars[:14] + [object()])


def test_reject_duplicate_timestamp():
    p = _pred_long()
    w = build_forecast_outcome_window(p, horizon="15m", evaluation_exchange="binance")
    bars = _grid(w, _ohlc_known)
    with pytest.raises(ForecastOutcomeInputError):
        evaluate_forecast_outcome(p, w, price_bars=bars + [bars[0]])


def test_reject_ts_outside_window():
    p = _pred_long()
    w = build_forecast_outcome_window(p, horizon="15m", evaluation_exchange="binance")
    bars = _grid(w, _ohlc_known)
    extra = _bar(w.evaluation_end_ts, 100.0, 100.0, 100.0, 100.0)   # == end (excluded)
    with pytest.raises(ForecastOutcomeInputError):
        evaluate_forecast_outcome(p, w, price_bars=bars + [extra])


def test_reject_wrong_exchange_or_symbol():
    p = _pred_long()
    w = build_forecast_outcome_window(p, horizon="15m", evaluation_exchange="binance")
    bars = _grid(w, _ohlc_known)
    bad_ex = bars[:14] + [_bar(w.target_bar_ts, 104.0, 106.0, 103.0, 105.0, exchange="bybit")]
    with pytest.raises(ForecastOutcomeInputError):
        evaluate_forecast_outcome(p, w, price_bars=bad_ex)


# ============================================================================
# J. order independence + no mutation
# ============================================================================
def test_order_independence_and_no_mutation():
    p = _pred_long()
    w = build_forecast_outcome_window(p, horizon="15m", evaluation_exchange="binance")
    bars = _grid(w, _ohlc_known)
    forward = evaluate_forecast_outcome(p, w, price_bars=bars)
    shuffled = list(reversed(bars))
    before = list(shuffled)
    backward = evaluate_forecast_outcome(p, w, price_bars=shuffled)
    assert forward == backward
    assert shuffled == before                    # input list not mutated


# ============================================================================
# K. direct model validation
# ============================================================================
def _valid_outcome(**over) -> ForecastOutcome:
    p = _pred_long()
    w = build_forecast_outcome_window(p, horizon="15m", evaluation_exchange="binance")
    o = evaluate_forecast_outcome(p, w, price_bars=_grid(w, _ohlc_known)).outcome
    if over:
        return dataclasses.replace(o, **over)
    return o


def test_direct_outcome_valid():
    assert isinstance(_valid_outcome(), ForecastOutcome)


@pytest.mark.parametrize("over", [
    dict(symbol="ETHUSDT"), dict(market_type="spot"), dict(timeframe="1m"),
    dict(calculation_version="zzz"), dict(config_hash="a" * 63),
    dict(direction="up"), dict(prediction_confidence=1.5),
    dict(prediction_final_score=2.0), dict(reference_price=0.0),
    dict(evaluation_price_source="other"), dict(bars_present=14),
    dict(market_return_pct=999.0),                  # formula inconsistency
    dict(mfe_pct=-1.0),                             # LONG mfe must be >= 0
    dict(directional_return_pct=None),             # LONG requires non-null
])
def test_direct_outcome_rejects_malformed(over):
    with pytest.raises(ForecastOutcomeInputError):
        _valid_outcome(**over)


def test_direct_outcome_neutral_nonnull_rejected():
    p = _pred_neutral()
    w = build_forecast_outcome_window(p, horizon="15m", evaluation_exchange="binance")
    o = evaluate_forecast_outcome(p, w, price_bars=_grid(w, _ohlc_known)).outcome
    with pytest.raises(ForecastOutcomeInputError):
        dataclasses.replace(o, directional_return_pct=1.0)   # NEUTRAL must be NULL


def test_direct_window_timing_invariants():
    good = dict(horizon="15m", outcome_version="v", evaluation_exchange="binance",
                evaluation_price_source=EVALUATION_PRICE_SOURCE,
                evaluation_start_ts=B + timedelta(minutes=5),
                evaluation_end_ts=B + timedelta(minutes=20),
                target_bar_ts=B + timedelta(minutes=19), bars_expected=15)
    ForecastOutcomeWindow(**good)
    for bad in (dict(bars_expected=14), dict(evaluation_end_ts=B + timedelta(minutes=21)),
                dict(target_bar_ts=B + timedelta(minutes=18)),
                dict(evaluation_price_source="x"), dict(evaluation_exchange="kraken")):
        kw = dict(good); kw.update(bad)
        with pytest.raises(ForecastOutcomeInputError):
            ForecastOutcomeWindow(**kw)


def test_direct_evaluation_invariants():
    # COMPLETE with missing bars is invalid; INCOMPLETE with an outcome is invalid
    o = _valid_outcome()
    common = dict(horizon="15m", outcome_version=DEFAULT_OUTCOME_VERSION,
                  evaluation_exchange="binance", evaluation_price_source=EVALUATION_PRICE_SOURCE,
                  evaluation_start_ts=o.evaluation_start_ts, evaluation_end_ts=o.evaluation_end_ts)
    with pytest.raises(ForecastOutcomeInputError):
        ForecastOutcomeEvaluation(status=OUTCOME_COMPLETE, bars_expected=15, bars_present=14,
                                  missing_bar_ts=(o.evaluation_start_ts,), outcome=o, **common)
    with pytest.raises(ForecastOutcomeInputError):
        ForecastOutcomeEvaluation(status=OUTCOME_INCOMPLETE, bars_expected=15, bars_present=14,
                                  missing_bar_ts=(o.evaluation_start_ts,), outcome=o, **common)


# ============================================================================
# K2. ForecastOutcome window is bound to the prediction bucket (start == bucket+5m)
# ============================================================================
def test_outcome_window_must_be_bound_to_bucket():
    o = _valid_outcome()
    # shift the whole window five minutes forward (still internally self-consistent:
    # end == start+15m, target == end-1m) but leave bucket_ts unchanged.
    with pytest.raises(ForecastOutcomeInputError):
        dataclasses.replace(
            o,
            evaluation_start_ts=o.evaluation_start_ts + timedelta(minutes=5),
            evaluation_end_ts=o.evaluation_end_ts + timedelta(minutes=5),
            target_bar_ts=o.target_bar_ts + timedelta(minutes=5))


def test_outcome_valid_window_still_accepted():
    o = _valid_outcome()
    assert o.evaluation_start_ts == o.bucket_ts + timedelta(minutes=5)


# ============================================================================
# K3. ForecastOutcomeWindow.bars_expected must be an exact int
# ============================================================================
@pytest.mark.parametrize("bars_expected", [15.0, True, "15"])
def test_window_bars_expected_must_be_exact_int(bars_expected):
    good = dict(horizon="15m", outcome_version="v", evaluation_exchange="binance",
                evaluation_price_source=EVALUATION_PRICE_SOURCE,
                evaluation_start_ts=B + timedelta(minutes=5),
                evaluation_end_ts=B + timedelta(minutes=20),
                target_bar_ts=B + timedelta(minutes=19), bars_expected=bars_expected)
    with pytest.raises(ForecastOutcomeInputError):
        ForecastOutcomeWindow(**good)


# ============================================================================
# K4. ForecastOutcomeEvaluation full validation (COMPLETE and INCOMPLETE)
# ============================================================================
def _incomplete_eval(**over) -> ForecastOutcomeEvaluation:
    """A real INCOMPLETE evaluation (target bar dropped: 14/15) for regressions."""
    p = _pred_long()
    w = build_forecast_outcome_window(p, horizon="15m", evaluation_exchange="binance")
    ev = evaluate_forecast_outcome(p, w, price_bars=_grid(w, _ohlc_known)[:-1])
    assert ev.status == OUTCOME_INCOMPLETE and ev.bars_present == 14
    if over:
        return dataclasses.replace(ev, **over)
    return ev


def test_incomplete_eval_baseline_valid():
    ev = _incomplete_eval()
    assert ev.status == OUTCOME_INCOMPLETE and len(ev.missing_bar_ts) == 1


# start / end used by the direct-construction cases below
_S = B + timedelta(minutes=5)      # evaluation_start (bucket + 5m)
_E = B + timedelta(minutes=20)     # evaluation_end (15m horizon)
_GRID15 = tuple(_S + timedelta(minutes=i) for i in range(15))


@pytest.mark.parametrize("over", [
    dict(horizon="30m"),                                   # unsupported horizon
    dict(horizon="5m"),                                    # unsupported horizon
    dict(outcome_version="  "),                            # blank outcome version
    dict(evaluation_exchange="kraken"),                    # unknown exchange
    dict(evaluation_price_source="other"),                 # wrong evaluation source
    dict(evaluation_start_ts=_S.replace(tzinfo=None)),     # naive timestamp
    dict(evaluation_start_ts=datetime(2026, 3, 1, 0, 5,    # non-UTC offset
                                      tzinfo=timezone(timedelta(hours=2)))),
    dict(evaluation_start_ts=B + timedelta(minutes=5, seconds=30)),  # not whole minute
    dict(evaluation_end_ts=B + timedelta(minutes=21)),     # wrong duration (end)
    dict(bars_expected=15.0),                              # float bars_expected
    dict(bars_expected=True),                              # bool bars_expected
    dict(bars_present=13.0),                               # float bars_present
    dict(bars_present=True),                               # bool bars_present
    dict(bars_present=-1),                                 # negative bars_present
])
def test_incomplete_eval_rejects_bad_window_or_counts(over):
    with pytest.raises(ForecastOutcomeInputError):
        _incomplete_eval(**over)


@pytest.mark.parametrize("bad_missing", [
    "abc", b"x", bytearray(b"x"),                          # str/bytes/bytearray
    {"a": 1},                                              # mapping
    {_S},                                                  # set
    frozenset({_S}),                                       # frozenset
    (t for t in (_S,)),                                    # generator
    iter([_S]),                                            # iterator
    123,                                                   # arbitrary non-Sequence
])
def test_incomplete_eval_rejects_malformed_missing_container(bad_missing):
    with pytest.raises(ForecastOutcomeInputError):
        _incomplete_eval(missing_bar_ts=bad_missing)


def test_incomplete_eval_rejects_missing_ts_outside_grid():
    # a timestamp not on the exact start..end-1m grid (here the bucket open, 5m early)
    with pytest.raises(ForecastOutcomeInputError):
        _incomplete_eval(missing_bar_ts=(B,), bars_present=14)


def test_incomplete_eval_rejects_missing_ts_not_whole_minute():
    off = _S + timedelta(seconds=30)
    with pytest.raises(ForecastOutcomeInputError):
        _incomplete_eval(missing_bar_ts=(off,), bars_present=14)


def _direct_eval(**over):
    base = dict(
        horizon="15m", outcome_version=DEFAULT_OUTCOME_VERSION,
        evaluation_exchange="binance", evaluation_price_source=EVALUATION_PRICE_SOURCE,
        evaluation_start_ts=_S, evaluation_end_ts=_E,
        status=OUTCOME_INCOMPLETE, bars_expected=15, bars_present=0,
        missing_bar_ts=_GRID15, outcome=None)
    base.update(over)
    return ForecastOutcomeEvaluation(**base)


def test_incomplete_eval_zero_of_fifteen_accepted():
    # a valid 0/15 incomplete evaluation with ALL fifteen expected timestamps missing
    ev = _direct_eval()
    assert ev.status == OUTCOME_INCOMPLETE
    assert ev.bars_present == 0 and ev.bars_expected == 15
    assert ev.missing_bar_ts == _GRID15 and len(ev.missing_bar_ts) == 15


def test_incomplete_eval_len_mismatch_rejected():
    # 14 missing but bars_present=0 (should be 15 missing)
    with pytest.raises(ForecastOutcomeInputError):
        _direct_eval(missing_bar_ts=_GRID15[:14])


def test_direct_eval_complete_matches_outcome():
    o = _valid_outcome()
    ev = ForecastOutcomeEvaluation(
        horizon=o.horizon, outcome_version=o.outcome_version,
        evaluation_exchange=o.evaluation_exchange,
        evaluation_price_source=o.evaluation_price_source,
        evaluation_start_ts=o.evaluation_start_ts, evaluation_end_ts=o.evaluation_end_ts,
        status=OUTCOME_COMPLETE, bars_expected=o.bars_expected, bars_present=o.bars_present,
        missing_bar_ts=(), outcome=o)
    assert ev.status == OUTCOME_COMPLETE and ev.outcome is o


# ============================================================================
# K5. exact public model types (no subclass / duck-typed substitutes)
# ============================================================================
def _ns_from(dc):
    return SimpleNamespace(**{f.name: getattr(dc, f.name) for f in dataclasses.fields(dc)})


def test_build_window_rejects_ducktyped_prediction():
    p = _pred_long()
    fake = _ns_from(p)
    with pytest.raises(ForecastOutcomeInputError):
        build_forecast_outcome_window(fake, horizon="15m", evaluation_exchange="binance")


def test_evaluate_rejects_ducktyped_prediction():
    p = _pred_long()
    w = build_forecast_outcome_window(p, horizon="15m", evaluation_exchange="binance")
    with pytest.raises(ForecastOutcomeInputError):
        evaluate_forecast_outcome(_ns_from(p), w, price_bars=_grid(w, _ohlc_known))


def test_evaluate_rejects_ducktyped_window():
    p = _pred_long()
    w = build_forecast_outcome_window(p, horizon="15m", evaluation_exchange="binance")
    with pytest.raises(ForecastOutcomeInputError):
        evaluate_forecast_outcome(p, _ns_from(w), price_bars=_grid(w, _ohlc_known))


# ============================================================================
# L. purity / architecture
# ============================================================================
_ALLOWED = {"__future__", "math", "re", "dataclasses", "datetime", "types",
            "typing", "collections", "analytics", "symbols"}
_FORBIDDEN = {
    "storage", "asyncpg", "asyncio", "socket", "redis", "aiohttp", "requests",
    "os", "dotenv", "subprocess", "pathlib", "logging", "main", "data_ingestion",
    "backfill", "telegram", "time", "random", "numpy", "pandas", "sklearn",
    "torch", "tensorflow",
}


def test_architecture_pure_boundary():
    src = Path("analytics/forecasting/outcomes.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported, used_attrs = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])
        elif isinstance(node, ast.Attribute):
            used_attrs.add(node.attr)
        assert not isinstance(node, (ast.AsyncFunctionDef, ast.Await))
    assert not (imported & _FORBIDDEN), imported & _FORBIDDEN
    assert imported <= _ALLOWED, imported - _ALLOWED
    assert not (used_attrs & {"now", "utcnow", "today", "environ", "getenv"})
