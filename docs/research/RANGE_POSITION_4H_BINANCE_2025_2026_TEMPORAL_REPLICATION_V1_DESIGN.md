# RANGE_POSITION_4H_BINANCE_2025_2026_TEMPORAL_REPLICATION_V1 — design (Unit B; frozen before any outcome)

**Date:** 2026-10-09. **Author:** chief architect. **Owner instruction:** 2026-10-09 (prepare; do not run before the frozen preflight is shown and a GO is given).
**Mode:** `CONFIRMATION`, one shot. **Track:** `STRUCTURE`. **Rules:** `RESEARCH_RULES_DECISION_V1.md`.
**Evidence class:** `TEMPORAL_HISTORICAL_REPLICATION / ONE_SHOT`. The surface class for this question follows the exposure audit (§ Exposure).
**Claim ceiling:** historical only. Never a current probability. `PRODUCT_INTEGRATION_CANDIDATE = NO`. No fees, entries, stops or PnL.
**Replaces:** `RANGE_POSITION_4H_BINANCE_2025_2026_TEMPORAL_REPLICATION_V1_DESIGN_DRAFT.md`.

## Scientific identity

This is Unit A's object and estimand, unchanged:
- **Unit A:** `RANGE_POSITION_4H_BITMEX_TEMPORAL_REPLICATION_V1`, design SHA `d9caaadd…`, route `RANGE_POSITION_TEMPORAL_REPLICATION_SUPPORTED`.
- **Parent:** the Bybit successor `RANGE_POSITION_4H_INCREMENTAL_REPLICATION_V1`, design SHA `8132f181…`.

The code imports Unit A's shared functions and does not copy them:
- `parent.features`, `spearman`, `partial_rank`, `quintile_table`, `_interval`, `ref_partial_spearman`;
- `evaluate._bootstrap`, `_pieces`, `assign_route`;
- `grid.local_returns`.

Unit B has only its own data loader, grid bounds and constants.

**Fixed elements:**
- **Object:** `RP4H(T) = (close[i] − min low(W)) / (max high(W) − min low(W))`, with W = bars `i−47 … i` (closes in `(T−4h, T]`). Every bar in W present, and span > 0.
- **Target:** `R_1H = log(close[i+12] / close[i])`. The target bar opens before the surface end.
- **Primary nuisance set:**
  - `RET_4H = log(close[i] / close[i−48])`;
  - `RV_4H = sqrt(Σ_{k=i−47..i} log(close[k]/close[k−1])²)`.
- **Primary estimand:** partial Spearman(`RP4H`, `R_1H` | `RET_4H`, `RV_4H`).
- **Secondaries (not routes; the same as Unit A, so the results are comparable):**
  - partial given `RET_4H` only;
  - partial given `RET_4H`, `RV_4H`, `RET_1H`, `RET_15M`, with `RET_1H = log(close[i]/close[i−12])` and `RET_15M = log(close[i]/close[i−3])`.
- **Width diagnostic (point only):** as Unit A.
- **Anchors:** 15-minute. A bar is an anchor bar when `((open − 2020-01-01T00:00Z)/5 min) mod 3 = 2` (floor modulo), so T falls at :00/:15/:30/:45 UTC.
- **Sample:** where `RP4H`, `RET_4H`, `RV_4H`, `RANGE_WIDTH_4H` and `R_1H` are all finite. One sample for every estimand.
- **Method:**
  - midrank ranks, OLS residualization with an intercept, Pearson correlation of the residuals;
  - degeneracy at RSS ≤ 1e-12·TSS;
  - parity gate: the one-covariate point must match the reference within 1e-8.
- **Bootstrap:** ISO-week blocks of T, B = 2000, seed `20261117`, percentile 0.025/0.975, every estimand and its ranks recomputed per draw, at least 1900 valid draws.
- **Route:** Unit A's frozen order, with the same names.
  1. `RANGE_POSITION_ESTIMATE_UNAVAILABLE`;
  2. `RANGE_POSITION_TEMPORAL_REPLICATION_SUPPORTED`;
  3. `RANGE_POSITION_RAW_REPLICATES_INCREMENTAL_UNCERTAIN`;
  4. `RANGE_POSITION_TEMPORALLY_COMPATIBLE_BUT_UNCERTAIN`;
  5. `RANGE_POSITION_NOT_TEMPORALLY_REPLICATED`, with the flag `INCREMENTAL_SIGN_OPPOSES` where it applies.

  There is no magnitude threshold, and only the primary enters the route.
- **Description (no gate):** quintiles with full-sample quantile edges (N, P(UP), mean, median), calendar years, the median-T halves.
- **Excluded:** no new threshold, horizon, window, control or feature. Rejection, bars-since and spot are not read.

## Surface

**Data:**
- **Source:** Binance USD-M BTCUSDT perpetual, 5m klines from data.binance.vision.
- **Manifest:** `docs/research_data/RP4H_BINANCE_UM_BTCUSDT_5M_2025_2026_V0/MANIFEST.json`, object-list SHA256 `e7a4f7b426031a43581f3176ee21348753979178fdcfb072e3a7368a436809ed`.
  - 78 objects: monthly 2025-01 … 2026-07; daily 2026-08-01 … 2026-08-15 and 2026-08-26 … 2026-10-08.
  - Each object's SHA256 is taken from its published `.CHECKSUM` and pinned before any object body was downloaded.
  - Every downloaded object is verified against it.
- **Interval:** bar opens 2025-01-01T00:00:00Z … 2026-10-08T23:55:00Z, end exclusive 2026-10-09T00:00:00Z.
- **No warm-up before 2025-01-01:** the 2024 discovery surface is not read even for features. The first anchors are the first with 48 complete bars.
- **Open times:** microsecond open times in 2025+ archives are converted to ms.

**Missingness (the same semantics as Unit A):**
- Every published row is a bar, used as published.
- A bar is missing only when its timestamp is absent. Nothing is carried forward or interpolated.
- An anchor whose 48-bar window, 4h return path or 1h target touches a missing slot is dropped.
- **Refusals:** duplicate, off-grid or out-of-surface rows.
- **Census pin:** the hole census is pinned after the outcome-blind preflight. The run refuses if it differs.

## E1-RUN-001 window — pre-fixed rule (decided before any outcome)

**The window `[2026-08-16T00:00Z, 2026-08-25T17:20Z)` is excluded.** This is the canonical product rule (`beta.history_data.PROTECTED_WINDOWS`, `url_refusal`, `drop_protected`), imported and not re-implemented:
- **Objects:** any archive object whose period overlaps the window is refused before any request. The monthly 2026-08 object is never planned. The daily objects 2026-08-16 … 2026-08-25 are refused, the 25th whole, as in the product.
- **Rows:** any parsed row with an open inside the window would be dropped. The run refuses if one is present.
- **Anchors:** the refused days are absent timestamps, so an anchor whose window, path or target touches them is dropped by the missingness rule above.
- **Opening the window instead:** that would need a separate owner permit and an amended design before any outcome. It is not part of this design and cannot be decided after the result.

## Exposure (exact question RP4H → R_1H on this surface)

See `RANGE_POSITION_4H_BINANCE_2025_2026_EXPOSURE_AUDIT_V1.md`. Its summary is copied here at freeze.

EXPOSURE_SUMMARY_PENDING

## Information (before reading)

- About 646 days, minus the 10 refused days and holes.
- At most about 61,000 anchors over about 92 ISO weeks.
- Unit A had N 127,303 over 191 weeks. Expected SE of the primary here is about 1.4× Unit A's.

## What would change the reading

The routes read as in Unit A, for this epoch alone:
- **Supported:** the relation holds in 2025–26 after the signed 4h return and 4h volatility.
- **Raw only:** in this epoch it is not separated from the recent 4h path.
- **Compatible:** right signs, unresolved.
- **Not replicated:** it does not transfer to 2025–26.

There is no joint gate with Unit A. A later synthesis reads the recorded results only.

## Execution

- **Code:** `scripts/research/rp4h_binance_2025_2026_temporal_v1/`, with tests on synthetic data.
- **Commands:**
  - `preflight`: manifest, guard, object hashes, hole census; timestamps only, no price statistic.
  - `run --go`: the one shot. It refuses unless the design SHA and the census pins match, and if a result exists.
- **Result:** `RANGE_POSITION_4H_BINANCE_2025_2026_TEMPORAL_REPLICATION_V1.json` / `.md`.
- **Search exposure added when read:** raw, primary and two secondaries on BINANCE_PERP_BTC_2025_2026 × DIRECTION.
