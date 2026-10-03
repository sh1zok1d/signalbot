"""Count-only C025-R1 support audit and GV0R02 V2 compile.

This module does not import outcomes.py and does not compute a post-T target.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from . import planning as planning_mod
from .constants import (
    MONTE_CARLO_P_FLOOR,
    PLACEBO_MAX_PER_STRATUM,
    PRIMARY_ALPHA,
    assert_locked_primary,
)
from .data import dataset_identity, load_panel
from .events import detect_primary, placebo_candidate_indices
from .matching import choose_matching, count_by_year_arm, distinct_event_days

REPO = Path(__file__).resolve().parents[3]


def _jsonable(value):
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, np.ndarray):
        return _jsonable(value.tolist())
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        if not np.isfinite(value):
            return None
        return float(value)
    if isinstance(value, float) and value != value:
        return None
    return value


def effective_n(active: int, inactive: int) -> float | None:
    if active <= 0 or inactive <= 0:
        return None
    return (active * inactive) / (active + inactive)


def run_support(panel: dict | None = None) -> dict:
    """Count-only pass. `panel` is injectable for tests; the market path loads pins."""
    assert_locked_primary()
    own_panel = panel is None
    if own_panel:
        panel = load_panel()
    found = detect_primary(panel)
    events = found["events"]
    match = choose_matching(events)
    usable = match["USABLE"]
    admitted_year = {}
    for year in (2020, 2021, 2022, 2023, 2024):
        member = events["year"] == year
        admitted_year[str(year)] = {
            "ONE_SIDED": int(np.sum(member & (events["arm"] == 1))),
            "TWO_SIDED": int(np.sum(member & (events["arm"] == 0))),
        }
    pre_edges = match.get("EDGES", {}).get("pre_decile", [])
    rv_edges = match.get("EDGES", {}).get("rv", [])
    placebo_idx = np.zeros(0, dtype=np.int64)
    if pre_edges and rv_edges and own_panel:
        placebo_idx = placebo_candidate_indices(
            panel["open_ms"], found["burst"], found["pre_impact"], found["prior_rv"],
            pre_edges, rv_edges, PLACEBO_MAX_PER_STRATUM,
        )
    orbit = int(match["PRIMARY_LABEL_ORBIT_SIZE"])
    one = int(match["MATCHABLE_ONE_SIDED_N"])
    two = int(match["MATCHABLE_TWO_SIDED_N"])
    if one <= 0 or two <= 0 or orbit <= 1:
        min_p = 1.0
    elif orbit > 10_000:
        min_p = MONTE_CARLO_P_FLOOR
    else:
        min_p = 1.0 / float(orbit)
    identity = dataset_identity() if own_panel else {"DATASET_ID": "SYNTHETIC", "PROTECTED_2025_2026_SELECTED": False}
    summary = {
        "TOTAL_MINUTES": found["summary"]["TOTAL_MINUTES"],
        "RAW_BURSTS": found["summary"]["RAW_BURSTS"],
        "DECLUSTERED_BURSTS": found["summary"]["DECLUSTERED_BURSTS"],
        "ONE_SIDED_N": found["summary"]["ONE_SIDED_N"],
        "TWO_SIDED_N": found["summary"]["TWO_SIDED_N"],
        "NEITHER_N": found["summary"]["NEITHER_N"],
        "ARM_ELIGIBLE_BEFORE_DECLUSTER": found["summary"]["ARM_ELIGIBLE_BEFORE_DECLUSTER"],
        "REFRACTORY_REJECTED": found["summary"]["REFRACTORY_REJECTED"],
        "MATCHABLE_ONE_SIDED_N": one,
        "MATCHABLE_TWO_SIDED_N": two,
        "COUNT_BY_YEAR_ARM": count_by_year_arm(events, usable),
        "ADMITTED_COUNT_BY_YEAR_ARM": admitted_year,
        "DISTINCT_EVENT_DAYS": distinct_event_days(events["open_ms"], usable if usable.size else np.zeros(0, dtype=bool)),
        "ADMITTED_DISTINCT_DAYS": distinct_event_days(events["open_ms"], np.ones(events["arm"].shape[0], dtype=bool)),
        "MATCHED_STRATA_N": int(match["MATCHED_STRATA_N"]),
        "PRIMARY_LABEL_ORBIT_SIZE": str(orbit),
        "MIN_ATTAINABLE_P": min_p,
        "ALPHA_ATTAINABLE": bool(min_p <= PRIMARY_ALPHA),
        "EFFECTIVE_N": effective_n(one, two),
        "MATCHING_STATUS": match["STATUS"],
        "MATCHING_LEVEL": match["LEVEL"],
        "MATCHING_REASON": match["REASON"],
        "RETENTION_ONE": match.get("RETENTION_ONE"),
        "RETENTION_TWO": match.get("RETENTION_TWO"),
        "MAX_ABS_SMD": match.get("MAX_ABS_SMD"),
        "SMD": match.get("SMD"),
        "LEVELS_TRIED": match.get("LEVELS_TRIED"),
        "EDGES": match.get("EDGES"),
        "APPLIED_EDGES": match.get("APPLIED_EDGES"),
        "LEVEL_SPEC": match.get("LEVEL_SPEC"),
        "PLACEBO_CANDIDATE_N": int(placebo_idx.size),
        "DATASET": identity,
        "POST_T_TARGET_COMPUTED": False,
        "MARKET_OUTCOMES_OPENED": False,
    }
    summary["MATCHING"] = {
        "STATUS": match["STATUS"],
        "LEVEL": match["LEVEL"],
        "MATCHABLE_ONE_SIDED_N": one,
        "MATCHABLE_TWO_SIDED_N": two,
        "MATCHED_STRATA_N": int(match["MATCHED_STRATA_N"]),
        "PRIMARY_LABEL_ORBIT_SIZE": orbit,
        "REASON": match["REASON"],
    }
    return _jsonable(summary)


def compile_support(support: dict) -> tuple[dict, dict]:
    plan = planning_mod.build_planning(support)
    compiled = planning_mod.compile_planning(plan)
    return plan, compiled


def public_status(support: dict, compiled: dict) -> str:
    if support["MATCHING_STATUS"] != "MATCHING_FROZEN":
        return "INFERENCE_SUPPORT_INSUFFICIENT"
    return compiled["FEASIBILITY_STATUS"]


def main() -> None:
    assert_locked_primary()
    support = run_support()
    plan, compiled = compile_support(support)
    status = public_status(support, compiled)
    payload = {
        "SUPPORT": support,
        "PLANNING": plan,
        "FEASIBILITY": compiled,
        "FEASIBILITY_STATUS": status,
        "POST_T_TARGET_COMPUTED": False,
    }
    out = REPO / "docs/research/GV0V03L40_C025_R1_SUPPORT.json"
    out.write_text(json.dumps(_jsonable(payload["SUPPORT"]), indent=2, sort_keys=True) + "\n")
    (REPO / "docs/research/GV0V03L40_C025_R1_PLANNING.json").write_text(
        json.dumps(_jsonable(plan), indent=2, sort_keys=True) + "\n"
    )
    (REPO / "docs/research/GV0V03L40_C025_R1_FEASIBILITY.json").write_text(
        json.dumps(_jsonable(compiled), indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps({
        "FEASIBILITY_STATUS": status,
        "COMPILER_STATUS": compiled["FEASIBILITY_STATUS"],
        "MATCHING_STATUS": support["MATCHING_STATUS"],
        "MATCHING_LEVEL": support["MATCHING_LEVEL"],
        "RAW_BURSTS": support["RAW_BURSTS"],
        "DECLUSTERED_BURSTS": support["DECLUSTERED_BURSTS"],
        "ONE_SIDED_N": support["ONE_SIDED_N"],
        "TWO_SIDED_N": support["TWO_SIDED_N"],
        "NEITHER_N": support["NEITHER_N"],
        "MATCHABLE_ONE_SIDED_N": support["MATCHABLE_ONE_SIDED_N"],
        "MATCHABLE_TWO_SIDED_N": support["MATCHABLE_TWO_SIDED_N"],
        "MATCHED_STRATA_N": support["MATCHED_STRATA_N"],
        "EFFECTIVE_N": support["EFFECTIVE_N"],
        "MIN_ATTAINABLE_P": support["MIN_ATTAINABLE_P"],
        "ALPHA_ATTAINABLE": support["ALPHA_ATTAINABLE"],
        "BLOCKERS": [b["BLOCKER_CODE"] for b in compiled["BLOCKERS"]],
        "DISCOVERY_SCREEN": compiled.get("DISCOVERY_SCREEN"),
        "POST_T_TARGET_COMPUTED": False,
    }, indent=2, default=str))


if __name__ == "__main__":
    main()
