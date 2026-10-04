"""DH1 outcomes. Imported only by the one-shot evaluator (`evaluate.py`), never by feasibility.

- LEVEL_HOLD_4H: 1 if the close of bar j+48 is beyond the level on the approach side, else 0
  (the product's metric, `beta/levels._outcome`). None if that close is missing.
- BARRIER_FIRST_PASSAGE_4H: over bars i+1..i+48, 1 if close[i]*(1 + d*X) is reached before
  close[i]*(1 - d*X), 0 if the reverse, 0.5 if neither or both in the same bar. None if fewer than
  90 % of those bars are present.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from beta.hist_series import Bars

from . import constants as K


def level_hold(b: Bars, j: int, level: float, side: int) -> Optional[float]:
    c = b.close[j + K.HOLD_BARS] if j + K.HOLD_BARS < b.n else np.nan
    if not math.isfinite(c):
        return None
    return 1.0 if side * (c - level) > 0 else 0.0


def barrier(b: Bars, i: int, d: int, x: float) -> Optional[float]:
    if i + K.HOLD_BARS >= b.n:
        return None
    entry = b.close[i]
    hi, lo = b.high[i + 1:i + 1 + K.HOLD_BARS], b.low[i + 1:i + 1 + K.HOLD_BARS]
    ok = np.isfinite(hi) & np.isfinite(lo)
    if not math.isfinite(entry) or ok.mean() < K.MIN_PRESENT:
        return None
    up, dn = entry * (1 + x), entry * (1 - x)
    hit_up = np.flatnonzero(ok & (hi >= up))
    hit_dn = np.flatnonzero(ok & (lo <= dn))
    first_up = int(hit_up[0]) if hit_up.size else None
    first_dn = int(hit_dn[0]) if hit_dn.size else None
    if first_up is None and first_dn is None:
        return 0.5
    if first_up is not None and first_dn is not None and first_up == first_dn:
        return 0.5
    up_first = first_dn is None or (first_up is not None and first_up < first_dn)
    return 1.0 if (up_first if d > 0 else not up_first) else 0.0


def attach(b: Bars, rows: list, card: str) -> list:
    """Rows with their outcome Y; rows whose outcome is missing are dropped (counted by the caller)."""
    out = []
    for r in rows:
        y = level_hold(b, r["J"], r["LEVEL"], r["SIDE"]) if card == "DH1-L" else barrier(b, r["J"], r["DIR"], r["X"])
        if y is not None:
            out.append({**r, "Y": y})
    return out
