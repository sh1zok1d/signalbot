from __future__ import annotations

import copy
import dataclasses
from datetime import datetime, timedelta, timezone
from types import MappingProxyType

import pytest

from common.stage2_config import Stage2Config
from common.versioning import compute_calculation_version
from analytics.feature_engine.consensus_input_adapter import (
    ConsensusInputError,
    build_consensus_feature_request,
)
from analytics.feature_engine.consensus_models import FAMILIES
from analytics.feature_engine.models import ExchangeFeatureVector

CFG = Stage2Config.load()
B = datetime(2026, 1, 1, tzinfo=timezone.utc)
EXS = ("binance", "bybit", "okx")
EXP = {f: EXS for f in FAMILIES}
LQ = {"binance": "snapshot", "bybit": "full", "okx": "aggregated"}


def _efv(ex="binance", **over):
    d = dict(
        exchange=ex, symbol="BTCUSDT", market_type="perp", timeframe="5m", bucket_ts=B,
        feature_schema_version=1, calculation_version=compute_calculation_version(
            CFG.feature_schema_version, CFG.resolve("BTCUSDT").config_hash(), "code-v1"),
        price_move_pct=1.0, range_width_pct=5.0, close_price=100.0,
        volume_raw=10.0, volume_raw_unit="base", volume_notional_usd=1000.0,
        taker_buy_notional_usd=600.0, taker_sell_notional_usd=400.0,
        taker_delta_notional_usd=200.0, cvd_delta_notional_usd=200.0,
        oi_change_pct=2.0, oi_unit="base", funding_rate=0.0001,
        long_liquidation_notional=0.0, short_liquidation_notional=0.0,
        liquidation_event_count=0, liquidation_feed_quality=LQ[ex], is_snapshot_feed=(ex == "binance"),
        bars_expected=5, bars_present=5, has_gap=False, is_usable=True,
        config_hash=CFG.resolve("BTCUSDT").config_hash(), config_version=CFG.config_version,
        code_version="code-v1")
    d.update(over)
    return ExchangeFeatureVector(**d)


def _request(**over):
    d = dict(stage2_config=CFG, exchange_features=tuple(_efv(e) for e in EXS),
             expected_exchanges_by_family=EXP, exclusion_reasons_by_family={},
             symbol="BTCUSDT", market_type="perp", timeframe="5m", bucket_ts=B,
             code_version="code-v1")
    d.update(over)
    cfg = d.pop("stage2_config")
    return build_consensus_feature_request(cfg, **d)


def test_builds_deterministic_consensus_request_from_explicit_inputs():
    req = _request()
    resolved = CFG.resolve("BTCUSDT")
    assert req.symbol == "BTCUSDT"
    assert req.exchange_features == tuple(_efv(e) for e in EXS)
    assert req.expected_exchanges_by_family["oi"] == EXS
    assert req.exclusion_reasons_by_family == {}
    assert req.config_hash == resolved.config_hash()
    assert req.config_version == CFG.config_version
    assert req.feature_schema_version == CFG.feature_schema_version
    assert req.calculation_version == compute_calculation_version(
        CFG.feature_schema_version, resolved.config_hash(), "code-v1")
    assert req.minimum_exchange_coverage == resolved["data_confidence"]["minimum_exchange_coverage"]
    assert dict(req.confidence_weights) == dict(resolved["data_confidence"]["weights"])
    assert req.robust_z_threshold == resolved["outliers"]["robust_z_threshold"]


def test_explicit_denominator_and_exclusions_are_not_inferred_or_mutated():
    expected = {f: ("binance", "bybit") for f in FAMILIES}
    exclusions = {"oi": {"bybit": "STALE"}}
    expected_before = copy.deepcopy(expected)
    exclusions_before = copy.deepcopy(exclusions)
    req = _request(exchange_features=(_efv("binance"), _efv("bybit")),
                   expected_exchanges_by_family=expected,
                   exclusion_reasons_by_family=exclusions)
    assert req.expected_exchanges_by_family["price_structure"] == ("binance", "bybit")
    assert req.exclusion_reasons_by_family["oi"]["bybit"] == "STALE"
    assert expected == expected_before
    assert exclusions == exclusions_before
    with pytest.raises(TypeError):
        req.expected_exchanges_by_family["oi"] = ("okx",)
    with pytest.raises(TypeError):
        req.exclusion_reasons_by_family["oi"]["bybit"] = "OTHER"


@pytest.mark.parametrize("over", [
    {"stage2_config": object()},
    {"exchange_features": object()},
    {"exchange_features": (_efv("binance"), object())},
    {"expected_exchanges_by_family": {"oi": ("binance",)}},
    {"expected_exchanges_by_family": {f: "binance" for f in FAMILIES}},
    {"exclusion_reasons_by_family": {"unknown": {"binance": "X"}}},
    {"exclusion_reasons_by_family": {"oi": {"binance": ""}}},
    {"symbol": ""},
    {"market_type": ""},
    {"timeframe": ""},
    {"bucket_ts": datetime(2026, 1, 1)},
    {"code_version": "  "},
])
def test_representative_malformed_inputs_fail_in_adapter(over):
    with pytest.raises(ConsensusInputError):
        _request(**over)


def test_stage2_disabled_does_not_prevent_explicit_request_build():
    assert CFG.enabled is False
    assert _request().calculation_version


def test_request_build_does_not_mutate_config_or_vectors():
    features = tuple(_efv(e) for e in EXS)
    before_features = copy.deepcopy(features)
    before_config = copy.deepcopy(CFG._raw)
    _request(exchange_features=features)
    assert features == before_features
    assert CFG._raw == before_config


def test_code_version_change_forks_calculation_version():
    assert _request(code_version="code-v1").calculation_version != _request(code_version="code-v2").calculation_version
