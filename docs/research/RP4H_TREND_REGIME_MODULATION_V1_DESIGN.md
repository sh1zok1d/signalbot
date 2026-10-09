# RP4H_TREND_REGIME_MODULATION_V1 — design (discovery; frozen before any outcome)

**Date:** 2026-10-09. **Author:** chief architect.
**Owner decision:** 2026-10-09, "давай те две" — the two adaptation candidates. This is the first.
**Mode:** `DISCOVERY`, one shot, on `CORE_BTC_BINANCE_V0`. **Claim ceiling:** `DISCOVERY_ONLY`. `PRODUCT_INTEGRATION_CANDIDATE = NO`.

## 1. Question and market mechanism

Does the RANGE_POSITION_4H reversal depend on the trend regime?
- **Mechanism:** reversal from the edges of the 4h range works in ranging markets, through stops and liquidity at the boundaries. In a strong trend, a close at the edge is more often the start of a continuation. So the RP4H association should be weaker in trending regimes.
- **Adaptation meant here:** the strength of a robust state is gated by an observable, past-only regime variable. One pre-declared regime variable; no data-driven window selection.

**Disclosure: the motivation is outcome-inspired.**
- RP4H's primary partial was ≈ 0 on Bybit in 2021 (a strong bull year).
- On Binance, RP4H raw was −0.029 in 2025 and −0.065 in 2026.
- Discovery therefore runs on CORE, and confirmation needs separate surfaces (§8).

## 2. Surface and sample

- **Data:** CORE BTCUSDT perpetual 1m → 5m, 2020-01-01 … 2024-12-31. The pinned R03/DSS V2 loader is imported (zip-list digest `93659495…aa90b`).
- **Anchors:** the RP4H 15-minute phase. Bar index ≥ 288 (24h of history), with RP4H, RET_4H, RV_4H, width, R_1H and TS_24H finite.
- **Size:** N 175,292 over 262 ISO weeks (outcome-blind preflight; the DIRECTIONAL_STATE_SEARCH_V2 base sample).
- **Features:** the RP4H parent code (imported). RET_1H and RET_15M come from Unit A's local returns (imported).

## 3. Regime variable (one, frozen)

- **TS_24H = |log(close_i / close_{i−288})| / √(Σ_{k=i−287..i} log(close_k/close_{k−1})²)**: the unsigned 24h trend strength in σ units.
  - Past-only; dimensionless, so comparable across eras.
- **Terciles:** cut at the quantiles of TS_24H on this sample, computed outcome-blind in the preflight and pinned: **0.3603253093 / 0.8528621531**.
  - T1 = ranging (TS < 0.360), T3 = trending (TS ≥ 0.853).
  - N by tercile: 58,431 / 58,430 / 58,431.
- **Feature-only correlations:** Spearman(TS, RP4H) = 0.016; Spearman(TS, |RET_4H|) = 0.19.
- **Not used:** signed trend, which is H04's pullback-continuation territory; other regime variables; other windows.

## 4. Estimands

All use the RP4H parent rank machinery: midranks, OLS residualization on the control ranks, Pearson of the residuals.

| name | estimand | role |
|---|---|---|
| rho_tk_b0 | partial Spearman(RP4H, R_1H \| RET_4H, RV_4H) within tercile k (k = 1, 2, 3) | components |
| **delta_b0** | **rho_t3_b0 − rho_t1_b0** (trending minus ranging) | **PRIMARY** |
| delta_b1 | the same with the local path (RET_4H, RV_4H, RET_1H, RET_15M) | secondary |
| interaction_b0 | partial Spearman(R_1H, centered rank(RP4H) × centered rank(TS) \| RP4H, TS, RET_4H, RV_4H) | secondary |

**Mechanism direction:** RP4H's association is negative, so a weaker reversal in trends means **delta > 0**.

**Diagnostics** (no route):
- per-year rho_t1, rho_t3 and delta;
- RP4H quintiles (P(UP), mean and median R_1H in bp) within T1 and within T3.

## 5. Uncertainty

- ISO-week blocks resampled with replacement; B = 2000; seed `20261122`.
- Tercile membership is fixed per row. Every partial and its ranks are recomputed per draw, and both terciles use the same draw.
- Percentile 2.5 / 97.5; at least 1,900 valid draws.

## 6. Routes (frozen; PRIMARY delta_b0 only)

1. **`TREND_REGIME_IMPLEMENTATION_INVALID`:** support or pin mismatch, or fewer than 1,900 valid draws.
2. **`TREND_REGIME_MODULATION_DISCOVERED`:** delta > 0 and the 95 % interval > 0. The reversal is weaker in trending regimes.
3. **`TREND_REGIME_MODULATION_OPPOSITE`:** delta < 0 and the interval < 0. The reversal is stronger in trends.
4. **`TREND_REGIME_MODULATION_NOT_DETECTED`:** otherwise.

**Promotion to a replication proposal** also needs the rules §4 search bar: |z| = |delta|/SE ≥ 3.850 (m = 840 CORE × DIRECTION + 6 cells of this unit). Below the bar a discovered route stays `DISCOVERY_ONLY`.

## 7. Information (before reading)

- **Prior evidence:** Unit A's RP4H partial had a CI half-width ≈ 0.0076 at N 127k.
- **Expected precision here:** at ≈ 58k per tercile, SE(rho_tk) ≈ 0.006 and **SE(delta) ≈ 0.008–0.009**.
- **Detectable sizes:**
  - an interval excluding zero needs |delta| ≳ 0.017;
  - the search bar needs |delta| ≳ 0.033, i.e. the reversal roughly vanishing in one regime.
- This is a deliberately modest-power discovery.

## 8. Exposure audit (before freeze)

Read-only audit: the records, the code and the Cursor branches (pre-impulse atlas and its review, the Bybit successor, the BitMEX, 2025–26 and forecast-prototype branches). Nothing was computed.

**Verdict:** no read of RP4H jointly with trend strength, efficiency, |RET_24H|, a variance ratio, an ADX-like measure or a trend percentile against a direction outcome exists on any surface. The contrast is not EXACT or EQUIVALENT; it is ADJACENT.

**Subgroup reading (rules §3):** the RP4H partial inside a TS tercile is a subgroup of RP4H → R_1H, which is exposed on CORE (atlas, DSS V2, the Bybit same-period read). So:
- CORE is `DISCOVERY_REUSABLE` for this question, which is acceptable for a discovery;
- the contrast is the new content;
- this unit claims no question-fresh status on CORE.

| nearest read | relation | class |
|---|---|---|
| Pre-impulse atlas | efficiency_1h/4h and adverse_share_4h as main effects only; 12 session interactions of range_ratio/frac_near (not close_pos_4h); its review says an interaction with position "was not estimated" | ADJACENT |
| DSS V2 stage 2 | OCC×RP4H and SESSION_HANDOFF×RP4H only; RET_24H/RV_24H only as controls | ADJACENT |
| H04 / B2-04 | trend gate (30-day percentile of \|ret\| over 4/8/16h ≥ 0.80) × pullback depth, signed, direction-aligned outcome; no low-trend arm, no RP4H | ADJACENT; **RP4H is not signed by the trend here, which would compose H04/C1 parts** |
| B2-03 | path efficiency over 15–60m inside a morphology score; no range position | ADJACENT |
| DH3 (owner-closed) | TREND24 = signed 24h-return tercile, a nuisance only, UP_FIRST_4H; no RP4H | not a DH3 cell or composition |
| RP4H replications (Bybit, Unit A, Unit B, Cursor twins) | full sample, years, halves, quintiles only | subgroup source |

**Disclosures:**
- This unit is not on the earlier run order or among the catalog survivors; the owner chose it on 2026-10-09.
- The red team rejected a different regime idea (R2, autocorrelation regime switch, `REJECT_UNCLEAR`, "no mechanism pins the regime rule"). Here one regime variable with a stated mechanism is pinned before the outcome.
- RP4H's outcome vector on CORE is known, including RP4H read within OCC and SESSION_HANDOFF terciles.
- `EXPOSURE_COUNTERS_V1` does not yet count the Cursor RP4H twins, so m_ST is a lower bound.

**Surfaces for a later replication of the contrast** (the RP4H level is read on each, so not pristine):
- BitMEX 2016–19 (Unit A canonical) **or** Binance spot 2017–19, not both (same period);
- Binance 2025–26 on the Unit B surface;
- prospective live data;
- **never** Bybit 2020–24 (same period as CORE).

## 9. After the outcome

- No other regime variable, window, tercile cut, horizon or signed trend.
- If promoted, a separate replication unit uses the frozen edges on BitMEX 2016–19 (or Binance spot 2017–19, not both) and on Binance 2025–26 (Unit B surface). Each needs its own design and owner GO.
- No product or forecast use.

## 10. Execution

- **Code:** `scripts/research/rp4h_trend_regime_v1/`. **Tests:** `tests/research/test_rp4h_trend_regime_v1.py` (synthetic).
- **`preflight`:** support, TS quantiles and terciles, feature-only correlations.
- **`run --go`:** the one shot. It refuses on a design hash, N/weeks or edge mismatch, or an existing result.
- **Exposure added when read:** 6 cells, CORE × DIRECTION.
