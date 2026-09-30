# Frozen profile contract: SELF_REFERENTIAL_TIME_SERIES_CONTRAST_V1

**Profile id:** `SELF_REFERENTIAL_TIME_SERIES_CONTRAST_V1`

**Contract status:** `PROFILE_CONTRACT_READY_TO_FREEZE`

This document is the canonical profile contract. It incorporates `INFERENCE_PROFILE_SELF_REFERENTIAL_TIME_SERIES_CONTRAST_V1_ERRATUM`. Where an earlier review states `L_T = o(T^{1/3})`, identifies cumulant summability with the mixing assumption, or treats `H_mechanical(T) / T → 0` as a sufficient bandwidth condition, this contract replaces that sentence. Equations and rules not replaced here remain those of the predecessor reviews named below.

No implementation, no simulation of the inference procedure, no RNG stream, and no BitMEX lag-1 inspection is authorized by this freeze. Method selection is not reopened.

`PRIMARY_METHOD = STUDENTIZED_FULL_IF_DWB`

`PRIMARY_METHOD_CHANGED = false`

`NO_AUTOMATIC_METHOD_SWITCHING = true`

`NUMERIC_G_REQUIRED = ONLY_FOR_FINITE_UNIFORM_CLAIM`

`G_MAX_REMOVED = true`

`GENERIC_TYPE_I_SIM_N = 9559`

`D7_ADMISSION_TYPE_I_SIM_N = 9559`

`D7_HYPOTHESIS_FAILED = false`

`D7_BITMEX_PRIMARY_TARGET_OPENED = false`

`D7_PRIMARY_EFFECT_COMPUTED = false`

`PROFILE_VALIDATED = false`

`TARGET_OPENING = FORBIDDEN`

## 1. Estimand and null

`θ = g(m) = (sum_s D_s) / M`, with `D_s = m_s^{(XY)} - m_s^{(X)} m_s^{(Y)} / m_s^{(0)}` and `M = sum_s m_s^{(X)}`, as in the smooth-functional review.

`D7_NULL = GLOBAL_WEIGHTED`: the composite null is `θ ≤ 0`, and the boundary used for the null distribution is `θ = 0`. Cellwise `Δ_s = 0` is a subclass. Cancelling cells with nonzero `Δ_s` and `θ = 0` remain inside the null. The null is not narrowed.

## 2. Procedure

The primary procedure is the studentized full-influence dependent wild bootstrap fixed in the primary-method review, the contract-readiness review, and the freeze amendment.

Normative pieces, unchanged by this contract:

- one deterministic block centering of the full influence, used in the variance and in the bootstrap numerator, and not in `sqrt(T) θ̂`;
- Gaussian multipliers with Bartlett covariance inside each gap-free segment and independence across structural gaps;
- `L_T = B_T`;
- no second centering inside a bootstrap draw;
- the studentizer recomputed on each draw from `η^{(r)} ∘ c`;
- the Bartlett quadratic form positive semidefinite, and equal to zero if and only if its argument is constant on the eligible index;
- observed nonpositive variance, within the scale-aware tolerance, is `VARIANCE_DEGENERATE` and is not a pass or a fail;
- a bootstrap draw with nonpositive variance fails the confirmatory run closed. The draw is not mapped to `+∞`, not dropped, and not replaced;
- `R = 9999`, fixed before the run;
- the confirmatory seed is the HMAC-SHA256 / HMAC_DRBG derivation in the freeze amendment, from the freeze-tree digest, the adapter digest, and the first NIST Beacon 2.0 pulse at or after that commit. One beacon value, one stream, no rerun.

`B_T = L_T = max(H_mechanical, ceil(T^{1/3}))`.

## 3. Maintained assumptions

`THEORETICAL_APPLICABILITY_CLASS` is maintained. It is not checked on a sealed series.

- `g` is continuously differentiable where every declared cell mass and the total candidate mass are bounded away from zero.
- The long-run variance of the block-centered influence in the direction `∇g` is finite and positive.
- Shao Assumption 3.1-style mixing and moments: strong mixing, or near-epoch dependence on a strong-mixing sequence, with some `δ > 2` such that `sum_j α(j)^{δ/(2+δ)} < ∞` and `E|Z_t|^{2+δ} < ∞`.
- Shao Assumption 3.2-style fourth-order joint cumulant summability, as a separate requirement.

Bounded primitive coordinates make `E|Z_t|^{2+δ} < ∞` automatic for every `δ > 2`. They do not make the mixing sum automatic, and they do not make Assumption 3.2 automatic. A stronger mixing condition may be added as a sufficient condition for the cumulant sum. That stronger condition is then part of what is maintained. It is not identified with Assumption 3.1.

`sum_{h≥1} h |γ(h)| < ∞` may be maintained as a qualitative dependence condition. It is not a measured admission input, and no numeric `G_MAX` is part of this contract.

Structural gaps and deterministic block centering remain an extension beyond the single-segment stationary theorem. This contract states that extension as maintained scope. It does not supply the extension proof.

## 4. Bandwidth and mechanical horizon

For the `δ > 2` in Assumption 3.1, the maintained bandwidth condition is

`L_T^{-1} + L_T / T^{δ/(2+2δ)} → 0`.

Under that same `δ`, `L_T = O(T^{1/3})` is permitted, because `δ/(2+2δ) > 1/3` and therefore `T^{1/3} = o(T^{δ/(2+2δ)})`.

`H_mechanical(T) / T → 0` is necessary and not sufficient. The theoretical-domain requirement is

`H_mechanical(T) = o(T^{δ/(2+2δ)})`.

`H_mechanical(T) = O(T^{1/3})` is a sufficient condition for that requirement. An adapter may establish the sufficient condition.

A fixed positive integer horizon satisfies the sufficient condition. D7's `H_mechanical = 721` is in the theoretical domain. At the D7 sample the executed bandwidth is `max(721, ceil(30354^{1/3})) = 721`.

## 5. Validation, stress, and admission

Three objects stay distinct, as in the freeze amendment.

`PROFILE_VALIDATION_DESIGN` is the finite anchor list. It is not a filled rectangle.

`PROFILE_VALIDATED_DOMAIN` is the subset of those anchors that pass after the runs exist. No hypothesis is admitted by interpolation between anchors.

`HYPOTHESIS_GEOMETRY_ADMISSION` is an outcome-blind type-I check on that hypothesis's own geometry. A generic pass does not substitute for it.

`PROFILE_VALIDATED = true` is necessary for a later target opening and is not sufficient. Opening also needs hypothesis-geometry admission and a power gate. The power gate is not defined here and is not run. Current `PROFILE_VALIDATED` remains false.

The finite stress battery is the explicit parameter list in the envelope resolution: `IID_BERNOULLI`, `INTERLACED_LAG2`, `MA_EVEN`, `CANCELLING_CELLS`, `VARIANCE_REGIMES`, and `LABEL_MARKOV`, on the geometries named there. Every gating law has `g(m) = 0` by construction. `FINITE_SAMPLE_STRESS_MAX` names interlaced `ρ = 0.90` and label stay `0.95`. It is not a boundary of the mixing class. The non-gating sensitivity draws do not enter pass/fail and do not widen the class.

`GENERIC_TYPE_I_SIM_N = 9559` and `D7_ADMISSION_TYPE_I_SIM_N = 9559`. The gate is the Wilson 95% upper bound of the one-sided rejection count at most `0.06`, with normal quantile `z = 1.959963984540054`. At `N = 9559` the largest passing count is `528`. These counts replace every earlier count of `1825`. Neither count is taken from a profile result or from a D7 rejection frequency.

D7 exact-geometry admission, after a generic stress pass, uses `T = 30354`, the one published gap inside 2016, year masses 4079, 8757, 8759, and 8759, the 16 published cell margins, candidate total `K = 3438`, and `B_T = L_T = 721`. Synthetic labels replace the generic probabilities by the published ratios `pi_s = candidate_n / eligible_n`. The real state path, lag-1 pairs, transitions, and time-ordered RV trajectory are not inputs. A D7 admission failure sets `D7_PROFILE_ADMISSION = FAIL`, keeps `TARGET_OPENING = FORBIDDEN`, and does not revoke a generic stress pass.

## 6. Status words

These are not synonyms.

`THEORETICALLY_APPLICABLE_UNDER_MAINTAINED_ASSUMPTIONS`: the law is in the class of sections 3 and 4. This is not a data check.

`FINITE_SAMPLE_STRESS_VALIDATED`: the battery in section 5 passed the Wilson gate at `N = 9559`.

`HYPOTHESIS_GEOMETRY_ADMISSION_PASS`: the same families, at that hypothesis's outcome-blind geometry, passed the same gate.

`CONFIRMED_UNDER_MAINTAINED_ASSUMPTIONS`: a later target result under this procedure, with the mixing and cumulant conditions still maintained rather than verified on the sealed series.

A future pass remains `CONFIRMED_UNDER_MAINTAINED_ASSUMPTIONS`. Stress validation does not verify BitMEX mixing.

## 7. What this freeze does not start

This contract freezes the profile text. It does not implement the statistic, generate a confirmatory stream, run the stress battery, run D7 admission, or open the BitMEX target.

`D7_HYPOTHESIS_FAILED = false`

`D7_BITMEX_PRIMARY_TARGET_OPENED = false`

`D7_PRIMARY_EFFECT_COMPUTED = false`

`PROFILE_VALIDATED = false`

`TARGET_OPENING = FORBIDDEN`
