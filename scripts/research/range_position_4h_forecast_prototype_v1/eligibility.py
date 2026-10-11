"""Replication eligibility. No label rate and no model score is computed here."""

from __future__ import annotations

import numpy as np

from . import constants as K


def _cumsum(flag: np.ndarray) -> np.ndarray:
    out = np.zeros(flag.size + 1, dtype=np.int64)
    np.cumsum(flag, dtype=np.int64, out=out[1:])
    return out


def phase_residue(grid_open: np.ndarray) -> np.ndarray:
    opened = np.asarray(grid_open, dtype=np.int64)
    global_i = np.floor_divide(opened - np.int64(K.PARENT_EPOCH_MS), np.int64(K.BAR_MS))
    return np.mod(global_i, 3) == K.PHASE_RESIDUE


def replication_eligible(grid_open: np.ndarray, high: np.ndarray, low: np.ndarray,
                         close: np.ndarray, surface_end_ms: int) -> np.ndarray:
    """15-minute phase, complete 4h lookback including T, complete 1h future, positive span."""
    opened = np.asarray(grid_open, dtype=np.int64)
    high = np.asarray(high, dtype=np.float64)
    low = np.asarray(low, dtype=np.float64)
    close = np.asarray(close, dtype=np.float64)
    n = int(close.shape[0])
    present_close = np.isfinite(close) & (close > 0.0)
    present_hl = np.isfinite(high) & np.isfinite(low)
    phase = phase_residue(opened) & ((opened + K.BAR_MS) < int(surface_end_ms))
    lookback_ok = np.zeros(n, dtype=bool)
    future_ok = np.zeros(n, dtype=bool)
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
        future_open_ok = (opened[i] + np.int64(K.HORIZON * K.BAR_MS)) < int(surface_end_ms)
        future_ok[i] = (future_count == K.HORIZON) & future_open_ok
    return phase & lookback_ok & future_ok


def local_returns(close: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """RET_1H and RET_15M. A missing or non-positive close stays missing."""
    close = np.asarray(close, dtype=np.float64)
    n = int(close.shape[0])
    ret_1h = np.full(n, np.nan, dtype=np.float64)
    ret_15m = np.full(n, np.nan, dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        if n > K.RET_1H_BARS:
            earlier = close[:-K.RET_1H_BARS]
            later = close[K.RET_1H_BARS:]
            step = np.log(later / earlier)
            ok = np.isfinite(earlier) & np.isfinite(later) & (earlier > 0.0) & (later > 0.0)
            ret_1h[K.RET_1H_BARS:] = np.where(ok, step, np.nan)
        if n > K.RET_15M_BARS:
            earlier = close[:-K.RET_15M_BARS]
            later = close[K.RET_15M_BARS:]
            step = np.log(later / earlier)
            ok = np.isfinite(earlier) & np.isfinite(later) & (earlier > 0.0) & (later > 0.0)
            ret_15m[K.RET_15M_BARS:] = np.where(ok, step, np.nan)
    return ret_1h, ret_15m
