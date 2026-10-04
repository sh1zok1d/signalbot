"""Calibration executor engine: two irreversible phases.

PHASE CAL : frozen CAL cells only -> replicate rows (V_A, truth) -> build and SEAL the C-table.
SEAL      : immutable artifact + CAL completion record binding its digest.
PHASE EVAL: allowed only if CAL is complete, the sealed C-table exists, its digest matches
            the completion record, and the frozen input digests match. EVAL reads the table;
            it has no writer for it (eval_phase imports load_sealed/factor only).

A synthetic sample is generated ONCE per (cell, seed); A, B, C, D are applied to that
sample. Stage A = first 4000 seeds of the EVAL range; Stage B = the next 16000 (pooled
20000; Stage A is a prefix). Decisions use the frozen 1199/1200 bounds for A/B/C and 0.99
for D. Deterministic resume through the checkpoint; no reruns, no new seeds.

Official execution on frozen cells is REFUSED unless a run-authorization artifact exists
and verifies; none exists. DEV fixtures (CELL_ID prefix "DEV-", seeds < 1e9) are the only
cells this engine will execute without it.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.research.compiler_v3_estimator_calibration import amendment_v3 as A3
from scripts.research.compiler_v3_estimator_calibration import cells as C
from scripts.research.compiler_v3_estimator_calibration import ctable
from scripts.research.compiler_v3_estimator_calibration import estimators as E
from scripts.research.compiler_v3_estimator_calibration import generators as G
from scripts.research.compiler_v3_estimator_calibration.checkpoint import Checkpoint

CAL_DONE_NAME = "CAL_COMPLETION_RECORD.json"
RUN_AUTHORIZATION = C.DOCS / "COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_RUN_AUTHORIZATION_V1.json"
DEV_PREFIX, DEV_SEED_MAX = "DEV-", 10**9
RHO_MAX = 1.5
CANDIDATES = ("A", "B", "C")


class OfficialExecutionRefused(RuntimeError):
    pass


def _guard(cell: dict, seeds: list[int], official: bool) -> None:
    frozen_id = cell["CELL_ID"] in C.frozen_cell_ids()
    if official:
        if not RUN_AUTHORIZATION.exists():
            raise OfficialExecutionRefused("no run authorization artifact exists; official execution refused")
        return
    if frozen_id or not cell["CELL_ID"].startswith(DEV_PREFIX) or any(s >= DEV_SEED_MAX for s in seeds):
        raise OfficialExecutionRefused(f"frozen cell or non-DEV seed refused without run authorization: {cell['CELL_ID']}")


# ----------------------------------------------------------------------------- replicates

def cal_replicate(cell: dict, seed: int) -> dict:
    row = {"PHASE": "CAL", "CLASS": cell["CLASS"], "CELL_ID": cell["CELL_ID"], "SEED": int(seed), "ERROR": None}
    try:
        s = G.generate(cell, seed)
        va, nua = E.naive_variance(s)
        row.update({"V_A": va, "NU_A": nua, "VAR_TRUE_USED": s["VAR_TRUE_USED"],
                    "VAR_TRUE_FROZEN_FORMULA": s["VAR_TRUE_FROZEN_FORMULA"], "TRUTH_MATCHES_FROZEN": s["TRUTH_MATCHES_FROZEN"]})
    except E.CalibrationExecutionError as err:
        row["ERROR"] = f"CALIBRATION_EXECUTION_ERROR: {err}"
    return row


def eval_replicate(cell: dict, seed: int, c_factor: float | None) -> dict:
    row = {"PHASE": "EVAL", "CLASS": cell["CLASS"], "CELL_ID": cell["CELL_ID"], "SEED": int(seed), "ERROR": None}
    try:
        s = G.generate(cell, seed)
        b = E.bounds(s, c_factor)
        t = s["VAR_TRUE_USED"]
        row.update({"VAR_TRUE_USED": t, "VAR_TRUE_FROZEN_FORMULA": s["VAR_TRUE_FROZEN_FORMULA"],
                    "TRUTH_MATCHES_FROZEN": s["TRUTH_MATCHES_FROZEN"], **b})
        for x in ("A", "B", "C", "D"):
            u = b[f"U_{x}"]
            row[f"MISS_{x}"] = None if u is None else bool(t > u)
            row[f"UTIL_{x}"] = None if u is None else bool(u / t <= RHO_MAX)
    except E.CalibrationExecutionError as err:
        row["ERROR"] = f"CALIBRATION_EXECUTION_ERROR: {err}"
    return row


# ----------------------------------------------------------------------------- phases

def executor_digest() -> dict:
    files = ["generators.py", "estimators.py", "cells.py", "ctable.py", "checkpoint.py", "engine.py", "aggregate.py", "amendment_v3.py", "amendment_v2.py"]
    base = Path(__file__).resolve().parent
    per = {f: hashlib.sha256((base / f).read_bytes()).hexdigest() for f in files}
    combined = hashlib.sha256("".join(f"{k}:{v}\n" for k, v in sorted(per.items())).encode()).hexdigest()
    return {"FILES": per, "EXECUTOR_DIGEST": combined}


def run_cal(out_dir: Path, cal_cells: list[dict], cal_n: int = C.CAL_N, official: bool = False) -> Path:
    """Execute missing CAL replicates (resume-safe), then build and seal the C-table."""
    out_dir.mkdir(parents=True, exist_ok=True)
    ck = Checkpoint(out_dir / "replicates.jsonl")
    for cell in cal_cells:
        lo, _ = C.cal_seed_range(cell)
        seeds = list(range(lo, lo + cal_n))
        _guard(cell, seeds, official)
        for seed in seeds:
            if not ck.has("CAL", cell["CELL_ID"], seed):
                ck.record(cal_replicate(cell, seed))
    rows = ck.rows("CAL")
    ck.close()
    table = ctable.build_c_table(rows, cal_cells)
    if official and any(sorted(int(k) for k in table[kl]) != C.CAL_SIZES[kl] for kl in C.CAL_SIZES):
        raise RuntimeError("C-table sizes do not equal the frozen calibrated sizes")
    digests = C.frozen()["DIGESTS"] if official else {"DEV": True}
    path = ctable.seal_c_table(out_dir, table, executor_digest()["EXECUTOR_DIGEST"], digests)
    record = {"PHASE": "CAL", "STATUS": "COMPLETE", "C_TABLE": path.name, "C_TABLE_SHA256": hashlib.sha256(path.read_bytes()).hexdigest(),
              "CAL_ROWS": len(rows), "INPUT_DIGESTS": digests, "EXECUTOR": executor_digest()}
    (out_dir / CAL_DONE_NAME).write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return path


def eval_gate(out_dir: Path, official: bool) -> dict:
    """EVAL preconditions (Protocol owner item 2). Returns the sealed table body."""
    rec_path = out_dir / CAL_DONE_NAME
    if not rec_path.exists():
        raise RuntimeError("EVAL refused: CAL not complete")
    rec = json.loads(rec_path.read_text())
    if rec.get("STATUS") != "COMPLETE":
        raise RuntimeError("EVAL refused: CAL completion record not COMPLETE")
    table = ctable.load_sealed(out_dir, rec["C_TABLE_SHA256"])
    if official:
        if rec["INPUT_DIGESTS"] != C.frozen()["DIGESTS"] or not C.digests_match_amendment():
            raise RuntimeError("EVAL refused: CAL input digests do not match the frozen artifacts")
        if rec["EXECUTOR"]["EXECUTOR_DIGEST"] != executor_digest()["EXECUTOR_DIGEST"]:
            raise RuntimeError("EVAL refused: executor digest changed since CAL")
    return table


def _decide(rows: list[dict], x: str, conf_official: bool = True) -> dict:
    """Coverage and utility decisions for candidate x from the rows of one cell (pooled stage)."""
    n = len(rows)
    errors = [r for r in rows if r["ERROR"]]
    if errors:
        return {"COVERAGE": "CALIBRATION_EXECUTION_ERROR", "UTILITY": "CALIBRATION_EXECUTION_ERROR", "N": n, "ERRORS": len(errors)}
    if any(r[f"MISS_{x}"] is None for r in rows):
        return {"COVERAGE": "NOT_APPLICABLE", "UTILITY": "NOT_APPLICABLE", "N": n, "ERRORS": 0}
    misses = sum(r[f"MISS_{x}"] for r in rows)
    util = sum(r[f"UTIL_{x}"] for r in rows)
    if x == "D":
        conf = 0.99
        cov = "PASS" if A3.cp_upper(misses, n, conf) <= A3.MISS_TARGET else "FAIL" if A3.cp_lower(misses, n, conf) > A3.MISS_UNACCEPTABLE else "ESCALATE"
        ut = "PASS" if A3.cp_lower(util, n, conf) >= A3.UTIL_MIN else "FAIL" if A3.cp_upper(util, n, conf) < A3.UTIL_MIN else "ESCALATE"
    else:
        cov, ut = A3.coverage_decision(misses, n), A3.utility_decision(util, n)
    return {"COVERAGE": cov, "UTILITY": ut, "N": n, "MISSES": misses, "UTIL_SUCCESSES": util, "ERRORS": 0}


def run_eval(out_dir: Path, eval_cells: list[dict], official: bool = False, stage_a: int = C.STAGE_A, stage_b: int = C.STAGE_B) -> list[dict]:
    """Execute EVAL (Stage A, then Stage B where any selectable candidate escalates). Resume-safe."""
    table = eval_gate(out_dir, official)
    ck = Checkpoint(out_dir / "replicates.jsonl")
    results = []
    for cell in eval_cells:
        klass, n = cell["CLASS"], int(cell["N"])
        lo = cell["SEED_RANGE"]["EVAL_STAGE_B"][0]
        c_factor = ctable.factor(table, klass, n)      # None below the smallest calibrated size; support is decided in aggregation
        seeds_a = list(range(lo, lo + stage_a))
        _guard(cell, seeds_a, official)
        for seed in seeds_a:
            if not ck.has("EVAL", cell["CELL_ID"], seed):
                ck.record(eval_replicate(cell, seed, c_factor))
        rows = [r for r in ck.rows("EVAL") if r["CELL_ID"] == cell["CELL_ID"]]
        dec = {x: _decide(rows, x) for x in ("A", "B", "C", "D")}
        escalated = any(dec[x][k] == "ESCALATE" for x in CANDIDATES for k in ("COVERAGE", "UTILITY"))
        if escalated:
            seeds_b = list(range(lo + stage_a, lo + stage_b))
            for seed in seeds_b:
                if not ck.has("EVAL", cell["CELL_ID"], seed):
                    ck.record(eval_replicate(cell, seed, c_factor))
            rows = [r for r in ck.rows("EVAL") if r["CELL_ID"] == cell["CELL_ID"]]
            dec = {x: _decide(rows, x) for x in ("A", "B", "C", "D")}
            for x in dec:
                for k in ("COVERAGE", "UTILITY"):
                    if dec[x][k] == "ESCALATE":
                        dec[x][k] = "CALIBRATION_INDETERMINATE"
        results.append({"CELL_ID": cell["CELL_ID"], "CLASS": klass, "N": n, "LABEL": cell.get("LABEL"), "DECISIVE": cell.get("DECISIVE", False),
                        "C_FACTOR": c_factor, "ESCALATED": escalated, "DECISIONS": dec,
                        "TRUTH_MATCHES_FROZEN": all(r.get("TRUTH_MATCHES_FROZEN", True) for r in rows if not r["ERROR"])})
    ck.close()
    results.sort(key=lambda r: (r["CLASS"], r["CELL_ID"]))
    return results
