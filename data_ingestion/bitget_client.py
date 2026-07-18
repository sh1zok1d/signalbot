"""
Bitget USDT-M futures perpetual.

WS: `trade` channel (price/taker flow).
Liquidations: Bitget does not expose a reliable public real-time liquidation
feed comparable to Binance/Bybit. We do NOT fabricate one. `on_liquidation`
is simply never called for this client — spec 1.6
(`count_only_valid_sources: true`, `min_available_for_capitulation: 2`)
already accounts for a source being unavailable, so consensus logic in
signal_engine (stage 2) should treat Bitget as a valid price/OI/orderflow
source but NOT a liquidation source. Revisit if Bitget ships a public feed.

REST poll: open interest, funding rate, mark price.

VERIFY: confirm exact endpoint paths/fields against current Bitget v2 API
docs before going live — no network access in this sandbox to check.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time

import aiohttp
import websockets

from .base_client import (ExchangeClient, Trade, OpenInterest, Funding,
                           MarkPrice, ClientCallbacks)

logger = logging.getLogger(__name__)

WS_URL = "wss://ws.bitget.com/v2/ws/public"
REST_BASE = "https://api.bitget.com"
PRODUCT_TYPE = "USDT-FUTURES"


class BitgetClient(ExchangeClient):
    name = "bitget"
    provides_liquidations = False

    def __init__(self, symbol: str, callbacks: ClientCallbacks, poll_interval_s: float = 15.0):
        super().__init__(symbol, callbacks)
        self._poll_interval_s = poll_interval_s

    async def _run_once(self) -> None:
        async with websockets.connect(WS_URL, ping_interval=20, ping_timeout=20) as ws:
            await ws.send(json.dumps({
                "op": "subscribe",
                "args": [{"instType": PRODUCT_TYPE, "channel": "trade", "instId": self.symbol}],
            }))
            logger.info("[bitget] WS connected, subscribed trade")
            self.touch()
            async for raw in ws:
                self.touch()
                if raw == "pong":
                    continue
                await self._handle_message(json.loads(raw))
                if self._stop.is_set():
                    break

    async def _handle_message(self, msg: dict) -> None:
        if msg.get("arg", {}).get("channel") != "trade":
            return
        for t in msg.get("data", []):
            # side == "sell" -> taker sold (aggressor sell)
            trade = Trade(
                exchange=self.name,
                symbol=self.symbol,
                ts=int(t["ts"]) / 1000.0,
                price=float(t["price"]),
                qty=float(t["size"]),
                is_buyer_maker=(t["side"] == "sell"),
            )
            await self.callbacks.on_trade(trade)

    # ------------------------------------------------------------
    async def run_poll_forever(self) -> None:
        async with aiohttp.ClientSession() as session:
            while not self._stop.is_set():
                try:
                    await self._poll_once(session)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    logger.warning("[bitget] poll error: %s", exc)
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=self._poll_interval_s)
                except asyncio.TimeoutError:
                    pass

    async def _poll_once(self, session: aiohttp.ClientSession) -> None:
        now = time.time()
        async with session.get(f"{REST_BASE}/api/v2/mix/market/open-interest",
                                params={"symbol": self.symbol, "productType": PRODUCT_TYPE}) as resp:
            oi_payload = await resp.json()
        oi_item = oi_payload["data"]
        # Some Bitget responses nest a list under "openInterestList"
        if isinstance(oi_item, dict) and "openInterestList" in oi_item:
            oi_item = oi_item["openInterestList"][0]
        # Bitget mix open-interest `size` is in base asset (BTC), verified by
        # magnitude (~35k BTC, in line with the other venues). No USD provided.
        await self.callbacks.on_oi(OpenInterest(
            exchange=self.name, symbol=self.symbol, ts=now,
            oi_raw=float(oi_item["size"]), oi_unit="base", oi_base_asset="BTC",
        ))

        async with session.get(f"{REST_BASE}/api/v2/mix/market/ticker",
                                params={"symbol": self.symbol, "productType": PRODUCT_TYPE}) as resp:
            tk_payload = await resp.json()
        tk_item = tk_payload["data"][0]
        await self.callbacks.on_mark_price(MarkPrice(
            exchange=self.name, symbol=self.symbol, ts=now,
            mark_price=float(tk_item["markPrice"]),
        ))
        await self.callbacks.on_funding(Funding(
            exchange=self.name, symbol=self.symbol, ts=now,
            funding_rate=float(tk_item["fundingRate"]),
            next_funding_time=None,
        ))
