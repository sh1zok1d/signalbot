# H02 Failed Breakout → Mean Reversion — Preregistration

**Status:** PREREGISTERED / EXPLORATORY
**Hypothesis ID:** `H02_FAILED_BREAKOUT_MEAN_REVERSION`
**Machine-readable freeze:** `docs/research/H02_FAILED_BREAKOUT_MEAN_REVERSION_PREREG.json`
**Dataset:** `CORE_BTC_BINANCE_V0` snapshot `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`

This document is frozen **before** any H02 development forward outcomes are computed. A clean null is a successful research result. This is not a trading strategy, product detector, liquidity-sweep claim, or confirmatory result.

Use the neutral term **failed breakout**. Do not claim that every event is a liquidity sweep.

## 1. Research question

When BTC briefly breaches a locally established price range but closes back inside that range, does subsequent price movement tend to continue back toward the range rather than behave like an ordinary/random boundary event?

Directional mean-reversion mechanism only. Not entries/exits, stop-hunting, market-maker intent, or product logic.

## 2. Dataset and information at T

Use accepted CORE_BTC_BINANCE_V0 only. Canonical 5m bars are derived from accepted 1m history. The development runner loads 2020–2024 1m monthly parquet only and must not open 2025/2026 partitions.

At decision time T use only bars with `available_at <= T`. No close_time shortcut. No volume, taker, trend, RSI, MACD, ATR, funding, OI, liquidations, higher-timeframe trend, session, or range-age gates.

Price columns are decimal strings. Parse with `float(Decimal(...))` before arithmetic. Never compare them lexicographically.

Fail closed if the repository manifest snapshot_id differs from the freeze above.

## 3. Chronological windows (UTC)

| Window | Start inclusive | End exclusive | Outcome inspection |
|---|---|---|---|
| Warmup | 2020-01-01T00:00:00Z | 2020-02-01T00:00:00Z | features only |
| Development / discovery | 2020-02-01T00:00:00Z | 2025-01-01T00:00:00Z | allowed |
| Reserved validation | 2025-01-01T00:00:00Z | 2026-01-01T00:00:00Z | **forbidden** |
| Untouched OOS | 2026-01-01T00:00:00Z | 2026-08-26T00:00:00Z | **forbidden** |

Every development event must satisfy `T + 240m < 2025-01-01T00:00:00Z`. Last legal 5m decision is `2024-12-31T19:55:00Z`.

## 4. Canonical timeframe and decision grid

Evaluate every UTC-epoch-aligned 5-minute boundary. Event bar `B = [T-5m, T)` is the last fully known 5m bar at T (`available_at(B) = T`). Do not use a still-forming bar.

## 5. Prior range

Lookbacks frozen: **L ∈ {60, 120, 240} minutes**.

Reference interval of complete 5m bars strictly before the event bar: `[T-5m-L, T-5m)`.

`R_high = max(high)`, `R_low = min(low)`, `prior_log_range = ln(R_high / R_low)`. Require `prior_log_range > 0`. The event bar is not part of the prior range.

## 6. Failed-breakout event

Event bar opens and closes inside the prior range.

UPPER: `high_B > R_high` and `low_B >= R_low`. Reversion direction SHORT = −1.

LOWER: `low_B < R_low` and `high_B <= R_high`. Reversion direction LONG = +1.

If both boundaries are breached in the same event bar: exclude as `AMBIGUOUS_DOUBLE_BREAK`. No post-hoc handling.

Open outside the prior range: excluded.

## 7. Overshoot strength

UPPER: `ln(high_B / R_high) / prior_log_range`

LOWER: `ln(R_low / low_B) / prior_log_range`

Thresholds frozen: **s ∈ {0.00, 0.05, 0.10}**. Candidate: `overshoot >= s`. No extra thresholds after outcomes. 3 L × 3 s = 9 structural configurations.

## 8. Refractory clustering

Primary population: after accepting an event at T, ignore further qualifying events of **either side** during `(T, T+30m)`. Keep the earliest. Report raw pre-dedup count diagnostically. Do not retune the 30m window after outcomes.

## 9. Horizons and primary outcome

Horizons frozen: **H ∈ {15, 30, 60, 120, 240} minutes**.

`RET_H(T) = ln(close(T+H) / close(T))` with `close(T)` the last fully known 5m close at T.

`REV_RET_H = reversion_direction * RET_H`

`PAST_MEDIAN_ABS_RET_H(T)` = median absolute H-horizon close return on UTC 5m boundaries in the preceding 30 calendar days with outcome known by T (`t + H <= T`). Current/future excluded.

`NORM_REV_RET_H = REV_RET_H / PAST_MEDIAN_ABS_RET_H(T)`

If the scale is zero/unavailable the event is ineligible for that outcome.

Primary metrics per L × s × H: N, mean/median NORM_REV_RET, mean raw REV_RET in bps, P(REV_RET > 0), 25/75 and 5/95 percentiles. No Sharpe/PnL.

## 10. Secondary path metrics

On the future H path of 5m bars with `available_at` in `(T, T+H]`:

MFE in the reversion direction and MAE against it, both divided by `PAST_MEDIAN_ABS_RET_H(T)`.

Also `P(reversion-direction MFE > adverse-direction MAE)`.

Secondary only. MFE cannot promote H02.

## 11. Controls

- **Baseline A — matched random times:** same month counts and UPPER/LOWER direction counts; sample eligible UTC 5m boundaries; seed **20260829**; **100** replicates. Report candidate minus matched-random mean NORM_REV_RET and positive-share.
- **Baseline B — successful breakout:** same L, range, s. Open inside range. UPPER success: high > R_high, close > R_high, low not breached. LOWER success: low < R_low, close < R_low, high not breached. Same hypothetical reversion sign. Independent 30m refractory. Do not force equal N. Report month/side composition.
- **Negative control — +6h same-UTC-day circular time shift** of true event timestamps. Do not re-detect. Preserve side and direction. Drop shifted T if past/future/scale invalid.

## 12. Dependence, uncertainty, stability

Report raw N, post-refractory N, unique UTC days/weeks/months, by month/year, max month share, top-5 month share, UPPER/LOWER share, median spacing.

UTC-week block bootstrap, seed **20260830**, **2000** replicates, 95% interval for candidate-minus-matched-random mean NORM_REV_RET and positive-share difference.

Year blocks **2020–2024** separately. Side breakdown UPPER vs LOWER. Do not silently redefine H02 as one-sided.

## 13. Search surface

3 L × 3 s × 5 H = **45** primary cells. Secondary: MFE/MAE, matched random, successful breakout, time shift, side, year.

Desired qualitative shape: for at least one lookback family, s=0.00/0.05/0.10 form a plateau or plausible strength-response; stronger overshoot non-worse; more than one lookback. One magic cell is fragile.

## 14. Development verdict (choose exactly one)

**H02_CANDIDATE_FOR_R3** requires all of: (1) true timing beats matched random in a broad neighborhood; (2) separates from successful-breakout control; (3) +6h weakens the effect; (4) neighboring s plateau/strength-response; (5) at least two adjacent horizons; (6) candidate-minus-matched positive in at least 4 of 5 years; (7) UPPER and LOWER both have the expected sign overall; (8) no single month dominates; (9) week-block bootstrap compatible with a real positive candidate-minus-matched effect; (10) primary close-return supports the mechanism.

**H02_KILL** if no credible failed-breakout mean reversion (matched-random/success/shift similar; year sign flips; one isolated cell; one side only; primary close-return null/adverse). Do not rescue with extra features.

**H02_INCONCLUSIVE** if suggestive but neither candidate nor kill.

After the development run: **do not inspect 2025 or 2026**. Stop before R3 regardless of verdict.

## 15. Implementation notes

Tooling: `scripts/research/h02_failed_breakout_mean_reversion.py` + `_lib.py`. Tests: `tests/research/test_h02_failed_breakout_mean_reversion.py`. Not a universal backtester. Not V1/V2 detector reuse. H01 remains `H01_KILL` and is not reinterpreted here.
