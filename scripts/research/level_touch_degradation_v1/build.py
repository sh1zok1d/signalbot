"""Assemble episodes and touches for one zone width. Does not classify outcomes."""

from __future__ import annotations

from beta.hist_series import Bars

from .control import control_episodes
from .events import build_episodes, level_instances, scan_all, sigma_before_touch


def build_population(bars: Bars, zone_half: float) -> dict:
    sigma = sigma_before_touch(bars.close)
    instances, drops = level_instances(bars)
    episodes, info = build_episodes(instances, zone_half)
    touches = scan_all(bars, episodes, sigma)
    controls = control_episodes(episodes, instances, zone_half)
    control_touches = scan_all(bars, controls, sigma)
    return {
        "zone_half": float(zone_half),
        "instances": instances,
        "drops": drops,
        "episodes": episodes,
        "episode_info": info,
        "touches": touches,
        "controls": controls,
        "control_touches": control_touches,
    }
