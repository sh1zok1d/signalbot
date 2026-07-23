from __future__ import annotations

import dataclasses
import math
from datetime import datetime, timedelta, timezone

import pytest

from analytics.feature_engine.consensus import compute_consensus_features
from analytics.feature_engine.consensus_models import ConsensusFeatureRequest, FAMILIES
from analytics.feature_engine.models import ExchangeFeatureVector
from analytics.forecasting.core import LOW_CONSENSUS_CONFIDENCE, compute_forecast_decision
from analytics.forecasting.models import DEFAULT_FORECAST_RULES, ForecastDecision, ForecastError, ForecastRuleSet

BASE = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
CV16 = "0123456789abcdef"
CH64 = "a" * 64
EXS = ("binance", "bybit", "okx")
WEIGHTS = {"coverage": 0.50, "agreement": 0.30, "dispersion": 0.20}
LQ = {"binance": "snapshot", "bybit": "full", "okx": "aggregated"}


def _efv(ex, *, price_move=1.0, tdelta=200.0, volume=1000.0, oi=2.0, funding=0.0001):
    return ExchangeFeatureVector(
        exchange=ex, symbol="BTCUSDT", market_type="perp", timeframe="5m",
        bucket_ts=BASE, feature_schema_version=1, calculation_version=CV16,
        price_move_pct=price_move, range_width_pct=5.0, close_price=100.0,
        volume_raw=10.0, volume_raw_unit="base", volume_notional_usd=volume,
        taker_buy_notional_usd=600.0, taker_sell_notional_usd=400.0,
        taker_delta_notional_usd=tdelta, cvd_delta_notional_usd=tdelta,
        oi_change_pct=oi, oi_unit="base", funding_rate=funding,
        long_liquidation_notional=0.0, short_liquidation_notional=0.0,
        liquidation_event_count=0, liquidation_feed_quality=LQ[ex],
        is_snapshot_feed=(ex == "binance"), bars_expected=5, bars_present=5,
        has_gap=False, is_usable=True, config_hash=CH64,
        config_version="2.1.0", code_version="t")


def _consensus(*, confidence=90.0, min_coverage=1.0):
    req = ConsensusFeatureRequest(
        symbol="BTCUSDT", market_type="perp", timeframe="5m", bucket_ts=BASE,
        feature_schema_version=1, calculation_version=CV16, config_hash=CH64,
        config_version="2.1.0", code_version="t",
        exchange_features=tuple(_efv(e) for e in EXS),
        expected_exchanges_by_family={f: EXS for f in FAMILIES},
        exclusion_reasons_by_family={}, minimum_exchange_coverage=2,
        confidence_weights=WEIGHTS, robust_z_threshold=3.5)
    v = compute_consensus_features(req)
    return dataclasses.replace(v, consensus_confidence=confidence, min_coverage_ratio=min_coverage)


def _decision(**overrides):
    fields = dict(
        symbol="BTCUSDT", market_type="perp", timeframe="5m", bucket_ts=BASE,
        feature_schema_version=1, calculation_version=CV16, config_hash=CH64,
        config_version="2.1.0", code_version="t", rule_version="forecast-rules-v1",
        horizon_set=("15m",), decision="BULLISH", confidence=0.5,
        final_score=0.5, reasons=("COMPOSITE_BULLISH",))
    fields.update(overrides)
    return ForecastDecision(**fields)


def test_default_rules_use_real_percent_confidence_scale():
    assert DEFAULT_FORECAST_RULES.minimum_consensus_confidence == 50.0
    with pytest.raises(ForecastError):
        ForecastRuleSet(minimum_consensus_confidence=101.0)

def test_compute_validates_percent_and_ratio_scales():
    compute_forecast_decision(_consensus(confidence=90.0))
    with pytest.raises(ForecastError):
        compute_forecast_decision(_consensus(confidence=100.1))
    with pytest.raises(ForecastError):
        compute_forecast_decision(dataclasses.replace(_consensus(), data_confidence_overall=100.1))
    with pytest.raises(ForecastError):
        compute_forecast_decision(_consensus(min_coverage=1.1))


def test_confidence_gate_boundary_50_passes_and_below_fails():
    at_boundary = compute_forecast_decision(_consensus(confidence=50.0))
    assert LOW_CONSENSUS_CONFIDENCE not in at_boundary.reasons
    below = compute_forecast_decision(_consensus(confidence=49.999999))
    assert below.decision == "NO_TRADE"
    assert LOW_CONSENSUS_CONFIDENCE in below.reasons


def test_actionable_confidence_uses_percent_scale_and_stays_normalized():
    c = _consensus(confidence=90.0, min_coverage=1.0)
    d = compute_forecast_decision(c)
    expected = min(1.0, abs(d.final_score) * math.sqrt((90.0 / 100.0) * 1.0))
    assert d.confidence == pytest.approx(expected)
    assert 0.0 <= d.confidence <= 1.0


def test_real_consensus_to_forecast_accepts_upstream_scale_without_copy():
    req = ConsensusFeatureRequest(
        symbol="BTCUSDT", market_type="perp", timeframe="5m", bucket_ts=BASE,
        feature_schema_version=1, calculation_version=CV16, config_hash=CH64,
        config_version="2.1.0", code_version="t",
        exchange_features=tuple(_efv(e) for e in EXS),
        expected_exchanges_by_family={f: EXS for f in FAMILIES},
        exclusion_reasons_by_family={}, minimum_exchange_coverage=2,
        confidence_weights=WEIGHTS, robust_z_threshold=3.5)
    consensus = compute_consensus_features(req)
    assert consensus.consensus_confidence is not None
    assert 0.0 <= consensus.consensus_confidence <= 100.0
    assert consensus.consensus_confidence > 1.0
    decision = compute_forecast_decision(consensus)
    assert 0.0 <= decision.confidence <= 1.0
    assert (decision.symbol, decision.market_type, decision.timeframe) == (consensus.symbol, consensus.market_type, consensus.timeframe)
    assert decision.bucket_ts == consensus.bucket_ts
    assert decision.feature_schema_version == consensus.feature_schema_version
    assert decision.calculation_version == consensus.calculation_version
    assert decision.config_hash == consensus.config_hash
    assert decision.config_version == consensus.config_version
    assert decision.code_version == consensus.code_version


@pytest.mark.parametrize("value", ["15m", b"15m", (), ("15m", "15m"), ("",)])
def test_forecast_decision_rejects_bad_horizon_sets(value):
    with pytest.raises(ForecastError):
        _decision(horizon_set=value)


@pytest.mark.parametrize("value", ["COMPOSITE_BULLISH", b"x", (), ("x", "x"), ("",)])
def test_forecast_decision_rejects_bad_reasons(value):
    with pytest.raises(ForecastError):
        _decision(reasons=value)


def test_forecast_decision_detaches_caller_containers():
    horizons = ["15m"]
    reasons = ["COMPOSITE_BULLISH"]
    d = _decision(horizon_set=horizons, reasons=reasons)
    horizons.append("30m")
    reasons.append("x")
    assert d.horizon_set == ("15m",)
    assert d.reasons == ("COMPOSITE_BULLISH",)


@pytest.mark.parametrize("field,value", [
    ("symbol", "ETHUSDT"), ("market_type", "spot"), ("timeframe", "1m"),
    ("bucket_ts", datetime(2026, 1, 1, 0, 0)),
    ("bucket_ts", datetime(2026, 1, 1, 0, 0, 1, tzinfo=timezone.utc)),
    ("bucket_ts", datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc)),
    ("feature_schema_version", True), ("feature_schema_version", 0),
    ("calculation_version", "0123456789abcdeg"), ("calculation_version", "ABC3456789abcdef"),
    ("config_hash", "b" * 63), ("config_hash", "B" * 64),
    ("config_version", ""), ("code_version", ""), ("rule_version", ""),
])
def test_forecast_decision_rejects_invalid_identity_and_versions(field, value):
    with pytest.raises(ForecastError):
        _decision(**{field: value})
