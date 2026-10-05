"""CLI of the calibration executor.

    python -m scripts.research.compiler_v3_estimator_calibration.run --digests
    python -m scripts.research.compiler_v3_estimator_calibration.run --dev-fixture OUT_DIR
    python -m scripts.research.compiler_v3_estimator_calibration.run --official OUT_DIR   # refused: no run authorization

--official is refused unless a run-authorization artifact exists and verifies; none exists.
No frozen CAL/EVAL cell is executed by --dev-fixture.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.research.compiler_v3_estimator_calibration import aggregate as AG
from scripts.research.compiler_v3_estimator_calibration import cells as C
from scripts.research.compiler_v3_estimator_calibration import engine


def dev_cells(seed_base: int = 1_000_000, n_cal: int = 60, n_eval: int = 60) -> tuple[list[dict], list[dict], dict, dict]:
    """Tiny DEV fixtures: not frozen cells, seeds < 1e9. Sizes are deliberately not frozen sizes."""
    def cell(cid, fam, klass, n, levels, idx, cal=True):
        base = seed_base + 10_000 * idx
        c = {"CELL_ID": cid, "FAMILY": fam, "CLASS": klass, "N": n, "LABEL": "MUST", "DECISIVE": True, "LEVELS": levels,
             "SEED_RANGE": {"EVAL_STAGE_B": [base + 5_000, base + 5_000 + n_eval - 1]}}
        if cal:
            c["SEED_RANGE"]["CAL"] = [base, base + n_cal - 1]
        return c
    cal_sizes = {"TWO_SAMPLE": [30, 60], "PAIRED_UNITS": [40, 60], "CLUSTERED": [8, 15], "RARE_EVENT": [30, 50]}
    cells, i = [], 0
    for klass, sizes in cal_sizes.items():
        fam = {"TWO_SAMPLE": "F1", "PAIRED_UNITS": "F2", "CLUSTERED": "F3", "RARE_EVENT": "F4"}[klass]
        for n in sizes:
            lv = {"F1": {"phi": 0.0, "tail": "GAUSS"}, "F2": {"phi": 0.3, "tail": "GAUSS"},
                  "F3": {"icc": 0.1, "sizes": "EQUAL", "phi_G": 0.0, "tail": "GAUSS", "m_nominal": 24, "m_range": None},
                  "F4": {"venue_corr": 0.7, "scale": "HOMO", "phi_e": 0.0, "tail": "GAUSS", "venues": 3, "scale_multiplier": None}}[fam]
            cells.append(cell(f"DEV-{klass}-{n}", fam, klass, n, lv, i)); i += 1
    realistic = {"TWO_SAMPLE": 60, "PAIRED_UNITS": 60, "CLUSTERED": 15, "RARE_EVENT": 50}
    rng = {k: [v[0], v[-1]] for k, v in cal_sizes.items()}
    return cells, cells, realistic, rng


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--digests", action="store_true")
    ap.add_argument("--dev-fixture", metavar="OUT_DIR")
    ap.add_argument("--official", metavar="OUT_DIR")
    a = ap.parse_args()
    if a.digests:
        print(json.dumps({"EXECUTOR": engine.executor_digest(), "FROZEN_INPUTS": C.frozen()["DIGESTS"],
                          "FROZEN_INPUTS_MATCH_AMENDMENT_V3": C.digests_match_amendment()}, indent=1))
        return
    if a.official:
        out = Path(a.official)
        engine.run_cal(out, C.cal_cells(), official=True)          # raises OfficialExecutionRefused: no authorization
        return
    if a.dev_fixture:
        out = Path(a.dev_fixture)
        cal, ev, realistic, rng = dev_cells()
        engine.run_cal(out, cal, cal_n=60)
        res = engine.run_eval(out, ev, stage_a=60, stage_b=120)
        agg = AG.aggregate(res, realistic, rng)
        (out / "DEV_AGGREGATION.json").write_text(json.dumps(agg, indent=1, sort_keys=True) + "\n")
        print(json.dumps({"GLOBAL_STATUS": agg["GLOBAL_STATUS"], "CLASSES": {k: v["CLASS_STATUS"] for k, v in agg["CLASSES"].items()}}, indent=1))


if __name__ == "__main__":
    main()
