"""CORE BTCUSDT perpetual 2020-24 sample on the RP4H grid (shared with ADAPTIVE_B1_FORECAST_V1).

Bars: the pinned CORE 1m objects aggregated to 5m (DIRECTIONAL_STATE_SEARCH_V2 loader, imported). Features: the RP4H
parent code and Unit A's local returns (imported). Anchors: the RP4H 15-minute phase. Past-only states; R_1H kept apart."""
from __future__ import annotations

import numpy as np

from scripts.research.directional_state_search_v2 import data as DD
from scripts.research.directional_state_search_v2.features import spa_family
from scripts.research.rp4h_bitmex_temporal_v1.grid import local_returns
from scripts.research.rp4h_bitmex_temporal_v1.parent import features

from . import constants as K

PHASE_ORIGIN_MS = 1_577_836_800_000


def core_bars() -> dict:
    return DD.to_5m(DD.load_core_1m())


def core_sample(bars: dict, need_24h: bool) -> dict:
    """Anchors with RP4H, RET_4H, RV_4H, width and R_1H finite (target bar inside the surface); with need_24h also
    TS_24H finite. RET_1H and RET_15M lie inside the RP4H window."""
    o = bars["open_ms"]
    if int(o[0]) != K.SURFACE_START_MS or int(o[-1]) != K.SURFACE_END_MS - K.BAR_MS or np.any(np.diff(o) != K.BAR_MS):
        raise SystemExit("CORE_GRID")
    f = features(bars["high"], bars["low"], bars["close"])
    loc = local_returns(bars["close"])
    s24 = spa_family(bars["close"])
    ts = np.abs(s24["RET_24H"]) / s24["RV_24H"]
    phase = ((o - PHASE_ORIGIN_MS) // K.BAR_MS) % 3 == 2
    ok = phase & np.isfinite(f["rp"]) & np.isfinite(f["ret4"]) & np.isfinite(f["rv4"]) & np.isfinite(f["width"]) \
        & np.isfinite(f["r1"])
    if need_24h:
        ok &= np.isfinite(ts)
    idx = np.flatnonzero(ok)
    out = {k: f[k][idx] for k in ("rp", "ret4", "rv4", "width", "r1")}
    out["ret1h"], out["ret15"] = loc["ret1h"][idx], loc["ret15"][idx]
    out["ts"] = ts[idx]
    if not (np.isfinite(out["ret1h"]).all() and np.isfinite(out["ret15"]).all()):
        raise SystemExit("LOCAL_CONTROLS_OUTSIDE_SAMPLE")
    out["close_ms"] = o[idx] + K.BAR_MS
    out["idx"] = idx
    return out
