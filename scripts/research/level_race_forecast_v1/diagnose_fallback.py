"""Descriptive diagnostics after development, before the freeze (mini-head red team R1/R2).

Same out-of-fold rows as develop.py; nothing is selected or refit for publication here.
- R2: the fallback model (generic G1 applied to level geometry: B0 offset + generic intercepts +
  SIGMA_T with generic tercile edges, fitted on the training years' generic rows) on level rows:
  CITL per outcome, recalibration slope per head, and the level-minus-generic intercept per head in
  logits (slope fixed at 1), per landmark, week-cluster bootstrap.
- R1 (descriptive on dev): M1 against that raw fallback, paired log-loss.

python -m scripts.research.level_race_forecast_v1.diagnose_fallback
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np

from scripts.research.level_touch_degradation_v1.data import load_discovery_bars

from . import constants as K
from .develop import fit_variant, oof, scored
from .events import attach_outcomes, first_touches, landmark_rows
from .generic import generic_rows
from .metrics import WeekBoot, evaluate, ll_rows
from .model import fit_logit, fit_two_head, logit, tercile_edges, y_index

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "docs/research/LEVEL_RACE_FORECAST_V1_FALLBACK_DIAGNOSTIC.json"
G_LAMBDA = 0.032   # generic lambda chosen in development


def intercept_shift(p: np.ndarray, y: np.ndarray, w: np.ndarray | None = None) -> float:
    """a in logit P(y) = a + logit p (slope fixed at 1)."""
    X = np.ones((len(p), 1))
    return float(fit_logit(X, logit(p), y.astype(float), 0.0, np.array([False]), w=w)[0])


def main() -> None:
    bars = load_discovery_bars()
    touches = first_touches(bars)
    rows = scored(attach_outcomes(bars, landmark_rows(bars, touches), touches))
    g = scored(generic_rows(bars, with_outcome=True))

    def fb(tr_years, te):
        gtr = [r for r in g if r["year"] in tr_years]
        m = fit_two_head(gtr, K.GENERIC_SPEC, K.GENERIC_SPEC, G_LAMBDA,
                         edges=tercile_edges(np.array([r["sigma"] for r in gtr])))
        return m.predict(te)

    P_fb, ix = [], []
    for tr_years, te_year in K.FOLDS:
        te_i = [i for i, r in enumerate(rows) if r["year"] == te_year]
        P_fb.append(fb(tr_years, [rows[i] for i in te_i]))
        ix += te_i
    order = np.argsort(ix)
    P_fb = np.vstack(P_fb)[order]
    ix = np.array(ix)[order]
    P_m1, ix2 = oof(rows, lambda tr, te: fit_variant(tr, "M1", 0.008).predict(te))
    assert np.array_equal(ix, ix2)
    ev = [rows[i] for i in ix]
    y = y_index(ev)
    out: dict = {"fallback_spec": "G1 (generic, lambda 0.032, fitted on the fold's training-year generic rows) applied to level B0 geometry; head U of G1 is used as the 'beyond | resolved' head",
                 "rows": len(ev)}
    for sub in ("ALL", "T0", "T15"):
        m = np.array([sub == "ALL" or r["landmark"] == sub for r in ev])
        wk = np.array([r["week"] for r in ev])[m]
        boot = WeekBoot(wk)
        e = evaluate(P_fb[m], y[m], wk, {"M1": P_m1[m]}, boot)
        rec = {"n": e["n"], "fallback_logloss": e["logloss"], "citl_pp": e["citl_pp"],
               "heads": {h: {k: e["heads"][h][k] for k in ("recal_a", "recal_a_ci95", "recal_b", "recal_b_ci95", "citl_pp")}
                         for h in ("R", "B")},
               "m1_gain_vs_fallback_nats": -e["ll_gain_vs_M1"], "m1_gain_vs_fallback_ci95": [-e["ll_gain_vs_M1_ci95"][1], -e["ll_gain_vs_M1_ci95"][0]]}
        # level-minus-generic intercept per head (slope fixed 1), with bootstrap
        P = P_fb[m]
        yy = y[m]
        pR, yR = 1 - P[:, 2], (yy != 2).astype(int)
        res = yy != 2
        pB, yB = P[res, 0] / (P[res, 0] + P[res, 1]), (yy[res] == 0).astype(int)
        shifts = {}
        for h, (p, t, mask) in {"R": (pR, yR, np.ones(len(yy), bool)), "B": (pB, yB, res)}.items():
            a = intercept_shift(p, t)
            draws = [intercept_shift(p, t, boot.row_weights(d)[mask]) for d in range(boot.W.shape[0])]
            shifts[h] = {"a_level_minus_generic_logit": a,
                         "ci95": [float(np.quantile(draws, .025)), float(np.quantile(draws, .975))]}
        rec["intercept_shift"] = shifts
        out[sub] = rec
    out["code_commit"] = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    for sub in ("ALL", "T0", "T15"):
        r = out[sub]
        print(sub, r["n"], "M1 vs fb", round(r["m1_gain_vs_fallback_nats"], 4), [round(v, 4) for v in r["m1_gain_vs_fallback_ci95"]])
        print("  citl", {k: [round(x, 1) for x in v] for k, v in r["citl_pp"].items()})
        print("  heads", {h: (round(v["recal_b"], 2), [round(x, 2) for x in v["recal_b_ci95"]]) for h, v in r["heads"].items()})
        print("  shift", {h: (round(v["a_level_minus_generic_logit"], 3), [round(x, 3) for x in v["ci95"]]) for h, v in r["intercept_shift"].items()})


if __name__ == "__main__":
    main()
