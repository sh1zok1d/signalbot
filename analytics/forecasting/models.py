"""Immutable public models for Forecast Core.

Forecast Core accepts the real ``ConsensusFeatureVector`` emitted by the merged
consensus core. Upstream consensus confidence fields use their native scales:
``min_coverage_ratio`` and direction agreements are ratios in ``[0, 1]``, while
``data_confidence_overall`` and ``consensus_confidence`` are percentages in
``[0, 100]``. Callers must pass the immutable consensus vector directly; no
normalizing copy is required.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import re
import math

_HEX16 = re.compile(r"^[0-9a-f]{16}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class ForecastError(ValueError):
    """Invalid forecast request, rules, consensus input, or decision."""


def _nonblank(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ForecastError(f"{name} must be a non-empty string")
    return value


def _string_sequence(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ForecastError(f"{name} must be a non-string sequence")
    if len(value) == 0:  # type: ignore[arg-type]
        raise ForecastError(f"{name} must be non-empty")
    out: list[str] = []
    seen: set[str] = set()
    for item in value:  # type: ignore[union-attr]
        if not isinstance(item, str) or not item.strip():
            raise ForecastError(f"{name} entries must be non-empty strings")
        if item in seen:
            raise ForecastError(f"{name} must not contain duplicates")
        seen.add(item)
        out.append(item)
    return tuple(out)


def _utc_5m_bucket(value: object, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise ForecastError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ForecastError(f"{name} must be timezone-aware UTC")
    utc = value.astimezone(timezone.utc)
    if utc.utcoffset() != timezone.utc.utcoffset(utc):
        raise ForecastError(f"{name} must be UTC")
    if utc.second != 0 or utc.microsecond != 0:
        raise ForecastError(f"{name} must be whole-minute")
    if utc.minute % 5 != 0:
        raise ForecastError(f"{name} must be 5m-aligned")
    if value.tzinfo is not timezone.utc and value.utcoffset() == timezone.utc.utcoffset(utc):
        return utc
    return value


@dataclass(frozen=True)
class ForecastRuleSet:
    """Pure rule parameters for Forecast Core.

    ``minimum_consensus_confidence`` is the raw upstream consensus percentage in
    ``[0, 100]``. Forecast decision confidence remains a normalized ``[0, 1]``
    score.
    """

    minimum_consensus_confidence: float = 50.0
    minimum_coverage_ratio: float = 0.5
    bullish_threshold: float = 0.20
    bearish_threshold: float = -0.20
    rule_version: str = "forecast-rules-v1"

    def __post_init__(self) -> None:
        if not isinstance(self.minimum_consensus_confidence, (int, float)) or isinstance(self.minimum_consensus_confidence, bool) or not math.isfinite(float(self.minimum_consensus_confidence)) or not 0.0 <= float(self.minimum_consensus_confidence) <= 100.0:
            raise ForecastError("minimum_consensus_confidence must be finite and in [0, 100]")
        if not isinstance(self.minimum_coverage_ratio, (int, float)) or isinstance(self.minimum_coverage_ratio, bool) or not math.isfinite(float(self.minimum_coverage_ratio)) or not 0.0 <= float(self.minimum_coverage_ratio) <= 1.0:
            raise ForecastError("minimum_coverage_ratio must be finite and in [0, 1]")
        if not isinstance(self.bullish_threshold, (int, float)) or isinstance(self.bullish_threshold, bool) or not math.isfinite(float(self.bullish_threshold)):
            raise ForecastError("bullish_threshold must be finite")
        if not isinstance(self.bearish_threshold, (int, float)) or isinstance(self.bearish_threshold, bool) or not math.isfinite(float(self.bearish_threshold)):
            raise ForecastError("bearish_threshold must be finite")
        if float(self.bearish_threshold) >= float(self.bullish_threshold):
            raise ForecastError("bearish_threshold must be below bullish_threshold")
        _nonblank(self.rule_version, "rule_version")
        object.__setattr__(self, "minimum_consensus_confidence", float(self.minimum_consensus_confidence))
        object.__setattr__(self, "minimum_coverage_ratio", float(self.minimum_coverage_ratio))
        object.__setattr__(self, "bullish_threshold", float(self.bullish_threshold))
        object.__setattr__(self, "bearish_threshold", float(self.bearish_threshold))


DEFAULT_FORECAST_RULES = ForecastRuleSet(minimum_consensus_confidence=50.0)


@dataclass(frozen=True)
class ForecastDecision:
    """Immutable, self-validating public forecast decision model."""

    symbol: str
    market_type: str
    timeframe: str
    bucket_ts: datetime
    feature_schema_version: int
    calculation_version: str
    config_hash: str
    config_version: str
    code_version: str
    rule_version: str
    horizon_set: Sequence[str]
    decision: str
    confidence: float
    final_score: float
    reasons: Sequence[str]

    def __post_init__(self) -> None:
        if self.symbol != "BTCUSDT":
            raise ForecastError("symbol must equal BTCUSDT")
        if self.market_type != "perp":
            raise ForecastError("market_type must equal perp")
        if self.timeframe != "5m":
            raise ForecastError("timeframe must equal 5m")
        object.__setattr__(self, "bucket_ts", _utc_5m_bucket(self.bucket_ts, "bucket_ts"))
        if not isinstance(self.feature_schema_version, int) or isinstance(self.feature_schema_version, bool) or self.feature_schema_version <= 0:
            raise ForecastError("feature_schema_version must be int > 0")
        if not isinstance(self.calculation_version, str) or not _HEX16.match(self.calculation_version):
            raise ForecastError("calculation_version must be 16 lowercase hex chars")
        if not isinstance(self.config_hash, str) or not _HEX64.match(self.config_hash):
            raise ForecastError("config_hash must be 64 lowercase hex chars")
        _nonblank(self.config_version, "config_version")
        _nonblank(self.code_version, "code_version")
        _nonblank(self.rule_version, "rule_version")
        object.__setattr__(self, "horizon_set", _string_sequence(self.horizon_set, "horizon_set"))
        object.__setattr__(self, "reasons", _string_sequence(self.reasons, "reasons"))
        if self.decision not in {"BULLISH", "BEARISH", "NO_TRADE"}:
            raise ForecastError("decision must be BULLISH, BEARISH, or NO_TRADE")
        if not isinstance(self.confidence, (int, float)) or isinstance(self.confidence, bool) or not math.isfinite(float(self.confidence)) or not (0.0 <= float(self.confidence) <= 1.0):
            raise ForecastError("confidence must be finite in [0, 1]")
        if not isinstance(self.final_score, (int, float)) or isinstance(self.final_score, bool) or not math.isfinite(float(self.final_score)):
            raise ForecastError("final_score must be finite")
        object.__setattr__(self, "confidence", float(self.confidence))
        object.__setattr__(self, "final_score", float(self.final_score))
