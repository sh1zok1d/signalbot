#!/usr/bin/env python3
"""Fail-closed entrypoint for HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1.

Production execution is authorized only by the tracked one-shot artifact in
the exact Git HEAD. This CLI accepts no authorize/force/unsafe flag, no
environment bypass, and no caller authority path. It does not run the
3200-world Monte Carlo in this authorization stage.
"""

from __future__ import annotations

import argparse
import json
import sys

from scripts.research.harness_synthetic_edge_calibration_v1_auth import (
    AuthorizedExecutionBoundaryReached,
)
from scripts.research.harness_synthetic_edge_calibration_v1_lib import (
    SyntheticExecutionNotAuthorized,
    implementation_identity,
    planned_production_grid_descriptor,
    run_frozen_production_grid,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 entrypoint. "
            "One-shot production execution is authorized only by tracked Git state."
        )
    )
    parser.add_argument(
        "--identity",
        action="store_true",
        help="print implementation/authorization identity JSON (no execution)",
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
            "verify tracked one-shot authorization and reach the production "
            "execution boundary without running the Monte Carlo in this stage"
        ),
    )
    parser.add_argument(
        "--expected-head",
        default=None,
        help="optional exact HEAD SHA confirmation; cannot authorize by itself",
    )
    args = parser.parse_args(argv)
    if args.expected_head:
        from scripts.research.harness_synthetic_edge_calibration_v1_auth import _head_sha, _repo_root

        actual = _head_sha(_repo_root())
        if actual != args.expected_head.strip().lower():
            print("SYNTHETIC_EXECUTION_NOT_AUTHORIZED: expected-head mismatch", file=sys.stderr)
            return 2
    if args.identity:
        print(json.dumps(implementation_identity(), sort_keys=True, indent=2))
        return 0
    if args.describe_grid:
        print(json.dumps(planned_production_grid_descriptor(), sort_keys=True, indent=2))
        return 0
    if args.run_production_grid:
        try:
            run_frozen_production_grid()
        except AuthorizedExecutionBoundaryReached as exc:
            print(
                json.dumps(
                    {
                        "status": "AUTHORIZED_UNUSED_PRODUCTION_EXECUTION_BOUNDARY",
                        "production_calibration_executed": False,
                        "authorization_consumed": False,
                        "monte_carlo_invoked": False,
                        "authorization_id": exc.proof.authorization_id,
                        "authorization_blob_sha256": exc.proof.authorization_blob_sha256,
                        "head_sha": exc.proof.head_sha,
                        "tree_sha": exc.proof.tree_sha,
                    },
                    sort_keys=True,
                    indent=2,
                )
            )
            return 0
        except SyntheticExecutionNotAuthorized as exc:
            print(str(exc), file=sys.stderr)
            return 2
    print("SYNTHETIC_EXECUTION_NOT_AUTHORIZED", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
