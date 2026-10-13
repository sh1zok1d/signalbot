"""Outcome-free information bounds for multi-timeframe directional questions (no market outcome is read).

For each surface (BitMEX 2016-19, CORE 2020-24, Binance 2025-26; the V1/V2 occupancy feature rows, R_1H and Y dropped
on load) and horizon H in {1h, 4h, 8h, 24h}: the across-replication SE of a rank correlation between a fixed real
feature and synthetic H-step returns (cumulated per-bar N(0,1) innovations on the surface's own 5m grid, so overlapping
anchors share innovations exactly as real targets do). MDE80 = 2.8 SE (two-sided 5 %, 80 % power, one pre-specified
feature, no search penalty).
  all_15m             RP4H (fast-varying) at every 15-minute anchor;
  aligned_nonoverlap  only decisions at UTC-aligned H closes (non-overlapping targets);
  block_const         a feature held constant within each UTC-aligned H block (a closed-HTF-bar feature), all anchors.

    python -m scripts.research.mtf_directional_audit_v1.power_bounds OUT.json"""
from __future__ import annotations

import json
import sys

import numpy as np

from scripts.research.multiscale_occupancy_v2.data import load_features
from scripts.research.rp4h_bitmex_temporal_v1.parent import average_ranks_fast

ERAS = {0: "BITMEX_2016_2019", 1: "CORE_2020_2024", 2: "BINANCE_2025_2026"}
H = {"1h": 12, "4h": 48, "8h": 96, "24h": 288}
REPS = 120


def _se(xs: np.ndarray, b: np.ndarray, h: int, nb: int, rng) -> float:
    xs = (xs - xs.mean()) / xs.std()
    rh = np.empty((xs.size, REPS))
    for r in range(REPS):
        c = np.concatenate([[0.0], np.cumsum(rng.standard_normal(nb))])
        ry = average_ranks_fast(c[b + 1 + h] - c[b + 1])
        rh[:, r] = (ry - ry.mean()) / ry.std()
    return float(((xs @ rh) / xs.size).std(ddof=1))


def main() -> None:
    rows = load_features()
    rng = np.random.default_rng(7)
    out = {}
    for e, name in ERAS.items():
        m = rows["era"] == e
        bars, t, x = rows["bar"][m], rows["close_ms"][m], rows["rp"][m]
        nb = int(bars.max()) + 300
        for hn, h in H.items():
            ok = bars + h < nb - 1
            blk = h * 300_000
            aligned = ok & ((t % blk) == 0)
            at_b = (t % blk) == 0
            last = np.maximum.accumulate(np.where(at_b, np.arange(t.size), -1))
            xb = np.where(last >= 0, x[np.maximum(last, 0)], np.nan)
            for sub, sel, feat in (("all_15m", ok, x), ("aligned_nonoverlap", aligned, x),
                                   ("block_const", ok & (last >= 0), xb)):
                se = _se(average_ranks_fast(feat[sel]), bars[sel], h, nb, rng)
                out[f"{name}|{hn}|{sub}"] = {"n": int(sel.sum()), "se": se, "mde80": 2.8 * se}
                print(name, hn, sub, int(sel.sum()), round(se, 4), round(2.8 * se, 4), flush=True)
    with open(sys.argv[1], "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, sort_keys=True)


if __name__ == "__main__":
    main()
