"""Frozen path labels for one 48-bar window. No market loader."""

from __future__ import annotations

import numpy as np

from . import constants as K


def score_window(high, low, level_high: float, level_low: float, side: str) -> dict:
    """One arm. `high` and `low` are the 48 bars strictly after the touch bar.

    Resolution is either barrier. Extension-first is 1 only when the first bar
    that meets a barrier meets the extension and not the reentry. A same-bar
    double hit is resolution 1 and extension-first 0. Unresolved is 0 on both.
    """
    high = np.asarray(high, dtype=np.float64)
    low = np.asarray(low, dtype=np.float64)
    if high.shape != (K.HORIZON_BARS,) or low.shape != (K.HORIZON_BARS,):
        raise ValueError("outcome window is not 48 bars")
    width = float(level_high) - float(level_low)
    if not width > 0.0:
        raise ValueError("nonpositive width")
    midpoint = (float(level_high) + float(level_low)) / 2.0
    reach = K.EXTENSION_FRACTION * width
    if side == "high":
        extension = high >= float(level_high) + reach
        reentry = low <= midpoint
        outward = np.maximum(0.0, high - float(level_high)) / width
    elif side == "low":
        extension = low <= float(level_low) - reach
        reentry = high >= midpoint
        outward = np.maximum(0.0, float(level_low) - low) / width
    else:
        raise ValueError(side)
    either = extension | reentry
    resolved = bool(either.any())
    both = False
    extension_first = False
    if resolved:
        k = int(np.argmax(either))
        both = bool(extension[k] and reentry[k])
        extension_first = bool(extension[k] and not reentry[k])
    outside = (high < float(level_low)) | (low > float(level_high))
    return {
        "resolution": float(resolved),
        "extension_first": float(extension_first),
        "outside_share": float(np.mean(outside)),
        "outward_excursion": float(np.max(outward)),
        "both_barriers_on_first_hit": both,
    }
