# `COMPILER_V3_VARIANCE_FLOOR_VALIDATION` — frozen specification V1

**Status:** `SPEC_DRAFT / NOT_RUN / NOT_ADOPTED` (2026-10-04). An adoption gate of `HYPOTHESIS_EVALUATION_CONTRACT_V2_DRAFT.md` §5.3. Nothing here runs until the owner freezes this spec (digest recorded in the V2 draft) and authorizes the run.
**Purpose:** choose the adopted value of the planning variance floor (§5.3) by a frozen rule on a synthetic suite with known ground truth. Not a test of any market hypothesis.

## 1. Rules that bind the run

1. **Order.** (a) this spec and the suite manifest (§4) are frozen with digests; (b) the selection rule (§3) is frozen in the same commit; (c) only then the suite runs, once; (d) the result and the chosen floor are recorded; (e) adoption is an owner decision.
2. **No known outcome is an input.** R03-C1, D12, any executed unit, any real market series and any exposed-data variance estimate are excluded from the suite and from the selection. After a floor is adopted, historical exposed units may be run only as a **non-decisive regression suite** (§6), reported beside the adopted floor and unable to change it.
3. **Synthetic only, ground truth known.** Every design in the suite is generated with a known true effect and a known dependence structure, so empirical power and size are exact targets, not estimates of the market.
4. **No hand selection.** If no candidate satisfies the rule, the output is `VARIANCE_MODEL_REDESIGN_REQUIRED` and no floor is chosen.

## 2. Objects

- **Candidate floor grid (frozen):** `{0.60, 0.75, 1.00}` on the **variance** scale: `VAR_PLANNING = max(VAR_EXPOSED_ESTIMATE, f × VAR_FALLBACK)`, `VAR_FALLBACK = (2.0 × SD_BASE)²`.
- **Adverse variance-ratio grid (frozen):** the true variance of the unit statistic relative to the planning variance the compiler would assume from a "clean" exposed estimate: `r ∈ {1.0, 1.5, 2.0, 3.0}`. `r = 1` is the honest case; `r = 3` means the exposed estimate under-stated the true variance threefold.
- **Nominal planning:** power 0.80 at the design's declared minimum meaningful effect, alpha from the design's multiplicity regime (Holm first step for its declared family size).
- **Pass criterion per design and candidate:** a design the compiler declares `FEASIBLE` under candidate `f` must keep **empirical power ≥ 0.75** at its declared effect on **every** point of the adverse grid, and empirical size ≤ alpha + 0.01 at zero effect.

## 3. Selection rule (frozen)

`ADOPTED_FLOOR = min { f in grid : every design in the suite declared FEASIBLE under f passes the criterion of §2 }`.
If the set is empty: `VARIANCE_MODEL_REDESIGN_REQUIRED`. Ties cannot occur (the grid is ordered). The rule is evaluated by script from the suite output; no manual override field exists.

## 4. Suite manifest (frozen with this spec)

Each design is generated at **three sample sizes**: the size at which the compiler declares it `FEASIBLE` at nominal power under `f = 1.00`, and 0.75× and 1.5× of that. Replications: 2 000 synthetic datasets per cell; seeds fixed per design id.

| ID | Design class | Generator (ground truth) | Independent unit / dependence | Estimator and inference |
|---|---|---|---|---|
| S1 | two-group unpaired | Gaussian outcomes, group effect δ ∈ {0, δ_min} | observation; independent | difference of means; two-sample `t` |
| S2 | two-group unpaired, heavy tails | `t₄` outcomes scaled to SD 1, same δ | observation; independent | same |
| S3 | paired / randomization | pairs with shared pair effect (ICC 0.5), within-pair contrast δ | pair; within-pair dependence | mean paired difference; sign-flip, 20 000 draws |
| S4 | small-G clustered | dates as clusters, `G ∈ {12, 20, 30}`, 24 units per cluster, ICC ∈ {0.05, 0.15}, effect δ | date cluster | cluster-robust ratio estimator with `G/(G−1)` and `t_{G−1}` (the V2 §5 form) |
| S5 | rare-event, event-level clustered | 40–60 events, each measured on 3 "venues" with venue correlation 0.8, effect δ at the event level | event (venues are measurements) | event-level mean of venue-averaged contrasts; sign-flip over events |
| S6 | rare-event with era clusters | 60 events across 3 eras with era-level shifts, effect δ | event nested in era | era-stratified sign-flip |
| N1–N6 | null controls | the same six generators with δ = 0 | as above | as above; size must hold |
| P1–P6 | positive controls | the same six generators with δ = 2 × δ_min | as above | power must be ≈ 1 at the feasible size |

For every design the "exposed variance estimate" fed to the compiler is the sample variance of the unit statistic from an **independent** synthetic sample of the same generator (the clean case), and the adverse grid then scales the **true** variance of the evaluation sample by `r`.

## 5. Outputs (one run)

- `COMPILER_V3_VARIANCE_FLOOR_VALIDATION_RESULT.json`: per design × candidate × size × `r`: feasibility verdict, empirical power, empirical size, the compiler's planning variance and MDE, seeds, digests of this spec and of the generator code.
- The selection-rule evaluation and `ADOPTED_FLOOR` or `VARIANCE_MODEL_REDESIGN_REQUIRED`.
- A short markdown report that prints the table of §4 with results; no narrative choice.

## 6. Non-decisive regression suite (after adoption only)

Historical exposed units (R03 cells, C025-R1, SEED-0001 feasibility, D-series feasibility records) are re-compiled under compiler V3 with the adopted floor, using their **frozen** planning inputs only; their feasibility verdicts are reported beside the V2 verdicts. They cannot change the floor, and no result is rescored.

## 7. What is not in scope

Market data; real variance estimates; any executed unit's numbers before adoption; thresholds other than the floor; the stress multiplier 2.0 (unchanged fallback); the PASS/FAIL bands of any design.

## 8. Freeze record

| Field | Value |
|---|---|
| Spec digest | recorded in `HYPOTHESIS_EVALUATION_CONTRACT_V2_DRAFT.md` at freeze |
| Suite generator code | `scripts/research/compiler_v3_variance_floor/` (to be written; digest at freeze) |
| Run authorized | — |
| Adopted floor | — |
