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
    # event zone (BETA_EVENT_CORRIDOR_TEMPORAL_REPAIR_DESIGN_V1 §9): numbers are withheld on purpose
    "ez_note": _pair("{hs}: числовую оценку не показываем — {events} {zone}. Вокруг публикации обычная калибровка "
                     "коридора не применяется.",
                     "{hs}: no numerical estimate — {events} ({zone}). Around the release, the usual corridor "
                     "calibration does not apply."),
    "ez_event": _pair("{name}, {when}", "{name}, {when}"),
    "ez_event_note": _pair("Числовой коридор на это время не показываем: вокруг публикации обычная калибровка "
                           "коридора не применяется.",
                           "No numerical corridor for this time: around the release, the usual corridor "
                           "calibration does not apply."),
    "dc_level_at": _pair("Цена у уровня {price} — {name}", "Price is at {price} — {name}"),
    "dc_level_now": _pair("— сейчас {price} —", "— now {price} —"),
    "dc_event_line": _pair("{when} — {name}", "{when} — {name}"),
    "dc_no_events": _pair("Крупных событий в ближайшие сутки нет.", "No major scheduled events within 24 hours."),
    # L2 in the quantitative format (EVIDENCE_AND_CLAIMS_DECISION_V1 §4): observed, baseline, the
    # difference and its interval; no verdict words
    "dc_analog_line": _pair("↳ после похожих ({n}): через {h} выше в {p_up} против {base_up} обычно ({diff} п.п.{ci}); "
                            "ход ×{ratio} к обычному{rci}",
                            "↳ after similar ({n}): {h} later higher in {p_up} vs {base_up} usually ({diff} pp{ci}); "
                            "move ×{ratio} of usual{rci}"),
    "dc_pp_ci": _pair("; 95% интервал {lo}…{hi}", "; 95% interval {lo}…{hi}"),
    "dc_ratio_ci": _pair(" (95% интервал ×{lo}…×{hi})", " (95% interval ×{lo}…×{hi})"),
    "dc_analog_short": _pair("↳ после похожих: мало данных ({n})", "↳ after similar: too little data ({n})"),
    "dc_analog_fewdays": _pair("↳ после похожих: мало разных дней ({n} за {d} дн.)",
                               "↳ after similar: too few distinct days ({n} over {d} days)"),
    "dc_analog_noci": _pair("↳ после похожих: интервал ещё не посчитан ({n})",
                            "↳ after similar: no interval computed yet ({n})"),
    "dc_unavailable": _pair("Коридор и уровни сейчас не показываем: {reason}.",
                            "Corridor and levels are not shown now: {reason}."),
    "dc_reason_stale": _pair("данные Binance отстают", "Binance data is late"),
    "dc_reason_no_stats": _pair("история ещё не загружена", "history is not loaded yet"),
    "dc_reason_stats_stale": _pair("статистика по истории не обновлялась больше 3 суток",
                                   "the history statistics have not been updated for over 3 days"),
    "dc_reason_data_late": _pair("данные отстают", "the data is late"),
    "dc_stats_built": _pair("Статистика по истории собрана {when} {zone}.", "History statistics built {when} {zone}."),
    "dc_reason_error": _pair("техническая ошибка", "a technical error"),
    # /btc (backlog C1): three corridors, their record, the two nearest levels with the «B» chance, the next 24h
    "dc_btc_corridor": _pair("Коридор: {parts}", "Corridor: {parts}"),
    "dc_btc_corridor_part": _pair("{h} {low}–{high}", "{h} {low}–{high}"),
    "dc_btc_track": _pair("↳ внутри коридора бывало (расчёт — {share}): {parts}",
                          "↳ inside the corridor (designed for {share}): {parts}"),
    "dc_btc_track_live": _pair("{h} {p} вживую за 30 дн. (N={n})", "{h} {p} live over 30 days (N={n})"),
    "dc_btc_track_hold": _pair("{parts} на истории ({days} дн.)", "{parts} on history ({days} days)"),
    "dc_btc_track_part": _pair("{h} {p}", "{h} {p}"),
    "dc_btc_level": _pair("{arrow} {price} {name} ({dist})", "{arrow} {price} {name} ({dist})"),
    "dc_btc_level_at": _pair("цена у {price} {name}", "price at {price} {name}"),
    "dc_btc_level_b": _pair("{arrow} {price} {name} ({dist}) · за {h} ≈ {p}", "{arrow} {price} {name} ({dist}) · within {h} ≈ {p}"),
    "dc_btc_level_fb": _pair("{arrow} {price} {name} ({dist}) · за {h} исторически в {p} случаев",
                             "{arrow} {price} {name} ({dist}) · within {h} historically in {p} of cases"),
    "dc_btc_cal": _pair("↳ шанс дойти; говорили → было: {parts}", "↳ chance to reach; said → happened: {parts}"),
    "dc_fallback_note": _pair("* исторически в стольких случаях; точность такой оценки не прошла проверку или ещё не "
                              "набрала N",
                              "* historically in that share of cases; the accuracy of such an estimate failed its "
                              "check or has too little N yet"),
    "dc_brief_levels": _pair("Уровни: {parts}", "Levels: {parts}"),
    "dc_btc_events": _pair("События в ближайшие сутки: {list}", "Events within 24 hours: {list}"),
    "btn_levels": _pair("Уровни", "Levels"),
    "btn_risk": _pair("Риск", "Risk"),
    # ---- /levels ----
    "lv_title": _pair("<b>Уровни BTC</b> · Binance · цена {price} · {clock}",
                      "<b>BTC levels</b> · Binance · price {price} · {clock}"),
    "lv_level": _pair("{arrow} {price} {names} ({dist}){chances}", "{arrow} {price} {names} ({dist}){chances}"),
    "lv_chance_b": _pair("за {h} ≈ {p}", "within {h} ≈ {p}"),
    "lv_chance_fb": _pair("за {h} исторически в {p} случаев", "within {h} historically in {p} of cases"),
    "lv_none": _pair("{arrow} рядом нет", "{arrow} none nearby"),
    "lv_hist": _pair("↳ после первого касания ({n}): через 1ч цена {side} уровня в {hold} — у случайного уровня {ctrl} "
                     "({diff} п.п.{ci})",
                     "↳ after the first touch ({n}): 1h later the price was {side} the level in {hold} — a random level: {ctrl} "
                     "({diff} pp{ci})"),
    "lv_side_above": _pair("выше", "above"),
    "lv_side_below": _pair("ниже", "below"),
    "lv_hist_short": _pair("↳ после первого касания: мало данных ({n})", "↳ after the first touch: too little data ({n})"),
    "lv_hist_fewperiods": _pair("↳ после первого касания: мало разных периодов ({n}, периодов: {d})",
                                "↳ after the first touch: too few distinct periods ({n}, {d} periods)"),
    "lv_hist_noci": _pair("↳ после первого касания: интервал ещё не посчитан ({n})",
                          "↳ after the first touch: no interval computed yet ({n})"),
    "lv_hist_move": _pair("↳ за 1ч медиана: дальше {further}, обратно {back} (у случайного уровня {c_further} и {c_back})",
                          "↳ 1h median: {further} further, {back} back (a random level: {c_further} and {c_back})"),
    "lv_footer": _pair("День, неделя и месяц — по UTC, как дневная свеча на бирже. История — Binance с 2020 года; "
                       "ликвидации — Binance и Bybit за 24 ч.",
                       "Day, week and month are UTC, like the exchange's daily candle. History: Binance since 2020; "
                       "liquidations: Binance and Bybit, last 24h."),
    # ---- /risk ----
    "rk_title": _pair("<b>Риск BTC</b> · Binance · цена {price}", "<b>BTC risk</b> · Binance · price {price}"),
    "rk_stop": _pair("Стоп {pct} (≈ {usd}) против позиции, как часто цена доходила до него:",
                     "A stop {pct} (≈ {usd}) away, how often the price reached it:"),
    "rk_line": _pair("за {h} — в {p}", "within {h} — {p}"),
    "rk_line_zone": _pair("за {h} — без оценки", "within {h} — not shown"),
    "rk_typical": _pair("Обычный ход: 1ч ±{h1}, 4ч ±{h4}, 24ч ±{h24}", "Typical move: 1h ±{h1}, 4h ±{h4}, 24h ±{h24}"),
    "rk_table_head": _pair("Как часто цена проходила такое расстояние в одну сторону:",
                           "How often the price moved this far in one direction:"),
    "rk_table_line": _pair("{pct}: 1ч {p1} · 4ч {p4} · 24ч {p24}", "{pct}: 1h {p1} · 4h {p4} · 24h {p24}"),
    "rk_note": _pair("Одинаково для лонга и шорта: направление модель не предсказывает.",
                     "The same for longs and shorts: the model does not forecast direction."),
    "rk_usage": _pair("Стоп в процентах или ценой: /risk 0.5 или /risk 61500",
                      "A stop in percent or as a price: /risk 0.5 or /risk 61500"),
    # ---- /events ----
    "ev_title": _pair("<b>События</b> (время — {zone_name})", "<b>Events</b> ({zone_name} time)"),
    "ev_none": _pair("В ближайшие 14 дней в календаре ничего нет.", "Nothing in the calendar for the next 14 days."),
    "ev_funding": _pair("Funding Binance: {times} {zone}", "Binance funding: {times} {zone}"),
    "ev_release_note": _pair("{names}: вокруг публикации обычная калибровка коридора не применяется.",
                             "{names}: around the release, the usual corridor calibration does not apply."),
    # ---- /accuracy ----
    "ac_title": _pair("<b>Точность коридора</b> (доля случаев, когда цена не вышла за коридор; расчётная — {share})",
                      "<b>Corridor accuracy</b> (share of cases the price stayed inside; designed for {share})"),
    "ac_holdout": _pair("Проверка на отложенном годе ({period}; {days} дн.): {parts}",
                        "Check on a held-out year ({period}; {days} days): {parts}"),
    "ac_live_head": _pair("Вживую (N — непересекающиеся окна):", "Live (N = non-overlapping windows):"),
    "ac_h_line": _pair("{h}: {windows} · ширина ±{width}", "{h}: {windows} · width ±{width}"),
    "ac_win": _pair("{d} дн. {p} (N={n})", "{d} days {p} (N={n})"),
    "ac_win_short": _pair("{d} дн. мало данных (N={n})", "{d} days too little data (N={n})"),
    "ac_miss_line": _pair("   за 30 дн. вне коридора: выше {up} (медиана на {up_size}), ниже {dn} (медиана на {dn_size})",
                          "   last 30 days outside: above {up} (median by {up_size}), below {dn} (median by {dn_size})"),
    "ac_regime_line": _pair("   за 90 дн.: в дни CPI/FOMC {ev} · при высокой волатильности {hv}",
                            "   last 90 days: on CPI/FOMC days {ev} · in high volatility {hv}"),
    "ac_reg": _pair("{p} (N={n})", "{p} (N={n})"),
    "ac_reg_short": _pair("мало данных (N={n})", "too little data (N={n})"),
    "ac_live": _pair("Живые прогнозы за 30 дней (N — непересекающиеся окна): {parts}",
                     "Live forecasts, last 30 days (N = non-overlapping windows): {parts}"),
    "ac_live_none": _pair("Живые прогнозы ещё не созрели.", "No live forecast has matured yet."),
    "ac_part": _pair("{h} {p}", "{h} {p}"),
    "ac_part_live": _pair("{h} — {p} (N={n})", "{h} — {p} (N={n})"),
    "ac_part_live_short": _pair("{h} — мало данных (N={n})", "{h} — too little data (N={n})"),
    "ac_touch_head": _pair("<b>Шанс дойти</b>: говорили → было на отложенном годе (N — непересекающиеся окна)",
                           "<b>Chance to reach</b>: said → happened on the held-out year (N = non-overlapping windows)"),
    "ac_touch_line": _pair("{h}: {parts}", "{h}: {parts}"),
    "ac_touch_part": _pair("{p} → {r} (N={n})", "{p} → {r} (N={n})"),
    "ac_touch_part_off": _pair("{p} → {r} (N={n})*", "{p} → {r} (N={n})*"),
    "ac_neither_head": _pair("<b>Ни один из двух уровней</b>: говорили → было на отложенном годе",
                             "<b>Neither of two levels</b>: said → happened on the held-out year"),
    "ac_live_touch_head": _pair("<b>Шанс дойти вживую</b> (журнал за последние {days} дн.): говорили → было",
                                "<b>Chance to reach, live</b> (journal, last {days} days): said → happened"),
    "ac_live_neither_head": _pair("<b>Ни один из двух уровней вживую</b>: говорили → было",
                                  "<b>Neither of two levels, live</b>: said → happened"),
    "ac_live_bins_short": _pair("{h}: мало данных (N={n})", "{h}: too little data (N={n})"),
    "ac_touch_part_div": _pair("{p} → {r} (N={n})‼", "{p} → {r} (N={n})‼"),
    "ac_live_div_note": _pair("‼ вживую разошлось с правилом (больше ±5 п.п., интервал без нуля): до новой версии модели "
                              "такие шансы показываем как «исторически в X % случаев»",
                              "‼ live result broke the rule (beyond ±5 pp, interval excluding zero): until the next model "
                              "version such chances are shown as “historically in X % of cases”"),
    "ac_touch_note": _pair("* вне правила (±5 п.п. при N ≥ 30): такие шансы показываем как «исторически в X % случаев»",
                           "* outside the rule (±5 pp with N ≥ 30): such chances are shown as “historically in X % of cases”"),
    # ---- /check (PRE_BETA_SCOPE_DECISION_V1 §5; docs/BETA_CHECK_CALIBRATION_DESIGN_V1.md) ----
    "ck_usage": _pair("Уровень ценой или в процентах: /check 64000 · /check 64к · /check -3% · два уровня: /check 64000 61000",
                      "A level as a price or a percent: /check 64000 · /check 64k · /check -3% · two levels: /check 64000 61000"),
    "ck_title_one": _pair("<b>BTC → {level}</b> ({dist}) · сейчас {price} · {clock}",
                          "<b>BTC → {level}</b> ({dist}) · now {price} · {clock}"),
    "ck_title_two": _pair("<b>BTC: {a} ({da}) и {b} ({db})</b> · сейчас {price} · {clock}",
                          "<b>BTC: {a} ({da}) and {b} ({db})</b> · now {price} · {clock}"),
    "ck_h_b_hold": _pair("{h}: шанс дойти ≈ {p} · на истории: говорили {P} → было {R} (N={n})",
                         "{h}: chance to reach ≈ {p} · on history: said {P} → happened {R} (N={n})"),
    "ck_h_b_live": _pair("{h}: шанс дойти ≈ {p} · вживую: говорили {P} → было {R} (N={n})",
                         "{h}: chance to reach ≈ {p} · live: said {P} → happened {R} (N={n})"),
    "ck_h_fallback": _pair("{h}: исторически цена доходила в {p} случаев (история {n} дн.; обычно ход за {h} ±{typ})",
                           "{h}: historically the price got there in {p} of cases ({n} days of history; a usual {h} move is ±{typ})"),
    "ck_arrow_up": _pair("↑", "↑"),
    "ck_arrow_down": _pair("↓", "↓"),
    "ck_neither": _pair("ни один", "neither"),
    "ck_part_b": _pair("{label} ≈ {p}", "{label} ≈ {p}"),
    "ck_part_fallback": _pair("{label} {p}*", "{label} {p}*"),
    "ck_cal_part": _pair("{label} {P} → {R} ({src}, N={n})", "{label} {P} → {R} ({src}, N={n})"),
    "ck_src_hold": _pair("на истории", "on history"),
    "ck_src_live": _pair("вживую", "live"),
    "ck_pair_line": _pair("{h}: {parts}", "{h}: {parts}"),
    "ck_pair_cal": _pair("   говорили → было: {parts}", "   said → happened: {parts}"),
    "ck_fallback_note": _pair("* исторически в стольких случаях (история {n} дн.); точность такой оценки не прошла "
                              "проверку или ещё не набрала N",
                              "* historically in that share of cases ({n} days of history); the accuracy of such an "
                              "estimate failed its check or has too little N yet"),
    "ck_events": _pair("События в ближайшие 24ч: {list}", "Events in the next 24h: {list}"),
    "ck_is_level": _pair("{level} — это {names}:", "{level} is {names}:"),
    "ck_beyond": _pair("За {level} дальше: {price} — {name} ({dist})", "Beyond {level}: {price} — {name} ({dist})"),
    "ck_dist": _pair("{level}: после касания цены на таком расстоянии (≈{d}, {n}) через 1ч цена была за ней в {hold}; "
                     "медиана за 1ч: дальше {further}, обратно {back}. Так обычно ведёт себя произвольная цена.",
                     "{level}: after a touch of a price this far (≈{d}, {n}), 1h later the price was beyond it in {hold}; "
                     "1h median: {further} further, {back} back. That is how an arbitrary price usually behaves."),
    "ck_dist_short": _pair("{level}: после касания цены на таком расстоянии — мало данных ({n})",
                           "{level}: after a touch of a price this far — too little data ({n})"),
    "ck_footer_one": _pair("Binance.", "Binance."),
    "ck_footer_two": _pair("Binance. Какой из двух уровней будет первым — не показываем.",
                           "Binance. Which of the two levels comes first is not shown."),
    "btn_watch": _pair("🔔 Следить: {price}", "🔔 Watch: {price}"),
    "btn_check": _pair("🎯 Проверить {price}", "🎯 Check {price}"),
    # ---- /alert ----
    "al_set": _pair("Сообщу, когда BTC дойдёт до {price} ({dist} от {now}). За 24ч до такого расстояния цена доходила в {p}.",
                    "I will message you when BTC reaches {price} ({dist} from {now}). Within 24h the price reached such a distance in {p}."),
    "al_set_plain": _pair("Сообщу, когда BTC дойдёт до {price} ({dist} от {now}).",
                          "I will message you when BTC reaches {price} ({dist} from {now})."),
    "al_list_head": _pair("<b>Ваши уровни</b>", "<b>Your price alerts</b>"),
    "al_list_line": _pair("{k}. {price} ({dist})", "{k}. {price} ({dist})"),
    "al_list_none": _pair("Уровней нет. Добавить: /alert 65000", "No alerts. Add one: /alert 65000"),
    "al_list_footer": _pair("Удалить: /alert del 1 · все: /alert del all", "Delete: /alert del 1 · all: /alert del all"),
    "al_approach_note": _pair("Когда до уровня останется меньше обычного хода за час, пришлю одно сообщение заранее, "
                              "потом — о касании.",
                              "When the level is closer than the usual 1h move, I send one message ahead, then one "
                              "at the touch."),
    "al_approach_note_list": _pair("Для уровня дальше обычного хода за час пришлю одно сообщение заранее, потом — о касании.",
                                   "For a level farther than the usual 1h move I send one message ahead, then one at "
                                   "the touch."),
    "al_deleted": _pair("Удалено: {n}.", "Deleted: {n}."),
    "al_limit": _pair("Уже {n} уровней — это максимум. Удалите лишний: /alert del 1",
                      "Already {n} alerts — the maximum. Delete one: /alert del 1"),
    "al_usage": _pair("Уровень ценой: /alert 65000 · список: /alert · удалить: /alert del 1",
                      "A price: /alert 65000 · list: /alert · delete: /alert del 1"),
    "al_too_far": _pair("Уровень дальше 30% от текущей цены {now}. Укажите ближе.",
                        "That is more than 30% from the current price {now}. Pick a closer level."),
    "al_too_close": _pair("Это слишком близко к текущей цене {now}.", "That is too close to the current price {now}."),
    "al_no_price": _pair("Цена Binance сейчас недоступна, попробуйте позже.", "The Binance price is unavailable now; try later."),
    # ---- weekly report (backlog B4) ----
    "wk_title": _pair("<b>📅 Неделя бота: {d0}–{d1}</b>", "<b>📅 The bot's week: {d0}–{d1}</b>"),
    "wk_intro": _pair("Как сработали наши оценки за 7 дней (N — непересекающиеся окна).",
                      "How our estimates did over 7 days (N = non-overlapping windows)."),
    "wk_cor_head": _pair("Коридоры — доля случаев, когда цена не вышла за коридор; расчётная — {share}:",
                         "Corridors: the share of cases the price stayed inside; designed for {share}:"),
    "wk_cor_line": _pair("• {h}: {p} (N={n}; на отложенном годе {hold}) · ширина ±{width}",
                         "• {h}: {p} (N={n}; held-out year {hold}) · width ±{width}"),
    "wk_cor_short": _pair("• {h}: мало данных (N={n})", "• {h}: too little data (N={n})"),
    "wk_cor_none": _pair("• за неделю нет проверенных коридоров", "• no corridor matured this week"),
    "wk_miss_line": _pair("   выше коридора {up} (медиана на {up_size}), ниже {dn} (медиана на {dn_size})",
                          "   above {up} (median by {up_size}), below {dn} (median by {dn_size})"),
    "wk_touch_head": _pair("Шанс дойти до уровня — говорили → было:", "Chance to reach a level — stated → happened:"),
    "wk_touch_line": _pair("• {h}: {parts}", "• {h}: {parts}"),
    "wk_touch_short": _pair("• {h}: мало данных (N={n})", "• {h}: too little data (N={n})"),
    "wk_alerts": _pair("Сообщений о рынке за неделю: уровни {level}, события {event}, резкие движения {move}.",
                       "Market messages this week: levels {level}, events {event}, sharp moves {move}."),
    "wk_footer": _pair("Подробнее и за 30/90 дней: /accuracy · выключить итоги недели: /push weekly off",
                       "More, and over 30/90 days: /accuracy · turn the weekly report off: /push weekly off"),
    # ---- /push ----
    "push_master_off_note": _pair("Сейчас не приходит ничего из списка ниже. Настройки категорий сохранены "
                                  "и снова заработают после /push on.",
                                  "Nothing below arrives now. Your category settings are kept and work "
                                  "again after /push on."),
    "push_status": _pair("Сообщения: {master}\n• уровни (первое касание вчерашних, недельных, месячных максимумов и минимумов): {levels}\n"
                         "• события (CPI, ФРС за 30 минут): {events}\n• резкие движения (за 15 минут): {moves}\n"
                         "• необычный час: {hours}\n• итоги недели (воскресенье вечером): {weekly}\n"
                         "Личные уровни (/alert) приходят всегда. "
                         "Утренняя сводка — отдельно: /brief on|off.\n"
                         "Включить или выключить: /push off · /push levels off · /push events on · /push moves off · "
                         "/push hour off · /push weekly off",
                         "Messages: {master}\n• levels (first touch of daily, weekly, monthly highs and lows): {levels}\n"
                         "• events (CPI, Fed, 30 minutes ahead): {events}\n• sharp moves (within 15 minutes): {moves}\n"
                         "• unusual hour: {hours}\n• weekly report (Sunday evening): {weekly}\n"
                         "Your own alerts (/alert) always arrive. "
                         "The morning briefing is separate: /brief on|off.\n"
                         "Switch: /push off · /push levels off · /push events on · /push moves off · /push hour off"
                         " · /push weekly off"),
    "push_pref_ok": _pair("Готово. {status}", "Done. {status}"),
    "on_word": _pair("вкл", "on"),
    "off_word": _pair("выкл", "off"),
    # ---- market alert pushes ----
    "pa_level_title": _pair("<b>BTC · {name} {level}</b>", "<b>BTC · {name} {level}</b>"),
    "pa_level_now_at": _pair("{clock} — первое касание за {period} · цена {price} (Binance, {price_clock})",
                             "{clock} — first touch this {period} · price {price} (Binance, {price_clock})"),
    "pa_level_now": _pair("{clock} · цена {price} (Binance) — первое касание за {period}",
                          "{clock} · price {price} (Binance) — first touch this {period}"),
    "pa_zone_now_at": _pair("{clock} — цена вошла в зону {name} {low}–{high}, первый раз за {period} · цена {price} "
                            "(Binance, {price_clock})",
                            "{clock} — the price entered the {name} zone {low}–{high}, the first time this {period} · "
                            "price {price} (Binance, {price_clock})"),
    "pa_period_day": _pair("день", "day"),
    "pa_period_week": _pair("неделю", "week"),
    "pa_period_month": _pair("месяц", "month"),
    "pa_level_hist": _pair("После первого касания ({n}): через 1ч цена {side} уровня в {hold} — у случайного уровня {ctrl} "
                           "({diff} п.п.{ci})",
                           "After the first touch ({n}): 1h later the price was {side} the level in {hold} — a random level: {ctrl} "
                           "({diff} pp{ci})"),
    "pa_level_hist_short": _pair("После первого касания: мало данных ({n})", "After the first touch: too little data ({n})"),
    "pa_level_hist_fewperiods": _pair("После первого касания: мало разных периодов ({n}, периодов: {d})",
                                      "After the first touch: too few distinct periods ({n}, {d} periods)"),
    "pa_level_hist_noci": _pair("После первого касания: интервал ещё не посчитан ({n})",
                                "After the first touch: no interval computed yet ({n})"),
    "pa_level_move": _pair("За 1ч медиана: дальше {further}, обратно {back} (у случайного уровня {c_further} и {c_back})",
                           "1h median: {further} further, {back} back (a random level: {c_further} and {c_back})"),
    "pa_next": _pair("Следующий уровень: {price} — {name} ({dist}), за 24ч доходили в {p}",
                     "Next level: {price} — {name} ({dist}), reached within 24h in {p}"),
    "pa_next_nop": _pair("Следующий уровень: {price} — {name} ({dist})", "Next level: {price} — {name} ({dist})"),
    "pa_corridor": _pair("Коридор 4ч: {low}–{high} (±{half})", "4h corridor: {low}–{high} (±{half})"),
    "pa_event_title": _pair("<b>BTC · через {mins} мин {name}</b>", "<b>BTC · {name} in {mins} min</b>"),
    "pa_event_when": _pair("{clock} · цена {price} (Binance)", "{clock} · price {price} (Binance)"),
    "pa_event_when_at": _pair("{clock} · цена {price} (Binance, {price_clock})", "{clock} · price {price} (Binance, {price_clock})"),
    # a model's corridor, never «обычно» (the word of a comparison base; review of #375)
    "pa_corridor_1h_plain": _pair("Коридор 1ч сейчас: {low}–{high} (±{half})", "1h corridor now: {low}–{high} (±{half})"),
    # the delay of a push or an alert (backlog F1; the measured field of A4)
    "dl_line": _pair(" · задержка {lag}", " · delay {lag}"),
    "dl_own": _pair("Задержка этого сообщения: {lag}", "This message's delay: {lag}"),
    "dl_typical": _pair(" (обычно {p50}, N={n})", " (usually {p50}, N={n})"),
    "dl_s": _pair("{s} с", "{s} s"),
    "dl_m": _pair("{m} мин", "{m} min"),
    "dl_ms": _pair("{m} мин {s} с", "{m} min {s} s"),
    "dl_hm": _pair("{h} ч {m} мин", "{h} h {m} min"),
    "pa_move_title": _pair("<b>BTC · резкое движение {pct} за 15 минут</b>", "<b>BTC · sharp move {pct} in 15 minutes</b>"),
    "pa_move_span": _pair("{span} · {open} → {close} (Binance)", "{span} · {open} → {close} (Binance)"),
    "pa_move_rare": _pair("Такой ход за 15 минут бывает примерно раз в {days} дн.",
                          "A 15-minute move like this happens about once every {days} days."),
    "pa_levels_near": _pair("Рядом: {parts}", "Nearby: {parts}"),
    "pa_price_title": _pair("<b>BTC дошёл до вашего уровня {level}</b>", "<b>BTC reached your level {level}</b>"),
    "pa_price_now": _pair("{clock} · цена {price} (Binance)", "{clock} · price {price} (Binance)"),
    "pa_price_now_at": _pair("{clock} — уровень достигнут · цена {price} (Binance, {price_clock})",
                             "{clock} — level reached · price {price} (Binance, {price_clock})"),
    "pa_price_late": _pair("Уровень был достигнут {when} {zone}, пока сообщения не отправлялись · сейчас {price} (Binance)",
                           "The level was reached on {when} ({zone}) while messages were off · now {price} (Binance)"),
    "pa_price_late_at": _pair("Уровень был достигнут {when} {zone}, пока сообщения не отправлялись · сейчас {price} "
                              "(Binance, {price_clock})",
                              "The level was reached on {when} ({zone}) while messages were off · now {price} "
                              "(Binance, {price_clock})"),
    "pa_approach_title": _pair("<b>BTC подходит к вашему уровню {level}</b>", "<b>BTC is nearing your level {level}</b>"),
    "pa_approach_line": _pair("{clock} · цена {price} (Binance, {price_clock}) · до уровня {dist} — меньше обычного "
                              "хода за 1ч (±{typ})",
                              "{clock} · price {price} (Binance, {price_clock}) · {dist} to the level — less than the "
                              "usual 1h move (±{typ})"),
    "pa_price_footer": _pair("Ваши уровни: /alert", "Your alerts: /alert"),
    # ---- research ↔ bot (config/beta_research_findings.yaml) ----
    # status-worded context lines: a discovery is never «Проверено», a weak effect is never a result
    "rs_line_confirmed": _pair("Проверено: {text}", "Tested: {text}"),
    "rs_line_not_confirmed": _pair("Проверка показала: {text}", "The test showed: {text}"),
    "rs_line_discovery": _pair("Гипотеза, не подтверждено: {text}", "Hypothesis, not confirmed: {text}"),
    "rs_line_weak": _pair("Ниже порога практической величины: {text}", "Below the materiality bar: {text}"),
    "rs_line_side_finding": _pair("Побочный результат проверки: {text}", "A side result of a test: {text}"),
    "rs_title": _pair("<b>Что проверили исследования</b> (история, не прогноз)",
                      "<b>What the research tested</b> (history, not a forecast)"),
    "rs_group_confirmed": _pair("<b>Подтвердилось</b> (и повторилось на другой бирже)",
                                "<b>Held up</b> (and replicated on another exchange)"),
    "rs_group_discovery": _pair("<b>Найдено, но ещё не перепроверено</b> (один прогон по 2020–2024)",
                                "<b>Found, not yet replicated</b> (one run on 2020–2024)"),
    "rs_group_weak": _pair("<b>Есть, но слабее порога практической величины</b>", "<b>Present, but below the materiality bar</b>"),
    "rs_group_not_confirmed": _pair("<b>Не подтвердилось</b> (популярные представления, которые не выдержали проверку)",
                                    "<b>Did not hold</b> (popular beliefs that failed the test)"),
    "rs_group_side_finding": _pair("<b>Побочные находки</b> (проверяли другое — нашли это)",
                                   "<b>Side findings</b> (tested something else, found this)"),
    "rs_group_underpowered": _pair("<b>Данных не хватило для вывода</b>", "<b>Not enough data for a verdict</b>"),
    "rs_continued": _pair("(продолжение)", "(continued)"),
    "rs_item": _pair("• {text} — {data} ({id})", "• {text} — {data} ({id})"),
    "rs_footer": _pair("Каждая строка — закрытая проверка с записью в репозитории. В анализе рынка бот приводит "
                       "их со значком 🔬, когда текущее состояние совпадает с проверенным: «Проверено», «Гипотеза», "
                       "«ниже порога» или «эффекта не нашла».",
                       "Each line is a closed test with its record in the repository. In its market analysis the bot "
                       "cites them with 🔬 when the current state matches a tested one: tested, hypothesis, below the "
                       "bar or no effect found."),
    # ---- research evidence in the live analysis (beta/research_evidence.py) ----
    # one line = the live state + what the closed research found after it, worded by status
    "rev_line_confirmed": _pair("🔬 {state}. Проверено на двух биржах: {effect}.",
                               "🔬 {state}. Tested on two exchanges: {effect}."),
    "rev_line_discovery": _pair("🔬 {state}. Гипотеза (найдено на истории, не подтверждено): {effect}.",
                               "🔬 {state}. Hypothesis (found on history, not confirmed): {effect}."),
    "rev_line_weak": _pair("🔬 {state}. В истории {effect} — эффект есть, но ниже нашего порога практической величины.",
                          "🔬 {state}. In history {effect} — the effect is there, but below our materiality bar."),
    "rev_line_not_confirmed": _pair("🔬 {state}. Историческая проверка эффекта не нашла: {effect}.",
                                   "🔬 {state}. The historical test found no effect: {effect}."),
    "rev_line_side_finding": _pair("🔬 {state}. Побочный результат проверки: {effect}.",
                                  "🔬 {state}. A side result of a test: {effect}."),
    "rev_line_conditional": _pair("🔬 Если цена дойдёт сюда: {state}. {verdict}: {effect}.",
                                 "🔬 If price gets here: {state}. {verdict}: {effect}."),
    "rev_verdict_confirmed": _pair("Проверено", "Tested"),
    "rev_verdict_discovery": _pair("Гипотеза, не подтверждено", "Hypothesis, not confirmed"),
    "rev_verdict_weak": _pair("Ниже нашего порога практической величины", "Below our materiality bar"),
    "rev_verdict_not_confirmed": _pair("Проверка эффекта не нашла", "The test found no effect"),
    "rev_verdict_side_finding": _pair("Побочный результат", "Side result"),
    # live states (what the market shows now); {when}: Kyiv time of the research decision moment
    "rev_st_D7_HOUR": _pair("Час {hour_start}–{hour_end}: цена ушла необычно далеко для своего объёма",
                           "Hour {hour_start}–{hour_end}: price moved unusually far for its volume"),
    "rev_st_D2_HIGH_RV_DAY": _pair("Вчера был очень волатильный день (RV {rv} при пороге {p90})",
                                  "Yesterday was a very volatile day (RV {rv} against a bar of {p90})"),
    "rev_st_P3_CROWD_CROWD_LONG": _pair("{when}: доля лонг-счетов на Binance необычно высока ({z}σ к своим 30 дням)",
                                       "{when}: the share of long accounts on Binance is unusually high ({z}σ vs its 30 days)"),
    "rev_st_P3_CROWD_CROWD_SHORT": _pair("{when}: доля шорт-счетов на Binance необычно высока ({z}σ к своим 30 дням)",
                                        "{when}: the share of short accounts on Binance is unusually high ({z}σ vs its 30 days)"),
    "rev_st_P1_LEVERAGE_LOADING": _pair("{when}: OI на Binance за 4 ч {doi4} при тихом рынке (размах 4 ч {range4})",
                                       "{when}: Binance OI {doi4} over 4h in a quiet market (4h range {range4})"),
    "rev_st_P2_DELEVERAGING": _pair("{when}: резкий сброс OI на Binance за час ({doi1})",
                                   "{when}: a sharp one-hour drop in Binance OI ({doi1})"),
    "rev_st_O1_IMPLIED_ABOVE_REALIZED": _pair("{when}: опционы закладывают заметно больше движения, чем было за сутки (DVOL {dvol})",
                                             "{when}: options price in clearly more movement than the last day showed (DVOL {dvol})"),
    "rev_st_O2_DVOL_JUMP": _pair("{when}: опционная волатильность DVOL за час выросла на {jump} (до {dvol})",
                                "{when}: options volatility DVOL rose {jump} in an hour (to {dvol})"),
    "rev_st_O3_UP_VOL": _pair("{when}: за сутки DVOL рос вместе с ценой", "{when}: over the day DVOL rose together with price"),
    "rev_st_L1_THIN_BOOK": _pair("{when}: стакан в пределах ±1% тоньше обычного ({ratio} от медианы 7 дней)",
                                "{when}: the ±1% order book is thinner than usual ({ratio} of its 7-day median)"),
    "rev_st_L2_BOOK_SKEW_BID_HEAVY": _pair("{when}: в стакане ±1% заявок на покупку заметно больше, чем на продажу ({bid} против {ask})",
                                          "{when}: the ±1% book holds clearly more bids than asks ({bid} vs {ask})"),
    "rev_st_L2_BOOK_SKEW_ASK_HEAVY": _pair("{when}: в стакане ±1% заявок на продажу заметно больше, чем на покупку ({ask} против {bid})",
                                          "{when}: the ±1% book holds clearly more asks than bids ({ask} vs {bid})"),
    "rev_st_L3_BOOK_NOT_RECOVERED": _pair("{when}: через 30 мин после резкого движения ({move_end}) стакан ±1% не восстановился ({recovery} от прежнего)",
                                         "{when}: 30 min after a sharp move ({move_end}) the ±1% book had not recovered ({recovery} of before)"),
    "rev_st_S1_STRESS_LEADER_SPOT_LED": _pair("Стресс-час с {hour} (размах {range}): цену вёл спот, а не перп",
                                             "The stress hour from {hour} (range {range}) was led by spot, not the perp"),
    "rev_st_S1_STRESS_LEADER_PERP_LED": _pair("Стресс-час с {hour} (размах {range}): цену вёл перп, а не спот",
                                             "The stress hour from {hour} (range {range}) was led by the perp, not spot"),
    "rev_st_S3_LARGE_PRINTS": _pair("Стресс-час с {hour}: {n} сделок на перпе от 1 млн $",
                                   "The stress hour from {hour}: {n} perp trades of $1M or more"),
    "rev_st_V1_SESSION_EXTREME": _pair("{when}: цена коснулась уровня «{name}» ({price})",
                                      "{when}: price touched {name} ({price})"),
    "rev_st_V1_SESSION_EXTREME_PENDING": _pair("это экстремум сессии («{name}»)", "this is a session extreme ({name})"),
    "rev_st_V2_KEY_LEVEL_TOUCH": _pair("{when}: первое касание уровня «{name}» ({price})",
                                      "{when}: the first touch of {name} ({price})"),
    "rev_st_V3_RETEST": _pair("{when}: повторное касание уровня «{name}» ({price}) после отката",
                             "{when}: a retest of {name} ({price}) after a pullback"),
    "rev_st_V3_RETEST_PENDING": _pair("это будет повторное касание «{name}» после отката",
                                     "it would be a retest of {name} after a pullback"),
    "rev_st_L_CONFLUENCE": _pair("{when}: уровень «{name}» совпал с другими уровнями",
                                "{when}: {name} coincided with other levels"),
    "rev_st_L_CONFLUENCE_PENDING": _pair("здесь сходятся несколько уровней ({names})",
                                        "several levels meet here ({names})"),
    "rev_st_L_STALE": _pair("{when}: уровень «{name}» до касания сутки не торговался",
                           "{when}: {name} had not traded for a day before its touch"),
    "rev_st_L_STALE_PENDING": _pair("уровень «{name}» сутки не торговался", "{name} has not traded for a day"),
    "rev_st_L_SPOT_APPROACH": _pair("{when}: к уровню «{name}» подходили на потоке спота в ту же сторону",
                                   "{when}: the approach to {name} came with spot taker flow the same way"),
    "rev_st_B2_SPOT_SHARE_MOVE": _pair("Резкое движение к {move_end}: доля спота в объёме выше, чем за предыдущие сутки",
                                      "The sharp move to {move_end}: spot's share of volume was above the previous day's"),
    "rev_st_H03_IMPULSE": _pair("{when}: резкий импульс {ret} за {window} мин (сильнее 90% за 30 дней)",
                               "{when}: a sharp {ret} impulse over {window} min (stronger than 90% of the last 30 days)"),
    "rev_st_H02_FAILED_BREAKOUT": _pair("{when}: цена вышла за диапазон последних {window} мин и вернулась внутрь (ложный пробой)",
                                       "{when}: price left the range of the last {window} min and came back in (a failed breakout)"),
    "rev_st_H04_TREND_PULLBACK": _pair("{when}: откат на {depth} от движения за {hours} ч",
                                      "{when}: a pullback of {depth} of the move over {hours}h"),
    "rev_st_H05_TAKER_SKEW_BUY": _pair("{when}: заметный перевес агрессивных покупок за {window} мин",
                                      "{when}: a clear skew to aggressive buying over {window} min"),
    "rev_st_H05_TAKER_SKEW_SELL": _pair("{when}: заметный перевес агрессивных продаж за {window} мин",
                                       "{when}: a clear skew to aggressive selling over {window} min"),
    "rev_st_M02_OI_CONFIRMED_IMPULSE": _pair("{when}: после импульса {impulse} OI растёт и цена продолжает",
                                            "{when}: after a {impulse} impulse OI is rising and price continues"),
    "rev_st_M02_OI_CONFIRMED_IMPULSE_LABEL": _pair("Последний час похож на набор позиций по ходу движения (цена и OI вместе)",
                                                  "The last hour looks like positions being built with the move (price and OI together)"),
    "rev_st_M01_OI_STALLED_IMPULSE": _pair("{when}: после импульса {impulse} OI растёт, а цена буксует",
                                          "{when}: after a {impulse} impulse OI is rising while price stalls"),
    "rev_st_R03_WEEKEND": _pair("Сегодня выходной", "It is the weekend"),
    "rev_st_R03_EXPIRY_HOUR": _pair("Сегодня экспирация опционов Deribit", "Deribit options expire today"),
    "rev_st_R03_EXPIRY_PIN": _pair("Сегодня экспирация опционов Deribit", "Deribit options expire today"),
    "rev_st_R03_US_OPEN_CLOSE_MONDAY_OPEN": _pair("Сегодня понедельник: открытие США", "It is Monday: the US open"),
    "rev_st_R03_US_OPEN_CLOSE_FRIDAY_CLOSE": _pair("Сегодня пятница: закрытие США", "It is Friday: the US close"),
    "rev_st_D12_US_CLOCK_WEEK": _pair("На этой неделе в США перевели часы", "The US changed its clocks this week"),
    "rev_st_H01_COMPRESSION": _pair("Рынок сжат: размах в нижних 20% обычного", "The market is compressed: the range is in the bottom 20%"),
    # Details tab and /research footer
    "rev_tab_head": _pair("<b>Исследования к рынку сейчас</b> · {clock}", "<b>Research on the market now</b> · {clock}"),
    "rev_tab_none": _pair("Сейчас ни одно закрытое исследование не описывает состояние рынка.",
                         "No closed research unit describes the current market state."),
    "rev_tab_item": _pair("• <b>{id}</b> [{status}] {state} — {effect}.", "• <b>{id}</b> [{status}] {state} — {effect}."),
    "rev_tab_meta": _pair("  Сравнение: {comparator}; N {n}; {replication}. Ограничения: {limitations}.",
                         "  Comparator: {comparator}; N {n}; {replication}. Limits: {limitations}."),
    "rev_tab_vetoed": _pair("  Не используется: противоречит непроверенному механизму ({by}).",
                           "  Not used: its mechanism did not hold ({by})."),
    "rev_tab_zones_head": _pair("<b>Если цена дойдёт до уровня</b> — что было после таких касаний:",
                                "<b>If the price reaches a level</b> — what followed such touches:"),
    "rev_tab_zone": _pair("{arrow} {price} {name}", "{arrow} {price} {name}"),
    "rev_tab_alerts_head": _pair("<b>Сообщения за сутки</b> — касания уровней и резкие ходы:",
                                 "<b>Alerts in the last 24h</b> — level touches and sharp moves:"),
    "rev_tab_alert_level": _pair("{clock} · касание {price} {name}", "{clock} · touch of {price} {name}"),
    "rev_tab_alert_move": _pair("{clock} · резкий ход {move}", "{clock} · sharp move {move}"),
    "rev_tab_unavailable_head": _pair("<b>Не проверить сейчас</b> (нет свежих данных — вывода нет):",
                                     "<b>Cannot be checked now</b> (no fresh data — no conclusion):"),
    "rev_tab_unavailable": _pair("• {id}: {reason}", "• {id}: {reason}"),
    "rev_tab_footer": _pair("Числа — из закрытых проверок 2020–2024 (N — число случаев). История, не прогноз; "
                           "коридор и шансы дойти они не меняют. Все проверки: /research",
                           "Numbers come from closed tests on 2020–2024 (N = number of cases). History, not a forecast; "
                           "they do not change the corridor or the chances to reach. All tests: /research"),
    "rev_status_confirmed": _pair("проверено", "tested"),
    "rev_status_discovery": _pair("гипотеза", "hypothesis"),
    "rev_status_weak": _pair("ниже порога", "below the bar"),
    "rev_status_not_confirmed": _pair("не подтвердилось", "did not hold"),
    "rev_status_side_finding": _pair("побочный результат", "side result"),
    "rev_reason_NO_DATA": _pair("нет данных", "no data"),
    "rev_reason_STALE": _pair("данные устарели", "data stale"),
    "rev_reason_STALE_OR_NOT_COVERED": _pair("стакан не дотягивается до ±1% или данные устарели",
                                            "the book does not reach ±1% or data is stale"),
    "rev_reason_STALE_OR_SHORT_HISTORY": _pair("мало истории или данные устарели", "too little history or stale data"),
    "rev_reason_INSUFFICIENT_HISTORY": _pair("мало истории", "too little history"),
    "rev_reason_DEFINITION_PENDING": _pair("live-ряд ещё не сверен с историческим", "the live series is not yet checked against history"),
    "rev_reason_DEFINITION_FAILED": _pair("live-ряд не совпал с историческим", "the live series did not match history"),
    "rev_reason_NO_MATCHER": _pair("нет live-проверки", "no live check"),
    "btn_research": _pair("🔬 Исследования", "🔬 Research"),
    "n_cases": _pair("{n} {word}", "{n} {word}"),
    "since_year": _pair("с {year}", "since {year}"),
    # level race, HIST (docs/research/LEVEL_RACE_FORECAST_V1_DESIGN.md §0; ids LR_HIST_V1, LR_PUSH_HIST_V1,
    # LR_HIST_LOW_N_V1). Prices only, the three outcomes together; the Russian text is the frozen one.
    "lr_head": _pair("↳ цена вошла в зону {names} в {when}, данные на {clock}",
                     "↳ the price entered the {names} zone at {when}, data as of {clock}"),
    "pa_zone_member": _pair("{kind} ({name})", "{kind} ({name})"),
    "lr_hist_v1": _pair("Похожие касания в 2020–2024 (N = {n}): первой достигалась верхняя цена — {h_up} % "
                        "(обычно {b_up} %; разница {d_up} п.п., 95 % интервал {lo_up}..{hi_up}), нижняя — {h_dn} % "
                        "(обычно {b_dn} %; разница {d_dn} п.п., 95 % интервал {lo_dn}..{hi_dn}), ни одна за окно — "
                        "{h_ne} % (обычно {b_ne} %; разница {d_ne} п.п., 95 % интервал {lo_ne}..{hi_ne}). "
                        "Сейчас верхняя {P_UP}, нижняя {P_DN}, окно до {END}.",
                        "Similar touches in 2020–2024 (N = {n}): the upper price was reached first in {h_up}% "
                        "(usually {b_up}%; difference {d_up} pp, 95% interval {lo_up}..{hi_up}), the lower in {h_dn}% "
                        "(usually {b_dn}%; difference {d_dn} pp, 95% interval {lo_dn}..{hi_dn}), neither within the "
                        "window in {h_ne}% (usually {b_ne}%; difference {d_ne} pp, 95% interval {lo_ne}..{hi_ne}). "
                        "Now: upper {P_UP}, lower {P_DN}, window until {END}."),
    "lr_push_hist_v1": _pair("2020–2024, похожие касания (N = {n}): первой была — верхняя {P_UP} — {h_up} % · нижняя "
                             "{P_DN} — {h_dn} % · ни одна — {h_ne} % (обычно {b_up}/{b_dn}/{b_ne} %), до {END}",
                             "2020–2024, similar touches (N = {n}): reached first — the upper {P_UP} — {h_up}% · the "
                             "lower {P_DN} — {h_dn}% · neither — {h_ne}% (usually {b_up}/{b_dn}/{b_ne}%), until {END}"),
    "lr_hist_low_n_v1": _pair("Похожих касаний в 2020–2024 мало (N = {n}).",
                              "Few similar touches in 2020–2024 (N = {n})."),
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
        "/check 64000 — шанс дойти за 1ч / 4ч / 24ч и что бывало у таких уровней (два уровня: /check 64000 61000)\n"
        "/events — события: CPI, ФРС, экспирации\n"
        "/accuracy — насколько точен коридор\n"
        "/research — что проверили исследования: что подтвердилось, что нет\n"
        "/brief on|off|07:30 — утренняя сводка (по умолчанию в 08:00)\n"
        "/tz — часовой пояс (по умолчанию Киев): /tz +3 или /tz Europe/Warsaw\n"
        "/type — как вы торгуете (для статистики беты)\n"
        "/idea — идея или чего не хватает · /interview — 15 минут с командой\n"
        "/guide — как читать бота\n"
        "/push — какие сообщения присылать\n"
        "/history — недавние необычные события\n"
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
        "/check 64000 — chance to reach it within 1h / 4h / 24h and what such levels did (two: /check 64000 61000)\n"
        "/events — CPI, Fed, options expiries\n"
        "/accuracy — how accurate the corridor is\n"
        "/research — what the research tested: what held up, what did not\n"
        "/brief on|off|07:30 — morning briefing (08:00 by default)\n"
        "/tz — time zone (Kyiv by default): /tz +3 or /tz Europe/Warsaw\n"
        "/type — how you trade (for the beta's statistics)\n"
        "/idea — an idea or what is missing · /interview — 15 minutes with the team\n"
        "/guide — how to read the bot\n"
        "/push — which messages to receive\n"
        "/history — recent unusual events\n"
        "/terms — terms · /lang — message language · /feedback — feedback\n"
        "/stop — pause · /delete_me — delete your data"
    ),
}

DECISION_TERMS = {
    "ru": (
        "\n\nРЕШЕНИЯ И ИСТОРИЯ\n"
        "Коридор — диапазон, в котором цена оставалась в 4 из 5 похожих случаев за 1ч, 4ч или 24ч. "
        "Считается по Binance с 2020 года: недавняя волатильность, время суток и выходные. "
        "Около CPI и решений ФРС числовой коридор и шанс дойти не показываем: вокруг публикации обычная "
        "калибровка коридора не применяется. "
        "Точность проверяется на отложенном годе и на живых прогнозах (/accuracy).\n"
        "Шанс дойти — как часто цена проходила такое расстояние в одну сторону за это время в похожих условиях. "
        "Направление модель не предсказывает: для роста и падения шанс одинаковый.\n"
        "Уровни — только те, что видит весь рынок: максимумы и минимумы вчера, прошлой недели и месяца, "
        "открытия дня, недели и месяца, сессии Азии, Европы и США, VWAP дня, объёмный центр вчера, круглые уровни, "
        "места крупных ликвидаций за 24ч. День, неделя и месяц — по UTC.\n"
        "Случайный уровень — уровень на том же расстоянии от открытия периода, но без смысла. Рядом с реальным "
        "уровнем бот пишет, как вёл себя случайный, и разницу в процентных пунктах (п.п.); её 95% интервал "
        "считается по периодам уровня (дням, неделям или месяцам), а не по дням.\n"
        "После похожих — что было после таких же состояний 1ч / 4ч в истории Binance. Обычно — все часы с той же "
        "волатильностью. Разница — в п.п.; ход — во сколько раз больше или меньше обычного (обычный ход — ×1). "
        "95% интервал — неопределённость этой исторической оценки: насколько она менялась бы на другой выборке "
        "дней. Интервал считается для каждой строки отдельно, без поправки на то, что строк много, и не говорит, "
        "что так будет сейчас.\n"
        "Строки «похожие касания» показывают, как часто в похожих ситуациях на BTCUSDT в 2020–2024 цена первой "
        "доходила до верхней или нижней цены — рядом с тем, что даёт простая геометрия цены («обычно»). Это история, "
        "а не текущая вероятность, и не рекомендация к сделке.\n"
        "Прошлое не гарантирует будущего. Бот не говорит, что делать со сделкой."
    ),
    "en": (
        "\n\nDECISIONS AND HISTORY\n"
        "Corridor — the range the price stayed in in 4 of 5 similar cases over 1h, 4h or 24h. "
        "Built on Binance since 2020: recent volatility, time of day and weekends. "
        "Around CPI and Fed decisions the numerical corridor and the chance to reach are not shown: around the "
        "release, the usual corridor calibration does not apply. "
        "Accuracy is checked on a held-out year and on live forecasts (/accuracy).\n"
        "Chance to reach — how often the price moved that far in one direction within that time in similar conditions. "
        "The model does not forecast direction: the chance is the same up and down.\n"
        "Levels — only what the whole market sees: yesterday's, last week's and last month's highs and lows, "
        "day, week and month opens, Asia, Europe and US sessions, the day VWAP, yesterday's volume POC, round numbers, "
        "places of large liquidations in 24h. Day, week and month are UTC.\n"
        "Random level — a level at the same distance from the period open that means nothing. Beside a real level the "
        "bot shows how the random one behaved and the difference in percentage points (pp); its 95% interval is "
        "computed over the level's periods (days, weeks or months), not over days.\n"
        "After similar — what followed the same 1h / 4h states in Binance history. Usual — all hours with the same "
        "volatility. The difference is in pp; the move is how many times larger or smaller than usual (the usual "
        "move is ×1). The 95% interval is the uncertainty of this historical estimate: how much it would vary on "
        "another sample of days. Each line's interval is computed on its own, with no correction for there being "
        "many lines, and it does not say that this will happen now.\n"
        "The «similar touches» lines show how often, in similar situations on BTCUSDT in 2020–2024, the price "
        "reached the upper or the lower price first — next to what simple price geometry gives («usually»). This is "
        "history, not a current probability, and it does not say what to do with a trade.\n"
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
