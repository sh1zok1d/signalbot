# HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY — Amendment_002

## V2 inherited detection-ladder binding

**Status: `FROZEN_BEFORE_IMPLEMENTATION` (methodology only; no code consumes this yet).**

This amendment exists because the provenance audit
(`docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_INHERITED_LADDER_PROVENANCE_AUDIT.md`)
found that only 18 of the 33 required-coverage-map conclusion ids
(`frozen_required_coverage_map()`) were mechanically unambiguous from
already-frozen V1/V2 authority; the remaining 15 lacked either an explicit
numeric threshold or an explicit combination/alias rule, even though every
one of them had *some* frozen textual description. Per the governing stop
condition on that audit, no mapping was bound as authority until this
amendment resolved every one of the 15.

This is a **pre-outcome** amendment: no production outcomes exist to inspect
(no real V2 ARM, no canonical 3200-world run has ever occurred), and none
were consulted while drafting this. It does not modify the original V2
prereg, Amendment_001, the frozen V2 policy fixture, the V2 policy
implementation freeze, or any V1 scientific TCB file — all remain
byte-identical, verified by `git diff` before this commit.

## Governing principle applied throughout

For every one of the 15 ids, this amendment used, in strict order of
preference:

1. an already-frozen V1 numeric threshold (from `load_frozen_prereg()["acceptance"]`),
   applied to the V2 cell/candidate binding Amendment_001 already declares
   for that id — **zero new numbers were invented** where a frozen number
   already existed for the underlying quantity;
2. an already-frozen V2 coverage/identifiability requirement
   (`frozen_coverage_thresholds_flat()`, `HARD_FLOOR_IDENTIFIABLE`,
   `WORLD_VALID_RATE_MIN_WILSON_LOWER`, L-stratification, `blind_not_claimed_invariant_to_L`);
3. an already-frozen precedence rule (`load_frozen_prereg()["conclusion_authority"]["priority_order"]`,
   `["acceptance"]["discovery_diagnosis_priority"]`, and V2's own
   `mechanical_conclusion_v2` precedence: structural incompleteness >
   insufficient identifiability > inherited ladder);
4. only where none of the above fully specified the combination logic, an
   **explicit, prospectively-declared, deterministic conjunction/disjunction
   rule** — every such case is labeled `NEWLY_SPECIFIED_V2_COMBINATION` or
   `NEWLY_SPECIFIED_V2_ALIAS` below and its reasoning is given in full, so a
   reviewer can verify no numeric threshold was invented and no discretion
   remains.

Every rule below fails closed: insufficient coverage always yields
`NOT_CLAIMABLE`, never a silent `PASS`. No rule inspects, depends on, or was
tuned against any production outcome (none exist).

## PASS / FAIL / NOT_CLAIMABLE / INDETERMINATE / DIAGNOSTIC semantics

- `NOT_CLAIMABLE` — the coverage/identifiability prerequisite for this id's
  cell/candidate(s) is not `ADEQUATE`. No detection statement is made.
  Strictly dominates PASS/FAIL/INDETERMINATE (coverage-before-detection,
  already frozen).
- `PASS` — coverage is `ADEQUATE` and the frozen Wilson-bounded criterion is
  met.
- `FAIL` — coverage is `ADEQUATE` and the frozen Wilson-bounded criterion is
  definitively not met (the wrong side of the interval, not merely
  straddling it).
- `INDETERMINATE` — coverage is `ADEQUATE`, but the relevant Wilson interval
  straddles the threshold (or, for banded ids, does not fit entirely inside
  one band) — "no binary methodology claim" (already frozen wording).
- `DIAGNOSTIC` — used only for `MATERIALITY_ONLY_DIAGNOSTIC`: a reported
  value that never participates in any PASS/FAIL/NOT_CLAIMABLE/INDETERMINATE
  computation of any other id (already-frozen non-governing role).

## Resolution of the 15 unresolved ids

### 1–2. `NULL_PER_CANDIDATE_FPR`, `NULL_FALSE_POSITIVE_CONCLUSION`

**`NULL_PER_CANDIDATE_FPR`** (evaluated independently for each of F01..F10 on
`NULL|5000`): `source_type = NEWLY_SPECIFIED_V2_COMBINATION`. No frozen
per-candidate (non-pooled, non-oracle) NULL FPR threshold exists. This
amendment reuses the existing frozen `BLIND_LIBRARY_NULL_FPR_max = 0.10`
(`acceptance.specificity`) applied per-candidate rather than pooled — this is
the more conservative (stricter) of the two existing frozen NULL thresholds
to reuse here (the pooled `ANY_EDGE_DECLARED` rate is, by construction, ≥ any
single candidate's own detection rate, so binding each individual candidate
to the same 0.10 ceiling is at least as strict as what the pooled bound
alone implies), and it invents no new number.

- Denominator: `candidate_identifiable_count[c]` on `NULL|5000` (evaluations
  where the candidate is `CANDIDATE_IDENTIFIABLE`).
- Statistic: Wilson upper bound of `candidate_detection_count[c] / candidate_identifiable_count[c]`.
- Coverage prerequisite: candidate `c` `ADEQUATE` on `NULL|5000` per the
  existing 80-entry coverage table (Amendment_001: "may be discussed only if
  that candidate is `ADEQUATE`"). If not `ADEQUATE`: `NOT_CLAIMABLE` — an
  insufficiently-covered candidate never silently counts as `PASS`.
- PASS if Wilson upper ≤ 0.10; FAIL if Wilson lower > 0.10; INDETERMINATE
  otherwise (straddles 0.10).

**`NULL_FALSE_POSITIVE_CONCLUSION`**: `source_type = NEWLY_SPECIFIED_V2_COMBINATION`.
Amendment_001 §5.2 already freezes the coverage side ("the bundled
`NULL_FALSE_POSITIVE_CONCLUSION` still requires all ten"), so this amendment
only needs to state the combination:
- `NOT_CLAIMABLE` if any of: `NULL_ORACLE_FPR`, `NULL_BLIND_FPR`, or any of
  the ten `NULL_PER_CANDIDATE_FPR(c)` is `NOT_CLAIMABLE`.
- Else `FAIL` if any of the three (oracle, blind, all ten per-candidate) is
  `FAIL`.
- Else `INDETERMINATE` if any is `INDETERMINATE`.
- Else `PASS` (all three components, including all ten per-candidate
  statements, are `PASS`).
- Precedence within this rule: `NOT_CLAIMABLE` > `FAIL` > `INDETERMINATE` >
  `PASS` (any missing coverage or any definite failure dominates; matches
  the frozen coverage-before-detection and specificity-failure-first
  ordering).

### 3–10. `ORACLE_F03_*` (8 ids)

`source_type = NEWLY_SPECIFIED_V2_ALIAS` for all eight. Amendment_001's own
table already states, verbatim, for three sibling ids in the same table —
`SMALL_CONCLUSION` = "inherited SMALL oracle-band conclusion (not a BLIND
decision statistic)", `TINY_NOISY_CONCLUSION` = "inherited TINY_NOISY oracle
diagnostic (...)", `NONSTATIONARY_TRAP_CONCLUSION` = "inherited TRAP oracle
specificity" — that a `_CONCLUSION`-style id which names the same cell and
the same sole required candidate (`{F03}`) as an already-defined oracle
diagnostic id **is** that diagnostic, restated. The eight `ORACLE_F03_*` ids
follow the exact same pattern (same cell, same `{F03}` candidate,
"oracle F03 on `<cell>`" reading as "the oracle F03 diagnostic already
defined for this cell"). This amendment makes that alias explicit and
binding rather than merely plausible:

| id | = | cell | rule reused |
|---|---|---|---|
| `ORACLE_F03_NULL` | `NULL_ORACLE_FPR` | `NULL\|5000` | Wilson upper ≤ 0.05 |
| `ORACLE_F03_EASY` | `EASY_ORACLE_POWER` | `EASY\|5000` | Wilson lower ≥ 0.90 |
| `ORACLE_F03_MODERATE` | `MODERATE_ORACLE_POWER` | `MODERATE\|5000` | Wilson lower ≥ 0.70 |
| `ORACLE_F03_SMALL_5000` | `SMALL_ORACLE_BAND` | `SMALL\|5000` | HIGH/MODERATE/LOW/VERY_LOW banding |
| `ORACLE_F03_TINY_NOISY` | `TINY_NOISY_ORACLE_DIAGNOSTIC` | `TINY_NOISY\|5000` | floor rule |
| `ORACLE_F03_TRAP` | `NONSTATIONARY_TRAP_ORACLE_SPECIFICITY` | `NONSTATIONARY_TRAP\|5000` | Wilson upper ≤ 0.20 |
| `ORACLE_F03_SMALL_2500` | `SMALL_2500_SENSITIVITY` | `SMALL\|2500` | banding, N=2500 |
| `ORACLE_F03_SMALL_10000` | `SMALL_10000_SENSITIVITY` | `SMALL\|10000` | banding, N=10000 |

Each has exactly the coverage prerequisite of its aliased id (F03 `ADEQUATE`
on that cell); `NOT_CLAIMABLE` otherwise, consistent with "F03
non-identifiable is not an ordinary false negative" (frozen V2 policy). No
new threshold is introduced by this alias; each id's value is defined to be
byte-identical to its already-unambiguous counterpart's value.

### 11–13. `BLIND_DISCOVERY_EASY`, `BLIND_DISCOVERY_MODERATE`, `BLIND_DISCOVERY_CONCLUSION`

**`BLIND_DISCOVERY_EASY`** = `EASY_BLIND_USEFUL_DISCOVERY`;
**`BLIND_DISCOVERY_MODERATE`** = `MODERATE_BLIND_USEFUL_DISCOVERY`.
`source_type = NEWLY_SPECIFIED_V2_ALIAS` (same reasoning as the `ORACLE_F03_*`
ids: Amendment_001 already names these "EASY/MODERATE BLIND useful-discovery
decision", which is exactly what `EASY_BLIND_USEFUL_DISCOVERY`/
`MODERATE_BLIND_USEFUL_DISCOVERY` already define). Both inherit, unchanged,
the frozen V2 BLIND semantics already in force: candidate competition only
among `CANDIDATE_IDENTIFIABLE` candidates (`select_blind`), L-stratified
reporting with `L=0` excluded from the BLIND-eligible denominator and never
credited as `NO_DISCOVERY` (per Amendment_001 MINOR-1), pooled-vs-L-stratum
reconciliation required, and `blind_not_claimed_invariant_to_L = true` (a
BLIND statement is a property of the pooled L>0 population on that cell, not
claimed to hold uniformly across every L stratum). Coverage prerequisite:
full library `{F01..F10}` `ADEQUATE` on that cell (already frozen in
Amendment_001 §5.1/§5.2).

**`BLIND_DISCOVERY_CONCLUSION`** (`EASY|5000` and `MODERATE|5000` combined):
`source_type = NEWLY_SPECIFIED_V2_COMBINATION`. Amendment_001 states this is
the "union of frozen BLIND useful-discovery decisions" but does not specify
how to combine two scenario-level decisions into one label. This amendment
defines a deterministic, conservative combination, using exactly the same
qualitative ordering V1's own `discovery_diagnosis_priority` already applies
within a single scenario (a definite failure signal dominates ambiguity,
which dominates a clean pass):

- `NOT_CLAIMABLE` if either `BLIND_DISCOVERY_EASY` or `BLIND_DISCOVERY_MODERATE`
  is `NOT_CLAIMABLE`.
- Else `FAIL` if either is `FAIL`.
- Else `INDETERMINATE` if either is `INDETERMINATE`.
- Else `PASS` (both `PASS`).

### 14. `MATERIALITY_ONLY_DIAGNOSTIC`

`source_type = NEWLY_SPECIFIED_V2_COMBINATION` (this is the id-level
classification recorded in the canonical JSON table, and the one that counts
toward the 15-newly-specified total below — this id is one of the audit's 15
unresolved ids, not one of the 18 already-unambiguous ones). Its
*non-governing role* is `INHERITED_DIRECT` — already frozen verbatim in
`conclusion_authority.materiality_only`: "record gate suppression; no
authorization to change market gate", and
`conclusion_authority.passing_does_not_authorize_b2_06 = true`. What this
amendment newly specifies is the **exact per-world boolean formula**, since
`acceptance.materiality` only names the comparison ("strict-ex-materiality vs
strict plus fraction-of-attainable") without giving the boolean:

```
materiality_only_suppressed(world) :=
    world.oracle_F03.gates.STRICT_PASS_EX_MATERIALITY is True
    AND world.oracle_F03.gates.STRICT_PASS is False
```

i.e. the candidate would have passed the full strict confirmatory gate
*except* for the 2% pooled-MAE materiality requirement specifically. Cell:
`EASY|5000`, candidate `{F03}` (per Amendment_001's binding). Reported as a
rate (with its already-frozen `MATERIALITY_FRACTION_OF_ATTAINABLE` metric)
under coverage prerequisite F03 `ADEQUATE` on `EASY|5000`
(`NOT_CLAIMABLE` otherwise). **Binding governance rule (frozen, restated
here for executability):** `MATERIALITY_ONLY_DIAGNOSTIC` is never read by,
and never changes the output of, `FINAL_OVERALL_MECHANICAL_CONCLUSION` or
any other id's PASS/FAIL/NOT_CLAIMABLE/INDETERMINATE value. It is reported
alongside the final conclusion, never folded into it.

### 15. `FINAL_OVERALL_MECHANICAL_CONCLUSION`

`source_type = NEWLY_SPECIFIED_V2_COMBINATION` for the exact state-machine
wiring; every individual precedence rule and threshold it invokes is
`INHERITED_DIRECT` (V1's own `conclusion_authority.priority_order` and
`acceptance.discovery_diagnosis_priority`, and V2's own already-frozen
`mechanical_conclusion_v2` structural/coverage precedence).

This amendment adopts **five** top-level states — the four the governing
task named at minimum, plus `CALIBRATION_INDETERMINATE` as a distinct fifth
state, since V1's own frozen priority order treats "no binary methodology
claim" as categorically different from both PASS and FAIL, and collapsing it
into either would misrepresent already-frozen V1 methodology:

```
STRUCTURALLY_INCOMPLETE
COVERAGE_INADEQUATE
CALIBRATION_INDETERMINATE
CALIBRATION_FAILED
CALIBRATION_PASSED
```

Deterministic precedence (first matching rule wins; exactly V1's frozen
`priority_order`, compressed onto these five labels, with the specific V1
sub-reason retained as a `sub_status` field so no information is lost):

1. **`STRUCTURALLY_INCOMPLETE`** — if the run is not structurally complete
   (any planned world missing; matches V2's already-frozen
   `MECHANICAL_STRUCTURAL_INCOMPLETE` / V1's `incomplete_execution`).
   `sub_status = INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM`.
2. **`COVERAGE_INADEQUATE`** — else if any cell/candidate required by the
   33-entry required-coverage map (the union table in Amendment_001 §5.2) is
   not `ADEQUATE` (matches V2's already-frozen
   `MECHANICAL_INSUFFICIENT_IDENTIFIABILITY`). `sub_status =
   INSUFFICIENT_IDENTIFIABILITY_NO_METHODOLOGY_CLAIM`.
3. **`CALIBRATION_FAILED`** (specificity) — else if `NULL_FALSE_POSITIVE_CONCLUSION
   == FAIL` (i.e. `NULL_ORACLE_FPR`, `NULL_BLIND_FPR`, or any
   `NULL_PER_CANDIDATE_FPR` is `FAIL`). `sub_status =
   METHODOLOGY_REPAIR_REQUIRED_BEFORE_B2_06`.
4. **`CALIBRATION_FAILED`** (power) — else if `EASY_ORACLE_POWER == FAIL` or
   `MODERATE_ORACLE_POWER == FAIL`. `sub_status =
   METHODOLOGY_POWER_REPAIR_REQUIRED_BEFORE_B2_06`.
5. **`CALIBRATION_INDETERMINATE`** — else if any of
   `NULL_FALSE_POSITIVE_CONCLUSION`, `EASY_ORACLE_POWER`,
   `MODERATE_ORACLE_POWER`, or `BLIND_DISCOVERY_CONCLUSION` is
   `INDETERMINATE` (a required boundary-straddling Wilson interval anywhere
   in the chain). `sub_status = CALIBRATION_INDETERMINATE`.
6. **`CALIBRATION_FAILED`** (discovery bottleneck) — else if
   `BLIND_DISCOVERY_CONCLUSION == FAIL` (specificity and power controlled,
   but useful discovery fails). `sub_status = DISCOVERY_BOTTLENECK_BEFORE_B2_06`.
7. **`CALIBRATION_PASSED`** — else. Attach non-blocking qualifiers, each
   computed independently and none altering this state:
   - `floor_label`: `VISIBILITY_FLOOR` if the frozen `detection_floor` rule's
     visibility Wilson upper < 0.50; else `MODEL_FLOOR` if model Wilson
     upper < 0.50; else `ABOVE_MEASURED_FLOOR`.
   - `materiality_only_diagnostic`: the value from §14, reported, never
     governing.
   - `sub_status = NO_V1_EVIDENCE_OF_DISCOVERY_BOTTLENECK`.

`passing_does_not_authorize_b2_06 = true` and
`post_outcome_relabel_forbidden = true` (both already frozen in V1's
`conclusion_authority`) apply unchanged to `CALIBRATION_PASSED`.

For identical authenticated evidence, this state machine is a pure function
— evaluating it twice on the same `WORLD_RECORDS` always yields the same
five-tuple `(top_level_state, sub_status, floor_label,
materiality_only_diagnostic, per-id table)`. There is no step at which a
human or caller supplies a value.

## Full 33-id canonical table

The complete, canonical, machine-readable table (all 33 ids — the 18
previously-unambiguous plus the 15 resolved above) is
`docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_INHERITED_LADDER_AMENDMENT_002.json`.
That JSON file is the sole authority for inherited-ladder derivation once a
future implementation unit consumes it; this Markdown file is exposition,
not an independent source of truth (if the two ever disagree, the JSON
governs).

## Adversarial self-check

- All 33 ids appear exactly once in the JSON table (verified: `len(table) ==
  33 == len(set(table.keys()))`).
- Zero ids remain unresolved (all 33 rows have a non-null `rule`).
- No rule reads or depends on any production outcome (none exist; every
  rule is a pure function of frozen prereg/amendment literals plus the
  as-yet-hypothetical authenticated `WORLD_RECORDS`).
- No overlapping contradictory precedence: `FINAL_OVERALL_MECHANICAL_CONCLUSION`'s
  7-step ladder is strictly ordered (first match wins), and every
  composite id's own internal precedence (`NOT_CLAIMABLE > FAIL >
  INDETERMINATE > PASS`) is applied consistently everywhere a composite
  appears.
- No threshold is omitted: every id with a numeric criterion cites the exact
  frozen number and comparison direction; ids without one are exactly the
  banding/floor/alias/diagnostic ids, whose exact frozen rule is cited
  instead.
- No prose-only rule survives: every entry in the JSON table has a `rule`
  field written as an executable boolean/threshold expression, not a
  free-text description alone (the free text is retained as `notes`/context
  only).
- `PASS`/`FAIL`/`NOT_CLAIMABLE`/`INDETERMINATE` are deterministic: each is
  defined as a pure function of (a) a coverage verdict already computed by
  frozen V2 coverage functions and (b) a Wilson interval already computed by
  the frozen `wilson_interval` function — both deterministic given fixed
  evidence.
- `FINAL_OVERALL_MECHANICAL_CONCLUSION` is deterministic (strict, exhaustive,
  first-match precedence; every branch condition is itself deterministic).
- Identical aggregate evidence cannot admit two valid final verdicts: every
  rule is a pure function with no free parameter, no caller input, and no
  random/nondeterministic element.

## What this amendment does NOT do

- Does not modify the original V2 prereg, Amendment_001, the frozen V2
  policy fixture, the V2 policy implementation freeze, or any V1 TCB file.
- Does not modify production mint code (`derive_v2_mechanical_conclusions`,
  `mint_v2_result`, etc. are unchanged; `inherited_detection_conclusions`
  remains a caller-supplied parameter in code until a *separate*
  implementation unit wires this table in and removes it).
- Does not create a real V2 ARM and does not run production.
- Does not inspect any production outcome (none exist).

## Next required step

`INDEPENDENT_V2_INHERITED_LADDER_AMENDMENT_REVIEW`. Only after that review
approves the full 33-id table should a separate implementation unit modify
`derive_v2_mechanical_conclusions`/`mint_v2_result`/`verify_historical_v2_result`
to consume it internally and remove `inherited_detection_conclusions` as a
caller-supplied parameter.
