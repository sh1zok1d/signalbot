"""Explicit Stage 2 shadow forecast cycle orchestration.

This module is a thin composition boundary for one caller-selected, already
closed 5m bucket plus a caller-supplied sequence of already-due outcome jobs.
It does not choose buckets, inspect wall-clock time, discover pending
predictions, retry, or provide cross-table transaction semantics.

Execution order is fixed:
1. orchestration-specific preflight;
2. process the current Stage 2 bucket;
3. compute a forecast when consensus exists;
4. resolve the explicit reference exchange from the bucket result only;
5. insert the current prediction when possible;
6. process explicit due outcomes sequentially;
7. return an immutable result.

A later exception does not roll back earlier successful writes. Prediction
insert-once semantics make repeated invocations safe, outcome upserts allow
corrected measurements, and later recovery/catch-up code owns partially completed cycles.
"""
from __future__ import annotations

import math
from collections.abc import Iterator as _AbcIterator, Mapping as _AbcMapping, Sequence as _AbcSequence, Set as _AbcSet
from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Optional, Protocol, Sequence

from analytics.feature_engine.bucket_coordinator import Stage2BucketResult, process_stage2_bucket
from analytics.feature_engine.consensus_models import ConsensusFeatureVector
from analytics.feature_engine.input_adapter import RawBundleReader
from analytics.feature_engine.models import ExchangeFeatureVector
from analytics.feature_engine.pipeline import ExchangeFeatureWriter
from analytics.feature_engine.consensus_pipeline import ConsensusFeatureWriter
from common.stage2_config import Stage2Config
from symbols.registry import ACTIVE_EXCHANGES

from .core import compute_forecast_decision
from .models import DEFAULT_FORECAST_RULES, ForecastDecision, ForecastRuleSet
from .outcome_pipeline import ForecastOutcomeReader, ForecastOutcomeWriter, process_forecast_outcome_horizon
from .outcomes import DEFAULT_OUTCOME_VERSION, EVALUATION_PRICE_SOURCE, ForecastOutcomeEvaluation, build_forecast_outcome_window
from .persistence import ForecastPrediction, build_forecast_prediction

PREDICTION_INSERTED = "PREDICTION_INSERTED"
PREDICTION_DUPLICATE = "PREDICTION_DUPLICATE"
PREDICTION_SKIPPED_NO_CONSENSUS = "PREDICTION_SKIPPED_NO_CONSENSUS"
PREDICTION_SKIPPED_REFERENCE_UNAVAILABLE = (
    "PREDICTION_SKIPPED_REFERENCE_UNAVAILABLE"
)
PREDICTION_STATUSES = (
    PREDICTION_INSERTED,
    PREDICTION_DUPLICATE,
    PREDICTION_SKIPPED_NO_CONSENSUS,
    PREDICTION_SKIPPED_REFERENCE_UNAVAILABLE,
)


class ShadowCycleError(ValueError):
    """Malformed shadow-cycle inputs or impossible composition states."""


class ShadowCycleReader(RawBundleReader, ForecastOutcomeReader, Protocol):
    ...


class ShadowCycleWriter(
    ExchangeFeatureWriter,
    ConsensusFeatureWriter,
    ForecastOutcomeWriter,
    Protocol,
):
    async def insert_forecast_prediction(self, row: ForecastPrediction) -> bool:
        ...


@dataclass(frozen=True)
class DueOutcomeJob:
    prediction: ForecastPrediction
    horizon: str
    evaluation_exchange: str
    outcome_version: str = DEFAULT_OUTCOME_VERSION

    def __post_init__(self) -> None:
        if type(self.prediction) is not ForecastPrediction:
            raise ShadowCycleError(
                "prediction must be exactly ForecastPrediction, got "
                f"{type(self.prediction).__name__}"
            )
        build_forecast_outcome_window(
            self.prediction,
            horizon=self.horizon,
            evaluation_exchange=self.evaluation_exchange,
            outcome_version=self.outcome_version,
        )


@dataclass(frozen=True)
class ShadowCycleResult:
    bucket_result: Stage2BucketResult
    prediction_status: str
    decision: Optional[ForecastDecision]
    prediction: Optional[ForecastPrediction]
    prediction_inserted: Optional[bool]
    outcome_evaluations: Sequence[ForecastOutcomeEvaluation]

    def __post_init__(self) -> None:
        if type(self.bucket_result) is not Stage2BucketResult:
            raise ShadowCycleError("bucket_result must be exactly Stage2BucketResult")
        if self.decision is not None and type(self.decision) is not ForecastDecision:
            raise ShadowCycleError("decision must be exactly ForecastDecision or None")
        if self.prediction is not None and type(self.prediction) is not ForecastPrediction:
            raise ShadowCycleError("prediction must be exactly ForecastPrediction or None")
        evaluations = _detach_sequence(self.outcome_evaluations, "outcome_evaluations")
        for value in evaluations:
            if type(value) is not ForecastOutcomeEvaluation:
                raise ShadowCycleError(
                    "outcome_evaluations items must be exactly ForecastOutcomeEvaluation"
                )
        object.__setattr__(self, "outcome_evaluations", evaluations)
        if self.prediction_status not in PREDICTION_STATUSES:
            raise ShadowCycleError(f"invalid prediction_status {self.prediction_status!r}")
        consensus = self.bucket_result.consensus_feature
        if self.prediction_status == PREDICTION_INSERTED:
            _require_consensus(consensus)
            if self.decision is None or self.prediction is None or self.prediction_inserted is not True:
                raise ShadowCycleError("inserted status requires consensus, decision, prediction, and True")
        elif self.prediction_status == PREDICTION_DUPLICATE:
            _require_consensus(consensus)
            if self.decision is None or self.prediction is None or self.prediction_inserted is not False:
                raise ShadowCycleError("duplicate status requires consensus, decision, prediction, and False")
        elif self.prediction_status == PREDICTION_SKIPPED_NO_CONSENSUS:
            if consensus is not None or self.decision is not None or self.prediction is not None or self.prediction_inserted is not None:
                raise ShadowCycleError("no-consensus status requires no consensus, decision, prediction, or insert bool")
        elif self.prediction_status == PREDICTION_SKIPPED_REFERENCE_UNAVAILABLE:
            _require_consensus(consensus)
            if self.decision is None or self.prediction is not None or self.prediction_inserted is not None:
                raise ShadowCycleError("reference-unavailable status requires consensus and decision only")
        if self.decision is not None:
            _require_consensus(consensus)
            _assert_decision_matches_consensus(self.decision, consensus)
        if self.prediction is not None:
            _require_consensus(consensus)
            _assert_prediction_matches(self.prediction, self.decision, consensus)


async def process_shadow_cycle(
    reader: ShadowCycleReader,
    writer: ShadowCycleWriter,
    stage2_config: Stage2Config,
    *,
    exchanges: Sequence[str],
    symbol: str,
    market_type: str,
    timeframe: str,
    bucket_ts: datetime,
    code_version: str,
    liquidation_feed_available_by_exchange: Mapping[str, bool],
    reference_exchange: str,
    forecast_rules: ForecastRuleSet = DEFAULT_FORECAST_RULES,
    due_outcome_jobs: Sequence[DueOutcomeJob] = (),
) -> ShadowCycleResult:
    if type(stage2_config) is not Stage2Config:
        raise ShadowCycleError("stage2_config must be exactly Stage2Config")
    if type(forecast_rules) is not ForecastRuleSet:
        raise ShadowCycleError("forecast_rules must be exactly ForecastRuleSet")
    requested = _validate_exchanges(exchanges)
    if type(reference_exchange) is not str or reference_exchange not in ACTIVE_EXCHANGES:
        raise ShadowCycleError("reference_exchange must be a canonical active exchange")
    if reference_exchange not in requested:
        raise ShadowCycleError("reference_exchange must be present in exchanges")
    jobs = _validate_due_jobs(due_outcome_jobs)
    _reject_duplicate_due_jobs(jobs)
    for job in jobs:
        build_forecast_outcome_window(
            job.prediction,
            horizon=job.horizon,
            evaluation_exchange=job.evaluation_exchange,
            outcome_version=job.outcome_version,
        )

    bucket_result = await process_stage2_bucket(
        reader,
        writer,
        writer,
        stage2_config,
        exchanges=requested,
        symbol=symbol,
        market_type=market_type,
        timeframe=timeframe,
        bucket_ts=bucket_ts,
        code_version=code_version,
        liquidation_feed_available_by_exchange=liquidation_feed_available_by_exchange,
    )
    if type(bucket_result) is not Stage2BucketResult:
        raise ShadowCycleError(
            "process_stage2_bucket must return exactly Stage2BucketResult"
        )

    decision: Optional[ForecastDecision] = None
    prediction: Optional[ForecastPrediction] = None
    inserted: Optional[bool] = None
    if bucket_result.consensus_feature is None:
        status = PREDICTION_SKIPPED_NO_CONSENSUS
    else:
        decision = compute_forecast_decision(bucket_result.consensus_feature, forecast_rules)
        reference_vector = _resolve_reference_vector(bucket_result, reference_exchange)
        if reference_vector is None:
            status = PREDICTION_SKIPPED_REFERENCE_UNAVAILABLE
        else:
            reference_price = _validate_reference_price(reference_vector.close_price)
            prediction = build_forecast_prediction(
                decision,
                bucket_result.consensus_feature,
                reference_price=reference_price,
                reference_price_source=f"{reference_exchange}_close_5m",
            )
            inserted = await writer.insert_forecast_prediction(prediction)
            if type(inserted) is not bool:
                raise ShadowCycleError("insert_forecast_prediction must return bool")
            status = PREDICTION_INSERTED if inserted else PREDICTION_DUPLICATE

    evaluations: list[ForecastOutcomeEvaluation] = []
    for job in jobs:
        evaluations.append(await process_forecast_outcome_horizon(
            reader,
            writer,
            job.prediction,
            horizon=job.horizon,
            evaluation_exchange=job.evaluation_exchange,
            outcome_version=job.outcome_version,
        ))

    return ShadowCycleResult(
        bucket_result=bucket_result,
        prediction_status=status,
        decision=decision,
        prediction=prediction,
        prediction_inserted=inserted,
        outcome_evaluations=evaluations,
    )


def _detach_sequence(value, name: str) -> tuple:
    if isinstance(value, (str, bytes, bytearray, _AbcMapping, _AbcSet, _AbcIterator)) or not isinstance(value, _AbcSequence):
        raise ShadowCycleError(f"{name} must be a non-string Sequence")
    return tuple(value)


def _validate_exchanges(exchanges: Sequence[str]) -> tuple[str, ...]:
    values = _detach_sequence(exchanges, "exchanges")
    if not values:
        raise ShadowCycleError("exchanges must be non-empty")
    seen: set[str] = set()
    for ex in values:
        if type(ex) is not str or ex not in ACTIVE_EXCHANGES:
            raise ShadowCycleError(f"unknown exchange {ex!r}")
        if ex in seen:
            raise ShadowCycleError(f"duplicate exchange {ex!r}")
        seen.add(ex)
    return values


def _validate_due_jobs(due_outcome_jobs: Sequence[DueOutcomeJob]) -> tuple[DueOutcomeJob, ...]:
    jobs = _detach_sequence(due_outcome_jobs, "due_outcome_jobs")
    for job in jobs:
        if type(job) is not DueOutcomeJob:
            raise ShadowCycleError("due_outcome_jobs items must be exactly DueOutcomeJob")
    return jobs


def _reject_duplicate_due_jobs(jobs: Sequence[DueOutcomeJob]) -> None:
    seen = set()
    for job in jobs:
        key = (
            job.prediction.symbol,
            job.prediction.market_type,
            job.prediction.timeframe,
            job.prediction.bucket_ts,
            job.prediction.calculation_version,
            job.prediction.rule_version,
            job.horizon,
            job.evaluation_exchange,
            EVALUATION_PRICE_SOURCE,
            job.outcome_version,
        )
        if key in seen:
            raise ShadowCycleError("duplicate due outcome job identity")
        seen.add(key)


def _require_consensus(consensus) -> None:
    if type(consensus) is not ConsensusFeatureVector:
        raise ShadowCycleError("consensus_feature must be exactly ConsensusFeatureVector")


def _assert_decision_matches_consensus(decision: ForecastDecision, consensus: ConsensusFeatureVector) -> None:
    for field in ("symbol", "market_type", "timeframe", "bucket_ts", "feature_schema_version", "calculation_version", "config_hash", "config_version", "code_version"):
        if getattr(decision, field) != getattr(consensus, field):
            raise ShadowCycleError(f"decision {field} does not match consensus")


def _assert_prediction_matches(prediction: ForecastPrediction, decision: Optional[ForecastDecision], consensus: ConsensusFeatureVector) -> None:
    for field in ("symbol", "market_type", "timeframe", "bucket_ts", "feature_schema_version", "calculation_version", "config_hash", "config_version", "code_version"):
        if getattr(prediction, field) != getattr(consensus, field):
            raise ShadowCycleError(f"prediction {field} does not match consensus")
    if prediction.consensus_snapshot is not consensus:
        raise ShadowCycleError("prediction consensus_snapshot is not the consensus used")
    if decision is None:
        raise ShadowCycleError("prediction requires decision")
    for field in ("direction", "confidence", "horizon_set", "reasons", "component_scores", "final_score", "rule_version"):
        if getattr(prediction, field) != getattr(decision, field):
            raise ShadowCycleError(f"prediction {field} does not match decision")


def _resolve_reference_vector(
    bucket_result: Stage2BucketResult,
    reference_exchange: str,
) -> Optional[ExchangeFeatureVector]:
    matches: list[ExchangeFeatureVector] = []
    for vector in bucket_result.exchange_features:
        if type(vector) is not ExchangeFeatureVector:
            raise ShadowCycleError(
                "exchange_features items must be exactly ExchangeFeatureVector"
            )
        if vector.exchange == reference_exchange:
            matches.append(vector)
    if len(matches) > 1:
        raise ShadowCycleError("multiple reference exchange feature vectors found")
    if not matches:
        return None
    vector = matches[0]
    if vector.is_usable is not True:
        return None
    if vector.has_gap is not False:
        return None
    _validate_reference_bar_counts(vector.bars_expected, vector.bars_present)
    if vector.bars_present != 5:
        return None
    if vector.close_price is None:
        return None
    return vector


def _validate_reference_bar_counts(bars_expected, bars_present) -> None:
    if type(bars_expected) is not int:
        raise ShadowCycleError("reference bars_expected must be exactly int")
    if type(bars_present) is not int:
        raise ShadowCycleError("reference bars_present must be exactly int")
    if bars_expected != 5:
        raise ShadowCycleError("reference bars_expected must be exactly 5")
    if not (0 <= bars_present <= 5):
        raise ShadowCycleError("reference bars_present must be in [0, 5]")


def _validate_reference_price(value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ShadowCycleError("reference close_price must be a real number")
    try:
        price = float(value)
    except OverflowError as exc:
        raise ShadowCycleError("reference close_price must be finite and > 0") from exc
    if not math.isfinite(price) or price <= 0:
        raise ShadowCycleError("reference close_price must be finite and > 0")
    return value
