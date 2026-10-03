"""Beta V0.2 multi-user Telegram bot (long polling) — isolated from the legacy
forecast notifier (runtime/telegram_cli.py / notifications/telegram_*): it reuses
only `notifications.telegram_client.TelegramSender` (subclassed, unmodified) and
none of the legacy candidate/formatter/outbox.

Each update is handled in ONE transaction that also persists the last processed
update id, so a restart never reprocesses an old command/callback. Replies are
sent after commit. A rejected /start stores an HMAC or a daily count, never the
raw id. No raw Telegram id is ever logged.
"""
from __future__ import annotations

import asyncio
import html
import logging
import math
import signal
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Optional, Sequence

from beta.access import PRIVACY_NOTICE_VERSION, start_code, telemetry_salt
from beta.admin import collect_status, fingerprint, handle_admin, is_owner, parse_command
from beta.config import BetaConfig, BetaSwitches, effective_d7_enabled
from beta.delivery import DeliveryAmbiguous, DeliveryRejected
from beta.formatter import assert_descriptive, format_history
from beta.i18n import t
from beta.market_view import build_view, parse_catchup_hours, persist_view
from common.logging_setup import setup_logging
from notifications.telegram_client import TelegramSender, sanitize_telegram_error

logger = logging.getLogger("beta.bot")
BOT_NAME = "beta_v0"
HISTORY_LIMIT = 10
_FROM_ENV = object()


@dataclass(frozen=True)
class Outgoing:
    kind: str                                   # 'message' | 'answer'
    chat_id: Optional[int] = None
    html: str = ""
    buttons: Optional[Sequence[Sequence[tuple]]] = None
    callback_id: Optional[str] = None
    message_id: Optional[int] = None


class BetaTelegramSender(TelegramSender):
    """TelegramSender + inline buttons / callback answers / long polling."""

    async def send(self, *, chat_id: int, html: str, buttons=None) -> int:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup   # lazy
        from telegram.error import (BadRequest, ChatMigrated, Forbidden, InvalidToken, NetworkError,
                                    RetryAfter, TelegramError, TimedOut)
        markup = None
        if buttons:
            markup = InlineKeyboardMarkup([[InlineKeyboardButton(t, callback_data=d) for t, d in row]
                                           for row in buttons])
        bot = self._ensure_bot()
        try:
            msg = await bot.send_message(chat_id=chat_id, text=html, parse_mode="HTML",
                                         reply_markup=markup)
        except (BadRequest, Forbidden, RetryAfter, InvalidToken, ChatMigrated) as exc:
            # Explicit API rejections (NB: BadRequest subclasses NetworkError in PTB,
            # so it must be matched first) — the message was NOT delivered.
            raise DeliveryRejected(sanitize_telegram_error(exc, token=self._token,
                                                           chat_id=str(chat_id))) from exc
        except (TimedOut, NetworkError) as exc:
            raise DeliveryAmbiguous(type(exc).__name__) from exc
        except TelegramError as exc:
            raise DeliveryRejected(sanitize_telegram_error(exc, token=self._token,
                                                           chat_id=str(chat_id))) from exc
        return msg.message_id

    async def edit(self, *, chat_id: int, message_id: int, html: str, buttons=None) -> None:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        from telegram.error import (BadRequest, ChatMigrated, Forbidden, InvalidToken, NetworkError,
                                    RetryAfter, TelegramError, TimedOut)
        markup = None
        if buttons:
            markup = InlineKeyboardMarkup([[InlineKeyboardButton(t, callback_data=d) for t, d in row]
                                           for row in buttons])
        bot = self._ensure_bot()
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=html,
                                        parse_mode="HTML", reply_markup=markup)
        except (BadRequest, Forbidden, RetryAfter, InvalidToken, ChatMigrated) as exc:
            raise DeliveryRejected(sanitize_telegram_error(exc, token=self._token,
                                                           chat_id=str(chat_id))) from exc
        except (TimedOut, NetworkError) as exc:
            raise DeliveryAmbiguous(type(exc).__name__) from exc
        except TelegramError as exc:
            raise DeliveryRejected(sanitize_telegram_error(exc, token=self._token,
                                                           chat_id=str(chat_id))) from exc

    async def answer(self, callback_id: str, text: str = "") -> None:
        await self._ensure_bot().answer_callback_query(callback_id, text=text[:200])

    async def get_me(self):
        return await self._ensure_bot().get_me()

    async def get_updates(self, *, offset: Optional[int], timeout: int) -> list:
        updates = await self._ensure_bot().get_updates(
            offset=offset, timeout=timeout, allowed_updates=["message", "callback_query"])
        return [u.to_dict() for u in updates]


def _msg(chat_id: int, text: str, buttons=None, lang: str = "ru") -> Outgoing:
    return Outgoing(kind="message", chat_id=chat_id, html=assert_descriptive(text, lang), buttons=buttons)


def _help(lang: str) -> str:
    return t(lang, "help") + "\n\n" + t(lang, "disclaimer")


def _help_buttons(lang: str) -> list:
    return [[(t(lang, "btn_terms"), "terms")]]


def _lang_of(user) -> str:
    return (user or {}).get("lang") or "ru"


def _lang_buttons(prefix: str) -> list:
    return [[(t("ru", "btn_ru"), f"{prefix}:ru"), (t("ru", "btn_en"), f"{prefix}:en")]]


class BetaBotHandler:
    def __init__(self, store, cfg: BetaConfig, *, switches: Callable[[], BetaSwitches],
                 owner_user_id: Optional[int], clock: Callable[[], datetime],
                 bot_username: Optional[str] = None, telemetry_salt: Any = _FROM_ENV):
        self.store, self.cfg, self.switches = store, cfg, switches
        self.owner, self.clock = owner_user_id, clock
        self.bot_username = bot_username
        self._telemetry_salt = telemetry_salt

    def _salt(self) -> Optional[str]:
        if self._telemetry_salt is _FROM_ENV:
            return telemetry_salt()
        return self._telemetry_salt

    async def handle(self, update: Mapping[str, Any]) -> list:
        update_id = int(update["update_id"])
        try:
            async with self.store.connect() as conn:
                async with conn.transaction():
                    last = await conn.get_last_update_id(BOT_NAME)
                    if last is not None and update_id <= last:
                        return []
                    out = await self._dispatch(conn, update)
                    await conn.set_last_update_id(BOT_NAME, update_id)
            return out
        except Exception as exc:  # noqa: BLE001 - one bad update must not crash-loop the poller
            logger.warning("beta bot update failed: %s", type(exc).__name__)
        # the update's own writes were rolled back; move past it so the next poll does not replay it
        async with self.store.connect() as conn:
            async with conn.transaction():
                last = await conn.get_last_update_id(BOT_NAME)
                if last is None or update_id > last:
                    await conn.set_last_update_id(BOT_NAME, update_id)
        return []

    async def _allowed(self, conn, uid: int) -> bool:
        return is_owner(self.owner, uid) or await conn.allowlist_contains(uid)

    async def _dispatch(self, conn, update) -> list:
        if update.get("callback_query"):
            return await self._callback(conn, update["callback_query"])
        m = update.get("message") or {}
        if (m.get("chat") or {}).get("type") != "private" or not m.get("from"):
            return []
        uid, chat_id = int(m["from"]["id"]), int(m["chat"]["id"])
        cmd, args = parse_command(m.get("text"))
        now = self.clock()
        if cmd and cmd.startswith("admin_"):
            res = await handle_admin(conn, self.cfg, self.switches(), owner_user_id=self.owner,
                                     actor_user_id=uid, command=cmd, args=args, now=now,
                                     bot_username=self.bot_username)
            if not res["authorized"]:
                return [_msg(chat_id, t("ru", "unknown_cmd"), lang="ru")]
            out = [Outgoing(kind="message", chat_id=chat_id,
                            html=f"<pre>{html.escape(res['reply'] or '', quote=False)}</pre>")]
            if res["broadcast"]:
                out += [_msg(c, res["broadcast"], lang="ru") for c in await conn.active_user_chats()]
            for item in res.get("direct") or []:
                dest, text, *rest = item
                out.append(_msg(int(dest), text, lang=rest[0] if rest else "ru"))
            return out
        user = await conn.get_user(uid)
        lang = _lang_of(user)
        if cmd == "start":
            return await self._start(conn, uid, chat_id, args, user, lang, now)
        if cmd == "delete_me":
            on_waitlist = await conn.waitlist_contains(uid)
            if user is None and not await conn.allowlist_contains(uid) and not on_waitlist:
                return [_msg(chat_id, t("ru", "closed_beta"), lang="ru")]
            removed = await conn.delete_participant(uid)
            await conn.insert_audit(action="user_delete_me", authorized=True,
                                    actor_fingerprint="participant", target_fingerprint=None,
                                    result="OK", detail=removed)
            return [_msg(chat_id, t(lang, "deleted"), lang=lang)]
        if user is None or user["status"] != "ACTIVE":
            if user is not None or await self._allowed(conn, uid):
                return [_msg(chat_id, t(lang, "not_joined"), lang=lang)]
            return [_msg(chat_id, t("ru", "closed_beta"), lang="ru")]
        if cmd == "lang":
            return await self._reply(conn, user, chat_id, lang, now, "cmd_lang",
                                     [_msg(chat_id, t(lang, "choose_lang"), _lang_buttons("set"), lang=lang)])
        if cmd == "btc":
            html_text, buttons = await self._btc(conn, now, lang)
            return await self._reply(conn, user, chat_id, lang, now, "cmd_btc",
                                     [_msg(chat_id, html_text, buttons, lang=lang)])
        if cmd == "catchup":
            hours = parse_catchup_hours(args)
            if hours is None:
                return [_msg(chat_id, t(lang, "catchup_usage"), lang=lang)]
            html_text, buttons = await self._catchup(conn, now, lang, hours,
                                                    push_enabled=bool(user.get("push_enabled", True)))
            return await self._reply(conn, user, chat_id, lang, now, "cmd_catchup",
                                     [_msg(chat_id, html_text, buttons, lang=lang)])
        if cmd == "push":
            reply, detail = await self._push_cmd(conn, uid, user, lang, args)
            # detail = what was requested ("on", "off", "levels:off", …) or "status": the history
            # of preferences is reconstructable from the activity log.
            return await self._reply(conn, user, chat_id, lang, now, "cmd_push", [_msg(chat_id, reply, lang=lang)],
                                     detail=detail)
        if cmd == "research":
            from beta.research_link import format_research
            return await self._reply(conn, user, chat_id, lang, now, "cmd_research",
                                     [_msg(chat_id, part, lang=lang) for part in format_research(lang)])
        if cmd in ("levels", "risk", "alert", "events", "accuracy"):
            reply = await self._decision_cmd(conn, cmd, user, now, lang, args)
            return await self._reply(conn, user, chat_id, lang, now, f"cmd_{cmd}",
                                     [_msg(chat_id, reply, lang=lang)])
        if cmd == "brief":
            arg = (args or "").strip().lower()
            if arg in ("on", "off"):
                await conn.set_brief_enabled(uid, arg == "on")
                reply = t(lang, "brief_on_ok" if arg == "on" else "brief_off_ok")
            else:
                on = user.get("brief_enabled", True)
                reply = t(lang, "brief_usage", state=t(lang, "brief_state_on" if on else "brief_state_off"))
            return await self._reply(conn, user, chat_id, lang, now, "cmd_brief", [_msg(chat_id, reply, lang=lang)],
                                     detail=arg if arg in ("on", "off") else "status")
        if cmd == "history":
            rows = await conn.fetch_episode_history(symbol=self.cfg.symbol, limit=HISTORY_LIMIT)
            outcomes = {r["episode_pk"]: await conn.fetch_outcomes(r["episode_pk"]) for r in rows}
            return await self._reply(conn, user, chat_id, lang, now, "cmd_history",
                                     [_msg(chat_id, format_history(rows, outcomes, lang), lang=lang)])
        if cmd == "terms":
            return await self._reply(conn, user, chat_id, lang, now, "cmd_terms",
                                     [_msg(chat_id, t(lang, "terms"), lang=lang)])
        if cmd == "help":
            return await self._reply(conn, user, chat_id, lang, now, "cmd_help",
                                     [_msg(chat_id, _help(lang), _help_buttons(lang), lang=lang)])
        if cmd == "feedback":
            return await self._feedback(conn, user, chat_id, lang, now, args)
        if cmd == "stop":
            await conn.stop_user(telegram_user_id=uid, now=now)
            return await self._reply(conn, user, chat_id, lang, now, "cmd_stop",
                                     [_msg(chat_id, t(lang, "paused"), lang=lang)])
        return [_msg(chat_id, t(lang, "unknown_cmd"), lang=lang)]

    async def _start(self, conn, uid, chat_id, args, user, lang, now) -> list:
        if user is not None and user["status"] == "ACTIVE":
            return await self._reply(conn, user, chat_id, lang, now, "cmd_start",
                                     [_msg(chat_id, _help(lang), _help_buttons(lang), lang=lang)])
        code = start_code(args)
        if code and not await conn.allowlist_contains(uid):
            outcome = await conn.redeem_invite(
                code, uid, now, int(self.cfg["access"]["max_active_users"]), self.owner)
            if outcome not in ("OK", "ALREADY") and not is_owner(self.owner, uid):
                await conn.record_rejected_start(uid, now, self._salt())
                return [self._waitlist_offer(chat_id)]
        if await self._allowed(conn, uid):
            if user is None:
                return [_msg(chat_id, t("ru", "choose_lang"), _lang_buttons("pick"), lang="ru")]
            return [_msg(chat_id, t(lang, "privacy"),
                         [[(t(lang, "btn_join"), f"join:{lang}")]], lang=lang)]
        await conn.record_rejected_start(uid, now, self._salt())
        return [self._waitlist_offer(chat_id)]

    def _waitlist_offer(self, chat_id: int) -> Outgoing:
        return _msg(chat_id, t("ru", "waitlist_offer"),
                    [[(t("ru", "btn_request_access"), "wl:ask")]], lang="ru")

    async def _welcome(self, conn, lang: str) -> str:
        from beta.config import effective_push_enabled
        text = t(lang, "welcome")
        if effective_push_enabled(self.switches(), await conn.get_admin_push_enabled()):
            text += "\n" + t(lang, "welcome_push")
        return text

    async def _feedback(self, conn, user, chat_id, lang, now, args) -> list:
        text = (args or "").strip()
        limits = self.cfg.section("feedback")
        if not text:
            return [_msg(chat_id, t(lang, "feedback_usage"), lang=lang)]
        if len(text) > int(limits["max_chars"]):
            return [_msg(chat_id, t(lang, "feedback_too_long", n=limits["max_chars"]), lang=lang)]
        day = now.astimezone(timezone.utc).date()
        sent = await conn.count_feedback_messages_on_utc_day(int(user["user_pk"]), day)
        if sent >= int(limits["max_per_utc_day"]):
            return [_msg(chat_id, t(lang, "feedback_daily_limit", n=limits["max_per_utc_day"]), lang=lang)]
        await conn.insert_feedback_message(user_pk=int(user["user_pk"]), text=text, lang=lang,
                                           created_at=now)
        await self._note(conn, user, "cmd_feedback", now)
        confirm = _msg(chat_id, t(lang, "feedback_thanks"), lang=lang)
        forward = self._owner_forward(user, lang, now, text)
        if forward is None:
            logger.warning("beta feedback forward skipped: owner unavailable")
            return [confirm]
        return [confirm, forward]

    def _owner_forward(self, user, lang: str, now: datetime, text: str):
        """Owner copy of user text. Not passed through assert_descriptive."""
        if self.owner is None:
            return None
        from beta.admin import fingerprint
        from beta.i18n import fmt_kyiv_date_hm
        fp = fingerprint(int(user["telegram_user_id"]))
        when = fmt_kyiv_date_hm(now, "en")
        body = (f"Feedback · {fp} · {lang} · {when}\n"
                f"{html.escape(text, quote=False)}\n"
                f"Reply: /admin_reply {fp} &lt;text&gt;")
        return Outgoing(kind="message", chat_id=int(self.owner), html=body)

    async def _note(self, conn, user, action: str, at: datetime, detail: Optional[str] = None) -> None:
        if not user or user.get("user_pk") is None:
            return
        try:
            await conn.record_activity(user_pk=user["user_pk"], action=action,
                                       lang=_lang_of(user), at=at, detail=detail)
        except Exception as exc:  # noqa: BLE001 - telemetry must not fail the reply
            logger.warning("beta activity note failed: %s", type(exc).__name__)

    async def _prepend_notice(self, conn, user, chat_id: int, lang: str, out: list) -> list:
        if user is None or user.get("status") != "ACTIVE":
            return out
        seen = int(user.get("privacy_notice_version", PRIVACY_NOTICE_VERSION))
        if seen >= PRIVACY_NOTICE_VERSION:
            return out
        await conn.mark_privacy_notice_seen(int(user["telegram_user_id"]), PRIVACY_NOTICE_VERSION)
        user["privacy_notice_version"] = PRIVACY_NOTICE_VERSION
        return [_msg(chat_id, t(lang, "privacy"), lang=lang), *out]

    async def _reply(self, conn, user, chat_id, lang, now, action, out, detail: Optional[str] = None) -> list:
        if action:
            await self._note(conn, user, action, now, detail)
        return await self._prepend_notice(conn, user, chat_id, lang, out)

    async def _btc(self, conn, now: datetime, lang: str):
        """Render /btc from the shared view builder and record exactly what was shown
        (view model + rendered text + digests + lang; no user id)."""
        from beta.formatter import btc_buttons, format_btc
        view = await self._view(conn, now, kind="btc")
        text = format_btc(self.cfg, view, lang)
        view_pk = await persist_view(conn, view, now=now, text=text, lang=lang, kind="btc")
        return text, btc_buttons(view, lang, view_pk)

    async def _catchup(self, conn, now: datetime, lang: str, hours: int, *, push_enabled: bool = True):
        """/catchup: the same view object with the window summary and 1h/4h labels."""
        from beta.formatter import btc_buttons, format_catchup
        view = await self._view(conn, now, kind="catchup", window_hours=hours)
        text = format_catchup(self.cfg, view, lang, push_enabled=push_enabled)
        view_pk = await persist_view(conn, view, now=now, text=text, lang=lang, kind="catchup")
        return text, btc_buttons(view, lang, view_pk)

    # ---- decision support (PRODUCT_DECISION_V2) ------------------------------------------
    _PUSH_PREFS = {"levels": "push_levels", "level": "push_levels", "уровни": "push_levels",
                   "events": "push_events", "event": "push_events", "события": "push_events",
                   "moves": "push_moves", "move": "push_moves", "движения": "push_moves",
                   "hour": "push_hours", "hours": "push_hours", "час": "push_hours"}

    def _push_status(self, user, lang: str) -> str:
        word = lambda v: t(lang, "on_word" if v else "off_word")  # noqa: E731
        return t(lang, "push_status", master=word(user.get("push_enabled", True)),
                 levels=word(user.get("push_levels", True)), events=word(user.get("push_events", True)),
                 moves=word(user.get("push_moves", True)), hours=word(user.get("push_hours", True)))

    async def _push_cmd(self, conn, uid: int, user, lang: str, args) -> tuple:
        parts = (args or "").strip().lower().split()
        if len(parts) == 1 and parts[0] in ("on", "off"):
            await conn.set_push_pref(uid, "push_enabled", parts[0] == "on")
            detail = parts[0]
        elif len(parts) == 2 and parts[0] in self._PUSH_PREFS and parts[1] in ("on", "off"):
            await conn.set_push_pref(uid, self._PUSH_PREFS[parts[0]], parts[1] == "on")
            detail = f"{self._PUSH_PREFS[parts[0]][5:]}:{parts[1]}"
        else:
            return self._push_status(user, lang), "status"
        fresh = await conn.get_user(uid)
        return t(lang, "push_pref_ok", status=self._push_status(fresh, lang)), detail

    async def _decision_cmd(self, conn, cmd: str, user, now: datetime, lang: str, args) -> str:
        from beta import decision_format as df
        from beta.decision import build_decision, latest_stats
        if cmd == "events":
            from beta.calendar_events import load_calendar, upcoming
            cal = load_calendar()
            stats = await latest_stats(conn, now=now)
            kinds = ((stats or {}).get("events") or {}).get("kinds") or {}
            evs = [{"kind": e["kind"], "at": e["at"].isoformat(), "stats": kinds.get(e["kind"])}
                   for e in upcoming(cal, now=now, hours=14 * 24) if e["kind"] != "EXPIRY_WEEKLY"]
            return df.format_events(evs, lang, funding_utc=(cal["recurring"].get("funding_utc") or ()))
        if cmd == "accuracy":
            from datetime import timedelta
            stats = await latest_stats(conn, now=now)
            live = await conn.forecast_accuracy(since=now - timedelta(days=30))
            return df.format_accuracy((stats or {}).get("range_model"), live, lang)
        block = await build_decision(conn, self.cfg, now=now)
        if cmd == "levels":
            return df.format_levels(block, lang, now=now)
        if cmd == "risk":
            mode, val = df.parse_risk_arg(args, block.get("price"))
            if mode == "bad":
                return t(lang, "rk_usage")
            stats = await latest_stats(conn, now=now)
            return df.format_risk(block, (stats or {}).get("range_model"), lang,
                                  stop_pct=val if mode == "pct" else None)
        return await self._alert_cmd(conn, user, now, lang, args, block)

    async def _alert_cmd(self, conn, user, now: datetime, lang: str, args, block) -> str:
        from beta import decision_format as df
        from beta.decision import latest_stats
        from beta.i18n import fmt_price, fmt_signed_pct
        parts = (args or "").strip().lower().split()
        price = block.get("price")
        if parts and parts[0] in ("del", "delete", "удалить", "rm"):
            alerts = await conn.list_price_alerts(user["user_pk"])
            if len(parts) == 2 and parts[1] in ("all", "все"):
                n = await conn.cancel_price_alerts(user["user_pk"], now=now)
            elif len(parts) == 2 and parts[1].isdigit() and 1 <= int(parts[1]) <= len(alerts):
                n = await conn.cancel_price_alerts(user["user_pk"], now=now,
                                                   price_alert_pk=alerts[int(parts[1]) - 1]["price_alert_pk"])
            else:
                return t(lang, "al_usage")
            return t(lang, "al_deleted", n=n)
        if not parts:
            alerts = await conn.list_price_alerts(user["user_pk"])
            if not alerts:
                return t(lang, "al_list_none")
            lines = [t(lang, "al_list_head")]
            for k, a in enumerate(alerts, 1):
                dist = fmt_signed_pct((a["price"] / price - 1) * 100.0, lang) if price else "—"
                lines.append(t(lang, "al_list_line", k=k, price=fmt_price(a["price"], lang), dist=dist))
            lines.append(t(lang, "al_list_footer"))
            return "\n".join(lines)
        raw = "".join(parts).replace(",", ".").replace("$", "")
        try:
            level = float(raw)
        except ValueError:
            return t(lang, "al_usage")
        if not math.isfinite(level):        # "nan" / "inf" parse as floats
            return t(lang, "al_usage")
        if not price:
            return t(lang, "al_no_price")
        dist = (level / price - 1) * 100.0
        if level <= 0 or abs(dist) > 30:
            return t(lang, "al_usage")
        if abs(dist) < 0.05:
            return t(lang, "al_too_close", now=fmt_price(price, lang))
        made = await conn.add_price_alert(user_pk=user["user_pk"], price=level, created_price=price, now=now,
                                          max_active=int(self.cfg.section("decision")["max_price_alerts"]))
        if made is None:
            return t(lang, "al_limit", n=int(self.cfg.section("decision")["max_price_alerts"]))
        stats = await latest_stats(conn, now=now)
        model = (stats or {}).get("range_model")
        hz = ((block.get("corridor") or {}).get("horizons") or {}).get("24h")
        if model and hz:
            from beta.rangecast import touch_probability
            p = touch_probability(model, "24h", hz["scale_pct"], abs(dist))
            return t(lang, "al_set", price=fmt_price(level, lang), dist=fmt_signed_pct(dist, lang),
                     now=fmt_price(price, lang), p=df.fmt_prob(p, lang))
        return t(lang, "al_set_plain", price=fmt_price(level, lang), dist=fmt_signed_pct(dist, lang),
                 now=fmt_price(price, lang))

    async def _view(self, conn, now: datetime, *, kind: str, window_hours: Optional[int] = None) -> dict:
        return await build_view(conn, self.cfg, now=now, kind=kind, window_hours=window_hours,
                                maturity_days=self._maturity_days(),
                                d7_enabled=effective_d7_enabled(self.cfg, await conn.get_admin_d7_enabled()))

    def _maturity_days(self) -> float:
        """The percentile core's maturity span (Stage-2 confidence tiers), not a UI constant."""
        from common.stage2_config import Stage2Config
        tiers = Stage2Config.load().resolve(self.cfg.symbol)["percentiles"]["confidence_tiers"]
        return float(tiers["building_below_days"])

    async def _readiness_details(self, conn, chat_id: int, answer, lang: str) -> list:
        from beta.formatter import format_readiness_details
        from beta.readiness import readiness
        latest = await conn.fetch_latest_live_tape(symbol=self.cfg.symbol)
        rd = readiness(self.cfg, latest, maturity_days=self._maturity_days())
        if rd is None:
            return [answer(t(lang, "no_evaluation"))]
        if effective_d7_enabled(self.cfg, await conn.get_admin_d7_enabled()):
            from beta.regime_d7 import warmup_for_readiness
            rd["impact_context"] = await warmup_for_readiness(conn, now=self.clock())
        return [answer(""), _msg(chat_id, format_readiness_details(self.cfg, rd, lang), lang=lang)]

    async def _open_tab(self, conn, cq, chat_id: int, answer, *, kind: str, view_pk: int, tab: str,
                        user=None) -> list:
        """Render a tab from the persisted view only, then record the open."""
        from beta.formatter import (detail_tab_buttons, format_1h_tab, format_24h_tab, format_event_tab,
                                    view_id8)
        row = await conn.fetch_btc_view(view_pk)
        if row is None:
            return [answer(t("ru", "not_available"))]
        payload, lang = row["payload"], row.get("lang") or "ru"
        fail = payload.get("product_status") in ("DATA STALE", "DATA DEGRADED")
        focus = payload.get("active_episode") or payload.get("last_event")
        if tab == "event" and not (focus and focus.get("episode_id")):
            return [answer(t(lang, "not_available"))]
        if tab in ("1h", "24h") and fail:
            return [answer(t(lang, "not_available"))]
        vid = view_id8(row.get("payload_digest") or "")
        if tab == "event":
            html_text = format_event_tab(self.cfg, payload, lang, vid)
        elif tab == "24h":
            html_text = format_24h_tab(self.cfg, payload, lang, vid)
        else:
            html_text = format_1h_tab(self.cfg, payload, lang, vid)
        await conn.insert_details_open(view_pk=view_pk, tab=tab, lang=lang, opened_at=self.clock())
        await self._note(conn, user, f"tab_{tab}", self.clock())
        buttons = detail_tab_buttons(payload, lang, view_pk)
        if kind == "e":
            message_id = ((cq.get("message") or {}).get("message_id"))
            if message_id is None:
                return [answer(""), _msg(chat_id, html_text, buttons, lang=lang)]
            return [answer(""), Outgoing(kind="edit", chat_id=chat_id, message_id=int(message_id),
                                         html=html_text, buttons=buttons)]
        return [answer(""), _msg(chat_id, html_text, buttons, lang=lang)]

    async def _callback(self, conn, cq) -> list:
        uid = int((cq.get("from") or {}).get("id", 0))
        chat_id = int(((cq.get("message") or {}).get("chat") or {}).get("id", uid))
        data, cid = cq.get("data") or "", cq.get("id")
        answer = lambda text: Outgoing(kind="answer", callback_id=cid, html=text)  # noqa: E731
        if data == "wl:ask":
            if await self._allowed(conn, uid):
                return [answer("")]
            await conn.waitlist_add(uid, self.clock())
            return [answer(""), _msg(chat_id, t("ru", "waitlist_consent"), lang="ru")]
        if data.startswith("pick:") and data[5:] in ("ru", "en"):
            if not await self._allowed(conn, uid):
                return [answer(t("ru", "closed_beta"))]
            lang = data[5:]
            return [answer(""), _msg(chat_id, t(lang, "privacy"),
                                     [[(t(lang, "btn_join"), f"join:{lang}")]], lang=lang)]
        if data == "join" or (data.startswith("join:") and data[5:] in ("ru", "en")):
            if not await self._allowed(conn, uid):
                return [answer(t("ru", "closed_beta"))]
            lang = "ru" if data == "join" else data[5:]
            await conn.join_user(telegram_user_id=uid, chat_id=chat_id, now=self.clock(), lang=lang)
            joined = await conn.get_user(uid)
            await self._note(conn, joined, "cmd_start", self.clock())
            welcome = await self._welcome(conn, lang)
            return [answer(t(lang, "joined")), _msg(chat_id, welcome, lang=lang)]
        user = await conn.get_user(uid)
        lang = _lang_of(user)
        if data.startswith("set:") and data[4:] in ("ru", "en"):
            if user is None or user["status"] != "ACTIVE":
                return [answer(t(lang, "not_available"))]
            chosen = data[4:]
            await conn.set_user_lang(uid, chosen)
            user = await conn.get_user(uid)
            out = [answer(t(chosen, "lang_saved")), _msg(chat_id, t(chosen, "lang_saved"), lang=chosen)]
            return await self._reply(conn, user, chat_id, chosen, self.clock(), "lang_set", out)
        if data == "terms":
            if user is None or user["status"] != "ACTIVE":
                return [answer(t(lang, "not_available"))]
            return await self._reply(conn, user, chat_id, lang, self.clock(), "cmd_terms",
                                     [answer(""), _msg(chat_id, t(lang, "terms"), lang=lang)])
        tab = _parse_tab(data)
        if tab is not None:
            if user is None or user["status"] != "ACTIVE":
                return [answer(t(lang, "not_available"))]
            opened = await self._open_tab(conn, cq, chat_id, answer, kind=tab[0], view_pk=tab[1],
                                          tab=tab[2], user=user)
            return await self._prepend_notice(conn, user, chat_id, lang, opened)
        if user is None or user["status"] != "ACTIVE" or len(data) < 3 or data[1] != ":":
            return [answer(t(lang, "not_available"))]
        if data == "r:latest":
            return await self._readiness_details(conn, chat_id, answer, lang)
        if data in ("L:levels", "L:risk"):
            cmd = data[2:]
            reply = await self._decision_cmd(conn, cmd, user, self.clock(), lang, "")
            return await self._reply(conn, user, chat_id, lang, self.clock(), f"btn_{cmd}",
                                     [answer(""), _msg(chat_id, reply, lang=lang)])
        if data == "n:latest" or data[0] in ("c", "d"):
            # Retired: live-state Details, and the episode Details of older pushes (they
            # show the detector name, internal id and rules version; decision §3 row 9).
            return [answer(t(lang, "not_available"))]
        ep = await conn.fetch_episode_by_public_id(data[2:])
        if ep is None:
            return [answer(t(lang, "unknown_episode"))]
        if data[0] in ("u", "n"):
            await conn.upsert_feedback(user_pk=user["user_pk"], episode_pk=ep.episode_pk,
                                       vote="USEFUL" if data[0] == "u" else "NOISE")
            action = "btn_useful" if data[0] == "u" else "btn_noise"
            return await self._reply(conn, user, chat_id, lang, self.clock(), action,
                                     [answer(t(lang, "feedback_recorded"))])
        return [answer(t(lang, "not_available"))]


def _parse_tab(data: str):
    """`o:<view_pk>:<tab>` opens a message; `e:<view_pk>:<tab>` edits it. Both ≤ 64 bytes."""
    if len(data) > 64:
        return None
    parts = data.split(":")
    if len(parts) != 3 or parts[0] not in ("o", "e") or parts[2] not in ("event", "1h", "24h"):
        return None
    if not parts[1].isdigit():
        return None
    return parts[0], int(parts[1]), parts[2]


async def deliver_outgoing(sender: BetaTelegramSender, out: Sequence[Outgoing]) -> None:
    for o in out:
        try:
            if o.kind == "answer":
                await sender.answer(o.callback_id, o.html)
            elif o.kind == "edit":
                await sender.edit(chat_id=o.chat_id, message_id=o.message_id, html=o.html, buttons=o.buttons)
            else:
                await sender.send(chat_id=o.chat_id, html=o.html, buttons=o.buttons)
        except Exception as exc:  # noqa: BLE001 - never log ids/tokens
            logger.warning("beta bot reply failed: %s", type(exc).__name__)


async def run_bot_service(*, store, cfg: BetaConfig, switches: Callable[[], BetaSwitches],
                          sender: BetaTelegramSender, owner_user_id: Optional[int],
                          stop: asyncio.Event, poll_timeout_s: int = 25) -> None:
    from storage.beta_v0_store import BOT_LOCK_KEY
    username = None
    try:
        me = await sender.get_me()
        username = getattr(me, "username", None)
    except Exception as exc:  # noqa: BLE001 - never log the token
        logger.warning("beta bot username unavailable: %s", type(exc).__name__)
    handler = BetaBotHandler(store, cfg, switches=switches, owner_user_id=owner_user_id,
                             clock=lambda: datetime.now(timezone.utc), bot_username=username)
    async with store.advisory_lock(BOT_LOCK_KEY) as acquired:
        if not acquired:
            raise RuntimeError("another beta bot poller holds the lock")
        while not stop.is_set():
            async with store.connect() as conn:
                last = await conn.get_last_update_id(BOT_NAME)
            try:
                updates = await sender.get_updates(offset=None if last is None else last + 1,
                                                   timeout=poll_timeout_s)
                ok = True
            except Exception as exc:  # noqa: BLE001
                logger.warning("beta bot polling error: %s", type(exc).__name__)
                updates, ok = [], False
                await asyncio.sleep(5)
            for u in updates:
                await deliver_outgoing(sender, await handler.handle(u))
            async with store.connect() as conn:
                await conn.record_health("bot", now=datetime.now(timezone.utc), success=ok,
                                         detail={"updates": len(updates)})


def main() -> None:   # systemd entry point: python -m runtime.beta_bot
    # shared setup: quiets httpx/httpcore/telegram (their INFO request lines carry the
    # bot-token URL) and attaches the Telegram-token redaction filter to the stream
    setup_logging("INFO")
    from beta.config import BetaSecrets, resolve_switches
    from common.config import Secrets as _S  # noqa: F401 - loads .env
    from runtime.beta_cli import load_postgres_dsn
    cfg = BetaConfig.load()
    switches = resolve_switches(cfg)
    if not switches.enabled:
        logger.info("beta disabled (config/env hard switch); bot not started")
        return
    if not switches.telegram:
        logger.info("no-Telegram shadow mode (BETA_TELEGRAM_ENABLED=0); bot not started")
        return
    secrets = BetaSecrets.from_env()
    if not secrets.bot_token:
        raise SystemExit("BETA_TELEGRAM_BOT_TOKEN is not set")

    async def _run():
        from storage.db import Database
        db = Database(load_postgres_dsn())
        await db.connect()
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, stop.set)
        try:
            await db.init_beta_v0_schema()
            await run_bot_service(store=db.beta_store(), cfg=cfg, switches=lambda: resolve_switches(cfg),
                                  sender=BetaTelegramSender(secrets.bot_token),
                                  owner_user_id=secrets.owner_user_id, stop=stop)
        finally:
            await db.close()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
