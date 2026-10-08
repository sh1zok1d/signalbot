"""Binance structural first touches with spot and cross-perp reaction attached.

Late labels are not attached here. Spot and the other venues do not create
levels, move the touch time, or rebuild the pseudo control.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Optional

import numpy as np

from scripts.research.level_acceptance_path_discovery_v1.path import approach_displacement
from scripts.research.level_cross_venue_reaction_discovery_v1.series import VenueSeries
from scripts.research.level_post_touch_reaction_discovery_v1.reactions import early_status, end_position
from scripts.research.level_touch_degradation_v1 import constants as PARENT
from scripts.research.level_touch_degradation_v1.build import build_population
from scripts.research.level_touch_degradation_v1.events import touch_week, touch_year

from . import constants as K
from .features import log_return, other_venue_median, spot_features, window_imbalance
from .spot import SpotSeries


def epoch_of(year: int) -> str:
    name = str(int(year))
    return name if name in K.EPOCHS else "OUT"


def time_block(open_ms: int) -> int:
    hour = (int(open_ms) // K.HOUR_MS) % 24
    return int(hour // 6)


def vol_tercile(sigma: Optional[float]) -> Optional[int]:
    if sigma is None or not math.isfinite(float(sigma)):
        return None
    if float(sigma) <= K.PARENT_SIGMA_LO:
        return 0
    if float(sigma) <= K.PARENT_SIGMA_HI:
        return 1
    return 2


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


def population(bars):
    return build_population(bars, PARENT.ZONE_HALF_PRIMARY)


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


def _perp_flow(bars, j: int) -> Optional[float]:
    if j < 0 or j + 2 >= bars.n:
        return None
    quotes = [float(bars.quote[j + k]) for k in range(3)]
    buys = [float(bars.taker_buy_quote[j + k]) for k in range(3)]
    return window_imbalance(quotes, buys)


def _spot_flow(spot: SpotSeries, open_ms: int) -> Optional[float]:
    quotes = []
    buys = []
    for k in range(3):
        quote, buy = spot.flow_at(int(open_ms) + k * K.BAR_MS)
        quotes.append(quote)
        buys.append(buy)
    return window_imbalance(quotes, buys)


def reaction_record(bars, open_ms: int, j: int, side: int, venues: dict[str, VenueSeries],
                    spot: SpotSeries) -> dict:
    base_open = int(open_ms) - K.BAR_MS
    decision_open = int(open_ms) + 2 * K.BAR_MS
    if j < 1 or j + 2 >= bars.n:
        b_base = b_decision = None
    elif int(bars.t0) + (j - 1) * K.BAR_MS != base_open or int(bars.t0) + j * K.BAR_MS != int(open_ms):
        b_base = b_decision = None
    elif int(bars.t0) + (j + 2) * K.BAR_MS != decision_open:
        b_base = b_decision = None
    else:
        b_base = float(bars.close[j - 1])
        b_decision = float(bars.close[j + 2])
        if not (math.isfinite(b_base) and math.isfinite(b_decision) and b_base > 0.0 and b_decision > 0.0):
            b_base = b_decision = None
    bybit = venues["BYBIT_LINEAR_BTCUSDT_PERP"]
    okx = venues["OKX_BTC_USDT_SWAP_PERP"]
    ret_binance = log_return(b_base, b_decision)
    ret_bybit = log_return(bybit.close_at(base_open), bybit.close_at(decision_open))
    ret_okx = log_return(okx.close_at(base_open), okx.close_at(decision_open))
    ret_spot = log_return(spot.close_at(base_open), spot.close_at(decision_open))
    cv1 = other_venue_median(ret_binance, ret_bybit, ret_okx, side)
    features = spot_features(
        ret_spot, ret_binance, ret_bybit, ret_okx, side,
        _spot_flow(spot, open_ms), _perp_flow(bars, j),
    )
    return {
        "RET_BINANCE": ret_binance,
        "RET_BYBIT": ret_bybit,
        "RET_OKX": ret_okx,
        "RET_SPOT": ret_spot,
        K.CV1_NAME: cv1,
        **features,
    }


def baseline_ok(row: dict) -> bool:
    endpoint = row.get("END_POSITION_X")
    disp = row.get("disp")
    cv1 = row.get(K.CV1_NAME)
    if row["vol_tercile"] is None or disp is None or endpoint is None or cv1 is None:
        return False
    if not all(math.isfinite(float(value)) for value in (disp, endpoint, cv1)):
        return False
    if row["family"] not in K.FAMILIES or row["epoch"] not in K.EPOCHS:
        return False
    return True


def _row(touch: dict, bars, venues, spot: SpotSeries, *, cluster_week: int) -> dict:
    oms = int(touch["open_ms"])
    side = int(touch["side"])
    j = int(touch["j"])
    if int(bars.t0) + j * K.BAR_MS != oms:
        raise RuntimeError("touch index does not match its open time")
    status = early_status(
        bars.high, bars.low, j, side, float(touch["zone_low"]), float(touch["zone_high"]),
        float(touch["x_primary"]),
    )
    close_d = float(bars.close[j + 2]) if j + 2 < bars.n else math.nan
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
        "decision_ms": oms + K.REACTION_MS,
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
        "END_POSITION_X": end_position(
            close_d, side, float(touch["zone_low"]), float(touch["zone_high"]), float(touch["x_primary"]),
        ),
    }
    row.update(reaction_record(bars, oms, j, side, venues, spot))
    row["baseline_ok"] = baseline_ok(row)
    return row


def assemble(bars, venues, spot: SpotSeries, built: Optional[dict] = None) -> dict:
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
        real_row = _row(real, bars, venues, spot, cluster_week=int(real["week"]))
        real_rows.append(real_row)
        if ps != "LEGITIMATE":
            continue
        pseudo_row = _row(pseudo, bars, venues, spot, cluster_week=int(real["week"]))
        pseudo_row["real_episode_id"] = eid
        pairs.append({
            "real": real_row,
            "pseudo": pseudo_row,
            "episode_id": eid,
            "pseudo_episode_id": pseudo["episode_id"],
        })
    return {
        "structural_episodes": len(built["episodes"]),
        "real_status": real_counts,
        "pseudo_status": pseudo_counts,
        "real_rows": real_rows,
        "pairs": pairs,
    }


def unresolved_baseline(rows: list[dict]) -> list[dict]:
    return [row for row in rows if row.get("early_status") == "UNRESOLVED" and row.get("baseline_ok")]


def early_census(rows: list[dict]) -> dict:
    counts = Counter(row.get("early_status") for row in rows)
    return {
        "n": len(rows),
        "n_early_break": int(counts["EARLY_BREAK"]),
        "n_early_reject": int(counts["EARLY_REJECT"]),
        "n_early_ambiguous": int(counts["EARLY_AMBIGUOUS"]),
        "n_unresolved": int(counts["UNRESOLVED"]),
        "n_unavailable": int(counts["UNAVAILABLE"]),
    }


def slice_counts(rows: list[dict]) -> dict:
    def pack(key: str) -> dict:
        counts = Counter(row.get(key) for row in rows)
        return {str(name): int(counts[name]) for name in sorted(counts, key=lambda item: str(item))}

    return {
        "year": pack("epoch"),
        "family": pack("family"),
        "side": {
            "resistance": sum(1 for row in rows if row["side"] > 0),
            "support": sum(1 for row in rows if row["side"] < 0),
        },
    }
