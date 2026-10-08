"""Adjusted linear probability slopes, tertiles, BH screening, cluster bootstrap.

Standardization constants are arguments. They are frozen from predictors and are not
refit inside a bootstrap or on a slice. The reported coefficient is always column
`feature_z`: the change in historical frequency per +1 SD of that feature.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from . import constants as K


def _moments(values: np.ndarray) -> tuple[float, float]:
    x = values[np.isfinite(values)]
    if x.size < 2:
        return math.nan, math.nan
    return float(x.mean()), float(x.std(ddof=0))


def freeze_scales(rows: list[dict], names: list[str]) -> dict:
    """Means, sds and tertile edges. No outcome field is read."""
    out = {"n": len(rows)}
    for name in list(names) + [K.DURATION_NUISANCE]:
        vals = np.array([math.nan if row.get(name) is None else float(row[name]) for row in rows], dtype=float)
        mean, sd = _moments(vals)
        finite = vals[np.isfinite(vals)]
        if finite.size < 3:
            q_lo = q_hi = math.nan
        else:
            q_lo, q_hi = (float(v) for v in np.quantile(finite, [1.0 / 3.0, 2.0 / 3.0]))
        out[name] = {"mean": mean, "sd": sd, "q33": q_lo, "q66": q_hi}
    return out


def _z(value, mean: float, sd: float) -> float:
    if value is None or not math.isfinite(float(value)) or not math.isfinite(mean) or not math.isfinite(sd) or sd <= 0:
        return math.nan
    return (float(value) - mean) / sd


def band_of(value, q33: float, q66: float) -> Optional[str]:
    if value is None or not math.isfinite(float(value)) or not math.isfinite(q33) or not math.isfinite(q66):
        return None
    if float(value) <= q33:
        return "low"
    if float(value) > q66:
        return "high"
    return "mid"


def columns_for(spec: str, *, drop_year: Optional[int] = None) -> tuple[str, ...]:
    cols = list(K.PRIMARY_COLUMNS)
    if spec == "no_touch":
        cols.remove("touch2")
        cols.remove("touch3")
    elif spec == "no_duration":
        cols.remove("log_steps_z")
    elif spec == "year":
        for name in ("y2021", "y2022", "y2023", "y2024"):
            cols.remove(name)
    elif spec == "family":
        cols.remove("fam_week")
        cols.remove("fam_month")
    elif spec == "side":
        cols.remove("support")
    elif spec == "loyo":
        if drop_year is None:
            raise ValueError("loyo needs drop_year")
        # 2020 is the reference. Leaving 2020 out makes every remaining row carry a
        # year dummy, so 2021 becomes the reference instead.
        drop = {"y2021"} if int(drop_year) == 2020 else {f"y{int(drop_year)}"}
        cols = [c for c in cols if c not in drop]
    elif spec != "full":
        raise ValueError(spec)
    if cols[1] != "feature_z":
        raise RuntimeError("feature_z must stay in column 1")
    return tuple(cols)


def _design_value(row: dict, scales: dict, column: str, feature: str) -> float:
    if column == "intercept":
        return 1.0
    if column == "feature_z":
        return _z(row.get(feature), scales[feature]["mean"], scales[feature]["sd"])
    if column == "log_steps_z":
        return _z(row.get("log_steps"), scales["log_steps"]["mean"], scales["log_steps"]["sd"])
    if column == "touch2":
        return float(row["touch2"])
    if column == "touch3":
        return float(row["touch3"])
    if column == "fam_week":
        return 1.0 if row["family"] == "WEEK" else 0.0
    if column == "fam_month":
        return 1.0 if row["family"] == "MONTH" else 0.0
    if column == "support":
        return float(row["support"])
    if column == "vol_mid":
        return 1.0 if row["vol_tercile"] == 1 else 0.0
    if column == "vol_high":
        return 1.0 if row["vol_tercile"] == 2 else 0.0
    if column.startswith("y"):
        return 1.0 if row["year"] == int(column[1:]) else 0.0
    raise ValueError(column)


def design_matrix(rows: list[dict], scales: dict, columns: tuple[str, ...], feature: str):
    kept = []
    xs = []
    clusters = []
    for row in rows:
        values = [_design_value(row, scales, column, feature) for column in columns]
        if not all(math.isfinite(v) for v in values):
            continue
        xs.append(values)
        kept.append(row)
        clusters.append(row["cluster"])
    if not xs:
        return None
    keys = sorted(set(clusters))
    code = {key: i for i, key in enumerate(keys)}
    x = np.asarray(xs, dtype=float)
    cluster = np.asarray([code[c] for c in clusters], dtype=int)
    return x, kept, cluster, len(keys)


def _ols(x: np.ndarray, y: np.ndarray) -> Optional[float]:
    if x.shape[0] <= x.shape[1]:
        return None
    for col in range(1, x.shape[1]):
        if np.unique(x[:, col]).size < 2:
            return None
    beta, _, rank, _ = np.linalg.lstsq(x, y, rcond=None)
    if int(rank) < x.shape[1] or not np.isfinite(beta[1]):
        return None
    return float(beta[1])


def _endpoint_y(rows: list[dict], endpoint: str) -> np.ndarray:
    return np.asarray([1.0 if row["outcome"] == endpoint else 0.0 for row in rows], dtype=float)


def _bootstrap(x, y, cluster, n_clusters: int, draws: int, seed: int):
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
    se = None
    if valid >= 2:
        se = float(acc[ok].std(ddof=1))
    if valid >= K.BOOT_MIN_VALID_FRAC * draws and valid >= 2:
        lo, hi = np.quantile(acc[ok], [K.CI_ALPHA / 2.0, 1.0 - K.CI_ALPHA / 2.0])
        ci = (float(lo), float(hi))
    return point, ci, se, valid, n_clusters


def wald_p(coef: Optional[float], se: Optional[float]) -> Optional[float]:
    """Two-sided normal p-value from the cluster-bootstrap standard error. A screen, not the estimand."""
    if coef is None or se is None or not math.isfinite(coef) or not math.isfinite(se):
        return None
    if se <= 0:
        return 1.0 if coef == 0 else 0.0
    z = abs(coef / se)
    return float(math.erfc(z / math.sqrt(2.0)))


def bh_adjust(pvalues: list[Optional[float]]) -> list[Optional[float]]:
    """Benjamini-Hochberg adjusted p-values. A missing p is treated as 1 and stays in m."""
    m = len(pvalues)
    if m == 0:
        return []
    usable = [1.0 if p is None or not math.isfinite(p) else float(p) for p in pvalues]
    order = sorted(range(m), key=lambda i: usable[i])
    adj = [None] * m
    running = 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        running = min(running, usable[i] * m / rank)
        adj[i] = running
    return adj


def lpm(rows: list[dict], scales: dict, feature: str, endpoint: str, *, spec: str = "full",
        drop_year: Optional[int] = None, draws: int = 0, seed: int = K.BOOT_SEED) -> dict:
    columns = columns_for(spec, drop_year=drop_year)
    built = design_matrix(rows, scales, columns, feature)
    empty = {
        "coef": None, "ci95": None, "se": None, "p": None, "bootstrap_valid": 0,
        "clusters": 0, "n": 0, "feature": feature, "endpoint": endpoint, "spec": spec,
        "drop_year": drop_year,
    }
    if built is None:
        return empty
    x, kept, cluster, n_clusters = built
    y = _endpoint_y(kept, endpoint)
    if draws <= 0:
        coef = _ols(x, y)
        return {**empty, "coef": coef, "n": int(x.shape[0]), "clusters": n_clusters}
    coef, ci, se, valid, n_clusters = _bootstrap(x, y, cluster, n_clusters, draws, seed)
    return {
        "coef": coef,
        "ci95": None if ci is None else [ci[0], ci[1]],
        "se": se,
        "p": wald_p(coef, se),
        "bootstrap_valid": valid,
        "clusters": n_clusters,
        "n": int(x.shape[0]),
        "feature": feature,
        "endpoint": endpoint,
        "spec": spec,
        "drop_year": drop_year,
    }


def tertile_diff(rows: list[dict], scales: dict, feature: str, endpoint: str, *,
                 draws: int = 0, seed: int = K.BOOT_SEED) -> dict:
    """Crude P(endpoint | high) - P(endpoint | low). Edges are the frozen predictor quantiles."""
    q33 = scales[feature]["q33"]
    q66 = scales[feature]["q66"]
    picked = []
    for row in rows:
        band = band_of(row.get(feature), q33, q66)
        if band not in ("low", "high"):
            continue
        picked.append((row["cluster"], 1.0 if row["outcome"] == endpoint else 0.0, band))
    counts = {"low": 0, "high": 0}
    for _, _, band in picked:
        counts[band] += 1
    empty = {"coef": None, "ci95": None, "se": None, "bootstrap_valid": 0, "clusters": 0,
             "n": 0, "n_low": counts["low"], "n_high": counts["high"],
             "feature": feature, "endpoint": endpoint, "spec": "tertile"}
    if not picked:
        return empty
    keys = sorted({item[0] for item in picked})
    code = {key: i for i, key in enumerate(keys)}
    y = np.asarray([item[1] for item in picked], dtype=float)
    high = np.asarray([1.0 if item[2] == "high" else 0.0 for item in picked], dtype=float)
    cluster = np.asarray([code[item[0]] for item in picked], dtype=int)
    x = np.column_stack([np.ones(len(picked)), high])
    # _ols reads column 1. Here column 1 is the high-band indicator, so the
    # coefficient is P(high) - P(low) only when the low band is the reference
    # and both bands are present. A constant column returns None.
    if draws <= 0:
        return {**empty, "coef": _ols(x, y), "n": int(x.shape[0]), "clusters": len(keys)}
    coef, ci, se, valid, n_clusters = _bootstrap(x, y, cluster, len(keys), draws, seed)
    return {
        **empty,
        "coef": coef,
        "ci95": None if ci is None else [ci[0], ci[1]],
        "se": se,
        "bootstrap_valid": valid,
        "clusters": n_clusters,
        "n": int(x.shape[0]),
    }


def bucket_rates(rows: list[dict], scales: dict, feature: str) -> dict:
    """All three tertiles, all three outcomes. Components of the high-low contrast, not extra cells."""
    q33 = scales[feature]["q33"]
    q66 = scales[feature]["q66"]
    bags = {name: {"BREAK": 0, "REJECT": 0, "NEITHER": 0, "n": 0} for name in ("low", "mid", "high")}
    for row in rows:
        band = band_of(row.get(feature), q33, q66)
        if band is None or row["outcome"] not in bags[band]:
            continue
        bags[band][row["outcome"]] += 1
        bags[band]["n"] += 1
    for band, bag in bags.items():
        n = bag["n"]
        for outcome in K.OUTCOMES:
            bag[f"p_{outcome}"] = None if n == 0 else bag[outcome] / n
    return bags


def shape_label(rates: dict, diff: dict) -> str:
    """Descriptive shape from the three tertile rates. Does not create a new threshold."""
    return _shape_from_probs(rates, diff)


def _shape_from_probs(rates: dict, diff: dict) -> str:
    probs = []
    for band in ("low", "mid", "high"):
        # stored under p_BREAK by bucket_rates_for
        value = rates[band].get("p")
        if value is None:
            return "insufficient"
        probs.append(value)
    low, mid, high = probs
    coef = diff.get("coef")
    ci = diff.get("ci95")
    near = coef is not None and abs(coef) < K.PRACTICAL_SCALE and ci is not None and ci[0] <= 0 <= ci[1]
    if near:
        return "near_zero"
    monotonic = (low <= mid <= high) or (low >= mid >= high)
    if monotonic and low != high:
        return "monotonic"
    if mid < min(low, high) or mid > max(low, high):
        return "u_shape"
    return "other"


def bucket_rates_for(rows: list[dict], scales: dict, feature: str, endpoint: str) -> dict:
    q33 = scales[feature]["q33"]
    q66 = scales[feature]["q66"]
    bags = {name: {"n": 0, "hits": 0, "p": None} for name in ("low", "mid", "high")}
    for row in rows:
        band = band_of(row.get(feature), q33, q66)
        if band is None:
            continue
        bags[band]["n"] += 1
        if row["outcome"] == endpoint:
            bags[band]["hits"] += 1
    for bag in bags.values():
        if bag["n"]:
            bag["p"] = bag["hits"] / bag["n"]
    return bags
