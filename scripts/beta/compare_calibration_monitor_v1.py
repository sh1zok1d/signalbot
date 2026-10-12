"""Shared-path check of calibration monitor V2 against the live V1 bin rule.

One Gaussian path per seed. A claim issued at hour t with horizon H is settled by the
sum of the next H hourly increments. The stated null probability is the exact Gaussian
tail or central probability of that sum, so overlapping 1h, 4h and 24h claims are
dependent and, under the null, each is calibrated at its own issue time. This is a
terminal barrier, not a path-maximum touch: the point is the shared path, and the
conditional probability has to be exact.

The monitor's decision statistic keeps only non-overlapping anchor hours. The script
also walks the same 4h touch residuals in issue order, one step per hour, which is the
filtration the daily e-process was using. Thresholds are imported from the monitor and
are not written here. Nothing is fit to October 2026.

Run: python3 scripts/beta/compare_calibration_monitor_v1.py
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import NormalDist

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import numpy as np

from beta import claims as claims
from beta.calibration_monitor import (
    E_CONFIRM, HORIZON_SECONDS, PRACTICAL_ABS, PROCEDURE_TOUCH_CHANCE, STATE_CONFIRMED,
    STATE_INSUFFICIENT, STATE_RECOVERED, STATE_SUSPECTED, VARIANTS_TRIED_FOR_THRESHOLDS,
    evaluate, mixture_peak,
)

UTC = timezone.utc
START = datetime(2023, 1, 1, tzinfo=UTC)
OUT = Path(__file__).resolve().parents[2] / "docs" / "BETA_CALIBRATION_MONITOR_V2_COMPARISON.json"
NORMAL = NormalDist()
TOUCH_P = (0.08, 0.18, 0.25, 0.40, 0.48, 0.62, 0.74, 0.88)
NEITHER_P = (0.20, 0.35, 0.55, 0.72, 0.78, 0.84, 0.91, 0.40)
HORIZON_HOURS = {"1h": 1, "4h": 4, "24h": 24}
NULL_PATHS = 36
NULL_DAYS = 80
V1_PATHS = 8
V1_DAYS = 56
WINDOW_DAYS = 7
WINDOW_STARTS = (0, 7, 14, 21, 28, 35)
POWER_PATHS = 3
POWER_DAYS = 70
RECOVERY_DAYS = 36


def _clip(probability: float) -> float:
    return float(min(0.98, max(0.02, probability)))


def _stated(kind: str, probability: float) -> float:
    if kind == "null":
        return probability
    if kind == "level":
        return _clip(probability - 0.10)
    if kind == "tail":
        if probability >= 0.70:
            return _clip(probability + 0.12)
        if probability < 0.30:
            return _clip(probability - 0.12)
        return probability
    if kind == "shape":
        return _clip(0.5 + 1.4 * (probability - 0.5))
    raise ValueError(kind)


def _touch_hit(future: float, probability: float, hours: int) -> float:
    barrier = math.sqrt(hours) * NORMAL.inv_cdf(1.0 - probability)
    return 1.0 if future >= barrier else 0.0


def _neither_hit(future: float, probability: float, hours: int) -> float:
    barrier = math.sqrt(hours) * NORMAL.inv_cdf((1.0 + probability) / 2.0)
    return 1.0 if abs(future) < barrier else 0.0


def build_path(days: int, *, seed: int, touch_kind: str = "null", neither_kind: str = "null",
               recover_touch_after: int | None = None) -> tuple:
    """Hourly claims on one path. Returns rows and the 4h touch level sequences."""
    rng = np.random.default_rng(seed)
    increments = rng.normal(0.0, 1.0, size=days * 24 + 24)
    rows = []
    hourly = []
    hourly_days = []
    anchor = []
    anchor_days = []
    for hour in range(days * 24):
        moment = START + timedelta(hours=hour)
        day = hour // 24
        kind_touch = "null" if recover_touch_after is not None and day >= recover_touch_after else touch_kind
        hour_residuals = []
        for horizon, hours in HORIZON_HOURS.items():
            future = float(increments[hour:hour + hours].sum())
            for probability in TOUCH_P:
                stated = _stated(kind_touch, probability)
                outcome = _touch_hit(future, probability, hours)
                rows.append({
                    "procedure_id": PROCEDURE_TOUCH_CHANCE, "family": "touch", "horizon": horizon,
                    "as_of": moment, "probability": stated, "outcome": outcome,
                    "status": "COMPLETE", "eval_rule_id": "TOUCH_V1",
                    "snapshot_id": f"snap-{day // 14}",
                })
                if horizon == "4h":
                    hour_residuals.append(outcome - stated)
            for probability in NEITHER_P:
                stated = _stated(neither_kind, probability)
                outcome = _neither_hit(future, probability, hours)
                rows.append({
                    "procedure_id": PROCEDURE_TOUCH_CHANCE, "family": "neither", "horizon": horizon,
                    "as_of": moment, "probability": stated, "outcome": outcome,
                    "status": "COMPLETE", "eval_rule_id": "NEITHER_V1",
                    "snapshot_id": f"snap-{day // 14}",
                })
        statistic = sum(hour_residuals) / len(hour_residuals)
        hourly.append(statistic)
        hourly_days.append(day)
        if hour % 4 == 0:
            anchor.append(statistic)
            anchor_days.append(day)
    return rows, hourly, hourly_days, anchor, anchor_days


def _cells(rows, family: str) -> list:
    pooled: dict = {}
    classes = ("L3_DISTANCE_TOUCH_4H",) if family == "touch" else ("L3_NEITHER_4H",)
    for row in rows:
        if row["family"] != family or row["horizon"] != "4h":
            continue
        day = int(row["as_of"].timestamp()) // 86400
        slot = int(row["as_of"].timestamp()) // 14400
        probability = row["probability"]
        bin_index = sum(probability >= edge for edge in (0.05, 0.15, 0.3, 0.5, 0.7, 0.85))
        key = (classes[0], bin_index, day, slot)
        cell = pooled.setdefault(key, {"claim_class": classes[0], "bin": bin_index, "day": day,
                                       "slot": slot, "n": 0, "hits": 0, "psum": 0.0})
        cell["n"] += 1
        cell["hits"] += int(row["outcome"])
        cell["psum"] += probability
    return list(pooled.values())


def v1_flags(rows) -> dict:
    out = {}
    for family, kind in (("touch", "touch"), ("neither", "neither")):
        bins = claims.live_touch_bins(_cells(rows, family), "4h", kind=kind)
        out[family] = claims.diverged_bins(bins)
    return out


def _slice(rows, start_day: int, length: int) -> list:
    begin = START + timedelta(days=start_day)
    end = begin + timedelta(days=length)
    return [row for row in rows if begin <= row["as_of"] < end]


def book_map(rows) -> dict:
    report = evaluate(rows)
    return {(item["family"], item["horizon"]): item for item in report["books"]}


def _ever_confirmed(book: dict) -> bool:
    return bool(book.get("episodes")) or book["state"] == STATE_CONFIRMED


def clopper_pearson_upper(successes: int, trials: int, alpha: float = 0.05) -> float:
    """One-sided upper 95% Clopper-Pearson bound on a binomial rate."""
    if trials <= 0:
        return 1.0
    if successes >= trials:
        return 1.0
    lo, hi = 0.0, 1.0
    for _ in range(80):
        mid = (lo + hi) / 2.0
        # P(K <= successes | p=mid). The upper bound is where this equals alpha.
        probability = sum(math.comb(trials, index) * mid ** index * (1.0 - mid) ** (trials - index)
                          for index in range(successes + 1))
        if probability > alpha:
            lo = mid
        else:
            hi = mid
    return hi


def level_walk(statistics, days) -> dict:
    """LEVEL-only book mixture, other channels held at 1. Diagnostic, not the monitor."""
    from beta.calibration_monitor import _mix_e, _update

    logs = [0.0, 0.0, 0.0, 0.0]
    total = 0.0
    seen = set()
    sup_book = 1.0
    confirmed = False
    for index, statistic in enumerate(statistics):
        _update(logs, statistic)
        total += statistic
        seen.add(days[index])
        book = (_mix_e(logs) + 3.0) / 4.0
        sup_book = max(sup_book, book)
        mean = total / (index + 1)
        if len(seen) >= 20 and book >= E_CONFIRM and abs(mean) > PRACTICAL_ABS:
            confirmed = True
    return {"sup_book_e": sup_book, "confirmed_level_only": confirmed,
            "peak_level_e": mixture_peak(statistics)}


def _quantile(values, q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    pos = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
    return float(ordered[pos])


def null_study() -> dict:
    joint_paths = 0
    joint_details = []
    anchor_level_confirmed = 0
    hourly_level_confirmed = 0
    anchor_sup = []
    hourly_sup = []
    included = []
    for seed in range(NULL_PATHS):
        rows, hourly, hourly_days, anchor, anchor_days = build_path(
            NULL_DAYS, seed=20261005 + seed)
        books = book_map(rows)
        path_hit = False
        for (family, horizon), book in books.items():
            if not _ever_confirmed(book):
                continue
            path_hit = True
            episode = book["episodes"][0]
            joint_details.append({
                "seed": 20261005 + seed,
                "family": family,
                "horizon": horizon,
                "e_at_confirm": episode.get("e_at_confirm"),
                "named_channels": episode.get("named_channels"),
            })
        joint_paths += int(path_hit)
        anchor_walk = level_walk(anchor, anchor_days)
        hourly_walk = level_walk(hourly, hourly_days)
        anchor_level_confirmed += int(anchor_walk["confirmed_level_only"])
        hourly_level_confirmed += int(hourly_walk["confirmed_level_only"])
        anchor_sup.append(anchor_walk["sup_book_e"])
        hourly_sup.append(hourly_walk["sup_book_e"])
        touch_4h = books[("touch", "4h")]
        included.append(touch_4h["n_included_slots"])
    return {
        "paths": NULL_PATHS,
        "days": NULL_DAYS,
        "books_per_path": 6,
        "paths_with_any_book_ever_confirmed": joint_paths,
        "joint_confirmations": joint_details,
        "joint_rate": joint_paths / NULL_PATHS,
        "joint_clopper_pearson_upper_95": clopper_pearson_upper(joint_paths, NULL_PATHS),
        "ville_union_bound": 0.10,
        "anchor_level_only_paths_confirmed": anchor_level_confirmed,
        "hourly_overlapping_level_only_paths_confirmed": hourly_level_confirmed,
        "anchor_level_sup_book_e_median": _quantile(anchor_sup, 0.50),
        "anchor_level_sup_book_e_max": max(anchor_sup),
        "hourly_overlapping_sup_book_e_median": _quantile(hourly_sup, 0.50),
        "hourly_overlapping_sup_book_e_max": max(hourly_sup),
        "touch_4h_included_slots_min": min(included),
        "touch_4h_included_slots_max": max(included),
        "expected_4h_anchors": NULL_DAYS * 6,
    }


def v1_short_windows() -> dict:
    v1_hit = 0
    v2_not_insufficient = 0
    windows = 0
    for seed in range(V1_PATHS):
        rows, *_rest = build_path(V1_DAYS, seed=20261005 + 500 + seed)
        for start in WINDOW_STARTS:
            part = _slice(rows, start, WINDOW_DAYS)
            flags = v1_flags(part)
            if flags["touch"] or flags["neither"]:
                v1_hit += 1
            books = book_map(part)
            if any(book["state"] != STATE_INSUFFICIENT for book in books.values()):
                v2_not_insufficient += 1
            windows += 1
    return {
        "paths": V1_PATHS,
        "days": V1_DAYS,
        "window_days": WINDOW_DAYS,
        "windows": windows,
        "v1_windows_with_any_divergence": v1_hit,
        "v1_window_rate": v1_hit / windows,
        "v2_windows_not_insufficient": v2_not_insufficient,
    }


def _channel_brief(book: dict) -> dict:
    return {
        name: {"state": channel["state"], "estimate": channel.get("estimate")}
        for name, channel in book["channels"].items()
    }


def _power_case(touch_kind: str, neither_kind: str, *, seed: int, days: int = POWER_DAYS,
                recover_touch_after: int | None = None) -> dict:
    rows, *_rest = build_path(days, seed=seed, touch_kind=touch_kind, neither_kind=neither_kind,
                              recover_touch_after=recover_touch_after)
    books = book_map(rows)
    brief = {}
    for (family, horizon), book in sorted(books.items()):
        brief[f"{family}_{horizon}"] = {
            "state": book["state"],
            "e_value": book["e_value"],
            "n_days": book["n_days"],
            "n_included_slots": book["n_included_slots"],
            "channels": _channel_brief(book),
        }
    return brief


def power_study() -> dict:
    scenarios = {
        "level_minus_10pp": ("level", "null", None),
        "tail_pm_12pp": ("tail", "null", None),
        "shape_stretch": ("shape", "null", None),
        "neither_only_minus_10pp": ("null", "level", None),
        "level_bias_then_null_after_day_36": ("level", "null", RECOVERY_DAYS),
    }
    out = {}
    for name, (touch_kind, neither_kind, recover_after) in scenarios.items():
        days = 90 if recover_after is not None else POWER_DAYS
        runs = [
            _power_case(touch_kind, neither_kind, seed=20261005 + 800 + index,
                        days=days, recover_touch_after=recover_after)
            for index in range(POWER_PATHS)
        ]
        out[name] = {"days": days, "runs": runs}
    return out


def main() -> None:
    report = {
        "monitor": "CALIBRATION_MONITOR_V2",
        "surface": (
            "shared Gaussian path, terminal barrier, exact conditional null; "
            "not a market archive and not October 2026"
        ),
        "filtration": "NON_OVERLAPPING_ANCHOR",
        "variants_tried_for_thresholds": VARIANTS_TRIED_FOR_THRESHOLDS,
        "horizons_seconds": HORIZON_SECONDS,
        "null": null_study(),
        "v1_short_windows": v1_short_windows(),
        "power": power_study(),
    }
    OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "wrote": str(OUT),
        "null": report["null"],
        "v1_short_windows": report["v1_short_windows"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
