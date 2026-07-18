"""
Binance USDT-M Futures.

WS (real-time): aggTrade (price/taker flow), forceOrder (liquidations).
NOTE per spec: Binance's forceOrder stream is a *snapshot* feed capped at
~1 event/symbol/1000ms, so during cascades it under-reports actual
liquidation volume. We tag every row `is_snapshot_feed=True` so the
consensus/percentile logic (stage 2) can treat it as an incomplete source.

REST poll (OI has no official WS push on Binance Futures; funding/mark are
polled alongside it for simplicity and to keep one poll cadence per client).

WS URL CATEGORY (verified live 2026-07-16): Binance futures streams are split
by category and the category is part of the PATH:
  * /public/stream  -> bookTicker, depth (market-data-lite)
  * /market/stream  -> aggTrade, forceOrder, kline, markPrice (the trade tape)
aggTrade/forceOrder therefore MUST be subscribed on `/market/stream`. On
`/public/stream` they connect and are "accepted" but deliver ZERO frames — the
silent trade tape is a wrong-category endpoint, NOT a geo/IP block. Verified:
`/market/stream?streams=btcusdt@aggTrade/...` -> 25 aggTrade in 12s;
`/public/stream?streams=btcusdt@aggTrade` -> 0. (An earlier note here wrongly
attributed the silence to an EEA IP restriction; that was a mis-diagnosis from
never testing the /market path.)
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

# aggTrade + forceOrder live on the /market category (see module docstring).
WS_URL = "wss://fstream.binance.com/market/stream?streams={streams}"
REST_BASE = "https://fapi.binance.com"


class BinanceClient(ExchangeClient):
    name = "binance"

    def __init__(self, symbol: str, callbacks: ClientCallbacks, poll_interval_s: float = 15.0):
        super().__init__(symbol, callbacks)
        self._poll_interval_s = poll_interval_s
        self._sym_lower = symbol.lower()

    async def _run_once(self) -> None:
        streams = f"{self._sym_lower}@aggTrade/{self._sym_lower}@forceOrder"
        url = WS_URL.format(streams=streams)
        async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
            logger.info("[binance] WS connected")
            self.touch()
            async for raw in ws:
                self.touch()
                await self._handle_message(json.loads(raw))
                if self._stop.is_set():
                    break

    async def _handle_message(self, msg: dict) -> None:
        data = msg.get("data", {})
        etype = data.get("e")
        if etype == "aggTrade":
            trade = Trade(
                exchange=self.name,
                symbol=self.symbol,
                ts=data["T"] / 1000.0,
                price=float(data["p"]),
                qty=float(data["q"]),
                is_buyer_maker=bool(data["m"]),
            )
            await self.callbacks.on_trade(trade)
        elif etype == "forceOrder":
            o = data["o"]
            # S = "SELL" -> forced sell -> a long position was liquidated
            side = "long" if o["S"] == "SELL" else "short"
            qty = float(o["q"])
            price = float(o["ap"] or o["p"])
            liq = Liquidation(
                exchange=self.name,
                symbol=self.symbol,
                ts=o["T"] / 1000.0,
                side=side,
                price=price,
                qty=qty,
                notional=price * qty,
                is_snapshot_feed=True,
            )
            await self.callbacks.on_liquidation(liq)

    # ------------------------------------------------------------
    # REST polling: open interest, funding, mark price
    # ------------------------------------------------------------
    async def run_poll_forever(self) -> None:
        async with aiohttp.ClientSession() as session:
            while not self._stop.is_set():
                try:
                    await self._poll_once(session)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    logger.warning("[binance] poll error: %s", exc)
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=self._poll_interval_s)
                except asyncio.TimeoutError:
                    pass

    async def _poll_once(self, session: aiohttp.ClientSession) -> None:
        now = time.time()
        async with session.get(f"{REST_BASE}/fapi/v1/openInterest",
                                params={"symbol": self.symbol}) as resp:
            oi_data = await resp.json()
        # Binance /fapi/v1/openInterest returns the value in base asset (BTC),
        # verified by magnitude (~100k BTC). No USD notional from this endpoint.
        oi = OpenInterest(
            exchange=self.name, symbol=self.symbol, ts=now,
            oi_raw=float(oi_data["openInterest"]), oi_unit="base", oi_base_asset="BTC",
        )
        await self.callbacks.on_oi(oi)

        async with session.get(f"{REST_BASE}/fapi/v1/premiumIndex",
                                params={"symbol": self.symbol}) as resp:
            pi = await resp.json()
        await self.callbacks.on_mark_price(MarkPrice(
            exchange=self.name, symbol=self.symbol, ts=now,
            mark_price=float(pi["markPrice"]),
        ))
        await self.callbacks.on_funding(Funding(
            exchange=self.name, symbol=self.symbol, ts=now,
            funding_rate=float(pi["lastFundingRate"]),
            next_funding_time=float(pi["nextFundingTime"]) / 1000.0,
        ))
