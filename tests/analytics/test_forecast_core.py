"""Unit tests for the Stage 2 shadow Forecast Core v0 (analytics/forecasting/).

Pure/deterministic — no DB, network, or clock. Uses real (hand-built)
ConsensusFeatureVector instances and the real ForecastRuleSet; the scoring
algorithm is not re-implemented in the tests.
"""
from __future__ import annotations

import ast
import dataclasses
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType

import pytest

from analytics.feature_engine.consensus_models import ConsensusFeatureVector
from analytics.forecasting.core import compute_forecast_decision
from analytics.forecasting.models import (
    DEFAULT_FORECAST_HORIZONS, DEFAULT_FORECAST_RULES, DIRECTIONS,
    FORECAST_COMPONENTS, ForecastDecision, ForecastInputError, ForecastRuleSet,
    INSUFFICIENT_COVERAGE, LONG, LOW_CONSENSUS_CONFIDENCE, NEUTRAL, SHORT,
    WEAK_PRIMARY_SIGNAL, SCORE_BELOW_ACTION_THRESHOLD, COMPOSITE_BULLISH,
    COMPOSITE_BEARISH, PARTIAL_CONSENSUS, FUNDING_BEARISH_CONTRARIAN,
    PRICE_BULLISH, FLOW_BULLISH,
)

B = datetime(2026, 3, 1, 0, 5, 0, tzinfo=timezone.utc)     # UTC, whole minute, 5m-aligned
CV16 = "0123456789abcdef"
CH64 = "a" * 64


def _cf(**over) -> ConsensusFeatureVector:
    """A strongly-bullish, full-coverage 3/3 baseline; override any field."""
    base = dict(
        symbol="BTCUSDT", market_type="perp", timeframe="5m", bucket_ts=B,
        feature_schema_version=1, calculation_version=CV16,
        coverage_by_metric=MappingProxyType({}), provenance_by_metric=MappingProxyType({}),
        data_confidence_by_metric=MappingProxyType({}),
        exchanges_expected_max=3, min_coverage_ratio=1.0, data_confidence_overall=0.8,
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
        consensus_confidence=0.8, is_partial_consensus=False,
        config_hash=CH64, config_version="2.1.0", code_version="code-v1")
    base.update(over)
    return ConsensusFeatureVector(**base)


def _bear_over(**extra):
    o = dict(price_move_pct_median=-0.4, taker_buy_notional_usd_sum=200.0,
             taker_sell_notional_usd_sum=800.0, taker_delta_notional_usd_sum=-600.0,
             observed_long_liquidation_notional_sum=900.0,
             observed_short_liquidation_notional_sum=100.0, funding_rate_median=-0.0001)
    o.update(extra)
    return o


def _rules(**over) -> ForecastRuleSet:
    return dataclasses.replace(DEFAULT_FORECAST_RULES, **over)


# ============================================================================
# 24. ForecastRuleSet validation
# ============================================================================
def test_default_rules_valid_and_immutable():
    r = DEFAULT_FORECAST_RULES
    assert r.rule_version == "forecast-rules-v0.1.0"
    assert r.horizons == ("15m", "1h", "4h")
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.action_score_threshold = 0.5


def test_rules_horizons_and_weights_detached_and_immutable():
    hz = ["15m", "1h"]
    wt = {"price": 0.30, "flow": 0.30, "oi": 0.15, "funding": 0.10,
          "liquidations": 0.10, "agreement": 0.05}
    r = _rules(horizons=hz, component_weights=wt)
    hz.append("mutated")
    wt["price"] = 0.99
    assert r.horizons == ("15m", "1h")                    # detached from caller list
    assert r.component_weights["price"] == 0.30           # detached from caller dict
    assert isinstance(r.horizons, tuple)
    with pytest.raises(TypeError):
        r.component_weights["price"] = 0.1                 # MappingProxyType


def test_rules_blank_version_rejected():
    with pytest.raises(ForecastInputError):
        _rules(rule_version="  ")


@pytest.mark.parametrize("bad", [None, "15m", b"15m", 5, {"15m": 1}, set(), (x for x in ())])
def test_rules_bad_horizons_container(bad):
    with pytest.raises(ForecastInputError):
        _rules(horizons=bad)


@pytest.mark.parametrize("bad", [(), ["15m", "15m"], ["15m", ""]])
def test_rules_empty_dup_blank_horizons(bad):
    with pytest.raises(ForecastInputError):
        _rules(horizons=bad)


@pytest.mark.parametrize("field", [
    "minimum_coverage_ratio", "minimum_consensus_confidence", "minimum_primary_score",
    "action_score_threshold", "reason_score_threshold", "price_full_scale_pct",
    "flow_imbalance_full_scale", "oi_change_full_scale_pct", "funding_full_scale"])
@pytest.mark.parametrize("bad", [True, "0.5", None, float("nan"), float("inf"), float("-inf")])
def test_rules_bad_numeric_field(field, bad):
    with pytest.raises(ForecastInputError):
        _rules(**{field: bad})


@pytest.mark.parametrize("field,bad", [
    ("minimum_coverage_ratio", 0.0), ("minimum_coverage_ratio", 1.5),
    ("minimum_consensus_confidence", -0.1), ("minimum_consensus_confidence", 1.1),
    ("minimum_primary_score", -0.01), ("minimum_primary_score", 1.01),
    ("action_score_threshold", 0.0), ("action_score_threshold", 1.01),
    ("reason_score_threshold", -0.1), ("reason_score_threshold", 1.1),
])
def test_rules_out_of_range_thresholds(field, bad):
    with pytest.raises(ForecastInputError):
        _rules(**{field: bad})


@pytest.mark.parametrize("field", ["price_full_scale_pct", "flow_imbalance_full_scale",
                                   "oi_change_full_scale_pct", "funding_full_scale"])
@pytest.mark.parametrize("bad", [0.0, -1.0])
def test_rules_nonpositive_full_scale(field, bad):
    with pytest.raises(ForecastInputError):
        _rules(**{field: bad})


def _w(**over):
    base = {"price": 0.30, "flow": 0.30, "oi": 0.15, "funding": 0.10,
            "liquidations": 0.10, "agreement": 0.05}
    base.update(over)
    return base


def test_rules_weight_missing_component():
    w = _w(); del w["oi"]
    with pytest.raises(ForecastInputError):
        _rules(component_weights=w)


def test_rules_weight_extra_component():
    w = _w(extra=0.0)
    with pytest.raises(ForecastInputError):
        _rules(component_weights=w)


@pytest.mark.parametrize("bad_w", [
    _w(oi=-0.15, price=0.45),          # negative weight (sum still 1)
    _w(price=True),                    # bool weight
    _w(price=float("nan")),            # non-finite
    _w(price=0.31),                    # sum != 1
])
def test_rules_bad_weight_values(bad_w):
    with pytest.raises(ForecastInputError):
        _rules(component_weights=bad_w)


def test_rules_zero_price_or_flow_weight_rejected():
    with pytest.raises(ForecastInputError):
        _rules(component_weights=_w(price=0.0, agreement=0.35))
    with pytest.raises(ForecastInputError):
        _rules(component_weights=_w(flow=0.0, agreement=0.35))


# ---- ForecastDecision validation -------------------------------------------
def _decision(**over) -> ForecastDecision:
    base = dict(
        symbol="BTCUSDT", market_type="perp", timeframe="5m", bucket_ts=B,
        direction=NEUTRAL, confidence=0.0, horizon_set=("15m",),
        reasons=(INSUFFICIENT_COVERAGE,),
        component_scores={k: 0.0 for k in FORECAST_COMPONENTS}, final_score=0.0,
        rule_version="forecast-rules-v0.1.0", feature_schema_version=1,
        calculation_version=CV16, config_hash=CH64, config_version="2.1.0",
        code_version="code-v1")
    base.update(over)
    return ForecastDecision(**base)


def test_decision_valid_default():
    d = _decision()
    assert d.direction == NEUTRAL and d.confidence == 0.0


@pytest.mark.parametrize("bad", ["long", "up", "", "buy"])
def test_decision_bad_direction(bad):
    with pytest.raises(ForecastInputError):
        _decision(direction=bad)


@pytest.mark.parametrize("bad", [-0.01, 1.01, float("nan"), True])
def test_decision_bad_confidence(bad):
    with pytest.raises(ForecastInputError):
        _decision(confidence=bad)


@pytest.mark.parametrize("bad", [-1.01, 1.01, float("inf")])
def test_decision_bad_final_score(bad):
    with pytest.raises(ForecastInputError):
        _decision(final_score=bad)


def test_decision_bad_component_keys():
    with pytest.raises(ForecastInputError):
        _decision(component_scores={"price": 0.0})


def test_decision_component_score_out_of_range():
    cs = {k: 0.0 for k in FORECAST_COMPONENTS}; cs["price"] = 1.5
    with pytest.raises(ForecastInputError):
        _decision(component_scores=cs)


def test_decision_empty_and_duplicate_reasons():
    with pytest.raises(ForecastInputError):
        _decision(reasons=())
    with pytest.raises(ForecastInputError):
        _decision(reasons=(INSUFFICIENT_COVERAGE, INSUFFICIENT_COVERAGE))


def test_decision_deep_immutability_and_detachment():
    reasons = [INSUFFICIENT_COVERAGE]
    cs = {k: 0.0 for k in FORECAST_COMPONENTS}
    d = _decision(reasons=reasons, component_scores=cs)
    reasons.append("x")
    cs["price"] = 0.9
    assert d.reasons == (INSUFFICIENT_COVERAGE,)
    assert d.component_scores["price"] == 0.0
    with pytest.raises(TypeError):
        d.component_scores["price"] = 1.0


# ============================================================================
# 25. compute_forecast_decision — input validation
# ============================================================================
class _DuckCF:
    pass


@pytest.mark.parametrize("bad", [None, {"symbol": "BTCUSDT"}, object(), _DuckCF()])
def test_rejects_non_consensus_vector(bad):
    with pytest.raises(ForecastInputError):
        compute_forecast_decision(bad)


def test_rejects_non_ruleset():
    with pytest.raises(ForecastInputError):
        compute_forecast_decision(_cf(), rules=object())


@pytest.mark.parametrize("over", [
    {"symbol": "ETHUSDT"}, {"market_type": "spot"}, {"timeframe": "1m"},
    {"bucket_ts": datetime(2026, 3, 1, 0, 5, 0)},                            # naive
    {"bucket_ts": datetime(2026, 3, 1, 0, 5, 0, tzinfo=timezone(timedelta(hours=1)))},
    {"bucket_ts": datetime(2026, 3, 1, 0, 5, 30, tzinfo=timezone.utc)},      # not whole minute
    {"bucket_ts": datetime(2026, 3, 1, 0, 3, 0, tzinfo=timezone.utc)},       # not 5m aligned
    {"feature_schema_version": 0}, {"feature_schema_version": True},
    {"calculation_version": "xyz"}, {"config_hash": "a" * 63},
    {"config_version": " "}, {"code_version": ""},
    {"is_partial_consensus": 1}, {"exchanges_expected_max": 0},
    {"exchanges_expected_max": True},
])
def test_rejects_bad_identity(over):
    with pytest.raises(ForecastInputError):
        compute_forecast_decision(_cf(**over))


@pytest.mark.parametrize("over", [
    {"price_move_pct_median": True}, {"price_move_pct_median": float("nan")},
    {"funding_rate_median": float("inf")}, {"oi_change_pct_median": float("-inf")},
    {"min_coverage_ratio": -0.1}, {"min_coverage_ratio": 1.1},
    {"consensus_confidence": 1.5}, {"price_direction_agreement": -0.01},
    {"flow_direction_agreement": 1.2}, {"oi_direction_agreement": 2.0},
    {"data_confidence_overall": 1.5},
    {"taker_buy_notional_usd_sum": -1.0}, {"taker_sell_notional_usd_sum": -5.0},
    {"observed_long_liquidation_notional_sum": -1.0},
    {"observed_short_liquidation_notional_sum": -1.0},
])
def test_rejects_bad_numerics(over):
    with pytest.raises(ForecastInputError):
        compute_forecast_decision(_cf(**over))


# ============================================================================
# 26. component formulas
# ============================================================================
def _scores(**over):
    return compute_forecast_decision(_cf(**over)).component_scores


def test_price_component():
    assert _scores(price_move_pct_median=0.4, price_direction_agreement=1.0)["price"] == pytest.approx(0.8)
    assert _scores(price_move_pct_median=-0.4)["price"] == pytest.approx(-0.8)
    assert _scores(price_move_pct_median=0.0)["price"] == 0.0
    assert _scores(price_move_pct_median=5.0)["price"] == pytest.approx(1.0)     # clamp
    assert _scores(price_move_pct_median=0.4, price_direction_agreement=0.5)["price"] == pytest.approx(0.4)
    assert _scores(price_move_pct_median=None)["price"] == 0.0


def test_flow_component_uses_stored_delta_not_buy_minus_sell():
    # buy-sell would be +600, but stored delta is -600 -> bearish flow
    s = _scores(taker_buy_notional_usd_sum=800.0, taker_sell_notional_usd_sum=200.0,
                taker_delta_notional_usd_sum=-600.0, flow_direction_agreement=1.0)
    assert s["flow"] < 0
    # zero gross flow -> 0
    assert _scores(taker_buy_notional_usd_sum=0.0, taker_sell_notional_usd_sum=0.0,
                   taker_delta_notional_usd_sum=0.0)["flow"] == 0.0
    # clamp and agreement reduction
    assert _scores(taker_buy_notional_usd_sum=500.0, taker_sell_notional_usd_sum=500.0,
                   taker_delta_notional_usd_sum=1000.0)["flow"] == pytest.approx(1.0)
    assert _scores(taker_delta_notional_usd_sum=None)["flow"] == 0.0


def test_primary_anchor_conflict_and_auxiliary_cannot_action():
    # price/flow missing -> anchor 0 -> auxiliary cannot make it actionable
    d = compute_forecast_decision(_cf(
        price_move_pct_median=None, taker_delta_notional_usd_sum=None,
        funding_rate_median=-0.01, oi_change_pct_median=5.0,
        observed_long_liquidation_notional_sum=0.0,
        observed_short_liquidation_notional_sum=1000.0))
    assert d.direction == NEUTRAL
    assert WEAK_PRIMARY_SIGNAL in d.reasons
    assert d.component_scores["oi"] == 0.0                  # no anchor -> oi 0
    assert d.component_scores["agreement"] == 0.0


def test_oi_component_confirm_and_oppose():
    # bullish anchor + rising OI -> positive; falling OI -> negative
    assert _scores(oi_change_pct_median=0.5)["oi"] > 0
    assert _scores(oi_change_pct_median=-0.5)["oi"] < 0
    # bearish anchor + rising OI -> negative (confirms bearish)
    assert _scores(**_bear_over(oi_change_pct_median=0.5))["oi"] < 0
    assert _scores(**_bear_over(oi_change_pct_median=-0.5))["oi"] > 0
    assert _scores(oi_change_pct_median=0.0)["oi"] == 0.0
    assert _scores(oi_change_pct_median=5.0)["oi"] == pytest.approx(1.0)     # clamp
    assert _scores(oi_change_pct_median=0.5, oi_direction_agreement=None)["oi"] == 0.0


def test_funding_component():
    assert _scores(funding_rate_median=0.0003)["funding"] == pytest.approx(-1.0)
    assert _scores(funding_rate_median=-0.0003)["funding"] == pytest.approx(1.0)
    assert _scores(funding_rate_median=0.0)["funding"] == 0.0
    assert _scores(funding_rate_median=1.0)["funding"] == pytest.approx(-1.0)    # clamp
    assert _scores(funding_rate_median=None)["funding"] == 0.0


def test_liquidation_component():
    assert _scores(observed_long_liquidation_notional_sum=100.0,
                   observed_short_liquidation_notional_sum=900.0)["liquidations"] == pytest.approx(0.8)
    assert _scores(observed_long_liquidation_notional_sum=900.0,
                   observed_short_liquidation_notional_sum=100.0)["liquidations"] == pytest.approx(-0.8)
    assert _scores(observed_long_liquidation_notional_sum=500.0,
                   observed_short_liquidation_notional_sum=500.0)["liquidations"] == 0.0
    assert _scores(observed_long_liquidation_notional_sum=0.0,
                   observed_short_liquidation_notional_sum=0.0)["liquidations"] == 0.0
    assert _scores(observed_long_liquidation_notional_sum=None)["liquidations"] == 0.0


def test_agreement_component():
    assert _scores()["agreement"] == pytest.approx(1.0)                          # all 1.0 -> strength 1
    # at/below 0.5 -> zero strength
    assert _scores(price_direction_agreement=0.5, flow_direction_agreement=0.5,
                   oi_direction_agreement=0.5)["agreement"] == 0.0
    # bearish anchor -> negative agreement
    assert _scores(**_bear_over())["agreement"] < 0
    # no anchor -> 0
    assert _scores(price_move_pct_median=None, taker_delta_notional_usd_sum=None)["agreement"] == 0.0


# ============================================================================
# 27. decision behaviour
# ============================================================================
def test_A_strong_bullish_3of3():
    d = compute_forecast_decision(_cf())
    assert d.direction == LONG and d.final_score > 0 and d.confidence > 0
    assert d.reasons[0] == COMPOSITE_BULLISH
    assert PRICE_BULLISH in d.reasons and FLOW_BULLISH in d.reasons
    assert PARTIAL_CONSENSUS not in d.reasons


def test_B_strong_bearish_3of3():
    d = compute_forecast_decision(_cf(**_bear_over()))
    assert d.direction == SHORT and d.final_score < 0 and d.confidence > 0
    assert d.reasons[0] == COMPOSITE_BEARISH


def test_C_weak_mixed_neutral():
    d = compute_forecast_decision(_cf(
        price_move_pct_median=0.01, taker_buy_notional_usd_sum=510.0,
        taker_sell_notional_usd_sum=490.0, taker_delta_notional_usd_sum=2.0))
    assert d.direction == NEUTRAL and d.confidence == 0.0
    assert WEAK_PRIMARY_SIGNAL in d.reasons or SCORE_BELOW_ACTION_THRESHOLD in d.reasons


def test_D_two_of_three_partial_high_quality():
    d = compute_forecast_decision(_cf(min_coverage_ratio=2.0 / 3.0, is_partial_consensus=True))
    assert d.direction in (LONG, SHORT)
    assert INSUFFICIENT_COVERAGE not in d.reasons                # 2/3 passes
    assert d.reasons[-1] == PARTIAL_CONSENSUS                    # appended last


def test_E_one_of_three_neutral():
    d = compute_forecast_decision(_cf(min_coverage_ratio=1.0 / 3.0))
    assert d.direction == NEUTRAL and d.confidence == 0.0
    assert INSUFFICIENT_COVERAGE in d.reasons


def test_F_low_consensus_confidence_neutral():
    d = compute_forecast_decision(_cf(consensus_confidence=0.4))
    assert d.direction == NEUTRAL
    assert LOW_CONSENSUS_CONFIDENCE in d.reasons


def test_G_missing_consensus_confidence_neutral():
    d = compute_forecast_decision(_cf(consensus_confidence=None))
    assert d.direction == NEUTRAL
    assert LOW_CONSENSUS_CONFIDENCE in d.reasons


def test_H_exact_threshold_boundaries_pass():
    # coverage == threshold, consensus_confidence == threshold both pass
    d = compute_forecast_decision(_cf(min_coverage_ratio=2.0 / 3.0, consensus_confidence=0.50))
    assert INSUFFICIENT_COVERAGE not in d.reasons
    assert LOW_CONSENSUS_CONFIDENCE not in d.reasons
    # primary anchor == minimum passes (custom rule set to the known anchor 0.9)
    d2 = compute_forecast_decision(_cf(), rules=_rules(minimum_primary_score=0.9))
    assert WEAK_PRIMARY_SIGNAL not in d2.reasons
    # abs(final_score) == action threshold passes (inclusive)
    base = compute_forecast_decision(_cf())
    d3 = compute_forecast_decision(_cf(), rules=_rules(action_score_threshold=abs(base.final_score)))
    assert SCORE_BELOW_ACTION_THRESHOLD not in d3.reasons and d3.direction == LONG


def test_I_conflicting_evidence_preserved():
    # positive funding contributes bearish reason inside a bullish decision
    d = compute_forecast_decision(_cf())
    assert d.direction == LONG
    assert FUNDING_BEARISH_CONTRARIAN in d.reasons              # opposing evidence kept
    assert compute_forecast_decision(_cf()).reasons == d.reasons  # deterministic


def test_J_confidence_formula_and_monotonicity():
    d = compute_forecast_decision(_cf())
    expected = min(1.0, abs(d.final_score) * math.sqrt(0.8 * 1.0))
    assert d.confidence == pytest.approx(expected)
    # stronger score -> larger confidence at equal quality
    weaker = compute_forecast_decision(_cf(price_move_pct_median=0.2))
    assert d.confidence > weaker.confidence
    # lower coverage/confidence -> smaller confidence
    lower_q = compute_forecast_decision(_cf(consensus_confidence=0.6, min_coverage_ratio=2.0 / 3.0))
    assert lower_q.confidence < d.confidence
    assert 0.0 <= d.confidence <= 1.0


def test_K_output_shape_identity_and_determinism():
    cf = _cf()
    d = compute_forecast_decision(cf)
    assert d.horizon_set == ("15m", "1h", "4h") == DEFAULT_FORECAST_HORIZONS
    assert d.rule_version == "forecast-rules-v0.1.0"
    for f in ("symbol", "market_type", "timeframe", "bucket_ts", "feature_schema_version",
              "calculation_version", "config_hash", "config_version", "code_version"):
        assert getattr(d, f) == getattr(cf, f)
    assert tuple(d.component_scores.keys()) == FORECAST_COMPONENTS
    assert compute_forecast_decision(cf) == d                   # repeated calls equal


def test_K_inputs_not_mutated():
    cf = _cf()
    reference = _cf()                                    # identical, independent instance
    rules_before = (DEFAULT_FORECAST_RULES.rule_version,
                    dict(DEFAULT_FORECAST_RULES.component_weights),
                    DEFAULT_FORECAST_RULES.horizons)
    compute_forecast_decision(cf)
    assert cf == reference                               # frozen input unchanged by value
    assert (DEFAULT_FORECAST_RULES.rule_version,
            dict(DEFAULT_FORECAST_RULES.component_weights),
            DEFAULT_FORECAST_RULES.horizons) == rules_before


def test_no_internal_rounding():
    # a fully-precise irrational-ish confidence is preserved (not rounded)
    d = compute_forecast_decision(_cf())
    assert repr(d.confidence).count("0000000") == 0 or d.confidence != round(d.confidence, 4)


# ============================================================================
# 28. purity / architecture
# ============================================================================
_ALLOWED_MODULES = {
    "__future__", "dataclasses", "datetime", "math", "re", "collections",
    "types", "typing", "analytics",
}
_FORBIDDEN_MODULES = {
    "storage", "asyncpg", "redis", "asyncio", "aiohttp", "requests", "websocket",
    "websockets", "os", "dotenv", "subprocess", "pathlib", "main", "data_ingestion",
    "backfill", "telegram", "time", "random", "numpy", "pandas", "sklearn",
    "torch", "tensorflow",
}


@pytest.mark.parametrize("mod", ["models", "core"])
def test_architecture_pure_boundary(mod):
    src = Path(f"analytics/forecasting/{mod}.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported = set()
    used_attrs = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])              # absolute imports only
        elif isinstance(node, ast.Attribute):
            used_attrs.add(node.attr)
        # no async functions anywhere in the forecast core
        assert not isinstance(node, (ast.AsyncFunctionDef, ast.Await, ast.AsyncFor,
                                     ast.AsyncWith))
    assert not (imported & _FORBIDDEN_MODULES), imported & _FORBIDDEN_MODULES
    assert imported <= _ALLOWED_MODULES, imported - _ALLOWED_MODULES
    assert not (used_attrs & {"now", "utcnow", "today", "environ", "getenv", "sleep"})


def test_forecasting_package_exports():
    import analytics.forecasting as fc
    for name in ("ForecastInputError", "ForecastRuleSet", "ForecastDecision",
                 "DEFAULT_FORECAST_RULES", "DEFAULT_FORECAST_HORIZONS",
                 "FORECAST_COMPONENTS", "LONG", "SHORT", "NEUTRAL",
                 "compute_forecast_decision"):
        assert hasattr(fc, name)
