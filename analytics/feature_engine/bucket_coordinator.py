"""
Stage 2.1 one-bucket coordinator (shadow-path infrastructure).

`process_stage2_bucket(...)` orchestrates a SINGLE already-selected, closed
Stage 2 bucket by composing the existing public pipelines:

    requested exchanges
      -> one exchange-feature pipeline call per exchange (sequential, one attempt)
      -> isolate per-exchange failures
      -> derive honest per-family exclusions from the public EFV fields
      -> one consensus pipeline call (unless zero exchanges succeeded)
      -> a typed, deeply-immutable Stage2BucketResult

It does NOT pick the time, find the latest bucket, loop/schedule/retry/sleep, use
`asyncio.gather`/background tasks, read env, resolve a code version, compute
percentiles / Data Quality / forecasts, initialize schema, or import a concrete
Database. The caller supplies every runtime/replay fact explicitly, and the
per-family expected denominator is exactly the caller's requested exchanges (it
never shrinks on failure and is never rebuilt from the registry or the successful
vectors). Stage 2 stays globally disabled; this explicit low-level operation is
not gated by `stage2.enabled`.

Only the internals of the composed pipelines own their semantics; this module
adds no forecast/signal logic and wraps no consensus-pipeline exception.
"""
from __future__ import annotations

from collections.abc import Mapping as _AbcMapping, Sequence as _AbcSequence
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Mapping, Optional, Sequence

from common.stage2_config import Stage2Config
from symbols.registry import ACTIVE_EXCHANGES

from .consensus_models import ConsensusFeatureVector, FAMILIES
from .consensus_pipeline import ConsensusFeatureWriter, process_consensus_feature_bucket
from .input_adapter import RawBundleReader, build_assembly_context
from .models import ExchangeFeatureVector
from .pipeline import ExchangeFeatureWriter, process_exchange_feature_bucket

# ---- stable exclusion reason taxonomy --------------------------------------
# Deliberately coarse: never claim STALE / LATE_BAR / NO_DATA when neither the
# EFV fields nor a caught exception prove it. Exception message text is never
# parsed to guess a reason.
EXCHANGE_PROCESSING_FAILED = "EXCHANGE_PROCESSING_FAILED"
BAR_DATA_UNUSABLE = "BAR_DATA_UNUSABLE"
METRIC_UNAVAILABLE = "METRIC_UNAVAILABLE"
LIQUIDATION_UNAVAILABLE = "LIQUIDATION_UNAVAILABLE"


class BucketCoordinatorError(ValueError):
    """Malformed coordinator arguments or invalid shared configuration detected
    BEFORE any I/O. Never used to wrap a consensus-pipeline exception, and never
    used to represent an isolated single-exchange failure."""


# ---- immutable result models -----------------------------------------------
@dataclass(frozen=True)
class ExchangeBucketFailure:
    """One isolated exchange-pipeline failure. Carries no exception object, no
    traceback, and no message text — only the canonical exchange, the stable
    reason, and `type(exc).__name__`."""
    exchange: str
    reason: str
    error_type: str


@dataclass(frozen=True)
class Stage2BucketResult:
    exchange_features: Sequence[ExchangeFeatureVector]
    consensus_feature: Optional[ConsensusFeatureVector]
    failures: Sequence[ExchangeBucketFailure]
    expected_exchanges_by_family: Mapping[str, Sequence[str]]
    exclusion_reasons_by_family: Mapping[str, Mapping[str, str]]

    def __post_init__(self):
        # Deeply freeze / detach from any caller-owned mutable container.
        object.__setattr__(self, "exchange_features", tuple(self.exchange_features))
        object.__setattr__(self, "failures", tuple(self.failures))
        object.__setattr__(
            self, "expected_exchanges_by_family",
            MappingProxyType({k: tuple(v)
                              for k, v in self.expected_exchanges_by_family.items()}))
        object.__setattr__(
            self, "exclusion_reasons_by_family",
            MappingProxyType({k: MappingProxyType(dict(v))
                              for k, v in self.exclusion_reasons_by_family.items()}))


# ---- per-family exclusion derivation (pure; never mutates the EFV) ---------
def _derive_family_exclusions(efv: ExchangeFeatureVector) -> dict[str, str]:
    """Return {family: reason} for exactly the families a successful EFV does NOT
    contribute to, mirroring the existing consensus contribution contract:
    `is_usable` gates ONLY the bar-derived families (price_structure/volume/
    taker_flow); oi/funding/liquidations depend solely on their own fields.
    Finiteness is NOT judged here — the consensus core stays authoritative."""
    out: dict[str, str] = {}

    # A. price_structure (bar-derived; is_usable gated)
    if not efv.is_usable:
        out["price_structure"] = BAR_DATA_UNUSABLE
    elif (efv.price_move_pct is None or efv.range_width_pct is None
          or efv.close_price is None):
        out["price_structure"] = METRIC_UNAVAILABLE

    # B. volume (bar-derived; is_usable gated)
    if not efv.is_usable:
        out["volume"] = BAR_DATA_UNUSABLE
    elif efv.volume_notional_usd is None:
        out["volume"] = METRIC_UNAVAILABLE

    # C. taker_flow (bar-derived; is_usable gated)
    if not efv.is_usable:
        out["taker_flow"] = BAR_DATA_UNUSABLE
    elif (efv.taker_buy_notional_usd is None or efv.taker_sell_notional_usd is None
          or efv.taker_delta_notional_usd is None or efv.cvd_delta_notional_usd is None):
        out["taker_flow"] = METRIC_UNAVAILABLE

    # D. oi (NOT is_usable gated)
    if efv.oi_change_pct is None:
        out["oi"] = METRIC_UNAVAILABLE

    # E. funding (NOT is_usable gated)
    if efv.funding_rate is None:
        out["funding"] = METRIC_UNAVAILABLE

    # F. liquidations (NOT is_usable gated; zero is a valid measurement)
    if (efv.long_liquidation_notional is None or efv.short_liquidation_notional is None
            or efv.liquidation_event_count is None):
        out["liquidations"] = LIQUIDATION_UNAVAILABLE

    return out


# ---- shared input validation (before any reader/writer call) ---------------
def _validate_shared_inputs(
    stage2_config, exchanges, symbol, market_type, timeframe, bucket_ts,
    code_version, liquidation_feed_available_by_exchange,
) -> tuple[str, ...]:
    if not isinstance(stage2_config, Stage2Config):
        raise BucketCoordinatorError(
            f"stage2_config must be a Stage2Config, got {type(stage2_config).__name__}")

    # exchanges: a real non-empty Sequence of canonical active names, no dupes.
    if isinstance(exchanges, (str, bytes, bytearray)) or not isinstance(exchanges, _AbcSequence):
        raise BucketCoordinatorError(
            f"exchanges must be a Sequence (list/tuple), not {type(exchanges).__name__}")
    if len(exchanges) == 0:
        raise BucketCoordinatorError("exchanges must be non-empty")
    seen: set[str] = set()
    for ex in exchanges:
        if not isinstance(ex, str) or ex not in ACTIVE_EXCHANGES:
            raise BucketCoordinatorError(
                f"exchange {ex!r} is not a canonical active exchange "
                f"{list(ACTIVE_EXCHANGES)}")
        if ex in seen:
            raise BucketCoordinatorError(f"duplicate exchange {ex!r}")
        seen.add(ex)
    exchanges = tuple(exchanges)   # preserve caller order, detached

    # liquidation availability: a Mapping whose keys EXACTLY equal the requested
    # exchange set, with strictly-bool values (no truthiness coercion).
    if not isinstance(liquidation_feed_available_by_exchange, _AbcMapping):
        raise BucketCoordinatorError(
            "liquidation_feed_available_by_exchange must be a mapping, got "
            f"{type(liquidation_feed_available_by_exchange).__name__}")
    keys = set(liquidation_feed_available_by_exchange)
    if keys != seen:
        missing = seen - keys
        extra = keys - seen
        raise BucketCoordinatorError(
            f"liquidation_feed_available_by_exchange keys must equal the requested "
            f"exchanges (missing={sorted(missing)}, extra={sorted(extra)})")
    for ex in exchanges:
        v = liquidation_feed_available_by_exchange[ex]
        if not isinstance(v, bool):
            raise BucketCoordinatorError(
                f"liquidation_feed_available_by_exchange[{ex!r}] must be a bool, "
                f"got {type(v).__name__}")

    # Reuse the pure exchange-context boundary for every requested exchange so
    # malformed shared identity/config fails loudly BEFORE any partial writes.
    for ex in exchanges:
        try:
            build_assembly_context(
                stage2_config, exchange=ex, symbol=symbol, market_type=market_type,
                timeframe=timeframe, bucket_ts=bucket_ts, code_version=code_version,
                liquidation_feed_available=liquidation_feed_available_by_exchange[ex])
        except Exception as exc:  # noqa: BLE001 - convert to a coordinator arg error
            raise BucketCoordinatorError(
                f"invalid shared bucket context for exchange {ex!r}: {exc}") from exc

    return exchanges


# ---- public coordinator ----------------------------------------------------
async def process_stage2_bucket(
    reader: RawBundleReader,
    exchange_writer: ExchangeFeatureWriter,
    consensus_writer: ConsensusFeatureWriter,
    stage2_config: Stage2Config,
    *,
    exchanges: Sequence[str],
    symbol: str,
    market_type: str,
    timeframe: str,
    bucket_ts: datetime,
    code_version: str,
    liquidation_feed_available_by_exchange: Mapping[str, bool],
) -> Stage2BucketResult:
    """Coordinate exactly one closed Stage 2 bucket. See module docstring."""
    exchanges = _validate_shared_inputs(
        stage2_config, exchanges, symbol, market_type, timeframe, bucket_ts,
        code_version, liquidation_feed_available_by_exchange)

    # Explicit replay denominator: ALL requested exchanges, every family, in the
    # canonical FAMILIES order. Never shrinks on failure; never registry-derived.
    expected_exchanges_by_family: dict[str, tuple[str, ...]] = {
        family: exchanges for family in FAMILIES
    }
    exclusion_reasons_by_family: dict[str, dict[str, str]] = {
        family: {} for family in FAMILIES
    }

    successful: list[ExchangeFeatureVector] = []
    failures: list[ExchangeBucketFailure] = []

    # Sequential, exactly one attempt per exchange, caller order preserved.
    for ex in exchanges:
        try:
            efv = await process_exchange_feature_bucket(
                reader, exchange_writer, stage2_config,
                exchange=ex, symbol=symbol, market_type=market_type,
                timeframe=timeframe, bucket_ts=bucket_ts, code_version=code_version,
                liquidation_feed_available=liquidation_feed_available_by_exchange[ex])
        except Exception as exc:  # noqa: BLE001 - isolate ordinary per-exchange failures only
            failures.append(ExchangeBucketFailure(
                exchange=ex, reason=EXCHANGE_PROCESSING_FAILED,
                error_type=type(exc).__name__))
            for family in FAMILIES:
                exclusion_reasons_by_family[family][ex] = EXCHANGE_PROCESSING_FAILED
            continue
        successful.append(efv)
        for family, reason in _derive_family_exclusions(efv).items():
            exclusion_reasons_by_family[family][ex] = reason

    consensus_feature: Optional[ConsensusFeatureVector] = None
    if successful:
        # Consensus adapter/core/writer exceptions propagate UNCHANGED.
        consensus_feature = await process_consensus_feature_bucket(
            consensus_writer, stage2_config,
            exchange_features=successful,
            expected_exchanges_by_family=expected_exchanges_by_family,
            exclusion_reasons_by_family=exclusion_reasons_by_family)

    return Stage2BucketResult(
        exchange_features=successful,
        consensus_feature=consensus_feature,
        failures=failures,
        expected_exchanges_by_family=expected_exchanges_by_family,
        exclusion_reasons_by_family=exclusion_reasons_by_family,
    )
