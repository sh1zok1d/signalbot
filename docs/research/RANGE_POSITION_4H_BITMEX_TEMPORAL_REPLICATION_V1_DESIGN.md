# RANGE_POSITION_4H_BITMEX_TEMPORAL_REPLICATION_V1 — design (Unit A; frozen before any BitMEX outcome)

**Date:** 2026-10-09. **Author:** chief architect.
**Owner directive:** 2026-10-09, GO after the corrections this design implements.
**Mode:** `CONFIRMATION`, one shot. **Track:** `STRUCTURE`. **Rules:** `RESEARCH_RULES_DECISION_V1.md`.
**Evidence class:** `TEMPORAL_HISTORICAL_REPLICATION / ONE_SHOT`. The surface is `QUESTION_FRESH_REPLICATION` for this question. BitMEX 2016–19 has no DIRECTION cell in `EXPOSURE_COUNTERS_V1`.
**Claim ceiling:** historical only. Never a current probability. `PRODUCT_INTEGRATION_CANDIDATE = NO`. No fees, entries, stops or PnL.

**Parent chain (the object is kept exactly):**
1. **Discovery.** `PRE_IMPULSE_STATE_ATLAS_V1` (Cursor) on Binance USD-M BTCUSDT 2020–24.
   - It was an adaptive scan of 496 cells and remains discovery.
   - Its CORE × DIRECTION search exposure stays in the counters.
2. **Cross-venue successor.** `RANGE_POSITION_4H_INCREMENTAL_REPLICATION_V1` (Cursor) on Bybit linear 2020–24.
   - Route `RANGE_POSITION_INCREMENTAL_CROSS_VENUE_SUPPORTED`.
   - Design SHA256 `8132f181fd4ced19ee1c356a99022e195c005f0b2e95ac2135074ad7cc4c0e7d`, design commit `4c6c5583`.
3. **This unit** tests that successor's object, primary estimand, formulas, ranks, residualization and bootstrap on a different epoch.
   - Discovery strength is not a criterion here; BitMEX stands on its own data and the frozen estimand.
   - The parent formula and statistics code is vendored unchanged from `origin/cursor/range-position-4h-incremental-replication-v1-08d8`. Git blobs: `grid.py` `18112255083d4c04f2f316156782d0993266758f`, `stats.py` `a7aa21f4af5fa7f1f2c8655fb5dff84e633cffb2`, and `formation_width_regime_v1/amendment_a1.py` `2ef15dbcec1cba268ef87616c05d89b36e75e18f` (reference `average_ranks` / `partial_spearman` only).

**Not this unit:**
- Binance 2025–26 (Unit B, separate design review and separate owner go, only after this result);
- Binance spot 2017–19 (not opened);
- Bybit, Binance 2020–24;
- rejection or bars-since;
- other horizons;
- fees.

## Surface

**Data:**
- **File:** `docs/research_data/D2_BITMEX_PRE2020_XBTUSD/canonical_5m.jsonl.gz`.
- **SHA256:** `8e027433b528a8ee084a90690ff4b0c4f819d1f1b66c776d635cf466bd8e56fa`, as in `docs/research_data/D2_BITMEX_PRE2020_SOURCE_AUTHORITY.json`.
- **Source:** BitMEX REST `trade/bucketed` binSize=5m XBTUSD, `partial=false`. Parser `D2_BITMEX_PRE2020_PARSER_V1`: `open_time_ms` = official bucket end − 5 min.
- **Interval:** bar opens 2016-05-13T11:55:00Z … 2019-12-31T23:55:00Z, end exclusive 2020-01-01T00:00:00Z.
- **Instrument:** XBTUSD, an inverse perpetual. Prices are USD per BTC; log returns of that price.

**Missing-bar semantics — canonical, from the source authority and `scripts/research/d2_bitmex_pre2020.py`:**
- **Zero-trade buckets are valid bars.** `coverage.zero_trade_buckets_retained_as_official_source_bins = true` (22,728 buckets), and the parser comment reads "Zero-trade buckets remain present timestamps; they are not silently dropped". They are used exactly as published (OHLC as given). Neither repeated nor flat prices make a bar missing.
- **A bar is missing only when its timestamp is absent.** The authority documents exactly one gap: 288 opens, 2016-12-06T23:55:00Z … 2016-12-07T23:50:00Z (`missing_bucket_count = 288`, `missing_open_timestamps_sha256 = 5e94399d…`).
  - The grid leaves those slots NaN; nothing is filled.
  - An anchor whose 48-bar window, 4h return path or 1h target touches a missing slot is dropped.
- **Preflight refusal:** the run refuses unless the file SHA matches, open times are strictly increasing on the 5m grid, and the grid has exactly 288 holes at exactly those timestamps.

## Anchors

- **Phase:** the parent phase on the clock. A bar is an anchor bar when `((open_ms − 2020-01-01T00:00Z) / 5 min) mod 3 = 2`, with floor modulo, so the bar opens at minute ≡ 10 (mod 15) and T falls at :00/:15/:30/:45 UTC.
- **T:** the close of that bar. `T < 2020-01-01T00:00Z`.
- **Warm-up:** the parent's warm-up index (≥ 96 from 2020-01-01) is a 2020 grid property. Here it is replaced by its content: 48 complete slots before and including the anchor bar.
- **Target:** the target bar `i+12` opens before 2020-01-01.

## Formulas (parent, unchanged)

The grid holds BitMEX bars from the first open to the last; missing slots are NaN.
- **Window:** `W` = bars `i−47 … i` (closes in `(T−4h, T]`).
- **`RP4H(T) = (close[i] − min low(W)) / (max high(W) − min low(W))`:** requires every high, low and close in `W` finite, and the span finite and > 0.
- **`RET_4H(T) = log(close[i] / close[i−48])`.**
- **`RV_4H(T) = sqrt(Σ_{k=i−47..i} log(close[k]/close[k−1])²)`:** missing if any of those 48 returns is missing.
- **`R_1H(T) = log(close[i+12] / close[i])`.**
- **`RANGE_WIDTH_4H(T) = log max high(W) − log min low(W)`:** diagnostic.
- **Secondary-only controls:** `RET_1H = log(close[i] / close[i−12])` and `RET_15M = log(close[i] / close[i−3])`. Both lie inside the window path, so they are finite whenever the primary sample is.

**Analysis sample:** the anchors where `RP4H`, `RET_4H`, `RV_4H`, `RANGE_WIDTH_4H` and `R_1H` are all finite (the parent intersection). One sample for every estimand.

## Estimands

**Method (parent):**
- Average ranks with midranks (mergesort tie order).
- OLS residualization of the ranks with an intercept.
- Pearson correlation of the two residuals.
- A residual is degenerate if RSS ≤ 1e-12 · TSS or TSS = 0.
- **Parity gate:** the one-covariate point (given `RET_4H`) must match the reference `amendment_a1.partial_spearman` within 1e-8 before any route is written.

**Estimands:**
- **Raw:** Spearman(`RP4H`, `R_1H`).
- **PRIMARY:** partial Spearman(`RP4H`, `R_1H` | `RET_4H`, `RV_4H`), with covariate columns in that order.
- **Secondary 1 (parent secondary, not a route):** partial given `RET_4H` only, with `attenuation_by_ret = raw − secondary1` and `share_removed_by_ret`.
- **Secondary 2 (local-path robustness, not a route):** partial given `RET_4H`, `RV_4H`, `RET_1H`, `RET_15M`.
  - Reason, recorded before the outcome: on Bybit, `RET_4H` removed about half the raw association. The leading competing reading is a more local recent-path reversal.
  - It cannot cancel, replace or rescue the primary, and it is not chosen after the result.
- **Width diagnostic (point only, not a route):** Spearman(`RP4H`, `RANGE_WIDTH_4H`) and the partial given `RET_4H`, `RV_4H`, `RANGE_WIDTH_4H`.

## Uncertainty

- **Blocks:** the ISO week of T (UTC).
- **Resampling:** weeks with replacement, B = 2000, seed `20261117` (the parent seed), percentile interval 0.025 / 0.975 (`np.quantile`, default linear).
- **Recomputed in every draw, ranks included:** raw, primary, secondary 1, secondary 2.
- **Degenerate draws** are omitted from that interval.
- **Unavailable:** fewer than 1900 valid draws for raw or primary → `RANGE_POSITION_ESTIMATE_UNAVAILABLE`.

## Route (frozen; primary only; no magnitude threshold)

Evaluated in this order, discovery sign negative:

| # | Route | Rule |
|---|---|---|
| 0 | `RANGE_POSITION_ESTIMATE_UNAVAILABLE` | raw or primary point missing, or fewer than 1900 valid draws for either |
| 1 | `RANGE_POSITION_TEMPORAL_REPLICATION_SUPPORTED` | raw < 0, primary < 0, and the primary 95 % interval entirely below 0 |
| 2 | `RANGE_POSITION_RAW_REPLICATES_INCREMENTAL_UNCERTAIN` | raw < 0, raw interval entirely below 0, primary interval includes 0 |
| 3 | `RANGE_POSITION_TEMPORALLY_COMPATIBLE_BUT_UNCERTAIN` | raw < 0 and primary < 0, rows 1–2 not fired |
| 4 | `RANGE_POSITION_NOT_TEMPORALLY_REPLICATED` | every other case |

- Row 4 includes raw ≥ 0, a non-negative primary point without row 2, and a primary interval entirely above 0. The last case additionally carries the descriptive flag `INCREMENTAL_SIGN_OPPOSES`.
- The secondary estimands, the width diagnostic and the descriptions never enter the route.

## Description (no gate)

- **Quintiles of RP4H**, edges at the full-sample 0.2/0.4/0.6/0.8 quantiles (the parent code): N, P(`R_1H` > 0), mean and median `R_1H`. This is a description, not a rule. Expected-return utility is a later question.
- **Calendar year of T** and the median-T half split: raw and primary in each piece.

## What would change the reading

- **Supported:** the cross-venue successor's incremental relation also holds in 2016–19.
- **Raw replicates, incremental uncertain:** in this epoch the association is not separated from the recent signed 4h path.
- **Compatible but uncertain:** right signs, not resolved by this sample.
- **Not replicated:** the exact relation does not transfer to 2016–19.

There is no synthesis with any other epoch in this unit. A later synthesis reads recorded results only, with no new outcome read.

## Search exposure

- **Cells:** raw, primary and two secondaries on BITMEX_XBTUSD_2016_2019 × DIRECTION, added to `EXPOSURE_COUNTERS_V1` when read.
- **Fixed:** one object, one target, one horizon, one primary nuisance pair. No threshold, no window, horizon or venue variant.

## Execution

- **Code:** `scripts/research/rp4h_bitmex_temporal_v1/`, with tests on synthetic data, committed after this design.
- **The code refuses** if this file's SHA256 differs from the constant, if the series SHA or the gap census differs, or if a result exists.
- **Result:** `RANGE_POSITION_4H_BITMEX_TEMPORAL_REPLICATION_V1.json` / `.md`.
