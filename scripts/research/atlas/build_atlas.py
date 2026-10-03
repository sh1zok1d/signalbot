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
Append-only:
    ATLAS_EVENTS_V1.jsonl              hash-chained change events; every change of the sources appends one

    python -m scripts.research.atlas.build_atlas --append-event --change-type GOVERNANCE_RECORD \
        --reason "..." --record docs/research/SOME_RECORD.md
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
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
EVENTS = ATLAS_DIR / "ATLAS_EVENTS_V1.jsonl"
MEMORY = ROOT / "docs" / "research" / "MECHANISM_MEMORY_V0.json"
GOVERNANCE = ROOT / "docs" / "research" / "GOVERNANCE_REGION_AUTHORITY_V0.json"
BLIND = ROOT / "docs" / "research" / "BLIND_MECHANISM_MAP_V0.json"
FINDINGS = ROOT / "config" / "beta_research_findings.yaml"
DESIGN = ROOT / "docs" / "research" / "HYPOTHESIS_GENERATOR_V0_DESIGN.json"

VERSION = "SIGNALBOT_RESEARCH_ATLAS_V1"
TESTED_STATES = ("CONFIRMED", "LIVE_SIGNAL", "NO_STRUCTURE", "CLOSED_ON_SURFACE")
NEEDS_REOPEN = TESTED_STATES + ("INFORMATIONALLY_WEAK", "FUTURE_NATURAL_ACCUMULATION", "BLOCKED_METHOD",
                                "BLOCKED_DATA", "BLOCKED_GOVERNANCE", "EXPOSED_ONLY", "CANDIDATE_UNTESTED",
                                "CLOSED_BEFORE_START")
NON_MEMORY_REQUIRED = ("title", "program", "mechanism", "function", "verdict", "records")
# what the generator view may say about a cell (outcome-neutral)
GEN_OPEN, GEN_PRIOR, GEN_DATA, GEN_WEAK = "OPEN", "PRIOR_WORK", "DATA_REQUIRED", "UNDERPOWERED_NOW"
PRIOR_STATES = ("CONFIRMED", "LIVE_SIGNAL", "NO_STRUCTURE", "CLOSED_ON_SURFACE", "EXPOSED_ONLY", "CANDIDATE_UNTESTED",
                "BLOCKED_METHOD", "BLOCKED_GOVERNANCE", "CLOSED_BEFORE_START")
ABBR = {"OPEN_FRONTIER": "·", "CANDIDATE_UNTESTED": "CU", "BLOCKED_METHOD": "BM", "BLOCKED_DATA": "BD",
        "INFORMATIONALLY_WEAK": "IW", "FUTURE_NATURAL_ACCUMULATION": "FA", "EXPOSED_ONLY": "EX",
        "BLOCKED_GOVERNANCE": "BG", "CLOSED_BEFORE_START": "CB",
        "CONFIRMED": "CF", "LIVE_SIGNAL": "LS", "NO_STRUCTURE": "NS", "CLOSED_ON_SURFACE": "CS"}
LENS = "LENS"  # datasets that only define when something happens (calendars, synthetic DGPs); never a data column
RECONCILIATION_KINDS = ("POST_MEMORY_RECORD", "ATLAS_CLASSIFICATION")
RESERVATION_STATUSES = ("RESERVED", "RELEASED", "CONSUMED")
EVENT_TYPES = ("INITIAL_TRANSFER", "GOVERNANCE_RECORD", "UNIT_ADDED", "UNIT_STATE_CHANGE", "UNIT_TEXT_CHANGE",
               "TAXONOMY_CHANGE", "SURFACE_CHANGE", "RESERVATION_CHANGE", "RECONCILIATION")
BLIND_ONLY_FIELDS = ("blind_mechanism", "blind_function")
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
    unit_ids = {u["id"] for u in units_doc["units"]}
    reservations = {r["id"]: r for r in surf.get("reservations") or ()}
    problems += _validate_reservations(surf, ds, unit_ids)
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
        if u.get("state") == "BLOCKED_GOVERNANCE":
            if not u.get("blocker"):
                problems.append(f"{uid}: BLOCKED_GOVERNANCE needs blocker")
            if u.get("blocker") == "HOLDOUT_OVERLAP" and u.get("reservation") not in reservations:
                problems.append(f"{uid}: HOLDOUT_OVERLAP must name a reservation")
        if u.get("state") == "CLOSED_BEFORE_START" and not u.get("why_closed"):
            problems.append(f"{uid}: CLOSED_BEFORE_START needs why_closed")
        if u.get("memory") and any(u.get(k) for k in BLIND_ONLY_FIELDS):
            problems.append(f"{uid}: memory units take their blind texts from BLIND_MECHANISM_MAP_V0")
        for rec in u.get("records") or ():
            if not (ROOT / rec.split("#")[0]).exists():
                problems.append(f"{uid}: record {rec} not found")
    covered = {u["id"] for u in units_doc["units"] if u.get("memory")}
    problems += [f"memory entry {k} has no atlas unit" for k in memory if k not in covered]
    problems += _validate_reconciliation(units_doc, memory)
    ids = {u["id"] for u in units_doc["units"]} | {a for u in units_doc["units"] for a in (u.get("aliases") or ())}
    problems += [f"findings registry id {f} has no atlas unit or alias" for f in findings if f not in ids]
    return problems


def _validate_reservations(surf, ds, unit_ids) -> list:
    problems = []
    for r in surf.get("reservations") or ():
        rid = r.get("id")
        for k in ("id", "status", "datasets", "period", "scope", "intended_use", "holder_units", "authority"):
            if not r.get(k):
                problems.append(f"reservation {rid}: missing {k}")
        if r.get("status") not in RESERVATION_STATUSES:
            problems.append(f"reservation {rid}: invalid status {r.get('status')}")
        if r.get("status") == "RESERVED" and r.get("permit_required") is not True:
            problems.append(f"reservation {rid}: a RESERVED surface needs permit_required: true")
        if r.get("status") == "CONSUMED" and not r.get("permit"):
            problems.append(f"reservation {rid}: CONSUMED needs the permit that consumed it")
        if r.get("datasets") != "*":
            for d in r.get("datasets") or ():
                if d not in ds:
                    problems.append(f"reservation {rid}: unknown dataset {d}")
        period = r.get("period") or {}
        if r.get("period") and not (period.get("start") and period.get("end_exclusive")):
            problems.append(f"reservation {rid}: period needs start and end_exclusive")
        for u in r.get("holder_units") or ():
            if u not in unit_ids:
                problems.append(f"reservation {rid}: unknown holder unit {u}")
        for rec in list(r.get("authority") or ()) + ([r["permit"]] if r.get("permit") else []):
            if not (ROOT / rec.split("#")[0]).exists():
                problems.append(f"reservation {rid}: record {rec} not found")
    return problems


def memory_implied_state(status, rules):
    """The atlas state the frozen memory status would map to (first matching rule)."""
    for r in rules:
        if re.search(r["pattern"], status or ""):
            return r["state"]
    return None


def _validate_reconciliation(units_doc, memory) -> list:
    """Every memory unit whose atlas state differs from the state its memory status implies needs an explicit,
    current reconciliation entry; memory itself is never edited."""
    problems = []
    rules = units_doc.get("memory_status_map") or []
    recs = {r["id"]: r for r in units_doc.get("memory_reconciliation") or ()}
    for k, n in Counter(r["id"] for r in units_doc.get("memory_reconciliation") or ()).items():
        if n > 1:
            problems.append(f"reconciliation {k}: duplicate entry")
    units = {u["id"]: u for u in units_doc["units"] if u.get("memory")}
    for uid, u in units.items():
        if uid not in memory:
            continue
        status = memory[uid].get("STATUS_EVIDENCE_CLASS")
        implied = memory_implied_state(status, rules)
        if implied is None:
            problems.append(f"{uid}: memory status not covered by memory_status_map")
            continue
        r = recs.get(uid)
        if implied == u["state"]:
            if r:
                problems.append(f"reconciliation {uid}: stale entry (atlas state equals the memory-implied state)")
            continue
        if not r:
            problems.append(f"{uid}: atlas state {u['state']} differs from memory-implied {implied} without a reconciliation entry")
            continue
        if r.get("kind") not in RECONCILIATION_KINDS:
            problems.append(f"reconciliation {uid}: invalid kind {r.get('kind')}")
        if r.get("memory_status") != status:
            problems.append(f"reconciliation {uid}: memory_status no longer matches the memory chain; review the entry")
        if r.get("memory_implied_state") != implied:
            problems.append(f"reconciliation {uid}: memory_implied_state should be {implied}")
        if r.get("atlas_state") != u["state"]:
            problems.append(f"reconciliation {uid}: atlas_state should be {u['state']}")
        if not r.get("reason"):
            problems.append(f"reconciliation {uid}: missing reason")
        if r.get("kind") == "POST_MEMORY_RECORD" and not r.get("records"):
            problems.append(f"reconciliation {uid}: POST_MEMORY_RECORD needs the records that changed the status")
        for rec in r.get("records") or ():
            if not (ROOT / rec.split("#")[0]).exists():
                problems.append(f"reconciliation {uid}: record {rec} not found")
    for uid in recs:
        if uid not in units:
            problems.append(f"reconciliation {uid}: not a memory unit")
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
    rules = units_doc.get("memory_status_map") or []
    recs = {r["id"]: r for r in units_doc.get("memory_reconciliation") or ()}
    for u in units_doc["units"]:
        rec = {}
        if u.get("memory"):
            rec.update(_memory_texts(u["id"], memory, gov))
            rec["records"] = rec["records"] + list(u.get("records") or ())
            status = memory[u["id"]].get("STATUS_EVIDENCE_CLASS")
            rec["memory_status"] = status
            rec["memory_implied_state"] = memory_implied_state(status, rules)
            rec["routing_authority"] = VERSION
            if u["id"] in recs:
                rec["reconciliation"] = {k: v for k, v in recs[u["id"]].items() if k != "id"}
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
        if d.get("_fully_reserved"):
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
    surf = _mark_reservations(surf)
    units = full_units(units_doc, memory, gov)
    by_id = {u["id"]: u for u in units}
    cell_list = cells(tax, surf, units, priorities)
    digest = sources_digest(_load_yaml(TAXONOMY), _load_yaml(SURFACES), units_doc, memory, findings)
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
            "MEMORY_RECONCILIATION": units_doc.get("memory_reconciliation") or [],
            "RESERVATIONS": surf.get("reservations") or [],
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
    event_problems = verify_events(load_events(), digest, unit_index(units_doc))
    if check_only:
        if stale:
            raise AtlasError("derived atlas files are stale: " + ", ".join(stale)
                             + " (run python -m scripts.research.atlas.build_atlas)")
        if event_problems:
            raise AtlasError("atlas event chain:\n  " + "\n  ".join(event_problems))
    else:
        for p, text in outputs.items():
            p.write_text(text, encoding="utf-8")
    return {"digest": digest, "units": len(units), "frontier": len(frontier), "stale": stale,
            "event_required": bool(event_problems)}


def sources_digest(tax, surf, units_doc, memory, findings) -> str:
    return _digest({"taxonomy": tax, "surfaces": surf, "units": units_doc,
                    "memory_ids": sorted(memory), "findings_ids": sorted(findings)})


def _mark_reservations(surf):
    """Datasets wholly held by an active reservation are invisible to discovery; period reservations become
    unavailable periods. Works on a copy; the digest is computed from the unmodified sources."""
    surf = json.loads(json.dumps(surf, default=str))
    active = [r for r in surf.get("reservations") or () if r.get("status") == "RESERVED"]
    for d in surf["datasets"]:
        periods = []
        for r in active:
            if r["datasets"] == "*" or d["id"] in r["datasets"]:
                if r.get("period"):
                    periods.append({"start": r["period"]["start"], "end_exclusive": r["period"]["end_exclusive"]})
                else:
                    d["_fully_reserved"] = True
        if periods:
            d["_unavailable_periods"] = periods
    return surf


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
        return {"id": uid, "mechanism": scrub(u.get("blind_mechanism") or u["mechanism"]),
                "function": scrub(u.get("blind_function") or u.get("title") or u["function"])}

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
    surfaces = []
    for d in surf["datasets"]:
        if d.get("_fully_reserved"):
            continue  # a reserved confirmation surface is invisible to exploratory generation
        entry = {"id": d["id"], "col": d["col"], "also_cols": d.get("also_cols") or [], "coverage": d.get("coverage"),
                 "availability": d["availability"]}
        if d.get("_unavailable_periods"):
            entry["unavailable_periods"] = d["_unavailable_periods"]
        surfaces.append(entry)
    view = {"ATLAS": VERSION, "VIEW": "GENERATOR_BLIND", "SOURCES_DIGEST": digest,
            "RULES": {
                "OPEN": "Unexplored. Generate here first, highest frontier_value first.",
                "PRIOR_WORK": "Prior signatures exist. A new card must be an orthogonal mechanism, use a data surface the "
                              "prior signatures did not use, or resolve a named blocker; never a parameter neighbour or relabel.",
                "DATA_REQUIRED": "No usable data surface yet. A card here must name the data it needs and how it would be obtained.",
                "UNDERPOWERED_NOW": "Too few independent units today. Do not generate until the revisit point.",
                "UNAVAILABLE_PERIODS": "A surface's unavailable_periods may not be read, used or proposed for any card.",
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
    L.append("## Reserved confirmation surfaces")
    L.append("")
    for r in surf.get("reservations") or ():
        per = r.get("period") or {}
        L.append(f"- `{r['id']}` {r['status']}: {r['datasets'] if r['datasets'] == '*' else ', '.join(r['datasets'])}"
                 + (f" [{per.get('start')}, {per.get('end_exclusive')})" if per else "")
                 + f" — {_short(r['intended_use'], 200)} (holders: {', '.join(r['holder_units'])})")
    if not surf.get("reservations"):
        L.append("- none")
    L.append("")
    L.append("## Memory reconciliation (memory preserved; the atlas is the routing authority)")
    L.append("")
    L.append("| Unit | Kind | Memory status (preserved) | Memory implies | Atlas state | Reason |")
    L.append("|---|---|---|---|---|---|")
    for u in units:
        r = u.get("reconciliation")
        if r:
            L.append(f"| {u['id']} | {r['kind']} | {_short(r['memory_status'], 70)} | {r['memory_implied_state']} | "
                     f"**{r['atlas_state']}** | {_short(r['reason'], 160)} |")
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


# ---- append-only event chain ----------------------------------------------------------------------
def unit_index(units_doc) -> dict:
    """Per-unit content digest and cell, so an event can state exactly what changed."""
    return {u["id"]: {"d": hashlib.sha256(json.dumps(u, sort_keys=True, ensure_ascii=False, default=str)
                                          .encode("utf-8")).hexdigest()[:16],
                      "cell": f"{u['row']}|{u['col']}"} for u in units_doc["units"]}


def event_hash(event) -> str:
    body = {k: v for k, v in event.items() if k != "event_hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def load_events(path=None) -> list:
    path = path or EVENTS
    if not Path(path).exists():
        return []
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def verify_events(events, digest=None, index=None) -> list:
    """The chain is intact (hashes, links, contiguous sequence, prior digests) and its head is the current atlas."""
    problems = []
    if not events:
        return ["no atlas events recorded"]
    prev = None
    for i, ev in enumerate(events):
        tag = f"event {ev.get('seq')}"
        if ev.get("seq") != i + 1:
            problems.append(f"{tag}: sequence must be {i + 1}")
        if ev.get("event_hash") != event_hash(ev):
            problems.append(f"{tag}: hash does not match its content (an event was rewritten)")
        if ev.get("change_type") not in EVENT_TYPES:
            problems.append(f"{tag}: unknown change_type {ev.get('change_type')}")
        if not ev.get("reason") or not ev.get("source_records") or not ev.get("timestamp"):
            problems.append(f"{tag}: needs reason, source_records and timestamp")
        if prev is None:
            if ev.get("prev_event_hash") is not None or ev.get("prior_atlas_digest") is not None:
                problems.append(f"{tag}: the first event has no predecessor")
        else:
            if ev.get("prev_event_hash") != prev["event_hash"]:
                problems.append(f"{tag}: prev_event_hash does not link to event {prev.get('seq')}")
            if ev.get("prior_atlas_digest") != prev.get("new_atlas_digest"):
                problems.append(f"{tag}: prior_atlas_digest is not the previous event's new digest")
            if ev.get("timestamp", "") < prev.get("timestamp", ""):
                problems.append(f"{tag}: timestamp earlier than event {prev.get('seq')}")
        prev = ev
    if digest is not None and prev.get("new_atlas_digest") != digest:
        problems.append("the atlas sources changed after the last event; append one with --append-event")
    if index is not None and digest is not None and prev.get("new_atlas_digest") == digest and prev.get("unit_index") != index:
        problems.append("the last event's unit index does not match the current units")
    return problems


def layer_digests(tax, surf, units_doc) -> dict:
    return {"taxonomy": _digest(tax), "surfaces": _digest(surf), "units": _digest(units_doc)}


def make_event(prev, change_type, reason, records, new_digest, new_index, old_index, timestamp, layer_digests) -> dict:
    if change_type not in EVENT_TYPES:
        raise AtlasError(f"unknown change_type {change_type}")
    if not reason or not records:
        raise AtlasError("an atlas event needs a reason and at least one source record")
    for rec in records:
        if not (ROOT / rec.split("#")[0]).exists():
            raise AtlasError(f"source record {rec} not found")
    old_index = old_index or {}
    added = sorted(set(new_index) - set(old_index))
    removed = sorted(set(old_index) - set(new_index))
    changed = sorted(k for k in set(new_index) & set(old_index) if new_index[k]["d"] != old_index[k]["d"])
    cells = sorted({new_index[k]["cell"] for k in added + changed} | {old_index[k]["cell"] for k in removed + changed})
    ev = {"seq": (prev["seq"] + 1) if prev else 1, "timestamp": timestamp, "change_type": change_type,
          "prior_atlas_digest": prev["new_atlas_digest"] if prev else None, "new_atlas_digest": new_digest,
          "prev_event_hash": prev["event_hash"] if prev else None,
          "affected_units": {"added": added, "removed": removed, "changed": changed}, "affected_cells": cells,
          "affected_layers": sorted(k for k, v in layer_digests.items()
                                    if not prev or (prev.get("layer_digests") or {}).get(k) != v),
          "layer_digests": layer_digests, "source_records": list(records), "reason": reason, "unit_index": new_index}
    ev["event_hash"] = event_hash(ev)
    return ev


def append_event(change_type, reason, records, timestamp=None) -> dict:
    tax, surf, units_doc = _load_yaml(TAXONOMY), _load_yaml(SURFACES), _load_yaml(UNITS)
    memory = _load_json(MEMORY)["ENTRIES"]
    findings = [f["id"] for f in (_load_yaml(FINDINGS) or {}).get("findings") or ()]
    problems = validate(tax, surf, units_doc, memory, findings)
    if problems:
        raise AtlasError("atlas sources invalid:\n  " + "\n  ".join(problems))
    events = load_events()
    chain = verify_events(events) if events else []
    if chain:
        raise AtlasError("atlas event chain broken; fix it before appending:\n  " + "\n  ".join(chain))
    digest = sources_digest(tax, surf, units_doc, memory, findings)
    prev = events[-1] if events else None
    if prev and prev["new_atlas_digest"] == digest:
        raise AtlasError("nothing changed since the last event")
    ev = make_event(prev, change_type, reason, records, digest, unit_index(units_doc),
                    prev.get("unit_index") if prev else None,
                    timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    layer_digests(tax, surf, units_doc))
    with open(EVENTS, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(ev, sort_keys=True, ensure_ascii=False) + "\n")
    return ev


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="validate and fail if derived files or the event chain are stale")
    ap.add_argument("--append-event", action="store_true", help="append a hash-chained change event for the current sources")
    ap.add_argument("--change-type", choices=EVENT_TYPES)
    ap.add_argument("--reason")
    ap.add_argument("--record", action="append", default=[])
    args = ap.parse_args(argv)
    try:
        if args.append_event:
            ev = append_event(args.change_type, args.reason, args.record)
            print(json.dumps({k: ev[k] for k in ("seq", "change_type", "prior_atlas_digest", "new_atlas_digest",
                                                 "affected_units", "event_hash")}, sort_keys=True))
            return 0
        rep = build(check_only=args.check)
    except AtlasError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(rep, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
