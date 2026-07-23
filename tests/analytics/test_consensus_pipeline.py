"""Unit tests for analytics/feature_engine/consensus_pipeline.py.

Drives the thin one-bucket consensus orchestration with a fake writer (no DB, no
Docker, no network, no clock). async is driven with asyncio.run. The already
merged exchange-feature pipeline is NOT tested here.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from common.stage2_config import Stage2Config
from common.versioning import compute_calculation_version
from analytics.feature_engine.models import ExchangeFeatureVector
from analytics.feature_engine.consensus_models import ConsensusFeatureVector, FAMILIES
from analytics.feature_engine.consensus import compute_consensus_features
from analytics.feature_engine.consensus_input_adapter import (
    ConsensusInputError, build_consensus_feature_request,
)
from analytics.feature_engine.consensus_pipeline import (
    ConsensusFeatureWriter, process_consensus_feature_bucket,
)

CFG = Stage2Config.load()
BASE = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
CODE = "code-v1"
CH = CFG.resolve("BTCUSDT").config_hash()
CV = compute_calculation_version(CFG.feature_schema_version, CH, CODE)
EXS = ("binance", "bybit", "okx")
LQ = {"binance": "snapshot", "bybit": "full", "okx": "aggregated"}


def _efv(ex, **over):
    base = dict(
        exchange=ex, symbol="BTCUSDT", market_type="perp", timeframe="5m",
        bucket_ts=BASE, feature_schema_version=CFG.feature_schema_version,
        calculation_version=CV, price_move_pct=1.0, range_width_pct=5.0,
        close_price=100.0, volume_raw=10.0, volume_raw_unit="base",
        volume_notional_usd=1000.0, taker_buy_notional_usd=600.0,
        taker_sell_notional_usd=400.0, taker_delta_notional_usd=200.0,
        cvd_delta_notional_usd=200.0, oi_change_pct=2.0, oi_unit="base",
        funding_rate=0.0001, long_liquidation_notional=0.0,
        short_liquidation_notional=0.0, liquidation_event_count=0,
        liquidation_feed_quality=LQ[ex], is_snapshot_feed=(ex == "binance"),
        bars_expected=5, bars_present=5, has_gap=False, is_usable=True,
        config_hash=CH, config_version=CFG.config_version, code_version=CODE)
    base.update(over)
    return ExchangeFeatureVector(**base)


def _exp():
    return {f: EXS for f in FAMILIES}


def _three():
    return [_efv("binance"), _efv("bybit"), _efv("okx")]


def _run(coro):
    return asyncio.run(coro)


class RecordingWriter:
    def __init__(self, ret=1):
        self.calls = []
        self._ret = ret

    async def upsert_consensus_feature_vectors(self, rows):
        self.calls.append(rows)
        return self._ret


class RaisingWriter:
    def __init__(self):
        self.calls = []

    async def upsert_consensus_feature_vectors(self, rows):
        self.calls.append(rows)
        raise RuntimeError("writer boom")


def _process(writer, features=None, expected=None, exclusions=None, cfg=CFG):
    return _run(process_consensus_feature_bucket(
        writer, cfg,
        exchange_features=(features if features is not None else _three()),
        expected_exchanges_by_family=(expected if expected is not None else _exp()),
        exclusion_reasons_by_family=(exclusions if exclusions is not None else {})))


# ============================================================================
# success order + shape
# ============================================================================
def test_success_calls_writer_once_with_one_tuple():
    w = RecordingWriter()
    out = _process(w)
    assert len(w.calls) == 1
    rows = w.calls[0]
    assert isinstance(rows, tuple) and len(rows) == 1
    assert isinstance(rows[0], ConsensusFeatureVector)


def test_returned_object_is_the_exact_computed_vector():
    w = RecordingWriter()
    out = _process(w)
    # identity: the returned object IS the one handed to the writer
    assert out is w.calls[0][0]
    # and it equals the vector the real core computes for the same inputs
    expected_vec = compute_consensus_features(
        build_consensus_feature_request(
            CFG, exchange_features=_three(),
            expected_exchanges_by_family=_exp(), exclusion_reasons_by_family={}))
    assert out == expected_vec


def test_adapter_arguments_forwarded_exactly():
    # a 2-EFV partial with explicit okx exclusion flows through unchanged
    w = RecordingWriter()
    out = _process(w, features=[_efv("binance"), _efv("bybit")],
                   exclusions={f: {"okx": "NO_DATA"} for f in FAMILIES})
    assert out.is_partial_consensus is True
    assert out is w.calls[0][0]


def test_real_adapter_core_integration_with_fake_writer():
    w = RecordingWriter(ret=1)
    out = _process(w)
    assert out.symbol == "BTCUSDT" and out.calculation_version == CV
    assert out.exchanges_expected_max == 3


# ============================================================================
# failure propagation (writer not called on upstream failure)
# ============================================================================
def test_adapter_error_propagates_and_writer_not_called():
    w = RecordingWriter()
    with pytest.raises(ConsensusInputError):
        _process(w, features=[_efv("binance"), _efv("bybit", timeframe="1h")])
    assert w.calls == []


def test_adapter_error_bad_container_writer_not_called():
    w = RecordingWriter()
    with pytest.raises(ConsensusInputError):
        _run(process_consensus_feature_bucket(
            w, CFG, exchange_features=None,
            expected_exchanges_by_family=_exp(), exclusion_reasons_by_family={}))
    assert w.calls == []


def test_consensus_core_error_propagates_and_writer_not_called():
    # expected okx but no EFV and no exclusion -> the CORE raises ConsensusError;
    # it must propagate unchanged and the writer must not be called.
    from analytics.feature_engine.consensus import ConsensusError
    w = RecordingWriter()
    with pytest.raises(ConsensusError):
        _process(w, features=[_efv("binance"), _efv("bybit")])   # okx missing, no exclusion
    assert w.calls == []


def test_writer_error_propagates_unchanged():
    w = RaisingWriter()
    with pytest.raises(RuntimeError, match="writer boom"):
        _process(w)
    assert len(w.calls) == 1                      # writer WAS reached exactly once


# ============================================================================
# architecture / determinism
# ============================================================================
def test_no_concrete_database_dependency_in_module():
    import ast
    from pathlib import Path
    src = Path("analytics/feature_engine/consensus_pipeline.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    for banned in ("storage", "asyncpg", "redis", "socket", "subprocess", "time"):
        assert banned not in imported


def test_stage2_disabled_allows_explicit_execution():
    assert CFG.enabled is False
    w = RecordingWriter()
    out = _process(w)
    assert isinstance(out, ConsensusFeatureVector)


def test_repeated_identical_calls_are_deterministic():
    w1 = RecordingWriter()
    w2 = RecordingWriter()
    a = _process(w1)
    b = _process(w2)
    assert a == b                                 # same computed vector
    assert len(w1.calls) == 1 and len(w2.calls) == 1


def test_writer_return_value_does_not_affect_returned_vector():
    # the function returns the vector, not the writer's int row-count
    w = RecordingWriter(ret=999)
    out = _process(w)
    assert isinstance(out, ConsensusFeatureVector)
