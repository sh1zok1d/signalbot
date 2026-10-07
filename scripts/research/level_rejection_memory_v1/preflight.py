"""Outcome-blind counts for LEVEL_REJECTION_MEMORY_V1.

Classifies the previous touch only far enough to count REJECT_FIRST pairs and the
predictor distribution. Does not aggregate the next touch's BREAK / REJECT / NEITHER.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import numpy as np

from scripts.research.level_touch_degradation_v1.build import build_population
from scripts.research.level_touch_degradation_v1.constants import ZONE_HALF_PRIMARY
from scripts.research.level_touch_degradation_v1.data import load_discovery_bars

from . import constants as K
from .hits import annotate
from .inference import freeze_scales, planning_mde
from .pairs import feature_pairs, iter_consecutive, pair_features

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "research" / "LEVEL_REJECTION_MEMORY_V1_PREFLIGHT.json"
PARENT_PREFLIGHT = ROOT / "docs" / "research" / "LEVEL_TOUCH_DEGRADATION_V1_PREFLIGHT.json"

FORBIDDEN_KEYS = ("next_outcome", "break_rate", "reject_rate", "delta", "effect_pp", "ci", "p_value",
                  "coef", "correlation_with_outcome")


def _assert_parent_edges() -> None:
    blob = json.loads(PARENT_PREFLIGHT.read_text(encoding="utf-8"))
    edges = blob["real"]["sigma_tercile_edges"]
    if [K.PARENT_SIGMA_LO, K.PARENT_SIGMA_HI] != edges:
        raise RuntimeError("parent sigma edges drifted; do not refit them here")


def _finite(x):
    if isinstance(x, float) and not np.isfinite(x):
        return None
    if isinstance(x, dict):
        return {k: _finite(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_finite(v) for v in x]
    return x


def _walk_keys(obj, found: list[str]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in FORBIDDEN_KEYS:
                found.append(k)
            _walk_keys(v, found)
    elif isinstance(obj, list):
        for v in obj:
            _walk_keys(v, found)


def _quantiles(values: list[float]) -> dict:
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return {"n": 0}
    qs = np.quantile(x, [0.1, 0.25, 0.5, 0.75, 0.9])
    return {"n": int(x.size), "min": float(x.min()), "p10": float(qs[0]), "p25": float(qs[1]),
            "p50": float(qs[2]), "p75": float(qs[3]), "p90": float(qs[4]), "max": float(x.max())}


def _corr(a: list[float], b: list[float]):
    x = np.asarray(a, dtype=float)
    y = np.asarray(b, dtype=float)
    if x.size < 3 or float(x.std()) == 0.0 or float(y.std()) == 0.0:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def _audit(annotated: list[dict]) -> dict:
    if any("next_outcome" in t for t in annotated):
        raise RuntimeError("preflight touches must not carry a next-touch outcome")
    n_eligible = sum(1 for t in annotated if t.get("feature_eligible"))
    n_reject = sum(1 for t in annotated if t.get("feature_eligible") and t.get("outcome") == "REJECT")
    ineligible_successor = 0
    nonpositive_gap = 0
    pairs = []
    for prev, nxt in iter_consecutive(annotated):
        if prev.get("outcome") != "REJECT" or not prev.get("feature_eligible"):
            continue
        if not nxt.get("feature_eligible"):
            ineligible_successor += 1
            continue
        feat = pair_features(prev, nxt)
        if feat is None:
            nonpositive_gap += 1
            continue
        if "next_outcome" in feat:
            raise RuntimeError("pair_features leaked a next-touch outcome")
        pairs.append(feat)
    scales = freeze_scales(pairs)
    by_year = Counter(p["year"] for p in pairs)
    by_family = Counter(p["family"] for p in pairs)
    by_side = Counter(p["side"] for p in pairs)
    by_bucket = Counter(p["next_bucket"] for p in pairs)
    by_vol = Counter(p["vol_tercile"] for p in pairs)
    n = len(pairs)
    clusters = len({p["cluster"] for p in pairs})
    max_year = (max(by_year.values()) / n) if n else None
    max_family = (max(by_family.values()) / n) if n else None
    deff = (n / clusters) if clusters else None
    return {
        "feature_eligible_touches": n_eligible,
        "rejected_feature_eligible_touches": n_reject,
        "feature_pairs": n,
        "ineligible_successor": ineligible_successor,
        "nonpositive_gap": nonpositive_gap,
        "clusters": clusters,
        "events_per_cluster": deff,
        "by_year": {str(y): int(by_year[y]) for y in K.YEARS},
        "by_family": {fam: int(by_family[fam]) for fam in K.FAMILIES},
        "by_side": {"resistance": int(by_side[1]), "support": int(by_side[-1])},
        "by_next_bucket": {"2": int(by_bucket["2"]), "3+": int(by_bucket["3+"])},
        "by_vol_tercile": {str(i): int(by_vol[i]) for i in (0, 1, 2)},
        "max_year_share": max_year,
        "max_family_share": max_family,
        "bars_to_reject": _quantiles([p["bars_to_reject"] for p in pairs]),
        "speed_raw": _quantiles([p["speed_raw"] for p in pairs]),
        "gap_bars": _quantiles([p["gap_bars"] for p in pairs]),
        "log_gap": _quantiles([p["log_gap"] for p in pairs]),
        "overshoot": _quantiles([p["overshoot"] for p in pairs if p.get("overshoot") is not None]),
        "corr_speed_log_gap": _corr([p["speed_raw"] for p in pairs], [p["log_gap"] for p in pairs]),
        "scales": scales,
        "planning_mde_deff_1_25": planning_mde(n, K.PLANNING_DEFF),
        "planning_mde_cluster": planning_mde(n, deff) if deff else None,
    }


def run() -> dict:
    _assert_parent_edges()
    bars = load_discovery_bars()
    built = build_population(bars, ZONE_HALF_PRIMARY)
    real = annotate(bars.high, bars.low, built["touches"])
    control = annotate(bars.high, bars.low, built["control_touches"])
    real_audit = _audit(real)
    control_audit = _audit(control)
    n = real_audit["feature_pairs"]
    scales = real_audit["scales"]
    computable = bool(
        n > len(K.PRIMARY_COLUMNS)
        and scales["speed_sd"] and scales["speed_sd"] > 0
        and scales["gap_sd"] and scales["gap_sd"] > 0
        and real_audit["by_next_bucket"]["2"] > 0
        and real_audit["by_next_bucket"]["3+"] > 0
        and control_audit["feature_pairs"] > len(K.PRIMARY_COLUMNS)
    )
    payload = {
        "unit": K.UNIT,
        "dependency": K.DEPENDENCY_SHA,
        "bars": int(bars.n),
        "zone_half": ZONE_HALF_PRIMARY,
        "parent_sigma_edges": [K.PARENT_SIGMA_LO, K.PARENT_SIGMA_HI],
        "real": real_audit,
        "control": {
            "feature_pairs": control_audit["feature_pairs"],
            "clusters": control_audit["clusters"],
            "by_year": control_audit["by_year"],
            "by_family": control_audit["by_family"],
            "by_side": control_audit["by_side"],
            "by_next_bucket": control_audit["by_next_bucket"],
            "rejected_feature_eligible_touches": control_audit["rejected_feature_eligible_touches"],
        },
        "method_computable": computable,
        "notes": [
            "Scales are moments of real feature pairs. The next touch's outcome is not an input.",
            "Ambiguous next touches are still inside these counts; execution drops them and does not refit scales.",
            "Planning MDE is an unadjusted lower bound at rate 0.5, not a gate.",
        ],
    }
    found: list[str] = []
    _walk_keys(payload, found)
    if found:
        raise RuntimeError(f"preflight payload contains forbidden keys: {found}")
    OUT.write_text(json.dumps(_finite(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    payload = run()
    real = payload["real"]
    print(json.dumps({
        "pairs": real["feature_pairs"],
        "clusters": real["clusters"],
        "reject_touches": real["rejected_feature_eligible_touches"],
        "computable": payload["method_computable"],
        "mde_1_25": real["planning_mde_deff_1_25"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
