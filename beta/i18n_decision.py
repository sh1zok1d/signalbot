"""User-facing strings of decision support (PRODUCT_DECISION_V2), merged into beta.i18n.

Rules (PRODUCT_DECISION_V2 §3): numbers come with N and "обычно"; forecasts with their
coverage; never a direct trade call (buy / sell / long now / short now / entry / target).
"""
from __future__ import annotations

LEVEL_NAMES = {
    "PDH": ("максимум вчера", "yesterday's high"),
    "PDL": ("минимум вчера", "yesterday's low"),
    "PWH": ("максимум прошлой недели", "last week's high"),
    "PWL": ("минимум прошлой недели", "last week's low"),
    "PMH": ("максимум прошлого месяца", "last month's high"),
    "PML": ("минимум прошлого месяца", "last month's low"),
    "DO": ("открытие дня", "day open"),
    "WO": ("открытие недели", "week open"),
    "MO": ("открытие месяца", "month open"),
    "ASIA_H": ("максимум Азии", "Asia high"),
    "ASIA_L": ("минимум Азии", "Asia low"),
    "EU_H": ("максимум Европы", "Europe high"),
    "EU_L": ("минимум Европы", "Europe low"),
    "US_H": ("максимум США", "US high"),
    "US_L": ("минимум США", "US low"),
    "VWAP_D": ("VWAP дня", "day VWAP"),
    "POC_PD": ("объёмный центр вчера", "yesterday's volume POC"),
    "ROUND": ("круглый уровень", "round number"),
    "ROUND_MAJOR": ("крупный круглый уровень", "major round number"),
    "LIQ_LONG": ("ликвидации лонгов {usd}", "long liquidations {usd}"),
    "LIQ_SHORT": ("ликвидации шортов {usd}", "short liquidations {usd}"),
}

EVENT_NAMES = {
    "CPI": ("CPI США (инфляция)", "US CPI (inflation)"),
    "FOMC": ("решение ФРС (FOMC)", "Fed decision (FOMC)"),
    "NFP": ("NFP США (занятость)", "US NFP (jobs)"),
    "PCE": ("PCE США (инфляция)", "US PCE (inflation)"),
    "EXPIRY_MONTHLY": ("месячная экспирация опционов Deribit", "Deribit monthly options expiry"),
    "EXPIRY_QUARTERLY": ("квартальная экспирация опционов Deribit", "Deribit quarterly options expiry"),
    "EXPIRY_WEEKLY": ("недельная экспирация опционов Deribit", "Deribit weekly options expiry"),
    "FUNDING": ("funding Binance", "Binance funding"),
}

WEEKDAYS = {"ru": ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"), "en": ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")}


def _pair(ru: str, en: str) -> dict:
    return {"ru": ru, "en": en}


DECISION_CATALOG: dict = {
    # ---- shared blocks (briefing, /catchup, /btc) ----
    "dc_corridor_head": _pair("<b>Коридор</b> (Binance; в 4 из 5 похожих случаев цена не выходила за него)",
                              "<b>Corridor</b> (Binance; in 4 of 5 similar cases the price stayed inside)"),
    "dc_corridor_line": _pair("{parts}", "{parts}"),
    "dc_corridor_part": _pair("{h}: {low}–{high} (±{half})", "{h}: {low}–{high} (±{half})"),
    "dc_corridor_event": _pair(" · в окне — {event}", " · includes {event}"),
    "dc_levels_head": _pair("<b>Уровни</b> (шанс дойти за 24ч)", "<b>Levels</b> (chance to reach within 24h)"),
    "dc_level_line": _pair("{arrow} {price} — {name} · {dist} · {p}", "{arrow} {price} — {name} · {dist} · {p}"),
    "dc_level_at": _pair("Цена у уровня {price} — {name}", "Price is at {price} — {name}"),
    "dc_level_now": _pair("— сейчас {price} —", "— now {price} —"),
    "dc_today_head": _pair("<b>Сегодня</b>", "<b>Today</b>"),
    "dc_event_line": _pair("{when} — {name}{size}", "{when} — {name}{size}"),
    "dc_event_size": _pair(": час выхода обычно ×{hour}, день ×{day} ({n})",
                           ": the release hour is usually ×{hour}, the day ×{day} ({n})"),
    "dc_event_size_plain": _pair(": час ×{hour}, день ×{day} ({n}) — почти как обычно",
                                 ": hour ×{hour}, day ×{day} ({n}) — close to usual"),
    "dc_no_events": _pair("Крупных событий в ближайшие 24ч нет.", "No major scheduled events in the next 24h."),
    "dc_analog_line": _pair("↳ после похожих ({n}): через {h} выше в {p_up} (обычно {base_up}) — {dir_verdict}; "
                            "ход ×{ratio} — {range_verdict}",
                            "↳ after similar ({n}): {h} later higher in {p_up} (usually {base_up}) — {dir_verdict}; "
                            "move ×{ratio} — {range_verdict}"),
    "dc_analog_short": _pair("↳ после похожих: мало данных ({n})", "↳ after similar: too little data ({n})"),
    "dc_dir_as_usual": _pair("как обычно", "as usual"),
    "dc_dir_higher": _pair("чаще выше обычного", "higher more often than usual"),
    "dc_dir_lower": _pair("чаще ниже обычного", "lower more often than usual"),
    "dc_range_as_usual": _pair("как обычно", "as usual"),
    "dc_range_bigger": _pair("больше обычного", "bigger than usual"),
    "dc_range_smaller": _pair("меньше обычного", "smaller than usual"),
    "dc_insufficient": _pair("мало данных", "too little data"),
    "dc_unavailable": _pair("Коридор и уровни сейчас не показываем: {reason}.",
                            "Corridor and levels are not shown now: {reason}."),
    "dc_reason_stale": _pair("данные Binance отстают", "Binance data is late"),
    "dc_reason_no_stats": _pair("история ещё не загружена", "history is not loaded yet"),
    "dc_reason_error": _pair("техническая ошибка", "a technical error"),
    "dc_btc_corridor": _pair("Коридор 4ч: {low}–{high} (±{half})", "4h corridor: {low}–{high} (±{half})"),
    "dc_btc_levels": _pair("Уровни: {parts}", "Levels: {parts}"),
    "dc_btc_level_part": _pair("{arrow} {price} {name} ({dist})", "{arrow} {price} {name} ({dist})"),
    "btn_levels": _pair("Уровни", "Levels"),
    "btn_risk": _pair("Риск", "Risk"),
    # ---- /levels ----
    "lv_title": _pair("<b>Уровни BTC</b> · Binance · цена {price} · {clock}",
                      "<b>BTC levels</b> · Binance · price {price} · {clock}"),
    "lv_above": _pair("<b>Выше</b>", "<b>Above</b>"),
    "lv_below": _pair("<b>Ниже</b>", "<b>Below</b>"),
    "lv_none": _pair("— рядом нет", "— none nearby"),
    "lv_zone": _pair("{price} — {names} ({dist})", "{price} — {names} ({dist})"),
    "lv_touch": _pair("   дойти: за 4ч {p4}, за 24ч {p24}", "   reach: within 4h {p4}, within 24h {p24}"),
    "lv_hist": _pair("   после первого касания ({n}): через 1ч цена {side} уровня в {hold} — у случайного уровня {ctrl}, {verdict}",
                     "   after the first touch ({n}): 1h later the price was {side} the level in {hold} — a random level: {ctrl}, {verdict}"),
    "lv_side_above": _pair("выше", "above"),
    "lv_side_below": _pair("ниже", "below"),
    "lv_hist_move": _pair("   обычно дальше {further}, обратно {back} за 1ч",
                          "   typically {further} further, {back} back within 1h"),
    "lv_verdict_as_usual": _pair("как обычно", "as usual"),
    "lv_verdict_differs_more": _pair("чаще обычного", "more often than usual"),
    "lv_verdict_differs_less": _pair("реже обычного", "less often than usual"),
    "lv_verdict_insufficient": _pair("мало данных", "too little data"),
    "lv_corridor": _pair("Коридор 24ч: {low}–{high}", "24h corridor: {low}–{high}"),
    "lv_footer": _pair("День, неделя и месяц — по UTC, как дневная свеча на бирже. История — Binance с 2020 года.",
                       "Day, week and month are UTC, like the exchange's daily candle. History: Binance since 2020."),
    # ---- /risk ----
    "rk_title": _pair("<b>Риск BTC</b> · Binance · цена {price}", "<b>BTC risk</b> · Binance · price {price}"),
    "rk_stop": _pair("Стоп {pct} (≈ {usd}) против позиции, как часто цена доходила до него:",
                     "A stop {pct} (≈ {usd}) away, how often the price reached it:"),
    "rk_line": _pair("за {h} — в {p}", "within {h} — {p}"),
    "rk_typical": _pair("Обычный ход: 1ч ±{h1}, 4ч ±{h4}, 24ч ±{h24}", "Typical move: 1h ±{h1}, 4h ±{h4}, 24h ±{h24}"),
    "rk_table_head": _pair("Как часто цена проходила такое расстояние в одну сторону:",
                           "How often the price moved this far in one direction:"),
    "rk_table_line": _pair("{pct}: 1ч {p1} · 4ч {p4} · 24ч {p24}", "{pct}: 1h {p1} · 4h {p4} · 24h {p24}"),
    "rk_note": _pair("Одинаково для лонга и шорта: направление модель не предсказывает.",
                     "The same for longs and shorts: the model does not forecast direction."),
    "rk_usage": _pair("Стоп в процентах или ценой: /risk 0.5 или /risk 61500",
                      "A stop in percent or as a price: /risk 0.5 or /risk 61500"),
    # ---- /events ----
    "ev_title": _pair("<b>События</b> (время — Киев)", "<b>Events</b> (Kyiv time)"),
    "ev_none": _pair("В ближайшие 14 дней в календаре ничего нет.", "Nothing in the calendar for the next 14 days."),
    "ev_funding": _pair("Funding Binance: {times} (Киев)", "Binance funding: {times} Kyiv"),
    "ev_footer": _pair("Размер — медиана к обычному часу и дню (Binance, с 2020 года).",
                       "Size is the median against a usual hour and day (Binance, since 2020)."),
    # ---- /accuracy ----
    "ac_title": _pair("<b>Точность коридора</b> (доля случаев, когда цена не вышла за коридор; расчётная — 80%)",
                      "<b>Corridor accuracy</b> (share of cases the price stayed inside; designed for 80%)"),
    "ac_holdout": _pair("Проверка на отложенном годе ({period}): {parts}",
                        "Check on a held-out year ({period}): {parts}"),
    "ac_live": _pair("Живые прогнозы за 30 дней: {parts}", "Live forecasts, last 30 days: {parts}"),
    "ac_live_none": _pair("Живые прогнозы ещё не созрели.", "No live forecast has matured yet."),
    "ac_part": _pair("{h} {p}", "{h} {p}"),
    "ac_part_live": _pair("{h} — {p} (из {n})", "{h} — {p} (of {n})"),
    # ---- /alert ----
    "al_set": _pair("Сообщу, когда BTC дойдёт до {price} ({dist} от {now}). За 24ч до такого расстояния цена доходила в {p}.",
                    "I will message you when BTC reaches {price} ({dist} from {now}). Within 24h the price reached such a distance in {p}."),
    "al_set_plain": _pair("Сообщу, когда BTC дойдёт до {price} ({dist} от {now}).",
                          "I will message you when BTC reaches {price} ({dist} from {now})."),
    "al_list_head": _pair("<b>Ваши уровни</b>", "<b>Your price alerts</b>"),
    "al_list_line": _pair("{k}. {price} ({dist})", "{k}. {price} ({dist})"),
    "al_list_none": _pair("Уровней нет. Добавить: /alert 65000", "No alerts. Add one: /alert 65000"),
    "al_list_footer": _pair("Удалить: /alert del 1 · все: /alert del all", "Delete: /alert del 1 · all: /alert del all"),
    "al_deleted": _pair("Удалено: {n}.", "Deleted: {n}."),
    "al_limit": _pair("Уже {n} уровней — это максимум. Удалите лишний: /alert del 1",
                      "Already {n} alerts — the maximum. Delete one: /alert del 1"),
    "al_usage": _pair("Уровень ценой: /alert 65000 · список: /alert · удалить: /alert del 1",
                      "A price: /alert 65000 · list: /alert · delete: /alert del 1"),
    "al_too_close": _pair("Это слишком близко к текущей цене {now}.", "That is too close to the current price {now}."),
    "al_no_price": _pair("Цена Binance сейчас недоступна, попробуйте позже.", "The Binance price is unavailable now; try later."),
    # ---- /push ----
    "push_status": _pair("Сообщения: {master}\n• уровни (первое касание вчерашних, недельных, месячных максимумов и минимумов): {levels}\n"
                         "• события (CPI, ФРС за 30 минут): {events}\n• резкие движения (за 15 минут): {moves}\n"
                         "• необычный час: {hours}\nЛичные уровни (/alert) приходят всегда. "
                         "Утренняя сводка — отдельно: /brief on|off.\n"
                         "Включить или выключить: /push off · /push levels off · /push events on · /push moves off · /push hour off",
                         "Messages: {master}\n• levels (first touch of daily, weekly, monthly highs and lows): {levels}\n"
                         "• events (CPI, Fed, 30 minutes ahead): {events}\n• sharp moves (within 15 minutes): {moves}\n"
                         "• unusual hour: {hours}\nYour own alerts (/alert) always arrive. "
                         "The morning briefing is separate: /brief on|off.\n"
                         "Switch: /push off · /push levels off · /push events on · /push moves off · /push hour off"),
    "push_pref_ok": _pair("Готово. {status}", "Done. {status}"),
    "on_word": _pair("вкл", "on"),
    "off_word": _pair("выкл", "off"),
    # ---- market alert pushes ----
    "pa_level_title": _pair("<b>BTC · {name} {level}</b>", "<b>BTC · {name} {level}</b>"),
    "pa_level_now": _pair("{clock} · цена {price} (Binance) — первое касание за {period}",
                          "{clock} · price {price} (Binance) — first touch this {period}"),
    "pa_period_day": _pair("день", "day"),
    "pa_period_week": _pair("неделю", "week"),
    "pa_period_month": _pair("месяц", "month"),
    "pa_level_hist": _pair("После первого касания ({n}): через 1ч цена {side} уровня в {hold} (у случайного уровня {ctrl}) — {verdict}",
                           "After the first touch ({n}): 1h later the price was {side} the level in {hold} (a random level: {ctrl}) — {verdict}"),
    "pa_level_move": _pair("За 1ч обычно дальше {further}, обратно {back}", "Within 1h typically {further} further, {back} back"),
    "pa_next": _pair("Следующий уровень: {price} — {name} ({dist}), за 24ч доходили в {p}",
                     "Next level: {price} — {name} ({dist}), reached within 24h in {p}"),
    "pa_corridor": _pair("Коридор 4ч: {low}–{high} (±{half})", "4h corridor: {low}–{high} (±{half})"),
    "pa_event_title": _pair("<b>BTC · через {mins} мин {name}</b>", "<b>BTC · {name} in {mins} min</b>"),
    "pa_event_when": _pair("{clock} · цена {price} (Binance)", "{clock} · price {price} (Binance)"),
    "pa_event_size": _pair("Час выхода обычно в {hour}× больше обычного часа, день — в {day}× ({n})",
                           "The release hour is usually {hour}× a usual hour, the day {day}× ({n})"),
    "pa_corridor_1h": _pair("Коридор 1ч с учётом события: {low}–{high} (±{half})",
                            "1h corridor with the event: {low}–{high} (±{half})"),
    "pa_corridor_1h_plain": _pair("Коридор 1ч сейчас: {low}–{high} (±{half})", "1h corridor now: {low}–{high} (±{half})"),
    "pa_move_title": _pair("<b>BTC · резкое движение {pct} за 15 минут</b>", "<b>BTC · sharp move {pct} in 15 minutes</b>"),
    "pa_move_span": _pair("{span} · {open} → {close} (Binance)", "{span} · {open} → {close} (Binance)"),
    "pa_move_rare": _pair("Такой ход за 15 минут бывает примерно раз в {days} дн.",
                          "A 15-minute move like this happens about once every {days} days."),
    "pa_levels_near": _pair("Рядом: {parts}", "Nearby: {parts}"),
    "pa_price_title": _pair("<b>BTC дошёл до вашего уровня {level}</b>", "<b>BTC reached your level {level}</b>"),
    "pa_price_now": _pair("{clock} · цена {price} (Binance)", "{clock} · price {price} (Binance)"),
    "pa_price_footer": _pair("Ваши уровни: /alert", "Your alerts: /alert"),
    "n_cases": _pair("{n} {word}", "{n} {word}"),
    "since_year": _pair("с {year}", "since {year}"),
}

DECISION_HELP = {
    "ru": (
        "<b>Signalbot, закрытая бета — BTCUSDT perpetual (Binance, Bybit, OKX)</b>\n"
        "Бот не говорит, покупать или продавать. Он показывает, насколько сейчас рискованно, где "
        "уровни, которые видит весь рынок, что было в похожих ситуациях раньше и что сегодня "
        "в календаре. Рядом с каждой цифрой — сколько было случаев и как бывает обычно.\n\n"
        "/btc — состояние BTC сейчас\n"
        "/catchup — что было за последние часы (по умолчанию 8 ч; /catchup 1–24)\n"
        "/levels — уровни: расстояние, шанс дойти, что было при касании\n"
        "/risk 0.5 — как часто цена проходит такой стоп против позиции\n"
        "/alert 65000 — сообщить, когда цена дойдёт (/alert — список)\n"
        "/events — события: CPI, ФРС, экспирации\n"
        "/accuracy — насколько точен коридор\n"
        "/brief on|off — утренняя сводка в 08:00 (Киев)\n"
        "/push — какие сообщения присылать\n"
        "/history — недавние эпизоды детектора\n"
        "/terms — термины · /lang — язык сообщений · /feedback — отзыв\n"
        "/stop — пауза · /delete_me — удалить ваши данные"
    ),
    "en": (
        "<b>Signalbot closed beta — BTCUSDT perpetual (Binance, Bybit, OKX)</b>\n"
        "The bot never says whether to buy or sell. It shows how risky the market is now, where the "
        "levels everyone watches are, what happened in similar situations before and what is in "
        "today's calendar. Every number comes with how many cases there were and what is usual.\n\n"
        "/btc — BTC right now\n"
        "/catchup — the last hours (default 8h; /catchup 1–24)\n"
        "/levels — levels: distance, chance to reach, what happened at the touch\n"
        "/risk 0.5 — how often the price moves this far against a position\n"
        "/alert 65000 — message me when the price gets there (/alert — list)\n"
        "/events — CPI, Fed, options expiries\n"
        "/accuracy — how accurate the corridor is\n"
        "/brief on|off — morning briefing at 08:00 Kyiv\n"
        "/push — which messages to receive\n"
        "/history — recent detector episodes\n"
        "/terms — terms · /lang — message language · /feedback — feedback\n"
        "/stop — pause · /delete_me — delete your data"
    ),
}

DECISION_TERMS = {
    "ru": (
        "\n\nРЕШЕНИЯ И ИСТОРИЯ\n"
        "Коридор — диапазон, в котором цена оставалась в 4 из 5 похожих случаев за 1ч, 4ч или 24ч. "
        "Считается по Binance с 2020 года: недавняя волатильность, время суток, выходные и события (CPI, ФРС). "
        "Точность проверяется на отложенном годе и на живых прогнозах (/accuracy).\n"
        "Шанс дойти — как часто цена проходила такое расстояние в одну сторону за это время в похожих условиях. "
        "Направление модель не предсказывает: для роста и падения шанс одинаковый.\n"
        "Уровни — только те, что видит весь рынок: максимумы и минимумы вчера, прошлой недели и месяца, "
        "открытия дня, недели и месяца, сессии Азии, Европы и США, VWAP дня, объёмный центр вчера, круглые уровни, "
        "места крупных ликвидаций за 24ч. День, неделя и месяц — по UTC.\n"
        "Случайный уровень — уровень на том же расстоянии от открытия периода, но без смысла. Если реальный уровень "
        "ведёт себя как случайный, бот так и пишет: как обычно.\n"
        "После похожих — что было после таких же состояний 1ч / 4ч в истории Binance. Обычно — все часы с той же "
        "волатильностью. «Отличается» — только если разница проходит проверку на случайность с поправкой на "
        "число проверок.\n"
        "Прошлое не гарантирует будущего. Бот не говорит, что делать со сделкой."
    ),
    "en": (
        "\n\nDECISIONS AND HISTORY\n"
        "Corridor — the range the price stayed in in 4 of 5 similar cases over 1h, 4h or 24h. "
        "Built on Binance since 2020: recent volatility, time of day, weekends and events (CPI, Fed). "
        "Accuracy is checked on a held-out year and on live forecasts (/accuracy).\n"
        "Chance to reach — how often the price moved that far in one direction within that time in similar conditions. "
        "The model does not forecast direction: the chance is the same up and down.\n"
        "Levels — only what the whole market sees: yesterday's, last week's and last month's highs and lows, "
        "day, week and month opens, Asia, Europe and US sessions, the day VWAP, yesterday's volume POC, round numbers, "
        "places of large liquidations in 24h. Day, week and month are UTC.\n"
        "Random level — a level at the same distance from the period open that means nothing. If a real level behaves "
        "like a random one, the bot says so: as usual.\n"
        "After similar — what followed the same 1h / 4h states in Binance history. Usual — all hours with the same "
        "volatility. 'Differs' only when the difference passes a randomness test corrected for the number of tests.\n"
        "The past does not guarantee the future. The bot does not tell you what to do with a trade."
    ),
}


def plural_ru(n: int, one: str, few: str, many: str) -> str:
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def cases_word(n: int, lang: str) -> str:
    if lang == "ru":
        return plural_ru(n, "случай", "случая", "случаев")
    return "case" if n == 1 else "cases"
