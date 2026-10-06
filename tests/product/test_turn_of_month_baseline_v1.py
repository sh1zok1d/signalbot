"""TURN_OF_MONTH_BASELINE_UNIT_V1 evaluator: typing parity with G01, 24h parity with production,
trade-count alignment, point-in-time, calendar edges, known answers and the clustered SE.

Synthetic tapes only; no market data is read."""
import datetime as dt
import io
import zipfile

import numpy as np
import pytest

from beta import horizons as hz
from beta.config import BetaConfig
from beta.state_tape import BUCKET, metric_key
from scripts.product.turn_of_month_baseline_v1 import evaluate as E
from scripts.product.weekday_weekend_baseline_v2 import evaluate as WW
from scripts.research.autogen_g01 import states as G01

CFG = BetaConfig.load()


def panel(days: int, seed: int = 7, shock_from_min: int | None = None, tom_volume: float = 1.0,
          tom_range: float = 1.0) -> dict:
    rng = np.random.default_rng(seed)
    n = days * 1440
    r = rng.normal(0, 0.0008, n)
    if tom_range != 1.0:
        r = r * _tom_minute_mask(days, tom_range)
    close = 10000 * np.exp(np.cumsum(r))
    open_ = np.concatenate([[10000.0], close[:-1]])
    wiggle = np.abs(rng.normal(0, 0.0004, n)) * close
    if tom_range != 1.0:
        wiggle = wiggle * _tom_minute_mask(days, tom_range)
    high = np.maximum(open_, close) + wiggle
    low = np.minimum(open_, close) - wiggle
    quote = rng.lognormal(10, 0.6, n)
    if tom_volume != 1.0:
        quote = quote * _tom_minute_mask(days, tom_volume)
    if shock_from_min is not None:
        high[shock_from_min:] *= 1.5
        quote[shock_from_min:] *= 50
    t0 = int(WW.T0.timestamp() * 1000)
    return {"open_ms": t0 + 60_000 * np.arange(n, dtype=np.int64), "open": open_, "high": high,
            "low": low, "close": close, "quote": quote}


def _tom_minute_mask(days: int, factor: float) -> np.ndarray:
    cal = E.calendar(dt.date(2020, 1, 1), WW.D0 + dt.timedelta(days=days))
    per_day = np.ones(days)
    for d, (s, _) in cal.items():
        if s == "TOM" and (d - WW.D0).days < days:
            per_day[(d - WW.D0).days] = factor
    return np.repeat(per_day, 1440)


def tape(b5: dict) -> dict:
    out = {}
    for j in range(len(b5["o"])):
        m = {"c:volume_notional_usd_sum": float(b5["q"][j])}
        for ex in CFG.exchanges:
            m[metric_key(ex, "kline_open")] = float(b5["o"][j])
            m[metric_key(ex, "kline_high")] = float(b5["h"][j])
            m[metric_key(ex, "kline_low")] = float(b5["l"][j])
            m[metric_key(ex, "kline_close")] = float(b5["c"][j])
        out[WW.T0 + j * BUCKET] = m
    return out


# ----------------------------------------------------------------------------- t quantile
@pytest.mark.parametrize("df,expected", [(1, 12.7062047), (4, 2.7764451), (57, 2.0024655), (58, 2.0017175)])
def test_t_quantile_known_values(df, expected):
    assert E.t_crit(df) == pytest.approx(expected, abs=1e-6)


# ----------------------------------------------------------------------------- typing parity
def test_typing_equals_g01_for_every_month_2020_2024():
    s, e = E._ms(E.MATURITY), E._ms(E.SURFACE_END)
    cal = E.calendar()
    for y in range(2020, 2025):
        for m in range(1, 13):
            unit = f"{y}-{m:02d}"
            tom = sorted(d for d, v in cal.items() if v == ("TOM", unit))
            mid = sorted(d for d, v in cal.items() if v == ("MID", unit))
            assert tom == G01.tom_state_days(y, m, s, e)
            assert mid == G01.comparator_days(y, m, s, e)


def test_calendar_counts_match_design_note_section_5():
    cal = E.calendar()
    sets = [v[0] for v in cal.values()]
    assert sets.count("TOM") == 202 and sets.count("MID") == 826
    both = {u for s, u in cal.values() if s == "TOM"} & {u for s, u in cal.values() if s == "MID"}
    assert len(both) == 58


def test_calendar_edges():
    cal = E.calendar()
    # the previous month's last day belongs to unit m; 2020-04-30 is a Thursday
    assert cal[dt.date(2020, 4, 30)] == ("TOM", "2020-05")
    # last-Friday expiry month end is dropped: 2020-07-31 and 2022-09-30 are last Fridays
    assert dt.date(2020, 7, 31) not in cal and dt.date(2022, 9, 30) not in cal
    # holiday windows: Dec 24 - Jan 2 and Oct 1 - 7 are in neither set
    for d in (dt.date(2021, 12, 31), dt.date(2022, 1, 1), dt.date(2022, 1, 2), dt.date(2023, 10, 1),
              dt.date(2023, 10, 3), dt.date(2023, 10, 7), dt.date(2023, 12, 24)):
        assert d not in cal
    # year boundary: Jan 3 is the only TOM day of a January unit; Dec 31 is a holiday
    assert cal[dt.date(2022, 1, 3)] == ("TOM", "2022-01")
    assert [d for d, v in cal.items() if v == ("TOM", "2022-01")] == [dt.date(2022, 1, 3)]
    # October 2022 has no TOM day (Sep 30 is the last Friday, Oct 1-3 holiday) but MID days
    assert not [d for d, v in cal.items() if v == ("TOM", "2022-10")]
    assert len([d for d, v in cal.items() if v == ("MID", "2022-10")]) == 14
    # nothing before maturity, nothing at or after 2025-01-01
    assert min(cal) >= E.MATURITY and max(cal) < E.SURFACE_END


def test_window_typing_by_start_date():
    cal = E.calendar()
    day = (dt.date(2020, 4, 30) - WW.D0).days
    # 1h window [Apr 30 23:00, May 1 00:00) is TOM of unit 2020-05; 4h [May 1 20:00, May 2 00:00) too
    j1 = (day + 1) * WW.BPD - 1
    sets, units = E.type_days(np.array([WW.start_day(j1, 12)]), cal)
    assert sets[0] == "TOM" and units[0] == "2020-05"
    j4 = (day + 2) * WW.BPD - 1
    sets, units = E.type_days(np.array([WW.start_day(j4, 48)]), cal)
    assert sets[0] == "TOM" and units[0] == "2020-05"
    # a window starting on day 22 is in neither set
    sets, _ = E.type_days(np.array([(dt.date(2020, 5, 22) - WW.D0).days]), cal)
    assert sets[0] == ""


# ----------------------------------------------------------------------------- 24h parity
@pytest.fixture(scope="module")
def small():
    p = panel(34)
    b5 = WW.to_5m(p)
    return p, b5, tape(b5)


def test_24h_value_and_baseline_match_production(small):
    _, b5, mbb = small
    v = WW.rolling(b5, E.H24)
    days = np.array([31, 32, 33])
    above = E.h24_above(b5, days)
    for i, d in enumerate(days):
        j = (int(d) + 1) * E.H24 - 1
        end = WW.T0 + j * BUCKET
        prod = hz.rolling_24h_values(CFG, mbb, end)
        assert prod["price_complete"] and prod["volume_complete"]
        assert prod["range_width_pct"] == pytest.approx(v["range"][j], rel=1e-12)
        assert prod["volume_notional_usd"] == pytest.approx(v["volume"][j], rel=1e-12)
        base = hz._baseline_24h(CFG, mbb, end)
        assert base["days"]["range_width_pct"] == 30
        assert above["range"][i] == float(v["range"][j] > base["median"]["range_width_pct"])
        assert above["volume"][i] == float(v["volume"][j] > base["median"]["volume_notional_usd"])


def test_24h_needs_twenty_prior_days(small):
    _, b5, _ = small
    above = E.h24_above(b5, np.array([18, 19, 20, 30]))
    assert np.isnan(above["range"][0]) and np.isnan(above["range"][1])
    assert np.isfinite(above["range"][2]) and np.isfinite(above["volume"][3])


def test_24h_baseline_uses_only_prior_days():
    days = 60
    a = WW.to_5m(panel(days))
    b = WW.to_5m(panel(days, shock_from_min=45 * 1440))
    da = E.h24_above(a, np.arange(31, 45))
    db = E.h24_above(b, np.arange(31, 45))
    for m in ("range", "volume"):
        np.testing.assert_array_equal(da[m], db[m])
    # day 45 itself sees the shock, its baseline does not
    assert E.h24_above(b, np.array([45]))["volume"][0] == 1.0


# ----------------------------------------------------------------------------- point in time
def test_shock_after_t_changes_nothing_at_t():
    days = 70
    a = WW.to_5m(panel(days))
    b = WW.to_5m(panel(days, shock_from_min=60 * 1440))
    N = len(a["o"])
    for n in (12, 48):
        grid = E.clock_grid(N, n)
        grid = grid[(WW.start_day(grid, n) >= 31) & (WW.start_day(grid, n) < 59)]
        ra, _ = E.ranks_c0_c1(WW.rolling(a, n), grid, n, N)
        rb, _ = E.ranks_c0_c1(WW.rolling(b, n), grid, n, N)
        for c in E.CONSTRUCTIONS:
            for m in WW.METRICS:
                np.testing.assert_array_equal(ra[c][m], rb[c][m])
                assert np.isfinite(ra[c][m]).all()


# ----------------------------------------------------------------------------- trade count
def _zip(path, name, rows, header):
    body = ("open_time,open,high,low,close,volume,close_time,quote_volume,count,tbv,tbq,ignore\n" if header else "")
    body += "".join(f"{t},1,2,0.5,1.5,10,{t + 59999},100,{c},1,1,0\n" for t, c in rows)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(name, body)


def test_trade_count_column_aligns_with_loader(tmp_path):
    from scripts.research.owner_cards_r03 import data as R03
    t0 = int(WW.T0.timestamp() * 1000)
    rows1 = [(t0 + 60_000 * k, 7 + k) for k in range(3)]
    rows2 = [(t0 + 60_000 * k, 7 + k) for k in range(3, 5)]
    _zip(tmp_path / "a.zip", "a.csv", rows1, header=False)
    _zip(tmp_path / "b.zip", "b.csv", rows2, header=True)
    specs = [{"KEY": "a", "FILENAME": "a.zip", "SHA256": "x", "CSV": "a.csv"},
             {"KEY": "b", "FILENAME": "b.zip", "SHA256": "y", "CSV": "b.csv"}]
    seen = []

    def fetch(url, dest, sha):
        seen.append((url, sha))
        return dest

    raw = E.read_trade_counts(specs, fetch, tmp_path, "origin/", R03._read_kline_zip)
    assert seen == [("origin/a", "x"), ("origin/b", "y")]
    open_ms = np.array([r[0] for r in rows1 + rows2], dtype=np.int64)
    np.testing.assert_array_equal(E.align_trades(open_ms, raw), [7, 8, 9, 10, 11])
    with pytest.raises(RuntimeError):
        E.align_trades(open_ms + 60_000, raw)
    with pytest.raises(RuntimeError):
        E.align_trades(open_ms[:-1], raw)


# ----------------------------------------------------------------------------- known answers
def _evaluate_volume_flag(p: dict, days: int):
    cal = E.calendar(dt.date(2020, 1, 31), WW.D0 + dt.timedelta(days=days))
    b5 = WW.to_5m(p)
    N = len(b5["o"])
    grid = E.clock_grid(N, 12)
    sd = WW.start_day(grid, 12)
    sets, units = E.type_days(sd, cal)
    sel = sets != ""
    grid, sd, sets, units = grid[sel], sd[sel], sets[sel], units[sel]
    ranks, _ = E.ranks_c0_c1(WW.rolling(b5, 12), grid, 12, N)
    usable = np.all([np.isfinite(ranks["C0"][m]) for m in WW.METRICS], axis=0)
    L = WW.labels_1h(ranks["C0"])
    return E.evaluate_label(L["flag_volume"], usable, sets, units, sd, 0.05, 0.02)


def test_stationary_series_gives_nominal_rates_and_no_difference():
    days = 400
    out = _evaluate_volume_flag(panel(days, seed=3), days)
    assert out["N_TOM"] > 1000 and out["N_MID"] > 3000
    assert abs(out["D"]) < 0.02
    assert abs(out["SETS"]["MID"]["GAP_TO_NOMINAL"]) < 0.015
    assert out["CI95"][0] < 0 < out["CI95"][1]


def test_synthetic_tom_volume_shift_is_recovered_with_its_sign():
    days = 400
    out = _evaluate_volume_flag(panel(days, seed=3, tom_volume=3.0), days)
    assert out["D"] > 0.10 and out["CI95"][0] > 0.02


def test_part_a_recovers_tom_shift_and_null():
    days = 731
    cal = E.calendar(dt.date(2020, 1, 31), WW.D0 + dt.timedelta(days=days))
    trades = np.full(days * 1440, 5.0)
    p0 = panel(days, seed=5)
    p1 = panel(days, seed=5, tom_volume=1.3, tom_range=1.3)
    a0, a1 = E.part_a(p0, trades, cal), E.part_a(p1, trades, cal)
    for m in ("log_quote_volume", "log_range"):
        assert a1[m]["ESTIMATE_SD"] > 0.5 and a1[m]["CI95"][0] > 0
        assert abs(a0[m]["ESTIMATE_SD"]) < 0.25
    both = {u for s, u in cal.values() if s == "TOM"} & {u for s, u in cal.values() if s == "MID"}
    assert a1["log_quote_volume"]["MONTHS"] == len(both) == 23


def test_label_status_rule():
    yearly_pos = {"2020": 0.03, "2021": 0.02, "2022": 0.01, "2023": 0.04, "2024": -0.01}
    assert E.label_status(-0.01, 0.015, 0.02, yearly_pos, 0.0) == "WITHIN_TOLERANCE"
    assert E.label_status(0.025, 0.05, 0.02, yearly_pos, 0.04) == "BEYOND_TOLERANCE"
    three = dict(yearly_pos, **{"2023": -0.01})
    assert E.label_status(0.025, 0.05, 0.02, three, 0.04) == "NOT_RESOLVED"
    assert E.label_status(0.01, 0.05, 0.02, yearly_pos, 0.03) == "NOT_RESOLVED"
    assert E.label_status(-0.06, -0.03, 0.02, {k: -v for k, v in yearly_pos.items()}, -0.04) == "BEYOND_TOLERANCE"


# ----------------------------------------------------------------------------- uncertainty
def test_month_clustered_difference_se_matches_simulation():
    rng = np.random.default_rng(1)
    G, nt, nm = 60, 24 * 4, 24 * 14
    est = []
    se_last = None
    for _ in range(400):
        xs, sets, groups = [], [], []
        for g in range(G):
            u = rng.normal(0, 0.03)                       # month-level shock shared by both sets
            pt, pm = 0.05 + u + rng.normal(0, 0.02), 0.05 + u
            xs += list(rng.random(nt) < max(pt, 0)) + list(rng.random(nm) < max(pm, 0))
            sets += [True] * nt + [False] * nm
            groups += [g] * (nt + nm)
        D, se, Gn = E.diff_se(np.array(xs, float), np.array(sets), np.array(groups))
        est.append(D)
        se_last = se
        assert Gn == G
    sd = float(np.std(est, ddof=1))
    assert se_last == pytest.approx(sd, rel=0.25)
    # ignoring the clustering would understate it
    x = np.array(xs, float)
    s = np.array(sets)
    naive = np.sqrt(x[s].var() / s.sum() + x[~s].var() / (~s).sum())
    assert naive < sd


def test_diff_se_equals_independent_formula_for_singleton_clusters():
    rng = np.random.default_rng(2)
    x = (rng.random(500) < 0.3).astype(float)
    s = np.arange(500) < 120
    D, se, G = E.diff_se(x, s, np.arange(500))
    rt, rm = x[s].mean(), x[~s].mean()
    v = (((x[s] - rt) ** 2).sum() / s.sum() ** 2 + ((x[~s] - rm) ** 2).sum() / (~s).sum() ** 2) * 500 / 499
    assert D == pytest.approx(rt - rm) and se == pytest.approx(np.sqrt(v)) and G == 500
