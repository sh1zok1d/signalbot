"""Tardis CSV parsing and production-equivalent 1-minute trade aggregation.

Trade aggregation follows data_ingestion.bar_builder.LiveBarBuilder:
minute bucket is floor(exchange event time) to 60 seconds, OHLC from trade
prices, volume is the sum of exchange-native amounts, and
is_buyer_maker True means the taker sold.

Tardis `side` is the liquidity taker (aggressor), documented as buy / sell /
unknown. That maps onto the live clients:

* Binance aggTrade `m` (isBuyerMaker) True => taker sold
* Bybit publicTrade `S == "Sell"` => is_buyer_maker
* OKX trades `side == "sell"` => is_buyer_maker

so Tardis side `sell` => is_buyer_maker True, side `buy` => False.
`unknown` does not get a guessed side and does not get multiplied by -1.
`amount` is the exchange-native quantity. It is not multiplied by ctVal here.
"""
from __future__ import annotations

import csv
import gzip
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .constants import (
    DERIVATIVE_TICKER_COLUMNS,
    TAKER_SIDE_BUY,
    TAKER_SIDE_SELL,
    TAKER_SIDE_UNKNOWN,
    TRADE_COLUMNS,
)


class SchemaError(ValueError):
    """The file is not the schema this audit is allowed to read."""


@dataclass(frozen=True)
class TradeRow:
    tardis_exchange: str
    tardis_symbol: str
    exchange_timestamp_us: int
    local_timestamp_us: int
    trade_id: str
    side: str
    price: float
    amount: float
    source_file_sha256: str
    sample_date: str


@dataclass
class MinuteBar:
    """Mutable accumulator. Converted to an immutable KlineBar by the caller."""

    minute_start: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    taker_buy_volume: float
    taker_sell_volume: float
    taker_split_complete: bool
    trades_count: int
    first_exchange_timestamp_us: int
    last_exchange_timestamp_us: int


def is_buyer_maker_from_tardis_side(side: str) -> bool | None:
    """Return the LiveBarBuilder flag, or None when the side is unknown."""
    if side == TAKER_SIDE_SELL:
        return True
    if side == TAKER_SIDE_BUY:
        return False
    if side == TAKER_SIDE_UNKNOWN:
        return None
    raise SchemaError(
        f"Tardis trade side {side!r} is not buy, sell, or unknown; "
        "refusing to substitute a side"
    )


def exchange_us_to_datetime(us: int) -> datetime:
    if us < 0:
        raise SchemaError(f"negative timestamp {us}")
    return datetime.fromtimestamp(us / 1_000_000, tz=timezone.utc)


def minute_start_from_us(us: int) -> datetime:
    """Match LiveBarBuilder._minute_bucket: int(seconds) // 60 * 60.

    A timestamp exactly on the next minute belongs to that next minute.
    Microseconds are truncated toward zero the same way int(ts) truncates a
    non-negative float second count.
    """
    seconds = us // 1_000_000
    bucket = (seconds // 60) * 60
    return datetime.fromtimestamp(bucket, tz=timezone.utc)


def require_columns(header: list[str], expected: tuple[str, ...], *, kind: str) -> None:
    if tuple(header) != expected:
        raise SchemaError(
            f"{kind} schema changed: expected {list(expected)} got {header}. "
            "This source is stopped; no substitute field is used."
        )


def _parse_us(value: str, *, field: str) -> int:
    if value is None or value == "":
        raise SchemaError(f"missing {field}")
    try:
        return int(value)
    except ValueError as exc:
        raise SchemaError(f"{field} is not an integer microsecond timestamp: {value!r}") from exc


def iter_csv_rows(path: str):
    with gzip.open(path, "rt", newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise SchemaError(f"{path} has no header") from exc
        yield header
        for row in reader:
            yield row


def iter_trades(path: str, *, sha256: str, sample_date: str,
                tardis_exchange: str, tardis_symbol: str):
    rows = iter_csv_rows(path)
    header = next(rows)
    require_columns(list(header), TRADE_COLUMNS, kind="trades")
    idx = {name: i for i, name in enumerate(header)}
    for raw in rows:
        if len(raw) != len(header):
            raise SchemaError(f"ragged trade row in {path}: {raw[:6]!r}")
        exchange = raw[idx["exchange"]]
        symbol = raw[idx["symbol"]]
        if exchange != tardis_exchange or symbol != tardis_symbol:
            raise SchemaError(
                f"trade row identity {exchange}/{symbol} does not match "
                f"{tardis_exchange}/{tardis_symbol}"
            )
        side = raw[idx["side"]]
        is_buyer_maker_from_tardis_side(side)  # reject unknown vocabulary immediately
        price = float(raw[idx["price"]])
        amount = float(raw[idx["amount"]])
        if not (price > 0) or amount < 0:
            raise SchemaError(f"invalid trade price/amount {price!r} {amount!r}")
        yield TradeRow(
            tardis_exchange=exchange,
            tardis_symbol=symbol,
            exchange_timestamp_us=_parse_us(raw[idx["timestamp"]], field="timestamp"),
            local_timestamp_us=_parse_us(raw[idx["local_timestamp"]], field="local_timestamp"),
            trade_id=raw[idx["id"]],
            side=side,
            price=price,
            amount=amount,
            source_file_sha256=sha256,
            sample_date=sample_date,
        )


def fold_trade(bars: dict[datetime, MinuteBar], trade: TradeRow) -> None:
    minute = minute_start_from_us(trade.exchange_timestamp_us)
    bar = bars.get(minute)
    if bar is None:
        bar = MinuteBar(
            minute_start=minute,
            open=trade.price,
            high=trade.price,
            low=trade.price,
            close=trade.price,
            volume=0.0,
            taker_buy_volume=0.0,
            taker_sell_volume=0.0,
            taker_split_complete=True,
            trades_count=0,
            first_exchange_timestamp_us=trade.exchange_timestamp_us,
            last_exchange_timestamp_us=trade.exchange_timestamp_us,
        )
        bars[minute] = bar
    bar.high = max(bar.high, trade.price)
    bar.low = min(bar.low, trade.price)
    bar.close = trade.price
    bar.volume += trade.amount
    bar.trades_count += 1
    bar.last_exchange_timestamp_us = trade.exchange_timestamp_us
    maker = is_buyer_maker_from_tardis_side(trade.side)
    if maker is None:
        bar.taker_split_complete = False
    elif maker:
        bar.taker_sell_volume += trade.amount
    else:
        bar.taker_buy_volume += trade.amount


def aggregate_trades(trades: list[TradeRow]) -> dict[datetime, MinuteBar]:
    """Build 1-minute bars. Input order does not matter.

    Sort is (exchange timestamp, local timestamp, original index), which is
    the deterministic stand-in for live arrival order. Amount is not rescaled.
    """
    ordered = sorted(
        enumerate(trades),
        key=lambda item: (
            item[1].exchange_timestamp_us,
            item[1].local_timestamp_us,
            item[0],
        ),
    )
    bars: dict[datetime, MinuteBar] = {}
    for _, trade in ordered:
        fold_trade(bars, trade)
    return bars


@dataclass(frozen=True)
class OpenInterestRow:
    tardis_exchange: str
    tardis_symbol: str
    exchange_timestamp_us: int
    local_timestamp_us: int
    open_interest: float | None
    source_file_sha256: str
    sample_date: str


def iter_open_interest(path: str, *, sha256: str, sample_date: str,
                       tardis_exchange: str, tardis_symbol: str):
    """Yield derivative_ticker rows. Empty open_interest stays None.

    Empty is not a market zero. The caller drops None values instead of
    filling them.
    """
    rows = iter_csv_rows(path)
    header = next(rows)
    require_columns(list(header), DERIVATIVE_TICKER_COLUMNS, kind="derivative_ticker")
    idx = {name: i for i, name in enumerate(header)}
    for raw in rows:
        if len(raw) != len(header):
            raise SchemaError(f"ragged derivative_ticker row in {path}")
        exchange = raw[idx["exchange"]]
        symbol = raw[idx["symbol"]]
        if exchange != tardis_exchange or symbol != tardis_symbol:
            raise SchemaError(
                f"derivative_ticker identity {exchange}/{symbol} does not match "
                f"{tardis_exchange}/{tardis_symbol}"
            )
        text = raw[idx["open_interest"]]
        oi: float | None
        if text == "":
            oi = None
        else:
            oi = float(text)
        yield OpenInterestRow(
            tardis_exchange=exchange,
            tardis_symbol=symbol,
            exchange_timestamp_us=_parse_us(raw[idx["timestamp"]], field="timestamp"),
            local_timestamp_us=_parse_us(raw[idx["local_timestamp"]], field="local_timestamp"),
            open_interest=oi,
            source_file_sha256=sha256,
            sample_date=sample_date,
        )


def bucket_bounds(bucket_ts: datetime) -> tuple[datetime, datetime]:
    if bucket_ts.tzinfo is None or bucket_ts.utcoffset() != timedelta(0):
        raise ValueError("bucket_ts must be timezone-aware UTC")
    if bucket_ts.second or bucket_ts.microsecond or bucket_ts.minute % 5:
        raise ValueError("bucket_ts must be an aligned UTC 5-minute start")
    return bucket_ts, bucket_ts + timedelta(minutes=5)


def in_half_open_bucket(ts: datetime, bucket_ts: datetime) -> bool:
    """True iff bucket_ts <= ts < bucket_ts + 5 minutes. The right edge is out."""
    start, end = bucket_bounds(bucket_ts)
    return start <= ts < end
