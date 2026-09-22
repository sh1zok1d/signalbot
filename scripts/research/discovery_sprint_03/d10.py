"""D10 BTC-ETH residual shock persistence. OPTION A: no-intercept OLS.

beta_t = sum(x*y)/sum(x^2) on the previous 720 valid completed hours strictly
before t. The same beta_t is reused for e_t and e_{t+1}. Event hour t and
hour t+1 are never in the fit. Feasibility may count events/controls; it
must not emit the signed next-hour persistence effect.
"""

from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from scripts.research.discovery_sprint_03 import common as C


def no_intercept_beta(r_btc: Sequence[float], r_eth: Sequence[float]) -> float:
    """OPTION A. Fail closed if the BTC denominator is zero or any value is nonfinite."""

    x = np.asarray(list(r_btc), dtype=np.float64)
    y = np.asarray(list(r_eth), dtype=np.float64)
    if x.size != y.size or x.size == 0:
        raise C.Sprint03IntegrityError("D10_BETA_WINDOW_SHAPE")
    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
        raise C.Sprint03IntegrityError("D10_BETA_NONFINITE_WINDOW")
    denom = float(np.dot(x, x))
    if denom == 0.0 or not math.isfinite(denom):
        raise C.Sprint03IntegrityError("D10_BETA_UNDEFINED")
    beta = float(np.dot(x, y) / denom)
    if not math.isfinite(beta):
        raise C.Sprint03IntegrityError("D10_BETA_NONFINITE")
    return beta


def residual(r_eth: float, r_btc: float, beta: float) -> float:
    if not math.isfinite(r_eth) or not math.isfinite(r_btc) or not math.isfinite(beta):
        raise C.Sprint03IntegrityError("D10_RESIDUAL_NONFINITE")
    return float(r_eth - beta * r_btc)


def signed_persistence(e_t: float, e_t_plus_1: float) -> float:
    if e_t == 0.0:
        return 0.0
    return float(math.copysign(1.0, e_t) * e_t_plus_1)


def d10_fixed_beta_row(
    r_btc: Sequence[float],
    r_eth: Sequence[float],
    t: int,
    *,
    window: int = C.D10_WINDOW,
) -> dict[str, Any]:
    """Pure row on positional arrays. Window is [t-window, t); t and t+1 excluded."""

    if t < window or t + 1 >= len(r_btc) or t + 1 >= len(r_eth):
        raise C.Sprint03IntegrityError("D10_ROW_OUT_OF_RANGE")
    beta = no_intercept_beta(r_btc[t - window : t], r_eth[t - window : t])
    e_t = residual(float(r_eth[t]), float(r_btc[t]), beta)
    e_tp1 = residual(float(r_eth[t + 1]), float(r_btc[t + 1]), beta)
    return {
        "beta_t": beta,
        "e_t": e_t,
        "e_t_plus_1_fixed_beta": e_tp1,
        "primary_target": signed_persistence(e_t, e_tp1),
        "window_start": t - window,
        "window_end_exclusive": t,
        "REGRESSION_SPECIFICATION": C.D10_REGRESSION_SPECIFICATION,
    }


def classify_d10_from_summary(summary: Mapping[str, Any]) -> str:
    return C.classify_discovery(summary)


def d10_statistical_gate(
    event_targets: Sequence[float],
    control_targets: Sequence[float],
    event_by_cell: Mapping[str, Sequence[float]] | None = None,
    control_by_cell: Mapping[str, Sequence[float]] | None = None,
    *,
    seed: int = C.D10_SEED,
    n: int = C.D10_N_RANDOMIZATIONS,
) -> dict[str, Any]:
    event = np.asarray(list(event_targets), dtype=np.float64)
    control = np.asarray(list(control_targets), dtype=np.float64)
    if event.size == 0 or control.size == 0:
        raise C.Sprint03IntegrityError("D10_EMPTY_TARGET_SAMPLE")
    if not np.all(np.isfinite(event)) or not np.all(np.isfinite(control)):
        raise C.Sprint03IntegrityError("D10_NONFINITE_TARGET")
    mean_event = float(event.mean())
    mean_control = float(control.mean())
    delta = mean_event - mean_control
    if event_by_cell is None or control_by_cell is None:
        event_by_cell = {"ALL": list(event_targets)}
        control_by_cell = {"ALL": list(control_targets)}
    p_value = C.stratified_label_permutation_p(
        event_by_cell,
        control_by_cell,
        observed=delta,
        statistic=lambda ev, ct: float(np.mean(ev) - np.mean(ct)),
        seed=seed,
        n=n,
        alternative="greater",
    )
    return {
        "MEAN_EVENT": mean_event,
        "MEAN_CONTROL": mean_control,
        "DELTA": delta,
        "MC_P": p_value,
        "STATISTICAL_GATE": bool(p_value < C.D10_MC_ALPHA and delta > 0.0),
        "PERMUTATION_RULE": (
            "STRATIFIED_LABEL_PERMUTATION inside YEAR x SIGN_E_T x "
            "ABS_BTC_RETURN_BUCKET; preserve event/control counts per stratum"
        ),
        "SEED": seed,
        "N_RANDOMIZATIONS": n,
        "TEMPORAL_DEPENDENCE_LIMITATION": C.D10_TEMPORAL_DEPENDENCE_LIMITATION,
    }


def evaluate_d10_scientific(
    event_targets: Sequence[float],
    control_targets: Sequence[float],
    yearly_event_targets: Mapping[str, Sequence[float]],
    yearly_control_targets: Mapping[str, Sequence[float]],
    *,
    support: Mapping[str, Any],
    event_by_cell: Mapping[str, Sequence[float]] | None = None,
    control_by_cell: Mapping[str, Sequence[float]] | None = None,
) -> dict[str, Any]:
    """Pure scientific evaluator on supplied arrays. No market I/O."""

    stats = d10_statistical_gate(
        event_targets,
        control_targets,
        event_by_cell=event_by_cell,
        control_by_cell=control_by_cell,
    )
    practical = bool(stats["DELTA"] >= C.D10_PRACTICAL_DELTA)
    temporal_ok = 0
    yearly: dict[str, float | None] = {}
    for year in sorted(set(yearly_event_targets) | set(yearly_control_targets)):
        ev = list(yearly_event_targets.get(year) or [])
        ct = list(yearly_control_targets.get(year) or [])
        yearly[year] = None
        if len(ev) < 1 or len(ct) < 1:
            continue
        delta_y = float(np.mean(ev) - np.mean(ct))
        yearly[year] = delta_y
        if stats["DELTA"] > 0 and delta_y > 0:
            temporal_ok += 1
    temporal = bool(temporal_ok >= C.D10_TEMPORAL_YEARS_REQUIRED)
    summary = {
        **stats,
        "PRACTICAL_GATE": practical,
        "TEMPORAL_GATE": temporal,
        "YEARLY_DELTA": yearly,
        "TEMPORAL_YEARS_OK": temporal_ok,
        "SUPPORT_PASS": bool(support.get("SUPPORT_PASS")),
        "IDENTITY_OK": bool(support.get("IDENTITY_OK", True)),
        "REGRESSION_SPECIFICATION": C.D10_REGRESSION_SPECIFICATION,
        "PRIMARY_STATISTIC": "MEAN_EVENT_SIGNED_PERSISTENCE_MINUS_MEAN_CONTROL",
    }
    summary["CLASSIFICATION"] = classify_d10_from_summary(summary)
    return summary


def _dense_hour_grid(start_ms: int, end_ms: int) -> np.ndarray:
    n = (end_ms - start_ms) // C.HOUR_MS
    return start_ms + np.arange(n, dtype=np.int64) * C.HOUR_MS


def aligned_return_arrays(
    btc_closes: Mapping[int, float],
    eth_closes: Mapping[int, float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    hours = _dense_hour_grid(C.LEGAL_START_MS, C.PROTECTED_START_MS)
    btc = np.full(hours.size, np.nan, dtype=np.float64)
    eth = np.full(hours.size, np.nan, dtype=np.float64)
    index = {int(ms): i for i, ms in enumerate(hours.tolist())}
    for ms, px in btc_closes.items():
        i = index.get(int(ms))
        if i is not None:
            btc[i] = float(px)
    for ms, px in eth_closes.items():
        i = index.get(int(ms))
        if i is not None:
            eth[i] = float(px)
    r_btc = np.full(hours.size, np.nan, dtype=np.float64)
    r_eth = np.full(hours.size, np.nan, dtype=np.float64)
    valid_prev = np.isfinite(btc[:-1]) & (btc[:-1] > 0) & np.isfinite(eth[:-1]) & (eth[:-1] > 0)
    valid_cur = np.isfinite(btc[1:]) & (btc[1:] > 0) & np.isfinite(eth[1:]) & (eth[1:] > 0)
    both = valid_prev & valid_cur
    r_btc[1:][both] = np.log(btc[1:][both] / btc[:-1][both])
    r_eth[1:][both] = np.log(eth[1:][both] / eth[:-1][both])
    return hours, r_btc, r_eth, both


def trailing_no_intercept_beta(r_btc: np.ndarray, r_eth: np.ndarray) -> np.ndarray:
    """beta[t] uses r[t-720:t]. Current t excluded. t+1 excluded."""

    n = int(r_btc.size)
    beta = np.full(n, np.nan, dtype=np.float64)
    finite = np.isfinite(r_btc) & np.isfinite(r_eth)
    xx = np.where(finite, r_btc * r_btc, np.nan)
    xy = np.where(finite, r_btc * r_eth, np.nan)
    # Fail closed unless the entire calendar window is finite.
    ok = np.convolve(finite.astype(np.int32), np.ones(C.D10_WINDOW, dtype=np.int32), mode="full")
    window_ok = ok[C.D10_WINDOW - 1 : C.D10_WINDOW - 1 + n] == C.D10_WINDOW
    cs_xx = np.concatenate([[0.0], np.nancumsum(np.where(finite, xx, 0.0))])
    cs_xy = np.concatenate([[0.0], np.nancumsum(np.where(finite, xy, 0.0))])
    for t in range(C.D10_WINDOW, n):
        if not window_ok[t - 1]:
            continue
        # window_ok[t-1] means finite[t-720:t] all true? 
        # convolve ok[t-1] with ones(720) at position covering r[t-720:t].
        denom = float(cs_xx[t] - cs_xx[t - C.D10_WINDOW])
        if denom == 0.0 or not math.isfinite(denom):
            continue
        beta[t] = float((cs_xy[t] - cs_xy[t - C.D10_WINDOW]) / denom)
    return beta


def _window_all_finite(finite: np.ndarray) -> np.ndarray:
    """window_ok[t] is true iff finite[t-720:t] are all true. t itself excluded."""

    n = int(finite.size)
    out = np.zeros(n, dtype=bool)
    counts = np.concatenate([[0], np.cumsum(finite.astype(np.int32))])
    for t in range(C.D10_WINDOW, n):
        out[t] = (counts[t] - counts[t - C.D10_WINDOW]) == C.D10_WINDOW
    return out


def d10_feasibility_census(
    btc_closes: Mapping[int, float],
    eth_closes: Mapping[int, float],
    *,
    include_indices: bool = False,
) -> dict[str, Any]:
    """Structural support only. Does not return persistence targets.

    Controls are 1:1 YEAR x SIGN_E_T x ABS_BTC_RETURN_BUCKET samples from
    the small-|e| (trailing P50) non-event population, without replacement.
    """

    hours, r_btc, r_eth, _adj = aligned_return_arrays(btc_closes, eth_closes)
    n = int(hours.size)
    finite_r = np.isfinite(r_btc) & np.isfinite(r_eth)
    window_ok = _window_all_finite(finite_r)
    cs_xx = np.concatenate([[0.0], np.cumsum(np.where(finite_r, r_btc * r_btc, 0.0))])
    cs_xy = np.concatenate([[0.0], np.cumsum(np.where(finite_r, r_btc * r_eth, 0.0))])
    beta = np.full(n, np.nan, dtype=np.float64)
    for t in range(C.D10_WINDOW, n):
        if not window_ok[t]:
            continue
        denom = float(cs_xx[t] - cs_xx[t - C.D10_WINDOW])
        if denom == 0.0 or not math.isfinite(denom):
            continue
        beta[t] = float((cs_xy[t] - cs_xy[t - C.D10_WINDOW]) / denom)
    e = np.full(n, np.nan, dtype=np.float64)
    defined = np.isfinite(beta) & finite_r
    e[defined] = r_eth[defined] - beta[defined] * r_btc[defined]
    abs_e = np.abs(e)
    abs_btc = np.abs(r_btc)
    finite_e = np.isfinite(e)
    e_window_ok = _window_all_finite(finite_e)
    btc_window_ok = _window_all_finite(np.isfinite(abs_btc) & finite_r)

    cs_abs_e = np.concatenate([[0.0], np.cumsum(np.where(finite_e, abs_e, 0.0))])

    event_idx: list[int] = []
    raw_control_idx: list[int] = []
    event_ids_by_cell: dict[str, list[int]] = {}
    raw_control_ids_by_cell: dict[str, list[int]] = {}
    event_by_year: dict[str, int] = {str(y): 0 for y in C.CONTROL_YEARS}
    event_by_sign: dict[str, int] = {"+1": 0, "-1": 0}
    event_by_cell: dict[str, int] = {}
    control_by_year: dict[str, int] = {str(y): 0 for y in C.CONTROL_YEARS}
    prefix_ok_n = 0
    aligned_n = int(np.sum(finite_r))

    def cell_key(year: int, sign: int, bucket: int) -> str:
        return f"{year}:{sign}:{bucket}"

    for t in range(C.D10_WINDOW, n - 1):
        if not window_ok[t] or not np.isfinite(beta[t]) or not finite_e[t]:
            continue
        if not e_window_ok[t] or not btc_window_ok[t]:
            continue
        if hours[t] + 2 * C.HOUR_MS >= C.PROTECTED_START_MS:
            continue
        if not finite_r[t + 1]:
            continue
        prefix_ok_n += 1
        trailing_e = abs_e[t - C.D10_WINDOW : t]
        trailing_btc = abs_btc[t - C.D10_WINDOW : t]
        p90 = C.percentile(trailing_e, C.D10_PCTL)
        p50 = C.percentile(trailing_e, C.D10_CONTROL_PCTL)
        bucket = C.quantile_bucket(float(abs_btc[t]), trailing_btc.tolist())
        year = datetime.fromtimestamp(int(hours[t]) / 1000.0, tz=C.UTC).year
        sign = 1 if e[t] > 0 else -1
        if e[t] == 0.0:
            continue
        key = cell_key(year, sign, bucket)
        is_event = bool(abs_e[t] > p90)
        is_control = (not is_event) and bool(abs_e[t] <= p50)
        if is_event:
            event_idx.append(t)
            event_ids_by_cell.setdefault(key, []).append(t)
            event_by_year[str(year)] = event_by_year.get(str(year), 0) + 1
            event_by_sign[f"{sign:+d}"] = event_by_sign.get(f"{sign:+d}", 0) + 1
            event_by_cell[key] = event_by_cell.get(key, 0) + 1
        elif is_control:
            raw_control_idx.append(t)
            raw_control_ids_by_cell.setdefault(key, []).append(t)
            control_by_year[str(year)] = control_by_year.get(str(year), 0) + 1

    matched_ids_by_cell, balanced = C.sample_matched_ids_per_cell(
        event_ids_by_cell,
        raw_control_ids_by_cell,
        seed=C.D10_CONTROL_SAMPLE_SEED,
    )
    matched_control_by_cell = {k: len(v) for k, v in matched_ids_by_cell.items()}
    matched_idx = [cid for ids in matched_ids_by_cell.values() for cid in ids]
    if len(matched_idx) != len(set(matched_idx)):
        raise C.Sprint03IntegrityError("D10_CONTROL_REUSED")
    matched_control_n = len(matched_idx)
    cells_balanced = bool(balanced) and matched_control_n == len(event_idx)
    if cells_balanced:
        for key, n_ev in event_by_cell.items():
            if matched_control_by_cell.get(key, 0) != n_ev:
                cells_balanced = False
                break
    years_with_both = 0
    for year in map(str, C.CONTROL_YEARS):
        has_event = event_by_year.get(year, 0) > 0
        has_control = any(
            k.startswith(f"{year}:") and v > 0 for k, v in matched_control_by_cell.items()
        )
        if has_event and has_control:
            years_with_both += 1
    years_with_events = [y for y, n_y in event_by_year.items() if n_y > 0]
    support_pass = bool(
        len(event_idx) >= C.D10_MIN_EVENTS
        and len(years_with_events) >= C.D10_MIN_YEARS_WITH_EVENTS
        and matched_control_n >= C.D10_MIN_MATCHED_CONTROLS
        and years_with_both >= C.D10_MIN_YEARS_WITH_EVENT_AND_CONTROL
        and cells_balanced
    )
    if len(event_idx) < C.D10_MIN_EVENTS or len(years_with_events) < C.D10_MIN_YEARS_WITH_EVENTS:
        status = "DEFERRED_INSUFFICIENT_EVENT_SUPPORT"
    elif (
        not cells_balanced
        or matched_control_n < C.D10_MIN_MATCHED_CONTROLS
        or years_with_both < C.D10_MIN_YEARS_WITH_EVENT_AND_CONTROL
    ):
        status = "DEFERRED_INSUFFICIENT_CONTROL_SUPPORT"
    else:
        status = "OUTCOME_BLIND_IMPLEMENTATION_READY"
    _ = cs_abs_e
    out: dict[str, Any] = {
        "ALIGNED_HOUR_RETURNS": aligned_n,
        "LEGAL_720H_PREFIX_SUPPORT_N": prefix_ok_n,
        "EVENT_N": len(event_idx),
        "RAW_ELIGIBLE_CONTROL_N": len(raw_control_idx),
        "CONTROL_N": len(raw_control_idx),
        "MATCHED_CONTROL_N": matched_control_n,
        "ALL_MATCHED_CELLS_BALANCED": cells_balanced,
        "EVENT_BY_YEAR": event_by_year,
        "CONTROL_BY_YEAR": control_by_year,
        "EVENT_BY_SIGN": event_by_sign,
        "EVENT_BY_YEAR_SIGN_BTC_BUCKET": event_by_cell,
        "RAW_CONTROL_BY_YEAR_SIGN_BTC_BUCKET": {
            k: len(v) for k, v in raw_control_ids_by_cell.items()
        },
        "MATCHED_CONTROL_BY_YEAR_SIGN_BTC_BUCKET": matched_control_by_cell,
        "CONTROL_BY_YEAR_SIGN_BTC_BUCKET": matched_control_by_cell,
        "YEARS_WITH_EVENTS": years_with_events,
        "YEARS_WITH_EVENT_AND_CONTROL": years_with_both,
        "SUPPORT_PASS": support_pass,
        "STATUS": status,
        "REGRESSION_SPECIFICATION": C.D10_REGRESSION_SPECIFICATION,
        "CONTROL_SAMPLE_SEED": C.D10_CONTROL_SAMPLE_SEED,
        "PERMUTATION_SEED": C.D10_SEED,
        "MATCH_RULE": (
            "1:1 YEAR x SIGN_E_T x ABS_BTC_RETURN_BUCKET without replacement; "
            "|e_t|<=trailing P50 and not event"
        ),
        "PERMUTATION_RULE": (
            "STRATIFIED_LABEL_PERMUTATION inside YEAR x SIGN_E_T x "
            "ABS_BTC_RETURN_BUCKET"
        ),
        "TEMPORAL_DEPENDENCE_LIMITATION": C.D10_TEMPORAL_DEPENDENCE_LIMITATION,
        "PERSISTENCE_VALUES_EMITTED": False,
    }
    if include_indices:
        out["EVENT_IDX"] = event_idx
        out["RAW_CONTROL_IDX"] = raw_control_idx
        out["MATCHED_CONTROL_IDX"] = matched_idx
        out["EVENT_IDS_BY_CELL"] = event_ids_by_cell
        out["MATCHED_CONTROL_IDS_BY_CELL"] = matched_ids_by_cell
        out["RAW_CONTROL_IDS_BY_CELL"] = raw_control_ids_by_cell
    return out


def load_d10_inputs(*, repo: Path | None = None) -> tuple[dict[int, float], dict[int, float], dict[str, Any]]:
    base = repo or C.repo_root()
    log = C.OpenedFileLog()
    btc_checksums = C.btc_legal_parquet_checksums(base)
    eth_checksums = C.eth_legal_parquet_checksums(base)
    try:
        btc = C.load_hourly_closes(
            dataset_id=C.CORE_BTC_DATASET_ID,
            snapshot_id=C.CORE_BTC_SNAPSHOT_ID,
            root_rel=C.CORE_BTC_ROOT_REL,
            checksums=btc_checksums,
            log=log,
            repo=base,
        )
        eth = C.load_hourly_closes(
            dataset_id=C.CORE_ETH_DATASET_ID,
            snapshot_id=C.CORE_ETH_SNAPSHOT_ID,
            root_rel=C.CORE_ETH_ROOT_REL,
            checksums=eth_checksums,
            log=log,
            repo=base,
        )
    except C.MissingLocalData as exc:
        raise C.MissingLocalData(f"D10_DATA_MATERIAL_BLOCKED:{exc}") from exc
    identity = {
        "CORE_BTC_SNAPSHOT_ID": C.CORE_BTC_SNAPSHOT_ID,
        "CORE_ETH_SNAPSHOT_ID": C.CORE_ETH_SNAPSHOT_ID,
        "BTC_HOURS": len(btc),
        "ETH_HOURS": len(eth),
        "FILES_OPENED": log.files,
        "IDENTITY_OK": True,
        "OPENED_1H_BARS_PARQUET": False,
    }
    return btc, eth, identity
