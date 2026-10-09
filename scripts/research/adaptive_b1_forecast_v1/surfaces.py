"""The three canonical surfaces in one chronology. Each series keeps its own grid: no feature window and no target
crosses a venue boundary (anchors near a boundary drop by the RP4H missingness rules). Imported loaders and samples:
BitMEX (RP4H Unit A), CORE (RP4H_TREND_REGIME_MODULATION_V1 sample), Binance 2025-26 (RP4H Unit B)."""
from __future__ import annotations

import numpy as np

from scripts.research.rp4h_binance_2025_2026_temporal_v1 import data as DB
from scripts.research.rp4h_binance_2025_2026_temporal_v1.evaluate import assert_census
from scripts.research.rp4h_binance_2025_2026_temporal_v1.evaluate import build_sample as build_b
from scripts.research.rp4h_bitmex_temporal_v1.evaluate import build_sample as build_a
from scripts.research.rp4h_bitmex_temporal_v1.grid import load_series as load_bitmex
from scripts.research.rp4h_bitmex_temporal_v1.grid import preflight_census
from scripts.research.rp4h_trend_regime_v1.sample import core_bars, core_sample

from . import constants as K

COLS = ("rp", "ret4", "rv4", "ret1h", "ret15", "r1", "close_ms")


def _rows(s: dict, era: int, bar_index: np.ndarray) -> dict:
    out = {c: np.asarray(s[c]) for c in COLS}
    out["era"] = np.full(out["r1"].size, era, dtype=np.int64)
    out["bar"] = bar_index.astype(np.int64)                    # anchor bar index on the era's own dense grid
    return out


def load_all() -> dict:
    bitmex = load_bitmex()
    census_a = preflight_census(bitmex)
    a = build_a(bitmex)
    a_bar = (a["close_ms"] - 300_000 - int(bitmex["open_ms"][0])) // 300_000
    core = core_sample(core_bars(), need_24h=False)
    binance = DB.load_series()
    census_b = DB.census(binance)
    assert_census(census_b)
    b = build_b(binance)
    b_bar = (b["close_ms"] - 300_000 - 1_735_689_600_000) // 300_000
    parts = [_rows(a, 0, a_bar), _rows(core, 1, core["idx"]), _rows(b, 2, b_bar)]
    out = {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}
    if np.any(np.diff(out["close_ms"]) <= 0):
        raise SystemExit("CHRONOLOGY_NOT_STRICT")
    for c in ("rp", "ret4", "rv4", "ret1h", "ret15", "r1"):
        if not np.isfinite(out[c]).all():
            raise SystemExit(f"NONFINITE_{c}")
    out["y"] = (out["r1"] > 0).astype(np.float64)
    out["_census"] = {"bitmex": census_a, "binance_2025_2026": census_b}
    return out
