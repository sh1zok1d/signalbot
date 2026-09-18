# V2 Rank-Degeneracy Policy — Amendment 001

**Status:** `FROZEN_BEFORE_IMPLEMENTATION`
**Unit ID:** `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY`
**Amendment ID:** `AMENDMENT_001`
**Amendment type:** docs-only prospective repair of independent-review findings
**Does not rewrite:** [`HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_PREREG.md`](HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_PREREG.md)

Machine-readable twin: [`HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_PREREG_AMENDMENT_001.json`](HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_PREREG_AMENDMENT_001.json).

```text
amended_prereg_head = ada237edc330b44bc412332e263f124757919e93
amended_prereg_tree = ba1c0873879b7ea8556c3e238f8b962b91da6dc2
review_verdict      = PREREG_REPAIR_REQUIRED
BLOCKERS            = 0
MAJORS              = 1
MINORS              = 4
closes              = MAJOR-1, MINOR-1, MINOR-2, MINOR-3, MINOR-4
```

This amendment does not implement V2, does not arm production, does not consume V1 authority, and does not change DGP, candidates, RNG, seeds, OLS, or the algebraic full-rank rule.

Sound V2 semantics from the original prereg remain in force except where this amendment explicitly clarifies or, for F01 only, prospectively retiers a coverage floor.

---

## 0. Preserved sound semantics

Unchanged:

- `WORLD_VALID` / `WORLD_INVALID`
- `CANDIDATE_IDENTIFIABLE` / `CANDIDATE_NOT_IDENTIFIABLE`
- baseline degeneracy → `WORLD_INVALID`
- candidate degeneracy with valid baseline → `CANDIDATE_NOT_IDENTIFIABLE`
- `NOT_IDENTIFIABLE` is neither PASS nor FAIL
- candidate-first confirmatory aggregation
- planned / world-valid / identifiable / non-identifiable / detection counters
- Wilson z and Wilson coverage rule
- hard floor `candidate_identifiable_count >= 200`
- NULL per-candidate conjunction (every F01–F10 on `NULL|5000`)
- oracle F03 policy (non-identifiable F03 is not an ordinary false negative)
- full-rank rule: `rank < ncols` ⇒ not identifiable
- mechanical precedence: structural incompleteness > `INSUFFICIENT_IDENTIFIABILITY` > inherited detection ladder
- V1 status remains `INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM`
- V1 3087-world subset remains non-claimable

---

## 1. MAJOR-1 — identifiable library size L

For every `WORLD_VALID` world define:

```text
identifiable_library_size L
  = number of F01..F10 candidates whose state is CANDIDATE_IDENTIFIABLE
L ∈ {0,1,2,3,4,5,6,7,8,9,10}
```

`L` MUST be persisted on every `WORLD_VALID` world record.

`WORLD_INVALID` worlds have no `L`. They are not placed in any `L` bucket.

### 1.1 Per-cell L distribution

For every `scenario × N` cell publish all eleven buckets:

```text
count(L=0)
count(L=1)
...
count(L=10)
```

No bucket may be omitted, including zeros.

Identity (required):

```text
sum_{l=0}^{10} count(L=l) = world_valid_count
```

for that exact cell.

### 1.2 Zero-identifiable scope (MINOR-2 companion)

`worlds_with_zero_identifiable_candidates` is a **per `scenario × N` cell** count. A global sum may be reported; the per-cell counts are authoritative.

Identity (required):

```text
worlds_with_zero_identifiable_candidates(cell) = count(L=0)(cell)
```

---

## 2. BLIND selection and L-stratified taxonomy

BLIND selection remains restricted to `CANDIDATE_IDENTIFIABLE` candidates. Mathematically unidentifiable candidates are not reintroduced into competition.

If `L = 0`:

```text
selection state = NO_CANDIDATE
```

`L=0` worlds MUST remain visible in `planned_worlds`, `world_valid_count`, candidate non-identifiability counts, the `L=0` bucket, and coverage gates. They MUST NOT enter BLIND taxonomy success/failure denominators. They MUST NEVER be credited as successful `NO_DISCOVERY`.

### 2.1 Required L-stratified BLIND report

For each `scenario × N × L` stratum with `L > 0` report:

```text
BLIND_WORLD_COUNT
TRUE_DISCOVERY
PROXY_DISCOVERY
FALSE_DISCOVERY
NO_DISCOVERY
ANY_EDGE_DECLARED
USEFUL_DISCOVERY
TRUE_DISCOVERY_RATE
USEFUL_DISCOVERY_RATE
Wilson intervals for TRUE_DISCOVERY_RATE and USEFUL_DISCOVERY_RATE
selected_STRICT_PASS_EX_MATERIALITY counts by feature ID
selected_STRICT_PASS counts by feature ID
```

Pooled BLIND totals over `L > 0` MUST also be published. Pooled metrics MUST NOT replace the L-stratified report.

### 2.2 Reconciliation identities

For each `scenario × N` cell:

```text
sum_{L=1}^{10} BLIND_WORLD_COUNT(L)
  = world_valid_count - count(L=0)
  = number of WORLD_VALID worlds with at least one identifiable library candidate

sum_{L=1}^{10} TRUE_DISCOVERY(L)     = pooled TRUE_DISCOVERY
sum_{L=1}^{10} PROXY_DISCOVERY(L)    = pooled PROXY_DISCOVERY
sum_{L=1}^{10} FALSE_DISCOVERY(L)    = pooled FALSE_DISCOVERY
sum_{L=1}^{10} NO_DISCOVERY(L)       = pooled NO_DISCOVERY
sum_{L=1}^{10} ANY_EDGE_DECLARED(L)  = pooled ANY_EDGE_DECLARED
sum_{L=1}^{10} USEFUL_DISCOVERY(L)   = pooled USEFUL_DISCOVERY
```

Pooled BLIND taxonomy denominators remain:

```text
world_valid worlds with L > 0
```

---

## 3. Variable-competition interpretation

A reduction in `L` can mechanically change BLIND selection difficulty. A smaller competition set can raise or lower `TRUE_DISCOVERY`, `FALSE_DISCOVERY`, and `ANY_EDGE_DECLARED` without any change in per-candidate science.

Therefore a favorable **pooled** `TRUE_DISCOVERY` / `FALSE_DISCOVERY` / `ANY_EDGE_DECLARED` / `USEFUL_DISCOVERY` result is not sufficient evidence by itself if that behavior is concentrated in reduced-`L` strata.

This amendment makes the effect observable by requiring the complete L distribution and L-stratified BLIND taxonomy **before** any V2 outcome is inspected.

No additional L-specific PASS/FAIL threshold is scientifically justified before seeing V2 outcomes. Inventing one now would be an arbitrary close-the-finding threshold.

Frozen mechanical rule:

```text
L-stratification is DIAGNOSTIC.
The inherited confirmatory BLIND conclusion may be evaluated only after
its required coverage map is ADEQUATE.
It MUST NOT claim invariance to competition-set size.
A pooled BLIND PASS/FAIL/INDETERMINATE does not supersede or hide the
L-stratified counts.
RESULT must set blind_not_claimed_invariant_to_L = true.
```

Do not invent a post-hoc L correction after V2 outcomes.

---

## 4. MINOR-1 — non-identifiability attribution

Every `CANDIDATE_NOT_IDENTIFIABLE` evaluation MUST carry:

```text
candidate_id
scenario
N
world_id
reason
first_failing_era
```

Closed reason taxonomy:

| reason | Meaning |
|---|---|
| `RANK_DEFICIENT` | candidate-augmented design `rank < ncols` at a required scored-era training window |
| `NONFINITE_FIT_OR_PREDICTION` | non-finite candidate coefficients or scored-row predictions |
| `DESIGN_SHAPE_INVALID` | candidate design shape invalid (not 2-D, or row count ≠ y) |
| `NONFINITE_AE_OR_RELATIVE_MAE` | candidate path AE non-finite, or relative MAE undefined while baseline remains defined |
| `NONFINITE_BOOTSTRAP` | any required bootstrap replicate non-finite/invalid after a successful scientific fit |
| `NONFINITE_PLACEBO` | any required placebo replicate non-finite/invalid after a successful scientific fit |
| `NONFINITE_VISIBILITY` | reserved; see below |

`NONFINITE_VISIBILITY` is reserved for a visibility-path incompleteness attributed to that candidate without baseline failure. The original prereg still holds: visibility-only invalidity does **not** recode candidate identifiability. Baseline residual failure that makes the comparison undefined is `WORLD_INVALID`, not this reason.

`CHRONOLOGY_LOOKAHEAD` is a world-level failure (`WORLD_INVALID`), not a candidate reason.

`first_failing_era`:

- expanding-era fit/prediction/AE failures: `E2`, `E3`, `E4`, or `E5` (first required scored era that fails)
- bootstrap/placebo/visibility-reserved failures after all required era fits succeeded: `NOT_ERA_SCOPED`

For `RANK_DEFICIENT` also record diagnostics (do not change scientific state):

```text
design_nrows
design_ncols
design_rank
required_rank
```

If several reasons apply, persist the first in pipeline order: design shape → rank → finite fit/prediction → AE/relative MAE → bootstrap → placebo.

---

## 5. MINOR-2 — required coverage map

Coverage is judged before detection. If any listed component is `INSUFFICIENT`, the dependent conclusion is `INSUFFICIENT_IDENTIFIABILITY` and its detection/performance threshold is not evaluated.

World-level baseline coverage (`Wilson lower(world_valid_count / planned_worlds) >= 0.95`) is required for the cell of every component below.

Library means exactly `{F01,F02,F03,F04,F05,F06,F07,F08,F09,F10}`.

### 5.1 Explicit map

| conclusion_id | Cell | Required candidates | Inherited claim |
|---|---|---|---|
| `NULL_ORACLE_FPR` | `NULL\|5000` | `{F03}` | ORACLE NULL `MODEL_DETECTED` FPR ≤ 0.05 |
| `NULL_PER_CANDIDATE_FPR` | `NULL\|5000` | that one of F01..F10 | per-candidate NULL FPR on identifiable evaluations |
| `NULL_BLIND_FPR` | `NULL\|5000` | `{F01,F02,F03,F04,F05,F06,F07,F08,F09,F10}` | BLIND NULL `ANY_EDGE_DECLARED` FPR ≤ 0.10 |
| `NULL_FALSE_POSITIVE_CONCLUSION` | `NULL\|5000` | `{F01,F02,F03,F04,F05,F06,F07,F08,F09,F10}` | union of NULL oracle FPR, per-candidate FPR, and BLIND FPR |
| `EASY_ORACLE_POWER` | `EASY\|5000` | `{F03}` | EASY ORACLE `MODEL_DETECTED` ≥ 0.90 |
| `EASY_BLIND_USEFUL_DISCOVERY` | `EASY\|5000` | `{F01,F02,F03,F04,F05,F06,F07,F08,F09,F10}` | EASY BLIND `USEFUL_DISCOVERY` ≥ 0.80 |
| `EASY_CONCLUSION` | `EASY\|5000` | `{F01,F02,F03,F04,F05,F06,F07,F08,F09,F10}` | union of EASY oracle power and EASY BLIND useful-discovery |
| `MODERATE_ORACLE_POWER` | `MODERATE\|5000` | `{F03}` | MODERATE ORACLE `MODEL_DETECTED` ≥ 0.70 |
| `MODERATE_BLIND_USEFUL_DISCOVERY` | `MODERATE\|5000` | `{F01,F02,F03,F04,F05,F06,F07,F08,F09,F10}` | MODERATE BLIND `USEFUL_DISCOVERY` ≥ 0.50 |
| `MODERATE_CONCLUSION` | `MODERATE\|5000` | `{F01,F02,F03,F04,F05,F06,F07,F08,F09,F10}` | union of MODERATE oracle power and MODERATE BLIND useful-discovery |
| `SMALL_ORACLE_BAND` | `SMALL\|5000` | `{F03}` | SMALL ORACLE `MODEL_DETECTED` HIGH/MODERATE/LOW/VERY_LOW band |
| `SMALL_CONCLUSION` | `SMALL\|5000` | `{F03}` | inherited SMALL oracle-band conclusion (not a BLIND decision statistic) |
| `TINY_NOISY_ORACLE_DIAGNOSTIC` | `TINY_NOISY\|5000` | `{F03}` | TINY_NOISY ORACLE conditional detection / floor diagnostic |
| `TINY_NOISY_CONCLUSION` | `TINY_NOISY\|5000` | `{F03}` | inherited TINY_NOISY oracle diagnostic (not a BLIND decision statistic) |
| `NONSTATIONARY_TRAP_ORACLE_SPECIFICITY` | `NONSTATIONARY_TRAP\|5000` | `{F03}` | TRAP `STRICT_PASS_EX_MATERIALITY` detection ≤ 0.20 |
| `NONSTATIONARY_TRAP_CONCLUSION` | `NONSTATIONARY_TRAP\|5000` | `{F03}` | inherited TRAP oracle specificity |
| `SMALL_2500_SENSITIVITY` | `SMALL\|2500` | `{F03}` | SMALL N=2500 ORACLE `MODEL_DETECTED` band / sensitivity |
| `SMALL_10000_SENSITIVITY` | `SMALL\|10000` | `{F03}` | SMALL N=10000 ORACLE `MODEL_DETECTED` band / sensitivity |
| `ORACLE_F03_NULL` | `NULL\|5000` | `{F03}` | oracle F03 on NULL |
| `ORACLE_F03_EASY` | `EASY\|5000` | `{F03}` | oracle F03 on EASY |
| `ORACLE_F03_MODERATE` | `MODERATE\|5000` | `{F03}` | oracle F03 on MODERATE |
| `ORACLE_F03_SMALL_5000` | `SMALL\|5000` | `{F03}` | oracle F03 on SMALL N=5000 |
| `ORACLE_F03_TINY_NOISY` | `TINY_NOISY\|5000` | `{F03}` | oracle F03 on TINY_NOISY |
| `ORACLE_F03_TRAP` | `NONSTATIONARY_TRAP\|5000` | `{F03}` | oracle F03 on TRAP |
| `ORACLE_F03_SMALL_2500` | `SMALL\|2500` | `{F03}` | oracle F03 on SMALL N=2500 |
| `ORACLE_F03_SMALL_10000` | `SMALL\|10000` | `{F03}` | oracle F03 on SMALL N=10000 |
| `BLIND_DISCOVERY_EASY` | `EASY\|5000` | `{F01,F02,F03,F04,F05,F06,F07,F08,F09,F10}` | EASY BLIND useful-discovery decision |
| `BLIND_DISCOVERY_MODERATE` | `MODERATE\|5000` | `{F01,F02,F03,F04,F05,F06,F07,F08,F09,F10}` | MODERATE BLIND useful-discovery decision |
| `BLIND_DISCOVERY_CONCLUSION` | `EASY\|5000` and `MODERATE\|5000` | `{F01,F02,F03,F04,F05,F06,F07,F08,F09,F10}` on each named cell | union of frozen BLIND useful-discovery decisions |
| `VISIBILITY_FLOOR` | `EASY\|5000` | world baseline only (no candidate) | visibility Wilson upper floor |
| `MODEL_FLOOR` | `EASY\|5000` | `{F03}` | model-detection Wilson upper floor |
| `MATERIALITY_ONLY_DIAGNOSTIC` | `EASY\|5000` | `{F03}` | strict-ex vs strict materiality comparison |
| `FINAL_OVERALL_MECHANICAL_CONCLUSION` | see union below | see union below | any methodology consequence other than structural incompleteness |

### 5.2 Final overall union

Before the inherited detection ladder may emit specificity, power, discovery, floor, or materiality consequences, all of the following must be `ADEQUATE`:

| Cell | Required candidates |
|---|---|
| `NULL\|5000` | `{F01,F02,F03,F04,F05,F06,F07,F08,F09,F10}` |
| `EASY\|5000` | `{F01,F02,F03,F04,F05,F06,F07,F08,F09,F10}` |
| `MODERATE\|5000` | `{F01,F02,F03,F04,F05,F06,F07,F08,F09,F10}` |
| `NONSTATIONARY_TRAP\|5000` | `{F03}` |
| `SMALL\|5000` | `{F03}` |
| `TINY_NOISY\|5000` | `{F03}` |
| `SMALL\|2500` | `{F03}` |
| `SMALL\|10000` | `{F03}` |

plus world-baseline coverage `ADEQUATE` on each of those eight cells.

If any required BLIND-only statement is emitted for SMALL, TINY_NOISY, TRAP, or SMALL sensitivity cells, that statement additionally requires the full library `{F01..F10}` `ADEQUATE` on that cell. Those cells have no inherited BLIND PASS/FAIL decision statistic; their default conclusions above remain F03-only.

`NULL_PER_CANDIDATE_FPR` for one candidate may be discussed only if that candidate is `ADEQUATE`. The bundled `NULL_FALSE_POSITIVE_CONCLUSION` still requires all ten.

---

## 6. MINOR-3 — F01 coverage tier

Decision: **B. Move F01 to the F03-like coverage tier.**

This is a prospective prereg amendment made before V2 execution. It is not a post-outcome repair and does not use V1 invalid counts as a fitting target.

Rationale: `F01 = S_(t-1)` (`F01_0 = 0`). The occupancy mechanism that makes F03 identically zero on E1 (no S variation in the E2 training window) also makes F01 identically zero on that window. F02 and F08 are `S` intersected with an X-sign indicator and therefore have a strictly larger non-identifiability set. Coverage floors must follow occupancy mechanism, not PROXY-vs-TRUE taxonomy. Grouping F01 with F02/F08 treated a lagged-S column as if it were a gated intersection.

Exact threshold changes (Wilson lower). No other coverage threshold changes.

| Cell | Candidate | Before | After |
|---|---|---|---|
| `SMALL\|2500` | F01 | 0.65 | 0.75 |
| `TINY_NOISY\|5000` | F01 | 0.60 | 0.70 |

After this amendment, F01 matches F03 on every cell. F02 and F08 remain on the sparser gated floors where those floors existed.

All 8 × 10 coverage entries remain present. The amended table is:

| Cell | F01 | F02 | F03 | F04 | F05 | F06 | F07 | F08 | F09 | F10 |
|---|---|---|---|---|---|---|---|---|---|---|
| `NULL\|5000` | 0.95 | 0.95 | 0.95 | 0.95 | 0.95 | 0.95 | 0.95 | 0.95 | 0.95 | 0.95 |
| `EASY\|5000` | 0.90 | 0.90 | 0.90 | 0.90 | 0.90 | 0.90 | 0.90 | 0.90 | 0.90 | 0.90 |
| `MODERATE\|5000` | 0.90 | 0.90 | 0.90 | 0.90 | 0.90 | 0.90 | 0.90 | 0.90 | 0.90 | 0.90 |
| `NONSTATIONARY_TRAP\|5000` | 0.90 | 0.90 | 0.90 | 0.90 | 0.90 | 0.90 | 0.90 | 0.90 | 0.90 | 0.90 |
| `SMALL\|5000` | 0.85 | 0.85 | 0.85 | 0.85 | 0.85 | 0.85 | 0.85 | 0.85 | 0.85 | 0.85 |
| `SMALL\|10000` | 0.85 | 0.85 | 0.85 | 0.85 | 0.85 | 0.85 | 0.85 | 0.85 | 0.85 | 0.85 |
| `SMALL\|2500` | **0.75** | 0.65 | 0.75 | 0.85 | 0.85 | 0.85 | 0.85 | 0.65 | 0.85 | 0.85 |
| `TINY_NOISY\|5000` | **0.70** | 0.60 | 0.70 | 0.85 | 0.85 | 0.85 | 0.85 | 0.60 | 0.85 | 0.85 |

Hard floor 200 and world-baseline Wilson lower 0.95 are unchanged.

---

## 7. MINOR-4 — selective re-execution

After any V2 production attempt it is forbidden to rerun only failed, incomplete, low-coverage, unfavorable, or otherwise selected `scenario × N` cells and combine those reruns with the original attempt.

Any methodology-changing successor requires a new prereg/version and a new complete authorized execution under that frozen contract.

Operational resume of an interrupted **identical** frozen run remains allowed only under the existing frozen resume semantics (untrusted durable partial cache; no ad-hoc recovery; no RESULT fabrication).

---

## 8. Authority and ceremony

```text
implementation_exists = false
synthetic_execution_authorized = false
v2_production_arm_authorized = false
ready_for_v2_implementation_review = false
ready_for_amendment_rereview = true
next_required_step = INDEPENDENT_REREVIEW_OF_V2_RANK_POLICY_AMENDMENT
```

The original prereg files remain byte-stable historical authority. This amendment is the additive contract for MAJOR-1 and MINOR-1..4.
