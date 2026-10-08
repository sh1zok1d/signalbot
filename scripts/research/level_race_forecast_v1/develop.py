"""Model development on CORE 2020–2024 (design §2–§4, §8, §8a). Reads race outcomes of the dev surface.

python -m scripts.research.level_race_forecast_v1.develop
Writes docs/research/LEVEL_RACE_FORECAST_V1_DEVELOPMENT.json. Nothing is frozen here.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np

from scripts.research.level_touch_degradation_v1.data import load_discovery_bars
from scripts.research.owner_cards_r03 import data as RD

from . import constants as K
from .crossvenue import attach_ovmm
from .events import attach_outcomes, first_touches, landmark_rows
from .generic import generic_rows
from .metrics import WeekBoot, evaluate, ll_rows
from .model import (OUT3, TwoHead, b0_matrix, fit_b1, fit_two_head, floor3, predict_b1, tercile_edges, y_index)

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "docs/research/LEVEL_RACE_FORECAST_V1_DEVELOPMENT.json"
PARAMS = {"M1": 10, "M1A": 10, "M1B": 4}


def scored(rows):
    return [r for r in rows if r["outcome"] in OUT3]


def edges_of(train):
    return tercile_edges(np.array([r["sigma"] for r in train if r["landmark"] in ("T0", "G")]))


def fit_variant(train, name, lam):
    spec = K.SPECS[name]
    return fit_two_head(train, spec, spec, lam, edges=edges_of(train))


def ovmm_moments(train):
    v = np.array([r["ovmm"] for r in train if r["landmark"] == "T15" and r.get("ovmm") is not None])
    return float(v.mean()), float(v.std())


def c1_rows(rows):
    """T0 rows and T15 rows with OVMM present (a missing move = no C1 forecast)."""
    return [r for r in rows if r["landmark"] == "T0" or r.get("ovmm") is not None]


def c1_extra(rows, mom):
    mu, sd = mom
    return {K.C1_TERM: [((r["ovmm"] - mu) / sd) if r["landmark"] == "T15" else 0.0 for r in rows]}


def fit_c1(train, base_spec, lam):
    tr = c1_rows(train)
    mom = ovmm_moments(tr)
    edges = edges_of(train)
    spec_b = tuple(base_spec) + (K.C1_TERM,)
    m = fit_two_head(tr, base_spec, spec_b, lam, edges=edges, extra=c1_extra(tr, mom))
    m.c1_moments = list(mom)
    return m


def oof(rows, fitter):
    """Pooled out-of-fold predictions for 2021–2024 (rolling origin)."""
    P, idx = [], []
    for train_years, test_year in K.FOLDS:
        tr = [r for r in rows if r["year"] in train_years]
        te_i = [i for i, r in enumerate(rows) if r["year"] == test_year]
        te = [rows[i] for i in te_i]
        P.append(fitter(tr, te))
        idx += te_i
    order = np.argsort(idx)
    return np.vstack(P)[order], np.array(idx)[order]


def main() -> None:
    bars = load_discovery_bars()
    touches = first_touches(bars)
    rows = attach_outcomes(bars, landmark_rows(bars, touches), touches)
    rows = attach_ovmm(rows, bars)
    counts = {"rows": {lm: sum(r["landmark"] == lm for r in rows) for lm in K.LANDMARKS},
              "ambiguous": {lm: sum(r["landmark"] == lm and r["outcome"] == "AMBIGUOUS" for r in rows) for lm in K.LANDMARKS},
              "unusable": sum(r["outcome"] is None for r in rows)}
    rows = scored(rows)

    # ---- lambda per variant and OOF predictions -------------------------------------------------
    preds: dict = {}
    lam_table: dict = {}
    for name in K.SPECS:
        best = None
        lam_table[name] = {}
        for lam in K.LAMBDA_GRID:
            P, ix = oof(rows, lambda tr, te: fit_variant(tr, name, lam).predict(te))
            y = y_index([rows[i] for i in ix])
            ll = float(ll_rows(P, y).mean())
            lam_table[name][str(lam)] = ll
            if best is None or ll < best[0] - K.LAMBDA_TIE_NATS or (abs(ll - best[0]) < K.LAMBDA_TIE_NATS and lam > best[1]):
                best = (ll, lam, P, ix)
        preds[name] = best
    _, _, _, ix = preds["M1"]
    ev_rows = [rows[i] for i in ix]
    y = y_index(ev_rows)
    P_b0 = floor3(b0_matrix(ev_rows))
    P_b1, _ = oof(rows, lambda tr, te: predict_b1(fit_b1(tr), te))
    ll_b0 = float(ll_rows(P_b0, y).mean())

    # ---- champion -----------------------------------------------------------------------------
    pooled = {n: preds[n][0] for n in K.SPECS}
    best_ll = min(pooled.values())
    champion = "B0"
    if best_ll < ll_b0:
        near = [n for n in K.CHAMPION_TIE_ORDER if pooled[n] - best_ll < K.CHAMPION_TIE_NATS]
        champion = near[0]
    base_name = champion if champion != "B0" else "M1"
    base_lam = preds[base_name][1]

    # ---- C1 (descriptive) ---------------------------------------------------------------------
    c1_all = c1_rows(rows)
    P_c1, ix_c1 = oof(c1_all, lambda tr, te: fit_c1(tr, K.SPECS[base_name], base_lam).predict(
        te, c1_extra(te, ovmm_moments(c1_rows(tr)))))
    c1_ev = [c1_all[i] for i in ix_c1]
    P_base_c1, _ = oof(c1_all, lambda tr, te: fit_variant(tr, base_name, base_lam).predict(te))

    # ---- evaluation ---------------------------------------------------------------------------
    models = {"B0": P_b0, "B1": P_b1, **{n: preds[n][2] for n in K.SPECS}}
    report: dict = {}
    for sub in ("ALL", "T0", "T15"):
        m = np.array([sub == "ALL" or r["landmark"] == sub for r in ev_rows])
        wk = np.array([r["week"] for r in ev_rows])[m]
        boot = WeekBoot(wk)
        report[sub] = {}
        for name, P in models.items():
            refs = {"B0": P_b0[m], "B1": P_b1[m]}
            report[sub][name] = evaluate(P[m], y[m], wk, refs, boot)
    stability: dict = {}
    for yr in (2021, 2022, 2023, 2024):
        for fam in ("ALL",) + K.FAMILIES:
            for lm in ("ALL", "T0", "T15"):
                m = np.array([r["year"] == yr and (fam == "ALL" or r["family"] == fam) and (lm == "ALL" or r["landmark"] == lm)
                              for r in ev_rows])
                if not m.any():
                    continue
                key = f"{yr}|{fam}|{lm}"
                stability[key] = {"n": int(m.sum()),
                                  **{n: float(ll_rows(P[m], y[m]).mean()) for n, P in models.items()}}
    # C1 paired with its base on the same rows
    yc = y_index(c1_ev)
    mc = np.array([r["landmark"] == "T15" for r in c1_ev])
    wkc = np.array([r["week"] for r in c1_ev])[mc]
    c1_report = evaluate(P_c1[mc], yc[mc], wkc, {"BASE": P_base_c1[mc], "B0": floor3(b0_matrix([c1_ev[i] for i in np.flatnonzero(mc)]))})

    # ---- generic stream -----------------------------------------------------------------------
    g = scored(generic_rows(bars, with_outcome=True))
    g_amb = None
    best_g = None
    g_lam = {}
    for lam in K.LAMBDA_GRID:
        Pg, ixg = oof(g, lambda tr, te: fit_two_head(tr, K.GENERIC_SPEC, K.GENERIC_SPEC, lam,
                                                    edges=tercile_edges(np.array([r["sigma"] for r in tr]))).predict(te))
        yg = y_index([g[i] for i in ixg])
        llg = float(ll_rows(Pg, yg).mean())
        g_lam[str(lam)] = llg
        if best_g is None or llg < best_g[0] - K.LAMBDA_TIE_NATS or (abs(llg - best_g[0]) < K.LAMBDA_TIE_NATS and lam > best_g[1]):
            best_g = (llg, lam, Pg, ixg)
    gev = [g[i] for i in best_g[3]]
    yg = y_index(gev)
    Pgb0 = floor3(b0_matrix(gev))
    wkg = np.array([r["week"] for r in gev])
    bg = WeekBoot(wkg)
    g_report = {"GB0": evaluate(Pgb0, yg, wkg, {"GB0": Pgb0}, bg), "G1": evaluate(best_g[2], yg, wkg, {"GB0": Pgb0}, bg)}
    g_choice = "G1" if best_g[0] < float(ll_rows(Pgb0, yg).mean()) - K.CHAMPION_TIE_NATS else "GB0"
    g_info = {"anchors": len({r["i"] for r in gev}), "rows": len(gev), "weeks": int(np.unique(wkg).size),
              "effective_windows": len({r["i"] for r in gev}) / 4, "lambda": best_g[1], "lambda_table": g_lam,
              "choice": g_choice, "per_pair": {}}
    for pair in ("11", "12", "21", "22"):
        mp = np.array([r["pair"] == pair for r in gev])
        g_info["per_pair"][pair] = {"n": int(mp.sum()), "GB0": float(ll_rows(Pgb0[mp], yg[mp]).mean()),
                                    "G1": float(ll_rows(best_g[2][mp], yg[mp]).mean()),
                                    "b0": Pgb0[mp][0].tolist(), "obs": np.bincount(yg[mp], minlength=3).tolist()}

    # ---- full-sample refits (candidates for the freeze; not frozen here) ------------------------
    final = {n: fit_variant(rows, n, preds[n][1]).to_json() for n in K.SPECS}
    final["C1"] = fit_c1(rows, K.SPECS[base_name], base_lam).to_json()
    gfin = fit_two_head(g, K.GENERIC_SPEC, K.GENERIC_SPEC, best_g[1],
                        edges=tercile_edges(np.array([r["sigma"] for r in g]))).to_json()

    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    out = {
        "unit": K.UNIT, "design_sha": K.DESIGN_SHA, "code_commit": commit, "dataset_digest": RD.btc_dataset_digest(),
        "mode": "DISCOVERY (development); DISCOVERY_ONLY for the selected variant",
        "counts": counts, "oof_rows": {lm: int(sum(r["landmark"] == lm for r in ev_rows)) for lm in K.LANDMARKS},
        "lambda": {n: {"chosen": preds[n][1], "pooled_oof_ll": preds[n][0], "grid": lam_table[n],
                       "effective_lambda_times_n_head_r_by_fold": {
                           str(te): preds[n][1] * sum(r["year"] in tr for r in rows) for tr, te in K.FOLDS}}
                   for n in K.SPECS},
        "pooled_oof_ll": {"B0": ll_b0, "B1": float(ll_rows(P_b1, y).mean()), **pooled},
        "champion": champion, "c1_base": base_name,
        "evaluation": report, "stability_ll": stability,
        "c1": {"rows_t15": int(mc.sum()), "evaluation_t15": c1_report},
        "generic": {"info": g_info, "evaluation": g_report},
        "full_sample_fits": final, "generic_fit": gfin,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float) + "\n")
    print(json.dumps({"pooled_oof_ll": out["pooled_oof_ll"], "champion": champion, "lambda": {n: preds[n][1] for n in K.SPECS},
                      "generic": {k: g_info[k] for k in ("anchors", "rows", "choice", "lambda")}}, indent=1))


if __name__ == "__main__":
    main()
