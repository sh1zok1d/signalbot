"""RESEARCH_HISTORY_AUDIT_V1 builder: census, completeness proof and per-unit table.

Reads the atlas (facts), the hand-written assessments (judgments) and every independent source of unit ids
(generator memory chain, scientific test ledger, bot findings registry, research ledger headings, research
file names). It fails if a unit is not assessed or an id in any source cannot be placed. It never edits a
source, a verdict or a sealed record.

    python -m scripts.research.history_audit            # write JSON + table
    python -m scripts.research.history_audit --check    # coverage proof only, no writes
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
ATLAS_JSON = ROOT / "docs/research/atlas/SIGNALBOT_RESEARCH_ATLAS_V1.json"
ATLAS_UNITS = ROOT / "docs/research/atlas/ATLAS_UNITS_V1.yaml"
ASSESSMENTS = ROOT / "docs/research/audit/RESEARCH_HISTORY_AUDIT_V1_ASSESSMENTS.yaml"
MEMORY = ROOT / "docs/research/MECHANISM_MEMORY_V0.json"
MEMORY_DELTAS = ROOT / "docs/research/generator_v0_memory/deltas"
TEST_LEDGER = ROOT / "docs/research/SCIENTIFIC_TEST_LEDGER.json"
FINDINGS = ROOT / "config/beta_research_findings.yaml"
RESEARCH_LEDGER = ROOT / "docs/RESEARCH_LEDGER.md"
OUT_JSON = ROOT / "docs/research/RESEARCH_HISTORY_AUDIT_V1.json"
OUT_TABLE = ROOT / "docs/research/RESEARCH_HISTORY_AUDIT_V1_TABLE.md"

VERSION = "RESEARCH_HISTORY_AUDIT_V1"
LEVELS = ("L0", "L1", "L2", "L3", "L4")
CONS = ("YES", "PARTLY", "NO", "NA")

# Test-ledger hypothesis ids that are spelled differently from the atlas id.
LEDGER_ALIASES = {"SEED0001-RD-V1": "SEED-0001"}

# Program -> the verdict framework the unit was judged under.
FRAMEWORKS = [
    ("BATCH01", "Batch01 development prereg: MPIE 0.10 vs matched random, structural and +6h controls, "
                "week-block bootstrap, 4/5 years, UP/DOWN symmetry, q/W/H neighbourhood (conjunction)"),
    ("BATCH02", "V2 Research Harness V1: five per-cell gates (primary, 2 % relative-MAE materiality, bootstrap, "
                "placebo, ordering) + horizon / parameter / year robustness"),
    ("DISCOVERY", "Hypothesis Discovery Pipeline V2: statistical + practical + temporal gates, one shot, adaptive discovery"),
    ("MARKET", "MARKET one-shot confirmatory contract (prereg freeze, ARM, reservation, sealed classification)"),
    ("OWNER_CARDS_R03", "Evaluation contract V1 + GV0R02 feasibility compiler: 0.5 comparator-SD bar, Holm, MDE stress, "
                        "replication MDE, product-frequency gate"),
    ("AUTOGEN_G01", "Evaluation contract V1 + feasibility compiler (as R03); red team / dedupe before compile"),
    ("DIRECTIONAL_HYPOTHESES_DH1", "DH contract: |nuisance-adjusted shift| >= 3 pp + Brier skill, Holm, week-cluster bootstrap, "
                                   "feasibility MDE <= 6 pp"),
    ("DIRECTIONAL_HYPOTHESES_DH2", "DH contract (pooled six coins, coin fixed effects)"),
    ("DIRECTIONAL_AND_RANGE_DH3", "DH contract: 3 pp directional bar; log(1.15) range bar after volatility nuisance; Holm"),
    ("GENERATOR_V0", "Generator V0 critics (novelty, red team, feasibility) + memory finalizer; no market test"),
    ("Discovery Sprint", "Sprint selection (one acquisition card, family rotation); never executed"),
    ("SEED", "Owner seed card: MIN_MEANINGFUL_EFFECT 0.10, hard floor 40 A episodes, STRESS power"),
    ("Divergence", "Divergence program gates: 15 pp MEOI, STRESS power 0.80, owner routing decisions V1-V3"),
    ("HYPOTHESIS_SEED_BACKLOG", "Seed backlog (not an execution queue)"),
    ("Decision-layer", "TWAP sealed spec V1: H1 ratio >= 1.10, price cells 10 bps floor + Holm"),
    ("E1", "E1-RUN-001 frozen prereg: SURVIVES / SIMPLIFY / DEMOTE / KILL / INCONCLUSIVE, UTC-day block bootstrap"),
    ("MICROSCOPE", "Synthetic calibration: Wilson cell targets"),
    ("Live-archive", "Pilot spec: range ratio 1.25 on the live archive"),
    ("Product", "Product decision V2 (product evidence, not a research claim)"),
    ("PRODUCT_DECISION_V2", "Product decision V2 (product evidence, not a research claim)"),
    ("Beta V0", "Beta V0 prospective sidecar (prereg-like)"),
    ("Generator V0 GV0V03L40", "Owner-authorized manual escalation; feasibility compiler"),
]

FALLBACK_DATES = {"GENERATOR_V0_CAMPAIGN_GV0CAL": "2026-09-24", "GENERATOR_V0_CAMPAIGN_GV0R01": "2026-09-24",
                  "GENERATOR_V0_CAMPAIGN_GV0V03L40": "2026-10-02"}
GENERIC_RECORDS = ("RESEARCH_LEDGER.md", "SCIENTIFIC_TEST_LEDGER.json", "MECHANISM_MEMORY_V0.json",
                   "beta_research_findings.yaml", "CURRENT_RESEARCH_STATE.md")

# Unit-like ids in research-ledger headings and research file names, mapped onto census ids.
ID_PATTERNS = [
    (re.compile(r"\bH0([1-5])\b"), lambda m: f"H0{m.group(1)}"),
    (re.compile(r"\bB2[-_ ]0([1-6])\b"), lambda m: f"B2-0{m.group(1)}"),
    (re.compile(r"\bMARKET[-_ ]0([1-6])H?\b"), lambda m: f"MARKET-0{m.group(1)}"),
    (re.compile(r"\bGV0R01[-_ ](C\d{3})\b"), lambda m: f"GV0R01-{m.group(1)}"),
    (re.compile(r"\bGV0V03L40[-_ ](C\d{3})([-_ ]R1)?\b"),
     lambda m: f"GV0V03L40-{m.group(1)}" + ("-R1" if m.group(2) else "")),
    (re.compile(r"\b(D(?:[1-9]|1[0-3]))(?=[ _]|$)"), lambda m: m.group(1)),
    (re.compile(r"\bDH([1-3])\b"), lambda m: f"DH{m.group(1)}"),
    (re.compile(r"\bSEED[-_ ]?000([1-3])\b"), lambda m: f"SEED-000{m.group(1)}"),
]


def _load():
    atlas = json.loads(ATLAS_JSON.read_text())
    units = {u["id"]: u for u in atlas["UNITS"]}
    raw = yaml.safe_load(ATLAS_UNITS.read_text())
    aliases = {}
    for u in raw["units"]:
        for al in u.get("aliases") or ():
            aliases[al] = u["id"]
        if u.get("source_id"):
            aliases[u["source_id"]] = u["id"]
    return units, aliases, yaml.safe_load(ASSESSMENTS.read_text())


def _blocker(verdict: str):
    if "SURVIVOR" in verdict:
        return "SURVIVOR"
    m = re.search(r"PIPELINE_BLOCKED_(.*?)_NO_SCIENTIFIC_STATUS", verdict)
    return m.group(1) if m else None


def _framework(program: str) -> str:
    for key, text in FRAMEWORKS:
        if key in program:
            return text
    return "unit-specific (see records)"


def _first_added(paths) -> str | None:
    for p in paths:
        p = p.split("#")[0]
        if Path(p).name in GENERIC_RECORDS or not (ROOT / p).exists():
            continue
        try:
            out = subprocess.run(["git", "log", "--diff-filter=A", "--format=%ad", "--date=short", "--", p],
                                 cwd=ROOT, capture_output=True, text=True, timeout=30).stdout.split()
        except (OSError, subprocess.SubprocessError):
            return None
        if out:
            return out[-1]
    return None


def _exposure(unit: dict, row: dict) -> str:
    period = str(unit.get("period") or "")
    used_2526 = re.search(r"binance_2025_2026_used: (yes|YES|live archive)", period)
    if row["cat"] == "PRODUCT_EVIDENCE":
        base = "EXPOSED (product statistics on the product surface)"
    elif row.get("est"):
        base = "EXPOSED: outcome read for this question (retrospective)"
    else:
        base = "NOT READ for this question (no outcome computed; the surface may be exposed by other units)"
    if used_2526:
        base += "; uses 2025/2026 data (" + used_2526.group(0) + ")"
    return base


def build(write_dates: bool = True) -> dict:
    units, aliases, A = _load()
    assessed, defaults = A["units"], A["generator_defaults"]
    problems: list[str] = []

    rows = []
    for uid, u in units.items():
        if uid in assessed:
            a = dict(assessed[uid])
            a["assessment_source"] = "explicit"
        else:
            key = _blocker(u.get("verdict") or "")
            if key not in defaults:
                problems.append(f"UNASSESSED atlas unit {uid} (verdict {u.get('verdict')!r})")
                continue
            a = dict(defaults[key])
            a["assessment_source"] = f"generator_default:{key}"
        row = {
            "id": uid, "family": u.get("program"), "cell": f"{u.get('row')} x {u.get('col')}",
            "question": u.get("title") + (" — " + u["function"] if u.get("function") else ""),
            "data": "; ".join(u.get("datasets") or []), "period": u.get("period"),
            "units_n": u.get("units_n"), "practical_bar": u.get("practical_bar"),
            "official_verdict": u.get("verdict"), "framework": _framework(u.get("program") or ""),
            "official_why_closed": u.get("why_closed"), "atlas_state": u.get("state"),
            **a,
            "records": list(a.get("records") or []) + list(u.get("records") or []),
        }
        row["exposure"] = a.get("exposure") or _exposure(u, row)
        rows.append(row)
    for uid, p in A["post_atlas_units"].items():
        row = {"id": uid, "family": p["program"], "cell": None, "question": p["question"], "data": p["data"],
               "period": None, "units_n": p["units_n"], "practical_bar": None, "official_verdict": p["official"],
               "framework": p["framework"], "official_why_closed": p["why_closed"], "atlas_state": None,
               "records": p["records"], "date": p["date"], "assessment_source": "explicit",
               **{k: p[k] for k in ("cat", "cons", "level", "needs", "est", "assess") if k in p}}
        row["exposure"] = "EXPOSED: CORE 2020-2024 (same surface as R03-C1), read once under a frozen design"
        rows.append(row)

    for r in rows:
        for rec in r.get("records") or ():
            if not (ROOT / rec.split("#")[0]).exists():
                problems.append(f"{r['id']}: record {rec} does not exist")
        if r["cat"] not in A["categories"] or (r.get("cat2") and r["cat2"] not in A["categories"]):
            problems.append(f"bad category on {r['id']}")
        if r["cons"] not in CONS:
            problems.append(f"bad cons on {r['id']}")
        if r["level"] not in LEVELS:
            problems.append(f"bad level on {r['id']}")
        if not r.get("date"):
            r["date"] = (_first_added(r.get("records") or []) if write_dates else None) \
                or FALLBACK_DATES.get(r.get("family") or "")
    census = {r["id"] for r in rows}
    known = census | set(A["child_executions"]) | set(A["methodology_units"])

    def resolve(x: str):
        x = LEDGER_ALIASES.get(x, x)
        return aliases.get(x, x)

    proof = {}
    # 1. generator memory: every signature on the census; every attempt either a signature or a linked attempt
    mem = json.loads(MEMORY.read_text())["ENTRIES"]
    proof["memory_entries"] = len(mem)
    problems += [f"memory entry {m} not in census" for m in mem if m not in census]
    attempts, linked = 0, []
    for f in sorted(MEMORY_DELTAS.glob("*.json")):
        d = json.loads(f.read_text())
        for at in d.get("ATTEMPTS") or ():
            attempts += 1
            if at.get("SIGNATURE_ID"):
                if at["SIGNATURE_ID"] not in census:
                    problems.append(f"attempt {at['ATTEMPT_ID']} signature not in census")
            else:
                linked.append(at["ATTEMPT_ID"])
    not_units_text = json.dumps(A["not_units"])
    for at in linked:
        if at.split("-")[-1] not in not_units_text:
            problems.append(f"linked attempt {at} not listed in not_units")
    proof["memory_attempts"] = attempts
    proof["memory_linked_attempts"] = len(linked)
    # 2. scientific test ledger
    led = json.loads(TEST_LEDGER.read_text())
    hyp = [resolve(h.strip()) for t in led["TESTS"] for h in t["HYPOTHESIS_ID"].split(",")]
    problems += [f"test-ledger hypothesis {h} not in census" for h in hyp if h not in census]
    proof["test_ledger_tests"] = len(led["TESTS"])
    proof["test_ledger_hypotheses"] = len(set(hyp))
    # 3. bot findings registry
    fids = [f["id"] for f in yaml.safe_load(FINDINGS.read_text())["findings"]]
    problems += [f"finding {f} not in census" for f in fids if resolve(f) not in census]
    proof["findings_ids"] = len(fids)
    # 4./5. research-ledger headings and research file names
    def scan(texts, where):
        seen = set()
        for t in texts:
            t = t.replace("_", " ")
            for pat, fn in ID_PATTERNS:
                for m in pat.finditer(t):
                    i = fn(m)
                    if i in ("DH1", "DH2", "DH3"):
                        if not any(c.startswith(i + "-") for c in census):
                            problems.append(f"{where}: program {i} has no census unit")
                        continue
                    seen.add(i)
                    if i not in known:
                        problems.append(f"{where}: id {i} in {t!r} not placed")
        return seen
    heads = [ln[3:] for ln in RESEARCH_LEDGER.read_text().splitlines() if ln.startswith("## ")]
    proof["research_ledger_headings"] = len(heads)
    proof["research_ledger_ids_placed"] = len(scan(heads, "RESEARCH_LEDGER"))
    names = [p.stem for p in (ROOT / "docs/research").iterdir() if p.is_file()]
    proof["research_files"] = len(names)
    proof["research_file_ids_placed"] = len(scan(names, "docs/research"))
    proof["problems"] = problems

    counts = {k: dict(collections.Counter(r[k] for r in rows).most_common())
              for k in ("cat", "cons", "level", "needs")}
    counts["cat2"] = dict(collections.Counter(r["cat2"] for r in rows if r.get("cat2")).most_common())
    executed = [r for r in rows if r.get("est")]
    counts["with_outcome"] = len(executed)
    counts["with_outcome_by_cat"] = dict(collections.Counter(r["cat"] for r in executed).most_common())
    counts["cons_by_cat"] = {c: dict(collections.Counter(r["cons"] for r in rows if r["cat"] == c))
                             for c in A["categories"]}

    def ids(pred):
        return sorted(r["id"] for r in rows if pred(r))
    lists = {
        "POTENTIALLY_KILLED_BY_OLD_CONSERVATISM_YES": ids(lambda r: r["cons"] == "YES"),
        "POTENTIALLY_KILLED_BY_OLD_CONSERVATISM_PARTLY": ids(lambda r: r["cons"] == "PARTLY"),
        "REAL_NULL": ids(lambda r: r["cat"] == "REAL_NULL"),
        "STRONG_NEGATIVE": ids(lambda r: r["cat"] == "STRONG_NEGATIVE"),
        "POSITIVE_ALIVE": ids(lambda r: r["cat"] == "POSITIVE_ALIVE"),
        "NEEDS_NEW_DATA_OR_PROSPECTIVE": ids(lambda r: any(k in r["needs"] for k in ("NEW_DATA", "PROSPECTIVE"))),
        "NOT_RECOVERABLE": ids(lambda r: "NOT_RECOVERABLE" in r["needs"]),
        "SUPPORTS_L1_OR_L2_NOW": ids(lambda r: r["level"] in ("L1", "L2")),
        "SUPPORTS_L1_L2_POSITIVE_OR_DESCRIPTIVE": ids(
            lambda r: r["level"] in ("L1", "L2") and r["cat"] not in ("REAL_NULL", "STRONG_NEGATIVE")),
        "SUPPORTS_L2_INFORMATIVE_NULL_OR_NEGATIVE": ids(
            lambda r: r["level"] == "L2" and r["cat"] in ("REAL_NULL", "STRONG_NEGATIVE")),
        "STANDARD_MISMATCH_POSSIBLE_UNTESTED": ids(lambda r: r.get("flag") == "STANDARD_MISMATCH_POSSIBLE"),
    }
    order = {r["id"]: i for i, r in enumerate(sorted(rows, key=lambda r: (r.get("date") or "9999", r["id"])))}
    rows.sort(key=lambda r: order[r["id"]])
    return {"version": VERSION, "census_total": len(rows), "atlas_units": len(units),
            "post_atlas_units": sorted(A["post_atlas_units"]), "child_executions": A["child_executions"],
            "methodology_units": A["methodology_units"], "not_units": A["not_units"],
            "categories": A["categories"], "completeness_proof": proof, "counts": counts, "lists": lists,
            "units": rows}


def _cell(v, n=160):
    s = "" if v is None else str(v)
    s = s.replace("|", "/").replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"


def render_table(res: dict) -> str:
    out = ["# RESEARCH_HISTORY_AUDIT_V1 — per-unit table", "",
           "Generated by `python -m scripts.research.history_audit` from the atlas (facts) and "
           "`docs/research/audit/RESEARCH_HISTORY_AUDIT_V1_ASSESSMENTS.yaml` (judgments). Do not edit by hand. "
           "Narrative and decisions: `RESEARCH_HISTORY_AUDIT_V1.md`. Official verdicts are quoted, never changed.", "",
           "Columns: date (first record), family, question, data / N, official verdict (framework in JSON), "
           "estimate / uncertainty / stability (executed units only), category, conservatism, max claim, needs, "
           "independent assessment.", ""]
    fam = None
    for r in res["units"]:
        if r["family"] != fam:
            fam = r["family"]
        out.append(f"### {r['id']}")
        out.append("")
        out.append(f"- **When / family:** {r.get('date') or 'unknown'} · {_cell(r['family'], 200)}")
        out.append(f"- **Question:** {_cell(r['question'], 400)}")
        out.append(f"- **Data / exposure:** {_cell(r['data'], 200)} · {_cell(r.get('period'), 300)} · {r['exposure']}")
        out.append(f"- **N / information:** {_cell(r.get('units_n'), 300) or '—'}")
        why = _cell(r.get("official_why_closed"), 300) or "not recorded"
        out.append(f"- **Official:** {_cell(r['official_verdict'], 400)} — closed because: {why}")
        out.append(f"- **Framework:** {_cell(r['framework'], 300)}")
        if r.get("est"):
            out.append(f"- **Estimate:** {_cell(r['est'], 400)}")
        if r.get("unc"):
            out.append(f"- **Uncertainty:** {_cell(r['unc'], 300)}")
        if r.get("stab"):
            out.append(f"- **Stability:** {_cell(r['stab'], 300)}")
        cat = r["cat"] + (f" + {r['cat2']}" if r.get("cat2") else "")
        out.append(f"- **Audit:** `{cat}` · conservatism `{r['cons']}` · max claim `{r['level']}` · needs "
                   f"`{r['needs']}`{' · flag ' + r['flag'] if r.get('flag') else ''}")
        out.append(f"- **Assessment:** {r['assess']}")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="coverage proof only; write nothing")
    args = ap.parse_args(argv)
    res = build(write_dates=not args.check)
    problems = res["completeness_proof"]["problems"]
    print(json.dumps({k: v for k, v in res["completeness_proof"].items() if k != "problems"}, indent=1))
    print(json.dumps(res["counts"]["cat"], indent=1))
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    if not args.check:
        OUT_JSON.write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n")
        OUT_TABLE.write_text(render_table(res))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
