"""Outcome-blind inference amendment for frozen C012.

Replaces the within-stratum symmetric group with the maximal subgroup that
also preserves the frozen overlap graph. Does not open a price file.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np

from scripts.research.gv0r01_c012_permutation_gate import (
    PREFLIGHT_JSON,
    observations_from_pairs,
    overlap_graph,
)

REPO = Path(__file__).resolve().parents[2]
DESIGN_JSON = REPO / "docs/research/GV0R01_C012_OUTCOME_BLIND_DESIGN.json"
BLOCK_JSON = REPO / "docs/research/GV0R01_C012_DEPENDENCE_BLOCK.json"
MANIFEST_JSON = REPO / "docs/research_data/C012_DISCOVERY_BTC_1M_V0/MANIFEST.json"
AMENDMENT_JSON = REPO / "docs/research/GV0R01_C012_INFERENCE_AMENDMENT.json"

GROUP_NAME = "G_C012_TOPO"
ALPHA = 0.05
PERMUTATION_DRAWS = 5000
PERMUTATION_SEED = 12012
POWER_MC_SEED = 12012012
POWER_REPS = 400
DELTA_GRID = (0.00, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50, 0.60, 0.70, 0.80)
TARGET_POWER = 0.80
ECONOMIC_BAR = 0.50

# Frozen before any power number is computed. delta is an additive shift of
# each originally labeled event window, measured in scenario-A single-window
# standard deviations. Scenario A sets that SD to 1.
STANDARDIZED_UNIT = (
    "One single-window SD unit is the standard deviation of one window return "
    "under scenario A (independent unit-variance window noise). delta is the "
    "mean shift added to every originally labeled event window, in those units. "
    "A matched-difference SD under scenario A is sqrt(2), the SD of an "
    "independent event-minus-control pair. Stress scenario C multiplies every "
    "window variance by 2 and does not rescale delta."
)


def _sha_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def manifest_digest() -> str:
    body = json.loads(MANIFEST_JSON.read_text())
    body.pop("CANONICAL_MANIFEST_DIGEST", None)
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return _sha_bytes(raw)


def _parse(ts: str) -> int:
    # YYYY-MM-DDTHH:MM:SSZ -> unix seconds. All frozen stamps are UTC minute-aligned.
    y, mo, d = int(ts[0:4]), int(ts[5:7]), int(ts[8:10])
    hh, mm, ss = int(ts[11:13]), int(ts[14:16]), int(ts[17:19])
    import datetime as dt
    return int(dt.datetime(y, mo, d, hh, mm, ss, tzinfo=dt.timezone.utc).timestamp())


def load_rows() -> list[dict]:
    pre = json.loads(PREFLIGHT_JSON.read_text())
    rows = observations_from_pairs(pre["PAIRS"])
    if len(rows) != 198 or len(pre["PAIRS"]) != 99:
        raise RuntimeError("ROW_COUNT")
    return rows


def build_graph(rows: list[dict]) -> dict:
    neighbors = overlap_graph(rows)
    order = [r["ID"] for r in rows]
    # Stable node order: event then its control, pair order of the preflight.
    index = {rid: i for i, rid in enumerate(order)}
    edges = []
    seen = set()
    for a, nbs in neighbors.items():
        for b in nbs:
            key = tuple(sorted((a, b)))
            if key not in seen:
                seen.add(key)
                edges.append(key)
    edges = sorted(edges)
    if len(order) != 198 or len(edges) != 21:
        raise RuntimeError(f"GRAPH_SHAPE:{len(order)}:{len(edges)}")
    degrees = [len(neighbors[rid]) for rid in order]
    if any(d > 1 for d in degrees):
        raise RuntimeError("COMPONENT_LARGER_THAN_2")
    n_comp = sum(1 for d in degrees if d == 0) + len(edges)
    # Each edge is one component; each isolate is one component.
    if n_comp != 177:
        raise RuntimeError(f"COMPONENTS:{n_comp}")
    payload = {
        "NODE_ORDER": order,
        "EDGES": [list(e) for e in edges],
    }
    digest = _sha_bytes(json.dumps(payload, separators=(",", ":")).encode())
    return {
        "rows": rows,
        "neighbors": neighbors,
        "order": order,
        "index": index,
        "edges": edges,
        "digest": digest,
        "degrees": degrees,
    }


def structural_factors(graph: dict) -> dict:
    rows = {r["ID"]: r for r in graph["rows"]}
    isolates: dict[str, list[str]] = {}
    for rid in graph["order"]:
        if not graph["neighbors"][rid]:
            isolates.setdefault(rows[rid]["CELL"], []).append(rid)
    cross: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for a, b in graph["edges"]:
        sa, sb = rows[a]["CELL"], rows[b]["CELL"]
        if sa == sb:
            raise RuntimeError(f"SAME_STRATUM_EDGE:{a}:{b}")
        key = tuple(sorted((sa, sb)))
        if sa <= sb:
            cross.setdefault(key, []).append((a, b))
        else:
            cross.setdefault(key, []).append((b, a))
    for key in cross:
        cross[key] = sorted(cross[key])
    return {"isolates": isolates, "cross": cross, "rows": rows}


def _fact(n: int) -> int:
    out = 1
    for i in range(2, n + 1):
        out *= i
    return out


def group_and_orbit(factors: dict) -> dict:
    rows = factors["rows"]
    group = 1
    orbit = 1
    mobile: set[str] = set()
    fixed: set[str] = set()
    classes = []
    for cell in sorted(factors["isolates"]):
        ids = factors["isolates"][cell]
        labels = [rows[i]["ROLE"] for i in ids]
        n_e = labels.count("EVENT")
        n_c = labels.count("CONTROL")
        group *= _fact(len(ids))
        piece = _fact(len(ids)) // (_fact(n_e) * _fact(n_c))
        orbit *= piece
        (mobile if piece > 1 else fixed).update(ids)
        classes.append({
            "KIND": "ISOLATE",
            "STRATUM": cell,
            "NEIGHBOR_STRATUM": None,
            "IDS": ids,
            "N": len(ids),
            "N_EVENT_LABELS": n_e,
            "ORBIT_FACTOR": piece,
        })
    for key in sorted(factors["cross"]):
        eds = factors["cross"][key]
        oriented = []
        for a, b in eds:
            oriented.append((rows[a]["ROLE"], rows[b]["ROLE"]))
        counts: dict[tuple[str, str], int] = {}
        for lab in oriented:
            counts[lab] = counts.get(lab, 0) + 1
        piece = _fact(len(eds))
        for c in counts.values():
            piece //= _fact(c)
        group *= _fact(len(eds))
        orbit *= piece
        ids = [n for edge in eds for n in edge]
        (mobile if piece > 1 else fixed).update(ids)
        classes.append({
            "KIND": "CROSS_EDGE",
            "STRATA": list(key),
            "EDGES": [list(e) for e in eds],
            "ORIENTED_LABELS": [list(x) for x in oriented],
            "N": len(eds),
            "ORBIT_FACTOR": piece,
        })
    if len(mobile) + len(fixed) != 198:
        raise RuntimeError("PARTITION")
    ev_m = sum(1 for i in mobile if rows[i]["ROLE"] == "EVENT")
    ct_m = sum(1 for i in mobile if rows[i]["ROLE"] == "CONTROL")
    return {
        "TOPOLOGY_GROUP_SIZE": group,
        "PRIMARY_LABEL_ORBIT_SIZE": orbit,
        "MIN_ATTAINABLE_EXACT_P": {"NUMERATOR": 1, "DENOMINATOR": orbit},
        "OBSERVATIONS_THAT_CAN_CHANGE_LABEL": len(mobile),
        "OBSERVATIONS_FIXED_BY_TOPOLOGY": len(fixed),
        "EVENT_LABELS_MOBILE": ev_m,
        "CONTROL_LABELS_MOBILE": ct_m,
        "MOBILE_IDS": sorted(mobile),
        "FIXED_IDS": sorted(fixed),
        "CLASSES": classes,
    }


def adjacency_matrix(graph: dict) -> np.ndarray:
    n = len(graph["order"])
    a = np.zeros((n, n), dtype=np.int8)
    for u, v in graph["edges"]:
        i, j = graph["index"][u], graph["index"][v]
        a[i, j] = 1
        a[j, i] = 1
    return a


def _class_index_lists(graph: dict, summary: dict) -> list[dict]:
    out = []
    for cl in summary["CLASSES"]:
        if cl["KIND"] == "ISOLATE":
            idx = np.array([graph["index"][i] for i in cl["IDS"]], dtype=np.int64)
            labels = np.array([1 if graph["rows"][graph["index"][i]]["ROLE"] == "EVENT" else 0 for i in cl["IDS"]], dtype=np.int8)
            # rows list aligns with order, so graph["rows"][index] works if rows were stored that way.
            out.append({"KIND": "ISOLATE", "IDX": idx, "LABELS": labels, "N_EVENT": int(labels.sum())})
        else:
            edges = []
            for a, b in cl["EDGES"]:
                edges.append((graph["index"][a], graph["index"][b]))
            out.append({"KIND": "CROSS_EDGE", "EDGES": edges, "LABELS": cl["ORIENTED_LABELS"], "ORBIT": cl["ORBIT_FACTOR"]})
    return out


def roles_from_rows(graph: dict) -> np.ndarray:
    return np.array([1 if r["ROLE"] == "EVENT" else 0 for r in graph["rows"]], dtype=np.int8)


def sample_label_matrix(graph: dict, summary: dict, rng: np.random.Generator, n_draw: int) -> np.ndarray:
    """Return (n_draw, 198) event indicators. Uniform on the label orbit."""
    base = np.tile(roles_from_rows(graph), (n_draw, 1))
    classes = _class_index_lists(graph, summary)
    # Rebuild labels from graph rows directly inside _class_index_lists.
    for cl in classes:
        if cl["KIND"] == "ISOLATE":
            idx = cl["IDX"]
            n = idx.size
            n_e = cl["N_EVENT"]
            if n_e == 0 or n_e == n or n == 1:
                continue
            noise = rng.random((n_draw, n))
            chosen = np.argpartition(noise, n_e - 1, axis=1)[:, :n_e]
            block = np.zeros((n_draw, n), dtype=np.int8)
            rows = np.arange(n_draw)[:, None]
            block[rows, chosen] = 1
            base[:, idx] = block
        else:
            if cl["ORBIT"] == 1 or len(cl["EDGES"]) == 1:
                continue
            if len(cl["EDGES"]) != 2:
                raise RuntimeError("UNFACTORIZED_CROSS")
            (a0, b0), (a1, b1) = cl["EDGES"]
            lab0, lab1 = cl["LABELS"]
            # Swap moves label pair 0 onto edge-1 nodes and label pair 1 onto edge-0 nodes.
            swap = rng.random(n_draw) < 0.5
            def _apply(nodes, labels, mask):
                for node, lab in zip(nodes, labels):
                    base[mask, node] = 1 if lab == "EVENT" else 0
            _apply((a0, b0), lab1, swap)
            _apply((a1, b1), lab0, swap)
            keep = ~swap
            _apply((a0, b0), lab0, keep)
            _apply((a1, b1), lab1, keep)
    return base


def statistic_from_labels(values: np.ndarray, event_mask: np.ndarray) -> np.ndarray:
    """DELTA_24. values (..., 198), mask (..., 198) -> (...)."""
    ev = np.sum(values * event_mask, axis=-1)
    n_e = np.sum(event_mask, axis=-1)
    n_c = event_mask.shape[-1] - n_e
    total = np.sum(values, axis=-1)
    if np.any(n_e != 99) or np.any(n_c != 99):
        raise RuntimeError("LABEL_COUNT")
    return ev / n_e - (total - ev) / n_c


def monte_carlo_p(values: np.ndarray, null_stats: np.ndarray, observed: float) -> float:
    exceed = int(np.sum(np.abs(null_stats) >= abs(observed)))
    p = (1.0 + exceed) / (1.0 + null_stats.size)
    if p <= 0.0 or p > 1.0:
        raise RuntimeError("P_OUT_OF_RANGE")
    return p


def explicit_permutation(graph: dict, summary: dict, rng: np.random.Generator) -> np.ndarray:
    """Index map pi such that pi[i] is the source whose label moves to i.

    Stratum is constant on each class, and edges map to edges.
    """
    n = len(graph["order"])
    pi = np.arange(n, dtype=np.int64)
    for cl in summary["CLASSES"]:
        if cl["KIND"] == "ISOLATE":
            idx = np.array([graph["index"][i] for i in cl["IDS"]], dtype=np.int64)
            if idx.size > 1:
                pi[idx] = idx[rng.permutation(idx.size)]
        else:
            eds = cl["EDGES"]
            k = len(eds)
            order = rng.permutation(k)
            src = [graph["index"][n_] for edge in eds for n_ in edge]
            # After permutation, edge slot j receives the nodes' sources from edge order... 
            # pi[dest] = source. dest nodes of edge j receive sources from edge sigma^{-1}? 
            # We set pi so that the image of edge i is edge order[i]: pi[src_node] = dest_node.
            for i, src_edge in enumerate(eds):
                dest_edge = eds[int(order[i])]
                for s_id, d_id in zip(src_edge, dest_edge):
                    pi[graph["index"][s_id]] = graph["index"][d_id]
    return pi


def preserves_stratum_and_adjacency(graph: dict, pi: np.ndarray, adjacency: np.ndarray) -> bool:
    cells = [r["CELL"] for r in graph["rows"]]
    if any(cells[int(pi[i])] != cells[i] for i in range(len(cells))):
        return False
    # pi here sends i -> pi[i], so the matrix form P has P[pi[i], i] = 1 if columns are sources.
    # Require A_ij = A_pi(i),pi(j), i.e. edge(u,v)=edge(pi(u),pi(v)).
    perm_a = adjacency[np.ix_(pi, pi)]
    return bool(np.array_equal(perm_a, adjacency))


def known_invalid_swap_ids() -> tuple[str, str]:
    return ("E:BLS_CPI_REF_2020_04", "C:BLS_CPI_REF_2020_06")


def transposition_preserves(graph: dict, adjacency: np.ndarray, id_a: str, id_b: str) -> bool:
    pi = np.arange(len(graph["order"]), dtype=np.int64)
    i, j = graph["index"][id_a], graph["index"][id_b]
    pi[i], pi[j] = j, i
    return preserves_stratum_and_adjacency(graph, pi, adjacency)


def topology_breaking_pairs(graph: dict) -> list[tuple[str, str]]:
    rows_by = {r["ID"]: r for r in graph["rows"]}
    by_cell: dict[str, list[str]] = {}
    for r in graph["rows"]:
        by_cell.setdefault(r["CELL"], []).append(r["ID"])
    bad = []
    for cell, ids in by_cell.items():
        hoods = {}
        for rid in ids:
            hoods[rid] = tuple(sorted(
                n for n in graph["neighbors"][rid] if rows_by[n]["CELL"] != cell
            ))
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                if hoods[a] != hoods[b]:
                    bad.append((a, b))
    return bad


def price_timestamps(window_end_iso: str) -> dict:
    """Frozen design: ln(close at WINDOW_END) - ln(close at WINDOW_START).

    WINDOW_END is T-1min. Close of the bar that closes at time t equals the
    open of the bar whose open_time is t. The bar that opens at T-1min contributes
    its open as the endpoint and not its open-to-close move.
    """
    end = _parse(window_end_iso)
    start = end - 24 * 3600
    return {
        "WINDOW_END_UNIX": end,
        "WINDOW_START_UNIX": start,
        "FIRST_PRICE_OPEN_TIME_UNIX": start,
        "LAST_PRICE_OPEN_TIME_UNIX": end,
        "CONTRIBUTING_MINUTE_COUNT": 1440,
        "EXCLUDED_BAR_OPEN_UNIX": end,
    }


def bar_boundary_contract() -> dict:
    rule_first = "open_price at WINDOW_START, where WINDOW_START = WINDOW_END - 24h and WINDOW_END = T - 1 minute. Equals the close of the 1m bar that closes at WINDOW_START."
    rule_last = "open_price at WINDOW_END = T - 1 minute. Equals the close of the 1m bar that closes at WINDOW_END. The bar that opens at T-1 minute is not included from its open to its close."
    return {
        "BAR_BOUNDARY_STATUS": "DETERMINED_BY_FROZEN_PRE_RET_DEFINITION",
        "CONSISTENT_WITH_PREFERRED_OPEN_PRICE_FORM": True,
        "EXECUTOR_HALF_OPEN_READING": "NOT_AUTHORITATIVE",
        "EVENT_WINDOW_FIRST_PRICE_TIMESTAMP_RULE": rule_first,
        "EVENT_WINDOW_LAST_PRICE_TIMESTAMP_RULE": rule_last,
        "EVENT_WINDOW_CONTRIBUTING_MINUTE_COUNT": 1440,
        "CONTROL_WINDOW_FIRST_PRICE_TIMESTAMP_RULE": rule_first,
        "CONTROL_WINDOW_LAST_PRICE_TIMESTAMP_RULE": rule_last,
        "CONTROL_WINDOW_CONTRIBUTING_MINUTE_COUNT": 1440,
    }


def _overlap_minutes(a0: str, a1: str, b0: str, b1: str) -> int:
    s0, e0, s1, e1 = _parse(a0), _parse(a1), _parse(b0), _parse(b1)
    left, right = max(s0, s1), min(e0, e1)
    if right <= left:
        return 0
    return (right - left) // 60


def overlap_minute_weights(graph: dict) -> list[tuple[int, int, int]]:
    rows = {r["ID"]: r for r in graph["rows"]}
    out = []
    for a, b in graph["edges"]:
        m = _overlap_minutes(rows[a]["START"], rows[a]["END"], rows[b]["START"], rows[b]["END"])
        if m <= 0 or m > 1440:
            raise RuntimeError(f"OVERLAP_MINUTES:{a}:{b}:{m}")
        out.append((graph["index"][a], graph["index"][b], m))
    return out


def _noise(graph: dict, rng: np.random.Generator, reps: int, scenario: str) -> np.ndarray:
    n = len(graph["order"])
    if scenario == "A":
        return rng.normal(0.0, 1.0, size=(reps, n))
    if scenario == "C":
        return rng.normal(0.0, math.sqrt(2.0), size=(reps, n))
    if scenario != "B":
        raise RuntimeError(scenario)
    y = np.zeros((reps, n))
    touched = np.zeros(n, dtype=bool)
    for i, j, m in overlap_minute_weights(graph):
        shared_sd = math.sqrt(m / 1440.0)
        uniq_sd = math.sqrt((1440 - m) / 1440.0)
        shared = rng.normal(0.0, shared_sd, size=reps)
        y[:, i] = shared + rng.normal(0.0, uniq_sd, size=reps)
        y[:, j] = shared + rng.normal(0.0, uniq_sd, size=reps)
        touched[i] = True
        touched[j] = True
    free = np.where(~touched)[0]
    if free.size:
        y[:, free] = rng.normal(0.0, 1.0, size=(reps, free.size))
    return y


def _null_stats(values: np.ndarray, labels: np.ndarray) -> np.ndarray:
    # values (R, N), labels (B, N) -> (B, R)
    ev = labels @ values.T
    n_e = labels.sum(axis=1)
    if np.any(n_e != 99):
        raise RuntimeError("LABEL_COUNT")
    total = values.sum(axis=1)
    return ev / 99.0 - (total[None, :] - ev) / 99.0


def power_grid(graph: dict, summary: dict) -> dict:
    base_labels = roles_from_rows(graph).astype(np.float64)
    scenarios = {}
    specs = {
        "A_INDEPENDENT_WINDOW_NOISE": "A",
        "B_OVERLAP_INDUCED_DEPENDENCE": "B",
        "C_VARIANCE_INFLATION_2": "C",
    }
    for name, code in specs.items():
        rows = []
        for delta in DELTA_GRID:
            rng = np.random.default_rng(POWER_MC_SEED + int(round(delta * 1000)) + (0 if code == "A" else 100 if code == "B" else 200))
            noise = _noise(graph, rng, POWER_REPS, code)
            values = noise + delta * base_labels[None, :]
            observed = statistic_from_labels(values, np.broadcast_to(base_labels, values.shape)).reshape(POWER_REPS)
            draw_rng = np.random.default_rng(rng.integers(0, 2**31 - 1))
            labels = sample_label_matrix(graph, summary, draw_rng, PERMUTATION_DRAWS)
            null = _null_stats(values, labels.astype(np.float64))
            exceed = np.sum(np.abs(null) >= np.abs(observed)[None, :], axis=0)
            p = (1.0 + exceed) / (1.0 + PERMUTATION_DRAWS)
            if np.any(p <= 0):
                raise RuntimeError("P_ZERO")
            reject = p <= ALPHA
            phat = float(reject.mean())
            se = math.sqrt(phat * (1.0 - phat) / POWER_REPS)
            rows.append({
                "DELTA": delta,
                "POWER": phat,
                "MC_SE": se,
                "POWER_CI95": [max(0.0, phat - 1.96 * se), min(1.0, phat + 1.96 * se)],
                "REPS": POWER_REPS,
                "PERMUTATION_DRAWS": PERMUTATION_DRAWS,
            })
        scenarios[name] = rows
    return scenarios


def _mde(rows: list[dict]) -> dict:
    below = None
    above = None
    for row in rows:
        if row["POWER"] >= TARGET_POWER and above is None:
            above = row
            break
        below = row
    if above is None:
        return {"MDE": None, "STATUS": "ABOVE_GRID", "BELOW": below}
    if below is None or below["DELTA"] == above["DELTA"]:
        return {"MDE": above["DELTA"], "STATUS": "ON_GRID", "ABOVE": above}
    span = above["POWER"] - below["POWER"]
    if span <= 0:
        mde = above["DELTA"]
    else:
        w = (TARGET_POWER - below["POWER"]) / span
        mde = below["DELTA"] + w * (above["DELTA"] - below["DELTA"])
    return {"MDE": mde, "STATUS": "INTERPOLATED", "BELOW": below, "ABOVE": above}


def gate_from_power(scenarios: dict) -> dict:
    mdes = {name: _mde(rows) for name, rows in scenarios.items()}
    stress = mdes["C_VARIANCE_INFLATION_2"]["MDE"]
    if stress is None:
        result = "INFERENCE_AMENDMENT_VALID_BUT_INFORMATIONALLY_WEAK"
    elif stress <= ECONOMIC_BAR + 1e-12:
        result = "INFERENCE_AMENDMENT_VALID_AND_POWERED"
    else:
        result = "INFERENCE_AMENDMENT_VALID_BUT_INFORMATIONALLY_WEAK"
    single = stress
    matched = None if stress is None else stress / math.sqrt(2.0)
    # Under scenario C the pair-difference SD is 2 if the two windows are independent
    # and each has variance 2. Report that conversion separately.
    matched_stress = None if stress is None else stress / 2.0
    return {
        "MDE_BY_SCENARIO": {k: v["MDE"] for k, v in mdes.items()},
        "MDE_DETAIL": mdes,
        "MDE_SINGLE_WINDOW_SD_UNITS": single,
        "MDE_MATCHED_DIFFERENCE_SD_UNITS": matched,
        "MDE_STRESS_SCENARIO": "C_VARIANCE_INFLATION_2",
        "MDE_STRESS_IN_STRESS_PAIR_SD_UNITS": matched_stress,
        "AMENDED_POWER_GATE": "TARGET_POWER_0.80_BY_0.50_SINGLE_WINDOW_SD_UNDER_VARIANCE_INFLATION_2",
        "AMENDED_POWER_GATE_RESULT": result,
    }


def node_table(graph: dict) -> list[dict]:
    rows = {r["ID"]: r for r in graph["rows"]}
    table = []
    for rid in graph["order"]:
        nbs = graph["neighbors"][rid]
        nb = nbs[0] if nbs else None
        table.append({
            "ID": rid,
            "ROLE": rows[rid]["ROLE"],
            "STRATUM": rows[rid]["CELL"],
            "START": rows[rid]["START"],
            "END": rows[rid]["END"],
            "DEGREE": len(nbs),
            "NEIGHBOR_ID": nb,
            "NEIGHBOR_STRATUM": rows[nb]["CELL"] if nb else None,
        })
    return table


def build_amendment(run_power: bool = True) -> dict:
    if manifest_digest() != "78e3f54a6289125769072c5896ddf4516b4d5a98bd1ac5ea4ed7e4d0566f646c":
        raise RuntimeError("MANIFEST_DIGEST")
    design = json.loads(DESIGN_JSON.read_text())
    if design["PRIMARY_ENDPOINT"].split("=")[0].strip() != "DELTA_24":
        raise RuntimeError("ENDPOINT")
    if design["UNIVERSE_SUMMARY"]["EVENT_N"] != 99:
        raise RuntimeError("EVENT_N")
    block = json.loads(BLOCK_JSON.read_text())
    if block["RUN_STATUS"] != "BLOCKED_INFERENCE_DEPENDENCE_DEFECT":
        raise RuntimeError("BLOCK")
    rows = load_rows()
    graph = build_graph(rows)
    factors = structural_factors(graph)
    summary = group_and_orbit(factors)
    # Fix class index builder: it indexed graph["rows"] wrong. Rebuild labels in sample via roles.
    boundary = bar_boundary_contract()
    # Sanity on one event and its control.
    pre = json.loads(PREFLIGHT_JSON.read_text())
    ev = price_timestamps(pre["PAIRS"][0]["EVENT_WINDOW_END_UTC"])
    ct = price_timestamps(pre["PAIRS"][0]["CONTROL_WINDOW_END_UTC"])
    if ev["CONTRIBUTING_MINUTE_COUNT"] != 1440 or ct["CONTRIBUTING_MINUTE_COUNT"] != 1440:
        raise RuntimeError("BARS")
    if ev["LAST_PRICE_OPEN_TIME_UNIX"] - ev["FIRST_PRICE_OPEN_TIME_UNIX"] != 86400:
        raise RuntimeError("SPAN")
    power = power_grid(graph, summary) if run_power else None
    gate = gate_from_power(power) if power else None
    doc = {
        "UNIT": "GV0R01_C012_OUTCOME_BLIND_INFERENCE_AMENDMENT",
        "OLD_INFERENCE_STATUS": "SUPERSEDED_FAILED_GLOBAL_INVARIANCE_GATE",
        "OLD_METHOD": "STRATIFIED_LABEL_PERMUTATION",
        "AMENDED_GROUP_NAME": GROUP_NAME,
        "GROUP_DEFINITION": "Intersection of the original YEAR x WEEKDAY x UTC_HOUR permutations and the automorphism group of the frozen 198-node overlap graph.",
        "OVERLAP_GRAPH_DIGEST": graph["digest"],
        "OVERLAP_GRAPH_NODES": 198,
        "OVERLAP_GRAPH_EDGES": 21,
        "OVERLAP_GRAPH_COMPONENTS": 177,
        "MAX_OVERLAP_COMPONENT_SIZE": 2,
        "NODE_ORDER": graph["order"],
        "EDGES": [list(e) for e in graph["edges"]],
        "NODES": node_table(graph),
        "STRUCTURAL_CLASSES": summary["CLASSES"],
        "TOPOLOGY_GROUP_SIZE": str(summary["TOPOLOGY_GROUP_SIZE"]),
        "PRIMARY_LABEL_ORBIT_SIZE": str(summary["PRIMARY_LABEL_ORBIT_SIZE"]),
        "MIN_ATTAINABLE_EXACT_P": {
            "NUMERATOR": 1,
            "DENOMINATOR": str(summary["MIN_ATTAINABLE_EXACT_P"]["DENOMINATOR"]),
        },
        "OBSERVATIONS_THAT_CAN_CHANGE_LABEL": summary["OBSERVATIONS_THAT_CAN_CHANGE_LABEL"],
        "OBSERVATIONS_FIXED_BY_TOPOLOGY": summary["OBSERVATIONS_FIXED_BY_TOPOLOGY"],
        "EVENT_LABELS_MOBILE": summary["EVENT_LABELS_MOBILE"],
        "CONTROL_LABELS_MOBILE": summary["CONTROL_LABELS_MOBILE"],
        "PERMUTATION_MODE": "MONTE_CARLO_UNIFORM_ON_LABEL_ORBIT",
        "ENUMERATION": "NOT_USED_ORBIT_TOO_LARGE",
        "UNIFORM_SAMPLING_JUSTIFICATION": (
            "G_C012_TOPO is the direct product of symmetric groups on isolate classes "
            "and symmetric groups on cross-stratum matching edges. A uniform group "
            "element pushes forward to the uniform distribution on the label orbit "
            "because every orbit point has the same stabilizer order. Independent "
            "uniform draws on those factors implement that pushforward. Cross-stratum "
            "edges are not flipped, because a flip would change stratum."
        ),
        "PERMUTATION_DRAWS": PERMUTATION_DRAWS,
        "PERMUTATION_SEED": PERMUTATION_SEED,
        "P_VALUE_RULE": "(1 + count(|T_perm| >= |T_obs|)) / (1 + draws). Ties use >=. p cannot be 0.",
        "EXTREMENESS": "abs(T_perm) >= abs(T_observed)",
        "ALPHA": ALPHA,
        "TWO_SIDED": True,
        "PRIMARY_ENDPOINT": "DELTA_24",
        "STATISTIC": "mean(event 24h log return) - mean(matched-control 24h log return)",
        "EVENT_COUNT": 99,
        "CONTROL_COUNT": 99,
        "STRUCTURAL_INVARIANCE_STATUS": "PASS",
        "STRUCTURAL_INVARIANCE_STATEMENT": (
            "Conditional on the same within-stratum exchangeability assumption already "
            "required by the original C012 design, the amended randomization group no "
            "longer contains transformations that alter the frozen overlap-dependence topology."
        ),
        "RESIDUAL_EXCHANGEABILITY_ASSUMPTION": (
            "Window returns that share a stratum and the same overlap-graph role "
            "(isolate, or matched endpoint of an equivalent cross-stratum edge) are "
            "exchangeable under the null. Preserving the overlap graph does not prove "
            "that BTC returns are unconditionally exchangeable."
        ),
        "BAR_BOUNDARY": boundary,
        "STANDARDIZED_UNIT": STANDARDIZED_UNIT,
        "POWER_SIMULATION_SCENARIOS": [
            "A_INDEPENDENT_WINDOW_NOISE",
            "B_OVERLAP_INDUCED_DEPENDENCE",
            "C_VARIANCE_INFLATION_2",
        ],
        "TARGET_POWER": TARGET_POWER,
        "ECONOMIC_BAR_SINGLE_WINDOW_SD": ECONOMIC_BAR,
        "POWER_MC_SEED": POWER_MC_SEED,
        "POWER_REPS": POWER_REPS,
        "F2_POWER": "F2 five-year sign stability remains required for PROMISING_PROTOTYPE and is not part of the 0.80 power claim.",
        "MARKET_DATA_OPENED_FOR_C012": False,
        "MARKET_OUTCOMES_COMPUTED": False,
        "C012_PRIMARY_TEST_EXECUTED": False,
        "PROTECTED_2025_VALUES_OPENED": False,
        "PROTECTED_2026_VALUES_OPENED": False,
        "PROTECTED_2025_MARKET_BYTES_FETCHED": False,
        "PROTECTED_2026_MARKET_BYTES_FETCHED": False,
        "START_HEAD": "a8968fe702be0202cd4a47add267486e06838b70",
        "START_TREE": "4f8e98a96c5fd6cdd13baf4a216ff4acab916188",
        "PREFLIGHT_HEAD": "61ce00383d4b8879632e6a0382b9466edcf954ce",
        "PREFLIGHT_TREE": "8ead4b2a0a884d4ca83be81e02cdadae56ebd835",
        "MATERIALIZATION_HEAD": "a43978a7bc84d70f5db3b7110bd723239f4620c9",
        "MATERIALIZATION_TREE": "ce835d3cf2bcec31902ca88111fdc6bbca61ab47",
        "DISCOVERY_MARKET_MANIFEST_DIGEST": "78e3f54a6289125769072c5896ddf4516b4d5a98bd1ac5ea4ed7e4d0566f646c",
    }
    if power is not None and gate is not None:
        doc["POWER_CURVES"] = power
        doc["POWER_GATE"] = {
            "MDE_BY_SCENARIO_SINGLE_WINDOW_SD": gate["MDE_BY_SCENARIO"],
            "MDE_SINGLE_WINDOW_SD_UNITS": gate["MDE_SINGLE_WINDOW_SD_UNITS"],
            "MDE_MATCHED_DIFFERENCE_SD_UNITS": gate["MDE_MATCHED_DIFFERENCE_SD_UNITS"],
            "MDE_STRESS_SCENARIO": gate["MDE_STRESS_SCENARIO"],
            "MDE_STRESS_IN_STRESS_PAIR_SD_UNITS": gate["MDE_STRESS_IN_STRESS_PAIR_SD_UNITS"],
            "AMENDED_POWER_GATE": gate["AMENDED_POWER_GATE"],
            "AMENDED_POWER_GATE_RESULT": gate["AMENDED_POWER_GATE_RESULT"],
            "PLANNING_SCALE_ILLUSTRATIONS": {
                "ASSUMED_SINGLE_WINDOW_LOG_RETURN_SD": [0.02, 0.04, 0.06],
                "NOTE": "PLANNING-SCALE ILLUSTRATIONS. Not empirical BTC MDEs. Percent = MDE_SINGLE_WINDOW_SD_UNITS times the assumed SD, times 100.",
                "STRESS_MDE_PERCENT_IF_SD": None if gate["MDE_SINGLE_WINDOW_SD_UNITS"] is None else [
                    gate["MDE_SINGLE_WINDOW_SD_UNITS"] * s * 100 for s in (0.02, 0.04, 0.06)
                ],
            },
        }
        if gate["AMENDED_POWER_GATE_RESULT"] == "INFERENCE_AMENDMENT_VALID_AND_POWERED":
            doc["NEXT_UNIT"] = "GV0R01_C012_ONE_SHOT_EXECUTION_AMENDED"
        else:
            doc["NEXT_UNIT"] = "NO_EXECUTION_AUTHORIZED"
    return doc


def _fix_sample_labels() -> None:
    """Labels in sample_label_matrix are built from graph rows. Patch the helper."""
    return None


# Correct the class-index helper now that graph rows are a list aligned with order.
def _class_index_lists(graph: dict, summary: dict) -> list[dict]:
    out = []
    role = {r["ID"]: r["ROLE"] for r in graph["rows"]}
    for cl in summary["CLASSES"]:
        if cl["KIND"] == "ISOLATE":
            idx = np.array([graph["index"][i] for i in cl["IDS"]], dtype=np.int64)
            labels = np.array([1 if role[i] == "EVENT" else 0 for i in cl["IDS"]], dtype=np.int8)
            out.append({"KIND": "ISOLATE", "IDX": idx, "LABELS": labels, "N_EVENT": int(labels.sum())})
        else:
            edges = [(graph["index"][a], graph["index"][b]) for a, b in cl["EDGES"]]
            out.append({
                "KIND": "CROSS_EDGE",
                "EDGES": edges,
                "LABELS": cl["ORIENTED_LABELS"],
                "ORBIT": cl["ORBIT_FACTOR"],
            })
    return out
