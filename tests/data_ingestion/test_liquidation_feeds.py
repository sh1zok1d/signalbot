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
        with pytest.raises(okx_client.SubscribeRefused):      # the socket is closed, then retried with backoff
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


class _FakeWS:
    """Plays `frames` (a list of str, or "SILENCE" for a recv timeout), records what is sent."""

    def __init__(self, frames):
        self.frames, self.sent = list(frames), []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def send(self, msg):
        self.sent.append(msg)

    async def recv(self):
        if not self.frames:
            raise ConnectionError("closed")
        f = self.frames.pop(0)
        if f == "SILENCE":
            raise asyncio.TimeoutError
        return f


def _loop_with(monkeypatch, sockets, c):
    """run_liquidations_forever over `sockets` (one per connect); returns the backoff sleeps."""
    sleeps = []

    def connect(*_a, **_k):
        return sockets.pop(0)

    async def sleep(s):
        sleeps.append(s)
        if not sockets:
            c.stop()

    async def wait_for(aw, timeout):
        return await aw
    monkeypatch.setattr(okx_client.websockets, "connect", connect)
    monkeypatch.setattr(okx_client.asyncio, "sleep", sleep)
    monkeypatch.setattr(okx_client.asyncio, "wait_for", wait_for)
    return sleeps


def test_a_refused_okx_subscription_backs_off_instead_of_retrying_at_once(monkeypatch):
    """Review of #374: the backoff was reset right after connect, before OKX answered, so a refused
    subscription reconnected every ~31 s forever. It now grows until OKX acknowledges."""
    got, cb = _collect()
    c = OKXClient("BTCUSDT", cb)
    c._ct_val = 0.01
    refused = '{"event": "error", "code": "60018", "msg": "doesn\'t exist"}'
    sleeps = _loop_with(monkeypatch, [_FakeWS([refused]) for _ in range(4)], c)
    _run(c.run_liquidations_forever())
    assert sleeps == [1.0, 2.0, 4.0, 8.0]
    # an acknowledged subscription resets it
    c2 = OKXClient("BTCUSDT", cb)
    c2._ct_val = 0.01
    ack = '{"event": "subscribe", "arg": {"channel": "liquidation-orders", "instType": "SWAP"}}'
    sleeps = _loop_with(monkeypatch, [_FakeWS([refused]), _FakeWS([refused]), _FakeWS([ack])], c2)
    _run(c2.run_liquidations_forever())
    assert sleeps == [1.0, 2.0, 1.0]


def test_a_silent_okx_socket_gets_a_text_ping_and_pong_is_swallowed(monkeypatch):
    """Review of #374: OKX closes a socket silent for 30 s unless it receives a text "ping"."""
    got, cb = _collect()
    c = OKXClient("BTCUSDT", cb)
    c._ct_val = 0.01
    push = ('{"arg": {"channel": "liquidation-orders"}, "data": [{"instId": "BTC-USDT-SWAP", "details": '
            '[{"posSide": "short", "side": "buy", "bkPx": "60000", "sz": "2", "ts": "1759900000000"}]}]}')
    ws = _FakeWS(["SILENCE", "pong", push])
    _loop_with(monkeypatch, [ws], c)
    _run(c.run_liquidations_forever())
    assert ws.sent[1:] == ["ping"] and [x.side for x in got] == ["short"]


def test_the_okx_liquidation_channel_reports_alive_on_ack_push_and_pong_after_ack(monkeypatch):
    """Architect, 2026-10-08: the collector's liveness marker. A pong before the ack proves only the
    socket, not the channel; an error frame never marks it alive."""
    got, cb = _collect()
    alive = []

    async def on_alive(ex, ts):
        alive.append(ex)
    cb.on_liquidation_feed_alive = on_alive
    c = OKXClient("BTCUSDT", cb)
    c._ct_val = 0.01
    _run(c._liq_pong())                                              # before the ack: not alive
    assert alive == []
    _run(c._handle_liquidation_message({"event": "subscribe", "arg": {"channel": "liquidation-orders"}}))
    _run(c._liq_pong())
    _run(c._handle_liquidation_message(_okx_push([
        {"posSide": "long", "side": "sell", "bkPx": "60000", "sz": "1", "ts": "1759900000000"}])))
    assert alive == ["okx", "okx", "okx"]
    with pytest.raises(okx_client.SubscribeRefused):
        _run(c._handle_liquidation_message({"event": "error", "code": "60018", "msg": "x"}))
    assert alive == ["okx", "okx", "okx"]


class _BeatDB:
    def __init__(self, fail_at=()):
        self.written, self.pruned, self.calls, self.fail_at = [], [], 0, set(fail_at)

    async def insert_liquidation_feed_heartbeat(self, ex, symbol, ts):
        self.calls += 1
        if self.calls in self.fail_at:
            raise ConnectionError("db blip")
        self.written.append(ts.timestamp())

    async def prune_liquidation_feed_heartbeats(self, *, before):
        self.pruned.append(before.timestamp())
        return 0


def _manager_callbacks(db):
    from data_ingestion.manager import IngestionManager
    mgr = IngestionManager.__new__(IngestionManager)
    mgr.db, mgr.symbol, mgr.bar_builders = db, "BTCUSDT", {}
    return mgr._make_callbacks("okx")


def test_the_manager_writes_at_most_one_heartbeat_per_30_seconds_and_prunes_hourly():
    """Review of #398: 30 s, so one lost row on a quiet socket (pong every 25 s) leaves ~100 s, inside
    the beta's 150 s; rows older than 60 days are pruned at most once an hour."""
    from data_ingestion.manager import HEARTBEAT_EVERY_S, HEARTBEAT_KEEP_DAYS
    db = _BeatDB()
    cb = _manager_callbacks(db)
    for t in (100000.0, 100010.0, 100029.9, 100030.0, 100060.0, 103700.0):
        _run(cb.on_liquidation_feed_alive("okx", t))
    assert HEARTBEAT_EVERY_S == 30.0 and db.written == [100000.0, 100030.0, 100060.0, 103700.0]
    assert db.pruned == [100000.0 - HEARTBEAT_KEEP_DAYS * 86400.0, 103700.0 - HEARTBEAT_KEEP_DAYS * 86400.0]


def test_a_failed_heartbeat_insert_is_retried_on_the_next_signal():
    """Review of #398: the throttle was set before the insert, so a DB blip silenced the marker for
    a full window and made one or two NO_FEED buckets."""
    db = _BeatDB(fail_at={1})
    cb = _manager_callbacks(db)
    with pytest.raises(ConnectionError):
        _run(cb.on_liquidation_feed_alive("okx", 1000.0))
    _run(cb.on_liquidation_feed_alive("okx", 1001.0))       # the next pong: written, not throttled
    assert db.written == [1001.0]


def test_a_failing_heartbeat_write_neither_escapes_the_push_nor_loses_its_liquidations(caplog):
    """Architect, review of #398: the marker was awaited unguarded before the push's data, so one DB
    blip on the heartbeat dropped that push's liquidations and tore the socket down."""
    got, cb = _collect()
    db = _BeatDB(fail_at={1})
    cb.on_liquidation_feed_alive = _manager_callbacks(db).on_liquidation_feed_alive
    c = OKXClient("BTCUSDT", cb)
    c._ct_val = 0.01
    c._liq_live = True
    with caplog.at_level(logging.WARNING, logger=okx_client.logger.name):
        _run(c._handle_liquidation_message(_okx_push([
            {"posSide": "long", "side": "sell", "bkPx": "60000", "sz": "1", "ts": "1759900000000"}])))
    assert [x.side for x in got] == ["long"] and db.written == []
    assert "liveness marker not written" in caplog.text
    _run(c._liq_pong())                                      # the next signal writes it (not throttled)
    assert len(db.written) == 1


def test_a_failing_heartbeat_prune_never_raises_into_the_socket_loop():
    class _PruneFails(_BeatDB):
        async def prune_liquidation_feed_heartbeats(self, *, before):
            raise ConnectionError("db blip")
    db = _PruneFails()
    cb = _manager_callbacks(db)
    _run(cb.on_liquidation_feed_alive("okx", 100000.0))      # no raise
    _run(cb.on_liquidation_feed_alive("okx", 100030.0))
    assert db.written == [100000.0, 100030.0]
