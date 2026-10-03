"""Decision support V2: pure modules (history parsing, range model, levels, analogues, calendar).

PRODUCT_DECISION_V2. No database, no network. Real Binance 5m archives committed in the
repository (MARKET_06 durable raw copies, 2022-2024) are used where calibration is checked.
"""
import asyncio
import math
import random
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pytest

from beta import hist_series as hs
from beta import history_data as hd
from beta import levels as lv
from beta import rangecast as rc
from beta.analogues import _ProxyCfg, analogue_stats, label_history, lookup, trailing_ranks, window_values
from beta.calendar_events import event_size_stats, event_times_ms, expiries, load_calendar, upcoming
from beta.config import BetaConfig
from v2_fakes import kline_zip, metrics_zip, repo_vision_zips, synthetic_rows

UTC = timezone.utc
CFG = BetaConfig.load()
T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _bars(days=60, seed=7):
    rows, ois = synthetic_rows(T0, days, seed=seed)
    return hs.bars_from_rows(rows, oi_rows=[{"ts_ms": r["ts_ms"], "oi": r["oi_base"]} for r in ois])


_REAL = {}


def _real(months):
    key = tuple(months)
    if key not in _REAL:
        _REAL[key] = hs.bars_from_rows(hd.rows_from_local_zips(repo_vision_zips(months)))
    return _REAL[key]


# ---- hist_series -------------------------------------------------------------------------
def test_grid_places_rows_and_keeps_gaps_nan():
    rows = [{"open_time_ms": 0, "open": 1, "high": 2, "low": 0.5, "close": 1.5},
            {"open_time_ms": 2 * hs.BAR_MS, "open": 1.5, "high": 3, "low": 1, "close": 2}]
    b = hs.bars_from_rows(rows, start_ms=0, end_ms=3 * hs.BAR_MS)
    assert b.n == 3 and b.close[0] == 1.5 and math.isnan(b.close[1]) and b.close[2] == 2
    assert b.last_complete_index() == 2 and b.end_ms == 3 * hs.BAR_MS


def test_aggregate_1m_needs_all_five_minutes_and_keeps_ohlc():
    t = datetime(2026, 1, 1, tzinfo=UTC)
    mins = [{"ts": t + timedelta(minutes=k), "open": 10 + k, "high": 20 + k, "low": 5 - k, "close": 11 + k,
             "volume": 1.0, "taker_buy_volume": 0.5} for k in range(5)]
    out = hs.aggregate_1m(mins + [{**mins[0], "ts": t + timedelta(minutes=5)}])   # 2nd bar incomplete
    assert len(out) == 1
    bar = out[0]
    assert (bar["open"], bar["high"], bar["low"], bar["close"]) == (10, 24, 1, 15)
    assert bar["quote_volume"] == pytest.approx(sum(11 + k for k in range(5)))


def test_merge_prefers_history_and_appends_only_later_live_bars():
    hist = [{"open_time_ms": 0, "close": 1}, {"open_time_ms": hs.BAR_MS, "close": 2}]
    live = [{"open_time_ms": hs.BAR_MS, "close": 99}, {"open_time_ms": 2 * hs.BAR_MS, "close": 3}]
    assert [r["close"] for r in hs.merge_rows(hist, live)] == [1, 2, 3]


def test_forward_extremes_use_the_following_bars_only():
    rows = [{"open_time_ms": k * hs.BAR_MS, "open": 1, "high": h, "low": l, "close": c}
            for k, (h, l, c) in enumerate([(2, 1, 1.5), (5, 0.5, 4), (3, 2, 2.5), (9, 1, 8)])]
    b = hs.bars_from_rows(rows)
    hi, lo, cl = hs.forward_extremes(b, 2, min_frac=1.0)
    assert (hi[0], lo[0], cl[0]) == (5, 0.5, 2.5)
    assert (hi[1], lo[1], cl[1]) == (9, 1, 8)
    assert math.isnan(hi[2]) and math.isnan(hi[3])


# ---- history_data ----------------------------------------------------------------------
def test_plan_monthly_until_last_month_then_daily_and_metrics_daily():
    objs = hd.planned_objects(date(2026, 10, 3), klines_start=date(2026, 9, 1), metrics_start=date(2026, 10, 1))
    keys = [o.key for o in objs]
    assert keys == ["monthly/klines/BTCUSDT/5m/BTCUSDT-5m-2026-09.zip",
                    "daily/klines/BTCUSDT/5m/BTCUSDT-5m-2026-10-01.zip",
                    "daily/klines/BTCUSDT/5m/BTCUSDT-5m-2026-10-02.zip",
                    "daily/metrics/BTCUSDT/BTCUSDT-metrics-2026-10-01.zip",
                    "daily/metrics/BTCUSDT/BTCUSDT-metrics-2026-10-02.zip"]
    assert objs[0].url.startswith("https://data.binance.vision/data/futures/um/monthly/klines/")
    assert len(hd.daily_fallback(objs[0])) == 30


# ---- E1-RUN-001 final holdout [2026-08-16 00:00, 2026-08-25 17:20): object level, before any request
E1_REJECTED = (["monthly/klines/BTCUSDT/5m/BTCUSDT-5m-2026-08.zip"]
               + [f"daily/klines/BTCUSDT/5m/BTCUSDT-5m-2026-08-{d:02d}.zip" for d in range(16, 26)]
               + [f"daily/metrics/BTCUSDT/BTCUSDT-metrics-2026-08-{d:02d}.zip" for d in range(16, 26)])


def _ms(*a):
    return int(datetime(*a, tzinfo=UTC).timestamp() * 1000)


def test_e1_every_overlapping_object_is_rejected_and_august_is_planned_from_allowed_days():
    planned, rejected = hd.plan_objects(date(2026, 10, 3))
    assert [o.key for o in rejected] == E1_REJECTED
    keys = {o.key for o in planned}
    assert not keys & set(E1_REJECTED)
    assert all(hd.url_refusal(o.url) is None for o in planned)            # nothing planned overlaps
    aug = sorted(int(k[-6:-4]) for k in keys if k.startswith("daily/klines/") and "-2026-08-" in k)
    assert aug == list(range(1, 16)) + list(range(26, 32))                 # 1..15 and 26..31
    met = sorted(int(k[-6:-4]) for k in keys if k.startswith("daily/metrics/") and "-2026-08-" in k)
    assert met == aug
    assert {"monthly/klines/BTCUSDT/5m/BTCUSDT-5m-2026-07.zip",
            "monthly/klines/BTCUSDT/5m/BTCUSDT-5m-2026-09.zip"} <= keys


@pytest.mark.parametrize("when,inside", [
    ((2026, 8, 15, 23, 55), False),     # last bar before the window: [23:55, 00:00)
    ((2026, 8, 16, 0, 0), True),        # first protected bar
    ((2026, 8, 25, 17, 15), True),      # last protected bar: [17:15, 17:20)
    ((2026, 8, 25, 17, 20), False),     # first bar after the window
])
def test_e1_boundaries_bar_level(when, inside):
    t = _ms(*when)
    assert hd.in_protected_window(t) is inside
    assert (hd.protected_overlap(t, t + 300_000) is not None) is inside   # the 5m bar opening at t


@pytest.mark.parametrize("day,rejected", [(15, False), (16, True), (24, True), (25, True), (26, False)])
def test_e1_boundaries_object_level(day, rejected):
    """2026-08-25 is rejected whole although its tail after 17:20 is outside the window."""
    for obj in (hd.klines_daily(date(2026, 8, day)), hd.metrics_daily(date(2026, 8, day))):
        assert (hd.object_protected(obj) is not None) is rejected
        assert (hd.url_refusal(obj.url) is not None) is rejected
        assert (hd.url_refusal(obj.url + ".CHECKSUM") is not None) is rejected


def test_e1_plans_during_and_right_after_the_window():
    planned, rejected = hd.plan_objects(date(2026, 8, 20), klines_start=date(2026, 8, 1), metrics_start=date(2026, 8, 1))
    assert sorted(o.period_end.day for o in planned if o.kind == "klines_daily") == list(range(1, 16))
    assert sorted(o.period_end.day for o in rejected if o.kind == "klines_daily") == [16, 17, 18, 19]
    planned, rejected = hd.plan_objects(date(2026, 9, 2), klines_start=date(2026, 8, 1), metrics_start=date(2026, 9, 1))
    assert "monthly/klines/BTCUSDT/5m/BTCUSDT-5m-2026-08.zip" in {o.key for o in rejected}
    fb = hd.daily_fallback(hd.klines_monthly(2026, 8))
    assert sorted(o.period_end.day for o in fb) == list(range(1, 16)) + list(range(26, 32))
    assert len(hd.daily_fallback(hd.klines_monthly(2026, 7))) == 31


def test_e1_request_gate_refuses_before_the_network_call():
    calls = []

    async def inner(url):
        calls.append(url)
        return b"x"
    gate = hd.guard_fetch(inner)
    base = hd.VISION_ROOT + "/"
    refused = [base + E1_REJECTED[0], base + E1_REJECTED[0] + ".CHECKSUM", base + E1_REJECTED[1],
               base + E1_REJECTED[-1] + ".CHECKSUM", base + "daily/klines/BTCUSDT/5m/README.zip"]
    for url in refused:
        with pytest.raises(hd.ProtectedObjectRefused):
            asyncio.run(gate(url))
    allowed = [base + "daily/klines/BTCUSDT/5m/BTCUSDT-5m-2026-08-15.zip",
               base + "daily/metrics/BTCUSDT/BTCUSDT-metrics-2026-08-26.zip.CHECKSUM",
               base + "monthly/klines/BTCUSDT/5m/BTCUSDT-5m-2026-07.zip"]
    for url in allowed:
        assert asyncio.run(gate(url)) == b"x"
    assert calls == allowed                                                  # refused URLs never reached it


def test_e1_rows_inside_the_window_are_still_dropped_after_parsing():
    rows, _ = synthetic_rows(datetime(2026, 8, 25, 17, tzinfo=UTC), 1)
    kept = hd.drop_protected(rows, "open_time_ms")
    assert min(r["open_time_ms"] for r in kept) == _ms(2026, 8, 25, 17, 20)


def test_parse_klines_with_and_without_header_and_microseconds():
    rows, _ = synthetic_rows(T0, 1)
    a = hd.parse_klines(kline_zip(rows[:3], "x.zip", header=True))
    b = hd.parse_klines(kline_zip(rows[:3], "x.zip", header=False))
    assert a == b and len(a) == 3 and a[0]["open_time_ms"] == rows[0]["open_time_ms"]
    micro = [{**r, "open_time_ms": r["open_time_ms"] * 1000} for r in rows[:1]]
    assert hd.parse_klines(kline_zip(micro, "x.zip"))[0]["open_time_ms"] == rows[0]["open_time_ms"]
    bad = [{**rows[0], "high": rows[0]["low"] - 1}]
    with pytest.raises(hd.HistoryDataError):
        hd.parse_klines(kline_zip(bad, "x.zip"))


def test_parse_metrics_and_checksum():
    _, ois = synthetic_rows(T0, 1)
    out = hd.parse_metrics(metrics_zip(ois[:4], "m.zip"))
    assert [r["ts_ms"] for r in out] == [o["ts_ms"] for o in ois[:4]]
    assert hd.checksum_of("ab" * 32 + "  file.zip\n") == "ab" * 32
    with pytest.raises(hd.HistoryDataError):
        hd.checksum_of("nope")


def test_repo_archive_parses_to_a_gap_free_month():
    b = _real(["2024-02"])
    assert b.n == 29 * 288 and int((~b.present()).sum()) == 0


# ---- range model --------------------------------------------------------------------------
def test_range_model_is_calibrated_out_of_sample_on_real_binance():
    """The held-out year (2024) keeps the price inside the 80% corridor about 80% of the time."""
    b = _real([f"{y}-{m:02d}" for y in (2022, 2023, 2024) for m in range(1, 13)])
    cal = load_calendar()
    model = rc.fit_range_model(b, events=event_times_ms(cal))
    for h in ("1h", "4h", "24h"):
        c = model["calibration"][h]
        assert 0.76 <= c["coverage_realized"] <= 0.84, (h, c)
        for rel in c["touch_reliability"]:
            assert abs(rel["realized_touch"] - rel["predicted_touch"]) < 0.04
    # scheduled releases widen the window they fall in
    assert model["horizons"]["1h"]["beta"][rc.FEATURES.index("event_cpi")] > 0.3
    assert model["move"]["threshold"] and 0.1 <= model["move"]["episodes_per_day"] <= 1.0


def test_forecast_corridor_and_touch_probabilities():
    b = _real(["2024-01", "2024-02", "2024-03", "2024-04", "2024-05", "2024-06"])
    model = rc.fit_range_model(b, events={})
    price = float(b.close[-1])
    fc = rc.forecast(model, b, price=price, events={})
    assert set(fc["horizons"]) == {"1h", "4h", "24h"}
    w = [fc["horizons"][h]["half_width_pct"] for h in ("1h", "4h", "24h")]
    assert w[0] < w[1] < w[2]
    for h, x in fc["horizons"].items():
        assert x["lower"] < price < x["upper"]
        ps = [rc.touch_probability(model, h, x["scale_pct"], d) for d in (0.1, 0.5, 1, 2, 5)]
        assert ps == sorted(ps, reverse=True) and 0 <= ps[-1] <= ps[0] <= 1
    assert rc.touch_probability(model, "1h", 1.0, 0.0) == 1.0
    stats = rc.stop_stats(model, fc, 0.5)
    assert stats["1h"]["hit_probability"] < stats["24h"]["hit_probability"]


def test_forecast_needs_complete_past_windows():
    b = _bars(days=3)
    model = rc.fit_range_model(_real(["2024-01", "2024-02", "2024-03", "2024-04"]), events={})
    assert rc.forecast(model, b, price=60000.0, events={})["horizons"] == {}


def test_weekend_share_and_event_window():
    sat = datetime(2026, 1, 3, tzinfo=UTC)               # a Saturday
    b = hs.empty_bars(int(sat.timestamp() * 1000), 10)
    assert rc.weekend_share(b, 12)[0] == 1.0
    anchor = np.array([int(sat.timestamp() * 1000)])
    ev = [int((sat + timedelta(minutes=30)).timestamp() * 1000)]
    assert rc.event_in_window(anchor, ev, rc.HORIZON_MS["1h"])[0] == 1.0
    assert rc.event_in_window(anchor + rc.HORIZON_MS["1h"], ev, rc.HORIZON_MS["1h"])[0] == 0.0


# ---- levels --------------------------------------------------------------------------------
def test_live_levels_from_the_previous_and_current_periods():
    b = _bars(days=40)
    now = b.end_ms                                         # the grid ends at a day boundary
    day = now // lv.DAY_MS
    prev = slice(int((day - 1) * lv.DAY_MS - b.t0) // hs.BAR_MS, int(day * lv.DAY_MS - b.t0) // hs.BAR_MS)
    out = lv.compute_levels(b, now_ms=now, price=float(b.close[-1]))
    kinds = {x["kind"]: x["price"] for x in out}
    assert kinds["PDH"] == pytest.approx(float(np.nanmax(b.high[prev])))
    assert kinds["PDL"] == pytest.approx(float(np.nanmin(b.low[prev])))
    assert "PWH" in kinds and "PWL" in kinds and "POC_PD" in kinds
    assert float(np.nanmin(b.low[prev])) <= kinds["POC_PD"] <= float(np.nanmax(b.high[prev]))
    assert sum(1 for x in out if x["kind"] == "ROUND") == 4


def test_zones_merge_and_selection_rules():
    price = 60000.0
    levels = [{"kind": "ROUND", "price": 61000.0}, {"kind": "PDH", "price": 61050.0},
              {"kind": "ROUND", "price": 62000.0}, {"kind": "WO", "price": 60400.0},
              {"kind": "ROUND", "price": 63000.0}, {"kind": "PDL", "price": 59000.0},
              {"kind": "ASIA_L", "price": 59990.0}]
    zones = lv.merge_zones(levels, price=price)
    merged = [z for z in zones if "PDH" in z["kinds"]][0]
    assert merged["kinds"] == ["PDH", "ROUND"] and merged["low"] == 61000.0 and merged["high"] == 61050.0
    near = lv.nearest_zones(zones, price=price, reach_pct=3.0)
    assert near["at"]["kinds"] == ["ASIA_L"]
    above = [z["kinds"] for z in near["above"]]
    assert above[0] == ["WO"] and ["PDH", "ROUND"] in above
    assert sum(1 for k in above if k == ["ROUND"]) <= 1
    assert [z["distance_pct"] > 0 for z in near["above"]] == [True] * len(near["above"])
    assert near["below"][0]["kinds"] == ["PDL"]


def test_liquidation_clusters_sum_by_side_and_bin():
    now = datetime(2026, 1, 2, tzinfo=UTC)
    rows = [{"ts": now - timedelta(hours=1), "side": "long", "price": 59050.0 + k, "notional": 1_000_000.0}
            for k in range(3)] + [{"ts": now - timedelta(hours=30), "side": "long", "price": 58000.0,
                                   "notional": 9e9}]
    out = lv.liquidation_clusters(rows, now_ms=int(now.timestamp() * 1000), price=60000.0)
    assert out == [{"kind": "LIQ_LONG", "price": 59050.0, "notional_usd": 3_000_000.0}]


def test_level_reaction_statistics_shape_and_controls():
    st = lv.level_reaction_stats(_bars(days=120), bootstrap=200)
    assert set(st["types"]) == set(lv.STAT_TYPES)
    pdh = st["types"]["PDH"]
    assert pdh["real"]["approaches"] > 30 and 0 <= pdh["real"]["touch_rate"] <= 1
    assert pdh["control"]["approaches"] == lv.CONTROLS_PER_PERIOD * pdh["real"]["approaches"]
    for rec in st["types"].values():
        assert set(rec["verdicts"]) <= {"1h", "4h", "touch"}
        assert set(rec["verdicts"].values()) <= {"differs", "as_usual", "insufficient"}


def test_holm_and_side_specific_statistics():
    adj = lv.holm({"a": 0.01, "b": 0.04, "c": 0.03, "d": None})
    assert adj == {"a": 0.03, "c": 0.06, "b": 0.06}
    assert lv.stat_type_for("PDH", +1) == "PDH" and lv.stat_type_for("PDH", -1) is None
    assert lv.stat_type_for("PWL", -1) == "PWL" and lv.stat_type_for("PWL", +1) is None
    assert lv.stat_type_for("ROUND", -1) == "ROUND_DOWN" and lv.stat_type_for("VWAP_D", 1) is None


# ---- analogues ------------------------------------------------------------------------------
def test_trailing_ranks_match_brute_force():
    rng = random.Random(3)
    vals = np.array([rng.choice([rng.random(), float("nan"), 0.5]) for _ in range(400)])
    anchors = np.arange(50, 400, 7)
    got = trailing_ranks(vals, anchors, window=40, min_fraction=0.5)
    for k, a in enumerate(anchors):
        prev = [v for v in vals[a - 40:a] if not math.isnan(v)]
        if math.isnan(vals[a]) or len(prev) < 20:
            assert math.isnan(got[k])
            continue
        less = sum(v < vals[a] for v in prev)
        eq = sum(v == vals[a] for v in prev)
        assert got[k] == pytest.approx((less + 0.5 * eq) / len(prev))


def test_window_values_follow_the_live_definitions():
    b = _bars(days=2)
    n = 12
    w = window_values(b, n)
    i = 200
    assert w["price_move_pct_median"][i] == pytest.approx((b.close[i] / b.open[i - n + 1] - 1) * 100)
    rng = (np.nanmax(b.high[i - n + 1:i + 1]) - np.nanmin(b.low[i - n + 1:i + 1])) / b.open[i - n + 1] * 100
    assert w["range_width_pct_median"][i] == pytest.approx(rng)
    assert w["oi_change_pct_median"][i] == pytest.approx((b.oi[i] / b.oi[i - n] - 1) * 100)
    assert w["taker_delta_notional_usd_sum"][i] == pytest.approx(
        float(np.sum(2 * b.taker_buy_quote[i - n + 1:i + 1] - b.quote[i - n + 1:i + 1])))


def test_analogue_statistics_shape_baseline_and_lookup():
    b = _bars(days=75)
    st = analogue_stats(b, context=CFG.section("context"), bootstrap=200)
    assert set(st["windows"]) == {"1h", "4h"}
    assert "venues_diverge" not in st["windows"]["1h"]
    some = next(iter(st["windows"]["4h"].values()))
    assert set(some["outcomes"]) == {"4h", "24h"}
    for rec in st["windows"]["1h"].values():
        for cell in rec["outcomes"].values():
            assert set(cell["verdicts"]) == {"direction", "range"}
            if cell["n"]:
                assert 0 <= cell["p_up"] <= 1 and cell["baseline"] is not None
    if "long_exit" in st["windows"]["1h"]:
        card = lookup(st, "1h", "long_flush")
        assert card["key"] == "long_exit" and card["proxy_label"] is True
    assert lookup(st, "1h", None) is None and lookup(None, "1h", "normal") is None


def test_label_history_uses_the_live_interpretation_rules():
    b = _bars(days=40)
    hist = label_history(b, context=CFG.section("context"))
    keys = set(hist["labels"]["1h"])
    assert "insufficient" in keys or "missing" in keys          # the first 30 days have no ranks
    assert keys <= {"short_exit", "long_build", "short_build", "long_exit", "compression", "compression_oi_na",
                    "normal", "up_oi_down", "up_oi_up", "down_oi_up", "down_oi_down", "up_oi_na", "down_oi_na",
                    "up_oi_stable", "down_oi_stable", "insufficient", "missing"}
    assert _ProxyCfg(CFG.section("context")).min_venues == 1


# ---- calendar --------------------------------------------------------------------------------
def test_calendar_holds_official_schedule_times():
    cal = load_calendar()
    times = {(e["kind"], e["at"].isoformat()) for e in cal["events"]}
    assert ("CPI", "2026-10-14T12:30:00+00:00") in times
    assert ("FOMC", "2026-10-28T18:00:00+00:00") in times
    assert ("FOMC", "2024-12-18T19:00:00+00:00") in times
    ev = event_times_ms(cal)
    assert ev["CPI"] == sorted(ev["CPI"]) and len(ev["CPI"]) >= 70


def test_calendar_generator_is_deterministic(tmp_path):
    from scripts.beta.build_calendar import main
    out = tmp_path / "cal.yaml"
    assert main(["--out", str(out)]) == 0
    from beta.calendar_events import CALENDAR_PATH
    assert out.read_text() == CALENDAR_PATH.read_text()


def test_expiries_and_upcoming():
    rec = load_calendar()["recurring"]
    ex = expiries(datetime(2026, 9, 21, tzinfo=UTC), datetime(2026, 11, 3, tzinfo=UTC), rec)
    kinds = {e["at"].date().isoformat(): e["kind"] for e in ex}
    assert kinds["2026-09-25"] == "EXPIRY_QUARTERLY" and kinds["2026-10-30"] == "EXPIRY_MONTHLY"
    assert kinds["2026-10-02"] == "EXPIRY_WEEKLY" and all(e["at"].hour == 8 for e in ex)
    up = upcoming(load_calendar(), now=datetime(2026, 10, 14, 6, tzinfo=UTC), hours=24)
    assert [e["kind"] for e in up] == ["CPI"]


def test_event_size_statistics_compare_with_days_without_the_event():
    b = _bars(days=60)
    cal = {"events": [{"kind": "CPI", "at": T0 + timedelta(days=d, hours=13, minutes=30)} for d in range(25, 58, 3)],
           "recurring": {}}
    st = event_size_stats(b, cal, kinds=("CPI",))
    rec = st["kinds"]["CPI"]
    assert rec["n"] == 11 and rec["hour"]["n"] == 11 and rec["hour"]["median_ratio"] > 0


# ---- config ----------------------------------------------------------------------------------
def test_decision_config_is_validated():
    from beta.config import BetaConfigError
    d = CFG.section("decision")
    assert d["max_price_alerts"] == 5 and d["market_alerts"]["max_per_utc_day"] == 4
    bad = dict(d)
    bad["market_alerts"] = {**d["market_alerts"], "max_per_utc_day": 0}
    with pytest.raises(BetaConfigError):
        CFG.with_overrides(decision=bad)
    with pytest.raises(BetaConfigError):
        CFG.with_overrides(decision={**d, "extra": 1})
