"""Three canonical series, two venues. Each series keeps its own grid: no feature window and no target crosses a
series boundary. Training never mixes venues (BitMEX trains on BitMEX; Binance 2020-26 on Binance only).
Imported loaders and samples: BitMEX (RP4H Unit A), CORE (RP4H_TREND_REGIME_MODULATION_V1 sample),
Binance 2025-26 (RP4H Unit B canonical surface; E1 window and E1-development slice never requested)."""
from __future__ import annotations

import numpy as np

from scripts.research.rp4h_binance_2025_2026_temporal_v1 import data as DB
from scripts.research.rp4h_binance_2025_2026_temporal_v1.evaluate import assert_census
from scripts.research.rp4h_binance_2025_2026_temporal_v1.evaluate import build_sample as build_b
from scripts.research.rp4h_bitmex_temporal_v1.evaluate import build_sample as build_a
from scripts.research.rp4h_bitmex_temporal_v1.grid import load_series as load_bitmex
from scripts.research.rp4h_bitmex_temporal_v1.grid import place as place_a
from scripts.research.rp4h_bitmex_temporal_v1.grid import preflight_census
from scripts.research.rp4h_trend_regime_v1.sample import core_bars, core_sample

from . import constants as K
from .features import occ_l

B1_COLS = ("rp", "ret4", "rv4", "ret1h", "ret15")


def rp_identity(grid: dict, bar: np.ndarray, rp: np.ndarray) -> float:
    """Max |RP4H recomputed from the grid at `bar` - the sample's RP4H|: proves the bar index of every row."""
    offs = np.arange(-47, 1)
    w = bar[:, None] + offs[None, :]
    hi, lo = grid["high"][w].max(axis=1), grid["low"][w].min(axis=1)
    return float(np.max(np.abs((grid["close"][bar] - lo) / (hi - lo) - rp)))


def _era_rows(s: dict, grid: dict, bar: np.ndarray, era: int) -> tuple:
    rows = {c: np.asarray(s[c]) for c in B1_COLS + ("r1", "close_ms")}
    rows["bar"] = bar.astype(np.int64)
    if rp_identity(grid, rows["bar"], rows["rp"]) > 1e-12:
        raise SystemExit(f"BAR_INDEX_IDENTITY_{era}")
    for h in K.LOOKBACK_HOURS:
        rows[f"OCC_{h}H"] = occ_l(grid["high"], grid["low"], grid["close"], rows["bar"], h)
    keep = np.ones(rows["r1"].size, dtype=bool)
    for h in K.LOOKBACK_HOURS:
        keep &= np.isfinite(rows[f"OCC_{h}H"])
    out = {k: v[keep] for k, v in rows.items()}
    out["era"] = np.full(int(keep.sum()), era, dtype=np.int64)
    out["venue"] = np.full(int(keep.sum()), K.ERA_VENUE[era], dtype=np.int64)
    return out, {"sample_rows": int(keep.size), "rows_with_all_occ": int(keep.sum())}


def load_all() -> dict:
    bitmex = load_bitmex()
    census_a = preflight_census(bitmex)
    ga = place_a(bitmex)
    a = build_a(bitmex)
    ra, ca = _era_rows(a, ga, (a["close_ms"] - K.BAR_MS - int(ga["grid_open"][0])) // K.BAR_MS, 0)
    bars = core_bars()
    c = core_sample(bars, need_24h=False)
    rc, cc = _era_rows(c, bars, c["idx"], 1)
    binance = DB.load_series()
    census_b = DB.census(binance)
    assert_census(census_b)
    gb = DB.place(binance)
    b = build_b(binance)
    rb, cb = _era_rows(b, gb, (b["close_ms"] - K.BAR_MS - int(gb["grid_open"][0])) // K.BAR_MS, 2)
    out = {k: np.concatenate([ra[k], rc[k], rb[k]]) for k in ra}
    if np.any(np.diff(out["close_ms"]) <= 0):
        raise SystemExit("CHRONOLOGY_NOT_STRICT")
    for k in B1_COLS + ("r1",):
        if not np.isfinite(out[k]).all():
            raise SystemExit(f"NONFINITE_{k}")
    out["y"] = (out["r1"] > 0).astype(np.float64)
    out["_census"] = {"bitmex": census_a, "binance_2025_2026": census_b,
                      "rows_by_era": {K.ERAS[0]: ca, K.ERAS[1]: cc, K.ERAS[2]: cb}}
    return out
