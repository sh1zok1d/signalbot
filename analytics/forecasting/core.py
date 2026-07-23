"""
Stage 2 shadow Forecast Core v0 — a pure, deterministic heuristic.

`compute_forecast_decision(consensus_feature, rules) -> ForecastDecision` turns one
`ConsensusFeatureVector` into an explainable LONG / SHORT / NEUTRAL decision with
weighted component scores, actionability gates, an uncalibrated action-strength
confidence, and stable reason codes.

Scope is the CURRENT shadow scope only: BTCUSDT / perp / 5m. Any other identity
fails with `ForecastInputError`. No DB, network, asyncio, clock, env, filesystem,
config file, randomness, or ML — same consensus vector + same rule set always
produce an equal decision. Nothing is rounded internally.

A real healthy `ConsensusFeatureVector` from the merged consensus core is accepted
directly: `consensus_confidence` / `data_confidence_overall` are read on their
upstream 0–100 scale, `min_coverage_ratio` and the direction agreements on 0–1. No
copied or renormalized vector is required.

`confidence` is an uncalibrated deterministic action-strength score in [0, 1], NOT
a probability of profit.
"""
from __future__ import annotations

import math

from analytics.feature_engine.consensus_models import ConsensusFeatureVector

from .models import (
    AGREEMENT_BEARISH, AGREEMENT_BULLISH, COMPOSITE_BEARISH, COMPOSITE_BULLISH,
    DEFAULT_FORECAST_RULES, DIRECTIONS, FLOW_BEARISH, FLOW_BULLISH,
    FORECAST_COMPONENTS, ForecastDecision, ForecastInputError, ForecastRuleSet,
    FUNDING_BEARISH_CONTRARIAN, FUNDING_BULLISH_CONTRARIAN, INSUFFICIENT_COVERAGE,
    LIQUIDATIONS_BEARISH, LIQUIDATIONS_BULLISH, LONG, LOW_CONSENSUS_CONFIDENCE,
    NEUTRAL, OI_BEARISH_CONTRIBUTION, OI_BULLISH_CONTRIBUTION, PARTIAL_CONSENSUS,
    PRICE_BEARISH, PRICE_BULLISH, SCORE_BELOW_ACTION_THRESHOLD, SHORT,
    WEAK_PRIMARY_SIGNAL, _finite_number, _in_range, _validate_scope_identity,
)


# ---- pure score helpers ----------------------------------------------------
def _clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return low if value < low else high if value > high else value


def _sign(value: float) -> float:
    if value > 0:
        return 1.0
    if value < 0:
        return -1.0
    return 0.0


# ---- input validation ------------------------------------------------------
def _num_or_none(value, name: str):
    """Finite float or None (bool rejected)."""
    return None if value is None else _finite_number(value, name)


def _ratio_or_none(value, name: str):
    """Finite value in [0, 1], or None (a true 0–1 ratio)."""
    if value is None:
        return None
    return _in_range(_finite_number(value, name), name, 0.0, 1.0)


def _percent_or_none(value, name: str):
    """Finite value on the upstream consensus 0–100 confidence scale, or None.
    Deliberately distinct from `_ratio_or_none` so a 0–100 confidence is never
    mislabeled a 0–1 ratio."""
    if value is None:
        return None
    return _in_range(_finite_number(value, name), name, 0.0, 100.0)


def _nonneg_or_none(value, name: str):
    if value is None:
        return None
    v = _finite_number(value, name)
    if v < 0:
        raise ForecastInputError(f"{name} must be >= 0, got {v!r}")
    return v


def _validate_identity(cf: ConsensusFeatureVector) -> None:
    # shared BTCUSDT/perp/5m identity + version rules
    _validate_scope_identity(
        cf.symbol, cf.market_type, cf.timeframe, cf.bucket_ts,
        cf.feature_schema_version, cf.calculation_version,
        cf.config_hash, cf.config_version, cf.code_version)
    if not isinstance(cf.is_partial_consensus, bool):
        raise ForecastInputError("is_partial_consensus must be a bool")
    if not isinstance(cf.exchanges_expected_max, int) or isinstance(cf.exchanges_expected_max, bool) \
            or cf.exchanges_expected_max < 1:
        raise ForecastInputError("exchanges_expected_max must be an int >= 1")


def _validate_numerics(cf: ConsensusFeatureVector) -> dict:
    """Validate + collect the numeric fields the core reads, each on its REAL
    upstream scale: `consensus_confidence`/`data_confidence_overall` in [0, 100];
    `min_coverage_ratio` and the direction agreements in [0, 1]; the notional sums
    used in ratios >= 0; the rest finite (any sign). None stays None (handled per
    component / per gate)."""
    return {
        "min_coverage_ratio": _ratio_or_none(cf.min_coverage_ratio, "min_coverage_ratio"),
        "data_confidence_overall": _percent_or_none(cf.data_confidence_overall, "data_confidence_overall"),
        "consensus_confidence": _percent_or_none(cf.consensus_confidence, "consensus_confidence"),
        "price_direction_agreement": _ratio_or_none(cf.price_direction_agreement, "price_direction_agreement"),
        "flow_direction_agreement": _ratio_or_none(cf.flow_direction_agreement, "flow_direction_agreement"),
        "oi_direction_agreement": _ratio_or_none(cf.oi_direction_agreement, "oi_direction_agreement"),
        "price_move_pct_median": _num_or_none(cf.price_move_pct_median, "price_move_pct_median"),
        "oi_change_pct_median": _num_or_none(cf.oi_change_pct_median, "oi_change_pct_median"),
        "funding_rate_median": _num_or_none(cf.funding_rate_median, "funding_rate_median"),
        "taker_buy_notional_usd_sum": _nonneg_or_none(cf.taker_buy_notional_usd_sum, "taker_buy_notional_usd_sum"),
        "taker_sell_notional_usd_sum": _nonneg_or_none(cf.taker_sell_notional_usd_sum, "taker_sell_notional_usd_sum"),
        "taker_delta_notional_usd_sum": _num_or_none(cf.taker_delta_notional_usd_sum, "taker_delta_notional_usd_sum"),
        "observed_long_liquidation_notional_sum": _nonneg_or_none(
            cf.observed_long_liquidation_notional_sum, "observed_long_liquidation_notional_sum"),
        "observed_short_liquidation_notional_sum": _nonneg_or_none(
            cf.observed_short_liquidation_notional_sum, "observed_short_liquidation_notional_sum"),
    }


# ---- component scores -------------------------------------------------------
def _price_score(v: dict, rules: ForecastRuleSet) -> float:
    pm = v["price_move_pct_median"]
    pa = v["price_direction_agreement"]
    if pm is None or pa is None:
        return 0.0
    strength = _clamp(pm / rules.price_full_scale_pct)
    return _clamp(strength * pa)


def _flow_score(v: dict, rules: ForecastRuleSet) -> float:
    buy = v["taker_buy_notional_usd_sum"]
    sell = v["taker_sell_notional_usd_sum"]
    delta = v["taker_delta_notional_usd_sum"]
    fa = v["flow_direction_agreement"]
    if buy is None or sell is None or delta is None or fa is None:
        return 0.0
    gross = buy + sell
    if gross == 0:
        return 0.0
    imbalance = delta / gross
    strength = _clamp(imbalance / rules.flow_imbalance_full_scale)
    return _clamp(strength * fa)


def _oi_score(v: dict, rules: ForecastRuleSet, anchor_sign: float) -> float:
    oi = v["oi_change_pct_median"]
    oa = v["oi_direction_agreement"]
    if oi is None or oa is None or anchor_sign == 0.0:
        return 0.0
    if oi == 0:
        return 0.0
    strength = _clamp(abs(oi) / rules.oi_change_full_scale_pct, 0.0, 1.0) * oa
    # rising OI (>0) confirms the anchor; falling OI (<0) opposes it.
    return _clamp((anchor_sign if oi > 0 else -anchor_sign) * strength)


def _funding_score(v: dict, rules: ForecastRuleSet) -> float:
    fr = v["funding_rate_median"]
    if fr is None:
        return 0.0
    return _clamp(-fr / rules.funding_full_scale)


def _liquidation_score(v: dict) -> float:
    long_sum = v["observed_long_liquidation_notional_sum"]
    short_sum = v["observed_short_liquidation_notional_sum"]
    if long_sum is None or short_sum is None:
        return 0.0
    gross = long_sum + short_sum
    if gross == 0:
        return 0.0
    return _clamp((short_sum - long_sum) / gross)


def _agreement_score(v: dict, anchor_sign: float) -> float:
    values = [x for x in (v["price_direction_agreement"], v["flow_direction_agreement"],
                          v["oi_direction_agreement"]) if x is not None]
    if not values or anchor_sign == 0.0:
        return 0.0
    mean_agreement = math.fsum(values) / len(values)
    strength = _clamp((mean_agreement - 0.50) / 0.50, 0.0, 1.0)
    return _clamp(anchor_sign * strength)


# ---- reason building --------------------------------------------------------
_REASON_BY_COMPONENT = {
    "price": (PRICE_BULLISH, PRICE_BEARISH),
    "flow": (FLOW_BULLISH, FLOW_BEARISH),
    "oi": (OI_BULLISH_CONTRIBUTION, OI_BEARISH_CONTRIBUTION),
    "funding": (FUNDING_BULLISH_CONTRARIAN, FUNDING_BEARISH_CONTRARIAN),
    "liquidations": (LIQUIDATIONS_BULLISH, LIQUIDATIONS_BEARISH),
    "agreement": (AGREEMENT_BULLISH, AGREEMENT_BEARISH),
}


def _actionable_reasons(direction: str, component_scores: dict, rules: ForecastRuleSet,
                        is_partial: bool) -> tuple:
    reasons = [COMPOSITE_BULLISH if direction == LONG else COMPOSITE_BEARISH]
    for name in FORECAST_COMPONENTS:
        score = component_scores[name]
        # A zero component is neither bullish nor bearish: it emits no reason even
        # when reason_score_threshold == 0.0. Opposing (non-zero) evidence is
        # preserved (never filtered to match the final direction).
        if score != 0.0 and abs(score) >= rules.reason_score_threshold:
            bull, bear = _REASON_BY_COMPONENT[name]
            reasons.append(bull if score > 0 else bear)
    if is_partial:
        reasons.append(PARTIAL_CONSENSUS)
    return tuple(reasons)


# ---- entry point -----------------------------------------------------------
def compute_forecast_decision(
    consensus_feature: ConsensusFeatureVector,
    rules: ForecastRuleSet = DEFAULT_FORECAST_RULES,
) -> ForecastDecision:
    if not isinstance(consensus_feature, ConsensusFeatureVector):
        raise ForecastInputError(
            f"consensus_feature must be a ConsensusFeatureVector, "
            f"got {type(consensus_feature).__name__}")
    if not isinstance(rules, ForecastRuleSet):
        raise ForecastInputError(f"rules must be a ForecastRuleSet, got {type(rules).__name__}")

    _validate_identity(consensus_feature)
    v = _validate_numerics(consensus_feature)

    # component scores + primary anchor
    price_score = _price_score(v, rules)
    flow_score = _flow_score(v, rules)
    primary_anchor = _clamp(0.5 * price_score + 0.5 * flow_score)
    anchor_sign = _sign(primary_anchor)

    oi_score = _oi_score(v, rules, anchor_sign)
    funding_score = _funding_score(v, rules)
    liquidation_score = _liquidation_score(v)
    agreement_score = _agreement_score(v, anchor_sign)

    component_scores = {
        "price": price_score,
        "flow": flow_score,
        "oi": oi_score,
        "funding": funding_score,
        "liquidations": liquidation_score,
        "agreement": agreement_score,
    }
    final_score = _clamp(math.fsum(
        component_scores[name] * rules.component_weights[name]
        for name in FORECAST_COMPONENTS))

    # actionability gates, in the exact stable order (inclusive passing)
    mcr = v["min_coverage_ratio"]
    cc = v["consensus_confidence"]
    gate_reasons = []
    if mcr is None or mcr < rules.minimum_coverage_ratio:
        gate_reasons.append(INSUFFICIENT_COVERAGE)
    if cc is None or cc < rules.minimum_consensus_confidence:
        gate_reasons.append(LOW_CONSENSUS_CONFIDENCE)
    # A zero anchor sign (no price/flow direction) is NEVER actionable, even when
    # minimum_primary_score == 0.0 — auxiliary components alone cannot act.
    if anchor_sign == 0.0 or abs(primary_anchor) < rules.minimum_primary_score:
        gate_reasons.append(WEAK_PRIMARY_SIGNAL)
    if abs(final_score) < rules.action_score_threshold:
        gate_reasons.append(SCORE_BELOW_ACTION_THRESHOLD)

    if gate_reasons:
        direction = NEUTRAL
        confidence = 0.0
        reasons = tuple(gate_reasons)
    else:
        direction = LONG if final_score > 0 else SHORT
        reasons = _actionable_reasons(
            direction, component_scores, rules, consensus_feature.is_partial_consensus)
        # cc (0–100) and mcr (0–1) are guaranteed non-None here (gates passed);
        # normalize the confidence percent to a 0–1 quality factor.
        quality_multiplier = math.sqrt((cc / 100.0) * mcr)
        confidence = _clamp(abs(final_score) * quality_multiplier, 0.0, 1.0)

    return ForecastDecision(
        symbol=consensus_feature.symbol,
        market_type=consensus_feature.market_type,
        timeframe=consensus_feature.timeframe,
        bucket_ts=consensus_feature.bucket_ts,
        direction=direction,
        confidence=confidence,
        horizon_set=rules.horizons,
        reasons=reasons,
        component_scores=component_scores,
        final_score=final_score,
        rule_version=rules.rule_version,
        feature_schema_version=consensus_feature.feature_schema_version,
        calculation_version=consensus_feature.calculation_version,
        config_hash=consensus_feature.config_hash,
        config_version=consensus_feature.config_version,
        code_version=consensus_feature.code_version,
    )
