# MARKET-06 CROSS_VENUE_DISLOCATION_ADVERSE_PATH_RISK — Preregistration

- **Status:** `PREREGISTERED_OUTCOME_BLIND_UNFROZEN`
- **Unit ID:** `MARKET_06_CROSS_VENUE_DISLOCATION_PREREG`
- **Research ID:** `MARKET-06_CROSS_VENUE_DISLOCATION_ADVERSE_PATH_RISK`
- **Short name:** `MARKET-06`
- **Date:** 2026-09-21
- **Machine-readable twin:** [`MARKET_06_CROSS_VENUE_DISLOCATION_PREREG.json`](MARKET_06_CROSS_VENUE_DISLOCATION_PREREG.json)

This document is the complete outcome-blind MARKET-06 scientific contract.
It does **not** freeze (a separate docs-only freeze is required), ARM,
implement an evaluator, execute, or create RESULT.

No MARKET-06 OHLC values, dislocation values, eligible-row counts from
price data, future returns, MAE, betas, or holdout metrics were inspected
to write this text. Thresholds and windows below are author-frozen, not
searched.

```text
PRE_PREREG_HEAD = a75a5272f994f9728308c47c524f2839b73762a7
PRE_PREREG_TREE = 7272614b7a2799aaf82a80f5d7c9cb1207af01ac
FULL_PREREGISTRATION_FROZEN = false
MARKET_06_FREEZE_REQUIRED = true
IMPLEMENTATION_FROZEN = false
ARMED = false
EXECUTION_AUTHORIZED = false
SCIENTIFIC_OUTCOMES_INSPECTED = false
PROTECTED_OOS_TOUCHED = false
MARKET_06_TEST_CALIBRATED = NO
```

---

## 0. What this is and is not

Incremental-information market-relationship study. Not a trading
strategy.

Forbidden in this prereg and any later RESULT: entries, exits,
stop-losses, take-profits, fees, Sharpe, position sizing, PnL
optimization, production enablement, automatic OOS promotion.

This is **not**:

- a MARKET-01 / MARKET-02 / MARKET-03 / MARKET-04 / MARKET-05 rescue;
- a funding, OI, or ETH-confirmation variant;
- same-venue Binance spot-versus-perp basis (M04 family);
- a claim that dislocation causes adverse path;
- a PnL claim;
- V3 confirmatory reuse;
- B2-06 execution.

V3 remains closed historical instrumentation
(`V3_METHODOLOGY_CLAIMABLE = NO`). This prereg does not modify V3 and
does not create V4 (`DEFAULT_V4 = NO`). The MARKET-06 test itself is
uncalibrated (`MARKET_06_TEST_CALIBRATED = NO`).

Protected 2025 validation and 2026 OOS remain untouched and forbidden.

---

## 1. Exact scientific claim

```text
PRIMARY_CLAIM = Conditional on BTC's own recent directional displacement
and volatility state, unusually large absolute cross-venue disagreement
between Binance USD-M BTCUSDT perpetual trade-price close and OKX
BTC-USDT spot close contains stable incremental information about
subsequent BTC direction-aligned 24-hour adverse-path risk.
```

The candidate feature is continuous `ABS_DISLOCATION_Z`. The hypothesized
mechanism direction is: larger unusual `|dislocation|` corresponds to
**higher** subsequent direction-aligned adverse excursion
(`EXPECTED_BETA_SIGN = positive`).

This is an incremental-information claim only.

```text
TARGET = BINANCE_USD_M_BTCUSDT_PERP
CONTEXT_LEG = OKX_BTC_USDT_SPOT
one_btc_experiment = true
simple_direction_predictor = false
```

---

## 2. Data authorities

Bound feasibility identity (do not remint):

```text
DATASET_ID = MARKET_06_OKX_BINANCE_FEASIBILITY_V0
SNAPSHOT_ID = e0403e40a9b1e2903f15fb9283ec6caf54788e48153038982e364d4318183e68
DURABLE_EVIDENCE_ROOT_SHA256 = f4b9e16a62707c70e782cc318399f3ba53ebb85c792e96cd12c164a98f0cdc6f
SOURCE_FEASIBILITY_HEAD = ef439110684e5bef5d6b6f31b664c21a114111b2
RAW_WINDOW = [2022-01-01T00:00:00Z, 2025-01-01T00:00:00Z)
NATIVE_GRAIN = 5m
```

Identity-file SHA256s (unchanged from mint):

```text
binance_object_ledger.json = 437f10220b49a7f74e2c76445f5388ffc4006673d232c8b90f1946fe97e40fbf
okx_page_manifest.json     = 22702942c3860cd3c026784a4abda129470d893149bbb612cd36b33a99f1a9d9
timestamp_census.json      = ad96ec9756ec77092a2eb26a6178e77b1a7dad4c2af21fdbc9ce92b3a2159d70
snapshot.json              = dfc6006f020af551d56b26caee6b694967c26557a405e9c668a78d77f74d4ba7
```

**Perpetual leg (unchanged):** Binance USD-M `BTCUSDT` 5m **trade-price**
klines from official Public Data
`data/futures/um/monthly/klines/BTCUSDT/5m/`. Mark-price klines are not
substituted. `open_time` is bar start. `bar_end_exclusive = open_time + 5m`.
`available_at = bar_end_exclusive`. Close at clock `U` is the close of the
canonical 5m bar whose `bar_end_exclusive` equals `U`. Strictly positive
close required.

**Spot leg:** official OKX `GET /api/v5/market/history-candles`
`instId=BTC-USDT` `bar=5m`. `ts` is candle open. `bar_end_exclusive = ts + 5m`.
Only `confirm=1` completed candles are legal. Aggregators, Binance spot,
and Bybit spot are forbidden.

Quote asset on both legs: `USDT`. Cross-venue structure is required.

Durable raw bytes:
`docs/research_data/MARKET_06_OKX_BINANCE_FEASIBILITY_V0/durable_raw/`.

The Bybit-route artifact
`docs/research/MARKET_06_CROSS_VENUE_FEASIBILITY.md` is preserved
historical evidence and is **not** this study's source authority.

`CORE_BTC_BINANCE_V0` is not the MARKET-06 price authority.

---

## 3. Decision clock and conservative feature cutoff

```text
DECISION_FREQUENCY = one decision per UTC day
DECISION_TIME_T    = that day's 00:05:00 UTC
FEATURE_CUTOFF     = T - 5 minutes = that day's 00:00:00 UTC
OUTCOME_HORIZON    = 24 hours = 288 native 5m bars
ENTRY              = open of the Binance perp 5m bar whose open_time = T
```

No information with `available_at > FEATURE_CUTOFF` may enter
eligibility, features, controls, standardization, or model fitting.
The still-forming bar that begins at `T` must not enter features.
No alternative UTC hour may be inspected after execution under this
identity. No intraday grid. No 6h / 12h / 48h lookback comparison.

Reason for `00:05` plus `FEATURE_CUTOFF = T-5m`: one clean daily
observational unit, reduced repeated 5m dependence, and a conservative
completed-candle lag so the last feature bar has `bar_end_exclusive =
FEATURE_CUTOFF`.

---

## 4. Feature construction

All feature quantities below are evaluated at `FEATURE_CUTOFF`.

### 4.1 Cross-venue dislocation

For every completed aligned 5m boundary `u` with both legs legal:

```text
D(u) = ln( perp_close(u) / spot_close(u) )
```

natural log. Both closes finite and strictly positive. Otherwise `D(u)`
is missing.

Let `e` be the unique boundary `FEATURE_CUTOFF`. Then:

```text
D_e = D(FEATURE_CUTOFF)
```

**Reference set (exactly 8640 preceding 5m dislocations, current excluded):**

```text
REF_e = { D(FEATURE_CUTOFF - k * 5m) : k = 1, 2, ..., 8640 }
```

`D_e` is **not** a member of `REF_e`. `8640 * 5m = 30 days`.

If any of the 8640 references is missing or non-finite, or `D_e` is
missing or non-finite: the decision row is `ROW_NOT_ELIGIBLE` for
**both** models.

```text
MED_e = numpy.median(REF_e)          # n=8640 even; mean of items 4320 and 4321 of the sorted sample
MAD_e = numpy.median( |D_ref - MED_e| for D_ref in REF_e )
```

No 1.4826 consistency constant. No clipping, winsorization, percentile
transform, or rank transform of `D`.

```text
MAD_e <= 0  =>  ROW_NOT_ELIGIBLE
Z_e = (D_e - MED_e) / MAD_e
ABS_DISLOCATION_Z = abs(Z_e)
PRIMARY_FEATURE = ABS_DISLOCATION_Z
```

`ABS_DISLOCATION_Z` remains CONTINUOUS. No threshold or bucket defines
the primary test.

### 4.2 BTC own-state controls (perp only)

Let `P_perp(u)` be the Binance perp close of the bar with
`bar_end_exclusive = u`.

```text
BTC_RET_24H = ln( P_perp(FEATURE_CUTOFF) / P_perp(FEATURE_CUTOFF - 24h) )
BTC_SIDE    = sign(BTC_RET_24H)     # +1 if >0, -1 if <0
```

```text
BTC_RET_24H == 0  =>  ROW_NOT_ELIGIBLE
```

Exact-zero exclusion only. No epsilon / minimum-move threshold.

Realized volatility over the 288 consecutive 5m log returns whose
right endpoint is `FEATURE_CUTOFF`:

```text
r_i = ln( close_i / close_{i-1} )     # i = 1..288
close_0 = P_perp(FEATURE_CUTOFF - 24h)
close_1 .. close_288 cover bar_end in (FEATURE_CUTOFF-24h, FEATURE_CUTOFF]
RV_BTC_24H = sqrt(sum_{i=1..288} r_i^2)
```

No annualization. No alternative volatility estimator.

Fewer or more than 288 returns, any unavailable required perp bar, or
non-finite/`<= 0` `RV_BTC_24H`: `ROW_NOT_ELIGIBLE`.

```text
Z_BTC     = BTC_RET_24H / RV_BTC_24H
ABS_Z_BTC = abs(Z_BTC)
```

Spot prices do not enter BTC own-state controls.

---

## 5. Primary outcome

```text
PRIMARY_OUTCOME = 24H_DIRECTION_ALIGNED_BTC_MAE
Y_NAME          = 24H_DIRECTION_ALIGNED_BTC_MAE
OUTCOME_HORIZON = 24 hours
FUTURE_BARS     = 288 Binance perp 5m OHLC bars
ENTRY           = open of the Binance perp 5m bar with open_time = T
PATH_WINDOW     = bars with open_time in [T, T+24h)
```

Use Binance perp OHLC only. No final-return substitution. No MFE/PnL
substitution. No spot path.

For `BTC_SIDE = +1`:

```text
ADVERSE_PRICE = minimum low among the 288 path bars
Y = max(0, ln(ENTRY / ADVERSE_PRICE))
```

For `BTC_SIDE = -1`:

```text
ADVERSE_PRICE = maximum high among the 288 path bars
Y = max(0, ln(ADVERSE_PRICE / ENTRY))
```

Thus `Y >= 0`. Higher `Y` = worse adverse excursion against the
pre-cutoff BTC direction.

Missing/non-finite required OHLC on any of the 288 path bars, or
non-positive `ENTRY` or `ADVERSE_PRICE`: `ROW_NOT_ELIGIBLE`.

---

## 6. Eligible rows and same support

A decision `T` is confirmatory-eligible iff all of:

1. `T` is a frozen grid time in §8;
2. `D_e` and all 8640 refs finite (both venues legal, `confirm=1` for OKX);
3. `MAD_e > 0`;
4. `BTC_RET_24H` finite and `!= 0`;
5. `RV_BTC_24H` finite and `> 0` from exactly 288 5m returns;
6. all required feature bars have `bar_end_exclusive <= FEATURE_CUTOFF`;
7. all 288 outcome bars exist with finite OHLC;
8. `Y` finite.

Fail closed. Never interpolate, forward-fill, upsample, or repair gaps.
Missingness is not zero dislocation and not zero return.

`same_support_required = true`. Any row ineligible for one model is
ineligible for both. Do not compute eligible-row counts in this unit.

---

## 7. Exact baseline and candidate

```text
BASELINE_MODEL  = Y ~ BTC_SIDE + ABS_Z_BTC + RV_BTC_24H
CANDIDATE_MODEL = Y ~ BTC_SIDE + ABS_Z_BTC + RV_BTC_24H + ABS_DISLOCATION_Z
```

Baseline design matrix columns, in order:

```text
[ INTERCEPT, BTC_SIDE, ABS_Z_BTC, RV_BTC_24H ]
```

Candidate = exact baseline plus `ABS_DISLOCATION_Z` as the last column.

```text
[ INTERCEPT, BTC_SIDE, ABS_Z_BTC, RV_BTC_24H, ABS_DISLOCATION_Z ]
```

No interaction terms. No polynomial terms. No signed `D_e` as a
candidate regressor. No MAD/median as separate candidate regressors.
No funding, OI, taker, ETH, or technical-indicator fields. No feature
selection.

MARKET-06 asks exactly one incremental question: does
`ABS_DISLOCATION_Z` add information beyond the BTC-only baseline?

```text
MODEL_CLASS = ORDINARY_LEAST_SQUARES_LINEAR_REGRESSION
solver = numpy.linalg.solve on X'X β = X'y
numpy_version = 2.1.3
```

If `numpy.linalg.matrix_rank(X'X) < ncols`, `LinAlgError`, or any
coefficient non-finite: `MARKET_06_INCOMPLETE_EXECUTION`. Do not use
`lstsq`, ridge, pseudoinverse, or ML. No regularization. No
hyperparameter tuning. Predictions are not clipped.

A candidate design matrix whose `ABS_DISLOCATION_Z` column is exactly
collinear with the baseline columns is `MARKET_06_INCOMPLETE_EXECUTION`,
not scientific `NO_EVIDENCE`.

---

## 8. Train / holdout (no refit)

No random split. No expanding-window refit. Coefficients are fit
**once** on train and applied unchanged to both holdouts.

```text
TRAIN_START_T = 2022-02-01T00:05:00Z
TRAIN_END_T   = 2022-12-30T00:05:00Z     inclusive
HOLDOUT_2023  = 2023-01-01T00:05:00Z through 2023-12-30T00:05:00Z inclusive
HOLDOUT_2024  = 2024-01-01T00:05:00Z through 2024-12-30T00:05:00Z inclusive
```

January 2022 supplies the 30-day dislocation reference / 24h BTC state
prefix for the first train decision; it is not itself a train decision
time.

**No 31 December decision** on this identity. A `T = YYYY-12-31T00:05:00Z`
row would require outcome bars into `YYYY+1-01-01`. For 2024 that would
open protected 2025. The same calendar rule is applied to 2022 and 2023
so the daily grid is uniform.

2022 eligible rows are **train only**. They are never promoted as
held-out evidence.

2025 and 2026 remain untouched.

---

## 9. Standardization

Continuous-predictor standardization parameters are learned **only**
from eligible TRAIN rows (2022 grid). Apply those exact train mean/sd
unchanged to 2023 and 2024. No holdout information. No refit. No
full-period normalization before evaluation.

```text
x_std = (x - train_mean) / train_sd
```

`BTC_SIDE` is not standardized. `INTERCEPT` is not standardized.
Continuous features: `ABS_Z_BTC`, `RV_BTC_24H`, and (candidate only)
`ABS_DISLOCATION_Z`.

Zero or non-finite train sd for any continuous feature: fail closed
(`MARKET_06_INCOMPLETE_EXECUTION`).

---

## 10. Primary predictive metric and materiality

Fit both models on standardized eligible TRAIN rows. Predict `Y` on
eligible 2023 and 2024 holdout rows **without refitting**.

MAE is mean absolute prediction error for `Y`.

Pooled held-out loss concatenates 2023 then 2024 predictions in
chronological `T` order:

```text
RELATIVE_MAE_IMPROVEMENT = 1 - (POOLED_MAE_CANDIDATE / POOLED_MAE_BASELINE)
MATERIAL_RELATIVE_MAE_IMPROVEMENT = 0.02
```

Positive = candidate predicts adverse risk better. Do NOT lower 2%
after outcomes. 2% is a preregistered practical-information threshold,
not a claim of trading profitability.

If `POOLED_MAE_BASELINE` is non-finite or `<= 0`:
`MARKET_06_INCOMPLETE_EXECUTION`.

Empty eligible support on TRAIN or on either holdout year:
`MARKET_06_INCOMPLETE_EXECUTION`. This unit does not count those rows.

---

## 11. Directional mechanism coefficient

`BETA_ABS_DISLOCATION_Z` is the last coefficient of the candidate OLS
fit on eligible TRAIN rows only (after the frozen train
standardization). It is not refit on holdouts.

```text
EXPECTED_BETA_SIGN = positive
GATE_1_DIRECTION   = BETA_ABS_DISLOCATION_Z > 0
```

Expected sign is positive because larger unusual `|dislocation|` is
hypothesized to correspond to **higher** future adverse excursion. The
coefficient is a required mechanism-direction gate. It is **not** by
itself sufficient for promotion.

---

## 12. Dependence-aware uncertainty

```text
BLOCK_BOOTSTRAP_UNIT = UTC calendar day rows (already one row per T)
BLOCK_LENGTH         = 14 consecutive days
BOOTSTRAP_REPLICATES = 5000
RANDOM_SEED          = 2026092106
BOOTSTRAP_KIND       = CIRCULAR_MOVING_BLOCK
RNG                  = numpy.random.Generator(numpy.random.PCG64(2026092106))
numpy_version        = 2.1.3
```

Deterministic circular moving-block bootstrap. Blocks wrap the end of
the resampled series to the start. One frozen method, two predeclared
statistics:

1. `RELATIVE_MAE_IMPROVEMENT`: models are fit once on train; bootstrap
   resamples held-out daily loss-difference tuples
   `(T, abs_err_baseline, abs_err_candidate)` from the concatenated
   2023+2024 holdout sequence in 14-day circular blocks **without
   refitting**.
2. `BETA_ABS_DISLOCATION_Z`: circular 14-day block bootstrap of TRAIN
   daily rows; **refit** only the candidate OLS on each replicate
   (reusing frozen train standardization parameters; do not re-estimate
   mean/sd inside replicates); collect `BETA_ABS_DISLOCATION_Z`.

Do NOT choose method after results. Do not refit the predictive models
inside the predictive bootstrap. `python_hash` forbidden. Reroll
forbidden.

Confidence bounds are the 2.5th and 97.5th percentiles of the 5000
replicate statistics via `numpy.percentile(..., [2.5, 97.5], method="linear")`.

If a replicate series is too short to form one 14-day block, or any
coefficient replicate is non-finite/rank-deficient:
`MARKET_06_INCOMPLETE_EXECUTION` (no redraw, no drop).

---

## 13. Six gates (all required)

```text
GATE_1_DIRECTION              = TRAIN BETA_ABS_DISLOCATION_Z > 0
GATE_2_DIRECTION_UNCERTAINTY  = 95% block-bootstrap upper confidence bound for BETA_ABS_DISLOCATION_Z > 0
GATE_3_PREDICTIVE_SIGN        = RELATIVE_MAE_IMPROVEMENT > 0
GATE_4_PREDICTIVE_UNCERTAINTY = 95% block-bootstrap lower confidence bound for RELATIVE_MAE_IMPROVEMENT > 0
GATE_5_MATERIALITY            = RELATIVE_MAE_IMPROVEMENT >= 0.02
GATE_6_TEMPORAL_STABILITY     = both holdout years 2023 and 2024 have YEAR_RELATIVE_MAE_IMPROVEMENT > 0
                                AND no holdout year YEAR_RELATIVE_MAE_IMPROVEMENT <= -0.02
```

Year metrics use that year's holdout rows only, still under the frozen
2022 coefficients (no refit).

Do NOT change gates after outcomes. No parameter-neighborhood grid.
Any different lookback, hour, horizon, transform, or model is a new
research ID.

---

## 14. Primary classification

```text
PROMOTION_CLASSIFICATION      = MARKET_06_PROMOTED_HISTORICAL_CANDIDATE
FAIL_CLASSIFICATION           = MARKET_06_NO_EVIDENCE
INTEGRITY_FAIL_CLASSIFICATION = MARKET_06_INCOMPLETE_EXECUTION
```

`MARKET_06_PROMOTED_HISTORICAL_CANDIDATE` iff **all six gates** pass and
all integrity/data/support contracts pass.

Otherwise `MARKET_06_NO_EVIDENCE`, unless a predeclared technical /
integrity condition makes execution non-identifiable or invalid, in
which case only `MARKET_06_INCOMPLETE_EXECUTION`.

Predeclared integrity/incomplete conditions include:

- durable snapshot identity mismatch;
- a required train or holdout support is empty;
- zero/non-finite train sd;
- candidate rank-deficient / `ABS_DISLOCATION_Z` collinear with baseline;
- bootstrap cannot form the frozen 14-day blocks;
- non-finite pooled baseline MAE.

Do NOT use `NEAR_PASS`, `MIXED`, `PROMISING`, or `PARTIAL_PASS` as
scientific promotion states.

`MARKET_06_PROMOTED_HISTORICAL_CANDIDATE` means only: within this frozen
2022-train / 2023–2024-holdout protocol, `ABS_DISLOCATION_Z` added
stable and materially nontrivial incremental information about
subsequent BTC direction-aligned adverse-path risk beyond the
preregistered BTC-only baseline.

It does **not** mean validated alpha, tradable edge, profitable
strategy, causal proof, OOS confirmation, or production readiness.

---

## 15. Anti-rescue

If `NO_EVIDENCE`, the exact MARKET-06 formulation is closed. Forbidden
rescue under the same identity: signed dislocation; Bybit spot; Binance
spot; different UTC hour; 12h/48h horizon; z-score using mean/sd
instead of median/MAD; 1.4826 MAD scale; 7d/60d refs; adding
interactions; nonlinear models; year-subsetting; lowering 2%; refitting
on holdouts; opening 2025/2026.

A materially different rule requires a **new** hypothesis ID.

No selective rerun. No post-outcome threshold repair.

---

## 16. Lifecycle (this unit)

```text
prereg_frozen                    = false
implementation_authorized        = false
arm_authorized                   = false
market_06_execution_authorized   = false
b2_06_execution_authorized       = false
protected_oos_authorized         = false
default_v4                       = false
v3_reused_as_market_06_test      = false
market_06_test_calibrated        = false
outcome_inspection_authorized    = false
evaluator_implemented            = false
result_created                   = false
arm_created                      = false
```

Next required step after this document: **separate prereg freeze**.
Then a later implementation unit. Not this unit.

```text
NEXT_UNIT = MARKET_06_PREREG_FREEZE
```
