"""Outcome-free rows of the two candidate surfaces on the exact Unit-1 definitions.

Anchors and RP4H, RET_4H, RV_4H, width, RET_1H, RET_15M: the canonical Unit A (BitMEX) and Unit B (Binance 2025-26)
samples, imported. TS_24H = |RET_24H| / RV_24H by the DSS V2 function Unit 1 used (spa_family), on the surface's own
grid, defined only when the 289 closes i-288..i are all present (vacuous on CORE: no missing close; verified).
R_1H is dropped on load and never returned: this module reads no outcome."""
from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.research.directional_state_search_v2.features import spa_family

from . import constants as K

KEEP = ("rp", "ret4", "rv4", "width", "ret1h", "ret15", "close_ms")


def ts_on_grid(close: np.ndarray) -> np.ndarray:
    f = spa_family(close)
    with np.errstate(invalid="ignore", divide="ignore"):
        ts = np.abs(f["RET_24H"]) / f["RV_24H"]
    ok = np.isfinite(close).astype(np.float64)
    c = np.concatenate([[0.0], np.cumsum(ok)])
    w = K.LOOKBACK_24H + 1
    full = np.zeros(close.size, dtype=bool)
    full[w - 1:] = (c[w:] - c[:-w]) == w
    return np.where(full & np.isfinite(ts), ts, np.nan)


def vol_scale(close: np.ndarray) -> np.ndarray:
    """Per-bar synthetic noise scale s_k: RMS of the real log returns of bars k-60..k-13 (past of every anchor whose
    1h target contains bar k); fallback to the surface median when fewer than 24 are finite; floor at 10 % of it."""
    r = np.full(close.size, np.nan)
    r[1:] = np.log(close[1:] / close[:-1])
    r2 = np.where(np.isfinite(r), r * r, 0.0)
    fin = np.isfinite(r).astype(np.float64)
    c2, cf = np.concatenate([[0.0], np.cumsum(r2)]), np.concatenate([[0.0], np.cumsum(fin)])
    n = close.size
    k = np.arange(n)
    hi = k - K.VOL_LAG_BARS + 1                 # exclusive end: bars <= k-13
    lo = hi - K.VOL_WINDOW_BARS
    valid = lo >= 0
    s = np.full(n, np.nan)
    a, b = lo[valid], hi[valid]
    cnt = cf[b] - cf[a]
    v = np.where(cnt >= K.VOL_MIN_FINITE, (c2[b] - c2[a]) / np.maximum(cnt, 1), np.nan)
    s[valid] = np.sqrt(v)
    med = float(np.nanmedian(s))
    s = np.where(np.isfinite(s) & (s > 0), s, med)
    return np.maximum(s, 0.1 * med)


def _rows(sample: dict, grid: dict, name: str) -> dict:
    bar = ((sample["close_ms"] - K.BAR_MS - int(grid["grid_open"][0])) // K.BAR_MS).astype(np.int64)
    ts = ts_on_grid(grid["close"])[bar]
    keep = np.isfinite(ts)
    out = {k: np.asarray(sample[k])[keep] for k in KEEP}
    out["ts"] = ts[keep]
    out["bar"] = bar[keep]
    iso = pd.to_datetime(out["close_ms"], unit="ms", utc=True).isocalendar()
    out["week"] = iso.year.to_numpy(dtype=np.int64) * 100 + iso.week.to_numpy(dtype=np.int64)
    out["year"] = pd.to_datetime(out["close_ms"], unit="ms", utc=True).year.to_numpy(dtype=np.int64)
    out["scale"] = vol_scale(grid["close"])
    out["n_bars"] = int(grid["close"].size)
    out["surface"] = name
    out["support"] = {"anchors_before_ts": int(keep.size), "anchors": int(keep.sum()),
                      "dropped_ts_undefined": int((~keep).sum()), "iso_weeks": int(np.unique(out["week"]).size),
                      "first": str(pd.to_datetime(out["close_ms"][0], unit="ms", utc=True)),
                      "last": str(pd.to_datetime(out["close_ms"][-1], unit="ms", utc=True)),
                      "by_year": {str(y): int((out["year"] == y).sum()) for y in sorted(set(out["year"].tolist()))},
                      "ts_quantiles": [float(v) for v in np.quantile(out["ts"], [0.1, 0.25, 0.5, 0.75, 0.9])],
                      "share_by_unit1_tercile": [float(v) for v in np.bincount(
                          np.digitize(out["ts"], K.UNIT1_TS_TERCILE_EDGES), minlength=3) / keep.sum()]}
    return out


def load_bitmex() -> dict:
    from scripts.research.rp4h_bitmex_temporal_v1.evaluate import build_sample
    from scripts.research.rp4h_bitmex_temporal_v1.grid import load_series, place
    series = load_series()
    sample = build_sample(series)
    sample.pop("r1")
    return _rows(sample, place(series), K.SURFACES[0])


def load_binance_2025_2026() -> dict:
    from scripts.research.rp4h_binance_2025_2026_temporal_v1 import data as DB
    from scripts.research.rp4h_binance_2025_2026_temporal_v1.evaluate import assert_census, build_sample
    series = DB.load_series()
    assert_census(DB.census(series))
    sample = build_sample(series)
    sample.pop("r1")
    return _rows(sample, DB.place(series), K.SURFACES[1])


def load(name: str) -> dict:
    return load_bitmex() if name == K.SURFACES[0] else load_binance_2025_2026()
