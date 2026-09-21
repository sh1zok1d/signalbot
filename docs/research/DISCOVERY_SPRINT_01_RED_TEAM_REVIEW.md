# Discovery Sprint 01 — Red-Team Review

**Unit:** `DISCOVERY_SPRINT_01_RED_TEAM_REVIEW`
**Unit type:** `OUTCOME_BLIND_RED_TEAM_REVIEW`
**Date:** 2026-09-21
**Reviewed commit:** `7bb92b0bd6238693164b6592c0711fa4c15fc9fe`
**Machine-readable record:** `docs/research/DISCOVERY_SPRINT_01_RED_TEAM_REVIEW.json`

No Discovery Sprint 01 card was executed to perform this review. No
candidate performance was inspected. Protected 2025/2026 remains unopened.
No MARKET-07 was created. This review does not try to preserve
`EXECUTABLE` status for all cards — a correct compiler is allowed to
reject its own cards.

## F1 — D2/D5 data authority and legal interval — **CONFIRMED, FIXED**

Verified against the actual code and frozen artifacts:

- `robust_dislocation_z` (`scripts/research/market_06_cross_venue_dislocation_evaluator.py`)
  is a pure function of the dislocation series `d = ln(perp_close /
  spot_close)`, requiring **both** a Binance perp close and an OKX spot
  close at every timestamp. `rv_btc_24h` / `btc_ret_24h` need BTC perp
  closes only.
- Canonical retained cross-venue dataset: `MARKET_06_OKX_BINANCE_FEASIBILITY_V0`,
  snapshot `e0403e40...183e68` — 36 monthly Binance ZIPs, 1053 OKX
  history-candles HTTP bodies.
- Exact available interval: `RAW_WINDOW = [2022-01-01T00:00:00Z,
  2025-01-01T00:00:00Z)` (frozen prereg), with the evaluator's own
  `TRAIN_START_T = 2022-02-01T00:05:00Z` already building in the
  30-day reference-window lookback margin.

**Confirmed:** MARKET-06 cross-venue data covers only 2022-2024. D2
`RULE_2` (`DISLOCATION_ABSTENTION`) and D5 cannot legally claim
2020-02→2025-01.

**Fix (outcome-blind):**

- `RULE_1` (RV-only, `CORE_BTC_BINANCE_V0` only): interval unchanged,
  2020-02-01 → 2025-01-01.
- `RULE_2`: interval corrected to **2022-02-01T00:05:00Z →
  2025-01-01T00:00:00Z** (reuses the frozen MARKET-06 `TRAIN_START_T`
  verbatim), dataset authority bound explicitly to
  `MARKET_06_OKX_BINANCE_FEASIBILITY_V0` (snapshot `e0403e40...183e68`),
  read-only, not modified.
- D5: interval corrected to the common overlap, **2022-02-01 →
  2025-01-01** (RULE_2 is the binding constraint).
- No 2020-2021 dislocation observations are fabricated or proxied;
  `RULE_1` alone still covers that span within D2.

## F2 — D2/D5 base exposure schedule — **CONFIRMED (underspecified), FIXED**

A coherent schedule already exists in the reused MARKET-06 machinery
(`_construct_row` / `arithmetic_mae`), but the prior compiled spec only
referenced it loosely. Now frozen explicitly:

- **Base exposure:** a full-size BTC perp position in direction
  `BTC_SIDE(t)` from entry through the 288-bar/24h window — abstain =
  skip that exact position; exposed = take exactly that position.
- **Direction:** `BTC_SIDE(t) = sign(ln(P_perp(E)/P_perp(E-24h)))`, closes
  ending at feature cutoff `E = T - 5m` (reused verbatim). Zero-return
  rows are already ineligible.
- **Legal knowledge time:** strictly before decision time `T` (restates
  the existing no-lookahead invariant).
- **Severity metric:** `arithmetic_mae(BTC_SIDE, entry, future_288_bars)`,
  reused verbatim — always ≥ 0.
- D2/D5 abstain from exactly this schedule.

## F3 — D3 null granularity mismatch — **CONFIRMED, mechanically broken as written, FIXED**

D1's null (GARCH(1,1) on the 24h-return series) produces exactly **one**
scalar surrogate return per day. D3's functionals all require the full
288×5m intra-24h path. Reusing D1's null for D3, as the prior compilation
stated, is mechanically impossible.

**Fix:** a new, native-granularity null — `5m_RETURN_POOLED_CIRCULAR_BLOCK_BOOTSTRAP`.
Pool every 5-minute log return in the discovery interval; for each
surrogate day, circular block-bootstrap this pooled sequence (block
length 12 bars ≈ 1h) to assemble a synthetic 288-bar path from a fixed
starting price. This preserves the empirical 5m-return marginal
distribution and short-range (≤1h) autocorrelation/clustering exactly
(blocks are real sub-sequences, not simulated); it destroys date-specific
conditioning and >1h cross-block dependency — appropriate for D3's
`UNCONDITIONAL_DESIGN`. 1000 replicates, seed
`D3_NULL_SURROGATE_SEED = 20260921103` (retained, now attached to this
null instead of D1's). Companion stability checks at block lengths 6 and
24 (frozen, not free-choice). This is not an invented bridge — it is the
standard nonparametric block-bootstrap applied at native frequency.

## F4 — D4 lead-lag null — **CONFIRMED, FIXED**

The original `BLOCK_BOOTSTRAP_PAIRED_RETURNS` null resamples contiguous
blocks of the *paired* (BTC,ETH) vector — the true `BTC(t)→ETH(t+1)`
relationship survives intact inside every block and therefore inside
every replicate, making it an inadequate (near-tautological) null for
`LEAD_LAG_1DAY` specifically.

**Fix — split by statistic:**

- `ROLLING_CORRELATION_90D`: **retains** the paired block-bootstrap
  (block length 20 days ≪ the 90-day rolling window) — separately
  justified, since it tests whether rolling-correlation variability
  exceeds what reordering genuine ~20-day co-movement chunks would
  produce, a longer-horizon question distinct from the 1-day lag.
- `LEAD_LAG_1DAY`: **replaced** with `INDEPENDENT_BLOCK_BOOTSTRAP` — BTC
  and ETH daily-return series block-bootstrapped **separately** (each its
  own independent draw, block length 20 days), preserving each series'
  own short-memory structure while destroying the true cross-series
  pairing (and thus the true 1-day lag) by construction. 1000 replicates,
  seed `D4_LEAD_LAG_NULL_SEED = 20260921107` (new; `D4_NULL_SEED =
  20260921104` retained for `ROLLING_CORRELATION_90D` only).

## F5 — D1 null adequacy — **CONFIRMED unverified assertion**

The prior compilation asserted GARCH(1,1) was "defensible" by generic
appeal to standard practice, without defining or running any check. Not
acceptable on assertion alone.

**Fix:** a `D1_NULL_ADEQUACY_GATE` is now defined, computed on **non-target
summary statistics only** (never `MEAN_STATE_RUN_LENGTH` or the state
labels): return marginal skew/kurtosis; return ACF at lags 1-5;
absolute-return ACF at short lags 1-10 (must match — ordinary vol
clustering, not under test); absolute-return ACF at lags 20+ (divergence
here is *expected*, not disqualifying — that's the tested structure);
leverage/asymmetry proxy; and RV_20 mean/variance/short-lag ACF only
(using the corrected F6 formula). All must fall within the surrogate
replicate distribution's [5th, 95th] percentile band, or GARCH(1,1) is
rejected as inadequate.

**This gate has not been executed** — doing so requires real numerical
computation on non-target statistics, out of scope for this spec-level
review (no data was loaded). **D1 → `BLOCKED_PENDING_PRE_OUTCOME_FIX`**
until the gate is run and passed. The gate may never be adjusted after
seeing D1's actual target outcome.

## F6 — D1 RV_20 definition — **CONFIRMED, FIXED**

The prior spec defined `RV_20 = sum of 20 trailing ev.rv_btc_24h values` —
each already a within-day `sqrt(sum of squared 5m returns)`. Summing
already-square-rooted values (L1 aggregation) is **not** the same object
as conventional trailing-20-day realized volatility, which aggregates at
the variance (squared) level before a single final sqrt (L2 aggregation).
By Jensen's inequality these differ systematically. The card's own prose
throughout intended conventional realized volatility — this is a genuine
unintended formula defect.

**Fix:** `RV_20(t) := sqrt( Σ_{i=0}^{19} [ev.rv_btc_24h(t-i)]² )` —
variance-level aggregation, consistent with how `rv_btc_24h` itself
aggregates within a day, simply extended to 20 days. No outcome was
inspected to make this correction.

## F7 — D6 source/target identifiability — **CONFIRMED partial defect + genuine usefulness problem**

The prior spec named the source but did not pin an exact URL/archived
snapshot/retrieval date, and did not mathematically define "local max /
cycle top," the search window, tie handling, or multiple-crossover
handling.

**Partial fix:**

- `LOCAL_MAX`: maximum daily close within `[crossover_date,
  min(crossover_date + 365d, 2025-01-01))` (frozen, truncated at the
  protected-2025 boundary).
- Ties: earliest date wins (frozen convention).
- Multiple crossovers: counted only if preceded by ≥30 days with the
  111-day SMA strictly below 2×350-day SMA (frozen debounce rule); every
  debounced event is reported, none cherry-picked.
- **Immutable source pin remains only partially resolved** — no
  archived/Wayback-style snapshot URL + retrieval timestamp has been
  captured; this is an open pre-execution action item.

**Usefulness assessment:** `CORE_BTC_BINANCE_V0` begins 2020-01-01; the
source's own cited coincidences are 2013, 2017, 2021. At most **one**
testable episode (2021) falls inside available data. A benchmark resting
on a single instance has essentially no statistical calibration power —
a hit doesn't rule out a high false-positive rate, a miss doesn't
establish over-conservatism. Applying the same standard the Promising
Prototype Gate applies elsewhere (disqualifying one-isolated-instance
results) to this diagnostic card itself:

**Decision: DEFER D6.** A replacement external benchmark, testable with
materially more than one episode inside 2020-2025 and selected without
any Signalbot outcome inspection, is required. Selecting that replacement
is explicitly **out of scope** for this review.

## Final classification

| Card | Status | Reason |
|---|---|---|
| D1 | `BLOCKED_PENDING_PRE_OUTCOME_FIX` | RV_20 corrected (F6); `D1_NULL_ADEQUACY_GATE` defined (F5) but not yet executed/passed |
| D2 | `EXECUTABLE_DISCOVERY_SPEC` | F1 (per-rule interval split + dataset authority) and F2 (explicit exposure schedule) fixed |
| D3 | `EXECUTABLE_DISCOVERY_SPEC` | F3 fixed — new native-5m pooled block-bootstrap null |
| D4 | `EXECUTABLE_DISCOVERY_SPEC` | F4 fixed — split null by statistic |
| D5 | `EXECUTABLE_DISCOVERY_SPEC` | Inherits F1 (2022-02→2025-01 overlap) and F2 fixes from D2 |
| D6 | `DEFERRED` | F7 — at most one testable episode; insufficient diagnostic power; source pin incomplete |

## Hard findings

1. **F1 confirmed & fixed** — D2 `RULE_2`/D5 restricted to 2022-02-01 →
   2025-01-01; cross-venue dataset authority bound
   (`MARKET_06_OKX_BINANCE_FEASIBILITY_V0`, snapshot `e0403e40...`).
2. **F2 confirmed (underspecification) & fixed** — base exposure
   schedule, direction, knowledge time, severity metric made explicit.
3. **F3 confirmed (mechanically broken) & fixed** — D3 given its own
   native-granularity null.
4. **F4 confirmed & fixed** — `LEAD_LAG_1DAY` given an independent-block
   null distinct from `ROLLING_CORRELATION_90D`'s paired-block null.
5. **F5 confirmed (unverified assertion)** — adequacy gate defined, not
   executed; D1 blocked.
6. **F6 confirmed & fixed** — RV_20 corrected to variance-level
   aggregation.
7. **F7 confirmed (partial defect + usefulness problem)** — mathematical
   definitions added; source pin incomplete; D6 deferred.

## Final report

```
D1_STATUS = BLOCKED_PENDING_PRE_OUTCOME_FIX
D2_STATUS = EXECUTABLE_DISCOVERY_SPEC
D3_STATUS = EXECUTABLE_DISCOVERY_SPEC
D4_STATUS = EXECUTABLE_DISCOVERY_SPEC
D5_STATUS = EXECUTABLE_DISCOVERY_SPEC
D6_STATUS = DEFERRED

HARD_FINDINGS  = F1 CONFIRMED+FIXED, F2 CONFIRMED(underspec)+FIXED, F3 CONFIRMED(broken)+FIXED,
                 F4 CONFIRMED+FIXED, F5 CONFIRMED(unverified assertion)+GATE DEFINED NOT RUN,
                 F6 CONFIRMED+FIXED, F7 CONFIRMED(partial defect + usefulness problem)
FIXES_APPLIED  = D2/D5 per-rule interval split + dataset authority binding (F1);
                 D2/D5 explicit base exposure schedule (F2);
                 D3 native-5m pooled circular block-bootstrap null (F3);
                 D4 split null: independent-block for LEAD_LAG_1DAY, paired-block retained for
                 ROLLING_CORRELATION_90D (F4);
                 D1 RV_20 corrected to variance-level aggregation (F6)
DEFERRED       = D6

SCIENTIFIC_OUTCOMES_COMPUTED   = false
CANDIDATE_PERFORMANCE_INSPECTED = false
PROTECTED_2025_OPENED          = false
PROTECTED_2026_OPENED          = false
MARKET_07_CREATED              = false

EXECUTION_AUTHORIZED = PARTIAL — D2, D3, D4, D5 only.
                       D1 NOT authorized (blocked pending D1_NULL_ADEQUACY_GATE execution).
                       D6 NOT authorized (deferred pending replacement benchmark selection).
NEXT_UNIT = DISCOVERY_SPRINT_01_PARTIAL_EXECUTION_D2_D3_D4_D5,
            gated separately on D1_NULL_ADEQUACY_GATE_EXECUTION
            and D6_REPLACEMENT_BENCHMARK_SELECTION
```
