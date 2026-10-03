# Product decision V2 — decision support (levels, ranges, history, events)

**Status:** `OWNER_DECISION_RECORDED / CANONICAL_PRODUCT_DECISION / IMPLEMENTED_IN_CODE (not deployed, not user-tested)`
**Date:** 2026-10-03
**Operating mode from this decision:** `PRODUCT_FIRST / DECISION_SUPPORT / NO_DIRECT_TRADE_CALLS`
**Authority:** owner decision of 2026-10-03, recorded verbatim in §1. This file is the canonical product decision. Where `PRODUCT_FIRST_DECISION_V1.md`, `BETA_COPY_CONTRACT_V1.md`, `BETA_HISTORICAL_ANALOGUE_GATE_V1.md` or any older beta document disagrees with it, this file wins. It changes no sealed research verdict and no frozen experiment (`E1-RUN-001`, V3, D2, D7, C013 and the rest stay exactly as they are).

```
PRODUCT_FIRST                     = true (unchanged)
PREDICTIVE_PRODUCT_FROZEN         = false (lifted by the owner, 2026-10-03)
DIRECT_TRADE_CALLS                = forbidden (long/short now, buy/sell, entries, targets)
HONESTY_RULE                      = every historical number carries N and a comparable "обычно";
                                    every forecast carries its own tracked accuracy
PROTECTED_2025_2026_FOR_PRODUCT   = opened (owner, 2026-10-03)
PROTECTED_2025_2026_FOR_RESEARCH  = consumed for any claim over the product features (§4)
USER_TEST                         = PRODUCT_FIRST_DECISION_V1 §7, run on the V2 surface
```

## 1. What the owner decided (verbatim, 2026-10-03)

> «Я сейчас абсолютно так же не вижу ценности, поэтому как владелец считаю, что пока что надо делать всё, что возможно. Поэтому все запреты на прогнозы и т.д. я снимаю. Да, прямого лонг/шорт не должно быть, но мы должны хотя бы исторически давать понимание.»

On the proposal (levels, range corridor, `/risk`, «что было после похожих», event calendar, timely pushes): «мне уже нравится очень то, что ты предлагаешь». On the protected data: «Открыть для продукта». On scope: «доведи то, что мы обговорили, максимально end to end … и решение само собой да».

Context that led here: the owner, reading the V1 build-to-test surface as a trader, found no answer to "what do I do with this information" and saw no historical price movement. A trader-perspective review agreed: the V1 surface was a compressed dashboard with interpretation, late pushes, no levels, no calendar and no risk translation.

## 2. What the product now does

The product answers three questions for an intraday BTC-perpetual trader, in Russian, without telling them which side to take:

1. **How far can price go and how risky is it now?** A range model forecasts the 1h / 4h / 24h corridor and touch probabilities. It is fitted on Binance USD-M BTCUSDT 5m history from 2020 and checked on a held-out last year. `/risk` translates a stop distance into how often such a move happened against a position.
2. **Where are the levels everyone watches, and what happened there before?** Objective levels only: previous day/week/month high and low, day/week/month open, session highs/lows, day VWAP, the previous day's volume point of control, round numbers and recent liquidation clusters. Nearby levels merge into zones. Each zone shows its distance and the chance to reach it. Each level type shows what happened after the first touch, beside a random level at the same distance.
3. **What happened after similar situations, and what is scheduled today?** For each 1h / 4h state label: N, how often price was higher after 1h / 4h / 24h, median move and the typical move up and down, always beside "обычно" in the same volatility. A verdict is computed: «как обычно» or «отличается». A calendar shows CPI, FOMC, Deribit expiry and funding times, with the historical size of such days (the size is not shown since 2026-10-03: see «Event zones» below).

4. **What did our own research find?** `config/beta_research_findings.yaml` turns the closed research units into short trader-language lines (§2.4). A line appears where its result applies, prefixed «Проверено:»: for example, H01 beside a «сжатие» label (a lull did not announce a breakout), R03-C1 on a weekend, H03 under a sharp-move alert, D2 in `/risk`. Since 2026-10-03 no line rides on a CPI/FOMC event surface (event zones, below); D11 stays in `/research`. `/research` lists all of them by status: replicated, found once, below the bar, beliefs that did not hold, side findings of hypotheses that missed their own target, and units with too few cases for a verdict.

**Pushes** become timely: the first touch of a key level (previous day/week/month high or low) with its history, a reminder before CPI / FOMC, a sharp 15-minute move, and the user's own price alerts. The late unusual-hour push stays available and can be switched off per user.

**Event zones (2026-10-03, `BETA_EVENT_CORRIDOR_TEMPORAL_REPAIR_DESIGN_V1.md` §9).** The corridor's CPI/FOMC conditioning is not calibrated at the live cadence. So for horizon H, while now ∈ [release − H, release + 60 min) the product shows no numerical corridor for H, no touch chance, `/risk` figure or alert corridor line derived from it, and no «4 из 5». It names the release and its time and says the usual corridor calibration does not apply around a release. No event-size multiplier is shown on any surface: `/events` is a plain calendar (name and exact time), and the briefing's «Сегодня» lists the same. The sharp-move alert is judged without the CPI/FOMC term (`SHARP_MOVE_EVENT_CONDITIONING = DISABLED_PENDING_VALIDATION`). Inside a release's 1h zone it shows the move, its size and the warning, with no «раз в N дней» frequency and no research line. Outside every zone the generic corridor is unchanged.

### 2.4 Research ↔ bot

- **Source.** One registry entry per closed unit: id, status, RU/EN text (at most 220 characters, guard-checked), the data it was measured on, the record path, the bot contexts and a priority. `beta/research_link.py` validates it (unique ids, length, wording, record present unless `pending_merge`).
- **Rules.** A text states only what its record states. A discovery-only result says so; a result below its frozen materiality bar says so; an underpowered unit is listed in `/research` but never shown as «Проверено». Research verdicts are unchanged by being shown.
- **Upkeep.** When a research unit closes, its entry is added or updated in the same change (AGENTS.md). Entries from `OWNER_CARDS_R03` carry `pending_merge: true` until that branch merges.

## 3. Rules that stay

- **No direct trade calls.** Never «покупай/продавай», «лонг/шорт сейчас», «входи», «точка входа», «цель/таргет», «тейк-профит», «гарантированно», «рекомендуем». The guard in `beta/i18n.py` enforces this on every rendered text.
- **Honesty rule.** A historical number is never shown without its N and the comparable "обычно" from the same history. A forecast is shown with the share of past forecasts that held (backtest on a held-out year, and live tracking once the forecasts mature). A verdict «отличается» needs a day-clustered bootstrap test with a Holm correction across its family plus a materiality floor. Otherwise the card says «как обычно». Too little data says «мало данных».
- **No hype.** No «срочно», «памп», «дамп», «ракета», «обвал», no exclamation marks, no capital-letter shouting.
- **Historical stats never steer the push decision** of the detector pipeline. A level push is driven by the level touch itself; its history is shown beside it.
- **Data honesty.** Levels, corridors and history are computed on Binance (one venue, declared «Binance» in the text). The live 1h / 4h labels stay multi-venue. Liquidation history does not exist before the live collector, so liquidation-based labels have no historical card. When the live tail is stale, the corridor and levels are not shown.
- **Still not built** (`PRODUCT_FIRST_DECISION_V1.md` §5, unchanged): an LLM in production, a web UI, payment infrastructure, a multi-asset scanner, order book and liquidation heatmaps, read-only exchange keys, a second detector engine.

## 4. Protected 2025/2026 data

The owner opened Binance USD-M BTCUSDT 2025/2026 history for product use. Consequences, recorded in `RESEARCH_LEDGER.md`:

- the product statistics (range model, level reactions, state analogues, event-day sizes) are computed on 2020 → yesterday, 2025/2026 included, **except the E1-RUN-001 final holdout `[2026-08-16T00:00Z, 2026-08-25T17:20Z)`**: `beta/history_data.py` never requests an archive object whose period overlaps it: the August 2026 monthly klines and the daily klines and metrics of 2026-08-16 … 2026-08-25 are rejected before any request, the 25th whole although its tail after 17:20 is outside; August is read from its other days. A request gate checks every URL again before the network call, and rows inside the window are dropped after parsing as a last line (AGENTS.md: that holdout is opened only by E1's frozen evaluator);
- the divergence program had already opened a six-symbol Binance surface for 2025-01-01 → 2026-08-15 (`docs/research/DIVERGENCE_PROGRAM_OWNER_DECISIONS_V3.md`); this decision adds the product's use of BTCUSDT after that date, outside the E1 holdout;
- for research, 2025/2026 Binance BTCUSDT is no longer an untouched out-of-sample window for any hypothesis whose features overlap the product features (range/volatility, levels, price/OI/taker states, event days). A future research claim over those features needs a different untouched window or a prospective test;
- sealed research verdicts are not reopened, rerun or reinterpreted.

## 5. What this supersedes

| Superseded | Where | Replaced by |
|---|---|---|
| `PREDICTIVE_CLAIMS_FROZEN`, "labels never say what follows", "never what comes next" | `PRODUCT_FIRST_DECISION_V1.md` §1, §3.1; `BETA_COPY_CONTRACT_V1.md` §3.14, §4, §5 rule 3 | §2, §3 of this file |
| Historical analogue cards on DO-NOT-BUILD-YET; the heavy promotion procedure (spec digest, 1000-replicate null calibration before any card) | `PRODUCT_FIRST_DECISION_V1.md` §5; `BETA_HISTORICAL_ANALOGUE_GATE_V1.md` | §3 honesty rule (N, "обычно", day-clustered bootstrap with Holm, materiality floor) |
| Calendar not in MUST; "no new backfill only to launch earlier" | `PRODUCT_FIRST_DECISION_V1.md` §6, §9 | §2; the history sync and the V2 tape rewind (`PRIVATE_BETA_V0_DEPLOY.md`, "Decision support V2") |
| The forbidden-word lists against forecasting vocabulary (вероятность, прогноз, ожидается, разворот, продолжение, стоп) | `beta/i18n.py`, `BETA_COPY_CONTRACT_V1.md` §4 | the trade-call and hype guard of §3 |
| `/catchup` and briefing 15-line limit | `BETA_COPY_CONTRACT_V1.md` §5 rule 8 | the briefing and `/catchup` add the corridor, the level ladder and today's events (about 22 lines); pushes stay at most 8 lines |
| Push cap of 2 a day as the only push budget | `PRODUCT_FIRST_DECISION_V1.md` §3 row 8 | the unusual-hour cap is unchanged; market alerts (levels, sharp moves) have their own daily cap; event reminders and personal price alerts are user-controlled |
| `AGENTS.md` beta line "never predictive wording" | `AGENTS.md` | this file |

Unchanged: one detector, one episodization, one context projection, one outbox, one notifier. The new market alerts and the briefing are delivered by the existing notifier through the existing outbox (`kind = 'alert'`).

## 6. User test

The 30-day test of `PRODUCT_FIRST_DECISION_V1.md` §7 (U1a, U1b, U2, U3, U4, U5 and the Continue / Reposition / Pivot / Stop rules) runs on this V2 surface. Its thresholds are fixed before the first invitation as written there. The new commands are counted as pull (`cmd_levels`, `cmd_risk`, `cmd_alert`, `cmd_events`, `cmd_accuracy`, `cmd_research`); `alert_delivered` counts as a push.

## 7. Implementation map

| Piece | Code |
|---|---|
| Binance Vision history (5m klines 2020→, OI metrics 2020-09→), ledger, upsert | `beta/history_data.py`, `--beta-history-sync` |
| Range model, corridors, touch probabilities, `/risk` | `beta/rangecast.py` |
| Objective levels, zones, level reaction statistics | `beta/levels.py` |
| State analogues («что было после похожих») | `beta/analogues.py` |
| Event calendar and event-day statistics | `beta/calendar_events.py`, `config/beta_calendar.yaml`, `scripts/beta/build_calendar.py` |
| Nightly statistics build | `beta/history_stats.py`, `--beta-history-build`, `deploy/signalbot-beta-history.{service,timer}` |
| Live decision block for every surface | `beta/decision.py` |
| Market alerts (levels, events, sharp moves, user alerts), forecast tracking | `beta/market_alerts.py` (inside `--beta-notify-once`) |
| Texts | `beta/decision_format.py`, `beta/i18n.py` |
| Research findings in the bot («Проверено», `/research`) | `beta/research_link.py`, `config/beta_research_findings.yaml` |
| V2 tape rewind (removes «мало истории» where raw data exist) | `--beta-bootstrap-rewind` |
| VPS upgrade helper | `deploy/beta_v2_upgrade.sh` |

Deploy and verification steps: `PRIVATE_BETA_V0_DEPLOY.md`, section "Decision support V2".
