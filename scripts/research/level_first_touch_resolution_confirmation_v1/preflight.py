"""Outcome-blind census of the BitMEX first-touch cohort. Does not classify barriers."""

from __future__ import annotations

import json
from pathlib import Path

from . import cohort, constants as K, data, inference

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "research" / "LEVEL_FIRST_TOUCH_RESOLUTION_CONFIRMATION_V1_PREFLIGHT.json"

PARITY_KEYS = (
    "structural_episodes",
    "controls_built",
    "real_legitimate",
    "pseudo_legitimate",
    "matched_pairs",
    "missing_real",
    "missing_pseudo",
    "incomplete_4h_real",
    "incomplete_4h_pseudo",
    "weeks",
    "by_epoch",
    "by_family",
    "by_real_side",
    "outside_epoch",
)


def _py(value):
    if isinstance(value, dict):
        return {str(k): _py(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_py(v) for v in value]
    if hasattr(value, "item") and not isinstance(value, (bytes, str)):
        try:
            return value.item()
        except Exception:
            return value
    return value


def build_preflight(bars, identity: dict) -> dict:
    audit = cohort.period_audit(bars)
    pop = cohort.population(bars)
    counted = cohort.census(pop)
    pairs = counted.pop("pairs")
    sigmas = [p["real_sigma"] for p in pairs]
    edges = inference.tercile_edges(sigmas)
    columns = inference.select_adjusted_columns(pairs, edges)
    real_status = counted["real_status"]
    pseudo_status = counted["pseudo_status"]
    body = {
        "unit": K.UNIT,
        "mode": K.MODE,
        "exposure_status": K.EXPOSURE_STATUS,
        "dataset": identity,
        "event_window": [K.EVENT_START, K.EVENT_END],
        "data_window": [K.DATA_START, K.EVENT_END],
        "zone_half": K.ZONE_HALF,
        "period_audit": audit,
        "structural_episodes": counted["structural_episodes"],
        "controls_built": counted["controls_built"],
        "real_first_touches": counted["structural_episodes"] - real_status["NO_TOUCH"],
        "pseudo_first_touches": counted["controls_built"] - pseudo_status["NO_TOUCH"],
        "real_status": real_status,
        "pseudo_status": pseudo_status,
        "real_legitimate": counted["real_legitimate"],
        "pseudo_legitimate": counted["pseudo_legitimate"],
        "matched_pairs": counted["matched_pairs"],
        "missing_real": counted["missing_real"],
        "missing_pseudo": counted["missing_pseudo"],
        "incomplete_4h_real": counted["incomplete_4h_real"],
        "incomplete_4h_pseudo": counted["incomplete_4h_pseudo"],
        "weeks": counted["weeks"],
        "by_epoch": counted["by_epoch"],
        "by_family": counted["by_family"],
        "by_real_side": counted["by_real_side"],
        "outside_epoch": counted["outside_epoch"],
        "sigma_tercile_edges": [edges[0], edges[1]],
        "sigma_tercile_edges_hex": [float(edges[0]).hex(), float(edges[1]).hex()],
        "adjusted_columns": columns["columns"],
        "adjusted_dropped_share": columns["dropped_share"],
        "adjusted_dropped_rank": columns["dropped_rank"],
        "run_floor": K.RUN_FLOOR,
        "proceed_to_outcomes": bool(counted["matched_pairs"] >= K.RUN_FLOOR and counted["outside_epoch"] == 0),
        "blocked_reason": None,
        "outcomes_read": False,
        "ambiguous_counts": "left_to_execution",
    }
    if counted["outside_epoch"]:
        body["proceed_to_outcomes"] = False
        body["blocked_reason"] = "matched touch outside 2017H2/2018/2019"
    elif counted["matched_pairs"] < K.RUN_FLOOR:
        body["proceed_to_outcomes"] = False
        body["blocked_reason"] = (
            f"matched pairs {counted['matched_pairs']} below the predeclared floor {K.RUN_FLOOR}"
        )
    if audit["DAY"]["first_bars"] != 288 or audit["MONTH"]["first_bars"] != 31 * 288:
        body["proceed_to_outcomes"] = False
        body["blocked_reason"] = "the grid is not aligned to a full August 2017"
    return _py(body)


def parity_view(body: dict) -> dict:
    return {key: body[key] for key in PARITY_KEYS}


def main() -> None:
    bars, identity = data.load_confirmation_bars()
    body = build_preflight(bars, identity)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "wrote": str(OUT),
        "structural_episodes": body["structural_episodes"],
        "real_first_touches": body["real_first_touches"],
        "pseudo_first_touches": body["pseudo_first_touches"],
        "real_legitimate": body["real_legitimate"],
        "pseudo_legitimate": body["pseudo_legitimate"],
        "matched_pairs": body["matched_pairs"],
        "missing_real": body["missing_real"],
        "missing_pseudo": body["missing_pseudo"],
        "incomplete_4h_real": body["incomplete_4h_real"],
        "incomplete_4h_pseudo": body["incomplete_4h_pseudo"],
        "weeks": body["weeks"],
        "by_epoch": body["by_epoch"],
        "by_family": body["by_family"],
        "by_real_side": body["by_real_side"],
        "finite_frac": body["period_audit"]["finite_frac"],
        "month_first_full": body["period_audit"]["MONTH"]["first_full"],
        "month_first_bars": body["period_audit"]["MONTH"]["first_bars"],
        "month_first_frac": body["period_audit"]["MONTH"]["first_frac"],
        "proceed_to_outcomes": body["proceed_to_outcomes"],
        "blocked_reason": body["blocked_reason"],
        "adjusted_columns": body["adjusted_columns"],
    }, indent=2))


if __name__ == "__main__":
    main()
