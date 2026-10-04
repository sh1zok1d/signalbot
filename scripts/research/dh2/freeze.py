"""DH2 twin preregistration, written after the outcome-blind feasibility pass and before any
outcome; registers the executable test families in SCIENTIFIC_TEST_LEDGER.json.

python -m scripts.research.dh2.freeze
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.research.dh1 import constants as K1

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
        raise RuntimeError("DH2: feasibility must be outcome-blind")
    cells = {}
    for h in K.HYPOTHESES:
        c = feas["CELLS"][h["ID"]]
        cells[h["ID"]] = {**{k: h[k] for k in ("CARD", "STATE", "SOURCE", "REPLICATION", "ATLAS_CELL")},
                          "NUISANCE": list(E.nuisance_names(h)), "EXECUTE": c["DECISION"]["EXECUTE"],
                          "FEASIBILITY_STATUS": c["DECISION"]["STATUS"], "DECISION": c["DECISION"],
                          "PLANNING": {s: {k: c[s].get(k) for k in ("N", "N_STATE", "N_COMPARATOR", "MDE_80",
                                                                     "POWER_AT_50PCT_PLANNING", "POWER_AT_75PCT_PLANNING",
                                                                     "HET_POWER_EPOCH_2X", "HET_POWER_SYMBOL_2X",
                                                                     "BTC_ONLY_MDE_80")}
                                       for s in ("DISCOVERY", "REPLICATION")}}
    return {
        "PROGRAM_ID": K.PROGRAM_ID, "SEARCH_FAMILY_ID": K.SEARCH_FAMILY_ID, "DESIGN_DATE": K.DESIGN_DATE,
        "DESIGN_RECORD": K.DESIGN_RECORD, "DECISION_RECORD": K1.DECISION_RECORD,
        "EVALUATION_CONTRACT": K1.EVALUATION_CONTRACT, "CLAIM_TYPE": "INCREMENTAL",
        "TARGET_CLASS": "UNCONDITIONAL over the pooled event population of six coins (coin fixed effects)",
        "ATLAS_OVERRIDE": ("Owner decision 2026-10-04 overrides the INFORMATIONALLY_WEAK routing 'no pooling to manufacture "
                           "N' for DH2 only; the claim is about six coins, guarded by the coin-heterogeneity gate."),
        "CARDS": K.CARDS, "CELLS": cells, "SYMBOLS": list(K.SYMBOLS), "LEVEL_TYPES": list(K.LEVEL_TYPES),
        "DISCOVERY": {"SYMBOL_STARTS": K.DISCOVERY, "END": K.DISCOVERY_END, "EPOCHS": K.DISCOVERY_EPOCHS},
        "REPLICATION": {"SPOT_4_COINS": K.REPLICATION_SPOT, "BTC_BITMEX": "DH1 replication surface 2017-09..2019-12",
                        "END": K.REPLICATION_END, "EPOCHS": K.REPLICATION_EPOCHS},
        "PROSPECTIVE": {**K1.PROSPECTIVE, "SYMBOLS": list(K.SYMBOLS)},
        "ESTIMAND": "State coefficient of a linear probability model with nuisance dummies and coin fixed effects.",
        "INFERENCE": (f"ISO-week clusters pooled across coins and cut at year boundaries; bootstrap {K1.BOOT_DRAWS} draws, "
                      f"seed base {K.BOOT_SEED}; Holm within each card at {K1.FAMILY_ALPHA}."),
        "PRACTICAL_BAR": {"ABS_SHIFT_MIN": K1.PRACTICAL_BAR, "BRIER_SKILL": "> 0"},
        "HETEROGENEITY": {"EPOCH": "as DH1", "SYMBOL": ("Q over coins with fixed inverse-variance weights; null by permuting "
                                                        "week x coin clusters across coins; a significant Q with a coin "
                                                        "significantly opposite fails the cell when the gate's power for a 2x "
                                                        "difference is >= 0.5, otherwise NOT_ASSESSABLE")},
        "CLASSIFICATION": "as DH1 (DH1_PREREG.json CLASSIFICATION), plus the coin gate",
        "BTC_ONLY": "reported for every executed cell; descriptive, never gates",
        "NO_RESCUE": "A failed cell is never re-scored with new parameters, states, coins, horizons, sides, baselines or claim type.",
        "CODE_DIGESTS": V.code_digests(), "DATASETS": D.dataset_identity(), "FEASIBILITY_SHA256": F.digest(),
        "MARKET_OUTCOMES_OPENED_AT_FREEZE": False, "OBJECTS_2025_2026_USED": "none",
    }


def register(sha: str, body: dict) -> None:
    ledger = json.loads(LEDGER.read_text())
    if any(t["SEARCH_FAMILY_ID"] == K.SEARCH_FAMILY_ID for t in ledger["TESTS"]):
        raise RuntimeError("DH2 already registered")
    for card, spec in K.CARDS.items():
        run = [hid for hid, c in body["CELLS"].items() if c["CARD"] == card and c["EXECUTE"]]
        if not run:
            continue
        ledger["TESTS"].append({
            "CLASSIFICATION": None,
            "DATASET_ID": "CORE_BTC_BINANCE_V0 + DH1_BINANCE_SPOT_BTCUSDT_5M_V0 + DH2_BINANCE_UM_ALTS_5M_V0 + "
                          "DH2_BINANCE_SPOT_ALTS_5M_V0 (discovery); spot 4 coins or DH1 BitMEX (replication)",
            "EVIDENCE_LABEL": "DISCOVERY_ON_SIX_COINS_2020_2024 (BTC levels exposed; alt levels unused); REPLICATION_2017_2019",
            "EXECUTED": None, "HYPOTHESIS_ID": ",".join(run),
            "MULTIPLICITY_METHOD": f"Holm over the {len(run)} executed cells of the card, week-cluster bootstrap two-sided p at 0.05",
            "PREREG_PATH": "docs/research/DH2_PREREG.json", "PREREG_SHA256": sha, "PRIMARY_TEST_COUNT": len(run),
            "REGISTERED": K.DESIGN_DATE, "REPLICATION_EXECUTED": False, "REPLICATION_OF": None,
            "REPLICATION_SURFACE": "per cell: spot BTC/ETH/BNB/XRP 2017-2019 (DH2-L3) or DH1 BitMEX BTC (DH2-L1, DH2-B2); live tracking",
            "RERUN_AUTHORIZED": False, "RESULT_PATH": "docs/research/DH2_RESULT_DISCOVERY.json", "RESULT_SHA256": None,
            "ROBUSTNESS_TEST_COUNT": 0, "SEARCH_FAMILY_ID": K.SEARCH_FAMILY_ID, "SECONDARY_TEST_COUNT": 0,
            "STATUS": "REGISTERED", "TEST_FAMILY_ID": spec["TEST_FAMILY_ID"]})
    ledger["SEARCH_FAMILIES"].append({
        "CLOSED_AT_FEASIBILITY": {hid: c["FEASIBILITY_STATUS"] for hid, c in body["CELLS"].items() if not c["EXECUTE"]},
        "CLOSED_BEFORE_FEASIBILITY": 0,
        "EXECUTABLE_NOW_CARDS": len({c["CARD"] for c in body["CELLS"].values() if c["EXECUTE"]}),
        "EXECUTED_HYPOTHESES": 0, "EXECUTED_TESTS": 0, "GENERATED_CARDS": 3, "PROMISING_PROTOTYPES": 0,
        "REGISTERED_TESTS": sum(1 for c in body["CELLS"].values() if c["EXECUTE"]), "SEARCH_FAMILY_ID": K.SEARCH_FAMILY_ID,
        "SOURCE": "Owner decision 2026-10-04 (DH2_POOLED_DESIGN.md): DH1-L1, L3, B2 pooled over six coins"})
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
