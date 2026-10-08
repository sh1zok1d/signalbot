"""Generic race stream (design §8a): hourly anchors, four price pairs, 4h window. Shadow only."""

from __future__ import annotations

import math

import numpy as np

from beta.hist_series import Bars

from scripts.research.dh1.events import rolling_sigma
from scripts.research.level_touch_degradation_v1 import constants as K352
from scripts.research.level_touch_degradation_v1.events import touch_week, touch_year

from . import b0 as B0
from . import constants as K


def x_g(sigma: float) -> float:
    return K352.x_from_sigma(sigma)


def anchors(bars: Bars, *, start_ms: int = K352.EVENT_START_MS, end_ms: int = K352.SURFACE_END_MS) -> np.ndarray:
    """Bars whose close is on a UTC hour, with sigma usable and the 48-bar window legal and >= 90 % present."""
    t = bars.times
    n = t.size
    sig = rolling_sigma(bars.close, window=K352.SCALE_BARS, min_frac=K352.MIN_PRESENT)
    close_ms = t + K352.BAR_MS
    on_hour = (close_ms % K.HOUR_MS) == 0
    ok = on_hour & np.isfinite(sig) & np.isfinite(bars.close) & (t >= start_ms)
    out = []
    for i in np.flatnonzero(ok):
        if i + K.WINDOW_BARS >= n:
            continue
        if t[i] + (K.WINDOW_BARS + 1) * K352.BAR_MS > end_ms:
            continue
        hh = bars.high[i + 1:i + 1 + K.WINDOW_BARS]
        ll = bars.low[i + 1:i + 1 + K.WINDOW_BARS]
        good = np.isfinite(hh) & np.isfinite(ll)
        if good.mean() < K352.MIN_PRESENT:
            continue
        x = x_g(float(sig[i]))
        if not (K352.X_MIN < 2 * x < K352.X_MAX):
            continue
        out.append(i)
    return np.array(out, dtype=int), sig


def first_passage(high, low, i: int, up_px: float, dn_px: float) -> str:
    hh = high[i + 1:i + 1 + K.WINDOW_BARS]
    ll = low[i + 1:i + 1 + K.WINDOW_BARS]
    ok = np.isfinite(hh) & np.isfinite(ll)
    iu = np.flatnonzero(ok & (hh >= up_px))
    idn = np.flatnonzero(ok & (ll <= dn_px))
    fu = int(iu[0]) if iu.size else None
    fd = int(idn[0]) if idn.size else None
    if fu is None and fd is None:
        return "NEITHER"
    if fu is not None and fd is not None and fu == fd:
        return "AMBIGUOUS"
    if fd is None or (fu is not None and fu < fd):
        return "UP"
    return "DOWN"


def generic_rows(bars: Bars, *, with_outcome: bool) -> list[dict]:
    idx, sig = anchors(bars)
    rows = []
    for i in idx:
        c = float(bars.close[i])
        s = float(sig[i])
        x = x_g(s)
        oms = int(bars.times[i])
        for (u, d) in K.GENERIC_PAIRS:
            up_px, dn_px = c * math.exp(u * x), c * math.exp(-d * x)
            pu, pd, pn = B0.race(c, up_px, dn_px, s, K.WINDOW_BARS)
            r = {"i": int(i), "pair": f"{u}{d}", "sigma": s, "week": touch_week(oms), "year": touch_year(oms),
                 "landmark": "G", "b0_beyond": pu, "b0_back": pd, "b0_neither": pn, "outcome": None}
            if with_outcome:
                y = first_passage(bars.high, bars.low, int(i), up_px, dn_px)
                r["outcome"] = {"UP": "BEYOND", "DOWN": "BACK", "NEITHER": "NEITHER", "AMBIGUOUS": "AMBIGUOUS"}[y]
            rows.append(r)
    return rows
