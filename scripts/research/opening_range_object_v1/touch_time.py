"""Outcome-blind touch-time audit and four-cell support census.

Counts formations, first-interaction existence, and time from the decision
point to that interaction. It does not score a post-touch path.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np

from . import census, constants as K

ROOT = Path(__file__).resolve().parents[3]
OUT_JSON = ROOT / "docs" / "research" / "OPENING_RANGE_OBJECT_V1_AMENDMENT_A1_CENSUS.json"
OUT_MD = ROOT / "docs" / "research" / "OPENING_RANGE_OBJECT_V1_AMENDMENT_A1_CENSUS.md"
ELAPSED_LABELS = ("under_60m", "m60_to_under_240", "m240_to_under_720", "at_least_720m")
QUANTILES = (0.25, 0.50, 0.75)


def _quantile(values: list[float], q: float):
    if not values:
        return None
    return float(np.quantile(np.asarray(values, dtype=np.float64), q))


def _bin_elapsed(minutes: float) -> str:
    edges = K.ELAPSED_BIN_EDGES_MIN
    if minutes < edges[0]:
        return ELAPSED_LABELS[0]
    if minutes < edges[1]:
        return ELAPSED_LABELS[1]
    if minutes < edges[2]:
        return ELAPSED_LABELS[2]
    return ELAPSED_LABELS[3]


def _empty_hist() -> dict:
    return {label: 0 for label in ELAPSED_LABELS}


def summarize_clocks(rows: list[dict]) -> dict:
    real_elapsed = [float(r["elapsed_real_min"]) for r in rows]
    pseudo_elapsed = [float(r["elapsed_pseudo_min"]) for r in rows]
    delta = [a - b for a, b in zip(real_elapsed, pseudo_elapsed)]
    abs_delta = [abs(x) for x in delta]
    real_hist = _empty_hist()
    pseudo_hist = _empty_hist()
    real_hour = {str(h): 0 for h in range(24)}
    pseudo_hour = {str(h): 0 for h in range(24)}
    nearby_weeks = set()
    n = len(rows)
    nearby = far = same_hour = 0
    for row, dlt, ad in zip(rows, delta, abs_delta):
        real_hist[_bin_elapsed(row["elapsed_real_min"])] += 1
        pseudo_hist[_bin_elapsed(row["elapsed_pseudo_min"])] += 1
        real_hour[str(row["real_hour"])] += 1
        pseudo_hour[str(row["pseudo_hour"])] += 1
        if row["real_hour"] == row["pseudo_hour"]:
            same_hour += 1
        if ad < K.TIMING_NEARBY_MIN:
            nearby += 1
            nearby_weeks.add((row["iso_year"], row["iso_week"]))
        if ad >= K.TIMING_FAR_MIN:
            far += 1
    share_far = (far / n) if n else 0.0
    median_abs = _quantile(abs_delta, 0.50)
    material = False if median_abs is None else K.timing_imbalance_material(share_far, median_abs)
    return {
        "paired_n": n,
        "elapsed_real_min": {f"p{int(q * 100)}": _quantile(real_elapsed, q) for q in QUANTILES},
        "elapsed_pseudo_min": {f"p{int(q * 100)}": _quantile(pseudo_elapsed, q) for q in QUANTILES},
        "paired_delta_min": {
            "mean": (sum(delta) / n) if n else None,
            **{f"p{int(q * 100)}": _quantile(delta, q) for q in QUANTILES},
        },
        "abs_paired_delta_min": {f"p{int(q * 100)}": _quantile(abs_delta, q) for q in QUANTILES},
        "elapsed_real_bins": real_hist,
        "elapsed_pseudo_bins": pseudo_hist,
        "real_touch_hour": real_hour,
        "pseudo_touch_hour": pseudo_hour,
        "same_clock_hour_n": same_hour,
        "same_clock_hour_share": (same_hour / n) if n else None,
        "nearby_60m_n": nearby,
        "nearby_60m_share": (nearby / n) if n else None,
        "nearby_60m_iso_weeks": len(nearby_weeks),
        "far_240m_n": far,
        "far_240m_share": share_far if n else None,
        "timing_imbalance_material": material,
    }


def audit(bars, *, amendment_commit: str) -> dict:
    high = np.asarray(bars.high, dtype=np.float64)
    low = np.asarray(bars.low, dtype=np.float64)
    close = np.asarray(bars.close, dtype=np.float64)
    cells = {}
    for name, offset in K.ANCHORS.items():
        clocks: list[dict] = []
        counts = census._cell(high, low, close, int(bars.t0), offset, clocks)
        timing = summarize_clocks(clocks)
        if timing["paired_n"] != counts["paired_outcome_eligible"]:
            raise RuntimeError("touch-time rows do not match paired support")
        cells[name] = {
            "support": {k: counts[k] for k in (
                "calendar_days", "formation_incomplete", "formation_complete",
                "nonpositive_width", "close_not_strictly_inside", "usable_geometry",
                "lifespan_truncated", "no_interaction", "first_interaction",
                "ambiguous_interaction", "high_side_interaction", "low_side_interaction",
                "immediate_interaction", "outcome_window_incomplete",
                "one_sided_outcome_eligible", "pseudo_one_sided_outcome_eligible",
                "paired_outcome_eligible", "weekday_group_too_small", "partner_not_found",
                "paired_iso_weeks", "planning_half_width", "information_status",
                "paired_by_year", "paired_by_weekday",
            )},
            "touch_time": timing,
        }
    primary = cells[K.PRIMARY_CELL]["touch_time"]
    handling = K.timing_handling(
        bool(primary["timing_imbalance_material"]),
        int(primary["nearby_60m_n"]),
        int(primary["nearby_60m_iso_weeks"]),
    )
    payload = {
        "unit": K.UNIT,
        "amendment": K.AMENDMENT,
        "object_name": K.OBJECT_NAME,
        "outcome_read": False,
        "y_known": False,
        "original_design_commit": K.ORIGINAL_DESIGN_COMMIT,
        "original_design_sha256": K.ORIGINAL_DESIGN_SHA256,
        "amendment_commit": amendment_commit,
        "surface": K.SURFACE_ID,
        "anchors": dict(K.ANCHORS),
        "timing_rule": {
            "far_minutes": K.TIMING_FAR_MIN,
            "far_share": K.TIMING_FAR_SHARE,
            "median_abs_minutes": K.TIMING_MEDIAN_ABS_MIN,
            "nearby_minutes": K.TIMING_NEARBY_MIN,
        },
        "primary_timing_imbalance_material": primary["timing_imbalance_material"],
        "timing_handling": handling,
        "cells": cells,
    }
    census.assert_support_only(payload)
    if payload["outcome_read"] is not False:
        raise RuntimeError("audit must keep outcome_read false")
    return payload


def render_markdown(payload: dict) -> str:
    lines = [
        "# OPENING_RANGE_OBJECT_V1 amendment A1 — support and touch-time audit",
        "",
        "No post-touch outcome was computed. `outcome_read` is false.",
        "",
        f"- Object name: `{payload['object_name']}`",
        f"- Original design: `{payload['original_design_commit']}`",
        f"- Amendment commit: `{payload['amendment_commit']}`",
        f"- Primary timing imbalance material: `{str(payload['primary_timing_imbalance_material']).lower()}`",
        f"- Timing handling: `{payload['timing_handling']}`",
        "",
    ]
    for name in K.CLOCK_CELLS:
        cell = payload["cells"][name]
        sup = cell["support"]
        tm = cell["touch_time"]
        lines.append(f"## {name}")
        lines.append("")
        lines.append(
            f"- paired: {sup['paired_outcome_eligible']} across {sup['paired_iso_weeks']} ISO weeks"
            f" — `{sup['information_status']}`"
        )
        lines.append(
            f"- usable geometry {sup['usable_geometry']}, first interaction {sup['first_interaction']},"
            f" ambiguous {sup['ambiguous_interaction']}, immediate {sup['immediate_interaction']}"
        )
        lines.append(
            f"- elapsed real p50 {tm['elapsed_real_min']['p50']} min;"
            f" pseudo p50 {tm['elapsed_pseudo_min']['p50']} min;"
            f" paired delta p50 {tm['paired_delta_min']['p50']} min"
        )
        lines.append(
            f"- |Δ| p50 {tm['abs_paired_delta_min']['p50']} min;"
            f" nearby 60m share {tm['nearby_60m_share']};"
            f" far 240m share {tm['far_240m_share']};"
            f" same clock hour share {tm['same_clock_hour_share']}"
        )
        lines.append(f"- material: `{str(tm['timing_imbalance_material']).lower()}`")
        lines.append("")
    lines.append("Touch time was not used to rematch pairs or to choose an hour.")
    lines.append("")
    return "\n".join(lines)


def _git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def write_audit(payload: dict) -> None:
    census.assert_support_only(payload)
    if OUT_JSON.exists() or OUT_MD.exists():
        raise SystemExit("REFUSING_RERUN")
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    OUT_MD.write_text(render_markdown(payload), encoding="utf-8")


def main() -> int:
    from scripts.research.level_touch_degradation_v1.data import load_discovery_bars

    if OUT_JSON.exists() or OUT_MD.exists():
        raise SystemExit("REFUSING_RERUN")
    payload = audit(load_discovery_bars(), amendment_commit=_git_head())
    # Constructor drift against the original outcome-blind census.
    if payload["cells"]["UTC_00"]["support"]["paired_outcome_eligible"] != 1719:
        raise RuntimeError("UTC_00 paired support moved")
    if payload["cells"]["UTC_12"]["support"]["paired_outcome_eligible"] != 1704:
        raise RuntimeError("UTC_12 paired support moved")
    write_audit(payload)
    primary = payload["cells"]["UTC_00"]
    print(json.dumps({
        "outcome_read": payload["outcome_read"],
        "timing_handling": payload["timing_handling"],
        "primary_material": payload["primary_timing_imbalance_material"],
        "paired": {name: payload["cells"][name]["support"]["paired_outcome_eligible"] for name in K.CLOCK_CELLS},
        "weeks": {name: payload["cells"][name]["support"]["paired_iso_weeks"] for name in K.CLOCK_CELLS},
        "information": {name: payload["cells"][name]["support"]["information_status"] for name in K.CLOCK_CELLS},
        "utc00_abs_delta_p50": primary["touch_time"]["abs_paired_delta_min"]["p50"],
        "utc00_far_share": primary["touch_time"]["far_240m_share"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
