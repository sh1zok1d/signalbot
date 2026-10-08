"""Liquidation feeds of the live collectors (docs/BETA_DATA_RELIABILITY_FIX_PLAN_V1.md R1, R2): the
side that was liquidated, OKX contracts -> BTC, the snapshot flag against each venue's capability,
OKX subscribe errors in the log, and the mapping revision every new row carries. No network."""
import asyncio
import logging

import pytest

from common.capabilities import CAPABILITIES
from data_ingestion import okx_client
from data_ingestion.base_client import LIQUIDATION_MAPPING_VERSION, ClientCallbacks
from data_ingestion.binance_client import BinanceClient
from data_ingestion.bybit_client import BybitClient
from data_ingestion.okx_client import OKXClient


def _collect():
    got = []

    async def on_liq(liq):
        got.append(liq)

    async def nop(*_a):
        return None
    return got, ClientCallbacks(on_trade=nop, on_oi=nop, on_funding=nop, on_mark_price=nop, on_liquidation=on_liq)


def _run(coro):
    return asyncio.run(coro)


def test_a_bybit_buy_update_is_a_liquidated_long_and_a_sell_update_a_short():
    """Bybit v5 allLiquidation: "When you receive a Buy update, this means that a long position has been
    liquidated"; `p` is the bankruptcy price. The VPS check of 2026-10-08 found every stored «long» above
    mark, i.e. the old mapping was swapped (R2)."""
    got, cb = _collect()
    c = BybitClient("BTCUSDT", cb)
    _run(c._handle_message({"topic": "allLiquidation.BTCUSDT", "type": "snapshot", "data": [
        {"T": 1759900000000, "s": "BTCUSDT", "S": "Buy", "v": "0.5", "p": "60000"},
        {"T": 1759900001000, "s": "BTCUSDT", "S": "Sell", "v": "0.2", "p": "62000"},
        {"T": 1759900002000, "s": "BTCUSDT", "S": "", "v": "1", "p": "61000"}]}))
    assert [(x.side, x.qty, x.price) for x in got] == [("long", 0.5, 60000.0), ("short", 0.2, 62000.0)]
    assert all(x.mapping_version == LIQUIDATION_MAPPING_VERSION == 2 for x in got)


def _okx_push(details):
    return {"arg": {"channel": "liquidation-orders", "instType": "SWAP"},
            "data": [{"instId": "BTC-USDT-SWAP", "instType": "SWAP", "uly": "BTC-USDT", "details": details},
                     {"instId": "ETH-USDT-SWAP", "instType": "SWAP", "details": [
                         {"posSide": "long", "side": "sell", "bkPx": "2000", "sz": "5", "ts": "1759900000000"}]}]}


def test_okx_contracts_are_turned_into_btc_and_net_mode_reads_the_order_side():
    """OKX `sz` is in contracts (ctVal 0.01 BTC): the old notional bkPx x sz was 100x too large (R1). In net
    mode posSide is "net" and the forced order's side names the position: buy closes a short."""
    got, cb = _collect()
    c = OKXClient("BTCUSDT", cb)
    c._ct_val = 0.01
    _run(c._handle_liquidation_message(_okx_push([
        {"posSide": "long", "side": "sell", "bkPx": "60000", "sz": "13", "ts": "1759900000000"},
        {"posSide": "net", "side": "buy", "bkPx": "61000", "sz": "100", "ts": "1759900001000"},
        {"posSide": "net", "side": "sell", "bkPx": "59000", "sz": "2", "ts": "1759900002000"},
        {"posSide": "net", "side": "", "bkPx": "59000", "sz": "2", "ts": "1759900003000"}])))
    assert [x.side for x in got] == ["long", "short", "long"]
    assert [x.qty for x in got] == pytest.approx([0.13, 1.0, 0.02])
    assert [x.notional for x in got] == pytest.approx([7800.0, 61000.0, 1180.0])
    assert all(x.symbol == "BTCUSDT" and x.mapping_version == 2 for x in got)


def test_okx_stores_nothing_without_a_contract_value():
    got, cb = _collect()
    c = OKXClient("BTCUSDT", cb)
    _run(c._handle_liquidation_message(_okx_push([
        {"posSide": "long", "side": "sell", "bkPx": "60000", "sz": "13", "ts": "1759900000000"}])))
    assert got == []


def test_each_venue_writes_the_snapshot_flag_its_capability_declares():
    """input_adapter refuses a bucket whose rows disagree with the venue's coverage type; OKX is
    `aggregated`, so a True flag dropped the whole OKX feature vector (R1)."""
    coverage = {ex: cov for ex, metric, _l, _h, cov, _f, _n in CAPABILITIES if metric == "liquidations"}
    rows = {}
    got, cb = _collect()
    _run(BinanceClient("BTCUSDT", cb)._handle_message({"data": {"e": "forceOrder", "o": {
        "S": "SELL", "q": "0.1", "ap": "60000", "p": "60000", "T": 1759900000000}}}))
    rows["binance"] = got[-1]
    _run(BybitClient("BTCUSDT", cb)._handle_message({"topic": "allLiquidation.BTCUSDT", "data": [
        {"T": 1759900000000, "S": "Buy", "v": "0.1", "p": "60000"}]}))
    rows["bybit"] = got[-1]
    okx = OKXClient("BTCUSDT", cb)
    okx._ct_val = 0.01
    _run(okx._handle_liquidation_message(_okx_push([
        {"posSide": "short", "side": "buy", "bkPx": "60000", "sz": "1", "ts": "1759900000000"}])))
    rows["okx"] = got[-1]
    for ex, liq in rows.items():
        assert liq.is_snapshot_feed is (coverage[ex] == "snapshot"), ex


def test_okx_subscribes_liquidations_on_the_public_endpoint():
    """liquidation-orders is a /ws/v5/public channel; /ws/v5/business answers 60018 (R1)."""
    assert okx_client.WS_LIQUIDATION_URL == "wss://ws.okx.com:8443/ws/v5/public"


def test_an_okx_subscribe_error_reaches_the_log(caplog):
    got, cb = _collect()
    c = OKXClient("BTCUSDT", cb)
    c._ct_val = 0.01
    with caplog.at_level(logging.INFO, logger="data_ingestion.okx_client"):
        _run(c._handle_liquidation_message({"event": "error", "code": "60018",
                                            "msg": "channel:liquidation-orders doesn't exist"}))
        _run(c._handle_liquidation_message({"event": "subscribe",
                                            "arg": {"channel": "liquidation-orders", "instType": "SWAP"}}))
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1 and "60018" in errors[0].getMessage()
    assert any("subscribe" in r.getMessage() and r.levelno == logging.INFO for r in caplog.records)
    assert got == []


def test_without_a_usable_ctval_the_okx_feed_never_subscribes(monkeypatch):
    from common.instrument_metadata import FailClosedError, parse_okx
    with pytest.raises(FailClosedError):          # the parser the feed relies on refuses a missing ctVal
        parse_okx({"data": [{"instId": "BTC-USDT-SWAP", "tickSz": "0.1", "ctVal": ""}]}, "BTCUSDT")
    got, cb = _collect()
    c = OKXClient("BTCUSDT", cb)
    connects = []

    async def no_ct_val():
        raise FailClosedError("okx BTC-USDT-SWAP: missing ctVal")

    def connect(*a, **k):
        connects.append(a)
        raise AssertionError("must not connect")

    async def sleep(_s):
        c.stop()
    monkeypatch.setattr(c, "_fetch_ct_val", no_ct_val)
    monkeypatch.setattr(okx_client.websockets, "connect", connect)
    monkeypatch.setattr(okx_client.asyncio, "sleep", sleep)
    _run(c.run_liquidations_forever())
    assert connects == [] and c._ct_val is None and got == []
