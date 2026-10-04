"""DH1 twin preregistration (contract V1 §1), written after the outcome-blind feasibility pass and
before any outcome. It binds the design, the cells to execute, the code, data and feasibility
digests, and registers the test families in SCIENTIFIC_TEST_LEDGER.json.

python -m scripts.research.dh1.freeze
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import constants as K
from . import data as D
from . import evaluate as V
from . import events as E
from . import feasibility as F

REPO = Path(__file__).resolve().parents[3]
LEDGER = REPO / "docs/research/SCIENTIFIC_TEST_LEDGER.json"


def prereg() -> dict:
    K.assert_locked()
    feas = json.loads(F.OUT_JSON.read_text())
    if feas["MARKET_OUTCOMES_OPENED"] is not False:
        raise RuntimeError("DH1: feasibility must be outcome-blind")
    cells = {}
    for h in K.HYPOTHESES:
        c = feas["CELLS"][h["ID"]]
        cells[h["ID"]] = {
            **{k: h[k] for k in ("CARD", "STATE", "STATE_TEXT", "COMPARATOR", "MECHANISM", "ATLAS_CELL")},
            "EXECUTE": c["DECISION"]["EXECUTE"], "FEASIBILITY_STATUS": c["DECISION"]["STATUS"],
            "REPLICATION_POWERED": c["DECISION"]["REPLICATION_POWERED"],
            "PLANNING": {s: {k: c[s][k] for k in ("N", "N_STATE", "N_COMPARATOR", "MDE_80", "POWER_AT_50PCT_PLANNING",
                                                  "POWER_AT_75PCT_PLANNING", "HET_POWER_2X")}
                         for s in ("DISCOVERY", "REPLICATION")},
            "NUISANCE": list(E.nuisance_names(h)),
        }
    return {
        "PROGRAM_ID": K.PROGRAM_ID, "SEARCH_FAMILY_ID": K.SEARCH_FAMILY_ID, "DESIGN_DATE": K.DESIGN_DATE,
        "DECISION_RECORD": K.DECISION_RECORD, "EVALUATION_CONTRACT": K.EVALUATION_CONTRACT,
        "CLAIM_TYPE": "INCREMENTAL", "TARGET_CLASS": "UNCONDITIONAL over the declared event population of each card",
        "CARDS": K.CARDS, "CELLS": cells, "SURFACES": K.SURFACES, "PROSPECTIVE": K.PROSPECTIVE,
        "ESTIMAND": ("Coefficient of the state indicator in a linear probability model of the endpoint on the state and "
                     "the nuisance dummies (first level dropped); every event weighs the same."),
        "INFERENCE": (f"Cluster bootstrap over ISO weeks cut at epoch boundaries, {K.BOOT_DRAWS} draws, seed base "
                      f"{K.BOOT_SEED}; two-sided p = 2 min(P(b*<=0), P(b*>=0)); Holm within each card at {K.FAMILY_ALPHA}."),
        "PRACTICAL_BAR": {"ABS_SHIFT_MIN": K.PRACTICAL_BAR, "BRIER_SKILL": "> 0 (discovery: leave-one-epoch-out "
                          "cross-fit; replication: frozen discovery models)",
                          "RATIONALE": "owner bar 2026-10-04: 3 pp against 'обычно' plus calibration; the product's "
                                       "materiality floor (beta MATERIAL_DIFF = 0.03)"},
        "HETEROGENEITY": {"EPOCHS": "calendar years (replication: 2017H2, 2018, 2019)", "TEST": "Cochran-type Q with fixed "
                          f"inverse-variance weights, null by permuting week clusters across epochs ({K.HET_PERM_DRAWS} draws, "
                          f"seed {K.HET_SEED}); opposite-sign one-sided p < {K.OPPOSITE_ALPHA}; NOT_ASSESSABLE when the "
                          "outcome-blind power to detect a 2x epoch difference is below 0.5 (does not fail the cell)"},
        "CLASSIFICATION": {
            "DISCOVERY": "PROMISING_PROTOTYPE if Holm p < 0.05, |shift| >= 0.03 and Brier skill > 0 (and heterogeneity not "
                         "failed when assessable); HETEROGENEOUS_UNEXPLAINED if only heterogeneity fails; "
                         "NO_INCREMENTAL_STRUCTURE if the 95% CI lies inside (-0.03, 0.03), or the shift is significant "
                         "but below the bar or not calibrated; otherwise INCONCLUSIVE",
            "REPLICATION": "only PROMISING_PROTOTYPE cells; SUPPORTED_UNCONDITIONAL if same sign, Holm p < 0.05, "
                           "|shift| >= 0.03, frozen Brier skill > 0 and heterogeneity not failed; REPLICATION_INCONCLUSIVE "
                           "if the replication surface was not powered and nothing significant; otherwise REPLICATION_FAILED",
            "BOT_STATUS": {"SUPPORTED_UNCONDITIONAL": "Проверено", "PROMISING_PROTOTYPE": "Гипотеза",
                           "REPLICATION_INCONCLUSIVE": "Гипотеза (live tracking decides)", "OTHER": "no number"},
        },
        "ALLOWED_INTERPRETATION": K.ALLOWED_INTERPRETATION, "FORBIDDEN_INTERPRETATION": K.FORBIDDEN_INTERPRETATION,
        "NO_RESCUE": "A failed cell is never re-scored with new parameters, states, horizons, sides, baselines or claim type.",
        "CODE_DIGESTS": V.code_digests(), "DATASETS": D.dataset_identity(), "FEASIBILITY_SHA256": F.digest(),
        "MARKET_OUTCOMES_OPENED_AT_FREEZE": False, "OBJECTS_2025_2026_USED": "none",
    }


def register(prereg_sha: str, body: dict) -> None:
    ledger = json.loads(LEDGER.read_text())
    if any(t["SEARCH_FAMILY_ID"] == K.SEARCH_FAMILY_ID for t in ledger["TESTS"]):
        raise RuntimeError("DH1 already registered")
    for card, spec in K.CARDS.items():
        run = [hid for hid, c in body["CELLS"].items() if c["CARD"] == card and c["EXECUTE"]]
        if not run:
            continue
        ledger["TESTS"].append({
            "CLASSIFICATION": None, "DATASET_ID": "CORE_BTC_BINANCE_V0 + DH1_BINANCE_SPOT_BTCUSDT_5M_V0 (discovery); "
                                                  "DH1_BITMEX_XBTUSD_TRADES_5M_V0 + DH1_BINANCE_SPOT_BTCUSDT_5M_V0 (replication)",
            "EVIDENCE_LABEL": "DISCOVERY_ON_BINANCE_2020_2024 (levels product-exposed, states new); REPLICATION_ON_BITMEX_BINANCE_SPOT_2017_2019",
            "EXECUTED": None, "HYPOTHESIS_ID": ",".join(run),
            "MULTIPLICITY_METHOD": f"Holm over the {len(run)} executed cells of the card, week-cluster bootstrap two-sided p at 0.05",
            "PREREG_PATH": "docs/research/DH1_PREREG.json", "PREREG_SHA256": prereg_sha,
            "PRIMARY_TEST_COUNT": len(run), "REGISTERED": K.DESIGN_DATE, "REPLICATION_EXECUTED": False,
            "REPLICATION_OF": None, "REPLICATION_SURFACE": "BitMEX XBTUSD trades + Binance spot 2017-09..2019-12 (same frozen rule); live tracking",
            "RERUN_AUTHORIZED": False, "RESULT_PATH": "docs/research/DH1_RESULT_DISCOVERY.json", "RESULT_SHA256": None,
            "ROBUSTNESS_TEST_COUNT": 0, "SEARCH_FAMILY_ID": K.SEARCH_FAMILY_ID, "SECONDARY_TEST_COUNT": 0,
            "STATUS": "REGISTERED", "TEST_FAMILY_ID": spec["TEST_FAMILY_ID"]})
    closed = {hid: c["FEASIBILITY_STATUS"] for hid, c in body["CELLS"].items() if not c["EXECUTE"]}
    ledger["SEARCH_FAMILIES"].append({
        "CLOSED_AT_FEASIBILITY": closed, "CLOSED_BEFORE_FEASIBILITY": 10,
        "EXECUTABLE_NOW_CARDS": len({c["CARD"] for c in body["CELLS"].values() if c["EXECUTE"]}),
        "EXECUTED_HYPOTHESES": 0, "EXECUTED_TESTS": 0, "GENERATED_CARDS": 15, "PROMISING_PROTOTYPES": 0,
        "REGISTERED_TESTS": sum(1 for c in body["CELLS"].values() if c["EXECUTE"]), "SEARCH_FAMILY_ID": K.SEARCH_FAMILY_ID,
        "SOURCE": ("Owner decision 2026-10-04 (DIRECTIONAL_HYPOTHESES_DECISION_V1.md): directional hypotheses for the bot; "
                   "15 candidates, 9 closed at red team, 1 deferred, 5 to feasibility")})
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
