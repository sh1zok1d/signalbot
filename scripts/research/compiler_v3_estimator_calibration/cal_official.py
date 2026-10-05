"""Official CAL phase driver for COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_V1.

This driver does not modify the executor (its modules and digests stay as bound). It
creates the immutable execution identity, runs the preflight, creates the CAL
authorization, executes the official CAL phase ONCE through engine.run_cal (resume-safe),
and writes the CAL completion artifact. It has no EVAL entry point.

Authorization mechanism: engine._guard checks that engine.RUN_AUTHORIZATION exists. On
disk that path (…_RUN_AUTHORIZATION_V1.json) does not exist, so engine.run_eval(official)
is refused. This driver re-points engine.RUN_AUTHORIZATION at runtime to the CAL
authorization artifact (PHASE = CAL, EVAL_PERMITTED = false) after verifying its content
and digest, for the CAL call only.

    python -m scripts.research.compiler_v3_estimator_calibration.cal_official preflight
    python -m scripts.research.compiler_v3_estimator_calibration.cal_official bind
    python -m scripts.research.compiler_v3_estimator_calibration.cal_official authorize
    python -m scripts.research.compiler_v3_estimator_calibration.cal_official execute
"""

from __future__ import annotations

import argparse
import hashlib
import json
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

from scripts.research.compiler_v3_estimator_calibration import amendment_v4 as A4
from scripts.research.compiler_v3_estimator_calibration import cells as C
from scripts.research.compiler_v3_estimator_calibration import ctable, engine
from scripts.research.compiler_v3_estimator_calibration.checkpoint import Checkpoint

REPO = C.REPO
DOCS = C.DOCS
N = "COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_"
BINDING = DOCS / (N + "EXECUTION_BINDING_V1.json")
CAL_AUTH = DOCS / (N + "CAL_AUTHORIZATION_V1.json")
PREFLIGHT = DOCS / (N + "CAL_PREFLIGHT_V1.json")
CAL_COMPLETION = DOCS / (N + "CAL_COMPLETION_V1.json")
C_TABLE_DOCS = DOCS / ctable.C_TABLE_NAME
RUN_DIR = REPO / "data" / "compiler_v3_estimator_calibration_run_1"     # data/ is gitignored; the checkpoint is not committed
RUN_ID = "COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_OFFICIAL_RUN_1"
EXPECTED_COMMIT = "778d51d"
CAL_CELLS, CAL_REPLICATES = 258, 1_032_000
MIN_FREE_BYTES = 30 * 10**9
THREAD_ENV = {"OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO).decode().strip()


def tree_clean() -> bool:
    """No modified or staged tracked file at HEAD. Untracked files are allowed only if they are
    this driver or new calibration artifacts under docs/research (recorded by the preflight)."""
    lines = subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO).decode().splitlines()
    for line in lines:
        status, path = line[:2], line[3:]
        if status != "??":
            return False
        if not (path.endswith("cal_official.py") or path.startswith("docs/research/" + N)):
            return False
    return True


def environment() -> dict:
    return {"PYTHON": sys.version.split()[0], "NUMPY": np.__version__, "SCIPY": scipy.__version__,
            "PLATFORM": platform.platform(), "MACHINE": platform.machine(),
            "RNG": "numpy.random.SeedSequence(seed).spawn(2) -> default_rng(child 0); child 1 reserved",
            "DTYPE": "float64 (numpy default); seeds are Python int",
            "THREADS": THREAD_ENV, "PARALLELISM": "single process, single thread for this CAL execution"}


def cal_surface() -> dict:
    cells = C.cal_cells()
    ranges = sorted((c["CELL_ID"], c["SEED_RANGE"]["CAL"]) for c in cells)
    digest = hashlib.sha256(json.dumps(ranges, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"CELLS": len(cells), "REPLICATES": sum(r[1][1] - r[1][0] + 1 for r in ranges), "SEED_RANGES_SHA256": digest,
            "MIN_SEED": min(r[1][0] for r in ranges), "MAX_SEED": max(r[1][1] for r in ranges), "PER_CELL": C.CAL_N}


def frozen_digests() -> dict:
    am4 = json.loads(A4.AMENDMENT_V4.read_text())
    out = {k: v for k, v in am4["BOUND_ARTIFACTS"].items()}
    out["AMENDMENT_V4"] = {"PATH": str(A4.AMENDMENT_V4.relative_to(REPO)), "SHA256": sha(A4.AMENDMENT_V4)}
    return out


def preflight() -> dict:
    checks = {}
    am4 = json.loads(A4.AMENDMENT_V4.read_text())
    checks["V4_BOUND_DIGESTS_MATCH"] = all(sha(REPO / v["PATH"]) == v["SHA256"] for v in am4["BOUND_ARTIFACTS"].values())
    checks["V4_VALIDATOR_OK"] = A4.verify()["OK"]
    checks["EXECUTOR_DIGEST_MATCHES_V4"] = engine.executor_digest() == am4["EXECUTOR_AFTER_REPAIR"]
    checks["WORKING_TREE_CLEAN"] = tree_clean()
    checks["HEAD_IS_778d51d"] = head().startswith(EXPECTED_COMMIT)
    checks["NO_PRIOR_C_TABLE"] = not C_TABLE_DOCS.exists() and not (RUN_DIR / ctable.C_TABLE_NAME).exists()
    checks["NO_CAL_COMPLETION"] = not CAL_COMPLETION.exists() and not (RUN_DIR / engine.CAL_DONE_NAME).exists()
    checks["NO_EVAL_RESULT"] = not any(DOCS.glob(N + "EVAL*")) and not any(DOCS.glob(N + "*RESULT*"))
    checks["NO_CONSUMED_AUTHORIZATION"] = not CAL_AUTH.exists() and not engine.RUN_AUTHORIZATION.exists()
    surf = cal_surface()
    checks["CAL_SURFACE_MATCHES_FROZEN"] = surf["CELLS"] == CAL_CELLS and surf["REPLICATES"] == CAL_REPLICATES and C.digests_match_amendment()
    src = "".join((Path(engine.__file__).parent / f).read_text() for f in ("generators.py", "estimators.py", "engine.py", "ctable.py", "cells.py"))
    checks["ZERO_RUN1_OUTCOME_DEPENDENCY"] = "VARIANCE_FLOOR_VALIDATION_RESULT" not in src and "RUN_RECORD" not in src
    free = shutil.disk_usage(REPO).free
    checks["FREE_DISK_GE_30E9_BYTES"] = free >= MIN_FREE_BYTES
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    probe = RUN_DIR / ".write_probe"
    try:
        probe.write_text("ok"); probe.unlink(); checks["CHECKPOINT_PATH_WRITABLE"] = True
    except OSError:
        checks["CHECKPOINT_PATH_WRITABLE"] = False
    untracked = subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO).decode().splitlines()
    rec = {"RUN_ID": RUN_ID, "AT_UTC": datetime.now(timezone.utc).isoformat(), "HEAD": head(), "CHECKS": checks, "UNTRACKED_AT_PREFLIGHT": untracked,
           "FREE_DISK_BYTES": free, "FREE_DISK_GIB": round(free / 2**30, 2), "CAL_SURFACE": surf, "OK": all(checks.values())}
    return rec


def bind() -> Path:
    if BINDING.exists():
        raise RuntimeError("execution binding already exists; immutable")
    am4 = json.loads(A4.AMENDMENT_V4.read_text())
    body = {
        "ARTIFACT": BINDING.name, "IMMUTABLE": True, "RUN_ID": RUN_ID, "PHASES": ["CAL", "EVAL"], "DATE": "2026-10-05",
        "COMMIT": head(), "COMMIT_SHORT": EXPECTED_COMMIT,
        "AMENDMENT_V4_SHA256": sha(A4.AMENDMENT_V4), "PROTOCOL_V4_SHA256": am4["BOUND_ARTIFACTS"]["PROTOCOL_V4"]["SHA256"],
        "EXECUTOR": engine.executor_digest(), "FROZEN_ARTIFACTS": frozen_digests(),
        "CAL_SURFACE": cal_surface(),
        "CANDIDATE_C_FITTING_RULE": {"POOL": "all MUST cells of (class, calibrated n) on the CAL split", "RATIO": "T / VA per replicate",
                                     "C_RAW": "order statistic of rank ceil(0.99 * M)", "C_ENV": "suffix maximum over calibrated sizes",
                                     "CALIBRATED_SIZES": C.CAL_SIZES},
        "TARGET_VARIANCE_OBJECT": {"TWO_SAMPLE": "variance of one observation within an arm (long-run)",
                                   "PAIRED_UNITS": "variance of the paired difference of one unit (long-run)",
                                   "CLUSTERED": "variance of the independent cluster-level mean (exact conditional finite-G, V4 D2)",
                                   "RARE_EVENT": "variance of the venue-averaged event statistic (long-run)", "ERA_STRATIFIED": "UNDEFINED"},
        "TWO_SAMPLE_ALLOCATION_DOMAIN": "EQUAL_ARMS_ONLY", "CHECKPOINT_SCHEMA": "SLIM_V4", "CHECKPOINT_ROW_KEYS": A4.SLIM_ROW_KEYS,
        "EXECUTION_ERROR_SEMANTICS": {"REPLICATE": "non-finite truth or non-finite/non-positive required estimator -> row E set, never repaired",
                                      "CAL_PHASE": "any error row, checkpoint integrity error, missing or duplicate seed -> CAL_PHASE_EXECUTION_ERROR; no partial C-table; no EVAL; no retry with another seed",
                                      "RESUME": "append-only checkpoint, same seeds, same binding header; completed replicates never re-executed"},
        "C_TABLE_OUTPUT": {"RUN_DIR": str(RUN_DIR.relative_to(REPO)), "SEALED_PATH": str((RUN_DIR / ctable.C_TABLE_NAME).relative_to(REPO)),
                           "COMMITTED_COPY": str(C_TABLE_DOCS.relative_to(REPO)), "COPY_RULE": "byte-identical copy; digest recorded in the completion artifact"},
        "CHECKPOINT_PATH": str((RUN_DIR / "replicates.jsonl").relative_to(REPO)),
        "ENVIRONMENT": environment(),
        "AUTHORIZATION_MECHANISM": "engine.RUN_AUTHORIZATION (…_RUN_AUTHORIZATION_V1.json) does not exist on disk, so engine.run_eval(official) is refused; the CAL driver re-points it at runtime to the CAL authorization artifact for the CAL call only",
        "EVAL_AUTHORIZED": False,
    }
    BINDING.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n")
    return BINDING


def authorize() -> Path:
    if CAL_AUTH.exists():
        raise RuntimeError("CAL authorization already exists; immutable")
    pf = json.loads(PREFLIGHT.read_text())
    if not pf["OK"]:
        raise RuntimeError("preflight not OK; STOP")
    body = {"ARTIFACT": CAL_AUTH.name, "IMMUTABLE": True, "RUN_ID": RUN_ID, "PHASE": "CAL", "ONE_OFFICIAL_CAL_EXECUTION": True,
            "EVAL_PERMITTED": False, "DATE": "2026-10-05", "OWNER_DECISION": "2026-10-05: official CAL phase only; EVAL forbidden",
            "EXECUTION_BINDING": {"PATH": str(BINDING.relative_to(REPO)), "SHA256": sha(BINDING)},
            "PREFLIGHT": {"PATH": str(PREFLIGHT.relative_to(REPO)), "SHA256": sha(PREFLIGHT)},
            "COMMIT": head(), "CAL_SURFACE": cal_surface(), "EXECUTOR_DIGEST": engine.executor_digest()["EXECUTOR_DIGEST"],
            "ENVIRONMENT": environment(),
            "ALLOWED": ["deterministic resume after interruption with the same checkpoint and binding"],
            "FORBIDDEN": ["new seeds", "replacement seeds", "rerun of a completed replicate", "parameter changes", "executor changes", "fitting-rule changes", "EVAL"]}
    CAL_AUTH.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n")
    return CAL_AUTH


def execute() -> dict:
    for k, v in THREAD_ENV.items():
        if os.environ.get(k) != v:
            raise RuntimeError(f"{k} must be {v} for the official CAL execution")
    auth = json.loads(CAL_AUTH.read_text())
    if auth["PHASE"] != "CAL" or auth["EVAL_PERMITTED"] is not False or auth["RUN_ID"] != RUN_ID:
        raise RuntimeError("CAL authorization content invalid; STOP")
    if sha(BINDING) != auth["EXECUTION_BINDING"]["SHA256"] or not head().startswith(EXPECTED_COMMIT):
        raise RuntimeError("binding digest or commit mismatch; STOP")
    binding = json.loads(BINDING.read_text())
    if binding["EXECUTOR"] != engine.executor_digest():
        raise RuntimeError("executor digest changed since binding; STOP")
    if CAL_COMPLETION.exists():
        raise RuntimeError("CAL already completed; ONE_OFFICIAL_CAL_EXECUTION")
    engine.RUN_AUTHORIZATION = CAL_AUTH              # runtime re-point for the CAL call only (see module docstring)
    t0 = time.time()
    started = datetime.now(timezone.utc).isoformat()
    cells = C.cal_cells()
    try:
        path = engine.run_cal(RUN_DIR, cells, official=True)
    except Exception as err:                         # noqa: BLE001 - any failure is CAL_PHASE_EXECUTION_ERROR, no repair
        (RUN_DIR / "CAL_PHASE_EXECUTION_ERROR.json").write_text(json.dumps({"ERROR": repr(err), "AT": datetime.now(timezone.utc).isoformat()}, indent=2) + "\n")
        raise
    elapsed = time.time() - t0
    # integrity summary over the checkpoint
    ck = Checkpoint(RUN_DIR / "replicates.jsonl")
    rows = ck.rows("CAL")
    ck.close()
    expected = {(c["CELL_ID"], s) for c in cells for s in range(c["SEED_RANGE"]["CAL"][0], c["SEED_RANGE"]["CAL"][0] + C.CAL_N)}
    got = {(r["C"], r["S"]) for r in rows}
    errors = [r for r in rows if r["E"]]
    nonfinite = [r for r in rows if not r["E"] and not (np.isfinite(r["T"]) and np.isfinite(r["VA"]) and r["VA"] > 0)]
    summary = {"COMPLETED": len(rows), "EXPECTED": len(expected), "MISSING": len(expected - got), "UNEXPECTED": len(got - expected),
               "DUPLICATES": len(rows) - len(got), "ERROR_ROWS": len(errors), "NONFINITE_ROWS": len(nonfinite)}
    if any(summary[k] for k in ("MISSING", "UNEXPECTED", "DUPLICATES", "ERROR_ROWS", "NONFINITE_ROWS")) or summary["COMPLETED"] != CAL_REPLICATES:
        raise RuntimeError(f"CAL_PHASE_EXECUTION_ERROR: integrity summary {summary}")
    shutil.copyfile(path, C_TABLE_DOCS)
    if sha(C_TABLE_DOCS) != sha(path):
        raise RuntimeError("C-table copy not byte-identical")
    table = json.loads(path.read_text())["TABLE"]
    completion = {"ARTIFACT": CAL_COMPLETION.name, "IMMUTABLE": True, "RUN_ID": RUN_ID, "PHASE": "CAL", "STATUS": "COMPLETE",
                  "STARTED_UTC": started, "FINISHED_UTC": datetime.now(timezone.utc).isoformat(), "ELAPSED_SECONDS": round(elapsed, 1),
                  "CAL_AUTHORIZATION_SHA256": sha(CAL_AUTH), "EXECUTION_BINDING_SHA256": sha(BINDING), "COMMIT": head(),
                  "CHECKPOINT": {"PATH": str((RUN_DIR / "replicates.jsonl").relative_to(REPO)), "SHA256": sha(RUN_DIR / "replicates.jsonl"),
                                 "BYTES": (RUN_DIR / "replicates.jsonl").stat().st_size, "INTEGRITY": summary},
                  "C_TABLE": {"SEALED_PATH": str(path.relative_to(REPO)), "COMMITTED_COPY": str(C_TABLE_DOCS.relative_to(REPO)), "SHA256": sha(path),
                              "ROWS_PER_CLASS": {k: {n: {"M": v["M"], "RANK": v["RANK"], "C_RAW": v["C_RAW"], "C_ENV": v["C_ENV"]} for n, v in t.items()} for k, t in table.items()}},
                  "ENGINE_CAL_RECORD_SHA256": sha(RUN_DIR / engine.CAL_DONE_NAME), "EXECUTOR_DIGEST": engine.executor_digest()["EXECUTOR_DIGEST"],
                  "EVAL_REPLICATES_EXECUTED": 0, "EVAL_AUTHORIZED": False}
    CAL_COMPLETION.write_text(json.dumps(completion, indent=2, sort_keys=True) + "\n")
    return completion


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["preflight", "bind", "authorize", "execute"])
    a = ap.parse_args()
    if a.step == "preflight":
        if PREFLIGHT.exists():
            raise RuntimeError("preflight record already exists; immutable")
        rec = preflight()
        PREFLIGHT.write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n")
        print(json.dumps(rec, indent=1))
        if not rec["OK"]:
            raise SystemExit("PREFLIGHT FAILED; STOP")
    elif a.step == "bind":
        print(bind(), sha(BINDING))
    elif a.step == "authorize":
        print(authorize(), sha(CAL_AUTH))
    else:
        print(json.dumps(execute(), indent=1))


if __name__ == "__main__":
    main()
