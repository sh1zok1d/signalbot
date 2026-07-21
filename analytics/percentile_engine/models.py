"""
Immutable input/output models for the Stage 2.1 Percentile Engine core
(Percentile Contract Revision 0.2.4, docs/STAGE2_SPEC.md §12).

Pure data only — no DB, no network, no clock. Nested structures are deeply
frozen (tuples + frozen dataclasses). `PercentileSnapshot`'s field set mirrors
the `percentile_snapshots` columns in storage/stage2_schema.sql EXCEPT
`computed_at` (DB default / writer). No invented columns.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Mapping, Optional, Sequence

# ---- frozen constants (§12.2 / §12.3 / §12.4 / §12.6) ----------------------
VALID_SCOPES: tuple[str, ...] = ("exchange", "consensus")
VALID_WINDOWS: tuple[str, ...] = ("7d", "30d")
WINDOW_TIMEDELTAS: Mapping[str, timedelta] = MappingProxyType({
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
})
CONFIDENCE_TIERS: tuple[str, ...] = ("none", "low", "building", "mature")

# Metric keys are the exact source-column / feature-vector field names (§12.4).
EXCHANGE_SCOPE_METRICS: tuple[str, ...] = (
    "price_move_pct", "range_width_pct", "volume_notional_usd",
    "taker_buy_notional_usd", "taker_sell_notional_usd", "taker_delta_notional_usd",
    "cvd_delta_notional_usd", "oi_change_pct", "funding_rate",
    "long_liquidation_notional", "short_liquidation_notional",
    "liquidation_event_count",
)
CONSENSUS_SCOPE_METRICS: tuple[str, ...] = (
    "price_move_pct_median", "range_width_pct_median", "oi_change_pct_median",
    "funding_rate_median", "volume_notional_usd_sum", "taker_buy_notional_usd_sum",
    "taker_sell_notional_usd_sum", "taker_delta_notional_usd_sum",
    "cvd_delta_notional_usd_sum", "observed_long_liquidation_notional_sum",
    "observed_short_liquidation_notional_sum", "observed_liquidation_event_count_sum",
)
METRICS_BY_SCOPE: Mapping[str, frozenset] = MappingProxyType({
    "exchange": frozenset(EXCHANGE_SCOPE_METRICS),
    "consensus": frozenset(CONSENSUS_SCOPE_METRICS),
})


class PercentileError(ValueError):
    """Invalid percentile request / input that must fail loudly (never silently
    coerced, dropped, filtered, or defaulted)."""


# ---- config value object ---------------------------------------------------
@dataclass(frozen=True)
class ConfidenceTierThresholds:
    """Span-day thresholds (§12.6/§12.8): three ints, each > 0, strictly
    increasing. Validated at construction."""
    none_below_days: int
    low_below_days: int
    building_below_days: int

    def __post_init__(self):
        vals = (self.none_below_days, self.low_below_days, self.building_below_days)
        names = ("none_below_days", "low_below_days", "building_below_days")
        for name, v in zip(names, vals):
            if not isinstance(v, int) or isinstance(v, bool) or v <= 0:
                raise PercentileError(f"{name} must be an int > 0, got {v!r}")
        if not (vals[0] < vals[1] < vals[2]):
            raise PercentileError(
                f"confidence-tier thresholds must be strictly increasing "
                f"(none_below < low_below < building_below), got {list(vals)}")


# ---- inputs ----------------------------------------------------------------
@dataclass(frozen=True)
class PercentileSample:
    """One earlier observation, carrying the full identity needed for fail-loud
    validation (§12.3) — never omitted just because a DB query would pre-filter."""
    scope: str
    exchange: str
    symbol: str
    market_type: str
    metric: str
    timeframe: str
    bucket_ts: datetime
    value: Optional[float]
    feature_schema_version: int
    calculation_version: str


@dataclass(frozen=True)
class PercentileRequest:
    scope: str
    exchange: str                  # '' for consensus scope
    symbol: str
    market_type: str
    metric: str
    timeframe: str
    percentile_window: str         # '7d' | '30d'
    bucket_ts: datetime
    value: Optional[float]         # current bucket's metric value (nullable)
    samples: Sequence[PercentileSample]
    confidence_tier_thresholds: ConfidenceTierThresholds
    config_hash: str
    config_version: str
    code_version: str
    feature_schema_version: int
    calculation_version: str

    def __post_init__(self):
        # Freeze the sample sequence so the request is fully immutable and the
        # caller's list can never be mutated through us.
        object.__setattr__(self, "samples", tuple(self.samples))


# ---- output ----------------------------------------------------------------
@dataclass(frozen=True)
class PercentileSnapshot:
    # identity / version
    scope: str
    exchange: str
    symbol: str
    market_type: str
    metric: str
    timeframe: str
    percentile_window: str
    bucket_ts: datetime

    # computed result
    value: Optional[float]
    percentile_rank: Optional[float]
    sample_size: int
    sample_window_start: Optional[datetime]
    sample_window_end: Optional[datetime]
    confidence_tier: str

    # provenance (computed_at intentionally omitted — DB default/writer)
    config_hash: str
    config_version: str
    code_version: str
    feature_schema_version: int
    calculation_version: str
