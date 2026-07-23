"""Tests for the thin Stage 2.1 exchange-feature pipeline."""
from __future__ import annotations

import asyncio
import ast
import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType

import pytest

from common.stage2_config import Stage2Config
from storage.stage2_readers import ExchangeFeatureRawBundle
from analytics.feature_engine.input_adapter import FeatureInputError
from analytics.feature_engine.pipeline import process_exchange_feature_bucket

CFG = Stage2Config.load()
EX, SYM, MT = "binance", "BTCUSDT", "perp"
B = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.run(coro)


def _m(**kw):
    return MappingProxyType(dict(kw))


def _kline(minute, **kw):
    base = dict(exchange=EX, symbol=SYM, ts=B + timedelta(minutes=minute),
                open=100.0 + minute, high=110.0 + minute, low=95.0 + minute,
                close=101.0 + minute, volume=10.0 + minute,
                taker_buy_volume=1.0 + minute, taker_sell_volume=0.5 + minute)
    base.update(kw)
    return _m(**base)


def _oi(minute, oi_raw=100.0, **kw):
    base = dict(exchange=EX, symbol=SYM, ts=B + timedelta(minutes=minute),
                oi_raw=oi_raw, oi_unit="base")
    base.update(kw)
    return _m(**base)


def _fund(**kw):
    base = dict(exchange=EX, symbol=SYM, ts=B - timedelta(minutes=1), funding_rate=0.0001)
    base.update(kw)
    return _m(**base)


def _liq(id_, minute, side="long", notional=100.0, **kw):
    base = dict(id=id_, exchange=EX, symbol=SYM, ts=B + timedelta(minutes=minute),
                side=side, notional=notional, is_snapshot_feed=True)
    base.update(kw)
    return _m(**base)


def _inst(**kw):
    base = dict(exchange=EX, symbol=SYM, market_type=MT, exchange_instrument_id="BTCUSDT",
                quantity_unit="base", contract_multiplier=None, tick_size=0.1,
                price_precision=None, quantity_precision=None,
                metadata_source="exchange_api", fetched_at=B, is_stale=False, note=None)
    base.update(kw)
    return _m(**base)


def _cap(**kw):
    base = dict(exchange=EX, symbol=SYM, market_type=MT, metric="liquidations",
                live_supported=True, historical_supported=False, coverage_type="snapshot",
                expected_freshness_s=None, enabled=True)
    base.update(kw)
    return _m(**base)


def _bundle(**kw):
    vals = dict(klines=tuple(_kline(i) for i in range(5)),
                open_interest=(_oi(0, 100.0), _oi(4, 110.0)),
                latest_funding=_fund(), liquidations=(_liq(1, 1), _liq(2, 2, side="short")),
                instrument=_inst(), liquidation_capability=_cap())
    vals.update(kw)
    return ExchangeFeatureRawBundle(**vals)


class Reader:
    def __init__(self, bundle=None, exc=None, events=None):
        self.bundle = _bundle() if bundle is None else bundle
        self.exc = exc
        self.calls = []
        self.events = events

    async def fetch_exchange_feature_raw_bundle(self, **kw):
        self.calls.append(kw)
        if self.events is not None:
            self.events.append("read")
        if self.exc is not None:
            raise self.exc
        return self.bundle


class Writer:
    def __init__(self, exc=None, events=None):
        self.exc = exc
        self.calls = []
        self.events = events

    async def upsert_exchange_feature_vectors(self, rows):
        self.calls.append(rows)
        if self.events is not None:
            self.events.append("write")
        if self.exc is not None:
            raise self.exc
        return len(rows)


def _call(reader, writer, **over):
    kw = dict(exchange=EX, symbol=SYM, market_type=MT, timeframe="5m", bucket_ts=B,
              code_version="code-v1", liquidation_feed_available=True)
    kw.update(over)
    return process_exchange_feature_bucket(reader, writer, CFG, **kw)


def test_happy_path_reads_computes_writes_one_tuple_and_returns_same_vector():
    r, w = Reader(), Writer()
    vector = _run(_call(r, w))
    assert len(r.calls) == 1
    assert r.calls[0]["bucket_start"] == B
    assert r.calls[0]["bucket_end"] == B + timedelta(minutes=5)
    assert len(w.calls) == 1
    assert isinstance(w.calls[0], tuple)
    assert len(w.calls[0]) == 1
    assert w.calls[0][0] is vector
    assert vector.exchange == EX and vector.timeframe == "5m"


def test_exact_operation_order_has_no_extra_io():
    events = []
    r, w = Reader(events=events), Writer(events=events)
    _run(_call(r, w))
    assert events == ["read", "write"]
    assert len(r.calls) == 1
    assert len(w.calls) == 1


@pytest.mark.parametrize("over", [
    {"exchange": "bitget"},
    {"timeframe": "3m"},
    {"bucket_ts": datetime(2026, 3, 1)},
    {"code_version": "   "},
    {"liquidation_feed_available": "yes"},
])
def test_public_input_validation_happens_before_reader_and_writer(over):
    r, w = Reader(), Writer()
    with pytest.raises(FeatureInputError):
        _run(_call(r, w, **over))
    assert r.calls == []
    assert w.calls == []


def test_reader_failure_propagates_unchanged_and_writer_not_called():
    exc = RuntimeError("reader boom")
    r, w = Reader(exc=exc), Writer()
    with pytest.raises(RuntimeError) as got:
        _run(_call(r, w))
    assert got.value is exc
    assert len(r.calls) == 1
    assert w.calls == []


def test_assembly_failure_propagates_feature_input_error_and_writer_not_called():
    bad = _bundle(klines=(object(),))
    r, w = Reader(bundle=bad), Writer()
    with pytest.raises(FeatureInputError):
        _run(_call(r, w))
    assert len(r.calls) == 1
    assert w.calls == []


def test_computation_failure_propagates_and_writer_not_called(monkeypatch):
    import analytics.feature_engine.pipeline as pipeline
    exc = RuntimeError("compute boom")
    def boom(_request):
        raise exc
    monkeypatch.setattr(pipeline, "compute_exchange_features", boom)
    r, w = Reader(), Writer()
    with pytest.raises(RuntimeError) as got:
        _run(_call(r, w))
    assert got.value is exc
    assert len(r.calls) == 1
    assert w.calls == []


def test_writer_failure_propagates_after_one_read_and_one_write_attempt():
    exc = RuntimeError("writer boom")
    r, w = Reader(), Writer(exc=exc)
    with pytest.raises(RuntimeError) as got:
        _run(_call(r, w))
    assert got.value is exc
    assert len(r.calls) == 1
    assert len(w.calls) == 1


def test_explicit_execution_allowed_while_stage2_master_gate_disabled():
    assert CFG.enabled is False
    vector = _run(_call(Reader(), Writer()))
    assert vector.is_usable is True


def test_repeatability_one_row_upsert_each_time_and_inputs_not_mutated():
    bundle = _bundle()
    before_bundle = repr(bundle)
    before_config = copy.deepcopy(CFG._raw)
    w = Writer()
    v1 = _run(_call(Reader(bundle=bundle), w))
    v2 = _run(_call(Reader(bundle=bundle), w))
    assert v1 == v2
    assert len(w.calls) == 2
    assert all(isinstance(rows, tuple) and len(rows) == 1 for rows in w.calls)
    assert repr(bundle) == before_bundle
    assert CFG._raw == before_config


def test_architecture_boundary_has_no_forbidden_behavior_or_storage_db_import():
    source = Path("analytics/feature_engine/pipeline.py").read_text()
    tree = ast.parse(source)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
        assert not isinstance(node, (ast.For, ast.While, ast.AsyncFor))
    assert "storage.db" not in imports
    forbidden = ("datetime.now", "utcnow", "sleep", "retry", "create_task", "gather",
                 "Redis", "redis", "os.environ", "subprocess", "open(", "Path(",
                 "init_schema", "init_stage2_schema", "compute_consensus", "percentile")
    for token in forbidden:
        assert token not in source
