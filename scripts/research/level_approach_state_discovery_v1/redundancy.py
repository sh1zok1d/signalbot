"""Outcome-blind redundancy. Correlations of predictors only. No outcome is read."""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from . import constants as K


def pearson(a: np.ndarray, b: np.ndarray) -> float:
    mask = np.isfinite(a) & np.isfinite(b)
    if int(mask.sum()) < 3:
        return math.nan
    x = a[mask]
    y = b[mask]
    if float(x.std()) == 0 or float(y.std()) == 0:
        return math.nan
    return float(np.corrcoef(x, y)[0, 1])


def _column(rows: list[dict], name: str) -> np.ndarray:
    out = np.empty(len(rows), dtype=float)
    for i, row in enumerate(rows):
        value = row.get(name)
        out[i] = math.nan if value is None else float(value)
    return out


def apply_rule(rows: list[dict], candidates: tuple[str, ...] = K.KEEP_ORDER) -> dict:
    """Greedy keep. A later feature loses if |rho| >= 0.90 with a kept feature or with log(steps)."""
    kept: list[str] = []
    dropped: list[dict] = []
    cols = {name: _column(rows, name) for name in list(candidates) + [K.DURATION_NUISANCE, "pullback"]}
    pull_rho = pearson(cols["pullback"], cols["efficiency"]) if "efficiency" in cols else math.nan
    dropped.append({
        "feature": "pullback",
        "reason": "algebraic complement of efficiency: pullback = (1 - efficiency) / 2",
        "with": "efficiency",
        "rho": None if not math.isfinite(pull_rho) else pull_rho,
    })
    for name in candidates:
        rivals = {}
        worst_name = None
        worst_abs = -1.0
        for other in kept + [K.DURATION_NUISANCE]:
            rho = pearson(cols[name], cols[other])
            rivals[other] = None if not math.isfinite(rho) else rho
            if math.isfinite(rho) and abs(rho) >= worst_abs:
                worst_abs = abs(rho)
                worst_name = other
        if worst_name is not None and worst_abs >= K.REDUNDANCY_RHO:
            dropped.append({
                "feature": name,
                "reason": "redundancy rule",
                "with": worst_name,
                "rho": rivals[worst_name],
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
