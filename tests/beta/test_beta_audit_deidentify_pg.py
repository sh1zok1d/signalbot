"""OUT-8: the read-only count and the redaction of pre-#418 deletion audit rows, on a copy with representative
rows (docs/BETA_AUDIT_DEIDENTIFY_V1.md). Runs the two deploy SQL files with psql, as the owner would."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from beta.i18n import KYIV
from beta_fakes import TEST_DSN, fresh_pool, run

pytestmark = [pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)"),
              pytest.mark.skipif(shutil.which("psql") is None, reason="psql not installed")]
ROOT = Path(__file__).resolve().parents[2]
OWNER_FP = "u_0123456789ab"
LIVE_ID = 900000000777


def _fp(uid):
    import hashlib
    return "u_" + hashlib.sha256(f"signalbot-beta-v0:{uid}".encode()).hexdigest()[:12]


LIVE_FP = _fp(LIVE_ID)


def _psql(*args):
    out = subprocess.run(["psql", TEST_DSN, "-X", "-v", "ON_ERROR_STOP=1", *args],
                         capture_output=True, text=True, check=True)
    return out.stdout


def test_count_is_read_only_and_redaction_keeps_only_the_cohort_fields():
    async def body():
        pool = await fresh_pool()
        rows = [  # as main wrote them before #418
            ("user_delete_me", "participant", None,
             {"users": 1, "allowlist": 1, "waitlist": 0, "activity": 17,
              "cohort": {"joined_kyiv_date": "2026-10-01", "known_contact": False}}),
            ("retention_purge", "system", "u_aaaaaaaaaaaa",
             {"users": 1, "allowlist": 0, "waitlist": 0, "activity": 3,
              "cohort": {"joined_kyiv_date": "2026-09-20", "known_contact": True}}),
            ("admin_remove", OWNER_FP, OWNER_FP,                     # the owner removing their own test account
             {"users": 1, "allowlist": 1, "waitlist": 0, "activity": 40, "cohort": None}),
            ("admin_remove", OWNER_FP, "u_bbbbbbbbbbbb",
             {"users": 0, "allowlist": 1, "waitlist": 0, "activity": 0, "cohort": None}),
            ("admin_stats", OWNER_FP, None, {"waitlist": 2}),          # never touched
            ("admin_known", OWNER_FP, "u_aaaaaaaaaaaa", {"known": True}),   # a deleted person: fingerprint goes
            ("admin_known", OWNER_FP, LIVE_FP, {"known": False}),            # still present: stays
            ("admin_add", OWNER_FP, OWNER_FP, {}),                           # the owner's own: stays
        ]
        await pool.execute("INSERT INTO beta_allowlist VALUES ($1, now())", LIVE_ID)
        for action, actor, target, detail in rows:
            await pool.execute("""INSERT INTO beta_admin_audit (action, authorized, actor_fingerprint,
                                      target_fingerprint, result, detail) VALUES ($1, true, $2, $3, 'OK', $4::jsonb)""",
                               action, actor, target, json.dumps(detail))
        before = [dict(r) for r in await pool.fetch("SELECT * FROM beta_admin_audit ORDER BY audit_id")]

        count = _psql("-At", "-v", f"owner_fp={OWNER_FP}",
                      "-f", str(ROOT / "deploy/signalbot-beta-audit-deidentify-count.sql"))
        lines = [ln for ln in count.splitlines() if "|" in ln or ln.isdigit()]
        by_action = {ln.split("|")[0]: ln.split("|")[1:] for ln in lines if "|" in ln}
        assert by_action["admin_remove"][:5] == ["2", "2", "1", "2", "2"]    # total, target fp, owner target, owner actor, extra
        assert by_action["retention_purge"][:2] == ["1", "1"] and by_action["user_delete_me"][:2] == ["1", "0"]
        assert [ln for ln in lines if ln.isdigit()] == ["4"]                 # deletion rows the redaction would change
        assert by_action["admin_known"][0] == "1"                            # the deleted person's admin_known row
        assert [dict(r) for r in await pool.fetch("SELECT * FROM beta_admin_audit ORDER BY audit_id")] == before

        out = _psql("-f", str(ROOT / "deploy/signalbot-beta-audit-deidentify.sql"))
        assert "before" in out and "after" in out and "trg_beta_audit_append_only | O" in out
        after = {r["audit_id"]: dict(r) for r in await pool.fetch("SELECT * FROM beta_admin_audit")}
        for b in before:
            a = after[b["audit_id"]]
            assert a["actor_fingerprint"] == b["actor_fingerprint"]
            if b["action"] in ("admin_stats", "admin_add") or b["target_fingerprint"] == LIVE_FP:
                assert a == b
                continue
            if b["action"] == "admin_known":                         # switch other_actions (default on)
                assert a["target_fingerprint"] is None and a["detail"] == b["detail"]
                assert a["recorded_at"] == b["recorded_at"]
                continue
            kyiv = b["recorded_at"].astimezone(KYIV)                 # switch coarsen (default on)
            assert a["recorded_at"] == kyiv.replace(hour=0, minute=0, second=0, microsecond=0)
            detail = json.loads(a["detail"])
            assert a["target_fingerprint"] is None and set(detail) == {"cohort"}, b["action"]
        cohorts = [json.loads(after[b["audit_id"]]["detail"])["cohort"] for b in before[:4]]
        assert "switches: coarsen= on  other_actions= on" in out
        assert cohorts == [{"joined_kyiv_date": "2026-10-01", "known_contact": False, "joined_after_test_open": False},
                           {"joined_kyiv_date": "2026-09-20", "known_contact": True, "joined_after_test_open": False},
                           None, None]
        with pytest.raises(Exception):                               # append-only again
            await pool.execute("DELETE FROM beta_admin_audit")
        again = _psql("-f", str(ROOT / "deploy/signalbot-beta-audit-deidentify.sql"))
        assert again.count("UPDATE 0") == 3                          # idempotent, every switch
        await pool.close()
    run(body())


def test_the_switches_can_be_turned_off():
    async def body():
        pool = await fresh_pool()
        await pool.execute("""INSERT INTO beta_admin_audit (action, authorized, actor_fingerprint, target_fingerprint,
                                  result, detail, recorded_at) VALUES
                              ('user_delete_me', true, 'participant', NULL, 'OK',
                               '{"activity": 2, "cohort": {"joined_kyiv_date": "2026-10-01", "known_contact": false}}',
                               '2026-10-03T13:14:15Z'),
                              ('admin_known', true, $1, 'u_cccccccccccc', 'OK', '{}', '2026-10-02T10:00:00Z')""",
                           OWNER_FP)
        out = _psql("-v", "coarsen=off", "-v", "other_actions=off",
                    "-f", str(ROOT / "deploy/signalbot-beta-audit-deidentify.sql"))
        assert "switches: coarsen= off  other_actions= off" in out
        rows = {r["action"]: dict(r) for r in await pool.fetch("SELECT * FROM beta_admin_audit")}
        assert rows["user_delete_me"]["recorded_at"].isoformat() == "2026-10-03T13:14:15+00:00"
        assert set(json.loads(rows["user_delete_me"]["detail"])) == {"cohort"}
        assert rows["admin_known"]["target_fingerprint"] == "u_cccccccccccc"
        await pool.close()
    run(body())
