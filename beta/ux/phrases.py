"""Pulsy UX V2 phrase dictionary (docs/PULSY_UX_STANDARD_V2.md §5). Every user-visible phrase lives here
with its RU and EN text and the formal predicate that allows it, written against existing labels, bands,
verdicts or thresholds. A screen prints nothing that is not a key here (rule G). Historical meaning is
exact (rule C): no «пробой / закрепление / удержался»; an OI decline is «открытых позиций стало меньше»."""
from __future__ import annotations

# key: (ru, en, predicate). The predicate is documentation and the test oracle, not code.
PHRASES = {
    # ---- headers ------------------------------------------------------------------------------
    "hdr_btc": ("BTC {price}", "BTC {price}", "decision block available: its live price"),
    "hdr_btc_na": ("BTC", "BTC", "no fresh price (decision block unavailable)"),
    "hdr_levels": ("Уровни BTC", "BTC levels", "always"),
    "hdr_why": ("Почему так", "Why", "L2 of the screen"),
    "hdr_data": ("Данные", "Data", "L3 of the screen"),
    "asof": ("данные на {clock} (Киев)", "data as of {clock} (Kyiv)", "view.data_through"),
    # ---- L1 salient lines (select.SALIENCE), current observations only, no historical number --
    "l1_stale": ("Данные не обновляются — показываю последнее, что есть.",
                 "Data is not updating — showing the last known state.",
                 "product status DATA STALE or DATA DEGRADED (fail-closed), or decision reason DATA_STALE"),
    "l1_episode": ("Сейчас: {name}.", "Now: {name}.", "an active episode in state TRIGGERED (detector)"),
    "l1_level_at": ("Цена у уровня: {name} {edge}.", "Price is at a level: {name} {edge}.",
                    "decision.levels.at is set (price inside a merged level zone, levels.ZONE_TOL_PCT)"),
    "l1_range_high": ("Цена ходит шире обычного для этого часа.", "Price swings wider than usual for this hour.",
                      "1h range rank >= context.label_high (0.95), tier mature"),
    "l1_range_extreme": ("Цена ходит намного шире обычного для этого часа.",
                         "Price swings far wider than usual for this hour.",
                         "1h range rank >= context.label_extreme (0.99), tier mature"),
    "l1_volume_high": ("Объём выше обычного для этого часа.", "Volume is higher than usual for this hour.",
                       "1h volume rank >= context.label_high (0.95), tier mature"),
    "l1_event_today": ("Сегодня {clock} — {event}.", "Today {clock} — {event}.",
                       "the next calendar event (CPI/FOMC) is within 24 h of the view"),
    "l1_corridor_edge": ("Цена у края обычного суточного диапазона.", "Price is near the edge of the usual daily range.",
                         "price within CORRIDOR_EDGE_SHARE (0.10) of the 24h half-width from a 24h corridor bound"),
    "l1_nothing": ("Сейчас ничего заметного.", "Nothing notable right now.", "no SALIENCE rule fires"),
    # ---- L2 explanations (short, no historical number beyond the rule's own definition) -------
    "l2_stale": ("Последние данные старше допустимого; цифры могут не совпадать с рынком.",
                 "The latest data is older than allowed; numbers may lag the market.", "l1_stale"),
    "l2_episode": ("Это событие детектора: условия правила выполнены сейчас, без прогноза.",
                   "A detector event: the rule's conditions hold now; it is not a forecast.", "l1_episode"),
    "l2_level_at": ("Уровень взят из данных: {name}. Расстояние до него меньше ширины зоны уровня.",
                    "The level comes from the data: {name}. The price is inside the level's zone.", "l1_level_at"),
    "l2_range": ("Диапазон последнего часа — в верхних {top}% этого часа суток за {days} дней.",
                 "The last hour's range is in the top {top}% for this hour of day over {days} days.", "l1_range_high"),
    "l2_range_extreme": ("Диапазон последнего часа — в верхних {top}% этого часа суток за {days} дней.",
                         "The last hour's range is in the top {top}% for this hour of day over {days} days.", "l1_range_extreme"),
    "l2_volume": ("Объём последнего часа — в верхних {top}% этого часа суток за {days} дней.",
                  "The last hour's volume is in the top {top}% for this hour of day over {days} days.", "l1_volume_high"),
    "l2_event": ("Это время из календаря; движение вокруг таких публикаций обычно шире.",
                 "The time comes from the calendar; moves around such releases are usually wider.", "l1_event_today"),
    "l2_corridor_edge": ("Обычный суточный диапазон — коридор, в который цена попадала в {cov}% дней на истории.",
                         "The usual daily range is the corridor the price stayed inside on {cov}% of days in history.",
                         "l1_corridor_edge"),
    "l2_nothing": ("Ни одно правило заметности не сработало: диапазон и объём обычные, цена не у уровня.",
                   "No salience rule fired: range and volume are usual, the price is not at a level.", "l1_nothing"),
    # ---- L3 data lines: numbers with baseline, N and interval -------------------------------
    "l3_price_1h": ("Цена за час: {pct}", "Price over 1h: {pct}", "horizons.1h.price_move_pct"),
    "l3_range_1h": ("Диапазон за час: {val} · обычно {base} (медиана {n} дн.)",
                    "1h range: {val} · usually {base} (median of {n} days)",
                    "horizons.1h.range_width_pct and baseline_median.range_width_pct_median, baseline_days"),
    "l3_volume_1h": ("Объём за час: {val} · обычно {base} (медиана {n} дн.)",
                     "1h volume: {val} · usually {base} (median of {n} days)",
                     "horizons.1h.volume_notional_usd and baseline_median.volume_notional_usd_sum, baseline_days"),
    "l3_oi_down": ("Открытых позиций стало меньше: {pct} за час", "Open positions decreased: {pct} over 1h",
                   "horizons.1h.oi_change_pct < 0"),
    "l3_oi_up": ("Открытых позиций стало больше: {pct} за час", "Open positions increased: {pct} over 1h",
                 "horizons.1h.oi_change_pct > 0"),
    "l3_hilo_24h": ("За 24 ч: максимум {high}, минимум {low}", "24h: high {high}, low {low}",
                    "horizons.24h.high / low (price_complete)"),
    "l3_corridor": ("Обычный диапазон на 24 ч: {lower}–{upper}", "Usual 24h range: {lower}–{upper}",
                    "decision.corridor.horizons.24h lower / upper"),
    # ---- levels ------------------------------------------------------------------------------
    "lv_card": ("{name} — {edge} ({dist})", "{name} — {edge} ({dist})",
                "a decision level zone: name from its first member (decision_format.level_name), edge, distance_pct"),
    "lv_above": ("Выше:", "Above:", "decision.levels.above non-empty"),
    "lv_below": ("Ниже:", "Below:", "decision.levels.below non-empty"),
    "lv_none": ("Уровней рядом нет.", "No levels nearby.", "both sides empty"),
    # ---- notifications -----------------------------------------------------------------------
    "nt_hour": ("Необычный час: {span}", "Unusual hour: {span}", "a TRIGGERED unusual-hour push (hour gate qualified)"),
    "nt_hour_range": ("Цена ходила шире обычного.", "Price swung wider than usual.", "gate.passed.range"),
    "nt_hour_volume": ("Объём выше обычного.", "Volume was higher than usual.", "gate.passed.volume"),
    "nt_hour_price": ("Цена за час: {pct}", "Price over the hour: {pct}", "gate.values.price_move_pct"),
    "nt_level": ("Касание уровня: {name} {level}", "Level touch: {name} {level}",
                 "a market alert of kind level (first touch of its period, market_alerts)"),
    "nt_level_price": ("Цена {price} в {clock} (Киев).", "Price {price} at {clock} (Kyiv).", "payload.price, payload.at"),
    "nt_move": ("Резкое движение: {pct} за 15 минут", "Sharp move: {pct} in 15 minutes",
                "a market alert of kind move (|15m move| over the 1h scale threshold, market_alerts.detect_move)"),
    "nt_move_span": ("{start}–{end} (Киев): {open} → {close}", "{start}–{end} (Kyiv): {open} → {close}",
                     "payload.start/at, open/close"),
    "nt_brief": ("Сводка за {hours} ч", "Summary of the last {hours} h", "the morning brief (catchup view)"),
    "nt_brief_move": ("Цена за {hours} ч: {pct}, диапазон {low}–{high}", "Price over {hours} h: {pct}, range {low}–{high}",
                      "market.window price_move_pct, low, high (price_complete)"),
    # ---- navigation --------------------------------------------------------------------------
    "btn_why": ("Почему так?", "Why?", "L1 → L2"),
    "btn_data": ("Данные", "Data", "L1/L2 → L3"),
    "btn_levels": ("Уровни", "Levels", "→ /levels L1"),
    "btn_back": ("← Назад", "← Back", "L2/L3 → the level above"),
}

# words that never appear in any phrase (rules C and F)
FORBIDDEN = ("пробой", "пробил", "закреп", "удержал", "обвал", "взрыв", "паник", "ракет", "breakout", "broke out",
             "held above", "held below", "crash", "explod", "panic", "moon", "🚀", "!!")
EMOJI = ("📍", "🗓", "⚡", "🕐", "☀️")


def text(key: str, lang: str, **kw) -> str:
    ru, en, _rule = PHRASES[key]
    return (ru if lang == "ru" else en).format(**kw)
