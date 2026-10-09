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
| **L2** | «Почему так?» | Trader language in 2–3 blocks: «Что видно сейчас» (one line per L1 observation; an episode reads «Идёт {name}: {its event_description}»), «Что было в похожих ситуациях» (verdict words only), «Чего это не значит» (only when a misreading is likely). | New observations that are not on L1. Historical numbers (they are on L3). |
| **L3** | «Данные» | Numbers in bold groups «Цена и диапазон», «Позиции и поток», «Уровни», «История похожих», each with its baseline («обычно (медиана 30 дн.)»); directional history with N, the random-level baseline and the 95 % interval. | A number without its baseline. A chance without its exact calibration (P1). |

### 1.1 L1 anatomy
1. **Header:** «₿ BTC · $64 000 · 10:30 Киев» (the live price and the view's as-of time).
2. **State line with its number:** «⚡ BTC −1,3 % за час» (⚡ for an episode or the extreme range band, else 📈 / 📉 by sign), «🎯 BTC у уровня …», or the calm sentence.
3. **One human sentence of context**, built from facts only («Сейчас резкое падение, цена ходит намного шире обычного для этого часа.»).
4. **«🎯 Рядом»:** at most 2 levels (the one at the price first, then the nearest above and below): the name from data, ↑ / ↓, the distance %. Omitted when there are none.
5. The calendar line when CPI / FOMC is within 24 h.

**The calm family** (no salience rule fires) is one full sentence with numbers, and each state reads differently by formal predicate:
- «💤 Спокойно. За час +0,3 %, диапазон и объём как обычно.» — both 1h labels known and ordinary;
- «💤 Тихо. За час +0,02 %, диапазон уже обычного, …» — compression: the 1h range in the existing low band (`context.tail_label` «bottom», rank ≤ `tail_display_max`, mature tier);
- «… объём ниже обычного» — thin trading: the 1h volume in the same low band;
- «💤 Выходные. …» — `data_through` falls on a Saturday or Sunday;
- the brief / catchup view adds its window: «📅 За 8 ч (02:00–10:00 Киев): BTC +0,30 %, диапазон 63 980–64 390.»;
- an unknown label (young history) drops the band words and keeps the move only.
The low band is a display band, not a salience rule: `PULSY_SALIENCE_V1` is unchanged.

**Stale ≠ degraded.** Both fire the frozen `stale` salience rule, and render differently:
- **stale** (status `DATA STALE` or decision reason `DATA_STALE`): «₿ BTC», then «🔎 Данные запаздывают: последние от 05:00 Киев. Текущих цифр нет.» and nothing else — no price, levels, calendar, or L3 numbers;
- **degraded** (`DATA DEGRADED`): the normal header with price, «🔎 Неполные данные: открытые позиции. Остальное — ниже.» (inputs named from `view.status_reasons`), then everything still valid; band words and L3 lines of a partial family are dropped.

**Example (RU), /btc L1, busy:**
```
₿ BTC · $62 480 · 14:10 Киев

⚡ BTC −0,84% за час
Сейчас резкое падение, цена ходит намного шире обычного для этого часа.

🎯 Рядом
🎯 у цены: минимум вчера 62 490
↑ максимум вчера 62 950 · +0,75%
```

**Example (RU), /btc L2:**
```
🔎 Почему так

Что видно сейчас
Идёт резкое падение: движение цены за 5м в нижних 5% последних 30 дней при снижении открытого интереса в его нижних 10%, не менее чем на 2 биржах.
Цена стоит у уровня: минимум вчера 62 490.
За последний час цена прошла намного больше, чем обычно в это время суток.

Что было в похожих ситуациях
У уровня «максимум вчера» через час цена была выше него так же часто, как у случайного уровня.

Чего это не значит
Это описание того, что уже произошло, а не прогноз, куда пойдёт цена.
```

**Example (RU), /btc L3:**
```
📊 Данные

📊 Цена и диапазон
За час: −0,84%
Диапазон за час: 1,12% · обычно 0,49% (медиана 30 дн.)
За 24 ч: максимум 113 900, минимум 110 800
Оценка диапазона на 24 ч: 60 230–64 730

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
- **Level line** (one shared form for «Рядом», `/levels`, L3 and the level card): «{↑/↓} {name} {price} · {distance}». The level at the price reads «🎯 у цены: {name} {price}», with no arrow and no «0,00 %».
  - The name comes from the level's data (`decision_format.level_name` on its member kind), never from free text.
  - P1 adds the card's chance line, with its exact calibration.
- **Notification** (hour / level / move / brief): one bold headline with its number, a blank line, one sentence, the time or window line («08:00–09:00 Киев»), then one row of buttons. The move push adds one rule-backed sentence whose predicate is the alert itself: «Для 15 минут это резкое движение.»

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
- **Fixed emoji set**, at most one per header: ₿ (the /btc header) 💤 calm, ⚡ sharp move or episode, 📈 / 📉 the hour's direction, 🎯 levels (and the «у цены» line), 📅 calendar and brief, 🔎 the «Почему так» header and L3 history, 📊 **data only** (the L3 header and its data groups), 💬 reserved. L2 block titles («Что видно сейчас», «Что было в похожих ситуациях», «Чего это не значит») are plain bold, with no emoji. No other emoji.
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

**The corridor** is named «оценка диапазона на 24 ч» / «24h range estimate», never «обычный диапазон». It is not on /btc L1, except for that one `corridor_edge` line («у края оценки суточного диапазона»). Its numbers are on L3. Accuracy appears only on L3, and only as the exact comparison (P1).

## 5. Phrase dictionary (`beta/ux/phrases.py`, authoritative)
Every user-visible phrase, with its formal predicate (the predicate is for the standard and tests; users never see it). A test keeps this table equal to the code.

| Key | RU | EN | Allowed when |
|---|---|---|---|
| `hdr_btc` | ₿ BTC · ${price} · {clock} Киев | ₿ BTC · ${price} · {clock} Kyiv | decision block available: its live price; the view's data_through in Kyiv time |
| `hdr_btc_na` | ₿ BTC · {clock} Киев | ₿ BTC · {clock} Kyiv | no fresh price (decision block unavailable) |
| `st_move` | {emoji} BTC {pct} за час | {emoji} BTC {pct} over the hour | an episode, the range bands or high volume fired; ⚡ for an episode or the extreme range band, else 📈 / 📉 by the sign of horizons.1h.price_move_pct |
| `st_level` | 🎯 BTC у уровня {name} {edge} | 🎯 BTC at a level: {name} {edge} | only level_at / event_today / corridor_edge fired and decision.levels.at is set |
| `st_quiet` | 💤 За час {pct} | 💤 {pct} over the hour | only event_today / corridor_edge fired: the hour itself was quiet |
| `st_calm_head` | 💤 Спокойно. | 💤 Calm. | nothing fires (or only the degraded-data line), no 1h low band and not a weekend |
| `st_calm_head_low` | 💤 Тихо. | 💤 Quiet. | as st_calm_head, and the 1h range or volume is in the low band (tail_label bottom, rank <= context.tail_display_max, tier mature) |
| `st_calm_head_weekend` | 💤 Выходные. | 💤 Weekend. | as st_calm_head, and data_through falls on a Saturday or Sunday (the user's clock) |
| `st_calm_move` | за час {pct} | {pct} over the hour | the calm line: horizons.1h.price_move_pct |
| `calm_both_usual` | диапазон и объём как обычно | range and volume as usual | both 1h labels known, neither high nor in the low band |
| `calm_range_usual` | диапазон как обычно | range as usual | 1h range label known, not high, not in the low band (volume is in the low band) |
| `calm_volume_usual` | объём как обычно | volume as usual | 1h volume label known, not high, not in the low band (range is in the low band) |
| `calm_range_low` | диапазон уже обычного | range narrower than usual | 1h range in the low band (rank <= context.tail_display_max, tier mature) |
| `calm_volume_low` | объём ниже обычного | volume below usual | 1h volume in the low band (rank <= context.tail_display_max, tier mature) |
| `st_calm_noprice` | 💤 Спокойно. | 💤 Calm. | nothing fires and the 1h move is missing |
| `hdr_btc_bare` | ₿ BTC | ₿ BTC | stale data: no current price or time on the header |
| `st_stale` | 🔎 Данные запаздывают: последние от {clock} Киев. Текущих цифр нет. | 🔎 Data is late: the latest is from {clock} Kyiv. No current numbers. | product status DATA STALE, or decision reason DATA_STALE; the view's data_through |
| `st_stale_never` | 🔎 Данные запаздывают. Текущих цифр нет. | 🔎 Data is late. No current numbers. | as st_stale, and the view has no data_through |
| `st_degraded` | 🔎 Неполные данные: {inputs}. Остальное — ниже. | 🔎 Partial data: {inputs}. The rest is below. | product status DATA DEGRADED (not stale); inputs named from view.status_reasons |
| `in_price` | цена и диапазон | price and range | status reason FAMILY_UNUSABLE:price_structure |
| `in_oi` | открытые позиции | open positions | status reason FAMILY_UNUSABLE:oi |
| `in_volume` | объём | volume | status reason FAMILY_UNUSABLE:volume |
| `in_feed` | поток с бирж | the exchange feed | status reason INGESTION_HEARTBEAT_UNHEALTHY |
| `in_calc` | расчёт последнего часа | the last hour's calculation | status reason MATERIALIZATION_FAILED, STALE_COHERENCE_BARRIER or EVALUATION_NOT_FRESH |
| `in_any` | часть входных данных | some inputs | DATA DEGRADED with no known reason |
| `win_line` | 📅 За {hours} ч ({start}–{end} Киев): BTC {pct}, диапазон {low}–{high}. | 📅 Last {hours} h ({start}–{end} Kyiv): BTC {pct}, range {low}–{high}. | the view carries a complete market window (the brief / catchup view): market.window |
| `cx_episode` | сейчас {name} | {name} is on | an active episode in state TRIGGERED |
| `cx_range_extreme` | цена ходит намного шире обычного для этого часа | the price swings far wider than usual for this hour | 1h range rank >= context.label_extreme, tier mature |
| `cx_range_high` | цена ходит шире обычного для этого часа | the price swings wider than usual for this hour | 1h range rank >= context.label_high (below extreme), tier mature |
| `cx_volume_high` | объём выше обычного | volume is above usual | 1h volume rank >= context.label_high, tier mature |
| `cx_corridor_edge` | цена у края оценки суточного диапазона | the price is near the edge of the 24h range estimate | price within CORRIDOR_EDGE_SHARE of the 24h half-width from a 24h corridor bound |
| `lv_at_line` | 🎯 у цены: {name} {edge} | 🎯 at the price: {name} {edge} | the level zone decision.levels.at (the price is inside it): no arrow, no distance |
| `near_hdr` | 🎯 Рядом | 🎯 Nearby | decision.levels has at least one level |
| `near_line` | {arrow} {name} {edge} · {dist} | {arrow} {name} {edge} · {dist} | a level zone: name from its member kind (decision_format.level_name), edge, distance_pct; ↑ above the price, ↓ below |
| `ev_today` | 📅 Сегодня в {clock} — {event}. | 📅 Today at {clock} — {event}. | the next CPI / FOMC in the calendar is within 24 h |
| `ev_cpi` | CPI (инфляция США) | CPI (US inflation) | event kind CPI |
| `ev_fomc` | решение ФРС | the Fed decision | event kind FOMC |
| `hdr_why` | 🔎 Почему так | 🔎 Why | L2 of the screen |
| `b_now` | Что видно сейчас | What we see now | always on L2 |
| `now_stale` | Новых данных давно не было, поэтому текущих цифр нет. | No new data has arrived for a while, so there are no current numbers. | st_stale |
| `now_degraded` | Неполные: {inputs}. Цифры по ним не показываю, остальные — по полным данным. | Partial: {inputs}. Their numbers are not shown; the rest comes from complete data. | st_degraded |
| `now_episode` | Идёт {name}: {meaning} | {name} is on: {meaning} | cx_episode; meaning = formatter.event_description of the episode's event type |
| `now_level_at` | Цена стоит у уровня: {name} {edge}. | The price is at a level: {name} {edge}. | decision.levels.at is set |
| `now_range_extreme` | За последний час цена прошла намного больше, чем обычно в это время суток. | In the last hour the price covered far more ground than usual for this time of day. | cx_range_extreme |
| `now_range_high` | За последний час цена прошла больше, чем обычно в это время суток. | In the last hour the price covered more ground than usual for this time of day. | cx_range_high |
| `now_volume_high` | Торгуют активнее, чем обычно в это время суток. | Trading is busier than usual for this time of day. | cx_volume_high |
| `now_event` | В {clock} выходит {event}. | {event} is out at {clock}. | ev_today |
| `now_corridor_edge` | Цена у края оценки суточного диапазона. | The price is near the edge of the 24h range estimate. | cx_corridor_edge |
| `now_calm` | Диапазон и объём за час — как обычно в это время суток. | Range and volume over the hour are as usual for this time of day. | calm_both_usual |
| `now_range_low` | За час цена прошла меньше, чем обычно в это время суток. | Over the hour the price covered less ground than usual for this time of day. | calm_range_low |
| `now_volume_low` | Торгуют меньше, чем обычно в это время суток. | Trading is thinner than usual for this time of day. | calm_volume_low |
| `now_calm_young` | Сравнить с обычным пока не с чем: истории этого часа ещё мало. | Nothing to compare with yet: this hour's history is still short. | nothing fires and a 1h label is unknown (history not mature) |
| `b_hist` | Что было в похожих ситуациях | What happened in similar cases | a nearby level with a stored first-touch history |
| `hist_same` | У уровня «{name}» через час цена была {side} него так же часто, как у случайного уровня. | At «{name}», an hour later the price was {side} it about as often as at a random level. | history.verdicts.1h == as_usual (levels.py, Holm-adjusted) |
| `hist_more` | У уровня «{name}» через час цена была {side} него чаще, чем у случайного уровня. | At «{name}», an hour later the price was {side} it more often than at a random level. | history.verdicts.1h == differs and real hold_rate > control hold_rate |
| `hist_less` | У уровня «{name}» через час цена была {side} него реже, чем у случайного уровня. | At «{name}», an hour later the price was {side} it less often than at a random level. | history.verdicts.1h == differs and real hold_rate < control hold_rate |
| `hist_few` | По уровню «{name}» истории пока мало для вывода. | There is too little history at «{name}» to say. | history.verdicts.1h == insufficient |
| `side_above` | выше | above | the level is above the price |
| `side_below` | ниже | below | the level is below the price |
| `b_not` | Чего это не значит | What it does not mean | an episode, a wide range, high volume or a level at the price is shown |
| `not_forecast` | Это описание того, что уже произошло, а не прогноз, куда пойдёт цена. | This describes what has happened; it is not a forecast of where the price goes. | b_not |
| `hdr_data` | 📊 Данные | 📊 Data | L3 of the screen |
| `g_price` | 📊 Цена и диапазон | 📊 Price and range | always on L3 |
| `g_flow` | 📊 Позиции и поток | 📊 Positions and flow | volume, OI or taker delta present |
| `g_levels` | 🎯 Уровни | 🎯 Levels | decision.levels non-empty |
| `g_hist` | 🔎 История похожих | 🔎 Similar cases in history | a nearby level with a first-touch history |
| `l3_price_1h` | За час: {pct} | Over the hour: {pct} | horizons.1h.price_move_pct |
| `l3_range_1h` | Диапазон за час: {val} · обычно {base} (медиана {n} дн.) | 1h range: {val} · usually {base} (median of {n} days) | horizons.1h.range_width_pct, baseline_median.range_width_pct_median, baseline_days |
| `l3_hilo_24h` | За 24 ч: максимум {high}, минимум {low} | 24h: high {high}, low {low} | horizons.24h.high / low (price_complete) |
| `l3_corridor` | Оценка диапазона на 24 ч: {lower}–{upper} | 24h range estimate: {lower}–{upper} | decision.corridor.horizons.24h lower / upper |
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
| `nt_move_rule` | Для 15 минут это резкое движение. | For 15 minutes, this is a sharp move. | the move alert itself: \|15m move\| over the 1h-scale threshold (market_alerts.detect_move) |
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
| **J** distinct states | The calm family (usual, compression, thin, weekend, night window) and stale vs degraded read differently | `test_calm_family_states_read_differently`, `test_stale_shows_nothing_current_and_degraded_names_the_partial_input` |
| **K** architect text fixes | Episode meaning from event_description; «у цены» level line; «оценка диапазона»; the move push's rule sentence; 📊 data only | `test_architect_text_fixes` |
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
  - `from_view(view)` for `/btc`, `/levels` and the brief (the catchup view); it carries `status_reasons` (additive key) so degraded data can name the partial input;
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
