# OCC_MEAN_4H_TEMPORAL_REPLICATION_V1 — design (frozen before any outcome)

**Date:** 2026-10-09. **Author:** chief architect. **Owner GO:** 2026-10-09 (this unit only; preflight first, then a separate GO for the outcome).
**Mode:** `CONFIRMATION`, one shot. **Evidence class:** `HISTORICAL_TEMPORAL_REPLICATION / QUESTION_FRESH_REPLICATION`.
**Claim ceiling:** historical only. Never a current probability. `PRODUCT_INTEGRATION_CANDIDATE = NO`. No fees, entries or PnL.
**Rules:** `RESEARCH_RULES_DECISION_V1.md`, `EVIDENCE_AND_CLAIMS_DECISION_V1.md`.

## 1. Question

Does the directional information of `OCC_MEAN_4H` replicate on a time-independent surface? And does it remain after an explicit control of the short local path (reversal)?

## 2. Parent (discovery; recorded, not recomputed)

- **Parent:** `DIRECTIONAL_STATE_SEARCH_V2`, object F2a.
  - Design `99205a3a` (SHA256 `a361ff35…2c52`); result JSON SHA256 `25e67a16…3389`.
  - It was the only object that cleared the search bar; TOP 3 = {F2a} by the frozen rule.
- **Discovery estimate** (Binance USD-M BTCUSDT 2020–24, CORE): partial Spearman(OCC_MEAN_4H, R_1H | RP4H, RET_4H, RV_4H) = **+0.0202 [+0.0130, +0.0277]**, z 5.31, N 175,292, 262 weeks.
  - Sign +: at the same range position, the next hour was more often up when price had lived higher in the 4h box.
- **The local-path-controlled discovery point was never computed.** Owner instruction: it stays uncomputed. The discovery surface is not touched by this unit.
- **Why the local path is decisive:** after the run, an outcome-blind feature check on CORE gave partial(OCC, RET_1H | B0) ≈ −0.42.

## 3. Surface

- **File:** `docs/research_data/D2_BITMEX_PRE2020_XBTUSD/canonical_5m.jsonl.gz`, SHA256 `8e027433b528a8ee084a90690ff4b0c4f819d1f1b66c776d635cf466bd8e56fa` (source authority `D2_BITMEX_PRE2020_SOURCE_AUTHORITY.json`).
  - BitMEX REST `trade/bucketed` 5m XBTUSD, `partial=false`.
  - Bar opens 2016-05-13T11:55Z … 2019-12-31T23:55Z, end exclusive 2020-01-01.
  - Inverse perpetual; prices are USD per BTC; log returns of that price.
- **Missingness: canonical D2 semantics, exactly as Unit A.**
  - Zero-trade buckets are bars (22,728), used as published.
  - A bar is missing only when its timestamp is absent: the one documented gap of 288 opens, 2016-12-06T23:55Z … 2016-12-07T23:50Z. Nothing is filled.
  - The run refuses unless the SHA, the bounds and that exact gap census match (`rp4h_bitmex_temporal_v1.grid.preflight_census`, imported).
- **Exposure audit:** §9.

## 4. Object (the discovery definition F2a, literally)

The discovery function `directional_state_search_v2.features.occupancy` is imported and used unchanged.
- **Anchor bar i; T = close of bar i.**
- **Box** = the RP4H box: H = max high and L = min low over bars i−47 … i (48 bars, the current bar included). Every high, low and close in the box must be present.
- **Zero range:** span = H − L ≤ 0, or not finite, makes OCC undefined (NaN). Same as discovery.
- **p_k = (close_k − L) / (H − L)** for the 47 closes k = i−47 … i−1. The current close (RP4H itself) is excluded.
- **`OCC_MEAN_4H = mean(p_k)`**, i.e. **(SMA₄₇ − L) / (H − L)**, where SMA₄₇ is the arithmetic mean of the 47 prior closes: the box position of the 4h simple mean of closes.
- **Anchors:** the RP4H 15-minute phase, `((open − 2020-01-01T00:00Z)/5 min) mod 3 = 2` (floor modulo), so T falls at :00/:15/:30/:45 UTC.
- **Target:** `R_1H = log(close[i+12] / close[i])`. The target bar must be present and open before 2020-01-01.
- **Sample:** Unit A's canonical BitMEX sample (RP4H, RET_4H, RV_4H, width and R_1H finite), imported. OCC is finite on every row by construction (same box), and the run refuses otherwise.
  - The discovery's program-level warm-up (i ≥ 288 from 2020-01-01) existed for its 24h states. It is not part of OCC and is not carried over.
  - One sample is used for every estimand.

## 5. Controls

- **B0** (as in discovery) = { `RP4H = (close_i − L)/(H − L)`, `RET_4H = log(close_i/close_{i−48})`, `RV_4H = √Σ_{k=i−47..i} log(close_k/close_{k−1})²` }.
- **B1** = B0 ∪ { `RET_1H = log(close_i/close_{i−12})`, `RET_15M = log(close_i/close_{i−3})` }: the Unit A/B local-path set.

## 6. Estimands

All estimands use midranks, OLS residualization with an intercept on the control ranks, and the Pearson correlation of the residuals. This is the RP4H parent code, imported.

| name | estimand | role |
|---|---|---|
| raw | Spearman(OCC, R_1H) | diagnostic |
| Secondary A | partial(OCC, R_1H \| B0) | parity with discovery; decides LOCAL_PATH vs NOT |
| Secondary B | partial(OCC, R_1H \| B0 + RET_1H) | how much one hour removes |
| **PRIMARY** | **partial(OCC, R_1H \| B1 = B0 + RET_1H + RET_15M)** | **the only route input for SUPPORTED** |

No other return, lag, TWAP or EMA residual, RSI, lag grid, variant, horizon or interaction.

## 7. Uncertainty (the canonical RP4H contract)

- ISO-week blocks of T, resampled with replacement.
- B = 2000; seed `20261117`.
- Every estimand and its ranks are recomputed per draw.
- Percentile 2.5 / 97.5.
- At least 1,900 valid draws for PRIMARY and Secondary A, otherwise the route is `OCC_IMPLEMENTATION_INVALID`.

## 8. Routes (frozen order; no magnitude threshold; discovery sign +)

1. **`OCC_IMPLEMENTATION_INVALID`:** provenance, support, parity or valid-draw failure. That covers a series SHA or gap-census mismatch, OCC not finite on the sample, support ≠ pinned N/weeks, a missing PRIMARY or Secondary A point, or fewer than 1,900 valid draws.
2. **`OCC_TEMPORAL_REPLICATION_INCREMENTAL_SUPPORTED`:** PRIMARY point > 0 and the PRIMARY 95 % interval entirely > 0.
3. **`OCC_REPLICATES_BUT_LOCAL_PATH_EXPLAINS`:** PRIMARY not supported, while Secondary A point > 0 and its interval entirely > 0.
   - Flag `PRIMARY_SIGN_OPPOSES` if the PRIMARY interval is entirely < 0.
4. **`OCC_NOT_TEMPORALLY_REPLICATED`:** otherwise; Secondary A does not reproduce.
   - Same flag rule.

**Reading:**
- **SUPPORTED:** OCC becomes `SECOND_INDEPENDENT_DIRECTIONAL_STATE_CANDIDATE`, not yet a forecast-engine component.
- **LOCAL_PATH_EXPLAINS:** the discovery mainly captured short-term reversal / deviation from the recent mean rather than a distinct state. This is a useful negative, and it is not rescued with encodings or windows.
- **NOT_TEMPORALLY_REPLICATED:** the relation does not transfer to 2016–19.

## 9. Exact exposure audit (before freeze)

AUDIT_PLACEHOLDER

## 10. Mathematical identity audit (outcome-blind)

- **Exact algebra:** `OCC = (SMA₄₇ − L)/(H − L)` and **`OCC − RP4H = −(close_i − SMA₄₇)/(H − L)`**.
  - Given RP4H, OCC is an affine function of the close's deviation from its 4h simple moving average of prior closes, in units of the 4h range.
  - So OCC is algebraically a close-vs-average object, with the average taken over the 47 prior closes and scaled by the 4h range.
  - Every monotone transform of OCC has the same Spearman.
  - Since RP4H is in every control set, the partial of OCC equals the partial of −(close − SMA₄₇)/(H − L) up to the rank non-linearity of the affine map.
- **In returns** (log approximation): (close_i − SMA₄₇)/close_i ≈ (1/47) Σ_{j=1..47} log(close_i/close_{i−j}) = Σ_{m=0..46} ((47 − m)/47) · r_{i−m}.
  - This is a triangular-weighted sum of the last 47 5m returns: the average of the trailing returns at every lag 1 … 47.
- **What B1 determines:** three points of that lag profile, R(3) = RET_15M, R(12) = RET_1H and R(48) = RET_4H, plus the range scale through RP4H and RV_4H.
  - It does **not** determine the average over all 47 lags. The intermediate path (where price was between those three lags) is free.
  - So OCC is **not `REDUNDANT_BY_CONSTRUCTION`** under B1.
- **What is genuinely new relative to B1:** the shape of the lag profile between 15m, 1h and 4h, i.e. where in the 4h the price spent time beyond the three endpoints and the extremes.
  - This is also why B1 is the decisive control: whatever OCC adds beyond B1 cannot be the last-hour or last-15-minute return.
- **Numeric check:** outcome-blind, in the preflight on this surface. It reports the algebra residual and the R² of rank(OCC) on the ranks of B0 and B1.
  - Pre-declared stop: if the rank residual of OCC on B1 is degenerate (RSS ≤ 1e-12·TSS, the parent's degeneracy rule), the unit stops as `REDUNDANT_BY_CONSTRUCTION`.

## 11. Diagnostics (no route)

- Raw, Secondary A, Secondary B and PRIMARY, each with an interval, N and ISO weeks.
- Yearly points 2016, 2017, 2018, 2019 and first/second half by median T, for all four estimands.
- Quintiles of OCC and of OCC's rank residual on B1: P(UP), mean and median R_1H (bp). In-sample edges; description only.
- The discovery comparison is quoted, not recomputed.

## 12. Exposure added when read

Four cells on BitMEX XBTUSD 2016–19 × DIRECTION: raw, Secondary A, Secondary B, PRIMARY.

## 13. Not this unit; no successor

- **Not read:** Binance 2025–26, spot, CORE (no recomputation), OCC variants (OCC_THIRDS), other windows, horizons, interactions with RP4H, a 4h target, OI, E1, the session objects.
- **After the one shot:** STOP. The owner decides the next step.

## 14. Execution

- **Code:** `scripts/research/occ_mean_4h_temporal_v1/`. It imports Unit A's loader, census, grid, anchors, sample and local returns; the discovery OCC function; and the parent rank code.
- **Tests:** `tests/research/test_occ_mean_4h_temporal_v1.py`, synthetic only.
- **`preflight`:** census, support N/weeks/years, and the identity audit. No R_1H statistic.
- **`run --go`:** the one shot. It refuses on a design-hash mismatch, a support mismatch with the pinned N/weeks, or an existing result.
- **Result:** `OCC_MEAN_4H_TEMPORAL_REPLICATION_V1.json` / `.md`.
