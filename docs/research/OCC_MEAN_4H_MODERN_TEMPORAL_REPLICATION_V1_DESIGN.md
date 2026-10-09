# OCC_MEAN_4H_MODERN_TEMPORAL_REPLICATION_V1 — design (frozen before any outcome)

**Date:** 2026-10-09. **Author:** chief architect.
**Owner decision:** 2026-10-09, "CONTINUE TRACK B". This is the only successor; preflight first, then a separate GO. An earlier, interrupted owner draft named the unit `OCC_MEAN_4H_BINANCE_2025_2026_MODERN_REPLICATION_V1`. The final message is authoritative.
**Mode:** `CONFIRMATION`, one shot. **Evidence class:** `MODERN_TIME_DISJOINT_HISTORICAL_REPLICATION / QUESTION_FRESH_REPLICATION`, not pristine.
**Claim ceiling:** historical only. Not a current probability, forecast-engine component, trading edge or product claim. `PRODUCT_INTEGRATION_CANDIDATE = NO`.
**Rules:** `RESEARCH_RULES_DECISION_V1.md`, `EVIDENCE_AND_CLAIMS_DECISION_V1.md`.

## 1. Question

Does the local-path-controlled OCC_MEAN_4H effect observed on BitMEX 2016–19 remain positive in Binance USD-M BTCUSDT 2025–26?

This is not a new discovery search, and not a venue-robustness check.

## 2. What is known before this read (quoted, never recomputed)

| surface | OCC \| B0 | OCC \| B1 (PRIMARY) |
|---|---|---|
| Binance USD-M 2020–24 (discovery, DIRECTIONAL_STATE_SEARCH_V2 F2a) | +0.0202 [+0.0130, +0.0277] | never computed; stays uncomputed (owner) |
| BitMEX XBTUSD 2016–19 (OCC_MEAN_4H_TEMPORAL_REPLICATION_V1, SUPPORTED) | +0.0299 [+0.0209, +0.0391] | +0.0110 [+0.0021, +0.0199]; years ≈0, ≈0, +0.016, +0.020 |

- **Status before this unit:** `SECOND_DIRECTIONAL_STATE_CANDIDATE / HISTORICAL_ONLY / TEMPORAL_STABILITY_UNRESOLVED`.
- **Interpretation rule (owner):** the BitMEX value is not used to tune anything. That covers controls, definition, subgroup, years, thresholds and bootstrap. This unit is a literal transfer of the frozen question. The modern estimate need not equal +0.011; the question is sign, uncertainty and temporal compatibility.

## 3. Surface: the canonical Binance 2025–26 surface of RP4H Unit B (imported)

- **Objects:** `docs/research_data/RP4H_BINANCE_UM_BTCUSDT_5M_2025_2026_V0/MANIFEST.json`, object-list SHA256 `5369e8dc265ada989fa048fd49e8d694a2478e69916338223fe118f0dd0db621`.
  - 64 Binance USD-M BTCUSDT 5m kline objects: monthly 2025-01 … 2026-07 (19), daily 2026-08-01 (1), daily 2026-08-26 … 2026-10-08 (44).
  - Each SHA256 was pinned from the published `.CHECKSUM` and is verified on every fetch.
- **Interval:** bar opens 2025-01-01T00:00Z … 2026-10-08T23:55Z, end exclusive 2026-10-09, **minus [2026-08-02T00:00Z, 2026-08-26T00:00Z)**.
- **Exclusions are unchanged and are not reopened:**
  - The E1-RUN-001 window `[2026-08-16T00:00Z, 2026-08-25T17:20Z)` goes through the product guard (`beta.history_data`), which refuses every overlapping object before any request: the monthly 2026-08 object, and the daily 2026-08-16 … 08-25 objects, the 25th whole.
  - The E1-development slice `[2026-08-02, 2026-08-16)` is never requested (Unit B's object-level cut).
  - Whole-object exclusion is the canonical policy. No widening for N. No Cursor surface semantics.
- **Missingness:** Unit B's.
  - Every published row is a bar. A bar is missing only when its timestamp is absent. Nothing is filled.
  - The census is pinned: rows 179,136; holes 6,912 = E1 window 2,800 + E1-development slice 4,032 + the rest of the refused 25th 80 + other 0; holes SHA256 `7217c65f…0b95ab`.
  - The run refuses on any difference (`assert_census`, imported).

## 4. Object (F2a, literally; the discovery function `directional_state_search_v2.features.occupancy` imported)

- **Box:** H = max high and L = min low over bars i−47 … i (48 bars, every bar present).
- **Undefined when** H − L ≤ 0 or is not finite.
- **p_k = (close_k − L)/(H − L)** for k = i−47 … i−1. The current close is excluded.
- **OCC_MEAN_4H = mean(p_k).**
- No OCC_THIRDS, alternate mean, EMA, TWAP variant, other lookback or other current-close treatment.

## 5. Controls, estimands, target, cadence, bootstrap

All imported from `OCC_MEAN_4H_TEMPORAL_REPLICATION_V1`, identical.

- **B0** = RP4H = (close_i − L)/(H − L), RET_4H = log(close_i/close_{i−48}), RV_4H = √Σ_{k=i−47..i} log(close_k/close_{k−1})².
- **B1** = B0 + RET_1H = log(close_i/close_{i−12}) + RET_15M = log(close_i/close_{i−3}).
- **PRIMARY:** partial Spearman(OCC, R_1H | B1). **Secondary, no route:** raw, | B0, | B0 + RET_1H. Nothing else.
- **Method:** midranks, OLS residualization with an intercept on the control ranks, and the Pearson correlation of the residuals (RP4H parent code).
- **Target:** `R_1H = log(close[i+12]/close[i])`. The target bar must be present and open before 2026-10-09.
- **Cadence:** 15-minute RP4H phase anchors.
- **Sample:** Unit B's sample (imported). OCC is finite on every row; the run refuses otherwise.
- **Bootstrap:** ISO-week blocks resampled with replacement, B = 2000, seed `20261117` (frozen), ranks and every partial recomputed per draw, percentile 2.5 / 97.5, at least 1,900 valid PRIMARY draws.

## 6. Routes (frozen order; PRIMARY alone; no magnitude gate)

1. **`OCC_IMPLEMENTATION_INVALID`:** provenance, census, support, finiteness or evaluator failure, a missing PRIMARY point, or fewer than 1,900 valid draws. → status unchanged.
2. **`OCC_MODERN_TEMPORAL_REPLICATION_INCREMENTAL_SUPPORTED`:** PRIMARY point > 0 and the whole 95 % interval > 0. → `CROSS_EPOCH_SECOND_DIRECTIONAL_STATE_CANDIDATE / HISTORICAL_ONLY`, then STOP (no automatic forecast integration).
3. **`OCC_MODERN_SIGN_OPPOSES`:** the whole 95 % interval < 0. → `HISTORICALLY_REPLICATED_BUT_NOT_MODERNLY_STABLE`.
4. **`OCC_MODERN_DIRECTION_COMPATIBLE_BUT_UNCERTAIN`:** PRIMARY point > 0, interval includes zero. → stays `SECOND_DIRECTIONAL_STATE_CANDIDATE / TEMPORAL_STABILITY_UNRESOLVED`.
5. **`OCC_MODERN_NOT_REPLICATED`:** otherwise (point ≤ 0, interval includes zero). → `HISTORICALLY_REPLICATED_BUT_NOT_MODERNLY_STABLE`.

No rescue by variants after any route. The OCC line ends after this unit unless the owner reopens it.

## 7. Exact exposure audit (before freeze)

Read-only audit of every recorded read of S (Binance USD-M BTCUSDT 2025-01-01 … 2026-10-08), the product code, the claim journal and the live matchers. It started from `RANGE_POSITION_4H_BINANCE_2025_2026_EXPOSURE_AUDIT_V1.md` and re-checked every read's code for mean-type features. Nothing was computed.

**Verdict: Q = OCC_MEAN_4H → R_1H has never been read on S, and neither has an equivalent.** Checked forms:
- close vs a trailing 2–8h SMA/TWAP/VWAP;
- z-score or %B;
- occupancy or frac_near;
- midpoint slope;
- A1.

S is `QUESTION_FRESH_REPLICATION` for Q, not pristine. The outcome-blind preflight of this unit (§8) never touched R_1H.

| read of S | mean-type feature | outcome | class vs Q |
|---|---|---|---|
| DIVERGENCE_FULL_HISTORY_V0 (six coins pooled, 2023-01 … 2026-08-11) | `HTF_EMA168_DIST_ATR` = (1h close − EMA168 of 1h closes)/ATR14 (a 7-day EMA); MACD; RSI deltas | +1R before −1R within 48h, inside divergence/support episodes | ADJACENT (same family, 42× longer window, episode-conditional, owner-closed line) |
| Product `VWAP_D` (`beta/levels.py`) | the current UTC-day VWAP as a level | none: not in the stats, push or race level kinds | UNRELATED |
| E1 development, V1 autopsy, product analogues, rangecast, level and distance reactions, LEVEL_RACE held-out, P3, P4, claim journal, live research states | no mean-distance feature (extrema, signed moves, ranges, flow, OI, σ) | various | UNRELATED or adjacent to the controls only |
| RP4H Unit B (identical anchors and R_1H vector) | RP4H, RET_4H, RV_4H, width, RET_1H, RET_15M; no OCC | R_1H | ADJACENT (closest) |
| Cursor's parallel Binance 2025–26 RP4H read (branch `cursor/range-position-4h-binance-2025-2026-temporal-replication-v1-08d8`, commit 7b55fff, not merged) | the same RP4H features; no OCC. Its object hole is only [2026-08-16, 2026-08-26), so it also read the E1-development slice | R_1H | ADJACENT for Q; newly disclosed; to be added to the exposure counters |
| Cursor's RP4H forecast prototype (commit 58648568) | RET_4H, RV_4H, RET_1H, RET_15M, RP4H; `OWNER_GO = False` | none read yet | none |

Not on S: DIRECTIONAL_STATE_SEARCH_V2, the BitMEX OCC unit, the pre-impulse atlas, the Bybit successor, MARKET-03, H02 and TWAP V1 (spot).

**Disclosed adjacent exposure:**
- Unit B exposed the RP4H term of OCC = RP4H − (close − SMA₄₇)/(H − L) in full, and the local-path secondary for RP4H.
- Its return controls cover part of the deviation term. It never published a control's own association with R_1H.
- E1 CB breakouts (2026-08-02 … 08-16) are a joint tail of RP4H and the deviation term, because a fresh close above the 4h high is above every prior close. There is no conditioning on the size of the deviation.
- The designer knows both earlier OCC results (§2) and uses neither.

**E1 cuts for OCC:**
- **The E1 holdout is mandatory:** a reserved surface; the product guard applies at object level; the P4 invalidation does not release it.
- **The E1-development cut is kept**, although OCC's exposure there is only adjacent:
  - parity with Unit B's canonical object list and anchors;
  - admitting the slice now would be a surface choice made after RP4H outcomes are known;
  - it is the densest adjacent exposure.
- The cost is 4,032 slots.

## 8. Identity audit (outcome-blind; as in the BitMEX unit)

- OCC = (SMA₄₇ − L)/(H − L) and OCC − RP4H = −(close_i − SMA₄₇)/(H − L).
- B1 fixes three points of the trailing-return profile (lags 3, 12, 48) and the range scale, but not the average over lags 1 … 47.
- **Pre-declared stop:** a degenerate rank residual of OCC on B1 (RSS ≤ 1e-12·TSS) → `REDUNDANT_BY_CONSTRUCTION`.
- **Outcome-blind preflight on this surface:** algebra residual 2.2e-13; Spearman(OCC − RP4H, −(close − SMA₄₇)/(H − L)) = 1.0000; R² of rank(OCC) on the ranks of B0 0.041 and of B1 0.215. So OCC is not redundant.

## 9. Diagnostics (no route)

- raw, | B0, | B0 + RET_1H and PRIMARY, each with an interval; N and ISO weeks.
- 2025 and 2026 (partial year) points.
- First / second chronological half by median T.
- Quintiles of OCC and of OCC's rank residual on B1: P(UP), mean and median R_1H in bp; in-sample edges.
- **Heterogeneity** (descriptive, pre-declared): modern PRIMARY − BitMEX PRIMARY, with SEs approximated from each 95 % percentile interval (width/3.92), and the z of the difference.
- The cross-era table is quoted, not pooled.

## 10. Exposure added when read

Four cells on BINANCE_PERP_BTC_2025_2026 × DIRECTION: raw, | B0, | B0 + RET_1H, PRIMARY.

## 11. Not this unit

- No B1 on Binance 2020–24. No spot, BitMEX, OCC variants, other windows or horizons, RET_30M/RET_2H, TWAP features, session or RP4H interactions, PnL, product or forecast-engine change, OI or E1.

## 12. Execution

- **Code:** `scripts/research/occ_mean_4h_modern_temporal_v1/`.
- **Tests:** `tests/research/test_occ_mean_4h_modern_temporal_v1.py` (synthetic).
- **`preflight`:** outcome-blind; census, support and the identity audit.
- **`run --go`:** the one shot.
  - It refuses on a design-hash mismatch, a census mismatch, N/weeks ≠ pinned, redundancy, or an existing result.
  - Set `RP4H_B_CACHE` to the verified object cache to avoid re-downloading.
