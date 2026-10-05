# Weekday / weekend baseline calibration — product-evidence unit V2

**Status:** `DESIGN_NOTE_COMMITTED / NOT_EXECUTED / NO_PRODUCT_CHANGE`
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
  - Warm-up 2020; evaluation 2021-01-01 .. 2024-12-31, identical for all candidates. C3 needs 26 weekends of history, and C2 for weekends about 105 days.
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
