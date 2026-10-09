"""Decision (d), 2026-10-09, on real PostgreSQL ($BETA_TEST_DSN), end to end through the live detector:
with 30 days of real (marked, heartbeat-covered) OKX liquidation history its percentile is MATURE, and
still OKX never votes and is never shown while `liquidations.okx_enabled` is false. The same world with
the flag on would let it vote, so the flag (not immaturity) is what holds. Stage-2 materialization is
untouched: OKX's value is still stored. Synthetic data only."""
import json
import random
from datetime import timedelta

import pytest

from beta_fakes import BUCKET, TEST_DSN, ScenarioReader, fresh_pool, history_buckets, history_metrics, run, \
    seed_history, seed_live_klines

pytestmark = pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)")


@pytest.fixture(autouse=True)
def _calc():
    import test_beta_pg_integration as pgi
    pgi.CALC = pgi.calc_version()


async def _world(cfg):
    import test_beta_pg_integration as pgi
    from beta.liq_mapping import LIQ_MAPPING_KEY
    b0 = pgi.B0
    pool = await fresh_pool()
    rng = random.Random(5)
    buckets = history_buckets(b0, 8)

    def metrics(_b):
        m = history_metrics(rng)
        for ex in ("binance", "bybit", "okx"):          # a real, measured history for every venue
            m[f"x:{ex}:long_liquidation_notional"] = rng.uniform(100.0, 1000.0)
            m[f"x:{ex}:short_liquidation_notional"] = rng.uniform(100.0, 1000.0)
        m[LIQ_MAPPING_KEY] = 2.0                        # written by the fixed collector: never corrected
        return m
    await seed_history(pool, calculation_version=pgi.CALC, buckets=buckets, metrics_fn=metrics)
    await seed_live_klines(pool, [b0 + i * BUCKET for i in range(8)])
    beats = sorted({b + timedelta(seconds=s) for b in buckets + [b0] for s in range(-90, 330, 60)})
    async with pool.acquire() as c:                     # OKX's liquidation channel alive over every bucket
        await c.executemany("INSERT INTO liquidation_feed_heartbeats (exchange, symbol, ts) VALUES ('okx', 'BTCUSDT', $1)",
                            [(t,) for t in beats])
        await c.executemany(
            """INSERT INTO liquidations (exchange, symbol, ts, side, price, qty, notional, is_snapshot_feed,
                   mapping_version) VALUES ($1, 'BTCUSDT', $2, 'long', 60000, 0.01, 600, FALSE, 2)""",
            [(ex, buckets[0] - timedelta(hours=1)) for ex in ("bybit", "okx")])
    scenario = ScenarioReader(lambda b: {"binance": {"liq_long": 9e6}, "bybit": {"liq_long": 500.0},
                                         "okx": {"liq_long": 9e6}})
    r = await pgi._detect(pool, scenario, b0, cfg=cfg)
    raw = (await pgi._rows(pool, "SELECT snapshot FROM beta_state_tape WHERE origin='LIVE'"))[0]["snapshot"]
    await pool.close()
    return r, (json.loads(raw) if isinstance(raw, str) else raw)


def test_mature_okx_never_votes_with_the_flag_off_and_would_with_it_on():
    import test_beta_pg_integration as pgi
    off_r, off = run(_world(pgi.CFG))
    p = off["percentiles"]["x:okx:long_liquidation_notional"]
    assert p["tier"] == "mature" and p["rank"] >= 0.95                 # OKX is mature and in its tail
    assert off["metrics"]["x:okx:long_liquidation_notional"] == 9e6       # Stage 2 still stores it
    ev = off["rule_evaluations"]["LIQUIDATION_STRESS_LONG"]
    assert ev["status"] == "NOT_QUALIFIES" and ev["detail"]["voting"] == ["binance"]
    assert ev["detail"]["ineligible"]["okx"] == "OKX_LIQUIDATIONS_EXCLUDED"
    on_r, on = run(_world(pgi.CFG.with_overrides(liquidations={"okx_enabled": True})))
    ev_on = on["rule_evaluations"]["LIQUIDATION_STRESS_LONG"]
    assert ev_on["status"] == "QUALIFIES" and ev_on["detail"]["voting"] == ["binance", "okx"]
    # Binance and Bybit are measured and ranked identically either way
    for k in ("x:binance:long_liquidation_notional", "x:bybit:long_liquidation_notional"):
        assert off["metrics"][k] == on["metrics"][k] and off["percentiles"][k] == on["percentiles"][k]
