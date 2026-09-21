"""D2 CONDITIONAL_ABSTENTION_TAIL_RISK."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from scripts.research.discovery_sprint_01 import common as C


SEARCH_SURFACE = ["RV_ABSTENTION", "DISLOCATION_ABSTENTION"]


def _rule_payload(name: str, rows: Sequence[C.DiscoveryRow], mask: np.ndarray, seed: int, n_replicates: int) -> dict[str, Any]:
    years = [row.year for row in rows]
    severity = [row.severity for row in rows]
    evaluated = C.evaluate_abstention_delta(
        severity, years, mask, seed=seed, n_replicates=n_replicates
    )
    evaluated["RULE"] = name
    evaluated["GATE_PASS"] = bool(
        evaluated["STATISTICAL_THRESHOLD_MET"]
        and evaluated["PRACTICAL_MAGNITUDE_MET"]
        and evaluated["TEMPORAL_CONSISTENCY_MET"]
        and evaluated["ABSTAIN_COUNT"] > 0
    )
    return evaluated


def evaluate_rule_1(
    rows: Sequence[C.DiscoveryRow],
    *,
    seed: int = C.D2_RANDOM_CONTROL_SEED,
    n_replicates: int = C.N_REPLICATES,
) -> dict[str, Any]:
    for row in rows:
        moment = C.utc_from_ms(row.t_ms)
        if moment < C.RULE1_INTERVAL_START or moment >= C.DISCOVERY_END:
            raise ValueError(f"RULE_1_INTERVAL_VIOLATION:{moment.isoformat()}")
    mask = C.rv_abstention_mask(rows)
    # Warmup rows cannot contribute to the rule; they remain in the
    # never-abstain secondary reference via the full severity vector.
    return _rule_payload("RV_ABSTENTION", rows, mask, seed, n_replicates)


def evaluate_rule_2(
    rows: Sequence[C.DiscoveryRow],
    *,
    seed: int = C.D2_RANDOM_CONTROL_SEED,
    n_replicates: int = C.N_REPLICATES,
) -> dict[str, Any]:
    for row in rows:
        moment = C.utc_from_ms(row.t_ms)
        if moment < C.RULE2_INTERVAL_START or moment >= C.DISCOVERY_END:
            raise ValueError(f"RULE_2_INTERVAL_VIOLATION:{moment.isoformat()}")
        if row.z is None:
            raise ValueError("RULE_2_MISSING_Z")
    mask = C.dislocation_abstention_mask(rows)
    return _rule_payload("DISLOCATION_ABSTENTION", rows, mask, seed, n_replicates)


def classify_d2(rule_results: Mapping[str, Any], *, missing: Sequence[str]) -> str:
    if missing:
        return "BLOCKED_MISSING_LOCAL_DATA"
    if "RV_ABSTENTION" not in rule_results or "DISLOCATION_ABSTENTION" not in rule_results:
        return "INCONCLUSIVE_DISCOVERY"
    attempted = [rule_results["RV_ABSTENTION"], rule_results["DISLOCATION_ABSTENTION"]]
    if any(item.get("INVALID") for item in attempted):
        return "INVALID_DISCOVERY"
    if any(item.get("GATE_PASS") for item in attempted):
        return "PROMISING_PROTOTYPE"
    return "NO_USEFUL_STRUCTURE"


def run_d2(
    *,
    implementation_commit: str,
    output_dir: Path | None = None,
    repo: Path | None = None,
    n_replicates: int = C.N_REPLICATES,
    core_perp: Mapping[int, C.PerpBar] | None = None,
    m06_perp: Mapping[int, C.PerpBar] | None = None,
    m06_spot: Mapping[int, float] | None = None,
) -> dict[str, Any]:
    base = repo or C.repo_root()
    log = C.OpenedFileLog()
    preflight = C.preflight_local_data(base)
    missing: list[str] = []
    extra_metrics: dict[str, Any] = {}
    files_before = list(log.files)

    rule1 = None
    rule2 = None
    rows_rule1: list[C.DiscoveryRow] = []
    rows_rule2: list[C.DiscoveryRow] = []

    need_core = core_perp is None and not preflight["BTC_DATA_PRESENT"]
    need_m06 = (
        (m06_perp is None or m06_spot is None)
        and not preflight["M06_CROSS_VENUE_DATA_PRESENT"]
    )
    if need_core:
        missing.append("CORE_BTC_BINANCE_V0_MONTHLY_PARQUET")
    if need_m06:
        missing.append("MARKET_06_OKX_BINANCE_FEASIBILITY_V0_DURABLE_RAW")

    if core_perp is None and "CORE_BTC_BINANCE_V0_MONTHLY_PARQUET" not in missing:
        try:
            core_perp = C.load_core_btc_5m(log, repo=base)
        except C.MissingLocalData as exc:
            missing.append(str(exc))
            core_perp = None

    if (m06_perp is None or m06_spot is None) and "MARKET_06_OKX_BINANCE_FEASIBILITY_V0_DURABLE_RAW" not in missing:
        try:
            loaded_perp, loaded_spot, _snap = C.load_m06_cross_venue(log, repo=base)
            m06_perp = loaded_perp if m06_perp is None else m06_perp
            m06_spot = loaded_spot if m06_spot is None else m06_spot
        except C.MissingLocalData as exc:
            missing.append(str(exc))

    if core_perp is not None:
        rows_rule1 = C.build_rows(core_perp, C.RULE1_INTERVAL_START, C.DISCOVERY_END)
        if rows_rule1:
            rule1 = evaluate_rule_1(rows_rule1, n_replicates=n_replicates)
            extra_metrics["RULE_1_ROW_COUNT"] = len(rows_rule1)
            extra_metrics["RULE_1_YEAR_BREAKDOWN"] = C.year_counts(rows_rule1)
        else:
            missing.append("RULE_1_ZERO_ELIGIBLE_ROWS")
    if m06_perp is not None and m06_spot is not None:
        rows_rule2 = C.build_rows(
            m06_perp,
            C.RULE2_INTERVAL_START,
            C.DISCOVERY_END,
            spot=m06_spot,
            require_z=True,
        )
        if rows_rule2:
            rule2 = evaluate_rule_2(rows_rule2, n_replicates=n_replicates)
            extra_metrics["RULE_2_ROW_COUNT"] = len(rows_rule2)
            extra_metrics["RULE_2_YEAR_BREAKDOWN"] = C.year_counts(rows_rule2)
        else:
            missing.append("RULE_2_ZERO_ELIGIBLE_ROWS")

    rule_results: dict[str, Any] = {}
    if rule1 is not None:
        rule_results["RV_ABSTENTION"] = rule1
    if rule2 is not None:
        rule_results["DISLOCATION_ABSTENTION"] = rule2

    classification = classify_d2(rule_results, missing=missing)
    payload = {
        "DISCOVERY_ID": "D2",
        "NAME": "CONDITIONAL_ABSTENTION_TAIL_RISK",
        "SPEC_AUTHORITY": C.SPEC_AUTHORITY,
        "IMPLEMENTATION_COMMIT": implementation_commit,
        "DATASET_IDENTITIES": {
            "RULE_1": {C.CORE_BTC_DATASET_ID: C.CORE_BTC_SNAPSHOT},
            "RULE_2": {C.M06_DATASET_ID: C.M06_SNAPSHOT},
        },
        "INTERVAL_USED": {
            "RULE_1": "2020-02-01T00:05:00Z -> 2025-01-01T00:00:00Z exclusive",
            "RULE_2": "2022-02-01T00:05:00Z -> 2025-01-01T00:00:00Z exclusive",
        },
        "FILES_OPENED": log.files or files_before,
        "SEARCH_SURFACE_ATTEMPTED": SEARCH_SURFACE,
        "SEEDS": {"D2_RANDOM_CONTROL_SEED": C.D2_RANDOM_CONTROL_SEED},
        "ROW_COUNTS": {
            "RULE_1": len(rows_rule1),
            "RULE_2": len(rows_rule2),
        },
        "YEAR_BREAKDOWN": {
            "RULE_1": C.year_counts(rows_rule1),
            "RULE_2": C.year_counts(rows_rule2),
        },
        "PRIMARY_METRICS": rule_results,
        "BASELINE_METRICS": {
            "PRIMARY_COMPARATOR": "RATE_MATCHED_RANDOM_ABSTENTION",
            "SECONDARY_REFERENCE_ONLY": "never-abstain / unconditional mean severity",
        },
        "PROTOTYPE_GATE_FIELDS": {
            "statistical_threshold": "DELTA / MU_RULE exceeds the 95th percentile of rate-matched random abstention mean severity",
            "practical_magnitude_threshold": "DELTA >= 20% of never-abstain mean severity",
            "temporal_consistency_check": "at least 3 year-buckets with DELTA > 0 versus that year's own rate-matched control",
            "RULE_1_GATE_PASS": None if rule1 is None else rule1.get("GATE_PASS"),
            "RULE_2_GATE_PASS": None if rule2 is None else rule2.get("GATE_PASS"),
        },
        "TERMINAL_CLASSIFICATION": classification,
        "KNOWN_LIMITATIONS": [
            "Adaptive discovery on historically exposed 2020-2024 data.",
            "Not confirmatory; not an independent surface.",
            "Exactly two frozen rules; no threshold variants.",
            *([f"missing:{item}" for item in missing] if missing else []),
        ],
        "PROTECTED_2025_OPENED": False,
        "PROTECTED_2026_OPENED": False,
        "PREFLIGHT": preflight,
        **extra_metrics,
    }
    if missing and classification == "BLOCKED_MISSING_LOCAL_DATA":
        payload["MISSING_LOCAL_DATA"] = missing
    if output_dir is not None:
        C.write_result_pair(
            payload,
            output_dir / "D2_DISCOVERY_RESULT.json",
            output_dir / "D2_DISCOVERY_RESULT.md",
            title="D2 CONDITIONAL_ABSTENTION_TAIL_RISK",
        )
    return payload
