"""Spawn-worker entry for HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1.

BLAS/OpenMP thread limits are applied before numpy is imported. This module
is a thin execution shim. It is not production authorization, does not read
an ARM, and does not mint RESULT or WORLD_RECORDS. Worker identity, PID,
wall clock, and completion order must not seed science.

Tracked execution authority must pin this file's bytes. The unused ARM at
0abc5fe does not authorize this module. A worker-byte change after freeze must
invalidate that freeze/ARM.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

_BLAS_THREAD_LIMIT_KEYS = (
    "OPENBLAS_NUM_THREADS",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)
for _key in _BLAS_THREAD_LIMIT_KEYS:
    os.environ[_key] = "1"

TEST_WORKER_CRASH_ENV = "HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_TEST_WORKER_CRASH"
_PINNED_WORKER_SHA256 = None
_PINNED_WORKER_PATH = None


def assert_pinned_worker_bytes(expected_sha256: str, expected_path: str) -> None:
    """Refuse if this process is not executing the git-pinned worker file."""
    global _PINNED_WORKER_SHA256, _PINNED_WORKER_PATH
    here = Path(__file__).resolve()
    expected = Path(expected_path).resolve()
    if here != expected:
        raise RuntimeError("worker module is not the pinned execution path")
    digest = hashlib.sha256(here.read_bytes()).hexdigest()
    if digest != str(expected_sha256).strip().lower():
        raise RuntimeError("worker bytes do not match tracked execution authority")
    _PINNED_WORKER_SHA256 = str(expected_sha256).strip().lower()
    _PINNED_WORKER_PATH = str(expected)


def multiprocessing_worker_init(expected_sha256: str, expected_path: str) -> None:
    """Pool initializer. Re-checks worker bytes after spawn import."""
    for key in _BLAS_THREAD_LIMIT_KEYS:
        os.environ[key] = "1"
    assert_pinned_worker_bytes(expected_sha256, expected_path)


def evaluate_job_payload(payload):
    """Evaluate one planned world from a pickleable (scenario_id, n, index) tuple."""
    if os.environ.get(TEST_WORKER_CRASH_ENV) == "1":
        raise RuntimeError(
            "NON_PRODUCTION_PERFORMANCE_DIAGNOSTIC injected worker crash"
        )
    if _PINNED_WORKER_SHA256 is not None:
        assert_pinned_worker_bytes(_PINNED_WORKER_SHA256, _PINNED_WORKER_PATH)
    scenario_id, n_rows, world_index = payload
    from scripts.research.harness_synthetic_edge_calibration_v1_production import (
        _evaluate_planned_world_body,
    )

    return _evaluate_planned_world_body(str(scenario_id), int(n_rows), int(world_index))
