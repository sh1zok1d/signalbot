# FORMATION_WIDTH_INCREMENTAL_PREDICTIVE_VALUE_V1

Design frozen before any out-of-sample score. This file does not contain its own hash.

## Question

Once next-hour activity is predicted from formation-hour realized volatility, how much does adding formation width improve an honest out-of-sample prediction on Binance and on Bybit?

## Evidence class

`POST_OUTCOME_CHARACTERIZATION / MODEL_DEVELOPMENT`.

The historical surfaces below are already consumed. This unit estimates incremental predictive gain. It does not raise an evidence tier. It is not a pristine confirmation and not an independent confirmation. `PRODUCT_INTEGRATION_CANDIDATE = NO`. It is not L3.

## What this unit does not redo

The frozen Bybit verdict stays `POSITIVE_BUT_BELOW_PRACTICAL_SCALE` at the historical rule `rho >= +0.10`.

Published partial Spearman given `RV_FORMATION`:

- Binance discovery `+0.10245095315584887`
- Bybit `+0.09903883442772482`

`rho >= +0.10` was the practical rule of those units. It was not derived from product utility, prediction error, calibration, PnL, or decision value. It is not deleted, not rewritten, and not transferred into predictive-loss space. This unit does not repair the Bybit result. The Bybit point is not rounded.

## Surfaces

Already read, and only these:

- Binance `CORE_BTC_BINANCE_V0`, formations `[2020-01-01, 2025-01-01)`. Analysis sample identity is the discovery sample: N 1820, 262 ISO weeks, years 365, 364, 363, 363, 365. The previous-hour close span is an eligibility filter so the rows match that sample. It is not a feature.
- Bybit `LEVEL_CROSS_VENUE_PERP_5M_V0` / `bybit_btcusdt_linear_5m.csv.gz`, formations `[2020-04-01, 2025-01-01)`. Analysis sample identity is the published Bybit sample: N 1613, 240 ISO weeks, years 261, 351, 362, 331, 308. No previous-hour filter.

Not opened: BitMEX, 2025/2026 Binance, E1, prospective forward bars, any new venue.

If either published N or week count does not match, the run stops with `SAMPLE_DOES_NOT_MATCH_PUBLISHED` and writes no result. Eligibility is not retuned.

## Target

One target. `ACTIVITY = RV_NEXT = sqrt(sum r_k^2)` on the 12 future 5-minute log returns of `[01:00, 02:00)`.

Not added: displacement, signed return, direction, a thresholded move.

## Predictor sets

Same rows, same folds, same target, same transformations, same model family.

- Baseline: `RV_FORMATION` only.
- Candidate: `RV_FORMATION + V`, with `V = (high - low) / P0`.

Not added: `RV_PREV` as a feature, volume, open interest, funding, flow, lagged activity, hour of day, year, regime labels.

## Folds

Expanding origin, yearly, frozen before scores. Membership is the formation date. The same folds are used for both models. No random K-fold. Venues are not pooled into one fit.

Test windows, end exclusive:

- `[2021-01-01, 2022-01-01)`
- `[2022-01-01, 2023-01-01)`
- `[2023-01-01, 2024-01-01)`
- `[2024-01-01, 2025-01-01)`

Train is `[venue_start, test_start)`. Binance `venue_start` is `2020-01-01`. Bybit `venue_start` is `2020-04-01`. The year 2020 is train only. A later test year enters the next train window only after it has been scored.

Minimums, not tuning knobs: 60 train days and 30 test days. A fold under a minimum stops with `FOLD_BELOW_FROZEN_MINIMUM` and writes no result.

## Model class, chosen before execution

Rejected before any score:

- Ridge: an extra hyperparameter with nothing to identify it without a target search.
- Raw-scale OLS: squared error on raw realized volatility is dominated by heavy tails.
- Log target: a different scale from the rank structure of the historical evidence.
- Any model chosen by held-out loss.

Chosen class: ordinary least squares on training-referenced rank scores. One family for baseline and candidate. Deterministic. Two or three columns. No hyperparameter.

Training score of a column is `average_ranks(train) / (n_train + 1)`, mergesort midranks, the same rank function as the historical Spearman. Test score uses only the training multiset:

`rank = 1 + #{train < x} + 0.5 * #{train == x}`, then divide by `(n_train + 1)`.

That test map is not the training midrank. On a training point the two differ, including when there are no ties, because the test map counts the point inside the training multiset. Training points therefore use midranks. Test points use the map above. A test value above every training value scores 1. Nothing is clipped. Nothing is re-ranked on the test fold.

The target score is the rank score of `ACTIVITY`, fit on training activity only, and it is shared by both models. The `RV_FORMATION` score is shared. The width score is candidate-only.

Fit is `numpy.linalg.lstsq` with `rcond=None` and an intercept. If the training design rank is below its column count, the fold stops with `FOLD_RANK_DEFICIENT`. No alternate model is substituted.

## No leakage

For each fold, in order: fit the three training maps (activity, realized volatility, width); transform train; transform test with those frozen maps; fit each model on train; predict test. No full-sample rank, no full-sample normalization, no future-fold distribution, no tuning on held-out loss.

## Metrics

Primary loss is the mean squared error of the prediction against the training-referenced activity rank score. The mean is over out-of-sample days pooled across the four folds, not the average of the four fold means.

`d_i = (y_i - pred_baseline_i)^2 - (y_i - pred_candidate_i)^2`

`ΔMSE = mean(d)`. Positive means width improves prediction. Relative improvement is `ΔMSE / MSE_baseline`. Root mean squared error is only the square root of the reported MSE, a scale reading. It is not bootstrapped and it is not a second decision.

No new yes/no bar is frozen. In particular there is no rule of the form `ΔMSE >= 1%`, and `rho >= +0.10` is not applied.

Secondary, descriptive, pooled out-of-sample days only, not bootstrapped: Spearman of each model's prediction with raw `ACTIVITY`, using midranks and Pearson.

The fold table is point estimates: train size, test size, both losses, absolute improvement, relative improvement.

## Inference

The inferential object is the mean of the paired out-of-sample loss differences already formed. The bootstrap does not refit models.

Block unit: ISO week `(iso_year, iso_week)` of the formation date, among out-of-sample days only. Weeks are drawn with replacement. Days inside a drawn week stay together. The draw mean is the mean of the concatenated days, so a larger week has more weight. Days are not drawn independently.

`B = 2000`. Generator `numpy.random.default_rng`. Seeds: Binance `20261110`, Bybit `20261111`. These seeds are unused by the previous formation-width units (`20261024` through `20261109`).

Interval: two-sided 95 percent, quantiles `0.025` and `0.975`, NumPy method `linear`. The interval estimates magnitude. It is not a forced binary confirmation. The share of bootstrap means above zero is descriptive and is not a threshold.

The interval is interpretable when at least 90 percent of draws are finite. Otherwise the venue is not interpretable and no result is rescued by another interval.

## Synthesis

Full evaluation separately on Binance and on Bybit. Then a side-by-side reading: sign agreement of the two point estimates, and the predeclared interval label below. No pooled model. No weighted mean presented as a confirmation.

## Interpretation labels, frozen before scores

Applied only after both venues have been scored, and only to the frozen interval geometry:

- An interval that is not interpretable: `INFERENCE_NOT_INTERPRETABLE`.
- Point estimates of opposite sign: `VENUES_DO_NOT_AGREE`.
- Both intervals entirely above zero: `POSITIVE_INCREMENTAL_PREDICTIVE_VALUE_WITHIN_MODEL_CLASS`. Width carries predictive information not fully captured by formation realized volatility within this model class. The gain is the estimated magnitude. Width is not said to cause activity.
- Both intervals entirely below zero: `PARTIAL_CORRELATION_DID_NOT_TRANSLATE`.
- Both point estimates positive, and the pair of intervals is not the both-above-zero case: `POINT_ESTIMATES_FAVOR_GAIN_INTERVALS_DO_NOT_BOTH_EXCLUDE_ZERO`.
- Otherwise: `POINT_ESTIMATES_DO_NOT_FAVOR_WIDTH`.

Whether the gain is large enough for a future dedicated validation is not a frozen yes or no. The owner judges that from the magnitude and the complexity cost. This unit does not make a product decision.

## Prospective unit

`FORMATION_WIDTH_ACTIVITY_PROSPECTIVE_V1` is not deleted, not scored, and not used as a blocker. Its forward association is not read. Governance state of that accrual is `ON_HOLD_PENDING_PREDICTIVE_VALUE_CHARACTERIZATION`. The atlas has no on-hold state, so the atlas state of the prospective unit stays `FUTURE_NATURAL_ACCUMULATION`. Checkpoints, the Amendment A1 budget, and the refusing evaluator stay as they are.

## Execution

The design, folds, model, and metrics are committed before the score. After the score they are not changed. An implementation bug found after the market read stops the unit. It is not repaired inside this read.
