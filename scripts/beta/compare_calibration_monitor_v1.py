"""Synthetic comparison of the live V1 bin rule and calibration monitor V2.

The generator is a comonotonic null: one uniform draw per horizon slot, and every claim in
that slot is touched when the draw falls below its stated probability. Conditional on the
stated probability the outcome is calibrated, and claims that share a slot are one path.

Nothing here is Binance history and nothing is fit to the October 2026 alerts. Those alerts
are not an input. Thresholds live in beta.calibration_monitor and are not written by this script.

Run: python scripts/beta/compare_calibration_monitor_v1.py
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from beta import claims as claims
from beta.calibration_monitor import (
    PRACTICAL_ABS, PROCEDURE_TOUCH_CHANCE, STATE_CONFIRMED, STATE_INSUFFICIENT,
    STATE_SUSPECTED, evaluate,
)

UTC = timezone.utc
START = datetime(2023, 1, 1, tzinfo=UTC)
OUT = Path(__file__).resolve().parents[2] / "docs" / "BETA_CALIBRATION_MONITOR_V2_COMPARISON.json"
TOUCH_P = (0.08, 0.18, 0.25, 0.40, 0.48, 0.62, 0.74, 0.88)
NEITHER_P = (0.20, 0.35, 0.55, 0.72, 0.78, 0.84, 0.91, 0.40)
NULL_SEEDS = 20
NULL_DAYS = 56
WINDOW_DAYS = 7
WINDOW_STARTS = tuple(range(0, 40, 3))


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
    if kind == "neither":
        return probability
    raise ValueError(kind)


def build(days: int, *, seed: int, touch_kind: str, neither_kind: str,
          recover_after: int | None = None) -> list:
    """Hourly claims. `recover_after` switches both families to the null generator."""
    rng = np.random.default_rng(seed)
    rows = []
    for hour in range(days * 24):
        moment = START + timedelta(hours=hour)
        kind_touch = "null" if recover_after is not None and hour >= recover_after * 24 else touch_kind
        kind_neither = "null" if recover_after is not None and hour >= recover_after * 24 else neither_kind
        slot_draw = float(rng.random())
        for probability in TOUCH_P:
            stated = _stated(kind_touch, probability)
            rows.append({
                "procedure_id": PROCEDURE_TOUCH_CHANCE, "family": "touch", "horizon": "4h",
                "as_of": moment, "probability": stated, "outcome": 1.0 if slot_draw < probability else 0.0,
                "status": "COMPLETE", "eval_rule_id": "TOUCH_V1", "snapshot_id": f"snap-{hour // (14 * 24)}",
            })
        neither_draw = float(rng.random())
        for probability in NEITHER_P:
            stated = _stated("level" if kind_neither == "neither" else kind_neither, probability)
            rows.append({
                "procedure_id": PROCEDURE_TOUCH_CHANCE, "family": "neither", "horizon": "4h",
                "as_of": moment, "probability": stated,
                "outcome": 1.0 if neither_draw < probability else 0.0,
                "status": "COMPLETE", "eval_rule_id": "NEITHER_V1", "snapshot_id": f"snap-{hour // (14 * 24)}",
            })
    return rows


def _cells(rows, family: str) -> list:
    pooled: dict = {}
    classes = ("L3_DISTANCE_TOUCH_4H",) if family == "touch" else ("L3_NEITHER_4H",)
    for row in rows:
        if row["family"] != family:
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


def v2_books(rows) -> list:
    report = evaluate(rows)
    return [item for item in report["books"] if item["horizon"] == "4h"]


def v2_states(rows) -> dict:
    return {item["family"]: item["state"] for item in v2_books(rows)}


def _slice(rows, start_day: int, length: int) -> list:
    begin = START + timedelta(days=start_day)
    end = begin + timedelta(days=length)
    return [row for row in rows if begin <= row["as_of"] < end]


def _mean_residual(rows, family: str) -> float:
    chosen = [row for row in rows if row["family"] == family]
    if not chosen:
        return 0.0
    return sum(row["outcome"] - row["probability"] for row in chosen) / len(chosen)


def null_study() -> dict:
    v1_hit = 0
    v2_short_not_insufficient = 0
    v2_full_confirmed = 0
    v2_full_suspected = 0
    windows = 0
    for seed in range(NULL_SEEDS):
        rows = build(NULL_DAYS, seed=20261005 + seed, touch_kind="null", neither_kind="null")
        for start in WINDOW_STARTS:
            part = _slice(rows, start, WINDOW_DAYS)
            flags = v1_flags(part)
            if flags["touch"] or flags["neither"]:
                v1_hit += 1
            states = v2_states(part)
            if any(state != STATE_INSUFFICIENT for state in states.values()):
                v2_short_not_insufficient += 1
            windows += 1
        full = v2_states(rows)
        if STATE_CONFIRMED in full.values():
            v2_full_confirmed += 1
        if STATE_SUSPECTED in full.values():
            v2_full_suspected += 1
    return {
        "seeds": NULL_SEEDS,
        "days": NULL_DAYS,
        "windows": windows,
        "window_days": WINDOW_DAYS,
        "v1_windows_with_any_divergence": v1_hit,
        "v1_window_rate": v1_hit / windows,
        "v2_short_windows_not_insufficient": v2_short_not_insufficient,
        "v2_full_seeds_confirmed": v2_full_confirmed,
        "v2_full_seeds_suspected": v2_full_suspected,
    }


def _first_day(kind_touch: str, kind_neither: str, *, seed: int, days: int = 70,
               recover_after: int | None = None) -> dict:
    rows = build(days, seed=seed, touch_kind=kind_touch, neither_kind=kind_neither,
                 recover_after=recover_after)
    seen = {}
    for day in range(5, days + 1):
        states = v2_states(_slice(rows, 0, day))
        flags = v1_flags(_slice(rows, 0, day)) if day in (7, 14, 28, days) else None
        seen[day] = {"v2": states, "v1": flags}
    final_books = {item["family"]: item for item in v2_books(rows)}

    def earliest(family, state):
        for day, item in seen.items():
            if item["v2"].get(family) == state:
                return day
        return None
    return {
        "touch_mean_residual": _mean_residual(rows, "touch"),
        "neither_mean_residual": _mean_residual(rows, "neither"),
        "v2_touch_suspected_on": earliest("touch", STATE_SUSPECTED),
        "v2_touch_confirmed_on": earliest("touch", STATE_CONFIRMED),
        "v2_neither_confirmed_on": earliest("neither", STATE_CONFIRMED),
        "v1_touch_diverged_by_day_7": bool(seen[7]["v1"]["touch"]),
        "v1_touch_diverged_by_day_14": bool(seen[14]["v1"]["touch"]),
        "final_v2": seen[days]["v2"],
        "final_v1_touch": seen[days]["v1"]["touch"],
        "final_touch_channels": {
            name: {"state": channel["state"], "estimate": channel.get("estimate")}
            for name, channel in (final_books.get("touch") or {}).get("channels", {}).items()
        },
        "final_neither_channels": {
            name: {"state": channel["state"], "estimate": channel.get("estimate")}
            for name, channel in (final_books.get("neither") or {}).get("channels", {}).items()
        },
    }


def power_study() -> dict:
    scenarios = {
        "level_minus_10pp": ("level", "null"),
        "tail_pm_12pp": ("tail", "null"),
        "neither_only_minus_10pp": ("null", "neither"),
        "shape_stretch": ("shape", "null"),
    }
    out = {}
    for name, (touch_kind, neither_kind) in scenarios.items():
        runs = [_first_day(touch_kind, neither_kind, seed=20261005 + 100 + index) for index in range(3)]
        out[name] = {
            "runs": runs,
            "practical_gate": PRACTICAL_ABS,
        }
    recovery = _first_day("level", "null", seed=20261005 + 7, days=80, recover_after=36)
    out["level_bias_then_null_after_day_36"] = recovery
    return out


def main() -> None:
    report = {
        "monitor": "CALIBRATION_MONITOR_V2",
        "surface": "synthetic comonotonic slots, not a market archive and not October 2026",
        "variants_tried_for_thresholds": 0,
        "null": null_study(),
        "power": power_study(),
    }
    OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"wrote": str(OUT), "null": report["null"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
