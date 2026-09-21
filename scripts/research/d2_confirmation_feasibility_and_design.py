"""D2 RULE_1 confirmation feasibility and outcome-blind design.

Does not execute confirmation, does not open 2025/2026 price bytes,
does not create MARKET-07 / ARM / prereg freeze / RESULT.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np

from scripts.research.discovery_sprint_01 import common as C
from scripts.research.discovery_sprint_01.d2_abstention_tail_risk import evaluate_rule_1


UTC = timezone.utc

UNIT = "D2_CONFIRMATION_FEASIBILITY_AND_DESIGN"
IMPLEMENTATION_COMMIT = "26d8f7066533bcae7138d5a1952783f2a16f3c39"
CORE_SNAPSHOT = C.CORE_BTC_SNAPSHOT

FIRST_T = datetime(2025, 1, 1, 0, 5, tzinfo=UTC)
LAST_T = datetime(2025, 12, 30, 0, 5, tzinfo=UTC)
CONFIRMATION_T_END_EXCLUSIVE = datetime(2025, 12, 31, 0, 0, tzinfo=UTC)
LAST_FUTURE_BAR_OPEN = datetime(2025, 12, 31, 0, 0, tzinfo=UTC)

# Frozen before any 2025 outcome. Distinct from discovery seed 20260921102.
D2_CONFIRMATION_RANDOM_CONTROL_SEED = 20260921120
D2_CONFIRMATION_POWER_SEED = 20260921121
D2_CONFIRMATION_SIZE_PLANNING_SEED = 20260921122

N_REPLICATES_CONFIRMATION = 10_000
N_POWER_OUTER = 1_000
MINIMUM_ACCEPTABLE_CONFIRMATION_POWER = 0.80
AUTHORITATIVE_RELATIVE_EFFECT = 0.20
SENSITIVITY_RELATIVE_EFFECTS = (0.15, 0.20, 0.25, 0.30)
SIZE_PLANNING_RELATIVE_EFFECTS = (0.20, 0.25, 0.30)
N_2025_DECISION_SLOTS = 364  # 2025 not leap; Dec 31 forbidden
FRESH_SURFACE_SIZES = ((1, 364), (2, 728), (3, 1092), (4, 1456))

# Frozen historical one-year year-cycled Monte Carlo (seed 20260921121).
# Not recomputed by the size-planning amendment.
ORIGINAL_ONE_YEAR_POWER_AT_20PCT = {
    "power_statistical_gate": 0.011,
    "power_both_gates": 0.006,
    "power_practical_gate": 0.499,
    "POWER_SEED": D2_CONFIRMATION_POWER_SEED,
    "n_outer": N_POWER_OUTER,
    "n_inner": N_REPLICATES_CONFIRMATION,
    "relative_effect": AUTHORITATIVE_RELATIVE_EFFECT,
    "method": "year-cycled empirical 2021-2024 severity; year-specific K",
}

DISCOVERY_PROVENANCE = {
    "RULE_1_eligible": 1791,
    "ABSTAIN_COUNT": 163,
    "MU_RULE": 0.04005839896629072,
    "MU_CONTROL_MEAN": 0.025856224865193674,
    "DELTA": 0.014202174101097049,
    "UNCONDITIONAL_MEAN": 0.02517689228869647,
    "GATE_PASS": True,
    "positive_years": "5/5",
    "note": "Adaptive discovery only. Not evidence. Not the confirmatory minimum effect.",
}

INVENTORY_REL = "docs/research_data/CORE_BTC_BINANCE_V0/SOURCE_INVENTORY_717d37a4.json"
SNAPSHOT_REL = "docs/research_data/CORE_BTC_BINANCE_V0/SNAPSHOT_717d37a4.json"
BINDING_REL = "docs/research_data/D2_CONFIRMATION_2025_METADATA_BINDING.json"
JSON_REL = "docs/research/D2_CONFIRMATION_FEASIBILITY_AND_DESIGN.json"
MD_REL = "docs/research/D2_CONFIRMATION_FEASIBILITY_AND_DESIGN.md"


class ProtectedPriceRefused(RuntimeError):
    """A 2025/2026 price object was requested."""


def _repo(root: Path | None = None) -> Path:
    return root or C.repo_root()


def refuse_protected_price_path(path: Path) -> None:
    C.assert_openable(path)
    text = str(path)
    if "2025-" in text or "2026-" in text:
        if text.endswith(".parquet") or text.endswith(".zip") or "/canonical/" in text.replace("\\", "/"):
            raise ProtectedPriceRefused(f"PROTECTED_PRICE_PATH:{path}")


def confirmation_decision_slot_count() -> int:
    n = 0
    cursor = FIRST_T
    while cursor < CONFIRMATION_T_END_EXCLUSIVE:
        if not (cursor.month == 12 and cursor.day == 31):
            n += 1
        cursor = cursor + timedelta(days=1)
    return n


def extract_2025_metadata(*, repo: Path | None = None) -> dict[str, Any]:
    base = _repo(repo)
    inventory_path = base / INVENTORY_REL
    snapshot_path = base / SNAPSHOT_REL
    C.assert_openable(inventory_path)
    C.assert_openable(snapshot_path)
    refuse_protected_price_path(inventory_path)
    refuse_protected_price_path(snapshot_path)
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    checksums = (snapshot.get("identity_payload") or snapshot).get("output_checksums") or {}
    objects = inventory.get("objects") or inventory.get("source_objects") or []
    if not objects and isinstance(inventory, dict):
        for key in ("monthly_objects", "sources", "items"):
            if isinstance(inventory.get(key), list):
                objects = inventory[key]
                break
    wanted = [f"2025-{m:02d}" for m in range(1, 13)]
    by_period = {}
    for item in objects:
        period = str(item.get("source_period") or "")
        if period in wanted:
            by_period[period] = item
    missing = [p for p in wanted if p not in by_period]
    rows: list[dict[str, Any]] = []
    issues: list[str] = []
    if missing:
        issues.append("MISSING_MONTHS:" + ",".join(missing))
    for period in wanted:
        item = by_period.get(period)
        if item is None:
            continue
        parquet_rel = f"canonical/1m/monthly/{period}.parquet"
        parquet_sha = checksums.get(parquet_rel)
        source_sha = item.get("expected_sha256") or item.get("local_sha256")
        admitted = bool(item.get("admitted_to_canonical") is True)
        verified = str(item.get("checksum_verification") or "") == "VERIFIED"
        parser_ok = str(item.get("parser_status") or "") == "OK"
        missing_buckets = int(item.get("missing_bucket_count") or 0)
        if not admitted:
            issues.append(f"NOT_ADMITTED:{period}")
        if not verified:
            issues.append(f"CHECKSUM_NOT_VERIFIED:{period}")
        if not parser_ok:
            issues.append(f"PARSER_NOT_OK:{period}")
        if missing_buckets != 0:
            issues.append(f"MISSING_BUCKETS:{period}:{missing_buckets}")
        if parquet_sha is None:
            issues.append(f"NO_CANONICAL_HASH:{period}")
        if item.get("expected_sha256") and item.get("local_sha256"):
            if item["expected_sha256"] != item["local_sha256"]:
                issues.append(f"SOURCE_HASH_MISMATCH:{period}")
        rows.append(
            {
                "period": period,
                "source_filename": item.get("expected_zip_filename"),
                "source_SHA256": source_sha,
                "canonical_parquet_relative_path": parquet_rel,
                "canonical_parquet_SHA256": parquet_sha,
                "admitted_to_canonical": admitted,
                "checksum_verification": item.get("checksum_verification"),
                "parser_status": item.get("parser_status"),
                "expected_rows": item.get("expected_rows"),
                "observed_rows": item.get("observed_rows"),
                "missing_bucket_count": missing_buckets,
                "first_open_time_ms": item.get("first_open_time_ms"),
                "last_open_time_ms": item.get("last_open_time_ms"),
                "invariant_violation_count": item.get("invariant_violation_count"),
            }
        )
    n_2026_checksum_keys = sum(
        1
        for key in checksums
        if "/2026-" in str(key) and str(key).endswith(".parquet")
    )
    return {
        "snapshot_id": CORE_SNAPSHOT,
        "months": rows,
        "n_months": len(rows),
        "issues": issues,
        "CONFIRMATION_2025_MONTHS_METADATA_BOUND": len(rows) == 12 and not missing,
        "CONFIRMATION_2025_SOURCE_HASHES_BOUND": all(r.get("source_SHA256") for r in rows) and len(rows) == 12,
        "CONFIRMATION_2025_CANONICAL_HASHES_BOUND": all(r.get("canonical_parquet_SHA256") for r in rows) and len(rows) == 12,
        "n_2026_monthly_parquet_keys_present_in_snapshot_identity": int(n_2026_checksum_keys),
        "2026_OBJECT_NEEDED_FOR_FROZEN_INTERVAL": False,
        "LAST_FUTURE_BAR_OPEN": LAST_FUTURE_BAR_OPEN.isoformat().replace("+00:00", "Z"),
        "files_read_for_metadata": [INVENTORY_REL, SNAPSHOT_REL],
        "price_values_present_in_binding": False,
    }


def _calibrate_relative_effect(
    y: np.ndarray, selected: np.ndarray, relative: float
) -> np.ndarray:
    y = np.asarray(y, dtype=np.float64)
    mask = np.asarray(selected, dtype=bool)
    k = int(mask.sum())
    n = int(y.size)
    if k == 0 or n == 0:
        raise ValueError("EMPTY_CALIBRATION")
    mu = float(y.mean())
    m_s = float(y[mask].mean())
    denom = 1.0 - (1.0 + relative) * (k / n)
    if abs(denom) < 1e-12:
        raise ValueError("CALIBRATION_DENOM_ZERO")
    shift = (relative * mu - (m_s - mu)) / denom
    out = y.copy()
    out[mask] = out[mask] + shift
    return out


def _randomization_control_means(y: np.ndarray, k: int, n_rep: int, rng: np.random.Generator) -> np.ndarray:
    n = int(y.size)
    if k <= 0 or k > n:
        raise ValueError(f"BAD_K:{k}:{n}")
    keys = rng.random((int(n_rep), n))
    idx = np.argpartition(keys, kth=k - 1, axis=1)[:, :k]
    return y[idx].mean(axis=1)


def _both_gates(y: np.ndarray, selected: np.ndarray, n_rep: int, rng: np.random.Generator) -> dict[str, Any]:
    mask = np.asarray(selected, dtype=bool)
    k = int(mask.sum())
    mu_rule = float(y[mask].mean())
    uncond = float(y.mean())
    ctrl = _randomization_control_means(y, k, n_rep, rng)
    mu_control_mean = float(ctrl.mean())
    delta = float(mu_rule - mu_control_mean)
    p95 = float(np.percentile(ctrl, 95))
    statistical = bool(mu_rule > p95)
    practical = bool(uncond != 0.0 and delta >= AUTHORITATIVE_RELATIVE_EFFECT * uncond)
    p_mc = float((1.0 + float(np.sum(ctrl >= mu_rule))) / (1.0 + n_rep))
    return {
        "STATISTICAL_GATE": statistical,
        "PRACTICAL_MAGNITUDE_GATE": practical,
        "BOTH": bool(statistical and practical),
        "MU_RULE": mu_rule,
        "MU_CONTROL_MEAN": mu_control_mean,
        "DELTA": delta,
        "UNCONDITIONAL_MEAN": uncond,
        "CONTROL_P95": p95,
        "MC_P": p_mc,
    }


def estimate_power(
    rows: list[C.DiscoveryRow],
    *,
    seed: int = D2_CONFIRMATION_POWER_SEED,
    n_outer: int = N_POWER_OUTER,
    n_inner: int = N_REPLICATES_CONFIRMATION,
) -> dict[str, Any]:
    mask = C.rv_abstention_mask(rows)
    years = np.asarray([row.year for row in rows], dtype=np.int64)
    sev = np.asarray([row.severity for row in rows], dtype=np.float64)
    fireable = np.arange(len(rows)) >= C.RV_TRAILING_WINDOW
    fireable_n = int(fireable.sum())
    abstain_fireable = int((mask & fireable).sum())
    fireable_rate = float(abstain_fireable / fireable_n) if fireable_n else float("nan")
    expected_k = int(round(fireable_rate * N_2025_DECISION_SLOTS))
    complete_years = [2021, 2022, 2023, 2024]
    year_pools: dict[int, np.ndarray] = {}
    year_k: dict[int, int] = {}
    for year in complete_years:
        idx = years == year
        year_pools[year] = sev[idx]
        year_k[year] = int(mask[idx].sum())
    rng = np.random.default_rng(int(seed))
    table: dict[str, Any] = {}
    for relative in SENSITIVITY_RELATIVE_EFFECTS:
        both = 0
        stat_only = 0
        prac_only = 0
        for i in range(int(n_outer)):
            year = int(complete_years[i % len(complete_years)])
            y = year_pools[year].copy()
            n = int(y.size)
            k = int(year_k[year])
            if k < 1 or k >= n:
                continue
            selected = np.zeros(n, dtype=bool)
            chosen = rng.choice(n, size=k, replace=False)
            selected[chosen] = True
            y_alt = _calibrate_relative_effect(y, selected, relative)
            inner_rng = np.random.default_rng(rng.integers(0, 2**31 - 1))
            result = _both_gates(y_alt, selected, n_inner, inner_rng)
            if result["STATISTICAL_GATE"]:
                stat_only += 1
            if result["PRACTICAL_MAGNITUDE_GATE"]:
                prac_only += 1
            if result["BOTH"]:
                both += 1
        denom = float(n_outer)
        table[f"{int(relative * 100)}pct"] = {
            "relative_effect": relative,
            "power_both_gates": both / denom,
            "power_statistical_gate": stat_only / denom,
            "power_practical_gate": prac_only / denom,
            "n_outer": int(n_outer),
            "n_inner": int(n_inner),
            "authoritative": relative == AUTHORITATIVE_RELATIVE_EFFECT,
        }
    return {
        "fireable_n_2020_2024": fireable_n,
        "fireable_abstain_count": abstain_fireable,
        "frozen_rule_fireable_rate": fireable_rate,
        "EXPECTED_2025_ELIGIBLE_N": N_2025_DECISION_SLOTS,
        "EXPECTED_2025_ABSTAIN_COUNT": expected_k,
        "year_eligible_n": {str(y): int(year_pools[y].size) for y in complete_years},
        "year_rule_abstain_count": {str(y): int(year_k[y]) for y in complete_years},
        "sensitivity": table,
        "POWER_AT_20PCT_MIN_EFFECT": table["20pct"]["power_both_gates"],
        "POWER_STATISTICAL_AT_20PCT": table["20pct"]["power_statistical_gate"],
        "POWER_JOINT_AT_20PCT": table["20pct"]["power_both_gates"],
        "POWER_SEED": int(seed),
        "method": (
            "Year-cycled empirical 2021-2024 severity vectors. For each outer "
            "replicate, a random K-subset (K = frozen-rule abstain count that "
            "year) is location-shifted so DELTA/UNCONDITIONAL_MEAN equals the "
            "predeclared relative effect. Inner RATE_MATCHED_RANDOM_ABSTENTION "
            "uses 10000 uniform-without-replacement draws. The random subset "
            "is used so power is evaluated at the predeclared effect rather "
            "than at the observed discovery DELTA."
        ),
        "historical_note": (
            "This year-cycled estimator is the original one-year calculation. "
            "POWER_AT_20PCT_MIN_EFFECT was the joint (both-gates) probability "
            "and is preserved as historical output. Confirmation feasibility "
            "now uses STATISTICAL_POWER_AT_20PCT_EFFECT as the primary "
            "prospective criterion. JOINT_PASS_PROBABILITY is diagnostic only. "
            "power_practical_gate ≈ 0.5 at the 20% alternative is expected "
            "and is not itself evidence of underpower."
        ),
    }


def _precompute_subset_indices(
    n: int, k: int, n_rep: int, rng: np.random.Generator
) -> np.ndarray:
    keys = rng.random((int(n_rep), int(n)))
    return np.argpartition(keys, kth=int(k) - 1, axis=1)[:, : int(k)].astype(np.intp)


def _gates_from_indices(
    y: np.ndarray, selected: np.ndarray, idx: np.ndarray
) -> dict[str, Any]:
    mask = np.asarray(selected, dtype=bool)
    mu_rule = float(y[mask].mean())
    uncond = float(y.mean())
    ctrl = y[idx].mean(axis=1)
    mu_control_mean = float(ctrl.mean())
    delta = float(mu_rule - mu_control_mean)
    p95 = float(np.percentile(ctrl, 95))
    statistical = bool(mu_rule > p95)
    practical = bool(uncond != 0.0 and delta >= AUTHORITATIVE_RELATIVE_EFFECT * uncond)
    return {
        "STATISTICAL_GATE": statistical,
        "PRACTICAL_MAGNITUDE_GATE": practical,
        "BOTH": bool(statistical and practical),
    }


def estimate_size_planning(
    rows: list[C.DiscoveryRow],
    *,
    seed: int = D2_CONFIRMATION_SIZE_PLANNING_SEED,
    n_outer: int = N_POWER_OUTER,
    n_inner: int = N_REPLICATES_CONFIRMATION,
) -> dict[str, Any]:
    """Hypothetical fresh-surface power using exposed 2020-2024 severity only.

    Does not read 2025/2026 prices. Does not change the frozen confirmation
    rule, target, comparator, or gates.
    """
    mask = C.rv_abstention_mask(rows)
    sev = np.asarray([row.severity for row in rows], dtype=np.float64)
    fireable = np.arange(len(rows)) >= C.RV_TRAILING_WINDOW
    fireable_n = int(fireable.sum())
    abstain_fireable = int((mask & fireable).sum())
    fireable_rate = float(abstain_fireable / fireable_n) if fireable_n else float("nan")
    pool = sev[fireable]
    if pool.size < 2:
        raise RuntimeError("SIZE_PLANNING_EMPTY_POOL")
    rng = np.random.default_rng(int(seed))
    surfaces: list[dict[str, Any]] = []
    for n_years, n_rows in FRESH_SURFACE_SIZES:
        k = int(round(fireable_rate * n_rows))
        if k < 1 or k >= n_rows:
            raise RuntimeError(f"SIZE_PLANNING_BAD_K:{n_rows}:{k}")
        idx = _precompute_subset_indices(n_rows, k, n_inner, rng)
        counts: dict[str, dict[str, int]] = {
            f"{int(rel * 100)}pct": {"stat": 0, "prac": 0, "both": 0}
            for rel in SIZE_PLANNING_RELATIVE_EFFECTS
        }
        for _ in range(int(n_outer)):
            y = rng.choice(pool, size=int(n_rows), replace=True)
            selected = np.zeros(int(n_rows), dtype=bool)
            selected[rng.choice(int(n_rows), size=k, replace=False)] = True
            for relative in SIZE_PLANNING_RELATIVE_EFFECTS:
                y_alt = _calibrate_relative_effect(y, selected, relative)
                result = _gates_from_indices(y_alt, selected, idx)
                key = f"{int(relative * 100)}pct"
                if result["STATISTICAL_GATE"]:
                    counts[key]["stat"] += 1
                if result["PRACTICAL_MAGNITUDE_GATE"]:
                    counts[key]["prac"] += 1
                if result["BOTH"]:
                    counts[key]["both"] += 1
        denom = float(n_outer)
        sensitivity: dict[str, Any] = {}
        for relative in SIZE_PLANNING_RELATIVE_EFFECTS:
            key = f"{int(relative * 100)}pct"
            sensitivity[key] = {
                "relative_effect": relative,
                "STATISTICAL_POWER": counts[key]["stat"] / denom,
                "JOINT_PASS_PROBABILITY": counts[key]["both"] / denom,
                "power_practical_gate": counts[key]["prac"] / denom,
                "n_outer": int(n_outer),
                "n_inner": int(n_inner),
                "authoritative": relative == AUTHORITATIVE_RELATIVE_EFFECT,
            }
        surfaces.append(
            {
                "approx_years": int(n_years),
                "N": int(n_rows),
                "expected_K": k,
                "STATISTICAL_POWER_AT_20PCT": sensitivity["20pct"]["STATISTICAL_POWER"],
                "JOINT_PASS_PROBABILITY_AT_20PCT": sensitivity["20pct"][
                    "JOINT_PASS_PROBABILITY"
                ],
                "sensitivity": sensitivity,
            }
        )
    min_rows: int | None = None
    min_years: int | None = None
    for row in surfaces:
        if float(row["STATISTICAL_POWER_AT_20PCT"]) >= MINIMUM_ACCEPTABLE_CONFIRMATION_POWER:
            min_rows = int(row["N"])
            min_years = int(row["approx_years"])
            break
    if min_years is None:
        requirement = "MORE_THAN_4_YEARS_OR_ALTERNATIVE_INDEPENDENT_SURFACE"
        potential = "DO_NOT_CONSUME_2025_PLUS_2026"
        next_unit = "D2_CONFIRMATION_ALTERNATIVE_INDEPENDENT_SURFACE_OR_WAIT"
    elif min_years <= 2:
        requirement = "TWO_YEARS_INDEPENDENT_FRESH" if min_years == 2 else "ONE_YEAR_INDEPENDENT_FRESH"
        potential = "2025_PLUS_FULL_2026" if min_years == 2 else "SINGLE_YEAR_2025_STILL_NOT_OPENED"
        next_unit = (
            "D2_CONFIRMATION_WAIT_FOR_PREDECLARED_2025_PLUS_2026_WITHOUT_OPENING"
            if min_years == 2
            else "D2_CONFIRMATION_PREREG_FREEZE"
        )
    elif min_years == 3:
        requirement = "THREE_YEARS_INDEPENDENT_FRESH"
        potential = "DO_NOT_CONSUME_2025_PLUS_2026"
        next_unit = "D2_CONFIRMATION_WAIT_FOR_3Y_INDEPENDENT_FRESH_SURFACE"
    else:
        requirement = "FOUR_YEARS_INDEPENDENT_FRESH"
        potential = "DO_NOT_CONSUME_2025_PLUS_2026"
        next_unit = "D2_CONFIRMATION_WAIT_FOR_4Y_INDEPENDENT_FRESH_SURFACE"
    by_years = {int(row["approx_years"]): row for row in surfaces}
    return {
        "SIZE_PLANNING_SEED": int(seed),
        "pool_description": (
            "Fireable 2020-2024 empirical direction-aligned MAE severity "
            "(trailing-250 warmup excluded). Hypothetical fresh surfaces are "
            "drawn with replacement. Expected K = round(frozen RULE_1 "
            "fireable rate * N). Inner P95 uses 10000 RATE_MATCHED_RANDOM_"
            "ABSTENTION replicates. No 2025/2026 prices are used."
        ),
        "fireable_n_2020_2024": fireable_n,
        "fireable_abstain_count": abstain_fireable,
        "frozen_rule_fireable_rate": fireable_rate,
        "n_outer": int(n_outer),
        "n_inner": int(n_inner),
        "surfaces": surfaces,
        "ONE_YEAR_STATISTICAL_POWER_AT_20PCT_SIZE_PLANNING": by_years[1][
            "STATISTICAL_POWER_AT_20PCT"
        ],
        "TWO_YEAR_STATISTICAL_POWER_AT_20PCT": by_years[2]["STATISTICAL_POWER_AT_20PCT"],
        "THREE_YEAR_STATISTICAL_POWER_AT_20PCT": by_years[3]["STATISTICAL_POWER_AT_20PCT"],
        "FOUR_YEAR_STATISTICAL_POWER_AT_20PCT": by_years[4]["STATISTICAL_POWER_AT_20PCT"],
        "TWO_YEAR_JOINT_PASS_PROBABILITY_AT_20PCT": by_years[2][
            "JOINT_PASS_PROBABILITY_AT_20PCT"
        ],
        "THREE_YEAR_JOINT_PASS_PROBABILITY_AT_20PCT": by_years[3][
            "JOINT_PASS_PROBABILITY_AT_20PCT"
        ],
        "FOUR_YEAR_JOINT_PASS_PROBABILITY_AT_20PCT": by_years[4][
            "JOINT_PASS_PROBABILITY_AT_20PCT"
        ],
        "MIN_REQUIRED_FRESH_DECISION_ROWS": min_rows,
        "MIN_REQUIRED_FRESH_YEARS": min_years,
        "CONFIRMATION_SURFACE_REQUIREMENT": requirement,
        "POTENTIAL_FUTURE_SURFACE": potential,
        "AUTHORIZED_TO_OPEN": False,
        "NEXT_UNIT": next_unit,
        "RULE_CHANGED": False,
        "TARGET_CHANGED": False,
        "GATES_CHANGED": False,
        "effect_bar_lowered": False,
        "2025_and_2026_not_automatically_combined": True,
    }


def power_interpretation_block(power: dict[str, Any]) -> dict[str, Any]:
    sens20 = power["sensitivity"]["20pct"]
    return {
        "PRIMARY_PROSPECTIVE_POWER_CRITERION": "STATISTICAL_POWER_AT_20PCT_EFFECT",
        "MINIMUM_ACCEPTABLE_STATISTICAL_POWER": MINIMUM_ACCEPTABLE_CONFIRMATION_POWER,
        "JOINT_PASS_PROBABILITY_IS_DIAGNOSTIC_ONLY": True,
        "PRACTICAL_GATE_UNCHANGED": True,
        "STATISTICAL_GATE_UNCHANGED": True,
        "WHY_PRACTICAL_GATE_POWER_NEAR_HALF_IS_NOT_UNDERPOWER": (
            "TRUE_EFFECT = 20% relative is the same magnitude as the frozen "
            "practical confirmation gate DELTA >= 20% * UNCONDITIONAL_MEAN. "
            "power_practical_gate at that exact boundary is therefore "
            "approximately 0.5 by construction / sampling variability of "
            "MU_CONTROL_MEAN. The observed original value "
            "power_practical_gate ~= 0.499 is not itself evidence that the "
            "study is underpowered."
        ),
        "A_STATISTICAL_POWER_AT_20PCT_EFFECT": (
            "Probability that the frozen statistical gate "
            "MU_RULE > P95(random-control means) passes when the true "
            "relative effect is 20%."
        ),
        "B_JOINT_PASS_PROBABILITY_AT_20PCT_EFFECT": (
            "Probability both statistical and practical gates pass when the "
            "true relative effect is 20%. Diagnostic only. Not the primary "
            "prospective power criterion."
        ),
        "ORIGINAL_ONE_YEAR_CALCULATION_PRESERVED": {
            "ONE_YEAR_STATISTICAL_POWER_AT_20PCT": float(
                sens20["power_statistical_gate"]
            ),
            "ONE_YEAR_JOINT_PASS_PROBABILITY_AT_20PCT": float(
                sens20["power_both_gates"]
            ),
            "ONE_YEAR_PRACTICAL_GATE_POWER_AT_20PCT": float(
                sens20["power_practical_gate"]
            ),
            "historical_POWER_AT_20PCT_MIN_EFFECT_WAS_JOINT": float(
                power["POWER_AT_20PCT_MIN_EFFECT"]
            ),
            "POWER_SEED": int(power["POWER_SEED"]),
            "method": power["method"],
            "year_eligible_n": power.get("year_eligible_n"),
            "year_rule_abstain_count": power.get("year_rule_abstain_count"),
        },
    }


def load_exposed_rule1_rows(*, repo: Path | None = None) -> tuple[list[C.DiscoveryRow], C.OpenedFileLog]:
    base = _repo(repo)
    log = C.OpenedFileLog()
    perp = C.load_core_btc_5m(log, repo=base)
    for rel in log.files:
        if "2025-" in rel or "2026-" in rel:
            raise ProtectedPriceRefused(f"LOGGED_PROTECTED:{rel}")
        refuse_protected_price_path(base / rel if not rel.startswith("/") else Path(rel))
    rows = C.build_rows(perp, C.RULE1_INTERVAL_START, C.DISCOVERY_END)
    return rows, log


def _load_preserved_one_year_power(base: Path) -> dict[str, Any] | None:
    path = base / JSON_REL
    if not path.is_file():
        return None
    existing = json.loads(path.read_text(encoding="utf-8"))
    power = existing.get("power")
    if not isinstance(power, dict):
        return None
    sens = (power.get("sensitivity") or {}).get("20pct") or {}
    if "power_statistical_gate" not in sens:
        return None
    return power


def run_feasibility(
    *,
    repo: Path | None = None,
    recompute_one_year_power: bool = False,
) -> dict[str, Any]:
    if confirmation_decision_slot_count() != N_2025_DECISION_SLOTS:
        raise RuntimeError(f"SLOT_COUNT:{confirmation_decision_slot_count()}")
    base = _repo(repo)
    meta = extract_2025_metadata(repo=base)
    rows, log = load_exposed_rule1_rows(repo=base)
    replay = evaluate_rule_1(rows)
    preserved = None if recompute_one_year_power else _load_preserved_one_year_power(base)
    power = estimate_power(rows) if preserved is None else preserved
    size_planning = estimate_size_planning(rows)
    interpretation = power_interpretation_block(power)
    original_20 = interpretation["ORIGINAL_ONE_YEAR_CALCULATION_PRESERVED"]
    one_year_stat = float(original_20["ONE_YEAR_STATISTICAL_POWER_AT_20PCT"])
    one_year_joint = float(original_20["ONE_YEAR_JOINT_PASS_PROBABILITY_AT_20PCT"])
    # Primary prospective criterion is statistical power, not joint.
    underpowered = bool(one_year_stat < MINIMUM_ACCEPTABLE_CONFIRMATION_POWER)
    feasibility = (
        "UNDERPOWERED_SINGLE_YEAR_2025" if underpowered else "FEASIBLE_SINGLE_YEAR_2025"
    )
    next_unit = str(size_planning["NEXT_UNIT"])
    if not underpowered:
        next_unit = "D2_CONFIRMATION_PREREG_FREEZE"
    opened = list(log.files)
    protected_price_opened = [
        item for item in opened if "2025-" in item or "2026-" in item
    ]
    report = {
        "unit": UNIT,
        "kind": "OUTCOME_BLIND_CONFIRMATION_DESIGN",
        "date": "2026-09-21",
        "D2_DISCOVERY_STATUS": "PROMISING_PROTOTYPE",
        "CANDIDATE": "D2 / RULE_1 / RV_ABSTENTION",
        "NOT_CONFIRMED_VARIANTS": [
            "DISLOCATION_ABSTENTION",
            "D5 OR composition",
            "AND rule",
            "another RV threshold",
            "another horizon",
            "another direction definition",
            "another outcome",
            "another volatility estimator",
        ],
        "CONFIRMATION_RULE": (
            "ABSTAIN(t)=1 iff ev.rv_btc_24h(t) > P90 of its own trailing 250 "
            "completed decision-point values with t excluded. No threshold sweep."
        ),
        "CONFIRMATION_TARGET": (
            "24h direction-aligned adverse-path severity using the exact existing "
            "288 x 5m future-bar construction (arithmetic MAE). Not terminal "
            "return, close-only MAE, MFE, drawdown, volatility, or PnL."
        ),
        "CONFIRMATION_COMPARATOR": (
            "RATE_MATCHED_RANDOM_ABSTENTION. Frozen D2 year-matched convention "
            "is retained. On a single-year 2025 surface it reduces to selecting "
            "exactly K eligible 2025 rows uniformly without replacement. No "
            "month/quarter matching added."
        ),
        "CONFIRMATION_STATISTICAL_GATE": (
            "MU_RULE > P95 of the 10000 RATE_MATCHED_RANDOM_ABSTENTION replicate "
            "mean-severity values. Authoritative pass rule. Monte Carlo "
            "one-sided p=(1+count(control_mean>=MU_RULE))/(1+N_REPLICATES) is "
            "reported only; it does not replace the percentile gate."
        ),
        "CONFIRMATION_PRACTICAL_GATE": (
            "DELTA >= 0.20 * UNCONDITIONAL_MEAN on the independent 2025 surface. "
            "Same discovery-era 20% relative bar. Not lowered. Not replaced by "
            "the observed +1.42pp discovery DELTA."
        ),
        "DIRECTION": "BTC_SIDE(t)=sign(ev.btc_ret_24h(t)); zero-return rows ineligible",
        "ENTRY": "frozen entry_open(t) from D2 / MARKET-05/06",
        "BASE_EXPOSURE": "full-size BTC perpetual in direction BTC_SIDE(t)",
        "DECISION_SCHEDULE": "one daily BTC decision on MARKET-05/06 00:05:00Z grid",
        "PRIMARY_CONFIRMATION_SURFACE": "2025",
        "SECOND_RESERVED_SURFACE": "2026",
        "FIRST_T": FIRST_T.isoformat().replace("+00:00", "Z"),
        "LAST_T": LAST_T.isoformat().replace("+00:00", "Z"),
        "CONFIRMATION_T_INTERVAL": "[2025-01-01T00:05:00Z, 2025-12-31T00:00:00Z)",
        "WARMUP": (
            "Trailing-250 feature history may use already-exposed 2024 decision "
            "points. 2025 outcomes remain unexposed. Metrics are computed only "
            "on 2025 T."
        ),
        "TEMPORAL_REPORTING": {
            "quarters_diagnostic_only": ["2025-Q1", "2025-Q2", "2025-Q3", "2025-Q4"],
            "quarterly_cannot_rescue_or_veto": True,
            "primary_uses_pooled_2025": True,
            "no_new_quarterly_pass_rule": True,
        },
        "FUTURE_EXECUTION_CLASSIFICATIONS_NOT_ASSIGNED": [
            "CONFIRMED_ON_INDEPENDENT_2025_SURFACE",
            "NOT_CONFIRMED_ON_INDEPENDENT_2025_SURFACE",
            "INVALID_CONFIRMATION_EXECUTION",
        ],
        "PASS_RULE": "STATISTICAL_GATE and PRACTICAL_MAGNITUDE_GATE both true",
        "D2_CONFIRMATION_RANDOM_CONTROL_SEED": D2_CONFIRMATION_RANDOM_CONTROL_SEED,
        "N_REPLICATES_CONFIRMATION": N_REPLICATES_CONFIRMATION,
        "MINIMUM_ACCEPTABLE_CONFIRMATION_POWER": MINIMUM_ACCEPTABLE_CONFIRMATION_POWER,
        "DISCOVERY_PROVENANCE_NOT_EVIDENCE": DISCOVERY_PROVENANCE,
        "RULE_1_REPLAY_ON_EXPOSED_2020_2024": {
            "ABSTAIN_COUNT": replay.get("ABSTAIN_COUNT"),
            "DELTA": replay.get("DELTA"),
            "MU_RULE": replay.get("MU_RULE"),
            "UNCONDITIONAL_MEAN": replay.get("UNCONDITIONAL_MEAN"),
            "RULE_ELIGIBLE_N": replay.get("RULE_ELIGIBLE_N"),
            "GATE_PASS": replay.get("GATE_PASS"),
        },
        "metadata_2025": {
            "CONFIRMATION_2025_MONTHS_METADATA_BOUND": meta["CONFIRMATION_2025_MONTHS_METADATA_BOUND"],
            "CONFIRMATION_2025_SOURCE_HASHES_BOUND": meta["CONFIRMATION_2025_SOURCE_HASHES_BOUND"],
            "CONFIRMATION_2025_CANONICAL_HASHES_BOUND": meta["CONFIRMATION_2025_CANONICAL_HASHES_BOUND"],
            "issues": meta["issues"],
            "n_months": meta["n_months"],
            "2026_OBJECT_NEEDED_FOR_FROZEN_INTERVAL": False,
            "binding": BINDING_REL,
        },
        "power": power,
        "EXPECTED_2025_ELIGIBLE_N": power["EXPECTED_2025_ELIGIBLE_N"],
        "EXPECTED_2025_ABSTAIN_COUNT": power["EXPECTED_2025_ABSTAIN_COUNT"],
        "POWER_AT_20PCT_MIN_EFFECT": one_year_joint,
        "POWER_AT_20PCT_MIN_EFFECT_IS_HISTORICAL_JOINT": True,
        "ONE_YEAR_STATISTICAL_POWER_AT_20PCT": one_year_stat,
        "ONE_YEAR_JOINT_PASS_PROBABILITY_AT_20PCT": one_year_joint,
        "PRIMARY_PROSPECTIVE_POWER_CRITERION": "STATISTICAL_POWER_AT_20PCT_EFFECT",
        "POWER_INTERPRETATION_CORRECTION": interpretation,
        "SIZE_PLANNING": size_planning,
        "TWO_YEAR_STATISTICAL_POWER_AT_20PCT": size_planning[
            "TWO_YEAR_STATISTICAL_POWER_AT_20PCT"
        ],
        "THREE_YEAR_STATISTICAL_POWER_AT_20PCT": size_planning[
            "THREE_YEAR_STATISTICAL_POWER_AT_20PCT"
        ],
        "FOUR_YEAR_STATISTICAL_POWER_AT_20PCT": size_planning[
            "FOUR_YEAR_STATISTICAL_POWER_AT_20PCT"
        ],
        "MIN_REQUIRED_FRESH_DECISION_ROWS": size_planning[
            "MIN_REQUIRED_FRESH_DECISION_ROWS"
        ],
        "MIN_REQUIRED_FRESH_YEARS": size_planning["MIN_REQUIRED_FRESH_YEARS"],
        "CONFIRMATION_SURFACE_REQUIREMENT": size_planning[
            "CONFIRMATION_SURFACE_REQUIREMENT"
        ],
        "POTENTIAL_FUTURE_SURFACE": size_planning["POTENTIAL_FUTURE_SURFACE"],
        "AUTHORIZED_TO_OPEN": False,
        "RULE_CHANGED": False,
        "TARGET_CHANGED": False,
        "GATES_CHANGED": False,
        "CONFIRMATION_FEASIBILITY": feasibility,
        "2025_OPEN_AUTHORIZED": False,
        "2025_OPENING_JUSTIFIED_BY_POWER": False,
        "MARKET_07_CREATED": False,
        "ARM_CREATED": False,
        "PROTECTED_2025_OPENED": False,
        "PROTECTED_2026_OPENED": False,
        "PROTECTED_2025_PRICE_VALUES_INSPECTED": False,
        "PROTECTED_2026_PRICE_VALUES_INSPECTED": False,
        "PROTECTED_PRICE_PATHS_OPENED": protected_price_opened,
        "EXPOSED_FILES_OPENED_COUNT": len(opened),
        "EXPOSED_FILES_OPENED_YEARS": sorted(
            {item.split("monthly/")[-1][:4] for item in opened if "monthly/" in item and item.endswith(".parquet")}
        ),
        "IMPLEMENTATION_COMMIT_AUTHORITY": IMPLEMENTATION_COMMIT,
        "NEXT_UNIT": next_unit,
        "WHY_NOT_CONSUME_2026": (
            "2026 remains unopened and is not automatically combined with "
            "2025. Size planning on exposed 2020-2024 data only tells whether "
            "a future predeclared combined fresh surface could be scientifically "
            "worthwhile. AUTHORIZED_TO_OPEN is false. If two years remain "
            "underpowered, do not consume 2025+2026."
        ),
        "NOT_CREATED": [
            "MARKET-07",
            "ARM",
            "reservation",
            "execution permit",
            "final prereg freeze",
            "protected-data loader execution",
            "RESULT artifact",
        ],
    }
    if meta["issues"]:
        report["CONFIRMATION_FEASIBILITY"] = "METADATA_ISSUES_PLUS_" + feasibility
    return report


def _flag(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    return str(value)


def render_markdown(report: dict[str, Any], meta: dict[str, Any]) -> str:
    power = report["power"]
    interp = report["POWER_INTERPRETATION_CORRECTION"]
    size = report["SIZE_PLANNING"]
    original = interp["ORIGINAL_ONE_YEAR_CALCULATION_PRESERVED"]
    sens_lines = []
    for key in ("15pct", "20pct", "25pct", "30pct"):
        row = power["sensitivity"][key]
        mark = " (authoritative 20% true-effect row)" if row["authoritative"] else " (sensitivity only)"
        sens_lines.append(
            f"- {int(row['relative_effect']*100)}% relative{mark}: "
            f"STATISTICAL_POWER = {row['power_statistical_gate']:.3f}; "
            f"JOINT_PASS_PROBABILITY = {row['power_both_gates']:.3f}; "
            f"practical-gate power = {row['power_practical_gate']:.3f} (diagnostic)"
        )
    size_lines = []
    for row in size["surfaces"]:
        s20 = row["sensitivity"]["20pct"]
        extra = []
        for key in ("25pct", "30pct"):
            srow = row["sensitivity"][key]
            extra.append(
                f"{int(srow['relative_effect']*100)}% statistical="
                f"{srow['STATISTICAL_POWER']:.3f} / joint="
                f"{srow['JOINT_PASS_PROBABILITY']:.3f}"
            )
        size_lines.append(
            f"- {row['approx_years']} year ≈ {row['N']} decision rows, "
            f"expected K = {row['expected_K']}: "
            f"STATISTICAL_POWER_AT_20PCT = {s20['STATISTICAL_POWER']:.3f}; "
            f"JOINT_PASS_PROBABILITY_AT_20PCT = {s20['JOINT_PASS_PROBABILITY']:.3f} "
            f"(diagnostic). Sensitivity: {'; '.join(extra)}."
        )
    months = "\n".join(
        f"- `{m['period']}` source `{m['source_filename']}` "
        f"SHA256 `{m['source_SHA256']}` parquet `{m['canonical_parquet_SHA256']}`"
        for m in meta["months"]
    )
    min_rows = report["MIN_REQUIRED_FRESH_DECISION_ROWS"]
    min_years = report["MIN_REQUIRED_FRESH_YEARS"]
    min_rows_txt = "null" if min_rows is None else str(min_rows)
    min_years_txt = "null" if min_years is None else str(min_years)
    return f"""# D2 confirmation feasibility and design

**Unit:** `{report["unit"]}`
**Kind:** `{report["kind"]}`
**Date:** `{report["date"]}`
**Candidate:** `{report["CANDIDATE"]}`
**Discovery status:** `{report["D2_DISCOVERY_STATUS"]}` (adaptive discovery only; not evidence)

This unit does **not** execute confirmation, inspect 2025/2026 BTC price
values, materialize protected parquet, create MARKET-07, or ARM anything.
The scientific confirmation design is unchanged: same rule, target,
comparator, P90 / trailing-250 / 24h horizon / severity target /
random-abstention comparator / 20% practical gate / P95 statistical gate.

## Verdict

| Field | Value |
|---|---|
| `PRIMARY_CONFIRMATION_SURFACE` | `{report["PRIMARY_CONFIRMATION_SURFACE"]}` |
| `SECOND_RESERVED_SURFACE` | `{report["SECOND_RESERVED_SURFACE"]}` |
| `CONFIRMATION_FEASIBILITY` | `{report["CONFIRMATION_FEASIBILITY"]}` |
| `ONE_YEAR_STATISTICAL_POWER_AT_20PCT` | `{report["ONE_YEAR_STATISTICAL_POWER_AT_20PCT"]}` |
| `ONE_YEAR_JOINT_PASS_PROBABILITY_AT_20PCT` | `{report["ONE_YEAR_JOINT_PASS_PROBABILITY_AT_20PCT"]}` |
| `PRIMARY_PROSPECTIVE_POWER_CRITERION` | `{report["PRIMARY_PROSPECTIVE_POWER_CRITERION"]}` |
| `MINIMUM_ACCEPTABLE_CONFIRMATION_POWER` | `{report["MINIMUM_ACCEPTABLE_CONFIRMATION_POWER"]}` |
| `TWO_YEAR_STATISTICAL_POWER_AT_20PCT` | `{report["TWO_YEAR_STATISTICAL_POWER_AT_20PCT"]}` |
| `THREE_YEAR_STATISTICAL_POWER_AT_20PCT` | `{report["THREE_YEAR_STATISTICAL_POWER_AT_20PCT"]}` |
| `FOUR_YEAR_STATISTICAL_POWER_AT_20PCT` | `{report["FOUR_YEAR_STATISTICAL_POWER_AT_20PCT"]}` |
| `MIN_REQUIRED_FRESH_DECISION_ROWS` | `{min_rows_txt}` |
| `MIN_REQUIRED_FRESH_YEARS` | `{min_years_txt}` |
| `CONFIRMATION_SURFACE_REQUIREMENT` | `{report["CONFIRMATION_SURFACE_REQUIREMENT"]}` |
| `POTENTIAL_FUTURE_SURFACE` | `{report["POTENTIAL_FUTURE_SURFACE"]}` |
| `AUTHORIZED_TO_OPEN` | `false` |
| `EXPECTED_2025_ELIGIBLE_N` | `{report["EXPECTED_2025_ELIGIBLE_N"]}` |
| `EXPECTED_2025_ABSTAIN_COUNT` | `{report["EXPECTED_2025_ABSTAIN_COUNT"]}` |
| `2025_OPEN_AUTHORIZED` | `false` |
| `MARKET_07_CREATED` | `false` |
| `ARM_CREATED` | `false` |
| `PROTECTED_2025_PRICE_VALUES_INSPECTED` | `false` |
| `PROTECTED_2026_PRICE_VALUES_INSPECTED` | `false` |
| `RULE_CHANGED` | `false` |
| `TARGET_CHANGED` | `false` |
| `GATES_CHANGED` | `false` |
| `NEXT_UNIT` | `{report["NEXT_UNIT"]}` |

Historical joint field `POWER_AT_20PCT_MIN_EFFECT` remains `{report["POWER_AT_20PCT_MIN_EFFECT"]}`
and is **not** the primary prospective criterion.

## POWER_INTERPRETATION_CORRECTION

Primary prospective power criterion:

`STATISTICAL_POWER_AT_20PCT_EFFECT >= 0.80`

That is the probability the frozen statistical gate
`MU_RULE > P95(random-control means)` passes when the true relative
effect is 20%.

`JOINT_PASS_PROBABILITY_AT_20PCT_EFFECT` (both statistical and practical
gates) is diagnostic only. The practical gate itself is unchanged and
remains an actual execution-time requirement:

`DELTA >= 0.20 * UNCONDITIONAL_MEAN`

{interp["WHY_PRACTICAL_GATE_POWER_NEAR_HALF_IS_NOT_UNDERPOWER"]}

This amendment is an interpretation correction plus fresh-surface size
planning. It is **not** a scientific-design rescue. The 20% effect bar
is not lowered.

### Original one-year calculation (preserved historical output)

Method: {original["method"]}

Seed `{original["POWER_SEED"]}`, n_outer `{power["sensitivity"]["20pct"]["n_outer"]}`,
n_inner `{power["sensitivity"]["20pct"]["n_inner"]}`.

Frozen-rule fireable rate = {power["frozen_rule_fireable_rate"]:.6f}
({power["fireable_abstain_count"]} / {power["fireable_n_2020_2024"]}).

Year-cycled K (not the size-planning frozen-rate K):
`{power.get("year_rule_abstain_count")}`.

{chr(10).join(sens_lines)}

```
ONE_YEAR_STATISTICAL_POWER_AT_20PCT = {report["ONE_YEAR_STATISTICAL_POWER_AT_20PCT"]}
ONE_YEAR_JOINT_PASS_PROBABILITY_AT_20PCT = {report["ONE_YEAR_JOINT_PASS_PROBABILITY_AT_20PCT"]}
historical POWER_AT_20PCT_MIN_EFFECT (joint) = {original["historical_POWER_AT_20PCT_MIN_EFFECT_WAS_JOINT"]}
```

Because `{report["ONE_YEAR_STATISTICAL_POWER_AT_20PCT"]}` is still far
below 0.80, `CONFIRMATION_FEASIBILITY` remains
`UNDERPOWERED_SINGLE_YEAR_2025`.

## Fresh-surface size planning (2020-2024 only)

{size["pool_description"]}

Size-planning seed: `{size["SIZE_PLANNING_SEED"]}`.

{chr(10).join(size_lines)}

```
MIN_REQUIRED_FRESH_DECISION_ROWS = {min_rows_txt}
MIN_REQUIRED_FRESH_YEARS = {min_years_txt}
CONFIRMATION_SURFACE_REQUIREMENT = {report["CONFIRMATION_SURFACE_REQUIREMENT"]}
POTENTIAL_FUTURE_SURFACE = {report["POTENTIAL_FUTURE_SURFACE"]}
AUTHORIZED_TO_OPEN = false
```

2025 remains unopened. 2026 remains unopened. They are not automatically
combined. The sizing result only says whether a future predeclared
combined fresh surface could be scientifically worthwhile.

{report["WHY_NOT_CONSUME_2026"]}

## Candidate (exact survivor only)

`{report["CONFIRMATION_RULE"]}`

Not confirmed: {", ".join(report["NOT_CONFIRMED_VARIANTS"])}.

Mechanism preserved from frozen D2 / implementation `{report["IMPLEMENTATION_COMMIT_AUTHORITY"]}`:

- schedule: {report["DECISION_SCHEDULE"]}
- exposure: {report["BASE_EXPOSURE"]}
- direction: {report["DIRECTION"]}
- entry: {report["ENTRY"]}
- target: {report["CONFIRMATION_TARGET"]}

## Independent surface

Primary: calendar **2025 only**, Binance USD-M BTCUSDT perpetual,
`CORE_BTC_BINANCE_V0` snapshot `{CORE_SNAPSHOT}`.

```
FIRST_T = {report["FIRST_T"]}
LAST_T  = {report["LAST_T"]}
T in {report["CONFIRMATION_T_INTERVAL"]}
```

2020-2024 is historically exposed and is **not** independent confirmation.
{report["WARMUP"]}

## 2025 metadata-only binding

Binding file: `{BINDING_REL}`. No price values. Objects were not
downloaded or materialized.

Months bound: {meta["n_months"]}/12.
Source hashes bound: `{_flag(meta["CONFIRMATION_2025_SOURCE_HASHES_BOUND"])}`.
Canonical hashes bound: `{_flag(meta["CONFIRMATION_2025_CANONICAL_HASHES_BOUND"])}`.
Issues: {meta["issues"] or "none"}.
2026 object needed for frozen interval: `false`
(last future bar opens `{meta["LAST_FUTURE_BAR_OPEN"]}`).

{months}

## Estimand and gates

Comparator: {report["CONFIRMATION_COMPARATOR"]}

Quantities: `MU_RULE`, `MU_CONTROL_MEAN`, `DELTA = MU_RULE - MU_CONTROL_MEAN`,
`UNCONDITIONAL_MEAN`.

Statistical: {report["CONFIRMATION_STATISTICAL_GATE"]}

Seed frozen now: `D2_CONFIRMATION_RANDOM_CONTROL_SEED = {report["D2_CONFIRMATION_RANDOM_CONTROL_SEED"]}`.
Replicates: `{report["N_REPLICATES_CONFIRMATION"]}`.

Practical: {report["CONFIRMATION_PRACTICAL_GATE"]}

Pass: {report["PASS_RULE"]}. No quarterly rescue, threshold change, sign
reversal, alternative comparator, D5 combination, or horizon swap.

Quarters `{report["TEMPORAL_REPORTING"]["quarters_diagnostic_only"]}` are
diagnostic only.

Future execution labels (not assigned here):
{report["FUTURE_EXECUTION_CLASSIFICATIONS_NOT_ASSIGNED"]}.

## Discovery provenance (planning context only)

Eligible 1791, abstain 163, `MU_RULE` 0.04005839896629072,
`MU_CONTROL_MEAN` 0.025856224865193674, `DELTA` 0.014202174101097049,
`GATE_PASS` true, 5/5 positive years.

Do not use +0.0142 as the minimum effect. Do not power solely at that
observed effect. Do not shrink the 20% bar. Do not call it evidence.

## Independence boundary

Protected 2025/2026 price values inspected: `false` / `false`.
Exposed parquet years opened: {report["EXPOSED_FILES_OPENED_YEARS"]}.
Protected price paths opened: {report["PROTECTED_PRICE_PATHS_OPENED"] or "none"}.

## Not created

{chr(10).join(f"- {item}" for item in report["NOT_CREATED"])}
"""


def write_artifacts(
    *,
    repo: Path | None = None,
    rewrite_binding: bool = False,
    recompute_one_year_power: bool = False,
) -> dict[str, Any]:
    base = _repo(repo)
    meta = extract_2025_metadata(repo=base)
    report = run_feasibility(repo=base, recompute_one_year_power=recompute_one_year_power)
    if rewrite_binding:
        binding = {
            "schema": "signalbot_d2_confirmation_2025_metadata_binding",
            "snapshot_id": CORE_SNAPSHOT,
            "PRIMARY_CONFIRMATION_SURFACE": "2025",
            "SECOND_RESERVED_SURFACE": "2026",
            "contains_price_values": False,
            "objects_materialized": False,
            "objects": [
                {
                    "period": m["period"],
                    "source_filename": m["source_filename"],
                    "source_SHA256": m["source_SHA256"],
                    "canonical_parquet_relative_path": m["canonical_parquet_relative_path"],
                    "canonical_parquet_SHA256": m["canonical_parquet_SHA256"],
                }
                for m in meta["months"]
            ],
            "coverage_metadata_not_prices": [
                {
                    "period": m["period"],
                    "expected_rows": m["expected_rows"],
                    "observed_rows": m["observed_rows"],
                    "missing_bucket_count": m["missing_bucket_count"],
                    "first_open_time_ms": m["first_open_time_ms"],
                    "last_open_time_ms": m["last_open_time_ms"],
                    "admitted_to_canonical": m["admitted_to_canonical"],
                    "checksum_verification": m["checksum_verification"],
                    "parser_status": m["parser_status"],
                }
                for m in meta["months"]
            ],
            "2026_OBJECT_NEEDED_FOR_FROZEN_INTERVAL": False,
        }
        (base / BINDING_REL).write_text(
            json.dumps(binding, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    (base / JSON_REL).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (base / MD_REL).write_text(render_markdown(report, meta), encoding="utf-8")
    return report


if __name__ == "__main__":
    written = write_artifacts(rewrite_binding=False, recompute_one_year_power=False)
    keys = (
        "CONFIRMATION_FEASIBILITY",
        "ONE_YEAR_STATISTICAL_POWER_AT_20PCT",
        "ONE_YEAR_JOINT_PASS_PROBABILITY_AT_20PCT",
        "TWO_YEAR_STATISTICAL_POWER_AT_20PCT",
        "THREE_YEAR_STATISTICAL_POWER_AT_20PCT",
        "FOUR_YEAR_STATISTICAL_POWER_AT_20PCT",
        "MIN_REQUIRED_FRESH_DECISION_ROWS",
        "MIN_REQUIRED_FRESH_YEARS",
        "CONFIRMATION_SURFACE_REQUIREMENT",
        "POTENTIAL_FUTURE_SURFACE",
        "NEXT_UNIT",
        "PROTECTED_2025_PRICE_VALUES_INSPECTED",
        "RULE_CHANGED",
        "TARGET_CHANGED",
        "GATES_CHANGED",
        "2025_OPEN_AUTHORIZED",
    )
    print(json.dumps({k: written[k] for k in keys}, indent=2))
