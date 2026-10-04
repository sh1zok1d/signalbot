# `COMPILER_V3_VARIANCE_MODEL_REDESIGN` — design V1 (design only; outcome-aware; nothing executed)

**Status:** `DESIGN_ONLY / NOT_FROZEN / NOT_EXECUTED / NOT_ADOPTED`. Written 2026-10-04 after `COMPILER_V3_VARIANCE_FLOOR_VALIDATION_OFFICIAL_RUN_1`.

**Evidence class of this document:** this unit is explicitly **outcome-aware**. It reads the immutable Official Run 1 artifacts (`COMPILER_V3_VARIANCE_FLOOR_VALIDATION_RESULT_V1.json`, sha256 `a10efe4b…`, and `…_AGGREGATION_V1.json`, sha256 `fdd520d7…`) as **DESIGN / DEVELOPMENT evidence** for a replacement variance model. Nothing here is confirmatory, and Official Run 1 can never be cited as confirmation of anything designed here.

**What was and was not computed.** Besides reading the run artifacts, the only computation behind this document is deterministic algebra on the frozen effective manifest's planning quantities (`SAMPLE_SIZE.COUNT`, `N_ORACLE_80`, `VAR_FALLBACK`, `q`, `VAR_TRUE`) through the frozen compiler's `required_n` (sha256 `fd342a38…`). No evaluation sample was simulated, no seed was drawn, no new parameter was searched against outcomes, and no frozen artifact was edited.

---

## 1. Official Run 1, as evidence

| Field | Value |
|---|---|
| Authorization | commit `0828ab0`, artifact sha256 `6760e24dd6beaf54b76c3357ff71f9fbf8676b0209fd9755654a177c3d01d18b` |
| Result commit | `4b2b4f8` |
| FINAL | `VARIANCE_MODEL_REDESIGN_REQUIRED` |
| `ADOPTED_FLOOR_CANDIDATE` | `null` |
| 3A status | 0.60 FAIL (15 power failures, 2 indeterminate), 0.75 FAIL (same), 1.00 FAIL (60 utility failures) |
| Rerun | not authorized; the artifacts are immutable |

Frozen model under test (spec §2): `VAR_PLANNING = max(VAR_EXPOSED_ESTIMATE, f·VAR_FALLBACK)`, with `VAR_EXPOSED_ESTIMATE = q·VAR_TRUE`, `VAR_TRUE = k·VAR_FALLBACK`, so `VAR_PLANNING = VAR_FALLBACK·max(q·k, f)` and the planning-to-true ratio is `ρ(f) = max(q·k, f)/k`.

## 2. Failure diagnosis (mechanical)

### 2.1 The two arithmetic facts that drive every verdict

**Fact A — feasibility is a ratio test on `ρ`.** The frozen compiler declares a cell `FEASIBLE` iff `SAMPLE_N ≥ required_n(VAR_PLANNING)`, and every design's `required_n` is (up to integer rounding and the S4 `t_{G−1}` iteration) linear in the planning variance. `N_ORACLE_80` is the same formula at `VAR_TRUE`. Hence, writing `x` for the cell's size multiple (0.5, 0.75, 1.0, 1.5 × `N_ORACLE_80`), the compiler declares `FEASIBLE` iff `x ≥ ρ(f)` up to rounding. The Run 1 feasibility table is exactly this: with `ρ = 1.2` only 1.5× is feasible; with `ρ = 0.75` the 0.75× cell becomes feasible; with `ρ = 2.0` nothing is feasible.

**Fact B — empirical power depends on `x` only.** Neither `q` nor `f` touches the evaluation sample; they only move the verdict. Run 1 measured, for `δ_min`:

| `x` | S1 | S3 | S4 | S5 |
|---|---|---|---|---|
| 0.50 | 0.42–0.46 | 0.41–0.45 | 0.31–0.44 | 0.32–0.41 |
| 0.75 | 0.64–0.66 | 0.62–0.66 | 0.61–0.66 | 0.58–0.62 |
| 1.00 | 0.79–0.81 | 0.77–0.80 | 0.78–0.82 | 0.74–0.78 |
| 1.50 | 0.94–0.95 | 0.93–0.95 | 0.95–0.97 | 0.92–0.94 |

The safety bar is power ≥ 0.75 at `δ_min`. So a `FEASIBLE` verdict is safe iff `x ≥ 1.0` (S5 at 1.0× sits on the bar; its honest cells came back `VALIDATION_INDETERMINATE`). The 0.75× cell is never safe to declare feasible.

### 2.2 Why `f = 0.60` and `f = 0.75` fail SAFETY

At `k = 1` (fallback not conservative) with `q < 1`, `ρ(f) = max(q, f) = f ≤ 0.75`, so by Fact A the 0.75× cell is declared `FEASIBLE`, and by Fact B its power is ≈ 0.65. All 15 failures per candidate are exactly these cells: 5 design variants × 3 values of `q < 1`, all at `k = 1.00`, `x = 0.75`, `δ_min`. Nothing else failed. There were no false-feasible failures (0.5× was never declared feasible) and no size failures.

### 2.3 Why `f = 1.00` fails UTILITY

At `k = 0.5` (fallback conservative by 2×), `ρ(1.0) = 1/0.5 = 2.0`, so by Fact A the compiler demands ≈ 2 × `N_ORACLE_80` and refuses the 1.5× cell. All 60 utility failures are the `k = 0.50`, `x = 1.5`, `MUST_BE_FEASIBLE` cells (5 variants × 4 `q` × 3 effect variants), independent of `q` because `q·k ≤ 0.5 < f`.

### 2.4 Why no interpolated global scalar is justified

Under the frozen rule, for a global scalar `f` and the frozen grid:

- SAFETY at `k = 1`, `q ≤ 0.75` requires the 0.75× cell `NOT_FEASIBLE`: `ρ = f/k > 0.75`, i.e. `f > 0.75·k_max = 0.75`.
- UTILITY at `k = 0.5` requires the 1.5× cell `FEASIBLE`: `ρ = f/k ≤ 1.5`, i.e. `f ≤ 1.5·k_min = 0.75`.

The admissible set is `(0.75, 0.75]`, empty. The boundary point `f = 0.75` itself was tested and fails SAFETY by rounding (the 0.75× cell at `k = 1` is feasible at equality). Every `f ∈ (0.75, 1.0)` fails UTILITY at `k = 0.5` for the same reason `1.00` does (`ρ = f/0.5 > 1.5`). An interpolated scalar is therefore not a next step; it is already excluded by the frozen arithmetic. In general the global-scalar model admits a floor iff `k_max / k_min < 2` (the band `(0.75, 1.5]` has ratio 2); the frozen grid has `k_max / k_min = 2`.

### 2.5 Which dimensions separate the conflicting corners

| Dimension | Separates? | Evidence from the frozen run |
|---|---|---|
| `k = VAR_TRUE / VAR_FALLBACK` | **Yes, the only one.** | SAFETY breaks only at `k = 1`; UTILITY breaks only at `k = 0.5`. `k = 0.75` passes at every candidate. The compiler cannot observe `k`. |
| `q` | No, not on its own | At `k = 1` every `q < 1` fails identically; at `k = 0.5` `q` is irrelevant (`q·k < f`). `q` matters only through the product `r = q·k`, which is what the compiler sees. |
| Effect size / `δ` multiple | No | SAFETY fails only on the `δ_min` power check; the `2δ_min` and null checks pass in the same cells. UTILITY failures hit all three variants because they are feasibility verdicts, not outcomes. |
| Design family | No | S1, S3, S4 (both ICC), S5 fail in the same `(k, q, x)` cells; differences are integer rounding only. The failure is arithmetic, not inferential. |
| Size multiple `x` | Locates, does not separate | Failures sit at `x = 0.75` (safety) and `x = 1.5` (utility), the two cells adjacent to the bars; the bars themselves define this. |
| Any other | None supported | ICC level, venue correlation and event count change power by at most ≈ 0.05 and never flip a verdict. |

### 2.6 The identification theorem (root cause)

The compiler's inputs are `(DESIGN, α, δ_min, VAR_EXPOSED_ESTIMATE, VAR_FALLBACK, SAMPLE_N)`. Consider the two frozen cells

- `k = 0.5, q = 1.0, x = 1.5` (expected `MUST_BE_FEASIBLE`; UTILITY requires `FEASIBLE`), and
- `k = 1.0, q = 0.5, x = 0.75` (declared feasible ⇒ power ≈ 0.65; SAFETY requires `NOT_FEASIBLE`).

Both have `VAR_EXPOSED_ESTIMATE = 2.0`, `VAR_FALLBACK = 4.0`, the same `α` and `δ_min`, and the same sample count up to rounding (from the effective manifest: S3 135 vs 135; S1 538 vs 536; S4-icc005 17 vs 15; S4-icc015 30 vs 28; S5 35 vs 34). **The compiler is handed the same information and is required to return opposite verdicts.** Exact computation through the frozen `required_n` of the planning variances `VAR_PLANNING/VAR_FALLBACK` that satisfy both cells: S3 **empty**; S1 a single rounding point (`0.7525`, width ≤ 0.0025); S4/S5 slivers of width 0.02–0.12 that exist only because the two cells' integer counts differ by two at small `G` / event counts. No deterministic function of the compiler's inputs — scalar, piecewise, continuous, or any combination of `VAR_EXPOSED_ESTIMATE` and `VAR_FALLBACK` — passes the frozen grid, except through rounding artefacts that are by definition not structure.

Equivalent statement in the band language: the bars allow `ρ ∈ (0.75, 1.5]`, a ratio of 2; at compiler input `r = q·k = 0.5` the set of true variances consistent with that input is `{0.5·VAR_FALLBACK, 1.0·VAR_FALLBACK}`, also a ratio of 2. A closed-open band of ratio 2 cannot contain two points of ratio 2.

**ROOT_CAUSE:** `VAR_PLANNING` must be a function of information the compiler has, and the frozen 3A grid asks the compiler to be robust to a 3× unseen understatement (`q ≥ 0.33`) and a 2× unseen fallback conservatism (`k ∈ [0.5, 1]`) at once, while allowing it only a 2× band between "unsafe" and "useless". The failing object is not the number `f`; it is the pair (robustness domain, utility multiple) under which no compile-time rule can exist.

## 3. Replacement model classes (conceptual evaluation; none selected by search)

Notation: `E = VAR_EXPOSED_ESTIMATE`, `VF = VAR_FALLBACK`, `r = E/VF`.

### Class A — piecewise floor by an existing structural quantity

- **Definition.** `VAR_PLANNING = VF·f_j` on regions `r ∈ R_j` of the observable ratio `r`, or by design family.
- **Outcome-blind inputs.** `E`, `VF` (and the design family), all available at compile time.
- **Mechanism addressed.** None that the theorem allows: it is a function `g(r)` and §2.6 shows every `g(r)` fails at `r = 0.5`. Regions keyed on design family do not help because all families fail in the same cells.
- **Monotonicity / invariants.** Can be made monotone in `r`; `VAR_PLANNING ≥ E` holds iff `f_j ≥ r` on each region.
- **Degrees of freedom.** Number of regions plus one floor per region (≥ 3 for two regions).
- **Overfit risk.** High: region boundaries would be read off the failed cells (forbidden move).
- **MDE / power semantics.** Unchanged (planning side only).
- **Inference classes.** Unchanged.
- **Verdict.** `REJECTED` by §2.6.

### Class B — continuous deterministic function of an existing structural quantity

- **Definition.** `VAR_PLANNING = VF·g(r)` with `g` continuous, e.g. `g(r) = max(r, a + b·r)` or `g(r) = r^{1−w}` (log-linear shrinkage toward `VF`).
- **Outcome-blind inputs.** `E`, `VF`.
- **Mechanism addressed.** Would let the floor rise with `r` (an understated estimate near `VF` is taken as a sign `k` is near 1). But any `g(r)` is still blind at `r = 0.5` (§2.6). For the log-linear form explicitly: `ρ = q^{1−w}·k^{−w}`; SAFETY (`0.33^{1−w} > 0.75`) needs `w > 0.74`, UTILITY (`2^{w} ≤ 1.5`) needs `w ≤ 0.585`; empty.
- **Monotonicity / invariants.** Monotone in `r` by construction; `VAR_PLANNING ≥ E` iff `g(r) ≥ r`.
- **Degrees of freedom.** 1–2.
- **Overfit risk.** Moderate (few parameters) but the parameters would still be chosen to thread the grid, i.e. selected from the failed cells.
- **MDE / power semantics.** Unchanged.
- **Inference classes.** Unchanged.
- **Verdict.** `REJECTED` by §2.6.

### Class C — conservative estimator combining two existing variance terms

- **Definition.** `VAR_PLANNING = c₁·E + c₂·VF`, or `max(E, VF·h(E/VF))`, or a geometric mean.
- **Outcome-blind inputs.** `E`, `VF`.
- **Mechanism addressed.** Same as B; every such combination is a function of `(E, VF)` and therefore of `r`.
- **Degrees of freedom.** 1–2. **Overfit risk.** As B. **Semantics / inference.** Unchanged.
- **Verdict.** `REJECTED` by §2.6.

### Class D — explicit uncertainty inflation from the exposed estimate's own information

- **Definition.** `VAR_PLANNING = E · U(n_eff)`, `U(n_eff) = (n_eff − 1) / χ²_{γ, n_eff − 1}`, the one-sided `(1−γ)` upper confidence factor for a variance estimated from `n_eff` effective independent units; `γ = 0.01` fixed to the gate's own one-sided 99 % level; `VF` is retained only as the absence rule (no exposed estimate ⇒ plan at `VF`), with no floor fraction.
- **Outcome-blind inputs.** `E` and `n_eff`, the effective information count of the exposed sample after the design's dependence correction (DEFF for clusters, event count for rare-event designs). `n_eff` is a count of the exposed sample's units and is available at compile time without any outcome.
- **Mechanism addressed.** It is the only class whose protection scales with the uncertainty of `VAR_TRUE` instead of with `VF`, so it does not inherit the `k`-blindness of §2.5. It replaces "robust to an unseen understatement" by "robust to the understatement that the exposed sample's size can produce".
- **Monotonicity / invariants.** `VAR_PLANNING ≥ E` always (`U ≥ 1`); `U` decreasing in `n_eff`, `U → 1` as `n_eff → ∞`; `VAR_PLANNING` linear in `E`.
- **Degrees of freedom.** Zero free parameters once `γ` is tied to the existing 99 % level (one structural constant, not fitted).
- **Overfit risk.** None with respect to Run 1 (nothing is fitted). The real risk is **coverage**: `U` covers sampling understatement only; structural understatement (ignored dependence, regime difference) is not covered and must be stated as such.
- **MDE / power semantics.** Changes the meaning of `FEASIBLE` from "feasible at a floored plan" to "feasible at the 99 % upper bound of the true variance given the exposed information". `δ_min`, nominal power 0.80, `α` and the oracle are unchanged.
- **Inference classes.** Unchanged; `VAR_PLANNING` enters only planning.
- **Verdict.** The only class with a structural reason, **but it cannot be evaluated on the frozen 3A grid at all**: there `q` is a controlled stipulation with no `n_eff`, so `U` is undefined. Making `q` a sampling realization of an exposed estimator turns the gate into exactly the unit that spec §2 names as separate ("a sampling/calibration check of a real exposed estimator … takes no part in choosing the floor"). On any grid where `q` is still allowed to vary freely at fixed `n_eff`, class D fails for the same ratio reason: `ρ = q·U(n_eff)`, and the `q` range (3×) exceeds the band (2×).

## 4. Joint satisfiability of the frozen SAFETY and UTILITY requirements

**`SAFETY_UTILITY_JOINTLY_SATISFIABLE = NO`** on the frozen domain, for every model class considered, including class D. The proof is §2.6: two cells with identical compile-time information require opposite verdicts. This is not weakened here and no bar is changed.

The conflict is between three frozen quantities, any one of which the owner could change (none is changed by this document):

1. the robustness domain of the fallback, `k ∈ [0.5, 1.0]` (`k_max / k_min = 2`);
2. the robustness domain of the exposed estimator, `q ∈ [0.33, 1.0]`, unseen by the compiler;
3. the utility multiple `1.5×` against the safety edge `0.75×` (band ratio 2).

The general admissibility condition for the global-scalar model is `f ∈ (0.75·k_max, 1.5·k_min]`, non-empty iff `k_max / k_min < 2`. For class D the condition is that the `q` spread at fixed `n_eff` is below 2, i.e. that `q` is generated by the sampling model, not stipulated. Changing (1) or (3) is a weakening of the frozen requirements and is the owner's decision; changing (2) in the class-D direction is a change of the gate's question, also the owner's decision. This document recommends none of them; it records that **no variance model satisfies the requirements as frozen**.

## 5. Recommendation

- `GLOBAL_SCALAR_MODEL = REJECTED` (§2.4).
- Classes A, B, C: `REJECTED` (§2.6; they are all functions of `r`).
- Class D: `ADMISSIBLE_IN_PRINCIPLE / NOT_EVALUABLE_ON_FROZEN_GATE`. It is the lowest-complexity model with a structural reason (zero fitted parameters) and the only one not blind to `k`, but it needs an owner decision to redefine the gate's input (`n_eff`) and the way `q` is generated.
- **No model is recommended for freezing now.** Proposing a larger learned surface would not help: the obstruction is informational, not a lack of flexibility.

## 6. Redesign test contract (conditional; binds any future validation, executes nothing)

Applies only after an owner decision resolving §4. Then:

1. **Fresh frozen design.** A new spec `COMPILER_V3_VARIANCE_MODEL_VALIDATION_SPEC_V2.md` with its own golden manifest and builder, digests recorded in a new freeze record. Spec V1, its manifest and amendment are not edited.
2. **Fresh binding and authorization.** A new execution binding over the (new or unchanged) generator files and a new run authorization artifact with `RUN_ID = COMPILER_V3_VARIANCE_MODEL_VALIDATION_OFFICIAL_RUN_2`, `ONE_OFFICIAL_RUN_ONLY`. Run 1's binding V1/V2 and authorization V1 stay as they are.
3. **Official Run 1 classification.** `DESIGN_DEVELOPMENT_EVIDENCE` for the redesign; never confirmation; its 900 cells and their seeds are never reused as a validation surface.
4. **Independent validation surface (exact source of independence).**
   - *RNG:* a new design index space in the frozen seed formula `base = 1e12·design + 1e6·cell` (design indices disjoint from Run 1's), so every Stage A/B seed range is disjoint from Run 1 by construction and checked pairwise by the manifest validator.
   - *Grid points:* `(k, q)` values not in Run 1 (interior points of the owner-decided domain, not its corners alone), with the expected-classification anchors `0.5× MUST_NOT` / `1.5× MUST_BE` unchanged (they are bars, not tunables).
   - *Nuisance parameters:* S4 cluster counts and ICC, S5 event counts and venue correlation, S3 pair ICC, each at values not used in Run 1.
   - *Order:* model fixed in the spec → manifest built → digests frozen → binding → authorization → run. No cell of the new manifest is examined with any outcome before the run.
   - *Limits, stated:* the surface is independent of Run 1 in RNG, grid points and nuisance parameters; it is **not** independent in generator family or bars. It tests whether the model generalizes across the declared domain, not whether the domain describes real exposed estimators (that remains the separate calibration unit of spec §2).
5. **No reuse of Run 1 as confirmation**, no rerun of Run 1, no overrides, no reruns of Run 2.

## 7. Independent validation surface: existence

`INDEPENDENT_VALIDATION_SURFACE = EXISTS_IN_PRINCIPLE` (specified in §6.4). It is **not** the blocker. The blocker is §4: the next validation cannot be designed against requirements that no model can satisfy. Therefore

`NEXT_VALIDATION_POSSIBLE = NO` — reason `REDESIGN_BLOCKED_REQUIREMENTS_JOINTLY_UNSATISFIABLE`, pending an owner decision on §4 (1), (2) or (3).

## 8. Explicitly not done

No rerun, no edit or reinterpretation of Run 1 artifacts, no parameter search, no new floor, no per-cell or per-design constants, no exception list, no change to SAFETY/UTILITY bars, no code execution against outcome-bearing data, no PR, no merge, no adoption, no calibration freeze, no V2 contract adoption.
