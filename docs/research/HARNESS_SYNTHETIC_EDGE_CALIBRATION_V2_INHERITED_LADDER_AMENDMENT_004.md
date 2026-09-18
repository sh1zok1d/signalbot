# HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY — Amendment_004

## STAGE 2b precedence repair

**Status: `FROZEN_BEFORE_IMPLEMENTATION` (methodology only; no code consumes
this yet).**

**Kind: `PRECEDENCE_COMPOSITION_REPAIR_ONLY`.** This unit changes *where* one
already-specified V2 gate is evaluated inside the composite ladder. It changes
no threshold, no denominator, no statistic, no terminal label and no inherited
priority.

**Amends:** `AMENDMENT_003`, which independent review rejected with exactly one
BLOCKER. Amendment_003 is **not modified** — it is retained byte-identical, and
this amendment supersedes exactly two of its 33 entries.

Pre-outcome: no V2 ARM exists, no canonical 3200-world run has occurred, and no
V1 or V2 `RESULT`/`WORLD_RECORDS` artifact exists anywhere in repository
history. No outcome data was inspected, because none exists.

## 1. What stays closed

Independent review confirmed, and this unit does **not** reopen:

- all four Amendment_002 BLOCKERs — CLOSED;
- all three Amendment_002 MAJORs — CLOSED;
- all 33 conclusion ids machine-executable, all 33 denominators pinned;
- the inherited STAGE 3 ladder exactly reproducing frozen
  `mechanical_conclusion()`.

Those parts are inherited unchanged. 31 of the 33 entries are carried forward
byte-identically; only `FINAL_OVERALL_MECHANICAL_CONCLUSION` and
`NULL_PER_CANDIDATE_FPR` are superseded, and within those two entries only
precedence-describing fields change.

## 2. The defect

Amendment_003 evaluated the aggregated V2 `NULL_PER_CANDIDATE_FPR` gate as a
**STAGE 2b early return**, before the inherited ladder. When that gate was
`INDETERMINATE`, the composite returned `CALIBRATION_INDETERMINATE` (frozen
priority 4) *without ever evaluating* the inherited ladder — replacing stronger
frozen consequences with a weaker one:

| gate | frozen ladder | Amendment_003 composite | frozen priority |
|---|---|---|---|
| `INDETERMINATE` | `METHODOLOGY_REPAIR_REQUIRED_BEFORE_B2_06` | `CALIBRATION_INDETERMINATE` | 2 → 4 |
| `INDETERMINATE` | `METHODOLOGY_POWER_REPAIR_REQUIRED_BEFORE_B2_06` | `CALIBRATION_INDETERMINATE` | 3 → 4 |

No masked case reached a passing state, so B2-06 was never wrongly authorised.
But a definite, actionable frozen finding ("specificity failed; repair required
before B2-06") was permanently recorded as ambiguity, and
`post_outcome_relabel_forbidden = true` makes that irreversible. Amendment_003's
own verification missed it because its oracle held the gate at `PASS` — a
scope limitation its §9 disclosed but whose consequence it did not analyse.

## 3. The repair

The gate is no longer an early return. It is integrated into the inherited
ladder at the frozen priority matching its scientific meaning:

- **`FAIL` → frozen step 3.1**, the specificity-failure stage, at the same
  priority as `oracle_null_specificity`, `blind_null_specificity` and
  `trap_specificity`, yielding `METHODOLOGY_REPAIR_REQUIRED_BEFORE_B2_06`.
- **`INDETERMINATE` → frozen step 3.3**, the required-verdict INDETERMINATE
  tuple, yielding `CALIBRATION_INDETERMINATE` only when no higher-priority
  definitive failure is present.
- **`PASS` →** no additional consequence.

No new scientific priority is created. The existing frozen priority structure is
extended mechanically, exactly as it already treats the other specificity
verdicts (FAIL at 3.1, INDETERMINATE at 3.3).

```
STAGE 1 (V2 precondition — V2 prereg §13.1)          [UNCHANGED]
  if not structurally_complete
      -> INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM

STAGE 2 (V2 precondition — V2 prereg §13.2, Amendment_001 §5.2 union)  [UNCHANGED]
  elif any required cell/candidate is not ADEQUATE
       (incl. world-baseline coverage on each of the eight cells)
      -> INSUFFICIENT_IDENTIFIABILITY_NO_METHODOLOGY_CLAIM

  [STAGE 2b early return — REMOVED by Amendment_004]

STAGE 3 (inherited frozen ladder, with the V2 gate integrated at its
         corresponding frozen priority)
  3.1 if FAIL in (oracle_null_specificity, blind_null_specificity,
                  trap_specificity, null_per_candidate_gate)
          -> METHODOLOGY_REPAIR_REQUIRED_BEFORE_B2_06
  3.2 elif FAIL in (easy_oracle_power, moderate_oracle_power)
          -> METHODOLOGY_POWER_REPAIR_REQUIRED_BEFORE_B2_06
  3.3 elif INDETERMINATE in (oracle_null_specificity, blind_null_specificity,
                             trap_specificity, easy_oracle_power,
                             moderate_oracle_power, easy_blind_useful,
                             moderate_blind_useful, null_per_candidate_gate)
          -> CALIBRATION_INDETERMINATE
  3.4 elif FAIL in (easy_blind_useful, moderate_blind_useful)
          -> DISCOVERY_BOTTLENECK_BEFORE_B2_06
  3.5 elif visibility_wilson_upper is not None
           and visibility_wilson_upper < 0.50   -> VISIBILITY_FLOOR
  3.6 elif model_detection_wilson_upper is not None
           and model_detection_wilson_upper < 0.50 -> MODEL_FLOOR
  3.7 elif materiality_only_failure            -> MATERIALITY_ONLY_DIAGNOSTIC
  3.8 else                                     -> NO_V1_EVIDENCE_OF_DISCOVERY_BOTTLENECK
```

Because definitive `FAIL` states are evaluated at 3.1 and 3.2 — strictly before
the INDETERMINATE tuple at 3.3 — a definitive frozen failure now always
dominates an `INDETERMINATE` V2 wrapper. That is the whole repair.

### 3.1 Missing evidence is never converted into a scientific FAIL

The aggregated gate can only be `NOT_CLAIMABLE` when some F01–F10 candidate on
`NULL|5000` is not `ADEQUATE` — which STAGE 2 has already refused, since its
Amendment_001 §5.2 union requires all ten on that cell. After STAGE 2 the gate
is therefore exactly one of `PASS` / `FAIL` / `INDETERMINATE`. STAGE 1 and
STAGE 2 remain fail-closed and unchanged; insufficient evidence still yields
`INSUFFICIENT_IDENTIFIABILITY_NO_METHODOLOGY_CLAIM`, never a scientific
failure verdict.

## 4. Verification (mechanically produced)

A fresh composite oracle enumerates the V2 gate as `PASS`/`FAIL`/`INDETERMINATE`
against the complete frozen verdict space — 3 gate states × 3⁷ verdict tuples ×
8 visibility probes × 8 model probes × 2 materiality states, with the floor
probes including `None`, `0.0`, `0.30`, `0.4999`, `0.50`, `0.5001`, `0.80` and
`1.0`. Severity is derived mechanically from the frozen `CONCLUSION_PRIORITY`
tuple, not hand-assigned. The script re-verifies the TCB `sha256` before running
and modifies nothing.

```
COMPOSITE_ORACLE_CASES                 = 839808
Amendment_003 masked stronger frozen   = 243072
Amendment_004 MASKED_STRONGER_FROZEN   = 0
Amendment_004 AUTHORIZED_CONSERVATIVE  = 83456
terminal labels unreachable under A004 = NONE

INHERITED_LADDER_ORACLE_CASES            = 279936   (gate = PASS)
INHERITED_LADDER_EXACT_LABEL_DIVERGENCES = 0        (no Amendment_003 regression)

ADVERSARIAL_CASES_10_10_PASS = 10/10
```

**Reconciliation with the review's counts.** The review reported 118,098 cases
with 34,182 masked and 11,736 conservative; this unit reports 839,808 / 243,072
/ 83,456. The absolute numbers differ only because the floor probe set is larger
here (64 floor pairs versus 9; 839808 / 118098 = 64/9 exactly). The
*proportions* are identical to six decimal places — masking 0.289438 in both,
conservative 0.099375 in both. The two enumerations describe the same defect at
the same density, and post-repair masking is 0 in both.

The 83,456 remaining differences from the bare frozen ladder are all
**strictly conservative** — the V2 gate making the result stricter, which is the
prospectively authorised V2 addition. None is a downgrade.

### 4.1 The ten required adversarial cases

| # | inputs | Amendment_004 | Amendment_003 was |
|---|---|---|---|
| 1 | gate=IND, trap FAIL | `METHODOLOGY_REPAIR_REQUIRED_BEFORE_B2_06` | `CALIBRATION_INDETERMINATE` |
| 2 | gate=IND, oracle NULL FAIL | `METHODOLOGY_REPAIR_REQUIRED_BEFORE_B2_06` | `CALIBRATION_INDETERMINATE` |
| 3 | gate=IND, blind NULL FAIL | `METHODOLOGY_REPAIR_REQUIRED_BEFORE_B2_06` | `CALIBRATION_INDETERMINATE` |
| 4 | gate=IND, EASY power FAIL | `METHODOLOGY_POWER_REPAIR_REQUIRED_BEFORE_B2_06` | `CALIBRATION_INDETERMINATE` |
| 5 | gate=IND, MODERATE power FAIL | `METHODOLOGY_POWER_REPAIR_REQUIRED_BEFORE_B2_06` | `CALIBRATION_INDETERMINATE` |
| 6 | gate=IND, no definitive failures | `CALIBRATION_INDETERMINATE` | same |
| 7 | gate=FAIL, all else PASS | `METHODOLOGY_REPAIR_REQUIRED_BEFORE_B2_06` | same |
| 8 | gate=PASS, all PASS, no floors/materiality | `NO_V1_EVIDENCE_OF_DISCOVERY_BOTTLENECK` | same |
| 9 | gate=IND, visibility floor triggers | `CALIBRATION_INDETERMINATE` | same |
| 10 | gate=IND, materiality-only true | `CALIBRATION_INDETERMINATE` | same |

Cases 9 and 10 confirm the frozen ordering is respected in the other direction
too: the INDETERMINATE stage (frozen priority 4) correctly precedes the floors
(6, 7) and materiality (8), so an `INDETERMINATE` gate does not let a floor or
materiality terminal be reported instead.

### 4.2 Scope proof

A field-level diff against Amendment_003 confirms the change is precedence-only:

```
entries superseded                 = 2   (FINAL_OVERALL..., NULL_PER_CANDIDATE_FPR)
entries inherited unchanged        = 31
fields changed in FINAL_OVERALL... = operator, precedence, source_identity,
                                     amendment_004_change
fields changed in NULL_PER_CAND... = precedence, downstream_use, source_identity,
                                     coverage_prerequisite, amendment_004_change
all 33 thresholds                  unchanged
all 33 denominators                unchanged
all 33 conditioning populations    unchanged
all 33 source classifications      unchanged
all 33 governing roles             unchanged
terminal label set (10 states)     unchanged
STAGE 1 / STAGE 2                  unchanged
low-L rule                         unchanged
```

## 5. MINOR-1 — materiality direction-of-effect disclosure

Amendment_003 §3.1 is titled "**One** direction-of-effect disclosure" and
discloses only `VISIBILITY_FLOOR`. At least one more case exists. Correcting the
record here, without editing Amendment_003 and without touching the statistic:

Conditioning the materiality comparison on F03-identifiable worlds (instead of
V1's all-400 planned-world aggregation) is **permissive-or-neutral** for
`MATERIALITY_ONLY_DIAGNOSTIC`. Removing a world from the conditioning population
either removes a world that is `STRICT_PASS_EX_MATERIALITY` but not
`STRICT_PASS`, shrinking `successes_ex − successes_strict` by one, or removes a
world that is both or neither, leaving the difference unchanged. The difference
can therefore only shrink or stay equal, so the frozen boolean
(`successes_ex > successes_strict`) can only become **harder** to satisfy, never
easier — the same direction as the already-disclosed visibility-floor effect.

This is nevertheless required, not chosen: V2 prereg §7 forbids `planned_worlds`
as a detection denominator and §13.3 explicitly names materiality among the
families the inherited ladder must compute on conditional identifiable
denominators. The residual gap is bounded by the STAGE 2 coverage gate, which
requires at least `HARD_FLOOR_IDENTIFIABLE` (200) F03-identifiable worlds on
`EASY|5000` plus world-baseline Wilson lower ≥ 0.95 — neither of which V1
required. The statistic, its threshold and its denominator are unchanged.

## 6. MINOR-2 — NULL authority disclosure

Amendment_003 characterised the `NULL_PER_CANDIDATE_FPR` coverage conflict as
frozen map versus Amendment_001 prose. More precisely, the tension is between
the frozen map's structured `candidates` field (all ten — what the executable
`required_coverage_for_conclusion()` enforces) and the frozen map's **own `note`
field** plus Amendment_001 §5.1/§5.2:

> "each candidate's per-candidate FPR requires that candidate ADEQUATE; bundled
> `NULL_FALSE_POSITIVE_CONCLUSION` still requires all ten"

Amendment_003 omitted the map's own note. The resolution — per-candidate
diagnostic under that candidate's own adequacy; canonical governing use
requiring all ten — is therefore supported by **three** frozen authorities, not
two, and by conservative deference to the stricter executable function. The
resolution is unchanged and is strengthened, not weakened. Documentation only.

## 7. Low-L residual — unchanged

Amendment_001 §3 provides no deterministic rule for turning low-`L`
concentration into a governing PASS/FAIL/INDETERMINATE decision, and explicitly
forbids inventing an L-specific threshold before outcomes are seen. Independent
review confirmed this and concluded the limitation does not block
implementation. Amendment_004 therefore does **not** invent a low-L gate and
does **not** alter the Amendment_003 disclosure. L-stratified reporting,
pooled/stratified reconciliation and `blind_not_claimed_invariant_to_L = true`
remain in force.

## 8. One evidence, one result

For fixed authenticated aggregate evidence plus the frozen V1 TCB, the original
V2 prereg, Amendment_001, Amendment_003 and this amendment, exactly one terminal
result follows. The composite is a total function — every branch condition is
deterministic, 3.8 is an unconditional `else`, and the oracle assigns exactly
one label to each of the 839,808 enumerated input states. There is no caller
judgment, no optional precedence and no post-hoc relabel;
`post_outcome_relabel_forbidden = true` and
`passing_does_not_authorize_b2_06 = true` apply unchanged.

## 9. What this amendment does NOT do

- Does not modify the original V2 prereg, Amendment_001, Amendment_002,
  **Amendment_003**, the frozen V2 policy fixture, the V2 policy implementation
  freeze, any V1 TCB file, the production driver/runtime, or the production
  tests.
- Does not change any threshold, denominator, identifiability rule, BLIND rule,
  F03 rule, floor rule, the materiality statistic, any frozen terminal label, or
  any inherited priority.
- Does not bind any amendment into production code and does not remove the
  caller-supplied `inherited_detection_conclusions` parameter.
- Does not create a production freeze or ARM, does not run the canonical 3200
  worlds, does not mint `RESULT`, does not consume authority.

## 10. Canonical authority

The machine-readable overlay is
`docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_INHERITED_LADDER_AMENDMENT_004.json`.
It carries the two superseded entries in full plus an explicit
`inherited_unchanged_from_amendment_003` list of the other 31 ids. For those 31,
**Amendment_003's JSON remains the canonical authority**. Where this Markdown
and the JSON disagree, the JSON governs. Where the JSON and a frozen executable
V1 TCB function disagree, the frozen function governs and the JSON is in error.

## 11. Next required step

`INDEPENDENT_AMENDMENT_004_PRECEDENCE_REVIEW`.

A reviewer is invited to rebuild the composite oracle independently — enumerate
the gate as `PASS`/`FAIL`/`INDETERMINATE`, derive severity from the frozen
`CONCLUSION_PRIORITY` tuple, and confirm that masked stronger frozen
consequences are zero. It requires no production execution and no ARM.
