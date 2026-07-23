from __future__ import annotations

import asyncio
import ast
from datetime import datetime, timezone
from pathlib import Path

import pytest

from common.stage2_config import Stage2Config
from analytics.feature_engine.consensus import ConsensusError
from analytics.feature_engine.consensus_input_adapter import ConsensusInputError
from analytics.feature_engine.consensus_models import FAMILIES
from analytics.feature_engine.consensus_pipeline import process_consensus_feature_bucket
from analytics.feature_engine.models import ExchangeFeatureVector

CFG = Stage2Config.load()
B = datetime(2026, 1, 1, tzinfo=timezone.utc)
EXS = ("binance", "bybit", "okx")
EXP = {f: EXS for f in FAMILIES}
LQ = {"binance": "snapshot", "bybit": "full", "okx": "aggregated"}


def _run(coro):
    return asyncio.run(coro)


def _efv(ex="binance", **over):
    resolved = CFG.resolve("BTCUSDT")
    from common.versioning import compute_calculation_version
    d = dict(
        exchange=ex, symbol="BTCUSDT", market_type="perp", timeframe="5m", bucket_ts=B,
        feature_schema_version=CFG.feature_schema_version,
        calculation_version=compute_calculation_version(CFG.feature_schema_version, resolved.config_hash(), "code-v1"),
        price_move_pct=1.0, range_width_pct=5.0, close_price=100.0,
        volume_raw=10.0, volume_raw_unit="base", volume_notional_usd=1000.0,
        taker_buy_notional_usd=600.0, taker_sell_notional_usd=400.0,
        taker_delta_notional_usd=200.0, cvd_delta_notional_usd=200.0,
        oi_change_pct=2.0, oi_unit="base", funding_rate=0.0001,
        long_liquidation_notional=0.0, short_liquidation_notional=0.0,
        liquidation_event_count=0, liquidation_feed_quality=LQ[ex], is_snapshot_feed=(ex == "binance"),
        bars_expected=5, bars_present=5, has_gap=False, is_usable=True,
        config_hash=resolved.config_hash(), config_version=CFG.config_version, code_version="code-v1")
    d.update(over)
    return ExchangeFeatureVector(**d)


class Writer:
    def __init__(self, exc=None, events=None):
        self.exc = exc
        self.events = events
        self.calls = []

    async def upsert_consensus_feature_vectors(self, rows):
        self.calls.append(rows)
        if self.events is not None:
            self.events.append("write")
        if self.exc is not None:
            raise self.exc
        return len(rows)


def _call(writer, **over):
    d = dict(exchange_features=tuple(_efv(e) for e in EXS), expected_exchanges_by_family=EXP,
             exclusion_reasons_by_family={}, symbol="BTCUSDT", market_type="perp",
             timeframe="5m", bucket_ts=B, code_version="code-v1")
    d.update(over)
    return process_consensus_feature_bucket(writer, CFG, **d)


def test_happy_path_computes_writes_one_tuple_and_returns_same_vector():
    w = Writer()
    vector = _run(_call(w))
    assert len(w.calls) == 1
    assert isinstance(w.calls[0], tuple)
    assert len(w.calls[0]) == 1
    assert w.calls[0][0] is vector
    assert vector.symbol == "BTCUSDT"
    assert vector.coverage_by_metric["oi"].available == 3


def test_no_extra_write_occurs():
    events = []
    w = Writer(events=events)
    _run(_call(w))
    assert events == ["write"]
    assert len(w.calls) == 1


@pytest.mark.parametrize("over", [
    {"expected_exchanges_by_family": {"oi": ("binance",)}},
    {"bucket_ts": datetime(2026, 1, 1)},
    {"code_version": ""},
])
def test_adapter_validation_fails_before_writer(over):
    w = Writer()
    with pytest.raises(ConsensusInputError):
        _run(_call(w, **over))
    assert w.calls == []


def test_computation_failure_propagates_and_writer_not_called():
    w = Writer()
    bad = _efv("okx", bucket_ts=datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc))
    with pytest.raises(ConsensusError):
        _run(_call(w, exchange_features=(_efv("binance"), _efv("bybit"), bad)))
    assert w.calls == []


def test_forced_imported_computation_failure_propagates_and_writer_not_called(monkeypatch):
    import analytics.feature_engine.consensus_pipeline as pipeline
    exc = RuntimeError("compute boom")
    def boom(_request):
        raise exc
    monkeypatch.setattr(pipeline, "compute_consensus_features", boom)
    w = Writer()
    with pytest.raises(RuntimeError) as got:
        _run(_call(w))
    assert got.value is exc
    assert w.calls == []


def test_writer_failure_propagates_after_one_write_attempt():
    exc = RuntimeError("writer boom")
    w = Writer(exc=exc)
    with pytest.raises(RuntimeError) as got:
        _run(_call(w))
    assert got.value is exc
    assert len(w.calls) == 1


def test_explicit_execution_allowed_while_stage2_disabled():
    assert CFG.enabled is False
    vector = _run(_call(Writer()))
    assert vector.consensus_confidence is not None


def test_repeatability_and_one_row_upsert_each_time():
    features = tuple(_efv(e) for e in EXS)
    w = Writer()
    v1 = _run(_call(w, exchange_features=features))
    v2 = _run(_call(w, exchange_features=tuple(reversed(features))))
    assert v1 == v2
    assert len(w.calls) == 2
    assert all(isinstance(rows, tuple) and len(rows) == 1 for rows in w.calls)
    assert features == tuple(_efv(e) for e in EXS)


def test_architecture_boundary_has_no_forbidden_behavior_or_storage_db_import():
    for path in ("analytics/feature_engine/consensus_input_adapter.py",
                 "analytics/feature_engine/consensus_pipeline.py"):
        source = Path(path).read_text()
        tree = ast.parse(source)
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
            assert not isinstance(node, (ast.For, ast.While, ast.AsyncFor)) or path.endswith("consensus_input_adapter.py")
        assert "storage.db" not in imports
        forbidden = ("datetime.now", "utcnow", "sleep", "retry", "create_task", "gather",
                     "Redis", "redis", "os.environ", "subprocess", "open(", "Path(",
                     "init_schema", "init_stage2_schema", "percentile", "fetch_")
        for token in forbidden:
            assert token not in source
