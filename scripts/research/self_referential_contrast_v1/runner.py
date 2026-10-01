"""Parallel validation runner.

Parallelism is across outer worlds. Draw streams are indexed by world
identity, so worker count, completion order, and chunk size do not change
results. Official screens are not launched by this module's import.
"""

from __future__ import annotations

from scripts.research.self_referential_contrast_v1 import env_limits as _env_limits  # noqa: F401

import multiprocessing as mp
import os
import time
from dataclasses import dataclass
from typing import Sequence

from scripts.research.self_referential_contrast_v1.constants import (
    R_VALIDATION,
    STATUS_PRIMARY_COMPLETED,
)
from scripts.research.self_referential_contrast_v1.contrast import indexed_epsilon_sampler, run_primary
from scripts.research.self_referential_contrast_v1.dgp import build_generic_world
from scripts.research.self_referential_contrast_v1.seeds import world_entropy
from scripts.research.self_referential_contrast_v1.validation_protocol import (
    FAIL_CLOSED_STATUSES,
    WorldSpec,
)


@dataclass(frozen=True)
class WorldResult:
    suite_id: str
    configuration_id: str
    world_index: int
    seed_digest: str
    reject: bool
    p_value: float | None
    variance_status: str
    runtime_seconds: float
    geometry_id: str
    region_id: str
    family: str
    t_count: int | None
    process_time_seconds: float


def default_worker_count() -> int:
    cpu = os.cpu_count() or 1
    return max(1, min(cpu, 8))


def execute_world(spec: WorldSpec, *, replicates: int, purpose: str, draw_batch_size: int = 64) -> WorldResult:
    started = time.perf_counter()
    cpu_started = time.process_time()
    entropy = world_entropy(
        suite_id=spec.suite_id,
        configuration_id=spec.configuration_id,
        world_index=spec.world_index,
        purpose=purpose,
    )
    data = build_generic_world(spec, purpose=purpose)
    result = run_primary(
        data,
        replicates=replicates,
        epsilon_sampler=indexed_epsilon_sampler(entropy),
        compute_sensitivity=False,
        draw_batch_size=draw_batch_size,
    )
    status = str(result["inference_status"])
    reject = bool(result["primary_reject"]) if status == STATUS_PRIMARY_COMPLETED else False
    return WorldResult(
        suite_id=spec.suite_id,
        configuration_id=spec.configuration_id,
        world_index=spec.world_index,
        seed_digest=entropy.hex(),
        reject=reject,
        p_value=None if result["p_value"] is None else float(result["p_value"]),
        variance_status=status,
        runtime_seconds=time.perf_counter() - started,
        geometry_id=spec.geometry_id,
        region_id=spec.region_id,
        family=spec.family,
        t_count=spec.t_count,
        process_time_seconds=time.process_time() - cpu_started,
    )


def execute_chunk(payload: tuple[tuple[WorldSpec, ...], int, str, int]) -> tuple[WorldResult, ...]:
    specs, replicates, purpose, draw_batch_size = payload
    return tuple(
        execute_world(spec, replicates=replicates, purpose=purpose, draw_batch_size=draw_batch_size)
        for spec in specs
    )


def sort_results(results: Sequence[WorldResult]) -> tuple[WorldResult, ...]:
    return tuple(sorted(results, key=lambda item: (item.suite_id, item.configuration_id, item.world_index)))


def run_worlds(
    specs: Sequence[WorldSpec],
    *,
    workers: int,
    chunk_size: int,
    replicates: int = R_VALIDATION,
    purpose: str,
    draw_batch_size: int = 64,
) -> tuple[WorldResult, ...]:
    if workers < 1:
        raise ValueError("workers must be positive")
    if chunk_size < 1:
        raise ValueError("chunk size must be positive")
    chunks = [
        (tuple(specs[index : index + chunk_size]), replicates, purpose, draw_batch_size)
        for index in range(0, len(specs), chunk_size)
    ]
    if workers == 1:
        nested = [execute_chunk(chunk) for chunk in chunks]
    else:
        context = mp.get_context("spawn")
        with context.Pool(processes=workers) as pool:
            nested = pool.map(execute_chunk, chunks)
    flat = [item for chunk in nested for item in chunk]
    return sort_results(flat)


def failed_closed(results: Sequence[WorldResult]) -> bool:
    return any(item.variance_status in FAIL_CLOSED_STATUSES for item in results)
