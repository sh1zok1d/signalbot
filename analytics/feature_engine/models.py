"""
Typed, immutable input/output models for Stage 2.1 per-exchange feature
computation. Pure data only — no DB, no network, no clock.

The ExchangeFeatureVector field set mirrors the current
storage/stage2_schema.sql `exchange_feature_vectors` table EXCEPT `computed_at`
(wall-clock metadata filled by the DB default / writer later). No invented
columns.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Sequence

from common.instrument_metadata import InstrumentMetadata

# Supported dimensions for this phase.
SUPPORTED_MARKET_TYPES = ("perp",)
TIMEFRAME_MINUTES = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240}
LIQUIDATION_COVERAGE_TYPES = ("full", "snapshot", "aggregated", "unavailable")
LIQUIDATION_SIDES = ("long", "short")


# ---- inputs ----------------------------------------------------------------
@dataclass(frozen=True)
class KlineBar:
    ts: datetime                       # bucket-of-1m start, tz-aware UTC
    open: float
    high: float
    low: float
    close: float
    volume: float
    # Stage 1 stores these as SEPARATE nullable columns; a split exists only
    # when BOTH are present. Never synthesize sell = volume - buy.
    taker_buy_volume: Optional[float] = None
    taker_sell_volume: Optional[float] = None


@dataclass(frozen=True)
class OpenInterestObservation:
    ts: datetime
    oi_raw: float
    oi_unit: str                       # 'base' | 'contracts'


@dataclass(frozen=True)
class FundingObservation:
    ts: datetime
    funding_rate: float


@dataclass(frozen=True)
class LiquidationEvent:
    ts: datetime
    side: str                          # 'long' | 'short'
    notional: float


@dataclass(frozen=True)
class LiquidationFeedState:
    is_available: bool
    coverage_type: str                 # full | snapshot | aggregated | unavailable
    is_snapshot_feed: bool


@dataclass(frozen=True)
class ExchangeFeatureRequest:
    exchange: str
    symbol: str                        # canonical, e.g. BTCUSDT
    market_type: str
    timeframe: str
    bucket_ts: datetime                # bucket start, tz-aware UTC
    feature_schema_version: int
    calculation_version: str
    config_hash: str
    config_version: str
    code_version: str
    bars: Sequence[KlineBar]
    open_interest: Sequence[OpenInterestObservation]
    funding: Sequence[FundingObservation]
    liquidations: Sequence[LiquidationEvent]
    liquidation_feed_state: LiquidationFeedState
    instrument_metadata: Optional[InstrumentMetadata]
    allowed_missing_bars: int

    def __post_init__(self):
        # Freeze the sequence fields into tuples so the request is fully
        # immutable and the caller's lists can never be mutated through us.
        object.__setattr__(self, "bars", tuple(self.bars))
        object.__setattr__(self, "open_interest", tuple(self.open_interest))
        object.__setattr__(self, "funding", tuple(self.funding))
        object.__setattr__(self, "liquidations", tuple(self.liquidations))


# ---- output ----------------------------------------------------------------
@dataclass(frozen=True)
class ExchangeFeatureVector:
    # identity
    exchange: str
    symbol: str
    market_type: str
    timeframe: str
    bucket_ts: datetime
    feature_schema_version: int
    calculation_version: str

    # price / structure
    price_move_pct: Optional[float]
    range_width_pct: Optional[float]
    close_price: Optional[float]

    # volume / flow (unit-safe)
    volume_raw: Optional[float]
    volume_raw_unit: Optional[str]
    volume_notional_usd: Optional[float]
    taker_buy_notional_usd: Optional[float]
    taker_sell_notional_usd: Optional[float]
    taker_delta_notional_usd: Optional[float]
    cvd_delta_notional_usd: Optional[float]

    # derivatives
    oi_change_pct: Optional[float]
    oi_unit: Optional[str]
    funding_rate: Optional[float]

    # liquidations
    long_liquidation_notional: Optional[float]
    short_liquidation_notional: Optional[float]
    liquidation_event_count: Optional[int]
    liquidation_feed_quality: str
    is_snapshot_feed: bool

    # per-exchange data quality for this bucket
    bars_expected: int
    bars_present: int
    has_gap: bool
    is_usable: bool

    # provenance (computed_at intentionally omitted — DB default/writer)
    config_hash: str
    config_version: str
    code_version: str
