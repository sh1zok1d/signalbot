# ADAPTIVE_B1_FORECAST_V1 — design DRAFT (not frozen; owner decision pending on sequencing with Cursor's prototype and on P2)

**Date:** 2026-10-09. **Author:** chief architect.
**Owner decision:** 2026-10-09, "давай те две" — the second adaptation candidate.
**Evidence class:** `RETROSPECTIVE_ADAPTIVE_FORECAST_PROTOTYPE / HISTORICAL_ONLY`. The B1 → R_1H relations were already read on all three surfaces (§9), so this is not a replication and not pristine.
**Not:** a current probability, a product line, a forecast-engine component, PnL or fees. `PRODUCT_INTEGRATION_CANDIDATE = NO`.

## 1. Questions

- **P1 (foundation):** does a simple logistic model on the robust B1 states give out-of-sample probabilistic skill for the sign of the next hour, against climatology?
- **P2 (adaptation):** does a trailing-memory model whose memory is chosen from the past only beat the same model with expanding (non-forgetting) memory?

The signal set (RANGE_POSITION_4H and the short local path) is the strongest directional information found in the project. If adaptation can be seen anywhere, it is here.

## 2. Surfaces and chronology

One chronology of three canonical series. Each keeps its own 5m grid, so no feature window and no target crosses a venue boundary.

| era | series | loader (imported) | rows |
|---|---|---|---|
| BitMEX XBTUSD 2016-05 … 2019-12 | D2 canonical 5m (SHA `8e027433…`; one 288-bar gap; zero-trade bars kept) | RP4H Unit A | 127,303 |
| Binance USD-M BTCUSDT 2020 … 2024 | CORE 1m → 5m (zip list `93659495…`) | RP4H_TREND_REGIME_MODULATION_V1 sample | 175,372 |
| Binance USD-M BTCUSDT 2025-01 … 2026-10-08 | RP4H Unit B canonical 64 objects (E1 window and E1-development slice never requested; census pinned) | RP4H Unit B | 59,672 |

- **Anchors:** the RP4H 15-minute phase. RP4H, RET_4H, RV_4H, width and R_1H are finite; RET_1H and RET_15M lie inside the window. Total 362,347 rows in strict chronological order.
- **Training across a venue boundary is permitted:** the features are dimensionless or standardized, and training memory may pool eras. The per-era diagnostics show what each era contributes.

## 3. Target, features, model (frozen)

- **Target:** `Y = 1{R_1H > 0}`, with `R_1H = log(close[i+12]/close[i])`. A zero return is 0; this matters for BitMEX zero-trade bars.
- **Features (all five B1 quantities):** x = [RP4H − 0.5, RET_4H/RV_4H, RET_1H/RV_4H, RET_15M/RV_4H, log RV_4H].
- **Preprocessing:** standardization fitted on the training rows only, then clipped to ±5.
- **Model:** logistic regression by Newton-IRLS with an L2 ridge of 1.0 on the standardized slopes (none on the intercept); at most 50 iterations; tolerance 1e-10. No other model class and no hyperparameter search.

## 4. Walk-forward (frozen)

- **Grid blocks:** 28-day blocks starting on Mondays 00:00 UTC.
- **First outer block:** the first Monday with 104 + 24 weeks of history: **2018-10-29T00:00Z**. **104 outer blocks** through 2026-10-08, with 276,225 outer predictions:

  | diagnostic era | outer rows |
  |---|---|
  | 2018–19 | 41,181 |
  | 2020–22 | 105,199 |
  | 2023–24 | 70,173 |
  | 2025–26 | 59,672 |

- **Training rows for a block starting at s:** rows whose target is realized by s (close_ms + 1h ≤ s).
- **Models for every grid block:**
  - `CLIM`: the expanding-window mean of Y;
  - `STATIC`: the expanding-window logistic;
  - `FIXED_M`: the trailing-M-week logistic, M ∈ {26, 52, 104}.
- **ADAPTIVE (nested):** for outer block S, M* is the memory with the lowest pooled Brier over the 6 grid blocks before S (24 weeks).
  - Those inner predictions were each made from data before their own block, and only rows whose target is realized by S are scored.
  - Ties within 1e-9 go to the longer memory (less adaptive).
  - The block is then predicted with FIXED_{M*}. M* stays fixed for the whole block; there is no intra-block switching.
- **Outer outcomes never reach their own block's model or selection.** This is tested: flipping a block's unrealized outcomes leaves its predictions and its selection unchanged.
- **Fold manifest:** `ADAPTIVE_B1_FORECAST_V1_FOLD_MANIFEST.json` (SHA256 pinned). It holds every outer block's start/end, train end and inner interval. The run's selector log adds, per block, the selected memory, the inner Brier of each memory, the model hash and coefficients, and n.

## 5. Metrics and uncertainty

- **Primary:** mean outer Brier and log loss (p clipped to [1e-6, 1 − 1e-6]). Differences a − b; negative means a is better.
  - P1: `STATIC − CLIM`. P2: `ADAPTIVE − STATIC`.
  - Also reported: `ADAPTIVE − CLIM` and each `FIXED_M − STATIC`.
- **Uncertainty:** an ISO-week block bootstrap of the outer predictions. Whole weeks resampled; the mean difference is a ratio of week sums; B = 2000; seed `20261123`; percentile 2.5 / 97.5; at least 1,900 valid draws.
- **Secondary (no route):** AUROC; calibration intercept and slope (y on logit p); a reliability table on 10 equal-count bins of p, with ECE; per-era differences with intervals (2018–19, 2020–22, 2023–24, 2025–26).
- **Selector behaviour:** the share of blocks per memory; switches; mean run length; choices by year.

## 6. Routes (frozen; separately for P1 and P2)

1. **`ADAPTIVE_B1_IMPLEMENTATION_INVALID`** (both): leakage, nesting, support, manifest mismatch, or fewer than 1,900 valid draws.
2. **SUPPORTED** (`B1_OOS_SKILL_SUPPORTED` / `ADAPTATION_IMPROVES_FORECAST`): ΔBrier < 0, the whole 95 % interval < 0, and the Δlog-loss point < 0.
3. **WORSE** (`B1_WORSE_THAN_CLIMATOLOGY` / `ADAPTATION_WORSE`): the whole ΔBrier interval > 0.
4. **UNCERTAIN** (`B1_OOS_SKILL_UNCERTAIN` / `ADAPTATION_UNCERTAIN`): ΔBrier point < 0 otherwise.
5. **NONE** (`B1_NO_OOS_SKILL` / `ADAPTATION_NO_GAIN`): otherwise.

There is no magnitude threshold and no accuracy target.

## 7. Synthetic power check (outcome-free; done in the preflight)

Run in the preflight before any real outcome.
- **Inputs:** the real B1 features of all 362,347 rows and the real schedule.
- **Synthetic outcome:** R_syn(T) = (sum of the next 12 per-bar N(0,1) innovations on each era's own grid)/√12 + β(T)·g(T), where g = −standardized RP4H. Overlapping anchors share noise exactly as real 1h targets do.
- **Scenarios** (seeds 777, 778, 779): NULL β = 0; CONSTANT β = 0.03 (≈ an RP4H-size association); SWITCHING β = 0.06 and 0 in alternating 52-week periods (a world built to reward adaptation).
- **Procedure:** the full frozen walk-forward, nested selection, bootstrap and routes.

| scenario | STATIC − CLIM ΔBrier [95 %] | P1 route | ADAPTIVE − STATIC ΔBrier [95 %] | P2 route | selected memory 26 / 52 / 104 |
|---|---|---|---|---|---|
| NULL | +3.9e-5 [+5.4e-6, +7.5e-5] | WORSE | +4.8e-5 [+1.2e-6, +9.7e-5] | WORSE | 7 % / 14 % / 79 % |
| CONSTANT 0.03 | −9.7e-5 [−1.7e-4, −2.6e-5] | SUPPORTED | +7.2e-5 [+2.9e-5, +1.2e-4] | WORSE | 4 % / 26 % / 70 % |
| SWITCHING 0.06/0 per 52 w | −1.3e-4 [−2.1e-4, −4.6e-5] | SUPPORTED | +1.3e-4 [+5.4e-5, +2.0e-4] | WORSE | 19 % / 13 % / 67 % |

Fixed memories against STATIC in SWITCHING: 26 w +1.6e-4, 52 w +1.5e-4, 104 w +2.1e-5. Every shorter memory is worse.

**Reading, recorded before any real outcome:**
- **P1 has power:** at an RP4H-size association the route fires; with no signal it reports WORSE, through the estimation penalty under overlapping targets.
- **P2 has no power to show a benefit of adaptation at this signal-to-noise.** Even when the signal switches on and off every year, 26–52-week memories lose more to estimation noise than they gain by tracking. The selector mostly keeps 104 weeks.
- **Pre-registered interpretation rule:** a real P2 result of NONE or WORSE can **not** be read as "the market's coefficients do not drift". It only says that trailing-memory adaptation cannot pay at this signal strength. Only a P2 SUPPORTED would be informative.
- **Design consequence:** P1 is the route of record. P2 is kept as frozen and reported, but under this interpretation rule.

## 8. What would change the reading

- **P1 supported:** the robust B1 states carry out-of-sample probabilistic skill at 1h. This is a prerequisite for any economic test.
- **P1 not supported:** the historical rank associations do not survive as an out-of-sample probability model.
- **P2 supported:** forgetting helps; the market's coefficients drift.
- **P2 none or worse:** the expanding model is as good or better, and adaptation adds variance.

Neither result validates a trading edge. An economic unit would be separate.

## 9. Exposure audit (before freeze)

Read-only audit, including Cursor's `origin/cursor/range-position-4h-forecast-prototype-v1-08d8`.

**No recorded out-of-sample forecast skill exists** (Brier, log loss or calibration) for a model on these features at 1h on any of the three surfaces. LEVEL_RACE, DH1–DH3 and P3 scored other objects; the claim-journal analog class is live-only; the V1/V2 engines are uncalibrated scores.

**Evidence class:** `RETROSPECTIVE_FORECAST_PROTOTYPE` on `DISCOVERY_REUSABLE` surfaces. RP4H → R_1H and the local path were read on all three:
- BitMEX: Unit A, Cursor's twin, and the OCC replication with B1;
- CORE: the atlas, DSS V2, the Bybit same-period read, and the analogues;
- 2025–26: Unit B, Cursor's twin, and OCC modern.

Out-of-time is not out-of-question. Choosing among 26/52/104 weeks is an adaptive search: it raises the counters and confirms nothing. No L3; only a prospective test can validate.

**Partial duplicate of Cursor's frozen, unfit prototype.**
- **Its design** (commit 483dc402, `OWNER_GO = false`, no outcome read):
  - Y = 1{R_1H > 0} with exact zeros excluded;
  - a baseline {RET_4H, RV_4H, RET_1H, RET_15M} against a candidate (+ RP4H), plus climatology;
  - unpenalized Newton logistic; expanding ISO-week folds;
  - the same "labels available by the block start" rule;
  - segments trained separately: BitMEX on BitMEX only, Binance 2025–26 on Binance 2020–26;
  - ΔBrier and ΔLogLoss with a week bootstrap.
- **Overlap:** this unit's STATIC + CLIM arms equal its candidate + climatology arms. Running this unit would pre-empt Cursor's one-shot on the same surfaces.
- **Differences:**
  - this unit measures adaptivity, and has no 4-feature baseline for the RP4H increment;
  - this unit pools eras in training;
  - **Cursor's 2025–26 file includes the E1-development slice 2026-08-02 … 08-15.** This unit uses only Unit B's canonical surface;
  - this unit counts zero returns as DOWN.

**The owner must choose or sequence the two.** Cursor's prototype answers P1 and the RP4H increment; this unit answers P1 and P2 (with P2 under the power rule of §7).

**Protected data:**
- the Unit B loader with E1-window and E1-development refusals;
- CORE inside [2020-01-01, 2025-01-01);
- the BitMEX canonical file;
- no bridging across segments for features or targets. The E1 holdout is untouched.

## 10. Not this unit; no successor

- No OCC, other features, spot, other horizons, interactions, multiscale variants, PnL, fees, product or forecast-engine change.
- One evaluation; then STOP.
- **Code:** `scripts/research/adaptive_b1_forecast_v1/`. **Tests:** `tests/research/test_adaptive_b1_forecast_v1.py` (synthetic; includes the leakage test).
