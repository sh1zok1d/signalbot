"""Frozen inputs for the free-day overlap audit.

Numeric readings of the qualitative acceptance principles live here so they
are declared with the tooling, not chosen after an aggregate is inspected.
This run does not apply them to a gold comparison: no Signalbot export was
available.
"""
from __future__ import annotations

from dataclasses import dataclass

URL_PATTERN = (
    "https://datasets.tardis.dev/v1/{tardis_exchange}/{data_type}/"
    "{year}/{month}/{day}/{tardis_symbol}.csv.gz"
)
SAMPLE_DATES = ("2026-08-01", "2026-09-01")
DATA_TYPES = ("derivative_ticker", "trades")
CANONICAL_SYMBOL = "BTCUSDT"
MARKET_TYPE = "perp"
TIMEFRAME = "5m"
BUCKET_MINUTES = 5

TRADE_COLUMNS = (
    "exchange", "symbol", "timestamp", "local_timestamp", "id", "side",
    "price", "amount",
)
DERIVATIVE_TICKER_COLUMNS = (
    "exchange", "symbol", "timestamp", "local_timestamp", "funding_timestamp",
    "funding_rate", "predicted_funding_rate", "open_interest", "last_price",
    "index_price", "mark_price",
)

# Tardis docs: side is the liquidity taker (aggressor).
# buy  -> taker was buying  -> LiveBarBuilder is_buyer_maker False
# sell -> taker was selling -> LiveBarBuilder is_buyer_maker True
# unknown -> taker split fail-closed for that minute (not guessed, not flipped)
TAKER_SIDE_BUY = "buy"
TAKER_SIDE_SELL = "sell"
TAKER_SIDE_UNKNOWN = "unknown"

VENDOR_GAP_TAG = "VENDOR_DOCUMENTED_GAP"
SIGNALBOT_GAP_TAG = "SIGNALBOT_DATA_GAP"

# Pre-declared principle readings. Not fitted to overlap aggregates.
SCALE_RATIO_ACCEPT_MIN = 0.5
SCALE_RATIO_ACCEPT_MAX = 2.0
# A median ratio within 1% of one of these is a metadata scale bug.
SCALE_SUSPECT_RATIOS = (0.001, 0.01, 0.1, 10.0, 100.0, 1000.0)
SCALE_SUSPECT_RELATIVE_TOLERANCE = 0.01
EVALUABILITY_DISAGREEMENT_FRACTION_MAX = 0.05
QUORUM_DISAGREEMENT_FRACTION_MAX = 0.05
RANK_CORRELATION_MIN = 0.90
OI_SIGN_AGREEMENT_MIN_OUTSIDE_LOWEST_DECILE = 0.90
OI_STRATUM_MIN_PAIRS = 20
TAKER_INVERSION_SIGN_AGREEMENT_MAX = 0.50
MATERIAL_FEATURE_MIN_PAIRS = 20


@dataclass(frozen=True)
class VenueMap:
    """Explicit venue identity. Symbols are never joined by string similarity."""

    signalbot_exchange: str
    canonical_symbol: str
    tardis_exchange: str
    tardis_symbol: str
    quantity_unit: str
    oi_unit: str
    # None means the audit must not invent a multiplier. OKX notional is
    # fail-closed until a PIT row from the Signalbot export supplies ctVal.
    contract_multiplier: float | None


VENUES: tuple[VenueMap, ...] = (
    VenueMap(
        signalbot_exchange="binance",
        canonical_symbol="BTCUSDT",
        tardis_exchange="binance-futures",
        tardis_symbol="BTCUSDT",
        quantity_unit="base",
        oi_unit="base",
        contract_multiplier=None,
    ),
    VenueMap(
        signalbot_exchange="bybit",
        canonical_symbol="BTCUSDT",
        tardis_exchange="bybit",
        tardis_symbol="BTCUSDT",
        quantity_unit="base",
        oi_unit="base",
        contract_multiplier=None,
    ),
    VenueMap(
        signalbot_exchange="okx",
        canonical_symbol="BTCUSDT",
        tardis_exchange="okex-swap",
        tardis_symbol="BTC-USDT-SWAP",
        quantity_unit="contracts",
        oi_unit="contracts",
        contract_multiplier=None,
    ),
)

VENUE_BY_SIGNALBOT = {v.signalbot_exchange: v for v in VENUES}
VENUE_BY_TARDIS = {(v.tardis_exchange, v.tardis_symbol): v for v in VENUES}


def file_url(venue: VenueMap, data_type: str, sample_date: str) -> str:
    year, month, day = sample_date.split("-")
    return URL_PATTERN.format(
        tardis_exchange=venue.tardis_exchange,
        data_type=data_type,
        year=year,
        month=month,
        day=day,
        tardis_symbol=venue.tardis_symbol,
    )


def vendor_filename(venue: VenueMap, data_type: str, sample_date: str) -> str:
    ymd = sample_date.replace("-", "")
    return (
        f"{venue.tardis_exchange}_{data_type}_{ymd}_{venue.tardis_symbol}.csv.gz"
    )
