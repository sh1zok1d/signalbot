"""Reaction features on [T, T+15m) and the early-resolution filter.

Nothing in this module reads a bar at or after D. The late label lives in late.py
and is not imported here.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from scripts.research.level_positioning_flow_discovery_v1.features import _imbalance
from scripts.research.level_touch_degradation_v1 import constants as PARENT

from . import constants as K


def _passage(high: np.ndarray, low: np.ndarray, start: int, stop: int, side: int,
             zone_low: float, zone_high: float, x: float) -> Optional[str]:
    """Parent first-passage rule on the half-open index interval [start, stop)."""
    horizon = int(stop) - int(start)
    if side not in (1, -1) or not (math.isfinite(x) and PARENT.X_MIN < x < PARENT.X_MAX):
        return None
    if horizon < 1 or start < 0 or stop > high.shape[0]:
        return None
    hh = high[start:stop]
    ll = low[start:stop]
    ok = np.isfinite(hh) & np.isfinite(ll)
    if ok.size != horizon or float(ok.mean()) < PARENT.MIN_PRESENT:
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


def early_status(high: np.ndarray, low: np.ndarray, j: int, side: int, zone_low: float,
                 zone_high: float, x: float) -> str:
    """Barrier passage on bars j+1 and j+2 only. The touch bar is not a resolution."""
    label = _passage(
        high, low, j + K.EARLY_START_OFFSET, j + K.EARLY_STOP_OFFSET,
        side, zone_low, zone_high, x,
    )
    if label == "BREAK":
        return "EARLY_BREAK"
    if label == "REJECT":
        return "EARLY_REJECT"
    if label == "AMBIGUOUS":
        return "EARLY_AMBIGUOUS"
    if label == "NEITHER":
        return "UNRESOLVED"
    return "UNAVAILABLE"


def _index(t0: int, decision_ms: int, n: int) -> Optional[int]:
    t = int(decision_ms)
    if t % K.BAR_MS != 0 or (t - int(t0)) % K.BAR_MS != 0:
        return None
    j = (t - int(t0)) // K.BAR_MS
    if j < K.PRE_BARS or j + K.REACTION_BARS > n:
        return None
    if int(t0) + j * K.BAR_MS != t:
        return None
    return int(j)


def end_position(close: float, side: int, zone_low: float, zone_high: float, x: float) -> Optional[float]:
    """Continuous close location at D, in units of the barrier distance. Not an acceptance flag."""
    if side not in (1, -1) or not math.isfinite(close) or close <= 0.0:
        return None
    if not (math.isfinite(x) and x > 0.0):
        return None
    if side > 0:
        if not (math.isfinite(zone_high) and zone_high > 0.0):
            return None
        return (float(close) - float(zone_high)) / (float(zone_high) * float(x))
    if not (math.isfinite(zone_low) and zone_low > 0.0):
        return None
    return (float(zone_low) - float(close)) / (float(zone_low) * float(x))


def _sum_positive(values: np.ndarray) -> Optional[float]:
    if values.size == 0 or not bool(np.isfinite(values).all()) or np.any(values < 0.0):
        return None
    total = float(values.sum())
    if not math.isfinite(total) or total <= 0.0:
        return None
    return total


def reaction_features(open_ms: int, t0: int, close: np.ndarray, quote: np.ndarray,
                      taker: np.ndarray, side: int, zone_low: float, zone_high: float,
                      x: float, pre_taker: Optional[float]) -> dict:
    """R1–R4. Slices stop at j+3 exclusive. Bar j+3 is the first bar that opens at D."""
    empty = {
        "END_POSITION_X": None,
        "RELATIVE_ACTIVITY_15M": None,
        "ORIENTED_TAKER_REACTION_15M": None,
        "TAKER_CHANGE_VS_PRE": None,
    }
    j = _index(t0, open_ms, close.shape[0])
    if j is None or side not in (1, -1):
        return empty
    # [T, D) is exactly three bars. The next bar is not read.
    post = slice(j, j + K.REACTION_BARS)
    pre = slice(j - K.PRE_BARS, j)
    if int(t0) + (j + K.REACTION_BARS) * K.BAR_MS != int(open_ms) + K.REACTION_MS:
        return empty
    last_close = float(close[j + K.REACTION_BARS - 1])
    r1 = end_position(last_close, side, zone_low, zone_high, x)
    post_qv = _sum_positive(quote[post])
    pre_qv = _sum_positive(quote[pre])
    r2 = None
    if post_qv is not None and pre_qv is not None:
        baseline = pre_qv / 4.0
        if baseline > 0.0:
            r2 = math.log(post_qv / baseline)
    r3 = _imbalance(quote[post], taker[post], side)
    r4 = None
    if r3 is not None and pre_taker is not None and math.isfinite(float(pre_taker)):
        r4 = float(r3) - float(pre_taker)
    return {
        "END_POSITION_X": r1,
        "RELATIVE_ACTIVITY_15M": r2,
        "ORIENTED_TAKER_REACTION_15M": r3,
        "TAKER_CHANGE_VS_PRE": r4,
    }


def oi_at(available_at: np.ndarray, values: np.ndarray, decision_ms: int):
    """Latest legal print at or before decision_ms, within one native period."""
    t = int(decision_ms)
    if t >= K.SURFACE_END_MS or available_at.size == 0:
        return None
    idx = int(np.searchsorted(available_at, t, side="right")) - 1
    if idx < 0:
        return None
    avail = int(available_at[idx])
    if avail > t:
        return None
    age = t - avail
    if age < 0 or age > K.MAX_OI_STALENESS_MS:
        return None
    value = float(values[idx])
    if not math.isfinite(value) or value <= 0.0:
        return None
    return avail, value


def oi_reaction(available_at: np.ndarray, values: np.ndarray, open_ms: int) -> Optional[float]:
    """log(OI at D / OI at T). Both endpoints must be legal. The print after D is ignored."""
    at_t = oi_at(available_at, values, int(open_ms))
    at_d = oi_at(available_at, values, int(open_ms) + K.REACTION_MS)
    if at_t is None or at_d is None:
        return None
    if int(at_d[0]) <= int(at_t[0]):
        return None
    if int(at_d[0]) > int(open_ms) + K.REACTION_MS:
        return None
    return math.log(float(at_d[1]) / float(at_t[1]))
