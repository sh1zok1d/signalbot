# FORMATION_WIDTH_REGIME_V1

**Status:** `DESIGN_FROZEN / OUTCOME_NOT_READ`. Date: 2026-10-09.

`MODE = DISCOVERY`. Tracks: `STRUCTURE` only. Claim ceiling: L2. Not `PRODUCT_EVIDENCE`. Not `EDGE`.

`outcome_read = false`. This note does not authorize a future-outcome read. A later owner go would be required.

This is not a rescue of `FUNDING_ANCHOR_OR_PERIODIC_RANGE_STRUCTURE`, not a restatement of +9.48 pp, and not a test of the sentence "a wide hour causes high volatility."

## Question

Is the width of one just-completed formation hour a PIT-safe description of the current market regime, and if it is, which predeclared class of later behaviour does it encode?

Two nested questions, both frozen:

1. **Foundation.** Does relative width have a monotone association with a predeclared future observable?
2. **Incremental.** Does that association remain after a simple past-only volatility baseline?

## Why this is not an already-tested object

Closed or exposed neighbours, and why they are not this estimand:

| Prior | What was measured | Why this is different |
| --- | --- | --- |
| H01 | Low recent-RV quantiles, then later RV. Compression persisted. | No RV quantile. No compression screen. The state is formation width. |
| B2-01 | A generic volatility-transition feature for forecast skill. Closed, not promoted. | No forecast loss. No threshold scan. |
| `LEVEL_VOLATILITY_TRANSITION_DISCOVERY_V1` | 60m RV after a structural first touch versus before that touch, real minus pseudo. | No level touch. No pseudo price. The population is every completed formation. |
| DH3-V2 `KEY_LEVEL_RANGE` | 4h log range after PD/PW/PM/POC touches versus random levels. | Not a level event and not a 4h range endpoint. |
| `PRODUCT-V2-RANGE` | Product corridor from recent ranges, clock, weekend, and events. Exposed diagnostic, not a research claim. | Not that model. No 2025/2026. No corridor. |
| `FROZEN_HOUR_RANGE` diagnosis | On the touch-paired cohort only, Spearman of `W/P0` with the next 4h RV was about +0.66 and with the next 4h range/`P0` about +0.57. The same width versus the previous hour's RV was about +0.67. Four clocks were described. | Those exact 4h associations are not recomputed. V1 does not condition on a later touch. The horizon is the next 60m. Partial association and directionless displacement were not estimated. |

Exposure class for a later outcome read: `EXPOSED_SURFACE_DISCOVERY`. The 60m activity cell is neighboring to the already-read 4h RV association, not a pristine discovery that width tracks volatility. Displacement and the partial association are unread. Fresh surfaces stay unused for a later confirmation.

## Object

One formation per UTC day. Anchor `UTC_00` only: bars `[00:00, 01:00)`. Twelve 5m bars. No other hour is estimated. `UTC_00` is the first completed hour of the UTC day, a daily state time. It is not a boundary candidate and not a search over 24 hours. The diagnosis already described the same width coupling at 00/08/12/16, so extra clocks would be dependent copies.

`T` is the close of the last formation bar (01:00 UTC). `P0` is that close. High and low are the max high and min low of the twelve bars. The hour is usable only when every formation bar is finite, high is at least low, width is positive, and `low < P0 < high`. After `T` the range is not a level to be touched.

## Width

One variable:

`V = (high − low) / P0`

Relative width is dimensionless and does not ride the BTC price level. Absolute dollar width, ATR scaling, realized-vol scaling, a z-score, and a percentile are not estimated. `log(V)` is the same rank transform as `V`, so it is not a second feature. `log(high/low)` and asymmetry are not in V1.

## Future horizon

One horizon: the next 60 minutes, twelve 5m log returns strictly after `T`.

The return ending at bar `j` is `log(close_j / close_{j−1})`. Future returns end on the twelve bars `[01:00, 02:00)`. They use closes from the formation close through 02:00. The formation hour's own returns are not in the future window.

4h is not used. It was the old barrier window, and the 4h RV and 4h range associations are already read on the paired cohort. Choosing 4h again would reanalyze that exposure. 60m is the formation's own length.

## Bounded map

Two future observables. Both are continuous. No terciles.

| Id | Observable | Class |
| --- | --- | --- |
| `ACTIVITY` | `RV_NEXT = sqrt(sum r_k^2)` on the twelve future returns | path variation |
| `DISPLACEMENT` | `abs(log(close_02:00 / P0))` | directionless net move |

High-low range over the same hour is not added. It is a near-copy of activity, and the 4h range association is already read. A thresholded "significant move" is not added. Signed return is not added: `V` has no direction, and a bullish or bearish split is not a V1 endpoint.

## Baseline

Past baseline, known before the formation starts and therefore at `T`:

`RV_PREV = sqrt(sum u_k^2)` on the twelve log returns of `[23:00, 00:00)` the previous UTC day. The last of those returns ends at 00:00. No formation bar enters `RV_PREV`.

Foundation comparator: Spearman rank correlation of `V` with the future observable, null of no monotone association. Not a rotated price range.

Incremental comparator: partial Spearman. Average ranks of `V`, of the future observable, and of `RV_PREV`. Residualize the first two on the third by OLS with an intercept. The coefficient is the Pearson correlation of those residuals. One covariate. No other feature.

The baseline does not residualize `V` on the formation hour's own RV. That would delete the contemporaneous state. See `CONTEMPORANEOUS_STATE_CONTROL_LESSON_V1.md`.

## Sample

Discovery surface: `CORE_BTC_BINANCE_V0`, events `[2020-01-01, 2025-01-01)`. Already consumed for other price questions. Not a pristine surface. No 2025, 2026, E1, BitMEX, spot 2017–2019, prospective, or product tape.

Analysis sample: usable formation, complete `RV_PREV`, and a complete future close path, on the same days for both questions. The first UTC day has no previous hour inside this surface and stays out. No fill.

Days are not treated as iid. The block is the ISO week of the formation date. `B = 2000`. One stream, seed `20261107`, redraws weeks with replacement and recomputes ranks inside each draw. Percentile intervals use `numpy.quantile` method `linear`. A cell is interpretable only if at least 90% of draws are finite.

Family correction, predeclared: two foundation cells, so a foundation clear uses the 0.0125 and 0.9875 percentiles. The two incremental cells use the same correction inside their own family. Foundation and incremental are nested questions, not four simultaneous candidates.

## Scales, stability, routes

A cell clears only if `|estimate| >= 0.10` and its family interval excludes 0. The 0.10 floor is not a target copied from the already-read 4h correlation.

Year Spearman is descriptive. A year counts if its analysis `N >= 100`. An endpoint is year-unstable if two such years have opposite signs.

Falsification, not a candidate: the same foundation Spearman of today's `V` with the previous analysis day's future observable. It cannot win. If its absolute value is at least the contemporaneous foundation absolute value, `interpretable_as_current_state = false`.

Information floor, outcome-blind: analysis `N >= 500` and at least 100 ISO weeks. Otherwise the later read stops at `INFORMATION_LIMITED`. A width distribution with `p90/p10 < 1.05` is degenerate and the same stop applies.

Route priority:

1. `INFORMATION_LIMITED`
2. `FORMATION_WIDTH_NO_DETECTABLE_FUTURE_STRUCTURE` if no foundation cell clears
3. `TEMPORALLY_UNSTABLE_WIDTH_RELATION` if every clearing foundation endpoint is year-unstable
4. `WIDTH_IS_REDUNDANT_WITH_PAST_VOLATILITY` if every year-stable clearing foundation endpoint fails its incremental cell
5. `FORMATION_WIDTH_REGIME_STRUCTURE_PRESENT` if at least one endpoint clears foundation, is year-stable, and clears its incremental cell

All four cells are reported. The largest cell is not selected after the fact. `interpretable_as_current_state = false` blocks calling the result a state at `T` even if a statistical route clears.

Search exposure: 1 width, 1 horizon, 2 outcomes, 2 questions, 4 inferential cells, 2 falsification cells, 5 year descriptions. No hour grid, no transform grid, no 2023 dummy.

## What a later go would launch

One outcome read of this frozen map on this surface, in this code, with `outcome_read` still false until that go. It would not open another surface, change the product, or start a forecast.
