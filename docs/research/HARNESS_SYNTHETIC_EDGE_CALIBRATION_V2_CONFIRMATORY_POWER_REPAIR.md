# V2 confirmatory power repair — independent review contract

**Status:** `IMPLEMENTATION_COMPLETE_AWAITING_INDEPENDENT_POWER_REPAIR_REVIEW`  
**Unit:** targeted V2 confirmatory-power repair  
**Not:** V3, generic methodology redesign, threshold tuning, or a rescue of the completed canonical V2 RESULT.

Canonical V2 remains CLOSED and immutable. Its mechanical conclusion stays:

`FINAL_MECHANICAL_CONCLUSION = METHODOLOGY_POWER_REPAIR_REQUIRED_BEFORE_B2_06`

This unit restores already pre-outcome-defined V1 confirmatory detection
semantics inside the V2 evaluator so confirmatory power can actually be
measured. It does not remint, reinterpret, or replace the completed RESULT.

## Immutable canonical artifacts

Do not edit, remint, or pretend these are a new V2 run:

```text
RESULT_SHA256         = 761cc9afc59265bfb94afecbd293082c274abf3affce3d9693f463442326c1e0
WORLD_RECORDS_SHA256  = d372eb00d4f6df9b4f8a2b0dcb22b051d95787ddeb8494a3c0efc31561e39821
VISIBILITY_EVIDENCE_SHA256 = 9be8dceb07d8fc43b01ef8630d4ad9f52e7401fd6f095b3c7a5bf364701c8b65
```

## Pre-outcome authority (verified before implementation)

All four required claims are uniquely supported by frozen pre-outcome
authority. `NEW_SCIENTIFIC_CHOICE_REQUIRED = NO`.

1. V1 `MODEL_DETECTED` is the confirmatory detection state:
   `primary_positive AND bootstrap_positive AND placebo_separation`
   (`docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.json`
   `diagnostic_meaning` / `strict_reference_gate`).
2. V1 production evaluation actually executes `prediction_bootstrap` (500
   replicates, 50-row blocks, PCG64 `BOOTSTRAP`+feature) and `placebo_q95`
   (999 era-local permutations, PCG64 `PLACEBO`+feature) in
   `evaluate_production_candidate`.
3. Oracle power historically measures `MODEL_DETECTED`, not `STRICT_PASS`:
   V1 acceptance `EASY_ORACLE_MODEL_detection_min=0.90` /
   `MODERATE_ORACLE_MODEL_detection_min=0.70`; V1 production
   `easy_oracle = _wilson_arm(..., _oracle_model_detected)`;
   Amendment_003 `EASY_ORACLE_POWER` / `MODERATE_ORACLE_POWER` /
   `MODEL_FLOOR` `input_statistic` = `ORACLE F03 MODEL_DETECTED rate`.
4. The `>=0.02` relative-MAE gate remains a separate `STRICT_PASS` /
   `MATERIALITY_ONLY_DIAGNOSTIC` identity. It is not the oracle-power
   detection identity. This repair does not lower 2%.

## What changed

A. V2 inner evaluation no longer hardcodes
   `bootstrap_positive=False` / `placebo_separation=False`. It calls
   `_frozen_v1_confirmatory_pair`, which reuses frozen V1 primitives with
   frozen replicate counts, block length, and RNG namespaces.

B. Invalid confirmatory output maps to V2 `CANDIDATE_NOT_IDENTIFIABLE`
   (`NONFINITE_BOOTSTRAP` / `NONFINITE_PLACEBO`), matching frozen V2
   identifiability policy. Identifiability itself is not redesigned.

C. `CandidateWorldRecord.detected` is `gates["MODEL_DETECTED"]`.
   `EASY_ORACLE_POWER`, `MODERATE_ORACLE_POWER`, `MODEL_FLOOR`, NULL
   detection rates, and SMALL bands therefore consume the pre-outcome
   intended statistic.

D. `MATERIALITY_ONLY_DIAGNOSTIC` now counts `gates["STRICT_PASS"]` vs
   `gates["STRICT_PASS_EX_MATERIALITY"]` rather than treating `detected`
   as STRICT_PASS. The 2% threshold is unchanged. TRAP still uses
   `STRICT_PASS_EX_MATERIALITY`.

## What did not change

- Canonical WORLD_RECORDS / VISIBILITY / RESULT bytes
- 2% materiality threshold
- STRICT_PASS composition
- Wilson EASY >= 0.90 / MODERATE >= 0.70
- Bootstrap/placebo definitions, replicate counts, RNG
- DGP, sample sizes, candidate library, 3200-world plan
- Identifiability rank/design/AE reasons
- No new ARM, reservation, 3200-world run, or RESULT mint

A disposable confirmatory proof in tests demonstrates that the
confirmatory path is reachable. It is not canonical calibration evidence.

## Next required step

`INDEPENDENT_POWER_REPAIR_REVIEW`

Do not create a new reservation/ARM or execute a new 3200-world
calibration until that review authorizes it.
