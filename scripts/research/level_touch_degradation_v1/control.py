"""Deterministic pseudo-level episodes.

The product's random-level control places levels at the same distance from the period open
and scores only the first touch. It has no touch-number dimension, so it cannot answer
whether a touch-number pattern appears away from structural levels.

This control keeps the real episode's lifetime and family, and moves the anchor to another
episode's signed distance from the open (a half-rotation of the same family and structural
side). The first non-colliding partner is kept. The rotation is a fixed function of the
episode order, not a draw, and it is not refit after outcomes.
"""

from __future__ import annotations

import math
from typing import Iterable, Optional

from .events import _near


def _overlaps(a0: int, a1: int, b0: int, b1: int) -> bool:
    return a0 <= b1 and b0 <= a1


def _collides(price: float, i0: int, i1: int, instances: list[dict], tol: float) -> bool:
    for inst in instances:
        if not _overlaps(i0, i1, inst["i0"], inst["i1"]):
            continue
        if _near(price, inst["price"], tol):
            return True
    return False


def control_episodes(episodes: Iterable[dict], instances: Iterable[dict], zone_half: float) -> list[dict]:
    real = [ep for ep in episodes if ep.get("population", "real") == "real"]
    inst = list(instances)
    groups: dict[tuple, list] = {}
    for ep in real:
        groups.setdefault((ep["family"], int(ep["struct_side"])), []).append(ep)
    out: list[dict] = []
    for key in sorted(groups, key=lambda k: (k[0], k[1])):
        group = sorted(groups[key], key=lambda ep: (ep["i0"], ep["anchor_price"], ep["episode_id"]))
        n = len(group)
        if n < 2:
            continue
        shift = n // 2
        for i, ep in enumerate(group):
            chosen: Optional[dict] = None
            distance = None
            for step in range(n - 1):
                partner = group[(i + shift + step) % n]
                if partner["episode_id"] == ep["episode_id"]:
                    continue
                if partner["period_open"] <= 0 or ep["period_open"] <= 0:
                    continue
                d = partner["anchor_price"] / partner["period_open"] - 1.0
                price = ep["period_open"] * (1.0 + d)
                if not math.isfinite(price) or price <= 0:
                    continue
                if _collides(price, ep["i0"], ep["i1"], inst, zone_half):
                    continue
                chosen = partner
                distance = d
                break
            if chosen is None or distance is None:
                continue
            zlo = price * (1.0 - zone_half)
            zhi = price * (1.0 + zone_half)
            out.append({
                "episode_id": f"CTRL:{ep['episode_id']}:{chosen['episode_id']}",
                "kind": f"CTRL_{ep['kind']}",
                "family": ep["family"],
                "struct_side": int(ep["struct_side"]),
                "priority": ep["priority"],
                "anchor_price": float(price),
                "zone_low": float(zlo),
                "zone_high": float(zhi),
                "i0": ep["i0"],
                "i1": ep["i1"],
                "period_open": ep["period_open"],
                "source_key": ep["source_key"],
                "period_key": ep["period_key"],
                "member_kinds": [f"CTRL_{ep['kind']}"],
                "n_members": 1,
                "absorbed_later": [],
                "population": "control",
                "zone_half": float(zone_half),
                "shadow_id": ep["episode_id"],
                "partner_id": chosen["episode_id"],
                "distance": float(distance),
            })
    return out
