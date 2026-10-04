"""DH1 one-shot evaluator (contract V1 gates, frozen before any outcome).

python -m scripts.research.dh1.evaluate --surface DISCOVERY
python -m scripts.research.dh1.evaluate --surface REPLICATION

It refuses to run unless `DH1_PREREG.json` is committed and every bound code, data and feasibility
digest matches, and it refuses a second run of the same surface. Replication runs only the cells
that discovery classified `PROMISING_PROTOTYPE`, with the frozen discovery models.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np

from . import constants as K
from . import data as D
from . import events as E
from . import feasibility as F
from . import outcomes as O
from . import stats as S

REPO = Path(__file__).resolve().parents[3]
PREREG = REPO / "docs/research/DH1_PREREG.json"
RESULT = {"DISCOVERY": REPO / "docs/research/DH1_RESULT_DISCOVERY.json",
          "REPLICATION": REPO / "docs/research/DH1_RESULT_REPLICATION.json"}
BOUND_FILES = ["scripts/research/dh1/constants.py", "scripts/research/dh1/data.py", "scripts/research/dh1/events.py",
               "scripts/research/dh1/outcomes.py", "scripts/research/dh1/stats.py", "scripts/research/dh1/evaluate.py",
               "scripts/research/dh1/feasibility.py", "beta/levels.py", "beta/hist_series.py",
               "scripts/research/owner_cards_r03/data.py"]


def code_digests() -> dict:
    return {p: hashlib.sha256((REPO / p).read_bytes()).hexdigest() for p in BOUND_FILES}


def _committed_clean(paths: list) -> bool:
    for p in paths:
        if subprocess.run(["git", "ls-files", "--error-unmatch", p], cwd=REPO, capture_output=True).returncode:
            return False
    return subprocess.run(["git", "diff", "--quiet", "HEAD", "--", *paths], cwd=REPO).returncode == 0


def verify(surface: str) -> dict:
    if not PREREG.exists():
        raise RuntimeError("DH1: no preregistration; nothing may be evaluated")
    prereg = json.loads(PREREG.read_text())
    if prereg["CODE_DIGESTS"] != code_digests():
        raise RuntimeError("DH1: bound code drifted from the preregistration")
    if prereg["DATASETS"] != D.dataset_identity():
        raise RuntimeError("DH1: dataset identity drifted from the preregistration")
    if prereg["FEASIBILITY_SHA256"] != F.digest():
        raise RuntimeError("DH1: feasibility record drifted from the preregistration")
    if not _committed_clean(["docs/research/DH1_PREREG.json", "docs/research/DH1_FEASIBILITY.json", *BOUND_FILES]):
        raise RuntimeError("DH1: preregistration and bound files must be committed and clean")
    if RESULT[surface].exists():
        raise RuntimeError(f"DH1: {surface} was already evaluated (one-shot)")
    if surface == "REPLICATION":
        if not RESULT["DISCOVERY"].exists() or not _committed_clean(["docs/research/DH1_RESULT_DISCOVERY.json"]):
            raise RuntimeError("DH1: replication needs the committed discovery result")
    return prereg


# ---------------------------------------------------------------- one cell
def evaluate_cell(rows: list, h: dict, surface: str, seed: int, model: dict | None = None) -> dict:
    levels = None if model is None else {k: v for k, v in model["LEVELS"].items()}
    X, labels, levels = E.design_matrix(rows, h, levels)
    y = np.array([r["Y"] for r in rows], dtype=float)
    cid = S.cluster_ids(rows)
    c_epoch = S.cluster_epochs(rows, cid)
    xtx, xty, arms = S.aggregates(X, y, cid)
    rng = np.random.default_rng(seed)
    beta_full = S.solve(xtx.sum(0), xty.sum(0))
    shift = float(beta_full[S.S_COL])
    draws = S.bootstrap_beta(xtx, xty, K.BOOT_DRAWS, rng)
    keep = [c for c in range(X.shape[1]) if c != S.S_COL]
    beta_null = S.fit(X[:, keep], y)
    if model is None:
        bss = S.crossfit_bss(X, y, [r["EPOCH"] for r in rows])
    else:
        bf = S.brier(X @ np.array(model["BETA_FULL"]), y)
        bn = S.brier(X[:, keep] @ np.array(model["BETA_NULL"]), y)
        bss = None if bn <= 0 else 1.0 - bf / bn
    epochs = [e for e, _, _ in K.SURFACES[surface]["EPOCHS"]]
    het = S.het_test(xtx, xty, arms, c_epoch, epochs, shift, rng)
    st = X[:, S.S_COL] == 1
    return {
        "N": int(y.size), "N_STATE": int(st.sum()), "N_COMPARATOR": int((~st).sum()), "CLUSTERS": int(cid.max()) + 1,
        "RATE_STATE": float(y[st].mean()) if st.any() else None,
        "RATE_COMPARATOR": float(y[~st].mean()) if (~st).any() else None,
        "RATE_ALL": float(y.mean()),
        "ADJUSTED_SHIFT": shift,
        "CI95": [float(np.nanpercentile(draws, 2.5)), float(np.nanpercentile(draws, 97.5))],
        "P_BOOT": S.boot_p(draws), "BRIER_SKILL": bss, "HETEROGENEITY": het,
        "MODEL": {"LABELS": labels, "LEVELS": {k: list(v) for k, v in levels.items()},
                  "BETA_FULL": beta_full.tolist(), "BETA_NULL": beta_null.tolist()},
    }


def classify_discovery(c: dict, p_holm: float, het_assessable: bool) -> str:
    stat = p_holm < K.FAMILY_ALPHA
    big = abs(c["ADJUSTED_SHIFT"]) >= K.PRACTICAL_BAR
    calibrated = c["BRIER_SKILL"] is not None and c["BRIER_SKILL"] > 0
    het = c["HETEROGENEITY"]["STATUS"]
    if stat and big and calibrated:
        if het == "FAIL_HETEROGENEOUS_UNEXPLAINED" and het_assessable:
            return "HETEROGENEOUS_UNEXPLAINED"
        return "PROMISING_PROTOTYPE"
    lo, hi = c["CI95"]
    if -K.PRACTICAL_BAR < lo and hi < K.PRACTICAL_BAR:
        return "NO_INCREMENTAL_STRUCTURE"
    if stat and (not big or not calibrated):
        return "NO_INCREMENTAL_STRUCTURE"
    return "INCONCLUSIVE"


def classify_replication(c: dict, p_holm: float, disc_shift: float, powered: bool, het_assessable: bool) -> str:
    same = np.sign(c["ADJUSTED_SHIFT"]) == np.sign(disc_shift)
    stat = p_holm < K.FAMILY_ALPHA
    big = abs(c["ADJUSTED_SHIFT"]) >= K.PRACTICAL_BAR
    calibrated = c["BRIER_SKILL"] is not None and c["BRIER_SKILL"] > 0
    het = c["HETEROGENEITY"]["STATUS"]
    if same and stat and big and calibrated:
        if het == "FAIL_HETEROGENEOUS_UNEXPLAINED" and het_assessable:
            return "HETEROGENEOUS_UNEXPLAINED"
        return "SUPPORTED_UNCONDITIONAL"
    if stat and not same:
        return "REPLICATION_FAILED"
    if not powered and not stat:
        return "REPLICATION_INCONCLUSIVE"
    return "REPLICATION_FAILED"


DISPLAY = {"SUPPORTED_UNCONDITIONAL": "Проверено", "PROMISING_PROTOTYPE": "Гипотеза",
           "REPLICATION_INCONCLUSIVE": "Гипотеза"}


# ---------------------------------------------------------------- runs
def run(surface: str) -> dict:
    prereg = verify(surface)
    feas = json.loads(F.OUT_JSON.read_text())
    if surface == "DISCOVERY":
        cells = [h for h in K.HYPOTHESES if prereg["CELLS"][h["ID"]]["EXECUTE"]]
        models = {}
    else:
        disc = json.loads(RESULT["DISCOVERY"].read_text())
        cells = [h for h in K.HYPOTHESES if disc["CELLS"].get(h["ID"], {}).get("CLASS") == "PROMISING_PROTOTYPE"]
        models = {h["ID"]: disc["CELLS"][h["ID"]]["MODEL"] for h in cells}
    out = {"PROGRAM_ID": K.PROGRAM_ID, "SURFACE": surface, "PREREG_SHA256": hashlib.sha256(PREREG.read_bytes()).hexdigest(),
           "CODE_DIGESTS": code_digests(), "ONE_SHOT": True, "CELLS": {}}
    if not cells:
        out["NOTE"] = "no cell to evaluate on this surface; no outcome was read"
        RESULT[surface].write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
        return out
    bars, spot = D.surface(surface)
    events = {"DH1-L": E.level_events(bars, spot, surface), "DH1-B": E.move_events(bars, spot, surface)}
    res = {}
    for h in cells:
        rows = E.cell_rows(events[h["CARD"]], h)
        rows_y = O.attach(bars, rows, h["CARD"])
        seed = K.BOOT_SEED + 101 * K.HYPOTHESES.index(h) + (0 if surface == "DISCOVERY" else 7)
        res[h["ID"]] = evaluate_cell(rows_y, h, surface, seed, models.get(h["ID"]))
        res[h["ID"]]["MISSING_OUTCOME_DROPPED"] = len(rows) - len(rows_y)
    for card in K.CARDS:
        fam = {hid: res[hid]["P_BOOT"] for hid in res if K.HYPOTHESIS_BY_ID[hid]["CARD"] == card}
        for hid, p in S.holm(fam).items():
            res[hid]["P_HOLM"] = p
            res[hid]["HOLM_FAMILY"] = sorted(fam)
    for hid, c in res.items():
        dec = feas["CELLS"][hid]["DECISION"]
        if surface == "DISCOVERY":
            c["CLASS"] = classify_discovery(c, c["P_HOLM"], dec["HET_DISCOVERY"] == "ASSESSABLE")
        else:
            disc_shift = json.loads(RESULT["DISCOVERY"].read_text())["CELLS"][hid]["ADJUSTED_SHIFT"]
            c["CLASS"] = classify_replication(c, c["P_HOLM"], disc_shift, dec["REPLICATION_POWERED"],
                                              dec["HET_REPLICATION"] == "ASSESSABLE")
        c["BOT_STATUS"] = DISPLAY.get(c["CLASS"])
        out["CELLS"][hid] = c
    RESULT[surface].write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--surface", choices=("DISCOVERY", "REPLICATION"), required=True)
    args = ap.parse_args()
    result = run(args.surface)
    for hid, c in result["CELLS"].items():
        print(hid, c["CLASS"], round(c["ADJUSTED_SHIFT"], 4), round(c["P_HOLM"], 4), c["BRIER_SKILL"])
