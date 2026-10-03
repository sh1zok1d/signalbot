# Beta — historical analogue gate V1 ("Что было после похожих")

**Status:** `OWNER_DECISION_RECORDED / GATE_FROZEN_BEFORE_IMPLEMENTATION / NOT_ACTIVE / DO_NOT_BUILD_YET (2026-10-02)`
**2026-10-03:** superseded by `PRODUCT_DECISION_V2_DECISION_SUPPORT.md` §3: analogue statistics are built (`beta/analogues.py`, `beta/levels.py`) under the lighter honesty rule — N and a volatility-matched "обычно" beside every number, a day-clustered bootstrap with Holm across the family and a materiality floor for «отличается». This gate's spec-digest and 1000-replicate null-calibration preconditions no longer apply. Kept as the record of the earlier design.
**2026-10-02:** analogue cards are on the DO-NOT-BUILD-YET list of `PRODUCT_FIRST_DECISION_V1.md` §5 until user evidence from its §7 test exists. The gate text is unchanged and remains the only path for this surface when it is built.
**Date:** 2026-10-02 (repair of the same day: sufficiency split, calibration bound, floors, historical proxy mapping, R8, control share)
**Authority:** owner decision 2026-10-02, recorded in §9. It is the promotion gate (restart decision 7) for one surface: historical analogue summaries.
**Builds on:** `BETA_HISTORICAL_FOLLOW_UP_V0.md`, which provides the comparability identity, the ordinary and volatility-matched baselines, and the provenance classes. This gate lifts that document's "range only, no direction" display limit, but only for summaries that satisfy every rule below.
**Product context:** `BETA_V0_3_MARKET_BRIEFING.md`.

## 1. What is permitted, exactly

> P1 permits outcome-aware historical analogue summaries under a frozen analogue gate. Direct trade recommendations, directional forecasts, target prices, probabilities of future price direction, and optimized signal thresholds remain out of scope.

> Historical conditional statistics are allowed; a prediction engine is not.

**This is not a lifting of `PREDICTIVE_PRODUCT_FROZEN`.** No other surface may cite this gate to add a bias, lean, score, signal, target or direction call.

**The user's takeaway.** A typical honest screen reads "the direction was ordinary, the range was not". The product may describe differences in market state or range even when no directional difference is detected. The decision stays with the trader.

## 2. Mandatory rules (all of them; any breach blocks display)

**R1. Direction medians are shown.**
- Per horizon: the median close return from the event price, with the share of cases that closed below the event price.
- Horizons are 1h and 4h.

**R2. The baseline sits next to every number, in the same card.**
- **Definition.** "Обычный рынок" is computed from matched controls only: the volatility-matched controls of `BETA_HISTORICAL_FOLLOW_UP_V0.md` §4 (same hour ±1h, same prior-1h range tercile, outside ±4h of any episode, up to 5 controls per event).
- **Every baseline number comes from those controls,** the share below the anchor price included (§3.1). Nothing is hardcoded: no "50%", no "0%".
- **Placement.** It is never behind a button and never in Details only.

**R3. N, spread and the baseline are always shown. Two separate sufficiency levels:**

| Level | Meaning | Requirement | Below it |
|---|---|---|---|
| `DISPLAY_FLOOR` | A display convention only. It is not evidence of a sufficient independent sample. | ≥ 30 events on ≥ 15 distinct UTC dates, per cohort and cell | Descriptive statistics are still shown (N, median, spread, matched baseline). The fixed verdict is «мало данных — вывод не рассчитывается». |
| `INFERENTIAL_SUFFICIENCY` | Whether the test of §3 may resolve the verdict | ≥ `INFERENTIAL_MIN_DATE_CLUSTERS` independent date clusters with matched controls (§3.3), plus the feasibility checks of §3.3 | The fixed verdict is «мало независимых дней — вывод не рассчитывается». |

**Spread** is the 10th–90th percentile. When N < 10 it is printed as `мин…макс` and labelled so.

**R4. The verdict is mandatory.**
- Every shown cell carries exactly one fixed sentence from §5.
- `ОТЛИЧАЕТСЯ` and `НЕ НАЙДЕНО` are resolved only by the frozen test of §3, and only when R3's inferential sufficiency holds.
- Never by a human, never by an LLM.

**R5. Live and historical cohorts are never pooled.**
- They are shown as separate labelled blocks.
- The historical block is a declared proxy (§6). It is never presented as the same identity as the live class.
- Pooling needs a new owner decision once the live N is meaningful.

**R6. Sealed data stays sealed.**
- Protected Binance 2025/2026 research data is never read. The historical cohort ends 2024-12-31.
- **The live cohort** is the beta's own prospective tape. It is product evidence only, and never research confirmation (restart decision 6).

**R7. Everything is frozen before any event-cohort outcome is computed:**
- the feature set, definitions, cut points and distances;
- the live→proxy mapping (§6);
- matching, horizons, metrics, sufficiency, test, family, materiality floors (§3.4) and wording.

**How.** All of it goes into `ANALOGUE_SPEC_V1`, and its digest is recorded in this file before the first event-cohort outcome computation.

**Changes.**
- Any change is a new version with a written reason.
- The reason may not cite the outputs of the old version.
- "Take slightly more similar ones" after seeing results is forbidden.

**R8. Directional labels are forbidden, always.**
- **Never written, whatever the test result:** bullish, bearish, bias, lean, edge, перевес, уклон, signal, "слабый медвежий уклон" and equivalents.
- **A passed test** (`ОТЛИЧАЕТСЯ`) permits only the fixed past-tense historical comparison sentence of §5. It permits no label, adjective or summary word.
- **A test that did not pass** prints the "not found" sentence. The numbers stay visible.

**R9. Fixed closing line**, in every card: «Историческая выборка описывает прошлое и не является прогнозом текущего движения.»

**R10. Analogue statistics never steer the product.**
- They never trigger, rank, suppress or word a push.
- They never feed the briefing significance rule of the P1 contract.
- They never sort situations by historical return or "win rate".

**R11. What "отличается" means.**
- It describes the historical sample only. It is not a confirmed mechanism.
- Lifting it into any statement outside this card (a headline, a push, a research claim) needs the decision-layer bar of `research/DECISION_LAYER_RESEARCH_PROGRAM_V0.md`: independent confirmation and its own gate.

## 3. The frozen test

### 3.1 Cells and statistics

**Cells.** One cell = (analogue class, cohort, horizon, metric).
- **Metrics:**
  - `close_return_pct` (direction);
  - `realized_range_pct` (range).
- **Horizons:** 1h and 4h.
- **Definitions** are those of `beta/outcomes.py` (`BETA_OUTCOME_V1`), reproduced unchanged for the historical proxy.

**Per event.** Its outcome minus the mean outcome of its matched controls. Matching follows `BETA_HISTORICAL_FOLLOW_UP_V0.md` §4, with no relaxation. An event with no match is excluded and counted.

**Cell statistic.** The median of these per-event differences.

**Displayed baseline.**
- Median: the median across events of each event's control mean.
- Spread: the 10th–90th percentile of control outcomes.
- **Share below the anchor price:** for each event, the fraction of its controls that closed below their own anchor price; then the mean of these fractions across events. The event column shows k/N for the events themselves.

### 3.2 Uncertainty and multiple testing

**Uncertainty.**
- A cluster bootstrap that resamples UTC dates, because events on the same day are not independent.
- B = 10 000 resamples with a fixed seed.
- The output is a two-sided bootstrap p-value. It is used internally and never displayed.

**Multiple testing.** Holm–Bonferroni at α = 0.05 across the frozen family: every cell the product can display for that cohort. The family is enumerated in `ANALOGUE_SPEC_V1`. A new cell means a new version.

**Verdict, when R3's inferential sufficiency holds.** `ОТЛИЧАЕТСЯ` only if both hold:
- the Holm-adjusted p-value is below 0.05;
- the absolute cell statistic is at least the frozen materiality floor of §3.4.

Otherwise the verdict is `НЕ НАЙДЕНО`.

### 3.3 Inferential sufficiency (fixed now, before any outcome)

**Independent date cluster.** A UTC date with at least one event that has matched controls. Events on adjacent dates within 4h of each other belong to the cluster of the earlier date.

**`INFERENTIAL_MIN_DATE_CLUSTERS` = max(30, C\*).**
- C\* is the smallest cluster count at which the outcome-blind calibration of §3.5 passes, for that cohort and cell family.
- The floor of 30 is fixed here. Calibration may raise the requirement, never lower it.
- The value is frozen in `ANALOGUE_SPEC_V1` before any event outcome is computed.

**Feasibility checks.** All must hold, or the cell is inferentially insufficient:
- at least 80% of events have the full set of matched controls;
- no single date cluster holds more than 10% of the events.

### 3.4 Materiality floors: `TBD_BEFORE_EVENT_OUTCOMES`

**No floor is approved yet.** The figures discussed earlier (0.10 pp / 0.20 pp / 15%) are withdrawn as proposals.

**Derivation rule** (fixed here; numbers computed later):
- For each cohort, horizon and metric, the floor is the 90th percentile of the absolute cell statistic across null pseudo-event replicates at the cohort's own N and cluster count (§3.5).
- Only controls and pseudo-events are used: no event-cohort outcome.

The floors are frozen into `ANALOGUE_SPEC_V1` before any event-cohort outcome is opened. **After event outcomes are opened, floors cannot change.** A change means a new version with new, unopened data.

### 3.5 Null calibration (outcome-blind; must pass before any real card is wired)

**Pseudo-events.**
- Anchors drawn from each cohort's eligible non-event anchors: outside ±4h of any real event, matched in count, cluster structure and time-of-day profile to the cohort.
- Their outcomes and those of their matched controls are read.
- **No real event-cohort outcome is read at any point.**

**Replicates.** R ≥ 1000 per cohort, seed frozen in the spec.

**Measured.** k = the number of replicates in which at least one cell of the family resolves `ОТЛИЧАЕТСЯ`, with the frozen test, floors and sufficiency.

**Acceptance (formal).** The one-sided 95% Clopper–Pearson upper bound of k/R must be ≤ 0.07, which is nominal α 0.05 plus 2 pp tolerance. For R = 1000 this is k ≤ 56.

**Order of operations** (avoids tuning on the same noise):
1. **Replicate set A** (R ≥ 1000) gives the null distributions, and from them the floors (§3.4).
2. **Replicate set B** (R ≥ 1000, independent seed), run with the floors fixed, gives C\* (§3.3) and the acceptance check above.

**Failure.** The spec is wrong. That gives a new version, fixed before any event outcome is opened.

**Expected result, stated in advance.** H05 rejected taker imbalance as a predictor of subsequent return, and the `PRICE_OI` pilot is `BALANCE_FAILED`. Most direction cells are therefore expected to print `НЕ НАЙДЕНО`. That is an acceptable and honest output, not a defect to fix.

## 4. Card format

```
Что было после похожих · похоже на закрытие шортов (1ч)

История (прокси): похожие по доступным историческим признакам Binance
47 случаев · 41 независимый день · 2022–2024 · одна биржа
                     после похожих       обычный рынок (контроли)
4ч цена    медиана   −0,48%              +0,03%
           разброс   −2,1…+1,2%          −1,6…+1,6%
           ниже цены события  29/47 (62%)      46%
4ч размах  медиана   2,9%                1,7%
Направление: убедительного отличия от обычного рынка не найдено.
Размах: в исторической выборке был заметно больше обычного.

Live beta: 9 случаев · 7 дней · с запуска
4ч цена    медиана   +0,21%              −0,05%
           разброс   мин…макс −1,4…+1,9%  −1,3…+1,2%
           ниже цены события  4/9               51%
Мало данных — вывод не рассчитывается.

Сейчас отличается: объём выше, чем у 90% похожих; OI упал сильнее, чем у 80%.
Историческая выборка описывает прошлое и не является прогнозом текущего движения.
```

The 1h rows follow the same layout.

**What the example shows:**
- every baseline number comes from controls (46%, 51%), never a hardcoded 50%;
- the live block below `DISPLAY_FLOOR` still shows its numbers, with no verdict;
- the historical block is labelled a proxy, and its period starts where Binance OI becomes defensible, because this state needs OI.

## 5. Fixed sentences (ru; en mirrors them)

| Case | Sentence |
|---|---|
| Direction, `НЕ НАЙДЕНО` | Направление: убедительного отличия от обычного рынка не найдено. |
| Direction, `ОТЛИЧАЕТСЯ` | Направление: в исторической выборке цена через {h} чаще была {ниже/выше}, чем у контрольных периодов. |
| Range, `НЕ НАЙДЕНО` | Размах: убедительного отличия от обычного рынка не найдено. |
| Range, `ОТЛИЧАЕТСЯ` | Размах: в исторической выборке был заметно {больше/меньше}, чем у контрольных периодов. |
| Below `DISPLAY_FLOOR` | Мало данных — вывод не рассчитывается. |
| Display floor met, inferential sufficiency not met | Мало независимых дней — вывод не рассчитывается. |
| State has no honest historical proxy (§6) | История недоступна: для этого состояния нет честной исторической реконструкции. |

**"Сейчас отличается"** compares the current case's own features with the cohort's feature distribution:
- up to 3 features whose current percentile is outside 20–80 within the cohort;
- no outcome words.

**Forbidden in the card**, guarded by a formatter test:
- bullish, bearish, bias, lean, edge, перевес, уклон, сигнал;
- вероятность, шанс, ожидается, будет;
- the word «прогноз», except in the fixed closing line;
- цель, таргет;
- imperative long/short, покупать, продавать;
- p-value, значимо.

## 6. Analogue classes: live identity and historical proxy

**`LIVE_ANALOGUE_CLASS_V1`** (hashed like `EVENT_COMPARABILITY_V0`) is the live identity:
- the 1h state label of the briefing episode (`BETA_MARKET_STATE_LABELS_V1`) at its opening;
- the briefing significance rule of the P1 contract, including its venue-agreement clause;
- the version labels of both;
- the multi-venue source set.

**`HISTORICAL_PROXY_CLASS_V1`** is a different identity: a declared Binance single-venue proxy of a live class.
- It is reached only through the frozen mapping `LIVE_ANALOGUE_CLASS_V1 → HISTORICAL_PROXY_CLASS_V1`.
- The mapping and its digest are part of `ANALOGUE_SPEC_V1`.

**Each mapping row lists:**
- the live class;
- its essential features;
- for each essential feature, whether it can be honestly reconstructed from Binance CORE data and from which date;
- every clause that is dropped or changed (for example the venue-agreement clause);
- the resulting proxy class, or `HISTORY_UNAVAILABLE`.

**Rules.**
- **Unavailable feature.** If any essential feature of a state cannot be honestly reconstructed, that state has no history: §5 «История недоступна…». There is no silent relaxation and no substitute feature.
- **Dropped clauses.** A clause may be dropped only if the mapping row declares it explicitly. The proxy is then labelled as such to the user: «История (прокси): похожие по доступным историческим признакам Binance».
- **Proxy period.** The period runs from the first date at which all essential features of the proxy are defensible in the CORE manifest, to 2024-12-31. It is printed in the card.

**Draft mapping** (illustrative; the frozen table is in `ANALOGUE_SPEC_V1`):

| Live state | Essential features | Historical proxy |
|---|---|---|
| похоже на закрытие шортов / лонгов, похоже на рост с набором новых лонгов, похоже на снижение с набором новых шортов, похоже на набор позиций без движения цены, похоже на разгрузку рынка | price, OI, taker share | proxy on Binance price, OI and taker; venue agreement dropped (declared); period = Binance OI defensible span |
| сжатие | range, OI | proxy on Binance range and OI; venue agreement dropped (declared) |
| похоже на поглощение агрессивных покупок / продаж | taker share, price | proxy on Binance klines taker volume; venue agreement dropped (declared) |
| вынос лонгов / вынос шортов | liquidations by side | `HISTORY_UNAVAILABLE` (no honest historical liquidation series) |
| обычное состояние | — | no analogue card |

**Reconstructed live rows.** Rows reconstructed from live-collected raw data keep their provenance class (`BETA_HISTORICAL_FOLLOW_UP_V0.md` §5). They are never labelled live.

## 7. Activation preconditions (all required; default off)

1. **Spec frozen.** `ANALOGUE_SPEC_V1` is committed and its digest recorded here, with `EVENT_COHORT_OUTCOMES_OPENED = false` at freeze time. It includes:
   - the live→proxy mapping;
   - the family;
   - `INFERENTIAL_MIN_DATE_CLUSTERS`;
   - the materiality floors.
2. **Null calibration (§3.5) passes.** The report is committed, with R, k and the Clopper–Pearson bound.
3. **Offline tests pass:**
   - the wording guard of §5, including R8 for every verdict;
   - both sufficiency levels;
   - baselines computed from controls, never constants;
   - cohort separation, with no pooled statistic anywhere;
   - the mapping digest, and `HISTORY_UNAVAILABLE` for states with a missing essential feature;
   - a date guard that rejects any 2025/2026 historical input;
   - as-of correctness;
   - R10: no analogue value reaches the push path.
4. **Owner review of rendered cards,** first with synthetic numbers, then real.
5. **Owner switch.** A durable owner switch (`/admin_analogues_on`), off by default, the same pattern as D7. The committed configuration flag is the hard allow.

## 8. Relationship to existing documents

- **`BETA_HISTORICAL_FOLLOW_UP_V0.md`.** Its range-only formatter and its directional-word guard stay authoritative for V0 output. A V1 formatter implements §5.
- **`PRODUCT_DIRECTION_AFTER_BETA_PROPOSAL.md`.** Its item 3 ("no direction") is superseded, for this surface only.
- **`research/DECISION_LAYER_RESEARCH_PROGRAM_V0.md`.** Unchanged. A confirmed statement still needs its bar (R11).
- **`research/BETA_V0_PROSPECTIVE_FORWARD_EVALUATION.md`.** Unchanged. Live-cohort numbers are never independent confirmation.

## 9. Owner decisions recorded (2026-10-02)

| # | Decision |
|---|---|
| 1 | Direction medians are shown; hiding them is not wanted. |
| 2 | The baseline is mandatory in the same card, never behind a button. It is computed from matched controls, never hardcoded. |
| 3 | N and spread are mandatory. `DISPLAY_FLOOR` (30 events / 15 dates) is a display convention, not evidence of sufficiency. Below it, the numbers are shown and the verdict is not computed. |
| 4 | The verdict is mandatory and product-computed. It is resolved only with separate inferential sufficiency, defined before outcomes. |
| 5 | Historical and live cohorts are shown separately and labelled. The historical block is an explicit proxy class reached through a frozen mapping. Pooling is a later decision. |
| 6 | Sealed 2025/2026 stays sealed. |
| 7 | Similarity, mapping, floors and sufficiency are frozen before outcomes. Floors come from an outcome-blind calibration and never change after event outcomes are opened. |
| 8 | Directional labels (bullish, bearish, bias, lean, edge) are forbidden always. A passed test permits only the fixed past-tense comparison sentence. |
| 9 | Null calibration uses ≥ 1000 pseudo-event replicates. Acceptance uses the one-sided 95% Clopper–Pearson bound ≤ 0.07 and stays outcome-blind with respect to the real event cohort. |
| — | The permission is narrowed to "outcome-aware historical analogue summaries". It is not a lifting of the predictive freeze. |
