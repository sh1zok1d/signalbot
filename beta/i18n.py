"""User-facing string catalog for the descriptive private beta (ru / en).

The formatter takes `lang` and does not build user text outside this module.
Number and clock formatting live here too: storage stays UTC; only rendering
converts to Europe/Kyiv.
"""
from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

LANGS = ("ru", "en")
KYIV = ZoneInfo("Europe/Kyiv")
MINUS = "−"

# English list: the historical patterns, plus the §9 bans. Nothing was removed.
_FORBIDDEN_EN = [
    r"\bbuy\b", r"\bsell\b", r"\b(long|short)\s+now\b", r"\bgo\s+(long|short)\b",
    r"\bentry\b", r"\bentries\b", r"\bstop[- ]?loss\b", r"\btake[- ]?profit\b", r"\btargets?\b",
    r"\bleverage\b", r"\bposition[- ]siz", r"probabilit", r"\blikely\b", r"\bimpulse\b",
    r"\bwin(s|ning)?\b", r"\bloss(es)?\b", r"win[- ]?rate", r"\bmfe\b", r"\bmae\b",
    r"\brecommend", r"\bprofit\b", r"\bsignal\b", r"\bforecast", r"\bpredict",
    r"\bpushing\b", r"\bdumping\b", r"\bwhales\b", r"\bshort covering\b", r"\blong unwind\b",
    r"\bhealthy\b", r"\bcontinuation\b", r"\breversal\b",
]
_FORBIDDEN_EN_CASE = [r"\bLONG\b", r"\bSHORT\b", r"\bBUY\b", r"\bSELL\b"]

# Russian list (§3.1 minimum, plus the §9 equivalents). Case-insensitive, word boundaries.
_FORBIDDEN_RU = [
    r"(?<!\w)купи(?:ть|те)(?!\w)",
    r"(?<!\w)покупай(?:те)?(?!\w)",
    r"(?<!\w)прода(?:й|йте|вай|вайте|ть)(?!\w)",
    r"(?<!\w)входи(?:ть|те)(?!\w)",
    r"(?<!\w)точка входа(?!\w)",
    r"(?<!\w)стоп-лосс(?!\w)",
    r"(?<!\w)тейк-профит(?!\w)",
    r"(?<!\w)цел(?:ь|и)(?!\w)",
    r"(?<!\w)плеч(?:о|а)(?!\w)",
    r"(?<!\w)вероятн\w*",
    r"(?<!\w)скорее всего(?!\w)",
    r"(?<!\w)прогноз\w*",
    r"(?<!\w)предсказ\w*",
    r"(?<!\w)ожида(?:ется|ем|ют)(?!\w)",
    r"(?<!\w)сигнал\w*",
    r"(?<!\w)рекоменд\w*",
    r"(?<!\w)прибыл\w*",
    r"(?<!\w)убыт\w*",
    r"(?<!\w)лонг сейчас(?!\w)",
    r"(?<!\w)шорт сейчас(?!\w)",
    r"(?<!\w)толкают(?!\w)",
    r"(?<!\w)сливают(?!\w)",
    r"(?<!\w)киты(?!\w)",
    r"(?<!\w)закрытие шортов(?!\w)",
    r"(?<!\w)разворот(?!\w)",
    r"(?<!\w)продолжение(?!\w)",
]


class ForbiddenWordingError(ValueError):
    pass


def normalize_lang(lang: str | None) -> str:
    return lang if lang in LANGS else "ru"


def assert_descriptive(text: str, lang: str = "en") -> str:
    """Reject trade-instruction and predictive wording.

    English text is checked against the English list. Russian text is checked
    against that list and the Russian list. Neither list is relaxed.
    """
    plain = re.sub(r"<[^>]+>", " ", text)
    for pat in _FORBIDDEN_EN:
        if re.search(pat, plain, flags=re.IGNORECASE):
            raise ForbiddenWordingError(f"forbidden wording matched {pat!r}")
    for pat in _FORBIDDEN_EN_CASE:
        if re.search(pat, plain):
            raise ForbiddenWordingError(f"forbidden wording matched {pat!r}")
    if normalize_lang(lang) == "ru":
        for pat in _FORBIDDEN_RU:
            if re.search(pat, plain, flags=re.IGNORECASE):
                raise ForbiddenWordingError(f"forbidden wording matched {pat!r}")
    return text


def t(lang: str, key: str, **kw) -> str:
    lang = normalize_lang(lang)
    template = _CATALOG[key][lang]
    return template.format(**kw) if kw else template


def kyiv(dt: datetime) -> datetime:
    return dt.astimezone(KYIV)


def fmt_kyiv_hm(dt: datetime) -> str:
    return kyiv(dt).strftime("%H:%M")


def fmt_kyiv_date_hm(dt: datetime, lang: str) -> str:
    local = kyiv(dt)
    zone = t(lang, "zone")
    return f"{local.strftime('%Y-%m-%d %H:%M')} {zone}"


def fmt_clock(dt: datetime, lang: str) -> str:
    """HH:MM plus the Kyiv label. The label differs by language; the clock does not."""
    return f"{fmt_kyiv_hm(dt)} {t(lang, 'zone')}"


def _group(n: int, lang: str) -> str:
    body = f"{n:,}" if lang == "en" else f"{n:,}".replace(",", " ")
    return body


def fmt_price(value: float, lang: str) -> str:
    """Whole USD, no currency sign (the title already says BTC)."""
    return _group(int(round(float(value))), lang)


def fmt_signed_pct(value: float, lang: str, nd: int = 2) -> str:
    sign = MINUS if value < 0 else "+" if value > 0 else ""
    body = f"{abs(value):.{nd}f}"
    if lang == "ru":
        body = body.replace(".", ",")
    return f"{sign}{body}%"


def fmt_plain_pct(value: float, lang: str, nd: int = 2) -> str:
    body = f"{value:.{nd}f}"
    if lang == "ru":
        body = body.replace(".", ",")
    return f"{body}%"


def fmt_usd(value: float, lang: str, *, signed: bool = False) -> str:
    """$84 млн / $84M. Trailing .0 is dropped. Below $1 the amount is cents-free whole dollars."""
    sign = ""
    if signed:
        sign = MINUS if value < 0 else "+" if value > 0 else ""
    a = abs(float(value))
    if a >= 1e9:
        num, unit = a / 1e9, "usd_b"
    elif a >= 1e6:
        num, unit = a / 1e6, "usd_m"
    elif a >= 1e3:
        num, unit = a / 1e3, "usd_k"
    else:
        return sign + "$" + _group(int(round(a)), lang)
    shown = f"{num:.1f}"
    if shown.endswith(".0"):
        shown = shown[:-2]
    if lang == "ru":
        shown = shown.replace(".", ",")
    sep = " " if lang == "ru" else ""
    return sign + "$" + shown + sep + t(lang, unit)


def fmt_ratio(ratio: float, lang: str) -> str:
    """One decimal and ×. Below 1 is shown. 10 or more prints 10×+."""
    if ratio >= 10:
        return "10×+"
    body = f"{ratio:.1f}"
    if lang == "ru":
        body = body.replace(".", ",")
    return body + "×"


def fmt_funding(rate: float, lang: str) -> str:
    """Tape funding_rate_median is a fraction (0.00006 → 0,006%)."""
    return fmt_plain_pct(rate * 100.0, lang, nd=3)


def na(lang: str) -> str:
    return t(lang, "na")


_CATALOG: dict[str, dict[str, str]] = {
    "zone": {"ru": "(Киев)", "en": "Kyiv"},
    "na": {"ru": "н/д", "en": "n/a"},
    "usd_b": {"ru": "млрд", "en": "B"},
    "usd_m": {"ru": "млн", "en": "M"},
    "usd_k": {"ru": "тыс", "en": "K"},
    "disclaimer": {
        "ru": ("<i>Экспериментальная закрытая бета. Только описание состояния рынка — "
               "не инвестиционный совет и не указание к сделке.</i>"),
        "en": ("<i>Experimental closed beta. Descriptive market-state observation only — "
               "not investment advice and not a trade instruction.</i>"),
    },
    "closed_beta": {
        "ru": "Это закрытая частная бета. Доступ только по приглашению.",
        "en": "This is a closed private beta. Access is by invitation only.",
    },
    "choose_lang": {
        "ru": "Выберите язык / Choose language",
        "en": "Выберите язык / Choose language",
    },
    "btn_ru": {"ru": "Русский", "en": "Русский"},
    "btn_en": {"ru": "English", "en": "English"},
    "btn_join": {"ru": "Вступить", "en": "Join"},
    "btn_event": {"ru": "Событие", "en": "Event"},
    "btn_1h": {"ru": "1ч", "en": "1h"},
    "btn_readiness": {"ru": "Готовность", "en": "Readiness"},
    "btn_details": {"ru": "Подробнее", "en": "Details"},
    "btn_useful": {"ru": "Полезно", "en": "Useful"},
    "btn_noise": {"ru": "Шум", "en": "Noise"},
    "lang_saved": {"ru": "Язык: русский.", "en": "Language: English."},
    "joined": {"ru": "Вы в бете.", "en": "Joined"},
    "privacy": {
        "ru": (
            "<b>Signalbot, закрытая бета — конфиденциальность</b>\n"
            "• Мы храним ваш Telegram id и id чата, чтобы отправлять сообщения беты, "
            "а также голоса «полезно / шум» и статус доставки.\n"
            "• Записи рынка и событий не содержат персональных данных.\n"
            "• /stop приостанавливает все сообщения. /delete_me удаляет ваши данные участника "
            "и исключает вас из беты.\n"
            "• После /stop данные удаляются автоматически через 30 дней.\n"
            "• Это не инвестиционный совет; бот не совершает и не предлагает сделки.\n\n"
            "Нажмите <b>Вступить</b>, чтобы принять условия и войти в бету."
        ),
        "en": (
            "<b>Signalbot closed beta — privacy notice</b>\n"
            "• We store your Telegram user id and chat id to send you beta messages, plus your "
            "Useful/Noise votes and delivery status.\n"
            "• Market/event records contain no personal data.\n"
            "• /stop pauses all messages. /delete_me deletes your participant data and removes "
            "you from the beta.\n"
            "• After /stop, your data is deleted automatically after 30 days.\n"
            "• Nothing here is investment advice; the bot never places or suggests trades.\n\n"
            "Press <b>Join</b> to accept and join the beta."
        ),
    },
    "help": {
        "ru": (
            "<b>Signalbot, закрытая бета — BTCUSDT perpetual (Binance, Bybit, OKX)</b>\n"
            "Бот наблюдает несколько замороженных, детерминированных необычных состояний рынка "
            "и сообщает, когда одно из них наблюдается. Он не говорит, что делать со сделкой.\n\n"
            "/btc — компактное состояние BTC perpetual (спокойно, необычно сейчас, затихло, "
            "накопление истории или данные неполные). Кнопки открывают измерения.\n"
            "/history — недавние эпизоды детектора, с доставкой или без, с фактическими диапазонами\n"
            "/lang — язык сообщений\n"
            "/stop — пауза · /delete_me — удалить ваши данные"
        ),
        "en": (
            "<b>Signalbot closed beta — BTCUSDT perpetual (Binance, Bybit, OKX)</b>\n"
            "The bot watches a few frozen, deterministic, unusual market states and tells you when one "
            "is observed. It does not tell you what to trade.\n\n"
            "/btc — compact BTC perpetual state (calm, unusual now, calmed, history building, "
            "or data incomplete). Buttons hold the measurements.\n"
            "/history — recent detector episodes, pushed or not, with factual follow-up ranges\n"
            "/lang — message language\n"
            "/stop — pause messages · /delete_me — delete your data"
        ),
    },
    "deleted": {
        "ru": "Данные участника беты удалены, и вы исключены из беты.",
        "en": "Your beta participant data was deleted and you were removed from the beta.",
    },
    "not_joined": {
        "ru": "Сообщения на паузе, или вы ещё не вступили. Отправьте /start.",
        "en": "Messages are paused or you have not joined yet. Send /start.",
    },
    "paused": {
        "ru": ("Сообщения на паузе. Отправьте /start, чтобы продолжить. Данные удаляются "
               "автоматически через 30 дней или сразу командой /delete_me."),
        "en": ("Messages paused. Send /start to resume. Your data is deleted "
               "automatically after 30 days, or now with /delete_me."),
    },
    "unknown_cmd": {"ru": "Неизвестная команда. /help", "en": "Unknown command. /help"},
    "not_available": {"ru": "Недоступно", "en": "Not available"},
    "no_evaluation": {"ru": "Оценки ещё нет", "en": "No evaluation yet"},
    "feedback_recorded": {
        "ru": "Отзыв записан (его можно изменить).",
        "en": "Feedback recorded (you can change it).",
    },
    "unknown_episode": {"ru": "Неизвестный эпизод", "en": "Unknown episode"},
    "not_in_context": {
        "ru": "Этого уже нет в текущем контексте",
        "en": "No longer in the current context",
    },
    "title_calm": {"ru": "спокойно", "en": "calm"},
    "title_unusual": {"ru": "необычно сейчас", "en": "unusual now"},
    "title_calmed": {"ru": "затихло", "en": "calmed"},
    "title_ended": {"ru": "событие завершено", "en": "event ended"},
    "title_history": {"ru": "накопление истории", "en": "history building"},
    "title_incomplete": {"ru": "данные неполные", "en": "data incomplete"},
    "screen_title": {"ru": "BTC {rest}", "en": "BTC {rest}"},
    "insufficient": {
        "ru": "Текущих данных недостаточно: отсутствие событий сейчас подтвердить нельзя.",
        "en": "Current observability is insufficient; the absence of events cannot be claimed right now.",
    },
    "projection_missing": {
        "ru": "Подробности эпизода сейчас недоступны.",
        "en": "Episode details are not available right now.",
    },
    "no_unusual": {"ru": "Необычного состояния сейчас нет", "en": "No unusual state now"},
    "not_evaluated_yet": {
        "ru": "Необычные состояния пока не оцениваются",
        "en": "Unusual states are not evaluated yet",
    },
    "measurements_missing": {"ru": "Измерения недоступны", "en": "Measurements are not available"},
    "na_reading": {"ru": "н/д", "en": "n/a"},
    "still_active": {"ru": "Ещё активно", "en": "Still active"},
    "event_ended_line": {"ru": "Событие завершено", "en": "Event has ended"},
    "ended_cap": {"ru": "Завершено по пределу длительности", "en": "Ended at the duration cap"},
    "end_gap": {
        "ru": "Недавнее событие завершилось на пропуске данных",
        "en": "A recent event ended on a data gap",
    },
    "end_not_evaluable": {
        "ru": "Недавнее событие завершилось, потому что данные нельзя было оценить",
        "en": "A recent event ended because data was not evaluable",
    },
    "end_version": {
        "ru": "Недавнее событие завершилось при смене версии",
        "en": "A recent event ended on a version change",
    },
    "last_known": {"ru": "Последнее известное ({hm}): {name}", "en": "Last known ({hm}): {name}"},
    "last_known_ended": {
        "ru": "Последнее известное ({hm}): {name}, завершено",
        "en": "Last known ({hm}): {name}, ended",
    },
    "state_unavailable": {
        "ru": "Текущее состояние события недоступно",
        "en": "Current event state unavailable",
    },
    "also_open": {"ru": "Также открыто: {names}", "en": "Also open: {names}"},
    "ago_just": {"ru": "только что: {name}", "en": "just ended: {name}"},
    "ago": {"ru": "{dur} назад: {name}", "en": "{dur} ago: {name}"},
    "data_line": {"ru": "{status} · данные {clock}", "en": "{status} · data {clock}"},
    "data_only": {"ru": "данные {clock}", "en": "data {clock}"},
    "no_evaluation_line": {"ru": "Оценки ещё нет", "en": "No evaluation yet"},
    "notable_none": {
        "ru": "Нет заметного события за последние {span}",
        "en": "No notable event in the last {span}",
    },
    "h1_incomplete": {"ru": "1ч: неполные данные", "en": "1h: incomplete"},
    "h1_prefix": {"ru": "1ч: {body}", "en": "1h: {body}"},
    "h1_vol": {"ru": "объём {ratio}", "en": "vol {ratio}"},
    "h1_range": {"ru": "диапазон {ratio}", "en": "range {ratio}"},
    "part_price": {"ru": "Цена {arrow}", "en": "Price {arrow}"},
    "part_oi": {"ru": "ОИ {arrow}", "en": "OI {arrow}"},
    "part_vol": {"ru": "Объём {level}", "en": "Volume {level}"},
    "part_taker": {"ru": "Тейкер-поток {arrow}", "en": "Taker flow {arrow}"},
    "level_elevated": {"ru": "повышенный", "en": "elevated"},
    "level_high": {"ru": "высокий", "en": "high"},
    "level_extreme": {"ru": "экстремальный", "en": "extreme"},
    "level_normal": {"ru": "обычный", "en": "normal"},
    "oi_fell_drop": {"ru": "ОИ снизился во время падения", "en": "Open interest fell during the drop"},
    "oi_fell_rise": {"ru": "ОИ снизился во время роста", "en": "Open interest fell during the rise"},
    "oi_rose_rise": {"ru": "ОИ вырос во время роста", "en": "Open interest rose during the rise"},
    "oi_rose_drop": {"ru": "ОИ вырос во время падения", "en": "Open interest rose during the drop"},
    "oi_rose": {"ru": "ОИ вырос", "en": "Open interest rose"},
    "oi_fell": {"ru": "ОИ снизился", "en": "Open interest fell"},
    "oi_level": {"ru": "ОИ {level}", "en": "Open interest {level}"},
    "move_liq": {
        "ru": "{move}, снижение ОИ, повышенные ликвидации {side}",
        "en": "{move}, falling OI, elevated {side}-side liquidations",
    },
    "move_rise": {"ru": "Рост", "en": "Rise"},
    "move_drop": {"ru": "Падение", "en": "Drop"},
    "side_long": {"ru": "лонгов", "en": "long"},
    "side_short": {"ru": "шортов", "en": "short"},
    "liq_count": {
        "ru": "Ликвидации {side} {votes}/{eligible} площадок",
        "en": "{Side}-side liquidations {votes}/{eligible} venues",
    },
    "liq_not_evaluable": {
        "ru": "Ликвидации {side} нельзя оценить",
        "en": "{Side}-side liquidations not evaluable",
    },
    "gap_span": {
        "ru": "История цены/ОИ {span} дн. / {need} дн.",
        "en": "Price/OI history {span}d / {need}d",
    },
    "gap_maturing": {
        "ru": "История цены/ОИ ещё накапливается",
        "en": "Price/OI history still maturing",
    },
    "gap_unavailable": {
        "ru": "Цену и ОИ сейчас нельзя оценить",
        "en": "Price/OI cannot be evaluated right now",
    },
    "gap_off": {"ru": "Цена и ОИ отключены", "en": "Price/OI is switched off"},
    "plain_down": {"ru": "необычное падение", "en": "unusual drop"},
    "plain_up": {"ru": "необычный рост", "en": "unusual rise"},
    "plain_build": {"ru": "набор ОИ в узком диапазоне", "en": "position build-up"},
    "plain_buy": {"ru": "агрессивные покупки", "en": "buyer-initiated flow"},
    "plain_sell": {"ru": "агрессивные продажи", "en": "seller-initiated flow"},
    "plain_liq_long": {"ru": "ликвидации лонгов", "en": "long-side liquidations"},
    "plain_liq_short": {"ru": "ликвидации шортов", "en": "short-side liquidations"},
    "evt_down": {"ru": "необычное падение цены при снижении ОИ", "en": "price + OI contraction down"},
    "evt_up": {"ru": "необычный рост цены при снижении ОИ", "en": "price + OI contraction up"},
    "evt_build": {
        "ru": "набор ОИ при сжатом диапазоне",
        "en": "position build-up with range compression",
    },
    "evt_buy": {"ru": "крайний тейкер-поток (агрессивные покупки)", "en": "taker flow extreme (buyer-initiated)"},
    "evt_sell": {"ru": "крайний тейкер-поток (агрессивные продажи)", "en": "taker flow extreme (seller-initiated)"},
    "evt_liq_long": {"ru": "ликвидационный стресс (ликвидации лонгов)", "en": "liquidation stress (long-side liquidations)"},
    "evt_liq_short": {"ru": "ликвидационный стресс (ликвидации шортов)", "en": "liquidation stress (short-side liquidations)"},
    "desc_down": {
        "ru": ("Движение цены за 5м в нижних 5% последних 30 дней при снижении открытого "
               "интереса в его нижних 10%, не менее чем на 2 площадках."),
        "en": ("5m price move in the bottom 5% of the last 30 days while open "
               "interest fell in its bottom 10%, on at least 2 venues."),
    },
    "desc_up": {
        "ru": ("Движение цены за 5м в верхних 5% последних 30 дней при снижении открытого "
               "интереса в его нижних 10%, не менее чем на 2 площадках."),
        "en": ("5m price move in the top 5% of the last 30 days while open "
               "interest fell in its bottom 10%, on at least 2 venues."),
    },
    "desc_build": {
        "ru": ("Открытый интерес растёт (верхние 20% за 30 дней) при узком 5м диапазоне "
               "(нижние 40%) и объёме не ниже медианы, 45 минут подряд."),
        "en": ("Open interest growing (top 20% of 30d) with a narrow 5m range "
               "(bottom 40%) and at least median volume, for 45 consecutive minutes."),
    },
    "desc_buy": {
        "ru": "Дельта тейкера в верхних 5% последних 30 дней два 5м бакета подряд.",
        "en": "Taker delta in the top 5% of the last 30 days for two consecutive 5m buckets.",
    },
    "desc_sell": {
        "ru": "Дельта тейкера в нижних 5% последних 30 дней два 5м бакета подряд.",
        "en": "Taker delta in the bottom 5% of the last 30 days for two consecutive 5m buckets.",
    },
    "desc_liq_long": {
        "ru": ("Номинал ликвидаций лонгов в верхних 5% собственной 30-дневной истории "
               "не менее чем на 2 площадках с живой лентой в том же 5м бакете."),
        "en": ("Long-side liquidation notional in the top 5% of its own 30d history "
               "on at least 2 venues with a live feed in the same 5m bucket."),
    },
    "desc_liq_short": {
        "ru": ("Номинал ликвидаций шортов в верхних 5% собственной 30-дневной истории "
               "не менее чем на 2 площадках с живой лентой в том же 5м бакете."),
        "en": ("Short-side liquidation notional in the top 5% of its own 30d history "
               "on at least 2 venues with a live feed in the same 5m bucket."),
    },
    "state_early": {"ru": "ранняя", "en": "early"},
    "state_armed": {"ru": "отмечена", "en": "armed"},
    "state_triggered": {"ru": "зафиксирована", "en": "triggered"},
    "state_ended": {"ru": "завершена", "en": "ended"},
    "state_expired": {"ru": "истекла", "en": "expired"},
    "push_title": {"ru": "BTCUSDT perp — СОБЫТИЕ: {name}", "en": "BTCUSDT perp — EVENT: {name}"},
    "push_decision": {
        "ru": "Время решения: {when} (закрытие 5м бакета)",
        "en": "Decision time: {when} (5m bucket close)",
    },
    "push_close": {
        "ru": "Сводная цена на решении: {price} ({venues})",
        "en": "Composite close at decision: {price} ({venues})",
    },
    "push_id": {"ru": "Эпизод {pid} · правила {rules}", "en": "Episode {pid} · rules {rules}"},
    "status_title": {"ru": "BTCUSDT perp — {status}", "en": "BTCUSDT perp — {status}"},
    "status_eval": {
        "ru": "Последняя оценка: 5м бакет закрыт {when}",
        "en": "Last evaluation: 5m bucket closed {when}",
    },
    "status_eval_none": {"ru": "Последняя оценка: ещё нет", "en": "Last evaluation: none yet"},
    "status_episode": {"ru": "• {name} — {state} (с {when})", "en": "• {name} — {state} (since {when})"},
    "status_context": {"ru": "Контекст (5м, по площадкам)", "en": "Context (5m, cross-venue)"},
    "status_price": {"ru": "движение цены: {v}", "en": "price move: {v}"},
    "status_oi": {"ru": "изменение ОИ: {v}", "en": "OI change: {v}"},
    "status_range": {"ru": "ширина диапазона: {v}", "en": "range width: {v}"},
    "status_volume": {"ru": "объём: {v}", "en": "volume: {v}"},
    "status_ref": {"ru": "сводная цена: {price} ({venues})", "en": "composite close: {price} ({venues})"},
    "status_gated": {"ru": "сейчас не оценивается: {names}", "en": "not evaluable now: {names}"},
    "rank_na": {"ru": "н/д", "en": "n/a"},
    "rank_immature": {"ru": "нельзя оценить (история: {tier})", "en": "not evaluable ({tier} history)"},
    "rank_pct": {"ru": "{n}-й перцентиль за 30 дн.", "en": "{n}th pct of 30d"},
    "history_title": {
        "ru": "История детектора (все эпизоды, с доставкой или без)",
        "en": "Detector history (all episodes, pushed or not)",
    },
    "history_empty": {"ru": "Эпизодов ещё нет.", "en": "No episodes recorded yet."},
    "history_note": {
        "ru": ("Диапазоны — абсолютное движение (макс − мин) после времени решения; "
               "* = пересмотрено после исправления данных."),
        "en": ("Ranges are absolute (max − min) moves after the decision time; "
               "* = revised after a data correction."),
    },
    "history_corrected": {"ru": " ⚠ вход исправлен", "en": " ⚠ corrected input"},
    "history_times": {
        "ru": "открыт {opened}; зафиксирован {triggered}; доставка {push}",
        "en": "opened {opened}; triggered {triggered}; push {push}",
    },
    "push_none": {"ru": "без доставки (не зафиксировано)", "en": "no push (not triggered)"},
    "push_pending": {"ru": "ДОСТАВКА (ожидает)", "en": "PUSH (pending)"},
    "follow_pending": {"ru": "данные после события ещё не собраны", "en": "follow-up pending"},
    "range_complete": {"ru": "{h} диапазон {pct}%{mark}", "en": "{h} range {pct}%{mark}"},
    "details_rules": {"ru": "Правила {ver} ({digest})", "en": "Rules {ver} ({digest})"},
    "details_transition": {"ru": "• {when}: {state} ({reason})", "en": "• {when}: {state} ({reason})"},
    "details_close": {"ru": "Сводная цена на решении: {price}", "en": "Composite close at decision: {price}"},
    "details_outcome": {
        "ru": "{h}: диапазон {rng}%, макс вверх {up}, макс вниз {down}, закрытие {close}{rev}",
        "en": "{h}: range {rng}%, max up {up}, max down {down}, close {close}{rev}",
    },
    "details_revised": {"ru": " (пересмотрено)", "en": " (revised)"},
    "details_corrected": {"ru": "⚠ вход исправлен: {note}", "en": "⚠ corrected input: {note}"},
    "dur_m": {"ru": "{n} мин", "en": "{n}m"},
    "dur_h": {"ru": "{n} ч", "en": "{n}h"},
    "dur_hm": {"ru": "{h} ч {m} мин", "en": "{h}h{m:02d}m"},
    "event_head": {"ru": "СОБЫТИЕ · {name}", "en": "EVENT · {name}"},
    "event_since": {"ru": "Ещё активно · с {clock}", "en": "Still active · since {clock}"},
    "event_ended_at": {"ru": "Завершено · {clock}", "en": "Ended · {clock}"},
    "why_window": {"ru": "Почему замечено ({window}):", "en": "Why it was noticed ({window}):"},
    "anchor_metrics": {
        "ru": "Цена {price} · диапазон {range} · объём {vol}{level}",
        "en": "Price {price} · range {range} · volume {vol}{level}",
    },
    "anchor_oi": {"ru": "ОИ {med}: {venues}", "en": "OI {med}: {venues}"},
    "anchor_oi_na": {"ru": "ОИ: {venues}", "en": "OI: {venues}"},
    "taker_line": {"ru": "Тейкер-поток: {side}, нетто {amt}", "en": "Taker flow: {side}, net {amt}"},
    "taker_flat": {"ru": "Тейкер-поток: нетто {amt}", "en": "Taker flow: net {amt}"},
    "taker_na": {"ru": "Тейкер-поток: {na}", "en": "Taker flow: {na}"},
    "taker_buyers": {"ru": "покупатели", "en": "buyers"},
    "taker_sellers": {"ru": "продавцы", "en": "sellers"},
    "liq_line": {"ru": "Ликвидации {side}: {body}", "en": "{Side} liquidations: {body}"},
    "liq_long_name": {"ru": "лонгов", "en": "Long"},
    "liq_short_name": {"ru": "шортов", "en": "Short"},
    "liq_footnote": {
        "ru": "≥ — нижняя граница: Binance передаёт не все ликвидации.",
        "en": "≥ — lower bound: Binance does not report every liquidation.",
    },
    "ref_line": {"ru": "ref {ep} · view {vid}", "en": "ref {ep} · view {vid}"},
    "ref_view_only": {"ru": "view {vid}", "en": "view {vid}"},
    "h1_head": {"ru": "ПОСЛЕДНИЙ ЧАС · {window} {zone}", "en": "LAST HOUR · {window} {zone}"},
    "h1_price_range": {
        "ru": "Цена {price} · диапазон {range}{ratio}",
        "en": "Price {price} · range {range}{ratio}",
    },
    "h1_volume": {"ru": "Объём {vol}{ratio}", "en": "Volume {vol}{ratio}"},
    "h1_ratio": {"ru": " ({ratio} от обычного для этого часа)", "en": " ({ratio} usual for this hour)"},
    "h1_incomplete_body": {"ru": "1ч: неполные данные", "en": "1h: incomplete"},
    "funding_now": {
        "ru": "Фандинг сейчас {rate} (медиана бирж)",
        "en": "Funding now {rate} (venue median)",
    },
    "funding_na": {"ru": "Фандинг сейчас {na}", "en": "Funding now {na}"},
    "ready_title": {
        "ru": "Готовность детектора — бакет закрыт {when}",
        "en": "Detector readiness — bucket closed {when}",
    },
    "ready_intro": {
        "ru": ("Зрелость требует {days} дней достоверной истории на каждый нужный перцентиль "
               "(от самого раннего достоверного образца, не от даты запуска)."),
        "en": ("Maturity needs {days} days of valid history per required percentile "
               "(counted from the earliest valid sample, not from deployment)."),
    },
    "ready_word": {"ru": "готово", "en": "ready"},
    "ready_building": {"ru": "накопление истории", "en": "history building"},
    "ready_unavailable": {"ru": "данные недоступны", "en": "data unavailable"},
    "ready_degraded": {"ru": "деградация", "en": "degraded"},
    "ready_disabled": {"ru": "отключено", "en": "disabled"},
    "ready_partly": {
        "ru": "частично готово ({a}/{b} правил) · {text}",
        "en": "partly ready ({a}/{b} rules) · {text}",
    },
    "ready_span": {"ru": "{name} {span} дн. / {need} дн.", "en": "{name} {span}d / {need}d"},
    "ready_member": {"ru": "• {name}: {status}{reason}", "en": "• {name}: {status}{reason}"},
    "ready_metric": {
        "ru": "{name}: {tier} · {n} образцов · охват {span} дн.",
        "en": "{name}: {tier} · {n} samples · {span}d span",
    },
    "ready_venue": {"ru": "{ex}: {state}{reason} · {tier} · охват {span} дн.",
                    "en": "{ex}: {state}{reason} · {tier} · {span}d span"},
    "ready_footer": {
        "ru": "Модель чтения {ver}. Изменения готовности не отправляют уведомления.",
        "en": "Read model {ver}. Readiness changes never send notifications.",
    },
    "hist_price": {"ru": "история цены", "en": "price history"},
    "hist_oi": {"ru": "история ОИ", "en": "OI history"},
    "hist_range": {"ru": "история диапазона", "en": "range history"},
    "hist_volume": {"ru": "история объёма", "en": "volume history"},
    "hist_taker": {"ru": "история тейкер-потока", "en": "taker-flow history"},
    "hist_liq_long": {"ru": "история ликвидаций лонгов", "en": "long-side liquidation history"},
    "hist_liq_short": {"ru": "история ликвидаций шортов", "en": "short-side liquidation history"},
    "fam_price": {"ru": "цены", "en": "price"},
    "fam_oi": {"ru": "ОИ", "en": "OI"},
    "fam_volume": {"ru": "объёма", "en": "volume"},
    "fam_taker": {"ru": "тейкер-потока", "en": "taker flow"},
    "reason_venues": {
        "ru": "меньше {n} пригодных площадок для {fam}",
        "en": "fewer than {n} usable venues for {fam}",
    },
    "reason_eligible": {
        "ru": "меньше требуемых пригодных живых лент",
        "en": "fewer than the required eligible live feeds",
    },
    "reason_value": {"ru": "текущее значение недоступно", "en": "current value unavailable"},
    "reason_pct": {"ru": "перцентиль недоступен", "en": "percentile unavailable"},
    "reason_not_mat": {"ru": "последний бакет не материализован", "en": "latest bucket not materialized"},
    "reason_late": {"ru": "оценка запоздала", "en": "evaluation late"},
    "reason_stale": {"ru": "входы изменились во время оценки", "en": "inputs changed during evaluation"},
    "reason_off": {"ru": "выключено", "en": "switched off"},
    "reason_not_eval": {"ru": "не оценено", "en": "not evaluated"},
}
