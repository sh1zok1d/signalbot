"""Interior probe cells for COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_V1
(freeze amendment V2, option B). Deterministic; no simulation; no outcome.

For each class and each interval (n_i, n_{i+1}) between consecutive frozen
calibrated sizes, one probe size p_i (geometric midpoint, rounded) is added at
every MUST structural level of the class. Probe cells are EVAL-only: they are
never used to fit Candidate C; at a probe the nearest-lower factor c_env(n_i)
is applied, and all candidates A, B, C (and reference D) are evaluated there.
Seed ranges use family indices 11-14 and are verified disjoint from the frozen
621-cell grid and from Official Run 1.

    python -m scripts.research.compiler_v3_estimator_calibration.build_probe_cells
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from scripts.research.compiler_v3_estimator_calibration import build_calibration_grid as G

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "docs/research/COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_GRID_PROBES_V1.json"
PROBE_FAMILY_INDEX = {"F1": 11, "F2": 12, "F3": 13, "F4": 14}
CAL_SIZES = {"F1": [30, 60, 120, 250, 500], "F2": [40, 60, 100, 160, 260, 400],
             "F3": [8, 15, 25, 40], "F4": [30, 50, 75, 100]}


def probe_size(lo: int, hi: int) -> int:
    p = int(round(math.sqrt(lo * hi)))
    assert lo < p < hi
    return p


def build() -> dict:
    grid = json.loads(G.OUT.read_text())
    must = [c for c in grid["CELLS"] if c["LABEL"] == "MUST"]
    cells, idx = [], 0
    for fam, sizes in CAL_SIZES.items():
        templates = {}
        for c in must:
            if c["FAMILY"] == fam and c["N"] == sizes[0]:
                templates[json.dumps(c["LEVELS"], sort_keys=True)] = c
        for lo, hi in zip(sizes, sizes[1:]):
            p = probe_size(lo, hi)
            for key in sorted(templates):
                t = templates[key]
                levels = dict(t["LEVELS"])
                truth = _truth(fam, p, levels)
                base = G.SEED_BASE + 10**9 * PROBE_FAMILY_INDEX[fam] + 10**6 * idx
                lv = "-".join(f"{k}{v}" for k, v in levels.items() if v is not None and k not in ("m_range", "scale_multiplier"))
                cells.append({
                    "CELL_ID": f"{fam}P-{t['CLASS']}-{t['N_KEY']}{p}-{lv}", "CELL_INDEX": idx, "FAMILY": f"{fam}P",
                    "CLASS": t["CLASS"], "N_KEY": t["N_KEY"], "N": p, "LABEL": "MUST_PROBE", "LEVELS": levels,
                    "PROBE_INTERVAL": [lo, hi], "NEAREST_LOWER_CALIBRATED_N": lo, "TRUTH": truth,
                    "BANDWIDTH_L": G.bandwidth(p), "NU_A": (2 * p - 2) if t["CLASS"] == "TWO_SAMPLE" else p - 1,
                    "NU_B": (2 * p) // (G.bandwidth(2 * p) + 1) - 1 if t["CLASS"] == "TWO_SAMPLE" else p // (G.bandwidth(p) + 1) - 1,
                    "K_IN_DOMAIN": None if truth["VAR_TRUE"] is None else bool(truth["VAR_TRUE"] <= G.VAR_FALLBACK),
                    "DECISIVE": True, "SPLIT": "EVAL_ONLY",
                    "SEED_RANGE": {"EVAL_STAGE_A": [base + 10**5, base + 10**5 + G.STAGE_A - 1],
                                   "EVAL_STAGE_B": [base + 10**5, base + 10**5 + G.STAGE_B - 1]},
                })
                idx += 1
    validation = _validate(cells, grid)
    return {"UNIT_ID": G.UNIT_ID, "AMENDMENT": "FREEZE_AMENDMENT_V2_OPTION_B",
            "BUILT_FROM_GRID_SHA256": _sha(G.OUT), "PROBE_SIZES": {f: [probe_size(a, b) for a, b in zip(s, s[1:])] for f, s in CAL_SIZES.items()},
            "COUNTS": {"PROBE_CELLS": len(cells), "BY_CLASS": {k: sum(c["CLASS"] == k for c in cells) for k in G.REALISTIC_MAX}},
            "GRID_VALIDATION": validation, "CELLS": cells}


def _truth(fam: str, n: int, lv: dict) -> dict:
    if fam in ("F1", "F2"):
        return {"FORMULA": "sigma2 * ar_factor(n, phi), sigma2 = 1", "VAR_TRUE": G.ar_factor(n, lv["phi"]), "PER_REPLICATE": False}
    if fam == "F3":
        eq = (lv["icc"] + (1 - lv["icc"]) / 24.0) * G.ar_factor(n, lv["phi_G"])
        return {"FORMULA": "(1/G) * sum_g sigma2 * (ICC + (1-ICC)/m_g) * ar_factor(G, phi_G)",
                "VAR_TRUE": eq if lv["sizes"] == "EQUAL" else None, "PER_REPLICATE": lv["sizes"] == "HETERO"}
    mult2 = math.exp(0.5) if lv["scale"] == "HETERO" else 1.0
    return {"FORMULA": "sigma2 * (1 + 2v)/3 * E[multiplier^2] * ar_factor(n_e, phi_e)",
            "VAR_TRUE": (1 + 2 * lv["venue_corr"]) / 3.0 * mult2 * G.ar_factor(n, lv["phi_e"]), "PER_REPLICATE": False}


def _validate(cells: list[dict], grid: dict) -> dict:
    mine = sorted((c["SEED_RANGE"]["EVAL_STAGE_B"], c["CELL_ID"]) for c in cells)
    pairwise = all(mine[i][0][1] < mine[i + 1][0][0] for i in range(len(mine) - 1))
    existing = [c["SEED_RANGE"]["CAL"] for c in grid["CELLS"]] + [c["SEED_RANGE"]["EVAL_STAGE_B"] for c in grid["CELLS"]]
    run1 = json.loads(G.RUN1_MANIFEST.read_text())["CELLS"]
    r1 = [c["SEED_RANGE"]["STAGE_B"] for c in run1]
    def disjoint(a, others): return all(a[1] < b[0] or b[1] < a[0] for b in others)
    vs_grid = all(disjoint(r, existing) for r, _ in mine)
    vs_run1 = all(disjoint(r, r1) for r, _ in mine)
    ids = {c["CELL_ID"] for c in cells}
    grid_ids = {c["CELL_ID"] for c in grid["CELLS"]}
    sizes_new = all(c["N"] not in CAL_SIZES[c["FAMILY"][:2]] for c in cells)
    return {"PAIRWISE_DISJOINT": pairwise, "DISJOINT_FROM_FROZEN_GRID": vs_grid, "DISJOINT_FROM_RUN1": vs_run1,
            "UNIQUE_CELL_IDS": len(ids) == len(cells), "NO_ID_COLLISION_WITH_GRID": not (ids & grid_ids),
            "PROBE_SIZES_NOT_CALIBRATED_SIZES": sizes_new, "MIN_SEED": mine[0][0][0], "MAX_SEED": mine[-1][0][1],
            "GRID_OK": bool(pairwise and vs_grid and vs_run1 and len(ids) == len(cells) and not (ids & grid_ids) and sizes_new)}


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> None:
    out = build()
    OUT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"COUNTS": out["COUNTS"], "PROBE_SIZES": out["PROBE_SIZES"], "VALIDATION": out["GRID_VALIDATION"]}, indent=1))


if __name__ == "__main__":
    main()
