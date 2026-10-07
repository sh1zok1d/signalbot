"""BREAK_FIRST / REJECT_FIRST after a touch. Imported only by the evaluator and by tests.

The touch bar itself is not in the window (same rule as DH1 barrier first-passage: bars
j+1 .. j+horizon). A 5m bar that reaches both barriers has an unknown order and is AMBIGUOUS.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from . import constants as K


def classify(high: np.ndarray, low: np.ndarray, j: int, side: int, zone_low: float, zone_high: float,
             x: float, horizon: int) -> Optional[str]:
    """BREAK, REJECT, NEITHER, AMBIGUOUS, or None when the window is not usable."""
    if side not in (1, -1) or not (math.isfinite(x) and K.X_MIN < x < K.X_MAX):
        return None
    if horizon < 1 or j + horizon >= high.shape[0]:
        return None
    hh = high[j + 1:j + 1 + horizon]
    ll = low[j + 1:j + 1 + horizon]
    ok = np.isfinite(hh) & np.isfinite(ll)
    if ok.size != horizon or float(ok.mean()) < K.MIN_PRESENT:
        return None
    if side > 0:
        break_px = zone_high * (1.0 + x)
        reject_px = zone_low * (1.0 - x)
        hit_break = ok & (hh >= break_px)
        hit_reject = ok & (ll <= reject_px)
    else:
        break_px = zone_low * (1.0 - x)
        reject_px = zone_high * (1.0 + x)
        hit_break = ok & (ll <= break_px)
        hit_reject = ok & (hh >= reject_px)
    ib = np.flatnonzero(hit_break)
    ir = np.flatnonzero(hit_reject)
    fb = int(ib[0]) if ib.size else None
    fr = int(ir[0]) if ir.size else None
    if fb is None and fr is None:
        return "NEITHER"
    if fb is not None and fr is not None and fb == fr:
        return "AMBIGUOUS"
    if fr is None or (fb is not None and fb < fr):
        return "BREAK"
    return "REJECT"


def attach(high: np.ndarray, low: np.ndarray, touches: list[dict], *, horizon: int,
           barrier_fraction: float) -> list[dict]:
    """Copy of touches with `outcome` set. Primary X is rescaled when the barrier fraction changes.

    Touch identity is unchanged. A different fraction replaces X; it does not rebuild touches.
    """
    scale = float(barrier_fraction) / K.BARRIER_FRACTION_PRIMARY
    out = []
    for t in touches:
        x0 = t.get("x_primary")
        x = None if x0 is None else float(x0) * scale
        y = None
        if x is not None:
            y = classify(high, low, int(t["j"]), int(t["side"]), float(t["zone_low"]),
                         float(t["zone_high"]), x, horizon)
        out.append({**t, "outcome": y, "x_used": x, "horizon": horizon,
                    "barrier_fraction": barrier_fraction})
    return out
