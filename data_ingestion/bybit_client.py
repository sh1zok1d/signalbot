"""
Bybit v5 linear perpetuals.

WS: publicTrade.<symbol> (price/taker flow), liquidation.<symbol>.
REST poll: /v5/market/tickers (bundles markPrice + fundingRate + openInterest
in one call, so a single poll covers all three).

VERIFY: as with the other clients, confirm exact field names against current
Bybit v5 docs before going live — no network access in this sandbox to check.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time

import aiohttp
import websockets

from .base_client import (ExchangeClient, Trade, OpenInterest, Funding,
                           MarkPrice, Liquidation, ClientCallbacks)

logger = logging.getLogger(__name__)

WS_URL = "wss://stream.bybit.com/v5/public/linear"
REST_BASE = "https://api.bybit.com"


class BybitClient(ExchangeClient):
    name = "bybit"

    def __init__(self, symbol: str, callbacks: ClientCallbacks, poll_interval_s: float = 15.0):
        super().__init__(symbol, callbacks)
        self._poll_interval_s = poll_interval_s

    async def _run_once(self) -> None:
        async with websockets.connect(WS_URL, ping_interval=20, ping_timeout=20) as ws:
            await ws.send(json.dumps({
                "op": "subscribe",
                # NOTE: the v5 topic is `allLiquidation.{symbol}`. The old
                # `liquidation.{symbol}` topic was removed; subscribing to it
                # makes Bybit reject the WHOLE subscribe frame
                # ("handler not found"), which also killed publicTrade and left
                # us with zero live bars. Verified live.
                "args": [f"publicTrade.{self.symbol}", f"allLiquidation.{self.symbol}"],
            }))
            logger.info("[bybit] WS connected, subscribed")
            self.touch()
            async for raw in ws:
                self.touch()
                await self._handle_message(json.loads(raw))
                if self._stop.is_set():
                    break

    async def _handle_message(self, msg: dict) -> None:
        topic = msg.get("topic", "")
        if topic.startswith("publicTrade."):
            for t in msg.get("data", []):
                # S == "Sell" -> taker sold (aggressor sell)
                trade = Trade(
                    exchange=self.name,
                    symbol=self.symbol,
                    ts=int(t["T"]) / 1000.0,
                    price=float(t["p"]),
                    qty=float(t["v"]),
                    is_buyer_maker=(t["S"] == "Sell"),
                )
                await self.callbacks.on_trade(trade)
        elif topic.startswith("allLiquidation."):
            # v5 allLiquidation payload: list of {T: ms, s, S: "Buy"/"Sell",
            # v: size, p: price}. S is the side of the liquidation order:
            # "Buy" -> a short was force-bought back (short liquidated),
            # "Sell" -> a long was force-sold (long liquidated).
            d = msg.get("data", {})
            items = d if isinstance(d, list) else [d]
            for item in items:
                side = "short" if item.get("S") == "Buy" else "long"
                price = float(item["p"])
                qty = float(item["v"])
                await self.callbacks.on_liquidation(Liquidation(
                    exchange=self.name, symbol=self.symbol,
                    ts=int(item["T"]) / 1000.0,
                    side=side, price=price, qty=qty, notional=price * qty,
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
                    logger.warning("[bybit] poll error: %s", exc)
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=self._poll_interval_s)
                except asyncio.TimeoutError:
                    pass

    async def _poll_once(self, session: aiohttp.ClientSession) -> None:
        now = time.time()
        async with session.get(f"{REST_BASE}/v5/market/tickers",
                                params={"category": "linear", "symbol": self.symbol}) as resp:
            payload = await resp.json()
        item = payload["result"]["list"][0]

        # Bybit tickers: openInterest in base (BTC), openInterestValue in USD
        # (verified: 54912 BTC ~ 3.52B USD). USD notional is provided directly.
        await self.callbacks.on_oi(OpenInterest(
            exchange=self.name, symbol=self.symbol, ts=now,
            oi_raw=float(item["openInterest"]), oi_unit="base", oi_base_asset="BTC",
            oi_notional_usd=float(item.get("openInterestValue", 0) or 0) or None,
        ))
        await self.callbacks.on_mark_price(MarkPrice(
            exchange=self.name, symbol=self.symbol, ts=now,
            mark_price=float(item["markPrice"]),
        ))
        await self.callbacks.on_funding(Funding(
            exchange=self.name, symbol=self.symbol, ts=now,
            funding_rate=float(item["fundingRate"]),
            next_funding_time=float(item["nextFundingTime"]) / 1000.0
            if item.get("nextFundingTime") else None,
        ))
