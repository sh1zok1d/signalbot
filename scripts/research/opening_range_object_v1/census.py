"""Outcome-blind support census for OPENING_RANGE_OBJECT_V1.

Counts complete formations, first boundary interactions, ambiguity, and whether
the predeclared 4h window is present inside the object lifespan. It does not
score extension, reentry, excursion, time outside, or realized volatility.

A second invocation that would overwrite the official feasibility file refuses.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import subprocess
from pathlib import Path

import numpy as np

from . import constants as K

ROOT = Path(__file__).resolve().parents[3]
DESIGN_PATH = ROOT / "docs" / "research" / "OPENING_RANGE_OBJECT_V1_DESIGN.md"
FEASIBILITY_JSON = ROOT / "docs" / "research" / "OPENING_RANGE_OBJECT_V1_FEASIBILITY.json"
FEASIBILITY_MD = ROOT / "docs" / "research" / "OPENING_RANGE_OBJECT_V1_FEASIBILITY.md"
UTC = dt.timezone.utc
WEEKDAY = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

FORBIDDEN_KEY_PARTS = (
    "resolved",
    "resolution",
    "excursion",
    "midpoint",
    "extension",
    "reentry",
    "rv_post",
    "rv_pre",
    "vol_transition",
    "pair_delta",
    "y_real",
    "y_pseudo",
    "break_first",
    "reject_first",
    "time_outside",
    "traverse",
)


def _ms(iso_date: str) -> int:
    return int(dt.datetime.fromisoformat(iso_date + "T00:00:00+00:00").timestamp() * 1000)


EVENT_START_MS = _ms(K.EVENT_START)
SURFACE_END_MS = _ms(K.SURFACE_END)


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
        raise RuntimeError("support census contains outcome fields: " + ", ".join(bad))
    if payload.get("outcome_read") is not False:
        raise RuntimeError("support census must keep outcome_read false")


def _finite_bar(high, low, close, i: int) -> bool:
    return bool(np.isfinite(high[i]) and np.isfinite(low[i]) and np.isfinite(close[i]) and high[i] >= low[i])


def _first_touch(high, low, start: int, end: int, level_high: float, level_low: float):
    """First finite bar in [start, end) whose wick meets either frozen bound. None if absent."""
    if end <= start:
        return None
    h = high[start:end]
    lo = low[start:end]
    finite = np.isfinite(h) & np.isfinite(lo)
    hi_hit = finite & (h >= level_high)
    lo_hit = finite & (lo <= level_low)
    either = hi_hit | lo_hit
    if not bool(either.any()):
        return None
    k = int(np.argmax(either))
    if bool(hi_hit[k] and lo_hit[k]):
        side = "ambiguous"
    elif bool(hi_hit[k]):
        side = "high"
    else:
        side = "low"
    return start + k, side


def _window_complete(j: int, active_end: int, high, low, close) -> bool:
    """The next HORIZON_BARS exist inside the lifespan and are finite. No barrier comparison."""
    a = j + 1
    b = a + K.HORIZON_BARS
    if b > active_end or b > int(high.shape[0]):
        return False
    return bool(
        np.isfinite(high[a:b]).all()
        and np.isfinite(low[a:b]).all()
        and np.isfinite(close[a:b]).all()
    )


def _calendar(day_ms: int) -> tuple[int, int, int, int]:
    stamp = dt.datetime.fromtimestamp(day_ms / 1000.0, tz=UTC)
    iso = stamp.isocalendar()
    return stamp.weekday(), stamp.year, int(iso.year), int(iso.week)


def _geometry(high, low, close, form_i0: int):
    sl = slice(form_i0, form_i0 + K.FORMATION_BARS)
    if form_i0 < 0 or form_i0 + K.FORMATION_BARS > int(high.shape[0]):
        return None
    h = high[sl]
    lo = low[sl]
    c = close[sl]
    if not (np.isfinite(h).all() and np.isfinite(lo).all() and np.isfinite(c).all()):
        return None
    if np.any(h < lo):
        return None
    or_high = float(np.max(h))
    or_low = float(np.min(lo))
    p0 = float(c[-1])
    if not (math.isfinite(or_high) and math.isfinite(or_low) and math.isfinite(p0)):
        return None
    if or_high <= or_low or not (or_low < p0 < or_high):
        return {
            "usable": False,
            "nonpositive_width": or_high <= or_low,
            "close_not_inside": not (or_low < p0 < or_high),
        }
    return {
        "usable": True,
        "nonpositive_width": False,
        "close_not_inside": False,
        "high": or_high,
        "low": or_low,
        "p0": p0,
        "u": math.log(or_high / p0),
        "d": math.log(p0 / or_low),
    }


def _collides(real_high: float, real_low: float, pseudo_high: float, pseudo_low: float) -> bool:
    if real_high <= 0 or real_low <= 0 or pseudo_high <= 0 or pseudo_low <= 0:
        return True
    return (
        abs(pseudo_high - real_high) / real_high < K.REL_COLLIDE
        and abs(pseudo_low - real_low) / real_low < K.REL_COLLIDE
    )


def _empty_counts() -> dict:
    return {
        "calendar_days": 0,
        "formation_incomplete": 0,
        "formation_complete": 0,
        "nonpositive_width": 0,
        "close_not_strictly_inside": 0,
        "usable_geometry": 0,
        "lifespan_truncated": 0,
        "no_interaction": 0,
        "first_interaction": 0,
        "ambiguous_interaction": 0,
        "high_side_interaction": 0,
        "low_side_interaction": 0,
        "immediate_interaction": 0,
        "outcome_window_incomplete": 0,
        "one_sided_outcome_eligible": 0,
        "pseudo_one_sided_outcome_eligible": 0,
        "paired_outcome_eligible": 0,
        "weekday_group_too_small": 0,
        "partner_not_found": 0,
        "weekday_usable": {name: 0 for name in WEEKDAY},
        "paired_by_year": {str(y): 0 for y in (2020, 2021, 2022, 2023, 2024)},
        "paired_by_weekday": {name: 0 for name in WEEKDAY},
        "paired_iso_weeks": 0,
        "planning_half_width": None,
        "information_status": K.information_status(0, 0),
    }


def _touch_hour(t0: int, index: int) -> int:
    ms = t0 + index * K.BAR_MS
    return dt.datetime.fromtimestamp(ms / 1000.0, tz=UTC).hour


def _cell(high, low, close, t0: int, offset: int, clocks: list | None = None) -> dict:
    counts = _empty_counts()
    n = int(high.shape[0])
    geoms = []
    # Day index over the whole grid. A day enters only when its UTC date is inside the event window.
    n_days = n // K.BARS_PER_DAY
    for d in range(n_days):
        day_ms = t0 + d * K.DAY_MS
        if day_ms < EVENT_START_MS or day_ms >= SURFACE_END_MS:
            continue
        counts["calendar_days"] += 1
        form_i0 = d * K.BARS_PER_DAY + offset
        geo = _geometry(high, low, close, form_i0)
        if geo is None:
            counts["formation_incomplete"] += 1
            continue
        counts["formation_complete"] += 1
        if geo["nonpositive_width"]:
            counts["nonpositive_width"] += 1
        if geo["close_not_inside"]:
            counts["close_not_strictly_inside"] += 1
        if not geo["usable"]:
            continue
        counts["usable_geometry"] += 1
        weekday, year, iso_year, iso_week = _calendar(day_ms)
        counts["weekday_usable"][WEEKDAY[weekday]] += 1
        active_start = form_i0 + K.FORMATION_BARS
        active_end = active_start + K.ACTIVE_LIFE_BARS
        truncated = active_end > n
        if truncated:
            counts["lifespan_truncated"] += 1
        touch = _first_touch(high, low, active_start, min(active_end, n), geo["high"], geo["low"])
        record = {
            "day_ms": day_ms,
            "weekday": weekday,
            "year": year,
            "iso_year": iso_year,
            "iso_week": iso_week,
            "high": geo["high"],
            "low": geo["low"],
            "p0": geo["p0"],
            "u": geo["u"],
            "d": geo["d"],
            "active_start": active_start,
            "active_end": active_end,
            "touch": touch,
        }
        if touch is None:
            counts["no_interaction"] += 1
            record["real_eligible"] = False
        else:
            j, side = touch
            counts["first_interaction"] += 1
            if side == "ambiguous":
                counts["ambiguous_interaction"] += 1
            elif side == "high":
                counts["high_side_interaction"] += 1
            else:
                counts["low_side_interaction"] += 1
            if j == active_start:
                counts["immediate_interaction"] += 1
            eligible = side != "ambiguous" and _window_complete(j, active_end, high, low, close)
            if side != "ambiguous" and not eligible:
                counts["outcome_window_incomplete"] += 1
            if eligible:
                counts["one_sided_outcome_eligible"] += 1
            record["real_eligible"] = eligible
        geoms.append(record)

    groups: dict[int, list] = {}
    for rec in geoms:
        groups.setdefault(rec["weekday"], []).append(rec)
    weeks = set()
    for weekday in sorted(groups):
        group = groups[weekday]
        n_group = len(group)
        if n_group < 2:
            counts["weekday_group_too_small"] += n_group
            continue
        shift = n_group // 2
        for i, rec in enumerate(group):
            partner = None
            for step in range(n_group - 1):
                cand = group[(i + shift + step) % n_group]
                if cand["day_ms"] == rec["day_ms"]:
                    continue
                pseudo_high = rec["p0"] * math.exp(cand["u"])
                pseudo_low = rec["p0"] * math.exp(-cand["d"])
                if not (math.isfinite(pseudo_high) and math.isfinite(pseudo_low) and pseudo_high > pseudo_low):
                    continue
                if _collides(rec["high"], rec["low"], pseudo_high, pseudo_low):
                    continue
                partner = (pseudo_high, pseudo_low)
                break
            if partner is None:
                counts["partner_not_found"] += 1
                continue
            pseudo_high, pseudo_low = partner
            ptouch = _first_touch(
                high, low, rec["active_start"], min(rec["active_end"], n), pseudo_high, pseudo_low
            )
            pseudo_eligible = False
            if ptouch is not None:
                pj, pside = ptouch
                pseudo_eligible = pside != "ambiguous" and _window_complete(pj, rec["active_end"], high, low, close)
            if pseudo_eligible:
                counts["pseudo_one_sided_outcome_eligible"] += 1
            if rec["real_eligible"] and pseudo_eligible:
                counts["paired_outcome_eligible"] += 1
                if clocks is not None:
                    rj = rec["touch"][0]
                    pj = ptouch[0]
                    clocks.append({
                        "elapsed_real_min": (rj - rec["active_start"]) * 5,
                        "elapsed_pseudo_min": (pj - rec["active_start"]) * 5,
                        "real_hour": _touch_hour(t0, rj),
                        "pseudo_hour": _touch_hour(t0, pj),
                        "iso_year": rec["iso_year"],
                        "iso_week": rec["iso_week"],
                    })
                year_key = str(rec["year"])
                if year_key in counts["paired_by_year"]:
                    counts["paired_by_year"][year_key] += 1
                counts["paired_by_weekday"][WEEKDAY[rec["weekday"]]] += 1
                weeks.add((rec["iso_year"], rec["iso_week"]))
    counts["paired_iso_weeks"] = len(weeks)
    n_pairs = counts["paired_outcome_eligible"]
    width = K.planning_half_width(n_pairs)
    counts["planning_half_width"] = None if math.isinf(width) else width
    counts["information_status"] = K.information_status(n_pairs, counts["paired_iso_weeks"])
    return counts


def summarize(bars, *, design_sha256: str) -> dict:
    if int(bars.t0) % K.DAY_MS != 0:
        raise RuntimeError("panel t0 is not UTC midnight")
    high = np.asarray(bars.high, dtype=np.float64)
    low = np.asarray(bars.low, dtype=np.float64)
    close = np.asarray(bars.close, dtype=np.float64)
    cells = {name: _cell(high, low, close, int(bars.t0), offset) for name, offset in K.ANCHORS.items()}
    payload = {
        "unit": K.UNIT,
        "mode": K.MODE,
        "outcome_read": False,
        "this_artifact_is_a_support_census": True,
        "surface": K.SURFACE_ID,
        "surface_evidence_class": K.SURFACE_EVIDENCE_CLASS,
        "exact_claim_previously_read": K.EXACT_CLAIM_PREVIOUSLY_READ,
        "neighboring_path_previously_read": K.NEIGHBORING_PATH_PREVIOUSLY_READ,
        "event_start": K.EVENT_START,
        "surface_end_exclusive": K.SURFACE_END,
        "source_main": K.SOURCE_MAIN_HEAD,
        "design_sha256": design_sha256,
        "formation_bars": K.FORMATION_BARS,
        "anchors": dict(K.ANCHORS),
        "primary_cell": K.PRIMARY_CELL,
        "veto_cell": K.VETO_CELL,
        "practical_scale": K.PRACTICAL_SCALE,
        "foundation_benchmark": K.FOUNDATION_BENCHMARK,
        "planning_variance": K.PLANNING_VARIANCE,
        "min_paired_outcome_eligible": K.MIN_PAIRED,
        "min_iso_weeks": K.MIN_ISO_WEEKS,
        "panel_t0_ms": int(bars.t0),
        "panel_bars": int(bars.n),
        "cells": cells,
        "information_primary": cells[K.PRIMARY_CELL]["information_status"],
        "information_veto": cells[K.VETO_CELL]["information_status"],
    }
    assert_support_only(payload)
    return payload


def render_markdown(payload: dict) -> str:
    lines = [
        "# OPENING_RANGE_OBJECT_V1 — support census",
        "",
        "Outcome labels were not computed. Counts are the size of the later estimand, not the estimand.",
        "",
        f"- Unit: `{payload['unit']}`",
        f"- Mode: `{payload['mode']}`",
        f"- Surface: `{payload['surface']}` `{payload['event_start']}` inclusive to `{payload['surface_end_exclusive']}` exclusive",
        f"- Evidence class: `{payload['surface_evidence_class']}`",
        f"- Design SHA256: `{payload['design_sha256']}`",
        f"- Design commit: `{payload.get('design_commit', 'unrecorded')}`",
        f"- outcome_read: `{str(payload['outcome_read']).lower()}`",
        f"- Information floor: {payload['min_paired_outcome_eligible']} paired outcome-eligible days and {payload['min_iso_weeks']} ISO weeks",
        f"- Primary information: `{payload['information_primary']}`",
        f"- Veto information: `{payload['information_veto']}`",
        "",
    ]
    for name in (K.PRIMARY_CELL, K.VETO_CELL):
        cell = payload["cells"][name]
        role = "primary" if name == K.PRIMARY_CELL else "noon veto"
        lines.append(f"## {name} ({role})")
        lines.append("")
        for key in (
            "calendar_days",
            "formation_incomplete",
            "formation_complete",
            "nonpositive_width",
            "close_not_strictly_inside",
            "usable_geometry",
            "lifespan_truncated",
            "no_interaction",
            "first_interaction",
            "ambiguous_interaction",
            "high_side_interaction",
            "low_side_interaction",
            "immediate_interaction",
            "outcome_window_incomplete",
            "one_sided_outcome_eligible",
            "pseudo_one_sided_outcome_eligible",
            "paired_outcome_eligible",
            "weekday_group_too_small",
            "partner_not_found",
            "paired_iso_weeks",
        ):
            lines.append(f"- {key}: {cell[key]}")
        width = cell["planning_half_width"]
        width_txt = "none" if width is None else f"{width:.6f}"
        lines.append(f"- planning_half_width: {width_txt}")
        lines.append(f"- information_status: `{cell['information_status']}`")
        lines.append(f"- paired_by_year: {json.dumps(cell['paired_by_year'], sort_keys=True)}")
        lines.append(f"- paired_by_weekday: {json.dumps(cell['paired_by_weekday'], sort_keys=True)}")
        lines.append(f"- weekday_usable: {json.dumps(cell['weekday_usable'], sort_keys=True)}")
        lines.append("")
    lines.append("No resolution rate, excursion, or real-minus-pseudo effect is in this file.")
    lines.append("")
    return "\n".join(lines)


def design_sha256() -> str:
    return hashlib.sha256(DESIGN_PATH.read_bytes()).hexdigest()


def _git_head() -> str:
    out = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True)
    return out.strip()


def write_feasibility(payload: dict) -> None:
    assert_support_only(payload)
    if FEASIBILITY_JSON.exists() or FEASIBILITY_MD.exists():
        raise SystemExit("REFUSING_RERUN")
    FEASIBILITY_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    FEASIBILITY_MD.write_text(render_markdown(payload), encoding="utf-8")


def main() -> int:
    from scripts.research.level_touch_degradation_v1.data import load_discovery_bars

    if FEASIBILITY_JSON.exists() or FEASIBILITY_MD.exists():
        raise SystemExit("REFUSING_RERUN")
    bars = load_discovery_bars()
    payload = summarize(bars, design_sha256=design_sha256())
    payload["design_commit"] = _git_head()
    write_feasibility(payload)
    print(json.dumps({
        "outcome_read": payload["outcome_read"],
        "information_primary": payload["information_primary"],
        "information_veto": payload["information_veto"],
        "primary_paired": payload["cells"][K.PRIMARY_CELL]["paired_outcome_eligible"],
        "veto_paired": payload["cells"][K.VETO_CELL]["paired_outcome_eligible"],
        "primary_weeks": payload["cells"][K.PRIMARY_CELL]["paired_iso_weeks"],
        "veto_weeks": payload["cells"][K.VETO_CELL]["paired_iso_weeks"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
