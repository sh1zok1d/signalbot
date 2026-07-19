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

from common.capabilities import CAPABILITIES as _STAGE1_CAPS


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


# ---- live capability is DERIVED from Stage 1 (single source of truth) ------
# live_supported and coverage_type are STRUCTURAL LIVE facts owned by Stage 1's
# common/capabilities.py — we read them programmatically instead of re-declaring
# them here (so the two can never silently diverge). Each Stage 2 family maps to
# the Stage 1 metric that carries that live capability.
_FAMILY_TO_STAGE1_METRIC: dict[str, str] = {
    "price_structure": "ohlcv",
    "volume":          "ohlcv",
    "taker_flow":      "taker_flow",
    "oi":              "open_interest",
    "funding":         "funding",
    "liquidations":    "liquidations",
}

# Stage 1 rows: (exchange, metric, live_supported, historical_supported,
#               coverage_type, expected_freshness_s, note).
_STAGE1_BY_KEY = {(r[0], r[1]): r for r in _STAGE1_CAPS}


def _stage1_row(exchange: str, metric: str):
    try:
        return _STAGE1_BY_KEY[(exchange, metric)]
    except KeyError:
        raise SymbolRegistryError(
            f"no Stage 1 capability declared for {exchange}/{metric}") from None


# ---- historical availability is Stage 2's OWN added semantics ---------------
# This is the ONLY capability axis declared here (not in Stage 1's metric table
# in a family-mapped form). Kept SEPARATE from live_supported and coverage_type.
#   price_structure 3/3   volume 3/3   funding 3/3
#   oi 2/3 (OKX historical unavailable)   taker_flow 1/3 (Binance only)
#   liquidations 0/3 (never backfilled)
_HISTORICAL_SUPPORTED: dict[str, dict[str, dict[str, bool]]] = {
    "BTCUSDT": {
        "price_structure": {"binance": True,  "bybit": True,  "okx": True},
        "volume":          {"binance": True,  "bybit": True,  "okx": True},
        "taker_flow":      {"binance": True,  "bybit": False, "okx": False},
        "oi":              {"binance": True,  "bybit": True,  "okx": False},
        "funding":         {"binance": True,  "bybit": True,  "okx": True},
        "liquidations":    {"binance": False, "bybit": False, "okx": False},
    },
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
    """live_supported + coverage_type derived from Stage 1; historical_supported
    from this registry's own declaration. Three separate axes, never conflated."""
    if symbol not in _HISTORICAL_SUPPORTED:
        raise SymbolRegistryError(f"unknown symbol {symbol!r}")
    if family not in METRIC_FAMILIES:
        raise SymbolRegistryError(f"unknown metric family {family!r}")
    if exchange not in ACTIVE_EXCHANGES:
        raise SymbolRegistryError(f"inactive/unknown exchange {exchange!r}")
    row = _stage1_row(exchange, _FAMILY_TO_STAGE1_METRIC[family])
    return FamilyCapability(
        live_supported=bool(row[2]),                 # Stage 1 (structural live)
        historical_supported=_HISTORICAL_SUPPORTED[symbol][family][exchange],
        coverage_type=row[4],                        # Stage 1 (live feed quality)
    )


def historical_support_count(symbol: str, family: str) -> tuple[int, int]:
    """(available, total) exchanges with historical support for the family."""
    if symbol not in _HISTORICAL_SUPPORTED:
        raise SymbolRegistryError(f"unknown symbol {symbol!r}")
    if family not in METRIC_FAMILIES:
        raise SymbolRegistryError(f"unknown metric family {family!r}")
    fam = _HISTORICAL_SUPPORTED[symbol][family]
    available = sum(1 for ex in ACTIVE_EXCHANGES if fam[ex])
    return available, len(ACTIVE_EXCHANGES)


def live_liquidation_quality(symbol: str) -> dict[str, str]:
    """Per-exchange LIVE liquidation feed quality (coverage_type), from Stage 1."""
    if symbol not in _HISTORICAL_SUPPORTED:
        raise SymbolRegistryError(f"unknown symbol {symbol!r}")
    return {ex: family_capability(symbol, "liquidations", ex).coverage_type
            for ex in ACTIVE_EXCHANGES}
