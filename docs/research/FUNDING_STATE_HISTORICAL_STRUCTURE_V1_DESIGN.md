# FUNDING_STATE_HISTORICAL_STRUCTURE_V1

Design frozen before any future-path score. This file does not contain its own hash.

## Governing principle

Signalbot does not require the market to produce a preselected effect magnitude. We freeze observables, estimands, controls and anti-overfitting rules before reading outcomes. The market determines effect magnitude, sign and usefulness.

This unit does not use an effect-size floor, `rho >= +0.10`, a `+5` pp gate, an MAE-improvement floor, or the MARKET-03 funding percentile `55`. None of those is an external utility function for this question.

## Question

What historical structure does future adverse-path risk actually show as a function of funding state, and does that structure remain after a control for the current volatility state?

## Evidence class

`RETROSPECTIVE_HISTORICAL_STRUCTURE / AVAILABILITY_LIMITED`.

`fundingTime` and Vision `calc_time` are event or settlement clocks. They are not a proven publication time. `FUNDING_PUBLICATION_LATENCY_UNPROVEN` stays in force. This unit does not call the read a pristine out-of-sample or point-in-time confirmation. It still measures the historical relationship.

It does not execute MARKET-04, does not rewrite MARKET-04 or MARKET-04H, does not clear `B2-06`, and does not set `research_authorized` on the funding snapshot. It does not raise an evidence tier, does not create L3, and does not authorize a product change. `PRODUCT_INTEGRATION_CANDIDATE = NO`.

## Why this unit exists

MARKET-03 / `EmaCrossFunding` has canonical outcome `REPRODUCED_DIRECTION` on its frozen historical interval: the funding filter reduced maximum drawdown relative to the baseline strategy. That result is strategy-specific. It does not establish a universal funding rule, does not make percentile `55` a natural boundary, does not establish a current product risk signal, and does not establish a causal funding effect.

MARKET-03 is external motivation for the observable family funding / premium / leverage state. The population here is every settled funding event, not the EMA600 entry population.

## MARKET-04 estimand audit

`MARKET_04_CANDIDATE_SELECTION` (2026-09-19) froze a candidate, not a preregistration and not an execution.

- Question: does historically available funding state add incremental information about future adverse-path risk beyond a simple price / trend / volatility state?
- Role: `RISK_STATE_FILTER`. Not a direction predictor.
- Family: `FUTURE_ADVERSE_PATH_RISK`. PnL is not the outcome. Final-horizon return is not primary.
- Mechanism text: crowded or elevated funding may mark states in which long exposure has worse subsequent downside than the contemporaneous price and volatility state would imply.
- Allowable later forms, not chosen: future maximum adverse excursion; future minimum cumulative return from `T`; a predeclared lower-tail statistic.
- Horizon, exact metric, baseline formula, and uncertainty method were left to a later design. No numeric success threshold was created.
- Forbidden: inheriting threshold `55`, copying the author's 180-day percentile because it worked, and using the external strategy as the population.
- Availability audit: `FUNDING_HISTORICAL_AVAILABILITY_UNRESOLVED`. Settled funding is not usable for MARKET-04 under a strict `legal_available_at` rule. Status remains `BLOCKED_OBSERVABLE / NOT_TESTED`.
- MARKET-04H: premium-index klines are a funding-pressure proxy, not settled funding. `MARKET_04H_PREMIUM_OBSERVABLE_BLOCKED`. The archive is not materialized. `safe_usable_at` is unset. The child family name `FUTURE_CROWDING_SIDE_ADVERSE_PATH_RISK` was not given a formula.

This unit reuses the parent family and the long-exposure downside reading. It freezes the formula the parent left open. The only relaxation is the evidence class: retrospective historical structure instead of strict point-in-time confirmation. The two-sided crowding claim (negative funding implies upside stress) is not the primary. It is a descriptive sign split.

## Source audit, completed before any future path

### Settled funding that can be read

`B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0` Vision monthly `fundingRate` zips under `artifacts/research_data/.../raw/funding`.

- Schema: `calc_time`, `funding_interval_hours`, `last_funding_rate`.
- Meaning: settled-style historical funding rate. Not predicted funding. Not premium. Not `lastFundingRate` from the live premium index.
- `funding_interval_hours` is `8` on every row.
- Events: `4749`. Unique `calc_time`: `4749`. Duplicates: `0`. Missing 8-hour hour-floor slots from the first event to the last: `0`.
- First `calc_time`: `2020-09-01T00:00:00Z`. Last: `2024-12-31T16:00:00Z`.
- Millisecond residual after the UTC hour: `0` to `47`. Preserved. Not treated as publication latency. The decision clock is the hour floor.
- Raw rate sign on the full series: positive `4177`, negative `572`, zero `0`. Range about `-0.00119172` to `0.00248993`. These counts are properties of the funding series, not of a future price path.
- Checksum sidecars: `52`, one per zip.
- Open interest files in the same snapshot are not opened.

`research_authorized` on this snapshot stays false. Reading `last_funding_rate` here does not authorize B2-06.

### REST funding identity that is not readable as bytes

`MARKET_03_BINANCE_UM_BTCUSDT_FUNDINGRATE_REST_V0`.

- Endpoint: `GET /fapi/v1/fundingRate`. Fields: `fundingTime`, `fundingRate`.
- Request window `[2019-09-01T00:00:00Z, 2025-01-01T00:00:00Z)`.
- Materialized identity: `5819` rows, first `2019-09-10T08:00:00Z`, last `2024-12-31T16:00:00Z`, duplicates `0`, missing expected 8-hour slots `0`.
- Canonical JSONL SHA256 `e7885cd53407d70b4627d58b9abf2cdf5b26cdc7097a139eac2e454ad75944cb`.
- Raw bytes are gitignored and are not on disk (`IDENTITY_PROVEN_AT_MATERIALIZATION_RAW_BYTES_NOT_GIT_RETAINED`).
- This unit does not re-fetch REST. A new pull would not be the pinned bytes.

The readable settled series therefore starts at `2020-09-01`, not `2020-01-01`.

### Premium and mark

`BINANCE_UM_PREMIUM_MARK_INDEX_KLINES` is `ACQUIRABLE` and not materialized. No premium-index file is in the repository. Premium is not scored. It is not folded into a composite with funding.

### Price path

`CORE_BTC_BINANCE_V0` through the existing DH1 aggregation to complete 5-minute bins, open times in `[2020-01-01, 2025-01-01)`. A 5-minute low is the minimum of the underlying 1-minute lows, so the path extreme is kept. No bar at or after `2025-01-01` is read. The E1 holdout is outside this window and is not read. Product and live tables are not read.

## Canonical funding observable

One primary representation, chosen before the future path.

`FUNDING_STATE` is the past-only percentile rank of the settled `last_funding_rate`.

For event `i`, the past is the raw rates of events `0 .. i-1` only. The current rate is not inside the reference multiset.

```text
state = (1 + #{past < x} + 0.5 * #{past == x}) / (n_past + 1)
```

The rank is defined only when `n_past >= 90`. Ninety prior settlements are 30 days of the 8-hour clock. That floor makes the percentile a rank against a real past distribution. It is not the MARKET-03 180-day window, and it was not chosen by an outcome.

No other funding transform is inferential. The raw sign is used only to label the descriptive positive and negative sides.

## Decision time

`T` is the UTC hour floor of `calc_time`. On this snapshot that hour is `00:00`, `08:00`, or `16:00`.

`P0` is the close of the 5-minute bar that closes at `T` (open time `T - 5 min`).

The future window for horizon `H` is the 5-minute bars whose open times lie in `[T, T+H)`. Their lows are prices after `T` and at or before `T+H`.

`calc_time` is the settlement clock of the archive row. It is not asserted to be the public availability time. No delay of 1 second, 1 minute, or 5 minutes is invented. No future funding event enters the state.

## Primary outcome

Horizon `8h`, one funding interval, frozen before the score.

`ADVERSE_LONG_8H = max(0, -log(min low in the window / P0))`.

This is the long-exposure maximum adverse excursion in log price. A path that never prints below `P0` has adverse value `0`. The sign convention is: a larger value is more downside stress for a long position. A positive association with `FUNDING_STATE` means higher historical funding rank lines up with larger subsequent long-side downside. That is the MARKET-04 family, not a buy or sell instruction.

An event is dropped when the 8-hour window or the volatility window is incomplete, a price is non-positive, or the decision bar is missing. Dropped events are counted. They are not filled.

## Secondary outcomes

Same adverse definition, horizons `1h` and `4h`. Point estimates only. Not bootstrapped. Not route inputs.

One non-directional description at `8h`: the larger of the log rally and the log drop,

`max(|log(max high / P0)|, |log(min low / P0)|)`.

Point estimates only. Not a route input.

## Control

One contemporaneous volatility state. `RV_8H` is the square root of the sum of squared 5-minute log close-to-close returns over the 8 hours that end at `T` (96 returns). It uses closes at `T-8h, T-8h+5min, ..., T`. It does not use a price after `T`.

No trend feature, no open interest, no second volatility window.

## Statistics

Primary raw association: Pearson correlation of average ranks of `FUNDING_STATE` and `ADVERSE_LONG_8H` (Spearman, ties averaged).

Primary incremental association: the same partial Spearman used in formation-width amendment A1. Average ranks of state, adverse outcome, and `RV_8H`; OLS residuals of the first two on the third, with intercept; Pearson correlation of the residuals. One covariate. No ridge.

Positive incremental rho means that, after the current 8-hour realized volatility, a higher funding rank still lines up with larger long-side adverse excursion.

The route uses only the incremental point and its interval.

1. Interval not interpretable (fewer than 90 percent of draws finite): `INFERENCE_NOT_INTERPRETABLE`.
2. Point `> 0` and the interval lies entirely above `0`: `POSITIVE_INCREMENTAL_ADVERSE_ASSOCIATION`.
3. Point `< 0` and the interval lies entirely below `0`: `NEGATIVE_INCREMENTAL_ADVERSE_ASSOCIATION`.
4. Otherwise: `INCREMENTAL_ASSOCIATION_UNCERTAIN`.

A point of exact zero is not positive. There is no minimum magnitude. Bin means, yearly signs, the 1-hour and 4-hour horizons, the absolute excursion, and the sign split do not enter the route.

## Bootstrap

The estimand is the Spearman and the partial Spearman on the realized historical event sequence. The bootstrap resamples that sequence. It recomputes both statistics on each draw. It does not fit a trading rule and it does not search a cutoff.

Blocks are ISO weeks of `T` in UTC. Weeks are drawn with replacement. Events stay inside their week, so a larger week has more weight.

`B = 2000`. Generator `numpy.random.default_rng`. Seed `20261114`. Two-sided 95 percent, quantiles `0.025` and `0.975`, NumPy method `linear`. The same draws are used for the raw Spearman and the partial Spearman.

## Descriptive shape

Fixed cuts of `FUNDING_STATE`, not of the outcome:

- `[0, 0.10)`
- `[0.10, 0.25)`
- `[0.25, 0.75)`
- `[0.75, 0.90)`
- `[0.90, 1]`

Each bin reports its count and the mean adverse excursion at `8h`. Bins are not five hypotheses. A tail-only or non-monotone shape is a description. It is not promoted to a new primary claim inside this unit.

Calendar years of `T` report the raw Spearman, the partial Spearman, and `N`. Sign changes across years are reported. They are not an automatic fail and not an automatic pass.

Positive raw funding and negative raw funding are summarized separately with the same state and the same `8h` adverse outcome. A difference between sides is a candidate for a later design, not a claim chosen after the score.

## MARKET-03 language after the score

Allowed, and only as prose: consistent with, compatible with, may help explain.

Not allowed: proves the MARKET-03 mechanism, or funding caused the drawdown reduction.

## Product

This unit does not change `/btc`, pushes, probability wording, activity decisions, ranking, or the feature set. A historical association, if one appears, is not by itself a product risk line.

## Execution

The design, the state, the outcome, the control, the bootstrap, and the route are committed before the score. After the score they are not changed. An implementation bug found after the market path is read stops the unit.
