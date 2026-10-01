# Contract-readiness review of the studentized full-influence DWB

**Reviewed selection:** `INFERENCE_PROFILE_SELF_REFERENTIAL_PRIMARY_METHOD_V1`

**Review status:** `PROFILE_CONTRACT_READY_TO_FREEZE`

This unit does not reopen method selection. No simulation, no implementation, no RNG, and no BitMEX lag-1 reconstruction. The scientific null stays `H0: theta <= 0`.

`PRIMARY_METHOD = STUDENTIZED_FULL_IF_DWB`

`NO_AUTOMATIC_METHOD_SWITCHING = true`

`D7_HYPOTHESIS_FAILED = false`

`D7_BITMEX_PRIMARY_TARGET_OPENED = false`

`D7_PRIMARY_EFFECT_COMPUTED = false`

`PROFILE_VALIDATED = false`

`TARGET_OPENING = FORBIDDEN`

Readiness means every numeric and algebraic choice below is fixed without target information. It does not mean the extension in L has been proved. A future pass remains `CONFIRMED_UNDER_MAINTAINED_ASSUMPTIONS`.

## A. Observed statistic

The sample is the eligible index `t = 1, ..., T` in calendar order. `T` counts structurally target-eligible hours. Hours inside a structural gap are absent. Lag is in eligible-index steps inside a gap-free segment, the same unit as the adapter's mechanical overlap.

For each adapter-declared cell `s`,

`m_hat_s^{(0)} = T^{-1} sum_t 1{S_t = s}`

`m_hat_s^{(X)} = T^{-1} sum_t 1{S_t = s} X_t`

`m_hat_s^{(Y)} = T^{-1} sum_t 1{S_t = s} X_{t+1}`

`m_hat_s^{(XY)} = T^{-1} sum_t 1{S_t = s} X_t X_{t+1}`

`M_hat = sum_s m_hat_s^{(X)}`

`D_hat_s = m_hat_s^{(XY)} - m_hat_s^{(X)} m_hat_s^{(Y)} / m_hat_s^{(0)}`

`theta_hat = g(m_hat) = (sum_s D_hat_s) / M_hat`

If any declared cell has `m_hat_s^{(0)} = 0`, or `M_hat = 0`, the estimand is undefined. The run does not reject, records `ESTIMAND_UNDEFINED`, and does not switch method. Empty declared cells are not dropped.

At a point where `g` is defined, the partial derivatives are

`∂g/∂m_s^{(XY)} = 1 / M`

`∂g/∂m_s^{(Y)} = -(m_s^{(X)} / m_s^{(0)}) / M`

`∂g/∂m_s^{(X)} = -(m_s^{(Y)} / m_s^{(0)}) / M - theta / M`

`∂g/∂m_s^{(0)} = (m_s^{(X)} m_s^{(Y)} / (m_s^{(0)})^2) / M`

Let `Z_t` stack `1{S_t=s}`, `1{S_t=s} X_t`, `1{S_t=s} X_{t+1}`, `1{S_t=s} X_t X_{t+1}` over `s`. The raw influence is

`φ_t = ∇g(m_hat)' (Z_t - m_hat)`

With `pi_hat_s = m_hat_s^{(X)} / m_hat_s^{(0)}`, `mu_hat_s = m_hat_s^{(Y)} / m_hat_s^{(0)}`, and

`u_t = (X_t - pi_hat_{S_t}) (X_{t+1} - mu_hat_{S_t}) / M_hat`,

the same series is the identity

`φ_t = u_t - theta_hat * X_t / M_hat`.

The sample mean of `u_t` equals `theta_hat`. The sample mean of `φ_t` equals 0. On the population boundary `theta = 0` the second term drops and `φ_t` reduces to the product score. The contract uses the gradient series, not the product with that term removed by hand.

Deterministic blocks `j = b(t)` are the adapter's calendar blocks. They are not year × RV cells.

`μ̂_j = T_j^{-1} sum_{t: b(t)=j} φ_t`

`c_t = φ_t - μ̂_{b(t)}`

`T_j` counts eligible hours in the block. A gap inside a block does not split the block mean. The sum of `c_t` is 0. That sum is not the numerator.

HAC, for a series `a_t` and bandwidth `B_T`, uses the Bartlett weights

`w(h) = 1 - h / B_T` for `0 ≤ h < B_T`, and `w(h) = 0` for `h ≥ B_T`.

`ā = T^{-1} sum_t a_t`

`Γ(0) = T^{-1} sum_t (a_t - ā)^2`

For `h ≥ 1`, `S_h` is the set of `t` such that `t` and `t+h` lie in the same structural segment,

`Γ(h) = T^{-1} sum_{t in S_h} (a_t - ā)(a_{t+h} - ā)`

`V(a; B_T) = Γ(0) + 2 sum_{h=1}^{B_T-1} w(h) Γ(h)`

The divisor is `T`, including at lags where `S_h` is a strict subset. Year boundaries are not segment breaks. Structural gaps are.

`V_obs = V(c; B_T)`

`T_obs = sqrt(T) * theta_hat / sqrt(V_obs)` when `V_obs > 0`.

Block centering enters only through `c` inside `V_obs`. It does not redefine `theta_hat`.

## B. Block centering

`BLOCK_CENTERING_VALID = CONDITIONAL`

Let `J` be fixed, `T_j / T → λ_j ≥ λ_min > 0`, and `sum_j λ_j mu_j = 0`, where `mu_j` is the deterministic block mean of the population influence. Write `δ_j = μ̂_j - mu_j = O_p(T^{-1/2})`. The difference of the lag-`h` sample autocovariances of `c_t` and of the population-centered influence is `O_p(T^{-1})` under the bounded-moment envelope, uniformly in `h`. The Bartlett sum of fewer than `B_T` such terms is `O_p(B_T / T)`. That difference tends to 0 when `B_T / T → 0`.

The conditions are a finite block count, block fractions bounded away from 0, `B_T → ∞`, `B_T / T → 0`, and the mixing envelope that makes each block mean `sqrt(T_j)`-consistent. Under those conditions the centering error in the long-run variance is asymptotically negligible.

`theta_hat = g(m_hat)` is computed before centering. Heterogeneous cell contributions remain inside `D_hat_s` and inside `theta_hat`. RV labels are not a centering key, so their variation remains in `c_t`. No equation sets `D_s = 0`.

## C. Bootstrap numerator

Draw `r` uses multipliers `η_t^{(r)}` from H. The bootstrap series and numerator are

`c_t^{(r)} = η_t^{(r)} c_t`

`N_r* = T^{-1/2} sum_t c_t^{(r)}`

No pseudo-outcome and no synthetic target are formed. The gradient stays at `m_hat`. Because each block of `c_t` sums to 0,

`sum_{t: b(t)=j} η_t^{(r)} c_t = sum_{t: b(t)=j} (η_t^{(r)} - η̄_j^{(r)}) c_t`,

so `N_r*` is within-block comovement of the multiplier with `c`, not a redraw of `X_{t+1}`.

## D. Bootstrap block centering

Freeze A: the bootstrap HAC is applied to `η_t^{(r)} c_t`.

Do not subtract `block_mean(η c)` before that HAC.

`c_t` is already the observed influence after its one deterministic-block centering. Multiplication does not put a calendar level back. A block mean of `η c` is a mean-zero draw artifact. At a bandwidth ratio `b = B_T / T` that does not vanish in the finite sample, removing it changes the quadratic form by a term of order `b`, which is the distortion the recomputed studentizer is there to track. The numerator is the sum of `η c`. The matching denominator is the HAC of that same series.

The observed pipeline removes deterministic means once, then forms `V(c)`. The bootstrap pipeline multiplies that centered series and forms `V(η c)`. A second block centering would be a different statistic.

## E. Bandwidths

`B_T` is `HAC_STUDENTIZER_BANDWIDTH`, the truncation in `V(·; B_T)`, in the original and in every draw.

`L_T` is `MULTIPLIER_DEPENDENCE_BANDWIDTH`, the scale of `Cov(η_t, η_s)`.

HAC consistency for a Bartlett estimator of the block-centered influence needs `B_T → ∞` and `B_T / T → 0`.

Dependent-multiplier consistency for a smooth function of means needs `L_T → ∞` and `L_T / T → 0`.

The mechanical floor is a lower bound on both, because construction overlap is dependence the HAC window and the multiplier covariance both have to cover. It is not an estimated memory.

## F. Bandwidth relation

`L_T_EQUALS_B_T_THEORETICALLY_JUSTIFIED`

The observed studentized statistic is one functional of one partial-sum process, with one Bartlett scale `B_T / T`. The multiplier covariance is a Bartlett operator at scale `L_T`. The recomputed HAC is a Bartlett operator at scale `B_T` applied to `η c`. Those are the same operator, and the bootstrap ratio stays in that one-parameter family, only when `L_T = B_T` and the kernels coincide. Any other ratio is a second researcher degree of freedom and a different limit functional. Equality does not relax `→ ∞` or `/T → 0`. No further relative-rate restriction is added: the ratio is fixed at 1, not estimated.

## G. Admission rule

`REPLACE_WITH_VALIDATION_DOMAIN_ADMISSION`

The cap `b_eff ≤ 1/2` is removed. It is not a condition in the small-bandwidth multiplier theorem, and a half-sample counting line is not a reason to keep it.

The profile requirement along an asymptotic sequence is `B_T / T → 0` and `L_T / T → 0`.

A finite hypothesis is admitted only when its outcome-blind geometry lies in the validated domain of M. Otherwise the result is `PROFILE_ADMISSION_OUT_OF_DOMAIN`. No hypothesis is admitted by this review. Validation has not been run.

## H. Bandwidth rule and multiplier law

`B_T = L_T = max(H_mechanical, ceil(T^{1/3}))`

`c = 1` and the exponent `1/3` are profile constants. They are not fit to an adapter length.

The exponent is the Bartlett mean-squared-error rate under the extra bandwidth-design assumption

`sum_{h≥1} h |γ(h)| ≤ G < ∞`

for the autocovariance of the block-centered influence, uniformly on the profile class. Bounded variables and `sum_h h α(h) < ∞` imply it. Absolute summability of `γ` alone does not pick the exponent `1/3`. The assumption is maintained, not estimated from the confirmation score. The leading constant is 1 because the spectral curvature that would replace it is unidentified under that assumption. `H_mechanical` is the adapter floor.

Multiplier law, for the eligible index and `L_T` as above. Let

`k(h) = 1 - h / L_T` for `0 ≤ h < L_T`, and `k(h) = 0` for `h ≥ L_T`.

`k(0) = 1`, so each margin has variance 1. No second normalization.

If `t` and `s` lie in the same structural segment, `Cov(η_t, η_s) = k(|t-s|)`. Otherwise the covariance is 0. Segments separated by a structural gap are independent, not merely uncorrelated: the vector is multivariate normal with mean 0 and this block-diagonal covariance. Each diagonal block is a principal section of a Bartlett Toeplitz matrix, which is positive semidefinite for every segment length, including segments shorter than `L_T`. A year boundary without a structural gap is inside the segment and keeps the kernel covariance.

No state is carried into a segment edge. No circular wrap and no circulant embedding. The law is the exact Gaussian with that covariance.

The same `k` is the HAC weight, because `L_T = B_T`. This is not the convention `1 - h / (B_T + 1)`.

## I. Bootstrap studentizer

`V_r* = V(c^{(r)}; B_T)`

with `c_t^{(r)} = η_t^{(r)} c_t`, the global demean inside `V`, gap-restricted pair sets `S_h`, and no second block centering.

`T_r* = N_r* / sqrt(V_r*)` when `V_r* > 0`.

The gradient is fixed at `∇g(m_hat)`. Draws do not recompute `m` or `g`. This is the linearization of `sqrt(T)(g(m_hat) - g(m))`. A draw that rebuilt `g(m*)` from a new moment vector would be a different statistic.

## J. Nonpositive variance

The gap-restricted divisor-`T` Bartlett sum is not algebraically the full Toeplitz quadratic form, so `V ≤ 0` is a specified edge, not only a rounding event. The zero series is included.

If `V_obs ≤ 0`, `T_obs` is undefined. The primary does not reject and records `VARIANCE_NONPOSITIVE`. That is not a confirmation pass and not a method switch.

If `V_r* ≤ 0`, set `T_r* = +∞`. The draw counts in the upper tail of K. This matches "counts as extreme" on the p-value and keeps `R` fixed. It moves `p` up, so the one-sided rejection region gets smaller. Validation must include draws from near-zero and gap-split series and must apply this assignment. It must not replace it with a new cutoff after seeing those draws.

Invalidating the whole run on one nonpositive `V_r*` would make the decision depend on an extra random count and would leave the finite-`R` lattice. That alternative is not used.

## K. Finite-R rule

`R = 9999`

`p = (1 + #{r : T_r* ≥ T_obs}) / (R + 1)`

Ties use `≥`. Attainable values are `(1 + k) / 10000` for `k = 0, ..., 9999`.

Reject `H0: theta ≤ 0` only when `V_obs > 0` and `p ≤ 0.05`. That is `k ≤ 499`, since `500 / 10000 = 0.05` and `501 / 10000 = 0.0501`. `(R + 1) * 0.05 = 500`.

If `T_obs ≤ 0` and `V_obs > 0`, the same formula is used. The upper-tail count is then large and the test does not reject. The bootstrap is still run. There is no sign short-circuit.

At a conditional tail probability 0.05, the Monte Carlo standard error is `sqrt(0.05 * 0.95 / 9999) ≈ 0.002180`. `R` is a profile constant.

The multiplier stream remains the HMAC-SHA256 / HMAC_DRBG derivation in the primary-method record. No seed is drawn here.

## L. Theorem status

`THEOREM_WITH_EXPLICIT_EXTENSION`

Shao's dependent wild bootstrap for smooth functions of means gives consistency of the linearized multiplier sum `T^{-1/2} sum η_t φ_t` for `sqrt(T)(g(m_hat) - g(m))` when the moment vector is mixing, `L_T → ∞`, and `L_T / T → 0`, with the gradient held at `m_hat`. The lead pair sits in `Z_t`, so the self-referential product is inside that smooth-function model once the mixing assumption is granted for `Z_t`.

Gonçalves and Vogelsang show that recomputing a HAC studentizer inside a block bootstrap tracks the fixed-bandwidth law of the original HAC statistic. That is a block-bootstrap theorem. It is the reason the contract recomputes `V_r*` rather than reusing `V_obs`. It is not a proof for Gaussian multipliers.

The frozen procedure adds these extensions, which validation must guard as type-I behavior of the whole rule, not as tuning inputs:

- one deterministic-block centering of `φ`, with numerator `theta_hat`;
- bootstrap numerator `sum η_t c_t`, and HAC on `η c` without a second block centering;
- `L_T = B_T` with the shared Bartlett kernel, including at a binding mechanical floor;
- gap-independent segment Gaussians and gap-restricted `Γ(h)`;
- heteroskedastic and randomly labeled cells inside `g`;
- the nonpositive-variance assignment in J;
- the finite-`R` tail in K.

A validation failure seals this profile version.

## M. Validation domain

Validation has not been run. The domain it must cover, stated before any draw and not centered on an adapter length, is the box:

- `T` at the dyadic points `2^11, 2^12, ..., 2^16`, and admission later uses the closed interval from `2^11` to `2^16`;
- cell count in `{1, 2, 4, 8, 16}`;
- candidate prevalence in `{0.05, 0.10, 0.25, 0.50}`, admission later the interval `[0.05, 0.50]`;
- equal cell shares, and the imbalance in which one cell holds half of candidate mass;
- global-null laws, including cellwise zero and cancelling nonzero cell effects;
- deterministic block counts in `{1, 2, 4, 8}`, with equal lengths and with one block at half the equal-block length and the others rebalanced;
- random predictable cell labels that are functions of lagged covariates, not of the lead;
- no gap, one interior gap of length `0.02 T`, and a gap that falls inside a deterministic block;
- `H_mechanical / T` in `{0, 0.01, 0.02, 0.05, 0.10}`, which stops at ten non-overlapping mechanical windows;
- dependence at a short memory and at a mixing sequence with `sum h α(h)` near the maintained bound;
- variance shifts across deterministic blocks.

Every gating law has `g(m) = 0` by construction. Envelope-violation series stay labeled `ENVELOPE_VIOLATION_SENSITIVITY` and stay outside pass/fail.

After that validation exists, a hypothesis is admitted only if each of its outcome-blind coordinates lies in this domain. Otherwise `PROFILE_ADMISSION_OUT_OF_DOMAIN`.

## N. D7 geometry

Published outcome-blind eligible length and the frozen mechanical floor:

`T = 30354`

`H_mechanical = 721`

`H_mechanical / T = 721 / 30354 = 0.0237530473743164`

This is an admission descriptor for a later comparison with M. It is not evidence that the procedure is valid, and no transition count was used.

## O. Final decision

`PROFILE_CONTRACT_READY_TO_FREEZE`

The observed map, the single block centering, the bootstrap numerator, the refusal to re-center `η c`, the equality `L_T = B_T`, the bandwidth assumption, the validation-domain admission rule, the Gaussian segment law, the recomputed studentizer, the nonpositive-variance assignment, and the finite-`R` rule are fixed. None of them uses a BitMEX transition.

## P. Scientific status

`D7_HYPOTHESIS_FAILED = false`

`D7_BITMEX_PRIMARY_TARGET_OPENED = false`

`D7_PRIMARY_EFFECT_COMPUTED = false`

`PROFILE_VALIDATED = false`

`TARGET_OPENING = FORBIDDEN`

`BLOCK_CENTERING_VALID = CONDITIONAL`

`L_T_EQUALS_B_T_THEORETICALLY_JUSTIFIED`

`REPLACE_WITH_VALIDATION_DOMAIN_ADMISSION`

`THEOREM_WITH_EXPLICIT_EXTENSION`

`PROFILE_CONTRACT_READY_TO_FREEZE`
