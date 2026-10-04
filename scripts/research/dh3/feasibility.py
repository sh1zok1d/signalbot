"""DH3 outcome-blind feasibility: per cell, events and arms by year and coin, planning MDE against
the cell's own bar, heterogeneity power. Never imports an outcome module.

Planning outcome variance: 0.25 for directional endpoints; for RANGE_4H, the variance of the lagged
target (prior 4h log range, known at T) over the cell's rows.

python -m scripts.research.dh3.feasibility
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np

from scripts.research.dh1 import constants as K1
from scripts.research.dh1 import stats as S
from scripts.research.dh2 import feasibility as F2

from . import constants as K
from . import data as D
from . import features as FT

REPO = Path(__file__).resolve().parents[3]
OUT_JSON = REPO / "docs/research/DH3_FEASIBILITY.json"
OUT_MD = REPO / "docs/research/DH3_FEASIBILITY.md"


def _het_power(X: np.ndarray, cid: np.ndarray, labels: list, names: list, seed: int, *, gauss_sd: float | None,
               effects: tuple) -> float:
    """Outcome-blind power of the frozen heterogeneity test (dh1.stats.het_test) when half of the groups
    have effect effects[0] and half effects[1]: Bernoulli outcomes around 0.5 (directional) or Gaussian
    noise with the planning SD (range). The per-cluster X'X is fixed, so it is built once."""
    import scipy.sparse as sp
    rng = np.random.default_rng(seed)
    grp = np.asarray(labels)[cid]
    eff = {g: effects[k % 2] for k, g in enumerate(names)}
    e = np.array([eff.get(g, 0.0) for g in grp])
    C = int(cid.max()) + 1
    k = X.shape[1]
    xtx = np.zeros((C, k, k))
    np.add.at(xtx, cid, X[:, :, None] * X[:, None, :])
    arms = np.zeros((C, 2))
    np.add.at(arms, (cid, X[:, S.S_COL].astype(int)), 1.0)
    M = sp.csr_matrix((np.ones(cid.size), (cid, np.arange(cid.size))), shape=(C, cid.size))
    rej = 0
    for _ in range(K1.HET_POWER_SIMS):
        if gauss_sd is None:
            y = (rng.random(X.shape[0]) < 0.5 + e * (X[:, S.S_COL] - 0.5)).astype(float)
        else:
            y = e * X[:, S.S_COL] + rng.normal(0.0, gauss_sd, X.shape[0])
        xty = np.asarray(M @ (X * y[:, None]))
        pooled = float(S.solve(xtx.sum(0), xty.sum(0))[S.S_COL])
        res = S.het_test(xtx, xty, arms, labels, names, pooled, rng, se_draws=100, perms=K1.HET_POWER_PERMS)
        rej += res.get("P_HET", 1.0) < K1.HET_ALPHA
    return rej / K1.HET_POWER_SIMS


def plan(rows: list, h: dict, seed: int) -> dict:
    if len(rows) < 10:
        return {"N": len(rows)}
    X, labels, _ = FT.design_matrix(rows, h)
    st = X[:, S.S_COL]
    if st.min() == st.max():
        return {"N": len(rows), "N_STATE": int(st.sum()), "N_COMPARATOR": int((1 - st).sum()), "DEGENERATE": True}
    var = 0.25 if h["ENDPOINT"] != "RANGE_4H" else float(np.var([r["LAG"] for r in rows]))
    inv = np.linalg.pinv(X.T @ X)
    se = math.sqrt(var * inv[S.S_COL, S.S_COL] * K1.DEFF_PLANNING)
    alpha = K1.FAMILY_ALPHA / 3
    bar = K.bar_of(h)
    cid = S.cluster_ids(rows)
    c_epoch = S.cluster_epochs(rows, cid)
    epochs = sorted({r["EPOCH"] for r in rows}, key=K.epoch_rank)
    syms = sorted({r["SYMBOL"] for r in rows})
    by = lambda key, val: np.array([r[key] == val for r in rows])  # noqa: E731
    per_epoch = {e: {"N_STATE": int(st[by("EPOCH", e)].sum()), "N_COMPARATOR": int((1 - st[by("EPOCH", e)]).sum())} for e in epochs}
    per_symbol = {s: {"N_STATE": int(st[by("SYMBOL", s)].sum()), "N_COMPARATOR": int((1 - st[by("SYMBOL", s)]).sum())} for s in syms}
    scid, slabels = F2.symbol_clusters(rows)
    sd = math.sqrt(var) if h["ENDPOINT"] == "RANGE_4H" else None
    effects = (bar, 2 * bar) if sd is not None else K1.HET_POWER_EFFECTS
    het_e = _het_power(X, cid, c_epoch, epochs, seed, gauss_sd=sd, effects=effects) if len(epochs) >= 3 else 0.0
    het_s = _het_power(X, scid, slabels, syms, seed + 1, gauss_sd=sd, effects=effects) if len(syms) >= 3 else 0.0
    return {
        "N": len(rows), "N_STATE": int(st.sum()), "N_COMPARATOR": int((1 - st).sum()), "STATE_SHARE": float(st.mean()),
        "WEEK_CLUSTERS": int(cid.max()) + 1, "OUTCOME_VAR_PLANNING": var, "PLANNING_SE": se, "BAR": bar,
        "MDE_80": S.mde(se, alpha), "POWER_AT_BAR": S.power_at(bar, se, alpha), "ALPHA_HOLM_FIRST_STEP": alpha,
        "EPOCHS": per_epoch, "SYMBOLS": per_symbol,
        "EPOCHS_WITH_BOTH_ARMS_GE_MIN": sum(1 for v in per_epoch.values() if min(v.values()) >= K1.MIN_EPOCH_ARM),
        "HET_POWER_EPOCH_2X": het_e, "HET_POWER_SYMBOL_2X": het_s, "DESIGN_COLUMNS": labels,
    }


def decide(h: dict, disc: dict, rep: dict | None) -> dict:
    reasons = []
    if disc.get("DEGENERATE"):
        reasons.append("state degenerate (one arm empty)")
    elif disc["N"] < 10:
        reasons.append("no events")
    else:
        if disc["MDE_80"] > K.EXECUTE_MDE_FACTOR * disc["BAR"]:
            reasons.append(f"discovery MDE {disc['MDE_80']:.4f} > {K.EXECUTE_MDE_FACTOR} x bar {disc['BAR']:.4f}")
        if min(disc["N_STATE"], disc["N_COMPARATOR"]) < K1.EXECUTE_MIN_ARM:
            reasons.append(f"smaller arm {min(disc['N_STATE'], disc['N_COMPARATOR'])} < {K1.EXECUTE_MIN_ARM}")
        if disc["EPOCHS_WITH_BOTH_ARMS_GE_MIN"] < 3:
            reasons.append("fewer than 3 years with both arms >= 30")
    rep_ok = bool(rep and rep.get("MDE_80") is not None and rep["MDE_80"] <= K.EXECUTE_MDE_FACTOR * rep["BAR"]
                  and min(rep["N_STATE"], rep["N_COMPARATOR"]) >= K1.EXECUTE_MIN_ARM)
    he, hs = disc.get("HET_POWER_EPOCH_2X"), disc.get("HET_POWER_SYMBOL_2X")
    return {"EXECUTE": not reasons, "STATUS": "EXECUTABLE" if not reasons else "INFORMATIONALLY_WEAK", "REASONS": reasons,
            "REPLICATION_SURFACE": K.REPLICATION.get(h["CARD"], "PROSPECTIVE_ONLY"), "REPLICATION_POWERED": rep_ok,
            "HET_EPOCH_DISCOVERY": "ASSESSABLE" if (he is not None and he >= 0.5) else "NOT_ASSESSABLE",
            "HET_SYMBOL_DISCOVERY": "ASSESSABLE" if (hs is not None and hs >= 0.5) else "NOT_ASSESSABLE"}


def run() -> dict:
    K.assert_locked()
    out = {"PROGRAM_ID": K.PROGRAM_ID, "SEARCH_FAMILY_ID": K.SEARCH_FAMILY_ID, "MARKET_OUTCOMES_OPENED": False,
           "MARKET_VALUES_READ": "prices, OI metrics, book depth, DVOL and trade features up to each decision time; no outcome",
           "OBJECTS_2025_2026_USED": "none", "DATASETS": D.dataset_identity(), "CELLS": {}}
    rep_rows = FT.card_v("REPLICATION")["ROWS"]
    for card, builder in FT.BUILDERS.items():
        built = builder()
        for h in [x for x in K.HYPOTHESES if x["CARD"] == card]:
            k = K.HYPOTHESES.index(h)
            disc = plan(FT.cell_rows(built["ROWS"][h["ID"]], h), h, K.BOOT_SEED + 13 * k)
            rep = plan(FT.cell_rows(rep_rows[h["ID"]], h), h, K.BOOT_SEED + 13 * k + 5) if card in K.REPLICATION else None
            out["CELLS"][h["ID"]] = {"CARD": card, "STATE": h["STATE"], "ENDPOINT": h["ENDPOINT"], "DISCOVERY": disc,
                                     "REPLICATION": rep, "DECISION": decide(h, disc, rep)}
            print("planned", h["ID"], out["CELLS"][h["ID"]]["DECISION"]["STATUS"], flush=True)
    OUT_JSON.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    OUT_MD.write_text(markdown(out))
    return out


def markdown(out: dict) -> str:
    lines = ["# DH3 — outcome-blind feasibility (five cards of three)", "",
             "**Program:** `DIRECTIONAL_AND_RANGE_DH3` · written before any outcome · machine record `DH3_FEASIBILITY.json`", "",
             "Rule frozen before counting: a cell runs if its discovery MDE at 80 % power (Holm first-step alpha 0.05/3) is at "
             "most twice its bar (range: 2 x log 1.15; direction: 6 pp), the smaller arm has at least 300 events and at least "
             "three years have both arms of 30 or more.", "",
             "| Cell | Endpoint | N | state / comparator | MDE80 | bar | power at bar | status | reasons |",
             "|---|---|---|---|---|---|---|---|---|"]
    for hid, c in out["CELLS"].items():
        p, d = c["DISCOVERY"], c["DECISION"]
        mde = f"{p['MDE_80']:.4f}" if p.get("MDE_80") is not None else "—"
        pw = f"{p['POWER_AT_BAR']:.2f}" if p.get("POWER_AT_BAR") is not None else "—"
        lines.append(f"| {hid} | {c['ENDPOINT']} | {p['N']} | {p.get('N_STATE', '—')} / {p.get('N_COMPARATOR', '—')} | {mde} | "
                     f"{p.get('BAR', K.bar_of(K.HYPOTHESIS_BY_ID[hid])):.4f} | {pw} | `{d['STATUS']}` | {'; '.join(d['REASONS']) or '—'} |")
    lines.append("")
    return "\n".join(lines)


def digest() -> str:
    return hashlib.sha256(OUT_JSON.read_bytes()).hexdigest()


if __name__ == "__main__":
    res = run()
    for hid, c in res["CELLS"].items():
        print(hid, c["DECISION"]["STATUS"], c["DISCOVERY"].get("MDE_80"), c["DISCOVERY"].get("N"), c["DECISION"]["REASONS"])
