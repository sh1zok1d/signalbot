"""Pinned Binance spot BTCUSDT 5m klines. Digests come from the DH1 inventory.

Only the months inside the common 2020-04..2024-12 overlap are read. Earlier
pinned months stay unread. No object at or after 2025-01-01 is requested.
Missing bars stay missing.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Optional

import numpy as np

from scripts.research.dh1.data import SPOT_INVENTORY, VISION, _get, _parse_kline_zip, sha256_bytes, cache_root

from . import constants as K


class SpotSeries:
    def __init__(self, open_ms: np.ndarray, close: np.ndarray, quote: np.ndarray, taker_buy_quote: np.ndarray):
        if open_ms.ndim != 1 or close.shape != open_ms.shape:
            raise RuntimeError("spot series shape is not a single grid")
        if quote.shape != open_ms.shape or taker_buy_quote.shape != open_ms.shape:
            raise RuntimeError("spot taker fields do not match the grid")
        if np.any(open_ms >= K.SURFACE_END_MS):
            raise RuntimeError("spot series contains a bar at or after 2025-01-01")
        if open_ms.size > 1 and np.any(np.diff(open_ms.astype(np.int64)) <= 0):
            raise RuntimeError("spot timestamps are not strictly increasing")
        if np.any(open_ms.astype(np.int64) % K.BAR_MS != 0):
            raise RuntimeError("spot leaves the 5m grid")
        self.open_ms = open_ms.astype(np.int64)
        self.close = close.astype(float)
        self.quote = quote.astype(float)
        self.taker_buy_quote = taker_buy_quote.astype(float)

    def _index(self, open_ms: int) -> Optional[int]:
        target = int(open_ms)
        if target >= K.SURFACE_END_MS or target % K.BAR_MS != 0:
            return None
        idx = int(np.searchsorted(self.open_ms, target))
        if idx >= self.open_ms.size or int(self.open_ms[idx]) != target:
            return None
        return idx

    def close_at(self, open_ms: int) -> Optional[float]:
        idx = self._index(open_ms)
        if idx is None:
            return None
        price = float(self.close[idx])
        if not np.isfinite(price) or price <= 0.0:
            return None
        return price

    def flow_at(self, open_ms: int) -> tuple[Optional[float], Optional[float]]:
        idx = self._index(open_ms)
        if idx is None:
            return None, None
        quote = float(self.quote[idx])
        buy = float(self.taker_buy_quote[idx])
        if not (np.isfinite(quote) and np.isfinite(buy)):
            return None, None
        return quote, buy


def _inventory() -> dict:
    inv = json.loads(SPOT_INVENTORY.read_text())
    if inv.get("DATASET_ID") != K.SPOT_DATASET_ID:
        raise RuntimeError("spot inventory is not DH1_BINANCE_SPOT_BTCUSDT_5M_V0")
    if inv.get("INSTRUMENT") != K.SPOT_INSTRUMENT or inv.get("INTERVAL") != K.SPOT_INTERVAL:
        raise RuntimeError("spot inventory is not Binance spot BTCUSDT 5m")
    if "taker_buy_quote_volume" not in str(inv.get("COLUMNS_USED")):
        raise RuntimeError("spot inventory has no taker-buy quote field")
    source = str(inv.get("SOURCE") or "")
    if "/spot/monthly/klines/BTCUSDT/5m/" not in source:
        raise RuntimeError("spot inventory source is not the official spot kline path")
    return inv


def load_spot() -> tuple[SpotSeries, dict]:
    inv = _inventory()
    months = [
        obj for obj in inv["OBJECTS"]
        if K.SPOT_LOAD_FIRST_MONTH <= obj["MONTH"] <= K.SPOT_LOAD_LAST_MONTH
    ]
    if not months or months[0]["MONTH"] != K.SPOT_LOAD_FIRST_MONTH or months[-1]["MONTH"] != K.SPOT_LOAD_LAST_MONTH:
        raise RuntimeError("spot overlap months are not the pinned 2020-04..2024-12 list")
    cache = cache_root() / "spot_5m"
    cache.mkdir(parents=True, exist_ok=True)
    parts = []
    for obj in months:
        if dt.date.fromisoformat(obj["MONTH"] + "-01") >= dt.date(2025, 1, 1):
            raise RuntimeError(f"refusing spot month {obj['MONTH']}")
        path = cache / Path(obj["KEY"]).name
        payload = path.read_bytes() if path.exists() else _get(VISION + obj["KEY"])
        if sha256_bytes(payload) != obj["SHA256"]:
            raise RuntimeError(f"spot {obj['MONTH']}: digest drifted from the pinned inventory")
        if not path.exists():
            path.write_bytes(payload)
        raw = _parse_kline_zip(payload, Path(obj["KEY"]).name.replace(".zip", ".csv"))
        if int(raw[0, 0]) != int(obj["FIRST_OPEN_MS"]) or int(raw[-1, 0]) != int(obj["LAST_OPEN_MS"]):
            raise RuntimeError(f"spot {obj['MONTH']}: open range drifted from the inventory")
        if int(raw.shape[0]) != int(obj["ROWS"]):
            raise RuntimeError(f"spot {obj['MONTH']}: row count drifted")
        parts.append(raw)
    raw = np.concatenate(parts, axis=0)
    raw = raw[np.argsort(raw[:, 0], kind="mergesort")]
    open_ms = np.rint(raw[:, 0]).astype(np.int64)
    start = 1585699200000
    expected = (K.SURFACE_END_MS - start) // K.BAR_MS
    present = int(np.sum((open_ms >= start) & (open_ms < K.SURFACE_END_MS)))
    missing = int(expected - present)
    census = {
        "dataset_id": K.SPOT_DATASET_ID,
        "instrument": K.SPOT_INSTRUMENT,
        "interval": K.SPOT_INTERVAL,
        "object_list_sha256": inv.get("OBJECT_LIST_SHA256"),
        "months": [obj["MONTH"] for obj in months],
        "n_bars": int(open_ms.size),
        "first_open_ms": int(open_ms[0]),
        "last_open_ms": int(open_ms[-1]),
        "expected_bars": int(expected),
        "missing_bars": missing,
        "missing_fraction": float(missing / expected) if expected else 1.0,
        "taker_field": "taker_buy_quote_volume",
    }
    series = SpotSeries(open_ms, raw[:, 4], raw[:, 6], raw[:, 7])
    return series, census
