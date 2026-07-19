"""Unit tests for the centralized OKX symbol mapper (Stage 2 decision F).

No network access is performed: constructing OKXClient does not open any
connection, and the backfill module is only imported (never run) to prove it
shares the same mapper.
"""
from __future__ import annotations

import pytest

import common.symbol_mapper as sm
from common.symbol_mapper import SymbolMappingError, to_exchange_symbol


# --- happy path: canonical -> OKX perpetual instrument id -------------------
@pytest.mark.parametrize(
    "canonical, expected",
    [
        ("BTCUSDT", "BTC-USDT-SWAP"),
        ("ETHUSDT", "ETH-USDT-SWAP"),
        ("SOLUSDT", "SOL-USDT-SWAP"),
    ],
)
def test_okx_perp_mapping(canonical, expected):
    assert to_exchange_symbol("okx", canonical, "perp") == expected


def test_market_type_defaults_to_perp():
    assert to_exchange_symbol("okx", "BTCUSDT") == "BTC-USDT-SWAP"


# --- explicit failures: no fallback ----------------------------------------
def test_unknown_symbol_raises():
    with pytest.raises(SymbolMappingError):
        to_exchange_symbol("okx", "DOGEUSDT", "perp")


def test_unknown_exchange_raises():
    with pytest.raises(SymbolMappingError):
        to_exchange_symbol("binance", "BTCUSDT", "perp")


def test_unsupported_market_type_raises():
    with pytest.raises(SymbolMappingError):
        to_exchange_symbol("okx", "BTCUSDT", "spot")


def test_unknown_symbol_never_returns_btc_mapping():
    """An unknown symbol must raise, never silently fall back to the BTC id."""
    with pytest.raises(SymbolMappingError):
        result = to_exchange_symbol("okx", "XRPUSDT", "perp")
        # unreachable, but make the intent explicit if the guard ever regresses:
        assert result != "BTC-USDT-SWAP"


def test_none_and_empty_symbol_raise():
    for bad in ("", "btcusdt", "BTC-USDT-SWAP"):  # wrong case / already-native
        with pytest.raises(SymbolMappingError):
            to_exchange_symbol("okx", bad, "perp")


# --- OKX client uses the mapper; canonical symbol is preserved --------------
def _dummy_callbacks():
    from data_ingestion.base_client import ClientCallbacks

    async def _noop(*_a, **_k):
        return None

    return ClientCallbacks(
        on_trade=_noop, on_oi=_noop, on_funding=_noop,
        on_mark_price=_noop, on_liquidation=_noop,
    )


def test_okx_client_maps_inst_id_but_keeps_canonical_symbol():
    from data_ingestion.okx_client import OKXClient

    client = OKXClient("ETHUSDT", _dummy_callbacks())
    # instrument id used for API/WS is the OKX-native one ...
    assert client._inst_id == "ETH-USDT-SWAP"
    # ... but the canonical symbol (used in outgoing objects / DB rows) is intact
    assert client.symbol == "ETHUSDT"


def test_okx_client_btc_default_symbol():
    from data_ingestion.okx_client import OKXClient

    client = OKXClient("BTCUSDT", _dummy_callbacks())
    assert client._inst_id == "BTC-USDT-SWAP"
    assert client.symbol == "BTCUSDT"


# --- live client and backfill share ONE mapper -----------------------------
def test_live_client_and_backfill_share_same_mapper():
    import backfill.backfill as bf
    import data_ingestion.okx_client as okx

    # Both modules import the exact same function object from common.symbol_mapper.
    assert okx.to_exchange_symbol is sm.to_exchange_symbol
    assert bf.to_exchange_symbol is sm.to_exchange_symbol
