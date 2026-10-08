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


def test_journal_and_display_through_the_notifier_and_levels():
    """The whole path on PostgreSQL with `journal_enabled` and `display_enabled` (legacy push trigger): the
    notifier journals the T0 and T15 records of yesterday's-high zone entry; /levels prints the T15 line
    and links it; the line is gone once the race is decided."""
    from beta.decision import reset_cache
    from beta.delivery import run_notify_once
    from beta.history_stats import run_history_build
    from beta_fakes import ON_PUSH, Clock
    from runtime.beta_bot import BetaBotHandler
    from test_beta_v2_pg import A, DAY, NOW, Sender, _join, _rows, _seed, plain

    async def body():
        reset_cache()
        pool = await fresh_pool()
        store = BetaStore(pool)
        seed = await _seed(pool, minutes=358)
        inside = seed["pdh"] * 0.9995                     # after the touch the price stays in the zone
        recs = [("binance", "BTCUSDT", DAY + timedelta(minutes=m), inside, inside, inside, inside, 10.0, 5.0, "live")
                for m in range(358, 400)]
        async with pool.acquire() as c:
            await c.execute("UPDATE klines_1m SET close = $1 WHERE ts = $2", inside, DAY + timedelta(minutes=357))
            await c.executemany("""INSERT INTO klines_1m (exchange, symbol, ts, open, high, low, close, volume,
                                   taker_buy_volume, source) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)""", recs)
        cfg = _cfg(journal_enabled=True, display_enabled=True)
        assert (await run_history_build(store, cfg, now=DAY + timedelta(hours=2)))["status"] == "OK"
        t0, t15 = DAY + timedelta(hours=6), DAY + timedelta(hours=6, minutes=10)
        h = BetaBotHandler(store, cfg, switches=lambda: ON_PUSH, owner_user_id=A, clock=Clock(t0 - timedelta(hours=1)))
        msg = await _join(h, A, 100)
        for at in (NOW, t15 + timedelta(seconds=40)):
            await run_notify_once(store, cfg, ON_PUSH, sender=Sender(), clock=Clock(at))
        rows = await _rows(pool, "SELECT claim_class, issue_slot, subject->>'event_id' AS ev FROM beta_claims "
                                 "WHERE claim_class LIKE 'L2_LEVEL_RACE%' ORDER BY issue_slot")
        assert [(r["claim_class"], r["issue_slot"]) for r in rows] == [("L2_LEVEL_RACE_HIST_T0_4H", t0),
                                                                       ("L2_LEVEL_RACE_HIST_T15_4H", t15)]
        assert rows[0]["ev"] == rows[1]["ev"] and rows[0]["ev"].startswith("PDH:")
        h2 = BetaBotHandler(store, cfg, switches=lambda: ON_PUSH, owner_user_id=A,
                            clock=Clock(t15 + timedelta(minutes=2)))
        out = await h2.handle(msg("/levels", 200))
        text = plain(out[-1].html)
        assert "цена вошла в зону" in text and "Похожие касания в 2020–2024" in text and "разница" in text, text
        links = await _rows(pool, "SELECT c.claim_class, d.surface FROM beta_claim_displays d JOIN beta_claims c "
                                  "USING (claim_pk) WHERE c.claim_class LIKE 'L2_LEVEL_RACE%'")
        assert links == [{"claim_class": "L2_LEVEL_RACE_HIST_T15_4H", "surface": "levels"}]
        # the race is decided (the upper price is reached): the line is gone
        async with pool.acquire() as c:
            await c.execute("UPDATE klines_1m SET high = $1 WHERE ts = $2", seed["pdh"] * 1.05,
                            DAY + timedelta(minutes=372))
        reset_cache()
        h3 = BetaBotHandler(store, cfg, switches=lambda: ON_PUSH, owner_user_id=A,
                            clock=Clock(t15 + timedelta(minutes=20)))
        out = await h3.handle(msg("/levels", 300))
        assert "Похожие касания" not in plain(out[-1].html)
        await pool.close()
    run(body())
