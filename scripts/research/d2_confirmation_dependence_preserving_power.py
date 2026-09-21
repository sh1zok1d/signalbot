"""Dependence-preserving D2 confirmation size planning.

Year-matched whole-year block resampling plus contiguous partial-year
blocks. Does not open 2025/2026 prices. Does not change the frozen
confirmation rule, target, comparator, or gates.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np

from scripts.research.discovery_sprint_01 import common as C

UTC = timezone.utc

D2_CONFIRMATION_DEPENDENCE_PRESERVING_SEED = 20260921123
N_REPLICATES_CONFIRMATION = 10_000
N_POWER_OUTER = 1_000
MINIMUM_ACCEPTABLE_CONFIRMATION_POWER = 0.80
AUTHORITATIVE_RELATIVE_EFFECT = 0.20
FULL_2025_CONFIRMATION_ROWS = 364
COMPLETE_EXPOSED_YEARS = (2021, 2022, 2023, 2024)
FIXED_N_POWER_GRID = (364, 550, 575, 600, 625, 650, 675, 700, 728, 1092, 1456)
AUTHORITATIVE_POWER_METHOD = "YEAR_MATCHED_WHOLE_YEAR_PLUS_CONTIGUOUS_PARTIAL_BLOCK"
STATUS_DATE = datetime(2026, 9, 21, tzinfo=UTC)


def extract_complete_year_blocks(rows: list[C.DiscoveryRow]) -> dict[int, dict[str, np.ndarray]]:
    mask = C.rv_abstention_mask(rows)
    years = np.asarray([row.year for row in rows], dtype=np.int64)
    sev = np.asarray([row.severity for row in rows], dtype=np.float64)
    blocks: dict[int, dict[str, np.ndarray]] = {}
    for year in COMPLETE_EXPOSED_YEARS:
        idx = years == year
        y = sev[idx]
        m = mask[idx]
        if y.size < 2:
            raise RuntimeError(f"EMPTY_YEAR_BLOCK:{year}")
        blocks[int(year)] = {"severity": y.copy(), "mask": m.copy()}
    return blocks


def circular_shift_mask(mask: np.ndarray, rng: np.random.Generator) -> tuple[np.ndarray, int]:
    n = int(mask.size)
    if n <= 1:
        return np.asarray(mask, dtype=bool).copy(), 0
    offset = int(rng.integers(1, n))
    return np.roll(np.asarray(mask, dtype=bool), offset), offset


def expected_year_matched_control_mean(
    y: np.ndarray, block_slices: list[tuple[int, int]], block_k: list[int]
) -> float:
    k_tot = int(sum(block_k))
    if k_tot <= 0:
        raise ValueError("EXPECTED_CONTROL_EMPTY_K")
    acc = 0.0
    for (lo, hi), k in zip(block_slices, block_k):
        if k == 0:
            continue
        acc += float(k) * float(y[lo:hi].mean())
    return acc / float(k_tot)


def calibrate_year_matched_relative_effect(
    y: np.ndarray,
    selected: np.ndarray,
    block_slices: list[tuple[int, int]],
    *,
    relative: float = AUTHORITATIVE_RELATIVE_EFFECT,
) -> np.ndarray:
    """Additive shift on selected rows so DELTA vs expected year-matched control is r * uncond."""
    y = np.asarray(y, dtype=np.float64)
    selected = np.asarray(selected, dtype=bool)
    n = int(y.size)
    k_tot = int(selected.sum())
    if k_tot <= 0 or k_tot >= n:
        raise ValueError(f"CALIBRATION_BAD_K:{k_tot}:{n}")
    block_k = [int(selected[lo:hi].sum()) for lo, hi in block_slices]
    mu = float(y.mean())
    mu_rule = float(y[selected].mean())
    e_ctrl = expected_year_matched_control_mean(y, block_slices, block_k)
    alpha = 0.0
    for (lo, hi), k in zip(block_slices, block_k):
        n_b = int(hi - lo)
        if k == 0 or n_b == 0:
            continue
        alpha += (float(k) ** 2) / float(n_b)
    alpha /= float(k_tot)
    p = float(k_tot) / float(n)
    denom = (1.0 - alpha) - float(relative) * p
    if abs(denom) < 1e-12:
        raise ValueError("YEAR_MATCHED_CALIBRATION_DENOM_ZERO")
    shift = (float(relative) * mu - (mu_rule - e_ctrl)) / denom
    out = y.copy()
    out[selected] = out[selected] + shift
    return out


def year_matched_control_means(
    y: np.ndarray,
    block_slices: list[tuple[int, int]],
    block_k: list[int],
    n_rep: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Each replicate draws exactly K_b rows without replacement inside block b."""
    k_tot = int(sum(block_k))
    if k_tot <= 0:
        raise ValueError("CONTROL_EMPTY_K")
    acc = np.zeros(int(n_rep), dtype=np.float64)
    for (lo, hi), k in zip(block_slices, block_k):
        if k == 0:
            continue
        n_b = int(hi - lo)
        if k > n_b:
            raise ValueError(f"BLOCK_K_EXCEEDS_N:{k}:{n_b}")
        yb = y[lo:hi]
        keys = rng.random((int(n_rep), n_b))
        idx = np.argpartition(keys, kth=int(k) - 1, axis=1)[:, : int(k)]
        acc += yb[idx].sum(axis=1)
    return acc / float(k_tot)


def year_matched_control_selected_counts(
    block_slices: list[tuple[int, int]],
    block_k: list[int],
    n_rep: int,
    rng: np.random.Generator,
    n_total: int,
) -> np.ndarray:
    """Boolean selected matrix (n_rep, n_total); year-matched draws."""
    out = np.zeros((int(n_rep), int(n_total)), dtype=bool)
    for (lo, hi), k in zip(block_slices, block_k):
        if k == 0:
            continue
        n_b = int(hi - lo)
        keys = rng.random((int(n_rep), n_b))
        idx = np.argpartition(keys, kth=int(k) - 1, axis=1)[:, : int(k)]
        rows = np.arange(int(n_rep))[:, None]
        out[rows, lo + idx] = True
    return out


def construct_fixed_n_surface(
    year_blocks: dict[int, dict[str, np.ndarray]],
    n_rows: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray, list[tuple[int, int]], list[dict[str, Any]]]:
    """Whole-year blocks plus one contiguous partial block, association-broken."""
    years = list(year_blocks.keys())
    remaining = int(n_rows)
    sev_parts: list[np.ndarray] = []
    mask_parts: list[np.ndarray] = []
    slices: list[tuple[int, int]] = []
    meta: list[dict[str, Any]] = []
    cursor = 0
    while remaining > 0:
        year = int(years[int(rng.integers(0, len(years)))])
        block = year_blocks[year]
        y = np.asarray(block["severity"], dtype=np.float64)
        m_shift, offset = circular_shift_mask(np.asarray(block["mask"], dtype=bool), rng)
        n_year = int(y.size)
        if remaining >= n_year:
            take = n_year
            start = 0
            y_seg = y
            m_seg = m_shift
            whole = True
        else:
            take = remaining
            start = int(rng.integers(0, n_year - take + 1))
            end = start + take
            y_seg = y[start:end]
            m_seg = m_shift[start:end]
            whole = False
        sev_parts.append(np.asarray(y_seg, dtype=np.float64))
        mask_parts.append(np.asarray(m_seg, dtype=bool))
        slices.append((cursor, cursor + take))
        meta.append(
            {
                "source_year": year,
                "length": int(take),
                "whole_year": bool(whole),
                "start": int(start),
                "end": int(start + take),
                "shift_offset": int(offset),
                "K": int(np.asarray(m_seg).sum()),
                "contiguous": True,
                "association_broken": int(offset) != 0,
            }
        )
        cursor += take
        remaining -= take
    y_out = np.concatenate(sev_parts)
    m_out = np.concatenate(mask_parts)
    if int(y_out.size) != int(n_rows):
        raise RuntimeError(f"SURFACE_N:{y_out.size}:{n_rows}")
    return y_out, m_out, slices, meta


def frozen_2026_prefix_from_total_n(total_n: int) -> dict[str, Any]:
    """Calendar-only 2026 prefix for a fixed total N. No prices."""
    if total_n <= FULL_2025_CONFIRMATION_ROWS:
        return {
            "FROZEN_2026_PREFIX_DECISION_COUNT": 0,
            "FROZEN_FINAL_DECISION_TIMESTAMP": None,
            "FIRST_2026_T": None,
            "uses_2026": False,
        }
    n_2026 = int(total_n - FULL_2025_CONFIRMATION_ROWS)
    first = datetime(2026, 1, 1, 0, 5, tzinfo=UTC)
    last = first + timedelta(days=n_2026 - 1)
    if last.month == 12 and last.day == 31:
        raise ValueError("DECEMBER_31_FORBIDDEN")
    if last.year != 2026:
        raise ValueError(f"PREFIX_LEAVES_2026:{last.isoformat()}")
    return {
        "FROZEN_2026_PREFIX_DECISION_COUNT": n_2026,
        "FROZEN_FINAL_DECISION_TIMESTAMP": last.isoformat().replace("+00:00", "Z"),
        "FIRST_2026_T": first.isoformat().replace("+00:00", "Z"),
        "uses_2026": True,
    }


def elapsed_2026_completed_decision_count(as_of: datetime = STATUS_DATE) -> int:
    """Mechanical count of 2026 decisions whose 24h window ends before as_of 00:00Z."""
    as_of_midnight = datetime(as_of.year, as_of.month, as_of.day, tzinfo=UTC)
    first = datetime(2026, 1, 1, 0, 5, tzinfo=UTC)
    n = 0
    cursor = first
    while cursor.year == 2026:
        if cursor.month == 12 and cursor.day == 31:
            cursor = cursor + timedelta(days=1)
            continue
        last_bar = datetime(cursor.year, cursor.month, cursor.day, tzinfo=UTC) + timedelta(days=1)
        if last_bar >= as_of_midnight:
            break
        n += 1
        cursor = cursor + timedelta(days=1)
    return n


def inject_and_gates(
    y: np.ndarray,
    selected: np.ndarray,
    block_slices: list[tuple[int, int]],
    n_inner: int,
    rng: np.random.Generator,
    *,
    relative: float = AUTHORITATIVE_RELATIVE_EFFECT,
) -> dict[str, Any]:
    block_k = [int(selected[lo:hi].sum()) for lo, hi in block_slices]
    y_alt = calibrate_year_matched_relative_effect(
        y, selected, block_slices, relative=relative
    )
    mu_rule = float(y_alt[selected].mean())
    uncond = float(y_alt.mean())
    e_ctrl = expected_year_matched_control_mean(y_alt, block_slices, block_k)
    injected = (mu_rule - e_ctrl) / uncond if uncond != 0.0 else float("nan")
    ctrl = year_matched_control_means(y_alt, block_slices, block_k, n_inner, rng)
    mu_control_mean = float(ctrl.mean())
    delta = float(mu_rule - mu_control_mean)
    p95 = float(np.percentile(ctrl, 95))
    statistical = bool(mu_rule > p95)
    practical = bool(uncond != 0.0 and delta >= AUTHORITATIVE_RELATIVE_EFFECT * uncond)
    return {
        "STATISTICAL_GATE": statistical,
        "PRACTICAL_MAGNITUDE_GATE": practical,
        "BOTH": bool(statistical and practical),
        "injected_relative_vs_expected_control": injected,
        "MU_RULE": mu_rule,
        "EXPECTED_CONTROL_MEAN": e_ctrl,
        "UNCONDITIONAL_MEAN": uncond,
        "DELTA_MC": delta,
        "CONTROL_P95": p95,
        "block_k": block_k,
    }


def estimate_dependence_preserving_size_planning(
    rows: list[C.DiscoveryRow],
    *,
    seed: int = D2_CONFIRMATION_DEPENDENCE_PRESERVING_SEED,
    n_outer: int = N_POWER_OUTER,
    n_inner: int = N_REPLICATES_CONFIRMATION,
    n_grid: tuple[int, ...] = FIXED_N_POWER_GRID,
) -> dict[str, Any]:
    """Authoritative fresh-surface power: year-matched whole-year + contiguous partial."""
    year_blocks = extract_complete_year_blocks(rows)
    rng = np.random.default_rng(int(seed))
    surfaces: list[dict[str, Any]] = []
    for n_rows in n_grid:
        stat_n = 0
        prac_n = 0
        both_n = 0
        injected_err = 0.0
        n_valid = 0
        for _ in range(int(n_outer)):
            y, selected, slices, _meta = construct_fixed_n_surface(
                year_blocks, int(n_rows), rng
            )
            k_tot = int(selected.sum())
            if k_tot <= 0 or k_tot >= int(y.size):
                continue
            inner_rng = np.random.default_rng(int(rng.integers(0, 2**31 - 1)))
            result = inject_and_gates(y, selected, slices, n_inner, inner_rng)
            n_valid += 1
            injected_err += abs(
                float(result["injected_relative_vs_expected_control"])
                - AUTHORITATIVE_RELATIVE_EFFECT
            )
            if result["STATISTICAL_GATE"]:
                stat_n += 1
            if result["PRACTICAL_MAGNITUDE_GATE"]:
                prac_n += 1
            if result["BOTH"]:
                both_n += 1
        denom = float(n_outer)
        surfaces.append(
            {
                "N": int(n_rows),
                "STATISTICAL_POWER_AT_20PCT": stat_n / denom,
                "JOINT_PASS_PROBABILITY_AT_20PCT": both_n / denom,
                "power_practical_gate": prac_n / denom,
                "n_outer": int(n_outer),
                "n_inner": int(n_inner),
                "n_valid": int(n_valid),
                "mean_abs_injection_error": (injected_err / n_valid) if n_valid else None,
            }
        )
    by_n = {int(row["N"]): row for row in surfaces}
    min_rows: int | None = None
    for n_rows in n_grid:
        if n_rows > 728:
            continue
        if float(by_n[n_rows]["STATISTICAL_POWER_AT_20PCT"]) >= MINIMUM_ACCEPTABLE_CONFIRMATION_POWER:
            min_rows = int(n_rows)
            break
    if min_rows is None:
        for n_rows in n_grid:
            if float(by_n[n_rows]["STATISTICAL_POWER_AT_20PCT"]) >= MINIMUM_ACCEPTABLE_CONFIRMATION_POWER:
                min_rows = int(n_rows)
                break
    prefix = (
        frozen_2026_prefix_from_total_n(min_rows)
        if min_rows is not None and min_rows <= 728
        else {
            "FROZEN_2026_PREFIX_DECISION_COUNT": None,
            "FROZEN_FINAL_DECISION_TIMESTAMP": None,
            "FIRST_2026_T": None,
            "uses_2026": False,
        }
    )
    elapsed = elapsed_2026_completed_decision_count()
    if min_rows is None:
        potential = "MORE_THAN_2025_PLUS_2026_OR_ALTERNATIVE_INDEPENDENT_SURFACE"
        next_unit = "D2_CONFIRMATION_WAIT_FOR_3Y_INDEPENDENT_FRESH_SURFACE_OR_FIND_EQUIVALENT"
        requirement = "MORE_THAN_4_YEARS_OR_ALTERNATIVE_INDEPENDENT_SURFACE"
        n_2026: int | None = None
    elif min_rows < 728:
        potential = "PREDECLARED_2025_PLUS_FIXED_PREFIX_OF_2026"
        next_unit = (
            "D2_CONFIRMATION_WAIT_FOR_PREDECLARED_2025_PLUS_FIXED_2026_PREFIX_WITHOUT_OPENING"
        )
        requirement = "FIXED_N_INDEPENDENT_FRESH"
        n_2026 = int(min_rows - FULL_2025_CONFIRMATION_ROWS)
    elif min_rows == 728:
        potential = "PREDECLARED_2025_PLUS_FULL_2026"
        next_unit = "D2_CONFIRMATION_WAIT_FOR_PREDECLARED_2025_PLUS_2026_WITHOUT_OPENING"
        requirement = "TWO_YEARS_INDEPENDENT_FRESH"
        n_2026 = FULL_2025_CONFIRMATION_ROWS
    elif min_rows <= 1092:
        potential = "MORE_THAN_2025_PLUS_2026_OR_ALTERNATIVE_INDEPENDENT_SURFACE"
        next_unit = "D2_CONFIRMATION_WAIT_FOR_3Y_INDEPENDENT_FRESH_SURFACE_OR_FIND_EQUIVALENT"
        requirement = "THREE_YEARS_INDEPENDENT_FRESH"
        n_2026 = None
    else:
        potential = "MORE_THAN_2025_PLUS_2026_OR_ALTERNATIVE_INDEPENDENT_SURFACE"
        next_unit = "D2_CONFIRMATION_WAIT_FOR_4Y_INDEPENDENT_FRESH_SURFACE_OR_FIND_EQUIVALENT"
        requirement = "FOUR_YEARS_OR_MORE_INDEPENDENT_FRESH"
        n_2026 = None
    min_years = None if min_rows is None else float(min_rows) / float(FULL_2025_CONFIRMATION_ROWS)
    return {
        "AUTHORITATIVE_POWER_METHOD": AUTHORITATIVE_POWER_METHOD,
        "DEPENDENCE_PRESERVING_SEED": int(seed),
        "n_outer": int(n_outer),
        "n_inner": int(n_inner),
        "FIXED_N_POWER_GRID": [int(n) for n in n_grid],
        "COMPLETE_EXPOSED_YEARS": [int(y) for y in COMPLETE_EXPOSED_YEARS],
        "method": (
            "YEAR_MATCHED_WHOLE_YEAR_PLUS_CONTIGUOUS_PARTIAL_BLOCK. "
            "Sample complete 2021-2024 years with replacement. Preserve "
            "chronological severity and circularly-shifted frozen RULE_1 "
            "mask clustering. Remainder N uses one contiguous partial-year "
            "block. Inner controls draw exactly K_b rows inside each block. "
            "No pooled K-subset. No IID daily resampling. 20% effect is "
            "injected against the expected year-matched control mean."
        ),
        "surfaces": surfaces,
        "ONE_YEAR_STATISTICAL_POWER_AT_20PCT_DEPENDENCE_PRESERVING": by_n.get(364, {}).get(
            "STATISTICAL_POWER_AT_20PCT"
        ),
        "TWO_YEAR_STATISTICAL_POWER_AT_20PCT": by_n.get(728, {}).get(
            "STATISTICAL_POWER_AT_20PCT"
        ),
        "THREE_YEAR_STATISTICAL_POWER_AT_20PCT": by_n.get(1092, {}).get(
            "STATISTICAL_POWER_AT_20PCT"
        ),
        "FOUR_YEAR_STATISTICAL_POWER_AT_20PCT": by_n.get(1456, {}).get(
            "STATISTICAL_POWER_AT_20PCT"
        ),
        "POWER_BY_N": {str(row["N"]): row["STATISTICAL_POWER_AT_20PCT"] for row in surfaces},
        "JOINT_BY_N": {str(row["N"]): row["JOINT_PASS_PROBABILITY_AT_20PCT"] for row in surfaces},
        "MIN_REQUIRED_FRESH_DECISION_ROWS": min_rows,
        "MIN_REQUIRED_FRESH_YEARS": min_years,
        "MIN_REQUIRED_FRESH_2026_ROWS_AFTER_FULL_2025": n_2026,
        "FROZEN_2026_PREFIX_DECISION_COUNT": prefix.get("FROZEN_2026_PREFIX_DECISION_COUNT"),
        "FROZEN_FINAL_DECISION_TIMESTAMP": prefix.get("FROZEN_FINAL_DECISION_TIMESTAMP"),
        "ELAPSED_2026_COMPLETED_DECISION_COUNT_ASOF_2026_09_21": elapsed,
        "CONFIRMATION_SURFACE_REQUIREMENT": requirement,
        "POTENTIAL_FUTURE_SURFACE": potential,
        "AUTHORIZED_TO_OPEN": False,
        "NEXT_UNIT": next_unit,
        "RULE_CHANGED": False,
        "TARGET_CHANGED": False,
        "GATES_CHANGED": False,
        "effect_bar_lowered": False,
        "full_calendar_2026_not_currently_available": True,
        "pooled_k_subset_used": False,
        "iid_row_resampling_used": False,
    }
