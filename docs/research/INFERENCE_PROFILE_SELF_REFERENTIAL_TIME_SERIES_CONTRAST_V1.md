# Self-referential time-series contrast — design record

**Class:** `SELF_REFERENTIAL_TIME_SERIES_CONTRAST`

**Record id:** `SELF_REFERENTIAL_TIME_SERIES_CONTRAST_V1`

**Status:** `PRIMARY_METHOD_NOT_YET_SELECTABLE`

This is a design record. It does not implement a test, draw a validation sample, derive a numeric seed, or open a target. It does not modify `DEPENDENT_TIME_SERIES_CONTRAST_V1`. That profile remains not implementation-authorized, under `docs/research/INFERENCE_PROFILE_DEPENDENT_TIME_SERIES_CONTRAST_V1_REVIEW.md` with status `PRIMARY_METHOD_RECONSIDERATION_REQUIRED`.

`PROFILE_VALIDATED = false`

`IMPLEMENTATION_AUTHORIZED = false`

`TARGET_OPENING = FORBIDDEN`

`D7_HYPOTHESIS_FAILED = false`

`D7_BITMEX_PRIMARY_TARGET_OPENED = false`

`D7_PRIMARY_EFFECT_COMPUTED = false`

`SELF_REFERENTIAL_D7 = true`

Machine-readable flags live in `INFERENCE_PROFILE_SELF_REFERENTIAL_TIME_SERIES_CONTRAST_V1.json`. This record wins on scientific interpretation. The JSON wins on the tokens below. Neither file authorizes a run.

## A. Class definition

A hypothesis is a `SELF_REFERENTIAL_TIME_SERIES_CONTRAST` when all of the following hold.

1. There is one underlying process `X`. The predictor at `t` and the outcome at `t` are transformations of that same process. In the binary case that defines this record's first use, `outcome_t = X_{t+1}` and `treatment_t = X_t`.
2. The treatment geometry is a property of `X`, not an externally assigned design. Who is treated is random under the null law, and that randomness is the same randomness that produces the outcome.
3. The realized treatment path carries information about the null process. A long run of treated hours is a statement about `X`, and therefore about the shifted outcome.
4. Conditioning on the entire realized path of `X` conditions on the outcome. After the path is fixed, the contrast is a number, not a random variable still waiting for an independent `Y`.
5. A calibration that freezes the realized weights, or freezes `X`, and then draws `Y` from a law independent of that `X` answers a different question: an exogenous-design contrast. That question is the dependent-time-series class. It is not this class.

`DEPENDENT_TIME_SERIES_CONTRAST_V1` is the exogenous-design class. It is not extended here. The null-generation logic differs: this class has to generate the joint law of `(X_t, X_{t+1})`.

### Applicability

The class applies to a future hypothesis only when:

- the estimand is a weighted contrast of a future transformation of `X` against a baseline computed from the same process;
- the weights are determined by `X` and by covariates that are declared either exogenous or protected;
- the null is a restriction on that joint law, written so the contrast has mean zero by construction under every law in the null set;
- the confirmation surface's serial statistics of `X` are either still sealed or are an authorized one-shot opening, not a calibration sample;
- a separate exogenous-outcome profile would mis-state the null.

The class does not apply when the outcome is a different series from the treatment, when an exact randomization over an exogenous assignment exists, or when group exchangeability is the dependence that matters. Those remain the other inference classes.

## B. D7 estimand

`D7_ESTIMAND_PRESERVED = true`

The frozen D7 estimand is, for target-eligible hours,

`delta = sum_s (K_s / K) (mean(Y | X=1, s) - mean(Y | eligible, s))`.

The D7 definitions are `X_t = D7_STATE_t` and `Y_t = D7_STATE_{t+1} = X_{t+1}`. The state is binary. Stratum `s` is the calendar year × RV bucket of the predictor hour `t`, not the stratum of hour `t+1`. `K_s` and `K` are the realized candidate counts on the target-eligible index. The eligible pool in `s` contains both candidate and non-candidate hours.

On that index the sample means are the empirical probabilities, so the same number is

`delta = sum_s (K_s / K) [ P_n(X_{t+1}=1 | X_t=1, s) - P_n(X_{t+1}=1 | eligible_t, s) ]`.

That is the displayed self-referential form. It matches the frozen functional. It is not a silent change of claim.

Two identities are recorded so they are not mistaken for a new estimand.

- The control arm is the eligible pool, including hours with `X_t=1`. It is not the `X_t=0` arm alone.
- Because the pool is the mixture of the two arms, `mean_1 - mean_pool = (1 - pi_s) (mean_1 - mean_0)` with `pi_s = K_s / N_s`. Substituting that identity does not change the value of `delta`.

The one-sided confirmation hypothesis remains `delta > 0`, with practical gate `delta_hat >= 0.05` left outside this class. The boundary null that matches the frozen estimand is `delta = 0`.

### Null that matches the estimand

`H0(D7):` for every stratum `s` with positive eligible mass,

`P(X_{t+1}=1 | X_t=1, eligible_t, s) = P(X_{t+1}=1 | eligible_t, s)`.

When `0 < pi_s < 1`, this is the same statement as equality, inside `s`, of the one-step probability leaving state 1 and the one-step probability leaving state 0. The weighted excess is then zero.

This is the null of no stratified excess lag-1 transition probability relative to the eligible-pool rate.

The following stronger statements are not the frozen null, and they are not adopted as calibration targets:

- `X_{t+1}` independent of the whole history given `s`;
- a global order-0 or order-1 Markov restriction outside the strata;
- equal transition probabilities across strata;
- absence of every predictive covariate other than `s`.

A binary process that is persistent inside `s` has a positive excess inside `s`. That persistence is the alternative of this estimand, not a nuisance the null is required to absorb. Persistence that appears only because strata with different base rates are themselves persistent can still lie in `H0`, because the contrast conditions on `s`.

## C. Conditioning boundary

| Object | Class | Reason |
| --- | --- | --- |
| Timestamps | Safe | Clock identity. Does not pair states. |
| Structural gaps | Safe | Missing-clock breaks. The December 2016 hole is a gap definition, not a transition count. |
| Year labels | Safe | A function of the timestamp. |
| RV strata | Safe as covariates | RV buckets are functions of trailing absolute returns under the frozen rule. They are not the state bit. Publishing or reusing already constructed bucket labels does not pair `X_t` with `X_{t+1}`. |
| Quote activity, raw returns | Conditionally safe | Upstream inputs. Safe only if the D7 state rule is not applied to them. Applying that rule rebuilds `X`, and a shift of `X` is the target. |
| Impact-threshold history | Unsafe for confirmation use | The threshold path together with impact rebuilds the state. |
| D7 state path `X` on BitMEX | Protected | The path equals the target after a shift of one hour. |
| Candidate count `K`, and already published stratum counts of candidates | Safe as published margins | Counts of `X_t=1` are not pairs. This record does not recompute them from the path. |
| Stratum prevalence `K_s/N_s` from published margins | Safe as published margins | Same reason. Not a license to form new path statistics. |
| Transition counts | Protected | They are the target contrast. |
| Run lengths, episode durations, state persistence | Protected | Functions of the path that reconstruct lag-1 structure. |
| Autocorrelation of D7 state | Protected | A lag-1 autocorrelation is a function of the sealed pairs. |
| Binance 2020–2024 D7 outcomes | Development surface only | Exposed discovery. Not a confirmation sample and not a validation acceptance set. |

For BitMEX, any statistic that is a non-degenerate function of the pairs `(X_t, X_{t+1})` reconstructs the unopened target. That includes the contrast itself, a transition matrix, a lag-1 correlation, a run-length distribution, and a persistence or episode summary of the confirmation state path.

Procedural sealing is not mathematical absence. The state path was built in earlier units. This record forbids new operations on it. It does not claim the path is ignorant of `Y`.

## D. Primary inference direction

`PRIMARY_METHOD_NOT_YET_SELECTABLE`

Conditional-on-`X` references are the wrong null. The direction that matches `H0` is a joint law of the process, not a critical value bolted onto fixed BitMEX weights. Naming that direction does not yet name a test. A usable primary method needs one theorem that is not available:

**Missing result.** A single critical value, or a single Monte Carlo envelope, controls type I at `alpha = 0.05` uniformly over the composite null

`{ laws of X : the stratified excess delta(P) = 0 }`,

including laws with dependence at lags other than 1, laws whose unconditional clustering is absorbed by the declared strata, gap-segmented laws, and laws produced by the overlapping 720-hour state builder when the builder's inputs are restricted so the resulting state still has excess zero. The envelope must be a proved least-favorable or intersection property, not a menu of generators to be narrowed after seeing rejection rates.

Until that result exists, no inner procedure — joint Monte Carlo, wild bootstrap, or fixed-b — is the primary method. An empirical tournament among them is forbidden.

### Comparison that led here, with no runs

**A. Joint price-process generator, then the real D7 builder.** Represents self-reference, because the builder emits one path and the outcome is its shift. It represents `H0` only for those input laws for which the built state has stratified excess exactly zero. Overlapping thresholds do not provide that equality for free. Without the missing uniformity result, this generator is a probe of mechanical excess, not a null. Using it as `H0` would change the estimand into "excess beyond the builder under a chosen price law."

**B. Direct state-process generator with an explicit transition constraint.** Can represent `H0` exactly, by drawing `X_{t+1}` so its conditional mean given `X_t` and `s` equals the pool mean. It preserves self-reference. It does not automatically include mechanical dependence from the 720-hour builder. It is the right null for the state-level functional, and it is the family in section G. It is not yet a test.

**C. Conditional randomization given allowed sufficient statistics.** On a synthetic path, randomizing inside the null constraints can build a reference. On BitMEX, the sufficient statistics of the state path are protected whenever they determine lag-1 structure. Randomizing the sealed path would open it. Not an admission tool.

**D. Dependent wild bootstrap.** See section F. Invalid when conditioned on the observed BitMEX path.

**E. Markov or semi-Markov nulls.** An order-1 binary Markov chain inside `s` with a raised staying probability is the alternative: that raise is the excess. The only order-1 Markov law inside `H0` is conditional independence given `s`, which is stratum-wise iid. Holding-time laws with long sojourns inside `s` are alternatives. They are not used as nulls.

**F. No other construction** currently supplies the missing uniform critical value.

## E. Fixed-b verdict

`FIXED_B_NOT_JUSTIFIED`

The fixed-b Bartlett critical value `c(b, q)` is a limit for a studentized mean when the long-run variance is random because the bandwidth ratio stays positive, under a design that is exogenous to the score. In D7 the score at `t` is a function of `X_{t+1}` and the weight at `t` is a function of `X_t`. Neighboring weights depend on the same path. The Gaussian table with frozen weights is not a theorem about that score. Replacing the normal quantile by `c(b, q)` does not repair an independent-`Y` null. Fixed-b is not retained as the reference, is not a diagnostic to be reported as if it calibrated D7, and is not rejected because of the historical NULL_3 count. NULL_3 is development information and is not an acceptance set.

## F. DWB verdict

`DWB_NOT_SELECTABLE_CONDITIONAL_ON_X_INVALID`

A dependent wild bootstrap multiplies a score series by an external dependent multiplier and recenters. That estimates the null law of a statistic conditional on observed covariates when the score is a residual with mean zero given those covariates.

For D7 the natural score is `v_t = w_t (X_{t+1} - pool_mean_s(t))`. The weight `w_t` is a function of `X_t` and of the stratum counts, which are functions of the path. Conditioning on the observed BitMEX state path fixes every `X_{t+1}` and every weight. The multiplier is then applied to a constant that already is the target. That conditional bootstrap is not a null distribution for a sealed, self-referential contrast. It is invalid for D7 admission and for any pre-opening calibration on BitMEX.

The objections to the old non-overlapping block bootstrap — few unequal blocks, a circular-shift segment, a short percentile — do not by themselves rule out an external multiplier. They also do not prove the multiplier theorem for this score. An unconditional multiplier proof would have to be a theorem about the joint process under `H0`, with a bandwidth taken from the construction horizon or from a development prior, not from BitMEX serial estimates. That proof is part of the missing result in section D. Until it exists, DWB is not the primary method.

Quantities a multiplier method may use before opening are the safe objects in section C, plus synthetic joint paths. The observed BitMEX score series is not among them.

## G. Joint null family

Every null family below generates one process `X`. The outcome used by the contrast is `Y_t = X_{t+1}`. No family draws `Y` independently of `X`.

**Common guarantee.** Stratum labels `S_t` are generated from a process independent of a latent Gaussian sequence `Z`. The state is `X_t = 1{Z_t > c(S_t)}`, except in the exogenous-drift family, where the threshold may also depend on `t` through a function independent of `Z` and of `X`. Pairs that cross a structural gap are not in the contrast. On every in-contrast pair, `(Z_t, Z_{t+1})` is bivariate normal with covariance 0, so `Z_{t+1}` is independent of `Z_t`. Then

`P(X_{t+1}=1 | Z_t, S) = P(Z_{t+1} > c(S_{t+1}, t+1) | S)`,

which does not depend on `Z_t` and therefore does not depend on `X_t`. Taking the expectation given `X_t=1` and `S_t=s` gives the same value as the expectation given `S_t=s` alone. The stratified excess is 0, so `E_null[delta] = 0`. Weights built from the realized `X` inside each stratum do not change this, because the identity holds inside each stratum before weighting.

Unconditional serial correlation of `X` may still be nonzero when `S_t` is persistent and `c(S)` varies. That correlation is between-stratum composition. The contrast removes it by stratifying. A generator that raises `P(X_{t+1}=1 | X_t=1, s)` above `P(X_{t+1}=1 | s)` is not in this family. In particular, a within-stratum two-state Markov chain with unequal transition probabilities is an alternative, not a null member.

| Id | What varies | Law | Why `E[delta]=0` |
| --- | --- | --- | --- |
| N1 | Marginal prevalence | `c(s)` set so `P(X_t=1\|s)=p_s`, `p_s` in `(0.05, 0.30)`, `Z_t` iid standard normal | `(Z_t, Z_{t+1})` independent. Candidate and pool means both equal `p_s`. |
| N2 | Dependence at lag 2 and beyond, none at lag 1 | Gaussian MA(2), `Z_t = ε_t + θ ε_{t-2}`, `θ` in `(0.2, 0.8)`, coefficient on `ε_{t-1}` fixed at 0 | `Cov(Z_t, Z_{t+1})=0` with joint normality, so the lag-1 pair of `Z` is independent while `Cov(Z_t, Z_{t+2})≠0`. The common guarantee applies inside each `s`. |
| N3 | Unconditional run lengths and regime persistence | `S_t` is a slow exogenous two-state regime, mean duration log-uniform on `[24, 4000]`, and `S_t` is one of the contrast's strata. `Z_t` iid given `S` | Inside `s` the series is iid, so the excess is 0. Unconditionally `X` clusters because the regime persists. Within-stratum holding times stay geometric. A long sojourn drawn inside `s` is not used. |
| N4 | Low-frequency drift | `p(s,t) = clip(p_s + A sin(2π t/τ + φ), 0.02, 0.40)`, `A` in `(0.05, 0.20)`, `τ` log-uniform on `[48, 5000]`, phase exogenous, `Z_t` iid | The threshold depends on `(s,t)` only. Independence of `Z_{t+1}` from `Z_t` keeps the conditional mean equal to the stratum-time pool mean, and therefore equal after averaging time inside `s`. |
| N5 | Prevalence tied to strata, heterogeneous levels | `p_s` a fixed function of the stratum label, distinct across `s`, no within-stratum transition gap | Heterogeneity of base rates is not heterogeneity of excess. Each stratum contributes excess 0, so the `K_s/K` average does. |
| N6 | Structural gaps | Gap count in `{0,1,2,3}`, process restarted in each segment, contrast pairs required to lie inside one segment | The equality is per in-sample pair. Pairs that do not exist are not in `delta`. |
| N7 | Higher-order mixture | N2 latent inside the N3 regime strata, gaps as in N6 | Each piece satisfies the common guarantee. The product still has `Cov(Z_t,Z_{t+1}\|S)=0`. |

`E_null[delta]=0` is the population statement under these laws. It is not a claim about a Monte Carlo estimate, and this unit draws none of the laws.

Development copies of N1–N7 may be studied later under a development label. They are not the held-out acceptance sample. Known D7 NW721 results, NULL_0–NULL_4, and the seeds `20260930171`, `20260930181`, `20260930211`, `20260930311`, `20260930317`, `20260930427`, and `20260930431` are development information. They are not members of the held-out family and are not acceptance data.

## H. Nuisance sources

`MECHANICAL_DEPENDENCE` is the dependence implied by the construction rule: trailing 720 hours, a next-hour outcome, and score overlap that ends at valid-hour separation 721. It is an arithmetic property of the definition. It does not require the BitMEX state path. A future method may take `H_mechanical = 721` from that definition. That number is not an estimated memory of BitMEX.

`EMPIRICAL_PROCESS_MEMORY` is the serial structure of the state as a stochastic process: autocorrelation, run lengths, regime durations estimated from states, transition rates. On BitMEX this memory is protected. It is not estimated here and must not be estimated from the confirmation path in order to tune a null.

| Source | May provide | May not provide |
| --- | --- | --- |
| Construction rule | Mechanical horizon 721, stratum definition, eligibility rule | An empirical BitMEX memory estimate |
| Already published BitMEX margins | `T`, `K`, gap existence, year and RV as labels | Pairs, runs, autocorrelations, new path summaries |
| Binance 2020–2024 | Development sketches of which alternative laws are worth writing down | Held-out acceptance counts, or a point estimate transplanted as the BitMEX null |
| Other exposed exchanges | Same, and only if their D7-equivalent target is already an exposed development surface | A silent proxy for BitMEX pairs |
| Synthetic priors in section G | The composite null used for a future uniformity proof | A fitted BitMEX parameter |
| Theoretical bounds | Inequalities that do not use the sealed pairs | A data-dependent bandwidth |

No portability assumption between Binance and BitMEX is granted. A method that needs the BitMEX law's empirical memory as a nuisance parameter cannot take it from Binance without adding a portability hypothesis this record does not contain. Such a method is not admissible for D7 pre-opening.

## I. Profile validation

Validation is specified so a later theorem can be checked. It is not authorized to run.

**Gate 1 — profile validation.** A future method for this class passes only if, under every held-out law in N1–N7, the type I rate at the boundary `delta=0` satisfies the project's existing ceiling: Wilson 95% upper bound logic with `alpha=0.05` and ceiling `0.06`, applied to the method's rejection indicator. The sample size, the quantile rule across configurations, and the configuration count are part of the method's own proof record. They are not frozen here, because freezing a Monte Carlo budget for an unselected statistic would pretend the statistic exists. The held-out laws are the families in section G, drawn once, after the seed rule in section L, with no redraw aimed at failures.

The development copies of those families, and every historical D7 simulation, stay on the development side of the wall. A pass on development copies is not Gate 1.

`TYPE_I_VALIDATION_FIRST` remains the order: power is undefined until a method has a type I theorem and a sealed type I record.

## J. D7 admission

**Gate 2 — hypothesis admission.** D7 may be compared with a future validated profile only through safe objects.

Admissible without opening the target:

- the estimand text in section B and the mechanical horizon 721;
- published design margins (`T`, `K`, stratum definition, gap definition, one-sided positive hypothesis, practical threshold 0.05);
- confirmation that the outcome accessor is the sealed shift and has not been called;
- confirmation that weights, once an opening exists, will be the frozen rate-matched weights.

Not admissible before opening:

- any serial statistic of the BitMEX state;
- a bandwidth estimated from that state;
- a transition table;
- a check that "D7's run lengths sit inside the validation range," because measuring those run lengths opens the structure the null is about.

`D7_ADMISSION_REQUIRES_EXTERNAL_OR_DEVELOPMENT_PRIOR`

Empirical-process-memory admission cannot be completed from BitMEX. It can be completed only if the future method's nuisance list is empty of BitMEX serial parameters, or if those parameters are replaced by the mechanical horizon and by the synthetic null set. A method that cannot state its critical value without a BitMEX run-length or autocorrelation is `D7_PROFILE_INAPPLICABLE`. This record does not declare the whole class inapplicable: the geometry margins and the mechanical horizon are available, and the missing piece is the uniform reference theorem, not a hidden look at the pairs.

`D7_PROFILE_ADMISSION` is not `PASS`. No profile is validated, so admission cannot pass.

## K. Power

`D7_POWER_NOT_YET_DEFINED`

An alternative has to be the same joint process with a nonzero excess. Independent synthetic `Y` on fixed `X` is forbidden. A Markov shift that sets

`P(X_{t+1}=1 | X_t=1, s) = P(X_{t+1}=1 | s) + 0.05`,

with the implied `X_t=0` probability kept inside `(0,1)` and the stratum marginal held fixed, is the alternative that matches the estimand algebraically. It is not adopted as the power design. Power is the rejection probability of a selected test under a stated alternative. There is no selected test, and the composite null's least favorable law is the missing theorem. A power number against one Markov alternative would describe a different, smaller problem. The temporal gate is not part of power and is not evaluated.

## L. Seed and holdout contract

No validation seed is chosen in this unit. No beacon pulse is fetched. No tree hash of an implementation is recorded, because no implementation exists.

When an implementation commit is later frozen, the seed material for a label is HMAC-SHA256, not a byte-sum mixer.

- Domain key, UTF-8: `signalbot/self-referential-time-series-contrast/v1`
- Message, length-prefixed with unsigned 64-bit big-endian lengths, in this order: profile id, lowercase hex git tree OID of that implementation commit (`git rev-parse <commit>^{tree}`), drand quicknet chain hash pinned in the implementation manifest before any pulse is read, decimal pulse round, the 32-byte pulse randomness, and the UTF-8 label.
- The pulse is the earliest quicknet round whose published timestamp is strictly greater than the implementation commit's committer timestamp plus 86400 seconds.
- `digest = HMAC-SHA256(domain_key, message)`.
- The generator is `numpy.random.Generator(numpy.random.PCG64(numpy.random.SeedSequence(digest)))`.

Labels for held-out streams start with `sr-v1:`. Development streams, if any, use a different domain key ending in `/development` and are not acceptance. The historical integer seeds listed in section G are not inputs to this HMAC. One beacon covers the held-out validation. A failed configuration does not get a new beacon.

## M. Target-sealing guards

Forbidden on BitMEX D7 state, in code or in an interactive calculation, until a written opening decision names the one authorized contrast:

- `shift` of the state by `-1` or `+1`, `numpy.roll`, `ndarray.take` with a one-step index, or a join of the state to itself on the next timestamp;
- construction of the pairs `(state_t, state_{t+1})`;
- transition matrices and lag-1 frequencies;
- autocorrelation, `corrcoef`, or a regression of the state on its lag;
- run-length, episode, persistence, or holding-time summaries;
- any statistic equal to the weighted contrast or to a monotone function of the same pairs.

Proposed interface, not implemented here:

- a `SealedStatePath` object exposes published margins and mechanical constants only;
- `lag1`, `shift`, `autocorrelation`, `run_lengths`, and `contrast` raise `SealError`;
- the raw state array is not a return value of the public adapter;
- a future unit test parses the adapter's AST and fails if those operations appear.

The guard is a brake on accidents. It is not a proof that no other function of the path equals the target. Review of any BitMEX D7 change includes that question.

## N. Reuse contract

A later hypothesis may use this class only when section A applies, its estimand is the stratified excess of a shift of its own process, its null is the corresponding mean-zero restriction, and its confirmation path is sealed the same way. It supplies its own stratum definition and its own mechanical horizon. It does not inherit 721 unless its construction has the same overlap.

`NEW_INFERENCE_DESIGN_REQUIRED_IF` the outcome is a different series, the assignment is exogenous, an exact randomization is available, the estimand is not this excess, or the method needs protected serial statistics from the confirmation surface.

Reuse of the class is not reuse of an implementation. There is no validated profile to call.

`DEPENDENT_TIME_SERIES_CONTRAST_V1` is not a fallback and is not amended into this class.

## O. Next unit

`THEORETICAL_REVIEW_REQUIRED`

The next unit is a proof or a proved counterexample for the uniform type I statement in section D. It is not an implementation, not a simulation study, and not a new primary-method nomination. `FREEZE_SELF_REFERENTIAL_PROFILE_CONTRACT` waits on that result. `D7_NOT_CONFIRMABLE_WITH_CURRENT_INFORMATION` is the wrong branch: the pairs exist and stay sealed; what is missing is a reference distribution that respects the seal.

## P. Scientific status

`D7_HYPOTHESIS_FAILED = false`

`D7_BITMEX_PRIMARY_TARGET_OPENED = false`

`D7_PRIMARY_EFFECT_COMPUTED = false`

`TARGET_OPENING = FORBIDDEN`

`PROFILE_VALIDATED = false`

`PRIMARY_METHOD_NOT_YET_SELECTABLE`

`D7_ESTIMAND_PRESERVED = true`

`FIXED_B_NOT_JUSTIFIED`

`DWB_NOT_SELECTABLE_CONDITIONAL_ON_X_INVALID`

`D7_POWER_NOT_YET_DEFINED`

`D7_ADMISSION_REQUIRES_EXTERNAL_OR_DEVELOPMENT_PRIOR`
