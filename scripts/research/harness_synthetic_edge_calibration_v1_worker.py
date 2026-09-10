"""Spawn-worker entry for HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1.

BLAS/OpenMP thread limits are applied before numpy is imported. This module
is a thin execution shim. It is not production authorization, does not read
an ARM, and does not mint RESULT or WORLD_RECORDS. Worker identity, PID,
wall clock, and completion order must not seed science.

A future ARM that authorizes a performance-optimized production HEAD must pin
this file's bytes. The unused ARM at 0abc5fe does not authorize this module.
"""

from __future__ import annotations

import os

_BLAS_THREAD_LIMIT_KEYS = (
    "OPENBLAS_NUM_THREADS",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)
for _key in _BLAS_THREAD_LIMIT_KEYS:
    os.environ[_key] = "1"

TEST_WORKER_CRASH_ENV = "HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_TEST_WORKER_CRASH"


def evaluate_job_payload(payload):
    """Evaluate one planned world from a pickleable (scenario_id, n, index) tuple."""
    if os.environ.get(TEST_WORKER_CRASH_ENV) == "1":
        raise RuntimeError(
            "NON_PRODUCTION_PERFORMANCE_DIAGNOSTIC injected worker crash"
        )
    scenario_id, n_rows, world_index = payload
    from scripts.research.harness_synthetic_edge_calibration_v1_production import (
        _evaluate_planned_world_body,
    )

    return _evaluate_planned_world_body(str(scenario_id), int(n_rows), int(world_index))
