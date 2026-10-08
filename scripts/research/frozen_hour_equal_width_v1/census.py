"""Outcome-blind support census for FROZEN_HOUR_EQUAL_WIDTH_V1.

Counts formations, the equal-width solver, collisions, first-touch existence,
and whether the predeclared 4h window is present. It does not score extension,
reentry, resolution, excursion, occupancy, or a paired effect.

A second invocation that would overwrite the official feasibility file refuses
before any market file is opened.
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
from .solver import collides, solve_equal_width

ROOT = Path(__file__).resolve().parents[3]
PKG = Path(__file__).resolve().parent
DESIGN_PATH = ROOT / K.DESIGN_PATH_REL
FEASIBILITY_JSON = ROOT / "docs" / "research" / "FROZEN_HOUR_EQUAL_WIDTH_V1_FEASIBILITY.json"
FEASIBILITY_MD = ROOT / "docs" / "research" / "FROZEN_HOUR_EQUAL_WIDTH_V1_FEASIBILITY.md"
WEEKDAY = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
YEARS = (2017, 2018, 2019)

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
    "occupancy",
    "direction",
    "volatility",
    "first_barrier",
)


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
        raise RuntimeError("support census contains outcome fields: " + ", ".join(bad))
    if payload.get("outcome_read") is not False:
        raise RuntimeError("support census must keep outcome_read false")
    if payload.get("barrier_path_read") is not False:
        raise RuntimeError("support census must keep barrier_path_read false")


def _finite_prices(high, low, close, i0: int, i1: int) -> bool:
    return bool(
        np.isfinite(high[i0:i1]).all()
        and np.isfinite(low[i0:i1]).all()
        and np.isfinite(close[i0:i1]).all()
    )


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


def _window_complete(j: int, active_end: int, n: int, high, low, close) -> bool:
    """The next HORIZON_BARS exist inside the lifespan and are finite. No barrier comparison."""
    a = j + 1
    b = a + K.HORIZON_BARS
    if b > active_end or b > n:
        return False
    return _finite_prices(high, low, close, a, b)


def _calendar(day_ms: int) -> tuple[int, int, int, int]:
    stamp = dt.datetime.fromtimestamp(day_ms / 1000.0, tz=K.UTC)
    iso = stamp.isocalendar()
    return stamp.weekday(), stamp.year, int(iso.year), int(iso.week)


def _geometry(high, low, close, form_i0: int):
    if form_i0 < 0 or form_i0 + K.FORMATION_BARS > int(high.shape[0]):
        return None
    sl = slice(form_i0, form_i0 + K.FORMATION_BARS)
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


def _empty_counts() -> dict:
    return {
        "calendar_days": 0,
        "formation_incomplete": 0,
        "formation_complete": 0,
        "nonpositive_width": 0,
        "close_not_strictly_inside": 0,
        "usable_real_geometry": 0,
        "lifespan_truncated": 0,
        "valid_equal_width_pseudo_geometry": 0,
        "partner_not_found": 0,
        "weekday_group_too_small": 0,
        "partner_failures": 0,
        "solver_attempts": 0,
        "solver_success": 0,
        "scale_unbounded": 0,
        "scale_tolerance_failed": 0,
        "invalid_partner_geometry": 0,
        "collisions": 0,
        "solver_rel_width_error_max": None,
        "asymmetry_abs_diff_max": None,
        "no_real_interaction": 0,
        "first_real_interaction": 0,
        "ambiguous_real": 0,
        "high_side_real": 0,
        "low_side_real": 0,
        "immediate_real": 0,
        "outcome_window_incomplete_real": 0,
        "one_sided_outcome_eligible_real": 0,
        "no_pseudo_interaction": 0,
        "first_pseudo_interaction": 0,
        "ambiguous_pseudo": 0,
        "high_side_pseudo": 0,
        "low_side_pseudo": 0,
        "immediate_pseudo": 0,
        "outcome_window_incomplete_pseudo": 0,
        "one_sided_outcome_eligible_pseudo": 0,
        "paired_outcome_eligible": 0,
        "paired_neither_immediate": 0,
        "paired_iso_weeks": 0,
        "usable_by_year": {str(year): 0 for year in YEARS},
        "usable_by_weekday": {name: 0 for name in WEEKDAY},
        "valid_pseudo_by_year": {str(year): 0 for year in YEARS},
        "paired_by_year": {str(year): 0 for year in YEARS},
        "paired_by_weekday": {name: 0 for name in WEEKDAY},
        "information_status": K.information_status(0, 0),
    }


def _note_max(counts: dict, key: str, value: float) -> None:
    current = counts[key]
    counts[key] = value if current is None else max(current, value)


def _record_real_touch(counts: dict, rec: dict, high, low, close, n: int) -> None:
    touch = rec["touch"]
    if touch is None:
        counts["no_real_interaction"] += 1
        rec["real_eligible"] = False
        rec["real_immediate"] = False
        return
    j, side = touch
    counts["first_real_interaction"] += 1
    if side == "ambiguous":
        counts["ambiguous_real"] += 1
    elif side == "high":
        counts["high_side_real"] += 1
    else:
        counts["low_side_real"] += 1
    immediate = j == rec["active_start"]
    rec["real_immediate"] = immediate
    if immediate:
        counts["immediate_real"] += 1
    eligible = side != "ambiguous" and _window_complete(j, rec["active_end"], n, high, low, close)
    if side != "ambiguous" and not eligible:
        counts["outcome_window_incomplete_real"] += 1
    if eligible:
        counts["one_sided_outcome_eligible_real"] += 1
    rec["real_eligible"] = eligible


def _record_pseudo_touch(counts: dict, rec: dict, ptouch, high, low, close, n: int) -> bool:
    if ptouch is None:
        counts["no_pseudo_interaction"] += 1
        return False
    pj, pside = ptouch
    counts["first_pseudo_interaction"] += 1
    if pside == "ambiguous":
        counts["ambiguous_pseudo"] += 1
    elif pside == "high":
        counts["high_side_pseudo"] += 1
    else:
        counts["low_side_pseudo"] += 1
    immediate = pj == rec["active_start"]
    if immediate:
        counts["immediate_pseudo"] += 1
    eligible = pside != "ambiguous" and _window_complete(pj, rec["active_end"], n, high, low, close)
    if pside != "ambiguous" and not eligible:
        counts["outcome_window_incomplete_pseudo"] += 1
    if eligible:
        counts["one_sided_outcome_eligible_pseudo"] += 1
    rec["pseudo_immediate"] = immediate
    return eligible


def _asymmetry_gap(u: float, d: float, pseudo_high: float, pseudo_low: float, p0: float) -> float:
    ku = math.log(pseudo_high / p0)
    kd = math.log(p0 / pseudo_low)
    partner = (u - d) / (u + d)
    scaled = (ku - kd) / (ku + kd)
    return abs(scaled - partner)


def _cell(high, low, close, t0: int, offset: int, pair_sink: list | None = None) -> dict:
    counts = _empty_counts()
    n = int(high.shape[0])
    geoms = []
    n_days = n // K.BARS_PER_DAY
    for d in range(n_days):
        day_ms = t0 + d * K.DAY_MS
        if day_ms < K.EVENT_START_MS or day_ms >= K.SURFACE_END_MS:
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
        counts["usable_real_geometry"] += 1
        weekday, year, iso_year, iso_week = _calendar(day_ms)
        year_key = str(year)
        if year_key not in counts["usable_by_year"]:
            raise RuntimeError(f"usable day outside 2017-2019: {year}")
        counts["usable_by_year"][year_key] += 1
        counts["usable_by_weekday"][WEEKDAY[weekday]] += 1
        active_start = form_i0 + K.FORMATION_BARS
        active_end = active_start + K.ACTIVE_LIFE_BARS
        if active_end > n:
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
        _record_real_touch(counts, record, high, low, close, n)
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
            solved_ok = None
            for step in range(n_group - 1):
                cand = group[(i + shift + step) % n_group]
                if cand["day_ms"] == rec["day_ms"]:
                    continue
                counts["solver_attempts"] += 1
                solved = solve_equal_width(rec["p0"], rec["high"] - rec["low"], cand["u"], cand["d"])
                status = solved["status"]
                if status == "scale_unbounded":
                    counts["scale_unbounded"] += 1
                    continue
                if status == "scale_tolerance_failed":
                    counts["scale_tolerance_failed"] += 1
                    continue
                if status == "invalid_geometry":
                    counts["invalid_partner_geometry"] += 1
                    continue
                if status != "ok":
                    raise RuntimeError(f"unknown solver status {status}")
                counts["solver_success"] += 1
                _note_max(counts, "solver_rel_width_error_max", solved["rel_width_error"])
                _note_max(
                    counts,
                    "asymmetry_abs_diff_max",
                    _asymmetry_gap(cand["u"], cand["d"], solved["pseudo_high"], solved["pseudo_low"], rec["p0"]),
                )
                if collides(rec["high"], rec["low"], solved["pseudo_high"], solved["pseudo_low"]):
                    counts["collisions"] += 1
                    continue
                partner = (solved["pseudo_high"], solved["pseudo_low"])
                solved_ok = solved
                break
            if partner is None or solved_ok is None:
                counts["partner_not_found"] += 1
                continue
            counts["valid_equal_width_pseudo_geometry"] += 1
            year_key = str(rec["year"])
            counts["valid_pseudo_by_year"][year_key] += 1
            pseudo_high, pseudo_low = partner
            ptouch = _first_touch(
                high, low, rec["active_start"], min(rec["active_end"], n), pseudo_high, pseudo_low
            )
            pseudo_eligible = _record_pseudo_touch(counts, rec, ptouch, high, low, close, n)
            if rec["real_eligible"] and pseudo_eligible:
                counts["paired_outcome_eligible"] += 1
                if pair_sink is not None:
                    pair_sink.append({
                        "iso_year": rec["iso_year"],
                        "iso_week": rec["iso_week"],
                        "real_index": rec["touch"][0],
                        "real_side": rec["touch"][1],
                        "real_high": rec["high"],
                        "real_low": rec["low"],
                        "real_immediate": bool(rec["real_immediate"]),
                        "pseudo_index": ptouch[0],
                        "pseudo_side": ptouch[1],
                        "pseudo_high": pseudo_high,
                        "pseudo_low": pseudo_low,
                        "pseudo_immediate": bool(rec["pseudo_immediate"]),
                    })
                if not rec["real_immediate"] and not rec["pseudo_immediate"]:
                    counts["paired_neither_immediate"] += 1
                counts["paired_by_year"][year_key] += 1
                counts["paired_by_weekday"][WEEKDAY[rec["weekday"]]] += 1
                weeks.add((rec["iso_year"], rec["iso_week"]))
    counts["paired_iso_weeks"] = len(weeks)
    counts["partner_failures"] = counts["partner_not_found"] + counts["weekday_group_too_small"]
    counts["information_status"] = K.information_status(
        counts["paired_outcome_eligible"], counts["paired_iso_weeks"]
    )
    _assert_partitions(counts)
    return counts


def _assert_partitions(counts: dict) -> None:
    if counts["calendar_days"] != counts["formation_incomplete"] + counts["formation_complete"]:
        raise RuntimeError("calendar days do not partition into formations")
    if counts["usable_real_geometry"] != counts["no_real_interaction"] + counts["first_real_interaction"]:
        raise RuntimeError("usable real geometry does not partition into interactions")
    if counts["first_real_interaction"] != (
        counts["ambiguous_real"] + counts["high_side_real"] + counts["low_side_real"]
    ):
        raise RuntimeError("real interactions do not partition by side")
    if counts["first_real_interaction"] != (
        counts["one_sided_outcome_eligible_real"]
        + counts["outcome_window_incomplete_real"]
        + counts["ambiguous_real"]
    ):
        raise RuntimeError("real interactions do not partition into eligibility")
    if counts["usable_real_geometry"] != (
        counts["valid_equal_width_pseudo_geometry"]
        + counts["partner_not_found"]
        + counts["weekday_group_too_small"]
    ):
        raise RuntimeError("usable days do not partition into pseudo geometry and partner failures")
    if counts["valid_equal_width_pseudo_geometry"] != (
        counts["no_pseudo_interaction"] + counts["first_pseudo_interaction"]
    ):
        raise RuntimeError("valid pseudo geometry does not partition into interactions")
    if counts["first_pseudo_interaction"] != (
        counts["ambiguous_pseudo"] + counts["high_side_pseudo"] + counts["low_side_pseudo"]
    ):
        raise RuntimeError("pseudo interactions do not partition by side")
    if counts["first_pseudo_interaction"] != (
        counts["one_sided_outcome_eligible_pseudo"]
        + counts["outcome_window_incomplete_pseudo"]
        + counts["ambiguous_pseudo"]
    ):
        raise RuntimeError("pseudo interactions do not partition into eligibility")
    if counts["paired_outcome_eligible"] > min(
        counts["one_sided_outcome_eligible_real"], counts["one_sided_outcome_eligible_pseudo"]
    ):
        raise RuntimeError("paired days exceed a one-sided arm")
    if counts["paired_neither_immediate"] > counts["paired_outcome_eligible"]:
        raise RuntimeError("neither-immediate subset exceeds paired days")
    err = counts["solver_rel_width_error_max"]
    if err is not None and err > K.WIDTH_REL_TOL:
        raise RuntimeError("accepted scale exceeds the frozen width tolerance")
    gap = counts["asymmetry_abs_diff_max"]
    if gap is not None and gap > 1e-9:
        raise RuntimeError("accepted scale changed log asymmetry")
    attempts = (
        counts["solver_success"]
        + counts["scale_unbounded"]
        + counts["scale_tolerance_failed"]
        + counts["invalid_partner_geometry"]
    )
    if attempts != counts["solver_attempts"]:
        raise RuntimeError("solver statuses do not add up to attempts")
    if counts["solver_success"] != counts["collisions"] + counts["valid_equal_width_pseudo_geometry"]:
        raise RuntimeError("solver successes do not partition into collisions and accepted partners")


def code_digest() -> str:
    digest = hashlib.sha256()
    for path in sorted(PKG.glob("*.py")):
        rel = str(path.relative_to(ROOT))
        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        digest.update(rel.encode())
        digest.update(file_hash.encode())
    return digest.hexdigest()


def design_sha256() -> str:
    return hashlib.sha256(DESIGN_PATH.read_bytes()).hexdigest()


def assert_design_freeze() -> None:
    content = subprocess.check_output(
        ["git", "show", f"{K.DESIGN_COMMIT}:{K.DESIGN_PATH_REL}"],
        cwd=ROOT,
    )
    if hashlib.sha256(content).hexdigest() != design_sha256():
        raise RuntimeError("design note no longer matches the freeze commit")


def _git(args: list[str]) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def summarize(high, low, close, t0: int, *, provenance: dict, design_sha256_hex: str) -> dict:
    if int(t0) % K.DAY_MS != 0:
        raise RuntimeError("panel t0 is not UTC midnight")
    high_a = np.asarray(high, dtype=np.float64)
    low_a = np.asarray(low, dtype=np.float64)
    close_a = np.asarray(close, dtype=np.float64)
    cells = {name: _cell(high_a, low_a, close_a, int(t0), offset) for name, offset in K.ANCHORS.items()}
    for name in K.CELLS:
        if cells[name]["calendar_days"] > K.CALENDAR_DAYS:
            raise RuntimeError(f"{name} counted more than 852 calendar days")
    payload = {
        "unit": K.UNIT,
        "mode": K.MODE,
        "outcome_read": False,
        "barrier_path_read": False,
        "labels_computed": False,
        "bootstrap_executed": False,
        "practical_scale_applied": False,
        "this_artifact_is_a_support_census": True,
        "owner_go_for_outcome": False,
        "first_access_for_this_estimand": True,
        "objects_2025_2026_opened": False,
        "e1_opened": False,
        "prospective_opened": False,
        "product_opened": False,
        "surface": K.SURFACE_ID,
        "venue": K.VENUE,
        "interval": K.INTERVAL,
        "surface_evidence_class": K.SURFACE_EVIDENCE_CLASS,
        "exact_claim_previously_read": False,
        "event_start": K.EVENT_START,
        "surface_end_exclusive": K.SURFACE_END,
        "first_month": K.FIRST_MONTH,
        "last_month": K.LAST_MONTH,
        "design_commit": K.DESIGN_COMMIT,
        "design_sha256": design_sha256_hex,
        "branch": _git(["rev-parse", "--abbrev-ref", "HEAD"]),
        "head": _git(["rev-parse", "HEAD"]),
        "code_digest": code_digest(),
        "formation_bars": K.FORMATION_BARS,
        "anchors": dict(K.ANCHORS),
        "primary_cell": K.PRIMARY_CELL,
        "diagnostic_cell": K.DIAGNOSTIC_CELL,
        "practical_scale": K.PRACTICAL_SCALE,
        "min_paired_outcome_eligible": K.MIN_PAIRED,
        "min_iso_weeks": K.MIN_ISO_WEEKS,
        "width_rel_tol": K.WIDTH_REL_TOL,
        "rel_collide": K.REL_COLLIDE,
        "max_doubles": K.MAX_DOUBLES,
        "bisections": K.BISECTIONS,
        "boot_draws_not_run": K.BOOT_DRAWS,
        "boot_seed_utc_00_not_run": K.BOOT_SEED_UTC_00,
        "boot_seed_utc_12_not_run": K.BOOT_SEED_UTC_12,
        "panel_t0_ms": int(t0),
        "panel_bars": int(high_a.shape[0]),
        "panel_provenance": provenance,
        "cells": cells,
        "information_utc_00": cells[K.PRIMARY_CELL]["information_status"],
        "information_utc_12": cells[K.DIAGNOSTIC_CELL]["information_status"],
        "information_gate": K.joint_information(
            cells[K.PRIMARY_CELL]["information_status"],
            cells[K.DIAGNOSTIC_CELL]["information_status"],
        ),
    }
    assert_support_only(payload)
    return payload


def render_markdown(payload: dict) -> str:
    lines = [
        "# FROZEN_HOUR_EQUAL_WIDTH_V1 — support census",
        "",
        "Outcome labels were not computed. Counts are the size of a later estimand, not the estimand.",
        "The information gate does not authorize that estimand.",
        "",
        f"- Unit: `{payload['unit']}`",
        f"- Mode: `{payload['mode']}`",
        f"- Branch: `{payload['branch']}`",
        f"- HEAD at the run: `{payload['head']}`",
        f"- Design commit: `{payload['design_commit']}`",
        f"- Design SHA256: `{payload['design_sha256']}`",
        f"- Code digest: `{payload['code_digest']}`",
        f"- Surface: `{payload['surface']}` `{payload['event_start']}` inclusive to `{payload['surface_end_exclusive']}` exclusive",
        f"- Months requested: `{payload['first_month']}` through `{payload['last_month']}`",
        f"- Evidence class: `{payload['surface_evidence_class']}`",
        f"- First access for this estimand: `{str(payload['first_access_for_this_estimand']).lower()}`",
        f"- outcome_read: `{str(payload['outcome_read']).lower()}`",
        f"- barrier_path_read: `{str(payload['barrier_path_read']).lower()}`",
        f"- 2025/2026 opened: `{str(payload['objects_2025_2026_opened']).lower()}`",
        f"- E1 opened: `{str(payload['e1_opened']).lower()}`",
        f"- Prospective opened: `{str(payload['prospective_opened']).lower()}`",
        f"- Product opened: `{str(payload['product_opened']).lower()}`",
        f"- Information floor: {payload['min_paired_outcome_eligible']} paired outcome-eligible days and {payload['min_iso_weeks']} ISO weeks",
        f"- UTC_00 information: `{payload['information_utc_00']}`",
        f"- UTC_12 information: `{payload['information_utc_12']}`",
        f"- Joint gate: `{payload['information_gate']}`",
        "",
        "ISO week labels of the last days of 2019 can fall in ISO year 2020. No 2020 bar was requested.",
        "A noon life that reaches 2020-01-01 is truncated. The missing bars are not filled.",
        "",
    ]
    prov = payload["panel_provenance"]
    lines.append(
        f"Panel: {prov['present_bars']} present bars, {prov['missing_bars']} missing, grid {prov['grid_bars']}."
    )
    lines.append(
        f"Off-grid opens left unplaced: {prov.get('off_grid_rows_not_placed', 0)}. "
        "An open time that is not divisible by 300000 ms is not moved onto a bucket."
    )
    lines.append("")
    for name, role in ((K.PRIMARY_CELL, "primary"), (K.DIAGNOSTIC_CELL, "diagnostic, not adoptable")):
        cell = payload["cells"][name]
        lines.append(f"## {name} ({role})")
        lines.append("")
        for key in (
            "calendar_days",
            "formation_incomplete",
            "formation_complete",
            "nonpositive_width",
            "close_not_strictly_inside",
            "usable_real_geometry",
            "lifespan_truncated",
            "valid_equal_width_pseudo_geometry",
            "solver_attempts",
            "solver_success",
            "scale_unbounded",
            "scale_tolerance_failed",
            "invalid_partner_geometry",
            "collisions",
            "partner_not_found",
            "weekday_group_too_small",
            "partner_failures",
            "no_real_interaction",
            "first_real_interaction",
            "ambiguous_real",
            "high_side_real",
            "low_side_real",
            "immediate_real",
            "outcome_window_incomplete_real",
            "one_sided_outcome_eligible_real",
            "no_pseudo_interaction",
            "first_pseudo_interaction",
            "ambiguous_pseudo",
            "high_side_pseudo",
            "low_side_pseudo",
            "immediate_pseudo",
            "outcome_window_incomplete_pseudo",
            "one_sided_outcome_eligible_pseudo",
            "paired_outcome_eligible",
            "paired_neither_immediate",
            "paired_iso_weeks",
        ):
            lines.append(f"- {key}: {cell[key]}")
        lines.append(f"- solver_rel_width_error_max: {cell['solver_rel_width_error_max']}")
        lines.append(f"- asymmetry_abs_diff_max: {cell['asymmetry_abs_diff_max']}")
        lines.append(f"- information_status: `{cell['information_status']}`")
        lines.append(f"- usable_by_year: {json.dumps(cell['usable_by_year'], sort_keys=True)}")
        lines.append(f"- valid_pseudo_by_year: {json.dumps(cell['valid_pseudo_by_year'], sort_keys=True)}")
        lines.append(f"- paired_by_year: {json.dumps(cell['paired_by_year'], sort_keys=True)}")
        lines.append(f"- usable_by_weekday: {json.dumps(cell['usable_by_weekday'], sort_keys=True)}")
        lines.append(f"- paired_by_weekday: {json.dumps(cell['paired_by_weekday'], sort_keys=True)}")
        lines.append("")
    lines.append("No resolution, extension, reentry, excursion, occupancy, or paired effect is in this file.")
    lines.append("")
    return "\n".join(lines)


def write_feasibility(payload: dict) -> None:
    assert_support_only(payload)
    if FEASIBILITY_JSON.exists() or FEASIBILITY_MD.exists():
        raise SystemExit(K.REFUSAL_RERUN)
    FEASIBILITY_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    FEASIBILITY_MD.write_text(render_markdown(payload), encoding="utf-8")


def main() -> int:
    if FEASIBILITY_JSON.exists() or FEASIBILITY_MD.exists():
        raise SystemExit(K.REFUSAL_RERUN)
    assert_design_freeze()
    from . import data

    panel, provenance = data.load_panel()
    payload = summarize(
        panel.high,
        panel.low,
        panel.close,
        panel.t0,
        provenance=provenance,
        design_sha256_hex=design_sha256(),
    )
    write_feasibility(payload)
    print(json.dumps({
        "outcome_read": payload["outcome_read"],
        "barrier_path_read": payload["barrier_path_read"],
        "information_utc_00": payload["information_utc_00"],
        "information_utc_12": payload["information_utc_12"],
        "information_gate": payload["information_gate"],
        "utc_00_paired": payload["cells"]["UTC_00"]["paired_outcome_eligible"],
        "utc_12_paired": payload["cells"]["UTC_12"]["paired_outcome_eligible"],
        "utc_00_weeks": payload["cells"]["UTC_00"]["paired_iso_weeks"],
        "utc_12_weeks": payload["cells"]["UTC_12"]["paired_iso_weeks"],
        "utc_00_solver_success": payload["cells"]["UTC_00"]["solver_success"],
        "utc_00_solver_failures": (
            payload["cells"]["UTC_00"]["scale_unbounded"]
            + payload["cells"]["UTC_00"]["scale_tolerance_failed"]
            + payload["cells"]["UTC_00"]["invalid_partner_geometry"]
        ),
        "utc_12_solver_success": payload["cells"]["UTC_12"]["solver_success"],
        "utc_12_solver_failures": (
            payload["cells"]["UTC_12"]["scale_unbounded"]
            + payload["cells"]["UTC_12"]["scale_tolerance_failed"]
            + payload["cells"]["UTC_12"]["invalid_partner_geometry"]
        ),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
