"""WEEKDAY_WEEKEND_BASELINE_UNIT_V2 evaluator: parity with production, point-in-time, typing.

Synthetic tapes only; no market data is read."""
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pytest

from beta import context as cx
from beta import horizons as hz
from beta.config import BetaConfig
from beta.state_tape import BUCKET, metric_key
from scripts.product.weekday_weekend_baseline_v2 import evaluate as E

# C0 parity is checked against the pooled reference, which production keeps under the
# BETA_CONTEXT_1H_V2 label (the active V3 label is C1, parity-tested in tests/beta/test_beta_c1_day_type.py).
_LOADED = BetaConfig.load()
CFG = _LOADED.with_overrides(context={**_LOADED.section("context"), "version": "BETA_CONTEXT_1H_V2"})
IDENT = {"feature_schema_version": 1, "calculation_version": "a" * 16,
         "stage2_config_hash": "b" * 64, "stage2_config_version": "v"}
TIERS = {"none_below_days": 3, "low_below_days": 7, "building_below_days": 30}


def panel(days: int, seed: int = 7, shock_from_min: int | None = None) -> dict:
    rng = np.random.default_rng(seed)
    n = days * 1440
    r = rng.normal(0, 0.0008, n)
    close = 10000 * np.exp(np.cumsum(r))
    open_ = np.concatenate([[10000.0], close[:-1]])
    wiggle = np.abs(rng.normal(0, 0.0004, n)) * close
    high = np.maximum(open_, close) + wiggle
    low = np.minimum(open_, close) - wiggle
    quote = rng.lognormal(10, 0.6, n)
    if shock_from_min is not None:
        high[shock_from_min:] *= 1.5
        quote[shock_from_min:] *= 50
    t0 = int(E.T0.timestamp() * 1000)
    return {"open_ms": t0 + 60_000 * np.arange(n, dtype=np.int64), "open": open_, "high": high,
            "low": low, "close": close, "quote": quote}


def tape(b5: dict) -> dict:
    out = {}
    for j in range(len(b5["o"])):
        m = {"c:volume_notional_usd_sum": float(b5["q"][j])}
        for ex in CFG.exchanges:
            m[metric_key(ex, "kline_open")] = float(b5["o"][j])
            m[metric_key(ex, "kline_high")] = float(b5["h"][j])
            m[metric_key(ex, "kline_low")] = float(b5["l"][j])
            m[metric_key(ex, "kline_close")] = float(b5["c"][j])
        out[E.T0 + j * BUCKET] = m
    return out


@pytest.fixture(scope="module")
def small():
    p = panel(33)
    b5 = E.to_5m(p)
    return p, b5, tape(b5)


def test_rolling_values_match_production(small):
    _, b5, mbb = small
    for n in (12, 48):
        v = E.rolling(b5, n)
        for j in (n - 1, 500, 9000):
            prod = cx.rolling_window_values(CFG, mbb, E.T0 + j * BUCKET, n)
            assert prod["range_width_pct_median"] == pytest.approx(v["range"][j], rel=1e-12)
            assert prod["price_move_pct_median"] == pytest.approx(v["move"][j], rel=1e-12, abs=1e-15)
            assert prod["volume_notional_usd_sum"] == pytest.approx(v["volume"][j], rel=1e-12)


def test_c0_rank_matches_production_percentile_core(small):
    _, b5, mbb = small
    n = 12
    vals = E.rolling(b5, n)
    grid = np.arange(n - 1, len(b5["o"]))
    grid = grid[(grid + 1) % n == 0]
    ranks = E.rank_all(vals, grid, n, {m: {"factor": {}} for m in E.METRICS})
    checked = 0
    for i, j in enumerate(grid):
        if j < E.REF_BUCKETS + n - 1 or checked >= 3:
            continue
        t = E.T0 + int(j) * BUCKET
        hist = [(b, m) for b, m in mbb.items() if t - timedelta(days=30, hours=2) <= b < t]
        ctx = cx.context_1h(CFG, bucket_ts=t, current_metrics=mbb[t], history=hist, identity=IDENT,
                            code_version="t", tiers=TIERS)
        p = ctx["percentiles"]
        assert p["range_width_pct_median"]["tier"] == "mature"
        assert ranks["C0"]["range"][i] == pytest.approx(p["range_width_pct_median"]["rank"])
        assert ranks["C0"]["move"][i] == pytest.approx(p["price_move_pct_median"]["rank"])
        assert ranks["C0"]["volume"][i] == pytest.approx(p["volume_notional_usd_sum"]["rank"])
        checked += 1
    assert checked == 3
    # before 30 days of history the production tier is not mature and C0 is unusable
    assert np.isnan(ranks["C0"]["range"][0])


def test_c0_tod_matches_production_baseline(small):
    _, b5, mbb = small
    vals = E.rolling(b5, 12)
    grid = np.arange(11, len(b5["o"]))
    grid = grid[(grid + 1) % 12 == 0]
    above = E.tod_above(vals, grid, {m: {"factor": {}} for m in E.METRICS})
    checked = 0
    for i, j in enumerate(grid):
        if j < 25 * E.BPD or checked >= 4:
            continue
        base = hz._baseline_tod(CFG, mbb, E.T0 + int(j) * BUCKET, 12)
        med = base["median"]["range_width_pct_median"]
        assert med is not None
        assert above["C0"]["range"][i] == float(vals["range"][j] > med)
        assert above["C0"]["volume"][i] == float(vals["volume"][j] > base["median"]["volume_notional_usd_sum"])
        checked += 1
    assert checked == 4


def test_point_in_time_shock_after_t_changes_nothing_at_t():
    days = 200
    shock_day = 190
    a = E.to_5m(panel(days))
    b = E.to_5m(panel(days, shock_from_min=shock_day * 1440))
    for n in (12,):
        va, vb = E.rolling(a, n), E.rolling(b, n)
        grid = np.arange(n - 1, len(a["o"]))
        grid = grid[(grid + 1) % n == 0]
        fa, fb = E.weekend_factors(va, grid, n), E.weekend_factors(vb, grid, n)
        sd = E.start_day(grid, n)
        before = grid[sd < shock_day - 1]
        keep = np.isin(grid, before)
        for m in E.METRICS:
            for wk, f in fa[m]["factor"].items():
                if E.iso_week_key(shock_day) > wk:
                    assert fb[m]["factor"][wk] == f          # factor never sees its own week or later
        ra = E.rank_all(va, grid[keep][-300:], n, fa)
        rb = E.rank_all(vb, grid[keep][-300:], n, fb)
        for c in E.CANDIDATES:
            for m in E.METRICS:
                np.testing.assert_array_equal(ra[c][m], rb[c][m])
        # all four candidates usable by then (C3 needs 26 weeks, C2 30 weekend dates)
        for c in E.CANDIDATES:
            assert np.isfinite(ra[c]["range"]).any()


def test_day_typing_by_window_start_across_dst_and_year_boundary():
    def day(d):
        return (d - E.D0).days
    assert E.is_weekend_day(day(date(2020, 1, 4))) and E.is_weekend_day(day(date(2020, 3, 8)))   # Sat; US DST Sunday
    assert not E.is_weekend_day(day(date(2020, 12, 31))) and E.is_weekend_day(day(date(2021, 1, 2)))
    assert E.iso_week_key(day(date(2021, 1, 3))) == (2020, 53)
    # the window [Fri 23:00, Sat 00:00) is a weekday window; [Sat 00:00, Sat 01:00) a weekend one
    sat = day(date(2020, 1, 4))
    j_fri_last = sat * E.BPD - 1
    j_sat_first = sat * E.BPD + 11
    assert not E.is_weekend_day(E.start_day(j_fri_last, 12))
    assert E.is_weekend_day(E.start_day(j_sat_first, 12))


def test_one_observation_per_clock_hour():
    b5 = E.to_5m(panel(3))
    grid = np.arange(11, len(b5["o"]))
    grid = grid[(grid + 1) % 12 == 0]
    assert grid[0] == 11 and np.all(np.diff(grid) == 12) and len(grid) == 3 * 24


def test_stationary_series_flags_near_nominal_under_c0():
    b5 = E.to_5m(panel(75, seed=11))
    vals = E.rolling(b5, 12)
    grid = np.arange(11, len(b5["o"]))
    grid = grid[(grid + 1) % 12 == 0]
    r = E.rank_all(vals, grid, 12, {m: {"factor": {}} for m in E.METRICS})["C0"]
    ok = np.isfinite(r["volume"])
    assert ok.sum() > 1000
    assert abs(float((r["volume"][ok] >= 0.95).mean()) - 0.05) < 0.02
    assert abs(float((r["range"][ok] <= 0.20).mean()) - 0.20) < 0.04


def test_c1_c2_reference_definitions():
    n, N = 12, 200 * E.BPD
    rb = E.RefBuilder(n, N)
    sat = (date(2020, 6, 6) - E.D0).days
    j = sat * E.BPD + 11 + 12 * 10                                   # Saturday 10:00-11:00 window
    c1 = rb.indices("C1", j)
    assert np.all(rb.sample_we[c1]) and np.all(c1 >= j - E.REF_BUCKETS) and np.all(c1 < j)
    assert 8 <= len(np.unique(rb.sample_day[c1])) <= 10
    c2 = rb.indices("C2", j)
    assert np.all(rb.sample_we[c2]) and np.all(c2 < j)
    assert len(np.unique(rb.sample_day[c2])) == 30                   # last 30 weekend dates, today included
    assert sat - rb.sample_day[c2].min() > 90                         # about 105 days back
