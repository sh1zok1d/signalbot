"""Invite-candidate journey on real PostgreSQL ($BETA_TEST_DSN; skipped when unset).

One participant goes through the whole product the way an invited user would: invite link,
language, privacy, join, a push, the morning briefing, a level alert, every command (with
wrong arguments), stale data, a blocked bot, /stop and /delete_me. Real detector, nightly
history build, notifier and bot handler; fakes only for Telegram, the exchange raw bundles
and the unusual-hour gate (answered "qualified" so a push exists on a synthetic tape).

It pins two things the 30-day user test depends on:
- every participant action leaves the activity row the measurement contract reads;
- nothing internal reaches a participant (BETA_COPY_CONTRACT_V1 §5 rule 5)."""
import json
import random
import re
from datetime import timedelta
from pathlib import Path

import pytest

from beta_fakes import (CFG, EXS, ON_PUSH, S2, TEST_DSN, Clock, ScenarioReader, deps, down_move,
                        fresh_pool, history_buckets, history_metrics, run, seed_history, seed_live_klines)
from beta import detector as det
from beta.delivery import DeliveryRejected, run_notify_once
from beta.state_tape import materialize_bucket
from storage.beta_v0_store import BetaStore
from test_beta_v2_pg import DAY, _seed

pytestmark = pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)")

OWNER, A, B = 900000000001, 900000000111, 900000000222
BUCKET = timedelta(minutes=5)
E0 = DAY + timedelta(hours=5)                                    # 08:00 Kyiv
EVAL = [E0 + i * BUCKET for i in range(12)]
NOW = DAY + timedelta(hours=6, seconds=40)
JCFG = CFG.with_overrides(briefing={"enabled": True, "time_kyiv": "08:00", "max_delay_min": 120},
                          max_new_pushes_per_utc_day=3,
                          push_policy={"quiet_hours_kyiv": ["00:00", "00:00"], "global_cooldown_min": 1})
# what a participant must never see (ids, versions, digests, raw states and codes, placeholders)
INTERNAL = re.compile(r"EV-[0-9A-F]{6,}|\b[0-9a-f]{32,}\b|BETA_[A-Z0-9_]+|\b(?:SENT|SUPPRESSED|PENDING|"
                      r"DELIVERY_UNKNOWN|EXPIRED|NOT_EVALUABLE|TRIGGERED|ARMED|QUALIFIES|CONDITION_[A-Z]+|"
                      r"MAX_DURATION|PUSH_DISABLED|HOUR_NOT_UNUSUAL|PERCENTILE_[A-Z_]+|mature)\b|"
                      r"\bNone\b|\bnan\b|\{[a-z_]+\}|Traceback|digest|бакет|перцентил|эпизод|детектор",
                      re.IGNORECASE)


def plain(html):
    return re.sub(r"<[^>]+>", "", html or "").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")


class Sender:
    def __init__(self, seen, *, fail_for=(), block_for=()):
        self.seen, self.sent, self.fail_for, self.block_for = seen, [], set(fail_for), set(block_for)

    async def send(self, *, chat_id, html, buttons=None):
        if chat_id in self.block_for:
            raise DeliveryRejected("Forbidden: bot was blocked by the user")
        if chat_id in self.fail_for:
            raise TimeoutError("network")
        self.sent.append((chat_id, html, buttons))
        self.seen.append(("notifier", plain(html), buttons))
        return len(self.sent)


@pytest.fixture(autouse=True)
def _qualified_hour(monkeypatch):
    async def qualified(conn, cfg, hour_ctx, snapshot):
        return {"version": "TEST_GATE", "qualified": True, "status": "QUALIFIED"}
    monkeypatch.setattr(det, "_hour_gate", qualified)


async def _rows(pool, sql, *args):
    async with pool.acquire() as c:
        return [dict(r) for r in await c.fetch(sql, *args)]


def test_invited_participant_journey_telemetry_and_clean_surface():
    from beta.decision import reset_cache
    from beta.history_stats import run_history_build
    from runtime.beta_bot import BetaBotHandler

    async def body():
        reset_cache()
        pool = await fresh_pool()
        store = BetaStore(pool)
        await _seed(pool)
        assert (await run_history_build(store, JCFG, now=DAY + timedelta(hours=2)))["status"] == "OK"
        calc = (await materialize_bucket(ScenarioReader(), S2, JCFG, bucket_ts=E0, code_version="feature-code-test",
                                         liquidation_feed_available_by_exchange={e: True for e in EXS})
                ).consensus_feature.calculation_version
        rng = random.Random(7)
        await seed_history(pool, calculation_version=calc, buckets=history_buckets(E0, 12),
                           metrics_fn=lambda b: history_metrics(rng))
        await seed_live_klines(pool, EVAL, exchanges=("bybit", "okx"))

        seen = []                                         # (who, text, buttons) shown to participants
        h = BetaBotHandler(store, JCFG, switches=lambda: ON_PUSH, owner_user_id=OWNER,
                           clock=Clock(E0 - timedelta(minutes=30)), bot_username="signalbot_beta_test")
        n = [0]

        async def say(uid, text):
            n[0] += 1
            out = await h.handle({"update_id": n[0], "message": {"from": {"id": uid},
                                  "chat": {"id": uid, "type": "private"}, "text": text}})
            if uid != OWNER:
                seen.extend((uid, plain(o.html), o.buttons) for o in out if o.chat_id == uid)
            return out

        async def click(uid, data):
            n[0] += 1
            out = await h.handle({"update_id": n[0], "callback_query": {
                "id": f"c{n[0]}", "from": {"id": uid}, "message": {"chat": {"id": uid}, "message_id": 1},
                "data": data}})
            seen.extend((uid, plain(o.html), o.buttons) for o in out if o.chat_id == uid)
            return out

        # ---- invite link -> language -> privacy -> join ------------------------------------
        out = await say(OWNER, "/admin_invite_new 2 7 first-wave")
        code = re.search(r"start=([A-Za-z0-9_-]{12})", plain(out[0].html)).group(1)
        await say(A, f"/start {code}")
        await click(A, "pick:ru")
        joined = await click(A, "join:ru")
        welcome = plain(joined[-1].html)
        assert "\n\nКак вы торгуете?" in welcome and joined[-1].buttons[-1] == [("Пропустить", "s:skip")]   # E5
        # /start explains what it is, what it does not promise, and how to leave
        assert "не говорит, покупать или продавать" in welcome and "/help" in welcome
        privacy = next(t for w, t, _ in seen if w == A and "конфиденциальность" in t)
        assert "/delete_me" in privacy and "/stop" in privacy and "не инвестиционный совет" in privacy
        # before Join: one concise line on what the bot is (owner decision 2026-10-03)
        assert ("Signalbot наблюдает за BTC и показывает необычные состояния рынка и контекст.\n"
                "Торговых рекомендаций бот не даёт.") in privacy
        await say(OWNER, f"/admin_add {B}")
        await say(B, "/start")
        await click(B, "pick:en")
        await click(B, "join:en")

        # ---- the detector triggers; the push goes out at once; A reacts within minutes -------
        scenario = lambda b: down_move(b) if b >= E0 + 8 * BUCKET else {}      # noqa: E731
        pushed_at = None
        for b in EVAL:
            at = b + BUCKET + timedelta(seconds=25)
            r = await det.run_detector_once(deps(pool, ScenarioReader(scenario), Clock(at)), JCFG, ON_PUSH)
            if any(d[1] == "PUSH" for p in r.get("processed", []) for d in p["push_decisions"]):
                s = Sender(seen)
                rep = await run_notify_once(store, JCFG, ON_PUSH, sender=s, clock=Clock(at + timedelta(seconds=15)))
                assert rep["sent"] == 2 and rep["briefs"]["sent"] == 2
                pushed_at = at + timedelta(seconds=15)
                h.clock = Clock(pushed_at + timedelta(minutes=3))
                brief_buttons = next(btn for c, html, btn in s.sent if c == A and btn and "L:levels" in str(btn))
                for row in brief_buttons:
                    for _, d in row:
                        await click(A, d)
                # «📊 BTC сейчас» above Useful / Noise on the push: one tap to the current /btc
                push_buttons = next(btn for c, html, btn in s.sent if c == A and "u:EV-" in str(btn))
                assert push_buttons[0] == [("📊 BTC сейчас", "b:now")]
                assert [lbl for lbl, _ in push_buttons[1]] == ["Полезно", "Шум"]
                now_view = await click(A, "b:now")
                assert plain(now_view[-1].html).startswith("BTC ") and now_view[-1].buttons
        assert pushed_at is not None

        # ---- every command, with wrong arguments ------------------------------------------
        h.clock = Clock(NOW)
        out = await say(A, "/btc")
        assert all(d != "r:latest" for row in (out[-1].buttons or ()) for _, d in row)
        assert "не инвестиционный совет" not in plain(out[-1].html)          # disclaimer: /start, /terms only
        assert "Прошлое не гарантирует будущего" in plain((await say(A, "/terms"))[-1].html)
        for text in ("/catchup", "/catchup 3", "/catchup 99", "/levels", "/risk", "/risk 0.5", "/risk abc",
                     "/events", "/accuracy", "/research", "/alert", "/alert del 1", "/alert 1000000",
                     "/alert abc", "/push", "/push off", "/push on", "/push levels off", "/push levels on",
                     "/brief", "/brief off", "/brief on", "/history", "/terms", "/help", "/feedback",
                     "/feedback что значит коридор?", "/lang", "/foo"):
            out = await say(A, text)
            assert out and all(plain(o.html).strip() or o.kind == "answer" for o in out), text
            if text == "/alert del 1":
                assert plain(out[-1].html).startswith("Уровней нет")             # not the usage line
            if text == "/alert 1000000":
                assert "дальше 30%" in plain(out[-1].html)
            if text == "/history":
                hist = plain(out[-1].html)
                assert hist.startswith("Необычные события BTC") and "сообщение отправлено" in hist
        out = await click(A, "r:latest")                  # an older message's button: owner-only
        assert [o.kind for o in out] == ["answer"]

        # ---- /push off keeps the categories and says so -----------------------------------
        await say(A, "/push levels off")
        off = plain((await say(A, "/push off"))[-1].html)
        assert off.splitlines()[1] == ("Сейчас не приходит ничего из списка ниже. Настройки категорий "
                                       "сохранены и снова заработают после /push on.")
        assert "месячных максимумов и минимумов): выкл" in off and "необычный час: вкл" in off
        on = plain((await say(A, "/push on"))[-1].html)
        assert "Сейчас не приходит" not in on and "месячных максимумов и минимумов): выкл" in on
        await say(A, "/push levels on")

        # ---- U5 fake door: only in /help, one activity row per tap, nothing behind it -------
        help_out = await say(A, "/help")
        assert ("Другие монеты", "x:assets") in [b for row in help_out[-1].buttons for b in row]
        for _ in range(2):
            door = await click(A, "x:assets")
            assert plain(door[-1].html) == "Пока доступен только BTC. Интерес к другим монетам записан."
            assert door[-1].buttons is None

        # ---- a level alert through the outbox ----------------------------------------------
        s = Sender(seen)
        rep = await run_notify_once(store, JCFG, ON_PUSH, sender=s, clock=Clock(NOW))
        assert rep["market"]["sent"] >= 1

        # ---- stale data: nobody advanced the detector or the 1m tail for 2h ------------------
        h.clock = Clock(NOW + timedelta(hours=2))
        out = await say(A, "/catchup")
        assert plain(out[-1].html).splitlines()[0] == "BTC за 8 ч"              # never «8 ч · 8 ч»
        await say(A, "/btc")
        await say(A, "/levels")

        # ---- next morning: A blocked the bot, B's network failed ----------------------------
        s = Sender(seen, block_for={A}, fail_for={B})
        rep = await run_notify_once(store, JCFG, ON_PUSH, sender=s, clock=Clock(NOW + timedelta(days=1)))
        assert rep["briefs"]["failed"] == 1 and rep["briefs"]["unknown"] == 1
        failed = await _rows(pool, "SELECT u.telegram_user_id AS uid, d.state, d.error_summary FROM "
                                   "beta_notification_deliveries d JOIN beta_users u USING (user_pk) "
                                   "WHERE d.kind='brief' AND d.state <> 'SENT' ORDER BY 1")
        assert failed == [{"uid": A, "state": "FAILED", "error_summary": "Forbidden: bot was blocked by the user"},
                          {"uid": B, "state": "DELIVERY_UNKNOWN", "error_summary": "TimeoutError"}]

        # ---- telemetry: every step is answerable -------------------------------------------
        act = await _rows(pool, "SELECT a.action, a.detail, a.at FROM beta_user_activity a JOIN beta_users u "
                                "USING (user_pk) WHERE u.telegram_user_id=$1 ORDER BY a.activity_pk", A)
        actions = {(r["action"], r["detail"]) for r in act}
        for expected in ("cmd_start", "push_delivered", "brief_delivered", "alert_delivered", "btn_levels",
                         "btn_risk", "cmd_btc", "cmd_catchup", "cmd_levels", "cmd_risk", "cmd_events",
                         "cmd_accuracy", "cmd_research", "cmd_alert", "cmd_history", "cmd_terms", "cmd_help",
                         "cmd_feedback", "cmd_lang", "tab_1h", "tab_24h", "btn_btc_now", "btn_other_assets"):
            assert expected in {a for a, _ in actions}, expected
        assert sum(1 for r in act if r["action"] == "btn_other_assets") == 2    # one row per tap
        # market alerts carry their kind, so personal /alert deliveries stay a separate class
        assert {r["detail"] for r in act if r["action"] == "alert_delivered"} <= {"level", "event", "move", "price"}
        assert all(r["detail"] for r in act if r["action"] == "alert_delivered")
        for detail in (("cmd_push", "off"), ("cmd_push", "on"), ("cmd_push", "levels:off"),
                       ("cmd_brief", "off"), ("cmd_brief", "on")):
            assert detail in actions, detail
        # a reaction after a push is derivable: a button within 10 minutes of push_delivered
        push = next(r["at"] for r in act if r["action"] == "push_delivered")
        assert any(r["action"].startswith(("btn_", "tab_")) and timedelta(0) <= r["at"] - push <= timedelta(minutes=10)
                   for r in act)

        # ---- the draft measurement contract's queries run on this schema and see the journey ---
        doc = (Path(__file__).resolve().parents[2] / "docs" / "BETA_MEASUREMENT_CONTRACT_V1.md").read_text("utf-8")
        sql = doc.split("```sql", 1)[1].split("```", 1)[0].replace(":owner", str(OWNER))
        sql = sql.replace(":day0", "TIMESTAMPTZ '%s'" % (E0 - timedelta(hours=1)).isoformat())
        statements = [x.strip() for x in sql.split(";")
                      if x.strip() and not all(ln.strip().startswith("--") for ln in x.splitlines() if ln.strip())]
        results = []
        async with pool.acquire() as c:
            for stmt in statements:
                results.append([dict(r) for r in await c.fetch(stmt)])
        a_pk = (await _rows(pool, "SELECT user_pk FROM beta_users WHERE telegram_user_id=$1", A))[0]["user_pk"]
        enrolled, pulls, reactions, votes, mutes, blocked, _deletions = results
        assert {r["user_pk"] for r in enrolled} >= {a_pk}
        assert any(r["user_pk"] == a_pk for r in pulls)
        assert any(r["user_pk"] == a_pk and r["reacted"] for r in reactions)
        assert all(r["vote"] in ("USEFUL", "NOISE") for r in votes)          # Amendment 1: votes of every type
        assert all(r["push_type"] in ("hours", "levels", "events", "moves", "weekly") for r in mutes)
        assert [r["user_pk"] for r in blocked] == [a_pk]

        # ---- nothing internal reached a participant -----------------------------------------
        leaks = sorted({(m.group(0), text[:60]) for _, text, _ in seen for m in INTERNAL.finditer(text)})
        assert leaks == [], leaks
        callbacks = [d for _, _, btn in seen for row in (btn or ()) for _, d in row]
        assert "r:latest" not in callbacks

        # ---- /stop, /delete_me ---------------------------------------------------------------
        h.clock = Clock(NOW + timedelta(days=1, hours=1))
        await say(B, "/stop")
        out = await say(B, "/btc")
        assert "/start" in plain(out[-1].html)
        await say(A, "/delete_me")
        assert await _rows(pool, "SELECT count(*) AS n FROM beta_user_activity a JOIN beta_users u USING (user_pk) "
                                 "WHERE u.telegram_user_id=$1", A) == [{"n": 0}]
        audit = await _rows(pool, "SELECT action, detail->'cohort' AS cohort FROM beta_admin_audit "
                                  "WHERE action='user_delete_me'")
        # the participant stays countable for the frozen denominator, without identity
        assert [(a["action"], json.loads(a["cohort"])) for a in audit] == [
            ("user_delete_me", {"joined_kyiv_date": "2026-05-12", "known_contact": False})]
        assert "telegram" not in str(audit) and str(A) not in str(audit)
        async with pool.acquire() as c:                       # the contract's denominator part 2 sees it
            cohort = [dict(r) for r in await c.fetch(statements[-1])]
        assert cohort == [{"joined_kyiv_date": "2026-05-12", "known_contact": False, "n": 1}]
        await pool.close()
    run(body())
