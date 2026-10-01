"""Welcome after Join, /feedback, and /admin_reply."""
from datetime import datetime, timedelta, timezone

import pytest

from beta.admin import classify_fingerprint, fingerprint
from beta.i18n import assert_descriptive, t
from beta_fakes import CFG, ON, ON_PUSH, TEST_DSN, Clock, fresh_pool, run
from storage.beta_v0_store import BetaStore

pytestmark = pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)")

NOW = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
OWNER = 900000000001
WELCOME_RU = (
    "Добро пожаловать в Signalbot (закрытая бета).\n"
    "Бот следит за BTC-фьючерсами на Binance, Bybit и OKX и показывает, когда на рынке "
    "происходит что-то необычное: резкие движения цены, всплески Delta, ликвидации, "
    "заметные изменения OI.\n"
    "/btc — состояние рынка сейчас. Кнопки 1ч и 24ч — картина за час и сутки.\n"
    "/terms — что значат термины.\n"
    "/lang — сменить язык.\n"
    "Бот только описывает рынок, это не торговые советы.\n"
    "Отзывы и вопросы: /feedback ваш текст"
)
WELCOME_EN = (
    "Welcome to Signalbot (closed beta).\n"
    "The bot watches BTC perpetual futures on Binance, Bybit and OKX and shows when "
    "something unusual happens: sharp price moves, Delta spikes, liquidations, notable "
    "OI changes.\n"
    "/btc — the market right now. The 1h and 24h buttons show the last hour and day.\n"
    "/terms — what the terms mean.\n"
    "/lang — change the language.\n"
    "The bot only describes the market; it is not trading advice.\n"
    "Feedback and questions: /feedback your text"
)
PUSH_RU = "Иногда бот сам пришлёт короткое сообщение — не больше 3 в день."
PUSH_EN = "Sometimes the bot will send a short message on its own — no more than 3 a day."


def _msg(uid, text, update_id):
    return {"update_id": update_id, "message": {"from": {"id": uid}, "chat": {"id": uid, "type": "private"},
                                                "text": text}}


def _cb(uid, data, update_id):
    return {"update_id": update_id, "callback_query": {
        "id": f"cb{update_id}", "from": {"id": uid},
        "message": {"chat": {"id": uid}, "message_id": 1}, "data": data}}


def _handler(pool, *, switches=ON, owner=OWNER):
    from runtime.beta_bot import BetaBotHandler
    return BetaBotHandler(BetaStore(pool), CFG, switches=lambda: switches, owner_user_id=owner,
                          clock=Clock(NOW), bot_username="BetaBot")


async def _rows(pool, sql, *args):
    async with pool.acquire() as c:
        return [dict(r) for r in await c.fetch(sql, *args)]


def test_new_bot_strings_pass_both_forbidden_lists():
    keys = ("welcome", "welcome_push", "feedback_usage", "feedback_too_long",
            "feedback_daily_limit", "feedback_thanks", "team_reply", "help", "privacy")
    for key in keys:
        for lang in ("ru", "en"):
            text = t(lang, key) if "{" not in t(lang, key) else t(lang, key, n=5)
            assert_descriptive(text, "ru")
            assert_descriptive(text, "en")
    assert t("ru", "welcome") == WELCOME_RU
    assert t("en", "welcome") == WELCOME_EN
    assert t("ru", "welcome_push") == PUSH_RU
    assert t("en", "welcome_push") == PUSH_EN
    assert "/feedback" in t("ru", "help") and "/feedback" in t("en", "help")


def test_ambiguous_fingerprint_is_not_a_send():
    rows = [{"telegram_user_id": 11, "chat_id": 11, "lang": "en"},
            {"telegram_user_id": 22, "chat_id": 22, "lang": "ru"}]

    def same(_uid):
        return "u_samefingerprint"

    import beta.admin as admin_mod
    original = admin_mod.fingerprint
    admin_mod.fingerprint = same
    try:
        status, hits = classify_fingerprint(rows, "u_samefingerprint")
    finally:
        admin_mod.fingerprint = original
    assert status == "AMBIGUOUS" and len(hits) == 2
    assert classify_fingerprint([], "u_missing") == ("UNKNOWN", [])


def test_welcome_after_join_and_help_lists_feedback():
    async def body():
        pool = await fresh_pool()
        ru = _handler(pool)
        alice = 900000000201
        async with BetaStore(pool).connect() as conn:
            code = await conn.create_invite(label="welcome", max_uses=2, now=NOW)
        await ru.handle(_msg(alice, f"/start {code}", 1))
        await ru.handle(_cb(alice, "pick:ru", 2))
        joined = await ru.handle(_cb(alice, "join:ru", 3))
        assert joined[0].html == "Вы в бете."
        assert joined[1].html == WELCOME_RU
        assert PUSH_RU not in joined[1].html
        help_ru = await ru.handle(_msg(alice, "/help", 4))
        assert "/feedback" in help_ru[-1].html

        en = _handler(pool, switches=ON_PUSH)
        bob = 900000000202
        await en.handle(_msg(bob, f"/start {code}", 5))
        await en.handle(_cb(bob, "pick:en", 6))
        joined_en = await en.handle(_cb(bob, "join:en", 7))
        assert joined_en[1].html == WELCOME_EN + "\n" + PUSH_EN
        await pool.close()
    run(body())


def test_feedback_store_forward_limits_purge_and_delete():
    async def body():
        from runtime.beta_bot import deliver_outgoing
        pool = await fresh_pool()
        h = _handler(pool)
        uid = 900000000301
        async with BetaStore(pool).connect() as conn:
            code = await conn.create_invite(label="fb", max_uses=1, now=NOW)
        await h.handle(_msg(uid, f"/start {code}", 1))
        await h.handle(_cb(uid, "pick:en", 2))
        await h.handle(_cb(uid, "join:en", 3))
        empty = await h.handle(_msg(uid, "/feedback   ", 4))
        assert "Write your feedback" in empty[0].html
        assert (await _rows(pool, "SELECT count(*) AS n FROM beta_feedback_messages"))[0]["n"] == 0

        text = "hello <b>team</b> & friends"
        sent = await h.handle(_msg(uid, f"/feedback {text}", 5))
        assert sent[0].html == "Thanks! Your feedback was sent to the team."
        fp = fingerprint(uid)
        forward = sent[1].html
        assert f"Feedback · {fp} · en · 2026-06-15 15:00 Kyiv" in forward
        assert "hello &lt;b&gt;team&lt;/b&gt; &amp; friends" in forward
        assert f"Reply: /admin_reply {fp} &lt;text&gt;" in forward
        assert str(uid) not in forward
        stored = await _rows(pool, "SELECT text, lang FROM beta_feedback_messages")
        assert stored == [{"text": text, "lang": "en"}]
        activity = await _rows(pool, "SELECT action, detail FROM beta_user_activity WHERE action='cmd_feedback'")
        assert activity == [{"action": "cmd_feedback", "detail": None}]

        too_long = await h.handle(_msg(uid, "/feedback " + ("x" * 1001), 6))
        assert "1000" in too_long[0].html and "nothing was stored" in too_long[0].html
        assert (await _rows(pool, "SELECT count(*) AS n FROM beta_feedback_messages"))[0]["n"] == 1
        ok = await h.handle(_msg(uid, "/feedback " + ("y" * 1000), 7))
        assert ok[0].html.startswith("Thanks!")

        for i in range(3):
            await h.handle(_msg(uid, f"/feedback more {i}", 8 + i))
        blocked = await h.handle(_msg(uid, "/feedback sixth", 11))
        assert "Already 5" in blocked[0].html
        assert (await _rows(pool, "SELECT count(*) AS n FROM beta_feedback_messages"))[0]["n"] == 5

        class Boom:
            def __init__(self):
                self.sent = []

            async def send(self, *, chat_id, html, buttons=None):
                if chat_id == OWNER:
                    raise RuntimeError("down")
                self.sent.append((chat_id, html))

            async def answer(self, *_a, **_k):
                return None

            async def edit(self, **_k):
                return None

        later = datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc)
        h.clock = Clock(later)
        again = await h.handle(_msg(uid, "/feedback next day <tag>", 12))
        sender = Boom()
        await deliver_outgoing(sender, again)
        assert sender.sent == [(uid, "Thanks! Your feedback was sent to the team.")]
        assert (await _rows(pool, "SELECT count(*) AS n FROM beta_feedback_messages"))[0]["n"] == 6

        async with pool.acquire() as c:
            await c.execute(
                "UPDATE beta_feedback_messages SET created_at=$1 WHERE text LIKE 'more %'",
                NOW - timedelta(days=121))
        from beta.delivery import run_notify_once
        report = await run_notify_once(BetaStore(pool), CFG, ON, sender=None, clock=Clock(later))
        assert report["purged_feedback_messages"] == 3
        left = await _rows(pool, "SELECT count(*) AS n FROM beta_feedback_messages")
        assert left[0]["n"] == 3

        await h.handle(_msg(uid, "/delete_me", 13))
        assert (await _rows(pool, "SELECT count(*) AS n FROM beta_feedback_messages"))[0]["n"] == 0
        await pool.close()
    run(body())


def test_admin_reply_owner_only_wording_and_audit():
    async def body():
        pool = await fresh_pool()
        h = _handler(pool)
        uid = 900000000401
        async with BetaStore(pool).connect() as conn:
            code = await conn.create_invite(label="reply", max_uses=1, now=NOW)
        await h.handle(_msg(uid, f"/start {code}", 1))
        await h.handle(_cb(uid, "pick:ru", 2))
        await h.handle(_cb(uid, "join:ru", 3))
        fp = fingerprint(uid)
        stranger = await h.handle(_msg(uid, f"/admin_reply {fp} hello", 4))
        assert "Неизвестная команда" in stranger[0].html
        refused = await _rows(pool, "SELECT authorized, action FROM beta_admin_audit")
        assert refused == [{"authorized": False, "action": "admin_reply"}]

        missing = await h.handle(_msg(OWNER, "/admin_reply u_doesnotexist hello", 5))
        assert "unknown fingerprint" in missing[0].html
        assert len(missing) == 1

        bad = await h.handle(_msg(OWNER, f"/admin_reply {fp} please buy this", 6))
        assert "forbidden wording" in bad[0].html and r"\bbuy\b" in bad[0].html
        assert len(bad) == 1

        good = await h.handle(_msg(OWNER, f"/admin_reply {fp} спасибо за отзыв", 7))
        assert f"delivered to {fp}" in good[0].html
        assert "спасибо за отзыв" not in good[0].html
        assert good[1].html == "Ответ команды Signalbot:\nспасибо за отзыв"
        audit = await _rows(
            pool, "SELECT result, target_fingerprint, detail::text AS detail FROM beta_admin_audit "
                  "WHERE action='admin_reply' AND authorized ORDER BY audit_id")
        assert audit[-1]["result"] == "OK"
        assert audit[-1]["target_fingerprint"] == fp
        assert "спасибо" not in audit[-1]["detail"]
        assert str(uid) not in audit[-1]["detail"]
        await pool.close()
    run(body())


def test_existing_user_on_privacy_v2_sees_the_feedback_notice_once():
    async def body():
        pool = await fresh_pool()
        h = _handler(pool)
        uid = 900000000501
        async with pool.acquire() as c:
            await c.execute(
                """INSERT INTO beta_users (telegram_user_id, chat_id, status, privacy_accepted_at,
                       joined_at, lang, privacy_notice_version)
                   VALUES ($1,$1,'ACTIVE',$2,$2,'ru',2)""", uid, NOW)
        first = await h.handle(_msg(uid, "/help", 1))
        assert "Тексты отзывов" in first[0].html and "120" in first[0].html
        assert "/feedback" in first[1].html
        second = await h.handle(_msg(uid, "/help", 2))
        assert len(second) == 1 and "Тексты отзывов" not in second[0].html
        version = await _rows(pool, "SELECT privacy_notice_version FROM beta_users")
        assert version == [{"privacy_notice_version": 3}]
        await pool.close()
    run(body())
