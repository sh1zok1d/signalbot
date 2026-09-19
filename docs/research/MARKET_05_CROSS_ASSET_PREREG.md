# MARKET-05 exact outcome-blind preregistration

- **Status:** `PREREGISTERED_OUTCOME_BLIND`
- **Unit ID:** `MARKET_05_CROSS_ASSET_PREREG`
- **Research ID:** `MARKET-05_CROSS_ASSET_CONFIRMATION_ADVERSE_PATH_RISK`
- **Short name:** `MARKET-05`
- **Date:** 2026-09-19
- **Machine-readable twin:** [`MARKET_05_CROSS_ASSET_PREREG.json`](MARKET_05_CROSS_ASSET_PREREG.json)
- **Bound candidate:** [`MARKET_05_CROSS_ASSET_CANDIDATE.md`](MARKET_05_CROSS_ASSET_CANDIDATE.md)
- **Bound feasibility:** [`MARKET_05_CROSS_ASSET_DATA_FEASIBILITY.md`](MARKET_05_CROSS_ASSET_DATA_FEASIBILITY.md)

This unit freezes **one exact** scientific formulation. It does not
execute the experiment, implement an evaluator, ARM, create RESULT, or
inspect scientific outcomes.

```text
FULL_PREREGISTRATION_FROZEN = true
IMPLEMENTATION_FROZEN = false
ARMED = false
EXECUTION_AUTHORIZED = false
SCIENTIFIC_OUTCOMES_INSPECTED = false
PROTECTED_OOS_TOUCHED = false
SIGNALBOT_PROTECTED_OOS_UNTOUCHED = YES
MARKET_05_TEST_CALIBRATED = NO
```

Bound authority:

```text
PRE_PREREG_HEAD = c44fb1503f9c5472b1452d56ea1fd5c372338176
PRE_PREREG_TREE = 0f3a96e1b6ee0265c2a80da62488f2da5e1174ee
```

This unit does **not**: calculate MARKET-05 scientific outcomes; calculate future BTC returns for hypothesis evaluation; calculate future MAE; fit the scientific model; calculate the ETH coefficient; compare baseline/candidate performance; inspect yearly effects; inspect confirmation buckets; search lookbacks; search horizons; search transformations; search thresholds; touch protected 2025/2026 OOS; ARM; create RESULT; or authorize execution.

---

## 1. Exact scientific claim

PRIMARY_CLAIM = Conditional on BTC's own recent directional displacement and volatility state, stronger contemporaneous ETH confirmation of BTC's direction predicts LOWER subsequent BTC adverse excursion against that direction.

This is an incremental cross-asset context claim.

It is **not**:

- ETH predicts BTC direction;
- ETH leads BTC;
- BTC/ETH correlation is profitable;
- cross-asset confirmation causes continuation;
- a pair trade;
- a PnL claim.

```text
TARGET = BTCUSDT
CONTEXT = ETHUSDT
one_btc_experiment = true
eth_is_independent_replication = false
simple_direction_predictor = false
```

---

## 2. Data authorities

```text
BTC_DATASET = CORE_BTC_BINANCE_V0
ETH_DATASET = CORE_ETH_BINANCE_V0
COMMON_COVERAGE = [2020-01-01T00:00:00Z, 2026-08-26T00:00:00Z)
BAR_AVAILABILITY = bar_end_exclusive
available_at = open_time + 60s
eligible iff bar_end_exclusive <= T
```

BTC authority remains accepted snapshot
`717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`.
ETH remains `SOURCE_INVENTORY_BOUND_NOT_MATERIALIZED_NOT_ACCEPTED`.
Later implementation must rematerialize/accept `CORE_ETH_BINANCE_V0`
under the same bar-end-exclusive contract before ARM/execution. This
preregistration does not accept the ETH snapshot.

No BTC perpetual + ETH spot mix. No cross-exchange mix.
`CORE_BTC_BINANCE_V0` is not redefined.

---

## 3. Development window and usable decisions

```text
SCIENTIFIC_DEVELOPMENT_WINDOW = [2020-01-01T00:00:00Z, 2025-01-01T00:00:00Z)
PROTECTED_OOS = [2025-01-01T00:00:00Z, onward)
DECISION_TIME = 00:00:00 UTC
DECISION_FREQUENCY = DAILY
FEATURE_LOOKBACK = 24 hours
OUTCOME_HORIZON = 24 hours
```

Protected `[2025-01-01T00:00:00Z, onward)` must remain untouched. All
lookback information and all future outcome bars for a development row
must remain strictly inside the development window.

Price convention:

```text
P_A_U = close of the final asset-A 1m bar whose bar_end_exclusive = U
```

The first CORE open is `2020-01-01T00:00:00Z`, so the first legal `P(U)`
requires `U - 1m >= 2020-01-01T00:00:00Z`. Features need both `P_T` and
`P_{T-24h}`. Therefore `T - 24h >= 2020-01-01T00:01:00Z`, so
`T >= 2020-01-02T00:01:00Z`. The frozen daily 00:00 UTC grid makes the
first usable decision:

```text
FIRST_USABLE_DECISION_TIME = 2020-01-03T00:00:00Z
```

Outcome window `[T, T+24h)` must satisfy `T+24h <= 2025-01-01T00:00:00Z`:

```text
LAST_USABLE_DECISION_TIME = 2024-12-31T00:00:00Z
```

No protected outcome may be opened. 2020/2021 are never promoted as
held-out evidence.

Decision-grid reason:

- reduces highly correlated repeated observations;
- provides a clean fixed observational unit;
- removes freedom to select favorable hours;
- remains compatible with bar_end_exclusive semantics.

No alternative UTC hour may be inspected after execution under this
identity. No 6h / 12h / 48h lookback comparison. No intraday decision
grid.

---

## 4. Feature construction

All feature calculations use only fully closed 1-minute bars in
`[T - 24h, T)` available by `T`. No bar beginning at `T` may enter the
features.

```text
R_BTC_24H = ln(P_BTC_T / P_BTC_T_MINUS_24H)
R_ETH_24H = ln(P_ETH_T / P_ETH_T_MINUS_24H)
BTC_SIDE = sign(R_BTC_24H)
BTC_DISPLACEMENT_MAG = abs(R_BTC_24H)
```

Rows with exactly `R_BTC_24H == 0` are excluded mechanically because
direction-aligned outcome orientation is undefined. Exact-zero BTC displacement exclusion only. No epsilon / minimum-move threshold is
permitted.

For each asset `A` in `{BTC, ETH}`:

```text
RV_A_24H = sqrt(sum(r_A_1m^2))
```

over all valid 1-minute log returns in `[T - 24h, T)`. No annualization.
No alternative volatility estimator.

A 1-minute log return uses the close of that minute and the close of
the immediately previous closed minute. The previous close for the first
lookback minute is the prefix bar with `bar_end_exclusive = T-24h`.

Required completeness for a usable row:

- 1440 BTC and 1440 ETH 1m bars with `open_time` in `[T-24h, T)`;
- prefix BTC and ETH bars with `bar_end_exclusive = T-24h`;
- 1440 BTC 1m OHLC bars with `open_time` in `[T, T+24h)`.

If any required bar is missing, the decision row is unavailable for
**BOTH** baseline and candidate. same_support_required = true. No silent
candidate-only drop.

```text
Z_BTC = R_BTC_24H / RV_BTC_24H
Z_ETH = R_ETH_24H / RV_ETH_24H
```

provided `RV > 0` and finite. Rows with zero/non-finite RV are excluded
mechanically from BOTH models. No clipping. No winsorization. No
percentile transform. No rolling z-score. No rank transform.

```text
ETH_CONFIRMATION = BTC_SIDE * Z_ETH
context_feature_family = ETH_CONFIRMATION_STATE
continuous_feature_required = true
threshold_search_allowed = false
```

ETH_CONFIRMATION > 0: ETH displacement has the same direction as BTC.
ETH_CONFIRMATION < 0: ETH displacement contradicts BTC direction.
Magnitude is ETH displacement normalized by ETH's own recent realized
volatility.

This feature remains CONTINUOUS. No threshold or bucket defines the primary test.

Identifiability: `ETH_CONFIRMATION` uses ETH displacement and ETH RV.
It is not a restatement of `Z_BTC` or `BTC_DISPLACEMENT_MAG`. The
candidate must not receive credit merely because ETH confirmation is
another representation of BTC displacement. A fold whose candidate
design matrix is rank-deficient, or whose `ETH_CONFIRMATION` column is
exactly collinear with the baseline columns, is
`MARKET_05_INCOMPLETE_EXECUTION`, not a scientific `NO_EVIDENCE`.

---

## 5. Primary outcome

```text
PRIMARY_OUTCOME = BTC_DIRECTION_ALIGNED_MAE_24H
OUTCOME_HORIZON = 24 hours
future outcome uses [T, T+24h)
```

Use BTC 1-minute OHLC bars. No final-return substitution. No MFE/PnL
substitution.

For `BTC_SIDE = +1`:

```text
ADVERSE_PRICE = minimum BTC low in [T, T+24h)
Y_T = max(0, ln(P_BTC_T / ADVERSE_PRICE))
```

For `BTC_SIDE = -1`:

```text
ADVERSE_PRICE = maximum BTC high in [T, T+24h)
Y_T = max(0, ln(ADVERSE_PRICE / P_BTC_T))
```

Thus `Y_T >= 0`. Higher `Y_T` = worse adverse excursion against the
pre-T BTC direction.

---

## 6. Exact baseline and candidate

```text
BASELINE_MODEL = Y ~ BTC_SIDE + ABS_Z_BTC + RV_BTC_24H
CANDIDATE_MODEL = Y ~ BTC_SIDE + ABS_Z_BTC + RV_BTC_24H + ETH_CONFIRMATION
ABS_Z_BTC = abs(Z_BTC)
```

Baseline design matrix: INTERCEPT, BTC_SIDE, ABS_Z_BTC, RV_BTC_24H.
No technical indicators. No trend filter. No range indicator. No
funding. No OI. No taker imbalance. No ETH field.

Candidate = exact BASELINE + ETH_CONFIRMATION.
No interaction terms. No polynomial terms. No ETH volatility as a
separate candidate regressor. No ETH return as a separate candidate
regressor. No feature selection.

MARKET-05 asks exactly one incremental question: does ETH_CONFIRMATION
add information beyond the BTC-only baseline?

---

## 7. Standardization and model

For model fitting, continuous predictor standardization parameters must
be learned ONLY from the training partition of each fold.

```text
x_std = (x - training_mean) / training_sd
```

Apply training mean/sd unchanged to the corresponding test partition.
BTC_SIDE is not standardized. INTERCEPT is not standardized.
Continuous features: ABS_Z_BTC, RV_BTC_24H, and ETH_CONFIRMATION
(candidate only). Zero training sd => fail closed for that fold. No
full-period normalization before chronological evaluation.

```text
MODEL_CLASS = ORDINARY_LEAST_SQUARES_LINEAR_REGRESSION
```

No ML. No regularization. No hyperparameter tuning. Prediction values
are NOT clipped. Both models use exact same rows.

---

## 8. Chronological folds

No random train/test split. Exact UTC boundaries:

```text
FOLD_1_TRAIN = [2020-01-03T00:00:00Z, 2022-01-01T00:00:00Z)
FOLD_1_TEST  = [2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z)
FOLD_2_TRAIN = [2020-01-03T00:00:00Z, 2023-01-01T00:00:00Z)
FOLD_2_TEST  = [2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z)
FOLD_3_TRAIN = [2020-01-03T00:00:00Z, 2024-01-01T00:00:00Z)
FOLD_3_TEST  = [2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z)
```

Human calendar form:

- FOLD_1 train = 2020-01-01 through 2021-12-31 eligible rows; test = calendar year 2022 eligible rows
- FOLD_2 train = 2020-01-01 through 2022-12-31 eligible rows; test = calendar year 2023 eligible rows
- FOLD_3 train = 2020-01-01 through 2023-12-31 eligible rows; test = calendar year 2024 eligible rows

2020/2021 are never promoted as held-out evidence. 2025/2026 remain
untouched.

---

## 9. Primary predictive metric and materiality

For each test fold calculate MAE_BASELINE and MAE_CANDIDATE, where MAE
refers to mean absolute prediction error for `Y_T`.

Pooled held-out loss from concatenated predictions across 2022-2024:

```text
RELATIVE_MAE_IMPROVEMENT = 1 - (POOLED_MAE_CANDIDATE / POOLED_MAE_BASELINE)
MATERIAL_RELATIVE_MAE_IMPROVEMENT = 0.02
```

Positive = candidate predicts adverse risk better. Primary materiality
requires `RELATIVE_MAE_IMPROVEMENT >= 0.02`. Do NOT lower 2% after
execution. 2% is a preregistered practical-information threshold, not a
claim of trading profitability.

---

## 10. Directional mechanism coefficient

Fit the frozen candidate specification on all eligible DEVELOPMENT rows
only: 2020-2024 (`T` in `[2020-01-03T00:00:00Z, 2025-01-01T00:00:00Z)`).
Standardize continuous features from that full-development sample only.

```text
EXPECTED_BETA_SIGN = negative
GATE_1_DIRECTION = full-development BETA_ETH_CONFIRMATION < 0
```

Expected sign is negative because stronger ETH confirmation is
hypothesized to correspond to LOWER future adverse excursion. This
coefficient is a mechanism-direction diagnostic and a required gate. It
is NOT by itself sufficient for promotion.

---

## 11. Dependence-aware uncertainty

```text
BLOCK_BOOTSTRAP_UNIT = UTC calendar day rows
BLOCK_LENGTH = 14 consecutive days
BOOTSTRAP_REPLICATES = 5000
RANDOM_SEED = 2026091905
BOOTSTRAP_KIND = CIRCULAR_MOVING_BLOCK
```

Deterministic circular moving-block bootstrap. Blocks wrap the end of
the resampled series to the start. The RNG is a deterministic
splitmix64-compatible generator seeded by `RANDOM_SEED`. Bootstrap
preserves chronological local dependence.

ONE method, two predeclared statistics:

1. `RELATIVE_MAE_IMPROVEMENT`: models are fit once under the frozen
   chronological folds; bootstrap resamples held-out daily
   loss-difference tuples `(date, abs_err_baseline, abs_err_candidate)`
   in 14-day circular blocks **without refitting**.
2. `BETA_ETH_CONFIRMATION`: circular 14-day block bootstrap of
   full-development daily rows; **refit** only the candidate OLS on each
   replicate; collect `BETA_ETH_CONFIRMATION`.

Do NOT choose method after results. Do not refit chronological
predictive folds inside the predictive bootstrap.

```text
GATE_2_DIRECTION_UNCERTAINTY = 95% block-bootstrap upper confidence bound for BETA_ETH_CONFIRMATION < 0
GATE_3_PREDICTIVE_SIGN = RELATIVE_MAE_IMPROVEMENT > 0
GATE_4_PREDICTIVE_UNCERTAINTY = 95% block-bootstrap lower confidence bound for RELATIVE_MAE_IMPROVEMENT > 0
GATE_5_MATERIALITY = RELATIVE_MAE_IMPROVEMENT >= 0.02
```

Confidence bounds are the 2.5th and 97.5th percentiles of the 5000
replicate statistics.

---

## 12. Temporal stability gate

For each held-out test year 2022, 2023, 2024 calculate
`YEAR_RELATIVE_MAE_IMPROVEMENT`.

```text
TEMPORAL_STABILITY_GATE = at least 2 of 3 test years YEAR_RELATIVE_MAE_IMPROVEMENT > 0 AND no held-out year YEAR_RELATIVE_MAE_IMPROVEMENT <= -0.02
```

This allows one mildly weak year but rejects a mechanism whose pooled
result is produced by offsetting a materially bad year. Do NOT change
this after execution.

---

## 13. No parameter robustness grid

MARKET-05 intentionally has ONE lookback, ONE decision time, ONE
horizon, ONE normalization, ONE feature, ONE model class. Therefore do
NOT create nearby 12h/48h robustness cells after outcome. Temporal
held-out stability replaces a parameter-neighborhood search. Any
different parameterization is a future new identity.

---

## 14. Primary classification

```text
PROMOTION_CLASSIFICATION = MARKET_05_PROMOTED_HISTORICAL_CANDIDATE
FAIL_CLASSIFICATION = MARKET_05_NO_EVIDENCE
INTEGRITY_FAIL_CLASSIFICATION = MARKET_05_INCOMPLETE_EXECUTION
```

`MARKET_05_PROMOTED_HISTORICAL_CANDIDATE` if and only if ALL gates pass:
direction; direction uncertainty; predictive improvement; predictive
uncertainty; 2% materiality; temporal stability; and all
integrity/data/support contracts.

Otherwise `MARKET_05_NO_EVIDENCE`, unless a predeclared
technical/integrity condition makes the scientific execution
non-identifiable or invalid. In that case only
`MARKET_05_INCOMPLETE_EXECUTION`.

Predeclared integrity/incomplete conditions:

- ETH companion cannot be rematerialized to the frozen identity;
- a chronological fold fails closed on zero training sd;
- candidate design matrix rank-deficient / ETH_CONFIRMATION collinear
  with baseline;
- required same-support rows are empty in a required fold;
- bootstrap cannot form the frozen 14-day blocks.

Do NOT use NEAR_PASS, MIXED, PROMISING, or PARTIAL_PASS as scientific
promotion states.

---

## 15. Interpretation and anti-rescue

If promoted, the allowed claim is only: Within the frozen 2020-2024
historical development protocol, ETH directional confirmation added
stable and materially nontrivial incremental information about
subsequent BTC direction-aligned adverse-path risk beyond the
preregistered BTC-only baseline.

Forbidden stronger claims: validated edge; tradable alpha; profitable
strategy; causal ETH -> BTC mechanism; OOS confirmation; independent
replication; universal crypto breadth effect.

If `NO_EVIDENCE`, the exact MARKET-05 formulation is closed. Forbidden
rescue under same identity: ETH 12h instead of 24h; horizon 8h/12h/48h;
ETH thresholding; SOL instead of ETH; ETH basket; correlation feature;
relative-strength ratio; bull-only/bear-only; specific years; new BTC
baseline; alternative primary outcome; nonlinear model. Any such idea
requires a NEW explicitly adaptive research identity.

---

## 16. OOS and calibration

```text
SIGNALBOT_PROTECTED_OOS_TOUCHED = false
MARKET_05_TEST_CALIBRATED = NO
```

Protected 2025/2026 values must not be inspected during prereg,
implementation, implementation audit, or ARM. Only a later separately
authorized OOS unit may consume them. Historical promotion does NOT
automatically authorize OOS.

V3 synthetic calibration does not automatically validate this new
cross-asset OLS + chronological prediction + block-bootstrap test
identity. Do NOT open a new synthetic calibration project in this unit.
Do NOT describe MARKET-05 as V3-calibrated.

---

## 17. Lifecycle

```text
FULL_PREREGISTRATION_FROZEN = true
IMPLEMENTATION_FROZEN = false
ARMED = false
EXECUTION_AUTHORIZED = false
SCIENTIFIC_OUTCOMES_INSPECTED = false
PROTECTED_OOS_TOUCHED = false
result_created = false
arm_created = false
evaluator_implemented = false
NEXT_UNIT = OUTCOME_BLIND_MARKET_05_IMPLEMENTATION
```

This freeze does not create MARKET-05 RESULT files, ARM files, or an
evaluator.
