"""Build SIGNALBOT_RESEARCH_ATLAS_V1 from its hand-maintained sources.

    python -m scripts.research.atlas.build_atlas            # write the derived files
    python -m scripts.research.atlas.build_atlas --check    # fail if they are stale or invalid

Sources (hand-maintained, docs/research/atlas/):
    ATLAS_TAXONOMY_V1.yaml   rows (mechanisms), columns (data surfaces), states, reopen rules
    ATLAS_SURFACES_V1.yaml   datasets per column: coverage, availability, exposure
    ATLAS_UNITS_V1.yaml      every research unit placed on the map
Read-only inputs (never edited here): MECHANISM_MEMORY_V0.json, GOVERNANCE_REGION_AUTHORITY_V0.json,
BLIND_MECHANISM_MAP_V0.json (derived caches of the generator memory chain),
config/beta_research_findings.yaml, HYPOTHESIS_GENERATOR_V0_DESIGN.json (scrub denylist).

Derived (never edit by hand):
    SIGNALBOT_RESEARCH_ATLAS_V1.json   full governance view (verdicts, numbers, why closed, reopen)
    ATLAS_GENERATOR_VIEW_V1.json       outcome-blind view for hypothesis generators
    ATLAS_MATRIX_V1.md                 human-readable matrix, frontier and cell details
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
ATLAS_DIR = ROOT / "docs" / "research" / "atlas"
TAXONOMY = ATLAS_DIR / "ATLAS_TAXONOMY_V1.yaml"
SURFACES = ATLAS_DIR / "ATLAS_SURFACES_V1.yaml"
UNITS = ATLAS_DIR / "ATLAS_UNITS_V1.yaml"
OUT_FULL = ATLAS_DIR / "SIGNALBOT_RESEARCH_ATLAS_V1.json"
OUT_GENERATOR = ATLAS_DIR / "ATLAS_GENERATOR_VIEW_V1.json"
OUT_MATRIX = ATLAS_DIR / "ATLAS_MATRIX_V1.md"
MEMORY = ROOT / "docs" / "research" / "MECHANISM_MEMORY_V0.json"
GOVERNANCE = ROOT / "docs" / "research" / "GOVERNANCE_REGION_AUTHORITY_V0.json"
BLIND = ROOT / "docs" / "research" / "BLIND_MECHANISM_MAP_V0.json"
FINDINGS = ROOT / "config" / "beta_research_findings.yaml"
DESIGN = ROOT / "docs" / "research" / "HYPOTHESIS_GENERATOR_V0_DESIGN.json"

VERSION = "SIGNALBOT_RESEARCH_ATLAS_V1"
TESTED_STATES = ("CONFIRMED", "LIVE_SIGNAL", "NO_STRUCTURE", "CLOSED_ON_SURFACE")
NEEDS_REOPEN = TESTED_STATES + ("INFORMATIONALLY_WEAK", "FUTURE_NATURAL_ACCUMULATION", "BLOCKED_METHOD",
                                "BLOCKED_DATA", "EXPOSED_ONLY", "CANDIDATE_UNTESTED")
NON_MEMORY_REQUIRED = ("title", "program", "mechanism", "function", "verdict", "records")
# what the generator view may say about a cell (outcome-neutral)
GEN_OPEN, GEN_PRIOR, GEN_DATA, GEN_WEAK = "OPEN", "PRIOR_WORK", "DATA_REQUIRED", "UNDERPOWERED_NOW"
PRIOR_STATES = ("CONFIRMED", "LIVE_SIGNAL", "NO_STRUCTURE", "CLOSED_ON_SURFACE", "EXPOSED_ONLY", "CANDIDATE_UNTESTED", "BLOCKED_METHOD")
ABBR = {"OPEN_FRONTIER": "·", "CANDIDATE_UNTESTED": "CU", "BLOCKED_METHOD": "BM", "BLOCKED_DATA": "BD",
        "INFORMATIONALLY_WEAK": "IW", "FUTURE_NATURAL_ACCUMULATION": "FA", "EXPOSED_ONLY": "EX",
        "CONFIRMED": "CF", "LIVE_SIGNAL": "LS", "NO_STRUCTURE": "NS", "CLOSED_ON_SURFACE": "CS"}
LENS = "LENS"  # datasets that only define when something happens (calendars, synthetic DGPs); never a data column
GEN_FORBIDDEN_KEYS = ("verdict", "key_numbers", "why_closed", "state", "states", "note", "practical_bar")


class AtlasError(ValueError):
    pass


def _load_yaml(path):
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _scrubber():
    from scripts.research.generator_v0.memory_finalizer import scrub
    design = _load_json(DESIGN)
    return lambda text: scrub(text, design) if text else text


# ---- validation ---------------------------------------------------------------------------------
def validate(tax, surf, units_doc, memory, findings) -> list:
    problems = []
    cols = [c["id"] for c in tax["columns"]]
    rows = [f"{r['id']}.{x['id']}" for r in tax["regions"] for x in r["rows"]]
    applicable = {rid: r["cols"] for rid, r in _row_index(tax).items()}
    known_ds = {d["id"] for d in surf["datasets"]}
    for rid, r in _row_index(tax).items():
        for d in r.get("needs") or ():
            if d not in known_ds:
                problems.append(f"row {rid}: needs unknown dataset {d}")
    for rid, rc in applicable.items():
        if not rc:
            problems.append(f"row {rid}: no applicable columns")
        for c in rc:
            if c not in cols:
                problems.append(f"row {rid}: unknown applicable column {c}")
    for name, ids in (("column", cols), ("row", rows)):
        dup = [k for k, n in Counter(ids).items() if n > 1]
        if dup:
            problems.append(f"duplicate {name} ids: {dup}")
    states = set(tax["states"])
    if set(tax["cell_precedence"]) != states:
        problems.append("cell_precedence must list every state exactly once")
    ds = {d["id"]: d for d in surf["datasets"]}
    for d in surf["datasets"]:
        for c in [d["col"]] + list(d.get("also_cols") or ()):
            if c not in cols and c != LENS:
                problems.append(f"dataset {d['id']}: unknown column {c}")
        for e in d.get("exposure") or ():
            for r in e.get("rows") or ():
                if r not in rows and r not in {x["id"] for x in tax["regions"]}:
                    problems.append(f"dataset {d['id']}: exposure row {r} unknown")
    for c in cols:
        if c not in (surf.get("columns") or {}):
            problems.append(f"surfaces: column {c} has no confirmation_path entry")
    seen = Counter(u["id"] for u in units_doc["units"])
    problems += [f"duplicate unit id {k}" for k, n in seen.items() if n > 1]
    for u in units_doc["units"]:
        uid = u["id"]
        if u.get("row") not in rows:
            problems.append(f"{uid}: unknown row {u.get('row')}")
        if u.get("col") not in cols:
            problems.append(f"{uid}: unknown column {u.get('col')}")
        elif u.get("row") in applicable and u["col"] not in applicable[u["row"]]:
            problems.append(f"{uid}: column {u['col']} is not applicable to row {u['row']}")
        if u.get("state") not in states or u.get("state") == "OPEN_FRONTIER":
            problems.append(f"{uid}: invalid unit state {u.get('state')}")
        for d in u.get("datasets") or ():
            if d not in ds:
                problems.append(f"{uid}: unknown dataset {d}")
        if not u.get("datasets"):
            problems.append(f"{uid}: no datasets")
        if u.get("memory"):
            if uid not in memory:
                problems.append(f"{uid}: memory unit missing from MECHANISM_MEMORY_V0")
        else:
            for k in NON_MEMORY_REQUIRED:
                if not u.get(k):
                    problems.append(f"{uid}: missing {k}")
            if u.get("state") in NEEDS_REOPEN and not u.get("reopen"):
                problems.append(f"{uid}: missing reopen")
            if u.get("state") in TESTED_STATES + ("INFORMATIONALLY_WEAK",) and not u.get("why_closed"):
                problems.append(f"{uid}: missing why_closed")
            if u.get("state") in TESTED_STATES and not u.get("forbidden"):
                problems.append(f"{uid}: missing forbidden")
        if u.get("state") == "FUTURE_NATURAL_ACCUMULATION" and not u.get("revisit"):
            problems.append(f"{uid}: FUTURE_NATURAL_ACCUMULATION needs revisit")
        for rec in u.get("records") or ():
            if not (ROOT / rec.split("#")[0]).exists():
                problems.append(f"{uid}: record {rec} not found")
    covered = {u["id"] for u in units_doc["units"] if u.get("memory")}
    problems += [f"memory entry {k} has no atlas unit" for k in memory if k not in covered]
    ids = {u["id"] for u in units_doc["units"]} | {a for u in units_doc["units"] for a in (u.get("aliases") or ())}
    problems += [f"findings registry id {f} has no atlas unit or alias" for f in findings if f not in ids]
    return problems


# ---- derivation ---------------------------------------------------------------------------------
def _memory_texts(uid, memory, gov):
    e, g = memory[uid], gov.get(uid, {})
    reopen = e.get("WHAT_REMAINS_OPEN")
    if g.get("BLOCKER_RESOLUTION_REQUIREMENT_IF_ANY"):
        reopen = f"{reopen} Blocker requirement: {g['BLOCKER_RESOLUTION_REQUIREMENT_IF_ANY']}"
    forbidden = "; ".join(x for x in (e.get("NEIGHBOR_RESCUE_WARNING"), g.get("ANTI_RESCUE_SCOPE")) if x)
    return {"title": e.get("MECHANISM"), "mechanism": e.get("MECHANISM"), "function": e.get("FUNCTION"),
            "target": e.get("TARGET_FAMILY"), "what_tested": e.get("WHAT_WAS_ACTUALLY_TESTED"),
            "verdict": e.get("STATUS_EVIDENCE_CLASS"), "why_closed": e.get("WHAT_THE_RESULT_DEPRIORITIZES_OR_CLOSES"),
            "reopen": reopen, "forbidden": forbidden or None, "information_source": e.get("INFORMATION_SOURCE"),
            "data_state": e.get("DATA_STATE"), "program": e.get("GENERATION"),
            "blocker": g.get("BLOCKER_CLASS_IF_ANY"), "governance_state": g.get("STATE"),
            "records": ["docs/research/MECHANISM_MEMORY_V0.json#" + uid]}


def full_units(units_doc, memory, gov) -> list:
    out = []
    for u in units_doc["units"]:
        rec = {}
        if u.get("memory"):
            rec.update(_memory_texts(u["id"], memory, gov))
            rec["records"] = rec["records"] + list(u.get("records") or ())
        for k, v in u.items():
            if k == "records" and u.get("memory"):
                continue
            if k != "memory" and v is not None:
                rec[k] = v
        rec["source"] = "MECHANISM_MEMORY_V0" if u.get("memory") else "ATLAS_UNITS_V1"
        out.append(rec)
    return sorted(out, key=lambda r: (r["row"], r["col"], r["id"]))


def _row_index(tax):
    out = {}
    for reg in tax["regions"]:
        for r in reg["rows"]:
            out[f"{reg['id']}.{r['id']}"] = dict(r, region=reg["id"], region_name=reg["name"],
                                                 cols=list(r.get("cols") or reg.get("cols") or ()),
                                                 frontier=reg.get("frontier", True))
    return out


def readiness(row, region, col, surf, units_by_dataset_rows, only=None) -> int:
    """Best outcome-neutral readiness of one column for one row (see the taxonomy comment)."""
    best = 0
    for d in surf["datasets"]:
        if col not in [d["col"]] + list(d.get("also_cols") or ()):
            continue
        if only and d["id"] not in only:
            continue
        avail = d["availability"]
        if avail in ("NOT_AVAILABLE", "BLOCKED"):
            continue
        if avail in ("FORWARD_ONLY", "LIVE_PRODUCT"):
            best = max(best, 1)
            continue
        exposed_all = any(e.get("scope") == "ALL" for e in d.get("exposure") or ())
        exposed_row = any(row in (e.get("rows") or ()) or region in (e.get("rows") or ())
                          for e in d.get("exposure") or ())
        exposed = exposed_all or exposed_row or row in units_by_dataset_rows.get(d["id"], set())
        if avail == "ACQUIRABLE":
            best = max(best, 1 if exposed else 2)
        else:
            best = max(best, 2 if exposed else 3)
    return best


def cell_readiness(row, region, col, native, surf, used_rows, needs=None) -> int:
    """A non-native column means the native layer plus this layer: both must be available. `needs`
    restricts the native layer to the datasets that can serve the row."""
    native_ready = readiness(row, region, native, surf, used_rows, only=needs)
    if col == native:
        return native_ready
    return min(readiness(row, region, col, surf, used_rows), native_ready)


def cells(tax, surf, units, priorities) -> list:
    rows = _row_index(tax)
    prec = tax["cell_precedence"]
    by_cell = defaultdict(list)
    for u in units:
        by_cell[(u["row"], u["col"])].append(u)
    row_count = Counter(u["row"] for u in units)
    used_rows = defaultdict(set)
    for u in units:
        for d in u.get("datasets") or ():
            used_rows[d].add(u["row"])
    conf = {c: int(v["confirmation_path"]) for c, v in surf["columns"].items()}
    out = []
    for rid, r in rows.items():
        for c in r["cols"]:
            us = by_cell.get((rid, c), [])
            counts = Counter(u["state"] for u in us)
            state = next((s for s in prec if counts.get(s)), "OPEN_FRONTIER")
            ready = cell_readiness(rid, r["region"], c, r["cols"][0], surf, used_rows, r.get("needs"))
            novelty = 0 if us else (2 if row_count.get(rid) else 3)
            saturation = min(3, row_count.get(rid, 0) // 3)
            prio = max([p["value"] for p in priorities
                        if p["target"] in (rid, r["region"], f"{rid}x{c}", f"{r['region']}x{c}", c)] + [0])
            confirm = min(conf[c], conf[r["cols"][0]])
            value = r["product_relevance"] + ready + novelty + confirm - saturation + prio
            revisit = sorted({str(u["revisit"]) for u in us if u.get("revisit")})
            out.append({"row": rid, "row_name": r["name"], "region": r["region"], "col": c, "native": c == r["cols"][0],
                        "frontier_eligible": r["frontier"], "state": state,
                        "mixed": len(counts) > 1, "counts": dict(sorted(counts.items())),
                        "units": sorted(u["id"] for u in us),
                        "value": {"total": value, "product_relevance": r["product_relevance"], "data_readiness": ready,
                                  "novelty": novelty, "confirmation_path": confirm, "saturation": saturation,
                                  "owner_priority": prio},
                        "revisit": revisit})
    return out


def generator_state(cell, units_by_id) -> str:
    states = [units_by_id[u]["state"] for u in cell["units"]]
    if any(s in PRIOR_STATES for s in states):
        return GEN_PRIOR
    if any(s in ("INFORMATIONALLY_WEAK", "FUTURE_NATURAL_ACCUMULATION") for s in states):
        return GEN_WEAK
    if states or cell["value"]["data_readiness"] == 0:
        return GEN_DATA
    return GEN_OPEN


def build(check_only=False) -> dict:
    tax, surf, units_doc = _load_yaml(TAXONOMY), _load_yaml(SURFACES), _load_yaml(UNITS)
    memory = _load_json(MEMORY)["ENTRIES"]
    gov = {r["SIGNATURE_ID"]: r for r in _load_json(GOVERNANCE)["ROWS"]}
    blind = _load_json(BLIND)
    findings = [f["id"] for f in (_load_yaml(FINDINGS) or {}).get("findings") or ()]
    problems = validate(tax, surf, units_doc, memory, findings)
    if problems:
        raise AtlasError("atlas sources invalid:\n  " + "\n  ".join(problems))
    priorities = list(tax.get("owner_priorities") or ())
    units = full_units(units_doc, memory, gov)
    by_id = {u["id"]: u for u in units}
    cell_list = cells(tax, surf, units, priorities)
    sources = {"taxonomy": _load_yaml(TAXONOMY), "surfaces": surf, "units": units_doc,
               "memory_ids": sorted(memory), "findings_ids": sorted(findings)}
    digest = _digest(sources)
    frontier = sorted((c for c in cell_list if c["state"] == "OPEN_FRONTIER" and c["frontier_eligible"]
                       and c["value"]["data_readiness"] > 0),
                      key=lambda c: (-c["value"]["total"], -c["value"]["owner_priority"],
                                     -c["value"]["product_relevance"], -c["value"]["data_readiness"], c["row"], c["col"]))
    data_blocked = sorted((c for c in cell_list if c["state"] == "OPEN_FRONTIER" and c["frontier_eligible"]
                           and c["value"]["data_readiness"] == 0),
                          key=lambda c: (-c["value"]["total"], c["row"], c["col"]))
    revisits = sorted(({"row": c["row"], "col": c["col"], "units": c["units"], "revisit": c["revisit"]}
                       for c in cell_list if c["revisit"]), key=lambda x: (x["revisit"], x["row"]))
    full = {"ATLAS": VERSION, "VIEW": "FULL_GOVERNANCE", "SOURCES_DIGEST": digest,
            "READERS": "HUMAN, SELECTOR, RED_TEAM (scoped), owner. Never generator context.",
            "COUNTS": {"units": len(units), "cells": len(cell_list),
                       "units_by_state": dict(sorted(Counter(u["state"] for u in units).items())),
                       "cells_by_state": dict(sorted(Counter(c["state"] for c in cell_list).items()))},
            "STATES": tax["states"], "REOPEN_KEYS": tax["reopen_keys"], "FORBIDDEN_MOVES": tax["forbidden_moves"],
            "FRONTIER_VALUE": tax["frontier_value"], "OWNER_PRIORITIES": priorities,
            "COLUMNS": tax["columns"], "REGIONS": tax["regions"], "SURFACES": surf,
            "UNITS": units, "CELLS": cell_list,
            "FRONTIER": [{"row": c["row"], "col": c["col"], "value": c["value"]} for c in frontier],
            "FRONTIER_NEEDS_DATA": [{"row": c["row"], "col": c["col"], "value": c["value"]} for c in data_blocked],
            "REVISIT_SCHEDULE": revisits}
    gen = generator_view(tax, surf, cell_list, by_id, blind, frontier, digest)
    matrix = render_matrix(tax, surf, cell_list, units, by_id, frontier, data_blocked, revisits, digest)
    outputs = {OUT_FULL: _dump(full), OUT_GENERATOR: _dump(gen), OUT_MATRIX: matrix}
    stale = [p.name for p, text in outputs.items() if not p.exists() or p.read_text(encoding="utf-8") != text]
    if check_only:
        if stale:
            raise AtlasError("derived atlas files are stale: " + ", ".join(stale)
                             + " (run python -m scripts.research.atlas.build_atlas)")
    else:
        for p, text in outputs.items():
            p.write_text(text, encoding="utf-8")
    return {"digest": digest, "units": len(units), "frontier": len(frontier), "stale": stale}


def _dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


# ---- the outcome-blind generator view ----------------------------------------------------------
def generator_view(tax, surf, cell_list, by_id, blind, frontier, digest) -> dict:
    scrub = _scrubber()

    def sig(uid):
        b = blind.get(uid)
        if b:
            return {"id": uid, "mechanism": b["MECHANISM"], "function": b["FUNCTION"]}
        # units outside the memory chain: the card's own short name stands in for the function, because the
        # record's function text carries design detail (tests, bars, horizons) that a generator must not see
        u = by_id[uid]
        return {"id": uid, "mechanism": scrub(u["mechanism"]), "function": scrub(u.get("title") or u["function"])}

    cells_out = []
    for c in cell_list:
        gs = generator_state(c, by_id)
        entry = {"row": c["row"], "col": c["col"], "native": c["native"], "generator_state": gs,
                 "prior_signature_count": len(c["units"]),
                 "data_readiness": c["value"]["data_readiness"], "frontier_value": c["value"]["total"]}
        if c["units"]:
            entry["prior_signatures"] = [sig(u) for u in c["units"]]
        if gs == GEN_WEAK and c["revisit"]:
            entry["revisit"] = c["revisit"]
        cells_out.append(entry)
    surfaces = [{"id": d["id"], "col": d["col"], "also_cols": d.get("also_cols") or [], "coverage": d.get("coverage"),
                 "availability": d["availability"]} for d in surf["datasets"]]
    view = {"ATLAS": VERSION, "VIEW": "GENERATOR_BLIND", "SOURCES_DIGEST": digest,
            "RULES": {
                "OPEN": "Unexplored. Generate here first, highest frontier_value first.",
                "PRIOR_WORK": "Prior signatures exist. A new card must be an orthogonal mechanism, use a data surface the "
                              "prior signatures did not use, or resolve a named blocker; never a parameter neighbour or relabel.",
                "DATA_REQUIRED": "No usable data surface yet. A card here must name the data it needs and how it would be obtained.",
                "UNDERPOWERED_NOW": "Too few independent units today. Do not generate until the revisit point.",
                "BLINDNESS": "This view carries no outcomes, verdicts, effect sizes or rankings by result.",
            },
            "COLUMNS": [{"id": c["id"], "name": c["name"], "covers": c["covers"]} for c in tax["columns"]],
            "ROWS": [{"row": rid, "name": r["name"], "region": r["region_name"], "native_column": r["cols"][0],
                      "applicable_columns": r["cols"]} for rid, r in _row_index(tax).items()],
            "SURFACES": surfaces, "CELLS": cells_out,
            "FRONTIER": [{"row": c["row"], "col": c["col"], "frontier_value": c["value"]["total"]} for c in frontier]}
    _assert_blind(view, scrub)
    return view


def _assert_blind(view, scrub):
    def walk(x, path=""):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in GEN_FORBIDDEN_KEYS:
                    raise AtlasError(f"generator view carries forbidden key {path}.{k}")
                walk(v, f"{path}.{k}")
        elif isinstance(x, list):
            for i, v in enumerate(x):
                walk(v, f"{path}[{i}]")
    walk(view)
    for c in view["CELLS"]:
        for s in c.get("prior_signatures") or ():
            for k in ("mechanism", "function"):
                if s[k] and scrub(s[k]) != " ".join(s[k].split()):
                    raise AtlasError(f"generator view text not scrubbed: {s['id']}.{k}")


# ---- the human matrix ---------------------------------------------------------------------------
def _cellcode(c) -> str:
    if c["state"] is None:
        return "—"
    if c["state"] == "OPEN_FRONTIER":
        return "·" if c["value"]["data_readiness"] else "∅"
    n = len(c["units"])
    code = ABBR[c["state"]] + (f"·{n}" if n > 1 else "")
    return code + ("*" if c["mixed"] else "")


def render_matrix(tax, surf, cell_list, units, by_id, frontier, data_blocked, revisits, digest) -> str:
    cols = [c["id"] for c in tax["columns"]]
    grid = {(c["row"], c["col"]): c for c in cell_list}
    na = {"row": None, "state": None}
    L = []
    L.append("# Signalbot Research Atlas V1 — matrix (derived)")
    L.append("")
    L.append("Generated by `python -m scripts.research.atlas.build_atlas` from `docs/research/atlas/*.yaml`. "
             "Do not edit by hand. Authority and rules: `docs/research/SIGNALBOT_RESEARCH_ATLAS_V1.md`.")
    L.append("")
    L.append(f"Sources digest: `{digest}`")
    L.append("")
    cnt = Counter(u["state"] for u in units)
    L.append(f"Units: {len(units)}. " + ", ".join(f"{k} {v}" for k, v in sorted(cnt.items())) + ".")
    L.append("")
    L.append("Legend: `·` open frontier with data · `∅` open, no usable data yet · `CU` candidate untested · "
             "`BM` blocked by method · `BD` blocked by data · `IW` informationally weak · `FA` future natural "
             "accumulation · `EX` exposed only · `CF` confirmed · `LS` live signal · `NS` no structure · `CS` closed on surface · "
             "`·n` number of units · `*` mixed states in the cell (the code shows the first by precedence) · "
             "`—` not applicable (the mechanism cannot be observed on this layer). The first applicable column of "
             "a row is its native layer; another column means the native layer plus that layer.")
    L.append("")
    L.append("## Matrix")
    L.append("")
    L.append("| Mechanism | " + " | ".join(cols) + " |")
    L.append("|---|" + "---|" * len(cols))
    for reg in tax["regions"]:
        L.append(f"| **{reg['name']}** |" + " |" * len(cols))
        for r in reg["rows"]:
            rid = f"{reg['id']}.{r['id']}"
            L.append(f"| {r['name']} | " + " | ".join(_cellcode(grid.get((rid, c), na)) for c in cols) + " |")
    L.append("")
    L.append("## Frontier (open cells with data, by frontier value)")
    L.append("")
    L.append("Value = product relevance + data readiness + novelty + confirmation path − saturation + owner priority "
             "(all outcome-neutral; definitions in the taxonomy).")
    L.append("")
    L.append("| # | Cell | Value | Product | Data | Novelty | Confirm | Saturation | Owner |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    rows = _row_index(tax)
    for i, c in enumerate(frontier[:40], 1):
        v = c["value"]
        L.append(f"| {i} | {rows[c['row']]['region_name']} / {c['row_name']} × {c['col']} | **{v['total']}** | "
                 f"{v['product_relevance']} | {v['data_readiness']} | {v['novelty']} | {v['confirmation_path']} | "
                 f"−{v['saturation']} | {v['owner_priority']} |")
    if len(frontier) > 40:
        L.append(f"| … | {len(frontier) - 40} more open cells in the JSON | | | | | | | |")
    L.append("")
    L.append(f"Open cells without a usable data surface: {len(data_blocked)} (listed in the JSON as FRONTIER_NEEDS_DATA).")
    L.append("")
    L.append("## Revisit schedule")
    L.append("")
    if revisits:
        for r in revisits:
            L.append(f"- {r['row']} × {r['col']} ({', '.join(r['units'])}): {'; '.join(r['revisit'])}")
    else:
        L.append("- none")
    L.append("")
    L.append("## Data surfaces")
    L.append("")
    L.append("| Dataset | Column | Coverage | Availability | Live in product |")
    L.append("|---|---|---|---|---|")
    for d in surf["datasets"]:
        cs = ", ".join([d["col"]] + list(d.get("also_cols") or ()))
        L.append(f"| `{d['id']}` | {cs} | {d.get('coverage') or '—'} | {d['availability']} | "
                 f"{'yes' if d.get('live_in_product') else 'no'} |")
    L.append("")
    L.append("## Cells with prior work")
    L.append("")
    for reg in tax["regions"]:
        block = []
        for r in reg["rows"]:
            rid = f"{reg['id']}.{r['id']}"
            for c in cols:
                cell = grid.get((rid, c))
                if not cell or not cell["units"]:
                    continue
                block.append(f"#### {r['name']} × {c} — {cell['state']}" + (" (mixed)" if cell["mixed"] else ""))
                block.append("")
                for uid in cell["units"]:
                    u = by_id[uid]
                    block.append(f"- **{uid}** `{u['state']}` — {_short(u.get('title') or u.get('mechanism'), 140)}")
                    if u.get("verdict"):
                        block.append(f"  - verdict: {_short(u['verdict'], 260)}")
                    if u.get("why_closed"):
                        block.append(f"  - why closed: {_short(u['why_closed'], 260)}")
                    if u.get("reopen"):
                        block.append(f"  - reopen: {_short(u['reopen'], 300)}")
                    if u.get("note"):
                        block.append(f"  - note: {_short(u['note'], 300)}")
                block.append("")
        if block:
            L.append(f"### {reg['name']}")
            L.append("")
            L.extend(block)
    return "\n".join(L).rstrip() + "\n"


def _short(text, n) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="validate and fail if derived files are stale")
    args = ap.parse_args(argv)
    try:
        rep = build(check_only=args.check)
    except AtlasError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(rep, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
