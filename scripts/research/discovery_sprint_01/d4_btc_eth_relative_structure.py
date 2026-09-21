"""D4 BTC_ETH_RELATIVE_STRUCTURE — ROLLING_CORRELATION_90D only."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from scripts.research.discovery_sprint_01 import common as C
from scripts.research.market_06_cross_venue_dislocation_evaluator import (
    FUTURE_BARS,
    btc_ret_24h,
    feature_cutoff_ms,
    get_perp_bar_ending_at,
    is_forbidden_decision,
)


SEARCH_SURFACE = ["ROLLING_CORRELATION_90D"]
LEAD_LAG_STATUS = "DEFERRED_FROM_SPRINT_01"


def refuse_lead_lag() -> None:
    raise C.DeferredFunctionalError("D4_LEAD_LAG_1DAY_DEFERRED_FROM_SPRINT_01")


def paired_daily_log_returns(
    btc: Mapping[int, C.PerpBar],
    eth: Mapping[int, C.PerpBar],
    start=C.D4_INTERVAL_START,
    end_exclusive=C.DISCOVERY_END,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    btc_rets: list[float] = []
    eth_rets: list[float] = []
    years: list[int] = []
    for moment in C.iter_discovery_decision_times(start, end_exclusive):
        if is_forbidden_decision(moment) is not None:
            continue
        t_ms = C.ms_from_utc(moment)
        e_ms = feature_cutoff_ms(t_ms)
        btc_e = get_perp_bar_ending_at(btc, e_ms)
        btc_p = get_perp_bar_ending_at(btc, e_ms - FUTURE_BARS * C.BAR_MS)
        eth_e = get_perp_bar_ending_at(eth, e_ms)
        eth_p = get_perp_bar_ending_at(eth, e_ms - FUTURE_BARS * C.BAR_MS)
        if None in (btc_e, btc_p, eth_e, eth_p):
            continue
        try:
            br = btc_ret_24h(btc_e.close, btc_p.close)
            er = btc_ret_24h(eth_e.close, eth_p.close)
        except Exception:
            continue
        btc_rets.append(float(br))
        eth_rets.append(float(er))
        years.append(int(moment.year))
    return (
        np.asarray(btc_rets, dtype=np.float64),
        np.asarray(eth_rets, dtype=np.float64),
        np.asarray(years, dtype=np.int64),
    )


def evaluate_rolling_correlation(
    btc_ret: np.ndarray,
    eth_ret: np.ndarray,
    years: np.ndarray,
    *,
    seed: int = C.D4_NULL_SEED,
    n_replicates: int = C.N_REPLICATES,
    block_length: int = C.D4_BLOCK_LENGTH,
) -> dict[str, Any]:
    observed = C.rolling_pearson(btc_ret, eth_ret, window=C.D4_ROLLING_WINDOW)
    finite = C.finite_series(observed)
    obs_range = C.observed_correlation_range(observed)
    obs_var = float(np.var(finite, ddof=0)) if finite.size else float("nan")
    null_ranges: list[float] = []
    null_vars: list[float] = []
    for btc_s, eth_s in C.circular_block_bootstrap_paired(
        btc_ret,
        eth_ret,
        block_length=block_length,
        n_replicates=n_replicates,
        seed=seed,
    ):
        series = C.rolling_pearson(btc_s, eth_s, window=C.D4_ROLLING_WINDOW)
        finite_s = C.finite_series(series)
        null_ranges.append(C.observed_correlation_range(series))
        null_vars.append(float(np.var(finite_s, ddof=0)) if finite_s.size else float("nan"))
    null_range_arr = np.asarray(null_ranges, dtype=np.float64)
    null_var_arr = np.asarray(null_vars, dtype=np.float64)
    null_range_median = float(np.nanmedian(null_range_arr))
    excess = C.practical_excess_range(obs_range, null_range_median)
    var_p975 = float(np.nanpercentile(null_var_arr, 97.5))
    statistical = bool(obs_var > var_p975)
    practical = bool(excess >= C.D4_PRACTICAL_GATE)
    year_ranges: dict[str, float | None] = {}
    material_years = 0
    for year in sorted(set(int(y) for y in years.tolist())):
        # Align rolling-corr index i with year[i] of the window end.
        sel = (years == year) & np.isfinite(observed)
        if not np.any(sel):
            year_ranges[str(year)] = None
            continue
        yr = float(np.max(observed[sel]) - np.min(observed[sel]))
        year_ranges[str(year)] = yr
        if np.isfinite(obs_range) and obs_range > 0.0 and yr >= 0.15 * obs_range:
            material_years += 1
        elif yr > 0.0:
            material_years += 1
    temporal = bool(material_years >= 2)
    unconditional = float(np.corrcoef(btc_ret, eth_ret)[0, 1]) if btc_ret.size >= 2 else None
    return {
        "OBSERVED_CORRELATION_RANGE": obs_range,
        "NULL_RANGE_MEDIAN": null_range_median,
        "PRACTICAL_EXCESS_RANGE": excess,
        "OBSERVED_VARIANCE": obs_var,
        "NULL_VARIANCE_P97_5": var_p975,
        "STATISTICAL_THRESHOLD_MET": statistical,
        "PRACTICAL_MAGNITUDE_MET": practical,
        "TEMPORAL_CONSISTENCY_MET": temporal,
        "YEAR_RANGES": year_ranges,
        "UNCONDITIONAL_CORRELATION": unconditional,
        "N_PAIRS": int(btc_ret.size),
        "N_ROLLING_POINTS": int(finite.size),
        "GATE_PASS": bool(statistical and practical and temporal),
        "LEAD_LAG_1DAY_EXECUTED": False,
        "LEAD_LAG_1DAY_STATUS": LEAD_LAG_STATUS,
    }


def classify_d4(report: Mapping[str, Any] | None, *, missing: Sequence[str]) -> str:
    if missing:
        return "BLOCKED_MISSING_LOCAL_DATA"
    if report is None:
        return "INCONCLUSIVE_DISCOVERY"
    if report.get("LEAD_LAG_1DAY_EXECUTED"):
        return "INVALID_DISCOVERY"
    if report.get("GATE_PASS"):
        return "PROMISING_PROTOTYPE"
    return "NO_USEFUL_STRUCTURE"


def run_d4(
    *,
    implementation_commit: str,
    output_dir: Path | None = None,
    repo: Path | None = None,
    n_replicates: int = C.N_REPLICATES,
    btc_perp: Mapping[int, C.PerpBar] | None = None,
    eth_perp: Mapping[int, C.PerpBar] | None = None,
    execute_lead_lag: bool = False,
) -> dict[str, Any]:
    if execute_lead_lag:
        refuse_lead_lag()
    base = repo or C.repo_root()
    log = C.OpenedFileLog()
    preflight = C.preflight_local_data(base)
    missing: list[str] = []
    if btc_perp is None and not preflight["BTC_DATA_PRESENT"]:
        missing.append("CORE_BTC_BINANCE_V0_MONTHLY_PARQUET")
    if eth_perp is None and not preflight["ETH_DATA_PRESENT"]:
        missing.append("CORE_ETH_BINANCE_V0_MONTHLY_PARQUET")
    if btc_perp is None and "CORE_BTC_BINANCE_V0_MONTHLY_PARQUET" not in missing:
        try:
            btc_perp = C.load_core_btc_5m(log, repo=base)
        except C.MissingLocalData as exc:
            missing.append(str(exc))
            btc_perp = None
    if eth_perp is None and "CORE_ETH_BINANCE_V0_MONTHLY_PARQUET" not in missing:
        try:
            eth_perp = C.load_core_eth_5m(log, repo=base)
        except C.MissingLocalData as exc:
            missing.append(str(exc))
            eth_perp = None
    report = None
    years: list[int] = []
    if btc_perp is not None and eth_perp is not None:
        btc_ret, eth_ret, year_arr = paired_daily_log_returns(btc_perp, eth_perp)
        years = [int(y) for y in year_arr.tolist()]
        if btc_ret.size < C.D4_ROLLING_WINDOW:
            missing.append("D4_INSUFFICIENT_PAIRED_RETURNS")
        else:
            report = evaluate_rolling_correlation(
                btc_ret, eth_ret, year_arr, n_replicates=n_replicates
            )
    classification = classify_d4(report, missing=missing)
    year_breakdown: dict[str, int] = {}
    for year in years:
        year_breakdown[str(year)] = year_breakdown.get(str(year), 0) + 1
    payload = {
        "DISCOVERY_ID": "D4",
        "NAME": "BTC_ETH_RELATIVE_STRUCTURE",
        "SPEC_AUTHORITY": C.SPEC_AUTHORITY,
        "IMPLEMENTATION_COMMIT": implementation_commit,
        "DATASET_IDENTITIES": {
            C.CORE_BTC_DATASET_ID: C.CORE_BTC_SNAPSHOT,
            C.CORE_ETH_DATASET_ID: C.CORE_ETH_SNAPSHOT,
        },
        "INTERVAL_USED": "2020-02-01T00:05:00Z -> 2025-01-01T00:00:00Z exclusive",
        "FILES_OPENED": list(log.files),
        "SEARCH_SURFACE_ATTEMPTED": SEARCH_SURFACE,
        "SEEDS": {"D4_NULL_SEED": C.D4_NULL_SEED},
        "ROW_COUNTS": {"N_PAIRS": None if report is None else report.get("N_PAIRS")},
        "YEAR_BREAKDOWN": year_breakdown,
        "PRIMARY_METRICS": report or {},
        "BASELINE_METRICS": {
            "NULL": "BLOCK_BOOTSTRAP_PAIRED_RETURNS",
            "BLOCK_LENGTH": C.D4_BLOCK_LENGTH,
            "UNCONDITIONAL_CORRELATION": None if report is None else report.get("UNCONDITIONAL_CORRELATION"),
        },
        "PROTOTYPE_GATE_FIELDS": {
            "statistical_gate": "observed rolling-corr variance > null 97.5th percentile",
            "practical_gate": "PRACTICAL_EXCESS_RANGE >= 0.15",
            "PRACTICAL_EXCESS_RANGE_FORMULA": "OBSERVED_CORRELATION_RANGE - NULL_RANGE_MEDIAN",
            "LEAD_LAG_1DAY": LEAD_LAG_STATUS,
        },
        "TERMINAL_CLASSIFICATION": classification,
        "KNOWN_LIMITATIONS": [
            "Two-asset precursor only; not cross-sectional panel structure.",
            "LEAD_LAG_1DAY deferred from Sprint 01.",
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
            output_dir / "D4_DISCOVERY_RESULT.json",
            output_dir / "D4_DISCOVERY_RESULT.md",
            title="D4 BTC_ETH_RELATIVE_STRUCTURE",
        )
    return payload
