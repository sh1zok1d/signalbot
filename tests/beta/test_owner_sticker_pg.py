"""Owner sticker replies (owner decision 2026-10-08): the owner replies with a sticker to the bot's copy of a
participant's message (feedback, idea, plain text) and the bot sends that sticker to the participant.
The copy is mapped by the message_id Telegram returned for it; every refusal names its reason to the owner;
a sticker from anyone else has no effect and no reply. Real PostgreSQL ($BETA_TEST_DSN)."""
from datetime import timedelta

import pytest

from beta.admin import fingerprint
from beta_fakes import TEST_DSN, fresh_pool, run
from storage.beta_v0_store import BetaStore
from test_beta_feedback import NOW, OWNER, _cb, _handler, _msg, _rows

pytestmark = pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)")


class Sender:
    def __init__(self):
        self.sent, self.stickers, self.next_id = [], [], 700

    async def send(self, *, chat_id, html, buttons=None):
        self.next_id += 1
        self.sent.append((chat_id, html, self.next_id))
        return self.next_id

    async def send_sticker(self, *, chat_id, sticker):
        self.stickers.append((chat_id, sticker))
        return 1


def _sticker(uid, update_id, *, reply_to=None, file_id="CAACAgIAAxk", **flags):
    m = {"from": {"id": uid}, "chat": {"id": uid, "type": "private"},
         "sticker": {"file_id": file_id, "file_unique_id": "u1", "is_animated": False, "is_video": False, **flags}}
    if file_id is None:
        del m["sticker"]["file_id"]
    if reply_to is not None:
        m["reply_to_message"] = {"message_id": reply_to, "chat": {"id": uid}}
    return {"update_id": update_id, "message": m}


async def _join(h, uid, code, base):
    await h.handle(_msg(uid, f"/start {code}", base))
    await h.handle(_cb(uid, "pick:en", base + 1))
    await h.handle(_cb(uid, "join:en", base + 2))


async def _forward(h, pool, sender, uid, text, update_id):
    """The participant writes; the bot's replies go out; returns the owner copy's message_id."""
    from runtime.beta_bot import deliver_outgoing
    out = await h.handle(_msg(uid, text, update_id))
    await deliver_outgoing(sender, out, store=BetaStore(pool))
    chat, _html, mid = sender.sent[-1]                       # the owner copy goes out after the confirmation
    assert chat == OWNER
    return mid


async def _owner_sticker(h, pool, sender, update):
    from runtime.beta_bot import deliver_outgoing, report_mass_send
    out = await h.handle(update)
    counts = await deliver_outgoing(sender, out, store=BetaStore(pool))
    await report_mass_send(BetaStore(pool), sender, OWNER, counts, now=NOW)
    return out


async def _setup():
    pool = await fresh_pool()
    async with BetaStore(pool).connect() as conn:
        code = await conn.create_invite(label="st", max_uses=5, now=NOW)
    return pool, _handler(pool), Sender(), code


def test_sticker_reply_round_trip_and_three_kinds():
    async def body():
        pool, h, sender, code = await _setup()
        uid = 900000000401
        await _join(h, uid, code, 1)
        mid = await _forward(h, pool, sender, uid, "/feedback where is ETH?", 10)
        rows = await _rows(pool, "SELECT owner_message_id, kind FROM beta_owner_forwards")
        assert rows == [{"owner_message_id": mid, "kind": "feedback"}]
        for i, flags in enumerate(({}, {"is_animated": True}, {"is_video": True})):
            await _owner_sticker(h, pool, sender, _sticker(OWNER, 20 + i, reply_to=mid, file_id=f"F{i}", **flags))
        assert sender.stickers == [(uid, "F0"), (uid, "F1"), (uid, "F2")]
        fp = fingerprint(uid)
        told = [html for chat, html, _ in sender.sent if chat == OWNER and "Sticker to" in html]
        assert told and all(f"Sticker to {fp}: delivered to 1 of 1" in x for x in told) and len(told) == 3
        audit = await _rows(pool, """SELECT result, target_fingerprint, detail->>'sticker_kind' AS k
                                     FROM beta_admin_audit WHERE action='admin_sticker' ORDER BY audit_id""")
        assert [a["k"] for a in audit if a["result"] == "OK"] == ["regular", "animated", "video"]
        assert [a["result"] for a in audit].count("DELIVERED") == 3
        assert all(a["target_fingerprint"] == fp for a in audit if a["result"] == "OK")
        assert "F0" not in str(await _rows(pool, "SELECT detail FROM beta_admin_audit"))     # no file_id kept
        await pool.close()
    run(body())


def test_each_refusal_names_its_reason_and_sends_nothing():
    async def body():
        pool, h, sender, code = await _setup()
        uid = 900000000402
        await _join(h, uid, code, 1)
        mid = await _forward(h, pool, sender, uid, "/feedback hi", 10)
        cases = [(_sticker(OWNER, 20), "reply with it to the bot's copy", "NO_REPLY"),
                 (_sticker(OWNER, 21, reply_to=mid + 999), "not a copy of a participant's message", "NOT_MAPPED"),
                 (_sticker(OWNER, 22, reply_to=mid, file_id=None), "no file_id", "NO_FILE_ID")]
        for upd, words, result in cases:
            out = await _owner_sticker(h, pool, sender, upd)
            assert len(out) == 1 and out[0].chat_id == OWNER and words in out[0].html
        assert sender.stickers == []
        audit = await _rows(pool, "SELECT result FROM beta_admin_audit WHERE action='admin_sticker' ORDER BY audit_id")
        assert [a["result"] for a in audit] == ["NO_REPLY", "NOT_MAPPED", "NO_FILE_ID"]
        # a deleted participant: the mapping cascades away, the reply is refused
        await h.handle(_msg(uid, "/delete_me", 30))
        assert (await _rows(pool, "SELECT count(*) AS n FROM beta_owner_forwards"))[0]["n"] == 0
        out = await _owner_sticker(h, pool, sender, _sticker(OWNER, 31, reply_to=mid))
        assert "participant was deleted" in out[0].html and sender.stickers == []
        await pool.close()
    run(body())


def test_a_sticker_from_anyone_else_has_no_effect_and_no_reply():
    async def body():
        pool, h, sender, code = await _setup()
        uid = 900000000403
        await _join(h, uid, code, 1)
        mid = await _forward(h, pool, sender, uid, "/feedback hi", 10)
        assert await h.handle(_sticker(uid, 20, reply_to=mid)) == []          # a participant, replying to anything
        assert await h.handle(_sticker(900000000499, 21, reply_to=mid)) == []  # a stranger
        assert (await _rows(pool, "SELECT count(*) AS n FROM beta_admin_audit WHERE action='admin_sticker'"))[0]["n"] == 0
        await pool.close()
    run(body())


def test_a_paused_participant_gets_it_and_idea_and_plain_text_copies_map():
    async def body():
        pool, h, sender, code = await _setup()
        uid = 900000000404
        await _join(h, uid, code, 1)
        idea = await _forward(h, pool, sender, uid, "/idea a funding chart", 10)
        await h.handle(_msg(uid, "/stop", 11))
        plain = await _forward(h, pool, sender, uid, "what do you keep about me?", 12)   # J4, paused
        kinds = await _rows(pool, "SELECT owner_message_id, kind FROM beta_owner_forwards ORDER BY owner_message_id")
        assert kinds == [{"owner_message_id": idea, "kind": "idea"}, {"owner_message_id": plain, "kind": "plain_text"}]
        await _owner_sticker(h, pool, sender, _sticker(OWNER, 20, reply_to=plain))
        assert sender.stickers == [(uid, "CAACAgIAAxk")]
        audit = await _rows(pool, """SELECT detail->>'status' AS status, detail->>'forward_kind' AS fk
                                     FROM beta_admin_audit WHERE action='admin_sticker' AND result='OK'""")
        assert audit == [{"status": "STOPPED", "fk": "plain_text"}]
        await pool.close()
    run(body())


def test_owner_forwards_are_purged_with_the_feedback_messages():
    async def body():
        pool, h, sender, code = await _setup()
        uid = 900000000405
        await _join(h, uid, code, 1)
        await _forward(h, pool, sender, uid, "/feedback hi", 10)
        async with BetaStore(pool).connect() as conn:
            assert await conn.purge_owner_forwards_before(NOW - timedelta(days=1)) == 0
            assert await conn.purge_owner_forwards_before(NOW + timedelta(days=400)) == 1
        await pool.close()
    run(body())


def test_preview_owner_only_never_holds_back_the_owners_own_replies():
    """The owner's UX preview (2026-10-09): with `access.preview_owner_only` on, an owner sticker reply and
    /admin_reply still reach the participant (explicit owner actions), while an automated alert to the same
    participant is SUPPRESSED / SUPPRESSED_PREVIEW."""
    async def body():
        from beta_fakes import CFG, ON, Clock
        from beta.delivery import PREVIEW_BLOCKED, SendPacer, send_one
        from runtime.beta_bot import BetaBotHandler, deliver_outgoing
        pool = await fresh_pool()
        preview = CFG.with_overrides(access={**dict(CFG["access"]), "preview_owner_only": True})
        h = BetaBotHandler(BetaStore(pool), preview, switches=lambda: ON, owner_user_id=OWNER, clock=Clock(NOW),
                           bot_username="BetaBot")
        sender = Sender()
        async with BetaStore(pool).connect() as conn:
            code = await conn.create_invite(label="pv", max_uses=5, now=NOW)
        uid = 900000000409
        await _join(h, uid, code, 1)
        mid = await _forward(h, pool, sender, uid, "/feedback hello", 10)
        await _owner_sticker(h, pool, sender, _sticker(OWNER, 20, reply_to=mid, file_id="FP"))
        assert sender.stickers == [(uid, "FP")]
        out = await h.handle(_msg(OWNER, f"/admin_reply {fingerprint(uid)} hi there", 21))
        await deliver_outgoing(sender, out, store=BetaStore(pool))
        assert any(chat == uid and "hi there" in html for chat, html, _ in sender.sent)
        async with BetaStore(pool).connect() as conn:                 # an automated alert to the same participant
            pk = await conn.insert_market_alert(kind="level", alert_key="level:pv", decision_ts=NOW, decision="PUSH",
                                                suppression_reason=None, payload={"at": NOW.isoformat()})
            user_pk = (await conn.get_user(uid))["user_pk"]
            did = await conn.conn.fetchval(
                """INSERT INTO beta_notification_deliveries (kind, alert_pk, user_pk, state, decision_ts)
                   VALUES ('alert', $1, $2, 'PENDING', $3) RETURNING delivery_id""", pk, user_pk, NOW)
            n = len(sender.sent)
            res = await send_one(conn, sender, SendPacer().set_preview(preview, OWNER), did, chat_id=uid,
                                 html="automated", clock=Clock(NOW))
        assert res[0] == PREVIEW_BLOCKED and len(sender.sent) == n
        row = (await _rows(pool, "SELECT state, suppression_reason FROM beta_notification_deliveries "
                                 "WHERE delivery_id = $1", did))[0]
        assert row == {"state": "SUPPRESSED", "suppression_reason": "SUPPRESSED_PREVIEW"}
        await pool.close()
    run(body())
