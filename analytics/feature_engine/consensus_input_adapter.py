"""Stage 2.1 consensus input adapter.

Builds one deterministic `ConsensusFeatureRequest` from caller-supplied
`ExchangeFeatureVector` objects plus an explicit replay denominator and explicit
exclusion reasons. It performs no I/O, reads no clock, and never infers the
expected exchange denominator from the current registry.
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Mapping, Sequence

from common.stage2_config import Stage2Config
from common.versioning import compute_calculation_version

from .consensus_models import ConsensusFeatureRequest, FAMILIES
from .models import ExchangeFeatureVector


class ConsensusInputError(ValueError):
    """Invalid consensus adapter input that must fail before computation/writes."""


def _nonblank(value, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConsensusInputError(f"{name} must be a non-empty string")
    return value


def _aware_datetime(value, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise ConsensusInputError(f"{name} must be a datetime, got {type(value).__name__}")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ConsensusInputError(f"{name} must be timezone-aware")
    return value


def _finite_positive(value, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConsensusInputError(f"{name} must be a number, got {type(value).__name__}")
    v = float(value)
    if not math.isfinite(v) or v <= 0:
        raise ConsensusInputError(f"{name} must be finite and > 0")
    return v


def _validate_family_maps(
    expected_exchanges_by_family: Mapping[str, Sequence[str]],
    exclusion_reasons_by_family: Mapping[str, Mapping[str, str]],
) -> None:
    if not isinstance(expected_exchanges_by_family, Mapping):
        raise ConsensusInputError("expected_exchanges_by_family must be a mapping")
    if set(expected_exchanges_by_family) != set(FAMILIES):
        raise ConsensusInputError(
            "expected_exchanges_by_family must contain exactly the consensus families")
    for family in FAMILIES:
        members = expected_exchanges_by_family[family]
        if isinstance(members, (str, bytes, bytearray)) or not isinstance(members, Sequence):
            raise ConsensusInputError(f"expected_exchanges_by_family[{family!r}] must be a sequence")
        for exchange in members:
            _nonblank(exchange, f"expected_exchanges_by_family[{family!r}] exchange")

    if not isinstance(exclusion_reasons_by_family, Mapping):
        raise ConsensusInputError("exclusion_reasons_by_family must be a mapping")
    for family, reasons in exclusion_reasons_by_family.items():
        if family not in FAMILIES:
            raise ConsensusInputError(f"unknown exclusion family {family!r}")
        if not isinstance(reasons, Mapping):
            raise ConsensusInputError(f"exclusion_reasons_by_family[{family!r}] must be a mapping")
        for exchange, reason in reasons.items():
            _nonblank(exchange, f"exclusion_reasons_by_family[{family!r}] exchange")
            _nonblank(reason, f"exclusion_reasons_by_family[{family!r}][{exchange!r}]")


def build_consensus_feature_request(
    stage2_config: Stage2Config,
    *,
    exchange_features: Sequence[ExchangeFeatureVector],
    expected_exchanges_by_family: Mapping[str, Sequence[str]],
    exclusion_reasons_by_family: Mapping[str, Mapping[str, str]],
    symbol: str,
    market_type: str,
    timeframe: str,
    bucket_ts: datetime,
    code_version: str,
) -> ConsensusFeatureRequest:
    """Build one immutable consensus request from explicit caller inputs."""
    if not isinstance(stage2_config, Stage2Config):
        raise ConsensusInputError("stage2_config must be a Stage2Config")
    if isinstance(exchange_features, (str, bytes, bytearray)) or not isinstance(exchange_features, Sequence):
        raise ConsensusInputError("exchange_features must be a sequence")
    for i, vector in enumerate(exchange_features):
        if type(vector) is not ExchangeFeatureVector:
            raise ConsensusInputError(
                f"exchange_features[{i}] must be exactly ExchangeFeatureVector, got {type(vector).__name__}")

    _nonblank(symbol, "symbol")
    _nonblank(market_type, "market_type")
    _nonblank(timeframe, "timeframe")
    _aware_datetime(bucket_ts, "bucket_ts")
    _nonblank(code_version, "code_version")
    _validate_family_maps(expected_exchanges_by_family, exclusion_reasons_by_family)

    resolved = stage2_config.resolve(symbol)
    config_hash = resolved.config_hash()
    feature_schema_version = stage2_config.feature_schema_version
    calculation_version = compute_calculation_version(
        feature_schema_version, config_hash, code_version)
    data_confidence = resolved["data_confidence"]

    return ConsensusFeatureRequest(
        symbol=symbol,
        market_type=market_type,
        timeframe=timeframe,
        bucket_ts=bucket_ts,
        feature_schema_version=feature_schema_version,
        calculation_version=calculation_version,
        config_hash=config_hash,
        config_version=stage2_config.config_version,
        code_version=code_version,
        exchange_features=tuple(exchange_features),
        expected_exchanges_by_family=expected_exchanges_by_family,
        exclusion_reasons_by_family=exclusion_reasons_by_family,
        minimum_exchange_coverage=data_confidence["minimum_exchange_coverage"],
        confidence_weights=data_confidence["weights"],
        robust_z_threshold=_finite_positive(
            resolved["outliers"]["robust_z_threshold"], "outliers.robust_z_threshold"),
    )
