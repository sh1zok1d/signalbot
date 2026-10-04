"""DH3 one-shot evaluator (contract V1 gates; range and directional endpoints).

python -m scripts.research.dh3.evaluate --surface DISCOVERY
python -m scripts.research.dh3.evaluate --surface REPLICATION     # card DH3-V only (spot 2017-2019)

Refuses to run without the committed preregistration and matching code, data and feasibility
digests; refuses a second run of a surface; replicates only DH3-V cells that discovery classified
PROMISING_PROTOTYPE, with the frozen discovery models.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from scripts.research.dh1 import constants as K1
from scripts.research.dh1 import evaluate as V1
from scripts.research.dh1 import stats as S
from scripts.research.dh2 import feasibility as F2

from . import constants as K
from . import data as D
from . import feasibility as F
from . import features as FT
from . import outcomes as O

REPO = Path(__file__).resolve().parents[3]
PREREG = REPO / "docs/research/DH3_PREREG.json"
RESULT = {"DISCOVERY": REPO / "docs/research/DH3_RESULT_DISCOVERY.json",
          "REPLICATION": REPO / "docs/research/DH3_RESULT_REPLICATION.json"}
BOUND_FILES = sorted({
    *(f"scripts/research/dh3/{m}.py" for m in ("constants", "data", "aggtrades", "features", "outcomes", "feasibility",
                                                "evaluate")),
    *(f"scripts/research/dh2/{m}.py" for m in ("constants", "data", "events", "feasibility")),
    *(f"scripts/research/dh1/{m}.py" for m in ("constants", "data", "events", "outcomes", "stats", "evaluate")),
    "beta/levels.py", "beta/hist_series.py", "scripts/research/owner_cards_r03/data.py"})
DISPLAY = {"SUPPORTED_UNCONDITIONAL": "Проверено", "PROMISING_PROTOTYPE": "Гипотеза", "REPLICATION_INCONCLUSIVE": "Гипотеза"}


def code_digests() -> dict:
    return {p: hashlib.sha256((REPO / p).read_bytes()).hexdigest() for p in BOUND_FILES}


def verify(surface: str) -> dict:
    if not PREREG.exists():
        raise RuntimeError("DH3: no preregistration; nothing may be evaluated")
    prereg = json.loads(PREREG.read_text())
    if prereg["CODE_DIGESTS"] != code_digests():
        raise RuntimeError("DH3: bound code drifted from the preregistration")
    if prereg["DATASETS"] != D.dataset_identity():
        raise RuntimeError("DH3: dataset identity drifted from the preregistration")
    if prereg["FEASIBILITY_SHA256"] != F.digest():
        raise RuntimeError("DH3: feasibility record drifted from the preregistration")
    if not V1._committed_clean(["docs/research/DH3_PREREG.json", "docs/research/DH3_FEASIBILITY.json", *BOUND_FILES]):
        raise RuntimeError("DH3: preregistration and bound files must be committed and clean")
    if RESULT[surface].exists():
        raise RuntimeError(f"DH3: {surface} was already evaluated (one-shot)")
    if surface == "REPLICATION" and (not RESULT["DISCOVERY"].exists()
                                     or not V1._committed_clean(["docs/research/DH3_RESULT_DISCOVERY.json"])):
        raise RuntimeError("DH3: replication needs the committed discovery result")
    return prereg


def skill(pred_full: np.ndarray, pred_null: np.ndarray, y: np.ndarray, clip: bool) -> float | None:
    if clip:
        bf, bn = S.brier(pred_full, y), S.brier(pred_null, y)
    else:
        bf, bn = float(np.sum((pred_full - y) ** 2)), float(np.sum((pred_null - y) ** 2))
    return None if bn <= 0 else 1.0 - bf / bn


def crossfit_skill(X: np.ndarray, y: np.ndarray, epochs: list, clip: bool) -> float | None:
    epochs = np.asarray(epochs)
    keep = [c for c in range(X.shape[1]) if c != S.S_COL]
    pf, pn, yy = [], [], []
    for e in sorted(set(epochs.tolist())):
        tr, te = epochs != e, epochs == e
        if te.sum() == 0 or tr.sum() == 0:
            continue
        pf.append(X[te] @ S.fit(X[tr], y[tr]))
        pn.append(X[te][:, keep] @ S.fit(X[tr][:, keep], y[tr]))
        yy.append(y[te])
    if not yy:
        return None
    return skill(np.concatenate(pf), np.concatenate(pn), np.concatenate(yy), clip)


def evaluate_cell(rows: list, h: dict, seed: int, model: dict | None = None) -> dict:
    clip = h["ENDPOINT"] != "RANGE_4H"
    X, labels, levels = FT.design_matrix(rows, h, None if model is None else model["LEVELS"])
    y = np.array([r["Y"] for r in rows], dtype=float)
    cid = S.cluster_ids(rows)
    c_epoch = S.cluster_epochs(rows, cid)
    xtx, xty, arms = S.aggregates(X, y, cid)
    rng = np.random.default_rng(seed)
    beta_full = S.solve(xtx.sum(0), xty.sum(0))
    shift = float(beta_full[S.S_COL])
    draws = S.bootstrap_beta(xtx, xty, K1.BOOT_DRAWS, rng)
    keep = [c for c in range(X.shape[1]) if c != S.S_COL]
    beta_null = S.fit(X[:, keep], y)
    if model is None:
        sk = crossfit_skill(X, y, [r["EPOCH"] for r in rows], clip)
    else:
        sk = skill(X @ np.array(model["BETA_FULL"]), X[:, keep] @ np.array(model["BETA_NULL"]), y, clip)
    epochs = sorted({r["EPOCH"] for r in rows}, key=K.epoch_rank)
    het = S.het_test(xtx, xty, arms, c_epoch, epochs, shift, rng)
    syms = sorted({r["SYMBOL"] for r in rows})
    if len(syms) >= 3:
        scid, slabels = F2.symbol_clusters(rows)
        sx, sy, sa = S.aggregates(X, y, scid)
        het_sym = S.het_test(sx, sy, sa, slabels, syms, shift, rng)
    else:
        het_sym = {"STATUS": "NOT_ASSESSABLE", "REASON": "fewer than 3 coins"}
    st = X[:, S.S_COL] == 1
    by_symbol = {}
    for s in syms:
        m = np.array([r["SYMBOL"] == s for r in rows])
        by_symbol[s] = {"N": int(m.sum()), "MEAN_STATE": float(y[m & st].mean()) if (m & st).any() else None,
                        "MEAN_COMPARATOR": float(y[m & ~st].mean()) if (m & ~st).any() else None}
    btc_only = None
    btc = [r for r in rows if r["SYMBOL"] == "BTC"]
    if btc and len(syms) > 1:
        Xb, _, _ = FT.design_matrix(btc, h)
        yb = np.array([r["Y"] for r in btc], dtype=float)
        bx, by_, _ = S.aggregates(Xb, yb, S.cluster_ids(btc))
        bd = S.bootstrap_beta(bx, by_, K1.BOOT_DRAWS, rng)
        btc_only = {"N": len(btc), "ADJUSTED_SHIFT": float(S.solve(bx.sum(0), by_.sum(0))[S.S_COL]),
                    "CI95": [float(np.nanpercentile(bd, 2.5)), float(np.nanpercentile(bd, 97.5))], "ROLE": "descriptive"}
    return {
        "ENDPOINT": h["ENDPOINT"], "BAR": K.bar_of(h), "N": int(y.size), "N_STATE": int(st.sum()),
        "N_COMPARATOR": int((~st).sum()), "WEEK_CLUSTERS": int(cid.max()) + 1,
        "MEAN_STATE": float(y[st].mean()) if st.any() else None, "MEAN_COMPARATOR": float(y[~st].mean()) if (~st).any() else None,
        "ADJUSTED_SHIFT": shift, "CI95": [float(np.nanpercentile(draws, 2.5)), float(np.nanpercentile(draws, 97.5))],
        "P_BOOT": S.boot_p(draws), "SKILL": sk, "SKILL_KIND": "BRIER" if clip else "MSE",
        "HETEROGENEITY": het, "HETEROGENEITY_SYMBOL": het_sym, "BY_SYMBOL": by_symbol, "BTC_ONLY": btc_only,
        "MODEL": {"LABELS": labels, "LEVELS": {k: list(v) for k, v in levels.items()},
                  "BETA_FULL": beta_full.tolist(), "BETA_NULL": beta_null.tolist()},
    }


def classify_discovery(c: dict, p_holm: float, dec: dict) -> str:
    bar = c["BAR"]
    stat, big = p_holm < K1.FAMILY_ALPHA, abs(c["ADJUSTED_SHIFT"]) >= bar
    skilled = c["SKILL"] is not None and c["SKILL"] > 0
    if stat and big and skilled:
        if dec["HET_EPOCH"] == "ASSESSABLE" and c["HETEROGENEITY"]["STATUS"] == "FAIL_HETEROGENEOUS_UNEXPLAINED":
            return "HETEROGENEOUS_UNEXPLAINED"
        if dec["HET_SYMBOL"] == "ASSESSABLE" and c["HETEROGENEITY_SYMBOL"].get("STATUS") == "FAIL_HETEROGENEOUS_UNEXPLAINED":
            return "HETEROGENEOUS_UNEXPLAINED"
        return "PROMISING_PROTOTYPE"
    lo, hi = c["CI95"]
    if -bar < lo and hi < bar:
        return "NO_INCREMENTAL_STRUCTURE"
    if stat and (not big or not skilled):
        return "NO_INCREMENTAL_STRUCTURE"
    return "INCONCLUSIVE"


def classify_replication(c: dict, p_holm: float, disc_shift: float, powered: bool) -> str:
    bar = c["BAR"]
    same = np.sign(c["ADJUSTED_SHIFT"]) == np.sign(disc_shift)
    stat, big = p_holm < K1.FAMILY_ALPHA, abs(c["ADJUSTED_SHIFT"]) >= bar
    skilled = c["SKILL"] is not None and c["SKILL"] > 0
    if same and stat and big and skilled:
        return "SUPPORTED_UNCONDITIONAL"
    if stat and not same:
        return "REPLICATION_FAILED"
    if not powered and not stat:
        return "REPLICATION_INCONCLUSIVE"
    return "REPLICATION_FAILED"


def run(surface: str) -> dict:
    prereg = verify(surface)
    feas = json.loads(F.OUT_JSON.read_text())
    out = {"PROGRAM_ID": K.PROGRAM_ID, "SURFACE": surface, "PREREG_SHA256": hashlib.sha256(PREREG.read_bytes()).hexdigest(),
           "CODE_DIGESTS": code_digests(), "ONE_SHOT": True, "CELLS": {}}
    if surface == "DISCOVERY":
        cells = [h for h in K.HYPOTHESES if prereg["CELLS"][h["ID"]]["EXECUTE"]]
        disc, models = None, {}
    else:
        disc = json.loads(RESULT["DISCOVERY"].read_text())
        cells = [h for h in K.HYPOTHESES if h["CARD"] in K.REPLICATION
                 and disc["CELLS"].get(h["ID"], {}).get("CLASS") == "PROMISING_PROTOTYPE"]
        models = {h["ID"]: disc["CELLS"][h["ID"]]["MODEL"] for h in cells}
    if not cells:
        out["NOTE"] = "no cell to evaluate on this surface; no outcome was read"
        RESULT[surface].write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
        return out
    res = {}
    for card in K.CARDS:
        card_cells = [h for h in cells if h["CARD"] == card]
        if not card_cells:
            continue
        built = FT.card_v("REPLICATION") if surface == "REPLICATION" else FT.BUILDERS[card]()
        for h in card_cells:
            rows = FT.cell_rows(built["ROWS"][h["ID"]], h)
            rows_y = O.attach(built["BARS"], rows)
            seed = K.BOOT_SEED + 101 * K.HYPOTHESES.index(h) + (0 if surface == "DISCOVERY" else 7)
            res[h["ID"]] = evaluate_cell(rows_y, h, seed, models.get(h["ID"]))
            res[h["ID"]]["MISSING_OUTCOME_DROPPED"] = len(rows) - len(rows_y)
    for card in K.CARDS:
        fam = {hid: res[hid]["P_BOOT"] for hid in res if K.HYPOTHESIS_BY_ID[hid]["CARD"] == card}
        for hid, p in S.holm(fam).items():
            res[hid]["P_HOLM"], res[hid]["HOLM_FAMILY"] = p, sorted(fam)
    for hid, c in res.items():
        dec = feas["CELLS"][hid]["DECISION"]
        if surface == "DISCOVERY":
            c["CLASS"] = classify_discovery(c, c["P_HOLM"], {"HET_EPOCH": dec["HET_EPOCH_DISCOVERY"],
                                                            "HET_SYMBOL": dec["HET_SYMBOL_DISCOVERY"]})
        else:
            c["CLASS"] = classify_replication(c, c["P_HOLM"], disc["CELLS"][hid]["ADJUSTED_SHIFT"],
                                              dec["REPLICATION_POWERED"])
        c["BOT_STATUS"] = DISPLAY.get(c["CLASS"])
        out["CELLS"][hid] = c
    RESULT[surface].write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--surface", choices=("DISCOVERY", "REPLICATION"), required=True)
    result = run(ap.parse_args().surface)
    for hid, c in result["CELLS"].items():
        print(hid, c["CLASS"], round(c["ADJUSTED_SHIFT"], 4), round(c["P_HOLM"], 4), c["SKILL"])
