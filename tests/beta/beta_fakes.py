"""Shared offline fakes for beta V0.2 tests. No network, no exchange call, no Telegram.

`ScenarioReader` feeds the REAL Stage-2 exchange-feature/consensus pipeline
(via beta.state_tape.materialize_bucket) with synthetic raw bundles whose shape
is controlled per bucket, so beta tests exercise the reused Stage-2 math
unchanged. PostgreSQL integration tests use a local throwaway database named by
$BETA_TEST_DSN and are skipped when it is unset.
"""
from __future__ import annotations

import asyncio
import json
import os
import random
from datetime import datetime, timedelta, timezone
from types import MappingProxyType

from beta.config import BetaConfig, BetaSwitches
from common.stage2_config import Stage2Config
from storage.stage2_readers import ExchangeFeatureRawBundle

S2 = Stage2Config.load()
CFG = BetaConfig.load().with_overrides(enabled=True)
SYM, MT = "BTCUSDT", "perp"
EXS = ("binance", "bybit", "okx")
COV = {"binance": "snapshot", "bybit": "full", "okx": "aggregated"}
FEATURE_CODE = "feature-code-test"
BETA_CODE = "beta-code-test"
ON = BetaSwitches(enabled=True, detection=True, push_hard=False, outcome_tracking=True)
ON_PUSH = BetaSwitches(enabled=True, detection=True, push_hard=True, outcome_tracking=True)
BUCKET = timedelta(minutes=5)
T0 = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)


def run(coro):
    return asyncio.run(coro)


def _m(**kw):
    return MappingProxyType(dict(kw))


def bundle(ex, bucket, *, price_move=0.0, range_pct=0.2, oi_change=0.0, volume=10.0,
           taker_buy=0.5, taker_sell=0.5, liq_long=0.0, liq_short=0.0, base=100.0,
           n_bars=5, price_bias=0.0):
    """One venue's raw bundle for `bucket`. price_move / oi_change in percent."""
    start = base * (1 + price_bias / 100)
    end = start * (1 + price_move / 100)
    kl = []
    for i in range(n_bars):
        o = start + (end - start) * i / 5
        c = start + (end - start) * (i + 1) / 5
        hi = max(o, c) * (1 + range_pct / 200)
        lo = min(o, c) * (1 - range_pct / 200)
        kl.append(_m(exchange=ex, symbol=SYM, ts=bucket + timedelta(minutes=i), open=o, high=hi,
                     low=lo, close=c, volume=volume, taker_buy_volume=taker_buy,
                     taker_sell_volume=taker_sell))
    oi0 = 1000.0
    oi = (_m(exchange=ex, symbol=SYM, ts=bucket, oi_raw=oi0, oi_unit="base"),
          _m(exchange=ex, symbol=SYM, ts=bucket + timedelta(minutes=4),
             oi_raw=oi0 * (1 + oi_change / 100), oi_unit="base"))
    liqs = []
    if liq_long:
        liqs.append(_m(id=1, exchange=ex, symbol=SYM, ts=bucket + timedelta(minutes=1), side="long",
                       notional=float(liq_long), is_snapshot_feed=(COV[ex] == "snapshot")))
    if liq_short:
        liqs.append(_m(id=2, exchange=ex, symbol=SYM, ts=bucket + timedelta(minutes=2), side="short",
                       notional=float(liq_short), is_snapshot_feed=(COV[ex] == "snapshot")))
    return ExchangeFeatureRawBundle(
        klines=tuple(kl), open_interest=oi,
        latest_funding=_m(exchange=ex, symbol=SYM, ts=bucket - timedelta(minutes=1), funding_rate=0.0001),
        liquidations=tuple(liqs),
        instrument=_m(exchange=ex, symbol=SYM, market_type=MT, exchange_instrument_id="BTCUSDT",
                      quantity_unit="base", contract_multiplier=None, tick_size=0.1,
                      price_precision=None, quantity_precision=None, metadata_source="exchange_api",
                      fetched_at=T0 - timedelta(days=60), is_stale=False, note=None),
        liquidation_capability=_m(exchange=ex, symbol=SYM, market_type=MT, metric="liquidations",
                                  live_supported=True, historical_supported=False,
                                  coverage_type=COV[ex], expected_freshness_s=None, enabled=True))


class ScenarioReader:
    """scenario(bucket) -> {exchange: kwargs-for-bundle | 'FAIL'}; default = quiet market."""

    def __init__(self, scenario=None):
        self.scenario = scenario or (lambda b: {})
        self.calls = []

    async def fetch_exchange_feature_raw_bundle(self, *, exchange, symbol, market_type,
                                                bucket_start, bucket_end):
        self.calls.append((exchange, bucket_start))
        spec = self.scenario(bucket_start).get(exchange, {})
        if spec == "FAIL":
            raise RuntimeError("synthetic venue failure")
        # With an unavailable/unhealthy liquidation feed the raw bundle must carry no events.
        return bundle(exchange, bucket_start, **spec)


# ---- quiet / extreme scenarios --------------------------------------------------
def quiet(b):
    return {ex: {} for ex in EXS}


def down_move(b):
    return {ex: {"price_move": -2.0, "oi_change": -3.0} for ex in EXS}


# ---- metrics history -------------------------------------------------------------------
def history_metrics(rng: random.Random) -> dict:
    """Typical-bucket metric values: the extreme scenarios rank at the tails."""
    m = {"c:price_move_pct_median": rng.uniform(-0.1, 0.1),
         "c:oi_change_pct_median": rng.uniform(-0.1, 0.1),
         "c:range_width_pct_median": rng.uniform(0.1, 0.4),
         "c:volume_notional_usd_sum": rng.uniform(2000.0, 4000.0),
         "c:taker_delta_notional_usd_sum": rng.uniform(-50.0, 50.0),
         "c:funding_rate_median": 0.0001, "c:price_direction_agreement": 0.5,
         "c:oi_direction_agreement": 0.5}
    for ex in EXS:
        m[f"x:{ex}:long_liquidation_notional"] = 0.0
        m[f"x:{ex}:short_liquidation_notional"] = 0.0
    return m


def history_buckets(first_eval: datetime, n_eval: int) -> list:
    """Contiguous 5m history covering [first_eval-30d, first_eval-30d + n_eval*5m] (so
    every evaluated bucket has its exact B-30d sample => 'mature') + hourly elsewhere."""
    start = first_eval - timedelta(days=30)
    dense = [start + i * BUCKET for i in range(n_eval + 2)]
    sparse = [start + timedelta(hours=h) for h in range(1, 30 * 24)]
    return sorted(set(dense) | {b for b in sparse if b < first_eval})


# ---- PostgreSQL ---------------------------------------------------------------------------
TEST_DSN = os.environ.get("BETA_TEST_DSN")

STAGE1_MIN_SQL = """
CREATE TABLE IF NOT EXISTS klines_1m (exchange TEXT NOT NULL, symbol TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL, open DOUBLE PRECISION, high DOUBLE PRECISION NOT NULL,
    low DOUBLE PRECISION NOT NULL, close DOUBLE PRECISION NOT NULL, volume DOUBLE PRECISION,
    taker_buy_volume DOUBLE PRECISION,
    source TEXT NOT NULL DEFAULT 'backfill', PRIMARY KEY (exchange, symbol, ts));
CREATE TABLE IF NOT EXISTS liquidations (id BIGSERIAL, exchange TEXT NOT NULL, symbol TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL, side TEXT NOT NULL, price DOUBLE PRECISION NOT NULL,
    qty DOUBLE PRECISION NOT NULL, notional DOUBLE PRECISION,
    is_snapshot_feed BOOLEAN NOT NULL DEFAULT FALSE, mapping_version SMALLINT, PRIMARY KEY (id, ts));
CREATE TABLE IF NOT EXISTS connectivity_events (id BIGSERIAL PRIMARY KEY, exchange TEXT NOT NULL,
    event_type TEXT NOT NULL, ts TIMESTAMPTZ NOT NULL DEFAULT now(), detail JSONB);
CREATE TABLE IF NOT EXISTS open_interest (
    exchange TEXT NOT NULL, symbol TEXT NOT NULL, ts TIMESTAMPTZ NOT NULL,
    oi_raw DOUBLE PRECISION, oi_unit TEXT, contract_value DOUBLE PRECISION,
    PRIMARY KEY (exchange, symbol, ts));
CREATE TABLE IF NOT EXISTS backfill_runs (
    id BIGSERIAL PRIMARY KEY, exchange TEXT NOT NULL, symbol TEXT NOT NULL, source TEXT NOT NULL,
    window_start TIMESTAMPTZ NOT NULL, window_end TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'running', rows_written INTEGER NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(), finished_at TIMESTAMPTZ, note TEXT);
"""


# A row the FIXED collector wrote (liquidations.mapping_version = 2) for Bybit and OKX, long before
# any test window: the default test world runs after the collector fix, where Bybit sides are read
# as stored and OKX liquidations are measured (docs/BETA_DATA_RELIABILITY_FIX_PLAN_V1.md D2).
# `fresh_pool(collector_fixed=False)` is the world before the fix.
FIXED_COLLECTOR_ROWS_SQL = """
INSERT INTO liquidations (exchange, symbol, ts, side, price, qty, notional, is_snapshot_feed, mapping_version)
VALUES ('bybit', 'BTCUSDT', '2020-01-01T00:00:00Z', 'long', 1, 0, 0, FALSE, 2),
       ('okx', 'BTCUSDT', '2020-01-01T00:00:00Z', 'long', 1, 0, 0, FALSE, 2)
"""


async def fresh_pool(*, collector_fixed: bool = True):
    import asyncpg
    from storage.beta_v0_store import apply_beta_schema
    admin = await asyncpg.connect(TEST_DSN)
    try:
        await admin.execute("DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;")
    finally:
        await admin.close()
    pool = await asyncpg.create_pool(TEST_DSN, min_size=1, max_size=6)
    async with pool.acquire() as c:
        await c.execute(STAGE1_MIN_SQL)
        await apply_beta_schema(c)
        if collector_fixed:
            await c.execute(FIXED_COLLECTOR_ROWS_SQL)
    return pool


async def seed_history(pool, *, calculation_version: str, buckets, metrics_fn):
    rows = []
    for i, b in enumerate(buckets):
        m = metrics_fn(b)
        rows.append((b, calculation_version, json.dumps(m), f"{i:064x}", f"{i + 10**6:064x}"))
    async with pool.acquire() as c:
        await c.executemany(
            """INSERT INTO beta_state_tape (symbol, market_type, timeframe, bucket_ts, calculation_version,
                   state_schema_version, rules_version, rules_digest, revision, origin, materialized,
                   evaluation_fresh, code_version, config_digest, raw_revision, evaluated_at, metrics,
                   snapshot, feature_digest, snapshot_digest)
               VALUES ('BTCUSDT','perp','5m',$1,$2,1,'BETA_EVENT_RULES_V1',repeat('a',64),1,'BOOTSTRAP',
                       TRUE,FALSE,'seed',repeat('b',64),0,$1,$3::jsonb,'{}'::jsonb,$4,$5)""", rows)


async def seed_live_klines(pool, buckets, *, exchanges=EXS, price=100.0, source="live"):
    rows = []
    for b in buckets:
        for i in range(5):
            for ex in exchanges:
                rows.append((ex, SYM, b + timedelta(minutes=i), price, price * 1.001, price * 0.999,
                             price, 1.0, source))
    async with pool.acquire() as c:
        await c.executemany(
            "INSERT INTO klines_1m (exchange, symbol, ts, open, high, low, close, volume, source) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) ON CONFLICT DO NOTHING", rows)


class Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


def deps(pool, reader, clock, *, declared=None, raw_revision=0, feature_code=FEATURE_CODE,
         code=BETA_CODE, host_boot_time=None):
    from beta.detector import DetectorDeps
    from storage.beta_v0_store import BetaStore
    declared = declared or {ex: True for ex in EXS}

    async def _declared(exchanges):
        return {ex: declared.get(ex, False) for ex in exchanges}

    async def _raw():
        return raw_revision() if callable(raw_revision) else raw_revision

    return DetectorDeps(reader=reader, store=BetaStore(pool), stage2_config=S2,
                        declared_liquidation_available=_declared, raw_revision=_raw, clock=clock,
                        code_version=code, feature_code_version=feature_code,
                        host_boot_time=host_boot_time)
