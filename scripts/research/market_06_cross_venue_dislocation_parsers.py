"""Exact MARKET-06 Binance USD-M and OKX spot parsers.

Network-free. Real retained snapshot bytes are refused unless a future
authenticated execution authorization exists (none exists now).
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from scripts.research.market_06_cross_venue_dislocation_authority import (
    Market06ExecutionNotAuthorized,
    Market06IncompleteExecution,
    refuse_real_retained_bytes,
    require_execution_authorization,
)


BAR_MS = 300_000
WINDOW_START_MS = int(datetime(2022, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
WINDOW_END_EXCLUSIVE_MS = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
BINANCE_SYMBOL = "BTCUSDT"
OKX_INST_ID = "BTC-USDT"
OKX_ROW_WIDTH = 9
OKX_CONFIRM = "1"


@dataclass(frozen=True)
class PerpBar:
    open_time_ms: int
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class SpotClose:
    open_time_ms: int
    close: float


def _finite_positive(value: Any, *, where: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise Market06IncompleteExecution(f"NON_NUMERIC:{where}") from exc
    if number != number or number in (float("inf"), float("-inf")) or number <= 0.0:
        raise Market06IncompleteExecution(f"NONFINITE_OR_NONPOSITIVE:{where}")
    return number


def _require_5m(ts: int, *, where: str) -> int:
    if ts % BAR_MS != 0:
        raise Market06IncompleteExecution(f"NOT_5M_ALIGNED:{where}:{ts}")
    return ts


def _require_window(ts: int, *, where: str) -> int:
    if not (WINDOW_START_MS <= ts < WINDOW_END_EXCLUSIVE_MS):
        raise Market06IncompleteExecution(f"OUTSIDE_HISTORICAL_WINDOW:{where}:{ts}")
    return ts


def parse_binance_klines_csv(text: str, *, source: str = "csv") -> list[PerpBar]:
    reader = csv.reader(io.StringIO(text))
    bars: list[PerpBar] = []
    seen: set[int] = set()
    for row in reader:
        if not row:
            continue
        first = row[0].strip().lower()
        if first in {"open_time", "open time"}:
            continue
        if len(row) < 5:
            raise Market06IncompleteExecution(f"BINANCE_SCHEMA:{source}")
        ts = _require_window(_require_5m(int(row[0]), where=source), where=source)
        if ts in seen:
            raise Market06IncompleteExecution(f"BINANCE_DUPLICATE:{source}:{ts}")
        seen.add(ts)
        open_px = _finite_positive(row[1], where=f"{source}.open")
        high_px = _finite_positive(row[2], where=f"{source}.high")
        low_px = _finite_positive(row[3], where=f"{source}.low")
        close_px = _finite_positive(row[4], where=f"{source}.close")
        if high_px < low_px:
            raise Market06IncompleteExecution(f"BINANCE_HIGH_LT_LOW:{source}:{ts}")
        bars.append(
            PerpBar(
                open_time_ms=ts,
                open=open_px,
                high=high_px,
                low=low_px,
                close=close_px,
            )
        )
    bars.sort(key=lambda bar: bar.open_time_ms)
    return bars


def parse_binance_zip_bytes(data: bytes, *, zip_name: str) -> list[PerpBar]:
    refuse_real_retained_bytes(data, where=zip_name)
    if BINANCE_SYMBOL not in zip_name or "-5m-" not in zip_name:
        raise Market06IncompleteExecution(f"BINANCE_IDENTITY:{zip_name}")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            csv_members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
            if len(csv_members) != 1:
                raise Market06IncompleteExecution(f"BINANCE_ZIP_MEMBERS:{zip_name}")
            raw = archive.read(csv_members[0])
    except zipfile.BadZipFile as exc:
        raise Market06IncompleteExecution(f"BINANCE_BAD_ZIP:{zip_name}") from exc
    return parse_binance_klines_csv(raw.decode("utf-8"), source=zip_name)


def parse_okx_history_body(data: bytes, *, source: str) -> list[SpotClose]:
    refuse_real_retained_bytes(data, where=source)
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Market06IncompleteExecution(f"OKX_JSON:{source}") from exc
    if str(payload.get("code")) != "0":
        raise Market06IncompleteExecution(f"OKX_CODE:{source}:{payload.get('code')}")
    rows = payload.get("data") or []
    if not isinstance(rows, list):
        raise Market06IncompleteExecution(f"OKX_DATA:{source}")
    closes: list[SpotClose] = []
    seen: set[int] = set()
    for row in rows:
        if not isinstance(row, list) or len(row) != OKX_ROW_WIDTH:
            raise Market06IncompleteExecution(f"OKX_SCHEMA:{source}")
        ts = _require_window(_require_5m(int(row[0]), where=source), where=source)
        confirm = str(row[8])
        if confirm != OKX_CONFIRM:
            raise Market06IncompleteExecution(f"OKX_CONFIRM:{source}:{confirm}")
        if ts in seen:
            raise Market06IncompleteExecution(f"OKX_DUPLICATE:{source}:{ts}")
        seen.add(ts)
        close_px = _finite_positive(row[4], where=f"{source}.close")
        closes.append(SpotClose(open_time_ms=ts, close=close_px))
    closes.sort(key=lambda item: item.open_time_ms)
    return closes


def reconstruct_canonical_dataset(*args: Any, **kwargs: Any) -> None:
    """Canonical reconstruction is execution. Refused in this unit."""

    require_execution_authorization(*args, **kwargs)
    raise Market06ExecutionNotAuthorized("MARKET_06_EXECUTION_NOT_AUTHORIZED")
