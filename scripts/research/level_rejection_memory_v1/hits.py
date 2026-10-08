"""First-passage offsets for a touch already defined by LEVEL_TOUCH_DEGRADATION_V1.

The label matches `outcomes.classify`. The offsets are the extra piece this unit needs:
how many bars after the touch bar the reject barrier was first hit. The scan does not
read bars after that hit when the caller asks only for the rejection time.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from scripts.research.level_touch_degradation_v1 import constants as P
from scripts.research.level_touch_degradation_v1.outcomes import classify


def passage(high: np.ndarray, low: np.ndarray, j: int, side: int, zone_low: float, zone_high: float,
            x: float, horizon: int) -> tuple[Optional[str], Optional[int], Optional[int]]:
    """Return (label, bars_to_break, bars_to_reject).

    Bar counts are 1-based offsets into the window that starts at j+1. None if that
    barrier is not hit. The label is None when the window is not usable.
    """
    label = classify(high, low, j, side, zone_low, zone_high, x, horizon)
    if label is None:
        return None, None, None
    if side > 0:
        break_px = zone_high * (1.0 + x)
        reject_px = zone_low * (1.0 - x)
        hit_break = high[j + 1:j + 1 + horizon] >= break_px
        hit_reject = low[j + 1:j + 1 + horizon] <= reject_px
    else:
        break_px = zone_low * (1.0 - x)
        reject_px = zone_high * (1.0 + x)
        hit_break = low[j + 1:j + 1 + horizon] <= break_px
        hit_reject = high[j + 1:j + 1 + horizon] >= reject_px
    ib = np.flatnonzero(hit_break)
    ir = np.flatnonzero(hit_reject)
    b_break = int(ib[0]) + 1 if ib.size else None
    b_reject = int(ir[0]) + 1 if ir.size else None
    return label, b_break, b_reject


def overshoot_at_reject(high: np.ndarray, low: np.ndarray, j: int, side: int, zone_low: float,
                        zone_high: float, x: float, bars_to_reject: int) -> Optional[float]:
    """How far the rejecting bar traded past the reject barrier, in units of X.

    Known on the rejection bar. Does not use any later bar, including the wait until
    the next touch. Zero means the bar touched the barrier and did not trade through it.
    """
    if bars_to_reject < 1 or not (math.isfinite(x) and x > 0):
        return None
    k = j + bars_to_reject
    if k >= high.shape[0]:
        return None
    if side > 0:
        unit = zone_low * x
        if unit <= 0 or not np.isfinite(low[k]):
            return None
        reject_px = zone_low * (1.0 - x)
        return float((reject_px - low[k]) / unit)
    unit = zone_high * x
    if unit <= 0 or not np.isfinite(high[k]):
        return None
    reject_px = zone_high * (1.0 + x)
    return float((high[k] - reject_px) / unit)


def annotate(high: np.ndarray, low: np.ndarray, touches: list[dict]) -> list[dict]:
    """Copy touches with the parent primary label and the rejection-bar fields.

    Horizon and barrier fraction stay at the parent primary. This unit does not retune them.
    """
    out = []
    horizon = P.HOLD_BARS_PRIMARY
    for t in touches:
        x0 = t.get("x_primary")
        x = None if x0 is None else float(x0)
        label = b_break = b_reject = over = None
        if x is not None and P.X_MIN < x < P.X_MAX and int(t["side"]) in (1, -1):
            label, b_break, b_reject = passage(
                high, low, int(t["j"]), int(t["side"]), float(t["zone_low"]), float(t["zone_high"]),
                x, horizon)
            if b_reject is not None and label == "REJECT":
                over = overshoot_at_reject(
                    high, low, int(t["j"]), int(t["side"]), float(t["zone_low"]), float(t["zone_high"]),
                    x, b_reject)
        out.append({**t, "outcome": label, "bars_to_break": b_break, "bars_to_reject": b_reject,
                    "overshoot": over})
    return out
