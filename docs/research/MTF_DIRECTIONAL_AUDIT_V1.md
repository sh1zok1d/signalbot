# MTF_DIRECTIONAL_AUDIT_V1 — should a multi-timeframe directional line be opened? (outcome-free audit)

**Date:** 2026-10-13. **Author:** chief architect (Track B, owner's research task).
**Recommendation:** **`DO_NOT_RUN_MTF_DIRECTIONAL_RESEARCH`.**
**Read:** code and records only, plus synthetic outcomes for the power bounds. No new directional market outcome was read. Track A, product, RANGECAST_V2 and adaptive OCC were not touched.
**Power bounds:** `MTF_DIRECTIONAL_AUDIT_V1_POWER_BOUNDS.json`, script `scripts/research/mtf_directional_audit_v1/power_bounds.py`.

## 1. What has actually been done on multi-timeframe direction

**Old Forecasting V2** (`analytics/forecasting_v2/`) was a real MTF stack on fully closed, UTC-aligned buckets (`alignment.selected_bucket`):
- **4h regime:** only the **last closed 4h bar**. Its signed move percentile vs 30 days must satisfy |2p−1| ≥ 0.40, with venue agreement ≥ 2/3 and an OI veto.
- **1h bias:** the last closed 1h bar against 7 days, |2p−1| ≥ 0.25.
- **Use:** the layers were never a predictor and never a combined score. They are **gates** on three setups:
  - TP: a 15m pullback of 0.5–3 range proxies from the 12h extreme;
  - CB: a breakout of a compressed 15m run;
  - FB: a 48h high/low cross. FB means "confirmed breakout".
- **Outcome:** the direction-aligned return at 15m–4h.

**E1-RUN-001 development** (2026-08-02 … 08-15, 147 usable rows, no intervals):

| family | variant | rows | 4h mean | positive share |
|---|---|---|---|---|
| TP | FULL | 93 | −0.205 % | 23.7 % |
| TP | NO_1H | | −0.012 % | |
| TP | NO_4H | | −0.035 % | |
| TP | NO_CONTEXT | 1,071 | −0.058 % | |
| CB | simple compression | 39 | +0.027 % | |
| CB | ordinary range breakout | 149 | negative at every horizon | |
| FB | with or without context | | adverse | |

- **Status:** all three families are `RETIRED_CURRENT_FORMULATION`; the holdout is unopened.
- **MATH-008** (the V2 register) named exactly this risk: the 4h, 1h, 15m and 5m layers may be "transformations of the same latent price impulse". The E1 TP ablations are its only execution.

**Trailing multi-scale directional reads (outcomes read):**
- **PRE_IMPULSE_STATE_ATLAS_V1** (Cursor; CORE; 50 trailing features × 1h / 4h / 8h, 24h logged; 496 cells). close_pos_4h, which equals RP4H, gives Spearman:

  | horizon | 1h | 4h | 8h | 24h |
  |---|---|---|---|---|
  | close_pos_4h | −0.0578 | −0.0450 | −0.0292 | −0.0159 |

  midpoint_slope_4h, last rejection and extension_up give about −0.04 to −0.05 at 1h. Efficiency, wick and body features are about 0. The review verdict was "interesting but trivial confound unresolved".
- **RP4H at 1h:**

  | surface | primary \| RET_4H, RV_4H | beyond the local path |
  |---|---|---|
  | Bybit | −0.028 | |
  | BitMEX | −0.047 | −0.011 |
  | Binance 2025–26 | −0.034 | −0.022 |

- **Other units:** DSS V2 (only OCC survived; it is not modernly stable; SPA and UPFRAC explained away; session clocks not separated from placebo clocks). The trend regime: not detected. H04 / B2-04 trend × pullback: rejected. Closed prior-day/week/month highs and lows as levels (DH1–DH3, level race): nothing ≥ 3 pp. The opening range: an owner-closed line.

**RANGECAST_V2** (Binance 2020–24 development; one 2025–26 read):
- **W_L1** (trailing ranges at 15m, 1h, 4h, 24h, 7d and 30d, plus activity and calendar) beats V1 on touch log loss: 4h −0.0040 [−0.0047, −0.0034], better in all four years; one-shot −0.0057 at 4h.
- **L3** adds signed returns sr_{1h,4h,24h} and positions pos_{4h,24h,7d} to **per-side excursion means**. It is worse than L1 (+0.0013 at 4h, 0 of 4 years better). The asymmetry alone vs L2 is +0.0008, with no interval.
- **LightGBM** was worse (+0.017).
- **What L3 tests:** whether signed state shifts the *size* of the up excursion relative to the down one. That is not a test of the sign of the return. It is also confounded by the shape change, about 14 extra parameters and intercept drift.

**Gap (all branches searched):** no unit has tested the shape of a **completed** UTC 1h/4h/daily candle against direction as a standalone predictor. This covers body, wick, close location, inside or engulfing bars, and HH/LL sequences of closed bars. The atlas "1h candle" features are averages of 5m candles.

## 2. What V2 refuted, and what it did not

**Refuted**, weakly (14 days, n = 93 for TP, no intervals): the exact gated stack in which the 4h regime and 1h bias, from single closed bars, filter one pullback setup or two breakout setups. FB's fresh-cross continuation was adverse with or without context.

**Not refuted:**
- closed-HTF structure as a standalone predictor;
- any representation other than the signed percentile of one bar;
- any horizon structure.

V2 also never had the power to show a small effect.

## 3. Information: is HTF new information, a representation, or an inductive bias?

**A. New information: none,** except the clock.
- A closed 1h/4h/daily candle is a deterministic function of the 5m bars plus the clock. By the data-processing inequality it carries no more information than the 5m history and the clock.
- **At the instant an HTF bar closes, its geometry coincides with features already read.** At a 4h-aligned T, the RP4H window (48 bars ending at T) *is* the closed 4h candle:
  - close location = RP4H, exactly;
  - body ≈ RET_4H;
  - range = width;
  - wicks are a function of those three.
- V2's 4h regime at that instant is a percentile transform of RET_4H. Between closes, the last closed bar is a **stale subset** of what trailing windows already hold.
- **So the only exogenous input HTF can add is clock phase:** participants coordinating on candle closes and UTC boundaries.

**B. A better representation of the same information,** i.e. multi-bar closed-candle sequences such as HH/LL and inside bars.
- These are functions of trailing windows of 8–24h. Their trailing analogues were partly read: atlas extension_up, bars_since_lower_4h, last rejection, midpoint slope.
- A closed-bar version can only differ through its clock alignment.

**C. Inductive bias / denoising for a simple model.**
- This can matter for SCALE, where the signal is large and persistent. RANGECAST shows it: volatility clustering.
- For DIRECTION the signal is so small (|ρ| ≈ 0.01–0.05) that better compression changes out-of-sample skill by second-order amounts. The OCC V2 study measured exactly this: ΔBrier SE ≈ 1.5–2e-5 against gains ≈ 2e-5.

**Test that separates A (coordination) from B/C:**
- a phase placebo: the same feature with the same window at UTC-aligned decision times vs fixed off-phase times, plus a trailing twin of equal length in the model;
- representation predicts phase invariance; coordination predicts a phase-locked excess.

## 4. What directional MTF question remains open

**1. Clock coordination at HTF closes.** Is directional predictability phase-locked to UTC 1h/4h closes?
- This is the only route to new information. Adjacent evidence is null or closed:
  - DSS V2 session clocks were not separated from placebo;
  - closed-level holds (DH1–DH3) are null;
  - the opening range is owner-closed.
- The power bound is in §5.

**2. Closed-candle shape, single or sequence.** This is a representation question only (B/C).
- The single-candle version at aligned times is RP4H/RET_4H/width, already read on CORE at 1h–24h (atlas) and replicated at 1h.

**3. Not MTF, but the more correct question the audit surfaced: the horizon term structure of the range-position reversal.**
- If the CORE 1h association (−0.058) lived only in the first hour, the 4h association would be about −0.029 (= −0.058/√4). The atlas shows −0.045.
- So roughly −0.018 of rank correlation with the 1h→4h return looks like a **delayed reversal** after the first hour. This is a CORE discovery-surface derivation; raw, uncontrolled and subject to winner's curse.
- Unlike MTF, this is one pre-specifiable relation with a numerical anchor.

## 5. Information power (outcome-free; synthetic outcomes on each surface's real grid; one pre-specified feature; no search penalty)

**MDE80**, in rank-correlation units:

| surface | 1h (any feature) | 4h, closed-HTF (block-constant) feature | 4h, aligned decisions only | 24h, closed-daily feature |
|---|---|---|---|---|
| CORE 2020–24 (exposed) | 0.012 | 0.022 | 0.028 | 0.054 |
| BitMEX 2016–19 | 0.013 | 0.025 | 0.032 | 0.061 |
| Binance 2025–26 | 0.020 | 0.034 | 0.043 | 0.100 |

**For the phase-coordination contrast** (aligned − placebo), the SE grows by about √(1 + n_aligned/n_placebo) of the aligned SE:
- MDE80 ≈ 0.015 for 1h closes on CORE, 0.03 for 4h closes on CORE and 0.035–0.045 on BitMEX.

**Plausible sizes:**
- A coordination excess would be a fraction of the known reversal, i.e. ≤ 0.01–0.015.
- An HTF increment beyond B1 at 4h would be ≤ 0.02. RP4H beyond its local path is only −0.011 / −0.022, and every slower directional state so far (SPA, UPFRAC, trend regime, OCC modern) is null.

**Conclusion of the bounds:** the replication surfaces cannot detect such effects. CORE, the only surface with near-adequate power, is the most exposed surface. It already carries the basic closed-4h relation: close location → 4h return, through the atlas.

## 6. If a test were ever run (not recommended now)

- **Object:** a phase-placebo contrast at a single horizon, the next HTF bar (4h).
  - Decisions at UTC 4h closes vs three fixed placebo phases.
  - At most 3 pre-declared closed-bar objects, each paired with a trailing twin of equal length.
- **Baseline:** B1 (RP4H, RET_4H, RV_4H, RET_1H, RET_15M), plus multi-scale ranges (RANGECAST lr_15m … lr_30d), plus the hour × weekday clock.
- **Inference:** score or likelihood-ratio tests in a fixed low-dimensional logistic model, or rank partials. Not a ΔBrier of nested models, which is inefficient. No ML model.
- **Surfaces:** discovery on BitMEX 2016–19 at 4h (only 1h reads exist there), replication on Binance 2025–26. CORE serves only as an exposed comparison.
- **Success:** the aligned − placebo excess has a CI excluding 0 on discovery and the same sign with CI on replication.
- **Closure:** the CI excludes effects ≥ MDE on BitMEX, or the phase contrast is null.
- **Cost:** about 2–4 days.
- **Expected information gain: low.** The prior probability of an effect at or above the MDE is about 10 %, and a positive would most likely be a small modulation of the known reversal.

## 7. Exposure and collisions

| surface | directional reads already on it |
|---|---|
| CORE | about 846 cells, including close_pos_4h at 1h/4h/8h/24h, H04 / B2-04 trend × pullback, levels, RANGECAST L3 per-side excursions (pos_4h/24h/7d, sr_*) |
| Bybit | same period as CORE; RP4H at 1h (Cursor) |
| BitMEX 2016–19 | 1h only (RP4H, OCC); fresh at 4h and for closed-candle shape |
| Binance spot 2017–19 | one directional cell; same period as BitMEX |
| Binance 2025–26 | about 130 cells; E1 development (closed 4h/1h context); RANGECAST one-shot (symmetric, plus a published side-specific PIT; it included the E1-development slice) |

**Collisions:**
- the owner-closed opening range / WIDTH and divergence lines, for closed-bar levels and swings;
- E1 (V2 context).

## 8. Recommendation

`DO_NOT_RUN_MTF_DIRECTIONAL_RESEARCH`:
- **No new information:** closed HTF candles add none beyond 5m and the clock. At their own close they equal features already read and replicated (RP4H, RET_4H).
- **Coordination is underpowered:** the only genuinely new channel is too weak to detect where a plausible effect would be, and its adjacent evidence is null or closed.
- **The representation gain applies to scale, not direction:** RANGECAST's gain is about scale, and the directional signal is too small for representation choice to be measurable.

The more correct open question is the **horizon term structure of the range-position reversal**: a delayed reversal from 1h to 4h.
- It is not MTF. It would need its own outcome-free adequacy gate before any read.
- Power: BitMEX roughly at the CORE-implied size, modern underpowered.
- Not started.
