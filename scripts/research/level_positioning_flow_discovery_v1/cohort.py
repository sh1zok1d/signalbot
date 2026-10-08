"""First-touch cohort. Geometry is the parent scanner. Outcomes are not classified here."""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from scripts.research.level_touch_degradation_v1 import constants as PARENT
from scripts.research.level_touch_degradation_v1.build import build_population
from scripts.research.level_touch_degradation_v1.events import touch_week, touch_year

from . import constants as K
from .features import epoch_of, flow_features, oi_features_from_prints, oi_prints, time_block, vol_tercile
from .oi import OiSeries


def geometry_status(touch: Optional[dict]) -> str:
    """Partition of a touch before any barrier label and before any positioning feature."""
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


def _row(touch: dict, bars, oi: OiSeries, *, cluster_week: int) -> dict:
    oms = int(touch["open_ms"])
    side = int(touch["side"])
    prints = oi_prints(oi.available_at_ms, oi.sum_open_interest, oms)
    oi_part = {"OI_CHANGE_60M": None, "OI_RECENT_ACCELERATION": None, "oi_complete_60m": False}
    if prints is not None:
        oi_part.update(oi_features_from_prints(prints))
        oi_part["oi_complete_60m"] = True
    flow = flow_features(bars.open, bars.close, bars.quote, bars.taker_buy_quote, int(bars.t0), oms, side)
    year = int(touch["year"]) if "year" in touch else touch_year(oms)
    week = int(touch["week"]) if "week" in touch else touch_week(oms)
    return {
        "episode_id": touch["episode_id"],
        "population": touch.get("population", "real"),
        "family": touch["family"],
        "kind": touch["kind"],
        "side": side,
        "support": 1.0 if side < 0 else 0.0,
        "year": year,
        "epoch": epoch_of(oms, year),
        "week": week,
        "cluster": int(cluster_week),
        "open_ms": oms,
        "j": int(touch["j"]),
        "zone_low": float(touch["zone_low"]),
        "zone_high": float(touch["zone_high"]),
        "x_primary": float(touch["x_primary"]),
        "sigma": float(touch["sigma"]),
        "vol_tercile": vol_tercile(float(touch["sigma"])),
        "time_block": time_block(oms),
        "struct_side": int(touch["struct_side"]),
        **oi_part,
        **flow,
    }


def _nuisance_ok(row: dict) -> bool:
    if row["vol_tercile"] is None or row["disp"] is None or row["rel_volume"] is None:
        return False
    if row["family"] not in K.FAMILIES or row["epoch"] not in K.EPOCHS:
        return False
    return True


def assemble(bars, oi: OiSeries, built: Optional[dict] = None) -> dict:
    """Real first touches and matched pseudo first touches. No barrier label."""
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
        real_row = _row(real, bars, oi, cluster_week=int(real["week"]))
        real_row["nuisance_ok"] = _nuisance_ok(real_row)
        real_rows.append(real_row)
        if ps != "LEGITIMATE":
            continue
        pseudo_row = _row(pseudo, bars, oi, cluster_week=int(real["week"]))
        pseudo_row["nuisance_ok"] = _nuisance_ok(pseudo_row)
        pseudo_row["real_episode_id"] = eid
        pairs.append({"real": real_row, "pseudo": pseudo_row, "episode_id": eid})
    return {
        "structural_episodes": len(built["episodes"]),
        "controls_built": len(built["controls"]),
        "real_status": real_counts,
        "pseudo_status": pseudo_counts,
        "real_rows": real_rows,
        "pairs": pairs,
    }


def feature_complete(row: dict, names: tuple[str, ...] | list[str]) -> bool:
    if not row.get("nuisance_ok"):
        return False
    for name in names:
        value = row.get(name)
        if value is None or not math.isfinite(float(value)):
            return False
    return True


def column(rows: list[dict], name: str) -> np.ndarray:
    out = np.empty(len(rows), dtype=float)
    for i, row in enumerate(rows):
        value = row.get(name)
        out[i] = math.nan if value is None else float(value)
    return out
