"""Linear probability model. END_POSITION_X and CV1 are in every specification.

Matched specificity fits the same columns on the real rows and on the pseudo
rows. The bootstrap resamples source episodes, so a real row and its pseudo
row always move together. There is no stacked interaction regressor.
"""

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


def freeze_scales(rows: list[dict], names: tuple[str, ...]) -> dict:
    out = {"n": len(rows)}
    for name in ("END_POSITION_X", "disp", K.CV1_NAME, *names):
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


PROTECTED = {"endpos_z", "cv1_z", "feature_z"}


def columns_for(rows: list[dict], *, feature: bool, family: bool = True, side: bool = True,
                epoch: bool = True, vol: bool = True, clock: bool = True) -> list[str]:
    cols = ["intercept", "endpos_z", "cv1_z"]
    if feature:
        cols.append("feature_z")
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
    if column_name == "cv1_z":
        return _z(row.get(K.CV1_NAME), scales[K.CV1_NAME])
    if column_name == "feature_z":
        return _z(row.get(feature), scales[feature])
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
    return x, y, cluster, len(keys), keys


def _prune(x: np.ndarray, columns: list[str]) -> tuple[np.ndarray, list[str]]:
    keep = [0]
    for i in range(1, len(columns)):
        if columns[i] in PROTECTED or float(x[:, i].std()) > 0.0:
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


def _targets(beta: np.ndarray, columns: list[str], *, feature: bool) -> dict:
    loc = {name: i for i, name in enumerate(columns)}
    endpos = float(beta[loc["endpos_z"]])
    cv1 = float(beta[loc["cv1_z"]])
    coef = float(beta[loc["feature_z"]]) if feature else cv1
    return {"coef": coef, "endpos": endpos, "cv1": cv1}


def _ci(series: np.ndarray, draws: int) -> tuple[Optional[tuple[float, float]], Optional[float], int]:
    ok = np.isfinite(series)
    valid = int(ok.sum())
    se = float(series[ok].std(ddof=1)) if valid >= 2 else None
    ci = None
    if valid >= K.BOOT_MIN_VALID_FRAC * draws and valid >= 2:
        lo, hi = np.quantile(series[ok], [K.CI_ALPHA / 2.0, 1.0 - K.CI_ALPHA / 2.0])
        ci = (float(lo), float(hi))
    return ci, se, valid


def _bootstrap(x, y, cluster, n_clusters, columns, *, feature: bool, draws: int, seed: int):
    point_beta = _fit(x, y)
    point = None if point_beta is None else _targets(point_beta, columns, feature=feature)
    rng = np.random.default_rng(seed)
    membership = [np.flatnonzero(cluster == c) for c in range(n_clusters)]
    draw = rng.integers(0, n_clusters, size=(draws, n_clusters))
    acc = {key: np.full(draws, np.nan) for key in ("coef", "endpos", "cv1")}
    for b in range(draws):
        counts = np.bincount(draw[b], minlength=n_clusters)
        parts = [np.repeat(membership[c], int(counts[c])) for c in range(n_clusters) if counts[c]]
        if not parts:
            continue
        idx = np.concatenate(parts)
        got = _fit(x[idx], y[idx])
        if got is None:
            continue
        targets = _targets(got, columns, feature=feature)
        acc["coef"][b] = targets["coef"]
        acc["endpos"][b] = targets["endpos"]
        acc["cv1"][b] = targets["cv1"]
    packed = {}
    for key, series in acc.items():
        ci, se, valid = _ci(series, draws)
        packed[key] = {
            "point": None if point is None else point[key],
            "ci": ci,
            "se": se,
            "valid": valid,
        }
    return packed, packed["coef"]["valid"], point


def _brier(x: np.ndarray, y: np.ndarray, beta: Optional[np.ndarray]) -> Optional[float]:
    if beta is None:
        return None
    pred = np.clip(x @ beta, 0.0, 1.0)
    return float(np.mean((y - pred) ** 2))


def _require_baseline(columns: list[str]) -> None:
    if "endpos_z" not in columns or "cv1_z" not in columns:
        raise RuntimeError("END_POSITION_X or OTHER_VENUE_MEDIAN_MOVE left the specification")


def fit_rows(rows: list[dict], feature: Optional[str], scales: dict, *,
             family: bool = True, side: bool = True, epoch: bool = True,
             draws: int = 0, seed: int = K.BOOT_SEED) -> dict:
    use_feature = feature is not None
    columns = columns_for(rows, feature=use_feature, family=family, side=side, epoch=epoch)
    _require_baseline(columns)
    cell = {
        "feature": feature, "columns": columns, "n": 0, "clusters": 0,
        "coef": None, "ci95": None, "se": None, "p": None,
        "endpos_coef": None, "endpos_ci95": None,
        "cv1_coef": None, "cv1_ci95": None,
        "bootstrap_valid": 0,
        "brier": None,
        "includes_end_position": True,
        "includes_cv1": True,
    }
    built = _design(rows, feature, scales, columns)
    if built is None:
        return cell
    x, y, cluster, n_clusters, _keys = built
    x, columns = _prune(x, columns)
    _require_baseline(columns)
    cell["columns"] = columns
    cell["n"] = int(x.shape[0])
    cell["clusters"] = int(n_clusters)
    if draws <= 0:
        beta = _fit(x, y)
        if beta is None:
            return cell
        targets = _targets(beta, columns, feature=use_feature)
        cell["coef"] = targets["coef"]
        cell["endpos_coef"] = targets["endpos"]
        cell["cv1_coef"] = targets["cv1"]
        cell["brier"] = _brier(x, y, beta)
        return cell
    packed, valid, point = _bootstrap(
        x, y, cluster, n_clusters, columns, feature=use_feature, draws=draws, seed=seed,
    )
    cell["bootstrap_valid"] = valid
    cell["coef"] = packed["coef"]["point"]
    cell["ci95"] = packed["coef"]["ci"]
    cell["se"] = packed["coef"]["se"]
    cell["p"] = wald_p(packed["coef"]["point"], packed["coef"]["se"])
    cell["endpos_coef"] = packed["endpos"]["point"]
    cell["endpos_ci95"] = packed["endpos"]["ci"]
    cell["cv1_coef"] = packed["cv1"]["point"]
    cell["cv1_ci95"] = packed["cv1"]["ci"]
    beta = _fit(x, y)
    cell["brier"] = _brier(x, y, beta)
    if point is None:
        cell["coef"] = None
    return cell


def identical_columns(real_rows: list[dict], pseudo_rows: list[dict], feature: str,
                      scales: dict) -> list[str]:
    """One column list for both matched models.

    A nuisance column that does not vary inside either sample is omitted from
    both. Protected baseline and feature columns stay.
    """
    columns = columns_for(real_rows + pseudo_rows, feature=True)
    real = _design(real_rows, feature, scales, columns)
    pseudo = _design(pseudo_rows, feature, scales, columns)
    if real is None or pseudo is None:
        return columns
    xr, xp = real[0], pseudo[0]
    keep = []
    for i, name in enumerate(columns):
        if name in PROTECTED or name == "intercept":
            keep.append(name)
            continue
        if float(xr[:, i].std()) > 0.0 and float(xp[:, i].std()) > 0.0:
            keep.append(name)
    return keep


def fit_matched(pairs: list[dict], feature: str, scales: dict, *, draws: int, seed: int) -> dict:
    """Separate identical models. Delta is the difference of the two slopes."""
    real_rows = [pair["real"] for pair in pairs]
    pseudo_rows = [pair["pseudo"] for pair in pairs]
    columns = identical_columns(real_rows, pseudo_rows, feature, scales)
    _require_baseline(columns)
    if "feature_z" not in columns:
        raise RuntimeError("the spot feature left the matched specification")
    empty = {
        "n_pairs": len(pairs), "columns": columns, "status": "NOT_ESTIMATED",
        "beta_real": None, "beta_pseudo": None, "delta": None, "delta_ci95": None,
        "beta_real_ci95": None, "beta_pseudo_ci95": None, "bootstrap_valid": 0,
    }
    real = _design(real_rows, feature, scales, columns)
    pseudo = _design(pseudo_rows, feature, scales, columns)
    if real is None or pseudo is None or real[0].shape[0] != len(pairs) or pseudo[0].shape[0] != len(pairs):
        return empty
    xr, yr = real[0], real[1]
    xp, yp = pseudo[0], pseudo[1]
    # Pair order follows the input. Clusters are the real-touch weeks.
    clusters = [int(pair["real"]["cluster"]) for pair in pairs]
    keys = sorted(set(clusters))
    code = {key: i for i, key in enumerate(keys)}
    cluster = np.asarray([code[c] for c in clusters], dtype=np.int64)
    n_clusters = len(keys)
    beta_r = _fit(xr, yr)
    beta_p = _fit(xp, yp)
    if beta_r is None or beta_p is None:
        return empty
    loc = columns.index("feature_z")
    point_r = float(beta_r[loc])
    point_p = float(beta_p[loc])
    rng = np.random.default_rng(seed)
    membership = [np.flatnonzero(cluster == c) for c in range(n_clusters)]
    draw = rng.integers(0, n_clusters, size=(draws, n_clusters))
    acc_r = np.full(draws, np.nan)
    acc_p = np.full(draws, np.nan)
    acc_d = np.full(draws, np.nan)
    for b in range(draws):
        counts = np.bincount(draw[b], minlength=n_clusters)
        parts = [np.repeat(membership[c], int(counts[c])) for c in range(n_clusters) if counts[c]]
        if not parts:
            continue
        idx = np.concatenate(parts)
        got_r = _fit(xr[idx], yr[idx])
        got_p = _fit(xp[idx], yp[idx])
        if got_r is None or got_p is None:
            continue
        acc_r[b] = float(got_r[loc])
        acc_p[b] = float(got_p[loc])
        acc_d[b] = float(got_r[loc] - got_p[loc])
    d_ci, _se, valid = _ci(acc_d, draws)
    r_ci, _, _ = _ci(acc_r, draws)
    p_ci, _, _ = _ci(acc_p, draws)
    return {
        "n_pairs": len(pairs),
        "columns": columns,
        "status": "ESTIMATED",
        "beta_real": point_r,
        "beta_pseudo": point_p,
        "delta": point_r - point_p,
        "delta_ci95": d_ci,
        "beta_real_ci95": r_ci,
        "beta_pseudo_ci95": p_ci,
        "bootstrap_valid": valid,
    }


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


def drop_redundant(rows: list[dict], names: tuple[str, ...]) -> dict:
    """Drop the later spot feature of any pair with |rho| >= 0.90."""
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
