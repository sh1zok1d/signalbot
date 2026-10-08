"""Matched first touches. First-event labels use the parent classifier only."""

from __future__ import annotations

from scripts.research.level_first_touch_resolution_confirmation_v1.cohort import (
    first_touch_status,
    iter_episode_links,
)
from scripts.research.level_touch_degradation_v1.build import build_population
from scripts.research.level_touch_degradation_v1 import constants as PARENT
from scripts.research.level_touch_degradation_v1.outcomes import classify

from . import constants as K


def assemble(bars) -> dict:
    population = build_population(bars, PARENT.ZONE_HALF_PRIMARY)
    keys = (
        "NO_TOUCH", "OUTSIDE_WINDOW", "INCOMPLETE_4H", "UNKNOWN_SIDE", "UNUSABLE_X", "LEGITIMATE",
    )
    real_counts = {name: 0 for name in keys}
    pseudo_counts = {name: 0 for name in keys}
    pseudo_counts["NO_CONTROL"] = 0
    pairs = []
    for episode, real, ctrl, pseudo in iter_episode_links(population):
        real_status = first_touch_status(
            real, event_start_ms=K.EVENT_START_MS, event_end_ms=K.EVENT_END_MS,
        )
        if real_status not in real_counts:
            real_status = "NO_TOUCH"
        real_counts[real_status] += 1
        if ctrl is None:
            pseudo_counts["NO_CONTROL"] += 1
            pseudo_status = "NO_CONTROL"
        else:
            pseudo_status = first_touch_status(
                pseudo, event_start_ms=K.EVENT_START_MS, event_end_ms=K.EVENT_END_MS,
            )
            if pseudo_status not in pseudo_counts:
                pseudo_status = "NO_TOUCH"
            pseudo_counts[pseudo_status] += 1
        if real_status == "LEGITIMATE" and pseudo_status == "LEGITIMATE":
            pairs.append(_pair(episode, real, pseudo))
    return {
        "structural_episodes": len(population["episodes"]),
        "real_status": real_counts,
        "pseudo_status": pseudo_counts,
        "real_legitimate": real_counts["LEGITIMATE"],
        "pseudo_legitimate": pseudo_counts["LEGITIMATE"],
        "incomplete_4h_real": real_counts["INCOMPLETE_4H"],
        "incomplete_4h_pseudo": pseudo_counts["INCOMPLETE_4H"],
        "matched_pairs": len(pairs),
        "slices": _slices(pairs),
        "pairs": pairs,
    }


def _slices(pairs: list[dict]) -> dict:
    year = {str(y): 0 for y in K.YEARS}
    family = {name: 0 for name in K.FAMILIES}
    side = {"resistance": 0, "support": 0}
    other_year = 0
    for pair in pairs:
        key = str(pair["year"])
        if key in year:
            year[key] += 1
        else:
            other_year += 1
        family[pair["family"]] = family.get(pair["family"], 0) + 1
        side[pair["side_name"]] += 1
    return {
        "year": year,
        "family": family,
        "side": side,
        "other_year": other_year,
        "weeks": len({int(pair["week"]) for pair in pairs}),
    }


def _pair(episode: dict, real: dict, pseudo: dict) -> dict:
    side = int(real["side"])
    return {
        "family": episode["family"],
        "year": int(real["year"]),
        "week": int(real["week"]),
        "side_name": "resistance" if side > 0 else "support",
        "real": real,
        "pseudo": pseudo,
    }


def first_event_counts(bars, pairs: list[dict]) -> dict:
    """Parent BREAK/REJECT/NEITHER/AMBIGUOUS counts. No opposite-barrier scan."""
    labels = ("BREAK", "REJECT", "AMBIGUOUS", "NEITHER", "UNUSABLE")
    real = {name: 0 for name in labels}
    pseudo = {name: 0 for name in labels}
    for pair in pairs:
        for arm, bucket in (("real", real), ("pseudo", pseudo)):
            touch = pair[arm]
            label = classify(
                bars.high, bars.low, int(touch["j"]), int(touch["side"]),
                float(touch["zone_low"]), float(touch["zone_high"]),
                float(touch["x_primary"]), K.HORIZON_BARS,
            )
            bucket[label if label in bucket else "UNUSABLE"] += 1
    return {"real": real, "pseudo": pseudo}


def gate_from_counts(counts: dict) -> dict:
    real, pseudo = counts["real"], counts["pseudo"]
    p1 = real["BREAK"] >= K.DENOM_GATE and pseudo["BREAK"] >= K.DENOM_GATE
    p2 = real["REJECT"] >= K.DENOM_GATE and pseudo["REJECT"] >= K.DENOM_GATE
    return {"P1": p1, "P2": p2}
