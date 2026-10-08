# Pre-beta scope decision V1 — everything decidable without users ships before Day 0

**Status:** `OWNER_DECISION_RECORDED / ACTIVE / NOT_IMPLEMENTED` (2026-10-05)
**Authority:** owner decisions of 2026-10-05, recorded verbatim in §1. This file sets the product scope between today and Day 0 of the 30-day user test. It extends the build-to-test scope of `PRODUCT_FIRST_DECISION_V1.md` §3 and amends that file only where §3 below says so. `PRODUCT_DECISION_V2_DECISION_SUPPORT.md` stays the canonical product decision; its §3 rules all stay. No sealed research verdict, frozen experiment or protected-data rule changes.

```
PRE_BETA_SCOPE            = plan A–J (§2) minus the post-beta list (§2.2)
ALL_CHANGES_BEFORE_DAY_0  = true
DAY_0                     = not declared; follows build, measurement re-freeze, deploy and soak (§9)
HISTORY_FIRST_RULE        = held-out history with a label now; live tracking joins automatically (§4)
CHECK_WORDING             = "B": «шанс ≈ X%» + held-out accuracy + live accuracy when mature (§5)
TWO_LEVEL_CHECK           = touch chance of each level + chance of neither; "which first" post-beta (§5)
                            (amended 2026-10-08: the race at structural levels is in scope — FORECAST_LAYER_DECISION_V1, §11)
RESEARCH_METHOD           = O1: EVIDENCE_AND_CLAIMS unchanged (§6.8)
MEASUREMENT_CONTRACT      = not frozen; amended and frozen on the final build commit (§6.7)
```

## 1. What the owner decided (verbatim, 2026-10-05)

- On the product direction: «Раз сроки не жмут … до инвайтов закрыть всё, что не требует мнения пользователей … Пользователям оставить то, что без них не решить: пороги, приоритеты расширений и цену.» — and on the plan A–J built from it: «я хочу его … сделаем до открытия беты».
- On timing: «до день 0 я хочу все изменения внести. и чек и прочее».
- On `/check`: «Хочу полную, ничего не переносить и не откладывать.»
- On missing live data: «Любые метрики которые нам нужны и которым не хватает лайв данных можно заменить на исторические с поправкой. А лайв данные потом подъедут сами.»
- On the four follow-up questions (2026-10-05):
  - «Для пары уровней показываем шанс касания каждого уровня + шанс «ни один». «Кто первый» не показываем и оставляем после beta.»
  - «Автоподсказку «Больше не присылать такие?» после 2/3 👎 убираем. Ручное отключение типа остаётся; само отключение учитываем как негативный behavioral signal в U2.»
  - «Делаем полноценные timezone + индивидуальное время briefing до Day 0. U1a меняем до freeze: окно `/catchup` считается относительно времени briefing конкретного пользователя, quiet hours — в его timezone. После Day 0 логика метрики заморожена.»
  - «O1. EVIDENCE_AND_CLAIMS не меняем. G01-A1 оформляем отдельной поправкой к audit #330, не переписывая сам audit. Следующий research-шаг — G01-A1/A2 как заранее определённая продуктовая baseline-оценка. DH3-P1 class добавить в claims journal в треке A.»
- On the conflicting items, the owner accepted the recommendation to keep them post-beta (§2.2), to show research evidence only in its tab (§6.1), and to build the owner-only signature index now, with the bot flagging and the owner choosing (§7).

Context: a trader-perspective review, two read-only audits of `main` (`c980fae`, 1003 tests; `c2b1316`, 800 tests), the read-only pre-beta backlog (`docs/PRE_BETA_BACKLOG_V1.md`, branch `claude/signalbot-prebeta-backlog-c1yqg0` until merged), the evaluator comparison note (`docs/research/EVALUATOR_VARIANTS_COMPARISON_V1.md`, branch `claude/signalbot-evaluator-comparison-jyvj1h` until merged) and the owner's review on 2026-10-05. Where the backlog's recommendations differ from this file, this file wins. Both audits found the existing beta contract nearly complete in code; this decision deliberately widens the scope before any external user.

## 2. Scope

### 2.1 Plan A–J (in scope before Day 0)

| Block | Content |
|---|---|
| **A Trust** | Data time on every screen and push; stale = «нет данных», never an old number; owner monitoring plus a ready user-facing outage text; measured alert latency (candle close → delivery) written into the push; a send load test within Telegram limits; one failed recipient never blocks the queue; a tested restore, including re-granting the feed role. |
| **B Accuracy** | Corridors: target vs realized plus width, 7 / 30 / 90 days (short windows hidden at small N), misses up and down with size, calm vs event / high-volatility days. Own calibration of `/check` («говорили X% → было Y%»). Touch-probability backtest for arbitrary levels before display. Weekly report. One "мало данных" N threshold below which a number becomes an honest phrase. |
| **C Screens** | `/btc`: price vs «обычно», corridors 1h / 4h / 24h with an accuracy line, the two nearest levels with touch chance, today's events, «необычное» or «ничего», buttons; research IDs only in Details; one disclaimer in `/terms`. Briefing about 8 lines. `/levels`, `/risk`, Details in one style and block order. One vocabulary, RU and EN equal. User time zone in every time. |
| **D `/check`** | Full version, §5. |
| **E Personal layer** | My levels (list, approach and touch alerts, delete); one-tap disable per alert type with undo; briefing time, time zone, quiet hours (exists), language; trader type as one onboarding question (scalp / intraday / swing / investing). |
| **F Push** | Template: fact → unusual or not → what usually follows → levels → delay → buttons. Deduplication (a level at most N times a day, cooldown per type, daily cap — exists). One-tap per-type mute under every push (E); no automatic «больше не присылать такие?» prompt. Owner review flag (≥ 30 votes from ≥ 8 people, noise > 50 %, or mass disables) — a human decides. Implicit metrics per push (action within 10 minutes, time to disable). «Полезно / Шум» on every alert type (§6.3). |
| **G Context** | Derivatives in numbers with «обычно» (funding value and its extremeness, OI change, long/short skew; context only, no conclusions). Research evidence per §6.1. |
| **H Feedback** | «💡 Идея / чего не хватает» free text; one reason after 👎 («неверно / не про меня / слишком часто / поздно»); one question at `/stop`; in-bot booking of a 15-minute interview; owner report (organic vs post-push returns, repeat `/check`, noise by type, split by trader type). |
| **I Monetization readiness** | free / paid access flags in code, everything open during the beta (§6.5). |
| **J Onboarding** | `/start` → trader type → live `/btc` → sample push → offer `/check` of an own level, first value within 60 seconds; «как читать бота»; terms, privacy, `/delete_me` (exists), «не инвестиционная рекомендация» in `/terms`; a support contact with a one-day answer. |

Text clean-up found by the audits is part of C: research IDs off the main screens, L2 lines in percentage points with uncertainty instead of the word «как обычно», the R03-C1 text (significant, below the materiality bar — not "below significance"), the duplicated CPI caveat, `/levels` length.

### 2.2 Post-beta (excluded from this scope)

| Item | Why |
|---|---|
| ETH as a second asset (G) | `PRODUCT_DECISION_V2` §3 multi-asset ban; it would also contaminate U5, which measures demand for other coins. |
| Historical CPI/FOMC move sizes (G) | Event zones in V2 show no calibrated sizes; D11 stays in `/research`. |
| Fake doors with a price and a tariff page with prices (H, I) | Distort U3, which is a real transfer offered on days 21–25. |
| «Кто первый» for two levels (D) — **amended 2026-10-08 (§11): moved into scope at structural levels; two user prices allowed under the same gates as an architect's call** | A directional first-passage line: DH1/DH2 earned no probability line for the bot (AGENTS.md), and on BTC history the upward drift would make the line read as a call. The amendment answers this with the driftless geometric «обычно», calibration gates and a fallback (`FORECAST_LAYER_DECISION_V1.md` §6–§7). |
| The automatic «больше не присылать такие?» prompt after 2 of 3 👎 (F) | Unhappy users would stop receiving pushes and inflate the U2 Useful share. |

### 2.3 Never (unchanged)

Alert-sensitivity settings, an LLM chat, a web UI, signals / entries / exchange keys, new research programs to produce a feature, a multi-coin scanner, and every item of `PRODUCT_DECISION_V2` §3 "Still not built".

## 3. Amendments to earlier decisions

| Earlier text | Change |
|---|---|
| `PRODUCT_FIRST_DECISION_V1` §3 build-to-test MUST scope | Extended by §2.1 of this file. |
| `PRODUCT_FIRST_DECISION_V1` §5 "per-type mute, complex personalisation" | Per-type mute is allowed (E, F). Other complex personalisation stays out. |
| `PRODUCT_FIRST_DECISION_V1` §9 row "per-user brief time" | Allowed: per-user briefing time and time zone (C, E). |
| `PRODUCT_FIRST_DECISION_V1` §5 "a claim ledger as a product feature" | Clarified, not changed: the claim journal of `BETA_CLAIM_JOURNAL_DESIGN_V1.md` is internal tracking, like `beta_forecasts`. Users see aggregated accuracy only. |
| `PRODUCT_FIRST_DECISION_V1` §5 "payment infrastructure beyond a manual link" | Clarified, not changed: access flags with everything open are not payment infrastructure. No payment processing. |
| `EVIDENCE_AND_CLAIMS_DECISION_V1` §6, touch chances («owner choice; not changed here») | The owner chooses wording "B" under the conditions of §5. |
| `BETA_MEASUREMENT_CONTRACT_V1` (FREEZE_READY, §0 hash empty) | Not frozen now. Amended for this scope (§6.7) and frozen on the final build commit. |

## 4. History first, live joins (the owner's rule)

A market metric that needs live data it does not yet have is shown from a held-out historical check, labelled «на истории». Live tracking runs from the first day and its line appears automatically when it reaches its threshold. Three conditions make the historical number honest:

1. it was checked on data the model did not see when it was fitted (the held-out year of `beta/rangecast.py`, or an equivalent held-out period declared before the check);
2. it is labelled as historical;
3. the live journal records the same quantity from day one, and the switch to the live line is a rule frozen before Day 0, not a manual change during the test.

The "correction" is the label and the held-out check, never an adjustment of the number toward a nicer value. This is the honesty rule of `PRODUCT_DECISION_V2` §3 ("backtest on a held-out year, and live tracking once the forecasts mature") applied to every forecast-like number.

**Does not apply to:**
- user behaviour (U1–U5): there are no historical users; this is what the beta measures;
- the live pipeline (latency, delivery, Telegram limits, failure handling): measured by load tests, replay and the soak;
- data that has no history (three-venue taker flow, liquidations, order book, 15-second OI): the history surface is Binance price, OI and volume only. Mixing Binance-only history into live three-venue ranks is a silent source fallback and is not allowed. The unusual-hour gate under C1 therefore matures on its own (about end of October).

## 5. `/check` — full version

- **Touch chance** of any user price within 1h / 4h / 24h, with «обычно», events in the window and the next levels beyond.
- **What followed touches of similar levels**, with N and «обычно», no directional call.
- **Two levels**: `/check 64000 69000` → the touch chance of each level within each horizon and the chance that neither is touched (from the joint historical excursions up and down, never by multiplying the two chances), with the same wording and accuracy as single-level chances. «Кто первый» is not shown (post-beta, §2.2).
- **«Следить за уровнем»** turns a check into a personal alert; input accepts «64000», «64к», «64 000», «-3 %»; reachable in one tap from every push and the briefing with the level filled in.
- **Wording "B"**: «шанс ≈ X%» next to the held-out accuracy of such estimates («на истории: говорили 20% → было 19%, N=…») and, once mature, the live accuracy from the claim journal.

Before implementation a design note records, by design and before any outcome is read:
- the calibration bins and the tolerance the held-out check must meet; below it the wording falls back to «исторически в X% случаев»;
- the N threshold (in effective, non-overlapping claims per horizon) at which the live line appears;
- the reaction when live and held-out accuracy diverge, as a rule frozen before Day 0.

The touch model already works on distance (`beta/rangecast.py`, held-out last 365 days, `touch_reliability` at 50 / 20 / 10 %); the work is more bins, arbitrary-level checks and display, not a new model. Live calibration of 24h claims needs months of data; that is why the live line is rule-based.

## 6. Other decisions

1. **Research evidence:** off on the main surfaces, on in the «🔬 Исследования» tab. Needs a split presentation switch; collection and matching unchanged.
2. **Order of work:** the claim journal first (its clock starts when it ships; it includes a claim class for DH3-P1, which the design lacks), then the calibration bins, then `/check`, then the rest of A–J.
3. **«Полезно / Шум» on every alert type**, so U2 can accumulate votes.
4. **Weekly report** is a new push type; it is counted in the measurement contract (it affects U1b).
5. **Access flags** free / paid in code, everything open; no payment processing, no price page.
6. **Owner review flag** during the test is observe-only: disabling a type mid-test changes the push rule, which `PRODUCT_FIRST_DECISION_V1` §7 forbids. There is no automatic «больше не присылать такие?» prompt; the manual one-tap per-type mute stays and counts as a negative behavioural signal in U2.
7. **Measurement contract** amendments before freeze:
   - U1a: the `/catchup` reaction window is measured from each user's own briefing time; quiet hours run in the user's time zone;
   - U2: votes on every alert type; a per-type mute counts as a negative behavioural signal; what counts as a push for the < 15 threshold;
   - the weekly report in U1b; classes for the new actions (`/check`, watch, idea, the automatic `/btc` of onboarding, which must not count as `cmd_btc`);
   - frozen with the final commit hash in §0; after Day 0 the metric logic does not change.
8. **Research line** runs in parallel and never blocks the beta. Re-evaluation method: **O1** — `EVIDENCE_AND_CLAIMS_DECISION_V1` stays unchanged; a per-unit Bayesian or partial-pooling method remains a design-note choice inside it. The G01-A1 assessment in `research/RESEARCH_HISTORY_AUDIT_V1.md` (`YES` → closer to `PARTLY`; its 0.486 MDE was computed at alpha 0.05, not at the Holm step) is recorded as a separate amendment; the audit itself is not rewritten. The next research step is G01-A1/A2 (turn of month) as a product baseline estimate defined before any outcome, with its design note first and its run on a separate owner go.

## 7. Owner-only signature index (`/hypotheses`)

Built now, in parallel with the product work. Research-supporting tooling, not a product feature; no user surface.

- **Signature** of a 5m bucket = a tuple of states the code already computes (interpretation bands and labels 1h / 4h, hour gate, D7 state, liquidation votes, evidence matches, C1 day type). No new threshold, no new detector (`PRODUCT_DECISION_V2` §3).
- **Episodes:** identical consecutive signatures are one episode. Append-only.
- **Flag NEW** when a signature has ≥ 2 tail (non-neutral) states, ≥ 3 separate episodes and ≥ 2 distinct UTC days. Its empirical frequency is shown beside it. No surprise ratio against independence: the labels are dependent, so the ratio inflates on known structure.
- **Blind review:** the owner decides «в research / отклонить» before seeing what followed; the hypothesis text and the generating window are frozen at that moment and written to the exposure ledger. Historical counts are read only after «в research». A historical check is discovery; replication is live, forward.
- `/pin` marks the current state by hand.

## 8. Unchanged

- `PRODUCT_DECISION_V2` §3 in full: no direct trade calls, N and «обычно» beside every historical number, tracked accuracy beside every forecast, no hype, historical stats never steer the push decision, and the "still not built" list.
- `PRODUCT_FIRST_DECISION_V1` §4 architecture (one detector, one episodization, one context projection, one shared view builder, one outbox, one notifier) and §7 test rules: after Day 0 only clarity, timing, translation and bug fixes; frozen from day 8.
- Every sealed research verdict, `E1-RUN-001`, V3, D2, D7, the atlas, the protected-data rules and the research findings registry procedure.
- «Пороги оставляем пользователям» means: thresholds stay fixed during the 30-day test; interviews inform changes only after day 30 (`PRODUCT_FIRST_DECISION_V1` §7).

## 9. Path to Day 0

1. Build §2.1 and §7 in the order of §6.2.
2. Amend `BETA_MEASUREMENT_CONTRACT_V1` (§6.7) and freeze it on the final build commit.
3. Deploy that commit as the invite candidate; smoke; owner soak with live alerts, two briefings, a restart and a night history build; telemetry checked on production (`BETA_INVITE_CANDIDATE_CHECKLIST.md`).
4. Day 0 is the first unknown-to-founder user (`PRODUCT_FIRST_DECISION_V1` §7).

**Owner actions before Day 0 (not code):** restore CI (GitHub billing); check `BETA_RESEARCH_EVIDENCE_ENABLED` in the production `.env` and record it; run the gate coverage dry-run (`--beta-context-dry-run`) on the production tape and record it; fix the U3 price in a commit before Day 0; the U3 price and manual payment method; a second acquisition channel for U4; approve the 5-question interview script; review the interpretation labels (`PROVISIONAL_PENDING_DRY_RUN`); 2–3 traders who have not seen the product for the onboarding check; update or close PR #307.

## 10. State when this was decided

- `main` = `c2b1316`. Production = `c980fae`: C1 deployed by the owner on 2026-10-05 12:44 UTC, smoke 27 PASS / 0 WARN / 0 FAIL, context `BETA_CONTEXT_1H_V3`, analogues `BETA_ANALOGUES_V2` (owner-reported). `c980fae..c2b1316` touches research documents only, so production equals `main` for the product; #319, #322, #326, #327 and #329 are in production. Records that still name `a16b876` as production are stale.
- The compiler V3 variance line is closed (`research/COMPILER_V3_VARIANCE_LINE_CLOSURE_V1.md`); `research/hypothesis-evaluation-contract-v2-draft` is merged through #328.

## 11. Amendment of 2026-10-08 — the forecast layer (owner decision)

Owner: «Показывать хочу сразу в бете и это надо изменить в документах. Решение владельца.» Recorded in full in `FORECAST_LAYER_DECISION_V1.md`.

- **§2.2 «Кто первый».** The race of the two barriers of a structural first touch (BREAK first / REJECT first / neither within 4h) is in the pre-beta scope and shown from Day 0 under `FORECAST_LAYER_DECISION_V1.md` §6. The race of two user prices in `/check` uses the same engine and gates; it is built before Day 0 only if it costs Day 0 nothing (architect's call), otherwise it stays post-beta. The two-level touch chances and «ни один» of §5 are unchanged.
- **§2.3 "new research programs to produce a feature".** One bounded exception: the forecast program of that file (model development on 2020–2024, a one-shot held-out check on 2025-01-01 → freeze without the E1 holdout, live calibration). It opens no other program.
- **§4 history first** applies to the layer as written.
- **§6.7 measurement contract.** Before its freeze it registers the T0 line in the level push, the T15 surfaces and the journal classes `L3_LEVEL_RACE_T0_4H` / `L3_LEVEL_RACE_T15_4H`. No new push type.
- **§9 path to Day 0.** Owner, the same day: «Б вариант, сразу по истории». Day 0 does not wait for the model. The layer ships in `HIST`: a history line on 2020–2024 with N and the geometric «обычно», logged in the claim journal from Day 0. The model states follow later (`FORECAST_LAYER_DECISION_V1.md` §6a).
- **Chain of command:** `ORCHESTRATION_V1.md`.
