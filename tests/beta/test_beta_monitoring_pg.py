"""A3 monitoring on real PostgreSQL ($BETA_TEST_DSN), with the external review of A3/A5: the failure spike
counts every outbox kind, expired and flood-control rows, never a participant who blocked the bot; the
ready outage notice goes paced to each active participant and the owner learns how many got it; a refused
feed job, a crashed or partly failed history sync and a swallowed notifier step reach the owner's alerts;
the owner's alert waits while the run's pacer is closed. Synthetic data only."""
from datetime import date, datetime, timedelta, timezone

import pytest

from beta_fakes import CFG, ON_PUSH, TEST_DSN, Clock, fresh_pool, run
from storage.beta_v0_store import BetaStore
from test_beta_v2_pg import A, B, C, Sender, _handler, _join, _rows, plain

pytestmark = pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)")

UTC = timezone.utc
NOW = datetime(2026, 10, 6, 9, 0, tzinfo=UTC)
OWNER = 900000000999


def _owner(text, k, uid=OWNER):
    return {"update_id": k, "message": {"from": {"id": uid}, "chat": {"id": uid, "type": "private"}, "text": text}}


async def _brief_row(conn, view_pk, user_pk, day, state, **cols):
    names = ", ".join(cols)
    vals = ", ".join(f"${i + 6}" for i in range(len(cols)))
    await conn.conn.execute(
        f"""INSERT INTO beta_notification_deliveries (kind, brief_date, view_pk, user_pk, state, decision_ts
                {', ' + names if cols else ''})
            VALUES ('brief', $1, $2, $3, $4, $5{', ' + vals if cols else ''})""",
        day, view_pk, user_pk, state, NOW - timedelta(minutes=5), *cols.values())


def test_the_spike_counts_real_problems_and_the_outage_notice_reports_its_deliveries():
    from beta.admin import collect_health
    from runtime.beta_bot import deliver_outgoing, report_mass_send

    async def body():
        pool = await fresh_pool()
        store = BetaStore(pool)
        async with store.connect() as conn:
            for uid in (A, B, C):
                await conn.allowlist_add(uid)
        h = _handler(pool, OWNER, Clock(NOW))
        await _join(h, A, 10, "ru")
        await _join(h, B, 20, "en")
        msg_c = await _join(h, C, 30, "ru")
        await h.handle(msg_c("/stop", 40))                           # STOPPED: no notice

        async with store.connect() as conn:
            view_pk = await conn.insert_btc_view(requested_at=NOW, as_of_bucket=None, context_state_digest=None,
                                                 episodization_version=None, episodization_digest=None,
                                                 payload={}, payload_digest="a" * 64, rendered_sha256="b" * 64,
                                                 rendered_html="x", kind="brief")
            users = [u["user_pk"] for u in await _rows(pool, "SELECT user_pk FROM beta_users ORDER BY user_pk")]
            # three participants who blocked the bot: their choice, never a spike (A3 review 2)
            for u in users:
                await _brief_row(conn, view_pk, u, date(2026, 10, 5), "FAILED", sending_at=NOW,
                                 error_summary="Forbidden: bot was blocked by the user")
            health = await collect_health(conn, CFG, ON_PUSH, NOW)
            assert "DELIVERY_FAILURE_SPIKE" not in {a["key"] for a in health["alerts"]}
            assert health["delivery_problems"]["blocked"] == 3
            # an ambiguous send, one that expired undelivered, one waiting after flood control (A5 review 2)
            await _brief_row(conn, view_pk, users[0], date(2026, 10, 6), "DELIVERY_UNKNOWN", sending_at=NOW)
            await _brief_row(conn, view_pk, users[1], date(2026, 10, 6), "EXPIRED_UNDELIVERED",
                             suppression_reason="DELIVERY_TOO_OLD", finished_at=NOW)
            await _brief_row(conn, view_pk, users[2], date(2026, 10, 6), "PENDING",
                             next_attempt_at=NOW + timedelta(seconds=30), error_summary="RetryAfter 30s")
            health = await collect_health(conn, CFG, ON_PUSH, NOW)
        spike = next(a for a in health["alerts"] if a["key"] == "DELIVERY_FAILURE_SPIKE")
        assert spike["detail"] == {"count": 3, "by_kind": {"brief": 3},
                                   "by_reason": {"unknown": 1, "expired": 1, "throttled": 1}, "blocked": 3}

        # the outage notice: paced, each ACTIVE participant in their language, then the real count (A3 review 4)
        out = await h.handle(_owner("/admin_outage start", 50))
        assert plain(out[0].html) == "outage start notice: sending to 2 active participants"
        notices = {o.chat_id: plain(o.html) for o in out[1:] if o.kind == "message"}
        assert notices[A].startswith("⚠️ У нас сбой") and notices[B].startswith("⚠️ We have an outage")
        assert C not in notices

        class _Flaky(Sender):
            async def send(self, *, chat_id, html, buttons=None):
                if chat_id == B:
                    from beta.delivery import DeliveryRejected
                    raise DeliveryRejected("Forbidden: bot was blocked by the user")
                return await super().send(chat_id=chat_id, html=html, buttons=buttons)
        waits = []

        async def sleep(s):
            waits.append(s)
        flaky = _Flaky()
        counts = await deliver_outgoing(flaky, out, sleep=sleep)
        assert counts == {("admin_outage", "outage start notice"): {"recipients": 2, "delivered": 1, "failed": 1,
                                                                     "unknown": 0}}
        assert waits == [0.05]                                         # one pause between the two notices
        owner = Sender()
        await report_mass_send(store, owner, OWNER, counts, now=NOW)
        assert plain(owner.sent[0][1]) == "outage start notice: delivered to 1 of 2, failed 1"
        audit = await _rows(pool, """SELECT result, detail FROM beta_admin_audit WHERE action = 'admin_outage'
                                     ORDER BY audit_id""")
        assert [a["result"] for a in audit] == ["OK", "DELIVERED"]
        assert '"delivered": 1' in audit[1]["detail"] and '"failed": 1' in audit[1]["detail"]
        # flood control during a mass send is waited out once
        from beta.delivery import DeliveryThrottled

        class _Busy(Sender):
            first = True

            async def send(self, *, chat_id, html, buttons=None):
                if self.first and chat_id == A:
                    self.first = False
                    raise DeliveryThrottled(2)
                return await super().send(chat_id=chat_id, html=html, buttons=buttons)
        waits.clear()
        counts = await deliver_outgoing(_Busy(), await h.handle(_owner("/admin_outage end", 51)), sleep=sleep)
        assert counts[("admin_outage", "outage end notice")] == {"recipients": 2, "delivered": 2, "failed": 0,
                                                                  "unknown": 0}
        assert 2.0 in waits
        usage = plain((await h.handle(_owner("/admin_outage", 52)))[0].html)
        assert usage.startswith("usage: /admin_outage start|end")
        assert len(await h.handle(_owner("/admin_outage start", 53, uid=A))) == 1          # refused for others
        # the broadcast takes the same paced, counted path (cleanup 12)
        out = await h.handle(_owner("/admin_broadcast Плановые работы в 12:00", 54))
        assert {o.mass for o in out[1:]} == {("admin_broadcast", "broadcast")}
        await pool.close()
    run(body())


def test_refused_crashed_and_swallowed_jobs_reach_the_owner(monkeypatch):
    from beta import history_data, market_alerts
    from beta.admin import collect_health
    from beta.delivery import SendPacer, run_notify_once
    from beta.research_feeds import run_feeds_job

    async def body():
        pool = await fresh_pool()
        store = BetaStore(pool)
        # a feed job refused by its readiness check leaves a failed health row (A3 review 7)
        rep = await run_feeds_job(store, now=NOW, expected_role="signalbot_somebody_else")
        assert rep["status"] == "WRONG_DB_ROLE"
        async with store.connect() as conn:
            row = (await conn.fetch_health(["research_feeds"]))["research_feeds"]
            assert (row["last_error_type"], row["last_success_at"], row["first_run_at"]) == ("WRONG_DB_ROLE", None, NOW)
            assert "FEEDS_FAILING" not in {a["key"] for a in (await collect_health(conn, CFG, ON_PUSH, NOW))["alerts"]}
            late = await collect_health(conn, CFG, ON_PUSH, NOW + timedelta(minutes=31))
        assert {"key": "FEEDS_FAILING", "detail": {"error": "WRONG_DB_ROLE"}} in late["alerts"]

        # a history sync that fails object by object names the error type (A3 review 11) ...
        async def bad_fetch(url):
            raise ValueError("bad archive")
        await history_data.sync_history(store, now=NOW, fetch=bad_fetch, max_objects=1, klines_start=date(2026, 8, 1))
        async with store.connect() as conn:
            assert (await conn.fetch_health(["history_sync"]))["history_sync"]["last_error_type"] == "ValueError"
        # ... and one that crashes before its health row still leaves one (A3 review 7)
        def boom(*a, **k):
            raise RuntimeError("plan")
        monkeypatch.setattr(history_data, "plan_objects", boom)
        with pytest.raises(RuntimeError):
            await history_data.sync_history(store, now=NOW, fetch=bad_fetch)
        async with store.connect() as conn:
            assert (await conn.fetch_health(["history_sync"]))["history_sync"]["last_error_type"] == "RuntimeError"

        # market alerts failing while the outbox carries on reach the owner (A3 review 3); the owner's alert
        # waits while the run's pacer is closed (A5 review 4)
        async def broken(*a, **k):
            raise KeyError("payload")
        monkeypatch.setattr(market_alerts, "run_market_alerts", broken)
        closed = SendPacer()
        closed.closed = "BUDGET"
        owner = Sender()
        r = await run_notify_once(store, CFG, ON_PUSH, sender=owner, clock=Clock(NOW), owner_user_id=OWNER,
                                  pacer=closed)
        assert r["market_error"] == "KeyError" and r["owner_alert_error"] == "DEFERRED" and owner.sent == []
        r = await run_notify_once(store, CFG, ON_PUSH, sender=owner, clock=Clock(NOW + timedelta(minutes=1)),
                                  owner_user_id=OWNER)
        assert "NOTIFIER_STEP_FAILED_MARKET" in r["owner_alerts"]
        assert any("NOTIFIER_STEP_FAILED_MARKET" in plain(html) for chat, html, _ in owner.sent if chat == OWNER)
        await pool.close()
    run(body())


def test_an_ambiguous_mass_send_is_unknown_and_an_empty_audience_is_still_reported():
    """Review of #345: a notice whose send is ambiguous (Telegram may have delivered it) is counted apart
    as unknown, never as failed; with no ACTIVE participant the owner still gets "0 of 0" and the audit
    its DELIVERED row."""
    from beta.delivery import DeliveryAmbiguous
    from runtime.beta_bot import deliver_outgoing, report_mass_send

    async def sleep(s):
        return None

    async def body():
        # nobody ACTIVE: the count is opened anyway
        pool = await fresh_pool()
        store = BetaStore(pool)
        h = _handler(pool, OWNER, Clock(NOW))
        out = await h.handle(_owner("/admin_outage start", 50))
        assert plain(out[0].html) == "outage start notice: sending to 0 active participants"
        counts = await deliver_outgoing(Sender(), out, sleep=sleep)
        assert counts == {("admin_outage", "outage start notice"): {"recipients": 0, "delivered": 0, "failed": 0,
                                                                     "unknown": 0}}
        owner = Sender()
        await report_mass_send(store, owner, OWNER, counts, now=NOW)
        assert [plain(html) for _, html, _ in owner.sent] == ["outage start notice: delivered to 0 of 0"]
        audit = await _rows(pool, "SELECT result FROM beta_admin_audit WHERE action = 'admin_outage' ORDER BY audit_id")
        assert [a["result"] for a in audit] == ["OK", "DELIVERED"]
        await pool.close()

        # an ambiguous send: unknown, reported apart from failed
        pool = await fresh_pool()
        store = BetaStore(pool)
        async with store.connect() as conn:
            for uid in (A, B):
                await conn.allowlist_add(uid)
        h = _handler(pool, OWNER, Clock(NOW))
        await _join(h, A, 10, "ru")
        await _join(h, B, 20, "en")

        class _Timeout(Sender):
            async def send(self, *, chat_id, html, buttons=None):
                if chat_id == B:
                    raise DeliveryAmbiguous("timeout")
                return await super().send(chat_id=chat_id, html=html, buttons=buttons)
        counts = await deliver_outgoing(_Timeout(), await h.handle(_owner("/admin_outage start", 51)), sleep=sleep)
        assert counts == {("admin_outage", "outage start notice"): {"recipients": 2, "delivered": 1, "failed": 0,
                                                                     "unknown": 1}}
        owner = Sender()
        await report_mass_send(store, owner, OWNER, counts, now=NOW)
        assert plain(owner.sent[0][1]) == "outage start notice: delivered to 1 of 2, unknown 1 (may have arrived)"
        audit = await _rows(pool, """SELECT detail FROM beta_admin_audit WHERE action = 'admin_outage'
                                     AND result = 'DELIVERED'""")
        assert '"unknown": 1' in audit[0]["detail"] and '"failed": 0' in audit[0]["detail"]
        await pool.close()
    run(body())


@pytest.mark.parametrize("failure", ["ambiguous", "refused"])
def test_an_ambiguous_or_refused_owner_alert_is_not_repeated_within_its_window(failure):
    """Review of #345: the owner's alert follows the outbox's rules. An ambiguous send (Telegram may have
    delivered it) and a refused one are not repeated by the next run; the window then runs as usual."""
    from beta.delivery import DeliveryAmbiguous, DeliveryRejected, run_notify_once

    class _OwnerFails(Sender):
        calls = 0

        async def send(self, *, chat_id, html, buttons=None):
            if chat_id == OWNER:
                self.calls += 1
                if self.calls == 1:
                    raise (DeliveryAmbiguous("timeout") if failure == "ambiguous"
                           else DeliveryRejected("Forbidden: bot was blocked by the user"))
            return await super().send(chat_id=chat_id, html=html, buttons=buttons)

    async def body():
        pool = await fresh_pool()
        store = BetaStore(pool)
        owner = _OwnerFails()
        r = await run_notify_once(store, CFG, ON_PUSH, sender=owner, clock=Clock(NOW), owner_user_id=OWNER)
        res = "UNKNOWN" if failure == "ambiguous" else "REJECTED"
        assert r["owner_alert_error"] == res and owner.calls == 1
        assert bool(r["owner_alerts"]) is (failure == "ambiguous")      # an ambiguous alert may have arrived
        async with store.connect() as conn:
            rows = {k: v for k, v in (await conn.fetch_health()).items() if k.startswith("owner_alert:")}
        assert rows and {v["last_error_type"] for v in rows.values()} == {res}
        r = await run_notify_once(store, CFG, ON_PUSH, sender=owner, clock=Clock(NOW + timedelta(minutes=1)),
                                  owner_user_id=OWNER)
        assert owner.calls == 1 and r["owner_alerts"] == [] and "owner_alert_error" not in r
        repeat = CFG["health"]["owner_alert_repeat_s"]
        r = await run_notify_once(store, CFG, ON_PUSH, sender=owner,
                                  clock=Clock(NOW + timedelta(seconds=repeat + 60)), owner_user_id=OWNER)
        assert owner.calls == 2 and r["owner_alerts"]           # the window over: sent again, as for a sent alert
        await pool.close()
    run(body())
