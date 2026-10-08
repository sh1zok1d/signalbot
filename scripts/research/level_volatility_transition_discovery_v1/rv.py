"""Realized-volatility transition. Imported only by the official outcome run."""

from __future__ import annotations

from typing import Optional

import numpy as np

from . import constants as K
from .windows import spans


def assigned_returns(close: np.ndarray, j: int) -> tuple[np.ndarray, np.ndarray, float]:
    """Pre returns, post returns, and the excluded touch-bar return.

    Pre uses closes [j-13, j-1]. Post uses closes [j, j+12].
    The touch-bar return log(close_j / close_{j-1}) is returned only so tests
    can see that it is not a member of either window.
    """
    j = int(j)
    s = spans(j)
    if s["pre_close_lo"] < 0 or s["post_close_hi"] >= int(close.shape[0]):
        raise IndexError("window is outside the bar array")
    pre = np.log(close[j - K.WINDOW_BARS:j] / close[j - K.PRE_CLOSE_LAG:j - 1])
    post = np.log(close[j + 1:j + K.WINDOW_BARS + 1] / close[j:j + K.WINDOW_BARS])
    touch = float(np.log(close[j] / close[j - 1]))
    return pre, post, touch


def realized(returns: np.ndarray) -> Optional[float]:
    """sqrt(mean(r^2)). No demean, no annualization, no epsilon."""
    if returns.shape != (K.WINDOW_BARS,):
        return None
    if not np.isfinite(returns).all():
        return None
    value = float(np.sqrt(np.mean(np.square(returns))))
    if not np.isfinite(value) or value <= 0.0:
        return None
    return value


def event_transition(close: np.ndarray, j: int) -> Optional[dict]:
    """VOL_TRANSITION_60 = log(RV_POST60 / RV_PRE60), or None if either RV is unusable."""
    try:
        pre_r, post_r, _touch = assigned_returns(close, j)
    except IndexError:
        return None
    rv_pre = realized(pre_r)
    rv_post = realized(post_r)
    if rv_pre is None or rv_post is None:
        return None
    transition = float(np.log(rv_post / rv_pre))
    if not np.isfinite(transition):
        return None
    return {"rv_pre": rv_pre, "rv_post": rv_post, "transition": transition}
