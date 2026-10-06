"""Derivatives beside their «обычно» (backlog G2) on real PostgreSQL ($BETA_TEST_DSN): the nightly OI
statistic reaches the stored view, and the long/short summary reads the research feed when it runs.
Synthetic data only."""
from datetime import timedelta

import pytest

from beta_fakes import CFG, TEST_DSN, fresh_pool, run
from storage.beta_v0_store import BetaStore
from test_beta_v2_pg import DAY, NOW, _seed

pytestmark = pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)")


def test_the_oi_comparator_is_built_nightly_and_long_short_reads_the_feed():
    from beta.decision import reset_cache
    from beta.history_stats import run_history_build

    async def body():
        reset_cache()
        pool = await fresh_pool()
        store = BetaStore(pool)
        await _seed(pool)
        assert (await run_history_build(store, CFG, now=DAY + timedelta(hours=2)))["status"] == "OK"
        async with store.connect() as conn:
            from beta.decision import latest_stats
            oi = (await latest_stats(conn, now=NOW))["derivatives"]["oi_24h"]
            assert oi["source"] == "binance" and oi["n_days"] >= 100 and oi["median_abs_pct"] > 0

            # no feed rows: no long/short line at all
            assert await conn.long_short_summary(as_of=NOW) is None
            rows = []
            for k in range(31 * 288 + 1):
                ts = NOW.replace(second=0) - timedelta(minutes=5 * k)
                ts = ts - timedelta(minutes=ts.minute % 5)
                day = int((NOW - ts).total_seconds() // 86400)
                rows.append((ts, 1.0 + day / 100))
            await conn.conn.executemany(
                """INSERT INTO beta_feed_metrics_5m (ts, ls_account_ratio, source, fetched_at)
                   VALUES ($1,$2,'binance_futures_data',$1) ON CONFLICT DO NOTHING""", rows)
            ls = await conn.long_short_summary(as_of=NOW)
        # the latest value is from the current day; the comparator is the median of days 1..30
        assert ls["ratio"] == 1.0 and ls["n_days"] == 30
        assert abs(ls["typical"] - 1.155) < 0.006
        await pool.close()
    run(body())
