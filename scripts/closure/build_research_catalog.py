"""Build docs/closure/RESEARCH_CATALOG_FINAL_V1.md from the research atlas (the authority for every closed unit) plus the
units and diagnostic reports that post-date the atlas or sit outside it.  Read-only on the atlas; the catalogue states each
unit's atlas state and verdict verbatim and adds nothing.  Run: python -m scripts.closure.build_research_catalog"""
from __future__ import annotations
import json, collections, datetime, pathlib
REPO = pathlib.Path(__file__).resolve().parents[2]
ATLAS = REPO / "docs/research/atlas/SIGNALBOT_RESEARCH_ATLAS_V1.json"
OUT = REPO / "docs/closure/RESEARCH_CATALOG_FINAL_V1.md"

# Units and records outside the atlas (forecast engines, product evidence, the 2026-10-14/15 diagnostic reports).
OUTSIDE = [
    ("Forecast V1 (touch-probability / corridor engine, production since 2025)", "FROZEN; replayed by formula in the 2026-10-14 revision: direction-proxy AUC 0.48-0.49; as a touch-probability baseline it is strong (Rangecast V2 record §1)", "docs/FORECASTING_ROADMAP.md (historical); docs/PULSY_FORECAST_INVESTIGATION_REVISION_2026-10-14.md"),
    ("Forecast V2 / Stage 2 setups (consensus, percentile maturity, red team)", "DISABLED, never enabled in production; V2 continuation mechanisms refuted at scale (2026-10-14 revision)", "docs/V2_PRODUCT_CONTRACT.md, docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md, docs/V2_EMPIRICAL_RED_TEAM_PLAN.md"),
    ("E1-RUN-001 (V2 Stage-5 detector separation, frozen pre-registration)", "FROZEN, NOT EXECUTED; final holdout [2026-08-16, 2026-08-25T17:20) never opened by the evaluator; invalidated for P4 overlap; closed without execution by PROJECT_CLOSURE_DECISION_V1", "docs/e1/, docs/E1_DETECTOR_SEPARATION_PREREG.md, docs/research/PRICE_OI_INCREMENTAL_INFORMATION_PILOT_V0_E1_OVERLAP_ERRATUM.md"),
    ("Rangecast V1 (production corridor model) and Rangecast V2 W_L1", "V2 W_L1 beats V1 by 1-2 % log loss on folds 2021-2024 and on the one exposed read 2025-01 .. 2026-10-11; DISCOVERY_ONLY; shadow contract V2 written, shadow never promoted", "docs/research/RANGECAST_V2_RESULT.md, docs/RANGECAST_V2_SHADOW_CONTRACT_V2.md"),
    ("Paired shadow (V1 vs W_L1 live, VPS)", "RUNNING at closure; live records in the VPS database only (never read into the repo); read-only export procedure in scripts/research/independent_diagnostics_2026_10/revision/v1_extraction_procedure.md", "docs/BETA_PAIRED_SHADOW_CONTRACT_V1.md, storage/beta_paired_shadow_schema.sql"),
    ("Level race forecast V1 (B0 geometry, M1 ridge offset, HIST table)", "M1 vs B0 on held-out 2025-01-01 -> 2026-10-08: +0.010 nats [-0.018, +0.038] at T0, 0.000 at T15; state HIST; B0 is the display", "docs/research/LEVEL_RACE_FORECAST_V1_HELDOUT.md and sibling records; docs/FORECAST_LAYER_DECISION_V1.md"),
    ("Beta V0 claim journal and outcomes (L2 level hold, L2 level race HIST, corridor)", "Live claim records exist only in the VPS database; never evaluated in the repository", "docs/BETA_CLAIM_JOURNAL_DESIGN_V1.md, beta/claims.py"),
    ("Independent forecast investigation (2026-10-14)", "Direction AUC 1h 0.543, 4h 0.553 (2022-2026 walk-forward), below costs; volatility R2 0.52-0.74; V1 formula an anti-predictor; one prequential scoreboard proposed", "docs/PULSY_INDEPENDENT_FORECAST_INVESTIGATION_2026-10-14.md"),
    ("Revision of the investigation (2026-10-14)", "Leakage audit (AUC unchanged), independent re-implementation, pre-registered high-volatility rule NOT supported on ETH, HAR/GARCH/DVOL benchmark (HAR+clock ~ Rangecast V1), DH3-P3 reproduced on discovery (-6.08 vs -5.92 pp), undetermined on 2025-26", "docs/PULSY_FORECAST_INVESTIGATION_REVISION_2026-10-14.md"),
    ("Cross-market study and its revision (2026-10-14)", "Lead-lag none; cross-asset direction dAUC <= +0.005; cross-sectional reversal IC positive every year but dollar value below ~1 bp break-even; beta leak immaterial; executable portfolio economics zero or negative after costs", "docs/PULSY_CROSS_MARKET_STUDY_2026-10-14.md, docs/PULSY_CROSS_MARKET_REVISION_2026-10-14.md"),
    ("Signal engine audit (2026-10-15)", "Level Engine contrasts reproduced with the product constructor and the half-rotation control (+5.1 pp paired, +10.1 unpaired; one volatility-expansion phenomenon, no direction); #363 adds nothing beyond the own 15m move; END_POSITION_X not level-specific; every T0/T15 expression zero or negative gross; matched pairs path-selected", "docs/PULSY_SIGNAL_ENGINE_AUDIT_2026-10-15.md"),
]

def main() -> None:
    atlas = json.loads(ATLAS.read_text())
    units = atlas["UNITS"]
    counts = atlas["COUNTS"]
    by_region: dict[str, list] = collections.defaultdict(list)
    for u in units:
        by_region[str(u.get("row", "")).split(".")[0] or "UNASSIGNED"].append(u)
    lines = []
    lines.append("# Pulsy / Signalbot — final research catalogue (closure record)")
    lines.append("")
    lines.append(f"Generated {datetime.date.today().isoformat()} by `scripts/closure/build_research_catalog.py` from `docs/research/atlas/SIGNALBOT_RESEARCH_ATLAS_V1.json` (atlas version `{atlas['ATLAS'] if isinstance(atlas['ATLAS'], str) else atlas['ATLAS'].get('version', '')}`), plus the units outside the atlas listed in §3. States and verdicts are the atlas's own words; nothing is re-graded here. Record paths are relative to the repository root. This catalogue is part of `docs/PROJECT_CLOSURE_DECISION_V1.md`; after closure no unit changes state.")
    lines.append("")
    lines.append("## 1. Totals")
    lines.append("")
    OUTCOME_READ = {"NO_STRUCTURE", "CLOSED_ON_SURFACE", "EXPOSED_ONLY", "LIVE_SIGNAL", "CONFIRMED"}
    CLOSED_BEFORE = {"BLOCKED_METHOD", "BLOCKED_DATA", "INFORMATIONALLY_WEAK", "CANDIDATE_UNTESTED", "CLOSED_BEFORE_START", "BLOCKED_GOVERNANCE"}
    n_read = sum(1 for u in units if u.get("state") in OUTCOME_READ)
    n_before = sum(1 for u in units if u.get("state") in CLOSED_BEFORE)
    n_other = len(units) - n_read - n_before
    lines.append(f"- Research units registered in the atlas: **{counts['units']}**; cells in the mechanism × surface × state map: {counts['cells']} (open frontier {counts['cells_by_state'].get('OPEN_FRONTIER', 0)} — never to be explored under the closure decision).")
    lines.append(f"- **207 registered units are not 207 executed experiments.** By atlas state: units whose outcome was read (`NO_STRUCTURE`, `CLOSED_ON_SURFACE`, `EXPOSED_ONLY`, `LIVE_SIGNAL`, `CONFIRMED`): **{n_read}**; units closed before an outcome (`BLOCKED_METHOD`, `BLOCKED_DATA`, `INFORMATIONALLY_WEAK`, `CANDIDATE_UNTESTED`, `CLOSED_BEFORE_START`, `BLOCKED_GOVERNANCE`): **{n_before}**; accruing or deferred (`FUTURE_NATURAL_ACCUMULATION`): {n_other}. `INFORMATIONALLY_WEAK` includes some units that were run but whose information was judged insufficient; the per-unit verdict column below is authoritative.")
    lines.append("- Units by state:")
    for st, n in sorted(counts["units_by_state"].items(), key=lambda kv: -kv[1]):
        lines.append(f"  - `{st}`: {n}")
    lines.append("- Units in `CONFIRMED`: " + ", ".join(f"`{u['id']}`" for u in units if u.get("state") == "CONFIRMED") + " (D7: regime-context object, confirmed under maintained assumptions on BitMEX 2016-2019; a context object, not a trading edge).")
    lines.append("- Units in `LIVE_SIGNAL` (discovery-only prototypes, никогда не «Проверено»): " + ", ".join(f"`{u['id']}`" for u in units if u.get("state") == "LIVE_SIGNAL") + ".")
    lines.append("- Internal historical candidates promoted to a validated trading edge: **0** (AGENTS.md, MARKET program record).")
    lines.append("")
    lines.append("## 2. Units by region (atlas)")
    lines.append("")
    lines.append("Columns: id · title · taxonomy row · state · verdict · sample / period · first record.")
    for region in sorted(by_region):
        us = sorted(by_region[region], key=lambda u: u["id"])
        lines.append("")
        lines.append(f"### {region} ({len(us)})")
        lines.append("")
        lines.append("| id | title | row | state | verdict | sample / period | record |")
        lines.append("|---|---|---|---|---|---|---|")
        for u in us:
            rec = (u.get("records") or [""])[0]
            per = str(u.get("period") or u.get("units_n") or "").replace("|", "/")
            lines.append(f"| `{u['id']}` | {str(u.get('title','')).replace('|','/')} | `{u.get('row','')}` | `{u.get('state','')}` | {str(u.get('verdict','')).replace('|','/')} | {per} | `{rec}` |")
    lines.append("")
    lines.append("## 3. Units and records outside the atlas")
    lines.append("")
    lines.append("| Object | Status at closure | Records |")
    lines.append("|---|---|---|")
    for name, status, recs in OUTSIDE:
        lines.append(f"| {name} | {status} | {recs} |")
    lines.append("")
    lines.append("## 4. Reservations and protected surfaces at closure")
    lines.append("")
    for r in atlas.get("RESERVATIONS", []):
        lines.append(f"- `{r.get('id', 'E1-RUN-001 holdout')}`: period {json.dumps(r.get('period') or r.get('contamination', [{}])[0].get('period'))} — stays sealed; closed without execution (PROJECT_CLOSURE_DECISION_V1 §3).")
    lines.append("- 2025/2026 Binance surfaces: opened for the product (PRODUCT_DECISION_V2 §4) and read by the diagnostic reports; not pristine for any family touched by them (see each report's exposure note and `docs/RESEARCH_LEDGER.md`).")
    lines.append("")
    lines.append("## 5. How to read a unit")
    lines.append("")
    lines.append("Open the first record path; design notes precede results; `docs/RESEARCH_LEDGER.md` carries the dated entry with the consumed windows; `docs/research/atlas/ATLAS_UNITS_V1.yaml` is the hand-maintained source and `ATLAS_EVENTS_V1.jsonl` the hash-chained change log. Generator V0 units take their texts from `docs/research/generator_v0_memory/MECHANISM_MEMORY_V0.json` (append-only chain).")
    OUT.write_text("\n".join(lines) + "\n")
    print(OUT, len(units), "units")

if __name__ == "__main__":
    main()
