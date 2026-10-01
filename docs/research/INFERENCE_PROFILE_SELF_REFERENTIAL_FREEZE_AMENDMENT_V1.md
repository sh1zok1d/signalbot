# Freeze amendment for the self-referential contrast

**Amends:** `INFERENCE_PROFILE_SELF_REFERENTIAL_CONTRACT_READINESS_V1`

**Review status:** `PROFILE_CONTRACT_NOT_READY:ENVELOPE_G_UNSPECIFIED`

This amendment does not reopen method selection. No implementation, no simulation, no RNG stream, and no BitMEX lag-1 reconstruction.

`PRIMARY_METHOD = STUDENTIZED_FULL_IF_DWB`

`PRIMARY_METHOD_CHANGED = false`

`NO_AUTOMATIC_METHOD_SWITCHING = true`

`D7_HYPOTHESIS_FAILED = false`

`D7_BITMEX_PRIMARY_TARGET_OPENED = false`

`D7_PRIMARY_EFFECT_COMPUTED = false`

`PROFILE_VALIDATED = false`

`TARGET_OPENING = FORBIDDEN`

The normalized dependence cutoff is not fixed below. Every other contract choice in this amendment is fixed. Readiness fails on that one constant.

## A. Validation and admission

Three objects stay distinct.

`PROFILE_VALIDATION_DESIGN` is the finite list of anchor geometries named in the readiness review: dyadic lengths, cell counts, prevalence anchors, block counts, gap patterns, and mechanical-ratio anchors. Running those anchors is how the generic mechanism is checked. The list is not a filled rectangle. A length, a cell count, or a ratio that merely sits between two anchors is not an anchor.

`PROFILE_VALIDATED_DOMAIN` is the subset of those anchors that pass the frozen type-I rule after the runs exist. It is a finite set of tested geometries. It does not contain the line segments that join them. No hypothesis is admitted by coordinate-wise interpolation.

`HYPOTHESIS_GEOMETRY_ADMISSION` is a separate outcome-blind type-I check on that hypothesis's own geometry: its `T`, its gaps, its deterministic blocks, its declared cells, its aggregate margins, and its mechanical horizon. Generic validation does not substitute for it.

`PROFILE_VALIDATED = true` is necessary for a later target opening and is not sufficient. Opening also needs `HYPOTHESIS_GEOMETRY_ADMISSION = PASS` and, after that, `HYPOTHESIS_POWER_GATE = PASS`. The power gate is not defined in this amendment and is not run. Current `PROFILE_VALIDATED` remains false.

## B. D7 exact-geometry admission

After generic validation has passed, D7 requires `D7_EXACT_GEOMETRY_ADMISSION` before any target opening. Failure sets `D7_PROFILE_ADMISSION = FAIL` and keeps `TARGET_OPENING = FORBIDDEN`. It does not revoke a generic profile pass.

Outcome-blind geometry taken from the published support record, not from a state path:

- `T = 30354`
- one structural gap, the published half-open clock interval `[2016-12-06T23:55:00.000Z, 2016-12-07T23:55:00.000Z)`, inside calendar year 2016; the eligible-index break is the one that abuts that interval on timestamps alone
- deterministic blocks are the calendar years 2016, 2017, 2018, 2019, with published eligible masses 4079, 8757, 8759, and 8759
- 16 declared cells, year × RV bucket `{0,1,2,3}`, with the published eligible and candidate margins in `D7_BITMEX_SUPPORT_AND_POWER_V0.json`
- candidate total `K = 3438`
- `H_mechanical = 721`
- `B_T = L_T = max(721, ceil(30354^{1/3})) = 721`

The real state path, lag-1 pairs, transitions, run lengths, autocorrelations, episode lengths, and the real time-ordered RV trajectory are not inputs. Synthetic labels and synthetic `X` are.

Population cell rates are the published ratios `pi_s = candidate_n / eligible_n`. Sample counts are not pinned to the published integers.

Admission replicates per gating configuration: `N_CONFIG = 1825`. This is the smallest integer `n` with

`sqrt(0.05 * 0.95 / n) ≤ (0.06 - 0.05) / z`,

`z = 1.959963984540054`. The Monte Carlo scale of a calibrated 0.05 rate then fits inside the gap between `α` and the ceiling. The count is not taken from a D7 rejection frequency.

Type-I rule, each gating configuration separately: the Wilson 95% upper bound of the one-sided rejection count is at most `0.06`. The point estimate is not the rule. One configuration failing fails admission.

The admission seed uses the same HMAC construction as K, with purpose `D7_EXACT_GEOMETRY_ADMISSION`. One beacon value, one stream, no rerun.

What cannot be frozen yet is which of these laws sit inside the dependence class. That comparison needs `G_MAX`. Until it exists, no D7 configuration is an executable gate.

## C. Mechanical horizon

Along every sequence in `THEORETICAL_PROFILE_DOMAIN`,

`H_mechanical(T) / T → 0`.

A horizon that stays a fixed integer is in that class. A horizon proportional to `T` is not. An adapter that cannot justify an `o(T)` horizon gets `PROFILE_ADMISSION_OUT_OF_THEORETICAL_DOMAIN`.

`FINITE_SAMPLE_STRESS_GEOMETRY` may include the anchor ratios `0.01, 0.02, 0.05, 0.10`. Those runs stress the finite sample. They do not add proportional horizons to the asymptotic class.

## D. Bartlett PSD

The previous claim that gap restriction can make the Bartlett form genuinely negative is retracted.

Let `x_t = a_t - ā` with `ā` the mean over the eligible index, and let `B` be the positive integer bandwidth. `T * V(a; B) = x' K x`, where `K` is zero across structural gaps and, inside a gap-free segment,

`K_ts = 1 - |t-s| / B` when `|t-s| < B`, and `0` otherwise.

On one segment, with `x` read as zero outside that segment,

`x' K x = (1/B) sum_u (sum_{j=0}^{B-1} x_{u+j})^2`.

The coefficient of `x_p x_q` in the expanded right-hand side is the number of windows that cover both indices, divided by `B`, which is `(1 - |p-q|/B)` when `|p-q| < B`. The identity is the quadratic form. Each window square is nonnegative, so each segment block is positive semidefinite, the block-diagonal `K` is positive semidefinite, and `V(a; B) ≥ 0` for every real `a`.

Each segment block is positive definite for every finite length `n ≥ 1` and every integer `B ≥ 1`. If every window sum vanishes, the window that meets the segment in only its first index forces that coordinate to `0`, and each following window forces the next coordinate to `0`. The only null vector is `0`. A block-diagonal matrix of positive definite blocks is positive definite, so `V(a; B) = 0` if and only if `x ≡ 0`, if and only if `a` is constant on the eligible index.

For the block-centered influence, the sample mean of `c` is `0`, so `V_obs = 0` if and only if `c_t = 0` for every eligible `t`.

## E. Numerical variance semantics

Working precision is binary64. `ε = 2^{-52}`.

Let `Γ0(a) = T^{-1} sum_t (a_t - ā)^2`. Sequential summation of `T` terms has the standard factor `γ_T = T ε / (1 - T ε)`. For every `T` in the validation anchors, `T ε < 1/2`, so `γ_T ≤ 2 T ε`. The absolute error in each `Γ(h)` is at most `γ_T Γ0` under the bound `sum_t |x_t x_{t+h}| ≤ T Γ0`. The Bartlett combination has one `Γ(0)` term and a two-sided sum over at most `B - 1` lags, and `1 + 2(B - 1) = 2B - 1 ≤ 2B`. Therefore

`tol(a) = 4 * T * B_T * ε * Γ0(a)`

whenever `Γ0(a) > 0`. The factor `4` is `2` from `γ_T ≤ 2 T ε` times `2` from `2B`. It does not depend on D7. If `Γ0(a) = 0`, the tolerance is not evaluated.

Observed statistic, before any bootstrap draw:

- `Γ0(c) = 0`, equivalently `c ≡ 0` in the working arithmetic: `VARIANCE_DEGENERATE`. No pass/fail.
- `-tol(c) ≤ V_obs < 0`: snap to the degeneracy state `VARIANCE_DEGENERATE`. No pass/fail.
- `V_obs < -tol(c)`: `INFERENCE_IMPLEMENTATION_ERROR`. A materially negative value contradicts D.
- `V_obs > 0`: ordinary studentized statistic, including a small positive value.

Bootstrap draws use `a = η^{(r)} ∘ c` and `tol` from that draw's own `Γ0`.

The rule that sent `V_r* ≤ 0` to `T_r* = +∞` is deleted. A nonpositive bootstrap variance is not an upper-tail count.

If any draw is in one of these states, the confirmatory run stops. The draw is not dropped, not replaced, `R` is not reduced, and no second seed is drawn.

- `Γ0 = 0` or `V_r* = 0`: `BOOTSTRAP_VARIANCE_DEGENERATE`
- `-tol ≤ V_r* < 0`: `BOOTSTRAP_VARIANCE_NUMERICAL`
- `V_r* < -tol`: `INFERENCE_IMPLEMENTATION_ERROR`

With `c` not identically zero and a nondegenerate Gaussian on each segment that `c` charges, `η ∘ c ≡ 0` is a lower-dimensional set and has probability zero. A small positive `V_r*` stays a real draw.

## F. Normalized envelope

For a law `P` of the block-centered influence with `γ_P(0) > 0`,

`G_norm(P) = sum_{h≥1} h |γ_P(h)| / γ_P(0)`.

The class restriction intended for the profile is `G_norm(P) ≤ G_MAX`. The symbol `G_MAX` is not given a number in this amendment.

## G. G_MAX

`PROFILE_CONTRACT_NOT_READY:ENVELOPE_G_UNSPECIFIED`

`sum_{h≥1} h |γ(h)| < ∞` has no canonical finite cutoff. Three natural ways to pick one were checked and rejected.

- Matching the Bartlett bias bound to the HAC sampling scale at the smallest anchor, `T = 2^{11}` and `B = ceil(T^{1/3}) = 13`, produces a cutoff near `1/2`. An autocovariance that is nonzero over a fixed mechanical horizon of several hundred lags lies far above that cutoff. The profile's own fixed-horizon adapters would sit outside the class by construction.
- A cutoff of order `H^2` large enough to contain a triangular autocovariance of width `H` makes the bias bound in H vacuous, and it imports a particular horizon into a profile constant.
- A round intermediate integer would be a convenience choice. It is not used.

No D7 rejection count, NULL_3 rate, or BitMEX state summary enters this refusal.

## H. Bandwidth-bias relation

For a stationary influence with mean zero and `G_norm` finite, the population Bartlett functional at integer `B` obeys

`|ω - V_pop(B)| / γ(0) ≤ 2 G_norm / B`.

The kernel-weight piece, lags `1 ≤ h < B`, contributes at most `(2/B) sum_{h<B} h |γ(h)| / γ(0)`. The omitted tail, lags `h ≥ B`, contributes at most `(2/B) sum_{h≥B} h |γ(h)| / γ(0)`, because `|γ(h)| ≤ h |γ(h)| / B` on that range. The two pieces add to the displayed bound.

Under `B_T = max(H_mechanical, ceil(T^{1/3}))` and `G_norm ≤ G_MAX`,

`|ω - V_pop(B_T)| / γ(0) ≤ 2 G_MAX / max(H_mechanical, ceil(T^{1/3}))`.

Along a theoretical sequence with `H_mechanical = o(T)` and `G_MAX` finite, the right-hand side tends to `0`. The inequality is not an executable class restriction until `G_MAX` is a number.

## I. Envelope-edge validation

A dependence family is legal as a gate only when its `G_norm` is known from the DGP formula, not from a retained simulation path. The operational partition, once a number exists, is:

- interior: analytic `G_norm ≤ G_MAX / 2`
- near-edge: analytic `G_norm` in `(G_MAX / 2, G_MAX)`
- edge: analytic `G_norm = G_MAX`

An AR(1) label or shock with autocorrelation `ρ` has `G_norm = |ρ| / (1 - |ρ|)^2` when the influence inherits that autocovariance up to the cell scaling. That formula is the construction template. The `ρ` that hits `G_MAX` is not solvable until `G_MAX` is fixed, so the edge family is not executable now.

## J. D7 admission nulls

Every law below has population `g(m) = 0` by the moment algebra, not by passing synthetic series through the 720-hour state builder. Builder replay is `NON_GATING_CONSTRUCTION_DIAGNOSTIC` unless a separate proof puts that law on `g(m) = 0`. No such proof is claimed.

Shared index: the published year masses, the one timestamp-defined gap, and synthetic labels. Two label mechanisms are defined.

- `IID_LABELS`: inside each year, labels are iid categorical with probabilities proportional to that year's published eligible margins, drawn before `X`.
- `CONTIGUOUS_BLOCKS`: inside each year, buckets run `0,1,2,3` in contiguous blocks with the published eligible lengths. This order is synthetic. It is not the archived RV trajectory.

`CELLWISE_ZERO` on either label mechanism: given the whole label path, the `X_t` are independent Bernoulli(`pi_{S_t}`). Then

`E[X_t X_{t+1} | S_t = s] = pi_s E[pi_{S_{t+1}} | S_t = s] = E[X_t | S_t = s] E[X_{t+1} | S_t = s]`,

so every `Delta_s = 0` and `g(m) = 0`.

`CANCELLING_CONTIGUOUS_BLOCKS`: labels use `CONTIGUOUS_BLOCKS`. Given labels, `X` is generated in order. On a pair that stays inside `2017:3` or `2019:3` and does not cross the gap,

`P(X_{t+1} = 1 | X_t, labels) = pi_s + c_s (X_t - pi_s)`.

On every other pair, `X_{t+1}` is drawn from Bernoulli(`pi_{S_{t+1}}`) and the shift is off. Margins are preserved by induction because the shift has conditional mean zero. With one exit from each of those two blocks,

`Delta_s = ((n_s - 1) / n_s) c_s (1 - pi_s)`

for `s` in `{2017:3, 2019:3}`, and `Delta_s = 0` otherwise. Freeze `c_{2019:3} = -1/4` and

`c_{2017:3} = - Delta_{2019:3} * (482 / 697) / (((2427 - 1) / 2427) (1 - 697/2427))`,

which is the unique value that enforces `sum_s (K_s / K) Delta_s = 0`. Both conditional probabilities on those cells lie in `(0, 1)`: the negative coefficient `-1/4` is above `-pi/(1-pi) = -482/1691` for `2019:3`, and the implied positive coefficient for `2017:3` lies in `(0, 1)`.

These three laws are global-null constructions. They become gating configurations only when their analytic `G_norm` is shown to be at most `G_MAX`. That comparison is blocked in G. Heterogeneous published `pi_s` is already inside each law.

## K. Confirmatory seed

No numeric seed is chosen here.

`profile_id = SELF_REFERENTIAL_TIME_SERIES_CONTRAST_V1`

`profile_version = FREEZE_AMENDMENT_V1`

`purpose = CONFIRMATORY_DWB_MULTIPLIERS`

`beacon_id = NIST-Beacon-2.0`

The beacon value is the `outputValue` of the first NIST beacon pulse whose timestamp is strictly later than the committer time of the implementation-and-admission freeze commit. One pulse.

`adapter_digest` is SHA-256 over the UTF-8 JSON of the D7 geometry in B, keys sorted lexicographically, separators comma and colon, no insignificant whitespace.

`tree` is the lowercase hex `git` tree hash of that same freeze commit.

The HMAC key is the UTF-8 string `profile_id || "/" || profile_version`. The message is the UTF-8 string

`v1\n`
`tree:<tree>\n`
`adapter:<adapter_digest>\n`
`beacon_id:<beacon_id>\n`
`beacon_time:<pulse timestamp>\n`
`beacon_value:<outputValue>\n`
`purpose:<purpose>\n`

The digest is HMAC-SHA256. It is the entropy input of HMAC_DRBG with SHA-256, empty nonce, and empty personalization string, as in NIST SP 800-90A. The generator is not seeded by a sum of bytes and not by a truncated integer. It produces the `R = 9999` segment-wise Gaussian multiplier draws for the one confirmatory run.

A bootstrap variance failure, a p-value near `0.05`, a disagreeing sensitivity, or a preferred second seed does not authorize another stream.

## L. Finite-R reporting

`R = 9999` and

`p = (1 + #{r : T_r* ≥ T_obs}) / (R + 1)`

remain the decision rule. The reported result includes the exceedance count, `R`, `p`, and the binomial standard error `sqrt(p_hat (1 - p_hat) / R)` at `p_hat = exceedance_count / R`. That standard error is a report. It does not move the threshold `0.05`.

## M. Primary method

`PRIMARY_METHOD_CHANGED = false`

Unchanged: the smooth map `theta = g(m)`, the full influence, one deterministic calendar-block centering, no second centering of `η c`, Gaussian Bartlett multipliers, `L_T = B_T`, the bandwidth `max(H_mechanical, ceil(T^{1/3}))`, `R = 9999`, the finite-`R` p-value, the normal-HAC sensitivity role, the global null `theta ≤ 0`, the evidence label `CONFIRMED_UNDER_MAINTAINED_ASSUMPTIONS`, and `NO_AUTOMATIC_METHOD_SWITCHING = true`.

## N. Final status

`PROFILE_CONTRACT_NOT_READY:ENVELOPE_G_UNSPECIFIED`

## O. Scientific status

`D7_HYPOTHESIS_FAILED = false`

`D7_BITMEX_PRIMARY_TARGET_OPENED = false`

`D7_PRIMARY_EFFECT_COMPUTED = false`

`PROFILE_VALIDATED = false`

`TARGET_OPENING = FORBIDDEN`
