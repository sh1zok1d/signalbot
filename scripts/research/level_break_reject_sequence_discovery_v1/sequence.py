"""Post-first opposite-barrier scan. Not imported by the outcome-blind preflight.

Stage 1 is the parent first-passage label. Stage 2 reads only bars after that
first one-sided hit, and only through j+48.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from scripts.research.level_touch_degradation_v1 import constants as PARENT
from scripts.research.level_touch_degradation_v1.outcomes import classify

from . import constants as K


def _hits(high, low, j: int, side: int, zone_low: float, zone_high: float, x: float):
    if side not in (1, -1) or not (math.isfinite(x) and PARENT.X_MIN < x < PARENT.X_MAX):
        return None
    horizon = K.HORIZON_BARS
    if j + horizon >= high.shape[0]:
        return None
    hh = high[j + 1:j + 1 + horizon]
    ll = low[j + 1:j + 1 + horizon]
    ok = np.isfinite(hh) & np.isfinite(ll)
    if ok.size != horizon or float(ok.mean()) < PARENT.MIN_PRESENT:
        return None
    if side > 0:
        hit_break = ok & (hh >= zone_high * (1.0 + x))
        hit_reject = ok & (ll <= zone_low * (1.0 - x))
    else:
        hit_break = ok & (ll <= zone_low * (1.0 - x))
        hit_reject = ok & (hh >= zone_high * (1.0 + x))
    return hit_break, hit_reject


def _first(mask: np.ndarray) -> Optional[int]:
    idx = np.flatnonzero(mask)
    return int(idx[0]) if idx.size else None


def sequence_class(high, low, j: int, side: int, zone_low: float, zone_high: float, x: float) -> dict:
    """One terminal class. The touch bar is outside the scan."""
    blank = {"status": "UNUSABLE", "class": None, "first": None, "delay_min": None}
    hits = _hits(high, low, j, side, zone_low, zone_high, x)
    if hits is None:
        return blank
    hit_break, hit_reject = hits
    fb = _first(hit_break)
    fr = _first(hit_reject)
    parent = classify(high, low, j, side, zone_low, zone_high, x, K.HORIZON_BARS)
    if fb is None and fr is None:
        name, first = "NEITHER", "NEITHER"
        delay = None
    elif fb is not None and fr is not None and fb == fr:
        name, first = "FIRST_AMBIGUOUS", "AMBIGUOUS"
        delay = None
    elif fr is None or (fb is not None and fb < fr):
        first = "BREAK"
        later = _first(hit_reject[fb + 1:])
        if later is None:
            name, delay = "BREAK_NO_LATER_REJECT", None
        else:
            name = "BREAK_THEN_REJECT"
            delay = float(K.BAR_MINUTES * (later + 1))
    else:
        first = "REJECT"
        later = _first(hit_break[fr + 1:])
        if later is None:
            name, delay = "REJECT_NO_LATER_BREAK", None
        else:
            name = "REJECT_THEN_BREAK"
            delay = float(K.BAR_MINUTES * (later + 1))
    if parent != first:
        raise RuntimeError(f"sequence first event {first} disagrees with parent {parent}")
    return {"status": "OK", "class": name, "first": first, "delay_min": delay}


def reversal_flag(name: Optional[str], primary: str) -> Optional[int]:
    """1 if the opposite barrier is hit after the first one-sided event."""
    if primary == "P1":
        if name == "BREAK_THEN_REJECT":
            return 1
        if name == "BREAK_NO_LATER_REJECT":
            return 0
        return None
    if name == "REJECT_THEN_BREAK":
        return 1
    if name == "REJECT_NO_LATER_BREAK":
        return 0
    return None
