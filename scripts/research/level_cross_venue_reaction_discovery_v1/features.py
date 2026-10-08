"""Frozen cross-venue features. All four are missing together.

Returns are 15-minute log moves. Orientation uses the Binance approach side.
Dispersion uses the unoriented log moves. Exact zero does not count as agreement.
"""

from __future__ import annotations

import math
from typing import Optional

from . import constants as K


def log_return(close_base: Optional[float], close_decision: Optional[float]) -> Optional[float]:
    if close_base is None or close_decision is None:
        return None
    base = float(close_base)
    decision = float(close_decision)
    if not (math.isfinite(base) and math.isfinite(decision) and base > 0.0 and decision > 0.0):
        return None
    value = math.log(decision / base)
    if not math.isfinite(value):
        return None
    return value


def orient(log_move: Optional[float], side: int) -> Optional[float]:
    if log_move is None or side not in (1, -1) or not math.isfinite(float(log_move)):
        return None
    return float(side) * float(log_move)


def _median2(left: float, right: float) -> float:
    return 0.5 * (float(left) + float(right))


def _std3(values: tuple[float, float, float]) -> float:
    mean = (values[0] + values[1] + values[2]) / 3.0
    var = sum((value - mean) ** 2 for value in values) / 3.0
    return math.sqrt(var)


def cross_venue_features(ret_binance: Optional[float], ret_bybit: Optional[float],
                         ret_okx: Optional[float], side: int) -> dict:
    """TIER A only. One missing venue makes every primary feature missing."""
    empty = {name: None for name in K.FEATURES}
    moves = (ret_binance, ret_bybit, ret_okx)
    if side not in (1, -1) or any(value is None or not math.isfinite(float(value)) for value in moves):
        return empty
    oriented = [float(side) * float(value) for value in moves]
    other = _median2(oriented[1], oriented[2])
    positive = sum(1 for value in oriented if value > 0.0)
    return {
        "OTHER_VENUE_MEDIAN_MOVE": other,
        "CROSS_VENUE_CONFIRMATION_GAP": oriented[0] - other,
        "CROSS_VENUE_DISPERSION": _std3((float(moves[0]), float(moves[1]), float(moves[2]))),
        "DIRECTION_AGREEMENT": positive / 3.0,
    }
