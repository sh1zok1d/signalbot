"""Dense exact-count EVAL support cells for COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_V1
(freeze amendment V3). Deterministic; no simulation; no outcome.

For each required class, every integer count n in the declared supported range
[n_min, REALISTIC_MAX] that is neither a frozen calibrated size nor an existing
probe size gets one EVAL-only decisive cell at every MUST structural level of the
class. Candidate C at such a count applies c_env(class, n_i) of the largest
calibrated size n_i <= n. Seed ranges use base 9e12 + 1e10 * family_index (21-24)
+ 1e6 * cell_index and are verified disjoint from Run 1, the 621 calibration
cells and the 198 probe cells. Existing cells are not renumbered.

    python -m scripts.research.compiler_v3_estimator_calibration.build_dense_support_cells
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.research.compiler_v3_estimator_calibration import build_calibration_grid as G
from scripts.research.compiler_v3_estimator_calibration import build_probe_cells as P

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "docs/research/COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_GRID_DENSE_SUPPORT_V1.json"
DENSE_FAMILY_INDEX = {"F1": 21, "F2": 22, "F3": 23, "F4": 24}
FAMILY_SPACING = 10**10
CLASS_OF = {"F1": "TWO_SAMPLE", "F2": "PAIRED_UNITS", "F3": "CLUSTERED", "F4": "RARE_EVENT"}
SUPPORTED_RANGE = {f: [P.CAL_SIZES[f][0], G.REALISTIC_MAX[CLASS_OF[f]]] for f in CLASS_OF}


def dense_counts(fam: str) -> list[int]:
    lo, hi = SUPPORTED_RANGE[fam]
    probes = [P.probe_size(a, b) for a, b in zip(P.CAL_SIZES[fam], P.CAL_SIZES[fam][1:])]
    return [n for n in range(lo, hi + 1) if n not in P.CAL_SIZES[fam] and n not in probes]


def build() -> dict:
    grid = json.loads(G.OUT.read_text())
    probes = json.loads(P.OUT.read_text())
    must = [c for c in grid["CELLS"] if c["LABEL"] == "MUST"]
    cells, idx = [], 0
    for fam in CLASS_OF:
        templates = {}
        for c in must:
            if c["FAMILY"] == fam and c["N"] == P.CAL_SIZES[fam][0]:
                templates[json.dumps(c["LEVELS"], sort_keys=True)] = c
        for n in dense_counts(fam):
            lower = max(s for s in P.CAL_SIZES[fam] if s <= n)
            for key in sorted(templates):
                t = templates[key]
                levels = dict(t["LEVELS"])
                truth = P._truth(fam, n, levels)
                base = G.SEED_BASE + FAMILY_SPACING * DENSE_FAMILY_INDEX[fam] + 10**6 * idx
                lv = "-".join(f"{k}{v}" for k, v in levels.items() if v is not None and k not in ("m_range", "scale_multiplier"))
                cells.append({
                    "CELL_ID": f"{fam}D-{t['CLASS']}-{t['N_KEY']}{n}-{lv}", "CELL_INDEX": idx, "FAMILY": f"{fam}D",
                    "CLASS": t["CLASS"], "N_KEY": t["N_KEY"], "N": n, "LABEL": "MUST_DENSE", "LEVELS": levels,
                    "NEAREST_LOWER_CALIBRATED_N": lower, "TRUTH": truth,
                    "BANDWIDTH_L": G.bandwidth(n), "NU_A": (2 * n - 2) if t["CLASS"] == "TWO_SAMPLE" else n - 1,
                    "NU_B": (2 * n) // (G.bandwidth(2 * n) + 1) - 1 if t["CLASS"] == "TWO_SAMPLE" else n // (G.bandwidth(n) + 1) - 1,
                    "K_IN_DOMAIN": None if truth["VAR_TRUE"] is None else bool(truth["VAR_TRUE"] <= G.VAR_FALLBACK),
                    "DECISIVE": True, "SPLIT": "EVAL_ONLY",
                    "SEED_RANGE": {"EVAL_STAGE_A": [base + 10**5, base + 10**5 + G.STAGE_A - 1],
                                   "EVAL_STAGE_B": [base + 10**5, base + 10**5 + G.STAGE_B - 1]},
                })
                idx += 1
    validation = _validate(cells, grid, probes)
    support = support_set(grid, probes, cells)
    return {"UNIT_ID": G.UNIT_ID, "AMENDMENT": "FREEZE_AMENDMENT_V3_DENSE_EXACT_COUNT_SUPPORT",
            "BUILT_FROM": {"GRID_SHA256": _sha(G.OUT), "PROBES_SHA256": _sha(P.OUT)},
            "SUPPORTED_RANGE": {CLASS_OF[f]: r for f, r in SUPPORTED_RANGE.items()},
            "COUNTS": {"DENSE_CELLS": len(cells), "BY_CLASS": {k: sum(c["CLASS"] == k for c in cells) for k in G.REALISTIC_MAX},
                       "DENSE_COUNTS_BY_CLASS": {CLASS_OF[f]: len(dense_counts(f)) for f in CLASS_OF}},
            "SUPPORT_SET": {"SIZE": len(support), "SHA256": _digest(support),
                            "DEFINITION": "sorted (class, n, structural-level key) over every EVAL support cell: calibrated MUST EVAL cells in range, the 198 probes in range, the dense cells"},
            "GRID_VALIDATION": validation, "CELLS": cells}


def support_set(grid: dict, probes: dict, dense: list[dict]) -> list[list]:
    rows = set()
    for c in grid["CELLS"]:
        if c["LABEL"] == "MUST" and SUPPORTED_RANGE[c["FAMILY"]][0] <= c["N"] <= SUPPORTED_RANGE[c["FAMILY"]][1]:
            rows.add((c["CLASS"], c["N"], json.dumps(c["LEVELS"], sort_keys=True)))
    for c in probes["CELLS"] + dense:
        fam = c["FAMILY"][:2]
        if SUPPORTED_RANGE[fam][0] <= c["N"] <= SUPPORTED_RANGE[fam][1]:
            rows.add((c["CLASS"], c["N"], json.dumps(c["LEVELS"], sort_keys=True)))
    return [list(r) for r in sorted(rows)]


def _validate(cells: list[dict], grid: dict, probes: dict) -> dict:
    mine = sorted((c["SEED_RANGE"]["EVAL_STAGE_B"], c["CELL_ID"]) for c in cells)
    pairwise = all(mine[i][0][1] < mine[i + 1][0][0] for i in range(len(mine) - 1))
    existing = [c["SEED_RANGE"]["CAL"] for c in grid["CELLS"]] + [c["SEED_RANGE"]["EVAL_STAGE_B"] for c in grid["CELLS"]] \
        + [c["SEED_RANGE"]["EVAL_STAGE_B"] for c in probes["CELLS"]]
    r1 = [c["SEED_RANGE"]["STAGE_B"] for c in json.loads(G.RUN1_MANIFEST.read_text())["CELLS"]]
    ex_lo, ex_hi = min(a for a, _ in existing), max(b for _, b in existing)
    def disjoint(a, others): return all(a[1] < b[0] or b[1] < a[0] for b in others)
    vs_existing = all(disjoint(r, existing) for r, _ in mine)
    vs_run1 = all(disjoint(r, r1) for r, _ in mine)
    ids = {c["CELL_ID"] for c in cells}
    other_ids = {c["CELL_ID"] for c in grid["CELLS"]} | {c["CELL_ID"] for c in probes["CELLS"]}
    complete = all(
        {c["N"] for c in cells if c["FAMILY"] == f + "D"} == set(dense_counts(f)) for f in CLASS_OF)
    levels_ok = all(
        sum(1 for c in cells if c["FAMILY"] == f + "D" and c["N"] == n) == len({json.dumps(c["LEVELS"], sort_keys=True)
            for c in grid["CELLS"] if c["FAMILY"] == f and c["LABEL"] == "MUST"})
        for f in CLASS_OF for n in dense_counts(f))
    return {"PAIRWISE_DISJOINT": pairwise, "DISJOINT_FROM_621_AND_198": vs_existing, "DISJOINT_FROM_RUN1": vs_run1,
            "EXISTING_SEED_ENVELOPE": [ex_lo, ex_hi], "MIN_SEED": mine[0][0][0], "MAX_SEED": mine[-1][0][1],
            "UNIQUE_CELL_IDS": len(ids) == len(cells), "NO_ID_COLLISION": not (ids & other_ids),
            "EVERY_INTEGER_COUNT_COVERED": complete, "EVERY_MUST_LEVEL_AT_EVERY_COUNT": levels_ok,
            "GRID_OK": bool(pairwise and vs_existing and vs_run1 and len(ids) == len(cells) and not (ids & other_ids) and complete and levels_ok)}


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main() -> None:
    out = build()
    OUT.write_text(json.dumps(out, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({k: out[k] for k in ("SUPPORTED_RANGE", "COUNTS", "SUPPORT_SET", "GRID_VALIDATION")}, indent=1))


if __name__ == "__main__":
    main()
