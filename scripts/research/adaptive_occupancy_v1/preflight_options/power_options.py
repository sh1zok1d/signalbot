"""Outcome-free information for the owner's GO (design §11). NOT part of the frozen design or its evaluator digest.

    python -m scripts.research.adaptive_occupancy_v1.preflight_options.power_options expanding OUT.json
        amendment option (a): an EXPANDING memory (encoded 0) added to the candidates; beta = 0.03
    python -m scripts.research.adaptive_occupancy_v1.preflight_options.power_options strong OUT.json
        the frozen design under a doubled synthetic signal, beta = 0.06 (non-null scenarios)

Same rows, schedule (first outer block from the 26-week memory), seeds, selector and bootstrap as the preflight."""
from __future__ import annotations

import json
import sys

import numpy as np

from scripts.research.adaptive_b1_forecast_v1 import model as M
from scripts.research.adaptive_occupancy_v1 import constants as K
from scripts.research.adaptive_occupancy_v1 import evaluate as E
from scripts.research.adaptive_occupancy_v1 import walkforward as WF
from scripts.research.adaptive_occupancy_v1.surfaces import load_all

EXP = 0
FROZEN_MEMORIES = (26, 52, 104)


def _eligible_with_expanding(S, first_ms):
    return [EXP] + [m for m in FROZEN_MEMORIES if S - K.INNER_BLOCKS * WF.block_ms() - m * K.WEEK_MS >= first_ms]


def _predict_grid_with_expanding(rows, sched, y, log_models=True):
    n, c, blk = rows["close_ms"].size, rows["close_ms"], WF.block_ms()
    preds = {"CLIM": np.full(n, np.nan), "B1": np.full(n, np.nan), "STATIC_OCC4": np.full(n, np.nan)}
    for mem in K.MEMORIES_WEEKS:
        for cfg in K.CONFIGS:
            preds[(mem, cfg)] = np.full(n, np.nan)
    for v, sv in sched.items():
        inv = rows["venue"] == v
        for s in sv["grid_starts"]:
            s = int(s)
            tgt = np.flatnonzero(inv & (c >= s) & (c < s + blk))
            if tgt.size == 0:
                continue
            past = inv & WF.realized_by(c, s)
            tr = np.flatnonzero(past)
            preds["CLIM"][tgt] = float(y[tr].mean())
            for mem in K.MEMORIES_WEEKS:
                if mem != EXP and s - mem * K.WEEK_MS < sv["first_ms"]:
                    continue
                trm = tr if mem == EXP else np.flatnonzero(past & (c >= s - mem * K.WEEK_MS))
                for cfg in K.CONFIGS:
                    m = M.fit(WF.design(rows, trm, cfg), y[trm])
                    preds[(mem, cfg)][tgt] = M.predict(m, WF.design(rows, tgt, cfg))
            preds["B1"][tgt] = preds[(EXP, K.NO_OCC)][tgt]
            preds["STATIC_OCC4"][tgt] = preds[(EXP, K.STATIC_OCC)][tgt]
    return {"preds": preds, "meta": {}}


def main() -> None:
    mode, out_path = sys.argv[1], sys.argv[2]
    rows = load_all()
    sched = WF.schedule(rows)                       # with the frozen memories
    scenarios = K.SYN_SCENARIOS
    if mode == "expanding":
        K.MEMORIES_WEEKS = (EXP,) + FROZEN_MEMORIES
        WF.eligible_memories = _eligible_with_expanding
        WF.predict_grid = _predict_grid_with_expanding
    elif mode == "strong":
        K.SYN_BETA = 0.06
        scenarios = tuple(s for s in scenarios if s[1] is not None)
    else:
        raise SystemExit("mode: expanding | strong")
    out = []
    for name, on, off in scenarios:
        k = [s[0] for s in K.SYN_SCENARIOS].index(name)
        ev = E.evaluate_predictions(rows, sched, E.synthetic_y(rows, on, off, K.SYN_SEED + k), log_models=False)
        log = ev["sel"]["log"]
        out.append({"scenario": name, "beta": K.SYN_BETA, "route": ev["route"],
                    **{f"brier_{p}": ev["brier_d"][p] for p in ("ADAPTIVE-B1", "ADAPTIVE-STATIC_OCC4", "STATIC_OCC4-B1",
                                                                 "ADAPTIVE-MM_NO_OCC")},
                    "selection_share": E.selection_share(log),
                    "memory_share": {str(m): float(np.mean([b["selected_memory_weeks"] == m for b in log]))
                                     for m in K.MEMORIES_WEEKS}})
        print(name, ev["route"], flush=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, sort_keys=True)


if __name__ == "__main__":
    main()
