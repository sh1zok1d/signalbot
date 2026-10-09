# FORMATION_WIDTH_ACTIVITY_BYBIT_FEASIBILITY_V1

`outcome_read = false`
`future_association_read = false`
`owner_go_required_for_outcome = true`
`mode = OUTCOME_BLIND_FEASIBILITY`

This unit asks one question: can the already pinned historical Bybit 5m series informationally test the exact frozen formation-width activity claim, without reading that claim's outcome?

It is not an execution of the confirmation. It is not a new discovery. It does not authorize an outcome read.

## Frozen claim

The claim stays the one selected by `FORMATION_WIDTH_REGIME_V1` and carried by `FORMATION_WIDTH_ACTIVITY_CONFIRMATION_V1`.

Relative width of the just-completed UTC formation hour has a positive monotone association with realized activity of the next hour, and that association remains after contemporaneous realized volatility of the same formation hour.

Discovery result SHA256 `333f5a778bf56207c3d6f8261d528a2d3271cdc523aba1239c3f013022466669`. Confirmation design `docs/research/FORMATION_WIDTH_ACTIVITY_CONFIRMATION_V1_DESIGN.md`. Practical bar `+0.10`. Sign positive. Primary statistic: partial Spearman of `V` with `ACTIVITY` given `RV_FORMATION`, average ranks, OLS with intercept, Pearson of residuals.

Nothing in that claim is retuned here. The statistic is named so the census can refuse to compute it. This file does not compute it.

## Historical-order decision, before any outcome

For this claim, historical candidate surface number 1 is Bybit. BitMEX is not in this unit. If the Bybit information forecast fails, the Bybit endpoint stays unread. This unit does not then open another historical surface. The next step is a separate owner decision: a prospective design, or a new historical unit if the owner asks for one.

## Exact surface

One series, taken from the repo pin, not chosen after an outcome.

| field | value |
| --- | --- |
| dataset | `LEVEL_CROSS_VENUE_PERP_5M_V0` |
| file | `bybit_btcusdt_linear_5m.csv.gz` |
| SHA256 | `f7ef739f7d359056cbbf78a77993995f54e3303e50775b5aadf36b4ba68f507c` |
| venue | Bybit |
| instrument | BTCUSDT |
| contract | linear USDT perpetual |
| interval | 5m OHLC |
| clock | public MT4 labels are UTC+3; the canonical `open_ms` is those labels minus 3 hours, so the stored opens are UTC |
| alignment | every stored open is divisible by 300000 ms |
| first open | `2020-03-31T21:00:00Z` |
| last open | `2024-12-31T20:55:00Z` |
| rows | 476254 |
| off-grid opens | 0 |
| bars at or after `2025-01-01` | 0 |
| gaps | 4 missing runs, 23714 absent bars, left missing |

Analysis dates are UTC `[2020-04-01, 2025-01-01)`. The grid starts `2020-03-31T00:00:00Z` so the 23:55 close before the first formation can sit on the grid. The series itself starts at 21:00 that day. No 2025/2026 object, no E1 bar, no product tape, no prospective panel.

There is no other pinned Bybit BTCUSDT linear 5m history in the atlas. Pre-2020 linear BTCUSDT is not in this pin. A later Bybit period would be 2025/2026, which this unit does not open.

## Exposure audit

The exact cell, partial Spearman of formation width with next-hour activity given formation-hour RV, has not been computed on this series.

The endpoint `ACTIVITY = RV_NEXT` of the UTC `[01:00, 02:00)` hour has not been consumed on this object.

Neighboring reads of the same canonical file, all on `PRICE_STRUCTURE.levels`, all `CONSUMED`:

- `LEVEL-CROSS-VENUE-REACTION-DISCOVERY-V1`: 15-minute Bybit close reaction as a cross-venue control into a 4h barrier.
- `LEVEL-SPOT-PERP-REACTION-DISCOVERY-V1`: the same series reused, not reminted.
- `LEVEL-ZONE-TRADED-ACTIVITY-DISCOVERY-V1`: the same series reused as the cross-perp close control. The traded-notional endpoint of that unit is Binance aggTrades, not this RV.

Exposure class: `SAME_CALENDAR_CROSS_VENUE_EXPOSED_REPLICATION`.

This is not `PRISTINE_CONFIRMATION`. Neighboring path questions on this file are already consumed.

This is not `TIME_DISJOINT_EXPOSED_SURFACE_REPLICATION`. The calendar `[2020-04-01, 2025-01-01)` sits inside the Binance discovery window `[2020-01-01, 2025-01-01)`. The venue differs. The hours do not. A later pass would be a same-era cross-venue replication, with less independence than a time-disjoint holdout. That limit is recorded now. It does not make the exact cell already consumed, so the information census is allowed. It does mean a later outcome, if one is ever authorized, cannot be called pristine or time-disjoint.

## Estimand the census prepares, and does not score

`V = (high − low) / P0` on the twelve 5m bars in UTC `[00:00, 01:00)`. `P0` is the 00:55 close. `T = 01:00` UTC.

`RV_FORMATION` uses closes `form−1` through `form+11`. `RV_NEXT` would use closes `form+11` through `form+23`. The census checks that those closes are finite and positive. It does not form the log returns and does not take the square root of a sum of squares.

An analysis row is a usable formation with both spans complete. The stability split, if a later read ever happens, is the calendar midpoint `2022-08-17T00:00:00Z`. This census only counts the two halves.

## Information rule, frozen before the census

The forecast function is the confirmation unit's function: lag-1 average-rank correlation of relative width, negative values set to 0, cap `0.95`, AR(1) inside each ISO week, Kish effective N, Fisher standard error `1/sqrt(n_eff − 3)`, normal power of the one-sided 95% lower bound at planted association `+0.10`. Bootstrap seed `20261108`, `B = 2000`, and quantile `0.05` stay the confirmation values. They are not refit after the Bybit counts.

Count floor, the same numbers as the confirmation design: analysis N `>= 500`, ISO weeks `>= 100`, each half N `>= 100`, lag pairs `>= 30`, width `p90/p10 >= 1.05`.

Route, first match:

1. Count floor fails: `INFORMATION_LIMITED_BEFORE_OUTCOME`.
2. Count floor holds and power is below `0.80`: `INFORMATIONALLY_WEAK_BEFORE_OUTCOME`.
3. Count floor holds and power is at least `0.80`: `INFORMATION_ADEQUATE_FOR_LATER_OUTCOME`.

`SURFACE_INELIGIBLE_BEFORE_OUTCOME` would have stopped the census if the exact cell were already consumed, or if the pin were not an exact 5m UTC OHLC grid. The audit above does not fire that route.

None of these routes is a pass or a fail of the claim.

`owner_go_required_for_outcome` stays true on every route. `outcome_read` stays false. `later_outcome_permitted_after_separate_go` is true only for `INFORMATION_ADEQUATE_FOR_LATER_OUTCOME`. A weak or limited route does not accept a later go inside this unit. No second venue is opened to repair the forecast.

## What this unit can say

It can say whether this Bybit series has enough outcome-blind support, under the frozen forecast, for a later one-cell read to be an informative test of `+0.10`.

It cannot say whether the association is present. A later adequate route would still need a separate owner go, and that go is not in this note. The strongest later wording, if that separate go ever happened and passed, would remain L2 on a same-calendar exposed cross-venue tape. L3 would still require prospective calibration. This feasibility note does not create either statement.
