"""Unit tests for analytics/forecasting/persistence.py.

Pure/deterministic — no DB, network, clock. Uses real ConsensusFeatureVector and
real ForecastDecision objects (built with the real compute_forecast_decision
where practical). No storage import.
"""
from __future__ import annotations

import ast
import dataclasses
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType

import pytest

from analytics.feature_engine.consensus_models import ConsensusFeatureVector
from analytics.forecasting import (
    ForecastDecision, ForecastInputError, ForecastPrediction,
    build_forecast_prediction, compute_forecast_decision, LONG, SHORT, NEUTRAL,
)

B = datetime(2026, 3, 1, 0, 5, 0, tzinfo=timezone.utc)     # UTC, whole minute, 5m-aligned
CV16 = "0123456789abcdef"
CH64 = "a" * 64
REF = 65_000.0
SRC = "binance_close_5m"


def _cv(**over) -> ConsensusFeatureVector:
    """A strongly-bullish 3/3 baseline consensus vector; override any field."""
    base = dict(
        symbol="BTCUSDT", market_type="perp", timeframe="5m", bucket_ts=B,
        feature_schema_version=1, calculation_version=CV16,
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
        config_hash=CH64, config_version="2.1.0", code_version="code-v1")
    base.update(over)
    return ConsensusFeatureVector(**base)


def _bear():
    return _cv(price_move_pct_median=-0.4, taker_buy_notional_usd_sum=200.0,
               taker_sell_notional_usd_sum=800.0, taker_delta_notional_usd_sum=-600.0,
               observed_long_liquidation_notional_sum=900.0,
               observed_short_liquidation_notional_sum=100.0, funding_rate_median=-0.0001)


def _build(cv=None, *, reference_price=REF, reference_price_source=SRC):
    cv = cv if cv is not None else _cv()
    decision = compute_forecast_decision(cv)
    return build_forecast_prediction(
        decision, cv, reference_price=reference_price,
        reference_price_source=reference_price_source)


def _pred_kwargs(cv, decision, **over) -> dict:
    """Full ForecastPrediction kwargs from a decision + consensus vector."""
    base = dict(
        symbol=decision.symbol, market_type=decision.market_type,
        timeframe=decision.timeframe, bucket_ts=decision.bucket_ts,
        feature_schema_version=decision.feature_schema_version,
        calculation_version=decision.calculation_version, rule_version=decision.rule_version,
        direction=decision.direction, confidence=decision.confidence,
        horizon_set=decision.horizon_set, reasons=decision.reasons,
        component_scores=decision.component_scores, final_score=decision.final_score,
        reference_price=REF, reference_price_source=SRC,
        exchanges_expected_max=cv.exchanges_expected_max,
        min_coverage_ratio=cv.min_coverage_ratio,
        data_confidence_overall=cv.data_confidence_overall,
        consensus_confidence=cv.consensus_confidence,
        is_partial_consensus=cv.is_partial_consensus,
        consensus_snapshot=cv, config_hash=decision.config_hash,
        config_version=decision.config_version, code_version=decision.code_version)
    base.update(over)
    return base


# ============================================================================
# A. happy paths
# ============================================================================
def test_long_prediction():
    p = _build()
    assert p.direction == LONG and p.confidence > 0.0


def test_short_prediction():
    p = _build(_bear())
    assert p.direction == SHORT


def test_neutral_prediction_preserved_not_filtered():
    p = _build(_cv(min_coverage_ratio=1.0 / 3.0))            # 1/3 -> NEUTRAL
    assert p.direction == NEUTRAL and p.confidence == 0.0
    assert "INSUFFICIENT_COVERAGE" in p.reasons


def test_decision_fields_and_reference_preserved():
    cv = _cv()
    decision = compute_forecast_decision(cv)
    p = build_forecast_prediction(decision, cv, reference_price=123.5,
                                  reference_price_source="mid")
    assert tuple(p.horizon_set) == tuple(decision.horizon_set)
    assert tuple(p.reasons) == tuple(decision.reasons)
    assert dict(p.component_scores) == dict(decision.component_scores)
    assert p.final_score == decision.final_score
    assert p.reference_price == 123.5 and p.reference_price_source == "mid"


def test_full_consensus_object_retained_and_summary_copied():
    cv = _cv()
    p = _build(cv)
    assert p.consensus_snapshot is cv                        # exact object retained
    assert p.exchanges_expected_max == cv.exchanges_expected_max
    assert p.min_coverage_ratio == cv.min_coverage_ratio
    assert p.data_confidence_overall == cv.data_confidence_overall
    assert p.consensus_confidence == cv.consensus_confidence
    assert p.is_partial_consensus == cv.is_partial_consensus


def test_identity_version_copied_exactly():
    cv = _cv()
    p = _build(cv)
    for f in ("symbol", "market_type", "timeframe", "bucket_ts", "feature_schema_version",
              "calculation_version", "config_hash", "config_version", "code_version"):
        assert getattr(p, f) == getattr(cv, f)
    assert p.rule_version == compute_forecast_decision(cv).rule_version


def test_deterministic_repeated_calls_equal():
    assert _build() == _build()


def test_inputs_not_mutated():
    cv = _cv()
    decision = compute_forecast_decision(cv)
    reasons_snapshot = tuple(decision.reasons)
    _build(cv)
    assert tuple(decision.reasons) == reasons_snapshot
    assert p_unchanged(cv)


def p_unchanged(cv):
    return cv.symbol == "BTCUSDT" and cv.consensus_confidence == 80.0


# ============================================================================
# B. type validation
# ============================================================================
@pytest.mark.parametrize("bad", [None, {"symbol": "BTCUSDT"}, object(), 5])
def test_reject_non_decision(bad):
    with pytest.raises(ForecastInputError):
        build_forecast_prediction(bad, _cv(), reference_price=REF, reference_price_source=SRC)


@pytest.mark.parametrize("bad", [None, {"symbol": "BTCUSDT"}, object(), 5])
def test_reject_non_consensus(bad):
    d = compute_forecast_decision(_cv())
    with pytest.raises(ForecastInputError):
        build_forecast_prediction(d, bad, reference_price=REF, reference_price_source=SRC)


# ============================================================================
# C. reference price validation
# ============================================================================
@pytest.mark.parametrize("bad", [None, True, "65000", float("nan"), float("inf"),
                                 float("-inf"), 0.0, -1.0])
def test_reference_price_rejected(bad):
    with pytest.raises(ForecastInputError):
        _build(reference_price=bad)


@pytest.mark.parametrize("good", [1, 0.01, 65_000, 65_000.5])
def test_reference_price_accepted_without_rounding(good):
    p = _build(reference_price=good)
    assert p.reference_price == good


# ============================================================================
# D. reference source validation
# ============================================================================
@pytest.mark.parametrize("bad", [None, True, b"src", "", "   "])
def test_reference_source_rejected(bad):
    with pytest.raises(ForecastInputError):
        _build(reference_price_source=bad)


# ============================================================================
# E. identity/version mismatch (builder)
# ============================================================================
@pytest.mark.parametrize("field,val", [
    ("symbol", "ETHUSDT"), ("market_type", "spot"), ("timeframe", "1m"),
    ("bucket_ts", B + timedelta(minutes=5)), ("feature_schema_version", 2),
    ("calculation_version", "f" * 16), ("config_hash", "b" * 64),
    ("config_version", "9.9.9"), ("code_version", "other"),
])
def test_builder_identity_mismatch_rejected(field, val):
    cv = _cv()
    decision = compute_forecast_decision(cv)
    cv2 = _cv(**{field: val})                                # snapshot differs on one field
    with pytest.raises(ForecastInputError):
        build_forecast_prediction(decision, cv2, reference_price=REF, reference_price_source=SRC)


# ============================================================================
# F. direct ForecastPrediction construction
# ============================================================================
def test_direct_construction_valid():
    cv = _cv()
    p = ForecastPrediction(**_pred_kwargs(cv, compute_forecast_decision(cv)))
    assert p.direction == LONG


@pytest.mark.parametrize("over", [
    {"direction": "up"}, {"confidence": 1.5}, {"final_score": 2.0},
    {"component_scores": {"price": 0.0}}, {"reasons": ()}, {"symbol": "ETHUSDT"},
    {"calculation_version": "zzz"},
])
def test_direct_malformed_decision_fields_rejected(over):
    cv = _cv()
    with pytest.raises(ForecastInputError):
        ForecastPrediction(**_pred_kwargs(cv, compute_forecast_decision(cv), **over))


@pytest.mark.parametrize("over", [
    {"reference_price": 0.0}, {"reference_price": None}, {"reference_price_source": ""},
    {"exchanges_expected_max": 0}, {"exchanges_expected_max": True},
    {"min_coverage_ratio": 1.5}, {"data_confidence_overall": 150.0},
    {"consensus_confidence": -1.0}, {"is_partial_consensus": 1},
])
def test_direct_malformed_reference_or_summary_rejected(over):
    cv = _cv()
    # keep snapshot consistent for summary fields being tested by overriding both
    snap_over = {k: v for k, v in over.items()
                 if k in ("exchanges_expected_max", "min_coverage_ratio",
                          "data_confidence_overall", "consensus_confidence",
                          "is_partial_consensus")}
    kwargs = _pred_kwargs(cv, compute_forecast_decision(cv), **over)
    with pytest.raises(ForecastInputError):
        ForecastPrediction(**kwargs)


def test_direct_wrong_snapshot_type_rejected():
    cv = _cv()
    kwargs = _pred_kwargs(cv, compute_forecast_decision(cv), consensus_snapshot=object())
    with pytest.raises(ForecastInputError):
        ForecastPrediction(**kwargs)


@pytest.mark.parametrize("field,val", [
    ("calculation_version", "f" * 16), ("config_hash", "b" * 64),
    ("config_version", "9.9.9"), ("code_version", "other"),
    ("feature_schema_version", 2),
])
def test_direct_duplicated_identity_inconsistent_with_snapshot(field, val):
    cv = _cv()
    decision = compute_forecast_decision(cv)
    # prediction claims a different identity than its stored snapshot
    kwargs = _pred_kwargs(cv, decision, **{field: val})
    with pytest.raises(ForecastInputError):
        ForecastPrediction(**kwargs)


@pytest.mark.parametrize("field,val", [
    ("exchanges_expected_max", 2), ("min_coverage_ratio", 0.5),
    ("data_confidence_overall", 55.0), ("consensus_confidence", 55.0),
    ("is_partial_consensus", True),
])
def test_direct_duplicated_summary_inconsistent_with_snapshot(field, val):
    cv = _cv()
    decision = compute_forecast_decision(cv)
    kwargs = _pred_kwargs(cv, decision, **{field: val})     # summary differs from snapshot
    with pytest.raises(ForecastInputError):
        ForecastPrediction(**kwargs)


# ============================================================================
# G. deep immutability
# ============================================================================
def test_immutability_and_detachment():
    cv = _cv()
    decision = compute_forecast_decision(cv)
    reasons = list(decision.reasons)
    scores = dict(decision.component_scores)
    horizons = list(decision.horizon_set)
    p = ForecastPrediction(**_pred_kwargs(
        cv, decision, reasons=reasons, component_scores=scores, horizon_set=horizons))
    reasons.append("x")
    scores["price"] = 0.999
    horizons.append("mut")
    assert isinstance(p.horizon_set, tuple) and "mut" not in p.horizon_set
    assert isinstance(p.reasons, tuple) and "x" not in p.reasons
    assert p.component_scores["price"] != 0.999
    with pytest.raises(TypeError):
        p.component_scores["price"] = 1.0
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.direction = "SHORT"
    # snapshot stays immutable
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.consensus_snapshot.symbol = "ETHUSDT"


# ============================================================================
# H. architecture / purity
# ============================================================================
_ALLOWED_MODULES = {"__future__", "math", "dataclasses", "datetime", "types",
                    "typing", "analytics"}
_FORBIDDEN_MODULES = {
    "storage", "asyncpg", "asyncio", "socket", "redis", "aiohttp", "requests",
    "websocket", "websockets", "os", "dotenv", "subprocess", "pathlib", "logging",
    "main", "data_ingestion", "backfill", "telegram", "time", "numpy", "pandas",
    "sklearn", "torch", "tensorflow",
}


def test_architecture_pure_boundary():
    src = Path("analytics/forecasting/persistence.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported = set()
    used_attrs = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])
        elif isinstance(node, ast.Attribute):
            used_attrs.add(node.attr)
        # no async functions in a pure builder
        assert not isinstance(node, (ast.AsyncFunctionDef, ast.Await))
    assert not (imported & _FORBIDDEN_MODULES), imported & _FORBIDDEN_MODULES
    assert imported <= _ALLOWED_MODULES, imported - _ALLOWED_MODULES
    assert not (used_attrs & {"now", "utcnow", "today", "environ", "getenv"})
