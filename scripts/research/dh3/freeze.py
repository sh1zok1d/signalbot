"""DH3 preregistration after the outcome-blind feasibility pass and before any outcome; registers
the executable card families in SCIENTIFIC_TEST_LEDGER.json.

python -m scripts.research.dh3.freeze
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.research.dh1 import constants as K1

from . import constants as K
from . import data as D
from . import evaluate as V
from . import feasibility as F
from . import features as FT

REPO = Path(__file__).resolve().parents[3]
LEDGER = REPO / "docs/research/SCIENTIFIC_TEST_LEDGER.json"


def prereg() -> dict:
    K.assert_locked()
    feas = json.loads(F.OUT_JSON.read_text())
    if feas["MARKET_OUTCOMES_OPENED"] is not False:
        raise RuntimeError("DH3: feasibility must be outcome-blind")
    cells = {}
    for h in K.HYPOTHESES:
        c = feas["CELLS"][h["ID"]]
        keep = ("N", "N_STATE", "N_COMPARATOR", "MDE_80", "BAR", "POWER_AT_BAR", "HET_POWER_EPOCH_2X", "HET_POWER_SYMBOL_2X")
        cells[h["ID"]] = {**{k: h[k] for k in ("CARD", "STATE", "ENDPOINT", "ATLAS_CELL")}, "BAR": K.bar_of(h),
                          "NUISANCE": list(FT.nuisance_names(h)), "EXECUTE": c["DECISION"]["EXECUTE"],
                          "FEASIBILITY_STATUS": c["DECISION"]["STATUS"], "DECISION": c["DECISION"],
                          "PLANNING_DISCOVERY": {k: c["DISCOVERY"].get(k) for k in keep},
                          "PLANNING_REPLICATION": None if c["REPLICATION"] is None else {k: c["REPLICATION"].get(k) for k in keep}}
    return {
        "PROGRAM_ID": K.PROGRAM_ID, "SEARCH_FAMILY_ID": K.SEARCH_FAMILY_ID, "DESIGN_DATE": K.DESIGN_DATE,
        "DESIGN_RECORD": K.DESIGN_RECORD, "EVALUATION_CONTRACT": K1.EVALUATION_CONTRACT, "CLAIM_TYPE": "INCREMENTAL",
        "CARDS": K.CARDS, "CELLS": cells, "SURFACES": K.SURFACES, "REPLICATION": K.REPLICATION,
        "PROSPECTIVE": K1.PROSPECTIVE, "EPOCHS": K.EPOCHS_ALL,
        "ESTIMAND": "State coefficient of a linear model of the endpoint on the state and nuisance dummies (coin fixed effects for pooled cards).",
        "INFERENCE": f"ISO-week clusters (pooled across coins, cut at year boundaries); bootstrap {K1.BOOT_DRAWS} draws, seed base {K.BOOT_SEED}; Holm within each card at 0.05.",
        "BARS": {"RANGE_4H": K.RANGE_BAR, "DIRECTIONAL": K.DIR_BAR,
                 "SKILL": "Brier skill (directional) or MSE skill (range) > 0: discovery leave-one-year-out cross-fit; replication frozen discovery models"},
        "CLASSIFICATION": ("PROMISING_PROTOTYPE if Holm p < 0.05, |shift| >= bar and skill > 0 (and assessable heterogeneity not "
                           "failed); NO_INCREMENTAL_STRUCTURE if the 95% CI lies inside (-bar, bar) or the shift is significant "
                           "but below the bar or without skill; otherwise INCONCLUSIVE. Replication as DH1."),
        "NO_RESCUE": "A failed cell is never re-scored with new thresholds, windows, coins, horizons, sides, baselines or claim type.",
        "CODE_DIGESTS": V.code_digests(), "DATASETS": D.dataset_identity(), "FEASIBILITY_SHA256": F.digest(),
        "MARKET_OUTCOMES_OPENED_AT_FREEZE": False, "OBJECTS_2025_2026_USED": "none",
    }


def register(sha: str, body: dict) -> None:
    ledger = json.loads(LEDGER.read_text())
    if any(t["SEARCH_FAMILY_ID"] == K.SEARCH_FAMILY_ID for t in ledger["TESTS"]):
        raise RuntimeError("DH3 already registered")
    for card, spec in K.CARDS.items():
        run = [hid for hid, c in body["CELLS"].items() if c["CARD"] == card and c["EXECUTE"]]
        if not run:
            continue
        ledger["TESTS"].append({
            "CLASSIFICATION": None, "DATASET_ID": f"DH3 card {card} surfaces (DH3_DESIGN.md §5)",
            "EVIDENCE_LABEL": "DISCOVERY_2020_2024 (see DH3_DESIGN.md §5 for exposure per card)",
            "EXECUTED": None, "HYPOTHESIS_ID": ",".join(run),
            "MULTIPLICITY_METHOD": f"Holm over the {len(run)} executed cells of the card, week-cluster bootstrap two-sided p at 0.05",
            "PREREG_PATH": "docs/research/DH3_PREREG.json", "PREREG_SHA256": sha, "PRIMARY_TEST_COUNT": len(run),
            "REGISTERED": K.DESIGN_DATE, "REPLICATION_EXECUTED": False, "REPLICATION_OF": None,
            "REPLICATION_SURFACE": K.REPLICATION.get(card, "prospective live tracking only"),
            "RERUN_AUTHORIZED": False, "RESULT_PATH": "docs/research/DH3_RESULT_DISCOVERY.json", "RESULT_SHA256": None,
            "ROBUSTNESS_TEST_COUNT": 0, "SEARCH_FAMILY_ID": K.SEARCH_FAMILY_ID, "SECONDARY_TEST_COUNT": 0,
            "STATUS": "REGISTERED", "TEST_FAMILY_ID": spec["TEST_FAMILY_ID"]})
    ledger["SEARCH_FAMILIES"].append({
        "CLOSED_AT_FEASIBILITY": {hid: c["FEASIBILITY_STATUS"] for hid, c in body["CELLS"].items() if not c["EXECUTE"]},
        "CLOSED_BEFORE_FEASIBILITY": 9,
        "EXECUTABLE_NOW_CARDS": len({c["CARD"] for c in body["CELLS"].values() if c["EXECUTE"]}),
        "EXECUTED_HYPOTHESES": 0, "EXECUTED_TESTS": 0, "GENERATED_CARDS": 24, "PROMISING_PROTOTYPES": 0,
        "REGISTERED_TESTS": sum(1 for c in body["CELLS"].values() if c["EXECUTE"]), "SEARCH_FAMILY_ID": K.SEARCH_FAMILY_ID,
        "SOURCE": "Owner decision 2026-10-04 (DH3_DESIGN.md): five cards of three (positioning, liquidity, options, levels, spot<->perp)"})
    LEDGER.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n")


def run() -> dict:
    body = prereg()
    text = json.dumps(body, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    V.PREREG.write_text(text)
    sha = hashlib.sha256(text.encode()).hexdigest()
    register(sha, body)
    return {"PREREG_SHA256": sha, "EXECUTE": {k: v["EXECUTE"] for k, v in body["CELLS"].items()}}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
