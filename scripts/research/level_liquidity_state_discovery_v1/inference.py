"""Linear probability models. Scales and cuts are inputs; they are not refit on Y."""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from . import constants as K
from .cohort import column


def _moments(values: np.ndarray) -> tuple[float, float, float, float]:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return (math.nan, math.nan, math.nan, math.nan)
    mean = float(finite.mean())
    sd = float(finite.std(ddof=0)) if finite.size else math.nan
    if finite.size < 3:
        return (mean, sd, math.nan, math.nan)
    q33, q66 = (float(v) for v in np.quantile(finite, [1.0 / 3.0, 2.0 / 3.0]))
    return (mean, sd, q33, q66)


def freeze_scales(rows: list[dict], names: list[str]) -> dict:
    """Predictor moments. `names` plus the two continuous nuisance fields."""
    out = {"n": len(rows)}
    for name in list(names) + ["disp", "rel_volume"]:
        series = column(rows, name)
        mean, sd, q33, q66 = _moments(series)
        out[name] = {
            "mean": mean, "sd": sd, "q33": q33, "q66": q66,
            "n": int(np.isfinite(series).sum()),
        }
    return out


def scale_hex(scale: dict) -> dict:
    def one(value: float) -> Optional[str]:
        if value is None or not math.isfinite(float(value)):
            return None
        return float(value).hex()
    return {key: one(scale[key]) for key in ("mean", "sd", "q33", "q66")}


def _z(value, scale: dict) -> float:
    if value is None or not math.isfinite(float(value)):
        return math.nan
    mean, sd = scale.get("mean"), scale.get("sd")
    if mean is None or sd is None or not math.isfinite(mean) or not math.isfinite(sd) or sd <= 0.0:
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


def epoch_dummies(rows: list[dict]) -> list[str]:
    present = {row["epoch"] for row in rows}
    ordered = [name for name in K.EPOCHS if name in present]
    if len(ordered) <= 1:
        return []
    return [f"ep_{name}" for name in ordered[1:]]


def columns_for(rows: list[dict], *, stacked: bool = False, family: bool = True,
                side: bool = True, epoch: bool = True, vol: bool = True, clock: bool = True,
                activity: bool = True) -> list[str]:
    cols = ["intercept", "feature_z"]
    if stacked:
        cols.extend(["real", "feature_x_real"])
    if family:
        cols.extend(K.FAMILY_DUMMIES)
    if side:
        cols.append("support")
    if vol:
        cols.extend(K.VOL_DUMMIES)
    if epoch:
        cols.extend(epoch_dummies(rows))
    if activity:
        cols.extend(["disp_z", "relvol_z"])
    if clock:
        cols.extend(K.TIME_DUMMIES)
    return cols


def _entry(row: dict, column_name: str, feature: str, scales: dict) -> float:
    if column_name == "intercept":
        return 1.0
    if column_name == "feature_z":
        return _z(row.get(feature), scales[feature])
    if column_name == "real":
        return float(row["real"])
    if column_name == "feature_x_real":
        return _z(row.get(feature), scales[feature]) * float(row["real"])
    if column_name == "fam_week":
        return 1.0 if row["family"] == "WEEK" else 0.0
    if column_name == "fam_month":
        return 1.0 if row["family"] == "MONTH" else 0.0
    if column_name == "support":
        return float(row["support"])
    if column_name == "vol_mid":
        return 1.0 if int(row["vol_tercile"]) == 1 else 0.0
    if column_name == "vol_high":
        return 1.0 if int(row["vol_tercile"]) == 2 else 0.0
    if column_name.startswith("ep_"):
        return 1.0 if row["epoch"] == column_name[3:] else 0.0
    if column_name == "disp_z":
        return _z(row.get("disp"), scales["disp"])
    if column_name == "relvol_z":
        return _z(row.get("rel_volume"), scales["rel_volume"])
    if column_name == "tb1":
        return 1.0 if int(row["time_block"]) == 1 else 0.0
    if column_name == "tb2":
        return 1.0 if int(row["time_block"]) == 2 else 0.0
    if column_name == "tb3":
        return 1.0 if int(row["time_block"]) == 3 else 0.0
    raise ValueError(column_name)


def _design(rows: list[dict], feature: str, scales: dict, columns: list[str]):
    xs = []
    ys = []
    clusters = []
    for row in rows:
        y = row.get("y")
        if y is None or not math.isfinite(float(y)):
            continue
        values = [_entry(row, name, feature, scales) for name in columns]
        if not all(math.isfinite(v) for v in values):
            continue
        xs.append(values)
        ys.append(float(y))
        clusters.append(row["cluster"])
    if not xs:
        return None
    keys = sorted(set(clusters))
    code = {key: i for i, key in enumerate(keys)}
    x = np.asarray(xs, dtype=float)
    y = np.asarray(ys, dtype=float)
    cluster = np.asarray([code[c] for c in clusters], dtype=np.int64)
    return x, y, cluster, len(keys)


def _prune_constant_nuisance(x: np.ndarray, columns: list[str]) -> tuple[np.ndarray, list[str]]:
    keep = [0]
    protected = {"feature_z", "real", "feature_x_real"}
    for i in range(1, len(columns)):
        if columns[i] in protected or float(x[:, i].std()) > 0.0:
            keep.append(i)
    idx = np.asarray(keep, dtype=int)
    return x[:, idx], [columns[i] for i in keep]


def _fit(x: np.ndarray, y: np.ndarray) -> Optional[np.ndarray]:
    if x.shape[0] <= x.shape[1]:
        return None
    if x.shape[1] > 1 and np.any(x[:, 1:].std(axis=0) <= 0.0):
        return None
    xtx = x.T @ x
    cond = float(np.linalg.cond(xtx))
    if not np.isfinite(cond) or cond > 1e8:
        return None
    try:
        beta = np.linalg.solve(xtx, x.T @ y)
    except np.linalg.LinAlgError:
        return None
    if not np.all(np.isfinite(beta)):
        return None
    return beta


def _targets(beta: np.ndarray, columns: list[str], stacked: bool) -> dict:
    loc = {name: i for i, name in enumerate(columns)}
    if stacked:
        pseudo = float(beta[loc["feature_z"]])
        delta = float(beta[loc["feature_x_real"]])
        return {"coef": delta, "beta_pseudo": pseudo, "beta_real": pseudo + delta, "delta": delta}
    return {"coef": float(beta[loc["feature_z"]]), "beta_pseudo": None, "beta_real": None, "delta": None}


def _bootstrap(x, y, cluster, n_clusters: int, columns: list[str], stacked: bool, draws: int, seed: int):
    point_beta = _fit(x, y)
    point = None if point_beta is None else _targets(point_beta, columns, stacked)
    rng = np.random.default_rng(seed)
    membership = [np.flatnonzero(cluster == c) for c in range(n_clusters)]
    draw = rng.integers(0, n_clusters, size=(draws, n_clusters))
    keys = ("coef", "beta_real", "beta_pseudo", "delta")
    acc = {key: np.full(draws, np.nan) for key in keys}
    for b in range(draws):
        counts = np.bincount(draw[b], minlength=n_clusters)
        parts = [np.repeat(membership[c], int(counts[c])) for c in range(n_clusters) if counts[c]]
        if not parts:
            continue
        idx = np.concatenate(parts)
        got = _fit(x[idx], y[idx])
        if got is None:
            continue
        targets = _targets(got, columns, stacked)
        for key in keys:
            value = targets[key]
            if value is not None:
                acc[key][b] = value
    packed = {}
    coef_ok = np.isfinite(acc["coef"])
    coef_valid = int(coef_ok.sum())
    for key, series in acc.items():
        ok = np.isfinite(series)
        valid = int(ok.sum())
        se = float(series[ok].std(ddof=1)) if valid >= 2 else None
        ci = None
        if valid >= K.BOOT_MIN_VALID_FRAC * draws and valid >= 2:
            lo, hi = np.quantile(series[ok], [K.CI_ALPHA / 2.0, 1.0 - K.CI_ALPHA / 2.0])
            ci = (float(lo), float(hi))
        point_value = None if point is None else point[key]
        packed[key] = {"point": point_value, "ci": ci, "se": se, "valid": valid}
    return packed, coef_valid, point


def wald_p(coef: Optional[float], se: Optional[float]) -> Optional[float]:
    if coef is None or se is None or not math.isfinite(coef) or not math.isfinite(se):
        return None
    if se <= 0.0:
        return 1.0 if coef == 0.0 else 0.0
    return float(math.erfc(abs(coef / se) / math.sqrt(2.0)))


def bh_adjust(pvalues: list[Optional[float]]) -> list[Optional[float]]:
    """Benjamini-Hochberg. A missing p-value is treated as 1."""
    m = len(pvalues)
    if m == 0:
        return []
    usable = [1.0 if p is None or not math.isfinite(p) else float(p) for p in pvalues]
    order = sorted(range(m), key=lambda i: (usable[i], i))
    adj = [None] * m
    running = 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        running = min(running, usable[i] * m / rank)
        adj[i] = running
    return adj


def fit_rows(rows: list[dict], feature: str, scales: dict, *, stacked: bool = False,
             family: bool = True, side: bool = True, epoch: bool = True,
             draws: int = 0, seed: int = K.BOOT_SEED) -> dict:
    columns = columns_for(rows, stacked=stacked, family=family, side=side, epoch=epoch)
    built = _design(rows, feature, scales, columns)
    cell = {
        "feature": feature, "columns": columns, "n": 0, "clusters": 0,
        "coef": None, "ci95": None, "se": None, "p": None,
        "beta_real": None, "beta_pseudo": None, "delta": None,
        "beta_real_ci95": None, "beta_pseudo_ci95": None,
        "bootstrap_valid": 0, "stacked": stacked,
    }
    if built is None:
        return cell
    x, y, cluster, n_clusters = built
    x, columns = _prune_constant_nuisance(x, columns)
    cell["columns"] = columns
    cell["n"] = int(x.shape[0])
    cell["clusters"] = int(n_clusters)
    if draws <= 0:
        beta = _fit(x, y)
        if beta is None:
            return cell
        targets = _targets(beta, columns, stacked)
        cell.update({key: targets[key] for key in ("coef", "beta_real", "beta_pseudo", "delta")})
        return cell
    packed, valid, _point = _bootstrap(x, y, cluster, n_clusters, columns, stacked, draws, seed)
    cell["bootstrap_valid"] = valid
    cell["coef"] = packed["coef"]["point"]
    cell["ci95"] = None if packed["coef"]["ci"] is None else list(packed["coef"]["ci"])
    cell["se"] = packed["coef"]["se"]
    cell["p"] = wald_p(packed["coef"]["point"], packed["coef"]["se"])
    cell["beta_real"] = packed["beta_real"]["point"]
    cell["beta_pseudo"] = packed["beta_pseudo"]["point"]
    cell["delta"] = packed["delta"]["point"]
    cell["beta_real_ci95"] = None if packed["beta_real"]["ci"] is None else list(packed["beta_real"]["ci"])
    cell["beta_pseudo_ci95"] = None if packed["beta_pseudo"]["ci"] is None else list(packed["beta_pseudo"]["ci"])
    return cell


def shape_table(rows: list[dict], feature: str, scale: dict) -> dict:
    q33, q66 = scale["q33"], scale["q66"]
    bags = {band: [] for band in ("low", "mid", "high")}
    for row in rows:
        band = band_of(row.get(feature), q33, q66)
        y = row.get("y")
        if band is None or y is None or not math.isfinite(float(y)):
            continue
        bags[band].append(float(y))
    out = {}
    for band, values in bags.items():
        out[band] = {
            "n": len(values),
            "rate": None if not values else float(sum(values) / len(values)),
        }
    return out


def shape_label(table: dict) -> str:
    rates = []
    for band in ("low", "mid", "high"):
        rate = table.get(band, {}).get("rate")
        if rate is None:
            return "insufficient"
        rates.append(rate)
    low, mid, high = rates
    if low == mid == high:
        return "flat"
    if low <= mid <= high or low >= mid >= high:
        return "monotonic"
    if mid < min(low, high) or mid > max(low, high):
        return "u_shape"
    return "other"


def pearson(a: np.ndarray, b: np.ndarray) -> float:
    mask = np.isfinite(a) & np.isfinite(b)
    if int(mask.sum()) < 3:
        return math.nan
    x, y = a[mask], b[mask]
    if float(x.std()) == 0.0 or float(y.std()) == 0.0:
        return math.nan
    return float(np.corrcoef(x, y)[0, 1])


def redundancy(rows: list[dict], names: tuple[str, ...] = K.RAW_FEATURES) -> dict:
    """Drop a later feature when |rho| >= 0.90 with an earlier one, or when it has no variation."""
    kept: list[str] = []
    dropped: list[dict] = []
    cols = {name: column(rows, name) for name in names}
    rho = {}
    for i, left in enumerate(names):
        for right in names[i + 1:]:
            rho[f"{left}__{right}"] = pearson(cols[left], cols[right])
    for name in names:
        finite = cols[name][np.isfinite(cols[name])]
        if finite.size < 3 or float(np.std(finite)) == 0.0:
            dropped.append({"feature": name, "reason": "degenerate", "rho": None, "kept": None})
            continue
        hit = None
        hit_rho = None
        for prev in kept:
            value = pearson(cols[name], cols[prev])
            if math.isfinite(value) and abs(value) >= K.REDUNDANCY_RHO:
                hit = prev
                hit_rho = value
                break
        if hit is not None:
            dropped.append({"feature": name, "reason": "redundancy", "rho": hit_rho, "kept": hit})
            continue
        kept.append(name)
    return {"kept": kept, "dropped": dropped, "rho": rho}
