"""DH2 outcome-blind feasibility: pooled events, arms by year and coin, planning power, epoch and
coin heterogeneity power. Never imports an outcome module.

python -m scripts.research.dh2.feasibility
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from scripts.research.dh1 import constants as K1
from scripts.research.dh1 import stats as S

from . import constants as K
from . import data as D
from . import events as E

REPO = Path(__file__).resolve().parents[3]
OUT_JSON = REPO / "docs/research/DH2_FEASIBILITY.json"
OUT_MD = REPO / "docs/research/DH2_FEASIBILITY.md"


def symbol_clusters(rows: list) -> tuple:
    keys = [(r["WEEK"], r["EPOCH"], r["SYMBOL"]) for r in rows]
    uniq = {k: n for n, k in enumerate(sorted(set(keys), key=str))}
    cid = np.array([uniq[k] for k in keys], dtype=np.int64)
    labels = [None] * len(uniq)
    for k, n in uniq.items():
        labels[n] = k[2]
    return cid, labels


def discovery_events() -> dict:
    lev, mov = [], []
    end = K._ms(K.DISCOVERY_END)
    for sym in K.SYMBOLS:
        bars, spot = D.discovery(sym)
        start = K._ms(K.DISCOVERY[sym][1])
        lev += E.level_events(bars, spot, sym, start, end, K.DISCOVERY_EPOCHS)
        mov += E.move_events(bars, spot, sym, start, end, K.DISCOVERY_EPOCHS)
    return {"DH2-L": lev, "DH2-B": mov}


def replication_events() -> dict:
    """Per cell: DH2-L3 on spot prices of four coins; DH2-L1 and DH2-B2 on the DH1 BTC surface."""
    end = K._ms(K.REPLICATION_END)
    spot_lev = []
    for sym in K.REPLICATION_SPOT:
        bars = D.replication_spot(sym)
        spot_lev += E.level_events(bars, None, sym, K._ms(K.REPLICATION_SPOT[sym][1]), end, K.REPLICATION_EPOCHS)
    bars, spot = D.replication_btc()
    start = K._ms("2017-09-01")
    btc_lev = E.level_events(bars, spot, "BTC", start, end, K.REPLICATION_EPOCHS)
    btc_mov = E.move_events(bars, spot, "BTC", start, end, K.REPLICATION_EPOCHS)
    return {"DH2-L1": btc_lev, "DH2-L3": spot_lev, "DH2-B2": btc_mov}


def plan(rows: list, h: dict, epochs: list, seed: int) -> dict:
    if not rows:
        return {"N": 0}
    X, labels, levels = E.design_matrix(rows, h)
    cid = S.cluster_ids(rows)
    c_epoch = S.cluster_epochs(rows, cid)
    m = sum(1 for x in K.HYPOTHESES if x["CARD"] == h["CARD"])
    alpha = K1.FAMILY_ALPHA / m
    se = S.planning_se(X)
    st = X[:, S.S_COL]
    syms = sorted({r["SYMBOL"] for r in rows})
    by = lambda key, val: np.array([r[key] == val for r in rows])  # noqa: E731
    per_epoch = {e: {"N_STATE": int(st[by("EPOCH", e)].sum()), "N_COMPARATOR": int((1 - st[by("EPOCH", e)]).sum())}
                 for e, _, _ in epochs}
    per_symbol = {s: {"N_STATE": int(st[by("SYMBOL", s)].sum()), "N_COMPARATOR": int((1 - st[by("SYMBOL", s)]).sum())}
                  for s in syms}
    scid, slabels = symbol_clusters(rows)
    out = {
        "N": len(rows), "N_STATE": int(st.sum()), "N_COMPARATOR": int((1 - st).sum()), "STATE_SHARE": float(st.mean()),
        "WEEK_CLUSTERS": int(cid.max()) + 1, "ALPHA_HOLM_FIRST_STEP": alpha, "PLANNING_SE": se,
        "MDE_80": S.mde(se, alpha), "POWER_AT_BAR": S.power_at(K1.PRACTICAL_BAR, se, alpha),
        "POWER_AT_50PCT_PLANNING": S.power_at(0.5 * K1.PLANNING_EFFECT, se, alpha),
        "POWER_AT_75PCT_PLANNING": S.power_at(0.75 * K1.PLANNING_EFFECT, se, alpha),
        "EPOCHS": per_epoch, "SYMBOLS": per_symbol,
        "EPOCHS_WITH_BOTH_ARMS_GE_MIN": sum(1 for v in per_epoch.values()
                                            if min(v["N_STATE"], v["N_COMPARATOR"]) >= K1.MIN_EPOCH_ARM),
        "SYMBOLS_WITH_BOTH_ARMS_GE_MIN": sum(1 for v in per_symbol.values()
                                             if min(v["N_STATE"], v["N_COMPARATOR"]) >= K1.MIN_EPOCH_ARM),
        "HET_POWER_EPOCH_2X": S.het_power(X, cid, c_epoch, [e for e, _, _ in epochs], seed),
        "HET_POWER_SYMBOL_2X": (S.het_power(X, scid, slabels, syms, seed + 1) if len(syms) >= K.SYMBOL_HET_MIN_SYMBOLS
                                else 0.0),
        "DESIGN_COLUMNS": labels,
    }
    btc = [r for r in rows if r["SYMBOL"] == "BTC"]
    if btc and len(syms) > 1:
        Xb, _, _ = E.design_matrix(btc, h)
        out["BTC_ONLY_MDE_80"] = S.mde(S.planning_se(Xb), alpha)
    return out


def decide(disc: dict, rep: dict) -> dict:
    reasons = []
    if disc["MDE_80"] > K1.EXECUTE_MDE_MAX:
        reasons.append(f"discovery MDE {disc['MDE_80']:.4f} > {K1.EXECUTE_MDE_MAX}")
    if min(disc["N_STATE"], disc["N_COMPARATOR"]) < K1.EXECUTE_MIN_ARM:
        reasons.append(f"smaller arm {min(disc['N_STATE'], disc['N_COMPARATOR'])} < {K1.EXECUTE_MIN_ARM}")
    if disc["EPOCHS_WITH_BOTH_ARMS_GE_MIN"] < 3:
        reasons.append("fewer than 3 discovery years with both arms >= 30")
    rep_ok = rep.get("N", 0) > 0 and rep["MDE_80"] <= K1.EXECUTE_MDE_MAX \
        and min(rep["N_STATE"], rep["N_COMPARATOR"]) >= K1.EXECUTE_MIN_ARM
    return {"EXECUTE": not reasons, "STATUS": "EXECUTABLE" if not reasons else "INFORMATIONALLY_WEAK", "REASONS": reasons,
            "REPLICATION_POWERED": bool(rep_ok),
            "HET_EPOCH_DISCOVERY": "ASSESSABLE" if disc["HET_POWER_EPOCH_2X"] >= 0.5 else "NOT_ASSESSABLE",
            "HET_SYMBOL_DISCOVERY": "ASSESSABLE" if disc["HET_POWER_SYMBOL_2X"] >= 0.5 else "NOT_ASSESSABLE",
            "HET_EPOCH_REPLICATION": ("ASSESSABLE" if rep.get("HET_POWER_EPOCH_2X", 0) >= 0.5 else "NOT_ASSESSABLE"),
            "HET_SYMBOL_REPLICATION": ("ASSESSABLE" if rep.get("HET_POWER_SYMBOL_2X", 0) >= 0.5 else "NOT_ASSESSABLE")}


def run() -> dict:
    K.assert_locked()
    disc_ev, rep_ev = discovery_events(), replication_events()
    out = {"PROGRAM_ID": K.PROGRAM_ID, "SEARCH_FAMILY_ID": K.SEARCH_FAMILY_ID, "MARKET_OUTCOMES_OPENED": False,
           "MARKET_VALUES_READ": "prices and taker flows up to each decision time (states and nuisance only); no outcome",
           "OBJECTS_2025_2026_USED": "none", "DATASETS": D.dataset_identity(),
           "EVENTS": {"DISCOVERY": {card: {s: sum(1 for e in ev if e["SYMBOL"] == s) for s in K.SYMBOLS}
                                    for card, ev in disc_ev.items()},
                      "REPLICATION": {cid_: {s: sum(1 for e in ev if e["SYMBOL"] == s) for s in K.SYMBOLS}
                                      for cid_, ev in rep_ev.items()}},
           "CELLS": {}}
    for k, h in enumerate(K.HYPOTHESES):
        disc = plan(E.cell_rows(disc_ev[h["CARD"]], h), h, K.DISCOVERY_EPOCHS, K.SYMBOL_HET_SEED + 10 * k)
        rep = plan(E.cell_rows(rep_ev[h["ID"]], h), h, K.REPLICATION_EPOCHS, K.SYMBOL_HET_SEED + 10 * k + 5)
        out["CELLS"][h["ID"]] = {"CARD": h["CARD"], "STATE": h["STATE"], "DISCOVERY": disc, "REPLICATION": rep,
                                 "DECISION": decide(disc, rep)}
    OUT_JSON.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    OUT_MD.write_text(markdown(out))
    return out


def markdown(out: dict) -> str:
    lines = ["# DH2 — outcome-blind feasibility (six coins pooled)", "",
             "**Program:** `DIRECTIONAL_HYPOTHESES_DH2` · **written before any outcome** · machine record `DH2_FEASIBILITY.json`", "",
             "States and nuisance terms were built from prices and flows known at each decision time; no outcome was "
             "computed. Rule as DH1: a cell runs if its discovery MDE at 80 % power (Holm first-step alpha) is at most "
             f"{K1.EXECUTE_MDE_MAX}, the smaller arm has at least {K1.EXECUTE_MIN_ARM} events and at least three years "
             "have both arms of 30 or more.", "", "## Events by coin", "",
             "| Surface / card | " + " | ".join(K.SYMBOLS) + " |", "|---|" + "---|" * len(K.SYMBOLS)]
    for surf, cards in out["EVENTS"].items():
        for card, counts in cards.items():
            lines.append(f"| {surf} {card} | " + " | ".join(str(counts[s]) for s in K.SYMBOLS) + " |")
    lines += ["", "## Cells", "",
              "| Cell | Surface | N | state / comparator | MDE80 | power at 3 pp | BTC-only MDE | epoch het power | coin het power |",
              "|---|---|---|---|---|---|---|---|---|"]
    for cid_, c in out["CELLS"].items():
        for s in ("DISCOVERY", "REPLICATION"):
            p = c[s]
            if not p.get("N"):
                lines.append(f"| {cid_} | {s} | 0 | — | — | — | — | — | — |")
                continue
            btc = p.get("BTC_ONLY_MDE_80")
            lines.append(f"| {cid_} | {s} | {p['N']} | {p['N_STATE']} / {p['N_COMPARATOR']} | {p['MDE_80']:.4f} | "
                         f"{p['POWER_AT_BAR']:.2f} | {'—' if btc is None else f'{btc:.4f}'} | {p['HET_POWER_EPOCH_2X']:.2f} | "
                         f"{p['HET_POWER_SYMBOL_2X']:.2f} |")
    lines += ["", "## Decisions", "", "| Cell | Status | Replication powered | Reasons |", "|---|---|---|---|"]
    for cid_, c in out["CELLS"].items():
        d = c["DECISION"]
        lines.append(f"| {cid_} | `{d['STATUS']}` | {'yes' if d['REPLICATION_POWERED'] else 'no (live tracking decides)'} | "
                     f"{'; '.join(d['REASONS']) or '—'} |")
    lines.append("")
    return "\n".join(lines)


def digest() -> str:
    return hashlib.sha256(OUT_JSON.read_bytes()).hexdigest()


if __name__ == "__main__":
    res = run()
    for k, v in res["CELLS"].items():
        print(k, v["DECISION"]["STATUS"], round(v["DISCOVERY"]["MDE_80"], 4), v["REPLICATION"].get("MDE_80"))
