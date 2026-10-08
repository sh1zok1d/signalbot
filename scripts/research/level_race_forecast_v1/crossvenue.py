"""OTHER_VENUE_MEDIAN_MOVE exactly as #363 (C1, design §8). Reuses the #363 series and feature code."""

from __future__ import annotations

from typing import Optional

from scripts.research.level_cross_venue_reaction_discovery_v1.features import log_return, orient
from scripts.research.level_cross_venue_reaction_discovery_v1.series import load_reaction_series
from scripts.research.level_touch_degradation_v1 import constants as K352

from . import constants as K


def ovmm_for(series: dict, open_ms: int, side: int) -> Optional[float]:
    """Mean of the Bybit and OKX oriented log moves from close(T - 5m bar) to close(T + 10m bar)."""
    base = open_ms - K352.BAR_MS
    dec = open_ms + 2 * K352.BAR_MS
    vals = []
    for name in ("BYBIT_LINEAR_BTCUSDT_PERP", "OKX_BTC_USDT_SWAP_PERP"):
        s = series[name]
        r = orient(log_return(s.close_at(base), s.close_at(dec)), side)
        if r is None:
            return None
        vals.append(r)
    return 0.5 * (vals[0] + vals[1])


def attach_ovmm(rows: list[dict], bars) -> list[dict]:
    """All three venues required (#363): the Binance closes at j-1 and j+2 must exist as well."""
    import math
    series = load_reaction_series()
    bars_t0 = int(bars.t0)
    out = []
    for r in rows:
        v = None
        if r["landmark"] == "T15":
            oms = int(bars_t0 + r["j"] * K352.BAR_MS)
            j = int(r["j"])
            okb = j >= 1 and math.isfinite(float(bars.close[j - 1])) and math.isfinite(float(bars.close[j + 2]))
            if oms >= K.C1_START_MS and okb:
                v = ovmm_for(series, oms, int(r["side"]))
        out.append({**r, "ovmm": v})
    return out
