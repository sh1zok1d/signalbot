"""
Stage 2 symbol registry — declarative, in the style of common/capabilities.py.

Active symbol in Stage 2.1: BTCUSDT only (perp). Active exchanges: binance,
bybit, okx (Bitget disabled — not present here). ETH/SOL are NOT activated even
though common.symbol_mapper knows their instrument ids.

THREE DISTINCT CONCEPTS, never conflated:
  1. live_supported       — a live feed for this family exists on the venue.
  2. historical_supported — a historical source exists to backfill the family.
  3. coverage_type        — the TYPE/QUALITY of the LIVE feed
                            (full | snapshot | aggregated | unavailable).
A family being live_supported does NOT mean a historical bucket has data — most
importantly, live liquidation feeds exist on all three venues (coverage_type
snapshot/full/aggregated) yet historical liquidations are 0/3, because
liquidations are never backfilled (Stage 1 rule). Absence of historical data is
NOT a measured zero.

Where a family's LIVE capability overlaps Stage 1's common/capabilities.py, that
Stage 1 declaration is the source of the live facts; this module only adds the
symbol/market_type dimension and the per-family HISTORICAL-availability
semantics. It is kept consistent with Stage 1 and does not restate it as a
second contradicting authority.
"""
from __future__ import annotations

from dataclasses import dataclass


class SymbolRegistryError(KeyError):
    """Unknown symbol / family / exchange lookup against the registry."""


# The six metric families (spec §2, revision 0.2.2). Exactly six.
METRIC_FAMILIES: tuple[str, ...] = (
    "price_structure",
    "volume",
    "taker_flow",
    "oi",
    "funding",
    "liquidations",
)

# Active Stage 2 venues (Bitget intentionally absent).
ACTIVE_EXCHANGES: tuple[str, ...] = ("binance", "bybit", "okx")


@dataclass(frozen=True)
class SymbolDefinition:
    symbol: str
    base_asset: str
    quote_asset: str
    asset_tier: str
    status: str
    enabled: bool
    disable_policy: str
    market_types: tuple[str, ...]


@dataclass(frozen=True)
class FamilyCapability:
    """Per (symbol, exchange, metric family). The three concepts are separate
    fields so they can never be conflated by a caller."""
    live_supported: bool
    historical_supported: bool
    coverage_type: str   # LIVE feed type/quality


# ---- active symbols (only BTCUSDT, perp) -----------------------------------
_SYMBOLS: dict[str, SymbolDefinition] = {
    "BTCUSDT": SymbolDefinition(
        symbol="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        asset_tier="major",
        status="ACTIVE",
        enabled=True,
        disable_policy="drain",
        market_types=("perp",),
    ),
}


# ---- per-family capability matrix for BTCUSDT ------------------------------
# Historical availability asymmetry (BTCUSDT):
#   price_structure : 3/3   volume : 3/3   funding : 3/3
#   oi              : 2/3 (OKX historical unavailable)
#   taker_flow      : 1/3 (Binance only)
#   liquidations    : 0/3 (never backfilled)
def _cap(live: bool, hist: bool, coverage: str) -> FamilyCapability:
    return FamilyCapability(live_supported=live, historical_supported=hist,
                            coverage_type=coverage)


# Live price/volume/taker/oi/funding are full on all three venues; the LIVE
# liquidation feed differs by venue (snapshot/full/aggregated), matching Stage 1.
_BTCUSDT_CAPS: dict[str, dict[str, FamilyCapability]] = {
    "price_structure": {
        "binance": _cap(True, True, "full"),
        "bybit":   _cap(True, True, "full"),
        "okx":     _cap(True, True, "full"),
    },
    "volume": {
        "binance": _cap(True, True, "full"),
        "bybit":   _cap(True, True, "full"),
        "okx":     _cap(True, True, "full"),
    },
    "taker_flow": {
        # Only Binance has a historical taker split (Stage 1 finding).
        "binance": _cap(True, True, "full"),
        "bybit":   _cap(True, False, "full"),
        "okx":     _cap(True, False, "full"),
    },
    "oi": {
        # OKX has no verified 30d historical OI endpoint.
        "binance": _cap(True, True, "full"),
        "bybit":   _cap(True, True, "full"),
        "okx":     _cap(True, False, "full"),
    },
    "funding": {
        "binance": _cap(True, True, "full"),
        "bybit":   _cap(True, True, "full"),
        "okx":     _cap(True, True, "full"),
    },
    "liquidations": {
        # Live feeds exist everywhere but differ in quality; NONE is backfilled.
        "binance": _cap(True, False, "snapshot"),
        "bybit":   _cap(True, False, "full"),
        "okx":     _cap(True, False, "aggregated"),
    },
}

_CAPABILITIES: dict[str, dict[str, dict[str, FamilyCapability]]] = {
    "BTCUSDT": _BTCUSDT_CAPS,
}


# ---- accessors -------------------------------------------------------------
def active_symbols() -> tuple[SymbolDefinition, ...]:
    """Symbols that are enabled AND status ACTIVE."""
    return tuple(s for s in _SYMBOLS.values() if s.enabled and s.status == "ACTIVE")


def all_symbols() -> tuple[SymbolDefinition, ...]:
    return tuple(_SYMBOLS.values())


def get_symbol(symbol: str) -> SymbolDefinition:
    try:
        return _SYMBOLS[symbol]
    except KeyError:
        raise SymbolRegistryError(
            f"unknown symbol {symbol!r}; active: {sorted(_SYMBOLS)}") from None


def family_capability(symbol: str, family: str, exchange: str) -> FamilyCapability:
    if symbol not in _CAPABILITIES:
        raise SymbolRegistryError(f"unknown symbol {symbol!r}")
    if family not in METRIC_FAMILIES:
        raise SymbolRegistryError(f"unknown metric family {family!r}")
    fam = _CAPABILITIES[symbol].get(family, {})
    try:
        return fam[exchange]
    except KeyError:
        raise SymbolRegistryError(
            f"no capability for {symbol}/{family}/{exchange}") from None


def historical_support_count(symbol: str, family: str) -> tuple[int, int]:
    """(available, total) exchanges with historical support for the family."""
    if symbol not in _CAPABILITIES:
        raise SymbolRegistryError(f"unknown symbol {symbol!r}")
    if family not in METRIC_FAMILIES:
        raise SymbolRegistryError(f"unknown metric family {family!r}")
    fam = _CAPABILITIES[symbol][family]
    available = sum(1 for ex in ACTIVE_EXCHANGES if fam[ex].historical_supported)
    return available, len(ACTIVE_EXCHANGES)


def live_liquidation_quality(symbol: str) -> dict[str, str]:
    """Per-exchange LIVE liquidation feed quality (coverage_type)."""
    if symbol not in _CAPABILITIES:
        raise SymbolRegistryError(f"unknown symbol {symbol!r}")
    fam = _CAPABILITIES[symbol]["liquidations"]
    return {ex: fam[ex].coverage_type for ex in ACTIVE_EXCHANGES}
