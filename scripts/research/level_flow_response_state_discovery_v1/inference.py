"""State-versus-rest linear probability models. The state labels are inputs."""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from . import constants as K


def _moments(values: np.ndarray) -> tuple[float, float]:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return (math.nan, math.nan)
    return float(finite.mean()), float(finite.std(ddof=0))


def freeze_activity(rows: list[dict]) -> dict:
    values = np.asarray([
        math.nan if row.get("rel_volume") is None else float(row["rel_volume"]) for row in rows
    ], dtype=float)
    mean, sd = _moments(values)
    return {"mean": mean, "sd": sd, "n": int(np.isfinite(values).sum())}


def year_dummies(rows: list[dict]) -> list[str]:
    years = sorted({int(row["year"]) for row in rows})
    if len(years) <= 1:
        return []
    return [f"y{year}" for year in years[1:]]


def columns_for(rows: list[dict], *, stacked: bool = False, family: bool = True,
                side: bool = True, year: bool = True) -> list[str]:
    cols = ["intercept", "state"]
    if stacked:
        cols.extend(["real", "state_x_real"])
    if family:
        cols.extend(K.FAMILY_DUMMIES)
    if side:
        cols.append("support")
    cols.extend(K.VOL_DUMMIES)
    if year:
        cols.extend(year_dummies(rows))
    cols.append("relvol_z")
    cols.extend(K.TIME_DUMMIES)
    return cols


def _activity(row: dict, scale: dict) -> float:
    value = row.get("rel_volume")
    if value is None or not math.isfinite(float(value)):
        return math.nan
    mean, sd = scale.get("mean"), scale.get("sd")
    if mean is None or sd is None or not math.isfinite(mean) or not math.isfinite(sd) or sd <= 0.0:
        return math.nan
    return (float(value) - float(mean)) / float(sd)


def _entry(row: dict, name: str, state_name: str, activity: dict) -> float:
    if name == "intercept":
        return 1.0
    if name == "state":
        return 1.0 if row.get("state") == state_name else 0.0
    if name == "real":
        return float(row["real"])
    if name == "state_x_real":
        indicator = 1.0 if row.get("state") == state_name else 0.0
        return indicator * float(row["real"])
    if name == "fam_week":
        return 1.0 if row["family"] == "WEEK" else 0.0
    if name == "fam_month":
        return 1.0 if row["family"] == "MONTH" else 0.0
    if name == "support":
        return float(row["support"])
    if name == "vol_mid":
        return 1.0 if int(row["vol_tercile"]) == 1 else 0.0
    if name == "vol_high":
        return 1.0 if int(row["vol_tercile"]) == 2 else 0.0
    if name.startswith("y") and name[1:].isdigit():
        return 1.0 if int(row["year"]) == int(name[1:]) else 0.0
    if name == "relvol_z":
        return _activity(row, activity)
    if name == "tb1":
        return 1.0 if int(row["time_block"]) == 1 else 0.0
    if name == "tb2":
        return 1.0 if int(row["time_block"]) == 2 else 0.0
    if name == "tb3":
        return 1.0 if int(row["time_block"]) == 3 else 0.0
    raise ValueError(name)


def _design(rows: list[dict], state_name: str, activity: dict, columns: list[str]):
    xs, ys, clusters = [], [], []
    for row in rows:
        y = row.get("y")
        if y is None or not math.isfinite(float(y)):
            continue
        values = [_entry(row, name, state_name, activity) for name in columns]
        if not all(math.isfinite(v) for v in values):
            continue
        xs.append(values)
        ys.append(float(y))
        clusters.append(row["cluster"])
    if not xs:
        return None
    keys = sorted(set(clusters))
    code = {key: i for i, key in enumerate(keys)}
    return (
        np.asarray(xs, dtype=float),
        np.asarray(ys, dtype=float),
        np.asarray([code[c] for c in clusters], dtype=np.int64),
        len(keys),
    )


def _prune(x: np.ndarray, columns: list[str]) -> tuple[np.ndarray, list[str]]:
    protected = {"state", "real", "state_x_real"}
    keep = [0]
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
        pseudo = float(beta[loc["state"]])
        delta = float(beta[loc["state_x_real"]])
        return {"coef": delta, "beta_pseudo": pseudo, "beta_real": pseudo + delta, "delta": delta}
    return {"coef": float(beta[loc["state"]]), "beta_pseudo": None, "beta_real": None, "delta": None}


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
            if value is not None and math.isfinite(value):
                acc[key][b] = value
    packed = {}
    valid_by_key = {}
    for key, series in acc.items():
        ok = np.isfinite(series)
        valid = int(ok.sum())
        valid_by_key[key] = valid
        se = float(series[ok].std(ddof=1)) if valid >= 2 else None
        ci = None
        if valid >= K.BOOT_MIN_VALID_FRAC * draws and valid >= 2:
            lo, hi = np.quantile(series[ok], [K.CI_ALPHA / 2.0, 1.0 - K.CI_ALPHA / 2.0])
            ci = (float(lo), float(hi))
        point_value = None if point is None else point[key]
        packed[key] = {"point": point_value, "ci": ci, "se": se, "valid": valid}
    return packed, valid_by_key, point


def wald_p(coef: Optional[float], se: Optional[float]) -> Optional[float]:
    if coef is None or se is None or not math.isfinite(coef) or not math.isfinite(se):
        return None
    if se <= 0.0:
        return 1.0 if coef == 0.0 else 0.0
    return float(math.erfc(abs(coef / se) / math.sqrt(2.0)))


def bh_adjust(pvalues: list[Optional[float]]) -> list[Optional[float]]:
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


def fit_rows(rows: list[dict], state_name: str, activity: dict, *, stacked: bool = False,
             family: bool = True, side: bool = True, year: bool = True,
             draws: int = 0, seed: int = K.BOOT_SEED) -> dict:
    columns = columns_for(rows, stacked=stacked, family=family, side=side, year=year)
    built = _design(rows, state_name, activity, columns)
    cell = {
        "state": state_name, "columns": columns, "n": 0, "n_state": 0, "clusters": 0,
        "coef": None, "ci95": None, "se": None, "p": None,
        "beta_real": None, "beta_pseudo": None, "delta": None,
        "beta_real_ci95": None, "beta_pseudo_ci95": None,
        "bootstrap_valid": 0, "stacked": stacked,
    }
    if built is None:
        return cell
    x, y, cluster, n_clusters = built
    x, columns = _prune(x, columns)
    cell["columns"] = columns
    cell["n"] = int(x.shape[0])
    cell["clusters"] = int(n_clusters)
    state_col = columns.index("state") if "state" in columns else None
    cell["n_state"] = int(x[:, state_col].sum()) if state_col is not None else 0
    if draws <= 0:
        beta = _fit(x, y)
        if beta is None:
            return cell
        cell.update(_targets(beta, columns, stacked))
        return cell
    packed, valid_by_key, _point = _bootstrap(x, y, cluster, n_clusters, columns, stacked, draws, seed)
    cell["bootstrap_valid"] = int(valid_by_key.get("coef", 0))
    coef = packed["coef"]
    cell["coef"] = coef["point"]
    cell["ci95"] = coef["ci"]
    cell["se"] = coef["se"]
    cell["p"] = wald_p(coef["point"], coef["se"])
    if stacked:
        cell["beta_real"] = packed["beta_real"]["point"]
        cell["beta_pseudo"] = packed["beta_pseudo"]["point"]
        cell["delta"] = packed["delta"]["point"]
        cell["beta_real_ci95"] = packed["beta_real"]["ci"]
        cell["beta_pseudo_ci95"] = packed["beta_pseudo"]["ci"]
        cell["ci95"] = packed["delta"]["ci"]
        cell["se"] = packed["delta"]["se"]
        cell["p"] = wald_p(packed["delta"]["point"], packed["delta"]["se"])
        cell["bootstrap_valid"] = int(valid_by_key.get("delta", 0))
    return cell
