# PRE_IMPULSE_STATE_ATLAS_V1 — design, frozen before the scan

Evidence class: `HISTORICAL_DIRECTIONAL_DISCOVERY / ADAPTIVE_SEARCH`.

Claim ceiling: `DISCOVERY_ONLY`.

Primary objective: `DISCOVER_DIRECTIONAL_PREDICTIVE_STATES`. The question is whether a state known at `T` carries information about the sign of the later return. A large range, a volatility forecast, or a context badge is not the target.

Governing principle, recorded before any feature is compared with an outcome:

> We do not demand a preselected effect magnitude from the market. We inspect a bounded, fully logged historical state space, characterize what systematically precedes directional movement, and then freeze separate successor hypotheses for independent testing. Effect magnitude and useful structure are outputs of discovery, not admission thresholds.

A discovery finding is not a confirmation. No cell in this pass becomes a product claim, a current probability, or an edge. `PRODUCT_INTEGRATION_CANDIDATE = NO` for the whole pass.

## Surface

`CORE_BTC_BINANCE_V0`, Binance USD-M BTCUSDT, complete 5-minute bars from the pinned 1-minute klines.

Decision times `T` satisfy `2020-01-01T00:00:00Z <= T < 2025-01-01T00:00:00Z`.

No bar whose open is at or after `2025-01-01T00:00:00Z` is read. The close of the bar that opens at `2024-12-31T23:55:00Z` may be used as a terminal price of a decision that itself is still in 2024. `2025/2026` objects are not opened. The E1 holdout is not opened.

Bybit and OKX enter only as already stored linear-perpetual 5-minute closes:

- `bybit_btcusdt_linear_5m.csv.gz`, SHA256 `f7ef739f7d359056cbbf78a77993995f54e3303e50775b5aadf36b4ba68f507c`
- `okx_btc_usdt_swap_5m.csv.gz`, SHA256 `b435fdec219df96e88e2ae4b65c04e16217af16f327aae36dca148d9203172a8`

Alignment is an exact `open_ms` match. A missing print stays missing. Nothing is carried forward. High, low, and open of those files are not used. No new download.

## What is not in the search

- Open interest. MARKET-01 and MARKET-02 already closed OI-expansion continuation on this surface. A stalled-price OI build is the same family. `OI_OPENED = false`.
- Level-engine structural levels. The level-reaction program already consumed touch, rejection, and acceptance on this path. Boundaries here are rolling highs and lows only.
- Funding. The funding line is closed on its own question.
- Spot versus perpetual basis. Not separately justified.
- BitMEX. Not opened.
- A 24-way hour-to-direction main effect is logged as a descriptive map and is not ranked. D12's claim is unsigned volume timing. Direction was outside that claim.

Flow is computed and logged. Both flow series are `eligible = false` with collision `COSMETIC_NEIGHBORHOOD_H05_B205`. They cannot enter the shortlist. H05 is taker imbalance to a later return. B2-05 is the absorption path on this tape. Scoring raw imbalance against a future return again would be a cosmetic rescue. The logged objects are the within-hour slope and correlation of the 5-minute return on taker imbalance, which is a response inside the past hour, not that retest. They stay ineligible anyway.

## Grid

The project already thins 5-minute event studies with a refractory gap, and it treats dependence in ISO-week blocks.

This pass uses 15-minute anchors and no second deletion. `T` is the close of a 5-minute bar, and `T` is divisible by 15 minutes. With the grid origin at `2020-01-01T00:00:00Z`, those bars are indexes `i` with `i % 3 == 2`. The first eligible index is `96`, so the prior 4-hour window and the recent 4-hour window both exist. Overlapping horizons are not treated as independent. The dependence unit for the weekly mean and for the bootstrap is the ISO week of `T`.

## Targets

For each anchor and each horizon `H` in `{1h, 4h, 8h, 24h}`:

`R_H = log(P[T+H] / P[T])`

`P[T]` is the close of the bar that closes at `T`. `P[T+H]` is the close of the bar that closes at `T+H`. The future bar's open must be before `2025-01-01`. No future price enters a feature.

`1h`, `4h`, and `8h` are the ranking horizons. `24h` is computed and logged and is not ranked.

There is no impulse threshold. Strong-move slices are descriptive. For each horizon, before the feature loop, the 10th and 90th percentiles of finite `R_H` are fixed. Bottom 10 percent is strong down, the middle is ordinary, top 10 percent is strong up. Those cuts are not moved after seeing a feature.

## Features

Every series below is past-only. A window that contains a missing bar is missing. A zero range makes a ratio missing. The near band is `0.15` of the window range. The speed distance is `1.0` times `RV_4h`. Neither number is tuned on outcomes.

Log-range is `log(max high) - log(min low)`. Realized volatility is the square root of the sum of squared 5-minute log returns. Distances are divided by the same window's high-low range. These are the scale-free forms. A second copy in raw price units is not built.

The identifier, the formula, the inputs, and the lookback are the dictionaries `FORMULA`, `INPUTS`, and `LOOKBACK` in `scripts/research/pre_impulse_state_atlas_v1/features.py`. The collision label is on each row of `FEATURES` in `constants.py`, assigned from the records below before any ranking.

Collision classes:

- `ADJACENT_VOLATILITY_DIFFERENT_ENDPOINT` — level of realized volatility or log-range. Prior volatility work did not ask this signed-return question. Eligible.
- `ADJACENT_FORMATION_WIDTH_DIFFERENT_ENDPOINT` — short-window versus long-window range or RV. Formation width was the completed UTC-hour width against next-hour activity. This is a rolling ratio against a signed return. Eligible.
- `ADJACENT_H03_DIFFERENT_FORMULATION` — path efficiency. Eligible.
- `ADJACENT_H02_B202_DIFFERENT_FORMULATION` — rolling-boundary pressure and acceptance. H02 was a 5-minute failed-breakout event with a 30-minute refractory, overshoot thresholds, and a mean-reversion endpoint, development verdict `H02_KILL`. B2-02 closed without promotion. The cells here are continuous dwell, distance, and extension on a 4-hour rolling range. Eligible, and labelled adjacent.
- `ADJACENT_H03_H04_DIFFERENT_FORMULATION` — countertrend path shares. Eligible, labelled adjacent.
- `NEW_LOCAL_GEOMETRY` — close location, sign changes, midpoint drift, traversal time, and candle geometry. Eligible.
- `ADJACENT_D9_M06_DIFFERENT_OBJECT` — perp-versus-perp 15-minute timing. D9 and MARKET-06 were spot lead-lag and absolute dislocation. Eligible, labelled adjacent.
- `ADJACENT_D12_DIFFERENT_ENDPOINT` — three predeclared states inside four UTC sessions. Eligible. The sessions are Asia `[0,7)`, Europe `[7,13)`, US `[13,21)`, late `[21,24)`. They are conventional labels, not a searched clock and not a Kyiv-hour magic number.
- `COSMETIC_NEIGHBORHOOD_H05_B205` — the two flow series. Not eligible.

Mirrored pairs are both computed. The expected relation is an opposite Spearman sign. The pass reports whether that happened. It does not keep the better side and drop the other.

## Statistics

Primary association: Spearman, Pearson correlation of tie-average ranks. The fast rank function must match `average_ranks`.

For every cell, also the mean of within-ISO-week Spearmans and its standard error. A week with fewer than 30 finite anchors, or a constant series, is skipped for that mean. The pooled Spearman remains the point.

Hour-adjusted Spearman uses `R` minus the mean of `R` inside the same UTC hour, computed on the cell sample. Session cells are still adjusted inside the session.

Feature quintiles use the fixed probabilities `0.2, 0.4, 0.6, 0.8`. If those edges are not strictly increasing, the quintile table is degenerate and the bin contrast is missing. The Spearman is still logged. Every bin reports N, `P(R>0)`, the mean signed return, and the median. `P(R=0)` is not up. The baseline rate is the cell's own rate.

The descriptive state used in the write-up is the top quintile when the Spearman is positive and the bottom quintile when it is negative. Both quintiles stay in the ledger. `ΔP` is `P(UP|state)` minus the cell baseline. The mean difference is the state mean minus the cell mean.

Outcome-slice means of the feature use the predeclared 10/90 cuts.

Discovery score, on raw Spearman, primary horizons, eligible series only:

`abs(Spearman) * year_sign_consistency * min(1, n_weeks / 100)`

`year_sign_consistency` is the fraction of calendar years with `N >= 200` whose Spearman has the same nonzero sign as the full sample. If the Spearman is missing or zero, or no year qualifies, the score is zero. There is no correlation floor and no probability-point floor.

`24h` is not scored into the ranking. Ineligible series are not scored into the ranking.

The top decile of absolute raw Spearman on primary eligible cells is checked against the hour-adjusted Spearman. A cell is flagged when the adjusted sign flips, the adjusted value is zero, or its absolute value is under half the raw absolute value. For the top 10 only, the same flag is applied to the partial Spearman of the feature and `R` given `rv_4h` (one covariate, the existing residual function, no ridge). A partial that is algebraically degenerate is recorded as degenerate.

Top 10 diagnostics, not gates: first half versus second half split at the median `T`, leave-one-year-out Spearman, and a week-block bootstrap. The bootstrap resamples the ISO weeks in the cell, `B = 1000`, seed `20261116`, quantiles `0.025` and `0.975`. Each draw recomputes the Spearman and the state contrast. The state side is locked from the full-sample sign. Seed `20261114` and seed `20261115` are not reused.

DST is a diagnostic split of the clock cells only: Europe/Kyiv offset `+3` versus `+2`. It is not an extra ranking cell.

## Ledger

Every feature, including the 12 session interactions, is crossed with every horizon and with both representations `SPEARMAN_RAW` and `SPEARMAN_HOUR_ADJUSTED`. Losers stay in the ledger. The ledger file is hashed after it is written. That digest is not written back into the ledger.

## Successors

Not executed in this unit. Preference is a different venue over the same years, then an older tape, then an untouched surface, then a prospective protocol.

Geometry, compression, boundary, acceptance, countertrend, speed, morphology, and clock: the recommended next tape is Bybit linear BTCUSDT, same formula. This pass does not compute those formulas on Bybit.

Cross-venue timing: the three venues are the discovery sample. Do not rerun them. Not `2025/2026`.

Flow: no successor.

## Stop line

One scan. If a result file exists, the runner returns `REFUSING_RERUN` before loading price. A bug found after that read stops the unit. The feature list, the band, the distance multiplier, and the score are not revised to improve a ranking.
