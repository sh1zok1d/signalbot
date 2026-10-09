"""Outcome-blind Bybit support census and the frozen information forecast.

Counts UTC midnight formations, relative width, and whether the formation-hour
close span and the next-hour close span are present. It does not compute a
future return or any association with a future path.
"""

from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from scripts.research.formation_width_activity_confirmation_v1 import support as CONFIRM
from scripts.research.formation_width_regime_v1 import amendment_a1 as A1
from scripts.research.opening_range_object_v1 import census as parent_census

from . import constants as K

ROOT = Path(__file__).resolve().parents[3]
PKG = Path(__file__).resolve().parent
DESIGN_PATH = ROOT / "docs" / "research" / "FORMATION_WIDTH_ACTIVITY_BYBIT_FEASIBILITY_V1_DESIGN.md"
SERIES_PATH = ROOT / "docs" / "research_data" / K.DATASET_ID / K.SERIES_NAME
OUT_JSON = ROOT / "docs" / "research" / "FORMATION_WIDTH_ACTIVITY_BYBIT_FEASIBILITY_V1_SUPPORT.json"
OUT_MD = ROOT / "docs" / "research" / "FORMATION_WIDTH_ACTIVITY_BYBIT_FEASIBILITY_V1_SUPPORT.md"
OUT_MANIFEST = ROOT / "docs" / "research" / "FORMATION_WIDTH_ACTIVITY_BYBIT_FEASIBILITY_V1_MANIFEST.json"
UTC = dt.timezone.utc

FORBIDDEN_KEY_PARTS = CONFIRM.FORBIDDEN_KEY_PARTS
information_forecast = CONFIRM.information_forecast
span_complete = CONFIRM.span_complete
state_rank_correlation = CONFIRM.state_rank_correlation


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
GRID_START_MS = _ms(K.GRID_START)
EVENT_START_MS = _ms(K.EVENT_START)
SURFACE_END_MS = _ms(K.SURFACE_END)
GRID_DAYS = (SURFACE_END_MS - GRID_START_MS) // K.DAY_MS


def load_ohlc() -> tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
    """Place the pinned Bybit series on an exact 5m UTC grid. Missing stays missing."""
    if not SERIES_PATH.is_file():
        raise RuntimeError("pinned Bybit series is missing")
    blob = SERIES_PATH.read_bytes()
    digest = hashlib.sha256(blob).hexdigest()
    if digest != K.CANONICAL_SHA256:
        raise RuntimeError("Bybit canonical digest drifted")
    text = gzip.decompress(blob).decode("utf-8")
    lines = text.splitlines()
    if not lines or lines[0] != "open_ms,open,high,low,close":
        raise RuntimeError("Bybit header is not the pinned OHLC schema")
    n = int(GRID_DAYS) * K.BARS_PER_DAY
    high = np.full(n, np.nan, dtype=np.float64)
    low = np.full(n, np.nan, dtype=np.float64)
    close = np.full(n, np.nan, dtype=np.float64)
    present = 0
    first_ms = None
    last_ms = None
    previous = None
    for line in lines[1:]:
        if not line.strip():
            continue
        parts = line.split(",")
        if len(parts) != 5:
            raise RuntimeError("short Bybit row")
        open_ms = int(parts[0])
        if open_ms % K.BAR_MS != 0:
            raise RuntimeError("Bybit bar leaves the 5m UTC grid")
        if open_ms >= SURFACE_END_MS:
            raise RuntimeError("Bybit bar is at or after 2025-01-01")
        if open_ms < GRID_START_MS:
            raise RuntimeError("Bybit bar is before the frozen grid")
        if previous is not None and open_ms <= previous:
            raise RuntimeError("Bybit open times are not strictly increasing")
        index = (open_ms - GRID_START_MS) // K.BAR_MS
        if index < 0 or index >= n:
            raise RuntimeError("Bybit bar index outside the frozen grid")
        high[index] = float(parts[2])
        low[index] = float(parts[3])
        close[index] = float(parts[4])
        present += 1
        previous = open_ms
        if first_ms is None:
            first_ms = open_ms
        last_ms = open_ms
    if first_ms != _ms("2020-03-31") + 21 * 60 * 60 * 1000:
        raise RuntimeError("first Bybit open is not 2020-03-31T21:00:00Z")
    if last_ms != _ms("2024-12-31") + (20 * 60 + 55) * 60 * 1000:
        raise RuntimeError("last Bybit open is not 2024-12-31T20:55:00Z")
    if present != 476254:
        raise RuntimeError("Bybit row count drifted from the pin")
    provenance = {
        "dataset_id": K.DATASET_ID,
        "series": K.SERIES_NAME,
        "canonical_sha256": digest,
        "venue": K.VENUE,
        "instrument": K.INSTRUMENT,
        "contract_type": K.CONTRACT_TYPE,
        "interval": K.INTERVAL,
        "clock": K.CLOCK,
        "present_bars": present,
        "grid_bars": n,
        "missing_bars": int(n - present),
        "first_open_ms": int(first_ms),
        "last_open_ms": int(last_ms),
        "time_disjoint_from_discovery": False,
    }
    return high, low, close, provenance


def collect(high, low, close) -> dict:
    n_days = int(high.shape[0]) // K.BARS_PER_DAY
    if n_days != GRID_DAYS:
        raise RuntimeError("grid length drifted")
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
    by_year = {str(year): 0 for year in range(2020, 2025)}
    for day in range(n_days):
        day_ms = GRID_START_MS + day * K.DAY_MS
        if day_ms < EVENT_START_MS or day_ms >= SURFACE_END_MS:
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
        if (rv_start, rv_count) != (form - 1, K.FORMATION_BARS + 1):
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
                raise RuntimeError(f"analysis year outside 2020-2024: {stamp.year}")
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


def assign_route(counts_ok: bool, power: float) -> str:
    if not counts_ok:
        return K.ROUTE_LIMITED
    if not math.isfinite(power) or power < K.POWER_FLOOR:
        return K.ROUTE_WEAK
    return K.ROUTE_ADEQUATE


def summarize(collected: dict) -> dict:
    rows = collected["rows"]
    usable = [row["relative_width"] for row in rows]
    if len(usable) < 3:
        quant = {}
        ratio = float("inf")
        mean = float("nan")
    else:
        quant = _quantiles(usable)
        ratio = quant["p90"] / quant["p10"] if quant["p10"] > 0.0 else float("inf")
        mean = float(sum(usable) / len(usable))
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
    if week_sizes:
        forecast = information_forecast(week_sizes, phi)
        power = float(forecast["power_lower_bound_excludes_zero_at_practical_bar"])
    else:
        forecast = {
            "effective_n": 0.0,
            "fisher_se": float("inf"),
            "independent_day_se": float("inf"),
            "one_draw_per_week_se": float("inf"),
            "minimum_detectable_association_80": float("inf"),
            "power_lower_bound_excludes_zero_at_practical_bar": 0.0,
            "probability_point_clears_bar_and_bound_excludes_zero": 0.0,
        }
        power = 0.0
    first = sum(1 for row in sample if row["first_half"])
    second = sum(1 for row in sample if not row["first_half"])
    counts = collected["counts"]
    counts_ok = (
        counts["analysis_sample"] >= K.MIN_ANALYSIS_N
        and len(weeks) >= K.MIN_ISO_WEEKS
        and first >= K.MIN_HALF_N
        and second >= K.MIN_HALF_N
        and lag_n >= K.MIN_DEPENDENCE_PAIRS
        and math.isfinite(lag)
        and ratio >= K.DEGENERATE_P90_P10
        and len(usable) >= 3
    )
    route = assign_route(counts_ok, power)
    later = route == K.ROUTE_ADEQUATE
    return {
        "unit": K.UNIT,
        "mode": K.MODE,
        "outcome_read": False,
        "future_association_read": False,
        "claim_selected_pre_outcome": True,
        "owner_go_required_for_outcome": True,
        "this_unit_reads_outcome": False,
        "later_outcome_permitted_after_separate_go": later,
        "exposure_class": K.EXPOSURE_CLASS,
        "time_disjoint_from_discovery": False,
        "exact_cell_consumed_before_this_unit": False,
        "surface": K.DATASET_ID,
        "venue": K.VENUE,
        "instrument": K.INSTRUMENT,
        "contract_type": K.CONTRACT_TYPE,
        "event_start": K.EVENT_START,
        "surface_end_exclusive": K.SURFACE_END,
        "stability_split": K.STABILITY_SPLIT,
        "anchor": K.ANCHOR,
        "state": K.STATE,
        "endpoint_name": K.ENDPOINT,
        "incremental_covariate": K.INCREMENTAL_COVARIATE,
        "counts": counts,
        "by_year_analysis": collected["by_year"],
        "by_month_analysis": collected["by_month"],
        "analysis_iso_weeks": len(weeks),
        "mean_analysis_days_per_week": (float(sum(week_sizes) / len(week_sizes)) if week_sizes else 0.0),
        "first_half_n": first,
        "second_half_n": second,
        "relative_width": {
            "n_usable": len(usable),
            "mean": mean,
            "quantiles": quant,
            "p90_over_p10": ratio,
        },
        "lag1_relative_width_rank_correlation": lag,
        "lag1_n": lag_n,
        "degenerate_width": bool(len(usable) >= 3 and ratio < K.DEGENERATE_P90_P10),
        "count_floor_met": counts_ok,
        "information_forecast": forecast,
        "pre_outcome_route": route,
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
    if payload.get("outcome_read") is not False or payload.get("future_association_read") is not False:
        raise RuntimeError("support payload marks an outcome")
    if payload.get("this_unit_reads_outcome") is not False:
        raise RuntimeError("support payload authorizes an immediate outcome read")


def render_md(payload: dict) -> str:
    counts = payload["counts"]
    width = payload["relative_width"]
    forecast = payload["information_forecast"]
    months = payload["by_month_analysis"]
    month_line = ", ".join(f"{key} {months[key]}" for key in sorted(months))
    return "\n".join([
        f"# {K.UNIT} — outcome-blind feasibility",
        "",
        f"`outcome_read = false`",
        f"`future_association_read = false`",
        f"`owner_go_required_for_outcome = true`",
        f"`pre_outcome_route = {payload['pre_outcome_route']}`",
        f"`later_outcome_permitted_after_separate_go = {str(payload['later_outcome_permitted_after_separate_go']).lower()}`",
        "",
        "This note counts path presence and the width state on one pinned Bybit series. It does not contain the next-hour endpoint or an association with that endpoint.",
        "",
        f"Surface `{payload['surface']}` `{payload['venue']}` `{payload['instrument']}` `{payload['contract_type']}`.",
        f"Events `{payload['event_start']}` to `{payload['surface_end_exclusive']}` exclusive.",
        f"Exposure `{payload['exposure_class']}`. Time-disjoint from the Binance discovery window: false.",
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
        f"- mean: {width['mean']}",
        f"- quantiles: {width['quantiles']}",
        f"- p90/p10: {width['p90_over_p10']}",
        f"- lag-1 rank correlation of relative width: {payload['lag1_relative_width_rank_correlation']}",
        f"- lag pairs: {payload['lag1_n']}",
        "",
        "## Information forecast",
        "",
        "The forecast is the confirmation unit's width-lag AR(1) Kish model. It does not use the next-hour endpoint.",
        "",
        f"- effective N: {forecast.get('effective_n')}",
        f"- Fisher SE: {forecast.get('fisher_se')}",
        f"- independent-day SE: {forecast.get('independent_day_se')}",
        f"- one-draw-per-week SE: {forecast.get('one_draw_per_week_se')}",
        f"- 80% MDE: {forecast.get('minimum_detectable_association_80')}",
        f"- power that the lower bound excludes 0 at +0.10: {forecast.get('power_lower_bound_excludes_zero_at_practical_bar')}",
        "",
        "A separate owner go is required before any outcome. This file does not give that go.",
        "BitMEX is outside this unit. No second historical surface is opened here.",
        "",
    ])


def main() -> dict:
    if OUT_JSON.exists() or OUT_MD.exists() or OUT_MANIFEST.exists():
        raise SystemExit(K.REFUSAL_RERUN)
    if not DESIGN_PATH.is_file():
        raise RuntimeError("feasibility design is missing")
    high, low, close, provenance = load_ohlc()
    payload = summarize(collect(high, low, close))
    payload["read_at"] = dt.datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload["code_digest"] = code_digest()
    payload["design_sha256"] = hashlib.sha256(DESIGN_PATH.read_bytes()).hexdigest()
    payload["discovery_result_sha256"] = K.DISCOVERY_RESULT_SHA256
    payload["grid"] = provenance
    assert_support_only(payload)
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    OUT_MD.write_text(render_md(payload), encoding="utf-8")
    manifest = {
        "unit": K.UNIT,
        "outcome_read": False,
        "future_association_read": False,
        "owner_go_required_for_outcome": True,
        "this_unit_reads_outcome": False,
        "later_outcome_permitted_after_separate_go": payload["later_outcome_permitted_after_separate_go"],
        "pre_outcome_route": payload["pre_outcome_route"],
        "read_at": payload["read_at"],
        "design_sha256": payload["design_sha256"],
        "code_digest": payload["code_digest"],
        "canonical_sha256": K.CANONICAL_SHA256,
        "support_sha256": hashlib.sha256(OUT_JSON.read_bytes()).hexdigest(),
        "analysis_n": payload["counts"]["analysis_sample"],
        "analysis_iso_weeks": payload["analysis_iso_weeks"],
        "exposure_class": K.EXPOSURE_CLASS,
        "time_disjoint_from_discovery": False,
        "bitmex_in_unit": False,
        "objects_2025_2026_used": False,
        "e1_touched": False,
    }
    OUT_MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    main()
