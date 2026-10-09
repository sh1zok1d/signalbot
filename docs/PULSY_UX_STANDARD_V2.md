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
| **L1** | summary | Current observations only, as words from frozen rules (§4, §5). One header with the live price and the as-of time. | Any **historical number**: no percent of history, no «× обычного», no N, no chance, no interval. |
| **L2** | «Почему так?» | A few short explanations, one per L1 line. Each states the rule that put the line there. It may name the rule's own definition («верхние 5% за 30 дней»), with the numbers taken from config. | New observations that are not on L1. Measured historical outcomes. |
| **L3** | «Данные» | Numbers, each with its baseline («обычно», the median), N (days or cases) and, for directional history, its interval. | A number without its baseline. A chance without its exact calibration (P1). |

**Example (RU), /btc L1 in a calm state:**
```
BTC 62 480
данные на 14:05 (Киев)

Сейчас ничего заметного.
```

**Example (RU), /btc L3:**
```
Данные

Цена за час: −0,84%
Диапазон за час: 1,12% · обычно 0,49% (медиана 30 дн.)
Объём за час: $1,9 млрд · обычно $905 млн (медиана 30 дн.)
Открытых позиций стало меньше: −0,60% за час
За 24 ч: максимум 113 900, минимум 110 800
Обычный диапазон на 24 ч: 60 230–64 730
```

## 2. Components
- **Header:** bold, one line: «BTC {price}» or the screen's title. The as-of line sits under it («данные на HH:MM (Киев)»).
- **Block:** a group of lines. Blocks are separated by one blank line.
- **Level list** (`/levels`): «Выше:» and «Ниже:», at most 3 levels each, each line being a level card.
- **One shared level card**, used by `/levels`, `/check`, the level push and the brief: «{name} — {price} ({distance})».
  - The name comes from the level's data (`decision_format.level_name` on its member kind), never from free text.
  - P1 adds the card's chance line, with its exact calibration.
- **Notification frame:** emoji and a bold title, a blank line, at most 4 lines, and at most one row of buttons.
- **Navigation:** L1 has «Почему так?» and «Данные»; L2 and L3 have «← Назад». Callbacks have the form `ux:<screen>:<level>`.

## 3. Telegram format
- **HTML only:** `<b>` for the header; every other line is escaped text. No tables, no monospace, no Markdown.
- **Spacing:** blank lines between blocks, never inside one.
- **Fixed emoji set:** 📍 level, 🗓 calendar, ⚡ sharp move, 🕐 unusual hour, ☀️ brief. No other emoji.
- **Numbers:** thousands are separated by a **narrow no-break space** (U+202F) in RU. Number and unit are joined by a **no-break space** (U+00A0). Signs use the true minus «−».
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
| — | `nothing` | None fires: «Сейчас ничего заметного.» |

**The corridor** is not on /btc L1, except for that one `corridor_edge` line. Its numbers are on L3. Accuracy appears only on L3, and only as the exact comparison (P1).

## 5. Phrase dictionary (`beta/ux/phrases.py`, authoritative)
Every user-visible phrase, with its formal predicate. A test keeps this table equal to the code.

| Key | RU | EN | Allowed when |
|---|---|---|---|
| `hdr_btc` | BTC {price} | BTC {price} | decision block available: its live price |
| `hdr_btc_na` | BTC | BTC | no fresh price (decision block unavailable) |
| `hdr_levels` | Уровни BTC | BTC levels | always |
| `hdr_why` | Почему так | Why | L2 of the screen |
| `hdr_data` | Данные | Data | L3 of the screen |
| `asof` | данные на {clock} (Киев) | data as of {clock} (Kyiv) | view.data_through |
| `l1_stale` | Данные не обновляются — показываю последнее, что есть. | Data is not updating — showing the last known state. | product status DATA STALE or DATA DEGRADED (fail-closed), or decision reason DATA_STALE |
| `l1_episode` | Сейчас: {name}. | Now: {name}. | an active episode in state TRIGGERED (detector) |
| `l1_level_at` | Цена у уровня: {name} {edge}. | Price is at a level: {name} {edge}. | decision.levels.at is set (price inside a merged level zone, levels.ZONE_TOL_PCT) |
| `l1_range_high` | Цена ходит шире обычного для этого часа. | Price swings wider than usual for this hour. | 1h range rank >= context.label_high (0.95), tier mature |
| `l1_range_extreme` | Цена ходит намного шире обычного для этого часа. | Price swings far wider than usual for this hour. | 1h range rank >= context.label_extreme (0.99), tier mature |
| `l1_volume_high` | Объём выше обычного для этого часа. | Volume is higher than usual for this hour. | 1h volume rank >= context.label_high (0.95), tier mature |
| `l1_event_today` | Сегодня {clock} — {event}. | Today {clock} — {event}. | the next calendar event (CPI/FOMC) is within 24 h of the view |
| `l1_corridor_edge` | Цена у края обычного суточного диапазона. | Price is near the edge of the usual daily range. | price within CORRIDOR_EDGE_SHARE (0.10) of the 24h half-width from a 24h corridor bound |
| `l1_nothing` | Сейчас ничего заметного. | Nothing notable right now. | no SALIENCE rule fires |
| `l2_stale` | Последние данные старше допустимого; цифры могут не совпадать с рынком. | The latest data is older than allowed; numbers may lag the market. | l1_stale |
| `l2_episode` | Это событие детектора: условия правила выполнены сейчас, без прогноза. | A detector event: the rule's conditions hold now; it is not a forecast. | l1_episode |
| `l2_level_at` | Уровень взят из данных: {name}. Расстояние до него меньше ширины зоны уровня. | The level comes from the data: {name}. The price is inside the level's zone. | l1_level_at |
| `l2_range` | Диапазон последнего часа — в верхних {top}% этого часа суток за {days} дней. | The last hour's range is in the top {top}% for this hour of day over {days} days. | l1_range_high |
| `l2_range_extreme` | Диапазон последнего часа — в верхних {top}% этого часа суток за {days} дней. | The last hour's range is in the top {top}% for this hour of day over {days} days. | l1_range_extreme |
| `l2_volume` | Объём последнего часа — в верхних {top}% этого часа суток за {days} дней. | The last hour's volume is in the top {top}% for this hour of day over {days} days. | l1_volume_high |
| `l2_event` | Это время из календаря; движение вокруг таких публикаций обычно шире. | The time comes from the calendar; moves around such releases are usually wider. | l1_event_today |
| `l2_corridor_edge` | Обычный суточный диапазон — коридор, в который цена попадала в {cov}% дней на истории. | The usual daily range is the corridor the price stayed inside on {cov}% of days in history. | l1_corridor_edge |
| `l2_nothing` | Ни одно правило заметности не сработало: диапазон и объём обычные, цена не у уровня. | No salience rule fired: range and volume are usual, the price is not at a level. | l1_nothing |
| `l3_price_1h` | Цена за час: {pct} | Price over 1h: {pct} | horizons.1h.price_move_pct |
| `l3_range_1h` | Диапазон за час: {val} · обычно {base} (медиана {n} дн.) | 1h range: {val} · usually {base} (median of {n} days) | horizons.1h.range_width_pct and baseline_median.range_width_pct_median, baseline_days |
| `l3_volume_1h` | Объём за час: {val} · обычно {base} (медиана {n} дн.) | 1h volume: {val} · usually {base} (median of {n} days) | horizons.1h.volume_notional_usd and baseline_median.volume_notional_usd_sum, baseline_days |
| `l3_oi_down` | Открытых позиций стало меньше: {pct} за час | Open positions decreased: {pct} over 1h | horizons.1h.oi_change_pct < 0 |
| `l3_oi_up` | Открытых позиций стало больше: {pct} за час | Open positions increased: {pct} over 1h | horizons.1h.oi_change_pct > 0 |
| `l3_hilo_24h` | За 24 ч: максимум {high}, минимум {low} | 24h: high {high}, low {low} | horizons.24h.high / low (price_complete) |
| `l3_corridor` | Обычный диапазон на 24 ч: {lower}–{upper} | Usual 24h range: {lower}–{upper} | decision.corridor.horizons.24h lower / upper |
| `lv_card` | {name} — {edge} ({dist}) | {name} — {edge} ({dist}) | a decision level zone: name from its first member (decision_format.level_name), edge, distance_pct |
| `lv_above` | Выше: | Above: | decision.levels.above non-empty |
| `lv_below` | Ниже: | Below: | decision.levels.below non-empty |
| `lv_none` | Уровней рядом нет. | No levels nearby. | both sides empty |
| `nt_hour` | Необычный час: {span} | Unusual hour: {span} | a TRIGGERED unusual-hour push (hour gate qualified) |
| `nt_hour_range` | Цена ходила шире обычного. | Price swung wider than usual. | gate.passed.range |
| `nt_hour_volume` | Объём выше обычного. | Volume was higher than usual. | gate.passed.volume |
| `nt_hour_price` | Цена за час: {pct} | Price over the hour: {pct} | gate.values.price_move_pct |
| `nt_level` | Касание уровня: {name} {level} | Level touch: {name} {level} | a market alert of kind level (first touch of its period, market_alerts) |
| `nt_level_price` | Цена {price} в {clock} (Киев). | Price {price} at {clock} (Kyiv). | payload.price, payload.at |
| `nt_move` | Резкое движение: {pct} за 15 минут | Sharp move: {pct} in 15 minutes | a market alert of kind move (\|15m move\| over the 1h scale threshold, market_alerts.detect_move) |
| `nt_move_span` | {start}–{end} (Киев): {open} → {close} | {start}–{end} (Kyiv): {open} → {close} | payload.start/at, open/close |
| `nt_brief` | Сводка за {hours} ч | Summary of the last {hours} h | the morning brief (catchup view) |
| `nt_brief_move` | Цена за {hours} ч: {pct}, диапазон {low}–{high} | Price over {hours} h: {pct}, range {low}–{high} | market.window price_move_pct, low, high (price_complete) |
| `btn_why` | Почему так? | Why? | L1 → L2 |
| `btn_data` | Данные | Data | L1/L2 → L3 |
| `btn_levels` | Уровни | Levels | → /levels L1 |
| `btn_back` | ← Назад | ← Back | L2/L3 → the level above |

## 6. The owner's rules, each mapped to a test (`tests/beta/test_pulsy_ux_v2.py`)

| Rule | Meaning | Test |
|---|---|---|
| **A** compact | L1 within its maximum and at most `L1_MAX` (3) salient lines | `test_rule_A_l1_is_compact` |
| **B** compact L2 | L2 within its maximum; one short line per L1 line | `test_rule_B_l2_is_compact` |
| **C** exact historical meaning | No «пробой / закрепление / удержался» for "the price an hour later was above the level". An OI decline is «открытых позиций стало меньше». Directional history keeps its baseline, N and interval on L3. | `test_rule_C_exact_historical_meaning` |
| **D** every number backed | L3 numbers equal the facts and today's render. A chance appears only with its exact calibration (P1). Level names come from the data, so a weekly low cannot be labelled a weekly high. | `test_rule_D_l3_numbers_equal_the_facts_and_todays_render`, `test_rule_D_level_names_come_from_the_data` |
| **E** formatting | Valid Telegram HTML, no-break spaces in numbers, emoji from the fixed set, buttons ≤ 2×3, callback ≤ 64 bytes | `test_rule_E_telegram_format` |
| **F** no drama | No «обвал / взрыв / паника / ракета», no «!!» | `test_rule_F_no_drama` |
| **G** lively words only by rule | Every phrase has a predicate; the renderer prints only dictionary phrases and fact values | `test_rule_G_every_phrase_has_a_rule` |

Also tested:
- no historical number on L1;
- the RU/EN pairs are complete;
- `assert_descriptive` (the trade-call lint) holds on every render;
- the length maxima;
- «ничего заметного» for a calm state;
- facts equivalence;
- the flag is off.

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
