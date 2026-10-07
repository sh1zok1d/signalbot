"""Outcome-blind redundancy and the sparse-count coding rule. No outcome is read."""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from . import constants as K


def pearson(a: np.ndarray, b: np.ndarray) -> float:
    mask = np.isfinite(a) & np.isfinite(b)
    if int(mask.sum()) < 3:
        return math.nan
    x, y = a[mask], b[mask]
    if float(x.std()) == 0 or float(y.std()) == 0:
        return math.nan
    return float(np.corrcoef(x, y)[0, 1])


def _column(rows: list[dict], name: str) -> np.ndarray:
    out = np.empty(len(rows), dtype=float)
    for i, row in enumerate(rows):
        value = row.get(name)
        out[i] = math.nan if value is None else float(value)
    return out


def code_count(values: np.ndarray) -> dict:
    """Binary multi-vs-singleton, unless count>=3 is common enough to keep the integer."""
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return {"coding": "drop", "reason": "no finite values"}
    share_ge3 = float(np.mean(finite >= 3.0))
    n_unique = int(np.unique(np.round(finite, 6)).size)
    if n_unique < 2:
        return {"coding": "drop", "reason": "no variation", "share_ge3": share_ge3}
    if share_ge3 >= K.COUNT_GE3_SHARE:
        return {"coding": "continuous", "share_ge3": share_ge3, "n_unique": n_unique}
    return {"coding": "binary", "share_ge3": share_ge3, "n_unique": n_unique}


def apply_coding(rows: list[dict], name: str) -> dict:
    """Rewrite `name` in place when the frozen sparse rule says binary. Returns the decision."""
    decision = code_count(_column(rows, name))
    decision["feature"] = name
    if decision["coding"] == "binary":
        for row in rows:
            value = row.get(name)
            if value is None or not math.isfinite(float(value)):
                row[name] = None
            else:
                row[name] = 1.0 if float(value) >= 2.0 else 0.0
        decision["contrast"] = "multi_minus_singleton"
    elif decision["coding"] == "continuous":
        decision["contrast"] = "per_1sd_count"
    return decision


def missing_rate(rows: list[dict], name: str) -> float:
    if not rows:
        return 1.0
    bad = 0
    for row in rows:
        value = row.get(name)
        if value is None or not math.isfinite(float(value)):
            bad += 1
    return bad / len(rows)


def apply_rule(rows: list[dict], candidates: tuple[str, ...]) -> dict:
    """Drop a later feature when |rho| >= 0.90 with a kept feature or with age."""
    kept: list[str] = []
    dropped: list[dict] = []
    cols = {name: _column(rows, name) for name in list(candidates) + [K.AGE_NUISANCE]}
    for name in candidates:
        worst_name = None
        worst_abs = -1.0
        worst_rho = None
        rivals = kept if name == K.AGE_NUISANCE else kept + [K.AGE_NUISANCE]
        # Age is allowed to correlate with itself; it is not dropped for matching the nuisance.
        rivals = [other for other in rivals if other != name]
        for other in rivals:
            rho = pearson(cols[name], cols[other])
            if math.isfinite(rho) and abs(rho) >= worst_abs:
                worst_abs = abs(rho)
                worst_name = other
                worst_rho = rho
        if worst_name is not None and worst_abs >= K.REDUNDANCY_RHO:
            dropped.append({
                "feature": name,
                "reason": "redundancy rule",
                "with": worst_name,
                "rho": worst_rho,
            })
            continue
        kept.append(name)
    return {"retained": kept, "dropped": dropped, "rho_cut": K.REDUNDANCY_RHO}


def matrix(rows: list[dict], names: list[str]) -> dict:
    cols = {name: _column(rows, name) for name in names}
    out = {}
    for i, a in enumerate(names):
        for b in names[i:]:
            rho = pearson(cols[a], cols[b])
            out[f"{a}__{b}"] = None if not math.isfinite(rho) else rho
    return out
