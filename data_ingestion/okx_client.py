"""
OKX USDT-perpetual swap. The venue-native instrument id is derived from the
canonical symbol via common.symbol_mapper — no hardcoded instrument literal here.

WS: `trades` and `liquidation-orders` on the public WS (`/ws/v5/public`; the
OKX v5 docs list liquidation-orders there, and `/ws/v5/business` refuses it with
error 60018 -- the cause of zero stored OKX liquidations until 2026-10, see
docs/BETA_DATA_RELIABILITY_FIX_PLAN_V1.md R1). The docs also say the channel
"doesn't represent the total number of liquidations on OKX": it is an
incomplete, `aggregated` source (common/capabilities.py), never a total.
`sz` is in contracts: notional = bkPx x sz x ctVal, with ctVal fetched from the
instruments endpoint before subscribing (fail-closed: no ctVal, no feed).
If it proves unreliable, prefer running with `min_available_for_capitulation:
2` (config.yaml consensus.liquidations_min_sources) so OKX isn't a hard
dependency.

REST poll: open-interest, funding-rate, mark-price public endpoints.

VERIFY: confirm exact channel/field names against current OKX v5 docs before
going live — no network access in this sandbox to check.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time

from typing import Optional

import aiohttp
import websockets

from common.instrument_metadata import InstrumentMetadataError, parse_okx
from common.symbol_mapper import to_exchange_symbol

from .base_client import (ExchangeClient, Trade, OpenInterest, Funding,
                           MarkPrice, Liquidation, ClientCallbacks)

logger = logging.getLogger(__name__)

WS_PUBLIC_URL = "wss://ws.okx.com:8443/ws/v5/public"
# liquidation-orders is a /public channel (OKX v5 docs); /business answers 60018
WS_LIQUIDATION_URL = WS_PUBLIC_URL
REST_BASE = "https://www.okx.com"


# OKX closes a connection that receives nothing for 30 s; it wants a text "ping" (answered "pong"),
# not only the protocol ping the websockets library sends.
TEXT_PING_AFTER_S = 25.0


class SubscribeRefused(RuntimeError):
    """OKX answered a subscribe with an error frame: the connection is closed and retried with backoff."""


def _log_control_frame(msg: dict, feed: str) -> bool:
    """OKX answers a subscribe with {"event": "subscribe"} or {"event": "error", "code", "msg"}.
    Log both (an error was silently dropped before, docs/BETA_DATA_RELIABILITY_FIX_PLAN_V1.md R1);
    True when the frame was a control frame. An error raises SubscribeRefused after logging."""
    event = msg.get("event")
    if event is None:
        return False
    if event == "error":
        logger.error("[okx] %s subscribe refused: code=%s msg=%s", feed, msg.get("code"), msg.get("msg"))
        raise SubscribeRefused(f"{feed}: code={msg.get('code')}")
    logger.info("[okx] %s %s: %s", feed, event, msg.get("arg"))
    return True


async def _frames(ws, stop: asyncio.Event, on_pong=None):
    """The text frames of `ws`, sending OKX's text "ping" after TEXT_PING_AFTER_S of silence;
    "pong" answers are swallowed (and reported to `on_pong`)."""
    while not stop.is_set():
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=TEXT_PING_AFTER_S)
        except asyncio.TimeoutError:
            await ws.send("ping")
            continue
        if raw == "pong":
            if on_pong is not None:
                await on_pong()
            continue
        yield raw


def liquidation_side(detail: dict) -> Optional[str]:
    """The side that was liquidated. posSide is long/short in hedge mode; in net mode it is
    "net" and the liquidation order's own side says it: a forced buy closes a short, a forced
    sell closes a long. None when neither is readable (the row is skipped, never guessed)."""
    pos = detail.get("posSide")
    if pos in ("long", "short"):
        return pos
    side = detail.get("side")
    if side == "buy":
        return "short"
    if side == "sell":
        return "long"
    return None


class OKXClient(ExchangeClient):
    name = "okx"

    def __init__(self, symbol: str, callbacks: ClientCallbacks, poll_interval_s: float = 15.0):
        super().__init__(symbol, callbacks)
        self._poll_interval_s = poll_interval_s
        # Canonical symbol (self.symbol) stays in every outgoing object / DB row;
        # the OKX-native instrument id is used only for API/WS requests.
        self._inst_id = to_exchange_symbol("okx", symbol, "perp")
        self._ct_val: Optional[float] = None    # BTC per contract, from the instruments endpoint
        self._liq_live = False                  # the current liquidation socket was acknowledged

    async def _run_once(self) -> None:
        async with websockets.connect(WS_PUBLIC_URL, ping_interval=20, ping_timeout=20) as ws:
            await ws.send(json.dumps({
                "op": "subscribe",
                "args": [{"channel": "trades", "instId": self._inst_id}],
            }))
            logger.info("[okx] public WS connected, subscribed trades")
            self.touch()
            async for raw in _frames(ws, self._stop):
                self.touch()
                await self._handle_public_message(json.loads(raw))

    async def _handle_public_message(self, msg: dict) -> None:
        if _log_control_frame(msg, "trades"):
            return
        if msg.get("arg", {}).get("channel") != "trades":
            return
        for t in msg.get("data", []):
            # side == "sell" -> taker sold (aggressor sell)
            trade = Trade(
                exchange=self.name,
                symbol=self.symbol,
                ts=int(t["ts"]) / 1000.0,
                price=float(t["px"]),
                qty=float(t["sz"]),
                is_buyer_maker=(t["side"] == "sell"),
            )
            await self.callbacks.on_trade(trade)

    # ------------------------------------------------------------
    # Best-effort liquidation feed on its own public-WS connection, so a
    # failure here doesn't take down trades. No ctVal, no subscription.
    # ------------------------------------------------------------
    async def _fetch_ct_val(self) -> float:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{REST_BASE}/api/v5/public/instruments",
                                   params={"instType": "SWAP", "instId": self._inst_id}) as resp:
                payload = await resp.json()
        return parse_okx(payload, self.symbol).contract_multiplier

    async def run_liquidations_forever(self) -> None:
        backoff = 1.0
        while not self._stop.is_set():
            try:
                if self._ct_val is None:
                    try:
                        self._ct_val = await self._fetch_ct_val()
                    except InstrumentMetadataError as exc:
                        logger.error("[okx] liquidation feed not started, no usable ctVal: %s", exc)
                        raise
                async with websockets.connect(WS_LIQUIDATION_URL, ping_interval=20,
                                               ping_timeout=20) as ws:
                    await ws.send(json.dumps({
                        "op": "subscribe",
                        "args": [{"channel": "liquidation-orders", "instType": "SWAP"}],
                    }))
                    logger.info("[okx] public WS connected, subscribing liquidation-orders (ctVal=%s)",
                                self._ct_val)
                    self._liq_live = False
                    async for raw in _frames(ws, self._stop, on_pong=self._liq_pong):
                        await self._handle_liquidation_message(json.loads(raw))
                        if self._liq_live:
                            backoff = 1.0    # reset only once OKX acknowledged the subscription
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.warning("[okx] liquidation feed error: %s", exc)
            if self._stop.is_set():
                break
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)

    async def _feed_alive(self) -> None:
        """The liveness marker of the liquidation channel (collector side of data reliability D2)."""
        cb = getattr(self.callbacks, "on_liquidation_feed_alive", None)
        if cb is None:
            return
        try:
            await cb(self.name, time.time())
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - a marker write never tears down the socket
            logger.warning("[okx] liquidation liveness marker not written: %s", exc)

    async def _liq_pong(self) -> None:
        if self._liq_live:                    # a pong proves the socket; the ack proved the channel
            await self._feed_alive()

    async def _handle_liquidation_message(self, msg: dict) -> None:
        if _log_control_frame(msg, "liquidation-orders"):
            if msg.get("event") == "subscribe":
                self._liq_live = True
                await self._feed_alive()
            return
        if msg.get("arg", {}).get("channel") != "liquidation-orders":
            return
        self._liq_live = True
        if self._ct_val is not None:        # never stored without a usable multiplier (fail-closed)
            await self._store_liquidations(msg)
        await self._feed_alive()            # after the push's data: a marker blip never drops it

    async def _store_liquidations(self, msg: dict) -> None:
        for group in msg.get("data", []):
            if group.get("instId") != self._inst_id:
                continue
            for d in group.get("details", []):
                side = liquidation_side(d)
                if side is None:
                    logger.warning("[okx] liquidation without a readable side skipped")
                    continue
                price = float(d["bkPx"])
                qty = float(d["sz"]) * self._ct_val       # contracts -> BTC
                await self.callbacks.on_liquidation(Liquidation(
                    exchange=self.name, symbol=self.symbol,
                    ts=int(d["ts"]) / 1000.0,
                    side=side, price=price, qty=qty, notional=price * qty,
                    # the `aggregated` capability is not `snapshot`: the flag must be False, or
                    # input_adapter refuses the whole OKX feature vector for the bucket
                    is_snapshot_feed=False,
                ))

    # ------------------------------------------------------------
    async def run_poll_forever(self) -> None:
        async with aiohttp.ClientSession() as session:
            while not self._stop.is_set():
                try:
                    await self._poll_once(session)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    logger.warning("[okx] poll error: %s", exc)
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=self._poll_interval_s)
                except asyncio.TimeoutError:
                    pass

    async def _poll_once(self, session: aiohttp.ClientSession) -> None:
        now = time.time()
        async with session.get(f"{REST_BASE}/api/v5/public/open-interest",
                                params={"instType": "SWAP", "instId": self._inst_id}) as resp:
            oi_payload = await resp.json()
        oi_item = oi_payload["data"][0]
        # OKX reports oi in CONTRACTS (ctVal=0.01 BTC, verified via instruments
        # endpoint) and, helpfully, oiUsd directly. We keep the raw contracts
        # and take the exchange-provided USD notional rather than assuming any
        # coefficient. oiCcy (base BTC) is available too but oiUsd is what we
        # store as the normalized USD value.
        await self.callbacks.on_oi(OpenInterest(
            exchange=self.name, symbol=self.symbol, ts=now,
            oi_raw=float(oi_item["oi"]), oi_unit="contracts", oi_base_asset="BTC",
            oi_notional_usd=float(oi_item.get("oiUsd", 0) or 0) or None,
        ))

        async with session.get(f"{REST_BASE}/api/v5/public/funding-rate",
                                params={"instId": self._inst_id}) as resp:
            fr_payload = await resp.json()
        fr_item = fr_payload["data"][0]
        await self.callbacks.on_funding(Funding(
            exchange=self.name, symbol=self.symbol, ts=now,
            funding_rate=float(fr_item["fundingRate"]),
            next_funding_time=int(fr_item["nextFundingTime"]) / 1000.0,
        ))

        async with session.get(f"{REST_BASE}/api/v5/public/mark-price",
                                params={"instType": "SWAP", "instId": self._inst_id}) as resp:
            mp_payload = await resp.json()
        mp_item = mp_payload["data"][0]
        await self.callbacks.on_mark_price(MarkPrice(
            exchange=self.name, symbol=self.symbol, ts=now,
            mark_price=float(mp_item["markPx"]),
        ))
