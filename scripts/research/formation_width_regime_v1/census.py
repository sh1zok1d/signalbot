"""Outcome-blind support census for FORMATION_WIDTH_REGIME_V1.

Counts completed UTC_00 formations, relative width, and whether the previous
hour and the next hour have a complete close path. It does not compute a
future RV, a future range, a return, or any association with a future path.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import subprocess
from pathlib import Path

import numpy as np

from scripts.research.level_touch_degradation_v1.data import load_discovery_bars
from scripts.research.opening_range_object_v1 import census as parent_census
from scripts.research.opening_range_object_v1 import constants as PARENT

from . import constants as K

ROOT = Path(__file__).resolve().parents[3]
PKG = Path(__file__).resolve().parent
DESIGN_PATH = ROOT / "docs" / "research" / "FORMATION_WIDTH_REGIME_V1_DESIGN.md"
OUT_JSON = ROOT / "docs" / "research" / "FORMATION_WIDTH_REGIME_V1_FEASIBILITY.json"
OUT_MD = ROOT / "docs" / "research" / "FORMATION_WIDTH_REGIME_V1_FEASIBILITY.md"
UTC = dt.timezone.utc
FORBIDDEN_KEY_PARTS = (
    "future_rv",
    "post_rv",
    "activity_rho",
    "displacement_rho",
    "spearman",
    "resolution",
    "extension",
    "reentry",
    "directional",
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


def _quantiles(values: list[float]) -> dict:
    column = np.asarray(values, dtype=np.float64)
    return {
        f"p{int(q * 100)}": float(np.quantile(column, q, method="linear"))
        for q in (0.1, 0.25, 0.5, 0.75, 0.9)
    }


def _spearman(x: list[float], y: list[float]) -> float:
    """Rank correlation of two state series. Not used on a future outcome."""
    if len(x) < 3 or len(x) != len(y):
        raise RuntimeError("state autocorrelation sample is too small")
    rx = np.asarray(x, dtype=np.float64).argsort().argsort().astype(np.float64)
    ry = np.asarray(y, dtype=np.float64).argsort().argsort().astype(np.float64)
    rx -= rx.mean()
    ry -= ry.mean()
    denom = math.sqrt(float(np.dot(rx, rx) * np.dot(ry, ry)))
    if denom == 0.0:
        raise RuntimeError("state autocorrelation is degenerate")
    return float(np.dot(rx, ry) / denom)


def _path_complete(close, start: int, count: int) -> bool:
    if start < 0 or start + count > int(close.shape[0]):
        return False
    span = close[start:start + count]
    return bool(span.shape[0] == count and np.all(np.isfinite(span)) and np.all(span > 0.0))


def collect(high, low, close, t0: int) -> dict:
    n = int(high.shape[0])
    n_days = n // K.BARS_PER_DAY
    rows = []
    counts = {
        "calendar_days": 0,
        "formation_incomplete": 0,
        "usable_formation": 0,
        "past_hour_incomplete": 0,
        "future_path_incomplete": 0,
        "analysis_sample": 0,
    }
    by_year = {str(year): {"usable": 0, "analysis": 0} for year in K.YEARS}
    for day in range(n_days):
        day_ms = t0 + day * PARENT.DAY_MS
        if day_ms < parent_census.EVENT_START_MS or day_ms >= parent_census.SURFACE_END_MS:
            continue
        counts["calendar_days"] += 1
        form = day * K.BARS_PER_DAY
        geo = parent_census._geometry(high, low, close, form)
        if geo is None or not geo["usable"]:
            counts["formation_incomplete"] += 1
            continue
        counts["usable_formation"] += 1
        width = float(geo["high"] - geo["low"])
        relative = width / float(geo["p0"])
        stamp = dt.datetime.fromtimestamp(day_ms / 1000.0, tz=UTC)
        iso = stamp.isocalendar()
        past_ok = _path_complete(close, form - K.FORMATION_BARS - 1, K.FORMATION_BARS + 1)
        future_ok = _path_complete(close, form + K.FORMATION_BARS - 1, K.HORIZON_BARS + 1)
        if not past_ok:
            counts["past_hour_incomplete"] += 1
        if not future_ok:
            counts["future_path_incomplete"] += 1
        year_key = str(stamp.year)
        if year_key not in by_year:
            raise RuntimeError(f"formation year outside 2020-2024: {stamp.year}")
        by_year[year_key]["usable"] += 1
        in_sample = past_ok and future_ok
        if in_sample:
            counts["analysis_sample"] += 1
            by_year[year_key]["analysis"] += 1
        rows.append({
            "day_ms": day_ms,
            "year": stamp.year,
            "iso_year": int(iso.year),
            "iso_week": int(iso.week),
            "relative_width": relative,
            "in_sample": in_sample,
        })
    return {"counts": counts, "by_year": by_year, "rows": rows}


def summarize(collected: dict) -> dict:
    rows = collected["rows"]
    usable = [row["relative_width"] for row in rows]
    if len(usable) < 3:
        raise RuntimeError("usable formation count is too small")
    quant = _quantiles(usable)
    ratio = quant["p90"] / quant["p10"] if quant["p10"] > 0.0 else float("inf")
    weeks = {(row["iso_year"], row["iso_week"]) for row in rows if row["in_sample"]}
    lagged_x = []
    lagged_y = []
    by_day = {row["day_ms"]: row for row in rows}
    for row in rows:
        prev = by_day.get(row["day_ms"] - PARENT.DAY_MS)
        if prev is None:
            continue
        lagged_x.append(prev["relative_width"])
        lagged_y.append(row["relative_width"])
    floor_ok = (
        collected["counts"]["analysis_sample"] >= K.MIN_ANALYSIS_N
        and len(weeks) >= K.MIN_ISO_WEEKS
        and ratio >= K.DEGENERATE_P90_P10
    )
    return {
        "unit": K.UNIT,
        "mode": K.MODE,
        "outcome_read": False,
        "future_association_read": False,
        "surface": K.SURFACE_ID,
        "event_start": K.EVENT_START,
        "surface_end_exclusive": K.SURFACE_END,
        "anchor": K.ANCHOR,
        "width": "W/P0",
        "horizon_bars": K.HORIZON_BARS,
        "counts": collected["counts"],
        "by_year": collected["by_year"],
        "analysis_iso_weeks": len(weeks),
        "relative_width": {
            "n": len(usable),
            "mean": float(sum(usable) / len(usable)),
            "quantiles": quant,
            "p90_over_p10": ratio,
        },
        "lag1_relative_width_rank_correlation": _spearman(lagged_x, lagged_y),
        "lag1_n": len(lagged_x),
        "degenerate": ratio < K.DEGENERATE_P90_P10,
        "information_status": K.ADEQUATE if floor_ok else K.LIMITED,
        "information_authorizes_outcome": False,
    }


def assert_support_only(payload: dict) -> None:
    bad = []

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
        raise RuntimeError("support census contains a future association: " + ", ".join(bad))
    if payload.get("outcome_read") is not False or payload.get("future_association_read") is not False:
        raise RuntimeError("support census must keep the outcome unread")


def render_markdown(payload: dict) -> str:
    counts = payload["counts"]
    width = payload["relative_width"]
    lines = [
        "# FORMATION_WIDTH_REGIME_V1 — support census",
        "",
        "`outcome_read = false`",
        "`future_association_read = false`",
        "",
        f"Surface `{payload['surface']}` `{payload['event_start']}` to `{payload['surface_end_exclusive']}` exclusive.",
        f"Anchor `{payload['anchor']}` only. Width `{payload['width']}`. Next-hour path length `{payload['horizon_bars']}` bars.",
        f"Information `{payload['information_status']}`. This does not authorize an outcome read.",
        "",
        f"- Calendar days: {counts['calendar_days']}",
        f"- Usable formations: {counts['usable_formation']}",
        f"- Formation incomplete: {counts['formation_incomplete']}",
        f"- Usable but previous hour incomplete: {counts['past_hour_incomplete']}",
        f"- Usable but next-hour path incomplete: {counts['future_path_incomplete']}",
        f"- Analysis sample: {counts['analysis_sample']}",
        f"- Analysis ISO weeks: {payload['analysis_iso_weeks']}",
        f"- Relative width mean {width['mean']:.6f}, p10 {width['quantiles']['p10']:.6f}, "
        f"p50 {width['quantiles']['p50']:.6f}, p90 {width['quantiles']['p90']:.6f}, "
        f"p90/p10 {width['p90_over_p10']:.3f}",
        f"- Lag-1 rank correlation of relative width: {payload['lag1_relative_width_rank_correlation']:.4f} "
        f"on {payload['lag1_n']} consecutive usable days",
        "",
        "| year | usable | analysis |",
        "| --- | --- | --- |",
    ]
    for year in K.YEARS:
        row = payload["by_year"][str(year)]
        lines.append(f"| {year} | {row['usable']} | {row['analysis']} |")
    lines.extend([
        "",
        "No future RV, range, displacement, or association is in this file.",
        "",
    ])
    return "\n".join(lines)


def write_outputs(payload: dict, json_path: Path = OUT_JSON, md_path: Path = OUT_MD) -> None:
    if json_path.exists() or md_path.exists():
        raise SystemExit(K.REFUSAL_RERUN)
    assert_support_only(payload)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")


def main() -> int:
    if OUT_JSON.exists() or OUT_MD.exists():
        raise SystemExit(K.REFUSAL_RERUN)
    design_sha = hashlib.sha256(DESIGN_PATH.read_bytes()).hexdigest()
    committed = subprocess.check_output(
        ["git", "show", "HEAD:docs/research/FORMATION_WIDTH_REGIME_V1_DESIGN.md"],
        cwd=ROOT,
    )
    if hashlib.sha256(committed).hexdigest() != design_sha:
        raise SystemExit("DESIGN_FILE_DIFFERS_FROM_HEAD")
    bars = load_discovery_bars()
    if int(bars.t0) % PARENT.DAY_MS != 0:
        raise SystemExit("PANEL_T0_IS_NOT_UTC_MIDNIGHT")
    if int(bars.times[0]) < parent_census.EVENT_START_MS or int(bars.times[-1]) >= parent_census.SURFACE_END_MS:
        raise SystemExit("PANEL_LEAVES_THE_CONSUMED_SURFACE")
    high = np.asarray(bars.high, dtype=np.float64)
    low = np.asarray(bars.low, dtype=np.float64)
    close = np.asarray(bars.close, dtype=np.float64)
    payload = summarize(collect(high, low, close, int(bars.t0)))
    payload["design_sha256"] = design_sha
    payload["code_digest"] = code_digest()
    payload["read_at"] = dt.datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    write_outputs(payload)
    print(json.dumps({
        "analysis_sample": payload["counts"]["analysis_sample"],
        "information_status": payload["information_status"],
        "outcome_read": payload["outcome_read"],
        "p50": payload["relative_width"]["quantiles"]["p50"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
