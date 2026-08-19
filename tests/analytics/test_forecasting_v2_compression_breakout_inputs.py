"""Tests for analytics/forecasting_v2/compression_breakout_inputs.py
(Stage 5 — Setup Detectors, PR 3 of ~4). No real DB — a fake
`V2SetupHistoryReader` recording every call, following the existing V2
loader test style (tests/analytics/test_forecasting_v2_trend_pullback_
inputs.py's `RecordingReader`).

Exercises: `load_compression_breakout_inputs()` issues EXACTLY 7 reads for
ANY legal `context.T` (unlike `trend_pullback_inputs.py`, there is no
formation-boundary skip — every 5m boundary is a possible breakout
instant); the exact `COMPRESSION_LOOKBACK=16`-bucket inclusive 15m
consensus/percentile/reference-feature windows; the exact half-open raw-
kline window; the exact two-closed-bucket 5m reference-feature window;
the exact current-B5-only 5m consensus window; the exact instrument
lookup; zero unnecessary reads; that the assembler never decides the
setup itself; that it depends only on the `V2SetupHistoryReader` Protocol,
never a concrete storage import; and the cheap non-`V2ContextSnapshot`
`context` boundary check."""
from __future__ import annotations

import ast
import asyncio
import inspect
from datetime import datetime, timedelta, timezone

import pytest

from analytics.forecasting_v2 import compression_breakout_inputs as loader_module
from analytics.forecasting_v2.aligned_inputs import V2_REFERENCE_EXCHANGE
from analytics.forecasting_v2.bias_1h import NEUTRAL_NOT_ESTABLISHED, V2BiasResult
from analytics.forecasting_v2.compression_breakout import (
    COMPRESSION_LOOKBACK, COMPRESSION_PERCENTILE_WINDOW, V2CompressionBreakoutError,
    V2CompressionBreakoutInputs,
)
from analytics.forecasting_v2.compression_breakout_inputs import (
    load_compression_breakout_inputs,
)
from analytics.forecasting_v2.context_snapshot import V2ContextSnapshot
from analytics.forecasting_v2.regime_4h import NON_DIRECTIONAL, V2RegimeResult

UTC = timezone.utc
H16 = "a" * 16
SYMBOL = "BTCUSDT"
MARKET_TYPE = "perp"

T = datetime(2024, 1, 1, 12, 20, tzinfo=UTC)  # legal 5m boundary, not a 15m formation boundary
B5 = datetime(2024, 1, 1, 12, 15, tzinfo=UTC)
B15 = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
B4H = datetime(2024, 1, 1, 8, 0, tzinfo=UTC)
B1H = datetime(2024, 1, 1, 11, 0, tzinfo=UTC)
FIVE = timedelta(minutes=5)
FIFTEEN = timedelta(minutes=15)
LOOKBACK_START_15M = B15 - (COMPRESSION_LOOKBACK - 1) * FIFTEEN


def make_context(*, t=T, b4h=B4H, b1h=B1H) -> V2ContextSnapshot:
    return V2ContextSnapshot(
        T=t, symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=H16,
        feature_schema_version=1,
        regime_4h=V2RegimeResult(
            bucket_ts=b4h, regime=NON_DIRECTIONAL, is_compressed=False,
            price_evi=None, compression_score=0.5),
        bias_1h=V2BiasResult(bucket_ts=b1h, bias=NEUTRAL_NOT_ESTABLISHED, bias_evi=0.0),
    )


def _run(coro):
    return asyncio.run(coro)


class RecordingReader:
    """Satisfies `V2SetupHistoryReader` structurally. Every call is
    recorded with its exact kwargs; each `fetch_v2_*` returns whatever
    canned response was configured, or a legitimately-empty default
    (`()`/`None`) otherwise — matching a real empty-result read."""
    def __init__(self, *, consensus_15m_rows=(), percentile_15m_rows=(), reference_15m_rows=(),
                reference_1m_rows=(), reference_5m_rows=(), consensus_5m_rows=(), instrument=None):
        self._consensus_15m_rows = consensus_15m_rows
        self._percentile_15m_rows = percentile_15m_rows
        self._reference_15m_rows = reference_15m_rows
        self._reference_1m_rows = reference_1m_rows
        self._reference_5m_rows = reference_5m_rows
        self._consensus_5m_rows = consensus_5m_rows
        self._instrument = instrument
        self.calls: list = []

    async def fetch_v2_consensus_feature_window(self, **kw):
        self.calls.append(("consensus_feature_window", kw))
        if kw.get("timeframe") == "5m":
            return self._consensus_5m_rows
        return self._consensus_15m_rows

    async def fetch_v2_consensus_percentile_window(self, **kw):
        self.calls.append(("consensus_percentile_window", kw))
        return self._percentile_15m_rows

    async def fetch_v2_reference_feature_window(self, **kw):
        self.calls.append(("reference_feature_window", kw))
        if kw.get("timeframe") == "5m":
            return self._reference_5m_rows
        return self._reference_15m_rows

    async def fetch_v2_reference_klines(self, **kw):
        self.calls.append(("reference_klines", kw))
        return self._reference_1m_rows

    async def fetch_v2_instrument(self, **kw):
        self.calls.append(("instrument", kw))
        return self._instrument


# ============================================================================
# 1. EVERY legal T issues the full read set (no formation-boundary skip,
# unlike trend_pullback_inputs.py)
# ============================================================================
@pytest.mark.parametrize("t", [
    datetime(2024, 1, 1, 12, 15, tzinfo=UTC),  # a 15m formation boundary too
    datetime(2024, 1, 1, 12, 20, tzinfo=UTC),
    datetime(2024, 1, 1, 12, 25, tzinfo=UTC),
    datetime(2024, 1, 1, 12, 30, tzinfo=UTC),
])
def test_every_legal_t_issues_exactly_seven_reads(t):
    reader = RecordingReader()
    context = make_context(t=t)
    result = _run(load_compression_breakout_inputs(reader, context=context))
    assert isinstance(result, V2CompressionBreakoutInputs)
    assert len(reader.calls) == 7


# ============================================================================
# 2. EXACT READ CONTRACT -- exact arguments/intervals for every call
# ============================================================================
def test_exact_consensus_15m_window_call():
    reader = RecordingReader()
    _run(load_compression_breakout_inputs(reader, context=make_context()))
    calls = [kw for name, kw in reader.calls
             if name == "consensus_feature_window" and kw.get("timeframe") == "15m"]
    assert len(calls) == 1
    kw = calls[0]
    assert kw["symbol"] == SYMBOL
    assert kw["market_type"] == MARKET_TYPE
    assert kw["calculation_version"] == H16
    assert kw["bucket_start"] == LOOKBACK_START_15M
    assert kw["bucket_end"] == B15


def test_exact_percentile_window_call():
    reader = RecordingReader()
    _run(load_compression_breakout_inputs(reader, context=make_context()))
    calls = [kw for name, kw in reader.calls if name == "consensus_percentile_window"]
    assert len(calls) == 1
    kw = calls[0]
    assert kw["symbol"] == SYMBOL
    assert kw["market_type"] == MARKET_TYPE
    assert kw["metric"] == "range_width_pct_median"
    assert kw["timeframe"] == "15m"
    assert kw["percentile_window"] == COMPRESSION_PERCENTILE_WINDOW
    assert kw["calculation_version"] == H16
    assert kw["bucket_start"] == LOOKBACK_START_15M
    assert kw["bucket_end"] == B15


def test_exact_reference_15m_window_call():
    reader = RecordingReader()
    _run(load_compression_breakout_inputs(reader, context=make_context()))
    calls = [kw for name, kw in reader.calls
             if name == "reference_feature_window" and kw.get("timeframe") == "15m"]
    assert len(calls) == 1
    kw = calls[0]
    assert kw["exchange"] == V2_REFERENCE_EXCHANGE
    assert kw["symbol"] == SYMBOL
    assert kw["market_type"] == MARKET_TYPE
    assert kw["calculation_version"] == H16
    assert kw["bucket_start"] == LOOKBACK_START_15M
    assert kw["bucket_end"] == B15


def test_exact_raw_kline_window_call_half_open():
    reader = RecordingReader()
    _run(load_compression_breakout_inputs(reader, context=make_context()))
    calls = [kw for name, kw in reader.calls if name == "reference_klines"]
    assert len(calls) == 1
    kw = calls[0]
    assert kw["exchange"] == V2_REFERENCE_EXCHANGE
    assert kw["symbol"] == SYMBOL
    assert kw["bucket_start"] == LOOKBACK_START_15M
    assert kw["bucket_end"] == B15 + FIFTEEN  # half-open, covers whole lookback + B15's own bucket


def test_exact_reference_5m_window_call_two_closed_buckets():
    reader = RecordingReader()
    _run(load_compression_breakout_inputs(reader, context=make_context()))
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


def test_exact_consensus_5m_window_call_current_b5_only():
    reader = RecordingReader()
    _run(load_compression_breakout_inputs(reader, context=make_context()))
    calls = [kw for name, kw in reader.calls
             if name == "consensus_feature_window" and kw.get("timeframe") == "5m"]
    assert len(calls) == 1
    kw = calls[0]
    assert kw["symbol"] == SYMBOL
    assert kw["market_type"] == MARKET_TYPE
    assert kw["calculation_version"] == H16
    assert kw["bucket_start"] == B5
    assert kw["bucket_end"] == B5


def test_exact_instrument_call():
    reader = RecordingReader()
    _run(load_compression_breakout_inputs(reader, context=make_context()))
    calls = [kw for name, kw in reader.calls if name == "instrument"]
    assert len(calls) == 1
    kw = calls[0]
    assert kw["exchange"] == V2_REFERENCE_EXCHANGE
    assert kw["symbol"] == SYMBOL
    assert kw["market_type"] == MARKET_TYPE


def test_call_order_is_deterministic():
    reader = RecordingReader()
    _run(load_compression_breakout_inputs(reader, context=make_context()))
    names = [name for name, _ in reader.calls]
    assert names == [
        "consensus_feature_window",       # 15m consensus window
        "consensus_percentile_window",    # 15m percentile window
        "reference_feature_window",       # 15m reference window
        "reference_klines",               # raw 1m klines
        "reference_feature_window",       # 5m reference (two buckets)
        "consensus_feature_window",       # 5m consensus (current B5 only)
        "instrument",
    ]


# ============================================================================
# 3. ZERO UNNECESSARY READS
# ============================================================================
def test_no_extra_reads_beyond_the_seven():
    reader = RecordingReader()
    _run(load_compression_breakout_inputs(reader, context=make_context()))
    assert len(reader.calls) == 7
    # exactly 2 consensus_feature_window calls (15m + 5m), 1 percentile,
    # 2 reference_feature_window calls (15m + 5m), 1 klines, 1 instrument.
    counts = {}
    for name, _ in reader.calls:
        counts[name] = counts.get(name, 0) + 1
    assert counts == {
        "consensus_feature_window": 2,
        "consensus_percentile_window": 1,
        "reference_feature_window": 2,
        "reference_klines": 1,
        "instrument": 1,
    }


# ============================================================================
# 4. RESULT SHAPE -- returns whatever exists, never pre-filters/decides
# ============================================================================
def test_result_carries_context_and_raw_rows_unfiltered():
    consensus_row = {"symbol": SYMBOL, "bucket_ts": B15}
    percentile_row = {"metric": "range_width_pct_median", "bucket_ts": B15}
    reference_row = {"exchange": "binance", "bucket_ts": B15}
    raw_row = {"exchange": "binance", "symbol": SYMBOL, "ts": B15}
    reference_5m_row = {"exchange": "binance", "bucket_ts": B5}
    consensus_5m_row = {"symbol": SYMBOL, "bucket_ts": B5}
    instrument = {"tick_size": 0.1}
    reader = RecordingReader(
        consensus_15m_rows=(consensus_row,), percentile_15m_rows=(percentile_row,),
        reference_15m_rows=(reference_row,), reference_1m_rows=(raw_row,),
        reference_5m_rows=(reference_5m_row,), consensus_5m_rows=(consensus_5m_row,),
        instrument=instrument)
    result = _run(load_compression_breakout_inputs(reader, context=make_context()))
    assert result.consensus_15m_rows == (consensus_row,)
    assert result.percentile_15m_rows == (percentile_row,)
    assert result.reference_15m_rows == (reference_row,)
    assert result.reference_1m_rows == (raw_row,)
    assert result.reference_5m_rows == (reference_5m_row,)
    assert result.consensus_5m_rows == (consensus_5m_row,)
    assert result.instrument == instrument


def test_result_with_incomplete_history_still_returned_unfiltered():
    reader = RecordingReader()  # everything empty/None
    result = _run(load_compression_breakout_inputs(reader, context=make_context()))
    assert result.consensus_15m_rows == ()
    assert result.percentile_15m_rows == ()
    assert result.reference_15m_rows == ()
    assert result.reference_1m_rows == ()
    assert result.reference_5m_rows == ()
    assert result.consensus_5m_rows == ()
    assert result.instrument is None


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
        _run(load_compression_breakout_inputs(reader, context=make_context()))


# ============================================================================
# 6. CHEAP PUBLIC-BOUNDARY HARDENING -- non-V2ContextSnapshot context
# ============================================================================
def test_non_v2contextsnapshot_context_raises_before_any_access():
    reader = RecordingReader()
    with pytest.raises(V2CompressionBreakoutError):
        _run(load_compression_breakout_inputs(reader, context="not-a-context"))  # type: ignore[arg-type]
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


def test_load_compression_breakout_inputs_is_a_coroutine_function():
    assert inspect.iscoroutinefunction(load_compression_breakout_inputs)


# ============================================================================
# 9. END-TO-END: loader output feeds the real detector to a candidate
# ============================================================================
_FAMILIES = ("price_structure", "volume", "taker_flow", "oi", "funding", "liquidations")


def _family_maps(*, price_coverage=0.9, price_confidence=80.0, taker_coverage=0.9,
                 taker_confidence=80.0):
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


def test_loader_output_feeds_real_detector_to_a_valid_candidate():
    from analytics.forecasting_v2.compression_breakout import detect_compression_breakout

    compressed_idx = set(range(9, 16))
    lookback_start = LOOKBACK_START_15M
    lookback_grid = tuple(lookback_start + i * FIFTEEN for i in range(COMPRESSION_LOOKBACK))
    consensus_rows = []
    percentile_rows = []
    for i, b in enumerate(lookback_grid):
        coverage_by_metric, data_confidence_by_metric = _family_maps()
        consensus_rows.append({
            "symbol": SYMBOL, "market_type": MARKET_TYPE, "timeframe": "15m",
            "calculation_version": H16, "feature_schema_version": 1, "bucket_ts": b,
            "min_coverage_ratio": 0.9, "consensus_confidence": 80.0,
            "range_width_pct_median": 0.3,
            "coverage_by_metric": coverage_by_metric,
            "data_confidence_by_metric": data_confidence_by_metric,
        })
        score = 0.82 if i in compressed_idx else 0.10
        percentile_rows.append({
            "scope": "consensus", "exchange": "", "symbol": SYMBOL, "market_type": MARKET_TYPE,
            "metric": "range_width_pct_median", "timeframe": "15m", "percentile_window": "30d",
            "calculation_version": H16, "feature_schema_version": 1, "bucket_ts": b,
            "value": 0.01, "percentile_rank": 1.0 - score, "confidence_tier": "mature",
            "sample_window_end": b - timedelta(minutes=1),
        })

    reference_15m_rows = []
    raw_1m_rows = []
    run_start = lookback_grid[9]
    run_end = lookback_grid[15]
    for i in compressed_idx:
        b = lookback_grid[i]
        reference_15m_rows.append({
            "exchange": "binance", "symbol": SYMBOL, "market_type": MARKET_TYPE,
            "timeframe": "15m", "calculation_version": H16, "feature_schema_version": 1,
            "bucket_ts": b, "is_usable": True, "has_gap": False, "bars_present": 15,
            "bars_expected": 15, "close_price": 64_000.0,
        })
        for m in range(15):
            ts = b + timedelta(minutes=m)
            high = 64_100.0 if (b == run_end and m == 0) else 64_050.0
            low = 63_800.0 if (b == run_start and m == 0) else 63_950.0
            raw_1m_rows.append(
                {"exchange": "binance", "symbol": SYMBOL, "ts": ts, "high": high, "low": low})

    reference_5m_rows = (
        {"exchange": "binance", "symbol": SYMBOL, "market_type": MARKET_TYPE, "timeframe": "5m",
         "calculation_version": H16, "feature_schema_version": 1, "bucket_ts": B5 - FIVE,
         "is_usable": True, "has_gap": False, "bars_present": 5, "bars_expected": 5,
         "close_price": 63_820.0},
        {"exchange": "binance", "symbol": SYMBOL, "market_type": MARKET_TYPE, "timeframe": "5m",
         "calculation_version": H16, "feature_schema_version": 1, "bucket_ts": B5,
         "is_usable": True, "has_gap": False, "bars_present": 5, "bars_expected": 5,
         "close_price": 63_740.0},
    )
    trigger_coverage_by_metric, trigger_data_confidence_by_metric = _family_maps()
    consensus_5m_rows = ({
        "symbol": SYMBOL, "market_type": MARKET_TYPE, "timeframe": "5m",
        "calculation_version": H16, "feature_schema_version": 1, "bucket_ts": B5,
        "min_coverage_ratio": 0.9, "consensus_confidence": 80.0,
        "price_direction_agreement": 0.8, "taker_delta_notional_usd_sum": -1000.0,
        "coverage_by_metric": trigger_coverage_by_metric,
        "data_confidence_by_metric": trigger_data_confidence_by_metric,
    },)
    instrument = {"exchange": "binance", "symbol": SYMBOL, "market_type": MARKET_TYPE,
                 "tick_size": 0.1}

    reader = RecordingReader(
        consensus_15m_rows=tuple(consensus_rows), percentile_15m_rows=tuple(percentile_rows),
        reference_15m_rows=tuple(reference_15m_rows), reference_1m_rows=tuple(raw_1m_rows),
        reference_5m_rows=reference_5m_rows, consensus_5m_rows=consensus_5m_rows,
        instrument=instrument)
    inputs = _run(load_compression_breakout_inputs(reader, context=make_context()))
    candidate = detect_compression_breakout(inputs)
    assert candidate is not None
    assert candidate.direction == "SHORT"
    assert candidate.range_low == 63_800.0
    assert candidate.range_high == 64_100.0
