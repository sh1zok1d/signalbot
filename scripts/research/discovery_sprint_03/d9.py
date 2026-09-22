"""D9 venue-resolution attribution: algebra, selector, guarded evaluator.

Feasibility may count TOTAL_CLOSURE>0 eligibility. It must not emit SHARE
summaries. Median is the frozen location statistic because SHARE is a ratio
with an arbitrarily small positive denominator.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from scripts.research.discovery_sprint_01 import common as sprint01
from scripts.research.discovery_sprint_03 import common as C


@dataclass(frozen=True)
class D9ShareRow:
    eligible: bool
    reason: str
    total_closure: float | None
    perp_resolution_share: float | None


def d9_relative_resolution(d_u: float, rp: float, rs: float) -> D9ShareRow:
    if d_u == 0 or not math.isfinite(d_u):
        return D9ShareRow(False, "D_ZERO_OR_NONFINITE", None, None)
    if not math.isfinite(rp) or not math.isfinite(rs):
        return D9ShareRow(False, "NONFINITE_RETURN", None, None)
    s = math.copysign(1.0, d_u)
    total_closure = -s * (rp - rs)
    if total_closure <= 0:
        return D9ShareRow(False, "NO_GENUINE_CLOSURE", total_closure, None)
    share = (-s * rp) / total_closure
    if not math.isfinite(share):
        return D9ShareRow(False, "NONFINITE_SHARE", total_closure, None)
    return D9ShareRow(True, "GENUINE_CLOSURE", total_closure, share)


def median_share(shares: Sequence[float]) -> float:
    """Frozen primary location statistic. Unclipped. No winsorization."""

    return C.median(shares)


def classify_d9_from_summary(summary: Mapping[str, Any]) -> str:
    """Deterministic discovery predicate. Does not inspect raw bars."""

    return C.classify_discovery(summary)


def d9_p_half(
    event_shares: Sequence[float],
    *,
    seed: int = C.D9_SEED,
    n: int = C.D9_N_RANDOMIZATIONS,
) -> dict[str, Any]:
    observed = np.asarray(list(event_shares), dtype=np.float64)
    if observed.size == 0:
        raise C.Sprint03IntegrityError("D9_EMPTY_SHARE_SAMPLE")
    if not np.all(np.isfinite(observed)):
        raise C.Sprint03IntegrityError("D9_NONFINITE_SHARE_SAMPLE")
    obs_median = float(np.median(observed))
    obs_abs = abs(obs_median - C.D9_NULL_SHARE)
    rng = np.random.default_rng(seed)
    centered = observed - C.D9_NULL_SHARE
    exceed = 0
    for _ in range(n):
        signs = rng.choice(np.array([-1.0, 1.0]), size=centered.size)
        med = float(np.median(C.D9_NULL_SHARE + signs * centered))
        if abs(med - C.D9_NULL_SHARE) >= obs_abs:
            exceed += 1
    p_value = (1.0 + exceed) / (1.0 + n)
    return {
        "MEDIAN_SHARE": obs_median,
        "ABS_VS_HALF": obs_abs,
        "P_HALF": p_value,
        "SEED_HALF": seed,
        "N_RANDOMIZATIONS": n,
    }


def d9_p_control(
    event_by_cell: Mapping[str, Sequence[float]],
    control_by_cell: Mapping[str, Sequence[float]],
    *,
    seed: int = C.D9_CONTROL_PERM_SEED,
    n: int = C.D9_N_RANDOMIZATIONS,
) -> dict[str, Any]:
    event_all = np.concatenate(
        [np.asarray(list(event_by_cell[k]), dtype=np.float64) for k in sorted(event_by_cell)]
    )
    control_all = np.concatenate(
        [np.asarray(list(control_by_cell[k]), dtype=np.float64) for k in sorted(control_by_cell)]
    )
    event_med = float(np.median(event_all))
    control_med = float(np.median(control_all))
    observed = event_med - control_med
    p_value = C.stratified_label_permutation_p(
        event_by_cell,
        control_by_cell,
        observed=observed,
        statistic=lambda ev, ct: float(np.median(ev) - np.median(ct)),
        seed=seed,
        n=n,
        alternative="two-sided-abs",
    )
    return {
        "CONTROL_MEDIAN_SHARE": control_med,
        "ABS_VS_CONTROL": abs(observed),
        "P_CONTROL": p_value,
        "SEED_CONTROL": seed,
    }


def d9_statistical_gate(
    event_shares: Sequence[float],
    control_shares: Sequence[float],
    event_by_cell: Mapping[str, Sequence[float]] | None = None,
    control_by_cell: Mapping[str, Sequence[float]] | None = None,
    *,
    seed: int = C.D9_SEED,
    n: int = C.D9_N_RANDOMIZATIONS,
) -> dict[str, Any]:
    half = d9_p_half(event_shares, seed=seed, n=n)
    if event_by_cell is None or control_by_cell is None:
        event_by_cell = {"ALL": list(event_shares)}
        control_by_cell = {"ALL": list(control_shares)}
    control = d9_p_control(event_by_cell, control_by_cell, n=n)
    statistical = bool(
        half["P_HALF"] < C.D9_MC_ALPHA and control["P_CONTROL"] < C.D9_MC_ALPHA
    )
    return {
        **half,
        **control,
        "MC_P": half["P_HALF"],
        "STATISTICAL_GATE": statistical,
        "STATISTICAL_GATE_RULE": "P_HALF < 0.05 AND P_CONTROL < 0.05",
        "SEED": seed,
        "N_RANDOMIZATIONS": n,
    }


def evaluate_d9_scientific(
    event_shares: Sequence[float],
    control_shares: Sequence[float],
    yearly_event_shares: Mapping[str, Sequence[float]],
    *,
    support: Mapping[str, Any],
    event_by_cell: Mapping[str, Sequence[float]] | None = None,
    control_by_cell: Mapping[str, Sequence[float]] | None = None,
) -> dict[str, Any]:
    """Pure scientific evaluator on supplied arrays. No market I/O."""

    stats = d9_statistical_gate(
        event_shares,
        control_shares,
        event_by_cell=event_by_cell,
        control_by_cell=control_by_cell,
    )
    event_med = stats["MEDIAN_SHARE"]
    control_med = stats["CONTROL_MEDIAN_SHARE"]
    practical = bool(
        stats["ABS_VS_HALF"] >= C.D9_PRACTICAL_ABS_VS_HALF
        and math.isfinite(control_med)
        and abs(event_med - control_med) >= C.D9_PRACTICAL_ABS_VS_CONTROL
    )
    temporal_ok = 0
    yearly: dict[str, float | None] = {}
    pooled_sign = math.copysign(1.0, event_med - C.D9_NULL_SHARE)
    for year, shares in sorted(yearly_event_shares.items()):
        arr = list(shares)
        yearly[year] = None
        if len(arr) < C.D9_TEMPORAL_MIN_CLOSING_PER_YEAR:
            continue
        med = C.median(arr)
        yearly[year] = med
        if (
            math.copysign(1.0, med - C.D9_NULL_SHARE) == pooled_sign
            and abs(med - C.D9_NULL_SHARE) >= C.D9_TEMPORAL_YEAR_ABS_VS_HALF
        ):
            temporal_ok += 1
    temporal = bool(temporal_ok >= C.D9_TEMPORAL_YEARS_REQUIRED)
    summary = {
        **stats,
        "CONTROL_MEDIAN_SHARE": control_med,
        "PRACTICAL_GATE": practical,
        "TEMPORAL_GATE": temporal,
        "YEARLY_MEDIAN_SHARE": yearly,
        "TEMPORAL_YEARS_OK": temporal_ok,
        "SUPPORT_PASS": bool(support.get("SUPPORT_PASS")),
        "IDENTITY_OK": bool(support.get("IDENTITY_OK", True)),
        "PRIMARY_LOCATION_STATISTIC": C.D9_PRIMARY_LOCATION_STATISTIC,
        "SCIENTIFIC_CLAIM_MAY_ESTABLISH": "CONDITIONAL_VENUE_RESOLUTION_ATTRIBUTION",
    }
    summary["CLASSIFICATION"] = classify_d9_from_summary(summary)
    return summary


def _aligned_m06_series(
    perp: Mapping[int, Any],
    spot: Mapping[int, float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    opens = sorted(
        ts
        for ts in perp
        if ts >= C.M06_START_MS
        and ts < C.PROTECTED_START_MS
        and ts in spot
        and ts % C.BAR_5M_MS == 0
    )
    if not opens:
        raise C.MissingLocalData("D9_NO_ALIGNED_BARS")
    open_ms = np.asarray(opens, dtype=np.int64)
    perp_close = np.asarray([float(perp[int(ts)].close) for ts in opens], dtype=np.float64)
    spot_close = np.asarray([float(spot[int(ts)]) for ts in opens], dtype=np.float64)
    return open_ms, perp_close, spot_close


def d9_feasibility_census(
    perp: Mapping[int, Any],
    spot: Mapping[int, float],
    *,
    include_indices: bool = False,
) -> dict[str, Any]:
    """Structural support only. Does not return SHARE values.

    IS_EXTREME_BAR is computed from trailing P90 independently of the
    keep-first / 12-bar refractory rule. Controls require IS_EXTREME_BAR
    == false. A refractory-dropped extreme is neither a primary event nor
    a control. Matched controls are a 1:1 YEAR x SIGN_D x RV_BUCKET sample
    of closing non-extreme bars, without replacement.
    """

    open_ms, perp_close, spot_close = _aligned_m06_series(perp, spot)
    n = int(open_ms.size)
    valid_d = np.zeros(n, dtype=bool)
    abs_d = np.full(n, np.nan)
    sign_d = np.zeros(n, dtype=np.int8)
    rv = np.full(n, np.nan)
    d_values = np.log(perp_close / spot_close)
    for i in range(n):
        if open_ms[i] + C.D9_H_BARS * C.BAR_5M_MS >= C.PROTECTED_START_MS:
            continue
        if not math.isfinite(d_values[i]) or d_values[i] == 0.0:
            continue
        if perp_close[i] <= 0 or spot_close[i] <= 0:
            continue
        valid_d[i] = True
        abs_d[i] = abs(d_values[i])
        sign_d[i] = 1 if d_values[i] > 0 else -1
        if i > 0 and open_ms[i] - open_ms[i - 1] == C.BAR_5M_MS:
            if perp_close[i - 1] > 0 and math.isfinite(perp_close[i - 1]):
                rv[i] = abs(math.log(perp_close[i] / perp_close[i - 1]))
    valid_abs: list[float] = []
    valid_rv: list[float] = []
    valid_abs_pos = np.full(n, -1, dtype=np.int32)
    valid_rv_pos = np.full(n, -1, dtype=np.int32)
    is_extreme = np.zeros(n, dtype=bool)
    for i in range(n):
        if valid_d[i]:
            valid_abs_pos[i] = len(valid_abs)
            valid_abs.append(float(abs_d[i]))
        if math.isfinite(rv[i]):
            valid_rv_pos[i] = len(valid_rv)
            valid_rv.append(float(rv[i]))
        if not valid_d[i]:
            continue
        if valid_abs_pos[i] < C.D9_TRAILING_WINDOW:
            continue
        trailing_abs = valid_abs[valid_abs_pos[i] - C.D9_TRAILING_WINDOW : valid_abs_pos[i]]
        p90 = C.percentile(trailing_abs, C.D9_PCTL)
        is_extreme[i] = bool(abs_d[i] > p90)

    event_idx: list[int] = []
    refractory_dropped_idx: list[int] = []
    last_kept = -10**9
    for i in range(n):
        if not is_extreme[i]:
            continue
        if not math.isfinite(rv[i]) or valid_rv_pos[i] < C.D9_TRAILING_WINDOW:
            continue
        if i - last_kept < C.D9_MIN_EVENT_GAP_BARS:
            refractory_dropped_idx.append(i)
            continue
        event_idx.append(i)
        last_kept = i

    def bucket_at(i: int) -> int | None:
        pos = int(valid_rv_pos[i])
        if pos < C.D9_TRAILING_WINDOW:
            return None
        trailing = valid_rv[pos - C.D9_TRAILING_WINDOW : pos]
        return C.quantile_bucket(float(rv[i]), trailing)

    closing_by_year: dict[str, int] = {str(y): 0 for y in (2022, 2023, 2024)}
    event_by_year: dict[str, int] = {str(y): 0 for y in (2022, 2023, 2024)}
    event_by_sign: dict[str, int] = {"+1": 0, "-1": 0}
    event_by_year_sign_bucket: dict[str, int] = {}
    closing_by_year_sign_bucket: dict[str, int] = {}
    raw_control_ids_by_cell: dict[str, list[int]] = {}
    closing_event_ids_by_cell: dict[str, list[int]] = {}
    closing_n = 0
    horizon = C.D9_H_BARS

    def cell_key(year: int, sign: int, bucket: int) -> str:
        return f"{year}:{sign}:{bucket}"

    closing_event_idx: list[int] = []
    for i in event_idx:
        year = datetime.fromtimestamp(int(open_ms[i]) / 1000.0, tz=C.UTC).year
        event_by_year[str(year)] = event_by_year.get(str(year), 0) + 1
        event_by_sign[f"{int(sign_d[i]):+d}"] = event_by_sign.get(f"{int(sign_d[i]):+d}", 0) + 1
        j = i + horizon
        if j >= n or open_ms[j] != open_ms[i] + horizon * C.BAR_5M_MS:
            continue
        if open_ms[i] + horizon * C.BAR_5M_MS >= C.PROTECTED_START_MS:
            continue
        rp = math.log(perp_close[j] / perp_close[i])
        rs = math.log(spot_close[j] / spot_close[i])
        row = d9_relative_resolution(float(d_values[i]), rp, rs)
        bucket = bucket_at(i)
        if bucket is None:
            continue
        key = cell_key(year, int(sign_d[i]), bucket)
        event_by_year_sign_bucket[key] = event_by_year_sign_bucket.get(key, 0) + 1
        if row.eligible:
            closing_n += 1
            closing_event_idx.append(i)
            closing_by_year[str(year)] = closing_by_year.get(str(year), 0) + 1
            closing_by_year_sign_bucket[key] = closing_by_year_sign_bucket.get(key, 0) + 1
            closing_event_ids_by_cell.setdefault(key, []).append(i)

    raw_control_idx: list[int] = []
    for i in range(n):
        if is_extreme[i] or not valid_d[i]:
            continue
        if not math.isfinite(rv[i]):
            continue
        j = i + horizon
        if j >= n or open_ms[j] != open_ms[i] + horizon * C.BAR_5M_MS:
            continue
        if open_ms[i] + horizon * C.BAR_5M_MS >= C.PROTECTED_START_MS:
            continue
        rp = math.log(perp_close[j] / perp_close[i])
        rs = math.log(spot_close[j] / spot_close[i])
        row = d9_relative_resolution(float(d_values[i]), rp, rs)
        if not row.eligible:
            continue
        bucket = bucket_at(i)
        if bucket is None:
            continue
        year = datetime.fromtimestamp(int(open_ms[i]) / 1000.0, tz=C.UTC).year
        key = cell_key(year, int(sign_d[i]), bucket)
        raw_control_ids_by_cell.setdefault(key, []).append(i)
        raw_control_idx.append(i)

    matched_ids_by_cell, balanced = C.sample_matched_ids_per_cell(
        closing_event_ids_by_cell,
        raw_control_ids_by_cell,
        seed=C.D9_CONTROL_SAMPLE_SEED,
    )
    matched_control_by_cell = {k: len(v) for k, v in matched_ids_by_cell.items()}
    matched_idx = [cid for ids in matched_ids_by_cell.values() for cid in ids]
    if len(matched_idx) != len(set(matched_idx)):
        raise C.Sprint03IntegrityError("D9_CONTROL_REUSED")
    matched_n = len(matched_idx)
    raw_eligible_n = len(raw_control_idx)
    years_with_both = 0
    years_closing = [y for y, n_y in closing_by_year.items() if n_y > 0]
    for year in ("2022", "2023", "2024"):
        has_event = closing_by_year.get(year, 0) > 0
        has_control = any(
            k.startswith(f"{year}:") and v > 0 for k, v in matched_control_by_cell.items()
        )
        if has_event and has_control:
            years_with_both += 1
    cells_balanced = bool(balanced) and matched_n == closing_n
    if cells_balanced:
        for key, n_ev in closing_by_year_sign_bucket.items():
            if matched_control_by_cell.get(key, 0) != n_ev:
                cells_balanced = False
                break
    support_pass = bool(
        len(event_idx) >= C.D9_MIN_NONOVERLAPPING_EVENTS
        and closing_n >= C.D9_MIN_CLOSING_EVENTS
        and len(years_closing) >= C.D9_MIN_YEARS_WITH_CLOSING_EVENTS
        and matched_n >= C.D9_MIN_MATCHED_CLOSING_CONTROLS
        and years_with_both >= C.D9_MIN_YEARS_WITH_EVENT_AND_CONTROL
        and cells_balanced
    )
    if len(event_idx) < C.D9_MIN_NONOVERLAPPING_EVENTS or closing_n < C.D9_MIN_CLOSING_EVENTS:
        status = "DEFERRED_INSUFFICIENT_EVENT_SUPPORT"
    elif (
        not cells_balanced
        or matched_n < C.D9_MIN_MATCHED_CLOSING_CONTROLS
        or years_with_both < C.D9_MIN_YEARS_WITH_EVENT_AND_CONTROL
    ):
        status = "DEFERRED_INSUFFICIENT_CONTROL_SUPPORT"
    else:
        status = "OUTCOME_BLIND_IMPLEMENTATION_READY"
    out: dict[str, Any] = {
        "ALIGNED_BARS": n,
        "RAW_EXTREME_BAR_N": int(np.sum(is_extreme)),
        "RETAINED_EVENT_N": len(event_idx),
        "REFRACTORY_DROPPED_EXTREME_N": len(refractory_dropped_idx),
        "EVENT_N": len(event_idx),
        "CLOSING_EVENT_N": closing_n,
        "RAW_ELIGIBLE_CLOSING_CONTROL_N": raw_eligible_n,
        "MATCHED_CLOSING_CONTROL_N": matched_n,
        "MATCHED_CONTROL_N": matched_n,
        "CONTROL_N": matched_n,
        "ALL_MATCHED_CELLS_BALANCED": cells_balanced,
        "EVENT_BY_YEAR": event_by_year,
        "CLOSING_BY_YEAR": closing_by_year,
        "EVENT_BY_SIGN": event_by_sign,
        "EVENT_BY_YEAR_SIGN_BUCKET": event_by_year_sign_bucket,
        "CLOSING_BY_YEAR_SIGN_BUCKET": closing_by_year_sign_bucket,
        "RAW_CONTROL_BY_YEAR_SIGN_BUCKET": {k: len(v) for k, v in raw_control_ids_by_cell.items()},
        "MATCHED_CONTROL_BY_YEAR_SIGN_BUCKET": matched_control_by_cell,
        "CONTROL_BY_YEAR_SIGN_BUCKET": matched_control_by_cell,
        "YEARS_WITH_CLOSING_EVENTS": years_closing,
        "YEARS_WITH_EVENT_AND_CONTROL": years_with_both,
        "SUPPORT_PASS": support_pass,
        "STATUS": status,
        "PRIMARY_LOCATION_STATISTIC": C.D9_PRIMARY_LOCATION_STATISTIC,
        "CONTROL_SAMPLE_SEED": C.D9_CONTROL_SAMPLE_SEED,
        "CONTROL_PERM_SEED": C.D9_CONTROL_PERM_SEED,
        "MATCH_RULE": "1:1 YEAR x SIGN_D x RV_BUCKET without replacement; non-extreme only",
        "SHARE_VALUES_EMITTED": False,
    }
    if include_indices:
        out["RETAINED_EVENT_IDX"] = event_idx
        out["REFRACTORY_DROPPED_EXTREME_IDX"] = refractory_dropped_idx
        out["CLOSING_EVENT_IDX"] = closing_event_idx
        out["RAW_CONTROL_IDX"] = raw_control_idx
        out["MATCHED_CONTROL_IDX"] = matched_idx
        out["IS_EXTREME_IDX"] = [i for i in range(n) if is_extreme[i]]
        out["CLOSING_EVENT_IDS_BY_CELL"] = closing_event_ids_by_cell
        out["MATCHED_CONTROL_IDS_BY_CELL"] = matched_ids_by_cell
        out["RAW_CONTROL_IDS_BY_CELL"] = raw_control_ids_by_cell
    return out


def load_d9_inputs(*, repo: Path | None = None) -> tuple[dict[int, Any], dict[int, float], dict[str, Any]]:
    import json

    base = repo or C.repo_root()
    log = sprint01.OpenedFileLog()
    hashes_path = base / C.M06_HASHES_REL
    payload = json.loads(hashes_path.read_text(encoding="utf-8"))
    if payload.get("snapshot_id") != C.M06_SNAPSHOT_ID:
        raise C.SnapshotIdentityError(f"M06_SNAPSHOT_MISMATCH:{payload.get('snapshot_id')}")
    ledger_path = base / C.M06_LEDGER_REL
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    perp, spot, snapshot = sprint01.load_m06_cross_venue(log, repo=base)
    zip_root = base / "docs/research_data/MARKET_06_OKX_BINANCE_FEASIBILITY_V0/durable_raw/binance"
    for row in ledger:
        period = row["period"]
        expected = row["expected_sha256"]
        path = zip_root / f"BTCUSDT-5m-{period}.zip"
        C.assert_openable(path)
        digest = C.sha256_file(path)
        if digest != expected:
            raise C.SnapshotIdentityError(f"M06_ZIP_MISMATCH:{period}")
    return perp, spot, {
        "SNAPSHOT_ID": snapshot,
        "LEDGER_N": len(ledger),
        "FILES_OPENED": log.files,
        "IDENTITY_OK": True,
    }
