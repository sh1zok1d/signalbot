"""Unit tests for symbols/registry.py."""
from __future__ import annotations

import pytest

from symbols import registry as reg


def test_only_btcusdt_active():
    active = reg.active_symbols()
    assert [s.symbol for s in active] == ["BTCUSDT"]


def test_btcusdt_only_perp_and_fields():
    s = reg.get_symbol("BTCUSDT")
    assert s.symbol == "BTCUSDT"
    assert s.base_asset == "BTC"
    assert s.quote_asset == "USDT"
    assert s.asset_tier == "major"
    assert s.status == "ACTIVE"
    assert s.enabled is True
    assert s.disable_policy == "drain"
    assert s.market_types == ("perp",)


def test_active_exchanges():
    assert reg.ACTIVE_EXCHANGES == ("binance", "bybit", "okx")


def test_exactly_six_metric_families():
    assert reg.METRIC_FAMILIES == (
        "price_structure", "volume", "taker_flow", "oi", "funding", "liquidations")
    assert len(reg.METRIC_FAMILIES) == 6


@pytest.mark.parametrize("family, expected", [
    ("price_structure", (3, 3)),
    ("volume", (3, 3)),
    ("funding", (3, 3)),
    ("oi", (2, 3)),
    ("taker_flow", (1, 3)),
    ("liquidations", (0, 3)),
])
def test_historical_asymmetry(family, expected):
    assert reg.historical_support_count("BTCUSDT", family) == expected


def test_oi_okx_historical_unavailable():
    assert reg.family_capability("BTCUSDT", "oi", "okx").historical_supported is False
    assert reg.family_capability("BTCUSDT", "oi", "binance").historical_supported is True


def test_taker_flow_only_binance_historical():
    assert reg.family_capability("BTCUSDT", "taker_flow", "binance").historical_supported is True
    assert reg.family_capability("BTCUSDT", "taker_flow", "bybit").historical_supported is False
    assert reg.family_capability("BTCUSDT", "taker_flow", "okx").historical_supported is False


def test_live_liquidation_quality():
    q = reg.live_liquidation_quality("BTCUSDT")
    assert q == {"binance": "snapshot", "bybit": "full", "okx": "aggregated"}


def test_three_concepts_not_conflated():
    # liquidations: live_supported True everywhere, historical_supported False
    # everywhere, yet coverage_type differs per venue — three separate axes.
    for ex in reg.ACTIVE_EXCHANGES:
        cap = reg.family_capability("BTCUSDT", "liquidations", ex)
        assert cap.live_supported is True
        assert cap.historical_supported is False
    assert reg.family_capability("BTCUSDT", "liquidations", "binance").coverage_type == "snapshot"
    assert reg.family_capability("BTCUSDT", "liquidations", "bybit").coverage_type == "full"
    # historical availability (0/3) is NOT the same as live coverage_type
    assert reg.historical_support_count("BTCUSDT", "liquidations") == (0, 3)


def test_eth_sol_absent():
    names = [s.symbol for s in reg.all_symbols()]
    assert "ETHUSDT" not in names
    assert "SOLUSDT" not in names
    with pytest.raises(reg.SymbolRegistryError):
        reg.get_symbol("ETHUSDT")


def test_bitget_not_active():
    assert "bitget" not in reg.ACTIVE_EXCHANGES


def test_canonical_symbol_not_replaced_by_exchange_id():
    # The registry deals in canonical symbols only; no venue instrument id here.
    assert reg.get_symbol("BTCUSDT").symbol == "BTCUSDT"
