"""Deterministic EVAL resume driver after an infrastructure interruption, for the same
CALIBRATION_RUN_ID = COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_OFFICIAL_RUN_1 and
the same EVAL phase. Orchestration only: no research-semantic logic, no outcome reading or
filtering, no seed generation, no checkpoint row modification. It reuses the committed
eval_official shard functions (_run_cell, _integrity) and the frozen V4 engine.

Capacity rule (outcome-blind, resume amendment V1): REMAINING_MAX_ROWS is computed from the
frozen seed coverage only; RESUME_REQUIRED_FREE_BYTES = 512 * REMAINING_MAX_ROWS + 2e9.

    python -m scripts.research.compiler_v3_estimator_calibration.eval_resume snapshot
    python -m scripts.research.compiler_v3_estimator_calibration.eval_resume amend
    python -m scripts.research.compiler_v3_estimator_calibration.eval_resume bind
    python -m scripts.research.compiler_v3_estimator_calibration.eval_resume verify-binding
    python -m scripts.research.compiler_v3_estimator_calibration.eval_resume authorize
    python -m scripts.research.compiler_v3_estimator_calibration.eval_resume verify-authorization
    python -m scripts.research.compiler_v3_estimator_calibration.eval_resume execute
"""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from scripts.research.compiler_v3_estimator_calibration import aggregate as AG
from scripts.research.compiler_v3_estimator_calibration import cells as C
from scripts.research.compiler_v3_estimator_calibration import ctable, engine
from scripts.research.compiler_v3_estimator_calibration import eval_official as EO

DOCS, REPO, N, RUN_ID = EO.DOCS, EO.REPO, EO.N, EO.RUN_ID
SNAPSHOT = DOCS / (N + "EVAL_INTERRUPTION_SNAPSHOT_V1.json")
AMENDMENT = DOCS / (N + "EVAL_RESUME_AMENDMENT_V1.json")
BINDING = DOCS / (N + "EVAL_RESUME_BINDING_V1.json")
AUTH = DOCS / (N + "EVAL_RESUME_AUTHORIZATION_V1.json")
DRIVER = Path(__file__).resolve()
BYTES_PER_ROW, RESERVE_BYTES = 512, 2_000_000_000
sha, sha_bytes, head, tree_clean, committed_sha = EO.sha, EO.sha_bytes, EO.head, EO.tree_clean, EO.committed_sha


# ----------------------------------------------------------------------------- inventory (seed coverage only)

def shard_inventory(parse_seeds: bool = True) -> dict:
    """Per frozen cell: state, recorded seed coverage (seeds only; no estimator/truth/outcome field is read),
    file sizes and digests. Result files are hashed, never opened."""
    cells = C.eval_cells()
    inv, counts = [], {"COMPLETED": 0, "IN_FLIGHT": 0, "NOT_STARTED": 0}
    total_rows, remaining_max = 0, 0
    for cell in cells:
        d = EO._shard(cell)
        ck, res = d / "replicates.jsonl", d / "result.json"
        lo, hi = cell["SEED_RANGE"]["EVAL_STAGE_B"]
        rec = {"CELL_ID": cell["CELL_ID"], "FROZEN_SEED_RANGE": [lo, hi]}
        if res.exists():
            state = "COMPLETED"
        elif ck.exists():
            state = "IN_FLIGHT"
        else:
            state = "NOT_STARTED"
        rec["STATE"] = state
        counts[state] += 1
        if ck.exists() and not parse_seeds:
            rec.update({"CHECKPOINT_BYTES": ck.stat().st_size, "CHECKPOINT_SHA256": sha(ck), "ROWS": None})
        elif ck.exists():
            seeds = []
            with ck.open() as fh:
                for i, line in enumerate(fh):
                    if i == 0 and line.startswith('{"HEADER"'):
                        continue
                    seeds.append(json.loads(line)["S"])           # only the seed field is used
            n = len(seeds)
            contiguous = sorted(seeds) == list(range(lo, lo + n)) and len(set(seeds)) == n
            rec.update({"ROWS": n, "SEED_MIN": min(seeds) if seeds else None, "SEED_MAX": max(seeds) if seeds else None,
                        "CONTIGUOUS_FROM_RANGE_START": contiguous, "CHECKPOINT_BYTES": ck.stat().st_size, "CHECKPOINT_SHA256": sha(ck)})
            total_rows += n
        else:
            rec.update({"ROWS": 0})
        if res.exists():
            rec.update({"RESULT_BYTES": res.stat().st_size, "RESULT_SHA256": sha(res)})
        rem = 0 if state == "COMPLETED" else (max(0, C.STAGE_B - rec["ROWS"]) if rec["ROWS"] is not None else None)
        rec["REMAINING_MAX_ROWS"] = rem
        remaining_max += rem or 0
        inv.append(rec)
    root = sha_bytes(json.dumps([[r["CELL_ID"], r.get("CHECKPOINT_SHA256"), r.get("RESULT_SHA256")] for r in inv], separators=(",", ":")).encode())
    return {"CELLS": inv, "COUNTS": counts, "TOTAL_ROWS": total_rows, "REMAINING_MAX_ROWS": remaining_max,
            "RESUME_REQUIRED_FREE_BYTES": BYTES_PER_ROW * remaining_max + RESERVE_BYTES, "ROOT_SHA256": root, "SEEDS_PARSED": parse_seeds,
            "ALL_CONTIGUOUS": all(r.get("CONTIGUOUS_FROM_RANGE_START", True) for r in inv)}


def snapshot() -> Path:
    if SNAPSHOT.exists():
        raise RuntimeError("interruption snapshot already exists; immutable")
    inv = shard_inventory()
    body = {"ARTIFACT": SNAPSHOT.name, "IMMUTABLE": True, "RUN_ID": RUN_ID, "PHASE": "EVAL", "DATE": "2026-10-05",
            "INTERRUPTION_REASON": "container restart by the execution harness during the official EVAL run (not an executor failure)",
            "ORIGINAL_EVAL_BINDING": {"PATH": str(EO.EVAL_BINDING.relative_to(REPO)), "SHA256": sha(EO.EVAL_BINDING), "COMMIT": "b42722e"},
            "ORIGINAL_EVAL_AUTHORIZATION": {"PATH": str(EO.EVAL_AUTH.relative_to(REPO)), "SHA256": sha(EO.EVAL_AUTH), "COMMIT": "5bfdc17"},
            "C_TABLE_SHA256": sha(EO.C_TABLE_DOCS), "C_TABLE_RUN_DIR_SHA256": sha(EO.RUN_DIR / ctable.C_TABLE_NAME),
            "EXECUTOR": engine.executor_digest(),
            "CONFIRMATIONS": {"NO_AGGREGATION_ARTIFACT": not EO.AGGREGATION.exists(), "NO_RESULT_ARTIFACT": not EO.RESULT.exists(),
                              "NO_EVAL_COMPLETION_ARTIFACT": not EO.EVAL_COMPLETION.exists(), "CAL_NOT_RERUN": sha(EO.CAL_COMPLETION) == json.loads(EO.EVAL_BINDING.read_text())["CAL_CHAIN"]["CAL_COMPLETION_SHA256"],
                              "C_TABLE_UNCHANGED": sha(EO.C_TABLE_DOCS) == json.loads(EO.EVAL_AUTH.read_text())["C_TABLE_SHA256"],
                              "OUTCOME_FIELDS_READ_FOR_THIS_SNAPSHOT": False},
            "INVENTORY_METHOD": "seed field of each checkpoint row only; result files hashed, never opened",
            "COUNTS": inv["COUNTS"], "TOTAL_ROWS": inv["TOTAL_ROWS"], "REMAINING_MAX_ROWS": inv["REMAINING_MAX_ROWS"],
            "ALL_CONTIGUOUS": inv["ALL_CONTIGUOUS"], "SHARD_ROOT_SHA256": inv["ROOT_SHA256"], "SHARDS": inv["CELLS"]}
    SNAPSHOT.write_text(json.dumps(body, sort_keys=True, separators=(",", ":")) + "\n")
    return SNAPSHOT


def amend() -> Path:
    if AMENDMENT.exists():
        raise RuntimeError("resume amendment already exists; immutable")
    body = {"ARTIFACT": AMENDMENT.name, "IMMUTABLE": True, "RUN_ID": RUN_ID, "DATE": "2026-10-05", "KIND": "OPERATIONAL_AMENDMENT",
            "OWNER_DECISION": "2026-10-05 option 1: resume the same official EVAL phase after an infrastructure interruption; not failed; not restarted",
            "UNCHANGED": {"RESEARCH_STATISTICAL_SEMANTICS": True, "EXECUTOR_DIGEST": engine.executor_digest()["EXECUTOR_DIGEST"], "GRIDS_SEEDS_C_TABLE_CP_RULES_STAGE_RULES": "UNCHANGED"},
            "CHANGED": "only the operational disk gate for deterministic resume after an infrastructure interruption",
            "INITIAL_EVAL_GATE": {"REQUIRED_FREE_BYTES": 25_000_000_000, "APPLIES": "before the first EVAL replicate only; was satisfied at 30,242,562,048 bytes"},
            "RESUME_CAPACITY_RULE": {"REMAINING_MAX_ROWS": "sum over unfinished cells of (20000 - recorded frozen rows); completed cells 0; computed from frozen seed coverage only, never from observed PASS/FAIL/ESCALATE",
                                     "RESUME_REQUIRED_FREE_BYTES": "512 * REMAINING_MAX_ROWS + 2_000_000_000", "ALLOWED_IFF": "FREE_BYTES >= RESUME_REQUIRED_FREE_BYTES",
                                     "APPLICABLE_ONLY_AFTER": "a sealed interruption snapshot"},
            "RESUME_SEMANTICS": ["completed (CELL_ID, seed) rows never rerun", "partial cells continue only their missing frozen seeds", "cells with 20000 rows awaiting decision: decision/reduction only, zero new rows",
                                 "not-started cells use their original frozen seeds", "Stage-A locking unchanged", "no seeds beyond the frozen 20000 per cell", "no code repair during the resumed run",
                                 "a second infrastructure interruption may resume again under the same rule"],
            "PAST_ARTIFACTS_MODIFIED": False, "SNAPSHOT_SHA256": sha(SNAPSHOT)}
    AMENDMENT.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n")
    return AMENDMENT


def bind() -> Path:
    if BINDING.exists():
        raise RuntimeError("resume binding already exists; immutable")
    snap = json.loads(SNAPSHOT.read_text())
    inv = shard_inventory(parse_seeds=False)                      # file digests only; rows come from the sealed snapshot
    if inv["ROOT_SHA256"] != snap["SHARD_ROOT_SHA256"]:
        raise RuntimeError("shard inventory changed since the snapshot; STOP")
    inv["REMAINING_MAX_ROWS"] = snap["REMAINING_MAX_ROWS"]
    inv["RESUME_REQUIRED_FREE_BYTES"] = BYTES_PER_ROW * snap["REMAINING_MAX_ROWS"] + RESERVE_BYTES
    inv["TOTAL_ROWS"] = snap["TOTAL_ROWS"]
    remaining = [{"CELL_ID": r["CELL_ID"], "STATE": r["STATE"], "RECORDED_ROWS": r["ROWS"], "NEXT_SEED": r["FROZEN_SEED_RANGE"][0] + r["ROWS"],
                  "LAST_FROZEN_SEED": r["FROZEN_SEED_RANGE"][1], "REMAINING_MAX_ROWS": r["REMAINING_MAX_ROWS"]} for r in snap["SHARDS"] if r["STATE"] != "COMPLETED"]
    body = {"ARTIFACT": BINDING.name, "IMMUTABLE": True, "RUN_ID": RUN_ID, "PHASE": "EVAL_RESUME", "DATE": "2026-10-05",
            "ORIGINAL_EVAL_BINDING_SHA256": sha(EO.EVAL_BINDING), "ORIGINAL_EVAL_AUTHORIZATION_SHA256": sha(EO.EVAL_AUTH),
            "INTERRUPTION_SNAPSHOT_SHA256": sha(SNAPSHOT), "RESUME_AMENDMENT_SHA256": sha(AMENDMENT),
            "EXECUTOR": engine.executor_digest(), "RESUME_DRIVER": {"PATH": str(DRIVER.relative_to(REPO)), "SHA256": sha(DRIVER)},
            "ORIGINAL_EVAL_DRIVER_SHA256": sha(EO.DRIVER), "C_TABLE_SHA256": sha(EO.C_TABLE_DOCS),
            "SHARD_ROOT_SHA256": inv["ROOT_SHA256"], "COUNTS": inv["COUNTS"], "TOTAL_ROWS_RECORDED": inv["TOTAL_ROWS"],
            "REMAINING_FROZEN_SEED_SURFACE": {"CELLS": len(remaining), "REMAINING_MAX_ROWS": inv["REMAINING_MAX_ROWS"], "DETAIL_SHA256": sha_bytes(json.dumps(remaining, sort_keys=True, separators=(",", ":")).encode()), "DETAIL": remaining},
            "REMAINING_MAX_ROWS": inv["REMAINING_MAX_ROWS"], "RESUME_REQUIRED_FREE_BYTES": inv["RESUME_REQUIRED_FREE_BYTES"],
            "FREE_BYTES_AT_BINDING": shutil.disk_usage(REPO).free, "ENVIRONMENT": EO.environment()}
    BINDING.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n")
    return BINDING


def verify_binding() -> dict:
    b = json.loads(BINDING.read_text())
    checks = {"TREE_CLEAN": tree_clean(),
              "SNAPSHOT_COMMITTED_IDENTICAL": committed_sha(SNAPSHOT) == sha(SNAPSHOT) == b["INTERRUPTION_SNAPSHOT_SHA256"],
              "AMENDMENT_COMMITTED_IDENTICAL": committed_sha(AMENDMENT) == sha(AMENDMENT) == b["RESUME_AMENDMENT_SHA256"],
              "BINDING_COMMITTED_IDENTICAL": committed_sha(BINDING) == sha(BINDING),
              "DRIVER_COMMITTED_IDENTICAL": committed_sha(DRIVER) == sha(DRIVER) == b["RESUME_DRIVER"]["SHA256"],
              "EXECUTOR_EXACT_V4": engine.executor_digest() == b["EXECUTOR"] and b["EXECUTOR"]["EXECUTOR_DIGEST"] == json.loads(EO.EVAL_BINDING.read_text())["EXECUTOR"]["EXECUTOR_DIGEST"],
              "ORIGINAL_EVAL_CHAIN": sha(EO.EVAL_BINDING) == b["ORIGINAL_EVAL_BINDING_SHA256"] and sha(EO.EVAL_AUTH) == b["ORIGINAL_EVAL_AUTHORIZATION_SHA256"],
              "C_TABLE_MATCH": sha(EO.C_TABLE_DOCS) == b["C_TABLE_SHA256"] == sha(EO.RUN_DIR / ctable.C_TABLE_NAME),
              "SHARD_ROOT_UNCHANGED": shard_inventory(parse_seeds=False)["ROOT_SHA256"] == b["SHARD_ROOT_SHA256"]}
    return {"HEAD": head(), "BINDING_SHA256": sha(BINDING), "DRIVER_SHA256": sha(DRIVER), "CHECKS": checks, "OK": all(checks.values())}


def authorize() -> Path:
    if AUTH.exists():
        raise RuntimeError("resume authorization already exists; immutable")
    v = verify_binding()
    if not v["OK"]:
        raise RuntimeError(f"resume binding verification failed: {v['CHECKS']}; STOP")
    b = json.loads(BINDING.read_text())
    body = {"ARTIFACT": AUTH.name, "IMMUTABLE": True, "RUN_ID": RUN_ID, "PHASE": "EVAL_RESUME", "DATE": "2026-10-05",
            "RESUME_BINDING": {"PATH": str(BINDING.relative_to(REPO)), "SHA256": sha(BINDING), "COMMIT": head()},
            "INTERRUPTION_SNAPSHOT_SHA256": sha(SNAPSHOT), "EXECUTOR_DIGEST": engine.executor_digest()["EXECUTOR_DIGEST"], "DRIVER_SHA256": sha(DRIVER),
            "REMAINING_SEED_SURFACE_SHA256": b["REMAINING_FROZEN_SEED_SURFACE"]["DETAIL_SHA256"], "REMAINING_MAX_ROWS": b["REMAINING_MAX_ROWS"],
            "CAPACITY": {"RESUME_REQUIRED_FREE_BYTES": b["RESUME_REQUIRED_FREE_BYTES"], "RULE": "512 * REMAINING_MAX_ROWS + 2e9"},
            "NO_COMPLETED_SEED_RERUN": True, "NO_REPLACEMENT_SEEDS": True, "NO_STATISTICAL_RULE_CHANGE": True, "ONE_RESUMED_OFFICIAL_EVAL": True}
    AUTH.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n")
    return AUTH


def verify_authorization() -> dict:
    a = json.loads(AUTH.read_text())
    vb = verify_binding()
    free = shutil.disk_usage(REPO).free
    checks = {"TREE_CLEAN": tree_clean(), "AUTH_COMMITTED_IDENTICAL": committed_sha(AUTH) == sha(AUTH),
              "AUTH_BINDS_BINDING": a["RESUME_BINDING"]["SHA256"] == sha(BINDING), "BINDING_VERIFIES": vb["OK"],
              "PHASE_EVAL_RESUME": a["PHASE"] == "EVAL_RESUME" and a["NO_COMPLETED_SEED_RERUN"] and a["NO_REPLACEMENT_SEEDS"] and a["NO_STATISTICAL_RULE_CHANGE"],
              "CAPACITY_OK": free >= a["CAPACITY"]["RESUME_REQUIRED_FREE_BYTES"], "NO_PRIOR_EVAL_COMPLETION": not EO.EVAL_COMPLETION.exists()}
    return {"HEAD": head(), "AUTH_SHA256": sha(AUTH), "FREE_BYTES": free, "REQUIRED": a["CAPACITY"]["RESUME_REQUIRED_FREE_BYTES"], "CHECKS": checks, "OK": all(checks.values())}


# ----------------------------------------------------------------------------- resume execution

def _snapshot_prefix_unchanged(snap: dict) -> dict:
    """Every file present at the snapshot is still a byte-identical prefix of the current file (append-only)."""
    bad = []
    for r in snap["SHARDS"]:
        d = EO.EVAL_DIR / r["CELL_ID"]
        if "CHECKPOINT_SHA256" in r:
            p = d / "replicates.jsonl"
            with p.open("rb") as fh:
                prefix = fh.read(r["CHECKPOINT_BYTES"])
            if sha_bytes(prefix) != r["CHECKPOINT_SHA256"]:
                bad.append(r["CELL_ID"])
        if "RESULT_SHA256" in r and sha(d / "result.json") != r["RESULT_SHA256"]:
            bad.append(r["CELL_ID"])
    return {"SNAPSHOT_FILES_UNCHANGED": not bad, "CHANGED": bad}


def execute() -> dict:
    for k, v in EO.THREAD_ENV.items():
        if os.environ.get(k) != v:
            raise RuntimeError(f"{k} must be {v}")
    va = verify_authorization()
    if not va["OK"]:
        raise RuntimeError(f"resume authorization verification failed: {va['CHECKS']}; STOP")
    snap = json.loads(SNAPSHOT.read_text())
    started = datetime.now(timezone.utc).isoformat()
    t0 = time.time()
    cells = C.eval_cells()
    EO._worker_init()
    results = []
    with mp.get_context("fork").Pool(EO.WORKERS, initializer=EO._worker_init) as pool:
        for res in pool.imap_unordered(EO._run_cell, cells, chunksize=1):
            results.append(res)
    elapsed = time.time() - t0
    results.sort(key=lambda r: (r["CLASS"], r["CELL_ID"]))
    integrity = EO._integrity(cells)
    integrity.update(_snapshot_prefix_unchanged(snap))
    integrity["EXECUTOR_UNCHANGED"] = engine.executor_digest()["EXECUTOR_DIGEST"] == snap["EXECUTOR"]["EXECUTOR_DIGEST"]
    integrity["C_TABLE_UNCHANGED"] = sha(EO.C_TABLE_DOCS) == snap["C_TABLE_SHA256"] == sha(EO.RUN_DIR / ctable.C_TABLE_NAME)
    if integrity["STOP"] or not integrity["SNAPSHOT_FILES_UNCHANGED"] or not integrity["EXECUTOR_UNCHANGED"] or not integrity["C_TABLE_UNCHANGED"]:
        (EO.RUN_DIR / "EVAL_PHASE_EXECUTION_ERROR.json").write_text(json.dumps({k: v for k, v in integrity.items() if k != "SHARD_DIGESTS"}, indent=2) + "\n")
        raise RuntimeError("EVAL integrity failure after resume; STOP")
    f = C.frozen()
    agg = AG.aggregate(results, f["REALISTIC_MAX"], f["SUPPORTED_RANGE"])
    common = {"RUN_ID": RUN_ID, "EVAL_AUTHORIZATION_SHA256": sha(EO.EVAL_AUTH), "EVAL_BINDING_SHA256": sha(EO.EVAL_BINDING),
              "INTERRUPTION_SNAPSHOT_SHA256": sha(SNAPSHOT), "RESUME_AMENDMENT_SHA256": sha(AMENDMENT), "RESUME_BINDING_SHA256": sha(BINDING),
              "RESUME_AUTHORIZATION_SHA256": sha(AUTH), "EXECUTOR_DIGEST": engine.executor_digest()["EXECUTOR_DIGEST"], "C_TABLE_SHA256": sha(EO.C_TABLE_DOCS),
              "V4_INPUTS": EO.frozen_digests(), "CHECKPOINT_SHA256": integrity["CHECKPOINT_SHA256"]}
    EO.RESULT.write_text(json.dumps({"ARTIFACT": EO.RESULT.name, "IMMUTABLE": True, **common, "CELLS": results}, sort_keys=True, separators=(",", ":")) + "\n")
    EO.AGGREGATION.write_text(json.dumps({"ARTIFACT": EO.AGGREGATION.name, "IMMUTABLE": True, **common, "RESULT_SHA256": sha(EO.RESULT), **agg}, indent=2, sort_keys=True) + "\n")
    esc_cells = sum(1 for r in results if r["ESCALATED"])
    esc_checks = sum(1 for r in results for x in engine.CANDIDATES for m in engine.METRICS if r["CHECKS"][x][m]["STAGE_A"] == "ESCALATE")
    completion = {"ARTIFACT": EO.EVAL_COMPLETION.name, "IMMUTABLE": True, **common, "PHASE": "EVAL", "STATUS": "COMPLETE", "RESUMED_AFTER_INTERRUPTION": True,
                  "PRE_RESTART_ROWS": snap["TOTAL_ROWS"], "RESUME_STARTED_UTC": started, "FINISHED_UTC": datetime.now(timezone.utc).isoformat(), "RESUME_ELAPSED_SECONDS": round(elapsed, 1),
                  "ORIGINAL_EVAL_STARTED_UTC": "2026-10-05T04:54 UTC (approx.; original driver stdout lost at container restart)",
                  "COMMIT": head(), "RESUME_DRIVER_SHA256": sha(DRIVER), "ORIGINAL_EVAL_DRIVER_SHA256": sha(EO.DRIVER),
                  "INTEGRITY": {k: v for k, v in integrity.items() if k != "SHARD_DIGESTS"}, "ESCALATED_CELLS": esc_cells, "ESCALATED_CHECKS": esc_checks,
                  "RESULT_SHA256": sha(EO.RESULT), "AGGREGATION_SHA256": sha(EO.AGGREGATION), "GLOBAL_STATUS": agg["GLOBAL_STATUS"],
                  "CAL_RERUN": False, "RUN1_OUTCOMES_USED": False}
    EO.EVAL_COMPLETION.write_text(json.dumps(completion, indent=2, sort_keys=True) + "\n")
    return completion


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["snapshot", "amend", "bind", "verify-binding", "authorize", "verify-authorization", "execute"])
    a = ap.parse_args()
    fn = {"snapshot": snapshot, "amend": amend, "bind": bind, "authorize": authorize}.get(a.step)
    if fn is not None:
        p = fn()
        print(p, sha(p))
    elif a.step == "verify-binding":
        print(json.dumps(verify_binding(), indent=1))
    elif a.step == "verify-authorization":
        print(json.dumps(verify_authorization(), indent=1))
    else:
        out = execute()
        out.pop("INTEGRITY", None)
        print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
