# Primary-method selection for the self-referential contrast

**Reviewed record:** `INFERENCE_PROFILE_SELF_REFERENTIAL_SMOOTH_FUNCTIONAL_REVIEW_V1`

**Review status:** `FREEZE_SELF_REFERENTIAL_PROFILE_CONTRACT`

Theory and design only. No implementation, no simulation, no validation draws, and no BitMEX lag-1 reconstruction. The scientific null stays `H0: theta <= 0`. It is not narrowed to cellwise zero.

`D7_NULL = GLOBAL_WEIGHTED`

`FINITE_DIMENSIONAL_SMOOTH_FUNCTIONAL = true`

`PRIMARY_METHOD = STUDENTIZED_FULL_IF_DWB`

`STUDENTIZER_RECOMPUTED_EACH_DRAW = true`

`DETERMINISTIC_BLOCK_CENTERING_REQUIRED = true`

`NO_AUTOMATIC_METHOD_SWITCHING = true`

`D7_HYPOTHESIS_FAILED = false`

`D7_BITMEX_PRIMARY_TARGET_OPENED = false`

`D7_PRIMARY_EFFECT_COMPUTED = false`

`PROFILE_VALIDATED = false`

`TARGET_OPENING = FORBIDDEN`

Selection order used here: validity on the declared class, then finite-sample approximation at the bandwidth ratio the generic rule actually produces, then heterogeneous variance, then reproducibility. Reproducibility is not the selector.

## A. Boundary influence and NW721

On `theta = 0`, `sum_s D_s = theta * M = 0`. The full influence therefore drops the constant `N/M`:

`IF_t = (X_t - pi_{S_t}) (X_{t+1} - mu_{S_t}) / M`

with `pi_s = m_s^{(X)} / m_s^{(0)}` and `mu_s = m_s^{(Y)} / m_s^{(0)}`. The earlier display that subtracted `D_s` inside the cell sum is the same series on this boundary, because those constants add to `N = 0`.

`BOUNDARY_IF_EQUALS_OLD_PRODUCT_SCORE = true`

The historical score is `w_t (Y_t - mu_s)` with `w_t = (X_t - pi_s) / K` inside year × RV cells. On the sample, `M_hat = K / T`, so the plug-in boundary influence is `T` times that score. The factor `T` cancels in a studentized statistic: `delta / sqrt(Var(sum score))` and `sqrt(T) theta_hat / sqrt(LRV(IF))` are the same number. Cell-specific `pi_s` and `mu_s` match the historical weights. Random RV labels change the sampling interpretation of `Z_t`. They do not change the plugged-in boundary series.

What separates a normal-critical Bartlett test at this bandwidth from historical NW721 is then only the surrounding contract, not a new first-order null statistic:

- The influence derivation gives this product on the boundary and a different gradient off the boundary. The null reference uses the boundary product.
- Random predictable cells are inside `m`. The computed product still uses the realized labels.
- Deterministic year-block centering, derived in B, is required and was not part of NW721. NW721 subtracted the year × RV pool mean of `Y` inside the product. That is the definition of `mu_s`. It leaves a nonzero year-level mean of the product when year effects cancel.
- The generic bandwidth rule below binds at the mechanical floor for the published D7 length, so the lag count is 721 valid hours, the historical lag.
- Cross-gap products are omitted. The historical FFT autocovariance on the valid-hour vector does not reset at the December 2016 hole.

`FULL_IF_HAC` with a Bartlett kernel, bandwidth 721, and an `N(0,1)` critical value is that same boundary instrument plus year-block centering and a gap reset. Year-block centering changes a different error (inflation under cancelling year means) from the one that showed up in development (normal critical values with a long stochastic dependence). It does not make the normal-critical test a new method.

## B. Deterministic block centering

`DETERMINISTIC_BLOCK_CENTERING_REQUIRED = true`

Calendar years are deterministic blocks. The global boundary allows `E[IF_t] = mu_j` inside year `j` with `sum_j (T_j / T) mu_j = 0` and some `mu_j ≠ 0`.

Write `v_t = mu_{j(t)} + u_t` with `E[u_t] = 0`. Under that cancellation, `sum_t mu_{j(t)} = 0`, so

`sum_t v_t = sum_t u_t`.

The deterministic levels contribute nothing to the sum. They contribute to a Bartlett quadratic form. For each fixed lag inside a year,

`γ(h) → γ_u(h) + sum_j λ_j mu_j^2`,

`λ_j = T_j / T`. The Bartlett sum at truncation `B_T` multiplies the flat mean term by

`sum_{|h| < B_T} (1 - |h| / B_T) = B_T`.

The added term is exactly `B_T * sum_j λ_j mu_j^2`, the order `B_T * average(mu_j^2)`. If any year mean is nonzero and `B_T → ∞`, a globally demeaned or uncentered HAC estimator diverges while `Var(T^{-1/2} sum u_t)` stays finite. The estimator is inconsistent and asymptotically inflated.

Centering that preserves the estimand:

- The adapter names the deterministic blocks. For this class they are calendar blocks, not year × RV cells.
- `μ̂_j` is the sample mean of the plug-in influence inside block `j`.
- `c_t = IF_t - μ̂_{j(t)}` is the series that enters every long-run variance, Bartlett form, cosine form, and multiplier path.
- The numerator stays `T^{-1/2} sum_t IF_t = sqrt(T) theta_hat`. The sum of `c_t` is identically zero and is not the numerator.
- RV labels are not a centering key. Share and RV fluctuations remain in `c_t`.
- No cell is forced to `Delta_s = 0`. A year × RV mean of the product can be nonzero. Only the deterministic block mean is removed from the quadratic form.
- Stochastic autocovariances of `u_t` remain. Lags may cross a year boundary. They reset at a structural gap.
- The same centered series is the input to every candidate, including every DWB draw. Draws multiply `c_t`. They do not estimate a second deterministic mean from `η_t c_t`. That sample block mean is multiplier noise, not a fixed calendar level.

With a fixed number of blocks, replacing `mu_j` by `μ̂_j` changes the long-run variance by `O(J / T)` and does not change the HAC limit.

## C. Candidate A

`T_A = sqrt(T) theta_hat / σ̂_HAC(c)`

- Influence: plug-in `∇g(m̂)' (Z_t - m̂)`, reduced on the boundary to the product in A.
- Series inside the HAC: deterministic-block centered `c_t`.
- Kernel: Bartlett, positive semidefinite, weights `1 - |h| / B_T` for `|h| < B_T`.
- Bandwidth: the generic rule in H. No data-dependent lag picker.
- Gaps: products that cross a structural gap are omitted. Year boundaries are not gaps.
- Normalization: `σ̂²` is the Bartlett long-run variance of `c_t` on the `T` scale, divisor `T`.
- If `σ̂² <= 0`, the studentized statistic is undefined and the test does not reject.

Critical value: the one-sided standard normal quantile at level 0.05 only.

Theoretical status. Under the mixing envelope, the `δ`-domain, block centering, and `B_T → ∞`, `B_T / T → 0`, `T_A` is asymptotically standard normal on `theta = 0`, including cancelling cells. Heteroskedasticity is allowed in that first-order HAC theorem. There is no refinement theorem that replaces the normal quantile by a bandwidth-dependent law. At a binding mechanical floor the finite-sample reference is the normal law on the historical product score. Development calibration of that normal-critical instrument is relevant evidence about the approximation. It is not an acceptance test, and it is not a reason by itself to declare the first-order theorem false. It is a reason to refuse to treat Candidate A as a new primary method.

## D. Candidate B1

Same numerator, same block-centered Bartlett studentizer, same `B_T`, same gaps, same nonpositive-variance failure as A. The critical value is a fixed-`b` law evaluated at `b_eff = B_T / T`, not the normal quantile.

Pivotality of that law needs an FCLT of the centered influence to a single Brownian motion after one scale `σ`. That holds under the mixing envelope when the long-run variance is homogeneous along the sample. A time-varying variance profile leaves a Gaussian limit that is not standard Wiener, and a stationary Bartlett table does not match it. Random predictable RV labels are compatible with the FCLT when they are part of the mixing system and do not create a persistent variance shift. Deterministic year means have to be removed first, which B requires, or the partial-sum path has piecewise drift. A vanishing gap fraction can be skipped on the partial-sum clock. The global boundary is compatible with the limit once centering has removed year means: cellwise zero is not required.

B1 is conditionally pivotal on a stationary homogeneous-variance subclass. It is not pivotal on the declared heterogeneous class. Adopting it as primary would narrow the profile. This selection does not narrow the profile.

## E. Candidate B2

Equal-weighted cosine long-run variance, a different quadratic form from Bartlett. On the block-centered series, with the cosine basis

`φ_{j,t} = √2 cos(π j (t - 1/2) / T)`,

`λ_j = T^{-1/2} sum_t φ_{j,t} c_t`,

`σ̂²_EWC = ν^{-1} sum_{j=1}^{ν} λ_j^2`,

`T_EWC = sqrt(T) theta_hat / σ̂_EWC`.

The rule shape `ν = c_ν T^{2/3}` is the usual series rate. This review does not freeze `c_ν`. A published constant from stationary designs does not transfer. The reference is a `t` or `F` fixed-bandwidth law in the number of cosines, not a critical value for the Bartlett estimator.

Low-frequency cosines are sensitive to leftover block means, so centering is required. Gaps destroy orthogonality of the basis on the raw index. Heterogeneous variance and persistent RV regimes enter `λ_j`, so the equal-variance `t` reference needs a stationary homoskedastic segment. B2 is a narrower construction than B1, not a Bartlett correction. It is not valid on the declared class without narrowing the profile.

## F. Candidate C

Studentized dependent wild bootstrap of the block-centered full influence. The studentizer is recomputed inside every draw. A bootstrap numerator divided by the original-sample `σ̂` (call that C1) has the same first-order normal limit as Candidate A when `σ̂` is consistent. It does not reproduce the dependence between a bandwidth-`B_T` numerator and a bandwidth-`B_T` denominator. C2 is the construction that does.

Frozen construction:

- One observed influence from `∇g(m̂)' (Z_t - m̂)`. Primitive moments and `g` are not recomputed inside draws. The gradient stays at `m̂`.
- Deterministic-block centering once, giving `c_t`.
- External multipliers, mean zero, variance one, jointly Gaussian, covariance `k((t-s) / B_T)` with the Bartlett kernel, and covariance zero when `t` and `s` are separated by a structural gap. Year boundaries are not resets.
- Bandwidth: the same generic `B_T` as the HAC kernel. One rule.
- Draw `r` forms `c*_{r,t} = η_{r,t} c_t`.
- Numerator `N*_r = T^{-1/2} sum_t c*_{r,t}`.
- Denominator `σ̂*_r` is the Bartlett HAC of `c*_{r,·}` at the same `B_T`, with the same gap omissions.
- `T*_r = N*_r / σ̂*_r` when `σ̂*_r > 0`.
- If `σ̂*_r <= 0`, the draw counts as extreme. That choice moves the p-value up.
- If the original `σ̂(c) <= 0`, the test does not reject and records `VARIANCE_NONPOSITIVE`.
- Observed statistic `T_obs = sqrt(T) theta_hat / σ̂(c)`.
- Replication count `R = 9999`.
- `p = (1 + #{r : T*_r >= T_obs}) / (R + 1)`.
- Reject `H0: theta <= 0` at level 0.05 only when `σ̂(c) > 0` and `p <= 0.05`.

`R + 1 = 10000`, and `10000 * 0.05 = 500`, so the level sits on the finite-`R` lattice. Conditional on an exact continuous bootstrap null, the Monte Carlo standard error of a tail probability `0.05` is `sqrt(0.05 * 0.95 / 9999) ≈ 0.00218`. `R` is a profile constant. It is not chosen from D7.

The numeric multiplier seed is not chosen in this unit. After the implementation tree is frozen, the seed stream is `HMAC-SHA256` with key the profile id `SELF_REFERENTIAL_TIME_SERIES_CONTRAST_V1` and message the concatenation of the frozen git tree hash, the pinned external beacon identifier, the first beacon value at or after that freeze, and the purpose label `DWB_MULTIPLIERS`. The RNG consumes the full digest through `HMAC_DRBG`. No byte-sum mixer. No seed is drawn here.

## G. Literature transfer

| Result | Class | Transfer |
| --- | --- | --- |
| Jansson higher-order fixed-`b` expansion in Gaussian location models | `ANALOGY_ONLY` | Location, Gaussian, no `g(m)`, no heterogeneous variance, no calendar blocks |
| Sun–Phillips–Jin HAR bandwidth and fixed-`b` critical values | `APPLICABLE_WITH_EXTENSION` | The coverage argument extends to an influence that satisfies an FCLT. The optimal constants were not derived for this variance profile |
| Kiefer–Vogelsang fixed-`b` Bartlett limit | `APPLICABLE_WITH_EXTENSION` | The Wiener limit extends to a centered influence with homogeneous long-run scale. It does not supply a pivotal table under the declared heterogeneous profile |
| Lazarus–Lewis–Stock–Watson HAR and EWC recommendations | `ANALOGY_ONLY` | Qualitative warning against normal critical values at moderate `b`. Their numeric rules were calibrated on other designs and are not adopted |
| Gonçalves–Vogelsang studentized block-bootstrap HAC | `APPLICABLE_WITH_EXTENSION` | Recomputing the HAC studentizer is the mechanism that tracks the fixed-bandwidth law. The proof is for the block bootstrap, not for multipliers |
| Shao dependent wild bootstrap for smooth functions of means | `APPLICABLE_WITH_EXTENSION` | `theta = g(m)` is the smooth-function model, and the lead pair sits in `Z_t`. Extensions required: deterministic-block centering, structural gaps, heterogeneous variance, and internal studentization |

No location-model or block-bootstrap theorem is treated as a proof of multiplier validity on this profile.

## H. Bandwidth rule

`c = 1`, `rho = 1/3`, frozen as profile constants before any adapter length is used as a target.

`B_T = max(H_mechanical, ceil(T^{1/3}))`

`rho = 1/3` is the classical Bartlett exponent when `sum_h |h| |γ(h)|` is finite. That weighted summability is a bandwidth-design assumption. It is stronger than, and separate from, the mixing envelope. The leading constant is `1` because the spectral curvature that would replace it is not identified by the envelope and must not be estimated from the confirmation score. No Andrews plug-in. No published numeric recommendation is imported.

`H_mechanical` is an adapter input, a construction floor, not an estimated memory.

## I. D7 bandwidth ratio

Published outcome-blind length: `TARGET_STRUCTURALLY_ELIGIBLE_ROWS = 30354`. Mechanical floor: 721 valid hours. No target statistic is computed.

`ceil(30354^{1/3}) = 32`

`B_T = max(721, 32) = 721`

`b_eff = 721 / 30354 = 0.0237530473743164`

`MECHANICAL_FLOOR_BINDS = true`

## J. Admission cap

`B_EFF_MAX = 1/2`

A Bartlett window longer than half the eligible index leaves fewer than two non-overlapping stretches, and this profile does not claim a multiplier or HAC limit there. The cap is that half-sample line. It is not a small-`b` comfort region and it is not set to bracket D7. D7 has `b_eff ≈ 0.02375 <= 1/2`, so the cap admits the adapter. Admission does not restore a normal critical value. The binding floor is why the primary reference recomputes the studentizer.

An adapter with `b_eff > 1/2` is outside the profile.

## K. Heterogeneity

The declared class allows a heterogeneous variance profile inside the mixing envelope.

- A is first-order valid after HAC studentization. The `N(0,1)` quantile does not track finite-sample dependence on that profile.
- B1 is pivotal only when the centered partial sums converge to a single Wiener process. Heterogeneous long-run scale enters the limit and the stationary table misses it.
- B2 needs approximately equivariant cosine projections. Heterogeneous scale and gaps enter `λ_j`. The `t`/`F` reference is for a narrower stationary class.
- C2 applies multipliers to the observed centered path, so the variance profile is inside the bootstrap measure, and recomputing the studentizer compares the observation with draws that carry the same profile.

C2 stays on the declared class. B1 and B2 would require an explicit narrowing. The profile is not narrowed.

## L. Finite-sample theory

No simulation is used.

- A has a first-order HAC theorem under an extension to `g(m)`, and no bandwidth-refinement theorem. Development calibration of the normal-critical product score is finite-sample evidence about this reference at a binding floor.
- B1 has a fixed-`b` limit theorem under an FCLT extension, and a higher-order Gaussian-location result that is only an analogy. Pivotality stops at heterogeneous scale.
- B2 has a series-estimator limit under a stationary extension. The `t` reference is an analogy once projections are dependent or heteroskedastic.
- C1 matches A's normal limit and has no extra refinement.
- C2 has Shao's smooth-function multiplier theorem as an extension, plus the Gonçalves–Vogelsang mechanism, as a further extension, for why the studentizer has to be recomputed at this `b_eff`. That is the strongest finite-sample account that does not narrow the class.

## M. Primary method

`PRIMARY_METHOD = STUDENTIZED_FULL_IF_DWB`

C2 is valid on the declared global null without narrowing, it is the candidate whose studentizer matches the fixed-bandwidth mechanism, and it keeps heterogeneous scale in the reference. Candidate A is the historical normal-critical product score at the binding floor. B1 and B2 are pivotal only on a narrower class.

## N. Non-primary role

| Candidate | Role |
| --- | --- |
| A, same centered influence, same Bartlett `σ̂`, normal quantile | `SENSITIVITY_ONLY` |
| B1 | `NOT_INCLUDED` |
| B2 | `NOT_INCLUDED` |
| C1, original `σ̂` fixed across draws | `NOT_INCLUDED` |

If A and the primary disagree, `INFERENCE_SENSITIVE = true`. The primary pass/fail is unchanged. There is no AND/OR gate.

## O. Validation role

After this contract is frozen, generic synthetic validation may measure type I error, fail the profile, and measure power only after type I passes. It may describe finite-sample behavior of the frozen instrument.

It must not choose among A, B1, B2, and C, and it must not change `c`, `rho`, block centering, the Bartlett kernel, the reference, the Gaussian multiplier family, `R`, the p-value formula, or the null family.

Every gating law satisfies `g(m) = 0`, including cancelling nonzero cell effects, nonzero deterministic block means that cancel, random shares, random predictable labels, heteroskedasticity, gaps, lag-2 dependence, and dependence near the envelope, at the bandwidth ratio the rule produces.

`ENVELOPE_VIOLATION_SENSITIVITY` laws sit outside the mixing envelope. They do not enter pass/fail, do not change the method or the bandwidth, and do not widen the declared class. They show degradation when a maintained assumption fails.

A validation failure seals this profile version.

## P. Failure contract

`NO_AUTOMATIC_METHOD_SWITCHING = true`

If validation fails, nothing promotes another candidate, changes `B_T`, changes the kernel, changes the reference, changes `R`, draws a second validation seed, or deletes a null family. A redesign is a new profile id and version.

## Q. Reusability

The generic profile owns the moment map, the gradient, deterministic-block centering, the Bartlett studentizer, the multiplier covariance, the rule `B_T = max(H_mechanical, ceil(T^{1/3}))`, the half-sample cap, and the maintained-assumption schema.

The adapter supplies the state, the lead, eligibility, cell labels, which labels are deterministic blocks, the practical threshold, `H_mechanical`, and the assumption manifest. D7 is that adapter. The constant 721 is an adapter floor, not a constant in the generic inference code.

## R. Evidence class

A future pass is `CONFIRMED_UNDER_MAINTAINED_ASSUMPTIONS`.

`INFERENCE_SENSITIVE` is reported beside it when the normal-critical sensitivity disagrees. It does not change the pass.

## S. Next unit

`FREEZE_SELF_REFERENTIAL_PROFILE_CONTRACT`

The primary, the centering, the bandwidth rule, the cap, and the failure contract are decided. The next unit writes that contract in the form an implementation would have to follow. It does not open a target.

## T. Scientific status

`D7_HYPOTHESIS_FAILED = false`

`D7_BITMEX_PRIMARY_TARGET_OPENED = false`

`D7_PRIMARY_EFFECT_COMPUTED = false`

`PROFILE_VALIDATED = false`

`TARGET_OPENING = FORBIDDEN`

`BOUNDARY_IF_EQUALS_OLD_PRODUCT_SCORE = true`

`DETERMINISTIC_BLOCK_CENTERING_REQUIRED = true`

`PRIMARY_METHOD = STUDENTIZED_FULL_IF_DWB`

`NO_AUTOMATIC_METHOD_SWITCHING = true`
