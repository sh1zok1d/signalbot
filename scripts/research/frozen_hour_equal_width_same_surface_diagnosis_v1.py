"""Same-surface mechanism diagnosis for the published FROZEN_HOUR_RANGE pairs.

MODE = POST_OUTCOME_MECHANISM_DIAGNOSIS
EVIDENCE_UPGRADE = NONE
CONFIRMATION = false
ORIGINAL_RESULT_UNCHANGED = true
PRODUCT_CHANGE = none

The published weekday half-rotation partner stays the partner. The only change
is the frozen equal-width scale from FROZEN_HOUR_EQUAL_WIDTH_V1: one k > 0 on
that partner's log offsets so the pseudo linear width equals today's real width.
A candidate that fails the scale is dropped from the common-support cohort. It
is not replaced by a later weekday. That would be a new match.

This is not a confirmation and not a new route. The CORE_BTC 2020–2024 surface
is already consumed. No 2025/2026, E1, BitMEX, prospective, or product tape.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import subprocess
from pathlib import Path

import numpy as np

from scripts.research.frozen_hour_equal_width_v1.evaluate import (
    _draw_multiplicity,
    _one_mean,
    resolution_indicator,
)
from scripts.research.frozen_hour_equal_width_v1.solver import collides, solve_equal_width
from scripts.research.level_touch_degradation_v1.data import load_discovery_bars
from scripts.research.opening_range_object_v1 import census, constants as PARENT
from scripts.research.opening_range_object_v1 import outcomes
from scripts.research.opening_range_object_v1.evaluate import _arm_summary, score_pairs

ROOT = Path(__file__).resolve().parents[2]
OUT_JSON = ROOT / "docs" / "research" / "FROZEN_HOUR_EQUAL_WIDTH_SAME_SURFACE_DIAGNOSIS_V1.json"
OUT_MD = ROOT / "docs" / "research" / "FROZEN_HOUR_EQUAL_WIDTH_SAME_SURFACE_DIAGNOSIS_V1.md"
ORIGINAL_RESULT = ROOT / "docs" / "research" / "OPENING_RANGE_OBJECT_V1_RESULT.json"
SPOT_RESULT = ROOT / "docs" / "research" / "FROZEN_HOUR_EQUAL_WIDTH_V1_RESULT.json"
CELLS = ("UTC_00", "UTC_12")
YEARS = (2020, 2021, 2022, 2023, 2024)
QUANTILE_P = (0.1, 0.25, 0.5, 0.75, 0.9)
BOOT_DRAWS = 2000
EXPLORATORY_SEEDS = {"UTC_00": 20261105, "UTC_12": 20261106}
REFUSAL_RERUN = "REFUSING_RERUN"
# Owner illustrations for this diagnosis. Not a confirmatory bar and not a route.
STRONG_ABS_PP = 2.0
MIXED_ABS_PP = (4.0, 5.0)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mean(values: list) -> float:
    if not values:
        raise RuntimeError("empty mean")
    return float(sum(values) / len(values))


def _quantiles(values: list) -> dict:
    column = np.asarray(values, dtype=np.float64)
    return {
        f"p{int(q * 100)}": float(np.quantile(column, q, method="linear"))
        for q in QUANTILE_P
    }


def _window(series, index: int) -> np.ndarray:
    start = int(index) + 1
    return np.asarray(series[start:start + PARENT.HORIZON_BARS], dtype=np.float64)


def resolution_bit(high, low, index: int, level_high: float, level_low: float, side: str) -> float:
    """Parent score_window resolution, checked against the frozen equal-width bit."""
    window_high = _window(high, index)
    window_low = _window(low, index)
    parent_bit = outcomes.score_window(window_high, window_low, level_high, level_low, side)["resolution"]
    frozen_bit = resolution_indicator(window_high, window_low, level_high, level_low, side)
    if parent_bit != frozen_bit:
        raise RuntimeError("RESOLUTION_BIT_DIVERGENCE")
    return float(parent_bit)


def partner_by_touch(high, low, close, t0: int, offset: int) -> dict[int, dict]:
    """Published partner only. Same unscaled walk as opening_range_object_v1.census._cell."""
    n = int(high.shape[0])
    geoms = []
    n_days = n // PARENT.BARS_PER_DAY
    for day in range(n_days):
        day_ms = t0 + day * PARENT.DAY_MS
        if day_ms < census.EVENT_START_MS or day_ms >= census.SURFACE_END_MS:
            continue
        geo = census._geometry(high, low, close, day * PARENT.BARS_PER_DAY + offset)
        if geo is None or not geo["usable"]:
            continue
        _weekday, year, iso_year, iso_week = census._calendar(day_ms)
        active_start = day * PARENT.BARS_PER_DAY + offset + PARENT.FORMATION_BARS
        active_end = active_start + PARENT.ACTIVE_LIFE_BARS
        touch = census._first_touch(
            high, low, active_start, min(active_end, n), geo["high"], geo["low"]
        )
        eligible = False
        if touch is not None:
            j, side = touch
            eligible = side != "ambiguous" and census._window_complete(j, active_end, high, low, close)
        geoms.append({
            "day_ms": day_ms,
            "weekday": _weekday,
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
            "real_eligible": eligible,
        })
    groups: dict[int, list] = {}
    for rec in geoms:
        groups.setdefault(rec["weekday"], []).append(rec)
    found = {}
    for group in groups.values():
        n_group = len(group)
        if n_group < 2:
            continue
        shift = n_group // 2
        for i, rec in enumerate(group):
            if not rec["real_eligible"] or rec["touch"] is None:
                continue
            chosen = None
            pseudo_high = None
            pseudo_low = None
            for step in range(n_group - 1):
                cand = group[(i + shift + step) % n_group]
                if cand["day_ms"] == rec["day_ms"]:
                    continue
                high_b = rec["p0"] * math.exp(cand["u"])
                low_b = rec["p0"] * math.exp(-cand["d"])
                if not (math.isfinite(high_b) and math.isfinite(low_b) and high_b > low_b):
                    continue
                if census._collides(rec["high"], rec["low"], high_b, low_b):
                    continue
                chosen = cand
                pseudo_high = high_b
                pseudo_low = low_b
                break
            if chosen is None or pseudo_high is None or pseudo_low is None:
                continue
            ptouch = census._first_touch(
                high, low, rec["active_start"], min(rec["active_end"], n), pseudo_high, pseudo_low
            )
            if ptouch is None:
                continue
            pj, pside = ptouch
            if pside == "ambiguous" or not census._window_complete(pj, rec["active_end"], high, low, close):
                continue
            found[int(rec["touch"][0])] = {
                "partner_u": chosen["u"],
                "partner_d": chosen["d"],
                "p0": rec["p0"],
                "pseudo_high": pseudo_high,
                "pseudo_low": pseudo_low,
                "active_start": rec["active_start"],
                "active_end": rec["active_end"],
            }
    return found


def _scale_chosen_partner(high, low, close, pair: dict, meta: dict) -> dict:
    """Scale the published partner. Do not walk forward to another day."""
    w_real = float(pair["real_high"] - pair["real_low"])
    solved = solve_equal_width(meta["p0"], w_real, meta["partner_u"], meta["partner_d"])
    row = {
        "status": solved["status"],
        "eligible": False,
    }
    if solved["status"] != "ok":
        return row
    if collides(pair["real_high"], pair["real_low"], solved["pseudo_high"], solved["pseudo_low"]):
        row["status"] = "collision_after_scale"
        return row
    n = int(high.shape[0])
    ptouch = census._first_touch(
        high,
        low,
        meta["active_start"],
        min(meta["active_end"], n),
        solved["pseudo_high"],
        solved["pseudo_low"],
    )
    if ptouch is None:
        row["status"] = "no_equal_width_touch"
        return row
    pj, pside = ptouch
    if pside == "ambiguous":
        row["status"] = "ambiguous_equal_width_touch"
        return row
    if not census._window_complete(pj, meta["active_end"], high, low, close):
        row["status"] = "equal_width_window_incomplete"
        return row
    y_eq = resolution_bit(high, low, pj, solved["pseudo_high"], solved["pseudo_low"], pside)
    width_eq = float(solved["pseudo_high"] - solved["pseudo_low"])
    row.update({
        "status": "ok",
        "eligible": True,
        "y_eq": y_eq,
        "eq_index": pj,
        "eq_side": pside,
        "eq_high": float(solved["pseudo_high"]),
        "eq_low": float(solved["pseudo_low"]),
        "w_eq": width_eq,
        "k": float(solved["k"]),
        "rel_width_error": float(solved["rel_width_error"]),
        "width_ratio_eq": width_eq / w_real,
    })
    return row


def build_cell(high, low, close, t0: int, offset: int) -> dict:
    sink: list = []
    counts = census._cell(high, low, close, t0, offset, pair_sink=sink)
    if len(sink) != counts["paired_outcome_eligible"]:
        raise RuntimeError("PAIR_SINK_DRIFT")
    published = score_pairs(high, low, sink)
    arm = _arm_summary(published, "resolution")
    partners = partner_by_touch(high, low, close, t0, offset)
    if set(partners) != {int(pair["real_index"]) for pair in sink}:
        raise RuntimeError("PUBLISHED_PARTNER_JOIN_DRIFT")
    rows = []
    drop = {
        "scale_unbounded": 0,
        "scale_tolerance_failed": 0,
        "invalid_geometry": 0,
        "collision_after_scale": 0,
        "no_equal_width_touch": 0,
        "ambiguous_equal_width_touch": 0,
        "equal_width_window_incomplete": 0,
    }
    for pair, scored in zip(sink, published):
        meta = partners[int(pair["real_index"])]
        if meta["pseudo_high"] != pair["pseudo_high"] or meta["pseudo_low"] != pair["pseudo_low"]:
            raise RuntimeError("PUBLISHED_PARTNER_BOUNDS_DRIFT")
        y_real = resolution_bit(
            high, low, pair["real_index"], pair["real_high"], pair["real_low"], pair["real_side"]
        )
        y_orig = resolution_bit(
            high, low, pair["pseudo_index"], pair["pseudo_high"], pair["pseudo_low"], pair["pseudo_side"]
        )
        if y_real != scored["resolution_real"] or y_orig != scored["resolution_pseudo"]:
            raise RuntimeError("PUBLISHED_RESOLUTION_DRIFT")
        scaled = _scale_chosen_partner(high, low, close, pair, meta)
        if not scaled["eligible"]:
            status = scaled["status"]
            if status not in drop:
                raise RuntimeError(f"unknown scale status {status}")
            drop[status] += 1
            continue
        w_real = float(pair["real_high"] - pair["real_low"])
        w_orig = float(pair["pseudo_high"] - pair["pseudo_low"])
        rows.append({
            "year": int(pair["year"]),
            "iso_year": int(pair["iso_year"]),
            "iso_week": int(pair["iso_week"]),
            "y_real": y_real,
            "y_orig": y_orig,
            "y_eq": scaled["y_eq"],
            "d_orig": y_real - y_orig,
            "d_eq": y_real - scaled["y_eq"],
            "d_att": scaled["y_eq"] - y_orig,
            "w_real": w_real,
            "w_orig": w_orig,
            "w_eq": scaled["w_eq"],
            "width_ratio_orig": w_orig / w_real,
            "width_ratio_eq": scaled["width_ratio_eq"],
            "rel_mismatch_orig": (w_orig - w_real) / w_real,
            "rel_width_error": scaled["rel_width_error"],
        })
    return {
        "published_n": arm["n_pairs"],
        "published_real": arm["real"],
        "published_pseudo": arm["pseudo"],
        "published_delta": arm["paired_effect"],
        "published_iso_weeks": counts["paired_iso_weeks"],
        "published_by_year": _year_means(published),
        "drop_from_published_pairs": drop,
        "rows": rows,
    }


def _year_means(published: list) -> dict:
    grouped: dict[str, list] = {str(year): [] for year in YEARS}
    for row in published:
        grouped[str(row["year"])].append(row["resolution_real"] - row["resolution_pseudo"])
    out = {}
    for year in YEARS:
        values = grouped[str(year)]
        out[str(year)] = {
            "n": len(values),
            "original_delta": None if not values else _mean(values),
        }
    return out


def _rate_block(rows: list) -> dict:
    y_real = [row["y_real"] for row in rows]
    y_orig = [row["y_orig"] for row in rows]
    y_eq = [row["y_eq"] for row in rows]
    d_orig = [row["d_orig"] for row in rows]
    d_eq = [row["d_eq"] for row in rows]
    d_att = [row["d_att"] for row in rows]
    original_delta = _mean(d_orig)
    equal_width_delta = _mean(d_eq)
    attenuation = _mean(d_att)
    if attenuation != original_delta - equal_width_delta:
        # Sum/len is exact for these 0/1 differences when both sides use the same rows.
        if abs(attenuation - (original_delta - equal_width_delta)) > 1e-12:
            raise RuntimeError("ATTENUATION_IDENTITY_FAILED")
    ratio = None
    if abs(original_delta) > 1e-6:
        ratio = equal_width_delta / original_delta
    weeks = {(row["iso_year"], row["iso_week"]) for row in rows}
    return {
        "n": len(rows),
        "iso_weeks": len(weeks),
        "real_resolution_rate": _mean(y_real),
        "original_pseudo_resolution_rate": _mean(y_orig),
        "equal_width_pseudo_resolution_rate": _mean(y_eq),
        "original_delta": original_delta,
        "equal_width_delta": equal_width_delta,
        "attenuation": attenuation,
        "equal_width_over_original": ratio,
        "equal_width_minus_original_pseudo": attenuation,
    }


def _width_block(rows: list) -> dict:
    ratio = [row["width_ratio_orig"] for row in rows]
    mismatch = [row["rel_mismatch_orig"] for row in rows]
    eq_ratio = [row["width_ratio_eq"] for row in rows]
    eq_error = [row["rel_width_error"] for row in rows]
    return {
        "original_pseudo_over_real": {
            "mean": _mean(ratio),
            "share_pseudo_wider": _mean([1.0 if value > 1.0 else 0.0 for value in ratio]),
            "share_pseudo_narrower": _mean([1.0 if value < 1.0 else 0.0 for value in ratio]),
            "quantiles": _quantiles(ratio),
        },
        "relative_mismatch": {
            "mean": _mean(mismatch),
            "quantiles": _quantiles(mismatch),
        },
        "equal_width_over_real": {
            "mean": _mean(eq_ratio),
            "max_abs_deviation_from_1": max(abs(value - 1.0) for value in eq_ratio),
            "max_solver_rel_width_error": max(eq_error),
        },
    }


def _year_table(rows: list) -> dict:
    grouped: dict[int, list] = {year: [] for year in YEARS}
    for row in rows:
        grouped[int(row["year"])].append(row)
    out = {}
    for year in YEARS:
        subset = grouped[year]
        if not subset:
            out[str(year)] = {"n": 0}
            continue
        block = _rate_block(subset)
        width = [row["width_ratio_orig"] for row in subset]
        out[str(year)] = {
            "n": block["n"],
            "real_resolution_rate": block["real_resolution_rate"],
            "original_pseudo_resolution_rate": block["original_pseudo_resolution_rate"],
            "equal_width_pseudo_resolution_rate": block["equal_width_pseudo_resolution_rate"],
            "original_delta": block["original_delta"],
            "equal_width_delta": block["equal_width_delta"],
            "attenuation": block["attenuation"],
            "original_width_ratio_mean": _mean(width),
            "original_width_ratio_p50": float(np.quantile(np.asarray(width), 0.5, method="linear")),
        }
    return out


def _bootstrap(rows: list, seed: int) -> dict:
    fields = ("d_orig", "d_eq", "d_att")
    sums = {field: {} for field in fields}
    for row in rows:
        key = (int(row["iso_year"]), int(row["iso_week"]))
        for field in fields:
            total, n = sums[field].get(key, (0.0, 0))
            sums[field][key] = (total + float(row[field]), n + 1)
    weeks = sorted(sums["d_orig"])
    rng = np.random.default_rng(seed)
    draws = {field: [] for field in fields}
    invalid = 0
    for _ in range(BOOT_DRAWS):
        mult = _draw_multiplicity(weeks, rng)
        got = {field: _one_mean(sums[field], mult) for field in fields}
        if any(value is None for value in got.values()):
            invalid += 1
            continue
        for field, value in got.items():
            draws[field].append(value)
    valid = len(draws["d_orig"])
    interpretable = valid / BOOT_DRAWS >= 0.9 and valid > 0

    def _interval(field: str) -> dict:
        if not interpretable:
            return {"lo": None, "hi": None}
        column = np.asarray(draws[field], dtype=np.float64)
        return {
            "lo": float(np.quantile(column, 0.025, method="linear")),
            "hi": float(np.quantile(column, 0.975, method="linear")),
        }

    return {
        "class": "EXPLORATORY_POST_OUTCOME",
        "not_a_confirmatory_test": True,
        "no_pass_fail_route": True,
        "seed": seed,
        "draws": BOOT_DRAWS,
        "valid_draws": valid,
        "invalid_draws": invalid,
        "interpretable": interpretable,
        "original_delta": _interval("d_orig"),
        "equal_width_delta": _interval("d_eq"),
        "attenuation": _interval("d_att"),
    }


def _pooled_illustration(equal_width_delta: float) -> str:
    """Map the common-support equal-width delta onto the owner's stated illustrations.

    Gaps between those illustrations stay unlabeled. This is not a new bar.
    """
    eq_pp = abs(equal_width_delta * 100.0)
    if eq_pp <= STRONG_ABS_PP:
        return "WIDTH_REGIME_COUPLING_STRONGLY_SUPPORTED_AS_EXPLANATION"
    lo, hi = MIXED_ABS_PP
    if lo <= eq_pp <= hi:
        return "MIXED_WIDTH_AND_FORMATION_STRUCTURE_PLAUSIBLE"
    return "OUTSIDE_THE_STATED_NUMERIC_ILLUSTRATIONS"


def _reading(common: dict, years: dict) -> dict:
    year_deltas = [
        years[str(year)]["equal_width_delta"]
        for year in YEARS
        if years[str(year)].get("n", 0) > 0
    ]
    signs = set()
    for value in year_deltas:
        if value > 0.0:
            signs.add("positive")
        elif value < 0.0:
            signs.add("negative")
        else:
            signs.add("zero")
    sign_change = "positive" in signs and "negative" in signs
    return {
        "pooled_illustration": _pooled_illustration(common["equal_width_delta"]),
        "year_equal_width_sign_change": sign_change,
        "temporal_note": (
            "TEMPORAL_REGIME_DEPENDENCE_REMAINS"
            if sign_change
            else "YEAR_EQUAL_WIDTH_SIGNS_DO_NOT_DISAGREE"
        ),
        "does_not_say_width_fully_causes_the_effect": True,
        "evidence_upgrade": "NONE",
        "new_route": None,
    }


def _assert_published(cell_name: str, built: dict, official: dict) -> None:
    foundation = official["foundation"][cell_name]
    if built["published_n"] != foundation["n_pairs"]:
        raise RuntimeError(f"PUBLISHED_N_DRIFT {cell_name}")
    if built["published_delta"] != foundation["paired_delta"]:
        raise RuntimeError(f"PUBLISHED_DELTA_DRIFT {cell_name}")
    if built["published_real"] != foundation["real_resolution_rate"]:
        raise RuntimeError(f"PUBLISHED_REAL_RATE_DRIFT {cell_name}")
    if built["published_pseudo"] != foundation["pseudo_resolution_rate"]:
        raise RuntimeError(f"PUBLISHED_PSEUDO_RATE_DRIFT {cell_name}")
    stability = official["stability"][cell_name]["calendar_year"]
    for year in YEARS:
        got = built["published_by_year"][str(year)]
        expected = stability[str(year)]
        if got["n"] != expected["n_pairs"] or got["original_delta"] != expected["paired_effect"]:
            raise RuntimeError(f"PUBLISHED_YEAR_DRIFT {cell_name} {year}")


def _cell_payload(built: dict, seed: int) -> dict:
    rows = built["rows"]
    if len(rows) < 2:
        raise RuntimeError("COMMON_SUPPORT_TOO_SMALL")
    common = _rate_block(rows)
    years = _year_table(rows)
    return {
        "published_cohort_not_a_new_result": {
            "n": built["published_n"],
            "iso_weeks": built["published_iso_weeks"],
            "real_resolution_rate": built["published_real"],
            "original_pseudo_resolution_rate": built["published_pseudo"],
            "original_delta": built["published_delta"],
            "role": "REPRODUCTION_OF_THE_PUBLISHED_PAIRS",
        },
        "dropped_published_pairs": built["drop_from_published_pairs"],
        "common_support": common,
        "width": _width_block(rows),
        "years_common_support": years,
        "exploratory_uncertainty": _bootstrap(rows, seed),
        "reading": _reading(common, years),
    }


def _pp(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100.0:+.2f} pp"


def _pct(value: float) -> str:
    return f"{value * 100.0:.2f}%"


def render_markdown(payload: dict) -> str:
    lines = [
        "# FROZEN_HOUR_EQUAL_WIDTH_SAME_SURFACE_DIAGNOSIS_V1",
        "",
        "`MODE = POST_OUTCOME_MECHANISM_DIAGNOSIS`",
        "`EVIDENCE_UPGRADE = NONE`",
        "`CONFIRMATION = false`",
        "`ORIGINAL_RESULT_UNCHANGED = true`",
        "`PRODUCT_CHANGE = none`",
        "`INFERENCE = EXPLORATORY_POST_OUTCOME`",
        "",
        "The published route stays `FUNDING_ANCHOR_OR_PERIODIC_RANGE_STRUCTURE`.",
        "The spot equal-width route stays `NO_WIDTH_HELD_RESOLUTION_DIFFERENCE`.",
        "This file does not replace either result and does not add a route.",
        "",
        f"Read at `{payload['read_at']}`.",
        f"Surface `{payload['surface']}` `{payload['event_start']}` to `{payload['surface_end_exclusive']}` exclusive.",
        "The surface was already consumed. This is not a pristine confirmation.",
        "",
        "Partner identity is the published weekday half-rotation partner.",
        "The frozen `solve_equal_width` scale is applied to that partner only.",
        "A failed scale drops the day. It does not select a different partner.",
        "",
        "## UTC_00",
        "",
    ]
    lines.extend(_cell_markdown(payload["cells"]["UTC_00"]))
    lines.extend(["", "## UTC_12", "", "Comparative context only. Not adopted as an object.", ""])
    lines.extend(_cell_markdown(payload["cells"]["UTC_12"]))
    lines.extend([
        "",
        "## What this file does not say",
        "",
        "It does not say that width fully causes the original effect.",
        "It does not change +9.48 pp, and it does not say that width completely explains +9.48 pp.",
        "It does not confirm an opening range, a funding mechanism, a current probability, or a product signal.",
        "No new hour, match, volatility bin, or 2023 dummy is estimated.",
        "No successor was started.",
        "",
    ])
    return "\n".join(lines)


def _cell_markdown(cell: dict) -> list[str]:
    published = cell["published_cohort_not_a_new_result"]
    common = cell["common_support"]
    width = cell["width"]
    ratio = width["original_pseudo_over_real"]
    boot = cell["exploratory_uncertainty"]
    reading = cell["reading"]
    lines = [
        f"- Published cohort, reproduced, not a new result: N {published['n']}, "
        f"real {_pct(published['real_resolution_rate'])}, "
        f"original pseudo {_pct(published['original_pseudo_resolution_rate'])}, "
        f"original delta {_pp(published['original_delta'])}.",
        f"- Common support: N {common['n']}, ISO weeks {common['iso_weeks']}.",
        f"- Common-support rates: real {_pct(common['real_resolution_rate'])}, "
        f"original pseudo {_pct(common['original_pseudo_resolution_rate'])}, "
        f"equal-width pseudo {_pct(common['equal_width_pseudo_resolution_rate'])}.",
        f"- Common-support original delta {_pp(common['original_delta'])}.",
        f"- Common-support equal-width delta {_pp(common['equal_width_delta'])}.",
        f"- Attenuation (original delta minus equal-width delta) {_pp(common['attenuation'])}.",
        f"- Equal-width delta / original delta: {common['equal_width_over_original']}.",
        f"- Equal-width pseudo minus original pseudo: {_pp(common['equal_width_minus_original_pseudo'])}.",
        f"- Dropped published pairs: `{json.dumps(cell['dropped_published_pairs'], sort_keys=True)}`.",
        f"- Original width ratio mean {ratio['mean']:.6f}, "
        f"share pseudo wider {ratio['share_pseudo_wider']:.4f}, "
        f"share pseudo narrower {ratio['share_pseudo_narrower']:.4f}, "
        f"quantiles `{json.dumps(ratio['quantiles'], sort_keys=True)}`.",
        f"- Equal-width ratio mean {width['equal_width_over_real']['mean']:.12f}, "
        f"max |ratio-1| {width['equal_width_over_real']['max_abs_deviation_from_1']:.3e}, "
        f"max solver relative error {width['equal_width_over_real']['max_solver_rel_width_error']:.3e}.",
        "",
        "| year | N | real | original pseudo | equal-width pseudo | original delta | equal-width delta | attenuation | width ratio p50 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for year in YEARS:
        row = cell["years_common_support"][str(year)]
        if row["n"] == 0:
            lines.append(f"| {year} | 0 | | | | | | | |")
            continue
        lines.append(
            f"| {year} | {row['n']} | {_pct(row['real_resolution_rate'])} | "
            f"{_pct(row['original_pseudo_resolution_rate'])} | "
            f"{_pct(row['equal_width_pseudo_resolution_rate'])} | "
            f"{_pp(row['original_delta'])} | {_pp(row['equal_width_delta'])} | "
            f"{_pp(row['attenuation'])} | {row['original_width_ratio_p50']:.3f} |"
        )
    lines.extend([
        "",
        f"Exploratory week-block intervals, seed `{boot['seed']}`, B = {boot['draws']}, "
        f"class `{boot['class']}`, not a pass/fail rule.",
        f"- Original delta interval: `{json.dumps(boot['original_delta'], sort_keys=True)}`.",
        f"- Equal-width delta interval: `{json.dumps(boot['equal_width_delta'], sort_keys=True)}`.",
        f"- Attenuation interval: `{json.dumps(boot['attenuation'], sort_keys=True)}`.",
        f"- Pooled illustration: `{reading['pooled_illustration']}`.",
        f"- Year signs: `{reading['temporal_note']}`.",
        "The illustration is not a route. A year sign change is descriptive, not a 2023 finding.",
    ])
    return lines


def _assert_result_files_unchanged(before: dict) -> None:
    for path, digest in before.items():
        if _sha256(Path(path)) != digest:
            raise RuntimeError(f"OFFICIAL_RESULT_BYTES_CHANGED {path}")


def run(high, low, close, t0: int) -> dict:
    official = json.loads(ORIGINAL_RESULT.read_text(encoding="utf-8"))
    spot = json.loads(SPOT_RESULT.read_text(encoding="utf-8"))
    if official["route"] != "FUNDING_ANCHOR_OR_PERIODIC_RANGE_STRUCTURE":
        raise RuntimeError("ORIGINAL_ROUTE_UNEXPECTED")
    if spot["route"] != "NO_WIDTH_HELD_RESOLUTION_DIFFERENCE":
        raise RuntimeError("SPOT_ROUTE_UNEXPECTED")
    if int(t0) != official["panel_t0_ms"]:
        raise RuntimeError("PANEL_T0_DOES_NOT_MATCH_THE_PUBLISHED_READ")
    cells = {}
    for name in CELLS:
        built = build_cell(high, low, close, int(t0), PARENT.ANCHORS[name])
        _assert_published(name, built, official)
        cells[name] = _cell_payload(built, EXPLORATORY_SEEDS[name])
    identity = {
        "diagnosis_script_sha256": _sha256(Path(__file__)),
        "solver_sha256": _sha256(ROOT / "scripts/research/frozen_hour_equal_width_v1/solver.py"),
        "parent_census_sha256": _sha256(ROOT / "scripts/research/opening_range_object_v1/census.py"),
        "parent_outcomes_sha256": _sha256(ROOT / "scripts/research/opening_range_object_v1/outcomes.py"),
        "parent_evaluate_sha256": _sha256(ROOT / "scripts/research/opening_range_object_v1/evaluate.py"),
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    }
    return {
        "unit": "FROZEN_HOUR_EQUAL_WIDTH_SAME_SURFACE_DIAGNOSIS_V1",
        "mode": "POST_OUTCOME_MECHANISM_DIAGNOSIS",
        "evidence_upgrade": "NONE",
        "confirmation": False,
        "original_result_unchanged": True,
        "product_change": "none",
        "successor_started": False,
        "new_protected_surface_read": False,
        "inference_class": "EXPLORATORY_POST_OUTCOME",
        "read_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "surface": PARENT.SURFACE_ID,
        "event_start": PARENT.EVENT_START,
        "surface_end_exclusive": PARENT.SURFACE_END,
        "original_result": {
            "path": "docs/research/OPENING_RANGE_OBJECT_V1_RESULT.json",
            "sha256": _sha256(ORIGINAL_RESULT),
            "route": official["route"],
            "read_at": official["outcome_read_at"],
        },
        "equal_width_spot_result": {
            "path": "docs/research/FROZEN_HOUR_EQUAL_WIDTH_V1_RESULT.json",
            "sha256": _sha256(SPOT_RESULT),
            "route": spot["route"],
            "read_at": spot["read_at"],
            "surface": spot["surface"],
        },
        "code_identity": identity,
        "cells": cells,
    }


def write_outputs(payload: dict, json_path: Path = OUT_JSON, md_path: Path = OUT_MD) -> None:
    if json_path.exists() or md_path.exists():
        raise SystemExit(REFUSAL_RERUN)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")


def main() -> int:
    if OUT_JSON.exists() or OUT_MD.exists():
        raise SystemExit(REFUSAL_RERUN)
    before = {
        str(ORIGINAL_RESULT): _sha256(ORIGINAL_RESULT),
        str(SPOT_RESULT): _sha256(SPOT_RESULT),
    }
    bars = load_discovery_bars()
    official = json.loads(ORIGINAL_RESULT.read_text(encoding="utf-8"))
    if int(bars.t0) != official["panel_t0_ms"] or int(bars.n) != official["panel_bars"]:
        raise SystemExit("PANEL_DOES_NOT_MATCH_THE_PUBLISHED_READ")
    if int(bars.times[0]) < census.EVENT_START_MS or int(bars.times[-1]) >= census.SURFACE_END_MS:
        raise SystemExit("PANEL_LEAVES_THE_CONSUMED_SURFACE")
    high = np.asarray(bars.high, dtype=np.float64)
    low = np.asarray(bars.low, dtype=np.float64)
    close = np.asarray(bars.close, dtype=np.float64)
    payload = run(high, low, close, int(bars.t0))
    _assert_result_files_unchanged(before)
    write_outputs(payload)
    utc = payload["cells"]["UTC_00"]["common_support"]
    print(json.dumps({
        "read_at": payload["read_at"],
        "common_n": utc["n"],
        "original_delta": utc["original_delta"],
        "equal_width_delta": utc["equal_width_delta"],
        "attenuation": utc["attenuation"],
        "illustration": payload["cells"]["UTC_00"]["reading"]["pooled_illustration"],
        "temporal": payload["cells"]["UTC_00"]["reading"]["temporal_note"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
