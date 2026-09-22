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

    if not summary.get("SUPPORT_PASS"):
        return "INCONCLUSIVE_DISCOVERY"
    if not summary.get("IDENTITY_OK", True):
        return "INVALID_DISCOVERY"
    promising = bool(
        summary.get("STATISTICAL_GATE")
        and summary.get("PRACTICAL_GATE")
        and summary.get("TEMPORAL_GATE")
    )
    if promising:
        return "PROMISING_PROTOTYPE"
    return "NO_USEFUL_STRUCTURE"


def d9_statistical_gate(
    event_shares: Sequence[float],
    *,
    seed: int = C.D9_SEED,
    n: int = C.D9_N_RANDOMIZATIONS,
) -> dict[str, Any]:
    observed = np.asarray(list(event_shares), dtype=np.float64)
    if observed.size == 0:
        raise C.Sprint03IntegrityError("D9_EMPTY_SHARE_SAMPLE")
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
        "MC_P": p_value,
        "STATISTICAL_GATE": bool(p_value < C.D9_MC_ALPHA),
        "SEED": seed,
        "N_RANDOMIZATIONS": n,
    }


def evaluate_d9_scientific(
    event_shares: Sequence[float],
    control_shares: Sequence[float],
    yearly_event_shares: Mapping[str, Sequence[float]],
    *,
    support: Mapping[str, Any],
) -> dict[str, Any]:
    """Pure scientific evaluator on supplied arrays. No market I/O."""

    stats = d9_statistical_gate(event_shares)
    event_med = stats["MEDIAN_SHARE"]
    control_med = C.median(control_shares) if list(control_shares) else float("nan")
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
) -> dict[str, Any]:
    """Structural support only. Does not return SHARE values."""

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
    event_idx: list[int] = []
    last_kept = -10**9
    valid_abs: list[float] = []
    valid_rv: list[float] = []
    valid_abs_pos = np.full(n, -1, dtype=np.int32)
    valid_rv_pos = np.full(n, -1, dtype=np.int32)
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
        if i - last_kept < C.D9_MIN_EVENT_GAP_BARS:
            continue
        if not math.isfinite(rv[i]) or valid_rv_pos[i] < C.D9_TRAILING_WINDOW:
            continue
        trailing_abs = valid_abs[valid_abs_pos[i] - C.D9_TRAILING_WINDOW : valid_abs_pos[i]]
        p90 = C.percentile(trailing_abs, C.D9_PCTL)
        if not (abs_d[i] > p90):
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
    control_by_year_sign_bucket: dict[str, int] = {}
    event_set = set(event_idx)
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

    raw_control_n = 0
    years_with_both = 0
    closing_cells = set(closing_by_year_sign_bucket)
    for i in range(n):
        if i in event_set or not valid_d[i]:
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
        control_by_year_sign_bucket[key] = control_by_year_sign_bucket.get(key, 0) + 1
        raw_control_n += 1
    control_n = sum(v for k, v in control_by_year_sign_bucket.items() if k in closing_cells)

    years_closing = [y for y, n_y in closing_by_year.items() if n_y > 0]
    for year in ("2022", "2023", "2024"):
        has_event = closing_by_year.get(year, 0) > 0
        has_control = any(
            k.startswith(f"{year}:") and v > 0
            for k, v in control_by_year_sign_bucket.items()
        )
        if has_event and has_control:
            years_with_both += 1
    support_pass = bool(
        len(event_idx) >= C.D9_MIN_NONOVERLAPPING_EVENTS
        and closing_n >= C.D9_MIN_CLOSING_EVENTS
        and len(years_closing) >= C.D9_MIN_YEARS_WITH_CLOSING_EVENTS
        and control_n >= C.D9_MIN_MATCHED_CLOSING_CONTROLS
        and years_with_both >= C.D9_MIN_YEARS_WITH_EVENT_AND_CONTROL
    )
    if len(event_idx) < C.D9_MIN_NONOVERLAPPING_EVENTS or closing_n < C.D9_MIN_CLOSING_EVENTS:
        status = "DEFERRED_INSUFFICIENT_EVENT_SUPPORT"
    elif control_n < C.D9_MIN_MATCHED_CLOSING_CONTROLS or years_with_both < C.D9_MIN_YEARS_WITH_EVENT_AND_CONTROL:
        status = "DEFERRED_INSUFFICIENT_CONTROL_SUPPORT"
    else:
        status = "OUTCOME_BLIND_IMPLEMENTATION_READY"
    return {
        "ALIGNED_BARS": n,
        "EVENT_N": len(event_idx),
        "CLOSING_EVENT_N": closing_n,
        "CONTROL_N": control_n,
        "RAW_CLOSING_NON_EVENT_N": raw_control_n,
        "EVENT_BY_YEAR": event_by_year,
        "CLOSING_BY_YEAR": closing_by_year,
        "EVENT_BY_SIGN": event_by_sign,
        "EVENT_BY_YEAR_SIGN_BUCKET": event_by_year_sign_bucket,
        "CLOSING_BY_YEAR_SIGN_BUCKET": closing_by_year_sign_bucket,
        "CONTROL_BY_YEAR_SIGN_BUCKET": control_by_year_sign_bucket,
        "YEARS_WITH_CLOSING_EVENTS": years_closing,
        "YEARS_WITH_EVENT_AND_CONTROL": years_with_both,
        "SUPPORT_PASS": support_pass,
        "STATUS": status,
        "PRIMARY_LOCATION_STATISTIC": C.D9_PRIMARY_LOCATION_STATISTIC,
        "SHARE_VALUES_EMITTED": False,
    }


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
