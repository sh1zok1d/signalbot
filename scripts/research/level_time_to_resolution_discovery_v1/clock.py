"""First future barrier bar after a structural touch. The touch bar is not a resolution."""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from scripts.research.level_touch_degradation_v1 import constants as PARENT

from . import constants as K


def resolution_clock(high: np.ndarray, low: np.ndarray, j: int, side: int,
                     zone_low: float, zone_high: float, x: float) -> dict:
    """Time until the first future bar hits a frozen barrier.

    Bars are j+1 .. j+48. A hit on bar j+k has time 5*k minutes. A bar that
    reaches both barriers is AMBIGUOUS and still resolves the any-resolution
    clock. No hit by j+48 is right-censored at 240 minutes: the observed event
    time stays null.
    """
    blank = {
        "status": "UNUSABLE", "kind": None, "k": None, "time_min": None,
        "censor_min": float(K.RESTRICT_MIN),
    }
    if side not in (1, -1) or not (math.isfinite(x) and PARENT.X_MIN < x < PARENT.X_MAX):
        return blank
    horizon = K.HORIZON_BARS
    if j + horizon >= high.shape[0]:
        return blank
    hh = high[j + 1:j + 1 + horizon]
    ll = low[j + 1:j + 1 + horizon]
    ok = np.isfinite(hh) & np.isfinite(ll)
    if ok.size != horizon or float(ok.mean()) < PARENT.MIN_PRESENT:
        return blank
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
        return {
            "status": "CENSORED", "kind": "CENSORED", "k": None, "time_min": None,
            "censor_min": float(K.RESTRICT_MIN),
        }
    if fb is not None and fr is not None and fb == fr:
        offset = fb
        kind = "AMBIGUOUS"
    elif fr is None or (fb is not None and fb < fr):
        offset = fb
        kind = "BREAK"
    else:
        offset = fr
        kind = "REJECT"
    k = int(offset) + 1
    return {
        "status": "RESOLVED", "kind": kind, "k": k,
        "time_min": float(K.BAR_MINUTES * k),
        "censor_min": float(K.RESTRICT_MIN),
    }


def km_inputs(clocks: list[dict]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Observed-time convention for Kaplan-Meier.

    A censored row is carried at 240 with event flag 0. That is the censoring
    time, not an observed resolution. A resolution on bar j+48 is an event at
    240 and keeps its kind.
    """
    times = np.empty(len(clocks), dtype=float)
    events = np.empty(len(clocks), dtype=int)
    kinds = np.empty(len(clocks), dtype=object)
    for i, row in enumerate(clocks):
        kinds[i] = row["kind"]
        if row["status"] == "CENSORED":
            times[i] = float(K.RESTRICT_MIN)
            events[i] = 0
        else:
            times[i] = float(row["time_min"])
            events[i] = 1
    return times, events, kinds
