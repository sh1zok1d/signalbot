# Weekday / weekend baseline calibration — product-evidence unit V2

**Status:** `DESIGN_NOTE_COMMITTED + PRE-OUTCOME AMENDMENT A1 (§9, wins where it differs) / OWNER GO 2026-10-05 / NO_PRODUCT_CHANGE`
**Date:** 2026-10-05
**Track:** `PRODUCT_EVIDENCE` only (`research/EVIDENCE_AND_CLAIMS_DECISION_V1.md`). No directional claim and no `STRUCTURE` or `EDGE` claim. A baseline is construction, not a claim; its user-visible effect is on L0 labels.
**Supersedes as the plan to run:** `WEEKDAY_WEEKEND_BASELINE_CALIBRATION_DESIGN_V1.md` revision 5, kept unchanged as history.
- **Kept from revision 5:** the candidate definitions C0 / C1 / C1-LONG, the clock-hour sampling unit, common support, the availability guardrail, nominal-rate targets and date-clustered errors.
- **Dropped:** Stage P as an 11-month confirmatory gate (2 250 weekend hours, 52-week cap) and "Stage H has no evidentiary weight". Under the new model, the 2020–2024 measurement is the product evidence, and the live tape is a monitor with a revert trigger (§7).

**Motivation:** R03-C1 (`research/EVIDENCE_FORMAT_SHADOW_REPORT_V1.md` §2). Weekend hours were about 0.4 SD calmer than the same weekday hour in 2020–2024, more each year. No R03 number is an input, offset or prior here.

## 1. Question (estimand)

> Are the references behind the bot's unusualness flags and labels equally calibrated on weekdays and weekends, and which pre-declared construction calibrates both best?

**Calibration** means that a fresh window's rank is uniform, so each cut fires at its nominal rate. This is a calibration question, not a question of whether weekends are calmer.

## 2. Surfaces measured (current `main`)

| Surface | Current construction (C0) | Nominal target per stratum |
|---|---|---|
| Gate flags (`beta/hour_gate.py`) | rank of the rolling 1h value against every present 5m bucket in `[t − 30d, t)`, **all hours and weekdays pooled** | range ≥ 0.95: 5 %; volume ≥ 0.95: 5 %; price ≥ 0.95 or ≤ 0.05: 10 % |
| Interpretation bands (`beta/interpretation.py`; «сжатие», up / down) | same ranks; up ≥ 0.80, down ≤ 0.20 | range ≤ 0.20 («сжатие» input): 20 %; price up: 20 %; price down: 20 % |
| 4h context ranks | same, 48-bucket windows | as above |
| Time-of-day presentation baseline (`BETA_HORIZON_TOD_V2`) | median over 30 prior days of the same UTC hour ±30 min, weekday types pooled | current value above the baseline median: 50 % |

## 3. Candidates (fixed now; no other variant)

| Id | Reference for a window starting on day type T | Note |
|---|---|---|
| **C0** | current (above) | baseline |
| **C1** | C0 restricted to buckets whose window start falls on a UTC date of type T; usable only with ≥ 8 same-type dates | revision 5's minimal split. Weekends have only 9–10 dates in 30 days, so the reference is noisy by construction |
| **C2** | the most recent 30 same-type UTC dates (about 42 days back for weekdays, about 105 for weekends) | the longer weekend-only window (revision 5's C1-LONG) |
| **C3** | C0's reference unchanged; a weekend window's range, volume and \|move\| are divided by a point-in-time weekend factor before ranking. Per metric, the factor is the median over the trailing 52 complete weeks before `t` of (weekend value / same-hour weekday value); it needs ≥ 26 weekends of history | the long-history adjustment: one number per metric, updated weekly, never using data at or after `t` |

**TOD presentation baseline.** C1 and C2 restrict the per-day medians to same-type days. C3 multiplies the pooled median by the factor on weekends.

**Simplicity order** for ties: C0, then C3, then C1, then C2. C3 counts as simpler than C1 because it keeps one reference and adds a single factor per metric.

**Not tested here.** A volatility-conditioned reference: R03-C1's nuisance retention of 0.26 says it might absorb much of the gap. It would be a separate unit if this one is inconclusive.

## 4. Method (chosen before outcomes)

- **Data:** `CORE_BTC_BINANCE_V0` BTCUSDT perpetual 1m → 5m, through the pinned, SHA-verified loaders.
  - Window 2020-01-01 .. 2024-12-31 (restored by amendment A1, §9.1); each candidate's structural warm-up is counted, not chosen.
  - Single venue, so the label is `PROXY_SINGLE_VENUE`. Consensus = Binance and venue agreement is not evaluated; OI and taker bands are not measured.
- **Unit:** one observation per UTC clock hour (revision 5 §3.1): the rolling-1h window `[H−1:00, H:00)`, typed by its start date. 4h windows are sampled every 4h (00, 04, … UTC).
- **Common support:** hours usable under all four candidates.
  - Each candidate's own availability is reported.
  - **Guardrail:** availability ≥ C0's availability − 5 pp per stratum.
- **Estimates per candidate, stratum (WEEKDAY / WEEKEND / ALL) and metric:**
  - exceedance rate and gap to nominal, with a UTC-date-clustered SE (`G/(G−1)` correction; revision 5 §7 formulas) and the ISO-week SE beside it, using the larger;
  - the same by year;
  - **label flip rate** against C0: the share of hours whose flag, band or above-TOD-median status changes.
- **Ranks:** the production percentile core and `rolling_window_values`, imported read-only; no beta code changes.
- **Primary metric:** `P_S` = the largest |gap| over {WEEKDAY, WEEKEND} × {range flag, volume flag, price flag, range ≤ 0.20 band, price up band, price down band, TOD above-median}.

## 5. What would change our mind (decision rule, fixed now)

1. **Eligible** = passes every guardrail:
   - availability (§4);
   - no stratum and metric under-flags by more than 2 pp below nominal at the 5 % / 10 % cuts, or by more than 4 pp at the 20 % / 50 % bands;
   - weekday |gap| no worse than C0's + 0.5 pp;
   - in no year worse than C0 on `P_S` by more than 1 pp.
2. **Proposal:** the eligible candidate with the smallest `P_S`. If a simpler candidate is within 0.5 pp of it, the simpler one is proposed.
3. **If C0 is proposed**, or no candidate improves `P_S` by at least 1 pp: `NO_CHANGE`. The weekend gap stays documented.
4. **Otherwise** `PROPOSE_<Cx>`: a product change proposal (new context version label, config digest, deploy note). This unit makes no change.
5. **`INCONCLUSIVE`** if the data cannot be loaded completely or common support is below 90 % of evaluation hours in a stratum.

**Planning information:** about 10 000 weekend and about 25 000 weekday hours in 2021–2024. At a 5 % cut with a day-cluster design effect of 2.5, the weekend SE is about 0.34 pp: ample for 1–2 pp decisions.

## 6. Search exposure and limits

- **Exposure:**
  - 4 candidates × 7 metrics × 2 strata, with years reported, not selected on;
  - the surface 2020–2024 is **exposed** (R03 published weekend range differences on it);
  - single venue;
  - 2025 / 2026 is not used, although product use of that surface was opened by `PRODUCT_DECISION_V2` §4 (an owner may add it later as a labelled secondary slice).
- **Recorded before outcomes:** this note is committed before any rate is computed. Any added candidate or metric is a new unit.
- **Time-box:** 2 working days. If the CORE loaders or data are not available where it runs, it stops with that blocker.

## 7. Live check (prospective, after any proposal)

- **Weekly report from the beta tape (V2 rows since 2026-10-01):** C0 vs the proposed candidate on the same metrics, with the production 3-venue consensus. It is reported only, never used to select.
- **Revert trigger:** after ≥ 12 weekends (about 576 weekend hours; SE about 1.4 pp at a 5 % cut), the weekend gap of the deployed candidate is worse than C0's by more than 2 pp on any gate flag. A revert is proposed then.
- **Journal:** the weekly report reuses the claim journal (`BETA_CLAIM_JOURNAL_DESIGN_V1.md`) once it exists. Until then it is a read-only CLI report.

## 8. Implementation (when the owner says go)

- **Code:** `scripts/product/weekday_weekend_baseline_v2/`, offline. It imports `beta.context` / percentile core read-only and writes `docs/WEEKDAY_WEEKEND_BASELINE_UNIT_V2_RESULT.{md,json}`, with the full per-date sufficient statistics.
- **Synthetic tests:**
  - point-in-time: a shock after `t` changes nothing at `t`; the C3 factor never sees `t` or later;
  - weekday typing across DST and the year boundary;
  - one observation per clock hour;
  - a known-rate synthetic series is recovered at its nominal rate.
- **Not built:** no change to `beta/`, config, schema or deploy.

## 9. Amendment A1 — pre-outcome repair (owner go, 2026-10-05)

Written and committed **before any rate, rank or flag is computed**. Where it differs from §1–§8, it wins.

### 9.1 Data window: 2020–2024 restored

- **Window.** The owner decision named 2020–2024. Every UTC clock hour whose window starts in `[2020-01-01, 2025-01-01)` is in the window.
- **Data.** `CORE_BTC_BINANCE_V0` BTCUSDT perpetual 1m through `scripts/research/owner_cards_r03/data.py::load_btc_1m`: 60 pinned monthly objects 2020-01..2024-12, SHA-verified, with the loader's own gapless and bounds assertions. Protected 2025/2026 URLs are refused by that loader.
- **2020 is not technically unusable.** The only constraint is objective point-in-time. The pinned dataset starts 2020-01-01, and no earlier data is admitted (CORE contract start), so a reference needs history before `t`. A candidate's ranks are therefore unusable until its own reference matures.
- **Warm-up hours are counted, not removed by choice.** They are reported as `REFERENCE_IMMATURE`.
- **Calendar maturity** (arithmetic only, no data read):

| Candidate | First usable reference |
|---|---|
| C0 / C1 | 2020-01-31 |
| C2 | weekdays ≈ 2020-02-11; weekends ≈ 2020-04-25 (30 weekend dates) |
| C3 | ≈ 2020-07-06 (26 complete ISO weeks) |

- **Comparisons:**
  - The primary comparison is on **common support** (hours usable under all four candidates), so about H2 2020 enters it.
  - Each candidate is also reported against C0 on their **pairwise** support (C1 from February 2020).
  - The availability and common-support guardrails are computed **after the last calendar maturity date** (2020-07-06), so the structural warm-up does not fail them mechanically.

### 9.2 Values and ranks (single-venue proxy, production definitions)

- **5m bucket from 1m:** first open, max high, min low, last close, quote-volume sum. A bucket is present only if all 5 minutes are present.
- **Rolling window of `n` buckets ending at bucket `b`** (`rolling_window_values`, one venue):
  - range % = (max high − min low) / first open · 100;
  - move % = (last close − first open) / first open · 100;
  - volume = quote-volume sum.

  `n = 12` (1h) or `48` (4h).
- **Rank:** mid-rank `(#less + 0.5·#equal) / N` over the reference samples, as in `analytics/percentile_engine/compute.py::compute_percentile_snapshot`. It is implemented in numpy, and a parity test checks it against that function and `rolling_window_values` on a synthetic tape.
- **Day type:** WEEKEND = the UTC date of a window's **start** is Saturday or Sunday; this holds for evaluated windows and reference samples alike.
- **Evaluated windows:**
  - 1h: one per UTC clock hour, the window `[H−1:00, H:00)`, so the end bucket is `H:00 − 5m`;
  - 4h: one per 4h boundary (`00, 04, … UTC`), the window `[H−4:00, H:00)`.

### 9.3 Candidates (exact; frozen now)

For an evaluated window with end bucket `t`, start date `s` and type `T`, the reference samples are the rolling values at present buckets `b < t`, as in production.

| Id | Name | Reference | Usable when |
|---|---|---|---|
| **C0** | current, pooled 30 calendar days | every `b ∈ [t − 30d, t)`, all types | the production tier is mature (the sample at `t − 30d` exists) |
| **C1** | **same type inside the short calendar window** | `b ∈ [t − 30d, t)` whose start-date type = `T` | C0 usable **and** ≥ 8 distinct same-type start dates (about 8–10 weekend dates, about 2 300–2 900 samples) |
| **C2** | **last N = 30 same-type dates (longer window)** | `b < t` whose start date is among the 30 most recent same-type dates ≤ `s` (today's earlier samples included) | 30 such dates exist (weekend lookback ≈ 105 days, weekday ≈ 42 days; about 8 600 samples) |
| **C3** | pooled 30 days + long-history weekend factor | C0's samples, with every weekend-typed value (sample or evaluated) divided by `f_m(t)` | C0 usable **and** `f_m(t)` defined |

**The C3 factor `f_m(t)`**, per metric `m` ∈ {range, volume, move} and per horizon on its own grid (1h: hours 0–23; 4h: hours 0, 4, … 20):
- for each complete ISO week strictly before the ISO week of `s`, and each grid hour `k`, the weekday reference is the median of Mon–Fri values at `k` (≥ 3 present);
- `r` = Sat or Sun value at `k` / that reference (move uses |values|; a zero reference is skipped);
- `f_m(t) = exp(median(log r))` over the 52 most recent such weeks;
- it is defined when ≥ 26 weeks contribute;
- the signed move is divided by `f_move`.

**TOD presentation baseline** (1h windows; range and volume; production `_baseline_tod`: the window end `W = H:00`, ±30 min at 5-minute steps, the median per day, then the median of the daily medians). The day type of prior day `d` is the type of the date of `W − d days − 1h`.

| Candidate | Days used | Usable when |
|---|---|---|
| C0 | `d = 1..30` | ≥ 20 days (production) |
| C1 | `d = 1..30` with type `T` | ≥ 8 days |
| C2 | the 30 most recent prior days of type `T` | ≥ 20 days |
| C3 | C0's days; weekend daily medians and the evaluated weekend value divided by `f_m(t)` | as C0 and `f_m(t)` defined |

### 9.4 What is reported per candidate (owner list)

| Owner item | Metric |
|---|---|
| Calibration error | rate − nominal, by stratum (WEEKDAY / WEEKEND / ALL), with a date-clustered SE (`G/(G−1)`) and the ISO-week SE beside it, using the larger. Metrics: 1h gate flags (range ≥ 0.95 → 5 %, volume ≥ 0.95 → 5 %, price ≥ 0.95 or ≤ 0.05 → 10 %); 1h and 4h bands (range ≤ 0.20, price ≥ 0.80, price ≤ 0.20 → 20 % each); 4h flags as 1h; TOD above-median for range and volume → 50 % |
| Flag-rate imbalance | gate qualification rate `U` (≥ 2 of 3 flags; venue agreement not evaluable): `U_WEEKEND − U_WEEKDAY`; no nominal claimed |
| Label-switch rate | share of common-support hours where any 1h label (3 flags, qualification, 3 bands) differs from C0; separately 4h bands and TOD status |
| Rank change | mean \|rank_Cx − rank_C0\| per metric and stratum |
| Amount of information | median reference size and distinct reference dates, common-support hours and date clusters per stratum |
| Stability by year | every gap by the year of the window start |
| Small-sample failure mode | weekend overdispersion index: the SD of ISO-week flag rates divided by its binomial expectation, for the 1h gate flags, beside C0's |
| Operational cost | lookback days needed and the history the live tape would need (stated, not measured) |

`P_S` = the largest |gap| over {WEEKDAY, WEEKEND} × {1h flags ×3, 1h bands ×3, 4h bands ×3, TOD ×2}.

### 9.5 Decision rule (replaces §5; same logic, owner labels)

1. **Eligible** = all of the following, on common support after 2020-07-06 for availability:
   - availability ≥ C0's − 5 pp per stratum;
   - no under-flagging beyond −2 pp at the 5 % / 10 % cuts or beyond −4 pp at the 20 % / 50 % bands, in either stratum;
   - every weekday |gap| ≤ C0's + 0.5 pp;
   - `P_S` in each year ≤ C0's + 1 pp;
   - weekend overdispersion index ≤ 1.25 × C0's on every 1h gate flag;
   - |`U_WEEKEND − U_WEEKDAY`| ≤ C0's.
2. **Proposal:** the smallest `P_S` among eligible candidates, with the simpler candidate kept within 0.5 pp (order C0, C3, C1, C2).
3. **Recommendation:**
   - **`CHANGE_BASELINE (Cx)`** if the proposal is not C0 and improves `P_S` by ≥ 1 pp;
   - **`INSUFFICIENT_TO_CHANGE`** if some candidate improves `P_S` by ≥ 1 pp but is ineligible only through the year-stability or overdispersion guardrails, or if data or common support fail (common support < 90 % of hours after 2020-07-06 in a stratum);
   - **`KEEP_CURRENT`** otherwise.

   Each candidate gets its own line: eligibility with reasons, plus its metrics.
4. **No claim** about direction, edge or market behaviour. A recommendation is a product baseline proposal; this unit makes no change.

### 9.6 Implementation for this run

- **Code:** `scripts/product/weekday_weekend_baseline_v2/evaluate.py` (offline; reads the pinned loader only; imports nothing that writes).
- **Tests:** `tests/product/test_weekday_weekend_baseline_v2.py`:
  - parity of rank, rolling values and TOD against the production functions on a synthetic tape;
  - point-in-time (a shock after `t` changes nothing at `t`; the C3 factor never sees the ISO week of `s` or later);
  - day typing across DST and the year boundary;
  - one observation per clock hour;
  - a stationary synthetic series flags at its nominal rate under C0.
- **Run:** once, after the tests pass. Output: `docs/WEEKDAY_WEEKEND_BASELINE_UNIT_V2_RESULT.{md,json}`.
- **Live beta tape:** not read here (§7 monitoring only, after a decision).
