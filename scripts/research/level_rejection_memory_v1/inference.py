"""Linear probability model with a predeclared cluster bootstrap.

The primary coefficient is the change in the historical frequency per +1 SD of the
frozen predictor. Standardization constants are arguments: the caller freezes them
from predictors, not from Y, and does not refit them inside the bootstrap.
"""

from __future__ import annotations

import math

import numpy as np

from . import constants as K


def _moments(values: list[float]) -> tuple[float, float]:
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 2:
        return math.nan, math.nan
    return float(x.mean()), float(x.std(ddof=0))


def freeze_scales(pairs: list[dict]) -> dict:
    """Predictor moments and speed tertile edges. No outcome field is read."""
    speed = [p["speed_raw"] for p in pairs]
    linear = [p["linear_raw"] for p in pairs]
    gap = [p["log_gap"] for p in pairs]
    over = [p["overshoot"] for p in pairs if p.get("overshoot") is not None]
    s_mean, s_sd = _moments(speed)
    l_mean, l_sd = _moments(linear)
    g_mean, g_sd = _moments(gap)
    o_mean, o_sd = _moments(over)
    xs = np.asarray(speed, dtype=float)
    xs = xs[np.isfinite(xs)]
    if xs.size < 3:
        q_lo = q_hi = math.nan
    else:
        q_lo, q_hi = (float(v) for v in np.quantile(xs, [1.0 / 3.0, 2.0 / 3.0]))
    return {
        "speed_mean": s_mean, "speed_sd": s_sd,
        "linear_mean": l_mean, "linear_sd": l_sd,
        "gap_mean": g_mean, "gap_sd": g_sd,
        "overshoot_mean": o_mean, "overshoot_sd": o_sd,
        "speed_q33": q_lo, "speed_q66": q_hi,
        "n_pairs_scaled": len(pairs),
    }


def _z(value: float, mean: float, sd: float) -> float:
    if not math.isfinite(sd) or sd <= 0 or not math.isfinite(value) or not math.isfinite(mean):
        return math.nan
    return (value - mean) / sd


def speed_band(speed_raw: float, q33: float, q66: float) -> Optional[str]:
    if not math.isfinite(speed_raw) or not math.isfinite(q33) or not math.isfinite(q66):
        return None
    if speed_raw <= q33:
        return "slow"
    if speed_raw > q66:
        return "fast"
    return "mid"


def _columns_for(spec: str) -> tuple[str, ...]:
    cols = list(K.PRIMARY_COLUMNS)
    if spec == "no_touch":
        cols.remove("touch3")
    elif spec == "no_gap":
        cols.remove("gap_z")
    elif spec == "year":
        for name in ("y2021", "y2022", "y2023", "y2024"):
            cols.remove(name)
    elif spec == "family":
        cols.remove("fam_week")
        cols.remove("fam_month")
    elif spec == "side":
        cols.remove("support")
    elif spec == "bucket":
        cols.remove("touch3")
    elif spec != "full":
        raise ValueError(spec)
    return tuple(cols)


def _predictor(pair: dict, scales: dict, which: str) -> float:
    if which == "speed":
        return _z(pair["speed_raw"], scales["speed_mean"], scales["speed_sd"])
    if which == "linear":
        return _z(pair["linear_raw"], scales["linear_mean"], scales["linear_sd"])
    if which == "overshoot":
        if pair.get("overshoot") is None:
            return math.nan
        return _z(pair["overshoot"], scales["overshoot_mean"], scales["overshoot_sd"])
    raise ValueError(which)


def design_row(pair: dict, scales: dict, columns: tuple[str, ...], which: str) -> Optional[np.ndarray]:
    pred = _predictor(pair, scales, which)
    gap_z = _z(pair["log_gap"], scales["gap_mean"], scales["gap_sd"])
    if not math.isfinite(pred) or not math.isfinite(gap_z):
        return None
    values = {
        "intercept": 1.0,
        "speed_z": pred,
        "touch3": float(pair["touch3"]),
        "fam_week": 1.0 if pair["family"] == "WEEK" else 0.0,
        "fam_month": 1.0 if pair["family"] == "MONTH" else 0.0,
        "support": float(pair["support"]),
        "vol_mid": 1.0 if pair["vol_tercile"] == 1 else 0.0,
        "vol_high": 1.0 if pair["vol_tercile"] == 2 else 0.0,
        "gap_z": gap_z,
        "y2021": 1.0 if pair["year"] == 2021 else 0.0,
        "y2022": 1.0 if pair["year"] == 2022 else 0.0,
        "y2023": 1.0 if pair["year"] == 2023 else 0.0,
        "y2024": 1.0 if pair["year"] == 2024 else 0.0,
    }
    return np.array([values[c] for c in columns], dtype=float)


def _ols(x: np.ndarray, y: np.ndarray) -> Optional[float]:
    if x.shape[0] <= x.shape[1]:
        return None
    # A constant non-intercept column makes the point unidentified.
    for col in range(1, x.shape[1]):
        if np.unique(x[:, col]).size < 2:
            return None
    beta, _, rank, _ = np.linalg.lstsq(x, y, rcond=None)
    if int(rank) < x.shape[1] or not np.isfinite(beta[1]):
        return None
    return float(beta[1])


def _pack(pairs: list[dict], scales: dict, columns: tuple[str, ...], which: str, endpoint: str):
    rows_x = []
    ys = []
    clusters = []
    for p in pairs:
        row = design_row(p, scales, columns, which)
        if row is None:
            continue
        rows_x.append(row)
        ys.append(1.0 if p["next_outcome"] == endpoint else 0.0)
        clusters.append(p["cluster"])
    if not rows_x:
        return None
    keys = sorted(set(clusters))
    code = {k: i for i, k in enumerate(keys)}
    return (np.vstack(rows_x), np.asarray(ys, dtype=float),
            np.asarray([code[c] for c in clusters], dtype=int), len(keys))


def _bootstrap_coef_once(x, y, cluster, n_clusters: int, draws: int, seed: int):
    point = _ols(x, y)
    rng = np.random.default_rng(seed)
    membership = [np.flatnonzero(cluster == c) for c in range(n_clusters)]
    draw = rng.integers(0, n_clusters, size=(draws, n_clusters))
    acc = np.full(draws, np.nan)
    for b in range(draws):
        counts = np.bincount(draw[b], minlength=n_clusters)
        parts = [np.repeat(membership[c], int(counts[c])) for c in range(n_clusters) if counts[c]]
        if not parts:
            continue
        idx = np.concatenate(parts)
        beta = _ols(x[idx], y[idx])
        if beta is not None:
            acc[b] = beta
    ok = np.isfinite(acc)
    valid = int(ok.sum())
    ci = None
    if valid >= K.BOOT_MIN_VALID_FRAC * draws:
        lo, hi = np.quantile(acc[ok], [K.CI_ALPHA / 2.0, 1.0 - K.CI_ALPHA / 2.0])
        ci = (float(lo), float(hi))
    return point, ci, valid, n_clusters


def lpm_effect(pairs: list[dict], scales: dict, *, spec: str = "full", which: str = "speed",
               endpoint: str = "BREAK", draws: int = K.BOOT_DRAWS, seed: int = K.BOOT_SEED) -> dict:
    columns = _columns_for(spec)
    # Sensitivity predictors still occupy the speed_z column. The name is the slot, not the feature.
    packed = _pack(pairs, scales, columns, which, endpoint)
    if packed is None:
        return {"coef": None, "ci95": None, "bootstrap_valid": 0, "clusters": 0, "n": 0,
                "columns": list(columns), "endpoint": endpoint, "which": which, "spec": spec}
    x, y, cluster, n_clusters = packed
    coef, ci, valid, n_clusters = _bootstrap_coef_once(x, y, cluster, n_clusters, draws, seed)
    return {
        "coef": coef,
        "ci95": None if ci is None else [ci[0], ci[1]],
        "bootstrap_valid": valid,
        "clusters": n_clusters,
        "n": int(x.shape[0]),
        "columns": list(columns),
        "endpoint": endpoint,
        "which": which,
        "spec": spec,
    }


def rate_diff(pairs: list[dict], scales: dict, *, endpoint: str, band_a: str = "fast",
              band_b: str = "slow", draws: int = K.BOOT_DRAWS, seed: int = K.BOOT_SEED) -> dict:
    """Crude P(endpoint | band_a) − P(endpoint | band_b), cluster bootstrap."""
    q33, q66 = scales["speed_q33"], scales["speed_q66"]
    rows = []
    for p in pairs:
        band = speed_band(p["speed_raw"], q33, q66)
        if band not in (band_a, band_b):
            continue
        rows.append((p["cluster"], 1.0 if p["next_outcome"] == endpoint else 0.0, band))
    if not rows:
        return {"coef": None, "ci95": None, "bootstrap_valid": 0, "clusters": 0, "n": 0,
                "n_a": 0, "n_b": 0}
    keys = sorted({r[0] for r in rows})
    code = {k: i for i, k in enumerate(keys)}
    y = np.asarray([r[1] for r in rows], dtype=float)
    band = np.asarray([r[2] for r in rows])
    cluster = np.asarray([code[r[0]] for r in rows], dtype=int)
    n_clusters = len(keys)

    def _diff(idx):
        ya = y[idx][band[idx] == band_a]
        yb = y[idx][band[idx] == band_b]
        if ya.size == 0 or yb.size == 0:
            return None
        return float(ya.mean() - yb.mean())

    point = _diff(np.arange(y.size))
    rng = np.random.default_rng(seed)
    membership = [np.flatnonzero(cluster == c) for c in range(n_clusters)]
    draw = rng.integers(0, n_clusters, size=(draws, n_clusters))
    acc = np.full(draws, np.nan)
    for b in range(draws):
        counts = np.bincount(draw[b], minlength=n_clusters)
        parts = [np.repeat(membership[c], int(counts[c])) for c in range(n_clusters) if counts[c]]
        if not parts:
            continue
        beta = _diff(np.concatenate(parts))
        if beta is not None:
            acc[b] = beta
    ok = np.isfinite(acc)
    valid = int(ok.sum())
    ci = None
    if valid >= K.BOOT_MIN_VALID_FRAC * draws:
        lo, hi = np.quantile(acc[ok], [K.CI_ALPHA / 2.0, 1.0 - K.CI_ALPHA / 2.0])
        ci = [float(lo), float(hi)]
    return {"coef": point, "ci95": ci, "bootstrap_valid": valid, "clusters": n_clusters,
            "n": int(y.size), "n_fast": int((band == "fast").sum()) if band_a == "fast" else int((band == band_a).sum()),
            "n_slow": int((band == "slow").sum()) if band_b == "slow" else int((band == band_b).sum())}


def band_rates(pairs: list[dict], scales: dict) -> dict:
    q33, q66 = scales["speed_q33"], scales["speed_q66"]
    out = {}
    for name in ("slow", "mid", "fast"):
        rows = [p for p in pairs if speed_band(p["speed_raw"], q33, q66) == name]
        n = len(rows)
        counts = {k: sum(1 for p in rows if p["next_outcome"] == k) for k in ("BREAK", "REJECT", "NEITHER")}
        out[name] = {"n": n, **{k: counts[k] for k in counts},
                     **{f"p_{k.lower()}": (counts[k] / n if n else None) for k in counts}}
    return out


def planning_mde(n: int, deff: float) -> Optional[float]:
    """Rough SE scale for a unit-variance regressor in an LPM at the planning rate.

    This ignores covariates, so it is a lower bound on the adjusted uncertainty.
    It is an amount of information, not a gate.
    """
    if n < 2 or not math.isfinite(deff) or deff <= 0:
        return None
    p = K.PLANNING_RATE
    return K.PLANNING_Z * math.sqrt(p * (1.0 - p) / n * deff)


def slice_pairs(pairs: list[dict], *, year: int | None = None, family: str | None = None,
                side: int | None = None, bucket: str | None = None) -> list[dict]:
    out = pairs
    if year is not None:
        out = [p for p in out if p["year"] == year]
    if family is not None:
        out = [p for p in out if p["family"] == family]
    if side is not None:
        out = [p for p in out if p["side"] == side]
    if bucket is not None:
        out = [p for p in out if p["next_bucket"] == bucket]
    return out
