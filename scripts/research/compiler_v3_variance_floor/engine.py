"""Monte Carlo engine, per-cell results, suite aggregation and the frozen state machine.

Frozen rules implemented literally (spec §4, §6):
- Stage A = exactly the manifest's STAGE_A seeds; Stage B = pooled STAGE_B seeds, Stage A a prefix;
- escalation only by the Clopper-Pearson rule; no rerun, no seed replacement, no retry;
- a replicate error freezes the cell in an execution-error state;
- evaluation outcomes are simulated once per cell and shared by every candidate (common random
  numbers); the candidate floor touches only the compiler's planning side.

An official run needs the execution binding (freeze.verify_execution_binding) with
OFFICIAL_RUN_AUTHORIZED = true; otherwise only developer fixtures (CELL_ID prefix "DEV-") may run.
"""

from __future__ import annotations

import datetime as dt
import json
import traceback
from pathlib import Path

from . import compiler, cp, freeze, generator

REPO = Path(__file__).resolve().parents[3]
RESULT_OUT = REPO / "docs/research/COMPILER_V3_VARIANCE_FLOOR_VALIDATION_RESULT.json"
AGG_OUT = REPO / "docs/research/COMPILER_V3_VARIANCE_FLOOR_VALIDATION_AGGREGATION.json"
DEV_PREFIX = "DEV-"
CHECK_SPEC = {  # CHECK field of a cell -> (kind, threshold rule)
    "SIZE<=ALPHA+0.01": ("AT_MOST", lambda cell: cell["MULTIPLICITY_ALPHA"] + 0.01),
    "POWER>=0.75_IF_FEASIBLE": ("AT_LEAST", lambda cell: 0.75),
    "POWER>=0.95_IF_FEASIBLE": ("AT_LEAST", lambda cell: 0.95),
}


class OfficialRunNotAuthorized(RuntimeError):
    pass


def _seeds(cell: dict, stage: str) -> range:
    lo, hi = cell["SEED_RANGE"][stage]
    return range(lo, hi + 1)


def simulate_cell(cell: dict, constants: dict) -> dict:
    """Stage A, then Stage B only if the frozen rule escalates. Candidate-independent."""
    kind, thr = CHECK_SPEC[cell["CHECK"]]
    threshold = thr(cell)
    out = {"CELL_ID": cell["CELL_ID"], "CHECK": cell["CHECK"], "THRESHOLD": threshold, "ERROR": None,
           "STAGE_A": None, "ESCALATED": False, "STAGE_B": None, "DECISION": None}
    try:
        a_seeds = _seeds(cell, "STAGE_A")
        if len(a_seeds) != constants["STAGE_A"]:
            raise RuntimeError("Stage A seed range length differs from the frozen STAGE_A")
        rejections = 0
        for s in a_seeds:
            rejections += generator.replicate(cell, s)
        n_a = len(a_seeds)
        dec_a = cp.stage_decision(kind, rejections, n_a, threshold)
        out["STAGE_A"] = {"N": n_a, "REJECTIONS": rejections, "RATE": rejections / n_a,
                          "CP_LOWER_99": cp.cp_lower(rejections, n_a), "CP_UPPER_99": cp.cp_upper(rejections, n_a),
                          "DECISION": dec_a}
        dec_b = None
        if dec_a == cp.ESCALATE:
            out["ESCALATED"] = True
            b_seeds = _seeds(cell, "STAGE_B")
            if len(b_seeds) != constants["STAGE_B"] or b_seeds[0] != a_seeds[0] or b_seeds[-1] < a_seeds[-1]:
                raise RuntimeError("Stage B seed range is not the frozen superset of Stage A")
            extra = range(a_seeds[-1] + 1, b_seeds[-1] + 1)
            pooled = rejections + sum(generator.replicate(cell, s) for s in extra)
            n_b = len(b_seeds)
            dec_b = cp.stage_decision(kind, pooled, n_b, threshold)
            out["STAGE_B"] = {"N": n_b, "REJECTIONS": pooled, "RATE": pooled / n_b,
                              "CP_LOWER_99": cp.cp_lower(pooled, n_b), "CP_UPPER_99": cp.cp_upper(pooled, n_b),
                              "DECISION": dec_b}
        out["DECISION"] = cp.final_decision(dec_a, dec_b)
    except generator.FrozenSpecContradiction as exc:
        out["ERROR"] = {"STATE": "BLOCKED_FROZEN_SPEC_CONTRADICTION", "DETAIL": str(exc)}
        out["DECISION"] = "EXECUTION_ERROR"
    except Exception as exc:  # noqa: BLE001 - frozen execution-error state, never a retry
        out["ERROR"] = {"STATE": "EXECUTION_ERROR", "DETAIL": f"{type(exc).__name__}: {exc}",
                        "TRACE": traceback.format_exc(limit=3)}
        out["DECISION"] = "EXECUTION_ERROR"
    return out


def candidate_rows(cell: dict, sim: dict, candidates: list[float], digests: dict) -> list[dict]:
    """One row per candidate. Safety applies only when the compiler declares FEASIBLE."""
    rows = []
    for f in candidates:
        feas = compiler.feasibility(cell, f)
        expected = cell["EXPECTED_CLASSIFICATION"]
        utility = None
        if expected == "MUST_BE_FEASIBLE":
            utility = "PASS" if feas["VERDICT"] == compiler.FEASIBLE else "FAIL"
        false_feasible = expected == "MUST_NOT_BE_FEASIBLE" and feas["VERDICT"] == compiler.FEASIBLE
        if feas["VERDICT"] == compiler.FEASIBLE:
            safety = "FAIL" if false_feasible else sim["DECISION"]
        else:
            safety = "NOT_APPLICABLE_NOT_FEASIBLE"
        rows.append({
            "CELL_ID": cell["CELL_ID"], "DESIGN_ID": cell["DESIGN_ID"], "GRID": cell["GRID"], "ROLE": cell["ROLE"],
            "CANDIDATE_FLOOR": f, "DIGESTS": digests, "FEASIBILITY": feas,
            "EXPECTED_CLASSIFICATION": expected, "CHECK": cell["CHECK"],
            "STAGE_A": sim["STAGE_A"], "ESCALATED": sim["ESCALATED"], "STAGE_B": sim["STAGE_B"],
            "EMPIRICAL_DECISION": sim["DECISION"], "SAFETY": safety, "UTILITY": utility,
            "FALSE_FEASIBLE": false_feasible, "ERROR": sim["ERROR"],
        })
    return rows


def _status_from(decisions: list[str]) -> str:
    if any(d in ("FAIL", "EXECUTION_ERROR") for d in decisions):
        return "FAIL"
    if any(d == cp.INDETERMINATE for d in decisions):
        return "INDETERMINATE"
    return "PASS"


def aggregate(rows: list[dict], candidates: list[float]) -> dict:
    """Spec §4 selection on 3A only, §3B stress gate at the candidate, final state machine."""
    status_3a, detail = {}, {}
    for f in candidates:
        decisive = []
        for r in rows:
            if r["GRID"] != "3A" or r["CANDIDATE_FLOOR"] != f:
                continue
            if r["FEASIBILITY"]["VERDICT"] == compiler.FEASIBLE:
                decisive.append(r["SAFETY"])                 # safety on actual FEASIBLE, every 3A cell
            if r["UTILITY"] is not None:
                decisive.append(r["UTILITY"])                # utility on MUST_BE_FEASIBLE
        status_3a[f] = _status_from(decisive) if decisive else "INDETERMINATE"
        detail[f] = {"DECISIVE_CHECKS": len(decisive), "FAIL": decisive.count("FAIL"),
                     "INDETERMINATE": decisive.count(cp.INDETERMINATE)}
    passing = [f for f in sorted(candidates) if status_3a[f] == "PASS"]
    out = {"STATUS_3A": {str(f): status_3a[f] for f in candidates}, "DETAIL_3A": {str(f): detail[f] for f in candidates},
           "ADOPTED_FLOOR_CANDIDATE": None, "STRESS_3B": None, "FINAL": None}
    if not passing:
        out["FINAL"] = ("VALIDATION_INDETERMINATE" if any(s == "INDETERMINATE" for s in status_3a.values())
                        else "VARIANCE_MODEL_REDESIGN_REQUIRED")
        return out
    f_sel = passing[0]
    out["ADOPTED_FLOOR_CANDIDATE"] = f_sel
    stress = [r["SAFETY"] for r in rows if r["GRID"] == "3B" and r["CANDIDATE_FLOOR"] == f_sel
              and r["FEASIBILITY"]["VERDICT"] == compiler.FEASIBLE]
    s = _status_from(stress) if stress else "PASS"
    out["STRESS_3B"] = {"CANDIDATE": f_sel, "FEASIBLE_CELLS": len(stress), "STATUS": s}
    out["FINAL"] = {"FAIL": "ADOPTION_BLOCKED_BY_STRESS", "INDETERMINATE": "STRESS_VALIDATION_INDETERMINATE",
                    "PASS": "VALIDATION_PASS"}[s]
    if out["FINAL"] == "VALIDATION_PASS":
        out["ADOPTED_FLOOR"] = f_sel
    return out


def run_cells(cells: list[dict], constants: dict, candidates: list[float], digests: dict) -> list[dict]:
    rows = []
    for cell in cells:
        sim = simulate_cell(cell, constants)
        rows.extend(candidate_rows(cell, sim, candidates, digests))
    return rows


def official_run() -> dict:
    """The one official run. Refuses without the execution binding and its authorization flag."""
    record = freeze.verify_freeze()
    binding = freeze.verify_execution_binding()
    if binding.get("OFFICIAL_RUN_AUTHORIZED") is not True:
        raise OfficialRunNotAuthorized("OFFICIAL_RUN_AUTHORIZED is not true in the execution binding")
    if RESULT_OUT.exists():
        raise OfficialRunNotAuthorized("a result already exists; the official run is one-shot")
    manifest = freeze.load_manifest()
    digests = {"SPEC": record["ARTIFACTS"][str(freeze.SPEC.relative_to(REPO))],
               "MANIFEST": record["ARTIFACTS"][str(freeze.MANIFEST.relative_to(REPO))],
               "GENERATOR": binding["GENERATOR_DIGESTS"]}
    rows = run_cells(manifest["CELLS"], manifest["CONSTANTS"], manifest["CANDIDATE_FLOORS"], digests)
    agg = aggregate(rows, manifest["CANDIDATE_FLOORS"])
    payload = {"RUN": "COMPILER_V3_VARIANCE_FLOOR_VALIDATION", "AT_UTC": dt.datetime.now(tz=dt.timezone.utc).isoformat(),
               "DIGESTS": digests, "ROWS": rows}
    RESULT_OUT.write_text(json.dumps(payload, indent=1) + "\n")
    AGG_OUT.write_text(json.dumps({"DIGESTS": digests, **agg}, indent=1) + "\n")
    return agg


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--official", action="store_true", help="run the frozen suite once (needs the execution binding)")
    args = ap.parse_args()
    if not args.official:
        print("nothing to do: the frozen suite runs only with --official and an authorized execution binding")
        return
    print(json.dumps(official_run(), indent=1))


if __name__ == "__main__":
    main()
