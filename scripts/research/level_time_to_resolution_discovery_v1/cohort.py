"""Outcome-blind first-touch pairing. Does not read a barrier time."""

from __future__ import annotations

from scripts.research.level_first_touch_resolution_confirmation_v1.cohort import (
    first_touch_status,
    iter_episode_links,
)
from scripts.research.level_touch_degradation_v1.build import build_population
from scripts.research.level_touch_degradation_v1 import constants as PARENT

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
        "matched_pairs": len(pairs),
        "incomplete_4h_real": real_counts["INCOMPLETE_4H"],
        "incomplete_4h_pseudo": pseudo_counts["INCOMPLETE_4H"],
        "slices": _slices(pairs),
        "pairs": pairs,
    }


def _pair(episode: dict, real: dict, pseudo: dict) -> dict:
    side = int(real["side"])
    return {
        "episode_id": episode["episode_id"],
        "family": episode["family"],
        "year": int(real["year"]),
        "week": int(real["week"]),
        "side_name": "resistance" if side > 0 else "support",
        "real": real,
        "pseudo": pseudo,
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
    weeks = len({int(pair["week"]) for pair in pairs})
    return {"year": year, "family": family, "side": side, "other_year": other_year, "weeks": weeks}
