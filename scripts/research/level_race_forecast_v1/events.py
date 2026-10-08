"""Race events at the two landmarks, built by the unchanged #352 constructor (design §0, §1).

Outcome labels are attached only by `attach_outcomes`, which the HIST builder and tests import.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from beta.hist_series import Bars

from scripts.research.level_touch_degradation_v1 import constants as K352
from scripts.research.level_touch_degradation_v1.events import (
    build_episodes, level_instances, scan_all, sigma_before_touch,
)
from scripts.research.level_touch_degradation_v1.outcomes import classify

from . import b0 as B0
from . import constants as K

OUTCOME_MAP = {"BREAK": "BEYOND", "REJECT": "BACK", "NEITHER": "NEITHER", "AMBIGUOUS": "AMBIGUOUS"}


def first_touches(bars: Bars, *, end_ms: int = K352.SURFACE_END_MS) -> list[dict]:
    """#352 touch 1 rows with `feature_eligible` (geometry usable, side known, 4h window complete)."""
    sigma = sigma_before_touch(bars.close)
    instances, _ = level_instances(bars)
    episodes, _ = build_episodes(instances, K.ZONE_HALF)
    touches = scan_all(bars, episodes, sigma, end_ms=end_ms)
    return [t for t in touches if t["touch_number"] == 1 and t["feature_eligible"]]


def geometry(t: dict) -> dict:
    """Barrier prices and orientation. Upper/lower are the same for both approach sides."""
    x = float(t["x_primary"])
    p_up = float(t["zone_high"]) * (1.0 + x)
    p_dn = float(t["zone_low"]) * (1.0 - x)
    beyond_is_up = int(t["side"]) > 0
    return {"p_up": p_up, "p_dn": p_dn, "beyond_is_up": beyond_is_up}


def early_state(high: np.ndarray, low: np.ndarray, t: dict) -> Optional[str]:
    """#352 barrier rule on bars j+1, j+2 only (#361). NEITHER = still unresolved at T15."""
    return classify(high, low, int(t["j"]), int(t["side"]), float(t["zone_low"]), float(t["zone_high"]),
                    float(t["x_primary"]), K.T15_OFFSET)


def landmark_rows(bars: Bars, touches: list[dict]) -> list[dict]:
    """One row per event per landmark. A T15 row exists only if no barrier (and no AMBIGUOUS bar)
    occurred on j+1 or j+2: a display rule, not an empty cell (design §0)."""
    high, low, close = bars.high, bars.low, bars.close
    rows: list[dict] = []
    for t in touches:
        g = geometry(t)
        j = int(t["j"])
        sigma = float(t["sigma"])
        for lm in K.LANDMARKS:
            if lm == "T15":
                st = early_state(high, low, t)
                if st != "NEITHER":
                    continue
                pos_i = j + K.T15_OFFSET
            else:
                pos_i = j
            pos = float(close[pos_i])
            if not math.isfinite(pos) or pos <= 0:
                continue
            up, dn, ne = B0.race(pos, g["p_up"], g["p_dn"], sigma, K.TAU[lm])
            beyond, back = (up, dn) if g["beyond_is_up"] else (dn, up)
            rows.append({
                "event_id": f"{t['episode_id']}:{j}",
                "landmark": lm,
                "family": t["family"],
                "struct_side": int(t["struct_side"]),
                "side": int(t["side"]),
                "week": int(t["week"]),
                "year": int(t["year"]),
                "j": j,
                "position": pos,
                "p_up": g["p_up"],
                "p_dn": g["p_dn"],
                "beyond_is_up": g["beyond_is_up"],
                "sigma": sigma,
                "tau": K.TAU[lm],
                "b0_beyond": beyond,
                "b0_back": back,
                "b0_neither": ne,
                "outcome": None,
            })
    return rows


def early_census(bars: Bars, touches: list[dict]) -> dict:
    """Counts of the j+1/j+2 states (why an event has no T15 row)."""
    out: dict = {}
    for t in touches:
        st = early_state(bars.high, bars.low, t)
        key = "NONE" if st is None else st
        out[key] = out.get(key, 0) + 1
    return out


def attach_outcomes(bars: Bars, rows: list[dict], touches: list[dict]) -> list[dict]:
    """#352 classify on the original window j+1 .. j+48. For a T15 row (unresolved on j+1, j+2)
    this equals the first passage on j+3 .. j+48."""
    by_id = {f"{t['episode_id']}:{int(t['j'])}": t for t in touches}
    out = []
    for r in rows:
        t = by_id[r["event_id"]]
        y = classify(bars.high, bars.low, int(t["j"]), int(t["side"]), float(t["zone_low"]),
                     float(t["zone_high"]), float(t["x_primary"]), K.WINDOW_BARS)
        out.append({**r, "outcome": None if y is None else OUTCOME_MAP[y]})
    return out
