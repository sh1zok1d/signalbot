"""Outcome-blind census. This module must not import the late label."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from scripts.research.level_cross_venue_reaction_discovery_v1.series import load_reaction_series
from scripts.research.level_touch_degradation_v1.data import load_discovery_bars

from . import constants as K
from .cohort import assemble, early_census, slice_counts, unresolved_baseline
from .inference import drop_redundant, freeze_scales, pearson, rough_mde, scale_hex, tertile_cuts
from .spot import load_spot

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "research" / "LEVEL_SPOT_PERP_REACTION_DISCOVERY_V1_PREFLIGHT.json"


def _finite(row: dict, name: str) -> bool:
    value = row.get(name)
    return value is not None and math.isfinite(float(value))


def _dist(values: np.ndarray) -> dict:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return {"n": 0}
    qs = np.quantile(finite, [0.05, 0.25, 0.5, 0.75, 0.95])
    return {
        "n": int(finite.size), "mean": float(finite.mean()), "sd": float(finite.std(ddof=0)),
        "p05": float(qs[0]), "p25": float(qs[1]), "p50": float(qs[2]),
        "p75": float(qs[3]), "p95": float(qs[4]),
    }


def run() -> dict:
    bars = load_discovery_bars()
    venues = load_reaction_series()
    spot, census = load_spot()
    built = assemble(bars, venues, spot)
    rows = built["real_rows"]
    base = unresolved_baseline(rows)
    price = [row for row in base if _finite(row, "SPOT_ORIENTED_MOVE_15M")]
    sp3_name = "RELATIVE_SPOT_TAKER_PRESSURE_15M"
    legal = sum(1 for row in price if _finite(row, sp3_name))
    legal_rate = float(legal / len(price)) if price else 0.0
    names = list(K.FEATURES)
    pre_drops = []
    if legal_rate < K.SP3_MIN_LEGAL_RATE:
        names = [name for name in names if name != sp3_name]
        pre_drops.append({
            "feature": sp3_name,
            "reason": "spot or perp taker aggregate is missing on too many price-complete rows",
            "legal_rate": legal_rate,
        })
    audited = [row for row in base if all(_finite(row, name) for name in names)]
    redundancy = drop_redundant(audited, tuple(names))
    retained = list(redundancy["retained"])
    support = [row for row in base if all(_finite(row, name) for name in retained)] if retained else []
    scales = freeze_scales(support, tuple(retained))
    cuts = {name: tertile_cuts(support, name) for name in retained}
    cut_hex = {
        name: {key: None if value is None else float(value).hex() for key, value in item.items()}
        for name, item in cuts.items()
    }
    context_rho = {}
    for name in retained:
        context_rho[f"{name}__END_POSITION_X"] = pearson(support, name, "END_POSITION_X")
        context_rho[f"{name}__{K.CV1_NAME}"] = pearson(support, name, K.CV1_NAME)
    pseudo_pairs = 0
    for pair in built["pairs"]:
        real, pseudo = pair["real"], pair["pseudo"]
        if real["early_status"] != "UNRESOLVED" or pseudo["early_status"] != "UNRESOLVED":
            continue
        if not real["baseline_ok"] or not pseudo["baseline_ok"]:
            continue
        if all(_finite(real, name) and _finite(pseudo, name) for name in retained):
            pseudo_pairs += 1
    history_ok = census["missing_fraction"] <= K.SPOT_MAX_MISSING_FRACTION and census["n_bars"] > 0
    expected = len(support) * K.PLANNING_RESOLVE_FRACTION
    gate = (
        history_ok
        and len(support) >= K.PRE_OUTCOME_MIN_UNRESOLVED
        and expected >= K.INFORMATION_MIN_RESOLVED
        and bool(retained)
    )
    payload = {
        "unit": K.UNIT,
        "outcomes_read": False,
        "novelty_ok": True,
        "history_ok": history_ok,
        "identity_artifact": not history_ok,
        "reference_venue": K.REFERENCE_VENUE,
        "other_venues": list(K.OTHER_VENUES),
        "spot": census,
        "sp3_legal_rate": legal_rate,
        "alignment_tolerance_ms": K.ALIGNMENT_TOLERANCE_MS,
        "event_window": [K.EVENT_START, K.EVENT_END],
        "structural_episodes": built["structural_episodes"],
        "real_status": built["real_status"],
        "pseudo_status": built["pseudo_status"],
        "first_touch_legitimate": built["real_status"]["LEGITIMATE"],
        "early": early_census(rows),
        "unresolved_baseline": len(base),
        "feature_complete_unresolved": len(support),
        "resolved_after_d": None,
        "pseudo_unresolved_feature_complete_pairs": pseudo_pairs,
        "pre_drops": pre_drops,
        "redundancy": redundancy,
        "retained": retained,
        "context_rho": context_rho,
        "slice_counts_unresolved_complete": slice_counts(support),
        "return_distributions": {
            name: _dist(np.asarray([row.get(name, math.nan) for row in support], dtype=float))
            for name in ("RET_SPOT", "RET_BINANCE", K.CV1_NAME, "END_POSITION_X", *retained)
        },
        "scales": scales,
        "scale_hex": {name: scale_hex(scales[name]) for name in scales if name != "n"},
        "tertile_cuts_hex": cut_hex,
        "rough_mde_80": rough_mde(len(support)),
        "planning_resolve_fraction": K.PLANNING_RESOLVE_FRACTION,
        "expected_primary_n": expected,
        "pre_outcome_gate_pass": gate,
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload
