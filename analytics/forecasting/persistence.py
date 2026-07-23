"""
Immutable, self-validating persistence model for a Stage 2 shadow forecast.

`ForecastPrediction` couples one `ForecastDecision` with the exact
`ConsensusFeatureVector` it was computed from plus an explicit reference price, so
every shadow decision becomes a durable, reproducible record. `build_forecast_prediction`
is a pure provenance-checking builder — it never recomputes the forecast.

Pure only: no DB, network, clock, env, filesystem, or ML. A prediction is an
EVENT (what the bot decided for one bucket under one calculation_version + one
rule_version); the storage layer inserts it once and never rewrites it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Mapping, Optional, Sequence

from analytics.feature_engine.consensus_models import ConsensusFeatureVector

from .models import ForecastDecision, ForecastInputError

# Identity/version fields duplicated onto the prediction that must match the
# stored consensus snapshot exactly (never one value claimed, another stored).
_IDENTITY_FIELDS = (
    "symbol", "market_type", "timeframe", "bucket_ts", "feature_schema_version",
    "calculation_version", "config_hash", "config_version", "code_version",
)
_SUMMARY_FIELDS = (
    "exchanges_expected_max", "min_coverage_ratio", "data_confidence_overall",
    "consensus_confidence", "is_partial_consensus",
)


def _finite(value, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ForecastInputError(f"{name} must be a real number, got {type(value).__name__}")
    v = float(value)
    if not math.isfinite(v):
        raise ForecastInputError(f"{name} must be finite, got {value!r}")
    return v


def _finite_in_range_or_none(value, name: str, low: float, high: float):
    if value is None:
        return None
    v = _finite(value, name)
    if not (low <= v <= high):
        raise ForecastInputError(f"{name} must be in [{low}, {high}], got {v!r}")
    return v


@dataclass(frozen=True)
class ForecastPrediction:
    """Deeply-immutable, self-validating durable forecast record. Its field set
    equals the `forecast_predictions` columns EXCEPT the DB-owned `created_at`."""
    symbol: str
    market_type: str
    timeframe: str
    bucket_ts: datetime

    feature_schema_version: int
    calculation_version: str
    rule_version: str

    direction: str
    confidence: float
    horizon_set: Sequence[str]
    reasons: Sequence[str]
    component_scores: Mapping[str, float]
    final_score: float

    reference_price: float
    reference_price_source: str

    exchanges_expected_max: int
    min_coverage_ratio: Optional[float]
    data_confidence_overall: Optional[float]
    consensus_confidence: Optional[float]
    is_partial_consensus: bool

    consensus_snapshot: ConsensusFeatureVector

    config_hash: str
    config_version: str
    code_version: str

    def __post_init__(self):
        if not isinstance(self.consensus_snapshot, ConsensusFeatureVector):
            raise ForecastInputError(
                "consensus_snapshot must be a ConsensusFeatureVector, got "
                f"{type(self.consensus_snapshot).__name__}")

        # Reuse the already-merged ForecastDecision validator for every
        # decision-owned field (identity/version scope, direction, confidence,
        # scores, reasons, horizons) instead of duplicating it. A validation
        # failure surfaces as ForecastInputError unchanged.
        decision = ForecastDecision(
            symbol=self.symbol, market_type=self.market_type, timeframe=self.timeframe,
            bucket_ts=self.bucket_ts, direction=self.direction, confidence=self.confidence,
            horizon_set=self.horizon_set, reasons=self.reasons,
            component_scores=self.component_scores, final_score=self.final_score,
            rule_version=self.rule_version,
            feature_schema_version=self.feature_schema_version,
            calculation_version=self.calculation_version, config_hash=self.config_hash,
            config_version=self.config_version, code_version=self.code_version)
        # Detach the validated (tuple / tuple / MappingProxyType) containers.
        object.__setattr__(self, "horizon_set", decision.horizon_set)
        object.__setattr__(self, "reasons", decision.reasons)
        object.__setattr__(self, "component_scores", decision.component_scores)

        # reference price + source (never rounded/coerced)
        rp = _finite(self.reference_price, "reference_price")
        if not rp > 0:
            raise ForecastInputError(f"reference_price must be > 0, got {rp!r}")
        if not isinstance(self.reference_price_source, str) or not self.reference_price_source.strip():
            raise ForecastInputError("reference_price_source must be a non-empty string")

        # consensus summary values, each on its real scale
        if not isinstance(self.exchanges_expected_max, int) or isinstance(self.exchanges_expected_max, bool) \
                or self.exchanges_expected_max < 1:
            raise ForecastInputError("exchanges_expected_max must be an int >= 1")
        _finite_in_range_or_none(self.min_coverage_ratio, "min_coverage_ratio", 0.0, 1.0)
        _finite_in_range_or_none(self.data_confidence_overall, "data_confidence_overall", 0.0, 100.0)
        _finite_in_range_or_none(self.consensus_confidence, "consensus_confidence", 0.0, 100.0)
        if not isinstance(self.is_partial_consensus, bool):
            raise ForecastInputError("is_partial_consensus must be a bool")

        # provenance: duplicated identity/version + summary must match the snapshot
        snap = self.consensus_snapshot
        for f in _IDENTITY_FIELDS + _SUMMARY_FIELDS:
            if getattr(self, f) != getattr(snap, f):
                raise ForecastInputError(
                    f"prediction {f}={getattr(self, f)!r} does not match "
                    f"consensus_snapshot {getattr(snap, f)!r}")


def build_forecast_prediction(
    decision: ForecastDecision,
    consensus_feature: ConsensusFeatureVector,
    *,
    reference_price: float,
    reference_price_source: str,
) -> ForecastPrediction:
    """Pure builder: bind a decision to its consensus snapshot + reference price.
    Verifies provenance identity (never the scoring math — the forecast core owns
    that) and does NO recomputation, I/O, clock, or mutation. Not gated by
    stage2.enabled."""
    if not isinstance(decision, ForecastDecision):
        raise ForecastInputError(
            f"decision must be a ForecastDecision, got {type(decision).__name__}")
    if not isinstance(consensus_feature, ConsensusFeatureVector):
        raise ForecastInputError(
            f"consensus_feature must be a ConsensusFeatureVector, "
            f"got {type(consensus_feature).__name__}")

    # every shared identity/version field must match before we build the output
    for f in _IDENTITY_FIELDS:
        if getattr(decision, f) != getattr(consensus_feature, f):
            raise ForecastInputError(
                f"decision {f}={getattr(decision, f)!r} does not match "
                f"consensus_feature {getattr(consensus_feature, f)!r}")

    return ForecastPrediction(
        symbol=decision.symbol, market_type=decision.market_type,
        timeframe=decision.timeframe, bucket_ts=decision.bucket_ts,
        feature_schema_version=decision.feature_schema_version,
        calculation_version=decision.calculation_version,
        rule_version=decision.rule_version,
        direction=decision.direction, confidence=decision.confidence,
        horizon_set=decision.horizon_set, reasons=decision.reasons,
        component_scores=decision.component_scores, final_score=decision.final_score,
        reference_price=reference_price, reference_price_source=reference_price_source,
        exchanges_expected_max=consensus_feature.exchanges_expected_max,
        min_coverage_ratio=consensus_feature.min_coverage_ratio,
        data_confidence_overall=consensus_feature.data_confidence_overall,
        consensus_confidence=consensus_feature.consensus_confidence,
        is_partial_consensus=consensus_feature.is_partial_consensus,
        consensus_snapshot=consensus_feature,
        config_hash=decision.config_hash, config_version=decision.config_version,
        code_version=decision.code_version)
