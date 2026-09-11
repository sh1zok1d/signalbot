# HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY — Preregistration

**Status:** `FROZEN_BEFORE_IMPLEMENTATION`  
**Unit ID:** `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY`  
**Unit type:** methodology-only identifiability policy; not a market hypothesis; not a production ARM  
**Base HEAD at design freeze:** `9ab32fc14c50df0c6f1c7ddfe2a8990d2d49c339`  
**Base tree at design freeze:** `8aca4445f4638f678810d64a17de2a253a22763d`  
**Execution status:** `synthetic_execution_authorized = false`

Machine-readable twin: [`HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_PREREG.json`](HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_PREREG.json).

This unit freezes candidate-level non-identifiability **before** any V2 implementation, freeze, ARM, or Monte Carlo. It does not authorize a new production run and does not consume V1 authority.

---

## 0. Purpose

V1 world-validity treated any candidate-augmented rank failure as `WORLD_INVALID`, which forced `INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM` even when the baseline comparison was defined and other candidates were identifiable.

V2 separates:

- whether a **world** can host a candidate-vs-baseline comparison (baseline identifiability);
- whether a **candidate** can be estimated in that world (candidate-augmented identifiability);
- whether detection, once defined, succeeds.

This is methodology calibration, never market evidence. It does not authorize B2-06.

---

## 1. Relation to V1 (permanent)

The canonical V1 production attempt:

```text
EXECUTION_HEAD   = 9ab32fc14c50df0c6f1c7ddfe2a8990d2d49c339
EXECUTION_TREE   = 8aca4445f4638f678810d64a17de2a253a22763d
RUN_IDENTITY     = ac1087b75250a671f4a207defec6d2b606050cd8c2fbcfcd894b6b2876be2565
PLANNED          = 3200
STRUCTURAL       = 3200
V1_WORLD_VALID   = 3087
V1_WORLD_INVALID = 113
RESULT minted    = NO
WORLD_RECORDS    = NO
AUTHORITY consumed = NO
```

Frozen V1 mechanical status, permanently:

```text
INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM
```

No V1 subset is claimable, including the 3087 V1-valid worlds. V1 compute may be used only as diagnostic motivation for writing this policy. It is not V2 evidence, not a V2 RESULT, and not continuity of the failed V1 ARM.

V1 cause class, recorded as motivation only: `EXPECTED_DGP_DEGENERACY`. Expanding-era E2 trains on E1 only. S-dependent candidates `F01`, `F02`, `F03`, `F08` can be identically zero on E1. That is not an OLS bug and not a license to salvage V1.

Do not mint a V1 RESULT. Do not consume V1 ARM in order to close this record. Do not resume the V1 production path as V2.

---

## 2. Hard boundaries

```text
synthetic_execution_authorized = false
real_market_data_access_authorized = false
b2_06_scientific_execution_authorized = false
validation_2025_authorized = false
oos_2026_authorized = false
market_promotion_possible = false
v1_result_mint_authorized = false
v1_subset_claim_authorized = false
v2_production_arm_authorized = false
implementation_exists = false
```

This unit does not change DGP, scenarios, candidate definitions, RNG, world seeds, replicate counts, OLS, the algebraic full-rank rule, visibility/bootstrap/placebo science, multiprocessing, checkpoint trust, mint authentication, historical recomputation, or ARM machinery.

---

## 3. Scientific states

Exactly four scientific states are defined.

### 3.1 `WORLD_VALID`

The baseline design `Y ~ intercept + X1 + X2` is identifiable at every required expanding-era training window (scored eras E2, E3, E4, E5; train = all prior eras). Baseline coefficients and baseline predictions on scored rows are finite.

### 3.2 `WORLD_INVALID`

Baseline is not identifiable at any required scored-era training window, or baseline coefficients/predictions are non-finite, or any other world-level numerical failure makes every candidate-vs-baseline comparison undefined.

If `WORLD_INVALID = YES`:

- no candidate result from that world may enter detection statistics;
- candidates in that world do not increment `candidate_identifiable_count` or `candidate_non_identifiable_count`;
- the world remains in `planned_worlds`.

### 3.3 `CANDIDATE_IDENTIFIABLE`

`WORLD_VALID` and the candidate-augmented design `Y ~ intercept + X1 + X2 + Fj` is full rank at every required scored-era training window, and candidate coefficients/predictions (and any later bootstrap/placebo statistics required to define detection for that candidate) are finite.

### 3.4 `CANDIDATE_NOT_IDENTIFIABLE`

`WORLD_VALID` and the candidate-augmented design is rank-deficient at a required scored-era training window, or that candidate's fit/prediction/bootstrap/placebo path is non-finite, while the baseline remains identifiable.

A candidate-level rank failure does **not** invalidate the world unless the baseline itself is not identifiable.

`CANDIDATE_NOT_IDENTIFIABLE` is undefined on `WORLD_INVALID` worlds. Those worlds are baseline failures, not candidate non-identifiability.

---

## 4. Baseline policy

If the baseline design is rank-deficient at a required scored era:

```text
WORLD_INVALID = YES
```

Reason: the candidate comparison cannot be scientifically defined.

No candidate from that world contributes to `detected_count` or `not_detected_count`. Other worlds continue.

---

## 5. Candidate policy

If baseline is identifiable and one candidate-augmented design is rank-deficient:

```text
candidate state = CANDIDATE_NOT_IDENTIFIABLE
planned_worlds += 1                    # the world remains planned
candidate_non_identifiable_count += 1
```

That candidate contributes to **neither**:

```text
detected_count
not_detected_count
```

Other candidates in the same world continue normally.

`MODEL_DETECTED`, `STRICT_PASS_EX_MATERIALITY`, and `STRICT_PASS` are defined only for `CANDIDATE_IDENTIFIABLE` evaluations. They are not false and not true when the candidate is not identifiable.

Placebo or bootstrap `IncompleteWorld` on an otherwise world-valid baseline, for one candidate, marks that candidate `CANDIDATE_NOT_IDENTIFIABLE`. It does not flip the world to `WORLD_INVALID`.

Visibility uses baseline residuals. Visibility failure that is caused by baseline non-identifiability is a world failure. Visibility invalidity that does not prevent a defined candidate-vs-baseline comparison is recorded on the visibility diagnostic and does not, by itself, recode candidate identifiability.

---

## 6. Full-rank semantics

Preserve the V1 algebraic rule. Do not retune it.

```text
rank < number_of_columns  =>  not identifiable
```

Required rank equals the number of columns in the design actually fitted:

- baseline: 3 (`intercept`, `X1`, `X2`);
- candidate-augmented: 4 (`intercept`, `X1`, `X2`, `Fj`).

Forbidden unless a later unit separately preregisters them:

- pseudo-inverse fallback;
- ridge / other regularization fallback;
- coefficient imputation;
- zero-coefficient assumption for a collinear column;
- arbitrary tolerance relaxation.

Scientific OLS remains unweighted `numpy.linalg.lstsq(..., rcond=None)` with a strict full-rank requirement. Rank may be taken from `numpy.linalg.matrix_rank` or from the `lstsq` rank return; both must agree that a zero column is deficient. No new tolerance is introduced here.

---

## 7. Denominators (frozen)

For every `scenario × N × candidate` report exactly:

```text
planned_worlds
world_valid_count
candidate_identifiable_count
candidate_non_identifiable_count
candidate_detection_count
```

Definitions:

```text
identifiability_rate
  = candidate_identifiable_count / world_valid_count

conditional_detection_rate
  = candidate_detection_count / candidate_identifiable_count
```

If `world_valid_count = 0`, `identifiability_rate` is undefined.  
If `candidate_identifiable_count = 0`, `conditional_detection_rate` is undefined.  
Undefined rates cannot PASS or FAIL a detection claim.

Do **not** silently use `planned_worlds` as the detection denominator.  
Do **not** silently drop non-identifiable cases from reporting.  
Always publish the five counts, even when a rate is undefined.

`candidate_non_identifiable_count + candidate_identifiable_count = world_valid_count` for each candidate. `WORLD_INVALID` worlds are in `planned_worlds - world_valid_count` and are not redistributed into candidate non-identifiability.

Wilson intervals use the same frozen constants as V1:

```text
z = 1.959963984540054
n = world_valid_count                 # for identifiability_rate
n = candidate_identifiable_count      # for conditional_detection_rate
```

---

## 8. Aggregation order (frozen, not ambiguous)

### 8.1 Primary: candidate first, then cell, then scenario

Confirmatory/oracle metrics, per-candidate false-positive metrics, and identifiability coverage are computed **per candidate inside each `scenario|N` cell**, then read by the scenario-level conclusion engine.

Do not average candidates with different identifiability rates into one scenario detection number. That would hide poor coverage.

### 8.2 Secondary: world-level BLIND selection, after candidate identifiability

BLIND search-select-evaluate is a world-level operator. Inside each `WORLD_VALID` world:

1. discard `CANDIDATE_NOT_IDENTIFIABLE` candidates from the selectable set;
2. among remaining identifiable candidates, apply the frozen V1 selector (`STRICT_PASS_EX_MATERIALITY`, max pooled mean AE improvement, tie ascending feature ID);
3. if the selectable set is empty, selection = `NO_CANDIDATE`.

World-level taxonomy rates (`TRUE_DISCOVERY`, `PROXY_DISCOVERY`, `FALSE_DISCOVERY`, `NO_DISCOVERY`, `ANY_EDGE_DECLARED`, `USEFUL_DISCOVERY`) use:

```text
denominator = world_valid worlds with at least one identifiable library candidate
```

Worlds with zero identifiable library candidates are reported separately as `worlds_with_zero_identifiable_candidates`. They are **not** scored as successful `NO_DISCOVERY` for false-positive control. If NULL coverage is ADEQUATE, this count is expected to be near zero; if it is not, the NULL coverage gate fails first.

### 8.3 Scenario conclusions

A scenario-level PASS/FAIL that depends on a candidate may be issued only if that candidate's coverage verdict in that cell is `ADEQUATE`. A scenario-level BLIND conclusion may be issued only if every library candidate required by that conclusion has `ADEQUATE` coverage in that cell.

---

## 9. Coverage / identifiability gate

A high `conditional_detection_rate` with poor identifiability is not successful calibration.

Coverage is judged **before** detection PASS/FAIL. Thresholds below are prospective. They are **not** fitted to V1 observed invalid counts.

### 9.1 Why these numbers (prospective)

The V1 Monte Carlo was sized at 400 worlds/cell so a Wilson 95% interval at `p=0.5` has half-width about 0.049. V2 detection uses `candidate_identifiable_count` as `n`. Coverage must:

1. keep `n` large enough that inherited V1 power/specificity/band decisions remain statistically meaningful;
2. prevent an artificially low false-positive rate by labeling hard evaluations `NOT_IDENTIFIABLE`;
3. acknowledge, from **frozen DGP parameters** (not V1 outcomes), that TINY_NOISY (`target_support=0.025`) and SMALL at N=2500 (E1 width 500) have a structurally higher chance of an all-zero S-gated E1 column than EASY (`target_support=0.20`, E1 width 1000).

Hard floor `candidate_identifiable_count >= 200` keeps Wilson half-width at `p=0.5` no worse than about 0.07, which is the coarsest precision that can still speak to 0.05-scale FPR claims or 0.20-wide SMALL bands. Cells that underwrite PASS/FAIL methodology conclusions get higher rate floors so the Monte Carlo is not silently re-sized.

Wilson decision for coverage:

```text
ADEQUATE iff
  world_valid_count >= 1
  AND candidate_identifiable_count >= 200
  AND identifiability Wilson lower >= cell/candidate minimum

otherwise INSUFFICIENT_IDENTIFIABILITY
```

Coverage has no PASS/FAIL detection meaning. `INSUFFICIENT_IDENTIFIABILITY` is not detection FAIL and not detection PASS. Boundary-straddling identifiability is `INSUFFICIENT_IDENTIFIABILITY` (conservative; does not grant a detection claim).

World-level baseline coverage, every cell:

```text
world_valid_rate = world_valid_count / planned_worlds
ADEQUATE iff Wilson lower(world_valid_rate) >= 0.95
```

Baseline `[1,X1,X2]` is a continuous AR design. A material baseline-failure rate is a world-level identifiability failure, not candidate sparsity.

### 9.2 Frozen identifiability minima (Wilson lower)

`hard_min_identifiable_count = 200` for every candidate cell below.

| Cell | Candidate | Min Wilson lower |
|---|---|---|
| `NULL\|5000` | each of F01..F10 | 0.95 |
| `EASY\|5000` | each of F01..F10 | 0.90 |
| `MODERATE\|5000` | each of F01..F10 | 0.90 |
| `NONSTATIONARY_TRAP\|5000` | each of F01..F10 | 0.90 |
| `SMALL\|5000` | each of F01..F10 | 0.85 |
| `SMALL\|10000` | each of F01..F10 | 0.85 |
| `SMALL\|2500` | F03 | 0.75 |
| `SMALL\|2500` | F01, F02, F08 | 0.65 |
| `SMALL\|2500` | F04, F05, F06, F07, F09, F10 | 0.85 |
| `TINY_NOISY\|5000` | F03 | 0.70 |
| `TINY_NOISY\|5000` | F01, F02, F08 | 0.60 |
| `TINY_NOISY\|5000` | F04, F05, F06, F07, F09, F10 | 0.85 |

NULL 0.95 is an anti-gaming FPR-integrity floor: at `target_support=0.10`, N=5000, E1 occupancy of the trigger is not a sparse-by-design cell. EASY/MODERATE/TRAP 0.90 are sanity-power/specificity cells sized for n=400. SMALL primary and N=10000 0.85 protect band classification precision. SMALL|2500 and TINY_NOISY S-gated floors are lower because those cells are designed with smaller E1 occupancy; they are still high enough that a conditional rate cannot be a handful of worlds.

Do not change these thresholds after a V2 run.

---

## 10. Oracle policy (F03)

F03 is the true synthetic oracle candidate.

Failure to identify F03 because `S` has no variation on a required training window is **not** an ordinary false negative. It does not increment `not_detected_count`. It increments `candidate_non_identifiable_count`.

Oracle performance that may PASS/FAIL:

```text
conditional_detection_rate of F03
  = F03 detections / F03 identifiable worlds
```

is evaluated only if F03 coverage in that cell is `ADEQUATE`.

Excessive F03 non-identifiability fails calibration only through the coverage gate (`INSUFFICIENT_IDENTIFIABILITY`), never by recoding those worlds as `MODEL_DETECTED = false`.

---

## 11. NULL policy

False-positive behavior is evaluated only over identifiable candidate evaluations.

Per-candidate NULL FPR:

```text
P(candidate detection | CANDIDATE_IDENTIFIABLE) on NULL|5000
```

World-level BLIND NULL FPR:

```text
P(ANY_EDGE_DECLARED | WORLD_VALID and at least one identifiable library candidate)
```

Both require ADEQUATE identifiability for **every** of F01..F10 on `NULL|5000` (Wilson lower ≥ 0.95 and identifiable count ≥ 200). If any library candidate fails that coverage gate, the NULL FPR conclusion is `INSUFFICIENT_IDENTIFIABILITY`, not a low-FPR PASS.

The system must not obtain an artificially low false-positive rate by classifying difficult candidates as non-identifiable.

---

## 12. Inherited detection science (unchanged here)

Unless a later full V2 calibration prereg explicitly revises them, V2 inherits V1:

- DGP, scenarios, candidate library, RNG, world identities/seeds;
- expanding-era chronology;
- bootstrap/placebo/visibility replicate counts and block construction;
- gate order and numeric detection/specificity/power/band thresholds;
- materiality 0.02;
- Wilson z.

This policy unit only changes **who enters those denominators** and adds the coverage gate. It does not reopen those numeric detection thresholds.

---

## 13. Mechanical conclusion priority (V2 policy layer)

A future V2 RESULT may emit methodology consequences only in this order:

1. missing/malformed planned worlds, torn checkpoint, or other structural incompleteness → `INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM`;
2. any cell/candidate required by a methodology claim has `INSUFFICIENT_IDENTIFIABILITY` → `INSUFFICIENT_IDENTIFIABILITY_NO_METHODOLOGY_CLAIM`;
3. then the inherited V1 conclusion ladder, computed on **conditional** identifiable denominators (specificity, power, discovery, floors, materiality).

Passing V2 calibration never authorizes B2-06.  
V2 must not claim continuity of RESULT with the failed V1 ARM.

---

## 14. Anti-rescue

Explicitly forbidden:

- deleting sparse worlds;
- changing support probabilities, rho, beta, noise, or N after observing calibration outcomes;
- excluding candidates after seeing detection rates;
- using only the 3087 V1-valid subset;
- converting `CANDIDATE_NOT_IDENTIFIABLE` to FAIL or PASS after results are known;
- changing coverage thresholds after the V2 run;
- minting a V1 RESULT from partial/invalid records;
- silent planned-world detection denominators;
- pseudo-inverse / ridge / imputed-coefficient rescue of rank-deficient designs;
- presenting synthetic calibration as market evidence.

Any scientific change after a V2 outcome opening requires a new version.

---

## 15. Future implementation boundary

This unit does **not** implement runtime behavior.

### 15.1 Minimal expected later implementation changes

- candidate evaluation state (`CANDIDATE_IDENTIFIABLE` / `CANDIDATE_NOT_IDENTIFIABLE`);
- world validity semantics (baseline-only `WORLD_INVALID`);
- aggregation/counting (five frozen counts; split denominators);
- RESULT schema (identifiability rates, coverage verdicts, conditional detection);
- mechanical conclusion logic (`INSUFFICIENT_IDENTIFIABILITY_NO_METHODOLOGY_CLAIM`).

### 15.2 Expected unchanged components

DGP; scenario definitions; candidate definitions; RNG; world seeds; replicate counts; OLS implementation; full-rank criterion; visibility/bootstrap/placebo science; performance multiprocessing; checkpoint trust model; mint authentication; historical recomputation; authority/freeze/ARM machinery.

A later implementation may exist only after independent adversarial review of this prereg, fixture-only implementation, independent implementation review, a new freeze, and a new ARM. Those are separate units.

---

## 16. Execution ceremony

1. independent red-team accepts this policy prereg;
2. fixture-only implementation of the policy (no production grid);
3. independent implementation review;
4. freeze exact implementation commit/tree;
5. explicit new ARM for one V2 production calibration;
6. persist full V2 RESULT before methodology changes;
7. inspect outcomes once;
8. any methodology change requires a new version.

Current state:

```text
implementation_exists = false
production_calibration_executed = false
synthetic_execution_authorized = false
v2_production_arm_authorized = false
ready_for_v2_implementation_review = false
next_required_step = INDEPENDENT_ADVERSARIAL_REVIEW_OF_V2_RANK_DEGENERACY_POLICY_PREREG
```
