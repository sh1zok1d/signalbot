"""Pure Forecast Core computation over real consensus feature vectors.

The core validates the consensus model on its native upstream scales: coverage
and direction agreement values are ratios in ``[0, 1]``; overall data confidence
and consensus confidence are percentages in ``[0, 100]``.
"""
from __future__ import annotations

import math
from typing import Optional

from analytics.feature_engine.consensus_models import ConsensusFeatureVector

from .models import DEFAULT_FORECAST_RULES, ForecastDecision, ForecastError, ForecastRuleSet

LOW_CONSENSUS_CONFIDENCE = "LOW_CONSENSUS_CONFIDENCE"
LOW_COVERAGE = "LOW_COVERAGE"
INSUFFICIENT_SIGNAL = "INSUFFICIENT_SIGNAL"
COMPOSITE_BULLISH = "COMPOSITE_BULLISH"
COMPOSITE_BEARISH = "COMPOSITE_BEARISH"


def _finite(value: object, name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ForecastError(f"{name} must be a number")
    v = float(value)
    if not math.isfinite(v):
        raise ForecastError(f"{name} must be finite")
    return v


def _ratio_or_none(value: Optional[float], name: str) -> Optional[float]:
    if value is None:
        return None
    v = _finite(value, name)
    if not 0.0 <= v <= 1.0:
        raise ForecastError(f"{name} must be in [0, 1]")
    return v


def _percent_or_none(value: Optional[float], name: str) -> Optional[float]:
    if value is None:
        return None
    v = _finite(value, name)
    if not 0.0 <= v <= 100.0:
        raise ForecastError(f"{name} must be in [0, 100]")
    return v


def _validate_rules(rules: ForecastRuleSet) -> None:
    pct = _finite(rules.minimum_consensus_confidence, "minimum_consensus_confidence")
    if not 0.0 <= pct <= 100.0:
        raise ForecastError("minimum_consensus_confidence must be in [0, 100]")
    cov = _finite(rules.minimum_coverage_ratio, "minimum_coverage_ratio")
    if not 0.0 <= cov <= 1.0:
        raise ForecastError("minimum_coverage_ratio must be in [0, 1]")
    _finite(rules.bullish_threshold, "bullish_threshold")
    _finite(rules.bearish_threshold, "bearish_threshold")
    if rules.bearish_threshold >= rules.bullish_threshold:
        raise ForecastError("bearish_threshold must be below bullish_threshold")


def _score(consensus: ConsensusFeatureVector) -> float:
    parts = []
    if consensus.price_move_pct_median is not None:
        parts.append(max(-1.0, min(1.0, consensus.price_move_pct_median / 2.0)))
    if consensus.taker_delta_notional_usd_sum is not None and consensus.volume_notional_usd_sum:
        parts.append(max(-1.0, min(1.0, consensus.taker_delta_notional_usd_sum / consensus.volume_notional_usd_sum)))
    if consensus.oi_change_pct_median is not None:
        parts.append(max(-1.0, min(1.0, consensus.oi_change_pct_median / 5.0)))
    if consensus.funding_rate_median is not None:
        parts.append(max(-1.0, min(1.0, consensus.funding_rate_median * 1000.0)))
    if not parts:
        return 0.0
    return math.fsum(parts) / len(parts)


def compute_forecast_decision(consensus: ConsensusFeatureVector, rules: ForecastRuleSet = DEFAULT_FORECAST_RULES) -> ForecastDecision:
    """Compute a normalized public forecast decision from real consensus output."""
    _validate_rules(rules)
    min_coverage_ratio = _ratio_or_none(consensus.min_coverage_ratio, "min_coverage_ratio")
    _ratio_or_none(consensus.price_direction_agreement, "price_direction_agreement")
    _ratio_or_none(consensus.flow_direction_agreement, "flow_direction_agreement")
    _ratio_or_none(consensus.oi_direction_agreement, "oi_direction_agreement")
    _percent_or_none(consensus.data_confidence_overall, "data_confidence_overall")
    consensus_confidence = _percent_or_none(consensus.consensus_confidence, "consensus_confidence")

    reasons: list[str] = []
    if consensus_confidence is None or consensus_confidence < rules.minimum_consensus_confidence:
        reasons.append(LOW_CONSENSUS_CONFIDENCE)
    if min_coverage_ratio is None or min_coverage_ratio < rules.minimum_coverage_ratio:
        reasons.append(LOW_COVERAGE)

    final_score = _score(consensus)
    if reasons:
        decision = "NO_TRADE"
        confidence = 0.0
    elif final_score >= rules.bullish_threshold:
        decision = "BULLISH"
        reasons.append(COMPOSITE_BULLISH)
        quality_multiplier = math.sqrt((consensus_confidence / 100.0) * min_coverage_ratio)
        confidence = max(0.0, min(1.0, abs(final_score) * quality_multiplier))
    elif final_score <= rules.bearish_threshold:
        decision = "BEARISH"
        reasons.append(COMPOSITE_BEARISH)
        quality_multiplier = math.sqrt((consensus_confidence / 100.0) * min_coverage_ratio)
        confidence = max(0.0, min(1.0, abs(final_score) * quality_multiplier))
    else:
        decision = "NO_TRADE"
        reasons.append(INSUFFICIENT_SIGNAL)
        confidence = 0.0

    return ForecastDecision(
        symbol=consensus.symbol, market_type=consensus.market_type, timeframe=consensus.timeframe,
        bucket_ts=consensus.bucket_ts, feature_schema_version=consensus.feature_schema_version,
        calculation_version=consensus.calculation_version, config_hash=consensus.config_hash,
        config_version=consensus.config_version, code_version=consensus.code_version,
        rule_version=rules.rule_version, horizon_set=("15m", "30m", "1h"),
        decision=decision, confidence=confidence, final_score=final_score, reasons=tuple(reasons),
    )
