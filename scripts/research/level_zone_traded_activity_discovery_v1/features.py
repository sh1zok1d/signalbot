"""Zone-traded features from event aggregates. No late label is read here.

ZA1 is defined only when both notionals are strictly positive. A zero is missing.
No epsilon is added.
"""

from __future__ import annotations

import math
from typing import Optional

from . import constants as K


def zone_features(agg: Optional[dict], open_ms: int) -> dict:
    blank = {
        "trade_covered": False,
        "PRE60_TOTAL_NOTIONAL": None,
        "ZONE_NOTIONAL_15M": None,
        "TOTAL_NOTIONAL_15M": None,
        "ZONE_NOTIONAL_INTENSITY_15M": None,
        "ZONE_NOTIONAL_SHARE_15M": None,
        "ZONE_ACTIVE_SECONDS_15M": None,
        "TOUCH_OFFSET_SECONDS": None,
        "tau_ms": None,
        "touch_in_zone": 0,
    }
    if agg is None:
        return blank
    pre = float(agg["pre60_notional"])
    zone = float(agg["zone_notional_15m"])
    total = float(agg["total_notional_15m"])
    pre15 = pre / 4.0
    za1 = math.log(zone / pre15) if zone > 0.0 and pre15 > 0.0 else None
    za2 = (zone / total) if total > 0.0 else None
    active = int(agg["zone_active_seconds"])
    tau = agg.get("tau_ms")
    offset = None
    if tau is not None:
        offset = (int(tau) - int(open_ms)) / 1000.0
    return {
        "trade_covered": True,
        "PRE60_TOTAL_NOTIONAL": pre,
        "ZONE_NOTIONAL_15M": zone,
        "TOTAL_NOTIONAL_15M": total,
        "ZONE_NOTIONAL_INTENSITY_15M": za1,
        "ZONE_NOTIONAL_SHARE_15M": za2,
        "ZONE_ACTIVE_SECONDS_15M": active / float(K.ACTIVE_SECONDS_DENOM),
        "TOUCH_OFFSET_SECONDS": offset,
        "tau_ms": None if tau is None else int(tau),
        "touch_in_zone": int(agg.get("touch_in_zone") or 0),
    }


def finite_feature(row: dict, name: str) -> bool:
    value = row.get(name)
    return value is not None and math.isfinite(float(value))


def baseline_ready(row: dict) -> bool:
    needed = (
        "END_POSITION_X", K.CV1_NAME, K.OFFSET_NAME, "disp",
    )
    for name in needed:
        value = row.get(name)
        if value is None or not math.isfinite(float(value)):
            return False
    if row.get("vol_tercile") is None:
        return False
    if not row.get("trade_covered"):
        return False
    if int(row.get("touch_in_zone") or 0) < 1:
        return False
    offset = float(row[K.OFFSET_NAME])
    if offset < 0.0 or offset >= 300.0:
        return False
    return bool(row.get("nuisance_ok"))
