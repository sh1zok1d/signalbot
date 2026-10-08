"""Point-in-time constituent list for a structural zone.

Replays the parent birth-cluster and later-absorption rules and keeps the bar index at
which each constituent became known. The parent episode stores later constituents as
kind names only, so this replay is the as-of clock. It does not move the zone and it
does not classify outcomes.

A constituent born at bar i0 is known at the open of i0. A touch at bar j may use
constituents with available index <= j. A constituent with a later index is future.
"""

from __future__ import annotations

from typing import Iterable

from scripts.research.level_touch_degradation_v1 import constants as PK
from scripts.research.level_touch_degradation_v1.events import _near, _rel_gap


def _member(inst: dict, available: int, *, birth: bool) -> dict:
    return {
        "kind": inst["kind"],
        "family": inst["family"],
        "price": float(inst["price"]),
        "available_i0": int(available),
        "source_key": int(inst["source_key"]),
        "struct_side": int(inst["struct_side"]),
        "birth": bool(birth),
    }


def replay(instances: Iterable[dict], zone_half: float) -> dict[str, dict]:
    """Episode id -> ledger. Birth geometry matches `events.build_episodes`."""
    born: dict[int, list] = {}
    for inst in instances:
        born.setdefault(int(inst["i0"]), []).append(inst)
    episodes: list[dict] = []
    ledgers: dict[str, dict] = {}
    for i0 in sorted(born):
        active = [ep for ep in episodes if ep["i0"] < i0 <= ep["i1"]]
        free: list[dict] = []
        for inst in born[i0]:
            hosts = []
            for ep in active:
                inside = ep["zone_low"] <= inst["price"] <= ep["zone_high"]
                if inside or _near(inst["price"], ep["anchor_price"], zone_half):
                    hosts.append(ep)
            if not hosts:
                free.append(inst)
                continue
            host = min(hosts, key=lambda ep: (ep["priority"], abs(ep["anchor_price"] - inst["price"])))
            host["absorbed_later"].append(inst["kind"])
            ledgers[host["episode_id"]]["members"].append(_member(inst, i0, birth=False))
        free.sort(key=lambda r: (r["price"], PK.PRIORITY[r["kind"]], r["kind"]))
        clusters: list[list] = []
        for inst in free:
            if clusters and _rel_gap(inst["price"], clusters[-1][-1]["price"]) <= zone_half:
                clusters[-1].append(inst)
            else:
                clusters.append([inst])
        for cluster in clusters:
            anchor = min(cluster, key=lambda r: (PK.PRIORITY[r["kind"]], r["price"], r["kind"]))
            prices = [r["price"] for r in cluster]
            zlo = min(prices) * (1.0 - zone_half)
            zhi = max(prices) * (1.0 + zone_half)
            if not (zlo > 0 and zhi > zlo):
                continue
            episode_id = f"{anchor['kind']}:{anchor['source_key']}:{anchor['i0']}"
            ep = {
                "episode_id": episode_id,
                "priority": PK.PRIORITY[anchor["kind"]],
                "anchor_price": anchor["price"],
                "zone_low": float(zlo),
                "zone_high": float(zhi),
                "i0": anchor["i0"],
                "i1": anchor["i1"],
                "absorbed_later": [],
            }
            episodes.append(ep)
            ledgers[episode_id] = {
                "episode_id": episode_id,
                "i0": int(anchor["i0"]),
                "i1": int(anchor["i1"]),
                "anchor_kind": anchor["kind"],
                "anchor_family": anchor["family"],
                "anchor_side": int(anchor["struct_side"]),
                "anchor_price": float(anchor["price"]),
                "source_key": int(anchor["source_key"]),
                "members": [_member(inst, anchor["i0"], birth=True) for inst in cluster],
                "absorbed_kinds": [],
            }
    for ep in episodes:
        ledgers[ep["episode_id"]]["absorbed_kinds"] = list(ep["absorbed_later"])
    return ledgers


def members_as_of(ledger: dict, j: int) -> list[dict]:
    """Constituents known at the open of bar j. Later births are excluded."""
    return [m for m in ledger["members"] if int(m["available_i0"]) <= int(j)]
