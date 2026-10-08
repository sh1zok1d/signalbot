# LEVEL_LIQUIDITY_STATE_DISCOVERY_V1 — design note

MODE = DISCOVERY

Family `LEVEL_BEHAVIOR_V1`. Tracks `STRUCTURE` + `PRODUCT_EVIDENCE`.

Owner go for this unit is the task that opened it. This note is the outcome-blind freeze. No resolution rate by book feature is computed here. The preflight census is `docs/research/LEVEL_LIQUIDITY_STATE_DISCOVERY_V1_PREFLIGHT.json`.

Claim ceiling: L2 historical association. Exposure status: `DISCOVERY_ONLY`. The Binance USD-M BTC bookDepth surface for 2023–2024 is already outcome-exposed by DH3-L and by the divergence book's ±5% support state. Nothing in this run is a confirmation. A historical frequency is not a current probability. Product files are not changed. `PRODUCT_INTEGRATION_CANDIDATE = NO` for this unit regardless of the routing word.

Honest name for the observable: `LOCAL_BOOK_STATE_AROUND_LEVEL_TOUCH`. The archive does not contain resting orders at the structural price.

## 1. Question

Which point-in-time states of observable order-book liquidity, measured immediately before the first touch of a confirmed structural level, if any, differ historically on whether that touch resolves within 4h and, among resolved touches, on BREAK versus REJECT?

This is a new information layer. It does not rework candles, open interest, taker flow, or their joint states. It does not assume that a large visible bid or ask rejects, or that a thin book breaks.

## 2. What is already established

`LEVEL_FIRST_TOUCH_RESOLUTION_CONFIRMATION_V1` replicated, on BitMEX 2017–2019, that a real structural first touch resolves into BREAK or REJECT within 4h more often than the matched pseudo-price: Δ RESOLVE = +8.0 pp, 95% +4.4..+11.8.

Later discovery on Binance did not find a robust incremental account of that resolution in static level properties, approach geometry, open interest alone, taker flow alone, or the joint OI / taker / price state. Those nulls are not rescued here. No threshold, window, FDR level, or 3 pp scale from those units is loosened.

## 3. Novelty audit

Closed book cells, and why this unit is not a reopen of them:

| Closed object | Population | Function | Endpoint |
|---|---|---|---|
| DH3-L1 `THIN_BOOK` | all hours, six coins, 2023–2024 | ±1% total notional in the bottom quintile of its trailing 7-day median | next 4h log range |
| DH3-L2 `BID_HEAVY_BOOK` | all hours, extreme quintiles | log(bid −1% / ask +1%), top versus bottom quintile | up first within 4h |
| DH3-L3 `BOOK_NOT_RECOVERED` | after a DH1 sharp move | ±1% notional 30 min after the move, relative to before, bottom tercile | next 4h log range |
| SEED-0001 / divergence support | confirmed swing or divergence episodes | ±5% bid/ask imbalance as a binary support state | reversal bracket |
| DH3-X9 | never run | ±5% imbalance at support | direction; closed at red team as a functional relabel of SEED-0001 |

This unit's object is the pre-touch local liquidity configuration on the structural first-touch event:

1. Population: first touches only of PDH, PDL, PWH, PWL, PMH, PML on BTC. Not all hours. Not a post-move hour. Not a divergence episode.
2. Orientation: ahead and behind the structural level, using the #352 approach side. Not absolute bid-heavy versus ask-heavy.
3. Timing: the last legal snapshot strictly before the touch open, and one comparison snapshot at or before T − 60m. Not a 7-day median. Not a 30-minute recovery lag.
4. Endpoint: `RESOLVE_4H` and `BREAK_GIVEN_RESOLVED`. Not range. Not up-first.
5. Control: the #352 half-rotation pseudo-price. Book features are read at that pseudo time. The pseudo price is not moved by the book.
6. Form: continuous features, +1 SD in a linear probability model. Not a thin-book quintile, a bid-heavy quintile, or an ask-heavy quintile.

The ±1% band is used because it is the narrowest native band in the file, not because DH3 used a ±1% quintile. Switching to ±2% or ±5% to look different would be a parameter dodge and is not done. The ±5% binary support state is not constructed. No RSI, divergence detector, or SEED-0001 arm is used.

Atlas row for the unit, when it is registered after the one run, is `PRICE_STRUCTURE.levels`, because the event is the replicated first-touch resolution. The book dataset is a covariate. Reopen key relative to DH3-L1/L2/L3 and to SEED-0001: `NEW_MECHANISM`. This is not `CONFIRMATION_ON_EXPOSED`. The book surface stays consumed for microstructure questions; this run adds discovery exposure of local book state at structural first touches.

Verdict of the audit: not `BLOCKED_REOPENING_EXISTING_BOOK_CELL`.

## 4. Book observability

Dataset `DH3_BINANCE_UM_BOOKDEPTH_V0`. Inventory `docs/research_data/DH3_BINANCE_UM_BOOKDEPTH_V0/SOURCE_INVENTORY.json`. Object-list SHA256 `c53fc179d922f83b572703d52e80f847fb54531961ac776929f2e3e95feeddce`. Source `https://data.binance.vision/` daily `bookDepth` zips. Instrument: Binance USD-M BTCUSDT only. Days 2023-01-01..2024-12-31. No object at or after 2025-01-01 is requested.

Schema, read from the pinned zips rather than from the DH3 ±1% grid reduction:

- Columns: `timestamp`, `percentage`, `depth`, `notional`.
- `timestamp` is a naive `YYYY-MM-DD HH:MM:SS` stamp. It is interpreted as UTC. There is no separate publication-delay field. `available_at` is that timestamp. A zoned stamp is refused.
- `percentage` is the cumulative band around the contemporaneous mid. The native set on every verified BTC day loaded here is −5, −4, −3, −2, −1, +1, +2, +3, +4, +5. No fractional band and no band inside ±1% appeared. A narrower band would have stopped the run before outcomes.
- Negative percentage is the bid side. Positive percentage is the ask side. Both `depth` (base quantity) and `notional` (USDT) are cumulative within that percent of mid, not a price-level ladder and not a shell between bands.
- This unit uses USDT notional at exactly ±1%. That is the narrowest reliable native band. Wider bands are not differenced into a fake ladder.
- There is no best bid, best ask, or midpoint column. The structural level price is not a book coordinate.
- Snapshots are exchange-native rows inside the daily zip. DH3's 5-minute grid is a derived view and is not the input here.
- Revisions are the pinned SHA256 of each zip. The loader checks the object-list digest and each zip digest.
- BTC: 728 verified days, 3 missing days (`2023-02-08`, `2023-02-09`, `2024-04-18`). Loaded snapshots: 2,068,585, all with both ±1% sides nonnegative. First stamp 2023-01-01 00:06:05Z. Last stamp 2024-12-31 23:59:31Z.
- Cadence on two complete days, read before any event join: 2023-01-01 median gap 29s, maximum 44s; 2024-12-31 median gap 30s, maximum 47s. Full-series median gap 30s, 99th percentile 38s. The maximum gap is about 70 hours because missing and sparse days are real holes. There are 223 successive gaps longer than 90s. Those holes are not filled.

Observability verdict: the file can support depth ahead of the approach, depth behind the approach, total local depth inside ±1% of mid, and the change of those three quantities between two legal snapshots. It cannot support orders at the level, a 10 bp concentration, a wall, a pocket, or a thin zone behind the level. Those quantities are not invented. The scientific run is allowed under the local-book name above. It is not `LEVEL_LIQUIDITY_OBSERVABILITY_INSUFFICIENT`.

## 5. Event window and cohort

Price geometry is imported from `LEVEL_TOUCH_DEGRADATION_V1` (`build_population`, zone half 0.0015, level kinds, touch, first touch, approach side, barrier X). It is not re-implemented.

`T` is the open time of the touch bar. Book features use snapshots strictly before `T`. The touch bar's high, low, and close are not book inputs and are not in the quote-volume window.

Event window: `[2023-01-01T02:00:00Z, 2025-01-01T00:00:00Z)`. The start is one round hour after the archive's first hour, so the 60-minute comparison can fall inside the archive. It was not chosen from a resolution rate. The price series still ends before 2025-01-01, so a touch whose 4h path is incomplete stays out through the parent `window_ok_48` flag.

Cohort: touch number 1 only, approach side ±1, finite parent sigma, usable X, level index `j >= i0`. Preflight, before any barrier label: 4,076 structural episodes; 790 geometry-legitimate first touches inside the window; 1,162 first touches outside the window; 397 pairs in which the matched pseudo first touch is also geometry-legitimate inside the window. Nuisance is complete on all 790. Book-legal rows: 767. Weeks among nuisance-complete rows: 106.

Half-year counts on the nuisance-complete rows: 2023H1 202, 2023H2 189, 2024H1 200, 2024H2 199. Families: DAY 671, WEEK 103, MONTH 16. Sides: resistance (side +1) 432, support (side −1) 358. There are not five calendar years of book data, and the design does not pretend there are.

## 6. Snapshot rule

Current snapshot: the latest snapshot with `snapshot_time < T` and `0 < T − snapshot_time ≤ 90_000` ms, both sides finite and nonnegative.

Comparison snapshot: the latest snapshot with `snapshot_time ≤ T − 60m` and `0 ≤ (T − 60m) − snapshot_time ≤ 90_000` ms, same side check.

Maximum staleness is 90 seconds: three nominal 30-second intervals. It was frozen from the complete-day cadence above, not from DH3's 10-minute grid alignment, and not from the outcome. A malformed snapshot is skipped. The walk stops when the next older snapshot is outside 90 seconds. That older snapshot is not copied across the gap.

If either snapshot is missing, the event is book-unavailable. Preflight: 20 legitimate touches have no legal current snapshot, 3 more have no legal comparison snapshot, 767 are `OK`. On those 767, the current snapshot's age has median 29s and maximum 89s. No zero notional occurred on the legal rows, so the log-ratio rule below is the one that applies; a zero would have been unavailable rather than replaced by an epsilon.

The only comparison lag is 60 minutes. Lags of 5, 15, 30 minutes and of 2 or 4 hours are not estimated, including after the result.

## 7. Features

Approach side `d` is the #352 side. `d = +1` is an approach from below. Ahead is the ask notional within +1% of mid: the visible size on the side price would have to trade through to continue past a resistance-like touch. `d = −1` is an approach from above. Ahead is the bid notional within −1% of mid. Behind is the other side. This is book geometry. It is not a long or a short, and it is not a claim that the level is strong.

Retained, all five. The predictor-only redundancy audit found no pair with `|ρ| ≥ 0.90` and no degenerate column. The largest correlation is 0.780 between the ahead-depth change and the total-depth change. Nothing was dropped. Simplicity order, had a pair crossed 0.90, would have kept the earlier name in this list:

1. `TOTAL_LOCAL_DEPTH` = bid notional at −1% plus ask notional at +1%, on the current snapshot. Positive total only.
2. `ORIENTED_DEPTH_IMBALANCE` = `(ahead − behind) / (ahead + behind)`. Positive means more visible notional ahead of the approach than behind it.
3. `AHEAD_DEPTH_CHANGE_60M` = `log(ahead_now / ahead_60m)`. Positive means visible ahead notional increased. If either value is ≤ 0, the feature is missing.
4. `BEHIND_DEPTH_CHANGE_60M` = the same log ratio on the behind side.
5. `TOTAL_DEPTH_CHANGE_60M` = `log(total_now / total_60m)`, same zero rule.

No level-strength score, wall score, pressure score, or book-support score is built. No KMeans and no combined state. If more than one dimension is associated with an outcome, a later unit may combine them. This unit does not.

## 8. Scaling, outcomes, nuisance, estimator

Scaling, frozen before outcomes and stored in the preflight: standard z, `(x − mean) / sd`, population sd (`ddof = 0`), plus tertile cuts at the empirical 1/3 and 2/3 quantiles for the shape table only. The same rule as `LEVEL_POSITIONING_FLOW_DISCOVERY_V1`. Each book feature's moments are taken on the nuisance-complete rows where that feature is finite. Displacement and relative-volume moments are taken on all nuisance-complete rows. Moments are not refit after ambiguous labels are dropped, and they are not refit inside an epoch.

Primary outcomes, same two-stage model as #358 and #359:

- `RESOLVE_4H`: 1 if BREAK or REJECT, 0 if NEITHER. AMBIGUOUS is excluded.
- `BREAK_GIVEN_RESOLVED`: 1 if BREAK, 0 if REJECT. NEITHER and AMBIGUOUS are excluded.

Labels come from the parent `classify` on bars `j+1 .. j+48`. The touch bar is outside that window.

Primary family: 5 features × 2 outcomes = 10 cells. Estimand: adjusted historical probability change per +1 SD. Estimator: linear probability model. No machine learning.

Nuisance, and not the book features again: level family (DAY reference), support versus resistance, half-year epoch (2023H1 reference), parent volatility tercile (the #352 cuts, not refit), UTC six-hour block, oriented 60-minute price displacement, and relative quote volume on the prior 12 bars against the prior 24h. Displacement is `d × log(close of the bar that ends at T / open of the bar that opens at T−60m)`. Quote volume does not include the touch bar. Taker flow and open interest are not in the model: the question is the incremental information in the book layer, and those series already had their own discovery units.

Cluster is the product week of the real touch. Bootstrap: 2,000 draws, seed `20261016`, percentile 95% interval. In the stacked regression the real row and its pseudo row share the real touch's week, so a draw keeps the pair together. Benjamini–Hochberg q = 0.10 on the 10 primary cells only. Practical scale: 3 percentage points per +1 SD. Not lowered after the result. Not the DH1 bar of 3 pp plus a Brier skill score.

Slices (epoch, family, side, leave-one-epoch-out, leave-one-family-out) are point estimates without a second bootstrap and without a second FDR. Shape tertiles are descriptive. A U-shape or other non-monotone pattern is recorded as `EXPLORATORY_SUCCESSOR_IDEA`. No threshold child is fit in this run.

## 9. Pseudo specificity

The pseudo touch is the parent half-rotation inside `(family, struct_side)`. Its decision time is its own touch open. The same snapshot rule and the same formulas are applied. The book is not an input to the rotation.

Sequence: a feature must pass the real-cohort conjunction before specificity can name it. A large real-minus-pseudo contrast does not rescue a null real effect.

For a cell that passed, the stacked model estimates `β_pseudo` on the feature, `β_real = β_pseudo + Δ`, and `Δ = β_real − β_pseudo`.

- `LEVEL_LIQUIDITY_INTERACTION_CANDIDATE`: `|Δ| ≥ 0.03`, the 95% interval for Δ excludes 0, `|β_real| > |β_pseudo|`, and the real slope, the stacked real slope, and Δ share a sign. Reading: the association is larger at the structural event than at the matched pseudo-price.
- `GENERIC_LIQUIDITY_STATE_CANDIDATE`: not material, same sign, and `|β_pseudo| ≥ 0.5 × |β_real|`. Reading: a general BTC liquidity association, not specific to the structural price.
- Otherwise `SPECIFICITY_UNRESOLVED`. That cell is not a candidate. The route treats it as `STRUCTURE_PRESENT_BUT_UNSTABLE` because the association cannot be assigned to either candidate class. This mapping is frozen here, before outcomes.

Neither label is a current probability.

## 10. Candidate conjunction

All of the following, on the real cohort, for a cell to be eligible for a specificity label:

1. Benjamini–Hochberg q ≤ 0.10.
2. Absolute effect ≥ 3 pp per +1 SD.
3. The 95% interval excludes 0.
4. Among half-year epochs with N ≥ 30, at least 3 exist and every one of them has the same sign as the primary coefficient.
5. Every leave-one-epoch-out refit with N ≥ 30 keeps that sign.
6. Every leave-one-family-out refit with N ≥ 30 keeps that sign. A complement below N = 30 is reported and does not by itself fail the cell. There is no 70% DAY ceiling.
7. If both support and resistance have N ≥ 30, their coefficients are not opposite in sign. A side below N = 30 does not fail the cell. No side-specific candidate is created after the result.
8. No point-in-time, staleness, or sign-of-data failure. The loader's fail-closed rules are the implementation of this clause.

`SUCCESSOR_CANDIDATE` stays `NONE` even if a cell is named. No combined liquidity state, no OI-by-book interaction, no taker-by-book interaction, no liquidation map, no cross-venue or spot book, no 2025/2026 read, no confirmation, and no level-strength score is started from this run.

## 11. Information

On 767 book-legal first touches and 106 weeks, a Bernoulli upper bound with the parent planning design effect 1.25 gives a standard error of about 2.0 pp per +1 SD and a rough 80% MDE of about 5.7 pp. A 3 pp effect can be estimated, and the interval around it can easily include both 0 and 3 pp. That number is context. It is not a pass/fail gate and it does not stop the run. `INFORMATION_LIMITED` is used only if, after the run, the largest RESOLVE cell has N < 100 or fewer than 20 week clusters and no other route applies.

## 12. Search exposure and no-rescue rules

Counted before outcomes, for 5 retained features: 10 primary cells, 10 shape tables, 10 pseudo slopes, 10 specificity contrasts, epoch/family/side slices, 4 leave-one-epoch-out refits per cell, 3 leave-one-family-out refits per cell. Interactions: 0. Extra windows: 0. DH3 quintiles: 0. Clusters: 0.

One official outcome run. The evaluator refuses a second run once the result files exist. After the result, none of the following change: feature list, band, staleness, threshold, window, snapshot rule, an extra book metric, the outcomes, the FDR level, or the 3 pp scale.

## 13. Routing words

`LEVEL_LIQUIDITY_STRUCTURE_PRESENT` — one or more interaction candidates.

`GENERIC_LIQUIDITY_STATE_ONLY` — a real conjunction passed and the pseudo association is comparable, and no interaction candidate exists.

`STRUCTURE_PRESENT_BUT_UNSTABLE` — a real cell clears q, scale, and the interval, but fails the stability clauses; or the real conjunction passed and specificity is unresolved.

`NO_INCREMENTAL_LEVEL_LIQUIDITY_STRUCTURE` — no retained book dimension meets the real rule, and the sample is large enough that this is a null rather than an empty cell.

`INFORMATION_LIMITED` — the estimation sample is below the predeclared floor and no cell was named.

`LEVEL_LIQUIDITY_OBSERVABILITY_INSUFFICIENT` and `BLOCKED_REOPENING_EXISTING_BOOK_CELL` were the pre-outcome stops. Neither applies.

## 14. What this note does not do

It does not edit #352–#359, DH3, or SEED-0001. It does not open 2025/2026 or the E1 holdout. It does not read funding. It does not change `/btc`, `/levels`, `/check`, `/risk`, Telegram, config, the findings registry, scoring, or deployment.
