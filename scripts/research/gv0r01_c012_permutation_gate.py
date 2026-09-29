"""Timestamp-only global permutation-invariance gate for frozen C012.

Reads the committed preflight windows. Does not open a price file and does
not change the frozen permutation.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PREFLIGHT_JSON = REPO / "docs/research/GV0R01_C012_PREFLIGHT.json"

RATIONALE = (
    "The frozen test shuffles event and control labels inside YEAR x WEEKDAY x "
    "UTC_HOUR and leaves every other label fixed. Within-stratum endpoints are "
    "at least 7 days apart, so that local separation does not by itself make the "
    "joint return vector invariant. Overlap components cross strata. 240 allowed "
    "within-stratum swaps exchange observations whose sets of outside-stratum "
    "overlap neighbors differ (154 observations). A swap of that kind changes "
    "which coordinate shares minutes with a fixed outside window, so the "
    "dependency topology of the complete statistic is not preserved. Exact "
    "global exchangeability of the frozen permutation group is therefore not "
    "established. The inference procedure is not amended in this unit."
)


def _overlap(a0: str, a1: str, b0: str, b1: str) -> bool:
    return a0 < b1 and b0 < a1


def observations_from_pairs(pairs: list[dict]) -> list[dict]:
    rows = []
    for p in pairs:
        rows.append({
            "ID": f"E:{p['EVENT_ID']}",
            "ROLE": "EVENT",
            "CELL": p["CELL"],
            "START": p["EVENT_WINDOW_START_UTC"],
            "END": p["EVENT_WINDOW_END_UTC"],
        })
        rows.append({
            "ID": f"C:{p['EVENT_ID']}",
            "ROLE": "CONTROL",
            "CELL": p["CELL"],
            "START": p["CONTROL_WINDOW_START_UTC"],
            "END": p["CONTROL_WINDOW_END_UTC"],
        })
    return rows


def overlap_graph(rows: list[dict]) -> dict[str, list[str]]:
    neighbors = {r["ID"]: [] for r in rows}
    for i, a in enumerate(rows):
        for b in rows[i + 1:]:
            if _overlap(a["START"], a["END"], b["START"], b["END"]):
                neighbors[a["ID"]].append(b["ID"])
                neighbors[b["ID"]].append(a["ID"])
    for key in neighbors:
        neighbors[key] = sorted(neighbors[key])
    return neighbors


def _components(neighbors: dict[str, list[str]]) -> list[list[str]]:
    seen: set[str] = set()
    out = []
    for node in sorted(neighbors):
        if node in seen:
            continue
        stack = [node]
        comp = []
        seen.add(node)
        while stack:
            cur = stack.pop()
            comp.append(cur)
            for nxt in neighbors[cur]:
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        out.append(sorted(comp))
    return out


def external_neighborhood(row_id: str, cell: str, rows_by_id: dict, neighbors: dict) -> tuple:
    ext = []
    for nid in neighbors[row_id]:
        if rows_by_id[nid]["CELL"] != cell:
            ext.append(nid)
    return tuple(sorted(ext))


def gate_from_pairs(pairs: list[dict]) -> dict:
    rows = observations_from_pairs(pairs)
    rows_by_id = {r["ID"]: r for r in rows}
    neighbors = overlap_graph(rows)
    comps = _components(neighbors)
    sizes = sorted(len(c) for c in comps)
    by_cell: dict[str, list[dict]] = {}
    for r in rows:
        by_cell.setdefault(r["CELL"], []).append(r)
    diff_pairs = []
    diff_obs: set[str] = set()
    for cell, group in sorted(by_cell.items()):
        hoods = {
            r["ID"]: external_neighborhood(r["ID"], cell, rows_by_id, neighbors)
            for r in group
        }
        ids = [r["ID"] for r in group]
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                if hoods[a] != hoods[b]:
                    diff_pairs.append((cell, a, b, list(hoods[a]), list(hoods[b])))
                    diff_obs.add(a)
                    diff_obs.add(b)
    status = "PASS" if not diff_pairs else "NOT_ESTABLISHED"
    return {
        "OBSERVATION_COUNT": len(rows),
        "GLOBAL_OVERLAP_GRAPH_COMPONENTS": len(comps),
        "MAX_OVERLAP_COMPONENT_SIZE": max(sizes) if sizes else 0,
        "NONTRIVIAL_COMPONENT_COUNT": sum(1 for s in sizes if s > 1),
        "COMPONENT_SIZE_HISTOGRAM": {str(s): sizes.count(s) for s in sorted(set(sizes))},
        "SWAPPABLE_PAIRS_WITH_DIFFERENT_EXTERNAL_NEIGHBORHOODS": len(diff_pairs),
        "SWAPPABLE_OBSERVATIONS_WITH_DIFFERENT_EXTERNAL_NEIGHBORHOODS": len(diff_obs),
        "EXAMPLE_DIFFERING_PAIR": (
            {
                "CELL": diff_pairs[0][0],
                "LEFT": diff_pairs[0][1],
                "RIGHT": diff_pairs[0][2],
                "LEFT_EXTERNAL_NEIGHBORS": diff_pairs[0][3],
                "RIGHT_EXTERNAL_NEIGHBORS": diff_pairs[0][4],
            }
            if diff_pairs else None
        ),
        "GLOBAL_PERMUTATION_INVARIANCE_STATUS": status,
        "GLOBAL_PERMUTATION_INVARIANCE_RATIONALE": RATIONALE if status != "PASS" else "Every within-stratum pair has the same external overlap neighborhood.",
    }
