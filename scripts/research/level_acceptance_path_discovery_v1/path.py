"""Close-versus-zone bits and the frozen four-state path. No late label is read."""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from scripts.research.level_post_touch_reaction_discovery_v1.reactions import end_position

from . import constants as K


def beyond_break_edge(close: float, side: int, zone_low: float, zone_high: float) -> Optional[int]:
    """1 when the close is strictly beyond the break-side zone edge. Equality is 0."""
    if side not in (1, -1) or not math.isfinite(close):
        return None
    if side > 0:
        if not (math.isfinite(zone_high) and zone_high > 0.0):
            return None
        return 1 if float(close) > float(zone_high) else 0
    if not (math.isfinite(zone_low) and zone_low > 0.0):
        return None
    return 1 if float(close) < float(zone_low) else 0


def state_of(b0: int, b1: int, b2: int) -> str:
    bits = (int(b0), int(b1), int(b2))
    if any(bit not in (0, 1) for bit in bits):
        raise ValueError("path bits must be 0 or 1")
    if bits == (0, 0, 0):
        return "NEVER_OUTSIDE"
    if bits[2] == 0:
        return "REENTERED"
    if bits[1] == 0:
        return "LATE_OR_RECROSS_OUTSIDE"
    return "PERSISTENT_OUTSIDE"


def sequence_of(b0: int, b1: int, b2: int) -> str:
    return f"{int(b0)}{int(b1)}{int(b2)}"


def assign_contrast(state: str) -> tuple[Optional[str], Optional[int]]:
    if state == "NEVER_OUTSIDE":
        return "REENTRY_MEMORY", 0
    if state == "REENTERED":
        return "REENTRY_MEMORY", 1
    if state == "LATE_OR_RECROSS_OUTSIDE":
        return "PERSISTENCE_MEMORY", 0
    if state == "PERSISTENT_OUTSIDE":
        return "PERSISTENCE_MEMORY", 1
    return None, None


def end_position_x(close: float, side: int, zone_low: float, zone_high: float, x: float) -> Optional[float]:
    """#361 R1. Continuous location of the close at D. Not a path state."""
    return end_position(close, side, zone_low, zone_high, x)


def approach_displacement(open_: np.ndarray, close: np.ndarray, t0: int, open_ms: int, side: int) -> Optional[float]:
    """side × log(close of the bar ending at T / open of the bar opening at T−60m)."""
    if side not in (1, -1):
        return None
    t = int(open_ms)
    if (t - int(t0)) % K.BAR_MS != 0:
        return None
    j = (t - int(t0)) // K.BAR_MS
    i0 = j - K.PRE_BARS
    if i0 < 0 or j > close.shape[0] or j > open_.shape[0]:
        return None
    if int(t0) + i0 * K.BAR_MS != t - K.PRE_BARS * K.BAR_MS:
        return None
    if int(t0) + j * K.BAR_MS != t:
        return None
    o0 = float(open_[i0])
    c1 = float(close[j - 1])
    if not (math.isfinite(o0) and math.isfinite(c1) and o0 > 0.0 and c1 > 0.0):
        return None
    return float(side) * math.log(c1 / o0)


def path_record(close: np.ndarray, t0: int, open_ms: int, side: int, zone_low: float,
                zone_high: float, x: float) -> dict:
    """Bits, state, sequence, and endpoint from bars j, j+1, j+2. Bar j+3 is not read."""
    empty = {
        "B0": None, "B1": None, "B2": None, "sequence": None, "state": None,
        "contrast": None, "state_indicator": None, "END_POSITION_X": None,
    }
    t = int(open_ms)
    if side not in (1, -1) or (t - int(t0)) % K.BAR_MS != 0:
        return empty
    j = (t - int(t0)) // K.BAR_MS
    if j < 0 or j + K.REACTION_BARS > close.shape[0]:
        return empty
    if int(t0) + (j + K.REACTION_BARS) * K.BAR_MS != t + K.REACTION_MS:
        return empty
    bits = []
    for offset in range(K.REACTION_BARS):
        bit = beyond_break_edge(float(close[j + offset]), side, zone_low, zone_high)
        if bit is None:
            return empty
        bits.append(bit)
    b0, b1, b2 = bits
    state = state_of(b0, b1, b2)
    contrast, indicator = assign_contrast(state)
    return {
        "B0": b0,
        "B1": b1,
        "B2": b2,
        "sequence": sequence_of(b0, b1, b2),
        "state": state,
        "contrast": contrast,
        "state_indicator": indicator,
        "END_POSITION_X": end_position_x(float(close[j + K.REACTION_BARS - 1]), side, zone_low, zone_high, x),
    }


def time_block(open_ms: int) -> int:
    hour = (int(open_ms) // K.HOUR_MS) % 24
    return int(hour // 6)


def epoch_of(year: int) -> str:
    name = str(int(year))
    if name in K.EPOCHS:
        return name
    return "OUT"


def vol_tercile(sigma: Optional[float]) -> Optional[int]:
    if sigma is None or not math.isfinite(float(sigma)):
        return None
    if float(sigma) <= K.PARENT_SIGMA_LO:
        return 0
    if float(sigma) <= K.PARENT_SIGMA_HI:
        return 1
    return 2
