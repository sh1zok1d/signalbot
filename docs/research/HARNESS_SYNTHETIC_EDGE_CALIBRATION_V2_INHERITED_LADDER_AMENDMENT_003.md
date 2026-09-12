# HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY — Amendment_003

## V2 inherited detection-ladder binding (repair of Amendment_002)

**Status: `FROZEN_BEFORE_IMPLEMENTATION` (methodology only; no code consumes
this yet).**

**Supersedes:** `AMENDMENT_002`, which independent review rejected with 4
BLOCKERS, 3 MAJORS and 2 MINORS. Amendment_002 is **not modified** — it is
retained byte-identical as historical evidence of the rejected attempt.

This is a **pre-outcome** repair. No V2 ARM exists, no canonical 3200-world run
has occurred, and no V1 or V2 `RESULT`/`WORLD_RECORDS` artifact exists anywhere
in repository history. No outcome data was inspected, because none exists.

## 1. Why Amendment_002 failed, in one sentence

Amendment_002 derived the inherited ladder from the frozen **prose** prereg
dictionaries while a frozen, SHA256-pinned, **executable** implementation of the
same ladder sat unread in the V1 TCB — and the prose-derived ladder diverged
from the executable one five times, every single time in the permissive
direction.

## 2. Authority precedence (frozen by this amendment)

1. **Frozen SHA256-pinned executable V1 TCB functions**, wherever they directly
   define a scientific rule that prose also describes.
2. **Frozen V2 policy artifacts** (original V2 prereg, Amendment_001) where they
   explicitly and *necessarily* replace a V1 implementation detail — in practice
   this means the identifiability-conditional denominators.
3. **Frozen prose** (`load_frozen_prereg()` dicts, prereg Markdown) where no
   executable authority exists.
4. **Explicit, prospectively-declared deterministic rules newly specified here**,
   only where 1–3 leave a genuine gap.

> Prose may **explain** an executable rule. Prose may **not** silently override
> executable semantics.

### 2.1 The bound executable authority

`scripts/research/harness_synthetic_edge_calibration_v1_lib.py`
(V1 TCB role `lib`; `sha256 = 12230dcad714e3a06d3f57de69b78fedcab088be950af3d06f959366f01d6c51`;
git blob `8142ce5d757851bec6dfd0ca2c0bcc13652d37d7`; 37636 bytes)

| function | line | inputs | outputs | precedence position |
|---|---|---|---|---|
| `mechanical_conclusion()` | 845 | `incomplete_execution`, the 7-verdict tuple, `visibility_wilson_upper`, `model_detection_wilson_upper`, `materiality_only_failure` | the 9 frozen terminal labels | **STAGE 3**, transcribed verbatim |
| `specificity_verdict()` | 809 | Wilson interval, `maximum` | PASS / FAIL / INDETERMINATE | computes every max-type specificity verdict fed to STAGE 3 |
| `power_verdict()` | 817 | Wilson interval, `minimum` | PASS / FAIL / INDETERMINATE | computes every min-type power and discovery verdict fed to STAGE 3 |
| `small_band()` | 825 | Wilson interval | HIGH / MODERATE / LOW / VERY_LOW / INDETERMINATE | computes the SMALL band diagnostics; **not** a STAGE 3 input, matching frozen V1 |

`CONCLUSION_PRIORITY` (line 49) is byte-identical to
`load_frozen_prereg()["conclusion_authority"]["priority_order"]`.
`WILSON_Z = 1.959963984540054`; `PRODUCTION_WORLDS_PER_CELL = 400`.

### 2.2 The bound production call site

`scripts/research/harness_synthetic_edge_calibration_v1_production.py`
(V1 TCB role `production`; `sha256 = 9e784ecdcbd53ae4128d803d9325c8ff0f6db49ce70a0a63b13c4fc6a548a4ed`)

`aggregate_planned_worlds()` (line 2526) calls `mechanical_conclusion()` at line
2612 and publishes the complete verdict tuple at line 2704:

```
oracle_null_specificity   blind_null_specificity   trap_specificity
easy_oracle_power         moderate_oracle_power
easy_blind_useful         moderate_blind_useful
```

**`trap_specificity` is bound.** `trap_v = _spec(trap_ex, TRAP_STRICT_EX_MAX)`
(line 2572) is passed as `trap_specificity` (line 2616), with
`TRAP_STRICT_EX_MAX = 0.20` (line 256). Amendment_002 dropped this input
entirely; that omission is BLOCKER-1 and BLOCKER-2.

`materiality_only` (line 2579) is the frozen aggregate boolean supplied as
`materiality_only_failure`.

The complete relevant frozen behaviour is bound — not only the parts that happen
to be convenient.

## 3. Denominators: what frozen V2 does and does not change

Frozen V1 computes every arm as `len(_cell_records(...))` = all 400 planned
worlds in the cell, with the docstring "Invalid worlds stay in the denominator."

Frozen V2 authority **necessarily replaces** this, and says so explicitly:

- V2 prereg §7: `conditional_detection_rate = candidate_detection_count /
  candidate_identifiable_count`, with `n = candidate_identifiable_count`, and
  **"Do not silently use `planned_worlds` as the detection denominator."**
- V2 prereg §13.3: "then the inherited V1 conclusion ladder, computed on
  **conditional** identifiable denominators (specificity, power, discovery,
  floors, materiality)" — naming all five families.
- V2 prereg §12: "This policy unit only changes **who enters those
  denominators** and adds the coverage gate. It does not reopen those numeric
  detection thresholds."
- V2 prereg §8.2 / Amendment_001 §2.2: BLIND taxonomy denominators are
  `world_valid` worlds with `L > 0`.
- V2 prereg §7: an undefined rate "cannot PASS or FAIL a detection claim"
  (fail-closed).

So Amendment_003 inherits the frozen **operators, thresholds and ladder logic**
verbatim, while computing the inputs on the frozen-V2-mandated denominators.
Every one of the 33 rules names its numerator, denominator, conditioning
population, excluded states, denominator authority and undefined-rate behaviour
in the JSON. There are no implicit denominators.

### 3.1 One direction-of-effect disclosure

`VISIBILITY_FLOOR` is a baseline-level statistic that Amendment_001 §5.1 binds
to "world baseline only (no candidate)", so its V2 denominator is
`world_valid_count` on `EASY|5000`. `WORLD_INVALID` worlds can never be
`GROUND_TRUTH_VISIBLE`, so excluding them **raises** the visibility rate and
makes `VISIBILITY_FLOOR` marginally **less** likely to bind than under V1's
literal arithmetic.

This is disclosed rather than buried. It is not a chosen permissiveness: frozen
V2 explicitly forbids `planned_worlds` denominators, and the residual gap is
bounded by the STAGE 2 world-baseline coverage gate (Wilson lower of
`world_valid / planned` ≥ 0.95) that V1 did not have.

## 4. The final state machine

```
STAGE 1 (V2 precondition — V2 prereg §13.1)
  if not structurally_complete
      -> INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM

STAGE 2 (V2 precondition — V2 prereg §13.2, Amendment_001 §5.2 union)
  elif any required cell/candidate is not ADEQUATE
       (incl. world-baseline coverage on each of the eight cells)
      -> INSUFFICIENT_IDENTIFIABILITY_NO_METHODOLOGY_CLAIM

STAGE 2b (V2-only pre-ladder gate — Amendment_001 §5.1 per-candidate NULL FPR)
  elif aggregated NULL_PER_CANDIDATE_FPR == FAIL
      -> METHODOLOGY_REPAIR_REQUIRED_BEFORE_B2_06
  elif aggregated NULL_PER_CANDIDATE_FPR == INDETERMINATE
      -> CALIBRATION_INDETERMINATE

STAGE 3 (inherited — verbatim transcription of frozen mechanical_conclusion)
  3.1 if FAIL in (oracle_null_specificity, blind_null_specificity,
                  trap_specificity)
          -> METHODOLOGY_REPAIR_REQUIRED_BEFORE_B2_06
  3.2 elif FAIL in (easy_oracle_power, moderate_oracle_power)
          -> METHODOLOGY_POWER_REPAIR_REQUIRED_BEFORE_B2_06
  3.3 elif INDETERMINATE in (oracle_null_specificity, blind_null_specificity,
                             trap_specificity, easy_oracle_power,
                             moderate_oracle_power, easy_blind_useful,
                             moderate_blind_useful)
          -> CALIBRATION_INDETERMINATE
  3.4 elif FAIL in (easy_blind_useful, moderate_blind_useful)
          -> DISCOVERY_BOTTLENECK_BEFORE_B2_06
  3.5 elif visibility_wilson_upper is not None
           and visibility_wilson_upper < 0.50
          -> VISIBILITY_FLOOR
  3.6 elif model_detection_wilson_upper is not None
           and model_detection_wilson_upper < 0.50
          -> MODEL_FLOOR
  3.7 elif materiality_only_failure
          -> MATERIALITY_ONLY_DIAGNOSTIC
  3.8 else
          -> NO_V1_EVIDENCE_OF_DISCOVERY_BOTTLENECK
```

First match wins. Step 3.8 is an unconditional `else`, so the machine is total:
every input state yields exactly one output.

**The division of labour is strict.** V2 (stages 1, 2, 2b) may gate *whether*
the inherited ladder is claimable. V2 may **never** make the inherited ladder
more permissive. Stage 3 is a transcription, not a reinterpretation.

### 4.1 Complete terminal label set — all frozen labels preserved

Amendment_002's generic `CALIBRATION_PASSED` / `CALIBRATION_FAILED` /
`COVERAGE_INADEQUATE` / `STRUCTURALLY_INCOMPLETE` relabelling is **withdrawn**.
It collapsed four distinct frozen scientific conclusions into two generic ones
and destroyed inherited meaning.

| # | terminal label | frozen priority | reached by |
|---|---|---|---|
| 1 | `INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM` | 1 | STAGE 1 |
| — | `INSUFFICIENT_IDENTIFIABILITY_NO_METHODOLOGY_CLAIM` | V2-only | STAGE 2 |
| 2 | `METHODOLOGY_REPAIR_REQUIRED_BEFORE_B2_06` | 2 | STAGE 2b, 3.1 |
| 3 | `METHODOLOGY_POWER_REPAIR_REQUIRED_BEFORE_B2_06` | 3 | STAGE 3.2 |
| 4 | `CALIBRATION_INDETERMINATE` | 4 | STAGE 2b, 3.3 |
| 5 | `DISCOVERY_BOTTLENECK_BEFORE_B2_06` | 5 | STAGE 3.4 |
| 6 | `VISIBILITY_FLOOR` | 6 | STAGE 3.5 |
| 7 | `MODEL_FLOOR` | 7 | STAGE 3.6 |
| 8 | `MATERIALITY_ONLY_DIAGNOSTIC` | 8 | STAGE 3.7 |
| 9 | `NO_V1_EVIDENCE_OF_DISCOVERY_BOTTLENECK` | 9 | STAGE 3.8 |

Frozen V2's `MECHANICAL_STRUCTURAL_INCOMPLETE` is the *identical string* as
frozen V1's priority-1 label, so STAGE 1 needs no new label. All nine frozen
labels plus V2's own identifiability label = 10 states, and the differential
oracle confirms all eight inherited stage-3 labels are reachable.

`passing_does_not_authorize_b2_06 = true` and
`post_outcome_relabel_forbidden = true` apply unchanged.

## 5. The four BLOCKER repairs

### BLOCKER-1 — `trap_specificity` restored to the specificity gate

Frozen step 3.1 tests `FAIL in (oracle_null_specificity,
blind_null_specificity, trap_specificity)`. Amendment_002 tested only a NULL
composite. `NONSTATIONARY_TRAP_STRICT_EX_MATERIALITY_detection_max = 0.20` is
one of the three thresholds under `acceptance.specificity`, and
`conclusion_authority.specificity_failure` maps any specificity failure to
`METHODOLOGY_REPAIR_REQUIRED_BEFORE_B2_06`. The frozen label is preserved
exactly — not renamed.

### BLOCKER-2 — `trap_specificity` restored to the INDETERMINATE tuple

The frozen `required` tuple has **seven** members. Amendment_002 listed four.
`trap_specificity` `INDETERMINATE` now yields `CALIBRATION_INDETERMINATE`,
exactly as frozen.

### BLOCKER-3 — `VISIBILITY_FLOOR` and `MODEL_FLOOR` restored as terminal states

Frozen `mechanical_conclusion` *returns* these labels at priorities 6 and 7,
above `NO_V1_EVIDENCE_OF_DISCOVERY_BOTTLENECK` at 9, and Amendment_001 §5.2
lists "floor … consequences" among what the ladder emits. Amendment_002 demoted
them to non-blocking `floor_label` annotations on a passing verdict. They are
terminal conclusions again, with their frozen consequences attached:

- `visibility_floor`: "comparable negative market result cannot strongly
  establish absence"
- `model_floor`: "repair model/evaluation or carry explicit power caveat"

Statistic, denominator, threshold and operator for each are pinned in the JSON.
Note that the frozen production call site supplies `model_detection_wilson_upper`
from the *same arm* as `EASY_ORACLE_POWER`; Amendment_003 preserves that
identity.

### BLOCKER-4 — `MATERIALITY_ONLY_DIAGNOSTIC` statistic and role restored

Amendment_002 changed both the statistic (to a per-world indicator reported as a
Wilson rate) and the role (asserting it "NEVER governs"). Both are restored:

```
materiality_only_failure := (successes_ex > successes_strict)
                            AND (the shared denominator is complete/ADEQUATE)
```

where `successes_ex = count(STRICT_PASS_EX_MATERIALITY is True)` and
`successes_strict = count(STRICT_PASS is True)`, both on the *same* denominator
(F03-identifiable worlds on `EASY|5000`) — structurally identical to the frozen
`easy_strict_ex` / `easy_strict` arm pair. Strict `>`: equality does not trigger.

The frozen boolean's second leg is literally `easy_strict_ex["n"] ==
PRODUCTION_WORLDS_PER_CELL` (400), meaning "this arm's denominator is the
complete planned cell". Under V2 conditional denominators the literal 400 no
longer applies, so Amendment_003 substitutes the V2 equivalent of denominator
completeness — F03 coverage `ADEQUATE` on `EASY|5000` plus world-baseline
coverage `ADEQUATE`, which STAGE 2 already guarantees. This substitution is
**equal-or-stricter**: under V1 the leg was automatically satisfied on any
structurally complete run, whereas the V2 coverage gate is a real additional
requirement. The successes comparison itself is preserved byte-for-byte.

**The word "diagnostic" in this label does not mean non-governing.** The frozen
executable ladder returns it as a terminal conclusion at priority 8.
`MATERIALITY_FRACTION_OF_ATTAINABLE` and both arms' Wilson intervals are
reported alongside, per `acceptance.materiality`, but reported values do not
alter the boolean.

## 6. MAJOR-1 — the `NULL_PER_CANDIDATE_FPR` coverage conflict, disclosed

Two frozen authorities genuinely disagree:

- **A.** `frozen_required_coverage_map()["NULL_PER_CANDIDATE_FPR"]` requires
  **all ten** F01–F10 `ADEQUATE` on `NULL|5000`; `null_claim_blocked_by_coverage()`
  reinforces this ("Claim-bearing NULL requires adequate coverage for all
  F01–F10").
- **B.** Amendment_001 §5.1 binds the row to "**that one** of F01..F10" and
  §5.2 says "`NULL_PER_CANDIDATE_FPR` for one candidate may be discussed only if
  **that candidate** is `ADEQUATE`."

Amendment_002 silently adopted the looser reading (B) and did not mention the
conflict. Amendment_003 discloses it and honours **both** by splitting the roles
fail-closed:

- an **individual candidate's diagnostic FPR** may be computed and reported when
  that candidate alone is `ADEQUATE` — authority B;
- the **canonical conclusion id** `NULL_PER_CANDIDATE_FPR`, in its governing role
  as the STAGE 2b claimability gate and as a component of
  `NULL_FALSE_POSITIVE_CONCLUSION`, is claimable only when the complete frozen
  required-coverage map for F01–F10 on `NULL|5000` is satisfied — authority A.

The stricter authority governs the governing use; the looser authority governs
only the reported diagnostic. No frozen executable authority contradicts this
split, so no STOP was required.

### 6.1 Why STAGE 2b sits outside the inherited ladder

Frozen `mechanical_conclusion()` has **no** per-candidate NULL input. Injecting
one into its verdict tuple would make the inherited ladder diverge from its own
frozen authority — conservatively, but still a divergence. Placing it at STAGE 2b
instead keeps STAGE 3 bit-exact against the oracle while preserving the V2
addition's full strictness. This is the "explicit, separately documented V2
pre-outcome rule that gates claimability before entering the ladder" carve-out,
and it is the *only* such rule in Amendment_003.

## 7. MAJOR-3 — honest source classification

The bare label `INHERITED_DIRECT` is abolished. Numeric inheritance is now
distinguished from full semantic inheritance:

| source_type | count | meaning |
|---|---|---|
| `INHERITED_EXECUTABLE_DIRECT` | 3 | verbatim transcription of a frozen executable function, governing role and terminal label included |
| `INHERITED_EXECUTABLE_DIRECT_WITH_V2_PRECONDITIONS` | 1 | frozen executable rule verbatim, with V2 gates ahead of it that can only refuse |
| `INHERITED_NUMERIC_WITH_V2_IDENTIFIABILITY_WRAPPER` | 11 | frozen threshold **and** frozen operator, on the frozen-V2-mandated conditional denominator |
| `INHERITED_ALIAS_EXPLICIT` | 3 | alias stated verbatim in Amendment_001 §5.1 |
| `NEWLY_SPECIFIED_V2_ALIAS` | 10 | alias made explicit by pattern-match to Amendment_001's own verbatim aliases; no new threshold, denominator or operator |
| `NEWLY_SPECIFIED_V2_COMBINATION` | 4 | new deterministic combination over frozen inputs |
| `NEWLY_SPECIFIED_V2_PRECONDITION` | 1 | V2 gate with no counterpart in frozen `mechanical_conclusion()`; can only add a refusal |

Every id also carries a `governing_role`:
`GOVERNING_FINAL_STATE_MACHINE` (1), `GOVERNING_VIA_FROZEN_LADDER` (7),
`GOVERNING_TERMINAL_STATE` (3), `GOVERNING_V2_PRECONDITION` (1),
`DIAGNOSTIC_REPORTED_ONLY` (21).

The 21 `DIAGNOSTIC_REPORTED_ONLY` ids are diagnostic **because frozen V1 treats
them that way** — the frozen production payload places SMALL bands, TRUE
discovery rate and the TINY_NOISY floor under `diagnostics`, not under
`verdicts`. Their `INDETERMINATE` therefore does not trigger
`CALIBRATION_INDETERMINATE`, exactly as in frozen V1. No id that frozen V1 reads
as a `verdict` was downgraded.

## 8. Preserved unchanged from Amendment_002

Independent review found these sound; they are carried forward verbatim and were
not redesigned:

- **NULL** — identifiable-evaluation conditioning; `CANDIDATE_NOT_IDENTIFIABLE`
  excluded from both numerator and denominator and never counted as a negative
  detection; hard floor 200; Wilson coverage; reuse of the frozen 0.10 rather
  than inventing a per-candidate number.
- **F03** — `NOT_IDENTIFIABLE` is not an ordinary false negative; coverage
  precedes detection; scenario/N-specific thresholds with no cell borrowing
  another cell's threshold; same-cell aliases.
- **BLIND** — selection among identifiable candidates only; L-stratified
  reporting for every `L = 1..10` plus pooled totals; `L=0` excluded from
  denominators and never credited as successful `NO_DISCOVERY`;
  TRUE/PROXY/FALSE/NO_DISCOVERY taxonomy; pooled-vs-stratified reconciliation;
  `blind_not_claimed_invariant_to_L = true`; **no invented L-specific
  threshold** (Amendment_001 §3 forbids one pre-outcome).

## 9. Verification results (mechanically produced, not asserted)

Differential oracle: a review-only script enumerated the full inherited-ladder
input space — 3⁷ verdict tuples × 4 visibility values × 4 model values × 2
materiality values, with the visibility/model probes including `None` and the
exact boundary `0.50` — and compared Amendment_003 STAGE 3 against frozen
`mechanical_conclusion()` with the V2 stages inert. The script re-verifies the
TCB `sha256` before running and does not modify the TCB.

```
FROZEN_AUTHORITY_SHA256_REVERIFIED       = YES
DIFFERENTIAL_ORACLE_CASES                = 69984
PERMISSIVE_DIVERGENCES                   = 0
CONSERVATIVE_DIVERGENCES                 = 0
INHERITED_TERMINAL_LABELS_UNREACHABLE    = NONE
TOTAL_IDS                                = 33
DUPLICATE_IDS                            = 0
ID_SET_EQUALS_FROZEN_REQUIRED_COVERAGE_MAP = YES
REQUIRED_MACHINE_FIELDS_PRESENT          = 19/19 on all 33
DENOMINATORS_PINNED                      = 28/28 rate-bearing (5 verdict-composites n/a)
UNRESOLVED_RULES                         = 0
EQUALITY_BEHAVIOUR_STATED                = 33/33
COVERAGE_SCOPES_MATCHING_FROZEN_MAP      = 33/33
KNOWN_AMENDMENT_002_PERMISSIVE_DIVERGENCES_FIXED = 5/5
AMENDMENT_002_SUCCESS_LABEL_REMAPS_FIXED = 1
```

Pinned equality behaviour, read off the frozen functions rather than inferred:

| probe | frozen result |
|---|---|
| `specificity_verdict(lower=0.02, upper=0.05, max=0.05)` | `PASS` (upper == max passes) |
| `specificity_verdict(lower=0.05, upper=0.09, max=0.05)` | `INDETERMINATE` (lower == max is not FAIL) |
| `power_verdict(lower=0.90, upper=0.95, min=0.90)` | `PASS` (lower == min passes) |
| `power_verdict(lower=0.85, upper=0.90, min=0.90)` | `INDETERMINATE` (upper == min is not FAIL) |
| `small_band(lower=0.50, upper=0.80)` | `INDETERMINATE` (right edges are strict) |
| `small_band(lower=0.50, upper=0.7999)` | `MODERATE` |
| floor at `upper == 0.50` | does **not** bind (comparison is strict `<`) |

The ten required proof cases, each compared directly against the frozen oracle:

| case | frozen `mechanical_conclusion` | Amendment_003 | Amendment_002 (rejected) |
|---|---|---|---|
| 1 trap specificity FAIL | `METHODOLOGY_REPAIR_REQUIRED_BEFORE_B2_06` | **same** | `CALIBRATION_PASSED` |
| 2 trap specificity INDETERMINATE | `CALIBRATION_INDETERMINATE` | **same** | `CALIBRATION_PASSED` |
| 3 visibility floor only | `VISIBILITY_FLOOR` | **same** | `CALIBRATION_PASSED` |
| 4 model floor only | `MODEL_FLOOR` | **same** | `CALIBRATION_PASSED` |
| 5 materiality-only failure only | `MATERIALITY_ONLY_DIAGNOSTIC` | **same** | `CALIBRATION_PASSED` |
| 6 NULL specificity failure | `METHODOLOGY_REPAIR_REQUIRED_BEFORE_B2_06` | **same** | same |
| 7 EASY blind discovery failure | `DISCOVERY_BOTTLENECK_BEFORE_B2_06` | **same** | same |
| 8 coverage inadequate, else favourable | (V2 precondition) | `INSUFFICIENT_IDENTIFIABILITY_NO_METHODOLOGY_CLAIM` | — |
| 9 structurally incomplete, else favourable | `INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM` | **same** | — |
| 10 everything governing PASS | `NO_V1_EVIDENCE_OF_DISCOVERY_BOTTLENECK` | **same** | `CALIBRATION_PASSED` |

Case 10 exposes a sixth Amendment_002 divergence the review under-counted: an
equal-severity **rename** of the frozen success label. It is also fixed.

## 10. Anti-rescue check

Every Amendment_002 behaviour that could turn a frozen repair-required,
bottleneck, indeterminate, floor or diagnostic terminal into a V2 success state
was enumerated and closed:

| frozen consequence | A002 outcome | A003 outcome |
|---|---|---|
| specificity failure via TRAP | success | frozen repair-required |
| indeterminate via TRAP | success | frozen indeterminate |
| visibility floor | success + annotation | frozen terminal `VISIBILITY_FLOOR` |
| model floor | success + annotation | frozen terminal `MODEL_FLOOR` |
| materiality-only suppression | success + annotation | frozen terminal `MATERIALITY_ONLY_DIAGNOSTIC` |
| frozen success label | renamed `CALIBRATION_PASSED` | frozen `NO_V1_EVIDENCE_OF_DISCOVERY_BOTTLENECK` |

`NEW_PERMISSIVE_DIVERGENCES = 0` (69984-case differential oracle). No final
conclusion remapping. No diagnostic-layer switching. No denominator change that
lowers failure risk without frozen authority — the one denominator change with a
permissive direction of effect (`VISIBILITY_FLOOR`) is mandated by frozen V2
authority and is disclosed in §3.1 with its bounding gate.

## 11. What this amendment does NOT do

- Does not modify the original V2 prereg, Amendment_001, **Amendment_002**, the
  frozen V2 policy fixture, the V2 policy implementation freeze, any V1 TCB
  file, or any production runtime code.
- Does not bind Amendment_003 into production code; `derive_v2_mechanical_conclusions`,
  `mint_v2_result` and `verify_historical_v2_result` are unchanged and
  `inherited_detection_conclusions` remains a caller-supplied parameter.
- Does not create an execution freeze, does not create a V2 ARM, does not run
  the canonical 3200-world grid, does not mint `RESULT`, does not consume
  authority.
- Does not inspect any production outcome (none exist).

## 12. Residual limitation, stated plainly

Amendment_001 §3 holds that a favourable **pooled** BLIND result "is not
sufficient evidence by itself if that behavior is concentrated in reduced-`L`
strata", while simultaneously forbidding the invention of an L-specific
threshold before outcomes are seen ("Inventing one now would be an arbitrary
close-the-finding threshold"). Amendment_003 therefore does **not** invent one.
Consequently `NO_V1_EVIDENCE_OF_DISCOVERY_BOTTLENECK` can be reached on a pooled
BLIND pass whose behaviour is concentrated in low-`L` strata. The frozen
mitigations — mandatory L-stratified reporting, mandatory pooled/stratified
reconciliation, and `blind_not_claimed_invariant_to_L = true` on the RESULT —
remain in force and make the concentration visible. This is an inherited open
question, not something Amendment_003 introduces or closes.

## 13. Complete 33-id canonical table (generated from the JSON)

This table is **generated mechanically from the JSON**, not transcribed by
hand — hand-transcription is precisely the failure mode that produced
Amendment_002. It is a readable index; the thirteen fields omitted here for
width (`source_identity`, `input_statistic`, `numerator`,
`conditioning_population`, `excluded_states`, `denominator_authority`,
`undefined_rate_behaviour`, `equality_behaviour`, `coverage_prerequisite`,
`structural_prerequisite`, `possible_states`, `precedence`, `downstream_use`)
are carried in full by the JSON for every one of the 33 ids.

`src` abbreviations: **IED** = `INHERITED_EXECUTABLE_DIRECT`; **IED+PRE** =
same with V2 preconditions; **INUM+V2** =
`INHERITED_NUMERIC_WITH_V2_IDENTIFIABILITY_WRAPPER`; **IALIAS** =
`INHERITED_ALIAS_EXPLICIT`; **NALIAS** = `NEWLY_SPECIFIED_V2_ALIAS`;
**NCOMB** = `NEWLY_SPECIFIED_V2_COMBINATION`; **NPRE** =
`NEWLY_SPECIFIED_V2_PRECONDITION`.

The 12 governing ids come first, then the 21 ids that frozen V1 itself treats
as diagnostics (frozen V1 publishes them under `diagnostics`, not `verdicts`).

| conclusion_id | src | denominator | thr | operator | role |
|---|---|---|---|---|---|
| `NULL_ORACLE_FPR` | INUM+V2 | F03-identifiable on NULL\|5000 | 0.05 | upper≤thr PASS / lower>thr FAIL | ladder input |
| `NULL_BLIND_FPR` | INUM+V2 | pooled BLIND L>0 on NULL\|5000 | 0.1 | upper≤thr PASS / lower>thr FAIL | ladder input |
| `NONSTATIONARY_TRAP_ORACLE_SPECIFICITY` | INUM+V2 | F03-identifiable on NONSTATIONARY_TRAP\|5000 | 0.2 | upper≤thr PASS / lower>thr FAIL | ladder input |
| `EASY_ORACLE_POWER` | INUM+V2 | F03-identifiable on EASY\|5000 | 0.9 | lower≥thr PASS / upper<thr FAIL | ladder input |
| `MODERATE_ORACLE_POWER` | INUM+V2 | F03-identifiable on MODERATE\|5000 | 0.7 | lower≥thr PASS / upper<thr FAIL | ladder input |
| `EASY_BLIND_USEFUL_DISCOVERY` | INUM+V2 | pooled BLIND L>0 on EASY\|5000 | 0.8 | lower≥thr PASS / upper<thr FAIL | ladder input |
| `MODERATE_BLIND_USEFUL_DISCOVERY` | INUM+V2 | pooled BLIND L>0 on MODERATE\|5000 | 0.5 | lower≥thr PASS / upper<thr FAIL | ladder input |
| `VISIBILITY_FLOOR` | IED | world_valid on EASY\|5000 | 0.5 | upper<0.50 strict | terminal |
| `MODEL_FLOOR` | IED | F03-identifiable on EASY\|5000 | 0.5 | upper<0.50 strict | terminal |
| `MATERIALITY_ONLY_DIAGNOSTIC` | IED | F03-identifiable on EASY\|5000 | — | successes_ex > successes_strict | terminal |
| `NULL_PER_CANDIDATE_FPR` | NPRE | candidate-c-identifiable on NULL\|5000 | 0.1 | upper≤thr PASS / lower>thr FAIL | V2 gate |
| `FINAL_OVERALL_MECHANICAL_CONCLUSION` | IED+PRE | n/a (verdict composite) | — | 10-step state machine (see §4) | final |
| `NULL_FALSE_POSITIVE_CONCLUSION` | NCOMB | n/a (verdict composite) | — | NC>FAIL>IND>PASS | diagnostic |
| `EASY_CONCLUSION` | NCOMB | n/a (verdict composite) | — | NC>pwrFAIL>IND>discFAIL>PASS | diagnostic |
| `MODERATE_CONCLUSION` | NCOMB | n/a (verdict composite) | — | NC>pwrFAIL>IND>discFAIL>PASS | diagnostic |
| `BLIND_DISCOVERY_CONCLUSION` | NCOMB | n/a (verdict composite) | — | NC>FAIL>IND>PASS | diagnostic |
| `SMALL_ORACLE_BAND` | INUM+V2 | F03-identifiable on SMALL\|5000 | bands | frozen `small_band()` | diagnostic |
| `SMALL_2500_SENSITIVITY` | INUM+V2 | F03-identifiable on SMALL\|2500 | bands | frozen `small_band()` | diagnostic |
| `SMALL_10000_SENSITIVITY` | INUM+V2 | F03-identifiable on SMALL\|10000 | bands | frozen `small_band()` | diagnostic |
| `TINY_NOISY_ORACLE_DIAGNOSTIC` | INUM+V2 | world_valid (vis leg) / F03-identifiable (model leg) | 0.5 | upper<0.50 strict | diagnostic |
| `SMALL_CONCLUSION` | IALIAS | F03-identifiable on SMALL\|5000 | bands | alias of `SMALL_ORACLE_BAND` | diagnostic |
| `TINY_NOISY_CONCLUSION` | IALIAS | world_valid (vis leg) / F03-identifiable (model leg) | 0.5 | alias of `TINY_NOISY_ORACLE_DIAGNOSTIC` | diagnostic |
| `NONSTATIONARY_TRAP_CONCLUSION` | IALIAS | F03-identifiable on NONSTATIONARY_TRAP\|5000 | 0.2 | alias of `NONSTATIONARY_TRAP_ORACLE_SPECIFICITY` | diagnostic |
| `ORACLE_F03_NULL` | NALIAS | F03-identifiable on NULL\|5000 | 0.05 | alias of `NULL_ORACLE_FPR` | diagnostic |
| `ORACLE_F03_EASY` | NALIAS | F03-identifiable on EASY\|5000 | 0.9 | alias of `EASY_ORACLE_POWER` | diagnostic |
| `ORACLE_F03_MODERATE` | NALIAS | F03-identifiable on MODERATE\|5000 | 0.7 | alias of `MODERATE_ORACLE_POWER` | diagnostic |
| `ORACLE_F03_SMALL_5000` | NALIAS | F03-identifiable on SMALL\|5000 | bands | alias of `SMALL_ORACLE_BAND` | diagnostic |
| `ORACLE_F03_TINY_NOISY` | NALIAS | world_valid (vis leg) / F03-identifiable (model leg) | 0.5 | alias of `TINY_NOISY_ORACLE_DIAGNOSTIC` | diagnostic |
| `ORACLE_F03_TRAP` | NALIAS | F03-identifiable on NONSTATIONARY_TRAP\|5000 | 0.2 | alias of `NONSTATIONARY_TRAP_ORACLE_SPECIFICITY` | diagnostic |
| `ORACLE_F03_SMALL_2500` | NALIAS | F03-identifiable on SMALL\|2500 | bands | alias of `SMALL_2500_SENSITIVITY` | diagnostic |
| `ORACLE_F03_SMALL_10000` | NALIAS | F03-identifiable on SMALL\|10000 | bands | alias of `SMALL_10000_SENSITIVITY` | diagnostic |
| `BLIND_DISCOVERY_EASY` | NALIAS | pooled BLIND L>0 on EASY\|5000 | 0.8 | alias of `EASY_BLIND_USEFUL_DISCOVERY` | diagnostic |
| `BLIND_DISCOVERY_MODERATE` | NALIAS | pooled BLIND L>0 on MODERATE\|5000 | 0.5 | alias of `MODERATE_BLIND_USEFUL_DISCOVERY` | diagnostic |

## 14. Canonical authority

The complete machine-readable 33-row table is
`docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_INHERITED_LADDER_AMENDMENT_003.json`.
Where this Markdown and that JSON disagree, **the JSON governs**; this file is
exposition. Where the JSON and a **frozen executable V1 TCB function** disagree,
**the frozen function governs** and the JSON is in error and must be repaired —
that precedence is the whole point of this amendment.

## 15. Next required step

`INDEPENDENT_V2_INHERITED_LADDER_AMENDMENT_003_REVIEW`.

Only after that review approves the full 33-id table should a separate
implementation unit modify `derive_v2_mechanical_conclusions` /
`mint_v2_result` / `verify_historical_v2_result` to consume it internally and
remove `inherited_detection_conclusions` as a caller-supplied parameter. A
reviewer is invited to re-run the differential oracle against the frozen TCB
independently; it requires no production execution and no ARM.
