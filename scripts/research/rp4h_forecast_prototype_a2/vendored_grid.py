"""Clock-grid features. A missing 5-minute slot stays missing."""

from __future__ import annotations

import numpy as np

from . import vendored_grid_constants as K


def _nan(n: int) -> np.ndarray:
    return np.full(n, np.nan, dtype=np.float64)


def place(open_ms: np.ndarray, high: np.ndarray, low: np.ndarray, close: np.ndarray) -> dict:
    """Put prints on the complete 5m grid from the first open to the last. No fill."""
    open_ms = np.asarray(open_ms, dtype=np.int64)
    if open_ms.size == 0:
        raise RuntimeError("empty Bybit series")
    if np.any(open_ms >= K.SURFACE_END_MS):
        raise RuntimeError("series contains a bar at or after 2025-01-01")
    if np.any(np.diff(open_ms) <= 0):
        raise RuntimeError("open times are not strictly increasing")
    if np.any(open_ms % K.BAR_MS != 0):
        raise RuntimeError("open times leave the 5m grid")
    origin = int(open_ms[0])
    last = int(open_ms[-1])
    n = (last - origin) // K.BAR_MS + 1
    slot = (open_ms - origin) // K.BAR_MS
    if np.unique(slot).size != open_ms.size:
        raise RuntimeError("duplicate open time")
    hi = _nan(n)
    lo = _nan(n)
    cl = _nan(n)
    hi[slot] = high
    lo[slot] = low
    cl[slot] = close
    grid_open = origin + np.arange(n, dtype=np.int64) * K.BAR_MS
    return {
        "origin_ms": origin,
        "grid_open": grid_open,
        "high": hi,
        "low": lo,
        "close": cl,
        "occupied": int(open_ms.size),
        "slots": int(n),
        "holes": int(n - open_ms.size),
    }


def features(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> dict[str, np.ndarray]:
    """RP4H, RET_4H, RV_4H, RANGE_WIDTH_4H, R_1H on one dense grid. Past only for the states."""
    n = int(close.shape[0])
    ret = _nan(n)
    with np.errstate(divide="ignore", invalid="ignore"):
        ret[1:] = np.log(close[1:] / close[:-1])
    rp = _nan(n)
    width = _nan(n)
    signed = _nan(n)
    rv = _nan(n)
    future = _nan(n)
    w = K.LOOKBACK
    h = K.HORIZON
    if n > w:
        hv = np.lib.stride_tricks.sliding_window_view(high, w)
        lv = np.lib.stride_tricks.sliding_window_view(low, w)
        cv = np.lib.stride_tricks.sliding_window_view(close, w)
        rvw = np.lib.stride_tricks.sliding_window_view(ret, w)
        finite = np.isfinite(hv).all(axis=1) & np.isfinite(lv).all(axis=1) & np.isfinite(cv).all(axis=1)
        hi = np.max(hv, axis=1)
        lo = np.min(lv, axis=1)
        span = hi - lo
        last = cv[:, -1]
        ok_rp = finite & np.isfinite(span) & (span > 0.0) & np.isfinite(last)
        with np.errstate(divide="ignore", invalid="ignore"):
            pos = (last - lo) / span
        sl = slice(w - 1, None)
        rp[sl] = np.where(ok_rp, pos, np.nan)
        ok_w = ok_rp & (lo > 0.0) & (hi > 0.0)
        with np.errstate(divide="ignore", invalid="ignore"):
            log_width = np.log(hi) - np.log(lo)
        width[sl] = np.where(ok_w, log_width, np.nan)
        ret_ok = np.isfinite(rvw).all(axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            scale = np.sqrt(np.sum(rvw * rvw, axis=1))
        rv[sl] = np.where(ret_ok, scale, np.nan)
    if n > w:
        earlier = close[:-w]
        later = close[w:]
        with np.errstate(divide="ignore", invalid="ignore"):
            step = np.log(later / earlier)
        ok_s = np.isfinite(earlier) & np.isfinite(later) & (earlier > 0.0) & (later > 0.0)
        signed[w:] = np.where(ok_s, step, np.nan)
    if n > h:
        base = close[:-h]
        dest = close[h:]
        with np.errstate(divide="ignore", invalid="ignore"):
            fwd = np.log(dest / base)
        ok_f = np.isfinite(base) & np.isfinite(dest) & (base > 0.0) & (dest > 0.0)
        future[:-h] = np.where(ok_f, fwd, np.nan)
    return {"rp": rp, "ret4": signed, "rv4": rv, "width": width, "r1": future}


def anchor_mask(grid_open: np.ndarray) -> np.ndarray:
    """Parent phase: global index from 2020-01-01, i >= 96, i % 3 == 2, close before 2025."""
    global_i = (grid_open - K.DATA_START_MS) // K.BAR_MS
    close_ms = grid_open + K.BAR_MS
    return (global_i >= K.MIN_GLOBAL_INDEX) & ((global_i % 3) == 2) & (close_ms < K.SURFACE_END_MS)
