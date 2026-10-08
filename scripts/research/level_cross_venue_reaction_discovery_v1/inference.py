"""Linear probability model. END_POSITION_X is in every primary specification."""

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


def column(rows: list[dict], name: str) -> np.ndarray:
    return np.asarray([row.get(name, math.nan) for row in rows], dtype=float)


def freeze_scales(rows: list[dict]) -> dict:
    names = ("END_POSITION_X", "disp", *K.FEATURES)
    out = {"n": len(rows)}
    for name in names:
        mean, sd = _moments(column(rows, name))
        out[name] = {"mean": mean, "sd": sd, "n": int(np.isfinite(column(rows, name)).sum())}
    return out


def scale_hex(scale: dict) -> dict:
    def one(value) -> Optional[str]:
        if value is None or not math.isfinite(float(value)):
            return None
        return float(value).hex()
    return {key: one(scale[key]) for key in ("mean", "sd")}


def _z(value, scale: dict) -> float:
    if value is None or not math.isfinite(float(value)):
        return math.nan
    mean, sd = scale.get("mean"), scale.get("sd")
    if mean is None or sd is None or not math.isfinite(mean) or not math.isfinite(sd) or sd <= 0.0:
        return math.nan
    return (float(value) - float(mean)) / float(sd)


def epoch_dummies(rows: list[dict]) -> list[str]:
    present = {row["epoch"] for row in rows}
    ordered = [name for name in K.EPOCHS if name in present]
    if len(ordered) <= 1:
        return []
    return [f"ep_{name}" for name in ordered[1:]]


def columns_for(rows: list[dict], *, feature: bool, family: bool = True, side: bool = True,
                epoch: bool = True, vol: bool = True, clock: bool = True,
                stacked: bool = False) -> list[str]:
    cols = ["intercept", "endpos_z"]
    if feature:
        cols.append("feature_z")
    if stacked:
        cols.extend(["real", "feature_x_real"])
    cols.append("disp_z")
    if family:
        cols.extend(K.FAMILY_DUMMIES)
    if side:
        cols.append("support")
    if vol:
        cols.extend(K.VOL_DUMMIES)
    if epoch:
        cols.extend(epoch_dummies(rows))
    if clock:
        cols.extend(K.TIME_DUMMIES)
    return cols


def _entry(row: dict, column_name: str, feature: Optional[str], scales: dict) -> float:
    if column_name == "intercept":
        return 1.0
    if column_name == "endpos_z":
        return _z(row.get("END_POSITION_X"), scales["END_POSITION_X"])
    if column_name == "feature_z":
        return _z(row.get(feature), scales[feature])
    if column_name == "real":
        return float(row["real"])
    if column_name == "feature_x_real":
        return _z(row.get(feature), scales[feature]) * float(row["real"])
    if column_name == "disp_z":
        return _z(row.get("disp"), scales["disp"])
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
    if column_name == "tb1":
        return 1.0 if int(row["time_block"]) == 1 else 0.0
    if column_name == "tb2":
        return 1.0 if int(row["time_block"]) == 2 else 0.0
    if column_name == "tb3":
        return 1.0 if int(row["time_block"]) == 3 else 0.0
    raise ValueError(column_name)


def _design(rows: list[dict], feature: Optional[str], scales: dict, columns: list[str]):
    xs, ys, clusters = [], [], []
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


def _prune(x: np.ndarray, columns: list[str]) -> tuple[np.ndarray, list[str]]:
    protected = {"endpos_z", "feature_z", "real", "feature_x_real"}
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


def _targets(beta: np.ndarray, columns: list[str], *, feature: bool, stacked: bool) -> dict:
    loc = {name: i for i, name in enumerate(columns)}
    endpos = float(beta[loc["endpos_z"]])
    if stacked:
        pseudo = float(beta[loc["feature_z"]])
        delta = float(beta[loc["feature_x_real"]])
        return {
            "coef": delta, "beta_pseudo": pseudo, "beta_real": pseudo + delta,
            "delta": delta, "endpos": endpos,
        }
    coef = float(beta[loc["feature_z"]]) if feature else endpos
    return {"coef": coef, "beta_pseudo": None, "beta_real": None, "delta": None, "endpos": endpos}


def _bootstrap(x, y, cluster, n_clusters, columns, *, feature: bool, stacked: bool,
               draws: int, seed: int):
    point_beta = _fit(x, y)
    point = None if point_beta is None else _targets(point_beta, columns, feature=feature, stacked=stacked)
    rng = np.random.default_rng(seed)
    membership = [np.flatnonzero(cluster == c) for c in range(n_clusters)]
    draw = rng.integers(0, n_clusters, size=(draws, n_clusters))
    keys = ("coef", "beta_real", "beta_pseudo", "delta", "endpos")
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
        targets = _targets(got, columns, feature=feature, stacked=stacked)
        for key in keys:
            value = targets[key]
            if value is not None:
                acc[key][b] = value
    packed = {}
    coef_ok = np.isfinite(acc["coef"])
    for key, series in acc.items():
        ok = np.isfinite(series)
        valid = int(ok.sum())
        se = float(series[ok].std(ddof=1)) if valid >= 2 else None
        ci = None
        if valid >= K.BOOT_MIN_VALID_FRAC * draws and valid >= 2:
            lo, hi = np.quantile(series[ok], [K.CI_ALPHA / 2.0, 1.0 - K.CI_ALPHA / 2.0])
            ci = (float(lo), float(hi))
        packed[key] = {
            "point": None if point is None else point[key],
            "ci": ci,
            "se": se,
            "valid": valid,
        }
    return packed, int(coef_ok.sum()), point


def _brier(x: np.ndarray, y: np.ndarray, beta: Optional[np.ndarray]) -> Optional[float]:
    if beta is None:
        return None
    pred = np.clip(x @ beta, 0.0, 1.0)
    return float(np.mean((y - pred) ** 2))


def fit_rows(rows: list[dict], feature: Optional[str], scales: dict, *, stacked: bool = False,
             family: bool = True, side: bool = True, epoch: bool = True,
             draws: int = 0, seed: int = K.BOOT_SEED) -> dict:
    use_feature = feature is not None
    columns = columns_for(
        rows, feature=use_feature, family=family, side=side, epoch=epoch, stacked=stacked,
    )
    if "endpos_z" not in columns:
        raise RuntimeError("END_POSITION_X left the specification")
    cell = {
        "feature": feature, "columns": columns, "n": 0, "clusters": 0,
        "coef": None, "ci95": None, "se": None, "p": None,
        "endpos_coef": None, "endpos_ci95": None,
        "beta_real": None, "beta_pseudo": None, "delta": None,
        "beta_real_ci95": None, "beta_pseudo_ci95": None, "delta_ci95": None,
        "bootstrap_valid": 0, "stacked": stacked,
        "brier": None, "includes_end_position": True,
    }
    built = _design(rows, feature, scales, columns)
    if built is None:
        return cell
    x, y, cluster, n_clusters = built
    x, columns = _prune(x, columns)
    if "endpos_z" not in columns:
        raise RuntimeError("END_POSITION_X was pruned")
    cell["columns"] = columns
    cell["n"] = int(x.shape[0])
    cell["clusters"] = int(n_clusters)
    if draws <= 0:
        beta = _fit(x, y)
        if beta is None:
            return cell
        targets = _targets(beta, columns, feature=use_feature, stacked=stacked)
        cell["coef"] = targets["coef"]
        cell["endpos_coef"] = targets["endpos"]
        cell["beta_real"] = targets["beta_real"]
        cell["beta_pseudo"] = targets["beta_pseudo"]
        cell["delta"] = targets["delta"]
        cell["brier"] = _brier(x, y, beta)
        return cell
    packed, valid, point = _bootstrap(
        x, y, cluster, n_clusters, columns, feature=use_feature, stacked=stacked,
        draws=draws, seed=seed,
    )
    cell["bootstrap_valid"] = valid
    cell["coef"] = packed["coef"]["point"]
    cell["ci95"] = packed["coef"]["ci"]
    cell["se"] = packed["coef"]["se"]
    cell["p"] = wald_p(packed["coef"]["point"], packed["coef"]["se"])
    cell["endpos_coef"] = packed["endpos"]["point"]
    cell["endpos_ci95"] = packed["endpos"]["ci"]
    cell["beta_real"] = packed["beta_real"]["point"]
    cell["beta_pseudo"] = packed["beta_pseudo"]["point"]
    cell["delta"] = packed["delta"]["point"]
    cell["beta_real_ci95"] = packed["beta_real"]["ci"]
    cell["beta_pseudo_ci95"] = packed["beta_pseudo"]["ci"]
    cell["delta_ci95"] = packed["delta"]["ci"]
    beta = _fit(x, y)
    cell["brier"] = _brier(x, y, beta)
    if point is None:
        cell["coef"] = None
    return cell


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


def pearson(rows: list[dict], left: str, right: str) -> Optional[float]:
    a = column(rows, left)
    b = column(rows, right)
    ok = np.isfinite(a) & np.isfinite(b)
    if int(ok.sum()) < 3:
        return None
    aa, bb = a[ok], b[ok]
    if float(aa.std(ddof=0)) == 0.0 or float(bb.std(ddof=0)) == 0.0:
        return None
    return float(np.corrcoef(aa, bb)[0, 1])


def drop_redundant(rows: list[dict], names: tuple[str, ...] = K.FEATURES) -> dict:
    """Drop the later feature of any pair with |rho| >= 0.90. Outcome-blind."""
    rho = {}
    for i, left in enumerate(names):
        for right in names[i + 1:]:
            rho[f"{left}__{right}"] = pearson(rows, left, right)
    dropped = []
    retained = []
    for name in names:
        redundant = False
        for kept in retained:
            value = rho.get(f"{kept}__{name}")
            if value is None:
                value = rho.get(f"{name}__{kept}")
            if value is not None and abs(float(value)) >= K.REDUNDANCY_ABS_RHO:
                redundant = True
                dropped.append({"feature": name, "redundant_with": kept, "rho": value})
                break
        if not redundant:
            retained.append(name)
    return {"retained": retained, "dropped": dropped, "rho": rho}


def tertile_cuts(rows: list[dict], name: str) -> dict:
    values = column(rows, name)
    finite = values[np.isfinite(values)]
    if finite.size < 3:
        return {"q33": None, "q67": None}
    q33, q67 = np.quantile(finite, [1.0 / 3.0, 2.0 / 3.0])
    return {"q33": float(q33), "q67": float(q67)}


def rough_mde(n_unresolved: int) -> Optional[float]:
    n_eff = n_unresolved * K.PLANNING_RESOLVE_FRACTION / K.INFO_DEFF
    if n_eff <= 0:
        return None
    return float(K.PLANNING_Z * math.sqrt(0.25 / n_eff))
