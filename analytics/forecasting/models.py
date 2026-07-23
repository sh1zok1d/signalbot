"""
Immutable models + stable constants for the Stage 2 shadow Forecast Core v0.

Pure data only — no DB, network, clock, env, or filesystem. `ForecastRuleSet` is a
deeply-frozen, self-validating provisional rule set; `ForecastDecision` is the
deeply-frozen, self-validating output of `compute_forecast_decision`.

These thresholds are a PROVISIONAL research heuristic for the BTCUSDT / perp / 5m
shadow scope only — not a claim of predictive validity. `ForecastDecision.confidence`
is an uncalibrated, deterministic ACTION-STRENGTH score in [0, 1]; it is NOT a
probability of profit and is never turned into a percentage or passed through a
sigmoid/logistic transform.

The ratio/confidence inputs the core reads (`consensus_confidence`,
`data_confidence_overall`, the direction agreements, `min_coverage_ratio`) are
validated as normalized [0, 1] values; a future integration layer is responsible
for presenting the consensus vector on that normalized scale.
"""
from __future__ import annotations

import math
from collections.abc import Mapping as _AbcMapping, Sequence as _AbcSequence
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Mapping, Sequence

# ---- directions ------------------------------------------------------------
LONG = "LONG"
SHORT = "SHORT"
NEUTRAL = "NEUTRAL"
DIRECTIONS = (LONG, SHORT, NEUTRAL)

# ---- component + horizon taxonomy ------------------------------------------
FORECAST_COMPONENTS = (
    "price",
    "flow",
    "oi",
    "funding",
    "liquidations",
    "agreement",
)

DEFAULT_FORECAST_HORIZONS = (
    "15m",
    "1h",
    "4h",
)

# ---- stable gate / reason codes --------------------------------------------
INSUFFICIENT_COVERAGE = "INSUFFICIENT_COVERAGE"
LOW_CONSENSUS_CONFIDENCE = "LOW_CONSENSUS_CONFIDENCE"
WEAK_PRIMARY_SIGNAL = "WEAK_PRIMARY_SIGNAL"
SCORE_BELOW_ACTION_THRESHOLD = "SCORE_BELOW_ACTION_THRESHOLD"

COMPOSITE_BULLISH = "COMPOSITE_BULLISH"
COMPOSITE_BEARISH = "COMPOSITE_BEARISH"

PRICE_BULLISH = "PRICE_BULLISH"
PRICE_BEARISH = "PRICE_BEARISH"
FLOW_BULLISH = "FLOW_BULLISH"
FLOW_BEARISH = "FLOW_BEARISH"
OI_BULLISH_CONTRIBUTION = "OI_BULLISH_CONTRIBUTION"
OI_BEARISH_CONTRIBUTION = "OI_BEARISH_CONTRIBUTION"
FUNDING_BULLISH_CONTRARIAN = "FUNDING_BULLISH_CONTRARIAN"
FUNDING_BEARISH_CONTRARIAN = "FUNDING_BEARISH_CONTRARIAN"
LIQUIDATIONS_BULLISH = "LIQUIDATIONS_BULLISH"
LIQUIDATIONS_BEARISH = "LIQUIDATIONS_BEARISH"
AGREEMENT_BULLISH = "AGREEMENT_BULLISH"
AGREEMENT_BEARISH = "AGREEMENT_BEARISH"
PARTIAL_CONSENSUS = "PARTIAL_CONSENSUS"

_WEIGHT_SUM_TOL = 1e-12


class ForecastInputError(ValueError):
    """Malformed forecast input: a bad ConsensusFeatureVector, unsupported
    identity, an invalid numeric field, or a malformed/inconsistent
    ForecastRuleSet. Never silently coerced."""


# ---- shared numeric validators ---------------------------------------------
def _finite_number(value, name: str) -> float:
    """A real, finite number as float — bool rejected, NaN/±Inf rejected."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ForecastInputError(f"{name} must be a real number, got {type(value).__name__}")
    v = float(value)
    if not math.isfinite(v):
        raise ForecastInputError(f"{name} must be finite, got {value!r}")
    return v


def _in_range(value: float, name: str, low: float, high: float,
              *, low_inclusive: bool = True, high_inclusive: bool = True) -> float:
    lo_ok = value >= low if low_inclusive else value > low
    hi_ok = value <= high if high_inclusive else value < high
    if not (lo_ok and hi_ok):
        lb = "[" if low_inclusive else "("
        rb = "]" if high_inclusive else ")"
        raise ForecastInputError(f"{name} must be in {lb}{low}, {high}{rb}, got {value!r}")
    return value


def _nonblank(value, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ForecastInputError(f"{name} must be a non-empty string")
    return value


# ---- rule set --------------------------------------------------------------
@dataclass(frozen=True)
class ForecastRuleSet:
    """Provisional, self-validating shadow rule set (deeply immutable)."""
    rule_version: str
    horizons: Sequence[str]

    minimum_coverage_ratio: float
    minimum_consensus_confidence: float
    minimum_primary_score: float
    action_score_threshold: float
    reason_score_threshold: float

    price_full_scale_pct: float
    flow_imbalance_full_scale: float
    oi_change_full_scale_pct: float
    funding_full_scale: float

    component_weights: Mapping[str, float]

    def __post_init__(self):
        # Detach/freeze the container fields (checking shape BEFORE tuple/dict so a
        # str/bytes horizons or a non-mapping weights can never be silently taken).
        h = self.horizons
        if isinstance(h, (str, bytes, bytearray)) or not isinstance(h, _AbcSequence):
            raise ForecastInputError(
                f"horizons must be a Sequence (list/tuple), got {type(h).__name__}")
        object.__setattr__(self, "horizons", tuple(h))
        w = self.component_weights
        if not isinstance(w, _AbcMapping):
            raise ForecastInputError(
                f"component_weights must be a mapping, got {type(w).__name__}")
        object.__setattr__(self, "component_weights", MappingProxyType(dict(w)))
        self._validate()

    def _validate(self) -> None:
        _nonblank(self.rule_version, "rule_version")

        if len(self.horizons) == 0:
            raise ForecastInputError("horizons must be non-empty")
        seen = set()
        for h in self.horizons:
            _nonblank(h, "horizon")
            if h in seen:
                raise ForecastInputError(f"duplicate horizon {h!r}")
            seen.add(h)

        # unit-interval thresholds (with the exact open/closed bounds from the spec)
        _in_range(_finite_number(self.minimum_coverage_ratio, "minimum_coverage_ratio"),
                  "minimum_coverage_ratio", 0.0, 1.0, low_inclusive=False)
        _in_range(_finite_number(self.minimum_consensus_confidence, "minimum_consensus_confidence"),
                  "minimum_consensus_confidence", 0.0, 1.0)
        _in_range(_finite_number(self.minimum_primary_score, "minimum_primary_score"),
                  "minimum_primary_score", 0.0, 1.0)
        _in_range(_finite_number(self.action_score_threshold, "action_score_threshold"),
                  "action_score_threshold", 0.0, 1.0, low_inclusive=False)
        _in_range(_finite_number(self.reason_score_threshold, "reason_score_threshold"),
                  "reason_score_threshold", 0.0, 1.0)

        # full-scale denominators must be strictly positive
        for name in ("price_full_scale_pct", "flow_imbalance_full_scale",
                     "oi_change_full_scale_pct", "funding_full_scale"):
            v = _finite_number(getattr(self, name), name)
            if not v > 0:
                raise ForecastInputError(f"{name} must be > 0, got {v!r}")

        self._validate_weights()

    def _validate_weights(self) -> None:
        w = self.component_weights
        if set(w) != set(FORECAST_COMPONENTS):
            raise ForecastInputError(
                f"component_weights keys must be exactly {list(FORECAST_COMPONENTS)}, "
                f"got {sorted(w)}")
        vals = {k: _finite_number(w[k], f"component_weights.{k}") for k in FORECAST_COMPONENTS}
        for k, v in vals.items():
            if v < 0:
                raise ForecastInputError(f"component_weights.{k} must be >= 0, got {v!r}")
        total = math.fsum(vals[k] for k in FORECAST_COMPONENTS)
        if abs(total - 1.0) > _WEIGHT_SUM_TOL:
            raise ForecastInputError(f"component_weights must sum to 1.0, got {total!r}")
        if not vals["price"] > 0:
            raise ForecastInputError("component_weights.price must be > 0")
        if not vals["flow"] > 0:
            raise ForecastInputError("component_weights.flow must be > 0")


DEFAULT_FORECAST_RULES = ForecastRuleSet(
    rule_version="forecast-rules-v0.1.0",
    horizons=DEFAULT_FORECAST_HORIZONS,

    minimum_coverage_ratio=2.0 / 3.0,
    minimum_consensus_confidence=0.50,
    minimum_primary_score=0.10,
    action_score_threshold=0.30,
    reason_score_threshold=0.10,

    price_full_scale_pct=0.50,
    flow_imbalance_full_scale=0.10,
    oi_change_full_scale_pct=1.00,
    funding_full_scale=0.00030,

    component_weights={
        "price": 0.30,
        "flow": 0.30,
        "oi": 0.15,
        "funding": 0.10,
        "liquidations": 0.10,
        "agreement": 0.05,
    },
)


# ---- decision --------------------------------------------------------------
@dataclass(frozen=True)
class ForecastDecision:
    """Deeply-immutable, self-validating forecast output. `confidence` is an
    uncalibrated action-strength score in [0, 1], NOT a probability of profit."""
    symbol: str
    market_type: str
    timeframe: str
    bucket_ts: datetime

    direction: str
    confidence: float
    horizon_set: Sequence[str]
    reasons: Sequence[str]

    component_scores: Mapping[str, float]
    final_score: float

    rule_version: str

    feature_schema_version: int
    calculation_version: str
    config_hash: str
    config_version: str
    code_version: str

    def __post_init__(self):
        object.__setattr__(self, "horizon_set", tuple(self.horizon_set))
        object.__setattr__(self, "reasons", tuple(self.reasons))
        cs = self.component_scores
        if not isinstance(cs, _AbcMapping):
            raise ForecastInputError(
                f"component_scores must be a mapping, got {type(cs).__name__}")
        object.__setattr__(self, "component_scores", MappingProxyType(dict(cs)))
        self._validate()

    def _validate(self) -> None:
        if self.direction not in DIRECTIONS:
            raise ForecastInputError(
                f"direction must be one of {list(DIRECTIONS)}, got {self.direction!r}")
        _in_range(_finite_number(self.confidence, "confidence"), "confidence", 0.0, 1.0)
        _in_range(_finite_number(self.final_score, "final_score"), "final_score", -1.0, 1.0)

        if set(self.component_scores) != set(FORECAST_COMPONENTS):
            raise ForecastInputError(
                f"component_scores keys must be exactly {list(FORECAST_COMPONENTS)}, "
                f"got {sorted(self.component_scores)}")
        for k in FORECAST_COMPONENTS:
            _in_range(_finite_number(self.component_scores[k], f"component_scores.{k}"),
                      f"component_scores.{k}", -1.0, 1.0)

        if len(self.reasons) == 0:
            raise ForecastInputError("reasons must contain at least one reason")
        seen = set()
        for r in self.reasons:
            _nonblank(r, "reason")
            if r in seen:
                raise ForecastInputError(f"duplicate reason {r!r}")
            seen.add(r)

        _nonblank(self.rule_version, "rule_version")
