"""
Centralized canonical-symbol -> exchange-native instrument id mapping.

Why this exists (Stage 2 decision F): the OKX client and the OKX backfill each
had an independent hardcoded ``BTC-USDT-SWAP`` literal. That is a silent-mislabel
hazard — if a second symbol is ever ingested, a stale hardcode would quietly
pull the wrong instrument while the stored rows still claim the canonical
symbol. This module is the single source of truth for that translation, used by
BOTH the live client and the backfill.

Contract:
  * The CANONICAL symbol (``BTCUSDT``/``ETHUSDT``/``SOLUSDT``) is what the
    application and every persisted DB row use — it is NEVER changed here.
  * The value returned by :func:`to_exchange_symbol` is the venue-native
    instrument id, used ONLY for exchange API / WebSocket requests.
  * There is NO fallback. An unknown exchange, symbol, or market_type raises
    :class:`SymbolMappingError` — loudly, before any network call or DB write —
    so a wrong instrument can never be silently substituted (never a BTC
    default for an unknown symbol).

Scope right now: only ``exchange="okx"`` and ``market_type="perp"``. Spot is not
implemented. The presence of ETH/SOL rows here does NOT enable their ingestion —
it only makes the mapping correct if/when they are turned on elsewhere.
"""
from __future__ import annotations


class SymbolMappingError(ValueError):
    """Raised when a canonical symbol cannot be mapped to an exchange
    instrument id (unknown exchange / market_type / symbol). Never falls back."""


# (exchange, market_type) -> { canonical_symbol : exchange_instrument_id }
# This table is the ONLY place the venue-native instrument literals live.
_MAPPINGS: dict[tuple[str, str], dict[str, str]] = {
    ("okx", "perp"): {
        "BTCUSDT": "BTC-USDT-SWAP",
        "ETHUSDT": "ETH-USDT-SWAP",
        "SOLUSDT": "SOL-USDT-SWAP",
    },
}

_SUPPORTED_EXCHANGES = {ex for (ex, _mt) in _MAPPINGS}
_SUPPORTED_MARKET_TYPES = {mt for (_ex, mt) in _MAPPINGS}


def to_exchange_symbol(exchange: str, symbol: str, market_type: str = "perp") -> str:
    """Map a canonical symbol to its exchange-native instrument id.

    Args:
        exchange: exchange key, e.g. ``"okx"`` (only ``okx`` supported now).
        symbol: canonical symbol, e.g. ``"BTCUSDT"``.
        market_type: ``"perp"`` (only perpetual supported now; spot not
            implemented).

    Returns:
        The venue-native instrument id, e.g. ``"BTC-USDT-SWAP"``.

    Raises:
        SymbolMappingError: if the exchange, market_type, or symbol is unknown.
            Never returns a fallback / default instrument.
    """
    if exchange not in _SUPPORTED_EXCHANGES:
        raise SymbolMappingError(
            f"unsupported exchange {exchange!r}; supported: {sorted(_SUPPORTED_EXCHANGES)}"
        )
    if market_type not in _SUPPORTED_MARKET_TYPES:
        raise SymbolMappingError(
            f"unsupported market_type {market_type!r} for exchange {exchange!r}; "
            f"supported: {sorted(_SUPPORTED_MARKET_TYPES)} (spot not implemented)"
        )
    table = _MAPPINGS.get((exchange, market_type))
    if table is None:
        # exchange/market_type are individually supported but not this pairing.
        raise SymbolMappingError(
            f"no mapping table for exchange={exchange!r} market_type={market_type!r}"
        )
    try:
        return table[symbol]
    except KeyError:
        raise SymbolMappingError(
            f"no {exchange}/{market_type} instrument mapping for canonical symbol "
            f"{symbol!r}; known symbols: {sorted(table)} (no fallback)"
        ) from None
