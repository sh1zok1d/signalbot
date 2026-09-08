#!/usr/bin/env python3
"""Fail-closed entrypoint for HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1.

Fixture-only implementation review may import helpers from
``harness_synthetic_edge_calibration_v1_lib``. This CLI cannot run the frozen
3200-world production grid and accepts no authorization flag or environment
bypass.
"""

from __future__ import annotations

import argparse
import json
import sys

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
            "Production execution is not authorized."
        )
    )
    parser.add_argument(
        "--identity",
        action="store_true",
        help="print implementation-review identity JSON (no execution)",
    )
    parser.add_argument(
        "--describe-grid",
        action="store_true",
        help="print the frozen grid descriptor without running it",
    )
    parser.add_argument(
        "--run-production-grid",
        action="store_true",
        help="always fails closed; production calibration is not authorized",
    )
    args = parser.parse_args(argv)
    if args.identity:
        print(json.dumps(implementation_identity(), sort_keys=True, indent=2))
        return 0
    if args.describe_grid:
        print(json.dumps(planned_production_grid_descriptor(), sort_keys=True, indent=2))
        return 0
    if args.run_production_grid:
        try:
            run_frozen_production_grid()
        except SyntheticExecutionNotAuthorized as exc:
            print(str(exc), file=sys.stderr)
            return 2
    print("SYNTHETIC_EXECUTION_NOT_AUTHORIZED", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
