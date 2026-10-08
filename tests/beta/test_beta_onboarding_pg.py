"""Onboarding and access on PostgreSQL (PRE_BETA_SCOPE_DECISION_V1 §9 I, J; backlog J1, J4, I1, I2)."""
import re
from datetime import timedelta

import pytest

from beta_fakes import CFG, ON, TEST_DSN, Clock, fresh_pool, run
from storage.beta_v0_store import BetaStore
from test_beta_feedback import NOW, _cb, _handler, _msg

pytestmark = pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)")
OWNER = 900000000900


def plain(html):
    return re.sub(r"<[^>]+>", "", html)


async def _join(h, store, uid, k=1):
    async with store.connect() as conn:
        code = await conn.create_invite(label="j1", max_uses=5, now=NOW)
    await h.handle(_msg(uid, f"/start {code}", k))
    await h.handle(_cb(uid, "pick:ru", k + 1))
    return await h.handle(_cb(uid, "join:ru", k + 2))


def test_the_trader_type_answer_opens_the_onboarding_once():
    """J1: /start → trader type → live /btc (onboard_btc, never cmd_btc) → an example → the /check offer."""
    async def body():
        pool = await fresh_pool()
        store = BetaStore(pool)
        h = _handler(pool)
        uid = 900000000301
        await _join(h, store, uid)
        out = await h.handle(_cb(uid, "s:skip", 4))
        texts = [plain(o.html) for o in out if o.kind == "message"]
        assert texts[0] == "Хорошо. Указать позже: /type" and texts[1] == "Вот BTC прямо сейчас:"
        assert texts[2].startswith("BTC")                                    # the live /btc
        assert texts[3].startswith("Так выглядит сообщение о касании уровня. Это пример")
        assert texts[4].startswith("BTC · максимум вчера 100 000")           # the example, round numbers
        assert "случаев" not in texts[4]                                     # no statistics in an example
        assert texts[5].startswith("Проверьте свой уровень: /check")
        again = await h.handle(_cb(uid, "s:swing", 5))                       # later answers: no second onboarding
        assert [plain(o.html) for o in again if o.kind == "message"] == ["Записал: Свинг (дни–недели). Изменить: /type"]
        acts = [r["action"] for r in await pool.fetch("SELECT action FROM beta_user_activity ORDER BY activity_pk")]
        assert acts.count("onboard_btc") == 1 and "cmd_btc" not in acts and acts.count("type_set") == 1
        await pool.close()
    run(body())


def test_paused_participants_can_be_answered_and_the_u3_offer_reaches_the_churned_too():
    """J4: /admin_reply reaches a STOPPED participant. I2: /admin_offer refuses without a fixed price,
    previews, then goes to every enrolled participant, churned included; the owner gets the ledger lines."""
    async def body():
        from runtime.beta_bot import BetaBotHandler
        from beta.admin import fingerprint
        pool = await fresh_pool()
        store = BetaStore(pool)
        a, b = 900000000311, 900000000312
        h = BetaBotHandler(store, CFG, switches=lambda: ON, owner_user_id=OWNER, clock=Clock(NOW))
        await _join(h, store, a, 1)
        await _join(h, store, b, 10)
        await h.handle(_msg(b, "/stop", 20))
        out = await h.handle(_msg(OWNER, f"/admin_reply {fingerprint(b)} hello", 21))
        assert [o.chat_id for o in out if o.chat_id == b] == [b]
        refused = await h.handle(_msg(OWNER, "/admin_offer", 22))
        assert "refused" in refused[0].html
        cfg = CFG.with_overrides(access={**CFG["access"], "u3_offer": {"price": "$15 в месяц", "method": "перевод"}})
        h2 = BetaBotHandler(store, cfg, switches=lambda: ON, owner_user_id=OWNER, clock=Clock(NOW + timedelta(days=22)))
        preview = await h2.handle(_msg(OWNER, "/admin_offer", 23))
        assert "preview" in preview[0].html and len(preview) == 1
        sent = await h2.handle(_msg(OWNER, "/admin_offer send", 24))
        to = sorted(o.chat_id for o in sent if o.chat_id in (a, b))
        assert to == [a, b] and all("$15 в месяц" in o.html for o in sent if o.chat_id in (a, b))
        assert fingerprint(a) in sent[0].html and fingerprint(b) in sent[0].html      # the ledger lines, owner only
        twice = await h2.handle(_msg(OWNER, "/admin_offer send", 25))                # U3 is one offer
        assert len(twice) == 1 and "already sent" in twice[0].html
        again = await h2.handle(_msg(OWNER, "/admin_offer send again", 26))          # only on purpose
        assert sorted(o.chat_id for o in again if o.chat_id in (a, b)) == [a, b]
        await pool.close()
    run(body())


def test_a_paused_participants_plain_reply_reaches_the_team():
    """J4 for STOPPED: the U3 offer asks for «ответом сюда», so a churned participant's plain text is stored
    (plain_text, the same limits) and forwarded to the owner instead of «not joined»."""
    async def body():
        from runtime.beta_bot import BetaBotHandler
        from beta.admin import fingerprint
        pool = await fresh_pool()
        store = BetaStore(pool)
        uid = 900000000321
        h = BetaBotHandler(store, CFG, switches=lambda: ON, owner_user_id=OWNER, clock=Clock(NOW))
        await _join(h, store, uid)
        await h.handle(_msg(uid, "/stop", 5))
        out = await h.handle(_msg(uid, "how do I pay?", 6))
        mine = [plain(o.html) for o in out if o.chat_id == uid]
        assert mine == ["Передал команде — ответ придёт сюда. Команды: /help"]
        owner = [o.html for o in out if o.chat_id == OWNER]
        assert len(owner) == 1 and fingerprint(uid) in owner[0] and "how do I pay?" in owner[0]
        rows = await pool.fetch("SELECT kind, text FROM beta_feedback_messages")
        assert [dict(r) for r in rows] == [{"kind": "feedback", "text": "how do I pay?"}]
        acts = [r["action"] for r in await pool.fetch("SELECT action FROM beta_user_activity ORDER BY activity_pk")]
        assert acts[-1] == "plain_text"
        assert "/start" in (await h.handle(_msg(uid, "/btc", 7)))[0].html            # commands: as before
        await pool.close()
    run(body())


def test_tiers_are_dormant_during_the_beta():
    """I1: every feature has a tier in code; nothing is gated while access.tiers_enforced is false."""
    from beta.access import FEATURE_TIERS, feature_open
    assert all(feature_open(CFG, {"tier": "free"}, f) for f in FEATURE_TIERS)
    enforced = CFG.with_overrides(access={**CFG["access"], "tiers_enforced": True})
    assert not feature_open(enforced, {"tier": "free"}, "check_two_levels")
    assert feature_open(enforced, {"tier": "paid"}, "check_two_levels") and feature_open(enforced, None, "btc")
