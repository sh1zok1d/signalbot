"""Outcome-blind support and information forecast.

Counts complete UTC midnight formations, relative width, RV_FORMATION close-span
presence, and next-hour close-span presence. It does not compute a future
return, a future realized volatility, or any association with a future path.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from statistics import NormalDist

from scripts.research.formation_width_regime_v1 import amendment_a1 as A1
from scripts.research.frozen_hour_equal_width_v1 import data as spot_data
from scripts.research.opening_range_object_v1 import census as parent_census

from . import constants as K

ROOT = Path(__file__).resolve().parents[3]
PKG = Path(__file__).resolve().parent
DESIGN_PATH = ROOT / "docs" / "research" / "FORMATION_WIDTH_ACTIVITY_CONFIRMATION_V1_DESIGN.md"
OUT_JSON = ROOT / "docs" / "research" / "FORMATION_WIDTH_ACTIVITY_CONFIRMATION_V1_SUPPORT.json"
OUT_MD = ROOT / "docs" / "research" / "FORMATION_WIDTH_ACTIVITY_CONFIRMATION_V1_SUPPORT.md"
UTC = dt.timezone.utc
Z_LO = 1.6448536269514722
Z_POWER = 0.8416212335729143
NORMAL = NormalDist()

FORBIDDEN_KEY_PARTS = (
    "spearman",
    "partial",
    "rho",
    "activity",
    "displacement",
    "future_rv",
    "log_return",
    "y_future",
    "outcome_association",
)


def code_digest() -> str:
    digest = hashlib.sha256()
    for path in sorted(PKG.glob("*.py")):
        rel = str(path.relative_to(ROOT))
        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        digest.update(rel.encode())
        digest.update(file_hash.encode())
    return digest.hexdigest()


def _ms(day: str) -> int:
    stamp = dt.datetime.fromisoformat(day).replace(tzinfo=UTC)
    return int(stamp.timestamp() * 1000)


SPLIT_MS = _ms(K.STABILITY_SPLIT)


def span_complete(close: np.ndarray, start: int, count: int) -> bool:
    if start < 0 or start + count > int(close.shape[0]):
        return False
    window = close[start:start + count]
    return bool(window.shape[0] == count and np.all(np.isfinite(window)) and np.all(window > 0.0))


def state_rank_correlation(left: list[float], right: list[float]) -> float:
    """Average-rank correlation of two state series. Not a future association."""
    if len(left) < 3 or len(left) != len(right):
        raise RuntimeError("state dependence sample is too small")
    rx = A1.average_ranks(np.asarray(left, dtype=np.float64))
    ry = A1.average_ranks(np.asarray(right, dtype=np.float64))
    rx = rx - float(rx.mean())
    ry = ry - float(ry.mean())
    denom = math.sqrt(float(np.dot(rx, rx) * np.dot(ry, ry)))
    if denom == 0.0:
        raise RuntimeError("state dependence is degenerate")
    return float(np.dot(rx, ry) / denom)


def ar1_average_pairwise(phi: float, block: int) -> float:
    """Mean pairwise correlation inside one block under AR(1)."""
    if block < 2 or phi <= 0.0:
        return 0.0
    rate = min(float(phi), K.PHI_CAP)
    acc = 0.0
    for lag in range(1, block):
        acc += (block - lag) * (rate ** lag)
    return (2.0 / (block * (block - 1))) * acc


def effective_n(week_sizes: list[int], phi: float) -> float:
    """Kish effective size. phi is state dependence, clipped, never an outcome."""
    sizes = [int(size) for size in week_sizes]
    total = sum(sizes)
    if total <= 0:
        raise RuntimeError("week sizes are empty")
    denom = 0.0
    for size in sizes:
        icc = ar1_average_pairwise(phi, size)
        denom += size * (1.0 + (size - 1) * icc)
    return float(total * total) / float(denom)


def fisher_se(n_eff: float) -> float:
    if not math.isfinite(n_eff) or n_eff <= 3.0:
        return float("inf")
    return 1.0 / math.sqrt(n_eff - 3.0)


def power_lower_bound_excludes_zero(se: float, planted: float = K.PRACTICAL_RHO) -> float:
    """Normal power of the one-sided 95% lower bound at a planted association."""
    if not math.isfinite(se) or se <= 0.0:
        return 0.0
    z = (Z_LO * se - planted) / se
    return float(1.0 - NORMAL.cdf(z))


def probability_point_and_bound(se: float, planted: float = K.PRACTICAL_RHO) -> float:
    """P(point >= bar and lower bound > 0) when the planted value equals the bar.

    When the truth sits on the bar, the point-estimate half of this event has
    probability one half. The bound can only make it smaller.
    """
    if not math.isfinite(se) or se <= 0.0:
        return 0.0
    threshold = max(planted, Z_LO * se)
    z = (threshold - planted) / se
    return float(1.0 - NORMAL.cdf(z))


def information_forecast(week_sizes: list[int], phi: float) -> dict:
    n_eff = effective_n(week_sizes, max(0.0, min(float(phi), K.PHI_CAP)))
    se = fisher_se(n_eff)
    n = int(sum(week_sizes))
    n_weeks = int(len(week_sizes))
    independent = fisher_se(float(n))
    week_bound = fisher_se(float(n_weeks))
    mde = (Z_LO + Z_POWER) * se if math.isfinite(se) else float("inf")
    return {
        "dependence_model": "AR1_WITHIN_ISO_WEEK_USING_WIDTH_LAG_THEN_KISH",
        "phi_cap": K.PHI_CAP,
        "phi_used": max(0.0, min(float(phi), K.PHI_CAP)),
        "effective_n": n_eff,
        "fisher_se": se,
        "independent_day_se": independent,
        "one_draw_per_week_se": week_bound,
        "minimum_detectable_association_80": mde,
        "power_lower_bound_excludes_zero_at_practical_bar": power_lower_bound_excludes_zero(se),
        "probability_point_clears_bar_and_bound_excludes_zero": probability_point_and_bound(se),
        "decision_uses_design_effect_not_the_week_total_bound": True,
        "practical_bar": K.PRACTICAL_RHO,
        "power_floor": K.POWER_FLOOR,
    }


def collect(high, low, close, t0: int) -> dict:
    n_days = int(high.shape[0]) // K.BARS_PER_DAY
    if int(high.shape[0]) != n_days * K.BARS_PER_DAY:
        raise RuntimeError("panel length is not a whole number of UTC dates")
    if t0 != _ms(K.EVENT_START):
        raise RuntimeError("panel does not start at the frozen confirmation open")
    rows = []
    counts = {
        "calendar_days": 0,
        "formation_incomplete": 0,
        "usable_formation": 0,
        "rv_formation_span_incomplete": 0,
        "next_hour_path_incomplete": 0,
        "analysis_sample": 0,
    }
    by_month: dict[str, int] = {}
    by_year = {"2017": 0, "2018": 0, "2019": 0}
    for day in range(n_days):
        day_ms = t0 + day * K.DAY_MS
        if day_ms < _ms(K.EVENT_START) or day_ms >= _ms(K.SURFACE_END):
            continue
        counts["calendar_days"] += 1
        form = day * K.BARS_PER_DAY
        geo = parent_census._geometry(high, low, close, form)
        if geo is None or not geo["usable"]:
            counts["formation_incomplete"] += 1
            continue
        counts["usable_formation"] += 1
        relative = float(geo["high"] - geo["low"]) / float(geo["p0"])
        rv_start, rv_count = A1.formation_close_span(form)
        if rv_count != K.FORMATION_BARS + 1:
            raise RuntimeError("RV_FORMATION span drifted")
        rv_ok = span_complete(close, rv_start, rv_count)
        next_ok = span_complete(close, form + K.FORMATION_BARS - 1, K.HORIZON_BARS + 1)
        if not rv_ok:
            counts["rv_formation_span_incomplete"] += 1
        if not next_ok:
            counts["next_hour_path_incomplete"] += 1
        stamp = dt.datetime.fromtimestamp(day_ms / 1000.0, tz=UTC)
        iso = stamp.isocalendar()
        in_sample = bool(rv_ok and next_ok)
        if in_sample:
            counts["analysis_sample"] += 1
            month_key = stamp.strftime("%Y-%m")
            by_month[month_key] = by_month.get(month_key, 0) + 1
            year_key = str(stamp.year)
            if year_key not in by_year:
                raise RuntimeError(f"analysis year outside 2017-2019: {stamp.year}")
            by_year[year_key] += 1
        rows.append({
            "day_ms": day_ms,
            "iso_year": int(iso.year),
            "iso_week": int(iso.week),
            "relative_width": relative,
            "in_sample": in_sample,
            "first_half": day_ms < SPLIT_MS,
        })
    return {"counts": counts, "by_month": by_month, "by_year": by_year, "rows": rows}


def _quantiles(values: list[float]) -> dict:
    column = np.asarray(values, dtype=np.float64)
    return {
        f"p{int(q * 100)}": float(np.quantile(column, q, method="linear"))
        for q in (0.1, 0.25, 0.5, 0.75, 0.9)
    }


def summarize(collected: dict) -> dict:
    rows = collected["rows"]
    usable = [row["relative_width"] for row in rows]
    if len(usable) < 3:
        raise RuntimeError("usable formation count is too small")
    quant = _quantiles(usable)
    ratio = quant["p90"] / quant["p10"] if quant["p10"] > 0.0 else float("inf")
    sample = [row for row in rows if row["in_sample"]]
    weeks: dict[tuple[int, int], int] = {}
    for row in sample:
        key = (row["iso_year"], row["iso_week"])
        weeks[key] = weeks.get(key, 0) + 1
    week_sizes = list(weeks.values())
    lagged_x: list[float] = []
    lagged_y: list[float] = []
    by_day = {row["day_ms"]: row for row in sample}
    for row in sample:
        prev = by_day.get(row["day_ms"] - K.DAY_MS)
        if prev is None:
            continue
        lagged_x.append(prev["relative_width"])
        lagged_y.append(row["relative_width"])
    lag_n = len(lagged_x)
    lag = state_rank_correlation(lagged_x, lagged_y) if lag_n >= 3 else float("nan")
    phi = 0.0 if not math.isfinite(lag) or lag < 0.0 else min(lag, K.PHI_CAP)
    forecast = information_forecast(week_sizes, phi) if week_sizes else {
        "effective_n": 0.0,
        "fisher_se": float("inf"),
        "power_lower_bound_excludes_zero_at_practical_bar": 0.0,
        "minimum_detectable_association_80": float("inf"),
    }
    first = sum(1 for row in sample if row["first_half"])
    second = sum(1 for row in sample if not row["first_half"])
    counts = collected["counts"]
    power = float(forecast["power_lower_bound_excludes_zero_at_practical_bar"])
    floor_ok = (
        counts["analysis_sample"] >= K.MIN_ANALYSIS_N
        and len(weeks) >= K.MIN_ISO_WEEKS
        and first >= K.MIN_HALF_N
        and second >= K.MIN_HALF_N
        and lag_n >= K.MIN_DEPENDENCE_PAIRS
        and math.isfinite(lag)
        and ratio >= K.DEGENERATE_P90_P10
        and math.isfinite(float(forecast["fisher_se"]))
        and power >= K.POWER_FLOOR
    )
    status = K.ADEQUATE if floor_ok else K.WEAK
    return {
        "unit": K.UNIT,
        "mode": K.MODE,
        "outcome_read": False,
        "claim_selected_pre_outcome": True,
        "future_association_read": False,
        "information_authorizes_outcome": False,
        "exposure_class": K.EXPOSURE_CLASS,
        "surface": K.SURFACE_ID,
        "event_start": K.EVENT_START,
        "surface_end_exclusive": K.SURFACE_END,
        "anchor": K.ANCHOR,
        "state": K.STATE,
        "endpoint_name": K.ENDPOINT,
        "incremental_covariate": K.INCREMENTAL_COVARIATE,
        "counts": counts,
        "by_year_analysis": collected["by_year"],
        "by_month_analysis": collected["by_month"],
        "analysis_iso_weeks": len(weeks),
        "mean_analysis_days_per_week": (float(sum(week_sizes) / len(week_sizes)) if week_sizes else 0.0),
        "stability_split": K.STABILITY_SPLIT,
        "first_half_n": first,
        "second_half_n": second,
        "relative_width": {
            "n_usable": len(usable),
            "mean": float(sum(usable) / len(usable)),
            "quantiles": quant,
            "p90_over_p10": ratio,
        },
        "lag1_relative_width_rank_correlation": lag,
        "lag1_n": lag_n,
        "degenerate_width": ratio < K.DEGENERATE_P90_P10,
        "information_forecast": forecast,
        "information_status": status,
        "pre_outcome_route": status,
        "awaiting_separate_owner_go": bool(floor_ok),
    }


def assert_support_only(payload: dict) -> None:
    bad: list[str] = []

    def walk(obj, prefix: str) -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                name = str(key).lower()
                if any(part in name for part in FORBIDDEN_KEY_PARTS):
                    bad.append(prefix + str(key))
                walk(value, prefix + str(key) + ".")
        elif isinstance(obj, list):
            for i, value in enumerate(obj):
                walk(value, prefix + f"[{i}].")

    walk(payload, "")
    if bad:
        raise RuntimeError("support payload contains a forbidden key: " + ", ".join(bad))
    if payload.get("outcome_read") is not False:
        raise RuntimeError("support payload marks an outcome read")
    if payload.get("future_association_read") is not False:
        raise RuntimeError("support payload marks a future association")


def render_md(payload: dict) -> str:
    counts = payload["counts"]
    width = payload["relative_width"]
    forecast = payload["information_forecast"]
    months = payload["by_month_analysis"]
    month_line = ", ".join(f"{key} {months[key]}" for key in sorted(months))
    return "\n".join([
        f"# {K.UNIT} — outcome-blind support",
        "",
        f"`outcome_read = false`",
        f"`claim_selected_pre_outcome = true`",
        f"`information_status = {payload['information_status']}`",
        f"`pre_outcome_route = {payload['pre_outcome_route']}`",
        "",
        "This file counts path presence and the width state. It does not contain the next-hour endpoint or an association with that endpoint.",
        "",
        f"Surface `{payload['surface']}` `{payload['event_start']}` to `{payload['surface_end_exclusive']}` exclusive.",
        f"Exposure `{payload['exposure_class']}`.",
        "",
        "## Counts",
        "",
        f"- calendar days: {counts['calendar_days']}",
        f"- usable formations: {counts['usable_formation']}",
        f"- formation incomplete: {counts['formation_incomplete']}",
        f"- RV_FORMATION span incomplete among usable: {counts['rv_formation_span_incomplete']}",
        f"- next-hour path incomplete among usable: {counts['next_hour_path_incomplete']}",
        f"- analysis N: {counts['analysis_sample']}",
        f"- ISO weeks: {payload['analysis_iso_weeks']}",
        f"- mean analysis days per week: {payload['mean_analysis_days_per_week']:.4f}",
        f"- first half before {payload['stability_split']}: {payload['first_half_n']}",
        f"- second half: {payload['second_half_n']}",
        f"- years: {payload['by_year_analysis']}",
        f"- months: {month_line}",
        "",
        "## Width state",
        "",
        f"- usable n: {width['n_usable']}",
        f"- mean: {width['mean']:.6f}",
        f"- quantiles: {width['quantiles']}",
        f"- p90/p10: {width['p90_over_p10']:.6f}",
        f"- lag-1 rank correlation of relative width: {payload['lag1_relative_width_rank_correlation']}",
        f"- lag pairs: {payload['lag1_n']}",
        "",
        "## Information forecast",
        "",
        "The forecast uses the width lag as an AR(1) stand-in for within-week dependence of the later association. It does not use the next-hour endpoint.",
        "",
        f"- effective N: {forecast['effective_n']:.4f}",
        f"- Fisher SE: {forecast['fisher_se']}",
        f"- independent-day SE: {forecast['independent_day_se']}",
        f"- one-draw-per-week SE: {forecast['one_draw_per_week_se']}",
        f"- 80% MDE: {forecast['minimum_detectable_association_80']}",
        f"- power that the lower bound excludes 0 at the practical bar: {forecast['power_lower_bound_excludes_zero_at_practical_bar']}",
        f"- probability the point clears the bar and the bound excludes 0, when the planted value equals the bar: {forecast['probability_point_clears_bar_and_bound_excludes_zero']}",
        "",
        f"Separate owner go to read the endpoint: {payload['awaiting_separate_owner_go']}.",
        "The support census does not authorize that read.",
        "",
    ])


def main() -> dict:
    if OUT_JSON.exists() or OUT_MD.exists():
        raise SystemExit(K.REFUSAL_RERUN)
    if not DESIGN_PATH.is_file():
        raise RuntimeError("confirmation design is missing")
    panel, provenance = spot_data.load_panel()
    if provenance["dataset_id"] != K.SURFACE_ID:
        raise RuntimeError("panel is not the frozen spot surface")
    if panel.months[0] != K.FIRST_MONTH or panel.months[-1] != K.LAST_MONTH:
        raise RuntimeError("panel months are not 2017-09..2019-12")
    if any(month >= "2020-01" or month[:4] in {"2025", "2026"} for month in panel.months):
        raise RuntimeError("panel includes a forbidden month")
    collected = collect(panel.high, panel.low, panel.close, panel.t0)
    payload = summarize(collected)
    payload["read_at"] = dt.datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload["code_digest"] = code_digest()
    payload["design_sha256"] = hashlib.sha256(DESIGN_PATH.read_bytes()).hexdigest()
    payload["discovery_result_sha256"] = K.DISCOVERY_RESULT_SHA256
    payload["grid"] = {
        "present_bars": provenance["present_bars"],
        "missing_bars": provenance["missing_bars"],
        "grid_bars": provenance["grid_bars"],
        "off_grid_rows_not_placed": provenance["off_grid_rows_not_placed"],
        "object_list_sha256": provenance["object_list_sha256"],
        "months": provenance["months"],
    }
    assert_support_only(payload)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    OUT_JSON.write_text(text, encoding="utf-8")
    OUT_MD.write_text(render_md(payload), encoding="utf-8")
    return payload


if __name__ == "__main__":
    main()
