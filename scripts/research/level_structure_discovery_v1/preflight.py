"""Outcome-blind preflight for LEVEL_STRUCTURE_DISCOVERY_V1.

Counts, missingness, coding, correlations and frozen scales only. No touch outcome
is classified and no slope is fit.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from scripts.research.level_approach_state_discovery_v1.approach import compute_features, price_features_ok, volume_ok
from scripts.research.level_approach_state_discovery_v1.constants import BAND_MULT_PRIMARY
from scripts.research.level_approach_state_discovery_v1.constants import (
    PARENT_SIGMA_HI,
    PARENT_SIGMA_LO,
)
from scripts.research.level_touch_degradation_v1.build import build_population
from scripts.research.level_touch_degradation_v1.constants import ZONE_HALF_PRIMARY
from scripts.research.level_touch_degradation_v1.data import load_discovery_bars

from . import constants as K
from .inference import freeze_scales
from .redundancy import apply_coding, apply_rule, matrix, missing_rate
from .rows import complete, control_rows, counts, prepare, real_rows, restrict_matched

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "research" / "LEVEL_STRUCTURE_DISCOVERY_V1_PREFLIGHT.json"
FORBIDDEN = ("outcome", "break_rate", "reject_rate", "neither_rate", "coef", "p_value", "q_value", "ci95", "delta")


def _dist(rows: list[dict], name: str) -> dict:
    vals = np.array([float(row[name]) for row in rows if row.get(name) is not None], dtype=float)
    vals = vals[np.isfinite(vals)]
    if vals.size == 0:
        return {"n": 0}
    qs = np.quantile(vals, [0.25, 0.5, 0.75])
    return {
        "n": int(vals.size),
        "mean": float(vals.mean()),
        "sd": float(vals.std(ddof=0)),
        "min": float(vals.min()),
        "p25": float(qs[0]),
        "p50": float(qs[1]),
        "p75": float(qs[2]),
        "max": float(vals.max()),
    }


def _parity(episodes: list[dict], ledgers: dict) -> None:
    for ep in episodes:
        ledger = ledgers.get(ep["episode_id"])
        if ledger is None:
            raise RuntimeError(f"ledger missing {ep['episode_id']}")
        birth = [m for m in ledger["members"] if m["birth"]]
        if len(birth) != int(ep["n_members"]):
            raise RuntimeError("birth membership drifted from the parent episode")
        if [m["kind"] for m in birth] != list(ep["member_kinds"]):
            raise RuntimeError("birth kinds drifted from the parent episode")
        if list(ledger["absorbed_kinds"]) != list(ep["absorbed_later"]):
            raise RuntimeError("later absorption drifted from the parent episode")


def _approach_ok(row: dict, bars) -> bool:
    feat = compute_features(
        bars.close, bars.high, bars.low, bars.quote,
        j=int(row["j"]), i0=int(row["i0"]), side=int(row["side"]),
        zlo=float(row["zone_low"]), zhi=float(row["zone_high"]),
        x=float(row["x_primary"]), sigma=float(row["sigma"]), band_mult=BAND_MULT_PRIMARY,
    )
    if feat is None or not price_features_ok(feat) or not volume_ok(feat):
        return False
    for name in K.APPROACH_FEATURES:
        row[name] = float(feat[name])
    return True


def run() -> dict:
    if abs(K.PARENT_SIGMA_LO - PARENT_SIGMA_LO) > 0 or abs(K.PARENT_SIGMA_HI - PARENT_SIGMA_HI) > 0:
        raise RuntimeError("parent sigma edges drifted")
    bars = load_discovery_bars()
    built = build_population(bars, ZONE_HALF_PRIMARY)
    prepared = prepare(bars, built)
    _parity(built["episodes"], prepared["ledgers"])
    real = real_rows(built["touches"], prepared)
    real_ids = {row["episode_id"] for row in real}
    pseudo = control_rows(built["control_touches"], built["controls"], prepared, real_ids)
    raw = list(K.RAW_FEATURES)
    missing = {name: missing_rate(real, name) for name in raw}
    dropped_missing = [
        {"feature": name, "reason": "missingness above the predeclared cap", "rate": missing[name]}
        for name in raw if missing[name] > K.MISSING_MAX
    ]
    candidates = [name for name in raw if missing[name] <= K.MISSING_MAX]
    real_f = complete(real, candidates)
    pseudo_f = complete(pseudo, candidates)
    real_f, pseudo_f = restrict_matched(real_f, pseudo_f)
    coding = {}
    for name in ("confluence", "diversity"):
        if name not in candidates:
            continue
        decision = apply_coding(real_f, name)
        if decision["coding"] == "binary":
            for row in pseudo:
                value = row.get(name)
                if value is None or value != value:
                    row[name] = None
                else:
                    row[name] = 1.0 if float(value) >= 2.0 else 0.0
        coding[name] = decision
        if decision["coding"] == "drop":
            candidates.remove(name)
            dropped_missing.append({"feature": name, "reason": decision["reason"], "rate": None})
    for name in list(candidates):
        vals = [float(row[name]) for row in real_f if row.get(name) is not None]
        finite = [v for v in vals if np.isfinite(v)]
        if len(set(np.round(finite, 6))) < 2:
            candidates.remove(name)
            dropped_missing.append({"feature": name, "reason": "no variation on the real touches", "rate": None})
    real_c = complete(real_f, candidates)
    pseudo_c = complete(pseudo_f, candidates)
    rule = apply_rule(real_c, tuple(candidates))
    retained = rule["retained"]
    real_c = complete(real_c, retained)
    pseudo_c = complete(pseudo_c, retained)
    scale_names = list(retained)
    if "age" not in scale_names and any(row.get("age") is not None for row in real_c):
        scale_names.append("age")
    if "confluence" in retained or any(name == "zone_span" for name in retained):
        if "confluence" not in scale_names and any(row.get("confluence") is not None for row in real_c):
            scale_names.append("confluence")
    scales = freeze_scales(real_c, scale_names, coding)
    approach_rows = []
    for row in real_c:
        copied = dict(row)
        if _approach_ok(copied, bars):
            approach_rows.append(copied)
    approach_scales = freeze_scales(approach_rows, list(K.APPROACH_FEATURES), {})
    multi = {}
    for name in ("confluence", "diversity"):
        if name not in retained:
            continue
        if coding.get(name, {}).get("coding") == "binary":
            multi[name] = int(sum(1 for row in real_c if float(row[name]) >= 1.0))
        else:
            multi[name] = int(sum(1 for row in real_c if float(row[name]) >= 3.0))
    payload = {
        "unit": K.UNIT,
        "mode": K.MODE,
        "outcome_blind": True,
        "n_bars": int(bars.n),
        "parent_episodes": len(built["episodes"]),
        "parent_controls": len(built["controls"]),
        "parent_feature_eligible_touches": int(sum(1 for t in built["touches"] if t.get("feature_eligible"))),
        "missing": missing,
        "dropped_missing_or_degenerate": dropped_missing,
        "coding": coding,
        "raw_features": list(K.RAW_FEATURES),
        "candidates_after_audit": candidates,
        "retained": retained,
        "dropped_redundant": rule["dropped"],
        "rho_cut": K.REDUNDANCY_RHO,
        "correlations": matrix(real_c, list(dict.fromkeys(list(retained) + ["age", "confluence"]))),
        "distributions": {name: _dist(real_c, name) for name in list(dict.fromkeys(scale_names))},
        "multi_member_touches": multi,
        "real_counts": counts(real_c),
        "pseudo_counts": counts(pseudo_c),
        "scales": scales,
        "approach_overlap_n": len(approach_rows),
        "approach_scales": approach_scales,
        "material_cells": K.material_cells(len(retained)),
        "fdr_family_size": K.fdr_family_size(len(retained)),
        "cells_per_feature_outcome": K.cells_per_feature_outcome(),
        "extreme_tol": K.EXTREME_TOL,
        "formation_base": K.FORMATION_BASE,
        "formation_min": K.FORMATION_MIN,
        "practical_scale": K.PRACTICAL_SCALE,
        "fdr_q": K.FDR_Q,
        "taker_not_used": True,
        "note": (
            "Counts and predictor moments only. No touch outcome was classified and no slope was fit. "
            "Quote volume is the source-period sum of the Binance quote field. Taker-buy quote was not used. "
            "The 70% DAY cap from the approach unit is not applied."
        ),
    }
    blob = json.dumps(payload)
    for key in FORBIDDEN:
        if f'"{key}"' in blob:
            raise RuntimeError(f"preflight leaked {key}")
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    result = run()
    print(json.dumps({
        "real_n": result["real_counts"]["n"],
        "pseudo_n": result["pseudo_counts"]["n"],
        "retained": result["retained"],
        "dropped_missing": [row["feature"] for row in result["dropped_missing_or_degenerate"]],
        "dropped_redundant": [row["feature"] for row in result["dropped_redundant"]],
        "material_cells": result["material_cells"],
        "approach_overlap_n": result["approach_overlap_n"],
        "coding": {k: v.get("coding") for k, v in result["coding"].items()},
    }, indent=2))
