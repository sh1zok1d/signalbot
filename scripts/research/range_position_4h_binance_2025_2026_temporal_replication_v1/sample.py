"""Canonical grid and eligibility. No future return is computed here."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

from . import constants as K


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_rows(path: Path) -> list[dict]:
    if K.SERIES_SHA256 != "PENDING_SERIES_HASH" and sha256(path) != K.SERIES_SHA256:
        raise SystemExit("SERIES_HASH_MISMATCH")
    rows = []
    with gzip.open(path, "rt") as handle:
        for line in handle:
            row = json.loads(line)
            opened = int(row["open_time_ms"])
            if K.E1_START_MS <= opened < K.E1_END_MS:
                raise SystemExit("PROTECTED_ROW_IN_SERIES")
            if opened < K.SURFACE_START_MS or opened >= K.SURFACE_END_MS:
                raise SystemExit("ROW_OUTSIDE_SURFACE")
            rows.append(row)
    return rows


def rows_to_arrays(rows: list[dict]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    opens = np.asarray([int(row["open_time_ms"]) for row in rows], dtype=np.int64)
    highs = np.asarray([float(row["high"]) for row in rows], dtype=np.float64)
    lows = np.asarray([float(row["low"]) for row in rows], dtype=np.float64)
    closes = np.asarray([float(row["close"]) for row in rows], dtype=np.float64)
    return opens, highs, lows, closes


def build_grid(opens: np.ndarray, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray) -> dict:
    """Dense 5m grid. A missing slot stays missing. Same placement as the Bybit grid, without its 2025 cutoff."""
    opens = np.asarray(opens, dtype=np.int64)
    if opens.size == 0:
        raise SystemExit("EMPTY_SERIES")
    if np.any(np.diff(opens) <= 0):
        raise SystemExit("OPENS_NOT_INCREASING")
    if np.any(opens % K.BAR_MS != 0):
        raise SystemExit("OPENS_OFF_GRID")
    origin = int(opens[0])
    last = int(opens[-1])
    n = (last - origin) // K.BAR_MS + 1
    slot = (opens - origin) // K.BAR_MS
    if np.unique(slot).size != opens.size:
        raise SystemExit("DUPLICATE_OPEN")
    high = np.full(n, np.nan, dtype=np.float64)
    low = np.full(n, np.nan, dtype=np.float64)
    close = np.full(n, np.nan, dtype=np.float64)
    high[slot] = highs
    low[slot] = lows
    close[slot] = closes
    grid_open = origin + np.arange(n, dtype=np.int64) * K.BAR_MS
    return {
        "origin_ms": origin,
        "grid_open": grid_open,
        "high": high,
        "low": low,
        "close": close,
        "occupied": int(opens.size),
        "slots": int(n),
        "holes": int(n - opens.size),
        "close_at_decision": grid_open + K.BAR_MS,
    }


def phase_residue(grid_open: np.ndarray) -> np.ndarray:
    opened = np.asarray(grid_open, dtype=np.int64)
    global_i = np.floor_divide(opened - np.int64(K.PARENT_EPOCH_MS), np.int64(K.BAR_MS))
    return np.mod(global_i, 3) == K.PHASE_RESIDUE


def _cumsum(flag: np.ndarray) -> np.ndarray:
    out = np.zeros(flag.size + 1, dtype=np.int64)
    np.cumsum(flag, dtype=np.int64, out=out[1:])
    return out


def classify(grid: dict) -> dict[str, np.ndarray]:
    """Phase anchors: object-hole first, then lookback, then future, else eligible."""
    opened = np.asarray(grid["grid_open"], dtype=np.int64)
    high = np.asarray(grid["high"], dtype=np.float64)
    low = np.asarray(grid["low"], dtype=np.float64)
    close = np.asarray(grid["close"], dtype=np.float64)
    n = int(close.shape[0])
    present_close = np.isfinite(close) & (close > 0.0)
    present_hl = np.isfinite(high) & np.isfinite(low)
    hole = ~np.isfinite(close)
    in_object_hole = (opened >= K.OBJECT_HOLE_START_MS) & (opened < K.OBJECT_HOLE_END_MS)
    in_e1 = (opened >= K.E1_START_MS) & (opened < K.E1_END_MS)
    hole_slot = hole & in_object_hole
    phase = phase_residue(opened) & ((opened + K.BAR_MS) < K.SURFACE_END_MS)
    hole_hits = np.zeros(n, dtype=bool)
    e1_hits = np.zeros(n, dtype=bool)
    lookback_ok = np.zeros(n, dtype=bool)
    future_ok = np.zeros(n, dtype=bool)
    if n:
        idx = np.arange(n, dtype=np.int64)
        left = np.maximum(idx - K.LOOKBACK, 0)
        right = np.minimum(idx + K.HORIZON, n - 1)
        hole_c = _cumsum(hole_slot)
        e1_c = _cumsum(hole & in_e1)
        hole_hits = (hole_c[right + 1] - hole_c[left]) > 0
        e1_hits = (e1_c[right + 1] - e1_c[left]) > 0
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
    excluded = phase & hole_hits
    lookback = phase & ~hole_hits & ~lookback_ok
    future = phase & ~hole_hits & lookback_ok & ~future_ok
    eligible = phase & ~hole_hits & lookback_ok & future_ok
    return {
        "phase": phase,
        "excluded": excluded,
        "e1_touch": phase & e1_hits,
        "lookback": lookback,
        "future": future,
        "eligible": eligible,
        "hole": hole,
        "in_object_hole": in_object_hole,
        "in_e1": in_e1,
    }
