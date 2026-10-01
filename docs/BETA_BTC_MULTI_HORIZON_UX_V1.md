# Beta V0.2 — `/btc` multi-horizon UX V1 (Event · 1h · 24h, RU/EN)

**Status:** `PR1_IMPLEMENTED / PR2_IMPLEMENTED / PR3_CODE_DONE_INACTIVE`. Steps 2, 3, and 4 below are done in code. The D7 line stays off until the owner sets `regime_d7.enabled` after deploy. `BETA_BTC_MAIN_SCREEN_UX_V1.md` describes what PR 2 renders.
**Date:** 2026-10-01
**Scope:** presentation, read-only context projections, and a per-user language setting for the descriptive private beta (`docs/PRIVATE_BETA_V0_RESTART_DECISION.md`).

**Authority:**
- This document is the implementation authority for the multi-horizon `/btc` pass.
- PR 1 updated `BETA_BTC_MAIN_SCREEN_UX_V1.md` to the screen it renders. `BETA_BTC_TEMPORAL_CONTEXT_V0.md` is unchanged until PR 2, which still amends its deferred items for 1h/24h OI and the time-of-day note. PR 1 stores the 1h baseline only on the view payload (`horizons`), not in that context version.
- The D7 regime layer is governed by `BETA_D7_REGIME_CONTEXT_GATE_V1.md`.
- Decisions are listed in §11. Owner choices and choices the owner delegated are marked there.

## 0. Why

**Trader feedback (scalper interview, 2026-09-30):**
- 5m change is noise for the overall picture.
- Hourly context is too thin.
- OI by venue is wanted ("where it is pushed, where it is dumped").
- `91.5 pct of 30d` means nothing.

The scalper segment is a poor fit, because it trades from the order book. **The target user is a BTC intraday trader holding from about 30 minutes to several hours**, and the first users are Russian-speaking.

**Code fact.** Event Details (`beta/formatter.py`, `format_context_details`) prints the anchor 5m bucket and the latest 5m bucket as two full MARKET / OI / FLOW blocks (about 24 lines), and the rolling 1h in five lines.

**Out of scope:** order book and liquidity walls, multi-coin screeners, forecasts, and trade suggestions.

## 1. Boundaries (unchanged by this pass)

- **Detection is untouched:** the detector, `BETA_EVENT_RULES_V1`, the rules digest, episodization `STRICT_QUALIFICATION_V1`, readiness semantics, forward outcomes, and push (disabled).
- **State tape schema V2 is unchanged.** Inputs that are not on the tape are read as of the view time from Stage-1 storage, or for D7 from its own beta table. They are never written into the tape: a tape schema change would change the rules digest and end every open episode with `DETECTOR_VERSION_CHANGED`.
- **Wording rules** of `BETA_BTC_MAIN_SCREEN_UX_V1.md` §5 stay, in both languages. The one exception is the D7 sentences fixed by its gate document.
- **Code paths:** `beta/`, `runtime/beta_*`, `storage/beta_v0_*`, `config/beta_v0.yaml`, `deploy/signalbot-beta-*`. No LLM anywhere.

## 2. Information model

Three layers, kept separate in the view model, in code, and on screen:

| Layer | Object | Clock | Source |
|---|---|---|---|
| EVENT | detector episode and its anchor bucket | 5m | existing view (`active_episode`, `last_event`, anchor) |
| HORIZONS | rolling 1h and rolling 24h | evaluated at each 5m view | tape V2, plus Stage-1 `open_interest` as-of reads (§6) |
| REGIME | D7 high-impact hour | clock hour | `BETA_D7_REGIME_CONTEXT_GATE_V1.md` |

The rolling 1h (the last 60 minutes) and the D7 clock hour are different objects. They are never merged, and the D7 hour is always printed with its clock bounds.

## 3. Language and time

### 3.1 Language

- **Per-user setting `ru` / `en`, default `ru`.**
  - Stored as `beta_users.lang`: `TEXT NOT NULL DEFAULT 'ru'`, `CHECK (lang IN ('ru','en'))`, added by an additive migration in `storage/beta_v0_schema.sql`.
  - `/start` shows a one-time `[Русский] [English]` choice.
  - `/lang` shows it again at any time.
  - Every reply, including `/help`, `/history`, errors, and the privacy text, uses the user's language.
- **One string catalog**, `beta/i18n.py`. Every user-facing string, plain event name, presentation title, and wording sentence has a key with both translations. The formatter takes `lang` and never builds user text outside the catalog.
- **The persisted view model is language-neutral.** Each rendered `/btc` row in `beta_btc_views` stores `lang` together with the rendered text and its SHA-256.
- **`assert_descriptive` gets a Russian forbidden list**, checked for `ru` text alongside the English list. Minimum list, case-insensitive with word boundaries:
  - trade instructions: `купи(ть|те)`, `покупай(те)`, `прода(й|йте|вай|вайте|ть)`, `входи(ть|те)`, `точка входа`, `стоп-лосс`, `тейк-профит`, `цел(ь|и)`, `плеч(о|а)`;
  - forecasts: `вероятн…`, `скорее всего`, `прогноз…`, `предсказ…`, `ожида(ется|ем|ют)`;
  - other: `сигнал…`, `рекоменд…`, `прибыл…`, `убыт…`, `лонг сейчас`, `шорт сейчас`.

  The Russian disclaimer must pass this list. Example: `Экспериментальная закрытая бета. Только описание состояния рынка — не инвестиционный совет и не указание к сделке.`
- **Number format:**
  - `ru`: thin-space thousands (`112 450`), decimal comma (`−0,84%`), money as `$84 млн`, `$1,9 млрд`;
  - `en`: `112,450`, `−0.84%`, `$84M`, `$1.9B`.
- **Technical terms stay English in the Russian UI** (owner rule). The glossary command `/terms` and the `[Термины]` / `[Glossary]` button under `/help` print the verbatim texts in the PR 2 task. Summary:

  | Concept | Russian UI |
  |---|---|
  | OI | OI |
  | funding | Funding |
  | taker flow | Delta (покупатели / продавцы) |
  | range | диапазон |
  | volume | объём |
  | long / short liquidations | ликвидации лонгов / шортов |
  | sharp rise / drop | резкий рост / резкое падение |
  | OI build-up in a narrow range | набор OI в узком диапазоне |
  | aggressive buying / selling | агрессивные покупки / продажи |
  | "× usual" | × от обычного |

  Russian titles:

  | English title | Russian title |
  |---|---|
  | calm | спокойно |
  | unusual now | необычно сейчас |
  | calmed | затихло |
  | event ended | событие завершено |
  | history building | бот собирает историю |
  | data incomplete | данные неполные |

  Russian fail-closed sentence: `Текущих данных недостаточно: отсутствие событий сейчас подтвердить нельзя.`

### 3.2 Time

- **All displayed times are Kyiv time** (`Europe/Kyiv`, IANA zone with daylight saving), labelled `(Киев)` / `Kyiv`, for every user and both languages.
- Storage, windows, baselines, and the D7 clock hours stay in UTC. Only rendering converts.
- Kyiv's offset is a whole number of hours, so UTC clock hours render as Kyiv clock hours.
- The daylight-saving transitions must be covered by tests.

## 4. Main screen

Russian (default):

```
BTC 112 450 · необычно сейчас
Цена ↓ · OI ↓ · Объём высокий
OI снизился во время падения
1ч: −0,8% · объём 2,1× · диапазон 1,8× · OI −0,6%
24ч: −1,9% · объём 1,3× · ОИ +2,1%
High impact в прошлый час
Ещё активно · данные 15:10 (Киев)
[Событие] [1ч] [24ч]
```

English:

```
BTC 112,450 · unusual now
Price ↓ · OI ↓ · Volume high
Open interest fell during the drop
1h: −0.8% · vol 2.1× · range 1.8× · OI −0.6%
24h: −1.9% · vol 1.3× · OI +2.1%
High impact last hour
Still active · data 15:10 Kyiv
[Event] [1h] [24h]
```

**Rules:**
- **Title:** `BTC <price> · <state>`. The price is the view's `now.reference_price`, rounded to whole USD and omitted when null. The six presentation states are unchanged.
- **Event lines** are unchanged in meaning from `BETA_BTC_MAIN_SCREEN_UX_V1.md` §3:
  - one arrow for direction only;
  - the frozen volume level word;
  - the factual OI sentence;
  - no short-covering or long-unwind narrative (owner, 2026-10-01).
- **`1h` line:** price change %, volume ×, range ×, OI %. It replaces `1h activity: …` and is shown on every non-fail-closed screen, calm included.
- **`24h` line:** price change %, volume ×, OI %.
- **High-impact line:** only under the D7 gate conditions. Otherwise it is absent and nothing replaces it.
- **Status and data-through** share one line.
- **Partial values:**
  - an incomplete window prints `1ч: неполные данные` / `1h: incomplete`;
  - an immature baseline prints `н/д` / `n/a` in place of the ratio;
  - a field that cannot be computed is dropped from the line, never shown as 0.
- **Fail-closed (`DATA STALE` / `DATA DEGRADED`):**
  - no 1h, 24h, or high-impact line;
  - the last-known event block of `BETA_BTC_MAIN_SCREEN_UX_V1.md` §3 is unchanged;
  - no tab buttons except `[Событие]` / `[Event]` when a last-known episode exists. It renders as last-known.
- **Line budget:** at most 8 lines plus the one-line disclaimer.
- **Buttons:**
  - `[Событие]` appears only when an episode is open or retained;
  - `[1ч]` and `[24ч]` always appear outside fail-closed;
  - `[Готовность]` / `[Readiness]` keeps its current rule.

## 5. Details: three tabs

**Mechanism:**
- A tab button sends one Details message showing that tab, with the tab row at its bottom.
- A tab press inside that message **edits the same message in place**.
- Each tab renders from the **persisted view snapshot** of the `/btc` message it belongs to, so it shares that message's data-through. Callback data carries the view id. Tabs never recompute from live state.

**Common rules for every tab:**
- Body lines are facts with units.
- Each ratio names its baseline (`от обычного для этого часа` / `usual for this hour`, `от медианы 30 дн.` / `30d median`).
- No percentile ranks, no `EARLY` / `ARMED` / `TRIGGERED`, and no version strings in the body.
- The last line is `Термины: /terms` / `Terms: /terms`. The support ref line is not shown. Episode and view ids stay in the persisted payload.
- Ranks, levels, and versions stay in the persisted payload.

**Usage record:** each tab open writes one row `(view_id, tab, lang, opened_at)` to an additive table `beta_details_opens`. There is no user id, the same privacy posture as `beta_btc_views`. This measures which horizon traders actually use.

### 5.1 Event tab (anchor bucket only)

```
СОБЫТИЕ · резкое падение
Ещё активно · с 14:55 (Киев)
Почему замечено (15:05–15:10):
  Цена −0,50% · диапазон 0,62% · объём $310 млн (высокий)
  OI −0,42%: Binance −0,61% · Bybit −0,35% · OKX −0,12%
  Delta: −$41 млн (продавцы)
  Ликвидации лонгов: Binance ≥$2,1 млн · Bybit $3,4 млн · OKX $0,6 млн
Также открыто: агрессивные продажи
≥ — нижняя граница: Binance передаёт не все ликвидации.
Термины: /terms
```

- Only the anchor bucket is shown. The second "Now" 5m block is removed from user-facing Details.
- **Per-venue OI percents** come from the anchor snapshot's `venue_raw.oi_change_pct`, which is already on the tape. The view model must persist these numbers; today it stores only up/down/flat.
- **Liquidations** follow §7.
- Volume uses the frozen level word, not a ratio. No new 5m baseline is introduced.

### 5.2 1h tab

```
ПОСЛЕДНИЙ ЧАС · 14:10–15:10 (Киев)
Цена −0,84% · диапазон 1,12% (2,3× от обычного для этого часа)
Объём $1,9 млрд (2,1× от обычного для этого часа)
OI −0,6%: Binance −0,9% · Bybit −0,4% · OKX +0,1%
Delta: −$84 млн (продавцы)
Ликвидации лонгов: Binance ≥$8 млн · Bybit $10 млн · OKX $3 млн
Ликвидации шортов: Binance ≥$1 млн · Bybit $2 млн · OKX $0,4 млн
Funding сейчас 0,006% (медиана бирж)
High impact 14:00–15:00 (Киев): цена прошла много относительно объёма торгов.
Исторически следующий час был таким же примерно в 1 из 5 случаев (обычно в 1 из 10).
Направление цены это не показывает.
≥ — нижняя граница: Binance передаёт не все ликвидации.
Термины: /terms
```

The three high-impact lines appear only under the D7 gate. Their exact strings come from the gate document.

### 5.3 24h tab

```
ПОСЛЕДНИЕ 24 Ч · до 15:10 (Киев)
Цена −1,9% · макс 113 900 · мин 110 800
Диапазон 2,8% (1,4× от медианы 30 дн.)
Объём $38 млрд (1,3× от медианы 30 дн.)
OI +2,1%: Binance +2,8% · Bybit +1,5% · OKX +0,9%
Delta: +$210 млн (покупатели)
Ликвидации лонгов: Binance ≥$42 млн · Bybit $61 млн · OKX $19 млн
Ликвидации шортов: Binance ≥$9 млн · Bybit $14 млн · OKX $6 млн
Funding сейчас 0,006% · среднее за 24 ч 0,009%
Изменения к предыдущим 24 ч:
· диапазон шире: 2,8% против 1,9%
· OI вырос, пока цена падала
≥ — нижняя граница: Binance передаёт не все ликвидации.
Термины: /terms
```

## 6. Horizon computation (all as of the view's data-through)

1. **Windows** are rolling and end at the view's data-through: 1h is the last 12 closed 5m buckets, 24h is the last 288.
2. **Price, range, volume.** Computed from tape V2 per-venue 5m kline OHLC (`x:<venue>:kline_*`) and the cross-venue volume sums, with the `BETA_CONTEXT_1H_V0` definitions:
   - range = median over venues of (max high − min low) / first open;
   - move = median over venues of (last close − first open) / first open;
   - volume = sum.

   **24h completeness:**
   - price and range need at least 282 of the 288 buckets, with the first and last bucket present;
   - the volume ratio needs 288 of 288. Otherwise the volume value is printed with `(неполные)` / `(partial)` and no ratio.
3. **Taker flow:** sum of the 5m `taker_delta_notional_usd_sum`. It is additive, so the sum is exact.
4. **OI.** The tape's per-venue `oi_change_pct` is *within-bucket*: last minus first observation (`analytics/feature_engine/exchange_features.py`, `_oi_feature`). Compounding 12 or 288 buckets misses the changes between buckets.

   Instead, for each venue, read Stage-1 `open_interest`:
   - take the last observation at or before the window start and at or before the window end;
   - each observation must be at most 2 minutes old relative to its boundary;
   - both must have the same `oi_unit` and contract value, otherwise that venue prints `н/д`;
   - per-venue change = (end − start) / start.

   **Aggregate:** median of the venue percents, the same convention as `oi_change_pct_median`. Never a USD sum, because OKX contract value is not provable as of a point in time.

   **Retention:** `open_interest` must keep at least 48h plus tolerance (§8 needs t−48h). The repository defines no retention policy. Owner VPS check, 2026-10-01: `OPEN_INTEREST_RETENTION_48H = PASS` (no retention policy; history far beyond 48h). `OPEN_INTEREST_CONTINUITY_48H = PASS` (48h coverage effectively complete; max gap 1 minute on Binance, Bybit and OKX). The as-of read itself is PR 2; this record is the retention and continuity check only.
5. **Funding:**
   - `now` = the tape's `funding_rate_median` at the view bucket;
   - 24h average = the mean of the tape values over the 24h window.
6. **Baselines ("× usual"):**
   - **1h:** median of rolling-1h values whose window end lies within ±30 minutes of the same UTC time of day, on each of the prior 30 UTC days. Mature at 20 contributing days. The reason is intraday seasonality: US open is not comparable with the Asia night.
   - **24h:** median of rolling-24h values ending at the same UTC time of day on each of the prior 30 days, one value per day. Mature at 20 days.
   - **Display:** one decimal followed by `×`; values below 1 are shown; 10 or more prints `10×+`.
   - **Scope:** presentation only. Never used for detection, never tuned on outcomes, with its own context version label.
7. **Persistence and replay:**
   - New payload keys `horizons` (1h, 24h) and `regime` (D7), with a new context version label and digest.
   - The persisted payload is the record of what was shown.
   - Recompute is deterministic from the tape, the Stage-1 as-of reads, and the D7 table. A later correction of a Stage-1 row may change a recompute, and that is documented, not hidden.

## 7. Liquidations (decided)

1. **Per venue, never summed across venues.** This is the existing principle in `beta/context.py`: venues differ in feed quality, and a sum would hide that.
2. **Binance is a lower bound.** Binance's `forceOrder` stream sends at most one liquidation per symbol per second (`liquidations.is_snapshot_feed`, `storage/schema.sql`), so it under-counts during cascades.
   - Every Binance amount is printed with `≥`.
   - Each tab that prints one ends with the one-line footnote `≥ — нижняя граница: Binance передаёт не все ликвидации.` / `≥ — lower bound: Binance does not report every liquidation.`
3. **Missing is not zero.**
   - A venue whose liquidation feed was unhealthy at any point in the window, or that has no data for it, prints `н/д` / `n/a`, never `$0`.
   - `$0` is printed only when the feed was healthy and nothing was liquidated.
4. **Incomplete windows are lower bounds.** If the window has missing buckets (the 24h completeness rule allows up to 6), every venue's amount in that window gets `≥`.
5. **Sides:** long and short are separate lines, named by the side that was liquidated. There is no long/short ratio and no reading of what the liquidations mean.
6. **Main screen:** no liquidation amounts. The existing liquidation event line ("Long-side liquidations 2/3 venues") is unchanged.

## 8. "Changes vs previous 24h" (frozen presentation rules)

Compare the window W = (t−24h, t] with the previous window P = (t−48h, t−24h]. The rules are evaluated in this order and at most 3 lines are shown:

1. **Range.** Ratio W/P ≥ 1.5 → `диапазон шире: a% против b%`. Ratio ≤ 0.67 → `диапазон уже: …`.
2. **Volume.** Ratio ≥ 1.5 / ≤ 0.67 → `объём выше: $X против $Y` / `объём ниже: …`.
3. **OI together with price, over W.** Shown only when |OI %| ≥ 1.0 and |price %| ≥ 1.0. The sentence is a factual joint statement, for example `OI вырос, пока цена падала`.
4. **Funding.** The sign of the P average differs from the sign of `now` → `Funding стал положительным` / `Funding стал отрицательным`.

If no rule fires: `Крупных изменений к предыдущим 24 ч нет`.

The thresholds are presentation constants in `config/beta_v0.yaml`. They are versioned and never tuned on outcomes.

## 9. Wording additions

- Ratios name their baseline in tabs. The main screen prints only `×`.
- Per-venue numbers are facts. Banned in both languages: "pushing", "dumping", "whales", "short covering", "long unwind", "healthy", "continuation", "reversal", and their Russian equivalents (`толкают`, `сливают`, `киты`, `закрытие шортов`, `разворот`, `продолжение`).
- Every rendered string passes `assert_descriptive` for its language, and neither forbidden list is relaxed.

## 10. How it gets done (owner: traders only after everything below)

| Step | Who | What |
|---|---|---|
| 0 | done 2026-10-01 | D7 confirmation stack, #236 and #238 merged to `main`; stale D7 tests fixed |
| 1 | owner | merge this specification |
| 2 | done (PR 1, existing data) | language setting and string catalog (§3.1); Kyiv time (§3.2); the tab mechanism and `beta_details_opens`; Event tab; 1h tab without OI; liquidation rules (§7); main screen price and `1h` line; removal of the duplicate "Now" block; Russian forbidden list; update `BETA_BTC_MAIN_SCREEN_UX_V1.md` |
| 3 | done (PR 2) | OI 1h and 24h via `open_interest` as-of reads (§6.4); 24h tab; `24h` line; "Changes vs previous 24h" (§8); glossary `/terms`; terminology pass; update `BETA_BTC_TEMPORAL_CONTEXT_V0.md` |
| 4 | done (code, PR 3) | everything in `BETA_D7_REGIME_CONTEXT_GATE_V1.md` §§4–5: Binance 1m quote-volume feed, 90-day backfill, state computation, parity tests, display; the gate pointer in `PRIVATE_BETA_V0_RESTART_DECISION.md`. Activation is an owner step after deploy: warm-up of at least 1440 valid hours, the real-data parity test, then `regime_d7.enabled` |
| 5 | owner on a copy of the production database | pre-beta readiness check. Already recorded 2026-10-01: `OPEN_INTEREST_RETENTION_48H = PASS` (no retention policy; history far beyond 48h); `OPEN_INTEREST_CONTINUITY_48H = PASS` (48h coverage effectively complete; max gap 1 minute on Binance, Bybit and OKX). Still open: D7 backfill ≥ 1440 valid hours; render every main state and every tab in `ru` and `en` on that database |
| 6 | owner | deploy, then the soak gate of `PRIVATE_BETA_V0_RESTART_DECISION.md` |
| 7 | owner | invite codes, up to 20 active users; watch unprompted returns, `beta_details_opens` per tab, and feedback |

**Acceptance for each PR:**
- full-body render tests in `ru` and `en` for each main state and tab, including STALE, DEGRADED, history-building, incomplete-window, immature-baseline, and liquidation-feed-missing cases;
- Kyiv daylight-saving boundary tests;
- the existing PostgreSQL golden test shows detector episodes, transitions, and push decisions identical to the base commit;
- `assert_descriptive` passes on every rendered string;
- a main-screen line-budget test in both languages;
- `python -m compileall -q .`, `python -m pytest -q tests/beta`, `git diff --check`.

## 11. Decision record (2026-10-01)

| Topic | Decision | By |
|---|---|---|
| When traders get the bot | only after steps 2–6 | owner |
| Language | per-user `ru`/`en`, default `ru` | owner |
| Time zone | Kyiv (`Europe/Kyiv`) for all users | owner |
| Windows | rolling 1h and 24h ending at data-through; D7 uses clock hours | delegated by owner |
| Baselines | 1h: same time of day over 30 days; 24h: same time over 30 days | delegated by owner |
| OI narrative | not shown | owner |
| D7 data source | beta-owned Binance 1m feed with quote volume (gate document) | delegated by owner |
| Target user | Russian-speaking BTC intraday traders | owner |
| Tab switching | edit the Details message in place | delegated |
| OI aggregate | median of venue percents; never a USD sum | delegated |
| Liquidations | §7 | delegated |
| Ranks, ids, versions in Details | dropped from the body; one `ref` line kept | delegated |
| "Changes vs 24h" thresholds | §8 values | delegated |
| 24h completeness | ≥ 282/288 for price and range; 288/288 for the volume ratio | delegated |
