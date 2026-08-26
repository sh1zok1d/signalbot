# H01 Compression → Volatility Expansion — Preregistration

**Status:** PREREGISTERED / EXPLORATORY  
**Hypothesis ID:** `H01_COMPRESSION_EXPANSION`  
**Machine-readable freeze:** `docs/research/H01_COMPRESSION_EXPANSION_PREREG.json`  
**Dataset:** `CORE_BTC_BINANCE_V0` snapshot `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`

This document is frozen **before** any H01 development forward outcomes are computed. A clean null is a successful research result. This is not a directional edge, trading, or confirmatory claim.

## 1. Research question

Does unusually low recent BTC realized volatility relative to its own recent history predict a subsequent increase in realized volatility?

Non-directional mechanism test only. Not LONG vs SHORT, PnL, breakout direction, entries/exits, leverage, or forecasting-product logic.

## 2. Mechanism rationale (not evidence)

Markets sometimes enter periods where short-horizon realized volatility is unusually low versus the immediately preceding local regime. If that is temporary compression rather than a persistent low-vol state, sufficiently strong compression may be followed by a higher probability/magnitude of volatility expansion.

Volatility regimes fluctuate; short-term RV can undershoot the local regime; quiet periods may precede larger movement. This is a rationale only.

## 3. Dataset and information at T

Use accepted CORE_BTC_BINANCE_V0 1m canonical bars only.

At decision time T use only bars with `available_at <= T`. No close_time shortcut. No OI, funding, liquidations, other exchanges, or future bars.

Price/volume canonical columns are decimal strings. Parse with `float(Decimal(...))` before arithmetic. Never compare them lexicographically.

Fail closed if the repository manifest snapshot_id differs from the freeze above.

## 4. Chronological windows (UTC)

| Window | Start inclusive | End exclusive | Outcome inspection |
|---|---|---|---|
| Warmup | 2020-01-01T00:00:00Z | 2020-02-01T00:00:00Z | features only |
| Development / discovery | 2020-02-01T00:00:00Z | 2025-01-01T00:00:00Z | allowed |
| Reserved validation | 2025-01-01T00:00:00Z | 2026-01-01T00:00:00Z | **forbidden** |
| Untouched OOS | 2026-01-01T00:00:00Z | 2026-08-26T00:00:00Z | **forbidden** |

Every development event must satisfy `T + 240m < 2025-01-01T00:00:00Z`. The development runner must not open 2025/2026 canonical partitions.

## 5. Decision grid

Evaluate only UTC-epoch-aligned 15-minute boundaries (`00:00`, `00:15`, …). Do not treat every 1m row as an independent setup.

## 6. Compression definition

`r_t = ln(close_t / close_{t-1})` using returns completely known by T.

Recent realized vol for lookback L:

`RV_L(T) = sqrt(sum r^2)` over the last L complete 1m returns known by T.

Lookbacks frozen: **30, 60, 120** minutes. No other L in H01.

## 7. Reference distribution

For each L, compare `RV_L(T)` to the same L on the same 15m grid over the **30 calendar days immediately preceding T**. Exclude the current observation. No full-dataset, year-wide, or 2025/2026 normalization.

Compression percentile (0–100, lower = stronger compression), midrank:

`C_L(T) = 100 * (#{ref < RV_L(T)} + 0.5 * #{ref == RV_L(T)}) / N_ref`

Candidate: `C_L(T) <= 100 * q` with **q ∈ {0.10, 0.20, 0.30}**. Do not add 0.05/0.15/0.25 after seeing results.

## 8. Horizons and outcomes

Horizons H frozen: **15, 30, 60, 120, 240** minutes.

Future RV uses 1m log returns on bars whose `available_at` lies in `(T, T+H]`. All required bars must be complete.

`PAST_MEDIAN_RV_H(T)` = median of `FUTURE_RV_H` on the same 15m grid in the preceding 30 days whose outcome is known by T (`t + H <= T`).

**Primary:** `NORMALIZED_FUTURE_RV_H = FUTURE_RV_H(T) / PAST_MEDIAN_RV_H(T)`

Do **not** use `future_RV / current_compressed_RV` as primary (mechanical ratio).

**Secondary expansion:** `PAST_Q75_RV_H(T)` from the same known-by-T 30-day history. `EXPANSION_H = 1` iff `FUTURE_RV_H(T) >= PAST_Q75_RV_H(T)`. Report `P(EXPANSION_H | compression)`. Do not change Q75 after outcomes.

**Secondary range:** `FUTURE_RANGE_H = ln(max(high)/min(low))` over the same future bars, divided by the trailing 30-day median of that statistic known at T. Range alone cannot promote H01.

## 9. Baselines, controls, dependence

- **Baseline A:** unconditional eligible development 15m boundaries (complete L, H, and scale).
- **Baseline B:** matched-random timing; preserve each calendar month’s candidate count; seed **20260826**; **100** replicates.
- **Negative control:** within each calendar month, deterministically permute compression scores across eligible 15m boundaries; seed **20260827**. Same threshold analysis. Direction inversion is not used.
- **Uncertainty:** UTC-week block bootstrap, seed **20260828**, **2000** replicates, 95% interval for candidate minus baseline A on normalized future RV and on expansion probability.
- Report raw N, unique UTC days/weeks/months, per-year and per-month counts, top-5 month share, max single-month share, consecutive qualifying-boundary clustering. Do not treat overlapping 15m rows as iid.

## 10. Search surface and reporting

3 L × 3 q × 5 H = **45** primary cells. Secondary families: expansion probability and normalized range. Decile bins `[0,10), …, [90,100]` (last inclusive of 100) are diagnostics, not extra strategies. Optional Spearman across the ten bin summaries. Year blocks **2020–2024** reported separately. No Sharpe, PnL, or leverage.

Desired qualitative shape if the mechanism exists: stronger compression (q10) at least as strong as q20/q30; more than one lookback; adjacent horizons. One magic cell is fragile.

## 11. Development verdict (choose exactly one)

**H01_KILL** if true compression is broadly indistinguishable from matched random; permutation performs similarly; stronger compression is not stronger/non-worse; effects reverse across years; uplift is one parameter point or one year/month. Do not rescue with extra thresholds/features.

**H01_CANDIDATE_FOR_R3** requires all of: (1) true compression separates from matched-random for at least one lookback family; (2) permutation materially weakens/destroys it; (3) neighboring q show a plateau or sensible strength-response; (4) effect on at least two adjacent horizons; (5) positive in at least 4 of 5 yearly blocks for the proposed neighborhood; (6) no single month dominates the effect; (7) bootstrap interval compatible with a real positive effect; (8) primary RV supports the mechanism. Do not freeze one final candidate in this task.

**H01_INCONCLUSIVE** if suggestive but neither KILL nor candidate.

After the development run: **do not inspect 2025 or 2026**. If KILL or INCONCLUSIVE, stop. If CANDIDATE_FOR_R3, stop before R3 tuning/freeze.

## 12. Implementation notes

Tooling: `scripts/research/h01_compression_expansion.py` + `_lib.py`. Tests: `tests/research/test_h01_compression_expansion.py`. Not a universal backtester. Not V1/V2 detector reuse.
