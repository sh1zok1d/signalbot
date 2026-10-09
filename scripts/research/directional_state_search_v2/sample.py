"""Dense 5m grid, 15-minute anchors, baseline, target and ISO-week blocks for the CORE price/flow families."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import constants as K
from . import features as F


def anchor_index(open_ms: np.ndarray) -> np.ndarray:
    n = open_ms.size
    phase = ((open_ms - K.PHASE_ORIGIN_MS) // K.BAR_MS) % 3 == 2
    i = np.flatnonzero(phase)
    return i[(i >= K.LOOKBACK_24H) & (i + K.HORIZON_1H < n)]


def blocks_of(t_close_ms: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    ts = pd.to_datetime(t_close_ms, unit="ms", utc=True)
    iso = ts.isocalendar()
    blocks = iso.year.to_numpy(dtype=np.int64) * 100 + iso.week.to_numpy(dtype=np.int64)
    return blocks, ts.year.to_numpy(dtype=np.int64)


def core_frame(bars: dict) -> dict:
    """Baseline, target and every CORE price/flow state at the anchors (the target is kept apart)."""
    base = F.baseline(bars)
    idx = anchor_index(bars["open_ms"])
    keep = np.isfinite(base["rp"][idx]) & np.isfinite(base["ret4"][idx]) & np.isfinite(base["rv4"][idx]) \
        & np.isfinite(base["r1"][idx])
    idx = idx[keep]
    spa = F.spa_family(bars["close"])
    flow = F.flow_family(bars)
    states = {k: v[idx] for k, v in {**spa, **flow}.items()}
    for fn in (F.occupancy, F.countermove, F.rejection):
        states.update(fn(bars, idx))
    t_close = bars["open_ms"][idx] + K.BAR_MS
    blocks, year = blocks_of(t_close)
    return {"idx": idx, "t_close_ms": t_close, "blocks": blocks, "year": year,
            "RP4H": base["rp"][idx], "RET_4H": base["ret4"][idx], "RV_4H": base["rv4"][idx],
            "R_1H": base["r1"][idx], "states": states}
