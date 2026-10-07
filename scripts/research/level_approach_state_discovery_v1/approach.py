"""PIT approach episode and the frozen feature family.

Decision boundary T is the open of the touch bar `j`. Every price, range and quote
value read here has index < j. The touch bar and the outcome window are not read.

The episode is geometric. On the approach side, the outer band is the region outside
the zone and within `band_mult * X` of the near edge. The episode is the contiguous
run of in-band closes that ends at bar j-1, and it counts only when the bar just
before that run is strictly farther than the band (the entry is observed) and that
bar is still inside the level's active interval.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from . import constants as K


def _gap(close: float, side: int, zlo: float, zhi: float) -> float:
    """Positive when `close` is still outside the zone on the approach side."""
    if side > 0:
        return math.log(zlo / close)
    return math.log(close / zhi)


def _in_band(close: float, side: int, zlo: float, zhi: float, dist: float) -> bool:
    if not math.isfinite(close) or dist <= 0:
        return False
    if side > 0:
        edge = zlo * (1.0 - dist)
        return edge <= close < zlo
    edge = zhi * (1.0 + dist)
    return zhi < close <= edge


def _is_far(close: float, side: int, zlo: float, zhi: float, dist: float) -> bool:
    if not math.isfinite(close) or dist <= 0:
        return False
    if side > 0:
        return close < zlo * (1.0 - dist)
    return close > zhi * (1.0 + dist)


def _inner(close: float, side: int, zlo: float, zhi: float, inner: float) -> bool:
    return _in_band(close, side, zlo, zhi, inner)


def episode_bounds(close: np.ndarray, j: int, i0: int, side: int, zlo: float, zhi: float,
                   x: float, band_mult: float) -> Optional[tuple[int, int]]:
    """Return (entry_bar, first_in_band_bar) or None.

    `entry_bar` is the far bar. The in-band run is `first_in_band_bar .. j-1`.
    """
    if side not in (1, -1) or j <= i0 or not (math.isfinite(x) and x > 0):
        return None
    dist = float(band_mult) * float(x)
    k = j - 1
    if k < i0 or not _in_band(float(close[k]), side, zlo, zhi, dist):
        return None
    while k >= i0 and _in_band(float(close[k]), side, zlo, zhi, dist):
        k -= 1
    first = k + 1
    n_bars = j - first
    if n_bars < K.MIN_APPROACH_BARS:
        return None
    if k < i0 or not _is_far(float(close[k]), side, zlo, zhi, dist):
        return None
    return k, first


def _window_ok(high, low, close, quote, start: int, end: int, *, recent: bool) -> bool:
    if start < 0 or end > high.shape[0] or start >= end:
        return False
    hh, ll, cc = high[start:end], low[start:end], close[start:end]
    ok = np.isfinite(hh) & np.isfinite(ll) & np.isfinite(cc) & (cc > 0)
    if recent:
        if not bool(ok.all()):
            return False
    elif float(ok.mean()) < K.MIN_PRESENT:
        return False
    if quote is not None:
        qq = quote[start:end]
        qok = np.isfinite(qq) & (qq >= 0)
        if recent and not bool(qok.all()):
            return False
        if not recent and float(qok.mean()) < K.MIN_PRESENT:
            return False
    return True


def _median_range(high, low, close, start: int, end: int) -> float:
    hh, ll, cc = high[start:end], low[start:end], close[start:end]
    ok = np.isfinite(hh) & np.isfinite(ll) & np.isfinite(cc) & (cc > 0)
    width = (hh[ok] - ll[ok]) / cc[ok]
    width = width[np.isfinite(width) & (width >= 0)]
    if width.size == 0:
        return math.nan
    return float(np.median(width))


def _mean_quote(quote, start: int, end: int) -> float:
    qq = quote[start:end]
    ok = np.isfinite(qq) & (qq >= 0)
    if not np.any(ok):
        return math.nan
    return float(np.mean(qq[ok]))


def compute_features(close: np.ndarray, high: np.ndarray, low: np.ndarray, quote: Optional[np.ndarray],
                     *, j: int, i0: int, side: int, zlo: float, zhi: float, x: float, sigma: float,
                     band_mult: float) -> Optional[dict]:
    """Approach features known strictly before bar j. None when the episode is not eligible."""
    if not (math.isfinite(sigma) and sigma > 0 and math.isfinite(zlo) and math.isfinite(zhi) and zlo > 0):
        return None
    bounds = episode_bounds(close, j, i0, side, zlo, zhi, x, band_mult)
    if bounds is None:
        return None
    entry, first = bounds
    # Closes entry .. j-1 are all < j. Steps are the differences along that path.
    closes = close[entry:j].astype(float)
    if closes.size < K.MIN_APPROACH_BARS + 1 or not np.all(np.isfinite(closes)) or np.any(closes <= 0):
        return None
    gaps = np.array([_gap(float(c), side, zlo, zhi) for c in closes], dtype=float)
    if not np.all(np.isfinite(gaps)):
        return None
    toward = -np.diff(gaps)  # positive when the gap to the zone shrinks
    path = float(np.abs(np.diff(np.log(closes))).sum())
    if not math.isfinite(path) or path <= 0:
        return None
    net = float(gaps[0] - gaps[-1])
    n_steps = int(toward.size)
    if n_steps < K.MIN_APPROACH_BARS:
        return None
    half = n_steps // 2
    if half < 2 or n_steps - half < 2:
        return None
    velocity = net / (n_steps * sigma)
    efficiency = net / path
    against = float(np.minimum(toward, 0.0).sum() * -1.0)
    pullback = against / path
    persistence = float(np.mean(toward > 0.0))
    vel_first = float(toward[:half].sum()) / (half * sigma)
    vel_second = float(toward[half:].sum()) / ((n_steps - half) * sigma)
    acceleration = vel_second - vel_first

    recent_start = j - K.RANGE_RECENT
    base_start = j - K.RANGE_BASE
    if not _window_ok(high, low, close, None, recent_start, j, recent=True):
        return None
    if not _window_ok(high, low, close, None, base_start, j, recent=False):
        return None
    recent_range = _median_range(high, low, close, recent_start, j)
    base_range = _median_range(high, low, close, base_start, j)
    if not (math.isfinite(recent_range) and math.isfinite(base_range) and recent_range > 0 and base_range > 0):
        return None
    range_state = math.log(recent_range / base_range)

    rel_volume = math.nan
    if quote is not None and _window_ok(high, low, close, quote, recent_start, j, recent=True) and _window_ok(
            high, low, close, quote, base_start, j, recent=False):
        q_recent = _mean_quote(quote, recent_start, j)
        q_base = _mean_quote(quote, base_start, j)
        if math.isfinite(q_recent) and math.isfinite(q_base) and q_recent > 0 and q_base > 0:
            rel_volume = math.log(q_recent / q_base)

    inner = K.DWELL_FRAC * float(x)
    dwell = 0
    for idx in range(j - 1, first - 1, -1):
        if _inner(float(close[idx]), side, zlo, zhi, inner):
            dwell += 1
        else:
            break

    return {
        "entry_j": int(entry),
        "first_j": int(first),
        "n_steps": n_steps,
        "log_steps": math.log(float(n_steps)),
        "velocity": float(velocity),
        "efficiency": float(efficiency),
        "pullback": float(pullback),
        "persistence": float(persistence),
        "acceleration": float(acceleration),
        "range_state": float(range_state),
        "rel_volume": float(rel_volume) if math.isfinite(rel_volume) else None,
        "dwell": float(dwell),
        "band_mult": float(band_mult),
    }


def price_features_ok(feat: dict) -> bool:
    for name in ("velocity", "efficiency", "persistence", "acceleration", "range_state", "dwell", "log_steps"):
        value = feat.get(name)
        if value is None or not math.isfinite(float(value)):
            return False
    return True


def volume_ok(feat: dict) -> bool:
    value = feat.get("rel_volume")
    return value is not None and math.isfinite(float(value))
