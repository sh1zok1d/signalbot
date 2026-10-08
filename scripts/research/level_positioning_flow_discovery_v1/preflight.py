"""Outcome-blind census. Does not classify BREAK, REJECT, or NEITHER."""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

import numpy as np

from scripts.research.level_touch_degradation_v1.data import load_discovery_bars
from scripts.research.owner_cards_r03 import data as RD

from . import constants as K
from .cohort import assemble, column, feature_complete, population
from .inference import freeze_scales, redundancy, scale_hex
from .oi import load_bound_oi

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "research" / "LEVEL_POSITIONING_FLOW_DISCOVERY_V1_PREFLIGHT.json"

PARITY_KEYS = (
    "structural_episodes",
    "real_legitimate",
    "pseudo_legitimate",
    "geometry_pairs",
    "real_nuisance",
    "real_weeks",
    "kept_features",
    "scale_hex",
)


def _dist(values: np.ndarray) -> dict:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return {"n": 0, "missing_rate": 1.0}
    qs = np.quantile(finite, [0.01, 0.05, 0.25, 0.50, 0.75, 0.95, 0.99])
    return {
        "n": int(finite.size),
        "missing_rate": float(1.0 - finite.size / values.size) if values.size else 1.0,
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


def summarize(bars, oi, oi_meta: dict, built: dict | None = None) -> dict:
    built = population(bars) if built is None else built
    assembled = assemble(bars, oi, built)
    real = assembled["real_rows"]
    nuisance = [row for row in real if row["nuisance_ok"]]
    rule = redundancy(nuisance)
    kept = rule["kept"]
    scales = {}
    for name in kept:
        support = [row for row in nuisance if feature_complete(row, (name,))]
        scales[name] = freeze_scales(support, [name])[name]
    scales["disp"] = freeze_scales(nuisance, [])["disp"]
    scales["rel_volume"] = freeze_scales(nuisance, [])["rel_volume"]
    both = []
    for pair in assembled["pairs"]:
        if feature_complete(pair["real"], kept) and feature_complete(pair["pseudo"], kept):
            both.append(pair["episode_id"])
    per_feature = {}
    for name in K.RAW_FEATURES:
        per_feature[name] = {
            "real_complete": sum(1 for row in real if feature_complete(row, (name,))),
            "pair_both_complete": sum(
                1 for pair in assembled["pairs"]
                if feature_complete(pair["real"], (name,)) and feature_complete(pair["pseudo"], (name,))
            ),
            "distribution": _dist(column(nuisance, name)),
        }
    align_rows = [row for row in nuisance if feature_complete(row, ("OI_CHANGE_60M", "ORIENTED_TAKER_IMBALANCE_60M"))]
    same = opposite = 0
    for row in align_rows:
        product = float(row["OI_CHANGE_60M"]) * float(row["ORIENTED_TAKER_IMBALANCE_60M"])
        if product > 0:
            same += 1
        elif product < 0:
            opposite += 1
    digest = RD.btc_dataset_digest()
    if digest != K.CORE_ZIP_LIST_SHA256:
        raise RuntimeError("CORE zip-list digest drifted")
    opens = [int(row["open_ms"]) for row in real]
    body = {
        "unit": K.UNIT,
        "mode": K.MODE,
        "outcome_blind": True,
        "proceed_to_outcomes": True,
        "core": {
            "dataset_id": K.CORE_DATASET_ID,
            "zip_list_sha256": digest,
            "bars": int(bars.n),
            "t0": int(bars.t0),
            "end_ms": int(bars.end_ms),
        },
        "oi": oi_meta,
        "event_window": {"start": K.EVENT_START, "end_exclusive": K.EVENT_END},
        "structural_episodes": assembled["structural_episodes"],
        "controls_built": assembled["controls_built"],
        "real_status": assembled["real_status"],
        "pseudo_status": assembled["pseudo_status"],
        "real_legitimate": assembled["real_status"]["LEGITIMATE"],
        "pseudo_legitimate": assembled["pseudo_status"]["LEGITIMATE"],
        "geometry_pairs": len(assembled["pairs"]),
        "real_nuisance": len(nuisance),
        "real_weeks": len({int(row["week"]) for row in nuisance}),
        "observed_first_open_ms": None if not opens else min(opens),
        "observed_last_open_ms": None if not opens else max(opens),
        "oi_complete_60m": sum(1 for row in real if row["oi_complete_60m"]),
        "taker_complete_60m": sum(1 for row in real if row["taker_complete_60m"]),
        "taker_complete_15m": sum(1 for row in real if row["taker_complete_15m"]),
        "per_feature": per_feature,
        "alignment": {"n": len(align_rows), "same_sign": same, "opposite_sign": opposite},
        "by_epoch": _counts(nuisance, "epoch"),
        "by_family": _counts(nuisance, "family"),
        "by_side": _counts(nuisance, "side"),
        "by_time_block": _counts(nuisance, "time_block"),
        "by_vol_tercile": _counts(nuisance, "vol_tercile"),
        "redundancy": rule,
        "kept_features": kept,
        "scales": scales,
        "scale_hex": {name: scale_hex(scales[name]) for name in list(kept) + ["disp", "rel_volume"]},
        "pair_all_retained_complete": len(both),
        "search_exposure_if_kept": K.exposure(len(kept)),
        "funding_jsonl_opened": False,
        "forbidden_not_used": [
            "funding", "long_short_ratio", "top_trader_ratio", "premium", "mark_price",
            "liquidations", "order_book", "2025", "2026", "E1",
        ],
    }
    # Constant-column guard, still outcome-blind.
    for name, rows in (
        ("fam_week", [row for row in nuisance if row["family"] == "WEEK"]),
        ("fam_month", [row for row in nuisance if row["family"] == "MONTH"]),
        ("support", [row for row in nuisance if row["support"] == 1.0]),
        ("resistance", [row for row in nuisance if row["support"] == 0.0]),
    ):
        if not rows:
            body["proceed_to_outcomes"] = False
            body["blocked_reason"] = f"nuisance level {name} is empty"
    for dummy, block in (("tb1", 1), ("tb2", 2), ("tb3", 3), ("tb0", 0)):
        if not any(int(row["time_block"]) == block for row in nuisance):
            body["proceed_to_outcomes"] = False
            body["blocked_reason"] = f"time block {dummy} is empty"
    for year in (2020, 2021, 2022, 2023, 2024):
        if not any(int(row["year"]) == year for row in nuisance):
            body["proceed_to_outcomes"] = False
            body["blocked_reason"] = f"year {year} is empty"
    for tercile in (0, 1, 2):
        if not any(row["vol_tercile"] == tercile for row in nuisance):
            body["proceed_to_outcomes"] = False
            body["blocked_reason"] = f"vol tercile {tercile} is empty"
    for name in ("disp", "rel_volume"):
        sd = scales[name]["sd"]
        if sd is None or not math.isfinite(sd) or sd <= 0.0:
            body["proceed_to_outcomes"] = False
            body["blocked_reason"] = f"{name} has no variation"
    return body


def _py(value):
    if isinstance(value, dict):
        return {str(k): _py(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_py(v) for v in value]
    if isinstance(value, (np.floating, float)):
        return None if not math.isfinite(float(value)) else float(value)
    if isinstance(value, (np.integer, int)) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    return value


def main() -> None:
    bars = load_discovery_bars()
    oi, meta = load_bound_oi()
    body = _py(summarize(bars, oi, meta))
    OUT.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n")
    print(f"wrote {OUT}")
    print(json.dumps({
        "real_legitimate": body["real_legitimate"],
        "real_nuisance": body["real_nuisance"],
        "geometry_pairs": body["geometry_pairs"],
        "kept_features": body["kept_features"],
        "proceed": body["proceed_to_outcomes"],
        "oi_sha": body["oi"]["oi_jsonl_sha256"],
        "funding_opened": body["funding_jsonl_opened"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
