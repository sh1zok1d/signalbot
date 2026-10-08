"""Outcome-blind structural first-touch cohort on a bar grid.

Eligibility does not use LEVEL_TOUCH_DEGRADATION_V1.feature_eligible. That flag is tied to
the Binance event start (2020-02-01) and would drop every BitMEX touch. The geometric
touch, the zone and the pseudo episode are still the parent functions.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from beta import levels as LV

from scripts.research.level_touch_degradation_v1.build import build_population
from scripts.research.level_touch_degradation_v1.control import control_episodes
from scripts.research.level_touch_degradation_v1.events import touch_week

from . import constants as K
from scripts.research.level_touch_degradation_v1 import constants as PARENT


def first_touch_status(touch: Optional[dict], *, event_start_ms: int, event_end_ms: int) -> str:
    """Partition of a geometric first touch. Does not look at a barrier label."""
    if touch is None:
        return "NO_TOUCH"
    if int(touch["touch_number"]) != 1:
        return "NOT_FIRST"
    oms = int(touch["open_ms"])
    if oms < event_start_ms or oms >= event_end_ms:
        return "OUTSIDE_WINDOW"
    if not bool(touch.get("window_ok_48")):
        return "INCOMPLETE_4H"
    if int(touch.get("side", 0)) not in (1, -1):
        return "UNKNOWN_SIDE"
    x = touch.get("x_primary")
    if x is None or not (math.isfinite(float(x)) and PARENT.X_MIN < float(x) < PARENT.X_MAX):
        return "UNUSABLE_X"
    return "LEGITIMATE"


def _index_first(touches: list[dict]) -> dict:
    out = {}
    for touch in touches:
        if int(touch["touch_number"]) != 1:
            continue
        eid = touch["episode_id"]
        if eid in out:
            raise RuntimeError(f"two first touches on {eid}")
        out[eid] = touch
    return out


def iter_episode_links(population: dict):
    """Yield (episode, real_touch_or_none, control_or_none, pseudo_touch_or_none)."""
    real_first = _index_first(population["touches"])
    control_first = _index_first(population["control_touches"])
    by_shadow = {}
    for ctrl in population["controls"]:
        shadow = ctrl["shadow_id"]
        if shadow in by_shadow:
            raise RuntimeError(f"two controls for {shadow}")
        by_shadow[shadow] = ctrl
    for ep in population["episodes"]:
        eid = ep["episode_id"]
        ctrl = by_shadow.get(eid)
        pseudo = control_first.get(ctrl["episode_id"]) if ctrl is not None else None
        yield ep, real_first.get(eid), ctrl, pseudo


def census(population: dict, *, event_start_ms: int = K.EVENT_START_MS,
           event_end_ms: int = K.EVENT_END_MS) -> dict:
    """Counts only. No barrier frequency."""
    keys = (
        "NO_TOUCH", "OUTSIDE_WINDOW", "INCOMPLETE_4H", "UNKNOWN_SIDE", "UNUSABLE_X", "LEGITIMATE",
    )
    real_counts = {k: 0 for k in keys}
    pseudo_counts = {k: 0 for k in keys}
    pseudo_counts["NO_CONTROL"] = 0
    matched = []
    for ep, real, ctrl, pseudo in iter_episode_links(population):
        rs = first_touch_status(real, event_start_ms=event_start_ms, event_end_ms=event_end_ms)
        real_counts[rs] += 1
        if ctrl is None:
            pseudo_counts["NO_CONTROL"] += 1
            ps = "NO_CONTROL"
        else:
            ps = first_touch_status(pseudo, event_start_ms=event_start_ms, event_end_ms=event_end_ms)
            pseudo_counts[ps] += 1
        if rs == "LEGITIMATE" and ps == "LEGITIMATE":
            matched.append(_pair(ep, real, ctrl, pseudo))
    weeks = sorted({int(p["week"]) for p in matched})
    by_epoch = {name: 0 for name in K.EPOCHS}
    by_family = {name: 0 for name in K.FAMILIES}
    by_side = {name: 0 for name in ("resistance", "support")}
    out_epoch = 0
    for p in matched:
        if p["epoch"] in by_epoch:
            by_epoch[p["epoch"]] += 1
        else:
            out_epoch += 1
        by_family[p["family"]] += 1
        by_side[K.SIDE_NAME[int(p["real_side"])]] += 1
    n_eps = len(population["episodes"])
    return {
        "structural_episodes": n_eps,
        "controls_built": len(population["controls"]),
        "real_status": real_counts,
        "pseudo_status": pseudo_counts,
        "real_legitimate": real_counts["LEGITIMATE"],
        "pseudo_legitimate": pseudo_counts["LEGITIMATE"],
        "matched_pairs": len(matched),
        "missing_real": n_eps - real_counts["LEGITIMATE"],
        "missing_pseudo": n_eps - pseudo_counts["LEGITIMATE"],
        "incomplete_4h_real": real_counts["INCOMPLETE_4H"],
        "incomplete_4h_pseudo": pseudo_counts["INCOMPLETE_4H"],
        "weeks": len(weeks),
        "by_epoch": by_epoch,
        "by_family": by_family,
        "by_real_side": by_side,
        "outside_epoch": out_epoch,
        "pairs": matched,
    }


def _pair(ep: dict, real: dict, ctrl: dict, pseudo: dict) -> dict:
    return {
        "episode_id": ep["episode_id"],
        "family": ep["family"],
        "struct_side": int(ep["struct_side"]),
        "week": int(real["week"]),
        "epoch": K.epoch_of_ms(int(real["open_ms"])),
        "pseudo_epoch": K.epoch_of_ms(int(pseudo["open_ms"])),
        "real_side": int(real["side"]),
        "pseudo_side": int(pseudo["side"]),
        "real_sigma": float(real["sigma"]),
        "pseudo_sigma": float(pseudo["sigma"]),
        "real_open_ms": int(real["open_ms"]),
        "pseudo_open_ms": int(pseudo["open_ms"]),
        "real_year": int(real["year"]),
        "real_touch": real,
        "pseudo_touch": pseudo,
        "control_id": ctrl["episode_id"],
        "partner_id": ctrl["partner_id"],
    }


def period_audit(bars) -> dict:
    """Full-period counts under the parent rule. No prices are turned into outcomes."""
    keys = LV.period_keys(bars)
    spec = (("DAY", "day", 288), ("WEEK", "week", 7 * 288), ("MONTH", "month", None))
    out = {"n_bars": int(bars.n), "finite_frac": float(np.isfinite(bars.close).mean())}
    for family, name, expected in spec:
        rows = LV._period_table(bars, keys[name])
        full = [r for r in rows if LV._full_period(r, expected)]
        first = rows[0] if rows else None
        out[family] = {
            "periods": len(rows),
            "full_periods": len(full),
            "first_bars": None if first is None else int(first["bars"]),
            "first_frac": None if first is None else float(first["frac"]),
            "first_full": bool(first is not None and LV._full_period(first, expected)),
        }
    present = np.isfinite(bars.close)
    missing = ~present
    # Longest run of missing bars, outcome-blind.
    longest = 0
    run = 0
    for flag in missing:
        if flag:
            run += 1
            longest = max(longest, run)
        else:
            run = 0
    out["missing_bars"] = int(missing.sum())
    out["longest_missing_run"] = int(longest)
    return out


def population(bars):
    """Parent episode builder at the frozen zone width. Does not classify barriers."""
    return build_population(bars, K.ZONE_HALF)


def touch_week_id(open_ms: int) -> int:
    return int(touch_week(open_ms))


__all__ = ["census", "control_episodes", "first_touch_status", "period_audit", "population"]
