# `COMPILER_V3_VARIANCE_FLOOR_VALIDATION` — specification V1 (revision 4, frozen)

**Status:** `FROZEN / NOT_RUN / NOT_ADOPTED` (2026-10-04, revision 4: the owner's last repair, 3B stress-adoption gate and candidate invariance; frozen by owner authorization together with the golden manifest and the builder; digests in §11 and in `COMPILER_V3_VARIANCE_FLOOR_FREEZE_RECORD.json`). A simulation generator may now be written; no official sensitivity run without a separate authorization. An adoption gate of `HYPOTHESIS_EVALUATION_CONTRACT_V2_DRAFT.md` §5.3. Nothing here runs until the owner freezes this spec (digest recorded in the V2 draft) and authorizes the run. No generator code exists yet.
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
| `VAR_EXPOSED_ESTIMATE` | the planning input the compiler is handed. **In this gate it is a controlled input, not an estimate:** `VAR_EXPOSED_ESTIMATE := q × VAR_TRUE` with `q` read directly from the frozen grid (§3A). No exposed sample is drawn and no estimator is evaluated here; the gate tests compiler robustness to a given degree of understatement. A sampling/calibration check of a real exposed estimator is a separate unit and takes no part in choosing the floor |
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

Twelve points. For each design, each candidate `f ∈ {0.60, 0.75, 1.00}` and each grid point: the compiler is handed `VAR_EXPOSED_ESTIMATE = q·k·VAR_FALLBACK` and plans with `VAR_PLANNING = VAR_FALLBACK × max(q·k, f)` at nominal power 0.80 for the design's declared effect `δ_min` and its multiplicity alpha, declaring the cell `FEASIBLE` or not at the cell's sample size; the **evaluation samples are generated under `VAR_TRUE = k·VAR_FALLBACK`** and the empirical power and size are measured. This grid asks exactly one question: **does the floor protect feasibility verdicts against an understating exposed estimator when the fallback is conservative?** The true variance never exceeds the fallback here, so no candidate `f ≤ 1` is asked to compensate a regime shift.

### 3B. DISTRIBUTIONAL / STRESS REGRESSION grid (stress-adoption gate; never selects `f`)

Cells (frozen in the manifest):
- **regime shift:** `k ∈ {1.50, 2.00}` with `q = 1` (true variance above the fallback);
- **heavy tails:** innovations `t₄` and `t₃` scaled to the design's `VAR_TRUE`, at `k = 1, q = 1`;
- **dependence stress:** for S4, ICC doubled; for S5, venue correlation 0.95; at `k = 1, q = 1`.

**Role.** 3B never participates in choosing `f`: it cannot move the choice between 0.60, 0.75 and 1.00. After the 3A selection (§4) has produced `ADOPTED_FLOOR_CANDIDATE`, the **stress-adoption gate** runs on the 3B cells **at that candidate only**: for every 3B cell the compiler actually declares `FEASIBLE`, the same safety requirements as in §4 apply (empirical power ≥ 0.75 at `δ_min`, ≥ 0.95 at `2δ_min`, size ≤ α + 0.01 at `δ = 0`), decided by the same Stage A/B Monte Carlo rule and the same one-sided 99 % Clopper–Pearson bounds (§6). Outcome: any decisive 3B safety `FAIL` → `ADOPTION_BLOCKED_BY_STRESS`; no `FAIL` but an unresolved Stage-B cell → `STRESS_VALIDATION_INDETERMINATE`; otherwise the stress gate is `PASS`.

**Candidate invariance (freeze invariant).** By the exact frozen arithmetic `VAR_PLANNING = VAR_FALLBACK × max(q·k, f)`, every 3B cell has `q·k ≥ 1 ≥ f`, so `VAR_PLANNING(0.60) = VAR_PLANNING(0.75) = VAR_PLANNING(1.00)` in every 3B cell: the floor never binds there. The manifest validator computes `VAR_PLANNING` at all three candidates for every 3B cell and requires equality; any 3B cell whose planning variance depends on the candidate is `FREEZE_FAIL`. This guarantees that 3B can block adoption but cannot select the floor by a hidden route.

## 4. Selection rule (frozen): safety and utility

For a candidate `f`, over the §3A grid and the golden manifest (§5):

- **SAFETY (on actual `FEASIBLE`, every 3A cell).** For **every** 3A cell, whatever its expected classification (`MUST_BE_FEASIBLE`, `MUST_NOT_BE_FEASIBLE` or `BOUNDARY_NO_REQUIREMENT`): if the compiler declares it `FEASIBLE` under `f`, it must show empirical **power ≥ 0.75** at `δ_min`, **power ≥ 0.95** at `2δ_min`, and empirical **size ≤ α + 0.01** at `δ = 0`, each decided by the Monte Carlo procedure of §6. `BOUNDARY_NO_REQUIREMENT` only means that no compiler classification is required of the cell; it never exempts a cell the candidate actually declares feasible from the power and size rule. Separately, any cell with expected classification `MUST_NOT_BE_FEASIBLE` that the compiler declares `FEASIBLE` under `f` is a safety failure (false-feasible). The expected-classification check and the safety-on-actual-`FEASIBLE` check are two different checks and both apply.
- **UTILITY.** Every cell with expected classification `MUST_BE_FEASIBLE` must be declared `FEASIBLE` under `f`. A candidate that is safe only because it refuses mandatory cells fails here.
- **Candidate status:** `PASS` if every decisive check passes; `FAIL` if any decisive check fails; `INDETERMINATE` if no check fails but at least one decisive check is `VALIDATION_INDETERMINATE` after §6. Decisive checks are: every safety check on a cell actually declared `FEASIBLE` (3A), every false-feasible check, every utility check.
- **Selection (3A only):** `ADOPTED_FLOOR_CANDIDATE = min { f : 3A status(f) = PASS }`. 3B cells take no part in this step.

**Final status state machine (no manual override):**

| Condition | Result |
|---|---|
| no 3A candidate `PASS`, at least one 3A candidate `INDETERMINATE` | `VALIDATION_INDETERMINATE` |
| every 3A candidate `FAIL` | `VARIANCE_MODEL_REDESIGN_REQUIRED` |
| 3A floor selected, 3B stress gate has a decisive `FAIL` | `ADOPTION_BLOCKED_BY_STRESS` |
| 3A floor selected, no stress `FAIL`, a stress cell `VALIDATION_INDETERMINATE` | `STRESS_VALIDATION_INDETERMINATE` |
| 3A floor selected, 3B stress gate `PASS` | `VALIDATION_PASS` with `ADOPTED_FLOOR = ADOPTED_FLOOR_CANDIDATE` |

Only `VALIDATION_PASS` completes the variance-floor validation for adoption.

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

**Candidate-independent oracle (frozen, mechanical, written before any run).** For every design/scenario cell the manifest records `N_ORACLE_80`: the information count (observations, pairs, clusters or events, as the design's independent unit) at which the design's **own inference procedure** reaches **power 0.80** for `δ_min` under **`VAR_TRUE`**, computed analytically **without** any candidate floor `f`, without `VAR_EXPOSED_ESTIMATE` and without any compiler decision:

- S1/S2 (two-sample `t`): per arm `n = 2·VAR_TRUE·(z_{α/2} + z_{0.80})² / δ_min²`, total `2·⌈n⌉`;
- S3 (sign-flip over pairs, normal approximation): `⌈VAR_TRUE·(z_{α/2} + z_{0.80})² / δ_min²⌉` pairs;
- S4 (cluster-robust with `t_{G−1}`): the smallest integer `G` with `G ≥ DEFF·VAR_TRUE·(t_{G−1,α/2} + t_{G−1,0.80})² / (m·δ_min²)`, `DEFF = 1 + (m−1)·ICC`, `m = 24`; the `t` quantiles are iterated on `G−1`;
- S5 (sign-flip over events; venues are measurements): `⌈VAR_TRUE·(z_{α/2} + z_{0.80})² / δ_min²⌉` events, where `VAR_TRUE` is the variance of the venue-averaged event statistic;
- S6 (era-stratified sign-flip): as S5, rounded up to a multiple of 3 (equal era allocation).

`α` is the Holm first step for a family of 4 (`0.0125`, two-sided). `δ_min` is frozen per design (`0.5·SD_BASE` for S1–S4, `1.0·SD_BASE` for the rare-event designs S5–S6).

**Sample-size grid and expected classification (relative to `N_ORACLE_80` only):**
- `0.50 × N_ORACLE_80` → `MUST_NOT_BE_FEASIBLE`;
- `0.75 × N_ORACLE_80` → `BOUNDARY_NO_REQUIREMENT`;
- `1.00 × N_ORACLE_80` → `BOUNDARY_NO_REQUIREMENT`;
- `1.50 × N_ORACLE_80` → `MUST_BE_FEASIBLE`.
Every multiplier is rounded **up** to the design's discreteness (even counts for two arms, a multiple of 3 for eras, an integer number of clusters with a floor of 4 so that `t_{G−1}` exists); the rounding rule and the raw value are recorded per cell in the manifest (`ORACLE_ROUNDING`, `SAMPLE_SIZE.ROUNDING`) **before** the freeze and are never changed after a run. The compiler's verdict for a cell does not depend on the true effect of the evaluation sample, so the null, `δ_min` and `2δ_min` variants of a cell share the expected classification and differ only in the check they run (size, power ≥ 0.75, power ≥ 0.95).

3B cells carry `EXPECTED_CLASSIFICATION = BOUNDARY_NO_REQUIREMENT` and `ROLE = STRESS_REGRESSION`; they never select `f` and act only through the §3B stress-adoption gate.

## 6. Monte Carlo procedure (deterministic escalation; no boundary lottery)

- **Confidence level:** one-sided **99 %**.
- **Interval method:** exact Clopper–Pearson one-sided bounds on the binomial proportion (power or size) from the replication counts.
- **Stage A:** 2 000 replications per cell (seeds `base … base+1999` from the seed manifest).
  - Power check (threshold 0.75): `PASS` if the 99 % **lower** bound ≥ 0.75; `FAIL` if the 99 % **upper** bound < 0.75; otherwise **escalate**.
  - Size check (threshold `α + 0.01`): `PASS` if the 99 % **upper** bound ≤ α + 0.01; `FAIL` if the 99 % **lower** bound > α + 0.01; otherwise **escalate**.
- **Stage B (automatic, no decision):** the cell is extended with the pre-assigned additional seeds to a **total of 10 000 replications** (`base … base+9999`); the same bounds are recomputed on the pooled count; `PASS` / `FAIL` as above.
- **Unresolved after Stage B:** cell status `VALIDATION_INDETERMINATE`.
- **Seed namespace (collision-proof):** `base = 10¹² × design_index + 10⁶ × cell_index`, `seed = base + replicate_index` with `0 ≤ replicate_index < 10 000`; Stage A is the **prefix** `[base, base + 1 999]` of Stage B `[base, base + 9 999]`. With at most 10⁶ cells per design and 10⁴ replications per cell no two cells can overlap.
- **Manifest validation (part of the freeze; a failure is `FREEZE_FAIL`):** schema (every required field on every cell); oracle/label validity (expected classification is the pure function of grid and size multiplier; positive counts; sizes monotone in the multiplier); 3B candidate invariance (§3B); seeds: every cell has both ranges, Stage A is the prefix of Stage B, lengths exactly 2 000 and 10 000, Stage-B ranges of distinct `CELL_ID`s pairwise disjoint (sorted-adjacent check), any duplicate seed fails. The check runs in `build_golden_manifest.py` and its output is stored in the manifest (`MANIFEST_VALIDATION`, with `FREEZE_OK`).
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
- The §4 evaluation per candidate, the 3B stress-gate evaluation at the candidate, and the final state-machine result (`VALIDATION_PASS` with `ADOPTED_FLOOR`, `VALIDATION_INDETERMINATE`, `VARIANCE_MODEL_REDESIGN_REQUIRED`, `ADOPTION_BLOCKED_BY_STRESS`, `STRESS_VALIDATION_INDETERMINATE`).
- A markdown table of the manifest with results; no narrative choice.

## 10. Not in scope

Market data; real variance estimates; any executed unit before adoption; the stress multiplier 2.0 (unchanged fallback); any PASS/FAIL band of any design; any floor outside the grid.

## 11. Freeze record

| Field | Value |
|---|---|
| Frozen | 2026-10-04, owner authorization after the manifest sanity review and the §3B repair |
| Spec digest | the digest of this file cannot be stored inside it; it is recorded in `COMPILER_V3_VARIANCE_FLOOR_FREEZE_RECORD.json` and in `HYPOTHESIS_EVALUATION_CONTRACT_V2_DRAFT.md` §5.3 |
| Golden manifest | `COMPILER_V3_VARIANCE_FLOOR_GOLDEN_MANIFEST_V1.json`, sha256 `4a03855324478671a4cb0952066c1c1d58d854d05098c40e5420acc6c9b0c4fd` |
| Builder / validator | `scripts/research/compiler_v3_variance_floor/build_golden_manifest.py`, sha256 `6d4b99b655728345f145f00335cd5f36dd6f7cae430b3eb27e16d7c8fa07e095` |
| Manifest validation at freeze | `FREEZE_OK = true` (1 068 cells; schema, oracle/labels, 3B candidate invariance, seed prefix/lengths/pairwise-disjoint all true; stored in the manifest's `MANIFEST_VALIDATION`) |
| Simulation generator | not written at freeze; may be written after it; its digest is recorded in the freeze record before any run |
| Run authorized | — (separate authorization) |
| Adopted floor | — |
