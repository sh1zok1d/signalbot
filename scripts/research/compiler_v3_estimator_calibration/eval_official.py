"""Official EVAL phase driver for COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_OFFICIAL_RUN_1.

Orchestration only: no estimator, bound, generator, seed, filtering or candidate logic lives
here. It verifies binding / authorization / environment, invokes the frozen V4 EVAL engine
(engine.run_eval) once per frozen cell, performs post-run integrity checks, and writes the
result, aggregation and completion artifacts by calling the frozen aggregate module.

Sharding (orchestration, not semantics): each frozen EVAL cell is executed in its own shard
directory  <RUN_DIR>/eval/<CELL_ID>/  that holds byte-identical copies of the sealed C-table
and the engine CAL completion record (so engine.eval_gate verifies the table digest in
every shard) and the cell's own SLIM_V4 checkpoint. Shards are independent, so up to
WORKERS single-threaded processes run disjoint cells; the per-(cell, seed) sample is a pure
function of the frozen seed, so the result is scheduling-independent. Resume: a shard with a
complete result file is skipped; an incomplete shard resumes through the frozen checkpoint.

Authorization mechanism: as for CAL, engine.RUN_AUTHORIZATION is re-pointed at runtime to the
EVAL authorization artifact (PHASE = EVAL) inside each worker, after its content and digest
were verified against the committed tree.

    python -m scripts.research.compiler_v3_estimator_calibration.eval_official bind
    python -m scripts.research.compiler_v3_estimator_calibration.eval_official verify-binding
    python -m scripts.research.compiler_v3_estimator_calibration.eval_official authorize
    python -m scripts.research.compiler_v3_estimator_calibration.eval_official verify-authorization
    python -m scripts.research.compiler_v3_estimator_calibration.eval_official execute
"""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
import os
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import scipy

from scripts.research.compiler_v3_estimator_calibration import aggregate as AG
from scripts.research.compiler_v3_estimator_calibration import amendment_v4 as A4
from scripts.research.compiler_v3_estimator_calibration import cells as C
from scripts.research.compiler_v3_estimator_calibration import ctable, engine
from scripts.research.compiler_v3_estimator_calibration.checkpoint import Checkpoint

REPO, DOCS = C.REPO, C.DOCS
N = "COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_"
RUN_ID = "COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_OFFICIAL_RUN_1"
EVAL_BINDING = DOCS / (N + "EVAL_BINDING_V1.json")
EVAL_AUTH = DOCS / (N + "EVAL_AUTHORIZATION_V1.json")
EVAL_COMPLETION = DOCS / (N + "EVAL_COMPLETION_V1.json")
RESULT = DOCS / (N + "RESULT_V1.json")
AGGREGATION = DOCS / (N + "AGGREGATION_V1.json")
CAL_BINDING = DOCS / (N + "EXECUTION_BINDING_V1.json")
CAL_AUTH = DOCS / (N + "CAL_AUTHORIZATION_V1.json")
CAL_COMPLETION = DOCS / (N + "CAL_COMPLETION_V1.json")
CAL_DEVIATION = DOCS / (N + "CAL_PROVENANCE_DEVIATION_V1.json")
C_TABLE_DOCS = DOCS / ctable.C_TABLE_NAME
RUN_DIR = REPO / "data" / "compiler_v3_estimator_calibration_run_1"
EVAL_DIR = RUN_DIR / "eval"
DRIVER = Path(__file__).resolve()
EXPECTED_CELLS, EXPECTED_STAGE_A = 5535, 22_140_000
MIN_FREE_BYTES = 25_000_000_000
THREAD_ENV = {"OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
WORKERS = 4


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO).decode().strip()


def tree_clean() -> bool:
    return subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO).decode().strip() == ""


def committed_sha(path: Path, rev: str = "HEAD") -> str:
    rel = str(path.relative_to(REPO))
    return sha_bytes(subprocess.check_output(["git", "show", f"{rev}:{rel}"], cwd=REPO))


def environment() -> dict:
    return {"PYTHON": sys.version.split()[0], "NUMPY": np.__version__, "SCIPY": scipy.__version__,
            "PLATFORM": platform.platform(), "MACHINE": platform.machine(),
            "RNG": "numpy.random.SeedSequence(seed).spawn(2) -> default_rng(child 0); child 1 reserved; candidate never enters the derivation",
            "DTYPE": "float64 (numpy default); seeds are Python int", "THREADS": THREAD_ENV,
            "PARALLELISM": f"up to {WORKERS} single-threaded worker processes over disjoint cell shards; scheduling-independent by construction"}


def eval_surface() -> dict:
    cells = C.eval_cells()
    rows = sorted((c["CELL_ID"], c["SEED_RANGE"]["EVAL_STAGE_B"]) for c in cells)
    digest = sha_bytes(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode())
    return {"CELLS": len(cells), "STAGE_A_REPLICATES": len(cells) * C.STAGE_A, "STAGE_B_POOLED_PER_CELL": C.STAGE_B,
            "MAX_REPLICATES": len(cells) * C.STAGE_B, "SEED_RANGES_SHA256": digest,
            "BY_SOURCE": {"GRID_621": len(C.frozen()["GRID"]["CELLS"]), "PROBES_198": len(C.frozen()["PROBES"]["CELLS"]), "DENSE_4716": len(C.frozen()["DENSE"]["CELLS"])},
            "DECISIVE_CELLS": sum(1 for c in cells if c.get("DECISIVE")), "MIN_SEED": min(r[1][0] for r in rows), "MAX_SEED": max(r[1][1] for r in rows)}


def frozen_digests() -> dict:
    am4 = json.loads(A4.AMENDMENT_V4.read_text())
    out = dict(am4["BOUND_ARTIFACTS"])
    out["AMENDMENT_V4"] = {"PATH": str(A4.AMENDMENT_V4.relative_to(REPO)), "SHA256": sha(A4.AMENDMENT_V4)}
    return out


def bind() -> Path:
    if EVAL_BINDING.exists():
        raise RuntimeError("EVAL binding already exists; immutable")
    surf = eval_surface()
    if surf["CELLS"] != EXPECTED_CELLS or surf["STAGE_A_REPLICATES"] != EXPECTED_STAGE_A:
        raise RuntimeError(f"frozen EVAL surface {surf['CELLS']} cells / {surf['STAGE_A_REPLICATES']} Stage-A replicates differs from the expected 5535 / 22,140,000; STOP")
    am4 = json.loads(A4.AMENDMENT_V4.read_text())
    thr = json.loads(DOCS.joinpath(N + "FREEZE_AMENDMENT_V3.json").read_text())["ERROR_BUDGET"]["STAGE_THRESHOLDS"]
    body = {
        "ARTIFACT": EVAL_BINDING.name, "IMMUTABLE": True, "RUN_ID": RUN_ID, "PHASE": "EVAL", "DATE": "2026-10-05",
        "AMENDMENT_V4_SHA256": sha(A4.AMENDMENT_V4), "PROTOCOL_V4_SHA256": am4["BOUND_ARTIFACTS"]["PROTOCOL_V4"]["SHA256"],
        "EXECUTOR": engine.executor_digest(), "DRIVER": {"PATH": str(DRIVER.relative_to(REPO)), "SHA256": sha(DRIVER)},
        "CAL_CHAIN": {"EXECUTION_BINDING_SHA256": sha(CAL_BINDING), "CAL_AUTHORIZATION_SHA256": sha(CAL_AUTH),
                      "CAL_COMPLETION_SHA256": sha(CAL_COMPLETION), "CAL_PROVENANCE_DEVIATION_SHA256": sha(CAL_DEVIATION),
                      "CAL_STATUS": "CAL_ADMISSIBLE_WITH_RECORDED_PROVENANCE_DEVIATION", "CAL_RERUN": "FORBIDDEN"},
        "C_TABLE": {"PATH": str(C_TABLE_DOCS.relative_to(REPO)), "SHA256": sha(C_TABLE_DOCS), "ACCESS": "READ_ONLY; no refit, smoothing, monotonicity repair, envelope or quantile change; a failing dense count is evidence against C, never a deletion"},
        "FROZEN_ARTIFACTS": frozen_digests(), "EVAL_SURFACE": surf,
        "STAGE_RULES": {"STAGE_A": "exactly the first 4000 frozen seeds of each cell", "STAGE_B": "seeds 4000..19999 of the cell, generated once and shared; decides only checks whose own Stage-A state is ESCALATE; Stage-A PASS/FAIL locked; residual ESCALATE -> CALIBRATION_INDETERMINATE; no third stage",
                        "CONF_CLASS_CANDIDATE": "1199/1200", "REFERENCE_D_CONFIDENCE": 0.99, "THRESHOLDS": thr},
        "SELECTION": "per required class, strict preference A -> B -> C (amendment V4 D1); global precedence EXECUTION_ERROR > FAIL_INFORMATION_INSUFFICIENT > INDETERMINATE > PASS",
        "CHECKPOINT_SCHEMA": "SLIM_V4", "CHECKPOINT_ROW_KEYS": A4.SLIM_ROW_KEYS,
        "CHECKPOINT_SHARDING": {"LAYOUT": "data/compiler_v3_estimator_calibration_run_1/eval/<CELL_ID>/replicates.jsonl", "SHARD_CONTENTS": "byte-identical copies of the sealed C-table and the engine CAL completion record, the cell checkpoint with HEADER, the cell result file",
                                "FINAL_DIGEST": "sha256 over the sorted list of (CELL_ID, shard checkpoint sha256)"},
        "EXECUTION_ERROR_SEMANTICS": {"REPLICATE": "non-finite truth or non-finite/non-positive estimator -> row E set, never repaired; cell check CALIBRATION_EXECUTION_ERROR",
                                      "INTEGRITY": "non-identical duplicate or header mismatch -> EXECUTION_INTEGRITY_ERROR; STOP; partial artifacts preserved",
                                      "RESUME": "append-only checkpoint, same seeds, same header; completed replicates never re-executed; no new or replacement seeds; no repair after partial results"},
        "ENVIRONMENT": environment(),
        "AUTHORIZATION_MECHANISM": "engine.RUN_AUTHORIZATION re-pointed at runtime to the EVAL authorization artifact inside each worker after content/digest verification against the committed tree",
        "GOVERNANCE": "binding and authorization are committed and pushed BEFORE the first EVAL replicate; results in a later separate commit",
    }
    EVAL_BINDING.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n")
    return EVAL_BINDING


def verify_binding() -> dict:
    b = json.loads(EVAL_BINDING.read_text())
    checks = {"TREE_CLEAN": tree_clean(), "BINDING_COMMITTED_IDENTICAL": committed_sha(EVAL_BINDING) == sha(EVAL_BINDING),
              "DRIVER_COMMITTED_IDENTICAL": committed_sha(DRIVER) == sha(DRIVER) == b["DRIVER"]["SHA256"],
              "EXECUTOR_MATCH": engine.executor_digest() == b["EXECUTOR"],
              "FROZEN_MATCH": all(sha(REPO / v["PATH"]) == v["SHA256"] for v in b["FROZEN_ARTIFACTS"].values()),
              "C_TABLE_MATCH": sha(C_TABLE_DOCS) == b["C_TABLE"]["SHA256"],
              "CAL_CHAIN_MATCH": sha(CAL_BINDING) == b["CAL_CHAIN"]["EXECUTION_BINDING_SHA256"] and sha(CAL_AUTH) == b["CAL_CHAIN"]["CAL_AUTHORIZATION_SHA256"]
                                 and sha(CAL_COMPLETION) == b["CAL_CHAIN"]["CAL_COMPLETION_SHA256"] and sha(CAL_DEVIATION) == b["CAL_CHAIN"]["CAL_PROVENANCE_DEVIATION_SHA256"],
              "SURFACE_MATCH": eval_surface() == b["EVAL_SURFACE"]}
    return {"HEAD": head(), "BINDING_SHA256": sha(EVAL_BINDING), "DRIVER_SHA256": sha(DRIVER), "CHECKS": checks, "OK": all(checks.values())}


def authorize() -> Path:
    if EVAL_AUTH.exists():
        raise RuntimeError("EVAL authorization already exists; immutable")
    v = verify_binding()
    if not v["OK"]:
        raise RuntimeError(f"binding verification failed: {v['CHECKS']}; STOP")
    body = {"ARTIFACT": EVAL_AUTH.name, "IMMUTABLE": True, "RUN_ID": RUN_ID, "PHASE": "EVAL", "ONE_OFFICIAL_EVAL_EXECUTION": True, "DATE": "2026-10-05",
            "OWNER_DECISION": "2026-10-05: one official EVAL phase; CAL admissible with recorded provenance deviation; CAL rerun forbidden",
            "EVAL_BINDING": {"PATH": str(EVAL_BINDING.relative_to(REPO)), "SHA256": sha(EVAL_BINDING), "COMMIT": head()},
            "C_TABLE_SHA256": sha(C_TABLE_DOCS), "EXECUTOR_DIGEST": engine.executor_digest()["EXECUTOR_DIGEST"], "DRIVER_SHA256": sha(DRIVER),
            "EVAL_SURFACE": eval_surface(), "ENVIRONMENT": environment(),
            "FORBIDDEN": ["CAL rerun", "new seeds", "replacement seeds", "manual candidate exclusion", "parameter repair", "C-table change", "third stage", "rerun of completed seeds", "code fix inside the same official run"],
            "ALLOWED": ["deterministic resume through the frozen checkpoint with the same seeds and header"]}
    EVAL_AUTH.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n")
    return EVAL_AUTH


def verify_authorization() -> dict:
    a = json.loads(EVAL_AUTH.read_text())
    vb = verify_binding()
    checks = {"TREE_CLEAN": tree_clean(), "AUTH_COMMITTED_IDENTICAL": committed_sha(EVAL_AUTH) == sha(EVAL_AUTH),
              "AUTH_BINDS_BINDING": a["EVAL_BINDING"]["SHA256"] == sha(EVAL_BINDING), "BINDING_VERIFIES": vb["OK"],
              "AUTH_PHASE_EVAL": a["PHASE"] == "EVAL" and a["ONE_OFFICIAL_EVAL_EXECUTION"] is True and a["RUN_ID"] == RUN_ID,
              "AUTH_C_TABLE": a["C_TABLE_SHA256"] == sha(C_TABLE_DOCS), "AUTH_EXECUTOR": a["EXECUTOR_DIGEST"] == engine.executor_digest()["EXECUTOR_DIGEST"],
              "AUTH_DRIVER": a["DRIVER_SHA256"] == sha(DRIVER), "NO_PRIOR_EVAL_COMPLETION": not EVAL_COMPLETION.exists() and not RESULT.exists() and not AGGREGATION.exists()}
    free = shutil.disk_usage(REPO).free
    checks["FREE_DISK_GE_25E9_BYTES"] = free >= MIN_FREE_BYTES
    return {"HEAD": head(), "AUTH_SHA256": sha(EVAL_AUTH), "FREE_DISK_BYTES": free, "CHECKS": checks, "OK": all(checks.values())}


# ----------------------------------------------------------------------------- execution

def _shard(cell: dict) -> Path:
    return EVAL_DIR / cell["CELL_ID"]


def _prepare_shard(cell: dict) -> Path:
    d = _shard(cell)
    d.mkdir(parents=True, exist_ok=True)
    for src, name in ((RUN_DIR / ctable.C_TABLE_NAME, ctable.C_TABLE_NAME), (RUN_DIR / engine.CAL_DONE_NAME, engine.CAL_DONE_NAME)):
        dst = d / name
        if not dst.exists():
            shutil.copyfile(src, dst)
        if sha(dst) != sha(src):
            raise RuntimeError(f"shard copy not byte-identical: {dst}")
    return d


def _worker_init() -> None:
    for k, v in THREAD_ENV.items():
        os.environ[k] = v
    engine.RUN_AUTHORIZATION = EVAL_AUTH


def _run_cell(cell: dict) -> dict:
    d = _prepare_shard(cell)
    done = d / "result.json"
    if done.exists():
        return json.loads(done.read_text())
    res = engine.run_eval(d, [cell], official=True)[0]
    done.write_text(json.dumps(res, sort_keys=True, separators=(",", ":")) + "\n")
    return res


def execute() -> dict:
    for k, v in THREAD_ENV.items():
        if os.environ.get(k) != v:
            raise RuntimeError(f"{k} must be {v} for the official EVAL execution")
    va = verify_authorization()
    if not va["OK"]:
        raise RuntimeError(f"authorization verification failed: {va['CHECKS']}; STOP")
    if EVAL_COMPLETION.exists():
        raise RuntimeError("EVAL already completed; ONE_OFFICIAL_EVAL_EXECUTION")
    if sha(RUN_DIR / ctable.C_TABLE_NAME) != sha(C_TABLE_DOCS):
        raise RuntimeError("sealed C-table in the run directory differs from the committed copy; STOP")
    started = datetime.now(timezone.utc).isoformat()
    t0 = time.time()
    cells = C.eval_cells()
    _worker_init()
    results = []
    with mp.get_context("fork").Pool(WORKERS, initializer=_worker_init) as pool:
        for res in pool.imap_unordered(_run_cell, cells, chunksize=1):
            results.append(res)
    elapsed = time.time() - t0
    results.sort(key=lambda r: (r["CLASS"], r["CELL_ID"]))
    integrity = _integrity(cells)
    if integrity["STOP"]:
        (RUN_DIR / "EVAL_PHASE_EXECUTION_ERROR.json").write_text(json.dumps(integrity, indent=2) + "\n")
        raise RuntimeError(f"EVAL integrity failure: {integrity}")
    f = C.frozen()
    agg = AG.aggregate(results, f["REALISTIC_MAX"], f["SUPPORTED_RANGE"])
    common = {"RUN_ID": RUN_ID, "EVAL_AUTHORIZATION_SHA256": sha(EVAL_AUTH), "EVAL_BINDING_SHA256": sha(EVAL_BINDING),
              "EXECUTOR_DIGEST": engine.executor_digest()["EXECUTOR_DIGEST"], "C_TABLE_SHA256": sha(C_TABLE_DOCS),
              "V4_INPUTS": frozen_digests(), "CHECKPOINT_SHA256": integrity["CHECKPOINT_SHA256"]}
    RESULT.write_text(json.dumps({"ARTIFACT": RESULT.name, "IMMUTABLE": True, **common, "CELLS": results}, sort_keys=True, separators=(",", ":")) + "\n")
    AGGREGATION.write_text(json.dumps({"ARTIFACT": AGGREGATION.name, "IMMUTABLE": True, **common, "RESULT_SHA256": sha(RESULT), **agg}, indent=2, sort_keys=True) + "\n")
    esc_cells = sum(1 for r in results if r["ESCALATED"])
    esc_checks = sum(1 for r in results for x in engine.CANDIDATES for m in engine.METRICS if r["CHECKS"][x][m]["STAGE_A"] == "ESCALATE")
    completion = {"ARTIFACT": EVAL_COMPLETION.name, "IMMUTABLE": True, **common, "PHASE": "EVAL", "STATUS": "COMPLETE",
                  "STARTED_UTC": started, "FINISHED_UTC": datetime.now(timezone.utc).isoformat(), "ELAPSED_SECONDS": round(elapsed, 1),
                  "COMMIT": head(), "DRIVER_SHA256": sha(DRIVER), "INTEGRITY": integrity, "ESCALATED_CELLS": esc_cells, "ESCALATED_CHECKS": esc_checks,
                  "RESULT_SHA256": sha(RESULT), "AGGREGATION_SHA256": sha(AGGREGATION), "GLOBAL_STATUS": agg["GLOBAL_STATUS"],
                  "CAL_RERUN": False, "RUN1_OUTCOMES_USED": False, "C_TABLE_UNCHANGED": sha(C_TABLE_DOCS) == json.loads(EVAL_AUTH.read_text())["C_TABLE_SHA256"]}
    EVAL_COMPLETION.write_text(json.dumps(completion, indent=2, sort_keys=True) + "\n")
    return completion


def _integrity(cells: list[dict]) -> dict:
    per_shard, total, stage_b_rows, errors, missing_cells = [], 0, 0, 0, 0
    bad_seed, dup, out_of_range = 0, 0, 0
    size = 0
    for cell in cells:
        p = _shard(cell) / "replicates.jsonl"
        if not p.exists() or not (_shard(cell) / "result.json").exists():
            missing_cells += 1
            continue
        size += p.stat().st_size
        ck = Checkpoint(p)
        rows = ck.rows("EVAL")
        ck.close()
        lo, hi = cell["SEED_RANGE"]["EVAL_STAGE_B"]
        seeds = [r["S"] for r in rows]
        n = len(rows)
        if n not in (C.STAGE_A, C.STAGE_B):
            bad_seed += 1
        if sorted(seeds) != list(range(lo, lo + n)):
            bad_seed += 1
        out_of_range += sum(1 for s in seeds if not lo <= s <= hi)
        dup += n - len(set(seeds))
        errors += sum(1 for r in rows if r["E"])
        total += n
        stage_b_rows += max(0, n - C.STAGE_A)
        per_shard.append([cell["CELL_ID"], sha(p)])
    per_shard.sort()
    digest = sha_bytes(json.dumps(per_shard, separators=(",", ":")).encode())
    stop = missing_cells > 0 or bad_seed > 0 or out_of_range > 0 or dup > 0
    return {"CELLS_EXPECTED": len(cells), "CELLS_COMPLETE": len(cells) - missing_cells, "CELLS_MISSING": missing_cells,
            "STAGE_A_EXPECTED": len(cells) * C.STAGE_A, "ROWS_COMPLETED": total, "STAGE_B_ADDITIONAL_ROWS": stage_b_rows,
            "CELLS_WITH_BAD_SEED_SET": bad_seed, "SEEDS_OUT_OF_RANGE": out_of_range, "DUPLICATES": dup, "ERROR_ROWS": errors,
            "CHECKPOINT_BYTES": size, "CHECKPOINT_SHA256": digest, "SHARD_DIGESTS": per_shard, "STOP": stop}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["bind", "verify-binding", "authorize", "verify-authorization", "execute"])
    a = ap.parse_args()
    if a.step == "bind":
        print(bind(), sha(EVAL_BINDING))
    elif a.step == "verify-binding":
        print(json.dumps(verify_binding(), indent=1))
    elif a.step == "authorize":
        print(authorize(), sha(EVAL_AUTH))
    elif a.step == "verify-authorization":
        print(json.dumps(verify_authorization(), indent=1))
    else:
        out = execute()
        out.pop("INTEGRITY", None)
        print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
