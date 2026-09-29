"""Beta V0.2 multi-user Telegram bot (long polling) — isolated from the legacy
forecast notifier (runtime/telegram_cli.py / notifications/telegram_*): it reuses
only `notifications.telegram_client.TelegramSender` (subclassed, unmodified) and
none of the legacy candidate/formatter/outbox.

Each update is handled in ONE transaction that also persists the last processed
update id, so a restart never reprocesses an old command/callback. Replies are
sent after commit. Unauthorized /start gets "closed private beta" and nothing is
persisted about that user. No raw Telegram id is ever logged.
"""
from __future__ import annotations

import asyncio
import hashlib
import html
import logging
import signal
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Optional, Sequence

from beta.admin import collect_status, fingerprint, handle_admin, is_owner, parse_command
from beta.config import BetaConfig, BetaSwitches
from beta.delivery import DeliveryAmbiguous, DeliveryRejected
from beta.formatter import (CLOSED_BETA_TEXT, HELP_TEXT, PRIVACY_NOTICE, assert_descriptive,
                            format_details, format_history)
from common.logging_setup import setup_logging
from notifications.telegram_client import TelegramSender, sanitize_telegram_error

logger = logging.getLogger("beta.bot")
BOT_NAME = "beta_v0"
HISTORY_LIMIT = 10


@dataclass(frozen=True)
class Outgoing:
    kind: str                                   # 'message' | 'answer'
    chat_id: Optional[int] = None
    html: str = ""
    buttons: Optional[Sequence[Sequence[tuple]]] = None
    callback_id: Optional[str] = None


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

    async def answer(self, callback_id: str, text: str = "") -> None:
        await self._ensure_bot().answer_callback_query(callback_id, text=text[:200])

    async def get_updates(self, *, offset: Optional[int], timeout: int) -> list:
        updates = await self._ensure_bot().get_updates(
            offset=offset, timeout=timeout, allowed_updates=["message", "callback_query"])
        return [u.to_dict() for u in updates]


def _msg(chat_id: int, text: str, buttons=None) -> Outgoing:
    return Outgoing(kind="message", chat_id=chat_id, html=assert_descriptive(text), buttons=buttons)


class BetaBotHandler:
    def __init__(self, store, cfg: BetaConfig, *, switches: Callable[[], BetaSwitches],
                 owner_user_id: Optional[int], clock: Callable[[], datetime]):
        self.store, self.cfg, self.switches = store, cfg, switches
        self.owner, self.clock = owner_user_id, clock

    async def handle(self, update: Mapping[str, Any]) -> list:
        update_id = int(update["update_id"])
        async with self.store.connect() as conn:
            async with conn.transaction():
                last = await conn.get_last_update_id(BOT_NAME)
                if last is not None and update_id <= last:
                    return []
                out = await self._dispatch(conn, update)
                await conn.set_last_update_id(BOT_NAME, update_id)
        return out

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
                                     actor_user_id=uid, command=cmd, args=args, now=now)
            if not res["authorized"]:
                return [_msg(chat_id, "Unknown command. /help")]
            out = [Outgoing(kind="message", chat_id=chat_id,
                            html=f"<pre>{html.escape(res['reply'] or '', quote=False)}</pre>")]
            if res["broadcast"]:
                out += [_msg(c, res["broadcast"]) for c in await conn.active_user_chats()]
            return out
        user = await conn.get_user(uid)
        if cmd == "start":
            if user is not None and user["status"] == "ACTIVE":
                return [_msg(chat_id, HELP_TEXT)]
            if await self._allowed(conn, uid):
                return [_msg(chat_id, PRIVACY_NOTICE, [[("Join", "join")]])]
            return [_msg(chat_id, CLOSED_BETA_TEXT)]           # nothing persisted
        if cmd == "delete_me":
            if user is None and not await conn.allowlist_contains(uid):
                return [_msg(chat_id, CLOSED_BETA_TEXT)]
            removed = await conn.delete_participant(uid)
            await conn.insert_audit(action="user_delete_me", authorized=True,
                                    actor_fingerprint="participant", target_fingerprint=None,
                                    result="OK", detail=removed)
            return [_msg(chat_id, "Your beta participant data was deleted and you were removed "
                                  "from the beta.")]
        if user is None or user["status"] != "ACTIVE":
            if user is not None or await self._allowed(conn, uid):
                return [_msg(chat_id, "Messages are paused or you have not joined yet. Send /start.")]
            return [_msg(chat_id, CLOSED_BETA_TEXT)]
        if cmd == "btc":
            html_text, buttons = await self._btc(conn, now)
            return [_msg(chat_id, html_text, buttons)]
        if cmd == "history":
            rows = await conn.fetch_episode_history(symbol=self.cfg.symbol, limit=HISTORY_LIMIT)
            outcomes = {r["episode_pk"]: await conn.fetch_outcomes(r["episode_pk"]) for r in rows}
            return [_msg(chat_id, format_history(rows, outcomes))]
        if cmd == "help":
            return [_msg(chat_id, HELP_TEXT)]
        if cmd == "stop":
            await conn.stop_user(telegram_user_id=uid, now=now)
            return [_msg(chat_id, "Messages paused. Send /start to resume. Your data is deleted "
                                  "automatically after 30 days, or now with /delete_me.")]
        return [_msg(chat_id, "Unknown command. /help")]

    async def _btc(self, conn, now: datetime):
        """Render /btc from the persisted context projection and record exactly what
        was shown (view model + rendered text + digests; no user id)."""
        from beta.context import btc_view, episodization_digest
        from beta.formatter import btc_buttons, format_btc
        from beta.readiness import readiness
        from beta.state_tape import sha256_json
        st = await collect_status(conn, self.cfg, now)
        ctx = await conn.fetch_latest_context_state(symbol=self.cfg.symbol,
                                                    episodization_digest=episodization_digest(self.cfg))
        # readiness of the SAME latest LIVE tape row the product status is built from
        rd = readiness(self.cfg, st["latest"], maturity_days=self._maturity_days())
        view = btc_view(self.cfg, product=st["status"], state=ctx["state"] if ctx else None,
                        state_digest_value=ctx["state_digest"] if ctx else None, now=now, readiness=rd,
                        detector_open_ids=[e.public_id for e in st["open_episodes"]])
        text = format_btc(self.cfg, view)
        await conn.insert_btc_view(
            requested_at=now, as_of_bucket=datetime.fromisoformat(view["as_of_bucket"]) if view["as_of_bucket"] else None,
            context_state_digest=view["context_state_digest"],
            episodization_version=view["episodization_version"],
            episodization_digest=view["episodization_digest"], payload=view,
            payload_digest=sha256_json(view), rendered_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            rendered_html=text)
        return text, btc_buttons(view)

    def _maturity_days(self) -> float:
        """The percentile core's maturity span (Stage-2 confidence tiers), not a UI constant."""
        from common.stage2_config import Stage2Config
        tiers = Stage2Config.load().resolve(self.cfg.symbol)["percentiles"]["confidence_tiers"]
        return float(tiers["building_below_days"])

    async def _readiness_details(self, conn, chat_id: int, answer) -> list:
        from beta.formatter import format_readiness_details
        from beta.readiness import readiness
        latest = await conn.fetch_latest_live_tape(symbol=self.cfg.symbol)
        rd = readiness(self.cfg, latest, maturity_days=self._maturity_days())
        if rd is None:
            return [answer("No evaluation yet")]
        return [answer(""), _msg(chat_id, format_readiness_details(self.cfg, rd))]

    async def _now_details(self, conn, chat_id: int, answer) -> list:
        from beta.context import episodization_digest
        from beta.formatter import format_now_details
        ctx = await conn.fetch_latest_context_state(symbol=self.cfg.symbol,
                                                    episodization_digest=episodization_digest(self.cfg))
        state = ctx["state"] if ctx else None
        if not state or not state.get("now"):
            return [answer("No evaluation yet")]
        return [answer(""), _msg(chat_id, format_now_details(self.cfg, state))]

    async def _context_details(self, conn, chat_id: int, episode_id: str, answer) -> list:
        from beta.context import episodization_digest, find_episode
        from beta.formatter import format_context_details
        ctx = await conn.fetch_latest_context_state(symbol=self.cfg.symbol,
                                                    episodization_digest=episodization_digest(self.cfg))
        ep = find_episode(ctx["state"] if ctx else None, episode_id)
        if ep is None:
            return [answer("No longer in the current context")]
        return [answer(""), _msg(chat_id, format_context_details(self.cfg, ep, ctx["state"]))]

    async def _callback(self, conn, cq) -> list:
        uid = int((cq.get("from") or {}).get("id", 0))
        chat_id = int(((cq.get("message") or {}).get("chat") or {}).get("id", uid))
        data, cid = cq.get("data") or "", cq.get("id")
        answer = lambda text: Outgoing(kind="answer", callback_id=cid, html=text)  # noqa: E731
        if data == "join":
            if not await self._allowed(conn, uid):
                return [answer(CLOSED_BETA_TEXT)]
            await conn.join_user(telegram_user_id=uid, chat_id=chat_id, now=self.clock())
            return [answer("Joined"), _msg(chat_id, HELP_TEXT)]
        user = await conn.get_user(uid)
        if user is None or user["status"] != "ACTIVE" or len(data) < 3 or data[1] != ":":
            return [answer("Not available")]
        if data[0] == "c":
            return await self._context_details(conn, chat_id, data[2:], answer)
        if data == "n:latest":
            return await self._now_details(conn, chat_id, answer)
        if data == "r:latest":
            return await self._readiness_details(conn, chat_id, answer)
        ep = await conn.fetch_episode_by_public_id(data[2:])
        if ep is None:
            return [answer("Unknown episode")]
        if data[0] == "d":
            return [answer(""), _msg(chat_id, format_details(
                ep, await conn.fetch_transitions(ep.episode_pk), await conn.fetch_outcomes(ep.episode_pk)))]
        if data[0] in ("u", "n"):
            await conn.upsert_feedback(user_pk=user["user_pk"], episode_pk=ep.episode_pk,
                                       vote="USEFUL" if data[0] == "u" else "NOISE")
            return [answer("Feedback recorded (you can change it).")]
        return [answer("Not available")]


async def deliver_outgoing(sender: BetaTelegramSender, out: Sequence[Outgoing]) -> None:
    for o in out:
        try:
            if o.kind == "answer":
                await sender.answer(o.callback_id, o.html)
            else:
                await sender.send(chat_id=o.chat_id, html=o.html, buttons=o.buttons)
        except Exception as exc:  # noqa: BLE001 - never log ids/tokens
            logger.warning("beta bot reply failed: %s", type(exc).__name__)


async def run_bot_service(*, store, cfg: BetaConfig, switches: Callable[[], BetaSwitches],
                          sender: BetaTelegramSender, owner_user_id: Optional[int],
                          stop: asyncio.Event, poll_timeout_s: int = 25) -> None:
    from storage.beta_v0_store import BOT_LOCK_KEY
    handler = BetaBotHandler(store, cfg, switches=switches, owner_user_id=owner_user_id,
                             clock=lambda: datetime.now(timezone.utc))
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
