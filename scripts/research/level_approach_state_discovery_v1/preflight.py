"""Outcome-blind preflight for LEVEL_APPROACH_STATE_DISCOVERY_V1.

Counts, predictor distributions, correlations and the redundancy decision.
Does not classify BREAK / REJECT / NEITHER and does not fit a slope.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

import numpy as np

from scripts.research.level_touch_degradation_v1.build import build_population
from scripts.research.level_touch_degradation_v1.constants import ZONE_HALF_PRIMARY
from scripts.research.level_touch_degradation_v1.data import load_discovery_bars

from . import constants as K
from .inference import freeze_scales
from .redundancy import apply_rule, matrix
from .rows import collect, require_volume, volume_missing_rate

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "research" / "LEVEL_APPROACH_STATE_DISCOVERY_V1_PREFLIGHT.json"
PARENT_PREFLIGHT = ROOT / "docs" / "research" / "LEVEL_TOUCH_DEGRADATION_V1_PREFLIGHT.json"

FORBIDDEN_KEYS = ("outcome", "break_rate", "reject_rate", "neither_rate", "coef", "p_value", "q_value", "ci95")


def _assert_parent_edges() -> None:
    blob = json.loads(PARENT_PREFLIGHT.read_text(encoding="utf-8"))
    edges = blob["real"]["sigma_tercile_edges"]
    if [K.PARENT_SIGMA_LO, K.PARENT_SIGMA_HI] != edges:
        raise RuntimeError("parent sigma edges drifted; do not refit them here")


def _dist(rows: list[dict], name: str) -> dict:
    vals = np.array([math.nan if row.get(name) is None else float(row[name]) for row in rows], dtype=float)
    vals = vals[np.isfinite(vals)]
    if vals.size == 0:
        return {"n": 0}
    qs = np.quantile(vals, [0.0, 0.25, 0.5, 0.75, 1.0])
    return {
        "n": int(vals.size),
        "min": float(qs[0]),
        "p25": float(qs[1]),
        "p50": float(qs[2]),
        "p75": float(qs[3]),
        "max": float(qs[4]),
        "mean": float(vals.mean()),
        "sd": float(vals.std(ddof=0)),
    }


def _counts(rows: list[dict]) -> dict:
    def pack(counter: Counter) -> dict:
        return {str(key): int(counter[key]) for key in sorted(counter, key=lambda k: str(k))}

    return {
        "n": len(rows),
        "by_year": pack(Counter(row["year"] for row in rows)),
        "by_family": pack(Counter(row["family"] for row in rows)),
        "by_side": pack(Counter("support" if row["side"] < 0 else "resistance" for row in rows)),
        "by_bucket": pack(Counter(row["bucket"] for row in rows)),
        "clusters": len({row["cluster"] for row in rows}),
        "weeks": len({row["week"] for row in rows}),
    }


def _finite(node):
    if isinstance(node, float) and not math.isfinite(node):
        return None
    if isinstance(node, dict):
        return {key: _finite(value) for key, value in node.items()}
    if isinstance(node, list):
        return [_finite(value) for value in node]
    if isinstance(node, np.floating):
        value = float(node)
        return None if not math.isfinite(value) else value
    if isinstance(node, np.integer):
        return int(node)
    return node


def _guard(node) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key in FORBIDDEN_KEYS:
                raise RuntimeError(f"preflight tried to record {key}")
            _guard(value)
    elif isinstance(node, list):
        for value in node:
            _guard(value)


def summarize(bars, built: dict) -> dict:
    _assert_parent_edges()
    close, high, low, quote = bars.close, bars.high, bars.low, bars.quote
    parent_eligible = sum(1 for touch in built["touches"] if touch.get("feature_eligible"))
    if any(touch.get("outcome") not in (None,) for touch in built["touches"]):
        raise RuntimeError("parent touches already carry an outcome")
    primary = collect(built["touches"], close, high, low, quote, band_mult=K.BAND_MULT_PRIMARY)
    sensitivity = collect(built["touches"], close, high, low, quote, band_mult=K.BAND_MULT_SENSITIVITY)
    control = collect(built["control_touches"], close, high, low, quote, band_mult=K.BAND_MULT_PRIMARY)
    n_price = len(primary)
    missing = volume_missing_rate(primary)
    candidates = list(K.KEEP_ORDER)
    volume_status = "pending"
    if not math.isfinite(missing) or missing > K.VOLUME_MISSING_MAX:
        candidates = [name for name in candidates if name != "rel_volume"]
        volume_status = "excluded_before_outcome"
    else:
        primary = require_volume(primary, ["rel_volume"])
        sensitivity = require_volume(sensitivity, ["rel_volume"])
        control = require_volume(control, ["rel_volume"])
        volume_status = "available"
    rule = apply_rule(primary, tuple(candidates))
    retained = list(rule["retained"])
    if "rel_volume" not in retained:
        # The correlation sample may have required volume. Keeping those rows is fine:
        # a dropped volume feature does not put the touches back. Record which filter applied.
        pass
    names = retained + [K.DURATION_NUISANCE, "pullback", "n_steps"]
    payload = {
        "unit": K.UNIT,
        "mode": K.MODE,
        "outcome_blind": True,
        "n_bars": int(bars.n),
        "parent_feature_eligible": parent_eligible,
        "approach_price_eligible_before_volume_filter": n_price,
        "volume_missing_rate": missing,
        "volume_status": volume_status,
        "volume_field": "quote",
        "taker_not_used": True,
        "raw_features": list(K.RAW_FEATURES),
        "candidates_after_volume_audit": candidates,
        "retained": retained,
        "dropped": rule["dropped"],
        "rho_cut": K.REDUNDANCY_RHO,
        "correlations": matrix(primary, [name for name in names if name != "n_steps"] + ["n_steps"]),
        "distributions": {name: _dist(primary, name) for name in retained + [K.DURATION_NUISANCE, "pullback"]},
        "counts": _counts(primary),
        "scales": freeze_scales(primary, retained),
        "sensitivity_band_mult": K.BAND_MULT_SENSITIVITY,
        "sensitivity_counts": _counts(sensitivity),
        "sensitivity_scales": freeze_scales(sensitivity, retained),
        "control_counts": _counts(control),
        "material_cells": K.material_cells(len(retained)),
        "fdr_family_size": K.fdr_family_size(len(retained)),
        "cells_per_feature_outcome": K.cells_per_feature_outcome(),
        "note": (
            "Counts and predictor moments only. No touch outcome was classified and no slope was fit. "
            "Quote volume is the Binance kline quote field on the same complete 5m bins as OHLC, read only before the touch bar. "
            "Taker-buy quote was not used."
        ),
    }
    _guard(payload)
    return _finite(payload)


def main() -> None:
    bars = load_discovery_bars()
    built = build_population(bars, ZONE_HALF_PRIMARY)
    payload = summarize(bars, built)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "retained": payload["retained"],
        "n": payload["counts"]["n"],
        "clusters": payload["counts"]["clusters"],
        "volume_status": payload["volume_status"],
        "material_cells": payload["material_cells"],
        "dropped": [item["feature"] for item in payload["dropped"]],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
