"""
Stage 2 forecast-outcome future-kline reader: fetch the future 1m klines for one
horizon evaluation window. Pure storage layer — static/trusted SQL, an immutable
detached result, NO analytics import, no computation, no clock, no writes.

klines_1m has no market_type column, so the query never references one.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Mapping


class ForecastOutcomeReaderError(ValueError):
    """Invalid future-kline request argument (validated before any DB access)."""


# Static, trusted SQL — no SELECT *, no dynamic identifiers, no market_type.
FORECAST_OUTCOME_KLINES_SQL = """
SELECT exchange, symbol, ts, open, high, low, close
FROM klines_1m
WHERE exchange = $1
  AND symbol = $2
  AND ts >= $3
  AND ts < $4
ORDER BY ts ASC
"""

# Evaluation-window durations (minutes) allowed by the 15m/1h/4h horizons.
_ALLOWED_DURATION_MINUTES = (15, 60, 240)


def _utc_whole_minute(dt, name: str) -> None:
    if not isinstance(dt, datetime):
        raise ForecastOutcomeReaderError(f"{name} must be a datetime, got {type(dt).__name__}")
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ForecastOutcomeReaderError(f"{name} must be timezone-aware")
    if dt.utcoffset() != timedelta(0):
        raise ForecastOutcomeReaderError(f"{name} must be UTC (offset 0), got {dt.utcoffset()}")
    if dt.second != 0 or dt.microsecond != 0:
        raise ForecastOutcomeReaderError(f"{name} must be on a whole minute")


def validate_forecast_outcome_reader_args(
    *,
    exchange: str,
    symbol: str,
    window_start: datetime,
    window_end: datetime,
) -> None:
    """Validate the request BEFORE any DB access."""
    if not isinstance(exchange, str) or not exchange.strip():
        raise ForecastOutcomeReaderError("exchange must be a non-empty string")
    if not isinstance(symbol, str) or not symbol.strip():
        raise ForecastOutcomeReaderError("symbol must be a non-empty string")
    _utc_whole_minute(window_start, "window_start")
    _utc_whole_minute(window_end, "window_end")
    if not (window_start < window_end):
        raise ForecastOutcomeReaderError("window_start must be < window_end")
    duration_minutes = (window_end - window_start).total_seconds() / 60.0
    if duration_minutes not in _ALLOWED_DURATION_MINUTES:
        raise ForecastOutcomeReaderError(
            f"window duration must be one of {list(_ALLOWED_DURATION_MINUTES)} minutes, "
            f"got {duration_minutes}")


async def read_forecast_outcome_klines(
    conn,
    *,
    exchange: str,
    symbol: str,
    window_start: datetime,
    window_end: datetime,
) -> tuple[Mapping, ...]:
    """One conn.fetch with the static SQL; return a detached tuple of
    MappingProxyType rows in SQL (chronological) order. Args are NOT re-validated
    here — the Database method validates before acquiring."""
    records = await conn.fetch(
        FORECAST_OUTCOME_KLINES_SQL, exchange, symbol, window_start, window_end)
    return tuple(MappingProxyType(dict(record)) for record in records)
