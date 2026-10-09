"""Data reliability D2 on real PostgreSQL ($BETA_TEST_DSN): tape history and raw rows written before
the collector fix (docs/BETA_DATA_RELIABILITY_FIX_PLAN_V1.md R1, R2) are read honestly through the
live detector. OKX's false zeros never let OKX vote; Bybit's swapped sides are ranked against their
own side; the LIQ clusters read the corrected sides. Synthetic data only."""
import random
from datetime import timedelta

import pytest

from beta_fakes import BUCKET, EXS, TEST_DSN, ScenarioReader, fresh_pool, history_buckets, history_metrics, \
    run, seed_history, seed_live_klines
from storage.beta_v0_store import BetaStore

pytestmark = pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)")


@pytest.fixture(autouse=True)
def _calc():
    import test_beta_pg_integration as pgi
    pgi.CALC = pgi.calc_version()


async def _pool(history_fn, liquidation_rows):
    """History seeded BEFORE the fix (no marker on any row), then the raw rows that tell the cutover."""
    import test_beta_pg_integration as pgi
    pool = await fresh_pool(collector_fixed=False)
    rng = random.Random(7)
    await seed_history(pool, calculation_version=pgi.CALC, buckets=history_buckets(pgi.B0, 8),
                       metrics_fn=lambda b: history_fn(history_metrics(rng)))
    await seed_live_klines(pool, [pgi.B0 + i * BUCKET for i in range(8)])
    async with pool.acquire() as c:
        await c.executemany(
            """INSERT INTO liquidations (exchange, symbol, ts, side, price, qty, notional, is_snapshot_feed,
                   mapping_version) VALUES ($1, 'BTCUSDT', $2, $3, 60000, 0.01, 600, FALSE, $4)""",
            liquidation_rows)
    return pool


async def _heartbeats(pool, exchange, start, end, every_s=60):
    """The collector's liveness rows for a channel alive over [start, end]."""
    rows, t = [], start
    while t <= end:
        rows.append((exchange, "BTCUSDT", t))
        t += timedelta(seconds=every_s)
    async with pool.acquire() as c:
        await c.executemany("INSERT INTO liquidation_feed_heartbeats (exchange, symbol, ts) VALUES ($1,$2,$3)", rows)


def _liq(r):
    p = r["processed"][0]
    return p["evaluations"]["LIQUIDATION_STRESS_LONG"]


def test_okx_false_zero_history_never_lets_okx_vote():
    """Review of #374, point 1: 30 days of stored OKX zeros gave ANY real OKX liquidation rank 1.0, so
    «Binance in the tail + any OKX row» qualified instead of «Binance and Bybit together»."""
    import test_beta_pg_integration as pgi
    b0 = pgi.B0
    fixed = b0 - timedelta(hours=1)                   # the collector restarted an hour before B0
    rows = [("bybit", b0 - timedelta(hours=2), "short", None), ("bybit", fixed, "long", 2),
            ("okx", fixed, "long", 2)]

    async def body():
        pool = await _pool(lambda m: m, rows)
        await _heartbeats(pool, "okx", fixed, b0 + BUCKET)              # the OKX channel was alive
        scenario = ScenarioReader(lambda b: {"binance": {"liq_long": 5000.0}, "bybit": {"liq_long": 0.0},
                                             "okx": {"liq_long": 500.0}})
        r = await pgi._detect(pool, scenario, b0)
        assert _liq(r) == "NOT_QUALIFIES"
        detail = (await pgi._rows(pool, "SELECT snapshot FROM beta_state_tape WHERE origin='LIVE'"))[0]["snapshot"]
        import json
        snap = json.loads(detail) if isinstance(detail, str) else detail
        ev = snap["rule_evaluations"]["LIQUIDATION_STRESS_LONG"]["detail"]
        # «k из n»: OKX is out of the denominator until it has 30 days of real history
        assert ev["eligible"] == ["binance", "bybit"] and ev["voting"] == ["binance"]
        assert ev["ineligible"]["okx"] == "OKX_LIQUIDATIONS_EXCLUDED"                 # decision (d), flag off
        assert snap["metrics"]["x:okx:long_liquidation_notional"] == 500.0          # measured since the fix
        assert snap["venues"]["okx"]["liq_mapping"] == "NEW" and snap["metrics"]["liq_mapping_version"] == 2.0
        await pool.close()
    run(body())


def test_bybit_sides_are_ranked_against_their_own_side_of_the_old_history():
    """Review of #374, point 2: before the fix every Bybit long was stored as a short. A real long now
    must be ranked against the old shorts (the real longs), not against the old longs."""
    import test_beta_pg_integration as pgi
    b0 = pgi.B0
    fixed = b0 - timedelta(hours=1)
    rows = [("bybit", b0 - timedelta(hours=2), "short", None), ("bybit", fixed, "long", 2),
            ("okx", fixed, "long", 2)]

    def stored_swapped(m):
        # real longs were large and stored under «short»; real shorts were zero and stored under «long»
        m["x:bybit:long_liquidation_notional"] = 0.0
        m["x:bybit:short_liquidation_notional"] = 50000.0
        return m

    async def body():
        pool = await _pool(stored_swapped, rows)
        scenario = ScenarioReader(lambda b: {"binance": {"liq_long": 5000.0}, "bybit": {"liq_long": 5000.0}})
        r = await pgi._detect(pool, scenario, b0)
        # read honestly, the history of real longs is 50 000 per bucket: 5 000 is not in the tail
        assert _liq(r) == "NOT_QUALIFIES"
        async with BetaStore(pool).connect() as conn:
            hist = await conn.fetch_tape_history(
                symbol="BTCUSDT", market_type="perp", timeframe="5m", calculation_version=pgi.CALC,
                state_schema_versions=(1, 2), start=b0 - timedelta(days=30), end=b0)
        old = [m for b, m in hist if b + BUCKET <= b0 - timedelta(hours=2)]          # before the last old row
        assert old and {m["x:bybit:long_liquidation_notional"] for m in old} == {50000.0}
        assert {m["x:bybit:short_liquidation_notional"] for m in old} == {0.0}
        assert {m["x:okx:long_liquidation_notional"] for m in old} == {None}         # never measured
        new = [m for b, m in hist if b > b0 - timedelta(hours=1)]                      # after the fix: as stored
        assert all(m["x:bybit:long_liquidation_notional"] == 0.0 for m in new)
        await pool.close()
    run(body())


def test_the_liquidation_clusters_read_old_bybit_rows_with_their_side_swapped():
    """Review of #374, point 3: the 24h LIQ_LONG / LIQ_SHORT clusters read raw rows."""
    import test_beta_pg_integration as pgi
    b0 = pgi.B0

    async def body():
        pool = await _pool(lambda m: m, [("bybit", b0 - timedelta(hours=3), "short", None),
                                         ("bybit", b0 - timedelta(hours=1), "short", 2),
                                         ("binance", b0 - timedelta(hours=2), "short", None)])
        async with BetaStore(pool).connect() as conn:
            got = await conn.fetch_liquidations(symbol="BTCUSDT", exchanges=["binance", "bybit"],
                                                start=b0 - timedelta(days=1), end=b0)
        assert sorted((r["exchange"], r["side"], r["mapping_version"]) for r in got) == [
            ("binance", "short", None), ("bybit", "long", None), ("bybit", "short", 2)]
        await pool.close()
    run(body())


def test_before_the_collector_restarts_old_bybit_buckets_are_swapped_and_okx_is_not_measured():
    """D2 deployed before the collector restart: every Bybit bucket is old-mapping (read swapped) and
    OKX has no fixed row (not measured, never READY)."""
    import test_beta_pg_integration as pgi
    b0 = pgi.B0

    async def body():
        pool = await _pool(lambda m: m, [("bybit", b0 + timedelta(minutes=1), "short", None)])
        scenario = ScenarioReader(lambda b: {ex: {"liq_short": 700.0} for ex in EXS})
        await pgi._detect(pool, scenario, b0)
        import json
        raw = (await pgi._rows(pool, "SELECT snapshot FROM beta_state_tape WHERE origin='LIVE'"))[0]["snapshot"]
        snap = json.loads(raw) if isinstance(raw, str) else raw
        m = snap["metrics"]
        assert (m["x:bybit:long_liquidation_notional"], m["x:bybit:short_liquidation_notional"]) == (700.0, 0.0)
        assert m["x:okx:long_liquidation_notional"] is None and m["x:okx:short_liquidation_notional"] is None
        assert (m["x:binance:long_liquidation_notional"], m["x:binance:short_liquidation_notional"]) == (0.0, 700.0)
        assert snap["venues"]["bybit"]["liq_mapping"] == "OLD" and snap["venues"]["okx"]["liq_mapping"] == "UNPROVEN"
        await pool.close()
    run(body())


def test_reapplying_the_beta_schema_never_waits_on_the_collectors_liquidations_table():
    """Review of #378 (HIGH): the beta applies its schema every few minutes. It must take no lock on the
    collector's `liquidations` hypertable, or a reader there (the nightly pg_dump) would stall the
    collector's inserts behind it."""
    import asyncpg
    from storage.beta_v0_store import BETA_SCHEMA_PATH, apply_beta_schema
    assert "liquidations" not in BETA_SCHEMA_PATH.read_text()

    async def body():
        pool = await fresh_pool()
        holder = await asyncpg.connect(TEST_DSN)
        other = await asyncpg.connect(TEST_DSN)
        try:
            await holder.execute("BEGIN; LOCK TABLE liquidations IN ROW EXCLUSIVE MODE")   # a writer mid-insert
            await other.execute("SET lock_timeout = '500ms'")
            await apply_beta_schema(other)                 # would time out behind ALTER / CREATE INDEX
        finally:
            await holder.execute("ROLLBACK")
            await holder.close()
            await other.close()
            await pool.close()
    run(body())


def test_before_the_collector_adds_the_column_the_beta_reads_every_row_as_old():
    """The deploy restarts the collector first; if the beta runs before it, `mapping_version` does not
    exist yet: every Bybit row is old (swapped) and OKX is not measured, without an error."""
    import test_beta_pg_integration as pgi
    b0 = pgi.B0

    async def body():
        pool = await fresh_pool(collector_fixed=False)
        async with pool.acquire() as c:
            await c.execute("ALTER TABLE liquidations DROP COLUMN mapping_version")
            await c.execute("""INSERT INTO liquidations (exchange, symbol, ts, side, price, qty, notional)
                               VALUES ('bybit', 'BTCUSDT', $1, 'short', 60000, 0.01, 600)""", b0 - timedelta(hours=1))
        async with BetaStore(pool).connect() as conn:
            cut = await conn.fetch_liquidation_cutover(symbol="BTCUSDT")
            rows = await conn.fetch_liquidations(symbol="BTCUSDT", exchanges=["bybit"],
                                                 start=b0 - timedelta(days=1), end=b0)
        assert cut == {"bybit": {"first_new": None, "last_old": None}, "okx": {"first_new": None, "last_old": None}}
        assert [(r["side"], r["mapping_version"]) for r in rows] == [("long", None)]
        await pool.close()
    run(body())


def test_okx_without_a_fresh_liveness_marker_is_not_measured_and_never_a_zero():
    """Architect, 2026-10-08: a quiet OKX bucket is a measured 0 only while its liquidation channel is
    alive. A refused or silent channel leaves no heartbeat: OKX reads «не измерен» (None), not 0, at
    tape time and in history, and never joins the vote."""
    import json
    import test_beta_pg_integration as pgi
    b0 = pgi.B0
    fixed = b0 - timedelta(hours=1)
    rows = [("bybit", b0 - timedelta(hours=2), "short", None), ("bybit", fixed, "long", 2), ("okx", fixed, "long", 2)]

    async def body():
        pool = await _pool(lambda m: m, rows)
        # heartbeats stop 4 minutes before B0 + 5m: the bucket has a gap over 150 s
        alive_from = fixed - timedelta(minutes=10)
        await _heartbeats(pool, "okx", alive_from, b0 + timedelta(minutes=1))
        scenario = ScenarioReader(lambda b: {"binance": {"liq_long": 5000.0}, "okx": {"liq_long": 0.0}})
        await pgi._detect(pool, scenario, b0)
        raw = (await pgi._rows(pool, "SELECT snapshot FROM beta_state_tape WHERE origin='LIVE'"))[0]["snapshot"]
        snap = json.loads(raw) if isinstance(raw, str) else raw
        assert snap["venues"]["okx"]["liq_mapping"] == "NO_FEED"
        assert snap["metrics"]["x:okx:long_liquidation_notional"] is None          # not a measured 0
        assert "okx" not in snap["rule_evaluations"]["LIQUIDATION_STRESS_LONG"]["detail"]["eligible"]
        # history: an OKX 0.0 in a bucket without heartbeats reads None; one with heartbeats stays 0.0
        async with BetaStore(pool).connect() as conn:
            hist = dict(await conn.fetch_tape_history(
                symbol="BTCUSDT", market_type="perp", timeframe="5m", calculation_version=pgi.CALC,
                state_schema_versions=(1, 2), start=b0 - timedelta(days=30), end=b0))
        covered = [b for b in hist if b - timedelta(seconds=90) >= alive_from and b + BUCKET <= b0 + timedelta(minutes=1)]
        uncovered = [b for b in hist if b + BUCKET < alive_from]
        assert covered and all(hist[b]["x:okx:long_liquidation_notional"] == 0.0 for b in covered)
        assert uncovered and all(hist[b]["x:okx:long_liquidation_notional"] is None for b in uncovered)
        await pool.close()
    run(body())


def test_without_the_heartbeat_table_okx_is_never_measured():
    """Before the collector restart creates the table, nothing proves the OKX channel alive."""
    import test_beta_pg_integration as pgi
    b0 = pgi.B0

    async def body():
        pool = await fresh_pool()
        async with pool.acquire() as c:
            await c.execute("DROP TABLE liquidation_feed_heartbeats")
        async with BetaStore(pool).connect() as conn:
            assert await conn.fetch_liquidation_feed_heartbeats(symbol="BTCUSDT", start=b0, end=b0) == {}
        await pool.close()
    run(body())


def test_the_heartbeat_read_uses_the_primary_key_and_ignores_other_venues():
    """Review of #398: the read filtered symbol + ts only, a seq scan of a table that grows forever.
    It now leads with exchange (the primary key's first column) and reads only OKX."""
    import test_beta_pg_integration as pgi
    b0 = pgi.B0

    async def body():
        pool = await fresh_pool()
        async with pool.acquire() as c:
            await c.executemany("INSERT INTO liquidation_feed_heartbeats VALUES ($1, 'BTCUSDT', $2)",
                                [("okx", b0), ("bybit", b0)])
            await c.execute("SET enable_seqscan = off")
        async with BetaStore(pool).connect() as conn:
            got = await conn.fetch_liquidation_feed_heartbeats(symbol="BTCUSDT", start=b0 - BUCKET, end=b0 + BUCKET)
            plan = "\n".join(r[0] for r in await conn.conn.fetch(
                """EXPLAIN SELECT exchange, ts FROM liquidation_feed_heartbeats
                   WHERE exchange = ANY($4::text[]) AND symbol=$1 AND ts >= $2 AND ts <= $3 ORDER BY ts""",
                "BTCUSDT", b0 - BUCKET, b0 + BUCKET, ["okx"]))
        assert got == {"okx": [b0]}
        assert "Index" in plan
        await pool.close()
    run(body())
