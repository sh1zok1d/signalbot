# Smooth-functional review of the self-referential contrast

**Reviewed amendment:** `INFERENCE_PROFILE_SELF_REFERENTIAL_NULL_AMENDMENT_V1`

**Review status:** `SELECT_PRIMARY_METHOD_THEORETICALLY`

Theory only. No implementation, no simulation, no RNG, and no BitMEX lag-1 reconstruction. The scientific null stays global. It is not narrowed to cellwise zero.

`D7_NULL = GLOBAL_WEIGHTED`

`D7_HYPOTHESIS_FAILED = false`

`D7_BITMEX_PRIMARY_TARGET_OPENED = false`

`D7_PRIMARY_EFFECT_COMPUTED = false`

`PROFILE_VALIDATED = false`

`TARGET_OPENING = FORBIDDEN`

## A. Primitive moments

Let `S` be a finite cell list supplied by the hypothesis. On the eligible index where the lead exists, define the Cesàro limits

`m_s^{(0)} = lim T^{-1} sum_t 1{S_t = s}`

`m_s^{(X)} = lim T^{-1} sum_t 1{S_t = s} X_t`

`m_s^{(Y)} = lim T^{-1} sum_t 1{S_t = s} X_{t+1}`

`m_s^{(XY)} = lim T^{-1} sum_t 1{S_t = s} X_t X_{t+1}`

and stack them as `m`. Eligibility and gaps enter only by restricting that index, when the mask is a function of the clock and of data presence, not of the value of `X_{t+1}`. Candidate shares are not conditioned away: `m_s^{(X)}` remains a coordinate.

Write `M = sum_s m_s^{(X)}` and

`D_s = m_s^{(XY)} - m_s^{(X)} m_s^{(Y)} / m_s^{(0)}`.

When `m_s^{(X)} > 0` and `m_s^{(0)} > 0`,

`Delta_s = m_s^{(XY)} / m_s^{(X)} - m_s^{(Y)} / m_s^{(0)} = D_s / m_s^{(X)}`

`a_s = m_s^{(X)} / M`

`Delta = sum_s a_s Delta_s = sum_s D_s / M`.

`D_s` is the pooled covariance of `(X_t, X_{t+1})` inside the cell, up to the cell-mass factor `m_s^{(0)}`. Random `K_s/K` is `a_s`. A cell with `m_s^{(X)} = 0` contributes `D_s = 0` for a binary state and drops out of the sum without a separate division.

## B. Functional

`theta = g(m) = (sum_s D_s) / M`

`FINITE_DIMENSIONAL_SMOOTH_FUNCTIONAL = true`

`g` is a ratio of polynomials in the coordinates of `m`. It is `C^∞` on the open set where every declared cell has `m_s^{(0)} ≥ δ > 0` and `M ≥ δ > 0`. Those bounds keep the two denominators off zero. Separate cell candidate masses need not be bounded away from zero for `g` itself; a vanishing `m_s^{(X)}` removes that cell continuously for a binary `X`. Estimating `Delta_s` as its own ratio still needs `m_s^{(X)} > 0`. The global parameter does not.

## C. Gradient

With `N = sum_s D_s` and `theta = N/M`,

`∂g/∂m_s^{(XY)} = 1/M`

`∂g/∂m_s^{(Y)} = - (m_s^{(X)} / m_s^{(0)}) / M`

`∂g/∂m_s^{(X)} = - (m_s^{(Y)} / m_s^{(0)}) / M - theta / M`

`∂g/∂m_s^{(0)} = (m_s^{(X)} m_s^{(Y)} / (m_s^{(0)})^2) / M`

All other cross-cell derivatives of these coordinates are zero. Heterogeneous `Delta_s` sit inside `m` through `D_s` and through `m_s^{(Y)}/m_s^{(0)}`. They are not set to zero before differentiation. On `theta = 0` the term `-theta/M` drops, and the remaining gradient still depends on the cell margins.

## D. Influence function

Let `Z_t` be the stacked vector of `1{S_t=s}`, `1{S_t=s} X_t`, `1{S_t=s} X_{t+1}`, and `1{S_t=s} X_t X_{t+1}` over `s`, and let `ψ_t = Z_t - m`. Then

`IF_t = ∇g(m)' ψ_t`.

This is the first-order influence of `theta_hat = g(m_hat)` for the sample-mean estimator `m_hat`. It keeps random cell indicators, random candidate mass, and nonzero `Delta_s`. Deterministic year indicators have degenerate coordinates: their contribution to `ψ_t` is zero when the calendar fraction is nonrandom, and the gradient simply does not get noise from those coordinates.

On `theta = 0`, the stochastic part collapses to

`IF_t = M^{-1} sum_s [ 1{S_t=s} (X_t - pi_s)(X_{t+1} - mu_s) - D_s ]`

with `pi_s = m_s^{(X)} / m_s^{(0)}` and `mu_s = m_s^{(Y)} / m_s^{(0)}`, up to the mean-zero centering already in `ψ_t`. Because `D_s = m_s^{(0)} pi_s Delta_s`, a nonzero cell excess remains inside the product `(X_t - pi_s)(X_{t+1} - mu_s)` and inside `D_s`. Share reallocation is the derivative through `M` and through `m_s^{(X)}`, not an optional add-on.

## E. Previous phi

`PREVIOUS_PHI_INCOMPLETE`

The amendment's `phi_t` was a conditional-on-partition linearization. It treated cell membership as fixed and added a share term for `K_s` given that partition. Law C below redraws predictable RV labels with the state, so `m_s^{(0)}` is random and its gradient coordinate is part of `IF_t`. That coordinate is absent from `phi_t`. Conditional on a fixed partition the two formulae describe the same ratio, but that extra conditioning is not the confirmatory sampling law, and `phi_t` is not the canonical `∇g(m)' ψ_t` for the primitive vector in section A.

## F. Sampling law

`SAMPLING_LAW = MIXED_DETERMINISTIC_YEAR_RANDOM_PREDICTABLE_RV`

Repeated sampling redraws the market process.

- Calendar year is a deterministic function of the timestamp. Its membership is not a random draw.
- Structural gaps and target-eligibility, when they record missing clocks or constructibility rather than the value of `X_{t+1}`, are fixed masks.
- RV bucket labels are random and predetermined relative to `(X_t, X_{t+1})` when the bucket at `t` uses only earlier returns. The whole label field is still random and dependent with `X`, because later buckets use intermediate returns.
- `X_t` and `X_{t+1}` are the random lead pair.

Conditioning on the entire realized RV path conditions on labels that are functions of returns entangled with `X`. That is not an ancillary sigma-field of the frozen design. The frozen statistic uses the realized labels; the population parameter is the Cesàro `g(m)`, which already averages over the law of those labels. The natural law is mixed: deterministic years, fixed gaps, random predictable RV, random state.

The joint CLT is for `√T (m_hat - m)` under that law. Year coordinates may be singular. RV and state coordinates are not.

## G. Joint CLT

`JOINT_MOMENT_CLT_SUPPORTABLE = CONDITIONAL`

Binary `X` and finite cell indicators are bounded, so every fixed moment of `Z_t` exists. Dependence is the remaining condition. If an underlying process is alpha-mixing, or near-epoch dependent on an alpha-mixing process, with a summable envelope uniform on the profile class, then a fixed lead and a finite predictable partition preserve that structure: `Z_t` is a bounded measurable function of a finite window. A finite-dimensional CLT and a functional CLT for the partial sums of `Z_t` follow from that envelope. The long-run covariance `Ω` of `Z_t` exists. Singular calendar coordinates are allowed. The gradient quadratic form `∇g(m)' Ω ∇g(m)` is the asymptotic variance of `theta`.

The profile class is exactly those processes: finite predetermined cells, `m_s^{(0)}` and `M` inside the `δ`-domain, bounded primitive coordinates, and one uniform mixing or near-epoch envelope. No eighth-moment or sub-Gaussian assumption is required for binary `X`.

## H. Global boundary

`√T (theta_hat - theta) → N(0, ∇g(m)' Ω ∇g(m))`

whenever `m` is in the `δ`-domain and the envelope holds. Every `m` with `g(m) = 0` is included, whether or not each `Delta_s` is zero. Heterogeneous cancellation is a property of `m`. It changes `∇g(m)` and `Ω`. It does not require a separate recentering that sets cell excesses to zero, and it is not a reason to narrow `H0: theta <= 0`.

## I. HAC

`FULL_IF_HAC_THEORETICALLY_VIABLE = CONDITIONAL`

Apply a small-bandwidth HAC estimator to the plug-in influence `IF_hat_t = ∇g(m_hat)' (Z_t - m_hat)`, with a positive-semidefinite kernel. The bandwidth sequence satisfies `B_T → ∞` and `B_T / T → 0`. It is not the fixed-b sequence `B_T / T → b0 > 0`, and it is not the constant 721. A fixed mechanical-overlap floor is compatible with those two limits along `T → ∞`, because a fixed floor is eventually dominated by any `B_T → ∞` with `B_T = o(T)`. The floor is an admission constraint supplied by the adapter. It does not choose the sequence.

Under the envelope, `m_hat - m = O_p(T^{-1/2})` and the map `m ↦ IF(m)` is Lipschitz on the `δ`-domain because `Z_t` is bounded. Replacing `m` by `m_hat` inside the influence does not change the small-bandwidth long-run variance limit. Heteroskedasticity is carried by `Z_t`. Random predictable strata are coordinates of `Z_t`. Gaps of vanishing fraction are handled by omitting cross-gap products; they do not change the limit. This is conditional on the envelope, the `δ`-domain, and the small-bandwidth regime. It is an asymptotic statement, not a finite-sample level at any particular `T`. No numeric bandwidth is chosen here.

## J. DWB

`FULL_IF_DWB_THEORETICALLY_VIABLE = CONDITIONAL`

At an authorized opening the observed `IF_hat_t` is computed once from the joint path. External multipliers, mean zero and variance one, with `Cov(η_t, η_{t+h}) = k(h / l_T)`, multiply that sequence. The bootstrap statistic is the mean of the multiplied, sample-demeaned influence. It approximates the law of `√T (theta_hat - theta)` centered at zero. The gradient is fixed at `m_hat`. Draws do not recompute `g`. Recomputing `g` would be a different resampling scheme.

This is not a bootstrap that holds `X` fixed and draws an independent `Y`, and it does not drop the share term: that term is inside `∇g`. Multipliers are uncorrelated across gaps. The regime is `l_T → ∞` and `l_T / T → 0`, the same small-bandwidth regime as HAC, not fixed-b. A mechanical floor may lower-bound `l_T` without defining it. Validity is conditional on the same envelope and `δ`-domain. First-order, this bootstrap and the HAC normal limit estimate the same `N(0, ∇g' Ω ∇g)` law.

## K. Least-favorable boundary

`GLOBAL_BOUNDARY_LEAST_FAVORABLE = CONDITIONAL`

Studentize `√T theta_hat` by a consistent estimator of `σ(m) = sqrt(∇g(m)' Ω ∇g(m))`. On the `δ`-domain with `σ(m)` bounded away from zero, the limit at every `m` with `g(m) = 0` is standard normal. Cell heterogeneity changes `σ(m)` and is accounted for by using that `m`, not a cellwise-zero proxy. For `theta < 0` fixed, `√T theta_hat → -∞` and an upper-tail rejection probability tends to 0. Local alternatives `theta = h/√T` shift the normal mean by `h/σ(m)` and do not reorder the scalar test. The least-favorable slice of `H0: theta <= 0` is therefore `theta = 0`, uniformly over cell vectors on that slice, when studentization is consistent for the full influence. The earlier break in pivotality came from a critical value that ignored those cells. It does not reappear for this studentized functional.

## L. Maintained assumptions

Still required, and still not estimated from protected lag-1 correlation, run lengths, transition counts, or score memory:

- a uniform alpha-mixing or near-epoch envelope for the primitive vector `Z_t`;
- `σ(m)` bounded away from 0 and infinity on the profile's null set;
- the `δ`-domain for cell masses and total candidate mass;
- a small-bandwidth sequence obeying `B_T → ∞`, `B_T/T → 0`, and the adapter's mechanical floor.

If any of these fails, the normal or bootstrap limit is not the theorem above. A development panel can show that an envelope is not an empty gesture. It does not validate the confirmation venue. No portability assumption is granted. A PASS that uses this list remains

`CONFIRMED_UNDER_MAINTAINED_ASSUMPTIONS`

Post-opening diagnostics stay diagnostic. They do not change bandwidth, method, or the mechanical gate. The severe-warning display label from the amendment is unchanged.

## M. Validation class

Generic validation, when a later unit is authorized to draw it, uses joint laws of `(S_t, X_t)` with `Y_t = X_{t+1}` and `g(m) = 0` by construction. The class includes cancelling nonzero `Delta_s`, random candidate shares, deterministic year-like blocks and random predictable RV-like labels, unequal cell masses, lag-2 dependence with the lag-1 pooled moment constrained so `N = 0`, heteroskedastic Bernoulli variances from a lead-uncorrelated probability path, structural gaps, and dependence near the declared envelope. Cellwise-zero laws may appear as a subset. They are not the whole class. N4's slow within-cell path has `g(m) ≠ 0` and is not a null member. This review draws none of these laws.

## N. Reusability

`GENERIC_PROFILE_SUPPORTABLE = true`

`SELF_REFERENTIAL_TIME_SERIES_CONTRAST_V1` is `theta = g(m)` for a lead of one process, the influence `∇g' ψ`, and a small-bandwidth studentization of that influence. Generic code receives the state, the lead, the eligibility mask, the cell labels, and the realized bounded coordinates `Z_t`. It does not contain a mechanical horizon, a practical threshold, a venue, or a year × RV partition.

The adapter supplies the state definition, the lead, eligibility, the cells, the practical effect, the mechanical-overlap floor, and the maintained-assumption manifest. Another hypothesis changes those inputs without a profile edit.

## O. Method decision

`BOTH_FULL_IF_METHODS_VIABLE`

Full-influence HAC and full-influence dependent multipliers are both conditionally valid for `H0: theta <= 0` on the whole smooth hyperplane `g(m) = 0`, under one mixing envelope and one small-bandwidth regime. They are first-order equivalent. Neither is the old pivotal `c(b, q)` table, and neither is the rejected independent-`Y` bootstrap. No finite-sample dominance is claimed, and historical NULL_3 behavior is not a selector.

## P. Next unit

`SELECT_PRIMARY_METHOD_THEORETICALLY`

The functional and the global null are in place. Two first-order-equivalent variance estimators remain. A profile freeze needs one primary so the confirmatory gate cannot switch after the fact. That choice is the next theoretical unit. It does not narrow `H0`, does not restore removed null families, and does not open a target.

## Q. Scientific status

`D7_HYPOTHESIS_FAILED = false`

`D7_BITMEX_PRIMARY_TARGET_OPENED = false`

`D7_PRIMARY_EFFECT_COMPUTED = false`

`PROFILE_VALIDATED = false`

`TARGET_OPENING = FORBIDDEN`

`FINITE_DIMENSIONAL_SMOOTH_FUNCTIONAL = true`

`PREVIOUS_PHI_INCOMPLETE`

`JOINT_MOMENT_CLT_SUPPORTABLE = CONDITIONAL`

`FULL_IF_HAC_THEORETICALLY_VIABLE = CONDITIONAL`

`FULL_IF_DWB_THEORETICALLY_VIABLE = CONDITIONAL`

`GLOBAL_BOUNDARY_LEAST_FAVORABLE = CONDITIONAL`

`BOTH_FULL_IF_METHODS_VIABLE`
