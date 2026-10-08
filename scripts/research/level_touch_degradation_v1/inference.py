"""Direct standardization and week-cluster bootstrap. No market I/O.

The estimand is the touch-1-weighted average of stratum risk differences:

    Δ_k = Σ_s w_s [p(BREAK | touch bucket k, s) − p(BREAK | touch = 1, s)]

with w_s the touch-1 share of stratum s, and s = family × approach side × volatility tercile.
Strata with fewer than MIN_ARM events in either arm are dropped and the weights renormalized.
NEITHER stays in the denominator. AMBIGUOUS is excluded by the caller.

Uncertainty is a percentile interval from resampling the product-week of the touch.
Tercile edges are an argument: the caller freezes them from feature sigmas, not from Y.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from . import constants as K

_FAMILY = {name: i for i, name in enumerate(K.FAMILIES)}
_N_STRATA = len(K.FAMILIES) * 2 * 3


def tercile_edges(sigmas: np.ndarray) -> tuple[float, float]:
    s = np.asarray(sigmas, dtype=float)
    s = s[np.isfinite(s)]
    if s.size < 3:
        return (math.nan, math.nan)
    lo, hi = np.quantile(s, [1.0 / 3.0, 2.0 / 3.0])
    return float(lo), float(hi)


def _tercile(sigma: float, lo: float, hi: float) -> int:
    if not math.isfinite(sigma) or not math.isfinite(lo):
        return -1
    if sigma <= lo:
        return 0
    if sigma <= hi:
        return 1
    return 2


def _stratum(family: str, side: int, tercile: int) -> int:
    return _FAMILY[family] * 6 + (0 if side > 0 else 1) * 3 + tercile


def pack(rows: list[dict], edges: tuple[float, float]) -> dict:
    """Rows already restricted to BREAK/REJECT/NEITHER."""
    n = len(rows)
    y = np.zeros(n, dtype=np.float64)
    stratum = np.full(n, -1, dtype=np.int16)
    bucket = np.zeros(n, dtype=np.int8)
    week = np.zeros(n, dtype=np.int64)
    year = np.zeros(n, dtype=np.int16)
    family = np.zeros(n, dtype=np.int8)
    side = np.zeros(n, dtype=np.int8)
    lo, hi = edges
    bmap = {"1": 0, "2": 1, "3+": 2}
    for i, r in enumerate(rows):
        y[i] = 1.0 if r["outcome"] == "BREAK" else 0.0
        ter = _tercile(float(r["sigma"]), lo, hi)
        stratum[i] = _stratum(r["family"], int(r["side"]), ter) if ter >= 0 else -1
        bucket[i] = bmap[r["bucket"]]
        week[i] = int(r["week"])
        year[i] = int(r["year"])
        family[i] = _FAMILY[r["family"]]
        side[i] = 0 if int(r["side"]) > 0 else 1
    return {"y": y, "stratum": stratum, "bucket": bucket, "week": week, "year": year,
            "family": family, "side": side, "edges": (lo, hi)}


def _arm(counts, succ, keep) -> tuple[Optional[float], Optional[float], float]:
    """(p_reference, p_compare, retained reference weight) on `keep`."""
    den = float(counts[keep, 0].sum()) if keep.any() else 0.0
    n1 = float(counts[:, 0].sum())
    if den <= 0 or n1 <= 0:
        return None, None, 0.0
    w = counts[keep, 0] / den
    p1 = float(np.sum(w * (succ[keep, 0] / counts[keep, 0])))
    pk = float(np.sum(w * (succ[keep, 1] / counts[keep, 1])))
    return p1, pk, den / n1


def _std_delta(y, stratum, bucket, weight, min_arm: int) -> dict:
    """Standardized rates and differences under per-event multiplicity `weight`."""
    key = stratum.astype(np.int32) * 3 + bucket.astype(np.int32)
    valid = stratum >= 0
    counts = np.bincount(key[valid], weights=weight[valid], minlength=_N_STRATA * 3)
    succ = np.bincount(key[valid], weights=weight[valid] * y[valid], minlength=_N_STRATA * 3)
    counts = counts.reshape(_N_STRATA, 3)
    succ = succ.reshape(_N_STRATA, 3)
    keep2 = (counts[:, 0] >= min_arm) & (counts[:, 1] >= min_arm)
    keep3 = (counts[:, 0] >= min_arm) & (counts[:, 2] >= min_arm)
    p1_2, p2, share2 = _arm(counts[:, [0, 1]], succ[:, [0, 1]], keep2)
    p1_3, p3, share3 = _arm(counts[:, [0, 2]], succ[:, [0, 2]], keep3)
    return {
        "d2": None if p1_2 is None else p2 - p1_2,
        "d3": None if p1_3 is None else p3 - p1_3,
        "p1_for_2": p1_2, "p2": p2, "share2": share2,
        "p1_for_3": p1_3, "p3": p3, "share3": share3,
    }


def _crude(y, bucket, weight) -> tuple[Optional[float], Optional[float]]:
    out = []
    for k in (1, 2):
        m1 = bucket == 0
        mk = bucket == k
        n1 = float(weight[m1].sum())
        nk = float(weight[mk].sum())
        if n1 <= 0 or nk <= 0:
            out.append(None)
            continue
        out.append(float(weight[mk] @ y[mk] / nk - weight[m1] @ y[m1] / n1))
    return out[0], out[1]


def _resample_deltas(y, stratum, bucket, inverse, wcount, draws, rng, min_arm, standardized):
    """Week-resampled Δ₂ and Δ₃. One `integers` draw of shape (draws, weeks), same stream as a loop."""
    draw = rng.integers(0, wcount, size=(draws, wcount))
    mult = np.zeros((draws, wcount), dtype=np.float64)
    for i in range(draws):
        mult[i] = np.bincount(draw[i], minlength=wcount)
    weight = mult[:, inverse]
    if not standardized:
        d2 = np.full(draws, np.nan)
        d3 = np.full(draws, np.nan)
        for k, dest in ((1, d2), (2, d3)):
            m1 = bucket == 0
            mk = bucket == k
            n1 = weight[:, m1].sum(axis=1)
            nk = weight[:, mk].sum(axis=1)
            ok = (n1 > 0) & (nk > 0)
            p1 = np.zeros(draws)
            pk = np.zeros(draws)
            p1[ok] = (weight[:, m1][ok] * y[m1]).sum(axis=1) / n1[ok]
            pk[ok] = (weight[:, mk][ok] * y[mk]).sum(axis=1) / nk[ok]
            dest[ok] = pk[ok] - p1[ok]
        return d2, d3
    counts = np.zeros((draws, _N_STRATA, 3), dtype=np.float64)
    succ = np.zeros((draws, _N_STRATA, 3), dtype=np.float64)
    for s in range(_N_STRATA):
        for k in range(3):
            m = (stratum == s) & (bucket == k)
            if not np.any(m):
                continue
            counts[:, s, k] = weight[:, m].sum(axis=1)
            succ[:, s, k] = (weight[:, m] * y[m]).sum(axis=1)
    out = []
    n1 = counts[:, :, 0].sum(axis=1)
    for k in (1, 2):
        keep = (counts[:, :, 0] >= min_arm) & (counts[:, :, k] >= min_arm)
        den = (counts[:, :, 0] * keep).sum(axis=1)
        ok = (den > 0) & (n1 > 0)
        with np.errstate(invalid="ignore", divide="ignore"):
            rate0 = np.where(counts[:, :, 0] > 0, succ[:, :, 0] / counts[:, :, 0], 0.0)
            ratek = np.where(counts[:, :, k] > 0, succ[:, :, k] / counts[:, :, k], 0.0)
        w = np.where(keep, counts[:, :, 0], 0.0) / np.where(ok, den, 1.0)[:, None]
        delta = (w * np.where(keep, ratek - rate0, 0.0)).sum(axis=1)
        delta = np.where(ok, delta, np.nan)
        out.append(delta)
    return out[0], out[1]


def _bootstrap(y, stratum, bucket, week, *, min_arm: int, draws: int, seed: int,
               standardized: bool) -> dict:
    empty = {"d2": None, "d3": None, "ci2": None, "ci3": None, "valid": 0, "share2": 0.0,
             "share3": 0.0, "p1_for_2": None, "p2": None, "p1_for_3": None, "p3": None, "weeks": 0}
    if week.size == 0:
        return empty
    _codes, inverse = np.unique(week, return_inverse=True)
    wcount = int(_codes.size)
    rng = np.random.default_rng(seed)
    point_w = np.ones(y.shape[0], dtype=np.float64)
    if standardized:
        point = _std_delta(y, stratum, bucket, point_w, min_arm)
    else:
        d2, d3 = _crude(y, bucket, point_w)
        point = {"d2": d2, "d3": d3, "share2": 1.0, "share3": 1.0,
                 "p1_for_2": None, "p2": None, "p1_for_3": None, "p3": None}
    d2s, d3s = _resample_deltas(y, stratum, bucket, inverse, wcount, draws, rng, min_arm, standardized)
    ok = np.isfinite(d2s) & np.isfinite(d3s)
    valid = int(ok.sum())
    def _ci(acc):
        if valid < K.BOOT_MIN_VALID_FRAC * draws:
            return None
        lo, hi = np.quantile(acc[ok], [K.CI_ALPHA / 2.0, 1.0 - K.CI_ALPHA / 2.0])
        return (float(lo), float(hi))
    return {**point, "ci2": _ci(d2s), "ci3": _ci(d3s), "valid": valid, "weeks": wcount}


def contrasts(rows: list[dict], edges: tuple[float, float], *, standardized: bool,
              min_arm: int = K.MIN_ARM, draws: int = K.BOOT_DRAWS, seed: int = K.BOOT_SEED) -> dict:
    packed = pack(rows, edges)
    return _bootstrap(packed["y"], packed["stratum"], packed["bucket"], packed["week"],
                      min_arm=min_arm, draws=draws, seed=seed, standardized=standardized)


def subset_contrasts(rows: list[dict], edges: tuple[float, float], *, mask_fn, standardized: bool,
                     seed: int) -> dict:
    kept = [r for r in rows if mask_fn(r)]
    return contrasts(kept, edges, standardized=standardized, seed=seed)


def bucket_counts(touches: list[dict]) -> dict:
    """Integer tallies. `analysis` is BREAK+REJECT+NEITHER among feature-eligible touches."""
    buckets = {b: {"geometric": 0, "feature_eligible": 0, "BREAK": 0, "REJECT": 0,
                   "NEITHER": 0, "AMBIGUOUS": 0, "analysis": 0} for b in K.TOUCH_BUCKETS}
    for t in touches:
        b = t["bucket"]
        buckets[b]["geometric"] += 1
        if t.get("feature_eligible"):
            buckets[b]["feature_eligible"] += 1
        y = t.get("outcome")
        if t.get("feature_eligible") and y in ("BREAK", "REJECT", "NEITHER", "AMBIGUOUS"):
            buckets[b][y] += 1
            if y != "AMBIGUOUS":
                buckets[b]["analysis"] += 1
    return buckets


def analysis_rows(touches: list[dict]) -> list[dict]:
    return [t for t in touches
            if t.get("feature_eligible") and t.get("outcome") in ("BREAK", "REJECT", "NEITHER")
            and t.get("sigma") is not None]


def feature_sigmas(touches: list[dict]) -> np.ndarray:
    return np.asarray([t["sigma"] for t in touches if t.get("feature_eligible") and t.get("sigma") is not None],
                      dtype=float)


def planning_mde(n_a: int, n_b: int, deff: float) -> Optional[float]:
    """Two-sided 5%, 80% power, planning rate 0.5. Outcome-blind."""
    if n_a < 1 or n_b < 1 or not math.isfinite(deff) or deff <= 0:
        return None
    se = math.sqrt(0.25 * (1.0 / n_a + 1.0 / n_b) * deff)
    return K.PLANNING_Z * se
