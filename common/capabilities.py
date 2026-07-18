"""
Structural exchange x metric capability registry — the single declarative
source of truth for "what can each exchange actually provide, per metric".

WHY THIS EXISTS: the spec's hard rules (min 3 exchanges for price/OI/order
flow, count_only_valid_sources, coverage shown separately) must be enforceable
from DATA, not by reading the WS client classes. This module is plain data;
storage/db.py seeds it into the `exchange_capabilities` table at startup, and
validate.py / the future signal_engine query that TABLE. Nothing downstream
should import the client classes to discover capabilities.

Fields per (exchange, metric):
  live_supported        - a live feed for this metric exists at all
  historical_supported  - a REST endpoint lets us backfill 30d of it
  coverage_type         - full | snapshot | aggregated | unavailable
                          full       = complete real-time/near-real-time feed
                          snapshot   = rate-capped/under-counts (Binance forceOrder)
                          aggregated = batched/delayed (OKX liquidation-orders)
                          unavailable= no usable public feed at all
  expected_freshness_s  - how old the newest row may be before we call it stale;
                          None for event-driven metrics (liquidations are
                          sporadic — absence is not staleness)
  note                  - short human explanation

IMPORTANT: this describes STRUCTURAL capability of each exchange's public API,
not the current runtime/network state, and not whether the exchange is ACTIVE.
Whether an exchange participates in the MVP is a separate `enabled` flag on the
exchange_capabilities table, seeded from config.enabled_exchanges at startup
(e.g. Bitget is structurally capable but enabled=False in the 3-exchange MVP).
The signal_engine reads `enabled AND live_supported` — a disabled exchange is
excluded from coverage and percentile voting regardless of its capability.
"""
from __future__ import annotations

# Metric keys line up with the storage tables / feeds they describe.
METRICS = ("ohlcv", "taker_flow", "open_interest", "funding", "mark_price", "liquidations")

# Freshness budgets (seconds). Live 1m bars close each minute; polled metrics
# use a 15s poll cadence (see clients) so ~60s is a comfortable stale bound.
_FRESH_BAR = 120
_FRESH_POLL = 60

# Each row: exchange, metric, live, historical, coverage_type, freshness_s, note
CAPABILITIES: list[tuple] = [
    # ---------------- Binance ----------------
    ("binance", "ohlcv",         True,  True,  "full",        _FRESH_BAR,  ""),
    # Binance is the only exchange whose historical klines carry a taker split.
    ("binance", "taker_flow",    True,  True,  "full",        _FRESH_BAR,  "historical taker split available (kline field)"),
    ("binance", "open_interest", True,  True,  "full",        _FRESH_POLL, "openInterestHist retention ~29d23h, shorter than 30d"),
    ("binance", "funding",       True,  True,  "full",        _FRESH_POLL, ""),
    ("binance", "mark_price",    True,  True,  "full",        _FRESH_POLL, ""),
    ("binance", "liquidations",  True,  False, "snapshot",    None,        "forceOrder is a 1/1000ms snapshot feed; under-counts cascades; never backfilled"),

    # ---------------- Bybit ----------------
    ("bybit",   "ohlcv",         True,  True,  "full",        _FRESH_BAR,  ""),
    ("bybit",   "taker_flow",    True,  False, "full",        _FRESH_BAR,  "live taker split from trades; no historical split in klines"),
    ("bybit",   "open_interest", True,  True,  "full",        _FRESH_POLL, ""),
    ("bybit",   "funding",       True,  True,  "full",        _FRESH_POLL, ""),
    ("bybit",   "mark_price",    True,  True,  "full",        _FRESH_POLL, "historical via mark-price-kline"),
    ("bybit",   "liquidations",  True,  False, "full",        None,        "allLiquidation real-time feed; never backfilled"),

    # ---------------- OKX ----------------
    ("okx",     "ohlcv",         True,  True,  "full",        _FRESH_BAR,  "historical paged 100/req"),
    ("okx",     "taker_flow",    True,  False, "full",        _FRESH_BAR,  "live taker split from trades; no historical split"),
    ("okx",     "open_interest", True,  False, "full",        _FRESH_POLL, "live REST poll only; no verified 30d historical OI endpoint"),
    ("okx",     "funding",       True,  True,  "full",        _FRESH_POLL, ""),
    ("okx",     "mark_price",    True,  True,  "full",        _FRESH_POLL, ""),
    ("okx",     "liquidations",  True,  False, "aggregated",  None,        "business-WS liquidation-orders is aggregated/delayed; never backfilled"),

    # ---------------- Bitget ----------------
    ("bitget",  "ohlcv",         True,  True,  "full",        _FRESH_BAR,  "historical via history-candles (200/req)"),
    ("bitget",  "taker_flow",    True,  False, "full",        _FRESH_BAR,  "live taker split from trades; no historical split"),
    ("bitget",  "open_interest", True,  False, "full",        _FRESH_POLL, "live REST poll only; no verified 30d historical OI endpoint"),
    ("bitget",  "funding",       True,  True,  "full",        _FRESH_POLL, ""),
    ("bitget",  "mark_price",    True,  False, "full",        _FRESH_POLL, "live REST poll only; no verified 30d historical mark-price endpoint"),
    ("bitget",  "liquidations",  False, False, "unavailable", None,        "no reliable public liquidation feed; not a valid liquidation source"),
]


def capabilities_rows() -> list[tuple]:
    """Rows in exact column order for exchange_capabilities upsert:
    (exchange, metric, live_supported, historical_supported, coverage_type,
     expected_freshness_s, note)."""
    return list(CAPABILITIES)
