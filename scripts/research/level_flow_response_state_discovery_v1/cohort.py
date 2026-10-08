"""First-touch rows from the #358 builder, plus the fifth observable.

X5 is the #358 oriented displacement. It is not divided or multiplied by flow.
Outcomes are not classified here.
"""

from __future__ import annotations

import math

from scripts.research.level_positioning_flow_discovery_v1.cohort import (
    assemble as parent_assemble,
    population,
)
from scripts.research.level_positioning_flow_discovery_v1.oi import load_bound_oi

from . import constants as K


def predictors_ok(row: dict) -> bool:
    for name in K.FEATURES:
        value = row.get(name)
        if value is None or not math.isfinite(float(value)):
            return False
    return True


def _annotate(row: dict) -> dict:
    out = dict(row)
    out["ORIENTED_PRICE_PROGRESS_60M"] = out.get("disp")
    return out


def assemble(bars, oi, built=None):
    raw = parent_assemble(bars, oi, built)
    real_rows = [_annotate(row) for row in raw["real_rows"]]
    pairs = []
    for pair in raw["pairs"]:
        pairs.append({
            **pair,
            "real": _annotate(pair["real"]),
            "pseudo": _annotate(pair["pseudo"]),
        })
    return {**raw, "real_rows": real_rows, "pairs": pairs}


def outcome_ready(row: dict) -> bool:
    return bool(row.get("nuisance_ok")) and predictors_ok(row) and row.get("state") is not None


__all__ = ["assemble", "load_bound_oi", "outcome_ready", "population", "predictors_ok"]
