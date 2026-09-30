# Reusable inference profile: dependent time-series contrast V1

**Contract:** `INFERENCE_PROFILE_DEPENDENT_TIME_SERIES_CONTRAST_V1`

**Decision:** `REUSABLE_V2_CONTRACT_READY_FOR_INDEPENDENT_REVIEW`

This unit freezes a reusable inference contract. It does not implement the
profile, draw the held-out validation, or open any market outcome.
`VALIDATION_EXECUTED = false`. `IMPLEMENTATION_AUTHORIZED = false`.
`PROFILE_VALIDATED = false`. `TARGET_OPENING = FORBIDDEN`.

D7 is the first intended user of the profile. D7 is not the profile.
`D7_V2_ESTIMAND_CHANGED = false`.
`V2_AUTOMATIC_METHOD_SWITCHING = false`.
`D7_HYPOTHESIS_FAILED = false`.
`D7_BITMEX_PRIMARY_TARGET_OPENED = false`.
`D7_PRIMARY_EFFECT_COMPUTED = false`.

Machine-readable constants live in
`INFERENCE_PROFILE_DEPENDENT_TIME_SERIES_CONTRAST_V1.json`.
If prose and JSON disagree, the JSON constants win and the prose must be
corrected before validation starts. Neither file authorizes a run.

Development evidence that must not be reused as V2 acceptance:

- NULL_0 through NULL_4 and every forensic diagnostic computed from them;
- seeds `20260930171`, `20260930181`, `20260930211`, `20260930311`,
  `20260930317`.

The amended NW721 result stands: the normal-critical-value instrument was
not validated. That result does not choose the V1 critical value, the
validation seed, or the geometry distribution.

## A. General architecture

A hypothesis supplies an inference problem. A registered profile decides
whether that problem is in its validated domain and, if it is, produces
one reference distribution. The hypothesis does not own the critical value.

```
InferenceProblem
    -> InferenceProfileRegistry
        -> InferenceProfile
            -> CalibrationContract
                -> ProfileValidationResult
            -> HypothesisAdmissionResult
            -> PowerResult
            -> InferenceResult
    -> TargetOpeningDecision
```

### Hypothesis-specific layer

The hypothesis defines the economic question. Minimum inputs:

| Field | Role |
| --- | --- |
| `hypothesis_id` | Stable name. Not read by the statistic. |
| `time_index` | Ordered decision index. |
| `outcome_definition` | Accessor name. Bytes stay unread until a target-opening decision allows them. |
| `estimand` | Must be `delta = sum_t w_t Y_t` for this profile. |
| `treatment_or_state` | Indicator `X_t`. |
| `eligibility_mask` | Rows allowed into the contrast. |
| `strata` | Label per row. |
| `contrast_weights` | Numeric `w_t`, or a named constructor plus the inputs that determine it. |
| `structural_gaps` | Breaks that the autocovariance must not cross. |
| `nominal_sample` | `T_index`, candidate count `K`, stratum count `q`. |
| `structural_dependence_horizon` | `H` in index steps, or an explicit refusal if no structural horizon exists. |
| `horizon_justification` | Construction or sampling argument, written before the outcome is opened. |
| `practical_effect_threshold` | Applied by the hypothesis layer after the statistical result. |
| `test_direction` | This profile accepts only `ONE_SIDED_UPPER`. |
| `support_requirements` | Minimum arm sizes the hypothesis itself requires. |
| `temporal_gate` | Optional hypothesis object. The profile does not read it. |

Weights, strata, gaps, eligibility, and `H` must be functions of
information that does not include the outcome vector under test.

### Generic inference layer

The profile owns:

- reference-distribution construction;
- long-run variance;
- the test statistic and its critical value;
- the p-value;
- type-I calibration and its provenance;
- profile-level power and MDE;
- the held-out validation record;
- the admission decision;
- the target-opening recommendation.

The profile does not know what D7 means. A D7 adapter may only fill
`InferenceProblem`. There is no `D7InferenceV2` entry point.

`InferenceProfileRegistry` maps a profile id to one implementation.
Adding a profile is a new id. A failed id is not edited into a pass.

## B. Inference taxonomy

The compiler names one class. It does not move a hypothesis into a class
because an implementation exists.

### A. `DEPENDENT_TIME_SERIES_CONTRAST`

Ordered panel, serially dependent numeric outcome, weighted linear
contrast, weak or locally stationary dependence with a declared horizon.
State-versus-control hourly or 5-minute panels, volatility clustering,
and persistent regimes belong here when the other inclusion conditions
hold. D7 belongs here. The only validated-intent profile in this class
is `DEPENDENT_TIME_SERIES_CONTRAST_V1`. It is not validated until the
held-out family passes.

### B. `EVENT_LEVEL_INDEPENDENT_OR_WEAKLY_DEPENDENT`

Sparse scheduled events with separated windows, such as FOMC or CPI
event studies, where the resampling or randomization unit is the event.
Exact or event-level permutation inference is the natural design. Those
hypotheses must not use V1.

### C. `GROUP_OR_PANEL_INVARIANCE`

Exchangeability inside predeclared groups, days, or venues, where the
dependence that matters is the group rather than the time order.
Permutation within groups is the natural design. Those hypotheses must
not use V1.

### D. `OTHER_OR_UNSUPPORTED`

Anything else, including a dependent time-series contrast whose geometry
or horizon falls outside the validated domain. The registry returns
`UNSUPPORTED` and does not substitute V1.

## C. D7 profile

`REUSABLE_PROFILE_ID = DEPENDENT_TIME_SERIES_CONTRAST_V1`

`PRIMARY_D7_V2_METHOD = FIXED_B_BARTLETT_HAC`

The method is fixed-b Bartlett HAC on the hypothesis-supplied weighted
contrast. D7's adapter sets `H = 721`. The profile stores that number
only as the problem's horizon, not as its own constant.

### Why this candidate

The estimand stayed centered and approximately symmetric under the
development nulls. The normal critical value did not price the
finite-sample noise of the long-run variance under slow dependence.
Lag truncation was a small part of that distortion. Fixed-b keeps the
same contrast and the same Bartlett long-run variance, and replaces the
normal critical value with a critical value that depends on `b = H/T`.
That is a property of the inference class, not a D7 patch.

### Candidates not selected

**Dependent wild bootstrap or stationary bootstrap.** Compatible with a
weighted contrast and with conditional heteroskedasticity when the
multiplier or block matches the dependence. The development failure mode
was too little resampling support once blocks are long enough for slow
regimes, plus an unstable one-sided percentile. An ex-ante block rule
tied to `H` does not create blocks the sample does not have. Block
length would remain a shopping parameter. Not the primary profile.

**Subsampling with a predeclared window.** Compatible with a weighted
contrast. Window length is a second tuning parameter. Windows long
enough for a slow regime leave few subsets, so the attainable alpha is
coarse, and overlapping subsets are not an exchangeable reference.
Not the primary profile.

Neither candidate is a fallback if V1 fails validation.

## D. Estimand

`D7_V2_ESTIMAND_CHANGED = false`

Preserved exactly:

- D7 state definition and eligible-control definition;
- calendar year × RV-bucket strata;
- `delta = sum_s (K_s/K) * (mean(Y|X=1,s) - mean(Y|eligible,s))`;
- practical gate `delta_hat >= 0.05`;
- positive one-sided hypothesis.

The stratum-FE slope `delta / c` is not the estimand.
`c = 0.8037903043858667` on the pinned BitMEX stratum counts remains a
scale note, not a new claim. A method that needs a different economic
contrast is rejected rather than used.

The gap rule below changes how products enter the long-run variance.
It does not change `delta`.

## E. Exact statistic

### Contrast estimator

`delta_hat = sum_t w_t Y_t`

on the ordered contrast index. Rows outside the eligibility mask have
weight 0. For every stratum `s`, `sum_{t in s} w_t = 0` up to absolute
tolerance `1e-9`.

Two constructors are in the validated domain.

**`WITHIN_STRATUM_RATE_MATCHED`.** With `pi_s = K_s/N_s` and
`K = sum_s K_s`:

- candidate in `s`: `w = (1 - pi_s) / K`;
- other eligible row in `s`: `w = -pi_s / K`.

This is D7's contrast. The profile accepts the resulting numbers. It
does not contain a D7 formula.

**`EQUAL_WITHIN_STRATUM`.**

- candidate in `s`: `w = 1/K`;
- other eligible row in `s`: `w = -(K_s/K) / (N_s - K_s)`.

This is `sum_s (K_s/K) * (mean_1,s - mean_0,s)`.

### Long-run variance

Let `mu_s` be the eligible-pool mean of `Y` in stratum `s`, and

`v_t = w_t * (Y_t - mu_s(t))`.

Because the weights sum to zero inside each stratum,
`delta_hat = sum_t v_t`.

Structural gaps partition the index into contiguous segments. Year
boundaries are not gaps unless the hypothesis lists them. D7's December
2016 hole is a structural gap. D7's year boundaries are strata, not
dependence breaks.

`gamma(h) = sum_{segments} sum_{t: t and t+h in the segment} v_t v_{t+h}`

for `h = 0..H`. Products that would cross a gap are omitted.

Bartlett weights, same construction as the reviewed HAC:

- `k(0) = 1`;
- `k(h) = 1 - h/(H+1)` for `h = 1..H`.

`LRV = k(0) * gamma(0) + 2 * sum_{h=1}^{H} k(h) * gamma(h)`.

`z = delta_hat / sqrt(LRV)` when `LRV > 0`.

### Critical value

`q` is the number of strata with a positive eligible count.
`T_index` is the number of rows on the ordered contrast index.
`b = H / T_index`.

`c(b, q)` is the one-sided 0.95 quantile of the fixed-b Bartlett
t-statistic on Gaussian white noise, indexed only by `b` and `q`.

Table construction, executed only in a later implementation unit, uses
no market outcome and no validation seed:

- seed `FIXED_B_LIMIT_TABLE_SEED = 20260930431`;
- `q = 1..32` exact;
- `b = 0.005, 0.010, ..., 0.100`;
- `N_GRID = 4000` iid `N(0,1)` rows;
- `M_PATHS = 500000` paths per cell;
- nuisance design inside the table only: `q` contiguous equal strata,
  prevalence 0.10, rate-matched weights, no gaps;
- percentile method `linear`;
- store quantiles at probabilities `k/1000` for `k = 1..999`.

At use time, interpolate `c` linearly in `b` between adjacent grid
points at that integer `q`. Do not extrapolate in `b`. Do not
interpolate in `q`. If `b` is outside `(0.005, 0.10]` or `q` is outside
`1..32`, the profile is inapplicable.

The table's contiguous strata are a declared nuisance, not a claim that
real strata are contiguous. Validation geometries interleave strata.
If the `(b, q)` table does not control type I on those geometries, V1
fails. The critical value is not refit.

The implementation must record the Monte Carlo standard error of each
stored 0.95 quantile. If any cell's batch standard error exceeds
`0.005`, table construction stops with
`CRITICAL_VALUE_TOLERANCE_NOT_MET` and validation does not start.
`0.005` is a numerical tolerance on an outcome-free functional. It is
not a second type-I ceiling.

### Decision and p-value

Reject `H0: delta <= 0` only when `LRV > 0`, `delta_hat > 0`, and
`z > c(b, q)`.

If `LRV <= 0` or `delta_hat <= 0`, do not reject. The reported p-value
is 1.

Otherwise the p-value is read from the stored quantile grid by monotone
interpolation. Values below `0.001` are reported as `<0.001`.
`MIN_ATTAINABLE_P = 0.001`. Nominal alpha 0.05 is attainable inside
the grid. There is no extra inflation factor and no residual lag picker.

## F. Generic dependence rule

`H` is `structural_dependence_horizon` on the inference problem.

The profile does not estimate `H` from residuals, from a lag search, or
from calibration pass rates. A future hypothesis supplies `H` with a
written construction or sampling argument before its outcome is opened.
`b = H / T_index` is then determined by the sample. The critical value
is the table value at that `b` and `q`.

D7's argument, unchanged: the 720-hour trailing windows and the
next-hour target still share a construction input at valid-hour
separation 721, and that overlap is gone at 722. So the D7 adapter
sets `H = 721`. A different hypothesis with the same mathematics and a
different construction horizon supplies a different `H` and does not
require a profile edit.

## G. Profile applicability

All of the following are required:

- estimand is one weighted linear contrast, weights sum to 0 within
  each stratum;
- ordered time index;
- numeric outcome (binary included);
- one-sided upper alternative;
- weights, strata, gaps, and `H` are outcome-free;
- `H` has an ex-ante structural justification;
- `T_index` in `[8000, 80000]`;
- `q` in `[4, 32]`;
- prevalence of strictly positive weights in `[0.03, 0.25]`;
- structural gap count in `[0, 3]`;
- `K >= 200` and `T_index / H >= 20`;
- `b = H/T_index` in `(0.005, 0.10]`;
- weight scheme is rate-matched or equal-within-stratum, or another
  numeric weight vector that meets the same support bounds;
- dependence assumption stated by the hypothesis is weak dependence or
  local stationarity inside segments, with memory on the scale of `H`,
  not a unit root and not long memory beyond the `b` cap.

Disqualifiers, any one of which returns `UNSUPPORTED` for this profile:

- no structural `H`;
- exact finite-sample randomization or event-level permutation is the
  natural design;
- event count is too small for the support bounds above;
- group or panel exchangeability dominates the time dependence;
- estimand is nonlinear or is not a single linear contrast;
- two-sided or lower-tailed test;
- geometry outside the bounds above;
- the hypothesis asserts a unit root or long memory;
- outcome-dependent weights or an outcome-dependent horizon;
- a discrete reference distribution whose minimum p-value cannot
  attain alpha 0.05 and the hypothesis requires that exact discrete
  test.

The validation domain is the applicability domain. Table rows with
`q < 4` exist so the grid is complete; they are not an invitation to
use the profile on a three-stratum design.

## H. Generic held-out validation family

The family validates `DEPENDENT_TIME_SERIES_CONTRAST_V1`, not D7's
weight vector. Development NULL_0–NULL_4 are not members.

Each configuration draws a new geometry and a new DGP parameter vector.
Under every null, the conditional mean of `Y` does not depend on `X`.
`X` is a Markov treatment indicator, independent of `Y`, with prevalence
`pi` and mean run length `L`.

### Geometries

Drawn under `VALIDATION_MASTER_SEED`, label prefix `dts-v1:`:

- `T` log-uniform integer on `[8000, 80000]`;
- `q` uniform integer on `4..32`;
- prevalence uniform on `(0.03, 0.25)`;
- stratum shares `Dirichlet(1..1)`, redraw if any share is above 0.70
  or below 0.02;
- stratum labels drawn independently so strata interleave in time;
- gap count uniform on `{0,1,2,3}`, interior cuts, segments nonempty;
- `b` log-uniform on `(0.005, 0.10]`, `H = round(b T)`, kept inside
  the open-closed interval;
- treatment mean run length log-uniform on `[1, 24]`;
- redraw up to 1000 times if `K < 200`, `T/H < 20`, or any stratum has
  fewer than 5 treated or 5 control rows.

If a configuration still fails those constraints,
`DESIGN_DRAW_FAILED` fails the profile. The configuration is not
dropped and the bounds are not widened.

Eight configuration slots per family:

| Slot | Outcome | Weights |
| --- | --- | --- |
| 0, 1 | binary | rate-matched |
| 2, 3 | binary | equal-within-stratum |
| 4, 5 | continuous | rate-matched |
| 6, 7 | continuous | equal-within-stratum |

### DGP families

1. **IID.** Binary: `Bernoulli(p)`, `p` uniform `(0.05, 0.30)`.
   Continuous: iid `N(0,1)`.
2. **Short or medium AR.** `phi` uniform `(0.05, 0.95)`. Stationary
   Gaussian AR(1), reset at gaps only. Binary uses the Gaussian copula
   threshold at marginal `p` uniform `(0.05, 0.30)`. Continuous outcome
   is the AR itself.
3. **Persistent regimes.** Mean duration `D` log-uniform on
   `[24, 4000]`, so values below and above 720 are both in the family.
   Two-state Markov, stationary 50/50, `p_stay = 1 - 1/D`, reset at
   gaps only, not at strata. Binary: `p_low` uniform `(0.02, 0.08)`,
   `p_high` uniform `(0.15, 0.40)`, require `p_high > p_low + 0.05`
   and mixture mean in `(0.05, 0.30)`. Continuous: within-regime
   `N(mu, 1)` with mean gap uniform on `(0.25, 1.5)`.
4. **Low-frequency drift.** Sinusoid, period log-uniform `[48, 5000]`,
   phase uniform `(0, 2π)`, common across strata, independent of `X`.
   Binary amplitude uniform `(0.05, 0.20)` around a base rate uniform
   `(0.10, 0.25)`, probabilities clipped to `(0.02, 0.40)`. Continuous
   amplitude uniform `(0.20, 1.0)` plus `N(0,1)`.
5. **Conditional heteroskedasticity, constant mean.** Continuous:
   `Y_t = σ_t ε_t`, `ε` iid `N(0,1)`, `σ_t = exp(κ G_t)`, `G` a
   unit-variance AR(1) with `phi_g` uniform `(0.50, 0.98)` and `κ`
   uniform `(0.25, 0.75)`. A Bernoulli random variable has no free
   variance once its conditional mean is fixed, so the four binary
   slots in this family are reassigned to additional continuous
   stochastic-volatility draws. That reassignment is part of the
   freeze, not a post-result deletion.
6. **Heavier tails.** Degrees of freedom uniform on `{3,4,5,6,8}`.
   `phi` uniform `(0, 0.8)`. Continuous: AR with standardized t
   innovations. Binary: the same symmetric AR-t latent, threshold 0,
   so the marginal probability is 0.5 by symmetry and the copula has
   t tails. A Gaussian PIT is not used as a stand-in for tail
   dependence.
7. **Persistence plus scale.** Continuous: family-3 mean regime plus
   family-5 scale, `Y_t = μ_{R_t} + σ_t ε_t`, mean independent of `X`.
   Binary: family-3 regime probabilities plus a within-regime Gaussian
   AR copula, `phi` uniform `(0.05, 0.80)`. The binary arm uses that
   substitute because a Bernoulli regime already spends its one
   parameter on the mean.

Parameter redraws that miss a family's stated inequalities use the same
1000-draw cap. Exceeding the cap is `DESIGN_DRAW_FAILED`.

## I. Validation seed

`VALIDATION_MASTER_SEED = 20260930427`

`FIXED_B_LIMIT_TABLE_SEED = 20260930431`

The table seed is disjoint from the validation seed and from the
development seeds. Streams are `PCG64([seed, mix])` with

`mix = uint32(sum(digest_bytes * 1..len(digest)))`

of the UTF-8 string `"{seed}:{label}"`, the same mixer as the D7
dependence review. Every validation label starts with `dts-v1:`.
No validation stream uses a development seed or a development label.

This unit does not draw the geometries. The seed is frozen before any
validation draw.

## J. Validation sample design

Type I:

- 7 families × 8 geometries = 56 configurations;
- 10000 simulations per configuration;
- 560000 type-I evaluations;
- one configuration is one geometry and one DGP draw, then 10000
  outcome paths;
- Wilson 95% interval on each configuration's rejection count, using
  `WILSON_Z_95 = 1.959963984540054` and the usual Wilson score formula.

At `n = 10000` and a true 5% rejection rate, the Wilson upper bound
first exceeds 0.06 at 554 rejections. The normal approximation to that
binomial tail is about 0.007 per configuration, so an every-cell rule
would fail a correctly calibrated profile on 56 cells roughly one time
in three. The gate in section K is the response to that fact. It is not
a loosening chosen after a failed cell.

Profile power, only after the type-I artifact is sealed as a pass:
8 new geometries, 1000 simulations each, base and stress as in section L.
Those streams are distinct from the type-I streams.

No second wave of simulations is added to cells that fail.

## K. Type-I gate

`alpha = 0.05`. `TYPE_I_CEILING = 0.06` exactly, not a floating
`(1 + 0.2) * 0.05`.

`PROFILE_TYPE_I_PASS` if and only if all of the following hold:

1. all 56 configurations are present, each with at least 10000
   simulations, and none is `DESIGN_DRAW_FAILED`;
2. the linear 0.90 quantile of the 56 Wilson 95% upper bounds is
   `<= 0.06`;
3. every configuration's Wilson 95% lower bound is `<= 0.06`;
4. every configuration's Wilson 95% upper bound is `<= 0.075`.

On 56 ordered upper bounds the linear 0.90 quantile interpolates
positions 49 and 50 in the zero-based sorted array
(`numpy` linear index `(56 - 1) * 0.90 = 49.5`).

Rule 2 is the domain requirement: a hot region, not one unlucky cell,
fails the profile. Rule 3 fails a cell whose rate is confidently above
the ceiling. Rule 4 is the single-cell catastrophe cap at 0.075. The
cap does not replace 0.06 and is not available as a typical-cell
ceiling.

Failure yields `PROFILE_VALIDATION_FAILED`. It does not yield a search
over bandwidths, kernels, or the other candidates.

## L. Power contract

`TYPE_I_VALIDATION_FIRST`. Power is undefined for the pass decision
until type I has passed and that artifact is sealed. A power run
started earlier is void and cannot be reused.

### Profile power

Eight fresh geometries, slots as in section H, 1000 simulations each.
The recorded power is the statistical rejection rate only.

- Base: family 2, one `phi` draw per geometry. Binary population
  `delta = 0.05`. Continuous population `delta = 0.25` in innovation
  standard-deviation units.
- Stress: family 3 conditional on duration at least 720, same targets.
- Base passes if at least 6 of 8 geometries have power `>= 0.80`.
- Stress passes if at least 6 of 8 have power `>= 0.50`.

The mean shift is pool-preserving inside each stratum. A common gap `d`
is scaled by the weight scheme's contrast scale so the population value
of `sum w_t Y_t` equals the target. Binary probabilities are clipped to
`[0.01, 0.99]`. If clipping binds on more than 5% of rows, that
geometry is `POWER_DESIGN_INFEASIBLE` and counts as not meeting the
power floor. It is not redrawn until it looks powerful.

`PROFILE_VALIDATED = true` only when type I and both power bars pass.
Power failure does not authorize a different statistic.

### D7 power admission

Runs only after `PROFILE_VALIDATED = true` and the geometry admission
in section M passes. Uses the real D7 weights, strata, gaps, and
`H = 721`. Uses synthetic `Y` only.

- Base: one family-2 draw. Stress: one family-3 draw with duration at
  least 720.
- Gate: population `delta = 0.05`, 2000 simulations.
- Pass: base power `>= 0.80` and stress power `>= 0.50`.
- Descriptive only, same DGPs, 2000 simulations: `delta = 0.075` and
  the discovery magnitude `0.09087324532453248`. They are not the gate.
- MDE: smallest value on `{0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10}`
  whose base-DGP rejection rate at 1000 simulations is at least 0.80.
  The admission gate still uses the 2000-simulation result at 0.05,
  not the MDE grid.

D7's temporal gate and practical gate are confirmation rules. They are
not folded into this power count.

## M. D7 admission check

`D7_PROFILE_ADMISSION = PASS` only when every blind check below passes.
The check reads the pinned predictor design. It does not read the
BitMEX target.

- selector digest
  `88b6e9571e26c0037ee14522249f21ec7f0d46261982dcb5e5bb0964cd396cc6`;
- `T_index` equals the ordered target-structurally-eligible row count
  and lies in `[8000, 80000]`;
- `K` is the candidate count on that index, `K >= 200`, prevalence
  `K/T_index` in `[0.03, 0.25]`;
- stratum count of nonempty year × RV cells lies in `[4, 32]`;
- structural gap count lies in `[0, 3]`;
- `H = 721` and `b = 721/T_index` lies in `(0.005, 0.10]`;
- `T_index / H >= 20`;
- weight scheme is `WITHIN_STRATUM_RATE_MATCHED`;
- weights sum to 0 within each stratum within tolerance `1e-9`;
- direction is `ONE_SIDED_UPPER`;
- practical threshold is 0.05;
- the outcome accessor has not been called.

Pinned reference counts, for identity rather than as a substitute for
the measurement: constructed hours 31835, selector candidates 3438,
target-structurally-eligible rows 30354. Admission measures the design
it is given and fails closed on a digest mismatch.

`PROFILE_VALIDATED = true` and `D7_PROFILE_ADMISSION = PASS` are both
required before D7 may use the profile. The same two-layer rule applies
to any later hypothesis.

## N. Fallback

`V2_AUTOMATIC_METHOD_SWITCHING = false`

If V1 fails validation, the status is `PROFILE_VALIDATION_FAILED`.
The implementation must not switch to the bootstrap, to subsampling,
to another bandwidth, or to another block rule. A later profile, if
one is designed, is a new id such as
`DEPENDENT_TIME_SERIES_CONTRAST_V2`.

The normal-critical-value HAC at the same `H` may be reported as a
diagnostic. Disagreement sets `INFERENCE_SENSITIVE` and does not flip
the primary decision.

## O. Feasibility compiler integration

This contract does not edit `gv0r02_feasibility_compiler.py`.

The profile's admission and power objects expose at least:

| Profile field | Compiler field |
| --- | --- |
| candidate `K` | `PRIMARY_SUPPORT_SIZE` |
| `MIN_ATTAINABLE_P = 0.001` | `MIN_ATTAINABLE_P` |
| nominal alpha attainable inside the domain | `ALPHA_ATTAINABLE` |
| MDE on the base DGP | `MDE_BASE` |
| MDE on the stress DGP | `MDE_STRESS` |
| power at the hypothesis threshold, base and stress | `POWER_AT_MIN_MEANINGFUL_EFFECT_BASE` and `_STRESS` |

Also exposed, for the screen rather than as a silent rename:

- `nominal_T` = `T_index`;
- `candidate_N` = `K`;
- `N_EFF_CONSERVATIVE_PRE_OUTCOME = T_index / (1 + 2H)`, informational
  only, not a substitute for the power-admission gate;
- `horizon_count = T_index / H`;
- dependence class and profile id;
- p-value resolution `CONTINUOUS_QUANTILE_GRID_0.001`;
- profile compatibility `APPLICABLE` or `INAPPLICABLE:<code>`;
- admission result;
- feasibility status `FEASIBLE_FOR_PREREGISTRATION` only when the
  profile is validated, admission passed, and the power/MDE gate
  passed. Otherwise a precise failure such as `PROFILE_NOT_VALIDATED`,
  `ADMISSION_FAIL`, `POWER_ADMISSION_FAIL`, or
  `INFERENCE_SUPPORT_INSUFFICIENT`.

Until validation has run, the status is `PROFILE_NOT_VALIDATED`.

## P. Target-opening gate

`TARGET_OPENING_ALLOWED` only when every generic condition holds:

- this contract is frozen and unchanged;
- the implementation matches the contract, including the statistic,
  the table seed, and the validation seed;
- `PROFILE_VALIDATED = true`;
- hypothesis admission is `PASS`;
- hypothesis power/MDE gate is `PASS`;
- unit tests and provenance checks passed;
- the protected outcome is still unopened at decision time;
- an independent review has approved the opening.

Otherwise `TARGET_OPENING_FORBIDDEN`.

D7 adds three conditions:

- `D7_V2_ESTIMAND_CHANGED = false`;
- the temporal gate remains the frozen 2-of-3 rule on
  `{2017, 2018, 2019}`, with 2016 diagnostic only, and that rule stays
  outside the profile;
- `D7_BITMEX_PRIMARY_TARGET_OPENED = false` until the generic gate and
  these three conditions are met in a later, separately authorized unit.

This document does not meet the implementation, validation, power, or
review conditions. Opening is forbidden now.

The temporal rule is a D7 confirmation gate. A future hypothesis may
declare a different temporal gate or none. The engine must not apply
2-of-3 on 2017–2019 to that hypothesis.

## Q. Reuse contract

`PROFILE_REUSABLE_IF`:

- the estimand is a supported weighted linear contrast;
- the dependence assumption is inside the class in section G;
- `T`, `K`, `q`, prevalence, gaps, and `b` lie inside the validated
  bounds;
- support and effective-sample screens pass;
- hypothesis admission passes;
- the hypothesis supplies its own `H` and does not reuse 721 unless
  its own construction argument says 721.

`NEW_INFERENCE_DESIGN_REQUIRED_IF`:

- exact or randomization inference is naturally available;
- the event count is below the support bounds;
- clustered group structure dominates time dependence;
- the estimand is nonlinear or otherwise outside the profile;
- the dependence geometry lies outside the validated domain;
- a discrete reference distribution cannot attain alpha;
- another declared assumption of section G fails.

Reuse does not skip admission or the hypothesis-level power gate.

## R. Anti-overfitting contract

After the first `dts-v1:` validation draw, the following are forbidden
on this profile id:

- method-family changes;
- bandwidth or `H` rule changes;
- block-rule changes;
- critical-value, kernel, or quantile-grid changes;
- alpha, ceiling, Wilson `z`, quantile level, or catastrophe-cap
  changes;
- deleting or replacing a difficult validation case;
- changing geometry or DGP ranges;
- adding simulations only to failing configurations;
- changing either seed;
- switching to the bootstrap or to subsampling;
- adding a D7-specific exception, weight path, or critical value.

A failure is sealed as `PROFILE_VALIDATION_FAILED` on V1. A redesigned
procedure is a new profile id. V1 is not edited until it passes.

## S. Implementation plan

Not created in this unit. Later code, if a review authorizes it, should
split as follows.

Generic, profile-owned:

- `scripts/research/inference/problem.py` — `InferenceProblem` schema
  and outcome-free weight checks;
- `scripts/research/inference/profile.py` — profile protocol;
- `scripts/research/inference/registry.py` — id to implementation,
  unknown id returns `UNSUPPORTED`;
- `scripts/research/inference/profiles/dependent_time_series_contrast_v1.py`
  — contrast, gap-aware Bartlett LRV, fixed-b decision;
- `scripts/research/inference/critical_values.py` — Brownian table from
  the table seed only;
- `scripts/research/inference/calibration.py` — scenarios, streams, and
  the type-I gate;
- `scripts/research/inference/power.py` — profile power after type I;
- `scripts/research/inference/admission.py` — geometry admission;
- `scripts/research/inference/target_gate.py` — opening decision.

D7 adapter only:

- `scripts/research/d7_bitmex/inference_problem_v1.py` — fills the
  problem from the pinned design, sets `H = 721`, attaches the temporal
  gate as data the profile does not read, and refuses to load the
  target.

Tests, when implementation exists:

- contract lock (this unit already locks the JSON);
- stratum weights sum to 0 and a constant outcome gives delta 0;
- a one-row gap removes the cross product the unsplit series would have
  included;
- the registry has no D7-named statistic;
- admission does not call the outcome accessor;
- no function switches method after a failed configuration;
- table digest is reproducible from the table seed.

Artifacts, when a run is separately authorized:

- Brownian table manifest and digest;
- profile validation result, one row per configuration, with seeds and
  rejection counts;
- D7 admission result, including the blind geometry measurements;
- target-opening decision, defaulting to forbidden.

Provenance on every result: profile id, contract digest, table digest,
validation or table seed, label, geometry digest, and a boolean that
the outcome file was not read.

The compiler stays a consumer of the fields in section O. It is not
modified by the future profile implementation unless a separate unit
says so.

## T. Final decision

`REUSABLE_V2_CONTRACT_READY_FOR_INDEPENDENT_REVIEW`

The contract is ready for review because the profile, the statistic,
the horizon rule, the validation distribution, the seed, the type-I
gate, the power bars, the admission split, and the failure rule are
fixed before any V2 draw.

It is not a validation pass, not an implementation permit, and not a
target-opening permit. `PROFILE_VALIDATED` remains false.
`TARGET_OPENING` remains `FORBIDDEN`.
The D7 hypothesis has not failed, and the BitMEX primary target remains
unopened.
