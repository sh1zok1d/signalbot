"""Prospective structural episodes. Geometry only.

The real constructor is #352. An episode is eligible only when its active
period opens at or after the prospective start. A period that opened earlier
is dropped whole. It is not truncated.
"""

from __future__ import annotations

from scripts.research.level_touch_degradation_v1 import constants as PARENT
from scripts.research.level_touch_degradation_v1.events import (
    build_episodes,
    level_instances,
    scan_all,
    sigma_before_touch,
)

from . import constants as K


def active_start_ms(t0: int, episode: dict) -> int:
    return int(t0) + int(episode["i0"]) * PARENT.BAR_MS


def active_end_ms(t0: int, episode: dict) -> int:
    """Close time of the last bar of the active period."""
    return int(t0) + (int(episode["i1"]) + 1) * PARENT.BAR_MS


def eligible_episode(episode: dict, *, t0: int, start_ms: int) -> bool:
    if episode.get("population", "real") != "real":
        return False
    if episode.get("kind") not in K.LEVEL_KINDS:
        return False
    return active_start_ms(t0, episode) >= int(start_ms)


def complete_by(episode: dict, *, t0: int, checkpoint_end_ms: int) -> bool:
    return active_end_ms(t0, episode) <= int(checkpoint_end_ms)


def prospective_episodes(bars, start_ms: int) -> tuple[list[dict], list[dict], dict]:
    """Real episodes whose active period begins prospectively.

    Warm-up bars may sit in `bars`. They can form the previous period's high
    and low. They cannot open an eligible episode.
    """
    instances, drops = level_instances(bars)
    episodes, info = build_episodes(instances, K.ZONE_HALF)
    kept = [ep for ep in episodes if eligible_episode(ep, t0=int(bars.t0), start_ms=start_ms)]
    dropped = len(episodes) - len(kept)
    info = dict(info)
    info["dropped_pre_start"] = dropped
    info["instance_drops"] = drops
    return kept, instances, info


def first_touches(bars, episodes: list[dict], *, end_ms: int) -> list[dict]:
    """Touch number 1 only. No resolution label is consulted."""
    if not episodes:
        return []
    sigma = sigma_before_touch(bars.close)
    touches = scan_all(bars, episodes, sigma, end_ms=int(end_ms))
    out = []
    for touch in touches:
        if int(touch["touch_number"]) != 1:
            continue
        if touch.get("outcome") not in (None,):
            raise RuntimeError("a resolution label entered the prospective touch")
        out.append(touch)
    return out
