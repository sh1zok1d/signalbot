"""
Immutable input/output models for Stage 2.1 Level B consensus computation
(Consensus Contract Revision 0.2.3, docs/STAGE2_SPEC.md §11).

Pure data only — no DB, no network, no clock. Nested request/output structures
are deeply frozen (tuples + MappingProxyType + frozen dataclasses) so neither a
caller's inputs nor a returned vector can be mutated through us.

`ConsensusFeatureVector`'s field set mirrors the `consensus_feature_vectors`
columns in storage/stage2_schema.sql EXCEPT `computed_at` (DB default / writer).
No invented columns.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Mapping, Optional, Sequence

from .models import ExchangeFeatureVector

# The six metric families, in canonical order (spec §2 / §11).
FAMILIES: tuple[str, ...] = (
    "price_structure", "volume", "taker_flow", "oi", "funding", "liquidations",
)

# Applicable Data-Confidence components per family (§11.4).
APPLICABLE_COMPONENTS: dict[str, tuple[str, ...]] = {
    "price_structure": ("coverage", "agreement", "dispersion"),
    "volume":          ("coverage",),
    "taker_flow":      ("coverage", "agreement", "dispersion"),
    "oi":              ("coverage", "agreement", "dispersion"),
    "funding":         ("coverage", "dispersion"),
    "liquidations":    ("coverage",),
}

CONFIDENCE_WEIGHT_KEYS: tuple[str, ...] = ("coverage", "agreement", "dispersion")

# Robust-z scale constant — a FIXED part of Revision 0.2.3, never config (§11.5).
ROBUST_Z_SCALE = 0.6744897501960817

OUTLIER_REASON_THRESHOLD = "ROBUST_Z_THRESHOLD"
OUTLIER_REASON_MAD_ZERO = "MAD_ZERO_NONMEDIAN"


class ConsensusError(ValueError):
    """Invalid consensus request / input that must fail loudly (never silently
    coerced, dropped, defaulted, or guessed)."""


# ---- frozen JSONB-ready entries --------------------------------------------
@dataclass(frozen=True)
class CoverageEntry:
    available: int
    expected: int
    ratio: float


@dataclass(frozen=True)
class ProvenanceEntry:
    # Deterministically ordered: contributing sorted; excluded as sorted
    # (exchange, reason) pairs.
    contributing: tuple[str, ...]
    excluded: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class OutlierEntry:
    robust_z: Optional[float]     # None only for the MAD==0 non-median case
    reason: str


def _freeze_str_seq(seq: Sequence[str]) -> tuple[str, ...]:
    return tuple(seq)


def _freeze_expected(m: Mapping[str, Sequence[str]]) -> Mapping[str, tuple[str, ...]]:
    return MappingProxyType({str(k): tuple(v) for k, v in m.items()})


def _freeze_reason_map(m: Mapping[str, Mapping[str, str]]
                       ) -> Mapping[str, Mapping[str, str]]:
    return MappingProxyType(
        {str(k): MappingProxyType(dict(v)) for k, v in m.items()})


def _freeze_weights(m: Mapping[str, float]) -> Mapping[str, float]:
    return MappingProxyType(dict(m))


# ---- request ---------------------------------------------------------------
@dataclass(frozen=True)
class ConsensusFeatureRequest:
    # identity / version
    symbol: str
    market_type: str
    timeframe: str
    bucket_ts: datetime
    feature_schema_version: int
    calculation_version: str
    config_hash: str
    config_version: str
    code_version: str

    # per-exchange inputs for THIS bucket (<= 1 per exchange)
    exchange_features: Sequence[ExchangeFeatureVector]

    # explicit, replay-safe denominator + provenance (never recomputed from the
    # live registry): family -> expected exchange set, family -> {exchange: reason}
    expected_exchanges_by_family: Mapping[str, Sequence[str]]
    exclusion_reasons_by_family: Mapping[str, Mapping[str, str]]

    # resolved-config parameters (part of config_hash / calculation_version)
    minimum_exchange_coverage: int
    confidence_weights: Mapping[str, float]
    robust_z_threshold: float

    def __post_init__(self):
        # Deep-freeze every nested container so the request is fully immutable
        # and the caller's originals can never be mutated through us.
        object.__setattr__(self, "exchange_features", tuple(self.exchange_features))
        object.__setattr__(self, "expected_exchanges_by_family",
                           _freeze_expected(self.expected_exchanges_by_family))
        object.__setattr__(self, "exclusion_reasons_by_family",
                           _freeze_reason_map(self.exclusion_reasons_by_family))
        object.__setattr__(self, "confidence_weights",
                           _freeze_weights(self.confidence_weights))


# ---- output ----------------------------------------------------------------
@dataclass(frozen=True)
class ConsensusFeatureVector:
    # identity / version
    symbol: str
    market_type: str
    timeframe: str
    bucket_ts: datetime
    feature_schema_version: int
    calculation_version: str

    # per-family maps
    coverage_by_metric: Mapping[str, CoverageEntry]
    provenance_by_metric: Mapping[str, ProvenanceEntry]
    data_confidence_by_metric: Mapping[str, float]

    # rolled-up reporting
    exchanges_expected_max: int
    min_coverage_ratio: Optional[float]
    data_confidence_overall: Optional[float]

    # direction agreement (0..1 or None)
    price_direction_agreement: Optional[float]
    flow_direction_agreement: Optional[float]
    oi_direction_agreement: Optional[float]

    # robust aggregates of normalized values
    price_move_pct_median: Optional[float]
    range_width_pct_median: Optional[float]
    oi_change_pct_median: Optional[float]
    funding_rate_median: Optional[float]
    funding_rate_mad: Optional[float]

    # additive notional sums
    volume_notional_usd_sum: Optional[float]
    taker_buy_notional_usd_sum: Optional[float]
    taker_sell_notional_usd_sum: Optional[float]
    taker_delta_notional_usd_sum: Optional[float]
    cvd_delta_notional_usd_sum: Optional[float]

    # liquidation provenance (lower bounds) + per-exchange feed quality
    observed_long_liquidation_notional_sum: Optional[float]
    observed_short_liquidation_notional_sum: Optional[float]
    observed_liquidation_event_count_sum: Optional[int]
    liquidation_feed_quality_by_exchange: Mapping[str, str]

    # dispersion / outliers
    price_move_pct_mad: Optional[float]
    oi_change_pct_mad: Optional[float]
    outlier_exchanges: Mapping[str, Mapping[str, OutlierEntry]]

    # confidence
    consensus_confidence: Optional[float]
    is_partial_consensus: bool

    # provenance (computed_at intentionally omitted — DB default/writer)
    config_hash: str
    config_version: str
    code_version: str
