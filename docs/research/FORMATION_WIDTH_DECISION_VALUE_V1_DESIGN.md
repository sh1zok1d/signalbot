# FORMATION_WIDTH_DECISION_VALUE_V1

Design frozen before any decision-value score. This file does not contain its own hash.

## Governing principle

Signalbot does not require the market to produce a preselected effect magnitude. Research freezes observables, estimands, evaluation procedures and anti-overfitting protections before scoring. Effect magnitude and utility are then estimated from the market. Practical thresholds are introduced only when independently justified by an external decision cost, product utility, or operational requirement.

This unit does not use `rho >= +0.10`, an MSE-gain floor, a Brier-gain floor, or a precision floor. None of those was derived from an external cost function. The historical `rho >= +0.10` rule of the earlier formation-width units stays where it was. It is not rewritten and it is not applied here. The Bybit route `POSITIVE_BUT_BELOW_PRACTICAL_SCALE` and the point `+0.09903883442772482` stay unchanged.

## Question

What additional decision value did the market actually give formation width, beyond `RV_FORMATION`?

Not: is the effect large enough to clear a preselected bar.

The objects are: which forecast decisions change, how often, in which direction, and whether the observed next-hour activity is closer to the changed decision.

## Evidence class

`POST_OUTCOME_CHARACTERIZATION / FORECAST_ARCHITECTURE_DEVELOPMENT`.

The surfaces below are already consumed. This unit does not raise an evidence tier, does not create L3, and does not authorize product deployment. It is not an independent confirmation. `PRODUCT_INTEGRATION_CANDIDATE = NO`. A positive decision value still does not enter the forecast architecture inside this unit.

## Context already on the record

Partial Spearman of width with next-hour activity given `RV_FORMATION`:

- Binance `+0.10245095315584887`
- Bybit `+0.09903883442772482`

Out-of-sample mean-squared-error characterization, same folds and rank-score OLS, read `2026-10-09T09:44:11Z`:

- Binance relative MSE improvement `+0.006406560255166168`
- Bybit relative MSE improvement `+0.006500335026704653`
- Binance OOS Spearman baseline `0.7026846266851142`, candidate `0.7068849157696045`
- Bybit OOS Spearman baseline `0.7022674322712014`, candidate `0.7058682258652623`

Both MSE point estimates were positive. Both 95 percent intervals included 0. That read did not measure decision value. This unit does not recompute it and does not retune it.

## Product and activity-state audit

Checked before the decision target was frozen.

Product percentile labels, `config/beta_v0.yaml` `context`, version `BETA_CONTEXT_1H_V3`:

- `label_elevated = 0.80`
- `label_high = 0.95`
- `label_extreme = 0.99`
- `tail_display_max = 0.20`

`beta/context.py` `level_label` maps a mature percentile rank of a current rolling window to `elevated` / `high` / `extreme` / `normal`. The ranked metrics are `range_width_pct_median`, `price_move_pct_median`, and `volume_notional_usd_sum`, against a 30-day reference (V3: the same UTC day type). `beta/hour_gate.py` `BETA_HOUR_GATE_V1` qualifies an hour when at least two of those three ranks clear `label_high` (price uses either tail). `beta/interpretation.py` uses `label_elevated` as the "up" band and states that a label describes the window and never says what comes next. Its status is `PROVISIONAL_PENDING_DRY_RUN`. Stage-2 `confidence_tiers` are maturity spans in days, not activity magnitudes. `beta/rangecast.py` has no activity-state quartile.

These cuts were not taken from the width results. They also do not answer this question. They label the current hour's range, move, and volume. They are not a forecast of next-hour `RV_NEXT`, and they are not a training-fold distribution of that future activity. Transplanting `0.95` or `0.80` onto next-hour realized volatility would be a new forecast threshold wearing an old display cut. They are not the primary target.

No other frozen product definition of the form "high next-hour activity = at least the training percentile X" was found.

## Primary decision target

One inferential target, chosen before scores:

`HIGH` means next-hour `ACTIVITY` is at least the training-fold empirical upper quartile.

`ACTIVITY = RV_NEXT = sqrt(sum r_k^2)` on the 12 future 5-minute log returns of `[01:00, 02:00)`. The quartile is `numpy.quantile` at `0.75`, method `linear`, fit on that fold's training activity only. A value equal to the boundary counts as `HIGH`. The cut is distributional. It was not chosen by scanning where width looks best.

Why this one: it is an interpretable high-activity state, it uses only the training distribution, and it asks about the upper part of activity rather than squared error in the middle of the distribution. The product audit above is why it is not `0.80` or `0.95`.

Descriptive cuts, same machinery, `route_input = false`, no bootstrap, not four hypotheses:

- median, quantile `0.50`
- upper tercile, quantile `2/3`
- upper decile, quantile `0.90`

The route function cannot see them. A pattern in them is not a new main claim.

## Predictors and folds

Baseline: `RV_FORMATION` only. Candidate: `RV_FORMATION + WIDTH`, `WIDTH = (high - low) / P0`. No other predictors. No interactions.

Same expanding yearly tests as the predictive-value unit. End exclusive:

- `[2021-01-01, 2022-01-01)`
- `[2022-01-01, 2023-01-01)`
- `[2023-01-01, 2024-01-01)`
- `[2024-01-01, 2025-01-01)`

Train is `[venue_start, test_start)`. Binance start `2020-01-01`. Bybit start `2020-04-01`. Membership is the formation date. Minimums 60 train days and 30 test days. A short fold stops the unit. Venues are not pooled.

Surfaces, already consumed:

- Binance `CORE_BTC_BINANCE_V0` `[2020-01-01, 2025-01-01)`, analysis N 1820, 262 ISO weeks
- Bybit `LEVEL_CROSS_VENUE_PERP_5M_V0` `[2020-04-01, 2025-01-01)`, analysis N 1613, 240 ISO weeks

The Binance previous-hour span remains sample identity only. Not opened: BitMEX, Binance 2025/2026, E1, prospective forward bars, any new venue. A sample mismatch stops with `SAMPLE_DOES_NOT_MATCH_PUBLISHED` and writes no result.

## Model

Chosen before scores. Logistic regression, not a second continuous OLS.

The previous unit's OLS answers squared error on a rank score of activity. A decision about the upper quartile is a probability. Logistic is the fixed low-capacity probability model for that binary state. It is a different head on the same rank features, not a search over model classes.

Both models use the training-referenced rank scores from the predictive-value unit: training midranks divided by `(n_train + 1)`, and the test map `1 + #{train < x} + 0.5 * #{train == x}` over `(n_train + 1)`. Rank maps are fit on train only.

Baseline: intercept plus the rank score of `RV_FORMATION`. Candidate: the same plus the rank score of width. Newton / IRLS, start at the zero coefficient vector, at most 50 iterations, stop when the largest absolute coefficient step is below `1e-10`. No penalty, no class weight, no hyperparameter. If the weighted design is singular, a coefficient is non-finite, or the iteration budget is exhausted, the fold stops with `FOLD_RANK_DEFICIENT` or `LOGISTIC_DID_NOT_CONVERGE`. No ridge is added afterwards. If a training fold has fewer than two `HIGH` or two non-`HIGH` days, the fold stops with `CLASS_DEGENERATE`.

## Decision

For each model and fold, after the fit:

- predicted probability on train and on test, unclipped
- decision threshold = the training empirical quantile of that model's own training predicted probabilities, at the same probability as the label quantile (`0.75` for the primary)
- test call is `HIGH` when the test probability is at least that frozen threshold

Baseline and candidate each have their own threshold, because their probability scales are not forced to match. The threshold does not see test outcomes or test probabilities.

An upgrade is a test day the candidate calls `HIGH` and the baseline does not. A downgrade is the opposite.

Among days where the calls differ, the candidate change is correct when the candidate call equals the observed `HIGH` state, and harmful when it does not. On a binary state those two partitions exhaust the changed days.

Net decision improvement is the mean of `1{candidate call = state} - 1{baseline call = state}`. It equals the accuracy difference. Positive means the changed calls, taken together, match the observed state more often.

## Proper score and tail discrimination

Primary proper score: Brier, `mean (p - y)^2`. Gain is baseline minus candidate. Positive means width lowers Brier. Log loss is not used. It is unbounded at 0 and 1 and would need a clip, which would be an extra constant.

Tail discrimination: AUROC of the predicted probability against the observed `HIGH` state, with midranks so ties count as 0.5. The reported change is candidate minus baseline. Positive means the candidate ranks observed high-activity days above the others more often. The AUROC interval is estimated and is not a route input.

## Estimand and bootstrap

The primary estimands are functions of the realized out-of-sample sequence from the frozen folds: the paired decision increment, the paired Brier increment, and the AUROC difference. The bootstrap resamples ISO weeks of that sequence. It does not refit rank maps, quartiles, logistic coefficients, or probability thresholds.

`B = 2000`. Generator `numpy.random.default_rng`. Seeds: Binance `20261112`, Bybit `20261113`. Two-sided 95 percent, quantiles `0.025` and `0.975`, NumPy method `linear`. An interval is interpretable when at least 90 percent of draws are finite. Days are concatenated inside drawn weeks, so a larger week has more weight. The same draws are used for the decision increment, the Brier increment, and the AUROC difference.

## Descriptive decomposition

Not a route input. Quartile edges are the training distribution, applied to the test:

- baseline predicted probability
- formation width
- `RV_FORMATION`
- the four calendar folds

Each cell reports its count, decision-change rate, net improvement, and Brier gain. No cell is promoted to a claim. A concentration, if one appears, is only a candidate for a later design.

## Route

Sign, interval exclusion of zero, and cross-venue sign agreement. No magnitude floor.

Let each venue have a net-decision point and interval and a Brier-gain point and interval.

1. Any of the four intervals not interpretable: `INFERENCE_NOT_INTERPRETABLE`.
2. The venues' net points have opposite signs, or their Brier points have opposite signs: `WIDTH_DECISION_EFFECT_HETEROGENEOUS`.
3. All four points are positive and all four intervals lie entirely above zero: `WIDTH_ADDS_CONSISTENT_DECISION_VALUE`.
4. All four points are less than or equal to zero: `WIDTH_ADDS_LITTLE_OR_NO_DECISION_VALUE`.
5. Otherwise: `WIDTH_SIGNAL_PRESENT_DECISION_VALUE_UNCERTAIN`.

Fold signs and the descriptive cuts do not enter. "Reasonably supports" means the intervals lie above zero. "Near zero" is not a separate band. A point of exact zero counts as not positive.

## Product and the prospective unit

This unit does not integrate width. The owner sees the change rate, the correct and harmful counts, the Brier gain, the tail change, the descriptive slices, and the cross-venue signs, and decides.

`FORMATION_WIDTH_ACTIVITY_PROSPECTIVE_V1` is not scored. Its amendments are not rewritten. Forward association is not read. Governance status of that accrual is `ON_HOLD_PENDING_DECISION_VALUE_REVIEW`. The atlas state stays `FUTURE_NATURAL_ACCUMULATION`. Checkpoints and the refusing evaluator stay as they are.

## Execution

Design, folds, model, metrics, and the route are committed before the score. After the score they are not changed. An implementation bug found after the market read stops the unit.
