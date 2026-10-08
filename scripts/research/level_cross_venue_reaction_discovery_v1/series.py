"""Exact 5m close lookup. Missing stays missing. No forward fill."""

from __future__ import annotations

import gzip
from pathlib import Path
from typing import Optional

import numpy as np

from . import constants as K

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "docs" / "research_data" / K.DATASET_ID


class VenueSeries:
    def __init__(self, name: str, open_ms: np.ndarray, close: np.ndarray):
        if open_ms.ndim != 1 or close.shape != open_ms.shape:
            raise RuntimeError(f"{name} series shape is not a single grid")
        earliest = 1585699200000 + K.BYBIT_LABEL_OFFSET_MS
        if open_ms.size and int(open_ms[0]) < earliest:
            raise RuntimeError(f"{name} starts before the declared overlap")
        if np.any(open_ms >= K.SURFACE_END_MS):
            raise RuntimeError(f"{name} contains a bar at or after 2025-01-01")
        if open_ms.size > 1 and np.any(np.diff(open_ms.astype(np.int64)) <= 0):
            raise RuntimeError(f"{name} timestamps are not strictly increasing")
        if np.any(open_ms.astype(np.int64) % K.BAR_MS != 0):
            raise RuntimeError(f"{name} leaves the 5m grid")
        self.name = name
        self.open_ms = open_ms.astype(np.int64)
        self.close = close.astype(float)

    def close_at(self, open_ms: int) -> Optional[float]:
        """Close of the bar whose open equals open_ms. Anything else is missing."""
        target = int(open_ms)
        if target >= K.SURFACE_END_MS or target % K.BAR_MS != 0:
            return None
        idx = int(np.searchsorted(self.open_ms, target))
        if idx >= self.open_ms.size or int(self.open_ms[idx]) != target:
            return None
        price = float(self.close[idx])
        if not np.isfinite(price) or price <= 0.0:
            return None
        return price


def _load_csv(path: Path, name: str) -> VenueSeries:
    if not path.is_file():
        raise RuntimeError(f"missing canonical series {path}")
    opens = []
    closes = []
    with gzip.open(path, "rt") as handle:
        header = handle.readline().strip()
        if header != "open_ms,open,high,low,close":
            raise RuntimeError(f"unexpected header in {path}")
        for line in handle:
            parts = line.strip().split(",")
            if len(parts) != 5:
                raise RuntimeError(f"short row in {path}")
            opens.append(int(parts[0]))
            closes.append(float(parts[4]))
    return VenueSeries(name, np.asarray(opens, dtype=np.int64), np.asarray(closes, dtype=float))


def load_reaction_series() -> dict[str, VenueSeries]:
    return {
        "BYBIT_LINEAR_BTCUSDT_PERP": _load_csv(
            DATA / "bybit_btcusdt_linear_5m.csv.gz", "BYBIT_LINEAR_BTCUSDT_PERP",
        ),
        "OKX_BTC_USDT_SWAP_PERP": _load_csv(
            DATA / "okx_btc_usdt_swap_5m.csv.gz", "OKX_BTC_USDT_SWAP_PERP",
        ),
    }
