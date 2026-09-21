"""D3 PATH_MORPHOLOGY — close-path only, unconditional design."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from scripts.research.discovery_sprint_01 import common as C


SEARCH_SURFACE = list(C.D3_FUNCTIONALS)


def functionals_for_rows(rows: Sequence[C.DiscoveryRow]) -> dict[str, np.ndarray]:
    values = {name: [] for name in C.D3_FUNCTIONALS}
    for row in rows:
        computed = C.close_path_functionals(row.entry_open, row.future_closes)
        for name in C.D3_FUNCTIONALS:
            values[name].append(computed[name])
    return {name: np.asarray(items, dtype=np.float64) for name, items in values.items()}


def surrogate_functional_means(
    rows: Sequence[C.DiscoveryRow],
    *,
    seed: int,
    n_replicates: int,
    block_length: int,
) -> dict[str, np.ndarray]:
    pools = C.slot_pools_from_rows(rows, block_length=block_length)
    rng_means = {name: np.empty(n_replicates, dtype=np.float64) for name in C.D3_FUNCTIONALS}
    n_days = len(rows)
    for r in range(int(n_replicates)):
        # Independent replicate stream: seed + replicate index keeps the
        # frozen seed authoritative while remaining deterministic.
        paths = C.stratified_block_bootstrap_paths(
            pools, n_paths=n_days, seed=int(seed) + r * 1_000_003
        )
        acc = {name: 0.0 for name in C.D3_FUNCTIONALS}
        for path in paths:
            computed = C.close_path_functionals(1.0, path)
            for name in C.D3_FUNCTIONALS:
                acc[name] += computed[name]
        for name in C.D3_FUNCTIONALS:
            rng_means[name][r] = acc[name] / float(n_days)
    return rng_means


def evaluate_functionals(
    rows: Sequence[C.DiscoveryRow],
    *,
    seed: int = C.D3_NULL_SURROGATE_SEED,
    n_replicates: int = C.N_REPLICATES,
    block_length: int = C.D3_BLOCK_LENGTH,
) -> dict[str, Any]:
    observed = functionals_for_rows(rows)
    surrogate_means = surrogate_functional_means(
        rows, seed=seed, n_replicates=n_replicates, block_length=block_length
    )
    years = np.asarray([row.year for row in rows], dtype=np.int64)
    report: dict[str, Any] = {}
    all_gates = True
    for name in C.D3_FUNCTIONALS:
        emp = observed[name]
        emp_mean = float(np.mean(emp))
        null = surrogate_means[name]
        lo = float(np.percentile(null, 2.5))
        hi = float(np.percentile(null, 97.5))
        null_median = float(np.median(null))
        statistical = bool(emp_mean < lo or emp_mean > hi)
        if null_median == 0.0:
            practical = bool(abs(emp_mean - null_median) > 0.0) if name.startswith("TIME_") else False
        else:
            practical = bool(abs(emp_mean - null_median) > 0.15 * abs(null_median))
        direction = 1.0 if emp_mean > null_median else -1.0
        year_hits = 0
        year_detail: dict[str, Any] = {}
        for year in sorted(set(int(y) for y in years.tolist())):
            sel = years == year
            if not np.any(sel):
                continue
            y_mean = float(np.mean(emp[sel]))
            y_dir = 1.0 if y_mean > null_median else -1.0
            same = bool(y_dir == direction and y_mean != null_median)
            year_detail[str(year)] = {"mean": y_mean, "same_direction": same}
            if same:
                year_hits += 1
        temporal = bool(year_hits >= 3)
        collapsed = False
        if name != "TIME_TO_MAX_ABS_CLOSE_EXCURSION":
            # Terminal close return vs max close excursion identity check.
            terminal = np.asarray(
                [
                    max(0.0, (row.future_closes[-1] - row.entry_open) / row.entry_open)
                    if name == "MAX_UPSIDE_CLOSE_24H"
                    else max(0.0, (row.entry_open - row.future_closes[-1]) / row.entry_open)
                    for row in rows
                ],
                dtype=np.float64,
            )
            collapsed = bool(np.allclose(emp, terminal))
        else:
            collapsed = bool(np.all(emp == float(C.FUTURE_BARS - 1)))
        gate = bool(statistical and practical and temporal and not collapsed)
        all_gates = all_gates and gate
        report[name] = {
            "EMPIRICAL_MEAN": emp_mean,
            "SURROGATE_MEAN_MEDIAN": null_median,
            "SURROGATE_MEAN_P2_5": lo,
            "SURROGATE_MEAN_P97_5": hi,
            "STATISTICAL_THRESHOLD_MET": statistical,
            "PRACTICAL_MAGNITUDE_MET": practical,
            "TEMPORAL_CONSISTENCY_MET": temporal,
            "COLLAPSED_TO_TERMINAL": collapsed,
            "YEAR_BREAKDOWN": year_detail,
            "GATE_PASS": gate,
        }
    report["ALL_FUNCTIONAL_GATES_PASS"] = bool(all_gates)
    report["FUNCTIONAL_COUNT"] = len(C.D3_FUNCTIONALS)
    report["FUNCTIONALS"] = list(C.D3_FUNCTIONALS)
    report["BLOCK_LENGTH"] = int(block_length)
    return report


def classify_d3(report: Mapping[str, Any] | None, *, missing: Sequence[str]) -> str:
    if missing:
        return "BLOCKED_MISSING_LOCAL_DATA"
    if report is None:
        return "INCONCLUSIVE_DISCOVERY"
    if int(report.get("FUNCTIONAL_COUNT", -1)) != 3:
        return "INVALID_DISCOVERY"
    if any(report[name].get("COLLAPSED_TO_TERMINAL") for name in C.D3_FUNCTIONALS):
        return "INVALID_DISCOVERY"
    if report.get("ALL_FUNCTIONAL_GATES_PASS"):
        return "PROMISING_PROTOTYPE"
    return "NO_USEFUL_STRUCTURE"


def run_d3(
    *,
    implementation_commit: str,
    output_dir: Path | None = None,
    repo: Path | None = None,
    n_replicates: int = C.N_REPLICATES,
    core_perp: Mapping[int, C.PerpBar] | None = None,
    run_companions: bool = True,
) -> dict[str, Any]:
    base = repo or C.repo_root()
    log = C.OpenedFileLog()
    preflight = C.preflight_local_data(base)
    missing: list[str] = []
    if core_perp is None and not preflight["BTC_DATA_PRESENT"]:
        missing.append("CORE_BTC_BINANCE_V0_MONTHLY_PARQUET")
    if core_perp is None and not missing:
        try:
            core_perp = C.load_core_btc_5m(log, repo=base)
        except C.MissingLocalData as exc:
            missing.append(str(exc))
            core_perp = None
    rows: list[C.DiscoveryRow] = []
    report = None
    companions: dict[str, Any] = {}
    if core_perp is not None:
        rows = C.build_rows(core_perp, C.D3_INTERVAL_START, C.DISCOVERY_END)
        if not rows:
            missing.append("D3_ZERO_ELIGIBLE_ROWS")
        else:
            report = evaluate_functionals(rows, n_replicates=n_replicates)
            if run_companions:
                for block in C.D3_COMPANION_BLOCKS:
                    companions[str(block)] = evaluate_functionals(
                        rows,
                        seed=C.D3_NULL_SURROGATE_SEED,
                        n_replicates=n_replicates,
                        block_length=block,
                    )
    classification = classify_d3(report, missing=missing)
    payload = {
        "DISCOVERY_ID": "D3",
        "NAME": "PATH_MORPHOLOGY",
        "SPEC_AUTHORITY": C.SPEC_AUTHORITY,
        "IMPLEMENTATION_COMMIT": implementation_commit,
        "DATASET_IDENTITIES": {C.CORE_BTC_DATASET_ID: C.CORE_BTC_SNAPSHOT},
        "INTERVAL_USED": "2020-02-01T00:05:00Z -> 2025-01-01T00:00:00Z exclusive",
        "FILES_OPENED": list(log.files),
        "SEARCH_SURFACE_ATTEMPTED": SEARCH_SURFACE,
        "SEEDS": {"D3_NULL_SURROGATE_SEED": C.D3_NULL_SURROGATE_SEED},
        "ROW_COUNTS": {"N": len(rows)},
        "YEAR_BREAKDOWN": C.year_counts(rows),
        "PRIMARY_METRICS": report or {},
        "BASELINE_METRICS": {
            "NULL": "5m_RETURN_TIME_OF_DAY_STRATIFIED_BLOCK_BOOTSTRAP",
            "BLOCK_LENGTH": C.D3_BLOCK_LENGTH,
            "COMPANION_BLOCK_LENGTHS": list(C.D3_COMPANION_BLOCKS),
            "COMPANIONS": companions,
        },
        "PROTOTYPE_GATE_FIELDS": {
            "statistical_threshold": "empirical mean outside surrogate-mean [2.5, 97.5]",
            "practical_magnitude_threshold": "|emp_mean - surrogate_median| > 15% of |surrogate_median|",
            "temporal_consistency_check": "at least 3 year-buckets same-direction vs surrogate median",
            "exactly_three_functionals": True,
            "high_low_used": False,
            "btc_side_used": False,
            "path_asymmetry_included": False,
        },
        "TERMINAL_CLASSIFICATION": classification,
        "KNOWN_LIMITATIONS": [
            "Adaptive discovery on historically exposed 2020-2024 data.",
            "Unconditional close-path design; not a terminal-return card.",
            *([f"missing:{item}" for item in missing] if missing else []),
        ],
        "PROTECTED_2025_OPENED": False,
        "PROTECTED_2026_OPENED": False,
        "PREFLIGHT": preflight,
    }
    if missing and classification == "BLOCKED_MISSING_LOCAL_DATA":
        payload["MISSING_LOCAL_DATA"] = missing
    if output_dir is not None:
        C.write_result_pair(
            payload,
            output_dir / "D3_DISCOVERY_RESULT.json",
            output_dir / "D3_DISCOVERY_RESULT.md",
            title="D3 PATH_MORPHOLOGY",
        )
    return payload
