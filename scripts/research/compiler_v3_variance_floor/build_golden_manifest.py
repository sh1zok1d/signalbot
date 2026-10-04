"""Build COMPILER_V3_VARIANCE_FLOOR_GOLDEN_MANIFEST_V1.json (spec rev 3).

Pure, deterministic, analytic. No random numbers, no market data, no simulation.
N_ORACLE_80 is the information count at which the design's own inference
procedure reaches power 0.80 for delta_min under VAR_TRUE, independent of any
candidate floor, of VAR_EXPOSED_ESTIMATE and of the compiler.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from scipy.stats import norm, t as student_t

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "docs/research/COMPILER_V3_VARIANCE_FLOOR_GOLDEN_MANIFEST_V1.json"

SD_BASE = 1.0
VAR_FALLBACK = (2.0 * SD_BASE) ** 2
POWER = 0.80
HOLM_FAMILY = 4
ALPHA = 0.05 / HOLM_FAMILY          # Holm first step, two-sided
Z_A = norm.ppf(1 - ALPHA / 2)
Z_B = norm.ppf(POWER)
K_GRID = (0.50, 0.75, 1.00)
Q_GRID = (1.00, 0.75, 0.50, 0.33)
SIZE_MULT = {0.50: "MUST_NOT_BE_FEASIBLE", 0.75: "BOUNDARY_NO_REQUIREMENT",
             1.00: "BOUNDARY_NO_REQUIREMENT", 1.50: "MUST_BE_FEASIBLE"}
EFFECTS = ("NULL", "DELTA_MIN", "2x_DELTA_MIN")
STAGE_A, STAGE_B = 2000, 10000
SEED_DESIGN, SEED_CELL = 10 ** 12, 10 ** 6

# Design table. UNIT_STAT_SD is the SD of the unit statistic in SD_BASE units at k = 1
# (VAR_TRUE = k * VAR_FALLBACK by construction), so the oracle only needs k.
DESIGNS = [
    {"ID": "S1", "IDX": 1, "CLASS": "two-group unpaired", "UNIT": "observation", "DELTA_MIN": 0.5,
     "INFERENCE": "two-sample t", "VARIANTS": [{"VID": "gauss", "PARAMS": {"innovation": "gaussian"}}]},
    {"ID": "S2", "IDX": 2, "CLASS": "two-group unpaired, heavy tails (3B only)", "UNIT": "observation", "DELTA_MIN": 0.5,
     "INFERENCE": "two-sample t", "VARIANTS": [{"VID": "t4", "PARAMS": {"innovation": "t4_scaled"}},
                                               {"VID": "t3", "PARAMS": {"innovation": "t3_scaled"}}], "GRID": "3B_ONLY"},
    {"ID": "S3", "IDX": 3, "CLASS": "paired / randomization", "UNIT": "pair", "DELTA_MIN": 0.5,
     "INFERENCE": "sign-flip over pairs (20000 draws)", "VARIANTS": [{"VID": "icc05", "PARAMS": {"pair_icc": 0.5}}]},
    {"ID": "S4", "IDX": 4, "CLASS": "small-G clustered", "UNIT": "cluster (date) of 24 hours", "DELTA_MIN": 0.5,
     "INFERENCE": "cluster-robust ratio, G/(G-1), t_{G-1}", "M": 24,
     "VARIANTS": [{"VID": "icc005", "PARAMS": {"icc": 0.05, "m": 24}}, {"VID": "icc015", "PARAMS": {"icc": 0.15, "m": 24}}]},
    {"ID": "S5", "IDX": 5, "CLASS": "rare-event, event-level clustered", "UNIT": "event (3 venue measurements)", "DELTA_MIN": 1.0,
     "INFERENCE": "sign-flip over events", "VARIANTS": [{"VID": "vc080", "PARAMS": {"venues": 3, "venue_corr": 0.80}}]},
    {"ID": "S6", "IDX": 6, "CLASS": "rare-event with era clusters", "UNIT": "event nested in 3 eras", "DELTA_MIN": 1.0,
     "INFERENCE": "era-stratified sign-flip", "VARIANTS": [{"VID": "era3", "PARAMS": {"eras": 3, "era_shift_sd": 0.5}}]},
]


def oracle(design: dict, variant: dict, k: float) -> tuple[int, str, dict]:
    """(N_ORACLE_80, unit name, rounding note). Analytic, candidate-independent."""
    var_true = k * VAR_FALLBACK
    d = design["DELTA_MIN"]
    if design["ID"] in ("S1", "S2"):
        n_arm = 2 * var_true * (Z_A + Z_B) ** 2 / d ** 2
        n = 2 * math.ceil(n_arm)
        return n, "observations (both arms, equal allocation)", {"RULE": "ceil per arm, x2", "RAW": 2 * n_arm}
    if design["ID"] == "S3":
        raw = var_true * (Z_A + Z_B) ** 2 / d ** 2
        return math.ceil(raw), "pairs", {"RULE": "ceil; normal approximation of the sign-flip test", "RAW": raw}
    if design["ID"] == "S4":
        m, icc = variant["PARAMS"]["m"], variant["PARAMS"]["icc"]
        deff = 1 + (m - 1) * icc
        g = 5
        while True:
            ta = student_t.ppf(1 - ALPHA / 2, g - 1)
            tb = student_t.ppf(POWER, g - 1)
            need = var_true * deff * (ta + tb) ** 2 / (m * d ** 2)
            if g >= need:
                break
            g += 1
        raw_norm = var_true * deff * (Z_A + Z_B) ** 2 / (m * d ** 2)
        return g, "clusters (dates); hours = 24 x clusters", {"RULE": "smallest integer G with G >= DEFF*var*(t_{G-1,a}+t_{G-1,b})^2/(m*d^2); t quantiles iterated on G-1", "RAW_NORMAL_APPROX": raw_norm, "DEFF": deff}
    if design["ID"] == "S5":
        raw = var_true * (Z_A + Z_B) ** 2 / d ** 2
        return math.ceil(raw), "events (venue-averaged contrast)", {"RULE": "ceil; VAR_TRUE is the variance of the venue-averaged event statistic; venues never multiply N", "RAW": raw}
    if design["ID"] == "S6":
        raw = var_true * (Z_A + Z_B) ** 2 / d ** 2
        n = 3 * math.ceil(raw / 3)
        return n, "events (equal across 3 eras)", {"RULE": "ceil to a multiple of 3 (equal era allocation); era shifts removed by stratification", "RAW": raw}
    raise KeyError(design["ID"])


def size_from_mult(n_oracle: int, mult: float, design: dict) -> tuple[int, str]:
    raw = n_oracle * mult
    if design["ID"] in ("S1", "S2"):
        n = 2 * math.ceil(raw / 2); note = "ceil to even (equal arms)"
    elif design["ID"] == "S6":
        n = 3 * math.ceil(raw / 3); note = "ceil to a multiple of 3 (eras)"
    elif design["ID"] == "S4":
        n = max(4, math.ceil(raw)); note = "ceil; floor of 4 clusters so t_{G-1} exists"
    else:
        n = math.ceil(raw); note = "ceil"
    return n, note


def build() -> dict:
    cells, cell_index = [], 0
    for design in DESIGNS:
        for variant in design["VARIANTS"]:
            grid_points = []
            if design.get("GRID") != "3B_ONLY":
                grid_points += [("3A", k, q, "FLOOR_CALIBRATION") for k in K_GRID for q in Q_GRID]
                grid_points += [("3B", k, 1.00, "REGIME_SHIFT") for k in (1.50, 2.00)]
            else:
                grid_points += [("3B", 1.00, 1.00, "HEAVY_TAILS")]
            if design["ID"] == "S4":
                grid_points += [("3B", 1.00, 1.00, "DEPENDENCE_STRESS_ICC_X2")]
            if design["ID"] == "S5":
                grid_points += [("3B", 1.00, 1.00, "DEPENDENCE_STRESS_VENUE_CORR_095")]
            for grid, k, q, stress in grid_points:
                v = dict(variant)
                params = dict(variant["PARAMS"])
                if stress == "DEPENDENCE_STRESS_ICC_X2":
                    params["icc"] = round(params["icc"] * 2, 3)
                if stress == "DEPENDENCE_STRESS_VENUE_CORR_095":
                    params["venue_corr"] = 0.95
                v["PARAMS"] = params
                n_oracle, unit, rounding = oracle(design, v, k)
                for mult, expected in SIZE_MULT.items():
                    n, size_note = size_from_mult(n_oracle, mult, design)
                    for effect in EFFECTS:
                        cell_index += 1
                        base = SEED_DESIGN * design["IDX"] + SEED_CELL * cell_index
                        role = "SAFETY"
                        if grid == "3B":
                            role = "STRESS_REGRESSION"
                        elif expected == "MUST_BE_FEASIBLE":
                            role = "BOTH"
                        checks = {"NULL": "SIZE<=ALPHA+0.01", "DELTA_MIN": "POWER>=0.75_IF_FEASIBLE",
                                  "2x_DELTA_MIN": "POWER>=0.95_IF_FEASIBLE"}[effect]
                        cells.append({
                            "CELL_ID": f"{design['ID']}-{v['VID']}-{grid}-{stress}-k{k:.2f}-q{q:.2f}-x{mult:.2f}-{effect}",
                            "DESIGN_ID": design["ID"], "VARIANT_ID": v["VID"], "SCENARIO": design["CLASS"],
                            "INFERENCE": design["INFERENCE"], "INDEPENDENT_UNIT": design["UNIT"],
                            "GENERATOR_PARAMS": {**params, "sd_base": SD_BASE, "delta_min": design["DELTA_MIN"]},
                            "GRID": grid, "STRESS": stress,
                            "VARIANCE_RELATIONSHIPS": {"k": k, "q": q, "SD_BASE": SD_BASE, "VAR_FALLBACK": VAR_FALLBACK,
                                                       "VAR_TRUE": k * VAR_FALLBACK, "VAR_EXPOSED_ESTIMATE": q * k * VAR_FALLBACK},
                            "N_ORACLE_80": n_oracle, "ORACLE_UNIT": unit, "ORACLE_ROUNDING": rounding,
                            "SIZE_MULTIPLIER": mult, "SAMPLE_SIZE": {"COUNT": n, "UNIT": unit, "ROUNDING": size_note},
                            "TRUE_EFFECT": effect,
                            "EXPECTED_CLASSIFICATION": expected if grid == "3A" else "BOUNDARY_NO_REQUIREMENT",
                            "ROLE": role, "CHECK": checks,
                            "MULTIPLICITY_ALPHA": ALPHA,
                            "SEED_RANGE": {"STAGE_A": [base, base + STAGE_A - 1], "STAGE_B": [base, base + STAGE_B - 1]},
                        })
    return {
        "MANIFEST": "COMPILER_V3_VARIANCE_FLOOR_GOLDEN_MANIFEST_V1", "STATUS": "FROZEN_2026-10-04",
        "SPEC": "docs/research/COMPILER_V3_VARIANCE_FLOOR_VALIDATION_SPEC_V1.md",
        "CONSTANTS": {"SD_BASE": SD_BASE, "VAR_FALLBACK": VAR_FALLBACK, "POWER": POWER, "HOLM_FAMILY": HOLM_FAMILY,
                      "ALPHA": ALPHA, "Z_ALPHA": Z_A, "Z_BETA": Z_B, "K_GRID": K_GRID, "Q_GRID": Q_GRID,
                      "SIZE_MULTIPLIERS": SIZE_MULT, "STAGE_A": STAGE_A, "STAGE_B": STAGE_B,
                      "SEED_NAMESPACE": "base = 1e12*design_index + 1e6*cell_index; seed = base + replicate_index, 0 <= replicate_index < 10000; Stage A is the prefix [base, base+1999] of Stage B [base, base+9999]"},
        "CANDIDATE_FLOORS": [0.60, 0.75, 1.00],
        "CELLS": cells,
    }


REQUIRED_FIELDS = ("CELL_ID", "DESIGN_ID", "VARIANT_ID", "SCENARIO", "INFERENCE", "INDEPENDENT_UNIT",
                   "GENERATOR_PARAMS", "GRID", "STRESS", "VARIANCE_RELATIONSHIPS", "N_ORACLE_80", "ORACLE_UNIT",
                   "ORACLE_ROUNDING", "SIZE_MULTIPLIER", "SAMPLE_SIZE", "TRUE_EFFECT", "EXPECTED_CLASSIFICATION",
                   "ROLE", "CHECK", "MULTIPLICITY_ALPHA", "SEED_RANGE")


def var_planning(cell: dict, f: float) -> float:
    """Exact frozen arithmetic: VAR_PLANNING = VAR_FALLBACK * max(q*k, f)."""
    vr = cell["VARIANCE_RELATIONSHIPS"]
    return vr["VAR_FALLBACK"] * max(vr["q"] * vr["k"], f)


def validate(manifest: dict) -> dict:
    cells = manifest["CELLS"]
    ids = [c["CELL_ID"] for c in cells]
    assert len(ids) == len(set(ids)), "duplicate CELL_ID"
    # schema
    schema_ok = all(all(k in c for k in REQUIRED_FIELDS) for c in cells)
    # oracle / label validity: classification is a pure function of grid and size multiplier;
    # oracle counts positive; sample sizes monotone in the multiplier within a (design, variant, k, q, stress)
    labels_ok = all(
        (c["EXPECTED_CLASSIFICATION"] == (SIZE_MULT[c["SIZE_MULTIPLIER"]] if c["GRID"] == "3A" else "BOUNDARY_NO_REQUIREMENT"))
        and c["N_ORACLE_80"] > 0 and c["SAMPLE_SIZE"]["COUNT"] > 0
        and (c["ROLE"] == "STRESS_REGRESSION") == (c["GRID"] == "3B")
        for c in cells)
    groups: dict = {}
    for c in cells:
        key = (c["DESIGN_ID"], c["VARIANT_ID"], c["STRESS"], c["VARIANCE_RELATIONSHIPS"]["k"], c["VARIANCE_RELATIONSHIPS"]["q"], c["TRUE_EFFECT"])
        groups.setdefault(key, []).append((c["SIZE_MULTIPLIER"], c["SAMPLE_SIZE"]["COUNT"]))
    monotone_ok = all(sorted(g) == sorted(g, key=lambda x: x[0]) and all(a[1] <= b[1] for a, b in zip(sorted(g), sorted(g)[1:])) for g in groups.values())
    # 3B candidate invariance: the floor must not bind in any 3B cell
    dependent = [c["CELL_ID"] for c in cells if c["GRID"] == "3B"
                 and len({round(var_planning(c, f), 12) for f in manifest["CANDIDATE_FLOORS"]}) != 1]
    # seeds
    ranges = sorted((c["SEED_RANGE"]["STAGE_B"][0], c["SEED_RANGE"]["STAGE_B"][1], c["CELL_ID"]) for c in cells)
    overlaps = [(a[2], b[2]) for a, b in zip(ranges, ranges[1:]) if b[0] <= a[1]]
    prefix_ok = all(c["SEED_RANGE"]["STAGE_A"][0] == c["SEED_RANGE"]["STAGE_B"][0]
                    and c["SEED_RANGE"]["STAGE_A"][1] < c["SEED_RANGE"]["STAGE_B"][1] for c in cells)
    sizes_ok = all(c["SEED_RANGE"]["STAGE_A"][1] - c["SEED_RANGE"]["STAGE_A"][0] + 1 == STAGE_A
                   and c["SEED_RANGE"]["STAGE_B"][1] - c["SEED_RANGE"]["STAGE_B"][0] + 1 == STAGE_B for c in cells)
    out = {"CELLS": len(cells), "SCHEMA_VALID": schema_ok, "ORACLE_LABELS_VALID": labels_ok and monotone_ok,
           "CELLS_3B": sum(1 for c in cells if c["GRID"] == "3B"),
           "THREE_B_CANDIDATE_INVARIANT": not dependent, "THREE_B_FLOOR_DEPENDENT_CELLS": dependent,
           "STAGE_A_PREFIX_OF_STAGE_B": prefix_ok, "RANGE_SIZES_OK": sizes_ok,
           "PAIRWISE_DISJOINT": not overlaps, "OVERLAPS": overlaps, "MIN_SEED": ranges[0][0], "MAX_SEED": ranges[-1][1]}
    out["FREEZE_OK"] = all([schema_ok, labels_ok, monotone_ok, not dependent, prefix_ok, sizes_ok, not overlaps])
    return out


if __name__ == "__main__":
    m = build()
    v = validate(m)
    if not v["FREEZE_OK"]:
        raise SystemExit(f"FREEZE_FAIL: {v}")
    m["MANIFEST_VALIDATION"] = v
    OUT.write_text(json.dumps(m, indent=1) + "\n")
    print(json.dumps(v, indent=1))
