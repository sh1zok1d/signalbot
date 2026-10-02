# Beta — historical analogue gate V1 ("Что было после похожих")

**Status:** `OWNER_DECISION_RECORDED / GATE_FROZEN_BEFORE_IMPLEMENTATION / NOT_ACTIVE`
**Date:** 2026-10-02
**Authority:** owner decision 2026-10-02, recorded in §8. It is the promotion gate (restart decision 7) for one surface: historical analogue summaries.
**Builds on:** `BETA_HISTORICAL_FOLLOW_UP_V0.md`, which provides the comparability identity, the ordinary and volatility-matched baselines, and the provenance classes. This gate lifts that document's "range only, no direction" display limit, but only for summaries that satisfy every rule below.
**Product context:** `BETA_V0_3_MARKET_BRIEFING.md`.

## 1. What is permitted, exactly

> P1 permits outcome-aware historical analogue summaries under a frozen analogue gate. Direct trade recommendations, directional forecasts, target prices, probabilities of future price direction, and optimized signal thresholds remain out of scope.

> Historical conditional statistics are allowed; a prediction engine is not.

**This is not a lifting of `PREDICTIVE_PRODUCT_FROZEN`.** No other surface may cite this gate to add a bias, lean, score, signal, target or direction call.

**The user's takeaway.** A typical honest screen reads "the direction was ordinary, the range was not". The edge is in the state of the market, not in its direction. The decision stays with the trader.

## 2. Mandatory rules (all of them; any breach blocks display)

**R1. Direction medians are shown.**
- Per horizon: the median close return from the event price, with the share of cases that closed below the event price.
- Horizons are 1h and 4h.

**R2. The baseline sits next to every number, in the same card.**
- "Обычный рынок" is the volatility-matched baseline of `BETA_HISTORICAL_FOLLOW_UP_V0.md` §4: same hour ±1h, same prior-1h range tercile, outside ±4h of any episode.
- It is never behind a button and never in Details only.

**R3. N and spread are always shown.**
- Spread is the 10th to 90th percentile of the event outcomes and of the baseline outcomes.
- **Sufficiency.** At least 30 events on at least 15 distinct UTC dates, per cohort and per cell.
- **Below that,** the card prints only "мало данных: N случаев за D дней". There is no median, no baseline and no verdict.

**R4. The verdict is mandatory.** Every shown cell carries one of the fixed sentences in §4. The verdict comes from the frozen test of §3, never from a human or an LLM.

**R5. Historical and live cohorts are never pooled.**
- They are shown as separate labelled blocks: `История: N случаев · <источник> · <период> · <определение>` and `Live beta: N случаев · с запуска`.
- Pooling needs a new owner decision once the live N is meaningful.

**R6. Sealed data stays sealed.**
- Protected Binance 2025/2026 research data is never read. The historical cohort ends 2024-12-31.
- **The live cohort** is the beta's own prospective tape. It is product evidence only, and never research confirmation (restart decision 6).

**R7. Similarity is frozen before any event-cohort outcome is computed.**
- **What is frozen:** the feature set, definitions, cut points and distances, matching, horizons, metrics, sufficiency, test, family and wording.
- **How.** All of it goes into `ANALOGUE_SPEC_V1`, and its digest is recorded in this file before the first outcome computation.
- **Changes.**
  - Any change is a new version with a written reason.
  - The reason may not cite the outputs of the old version.
  - "Take slightly more similar ones" after seeing results is forbidden.

**R8. No directional label unless the test passed, and none after it either.**
- **Never written:** bullish or bearish, bias, lean, edge, перевес, уклон, signal, "слабый медвежий уклон".
- **When the test did not pass,** only the "not found" sentence is printed. The numbers stay visible.
- **When it passed,** the fixed past-tense sentence of §4 is printed, with no further adjective.

**R9. Fixed closing line**, in every card: «Историческая выборка описывает прошлое и не является прогнозом текущего движения.»

**R10. Analogue statistics never steer the product.**
- They never trigger, rank, suppress or word a push.
- They never feed the §1.4 significance rule of the P1 contract.
- They never sort situations by historical return or "win rate".

**R11. What "отличается" means.**
- It describes the historical sample only. It is not a confirmed mechanism.
- Lifting it into any statement outside this card (a headline, a push, a research claim) needs the decision-layer bar of `research/DECISION_LAYER_RESEARCH_PROGRAM_V0.md`: independent confirmation and its own gate.

## 3. The frozen test

**Cells.** One cell = (analogue class, cohort, horizon, metric).
- **Metrics:**
  - `close_return_pct` (direction);
  - `realized_range_pct` (range).
- **Horizons:** 1h and 4h.
- **Definitions** are those of `beta/outcomes.py` (`BETA_OUTCOME_V1`), reproduced unchanged for the historical cohort.

**Statistic.**
- Per event: its outcome minus the mean outcome of its up to 5 matched controls. Matching follows `BETA_HISTORICAL_FOLLOW_UP_V0.md` §4, with no relaxation.
- The cell statistic is the median of these differences.

**Uncertainty.**
- A cluster bootstrap that resamples UTC dates, because events on the same day are not independent.
- B = 10 000 resamples with a fixed seed.
- The output is a two-sided bootstrap p-value. It is used internally and never displayed.

**Multiple testing.** Holm–Bonferroni at α = 0.05 across the frozen family: every cell the product can display for that cohort. The family is enumerated in `ANALOGUE_SPEC_V1`. A new cell means a new version.

**Verdict.** `ОТЛИЧАЕТСЯ` only if both hold:
- the Holm-adjusted p-value is below 0.05;
- the absolute median difference is at least the materiality floor.

Floors are frozen in the spec. Proposed: direction 0.10 pp at 1h and 0.20 pp at 4h; range 15% of the baseline median. Otherwise the verdict is `НЕ НАЙДЕНО`.

**Null calibration (must pass before any real card is wired).**
- Run the frozen pipeline on pseudo-events: anchors drawn from each cohort's eligible non-event anchors, matched in count and time-of-day profile, over at least 200 replicates.
- The family-wise rate of any `ОТЛИЧАЕТСЯ` must be ≤ 5% within Monte Carlo error.
- No event-cohort outcome is read in this step.
- If it fails, the spec is wrong. That gives a new version, fixed before any event outcome is opened.

**Expected result, stated in advance.** H05 rejected taker imbalance as a predictor of subsequent return, and the `PRICE_OI` pilot is `BALANCE_FAILED`. Most direction cells are therefore expected to print `НЕ НАЙДЕНО`. That is an acceptable and honest output, not a defect to fix.

## 4. Card format and fixed sentences

```
Что было после похожих · похоже на закрытие шортов (1h)

История: 47 случаев · Binance · 2020–2024 · одна биржа, определение приближённое
                     после похожих       обычный рынок
4ч цена    медиана   −0,48%              +0,03%
           разброс   −2,1…+1,2%          −1,6…+1,6%
           ниже цены события  29/47 (62%)      50%
4ч размах  медиана   2,9%                1,7%
Направление: убедительного отличия от обычного рынка не найдено.
Размах: в исторической выборке был заметно больше обычного.

Live beta: 9 случаев с запуска — мало данных для сравнения.

Сейчас отличается: объём выше, чем у 90% похожих; OI упал сильнее, чем у 80%.
Историческая выборка описывает прошлое и не является прогнозом текущего движения.
```

The 1h rows follow the same layout.

**Fixed sentences (ru; en mirrors them):**

| Case | Sentence |
|---|---|
| Direction, `НЕ НАЙДЕНО` | Направление: убедительного отличия от обычного рынка не найдено. |
| Direction, `ОТЛИЧАЕТСЯ` | Направление: в исторической выборке цена через {h} чаще была {ниже/выше}, чем на обычном рынке. |
| Range, `НЕ НАЙДЕНО` | Размах: убедительного отличия от обычного рынка не найдено. |
| Range, `ОТЛИЧАЕТСЯ` | Размах: в исторической выборке был заметно {больше/меньше} обычного. |
| Below sufficiency | мало данных: N случаев за D дней |

**"Сейчас отличается"** compares the current case's own features with the cohort's feature distribution:
- up to 3 features whose current percentile is outside 20–80 within the cohort;
- no outcome words.

**Forbidden in the card**, guarded by a formatter test:
- bullish, bearish, bias, edge, перевес, уклон, сигнал;
- вероятность, шанс, ожидается, будет;
- the word «прогноз», except in the fixed closing line;
- цель, таргет;
- imperative long/short, покупать, продавать;
- p-value, значимо.

## 5. Analogue classes and cohorts

**Analogue class** (`ANALOGUE_CLASS_V1`, hashed like `EVENT_COMPARABILITY_V0`):
- the 1h state label of `BETA_MARKET_STATE_LABELS_V1`;
- the §1.4 significance rule of the P1 contract;
- the version labels of both.

The live cohort may additionally key on detector event classes through `EVENT_COMPARABILITY_V0`.

**Cohorts**

| Cohort | Source | Definition class | Label shown |
|---|---|---|---|
| History | Binance USDT-M perpetual CORE data, from the first date the CORE manifest marks each field defensible, to 2024-12-31 | `HISTORICAL_SINGLE_VENUE_V1`: the same label logic on single-venue fields (price, volume, taker buy share, funding; OI only where defensible) | `Binance · <период> · одна биржа, определение приближённое` |
| Live beta | beta state tape V2, `LIVE_OBSERVED` only | `LIVE_MULTI_VENUE_V1`: the P1 labels as computed live | `Live beta · с запуска` |

**Approximation in the historical cohort.** The venue-agreement clause of the significance rule cannot be evaluated on one venue, so the historical cohort drops it. This is one reason its definition is labelled approximate.

**Labels that need missing fields.** A label whose own condition needs liquidations (вынос лонгов / вынос шортов) has no historical definition. Its history block prints «нет истории для этого состояния». Nothing is substituted.

**Reconstructed rows.** Rows reconstructed from live-collected raw data keep their provenance class (`BETA_HISTORICAL_FOLLOW_UP_V0.md` §5). They are never labelled live.

## 6. Activation preconditions (all required; default off)

1. **Spec frozen.** `ANALOGUE_SPEC_V1` is committed and its digest recorded here, with `EVENT_COHORT_OUTCOMES_OPENED = false` at freeze time.
2. **Null calibration (§3) passes.** The report is committed.
3. **Offline tests pass:**
   - the wording guard of §4;
   - sufficiency;
   - cohort separation, with no pooled statistic anywhere;
   - a date guard that rejects any 2025/2026 historical input;
   - as-of correctness;
   - R10: no analogue value reaches the push path.
4. **Owner review of rendered cards,** first with synthetic numbers, then real.
5. **Owner switch.** A durable owner switch (`/admin_analogues_on`), off by default, the same pattern as D7. The committed configuration flag is the hard allow.

## 7. Relationship to existing documents

- **`BETA_HISTORICAL_FOLLOW_UP_V0.md`.** Its range-only formatter and its directional-word guard stay authoritative for V0 output. A V1 formatter implements §4.
- **`PRODUCT_DIRECTION_AFTER_BETA_PROPOSAL.md`.** Its item 3 ("no direction") is superseded, for this surface only.
- **`research/DECISION_LAYER_RESEARCH_PROGRAM_V0.md`.** Unchanged. A confirmed statement still needs its bar (R11).
- **`research/BETA_V0_PROSPECTIVE_FORWARD_EVALUATION.md`.** Unchanged. Live-cohort numbers are never independent confirmation.

## 8. Owner decisions recorded (2026-10-02)

| # | Decision |
|---|---|
| 1 | Direction medians are shown; hiding them is not wanted. |
| 2 | The baseline is mandatory in the same card, never behind a button. |
| 3 | N and spread are mandatory. |
| 4 | The verdict ("отличается" / "убедительного отличия не найдено") is mandatory, computed by the product. |
| 5 | Historical 2020–2024 and live beta cohorts are shown separately and labelled. Pooling is a later decision. |
| 6 | Sealed 2025/2026 stays sealed. |
| 7 | Similarity (features, distances, thresholds) is frozen before outcomes. "Slightly more similar" after results is forbidden. |
| 8 | No directional label (bullish, bearish, bias, lean) unless the test passed. The numbers are shown, the verdict is a fixed sentence. |
| — | The permission is narrowed to "outcome-aware historical analogue summaries". It is not a lifting of the predictive freeze. |
