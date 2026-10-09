"""Pre-outcome amendment A1. Incremental covariate only.

The outcome entry point is evaluate.py. It refuses before an owner go.
This module can count whether the formation-hour close path is complete.
It does not compute a future RV, a future displacement, or any association with Y.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from scripts.research.opening_range_object_v1 import census as parent_census
from scripts.research.opening_range_object_v1 import constants as PARENT

from . import census as census_mod
from . import constants as K

ROOT = Path(__file__).resolve().parents[3]
OUT_JSON = ROOT / "docs" / "research" / "FORMATION_WIDTH_REGIME_V1_AMENDMENT_A1_SUPPORT.json"
OUT_MD = ROOT / "docs" / "research" / "FORMATION_WIDTH_REGIME_V1_AMENDMENT_A1_SUPPORT.md"
UTC = dt.timezone.utc

INCREMENTAL_COVARIATE = "RV_FORMATION"
RV_PREV_ROLE = "DESCRIPTIVE_SECONDARY_NOT_A_ROUTE_INPUT"
DRAW_ORDER = (
    "FOUNDATION_ACTIVITY",
    "FOUNDATION_DISPLACEMENT",
    "INCREMENTAL_ACTIVITY_RV_FORMATION",
    "INCREMENTAL_DISPLACEMENT_RV_FORMATION",
)
ENDPOINTS = ("ACTIVITY", "DISPLACEMENT")
ROUTE_INFORMATION_LIMITED = "INFORMATION_LIMITED"
ROUTE_NO_DETECTABLE = "FORMATION_WIDTH_NO_DETECTABLE_FUTURE_STRUCTURE"
ROUTE_UNSTABLE = "TEMPORALLY_UNSTABLE_WIDTH_RELATION"
ROUTE_REDUNDANT = "WIDTH_IS_REDUNDANT_WITH_CONTEMPORANEOUS_VOLATILITY"
ROUTE_PRESENT = "FORMATION_WIDTH_REGIME_STRUCTURE_PRESENT"
ROUTE_NOT_SPECIFIC = "CURRENT_STATE_SPECIFICITY_NOT_SATISFIED"
ORIGINAL_ANALYSIS_N = 1820
ORIGINAL_ISO_WEEKS = 262
FORBIDDEN_KEY_PARTS = (
    "activity",
    "displacement",
    "spearman",
    "partial",
    "rho",
    "future_rv",
    "y_future",
    "outcome_association",
    "log_return",
)


def formation_return_pairs(form: int) -> tuple[tuple[int, int], ...]:
    """Twelve returns ending on the formation bars [form, form+12).

    Pair k is (close index of the previous bar, close index of the end bar).
    The last end bar is form+11, whose close is P0 at T.
    """
    return tuple((form - 1 + k, form + k) for k in range(K.FORMATION_BARS))


def future_return_pairs(form: int) -> tuple[tuple[int, int], ...]:
    """Twelve returns ending on bars [form+12, form+24).

    The first pair starts at P0 = close[form+11] and ends on the first bar after T.
    """
    start = form + K.FORMATION_BARS
    return tuple((start - 1 + k, start + k) for k in range(K.HORIZON_BARS))


def prev_hour_return_pairs(form: int) -> tuple[tuple[int, int], ...]:
    """Twelve returns of [23:00, 00:00). The last end bar is form-1, close at 00:00."""
    start = form - K.FORMATION_BARS
    return tuple((start - 1 + k, start + k) for k in range(K.FORMATION_BARS))


def formation_close_span(form: int) -> tuple[int, int]:
    """Start index and count of the 13 closes used by RV_FORMATION."""
    return form - 1, K.FORMATION_BARS + 1


def returns_are_disjoint(form: int) -> bool:
    formation = set(formation_return_pairs(form))
    future = set(future_return_pairs(form))
    prev = set(prev_hour_return_pairs(form))
    return not (formation & future or formation & prev or future & prev)


def log_returns(close: np.ndarray, pairs: tuple[tuple[int, int], ...]) -> np.ndarray:
    out = np.empty(len(pairs), dtype=np.float64)
    for i, (left, right) in enumerate(pairs):
        out[i] = math.log(float(close[right]) / float(close[left]))
    return out


def realized_variation(returns: np.ndarray) -> float:
    values = np.asarray(returns, dtype=np.float64)
    return float(math.sqrt(float(np.dot(values, values))))


def average_ranks(values: np.ndarray) -> np.ndarray:
    x = np.asarray(values, dtype=np.float64)
    n = int(x.shape[0])
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(n, dtype=np.float64)
    sorted_x = x[order]
    i = 0
    while i < n:
        j = i + 1
        while j < n and sorted_x[j] == sorted_x[i]:
            j += 1
        ranks[order[i:j]] = 0.5 * ((i + 1) + j)
        i = j
    return ranks


def _ols_residual(y: np.ndarray, x: np.ndarray) -> np.ndarray | None:
    design = np.column_stack([np.ones(len(y)), x])
    beta, _, _, _ = np.linalg.lstsq(design, y, rcond=None)
    resid = y - design @ beta
    ss_tot = float(np.dot(y - y.mean(), y - y.mean()))
    ss_res = float(np.dot(resid, resid))
    if ss_tot == 0.0 or ss_res <= 1e-12 * ss_tot:
        return None
    return resid


def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    left = a - a.mean()
    right = b - b.mean()
    denom = math.sqrt(float(np.dot(left, left) * np.dot(right, right)))
    if denom == 0.0:
        raise RuntimeError("partial correlation is degenerate")
    return float(np.dot(left, right) / denom)


def partial_spearman(v: np.ndarray, y: np.ndarray, z: np.ndarray) -> dict:
    """Pearson correlation of average-rank residuals. One covariate, OLS with intercept."""
    v = np.asarray(v, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    z = np.asarray(z, dtype=np.float64)
    if not (len(v) == len(y) == len(z)) or len(v) < 3:
        raise RuntimeError("partial Spearman needs three aligned series of length at least 3")
    rv = average_ranks(v)
    ry = average_ranks(y)
    rz = average_ranks(z)
    left = _ols_residual(rv, rz)
    right = _ols_residual(ry, rz)
    if left is None or right is None:
        return {"rho": None, "degenerate": True, "covariate": INCREMENTAL_COVARIATE}
    return {"rho": _pearson(left, right), "degenerate": False, "covariate": INCREMENTAL_COVARIATE}


def cell_clears(abs_estimate: float, family_interval_excludes_zero: bool) -> bool:
    return abs_estimate >= K.PRACTICAL_ABS_RHO and family_interval_excludes_zero


def assign_route(endpoints: dict[str, dict], *, information_limited: bool) -> dict:
    """Route from foundation cells and RV_FORMATION incremental cells only."""
    if set(endpoints) != set(ENDPOINTS):
        raise RuntimeError("inferential endpoints must be ACTIVITY and DISPLACEMENT")
    for payload in endpoints.values():
        if "rv_prev_clears" in payload or "incremental_prev_clears" in payload:
            raise RuntimeError("RV_PREV is not an inferential input")
    if information_limited:
        return _route(ROUTE_INFORMATION_LIMITED, interpretable=None)
    rows = []
    for name in ENDPOINTS:
        row = endpoints[name]
        for key in (
            "foundation_clears",
            "year_unstable",
            "incremental_formation_clears",
            "foundation_abs",
            "lag_placebo_abs",
        ):
            if key not in row:
                raise RuntimeError(f"{name} is missing {key}")
        rows.append(row)
    specific = all(row["lag_placebo_abs"] < row["foundation_abs"] for row in rows)
    clearing = [row for row in rows if row["foundation_clears"]]
    if not clearing:
        return _route(ROUTE_NO_DETECTABLE, interpretable=specific)
    if all(row["year_unstable"] for row in clearing):
        return _route(ROUTE_UNSTABLE, interpretable=specific)
    stable = [row for row in clearing if not row["year_unstable"]]
    if all(not row["incremental_formation_clears"] for row in stable):
        return _route(ROUTE_REDUNDANT, interpretable=specific)
    if specific:
        return _route(ROUTE_PRESENT, interpretable=True)
    return _route(ROUTE_NOT_SPECIFIC, interpretable=False)


def _route(name: str, *, interpretable: bool | None) -> dict:
    return {
        "route": name,
        "interpretable_as_current_state": interpretable,
        "incremental_covariate": INCREMENTAL_COVARIATE,
        "rv_prev_role": RV_PREV_ROLE,
    }


def availability(high, low, close, t0: int) -> dict:
    """Path presence only. No return, no RV, no association."""
    base = census_mod.collect(high, low, close, t0)
    n = int(high.shape[0])
    n_days = n // K.BARS_PER_DAY
    counts = {
        "calendar_days": 0,
        "usable_formation": 0,
        "analysis_sample": 0,
        "rv_formation_complete": 0,
        "analysis_and_rv_formation": 0,
        "analysis_missing_rv_formation": 0,
        "rv_formation_outside_analysis": 0,
    }
    weeks = set()
    for day in range(n_days):
        day_ms = t0 + day * PARENT.DAY_MS
        if day_ms < parent_census.EVENT_START_MS or day_ms >= parent_census.SURFACE_END_MS:
            continue
        counts["calendar_days"] += 1
        form = day * K.BARS_PER_DAY
        geo = parent_census._geometry(high, low, close, form)
        if geo is None or not geo["usable"]:
            continue
        counts["usable_formation"] += 1
        past_ok = census_mod._path_complete(close, form - K.FORMATION_BARS - 1, K.FORMATION_BARS + 1)
        future_ok = census_mod._path_complete(close, form + K.FORMATION_BARS - 1, K.HORIZON_BARS + 1)
        span_start, span_count = formation_close_span(form)
        rv_ok = census_mod._path_complete(close, span_start, span_count)
        in_sample = past_ok and future_ok
        if rv_ok:
            counts["rv_formation_complete"] += 1
        if in_sample:
            counts["analysis_sample"] += 1
            if rv_ok:
                counts["analysis_and_rv_formation"] += 1
                stamp = dt.datetime.fromtimestamp(day_ms / 1000.0, tz=UTC)
                iso = stamp.isocalendar()
                weeks.add((int(iso.year), int(iso.week)))
            else:
                counts["analysis_missing_rv_formation"] += 1
        elif rv_ok:
            counts["rv_formation_outside_analysis"] += 1
    if counts["analysis_sample"] != base["counts"]["analysis_sample"]:
        raise RuntimeError("A1 availability drifted from the frozen analysis sample")
    if counts["calendar_days"] != base["counts"]["calendar_days"]:
        raise RuntimeError("A1 availability drifted from the frozen calendar")
    n_a1 = counts["analysis_and_rv_formation"]
    return {
        "unit": K.UNIT,
        "amendment": "A1",
        "outcome_read": False,
        "future_association_read": False,
        "information_authorizes_outcome": False,
        "incremental_covariate": INCREMENTAL_COVARIATE,
        "rv_prev_role": RV_PREV_ROLE,
        "counts": counts,
        "a1_analysis_sample": n_a1,
        "a1_iso_weeks": len(weeks),
        "original_analysis_sample": ORIGINAL_ANALYSIS_N,
        "original_iso_weeks": ORIGINAL_ISO_WEEKS,
        "sample_n_changed": n_a1 != ORIGINAL_ANALYSIS_N or len(weeks) != ORIGINAL_ISO_WEEKS,
        "inclusion_rule": "original analysis sample intersect complete RV_FORMATION close span",
    }


def assert_support_only(payload: dict) -> None:
    blob = json.dumps(payload, sort_keys=True).lower()
    bad = [part for part in FORBIDDEN_KEY_PARTS if part in blob]
    if bad or payload.get("outcome_read") is not False or payload.get("future_association_read") is not False:
        raise RuntimeError(f"A1 support payload is not outcome-blind: {bad}")


def render_markdown(payload: dict) -> str:
    counts = payload["counts"]
    return "\n".join([
        "# FORMATION_WIDTH_REGIME_V1 — amendment A1 support",
        "",
        "`outcome_read = false`",
        "`future_association_read = false`",
        "",
        "Path presence of the 13 closes used by `RV_FORMATION`. No return and no association is in this file.",
        "",
        f"- Original analysis sample: {payload['original_analysis_sample']}",
        f"- A1 analysis sample: {payload['a1_analysis_sample']}",
        f"- A1 ISO weeks: {payload['a1_iso_weeks']}",
        f"- `sample_n_changed`: {str(payload['sample_n_changed']).lower()}",
        f"- RV_FORMATION complete: {counts['rv_formation_complete']}",
        f"- Analysis missing RV_FORMATION: {counts['analysis_missing_rv_formation']}",
        f"- RV_FORMATION outside the analysis sample: {counts['rv_formation_outside_analysis']}",
        "",
    ])


def write_support(payload: dict, json_path: Path = OUT_JSON, md_path: Path = OUT_MD) -> None:
    if json_path.exists() or md_path.exists():
        raise SystemExit(K.REFUSAL_RERUN)
    assert_support_only(payload)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")


def support_code_digest() -> str:
    path = Path(__file__).resolve()
    return hashlib.sha256(path.read_bytes()).hexdigest()
