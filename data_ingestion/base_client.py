"""
Abstract exchange client interface.

Each concrete client (binance/bybit/okx/bitget) implements `_run_once`, which
opens a WS connection and feeds normalized events into the callbacks passed
at construction time. `run_forever` wraps it with exponential backoff
reconnect and last-message tracking used for coverage / disconnect alerts
(spec 5: "short_drop: auto_reconnect_silently, alert_after_min: 3").
"""
from __future__ import annotations

import abc
import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    exchange: str
    symbol: str
    ts: float          # epoch seconds
    price: float
    qty: float
    is_buyer_maker: bool  # True => taker sold (aggressor was seller)


@dataclass
class OpenInterest:
    exchange: str
    symbol: str
    ts: float
    # Raw OI value exactly as the exchange reports it, plus what it means.
    # Do NOT compare/sum oi_raw across exchanges (units differ). Normalized
    # fields stay None unless directly provided or verified — no assumptions.
    oi_raw: Optional[float] = None
    oi_unit: Optional[str] = None            # 'base' | 'contracts' | 'usd'
    contract_value: Optional[float] = None   # base per contract, verified only
    oi_base_asset: Optional[str] = None      # e.g. 'BTC'
    oi_notional_usd: Optional[float] = None  # only when exchange returns USD


@dataclass
class Funding:
    exchange: str
    symbol: str
    ts: float
    funding_rate: float
    next_funding_time: Optional[float] = None


@dataclass
class MarkPrice:
    exchange: str
    symbol: str
    ts: float
    mark_price: float


@dataclass
class Liquidation:
    exchange: str
    symbol: str
    ts: float
    side: str           # 'long' | 'short' — side that got liquidated
    price: float
    qty: float
    notional: Optional[float] = None
    is_snapshot_feed: bool = False


@dataclass
class ClientCallbacks:
    on_trade: Callable[[Trade], Awaitable[None]]
    on_oi: Callable[[OpenInterest], Awaitable[None]]
    on_funding: Callable[[Funding], Awaitable[None]]
    on_mark_price: Callable[[MarkPrice], Awaitable[None]]
    on_liquidation: Callable[[Liquidation], Awaitable[None]]


@dataclass
class ConnectionState:
    connected: bool = False
    last_message_ts: float = field(default_factory=time.time)
    connect_attempts: int = 0
    disconnected_since: Optional[float] = None
    alert_sent_for_current_outage: bool = False


class ExchangeClient(abc.ABC):
    name: str = "base"

    def __init__(self, symbol: str, callbacks: ClientCallbacks,
                 max_backoff_s: float = 60.0):
        self.symbol = symbol
        self.callbacks = callbacks
        self.state = ConnectionState()
        self._max_backoff_s = max_backoff_s
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    def touch(self) -> None:
        """Call this every time any message (even a heartbeat/ping) arrives."""
        self.state.last_message_ts = time.time()
        if not self.state.connected:
            self.state.connected = True
        self.state.disconnected_since = None
        self.state.alert_sent_for_current_outage = False

    @abc.abstractmethod
    async def _run_once(self) -> None:
        """Open one WS connection and run until it dies or self._stop is set.
        Must call self.touch() on every inbound message."""
        raise NotImplementedError

    async def run_forever(self) -> None:
        backoff = 1.0
        while not self._stop.is_set():
            self.state.connect_attempts += 1
            try:
                await self._run_once()
                backoff = 1.0  # clean exit (e.g. planned reconnect) resets backoff
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - top-level resilience loop
                logger.warning("[%s] connection error: %s", self.name, exc)
            finally:
                self.state.connected = False
                if self.state.disconnected_since is None:
                    self.state.disconnected_since = time.time()

            if self._stop.is_set():
                break
            logger.info("[%s] reconnecting in %.1fs", self.name, backoff)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=backoff)
            except asyncio.TimeoutError:
                pass
            backoff = min(backoff * 2, self._max_backoff_s)

    def seconds_since_last_message(self) -> float:
        return time.time() - self.state.last_message_ts
