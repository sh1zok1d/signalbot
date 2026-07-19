"""
OKX USDT-perpetual swap. The venue-native instrument id is derived from the
canonical symbol via common.symbol_mapper — no hardcoded instrument literal here.

WS: `trades` channel on the public WS (price/taker flow). OKX's
`liquidation-orders` channel lives on the separate "business" WS endpoint and
is aggregated/delayed rather than a true real-time per-order feed — treat it
as a lower-quality liquidation source, same spirit as Binance's snapshot feed.
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

import aiohttp
import websockets

from common.symbol_mapper import to_exchange_symbol

from .base_client import (ExchangeClient, Trade, OpenInterest, Funding,
                           MarkPrice, Liquidation, ClientCallbacks)

logger = logging.getLogger(__name__)

WS_PUBLIC_URL = "wss://ws.okx.com:8443/ws/v5/public"
WS_BUSINESS_URL = "wss://ws.okx.com:8443/ws/v5/business"
REST_BASE = "https://www.okx.com"


class OKXClient(ExchangeClient):
    name = "okx"

    def __init__(self, symbol: str, callbacks: ClientCallbacks, poll_interval_s: float = 15.0):
        super().__init__(symbol, callbacks)
        self._poll_interval_s = poll_interval_s
        # Canonical symbol (self.symbol) stays in every outgoing object / DB row;
        # the OKX-native instrument id is used only for API/WS requests.
        self._inst_id = to_exchange_symbol("okx", symbol, "perp")

    async def _run_once(self) -> None:
        async with websockets.connect(WS_PUBLIC_URL, ping_interval=20, ping_timeout=20) as ws:
            await ws.send(json.dumps({
                "op": "subscribe",
                "args": [{"channel": "trades", "instId": self._inst_id}],
            }))
            logger.info("[okx] public WS connected, subscribed trades")
            self.touch()
            async for raw in ws:
                self.touch()
                if raw == "pong":
                    continue
                await self._handle_public_message(json.loads(raw))
                if self._stop.is_set():
                    break

    async def _handle_public_message(self, msg: dict) -> None:
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
    # Best-effort liquidation feed on the business WS. Runs as an
    # independent connection so a failure here doesn't take down trades.
    # ------------------------------------------------------------
    async def run_liquidations_forever(self) -> None:
        backoff = 1.0
        while not self._stop.is_set():
            try:
                async with websockets.connect(WS_BUSINESS_URL, ping_interval=20,
                                               ping_timeout=20) as ws:
                    await ws.send(json.dumps({
                        "op": "subscribe",
                        "args": [{"channel": "liquidation-orders", "instType": "SWAP"}],
                    }))
                    logger.info("[okx] business WS connected, subscribed liquidation-orders")
                    backoff = 1.0
                    async for raw in ws:
                        if raw == "pong":
                            continue
                        await self._handle_liquidation_message(json.loads(raw))
                        if self._stop.is_set():
                            break
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.warning("[okx] liquidation feed error: %s", exc)
            if self._stop.is_set():
                break
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)

    async def _handle_liquidation_message(self, msg: dict) -> None:
        if msg.get("arg", {}).get("channel") != "liquidation-orders":
            return
        for group in msg.get("data", []):
            if group.get("instId") != self._inst_id:
                continue
            for d in group.get("details", []):
                # posSide == "long" -> a long position was force-closed
                side = d.get("posSide", "long")
                price = float(d["bkPx"])
                qty = float(d["sz"])
                await self.callbacks.on_liquidation(Liquidation(
                    exchange=self.name, symbol=self.symbol,
                    ts=int(d["ts"]) / 1000.0,
                    side=side, price=price, qty=qty, notional=price * qty,
                    is_snapshot_feed=True,  # aggregated/delayed, treat conservatively
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
