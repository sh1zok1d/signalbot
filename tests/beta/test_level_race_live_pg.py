"""Level race HIST journal on real PostgreSQL ($BETA_TEST_DSN): rows are accepted by the claim schema,
idempotent per (class, event, landmark), scored only under their frozen rule, linked to a surface on
their own slot and reported. Synthetic bars only."""
from datetime import timedelta

import asyncpg
import pytest

from beta_fakes import TEST_DSN, fresh_pool, run
from storage.beta_v0_store import BetaStore
from test_level_race_live import B, _cfg, _block, _cut, _t15_event, _ts

pytestmark = pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)")


def test_hist_journal_round_trip_on_postgres():
    from beta import claims as cj

    async def body():
        pool = await fresh_pool()
        store = BetaStore(pool)
        e, v = _t15_event()
        cap = {"bars": _cut(B, e["t15_ms"])}
        now = _ts(e["t15_ms"] + 60_000)
        on = _cfg(journal_enabled=True)
        async with store.connect() as conn:
            rep = await cj.record_level_race(conn, on, now=now, capture=cap)
            assert rep["race_written"] >= 1
            assert (await cj.record_level_race(conn, on, now=now, capture=cap))["race_written"] == 0
            blk = _block(cap["bars"], now + timedelta(minutes=70), float(cap["bars"].close[-1]))
            assert await cj.record_displays(conn, surface="levels", shown=cj.shown_keys("levels", blk),
                                            now=now + timedelta(minutes=70)) == 1
            end = e["window_end_ms"]
            due = await conn.fetch_due_claims(now=_ts(end) + timedelta(minutes=5))
            mine = [c for c in due if c["claim_class"] == "L2_LEVEL_RACE_HIST_T15_4H"]
            assert len(mine) == 1
            res = await cj.score_claims(conn, _cut(B, end), [], now=_ts(end) + timedelta(minutes=5))
            assert res["scored"] >= 1
            rows = await conn.fetch_claim_cohort(classes=["L2_LEVEL_RACE_HIST_T15_4H"])
        assert len(rows) == 1 and rows[0]["status"] == "COMPLETE" and rows[0]["shown"] is True
        assert rows[0]["subject"]["mode"] == "HIST" and rows[0]["realized"]["outcome"] in ("UP", "DN", "NEITHER", "AMBIGUOUS")
        rep = cj.claims_report(rows)["classes"]["L2_LEVEL_RACE_HIST_T15_4H"]
        assert rep["n"] == 1
        async with pool.acquire() as c:
            pk = rows[0]["claim_pk"]
            with pytest.raises(asyncpg.PostgresError):        # never under another rule
                await c.execute("INSERT INTO beta_claim_outcomes (claim_pk, eval_rule_digest, revision, status, "
                                "realized, computed_at, outcome_digest) VALUES ($1, $2, 2, 'COMPLETE', '{}', now(), $2)",
                                pk, "0" * 64)
            with pytest.raises(asyncpg.PostgresError):        # append-only
                await c.execute("UPDATE beta_claims SET subject_key = 'x' WHERE claim_pk = $1", pk)
        await pool.close()
    run(body())
