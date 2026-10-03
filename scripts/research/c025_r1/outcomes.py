"""Post-T targets for C025-R1.

Imported only by the execution path. Event admission does not call this module.
A later burst is a contamination flag. It does not drop the event and it is
not an input to the primary statistic.
"""

from __future__ import annotations

import numpy as np

from .constants import PRIMARY_W_MINUTES, assert_locked_primary


def window_sums(abs_ret: np.ndarray, quote: np.ndarray, indices: np.ndarray, width: int) -> tuple[np.ndarray, np.ndarray]:
    """Sum over (t, t+width], the width minutes strictly after the event bar."""
    if width != PRIMARY_W_MINUTES:
        raise RuntimeError("outcome width is frozen at 30 minutes")
    n = int(abs_ret.shape[0])
    indices = np.asarray(indices, dtype=np.int64)
    abs_sum = np.full(indices.shape[0], np.nan, dtype=np.float64)
    quote_sum = np.full(indices.shape[0], np.nan, dtype=np.float64)
    if indices.size == 0:
        return abs_sum, quote_sum
    # A window that would require a minute at or after 2025-01-01 is missing,
    # not filled and not taken from protected data.
    valid = (indices >= 0) & (indices + width < n)
    if not np.any(valid):
        return abs_sum, quote_sum
    c_abs = np.cumsum(abs_ret)
    c_quote = np.cumsum(quote)
    end = indices[valid] + width
    abs_sum[valid] = c_abs[end] - c_abs[indices[valid]]
    quote_sum[valid] = c_quote[end] - c_quote[indices[valid]]
    return abs_sum, quote_sum


def impact_ratio(pre_impact: np.ndarray, post_abs: np.ndarray, post_quote: np.ndarray) -> np.ndarray:
    """log(post impact) - log(pre impact). Non-positive parts stay NaN."""
    post = np.full(pre_impact.shape[0], np.nan, dtype=np.float64)
    ok = (post_quote > 0.0) & (post_abs > 0.0) & np.isfinite(pre_impact) & (pre_impact > 0.0)
    post[ok] = post_abs[ok] / post_quote[ok]
    ratio = np.full(pre_impact.shape[0], np.nan, dtype=np.float64)
    ratio[ok] = np.log(post[ok]) - np.log(pre_impact[ok])
    return ratio


def contamination_flags(burst: np.ndarray, indices: np.ndarray, width: int) -> np.ndarray:
    """True when any BURST minute lies in (t, t+width]. Descriptive only."""
    if width != PRIMARY_W_MINUTES:
        raise RuntimeError("contamination window is frozen at 30 minutes")
    n = int(burst.shape[0])
    indices = np.asarray(indices, dtype=np.int64)
    flags = np.zeros(indices.shape[0], dtype=bool)
    if indices.size == 0:
        return flags
    valid = (indices >= 0) & (indices + width < n)
    if not np.any(valid):
        return flags
    c = np.cumsum(burst.astype(np.int64))
    end = indices[valid] + width
    flags[valid] = (c[end] - c[indices[valid]]) > 0
    return flags


def attach_outcomes(abs_ret: np.ndarray, quote: np.ndarray, burst: np.ndarray,
                    indices: np.ndarray, pre_impact: np.ndarray) -> dict:
    """Compute the frozen 30m target. Width cannot be switched."""
    assert_locked_primary()
    post_abs, post_quote = window_sums(abs_ret, quote, indices, PRIMARY_W_MINUTES)
    ratio = impact_ratio(pre_impact, post_abs, post_quote)
    flags = contamination_flags(burst, indices, PRIMARY_W_MINUTES)
    return {
        "post_abs": post_abs,
        "post_quote": post_quote,
        "impact_ratio": ratio,
        "contamination": flags,
        "complete": np.isfinite(ratio),
    }
