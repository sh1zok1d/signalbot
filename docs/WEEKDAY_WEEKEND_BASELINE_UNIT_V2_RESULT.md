# Weekday / weekend baseline calibration — unit V2 result

**Status:** `EXECUTED_ONCE (2026-10-05) / PRODUCT_EVIDENCE / RECOMMENDATION = CHANGE_BASELINE (C1) / NO_PRODUCT_CHANGE_MADE`

**Records:**
- design `WEEKDAY_WEEKEND_BASELINE_UNIT_V2.md` with pre-outcome amendment A1 (`2c1aed2`);
- evaluator `scripts/product/weekday_weekend_baseline_v2/evaluate.py` (`86b2c09`, sha256 `5bda5d60e9b55812…`, committed before the run);
- machine record `WEEKDAY_WEEKEND_BASELINE_UNIT_V2_RESULT.json`.

**Data:**
- `CORE_BTC_BINANCE_V0` BTCUSDT perpetual 1m, 2020-01-01 .. 2024-12-31, from the pinned R03 loader (dataset digest `93659495…`, 2 630 880 rows, gapless);
- single-venue proxy (Binance): venue agreement, OI and taker ranks are not evaluated;
- the live beta tape was not read; 2025/2026 not used.

**What this is not:** no claim about direction, edge or market behaviour. It measures whether the bot's own reference distributions fire at their nominal rates on weekdays and on weekends.

## 1. Answer

**No.** The current pooled 30-day reference (C0) is not equally calibrated:
- **Weekends under-fire, weekdays over-fire.** The gate (≥ 2 of 3 flags) qualifies **2.4 %** of weekend hours against **7.1 %** of weekday hours. The weekend range, volume and price flags fire at about half their nominal rates.
- **«Обычно» misleads on weekends.** Only **32 % / 29 %** of weekend hours are "above usual" on the time-of-day baseline for range / volume, where 50 % is the target. Weekend hours land in the «сжатие» range band (range rank ≤ 0.20) 37 % of the time, against 20 % nominal.
- **The gap has grown every year:** C0's worst gap was 11 pp in 2020–2021 and 24–28 pp in 2022–2024.

A same-type reference inside the current 30-day window (**C1**) removes the imbalance: every gap is within ±2 pp, and gate qualification is 5.9 % on both day types. By the frozen rule (§9.5): **`CHANGE_BASELINE (C1)`**.

## 2. Per candidate (common support: 39 528 hours, 2020-06-29 .. 2024-12-31; 11 280 weekend hours on 470 dates; 236 ISO weeks)

Gaps are the rate minus nominal, in pp, with the larger of the date-clustered and ISO-week SE in brackets.

| | **C0** current pooled 30d | **C1** same type, 30-day window | **C2** last 30 same-type dates | **C3** pooled + weekend factor |
|---|---|---|---|---|
| Weekend 1h flags: range / volume / price | −2.5 / −3.0 / −4.3 (0.3–0.4) | +0.6 / +0.6 / +0.7 (0.4–0.6) | +0.5 / +0.9 / +0.1 (0.5–0.7) | +0.4 / −0.3 / +0.3 (0.4–0.6) |
| Weekday 1h flags | +1.8 / +1.8 / +2.7 | +0.7 / +0.5 / +0.8 | +0.6 / +0.5 / +0.9 | +0.7 / +0.7 / +0.8 |
| Gate qualification: weekend / weekday (imbalance) | 2.4 % / 7.1 % (−4.7 pp) | 5.85 % / 5.91 % (−0.06) | 5.84 % / 5.92 % (−0.07) | 5.39 % / 6.04 % (−0.65) |
| Range ≤ 0.20 band, 1h: weekend / weekday | +16.6 / −5.8 | +1.4 / +0.6 | +1.9 / +0.3 | +2.9 / +0.1 |
| TOD "above usual", range / volume: weekend | −18.2 / −20.9 | −2.0 / −0.2 | −1.1 / +2.5 | −2.4 / −1.8 |
| `P_S` (worst \|gap\|) | **20.9** | **2.0** | **2.5** | **2.9** |
| `P_S` by year 2020…2024 | 11.1 / 11.1 / 26.3 / 24.1 / 28.0 | 7.1 / 2.6 / 6.1 / 2.6 / 2.0 | 12.1 / 7.2 / 10.5 / 2.7 / 5.0 | 7.1 / 3.5 / 11.6 / 2.9 / 2.3 |
| Label-switch vs C0: 1h / 4h bands / TOD, weekend | — | 34 % / 26 % / 29 % | 36 % / 27 % / 33 % | 31 % / 25 % / 27 % |
| Label-switch, weekday | — | 15 % / 11 % / 14 % | 17 % / 12 % / 17 % | 14 % / 10 % / 12 % |
| Mean \|Δ rank\| weekend, range / volume / move | — | 0.12 / 0.15 / 0.04 | 0.14 / 0.16 / 0.04 | 0.11 / 0.13 / 0.04 |
| Reference: samples / dates / lookback, weekend | 8 640 / 31 / 30 d | **2 544 / 9 / 28 d** | 8 472 / 30 / 104 d | 8 640 / 31 / 30 d, + 26–52 weeks for the factor |
| Weekend overdispersion, range / volume / price flag (× binomial) | 2.04 / 1.95 / 2.02 | 2.25 / 1.93 / 2.11 | **2.64** / 2.42 / 2.36 | 2.23 / 2.07 / 2.12 |
| Own support from | 2020-01-31 | 2020-01-31 | 2020-02-11 | 2020-06-29 |
| Eligible (§9.5) | no: under-fires on weekends and in the weekday range band | **yes** | no: overdispersion 2.64 > 1.25 × 2.04 | yes |
| Operational cost | none | **none extra: the same 30-day window, a filter by day type; the live tape matures like C0** | about 105 days of weekend history: longer than the live tape has, or a backfill | a 26–52-week weekend factor: needs Binance history beyond the live tape (it exists in `beta_hist_bars_5m`); one more versioned input |

**Pairwise check vs C0 from 2020-01-31 (secondary).** C1's weekend gate-flag gaps are +0.6 / +0.7 / +0.7 pp, against C0's −2.4 / −2.9 / −4.1.

## 3. Decision by the frozen rule

- **Eligible candidates:**
  - C1, `P_S` 2.0 pp;
  - C3, 2.9 pp. C3 is simpler but is not within 0.5 pp of C1.
- **Proposal: C1**, improving `P_S` by 18.9 pp.
- **C2 improves too, but is not robust.** It fails only the small-sample / staleness guardrail. A 105-day weekend reference makes the week-to-week weekend flag rate 29 % noisier than C0's, because a stale reference crosses volatility regimes.
- **Recommendation: `CHANGE_BASELINE (C1)`.**

**Failure modes, as measured:**
- **C1's small weekend reference (about 9 dates) did not create the opposite problem on average.** Weekend gaps are +0.2..+1.4 pp, and its overdispersion is 1.10 × C0's, inside the 1.25 guardrail.
- **2020 is C1's weak year.** Its weekend flags were +2–3.5 pp, its year `P_S` 7.1 pp: COVID-crash weekends with a 9-date reference.
- **C3 trails on the «сжатие» band.** One multiplicative factor does not fix the range band on weekends (+2.9 pp), and its factor drifted from 0.80 (2020) to 0.58 (2024) for range. That drift is the same weekend narrowing R03-C1 recorded, growing each year.
- **All candidates are overdispersed (about 2×).** Flags cluster in volatility regimes whatever the reference.

## 4. Product consequences of C1 (for the owner; nothing is changed by this unit)

- **Weekend gate qualification rises about 2.4×** (2.4 % → 5.9 % of hours), and weekday qualification falls (7.1 % → 5.9 %). Weekend unusual-hour labels and pushes become as frequent as weekday ones, within the existing caps.
- **Labels change on about a third of weekend hours and about one in seven weekday hours** («сжатие» less often on weekends; «обычно» lines balanced). 4h bands and the TOD «обычно» follow the same split.
- **Implementation would be a new context version** (e.g. `BETA_CONTEXT_1H_V3`) with the day-type filter in the reference, the same filter in `BETA_HORIZON_TOD` (≥ 8 same-type days), and a carry-over of episode state as in V1→V2. That is a separate product change, needing its own go.
- **Live check after any deploy:** design §7. The weekly beta-tape report gives C0 vs C1 on the same metrics with the 3-venue consensus. A revert is proposed if, after ≥ 12 weekends, C1's weekend gap on a gate flag is worse than C0's by > 2 pp.

## 5. Limits

- **Single-venue proxy:** the production median of three venues and venue agreement were not reproduced. OI and taker ranks were not evaluated.
- **Exposed surface:** 2020–2024 was already exposed by R03. This unit uses it as product evidence, not as a confirmation.
- **Warm-up:**
  - common support starts 2020-06-29 (C3's factor);
  - C1 was also checked pairwise from 2020-01-31;
  - three `|move|` ratios of zero were skipped in the 1h factor (implementation interpretation: the log of 0 is undefined).
- **Search exposure:** 4 candidates × 11 metric families × 2 strata, frozen before outcomes. Years are reported, not selected on. No variant was added after the run.
