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


def test_live_capability_derived_from_stage1_capabilities():
    """live_supported and coverage_type must come FROM Stage 1's declaration,
    not be a hand-copied second source that can silently diverge."""
    from common.capabilities import CAPABILITIES
    stage1 = {(r[0], r[1]): r for r in CAPABILITIES}   # (ex,metric)->row
    fam_to_metric = {
        "price_structure": "ohlcv", "volume": "ohlcv", "taker_flow": "taker_flow",
        "oi": "open_interest", "funding": "funding", "liquidations": "liquidations",
    }
    for family in reg.METRIC_FAMILIES:
        metric = fam_to_metric[family]
        for ex in reg.ACTIVE_EXCHANGES:
            cap = reg.family_capability("BTCUSDT", family, ex)
            row = stage1[(ex, metric)]
            assert cap.live_supported == row[2]        # derived live_supported
            assert cap.coverage_type == row[4]         # derived coverage_type
    # historical stays a SEPARATE Stage 2 declaration (not equal to live)
    assert reg.family_capability("BTCUSDT", "liquidations", "bybit").live_supported is True
    assert reg.family_capability("BTCUSDT", "liquidations", "bybit").historical_supported is False


# ============================================================================
# structural seed rows (symbol_seed_rows / symbol_exchange_capability_seed_rows)
# ============================================================================
def test_symbol_seed_rows_exact_columns_and_rows():
    rows = reg.symbol_seed_rows()
    assert isinstance(rows, tuple)
    # exactly one row per active symbol
    assert len(rows) == len(reg.active_symbols()) == 1
    # exact column order: symbol, base, quote, tier, status, enabled, disable_policy
    assert rows[0] == ("BTCUSDT", "BTC", "USDT", "major", "ACTIVE", True, "drain")


def test_symbol_seed_rows_repeatable_and_immutable():
    assert reg.symbol_seed_rows() == reg.symbol_seed_rows()
    rows = reg.symbol_seed_rows()
    assert isinstance(rows, tuple) and all(isinstance(r, tuple) for r in rows)


def _cap_index(rows):
    return {(r[0], r[1], r[2], r[3]): r for r in rows}   # (exchange, symbol, mt, metric)


def test_capability_seed_rows_full_cross_product_count():
    rows = reg.symbol_exchange_capability_seed_rows()
    assert isinstance(rows, tuple)
    n_symbols = len(reg.active_symbols())
    n_market_types = sum(len(s.market_types) for s in reg.active_symbols())
    expected = n_market_types * len(reg.ACTIVE_EXCHANGES) * len(reg.METRIC_FAMILIES)
    assert len(rows) == expected == 18       # 1 symbol * 1 mt * 3 exchanges * 6 families
    assert n_symbols == 1


def test_capability_seed_rows_deterministic_order():
    rows = reg.symbol_exchange_capability_seed_rows()
    # order: symbol -> market_type -> exchange -> METRIC_FAMILIES order
    expected_order = []
    for s in reg.active_symbols():
        for mt in s.market_types:
            for ex in reg.ACTIVE_EXCHANGES:
                for fam in reg.METRIC_FAMILIES:
                    expected_order.append((ex, s.symbol, mt, fam))
    assert [(r[0], r[1], r[2], r[3]) for r in rows] == expected_order


def test_capability_seed_rows_cover_every_exchange_family_market_type():
    rows = reg.symbol_exchange_capability_seed_rows()
    assert {r[0] for r in rows} == set(reg.ACTIVE_EXCHANGES)
    assert {r[3] for r in rows} == set(reg.METRIC_FAMILIES)
    assert {r[2] for r in rows} == {"perp"}


def test_capability_seed_rows_live_facts_equal_stage1():
    from common.capabilities import CAPABILITIES
    stage1 = {(r[0], r[1]): r for r in CAPABILITIES}
    fam_to_metric = {
        "price_structure": "ohlcv", "volume": "ohlcv", "taker_flow": "taker_flow",
        "oi": "open_interest", "funding": "funding", "liquidations": "liquidations",
    }
    for r in reg.symbol_exchange_capability_seed_rows():
        exchange, _symbol, _mt, metric = r[0], r[1], r[2], r[3]
        s1 = stage1[(exchange, fam_to_metric[metric])]
        assert r[4] == bool(s1[2])       # live_supported
        assert r[6] == s1[4]             # coverage_type
        assert r[7] == s1[5]             # expected_freshness_s
        assert r[9] == s1[6]             # note


def test_capability_seed_rows_historical_facts_equal_registry():
    idx = _cap_index(reg.symbol_exchange_capability_seed_rows())
    # historical_supported must mirror registry family_capability, not live facts
    for ex in reg.ACTIVE_EXCHANGES:
        for fam in reg.METRIC_FAMILIES:
            row = idx[(ex, "BTCUSDT", "perp", fam)]
            expected = reg.family_capability("BTCUSDT", fam, ex).historical_supported
            assert row[5] == expected


def test_capability_seed_rows_no_fabricated_unavailable_or_disabled():
    rows = reg.symbol_exchange_capability_seed_rows()
    # every active-venue row is enabled; coverage_type is never fabricated as
    # 'unavailable' for these active exchanges (all live-supported here).
    for r in rows:
        assert r[8] is True                          # enabled
        assert r[6] != "unavailable"


def test_capability_seed_rows_repeatable_and_source_not_mutated():
    from common.capabilities import CAPABILITIES
    before_caps = [tuple(r) for r in CAPABILITIES]
    first = reg.symbol_exchange_capability_seed_rows()
    second = reg.symbol_exchange_capability_seed_rows()
    assert first == second
    assert isinstance(first, tuple) and all(isinstance(r, tuple) for r in first)
    # calling the helper must not mutate the Stage 1 declaration
    assert [tuple(r) for r in CAPABILITIES] == before_caps
