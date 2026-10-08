"""Post-outcome diagnosis of the already-read FROZEN_HOUR_RANGE map.

MODE = POST_OUTCOME_DIAGNOSIS
EVIDENCE_UPGRADE = NONE
CONFIRMATION = false
PRODUCT_CHANGE = none

Reads the already consumed CORE_BTC_BINANCE_V0 2020–2024 surface again, only to
describe the published pairs. Does not rewrite the design, the amendments, the
official result, the route, or the evaluator package. A year slice is an
accounting identity, not a winner.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from scripts.research.level_touch_degradation_v1.data import load_discovery_bars
from scripts.research.opening_range_object_v1 import census, constants as K
from scripts.research.opening_range_object_v1 import outcomes
from scripts.research.opening_range_object_v1.evaluate import (
    RESULT_JSON,
    RESULT_MD,
    _window,
    collect_pairs,
    score_pairs,
)

ROOT = Path(__file__).resolve().parents[2]
OUT_JSON = ROOT / "docs" / "research" / "FROZEN_HOUR_RANGE_POST_OUTCOME_DIAGNOSIS_V1.json"
FIG_DIR = ROOT / "docs" / "research" / "figures" / "frozen_hour_range_diagnosis"
OFFICIAL_ROUTE = "FUNDING_ANCHOR_OR_PERIODIC_RANGE_STRUCTURE"
YEARS = (2020, 2021, 2022, 2023, 2024)
# The published year table already shows the break. These two blocks only
# describe that published split. They are not a new threshold.
EARLY_YEARS = (2020, 2021, 2022)
LATE_YEARS = (2023, 2024)
# Reciprocal round cuts. Not searched, not a matching rule.
SIMILAR_WIDTH_LO = 0.8
SIMILAR_WIDTH_HI = 1.25
# Shape marks only. Not candidate endpoints.
EXCURSION_SHAPE_MARKS = (0.5, 1.0, 1.5)
UTC = dt.timezone.utc


def recover_active_start(touch_index: int, offset: int) -> int:
    """The unique formation-end bar whose 23h life contains this touch.

    Active starts are 288 bars apart and the life is 276 bars, so at most one
    legal start sits at or before the touch.
    """
    residue = offset + K.FORMATION_BARS
    delta = (int(touch_index) - residue) % K.BARS_PER_DAY
    active = int(touch_index) - delta
    if not (active <= int(touch_index) < active + K.ACTIVE_LIFE_BARS):
        raise RuntimeError("touch is outside the recovered object life")
    return active


def partner_table(high, low, close, t0: int, offset: int) -> dict[int, dict]:
    """Same weekday half-rotation as the frozen collector. Touch index -> partner day.

    Used only to measure how far the published pseudo geometry sits from the
    object day. It does not rematch and it does not change a pair.
    """
    n = int(high.shape[0])
    geoms = []
    n_days = n // K.BARS_PER_DAY
    for d in range(n_days):
        day_ms = t0 + d * K.DAY_MS
        if day_ms < census.EVENT_START_MS or day_ms >= census.SURFACE_END_MS:
            continue
        geo = census._geometry(high, low, close, d * K.BARS_PER_DAY + offset)
        if geo is None or not geo["usable"]:
            continue
        weekday, year, iso_year, iso_week = census._calendar(day_ms)
        active_start = d * K.BARS_PER_DAY + offset + K.FORMATION_BARS
        active_end = active_start + K.ACTIVE_LIFE_BARS
        touch = census._first_touch(high, low, active_start, min(active_end, n), geo["high"], geo["low"])
        eligible = False
        if touch is not None:
            j, side = touch
            eligible = side != "ambiguous" and census._window_complete(j, active_end, high, low, close)
        geoms.append({
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
            if not rec["real_eligible"]:
                continue
            partner = None
            chosen = None
            for step in range(n_group - 1):
                cand = group[(i + shift + step) % n_group]
                if cand["day_ms"] == rec["day_ms"]:
                    continue
                pseudo_high = rec["p0"] * math.exp(cand["u"])
                pseudo_low = rec["p0"] * math.exp(-cand["d"])
                if not (math.isfinite(pseudo_high) and math.isfinite(pseudo_low) and pseudo_high > pseudo_low):
                    continue
                if census._collides(rec["high"], rec["low"], pseudo_high, pseudo_low):
                    continue
                partner = (pseudo_high, pseudo_low)
                chosen = cand
                break
            if partner is None or chosen is None:
                continue
            pseudo_high, pseudo_low = partner
            ptouch = census._first_touch(
                high, low, rec["active_start"], min(rec["active_end"], n), pseudo_high, pseudo_low
            )
            if ptouch is None:
                continue
            pj, pside = ptouch
            if pside == "ambiguous" or not census._window_complete(pj, rec["active_end"], high, low, close):
                continue
            touch_index = rec["touch"][0]
            found[touch_index] = {
                "partner_day_ms": chosen["day_ms"],
                "lag_days": (chosen["day_ms"] - rec["day_ms"]) / K.DAY_MS,
                "partner_year": chosen["year"],
                "pseudo_high": pseudo_high,
                "pseudo_low": pseudo_low,
            }
    return found


def barrier_detail(high, low, level_high: float, level_low: float, side: str) -> dict:
    """Frozen score plus the first-barrier bar. Descriptive timing only."""
    scored = outcomes.score_window(high, low, level_high, level_low, side)
    high = np.asarray(high, dtype=np.float64)
    low = np.asarray(low, dtype=np.float64)
    width = float(level_high) - float(level_low)
    midpoint = (float(level_high) + float(level_low)) / 2.0
    reach = K.EXTENSION_FRACTION * width
    if side == "high":
        extension = high >= float(level_high) + reach
        reentry = low <= midpoint
    else:
        extension = low <= float(level_low) - reach
        reentry = high >= midpoint
    either = extension | reentry
    first = None
    if bool(either.any()):
        first = int(np.argmax(either))
        if bool(extension[first] and not reentry[first]) != bool(scored["extension_first"]):
            raise RuntimeError("barrier detail drifted from the frozen score")
    if bool(either.any()) != bool(scored["resolution"]):
        raise RuntimeError("resolution detail drifted from the frozen score")
    return {
        "resolution": scored["resolution"],
        "extension_first": scored["extension_first"],
        "outside_share": scored["outside_share"],
        "outward_excursion": scored["outward_excursion"],
        "both_barriers_on_first_hit": scored["both_barriers_on_first_hit"],
        "first_barrier_bar": first,
    }


def realized_vol(close: np.ndarray, first_close: int, n_returns: int) -> float | None:
    """Square-root of summed squared log returns. None when the span is missing."""
    start = int(first_close)
    stop = start + int(n_returns)
    if start < 0 or stop >= int(close.shape[0]):
        return None
    span = np.asarray(close[start:stop + 1], dtype=np.float64)
    if span.shape[0] != n_returns + 1 or not np.all(np.isfinite(span)) or np.any(span <= 0.0):
        return None
    returns = np.diff(np.log(span))
    return float(np.sqrt(np.sum(returns * returns)))


def _rank(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(values.shape[0], dtype=np.float64)
    ordered = values[order]
    n = int(values.shape[0])
    i = 0
    while i < n:
        j = i + 1
        while j < n and ordered[j] == ordered[i]:
            j += 1
        ranks[order[i:j]] = 0.5 * ((i + 1) + j)
        i = j
    return ranks


def spearman(x, y) -> dict:
    left = np.asarray(x, dtype=np.float64)
    right = np.asarray(y, dtype=np.float64)
    mask = np.isfinite(left) & np.isfinite(right)
    left = left[mask]
    right = right[mask]
    n = int(left.shape[0])
    if n < 3:
        return {"n": n, "rho": None}
    rx = _rank(left)
    ry = _rank(right)
    rx = rx - rx.mean()
    ry = ry - ry.mean()
    denom = math.sqrt(float(np.sum(rx * rx) * np.sum(ry * ry)))
    if denom == 0.0:
        return {"n": n, "rho": None}
    return {"n": n, "rho": float(np.sum(rx * ry) / denom)}


def quantiles(values) -> dict | None:
    data = np.asarray(list(values), dtype=np.float64)
    data = data[np.isfinite(data)]
    if data.size == 0:
        return None
    marks = np.quantile(data, [0.10, 0.25, 0.50, 0.75, 0.90])
    return {
        "n": int(data.size),
        "mean": float(data.mean()),
        "p10": float(marks[0]),
        "p25": float(marks[1]),
        "p50": float(marks[2]),
        "p75": float(marks[3]),
        "p90": float(marks[4]),
    }


def paired_numbers(real, pseudo) -> dict:
    left = np.asarray(list(real), dtype=np.float64)
    right = np.asarray(list(pseudo), dtype=np.float64)
    delta = left - right
    n = int(delta.size)
    mean = float(delta.mean()) if n else None
    se = None
    if n > 1:
        se = float(delta.std(ddof=1) / math.sqrt(n))
    return {
        "n": n,
        "real": float(left.mean()) if n else None,
        "pseudo": float(right.mean()) if n else None,
        "delta": mean,
        "sum_of_paired_differences": float(delta.sum()) if n else None,
        "descriptive_se": se,
        "descriptive_lo": None if se is None else mean - 1.96 * se,
        "descriptive_hi": None if se is None else mean + 1.96 * se,
        "interval_role": "DESCRIPTIVE_WALD_NOT_A_FAMILY_TEST",
    }


def width_bin(ratio: float) -> str:
    if ratio < SIMILAR_WIDTH_LO:
        return "PSEUDO_WIDER"
    if ratio <= SIMILAR_WIDTH_HI:
        return "SIMILAR"
    return "REAL_WIDER"


def equal_width_line(rows: list[dict]) -> dict:
    """y = a + b log(W_real/W_pseudo). a is the fitted difference at equal widths.

    EXPLORATORY_POST_OUTCOME. Not a control, not a confirmation, not a new claim.
    """
    y = np.asarray([row["resolution_real"] - row["resolution_pseudo"] for row in rows], dtype=np.float64)
    x = np.asarray([math.log(row["width_ratio"]) for row in rows], dtype=np.float64)
    mask = np.isfinite(y) & np.isfinite(x)
    y = y[mask]
    x = x[mask]
    if y.size < 3:
        return {"n": int(y.size), "intercept_at_equal_width": None, "slope": None}
    design = np.column_stack([np.ones(y.size), x])
    coef, _, _, _ = np.linalg.lstsq(design, y, rcond=None)
    return {
        "n": int(y.size),
        "intercept_at_equal_width": float(coef[0]),
        "slope_on_log_width_ratio": float(coef[1]),
        "role": "EXPLORATORY_POST_OUTCOME",
        "not_a_confirmation": True,
        "not_an_adjusted_claim": True,
    }


def _column(rows: list[dict], name: str):
    return [row[name] for row in rows]


def _geometry_arm(rows: list[dict], arm: str) -> dict:
    return {
        "absolute_width": quantiles(_column(rows, f"width_{arm}")),
        "relative_width": quantiles(_column(rows, f"relative_width_{arm}")),
        "upper_log_offset": quantiles(_column(rows, f"u_{arm}")),
        "lower_log_offset": quantiles(_column(rows, f"d_{arm}")),
        "asymmetry": quantiles(_column(rows, f"asymmetry_{arm}")),
    }


def _coupling(rows: list[dict]) -> dict:
    post = _column(rows, "post_decision_rv")
    pre = _column(rows, "pre_rv")
    span = _column(rows, "post_decision_range")
    out = {}
    for arm in ("real", "pseudo"):
        width = _column(rows, f"relative_width_{arm}")
        out[arm] = {
            "relative_width_vs_pre_rv": spearman(width, pre),
            "relative_width_vs_post_decision_rv": spearman(width, post),
            "relative_width_vs_post_decision_range": spearman(width, span),
            "relative_width_vs_own_resolution": spearman(width, _column(rows, f"resolution_{arm}")),
            "relative_width_vs_own_touch_latency": spearman(width, _column(rows, f"latency_{arm}")),
        }
    out["real_vs_pseudo_relative_width"] = spearman(
        _column(rows, "relative_width_real"), _column(rows, "relative_width_pseudo")
    )
    return out


def _mismatch(rows: list[dict]) -> dict:
    ratios = np.asarray(_column(rows, "width_ratio"), dtype=np.float64)
    log_gap = np.log(ratios)
    asym_gap = np.asarray(_column(rows, "asymmetry_real"), dtype=np.float64) - np.asarray(
        _column(rows, "asymmetry_pseudo"), dtype=np.float64
    )
    return {
        "width_ratio": quantiles(ratios),
        "share_pseudo_wider": float(np.mean(ratios < 1.0)),
        "share_real_wider": float(np.mean(ratios > 1.0)),
        "median_abs_log_width_mismatch": float(np.median(np.abs(log_gap))),
        "mean_log_width_mismatch": float(np.mean(log_gap)),
        "asymmetry_mismatch": quantiles(asym_gap),
    }


def _touch(rows: list[dict]) -> dict:
    return {
        "latency_min_real": quantiles(_column(rows, "latency_real")),
        "latency_min_pseudo": quantiles(_column(rows, "latency_pseudo")),
        "immediate_rate_real": float(np.mean(_column(rows, "immediate_real"))),
        "immediate_rate_pseudo": float(np.mean(_column(rows, "immediate_pseudo"))),
        "high_side_share_real": float(np.mean([row["side_real"] == "high" for row in rows])),
        "high_side_share_pseudo": float(np.mean([row["side_pseudo"] == "high" for row in rows])),
    }


def _path(rows: list[dict]) -> dict:
    return {
        "resolution": paired_numbers(_column(rows, "resolution_real"), _column(rows, "resolution_pseudo")),
        "extension_first": paired_numbers(
            _column(rows, "extension_first_real"), _column(rows, "extension_first_pseudo")
        ),
        "outside_occupancy": paired_numbers(_column(rows, "outside_real"), _column(rows, "outside_pseudo")),
        "outward_excursion": paired_numbers(_column(rows, "excursion_real"), _column(rows, "excursion_pseudo")),
    }


def _slice(rows: list[dict]) -> dict:
    return {
        "n": len(rows),
        "path": _path(rows),
        "geometry": {"real": _geometry_arm(rows, "real"), "pseudo": _geometry_arm(rows, "pseudo")},
        "mismatch": _mismatch(rows),
        "coupling": _coupling(rows),
        "touch": _touch(rows),
        "volatility": {
            "pre_formation_1h_rv": quantiles(_column(rows, "pre_rv")),
            "post_decision_4h_rv": quantiles(_column(rows, "post_decision_rv")),
            "post_decision_4h_range_over_p0": quantiles(_column(rows, "post_decision_range")),
            "post_touch_rv_real": quantiles(_column(rows, "post_touch_rv_real")),
            "post_touch_rv_pseudo": quantiles(_column(rows, "post_touch_rv_pseudo")),
        },
        "width_bins": _width_bins(rows),
        "exploratory_equal_width_line": equal_width_line(rows),
        "partner": _partner_summary(rows),
    }


def _width_bins(rows: list[dict]) -> dict:
    grouped: dict[str, list] = {"PSEUDO_WIDER": [], "SIMILAR": [], "REAL_WIDER": []}
    for row in rows:
        grouped[row["width_bin"]].append(row)
    out = {}
    for name, group in grouped.items():
        if not group:
            out[name] = {"n": 0}
            continue
        out[name] = {
            "n": len(group),
            "share": len(group) / len(rows),
            "resolution": paired_numbers(_column(group, "resolution_real"), _column(group, "resolution_pseudo")),
            "extension_first": paired_numbers(
                _column(group, "extension_first_real"), _column(group, "extension_first_pseudo")
            ),
            "outside_occupancy": paired_numbers(_column(group, "outside_real"), _column(group, "outside_pseudo")),
            "outward_excursion": paired_numbers(
                _column(group, "excursion_real"), _column(group, "excursion_pseudo")
            ),
            "role": "EXPLORATORY_POST_OUTCOME_DESCRIPTIVE_BIN",
        }
    return out


def _conditional_excursion(rows: list[dict], arm: str) -> dict:
    labels = {
        "extension_first": [
            row for row in rows if row[f"extension_first_{arm}"] == 1.0
        ],
        "resolved_not_extension_first": [
            row
            for row in rows
            if row[f"resolution_{arm}"] == 1.0 and row[f"extension_first_{arm}"] == 0.0
        ],
        "unresolved": [row for row in rows if row[f"resolution_{arm}"] == 0.0],
    }
    out = {}
    for name, group in labels.items():
        exc = _column(group, f"excursion_{arm}")
        both = sum(1 for row in group if row[f"both_{arm}"])
        out[name] = {
            "n": len(group),
            "share": len(group) / len(rows) if rows else None,
            "both_barriers_on_first_hit": both,
            "excursion": quantiles(exc),
        }
    return out


def _shape(rows: list[dict]) -> dict:
    out = {"role": "DESCRIPTIVE_SHAPE_NOT_A_TEST", "threshold_share": {}}
    for arm in ("real", "pseudo"):
        exc = np.asarray(_column(rows, f"excursion_{arm}"), dtype=np.float64)
        out["threshold_share"][arm] = {
            str(mark): float(np.mean(exc >= mark)) for mark in EXCURSION_SHAPE_MARKS
        }
        times = [
            (row[f"first_barrier_bar_{arm}"] + 1) * 5
            for row in rows
            if row[f"first_barrier_bar_{arm}"] is not None
        ]
        out.setdefault("minutes_to_first_barrier_among_resolved", {})[arm] = quantiles(times)
    out["quantiles"] = {
        "real": quantiles(_column(rows, "excursion_real")),
        "pseudo": quantiles(_column(rows, "excursion_pseudo")),
    }
    out["conditional_on_own_first_event"] = {
        "real": _conditional_excursion(rows, "real"),
        "pseudo": _conditional_excursion(rows, "pseudo"),
    }
    focused = [row for row in rows if row["extension_first_real"] == 1.0]
    out["when_real_is_extension_first"] = {
        "n": len(focused),
        "excursion": paired_numbers(_column(focused, "excursion_real"), _column(focused, "excursion_pseudo")),
        "share_real_excursion_below_pseudo": float(
            np.mean(
                [
                    row["excursion_real"] < row["excursion_pseudo"]
                    for row in focused
                ]
            )
        )
        if focused
        else None,
    }
    return out


def _partner_summary(rows: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for row in rows:
        counts[str(row["partner_year"])] = counts.get(str(row["partner_year"]), 0) + 1
    n = len(rows)
    return {
        "lag_days": quantiles(_column(rows, "partner_lag_days")),
        "absolute_lag_days": quantiles([abs(row["partner_lag_days"]) for row in rows]),
        "partner_year_share": {year: counts[year] / n for year in sorted(counts)},
    }


def _enrich(name: str, offset: int, pairs: list, scored: list, high, low, close, t0: int, partners: dict) -> list[dict]:
    rows = []
    for pair, score in zip(pairs, scored):
        active = recover_active_start(pair["real_index"], offset)
        form = active - K.FORMATION_BARS
        decision = active - 1
        formed_high = float(np.max(high[form:active]))
        formed_low = float(np.min(low[form:active]))
        if abs(formed_high - float(pair["real_high"])) > 1e-6 or abs(formed_low - float(pair["real_low"])) > 1e-6:
            raise RuntimeError(f"{name} recovered formation does not match the frozen pair")
        p0 = float(close[decision])
        real_high = float(pair["real_high"])
        real_low = float(pair["real_low"])
        pseudo_high = float(pair["pseudo_high"])
        pseudo_low = float(pair["pseudo_low"])
        if not (real_low < p0 < real_high and pseudo_low < p0 < pseudo_high):
            raise RuntimeError(f"{name} decision close is not inside both ranges")
        partner = partners.get(pair["real_index"])
        if partner is None:
            raise RuntimeError(f"{name} frozen pair has no recovered partner day")
        if abs(partner["pseudo_high"] - pseudo_high) > 1e-6 or abs(partner["pseudo_low"] - pseudo_low) > 1e-6:
            raise RuntimeError(f"{name} recovered pseudo bounds do not match the frozen pair")
        day_index = form // K.BARS_PER_DAY
        if form != day_index * K.BARS_PER_DAY + offset:
            raise RuntimeError(f"{name} formation is not on the frozen hour")
        day_ms = t0 + day_index * K.DAY_MS
        stamp = dt.datetime.fromtimestamp(day_ms / 1000.0, tz=UTC)
        if stamp.year != int(pair["year"]):
            raise RuntimeError(f"{name} recovered year does not match the frozen pair")
        real_detail = barrier_detail(
            _window(high, pair["real_index"]),
            _window(low, pair["real_index"]),
            real_high,
            real_low,
            pair["real_side"],
        )
        pseudo_detail = barrier_detail(
            _window(high, pair["pseudo_index"]),
            _window(low, pair["pseudo_index"]),
            pseudo_high,
            pseudo_low,
            pair["pseudo_side"],
        )
        if real_detail["resolution"] != score["resolution_real"] or pseudo_detail["resolution"] != score["resolution_pseudo"]:
            raise RuntimeError(f"{name} diagnosis score drifted from the official scorer")
        if abs(real_detail["outward_excursion"] - score["outward_excursion_real"]) > 1e-12:
            raise RuntimeError(f"{name} excursion drifted from the official scorer")
        u_real = math.log(real_high / p0)
        d_real = math.log(p0 / real_low)
        u_pseudo = math.log(pseudo_high / p0)
        d_pseudo = math.log(p0 / pseudo_low)
        width_real = real_high - real_low
        width_pseudo = pseudo_high - pseudo_low
        post_high = high[active:active + K.HORIZON_BARS]
        post_low = low[active:active + K.HORIZON_BARS]
        if post_high.shape[0] == K.HORIZON_BARS and np.all(np.isfinite(post_high)) and np.all(np.isfinite(post_low)):
            post_range = float((np.max(post_high) - np.min(post_low)) / p0)
        else:
            post_range = None
        year = int(pair["year"])
        rows.append({
            "year": year,
            "month": f"{stamp.year:04d}-{stamp.month:02d}",
            "half": f"{year}H1" if stamp.month <= 6 else f"{year}H2",
            "block": "EARLY_2020_2022" if year in EARLY_YEARS else "LATE_2023_2024",
            "resolution_real": float(score["resolution_real"]),
            "resolution_pseudo": float(score["resolution_pseudo"]),
            "extension_first_real": float(score["extension_first_real"]),
            "extension_first_pseudo": float(score["extension_first_pseudo"]),
            "outside_real": float(score["outside_share_real"]),
            "outside_pseudo": float(score["outside_share_pseudo"]),
            "excursion_real": float(score["outward_excursion_real"]),
            "excursion_pseudo": float(score["outward_excursion_pseudo"]),
            "both_real": bool(score["both_barriers_real"]),
            "both_pseudo": bool(score["both_barriers_pseudo"]),
            "first_barrier_bar_real": real_detail["first_barrier_bar"],
            "first_barrier_bar_pseudo": pseudo_detail["first_barrier_bar"],
            "width_real": width_real,
            "width_pseudo": width_pseudo,
            "width_ratio": width_real / width_pseudo,
            "width_bin": width_bin(width_real / width_pseudo),
            "relative_width_real": width_real / p0,
            "relative_width_pseudo": width_pseudo / p0,
            "u_real": u_real,
            "d_real": d_real,
            "u_pseudo": u_pseudo,
            "d_pseudo": d_pseudo,
            "asymmetry_real": (u_real - d_real) / (u_real + d_real),
            "asymmetry_pseudo": (u_pseudo - d_pseudo) / (u_pseudo + d_pseudo),
            "pre_rv": realized_vol(close, form - K.FORMATION_BARS, K.FORMATION_BARS - 1),
            "post_decision_rv": realized_vol(close, decision, K.HORIZON_BARS),
            "post_decision_range": post_range,
            "post_touch_rv_real": realized_vol(close, pair["real_index"], K.HORIZON_BARS),
            "post_touch_rv_pseudo": realized_vol(close, pair["pseudo_index"], K.HORIZON_BARS),
            "latency_real": (pair["real_index"] - active) * 5,
            "latency_pseudo": (pair["pseudo_index"] - active) * 5,
            "immediate_real": float(pair["real_index"] == active),
            "immediate_pseudo": float(pair["pseudo_index"] == active),
            "side_real": pair["real_side"],
            "side_pseudo": pair["pseudo_side"],
            "partner_lag_days": float(partner["lag_days"]),
            "partner_year": int(partner["partner_year"]),
        })
    return rows


def _by_key(rows: list[dict], key: str, expected: tuple) -> dict:
    grouped = {name: [] for name in expected}
    for row in rows:
        grouped[row[key]].append(row)
    return {str(name): _slice(group) for name, group in grouped.items() if group}


def _monthly(rows: list[dict]) -> list[dict]:
    grouped: dict[str, list] = {}
    for row in rows:
        grouped.setdefault(row["month"], []).append(row)
    out = []
    for month in sorted(grouped):
        group = grouped[month]
        numbers = paired_numbers(_column(group, "resolution_real"), _column(group, "resolution_pseudo"))
        out.append({"month": month, **numbers})
    return out


def _contribution(rows: list[dict]) -> dict:
    pooled = paired_numbers(_column(rows, "resolution_real"), _column(rows, "resolution_pseudo"))
    parts = {}
    for year in YEARS:
        group = [row for row in rows if row["year"] == year]
        numbers = paired_numbers(_column(group, "resolution_real"), _column(group, "resolution_pseudo"))
        weight = numbers["n"] / pooled["n"]
        contribution = weight * numbers["delta"]
        parts[str(year)] = {
            **numbers,
            "weight": weight,
            "contribution_to_pooled_delta": contribution,
            "share_of_pooled_delta": contribution / pooled["delta"] if pooled["delta"] else None,
        }
    return {"pooled": pooled, "by_year": parts, "role": "ACCOUNTING_IDENTITY_NOT_A_YEAR_TEST"}


def _assert_official(cell: str, rows: list[dict], official: dict) -> None:
    numbers = paired_numbers(_column(rows, "resolution_real"), _column(rows, "resolution_pseudo"))
    found = official["foundation"][cell]
    if numbers["n"] != found["n_pairs"]:
        raise RuntimeError(f"{cell} pair count drifted from the official result")
    if abs(numbers["delta"] - found["paired_delta"]) > 1e-12:
        raise RuntimeError(f"{cell} foundation delta drifted from the official result")
    if abs(numbers["real"] - found["real_resolution_rate"]) > 1e-12:
        raise RuntimeError(f"{cell} real rate drifted from the official result")
    if abs(numbers["pseudo"] - found["pseudo_resolution_rate"]) > 1e-12:
        raise RuntimeError(f"{cell} pseudo rate drifted from the official result")
    for year, item in official["stability"][cell]["calendar_year"].items():
        group = [row for row in rows if str(row["year"]) == year]
        got = paired_numbers(_column(group, "resolution_real"), _column(group, "resolution_pseudo"))
        if got["n"] != item["n_pairs"] or abs(got["delta"] - item["paired_effect"]) > 1e-12:
            raise RuntimeError(f"{cell} {year} drifted from the official stability table")


def _svg(path: Path, panels: list[dict], title: str, y_label: str, y0: float, y1: float) -> None:
    width = 980
    height = 560
    pad_l, pad_r, pad_t, pad_b = 58, 16, 42, 36
    cols = 2
    rows_n = 2
    gap = 18
    panel_w = (width - pad_l - pad_r - gap) / cols
    panel_h = (height - pad_t - pad_b - gap) / rows_n
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#fbfaf6"/>',
        f'<text x="{pad_l}" y="24" font-family="sans-serif" font-size="16" fill="#1c1917">{_esc(title)}</text>',
    ]
    for i, panel in enumerate(panels):
        col = i % cols
        row = i // cols
        x0 = pad_l + col * (panel_w + gap)
        y_top = pad_t + row * (panel_h + gap)
        parts.append(
            f'<text x="{x0:.1f}" y="{y_top + 14:.1f}" font-family="sans-serif" font-size="13" fill="#1c1917">{_esc(panel["title"])}</text>'
        )
        plot_top = y_top + 22
        plot_h = panel_h - 48
        plot_w = panel_w - 8
        parts.append(
            f'<rect x="{x0:.1f}" y="{plot_top:.1f}" width="{plot_w:.1f}" height="{plot_h:.1f}" fill="#fff" stroke="#d6d3d1"/>'
        )
        labels = panel["labels"]
        for tick, label in ((0.0, f"{y0:g}"), (0.5, f"{(y0 + y1) / 2:g}"), (1.0, f"{y1:g}")):
            yy = plot_top + (1.0 - tick) * plot_h
            parts.append(f'<line x1="{x0:.1f}" y1="{yy:.1f}" x2="{x0 + plot_w:.1f}" y2="{yy:.1f}" stroke="#e7e5e4"/>')
            parts.append(
                f'<text x="{x0 - 6:.1f}" y="{yy + 3:.1f}" text-anchor="end" font-family="sans-serif" font-size="10" fill="#57534e">{label}</text>'
            )
        for series in panel["series"]:
            coords = []
            for j, value in enumerate(series["values"]):
                if value is None:
                    continue
                xx = x0 + (j + 0.5) * plot_w / max(1, len(labels))
                yy = plot_top + (1.0 - (value - y0) / (y1 - y0)) * plot_h
                coords.append(f"{xx:.1f},{yy:.1f}")
            if len(coords) >= 2:
                parts.append(
                    f'<polyline fill="none" stroke="{series["color"]}" stroke-width="2" points="{" ".join(coords)}"/>'
                )
        for j, label in enumerate(labels):
            if j % panel.get("label_every", 1) != 0:
                continue
            xx = x0 + (j + 0.5) * plot_w / max(1, len(labels))
            parts.append(
                f'<text x="{xx:.1f}" y="{plot_top + plot_h + 14:.1f}" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#57534e">{_esc(label)}</text>'
            )
        legend = "  ".join(series["name"] for series in panel["series"])
        parts.append(
            f'<text x="{x0:.1f}" y="{y_top + panel_h - 4:.1f}" font-family="sans-serif" font-size="10" fill="#57534e">{_esc(legend)} · {_esc(y_label)}</text>'
        )
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _charts(payload: dict) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    cells = list(K.CLOCK_CELLS)
    rate_panels = []
    width_panels = []
    ratio_panels = []
    for cell in cells:
        years = payload["by_cell"][cell]["by_year"]
        labels = [str(year) for year in YEARS]
        rate_panels.append({
            "title": cell,
            "labels": labels,
            "series": [
                {"name": "real", "color": "#1f4e79", "values": [years[label]["path"]["resolution"]["real"] for label in labels]},
                {"name": "pseudo", "color": "#b85c38", "values": [years[label]["path"]["resolution"]["pseudo"] for label in labels]},
            ],
        })
        width_panels.append({
            "title": cell,
            "labels": labels,
            "series": [
                {
                    "name": "real W/P0",
                    "color": "#1f4e79",
                    "values": [years[label]["geometry"]["real"]["relative_width"]["p50"] for label in labels],
                },
                {
                    "name": "pseudo W/P0",
                    "color": "#b85c38",
                    "values": [years[label]["geometry"]["pseudo"]["relative_width"]["p50"] for label in labels],
                },
            ],
        })
        ratio_panels.append({
            "title": cell,
            "labels": labels,
            "series": [
                {
                    "name": "median W_real/W_pseudo",
                    "color": "#2f6f4e",
                    "values": [years[label]["mismatch"]["width_ratio"]["p50"] for label in labels],
                }
            ],
        })
    _svg(
        FIG_DIR / "yearly_resolution_rates.svg",
        rate_panels,
        "FROZEN_HOUR_RANGE resolution rate by year — descriptive, not a test",
        "resolution rate",
        0.45,
        1.0,
    )
    _svg(
        FIG_DIR / "yearly_relative_width.svg",
        width_panels,
        "Median relative width W/P0 by year — descriptive",
        "median W/P0",
        0.0,
        0.04,
    )
    _svg(
        FIG_DIR / "yearly_width_ratio.svg",
        ratio_panels,
        "Median W_real / W_pseudo by year — descriptive",
        "width ratio",
        0.2,
        3.2,
    )
    month_labels = [item["month"] for item in payload["by_cell"]["UTC_00"]["monthly_resolution"]]
    month_panels = []
    for cell in cells:
        series = payload["by_cell"][cell]["monthly_resolution"]
        month_panels.append({
            "title": cell,
            "labels": [item["month"][2:7] for item in series],
            "label_every": 6,
            "series": [
                {"name": "paired delta", "color": "#1f4e79", "values": [item["delta"] for item in series]},
            ],
        })
    _svg(
        FIG_DIR / "monthly_resolution_delta.svg",
        month_panels,
        "Monthly paired resolution delta — descriptive smoothness, not a breakpoint",
        "real minus pseudo",
        -0.5,
        0.8,
    )
    if [item["month"] for item in payload["by_cell"]["UTC_00"]["monthly_resolution"]] != month_labels:
        raise RuntimeError("monthly labels drifted")


def _clean(value):
    if isinstance(value, dict):
        return {str(key): _clean(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clean(item) for item in value]
    if isinstance(value, tuple):
        return [_clean(item) for item in value]
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_payload() -> dict:
    before = {path.name: _sha256(path) for path in (RESULT_JSON, RESULT_MD)}
    official = json.loads(RESULT_JSON.read_text(encoding="utf-8"))
    if official["route"] != OFFICIAL_ROUTE:
        raise RuntimeError("official route is not the published route")
    bars = load_discovery_bars()
    if int(bars.n) != official["panel_bars"] or int(bars.t0) != official["panel_t0_ms"]:
        raise RuntimeError("diagnosis panel is not the official panel")
    found = collect_pairs(bars.high, bars.low, bars.close, int(bars.t0))
    by_cell = {}
    for name, offset in K.ANCHORS.items():
        scored = score_pairs(bars.high, bars.low, found[name]["pairs"])
        partners = partner_table(bars.high, bars.low, bars.close, int(bars.t0), offset)
        rows = _enrich(
            name, offset, found[name]["pairs"], scored, bars.high, bars.low, bars.close, int(bars.t0), partners
        )
        _assert_official(name, rows, official)
        halves = tuple(f"{year}H{half}" for year in YEARS for half in (1, 2))
        by_cell[name] = {
            "all": _slice(rows),
            "by_year": _by_key(rows, "year", YEARS),
            "by_half": _by_key(rows, "half", halves),
            "by_block": _by_key(rows, "block", ("EARLY_2020_2022", "LATE_2023_2024")),
            "monthly_resolution": _monthly(rows),
            "contribution": _contribution(rows),
            "excursion_shape": _shape(rows),
        }
    after = {path.name: _sha256(path) for path in (RESULT_JSON, RESULT_MD)}
    if after != before:
        raise RuntimeError("diagnosis rewrote an official result file")
    return {
        "mode": "POST_OUTCOME_DIAGNOSIS",
        "evidence_upgrade": "NONE",
        "original_result_unchanged": True,
        "confirmation": False,
        "product_change": "none",
        "official_route_unchanged": OFFICIAL_ROUTE,
        "claim_ceiling_unchanged": "L2",
        "surface": K.SURFACE_ID,
        "window": "[2020-01-01, 2025-01-01)",
        "new_surface_opened": False,
        "successor_started": False,
        "official_result_sha256": before[RESULT_JSON.name],
        "official_result_md_sha256": before[RESULT_MD.name],
        "parity_with_official_result": True,
        "definitions": {
            "relative_width": "W / P0, P0 = close of the last formation bar, the same close the pseudo bounds are placed on",
            "asymmetry": "(u - d) / (u + d), u = log(high/P0), d = log(P0/low)",
            "pre_formation_rv": "sqrt of summed squared 5m log returns across the 12 closes immediately before formation (11 returns)",
            "post_decision_rv": "sqrt of summed squared 5m log returns from the decision close across the next 48 returns (4h)",
            "post_touch_rv": "sqrt of summed squared 5m log returns from the touch-bar close across the next 48 returns",
            "width_bins": "PSEUDO_WIDER if W_real/W_pseudo < 0.8; SIMILAR if 0.8 to 1.25 inclusive; else REAL_WIDER. Round reciprocal cuts, not a searched match.",
            "partner_lag": "Calendar days from the object day to the weekday half-rotation partner that supplied u and d. The frozen match is not changed.",
            "equal_width_line": "EXPLORATORY_POST_OUTCOME linear description. Intercept is the fitted paired resolution difference at log width ratio 0. Not a control and not a claim.",
            "blocks": "EARLY is 2020-2022 and LATE is 2023-2024, the split already visible in the published year table. Not a new threshold.",
            "wald_interval": "Paired mean plus or minus 1.96 sample standard errors. Descriptive. Not a family test and not a pass/fail.",
            "excursion_marks": "Shares at 0.5W, 1.0W and 1.5W are shape descriptions, not candidate tests.",
        },
        "by_cell": by_cell,
    }


def main() -> None:
    payload = _clean(build_payload())
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _charts(payload)
    print(f"wrote {OUT_JSON}")
    print(f"wrote {FIG_DIR}")


if __name__ == "__main__":
    main()
