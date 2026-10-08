"""Consecutive-touch pairs whose previous touch was REJECT_FIRST.

Features on a pair are known at the open of the next touch. The next touch's outcome
is not a feature. Callers that must stay outcome-blind use `pair_features` only.
"""

from __future__ import annotations

import math
from typing import Optional

from scripts.research.level_touch_degradation_v1 import constants as P

from . import constants as K


def _vol_tercile(sigma: Optional[float]) -> int:
    if sigma is None or not math.isfinite(sigma):
        return -1
    if sigma <= K.PARENT_SIGMA_LO:
        return 0
    if sigma <= K.PARENT_SIGMA_HI:
        return 1
    return 2


def cluster_key(family: str, episode_id: str, next_week: int) -> str:
    """Day and week episodes sit inside one product week. A month episode does not.

    Month pairs of the same level therefore share the episode id. Everything else
    shares the product week of the next touch, which also covers same-level day pairs.
    """
    if family == "MONTH":
        return "M:" + episode_id
    return "W:" + str(int(next_week))


def pair_features(prev: dict, nxt: dict) -> Optional[dict]:
    """Geometry and predictors. Returns None when the pair is not in the cohort.

    Does not read `nxt["outcome"]`.
    """
    if prev.get("episode_id") != nxt.get("episode_id"):
        return None
    if int(nxt["touch_number"]) != int(prev["touch_number"]) + 1:
        return None
    if prev.get("outcome") != "REJECT":
        return None
    bars = prev.get("bars_to_reject")
    if not isinstance(bars, int) or bars < 1 or bars > P.HOLD_BARS_PRIMARY:
        return None
    if not prev.get("feature_eligible") or not nxt.get("feature_eligible"):
        return None
    j_reject = int(prev["j"]) + bars
    gap = int(nxt["j"]) - j_reject
    if gap < 1:
        return None
    over = prev.get("overshoot")
    side = int(nxt["side"])
    if side not in (1, -1):
        return None
    sigma = nxt.get("sigma")
    ter = _vol_tercile(None if sigma is None else float(sigma))
    if ter < 0:
        return None
    return {
        "episode_id": prev["episode_id"],
        "population": prev.get("population", "real"),
        "family": prev["family"],
        "prev_touch_number": int(prev["touch_number"]),
        "next_touch_number": int(nxt["touch_number"]),
        "next_bucket": nxt["bucket"],
        "touch3": 1 if nxt["bucket"] == "3+" else 0,
        "side": side,
        "support": 1 if side < 0 else 0,
        "year": int(nxt["year"]),
        "next_week": int(nxt["week"]),
        "sigma": float(sigma),
        "vol_tercile": ter,
        "bars_to_reject": bars,
        "speed_raw": -math.log(bars),
        "linear_raw": -float(bars),
        "overshoot": None if over is None or not math.isfinite(over) else float(over),
        "gap_bars": gap,
        "log_gap": math.log(gap),
        "j_prev": int(prev["j"]),
        "j_reject": j_reject,
        "j_next": int(nxt["j"]),
        "cluster": cluster_key(prev["family"], prev["episode_id"], int(nxt["week"])),
    }


def iter_consecutive(touches: list[dict]):
    """Yield (prev, next) in touch-number order within each episode. Outcome-free."""
    groups: dict[str, list] = {}
    for t in touches:
        groups.setdefault(t["episode_id"], []).append(t)
    for eid in sorted(groups):
        rows = sorted(groups[eid], key=lambda r: int(r["touch_number"]))
        for a, b in zip(rows, rows[1:]):
            if int(b["touch_number"]) == int(a["touch_number"]) + 1:
                yield a, b


def feature_pairs(touches: list[dict]) -> list[dict]:
    """Pairs with a usable predictor. Next-touch outcome is not copied."""
    out = []
    for prev, nxt in iter_consecutive(touches):
        feat = pair_features(prev, nxt)
        if feat is not None:
            out.append(feat)
    return out


def analysis_pairs(touches: list[dict]) -> tuple[list[dict], dict]:
    """Feature pairs whose next touch has a decisive primary outcome, plus drop counts.

    AMBIGUOUS next touches are counted and excluded. A missing next label is counted
    and excluded. BREAK / REJECT / NEITHER stay in the sample; NEITHER is a zero on
    the break indicator, not a drop.
    """
    kept = []
    drops = {"ambiguous": 0, "missing_next": 0, "features": 0}
    by_id = {}
    for t in touches:
        by_id.setdefault(t["episode_id"], {})[int(t["touch_number"])] = t
    for feat in feature_pairs(touches):
        drops["features"] += 1
        nxt = by_id[feat["episode_id"]][feat["next_touch_number"]]
        y = nxt.get("outcome")
        if y == "AMBIGUOUS":
            drops["ambiguous"] += 1
            continue
        if y not in ("BREAK", "REJECT", "NEITHER"):
            drops["missing_next"] += 1
            continue
        kept.append({**feat, "next_outcome": y})
    return kept, drops
