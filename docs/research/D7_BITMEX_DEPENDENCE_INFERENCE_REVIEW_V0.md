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

For every predeclared null regime, the Wilson 95% upper bound of the one-sided rejection rate must be <= 0.06. TYPE_I_CEILING = 1.2 * alpha, with alpha = 0.05. The point estimate and the Wilson lower bound are not the rule.

NEW_CONFIRMATION_DESIGN_CHOICE: joint confirmation power (statistical AND practical AND temporal) at the full frozen delta has point estimate >= 0.80 under NULL_1_MARKOV_MODERATE, and point estimate >= 0.50 under each of NULL_2_MARKOV_STRONG, NULL_3_LATENT_30D, and NULL_4_YEAR_HETERO. IID power is reported and is not the acceptance bar. 75% and 50% effects are reported and are not substituted for the full-effect bar.

## Gates

STATISTICAL_GATE = One-sided level 0.05 test of H0: delta <= 0 on the exact frozen pool-adjusted contrast, using EXACT_DELTA_NW_BARTLETT_LAG_721 only. Bartlett kernel, fixed lag 721 valid hours, normal critical value 1.6448536269514722. Reject only when the long-run variance is positive and delta_hat / se exceeds that critical value. Lag 720, the block bootstrap, and circular shift are not selectable at confirmation.

PRACTICAL_GATE = delta_hat >= 0.05

TEMPORAL_GATE = PASS if year-level delta_hat > 0 in at least 2 of the 3 full calendar years 2017, 2018, and 2019. 2016 is diagnostic only and does not enter the numerator or the denominator. A full year with no candidates would not count as positive.

INTEGRITY_GATE = Canonical D7_BITMEX_ACTIVITY_V0 gzip hash, frozen selector digest, and unchanged D2 gzip all match the support-unit pin; no Binance 2025/2026 input is read; the estimator uses only the predeclared weights, Bartlett kernel, and lag 721.

The Binance temporal gate remains `D7_TEMPORAL_YEARS_REQUIRED = 3`
positive year-level contrasts on `(2020, 2021, 2022, 2023, 2024)`.
That discovery rule is unchanged. The BitMEX confirmation amendment
uses a different surface: PASS if the sign is positive in at least
2 of the 3 full years 2017, 2018, and 2019. The gate exists to stop
one historical period from carrying the result. It does not require
the effect in every year. With three full years, 2 of 3 is a
symmetric majority. 2016 is a partial post-listing year. Its
year-level sign is recorded as a diagnostic and is excluded from
both the numerator and the denominator.

The block bootstrap does not enter the confirmation conjunction.
If the primary call and the bootstrap call disagree,
`INFERENCE_SENSITIVE` is true. Agreement adds no flag. The flag
does not turn a primary PASS into a FAIL or a primary FAIL into a
PASS, and it is not combined with the primary call by AND or OR.

## RV x qrel support

Each fine cell is one RV quartile crossed with one trailing qrel
quartile. A cell is supported when both arms have at least 50
hours. That floor is the frozen `MIN_D7_STATE_PER_YEAR`. If any fine
cell fails, qrel is coarsened once, by merging bins (0, 1) and bins
(2, 3). RV bins stay at four. No other merge is allowed. If the
coarse grid still fails, the decomposition is `NOT_SUPPORTED` and
no effect is reported for it.

STATUS = NOT_SUPPORTED

Fine cells:

- RV 0 qrel 0: n=3659 candidates=115 controls=3544 candidate_share=0.03142935228204428 control_share=0.9685706477179558 arm_support_ok=true
- RV 0 qrel 1: n=2044 candidates=0 controls=2044 candidate_share=0.0 control_share=1.0 arm_support_ok=false
- RV 0 qrel 2: n=1373 candidates=0 controls=1373 candidate_share=0.0 control_share=1.0 arm_support_ok=false
- RV 0 qrel 3: n=705 candidates=0 controls=705 candidate_share=0.0 control_share=1.0 arm_support_ok=false
- RV 1 qrel 0: n=2840 candidates=452 controls=2388 candidate_share=0.1591549295774648 control_share=0.8408450704225352 arm_support_ok=true
- RV 1 qrel 1: n=2197 candidates=0 controls=2197 candidate_share=0.0 control_share=1.0 arm_support_ok=false
- RV 1 qrel 2: n=1623 candidates=0 controls=1623 candidate_share=0.0 control_share=1.0 arm_support_ok=false
- RV 1 qrel 3: n=976 candidates=0 controls=976 candidate_share=0.0 control_share=1.0 arm_support_ok=false
- RV 2 qrel 0: n=1488 candidates=903 controls=585 candidate_share=0.6068548387096774 control_share=0.39314516129032256 arm_support_ok=true
- RV 2 qrel 1: n=2013 candidates=111 controls=1902 candidate_share=0.05514157973174367 control_share=0.9448584202682563 arm_support_ok=true
- RV 2 qrel 2: n=2172 candidates=0 controls=2172 candidate_share=0.0 control_share=1.0 arm_support_ok=false
- RV 2 qrel 3: n=1585 candidates=0 controls=1585 candidate_share=0.0 control_share=1.0 arm_support_ok=false
- RV 3 qrel 0: n=275 candidates=275 controls=0 candidate_share=1.0 control_share=0.0 arm_support_ok=false
- RV 3 qrel 1: n=920 candidates=644 controls=276 candidate_share=0.7 control_share=0.3 arm_support_ok=true
- RV 3 qrel 2: n=1942 candidates=524 controls=1418 candidate_share=0.2698249227600412 control_share=0.7301750772399588 arm_support_ok=true
- RV 3 qrel 3: n=4507 candidates=414 controls=4093 candidate_share=0.09185711116041713 control_share=0.9081428888395828 arm_support_ok=true

Coarse cells:

- RV 0 qrel 0+1: n=5703 candidates=115 controls=5588 candidate_share=0.020164825530422585 control_share=0.9798351744695775 arm_support_ok=true
- RV 0 qrel 2+3: n=2078 candidates=0 controls=2078 candidate_share=0.0 control_share=1.0 arm_support_ok=false
- RV 1 qrel 0+1: n=5037 candidates=452 controls=4585 candidate_share=0.0897359539408378 control_share=0.9102640460591622 arm_support_ok=true
- RV 1 qrel 2+3: n=2599 candidates=0 controls=2599 candidate_share=0.0 control_share=1.0 arm_support_ok=false
- RV 2 qrel 0+1: n=3501 candidates=1014 controls=2487 candidate_share=0.28963153384747214 control_share=0.7103684661525278 arm_support_ok=true
- RV 2 qrel 2+3: n=3757 candidates=0 controls=3757 candidate_share=0.0 control_share=1.0 arm_support_ok=false
- RV 3 qrel 0+1: n=1195 candidates=919 controls=276 candidate_share=0.7690376569037657 control_share=0.2309623430962343 arm_support_ok=true
- RV 3 qrel 2+3: n=6449 candidates=938 controls=5511 candidate_share=0.14544890680725694 control_share=0.854551093192743 arm_support_ok=true

## Calibration

One-sided rejection rate at alpha 0.05. A regime is accepted when
the Wilson 95% upper bound is at most 0.06. The point estimate and
the lower bound are not the rule. Lag 720 is reported and is not
selectable. The block bootstrap is a sensitivity calibration, not
a second gate.

### Type I

`EXACT_DELTA_NW_BARTLETT_LAG_721`

- NULL_0_IID: 241/5000 = 0.0482, Wilson [0.042602103737660074, 0.054491591739893555], accepted=true
- NULL_1_MARKOV_MODERATE: 216/5000 = 0.0432, Wilson [0.037906663853665874, 0.049194708643338324], accepted=true
- NULL_2_MARKOV_STRONG: 241/5000 = 0.0482, Wilson [0.042602103737660074, 0.054491591739893555], accepted=true
- NULL_3_LATENT_30D: 286/5000 = 0.0572, Wilson [0.0510966231678006, 0.063983253674742], accepted=false
- NULL_4_YEAR_HETERO: 217/5000 = 0.0434, Wilson [0.038094109375360806, 0.049406956040865375], accepted=true

`EXACT_DELTA_NW_BARTLETT_LAG_720`

- NULL_0_IID: 241/5000 = 0.0482, Wilson [0.042602103737660074, 0.054491591739893555], accepted=true
- NULL_1_MARKOV_MODERATE: 216/5000 = 0.0432, Wilson [0.037906663853665874, 0.049194708643338324], accepted=true
- NULL_2_MARKOV_STRONG: 241/5000 = 0.0482, Wilson [0.042602103737660074, 0.054491591739893555], accepted=true
- NULL_3_LATENT_30D: 286/5000 = 0.0572, Wilson [0.0510966231678006, 0.063983253674742], accepted=false
- NULL_4_YEAR_HETERO: 217/5000 = 0.0434, Wilson [0.038094109375360806, 0.049406956040865375], accepted=true

`EXACT_DELTA_NONOVERLAPPING_BLOCK_BOOTSTRAP`

- NULL_0_IID: 251/5000 = 0.0502, Wilson [0.04448534215006972, 0.05660528251970369], accepted=true
- NULL_1_MARKOV_MODERATE: 239/5000 = 0.0478, Wilson [0.042225787297577644, 0.05406852234153203], accepted=true
- NULL_2_MARKOV_STRONG: 282/5000 = 0.0564, Wilson [0.05033958885978194, 0.06314151630587275], accepted=false
- NULL_3_LATENT_30D: 269/5000 = 0.0538, Wilson [0.04788174698389211, 0.06040335023187689], accepted=false
- NULL_4_YEAR_HETERO: 259/5000 = 0.0518, Wilson [0.04599384613067904, 0.05829432189287018], accepted=true

`CIRCULAR_SHIFT`: NOT_EQUIVALENT. A circular-shift reference distribution tests whether the next-hour alignment is unusual among alignments.

### Joint power

Joint means the statistical gate, the practical gate, and the
temporal gate all pass. At half the frozen delta the within-stratum
gap maps to a contrast near 0.045, below 0.05, so the practical gate
binds and the joint rate equals the practical rate. That 50% rate is
reported. It is not the acceptance bar.

`EXACT_DELTA_NW_BARTLETT_LAG_721` (primary)

- NULL_0_IID: full joint 1.0; 75pct joint 0.9996; 50pct joint 0.2042
- NULL_1_MARKOV_MODERATE: full joint 1.0; 75pct joint 0.9982; 50pct joint 0.2062
- NULL_2_MARKOV_STRONG: full joint 1.0; 75pct joint 0.981; 50pct joint 0.2822
- NULL_3_LATENT_30D: full joint 1.0; 75pct joint 0.9866; 50pct joint 0.2862
- NULL_4_YEAR_HETERO: full joint 1.0; 75pct joint 0.9988; 50pct joint 0.2104

`EXACT_DELTA_NW_BARTLETT_LAG_720` (sensitivity, not selectable)

- NULL_0_IID: full joint 1.0; 75pct joint 0.9996; 50pct joint 0.2042
- NULL_1_MARKOV_MODERATE: full joint 1.0; 75pct joint 0.9982; 50pct joint 0.2062
- NULL_2_MARKOV_STRONG: full joint 1.0; 75pct joint 0.981; 50pct joint 0.2822
- NULL_3_LATENT_30D: full joint 1.0; 75pct joint 0.9866; 50pct joint 0.2862
- NULL_4_YEAR_HETERO: full joint 1.0; 75pct joint 0.9988; 50pct joint 0.2104

`EXACT_DELTA_NONOVERLAPPING_BLOCK_BOOTSTRAP` (sensitivity only, not a gate)

Null calibration is under type I. Bootstrap power is not a gate and was not recomputed.

## Results

```
OLD_EXCHANGEABLE_NULL_STATUS = INVALID_UNDER_SERIAL_DEPENDENCE
PRIMARY_INFERENCE_METHOD = EXACT_DELTA_NW_BARTLETT_LAG_721
DECISION = NO_VALID_EQUIVALENT_INFERENCE_DESIGN
NEXT_UNIT = NONE
POWER_FULL_EFFECT = None
POWER_75PCT_EFFECT = None
POWER_50PCT_EFFECT = None
D7_BITMEX_PRIMARY_TARGET_OPENED = false
D7_BITMEX_EFFECT_COMPUTED = false
D7_PRIMARY_EFFECT_COMPUTED = false
D7_AMENDMENT_OUTCOME_BLIND = true
D7_BITMEX_REPLICATION_CLASS_ASSIGNED = false
BINANCE_2025_OPENED = false
BINANCE_2026_OPENED = false
PRIMARY_INFERENCE_RESULT = NOT_EVALUATED_TARGET_UNOPENED
BLOCK_BOOTSTRAP_SENSITIVITY_RESULT = NOT_EVALUATED_TARGET_UNOPENED
INFERENCE_SENSITIVE = None
RV_QREL_DECOMPOSITION = NOT_SUPPORTED
```

Primary NW721 did not keep every null regime's Wilson 95% upper bound at or below 0.06. The block bootstrap is not a fallback gate. No confirmation preregistration is authorized.

Block-bootstrap null calibration is FAIL. A FAIL means the bootstrap is not an interpretable sensitivity check. It does not change the primary call.

This unit does not classify scientific truth.
