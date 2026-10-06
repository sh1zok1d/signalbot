"""Owner-only signature index (PRE_BETA_SCOPE_DECISION_V1 §7; backlog K) on real PostgreSQL
($BETA_TEST_DSN): buckets signed from stored states in the notifier step, append-only, episodes split by a
change or a gap, the NEW rule, the blind review frozen once, /pin, owner-only commands and the export.
Synthetic data only."""
from datetime import datetime, timedelta, timezone

import asyncpg
import pytest

from beta_fakes import CFG, ON_PUSH, TEST_DSN, Clock, fresh_pool, run
from storage.beta_v0_store import BetaStore
from test_beta_v2_pg import A, Sender, _handler, _rows, plain

pytestmark = pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)")

UTC = timezone.utc
OWNER = 900000000999
T0 = datetime(2026, 10, 4, 22, 0, tzinfo=UTC)
# marks per 5m bucket: X is a two-tail signature, Y a neutral one; None is a missing bucket (a gap)
DAY1 = ["X", "X", "Y", "X", "Y"]                  # 22:00 .. 22:20 on 10-04: two X episodes
DAY2 = ["Y", "X", "X", None, "X", "Y"]            # 00:00 .. 00:25 on 10-05: one X episode, a gap, one more;
                                                  # the newest bucket (Y) is the one the run's evidence describes


def _comp(mark, d7, evidence):
    from beta import signatures as sg
    base = {k: "normal" for k in ("i1h", "i4h", "r1h", "v1h", "r4h", "v4h")}
    base.update(gate="N", liq="none", day="WD", d7=sg.UNKNOWN if d7 is None else ("on" if d7 else "off"),
                ev=sg.UNKNOWN if evidence is None else "+".join(evidence))
    if mark == "X":
        base.update(i1h="long_build", gate="Q")
    return base


async def _snapshots(pool, buckets):
    from beta.context import episodization_digest
    async with pool.acquire() as c:
        await c.executemany(
            """INSERT INTO beta_context_snapshots (symbol, bucket_ts, episodization_version, episodization_digest,
                   context_version, context_digest, rules_digest, state, state_digest)
               VALUES ('BTCUSDT', $1, 'E', $2, 'C', repeat('c', 64), repeat('a', 64), $3::jsonb, repeat('b', 64))""",
            [(b, episodization_digest(CFG), f'{{"mark": "{m}"}}') for b, m in buckets])


def _owner(text, k, uid=OWNER):
    return {"update_id": k, "message": {"from": {"id": uid}, "chat": {"id": uid, "type": "private"}, "text": text}}


def test_signature_index_end_to_end(monkeypatch):
    from beta import signatures as sg

    monkeypatch.setattr(sg, "components", lambda cfg, *, state, rules, d7, evidence: _comp(state.get("mark"), d7,
                                                                                            evidence))

    async def body():
        pool = await fresh_pool()
        store = BetaStore(pool)
        day1 = [(T0 + timedelta(minutes=5 * i), m) for i, m in enumerate(DAY1)]
        day2 = [(datetime(2026, 10, 5, 0, 0, tzinfo=UTC) + timedelta(minutes=5 * i), m) for i, m in enumerate(DAY2)]
        await _snapshots(pool, day1[:1])
        async with pool.acquire() as c:              # the D7 state of 21:00 became available at 22:07
            await c.execute("""INSERT INTO beta_d7_hour_states (hour_start, complete, state, available_at, computed_at,
                                   definition_digest) VALUES ($1, TRUE, TRUE, $2, $2, repeat('d', 64))""",
                            T0 - timedelta(hours=1), T0 + timedelta(minutes=7))
        async with store.connect() as conn:
            # the first run signs the newest bucket only: the index starts now, without backfill
            assert (await sg.record_signatures(conn, CFG, now=T0 + timedelta(minutes=6)))["signed"] == 1
        await _snapshots(pool, day1[1:] + [x for x in day2 if x[1] is not None])
        newest = day2[-1][0]
        ev = {"as_of": (newest + timedelta(minutes=6)).isoformat(), "matches": [{"finding_id": "D2"}]}
        async with store.connect() as conn:
            rep = await sg.record_signatures(conn, CFG, now=newest + timedelta(minutes=6), evidence=ev)
            assert rep["signed"] == len(DAY1) - 1 + 5
            again = await sg.record_signatures(conn, CFG, now=newest + timedelta(minutes=7), evidence=ev)
            assert again["signed"] == 0                                   # idempotent per bucket
        rows = await _rows(pool, """SELECT bucket_ts, episode_start, components->>'d7' AS d7,
                                          components->>'ev' AS ev, tail_count FROM beta_signature_buckets
                                   ORDER BY bucket_ts""")
        # a change of any component starts an episode (22:05: D7 became readable), and so does a gap (00:15)
        assert [r["episode_start"] for r in rows] == [True, True, True, True, True,       # day 1
                                                      True, True, False, True, True]     # day 2
        # as-of: the 22:00 bucket closes at 22:05, before the hour state existed; the 22:05 one at 22:10
        assert rows[0]["d7"] == "?" and rows[1]["d7"] == "on"
        assert [r["ev"] for r in rows][-1] == "D2" and {r["ev"] for r in rows[:-1]} == {"?"}
        async with pool.acquire() as c:
            with pytest.raises(asyncpg.PostgresError):
                await c.execute("UPDATE beta_signature_buckets SET tail_count = 0")

        # the owner's index: X with D7 unread is NEW (2 tails, 3 episodes, 2 UTC days); X with D7 on has only
        # 2 episodes on one day; Y has no tail
        x_id = sg.signature_id(sg.signature_key(_comp("X", None, None)))
        h = _handler(pool, OWNER, Clock(newest + timedelta(minutes=8)))
        text = plain((await h.handle(_owner("/hypotheses", 1)))[0].html)
        assert "NEW 1" in text and f"[{x_id}]" in text and "3 episodes · 2 days · tail 2" in text
        assert "what followed is not shown" in text
        assert plain((await h.handle(_owner("/hypotheses", 2, uid=A)))[0].html) != text      # never for others
        assert "needs the hypothesis text" in plain((await h.handle(_owner("/hypotheses research " + x_id, 3)))[0].html)
        frozen = plain((await h.handle(_owner(f"/hypotheses research {x_id} quiet build-up before range", 4)))[0].html)
        assert f"[{x_id}] в research; frozen window 2026-10-04 22:00 .. 2026-10-05 00:25 UTC" == frozen
        assert "already reviewed" in plain((await h.handle(_owner(f"/hypotheses reject {x_id}", 5)))[0].html)
        after = plain((await h.handle(_owner("/hypotheses", 6)))[0].html)
        assert "NEW 0" in after and f"[{x_id}] RESEARCH" in after
        assert "pinned 2026-10-05 00:25 UTC" in plain((await h.handle(_owner("/pin looks like a squeeze", 7)))[0].html)
        reviews = await _rows(pool, "SELECT decision, hypothesis, seen FROM beta_hypothesis_reviews")
        assert len(reviews) == 1 and reviews[0]["decision"] == "RESEARCH"
        async with pool.acquire() as c:
            with pytest.raises(asyncpg.PostgresError):
                await c.execute("UPDATE beta_hypothesis_reviews SET decision = 'REJECT'")

        # the export for a reviewed atlas change (read-only)
        from storage.db import Database
        import main
        from runtime.beta_cli import run_beta_cli_command
        db = Database(TEST_DSN)
        await db.connect()
        try:
            out = await run_beta_cli_command(main.parse_args(["--beta-hypotheses-export", "--beta-json"]), db=db,
                                             env={}, clock=Clock(newest))
        finally:
            await db.close()
        assert out["status"] == "OK" and out["reviews"][0]["signature_id"] == x_id
        assert out["reviews"][0]["exposure_entry"]["period"] == "2026-10-04..2026-10-05"

        # the notifier step signs on its own, with the alert run's evidence, and never stops the run
        from beta.delivery import run_notify_once
        r = await run_notify_once(store, CFG, ON_PUSH, sender=Sender(), clock=Clock(newest + timedelta(minutes=9)))
        assert "signatures" in r["market"] and "signatures_error" not in r["market"]
        await pool.close()
    run(body())
