"""
Stage 2.1 Level B consensus input adapter: assemble ONE valid, deterministic
`ConsensusFeatureRequest` from a bucket's already-computed per-exchange
`ExchangeFeatureVector`s plus the caller's explicit replay/runtime denominator
facts.

PURE: no DB, network, asyncio, clock, env, subprocess, filesystem, or mutable
module state. Same logical input -> equal request. The global `stage2.enabled`
master switch does NOT gate this explicit low-level function.

The first `ExchangeFeatureVector` is authoritative for identity
(`symbol`/`market_type`/`timeframe`/`bucket_ts`) and `code_version`; the version
fields (`feature_schema_version`/`config_hash`/`config_version`/
`calculation_version`) are DERIVED from the resolved Stage 2 config — never
trusted from an EFV — and every EFV must then match them exactly, so an
inconsistent config/calculation version can never be smuggled in through a row.

The per-family expected exchange sets and exclusion reasons are caller-owned
replay facts: they are preserved verbatim and NEVER inferred from the present
contributors or the live registry (the frozen replay-denominator contract).
"""
from __future__ import annotations

from collections.abc import Mapping as _AbcMapping, Sequence as _AbcSequence
from typing import Mapping, Sequence

from common.stage2_config import Stage2Config, Stage2ConfigError
from common.versioning import compute_calculation_version

from .consensus_models import ConsensusFeatureRequest
from .models import ExchangeFeatureVector

# Identity/version fields every EFV must match against the derived authoritative
# values before the consensus core is ever called.
_EFV_MATCH_FIELDS = (
    "symbol", "market_type", "timeframe", "bucket_ts", "code_version",
    "feature_schema_version", "config_hash", "config_version", "calculation_version",
)


class ConsensusInputError(ValueError):
    """Invalid consensus-adapter input that must fail loudly (never silently
    coerced, inferred, dropped, or defaulted). Raised before the consensus core
    is called."""


# ---- small structural validators (container-shape only) --------------------
def _require_mapping(obj, name: str) -> Mapping:
    if not isinstance(obj, _AbcMapping):
        raise ConsensusInputError(f"{name} must be a mapping, got {type(obj).__name__}")
    return obj


def _require_exchange_name_sequence(obj, name: str) -> None:
    if isinstance(obj, (str, bytes, bytearray)) or not isinstance(obj, _AbcSequence):
        raise ConsensusInputError(
            f"{name} must be a sequence of exchange names, got {type(obj).__name__}")


# ---- public entry point ----------------------------------------------------
def build_consensus_feature_request(
    stage2_config: Stage2Config,
    *,
    exchange_features: Sequence[ExchangeFeatureVector],
    expected_exchanges_by_family: Mapping[str, Sequence[str]],
    exclusion_reasons_by_family: Mapping[str, Mapping[str, str]],
) -> ConsensusFeatureRequest:
    """Build one `ConsensusFeatureRequest` for a single bucket. Pure; the caller
    owns the expected/exclusion denominator facts (preserved verbatim)."""
    if not isinstance(stage2_config, Stage2Config):
        raise ConsensusInputError(
            f"stage2_config must be a Stage2Config, got {type(stage2_config).__name__}")

    # --- exchange_features container: a real non-empty Sequence of EFVs -------
    if isinstance(exchange_features, (str, bytes, bytearray)) \
            or not isinstance(exchange_features, _AbcSequence):
        raise ConsensusInputError(
            f"exchange_features must be a Sequence (list/tuple), "
            f"not {type(exchange_features).__name__}")
    if len(exchange_features) == 0:
        raise ConsensusInputError("exchange_features must contain at least one item")
    for i, efv in enumerate(exchange_features):
        if type(efv) is not ExchangeFeatureVector:
            raise ConsensusInputError(
                f"exchange_features[{i}] must be an ExchangeFeatureVector, "
                f"got {type(efv).__name__}")

    # --- authoritative identity from the FIRST vector ------------------------
    first = exchange_features[0]
    symbol = first.symbol
    market_type = first.market_type
    timeframe = first.timeframe
    bucket_ts = first.bucket_ts
    code_version = first.code_version

    # --- resolve config + enablement/support (NOT the global master switch) ---
    if not isinstance(symbol, str):
        raise ConsensusInputError(
            f"first exchange_features symbol must be a string, got {type(symbol).__name__}")
    try:
        resolved = stage2_config.resolve(symbol)
    except Stage2ConfigError as exc:
        raise ConsensusInputError(f"cannot resolve symbol {symbol!r}: {exc}") from exc
    if resolved.enabled is not True:
        raise ConsensusInputError(f"symbol {symbol!r} is disabled in the resolved config")
    if market_type not in resolved.market_types:
        raise ConsensusInputError(
            f"market_type {market_type!r} not supported for {symbol!r} "
            f"(resolved: {list(resolved.market_types)})")
    if timeframe not in resolved["timeframes"]:
        raise ConsensusInputError(
            f"timeframe {timeframe!r} not enabled for {symbol!r} "
            f"(resolved: {list(resolved['timeframes'])})")

    # --- DERIVE authoritative version fields (never trust an EFV for these) ---
    config_hash = resolved.config_hash()
    config_version = stage2_config.config_version
    feature_schema_version = stage2_config.feature_schema_version
    calculation_version = compute_calculation_version(
        feature_schema_version, config_hash, code_version)

    authoritative = {
        "symbol": symbol, "market_type": market_type, "timeframe": timeframe,
        "bucket_ts": bucket_ts, "code_version": code_version,
        "feature_schema_version": feature_schema_version, "config_hash": config_hash,
        "config_version": config_version, "calculation_version": calculation_version,
    }

    # --- every EFV must match ALL authoritative identity/version fields -------
    for i, efv in enumerate(exchange_features):
        mismatch = [f for f in _EFV_MATCH_FIELDS
                    if getattr(efv, f) != authoritative[f]]
        if mismatch:
            raise ConsensusInputError(
                f"exchange_features[{i}] (exchange={efv.exchange!r}) mismatches the "
                f"authoritative identity/version on {mismatch}")

    # --- caller-owned denominator facts: structural shape only, preserved -----
    _require_mapping(expected_exchanges_by_family, "expected_exchanges_by_family")
    for family, members in expected_exchanges_by_family.items():
        _require_exchange_name_sequence(
            members, f"expected_exchanges_by_family[{family!r}]")
    _require_mapping(exclusion_reasons_by_family, "exclusion_reasons_by_family")
    for family, reasons in exclusion_reasons_by_family.items():
        _require_mapping(reasons, f"exclusion_reasons_by_family[{family!r}]")

    # --- resolved consensus thresholds (config-owned) ------------------------
    data_confidence = _require_mapping(
        resolved["data_confidence"], "resolved data_confidence")
    minimum_exchange_coverage = data_confidence["minimum_exchange_coverage"]
    confidence_weights = data_confidence["weights"]
    robust_z_threshold = resolved["outliers"]["robust_z_threshold"]

    # ConsensusFeatureRequest deep-freezes every nested container in __post_init__
    # (a copy), so no input object is mutated. Full semantic validation (family
    # completeness, membership, contribution, weight sum, …) is owned by the core.
    return ConsensusFeatureRequest(
        symbol=symbol, market_type=market_type, timeframe=timeframe,
        bucket_ts=bucket_ts, feature_schema_version=feature_schema_version,
        calculation_version=calculation_version, config_hash=config_hash,
        config_version=config_version, code_version=code_version,
        exchange_features=exchange_features,
        expected_exchanges_by_family=expected_exchanges_by_family,
        exclusion_reasons_by_family=exclusion_reasons_by_family,
        minimum_exchange_coverage=minimum_exchange_coverage,
        confidence_weights=confidence_weights,
        robust_z_threshold=robust_z_threshold,
    )
