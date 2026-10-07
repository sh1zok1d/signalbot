"""First-touch cohort. Geometry is the parent scanner. Outcomes are not classified here.

Book features are read at the touch open. The pseudo price is the parent's
half-rotation. This module does not move that price using the book.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from scripts.research.level_touch_degradation_v1 import constants as PARENT
from scripts.research.level_touch_degradation_v1.build import build_population
from scripts.research.level_touch_degradation_v1.events import touch_week, touch_year

from . import constants as K
from .book import book_features


def epoch_of(decision_ms: int) -> Optional[str]:
    t = int(decision_ms)
    for name, start, end in K.EPOCH_BOUND_MS:
        if start <= t < end:
            return name
    return None


def time_block(decision_ms: int) -> int:
    hour = (int(decision_ms) // K.HOUR_MS) % 24
    return int(hour // 6)


def vol_tercile(sigma: Optional[float]) -> Optional[int]:
    if sigma is None or not math.isfinite(float(sigma)):
        return None
    if float(sigma) <= K.PARENT_SIGMA_LO:
        return 0
    if float(sigma) <= K.PARENT_SIGMA_HI:
        return 1
    return 2


def price_nuisance(open_: np.ndarray, close: np.ndarray, quote: np.ndarray,
                   t0: int, decision_ms: int, side: int) -> dict:
    """Oriented displacement and relative quote volume on bars that close at or before T.

    The touch bar is excluded. Taker volume is not read.
    """
    empty = {"disp": None, "rel_volume": None}
    t = int(decision_ms)
    if side not in (1, -1) or t % K.BAR_MS != 0 or (t - int(t0)) % K.BAR_MS != 0:
        return empty
    j = (t - int(t0)) // K.BAR_MS
    i0 = j - K.TAKER_BARS
    i24 = j - K.REL_VOL_BARS
    if i0 < 0 or j > quote.shape[0]:
        return empty
    if int(t0) + i0 * K.BAR_MS != t - K.PRIMARY_MS:
        return empty
    if int(t0) + j * K.BAR_MS != t:
        return empty
    q60 = quote[i0:j]
    if q60.shape[0] != K.TAKER_BARS or not bool(np.isfinite(q60).all()) or np.any(q60 < 0.0):
        return empty
    o0 = float(open_[i0])
    c1 = float(close[j - 1])
    disp = None
    if math.isfinite(o0) and math.isfinite(c1) and o0 > 0.0 and c1 > 0.0:
        disp = float(side) * math.log(c1 / o0)
    rel = None
    if i24 >= 0:
        hist = quote[i24:j]
        ok = np.isfinite(hist) & (hist >= 0.0)
        if ok.size == K.REL_VOL_BARS and float(ok.mean()) >= K.REL_VOL_MIN_PRESENT:
            base = float(hist[ok].mean())
            if base > 0.0:
                rel = float(q60.sum()) / (base * K.TAKER_BARS)
    return {"disp": disp, "rel_volume": rel}


def geometry_status(touch: Optional[dict]) -> str:
    if touch is None:
        return "NO_TOUCH"
    if int(touch["touch_number"]) != 1:
        return "NOT_FIRST"
    oms = int(touch["open_ms"])
    if oms < K.EVENT_START_MS or oms >= K.EVENT_END_MS:
        return "OUTSIDE_WINDOW"
    if int(touch["j"]) < int(touch["i0"]):
        return "LEVEL_NOT_YET_BORN"
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


def _row(touch: dict, bars, book: dict, *, cluster_week: int) -> dict:
    oms = int(touch["open_ms"])
    side = int(touch["side"])
    features = book_features(book, oms, side)
    nuisance = price_nuisance(bars.open, bars.close, bars.quote, int(bars.t0), oms, side)
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
        "epoch": epoch_of(oms),
        "week": week,
        "cluster": int(cluster_week),
        "open_ms": oms,
        "j": int(touch["j"]),
        "i0": int(touch["i0"]),
        "zone_low": float(touch["zone_low"]),
        "zone_high": float(touch["zone_high"]),
        "x_primary": float(touch["x_primary"]),
        "sigma": float(touch["sigma"]),
        "vol_tercile": vol_tercile(float(touch["sigma"])),
        "time_block": time_block(oms),
        "struct_side": int(touch["struct_side"]),
        **features,
        **nuisance,
    }


def _nuisance_ok(row: dict) -> bool:
    if row["vol_tercile"] is None or row["disp"] is None or row["rel_volume"] is None:
        return False
    if row["family"] not in K.FAMILIES or row["epoch"] not in K.EPOCHS:
        return False
    if int(row["j"]) < int(row["i0"]):
        return False
    return True


def assemble(bars, book: dict, built: Optional[dict] = None) -> dict:
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
        "NO_SIGMA", "LEVEL_NOT_YET_BORN", "LEGITIMATE",
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
        real_row = _row(real, bars, book, cluster_week=int(real["week"]))
        real_row["nuisance_ok"] = _nuisance_ok(real_row)
        real_rows.append(real_row)
        if ps != "LEGITIMATE":
            continue
        pseudo_row = _row(pseudo, bars, book, cluster_week=int(real["week"]))
        pseudo_row["nuisance_ok"] = _nuisance_ok(pseudo_row)
        pseudo_row["real_episode_id"] = eid
        pairs.append({
            "real": real_row,
            "pseudo": pseudo_row,
            "episode_id": eid,
            "pseudo_episode_id": pseudo["episode_id"],
            "pseudo_open_ms": int(pseudo["open_ms"]),
        })
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
