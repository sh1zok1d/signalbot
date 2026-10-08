"""Bounded loader for the equal-width support census.

Requests Binance spot BTCUSDT 5m months 2017-09 through 2019-12 only.
Does not request 2017-08, any month from 2020-01, or any 2025/2026 object.
Missing bars stay missing. This module scores no touch and no barrier.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from scripts.research.dh1.data import SPOT_INVENTORY, VISION, _get, _parse_kline_zip, cache_root, sha256_bytes

from . import constants as K


def allowed_months() -> list[str]:
    out: list[str] = []
    year, month = 2017, 9
    while (year, month) <= (2019, 12):
        out.append(f"{year:04d}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    if out[0] != K.FIRST_MONTH or out[-1] != K.LAST_MONTH or len(out) != 28:
        raise RuntimeError("equal-width month list drifted")
    if "2017-08" in out or "2020-01" in out:
        raise RuntimeError("equal-width month list includes a forbidden month")
    return out


def refuse_month(month: str) -> None:
    if month < K.FIRST_MONTH or month > K.LAST_MONTH:
        raise RuntimeError(f"equal-width census refuses spot month {month}")
    if month >= "2020-01" or month[:4] in {"2025", "2026"}:
        raise RuntimeError(f"equal-width census refuses protected month {month}")


def select_objects(inventory: dict) -> list[dict]:
    if inventory.get("DATASET_ID") != K.SURFACE_ID:
        raise RuntimeError("spot inventory is not DH1_BINANCE_SPOT_BTCUSDT_5M_V0")
    if inventory.get("INSTRUMENT") != K.VENUE or inventory.get("INTERVAL") != K.INTERVAL:
        raise RuntimeError("spot inventory is not Binance spot BTCUSDT 5m")
    source = str(inventory.get("SOURCE") or "")
    if "/spot/monthly/klines/BTCUSDT/5m/" not in source:
        raise RuntimeError("spot inventory source is not the official spot kline path")
    by_month = {obj["MONTH"]: obj for obj in inventory["OBJECTS"]}
    chosen = []
    for month in allowed_months():
        refuse_month(month)
        if month not in by_month:
            raise RuntimeError(f"pinned inventory has no {month}")
        obj = by_month[month]
        key = str(obj["KEY"])
        if not key.endswith(f"BTCUSDT-5m-{month}.zip"):
            raise RuntimeError(f"spot {month}: key is not that month's official zip")
        if "/spot/monthly/klines/BTCUSDT/5m/" not in key:
            raise RuntimeError(f"spot {month}: key is not the spot kline path")
        chosen.append(obj)
    return chosen


def place_on_grid(open_ms, high, low, close) -> tuple[np.ndarray, np.ndarray, np.ndarray, int, int]:
    """Dense 5m grid on [2017-09-01, 2020-01-01).

    An open time that is not an exact 5m boundary is not a bar of this grid.
    It is counted and left unplaced. It is not moved onto a neighboring bucket.
    Absent grid bars stay NaN. Nothing is filled.
    """
    n = K.CALENDAR_DAYS * K.BARS_PER_DAY
    out_high = np.full(n, np.nan, dtype=np.float64)
    out_low = np.full(n, np.nan, dtype=np.float64)
    out_close = np.full(n, np.nan, dtype=np.float64)
    stamps = np.asarray(open_ms, dtype=np.int64)
    highs = np.asarray(high, dtype=np.float64)
    lows = np.asarray(low, dtype=np.float64)
    closes = np.asarray(close, dtype=np.float64)
    if stamps.size == 0:
        raise RuntimeError("spot panel is empty")
    if np.any(stamps < K.EVENT_START_MS) or np.any(stamps >= K.SURFACE_END_MS):
        raise RuntimeError("spot bar falls outside [2017-09-01, 2020-01-01)")
    aligned = stamps % K.BAR_MS == 0
    excluded = int(np.count_nonzero(~aligned))
    stamps = stamps[aligned]
    highs = highs[aligned]
    lows = lows[aligned]
    closes = closes[aligned]
    index = ((stamps - K.EVENT_START_MS) // K.BAR_MS).astype(np.int64)
    if np.any(index < 0) or np.any(index >= n):
        raise RuntimeError("spot bar index outside the frozen grid")
    if np.unique(index).size != int(index.size):
        raise RuntimeError("duplicate spot open time")
    out_high[index] = highs
    out_low[index] = lows
    out_close[index] = closes
    return out_high, out_low, out_close, int(index.size), excluded


class Panel:
    def __init__(self, t0: int, high, low, close, months: list[str], present_bars: int, month_sha256: list[dict]):
        self.t0 = int(t0)
        self.high = np.asarray(high, dtype=np.float64)
        self.low = np.asarray(low, dtype=np.float64)
        self.close = np.asarray(close, dtype=np.float64)
        self.n = int(self.high.shape[0])
        self.months = list(months)
        self.present_bars = int(present_bars)
        self.missing_bars = int(self.n - self.present_bars)
        self.month_sha256 = list(month_sha256)
        if self.t0 != K.EVENT_START_MS:
            raise RuntimeError("panel does not start at 2017-09-01")
        if self.n != K.CALENDAR_DAYS * K.BARS_PER_DAY:
            raise RuntimeError("panel length is not 852 UTC dates")
        if self.missing_bars < 0:
            raise RuntimeError("present bars exceed the grid")


def load_panel() -> tuple[Panel, dict]:
    inventory = json.loads(SPOT_INVENTORY.read_text(encoding="utf-8"))
    objects = select_objects(inventory)
    cache = cache_root() / "spot_5m"
    cache.mkdir(parents=True, exist_ok=True)
    parts = []
    month_sha = []
    for obj in objects:
        month = obj["MONTH"]
        refuse_month(month)
        path = cache / Path(obj["KEY"]).name
        payload = path.read_bytes() if path.exists() else _get(VISION + obj["KEY"])
        if sha256_bytes(payload) != obj["SHA256"]:
            raise RuntimeError(f"spot {month}: digest drifted from the pinned inventory")
        if not path.exists():
            path.write_bytes(payload)
        raw = _parse_kline_zip(payload, Path(obj["KEY"]).name.replace(".zip", ".csv"))
        if int(raw[0, 0]) != int(obj["FIRST_OPEN_MS"]) or int(raw[-1, 0]) != int(obj["LAST_OPEN_MS"]):
            raise RuntimeError(f"spot {month}: open range drifted from the inventory")
        if int(raw.shape[0]) != int(obj["ROWS"]):
            raise RuntimeError(f"spot {month}: row count drifted")
        if int(raw[0, 0]) < K.EVENT_START_MS or int(raw[-1, 0]) >= K.SURFACE_END_MS:
            raise RuntimeError(f"spot {month}: zip leaves [2017-09-01, 2020-01-01)")
        stamps = np.rint(raw[:, 0]).astype(np.int64)
        off_grid = int(np.count_nonzero(stamps % K.BAR_MS != 0))
        parts.append(raw)
        month_sha.append({
            "month": month,
            "sha256": obj["SHA256"],
            "rows": int(obj["ROWS"]),
            "off_grid_rows": off_grid,
        })
    raw = np.concatenate(parts, axis=0)
    raw = raw[np.argsort(raw[:, 0], kind="mergesort")]
    open_ms = np.rint(raw[:, 0]).astype(np.int64)
    if int(open_ms[0]) != K.EVENT_START_MS:
        raise RuntimeError("first spot bar is not 2017-09-01T00:00Z")
    if int(open_ms[-1]) >= K.SURFACE_END_MS:
        raise RuntimeError("last spot bar is not inside 2019")
    high, low, close, present, excluded = place_on_grid(open_ms, raw[:, 2], raw[:, 3], raw[:, 4])
    if excluded != sum(item["off_grid_rows"] for item in month_sha):
        raise RuntimeError("off-grid row count does not match the months")
    panel = Panel(
        K.EVENT_START_MS,
        high,
        low,
        close,
        [obj["MONTH"] for obj in objects],
        present,
        month_sha,
    )
    provenance = {
        "dataset_id": K.SURFACE_ID,
        "instrument": K.VENUE,
        "interval": K.INTERVAL,
        "object_list_sha256": inventory.get("OBJECT_LIST_SHA256"),
        "months": panel.months,
        "present_bars": panel.present_bars,
        "missing_bars": panel.missing_bars,
        "grid_bars": panel.n,
        "first_open_ms": int(open_ms[0]),
        "last_open_ms": int(open_ms[-1]),
        "off_grid_rows_not_placed": excluded,
        "off_grid_rule": "an open time not divisible by 300000 ms is not a bar of this grid and is not moved onto a bucket",
        "months_sha256": panel.month_sha256,
    }
    return panel, provenance
