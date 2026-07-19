"""Unit tests for common/instrument_metadata.py. No real network."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from common.symbol_mapper import to_exchange_symbol
from common import instrument_metadata as im
from common.instrument_metadata import (
    FailClosedError, InstrumentMetadata, MalformedMetadataError,
    MetadataMismatchError, MetadataUnavailableError, fetch_instrument_metadata,
    is_notional_eligible, parse_binance, parse_bybit, parse_okx,
)

FIXED = datetime(2026, 1, 1, tzinfo=timezone.utc)

BINANCE_PAYLOAD = {"symbols": [{
    "symbol": "BTCUSDT", "pricePrecision": 2, "quantityPrecision": 3,
    "filters": [{"filterType": "PRICE_FILTER", "tickSize": "0.10"},
                {"filterType": "LOT_SIZE", "stepSize": "0.001"}]}]}

BYBIT_PAYLOAD = {"result": {"list": [{
    "symbol": "BTCUSDT", "priceFilter": {"tickSize": "0.10"},
    "lotSizeFilter": {"qtyStep": "0.001"}}]}}

OKX_PAYLOAD = {"data": [{
    "instId": "BTC-USDT-SWAP", "ctVal": "0.01", "ctValCcy": "BTC",
    "tickSz": "0.1", "lotSz": "1"}]}


def _run(coro):
    return asyncio.run(coro)


def _fetch_returning(payload):
    async def _f(url, params):
        return payload
    return _f


def _fetch_failing(exc=RuntimeError("network down")):
    async def _f(url, params):
        raise exc
    return _f


# -- parsers -----------------------------------------------------------------
def test_binance_parser_base_unit():
    m = parse_binance(BINANCE_PAYLOAD, "BTCUSDT", fetched_at=FIXED)
    assert m.quantity_unit == "base"
    assert m.contract_multiplier is None
    assert m.tick_size == 0.10
    assert m.exchange_instrument_id == "BTCUSDT"
    assert m.metadata_source == "exchange_api"


def test_bybit_parser_base_unit():
    m = parse_bybit(BYBIT_PAYLOAD, "BTCUSDT", fetched_at=FIXED)
    assert m.quantity_unit == "base"
    assert m.contract_multiplier is None
    assert m.tick_size == 0.10


def test_okx_parser_contracts_and_uses_shared_mapper():
    m = parse_okx(OKX_PAYLOAD, "BTCUSDT", fetched_at=FIXED)
    assert m.quantity_unit == "contracts"
    assert m.contract_multiplier == 0.01                      # ctVal -> multiplier
    assert m.tick_size == 0.1
    # instrument id comes from the shared symbol mapper, not a second mapping
    assert m.exchange_instrument_id == to_exchange_symbol("okx", "BTCUSDT", "perp")
    assert m.exchange_instrument_id == "BTC-USDT-SWAP"


def test_okx_missing_ctval_fails_closed_no_default_multiplier():
    bad = {"data": [{"instId": "BTC-USDT-SWAP", "tickSz": "0.1"}]}  # no ctVal
    with pytest.raises(FailClosedError):
        parse_okx(bad, "BTCUSDT", fetched_at=FIXED)


def test_okx_zero_ctval_fails_closed():
    bad = {"data": [{"instId": "BTC-USDT-SWAP", "ctVal": "0", "tickSz": "0.1"}]}
    with pytest.raises(FailClosedError):
        parse_okx(bad, "BTCUSDT", fetched_at=FIXED)


def test_malformed_numeric_rejected():
    bad = {"symbols": [{"symbol": "BTCUSDT",
                        "filters": [{"filterType": "PRICE_FILTER", "tickSize": "abc"}]}]}
    with pytest.raises(MalformedMetadataError):
        parse_binance(bad, "BTCUSDT", fetched_at=FIXED)


# -- notional eligibility ----------------------------------------------------
def test_base_unit_notional_eligible_without_multiplier():
    m = parse_binance(BINANCE_PAYLOAD, "BTCUSDT", fetched_at=FIXED)
    assert is_notional_eligible(m) is True


def test_contracts_without_multiplier_not_eligible():
    m = InstrumentMetadata(
        exchange="okx", symbol="BTCUSDT", market_type="perp",
        exchange_instrument_id="BTC-USDT-SWAP", quantity_unit="contracts",
        contract_multiplier=None, tick_size=0.1, price_precision=None,
        quantity_precision=None, metadata_source="declared_fallback",
        fetched_at=FIXED, is_stale=True)
    assert is_notional_eligible(m) is False
    # and it was never defaulted to 1.0
    assert m.contract_multiplier is None


# -- fetch wrapper: LKG / unavailable ---------------------------------------
def test_fetch_success_fresh():
    m = _run(fetch_instrument_metadata("okx", "BTCUSDT", _fetch_returning(OKX_PAYLOAD),
                                       fetched_at=FIXED))
    assert m.is_stale is False
    assert m.contract_multiplier == 0.01


def test_fetch_failure_with_lkg_returns_stale_lkg():
    lkg = parse_okx(OKX_PAYLOAD, "BTCUSDT", fetched_at=FIXED)
    m = _run(fetch_instrument_metadata("okx", "BTCUSDT", _fetch_failing(), lkg=lkg))
    assert m.is_stale is True
    assert m.contract_multiplier == lkg.contract_multiplier
    assert m.exchange_instrument_id == lkg.exchange_instrument_id


def test_fetch_failure_without_lkg_unavailable():
    with pytest.raises(MetadataUnavailableError):
        _run(fetch_instrument_metadata("okx", "BTCUSDT", _fetch_failing(), lkg=None))


def test_stale_fallback_preserves_fetched_at_and_critical_fields():
    lkg = parse_okx(OKX_PAYLOAD, "BTCUSDT", fetched_at=FIXED)
    m = _run(fetch_instrument_metadata("okx", "BTCUSDT", _fetch_failing(), lkg=lkg))
    assert m.is_stale is True
    assert m.fetched_at == FIXED                 # ORIGINAL fetched_at preserved
    assert m.fetched_at.tzinfo is not None       # tz-aware
    for f in ("exchange_instrument_id", "quantity_unit",
              "contract_multiplier", "tick_size"):
        assert getattr(m, f) == getattr(lkg, f)  # critical fields NOT changed


# -- mismatch alarm ----------------------------------------------------------
def test_mismatch_tick_size_detected_and_lkg_not_overwritten():
    lkg = parse_binance(BINANCE_PAYLOAD, "BTCUSDT", fetched_at=FIXED)
    changed = {"symbols": [{"symbol": "BTCUSDT", "pricePrecision": 2,
                            "quantityPrecision": 3,
                            "filters": [{"filterType": "PRICE_FILTER", "tickSize": "0.20"}]}]}
    with pytest.raises(MetadataMismatchError) as ei:
        _run(fetch_instrument_metadata("binance", "BTCUSDT", _fetch_returning(changed),
                                       lkg=lkg, fetched_at=FIXED))
    assert "tick_size" in ei.value.fields
    # LKG object is unchanged (frozen; never overwritten)
    assert lkg.tick_size == 0.10


def test_mismatch_ctval_detected():
    lkg = parse_okx(OKX_PAYLOAD, "BTCUSDT", fetched_at=FIXED)
    changed = {"data": [{"instId": "BTC-USDT-SWAP", "ctVal": "0.02", "tickSz": "0.1"}]}
    with pytest.raises(MetadataMismatchError) as ei:
        _run(fetch_instrument_metadata("okx", "BTCUSDT", _fetch_returning(changed),
                                       lkg=lkg, fetched_at=FIXED))
    assert "contract_multiplier" in ei.value.fields
    assert lkg.contract_multiplier == 0.01
