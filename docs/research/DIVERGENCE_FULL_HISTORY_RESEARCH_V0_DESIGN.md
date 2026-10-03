# Divergence full-history research V0 — frozen design

**Status:** `FROZEN_BEFORE_ANY_2025_PLUS_BYTE`
**Date:** 2026-10-02
**Machine twin:** `DIVERGENCE_FULL_HISTORY_RESEARCH_V0_DESIGN.json`. It is authoritative and binds code and frozen-artifact hashes.
**Kind:** a research and discovery program. It is never one independent confirmatory test over 2023–2026.

## Slices (labels are mandatory in every report)

| Slice | Decisions | Label | Role |
|---|---|---|---|
| Discovery | 2023-01-01 .. 2024-12-28 | `DISCOVERY / PREVIOUSLY OBSERVED` | estimation and mechanism research; never independent validation evidence |
| Validation | 2025-01-01 .. 2026-08-11 | `VALIDATION / PREVIOUSLY UNSEEN` | the only source of an independent validation statement; evaluated once |
| Pooled | both | `POOLED FULL HISTORY` | estimation, mechanism, stability and heterogeneity; never replication, confirmation or fresh holdout evidence |

Decisions in (2024-12-28, 2025-01-01) belong to no slice, because their windows would straddle the two slices.

## E1 boundary (derived mechanically)

**E1-RUN-001 holdout:** `[2026-08-16T00:00Z, 2026-08-25T17:20Z)`.

**Forward reads.** The longest forward read is T + 96h, covering the brackets, forward return, MFE/MAE and time-to measures.

**Lookback reads all end before T:**
- detector warm-up;
- the 720h book baseline;
- the OI windows: 24h, the leg and 6h;
- the 720h volume baseline;
- EMA168 and the 7-day return;
- 24h market returns.

**Cutoffs:**
- **last decision** = E1 start − 96h − 24h margin = **2026-08-11T00:00Z**;
- **read horizon** = **2026-08-15T00:00Z**, exclusive.

**Archive objects:**
- monthly klines only through 2026-07, because the 2026-08 monthly file contains E1 bytes;
- daily klines, bookDepth and OI metrics only through 2026-08-14.

**Detector guard.** The SEED-0001 detector refuses windows that reach 2025. Inside a scoped context only, its guard constant is replaced by the E1 holdout start. The detector logic is unchanged.

## Panel, detector, arms

**Panel:** BTC, ETH, SOL, XRP, BNB and DOGE UM perps. It is fixed.

**Detector:** SEED-0001 V1, unchanged. Discovery episodes must reproduce the V0 per-symbol digests.

**Arms (definitions unchanged):**
- A = support + regular bullish divergence;
- B = support only;
- C = divergence only;
- D = neither.

## Estimands

| Role | Contrast | Question |
|---|---|---|
| primary practical | `A − B` | Conditional on support, does divergence improve the subsequent trading outcome? It is not an interaction. |
| secondary mechanistic | `(A − B) − (C − D)` | Does the contribution of divergence differ with support present? |
| descriptive | `A − D`, `C − D` | context and support necessity; never promoted |

The primary outcome is `Y1_48H`, +1R before −1R within 48h.

## Outcomes (frozen)

**Bracket (SEED-0001):**
- entry at the close of bar i+3;
- stop when low < low_i; target at E + kR;
- same minute = stop; timeout = neutral;
- Y1 and Y2 at 48h and 96h.

**Costs:** 0.10% round trip, with `COST_R = 0.0010·E/R`.

**Net R:** k on WIN, −1 on LOSS, FWD_R on timeout, each minus COST_R.

**Continuous outcomes:**
- FWD_RET and FWD_R;
- MFE_R and MAE_R, each at 48h and 96h;
- time to MFE and time to MAE;
- time to +1R and time to −1R.

**Resolution:** 1m bars. A missing minute makes that window unavailable.

## Mechanism-feature registry (point-in-time research covariates, never selection rules)

There are 22 features. The JSON twin holds the exact definitions.

| Group | Features |
|---|---|
| Divergence strength | RSI14 and RSI21 deltas, MACD delta in ATR, CVD share over the second leg |
| Structure | leg depth, new-low depth, pivot spacing |
| Support | support excess over P80, book imbalance at the low |
| Flow | net flow over 24h, change in selling pressure between legs, flow after the low |
| OI (5m metrics, available at bucket end) | OI change over 24h, OI change over the leg |
| Liquidation proxy | defined explicitly: OI −1% over 6h together with a 3× volume spike |
| Volatility and trend | log RV24, ATR%, distance from EMA168 in ATR, 7-day return, new-30-day-low depth |
| Market | panel 24h return, BTC 24h return |

**Pre-specified mechanism state:** `DEEPER_STATE_FLOW_OI` = selling weakened into the new low AND OI did not expand. It has no oscillator input.

## Inference

**Model.**
- OLS (a linear probability model for binary outcomes);
- arm dummies with D as reference;
- symbol fixed effects;
- the SEED-0001 covariates;
- pooled models add a slice fixed effect.

**Variance.**
- CR1 with panel-wide UTC-week clusters: all symbols in a week share one cluster, so cross-symbol episodes are never independent.
- The t reference uses G − 1 degrees of freedom.

**Primary A − B bootstrap:** 4999 whole-week resamples, seed 20261007.

**Validation labels.** A list of tags, never a forced pass or fail:
- `INCONCLUSIVE_SAMPLE`;
- `SAME_DIRECTION` or `OPPOSITE_DIRECTION` (against discovery);
- `COMPATIBLE_WITH_ZERO` or `DISTINGUISHABLE_FROM_ZERO`;
- `AT_OR_ABOVE_MEOI` or `BELOW_MEOI` (MEOI is 0.15);
- `ECONOMICALLY_SMALL`;
- `HETEROGENEOUS_ACROSS_SYMBOLS` or `NO_DETECTED_SYMBOL_HETEROGENEITY`.

## Stages (never intermingled)

1. **Validation, evaluated once.**
   - **Validation slice:** counts, arm summaries, every outcome model, the bootstrap, results by symbol and by half-year, and labels.
   - **Discovery slice:** the same frozen model, for comparison.
   - **Persistence:** the result JSON and the per-episode validation CSV are written and committed before stage 2. A second stage-1 run is refused.
2. **Pooled and mechanism, labelled exploratory.**
   - **Pooled models** with a slice fixed effect, and the validation-minus-discovery differences.
   - **Breakdowns** by year and by symbol, with heterogeneity tests.
   - **Feature SMDs** and missingness.
   - **Within-support models:**
     - M0: divergence;
     - M1: divergence plus mechanism features;
     - M2: oscillator families;
     - M3: the deeper state.
   - **Failure states** within A and within B, with Holm.
   - **Reproduction check:** stage 2 first verifies that the validation episodes reproduce the persisted CSV.

## Prohibited after opening

- Changing the detector, rules, arms, thresholds, horizons, outcomes, costs, entry, stop or target.
- Changing the symbol panel.
- Selecting subgroups or filters as results.
- Searching thresholds combinatorially.
- A second validation evaluation.
- Presenting pooled results as replication or confirmation.
- Promoting `A − D` or an exploratory model to the primary.
- Activating the V1 prospective continuation.
- Creating SEED-0003.

## Unchanged

- SEED-0001 artifacts.
- V0 and V1 feasibility.
- E1-RUN-001.
- D2's history.

Their hashes are bound in the JSON twin and re-verified by the runner before each stage.
