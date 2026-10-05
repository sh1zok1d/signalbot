"""Build the pre-run freeze amendment V1 and the effective manifest (owner decision 2026-10-04).

The original freeze (62f1a74) and its artifacts are never rewritten. The effective
manifest is the frozen manifest with an EXECUTION_STATUS on every cell: S6 cells are
EXCLUDED_PRE_RUN_DESIGN_INVALID and keep their CELL_ID, seeds and frozen metadata.
"""

from __future__ import annotations

import hashlib
import json

from . import freeze

EXCLUDED_DESIGN = "S6"
EXCLUSION_STATUS = "EXCLUDED_PRE_RUN_DESIGN_INVALID"
EXCLUSION_REASON = "RANDOM_ERA_LOCATION_SHIFT_INCOMPATIBLE_WITH_DECLARED_EVENT_LEVEL_STRATIFIED_SIGN_FLIP"
EXPECTED_ACTIVE = {"TOTAL": 900, "3A": 720, "3B": 180, "EXCLUDED": 168}


def build() -> tuple[dict, dict]:
    record = freeze.verify_freeze()
    manifest = json.loads(freeze.MANIFEST.read_text())
    cells = []
    for c in manifest["CELLS"]:
        c = dict(c)
        if c["DESIGN_ID"] == EXCLUDED_DESIGN:
            c["EXECUTION_STATUS"] = EXCLUSION_STATUS
            c["EXCLUSION_REASON"] = EXCLUSION_REASON
        else:
            c["EXECUTION_STATUS"] = "ACTIVE"
        cells.append(c)
    excluded = sorted(c["CELL_ID"] for c in cells if c["EXECUTION_STATUS"] == EXCLUSION_STATUS)
    active = [c for c in cells if c["EXECUTION_STATUS"] == "ACTIVE"]
    counts = {"TOTAL": len(active), "3A": sum(c["GRID"] == "3A" for c in active),
              "3B": sum(c["GRID"] == "3B" for c in active), "EXCLUDED": len(excluded)}
    if counts != EXPECTED_ACTIVE:
        raise SystemExit(f"STOP: active counts {counts} differ from the owner's expectation {EXPECTED_ACTIVE}")
    effective = {"EFFECTIVE_MANIFEST": "COMPILER_V3_VARIANCE_FLOOR_EFFECTIVE_MANIFEST_V1", "DERIVED_FROM": {
                     "FROZEN_MANIFEST": "docs/research/COMPILER_V3_VARIANCE_FLOOR_GOLDEN_MANIFEST_V1.json",
                     "FROZEN_MANIFEST_SHA256": record["ARTIFACTS"]["docs/research/COMPILER_V3_VARIANCE_FLOOR_GOLDEN_MANIFEST_V1.json"],
                     "ORIGINAL_FREEZE_COMMIT": freeze.ORIGINAL_FREEZE_COMMIT},
                 "CONSTANTS": manifest["CONSTANTS"], "CANDIDATE_FLOORS": manifest["CANDIDATE_FLOORS"],
                 "ACTIVE_COUNTS": counts, "CELLS": cells}
    eff_text = json.dumps(effective, indent=1) + "\n"
    freeze.EFFECTIVE_MANIFEST.write_text(eff_text)
    amendment = {
        "AMENDMENT": "COMPILER_V3_VARIANCE_FLOOR_FREEZE_AMENDMENT_V1", "DATE": "2026-10-04",
        "AUTHORIZED_BY": "owner (S6 blocker recognized as a frozen-design contradiction; EXCLUSION chosen, not redesign)",
        "ORIGINAL_FREEZE": {"COMMIT": freeze.ORIGINAL_FREEZE_COMMIT, "RECORD": str(freeze.FREEZE_RECORD.relative_to(freeze.REPO)),
                            "ARTIFACTS": record["ARTIFACTS"]},
        "ORIGINAL_ARTIFACTS_UNCHANGED": True,
        "A_S6_EXCLUSION": {"STATUS": EXCLUSION_STATUS, "REASON": EXCLUSION_REASON, "DESIGN_ID": EXCLUDED_DESIGN,
                           "EXCLUDED_CELL_COUNT": len(excluded),
                           "EXCLUDED_CELL_IDS_SHA256": hashlib.sha256("\n".join(excluded).encode()).hexdigest(),
                           "EXCLUDED_CELL_IDS": excluded,
                           "NOT_IN": ["3A candidate PASS/FAIL", "floor selection", "3B stress gate", "final aggregation"],
                           "KEPT": "CELL_ID, seeds and frozen metadata retained in the effective manifest for audit; no S6b; S1-S5 unchanged; no renumbering"},
        "B_POWER_SEMANTICS": "for every S1-S5 cell a replicate is REJECT iff two_sided_p < alpha; no sign condition on the estimate; applies to NULL, DELTA_MIN and 2x_DELTA_MIN cells",
        "C_S5_RANDOMIZATION": {"UNIT": "event-level sign-flip over venue-averaged event statistics", "DRAWS": 20000,
                               "P_VALUE": "(1 + extreme_draws) / (1 + 20000)", "STATISTIC": "two-sided by absolute value of the mean",
                               "S3": "unchanged: sign-flip over pairs, 20000 draws, same p-value form"},
        "C_RNG_SUBSTREAMS": {"ALGORITHM": "root = numpy.random.SeedSequence(replicate_seed); data_ss, rand_ss = root.spawn(2); DATA rng = numpy.random.default_rng(data_ss) (child 0); RANDOMIZATION rng = numpy.random.default_rng(rand_ss) (child 1)",
                             "PROPERTIES": ["independent substreams: the data generator's draw count never shifts the randomization sequence",
                                            "one replicate seed -> identical data and identical sign-flip draws",
                                            "candidate floor touches no substream"]},
        "D_COMPILER_FEASIBILITY": {"RULE": "FEASIBLE(f) <=> N_CELL >= N_REQUIRED(VAR_PLANNING(f))",
                                   "VAR_PLANNING": "max(VAR_EXPOSED_ESTIMATE, f * VAR_FALLBACK), VAR_EXPOSED_ESTIMATE = q * VAR_TRUE",
                                   "N_REQUIRED": {"S1": "2*ceil(2*V*(z_{a/2}+z_0.80)^2/d^2) (two-sample t, equal arms)",
                                                  "S2": "as S1",
                                                  "S3": "ceil(V*(z_{a/2}+z_0.80)^2/d^2) (sign-flip over pairs, normal approximation)",
                                                  "S4": "smallest integer G with G >= DEFF*V*(t_{G-1,a/2}+t_{G-1,0.80})^2/(m*d^2), DEFF=1+(m-1)*ICC, m=24",
                                                  "S5": "ceil(V*(z_{a/2}+z_0.80)^2/d^2) (sign-flip over events; venues are measurements)"},
                                   "N_ORACLE_80": "frozen; never recomputed; never a candidate decision input",
                                   "EVALUATION_OUTCOMES": "inaccessible to the compiler"},
        "E_EFFECTIVE_MANIFEST": {"PATH": str(freeze.EFFECTIVE_MANIFEST.relative_to(freeze.REPO)), "ACTIVE_COUNTS": counts},
        "EFFECTIVE_MANIFEST_SHA256": hashlib.sha256(eff_text.encode()).hexdigest(),
        "GENERATOR_DIGESTS": freeze.generator_digests(),
        "OFFICIAL_RUN_AUTHORIZED": False,
    }
    freeze.AMENDMENT.write_text(json.dumps(amendment, indent=2) + "\n")
    return amendment, effective


if __name__ == "__main__":
    a, e = build()
    print(json.dumps({"ACTIVE_COUNTS": e["ACTIVE_COUNTS"], "EXCLUDED": a["A_S6_EXCLUSION"]["EXCLUDED_CELL_COUNT"],
                      "EXCLUDED_IDS_SHA256": a["A_S6_EXCLUSION"]["EXCLUDED_CELL_IDS_SHA256"],
                      "EFFECTIVE_MANIFEST_SHA256": a["EFFECTIVE_MANIFEST_SHA256"]}, indent=1))
