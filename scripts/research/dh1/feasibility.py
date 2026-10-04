"""DH1 outcome-blind feasibility: event counts, arms, epochs, nuisance support and planning power.

Reads prices and flows to build events and states (as-of the decision time) but never an outcome:
this module does not import `outcomes.py`. Run: python -m scripts.research.dh1.feasibility
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from . import constants as K
from . import data as D
from . import events as E
from . import stats as S

REPO = Path(__file__).resolve().parents[3]
OUT_JSON = REPO / "docs/research/DH1_FEASIBILITY.json"
OUT_MD = REPO / "docs/research/DH1_FEASIBILITY.md"


def cards_cells(card: str) -> list:
    return [h for h in K.HYPOTHESES if h["CARD"] == card]


def cell_plan(rows: list, h: dict, surface: str, seed: int) -> dict:
    X, labels, levels = E.design_matrix(rows, h)
    cid = S.cluster_ids(rows)
    c_epoch = S.cluster_epochs(rows, cid)
    epochs = [e for e, _, _ in K.SURFACES[surface]["EPOCHS"]]
    m = len(cards_cells(h["CARD"]))
    alpha = K.FAMILY_ALPHA / m
    se = S.planning_se(X)
    st = X[:, S.S_COL]
    per_epoch = {}
    for e in epochs:
        mask = np.array([r["EPOCH"] == e for r in rows])
        per_epoch[e] = {"N_STATE": int(st[mask].sum()), "N_COMPARATOR": int((1 - st[mask]).sum())}
    support = {}
    for n in E.nuisance_names(h):
        cells = {}
        for lv in levels[n]:
            sel = np.array([r[n] == lv for r in rows])
            cells[str(lv)] = [int((1 - st[sel]).sum()), int(st[sel].sum())]
        support[n] = cells
    return {
        "N": len(rows), "N_STATE": int(st.sum()), "N_COMPARATOR": int((1 - st).sum()),
        "STATE_SHARE": float(st.mean()) if len(rows) else None,
        "CLUSTERS": int(cid.max()) + 1 if cid.size else 0,
        "EVENTS_PER_YEAR": len(rows) / (sum(K._ms(z) - K._ms(a) for _, a, z in K.SURFACES[surface]["EPOCHS"]) / (365.25 * K.DAY_MS)),
        "DESIGN_COLUMNS": labels, "ALPHA_HOLM_FIRST_STEP": alpha,
        "PLANNING_SE": se, "MDE_80": S.mde(se, alpha),
        "POWER_AT_50PCT_PLANNING": S.power_at(0.5 * K.PLANNING_EFFECT, se, alpha),
        "POWER_AT_75PCT_PLANNING": S.power_at(0.75 * K.PLANNING_EFFECT, se, alpha),
        "POWER_AT_BAR": S.power_at(K.PRACTICAL_BAR, se, alpha),
        "EPOCHS": per_epoch,
        "EPOCHS_WITH_BOTH_ARMS_GE_MIN": sum(1 for v in per_epoch.values()
                                            if v["N_STATE"] >= K.MIN_EPOCH_ARM and v["N_COMPARATOR"] >= K.MIN_EPOCH_ARM),
        "NUISANCE_SUPPORT_[COMPARATOR,STATE]": support,
        "HET_POWER_2X": S.het_power(X, cid, c_epoch, epochs, seed) if len(rows) else 0.0,
    }


def decide(disc: dict, rep: dict) -> dict:
    reasons = []
    if disc["MDE_80"] > K.EXECUTE_MDE_MAX:
        reasons.append(f"discovery MDE {disc['MDE_80']:.4f} > {K.EXECUTE_MDE_MAX}")
    if min(disc["N_STATE"], disc["N_COMPARATOR"]) < K.EXECUTE_MIN_ARM:
        reasons.append(f"smaller arm {min(disc['N_STATE'], disc['N_COMPARATOR'])} < {K.EXECUTE_MIN_ARM}")
    if disc["EPOCHS_WITH_BOTH_ARMS_GE_MIN"] < 3:
        reasons.append("fewer than 3 discovery epochs with both arms >= 30")
    return {
        "EXECUTE": not reasons, "STATUS": "EXECUTABLE" if not reasons else "INFORMATIONALLY_WEAK", "REASONS": reasons,
        "REPLICATION_POWERED": bool(rep["MDE_80"] <= K.EXECUTE_MDE_MAX and min(rep["N_STATE"], rep["N_COMPARATOR"]) >= K.EXECUTE_MIN_ARM),
        "HET_DISCOVERY": "ASSESSABLE" if disc["HET_POWER_2X"] >= 0.5 else "NOT_ASSESSABLE",
        "HET_REPLICATION": "ASSESSABLE" if rep["HET_POWER_2X"] >= 0.5 else "NOT_ASSESSABLE",
    }


def run() -> dict:
    K.assert_locked()
    out = {"PROGRAM_ID": K.PROGRAM_ID, "SEARCH_FAMILY_ID": K.SEARCH_FAMILY_ID, "DESIGN_DATE": K.DESIGN_DATE,
           "MARKET_OUTCOMES_OPENED": False,
           "MARKET_VALUES_READ": "prices and taker flows up to each decision time (states and nuisance only); no outcome",
           "OBJECTS_2025_2026_USED": "none", "DATASETS": D.dataset_identity(),
           "RULES": {"EXECUTE_MDE_MAX": K.EXECUTE_MDE_MAX, "EXECUTE_MIN_ARM": K.EXECUTE_MIN_ARM,
                     "PLANNING_EFFECT": K.PLANNING_EFFECT, "DEFF_PLANNING": K.DEFF_PLANNING,
                     "OUTCOME_VARIANCE": 0.25, "HET_POWER": "2x epoch difference (0.03 vs 0.06), >= 0.5 to be assessable"},
           "SURFACES": {}, "CELLS": {}}
    plans = {}
    for k, surface in enumerate(("DISCOVERY", "REPLICATION")):
        bars, spot = D.surface(surface)
        lev = E.level_events(bars, spot, surface)
        mov = E.move_events(bars, spot, surface)
        out["SURFACES"][surface] = {
            "BARS": bars.n, "BARS_PRESENT": int(np.isfinite(bars.close).sum()),
            "SPOT_BARS_PRESENT": int(np.isfinite(spot["quote"]).sum()),
            "LEVEL_EVENTS": len(lev), "MOVE_EVENTS": len(mov),
            "LEVEL_EVENTS_BY_TYPE": {t: sum(1 for e in lev if e["TYPE"] == t) for t in K.LEVEL_TYPES},
        }
        for h in K.HYPOTHESES:
            rows = E.cell_rows(lev if h["CARD"] == "DH1-L" else mov, h)
            plans[(h["ID"], surface)] = cell_plan(rows, h, surface, K.HET_SEED + 17 * k + K.HYPOTHESES.index(h))
    for h in K.HYPOTHESES:
        disc, rep = plans[(h["ID"], "DISCOVERY")], plans[(h["ID"], "REPLICATION")]
        out["CELLS"][h["ID"]] = {"CARD": h["CARD"], "STATE": h["STATE"], "DISCOVERY": disc, "REPLICATION": rep,
                                 "DECISION": decide(disc, rep)}
    OUT_JSON.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    OUT_MD.write_text(markdown(out))
    return out


def markdown(out: dict) -> str:
    lines = [
        "# DH1 — outcome-blind feasibility",
        "",
        "**Program:** `DIRECTIONAL_HYPOTHESES_DH1` · **Written before any outcome** · machine record: `DH1_FEASIBILITY.json`",
        "",
        "Events, states and nuisance terms were built from prices and flows known at each decision time. No outcome "
        "was computed (`MARKET_OUTCOMES_OPENED = false`). Planning SE assumes outcome variance 0.25 and a design "
        f"effect of {K.DEFF_PLANNING} for week clustering. Rule, frozen before counting: a cell runs if its discovery "
        f"MDE at 80 % power (Holm first-step alpha) is at most {K.EXECUTE_MDE_MAX} and the smaller arm has at least "
        f"{K.EXECUTE_MIN_ARM} events in at least three epochs with both arms of 30 or more.",
        "",
        "## Surfaces",
        "",
        "| Surface | 5m bars present | spot bars present | level events | sharp-move events |",
        "|---|---|---|---|---|",
    ]
    for s, v in out["SURFACES"].items():
        lines.append(f"| {s} | {v['BARS_PRESENT']} / {v['BARS']} | {v['SPOT_BARS_PRESENT']} | {v['LEVEL_EVENTS']} | {v['MOVE_EVENTS']} |")
    lines += ["", "## Cells", "",
              "| Cell | Surface | N | state / comparator | MDE80 | power at 3 pp | power at 4.5 pp | epochs OK | het power |",
              "|---|---|---|---|---|---|---|---|---|"]
    for cid_, c in out["CELLS"].items():
        for s in ("DISCOVERY", "REPLICATION"):
            p = c[s]
            lines.append(f"| {cid_} | {s} | {p['N']} | {p['N_STATE']} / {p['N_COMPARATOR']} | {p['MDE_80']:.4f} | "
                         f"{p['POWER_AT_BAR']:.2f} | {p['POWER_AT_75PCT_PLANNING']:.2f} | {p['EPOCHS_WITH_BOTH_ARMS_GE_MIN']} | "
                         f"{p['HET_POWER_2X']:.2f} |")
    lines += ["", "## Decisions", "", "| Cell | Status | Replication powered | Het (discovery / replication) | Reasons |",
              "|---|---|---|---|---|"]
    for cid_, c in out["CELLS"].items():
        d = c["DECISION"]
        lines.append(f"| {cid_} | `{d['STATUS']}` | {'yes' if d['REPLICATION_POWERED'] else 'no (live tracking decides)'} | "
                     f"{d['HET_DISCOVERY']} / {d['HET_REPLICATION']} | {'; '.join(d['REASONS']) or '—'} |")
    lines.append("")
    return "\n".join(lines)


def digest() -> str:
    return hashlib.sha256(OUT_JSON.read_bytes()).hexdigest()


if __name__ == "__main__":
    res = run()
    for k, v in res["CELLS"].items():
        print(k, v["DECISION"]["STATUS"], round(v["DISCOVERY"]["MDE_80"], 4), round(v["REPLICATION"]["MDE_80"], 4))
