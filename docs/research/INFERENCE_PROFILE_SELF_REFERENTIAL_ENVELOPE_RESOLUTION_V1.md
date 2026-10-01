# Envelope-cutoff resolution for the self-referential contrast

**Amends:** `INFERENCE_PROFILE_SELF_REFERENTIAL_FREEZE_AMENDMENT_V1`

**Review status:** `PROFILE_CONTRACT_READY_TO_FREEZE`

No implementation, no simulation of the inference procedure, no RNG stream, and no BitMEX lag-1 inspection. The primary method is not reconsidered.

`PRIMARY_METHOD = STUDENTIZED_FULL_IF_DWB`

`PRIMARY_METHOD_CHANGED = false`

`NUMERIC_G_REQUIRED = ONLY_FOR_FINITE_UNIFORM_CLAIM`

`G_MAX_REMOVED = true`

`D7_HYPOTHESIS_FAILED = false`

`D7_BITMEX_PRIMARY_TARGET_OPENED = false`

`D7_PRIMARY_EFFECT_COMPUTED = false`

`PROFILE_VALIDATED = false`

`TARGET_OPENING = FORBIDDEN`

## A. Role of a numeric envelope

`G_norm = sum_{h≥1} h |γ(h)| / γ(0)` was proposed as an executable cap. It is not.

- Asymptotic validity of the dependent wild bootstrap needs a qualitative mixing rate, not a published number `G_MAX`.
- Computing the statistic does not read `G_norm`.
- A finite stress battery is a list of explicit data-generating parameters. It does not need a cap that those parameters must sit under.
- Exact-geometry admission replays that same list at the hypothesis geometry. It does not ask the hypothesis to certify `G` before the target is opened.

A numeric cap would be required only for a claim that every process with `G_norm ≤ G_MAX` had been uniformly validated. This profile does not make that claim. `G_MAX`, edge-of-envelope gating, and any pre-target estimate of `G` are removed.

Weighted summability `sum_{h≥1} h |γ(h)| < ∞` stays inside `MAINTAINED_DEPENDENCE_ASSUMPTIONS` as a qualitative condition. It is not a measured admission input. A future pass remains `CONFIRMED_UNDER_MAINTAINED_ASSUMPTIONS`.

## B. Theoretical class

`THEORETICAL_APPLICABILITY_CLASS` is the set of laws for which the smooth-function multiplier theorem is being maintained. It is not checked on sealed BitMEX series.

Maintained conditions:

- `theta = g(m)` with `g` continuously differentiable on the domain where every declared cell mass and the total candidate mass are bounded away from zero.
- Primitive coordinates are bounded. Binary states and finite cell indicators have finite moments of every order, so the moment side of a condition `E|Z|^{2+δ} < ∞` holds for every `δ > 2` without a further restriction.
- The long-run variance of the block-centered influence in the direction `∇g` is finite and positive.
- `Z_t` is strong mixing, or near-epoch dependent on a strong-mixing sequence.
- There exists `δ > 2` such that `sum_j α(j)^{δ/(2+δ)} < ∞`.
- Joint cumulants of the primitive coordinates up to the order the smooth-function argument uses are absolutely summable. Boundedness does not by itself give that decay. The mixing rate above does, through the usual covariance inequality for bounded variables. No numeric covariance cap is added.
- `L_T → ∞`.

The classical upper rate that makes a Bartlett bias of order `1/L_T` negligible in the multiplier approximation is `L_T = o(T^{1/3})`, equivalently `L_T^3 / T → 0`. `L_T = O(T^{1/3})` with a constant that does not tend to zero does not imply that limit. The executed rule `max(H_mechanical, ceil(T^{1/3}))` is `Θ(T^{1/3})` when the floor does not bind, and it is larger still when a fixed floor exceeds `T^{1/3}`. That rule stays the executed bandwidth. It is not restated as a proof that the `o(T^{1/3})` condition holds at the sample being tested. D7's binding floor `721` is outside `o(T^{1/3})` at `T = 30354` because `721 > ceil(30354^{1/3})`.

## C. What finite validation supports

`FINITE_SAMPLE_VALIDATION_BATTERY` is the explicit list in D. A pass means `FINITE_SAMPLE_STRESS_VALIDATED` for those designs under the executed bandwidth, centering, kernel, and bootstrap rule.

It does not mean that every law in the theoretical class has been uniformly validated. Synthetic passes do not verify a sealed series' mixing rate.

## D. Finite stress battery

Every gating law has population `g(m) = 0` by the construction, not by a builder replay. Geometry factors, crossed with every family below, are `T ∈ {2048, 16384, 65536}`, deterministic block count `J ∈ {1, 4}` with equal block lengths, and either no gap or one gap of length `floor(0.02 T)` at index `floor(T/2)`. Cell schedules are functions of the index only.

`IID_BERNOULLI`. One cell, `X_t` iid Bernoulli(`0.25`).

`INTERLACED_LAG2`. Even and odd indices are independent chains. Marginal probability `0.30`. On each chain,

`P(X_t = 1 | X_{t-2}) = 0.30 + ρ (X_{t-2} - 0.30)`,

`ρ ∈ {0, 0.25, 0.50, 0.75, 0.90}`. Lag 1 has covariance 0, so the one-cell excess is 0. At `ρ = 0.90` the two conditional probabilities are `0.93` and `0.03`.

`MA_EVEN`. Same interlaced split and marginal `0.30`. Innovations `e_t` are iid Bernoulli(`0.5`). On each chain,

`P(X_t = 1 | e) = 0.30 + sum_{j=1}^{q} θ_j (e_{t-2j} - 0.5)`,

with `(q, θ)` equal to `(1, (0.40))`, `(2, (0.30, 0.20))`, and `(4, (0.20, 0.15, 0.10, 0.05))`. The largest absolute shift is `0.25`, so the conditional probability stays inside `[0.05, 0.55]`. Odd lags carry no coefficient, so the lag-1 excess is 0.

`CANCELLING_CELLS`. Two equal blocks, both with probability `0.30`. Inside a block,

`P(X_{t+1} = 1 | X_t) = 0.30 + c (X_t - 0.30)`,

with `c` and `-c` on the two blocks and `c ∈ {0.02/0.7, 0.05/0.7, 0.10/0.7}`. Equal lengths, equal probabilities, and opposite coefficients make the weighted sum of cell excesses 0. The boundary pair between blocks is drawn from the marginal. At `c = 0.10/0.7` the conditional probabilities are `0.40` and `0.25714`.

`VARIANCE_REGIMES`. Independent Bernoulli draws, so every cell excess is 0. On four equal blocks the probabilities alternate through `(0.10, 0.50)` or through `(0.05, 0.40)`.

`LABEL_MARKOV`. Two labels, stationary distribution `(1/2, 1/2)`, stay probability `s ∈ {0.50, 0.80, 0.95}`. Given the labels, `X_t` is independent Bernoulli with cell probabilities `(0.20, 0.40)`. Conditional independence given the labels makes every cell excess 0.

`FINITE_SAMPLE_STRESS_MAX` names the most persistent members of this list: interlaced `ρ = 0.90` and label stay `0.95`. It is not the boundary of the mixing class.

`OUT_OF_VALIDATION_STRESS_SENSITIVITY`, non-gating, is interlaced `ρ = 0.98` and label stay `0.99`. Those draws do not enter pass/fail, do not widen the theoretical class, and do not add a numeric envelope.

## E. D7 exact-geometry admission

`D7_EXACT_GEOMETRY_ADMISSION` remains a separate check after generic stress validation. It uses `T = 30354`, the one published gap inside 2016, year masses 4079, 8757, 8759, and 8759, the 16 published cell margins, and `B_T = L_T = 721`. Labels are synthetic. The real transition path is not used.

The families are the ones in D. Published `pi_s = candidate_n / eligible_n` replace the generic probabilities. A shift coefficient that would leave `[0, 1]` at a published `pi_s` is not applied in that cell; that cell uses an independent Bernoulli(`pi_s`) draw. The cancelling law is the already specified pair `2017:3` and `2019:3` with coefficient `-1/4` on `2019:3` and the compensating coefficient on `2017:3`. Every gating law still has `g(m) = 0`. A D7 failure does not revoke a generic stress pass.

## F. Operating characteristics of 1825 draws

The gate is unchanged: Wilson 95% upper bound of the rejection count at most `0.06`, with normal quantile `z = 1.959963984540054`.

At `N = 1825` the largest passing count is `89`. Then `89/1825 = 0.048767` and the Wilson upper bound is `0.059631`. The next count, `90`, has upper bound `0.060230`.

Probability of passing when the true rejection probability is:

- `0.050`: `0.4316`
- `0.055`: `0.1312`
- `0.060`: `0.0218`
- `0.065`: `0.0021`

A calibrated 5% procedure fails this gate more often than it passes. That is Monte Carlo noise from a threshold sitting below `0.05`, not a predeclared penalty for anti-conservatism. `1825` is not kept.

## G. Simulation counts

Targets fixed before the count:

- probability of passing at true type I `0.05` is at least `0.99`;
- probability of passing at true type I `0.065` is at most `0.05`.

The Wilson ceiling stays `0.06`. The smallest `N` that meets both targets is `9559`. At that size the largest passing count is `528` (`528/9559 = 0.055236`, Wilson upper bound `0.059997`). Pass probabilities:

- `0.050`: `0.9904`
- `0.055`: `0.5518`
- `0.060`: `0.0251`
- `0.065`: `0.0000406`

`GENERIC_TYPE_I_SIM_N = 9559`

`D7_ADMISSION_TYPE_I_SIM_N = 9559`

The two checks use the same gate and the same targets, so the counts are equal. Neither count is taken from a profile result.

## H. Status taxonomy

`THEORETICALLY_APPLICABLE_UNDER_MAINTAINED_ASSUMPTIONS`: the law is in the class of B. This is not a data check.

`FINITE_SAMPLE_STRESS_VALIDATED`: the battery in D passed the Wilson gate at `N = 9559`.

`HYPOTHESIS_GEOMETRY_ADMISSION_PASS`: the same families, at that hypothesis's outcome-blind geometry, passed the same gate.

`CONFIRMED_UNDER_MAINTAINED_ASSUMPTIONS`: a later target result under the frozen procedure, with the mixing conditions still maintained rather than verified.

These four are not synonyms. Stress validation does not verify BitMEX mixing.

## I. Primary method

`PRIMARY_METHOD_CHANGED = false`

Still in force: validation anchors are not an admission rectangle; `H_mechanical(T) / T → 0`; the Bartlett form is positive definite and `V_obs = 0` only when the centered influence is identically zero; nonpositive bootstrap variance fails the run closed; the confirmatory stream is the HMAC-SHA256 / HMAC_DRBG derivation from the freeze tree, the adapter digest, and the first NIST Beacon 2.0 pulse after that commit; `R = 9999`; no automatic method switching; the primary remains the studentized full-influence dependent wild bootstrap.

## J. Final decision

`PROFILE_CONTRACT_READY_TO_FREEZE`

No executable envelope cutoff remains. The dependence class is the maintained mixing condition. Finite severity is the parameter list in D.

## K. Scientific status

`D7_HYPOTHESIS_FAILED = false`

`D7_BITMEX_PRIMARY_TARGET_OPENED = false`

`D7_PRIMARY_EFFECT_COMPUTED = false`

`PROFILE_VALIDATED = false`

`TARGET_OPENING = FORBIDDEN`
