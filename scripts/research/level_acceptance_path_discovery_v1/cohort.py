"""First-touch cohort at D = T+15m. Late labels are not attached here."""

from __future__ import annotations

import math
from collections import Counter
from typing import Optional

import numpy as np

from scripts.research.level_post_touch_reaction_discovery_v1.reactions import early_status
from scripts.research.level_touch_degradation_v1 import constants as PARENT
from scripts.research.level_touch_degradation_v1.build import build_population
from scripts.research.level_touch_degradation_v1.events import touch_week, touch_year

from . import constants as K
from .path import approach_displacement, epoch_of, path_record, time_block, vol_tercile


def geometry_status(touch: Optional[dict]) -> str:
    if touch is None:
        return "NO_TOUCH"
    if int(touch["touch_number"]) != 1:
        return "NOT_FIRST"
    oms = int(touch["open_ms"])
    if oms < K.EVENT_START_MS or oms >= K.EVENT_END_MS:
        return "OUTSIDE_WINDOW"
    if not bool(touch.get("window_ok_48")):
        return "INCOMPLETE_4H"
    if int(touch.get("side", 0)) not in (1, -1):
        return "UNKNOWN_SIDE"
    x = touch.get("x_primary")
    if x is None or not (math.isfinite(float(x)) and PARENT.X_MIN < float(x) < PARENT.X_MAX):
        return "UNUSABLE_X"
    sigma = touch.get("sigma")
    if sigma is None or not math.isfinite(float(sigma)):
        return "NO_SIGMA"
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


def population(bars):
    return build_population(bars, PARENT.ZONE_HALF_PRIMARY)


def decision_ms(open_ms: int) -> int:
    return int(open_ms) + K.REACTION_MS


def _nuisance_ok(row: dict) -> bool:
    if row["vol_tercile"] is None or row["disp"] is None:
        return False
    if row["state"] not in K.STATES or row["state_indicator"] not in (0, 1):
        return False
    endpoint = row.get("END_POSITION_X")
    if endpoint is None or not math.isfinite(float(endpoint)):
        return False
    if not math.isfinite(float(row["disp"])):
        return False
    if row["family"] not in K.FAMILIES or row["epoch"] not in K.EPOCHS:
        return False
    return True


def _row(touch: dict, bars, *, cluster_week: int) -> dict:
    oms = int(touch["open_ms"])
    side = int(touch["side"])
    j = int(touch["j"])
    if int(bars.t0) + j * K.BAR_MS != oms:
        raise RuntimeError("touch index does not match its open time")
    status = early_status(
        bars.high, bars.low, j, side, float(touch["zone_low"]), float(touch["zone_high"]),
        float(touch["x_primary"]),
    )
    recorded = path_record(
        bars.close, int(bars.t0), oms, side, float(touch["zone_low"]), float(touch["zone_high"]),
        float(touch["x_primary"]),
    )
    year = int(touch["year"]) if "year" in touch else touch_year(oms)
    week = int(touch["week"]) if "week" in touch else touch_week(oms)
    row = {
        "episode_id": touch["episode_id"],
        "population": touch.get("population", "real"),
        "family": touch["family"],
        "kind": touch["kind"],
        "side": side,
        "support": 1.0 if side < 0 else 0.0,
        "year": year,
        "epoch": epoch_of(year),
        "week": week,
        "cluster": int(cluster_week),
        "open_ms": oms,
        "decision_ms": decision_ms(oms),
        "j": j,
        "zone_low": float(touch["zone_low"]),
        "zone_high": float(touch["zone_high"]),
        "x_primary": float(touch["x_primary"]),
        "sigma": float(touch["sigma"]),
        "vol_tercile": vol_tercile(float(touch["sigma"])),
        "time_block": time_block(oms),
        "struct_side": int(touch["struct_side"]),
        "early_status": status,
        "disp": approach_displacement(bars.open, bars.close, int(bars.t0), oms, side),
        **recorded,
    }
    row["nuisance_ok"] = _nuisance_ok(row)
    return row


def assemble(bars, built: Optional[dict] = None) -> dict:
    """Real and matched pseudo first touches. The pseudo price is the parent control."""
    built = population(bars) if built is None else built
    real_first = _index_first(built["touches"])
    pseudo_first = _index_first(built["control_touches"])
    by_shadow = {}
    for ctrl in built["controls"]:
        shadow = ctrl["shadow_id"]
        if shadow in by_shadow:
            raise RuntimeError(f"two controls for {shadow}")
        by_shadow[shadow] = ctrl
    keys = (
        "NO_TOUCH", "OUTSIDE_WINDOW", "INCOMPLETE_4H", "UNKNOWN_SIDE", "UNUSABLE_X",
        "NO_SIGMA", "LEGITIMATE",
    )
    real_counts = {k: 0 for k in keys}
    pseudo_counts = {k: 0 for k in keys}
    pseudo_counts["NO_CONTROL"] = 0
    real_rows = []
    pairs = []
    for ep in built["episodes"]:
        eid = ep["episode_id"]
        real = real_first.get(eid)
        rs = geometry_status(real)
        real_counts[rs] += 1
        ctrl = by_shadow.get(eid)
        if ctrl is None:
            pseudo_counts["NO_CONTROL"] += 1
            pseudo = None
            ps = "NO_CONTROL"
        else:
            pseudo = pseudo_first.get(ctrl["episode_id"])
            ps = geometry_status(pseudo)
            pseudo_counts[ps] += 1
        if rs != "LEGITIMATE":
            continue
        real_row = _row(real, bars, cluster_week=int(real["week"]))
        real_rows.append(real_row)
        if ps != "LEGITIMATE":
            continue
        pseudo_row = _row(pseudo, bars, cluster_week=int(real["week"]))
        pseudo_row["real_episode_id"] = eid
        pseudo_row["pseudo_episode_id"] = pseudo["episode_id"]
        pairs.append({
            "real": real_row,
            "pseudo": pseudo_row,
            "episode_id": eid,
            "pseudo_episode_id": pseudo["episode_id"],
        })
    return {
        "structural_episodes": len(built["episodes"]),
        "controls_built": len(built["controls"]),
        "real_status": real_counts,
        "pseudo_status": pseudo_counts,
        "real_rows": real_rows,
        "pairs": pairs,
    }


def unresolved_rows(rows: list[dict]) -> list[dict]:
    return [row for row in rows if row.get("early_status") == "UNRESOLVED"]


def early_census(rows: list[dict]) -> dict:
    counts = Counter(row.get("early_status") for row in rows)
    classified = sum(int(counts[name]) for name in (
        "EARLY_BREAK", "EARLY_REJECT", "EARLY_AMBIGUOUS", "UNRESOLVED",
    ))
    resolved = int(counts["EARLY_BREAK"]) + int(counts["EARLY_REJECT"])

    def rate(name: str):
        if classified == 0:
            return None
        return counts[name] / classified

    return {
        "n": len(rows),
        "n_early_break": int(counts["EARLY_BREAK"]),
        "n_early_reject": int(counts["EARLY_REJECT"]),
        "n_early_ambiguous": int(counts["EARLY_AMBIGUOUS"]),
        "n_unresolved": int(counts["UNRESOLVED"]),
        "n_unavailable": int(counts["UNAVAILABLE"]),
        "n_early_resolved": resolved,
        "n_classified": classified,
        "p_early_break": rate("EARLY_BREAK"),
        "p_early_reject": rate("EARLY_REJECT"),
        "p_early_ambiguous": rate("EARLY_AMBIGUOUS"),
        "p_unresolved": rate("UNRESOLVED"),
    }


def column(rows: list[dict], name: str) -> np.ndarray:
    out = np.empty(len(rows), dtype=float)
    for i, row in enumerate(rows):
        value = row.get(name)
        out[i] = math.nan if value is None else float(value)
    return out
