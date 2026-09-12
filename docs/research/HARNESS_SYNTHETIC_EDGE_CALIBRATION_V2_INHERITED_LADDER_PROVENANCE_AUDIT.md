# V2 inherited-detection-ladder provenance audit (pre-outcome, no result data used)

**This is an audit, not an implementation.** No inherited-ladder mapping is
implemented in this unit. Per the explicit stop condition governing this
audit, the mapping may only be bound as tracked authority once all 33
conclusion ids are mechanically unambiguous from already-frozen pre-outcome
material. That is not the case today (18/33 unambiguous; 15/33 ambiguous —
see below), so this unit stops here.

No V2 result/outcome data was inspected or exists to inspect; this audit
reads only frozen prereg/amendment documents and frozen library code.

## Sources consulted

- V1 frozen prereg: `harness_synthetic_edge_calibration_v1_lib.load_frozen_prereg()`
  — specifically `acceptance` (specificity/sanity_power/small_bands/discovery/
  discovery_diagnosis_priority/detection_floor/materiality) and
  `conclusion_authority` (priority_order and named sub-rules).
- V2 required-coverage map: `harness_synthetic_edge_calibration_v2_rank_policy.frozen_required_coverage_map()`
  (33 entries; only 6 carry an inline numeric `inherited_claim`).
- V2 Amendment_001 text (`docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_PREREG_AMENDMENT_001.md`,
  §5.1 "Explicit map" and §5.2 "Final overall union") — the authoritative
  cell/candidate binding table for all 33 ids.

## Per-conclusion-id table

| conclusion_id | frozen source | rule | class |
|---|---|---|---|
| `NULL_ORACLE_FPR` | `acceptance.specificity.ORACLE_NULL_MODEL_FPR_max=0.05` | Wilson upper ≤ 0.05 | **A** unambiguous |
| `NULL_PER_CANDIDATE_FPR` | none found | no threshold or comparison direction specified anywhere for a per-candidate (not pooled BLIND, not oracle-F03) FPR | **B** ambiguous |
| `NULL_BLIND_FPR` | `acceptance.specificity.BLIND_LIBRARY_NULL_FPR_max=0.10` | Wilson upper ≤ 0.10 | **A** unambiguous |
| `NULL_FALSE_POSITIVE_CONCLUSION` | "union of" the three NULL ids above | depends on `NULL_PER_CANDIDATE_FPR` | **B** ambiguous (inherits #2's gap) |
| `EASY_ORACLE_POWER` | `acceptance.sanity_power.EASY_ORACLE_MODEL_detection_min=0.90` | Wilson lower ≥ 0.90 | **A** unambiguous |
| `EASY_BLIND_USEFUL_DISCOVERY` | `acceptance.discovery.EASY_BLIND_USEFUL_DISCOVERY_min=0.80` | Wilson lower ≥ 0.80 (PASS) / Wilson upper < 0.80 (FAIL) / else INDETERMINATE | **A** unambiguous |
| `EASY_CONCLUSION` | `acceptance.discovery_diagnosis_priority` combining #5+#6 | explicit precedence string; combination of two already-unambiguous verdicts via a fully specified rule | **A** unambiguous |
| `MODERATE_ORACLE_POWER` | `acceptance.sanity_power.MODERATE_ORACLE_MODEL_detection_min=0.70` | Wilson lower ≥ 0.70 | **A** unambiguous |
| `MODERATE_BLIND_USEFUL_DISCOVERY` | `acceptance.discovery.MODERATE_BLIND_USEFUL_DISCOVERY_min=0.50` | Wilson lower ≥ 0.50 | **A** unambiguous |
| `MODERATE_CONCLUSION` | same composite rule as `EASY_CONCLUSION` | — | **A** unambiguous |
| `SMALL_ORACLE_BAND` | `acceptance.small_bands` | HIGH≥0.80 / MODERATE[0.50,0.80) / LOW[0.20,0.50) / VERY_LOW<0.20, whole-interval-required else INDETERMINATE | **A** unambiguous |
| `SMALL_CONCLUSION` | Amendment_001 §5.1: "inherited SMALL oracle-band conclusion" | = `SMALL_ORACLE_BAND` (explicit alias statement in the amendment text) | **A** unambiguous |
| `TINY_NOISY_ORACLE_DIAGNOSTIC` | `acceptance.detection_floor` | VISIBILITY_FLOOR if visibility Wilson upper<0.50; else MODEL_FLOOR if model Wilson upper<0.50; else ABOVE_MEASURED_FLOOR | **A** unambiguous |
| `TINY_NOISY_CONCLUSION` | Amendment_001 §5.1: "inherited TINY_NOISY oracle diagnostic" | = `TINY_NOISY_ORACLE_DIAGNOSTIC` (explicit alias) | **A** unambiguous |
| `NONSTATIONARY_TRAP_ORACLE_SPECIFICITY` | `acceptance.specificity.NONSTATIONARY_TRAP_STRICT_EX_MATERIALITY_detection_max=0.20` | Wilson upper ≤ 0.20 | **A** unambiguous |
| `NONSTATIONARY_TRAP_CONCLUSION` | Amendment_001 §5.1: "inherited TRAP oracle specificity" | = `NONSTATIONARY_TRAP_ORACLE_SPECIFICITY` (explicit alias) | **A** unambiguous |
| `SMALL_2500_SENSITIVITY` | `acceptance.small_bands`, applied to cell `SMALL\|2500` | same banding rule as `SMALL_ORACLE_BAND`, different cell | **A** unambiguous |
| `SMALL_10000_SENSITIVITY` | `acceptance.small_bands`, applied to cell `SMALL\|10000` | same banding rule, different cell | **A** unambiguous |
| `ORACLE_F03_NULL` | Amendment_001 §5.1: "oracle F03 on NULL" | plausibly = `NULL_ORACLE_FPR`, but the amendment does not use the same explicit "inherited X (not a BLIND decision statistic)" alias phrasing it uses for `SMALL_CONCLUSION`/`TINY_NOISY_CONCLUSION`/`TRAP_CONCLUSION` | **B** ambiguous (plausible alias, not explicitly confirmed as such; treating an unstated alias as certain would itself be an inference this audit is instructed not to make) |
| `ORACLE_F03_EASY` | same pattern, cell `EASY\|5000` | plausibly = `EASY_ORACLE_POWER` | **B** ambiguous (same reason) |
| `ORACLE_F03_MODERATE` | same pattern, cell `MODERATE\|5000` | plausibly = `MODERATE_ORACLE_POWER` | **B** ambiguous |
| `ORACLE_F03_SMALL_5000` | same pattern, cell `SMALL\|5000` | plausibly = `SMALL_ORACLE_BAND` | **B** ambiguous |
| `ORACLE_F03_TINY_NOISY` | same pattern, cell `TINY_NOISY\|5000` | plausibly = `TINY_NOISY_ORACLE_DIAGNOSTIC` | **B** ambiguous |
| `ORACLE_F03_TRAP` | same pattern, cell `NONSTATIONARY_TRAP\|5000` | plausibly = `NONSTATIONARY_TRAP_ORACLE_SPECIFICITY` | **B** ambiguous |
| `ORACLE_F03_SMALL_2500` | same pattern, cell `SMALL\|2500` | plausibly = `SMALL_2500_SENSITIVITY` | **B** ambiguous |
| `ORACLE_F03_SMALL_10000` | same pattern, cell `SMALL\|10000` | plausibly = `SMALL_10000_SENSITIVITY` | **B** ambiguous |
| `BLIND_DISCOVERY_EASY` | Amendment_001 §5.1: "EASY BLIND useful-discovery decision" | plausibly = `EASY_BLIND_USEFUL_DISCOVERY`, same unconfirmed-alias caveat | **B** ambiguous |
| `BLIND_DISCOVERY_MODERATE` | same pattern | plausibly = `MODERATE_BLIND_USEFUL_DISCOVERY` | **B** ambiguous |
| `BLIND_DISCOVERY_CONCLUSION` | Amendment_001 §5.1: "union of frozen BLIND useful-discovery decisions" over `EASY\|5000` and `MODERATE\|5000` | per-scenario pieces are unambiguous; no frozen rule found for combining EASY's and MODERATE's decisions into one label | **B** ambiguous |
| `VISIBILITY_FLOOR` | `acceptance.detection_floor` | visibility Wilson upper < 0.50 | **A** unambiguous |
| `MODEL_FLOOR` | `acceptance.detection_floor` | model-detection Wilson upper < 0.50 (given visibility not already the binding floor) | **A** unambiguous |
| `MATERIALITY_ONLY_DIAGNOSTIC` | `acceptance.materiality`: "compare strict-ex-materiality vs strict plus fraction-of-attainable" | describes WHAT to compare, not an explicit pass/fail rule (e.g. is it `STRICT_PASS_EX_MATERIALITY and not STRICT_PASS`? plausible but not stated as a formula) | **B** ambiguous |
| `FINAL_OVERALL_MECHANICAL_CONCLUSION` | `conclusion_authority.priority_order` (9-item list) + `discovery_diagnosis_priority` | precedence order itself is explicit and frozen, but its correct evaluation over ALL scenarios requires the ambiguous inputs above (`NULL_PER_CANDIDATE_FPR`, `MATERIALITY_ONLY_DIAGNOSTIC`, `BLIND_DISCOVERY_CONCLUSION`) | **B** ambiguous (contingent on unresolved inputs) |

## Counts

```
INHERITED_MAPPING_UNAMBIGUOUS_COUNT = 18
INHERITED_MAPPING_AMBIGUOUS_COUNT = 15
INHERITED_MAPPING_MISSING_COUNT = 0
```

`MISSING` is 0 because every id has at least some frozen textual description
somewhere; the issue for the 15 flagged ids is that the description is not
precise/explicit enough to transcribe without inference — which is exactly
the boundary this audit was told to respect.

## Unresolved conclusion_ids (15)

```
NULL_PER_CANDIDATE_FPR
NULL_FALSE_POSITIVE_CONCLUSION
ORACLE_F03_NULL
ORACLE_F03_EASY
ORACLE_F03_MODERATE
ORACLE_F03_SMALL_5000
ORACLE_F03_TINY_NOISY
ORACLE_F03_TRAP
ORACLE_F03_SMALL_2500
ORACLE_F03_SMALL_10000
BLIND_DISCOVERY_EASY
BLIND_DISCOVERY_MODERATE
BLIND_DISCOVERY_CONCLUSION
MATERIALITY_ONLY_DIAGNOSTIC
FINAL_OVERALL_MECHANICAL_CONCLUSION
```

## Why this stops at Section D

18/33 is not 33/33. Per the governing instruction, if even one mapping
requires a new scientific judgment (or, as found here, cannot yet be
confirmed unambiguous without either locating more frozen source material or
making an inference the source text does not itself state), this unit must
stop and report rather than invent, infer a convenient threshold, or bind
anything as tracked pre-outcome authority. Note that most of the 15 flagged
ids look *plausibly* resolvable (8 of them are very likely simple aliases of
already-unambiguous ids, following the exact pattern the amendment text uses
explicitly for 3 sibling ids) — but "very likely" is not the same as "stated
unambiguously in the frozen source," and this audit was explicitly told not
to infer a convenient reading.

## Recommended next step

A dedicated `PRE_OUTCOME_INHERITED_LADDER_METHODOLOGY_AMENDMENT` unit should:
1. Either locate additional frozen V1/V2 source text that explicitly confirms
   the 8 `ORACLE_F03_*` and 2 `BLIND_DISCOVERY_*` aliases (e.g. by asking
   whoever authored Amendment_001 §5.1 whether the omission of the explicit
   "inherited ... (not a BLIND decision statistic)" phrasing for those 10 ids
   was intentional or simply terser prose), and/or
2. Add an explicit prereg amendment defining precisely: the `NULL_PER_CANDIDATE_FPR`
   threshold/comparison, the `MATERIALITY_ONLY_DIAGNOSTIC` formula, and the
   two-scenario combination rule for `BLIND_DISCOVERY_CONCLUSION`,

then re-run this audit; only once it reports 33/33 unambiguous may Section E
(binding the mapping as tracked authority, removing the caller-supplied
`inherited_detection_conclusions` parameter) proceed.
