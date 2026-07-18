"""
Orchestrates all exchange clients, wires their events into storage, and
tracks coverage per spec section 5:

  4/4 -> full_operation
  3/4 -> operate_normally_lower_score
  2/4 -> no_new_TRIGGERED_only_EARLY_and_status_LOW_confidence
  1_or_0_of_4 -> pause_signal_engine_critical_alert

Stage 1 scope: connect, ingest, persist, and expose coverage state via Redis
+ connectivity_events. Actual Telegram SYSTEM ALERT delivery is stage 3; for
now disconnect/restore/coverage-change events are logged and written to
Postgres so nothing is lost once telegram_bot/ lands.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, List

from common.config import Config
from storage.db import Database
from storage.redis_client import RedisState

from .base_client import ClientCallbacks, ExchangeClient, Trade, OpenInterest, Funding, MarkPrice, Liquidation
from .bar_builder import LiveBarBuilder, Bar1m
from .binance_client import BinanceClient
from .bybit_client import BybitClient
from .okx_client import OKXClient
from .bitget_client import BitgetClient

logger = logging.getLogger(__name__)

CLIENT_CLASSES = {
    "binance": BinanceClient,
    "bybit": BybitClient,
    "okx": OKXClient,
    "bitget": BitgetClient,
}


class IngestionManager:
    def __init__(self, cfg: Config, db: Database, redis_state: RedisState):
        self.cfg = cfg
        self.db = db
        self.redis = redis_state
        self.symbol = cfg.symbol
        self.exchanges: List[str] = cfg.enabled_exchanges
        self.clients: Dict[str, ExchangeClient] = {}
        self.bar_builders: Dict[str, LiveBarBuilder] = {}
        self._tasks: List[asyncio.Task] = []
        self._stop = asyncio.Event()
        self._alert_after_s = cfg["reliability"]["exchange_alert_after_min"] * 60
        self._heartbeat_after_s = cfg["reliability"]["heartbeat_alert_after_min"] * 60
        # Manager-owned outage bookkeeping, keyed by exchange. We track this
        # here rather than on the client because client.touch() resets the
        # client's own flags on every inbound message, which would race the
        # coverage loop and lose the disconnect->restore transition (and its
        # downtime, which the stage-3 "restored" alert needs).
        # value: {"since": epoch_s, "alerted": bool} while an outage is open.
        self._outages: Dict[str, dict] = {}

    # ------------------------------------------------------------
    def _make_callbacks(self, exchange: str) -> ClientCallbacks:
        builder = LiveBarBuilder(exchange, self.symbol, self._on_bar_closed)
        self.bar_builders[exchange] = builder

        async def on_trade(t: Trade) -> None:
            await builder.add_trade(t)

        async def on_oi(o: OpenInterest) -> None:
            await self.db.insert_open_interest(
                [(o.exchange, o.symbol, _to_ts(o.ts), o.oi_raw, o.oi_unit,
                  o.contract_value, o.oi_base_asset, o.oi_notional_usd)],
                source="live",
            )

        async def on_funding(f: Funding) -> None:
            await self.db.insert_funding(
                [(f.exchange, f.symbol, _to_ts(f.ts), f.funding_rate,
                  _to_ts(f.next_funding_time) if f.next_funding_time else None)],
                source="live",
            )

        async def on_mark_price(m: MarkPrice) -> None:
            await self.db.insert_mark_price(
                [(m.exchange, m.symbol, _to_ts(m.ts), m.mark_price)],
                source="live",
            )

        async def on_liquidation(l: Liquidation) -> None:
            await self.db.insert_liquidations([(
                l.exchange, l.symbol, _to_ts(l.ts), l.side, l.price, l.qty,
                l.notional, l.is_snapshot_feed,
            )])
            logger.info("[%s] LIQUIDATION %s side=%s qty=%.4f price=%.2f",
                        l.exchange, l.symbol, l.side, l.qty, l.price)

        return ClientCallbacks(
            on_trade=on_trade, on_oi=on_oi, on_funding=on_funding,
            on_mark_price=on_mark_price, on_liquidation=on_liquidation,
        )

    async def _on_bar_closed(self, bar: Bar1m) -> None:
        await self.db.insert_klines([bar.as_row()], source="live")

    # ------------------------------------------------------------
    async def start(self) -> None:
        for exchange in self.exchanges:
            cls = CLIENT_CLASSES[exchange]
            client = cls(self.symbol, self._make_callbacks(exchange))
            self.clients[exchange] = client
            self._tasks.append(asyncio.create_task(client.run_forever(), name=f"{exchange}-ws"))
            if hasattr(client, "run_poll_forever"):
                self._tasks.append(asyncio.create_task(client.run_poll_forever(), name=f"{exchange}-poll"))
            if hasattr(client, "run_liquidations_forever"):
                self._tasks.append(asyncio.create_task(client.run_liquidations_forever(), name=f"{exchange}-liq"))

        self._tasks.append(asyncio.create_task(self._coverage_loop(), name="coverage-loop"))
        self._tasks.append(asyncio.create_task(self._heartbeat_loop(), name="heartbeat-loop"))
        logger.info("Ingestion manager started for %s across %s", self.symbol, self.exchanges)

    async def stop(self) -> None:
        self._stop.set()
        for client in self.clients.values():
            client.stop()
        for builder in self.bar_builders.values():
            await builder.flush()
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    # ------------------------------------------------------------
    async def _coverage_loop(self, interval_s: float = 15.0) -> None:
        while not self._stop.is_set():
            connected_count = 0
            for exchange, client in self.clients.items():
                idle = client.seconds_since_last_message()
                healthy = client.state.connected and idle < self._alert_after_s
                if healthy:
                    connected_count += 1

                await self.redis.set_exchange_status(exchange, {
                    "connected": client.state.connected,
                    "healthy": healthy,
                    "seconds_since_last_message": round(idle, 1),
                    "connect_attempts": client.state.connect_attempts,
                    "in_outage": exchange in self._outages,
                })

                await self._track_outage(exchange, healthy, idle)

            coverage = f"{connected_count}/{len(self.exchanges)}"
            logger.debug("Coverage: %s", coverage)

            try:
                await asyncio.wait_for(self._stop.wait(), timeout=interval_s)
            except asyncio.TimeoutError:
                pass

    async def _track_outage(self, exchange: str, healthy: bool, idle: float) -> None:
        """Open/close a per-exchange outage and log disconnect/restore events.

        Stage 1 only persists these to connectivity_events + logs; stage 3's
        telegram_bot turns them into the SYSTEM ALERT / "restored" messages
        (spec section 5). Downtime is measured from the last good message.
        """
        outage = self._outages.get(exchange)

        if not healthy:
            if outage is None:
                # Just crossed into an outage. Anchor downtime at the last
                # message we actually saw, not "now".
                self._outages[exchange] = {"since": time.time() - idle, "alerted": False}
                outage = self._outages[exchange]
            if not outage["alerted"] and idle >= self._alert_after_s:
                outage["alerted"] = True
                logger.warning("SYSTEM ALERT: %s down for %.0fs (coverage degraded)", exchange, idle)
                await self.db.log_connectivity_event(exchange, "disconnect", {
                    "idle_seconds": round(idle, 1),
                })
            return

        # healthy again
        if outage is not None:
            downtime_s = time.time() - outage["since"]
            del self._outages[exchange]
            if outage["alerted"]:
                # Only announce a restore if we previously announced the drop,
                # so brief blips that never alerted stay silent (spec:
                # "short_drop: auto_reconnect_silently").
                logger.info("%s connection restored | downtime: %.0fs", exchange, downtime_s)
                await self.db.log_connectivity_event(exchange, "restore", {
                    "downtime_seconds": round(downtime_s, 1),
                    "coverage": f"{sum(1 for c in self.clients.values() if c.state.connected)}/{len(self.exchanges)}",
                })

    async def _heartbeat_loop(self, interval_s: float = 30.0) -> None:
        while not self._stop.is_set():
            await self.redis.set_heartbeat()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=interval_s)
            except asyncio.TimeoutError:
                pass

    def coverage_summary(self) -> dict:
        summary = {}
        for exchange, client in self.clients.items():
            summary[exchange] = {
                "connected": client.state.connected,
                "idle_s": round(client.seconds_since_last_message(), 1),
            }
        return summary


def _to_ts(epoch_s: float):
    from datetime import datetime, timezone
    return datetime.fromtimestamp(epoch_s, tz=timezone.utc)
