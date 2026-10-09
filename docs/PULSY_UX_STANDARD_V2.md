# Pulsy UX standard V2

**Status:** `P0_SKELETON` (2026-10-09, track A for ОПГ-1). The owner approved this UX on 2026-10-09.
- P0 is the standard and a renderer in `beta/ux/`. It is **wired to no user surface**: `ux.v2_enabled: false` in `config/beta_v0.yaml`.
- The old render is untouched.
- It brings no change to Day 0, the measurement contract or analytics.
- The renderer is deterministic: facts → salience → phrases → render. No LLM.

## 1. Three levels
Every screen has up to three levels, and each level allows only certain claims:

| Level | Name | What it may say | What it may not say |
|---|---|---|---|
| **L1** | summary | Current observations only, as words from frozen rules (§4, §5), each with its own current number. | Any **historical number**: no percent of history, no «× обычного», no N, no chance, no interval. |
| **L2** | «Почему так?» | Trader language in 2–3 blocks: «Что видно сейчас» (one line per L1 observation), «Что было в похожих ситуациях» (verdict words only), «Чего это не значит» (only when a misreading is likely). | New observations that are not on L1. Historical numbers (they are on L3). |
| **L3** | «Данные» | Numbers in bold groups «Цена и диапазон», «Позиции и поток», «Уровни», «История похожих», each with its baseline («обычно (медиана 30 дн.)»); directional history with N, the random-level baseline and the 95 % interval. | A number without its baseline. A chance without its exact calibration (P1). |

### 1.1 L1 anatomy
1. **Header:** «₿ BTC · $64 000 · 10:30 Киев» (the live price and the view's as-of time).
2. **State line with its number:** «⚡ BTC −1,3 % за час» (⚡ for an episode or the extreme range band, else 📈 / 📉 by sign), «🎯 BTC у уровня …», or the calm sentence.
3. **One human sentence of context**, built from facts only («Сейчас резкое падение, цена ходит намного шире обычного для этого часа.»).
4. **«🎯 Рядом»:** at most 2 levels (the one at the price first, then the nearest above and below): the name from data, ↑ / ↓, the distance %. Omitted when there are none.
5. The calendar line when CPI / FOMC is within 24 h.

**Calm** is a full sentence with numbers: «💤 Спокойно. За час +0,3 %, диапазон и объём как обычно.» The «как обычно» part appears only when both labels are known (mature tier); otherwise only the move.

**Example (RU), /btc L1, busy:**
```
₿ BTC · $62 480 · 14:10 Киев

⚡ BTC −0,84% за час
Сейчас резкое падение, цена ходит намного шире обычного для этого часа.

🎯 Рядом
↑ минимум вчера 62 490 · 0,00%
↑ максимум вчера 62 950 · +0,75%
```

**Example (RU), /btc L2:**
```
🔎 Почему так

📊 Что видно сейчас
Сейчас резкое падение: его условия выполняются прямо сейчас.
Цена стоит у уровня: минимум вчера 62 490.
За последний час цена прошла намного больше, чем обычно в это время суток.

🔎 Что было в похожих ситуациях
У уровня «максимум вчера» через час цена была выше него так же часто, как у случайного уровня.

💬 Чего это не значит
Это описание того, что уже произошло, а не прогноз, куда пойдёт цена.
```

**Example (RU), /btc L3:**
```
📊 Данные

📊 Цена и диапазон
За час: −0,84%
Диапазон за час: 1,12% · обычно 0,49% (медиана 30 дн.)
За 24 ч: максимум 113 900, минимум 110 800
Обычный диапазон на 24 ч: 60 230–64 730

📊 Позиции и поток
Объём за час: $1,9 млрд · обычно $905 млн (медиана 30 дн.)
Открытых позиций стало меньше: −0,60% за час
Продажи по рынку сильнее покупок на $84 млн за час

🎯 Уровни
↑ максимум вчера 62 950 · +0,75%
↓ минимум Азии 61 900 · −0,93%

🔎 История похожих
Максимум вчера: после первого касания (812 случаев): через 1ч цена выше уровня в 47% — у случайного уровня 43% (+4,0 п.п.; 95% интервал −1,2…+9,1)
```

## 2. Components
- **Block:** a bold header with one emoji, then its lines. Blocks are separated by one blank line.
- **Level line** (one shared form for «Рядом», `/levels`, L3 and the level card): «{↑/↓} {name} {price} · {distance}».
  - The name comes from the level's data (`decision_format.level_name` on its member kind), never from free text.
  - P1 adds the card's chance line, with its exact calibration.
- **Notification** (hour / level / move / brief): one bold headline with its number, a blank line, one sentence, the time or window line («08:00–09:00 Киев»), then one row of buttons.

**Example (RU), unusual-hour push:**
```
📉 Необычный час: BTC −0,84%

Цена ходит шире обычного для этого часа, объём выше обычного.
08:00–09:00 Киев
```
- **Navigation:** L1 has «Почему так?» and «Данные»; L2 and L3 have «← Назад». Callbacks have the form `ux:<screen>:<level>`.

## 3. Telegram format
- **HTML only:** `<b>` for headers; every other line is escaped text. No tables, no monospace, no Markdown.
- **Spacing:** blank lines between blocks, never inside one.
- **Fixed emoji set**, one per block header: ₿ (the /btc header) 💤 calm, ⚡ sharp move or episode, 📈 / 📉 the hour's direction, 🎯 levels, 📅 calendar and brief, 💬 «Чего это не значит», 🔎 «Почему так» and history, 📊 data. No other emoji.
- **Numbers:** thousands are separated by a **narrow no-break space** (U+202F) in RU. Number and unit are joined by a **no-break space** (U+00A0). Signs use the true minus «−».
- **No machine language:** no rule, salience or predicate words, no snake_case or CONSTANT ids, no None / null / braces. A lint test checks every rendered output.
- **EN** reads as a native product («strong buying», «as of»), not a translation of internal names.
- **Length maxima** (maxima, not targets): L1 ≤ 600 characters, L2 ≤ 900, L3 ≤ 1500, a notification ≤ 500.
- **Buttons:** at most 2 per row and at most 3 rows. Callback data is ≤ 64 bytes.
- **Expandable quotes** (`<blockquote expandable>`) are not used until checked in a real client.

## 4. Salience (frozen: `beta/ux/select.py`, `PULSY_SALIENCE_V1`)
The rules are evaluated in this order. L1 shows the first **3** that fire, and L2 explains exactly those.

| # | Key | Fires when (existing labels and thresholds only) |
|---|---|---|
| 1 | `stale` | The product status is `DATA STALE` or `DATA DEGRADED`, or the decision block reports `DATA_STALE`. |
| 2 | `episode` | An active episode is `TRIGGERED` (the detector). |
| 3 | `level_at` | `decision.levels.at` is set: the price is inside a merged level zone. |
| 4 | `range_extreme` | The 1h range rank is ≥ `context.label_extreme` (0.99) with a mature tier (`context.level_label`). |
| 5 | `range_high` | The 1h range rank is ≥ `context.label_high` (0.95), below the extreme band. |
| 6 | `volume_high` | The 1h volume rank is ≥ `context.label_high` (0.95). |
| 7 | `event_today` | The next CPI or FOMC in the calendar is within 24 h. |
| 8 | `corridor_edge` | The price is within **10 %** of the 24h half-width from a 24h corridor bound (`CORRIDOR_EDGE_SHARE`). |
| — | `nothing` | None fires: the calm sentence («💤 Спокойно. …»). |

**The corridor** is not on /btc L1, except for that one `corridor_edge` line. Its numbers are on L3. Accuracy appears only on L3, and only as the exact comparison (P1).

## 5. Phrase dictionary (`beta/ux/phrases.py`, authoritative)
Every user-visible phrase, with its formal predicate (the predicate is for the standard and tests; users never see it). A test keeps this table equal to the code.

| Key | RU | EN | Allowed when |
|---|---|---|---|
| `hdr_btc` | ₿ BTC · ${price} · {clock} Киев | ₿ BTC · ${price} · {clock} Kyiv | decision block available: its live price; the view's data_through in Kyiv time |
| `hdr_btc_na` | ₿ BTC · {clock} Киев | ₿ BTC · {clock} Kyiv | no fresh price (decision block unavailable) |
| `st_move` | {emoji} BTC {pct} за час | {emoji} BTC {pct} over the hour | an episode, the range bands or high volume fired; ⚡ for an episode or the extreme range band, else 📈 / 📉 by the sign of horizons.1h.price_move_pct |
| `st_level` | 🎯 BTC у уровня {name} {edge} | 🎯 BTC at a level: {name} {edge} | only level_at / event_today / corridor_edge fired and decision.levels.at is set |
| `st_quiet` | 💤 За час {pct} | 💤 {pct} over the hour | only event_today / corridor_edge fired: the hour itself was quiet |
| `st_calm` | 💤 Спокойно. За час {pct}, диапазон и объём как обычно. | 💤 Calm. {pct} over the hour, range and volume as usual. | nothing fires and both 1h labels (range, volume) are known and below context.label_high |
| `st_calm_short` | 💤 Спокойно. За час {pct}. | 💤 Calm. {pct} over the hour. | nothing fires, a 1h label is unknown (history not mature) |
| `st_calm_noprice` | 💤 Спокойно. | 💤 Calm. | nothing fires and the 1h move is missing |
| `st_stale` | 🔎 Свежих данных нет — показываю последнее, что есть. | 🔎 No fresh data — showing the last known state. | product status DATA STALE or DATA DEGRADED, or decision reason DATA_STALE |
| `cx_episode` | сейчас {name} | {name} is on | an active episode in state TRIGGERED |
| `cx_range_extreme` | цена ходит намного шире обычного для этого часа | the price swings far wider than usual for this hour | 1h range rank >= context.label_extreme, tier mature |
| `cx_range_high` | цена ходит шире обычного для этого часа | the price swings wider than usual for this hour | 1h range rank >= context.label_high (below extreme), tier mature |
| `cx_volume_high` | объём выше обычного | volume is above usual | 1h volume rank >= context.label_high, tier mature |
| `cx_corridor_edge` | цена у края обычного суточного диапазона | the price is near the edge of its usual daily range | price within CORRIDOR_EDGE_SHARE of the 24h half-width from a 24h corridor bound |
| `near_hdr` | 🎯 Рядом | 🎯 Nearby | decision.levels has at least one level |
| `near_line` | {arrow} {name} {edge} · {dist} | {arrow} {name} {edge} · {dist} | a level zone: name from its member kind (decision_format.level_name), edge, distance_pct; ↑ above the price, ↓ below |
| `ev_today` | 📅 Сегодня в {clock} — {event}. | 📅 Today at {clock} — {event}. | the next CPI / FOMC in the calendar is within 24 h |
| `ev_cpi` | CPI (инфляция США) | CPI (US inflation) | event kind CPI |
| `ev_fomc` | решение ФРС | the Fed decision | event kind FOMC |
| `hdr_why` | 🔎 Почему так | 🔎 Why | L2 of the screen |
| `b_now` | 📊 Что видно сейчас | 📊 What we see now | always on L2 |
| `now_stale` | Свежих данных нет, цифры могут отставать от рынка. | There is no fresh data; numbers may lag the market. | st_stale |
| `now_episode` | Сейчас {name}: его условия выполняются прямо сейчас. | {name} is on: its conditions hold right now. | cx_episode |
| `now_level_at` | Цена стоит у уровня: {name} {edge}. | The price is at a level: {name} {edge}. | decision.levels.at is set |
| `now_range_extreme` | За последний час цена прошла намного больше, чем обычно в это время суток. | In the last hour the price covered far more ground than usual for this time of day. | cx_range_extreme |
| `now_range_high` | За последний час цена прошла больше, чем обычно в это время суток. | In the last hour the price covered more ground than usual for this time of day. | cx_range_high |
| `now_volume_high` | Торгуют активнее, чем обычно в это время суток. | Trading is busier than usual for this time of day. | cx_volume_high |
| `now_event` | В {clock} выходит {event}. | {event} is out at {clock}. | ev_today |
| `now_corridor_edge` | Цена у края диапазона, в котором она обычно проводит сутки. | The price is near the edge of the range it usually stays in over a day. | cx_corridor_edge |
| `now_calm` | Диапазон и объём за час — как обычно в это время суток. | Range and volume over the hour are as usual for this time of day. | st_calm |
| `now_calm_young` | Сравнить с обычным пока не с чем: истории этого часа ещё мало. | Nothing to compare with yet: this hour's history is still short. | st_calm_short |
| `b_hist` | 🔎 Что было в похожих ситуациях | 🔎 What happened in similar cases | a nearby level with a stored first-touch history |
| `hist_same` | У уровня «{name}» через час цена была {side} него так же часто, как у случайного уровня. | At «{name}», an hour later the price was {side} it about as often as at a random level. | history.verdicts.1h == as_usual (levels.py, Holm-adjusted) |
| `hist_more` | У уровня «{name}» через час цена была {side} него чаще, чем у случайного уровня. | At «{name}», an hour later the price was {side} it more often than at a random level. | history.verdicts.1h == differs and real hold_rate > control hold_rate |
| `hist_less` | У уровня «{name}» через час цена была {side} него реже, чем у случайного уровня. | At «{name}», an hour later the price was {side} it less often than at a random level. | history.verdicts.1h == differs and real hold_rate < control hold_rate |
| `hist_few` | По уровню «{name}» истории пока мало для вывода. | There is too little history at «{name}» to say. | history.verdicts.1h == insufficient |
| `side_above` | выше | above | the level is above the price |
| `side_below` | ниже | below | the level is below the price |
| `b_not` | 💬 Чего это не значит | 💬 What it does not mean | an episode, a wide range, high volume or a level at the price is shown |
| `not_forecast` | Это описание того, что уже произошло, а не прогноз, куда пойдёт цена. | This describes what has happened; it is not a forecast of where the price goes. | b_not |
| `hdr_data` | 📊 Данные | 📊 Data | L3 of the screen |
| `g_price` | 📊 Цена и диапазон | 📊 Price and range | always on L3 |
| `g_flow` | 📊 Позиции и поток | 📊 Positions and flow | volume, OI or taker delta present |
| `g_levels` | 🎯 Уровни | 🎯 Levels | decision.levels non-empty |
| `g_hist` | 🔎 История похожих | 🔎 Similar cases in history | a nearby level with a first-touch history |
| `l3_price_1h` | За час: {pct} | Over the hour: {pct} | horizons.1h.price_move_pct |
| `l3_range_1h` | Диапазон за час: {val} · обычно {base} (медиана {n} дн.) | 1h range: {val} · usually {base} (median of {n} days) | horizons.1h.range_width_pct, baseline_median.range_width_pct_median, baseline_days |
| `l3_hilo_24h` | За 24 ч: максимум {high}, минимум {low} | 24h: high {high}, low {low} | horizons.24h.high / low (price_complete) |
| `l3_corridor` | Обычный диапазон на 24 ч: {lower}–{upper} | Usual 24h range: {lower}–{upper} | decision.corridor.horizons.24h lower / upper |
| `l3_volume_1h` | Объём за час: {val} · обычно {base} (медиана {n} дн.) | 1h volume: {val} · usually {base} (median of {n} days) | horizons.1h.volume_notional_usd, baseline_median.volume_notional_usd_sum, baseline_days |
| `l3_oi_down` | Открытых позиций стало меньше: {pct} за час | Open positions fell: {pct} over the hour | horizons.1h.oi_change_pct < 0 |
| `l3_oi_up` | Открытых позиций стало больше: {pct} за час | Open positions rose: {pct} over the hour | horizons.1h.oi_change_pct > 0 |
| `l3_buys` | Покупки по рынку сильнее продаж на {usd} за час | Strong buying: {usd} more bought than sold over the hour | horizons.1h.taker_delta_notional_usd_sum > 0 |
| `l3_sells` | Продажи по рынку сильнее покупок на {usd} за час | Strong selling: {usd} more sold than bought over the hour | horizons.1h.taker_delta_notional_usd_sum < 0 |
| `l3_level` | {arrow} {name} {edge} · {dist} | {arrow} {name} {edge} · {dist} | near_line, up to 3 a side |
| `l3_hist` | {name}: {line} | {name}: {line} | decision_format._hist_lines: the 1h hold rate beside the random level's, with N and the 95% interval |
| `hdr_levels` | 🎯 Уровни BTC | 🎯 BTC levels | always |
| `lv_none` | Уровней рядом нет. | No levels nearby. | both sides empty |
| `nt_hour` | {emoji} Необычный час: BTC {pct} | {emoji} Unusual hour: BTC {pct} | a TRIGGERED unusual-hour push; 📈 / 📉 by the sign of gate.values.price_move_pct |
| `nt_hour_any` | ⚡ Необычный час | ⚡ Unusual hour | the hour push without a price move |
| `nt_hour_why` | {what}. | {what}. | gate.passed: range → cx_range_high, volume → cx_volume_high |
| `nt_level` | 🎯 BTC у уровня: {name} {level} | 🎯 BTC at a level: {name} {level} | a market alert of kind level (first touch of its period) |
| `nt_level_why` | Первое касание за {period}: цена {price}. | First touch {period}: price {price}. | payload.period, payload.price |
| `period_day` | день | today | payload.period == day |
| `period_week` | неделю | this week | payload.period == week |
| `period_month` | месяц | this month | payload.period == month |
| `nt_move` | ⚡ BTC {pct} за 15 минут | ⚡ BTC {pct} in 15 minutes | a market alert of kind move (\|15m move\| over the 1h scale threshold, market_alerts.detect_move) |
| `nt_move_why` | Цена прошла от {open} до {close}. | The price went from {open} to {close}. | payload.open / close |
| `nt_brief` | 📅 Сводка за {hours} ч: BTC {pct} | 📅 Last {hours} h: BTC {pct} | the morning brief (catchup view): market.window.price_move_pct |
| `nt_brief_range` | Диапазон {low}–{high}. | Range {low}–{high}. | market.window low / high |
| `nt_brief_none` | Полного окна за этот период в данных нет. | The data has no complete window for this period. | the brief view has no market.window |
| `nt_at` | {clock} Киев | {clock} Kyiv | the alert's time |
| `nt_window` | {start}–{end} Киев | {start}–{end} Kyiv | the alert's or window's start and end |
| `btn_why` | Почему так? | Why? | L1 → L2 |
| `btn_data` | Данные | Data | L1/L2 → L3 |
| `btn_levels` | Уровни | Levels | → /levels L1 |
| `btn_back` | ← Назад | ← Back | L2/L3 → the level above |

## 6. The owner's rules, each mapped to a test (`tests/beta/test_pulsy_ux_v2.py`)

| Rule | Meaning | Test |
|---|---|---|
| **A** compact | L1 within its maximum and at most `L1_MAX` (3) salient observations | `test_rule_A_l1_is_compact` |
| **B** compact L2 | L2 within its maximum, in its 2–3 named blocks | `test_rule_B_l2_is_compact` |
| **C** exact historical meaning | No «пробой / закрепление / удержался» for "the price an hour later was above the level". An OI decline is «открытых позиций стало меньше». Directional history keeps its baseline, N and interval on L3. | `test_rule_C_exact_historical_meaning` |
| **D** every number backed | L3 numbers equal the facts and today's render. A chance appears only with its exact calibration (P1). Level names come from the data, so a weekly low cannot be labelled a weekly high. | `test_rule_D_l3_numbers_equal_the_facts_and_todays_render`, `test_rule_D_level_names_come_from_the_data` |
| **E** formatting | Valid Telegram HTML, no-break spaces in numbers, emoji from the fixed set, buttons ≤ 2×3, callback ≤ 64 bytes | `test_rule_E_telegram_format` |
| **F** no drama | No «обвал / взрыв / паника / ракета», no «!!» | `test_rule_F_no_drama` |
| **G** lively words only by rule | Every phrase has a predicate; the renderer prints only dictionary phrases and fact values | `test_rule_G_every_phrase_has_a_rule_and_the_doc_lists_them` |
| **H** no machine language | No internal tokens in any rendered output | `test_no_machine_language_reaches_a_user` |
| **I** anatomy | L1 header / state / «Рядом» ≤ 2; L3 bold groups; notifications: headline with number, one sentence, window, buttons | `test_l1_anatomy_and_l3_groups`, `test_notifications_have_one_headline_one_sentence_and_a_window` |

Also tested:
- no historical number on L1;
- the RU/EN pairs are complete and EN has no Cyrillic;
- `assert_descriptive` (the trade-call lint) holds on every render;
- the length maxima;
- the calm sentence for a calm state;
- facts equivalence;
- the flag is off;
- the level alert and level card take names from data and degrade without a zone.

## 7. API for track B (stable)
- `render(screen: str, level: int, lang: str, facts) -> (html: str, buttons: list[list[(label, callback)]])`.
- **Screens** (`SCREENS`):
  - `btc` 1/2/3;
  - `levels` 1;
  - `level_card` 1 (facts: `{"zone": …}`);
  - `hour`, `level`, `move`, `brief` 1.
- **Facts** (`beta/ux/facts.py`, read-only copies of the persisted payload; nothing is computed):
  - `from_view(view)` for `/btc`, `/levels` and the brief (the catchup view);
  - `from_alert("level" | "move", payload)`;
  - `from_hour_gate(triggered_at, gate)`.
  - `facts_equivalent(facts, view)` lists any fact that drifted from the payload.
- An unknown screen or level raises an error; the renderer never guesses.

## 8. Scope
- **P0 (this PR):**
  - the standard;
  - `beta/ux/`, with `/btc` L1/L2/L3, `/levels` L1 and the level card, and the hour, level, move and brief notifications;
  - the flag, off;
  - the tests.
- **P1 needs ОПГ-2's review:** any template with a **level-race line or a chance**, meaning the level card's chance and race lines, `/check`, the race line in the level push, and accuracy on L3. Not in P0.
- **Not in P0:** wiring into the bot, `/check`, `/catchup` as a screen, the weekly report, event reminders and personal `/alert` texts.
