# `COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_V1` — specification V1 (frozen; not executed)

**Status:** `FROZEN_DESIGN / EXECUTION_NOT_AUTHORIZED / NOT_RUN / NO_OUTCOME_READ`. Owner authorization of the unit: 2026-10-04 (design only). Freeze record: `COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_FREEZE_RECORD_V1.json`.

**Purpose.** Determine whether the compiler can replace the hidden robustness domain `q ∈ [0.33, 1.0]` of the frozen floor gate (`COMPILER_V3_VARIANCE_FLOOR_VALIDATION_SPEC_V1.md`, unchanged) by an **outcome-blind upper planning-variance bound `U`** computed from information actually available about the exposed variance estimator. This is **estimator calibration**, not variance-model validation; nothing here adopts a model, changes the SAFETY bar, the UTILITY 1.5× requirement, the fallback domain `k ∈ [0.5, 1.0]`, Official Run 1 or the frozen V1 design.

**Motivation (the only use of Official Run 1).** Run 1 and `COMPILER_V3_VARIANCE_MODEL_REDESIGN_DESIGN_V1.md` showed that with `q` unseen no compile-time rule can be both safe and useful. Run 1's outcome rows, seeds and grid take no further part: they select no parameter here and are not calibration evidence.

---

## 1. The exposed variance estimator the compiler actually uses

### 1.1 What exists in code today

The GV0R02 compiler (V0/V1/V2, `scripts/research/gv0r02_feasibility_compiler*.py`) has **no exposed variance estimator**. Its planning model is `POWER_PROFILE`: unit statistics are standardized to `BASE_SD = 1`, the planning SD is `BASE_SD × STRESS_SD_MULTIPLIER = 2.0` (hence `VAR_FALLBACK = 4`), and the information count is the nominal unit count, or `active·inactive/(active+inactive)` for a binary contrast. The R03 unit screen (`scripts/research/owner_cards_r03/support.py`) does the same per unit: `SE² = mean_u[ 4·(1/n_state,u + 1/n_comp,u) ] / N_units`. The exposed-data estimate of contract V2 draft §5.3 ("a design may instead freeze a variance estimate from exposed data with a declared estimator, data window and a cap") is **not implemented**. Therefore item 1 of the owner's decision is answered by **defining** the estimator that this unit calibrates, per supported inference class, and that definition is frozen here.

### 1.2 Estimator definitions by inference class (frozen)

All estimators are of the **per-unit variance** `σ²_unit` of the design's independent unit, so that the planner's SE² at any planned count `N_plan` is `σ²_unit / N_plan`. `VAR_TRUE` in this unit is the **true per-unit variance of the evaluation statistic**, i.e. `N × Var(statistic)` including all dependence among units (the long-run variance when units are serially dependent).

| Class | Supported design (contract V2 §5 forms) | Unit statistic | Estimator `V̂_A` (naive) | Dependence correction `V̂_B` | Information at compile time | `n_eff` candidate | Status of `n_eff` |
|---|---|---|---|---|---|---|---|
| `TWO_SAMPLE` | two-group contrast (binary mechanism, S1-form) | difference of arm means | pooled within-arm sample variance `s²_p` (df `n_a + n_i − 2`) | Bartlett long-run variance per arm with bandwidth `L(n)` (§1.3) | `n_a`, `n_i`, `s²_p`, `V̂_B` | `n_a + n_i − 2` (A); `⌊(n_a+n_i)/(L+1)⌋ − 1` (B) | A **exact** only under independent Gaussian observations; B **approximate** |
| `PAIRED_UNITS` | per-unit state-minus-comparator difference, sign-flip over units (R03 form, S3-form) | mean of unit differences `d_u` | sample variance `s²_d` over units (df `N − 1`) | Bartlett long-run variance of `{d_u}` with bandwidth `L(N)`; the sign-flip SE is **not** an estimator of `σ²_unit` (it includes the effect) and is excluded | `N`, `s²_d`, `V̂_B` | `N − 1` (A); `⌊N/(L+1)⌋ − 1` (B) | A exact only under independent Gaussian `d_u`; B approximate |
| `CLUSTERED` | small-G cluster-robust (dates as clusters, S4-form) | unweighted mean of cluster means | between-cluster sample variance of cluster means (df `G − 1`); this already absorbs within-cluster ICC | Bartlett long-run variance over the ordered cluster means with `L(G)` | `G`, cluster sizes `m_g`, `V̂_A`, `V̂_B` | `G − 1` (A); `⌊G/(L+1)⌋ − 1` (B) | A exact under Gaussian cluster means with equal `m_g` and independent clusters; approximate with unequal `m_g`; B approximate |
| `RARE_EVENT` | event-level clustered, venues as measurements (S5-form) | mean over events of the venue-averaged contrast | between-event sample variance of event statistics (df `n_e − 1`); venue correlation is absorbed by averaging within the event first | Bartlett long-run variance over ordered events with `L(n_e)` | `n_e`, `V̂_A`, `V̂_B` | `n_e − 1` (A); `⌊n_e/(L+1)⌋ − 1` (B) | A exact only under Gaussian homoskedastic independent events; **undefined as exact** under heteroskedastic events; B approximate |
| `ERA_STRATIFIED` | era-stratified sign-flip (S6-form) | — | — | — | — | — | **UNDEFINED**: the S6 design is excluded (freeze amendment V1); no estimator is calibrated for it |

No class assumes an iid chi-square variance law by default: class A is the chi-square law **as a candidate**, and the calibration families of §4 are built so that the law is false in most cells (dependence, heteroskedasticity, heavy tails, small `G`).

### 1.3 Frozen auxiliary definitions

- Bartlett long-run variance of an ordered sequence `x_1..x_n`: `V̂_B = γ̂_0 + 2·Σ_{h=1}^{L} (1 − h/(L+1))·γ̂_h`, `γ̂_h` the lag-`h` sample autocovariance (divisor `n`), floored at `γ̂_0 · 0.25` so that a negative-weight artefact never produces a variance below a quarter of the naive one; bandwidth `L(n) = ⌈n^{1/3}⌉` (4 at `n = 40`, 8 at `n = 400`). For `TWO_SAMPLE` the arm sequences are treated separately and pooled with df weights.
- `χ²_{γ,ν}` is the lower `γ`-quantile of the chi-square distribution with `ν` df. `γ = 0.01`, tied to the gate's one-sided 99 % level.
- `VAR_FALLBACK = (2.0 × SD_BASE)² = 4` in standardized units, unchanged.

## 2. Calibration question (frozen)

Given only compile-time information `I = (class, counts, V̂_A, V̂_B)`, does a bound `U(I)` exist with

`P( VAR_TRUE ≤ U(I) ) ≥ 0.99`

under every **MUST-support** truth-generating family of §4? Coverage is primary. Utility (§6) is secondary and is reported in full; it is never traded against coverage.

## 3. Candidate bound classes (frozen; no per-cell tuning; no learned surface)

| Class | Definition | Free parameters | Covers |
|---|---|---|---|
| **A — exact / analytic** | `U_A = V̂_A · ν_A / χ²_{0.01, ν_A}` with the exact df `ν_A` of §1.2 | 0 | sampling noise under the Gaussian independent-unit law only; exact where §1.2 says exact |
| **B — effective-df approximation** | `U_B = V̂_B · ν_B / χ²_{0.01, ν_B}` with the long-run estimator and `ν_B = ⌊n/(L+1)⌋ − 1` | 0 (bandwidth rule frozen) | sampling noise plus serial dependence up to the bandwidth; not heteroskedasticity, not tails |
| **C — design-aware simulation-calibrated factor** | `U_C = V̂_A · c(class, n)`, where `c(class, n)` is the empirical 0.99-quantile of `VAR_TRUE / V̂_A` pooled over **all MUST-support cells** of that class at that `n` on the **CAL split** (§5); a table indexed by class and `n` only, frozen after the CAL split and before the EVAL split is read | one table, never per cell, never per dependence or tail level | whatever structural understatement is inside the declared MUST domain, by construction; nothing outside it |
| **D — fallback-only reference** | `U_D = VAR_FALLBACK = 4` | 0 | the fallback domain `k ≤ 1` by assumption; it uses no exposed information and is never selected |

Preference order, frozen: A, then B, then C; the first class with `COVERAGE_PASS` is the **selected class**. D is reported beside it as the conservative reference. No other class may be added after the freeze, and none of A/B/D has a parameter to search. C is evaluated only on the EVAL split, with its table taken from the CAL split, so the factor is never selected on the data that judges it.

## 4. Truth-generating families (known `VAR_TRUE` by construction)

Base scale `SD_BASE = 1`. Every family is parameterized so that the in-domain truths sit inside the fallback domain (`VAR_TRUE ≤ VAR_FALLBACK = 4`, i.e. `k ≤ 1`); the stress and out-of-domain levels may leave it and are labelled.

| Family | Class | Grid of `n` | Structural levels (MUST) | STRESS (reported, non-decisive) | Truth formula |
|---|---|---|---|---|---|
| `F1` | `TWO_SAMPLE` | per arm `n ∈ {30, 60, 120, 250, 500}` | AR(1) across observations within each arm `φ ∈ {0, 0.3, 0.6}`; innovations `GAUSS`, `T4` (scaled to unit variance) | `φ = 0.8`; `T3` | `VAR_TRUE = n·Var(ȳ) = σ²·[1 + 2·Σ_{h=1}^{n−1}(1 − h/n)·φ^h]` per arm, `σ² = 1`; pooled over two equal arms |
| `F2` | `PAIRED_UNITS` | `N ∈ {40, 60, 100, 160, 260, 400}` (spans the R03 planning counts 41–260) | AR(1) across units `φ ∈ {0, 0.3, 0.6}`; `GAUSS`, `T4` | `φ = 0.8`; `T3` | as F1 with `N` |
| `F3` | `CLUSTERED` | `G ∈ {8, 15, 25, 40}`, nominal `m = 24` | `ICC ∈ {0.02, 0.10, 0.30}`; cluster sizes `EQUAL` or `HETERO` (`m_g` uniform on `{12..36}`, drawn per replicate); AR(1) across ordered clusters `φ_G ∈ {0, 0.3}`; `GAUSS`, `T4` on the cluster-level and unit-level innovations | `φ_G = 0.6`; `T3` | per-cluster-unit truth `(1/G)·Σ_g σ²·(ICC + (1 − ICC)/m_g)` times the AR factor over `G`, computed per replicate from the realized `m_g` |
| `F4` | `RARE_EVENT` | `n_e ∈ {30, 50, 75, 100}`, 3 venues | venue correlation `v ∈ {0.5, 0.7, 0.9}`; event scale heterogeneity `HOMO` or `HETERO` (per-event SD multiplier `exp(0.5·Z)`); AR(1) across ordered events `φ_e ∈ {0, 0.3}`; `GAUSS`, `T4` | `φ_e = 0.6`; `T3` | per-event truth `σ²·(1 + 2v)/3 × E[multiplier²]` (`E = exp(0.5)` for HETERO) times the AR factor over `n_e` |
| `F5` | all four | the family's own grid at its central dependence level | — | **OUT_OF_DOMAIN**: evaluation-window variance `= λ ×` exposed-window variance, `λ ∈ {1.25, 1.5, 2.0}` | the exposed sample is drawn at variance `1`, the truth is `λ ×` the family's truth |

**Explicit limitation labels.** Classes A and B cover **sampling** understatement (A) and **declared-bandwidth serial dependence** (B); neither covers a change of variance between the exposed window and the evaluation window. Family F5 measures that gap and is reported under the label `STRUCTURAL_UNDERSTATEMENT_NOT_COVERABLE_AT_COMPILE_TIME`; it is **non-decisive** because a between-window regime shift is outside the compiler's declared supported domain (floor spec §3B: no planning rule is asked to compensate a regime shift). Any PASS of this unit is therefore a PASS **within the declared domain only** and must be quoted with that label.

**Avoidance of Run 1 values.** Run 1 used `G ∈ {12, 20, 30}`, `ICC ∈ {0.05, 0.15}`, 40–60 events, venue correlation 0.8 / 0.95, and a `(k, q)` grid; none of these values or that grid is reused.

## 5. Protocol, seeds, independence

- **Per replicate** (one seed): draw the exposed sample of the cell's family at the cell's `n`; compute `V̂_A`, `V̂_B`; compute `U_A`, `U_B`, `U_D` (and `U_C` on the EVAL split from the frozen CAL table); compare with the replicate's `VAR_TRUE` (analytic, or computed from the realized `m_g`). **No evaluation sample is simulated and no test is run**: coverage is a comparison of a bound with a known truth. RNG substreams as in the floor generator: `SeedSequence(seed).spawn(2)`, child 0 for data, child 1 unused here (reserved).
- **Splits.** Each cell has a `CAL` split and an `EVAL` split with disjoint seed ranges. CAL is read only to build the class-C table. **All decisions (A, B, C, D) are made on EVAL.**
- **Seed space.** `base = 9·10¹² + 10⁹·family_index + 10⁶·cell_index + 10⁵·split`, Stage A `[base, base + 3 999]`, Stage B `[base, base + 19 999]`. The builder verifies pairwise disjointness of all ranges **and** disjointness from every Run 1 range (`[1.000001·10¹², 6.001068·10¹²]`, read from the Run 1 golden manifest). No Run 1 seed can be reused by construction.
- **Independence statement.** The calibration surface is independent of Run 1 in RNG, grid values, family parameterization and the quantity measured (bound coverage, not feasibility verdicts). It is **not** independent of the gate's bars or of the synthetic generator idiom; it tests whether compile-time information can bound a known truth, not whether the families describe markets.

## 6. Coverage target, utility metric, decisions, stopping rule (frozen)

- **Coverage.** Miss `= 1{VAR_TRUE > U}`. Target miss rate `≤ 0.01`. Per cell and class, one-sided exact 99 % Clopper–Pearson on the miss count (the frozen `cp.py` of the floor package, sha256 `f93702fe…`): `PASS` if `cp_upper ≤ 0.02` (tolerance `+0.01`, the same tolerance the gate gives size), `FAIL` if `cp_lower > 0.01`, else `ESCALATE`.
- **Utility.** `ρ = U / VAR_TRUE`. `UTIL = 1{ρ ≤ 1.5}`: the bound leaves a genuinely 1.5×-oracle-feasible case `FEASIBLE`. Per cell and class report `P(UTIL)` with CP bounds; a cell is `UTILITY_OK` iff `cp_lower(P(UTIL)) ≥ 0.80`. The **utility frontier** of a class is, per design class, the smallest grid `n` at which every MUST cell at that `n` is `UTILITY_OK`; `NONE` if no grid `n` qualifies. The 1.5× requirement is not altered.
- **Stopping rule.** Stage A: 4 000 EVAL replicates per cell. A cell with any `ESCALATE` (coverage or utility) draws Stage B to 20 000 pooled replicates (same seed range, same order); after Stage B an undecided check is `CALIBRATION_INDETERMINATE` and is never extended. CAL split: 4 000 replicates per cell, no escalation (the table uses the pooled quantile over cells, not a per-cell decision).
- **Preregistered analytic expectation (not an outcome).** Under independent Gaussian units class A is exact, and `P(ρ ≤ 1.5) = P(χ²_ν ≤ 1.5·χ²_{0.01,ν})` is about 0.35 at `ν = 49`, 0.68 at `ν = 99`, 0.96 at `ν = 199`; dependence and tails lower coverage of A and raise the utility frontier of every class. This expectation is recorded so that the result can be compared with it; it selects nothing.

## 7. Pass / fail rules (frozen)

1. For each class in the order A, B, C: `COVERAGE_PASS` iff every MUST cell (families F1–F4, MUST levels only) is `PASS`; `COVERAGE_FAIL` iff any MUST cell is `FAIL`; else `COVERAGE_INDETERMINATE`. The first `COVERAGE_PASS` class is the selected class. A `COVERAGE_INDETERMINATE` class blocks selection of a later class only if no later class is `COVERAGE_PASS`.
2. `ESTIMATOR_CALIBRATION_PASS` iff a selected class exists **and** for every MUST design class its utility frontier lies inside the declared realistic range (`TWO_SAMPLE` per-arm `n ≤ 250`, `PAIRED_UNITS` `N ≤ 260`, `CLUSTERED` `G ≤ 40`, `RARE_EVENT` `n_e ≤ 100`; the ranges are read from the R03 planning counts and the Run 1 design envelope, outcome-blind).
3. `ESTIMATOR_CALIBRATION_FAIL_INFORMATION_INSUFFICIENT` iff no class is `COVERAGE_PASS` (sub-reason `COVERAGE`), or the selected class has a utility frontier of `NONE` or outside the realistic range for any MUST design class (sub-reason `UTILITY`). Neither sub-reason is rescued by changing a bar, a range, the grid, or the class list.
4. `CALIBRATION_INDETERMINATE` iff neither 2 nor 3 applies after Stage B.
5. STRESS and F5 cells are reported with their own coverage and utility and are never decisive.
6. **On PASS the unit specifies**, in its result, the exact new compiler inputs and bound semantics a future variance-model validation may freeze: the inputs of the selected class (`V̂_A` or `V̂_B`, its df, the bandwidth rule, or the class-C table with its digest), `VAR_PLANNING := U(I)`, the meaning "feasible at the 99 % upper bound of the true per-unit variance within the declared domain", and the label of §4 on what is not covered. **Nothing is adopted by this unit.**

## 8. What this unit does not do

No production or product change; no PR merge; no Official Run 2; no adoption of class D of the redesign design or of any class here; no change to SAFETY, UTILITY 1.5×, `k ∈ [0.5, 1]`, Run 1 or the frozen V1 design; no reading of any calibration outcome before a separate owner execution authorization; no market data.

## 9. Freeze

Frozen 2026-10-04 (design only). Digests of this file, the grid builder and the grid are recorded in `COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_FREEZE_RECORD_V1.json`. `EXECUTION_AUTHORIZED = NO`. An executor, its binding and a run authorization are separate artifacts that do not exist yet.
