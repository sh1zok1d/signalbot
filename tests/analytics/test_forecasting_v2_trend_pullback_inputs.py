"""Tests for analytics/forecasting_v2/trend_pullback_inputs.py (Stage 5 —
Setup Detectors, PR 2 of ~4). No real DB — a fake `V2SetupHistoryReader`
recording every call, following the existing V2 loader test style
(tests/analytics/test_forecasting_v2_aligned_inputs.py's `RecordingReader`).

Exercises: `load_trend_pullback_inputs()` skips ALL storage reads and
returns `None` for a non-15m-formation `T`; issues exactly ONE call each
to `fetch_v2_reference_feature_window`/`fetch_v2_consensus_feature_
window`/`fetch_v2_instrument`, with the exact `LOOKBACK_15M=48`/
`RANGE_PROXY_N=14` inclusive intervals and exact identity, and ZERO calls
to `fetch_v2_consensus_percentile_window`/`fetch_v2_reference_klines`;
that the assembler never decides the setup itself (it returns whatever
history physically exists, unfiltered); that it depends only on the
`V2SetupHistoryReader` Protocol, never a concrete storage import; and the
cheap non-`V2ContextSnapshot` `context` boundary check."""
from __future__ import annotations

import ast
import inspect
from datetime import datetime, timedelta, timezone

import pytest

from analytics.forecasting_v2 import trend_pullback_inputs as loader_module
from analytics.forecasting_v2.aligned_inputs import V2_REFERENCE_EXCHANGE
from analytics.forecasting_v2.bias_1h import BULLISH, V2BiasResult
from analytics.forecasting_v2.context_snapshot import V2ContextSnapshot
from analytics.forecasting_v2.regime_4h import BULLISH_TRENDING, V2RegimeResult
from analytics.forecasting_v2.setup_common import RANGE_PROXY_N
from analytics.forecasting_v2.trend_pullback import (
    LOOKBACK_15M, V2TrendPullbackError, V2TrendPullbackInputs,
)
from analytics.forecasting_v2.trend_pullback_inputs import load_trend_pullback_inputs

UTC = timezone.utc
H16 = "a" * 16
SYMBOL = "BTCUSDT"
MARKET_TYPE = "perp"

T = datetime(2026, 8, 15, 12, 15, tzinfo=UTC)  # legal 15m formation boundary
B15 = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
B4H = datetime(2026, 8, 15, 8, 0, tzinfo=UTC)
B1H = datetime(2026, 8, 15, 11, 0, tzinfo=UTC)
FIFTEEN = timedelta(minutes=15)


def make_context(*, t=T, b4h=B4H, b1h=B1H) -> V2ContextSnapshot:
    return V2ContextSnapshot(
        T=t, symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=H16,
        feature_schema_version=1,
        regime_4h=V2RegimeResult(bucket_ts=b4h, regime=BULLISH_TRENDING, is_compressed=None),
        bias_1h=V2BiasResult(bucket_ts=b1h, bias=BULLISH),
    )


def _run(coro):
    import asyncio
    return asyncio.run(coro)


class RecordingReader:
    """Satisfies `V2SetupHistoryReader` structurally. Every call is
    recorded with its exact kwargs; each `fetch_v2_*` returns whatever
    canned response was configured, or a legitimately-empty default
    (`()`/`None`) otherwise — matching a real empty-result read."""
    def __init__(self, *, reference_rows=(), proxy_rows=(), instrument=None):
        self._reference_rows = reference_rows
        self._proxy_rows = proxy_rows
        self._instrument = instrument
        self.calls: list = []

    async def fetch_v2_consensus_feature_window(self, **kw):
        self.calls.append(("consensus_feature_window", kw))
        return self._proxy_rows

    async def fetch_v2_consensus_percentile_window(self, **kw):
        self.calls.append(("consensus_percentile_window", kw))
        return ()

    async def fetch_v2_reference_feature_window(self, **kw):
        self.calls.append(("reference_feature_window", kw))
        return self._reference_rows

    async def fetch_v2_reference_klines(self, **kw):
        self.calls.append(("reference_klines", kw))
        return ()

    async def fetch_v2_instrument(self, **kw):
        self.calls.append(("instrument", kw))
        return self._instrument


# ============================================================================
# 1. NON-15m-FORMATION T -- zero reads
# ============================================================================
@pytest.mark.parametrize("t", [
    datetime(2026, 8, 15, 12, 20, tzinfo=UTC),
    datetime(2026, 8, 15, 12, 25, tzinfo=UTC),
    datetime(2026, 8, 15, 12, 10, tzinfo=UTC),
])
def test_non_formation_boundary_returns_none_zero_reads(t):
    reader = RecordingReader()
    context = make_context(t=t, b4h=B4H, b1h=B1H)
    result = _run(load_trend_pullback_inputs(reader, context=context))
    assert result is None
    assert reader.calls == []


@pytest.mark.parametrize("t", [
    datetime(2026, 8, 15, 12, 15, tzinfo=UTC),
    datetime(2026, 8, 15, 12, 30, tzinfo=UTC),
    datetime(2026, 8, 15, 13, 0, tzinfo=UTC),
])
def test_formation_boundary_issues_reads(t):
    from analytics.forecasting_v2.alignment import selected_bucket
    reader = RecordingReader()
    context = make_context(t=t, b4h=selected_bucket("4h", t), b1h=selected_bucket("1h", t))
    result = _run(load_trend_pullback_inputs(reader, context=context))
    assert result is not None
    assert len(reader.calls) == 3


# ============================================================================
# 2. EXACT READ CONTRACT -- one of each, exact intervals/identity, zero
# unnecessary reads (percentile window / raw klines)
# ============================================================================
def test_exact_reference_feature_window_call():
    reader = RecordingReader()
    context = make_context()
    _run(load_trend_pullback_inputs(reader, context=context))

    ref_calls = [kw for name, kw in reader.calls if name == "reference_feature_window"]
    assert len(ref_calls) == 1
    kw = ref_calls[0]
    assert kw["exchange"] == V2_REFERENCE_EXCHANGE
    assert kw["symbol"] == SYMBOL
    assert kw["market_type"] == MARKET_TYPE
    assert kw["timeframe"] == "15m"
    assert kw["calculation_version"] == H16
    assert kw["bucket_start"] == B15 - (LOOKBACK_15M - 1) * FIFTEEN
    assert kw["bucket_end"] == B15


def test_exact_consensus_feature_window_call():
    reader = RecordingReader()
    context = make_context()
    _run(load_trend_pullback_inputs(reader, context=context))

    proxy_calls = [kw for name, kw in reader.calls if name == "consensus_feature_window"]
    assert len(proxy_calls) == 1
    kw = proxy_calls[0]
    assert kw["symbol"] == SYMBOL
    assert kw["market_type"] == MARKET_TYPE
    assert kw["timeframe"] == "15m"
    assert kw["calculation_version"] == H16
    assert kw["bucket_start"] == B15 - (RANGE_PROXY_N - 1) * FIFTEEN
    assert kw["bucket_end"] == B15


def test_exact_instrument_call():
    reader = RecordingReader()
    context = make_context()
    _run(load_trend_pullback_inputs(reader, context=context))

    instrument_calls = [kw for name, kw in reader.calls if name == "instrument"]
    assert len(instrument_calls) == 1
    kw = instrument_calls[0]
    assert kw["exchange"] == V2_REFERENCE_EXCHANGE
    assert kw["symbol"] == SYMBOL
    assert kw["market_type"] == MARKET_TYPE


def test_zero_percentile_window_or_kline_reads():
    reader = RecordingReader()
    context = make_context()
    _run(load_trend_pullback_inputs(reader, context=context))

    assert not any(name == "consensus_percentile_window" for name, _ in reader.calls)
    assert not any(name == "reference_klines" for name, _ in reader.calls)


def test_exactly_three_reads_total():
    reader = RecordingReader()
    context = make_context()
    _run(load_trend_pullback_inputs(reader, context=context))
    assert len(reader.calls) == 3


# ============================================================================
# 3. RESULT SHAPE -- returns whatever exists, never pre-filters/decides
# ============================================================================
def test_result_carries_context_and_raw_rows_unfiltered():
    ref_row = {"exchange": "binance", "bucket_ts": B15, "close_price": 64_000.0}
    proxy_row = {"symbol": SYMBOL, "bucket_ts": B15}
    instrument = {"tick_size": 0.1}
    reader = RecordingReader(reference_rows=(ref_row,), proxy_rows=(proxy_row,),
                             instrument=instrument)
    context = make_context()
    result = _run(load_trend_pullback_inputs(reader, context=context))
    assert isinstance(result, V2TrendPullbackInputs)
    assert result.context is context
    assert result.reference_15m_rows == (ref_row,)
    assert result.range_proxy_15m_rows == (proxy_row,)
    assert result.instrument == instrument


def test_result_with_incomplete_history_still_returned_unfiltered():
    # Only 1 of 48 expected reference rows -- the loader does NOT decide
    # this is unusable; it just returns what exists. detect_trend_pullback
    # is the one that later turns this into None.
    ref_row = {"exchange": "binance", "bucket_ts": B15, "close_price": 64_000.0}
    reader = RecordingReader(reference_rows=(ref_row,), proxy_rows=(), instrument=None)
    context = make_context()
    result = _run(load_trend_pullback_inputs(reader, context=context))
    assert result.reference_15m_rows == (ref_row,)
    assert result.range_proxy_15m_rows == ()
    assert result.instrument is None


def test_result_instrument_none_when_absent():
    reader = RecordingReader(instrument=None)
    context = make_context()
    result = _run(load_trend_pullback_inputs(reader, context=context))
    assert result.instrument is None


# ============================================================================
# 4. READER ERRORS PROPAGATE UNCHANGED (never swallowed into None)
# ============================================================================
class RaisingReader:
    class _BoomError(ValueError):
        pass

    async def fetch_v2_reference_feature_window(self, **kw):
        raise self._BoomError("reader boom")

    async def fetch_v2_consensus_feature_window(self, **kw):
        raise AssertionError("should not be called")

    async def fetch_v2_consensus_percentile_window(self, **kw):
        raise AssertionError("should not be called")

    async def fetch_v2_reference_klines(self, **kw):
        raise AssertionError("should not be called")

    async def fetch_v2_instrument(self, **kw):
        raise AssertionError("should not be called")


def test_reader_error_propagates_unwrapped():
    reader = RaisingReader()
    context = make_context()
    with pytest.raises(RaisingReader._BoomError):
        _run(load_trend_pullback_inputs(reader, context=context))


# ============================================================================
# 4b. CHEAP PUBLIC-BOUNDARY HARDENING — non-V2ContextSnapshot context
# ============================================================================
def test_non_v2contextsnapshot_context_raises_before_any_access():
    reader = RecordingReader()
    with pytest.raises(V2TrendPullbackError):
        _run(load_trend_pullback_inputs(reader, context="not-a-context"))  # type: ignore[arg-type]
    assert reader.calls == []


# ============================================================================
# 5. NO WALL CLOCK -- context.T is the only logical time input
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
# 6. LAYERING -- depends only on the Protocol, never a concrete storage
# module (§35/§56)
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


def test_load_trend_pullback_inputs_is_a_coroutine_function():
    assert inspect.iscoroutinefunction(load_trend_pullback_inputs)
