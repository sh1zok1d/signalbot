"""Freeze step for OWNER_CARDS_R03: writes the preregistration twin, the
feasibility report, the frozen unit sets and the execution permit. Outcome-blind.

Run after support.py. It reads the frozen planning and feasibility files, never
a market target. The permit binds SHA256 digests of every artifact the one-shot
depends on.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
from pathlib import Path

from . import constants as K
from . import data as D
from . import states as S
from . import support as SP

REPO = Path(__file__).resolve().parents[3]
DOCS = REPO / "docs/research"
PREREG_JSON = DOCS / "OWNER_CARDS_R03_PREREG.json"
PREREG_MD = DOCS / "OWNER_CARDS_R03_PREREG.md"
FEAS_MD = DOCS / "OWNER_CARDS_R03_FEASIBILITY.md"
PERMIT = DOCS / "OWNER_CARDS_R03_EXECUTION_PERMIT.json"
UNITS_DIR = DOCS / "owner_cards_r03"
FROZEN_CODE = [
    "scripts/research/owner_cards_r03/__init__.py",
    "scripts/research/owner_cards_r03/constants.py",
    "scripts/research/owner_cards_r03/data.py",
    "scripts/research/owner_cards_r03/windows.py",
    "scripts/research/owner_cards_r03/states.py",
    "scripts/research/owner_cards_r03/support.py",
    "scripts/research/owner_cards_r03/outcomes.py",
    "scripts/research/owner_cards_r03/evaluate.py",
    "scripts/research/owner_cards_r03/execute.py",
    "docs/research/OWNER_CARDS_R03_PLANNING.json",
    "docs/research/OWNER_CARDS_R03_FEASIBILITY.json",
    "docs/research/OWNER_CARDS_R03_CARDS.md",
    "docs/research_data/CORE_BTC_BINANCE_V0/SOURCE_INVENTORY_717d37a4.json",
    "docs/research_data/D2_BITMEX_PRE2020_SOURCE_AUTHORITY.json",
    "docs/research_data/SPRINT04_BINANCE_SPOT_USDT_DAILY_PANEL_V0/object_ledger.json",
    "docs/research_data/SPRINT04_BINANCE_SPOT_USDT_DAILY_PANEL_V0/EXCLUSION_LISTS.json",
    "docs/research_data/NYSE_HOLIDAY_CALENDAR_ARCHIVE_V0/EVENTS.json",
]


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()


def main() -> None:
    K.assert_locked()
    feas = json.loads(SP.FEASIBILITY_OUT.read_text())
    planning = json.loads(SP.PLANNING_OUT.read_text())
    summary = feas["SUMMARY"]
    executed = [h["ID"] for h in K.HYPOTHESES if summary[h["ID"]]["EXECUTABLE"]]
    closed = {h["ID"]: summary[h["ID"]]["STATUS"] for h in K.HYPOTHESES if not summary[h["ID"]]["EXECUTABLE"]}
    nyse = D.nyse_events()
    metrics = SP.panel_metrics() if any(h.startswith("R03-B") for h in executed) else None
    UNITS_DIR.mkdir(exist_ok=True)
    unit_digests, unit_counts = {}, {}
    for hid in executed:
        units = S.build_units(hid, "DISCOVERY", nyse=nyse, metrics=metrics)
        body = json.dumps(units, sort_keys=True, separators=(",", ":"))
        unit_digests[hid] = hashlib.sha256(body.encode()).hexdigest()
        unit_counts[hid] = S.unit_counts(units)
        (UNITS_DIR / f"UNITS_{hid}.json").write_text(json.dumps(units, sort_keys=True) + "\n")
        if K.HYPOTHESIS_BY_ID[hid]["REPLICATION"] and K.CARDS[K.HYPOTHESIS_BY_ID[hid]["CARD"]]["REPLICATION"] == "BITMEX_HISTORICAL":
            rep = S.build_units(hid, "REPLICATION", nyse=nyse)
            (UNITS_DIR / f"UNITS_{hid}_REPLICATION.json").write_text(json.dumps(rep, sort_keys=True) + "\n")
            unit_digests[hid + ":REPLICATION"] = hashlib.sha256(
                json.dumps(rep, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    holm_m = {cid: sum(1 for h in executed if K.HYPOTHESIS_BY_ID[h]["CARD"] == cid) for cid in K.CARDS}
    prereg = {
        "PREREG": "OWNER_CARDS_R03_PREREG_V1",
        "STATUS": "FROZEN_BEFORE_OUTCOMES",
        "DATE": K.DESIGN_DATE,
        "PROGRAM_ID": K.PROGRAM_ID,
        "SEARCH_FAMILY_ID": K.SEARCH_FAMILY_ID,
        "EVALUATION_CONTRACT": K.EVALUATION_CONTRACT,
        "CONTRACT_VERSION": K.CONTRACT_VERSION,
        "CARDS": {cid: {**card, "HOLM_M": holm_m[cid]} for cid, card in K.CARDS.items()},
        "HYPOTHESES": K.HYPOTHESES,
        "EXECUTED_HYPOTHESES": executed,
        "CLOSED_AT_FEASIBILITY": closed,
        "WINDOW_DEFS": K.WINDOW_DEFS,
        "TARGET": "log range ln(max high / min low) over the window; a window with a missing bar is UNAVAILABLE from timestamps only",
        "STANDARDIZATION": "per calendar year and per window definition, over all days' windows of that definition (label-blind)",
        "ESTIMAND": "mean over units of d = mean z(state) - mean z(comparator)",
        "INFERENCE": {"CLASS": "PERMUTATION_GROUP_INVARIANCE", "TEST": "sign-flip over units, two-sided",
                      "DRAWS": K.SIGNFLIP_DRAWS, "SEED": f"{K.SIGNFLIP_SEED} + hypothesis index (discovery), + 50 + index (replication)",
                      "MULTIPLICITY": K.MULTIPLICITY, "FAMILY_ALPHA": K.FAMILY_ALPHA,
                      "DEPENDENCE_DIAGNOSTIC": f"moving-block SE over units, block {K.HET_BLOCK_UNITS}"},
        "GATES": {
            "STATISTICAL": "Holm rejects within the card (two-sided)",
            "PRACTICAL": f"|estimate| >= {K.MIN_MEANINGFUL_EFFECT} SD with the declared sign (any sign for TWO_SIDED)",
            "EPOCH": f"calendar years; block-permutation Q test ({K.HET_DRAWS} draws, seed {K.HET_SEED} + index, alpha {K.ALPHA_HET}) and opposite-sign test; fails the card only if the compiler recorded the gate ASSESSABLE",
            "PRODUCT_FREQUENCY": f"at least {K.PRODUCT_FREQUENCY_MIN_PER_YEAR} evaluated units per year on average",
            "NUISANCE_WORDING": f"adjusted estimate (prior 24h RV, lagged target) keeps >= {K.NUISANCE_RETENTION_FOR_STATE_SPECIFIC_WORDING} of the raw estimate with the same sign, else REFLECTS_GENERAL_VOLATILITY_REGIME",
        },
        "CLASSIFICATION": {
            "DISCOVERY": "PROMISING_PROTOTYPE iff statistical and practical pass and the epoch gate does not fail; NO_INCREMENTAL_STRUCTURE if statistical or practical fails; HETEROGENEOUS_UNEXPLAINED if only the epoch gate fails",
            "REPLICATION": "BitMEX 2017-2019, same frozen rule, Holm over the replicated prototypes of the card; REPLICATED iff statistical and practical pass",
            "FINAL": "SUPPORTED_UNCONDITIONAL iff PROMISING_PROTOTYPE and REPLICATED (SUPPORTED_BUT_PRODUCT_SPARSE if the frequency gate fails); PROMISING_PROTOTYPE_NOT_REPLICATED if the replication fails; PROMISING_PROTOTYPE if no replication surface is available in this unit",
        },
        "REPLICATION_SURFACES": {"R03-A": K.REPLICATION_BITMEX, "R03-C": K.REPLICATION_BITMEX, "R03-B": K.PROSPECTIVE_PANEL},
        "FROZEN_UNIT_DIGESTS": unit_digests,
        "FROZEN_UNIT_COUNTS": unit_counts,
        "FORBIDDEN_AFTER_OUTCOMES": [
            "any change to a window, state, comparator, unit, standardization or seed",
            "any added hypothesis, regime, horizon or sign",
            "any rescue of a closed hypothesis",
            "any rerun",
            "any 2025/2026 object",
        ],
        "ALLOWED_INTERPRETATION": K.ALLOWED_INTERPRETATION,
        "FORBIDDEN_INTERPRETATION": K.FORBIDDEN_INTERPRETATION,
        "MARKET_OUTCOMES_COMPUTED": False,
        "PROTECTED_2025_2026_OPENED": False,
    }
    PREREG_JSON.write_text(json.dumps(SP._jsonable(prereg), indent=2, sort_keys=True) + "\n")

    # Feasibility report (markdown)
    lines = ["# Owner cards R03 — outcome-blind feasibility", "",
             "**Status:** `FEASIBILITY_COMPLETE / OUTCOMES_NOT_OPENED`", f"**Date:** {K.DESIGN_DATE}",
             "**Compiler:** `GV0R02_SCHEMA_V2 / GV0R02_POLICY_V2` via `to_compiler_proposal_v1`; paired-unit screen at the card's Holm first-step alpha",
             "**Machine record:** `OWNER_CARDS_R03_FEASIBILITY.json`; planning objects in `OWNER_CARDS_R03_PLANNING.json`", "",
             "| ID | Units | Active / comparator windows | n_eff (compiler) | MDE stress (compiler) | MDE stress (units, alpha/m) | Replication units | Status |",
             "|---|---|---|---|---|---|---|---|"]
    for h in K.HYPOTHESES:
        s = summary[h["ID"]]; p = planning["PLANNING"][h["ID"]]["UNIT_COUNTS"]
        lines.append(f"| {h['ID']} `{h['NAME']}` | {s['N_UNITS']} | {p['ACTIVE_WINDOWS']} / {p['INACTIVE_WINDOWS']} | "
                     f"{(s['EFFECTIVE_N'] or 0):.1f} | {(s['MDE_STRESS_COMPILER'] or 0):.3f} | {(s['MDE_STRESS_UNITS'] or 0):.3f} | "
                     f"{s['REPLICATION_UNITS']} | `{s['STATUS']}` |")
    lines += ["", f"Effect bar {K.MIN_MEANINGFUL_EFFECT} SD for every hypothesis. Executed set: " + ", ".join(executed) + ".",
              "Closed at feasibility (never executed, no rescue): " + ", ".join(f"{k} (`{v}`)" for k, v in closed.items()) + ".", "",
              "Holm counts per card: " + ", ".join(f"{cid} = {m}" for cid, m in holm_m.items()) + ".", "",
              "No BTC target was read. No 2025/2026 object was selected. Panel states for card B use panel closes and quote volumes up to the decision boundary only."]
    for hid, det in feas["DETAIL"].items():
        if "PANEL_STATE_DIAGNOSTIC" in det:
            lines.append(f"- {hid} panel state diagnostic: {json.dumps(det['PANEL_STATE_DIAGNOSTIC'])}")
    FEAS_MD.write_text("\n".join(lines) + "\n")

    # Preregistration markdown twin
    md = ["# Owner cards R03 — twin preregistration", "",
          "**Status:** `FROZEN_BEFORE_OUTCOMES`", f"**Date:** {K.DESIGN_DATE}",
          f"**Contract:** `{K.EVALUATION_CONTRACT}`; planning under `{K.CONTRACT_VERSION}`",
          "**Machine twin:** `OWNER_CARDS_R03_PREREG.json` is authoritative for every constant; its SHA256 is bound in `SCIENTIFIC_TEST_LEDGER.json` and in the execution permit.",
          "**Design text:** `OWNER_CARDS_R03_CARDS.md`; feasibility: `OWNER_CARDS_R03_FEASIBILITY.md`", "",
          "```", f"SEARCH_FAMILY_ID = {K.SEARCH_FAMILY_ID}"]
    for cid, card in K.CARDS.items():
        md.append(f"{card['TEST_FAMILY_ID']} : executed = {[h for h in executed if K.HYPOTHESIS_BY_ID[h]['CARD'] == cid]} (Holm m = {holm_m[cid]})")
    md += [f"CLOSED_AT_FEASIBILITY = {closed}", "MARKET_OUTCOMES_COMPUTED = false", "PROTECTED_2025_2026_OPENED = false", "```", "",
           "## Executed hypotheses", ""]
    for hid in executed:
        h = K.HYPOTHESIS_BY_ID[hid]
        md += [f"### {hid} `{h['NAME']}` ({h['CARD']})", "",
               f"- **State:** {h['STATE']}", f"- **Comparator:** {h['COMPARATOR']}", f"- **Unit:** {h['UNIT']}; frozen units {unit_counts[hid]['UNITS']}, digest `{unit_digests[hid][:16]}…` (`owner_cards_r03/UNITS_{hid}.json`)",
               f"- **Expected sign:** {h['DIRECTION']}", f"- **Mechanism (descriptive motivation, not a claim):** {h['MECHANISM']}",
               f"- **Replication:** {h.get('REPLICATION_NOTE', 'prospective panel surface (card B)') if h['REPLICATION'] or h['CARD']=='R03-B' else 'none'}", ""]
    md += ["## Frozen inference", "",
           f"- Target: log range of the window; standardized per year and window definition, label-blind.",
           f"- Estimand: mean over units of d = mean z(state) − mean z(comparator).",
           f"- Test: sign-flip over units, {K.SIGNFLIP_DRAWS} draws, seed {K.SIGNFLIP_SEED} + index, two-sided; Holm within the card at alpha {K.FAMILY_ALPHA}.",
           f"- Practical bar: |estimate| ≥ {K.MIN_MEANINGFUL_EFFECT} SD with the declared sign.",
           f"- Epochs: calendar years; Q test against a block permutation ({K.HET_BLOCK_UNITS}-unit blocks, {K.HET_DRAWS} draws) and the opposite-sign test; the compiler recorded every cell `NOT_ASSESSABLE`, so the epoch record is descriptive and cannot fail a card.",
           "- Nuisance diagnostic: prior 24h realized variance and the lagged target, fitted label-blind; it decides wording only.",
           "- Replication (cards A and C): BitMEX XBTUSD 5m 2017-01..2019-12, same rule, Holm over the replicated prototypes of the card; card B: prospective from 2027-01-01 with the fixed stopping rule in the planning objects.",
           "", "## Classification", "",
           "Discovery: `PROMISING_PROTOTYPE` iff statistical and practical pass; `NO_INCREMENTAL_STRUCTURE` otherwise. Final: `SUPPORTED_UNCONDITIONAL` iff the replication also passes; `PROMISING_PROTOTYPE_NOT_REPLICATED` if it fails; `PROMISING_PROTOTYPE` when no replication surface exists in this unit.",
           "", "## Forbidden after outcomes", ""] + [f"- {x}" for x in prereg["FORBIDDEN_AFTER_OUTCOMES"]] + [
           "", "## Interpretation", "", f"Allowed: {K.ALLOWED_INTERPRETATION}", "", f"Forbidden: {K.FORBIDDEN_INTERPRETATION}"]
    PREREG_MD.write_text("\n".join(md) + "\n")

    frozen = {rel: D.sha256_file(REPO / rel) for rel in FROZEN_CODE}
    frozen["docs/research/OWNER_CARDS_R03_PREREG.json"] = D.sha256_file(PREREG_JSON)
    frozen["docs/research/OWNER_CARDS_R03_PREREG.md"] = D.sha256_file(PREREG_MD)
    frozen["docs/research/OWNER_CARDS_R03_FEASIBILITY.md"] = D.sha256_file(FEAS_MD)
    for p in sorted(UNITS_DIR.glob("UNITS_*.json")):
        frozen[str(p.relative_to(REPO))] = D.sha256_file(p)
    permit = {
        "PERMIT": "OWNER_CARDS_R03_EXECUTION_PERMIT_V1",
        "PROGRAM_ID": K.PROGRAM_ID,
        "AUTHORIZED_BY": "owner (instruction of 2026-10-03: test, freeze the viable ones, execute)",
        "AUTHORIZED_AT_UTC": dt.datetime.now(tz=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "AUTHORIZATION_BASE_HEAD": git_head(),
        "SEARCH_FAMILY_ID": K.SEARCH_FAMILY_ID,
        "TEST_FAMILY_IDS": {cid: card["TEST_FAMILY_ID"] for cid, card in K.CARDS.items()},
        "PREREG_PATH": "docs/research/OWNER_CARDS_R03_PREREG.json",
        "PREREG_SHA256": frozen["docs/research/OWNER_CARDS_R03_PREREG.json"],
        "EXECUTED_HYPOTHESES": executed,
        "CLOSED_AT_FEASIBILITY": closed,
        "SCOPE": "ONE_SHOT_DISCOVERY_PLUS_DECLARED_HISTORICAL_REPLICATION",
        "EVIDENCE_LABEL": "DISCOVERY_ON_HISTORICALLY_EXPOSED_BINANCE_2020_2024; REPLICATION_ON_BITMEX_2017_2019_WHERE_DECLARED",
        "EXECUTION_AUTHORIZED": True,
        "RERUN_AUTHORIZED": False,
        "DESIGN_CHANGE_AUTHORIZED": False,
        "PROTECTED_2025_2026_AUTHORIZED": False,
        "FROZEN_ARTIFACT_SHA256": frozen,
        "FROZEN_UNIT_DIGESTS": unit_digests,
        "OUTPUTS": ["docs/research/OWNER_CARDS_R03_RESULT.json", "docs/research/OWNER_CARDS_R03_RESULT.md"],
        "ORDER": "this permit and the frozen artifacts are committed first; execute.py runs once after that commit and refuses to run if any digest differs or a RESULT exists",
    }
    PERMIT.write_text(json.dumps(permit, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"EXECUTED": executed, "CLOSED": closed, "UNIT_DIGESTS": {k: v[:12] for k, v in unit_digests.items()}}, indent=1))


if __name__ == "__main__":
    main()
