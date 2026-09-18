"""NON_PRODUCTION_PERFORMANCE_DIAGNOSTIC for HARNESS_PERFORMANCE_V1.

Structurally incapable of:
- treating an ARM as permission to run production
- consuming production authority
- creating canonical RESULT / WORLD_RECORDS / reservation / claim
- touching validation 2025, OOS 2026, B2-06, or real market data

This module exercises the expensive production evaluation path
(`_evaluate_planned_world_body`) on a bounded non-production plan.
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import time
from typing import Any, Sequence

from scripts.research.harness_synthetic_edge_calibration_v1_lib import (
    PRODUCTION_PLANNED_TOTAL_WORLDS,
    PRODUCTION_PRIMARY_N,
    PRODUCTION_SMALL_N,
    SyntheticExecutionNotAuthorized,
)
from scripts.research.harness_synthetic_edge_calibration_v1_production import (
    CANONICAL_CLAIM_PATH,
    CANONICAL_PARTIAL_PATH,
    CANONICAL_RESERVATION_PATH,
    CANONICAL_RESULT_PATH,
    CANONICAL_WORLD_RECORDS_PATH,
    _jsonable,
    _record_content_digest,
    assemble_canonical_world_records,
    canonical_json_bytes,
    evaluate_planned_jobs_fail_closed,
    planned_production_jobs,
    resolve_execution_workers,
)

DIAGNOSTIC_LABEL = "NON_PRODUCTION_PERFORMANCE_DIAGNOSTIC"
DIAGNOSTIC_N_ROWS = 80
PRODUCTION_N = frozenset({int(PRODUCTION_PRIMARY_N), *[int(n) for n in PRODUCTION_SMALL_N]})
FORBIDDEN_CANONICAL_PATHS = (
    CANONICAL_RESULT_PATH,
    CANONICAL_WORLD_RECORDS_PATH,
    CANONICAL_RESERVATION_PATH,
    CANONICAL_CLAIM_PATH,
    CANONICAL_PARTIAL_PATH,
)


def _refuse_diagnostic(detail: str) -> None:
    raise SyntheticExecutionNotAuthorized(
        f"SYNTHETIC_EXECUTION_NOT_AUTHORIZED: {DIAGNOSTIC_LABEL} {detail}"
    )


def assert_non_production_jobs(jobs: Sequence[tuple[str, int, int]]) -> None:
    planned = tuple((str(job[0]), int(job[1]), int(job[2])) for job in jobs)
    if not planned:
        _refuse_diagnostic("diagnostic plan is empty")
    if len(planned) >= int(PRODUCTION_PLANNED_TOTAL_WORLDS):
        _refuse_diagnostic("cannot encode the frozen 3200-world production grid")
    try:
        production_plan = planned_production_jobs()
    except Exception:
        production_plan = ()
    if planned == tuple(production_plan):
        _refuse_diagnostic("cannot encode the frozen 3200-world production grid")
    for scenario_id, n_rows, world_index in planned:
        if int(n_rows) in PRODUCTION_N:
            _refuse_diagnostic("cannot encode production N")
        if int(world_index) < 0:
            _refuse_diagnostic("world index is invalid")
        if not str(scenario_id):
            _refuse_diagnostic("world identity is invalid")


def diagnostic_jobs() -> tuple[tuple[str, int, int], ...]:
    """Bounded deterministic jobs. Not production N and not the 3200-world plan."""
    jobs = (
        ("EASY", DIAGNOSTIC_N_ROWS, 0),
        ("NULL", DIAGNOSTIC_N_ROWS, 0),
        ("EASY", DIAGNOSTIC_N_ROWS, 1),
    )
    assert_non_production_jobs(jobs)
    return jobs


def _canonical_paths_must_remain_absent(repo_root) -> None:
    root = repo_root
    for rel in FORBIDDEN_CANONICAL_PATHS:
        if (root / rel).exists():
            _refuse_diagnostic(f"refuses to run while canonical artifact exists: {rel}")


def run_non_production_performance_diagnostic(
    jobs: Sequence[tuple[str, int, int]] | None = None,
    *,
    workers: int = 1,
    repo_root=None,
) -> dict[str, Any]:
    """Evaluate a bounded plan without ARM permission or canonical writes."""
    from pathlib import Path

    from scripts.research.harness_synthetic_edge_calibration_v1_production import (
        _repo_root,
    )

    root = Path(repo_root) if repo_root is not None else _repo_root()
    _canonical_paths_must_remain_absent(root)
    planned = diagnostic_jobs() if jobs is None else tuple(
        (str(job[0]), int(job[1]), int(job[2])) for job in jobs
    )
    assert_non_production_jobs(planned)
    workers_n = resolve_execution_workers(workers)
    records = evaluate_planned_jobs_fail_closed(planned, workers=workers_n)
    ordered = assemble_canonical_world_records(
        planned_jobs=planned, completed_records=records
    )
    payload = {
        "label": DIAGNOSTIC_LABEL,
        "not_a_production_result": True,
        "scientific_result_exists": False,
        "authority_consumed": False,
        "production_monte_carlo_arm_authorized": False,
        "real_market_data_access_authorized": False,
        "b2_06_scientific_execution_authorized": False,
        "validation_2025_authorized": False,
        "oos_2026_authorized": False,
        "workers": workers_n,
        "planned_jobs": [list(job) for job in planned],
        "records": ordered,
        "record_digest_chain": [_record_content_digest(rec) for rec in ordered],
        "world_identities": [str(rec["world_identity"]) for rec in ordered],
        "world_seeds": [int(rec["world_seed"]) for rec in ordered],
        "world_set_sha256": __import__("hashlib")
        .sha256(
            canonical_json_bytes(
                {"label": DIAGNOSTIC_LABEL, "worlds": [_jsonable(dict(rec)) for rec in ordered]}
            )
        )
        .hexdigest(),
    }
    _canonical_paths_must_remain_absent(root)
    return payload


def rss_peak_kb() -> int:
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


def time_call(fn, *args, **kwargs) -> tuple[Any, dict[str, float]]:
    cpu0 = time.process_time()
    wall0 = time.perf_counter()
    result = fn(*args, **kwargs)
    wall = time.perf_counter() - wall0
    cpu = time.process_time() - cpu0
    return result, {
        "wall_s": float(wall),
        "cpu_s": float(cpu),
        "cpu_utilization": float(cpu / wall) if wall > 0 else 0.0,
        "rss_peak_kb": float(rss_peak_kb()),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=DIAGNOSTIC_LABEL)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument(
        "--run-production-grid",
        action="store_true",
        help="rejected: this diagnostic cannot invoke production",
    )
    args = parser.parse_args(argv)
    if args.run_production_grid:
        print(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: "
            f"{DIAGNOSTIC_LABEL} cannot invoke production",
            file=__import__("sys").stderr,
        )
        return 2
    try:
        payload = run_non_production_performance_diagnostic(workers=int(args.workers))
    except SyntheticExecutionNotAuthorized as exc:
        print(str(exc), file=__import__("sys").stderr)
        return 2
    print(json.dumps(_jsonable(payload), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
