"""Outcome-blind census. Does not read a bar after D and does not label late resolution."""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

import numpy as np

from scripts.research.level_positioning_flow_discovery_v1.oi import load_bound_oi
from scripts.research.level_touch_degradation_v1.data import load_discovery_bars

from . import constants as K
from .cohort import assemble, column, early_census, feature_complete, population, unresolved_rows
from .inference import freeze_scales, redundancy, scale_hex

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "research" / "LEVEL_POST_TOUCH_REACTION_DISCOVERY_V1_PREFLIGHT.json"

PARITY_KEYS = (
    "structural_episodes",
    "real_legitimate",
    "pseudo_legitimate",
    "geometry_pairs",
    "real_nuisance",
    "real_weeks",
    "n_unresolved",
    "n_early_resolved",
    "n_early_ambiguous",
    "kept_features",
    "scale_hex",
    "oi_jsonl_sha256",
)


def _dist(values: np.ndarray) -> dict:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return {"n": 0, "missing_rate": 1.0}
    qs = np.quantile(finite, [0.01, 0.05, 0.25, 0.50, 0.75, 0.95, 0.99])
    zeros = int(np.sum(finite == 0.0))
    return {
        "n": int(finite.size),
        "missing_rate": float(1.0 - finite.size / values.size) if values.size else 1.0,
        "zero_rate": float(zeros / finite.size) if finite.size else None,
        "mean": float(finite.mean()),
        "sd": float(finite.std(ddof=0)),
        "min": float(finite.min()),
        "p01": float(qs[0]),
        "p05": float(qs[1]),
        "p25": float(qs[2]),
        "p50": float(qs[3]),
        "p75": float(qs[4]),
        "p95": float(qs[5]),
        "p99": float(qs[6]),
        "max": float(finite.max()),
    }


def _counts(rows: list[dict], key: str) -> dict:
    return dict(Counter(row[key] for row in rows))


def information(n: int, clusters: int) -> dict:
    """Bernoulli bound on a +1 SD slope. Context only. Not a gate."""
    if n <= 1:
        return {"n": n, "clusters": clusters, "gate": False}
    se = 0.5 / math.sqrt(n / K.INFO_DEFF)
    z = 1.959963984540054 + 0.8416212335729143
    return {
        "n": int(n),
        "clusters": int(clusters),
        "deff_assumed": K.INFO_DEFF,
        "bernoulli_se_per_sd": se,
        "rough_80pct_mde": z * se,
        "gate": False,
        "note": "Upper bound using a 0.25 Bernoulli variance and the parent planning deff. Not a pass or fail.",
    }


def _py(value):
    if isinstance(value, dict):
        return {str(k): _py(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_py(v) for v in value]
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return None if not math.isfinite(number) else number
    if isinstance(value, (np.integer, int)) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    return value


def summarize(bars, oi, oi_meta: dict, built: dict | None = None) -> dict:
    built = population(bars) if built is None else built
    assembled = assemble(bars, oi, built)
    real = assembled["real_rows"]
    census = early_census(real)
    nuisance = [row for row in real if row["nuisance_ok"]]
    unresolved = unresolved_rows(nuisance)
    rule = redundancy(unresolved)
    kept = rule["kept"]
    scales = {}
    for name in list(kept) + ["disp", "rel_volume", K.PRICE_FEATURE]:
        support = unresolved if name in ("disp", "rel_volume") else [
            row for row in unresolved if feature_complete(row, (name,))
        ]
        scales[name] = freeze_scales(support, [name])[name]
    both = []
    for pair in assembled["pairs"]:
        if (
            pair["real"].get("early_status") == "UNRESOLVED"
            and pair["pseudo"].get("early_status") == "UNRESOLVED"
            and feature_complete(pair["real"], kept)
            and feature_complete(pair["pseudo"], kept)
        ):
            both.append(pair["episode_id"])
    per_feature = {}
    for name in K.RAW_FEATURES:
        series = column(unresolved, name)
        per_feature[name] = {
            "distribution": _dist(series),
            "real_complete": int(np.isfinite(series).sum()),
        }
    weeks = {int(row["week"]) for row in unresolved}
    info_n = 0
    if kept:
        info_n = sum(1 for row in unresolved if feature_complete(row, kept))
    blocked = None
    if len(kept) < K.MIN_RETAINED:
        blocked = "FEWER_THAN_3_RELIABLE_OBSERVABLES"
    for name, scale in scales.items():
        sd = scale.get("sd")
        if sd is None or not math.isfinite(float(sd)) or float(sd) <= 0.0:
            blocked = f"NONPOSITIVE_SCALE:{name}"
            break
    if not unresolved:
        blocked = "NO_UNRESOLVED_EVENTS"
    return {
        "outcome_blind": True,
        "mode": K.MODE,
        "exposure_status": K.EXPOSURE_STATUS,
        "blocked_reason": blocked,
        "proceed_to_outcomes": blocked is None,
        "event_window": {"start": K.EVENT_START, "end_exclusive": K.EVENT_END},
        "decision": {
            "T": "open of the touch bar",
            "D": "T + 15 minutes",
            "reaction_bars": "j, j+1, j+2",
            "early_bars": "j+1, j+2",
            "late_bars": "j+3 .. j+48",
            "touch_bar_is_not_a_resolution": True,
        },
        "structural_episodes": assembled["structural_episodes"],
        "controls_built": assembled["controls_built"],
        "real_status": assembled["real_status"],
        "pseudo_status": assembled["pseudo_status"],
        "real_legitimate": int(assembled["real_status"]["LEGITIMATE"]),
        "pseudo_legitimate": int(assembled["pseudo_status"]["LEGITIMATE"]),
        "geometry_pairs": len(assembled["pairs"]),
        "real_nuisance": len(nuisance),
        "real_weeks": len({int(row["week"]) for row in real}),
        "unresolved_weeks": len(weeks),
        "early_census": census,
        "n_unresolved": census["n_unresolved"],
        "n_early_resolved": census["n_early_resolved"],
        "n_early_ambiguous": census["n_early_ambiguous"],
        "n_unresolved_nuisance": len(unresolved),
        "pair_unresolved_feature_complete": len(both),
        "by_epoch_unresolved": _counts(unresolved, "epoch"),
        "by_family_unresolved": _counts(unresolved, "family"),
        "by_side_unresolved": _counts(unresolved, "side"),
        "by_time_block_unresolved": _counts(unresolved, "time_block"),
        "by_vol_tercile_unresolved": _counts(unresolved, "vol_tercile"),
        "per_feature": per_feature,
        "redundancy": rule,
        "kept_features": kept,
        "scales": scales,
        "scale_hex": {name: scale_hex(scales[name]) for name in scales},
        "information": information(info_n, len(weeks)),
        "oi": oi_meta,
        "oi_jsonl_sha256": oi_meta["oi_jsonl_sha256"],
        "core": {
            "dataset_id": K.CORE_DATASET_ID,
            "zip_list_sha256": K.CORE_ZIP_LIST_SHA256,
            "bars": int(bars.n),
            "t0": int(bars.t0),
        },
        "forbidden_not_used": [
            "funding",
            "long_short_ratio",
            "top_trader",
            "liquidations",
            "order_book",
            "spot",
            "bybit",
            "okx",
            "2025",
            "2026",
            "E1",
            "acceptance_flag",
            "false_break_flag",
            "confirmed_breakout_detector",
            "h02_range_wick",
        ],
        "search_exposure": K.exposure(len(kept)),
    }


def main() -> None:
    bars = load_discovery_bars()
    oi, meta = load_bound_oi()
    if meta["funding_jsonl_opened"] or meta["oi_jsonl_sha256"] != K.OI_JSONL_SHA256:
        raise RuntimeError("OI identity failed")
    if int(meta["last_period_start_ms"]) >= K.SURFACE_END_MS:
        raise RuntimeError("OI series enters 2025")
    payload = _py(summarize(bars, oi, meta))
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "proceed": payload["proceed_to_outcomes"],
        "blocked": payload["blocked_reason"],
        "legitimate": payload["real_legitimate"],
        "unresolved": payload["n_unresolved"],
        "early_resolved": payload["n_early_resolved"],
        "early_ambiguous": payload["n_early_ambiguous"],
        "kept": payload["kept_features"],
        "weeks": payload["unresolved_weeks"],
        "mde": payload["information"].get("rough_80pct_mde"),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
