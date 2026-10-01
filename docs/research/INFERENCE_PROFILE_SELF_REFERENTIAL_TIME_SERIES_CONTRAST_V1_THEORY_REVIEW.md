# Theory review: self-referential time-series contrast

**Reviewed record:** `docs/research/INFERENCE_PROFILE_SELF_REFERENTIAL_TIME_SERIES_CONTRAST_V1.md`

**Review status:** `NARROW_NULL_CLASS_AND_REVIEW_AGAIN`

Theory only. No implementation, no simulation, no RNG stream, and no BitMEX lag-1 reconstruction. The design record is not edited. Its null families N3, N4, and N7 are not accepted as members of the frozen D7 null.

`D7_HYPOTHESIS_FAILED = false`

`D7_BITMEX_PRIMARY_TARGET_OPENED = false`

`D7_PRIMARY_EFFECT_COMPUTED = false`

`PROFILE_VALIDATED = false`

`TARGET_OPENING = FORBIDDEN`

`D7_ESTIMAND_PRESERVED = true`

Frozen strata remain year × RV of the predictor hour. Latent regime labels are not added to those strata.

## A. Null class

Let `T_s` be the target-eligible times with frozen stratum `s`, `n_s = |T_s|`, and `Y_t = X_{t+1}`. For a conditionally independent Bernoulli mechanism `X_t | p ~ Bernoulli(p_t)`, with `(p_t)` measurable with respect to information that does not include the Bernoulli innovations,

`P(X_{t+1}=1 | X_t=1, s) = (sum_{t in T_s} E[p_t p_{t+1}]) / (sum_{t in T_s} E[p_t])`

`P(X_{t+1}=1 | s) = (sum_{t in T_s} E[p_{t+1}]) / n_s`

when the denominator is positive. If `p` is nonrandom on `T_s`,

`excess_s = cov_{n_s}(p_t, p_{t+1}) / mean_{n_s}(p_t)`

where `cov_{n_s}` is the within-stratum average `n_s^{-1} sum_t p_t p_{t+1} - mean(p_t) mean(p_{t+1})`. The stratum excess is zero if and only if that lag-1 covariance of the probability path is zero. The frozen contrast is the `K_s/K` average of the stratum excesses, so the population estimand is zero when every stratum with positive mass has this covariance equal to zero.

Independence of the Bernoulli innovations supplies `E[X_t X_{t+1} | p] = p_t p_{t+1}`. It does not supply `cov(p_t, p_{t+1} | s) = 0`. Pooling over times inside a frozen stratum reweights candidate hours toward times with large `p_t`. If `p_{t+1}` moves with `p_t`, the candidate mean sits above the pool mean.

**Largest defensible null.** Laws of `(X_t)` on the frozen partition such that, in every year × RV cell,

`cov_{n_s}(p_t, p_{t+1}) = 0`

under conditional independence of the innovations given `p`, or, without a latent `p`, the same identity in `X`:

`(sum_{t in T_s} E[X_t X_{t+1}]) / (sum_{t in T_s} E[X_t]) = (sum_{t in T_s} E[X_{t+1}]) / n_s`.

Plus the regularity in section C that makes one critical value uniformly valid. The bare moment restriction `E[delta_hat] = 0` with no dependence restriction is not that class.

Inside this null, prevalence may differ across frozen strata. It may vary over time inside a stratum only when the time path is uncorrelated with its own lead. Dependence at lags 2 and higher may exist when it does not induce a nonzero lag-1 covariance of `X` inside the stratum. Structural gaps may exist when pairs that cross a gap are excluded and each segment obeys the covariance restriction.

Lag-1 predictability of `X_{t+1}` by `X_t` inside a frozen stratum is the estimand. A positive value is an alternative. It is not nuisance dependence.

## B. N3 / N4 audit

`N4_IS_NULL = false`

`N3_IS_NULL_UNDER_FROZEN_STRATA = false`

`N7_IS_NULL_UNDER_FROZEN_STRATA = false`

**N4, slow sinusoid.** The design sets `p(s,t) = clip(p_s + A sin(2π t/τ + φ))` and treats innovation independence as enough. For large `τ`, `p_{t+1} ≈ p_t` inside the year × RV cell, so `cov(p_t, p_{t+1} | s) ≈ Var(p | s) > 0` whenever `A ≠ 0`. The excess equals that covariance divided by the mean level. A slow sinusoidal base rate is an alternative under the frozen estimand. It is a null only under an extra orthogonality restriction this family does not impose: `cov(p_t, p_{t+1} | s) = 0` inside each frozen cell. A fast oscillation can meet that restriction. The slow process named in N4 does not.

The design's common guarantee shows `P(X_{t+1}=1 | Z_t, full threshold path) ` does not depend on `Z_t`. The estimand conditions on `S_t = s` only. Those are different sigma-fields. `X_t = 1` reweights time inside the cell. The step that drops the full path down to the frozen label is the step that fails.

**N3, persistent latent regime.** As written, N3 puts the latent regime into the contrast's strata and then declares the excess zero inside those enlarged strata. Under year × RV alone, a persistent regime that is not a function of year × RV produces a probability path with positive lag-1 covariance inside the frozen cell. That is an alternative. Promoting the latent label into `s` changes the hypothesis. It is not a repair of the null.

**What still matches the frozen null.** N1 and N5, constant prevalence inside each frozen stratum and independent innovations. N2, Gaussian MA(2) with a zero lag-1 coefficient and a threshold that is constant on each frozen stratum: joint normality plus zero lag-1 covariance gives lag-1 independence of the latent, and the threshold does not move inside the cell, so the covariance identity holds, while lag 2 can still be dependent. N6, a gap rule applied to one of those laws. N7 inherits N3's extra stratum and falls with N3.

## C. Required assumptions

The class of all laws with only `E[delta_hat] = 0` admits no nontrivial level-0.05 test that is uniform over the class. The contrast of a binary process is bounded. A mixture that puts probability `γ ≤ 1/2` on a path with contrast `+1` and probability `1-γ` on a path with contrast `-γ/(1-γ)` has mean zero and puts mass up to `1/2` on the perfect positive path. Any procedure with power against that path has uniform type I error at least `1/2` on this class. This is the Bahadur–Savage phenomenon on a bounded contrast. Weak dependence cannot be omitted.

Minimum additional regularity, imposed as a class restriction rather than as a favor to one statistic:

- innovations conditionally independent given the probability path, and that path's within-stratum lag-1 covariance equal to zero (the scientific null);
- a uniform weak-dependence restriction on the score strong enough for a functional CLT: alpha-mixing or near-epoch dependence with rates and constants fixed for the whole class, not estimated from the confirmation path;
- long-run variance of the score bounded above, and bounded away from zero on the subclass where a studentized test is required;
- finitely many frozen strata, with arm shares in a compact subset of `(0,1)`;
- structural gaps either absent or of vanishing time fraction, unless the limit process is rebuilt on the observed gap partition;
- Bernoulli outcomes, which already satisfy every fixed-moment bound.

A martingale-difference assumption given the entire past is sufficient for the scientific null when the conditional mean really is constant on the frozen stratum. It is stronger than the pooled covariance restriction and is not required for a CLT. Summable autocovariance of a mean-zero score is the right second-order condition; it does not replace the restriction that the lag-1 excess itself is zero. Local stationarity is a convenience for a single Brownian limit, not a scientific reading of D7.

## D. Random-weight theory

`delta_hat = sum_t w_t(X) X_{t+1}`

with rate-matched weights. Two different pieces of `w` need different measurability.

The treatment bit `X_t` is predictable: it is a function of information at `t`, and the outcome `X_{t+1}` is the next value. Under the null, `X_t` is a predetermined regressor orthogonal to the within-stratum innovation. A CLT for lagged-regressor scores applies under the mixing condition above. The asymptotic object is the delta-method image of the joint CLT for the within-stratum averages `E_n[X_t]`, `E_n[X_{t+1}]`, and `E_n[X_t X_{t+1}]`.

The shares `π_s = K_s/N_s` and `K_s/K` use the whole sample. They are not predictable. Under the null the stratum excess is itself `O_p(n^{-1/2})`, and `K_s/K - λ_s` is `O_p(n^{-1/2})`. Their product is `O_p(n^{-1})`. Estimation of `K_s/K` therefore does not change the first-order null limit. It does change finite-sample weights. The probability limits `λ_s` remain in the asymptotic variance. Treating the realized shares as fixed when forming the influence function is first-order valid for the null limit and is not a claim that the weights were assigned exogenously.

Deterministic exogenous weights are a different theorem and a different hypothesis. Complete-sample shares are estimated nuisance quantities whose contribution is second order on the null boundary. Predictable state weights are the leading random design and are already the self-referential part of the estimand.

## E. Fixed-b

`FIXED_B_THEORETICALLY_VIABLE = CONDITIONAL`

A fixed-b or self-normalized Bartlett statistic built from the influence score is viable when section C holds and the partial-sum process of that score satisfies a functional CLT to `σ W`. The long-run scale `σ` cancels. The limiting random variable is the Kiefer–Vogelsang functional of that Brownian motion for one linear contrast after the stratum means are removed, at the bandwidth ratio `b` and the Bartlett kernel. It is not the Gaussian-white-noise table `c(b, q)` from the exogenous-weight profile, and that table is not reinstated.

The limit does not depend on `σ`. It depends on the kernel, on `b`, and on the limiting projection onto the frozen stratum indicators. It depends on the realized weight path only through that projection and through `λ_s`. It depends on a nonstationary variance profile: piecewise or persistent heteroskedasticity replaces `W` by a Gaussian process with the corresponding variance measure, and the homoskedastic critical value ceases to be pivotal. A gap of vanishing fraction does not enter the limit; a gap partition with positive time shares does. D7's single short hole is in the vanishing-fraction case if the sample length grows, and the dependence sum still should not cross it in finite samples.

`H` stays the mechanical construction horizon supplied by the hypothesis. `b = H / T_index`. No lag is chosen from confirmation pairs.

## F. DWB

`DWB_THEORETICALLY_VIABLE = CONDITIONAL`

Two different uses:

Ex ante selection and validation do not read the BitMEX score. The multiplier kernel, the centering, the mechanical bandwidth, and the null class are frozen. Size is a theorem about synthetic laws in section A, later checked on those laws only. The sealed path is not an input to that check.

At a later authorized opening, one application to the observed score is a conditional multiplier approximation to the sampling distribution. It is valid, under section C, because the external multiplier rebuilds the dependence of a mean-zero weakly dependent score. It is not valid as a pre-opening calibration that treats the realized BitMEX path as a fixed design and draws an independent `Y`. Sealing forbids the second use. It does not forbid the first, and it does not make the application-time theorem false.

Under those conditions the theorem can cover predictable state weights, serial dependence within the mixing class, conditional heteroskedasticity carried by the observed score, subtraction of estimated stratum pool means, and multipliers that are restarted at structural gaps. Bandwidth is the mechanical horizon or another ex-ante rule. It is not an autocorrelation estimated on the confirmation path.

Fixed-b and DWB are both conditionally compatible with the narrowed null. Fixed-b matches a bandwidth ratio that is not taken to zero. DWB matches heteroskedasticity without requiring the homoskedastic Brownian limit. No choice between them is made here. No simulation is used to prefer either.

## G. Other methods

No other family is required. Self-normalized HAC is the fixed-b object already assessed. Subsampling at the mechanical horizon yields too few blocks for a uniform 0.05 test on this sample shape and needs its own long-block theorem. Exact tests under a finite Markov assumption replace the scientific null with a stronger parametric null. Test martingales change the inferential target. They are not substitutes forced by a hole in section E or F.

## H. Pre-target checkability

| Assumption | Status |
| --- | --- |
| Binary state, hence uniform moment bounds | Structurally guaranteed by the D7 definition |
| Strata are year × RV, finite in number | Structurally guaranteed |
| Mechanical overlap horizon 721 | Structurally guaranteed by the 720-hour rule plus the lead |
| Gap locations and year labels | Measurable from timestamps, without pairs |
| Published margins `T`, `K`, stratum counts | Already released aggregates, not lag-1 statistics |
| Predictability of `X_t` relative to `X_{t+1}` | Structural from `Y_t = X_{t+1}` |
| Second-order role of `K_s/K` | Theorem under the null, not a data check |
| Within-stratum lag-1 covariance of `p` is zero | This is the hypothesis, decided at opening, not before |
| Mixing or near-epoch dependence, and an upper bound on the long-run variance | External maintained assumption. Not structurally guaranteed. Estimating it on BitMEX uses the protected path |
| Homoskedastic Brownian limit | Not checkable before opening. Time-varying prevalence inside a cell is a function of the state path |
| Portability of Binance serial estimates to BitMEX | Not granted, and not a pre-opening test |

A profile that needs a BitMEX autocorrelation, run length, or transition count before opening cannot serve D7. The conditional methods in E and F do not need those estimates. They need the external mixing restriction to be accepted as a modeling assumption, with development surfaces used only to decide whether the assumption is even plausible in similar markets. A development pass is not evidence about BitMEX and is not an acceptance sample.

## I. Reusable profile

`SELF_REFERENTIAL_PROFILE_THEORETICALLY_SUPPORTABLE = true`

A later `SELF_REFERENTIAL_TIME_SERIES_CONTRAST_V1` can cover hypotheses of the form "state at `t` predicts a future transformation of the same process" when all of the following hold:

- the outcome is a lead, or a fixed measurable function of a lead, of the same process that defines treatment;
- treatment at `t` is predictable given information at `t`;
- the contrast is a weighted within-stratum excess with shares estimated from the sample;
- the stratum partition is finite, predetermined, and part of the hypothesis, not a latent label added to make a simulator null;
- the null is the within-stratum lag-1 covariance restriction of section A;
- the score class satisfies section C;
- bandwidth and multiplier law are fixed before any confirmation pair is read.

Excluded: an exogenous treatment with a separate outcome; a bare mean-zero class with unrestricted dependence; a null that is restored by enlarging the strata; a procedure that estimates confirmation-path memory before opening; exact randomization designs; group-exchangeability designs. D7 is an admission case under year × RV and `Y_t = X_{t+1}`. It is not the definition of the class.

The profile is supportable. It is not frozen by this review. Freezing now would still point validation at N3, N4, and N7.

## J. D7 admission

`D7_CONFIRMABLE_WITH_EXTERNAL_ASSUMPTIONS`

The sealed surface can carry one later opening under a procedure whose critical value does not use BitMEX pairs. The mixing and variance-profile assumptions are external. They are not structural, and they are not checked on the confirmation path. No new surface is required for that logic. Opening remains forbidden until a narrowed null and a frozen procedure exist. This review does not open anything.

## K. Next unit

`NARROW_NULL_CLASS_AND_REVIEW_AGAIN`

The defensible null is the within-stratum lag-1 covariance restriction plus the uniform weak-dependence class. N4 is an alternative. N3 and N7 are alternatives under frozen year × RV. The next unit rewrites the null class on that basis and reviews the rewritten class. It does not implement, simulate, or select between conditional fixed-b and conditional DWB by a tournament.

## L. Scientific status

`D7_HYPOTHESIS_FAILED = false`

`D7_BITMEX_PRIMARY_TARGET_OPENED = false`

`D7_PRIMARY_EFFECT_COMPUTED = false`

`PROFILE_VALIDATED = false`

`TARGET_OPENING = FORBIDDEN`

`FIXED_B_THEORETICALLY_VIABLE = CONDITIONAL`

`DWB_THEORETICALLY_VIABLE = CONDITIONAL`

`SELF_REFERENTIAL_PROFILE_THEORETICALLY_SUPPORTABLE = true`

`D7_CONFIRMABLE_WITH_EXTERNAL_ASSUMPTIONS`
