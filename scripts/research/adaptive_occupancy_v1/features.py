"""OCC_L: the exact analogue of OCC_MEAN_4H on an L-hour window (n = 12 L bars, the current bar included).

Box: H = max high and Lo = min low over bars i-n+1 .. i. The n-1 previous closes k = i-n+1 .. i-1 are normalized
p_k = (close_k - Lo)/(H - Lo); the current close is excluded; OCC_L = mean p_k. Undefined (NaN) if any bar of the
window is missing or H - Lo <= 0. For L = 4 this is DIRECTIONAL_STATE_SEARCH_V2 F2a exactly (tested)."""
from __future__ import annotations

import numpy as np


def occ_l(high: np.ndarray, low: np.ndarray, close: np.ndarray, idx: np.ndarray, hours: int,
          chunk: int = 20_000) -> np.ndarray:
    n = 12 * hours
    out = np.full(idx.size, np.nan)
    offs = np.arange(-n + 1, 1)
    ok_idx = idx >= n - 1
    for s in range(0, idx.size, chunk):
        ix = idx[s:s + chunk]
        good = ok_idx[s:s + chunk]
        safe = np.where(good, ix, n - 1)
        w = safe[:, None] + offs[None, :]
        hi = high[w].max(axis=1)
        lo = low[w].min(axis=1)
        c = close[w][:, :-1]
        span = hi - lo
        with np.errstate(invalid="ignore", divide="ignore"):
            v = ((c - lo[:, None]) / span[:, None]).mean(axis=1)
        v = np.where(good & np.isfinite(span) & (span > 0) & np.isfinite(v), v, np.nan)
        out[s:s + chunk] = v
    return out
