"""Development-only compute benchmark.

This is not statistical validation. It does not execute the official
1600-world screens. Cases are read from the amendment JSON.
"""

from __future__ import annotations

from scripts.research.self_referential_contrast_v1 import env_limits as _env_limits  # noqa: F401

import argparse
import json
import resource
import time
from pathlib import Path

import numpy as np

from scripts.research.self_referential_contrast_v1.constants import (
    PURPOSE_DEVELOPMENT_BENCHMARK,
    R_CONFIRMATORY,
    R_VALIDATION,
)
from scripts.research.self_referential_contrast_v1.contrast import (
    ContrastInput,
    indexed_epsilon_sampler,
    run_primary,
)
from scripts.research.self_referential_contrast_v1.runner import default_worker_count, run_worlds
from scripts.research.self_referential_contrast_v1.seeds import generator_from_digest, world_entropy
from scripts.research.self_referential_contrast_v1.validation_protocol import generic_world_specs


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _amendment_path() -> Path:
    return _repo_root() / "docs/research/INFERENCE_PROFILE_SELF_REFERENTIAL_VALIDATION_PROTOCOL_AMENDMENT_V1.json"


def load_benchmark_cases() -> list[dict]:
    document = json.loads(_amendment_path().read_text(encoding="utf-8"))
    return list(document["development_benchmark_cases"])


def synthetic_case(t_count: int, h_mechanical: int, *, gap: bool) -> ContrastInput:
    entropy = world_entropy(
        suite_id="DEVELOPMENT_BENCHMARK",
        configuration_id=f"T={t_count}|H={h_mechanical}|gap={int(gap)}",
        world_index=0,
        purpose=PURPOSE_DEVELOPMENT_BENCHMARK,
    )
    generator = generator_from_digest(entropy, spawn_key=(2,))
    state = (generator.random(t_count + 2) < 0.30).astype(np.float64)
    if gap:
        mid = t_count // 2
        x = np.concatenate([state[:mid], state[mid + 1 : t_count + 1]])
        y = np.concatenate([state[1 : mid + 1], state[mid + 2 : t_count + 2]])
        segment = np.concatenate([np.zeros(mid, dtype=np.int64), np.ones(t_count - mid, dtype=np.int64)])
    else:
        x = state[:-1]
        y = state[1:]
        segment = np.zeros(t_count, dtype=np.int64)
        x = x[:t_count]
        y = y[:t_count]
    block = np.asarray(["b0" if index < t_count // 2 else "b1" for index in range(x.shape[0])], dtype=object)
    return ContrastInput(
        x=x,
        y=y,
        cell=np.full(x.shape[0], "c0", dtype=object),
        block=block,
        segment_id=segment[: x.shape[0]],
        declared_cells=("c0",),
        h_mechanical=h_mechanical,
        metadata={"benchmark": True},
    )


def time_primary(t_count: int, h_mechanical: int, replicates: int, *, gap: bool) -> dict:
    data = synthetic_case(t_count, h_mechanical, gap=gap)
    entropy = world_entropy(
        suite_id="DEVELOPMENT_BENCHMARK",
        configuration_id=f"draws|T={t_count}|H={h_mechanical}",
        world_index=1,
        purpose=PURPOSE_DEVELOPMENT_BENCHMARK,
    )
    started = time.perf_counter()
    cpu = time.process_time()
    result = run_primary(
        data,
        replicates=replicates,
        epsilon_sampler=indexed_epsilon_sampler(entropy),
        compute_sensitivity=False,
        draw_batch_size=64,
    )
    elapsed = time.perf_counter() - started
    rss_kb, hwm_kb = _memory_kb()
    return {
        "T": t_count,
        "H_mechanical": h_mechanical,
        "B_T": result["B_T"],
        "R": replicates,
        "gap": gap,
        "wall_seconds": elapsed,
        "process_seconds": time.process_time() - cpu,
        "draws_per_second": replicates / elapsed if elapsed > 0 else None,
        "vm_rss_kb": rss_kb,
        "vm_hwm_kb": hwm_kb,
        "cpu_utilization": (time.process_time() - cpu) / elapsed if elapsed else None,
        "inference_status": result["inference_status"],
    }


def _memory_kb() -> tuple[int | None, int | None]:
    rss = hwm = None
    try:
        for line in Path("/proc/self/status").read_text(encoding="utf-8").splitlines():
            if line.startswith("VmRSS:"):
                rss = int(line.split()[1])
            elif line.startswith("VmHWM:"):
                hwm = int(line.split()[1])
    except OSError:
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss, hwm


def time_speedup(case: dict, worker_counts: list[int], world_count: int) -> list[dict]:
    specs = []
    for spec in generic_world_specs():
        if spec.t_count == case["speedup_T"] and spec.gap == "none" and spec.block_count == 1:
            specs.append(spec)
        if len(specs) == world_count:
            break
    rows = []
    for workers in worker_counts:
        started = time.perf_counter()
        run_worlds(
            specs,
            workers=workers,
            chunk_size=1,
            replicates=case["speedup_R"],
            purpose=PURPOSE_DEVELOPMENT_BENCHMARK,
            draw_batch_size=32,
        )
        elapsed = time.perf_counter() - started
        rows.append({"workers": workers, "worlds": world_count, "wall_seconds": elapsed, "chunk_size": 1})
    baseline = rows[0]["wall_seconds"]
    for row in rows:
        row["speedup_vs_workers_1"] = baseline / row["wall_seconds"] if row["wall_seconds"] else None
        row["efficiency"] = row["speedup_vs_workers_1"] / row["workers"] if row["speedup_vs_workers_1"] else None
    return rows


def time_chunks(case: dict) -> list[dict]:
    specs = []
    for spec in generic_world_specs():
        if spec.t_count == case["chunk_T"]:
            specs.append(spec)
        if len(specs) == case["chunk_worlds"]:
            break
    rows = []
    for chunk_size in case["chunk_sizes"]:
        started = time.perf_counter()
        results = run_worlds(
            specs,
            workers=1,
            chunk_size=int(chunk_size),
            replicates=case["chunk_R"],
            purpose=PURPOSE_DEVELOPMENT_BENCHMARK,
        )
        rows.append(
            {
                "chunk_size": int(chunk_size),
                "wall_seconds": time.perf_counter() - started,
                "seed_digests": [item.seed_digest for item in results],
                "reject": [item.reject for item in results],
            }
        )
    return rows


def project(measurements: list[dict], speedups: list[dict]) -> dict:
    by_t = {row["T"]: row for row in measurements if row["R"] == R_VALIDATION and row.get("role") == "representative"}
    counts: dict[int, int] = {}
    for spec in generic_world_specs():
        counts[int(spec.t_count)] = counts.get(int(spec.t_count), 0) + 1
    generic_seconds = 0.0
    for t_count, count in counts.items():
        generic_seconds += count * (R_VALIDATION / by_t[t_count]["draws_per_second"])
    admission = next(row for row in measurements if row.get("role") == "admission_length")
    admission_seconds = D7_WORLD_N() * (R_VALIDATION / admission["draws_per_second"])
    high_r_counts: dict[int, int] = {}
    from scripts.research.self_referential_contrast_v1.validation_protocol import high_r_world_specs

    for spec in high_r_world_specs():
        high_r_counts[int(spec.t_count)] = high_r_counts.get(int(spec.t_count), 0) + 1
    high_r_seconds = 0.0
    for t_count, count in high_r_counts.items():
        high_r_seconds += count * (R_CONFIRMATORY / by_t[t_count]["draws_per_second"])
    return {
        "generic_world_counts_by_T": counts,
        "generic_1600_R_validation_seconds_workers_1": generic_seconds,
        "admission_1600_R_validation_seconds_workers_1": admission_seconds,
        "high_r_200_R_confirmatory_seconds_workers_1": high_r_seconds,
        "speedup_rows": [{key: value for key, value in row.items()} for row in speedups],
        "official_validation_executed": False,
        "operational_budget_authorized": False,
    }


def D7_WORLD_N() -> int:
    from scripts.research.self_referential_contrast_v1.constants import D7_ADMISSION_OUTER_WORLD_N

    return D7_ADMISSION_OUTER_WORLD_N


def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description="Development-only compute benchmark")
    parser.add_argument("--workers", type=int, default=0, help="0 uses the execution default; not a statistical parameter")
    parser.add_argument("--output", type=str, default="")
    args = parser.parse_args(argv)
    cases = load_benchmark_cases()
    measurements = []
    for case in cases:
        row = time_primary(int(case["T"]), int(case["h_mechanical"]), int(case["R"]), gap=bool(case["gap"]))
        row["name"] = case["name"]
        row["role"] = case["role"]
        measurements.append(row)
    worker_counts = [1, 2, 4]
    worker_counts = [count for count in worker_counts if count <= (os_cpu())]
    if args.workers:
        worker_counts = [count for count in worker_counts if count <= args.workers]
    speedup_case = {
        "speedup_T": 16384,
        "speedup_R": 999,
    }
    speedups = time_speedup(speedup_case, worker_counts, world_count=4)
    chunks = time_chunks({"chunk_T": 2048, "chunk_worlds": 4, "chunk_R": 20, "chunk_sizes": [1, 2, 4]})
    digest_sets = {tuple(row["seed_digests"]) for row in chunks}
    if len(digest_sets) != 1:
        raise RuntimeError("chunk size changed world seeds")
    projection = project(measurements, speedups)
    payload = {
        "measurements": measurements,
        "speedups": speedups,
        "chunk_rows": [
            {"chunk_size": row["chunk_size"], "wall_seconds": row["wall_seconds"]}
            for row in chunks
        ],
        "chunk_results_identical": True,
        "projection": projection,
        "default_workers": default_worker_count(),
        "cpu_count": os_cpu(),
        "official_validation_executed": False,
    }
    if args.output:
        Path(args.output).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return payload


def os_cpu() -> int:
    import os

    return os.cpu_count() or 1


if __name__ == "__main__":
    main()
