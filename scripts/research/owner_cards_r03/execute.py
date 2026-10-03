"""One-shot scientific execution for OWNER_CARDS_R03.

Order: verify the permit and every frozen digest; build units from the frozen
definitions; open targets once; evaluate discovery; evaluate the BitMEX
replication for prototypes whose card declares it; write RESULT. No parameter
is read from anywhere but constants.py and the frozen planning file.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np

from . import constants as K
from . import data as D
from . import evaluate as E
from . import outcomes as O
from . import states as S
from . import support as SP

REPO = Path(__file__).resolve().parents[3]
PERMIT = REPO / "docs/research/OWNER_CARDS_R03_EXECUTION_PERMIT.json"
RESULT_JSON = REPO / "docs/research/OWNER_CARDS_R03_RESULT.json"
RESULT_MD = REPO / "docs/research/OWNER_CARDS_R03_RESULT.md"
UNITS_DIR = REPO / "docs/research/owner_cards_r03"


def sha256_path(rel: str) -> str:
    return D.sha256_file(REPO / rel)


def verify_permit() -> dict:
    permit = json.loads(PERMIT.read_text())
    if permit.get("EXECUTION_AUTHORIZED") is not True or permit.get("PROGRAM_ID") != K.PROGRAM_ID:
        raise RuntimeError("permit does not authorize execution")
    if RESULT_JSON.exists():
        raise RuntimeError("RESULT already exists: rerun is not authorized")
    mismatches = {rel: (expected, sha256_path(rel)) for rel, expected in permit["FROZEN_ARTIFACT_SHA256"].items()
                  if sha256_path(rel) != expected}
    if mismatches:
        raise RuntimeError(f"frozen artifact digest mismatch: {mismatches}")
    return permit


def evaluate_surface(hid: str, units: list[dict], bars: O.Bars, seed_offset: int) -> dict:
    h = K.HYPOTHESIS_BY_ID[hid]
    att = O.attach_targets(units, bars)
    stats = O.standardize(att["rows"])
    adjusted = O.nuisance_adjust(att["rows"], stats)
    diffs = O.unit_differences(units, att["rows"], stats, adjusted)
    flip = E.signflip_p(diffs["d"], K.SIGNFLIP_DRAWS, K.SIGNFLIP_SEED + seed_offset)
    flip_adj = E.signflip_p(diffs["d_adj"], K.SIGNFLIP_DRAWS, K.SIGNFLIP_SEED + 100 + seed_offset)
    epochs = E.epoch_record(diffs["d"], diffs["years"], seed=K.HET_SEED + seed_offset)
    block_se = E.moving_block_se(diffs["d"], K.HET_BLOCK_UNITS, 2000, K.HET_SEED + 200 + seed_offset)
    practical = E.practical_gate(flip["ESTIMATE"], h["DIRECTION"])
    wording = E.nuisance_wording(flip["ESTIMATE"], flip_adj["ESTIMATE"])
    available = int(np.sum(np.isfinite(diffs["d"])))
    return {
        "UNITS_DECLARED": len(units), "UNITS_EVALUATED": available,
        "DROPPED_UNITS_MISSING_BARS": diffs["DROPPED_UNITS_MISSING_BARS"],
        "WINDOWS_TOTAL": len(att["rows"]),
        "WINDOWS_UNAVAILABLE": int(sum(1 for r in att["rows"] if not np.isfinite(r[6]))),
        "ESTIMATE": flip["ESTIMATE"], "SE_SIGNFLIP": flip["SE_SIGNFLIP"], "SE_MOVING_BLOCK": block_se,
        "P_TWO_SIDED": flip["P_TWO_SIDED"], "PRACTICAL": practical,
        "NUISANCE_ADJUSTED": {"ESTIMATE": flip_adj["ESTIMATE"], "P_TWO_SIDED": flip_adj["P_TWO_SIDED"],
                              "N": flip_adj["N"], **wording},
        "EPOCHS": epochs,
        "PER_UNIT": {"UNIT_ID": diffs["unit_ids"], "YEAR": diffs["years"].tolist(), "D": diffs["d"].tolist(),
                     "D_ADJ": [None if not np.isfinite(x) else float(x) for x in diffs["d_adj"]]},
    }


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    except Exception:  # noqa: BLE001
        return "UNKNOWN"


def main() -> None:
    K.assert_locked()
    permit = verify_permit()
    planning = json.loads((REPO / "docs/research/OWNER_CARDS_R03_PLANNING.json").read_text())
    feasibility = json.loads((REPO / "docs/research/OWNER_CARDS_R03_FEASIBILITY.json").read_text())
    executable = [hid for hid in permit["EXECUTED_HYPOTHESES"]]
    for hid in executable:
        if not feasibility["SUMMARY"][hid]["EXECUTABLE"]:
            raise RuntimeError(f"{hid} is not executable per the frozen feasibility")
    nyse = D.nyse_events()
    btc = O.Bars(D.load_btc_1m(), K.MINUTE_MS)
    bitmex = O.Bars(D.load_bitmex_5m(), 5 * K.MINUTE_MS)
    metrics = SP.panel_metrics() if any(h.startswith("R03-B") for h in executable) else None

    # Identity check: the units rebuilt now must match the frozen unit digests.
    results = {}
    for i, hid in enumerate(executable):
        units = S.build_units(hid, "DISCOVERY", nyse=nyse, metrics=metrics)
        digest = hashlib.sha256(json.dumps(units, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if digest != permit["FROZEN_UNIT_DIGESTS"][hid]:
            raise RuntimeError(f"unit digest drift for {hid}")
        results[hid] = {"DISCOVERY": evaluate_surface(hid, units, btc, i), "UNIT_DIGEST": digest}

    # Holm within each card over its executed hypotheses, two-sided.
    cards = {}
    for cid, card in K.CARDS.items():
        members = [hid for hid in executable if K.HYPOTHESIS_BY_ID[hid]["CARD"] == cid]
        if not members:
            continue
        holm = E.holm({hid: results[hid]["DISCOVERY"]["P_TWO_SIDED"] for hid in members}, K.FAMILY_ALPHA)
        cards[cid] = {"TEST_FAMILY_ID": card["TEST_FAMILY_ID"], "EXECUTED": members, "HOLM": holm}
        for hid in members:
            r = results[hid]["DISCOVERY"]
            assess = feasibility["DETAIL"][hid]["COMPILER"]["HETEROGENEITY_ASSESSABILITY"]["STATUS"] == "ASSESSABLE"
            r["HOLM"] = holm[hid]
            r["STATISTICAL_GATE"] = bool(holm[hid]["REJECT"])
            r["PRACTICAL_GATE"] = bool(r["PRACTICAL"]["PASS"])
            r["EPOCH_GATE"] = r["EPOCHS"]["STATUS"] if assess else "NOT_ASSESSABLE"
            r["PRODUCT_FREQUENCY_GATE"] = bool(r["UNITS_EVALUATED"] / 5.0 >= K.PRODUCT_FREQUENCY_MIN_PER_YEAR)
            results[hid]["DISCOVERY_CLASS"] = E.classify(
                integrity=True, statistical=r["STATISTICAL_GATE"], practical=r["PRACTICAL_GATE"],
                epoch_status=r["EPOCHS"]["STATUS"], assessable=assess)

    # Replication (BitMEX 2017-2019) for discovery prototypes whose card declares it.
    for cid, card in cards.items():
        rep_members = [hid for hid in card["EXECUTED"]
                       if results[hid]["DISCOVERY_CLASS"] == "PROMISING_PROTOTYPE" and K.HYPOTHESIS_BY_ID[hid]["REPLICATION"]
                       and K.CARDS[cid]["REPLICATION"] == "BITMEX_HISTORICAL"]
        for j, hid in enumerate(rep_members):
            units = S.build_units(hid, "REPLICATION", nyse=nyse)
            results[hid]["REPLICATION"] = evaluate_surface(hid, units, bitmex, 50 + j)
        if rep_members:
            holm_r = E.holm({hid: results[hid]["REPLICATION"]["P_TWO_SIDED"] for hid in rep_members}, K.FAMILY_ALPHA)
            card["REPLICATION_HOLM"] = holm_r
            for hid in rep_members:
                r = results[hid]["REPLICATION"]
                r["HOLM"] = holm_r[hid]
                r["STATISTICAL_GATE"] = bool(holm_r[hid]["REJECT"])
                r["PRACTICAL_GATE"] = bool(r["PRACTICAL"]["PASS"])
                results[hid]["REPLICATION_OUTCOME"] = "REPLICATED" if (r["STATISTICAL_GATE"] and r["PRACTICAL_GATE"]) else "NOT_REPLICATED"
        for hid in card["EXECUTED"]:
            cls = results[hid]["DISCOVERY_CLASS"]
            rep = results[hid].get("REPLICATION_OUTCOME")
            if cls != "PROMISING_PROTOTYPE":
                final = cls
            elif rep == "REPLICATED":
                final = "SUPPORTED_UNCONDITIONAL"
            elif rep == "NOT_REPLICATED":
                final = "PROMISING_PROTOTYPE_NOT_REPLICATED"
            else:
                final = "PROMISING_PROTOTYPE"
                results[hid]["REPLICATION_OUTCOME"] = "NOT_AVAILABLE_IN_THIS_UNIT" if not K.HYPOTHESIS_BY_ID[hid]["REPLICATION"] or K.CARDS[cid]["REPLICATION"] != "BITMEX_HISTORICAL" else rep
            if final == "SUPPORTED_UNCONDITIONAL" and not results[hid]["DISCOVERY"]["PRODUCT_FREQUENCY_GATE"]:
                final = "SUPPORTED_BUT_PRODUCT_SPARSE"
            results[hid]["FINAL_CLASS"] = final

    payload = {
        "PROGRAM_ID": K.PROGRAM_ID, "KIND": "CANONICAL_SCIENTIFIC_EXECUTION", "ONE_SHOT": True,
        "EXECUTED_AT_UTC": dt.datetime.now(tz=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "EXECUTION_HEAD": git_head(), "PERMIT_SHA256": D.sha256_file(PERMIT),
        "PREREG_SHA256": sha256_path("docs/research/OWNER_CARDS_R03_PREREG.json"),
        "DATASETS": D.dataset_identity(), "EXECUTED_HYPOTHESES": executable,
        "CARDS": cards, "RESULTS": results,
        "EVIDENCE_LABEL": "DISCOVERY_ON_HISTORICALLY_EXPOSED_BINANCE_2020_2024; REPLICATION_ON_BITMEX_2017_2019_WHERE_DECLARED",
        "NOT_VALIDATED_TRADING_EDGE": True, "NOT_DIRECTIONAL": True, "NOT_CAUSAL": True,
        "PROTECTED_2025_2026_OPENED": False, "RERUN_AUTHORIZED": False,
    }
    body = json.dumps(SP._jsonable(payload), indent=2, sort_keys=True) + "\n"
    RESULT_JSON.write_text(body)
    print(json.dumps({hid: {"FINAL": r["FINAL_CLASS"], "DISC_EST": round(r["DISCOVERY"]["ESTIMATE"], 3),
                            "DISC_P": r["DISCOVERY"]["P_TWO_SIDED"], "REP": r.get("REPLICATION_OUTCOME"),
                            "REP_EST": None if "REPLICATION" not in r else round(r["REPLICATION"]["ESTIMATE"], 3),
                            "WORDING": r["DISCOVERY"]["NUISANCE_ADJUSTED"]["WORDING"]}
                      for hid, r in results.items()}, indent=1))


if __name__ == "__main__":
    main()
