"""C1 production parity with the frozen WEEKDAY_WEEKEND_BASELINE_UNIT_V2 evaluator.

The same synthetic historical inputs go through the frozen evaluator
(scripts/product/weekday_weekend_baseline_v2/evaluate.py, candidate C1) and through production
(beta.context.context_1h under BETA_CONTEXT_1H_V3, beta.horizons._baseline_tod with day_type,
beta.analogues.trailing_ranks_day_type). Precision: the rolling values are computed in numpy
(evaluator) and in Python floats (production); ranks are compared exactly with a tolerance of one
reference sample (1/N), which an ulp-level tie could flip. No such flip occurs on these inputs.
"""
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pytest

from beta import context as cx
from beta import day_type as dt
from beta import horizons as hz
from beta.analogues import trailing_ranks_day_type, window_start_day
from beta.config import BetaConfig
from beta.hist_series import Bars
from beta.state_tape import BUCKET, metric_key
from scripts.product.weekday_weekend_baseline_v2 import evaluate as E

CFG = BetaConfig.load()
CFG_V2 = CFG.with_overrides(context={**CFG.section("context"), "version": "BETA_CONTEXT_1H_V2"})
IDENT = {"feature_schema_version": 1, "calculation_version": "a" * 16,
         "stage2_config_hash": "b" * 64, "stage2_config_version": "v"}
TIERS = {"none_below_days": 3, "low_below_days": 7, "building_below_days": 30}
UTC = timezone.utc
NOCHANGE = {m: {"factor": {}} for m in E.METRICS}
PROD = {"range": "range_width_pct_median", "move": "price_move_pct_median", "volume": "volume_notional_usd_sum"}


def panel(days: int, seed: int = 5) -> dict:
    rng = np.random.default_rng(seed)
    n = days * 1440
    # weekend minutes calmer and thinner, as in the market the unit measured
    minute_day = (np.arange(n) // 1440 + E.D0.weekday()) % 7
    scale = np.where(minute_day >= 5, 0.5, 1.0)
    r = rng.normal(0, 0.0008, n) * scale
    close = 10000 * np.exp(np.cumsum(r))
    open_ = np.concatenate([[10000.0], close[:-1]])
    wig = np.abs(rng.normal(0, 0.0004, n)) * close * scale
    quote = rng.lognormal(10, 0.6, n) * scale
    t0 = int(E.T0.timestamp() * 1000)
    return {"open_ms": t0 + 60_000 * np.arange(n, dtype=np.int64), "open": open_,
            "high": np.maximum(open_, close) + wig, "low": np.minimum(open_, close) - wig,
            "close": close, "quote": quote}


def tape(b5: dict, lo: int, hi: int, drop: frozenset = frozenset()) -> dict:
    out = {}
    for j in range(lo, hi + 1):
        if j in drop:
            continue
        m = {"c:volume_notional_usd_sum": float(b5["q"][j])}
        for ex in CFG.exchanges:
            m[metric_key(ex, "kline_open")] = float(b5["o"][j])
            m[metric_key(ex, "kline_high")] = float(b5["h"][j])
            m[metric_key(ex, "kline_low")] = float(b5["l"][j])
            m[metric_key(ex, "kline_close")] = float(b5["c"][j])
        out[E.T0 + j * BUCKET] = m
    return out


def idx(ts: datetime) -> int:
    return int((ts - E.T0) / BUCKET)


def prod_ctx(cfg, mbb: dict, j: int, horizon: str = "1h"):
    t = E.T0 + j * BUCKET
    hist = [(b, m) for b, m in mbb.items() if b < t]
    return cx.context_1h(cfg, bucket_ts=t, current_metrics=mbb.get(t), history=hist, identity=IDENT,
                         code_version="t", tiers=TIERS, horizon=horizon)


@pytest.fixture(scope="module")
def year():
    """2020-01-01 .. 2021-01-08: the year boundary and a full Fri/Sat/Sun/Mon sequence."""
    b5 = E.to_5m(panel(373))
    lo = idx(datetime(2020, 11, 28, tzinfo=UTC))
    return b5, tape(b5, lo, len(b5["o"]) - 1)


# window END times (exclusive) -> expected day type of the window START
CASES_1H = [
    (datetime(2020, 12, 31, 15, tzinfo=UTC), dt.WEEKDAY),     # weekday
    (datetime(2021, 1, 1, 0, tzinfo=UTC), dt.WEEKDAY),        # [Dec 31 23:00, Jan 1): year boundary, start Thu
    (datetime(2021, 1, 1, 1, tzinfo=UTC), dt.WEEKDAY),        # first window of 2021 (Fri)
    (datetime(2021, 1, 2, 0, tzinfo=UTC), dt.WEEKDAY),        # [Fri 23:00, Sat): weekday -> weekend edge
    (datetime(2021, 1, 2, 1, tzinfo=UTC), dt.WEEKEND),        # first Saturday window
    (datetime(2021, 1, 2, 12, tzinfo=UTC), dt.WEEKEND),       # Saturday
    (datetime(2021, 1, 3, 18, tzinfo=UTC), dt.WEEKEND),       # Sunday
    (datetime(2021, 1, 4, 0, tzinfo=UTC), dt.WEEKEND),        # [Sun 23:00, Mon): weekend -> weekday edge
    (datetime(2021, 1, 4, 1, tzinfo=UTC), dt.WEEKDAY),        # first Monday window
]


@pytest.mark.parametrize("end, want", CASES_1H)
def test_1h_ranks_labels_and_day_type_match_the_frozen_evaluator(year, end, want):
    b5, mbb = year
    n = 12
    j = idx(end) - 1                                           # end bucket of the window [end-1h, end)
    vals = E.rolling(b5, n)
    ev = E.rank_all(vals, np.array([j]), n, NOCHANGE)["C1"]
    ctx = prod_ctx(CFG, mbb, j)
    assert ctx["day_type"] == want == (dt.WEEKEND if E.is_weekend_day(E.start_day(j, n)) else dt.WEEKDAY)
    for m, pm in PROD.items():
        p = ctx["percentiles"][pm]
        assert p["tier"] == "mature" and p["reference"] == "SAME_UTC_DAY_TYPE"
        assert p["rank"] == pytest.approx(ev[m][0], abs=1.0 / p["sample_size"])
    # labels: the same gate flags and interpretation bands from the same ranks
    ev_labels = E.labels_1h({m: ev[m] for m in E.METRICS})
    from beta.hour_gate import evaluate_hour
    gate = evaluate_hour(CFG, ctx)
    assert gate["passed"]["range"] == bool(ev_labels["flag_range"][0])
    assert gate["passed"]["volume"] == bool(ev_labels["flag_volume"][0])
    assert (gate["passed"]["price"] is not None) == bool(ev_labels["flag_price"][0])
    from beta.interpretation import _band
    assert (_band(CFG, ctx, "range_width_pct_median")[0] == "down") == bool(ev_labels["band_range_low"][0])
    assert (_band(CFG, ctx, "price_move_pct_median")[0] == "up") == bool(ev_labels["band_price_up"][0])
    assert (_band(CFG, ctx, "price_move_pct_median")[0] == "down") == bool(ev_labels["band_price_down"][0])
    # taker and OI keep the pooled reference (not evaluated by the unit)
    assert "reference" not in ctx["percentiles"]["taker_delta_notional_usd_sum"]


@pytest.mark.parametrize("end, want", [(datetime(2021, 1, 2, 0, tzinfo=UTC), dt.WEEKDAY),
                                       (datetime(2021, 1, 2, 4, tzinfo=UTC), dt.WEEKEND),
                                       (datetime(2021, 1, 4, 4, tzinfo=UTC), dt.WEEKDAY)])
def test_4h_ranks_match_the_frozen_evaluator(year, end, want):
    b5, mbb = year
    n = 48
    j = idx(end) - 1
    ev = E.rank_all(E.rolling(b5, n), np.array([j]), n, NOCHANGE)["C1"]
    ctx = prod_ctx(CFG, mbb, j, "4h")
    assert ctx["day_type"] == want
    for m, pm in PROD.items():
        p = ctx["percentiles"][pm]
        assert p["tier"] == "mature" and p["rank"] == pytest.approx(ev[m][0], abs=1.0 / p["sample_size"])


@pytest.mark.parametrize("end", [CASES_1H[i][0] for i in (0, 3, 4, 6, 7, 8)])
def test_1h_tod_baseline_matches_the_frozen_evaluator(year, end):
    b5, mbb = year
    j = idx(end) - 1
    vals = E.rolling(b5, 12)
    ev = E.tod_above(vals, np.array([j]), NOCHANGE)["C1"]
    base = hz._baseline_tod(CFG, mbb, E.T0 + j * BUCKET, 12, day_type=True)
    want = dt.WEEKEND if E.is_weekend_day(E.start_day(j, 12)) else dt.WEEKDAY
    assert base["day_type"] == want
    for m, pm in (("range", "range_width_pct_median"), ("volume", "volume_notional_usd_sum")):
        assert base["median"][pm] is not None and base["days"][pm] >= 8
        assert float(vals[m][j] > base["median"][pm]) == ev[m][0]
    # price move keeps all days (not evaluated)
    assert base["days"]["price_move_pct_median"] >= 20


def test_maturity_boundary_and_no_lookahead():
    b5 = E.to_5m(panel(36, seed=9))
    mbb = tape(b5, 0, len(b5["o"]) - 1)
    vals = E.rolling(b5, 12)
    first = 8651                                   # the first 1h window with a sample at t - 30d
    for j in (first - 12, first):
        ev = E.rank_all(vals, np.array([j]), 12, NOCHANGE)["C1"]
        ctx = prod_ctx(CFG, mbb, j)
        p = ctx["percentiles"]["range_width_pct_median"]
        if j < first:
            assert np.isnan(ev["range"][0]) and p["tier"] != "mature"
        else:
            assert p["tier"] == "mature" and p["rank"] == pytest.approx(ev["range"][0], abs=1.0 / p["sample_size"])
    # the first weekend window after maturity: Sat 2020-02-01 13:00 sees 9 weekend dates
    # (Jan 4/5, 11/12, 18/19, 25/26 and today's earlier windows)
    sat = idx(datetime(2020, 2, 1, 13, tzinfo=UTC)) - 1
    ctx = prod_ctx(CFG, mbb, sat)
    p = ctx["percentiles"]["range_width_pct_median"]
    assert ctx["day_type"] == dt.WEEKEND and p["same_type_dates"] == 9 and p["tier"] == "mature"
    # a shock after t changes nothing at t
    later = {b: dict(m) for b, m in mbb.items()}
    t = E.T0 + sat * BUCKET
    for b, m in later.items():
        if b > t:
            m["c:volume_notional_usd_sum"] *= 100
    assert prod_ctx(CFG, later, sat)["percentiles"] == ctx["percentiles"]


def test_missing_buckets_keep_c0_gap_semantics_and_never_fall_back():
    b5 = E.to_5m(panel(36, seed=9))
    sat = idx(datetime(2020, 2, 1, 13, tzinfo=UTC)) - 1
    vals = E.rolling(b5, 12)
    # 1) a missing bucket inside the reference: those samples are absent; the rank is the
    #    evaluator's mid-rank over the remaining same-type samples
    gap = frozenset(range(idx(datetime(2020, 1, 11, 6, tzinfo=UTC)), idx(datetime(2020, 1, 11, 7, tzinfo=UTC))))
    mbb = tape(b5, 0, len(b5["o"]) - 1, drop=gap)
    ctx = prod_ctx(CFG, mbb, sat)
    ref = np.arange(sat - E.REF_BUCKETS, sat)
    hit = np.array([any(k in gap for k in range(b - 11, b + 1)) for b in ref])
    same = E.is_weekend_day(E.start_day(ref, 12))
    keep = ref[same & ~hit]
    p = ctx["percentiles"]["range_width_pct_median"]
    assert p["sample_size"] == len(keep) and p["tier"] == "mature"
    assert p["rank"] == pytest.approx(E.mid_rank(vals["range"][keep], vals["range"][sat]), abs=1.0 / len(keep))
    # 2) a whole weekend missing (Jan 25-26): 7 same-type dates -> not mature, no pooled fallback
    day = frozenset(range(idx(datetime(2020, 1, 25, tzinfo=UTC)), idx(datetime(2020, 1, 27, tzinfo=UTC))))
    ctx = prod_ctx(CFG, tape(b5, 0, len(b5["o"]) - 1, drop=day), sat)
    p = ctx["percentiles"]["range_width_pct_median"]
    assert p["same_type_dates"] == 7 and p["tier"] == cx.DAY_TYPE_TIER
    from beta.hour_gate import evaluate_hour
    from beta.interpretation import interpret
    assert evaluate_hour(CFG, ctx)["status"] == "IMMATURE"
    assert interpret(CFG, ctx, horizon="1h")["kind"] in ("INSUFFICIENT_HISTORY", "insufficient") or \
        interpret(CFG, ctx, horizon="1h")["key"] == "insufficient"
    # the pooled V2 rank on the same tape is mature: C1 does not borrow it
    pooled = prod_ctx(CFG_V2, tape(b5, 0, len(b5["o"]) - 1, drop=day), sat)
    assert pooled["percentiles"]["range_width_pct_median"]["tier"] == "mature"
    # 3) a missing bucket inside the current window: no reading at all (unchanged)
    cur_gap = frozenset({sat - 3})
    assert prod_ctx(CFG, tape(b5, 0, len(b5["o"]) - 1, drop=cur_gap), sat) is None
    # 4) TOD: fewer than 8 same-type days -> no median for range/volume, no fallback
    base = hz._baseline_tod(CFG, tape(b5, 0, len(b5["o"]) - 1, drop=day), E.T0 + sat * BUCKET, 12, day_type=True)
    assert base["days"]["range_width_pct_median"] == 6 and base["median"]["range_width_pct_median"] is None


def test_analogue_history_ranks_match_the_frozen_evaluator(year):
    b5, _ = year
    n = 12
    N = len(b5["o"])
    bars = Bars(t0=int(E.T0.timestamp() * 1000), open=b5["o"], high=b5["h"], low=b5["l"], close=b5["c"],
                volume=b5["q"], quote=b5["q"], taker_buy_quote=b5["q"] / 2, oi=np.full(N, np.nan))
    from beta.analogues import window_values
    vals_a = window_values(bars, n)
    day, weekend = window_start_day(bars, n)
    anchors = np.array([idx(e) - 1 for e, _ in CASES_1H])
    ev = E.rank_all(E.rolling(b5, n), anchors, n, NOCHANGE)["C1"]
    for m, pm in PROD.items():
        got = trailing_ranks_day_type(vals_a[pm], anchors, day, weekend)
        np.testing.assert_allclose(got, ev[m], atol=1.0 / 2000)
    assert (weekend[anchors] == E.is_weekend_day(E.start_day(anchors, n))).all()


def test_v2_identity_still_pooled_and_v3_versioned():
    assert cx.verify_versions(CFG)["context_version"] == "BETA_CONTEXT_1H_V3"
    assert cx.CONTEXT_PREDECESSORS["BETA_CONTEXT_1H_V3"] == ("BETA_CONTEXT_1H_V2",)
    assert hz.HORIZON_VERSION == "BETA_HORIZON_TOD_V3" and hz.verify_horizon_digest()
    from beta.analogues import ANALOGUES_VERSION, lookup
    assert ANALOGUES_VERSION == "BETA_ANALOGUES_V2"
    card = {"version": "BETA_ANALOGUES_V1", "windows": {"1h": {"compression": {"n": 50}}}}
    assert lookup(card, "1h", "compression") is None                 # C0 history never answers a C1 label
    assert lookup(dict(card, version="BETA_ANALOGUES_V2"), "1h", "compression")["n"] == 50


def _h1_view(start: datetime, days: int, version: str = hz.HORIZON_VERSION, ratio=None):
    end = start + timedelta(hours=1)
    block = {"complete": True, "window_start": cx.iso(start), "window_end": cx.iso(end),
             "price_move_pct": 0.1, "range_width_pct": 0.5, "volume_notional_usd": 1e8,
             "range_ratio": ratio, "volume_ratio": ratio,
             "baseline_days": {"range_width_pct_median": days, "volume_notional_usd_sum": days,
                               "price_move_pct_median": 25}}
    return {"horizons": {"version": version, "1h": block}}


@pytest.mark.parametrize("start, days, want", [
    (datetime(2026, 10, 10, 10, tzinfo=UTC), 5, 8),   # Sat: 3 weekend dates missing -> Sat, Sun, next Sat
    (datetime(2026, 10, 12, 10, tzinfo=UTC), 5, 3),   # Mon: 3 weekdays missing -> Mon, Tue, Wed
    (datetime(2026, 10, 16, 10, tzinfo=UTC), 6, 4),   # Fri: 2 weekdays missing -> Fri, (Sat, Sun), Mon
    (datetime(2026, 10, 11, 23, tzinfo=UTC), 7, 1),   # Sun 23:00 window: 1 weekend date missing
])
def test_c1_countdown_counts_missing_same_type_dates_not_twenty(start, days, want):
    from beta.formatter import _comparison_suffix, _days_remaining, _day_type_tod, format_1h_tab
    view = _h1_view(start, days)
    block = view["horizons"]["1h"]
    for metric in ("range_width_pct_median", "volume_notional_usd_sum"):
        assert _day_type_tod(view, metric)
        assert _days_remaining(block, metric, True) == want
    assert not _day_type_tod(view, "price_move_pct_median")                 # not evaluated: stays 20-day
    ru = format_1h_tab(CFG, view, "ru")
    assert f"через ~{want} дн." in ru and f"через ~{20 - days} дн." not in ru
    en = _comparison_suffix(block, ratio=None, days_key="range_width_pct_median", lang="en",
                            horizon="1h", day_type=True)
    assert (f"~{want} days" in en) if want > 1 else ("1 day" in en or "day" in en)


def test_c1_countdown_stops_at_eight_and_old_payloads_keep_their_rule():
    from beta.formatter import _days_remaining, _hour_line, format_1h_tab
    sat = datetime(2026, 10, 10, 10, tzinfo=UTC)
    mature = _h1_view(sat, 8)                                    # 8 same-type days: ready, no countdown
    assert _days_remaining(mature["horizons"]["1h"], "range_width_pct_median", True) is None
    assert "через ~" not in format_1h_tab(CFG, mature, "ru")
    assert "н/д" in _hour_line(mature, "ru")                    # ready baseline without a ratio prints n/a
    old = _h1_view(sat, 5, version="BETA_HORIZON_TOD_V2")         # a stored V2 payload re-renders as before
    assert "через ~15 дн." in format_1h_tab(CFG, old, "ru")
    with_ratio = _h1_view(sat, 5, ratio=1.3)
    assert "через ~" not in format_1h_tab(CFG, with_ratio, "ru")
