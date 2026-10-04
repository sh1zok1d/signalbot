"""DH2 one-shot evaluator (contract V1 gates plus the frozen coin-heterogeneity gate).

python -m scripts.research.dh2.evaluate --surface DISCOVERY
python -m scripts.research.dh2.evaluate --surface REPLICATION

It refuses to run unless `DH2_PREREG.json` is committed and every bound code, data and
feasibility digest matches, refuses a second run of a surface, and replicates only the cells that
discovery classified `PROMISING_PROTOTYPE`, with the frozen discovery models.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from scripts.research.dh1 import constants as K1
from scripts.research.dh1 import evaluate as V1
from scripts.research.dh1 import outcomes as O
from scripts.research.dh1 import stats as S

from . import constants as K
from . import data as D
from . import events as E
from . import feasibility as F

REPO = Path(__file__).resolve().parents[3]
PREREG = REPO / "docs/research/DH2_PREREG.json"
RESULT = {"DISCOVERY": REPO / "docs/research/DH2_RESULT_DISCOVERY.json",
          "REPLICATION": REPO / "docs/research/DH2_RESULT_REPLICATION.json"}
BOUND_FILES = ["scripts/research/dh2/constants.py", "scripts/research/dh2/data.py", "scripts/research/dh2/events.py",
               "scripts/research/dh2/feasibility.py", "scripts/research/dh2/evaluate.py",
               "scripts/research/dh1/constants.py", "scripts/research/dh1/data.py", "scripts/research/dh1/events.py",
               "scripts/research/dh1/outcomes.py", "scripts/research/dh1/stats.py", "scripts/research/dh1/evaluate.py",
               "beta/levels.py", "beta/hist_series.py", "scripts/research/owner_cards_r03/data.py"]


def code_digests() -> dict:
    return {p: hashlib.sha256((REPO / p).read_bytes()).hexdigest() for p in BOUND_FILES}


def verify(surface: str) -> dict:
    if not PREREG.exists():
        raise RuntimeError("DH2: no preregistration; nothing may be evaluated")
    prereg = json.loads(PREREG.read_text())
    if prereg["CODE_DIGESTS"] != code_digests():
        raise RuntimeError("DH2: bound code drifted from the preregistration")
    if prereg["DATASETS"] != D.dataset_identity():
        raise RuntimeError("DH2: dataset identity drifted from the preregistration")
    if prereg["FEASIBILITY_SHA256"] != F.digest():
        raise RuntimeError("DH2: feasibility record drifted from the preregistration")
    if not V1._committed_clean(["docs/research/DH2_PREREG.json", "docs/research/DH2_FEASIBILITY.json", *BOUND_FILES]):
        raise RuntimeError("DH2: preregistration and bound files must be committed and clean")
    if RESULT[surface].exists():
        raise RuntimeError(f"DH2: {surface} was already evaluated (one-shot)")
    if surface == "REPLICATION" and (not RESULT["DISCOVERY"].exists()
                                     or not V1._committed_clean(["docs/research/DH2_RESULT_DISCOVERY.json"])):
        raise RuntimeError("DH2: replication needs the committed discovery result")
    return prereg


def attach(bars_by_symbol: dict, rows: list, card: str) -> list:
    out = []
    for r in rows:
        b = bars_by_symbol[r["SYMBOL"]]
        y = O.level_hold(b, r["J"], r["LEVEL"], r["SIDE"]) if card == "DH2-L" else O.barrier(b, r["J"], r["DIR"], r["X"])
        if y is not None:
            out.append({**r, "Y": y})
    return out


def evaluate_cell(rows: list, h: dict, epochs: list, seed: int, model: dict | None = None) -> dict:
    levels = None if model is None else model["LEVELS"]
    X, labels, levels = E.design_matrix(rows, h, levels)
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
        bss = S.crossfit_bss(X, y, [r["EPOCH"] for r in rows])
    else:
        bf = S.brier(X @ np.array(model["BETA_FULL"]), y)
        bn = S.brier(X[:, keep] @ np.array(model["BETA_NULL"]), y)
        bss = None if bn <= 0 else 1.0 - bf / bn
    het = S.het_test(xtx, xty, arms, c_epoch, [e for e, _, _ in epochs], shift, rng)
    syms = sorted({r["SYMBOL"] for r in rows})
    if len(syms) >= K.SYMBOL_HET_MIN_SYMBOLS:
        scid, slabels = F.symbol_clusters(rows)
        sx, sy, sa = S.aggregates(X, y, scid)
        het_sym = S.het_test(sx, sy, sa, slabels, syms, shift, rng)
    else:
        het_sym = {"STATUS": "NOT_ASSESSABLE", "REASON": "fewer than 3 coins"}
    st = X[:, S.S_COL] == 1
    by_symbol = {}
    for s in syms:
        m = np.array([r["SYMBOL"] == s for r in rows])
        by_symbol[s] = {"N": int(m.sum()), "RATE_STATE": float(y[m & st].mean()) if (m & st).any() else None,
                        "RATE_COMPARATOR": float(y[m & ~st].mean()) if (m & ~st).any() else None}
    btc = [r for r in rows if r["SYMBOL"] == "BTC"]
    btc_only = None
    if btc and len(syms) > 1:
        Xb, _, _ = E.design_matrix(btc, h)
        yb = np.array([r["Y"] for r in btc], dtype=float)
        cb = S.cluster_ids(btc)
        bx, by_, _ = S.aggregates(Xb, yb, cb)
        bd = S.bootstrap_beta(bx, by_, K1.BOOT_DRAWS, rng)
        btc_only = {"N": len(btc), "ADJUSTED_SHIFT": float(S.solve(bx.sum(0), by_.sum(0))[S.S_COL]),
                    "CI95": [float(np.nanpercentile(bd, 2.5)), float(np.nanpercentile(bd, 97.5))], "P_BOOT": S.boot_p(bd),
                    "ROLE": "descriptive; never gates"}
    return {
        "N": int(y.size), "N_STATE": int(st.sum()), "N_COMPARATOR": int((~st).sum()), "WEEK_CLUSTERS": int(cid.max()) + 1,
        "RATE_STATE": float(y[st].mean()) if st.any() else None, "RATE_COMPARATOR": float(y[~st].mean()) if (~st).any() else None,
        "RATE_ALL": float(y.mean()), "ADJUSTED_SHIFT": shift,
        "CI95": [float(np.nanpercentile(draws, 2.5)), float(np.nanpercentile(draws, 97.5))],
        "P_BOOT": S.boot_p(draws), "BRIER_SKILL": bss, "HETEROGENEITY": het, "HETEROGENEITY_SYMBOL": het_sym,
        "BY_SYMBOL": by_symbol, "BTC_ONLY": btc_only,
        "MODEL": {"LABELS": labels, "LEVELS": {k: list(v) for k, v in levels.items()},
                  "BETA_FULL": beta_full.tolist(), "BETA_NULL": beta_null.tolist()},
    }


def classify(c: dict, surface: str, p_holm: float, dec: dict, disc_shift: float | None = None) -> str:
    if surface == "DISCOVERY":
        cls = V1.classify_discovery(c, p_holm, dec["HET_EPOCH_DISCOVERY"] == "ASSESSABLE")
        sym_assess = dec["HET_SYMBOL_DISCOVERY"] == "ASSESSABLE"
    else:
        cls = V1.classify_replication(c, p_holm, disc_shift, dec["REPLICATION_POWERED"],
                                      dec["HET_EPOCH_REPLICATION"] == "ASSESSABLE")
        sym_assess = dec["HET_SYMBOL_REPLICATION"] == "ASSESSABLE"
    if cls in ("PROMISING_PROTOTYPE", "SUPPORTED_UNCONDITIONAL") and sym_assess \
            and c["HETEROGENEITY_SYMBOL"].get("STATUS") == "FAIL_HETEROGENEOUS_UNEXPLAINED":
        return "HETEROGENEOUS_UNEXPLAINED"
    return cls


def run(surface: str) -> dict:
    prereg = verify(surface)
    feas = json.loads(F.OUT_JSON.read_text())
    if surface == "DISCOVERY":
        cells = [h for h in K.HYPOTHESES if prereg["CELLS"][h["ID"]]["EXECUTE"]]
        models, disc = {}, None
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
    res = {}
    if surface == "DISCOVERY":
        bars, events = {}, {"DH2-L": [], "DH2-B": []}
        end = K._ms(K.DISCOVERY_END)
        for sym in K.SYMBOLS:
            b, spot = D.discovery(sym)
            bars[sym] = b
            start = K._ms(K.DISCOVERY[sym][1])
            events["DH2-L"] += E.level_events(b, spot, sym, start, end, K.DISCOVERY_EPOCHS)
            events["DH2-B"] += E.move_events(b, spot, sym, start, end, K.DISCOVERY_EPOCHS)
        for h in cells:
            rows = E.cell_rows(events[h["CARD"]], h)
            rows_y = attach(bars, rows, h["CARD"])
            res[h["ID"]] = evaluate_cell(rows_y, h, K.DISCOVERY_EPOCHS, K.BOOT_SEED + 101 * K.HYPOTHESES.index(h))
            res[h["ID"]]["MISSING_OUTCOME_DROPPED"] = len(rows) - len(rows_y)
    else:
        end = K._ms(K.REPLICATION_END)
        for h in cells:
            if h["REPLICATION"] == "SPOT_4_COINS":
                bars, ev = {}, []
                for sym in K.REPLICATION_SPOT:
                    b = D.replication_spot(sym)
                    bars[sym] = b
                    ev += E.level_events(b, None, sym, K._ms(K.REPLICATION_SPOT[sym][1]), end, K.REPLICATION_EPOCHS)
            else:
                b, spot = D.replication_btc()
                bars = {"BTC": b}
                fn = E.level_events if h["CARD"] == "DH2-L" else E.move_events
                ev = fn(b, spot, "BTC", K._ms("2017-09-01"), end, K.REPLICATION_EPOCHS)
            rows = E.cell_rows(ev, h)
            rows_y = attach(bars, rows, h["CARD"])
            res[h["ID"]] = evaluate_cell(rows_y, h, K.REPLICATION_EPOCHS, K.BOOT_SEED + 101 * K.HYPOTHESES.index(h) + 7,
                                         models[h["ID"]])
            res[h["ID"]]["MISSING_OUTCOME_DROPPED"] = len(rows) - len(rows_y)
    for card in K.CARDS:
        fam = {hid: res[hid]["P_BOOT"] for hid in res if K.HYPOTHESIS_BY_ID[hid]["CARD"] == card}
        for hid, p in S.holm(fam).items():
            res[hid]["P_HOLM"], res[hid]["HOLM_FAMILY"] = p, sorted(fam)
    for hid, c in res.items():
        dec = feas["CELLS"][hid]["DECISION"]
        c["CLASS"] = classify(c, surface, c["P_HOLM"], dec,
                              None if disc is None else disc["CELLS"][hid]["ADJUSTED_SHIFT"])
        c["BOT_STATUS"] = V1.DISPLAY.get(c["CLASS"])
        out["CELLS"][hid] = c
    RESULT[surface].write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--surface", choices=("DISCOVERY", "REPLICATION"), required=True)
    result = run(ap.parse_args().surface)
    for hid, c in result["CELLS"].items():
        print(hid, c["CLASS"], round(c["ADJUSTED_SHIFT"], 4), round(c["P_HOLM"], 4), c["BRIER_SKILL"])
