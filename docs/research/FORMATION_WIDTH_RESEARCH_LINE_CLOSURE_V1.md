# FORMATION WIDTH research line — closure

`LINE = FORMATION_WIDTH_V1`
`STATUS = CLOSED / NO ACTIVE SUCCESSOR`
`LABEL = REPRODUCIBLE_SMALL_INCREMENTAL_STATE_SIGNAL_DECISION_VALUE_NOT_DEMONSTRATED`
`NEXT_UNIT = NONE`
`PRODUCT_INTEGRATION_CANDIDATE = NO`
`NEW_MARKET_READ = none`
`PROSPECTIVE_OUTCOME_READ = false`
`FUTURE_ASSOCIATION_READ = false`

This file is the canonical final pointer for the formation-width line. The design and result files of the units below stay as the lineage. Their numbers and routes are not rewritten here.

## Scientific conclusion

Formation WIDTH exhibits a small, reproducible incremental association with next-hour ACTIVITY beyond contemporaneous `RV_FORMATION`. The observed partial association was approximately `+0.10` on both Binance and Bybit. Historical OOS characterization suggested a small continuous predictive gain of approximately `+0.64%` baseline MSE on both venues, but uncertainty included zero. In the frozen downstream HIGH-activity decision architecture, WIDTH changed very few decisions and did not demonstrate improvement in Brier score or AUROC. Therefore WIDTH is retained as a scientifically observed state descriptor, but its practical forecast decision value is not demonstrated.

## Methodological lesson

Signalbot does not require the market to meet arbitrary effect thresholds. The research process freezes observables and evaluation rules to prevent self-deception, then estimates the magnitude and utility the market actually provides. Statistical association alone does not justify forecast or product inclusion. A feature may be scientifically real and still be excluded when downstream decision value is not demonstrated.

Old thresholds were valid frozen decision rules for their units. They are not interpreted as natural market boundaries. The rule `rho >= +0.10` remains the rule of the units that froze it. It is not moved, lowered, or reapplied to the later characterizations.

## Units

| Unit | Atlas state after this closure | What stays on its own record |
| --- | --- | --- |
| `FORMATION_WIDTH_REGIME_V1` | `CLOSED_ON_SURFACE` | route `FORMATION_WIDTH_REGIME_STRUCTURE_PRESENT`; ACTIVITY partial Spearman `+0.10245095315584887` |
| `FORMATION_WIDTH_ACTIVITY_CONFIRMATION_V1` | `INFORMATIONALLY_WEAK` | endpoint unread; route `INFORMATIONALLY_WEAK_BEFORE_OUTCOME` |
| `FORMATION_WIDTH_ACTIVITY_BYBIT_FEASIBILITY_V1` | `CLOSED_ON_SURFACE` | route `POSITIVE_BUT_BELOW_PRACTICAL_SCALE`; partial Spearman `+0.09903883442772482` |
| `FORMATION_WIDTH_ACTIVITY_PROSPECTIVE_V1` | `CLOSED_BEFORE_START` | `outcome_read = false`; no checkpoint; no alpha spent |
| `FORMATION_WIDTH_INCREMENTAL_PREDICTIVE_VALUE_V1` | `CLOSED_ON_SURFACE` | label `POINT_ESTIMATES_FAVOR_GAIN_INTERVALS_DO_NOT_BOTH_EXCLUDE_ZERO` |
| `FORMATION_WIDTH_DECISION_VALUE_V1` | `CLOSED_ON_SURFACE` | label `WIDTH_SIGNAL_PRESENT_DECISION_VALUE_UNCERTAIN` |

## Chronology

The chain is the order of questions. A later step does not strengthen an earlier unit past that unit's own record.

1. The frozen UTC-hour boundary contrast on `CORE_BTC_BINANCE_V0` reported a UTC_00 resolution gap of about `+9.48` pp (`OPENING_RANGE_OBJECT_V1`, route `FUNDING_ANCHOR_OR_PERIODIC_RANGE_STRUCTURE`).
2. The equal-width diagnosis on the same already consumed pairs scaled the published partner to the real formation width. On common support the gap went from about `+9.55` pp to about `-0.58` pp. The published route is unchanged. The comparison does not separate a special property of the hour's bounds from a difference of width and of the volatility regime. The spot equal-width resolution contrast stayed `NO_WIDTH_HELD_RESOLUTION_DIFFERENCE`.
3. `FORMATION_WIDTH_REGIME_V1` asked whether relative width of the completed UTC midnight hour is a point-in-time state for the next 60 minutes. One read, `2026-10-09T05:40:02Z`. Route `FORMATION_WIDTH_REGIME_STRUCTURE_PRESENT`. Supporting endpoint ACTIVITY.
4. Amendment A1 of that unit asked whether width adds association beyond realized volatility of the same hour. `RV_PREV` stayed descriptive.
5. Binance partial Spearman of width with next-hour ACTIVITY given `RV_FORMATION`: `+0.10245095315584887`. Family interval about `[+0.04797984625391018, +0.15534901403484885]`. N 1820.
6. Bybit, same cell, class `SAME_CALENDAR_CROSS_VENUE_EXPOSED_REPLICATION`, one read `2026-10-09T07:56:02Z`. Partial Spearman `+0.09903883442772482`. One-sided lower bound about `+0.054006220155678755`. Route `POSITIVE_BUT_BELOW_PRACTICAL_SCALE` under the frozen rule `rho >= +0.10`. The point is not rounded to `+0.10`.
7. `FORMATION_WIDTH_INCREMENTAL_PREDICTIVE_VALUE_V1`, one OOS read `2026-10-09T09:44:11Z`, already consumed windows, venues not pooled. Relative MSE improvement Binance `+0.006406560255166168` (`+0.6406560255166168` percent), Bybit `+0.006500335026704653` (`+0.6500335026704652` percent). Both intervals include 0. Label `POINT_ESTIMATES_FAVOR_GAIN_INTERVALS_DO_NOT_BOTH_EXCLUDE_ZERO`.
8. `FORMATION_WIDTH_DECISION_VALUE_V1`, one read `2026-10-09T10:05:39Z`. Primary target: training upper quartile of next-hour ACTIVITY. Unpenalized logistic. Binance changed 14 of 1455 calls (8 correct, 6 harmful); net `+0.0013745704467353953`. Bybit changed 5 of 1352 calls (3 correct, 2 harmful); net `+0.0007396449704142012`. Brier gain Binance `-1.2538622961901123e-06`, Bybit `-0.00023495296074117734`. AUROC change Binance `-0.0016015177143796633`, Bybit `-0.001128979857049961`. All four route intervals include 0. Label `WIDTH_SIGNAL_PRESENT_DECISION_VALUE_UNCERTAIN`.
9. This closure. The line stops. `NEXT_UNIT = NONE`.

The spot confirmation window stayed below its frozen power floor. Its endpoint was not read. That absence is not a null and not a confirmation.

## Prospective unit

`FORMATION_WIDTH_ACTIVITY_PROSPECTIVE_V1` is closed before any outcome.

Atlas state: `CLOSED_BEFORE_START`.

Final status text: `SUPERSEDED_BEFORE_OUTCOME_BY_DOWNSTREAM_DECISION_VALUE_CHARACTERIZATION`.

The prospective design targeted long-horizon validation of a practical partial-correlation magnitude. Subsequent historical characterization showed that WIDTH's small residual signal did not demonstrate downstream decision/proper-score value in the frozen forecast architecture. The owner therefore closes the prospective question before any forward score rather than spending years validating a claim that is no longer architecture-relevant.

This is not a statistical failure and not a negative prospective result.

```
outcome_read = false
future_association_read = false
formal_checkpoint = none
forward_partial_rho = not computed
alpha_spent = 0
accrued_analysis_N = 0
parent_design_SHA256 = d07b83ca9baea11d0af16424da6f7a7a29d43a2a61b6d850d974c8ed80da9612
```

Amendment A1 and the parent design file are not rewritten. Their checkpoint grid and error budget remain the record of what was frozen. They are not an active research obligation. The surface `BINANCE_UM_LIVE_FORWARD` keeps the pre-closure exposure line (path rules only, endpoint not read). A further exposure line records that the outcome was never consumed and the unit closed before outcome. Operational forward rows, if any were collected for other product purposes, are not a scientific score of this unit.

The evaluator `scripts/research/formation_width_activity_prospective_v1/evaluate.py` still raises `REFUSING_OUTCOME_BEFORE_OWNER_GO` and does not load a market panel. This closure does not run it.

## Product

`PRODUCT_INTEGRATION_CANDIDATE = NO`.

WIDTH does not enter the forecast layer, `/btc`, pushes, probability wording, activity decisions, product ranking, or the feature set. Production code is unchanged. The bot findings registry records the omission; it does not add a user-facing line.

## No successor

`NEXT_UNIT = NONE`.

This closure does not open BitMEX, another venue, another hour, another horizon, another activity threshold, a nonlinear WIDTH model, WIDTH interactions, a WIDTH subgroup, 2025/2026, E1, or a replacement prospective unit.

If WIDTH returns, that is a new owner decision from a new external basis. It is not a continuation of this line.
