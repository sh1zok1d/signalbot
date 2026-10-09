"""D3 (docs/BETA_DATA_RELIABILITY_FIX_PLAN_V1.md R3): «Funding сейчас» is the median of the venues whose newest
LIVE rate is at most 15 minutes old, from at least two venues, never the tape's unbounded value; the 24h mean
needs the price rule's bucket coverage; the sign-change line needs rates of a printable size; every rate says
«за 8 ч». Synthetic data; the store read is checked on PostgreSQL ($BETA_TEST_DSN)."""
import re
from datetime import timedelta

import pytest

from test_beta_horizons_ohlc_gaps import AS_OF, CFG, EXS, rows
from beta import horizons as hz
from beta.formatter import format_1h_tab, format_24h_tab
from beta.horizons import FUNDING_MAX_AGE, build_horizons, data_through, funding_now, select_changes

END = data_through(AS_OF)


def plain(s):
    return re.sub(r"<[^>]+>", "", s)


def latest(**ages_rates):
    return {ex: None if v is None else {"ts": END - timedelta(minutes=v[0]), "funding_rate": v[1]}
            for ex, v in ages_rates.items()}


def test_a_stale_venue_leaves_the_median_and_one_venue_is_not_a_median():
    f = funding_now(CFG, latest(binance=(1, 0.0001), bybit=(2, 0.0003), okx=(16, 0.009)), END)
    assert f["rate"] == pytest.approx(0.0002) and f["venues"] == 2 and f["by_venue"]["okx"] is None
    edge = funding_now(CFG, latest(binance=(15, 0.0001), bybit=(15, 0.0003), okx=None), END)
    assert edge["venues"] == 2                                          # exactly 15 minutes is still fresh
    one = funding_now(CFG, latest(binance=(1, 0.0001), bybit=(20, 0.0003), okx=(30, 0.0003)), END)
    assert one["rate"] is None and one["venues"] == 1
    assert funding_now(CFG, None, END)["rate"] is None


def test_horizons_never_print_the_tapes_unbounded_funding():
    r = rows(288)                                                       # every bucket carries c:funding_rate_median
    no_rows = build_horizons(CFG, as_of_bucket=AS_OF, metrics_by_bucket=r)
    assert no_rows["24h"]["funding_rate"] is None and no_rows["1h"]["funding_rate"] is None
    stale = build_horizons(CFG, as_of_bucket=AS_OF, metrics_by_bucket=r,
                           funding_latest=latest(binance=(60, 0.0001), bybit=(60, 0.0001), okx=(60, 0.0001)))
    assert stale["24h"]["funding_rate"] is None and stale["24h"]["funding_venues"] == 0
    fresh = build_horizons(CFG, as_of_bucket=AS_OF, metrics_by_bucket=r,
                           funding_latest=latest(binance=(1, 0.0001), bybit=(1, 0.0003), okx=(1, 0.0002)))
    assert fresh["24h"]["funding_rate"] == pytest.approx(0.0002) and fresh["24h"]["funding_venues"] == 3


def test_the_24h_mean_needs_the_price_rules_coverage():
    r = rows(288)
    keep = sorted(r)
    for b in keep[1:7]:                                                 # 6 buckets without funding: 282 left
        r[b] = {**r[b], "c:funding_rate_median": None}
    assert build_horizons(CFG, as_of_bucket=AS_OF, metrics_by_bucket=r)["24h"]["funding_rate_avg"] == pytest.approx(0.0001)
    r[keep[7]] = {**r[keep[7]], "c:funding_rate_median": None}          # 281
    assert build_horizons(CFG, as_of_bucket=AS_OF, metrics_by_bucket=r)["24h"]["funding_rate_avg"] is None


def test_the_sign_change_needs_rates_of_a_printable_size():
    base = dict(range_w=None, range_p=None, volume_w=None, volume_p=None, volume_w_complete=False,
                volume_p_complete=False, price_w=None, oi_w=None)
    assert select_changes(CFG, **base, funding_now=0.000004, funding_p=-0.000004) == []     # prints «0,000%»
    assert select_changes(CFG, **base, funding_now=0.00002, funding_p=-0.000004) == []
    assert select_changes(CFG, **base, funding_now=0.00002, funding_p=-0.00002) == [{"rule": "funding", "positive": True}]


@pytest.mark.parametrize("lang,now24,now1", [
    ("ru", "Funding сейчас 0,020% за 8 ч (медиана 2 из 3 бирж; нет свежей ставки: OKX) · среднее за 24 ч 0,010% за 8 ч",
     "Funding сейчас 0,020% за 8 ч (медиана 2 из 3 бирж; нет свежей ставки: OKX)"),
    ("en", "Funding now 0.020% per 8h (median of 2 of 3 exchanges; no fresh rate: OKX) · 24h average 0.010% per 8h",
     "Funding now 0.020% per 8h (median of 2 of 3 exchanges; no fresh rate: OKX)"),
])
def test_rates_say_per_8h_and_how_many_venues(lang, now24, now1):
    hzs = build_horizons(CFG, as_of_bucket=AS_OF, metrics_by_bucket=rows(288),
                         funding_latest=latest(binance=(1, 0.0001), bybit=(1, 0.0003), okx=(40, 0.0002)))
    view = {"horizons": hzs, "now": {"reference_price": 100.0}}
    assert now24 in plain(format_24h_tab(CFG, view, lang))
    assert now1 in plain(format_1h_tab(CFG, view, lang))


def test_definition_pins_the_bound():
    d = hz.horizon_definition()
    assert d["funding_now"]["max_age_min"] == FUNDING_MAX_AGE.total_seconds() // 60 == 15
    assert hz.verify_horizon_digest()


# ---- the store read (PostgreSQL) --------------------------------------------------------------
from beta_fakes import TEST_DSN, fresh_pool, run  # noqa: E402


@pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)")
def test_store_reads_each_venues_newest_live_row_before_the_boundary():
    from storage.beta_v0_store import BetaStore

    async def body():
        pool = await fresh_pool()
        t = END
        rows_ = [("binance", "BTCUSDT", t - timedelta(minutes=3), 0.0001, "live"),
                 ("binance", "BTCUSDT", t - timedelta(minutes=1), 0.0002, "live"),
                 ("binance", "BTCUSDT", t, 0.9, "live"),                       # at the boundary: look-ahead
                 ("bybit", "BTCUSDT", t - timedelta(minutes=30), 0.0003, "live"),
                 ("bybit", "BTCUSDT", t - timedelta(minutes=2), 0.7, "backfill"),  # a settled rate is not «сейчас»
                 ("okx", "ETHUSDT", t - timedelta(minutes=1), 0.5, "live")]
        async with pool.acquire() as c:
            await c.executemany(
                """INSERT INTO funding_rate (exchange, symbol, ts, funding_rate, source) VALUES ($1,$2,$3,$4,$5)""",
                rows_)
        async with BetaStore(pool).connect() as conn:
            got = await conn.fetch_funding_latest(symbol="BTCUSDT", exchanges=EXS, at=t, since=t - FUNDING_MAX_AGE)
            wide = await conn.fetch_funding_latest(symbol="BTCUSDT", exchanges=EXS, at=t, since=t - timedelta(hours=1))
        assert got["binance"]["funding_rate"] == 0.0002 and got["binance"]["ts"] == t - timedelta(minutes=1)
        assert got["bybit"] is None                                     # 30 minutes old: below the lower bound
        assert wide["bybit"]["funding_rate"] == 0.0003                  # read when inside the window
        assert got["okx"] is None
        f = funding_now(CFG, got, t)
        assert f["venues"] == 1 and f["rate"] is None
        await pool.close()
    run(body())


@pytest.mark.parametrize("lang,want", [("ru", "Funding сейчас н/д (нет свежей ставки: Bybit, OKX) · среднее за 24 ч 0,010% за 8 ч"),
                                       ("en", "Funding now n/a (no fresh rate: Bybit, OKX) · 24h average 0.010% per 8h")])
def test_with_one_fresh_venue_now_is_na_and_the_stale_ones_are_named(lang, want):
    hzs = build_horizons(CFG, as_of_bucket=AS_OF, metrics_by_bucket=rows(288),
                         funding_latest=latest(binance=(1, 0.0001), bybit=(30, 0.0003), okx=(40, 0.0002)))
    view = {"horizons": hzs, "now": {"reference_price": 100.0}}
    assert want in plain(format_24h_tab(CFG, view, lang))         # the venue note never sits beside the 24h mean


def test_the_store_read_carries_a_lower_time_bound_and_the_view_passes_it():
    """ОПГ-1 review of #413: without `ts >= since` the hypertable cannot exclude chunks and every view build
    scans the whole funding history. The view passes at − FUNDING_MAX_AGE: nothing that could be shown is lost."""
    import asyncio
    from storage.beta_v0_store import BetaConn
    seen = {}

    class Raw:
        async def fetch(self, sql, *args):
            seen["sql"], seen["args"] = sql, args
            return []
    out = asyncio.run(BetaConn(Raw()).fetch_funding_latest(symbol="BTCUSDT", exchanges=EXS, at=END,
                                                           since=END - FUNDING_MAX_AGE))
    assert out == {ex: None for ex in EXS}
    assert "ts < $3 AND ts >= $4" in seen["sql"] and seen["args"][2:] == (END, END - FUNDING_MAX_AGE)
    import inspect
    from beta import market_view
    src = inspect.getsource(market_view._tape_and_oi)
    assert "since=through - FUNDING_MAX_AGE" in src
