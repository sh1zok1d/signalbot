"""The external review of #346 + #348 on real PostgreSQL ($BETA_TEST_DSN): the /btc and briefing block built on a
fresh Binance tape with the live corridor record from `forecast_accuracy`, and stale statistics that keep the
personal price alerts working and say why on /alert and /risk."""
from datetime import timedelta

import pytest

from beta_fakes import CFG, TEST_DSN, Clock, fresh_pool, run
from storage.beta_v0_store import BetaStore
from test_beta_v2_pg import DAY, NOW, _handler, _join, _rows, _seed, plain

pytestmark = pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)")


async def _built(pool):
    from beta.decision import reset_cache
    from beta.history_stats import run_history_build
    reset_cache()
    seed = await _seed(pool)
    rep = await run_history_build(BetaStore(pool), CFG, now=DAY + timedelta(hours=2))
    assert rep["status"] == "OK"
    return seed


def test_the_btc_and_briefing_block_on_a_fresh_tape_with_the_live_record():
    """Check (f): the block /btc and the briefing print, built from real statistics, a fresh Binance tail and
    40 scored 1h forecasts (N_EFF 40 ≥ 30: the live share replaces the held-out one)."""
    from beta import decision_format as df
    from beta.decision import build_decision
    from beta.rangecast import HORIZONS, typical_move_at

    async def body():
        pool = await fresh_pool()
        await _built(pool)
        async with pool.acquire() as c:
            for k in range(40):
                at = NOW - timedelta(hours=2 + k)
                await c.execute(
                    "INSERT INTO beta_forecasts (horizon, issued_at, horizon_end, anchor_price, lower, upper, coverage,"
                    " model_version, outcome, evaluated_at) VALUES ('1h', $1, $2, 100, 99, 101, 0.8, 'm', $3, $2)",
                    at, at + timedelta(hours=1), "INSIDE" if k < 30 else "OUTSIDE")
        cap: dict = {}
        async with BetaStore(pool).connect() as conn:
            block = await build_decision(conn, CFG, now=NOW, capture=cap)
        assert block["available"] is True
        c = block["corridor"]
        assert c["live"]["1h"] == {"INSIDE": 30, "OUTSIDE": 10, "N_EFF": 40}
        # NOW is a CPI day: 24h is inside its event zone, 1h and 4h are shown
        assert set(c["horizons"]) == {"1h", "4h"} and set(c["history_days"]) == {"1h", "4h"}
        model, b = cap["model"], cap["bars"]
        assert c["history_days"]["1h"] == int(model["horizons"]["1h"]["n_days"]) > 0
        i = b.last_complete_index()
        assert c["window_typical"]["1h"] == pytest.approx(typical_move_at(model, b, i - HORIZONS["1h"], "1h", events=cap["events"]))
        assert "24h" not in c["window_typical"]                     # inside its event zone: no «обычно»
        lines = df.btc_lines({"decision": block}, "ru")
        assert lines[0].startswith("Коридор: 1ч ") and " · 4ч " in lines[0] and "24ч" not in lines[0]
        assert lines[1].startswith("24ч: числовую оценку не показываем — CPI США (инфляция)")
        assert lines[2].startswith("↳ внутри коридора бывало (расчёт — 80%): 1ч 75% вживую за 30 дн. (N=40)")
        assert any(x.startswith("↑ ") and " · за 4ч " in x for x in lines)
        assert "События в ближайшие сутки: 15:30 CPI США (инфляция)" in lines
        brief = df.brief_lines({"decision": block}, "ru")
        assert any(x.startswith("Коридор: 4ч ") for x in brief) and any(x.startswith("Уровни: ↑ ") for x in brief)
        await pool.close()
    run(body())


def test_stale_statistics_keep_price_alerts_and_say_why_on_alert_and_risk():
    """Finding 3: statistics older than 72h close every number of the history, never the tape. A personal
    price alert still fires on its touch; /alert sets one and says why there is no chance; /risk says why
    instead of its usage text."""
    from beta.decision import build_decision, reset_cache
    from beta.market_alerts import run_market_alerts

    async def body():
        pool = await fresh_pool()
        seed = await _built(pool)
        async with pool.acquire() as c:
            await c.execute("UPDATE beta_hist_stats SET built_at = $1", NOW - timedelta(days=4))
        reset_cache()
        uid = 900000000444
        h = _handler(pool, 900000000001, Clock(NOW))
        async with BetaStore(pool).connect() as conn:
            await conn.allowlist_add(uid)
        msg = await _join(h, uid, 10)
        async with BetaStore(pool).connect() as conn:
            await conn.mark_privacy_notice_seen(uid, 99)
            block = await build_decision(conn, CFG, now=NOW)
            assert block["available"] is False and block["reason"] == "STATS_STALE"
            assert block["price"] == pytest.approx(seed["base"]) and "corridor" not in block and "levels" not in block
            user = await conn.get_user(uid)
            # set before the touch at minute 357 of the day's tail (the seeded high of yesterday + 5)
            await conn.add_price_alert(user_pk=user["user_pk"], price=seed["pdh"], created_price=seed["base"],
                                       now=DAY + timedelta(hours=5), max_active=5)
        out = plain((await h.handle(msg("/alert %d" % round(seed["base"] * 1.02), 100)))[-1].html)
        assert out.startswith("Сообщу, когда BTC дойдёт до ") and "статистика по истории не обновлялась" in out
        assert "недоступна" not in out
        out = plain((await h.handle(msg("/risk 61500", 101)))[-1].html)
        assert out.startswith("Коридор и уровни сейчас не показываем") and "больше 3 суток" in out
        async with BetaStore(pool).connect() as conn:
            rep = await run_market_alerts(conn, CFG, sender=None, clock=Clock(NOW), push_on=True)
        assert rep["detected"] >= 1
        kinds = [r["kind"] for r in await _rows(pool, "SELECT kind FROM beta_market_alerts")]
        assert kinds == ["price"]                               # no level touch or move: they need the history
        await pool.close()
    run(body())
