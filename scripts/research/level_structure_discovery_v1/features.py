"""Touch-time structural features. No outcome is read.

Birth features come from the anchor source period. Membership, age and zone span use
only constituents known at the open of the touch bar, and the touch's own pre-touch X.
"""

from __future__ import annotations

import math
from typing import Optional

from .membership import members_as_of


def _span(members: list[dict], x: float) -> float:
    if len(members) <= 1:
        return 0.0
    prices = [float(m["price"]) for m in members if math.isfinite(float(m["price"])) and float(m["price"]) > 0]
    if len(prices) <= 1 or not math.isfinite(x) or x <= 0:
        return math.nan
    lo, hi = min(prices), max(prices)
    return (hi - lo) / lo / float(x)


def touch_features(ledger: dict, birth: dict, *, j: int, x: Optional[float]) -> Optional[dict]:
    """Features for one touch of the ledger's episode. None when age is undefined."""
    i0, i1 = int(ledger["i0"]), int(ledger["i1"])
    if j < i0 or j > i1 or i1 <= i0:
        return None
    members = members_as_of(ledger, j)
    if not members:
        return None
    families = {m["family"] for m in members}
    x_value = math.nan if x is None else float(x)
    return {
        "age": (int(j) - i0) / (i1 - i0),
        "confluence": float(len(members)),
        "diversity": float(len(families)),
        "zone_span": _span(members, x_value),
        "formation_range": float(birth["formation_range"]),
        "formation_volume": float(birth["formation_volume"]),
        "close_off_extreme": float(birth["close_off_extreme"]),
        "extreme_timing": float(birth["extreme_timing"]),
        "extreme_density": float(birth["extreme_density"]),
        "n_members_as_of": len(members),
    }
