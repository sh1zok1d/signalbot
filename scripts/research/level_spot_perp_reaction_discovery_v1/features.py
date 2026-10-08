"""Frozen spot features. CV1 is imported from #363 and is not re-derived.

SP1 is the oriented spot log move. SP2 subtracts the median of the three
oriented perpetual moves. SP3 subtracts oriented perp taker imbalance from
oriented spot taker imbalance. Exact zero is a real value, not a missing one.
"""

from __future__ import annotations

import math
from typing import Optional

from scripts.research.level_cross_venue_reaction_discovery_v1.features import (
    cross_venue_features,
    log_return,
    orient,
)

from . import constants as K


def perp_median(oriented: tuple[float, float, float]) -> float:
    ordered = sorted(float(value) for value in oriented)
    return ordered[1]


def other_venue_median(ret_binance: Optional[float], ret_bybit: Optional[float],
                       ret_okx: Optional[float], side: int) -> Optional[float]:
    """Exact #363 CV1. A missing venue makes the control missing."""
    packed = cross_venue_features(ret_binance, ret_bybit, ret_okx, side)
    value = packed.get(K.CV1_NAME)
    if value is None or not math.isfinite(float(value)):
        return None
    return float(value)


def spot_features(ret_spot: Optional[float], ret_binance: Optional[float],
                  ret_bybit: Optional[float], ret_okx: Optional[float], side: int,
                  spot_imbalance: Optional[float], perp_imbalance: Optional[float]) -> dict:
    empty = {name: None for name in K.FEATURES}
    sp1 = orient(ret_spot, side)
    if sp1 is None:
        return empty
    out = dict(empty)
    out["SPOT_ORIENTED_MOVE_15M"] = sp1
    moves = (ret_binance, ret_bybit, ret_okx)
    if side in (1, -1) and all(value is not None and math.isfinite(float(value)) for value in moves):
        oriented = tuple(float(side) * float(value) for value in moves)
        out["SPOT_EXCESS_VS_PERP_COMPLEX"] = sp1 - perp_median(oriented)
    if (spot_imbalance is not None and perp_imbalance is not None
            and math.isfinite(float(spot_imbalance)) and math.isfinite(float(perp_imbalance))
            and side in (1, -1)):
        out["RELATIVE_SPOT_TAKER_PRESSURE_15M"] = (
            float(side) * float(spot_imbalance) - float(side) * float(perp_imbalance)
        )
    return out


def window_imbalance(quotes: list[Optional[float]], buys: list[Optional[float]]) -> Optional[float]:
    """(buy - sell) / total over the three reaction bars. One illegal bar drops it."""
    if len(quotes) != 3 or len(buys) != 3:
        return None
    total = 0.0
    buy = 0.0
    for quote, taken in zip(quotes, buys):
        if quote is None or taken is None:
            return None
        q = float(quote)
        b = float(taken)
        if not (math.isfinite(q) and math.isfinite(b) and q > 0.0 and 0.0 <= b <= q):
            return None
        total += q
        buy += b
    if total <= 0.0:
        return None
    value = (2.0 * buy - total) / total
    if not math.isfinite(value):
        return None
    return value
