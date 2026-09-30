# D7 BitMEX dependence inference review V0

**Unit:** `D7_BITMEX_DEPENDENCE_INFERENCE_REVIEW_V0`

Outcome-blind statistical design. Real BitMEX t+1 targets are not
constructed. No replication class is assigned. No confirmation
preregistration and no execution permit.

## Estimand

The market claim is unchanged. For target-eligible hours, let
`Y_t` be the next completed hour's D7 state and let `X_t` be
`D7_STATE_t`. Strata are calendar year × RV bucket. With `K_s`
candidates and `N_s` eligible hours in stratum `s`, and `K = sum K_s`,

`delta = sum_s (K_s / K) (mean(Y | X=1, s) - mean(Y | eligible, s))`.

That is the expectation of the frozen rate-matched contrast, because
a rate-matched draw in stratum `s` has mean equal to the eligible-pool
mean. It equals `sum_s (K_s / K) (1 - K_s/N_s) (mean_1 - mean_0)`.
The ordinary stratum-fixed-effect slope is `delta / c` with
`c = 0.8037903043858667`, so the slope is not the frozen
delta. The practical gate stays on `delta`, which keeps the 0.05
threshold on the same magnitude as discovery.

Inference is separate from this estimand. Replacing the exchangeable
Monte Carlo changes the reference distribution, not the claim.

## Why the exchangeable null is invalid

The frozen null draws `K_s` eligible hours without replacement inside
each stratum and treats those hours as exchangeable. The contrast is
the linear statistic `delta = sum_t w_t Y_t`, with weights that sum
to zero inside each stratum: positive on candidates and negative on
other eligible hours. Exchangeability supplies every covariance term
`Cov(Y_t, Y_{t+h})` for `h ≠ 0` as if the candidate set were a random
subset. It is not. The 720-hour QREL median, the 720-hour impact P90,
and the 720-hour RV quantiles make nearby hours share threshold
inputs. The target is the next hour, so the score at `t` uses states
at `t` and `t+1`. Those scores still share a construction input at
valid-hour separation 721, and the overlap is gone at separation 722.
Positive serial correlation then inflates `Var(sum w_t Y_t)` relative
to the exchangeable formula, and the old 95th percentile is too small.
This is a structural statement. No BitMEX state adjacency was measured.

## Designs reviewed

A. Exact-delta Newey-West, Bartlett kernel, fixed lag 721 valid hours.
Estimand is `delta`. Year × RV bucket adjustment is the weight
construction. Lag 721 is the construction cutoff, not a residual lag.
Lag 720 leaves the last overlapping score lag uncovered and is not
selectable. Normal critical value `1.6448536269514722`. Finite-sample
risk: `L/T` is about 0.02, so fixed-b distortion is possible; the
null battery is the check. No automatic lag picker.

B. Non-overlapping block bootstrap of residuals, block length 1440
valid hours, resampled with replacement inside year segments and
inside the December 2016 gap split. Stratum means are added back, so
the bootstrap imposes `delta = 0` while keeping within-block serial
structure and the RV-bucket adjustment. A segment that is a single
block uses a circular residual shift inside that segment only, so
the short post-gap piece is still randomized. This is not a test
against other lags of the original contrast.

C. Circular shift of the target across lags. Rejecting when the
next-hour alignment is extreme among alignments changes the null
into 'lag 1 is unusual relative to other lags'. Status:
`NOT_EQUIVALENT`. It is not a primary method and it is not selectable
at execution.

## Calibration rules

For every predeclared null regime, the Wilson 95% lower bound of the one-sided rejection rate must be <= 0.05.

NEW_CONFIRMATION_DESIGN_CHOICE: joint confirmation power (statistical AND practical AND temporal) at the full frozen delta has point estimate >= 0.80 under NULL_1_MARKOV_MODERATE, and point estimate >= 0.50 under each of NULL_2_MARKOV_STRONG, NULL_3_LATENT_30D, and NULL_4_YEAR_HETERO. IID power is reported and is not the acceptance bar. 75% and 50% effects are reported and are not substituted for the full-effect bar.

## Gates

STATISTICAL_GATE = One-sided level 0.05 test of H0: delta <= 0 on the exact frozen pool-adjusted contrast, using the predeclared primary method (Newey-West Bartlett lag 721 if it passes type I; otherwise the non-overlapping block bootstrap if that passes type I).

PRACTICAL_GATE = delta_hat >= 0.05

TEMPORAL_GATE = At least 3 of calendar years 2016, 2017, 2018, 2019 have year-level delta_hat > 0. 2016 is included. A year with no candidates would not count as positive.

INTEGRITY_GATE = Canonical D7_BITMEX_ACTIVITY_V0 gzip hash, frozen selector digest, and unchanged D2 gzip all match the support-unit pin; no Binance 2025/2026 input is read; the estimator uses only the predeclared weights, lag or blocks, kernel, and gates.

The Binance temporal gate is `D7_TEMPORAL_YEARS_REQUIRED = 3` positive
year-level contrasts on the legal year list `(2020, 2021, 2022, 2023, 2024)`,
with a year omitted from the positive count when it has no candidates,
and with the sign test `delta_year > 0` rather than a second p-value.
The confirmation translation keeps the required count of 3 and counts
the four legal BitMEX years. 2016 stays in the count: it clears the
frozen per-year support floor, and Binance also counted its first
legal year even though the trailing window consumes the opening hours.
Requiring 3 of the 3 full years would tighten the gate. That was not done.

## Calibration

One-sided rejection rate at alpha 0.05. A regime is accepted when
the Wilson 95% lower bound is at most 0.05. The point estimate is
not the rule. Lag 720 and the block bootstrap are reported. Neither
is selectable after these counts.

### Type I

`EXACT_DELTA_NW_BARTLETT_LAG_721`

- NULL_0_IID: 242/5000 = 0.0484, Wilson [0.04279030408863613, 0.05470308430813947], accepted=true
- NULL_1_MARKOV_MODERATE: 220/5000 = 0.044, Wilson [0.038656640337733486, 0.05004350383615862], accepted=true
- NULL_2_MARKOV_STRONG: 206/5000 = 0.0412, Wilson [0.03603404693250978, 0.047070396372274656], accepted=true
- NULL_3_LATENT_30D: 241/5000 = 0.0482, Wilson [0.042602103737660074, 0.054491591739893555], accepted=true
- NULL_4_YEAR_HETERO: 258/5000 = 0.0516, Wilson [0.045805193052696626, 0.05808328205163061], accepted=true

`EXACT_DELTA_NW_BARTLETT_LAG_720`

- NULL_0_IID: 242/5000 = 0.0484, Wilson [0.04279030408863613, 0.05470308430813947], accepted=true
- NULL_1_MARKOV_MODERATE: 220/5000 = 0.044, Wilson [0.038656640337733486, 0.05004350383615862], accepted=true
- NULL_2_MARKOV_STRONG: 206/5000 = 0.0412, Wilson [0.03603404693250978, 0.047070396372274656], accepted=true
- NULL_3_LATENT_30D: 242/5000 = 0.0484, Wilson [0.04279030408863613, 0.05470308430813947], accepted=true
- NULL_4_YEAR_HETERO: 258/5000 = 0.0516, Wilson [0.045805193052696626, 0.05808328205163061], accepted=true

`EXACT_DELTA_NONOVERLAPPING_BLOCK_BOOTSTRAP`

- NULL_0_IID: 102/2000 = 0.051, Wilson [0.04218996991731548, 0.06153153854124964], accepted=true
- NULL_1_MARKOV_MODERATE: 99/2000 = 0.0495, Wilson [0.040827254610808245, 0.059900004989600644], accepted=true
- NULL_2_MARKOV_STRONG: 97/2000 = 0.0485, Wilson [0.03992009344287708, 0.05881100025209431], accepted=true
- NULL_3_LATENT_30D: 110/2000 = 0.055, Wilson [0.04583478836864504, 0.06587138371167006], accepted=true
- NULL_4_YEAR_HETERO: 97/2000 = 0.0485, Wilson [0.03992009344287708, 0.05881100025209431], accepted=true

`CIRCULAR_SHIFT`: NOT_EQUIVALENT. A circular-shift reference distribution tests whether the next-hour alignment is unusual among alignments.

### Joint power

Joint means the statistical gate, the practical gate, and the
temporal gate all pass. At half the frozen delta the within-stratum
gap maps to a contrast near 0.045, below 0.05, so the practical gate
binds and the joint rate equals the practical rate. That 50% rate is
reported. It is not the acceptance bar.

`EXACT_DELTA_NW_BARTLETT_LAG_721` (primary)

- NULL_0_IID: full joint 1.0; 75pct joint 0.9996; 50pct joint 0.202
- NULL_1_MARKOV_MODERATE: full joint 1.0; 75pct joint 0.9994; 50pct joint 0.2138
- NULL_2_MARKOV_STRONG: full joint 1.0; 75pct joint 0.9804; 50pct joint 0.277
- NULL_3_LATENT_30D: full joint 1.0; 75pct joint 0.9868; 50pct joint 0.2836
- NULL_4_YEAR_HETERO: full joint 1.0; 75pct joint 0.9986; 50pct joint 0.2174

`EXACT_DELTA_NW_BARTLETT_LAG_720` (sensitivity, not selectable)

- NULL_0_IID: full joint 1.0; 75pct joint 0.9996; 50pct joint 0.202
- NULL_1_MARKOV_MODERATE: full joint 1.0; 75pct joint 0.9994; 50pct joint 0.2138
- NULL_2_MARKOV_STRONG: full joint 1.0; 75pct joint 0.9804; 50pct joint 0.277
- NULL_3_LATENT_30D: full joint 1.0; 75pct joint 0.9868; 50pct joint 0.2836
- NULL_4_YEAR_HETERO: full joint 1.0; 75pct joint 0.9986; 50pct joint 0.2174

`EXACT_DELTA_NONOVERLAPPING_BLOCK_BOOTSTRAP` (calibrated, not selected)

- NULL_0_IID: full joint 1.0; 75pct joint 0.998; 50pct joint 0.19
- NULL_1_MARKOV_MODERATE: full joint 1.0; 75pct joint 0.9985; 50pct joint 0.206
- NULL_2_MARKOV_STRONG: full joint 1.0; 75pct joint 0.984; 50pct joint 0.2925
- NULL_3_LATENT_30D: full joint 1.0; 75pct joint 0.9845; 50pct joint 0.2935
- NULL_4_YEAR_HETERO: full joint 1.0; 75pct joint 0.9985; 50pct joint 0.2155

## Results

```
OLD_EXCHANGEABLE_NULL_STATUS = INVALID_UNDER_SERIAL_DEPENDENCE
PRIMARY_INFERENCE_METHOD = EXACT_DELTA_NW_BARTLETT_LAG_721
DECISION = DEPENDENCE_VALID_DESIGN_READY_FOR_PREREG
NEXT_UNIT = D7_BITMEX_CONFIRMATION_PREREG_FREEZE
POWER_FULL_EFFECT = 1.0
POWER_75PCT_EFFECT = 0.9994
POWER_50PCT_EFFECT = 0.2138
D7_BITMEX_PRIMARY_TARGET_OPENED = false
D7_BITMEX_EFFECT_COMPUTED = false
D7_BITMEX_REPLICATION_CLASS_ASSIGNED = false
BINANCE_2025_OPENED = false
BINANCE_2026_OPENED = false
```

Primary method `EXACT_DELTA_NW_BARTLETT_LAG_721` passed the type-I rule on every null regime and the predeclared dependence-aware power rule. The next unit may freeze the preregistration. It may not open the target inside that freeze.

This unit does not classify scientific truth.
