"""Tests for analytics/forecasting_v2/confirmed_breakout_inputs.py
(Stage 5 — Setup Detectors, PR 4 of ~4, FINAL planned Stage 5 detector
PR). No real DB — a fake `V2SetupHistoryReader` recording every call,
following the existing V2 loader test style (tests/analytics/
test_forecasting_v2_compression_breakout_inputs.py's `RecordingReader`).

Exercises: `load_confirmed_breakout_inputs()` issues EXACTLY 5 reads for
ANY legal `context.T` (no 1h-boundary skip); the exact 14-bucket 1h
RANGE_PROXY consensus window; the exact 48-bucket 1h structural
reference-feature window; the exact half-open raw-kline window; the
exact two-closed-bucket 5m reference-feature window; the exact
instrument lookup; the load-bearing ABSENCE of any current-B5 5m
consensus read (the family difference from #41's loader); that the
assembler never decides the setup itself; that it depends only on the
`V2SetupHistoryReader` Protocol, never a concrete storage import; and
the cheap non-`V2ContextSnapshot` `context` boundary check."""
from __future__ import annotations

import ast
import asyncio
import inspect
from datetime import datetime, timedelta, timezone

import pytest

from analytics.forecasting_v2 import confirmed_breakout_inputs as loader_module
from analytics.forecasting_v2.aligned_inputs import V2_REFERENCE_EXCHANGE
from analytics.forecasting_v2.bias_1h import NEUTRAL_NOT_ESTABLISHED, V2BiasResult
from analytics.forecasting_v2.confirmed_breakout import (
    LEVEL_LOOKBACK, V2ConfirmedBreakoutError, V2ConfirmedBreakoutInputs,
)
from analytics.forecasting_v2.confirmed_breakout_inputs import load_confirmed_breakout_inputs
from analytics.forecasting_v2.context_snapshot import V2ContextSnapshot
from analytics.forecasting_v2.alignment import selected_bucket
from analytics.forecasting_v2.regime_4h import NON_DIRECTIONAL, V2RegimeResult
from analytics.forecasting_v2.setup_common import RANGE_PROXY_N

UTC = timezone.utc
H16 = "a" * 16
SYMBOL = "BTCUSDT"
MARKET_TYPE = "perp"

T = datetime(2024, 1, 1, 13, 5, tzinfo=UTC)  # legal 5m boundary, not a 1h boundary
B5 = selected_bucket("5m", T)
B1H = selected_bucket("1h", T)
FIVE = timedelta(minutes=5)
ONE_HOUR = timedelta(hours=1)


def make_context(*, t=T) -> V2ContextSnapshot:
    return V2ContextSnapshot(
        T=t, symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=H16,
        feature_schema_version=1,
        regime_4h=V2RegimeResult(bucket_ts=selected_bucket("4h", t), regime=NON_DIRECTIONAL,
                                 is_compressed=False),
        bias_1h=V2BiasResult(bucket_ts=selected_bucket("1h", t), bias=NEUTRAL_NOT_ESTABLISHED),
    )


def _run(coro):
    return asyncio.run(coro)


class RecordingReader:
    """Satisfies `V2SetupHistoryReader` structurally. Every call is
    recorded with its exact kwargs; each `fetch_v2_*` returns whatever
    canned response was configured, or a legitimately-empty default
    (`()`/`None`) otherwise — matching a real empty-result read. Raises
    if `fetch_v2_consensus_feature_window` is ever called with
    `timeframe="5m"` -- this family must never issue a current-B5
    consensus read (load-bearing difference from #41)."""
    def __init__(self, *, consensus_1h_rows=(), reference_1h_rows=(), reference_1m_rows=(),
                reference_5m_rows=(), instrument=None):
        self._consensus_1h_rows = consensus_1h_rows
        self._reference_1h_rows = reference_1h_rows
        self._reference_1m_rows = reference_1m_rows
        self._reference_5m_rows = reference_5m_rows
        self._instrument = instrument
        self.calls: list = []

    async def fetch_v2_consensus_feature_window(self, **kw):
        self.calls.append(("consensus_feature_window", kw))
        if kw.get("timeframe") == "5m":
            raise AssertionError(
                "confirmed_breakout loader must never fetch a 5m consensus window")
        return self._consensus_1h_rows

    async def fetch_v2_consensus_percentile_window(self, **kw):
        self.calls.append(("consensus_percentile_window", kw))
        raise AssertionError("confirmed_breakout loader must never fetch a percentile window")

    async def fetch_v2_reference_feature_window(self, **kw):
        self.calls.append(("reference_feature_window", kw))
        if kw.get("timeframe") == "5m":
            return self._reference_5m_rows
        return self._reference_1h_rows

    async def fetch_v2_reference_klines(self, **kw):
        self.calls.append(("reference_klines", kw))
        return self._reference_1m_rows

    async def fetch_v2_instrument(self, **kw):
        self.calls.append(("instrument", kw))
        return self._instrument


# ============================================================================
# 1. EVERY legal T issues the full read set (no 1h-boundary skip)
# ============================================================================
@pytest.mark.parametrize("t", [
    datetime(2024, 1, 1, 13, 0, tzinfo=UTC),   # a 1h boundary too
    datetime(2024, 1, 1, 13, 5, tzinfo=UTC),
    datetime(2024, 1, 1, 13, 10, tzinfo=UTC),
    datetime(2024, 1, 1, 13, 55, tzinfo=UTC),
    datetime(2024, 1, 1, 14, 0, tzinfo=UTC),
])
def test_every_legal_t_issues_exactly_five_reads(t):
    reader = RecordingReader()
    context = make_context(t=t)
    result = _run(load_confirmed_breakout_inputs(reader, context=context))
    assert isinstance(result, V2ConfirmedBreakoutInputs)
    assert len(reader.calls) == 5


# ============================================================================
# 2. EXACT READ CONTRACT -- exact arguments/intervals for every call
# ============================================================================
def test_exact_consensus_1h_window_call():
    reader = RecordingReader()
    _run(load_confirmed_breakout_inputs(reader, context=make_context()))
    calls = [kw for name, kw in reader.calls if name == "consensus_feature_window"]
    assert len(calls) == 1
    kw = calls[0]
    assert kw["symbol"] == SYMBOL
    assert kw["market_type"] == MARKET_TYPE
    assert kw["timeframe"] == "1h"
    assert kw["calculation_version"] == H16
    assert kw["bucket_start"] == B1H - (RANGE_PROXY_N - 1) * ONE_HOUR
    assert kw["bucket_end"] == B1H


def test_exact_reference_1h_window_call():
    reader = RecordingReader()
    _run(load_confirmed_breakout_inputs(reader, context=make_context()))
    calls = [kw for name, kw in reader.calls
             if name == "reference_feature_window" and kw.get("timeframe") == "1h"]
    assert len(calls) == 1
    kw = calls[0]
    assert kw["exchange"] == V2_REFERENCE_EXCHANGE
    assert kw["symbol"] == SYMBOL
    assert kw["market_type"] == MARKET_TYPE
    assert kw["calculation_version"] == H16
    assert kw["bucket_start"] == B1H - (LEVEL_LOOKBACK - 1) * ONE_HOUR
    assert kw["bucket_end"] == B1H


def test_exact_raw_kline_window_call_half_open():
    reader = RecordingReader()
    _run(load_confirmed_breakout_inputs(reader, context=make_context()))
    calls = [kw for name, kw in reader.calls if name == "reference_klines"]
    assert len(calls) == 1
    kw = calls[0]
    assert kw["exchange"] == V2_REFERENCE_EXCHANGE
    assert kw["symbol"] == SYMBOL
    assert kw["bucket_start"] == B1H - (LEVEL_LOOKBACK - 1) * ONE_HOUR
    assert kw["bucket_end"] == B1H + ONE_HOUR  # half-open, covers whole 48h lookback


def test_exact_reference_5m_window_call_two_closed_buckets():
    reader = RecordingReader()
    _run(load_confirmed_breakout_inputs(reader, context=make_context()))
    calls = [kw for name, kw in reader.calls
             if name == "reference_feature_window" and kw.get("timeframe") == "5m"]
    assert len(calls) == 1
    kw = calls[0]
    assert kw["exchange"] == V2_REFERENCE_EXCHANGE
    assert kw["symbol"] == SYMBOL
    assert kw["market_type"] == MARKET_TYPE
    assert kw["calculation_version"] == H16
    assert kw["bucket_start"] == B5 - FIVE
    assert kw["bucket_end"] == B5


def test_exact_instrument_call():
    reader = RecordingReader()
    _run(load_confirmed_breakout_inputs(reader, context=make_context()))
    calls = [kw for name, kw in reader.calls if name == "instrument"]
    assert len(calls) == 1
    kw = calls[0]
    assert kw["exchange"] == V2_REFERENCE_EXCHANGE
    assert kw["symbol"] == SYMBOL
    assert kw["market_type"] == MARKET_TYPE


def test_call_order_is_deterministic():
    reader = RecordingReader()
    _run(load_confirmed_breakout_inputs(reader, context=make_context()))
    names = [name for name, _ in reader.calls]
    assert names == [
        "consensus_feature_window",     # 14-bucket 1h RANGE_PROXY window
        "reference_feature_window",     # 48-bucket 1h structural window
        "reference_klines",             # raw 1m klines
        "reference_feature_window",     # 5m reference (two buckets)
        "instrument",
    ]


# ============================================================================
# 3. LOAD-BEARING FAMILY DIFFERENCE -- zero unnecessary reads, especially
# no current-B5 5m consensus read and no percentile reads of any kind
# ============================================================================
def test_no_5m_consensus_read_and_no_percentile_reads():
    reader = RecordingReader()
    _run(load_confirmed_breakout_inputs(reader, context=make_context()))
    for name, kw in reader.calls:
        assert name != "consensus_percentile_window"
        if name == "consensus_feature_window":
            assert kw.get("timeframe") != "5m"


def test_exactly_five_reads_total_no_sixth_read():
    reader = RecordingReader()
    _run(load_confirmed_breakout_inputs(reader, context=make_context()))
    assert len(reader.calls) == 5
    counts = {}
    for name, _ in reader.calls:
        counts[name] = counts.get(name, 0) + 1
    assert counts == {
        "consensus_feature_window": 1,
        "reference_feature_window": 2,
        "reference_klines": 1,
        "instrument": 1,
    }


# ============================================================================
# 4. RESULT SHAPE -- returns whatever exists, never pre-filters/decides
# ============================================================================
def test_result_carries_context_and_raw_rows_unfiltered():
    consensus_row = {"symbol": SYMBOL, "bucket_ts": B1H}
    reference_1h_row = {"exchange": "binance", "bucket_ts": B1H}
    raw_row = {"exchange": "binance", "symbol": SYMBOL, "ts": B1H}
    reference_5m_row = {"exchange": "binance", "bucket_ts": B5}
    instrument = {"tick_size": 0.1}
    reader = RecordingReader(
        consensus_1h_rows=(consensus_row,), reference_1h_rows=(reference_1h_row,),
        reference_1m_rows=(raw_row,), reference_5m_rows=(reference_5m_row,),
        instrument=instrument)
    result = _run(load_confirmed_breakout_inputs(reader, context=make_context()))
    assert result.consensus_1h_rows == (consensus_row,)
    assert result.reference_1h_rows == (reference_1h_row,)
    assert result.reference_1m_rows == (raw_row,)
    assert result.reference_5m_rows == (reference_5m_row,)
    assert result.instrument == instrument


def test_result_with_incomplete_history_still_returned_unfiltered():
    reader = RecordingReader()  # everything empty/None
    result = _run(load_confirmed_breakout_inputs(reader, context=make_context()))
    assert result.consensus_1h_rows == ()
    assert result.reference_1h_rows == ()
    assert result.reference_1m_rows == ()
    assert result.reference_5m_rows == ()
    assert result.instrument is None


def test_v2confirmedbreakoutinputs_has_no_consensus_5m_field():
    import dataclasses
    field_names = {f.name for f in dataclasses.fields(V2ConfirmedBreakoutInputs)}
    assert "consensus_5m_rows" not in field_names


# ============================================================================
# 5. READER ERRORS PROPAGATE UNCHANGED (never swallowed into None)
# ============================================================================
class RaisingReader:
    class _BoomError(ValueError):
        pass

    async def fetch_v2_consensus_feature_window(self, **kw):
        raise self._BoomError("reader boom")

    async def fetch_v2_consensus_percentile_window(self, **kw):
        raise AssertionError("should not be called")

    async def fetch_v2_reference_feature_window(self, **kw):
        raise AssertionError("should not be called")

    async def fetch_v2_reference_klines(self, **kw):
        raise AssertionError("should not be called")

    async def fetch_v2_instrument(self, **kw):
        raise AssertionError("should not be called")


def test_reader_error_propagates_unwrapped():
    reader = RaisingReader()
    with pytest.raises(RaisingReader._BoomError):
        _run(load_confirmed_breakout_inputs(reader, context=make_context()))


# ============================================================================
# 6. CHEAP PUBLIC-BOUNDARY HARDENING -- non-V2ContextSnapshot context
# ============================================================================
def test_non_v2contextsnapshot_context_raises_before_any_access():
    reader = RecordingReader()
    with pytest.raises(V2ConfirmedBreakoutError):
        _run(load_confirmed_breakout_inputs(reader, context="not-a-context"))  # type: ignore[arg-type]
    assert reader.calls == []


# ============================================================================
# 7. NO WALL CLOCK -- context.T is the only logical time input
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


def test_module_has_no_clock_random_uuid_network_filesystem_access():
    body_src = _executable_body_source(loader_module)
    forbidden = (
        "datetime.now(", "datetime.utcnow(", "time.time(", "time.monotonic(",
        "import random", "import uuid", "import yaml", "os.environ", "os.getenv",
        "requests.", "httpx.", "open(", "asyncpg", "subprocess",
    )
    for token in forbidden:
        assert token not in body_src, f"forbidden token found: {token!r}"


# ============================================================================
# 8. LAYERING -- depends only on the Protocol, never a concrete storage
# module
# ============================================================================
def test_module_does_not_import_storage_db_or_v2_setup_readers():
    tree = ast.parse(inspect.getsource(loader_module))
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        for name in names:
            assert not name.startswith("storage"), f"forbidden import: {name}"


def test_module_imports_nothing_from_runtime_main_notifications():
    tree = ast.parse(inspect.getsource(loader_module))
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        for name in names:
            for banned in ("runtime", "main", "notifications"):
                assert not name.startswith(banned), f"forbidden import: {name}"


def test_load_confirmed_breakout_inputs_is_a_coroutine_function():
    assert inspect.iscoroutinefunction(load_confirmed_breakout_inputs)


# ============================================================================
# 9. END-TO-END: loader output feeds the real detector to a candidate
# ============================================================================
def test_loader_output_feeds_real_detector_to_a_valid_candidate():
    from analytics.forecasting_v2.confirmed_breakout import detect_confirmed_breakout

    level_start = B1H - (LEVEL_LOOKBACK - 1) * ONE_HOUR
    level_grid = tuple(level_start + i * ONE_HOUR for i in range(LEVEL_LOOKBACK))
    resistance_bucket = level_grid[-3]

    reference_1h_rows = []
    raw_1m_rows = []
    for b in level_grid:
        reference_1h_rows.append({
            "exchange": "binance", "symbol": SYMBOL, "market_type": MARKET_TYPE,
            "timeframe": "1h", "calculation_version": H16, "feature_schema_version": 1,
            "bucket_ts": b, "is_usable": True, "has_gap": False, "bars_present": 60,
            "bars_expected": 60, "close_price": 65_800.0,
        })
        for m in range(60):
            ts = b + timedelta(minutes=m)
            high = 66_200.0 if (b == resistance_bucket and m == 0) else 65_900.0
            low = 65_700.0
            raw_1m_rows.append(
                {"exchange": "binance", "symbol": SYMBOL, "ts": ts, "high": high, "low": low})

    proxy_start = B1H - (RANGE_PROXY_N - 1) * ONE_HOUR
    consensus_1h_rows = tuple({
        "symbol": SYMBOL, "market_type": MARKET_TYPE, "timeframe": "1h",
        "calculation_version": H16, "feature_schema_version": 1,
        "bucket_ts": proxy_start + i * ONE_HOUR,
        "min_coverage_ratio": 0.9, "consensus_confidence": 80.0, "range_width_pct_median": 0.5,
    } for i in range(RANGE_PROXY_N))

    reference_5m_rows = (
        {"exchange": "binance", "symbol": SYMBOL, "market_type": MARKET_TYPE, "timeframe": "5m",
         "calculation_version": H16, "feature_schema_version": 1, "bucket_ts": B5 - FIVE,
         "is_usable": True, "has_gap": False, "bars_present": 5, "bars_expected": 5,
         "close_price": 66_180.0},
        {"exchange": "binance", "symbol": SYMBOL, "market_type": MARKET_TYPE, "timeframe": "5m",
         "calculation_version": H16, "feature_schema_version": 1, "bucket_ts": B5,
         "is_usable": True, "has_gap": False, "bars_present": 5, "bars_expected": 5,
         "close_price": 66_240.0},
    )
    instrument = {"exchange": "binance", "symbol": SYMBOL, "market_type": MARKET_TYPE,
                 "tick_size": 0.1}

    reader = RecordingReader(
        consensus_1h_rows=consensus_1h_rows, reference_1h_rows=tuple(reference_1h_rows),
        reference_1m_rows=tuple(raw_1m_rows), reference_5m_rows=reference_5m_rows,
        instrument=instrument)
    inputs = _run(load_confirmed_breakout_inputs(reader, context=make_context()))
    candidate = detect_confirmed_breakout(inputs)
    assert candidate is not None
    assert candidate.direction == "LONG"
    assert candidate.level_price == 66_200.0
