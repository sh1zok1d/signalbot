"""DH3 outcomes. Imported only by the one-shot evaluator.

- RANGE_4H: log((max high - min low over bars j+1..j+48) / close[j]); None if fewer than 90 % present.
- UP_FIRST_4H / CONT_FIRST_4H: DH1's barrier rule (d = +1, or the triggering move's direction).
- LEVEL_HOLD_4H: DH1's (the product's) hold rule.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from beta.hist_series import Bars
from scripts.research.dh1 import constants as K1
from scripts.research.dh1 import outcomes as O1


def range_4h(b: Bars, j: int) -> Optional[float]:
    if j + K1.HOLD_BARS >= b.n or not math.isfinite(b.close[j]):
        return None
    hi, lo = b.high[j + 1:j + 1 + K1.HOLD_BARS], b.low[j + 1:j + 1 + K1.HOLD_BARS]
    ok = np.isfinite(hi) & np.isfinite(lo)
    if ok.mean() < K1.MIN_PRESENT:
        return None
    width = hi[ok].max() - lo[ok].min()
    return float(math.log(width / b.close[j])) if width > 0 else None


def outcome(b: Bars, row: dict) -> Optional[float]:
    ep = row["ENDPOINT"]
    if ep == "RANGE_4H":
        return range_4h(b, row["J"])
    if ep == "UP_FIRST_4H":
        return O1.barrier(b, row["J"], 1, row["X"])
    if ep == "CONT_FIRST_4H":
        return O1.barrier(b, row["J"], row["DIR"], row["X"])
    if ep == "LEVEL_HOLD_4H":
        return O1.level_hold(b, row["J"], row["LEVEL"], row["SIDE"])
    raise ValueError(ep)


def attach(bars_by_symbol: dict, rows: list) -> list:
    out = []
    for r in rows:
        y = outcome(bars_by_symbol[r["SYMBOL"]], r)
        if y is not None:
            out.append({**r, "Y": y})
    return out
