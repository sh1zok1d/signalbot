# ADAPTIVE_OCCUPANCY_TIMESCALE_V1 — design (frozen before any real outcome)

**Date:** 2026-10-10. **Author:** chief architect, on the owner's decision of 2026-10-10 (Track B).
**Mode:** one-shot retrospective walk-forward evaluation of a pre-defined algorithm.
**Evidence class:** `RETROSPECTIVE_ADAPTIVE_FORECAST_PROTOTYPE / HISTORICAL_ONLY`. **Claim ceiling:** `HISTORICAL_ONLY`.
**Not:** a current probability, a product line, a forecast-engine component, PnL, fees, Sharpe or entries. `PRODUCT_INTEGRATION_CANDIDATE = NO`.
**Track separation:** Cursor's RANGE_POSITION_4H_FORECAST_PROTOTYPE_V1 and its A2 port are Track A. This unit does not run them, does not use their outcome, and does not change them (§14).

## 1. Question and market mechanism

**Question:** can a pre-defined, past-only algorithm that adapts the occupancy timescale improve the next-hour BTC direction probability on unseen periods?

**Mechanism:**
- OCC_MEAN_4H measures where the price *spent* the last 4 hours inside its 4h box, not only where it closes. It is a slow inventory or acceptance state: time spent high in the box reads as acceptance and is followed by a slightly higher next hour, beyond RP4H and the local path.
- The horizon over which participants build and unwind inventory need not be fixed at 4 hours. It may lengthen or shorten with the market's speed and participation.
- An algorithm that picks the timescale from recent out-of-sample performance would follow such a shift. A fixed 4h choice would not.

**Disclosures:**
- **The motivation is outcome-inspired.** OCC_MEAN_4H was supported on BitMEX 2016–19 (PRIMARY | B1 +0.0110 [+0.0021, +0.0199]) and not replicated on Binance 2025–26 (−0.0017 [−0.0162, +0.0119]). The idea that "the timescale moved" came after those reads.
- **The OCC line was ended by owner rule.** The owner's 2026-10-10 order for this unit is the owner override for this exact question. The static OCC_4H status `HISTORICALLY_REPLICATED_BUT_NOT_MODERNLY_STABLE` is not reopened and not changed by any outcome here.

## 2. Surfaces and the venue-transition policy (fixed before the run)

Three canonical series on two venues. Each series keeps its own 5m grid: no feature window and no target crosses a series boundary.

| era | series and digest | loader (imported) | span | rows with all OCC_L |
|---|---|---|---|---|
| BitMEX XBTUSD 2016–19 | D2 canonical 5m, SHA256 `8e027433b528a8ee084a90690ff4b0c4f819d1f1b66c776d635cf466bd8e56fa`; 382,033 bars, 288 holes (the documented gap), 22,728 zero-trade bars kept | RP4H Unit A | 2016-05-13 … 2019-12-31 | 127,002 of 127,303 |
| Binance USD-M BTCUSDT 2020–24 (CORE) | 1m zip list SHA256 `936594956e8bfea33eec09a7e61dbbc8051bb4c0d4d083abdbcb6091c62aa90b` → 5m | RP4H_TREND_REGIME_MODULATION_V1 sample (`need_24h = False`) | 2020-01-01 … 2024-12-31 | 175,337 of 175,372 |
| Binance USD-M BTCUSDT 2025–26 | RP4H Unit B canonical 64 objects, list SHA256 `5369e8dc265ada989fa048fd49e8d694a2478e69916338223fe118f0dd0db621`; holes SHA256 `7217c65f…474090` (E1 window 2,800, E1-development slice 4,032, rest of the refused 25th 80, other 0) | RP4H Unit B (census asserted) | 2025-01-01 … 2026-10-08 | 59,610 of 59,672 |

- **Rows:** 361,949 in strict chronological order, all features finite. A row is dropped only if some OCC_L is undefined; the 12h window needs 144 bars, so the first 12 hours after a series start or a hole drop out.
- **Venue policy: two venues, never mixed in training.**
  - BitMEX blocks train on BitMEX rows only.
  - Binance blocks train on Binance rows only: 2020–24 and the earlier 2025–26 rows together, as one USD-M BTCUSDT venue.
  - Each venue has its own block schedule, warm-up and memory eligibility (§5).
  - *Reason:*
    - XBTUSD is an inverse contract with 6 % zero-trade bars;
    - OCC is a path-shape variable sensitive to bar formation;
    - a memory that straddled the venue switch would confound adaptation with the venue change.
  - *Cost:* Binance 2020 is warm-up only.
- **Protected data:**
  - the E1-RUN-001 holdout `[2026-08-16T00:00Z, 2026-08-25T17:20Z)` is never requested (Unit B object-level refusal);
  - the E1-development slice `[2026-08-02, 2026-08-16)` is never requested (Unit B canonical exclusion);
  - CORE lies inside [2020-01-01, 2025-01-01).
- **Not read:** spot, other venues, other symbols, OI, any other feature.

## 3. Target

- **Y = 1{R_1H > 0}**, with R_1H = log(close[i+12] / close[i]) on the series' own grid. A zero return counts as 0 (DOWN).
- **Anchors:** the RP4H 15-minute phase, ((open − 2020-01-01T00:00Z)/5m) mod 3 = 2, on every series.

## 4. Features

**Baseline B1 (the owner's five quantities):** RP4H, RET_4H, RV_4H, RET_1H, RET_15M.
- They come from the RP4H parent code and Unit A's local returns, imported.
- **Frozen representation:** x_B1 = [RP4H − 0.5, RET_4H/RV_4H, RET_1H/RV_4H, RET_15M/RV_4H, log RV_4H]. This is ADAPTIVE_B1_FORECAST_V1's design function, imported.

**OCC_L, the exact analogue of OCC_MEAN_4H on an L-hour window:**
- n = 12L bars i−n+1 … i, the current bar included.
- Box: H = max high, Lo = min low over the n bars.
- The n−1 previous closes k = i−n+1 … i−1 are normalized: p_k = (close_k − Lo)/(H − Lo).
- The current close is excluded. **OCC_L = mean p_k.**
- Undefined if any bar of the window is missing, or H − Lo ≤ 0.
- No EMA, VWAP, thirds, nonlinearity, weights or thresholds.
- **Parity:** for L = 4 this is DIRECTIONAL_STATE_SEARCH_V2 F2a to 1e-14, tested against the DSS V2 function.
- **Bar index:** proven per row. RP4H recomputed from the grid at the row's bar equals the sample's RP4H to 1e-12 on all three series; the preflight refuses otherwise.

**Lookbacks:** L ∈ {1, 2, 3, 4, 6, 8, 12} hours, plus **NO_OCC** (mandatory). A model with OCC_L has x = [x_B1, OCC_L − 0.5]. Exactly one lookback per model.

## 5. Systems and the walk-forward (frozen)

**Blocks (outer semantics):** per venue, consecutive 28-day blocks starting on Mondays 00:00 UTC (4 ISO weeks).
- **Why 28 days:**
  - ISO weeks, the bootstrap unit, nest inside blocks;
  - ≈ 2,690 rows per block, enough for a selection to be scored;
  - 13 decisions a year, fast enough to follow a timescale shift that lasts months;
  - the same as ADAPTIVE_B1_FORECAST_V1.
- Weekly blocks would make the selection noisy; quarterly blocks would be too slow to adapt.
- Models are refitted at every block start. The selection is frozen for the whole block; there is no intra-block switching.

**First outer block:** the first Monday with 26 + 24 weeks of venue history (the shortest memory plus the inner window).
- BitMEX: **2017-05-01**.
- Binance: **2020-12-21**.

**Outer blocks: 111** (BitMEX 35, Binance 76). **Outer rows: 294,493**, coverage 0.814 of all rows.

| diagnostic era | outer rows |
|---|---|
| 2016–19 (BitMEX from 2017-05) | 93,578 |
| 2020–22 (Binance from 2020-12-21) | 71,136 |
| 2023–24 | 70,169 |
| 2025–26 | 59,610 |

**Partial blocks are scored as they are:**
- Binance 2026-07-27 has 573 rows: the E1-development slice and the E1 window fall in it.
- Binance 2026-08-24 has 2,448 rows.
- Binance 2026-09-21 has 1,725 rows: the surface ends 2026-10-08.
- BitMEX 2019-12-09 has 2,205 rows: the series ends.

**Training rule:** a block starting at s trains only on venue rows whose label is realized by s, i.e. close_ms + 1h ≤ s. The row whose label is realized exactly at s is used.

**Systems, refitted at every grid block:**
- **CLIMATOLOGY:** the expanding-window mean of Y.
- **BASELINE_B1:** the expanding-window logistic on x_B1.
- **STATIC_OCC_4H:** the expanding-window logistic on x_B1 + OCC_4H.
- **Candidates (M, c):** trailing-M-week logistic, M ∈ {26, 52, 104}, c ∈ {NO_OCC, OCC_1H … OCC_12H}. That is 24 candidates.
- **ADAPTIVE_OCC:** the selected candidate (below).
- **Diagnostic MM_NO_OCC (no route):** the (M*, NO_OCC) model at the memory ADAPTIVE selected. It separates the OCC contribution from the memory effect.

**Memory eligibility and minimum history:**
- A candidate (M, ·) exists at a grid block start s only if s − M weeks ≥ the venue's first anchor, i.e. its window is full.
- It is eligible for outer block S only if all its inner models had a full window: S − 24 weeks − M weeks ≥ the first anchor.
- **No fallback:** an ineligible memory is not scored. The 26-week memory and NO_OCC are eligible at every outer block. Expanding systems fit from the venue's first anchor.
- A missing inner or outer prediction aborts the run (`IMPLEMENTATION_INVALID`).

| venue | memories eligible | blocks | from … to |
|---|---|---|---|
| BitMEX | 26 | 7 | 2017-05-01 … 2017-10-16 |
| BitMEX | 26, 52 | 13 | 2017-11-13 … 2018-10-15 |
| BitMEX | 26, 52, 104 | 15 | 2018-11-12 … 2019-12-09 |
| Binance | 26 | 7 | 2020-12-21 … 2021-06-07 |
| Binance | 26, 52 | 13 | 2021-07-05 … 2022-06-06 |
| Binance | 26, 52, 104 | 56 | 2022-07-04 … 2026-09-21 |

**Inner procedure (nested):**
- For outer block S, the inner window is the 6 grid blocks before S (24 weeks).
- Every inner prediction of a candidate was made by that candidate's model fitted at its own grid block's start. So the inner score is the out-of-sample record the policy (M, c) would have had.
- Only inner rows whose label is realized by S are scored.

**Selection algorithm:**
1. Over all eligible (M, c), the lowest pooled inner Brier wins.
2. Brier ties within 1e-9 go to the lowest inner log loss.
3. Remaining ties are broken by a fixed order: NO_OCC first, then the longer memory, then the shorter lookback.

No Spearman, p-value or accuracy is used. ADAPTIVE predicts the outer block with the chosen (M*, c*) model fitted at S.

**Manifests (pinned):**
- `ADAPTIVE_OCCUPANCY_TIMESCALE_V1_FOLD_MANIFEST.json` lists every outer block's start/end, train end, inner interval, eligible memories and n.
- `..._SELECTOR_MANIFEST.json` holds the candidate set, objective, tie-break and eligibility rule.

**Selector log (written by the run), per outer block:**
- venue, start/end, train end, inner interval;
- eligible memories, selected memory and lookback (or NO_OCC);
- the OCC coefficient (standardized β), the model hash;
- the inner Brier and log loss of the choice and the best NO_OCC inner Brier;
- the outer Brier and log loss of ADAPTIVE and the outer Brier of B1.

Selection shares and persistence (switches, mean run length) are reported per venue for lookbacks and for memories.

## 6. Model and preprocessing (frozen)

- **Model:** logistic regression by Newton-IRLS, imported from `adaptive_b1_forecast_v1.model`.
  - L2 ridge 1.0 on the standardized slopes, none on the intercept.
  - The intercept starts at logit(ȳ). At most 50 iterations; tolerance 1e-10.
- **Preprocessing:** standardization (mean, sd) is fitted on the model's training rows only, then clipped to ±5. The same transform is applied to its prediction rows.
- **Fixed:** no other model class, no hyperparameter search, no feature selection beyond the candidate set.
- **Guard:** the shared constants (ridge, clip, iterations, tolerance, probability clip, bootstrap draws and quantiles, reliability bins) are asserted equal to this design's values at run time.

## 7. Metrics

- **Losses:** Brier, and log loss with p clipped to [1e-6, 1 − 1e-6], over all outer rows of both venues.
- **Primary:**
  - **ΔBrier = Brier(ADAPTIVE_OCC) − Brier(BASELINE_B1)**, which carries the route, and ΔLogLoss for the same pair. Negative means ADAPTIVE is better.
  - Always reported: ADAPTIVE_OCC − STATIC_OCC_4H (ΔBrier, ΔLogLoss).
- **Diagnostic pairs:** STATIC_OCC_4H − B1, B1 − CLIM, ADAPTIVE − CLIM, ADAPTIVE − MM_NO_OCC.
- **Era diagnostics (no route):** 2016–19, 2020–22, 2023–24, 2025–26, each with N, weeks, P(UP) and the bootstrap intervals.
- **Secondary, per system (no route):**
  - calibration intercept and slope (y on logit p);
  - a reliability table on 10 equal-count bins with ECE;
  - AUROC;
  - the probability distribution (mean, sd, quantiles 1–99 %, share outside [0.45, 0.55]);
  - coverage.
- **Excluded:** PnL, fees, Sharpe, entries and spot.

## 8. Uncertainty (frozen)

- **ISO-week block bootstrap** of the outer rows. Whole ISO weeks are resampled with replacement.
- Each mean difference is a ratio of week sums. The two venues' outer weeks do not overlap in time.
- B = 2000; seed `20261124`; percentiles 2.5 / 97.5.
- A draw is valid if its difference is finite; at least 1,900 valid draws are required.
- The same draws serve every pair.

## 9. Routes (frozen; primary pair ADAPTIVE_OCC − B1)

1. **`ADAPTIVE_OCC_IMPLEMENTATION_INVALID`:** fewer than 1,900 valid draws. A design, manifest, pin, support, feature-digest or evaluator-digest mismatch refuses the run before any outcome; a missing prediction aborts it.
2. **`ADAPTIVE_OCC_WORSE_THAN_BASELINE`:** the whole ΔBrier interval > 0.
3. **`ADAPTIVE_OCC_FORECAST_SKILL_SUPPORTED`:** all of:
   - ΔBrier < 0 and its whole interval < 0;
   - ΔLogLoss point < 0;
   - ADAPTIVE's calibration slope ≥ 0.
4. **`ADAPTIVE_OCC_FORECAST_SKILL_UNCERTAIN`:** ΔBrier point < 0 otherwise.
5. **`ADAPTIVE_OCC_NO_INCREMENTAL_SKILL`:** otherwise.

**Frozen qualifier (always reported, not a route):** ADAPTIVE − STATIC_OCC_4H on Brier.
- `ADAPTIVE_BETTER_THAN_STATIC_OCC4`: interval < 0.
- `ADAPTIVE_WORSE_THAN_STATIC_OCC4`: interval > 0.
- `ADAPTIVE_NOT_DISTINGUISHED_FROM_STATIC_OCC4`: otherwise.

**SUPPORTED without BETTER** means the gain over B1 is not shown to come from the *adaptation*; a static OCC_4H could explain it.

There is no magnitude threshold and no accuracy target.

## 10. Synthetic power check (outcome-free; done in the preflight)

- **Inputs:** the real features, schedule, models, selector and bootstrap of all 361,949 rows.
- **Synthetic outcome:** R_syn(T) = (sum of the next 12 per-bar N(0,1) innovations on each era's own grid)/√12 + β·g(T).
  - g is the standardized OCC config active in T's 52-week period.
  - Overlapping anchors share noise exactly as real 1h targets do.
- **Scenarios** (seeds 4242, 4243, 4244; β = 0.03):
  - NULL;
  - CONSTANT_OCC_4H;
  - SWITCHING_OCC_2H_8H: OCC_2H and OCC_8H alternate every 52 weeks, a world built to reward adaptation.
- **Size of the planted signal:** β = 0.03 on a standardized OCC is an RP4H-size association. That is 1.5–3× the real OCC_4H increment over B1 recorded so far: +0.011 on BitMEX, −0.002 on 2025–26. So this check is optimistic.

| scenario | route | ADAPTIVE − B1 ΔBrier [95 %] | ADAPTIVE − STATIC_OCC4 | STATIC_OCC4 − B1 | ADAPTIVE − MM_NO_OCC |
|---|---|---|---|---|---|
| NULL | WORSE | +1.54e-4 [+7.4e-5, +2.30e-4] | +1.51e-4 [+7.5e-5, +2.27e-4] | +2.3e-6 [−1.3e-5, +1.9e-5] | +7.3e-5 [+3.1e-5, +1.12e-4] |
| CONSTANT_OCC_4H | WORSE | +8.7e-5 [+1.1e-5, +1.70e-4] | +1.44e-4 [+7.3e-5, +2.20e-4] | −5.6e-5 [−9.6e-5, −1.6e-5] | −1.2e-5 [−6.4e-5, +4.3e-5] |
| SWITCHING_OCC_2H_8H | WORSE | +1.20e-4 [+3.0e-5, +2.08e-4] | +1.23e-4 [+3.3e-5, +2.14e-4] | −3.2e-6 [−3.0e-5, +2.4e-5] | +4.7e-5 [+2.9e-6, +9.4e-5] |

**Selection shares:**

| scenario | NO_OCC | 1H | 2H | 3H | 4H | 6H | 8H | 12H | memory 26 / 52 / 104 |
|---|---|---|---|---|---|---|---|---|---|
| NULL | 14 % | 5 % | 16 % | 18 % | 5 % | 12 % | 6 % | 23 % | 28 % / 30 % / 42 % |
| CONSTANT_OCC_4H | 5 % | 13 % | 5 % | 14 % | 34 % | 13 % | 12 % | 5 % | 23 % / 31 % / 47 % |
| SWITCHING_OCC_2H_8H | 13 % | 11 % | 15 % | 6 % | 8 % | 14 % | 18 % | 15 % | 26 % / 34 % / 40 % |

**Reading, recorded before any real outcome:**
- **The primary route has no power to show skill at this signal-to-noise.** ADAPTIVE is WORSE than B1 in all three worlds:
  - in NULL;
  - in CONSTANT_OCC_4H, where a static OCC_4H is detectably better than B1;
  - in SWITCHING_OCC_2H_8H, the world built to reward adaptation.
- **The cost of adapting exceeds the gain.** Three sources:
  - trailing memories estimate with fewer rows than the expanding B1;
  - choosing among 24 candidates on 24 weeks of overlapping 1h targets is noisy;
  - in SWITCHING the selector does not find the planted lookback (2H 15 %, 8H 18 %).
- **Pre-registered interpretation rule:** a real `NO_INCREMENTAL_SKILL` or `WORSE_THAN_BASELINE` can **not** be read as "occupancy has no adaptive timescale" or "the timescale does not move". It only says that this algorithm cannot pay for its own variance at this signal strength. Only `SUPPORTED`, or `UNCERTAIN` with ADAPTIVE − STATIC_OCC4 < 0, would be informative.
- **Owner options before GO** (outcome-free information) are in §11. This design is frozen as the owner specified it; any change would be a formal amendment before any outcome.

## 11. Owner options before GO (outcome-free information; not part of this design)

Two outcome-free checks were run on the same rows, schedule, seeds and bootstrap: a candidate amendment and a stronger planted signal. Scratch code only; neither is part of this design.

**(a) Amendment option: add an EXPANDING memory to the candidates** (32 candidates; B1 and STATIC_OCC_4H become candidates). β = 0.03.

| scenario | route | ADAPTIVE − B1 | ADAPTIVE − STATIC_OCC4 | EXPANDING chosen |
|---|---|---|---|---|
| NULL | WORSE | +9.7e-5 [+3.4e-5, +1.60e-4] | +9.5e-5 [+3.3e-5, +1.56e-4] | 64 % |
| CONSTANT_OCC_4H | NONE | +3.1e-5 [−3.3e-5, +9.7e-5] | +8.7e-5 [+3.5e-5, +1.44e-4] | 65 % |
| SWITCHING_OCC_2H_8H | NONE | +4.6e-5 [−3.2e-5, +1.22e-4] | +4.9e-5 [−3.0e-5, +1.25e-4] | 64 % |

It removes part of the memory cost, but the selection among lookbacks still costs more than it finds. ADAPTIVE is never better than B1 or than STATIC_OCC4. **Not recommended;** it does not restore power.

**(b) The frozen design under a doubled signal,** β = 0.06 (3–6× the real OCC_4H increment recorded so far):

| scenario | route | ADAPTIVE − B1 | ADAPTIVE − STATIC_OCC4 | STATIC_OCC4 − B1 | lookback shares |
|---|---|---|---|---|---|
| CONSTANT_OCC_4H | SUPPORTED | −1.51e-4 [−2.60e-4, −3.6e-5] | +1.33e-4 [+7.1e-5, +2.00e-4] | −2.84e-4 [−3.76e-4, −1.89e-4] | 4H 72 % |
| SWITCHING_OCC_2H_8H | NONE | +3.7e-5 [−7.7e-5, +1.40e-4] | +7.7e-5 [−3.5e-5, +1.80e-4] | −4.0e-5 [−8.2e-5, +4.4e-6] | 2H 39 %, 8H 43 % |

- **With a large constant signal the route can fire,** but then a static OCC_4H is clearly better than the adaptive one.
- **In the world built for adaptation,** the selector does find the two planted lookbacks. It still does not beat B1 or the static model.

**Architect's reading for the owner (outcome-free):**
- At this market's signal-to-noise, retrospective selection of the occupancy timescale over 1h direction cannot show a gain from *adaptation* with this algorithm, even in a favourable synthetic world.
- A real run would most likely return WORSE or NONE, which §10 forbids reading as evidence about the market.
- It would also add 78 DIRECTION cells on three surfaces.
- **Options:**
  - **GO as frozen,** under the §10 rule;
  - **no run,** recording this power check as the unit's outcome-free answer;
  - **a different question** with more signal per decision, by a new design.

  Amendment (a) is not recommended.

## 12. What would change the reading

- **SUPPORTED with BETTER than STATIC_OCC4:** a past-only occupancy-timescale selector adds out-of-sample probability skill beyond B1 and beyond a fixed 4h. A prospective test would be the next step, by a separate owner decision.
- **SUPPORTED without BETTER:** OCC information helps; adaptation is not shown.
- **UNCERTAIN / NONE / WORSE:** read under the §10 rule. The algorithm does not pay for its variance; nothing is said about the market's timescale.

None of these validates a trading edge.

## 13. Exposure record (before freeze)

Read-only audit of the records, the code and the Cursor branches. Nothing was computed on an outcome.

| question | BitMEX 2016–19 | CORE 2020–24 | Binance 2025–26 |
|---|---|---|---|
| OCC_4H → R_1H \| B1 (or B0) | read (OCC replication, PRIMARY \| B1) | read (DSS V2, \| B0 only) | read (OCC modern, PRIMARY \| B1) |
| OCC_L → R_1H for L ≠ 4 | never read | never read | never read |
| B1 quantities → R_1H | read (Unit A, Cursor twin, OCC replication) | read (atlas, DSS V2, Bybit same-period read, analogues) | read (Unit B, Cursor twin, OCC modern) |
| out-of-sample Brier / log loss of any model on these features at 1h | none recorded | none recorded | none recorded |

- **Adjacent reads:**
  - DSS V2's variant OCC_THIRDS_4H (CORE);
  - the pre-impulse atlas' close_pos_4h, frac_near_* and midpoint_slope_4h (CORE);
  - RP4H at 4h everywhere.
- **Surface classes (rules §3):** all three surfaces are `DISCOVERY_REUSABLE` for this question. OCC_4H and B1 were read on each, and the motivation came from the OCC_4H reads. There is no `QUESTION_FRESH_REPLICATION` and no pristine claim. Out-of-time is not out-of-question.
- **Exposure added when the run reads outcomes:** DIRECTION, family PRICE_STRUCTURE.
  - On each of BitMEX 2016–19, CORE 2020–24 and Binance 2025–26: 26 cells, i.e. 24 candidates (8 configurations × 3 memories) plus the two expanding logistic systems.
  - That is 78 cells in total. Search penalty: the adaptive search confirms nothing by itself (rules §4).
- **Overlap with Track A, disclosed:**
  - Cursor's frozen, unrun RANGE_POSITION_4H_FORECAST_PROTOTYPE_V1 (A2 port `60b6209b`, `OWNER_GO = false`) scores a logistic model with RP4H against climatology on BitMEX and Binance 2025–26.
  - This unit's diagnostic pair B1 − CLIM is close to that question.
  - The two tracks do not use each other's outcomes. The owner sequences them.
- **Overlap with ADAPTIVE_B1_FORECAST_V1 (draft, not frozen):** its STATIC and CLIM arms equal this unit's B1 and CLIM arms, except that it pools venues in training.

## 14. Leakage and correctness tests (synthetic; `tests/research/test_adaptive_occupancy_v1.py`)

- **OCC_L definition:**
  - OCC_4H = DSS V2 F2a;
  - past-only: the future and the current close do not change it;
  - undefined with < n bars, a flat box or a hole.
- **Bar index:** the RP4H identity detects a one-bar shift.
- **Schedule:** per venue, on Mondays, with enough history; memory eligibility; the selection order (Brier, then log loss, then NO_OCC, longer memory, shorter lookback).
- **Nesting:**
  - flipping every label not realized by S (S's block and later) leaves S's predictions of every system and its selection unchanged;
  - the label realized exactly at S is used.
- **Venue isolation:** flipping all BitMEX labels leaves every Binance outer prediction unchanged.
- **ADAPTIVE:** in each block it equals the chosen frozen candidate's prediction; outer predictions are complete; a planted OCC signal is selected.
- **Digests:** the feature digest is unchanged when R_1H or Y changes.
- **Routes:** routes and the qualifier as frozen.
- **One-shot:** run refusals (no `--go`, pins unset, an existing result or attempt journal); the attempt journal is write-once.
- **Guard:** the imported constants match.

## 15. Execution and artifacts

- **Code:** `scripts/research/adaptive_occupancy_v1/` (constants, features, surfaces, walkforward, evaluate, report).
- **`preflight`:** outcome-blind. It produces the census, the fold and selector manifests, the design JSON, the feature digest, the evaluator digest and the synthetic power check.
- **`run --go`:** the one evaluation, after the owner's go.
  - **Refuses on:** the design SHA, the manifest SHAs, the design JSON, the feature digest, the evaluator digest, the rows or the outer blocks not matching their pins; an existing result; or an existing attempt journal.
  - **Journal:** before reading any outcome it writes `docs/research/adaptive_occupancy_timescale_v1_execution/ATTEMPT.json` (write-once). After the result it writes `COMPLETED.json`. A crashed attempt cannot be rerun without an owner decision.
  - **Result:** `docs/research/ADAPTIVE_OCCUPANCY_TIMESCALE_V1.{json,md}`.
- **Pins** are set in a separate commit after this design's freeze commit.

## 16. Anti-overfitting

- No lookback, memory, model, feature, block length, inner window, metric or route is added, removed or changed after any real outcome.
- No post-result rescue: no re-selection by era, venue, lookback subset or threshold, and no second run.
- A null is recorded under the §10 rule. It opens no nearby variant on these surfaces.
- No product or forecast-engine use.
