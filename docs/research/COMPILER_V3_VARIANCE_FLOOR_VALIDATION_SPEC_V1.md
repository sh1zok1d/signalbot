# `COMPILER_V3_VARIANCE_FLOOR_VALIDATION` — specification V1 (revision 2)

**Status:** `SPEC_DRAFT / NOT_FROZEN / NOT_RUN / NOT_ADOPTED` (2026-10-04, revision 2 after the owner's spec review). An adoption gate of `HYPOTHESIS_EVALUATION_CONTRACT_V2_DRAFT.md` §5.3. Nothing here runs until the owner freezes this spec (digest recorded in the V2 draft) and authorizes the run. No generator code exists yet.
**Purpose:** choose the adopted value of the planning variance floor `f` by a frozen two-sided rule (safety and utility) on a synthetic suite with known ground truth. Not a test of any market hypothesis.

## 1. Rules that bind the run

1. **Order.** (a) this spec, the golden manifest (§5) and the seed manifest (§6.4) are frozen with digests; (b) the selection rule (§4) is frozen in the same commit; (c) only then the suite runs, once, with the deterministic escalation of §6; (d) the result and the chosen floor are recorded; (e) adoption is an owner decision.
2. **No known outcome is an input.** R03-C1, D12, any executed unit, any real market series and any real exposed-data variance estimate are excluded from the suite and from the selection. After a floor is adopted, historical exposed units may be run only as a **non-decisive regression suite** (§8).
3. **Synthetic only, ground truth known.**
4. **No hand selection, no hand rerun.** If no candidate passes both sides of §4, the output is `VARIANCE_MODEL_REDESIGN_REQUIRED`; if the Monte Carlo escalation of §6 leaves a decisive cell unresolved, the output is `VALIDATION_INDETERMINATE`. Neither is a floor.

## 2. Variance concepts (exact definitions)

For a design's unit statistic (the quantity whose mean is the estimand):

| Symbol | Definition |
|---|---|
| `VAR_TRUE` | the true variance of the unit statistic in the evaluation sample, known from the generator |
| `VAR_FALLBACK` | the frozen conservative planning variance of V1: `VAR_FALLBACK = (2.0 × SD_BASE)²`, with `SD_BASE` the design's declared base SD of the unit statistic (`SD_BASE = 1` in the compiler's effect units) |
| `VAR_EXPOSED_ESTIMATE` | the variance the compiler would be handed from an exposed-data estimator: in the suite, the sample variance of the unit statistic computed on an **independent** synthetic sample from the same generator, then multiplied by the understatement factor `q` of the grid (§3A) |
| `VAR_PLANNING` | `VAR_PLANNING = max( VAR_EXPOSED_ESTIMATE , f × VAR_FALLBACK )`, the variance the compiler uses to declare feasibility and to size the design |

Two frozen ratios parameterize the suite:

- `k = VAR_TRUE / VAR_FALLBACK` — where the true variance sits relative to the conservative fallback (the floor is meaningful only when the fallback is conservative, `k ≤ 1`);
- `q = VAR_EXPOSED_ESTIMATE / VAR_TRUE` — how much the exposed estimator understates the truth (`q = 1` honest; `q < 1` understatement).

Hence `VAR_EXPOSED_ESTIMATE = q·k·VAR_FALLBACK` and `VAR_PLANNING = VAR_FALLBACK × max(q·k, f)`. The planning-to-true ratio the compiler effectively assumes is `ρ(f) = VAR_PLANNING / VAR_TRUE = max(q·k, f) / k`; the floor guarantees `ρ(f) ≥ f / k`.

## 3. Two grids, kept apart

### 3A. FLOOR CALIBRATION grid (selects `f`)

Frozen grid of `(k, q)`:

- `k ∈ {0.50, 0.75, 1.00}` (fallback conservative by 2×, 1.33×, exact);
- `q ∈ {1.00, 0.75, 0.50, 0.33}` (exposed estimator honest, or understating the truth by 1.33×, 2×, 3×).

Twelve points. For each design, each candidate `f ∈ {0.60, 0.75, 1.00}` and each grid point: the compiler plans with `VAR_PLANNING = VAR_FALLBACK × max(q·k, f)` at nominal power 0.80 for the design's declared effect `δ_min` and its multiplicity alpha, declaring the cell `FEASIBLE` or not at the cell's sample size; the evaluation sample is then drawn with `VAR_TRUE = k·VAR_FALLBACK` and the empirical power and size are measured. This grid asks exactly one question: **does the floor protect feasibility verdicts against an understating exposed estimator when the fallback is conservative?** The true variance never exceeds the fallback here, so no candidate `f ≤ 1` is asked to compensate a regime shift.

### 3B. DISTRIBUTIONAL / STRESS REGRESSION grid (can block adoption; never selects `f`)

Run only for the candidate selected by §4, and reported for all candidates descriptively:

- **regime shift:** `k ∈ {1.50, 2.00}` with `q = 1` (true variance above the fallback); measured: empirical size (must hold) and power loss (reported);
- **heavy tails:** innovations `t₄` and `t₃` scaled to the design's `VAR_TRUE`, at `k = 1, q = 1`;
- **dependence stress:** for clustered designs, ICC doubled relative to the manifest value; for the venue design, venue correlation 0.95.

Blocking criterion of 3B: **size** must satisfy the §4 safety size requirement on every 3B cell; a size breach is `ADOPTION_BLOCKED_BY_STRESS` with the cell named. Power under 3B is reported, never thresholded, because a floor `f ≤ 1` cannot and should not absorb a true variance above the fallback.

## 4. Selection rule (frozen): safety and utility

For a candidate `f`, over the §3A grid and the golden manifest (§5):

- **SAFETY.** Every cell whose role is `SAFETY` and which the compiler declares `FEASIBLE` under `f` must show empirical **power ≥ 0.75** at `δ_min` and empirical **size ≤ α + 0.01** at `δ = 0`, each decided by the Monte Carlo procedure of §6. Any cell with expected classification `MUST_NOT_BE_FEASIBLE` that the compiler declares `FEASIBLE` under `f` is a safety failure (false-feasible).
- **UTILITY.** Every cell with expected classification `MUST_BE_FEASIBLE` must be declared `FEASIBLE` under `f`. A candidate that is safe only because it refuses mandatory positive controls fails here.
- **Candidate status:** `PASS` if every decisive cell passes both sides; `FAIL` if any decisive cell fails; `INDETERMINATE` if no cell fails but at least one decisive cell is `VALIDATION_INDETERMINATE` after §6.
- **Selection:** `ADOPTED_FLOOR = min { f : status(f) = PASS }`. If no candidate is `PASS` and at least one is `INDETERMINATE`: gate result `VALIDATION_INDETERMINATE` (no floor; the suite's replication budget is revisited by amendment). If every candidate is `FAIL`: `VARIANCE_MODEL_REDESIGN_REQUIRED`. No manual override field exists.

## 5. Golden manifest (frozen before the run; labels immutable afterwards)

One JSON record per cell, schema:

```
{
  "CELL_ID": "S4-G20-ICC015-N0.75",
  "DESIGN_ID": "S4",                       // design family (§7)
  "SCENARIO": "small-G clustered",
  "GENERATOR_PARAMS": {...},               // every parameter of the generator, explicit
  "SAMPLE_SIZE": {"UNITS": 480, "RELATIVE_TO_FEASIBLE_N_AT_F1": 0.75},
  "TRUE_EFFECT": 0.0 | "DELTA_MIN" | "2x_DELTA_MIN",
  "VARIANCE_RELATIONSHIPS": {"k": 0.75, "q": 0.5, "SD_BASE": 1.0},
  "GRID": "3A" | "3B",
  "EXPECTED_CLASSIFICATION": "MUST_BE_FEASIBLE" | "MUST_NOT_BE_FEASIBLE" | "BOUNDARY_NO_REQUIREMENT",
  "ROLE": "SAFETY" | "UTILITY" | "BOTH" | "STRESS_REGRESSION",
  "SEED_RANGE": {"STAGE_A": [base, base+1999], "STAGE_B": [base, base+9999]},
  "MULTIPLICITY_ALPHA": 0.0125
}
```

**Expected-classification logic (frozen, mechanical, written before any run):**
- `MUST_BE_FEASIBLE`: the cell's sample size is **1.5×** the size at which the compiler declares the design feasible under `f = 1.00` with an honest estimator (`q = 1`) at the cell's `k`. Such a cell has ample information under the most conservative candidate; a candidate that refuses it is useless.
- `MUST_NOT_BE_FEASIBLE`: the cell's sample size is **0.50×** the size at which true power 0.80 is attained given `VAR_TRUE` (computed analytically from the generator). Declaring it feasible is a false-feasible verdict whatever the estimator says.
- `BOUNDARY_NO_REQUIREMENT`: sizes between those two (the `0.75×` and `1.0×` cells); reported, never decisive for selection.
Positive controls (`2× δ_min`) are `MUST_BE_FEASIBLE` at the `1.0×` size; null controls carry the size requirement only.

## 6. Monte Carlo procedure (deterministic escalation; no boundary lottery)

- **Confidence level:** one-sided **99 %**.
- **Interval method:** exact Clopper–Pearson one-sided bounds on the binomial proportion (power or size) from the replication counts.
- **Stage A:** 2 000 replications per cell (seeds `base … base+1999` from the seed manifest).
  - Power check (threshold 0.75): `PASS` if the 99 % **lower** bound ≥ 0.75; `FAIL` if the 99 % **upper** bound < 0.75; otherwise **escalate**.
  - Size check (threshold `α + 0.01`): `PASS` if the 99 % **upper** bound ≤ α + 0.01; `FAIL` if the 99 % **lower** bound > α + 0.01; otherwise **escalate**.
- **Stage B (automatic, no decision):** the cell is extended with the pre-assigned additional seeds to a **total of 10 000 replications** (`base … base+9999`); the same bounds are recomputed on the pooled count; `PASS` / `FAIL` as above.
- **Unresolved after Stage B:** cell status `VALIDATION_INDETERMINATE`.
- **Seed manifest:** `base = 1_000_000 × design_index + 10_000 × cell_index`, with the `(design_index, cell_index)` table frozen in the golden manifest; the generator is seeded per replication with `base + r`.
- **Aggregation rule:** a candidate is `FAIL` if any decisive cell (role `SAFETY`, `UTILITY` or `BOTH`) is `FAIL`; else `INDETERMINATE` if any decisive cell is `VALIDATION_INDETERMINATE`; else `PASS`. `BOUNDARY_NO_REQUIREMENT` and `STRESS_REGRESSION` cells never enter the aggregation except through the 3B size block of §3B.

## 7. Suite designs (generators; parameters frozen in the manifest)

| ID | Design class | Generator (ground truth) | Independent unit / dependence | Estimator and inference |
|---|---|---|---|---|
| S1 | two-group unpaired | Gaussian outcomes, effect δ ∈ {0, δ_min, 2δ_min} | observation; independent | difference of means; two-sample `t` |
| S2 | two-group unpaired, heavy tails (3B only) | `t₄` / `t₃` scaled to `VAR_TRUE` | observation; independent | same |
| S3 | paired / randomization | pairs with shared pair effect (ICC 0.5), within-pair contrast δ | pair | mean paired difference; sign-flip, 20 000 draws |
| S4 | small-G clustered | dates as clusters, `G ∈ {12, 20, 30}`, 24 units per cluster, ICC ∈ {0.05, 0.15}, effect δ | date cluster | cluster-robust ratio estimator, `G/(G−1)`, `t_{G−1}` (V2 §5 form) |
| S5 | rare-event, event-level clustered | 40–60 events × 3 venue measurements, venue correlation 0.8, effect δ at the event level | event (venues are measurements) | event-level mean of venue-averaged contrasts; sign-flip over events |
| S6 | rare-event with era clusters | 60 events across 3 eras with era shifts, effect δ | event nested in era | era-stratified sign-flip |

Each design appears at three sample sizes (0.50×, 0.75× / 1.0× boundary, 1.5× as defined in §5), with null (`δ = 0`), `δ_min` and positive-control (`2δ_min`) variants, over the twelve 3A points; 3B cells as listed in §3B.

## 8. Non-decisive regression suite (after adoption only)

Historical exposed units (R03 cells, C025-R1, SEED-0001 feasibility, D-series feasibility records) are re-compiled under compiler V3 with the adopted floor from their **frozen** planning inputs; verdicts are reported beside the V2 verdicts, cannot change the floor, and no result is rescored.

## 9. Outputs (one run)

- `COMPILER_V3_VARIANCE_FLOOR_VALIDATION_RESULT.json`: per cell × candidate: compiler verdict, Stage A and (if any) Stage B counts and bounds, cell status, with the digests of this spec, the golden manifest, the seed manifest and the generator code.
- The §4 evaluation per candidate and the gate result: `ADOPTED_FLOOR = f`, `VALIDATION_INDETERMINATE`, `VARIANCE_MODEL_REDESIGN_REQUIRED`, or `ADOPTION_BLOCKED_BY_STRESS`.
- A markdown table of the manifest with results; no narrative choice.

## 10. Not in scope

Market data; real variance estimates; any executed unit before adoption; the stress multiplier 2.0 (unchanged fallback); any PASS/FAIL band of any design; any floor outside the grid.

## 11. Freeze record

| Field | Value |
|---|---|
| Spec digest | — (recorded in the V2 draft at freeze) |
| Golden manifest | `COMPILER_V3_VARIANCE_FLOOR_GOLDEN_MANIFEST_V1.json` — to be written before freeze; digest at freeze |
| Generator code | `scripts/research/compiler_v3_variance_floor/` — not written; digest at freeze |
| Run authorized | — |
| Adopted floor | — |
