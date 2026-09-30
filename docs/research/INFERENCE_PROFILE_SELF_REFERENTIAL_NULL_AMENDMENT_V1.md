# Amendment review: global null, score, and bandwidth

**Reviewed records:** `INFERENCE_PROFILE_SELF_REFERENTIAL_TIME_SERIES_CONTRAST_V1` and its theory review.

**Review status:** `NARROW_NULL_CLASS_AND_REVIEW_AGAIN`

Theory only. No implementation, no simulation, no RNG, and no BitMEX lag-1 derivation. Prior design files are not edited.

`D7_HYPOTHESIS_FAILED = false`

`D7_BITMEX_PRIMARY_TARGET_OPENED = false`

`D7_PRIMARY_EFFECT_COMPUTED = false`

`PROFILE_VALIDATED = false`

`TARGET_OPENING = FORBIDDEN`

Every `Delta_s`, probability, and covariance below is pooled on the time index of frozen cell `s`, unless a pointwise object is named.

## A. Frozen D7 null

`D7_NULL = GLOBAL_WEIGHTED`

The frozen contrast is one weighted sum

`Delta = sum_s a_s Delta_s`, `a_s = K_s / K`,

`Delta_s = P_pool(X_{t+1}=1 | X_t=1, eligible_t, s) - P_pool(X_{t+1}=1 | eligible_t, s)`.

The confirmation statistical gate is a one-sided level-0.05 test of

`H0_global: Delta <= 0`

on that contrast. The size boundary inside this gate is

`Delta = 0`.

Evidence: `docs/research/D7_BITMEX_DEPENDENCE_INFERENCE_REVIEW_V0.md` states the gate as `H0: delta <= 0` on the pool-adjusted contrast. The discovery evaluator `evaluate_d7_scientific` compares one candidate mean with one rate-matched control distribution. It does not require `Delta_s = 0` in every year × RV cell. Year-level signs are a separate temporal gate: at least 2 of {2017, 2018, 2019}, with 2016 diagnostic. That gate allows a negative year. It is not a cellwise statistical null.

`H0_cellwise: Delta_s = 0 for every s` implies the global boundary. The converse is false: `Delta_1 > 0` and `Delta_2 < 0` can cancel in `sum a_s Delta_s`. Cellwise-zero laws are a subset used only when a proof says so. They are not the D7 null.

## B. Pooled moment representation

On cell `s`, with time measure uniform on the cell's eligible index,

`Cov_pool(X_t, X_{t+1} | s) = avg_t Cov_t(X_t, X_{t+1}) + cov_t(E[X_t], E[X_{t+1}])`.

`Cov_t` is the covariance at a fixed time. `cov_t` is the covariance of the two mean sequences over the cell's clock. For conditionally independent Bernoulli draws given a probability path `p`, `Cov_t = 0`, and the second term remains. A slow path has `cov_t(p_t, p_{t+1}) > 0`, so the pooled covariance is positive. Pointwise independence of innovations does not imply a zero pooled excess. N4 stays an alternative for that reason. `Cov_t = 0` at each hour does not put N4 in the null.

For a binary process the latent path is unnecessary. With `E_pool[X_t | s] > 0`,

`Delta_s = Cov_pool(X_t, X_{t+1} | s) / E_pool[X_t | s]`.

The denominator is the pooled treatment margin, the uniform time measure on the cell, not `Var(X_t)` and not `E[X_{t+1}]`. The global contrast is the `a_s`-weighted sum of these ratios. A reusable null statement is a restriction on these binary pooled moments.

## C. Global composite null

The boundary is the hyperplane `sum_s a_s Delta_s = 0`, including exact cancellation of positive and negative cell excesses.

Calibration on `Delta_s = 0` for every `s` controls type I on that subset. It does not, by itself, control type I uniformly on the hyperplane. Heterogeneous cancellation changes the first-order variance through the share terms in section D and the low-frequency quadratic form in section E. A critical value computed at the cellwise origin need not be an upper bound on rejection probability elsewhere on `Delta = 0`.

For the one-sided composite `Delta <= 0`, the least-favorable slice is the boundary `Delta = 0` when, for each fixed nuisance law, rejection probability is nondecreasing in the global contrast in a neighborhood of 0. That stochastic monotonicity is an extra condition, true for a pure location shift of a fixed dependence class and false if studentization or share estimation makes the law of the statistic depend on the cell vector `(Delta_s)` at fixed `Delta`. The nuisance dimensions that remain on `Delta = 0` are: the cell vector inside the hyperplane, the long-run variance profile, treatment-share limits, and within-cell heteroskedasticity. Uniform calibration has to cover those dimensions or the profile must say, in advance, which subset of the hyperplane it covers.

## D. Random shares and strata

Write `Delta_hat = sum_s a_hat_s Delta_hat_s` and `theta = sum_s lambda_s Delta_s`, with `lambda_s` the probability limit of `a_hat_s = K_s/K`.

`Delta_hat - theta = sum_s lambda_s (Delta_hat_s - Delta_s) + sum_s (a_hat_s - lambda_s) Delta_s + sum_s (a_hat_s - lambda_s)(Delta_hat_s - Delta_s)`.

The last sum is `O_p(n^{-1})` when both factors are `O_p(n^{-1/2})`. The middle sum is `O_p(n^{-1/2})` whenever the vector `(Delta_s)` is not zero, including on `theta = 0` with cancellation. The earlier claim that share error is second order used `Delta_s = O_p(n^{-1/2})`, which is the cellwise-zero boundary. It does not hold for fixed cancelling cell excesses.

Conditional on the realized stratum partition, cell counts `n_s` are fixed and `K_s` is still random, so `K_s/K` still contributes the middle term.

Deterministic strata, such as calendar year, fix membership in the time index. They do not fix `K_s`. The middle term is present.

Random strata, such as an RV bucket, also move `n_s` if the partition is redrawn. The frozen contrast is a functional of the realized partition, so the sampling law that matches the procedure is conditional on that partition (and on gaps and timestamps). Conditional on it, RV randomness does not add a further membership term. A law that redraws the RV field is a different experiment. Predetermined labels are allowed inside the conditional law. Labels that depend on `X_{t+1}` are not.

At `theta = 0` the quotient fluctuation of total `K` in the denominator is second order, because it multiplies a numerator with mean zero. Reallocation of shares across cells with different `Delta_s` is not that quotient and stays first order.

## E. Score and centering

Conditional on the realized finite partition, the cell influence of `Delta_s` and the share influence do not collapse on the global boundary. For `t` in cell `s`, the population quantities `pi_s = E_pool[X_t | s]`, `mu_s = E_pool[X_{t+1} | s]`, and `Delta_s` give the per-time contribution

`phi_t = lambda_s [ (X_t / pi_s) (X_{t+1} - mu_s - Delta_s) - (X_{t+1} - mu_s) ] + Delta_s (X_t - pi_s) / pi_bar`.

`pi_bar` is the pooled treatment margin that converts a unit change in `K_s` into a change in `a_s`. The first bracket is the cell-contrast influence. The last term is `sum_s (a_hat_s - lambda_s) Delta_s` in influence form. Its cell-wise sum is not zero when `Delta_s` differs across cells. Its `a_s`-weighted sum has mean zero on `theta = 0`.

Global centering imposes `theta^* = 0` and keeps this `phi`. Per-cell centering replaces every `Delta_s` by 0 inside `phi`, or recenters each cell's candidate mean to the pool mean in the reference distribution. That deletes the share term and the shift `mu_s + Delta_s` inside the cell. It is the influence of the cellwise origin, not of the global boundary. HAC, fixed-b, and a multiplier bootstrap all inherit the error if they are built from that reduced score.

Pool subtraction `X_{t+1} - mu_s` is part of `Delta_s` itself and stays. Subtracting `Delta_s` as well, cell by cell, in the reference law, is the forbidden extra centering.

### Deterministic-year heterogeneity

Let `m_t = E[phi_t | cell of t]` on the global boundary, so `sum_t m_t = 0` while `m_t` can be constant and nonzero on a calendar year. For a Bartlett kernel `k(h) = 1 - |h|/(B+1)` on `|h| <= B`, the kernel matrix is positive semidefinite and

`sum_{|h|<=B} k(h) = B + 1`.

The mean path contributes `m' K m >= 0` to the expected quadratic form. If each year is long relative to `B` and the per-time summands that add up to the contrast have conditional means of order `Delta_s / T`, this contribution is of order `(B+1) RMS(Delta_s)^2 / T` in the variance of the contrast. Then

`t ≍ sqrt(T / (B_T + 1)) * Delta_global / RMS(Delta_s)`

when that mean path dominates the quadratic form. This is an order identity under those assumptions, not a universal constant. On `Delta_global = 0` the same nonnegative term inflates the denominator relative to a cellwise-zero variance, which pushes size down, provided the inflation is present in the variance estimator that the test actually uses and is not offset by downward finite-sample bias of the HAC estimator. Those two effects have opposite signs. Heterogeneity of this kind is not, by itself, a proof of conservative size.

Power against a small global residual of large year effects is bounded by the display above. The temporal gate allows that configuration: two positive years and one negative year can pass the sign count while `RMS(Delta_s)` stays large relative to `Delta`. The statistical gate is then a low-power test of a small residual. The temporal gate does not remove the quadratic term.

## F. Regularity class

The reusable class is the set of binary lead contrasts on a finite predetermined partition for which the following hold uniformly, not only along one D7 sample.

| Restriction | Class | Scope |
| --- | --- | --- |
| Predictable state at `t` relative to the lead | `REQUIRED` | Pointwise, by the definition of the class |
| Finite predetermined partition; inference conditional on the realized labels | `REQUIRED` | Uniformly in the number of cells and in the labels' dependence on the lead, which is forbidden |
| Treatment shares in a fixed compact subset of `(0,1)` | `REQUIRED` | Uniformly |
| Bounded weight concentration | `REQUIRED` | Uniformly; a consequence of the share bound for rate-matched weights, stated so other weight maps stay covered |
| Vanishing total gap fraction | `REQUIRED` | Asymptotically, unless a profile variant rebuilds the limit on a positive-fraction gap set |
| Functional CLT for `phi` | `REQUIRED` | Uniformly on the declared null subset |
| Uniformly summable score autocovariance, with a uniform LRV upper bound and a uniform lower bound away from 0 where a studentized statistic is used | `REQUIRED` | Uniformly |
| Alpha-mixing, or near-epoch dependence, with uniform rates sufficient for that FCLT | `REQUIRED` | Uniformly; one of these two structures, not both |
| Piecewise weak dependence inside cells that occupy positive time | `REQUIRED` | Asymptotically |
| Strict stationarity of the whole record | `TOO_STRONG` | Optional special case; it forbids the year heterogeneity the temporal gate allows |
| Beta-mixing | `UNNECESSARY` | Stronger than the alpha-mixing route |
| Near-epoch dependence in addition to alpha-mixing | `UNNECESSARY` | A substitute, not an extra requirement |
| Random labels that are predetermined and then conditioned on | `OPTIONAL` | Allowed; redrawing them is not the frozen experiment |
| Cellwise `Delta_s = 0` | `UNNECESSARY` | Not the scientific null; using it as the whole uniformity class would strengthen H0 |

The profile states which subset of the hyperplane `sum a_s Delta_s = 0` is inside the uniformity claim. Until that subset is explicit, the class is not ready to freeze.

## G. Horizon definitions

`MECHANICAL_OVERLAP_HORIZON` is a construction fact supplied by the hypothesis. For the D7 adapter it is 721: shared trailing-window inputs of the state can still meet at valid-hour separation 721. It is a lower bound on how far construction-induced dependence can reach. It is not the inference bandwidth and it does not say that stochastic score memory ends at 721.

`INFERENCE_DEPENDENCE_BANDWIDTH` is the smoothing length in the variance estimator or the multiplier, owned by the profile, not read off the confirmation pairs.

`SCORE_MEMORY_ENVELOPE` is a maintained, uniform majorant on the tail of the score autocovariance. It is what justifies a bandwidth regime. It is not an estimate from the protected path.

A legal ex-ante rule is a profile-level sequence, plus the admission inequality that the bandwidth is at least the adapter's mechanical overlap, plus an envelope declared as maintained. Development samples may show that an envelope is not frivolous. They do not validate it for the confirmation venue, and they do not choose a numeric length equal to 721.

## H. Fixed-b semantics

`FIXED_B_REGIME_COHERENT = CONDITIONAL`

A constant 721 with `T → ∞` gives `B_T/T → 0`. That is small-bandwidth asymptotics, not fixed-b.

The coherent fixed-b sequence is `B_T = ceil(b0 * T)` with `b0 ∈ (0,1)` fixed before any confirmation pair is read. `b0` is generic profile metadata. It is not `721/T` and it is not fit per hypothesis. The adapter's mechanical overlap enters only as an admission check `B_T >= MECHANICAL_OVERLAP_HORIZON`. A hypothesis whose overlap exceeds the profile bandwidth at its sample size is outside the profile.

Under section F, partial sums of `phi` converge to a scale times Brownian motion only when the cell-mean path does not leave a nonvanishing nuisance in the limit. Non-shrinking cancelling `Delta_s` put a piecewise mean into `phi`. The Kiefer–Vogelsang functional of homoskedastic Brownian motion, and any `c(b, q)` table built from exogenous weights, is then not the limit. The reference depends on that cell-effect path and is not pivotal on the full hyperplane. Fixed-b is a coherent regime for the sequence `B_T`. It is a pivotal test for this class only on the subset of the hyperplane where that nuisance is absent or contiguous. The old `c(b, q)` construction is not reused.

## I. DWB semantics

The bootstrap score is `phi_t` from section E, including the share term. Centering is global: the bootstrap contrast is constrained to `theta^* = 0` and is not constrained to `Delta_s^* = 0`. Multipliers are external, mean zero, variance one, with `Cov(m_t, m_{t+h}) = k(h / l_T)`, independent of the data, and uncorrelated across structural gaps. Deterministic and random labels enter only through the conditioned partition. Weights are the predictable state together with the estimated shares already linearized in `phi`. Holding `X` fixed and multiplying a residual that omits `Delta_s (X_t - pi_s)` drops the first-order share term and is not a bootstrap of this score.

Classical dependent-wild consistency uses `l_T → ∞` and `l_T / T → 0`. That is a different regime from `B_T / T → b0 > 0`. A fixed mechanical floor is compatible with `l_T / T → 0` along a sequence in which `T` grows past any fixed overlap, because `l_T` may tend to infinity slower than `T`. The mechanical horizon still does not define `l_T`. A fixed-smoothing multiplier theorem would be required before `l_T / T → λ > 0` could be used. That theorem is not assumed here.

## J. Valid null families

N3, N4, and N7 as previously defined are removed. N3's extra latent stratum is not a frozen cell. N4's slow path has positive `cov_t(p_t, p_{t+1})`. N7 inherits N3.

Each family below is a binary construction with `Y_t = X_{t+1}` and `sum_s lambda_s Delta_s = 0`.

**G1, constant within cell.** Inside each frozen cell, `X_t` is iid Bernoulli(`p_s`) with `p_s` constant on the cell. Then both terms of the pooled-covariance decomposition are zero, so every `Delta_s = 0` and the weighted sum is zero. Different `p_s` across cells are allowed. This revises N1 and N5.

**G2, lag 2 without lag-1 covariance.** Inside each cell, a stationary Gaussian MA(2) with lag-1 coefficient 0 and a threshold constant on the cell. Joint normality and zero lag-1 covariance of the latent give `Cov_pool(X_t, X_{t+1} | s) = 0`, so `Delta_s = 0`. Lag 2 may be dependent. A non-Gaussian MA with only a zero lag-1 latent correlation is not this family.

**G3, gaps.** G1 or G2 inside each segment, with pairs that cross a gap omitted. Each included cell still has `Delta_s = 0`. This revises N6.

**G4, cancelling cells.** Two cells with equal `lambda`, stationary binary Markov laws with the same treatment margin `pi ∈ (0,1)` and cell excesses `+δ` and `-δ`, with `pi+δ ∈ (0,1)` and the implied `X_t=0` transition inside `(0,1)`. Then `Delta_s = ±δ` and `sum lambda_s Delta_s = 0`. This is on the global boundary and not in the cellwise subset. The same construction with deterministic year blocks is the year-heterogeneity null. The same construction with a predetermined RV-like label, conditional on that label, is the random-stratum null.

**G5, heteroskedastic score, zero excess.** Inside a cell, `p_t` is an exogenous sequence uncorrelated with `p_{t+1}`, and `X_t | p` is Bernoulli(`p_t`) independent across `t`. Then `Cov_t = 0` and `cov_t(p_t, p_{t+1}) = 0`, so `Cov_pool = 0` and `Delta_s = 0`, while `p_t(1-p_t)` may vary. A slow sinusoid is not this family.

**G6, envelope edge.** G2 with summable autocovariances arbitrarily close to the uniform summability bound of section F, and with the lag-1 binary covariance kept at zero by the Gaussian construction. Membership in `H0_global` is the same identity as G2. No draw is required to see it.

Persistent labels are allowed in G1–G3 when they are the hypothesis partition and the within-cell pooled covariance is zero. That does not add a latent regime to the strata.

## K. Maintained assumptions for D7

`D7_CONFIRMABLE_WITH_EXTERNAL_ASSUMPTIONS` means the following are maintained, not checked on the protected path, and not validated by another venue.

| Assumption | Why inference needs it | What can support plausibility | If violated |
| --- | --- | --- | --- |
| Uniform mixing or near-epoch envelope of `phi` | FCLT and a uniform critical value | A development panel can show the envelope is not empty of serious processes. That is motivation | Size is not controlled; a PASS is not confirmation under the label in section L |
| Uniform LRV upper bound and nondegeneracy | Studentized limits exist | Same, motivation only | Degenerate or infinite-variance limits; the reference is wrong |
| Stochastic memory may exceed 721, inside the declared envelope | The mechanical overlap is only a floor | Development decay can motivate a longer envelope. Using a Binance autocovariance as the BitMEX bandwidth would be an ungranted portability assumption | Bandwidth undercovers or overcovers; fixed-b and small-b justifications both fail |
| Uniformity subset of the hyperplane, once the profile names it | Section C | Not a data check | A PASS at the cellwise origin does not bound size on cancelling cells |
| Piecewise dependence inside the frozen partition rather than strict stationarity | Matches year blocks without forbidding their heterogeneity | The partition is structural; the dependence inside it is not | The FCLT on each piece fails |

Checkable without pairs, and therefore not in this maintained list: timestamps, the published gap, the mechanical overlap formula, and published share margins. Binance compatibility is not evidence about BitMEX. No cross-venue portability assumption is granted.

## L. Evidence label

A future statistical PASS that uses section K is stored as

`CONFIRMED_UNDER_MAINTAINED_ASSUMPTIONS`

It permits this sentence: the preregistered one-sided test rejected `H0_global` at the frozen level, conditional on the named assumption manifest. It does not permit an assumption-free or randomization-exact confirmation, a claim that mixing was verified on the confirmation path, a claim that another venue validated the envelope, a cellwise finding, or a trading-edge statement.

Provenance holds `evidence_label`, `assumption_manifest_id`, `profile_id`, the adapter's mechanical overlap, the profile bandwidth rule, and the gate result. Research summaries use the full label in the same sentence as the result. They do not shorten it to "confirmed" or "replicated".

The label is part of the contract before any opening.

## M. Post-opening diagnostics

After the single authorized opening, and not before, the realized score may be described: autocorrelation, run lengths, and variance stability across predetermined cells. These descriptions are diagnostic.

They do not change bandwidth, method, critical values, sample membership, strata, the null family, or the number of times the confirmatory statistic is evaluated.

`ASSUMPTION_DIAGNOSTIC_CLEAR`: the predeclared envelope still covers the diagnostic summaries. The evidence label stays `CONFIRMED_UNDER_MAINTAINED_ASSUMPTIONS`.

`ASSUMPTION_DIAGNOSTIC_WARNING`: a diagnostic sits outside the comfortable range of the envelope and inside the predeclared warning band. The mechanical gate does not change. Summaries must carry the warning on the same label.

`ASSUMPTION_DIAGNOSTIC_SEVERE_WARNING`: a diagnostic contradicts the envelope on a cutoff that was frozen before opening. The mechanical PASS stays a PASS. The displayed evidence label becomes `STATISTICAL_GATE_PASSED_BUT_ASSUMPTIONS_NOT_SUPPORTED`. That is a weaker claim, not a conversion of PASS into FAIL.

Numeric cutoffs for these bands are profile metadata frozen before opening. They are not chosen from the opened sample. This review does not set those numbers.

## N. Method comparison

`NEITHER_SUPPORTS_DECLARED_CLASS`

Both methods are scored against the same objects: `H0_global`, the cancelling-cell boundary, `phi` including the share term, global centering, section F, and section K.

Fixed-b, as `B_T = ceil(b0 T)`, is a coherent bandwidth regime and matches a non-vanishing ratio. Its pivotal Brownian limit does not cover non-shrinking cancelling cell effects or a nonstationary variance path. Year heterogeneity enters the quadratic form and can dominate power. Conditional-on-partition RV labels fit the experiment. The share term is present only if the HAC is built from `phi`, not from a cellwise-zero residual. Gaps of vanishing fraction fit. The missing theorem is a fixed-b limit for this `phi` that is uniform on the hyperplane the profile claims.

Dependent wild bootstrap, with global centering of the same `phi`, can carry a nuisance-dependent variance because the multipliers see the observed score, including heterogeneous cell levels and heteroskedasticity. That is a real advantage on the hyperplane. Classical consistency requires `l_T → ∞` and `l_T/T → 0`, which does not justify a fixed-b sequence. A bootstrap that freezes weights and drops `Delta_s (X_t - pi_s)` misses the share term. The missing theorem is consistency for this influence under the global boundary, in a bandwidth regime that also respects an unknown stochastic memory longer than the mechanical floor.

Neither standard package covers the class as declared. Historical NULL_3 behavior is not a reason for either verdict. No method is selected.

## O. Reusable profile

`SELF_REFERENTIAL_TIME_SERIES_CONTRAST_V1` is the primitive "predictable state at `t`, pooled within-cell lead excess, global weighted null, influence `phi`, profile-owned bandwidth regime, maintained envelope, evidence labels." It contains no numeric mechanical horizon, no practical threshold, no venue name, and no year × RV partition.

The D7 adapter may supply the estimand, the year × RV partition, mechanical overlap 721, the practical threshold 0.05, the upper one-sided direction, the temporal gate, and a declaration that section K is maintained. Another hypothesis supplies different values through the same fields. Profile code does not branch on those values.

Inclusion: binary or otherwise moment-bounded lead of the same process, finite predetermined partition, shares in the uniform compact set, global null `sum a_s Delta_s <= 0`, regularity of section F, bandwidth rule of section G. Exclusion: a separate exogenous outcome, a cellwise null substituted for the global null, a bandwidth set to the mechanical overlap, a pre-opening read of confirmation-path memory, exact randomization designs, and group-exchangeability designs.

## P. Next unit

`NARROW_NULL_CLASS_AND_REVIEW_AGAIN`

The scientific null stays global. The next unit narrows only the uniformity claim: which subset of `sum a_s Delta_s = 0` a later theorem actually covers. It does not restore N3, N4, or N7, does not select a method, and does not freeze a profile whose two candidate references lack that theorem.

## Q. Scientific status

`D7_HYPOTHESIS_FAILED = false`

`D7_BITMEX_PRIMARY_TARGET_OPENED = false`

`D7_PRIMARY_EFFECT_COMPUTED = false`

`PROFILE_VALIDATED = false`

`TARGET_OPENING = FORBIDDEN`

`D7_NULL = GLOBAL_WEIGHTED`

`FIXED_B_REGIME_COHERENT = CONDITIONAL`

`NEITHER_SUPPORTS_DECLARED_CLASS`
