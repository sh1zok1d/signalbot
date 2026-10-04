"""Calibration executor engine (amendment V4): two irreversible phases.

PHASE CAL : frozen CAL cells only -> slim rows (V_A, truth) -> build and SEAL the C-table.
SEAL      : immutable artifact + CAL completion record binding its digest.
PHASE EVAL: allowed only if CAL is complete, the sealed C-table exists, its digest matches
            the completion record, and the frozen input digests match. EVAL has no writer
            for the table (eval functions call neither seal_c_table nor build_c_table).

One synthetic sample per (cell, seed); A, B, C, D are applied to that sample. Rows are SLIM
(V4 D6): P, C, S, VA, [VB], T, E. Bounds, misses and utility are recomputed deterministically
from the slim row, the cell and the sealed factor. Stage A = first 4000 seeds; Stage B = the
next 16000 (pooled 20000). Per-check lock (V4 D3): a Stage-A PASS or FAIL of
(CELL_ID, CANDIDATE, METRIC) is final; only checks whose Stage-A state is ESCALATE are decided
on the pooled Stage-B rows; Stage-B rows are generated once per cell and shared.

Official execution on frozen cells is REFUSED unless a run-authorization artifact exists; none
exists. DEV fixtures (CELL_ID prefix "DEV-", seeds < 1e9) are the only cells executed without it.
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
METRICS = ("COVERAGE", "UTILITY")


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


# ----------------------------------------------------------------------------- slim replicate rows (V4 D6)

def cal_replicate(cell: dict, seed: int) -> dict:
    row = {"P": "CAL", "C": cell["CELL_ID"], "S": int(seed), "VA": None, "T": None, "E": None}
    try:
        s = G.generate(cell, seed)
        va, _ = E.naive_variance(s)
        row.update({"VA": va, "T": s["VAR_TRUE"]})
    except E.CalibrationExecutionError as err:
        row["E"] = f"CALIBRATION_EXECUTION_ERROR: {err}"
    return row


def eval_replicate(cell: dict, seed: int) -> dict:
    row = {"P": "EVAL", "C": cell["CELL_ID"], "S": int(seed), "VA": None, "VB": None, "T": None, "E": None}
    try:
        s = G.generate(cell, seed)
        va, _ = E.naive_variance(s)
        row["VA"], row["T"] = va, s["VAR_TRUE"]
        vb, _ = E.long_run_variance(s)
        row["VB"] = vb
    except E.CalibrationExecutionError as err:
        row["E"] = f"CALIBRATION_EXECUTION_ERROR: {err}"
    return row


def nu_of(cell: dict) -> tuple[int, int]:
    n = int(cell["N"])
    if cell["CLASS"] == "TWO_SAMPLE":
        return 2 * n - 2, 2 * (n // (E.bandwidth(n) + 1) - 1)
    return n - 1, n // (E.bandwidth(n) + 1) - 1


def derive(row: dict, cell: dict, c_factor: float | None) -> dict:
    """Recompute bounds, misses and utility flags from a slim EVAL row (deterministic, no RNG)."""
    if row["E"]:
        return {"ERROR": row["E"]}
    nua, nub = nu_of(cell)
    t = row["T"]
    u = {"A": E.chi2_bound(row["VA"], nua), "B": E.chi2_bound(row["VB"], nub),
         "C": None if c_factor is None else row["VA"] * c_factor, "D": E.VAR_FALLBACK}
    out = {"ERROR": None}
    for x, ux in u.items():
        out[f"MISS_{x}"] = None if ux is None else bool(t > ux)
        out[f"UTIL_{x}"] = None if ux is None else bool(ux / t <= RHO_MAX)
    return out


# ----------------------------------------------------------------------------- decisions (V4 D3 per-check lock)

def _decide_rows(derived: list[dict], x: str) -> dict:
    n = len(derived)
    errors = sum(1 for d in derived if d["ERROR"])
    if errors:
        return {"COVERAGE": "CALIBRATION_EXECUTION_ERROR", "UTILITY": "CALIBRATION_EXECUTION_ERROR", "N": n, "ERRORS": errors}
    if any(d[f"MISS_{x}"] is None for d in derived):
        return {"COVERAGE": "NOT_APPLICABLE", "UTILITY": "NOT_APPLICABLE", "N": n, "ERRORS": 0}
    misses = sum(d[f"MISS_{x}"] for d in derived)
    util = sum(d[f"UTIL_{x}"] for d in derived)
    if x == "D":
        conf = 0.99
        cov = "PASS" if A3.cp_upper(misses, n, conf) <= A3.MISS_TARGET else "FAIL" if A3.cp_lower(misses, n, conf) > A3.MISS_UNACCEPTABLE else "ESCALATE"
        ut = "PASS" if A3.cp_lower(util, n, conf) >= A3.UTIL_MIN else "FAIL" if A3.cp_upper(util, n, conf) < A3.UTIL_MIN else "ESCALATE"
    else:
        cov, ut = A3.coverage_decision(misses, n), A3.utility_decision(util, n)
    return {"COVERAGE": cov, "UTILITY": ut, "N": n, "MISSES": misses, "UTIL_SUCCESSES": util, "ERRORS": 0}


def decide_cell(stage_a: list[dict], stage_b: list[dict] | None) -> dict:
    """Per (candidate, metric): Stage-A PASS/FAIL is final; ESCALATE is decided on the pooled
    Stage-A + Stage-B rows; a residual ESCALATE after Stage B is CALIBRATION_INDETERMINATE.
    stage_a / stage_b are derived rows. Returns {candidate: {metric: {STAGE_A, STAGE_B, FINAL, DECIDED_AT}}}."""
    out = {}
    pooled = None if stage_b is None else stage_a + stage_b
    for x in ("A", "B", "C", "D"):
        da = _decide_rows(stage_a, x)
        db = _decide_rows(pooled, x) if pooled is not None else None
        out[x] = {"N_STAGE_A": da["N"], "N_POOLED": None if db is None else db["N"]}
        for m in METRICS:
            a = da[m]
            rec = {"STAGE_A": a, "STAGE_B": None, "FINAL": a, "DECIDED_AT": "A"}
            if a == "ESCALATE":
                if db is None:
                    rec["FINAL"] = "ESCALATE"                     # Stage B not yet executed
                else:
                    b = db[m]
                    rec["STAGE_B"] = b
                    rec["FINAL"] = "CALIBRATION_INDETERMINATE" if b == "ESCALATE" else b
                    rec["DECIDED_AT"] = "B"
            out[x][m] = rec
    return out


def needs_stage_b(decisions: dict) -> bool:
    return any(decisions[x][m]["STAGE_A"] == "ESCALATE" for x in CANDIDATES for m in METRICS)


def flat(decisions: dict) -> dict:
    """{candidate: {COVERAGE: final, UTILITY: final}} for aggregation."""
    return {x: {m: decisions[x][m]["FINAL"] for m in METRICS} for x in decisions}


# ----------------------------------------------------------------------------- phases

def executor_digest() -> dict:
    files = ["generators.py", "estimators.py", "cells.py", "ctable.py", "checkpoint.py", "engine.py", "aggregate.py",
             "amendment_v4.py", "amendment_v3.py", "amendment_v2.py"]
    base = Path(__file__).resolve().parent
    per = {f: hashlib.sha256((base / f).read_bytes()).hexdigest() for f in files}
    combined = hashlib.sha256("".join(f"{k}:{v}\n" for k, v in sorted(per.items())).encode()).hexdigest()
    return {"FILES": per, "EXECUTOR_DIGEST": combined}


def _header(official: bool) -> dict:
    return {"EXECUTOR_DIGEST": executor_digest()["EXECUTOR_DIGEST"],
            "INPUT_DIGESTS": C.frozen()["DIGESTS"] if official else {"DEV": True}, "SCHEMA": "SLIM_V4"}


def run_cal(out_dir: Path, cal_cells: list[dict], cal_n: int = C.CAL_N, official: bool = False) -> Path:
    for cell in cal_cells:                                   # guard every cell BEFORE any file is touched
        lo, _ = C.cal_seed_range(cell)
        _guard(cell, list(range(lo, lo + cal_n)), official)
    out_dir.mkdir(parents=True, exist_ok=True)
    ck = Checkpoint(out_dir / "replicates.jsonl", header=_header(official))
    for cell in cal_cells:
        lo, _ = C.cal_seed_range(cell)
        seeds = list(range(lo, lo + cal_n))
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


def run_eval(out_dir: Path, eval_cells: list[dict], official: bool = False, stage_a: int = C.STAGE_A, stage_b: int = C.STAGE_B) -> list[dict]:
    table = eval_gate(out_dir, official)
    for cell in eval_cells:                                  # guard every cell BEFORE any file is touched
        lo = cell["SEED_RANGE"]["EVAL_STAGE_B"][0]
        _guard(cell, list(range(lo, lo + stage_b)), official)
    ck = Checkpoint(out_dir / "replicates.jsonl", header=_header(official))
    results = []
    for cell in eval_cells:
        klass, n = cell["CLASS"], int(cell["N"])
        lo = cell["SEED_RANGE"]["EVAL_STAGE_B"][0]
        c_factor = ctable.factor(table, klass, n)
        seeds_a = list(range(lo, lo + stage_a))
        for seed in seeds_a:
            if not ck.has("EVAL", cell["CELL_ID"], seed):
                ck.record(eval_replicate(cell, seed))
        rows = {r["S"]: r for r in ck.rows("EVAL") if r["C"] == cell["CELL_ID"]}
        da = [derive(rows[s], cell, c_factor) for s in seeds_a]
        dec = decide_cell(da, None)
        escalated = needs_stage_b(dec)
        if escalated:
            seeds_b = list(range(lo + stage_a, lo + stage_b))
            for seed in seeds_b:
                if not ck.has("EVAL", cell["CELL_ID"], seed):
                    ck.record(eval_replicate(cell, seed))
            rows = {r["S"]: r for r in ck.rows("EVAL") if r["C"] == cell["CELL_ID"]}
            dec = decide_cell(da, [derive(rows[s], cell, c_factor) for s in seeds_b])
        results.append({"CELL_ID": cell["CELL_ID"], "CLASS": klass, "N": n, "LABEL": cell.get("LABEL"), "DECISIVE": cell.get("DECISIVE", False),
                        "C_FACTOR": c_factor, "ESCALATED": escalated, "CHECKS": dec, "DECISIONS": flat(dec)})
    ck.close()
    results.sort(key=lambda r: (r["CLASS"], r["CELL_ID"]))
    return results
