"""Thin async Stage 2 shadow forecast-outcome pipeline for ONE horizon.

Composes: request validation (`build_forecast_outcome_window`) -> exactly one
future-kline read -> adapt raw rows to `OutcomePriceBar` -> the pure
`evaluate_forecast_outcome` -> (only when COMPLETE) exactly one outcome upsert.

No concrete Database import, no retries/sleeps/clock/logging, no `asyncio.gather`
or tasks, and no loop over horizons. Reader/evaluator/writer exceptions propagate
unchanged; an INCOMPLETE window never calls the writer.
"""
from __future__ import annotations

from collections.abc import Mapping as _AbcMapping, Sequence as _AbcSequence
from datetime import datetime
from typing import Mapping, Protocol, Sequence

from .outcomes import (
    DEFAULT_OUTCOME_VERSION, ForecastOutcome, ForecastOutcomeEvaluation,
    ForecastOutcomeInputError, OUTCOME_COMPLETE, OutcomePriceBar,
    build_forecast_outcome_window, evaluate_forecast_outcome,
)
from .persistence import ForecastPrediction

_REQUIRED_KLINE_KEYS = ("exchange", "symbol", "ts", "open", "high", "low", "close")


class ForecastOutcomeReader(Protocol):
    async def fetch_forecast_outcome_klines(
        self,
        *,
        exchange: str,
        symbol: str,
        window_start: datetime,
        window_end: datetime,
    ) -> Sequence[Mapping]:
        ...


class ForecastOutcomeWriter(Protocol):
    async def upsert_forecast_outcomes(
        self,
        rows: Sequence[ForecastOutcome],
    ) -> int:
        ...


def _adapt_price_bars(rows: Sequence[Mapping]) -> list[OutcomePriceBar]:
    """Adapt raw kline mappings into detached OutcomePriceBar objects (no asyncpg
    Record reference retained). Raises ForecastOutcomeInputError on a malformed
    container / row / key set."""
    if isinstance(rows, (str, bytes, bytearray)) or not isinstance(rows, _AbcSequence):
        raise ForecastOutcomeInputError(
            f"kline rows must be a Sequence, got {type(rows).__name__}")
    bars: list[OutcomePriceBar] = []
    for i, row in enumerate(rows):
        if not isinstance(row, _AbcMapping):
            raise ForecastOutcomeInputError(
                f"kline row {i} must be a mapping, got {type(row).__name__}")
        if set(row.keys()) != set(_REQUIRED_KLINE_KEYS):
            raise ForecastOutcomeInputError(
                f"kline row {i} keys must be exactly {list(_REQUIRED_KLINE_KEYS)}, "
                f"got {sorted(row.keys())}")
        bars.append(OutcomePriceBar(
            exchange=row["exchange"], symbol=row["symbol"], ts=row["ts"],
            open=row["open"], high=row["high"], low=row["low"], close=row["close"]))
    return bars


async def process_forecast_outcome_horizon(
    reader: ForecastOutcomeReader,
    writer: ForecastOutcomeWriter,
    prediction: ForecastPrediction,
    *,
    horizon: str,
    evaluation_exchange: str,
    outcome_version: str = DEFAULT_OUTCOME_VERSION,
) -> ForecastOutcomeEvaluation:
    """Process exactly ONE horizon for one prediction. See module docstring."""
    # 1. all request validation before any I/O
    window = build_forecast_outcome_window(
        prediction, horizon=horizon, evaluation_exchange=evaluation_exchange,
        outcome_version=outcome_version)

    # 2. exactly one future-kline read
    raw_rows = await reader.fetch_forecast_outcome_klines(
        exchange=window.evaluation_exchange, symbol=prediction.symbol,
        window_start=window.evaluation_start_ts, window_end=window.evaluation_end_ts)

    # 3. adapt raw mappings -> OutcomePriceBar (detached)
    price_bars = _adapt_price_bars(raw_rows)

    # 4. pure evaluation
    result = evaluate_forecast_outcome(prediction, window, price_bars=price_bars)

    # 5-6. only a COMPLETE evaluation is persisted (one upsert); return the result
    if result.status == OUTCOME_COMPLETE:
        await writer.upsert_forecast_outcomes((result.outcome,))
    return result
