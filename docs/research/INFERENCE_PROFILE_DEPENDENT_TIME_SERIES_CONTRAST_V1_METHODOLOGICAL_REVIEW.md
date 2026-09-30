# Independent methodological review: `DEPENDENT_TIME_SERIES_CONTRAST_V1`

**Status:** `FROZEN_EVIDENCE` (review record)
**Review decision:** `PRIMARY_METHOD_RECONSIDERATION_REQUIRED`
**Reviewed contract:** `INFERENCE_PROFILE_DEPENDENT_TIME_SERIES_CONTRAST_V1` (`.md` and `.json`), commit `44ea0248c521a0729badff803ec648396a97c7ca`, contract status `REUSABLE_V2_CONTRACT_READY_FOR_INDEPENDENT_REVIEW`
**Recorded:** 2026-09-30

```
REVIEW_DECISION                       = PRIMARY_METHOD_RECONSIDERATION_REQUIRED
DEPENDENT_TIME_SERIES_CONTRAST_V1_IMPLEMENTATION_AUTHORIZED = false
PROFILE_VALIDATED                     = false
TARGET_OPENING                        = FORBIDDEN
SELF_REFERENTIAL_D7                   = true
D7_HYPOTHESIS_FAILED                  = false
D7_BITMEX_PRIMARY_TARGET_OPENED       = false
D7_PRIMARY_EFFECT_COMPUTED            = false
CONTRACT_AMENDED_BY_THIS_REVIEW       = false
NEW_PRIMARY_METHOD_SELECTED           = false
```

This review does not amend the contract, does not select a new primary method, and does not authorize implementation, validation, or target opening. It records findings for the owner and for any later amendment or redesign unit.

## Scope and provenance

- Read: the contract `.md` and `.json`, `D7_BITMEX_DEPENDENCE_INFERENCE_REVIEW_V0.md`, `D7_BITMEX_SUPPORT_AND_POWER_V0.md`, and the label mixer in `scripts/research/d7_bitmex_dependence_inference_review_v0.py`, all at `44ea024`.
- Computed: closed-form arithmetic only. Wilson bounds at `n = 10000`, binomial order-statistic probabilities for `m = 56`, and byte sums of hypothetical label strings for the label mixer.
- Not computed:
  - no random number generator was instantiated;
  - no validation draw, table draw, or simulation was run;
  - no D7 state, lag-1 pairing, D7-state autocorrelation, run length, episode persistence, or predictor-memory diagnostic was computed on BitMEX;
  - no BitMEX data file was read.
- The mixer check used the published seed value only as part of a string whose UTF-8 byte sum was formed. No PCG64 stream was created.

## 1. Self-referential D7

```
SELF_REFERENTIAL_D7 = true
Y_t = D7_STATE_{t+1} = X_{t+1}
```

The D7 outcome is the next hour's value of the same state series that defines the treatment. That has three consequences.

1. **The weights are functions of the outcome vector.** `w_t` is a function of `X_t = Y_{t-1}`, and every stratum rate `π̂_s` is built from `X` values that equal outcomes one hour earlier. Section A of the contract requires weights that do not include the outcome vector under test, and section G lists outcome-dependent weights as a disqualifier. D7 does not satisfy that rule. The D7 admission in section M does not detect this, because its check "the outcome accessor has not been called" is procedural.
2. **The current calibration model does not represent the D7 null.** The development nulls, the held-out family in section H, and the D7 power admission in section L all draw synthetic `Y` independent of a fixed `X`. The D7 null is a statement about lag-1 association inside one joint state process. Its sampling variance involves the state process's own higher-order dependence, which an independent synthetic `Y` removes. That calibration model therefore **cannot be used for D7 target admission**, for either type I or power. Conditioning on the realized `X` path does not help: it also fixes `Y`.
3. **The target is sealed procedurally, not informationally.** The support unit computes the D7 state for every constructed hour (`STATE_N = 3446`) and pins the selector (`SELECTOR_N = 3438`, digest `88b6e957…`). The target is that same series shifted by one hour, so it can be derived from the already built state path.

   Until a separately authorized opening, **any operation that reconstructs the lag-1 outcome is forbidden**. That includes, on BitMEX:
   - pairing `X_t` with `X_{t+1}`;
   - D7-state autocorrelation;
   - run lengths;
   - episode persistence;
   - predictor-memory diagnostics that use the full BitMEX D7-state path.

None of this is evidence about the D7 market effect. It does **not** mean `D7_HYPOTHESIS_FAILED = true`. `D7_HYPOTHESIS_FAILED = false`, `D7_BITMEX_PRIMARY_TARGET_OPENED = false`, and `D7_PRIMARY_EFFECT_COMPUTED = false` stand.

## 2. Critical findings

Each finding below can invalidate type-I control, the reuse guarantee, or holdout integrity.

- **F1. `c(b, q)` is not a pivotal critical value for the declared class, and the table is undefined** (section 3).
- **F2. The held-out family cannot reach the failure mode that already stopped NW721 on D7.** `X` is Markov with mean run length 1–24, independent of `Y` and of the stratum labels, with prevalence homogeneous across strata. The D7 predictor is persistent (720-hour construction windows plus clustering in high-volatility periods), strongly tied to the RV strata, and uses year strata that are contiguous in time. `NULL_3_LATENT_30D` (0.0572, Wilson upper bound 0.064) is consistent with persistence in both factors of the score. The scalar admission in section M would pass D7 into this unvalidated region.
- **F3. D7 is self-referential** (section 1).
- **F4. DGP family 4 is not a null once the configuration is fixed.** The sinusoid's period and phase are part of the per-configuration parameter vector, and `X` is fixed per configuration. Then `E[δ̂ | configuration] = Σ_t w_t m(t) ≠ 0`. A heuristic order of magnitude for the spread of that bias across configurations is `A·√L` times the noise standard deviation, which is up to about 5 for the continuous arm. Per-cell rejection rates would then be driven by how `X` happens to align with the drift, not by the method.
- **F5. The type-I gate is logically incompatible with the broad `PROFILE_REUSABLE_IF`** (section 6).
- **F6. The validation seed was published before the generator exists** (section 7).
- **F7. The admission domain is internally inconsistent and wider than the validation support** (section 5).

## 3. Fixed-b pivotality

Under `H0`, write `u_t = Y_t − m_s` and `z_t = w_t u_t`, so that `δ̂ = Σ z_t`. The score is `v_t = z_t − w_t ū_s`, and its partial sums are

```
S_v(r) = S_z(r) − Σ_s ū_s · W_s(r),   where W_s(r) = Σ_{t ≤ rT, t ∈ s} w_t
```

The reference `W(1)/√Q_b(W)` requires two things:
- `S_z` converges to `σW(r)` with a **constant** `σ`;
- the second term is negligible.

Because the score is not centered at `δ̂`, the functional is taken on a Brownian motion, not on a Brownian bridge.

Quantities that change the null distribution but are not in `(b, q)`:

| Quantity | Enters the null distribution | Mechanism |
|---|---|---|
| Local long-run variance of the score over time | yes | `S_z` converges to `∫λ dW`, and the t-statistic's limit `W_λ(1)/√Q_b(W_λ)` depends on the whole path `λ(·)` |
| Treatment prevalence, stratum shares and imbalance, choice of weight constructor | yes, through `λ(·)` | local weight scale differs by stratum: `(1−π_s)/K` against `−π_s/K`, or `−(K_s/K)/(N_s−K_s)` |
| Time layout of strata | yes | with prevalence drifting inside a stratum, `W_s(r) = O(T/K)`, and the whole geometry `W_s(·)` enters the limit |
| `q` alone | not in the limit | with interleaved strata and stationary `X`, the `ū_s W_s` term vanishes; the table's `q` index records only finite-sample effects at `N_GRID = 4000` on contiguous equal strata |
| Structural gaps | yes | the functional becomes a sum over segments and depends on segment lengths relative to `H`; the table has no gaps |
| Weight concentration | yes | Lindeberg requires `max w_t² / Σ w_t² → 0`; section G has no bound |
| Binary outcomes with small `p` or small `K` | yes, in finite samples | skewness of order `O(1/√K_eff)` under a one-sided test |
| Conditional heteroskedasticity and outcome regimes | yes | same `λ(·)`; the outcome side is unknown before opening |

Assessment of the remedies:

- **Adding table dimensions** is not sufficient. The nuisance is a set of functions, `λ(·)` and `W_s(·)`, plus the gap layout, not a finite set of scalars.
- **Critical values conditional on the concrete outcome-blind geometry**, simulated at the actual `T`, would handle the weight, stratum, gap, and bandwidth part. They would not handle the outcome-side variance profile. For self-referential hypotheses they are not outcome-blind.
- **Narrowing the domain** is needed in any case (homogeneity, concentration, memory), but it does not rescue a table-based pivot.
- **Another construction** is needed for the outcome-side variance profile. One candidate is a dependent wild bootstrap of the same studentized statistic with multiplier bandwidth equal to the declared bandwidth. The contract's reason for rejecting bootstraps ("resampling support") was derived from the block bootstrap, not from a dependent wild bootstrap. Validity under non-stationary volatility would have to be established analytically before any selection. This review names the candidate and does not select it.

Assumptions the reusable profile needs, which the contract does not state:

- **A1.** `Σ w_t E[Y_t | geometry] = 0` under `H0`. This fails when a deterministic or slow mean component aligns with the weights (F4).
- **A2.** The local long-run variance of the score is homogeneous over time, in both geometry and outcome.
- **A3.** Score memory is much smaller than the bandwidth and than `T`.
- **A4.** The effect of estimating `ū_s` is negligible: no within-stratum drift in prevalence, and no outcome memory comparable to stratum length.
- **A5.** The products omitted at gaps are negligible (`#gaps · H / T` small), or the gap functional is modelled explicitly.
- **A6.** A Lindeberg-type bound holds on the weights.
- **A7.** The weights are outcome-free. D7 fails this assumption (section 1).

Table construction (section E of the contract):

- How `X` is generated in the table is not specified, so "the same t-statistic" is not defined.
- `N_GRID = 4000` makes this a finite-sample table, not a limit table.
- Rows with `b > 0.05` can never be used.
- The Monte Carlo standard-error method for the 0.95 quantile is not specified. Two options are an order-statistic binomial interval or at least 100 independent sections.
- The expected standard error is about `3.1·10⁻⁴ / f(c)`, which is about 0.003–0.005. The stop rule can therefore trip on a purely numerical basis.
- A naive build is on the order of `10¹⁴` operations; the build needs the O(N) partial-sum form of the Bartlett estimator.

Because the score is not centered at `δ̂`, `LRV ≈ LRV₀ + (H+1)·δ²/T` under the alternative. So `t ≤ √(T/(H+1)) ≈ 1/√b`, which is about 6.5 for D7 and about 4.5 at `b = 0.05`.

## 4. Horizon semantics

`H` conflates four different quantities:

- predictor-construction overlap (720 for D7);
- score overlap (721 for D7), which is a **lower** bound on the needed bandwidth;
- target-process dependence (volatility and volume clustering);
- low-frequency regime persistence (up to 4000 hours in the family itself).

Construction overlap marks the end of mechanical dependence. It is not an upper bound on score memory.

Regimes up to 4000 hours are consistent with a bandwidth tied to `H` in only two cases:
- score memory is short because `X` has short memory, which holds in the validation family but not for D7;
- the domain excludes memory at or beyond the bandwidth.

Candidate replacement fields, as inputs to a later unit:

| Field | Meaning |
|---|---|
| `PREDICTOR_CONSTRUCTION_OVERLAP` | Overlap of inputs used to build `X` |
| `TARGET_CONSTRUCTION_OVERLAP` | Overlap of inputs used to build `Y` |
| `SCORE_MECHANICAL_OVERLAP` | Largest mechanical overlap between score terms; a lower bound on the bandwidth |
| `PREDICTOR_MEMORY_ENVELOPE` | Serial dependence of `X`. For self-referential hypotheses it may come only from exposed surfaces, never from the protected target surface. |
| `OUTCOME_MEMORY_PRIOR` | Outcome memory taken from external or exposed data, with a written justification |
| `SCORE_MEMORY_BOUND` | Derived by a frozen rule from the two envelopes above |
| `BANDWIDTH` | `max(SCORE_MECHANICAL_OVERLAP, κ·SCORE_MEMORY_BOUND)`, with `κ` fixed in the profile |
| `SELF_REFERENTIAL` | Whether `Y` is a lead of `X` |
| `INAPPLICABLE` | Set when the score memory bound exceeds a profile-set fraction of `T` |

The bandwidth is never chosen from validation results.

`N_EFF_CONSERVATIVE_PRE_OUTCOME = T/(1+2H)` is about 21.0 for D7. It is a count of disjoint windows of length `2H+1`. It is neither an effective-sample-size estimate nor a conservative bound. Candidate change: rename it to `HORIZON_WINDOW_COUNT` with `IS_EFFECTIVE_SAMPLE_SIZE = false`, and bar the feasibility compiler from using it for MDE or power.

## 5. Validation domain

The proposed validation can support at most the following population:

- `T` in 8000–80000 and `q` in 4–32;
- effectively `b ∈ (0.005, 0.05]`, because the contract also requires `T/H ≥ 20`;
- time-homogeneous Markov `X` with run length 1–24, independent of strata and of `Y`, with homogeneous per-stratum prevalence;
- strata that interleave as iid labels;
- at most three uniformly placed gaps;
- at least five treated and five control rows in every stratum;
- the seven outcome families with `Y` independent of `X`, conditional on one fixed `X` path per configuration. Family 4 is not a null (F4).

Not supported:

- persistent or clustered `X`;
- dependence between `X` and the strata;
- strata that are contiguous in time;
- dispersed per-stratum prevalence. The D7 fine cells range from about 0.02 to 0.77.
- concentrated weights;
- strata with fewer than five treated or five control rows;
- self-referential `Y`;
- corner combinations that the redraw loop systematically removes, for example `T ≈ 8000` with prevalence near 0.03 and `q` near 32.

Section G describes a box of marginal bounds, not the joint validation support. It also contradicts itself: `T/H ≥ 20` implies `b ≤ 0.05`, yet it lists `b ∈ (0.005, 0.10]`.

Generic versus D7-specific layers:

- The generic profile carries D7-shaped constants: a prevalence range centred on D7's 0.113, the binary power effect 0.05 (D7's practical threshold), the stress duration of at least 720 hours (D7's `H`), and the `H+1` Bartlett convention.
- In the other direction, the abstraction drops information that valid inference needs: the memory of `X`, the dependence of `X` on strata, the time layout of strata, and the relation between `Y` and `X`.

## 6. Type-I gate and reuse

Arithmetic at `n = 10000`, Wilson `z = 1.959963984540054`:

- The Wilson upper bound first exceeds 0.06 at 554 rejections.
- The lower bound first exceeds 0.06 at 647 rejections. At 646 rejections the upper bound is 0.06959.
- The upper bound first exceeds 0.075 at 699 rejections.
- **Rule 4 therefore never binds when `n ≥ 10000`.** Rule 3 already caps admissible cells below an upper bound of 0.0696.
- A cell with true size 0.065 passes rule 3 with probability about 0.44.
- A cell with true size 0.055 has an upper bound above 0.06 with probability about 0.44.

Rule 2 interpolates the 50th and 51st of the 56 ordered upper bounds. For the population 90th percentile of the per-cell upper bounds:

- `P(q90 ≤ X_(50)) ≈ 0.33`;
- `P(q90 ≤ X_(51)) ≈ 0.49`;
- `P(q90 ≤ X_(55)) ≈ 0.98`.

So rule 2 is closer to a point estimate than to a bound. It also stacks within-cell Monte Carlo uncertainty on top of configuration sampling without accounting for them jointly.

Guarantees under the alternative rules:

| Rule | What it would guarantee |
|---|---|
| Tolerance form, `X_(55) ≤ 0.06` | About 98% confidence that at least 90% of the configuration distribution has upper bound ≤ 0.06. It says nothing about where the other 10% lies. |
| Šidák-simultaneous upper bounds | All sampled configurations are ≤ 0.06, for those 56 configurations only |
| Hypothesis-specific admission | Type-I control on the concrete geometry of the hypothesis |

For an unseen hypothesis in the worst decile, the contract provides no evidence that type I is controlled.

A future hypothesis inside section G therefore **cannot** safely reuse the profile without its own outcome-blind type-I admission on its concrete geometry. A two-gate architecture would require the following:

- **Gate 1:** generic profile validation, as a screen.
- **Gate 2:** hypothesis-specific type-I admission, with all of the following:
  - method, statistic, critical-value rule, and bandwidth are frozen before gate 2;
  - inputs are only the frozen `InferenceProblem`;
  - the profile, not the hypothesis, owns the null battery and its parameter distributions;
  - low-frequency mean components are redrawn on every path;
  - the number of simulations and the acceptance rule are fixed in advance;
  - the seed is a hash of the tree, the beacon value, and the geometry digest;
  - the run is one-shot, and a FAIL makes the hypothesis ineligible for the profile. No edits to `H`, strata, or weights are allowed. A changed hypothesis is a new version, and the failure stays in the ledger.
- **Self-referential hypotheses:** gate 2 cannot use the real `X` path. It needs a joint synthetic generator that applies the hypothesis's own construction code to synthetic market variables whose memory comes from exposed priors, with the null true by construction. Otherwise the result is `INAPPLICABLE`.

## 7. Holdout integrity

`VALIDATION_MASTER_SEED = 20260930427` gives reproducibility but not holdout independence.

- The generator code is written after the seed is known. Its draw order, label strings beyond the prefix `dts-v1:`, and redraw loop together determine which configurations are sampled. Knowing the seed can therefore turn implementation choices into sample selection, even without intent.
- The rule "no changes after the first draw" cannot be verified.

A procedure that needs no secrecy:

1. Freeze the procedure, the distributions, the configuration count, the algorithm, and the exact label format.
2. Freeze the implementation tree.
3. Derive the seed as `SHA-256(tree_hash ‖ external beacon value ‖ "dts-v1")`. The beacon is named in advance and published only after the freeze, for example a drand round or the BTC block hash at a fixed height.
4. Derive the table seed the same way.

The label mixer `mix = Σ byte_i · i` is a weighted byte sum of the string `"{seed}:{label}"`, not a digest. A hypothetical scheme of 216 labels produced no collision, with mix values from 31,204 to 76,259, but uniqueness is not guaranteed. The mixer needs hash-based stream spawning and a uniqueness assertion before any draw.

## 8. Power contract: unresolved degrees of freedom

- Power geometry labels and streams are specified only as "distinct".
- Whether the power geometries share the type-I geometry distribution and redraw rule.
- The base arm uses one draw of `φ ~ U(0.05, 0.95)` per geometry. At `φ = 0.95`, an effect of 0.25 innovation SD is about 0.08 marginal SD.
- How the stress condition "duration at least 720" is sampled: rejection sampling, or a truncated log-uniform on [720, 4000].
- The binary base rate: drawn, or stratum-specific.
- The effect-injection form: additive on the probability, or a latent-threshold shift in the Gaussian copula; a common gap, a common odds ratio, or a common relative risk.
- What "pool-preserving" means, and which rows are shifted.
- Whether the population `δ` is computed on the realized or the expected geometry.
- Whether the realized `δ` is recorded after clipping, and which probabilities the 5% clipping threshold is measured on.
- For D7:
  - the synthetic `Y` is independent of `X`, which does not represent D7 (section 1);
  - there is one `φ` draw and one duration draw;
  - the source of the stratum base rates is not stated;
  - the labels are not stated.

For reference, the imposition that the contract text implies for D7 is the following:

- `δ = Σ_s (K_s/K)(1−π_s)·g_s`.
- With a common gap, `g = 0.05 / 0.8037903043858667 ≈ 0.0622`.
- Pool-preserving arms: `p1_s = m_s + (1−π_s)·g` and `p0_s = m_s − π_s·g`.
- The bounds require `m_s ≥ 0.01 + 0.0622·π_s` and `m_s ≤ 0.99 − 0.0622·(1−π_s)`.
- In the copula, `p_t` enters through a per-row threshold `Φ⁻¹(1 − p_t)` on a common latent AR process.

Every one of these choices must be frozen before any power run. For D7, the synthetic-`Y` power model is not admissible (section 1).

## 9. Amendment inputs for a later unit

These are listed without choosing among the options. They are not changes made by this review.

1. The reference-distribution construction needs a theory-based decision before any draw. The options considered in section 3 include geometry-conditional simulated fixed-b critical values and a dependent wild bootstrap of the same statistic. The decision must be accompanied by an analytic account of assumptions A1–A7.
2. Introduce a `SELF_REFERENTIAL` class. Either exclude such hypotheses from the profile, or require a joint null generator. Make "weights and `π̂` do not contain `Y`" a computed check.
3. Replace `H` with the fields in section 4.
4. Extend the validation family: persistent and clustered `X`, strata-dependent `X`, contiguous strata, dispersed stratum prevalence, and concentrated weights. Redraw low-frequency mean components on every path.
5. Admission: fix the `b` inconsistency; add per-stratum arm minima, a weight-concentration bound, an `X` memory envelope, a strata-contiguity flag, and the `SELF_REFERENTIAL` flag. Define the domain as the joint validation support.
6. Adopt the two-gate architecture in section 6.
7. State which guarantee the type-I rule is meant to provide, choose `n` and the rule for it, and remove or justify rule 4.
8. Adopt the seed and beacon procedure, freeze the label format, and replace the mixer.
9. Freeze every power degree of freedom listed in section 8.
10. Rename or remove `N_EFF_CONSERVATIVE_PRE_OUTCOME`.
11. If a table survives, specify how `X` is generated in it, the Monte Carlo standard-error method, and a predeclared escalation of `M`.

## 10. D7 status

```
SELF_REFERENTIAL_D7              = true
D7_HYPOTHESIS_FAILED             = false
D7_BITMEX_PRIMARY_TARGET_OPENED  = false
D7_PRIMARY_EFFECT_COMPUTED       = false
```

The findings concern the inference method, the validation design, and the procedure. They are not evidence about the D7 market effect, and they do not mean `D7_HYPOTHESIS_FAILED = true`.

The target is procedurally sealed but derivable from the already built state path. Until a separately authorized opening, every operation that reconstructs the lag-1 outcome on BitMEX is forbidden. That includes lag-1 pairing, D7-state autocorrelation, run lengths, episode persistence, and predictor-memory diagnostics that use the full BitMEX D7-state path.
