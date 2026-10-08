"""User-facing string catalog for the descriptive private beta (ru / en).

The formatter takes `lang` and does not build user text outside this module.
Number and clock formatting live here too: storage stays UTC; only rendering
converts, to the recipient's time zone (Europe/Kyiv unless the participant set one with
/tz; backlog C5). Scheduling logic that is defined in Kyiv time uses `kyiv()` / `KYIV`.
"""
from __future__ import annotations

import re
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone, tzinfo
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

LANGS = ("ru", "en")
KYIV = ZoneInfo("Europe/Kyiv")
MINUS = "−"

# ---- the recipient's time zone (backlog C5) ---------------------------------------------------
# A participant's `tz` is an IANA name («Europe/Warsaw») or a fixed offset «UTC+03:00»; NULL is Kyiv.
# The bot and the notifier set it for the duration of one rendering (`render_tz`); every clock the
# catalog formats then reads it. Nothing is stored in local time.
_RENDER_TZ: ContextVar[tzinfo] = ContextVar("beta_render_tz", default=KYIV)
# the sign is required: «[+\-−]» (a bare «[+-−]» is the range U+002B…U+2212, digits and letters included,
# which read «10» as «UTC+00:00»); a bare number is refused with the hint to add a sign or name a city
_OFFSET_RE = re.compile(r"^(?:utc|gmt)?\s*([+\-−])\s*(\d{1,2})(?::?(\d{2}))?$", re.I)
# every spelling of Kyiv is the default zone (stored NULL), labelled «Киев», never an offset
KYIV_ALIASES = frozenset({"kyiv", "kiev", "киев", "київ", "europe/kyiv", "europe/kiev"})


def tz_of(name: Optional[str]) -> tzinfo:
    """The tzinfo of a stored `tz` value; Kyiv for NULL or anything unreadable (never an error)."""
    if not name or name.strip().lower() in KYIV_ALIASES:
        return KYIV
    m = _OFFSET_RE.match(name.strip())
    if m:
        sign = -1 if m.group(1) in "-−" else 1
        return timezone(sign * timedelta(hours=int(m.group(2)), minutes=int(m.group(3) or 0)))
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return KYIV


def is_fixed_offset(stored: Optional[str]) -> bool:
    """A stored zone that is a fixed offset («UTC+03:00»): it never follows summer or winter time."""
    return bool(stored) and _OFFSET_RE.match(stored.strip()) is not None


def parse_tz(text: Optional[str]) -> Optional[str]:
    """The stored form of a /tz argument, or None: an IANA name («Europe/Warsaw», case as typed is
    normalised by the zone database) or a signed offset «+3», «UTC-5», «+05:30» (stored «UTC+05:30»).
    A bare number («10») is not an offset: None. Kyiv in any spelling is not stored here (see KYIV_ALIASES)."""
    s = (text or "").strip()
    m = _OFFSET_RE.match(s)
    if m:
        h, mm = int(m.group(2)), int(m.group(3) or 0)
        if h > 14 or mm >= 60 or (h == 14 and mm):
            return None
        sign = "-" if m.group(1) in "-−" else "+"
        return f"UTC{sign}{h:02d}:{mm:02d}"
    if not s or "/" not in s or len(s) > 64:
        return None
    try:
        ZoneInfo(s)
        return s
    except (ZoneInfoNotFoundError, ValueError):
        pass
    from zoneinfo import available_timezones
    return next((z for z in sorted(available_timezones()) if z.lower() == s.lower()), None)


@contextmanager
def render_tz(name: Optional[str]):
    """Render everything inside in the participant's time zone."""
    token = _RENDER_TZ.set(tz_of(name))
    try:
        yield
    finally:
        _RENDER_TZ.reset(token)


def use_render_tz(name: Optional[str]) -> None:
    """Set the rendering zone for the rest of the current task step (the bot's update handling resets it)."""
    _RENDER_TZ.set(tz_of(name))


def current_tz() -> tzinfo:
    return _RENDER_TZ.get()


def zone_name(lang: str, at: Optional[datetime] = None) -> str:
    """«Киев» / «Kyiv» for Kyiv; the city of any other named zone («Warsaw», «New York»), right on every
    date whatever summer or winter time; «UTC+3» / «UTC+5:30» for a fixed offset (which never changes)."""
    tz = _RENDER_TZ.get()
    if tz is KYIV or getattr(tz, "key", None) in ("Europe/Kyiv", "Europe/Kiev"):
        return "Киев" if normalize_lang(lang) == "ru" else "Kyiv"
    key = getattr(tz, "key", None)
    if key and not key.startswith(("Etc/", "UTC", "GMT")):
        # a city in Latin letters on the Russian side too (the zone database's own name)
        return key.rsplit("/", 1)[-1].replace("_", " ")
    # a fixed offset, or Etc/GMT±N (POSIX: «Etc/GMT+5» is UTC−5; review of #379), printed as the offset
    off = (at or datetime.now(timezone.utc)).astimezone(tz).utcoffset() or timedelta(0)
    total = int(off.total_seconds() // 60)
    sign = "+" if total >= 0 else MINUS
    h, m = divmod(abs(total), 60)
    return f"UTC{sign}{h}" + (f":{m:02d}" if m else "")

# PRODUCT_DECISION_V2 §3 (owner, 2026-10-03): forecasts, probabilities and historical
# statistics are allowed; direct trade calls and hype are not. The English list applies to
# every text; Russian text is also checked against the Russian list. The V0.2 / V1 lists that
# banned forecasting vocabulary are superseded (history: git, PRODUCT_DECISION_V2 §5).
_FORBIDDEN_EN = [
    r"\bbuy\s+now\b", r"\bsell\s+now\b", r"\b(long|short)\s+now\b", r"\bgo\s+(long|short)\b",
    r"\b(open|enter)\s+(a\s+)?(long|short)\b", r"\bentry\s+points?\b", r"\btake[- ]?profit\b",
    r"\bprice\s+targets?\b", r"\btargets?\b", r"\brecommend", r"\bguaranteed\b", r"\byou\s+should\b",
    r"\bto\s+the\s+moon\b", r"\bpump(ing)?\b", r"\bdump(ing)?\b",
    # instructions to act ("buy BTC at 64000", "sell here", "entry: 64,000", "stop loss at", "10x leverage");
    # the nouns the texts use (buyers, buyer-initiated, aggressive selling, a stop 0.5% away) stay allowed
    r"\b(buy|sell|long|short)(ing)?\s+(btc|bitcoin|here|there|at|from|above|below|the\s+(dip|break|top|bottom))\b",
    r"\bentry\s*[:=@]", r"\benter\s+(here|at|now|above|below)\b",
    r"\bstop[- ]?loss\s+(at|@|to|below|above)\b", r"\b(set|place|move)\s+(your|a|the)\s+stop\b",
    r"\b\d+\s*x\s+leverage\b", r"\b(use|with|take)\s+\d+\s*x\b",
]
_FORBIDDEN_EN_CASE = [r"\bLONG\b", r"\bSHORT\b", r"\bBUY\b", r"\bSELL\b"]

_FORBIDDEN_RU = [
    r"(?<!\w)купи(?:ть|те)?(?!\w)",
    r"(?<!\w)покупай(?:те)?(?!\w)",
    r"(?<!\w)прода(?:й|йте|вай|вайте|ть)(?!\w)",
    r"(?<!\w)(?:входи|заходи)(?:ть|те)?(?!\w)",
    r"(?<!\w)точк[аиуе] входа(?!\w)",
    r"(?<!\w)(?:открывай|открывайте|открой|откройте)\s+(?:лонг|шорт)\w*",
    r"(?<!\w)(?:лонг|шорт)\s+сейчас(?!\w)",
    r"(?<!\w)(?:лонгуй|шорти)\w*",
    r"(?<!\w)тейк-профит\w*",
    r"(?<!\w)цел(?:ь|и|ью|ей)(?!\w)",
    r"(?<!\w)таргет\w*",
    r"(?<!\w)гарантированн\w*",
    r"(?<!\w)(?:рекомендуем|советуем)(?!\w)",
    r"(?<!\w)срочно(?!\w)",
    r"(?<!\w)памп\w*",
    r"(?<!\w)дамп\w*",
    r"(?<!\w)ракет\w*",
    r"(?<!\w)обвал\w*",
    # first-person / imperative calls to act («покупаем», «входим», «шорт от 66000», «вход в лонг»)
    r"(?<!\w)(?:покупаем|покупаю|прода[её]м|продаю|входим|вхожу|заходим|захожу)(?!\w)",
    r"(?<!\w)(?:открываем|открываю|берите|бери|бер[её]м|беру|ставим|ставьте|набираем|набирайте)\s+(?:в\s+)?(?:лонг|шорт)\w*",
    r"(?<!\w)(?:лонг|шорт)\s+(?:от|с|по|на)\s+\d",
    r"(?<!\w)вход\w*\s+(?:в\s+(?:лонг|шорт)|на\s+\d|по\s+\d|от\s+\d)",
    r"(?<!\w)стоп(?:-лосс)?\w*\s+(?:ставим|ставьте|поставьте|переносим|переносите)(?!\w)",
    r"(?<!\w)(?:ставим|ставьте|поставьте|переносим|переносите)\s+стоп\w*",
    r"(?<!\w)плеч\w*\s+[xх]?\d+", r"(?<!\w)[xх]\d+\s+плеч\w*",
    # attributions nobody can observe (kept from V0.2: they are claims, not forecasts)
    r"(?<!\w)толкают(?!\w)",
    r"(?<!\w)сливают(?!\w)",
    r"(?<!\w)киты(?!\w)",
    r"(?<!\w)закрытие шортов(?!\w)",
]


class ForbiddenWordingError(ValueError):
    pass


def normalize_lang(lang: str | None) -> str:
    return lang if lang in LANGS else "ru"


def assert_descriptive(text: str, lang: str = "en") -> str:
    """Reject direct trade calls and hype (PRODUCT_DECISION_V2 §3).

    English text is checked against the English list. Russian text is checked
    against that list and the Russian list.
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
    if key == "zone":                       # «(Киев)» / «Kyiv», or the participant's zone (C5)
        name = zone_name(lang)
        return f"({name})" if lang == "ru" else name
    template = _CATALOG[key][lang]
    if "{zone" in template:                 # every clock label follows the participant's zone
        kw.setdefault("zone", t(lang, "zone"))
        kw.setdefault("zone_name", zone_name(lang))
    return template.format(**kw) if kw else template


def kyiv(dt: datetime) -> datetime:
    """Kyiv wall clock, for logic defined in Kyiv time (quiet hours of a participant without a zone,
    the weekend flag, the owner's report); user-facing clocks use `local`."""
    return dt.astimezone(KYIV)


def local(dt: datetime) -> datetime:
    """The recipient's wall clock (backlog C5)."""
    return dt.astimezone(_RENDER_TZ.get())


def fmt_kyiv_hm(dt: datetime) -> str:
    """HH:MM on the recipient's clock (the name stays from the Kyiv-only days)."""
    return local(dt).strftime("%H:%M")


def fmt_kyiv_date_hm(dt: datetime, lang: str) -> str:
    loc = local(dt)
    return f"{loc.strftime('%Y-%m-%d %H:%M')} {t(lang, 'zone')}"


def fmt_clock(dt: datetime, lang: str) -> str:
    """HH:MM plus the zone label («(Киев)» / «Kyiv», or «(UTC+3)»). The label differs by language."""
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
    "zone": {"ru": "(Киев)", "en": "Kyiv"},              # t() renders the participant's zone (C5)
    "na": {"ru": "н/д", "en": "n/a"},
    "usd_b": {"ru": "млрд", "en": "B"},
    "usd_m": {"ru": "млн", "en": "M"},
    "usd_k": {"ru": "тыс", "en": "K"},
    "disclaimer": {
        "ru": ("<i>Экспериментальная закрытая бета. Статистика и описание рынка — "
               "не инвестиционный совет и не указание к сделке.</i>"),
        "en": ("<i>Experimental closed beta. Market statistics and description — "
               "not investment advice and not a trade instruction.</i>"),
    },
    "closed_beta": {
        "ru": "Это закрытая частная бета. Доступ только по приглашению.",
        "en": "This is a closed private beta. Access is by invitation only.",
    },
    "waitlist_offer": {
        "ru": "Бот в закрытой бете. / The bot is in closed beta.",
        "en": "Бот в закрытой бете. / The bot is in closed beta.",
    },
    "btn_request_access": {
        "ru": "Хочу доступ / Request access",
        "en": "Хочу доступ / Request access",
    },
    "waitlist_consent": {
        "ru": ("Сохраним ваш Telegram ID, чтобы пригласить вас; удалить: /delete_me. / "
               "We will keep your Telegram ID so we can invite you; delete: /delete_me."),
        "en": ("Сохраним ваш Telegram ID, чтобы пригласить вас; удалить: /delete_me. / "
               "We will keep your Telegram ID so we can invite you; delete: /delete_me."),
    },
    "access_granted": {
        "ru": "Доступ открыт, нажмите /start / Access granted, press /start",
        "en": "Доступ открыт, нажмите /start / Access granted, press /start",
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
    "btn_24h": {"ru": "24ч", "en": "24h"},
    "btn_terms": {"ru": "Термины", "en": "Glossary"},
    "btn_readiness": {"ru": "Готовность", "en": "Readiness"},
    "btn_btc_now": {"ru": "📊 BTC сейчас", "en": "📊 BTC now"},
    "btn_other_assets": {"ru": "Другие монеты", "en": "Other coins"},
    "other_assets_reply": {"ru": "Пока доступен только BTC. Интерес к другим монетам записан.",
                           "en": "Only BTC is available for now. Your interest in other coins is noted."},
    "btn_details": {"ru": "Подробнее", "en": "Details"},
    "btn_useful": {"ru": "Полезно", "en": "Useful"},
    "btn_mute": {"ru": "🔕 Не присылать такие", "en": "🔕 Stop these"},
    "btn_unmute": {"ru": "↩️ Вернуть", "en": "↩️ Undo"},
    "mute_ok": {"ru": "Больше не присылаю: {name}. Вернуть — кнопкой ниже или /push {cmd} on.",
                "en": "I will not send these any more: {name}. Undo with the button below or /push {cmd} on."},
    "unmute_ok": {"ru": "Снова присылаю: {name}.", "en": "Sending these again: {name}."},
    "mute_name_hours": {"ru": "сообщения о необычном часе", "en": "unusual-hour messages"},
    "mute_name_levels": {"ru": "касания уровней", "en": "level touches"},
    "mute_name_events": {"ru": "напоминания о CPI и ФРС", "en": "CPI and Fed reminders"},
    "mute_name_moves": {"ru": "резкие движения", "en": "sharp moves"},
    "mute_name_weekly": {"ru": "итоги недели", "en": "the weekly report"},
    "btn_noise": {"ru": "Шум", "en": "Noise"},
    "lang_saved": {"ru": "Язык: русский.", "en": "Language: English."},
    "joined": {"ru": "Вы в бете.", "en": "Joined"},
    "welcome": {
        "ru": (
            "Добро пожаловать в Signalbot (закрытая бета).\n"
            "Бот следит за BTC-фьючерсами на Binance, Bybit и OKX. Он не говорит, покупать или "
            "продавать, а показывает: насколько сейчас рискованно (коридор и /risk), где максимумы и "
            "минимумы прошлого дня, недели и месяца и другие уровни (/levels), что было в похожих ситуациях раньше и что сегодня "
            "в календаре (/events).\n"
            "/btc — состояние рынка сейчас. /help — все команды.\n"
            "/terms — что значат термины.\n"
            "/lang — сменить язык.\n"
            "Это статистика и описание рынка, не торговые советы.\n"
            "Отзывы и вопросы: /feedback ваш текст"
        ),
        "en": (
            "Welcome to Signalbot (closed beta).\n"
            "The bot watches BTC perpetual futures on Binance, Bybit and OKX. It never says whether "
            "to buy or sell; it shows how risky the market is now (corridor and /risk), where the "
            "previous day's, week's and month's highs and lows and other levels are (/levels), what happened in similar situations before and "
            "what is in today's calendar (/events).\n"
            "/btc — the market right now. /help — all commands.\n"
            "/terms — what the terms mean.\n"
            "/lang — change the language.\n"
            "These are statistics and market description, not trading advice.\n"
            "Feedback and questions: /feedback your text"
        ),
    },
    "welcome_push": {
        "ru": ("Бот сам пришлёт короткое сообщение при первом касании важного уровня, за 30 минут до CPI "
               "или ФРС и при резком движении. Настроить: /push."),
        "en": ("The bot will message you at the first touch of a key level, 30 minutes before CPI or the Fed "
               "and on a sharp move. Settings: /push."),
    },
    "feedback_usage": {
        "ru": "Напишите отзыв: /feedback ваш текст",
        "en": "Write your feedback: /feedback your text",
    },
    "feedback_too_long": {
        "ru": "Отзыв длиннее {n} символов. Сократите текст, ничего не сохранено.",
        "en": "That feedback is longer than {n} characters. Shorten it; nothing was stored.",
    },
    "feedback_daily_limit": {
        "ru": "Сегодня уже {n} отзывов. Новый можно отправить завтра.",
        "en": "Already {n} feedback messages today. Another one can be sent tomorrow.",
    },
    # feedback in the bot (backlog H1–H4)
    "btn_idea": {"ru": "💡 Идея / чего не хватает", "en": "💡 An idea / what is missing"},
    "idea_prompt": {"ru": "Напишите одним сообщением: идея или чего не хватает. Это прочитает команда. Отменить: /cancel",
                    "en": "Write it in one message: an idea or what is missing. The team reads it. Cancel: /cancel"},
    "idea_thanks": {"ru": "Спасибо! Идея передана команде.", "en": "Thanks! Your idea was sent to the team."},
    "cancel_ok": {"ru": "Хорошо, отменено.", "en": "Fine, cancelled."},
    "noise_reason_q": {"ru": "Что не так? Один ответ:", "en": "What was wrong? One answer:"},
    "reason_wrong": {"ru": "Неверно", "en": "Wrong"},
    "reason_not_for_me": {"ru": "Не про меня", "en": "Not for me"},
    "reason_too_often": {"ru": "Слишком часто", "en": "Too often"},
    "reason_late": {"ru": "Поздно", "en": "Too late"},
    "stop_reason_q": {"ru": "Если не сложно — почему пауза? Один ответ:", "en": "If you do not mind — why the pause? One answer:"},
    "reason_not_needed": {"ru": "Не нужен", "en": "I do not need it"},
    "reason_too_many": {"ru": "Слишком много сообщений", "en": "Too many messages"},
    "reason_unclear": {"ru": "Непонятно, что он показывает", "en": "It is unclear what it shows"},
    "reason_other": {"ru": "Другое", "en": "Something else"},
    "reason_thanks": {"ru": "Спасибо, записал.", "en": "Thanks, noted."},
    # J4: a plain message (not a command) reaches the team as feedback; the answer comes here
    # J1 onboarding: live /btc, a sample message, the /check offer (first value within a minute)
    "onboard_btc_head": {"ru": "Вот BTC прямо сейчас:", "en": "Here is BTC right now:"},
    "onboard_sample_head": {"ru": "Так выглядит сообщение о касании уровня. Это пример, не текущий рынок:",
                            "en": "This is what a level-touch message looks like. An example, not the current market:"},
    "onboard_check": {"ru": "Проверьте свой уровень: /check и цена, например /check 65000 — шанс дойти за 1ч / 4ч / 24ч "
                            "и что бывало у таких уровней. Или кнопкой ниже. Как читать бота: /guide",
                      "en": "Check a level of your own: /check and a price, e.g. /check 65000 — the chance to reach it "
                            "within 1h / 4h / 24h and what such levels did. Or tap below. How to read the bot: /guide"},
    "btn_guide": {"ru": "📖 Как читать бота", "en": "📖 How to read the bot"},
    # J2 «как читать бота»: an annotated push and briefing
    "guide": {
        "ru": ("<b>Как читать бота</b>\n\n"
               "<b>Сообщение о необычном часе</b>\n"
               "«13:05–14:05 (Киев) · задержка 45 с» — окно часа и через сколько пришло сообщение.\n"
               "«Похоже на …» — описание состояния, не причина и не совет.\n"
               "«падение глубже, чем в 95% часовых окон за 30 дней» — насколько это необычно и с чем сравнивали.\n"
               "«OI · Delta · Биржи: 3 из 3» — открытый интерес, перевес рыночных покупок или продаж, согласие бирж.\n"
               "«Рядом: ↑ … · ↓ …» — ближайшие уровни.\n\n"
               "<b>Сообщение об уровне</b>\n"
               "«цена вошла в зону …» — цена впервые за день, неделю или месяц дошла до такого уровня.\n"
               "«первой была — верхняя … · нижняя … · ни одна … (обычно …)» — как часто в похожих касаниях "
               "2020–2024 (N — сколько их было) цена сначала доходила до верхней или нижней цены или ни до одной; "
               "«обычно» — что дала бы случайная цена с той же волатильностью из той же точки, без учёта уровня. "
               "Это частоты прошлого, не прогноз направления.\n\n"
               "<b>Утренняя сводка</b>\n"
               "«Сейчас · 1ч и 4ч» — состояние рынка за час и за 4 часа.\n"
               "«Коридор: 4ч … · 24ч …» — где цена оставалась в 4 из 5 похожих случаев; строка ниже — как часто так "
               "и было, на истории или вживую.\n"
               "«Уровни» — максимумы и минимумы прошлого дня, недели и месяца, открытия периодов, круглые цены и другие уровни из /terms; «🎯 Проверить» — шанс до них дойти.\n"
               "«События в ближайшие сутки» — CPI и ФРС: рядом с ними числовые оценки не показываем.\n\n"
               "<b>Числа</b>\n"
               "«≈ 41%» — шанс дойти; рядом — как такие оценки сбывались: «говорили 40% → было 39% (N=120)».\n"
               "«исторически в 41% случаев» — так бывало раньше, без проверки как прогноз.\n"
               "«+4,0 п.п.; 95% интервал …» — разница с обычным и её разброс; N — сколько было случаев.\n"
               "Бот не говорит, покупать или продавать."),
        "en": ("<b>How to read the bot</b>\n\n"
               "<b>Unusual-hour message</b>\n"
               "“13:05–14:05 Kyiv · delay 45 s” — the hour and how long the message took.\n"
               "“Looks like …” — a description of the state, not a cause and not advice.\n"
               "“a fall deeper than 95% of 1h windows over 30 days” — how unusual it is and what it was compared with.\n"
               "“OI · Delta · Exchanges: 3 of 3” — open interest, the balance of market buys and sells, how many "
               "exchanges agree.\n"
               "“Nearby: ↑ … · ↓ …” — the nearest levels.\n\n"
               "<b>Level message</b>\n"
               "“the price entered the … zone” — the first time this day, week or month the price reached such a level.\n"
               "“reached first — the upper … · the lower … · neither … (usually …)” — how often, in similar touches in "
               "2020–2024 (N is how many), the price reached the upper or the lower price first, or neither; "
               "“usually” — what a random price path with the same volatility from the same point would give, ignoring "
               "the level. These are past frequencies, not a direction forecast.\n\n"
               "<b>Morning briefing</b>\n"
               "“Now · 1h and 4h” — the market state over the hour and over 4 hours.\n"
               "“Corridor: 4h … · 24h …” — where the price stayed in 4 of 5 similar cases; the line below — how often "
               "that held, on history or live.\n"
               "“Levels” — the previous day's, week's and month's highs and lows, period opens, round prices and the other levels in /terms; “🎯 Check” — the chance to reach them.\n"
               "“Events within 24 hours” — CPI and the Fed: no numerical estimates around them.\n\n"
               "<b>Numbers</b>\n"
               "“≈ 41%” — the chance to reach; beside it, how such estimates turned out: “said 40% → was 39% (N=120)”.\n"
               "“historically in 41% of cases” — what happened before, not checked as a forecast.\n"
               "“+4.0 pp; 95% interval …” — the difference from usual and its spread; N is the number of cases.\n"
               "The bot never says whether to buy or sell."),
    },
    "tier_closed": {"ru": "Это сейчас недоступно.", "en": "This is not available now."},
    "plain_to_team": {"ru": "Передал команде — ответ придёт сюда. Команды: /help",
                      "en": "Passed to the team — the answer comes here. Commands: /help"},
    # I2 / U3 (PRODUCT_FIRST_DECISION_V1 §7): the offer on days 21–25, to everyone enrolled, churned included
    "u3_offer": {"ru": "Бета подходит к концу. Если бот был полезен, его можно продолжить: {price}. Оплата: {method}. "
                       "Деньги можно вернуть в течение 30 дней. Вопросы и оплата — через /feedback или ответом сюда.",
                 "en": "The beta is ending. If the bot was useful, you can keep it: {price}. Payment: {method}. "
                       "You can get the money back within 30 days. Questions and payment: /feedback or a reply here."},
    "feedback_thanks": {
        "ru": "Спасибо! Отзыв передан команде.",
        "en": "Thanks! Your feedback was sent to the team.",
    },
    # A3: the ready outage notice the owner sends with /admin_outage start|end
    "outage_start": {"ru": "⚠️ У нас сбой: данные или сообщения бота могут задерживаться или не приходить. "
                           "Цифры, показанные сейчас, могут быть устаревшими. Мы чиним и напишем, когда всё заработает.",
                     "en": "⚠️ We have an outage: the bot's data or messages may be late or missing. "
                           "Numbers shown now may be out of date. We are fixing it and will tell you when it works again."},
    "outage_end": {"ru": "✅ Сбой устранён: бот снова получает данные и присылает сообщения. "
                         "Если что-то выглядит странно, напишите /feedback.",
                   "en": "✅ The outage is over: the bot has its data again and sends messages. "
                         "If anything looks odd, write /feedback."},
    "team_reply": {
        "ru": "Ответ команды Signalbot:\n",
        "en": "Reply from the Signalbot team:\n",
    },
    "privacy": {
        "ru": (
            "<b>Signalbot, закрытая бета — конфиденциальность</b>\n"
            "Signalbot наблюдает за BTC и показывает необычные состояния рынка и контекст.\n"
            "Торговых рекомендаций бот не даёт.\n\n"
            "• Что бот показывает: коридор цены, уровни и шанс дойти до них, что бывало в похожих случаях, "
            "события календаря и оповещения.\n"
            "• Мы храним ваш Telegram id и id чата, чтобы отправлять сообщения беты, "
            "а также голоса «полезно / шум» и статус доставки.\n"
            "• Ваши настройки (язык, часовой пояс, какие сообщения получать, время утренней сводки) и стиль "
            "торговли, если вы его укажете, хранятся, пока вы в бете; /delete_me удаляет их.\n"
            "• Записи рынка и событий не содержат персональных данных.\n"
            "• Мы записываем, какие команды и кнопки вы используете и когда, и по какой "
            "ссылке-приглашению вы пришли, чтобы улучшать бота. Эти записи хранятся 120 дней. "
            "/delete_me удаляет их вместе с остальными вашими данными.\n"
            "• Тексты отзывов, идей и обычные сообщения боту (/feedback, /idea) хранятся 120 дней; "
            "ответы «почему» после «Шум» и при паузе хранятся, пока вы в бете. /delete_me удаляет всё это.\n"
            "• Ваши уровни (/alert) хранятся, пока вы их не удалите; /delete_me удаляет их.\n"
            "• /stop приостанавливает все сообщения, кроме ответов команды на ваши сообщения. "
            "/delete_me удаляет ваши данные участника "
            "и исключает вас из беты.\n"
            "• После /stop данные удаляются автоматически через 30 дней.\n"
            "• Журнал прогнозов бота (что он говорил и что было потом) и записи рынка не содержат "
            "ваших данных.\n"
            "• Вопросы о ваших данных — через /feedback, отвечает команда Signalbot.\n"
            "• Это не инвестиционный совет; бот не совершает сделки и не говорит, покупать или продавать. "
            "Исторические цифры описывают прошлое.\n\n"
            "Нажмите <b>Вступить</b>, чтобы принять условия и войти в бету."
        ),
        "en": (
            "<b>Signalbot closed beta — privacy notice</b>\n"
            "Signalbot watches BTC and shows unusual market states and their context.\n"
            "The bot gives no trading advice.\n\n"
            "• What the bot shows: the price corridor, levels and the chance to reach them, what happened in "
            "similar cases, calendar events and alerts.\n"
            "• We store your Telegram user id and chat id to send you beta messages, plus your "
            "Useful/Noise votes and delivery status.\n"
            "• Your settings (language, time zone, which messages to receive, the briefing time) and your trading "
            "style, if you give it, are kept while you are in the beta; /delete_me deletes them.\n"
            "• Market/event records contain no personal data.\n"
            "• We record which commands and buttons you use, and when, and which invite link "
            "you came from, so we can improve the bot. These records are kept for 120 days. "
            "/delete_me deletes them with the rest of your data.\n"
            "• Feedback and idea texts and plain messages to the bot (/feedback, /idea) are stored for 120 days; "
            "your "
            "answers to «why» after «Noise» and at a pause are kept while you are in the beta. /delete_me deletes "
            "all of it.\n"
            "• Your price alerts (/alert) are kept until you delete them; /delete_me deletes them.\n"
            "• /stop pauses all messages except the team's replies to your messages. "
            "/delete_me deletes your participant data and removes "
            "you from the beta.\n"
            "• After /stop, your data is deleted automatically after 30 days.\n"
            "• The bot's forecast journal (what it said and what happened next) and the market records do not "
            "contain your data.\n"
            "• Questions about your data: /feedback; the Signalbot team answers.\n"
            "• Nothing here is investment advice; the bot never places trades and never says whether to "
            "buy or sell. Historical numbers describe the past.\n\n"
            "Press <b>Join</b> to accept and join the beta."
        ),
    },
    "help": {
        "ru": (
            "<b>Signalbot, закрытая бета — BTCUSDT perpetual (Binance, Bybit, OKX)</b>\n"
            "Бот наблюдает несколько замороженных, детерминированных необычных состояний рынка "
            "и сообщает, когда одно из них наблюдается. Он не говорит, что делать со сделкой.\n\n"
            "/btc — компактное состояние BTC perpetual (спокойно, необычно сейчас, затихло, "
            "бот собирает историю или данные неполные). Кнопки открывают измерения.\n"
            "/catchup — что было за последние часы (по умолчанию 8 ч; /catchup 1–24)\n"
            "/history — недавние необычные события, с сообщением или без, с фактическими диапазонами\n"
            "/brief on|off — утренняя сводка в 08:00 (Киев)\n"
            "/push on|off — сообщения о необычном часе (не больше 2 в день)\n"
            "/terms — термины\n"
            "/lang — язык сообщений\n"
            "/feedback — отзыв или вопрос\n"
            "/stop — пауза · /delete_me — удалить ваши данные"
        ),
        "en": (
            "<b>Signalbot closed beta — BTCUSDT perpetual (Binance, Bybit, OKX)</b>\n"
            "The bot watches a few frozen, deterministic, unusual market states and tells you when one "
            "is observed. It does not tell you what to trade.\n\n"
            "/btc — compact BTC perpetual state (calm, unusual now, calmed, history building, "
            "or data incomplete). Buttons hold the measurements.\n"
            "/catchup — what happened over the last hours (8h by default; /catchup 1–24)\n"
            "/history — recent unusual events, with or without a message, with factual follow-up ranges\n"
            "/brief on|off — morning briefing at 08:00 Kyiv\n"
            "/push on|off — unusual-hour messages (no more than 2 a day)\n"
            "/terms — glossary\n"
            "/lang — message language\n"
            "/feedback — a comment or a question\n"
            "/stop — pause messages · /delete_me — delete your data"
        ),
    },
    "deleted": {
        "ru": "Данные участника беты удалены, и вы исключены из беты.",
        "en": "Your beta participant data was deleted and you were removed from the beta.",
    },
    "feedback_before_join": {
        "ru": "До вступления бот хранит о вас только приглашение (и запись в листе ожидания, если она есть); "
              "/delete_me удаляет их. Написать команде можно после вступления: /start, затем /feedback ваш текст.",
        "en": "Before you join, the bot keeps only your invitation (and a waitlist entry, if any); /delete_me "
              "removes them. You can write to the team after joining: /start, then /feedback your text.",
    },
    "not_joined": {
        "ru": "Сообщения на паузе, или вы ещё не вступили. Отправьте /start.",
        "en": "Messages are paused or you have not joined yet. Send /start.",
    },
    "paused": {
        "ru": ("Сообщения на паузе, кроме ответов команды на ваши сообщения. "
               "Отправьте /start, чтобы продолжить. Данные удаляются "
               "автоматически через 30 дней или сразу командой /delete_me."),
        "en": ("Messages paused, except the team's replies to your messages. "
               "Send /start to resume. Your data is deleted "
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
    "title_history": {"ru": "бот собирает историю", "en": "history building"},
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
    "ended_run": {
        "ru": "{window}: {name} · завершилось в {hm}, {dur} назад",
        "en": "{window}: {name} · ended {hm}, {dur} ago",
    },
    "ended_run_just": {
        "ru": "{window}: {name} · завершилось в {hm}, только что",
        "en": "{window}: {name} · ended {hm}, just now",
    },
    "bucket_reading": {"ru": "5м {window}: {reading}", "en": "5m {window}: {reading}"},
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
    "part_oi": {"ru": "OI {arrow}", "en": "OI {arrow}"},
    "part_vol": {"ru": "Объём {level}", "en": "Volume {level}"},
    "part_taker": {"ru": "Delta {arrow}", "en": "Delta {arrow}"},
    "h_oi": {"ru": "OI {pct} (медиана бирж)", "en": "OI {pct} (median across exchanges)"},
    "h_move_usual": {"ru": "{move} (обычно ±{typ})", "en": "{move} (usually ±{typ})"},
    "h24_incomplete": {"ru": "24ч: неполные данные", "en": "24h: incomplete"},
    "h24_prefix": {"ru": "24ч: {body}", "en": "24h: {body}"},
    "h_vol_partial": {"ru": "объём (неполные)", "en": "vol (partial)"},
    "level_elevated": {"ru": "повышенный", "en": "elevated"},
    "level_high": {"ru": "высокий", "en": "high"},
    "level_extreme": {"ru": "экстремальный", "en": "extreme"},
    "level_normal": {"ru": "обычный", "en": "normal"},
    "oi_fell_drop": {"ru": "OI снизился во время падения", "en": "Open interest fell during the drop"},
    "oi_fell_rise": {"ru": "OI снизился во время роста", "en": "Open interest fell during the rise"},
    "oi_rose_rise": {"ru": "OI вырос во время роста", "en": "Open interest rose during the rise"},
    "oi_rose_drop": {"ru": "OI вырос во время падения", "en": "Open interest rose during the drop"},
    "oi_rose": {"ru": "OI вырос", "en": "Open interest rose"},
    "oi_fell": {"ru": "OI снизился", "en": "Open interest fell"},
    "oi_level": {"ru": "OI {level}", "en": "Open interest {level}"},
    "move_liq": {
        "ru": "{move}, снижение OI, повышенные ликвидации {side}",
        "en": "{move}, falling OI, elevated {side}-side liquidations",
    },
    "move_rise": {"ru": "Рост", "en": "Rise"},
    "move_drop": {"ru": "Падение", "en": "Drop"},
    "side_long": {"ru": "лонгов", "en": "long"},
    "side_short": {"ru": "шортов", "en": "short"},
    "liq_count": {
        "ru": "Ликвидации {side} {votes}/{eligible} бирж",
        "en": "{Side}-side liquidations {votes}/{eligible} exchanges",
    },
    "liq_not_evaluable": {
        "ru": "Ликвидации {side} нельзя оценить",
        "en": "{Side}-side liquidations not evaluable",
    },
    "gap_span": {
        "ru": "История цены/OI {span} дн. / {need} дн.",
        "en": "Price/OI history {span}d / {need}d",
    },
    "gap_maturing": {
        "ru": "История цены/OI ещё накапливается",
        "en": "Price/OI history still maturing",
    },
    "gap_unavailable": {
        "ru": "Цену и OI сейчас нельзя оценить",
        "en": "Price/OI cannot be evaluated right now",
    },
    "gap_off": {"ru": "Цена и OI отключены", "en": "Price/OI is switched off"},
    "plain_down": {"ru": "резкое падение", "en": "sharp drop"},
    "plain_up": {"ru": "резкий рост", "en": "sharp rise"},
    "plain_build": {"ru": "набор OI в узком диапазоне", "en": "OI build-up in a narrow range"},
    "plain_buy": {"ru": "агрессивные покупки", "en": "buyer-initiated flow"},
    "plain_sell": {"ru": "агрессивные продажи", "en": "seller-initiated flow"},
    "plain_liq_long": {"ru": "ликвидации лонгов", "en": "long-side liquidations"},
    "plain_liq_short": {"ru": "ликвидации шортов", "en": "short-side liquidations"},
    "evt_down": {"ru": "резкое падение цены при снижении OI", "en": "price + OI contraction down"},
    "evt_up": {"ru": "резкий рост цены при снижении OI", "en": "price + OI contraction up"},
    "evt_build": {
        "ru": "набор OI при сжатом диапазоне",
        "en": "position build-up with range compression",
    },
    # 1h / 4h interpretation (PRODUCT_FIRST_DECISION_V1 §3.1). Inferred labels read
    # "похоже на"; FACTUAL ones carry no causal label. Never a future direction.
    "interp_short_exit": {"ru": "похоже на выход шортов", "en": "looks like shorts exiting"},
    "interp_long_build": {"ru": "похоже на рост с новыми лонгами", "en": "looks like a rise with new longs"},
    "interp_short_build": {"ru": "похоже на снижение с новыми шортами",
                           "en": "looks like a decline with new shorts"},
    "interp_long_exit": {"ru": "похоже на выход лонгов", "en": "looks like longs exiting"},
    "interp_short_flush": {"ru": "похоже на вынос шортов", "en": "looks like a short liquidation flush"},
    "interp_long_flush": {"ru": "похоже на вынос лонгов", "en": "looks like a long liquidation flush"},
    "interp_compression": {"ru": "сжатие", "en": "compression"},
    "interp_compression_oi_na": {"ru": "сжатие, OI н/д", "en": "compression, OI n/a"},
    "interp_normal": {"ru": "обычное состояние", "en": "ordinary state"},
    "fact_up_oi_down": {"ru": "рост при снижении OI", "en": "rise while OI fell"},
    "fact_up_oi_up": {"ru": "рост с ростом OI", "en": "rise with OI rising"},
    "fact_down_oi_up": {"ru": "снижение с ростом OI", "en": "decline with OI rising"},
    "fact_down_oi_down": {"ru": "снижение при снижении OI", "en": "decline while OI fell"},
    "fact_up_oi_na": {"ru": "рост, OI н/д", "en": "rise, OI n/a"},
    "fact_down_oi_na": {"ru": "снижение, OI н/д", "en": "decline, OI n/a"},
    "fact_up_oi_stable": {"ru": "рост при стабильном OI", "en": "rise with stable OI"},
    "fact_down_oi_stable": {"ru": "снижение при стабильном OI", "en": "decline with stable OI"},
    "interp_venues_diverge": {"ru": "биржи расходятся", "en": "exchanges disagree"},
    "interp_insufficient": {"ru": "мало истории", "en": "not enough history"},
    "interp_missing": {"ru": "н/д", "en": "n/a"},
    # /catchup, the morning briefing and the unusual-hour push (BETA_COPY_CONTRACT_V1).
    "catchup_title": {"ru": "BTC за {hours} ч · {span}", "en": "BTC, last {hours}h · {span}"},
    "catchup_title_nospan": {"ru": "BTC за {hours} ч", "en": "BTC, last {hours}h"},
    "brief_title": {"ru": "Сводка BTC · {span}", "en": "BTC briefing · {span}"},   # any briefing time, not only morning
    "span_hours": {"ru": "{hours} ч", "en": "{hours}h"},
    "window_kyiv": {"ru": "{start}–{end} {zone}", "en": "{start}–{end} {zone}"},
    "price_span": {"ru": "Цена {open} → {close} ({pct})", "en": "Price {open} → {close} ({pct})"},
    "price_span_minmax": {"ru": ", мин {low}, макс {high}", "en": ", low {low}, high {high}"},
    "price_span_incomplete": {"ru": "Цена: данные неполные", "en": "Price: incomplete data"},
    "no_unusual_hours": {"ru": "Необычных часов не было.", "en": "No unusual hours."},
    "unusual_immature": {
        "ru": "Необычные часы пока не отмечаем: мало истории ({days} дн. из 30).",
        "en": "Unusual hours are not marked yet: not enough history ({days} of 30 days).",
    },
    "unusual_head": {"ru": "Необычный час: {span} — {label}", "en": "Unusual hour: {span} — {label}"},
    "hour_facts": {"ru": "Цена {pct}, OI {oi}, Delta {delta}", "en": "Price {pct}, OI {oi}, Delta {delta}"},
    "liq_votes_line": {
        "ru": "Ликвидации {side} — топ-5% на {k} из {n} бирж",
        "en": "{side} liquidations — top 5% on {k} of {n} exchanges",
    },
    "unsigned_range": {"ru": "Диапазон — в топ-5% часовых окон за 30 дней",
                       "en": "Range — in the top 5% of hourly windows over 30 days"},
    "unsigned_volume": {"ru": "Объём — в топ-5% часовых окон за 30 дней",
                        "en": "Volume — in the top 5% of hourly windows over 30 days"},
    "unsigned_both": {"ru": "Диапазон и объём — оба в топ-5% часовых окон за 30 дней",
                      "en": "Range and volume — both in the top 5% of hourly windows over 30 days"},
    "venues_line": {"ru": "Биржи: {k} из {n} в одну сторону", "en": "Exchanges: {k} of {n} the same way"},
    "note_quiet": {"ru": "Ночью с {s} до {e} бот не пишет, поэтому это только в сводке.",
                   "en": "The bot does not write between {s} and {e}, so this is only in the briefing."},
    "note_cap": {"ru": "Сообщения об этом часе не было: за сутки уже было {n}.",
                 "en": "No message about this hour: there were already {n} today."},
    "note_fuse": {"ru": "Сообщения об этом часе не было: бот за сутки уже отправил предельное число сообщений.",
                  "en": "No message about this hour: the bot had already sent its daily maximum of messages."},
    "note_cooldown": {"ru": "Отдельного сообщения не было: незадолго до этого бот уже писал.",
                      "en": "No separate message: the bot had written shortly before."},
    "now_head": {"ru": "Сейчас", "en": "Now"},
    "now_line": {"ru": "{h}: {body}", "en": "{h}: {body}"},
    "now_both": {"ru": "<b>{head}</b> · 1ч и 4ч: {body}", "en": "<b>{head}</b> · 1h and 4h: {body}"},
    "hz_1h": {"ru": "1ч", "en": "1h"},
    "hz_4h": {"ru": "4ч", "en": "4h"},
    "hz_24h": {"ru": "24ч", "en": "24h"},
    "hz_windows_1h": {"ru": "часовых", "en": "hourly"},
    "hz_windows_4h": {"ru": "4-часовых", "en": "4-hour"},
    "beside_facts": {"ru": "{label} — цена {pct}, OI {oi}, Delta {delta}",
                     "en": "{label} — price {pct}, OI {oi}, Delta {delta}"},
    "beside_compression": {"ru": "{label} — диапазон {rng}, в нижних 20% {hz} окон за 30 дней",
                           "en": "{label} — range {rng}, in the bottom 20% of {hz} windows over 30 days"},
    "beside_oi": {"ru": " · OI {oi}", "en": " · OI {oi}"},
    "beside_venues": {"ru": "{label} — {venues}", "en": "{label} — {venues}"},
    "beside_insufficient": {"ru": "{label} — цена {pct}, OI {oi}", "en": "{label} — price {pct}, OI {oi}"},
    "beside_oi_na": {"ru": "{dir}, Delta {delta} · OI н/д: сейчас есть с {k} из {n} бирж",
                     "en": "{dir}, Delta {delta} · OI n/a: available from {k} of {n} exchanges"},
    "beside_delta_na": {"ru": "{label} — Delta н/д — без неё не интерпретируем",
                        "en": "{label} — Delta n/a — no interpretation without it"},
    "beside_delta_na_bare": {"ru": "Delta н/д — без неё не интерпретируем",
                             "en": "Delta n/a — no interpretation without it"},
    "beside_delta_against": {"ru": "{label} — Delta {delta} — против направления цены, без интерпретации",
                             "en": "{label} — Delta {delta} — against the price direction, no interpretation"},
    "delta_against_suffix": {"ru": " — против направления цены, без интерпретации",
                             "en": " — against the price direction, no interpretation"},
    "dir_up": {"ru": "рост", "en": "rise"},
    "dir_down": {"ru": "снижение", "en": "decline"},
    "data_incomplete": {"ru": "данные неполные", "en": "incomplete data"},
    "range_24h": {"ru": "{low}–{high}", "en": "{low}–{high}"},
    "range_24h_na": {"ru": "диапазон н/д", "en": "range n/a"},
    "pos_low": {"ru": "цена у нижней границы", "en": "price at the low end"},
    "pos_lowish": {"ru": "цена ближе к нижней границе", "en": "price closer to the low end"},
    "pos_mid": {"ru": "цена в середине", "en": "price in the middle"},
    "pos_highish": {"ru": "цена ближе к верхней границе", "en": "price closer to the high end"},
    "pos_high": {"ru": "цена у верхней границы", "en": "price at the high end"},
    "oi_24h": {"ru": "OI {oi} за 24ч (медиана бирж{usual})", "en": "OI {oi} over 24h (median across exchanges{usual})"},
    "oi_24h_na": {"ru": "OI за 24ч н/д", "en": "OI over 24h n/a"},
    "funding_avg": {"ru": "средний Funding {f}", "en": "average Funding {f}"},
    "funding_avg_na": {"ru": "средний Funding н/д", "en": "average Funding n/a"},
    # derivatives beside their «обычно» (backlog G2; beta/derivatives.py)
    "oi_usual_part": {"ru": "; Binance {bn}, обычно ±{typ}, N={n} дн.", "en": "; Binance {bn}, usually ±{typ}, N={n} days"},
    "funding_usual_part": {"ru": "обычно {typ}, N={n}", "en": "usually {typ}, N={n}"},
    "der_oi_usual": {"ru": "   Binance {bn} · обычно OI Binance за сутки меняется на ±{typ} (медиана, N={n} дн.)",
                     "en": "   Binance {bn} · Binance OI usually moves ±{typ} a day (median, N={n} days)"},
    "der_funding_usual": {"ru": "   обычно среднее за 24 ч {typ} (медиана за {n} дн.)",
                          "en": "   usually a 24h average of {typ} (median of {n} days)"},
    "der_usual_short": {"ru": "   обычно: мало данных (N={n} дн.)", "en": "   usually: too little data (N={n} days)"},
    "der_ls": {"ru": "Соотношение счетов лонг/шорт (Binance): {ratio} · обычно {typ} (медиана за {n} дн.)",
               "en": "Long/short account ratio (Binance): {ratio} · usually {typ} (median of {n} days)"},
    "der_ls_short": {"ru": "Соотношение счетов лонг/шорт (Binance): {ratio} · обычно: мало данных (N={n} дн.)",
                     "en": "Long/short account ratio (Binance): {ratio} · usually: too little data (N={n} days)"},
    "payer_longs": {"ru": "платят лонги", "en": "longs pay"},
    "payer_shorts": {"ru": "платят шорты", "en": "shorts pay"},
    "data_at": {"ru": "Данные на {clock}", "en": "Data as of {clock}"},
    "brief_off_hint": {"ru": "Отключить утреннюю сводку: /brief off", "en": "Turn the morning briefing off: /brief off"},
    "catchup_usage": {"ru": "Окно — от 1 до 24 часов. Например: /catchup 4",
                      "en": "The window is 1 to 24 hours. For example: /catchup 4"},
    "brief_usage": {"ru": "Утренняя сводка: {state}, в {time} {zone}. /brief on — включить, /brief off — выключить, "
                          "/brief 07:30 — другое время.",
                    "en": "Morning briefing: {state}, at {time} {zone}. /brief on to turn it on, /brief off to turn it "
                          "off, /brief 07:30 for another time."},
    "brief_time_ok": {"ru": "Утренняя сводка — в {time} {zone}.", "en": "Morning briefing at {time} {zone}."},
    "brief_time_off_hint": {"ru": "Сейчас она выключена: /brief on — включить.",
                            "en": "It is off now: /brief on to turn it on."},
    "brief_state_on": {"ru": "включена", "en": "on"},
    "brief_state_off": {"ru": "выключена", "en": "off"},
    "brief_on_ok": {"ru": "Утренняя сводка включена: {time} {zone}.", "en": "Morning briefing on: {time} {zone}."},
    # one onboarding question (backlog E5): stored only; the owner report is split by it, the bot does not change
    "type_question": {"ru": "Как вы торгуете? Один ответ, чтобы понять, кому бот полезен; сообщения от него не меняются.",
                      "en": "How do you trade? One answer, so we learn who the bot helps; the messages do not change."},
    "type_scalp": {"ru": "Скальпинг", "en": "Scalping"},
    "type_intraday": {"ru": "Внутри дня", "en": "Intraday"},
    "type_swing": {"ru": "Свинг (дни–недели)", "en": "Swing (days–weeks)"},
    "type_invest": {"ru": "Инвестиции", "en": "Investing"},
    "type_skip": {"ru": "Пропустить", "en": "Skip"},
    "type_saved": {"ru": "Записал: {name}. Изменить: /type", "en": "Saved: {name}. Change it: /type"},
    "type_skipped": {"ru": "Хорошо. Указать позже: /type", "en": "Fine. You can answer later: /type"},
    "tz_usage": {"ru": "Часовой пояс: {name}. Всё время в сообщениях — по нему, ночная тишина {quiet} — тоже.\n"
                       "Поменять: /tz Europe/Warsaw, /tz America/New_York (город — с переходом на летнее время) "
                       "или смещение со знаком: /tz +3; вернуть Киев: /tz kyiv",
                 "en": "Time zone: {name}. Every time in the messages follows it, and so do the quiet hours {quiet}.\n"
                       "Change it: /tz Europe/Warsaw, /tz America/New_York (a city follows summer time) or a signed "
                       "offset: /tz +3; back to Kyiv: /tz kyiv"},
    "tz_ok": {"ru": "Часовой пояс: {name}. Сейчас у вас {clock}.", "en": "Time zone: {name}. Your time now: {clock}."},
    "tz_fixed_note": {"ru": "Это постоянное смещение: летнее и зимнее время оно не учитывает. Город (например, "
                            "/tz Europe/Warsaw) переводит часы сам.",
                      "en": "This is a fixed offset: it does not follow summer and winter time. A city (for example, "
                            "/tz Europe/Warsaw) changes the clocks by itself."},
    "tz_bad": {"ru": "Не понял часовой пояс. Город: /tz Europe/Warsaw; смещение — со знаком: /tz +3, /tz -5, /tz +10; "
                     "Киев: /tz kyiv",
               "en": "I could not read that time zone. A city: /tz Europe/Warsaw; an offset needs a sign: /tz +3, "
                     "/tz -5, /tz +10; Kyiv: /tz kyiv"},
    "brief_off_ok": {"ru": "Утренняя сводка выключена. Сообщения о необычном часе это не меняет.",
                     "en": "Morning briefing off. Unusual-hour messages are not affected."},
    "push_usage": {"ru": "Сообщения о необычном часе: {state}. /push on — включить, /push off — выключить.",
                   "en": "Unusual-hour messages: {state}. /push on to turn them on, /push off to turn them off."},
    "push_state_on": {"ru": "включены", "en": "on"},
    "push_state_off": {"ru": "выключены", "en": "off"},
    "push_on_ok": {"ru": "Сообщения о необычном часе включены: не больше 2 в день, ночью бот не пишет.",
                   "en": "Unusual-hour messages on: no more than 2 a day, none at night."},
    "push_off_ok": {"ru": "Сообщения о необычном часе выключены. Утреннюю сводку это не меняет.",
                    "en": "Unusual-hour messages off. The morning briefing is not affected."},
    # push (BETA_COPY_CONTRACT_V1 §1.2)
    "push_hour_title": {"ru": "BTC · необычный час", "en": "BTC · unusual hour"},
    "price_line": {"ru": "Цена {pct} ({open} → {close})", "en": "Price {pct} ({open} → {close})"},
    "price_line_noprices": {"ru": "Цена {pct}", "en": "Price {pct}"},
    "price_line_na": {"ru": "Цена: н/д", "en": "Price: n/a"},
    "price_tail": {"ru": ": {dir}", "en": ": {dir}"},
    "price_rise_95": {"ru": "рост сильнее, чем в 95% часовых окон за 30 дней",
                      "en": "a rise stronger than in 95% of hourly windows over 30 days"},
    "price_drop_95": {"ru": "падение глубже, чем в 95% часовых окон за 30 дней",
                      "en": "a drop deeper than in 95% of hourly windows over 30 days"},
    "oi_delta_line": {"ru": "OI {oi} · Delta {delta}", "en": "OI {oi} · Delta {delta}"},
    "oi_only_line": {"ru": "OI {oi}", "en": "OI {oi}"},
    "evt_buy": {"ru": "агрессивные покупки", "en": "aggressive buying"},
    "evt_sell": {"ru": "агрессивные продажи", "en": "aggressive selling"},
    "evt_liq_long": {"ru": "ликвидационный стресс (ликвидации лонгов)", "en": "liquidation stress (long-side liquidations)"},
    "evt_liq_short": {"ru": "ликвидационный стресс (ликвидации шортов)", "en": "liquidation stress (short-side liquidations)"},
    "desc_down": {
        "ru": ("Движение цены за 5м в нижних 5% последних 30 дней при снижении открытого "
               "интереса в его нижних 10%, не менее чем на 2 биржах."),
        "en": ("5m price move in the bottom 5% of the last 30 days while open "
               "interest fell in its bottom 10%, on at least 2 exchanges."),
    },
    "desc_up": {
        "ru": ("Движение цены за 5м в верхних 5% последних 30 дней при снижении открытого "
               "интереса в его нижних 10%, не менее чем на 2 биржах."),
        "en": ("5m price move in the top 5% of the last 30 days while open "
               "interest fell in its bottom 10%, on at least 2 exchanges."),
    },
    "desc_build": {
        "ru": ("Открытый интерес растёт (верхние 20% за 30 дней) при узком 5м диапазоне "
               "(нижние 40%) и объёме не ниже медианы, 45 минут подряд."),
        "en": ("Open interest growing (top 20% of 30d) with a narrow 5m range "
               "(bottom 40%) and at least median volume, for 45 consecutive minutes."),
    },
    "desc_buy": {
        "ru": "Delta в верхних 5% последних 30 дней два 5м бакета подряд.",
        "en": "Delta in the top 5% of the last 30 days for two consecutive 5m buckets.",
    },
    "desc_sell": {
        "ru": "Delta в нижних 5% последних 30 дней два 5м бакета подряд.",
        "en": "Delta in the bottom 5% of the last 30 days for two consecutive 5m buckets.",
    },
    "desc_liq_long": {
        "ru": ("Номинал ликвидаций лонгов в верхних 5% собственной 30-дневной истории "
               "не менее чем на 2 биржах с живой лентой в том же 5м бакете."),
        "en": ("Long-side liquidation notional in the top 5% of its own 30d history "
               "on at least 2 exchanges with a live feed in the same 5m bucket."),
    },
    "desc_liq_short": {
        "ru": ("Номинал ликвидаций шортов в верхних 5% собственной 30-дневной истории "
               "не менее чем на 2 биржах с живой лентой в том же 5м бакете."),
        "en": ("Short-side liquidation notional in the top 5% of its own 30d history "
               "on at least 2 exchanges with a live feed in the same 5m bucket."),
    },
    "state_early": {"ru": "ранняя", "en": "early"},
    "state_armed": {"ru": "отмечена", "en": "armed"},
    "state_triggered": {"ru": "зафиксирована", "en": "triggered"},
    "state_ended": {"ru": "завершена", "en": "ended"},
    "state_expired": {"ru": "истекла", "en": "expired"},
    # Legacy V0.2 event-push keys. Not delivered to users since the unusual-hour push
    # (BETA_COPY_CONTRACT_V1); kept for `format_push_v02`, an offline replay helper.
    "push_title": {"ru": "BTCUSDT perp — СОБЫТИЕ: {name}", "en": "BTCUSDT perp — EVENT: {name}"},
    "push_decision": {
        "ru": "Время решения: {when} (закрытие 5м бакета)",
        "en": "Decision time: {when} (5m bucket close)",
    },
    "push_close": {
        "ru": "Сводная цена на решении: {price} ({venues})",
        "en": "Composite close at decision: {price} ({venues})",
    },
    "status_title": {"ru": "BTCUSDT perp — {status}", "en": "BTCUSDT perp — {status}"},
    "status_eval": {
        "ru": "Последняя оценка: 5м бакет закрыт {when}",
        "en": "Last evaluation: 5m bucket closed {when}",
    },
    "status_eval_none": {"ru": "Последняя оценка: ещё нет", "en": "Last evaluation: none yet"},
    "status_episode": {"ru": "• {name} — {state} (с {when})", "en": "• {name} — {state} (since {when})"},
    "status_context": {"ru": "Контекст (5м, по биржам)", "en": "Context (5m, across exchanges)"},
    "status_price": {"ru": "движение цены: {v}", "en": "price move: {v}"},
    "status_oi": {"ru": "изменение OI: {v}", "en": "OI change: {v}"},
    "status_range": {"ru": "ширина диапазона: {v}", "en": "range width: {v}"},
    "status_volume": {"ru": "объём: {v}", "en": "volume: {v}"},
    "status_ref": {"ru": "сводная цена: {price} ({venues})", "en": "composite close: {price} ({venues})"},
    "status_gated": {"ru": "сейчас не оценивается: {names}", "en": "not evaluable now: {names}"},
    "rank_na": {"ru": "н/д", "en": "n/a"},
    "rank_immature": {"ru": "нельзя оценить (история: {tier})", "en": "not evaluable ({tier} history)"},
    "rank_pct": {"ru": "{n}-й перцентиль за 30 дн.", "en": "{n}th pct of 30d"},
    "history_title": {
        "ru": "Необычные события BTC (с сообщением или без)",
        "en": "BTC unusual events (with or without a message)",
    },
    "history_empty": {"ru": "Событий ещё нет.", "en": "No events yet."},
    "history_note": {
        "ru": ("Диапазоны — абсолютное движение (макс − мин) после времени решения; "
               "* = пересмотрено после исправления данных."),
        "en": ("Ranges are absolute (max − min) moves after the decision time; "
               "* = revised after a data correction."),
    },
    "history_corrected": {"ru": " ⚠ вход исправлен", "en": " ⚠ corrected input"},
    "history_times": {
        "ru": "начало {opened}; зафиксировано {triggered}; {push}",
        "en": "started {opened}; triggered {triggered}; {push}",
    },
    # /history delivery wording: never a raw delivery state or suppression code
    # (BETA_COPY_CONTRACT_V1 §5 rule 5).
    "push_none": {"ru": "без сообщения", "en": "no message"},
    "push_pending": {"ru": "сообщение в очереди", "en": "message queued"},
    "push_sent": {"ru": "сообщение отправлено", "en": "message sent"},
    "push_unconfirmed": {"ru": "доставка не подтверждена", "en": "delivery not confirmed"},
    "push_expired": {"ru": "сообщение не отправлено: устарело", "en": "message not sent: too old"},
    "end_not_evaluable": {"ru": "нет данных", "en": "no data"},
    "end_max_duration": {"ru": "лимит длительности", "en": "duration limit"},
    "end_version_changed": {"ru": "смена версии", "en": "version change"},
    "end_detection_gap": {"ru": "пропуск данных", "en": "data gap"},
    "range_na": {"ru": "{h} н/д", "en": "{h} n/a"},
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
    "event_head": {"ru": "<b>Событие BTC</b> · {name}", "en": "<b>BTC event</b> · {name}"},
    "event_since": {"ru": "Ещё активно · с {clock}", "en": "Still active · since {clock}"},
    "event_ended_at": {"ru": "Завершено · {clock}", "en": "Ended · {clock}"},
    "why_window": {"ru": "Почему замечено ({window}):", "en": "Why it was noticed ({window}):"},
    "bucket_head": {"ru": "Показатели за 5м {window}:", "en": "Readings for the 5m bucket {window}:"},
    "anchor_metrics": {
        "ru": "Цена {price} · диапазон {range} · объём {vol}{level}",
        "en": "Price {price} · range {range} · volume {vol}{level}",
    },
    "anchor_oi": {"ru": "OI {med} (медиана бирж): {venues}", "en": "OI {med} (median across exchanges): {venues}"},
    "anchor_oi_na": {"ru": "OI: {venues}", "en": "OI: {venues}"},
    "taker_line": {"ru": "Delta: {signed} ({side})", "en": "Delta: {signed} ({side})"},
    "taker_flat": {"ru": "Delta: $0", "en": "Delta: $0"},
    "taker_na": {"ru": "Delta: {na}", "en": "Delta: {na}"},
    "taker_buyers": {"ru": "покупатели", "en": "buyers"},
    "taker_sellers": {"ru": "продавцы", "en": "sellers"},
    "liq_line": {"ru": "Ликвидации {side}: {body}", "en": "{Side} liquidations: {body}"},
    "liq_long_name": {"ru": "лонгов", "en": "Long"},
    "liq_short_name": {"ru": "шортов", "en": "Short"},
    "liq_footnote": {
        "ru": "≥ — нижняя граница: Binance и OKX передают не все ликвидации.",
        "en": "≥ — lower bound: Binance and OKX do not report every liquidation.",
    },
    "liq_zero_footnote": {
        "ru": "* — $0 по неполным данным: это не значит, что ликвидаций не было.",
        "en": "* — $0 from incomplete data: it does not mean there were no liquidations.",
    },
    "h1_head": {"ru": "<b>BTC за последний час</b> · {window} {zone}", "en": "<b>BTC, last hour</b> · {window} {zone}"},
    "h1_price_range": {
        "ru": "Цена {price} · диапазон {range}{ratio}",
        "en": "Price {price} · range {range}{ratio}",
    },
    "h1_volume": {"ru": "Объём {vol}{ratio}", "en": "Volume {vol}{ratio}"},
    "h1_ratio": {"ru": " ({ratio} от обычного для этого часа)", "en": " ({ratio} usual for this hour)"},
    "h1_ratio_wait": {
        "ru": " (сравнение с обычным — через ~{n} дн.)",
        "en": " (comparison with usual in ~{n} days)",
    },
    "h1_ratio_wait_one": {
        "ru": " (сравнение с обычным — через ~1 дн.)",
        "en": " (comparison with usual in ~1 day)",
    },
    "ratio_unavailable": {
        "ru": " (сравнение недоступно)",
        "en": " (comparison unavailable)",
    },
    "h1_incomplete_body": {"ru": "1ч: неполные данные", "en": "1h: incomplete"},
    "funding_now": {
        "ru": "Funding сейчас {rate} (медиана бирж)",
        "en": "Funding now {rate} (median across exchanges)",
    },
    "funding_24h": {
        "ru": "Funding сейчас {now} · среднее за 24 ч {avg}",
        "en": "Funding now {now} · 24h average {avg}",
    },
    "h24_head": {"ru": "<b>BTC за 24 ч</b> · до {hm} {zone}", "en": "<b>BTC, last 24h</b> · through {hm} {zone}"},
    "h24_price": {"ru": "Цена {price} · макс {high} · мин {low}", "en": "Price {price} · high {high} · low {low}"},
    "h24_range": {"ru": "Диапазон {range}{ratio}", "en": "Range {range}{ratio}"},
    "h24_ratio": {"ru": " ({ratio} от медианы 30 дн.)", "en": " ({ratio} 30d median)"},
    "h24_ratio_wait": {
        "ru": " (сравнение с медианой 30 дн. — через ~{n} дн.)",
        "en": " (30d comparison in ~{n} days)",
    },
    "h24_ratio_wait_one": {
        "ru": " (сравнение с медианой 30 дн. — через ~1 дн.)",
        "en": " (30d comparison in ~1 day)",
    },
    "h24_volume": {"ru": "Объём {vol}{ratio}", "en": "Volume {vol}{ratio}"},
    "h24_volume_partial": {"ru": "Объём {vol} (неполные)", "en": "Volume {vol} (partial)"},
    "changes_head": {"ru": "Изменения к предыдущим 24 ч:", "en": "Changes vs previous 24h:"},
    "changes_none": {
        "ru": "Крупных изменений к предыдущим 24 ч нет",
        "en": "No large change vs previous 24h",
    },
    "changes_range_wider": {"ru": "диапазон шире: {a} против {b}", "en": "range wider: {a} vs {b}"},
    "changes_range_narrower": {"ru": "диапазон уже: {a} против {b}", "en": "range narrower: {a} vs {b}"},
    "changes_vol_higher": {"ru": "объём выше: {a} против {b}", "en": "volume higher: {a} vs {b}"},
    "changes_vol_lower": {"ru": "объём ниже: {a} против {b}", "en": "volume lower: {a} vs {b}"},
    "changes_oi_up_down": {"ru": "OI вырос, пока цена падала", "en": "OI rose while price fell"},
    "changes_oi_down_down": {"ru": "OI снизился, пока цена падала", "en": "OI fell while price fell"},
    "changes_oi_up_up": {"ru": "OI вырос, пока цена росла", "en": "OI rose while price rose"},
    "changes_oi_down_up": {"ru": "OI снизился, пока цена росла", "en": "OI fell while price rose"},
    "changes_funding_pos": {"ru": "Funding стал положительным", "en": "Funding turned positive"},
    "changes_funding_neg": {"ru": "Funding стал отрицательным", "en": "Funding turned negative"},
    "terms_footer": {"ru": "Термины: /terms", "en": "Terms: /terms"},
    "funding_na": {"ru": "Funding сейчас {na}", "en": "Funding now {na}"},
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
    "ready_building": {"ru": "бот собирает историю", "en": "history building"},
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
    "hist_oi": {"ru": "история OI", "en": "OI history"},
    "hist_range": {"ru": "история диапазона", "en": "range history"},
    "hist_volume": {"ru": "история объёма", "en": "volume history"},
    "hist_taker": {"ru": "история Delta", "en": "Delta history"},
    "hist_liq_long": {"ru": "история ликвидаций лонгов", "en": "long-side liquidation history"},
    "hist_liq_short": {"ru": "история ликвидаций шортов", "en": "short-side liquidation history"},
    "fam_price": {"ru": "цены", "en": "price"},
    "fam_oi": {"ru": "OI", "en": "OI"},
    "fam_volume": {"ru": "объёма", "en": "volume"},
    "fam_taker": {"ru": "Delta", "en": "Delta"},
    "reason_venues": {
        "ru": "меньше {n} пригодных бирж для {fam}",
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
    "d7_main": {
        "ru": "High impact в прошлый час",
        "en": "High impact last hour",
    },
    "d7_h1_1": {
        "ru": "High impact {start}–{end} {zone}: цена прошла много относительно объёма торгов.",
        "en": "High impact {start}–{end} {zone}: price moved a lot relative to traded volume.",
    },
    "d7_h1_2": {
        "ru": "Исторически следующий час был таким же примерно в 1 из 5 случаев (обычно в 1 из 10).",
        "en": "Historically, the following hour was also like this about 1 in 5 times (usually 1 in 10).",
    },
    "d7_h1_3": {
        "ru": "Направление цены это не показывает.",
        "en": "This says nothing about price direction.",
    },
    "d7_warmup": {
        "ru": "Контекст импакта: бот собирает историю",
        "en": "Impact context: history building",
    },
    "terms": {
        "ru": (
            "ТЕРМИНЫ\n"
            "\n"
            "Состояния\n"
            "Спокойно — необычных состояний сейчас нет.\n"
            "Необычно сейчас — открыто одно из событий ниже.\n"
            "Затихло — событие было в последние 2 ч и закончилось.\n"
            "Событие завершено — событие прервалось по технической причине (нет данных, лимит длительности, смена версии).\n"
            "Бот собирает историю — меньше 30 дней данных, сравнивать пока не с чем.\n"
            "Данные неполные — свежих данных не хватает, отсутствие событий подтвердить нельзя.\n"
            "\n"
            "События\n"
            "Резкий рост / падение — за 5 мин цена прошла больше, чем в 95% пятиминуток за 30 дней, и одновременно OI заметно снизился, минимум на 2 биржах.\n"
            "Набор OI в узком диапазоне — 45 мин подряд OI растёт сильнее обычного, а цена стоит в узком диапазоне.\n"
            "Агрессивные покупки / продажи — две пятиминутки подряд Delta в верхних / нижних 5% за 30 дней.\n"
            "Ликвидации лонгов / шортов — ликвидации одной стороны в верхних 5% за 30 дней, минимум на 2 биржах одновременно.\n"
            "\n"
            "Показатели\n"
            "OI (open interest) — общее число открытых фьючерсных контрактов. Растёт, когда открывается больше, чем закрывается. "
            "Изменение OI в боте — медиана изменений по биржам (минимум 2 биржи), а не изменение суммарного OI.\n"
            "Funding — регулярный платёж между лонгами и шортами на бессрочных фьючерсах. Плюс — лонги платят шортам, минус — наоборот.\n"
            "Delta — разница между рыночными покупками и продажами в $. Минус — нетто продавали.\n"
            "Объём — сумма сделок в $ по Binance, Bybit и OKX.\n"
            "Диапазон — от минимума до максимума цены за период, в % от цены.\n"
            "Ликвидации — принудительное закрытие позиций биржей, по каждой бирже отдельно.\n"
            "≥ — нижняя граница: Binance публикует не все ликвидации.\n"
            "$0* — ноль по неполным данным: это не значит, что ликвидаций не было.\n"
            "н/д — данных нет или они неполные. Это не ноль.\n"
            "× от обычного — во сколько раз больше обычного: для 1ч — в это же время суток за 30 дней, для 24ч — медиана за 30 дней. "
            "Сравнение появляется, когда накоплено 20 дней истории.\n"
            "↑ ↓ — только направление, не сила.\n"
            "Время — по вашему часовому поясу (по умолчанию Киев; /tz).\n"
            "High impact — за прошлый календарный час цена прошла много относительно объёма торгов. "
            "Исторически следующий час был таким же примерно в 1 из 5 случаев (обычно 1 из 10). "
            "Направление цены это не показывает."
        ),
        "en": (
            "TERMS\n"
            "\n"
            "States\n"
            "Calm — no unusual state right now.\n"
            "Unusual now — one of the events below is open.\n"
            "Calmed — an event happened in the last 2h and has ended.\n"
            "Event ended — the event stopped for a technical reason (no data, duration limit, version change).\n"
            "History building — less than 30 days of data, nothing to compare with yet.\n"
            "Data incomplete — fresh data is insufficient; the absence of events cannot be confirmed.\n"
            "\n"
            "Events\n"
            "Sharp rise / drop — over 5 min the price moved more than in 95% of 5-minute periods of the last 30 days, while OI fell noticeably, on at least 2 exchanges.\n"
            "OI build-up in a narrow range — for 45 min in a row OI grows faster than usual while the price stays in a narrow range.\n"
            "Aggressive buying / selling — Delta in the top / bottom 5% of the last 30 days for two 5-minute periods in a row.\n"
            "Long / short liquidations — one side's liquidations in the top 5% of the last 30 days, on at least 2 exchanges at once.\n"
            "\n"
            "Metrics\n"
            "OI (open interest) — total number of open futures contracts. It rises when more contracts are opened than closed. "
            "The bot's OI change is the median of the exchanges' changes (at least 2 exchanges), not the change of total OI.\n"
            "Funding — a periodic payment between longs and shorts on perpetual futures. Positive — longs pay shorts; negative — the reverse.\n"
            "Delta — difference between market buys and market sells in $. Negative — net selling.\n"
            "Volume — total traded value in $ on Binance, Bybit and OKX.\n"
            "Range — from the lowest to the highest price in the period, in % of the price.\n"
            "Liquidations — positions force-closed by the exchange, shown per exchange.\n"
            "≥ — lower bound: Binance does not publish every liquidation.\n"
            "$0* — zero from incomplete data: it does not mean there were no liquidations.\n"
            "n/a — no data or incomplete data. This is not zero.\n"
            "× usual — how many times larger than usual: for 1h, the same time of day over 30 days; for 24h, the 30-day median. "
            "The comparison appears once 20 days of history are collected.\n"
            "↑ ↓ — direction only, not strength.\n"
            "Time — your time zone (Kyiv by default; /tz).\n"
            "High impact — in the last clock hour the price moved a lot relative to traded volume. "
            "Historically the following hour was like this about 1 in 5 times (usually 1 in 10). "
            "It says nothing about price direction."
        ),
    },
}


def _merge_decision_catalog() -> None:
    from .i18n_decision import DECISION_CATALOG, DECISION_HELP, DECISION_TERMS
    for key, val in DECISION_CATALOG.items():
        if key in _CATALOG:
            raise KeyError(f"duplicate catalog key {key!r}")
        _CATALOG[key] = val
    _CATALOG["help"] = dict(DECISION_HELP)
    _CATALOG["terms"] = {lang: _CATALOG["terms"][lang] + DECISION_TERMS[lang] for lang in LANGS}


_merge_decision_catalog()
