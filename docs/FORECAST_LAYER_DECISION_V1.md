# Forecast layer — owner decision V1 (level race probabilities in the beta)

**Status:** `OWNER_DECISION_RECORDED (2026-10-08) / ACTIVE / NOT_IMPLEMENTED`
**Authority:** the owner's decisions of 2026-10-08, recorded verbatim in §1. This file amends `PRE_BETA_SCOPE_DECISION_V1.md` §2.2 and §2.3 (see §9), adds work to the pre-beta scope and replaces one research target of `research/LEVEL_ENGINE_CONFIRMATION_PORTFOLIO_V1.md`.
**Unchanged:**
- `PRODUCT_DECISION_V2_DECISION_SUPPORT.md` §3: no direct trade calls; N and «обычно» beside every number; tracked accuracy beside every forecast.
- The L0–L4 ladder of `research/EVIDENCE_AND_CLAIMS_DECISION_V1.md`.
- The protected-data rules and the E1-RUN-001 holdout.
- Every sealed research record.

**Chain of command for this work:** `ORCHESTRATION_V1.md`.

```
FORECAST_OBJECT    = first passage inside the original 4h window of a structural first touch:
                     BREAK barrier first / REJECT barrier first / neither (three outcomes)
EVENTS             = #352 constructor: PDH PDL PWH PWL PMH PML, zone half-width 0.15 %, touch 1
BARRIERS           = #352: X = 0.5 × 1.2816 × σ × √48 beyond the zone edge (σ = 288 bars before the touch)
LANDMARKS          = T0 (touch-bar close) and T15 (close of bar j+2); one claim class each, one forecast per event
«ОБЫЧНО»           = HIST: B0, driftless first-passage geometry at the same position, PIT σ and time left;
                     model states: G1, the generic race model at the event's geometry (amended 2026-10-08, §6b)
PREDICTOR          = frozen and versioned; no online learning
CALIBRATOR         = two-parameter Bayesian logistic recalibration per outcome head, batched, versioned
HELD-OUT HISTORY   = Binance BTCUSDT 2025-01-01 → the freeze date, minus the E1-RUN-001 holdout; read once
LIVE RECORD        = beta claim journal (beta/claims.py), classes L3_LEVEL_RACE_T0_4H and L3_LEVEL_RACE_T15_4H
DISPLAY            = in the beta from Day 0 in HIST (history line); the model states follow later (§6a)
#363 PROSPECTIVE   = replaced by challenger C1 in a paired prospective comparison (§7)
#368 PROSPECTIVE   = long science track; never a gate for this layer or for the beta
```

## 1. What the owner decided (verbatim, 2026-10-08)

**Display in the beta:**
- «Показывать хочу сразу в бете и это надо изменить в документах. Решение владельца.»
- To the question "shadow now and display after the beta, or display before Day 0 too?": «Пока до дня 0». Read with the line above: display in the beta from Day 0.

**Day 0 (later the same day):** asked to choose between (a) Day 0 waits for the frozen model and (b) Day 0 earlier with a history line at the start and the full display later: «Б вариант, сразу по истории». See §6a.

**The Level Engine chain:**
- «Пр в мейн делай.» The Level Engine chain goes to main (PR #376).
- «Курсор остановлен.» The `cursor/level-*` agent is stopped; its chain is now owned by ОПГ-2 (`ORCHESTRATION_V1.md`).

**#363:** replacing its prospective confirmation (portfolio P3-2) by a challenger in the live forecast: «Да».

**Chain of command:**
- «Ты - главный архитектор который отвечает за продукт и ведет его к этапу инвайтов в бету.»
- «Полномочия у тебя выше нежели у опг 1 - ты над ним.» ОПГ-1 is re-subordinated to the chief architect («Переподчиняешь под себя»).

## 2. Why the object looks like this

This is the review of 2026-10-08, from the recorded Level Engine results only. No outcome was computed for it.

**Most of the T+15m information is geometry.**
- `END_POSITION_X` (#361) is the position of price between the two barriers. For a driftless walk, the chance of reaching the upper barrier first is the share of the distance already covered.
- With the recorded SD of `END_POSITION_X` (≈ 0.62 X) and a REJECT-to-BREAK span of about 2.45 X, geometry alone predicts ≈ 25 pp per +1 SD. #361 recorded +20 pp on the real arm and +30 pp on the pseudo arm.
- So skill is measured against the geometric baseline B0, not against 50 % or a base rate, and B0 is the «обычно» shown beside the number.

**NEITHER is real.**
- On the #363 support, events unresolved at T+15m ended BREAK 36 %, REJECT 50 % and NEITHER 14 % (N = 1235).
- #361 and #363 estimated their slopes among events that later resolved. That conditions on the future, so their coefficients are not reused; the model is refit on three outcomes at the decision time.

**The level-specific information is the structural-versus-pseudo offset.**
- #357 decomposition on BitMEX: BREAK +10 pp. #365 on Binance: cumulative BREAK incidence 0.470 versus 0.379.
- A generic first-passage model under-predicts BREAK at structural levels. The offset is what the Level Engine adds.

**Events are few.**
- About 7.5 structural first touches per week (T0) and 5 unresolved at T+15m.
- Hence the held-out history (§4) and pooling with a dense generic race stream (§5) instead of waiting for live data from zero.

## 3. Models

| Name | What | Parameters |
|---|---|---|
| **B0** | Driftless Brownian first passage of the two barriers with PIT σ, current position and time left in the 4h window; three outcomes (closed-form series or fixed-seed simulation) | 0 |
| **B1** | Climatology by family × structural side on the development years | ≤ 6 |
| **M1** (champion candidate) | Multinomial logit, or two heads (resolve by 4h; BREAK given resolve), offset by B0, plus family, side, landmark and σ tercile; ridge | ≤ 10 |
| **C1** (challenger) | M1 + `OTHER_VENUE_MEDIAN_MOVE` (#363 definition) from live three-venue klines | M1 + 1 |

**Not in any model:**
- The closed Level Engine nulls: touch ordinal, rejection speed, approach geometry, static level properties, OI, taker, joint OI/taker/price state, ±1 % book, path memory, spot after the perp move, the sequence taxonomy, zone notional.
- The #365 clock and the #368 RV transition (`RV_POST60` is not known at T+15m).
- Gradient boosting and neural networks: about 1 200 development events cannot support them.

**Decision-time hygiene:**
- Standardization moments and tercile edges come from training folds only.
- The pseudo map, which is built from a closed cohort, never enters a live input.

**One detector.** The live event must equal the #352 `build_episodes` / first-touch construction. It reuses the product level code, not a second detector, and gets a parity test against the research constructor on history before any live record counts.

## 4. Stages and data

| Stage | Data | Rule |
|---|---|---|
| Development | Binance USD-M BTCUSDT 2020–2024 (`CORE_BTC_BINANCE_V0`, the discovery surface) | Rolling-origin by year, week clusters. The variant menu (≤ 6) is fixed in the design note before any outcome and counted in the exposure ledger |
| Freeze | — | Code, coefficients, B0 and evaluation rules committed; the commit is the model version |
| Held-out history | Binance BTCUSDT 2025-01-01 → freeze date. No bar of `[2026-08-16T00:00Z, 2026-08-25T17:20Z)` and no window touching it | Read once, after the freeze. Product-open under V2 §4. The Level Engine chain never read 2025/2026. The product's first-touch hold statistics read a neighboring outcome there, so the surface class is `TIME_DISJOINT_EXPOSED_SURFACE_REPLICATION`-like and is disclosed. Roughly 400–450 T15 events and 600–700 T0 events |
| Live shadow | From the freeze | Every eligible event is written to the journal before its outcome, shown or not |
| Calibrator | Held-out history and live only | Never fitted on development years |

The design note of the model is committed before the held-out read. It fixes:
- the menu;
- the gates of §6 (tolerances and N);
- the drift rules of §7;
- the wording templates.

## 5. Live record, calibration and evaluation

**Record per forecast:**
- issue time, landmark, event id, model version, calibrator version and feature digest;
- raw and published probabilities of the three outcomes;
- the B0 probabilities and the evaluation rule id;
- outcome `UNKNOWN` until it resolves.

**Journal.** The journal already refuses an outcome under another rule. Displays are linked separately, as for the other claims.

**Prequential calibration.**
- The calibrator used at time t is fitted only on outcomes resolved before t.
- Updates are batched (weekly, later monthly) and stamped with a version.
- Prior: the held-out fit, worth about 100–200 events.
- No isotonic or other non-parametric calibrator below 300 events.
- A large required correction is a drift signal (§7), not a fix.

**Pooling.** A generic race engine (the same B0/M1 machinery on any two prices, extending `beta/rangecast.py`) issues forecasts on the hourly grid. It gives about 40 independent 4h windows a week, so its calibration matures in weeks. The level classes then have to show only that the level offset is not off.

**Metrics, in order:**
1. log-loss skill against B0 (and B1);
2. calibration intercept and slope with intervals, plus a 5-bin reliability table;
3. Brier score with its decomposition, for user-facing «говорили X → было Y»;
4. sharpness (share of forecasts outside 40–60 %);
5. AUC as a diagnostic.

ECE is descriptive only. Uncertainty is clustered by week. Raw and published probabilities are evaluated separately.

## 6. Display states and the Day-0 gate

| State | When | Wording (template ids fixed in the design note) |
|---|---|---|
| `HIST` | Before the held-out check passes, or after a fallback with no calibrated model | L2, past tense: «в истории похожих касаний: раньше дошла до {цена A} в X % (обычно Y %), N = …» |
| `L3_HISTORY_BACKED` | The held-out check meets the frozen tolerance | Wording "B" of PRE_BETA §5: «≈ X % раньше {цена A}, чем {цена B} · ни одной за 4ч ≈ Z % · обычно Y % · на истории: говорили X → было X′, N = … · live: копится (N = …)» |
| `L3_LIVE` | Live N per class at or above the frozen floor (planning value 150) and the live calibration within tolerance | as above, the live line replacing «копится» |
| `FALLBACK` | Drift rule (§7) | The B0 / generic-race probability with its own calibration line; the level offset is not claimed |
| `OFF` | Data fault, stale data or a parity break | no number; «нет данных» |

**Rules for every state:**
- Prices, never «пробой/отбой» or BREAK/REJECT, and never buy/sell, long/short or an entry.
- The three outcomes together, never one hidden.
- Data time, and one disclaimer in `/terms`.
- If M1 does not beat B0 on the held-out check, the calibrated B0 is what is published and no level effect is claimed.

**Surfaces:**
- **T0:** one line in the existing level-touch push. No new push type.
- **T15:** `/levels` and `/check` (the race of the level's two barriers).
- **Two user prices in `/check`:** the generic race line is allowed under the same engine and gates if it costs Day 0 nothing. That is the architect's call; otherwise it waits until after the beta.

**Day-0 gate.** A frozen model, the held-out check run once, and live shadow logging running. If the held-out tolerance is not met by Day 0, the layer ships in `HIST` / `FALLBACK` and Day 0 is not delayed for it. *(Superseded by §6a.)*

## 6a. Day 0 with the history line (owner, 2026-10-08: «Б вариант, сразу по истории»)

- **Day 0 does not wait for the model.** The layer ships in `HIST`: the race frequencies of a fixed, predeclared state set (family, structural side, landmark, position band at T15), each with N and the B0 geometric «обычно», in the past tense of L2. It sits on the same surfaces (T0 line in the level push, T15 in `/levels` and `/check`).
- **The history line is computed on 2020–2024 only** (`CORE_BTC_BINANCE_V0`) and labelled with those years. 2025/2026 stays unread for race outcomes, so the one-shot held-out check of §4 keeps its value.
- **Every eligible `HIST` statement is logged** in the claim journal from Day 0, shown or not, as an L2 class (EVIDENCE_AND_CLAIMS §5).
- **The model states** (`L3_HISTORY_BACKED`, `L3_LIVE`, `FALLBACK`) follow after the freeze and the held-out check. They reach the running beta as a predeclared upgrade on a fixed date (owner, 2026-10-08: «вариант 2 выбираю. Можно корректировать во время беты»).
- **Changes during the beta.** This is an exception to `PRODUCT_FIRST_DECISION_V1` §7 for the forecast layer only. The upgrade to the model states, and later corrections of the layer, may ship during the 30-day test under three conditions:
  - each change is announced in advance with its date and content;
  - each change is recorded as a dated event in the measurement contract;
  - every metric is reported separately before and after that date.

  The switch itself is one predeclared setting. The state rules of §6–§7 stay frozen. Other product areas keep §7 as written.


## 6b. «Обычно» in the model states and the level-offset claim (architect, 2026-10-08, before the model freeze)

The development record (`research/LEVEL_RACE_FORECAST_V1_DEVELOPMENT.md`) shows that the largest M1 term is the volatility term, which the generic race model G1 also carries. M1 beating B0 is therefore not by itself a level effect.

- **«Обычно» in `L3_HISTORY_BACKED`, `L3_LIVE` and `FALLBACK`:** G1 applied to the event's geometry, meaning any price at the same distances, with the same σ and time left. B0 stays in the journal as a second baseline. `HIST` V1 keeps its frozen «обычно», the cell mean of B0.
- **The level-offset claim** (internal and in any wording) also needs M1 to beat G1 on the event geometry, with an interval above 0 on the held-out check. This bar was added after development and before the held-out read, and it raises the bar.
- **`FALLBACK`** is published for a class only if the fallback model passes the calibration gate on that class; otherwise the class shows `HIST`.

## 7. Drift, fallback and challengers

**Monitors, all rules frozen before display:**
- an anytime-valid sequential test on the calibration intercept (e-process or CUSUM on y − p);
- rolling paired log loss against B0 over the last ~100 events;
- input drift: σ, position and event rate;
- data health.

**State changes (planning values; the design note fixes them):**
- data fault or parity break → `OFF` at once;
- e-value above 10, or the intercept interval outside ±10 pp → `FALLBACK`;
- return after at least 50 new resolved events back inside the tolerance.

**Challengers:**
- Each challenger logs in shadow from its registration and is compared on the same events (paired).
- The promotion rule is frozen at registration: at least 150 paired events, a week-clustered interval of the log-loss gain excluding 0, and calibration not worse.
- At most two run at once, each in the exposure ledger.
- A promoted challenger's shadow record counts as its live record.
- Retraining is a new version and enters as a challenger.

**C1 (cross-venue) is the first challenger.** It replaces the separate prospective confirmation of the #363 coefficient (portfolio P3-2): the question becomes whether the cross-venue move adds prospective skill to the forecast. #363's level specificity stays `NOT_ESTABLISHED`.

## 8. What this does not change

- **Research records:** no sealed record, verdict or frozen design is rewritten. #357, #361, #363, #365 and #368 keep their records and claim ceilings. Their numbers enter models only through refits declared in the design note.
- **#368 prospective protocol:** unchanged and not a gate. Its forward panel is bound (`research/LEVEL_VOLATILITY_TRANSITION_PROSPECTIVE_PANEL_BINDING_V1.md`). At the discovery pair rate (≈ 4.85 per week) it most likely closes at the 130-week checkpoint (2029-04-06).
- **Still forbidden:** an LLM in production, ETH, direct trade calls and the other V2 §3 items. This layer is BTC only.
- **Measurement contract:** before its freeze it registers the T0 line in the level push, the T15 surfaces and the two journal classes. It does not get a new push type.

## 9. Amendments

| Earlier text | Change |
|---|---|
| `PRE_BETA_SCOPE_DECISION_V1` §2.2, «Кто первый» post-beta | The race at structural levels moves into the pre-beta scope under §6. The two-user-price race in `/check` is allowed under the same gates as an architect's call (§6). |
| `PRE_BETA_SCOPE_DECISION_V1` §2.3 "new research programs to produce a feature" | One bounded exception: the program of this file (model development, held-out check, live calibration). No other research program is opened by it. |
| `PRE_BETA_SCOPE_DECISION_V1` §4 history first | Applies to this layer as written. The held-out check is §4 of this file. |
| `research/LEVEL_ENGINE_CONFIRMATION_PORTFOLIO_V1` P3-2 | Replaced by challenger C1 (§7). |
| `BETA_MEASUREMENT_CONTRACT_V1` (not frozen) | Registers the forecast surfaces and journal classes before its freeze (§8). |
