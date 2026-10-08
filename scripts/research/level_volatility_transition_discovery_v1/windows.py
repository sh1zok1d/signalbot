"""Index arithmetic for the frozen 60m windows. No return and no RV."""

from __future__ import annotations

import numpy as np

from . import constants as K


def spans(j: int) -> dict:
    """Inclusive close indices and the bars a return is assigned to.

    The return assigned to bar k is log(close_k / close_{k-1}).
    Pre returns are assigned to j-12..j-1. Post returns are assigned to j+1..j+12.
    Bar j itself is in neither assignment.
    """
    j = int(j)
    return {
        "touch": j,
        "pre_return_lo": j - K.WINDOW_BARS,
        "pre_return_hi": j - 1,
        "post_return_lo": j + 1,
        "post_return_hi": j + K.WINDOW_BARS,
        "pre_close_lo": j - K.PRE_CLOSE_LAG,
        "pre_close_hi": j - 1,
        "post_close_lo": j,
        "post_close_hi": j + K.POST_CLOSE_LEAD,
    }


def _segment_ok(close: np.ndarray, lo: int, hi: int) -> bool:
    n = int(close.shape[0])
    if lo < 0 or hi >= n or lo > hi:
        return False
    segment = close[lo:hi + 1]
    if int(segment.shape[0]) != hi - lo + 1:
        return False
    return bool(np.isfinite(segment).all() and np.all(segment > 0.0))


def path_flags(close: np.ndarray, j: int) -> dict:
    """Bar presence only. Finite positive closes. No log, no RV, no fill."""
    s = spans(j)
    pre = _segment_ok(close, s["pre_close_lo"], s["pre_close_hi"])
    touch = _segment_ok(close, s["touch"], s["touch"])
    post_tail = _segment_ok(close, s["touch"] + 1, s["post_close_hi"])
    return {
        "pre": pre,
        "touch": touch,
        "post": post_tail and touch,
        "complete": pre and touch and post_tail,
    }
