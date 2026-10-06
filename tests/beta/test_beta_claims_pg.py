"""Claim journal on real PostgreSQL ($BETA_TEST_DSN): written with zero users and with pushes paused,
idempotent per hour, append-only, outcomes only under the claim's frozen rule, scored from bars,
display links, the read-only report (docs/BETA_CLAIM_JOURNAL_DESIGN_V1.md). Synthetic data only."""
from datetime import timedelta

import asyncpg
import pytest

from beta_fakes import CFG, ON_PUSH, TEST_DSN, Clock, fresh_pool, run
from storage.beta_v0_store import BetaStore
from test_beta_v2_pg import A, DAY, NOW, Sender, _handler, _join, _rows, _seed

pytestmark = pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)")


def test_the_journal_writes_scores_links_and_reports_without_users():
    from beta import claims as cj
    from beta.decision import reset_cache
    from beta.delivery import run_notify_once
    from beta.history_stats import run_history_build

    async def body():
        reset_cache()
        pool = await fresh_pool()
        store = BetaStore(pool)
        seed = await _seed(pool)
        assert (await run_history_build(store, CFG, now=DAY + timedelta(hours=2)))["status"] == "OK"
        async with store.connect() as conn:
            await conn.set_admin_push_enabled(False)               # paused, and no participant exists

        r = await run_notify_once(store, CFG, ON_PUSH, sender=Sender(), clock=Clock(NOW))
        rep = r["market"]["claims"]
        assert rep["written"] == rep["candidates"] > 0, rep
        by = {x["claim_class"]: x["n"] for x in await _rows(
            pool, "SELECT claim_class, count(*) AS n FROM beta_claims GROUP BY claim_class")}
        # 2026-05-12 is a CPI day and NOW is inside the 24h event zone: no 24h claim at all
        assert not [c for c in by if c.endswith("_24H")]
        assert by["L3_DISTANCE_TOUCH_1H"] == by["L3_DISTANCE_TOUCH_4H"] == 2 * len(cj.TOUCH_GRID_PCT)
        assert by.get("L3_LEVEL_TOUCH_4H", 0) >= 1
        # the first touch of yesterday's high was evaluated (suppressed: pushes paused) and journaled
        alerts = await _rows(pool, "SELECT alert_key, decision FROM beta_market_alerts")
        assert alerts == [{"alert_key": f"level:PDH:{DAY.date().isoformat()}", "decision": "SUPPRESSED"}]
        assert by["L2_LEVEL_FIRST_TOUCH_HOLD_1H"] == by["L2_LEVEL_FIRST_TOUCH_HOLD_4H"] == 1
        hold = (await _rows(pool, "SELECT subject_key, eligible_reason, numbers->>'n' AS n FROM beta_claims "
                                  "WHERE claim_class='L2_LEVEL_FIRST_TOUCH_HOLD_1H'"))[0]
        assert hold["subject_key"] == f"level:PDH:{DAY.date().isoformat()}" and int(hold["n"]) >= 30

        # one hour, one claim per subject: the next minute writes nothing
        r2 = await run_notify_once(store, CFG, ON_PUSH, sender=Sender(), clock=Clock(NOW + timedelta(minutes=1)))
        assert r2["market"]["claims"]["written"] == 0
        total = (await _rows(pool, "SELECT count(*) AS n FROM beta_claims"))[0]["n"]

        # append-only, and an outcome only under the claim's own rule
        async with pool.acquire() as c:
            with pytest.raises(asyncpg.PostgresError):
                await c.execute("UPDATE beta_claims SET subject_key = 'x' WHERE claim_pk = 1")
            with pytest.raises(asyncpg.PostgresError):
                await c.execute("DELETE FROM beta_claims")
        one = (await _rows(pool, "SELECT claim_pk FROM beta_claims WHERE claim_class='L3_DISTANCE_TOUCH_1H' "
                                 "ORDER BY claim_pk LIMIT 1"))[0]["claim_pk"]
        async with store.connect() as conn:
            with pytest.raises(asyncpg.PostgresError):
                await conn.insert_claim_outcome(claim_pk=one, eval_rule_digest="0" * 64, status="NO_DATA",
                                                realized={}, computed_at=NOW, outcome_digest="1" * 64)

        # a display link: the /risk table prints the 1h / 4h distance grid of this hour
        async with store.connect() as conn:
            blk = {"available": True, "corridor": {"horizons": {"1h": {}, "4h": {}}}, "levels": {}}
            linked = await cj.record_displays(conn, surface="risk", shown=cj.shown_keys("risk", blk), now=NOW)
        assert linked == 2 * 4 * 2

        # one hour later the 1h claims are scored from the 1m bars
        async with pool.acquire() as c:
            later = [("binance", "BTCUSDT", DAY + timedelta(hours=6, minutes=m), seed["base"], seed["base"] * 1.0003,
                      seed["base"] * 0.9997, seed["base"], 1.0, 0.5, "live") for m in range(0, 70)]
            await c.executemany("""INSERT INTO klines_1m (exchange, symbol, ts, open, high, low, close, volume,
                                       taker_buy_volume, source) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                                   ON CONFLICT DO NOTHING""", later)
        await run_notify_once(store, CFG, ON_PUSH, sender=Sender(), clock=Clock(NOW + timedelta(hours=1, minutes=5)))
        scored = await _rows(pool, """SELECT c.claim_class, o.status, o.realized->>'touched' AS touched
                                      FROM beta_claim_outcomes o JOIN beta_claims c USING (claim_pk)
                                      WHERE c.claim_class = 'L3_DISTANCE_TOUCH_1H' ORDER BY c.claim_pk""")
        assert len(scored) == 2 * len(cj.TOUCH_GRID_PCT) and {x["status"] for x in scored} == {"COMPLETE"}
        assert {x["touched"] for x in scored} == {"false"}            # ±0.03% moves never reach 0.25%
        # the next hour's claims are a new slot
        assert (await _rows(pool, "SELECT count(*) AS n FROM beta_claims"))[0]["n"] > total

        # the hourly refresh pooled the scored 1h touch claims into the live calibration
        async with store.connect() as conn:
            live = (await conn.fetch_health())[cj.TOUCH_LIVE_COMPONENT]["detail"]
            cells = await conn.touch_claim_cells(since=DAY, classes=list(cj.touch_classes("1h")))
        assert sum(int(c["n"]) for c in cells) == 2 * len(cj.TOUCH_GRID_PCT)
        assert sum(b["n"] for b in live["horizons"]["1h"]["bins"]) == 2 * len(cj.TOUCH_GRID_PCT)
        assert live["diverged"] == {"1h": [], "4h": [], "24h": []}
        async with store.connect() as conn:
            report = cj.claims_report(await conn.fetch_claim_cohort(since=DAY))
        dist = report["classes"]["L3_DISTANCE_TOUCH_1H"]
        assert dist["scored"] == 2 * len(cj.TOUCH_GRID_PCT) and dist["n_eff"] == 1 and dist["shown"] == 2 * 4
        await pool.close()
    run(body())


def test_live_cells_use_the_class_horizon_for_slots_24h_included():
    """A 24h claim's slot is one UTC day: 72 hourly 24h claims over 3 days are 3 independent slots,
    not 18 (a 2-character suffix read _24H as 4H)."""
    from beta import claims as cj

    async def body():
        pool = await fresh_pool()
        store = BetaStore(pool)
        start = DAY.replace(hour=0, minute=0, second=0, microsecond=0)
        async with store.connect() as conn:
            for h, hours in (("24H", 72), ("4H", 24), ("1H", 6)):
                ms = {"1H": 3_600_000, "4H": 14_400_000, "24H": 86_400_000}[h]
                for i in range(hours):
                    at = start + timedelta(hours=i, minutes=1)
                    row = cj.claim_row(f"L3_DISTANCE_TOUCH_{h}", issued_at=at, issue_slot=at.replace(minute=0),
                                       as_of=at, subject={"side": 1, "distance_pct": 1.0}, subject_key="up:1.0",
                                       numbers={"probability": 0.2}, rule_version="t", eligible_reason="GRID",
                                       horizon_ms=ms)
                    pk = await conn.insert_claim(row)
                    await conn.insert_claim_outcome(claim_pk=pk, eval_rule_digest=row["eval_rule_digest"],
                                                    status="COMPLETE", realized={"touched": i % 5 == 0},
                                                    computed_at=at + timedelta(milliseconds=ms),
                                                    outcome_digest="0" * 64)
            cells = await conn.touch_claim_cells(since=start, classes=[f"L3_DISTANCE_TOUCH_{h}"
                                                                        for h in ("1H", "4H", "24H")])
        slots = {}
        for c in cells:
            slots.setdefault(c["claim_class"], set()).add(int(c["slot"]))
        assert {k: len(v) for k, v in slots.items()} == {"L3_DISTANCE_TOUCH_24H": 3, "L3_DISTANCE_TOUCH_4H": 6,
                                                         "L3_DISTANCE_TOUCH_1H": 6}
        assert [b["n_eff"] for b in cj.live_touch_bins(cells, "24h")] == [3]
        assert [b["n"] for b in cj.live_touch_bins(cells, "24h")] == [72]
        await pool.close()
    run(body())


@pytest.mark.parametrize("withdrawn", [True, False])
def test_brief_claims_are_linked_only_after_a_participant_received_the_brief(monkeypatch, withdrawn):
    """A brief withheld on a U1a withdrawal day shows nothing, so its claims get no display link; a
    delivered brief links them once, to the hour the brief was built in."""
    from beta import delivery
    from beta.decision import reset_cache
    from beta.history_stats import run_history_build
    from beta.i18n import kyiv

    async def body():
        reset_cache()
        pool = await fresh_pool()
        store = BetaStore(pool)
        await _seed(pool)
        assert (await run_history_build(store, CFG, now=DAY + timedelta(hours=2)))["status"] == "OK"
        async with store.connect() as conn:
            await conn.allowlist_add(A)
        await _join(_handler(pool, 900000000001, Clock(NOW - timedelta(hours=1))), A, 10)
        if withdrawn:
            monkeypatch.setattr(delivery, "brief_withdrawal_dates", lambda b: frozenset({kyiv(NOW).date()}))
        # this synthetic morning is inside the CPI 24h zone, so the brief itself prints no claim: let it
        # show two of the hour's 1h grid claims, to see when (and whether) they are linked
        from beta import claims as cj
        shown = {("L3_DISTANCE_TOUCH_1H", "+1:0.25"), ("L3_DISTANCE_TOUCH_1H", "-1:0.25")}
        monkeypatch.setattr(cj, "shown_keys", lambda surface, *a, **k: shown if surface == "brief" else set())
        # the synthetic tape has no venues, so the view is degraded and would link nothing (review of #346 + #348,
        # test_beta_review_348): the timing of the links is tested as if it were not
        from beta import formatter
        monkeypatch.setattr(formatter, "view_degraded", lambda view: False)
        r = await delivery.run_notify_once(store, CFG, ON_PUSH, sender=Sender(), clock=Clock(NOW))
        b = r["briefs"]
        links = await _rows(pool, """SELECT d.view_pk, d.shown_at, c.issue_slot FROM beta_claim_displays d
                                     JOIN beta_claims c USING (claim_pk) WHERE d.surface = 'brief'""")
        if withdrawn:
            assert b["withheld"] == 1 and b["sent"] == 0 and links == []
        else:
            assert b["sent"] == 1 and len(links) == 2
            assert {x["issue_slot"] for x in links} == {NOW.replace(minute=0, second=0, microsecond=0)}
            # a second run sends nothing new and links nothing twice
            await delivery.run_notify_once(store, CFG, ON_PUSH, sender=Sender(), clock=Clock(NOW + timedelta(minutes=1)))
            assert len(await _rows(pool, "SELECT 1 FROM beta_claim_displays WHERE surface = 'brief'")) == len(links)
        await pool.close()
    run(body())
