"""Deterministic grid builder for COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_V1.

Builds the calibration grid (families, cells, structural levels, labels, analytic
truth formulas and seed ranges) from the frozen spec. No simulation, no RNG draw,
no outcome. Validates that every seed range is pairwise disjoint and disjoint from
every Official Run 1 range (read from the Run 1 golden manifest).

    python -m scripts.research.compiler_v3_estimator_calibration.build_calibration_grid
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SPEC = REPO / "docs/research/COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_SPEC_V1.md"
RUN1_MANIFEST = REPO / "docs/research/COMPILER_V3_VARIANCE_FLOOR_GOLDEN_MANIFEST_V1.json"
OUT = REPO / "docs/research/COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_GRID_V1.json"

UNIT_ID = "COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_V1"
SEED_BASE = 9 * 10**12
STAGE_A, STAGE_B, CAL_N = 4000, 20000, 4000
SD_BASE, VAR_FALLBACK, GAMMA = 1.0, 4.0, 0.01
TAILS_MUST, TAILS_STRESS = ["GAUSS", "T4"], ["T3"]
REALISTIC_MAX = {"TWO_SAMPLE": 250, "PAIRED_UNITS": 260, "CLUSTERED": 40, "RARE_EVENT": 100}
LAMBDA_OOD = [1.25, 1.5, 2.0]


def bandwidth(n: int) -> int:
    return int(math.ceil(n ** (1.0 / 3.0)))


def ar_factor(n: int, phi: float) -> float:
    """n·Var(mean) / sigma² for an AR(1) sequence of length n with lag-1 correlation phi."""
    return 1.0 + 2.0 * sum((1.0 - h / n) * phi**h for h in range(1, n))


def _family_cells() -> list[dict]:
    cells: list[dict] = []

    def add(family, klass, n, label, levels, truth, n_key):
        cells.append({"FAMILY": family, "CLASS": klass, "N_KEY": n_key, "N": n, "LABEL": label,
                      "LEVELS": levels, "TRUTH": truth})

    # F1 two-sample: AR(1) within arms, two equal arms.
    for n in (30, 60, 120, 250, 500):
        for phi in (0.0, 0.3, 0.6, 0.8):
            for tail in TAILS_MUST + TAILS_STRESS:
                label = "MUST" if (phi <= 0.6 and tail in TAILS_MUST) else "STRESS"
                add("F1", "TWO_SAMPLE", n, label, {"phi": phi, "tail": tail},
                    {"FORMULA": "sigma2 * ar_factor(n, phi), sigma2 = 1, per arm; pooled over two equal arms",
                     "VAR_TRUE": SD_BASE**2 * ar_factor(n, phi), "PER_REPLICATE": False}, "n_per_arm")
    # F2 paired units: AR(1) across units.
    for n in (40, 60, 100, 160, 260, 400):
        for phi in (0.0, 0.3, 0.6, 0.8):
            for tail in TAILS_MUST + TAILS_STRESS:
                label = "MUST" if (phi <= 0.6 and tail in TAILS_MUST) else "STRESS"
                add("F2", "PAIRED_UNITS", n, label, {"phi": phi, "tail": tail},
                    {"FORMULA": "sigma2 * ar_factor(N, phi), sigma2 = 1",
                     "VAR_TRUE": SD_BASE**2 * ar_factor(n, phi), "PER_REPLICATE": False}, "N_units")
    # F3 clustered: ICC, cluster-size heterogeneity, AR across clusters.
    for g in (8, 15, 25, 40):
        for icc in (0.02, 0.10, 0.30):
            for sizes in ("EQUAL", "HETERO"):
                for phi in (0.0, 0.3, 0.6):
                    for tail in TAILS_MUST + TAILS_STRESS:
                        label = "MUST" if (phi <= 0.3 and tail in TAILS_MUST) else "STRESS"
                        eq = SD_BASE**2 * (icc + (1 - icc) / 24.0) * ar_factor(g, phi)
                        add("F3", "CLUSTERED", g, label,
                            {"icc": icc, "sizes": sizes, "phi_G": phi, "tail": tail, "m_nominal": 24,
                             "m_range": [12, 36] if sizes == "HETERO" else None},
                            {"FORMULA": "(1/G) * sum_g sigma2 * (ICC + (1-ICC)/m_g) * ar_factor(G, phi_G)",
                             "VAR_TRUE": eq if sizes == "EQUAL" else None,
                             "PER_REPLICATE": sizes == "HETERO"}, "G")
    # F4 rare events: venue correlation, event-scale heterogeneity, AR across events.
    for ne in (30, 50, 75, 100):
        for v in (0.5, 0.7, 0.9):
            for scale in ("HOMO", "HETERO"):
                for phi in (0.0, 0.3, 0.6):
                    for tail in TAILS_MUST + TAILS_STRESS:
                        label = "MUST" if (phi <= 0.3 and tail in TAILS_MUST) else "STRESS"
                        mult2 = math.exp(0.5) if scale == "HETERO" else 1.0
                        add("F4", "RARE_EVENT", ne, label,
                            {"venue_corr": v, "scale": scale, "phi_e": phi, "tail": tail, "venues": 3,
                             "scale_multiplier": "exp(0.5*Z)" if scale == "HETERO" else None},
                            {"FORMULA": "sigma2 * (1 + 2v)/3 * E[multiplier^2] * ar_factor(n_e, phi_e)",
                             "VAR_TRUE": SD_BASE**2 * (1 + 2 * v) / 3.0 * mult2 * ar_factor(ne, phi),
                             "PER_REPLICATE": False}, "n_events")
    # F5 out-of-domain regime ratio, at each class's central MUST level and GAUSS tails.
    central = {"F1": ("TWO_SAMPLE", (30, 60, 120, 250, 500), {"phi": 0.3, "tail": "GAUSS"}, "n_per_arm"),
               "F2": ("PAIRED_UNITS", (40, 60, 100, 160, 260, 400), {"phi": 0.3, "tail": "GAUSS"}, "N_units"),
               "F3": ("CLUSTERED", (8, 15, 25, 40), {"icc": 0.10, "sizes": "EQUAL", "phi_G": 0.0, "tail": "GAUSS", "m_nominal": 24, "m_range": None}, "G"),
               "F4": ("RARE_EVENT", (30, 50, 75, 100), {"venue_corr": 0.7, "scale": "HOMO", "phi_e": 0.0, "tail": "GAUSS", "venues": 3, "scale_multiplier": None}, "n_events")}
    for fam, (klass, ns, levels, n_key) in central.items():
        for n in ns:
            for lam in LAMBDA_OOD:
                base = next(c for c in cells if c["FAMILY"] == fam and c["N"] == n
                            and all(c["LEVELS"].get(k) == v for k, v in levels.items()))
                add("F5", klass, n, "OUT_OF_DOMAIN", {**levels, "lambda": lam, "base_family": fam},
                    {"FORMULA": f"lambda * truth of base cell {fam}; exposed sample drawn at lambda = 1",
                     "VAR_TRUE": None if base["TRUTH"]["VAR_TRUE"] is None else lam * base["TRUTH"]["VAR_TRUE"],
                     "PER_REPLICATE": base["TRUTH"]["PER_REPLICATE"]}, n_key)
    return cells


def build() -> dict:
    fam_index = {"F1": 1, "F2": 2, "F3": 3, "F4": 4, "F5": 5}
    cells = _family_cells()
    out = []
    for i, c in enumerate(cells):
        lv = "-".join(f"{k}{v}" for k, v in c["LEVELS"].items() if v is not None and k not in ("m_range", "scale_multiplier", "base_family"))
        cid = f"{c['FAMILY']}-{c['CLASS']}-{c['N_KEY']}{c['N']}-{lv}"
        base = SEED_BASE + 10**9 * fam_index[c["FAMILY"]] + 10**6 * i
        n = c["N"]
        row = {
            "CELL_ID": cid, "CELL_INDEX": i, **c,
            "BANDWIDTH_L": bandwidth(2 * n if c["CLASS"] == "TWO_SAMPLE" else n),
            "NU_A": (2 * n - 2) if c["CLASS"] == "TWO_SAMPLE" else n - 1,
            "NU_B": (2 * n) // (bandwidth(2 * n) + 1) - 1 if c["CLASS"] == "TWO_SAMPLE" else n // (bandwidth(n) + 1) - 1,
            "K_IN_DOMAIN": None if c["TRUTH"]["VAR_TRUE"] is None else bool(c["TRUTH"]["VAR_TRUE"] <= VAR_FALLBACK),
            "DECISIVE": c["LABEL"] == "MUST",
            "SEED_RANGE": {"CAL": [base, base + CAL_N - 1],
                           "EVAL_STAGE_A": [base + 10**5, base + 10**5 + STAGE_A - 1],
                           "EVAL_STAGE_B": [base + 10**5, base + 10**5 + STAGE_B - 1]},
        }
        out.append(row)
    validation = _validate(out)
    return {
        "UNIT_ID": UNIT_ID, "SPEC": SPEC.name, "BUILT_FROM_SPEC_SHA256": _sha(SPEC),
        "CONSTANTS": {"SEED_BASE": SEED_BASE, "STAGE_A": STAGE_A, "STAGE_B": STAGE_B, "CAL_N": CAL_N,
                      "SD_BASE": SD_BASE, "VAR_FALLBACK": VAR_FALLBACK, "GAMMA": GAMMA,
                      "COVERAGE_MISS_TARGET": 0.01, "COVERAGE_TOLERANCE": 0.01, "UTILITY_RHO_MAX": 1.5,
                      "UTILITY_OK_LOWER_BOUND": 0.80, "CP_CONFIDENCE": 0.99,
                      "BANDWIDTH_RULE": "ceil(n ** (1/3))", "LONG_RUN_FLOOR_FRACTION": 0.25,
                      "REALISTIC_MAX": REALISTIC_MAX, "CLASS_ORDER": ["A", "B", "C"], "REFERENCE_CLASS": "D"},
        "COUNTS": {"CELLS": len(out), "MUST": sum(r["LABEL"] == "MUST" for r in out),
                   "STRESS": sum(r["LABEL"] == "STRESS" for r in out),
                   "OUT_OF_DOMAIN": sum(r["LABEL"] == "OUT_OF_DOMAIN" for r in out),
                   "BY_CLASS": {k: sum(r["CLASS"] == k for r in out) for k in REALISTIC_MAX}},
        "GRID_VALIDATION": validation, "CELLS": out,
    }


def _validate(rows: list[dict]) -> dict:
    ranges = []
    for r in rows:
        ranges.append((r["SEED_RANGE"]["CAL"], r["CELL_ID"], "CAL"))
        ranges.append((r["SEED_RANGE"]["EVAL_STAGE_B"], r["CELL_ID"], "EVAL"))
    ranges.sort()
    pairwise = all(ranges[i][0][1] < ranges[i + 1][0][0] for i in range(len(ranges) - 1))
    run1 = json.loads(RUN1_MANIFEST.read_text())["CELLS"]
    r1 = [(c["SEED_RANGE"]["STAGE_B"][0], c["SEED_RANGE"]["STAGE_B"][1]) for c in run1]
    r1_lo, r1_hi = min(a for a, _ in r1), max(b for _, b in r1)
    disjoint_run1 = all(rg[0] > r1_hi or rg[1] < r1_lo for rg, _, _ in ranges) and all(
        not any(rg[0] <= b and a <= rg[1] for a, b in r1) for rg, _, _ in ranges)
    unique_ids = len({r["CELL_ID"] for r in rows}) == len(rows)
    return {"PAIRWISE_DISJOINT": pairwise, "DISJOINT_FROM_RUN1": disjoint_run1,
            "RUN1_SEED_ENVELOPE": [r1_lo, r1_hi], "RUN1_MANIFEST_SHA256": _sha(RUN1_MANIFEST),
            "UNIQUE_CELL_IDS": unique_ids, "GRID_OK": bool(pairwise and disjoint_run1 and unique_ids)}


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> None:
    grid = build()
    OUT.write_text(json.dumps(grid, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"CELLS": grid["COUNTS"], "VALIDATION": grid["GRID_VALIDATION"], "OUT": OUT.name}, indent=1))


if __name__ == "__main__":
    main()
