"""
Aggregates raw trade ticks into closed 1-minute OHLCV bars with taker
buy/sell volume split, per exchange. This is what makes stage-1's
"получить, сохранить и провалидировать реальные 1m бары" (live side) work;
backfill/ fills in the historical 30 days via REST.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

from .base_client import Trade


@dataclass
class Bar1m:
    exchange: str
    symbol: str
    minute_start_ts: float
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    taker_buy_volume: float = 0.0
    taker_sell_volume: float = 0.0
    trades_count: int = 0

    def as_row(self) -> tuple:
        from datetime import datetime, timezone
        ts = datetime.fromtimestamp(self.minute_start_ts, tz=timezone.utc)
        return (
            self.exchange, self.symbol, ts,
            self.open, self.high, self.low, self.close, self.volume,
            self.taker_buy_volume, self.taker_sell_volume, self.trades_count,
        )


class LiveBarBuilder:
    def __init__(self, exchange: str, symbol: str,
                 on_bar_closed: Callable[[Bar1m], Awaitable[None]]):
        self.exchange = exchange
        self.symbol = symbol
        self._on_bar_closed = on_bar_closed
        self._bar: Optional[Bar1m] = None

    @staticmethod
    def _minute_bucket(ts: float) -> float:
        return (int(ts) // 60) * 60

    async def add_trade(self, trade: Trade) -> None:
        bucket = self._minute_bucket(trade.ts)

        if self._bar is None:
            self._bar = self._new_bar(bucket, trade.price)
        elif bucket != self._bar.minute_start_ts:
            await self._on_bar_closed(self._bar)
            self._bar = self._new_bar(bucket, trade.price)

        b = self._bar
        b.high = max(b.high, trade.price)
        b.low = min(b.low, trade.price)
        b.close = trade.price
        b.volume += trade.qty
        b.trades_count += 1
        # is_buyer_maker True -> taker was the seller (aggressor sell)
        if trade.is_buyer_maker:
            b.taker_sell_volume += trade.qty
        else:
            b.taker_buy_volume += trade.qty

    def _new_bar(self, bucket: float, price: float) -> Bar1m:
        return Bar1m(
            exchange=self.exchange, symbol=self.symbol, minute_start_ts=bucket,
            open=price, high=price, low=price, close=price,
        )

    async def flush(self) -> None:
        """Force-close whatever bar is in progress (used on shutdown)."""
        if self._bar is not None:
            await self._on_bar_closed(self._bar)
            self._bar = None
