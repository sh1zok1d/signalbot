"""Stacked linear probability model for the level-specific increment.

β_pseudo is the slope at the rotated price. Δ = β_real − β_pseudo is the coefficient
on feature × real. Scales are frozen from the real predictors and are not refit on Y,
inside a bootstrap, or on a slice. The 70% family-share cap from the approach unit is
not used.
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


def freeze_scales(rows: list[dict], names: list[str], coding: dict) -> dict:
    out = {"n": len(rows)}
    for name in names:
        vals = np.array([math.nan if row.get(name) is None else float(row[name]) for row in rows], dtype=float)
        binary = coding.get(name, {}).get("coding") == "binary"
        mean, sd = _moments(vals)
        finite = vals[np.isfinite(vals)]
        if binary or finite.size < 3:
            q_lo = q_hi = math.nan
        else:
            q_lo, q_hi = (float(v) for v in np.quantile(finite, [1.0 / 3.0, 2.0 / 3.0]))
        out[name] = {"mean": mean, "sd": sd, "q33": q_lo, "q66": q_hi, "binary": binary}
    return out


def _z(value, scale: dict) -> float:
    if value is None or not math.isfinite(float(value)):
        return math.nan
    if scale.get("binary"):
        return float(value)
    mean, sd = scale.get("mean"), scale.get("sd")
    if mean is None or sd is None or not math.isfinite(mean) or not math.isfinite(sd) or sd <= 0:
        return math.nan
    return (float(value) - float(mean)) / float(sd)


def band_of(value, q33: float, q66: float) -> Optional[str]:
    if value is None or not math.isfinite(float(value)) or not math.isfinite(q33) or not math.isfinite(q66):
        return None
    if float(value) <= q33:
        return "low"
    if float(value) > q66:
        return "high"
    return "mid"


def columns_for(feature: str, coding: dict, retained: list[str], *, spec: str = "full",
                drop_year: Optional[int] = None, drop_family: Optional[str] = None,
                approach: bool = False) -> list[str]:
    cols = ["intercept", "feature_x", "real", "feature_x_real", "touch2", "touch3",
            "fam_week", "fam_month", "support", "vol_mid", "vol_high"]
    if feature != K.AGE_NUISANCE:
        cols.append("age_z")
    if feature == "zone_span" and "confluence" in retained and feature != "confluence":
        cols.append("confluence_z")
    cols.extend(["y2021", "y2022", "y2023", "y2024"])
    if approach:
        cols.extend(f"ap_{name}" for name in K.APPROACH_FEATURES)
    if spec == "no_touch":
        cols.remove("touch2")
        cols.remove("touch3")
    elif spec == "year":
        for name in ("y2021", "y2022", "y2023", "y2024"):
            cols.remove(name)
    elif spec == "family":
        cols.remove("fam_week")
        cols.remove("fam_month")
    elif spec == "side":
        cols.remove("support")
    elif spec == "touch":
        cols.remove("touch2")
        cols.remove("touch3")
    elif spec == "loyo":
        if drop_year is None:
            raise ValueError("loyo needs drop_year")
        drop = {"y2021"} if int(drop_year) == 2020 else {f"y{int(drop_year)}"}
        cols = [c for c in cols if c not in drop]
    elif spec == "lofo":
        if drop_family == "DAY":
            cols.remove("fam_week")
        elif drop_family == "WEEK":
            cols.remove("fam_week")
        elif drop_family == "MONTH":
            cols.remove("fam_month")
        else:
            raise ValueError("lofo needs a family")
    elif spec != "full":
        raise ValueError(spec)
    if "feature_x_real" not in cols:
        raise RuntimeError("the level-specific increment must stay in the model")
    return cols


def _value(row: dict, column: str, feature: str, scales: dict) -> float:
    if column == "intercept":
        return 1.0
    if column == "feature_x":
        return _z(row.get(feature), scales[feature])
    if column == "real":
        return float(row["real"])
    if column == "feature_x_real":
        return _z(row.get(feature), scales[feature]) * float(row["real"])
    if column == "age_z":
        return _z(row.get("age"), scales["age"])
    if column == "confluence_z":
        return _z(row.get("confluence"), scales["confluence"])
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
    if column.startswith("ap_"):
        name = column[3:]
        return _z(row.get(name), scales[name])
    raise ValueError(column)


def _design(rows: list[dict], scales: dict, columns: list[str], feature: str):
    xs, kept, clusters = [], [], []
    for row in rows:
        values = [_value(row, column, feature, scales) for column in columns]
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


def _fit(x: np.ndarray, y: np.ndarray, columns: list[str]) -> Optional[dict]:
    if x.shape[0] <= x.shape[1]:
        return None
    for col in range(1, x.shape[1]):
        if np.unique(x[:, col]).size < 2:
            return None
    beta, _, rank, _ = np.linalg.lstsq(x, y, rcond=None)
    if int(rank) < x.shape[1] or not np.all(np.isfinite(beta)):
        return None
    loc = {name: i for i, name in enumerate(columns)}
    pseudo = float(beta[loc["feature_x"]])
    delta = float(beta[loc["feature_x_real"]])
    return {"beta_pseudo": pseudo, "delta": delta, "beta_real": pseudo + delta}


def _endpoint(rows: list[dict], endpoint: str) -> np.ndarray:
    return np.asarray([1.0 if row["outcome"] == endpoint else 0.0 for row in rows], dtype=float)


def _bootstrap(x, y, cluster, n_clusters: int, columns: list[str], draws: int, seed: int):
    point = _fit(x, y, columns)
    rng = np.random.default_rng(seed)
    membership = [np.flatnonzero(cluster == c) for c in range(n_clusters)]
    draw = rng.integers(0, n_clusters, size=(draws, n_clusters))
    acc = {key: np.full(draws, np.nan) for key in ("delta", "beta_real", "beta_pseudo")}
    for b in range(draws):
        counts = np.bincount(draw[b], minlength=n_clusters)
        parts = [np.repeat(membership[c], int(counts[c])) for c in range(n_clusters) if counts[c]]
        if not parts:
            continue
        idx = np.concatenate(parts)
        got = _fit(x[idx], y[idx], columns)
        if got is None:
            continue
        for key in acc:
            acc[key][b] = got[key]
    out = {}
    valid = 0
    for key, series in acc.items():
        ok = np.isfinite(series)
        valid = int(ok.sum())
        ci = None
        se = None
        if valid >= 2:
            se = float(series[ok].std(ddof=1))
        if valid >= K.BOOT_MIN_VALID_FRAC * draws and valid >= 2:
            lo, hi = np.quantile(series[ok], [K.CI_ALPHA / 2.0, 1.0 - K.CI_ALPHA / 2.0])
            ci = (float(lo), float(hi))
        out[key] = {"point": None if point is None else point[key], "ci": ci, "se": se}
    return out, valid, n_clusters, point


def wald_p(coef: Optional[float], se: Optional[float]) -> Optional[float]:
    if coef is None or se is None or not math.isfinite(coef) or not math.isfinite(se):
        return None
    if se <= 0:
        return 1.0 if coef == 0 else 0.0
    return float(math.erfc(abs(coef / se) / math.sqrt(2.0)))


def bh_adjust(pvalues: list[Optional[float]]) -> list[Optional[float]]:
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


def _empty(feature: str, endpoint: str, spec: str) -> dict:
    return {
        "feature": feature, "endpoint": endpoint, "spec": spec,
        "delta": None, "beta_real": None, "beta_pseudo": None,
        "delta_ci95": None, "beta_real_ci95": None, "beta_pseudo_ci95": None,
        "delta_se": None, "p": None, "bootstrap_valid": 0,
        "n": 0, "n_real": 0, "n_pseudo": 0, "clusters": 0,
    }


def _pack(feature, endpoint, spec, point, ci_map, se, valid, n, n_real, n_pseudo, clusters) -> dict:
    cell = _empty(feature, endpoint, spec)
    cell.update({
        "n": n, "n_real": n_real, "n_pseudo": n_pseudo, "clusters": clusters,
        "bootstrap_valid": valid,
    })
    if point is None:
        return cell
    cell["delta"] = point["delta"]
    cell["beta_real"] = point["beta_real"]
    cell["beta_pseudo"] = point["beta_pseudo"]
    if ci_map:
        cell["delta_ci95"] = None if ci_map["delta"]["ci"] is None else list(ci_map["delta"]["ci"])
        cell["beta_real_ci95"] = None if ci_map["beta_real"]["ci"] is None else list(ci_map["beta_real"]["ci"])
        cell["beta_pseudo_ci95"] = None if ci_map["beta_pseudo"]["ci"] is None else list(ci_map["beta_pseudo"]["ci"])
        cell["delta_se"] = ci_map["delta"]["se"]
        cell["p"] = wald_p(point["delta"], ci_map["delta"]["se"])
    return cell


def lpm(rows: list[dict], scales: dict, feature: str, endpoint: str, coding: dict, retained: list[str],
        *, spec: str = "full", drop_year: Optional[int] = None, drop_family: Optional[str] = None,
        draws: int = 0, seed: int = K.BOOT_SEED, approach: bool = False,
        extra_scales: Optional[dict] = None) -> dict:
    scales_use = dict(scales)
    if extra_scales:
        scales_use.update(extra_scales)
    columns = columns_for(
        feature, coding, retained, spec=spec, drop_year=drop_year, drop_family=drop_family, approach=approach)
    # Approach sensitivity appends frozen columns after the structural block. They are not
    # part of the primary family; the caller passes them only for that sensitivity.
    built = _design(rows, scales_use, columns, feature)
    if built is None:
        return _empty(feature, endpoint, spec)
    x, kept, cluster, n_clusters = built
    y = _endpoint(kept, endpoint)
    n_real = int(sum(1 for row in kept if row["real"] == 1.0))
    n_pseudo = int(len(kept) - n_real)
    if draws <= 0:
        point = _fit(x, y, columns)
        return _pack(feature, endpoint, spec, point, None, None, 0, int(x.shape[0]), n_real, n_pseudo, n_clusters)
    ci_map, valid, n_clusters, point = _bootstrap(x, y, cluster, n_clusters, columns, draws, seed)
    return _pack(feature, endpoint, spec, point, ci_map, None, valid, int(x.shape[0]), n_real, n_pseudo, n_clusters)


def _shape_bootstrap(rows: list[dict], feature: str, endpoint: str, scale: dict,
                     draws: int, seed: int) -> np.ndarray:
    """Cluster bootstrap of the crude real−pseudo contrast. A draw with an empty arm is NaN."""
    binary = bool(scale.get("binary"))
    y = np.asarray([1.0 if row["outcome"] == endpoint else 0.0 for row in rows], dtype=float)
    real = np.asarray([row["real"] == 1.0 for row in rows])
    if binary:
        values = np.asarray([float(row[feature]) for row in rows], dtype=float)
        high_arm = values == 1.0
        low_arm = values == 0.0
    else:
        bands = np.asarray([
            band_of(row.get(feature), scale["q33"], scale["q66"]) for row in rows
        ])
        high_arm = bands == "high"
        low_arm = bands == "low"
    clusters = [row["cluster"] for row in rows]
    keys = sorted(set(clusters))
    code = {key: i for i, key in enumerate(keys)}
    cluster = np.asarray([code[c] for c in clusters], dtype=int)
    n_clusters = len(keys)
    rng = np.random.default_rng(seed)
    draw = rng.integers(0, n_clusters, size=(draws, n_clusters))
    flat = draw + (np.arange(draws, dtype=np.int64)[:, None] * n_clusters)
    counts = np.bincount(flat.ravel(), minlength=draws * n_clusters).reshape(draws, n_clusters)
    weight = counts[:, cluster]

    def _rate(mask: np.ndarray) -> np.ndarray:
        den = weight[:, mask].sum(axis=1)
        num = (weight[:, mask] * y[mask]).sum(axis=1)
        out = np.full(draws, np.nan)
        ok = den > 0
        out[ok] = num[ok] / den[ok]
        return out

    real_high = _rate(real & high_arm)
    real_low = _rate(real & low_arm)
    pseudo_high = _rate(~real & high_arm)
    pseudo_low = _rate(~real & low_arm)
    return (real_high - real_low) - (pseudo_high - pseudo_low)


def shape_contrast(rows: list[dict], scales: dict, feature: str, endpoint: str, *,
                   draws: int = 0, seed: int = K.BOOT_SEED) -> dict:
    """Crude real-minus-pseudo contrast. Tertile high−low for a continuous feature, the
    binary contrast itself when the feature is 0/1. Edges are the frozen real quantiles.
    """
    scale = scales[feature]
    binary = bool(scale.get("binary"))

    def _diff(sample: list[dict]) -> Optional[float]:
        if binary:
            return _binary_gap(sample, feature, endpoint)
        return _tertile_gap(sample, feature, endpoint, scale["q33"], scale["q66"])

    point = _diff(rows)
    cell = {
        "feature": feature, "endpoint": endpoint, "spec": "shape", "binary": binary,
        "coef": point, "ci95": None, "n": len(rows), "bootstrap_valid": 0,
        "bands": band_table(rows, feature, endpoint, scale),
    }
    if draws <= 0 or point is None:
        return cell
    # Cluster bootstrap of the crude contrast. Weights equal row repetition, so the rate
    # is the same statistic as rebuilding the sample. Same seed family as the primary model.
    acc = _shape_bootstrap(rows, feature, endpoint, scale, draws, seed)
    ok = np.isfinite(acc)
    valid = int(ok.sum())
    cell["bootstrap_valid"] = valid
    if valid >= K.BOOT_MIN_VALID_FRAC * draws and valid >= 2:
        lo, hi = np.quantile(acc[ok], [K.CI_ALPHA / 2.0, 1.0 - K.CI_ALPHA / 2.0])
        cell["ci95"] = [float(lo), float(hi)]
    return cell


def _rate(rows: list[dict], endpoint: str) -> Optional[float]:
    if not rows:
        return None
    return float(sum(1 for row in rows if row["outcome"] == endpoint) / len(rows))


def _binary_gap(rows: list[dict], feature: str, endpoint: str) -> Optional[float]:
    def arm(real: float, level: float) -> Optional[float]:
        group = [row for row in rows if row["real"] == real and float(row[feature]) == level]
        return _rate(group, endpoint)

    gaps = []
    for level_real in (1.0, 0.0):
        hi = arm(level_real, 1.0)
        lo = arm(level_real, 0.0)
        if hi is None or lo is None:
            return None
        gaps.append(hi - lo)
    return gaps[0] - gaps[1]


def _tertile_gap(rows: list[dict], feature: str, endpoint: str, q33: float, q66: float) -> Optional[float]:
    diffs = []
    for band in ("high", "low"):
        real = _rate([row for row in rows if row["real"] == 1.0 and band_of(row.get(feature), q33, q66) == band], endpoint)
        pseudo = _rate([row for row in rows if row["real"] == 0.0 and band_of(row.get(feature), q33, q66) == band], endpoint)
        if real is None or pseudo is None:
            return None
        diffs.append(real - pseudo)
    return diffs[0] - diffs[1]


def band_table(rows: list[dict], feature: str, endpoint: str, scale: dict) -> dict:
    q33, q66 = scale.get("q33"), scale.get("q66")
    if scale.get("binary"):
        bands = ("singleton", "multi")
    else:
        bands = ("low", "mid", "high")
    out = {}
    for band in bands:
        def pick(real, band=band):
            chosen = []
            for row in rows:
                if row["real"] != real:
                    continue
                if scale.get("binary"):
                    flag = "multi" if float(row[feature]) >= 1.0 else "singleton"
                    if flag == band:
                        chosen.append(row)
                elif band_of(row.get(feature), q33, q66) == band:
                    chosen.append(row)
            return chosen
        real_rows = pick(1.0)
        pseudo_rows = pick(0.0)
        real_p = _rate(real_rows, endpoint)
        pseudo_p = _rate(pseudo_rows, endpoint)
        diff = None if real_p is None or pseudo_p is None else real_p - pseudo_p
        out[band] = {
            "real_p": real_p, "real_n": len(real_rows),
            "pseudo_p": pseudo_p, "pseudo_n": len(pseudo_rows),
            "diff": diff,
        }
    return out


def shape_label(bands: dict, contrast: dict) -> str:
    if contrast.get("binary"):
        return "binary_contrast"
    order = ("low", "mid", "high")
    diffs = []
    for band in order:
        value = (bands.get(band) or {}).get("diff")
        if value is None:
            return "insufficient"
        diffs.append(value)
    low, mid, high = diffs
    coef = contrast.get("coef")
    ci = contrast.get("ci95")
    near = coef is not None and abs(coef) < K.PRACTICAL_SCALE and ci is not None and ci[0] <= 0 <= ci[1]
    if near:
        return "near_zero"
    if (low <= mid <= high or low >= mid >= high) and low != high:
        return "monotonic"
    if mid < min(low, high) or mid > max(low, high):
        return "u_shape"
    return "other"
