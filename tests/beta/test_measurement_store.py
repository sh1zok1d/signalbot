"""PostgreSQL proof that measurement rows survive delete and purge."""
from datetime import date, datetime, timedelta, timezone

import pytest

from beta.admin import fingerprint
from beta.measurement_eval import evaluate, load_contract
from beta_fakes import TEST_DSN, fresh_pool, run
from storage.beta_v0_store import BetaStore

pytestmark = pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)")

UTC = timezone.utc
NOW = datetime(2026, 6, 1, 6, tzinfo=UTC)
UID = 900000000777


def test_enrollment_survives_delete_purge_and_does_not_store_telegram_id():
    async def body():
        pool = await fresh_pool()
        store = BetaStore(pool)
        async with store.connect() as conn:
            code = await conn.create_invite(label="ch-a", max_uses=2, now=NOW)
            assert await conn.redeem_invite(code, UID, NOW, 20, None) == "OK"
            await conn.join_user(telegram_user_id=UID, chat_id=UID, now=NOW, known_contact=False,
                                  owner_excluded=False)
            user = await conn.get_user(UID)
            again = await conn.join_user(telegram_user_id=UID, chat_id=UID, now=NOW + timedelta(days=1),
                                          known_contact=True, owner_excluded=True)
            assert again == user["user_pk"]
            enrollments = await conn.conn.fetch("SELECT * FROM beta_measurement_enrollment")
            assert len(enrollments) == 1
            row = dict(enrollments[0])
            assert row["joined_at"] == NOW
            assert row["known_contact_initial"] is False
            assert row["owner_excluded"] is False
            assert row["pseudonym"] != fingerprint(UID)
            assert UID and str(UID) not in row["pseudonym"]
            pk = row["enrollment_pk"]
            await conn.append_contact_classification(enrollment_pk=pk, known_contact=True,
                                                     recorded_at=NOW + timedelta(days=2))
            initial = await conn.conn.fetchval(
                "SELECT known_contact_initial FROM beta_measurement_enrollment WHERE enrollment_pk=$1", pk)
            assert initial is False
            await conn.record_activity(user_pk=user["user_pk"], action="cmd_catchup", lang="ru", at=NOW)
            await conn.record_brief_attempt(enrollment_pk=pk, brief_date=date(2026, 6, 2), state="SENT",
                                            recorded_at=NOW + timedelta(days=1))
            await conn.record_commercial(enrollment_pk=pk, event_type="OFFER", recorded_at=NOW,
                                         amount="25", currency="USD")
            await conn.record_interview(enrollment_pk=pk, question_id="u5", answered_at=NOW,
                                        verbatim="other markets", spontaneous=True)
            await conn.conn.execute(
                """INSERT INTO beta_episodes (public_id, symbol, event_type, state, opened_bucket, opened_at,
                       rules_version, rules_digest, code_version, calculation_version, opening_tape_digest,
                       last_bucket, last_streak)
                   VALUES ('EV-AABBCCDDEE','BTCUSDT','PRICE_OI_CONTRACTION_DOWN','EARLY',$1,$1,
                           'BETA_EVENT_RULES_V1',$2,'code','calc',$2,$1,1)""", NOW, "ab" * 32)
            episode = await conn.conn.fetchval("SELECT episode_pk FROM beta_episodes")
            await conn.upsert_feedback(user_pk=user["user_pk"], episode_pk=episode, vote="USEFUL",
                                       recorded_at=NOW)
            await conn.upsert_feedback(user_pk=user["user_pk"], episode_pk=episode, vote="NOISE",
                                       recorded_at=NOW + timedelta(hours=1))
            with pytest.raises(Exception, match="append-only"):
                await conn.conn.execute(
                    "UPDATE beta_measurement_enrollment SET known_contact_initial=true WHERE enrollment_pk=$1", pk)
            with pytest.raises(Exception):
                await conn.record_brief_attempt(enrollment_pk=pk, brief_date=date(2026, 6, 2), state="FAILED",
                                                recorded_at=NOW, error_summary="again")
            removed = await conn.delete_participant(UID)
            assert removed["users"] == 1
            assert await conn.conn.fetchval("SELECT count(*) FROM beta_users") == 0
            assert await conn.conn.fetchval("SELECT count(*) FROM beta_measurement_enrollment") == 1
            activity = await conn.conn.fetchrow(
                "SELECT user_pk, enrollment_pk, action FROM beta_user_activity")
            assert activity["user_pk"] is None and activity["enrollment_pk"] == pk
            assert activity["action"] == "cmd_catchup"
            assert await conn.conn.fetchval("SELECT count(*) FROM beta_feedback") == 0
            assert await conn.conn.fetchval("SELECT count(*) FROM beta_feedback_revisions") == 2
            blob = []
            for table in ("beta_measurement_enrollment", "beta_measurement_classification",
                          "beta_user_activity", "beta_brief_deliveries", "beta_commercial_evidence",
                          "beta_interview_verbatim", "beta_feedback_revisions"):
                rows = await conn.conn.fetch(f"SELECT * FROM {table}")
                blob.append(str([dict(r) for r in rows]))
            assert str(UID) not in " ".join(blob)
            snap = await conn.measurement_snapshot()
        dumped = str(snap)
        assert str(UID) not in dumped and "telegram_user_id" not in dumped
        scored = evaluate(snap, load_contract(), cutoff=NOW + timedelta(days=40), overlay={
            "u4_window_start": "2026-06-01", "u4_work_within_cap": True})
        assert scored["metrics"]["U4"]["reason"] != "IDENTITY_IN_SNAPSHOT"
        assert any(e["pseudonym"] == row["pseudonym"] for e in snap["enrollments"])
        old = NOW - timedelta(days=121)
        async with store.connect() as conn:
            await conn.conn.execute(
                """INSERT INTO beta_users (telegram_user_id, chat_id, status, privacy_accepted_at, joined_at)
                   VALUES (77, 77, 'ACTIVE', $1, $1)""", NOW)
            bare = await conn.conn.fetchval("SELECT user_pk FROM beta_users WHERE telegram_user_id=77")
            await conn.conn.execute(
                "INSERT INTO beta_user_activity (user_pk, action, lang, at) VALUES ($1,'cmd_help','ru',$2)",
                bare, old)
            await conn.conn.execute(
                """INSERT INTO beta_user_activity (enrollment_pk, action, lang, at)
                   VALUES ($1,'cmd_btc','ru',$2)""", pk, old)
            purged = await conn.purge_activity_before(NOW - timedelta(days=120))
            assert purged == 1
            left = await conn.conn.fetch("SELECT action, enrollment_pk FROM beta_user_activity ORDER BY action")
            assert {r["action"] for r in left} >= {"cmd_btc", "cmd_catchup"}
            stopped = await conn.conn.fetchval("SELECT count(*) FROM beta_users")
        assert stopped == 1
        await pool.close()
    run(body())


def test_stopped_user_purge_keeps_the_enrollment():
    async def body():
        from beta.delivery import run_notify_once
        from beta_fakes import CFG, ON, Clock
        pool = await fresh_pool()
        store = BetaStore(pool)
        async with store.connect() as conn:
            await conn.allowlist_add(UID)
            await conn.join_user(telegram_user_id=UID, chat_id=UID, now=NOW)
            assert await conn.stop_user(telegram_user_id=UID, now=NOW)
        report = await run_notify_once(store, CFG, ON, sender=None, clock=Clock(NOW + timedelta(days=31)))
        assert report["purged_users"] == 1
        async with store.connect() as conn:
            assert await conn.conn.fetchval("SELECT count(*) FROM beta_users") == 0
            assert await conn.conn.fetchval("SELECT count(*) FROM beta_allowlist") == 0
            kept = await conn.conn.fetchrow("SELECT pseudonym FROM beta_measurement_enrollment")
            assert kept is not None and str(UID) not in kept["pseudonym"]
        await pool.close()
    run(body())
