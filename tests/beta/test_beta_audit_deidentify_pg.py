"""OUT-8 v2: the read-only count and the redaction of every audit row about a deleted participant, with the old
deletion rows reduced to the #420 minimal form and moved into the counter where they qualify
(docs/BETA_AUDIT_DEIDENTIFY_V1.md). Runs the two deploy SQL files with psql, as the owner would."""
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from beta.i18n import KYIV
from beta_fakes import TEST_DSN, fresh_pool, run

pytestmark = [pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)"),
              pytest.mark.skipif(shutil.which("psql") is None, reason="psql not installed")]
ROOT = Path(__file__).resolve().parents[2]
LIVE_ID, GONE_ID, OWNER_ID = 900000000777, 900000000666, 900000000900


def _old_fp(uid):                       # the unkeyed formula every pre-#421 row holds
    return "u_" + hashlib.sha256(f"signalbot-beta-v0:{uid}".encode()).hexdigest()[:12]


LIVE_FP, GONE_FP, OWNER_FP = _old_fp(LIVE_ID), _old_fp(GONE_ID), _old_fp(OWNER_ID)
T = datetime(2026, 10, 3, 13, 14, 15, tzinfo=timezone.utc)
COUNT = ROOT / "deploy/signalbot-beta-audit-deidentify-count.sql"
REDACT = ROOT / "deploy/signalbot-beta-audit-deidentify.sql"


def _psql(*args, stdin_file):
    with open(stdin_file, encoding="utf-8") as fh:
        out = subprocess.run(["psql", TEST_DSN, "-X", "-v", "ON_ERROR_STOP=1", *args],
                             stdin=fh, capture_output=True, text=True, check=True)
    return out.stdout


def test_every_row_about_a_deleted_participant_is_de_identified():
    async def body():
        pool = await fresh_pool()
        await pool.execute("INSERT INTO beta_allowlist VALUES ($1, now())", LIVE_ID)
        rows = [  # (action, actor, target, detail) as main and #418 wrote them
            ("user_delete_me", "participant", None, {"users": 1, "activity": 17,
                                                     "cohort": {"joined_kyiv_date": "2026-10-01", "known_contact": False}}),
            ("retention_purge", "system", GONE_FP, {"cohort": {"joined_kyiv_date": "2026-10-02", "known_contact": False,
                                                               "joined_after_test_open": True}}),
            ("admin_remove", OWNER_FP, GONE_FP, {"users": 1, "activity": 40, "cohort": None}),
            ("admin_known", OWNER_FP, GONE_FP, {"known_contact": True}),       # about the deleted person
            ("admin_reply", OWNER_FP, GONE_FP, {}),
            ("admin_known", OWNER_FP, LIVE_FP, {"known_contact": False}),      # about someone still present
            ("admin_add", OWNER_FP, OWNER_FP, {"result": "OK"}),              # the owner's own
            ("admin_stats", OWNER_FP, None, {"waitlist": 2}),                  # about nobody
        ]
        for action, actor, target, detail in rows:
            await pool.execute("""INSERT INTO beta_admin_audit (action, authorized, actor_fingerprint, target_fingerprint,
                                      result, detail, recorded_at) VALUES ($1, true, $2, $3, 'OK', $4::jsonb, $5)""",
                               action, actor, target, json.dumps(detail), T)
        before = {r["audit_id"]: dict(r) for r in await pool.fetch("SELECT * FROM beta_admin_audit")}

        count = _psql("-At", "-v", f"owner_fp={OWNER_FP}", stdin_file=COUNT)
        lines = count.splitlines()
        assert any(ln.startswith("deleted_person|admin_known|1|1|0|1|1|") for ln in lines)
        assert any(ln.startswith("deleted_person|admin_reply|1|1|0|1|0|") for ln in lines)
        assert any(ln.startswith("live|admin_known|1|1|0|1|1|") for ln in lines)
        assert any(ln.startswith("actor_own|admin_add|1|1|1|1|1|") for ln in lines)
        assert [ln for ln in lines if ln.isdigit()] == ["1"]                   # one old deletion row for the counter
        assert {r["audit_id"]: dict(r) for r in await pool.fetch("SELECT * FROM beta_admin_audit")} == before

        out = _psql(stdin_file=REDACT)
        assert "trg_beta_audit_append_only | O" in out
        after = {r["audit_id"]: dict(r) for r in await pool.fetch("SELECT * FROM beta_admin_audit")}
        midnight = T.astimezone(KYIV).replace(hour=0, minute=0, second=0)
        for audit_id, b in before.items():
            a = after[audit_id]
            if b["action"] in ("user_delete_me", "retention_purge", "admin_remove"):
                kind = {"user_delete_me": "participant", "retention_purge": "system", "admin_remove": "owner"}
                assert (a["actor_fingerprint"], a["target_fingerprint"], json.loads(a["detail"])) == (
                    kind[b["action"]], None, {})
                assert a["recorded_at"] == midnight
            elif b["target_fingerprint"] == GONE_FP:
                assert (a["actor_fingerprint"], a["target_fingerprint"], json.loads(a["detail"])) == (OWNER_FP, None, {})
                assert a["recorded_at"] == midnight and a["action"] == b["action"]     # the fact stays
            else:
                assert a == b, b["action"]                                       # live, own, no target: untouched
        assert [dict(r) for r in await pool.fetch("SELECT * FROM beta_deleted_cohort_counts")] == [
            {"joined_kyiv_date": datetime(2026, 10, 2).date(), "n": 1}]          # only the post-opening unknown one
        with pytest.raises(Exception):                                           # append-only again
            await pool.execute("DELETE FROM beta_admin_audit")
        again = _psql(stdin_file=REDACT)
        assert again.count("UPDATE 0") == 2 and "INSERT 0 0" in again           # idempotent
        counts = [dict(r) for r in await pool.fetch("SELECT * FROM beta_deleted_cohort_counts")]
        assert counts[0]["n"] == 1
        await pool.close()
    run(body())


def test_rows_with_keyed_fingerprints_are_left_alone_and_counted():
    async def body():
        pool = await fresh_pool()
        await pool.execute("""INSERT INTO beta_admin_audit (action, authorized, actor_fingerprint, target_fingerprint,
                                  result, detail, recorded_at) VALUES
                              ('admin_known', true, 'u_keyedowner01', 'u_keyedperson1', 'OK', '{}', '2026-11-02T10:00:00Z'),
                              ('admin_known', true, $1, $2, 'OK', '{}', '2026-10-02T10:00:00Z')""", OWNER_FP, GONE_FP)
        count = _psql("-At", "-v", f"owner_fp={OWNER_FP}", "-v", "keyed_since=2026-11-01T00:00:00Z", stdin_file=COUNT)
        assert "keyed_unmatched|admin_known|1|" in count and "deleted_person|admin_known|1|" in count
        _psql("-v", "keyed_since=2026-11-01T00:00:00Z", stdin_file=REDACT)
        rows = {r["target_fingerprint"] for r in await pool.fetch("SELECT target_fingerprint FROM beta_admin_audit")}
        assert rows == {"u_keyedperson1", None}
        await pool.close()
    run(body())
