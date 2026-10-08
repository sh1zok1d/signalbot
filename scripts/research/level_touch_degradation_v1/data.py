"""Load the discovery surface. Price bars only, 2020-01-01 inclusive to 2025-01-01 exclusive.

The bytes are CORE_BTC_BINANCE_V0 1m klines aggregated to complete 5m bins by the frozen DH1
loader. No 2025/2026 object, no E1 holdout, no second venue.
"""

from __future__ import annotations

import numpy as np

from beta.hist_series import Bars

from scripts.research.dh1.data import load_binance_perp_5m, to_bars

from . import constants as K


def assert_panel_legal(open_ms: np.ndarray) -> None:
    if open_ms.size == 0:
        raise RuntimeError("empty price panel")
    if int(open_ms[0]) < K.DATA_START_MS or int(open_ms[-1]) >= K.SURFACE_END_MS:
        raise RuntimeError("panel leaves the legal 2020-01..2024-12 surface")
    if np.any(open_ms >= K.SURFACE_END_MS):
        raise RuntimeError("panel contains a bar at or after 2025-01-01")
    in_e1 = (open_ms >= K.E1_START_MS) & (open_ms < K.E1_END_MS)
    if np.any(in_e1):
        raise RuntimeError("panel overlaps the E1-RUN-001 holdout")


def load_discovery_bars() -> Bars:
    panel = load_binance_perp_5m()
    assert_panel_legal(panel["open_ms"])
    bars = to_bars(panel, K.DATA_START_MS, K.SURFACE_END_MS)
    assert_panel_legal(bars.times)
    if bars.end_ms > K.SURFACE_END_MS:
        raise RuntimeError("grid ends after the legal surface")
    return bars
