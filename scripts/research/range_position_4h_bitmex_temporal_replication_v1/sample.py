"""D2 grid and the eligibility partition. No return is computed here."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

from scripts.research.range_position_4h_incremental_replication_v1.grid import place

from . import constants as K


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rows_to_arrays(rows: list[dict]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Last-trade OHLC as stored. The inverse contract is not inverted."""
    opens: list[int] = []
    highs: list[float] = []
    lows: list[float] = []
    closes: list[float] = []
    for row in rows:
        opened = int(row["open_time_ms"])
        if opened >= K.SURFACE_END_MS:
            raise SystemExit("SERIES_CROSSES_2020")
        opens.append(opened)
        highs.append(float(row["high"]))
        lows.append(float(row["low"]))
        closes.append(float(row["close"]))
    return (
        np.asarray(opens, dtype=np.int64),
        np.asarray(highs, dtype=np.float64),
        np.asarray(lows, dtype=np.float64),
        np.asarray(closes, dtype=np.float64),
    )


def load_rows(path: Path) -> list[dict]:
    if sha256(path) != K.SERIES_SHA256:
        raise SystemExit("SERIES_HASH_MISMATCH")
    rows: list[dict] = []
    with gzip.open(path, "rt") as handle:
        for line in handle:
            rows.append(json.loads(line))
    return rows


def build_grid(opens: np.ndarray, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray) -> dict:
    if opens.size and int(opens.max()) >= K.SURFACE_END_MS:
        raise SystemExit("SERIES_CROSSES_2020")
    grid = place(opens, highs, lows, closes)
    grid["close_at_decision"] = grid["grid_open"] + K.BAR_MS
    return grid


def phase_residue(grid_open: np.ndarray) -> np.ndarray:
    """Residue 2 from the 2020-01-01 5m index. Floor division, including dates before 2020."""
    opened = np.asarray(grid_open, dtype=np.int64)
    global_i = np.floor_divide(opened - np.int64(K.PARENT_EPOCH_MS), np.int64(K.BAR_MS))
    return np.mod(global_i, 3) == K.PHASE_RESIDUE


def _cumsum(flag: np.ndarray) -> np.ndarray:
    out = np.zeros(flag.size + 1, dtype=np.int64)
    np.cumsum(flag, dtype=np.int64, out=out[1:])
    return out


def classify(grid: dict) -> dict[str, np.ndarray]:
    """Partition phase anchors. Gap first, then lookback, then future, else eligible."""
    opened = np.asarray(grid["grid_open"], dtype=np.int64)
    high = np.asarray(grid["high"], dtype=np.float64)
    low = np.asarray(grid["low"], dtype=np.float64)
    close = np.asarray(grid["close"], dtype=np.float64)
    n = int(close.shape[0])
    present_close = np.isfinite(close) & (close > 0.0)
    present_hl = np.isfinite(high) & np.isfinite(low)
    hole = ~np.isfinite(close)
    in_declared = (opened >= K.GAP_START_MS) & (opened <= K.GAP_END_MS)
    gap_slot = hole & in_declared

    phase = phase_residue(opened) & ((opened + K.BAR_MS) < K.SURFACE_END_MS)
    gap_hits = np.zeros(n, dtype=bool)
    lookback_ok = np.zeros(n, dtype=bool)
    future_ok = np.zeros(n, dtype=bool)
    if n:
        idx = np.arange(n, dtype=np.int64)
        left = np.maximum(idx - K.LOOKBACK, 0)
        right = np.minimum(idx + K.HORIZON, n - 1)
        gap_c = _cumsum(gap_slot)
        gap_hits = (gap_c[right + 1] - gap_c[left]) > 0

        close_c = _cumsum(present_close)
        hl_c = _cumsum(present_hl)
        if n > K.LOOKBACK:
            i = np.arange(K.LOOKBACK, n, dtype=np.int64)
            closes_ok = (close_c[i + 1] - close_c[i - K.LOOKBACK]) == (K.LOOKBACK + 1)
            hl_ok = (hl_c[i + 1] - hl_c[i - (K.LOOKBACK - 1)]) == K.LOOKBACK
            window_hi = np.lib.stride_tricks.sliding_window_view(high, K.LOOKBACK).max(axis=1)
            window_lo = np.lib.stride_tricks.sliding_window_view(low, K.LOOKBACK).min(axis=1)
            span = window_hi - window_lo
            positive = np.isfinite(span) & (span > 0.0)
            lookback_ok[i] = closes_ok & hl_ok & positive[i - (K.LOOKBACK - 1)]
        if n > K.HORIZON:
            i = np.arange(0, n - K.HORIZON, dtype=np.int64)
            future_count = close_c[i + K.HORIZON + 1] - close_c[i + 1]
            future_open_ok = (opened[i] + np.int64(K.HORIZON * K.BAR_MS)) < K.SURFACE_END_MS
            future_ok[i] = (future_count == K.HORIZON) & future_open_ok

    gap = phase & gap_hits
    lookback = phase & ~gap_hits & ~lookback_ok
    future = phase & ~gap_hits & lookback_ok & ~future_ok
    eligible = phase & ~gap_hits & lookback_ok & future_ok
    return {
        "phase": phase,
        "gap": gap,
        "lookback": lookback,
        "future": future,
        "eligible": eligible,
        "hole": hole,
        "in_declared_gap": in_declared,
    }
