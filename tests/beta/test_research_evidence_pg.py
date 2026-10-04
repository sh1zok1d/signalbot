"""Research evidence on real PostgreSQL ($BETA_TEST_DSN): the read-only feeds job and the stress-hour
job write their tables from (fake) public responses; the decision block carries the evidence; /btc
shows at most two research lines; the research tab opens from the stored view and is recorded;
the corridor, the levels and the touch probabilities are identical with the evidence on or off.
Synthetic data only; no network, no Telegram."""
import asyncio
import json
import re
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from beta_fakes import CFG, ON_PUSH, TEST_DSN, Clock, fresh_pool, run
from storage.beta_v0_store import BetaStore
from test_beta_v2_pg import DAY, HIST_DAYS, NOW, _handler, _join, _rows, _seed, plain

pytestmark = pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)")
UTC = timezone.utc


def _ms(dt):
    return int(dt.timestamp() * 1000)


def fake_public_api(now, *, oi_rows, ls_rows, dvol, book, spot, k1h=(), perp_trades=(), spot_trades=()):
    from beta import research_feeds as RF
    calls = []

    async def fetch(url, params):
        calls.append((url, dict(params)))
        if url == RF.FAPI + "/futures/data/openInterestHist":
            return [r for r in oi_rows if params["startTime"] <= r["timestamp"] <= params["endTime"]]
        if url == RF.FAPI + "/futures/data/globalLongShortAccountRatio":
            return [r for r in ls_rows if params["startTime"] <= r["timestamp"] <= params["endTime"]]
        if url == RF.DERIBIT_DVOL:
            return {"result": {"data": [x for x in dvol if params["start_timestamp"] <= x[0] <= params["end_timestamp"]]}}
        if url == RF.FAPI + "/fapi/v1/depth":
            return book
        if url == RF.SPOT_API + "/api/v3/klines":
            return [k for k in spot if k[0] >= params["startTime"]][:params["limit"]]
        if url == RF.FAPI + "/fapi/v1/klines":
            return list(k1h)
        for venue, trades in (("/fapi/v1/aggTrades", perp_trades), ("/api/v3/aggTrades", spot_trades)):
            if url.endswith(venue):
                if "fromId" in params:
                    rest = [x for x in trades if x["a"] >= params["fromId"]]
                else:
                    rest = [x for x in trades if params["startTime"] <= x["T"] <= params["endTime"]]
                return rest[:params["limit"]]
        raise AssertionError(f"unexpected request {url}")
    return fetch, calls


def test_feeds_engine_surfaces_and_numbers_end_to_end():
    from beta.decision import build_decision, reset_cache
    from beta.history_stats import run_history_build
    from beta.research_feeds import run_feeds_job, run_stress_job

    async def body():
        reset_cache()
        pool = await fresh_pool()
        store = BetaStore(pool)
        await _seed(pool)
        rep = await run_history_build(store, CFG, now=DAY + timedelta(hours=2))
        assert rep["status"] == "OK"
        now = NOW
        t_end = _ms(now) - _ms(now) % 300_000
        # the REST tail repeats the Vision labels of the last 30 days and continues after them
        async with pool.acquire() as c:
            vis = await c.fetch("SELECT (extract(epoch FROM ts)*1000)::bigint AS t, oi_base FROM beta_hist_oi_5m "
                                "WHERE ts >= $1 ORDER BY ts", now - timedelta(days=30))
        last_vis = int(vis[-1]["t"])
        oi_rows = [{"timestamp": int(r["t"]), "sumOpenInterest": repr(float(r["oi_base"]))} for r in vis]
        oi_rows += [{"timestamp": t, "sumOpenInterest": repr(float(vis[-1]["oi_base"]) * (1 + 1e-5 * k))}
                    for k, t in enumerate(range(last_vis + 300_000, t_end, 300_000))]
        ls_rows = [{"timestamp": r["timestamp"], "longShortRatio": "1.8"} for r in oi_rows]
        async with pool.acquire() as c:                          # Vision carries the same ratio
            await c.execute("UPDATE beta_hist_oi_5m SET ls_account_ratio = 1.8")
        h0 = _ms(now) - _ms(now) % 3_600_000
        dvol = [[h0 - k * 3_600_000, 50.0, 51.0, 49.0, 50.0] for k in range(1, 72)]
        mid = 60000.0
        book = {"T": _ms(now), "bids": [[str(mid - 1 - k), "1"] for k in range(1000)],
                "asks": [[str(mid + 1 + k), "1"] for k in range(1000)]}
        spot = [[t, "60000", "60010", "59990", "60000", "1", t + 299_999, "60000", 10, "0.5", "30000", "0"]
                for t in range(t_end - 3 * 86_400_000, t_end, 300_000)]
        fetch, calls = fake_public_api(now, oi_rows=oi_rows, ls_rows=ls_rows, dvol=dvol, book=book, spot=spot)
        rep = await run_feeds_job(store, now=now, fetch=fetch, pause=lambda s: asyncio.sleep(0))
        assert not rep["errors"], rep["errors"]
        assert rep["definition_check"]["oi_base"]["status"] == "OK"
        assert rep["definition_check"]["ls_account_ratio"]["status"] == "OK"
        assert rep["depth"] == "COVERED"                         # 1000 levels $1 apart reach about 1.7 %
        n = {t: (await _rows(pool, f"SELECT count(*) AS n FROM {t}"))[0]["n"]
             for t in ("beta_feed_metrics_5m", "beta_feed_dvol_1h", "beta_feed_depth", "beta_feed_spot_5m")}
        assert all(v > 0 for v in n.values()), n
        assert all("api_key" not in json.dumps(p).lower() for _u, p in calls)

        # a stress hour: the perp 1h range reaches the frozen cut; trades of both venues
        hour = h0 - 3_600_000
        k1h = [[hour, "60000", "61500", "60000", "61000", "1", hour + 3_599_999]]
        rng = np.random.default_rng(1)
        ts = np.sort(rng.integers(hour, hour + 3_600_000, 400))
        perp = [{"a": k, "p": str(60000 + k), "q": "20" if k % 50 == 0 else "0.1", "T": int(t)} for k, t in enumerate(ts)]
        spt = [{"a": k, "p": str(60001 + k), "q": "0.1", "T": int(t)} for k, t in enumerate(ts)]
        fetch2, _ = fake_public_api(now, oi_rows=[], ls_rows=[], dvol=[], book=book, spot=[], k1h=k1h,
                                    perp_trades=perp, spot_trades=spt)
        srep = await run_stress_job(store, now=now, fetch=fetch2, pause=lambda s: asyncio.sleep(0))
        assert srep["stress"] == 1
        row = (await _rows(pool, "SELECT status, n_large_perp, lead_score FROM beta_feed_stress_hours"))[0]
        assert row["status"] == "OK" and row["n_large_perp"] == 8 and row["lead_score"] is not None

        # the decision block carries the evidence, and its numbers do not depend on it
        on = await _block(store, CFG, now)
        off_cfg = CFG.with_overrides(decision={**CFG.section("decision"),
                                               "research_evidence": {**CFG.section("decision")["research_evidence"],
                                                                     "enabled": False}})
        off = await _block(store, off_cfg, now)
        assert on["available"] and off["available"]
        ev = on["evidence"]
        assert ev and not ev.get("error_type"), ev
        assert "evidence" not in off or off["evidence"] is None
        for key in ("corridor", "levels", "price", "events", "analogues"):
            assert on[key] == off[key], key
        assert {u["finding_id"] for u in ev["unavailable"]}.isdisjoint({m["finding_id"] for m in ev["matches"]})
        # one snapshot, taken after the last full hour: no book state at that hour, and no 7-day median
        assert {"DH3-L1", "DH3-L2"} <= {u["finding_id"] for u in ev["unavailable"]}
        matched = {m["finding_id"] for m in ev["matches"]}
        assert "DH3-S1" in matched and "DH3-S3" not in matched         # 8 prints of $1M+ <= the frozen 35
        await pool.close()

    async def _block(store, cfg, now):
        reset_cache()
        async with store.connect() as conn:
            return await build_decision(conn, cfg, now=now)

    run(body())


def test_btc_shows_at_most_two_research_lines_and_the_research_tab_opens_and_is_recorded():
    from beta.decision import reset_cache
    from beta.history_stats import run_history_build

    async def body():
        reset_cache()
        pool = await fresh_pool()
        store = BetaStore(pool)
        await _seed(pool)
        await run_history_build(store, CFG, now=DAY + timedelta(hours=2))
        h = _handler(pool, 900000000001, Clock(NOW))
        uid = 900000000111
        async with store.connect() as conn:
            await conn.allowlist_add(uid)
        msg = await _join(h, uid, 10)
        async with store.connect() as conn:
            await conn.mark_privacy_notice_seen(uid, 4)
        out = await h.handle(msg("/btc", 50))
        text = plain(out[-1].html)
        assert text.count("🔬") <= 2
        view = (await _rows(pool, "SELECT view_pk, payload FROM beta_btc_views WHERE kind='btc' "
                                  "ORDER BY view_pk DESC LIMIT 1"))[0]
        payload = json.loads(view["payload"]) if isinstance(view["payload"], str) else view["payload"]
        ev = payload["decision"]["evidence"]
        assert ev and not ev.get("error_type") and ev["version"] == "BETA_RESEARCH_EVIDENCE_V1"
        btn = [b for row in out[-1].buttons for b in row if b[1].endswith(":research")]
        assert btn == [("🔬 Исследования", f"o:{view['view_pk']}:research")]
        cb = {"update_id": 60, "callback_query": {"id": "c60", "from": {"id": uid},
                                                 "message": {"chat": {"id": uid}, "message_id": 1},
                                                 "data": btn[0][1]}}
        res = await h.handle(cb)
        tab = plain(res[-1].html)
        assert tab.startswith("Исследования к рынку сейчас") and "Все проверки: /research" in tab
        assert "Не проверить сейчас" in tab                       # no feeds in this database: listed, no conclusion
        acts = await _rows(pool, "SELECT action FROM beta_user_activity WHERE action='tab_research'")
        assert len(acts) == 1
        opens = await _rows(pool, "SELECT tab FROM beta_details_opens")
        assert {"tab": "research"} in opens
        await pool.close()
    run(body())


def test_stress_job_failure_is_isolated_and_recorded_on_health():
    """A failing aggTrades response leaves the stress hour INCOMPLETE (retried later) and health says
    PARTIAL; a failing 1h klines request records the failure on health and then fails the unit."""
    from beta.research_feeds import FAPI, run_stress_job

    async def body():
        pool = await fresh_pool()
        store = BetaStore(pool)
        now = NOW
        h0 = _ms(now) - _ms(now) % 3_600_000
        hour = h0 - 3_600_000
        k1h = [[hour, "60000", "61500", "60000", "61000", "1", hour + 3_599_999]]

        async def agg_fails(url, params):
            if url == FAPI + "/fapi/v1/klines":
                return k1h
            raise ValueError("unexpected JSON body")
        rep = await run_stress_job(store, now=now, fetch=agg_fails, pause=lambda s: asyncio.sleep(0))
        assert rep["status"] == "PARTIAL" and rep["incomplete"] == 1 and rep["errors"].startswith("ValueError")
        rows = await _rows(pool, "SELECT status FROM beta_feed_stress_hours")
        assert [r["status"] for r in rows] == ["INCOMPLETE"]
        hl = (await _rows(pool, "SELECT last_success_at, last_error_type FROM beta_runtime_health "
                                "WHERE component='research_stress_hours'"))[0]
        assert hl["last_success_at"] is None and hl["last_error_type"] == "ValueError"

        async def k1h_fails(url, params):
            raise TimeoutError("read timeout")
        with pytest.raises(TimeoutError):
            await run_stress_job(store, now=now + timedelta(minutes=5), fetch=k1h_fails,
                                 pause=lambda s: asyncio.sleep(0))
        hl = (await _rows(pool, "SELECT last_run_at, last_success_at, last_error_type FROM beta_runtime_health "
                                "WHERE component='research_stress_hours'"))[0]
        assert hl["last_success_at"] is None and hl["last_error_type"] == "TimeoutError"
        assert hl["last_run_at"] == now + timedelta(minutes=5)
        assert [r["status"] for r in await _rows(pool, "SELECT status FROM beta_feed_stress_hours")] == ["INCOMPLETE"]
        await pool.close()
    run(body())
