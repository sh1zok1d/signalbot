"""Stage 2 shadow Forecast Core v0: a pure, deterministic, explainable heuristic
(ConsensusFeatureVector -> LONG/SHORT/NEUTRAL + confidence + stable reason codes)
for the BTCUSDT / perp / 5m shadow scope only. No DB, clock, network, or ML;
`confidence` is uncalibrated action strength, not a probability of profit."""
from .core import compute_forecast_decision
from .persistence import ForecastPrediction, build_forecast_prediction
from .outcomes import (
    DEFAULT_OUTCOME_VERSION, EVALUATION_PRICE_SOURCE, ForecastOutcome,
    ForecastOutcomeEvaluation, ForecastOutcomeInputError, ForecastOutcomeWindow,
    OUTCOME_COMPLETE, OUTCOME_HORIZON_MINUTES, OUTCOME_HORIZONS, OUTCOME_INCOMPLETE,
    OUTCOME_STATUSES, OutcomePriceBar, build_forecast_outcome_window,
    evaluate_forecast_outcome,
)
from .outcome_pipeline import (
    ForecastOutcomeReader, ForecastOutcomeWriter, process_forecast_outcome_horizon,
)

from .shadow_cycle import (
    DueOutcomeJob, PREDICTION_DUPLICATE, PREDICTION_INSERTED,
    PREDICTION_SKIPPED_NO_CONSENSUS,
    PREDICTION_SKIPPED_REFERENCE_UNAVAILABLE, PREDICTION_STATUSES,
    ShadowCycleError, ShadowCycleReader, ShadowCycleResult, ShadowCycleWriter,
    process_shadow_cycle,
)

from .models import (
    AGREEMENT_BEARISH, AGREEMENT_BULLISH, COMPOSITE_BEARISH, COMPOSITE_BULLISH,
    DEFAULT_FORECAST_HORIZONS, DEFAULT_FORECAST_RULES, DIRECTIONS,
    FLOW_BEARISH, FLOW_BULLISH, FORECAST_COMPONENTS, ForecastDecision,
    ForecastInputError, ForecastRuleSet, FUNDING_BEARISH_CONTRARIAN,
    FUNDING_BULLISH_CONTRARIAN, INSUFFICIENT_COVERAGE, LIQUIDATIONS_BEARISH,
    LIQUIDATIONS_BULLISH, LONG, LOW_CONSENSUS_CONFIDENCE, NEUTRAL,
    OI_BEARISH_CONTRIBUTION, OI_BULLISH_CONTRIBUTION, PARTIAL_CONSENSUS,
    PRICE_BEARISH, PRICE_BULLISH, SCORE_BELOW_ACTION_THRESHOLD, SHORT,
    WEAK_PRIMARY_SIGNAL,
)

__all__ = [
    "compute_forecast_decision",
    "ForecastPrediction", "build_forecast_prediction",
    # outcome evaluator
    "ForecastOutcomeInputError", "OutcomePriceBar", "ForecastOutcomeWindow",
    "ForecastOutcome", "ForecastOutcomeEvaluation",
    "OUTCOME_COMPLETE", "OUTCOME_INCOMPLETE", "OUTCOME_STATUSES",
    "OUTCOME_HORIZONS", "OUTCOME_HORIZON_MINUTES", "DEFAULT_OUTCOME_VERSION",
    "EVALUATION_PRICE_SOURCE", "build_forecast_outcome_window",
    "evaluate_forecast_outcome", "ForecastOutcomeReader", "ForecastOutcomeWriter",
    "process_forecast_outcome_horizon",
    "ForecastInputError", "ForecastRuleSet", "ForecastDecision",
    "DEFAULT_FORECAST_RULES", "DEFAULT_FORECAST_HORIZONS", "FORECAST_COMPONENTS",
    "DIRECTIONS", "LONG", "SHORT", "NEUTRAL",
    # stable gate / reason codes
    "INSUFFICIENT_COVERAGE", "LOW_CONSENSUS_CONFIDENCE", "WEAK_PRIMARY_SIGNAL",
    "SCORE_BELOW_ACTION_THRESHOLD", "COMPOSITE_BULLISH", "COMPOSITE_BEARISH",
    "PRICE_BULLISH", "PRICE_BEARISH", "FLOW_BULLISH", "FLOW_BEARISH",
    "OI_BULLISH_CONTRIBUTION", "OI_BEARISH_CONTRIBUTION",
    "FUNDING_BULLISH_CONTRARIAN", "FUNDING_BEARISH_CONTRARIAN",
    "LIQUIDATIONS_BULLISH", "LIQUIDATIONS_BEARISH",
    "AGREEMENT_BULLISH", "AGREEMENT_BEARISH", "PARTIAL_CONSENSUS",
    # explicit shadow cycle orchestration
    "ShadowCycleError", "ShadowCycleReader", "ShadowCycleWriter",
    "DueOutcomeJob", "ShadowCycleResult", "PREDICTION_INSERTED",
    "PREDICTION_DUPLICATE", "PREDICTION_SKIPPED_NO_CONSENSUS",
    "PREDICTION_SKIPPED_REFERENCE_UNAVAILABLE", "PREDICTION_STATUSES",
    "process_shadow_cycle",
]
