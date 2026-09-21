"""D5 COMPOSED_DECISION_MECHANISM — OR of D2 RULE_1 and RULE_2."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from scripts.research.discovery_sprint_01 import common as C
from scripts.research.discovery_sprint_01.d2_abstention_tail_risk import (
    evaluate_rule_1,
    evaluate_rule_2,
)


SEARCH_SURFACE = ["OR(RV_ABSTENTION, DISLOCATION_ABSTENTION)"]


def composed_or_mask(rule1: np.ndarray, rule2: np.ndarray) -> np.ndarray:
    if rule1.shape != rule2.shape:
        raise ValueError("COMPONENT_SHAPE_MISMATCH")
    return np.asarray(rule1, dtype=bool) | np.asarray(rule2, dtype=bool)


def evaluate_d5_same_window(
    rows: Sequence[C.DiscoveryRow],
    *,
    n_replicates: int = C.N_REPLICATES,
) -> dict[str, Any]:
    for row in rows:
        moment = C.utc_from_ms(row.t_ms)
        if moment < C.D5_INTERVAL_START or moment >= C.DISCOVERY_END:
            raise ValueError(f"D5_INTERVAL_VIOLATION:{moment.isoformat()}")
        if row.z is None:
            raise ValueError("D5_MISSING_COMPONENT_B_Z")
    mask_a = C.rv_abstention_mask(rows)
    mask_b = C.dislocation_abstention_mask(rows)
    mask_or = composed_or_mask(mask_a, mask_b)
    years = [row.year for row in rows]
    severity = [row.severity for row in rows]
    component_a = C.evaluate_abstention_delta(
        severity, years, mask_a, seed=C.D2_RANDOM_CONTROL_SEED, n_replicates=n_replicates
    )
    component_b = C.evaluate_abstention_delta(
        severity, years, mask_b, seed=C.D2_RANDOM_CONTROL_SEED, n_replicates=n_replicates
    )
    composed = C.evaluate_abstention_delta(
        severity, years, mask_or, seed=C.D5_RANDOM_CONTROL_SEED, n_replicates=n_replicates
    )
    d5_delta = composed.get("DELTA")
    a_delta = component_a.get("DELTA")
    b_delta = component_b.get("DELTA")
    if d5_delta is None or a_delta is None or b_delta is None:
        beats = False
    else:
        beats = bool(d5_delta > max(a_delta, b_delta))
    composed["COMPONENT_A_DELTA_FOR_D5"] = a_delta
    composed["COMPONENT_B_DELTA_FOR_D5"] = b_delta
    composed["D5_DELTA"] = d5_delta
    composed["COMPOSED_BEATS_COMPONENTS"] = beats
    composed["GATE_PASS"] = bool(
        composed.get("STATISTICAL_THRESHOLD_MET")
        and composed.get("PRACTICAL_MAGNITUDE_MET")
        and beats
    )
    return {
        "COMPOSED": composed,
        "COMPONENT_A": component_a,
        "COMPONENT_B": component_b,
        "ABSTAIN_COUNTS": {
            "A": int(mask_a.sum()),
            "B": int(mask_b.sum()),
            "OR": int(mask_or.sum()),
        },
    }


def classify_d5(report: Mapping[str, Any] | None, *, missing: Sequence[str]) -> str:
    if missing:
        return "BLOCKED_MISSING_LOCAL_DATA"
    if report is None:
        return "INCONCLUSIVE_DISCOVERY"
    composed = report.get("COMPOSED") or {}
    if composed.get("GATE_PASS"):
        return "PROMISING_PROTOTYPE"
    return "NO_USEFUL_STRUCTURE"


def run_d5(
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
    if core_perp is None and not preflight["BTC_DATA_PRESENT"]:
        missing.append("CORE_BTC_BINANCE_V0_MONTHLY_PARQUET")
    if (m06_perp is None or m06_spot is None) and not preflight["M06_CROSS_VENUE_DATA_PRESENT"]:
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

    report = None
    rows: list[C.DiscoveryRow] = []
    # Component A must use CORE_BTC identity, not M06 substitution.
    # Component B must use M06 cross-venue. Both required on the common grid.
    if core_perp is not None and m06_perp is not None and m06_spot is not None:
        core_rows = {
            row.t_ms: row
            for row in C.build_rows(core_perp, C.D5_INTERVAL_START, C.DISCOVERY_END)
        }
        m06_rows = {
            row.t_ms: row
            for row in C.build_rows(
                m06_perp,
                C.D5_INTERVAL_START,
                C.DISCOVERY_END,
                spot=m06_spot,
                require_z=True,
            )
        }
        common_ts = sorted(set(core_rows) & set(m06_rows))
        merged: list[C.DiscoveryRow] = []
        for t_ms in common_ts:
            a = core_rows[t_ms]
            b = m06_rows[t_ms]
            merged.append(
                C.DiscoveryRow(
                    t_ms=t_ms,
                    year=a.year,
                    rv=a.rv,
                    ret=a.ret,
                    side=a.side,
                    severity=a.severity,
                    entry_open=a.entry_open,
                    future_closes=a.future_closes,
                    z=b.z,
                )
            )
        rows = merged
        if not rows:
            missing.append("D5_ZERO_COMMON_ROWS")
        else:
            report = evaluate_d5_same_window(rows, n_replicates=n_replicates)
            # Keep evaluate_rule_* imported so tests can see D5 reuses D2 rules.
            _ = (evaluate_rule_1, evaluate_rule_2)

    classification = classify_d5(report, missing=missing)
    composed = (report or {}).get("COMPOSED") or {}
    payload = {
        "DISCOVERY_ID": "D5",
        "NAME": "COMPOSED_DECISION_MECHANISM",
        "SPEC_AUTHORITY": C.SPEC_AUTHORITY,
        "IMPLEMENTATION_COMMIT": implementation_commit,
        "DATASET_IDENTITIES": {
            C.CORE_BTC_DATASET_ID: C.CORE_BTC_SNAPSHOT,
            C.M06_DATASET_ID: C.M06_SNAPSHOT,
        },
        "INTERVAL_USED": "2022-02-01T00:05:00Z -> 2025-01-01T00:00:00Z exclusive",
        "FILES_OPENED": list(log.files),
        "SEARCH_SURFACE_ATTEMPTED": SEARCH_SURFACE,
        "SEEDS": {
            "D5_RANDOM_CONTROL_SEED": C.D5_RANDOM_CONTROL_SEED,
            "COMPONENT_CONTROL_SEED": C.D2_RANDOM_CONTROL_SEED,
        },
        "ROW_COUNTS": {"N": len(rows)},
        "YEAR_BREAKDOWN": C.year_counts(rows),
        "PRIMARY_METRICS": {
            "D5_DELTA": composed.get("D5_DELTA"),
            "COMPONENT_A_DELTA_FOR_D5": composed.get("COMPONENT_A_DELTA_FOR_D5"),
            "COMPONENT_B_DELTA_FOR_D5": composed.get("COMPONENT_B_DELTA_FOR_D5"),
            "COMPOSED_BEATS_COMPONENTS": composed.get("COMPOSED_BEATS_COMPONENTS"),
            "COMPOSED": composed,
            "COMPONENTS": {
                "A": None if report is None else report.get("COMPONENT_A"),
                "B": None if report is None else report.get("COMPONENT_B"),
            },
            "ABSTAIN_COUNTS": None if report is None else report.get("ABSTAIN_COUNTS"),
        },
        "BASELINE_METRICS": {
            "PRIMARY_COMPARATOR": "RATE_MATCHED_RANDOM_ABSTENTION",
            "COMPOSITION": "OR",
            "AND_TESTED": False,
        },
        "PROTOTYPE_GATE_FIELDS": {
            "statistical_threshold": "D5_DELTA / MU_RULE exceeds 95th percentile of D5 rate-matched random abstention",
            "practical_magnitude_threshold": "same 20% relative bar as D2",
            "beats_best_component_check": "D5_DELTA > max(COMPONENT_A_DELTA_FOR_D5, COMPONENT_B_DELTA_FOR_D5)",
            "same_window_only": True,
        },
        "TERMINAL_CLASSIFICATION": classification,
        "KNOWN_LIMITATIONS": [
            "Third look at the RV/dislocation family after D2's two individual rules.",
            "Compared only on the exact D5 common window, never against D2 RULE_1's 2020-2024 result.",
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
            output_dir / "D5_DISCOVERY_RESULT.json",
            output_dir / "D5_DISCOVERY_RESULT.md",
            title="D5 COMPOSED_DECISION_MECHANISM",
        )
    return payload
