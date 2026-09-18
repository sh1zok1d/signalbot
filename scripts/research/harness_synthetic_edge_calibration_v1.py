#!/usr/bin/env python3
"""Fail-closed entrypoint for HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1.

Canonical production execution, if later armed by a separate unit, must spawn a
fresh Python interpreter and re-verify exact HEAD/tree plus execution-authority
bytes inside that process. This durability unit does not arm Monte Carlo, does
not mint a production RESULT, and does not keep #114 local reservation executable
after authority-code changes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from scripts.research.harness_synthetic_edge_calibration_v1_lib import (
    SyntheticExecutionNotAuthorized,
    planned_production_grid_descriptor,
)
from scripts.research.harness_synthetic_edge_calibration_v1_production import (
    EXECUTION_WORKERS_ENV,
    production_durability_identity,
    resolve_execution_workers,
    spawn_canonical_production_process,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 entrypoint. "
            "Production execution remains fail-closed until a later arming unit."
        )
    )
    parser.add_argument(
        "--identity",
        action="store_true",
        help="print durability/authorization identity JSON (no execution)",
    )
    parser.add_argument(
        "--describe-grid",
        action="store_true",
        help="print the frozen grid descriptor without running it",
    )
    parser.add_argument(
        "--run-production-grid",
        action="store_true",
        help=(
            "spawn a fresh interpreter, re-verify executed-byte authority, "
            "and fail closed while production remains unarmed"
        ),
    )
    parser.add_argument(
        "--expected-head",
        default=None,
        help="optional exact HEAD SHA confirmation; cannot authorize by itself",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help=(
            "explicit world-level worker count for --run-production-grid "
            f"(env {EXECUTION_WORKERS_ENV}; default 1; does not authorize execution)"
        ),
    )
    args = parser.parse_args(argv)
    if args.expected_head:
        from scripts.research.harness_synthetic_edge_calibration_v1_auth import (
            _head_sha,
            _repo_root,
        )

        actual = _head_sha(_repo_root())
        if actual != args.expected_head.strip().lower():
            print("SYNTHETIC_EXECUTION_NOT_AUTHORIZED: expected-head mismatch", file=sys.stderr)
            return 2
    if args.identity:
        print(json.dumps(production_durability_identity(), sort_keys=True, indent=2))
        return 0
    if args.describe_grid:
        print(json.dumps(planned_production_grid_descriptor(), sort_keys=True, indent=2))
        return 0
    if args.run_production_grid:
        try:
            workers = resolve_execution_workers(int(args.workers))
        except SyntheticExecutionNotAuthorized as exc:
            print(str(exc), file=sys.stderr)
            return 2
        os.environ[EXECUTION_WORKERS_ENV] = str(workers)
        try:
            return int(spawn_canonical_production_process())
        except SyntheticExecutionNotAuthorized as exc:
            print(str(exc), file=sys.stderr)
            return 2
    print("SYNTHETIC_EXECUTION_NOT_AUTHORIZED", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
