"""Unit tests for analytics/forecasting/outcome_pipeline.py.

Pure/deterministic composition test — no DB, network, clock. Fake reader/writer
record their calls; real ForecastPrediction / price bars flow through. Verifies:
preflight validation before any read, exactly-one read/one adapt/one evaluate,
one writer call only when COMPLETE, exact reader args per horizon, raw-mapping
adaptation, Sequence validation, exception propagation, and no retry/gather.
"""
from __future__ import annotations

import ast
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType

import pytest

from analytics.feature_engine.consensus_models import ConsensusFeatureVector
from analytics.forecasting import (
    LONG, SHORT, compute_forecast_decision, build_forecast_prediction,
)
from analytics.forecasting.outcomes import (
    DEFAULT_OUTCOME_VERSION, ForecastOutcome, ForecastOutcomeEvaluation,
    ForecastOutcomeInputError, OUTCOME_COMPLETE, OUTCOME_INCOMPLETE,
    OUTCOME_HORIZON_MINUTES, OutcomePriceBar, build_forecast_outcome_window,
)
from analytics.forecasting.outcome_pipeline import (
    process_forecast_outcome_horizon,
)

UTC = timezone.utc
B = datetime(2026, 3, 1, 0, 0, 0, tzinfo=UTC)
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


def _pred_long(reference_price_source=SRC):
    cv = _cv()
    return build_forecast_prediction(
        compute_forecast_decision(cv), cv,
        reference_price=REF, reference_price_source=reference_price_source)


def _pred_short(reference_price_source=SRC):
    cv = _cv(price_move_pct_median=-0.4, taker_buy_notional_usd_sum=200.0,
             taker_sell_notional_usd_sum=800.0, taker_delta_notional_usd_sum=-600.0,
             observed_long_liquidation_notional_sum=900.0,
             observed_short_liquidation_notional_sum=100.0,
             funding_rate_median=-0.0001)
    return build_forecast_prediction(
        compute_forecast_decision(cv), cv,
        reference_price=REF, reference_price_source=reference_price_source)


def _raw_grid(window, ohlc=lambda i: (100.0, 101.0, 99.0, 100.0)):
    """Raw kline mappings (as an asyncpg reader would return) for a full window."""
    start = window.evaluation_start_ts
    rows = []
    for i in range(window.bars_expected):
        o, h, low, c = ohlc(i)
        rows.append(dict(exchange=window.evaluation_exchange, symbol="BTCUSDT",
                         ts=start + timedelta(minutes=i),
                         open=o, high=h, low=low, close=c))
    return rows


class FakeReader:
    def __init__(self, rows):
        self._rows = rows
        self.calls = []

    async def fetch_forecast_outcome_klines(self, *, exchange, symbol,
                                            window_start, window_end):
        self.calls.append(dict(exchange=exchange, symbol=symbol,
                               window_start=window_start, window_end=window_end))
        return self._rows


class FakeWriter:
    def __init__(self):
        self.calls = []

    async def upsert_forecast_outcomes(self, rows):
        self.calls.append(tuple(rows))
        return len(rows)


class BoomReader:
    def __init__(self):
        self.calls = 0

    async def fetch_forecast_outcome_klines(self, **kw):
        self.calls += 1
        raise RuntimeError("reader boom")


class BoomWriter:
    def __init__(self):
        self.calls = 0

    async def upsert_forecast_outcomes(self, rows):
        self.calls += 1
        raise RuntimeError("writer boom")


def _run(coro):
    return asyncio.run(coro)


# ============================================================================
# preflight: request validation happens BEFORE any read
# ============================================================================
def test_bad_horizon_rejected_before_read():
    r, w = FakeReader([]), FakeWriter()
    with pytest.raises(ForecastOutcomeInputError):
        _run(process_forecast_outcome_horizon(r, w, _pred_long(),
             horizon="30m", evaluation_exchange="binance"))
    assert r.calls == [] and w.calls == []


def test_source_mismatch_rejected_before_read():
    r, w = FakeReader([]), FakeWriter()
    with pytest.raises(ForecastOutcomeInputError):
        _run(process_forecast_outcome_horizon(r, w, _pred_long(),
             horizon="15m", evaluation_exchange="bybit"))  # source is binance_close_5m
    assert r.calls == [] and w.calls == []


def test_non_prediction_rejected_before_read():
    r, w = FakeReader([]), FakeWriter()
    with pytest.raises(ForecastOutcomeInputError):
        _run(process_forecast_outcome_horizon(r, w, object(),
             horizon="15m", evaluation_exchange="binance"))
    assert r.calls == [] and w.calls == []


# ============================================================================
# exact reader args per horizon
# ============================================================================
@pytest.mark.parametrize("horizon", ["15m", "1h", "4h"])
def test_reader_called_once_with_exact_window_args(horizon):
    p = _pred_long()
    window = build_forecast_outcome_window(p, horizon=horizon, evaluation_exchange="binance")
    r = FakeReader(_raw_grid(window))
    w = FakeWriter()
    _run(process_forecast_outcome_horizon(r, w, p,
         horizon=horizon, evaluation_exchange="binance"))
    assert len(r.calls) == 1
    call = r.calls[0]
    assert call["exchange"] == "binance"
    assert call["symbol"] == "BTCUSDT"
    assert call["window_start"] == B + timedelta(minutes=5)
    assert call["window_end"] == B + timedelta(minutes=5 + OUTCOME_HORIZON_MINUTES[horizon])


# ============================================================================
# complete -> exactly one writer call with one ForecastOutcome; exact result
# ============================================================================
def test_complete_persists_one_outcome_and_returns_it():
    p = _pred_long()
    window = build_forecast_outcome_window(p, horizon="15m", evaluation_exchange="binance")
    r = FakeReader(_raw_grid(window))
    w = FakeWriter()
    result = _run(process_forecast_outcome_horizon(r, w, p,
                  horizon="15m", evaluation_exchange="binance"))
    assert isinstance(result, ForecastOutcomeEvaluation)
    assert result.status == OUTCOME_COMPLETE
    assert len(w.calls) == 1
    persisted = w.calls[0]
    assert len(persisted) == 1
    assert isinstance(persisted[0], ForecastOutcome)
    # the persisted object IS the evaluation's outcome
    assert persisted[0] is result.outcome
    assert persisted[0].direction == LONG


def test_returned_evaluation_is_exact_object_short():
    p = _pred_short()
    window = build_forecast_outcome_window(p, horizon="1h", evaluation_exchange="binance")
    r = FakeReader(_raw_grid(window))
    w = FakeWriter()
    result = _run(process_forecast_outcome_horizon(r, w, p,
                  horizon="1h", evaluation_exchange="binance"))
    assert result.status == OUTCOME_COMPLETE
    assert result.outcome.direction == SHORT
    assert w.calls[0][0] is result.outcome


# ============================================================================
# incomplete -> no writer call, INCOMPLETE result
# ============================================================================
def test_incomplete_missing_bars_no_writer():
    p = _pred_long()
    window = build_forecast_outcome_window(p, horizon="15m", evaluation_exchange="binance")
    rows = _raw_grid(window)[:-1]  # drop the last (target) bar
    r = FakeReader(rows)
    w = FakeWriter()
    result = _run(process_forecast_outcome_horizon(r, w, p,
                  horizon="15m", evaluation_exchange="binance"))
    assert result.status == OUTCOME_INCOMPLETE
    assert result.outcome is None
    assert len(r.calls) == 1  # read still happened
    assert w.calls == []       # but nothing persisted


def test_incomplete_empty_window_no_writer():
    p = _pred_long()
    r = FakeReader([])
    w = FakeWriter()
    result = _run(process_forecast_outcome_horizon(r, w, p,
                  horizon="15m", evaluation_exchange="binance"))
    assert result.status == OUTCOME_INCOMPLETE
    assert w.calls == []


# ============================================================================
# malformed reader output -> adaptation fails; writer untouched
# ============================================================================
def test_malformed_rows_leave_writer_untouched():
    p = _pred_long()
    r = FakeReader("not-a-sequence-of-rows")  # str rejected as a container
    w = FakeWriter()
    with pytest.raises(ForecastOutcomeInputError):
        _run(process_forecast_outcome_horizon(r, w, p,
             horizon="15m", evaluation_exchange="binance"))
    assert len(r.calls) == 1
    assert w.calls == []


def test_row_missing_key_leaves_writer_untouched():
    p = _pred_long()
    window = build_forecast_outcome_window(p, horizon="15m", evaluation_exchange="binance")
    rows = _raw_grid(window)
    del rows[0]["close"]  # drop a required key
    r = FakeReader(rows)
    w = FakeWriter()
    with pytest.raises(ForecastOutcomeInputError):
        _run(process_forecast_outcome_horizon(r, w, p,
             horizon="15m", evaluation_exchange="binance"))
    assert w.calls == []


def test_row_extra_key_leaves_writer_untouched():
    p = _pred_long()
    window = build_forecast_outcome_window(p, horizon="15m", evaluation_exchange="binance")
    rows = _raw_grid(window)
    rows[0]["volume"] = 1.0  # unexpected extra key
    r = FakeReader(rows)
    w = FakeWriter()
    with pytest.raises(ForecastOutcomeInputError):
        _run(process_forecast_outcome_horizon(r, w, p,
             horizon="15m", evaluation_exchange="binance"))
    assert w.calls == []


# ============================================================================
# raw mapping -> OutcomePriceBar adaptation (MappingProxyType rows accepted)
# ============================================================================
def test_readonly_mapping_rows_are_adapted():
    p = _pred_long()
    window = build_forecast_outcome_window(p, horizon="15m", evaluation_exchange="binance")
    rows = tuple(MappingProxyType(dict(row)) for row in _raw_grid(window))
    r = FakeReader(rows)
    w = FakeWriter()
    result = _run(process_forecast_outcome_horizon(r, w, p,
                  horizon="15m", evaluation_exchange="binance"))
    assert result.status == OUTCOME_COMPLETE
    assert len(w.calls) == 1


# ============================================================================
# adapter error contract: a mapping with mixed key types must raise
# ForecastOutcomeInputError, never a raw TypeError from sorting unlike keys.
# ============================================================================
def test_mixed_key_row_raises_input_error_not_typeerror():
    p = _pred_long()
    window = build_forecast_outcome_window(p, horizon="15m", evaluation_exchange="binance")
    rows = _raw_grid(window)
    rows[0] = {**rows[0], 7: "surprise"}          # str keys + one int key -> set mismatch
    r = FakeReader(rows)
    w = FakeWriter()
    with pytest.raises(ForecastOutcomeInputError):  # would be TypeError without the repr sort
        _run(process_forecast_outcome_horizon(r, w, p,
             horizon="15m", evaluation_exchange="binance"))
    assert w.calls == []


def test_adapt_price_bars_mixed_keys_direct():
    from analytics.forecasting.outcome_pipeline import _adapt_price_bars
    bad = [{"exchange": "binance", "symbol": "BTCUSDT",
            "ts": B + timedelta(minutes=5), "open": 1.0, "high": 1.0,
            "low": 1.0, "close": 1.0, 7: "surprise"}]     # mixed str/int keys
    with pytest.raises(ForecastOutcomeInputError):
        _adapt_price_bars(bad)


# ============================================================================
# exception propagation
# ============================================================================
def test_reader_exception_propagates_no_writer():
    p = _pred_long()
    r = BoomReader()
    w = FakeWriter()
    with pytest.raises(RuntimeError, match="reader boom"):
        _run(process_forecast_outcome_horizon(r, w, p,
             horizon="15m", evaluation_exchange="binance"))
    assert r.calls == 1
    assert w.calls == []


def test_writer_exception_propagates():
    p = _pred_long()
    window = build_forecast_outcome_window(p, horizon="15m", evaluation_exchange="binance")
    r = FakeReader(_raw_grid(window))
    w = BoomWriter()
    with pytest.raises(RuntimeError, match="writer boom"):
        _run(process_forecast_outcome_horizon(r, w, p,
             horizon="15m", evaluation_exchange="binance"))
    assert w.calls == 1  # attempted exactly once, no retry


# ============================================================================
# architecture: no concrete DB import, no retry/gather/sleep/loop
# ============================================================================
_PIPELINE_SRC = Path("analytics/forecasting/outcome_pipeline.py")


def test_pipeline_has_no_forbidden_imports():
    tree = ast.parse(_PIPELINE_SRC.read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                imported.add(a.name)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    forbidden = {"storage.db", "storage", "asyncpg", "time", "logging"}
    assert not (imported & forbidden), f"forbidden imports: {imported & forbidden}"


def test_pipeline_has_no_retry_or_gather_calls():
    # Inspect actual call targets (not docstring prose) for concurrency/retry helpers.
    tree = ast.parse(_PIPELINE_SRC.read_text())
    called_attrs = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    banned = {"gather", "sleep", "create_task", "ensure_future", "wait_for", "shield"}
    assert not (called_attrs & banned), f"pipeline must not call {called_attrs & banned}"


def test_pipeline_awaits_reader_and_writer_each_once_in_source():
    """The single read and single (conditional) upsert are the only awaited I/O."""
    tree = ast.parse(_PIPELINE_SRC.read_text())
    awaited_attrs = [
        node.value.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Await)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Attribute)
    ]
    assert awaited_attrs.count("fetch_forecast_outcome_klines") == 1
    assert awaited_attrs.count("upsert_forecast_outcomes") == 1
