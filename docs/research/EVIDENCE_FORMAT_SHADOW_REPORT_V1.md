# Evidence format shadow report V1 — three closed units in the new record

**Status:** `SHADOW_FORMATTING_EXERCISE / NO_STATISTICAL_TEST / NO_PROMOTION / NO_STATUS_CHANGED`
**Date:** 2026-10-05
**Expectations, committed first:** `EVIDENCE_FORMAT_SHADOW_EXPECTATIONS_V1.md` (commit `6b0b542`). Its pointer "§6 (the reporting record)" refers to what became §3 of `EVIDENCE_AND_CLAIMS_DECISION_V1.md`.

Every number below is copied from the unit's own record. Nothing was recomputed on market data. The one piece of arithmetic is R03-C1's interval, ±1.96 × the recorded SE, and it is marked as such. Official classes, the ledger, the atlas and `config/beta_research_findings.yaml` are unchanged.

## 1. DH1-L2 — zone vs lone level, 4h hold after the first touch (obvious null)

Record: `DH1_RESULT.md`, prereg `DH1_PREREG.json` (`3e584f3`). Official: `INCONCLUSIVE` (frozen class), findings `NOT_CONFIRMED`.

| Field | Value |
|---|---|
| estimate | +0.05 pp, nuisance-adjusted (raw 46.5 % vs 46.3 %) |
| uncertainty | 95 % CI −3.03..+3.06 pp |
| information | N = 4 622 first touches, 261 week clusters; planning MDE 5.8 pp |
| stability | by year −6.9, +5.3, −0.3, −4.2, +1.2 pp; heterogeneity p 0.13 at low power |
| falsification | Brier skill of adding the state −0.0008; a placebo is `NOT_IN_RECORD` |
| limitations | one venue, BTC, 4h hold only |
| search exposure | DH1: 15 candidates → 5 at feasibility → 1 executed (`TF-DH1-L-LEVEL-HOLD`) |
| method before outcome | `DH1_PREREG.json`, `3e584f3` |
| evidence summary | Zone levels held as often as lone levels; a difference beyond about ±3 pp is practically excluded. |
| interpretation | A popular trader belief that did not hold on Binance 2020–2024. |
| claim decision | **No live line.** At most a `/research` L2 statement of no difference: «уровень в зоне держался 4ч в 46,5 % против 46,3 % у одиночного (N = 4 622; разница −3..+3 п.п.)». Product use: none. |

**Against the expectation:**
- The record ends as "nothing useful to show as a tendency".
- The tight interval keeps it from collapsing into "unknown". The old class `INCONCLUSIVE` did exactly that, missing by 0.03 pp.

## 2. R03-C1 — weekend hour vs the same hour on Tue–Thu (strong but small)

Record: `OWNER_CARDS_R03_RESULT.md`, prereg `OWNER_CARDS_R03_PREREG.md`. Official: `NO_INCREMENTAL_STRUCTURE`, findings `WEAK`.

| Field | Value |
|---|---|
| estimate | −0.396 comparator-SD (standardized log range) |
| uncertainty | SE 0.036 sign-flip / 0.033 moving-block; ≈ −0.47..−0.33 (±1.96·SE, arithmetic on the recorded SE); Holm p 0.0001 |
| information | 260 weekly units; 0 of 37 326 windows missing |
| stability | 2020 −0.19, 2021 −0.21, 2022 −0.43, 2023 −0.49, 2024 −0.65: same sign every year, growing (Q p 0.0005) |
| falsification | Sibling cells A1, A4, B2, C2 and C4 on the same estimator sit near zero. Nuisance-adjusted (prior 24h RV, lagged target): −0.104, retention 0.26, with the record's caveat that a Sunday's lagged target is the Saturday hour. |
| limitations | Binance only; the comparator is Tue–Thu, not all weekdays; a large share co-moves with the volatility level; 2025+ not examined |
| search exposure | R03: 12 ids, 6 executed; Holm within card C (m = 3); the bar was 0.5 SD |
| method before outcome | R03 twin prereg (`OWNER_CARDS_R03_PREREG.{md,json}`) |
| evidence summary | Weekend hours were narrower than the same weekday hour by about 0.4 SD (SE 0.036), in every year and more each year; much of the gap moves with the general volatility level. |
| interpretation | A real calendar structure in activity, not in direction. Below the 0.5 SD bar that a stronger claim would have needed. It matters to any baseline that pools weekdays with weekends. |
| claim decision | **L1 allowed:** «В 2020–2024 выходные часы на Binance были спокойнее того же часа во вт–чт — примерно на 0,4 SD; разрыв был каждый год и рос (с 0,2 до 0,65 SD).» **Not L2** (no future outcome). **Not EDGE.** `PRODUCT_EVIDENCE`: a baseline calibration question, handed to `docs/WEEKDAY_WEEKEND_BASELINE_UNIT_V2.md`. |

**Against the expectation:** it reads as "real structure / magnitude below the stronger claim's bar / potentially useful for the product baseline", with no contradiction between the fields.

**Wording defect surfaced.** The live findings text says «ниже порога значимости проверки». The record says the opposite: statistically significant, below the **materiality** bar. Proposed copy: «…но остался ниже порога практической величины проверки (0,5 SD)». This is a product follow-up and is not changed here.

## 3. D12 — US clock change and BTC's intraday volume profile (rare event, N = 10)

Record: `discovery_results/D12_DISCOVERY_RESULT.md`, card `DISCOVERY_SPRINT_04.md` (D12), with the pre-outcome window amendment F1. Official: `PROMISING_PROTOTYPE`, findings `DISCOVERY`.

| Field | Value |
|---|---|
| estimate | mean A = 0.134 over 10 US transitions. A is the share of the before/after profile distance removed by the clock-predicted one-hour shift, so a positive A means the profile moved with the US clock. |
| uncertainty | an interval is `NOT_IN_RECORD`; one-sided Monte Carlo p ≈ 0.0001 against 239 pseudo-transition Sundays (δ-matched) |
| information | **10 events** (two a year), 239 placebo Sundays; effective N = 10 |
| stability | by year 0.065, 0.015, −0.069, 0.256, 0.401: 4 of 5 positive, one negative, two near zero; the size sits in 2023–2024 |
| falsification | placebo Sundays (above); EU-transition diagnostic −0.17, so the profile did not follow the EU clock |
| limitations | N = 10; concentrated in two recent years; Binance BTC volume timing only; no price, volatility or direction content |
| search exposure | one observable, one window, one index (card); Sprint 04 ran 2 cards; 10 internal discovery cards were executed, 4 of them promising |
| method before outcome | `DISCOVERY_SPRINT_04.md` and its implementation freeze (F1 amended before outcomes) |
| evidence summary | Across 10 US clock changes the volume profile moved with the US clock on average and beat 239 placebo Sundays. This is 10 events, and most of the size is in 2023–2024. |
| interpretation | Consistent with participation anchored to the US wall clock. No participant or cause is identified (the card forbids it). |
| claim decision | **L1 at most, with N up front, in `/research`:** «за 10 переводов часов в США дневной профиль объёма BTC в среднем сдвигался вместе с ними (2020–2024; эффект в основном в 2023–2024)». **No live line.** **Accumulate prospectively:** the next US transitions are 2026-11-01, 2027-03-14, 2027-11-07 and 2028-03-12. The 2025 and 2026-03 transitions lie on the BTCUSDT surface already opened for the product, so their status is stated in a design note before any use and is not decided here. |

**Against the expectation:**
- The estimate and direction stay visible, and the shortage of information is the headline.
- The next step is accumulation.
- It is neither dropped as "nothing" nor shown as a tendency.

## 4. Verdict on the format

| Failure criterion (expectations §4) | Outcome |
|---|---|
| Two units end with the same summary and claim | **No.** null → none / `/research` no-difference; R03-C1 → L1 + product baseline; D12 → `/research` L1 with N, accumulate. The old labels did not separate them: DH1-L2 `INCONCLUSIVE`, R03-C1 `NO_INCREMENTAL_STRUCTURE`. |
| A mandatory field needs new computation | **No.** One field was `NOT_IN_RECORD` (D12 interval, DH1-L2 placebo) and was shown as such. One interval was simple arithmetic on a recorded SE. |
| An L2 or edge line slips through for the wrong unit | **No.** |
| A confidence adjective is needed to separate them | **No.** The estimate, interval, information and stability fields carry it. |

**Result: `FORMAT_DISTINGUISHES_THE_THREE_TYPES`.** No unit is promoted, rescored or reclassified.

**Lessons for new units:**
- **Discovery-era records sometimes lack an interval** (D12). New result records must carry one, from the declared method.
- **R03-C1's nuisance retention (0.26)** says a volatility-aware baseline may absorb part of the weekend gap. The weekday/weekend unit therefore reports its candidates beside the current pooled baseline and does not assume the split is the only fix.
