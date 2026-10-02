"""Pure parts of /catchup and the briefing: window parsing, the Kyiv slot, the
render of the shared view (interpretation labels) and the 4h horizon block."""
from datetime import datetime, timedelta, timezone

import pytest

from test_beta_context import CFG, EXS, T0, cx
from test_beta_context_4h_interpretation import C, _taker_hist

from beta import interpretation as it
from beta.delivery import brief_slot
from beta.formatter import format_catchup
from beta.horizons import HORIZON_VERSION, build_horizons, empty_horizons, verify_horizon_digest
from beta.i18n import assert_descriptive
from beta.market_view import (CATCHUP_DEFAULT_HOURS, VIEW_KINDS, market_block, parse_catchup_hours)
from beta.state_tape import BUCKET, metric_key

UTC = timezone.utc


@pytest.mark.parametrize("arg,hours", [(None, 8), ("", 8), ("3", 3), ("24", 24), ("1", 1), ("6h", 6),
                                       ("6ч", 6), ("0", None), ("25", None), ("x", None), ("-2", None)])
def test_catchup_window_parsing(arg, hours):
    assert parse_catchup_hours(arg) == hours


def test_brief_slot_is_08_kyiv_in_summer_and_winter_time():
    summer = datetime(2026, 7, 1, 4, 59, tzinfo=UTC)               # 07:59 EEST
    assert brief_slot(summer, "08:00") is None
    d, slot = brief_slot(summer + timedelta(minutes=1), "08:00")
    assert (d.isoformat(), slot) == ("2026-07-01", datetime(2026, 7, 1, 5, 0, tzinfo=UTC))
    d, slot = brief_slot(datetime(2026, 12, 1, 6, 30, tzinfo=UTC), "08:00")   # 08:30 EET
    assert slot == datetime(2026, 12, 1, 6, 0, tzinfo=UTC)
    # 00:30 Kyiv: the previous day's slot is gone and today's has not come yet
    assert brief_slot(datetime(2026, 12, 1, 22, 30, tzinfo=UTC), "08:00") is None


def _view(kind="catchup", market=None, status="NO ACTIVE EVENTS"):
    return {"product_status": status, "kind": kind, "now": {"reference_price": 84133.0},
            "data_through": "2026-10-01T16:00:00Z", "horizons": None, "market": market}


def _market(h1, h4, *, events=(), levels=None):
    return {"version": "BETA_MARKET_VIEW_V1", "window_hours": 8, "complete": True,
            "window": {"price_complete": True, "price_move_pct": 1.24, "range_width_pct": 2.1,
                       "low": 83100.0, "high": 84900.0, "volume_notional_usd": 1.4e10, "oi_change_pct": -0.4},
            "events": list(events), "interpretation": {"1h": h1, "4h": h4},
            "levels": levels or {"1h": {"range_width_pct_median": "high"}, "4h": {}}}


def test_catchup_renders_window_events_labels_and_data_time_in_both_languages():
    h1 = it.interpret(CFG, C(0.92, 0.08, 0.90), horizon="1h")
    h4 = it.interpret(CFG, C(0.5, 0.5, 0.5, rng=0.1), horizon="4h")
    ev = [{"event_type": "TAKER_FLOW_EXTREME_BUY", "triggered_at": "2026-10-01T15:50:00Z"}]
    ru = format_catchup(CFG, _view(market=_market(h1, h4, events=ev)), "ru")
    lines = ru.split("\n")
    assert lines[0] == "<b>BTC 84 133 · за 8 ч</b>"
    assert lines[1] == "8 ч: +1,2% · диапазон 2,1% (83 100–84 900) · объём $14 млрд · OI −0,4%"
    assert lines[2] == "События: агрессивные покупки 18:50"
    assert lines[3] == "1ч: похоже на выход шортов · диапазон высокий"
    assert lines[4] == "4ч: сжатие"
    assert lines[-1] == "данные 19:00 (Киев)"
    en = format_catchup(CFG, _view(kind="brief", market=_market(h1, h4)), "en")
    assert en.startswith("<b>Morning · BTC 84,133 · last 8h</b>")
    assert "No detector events" in en and "1h: looks like shorts exiting · range high" in en
    for text, lang in ((ru, "ru"), (en, "en")):
        assert_descriptive(text, lang)


def test_catchup_fails_closed_and_degrades_per_part():
    ru = format_catchup(CFG, _view(status="DATA STALE", market=_market(None, None)), "ru")
    assert "нельзя" in ru.lower() or "недостаточно" in ru.lower()
    assert "похоже" not in ru
    incomplete = _market(it.interpret(CFG, None, horizon="1h"),
                         it.interpret(CFG, C(0.92, 0.08, 0.9, tier="building"), horizon="4h"))
    incomplete["window"] = {"price_complete": False}
    ru = format_catchup(CFG, _view(market=incomplete), "ru")
    assert "8 ч: неполные данные" in ru and "1ч: н/д" in ru and "4ч: мало истории" in ru


def test_view_kinds_and_default_window():
    assert VIEW_KINDS == ("btc", "catchup", "brief") and CATCHUP_DEFAULT_HOURS == 8


# ---- 4h horizon block (BETA_HORIZON_TOD_V2) ---------------------------------------------------
def test_horizon_v2_adds_a_4h_block_and_keeps_1h_and_24h():
    assert HORIZON_VERSION == "BETA_HORIZON_TOD_V2" and verify_horizon_digest()
    assert empty_horizons()["4h"] is None
    n = int(timedelta(days=31, hours=24) / BUCKET)
    hist = dict(_taker_hist(n, T0))
    as_of = T0 + (n - 1) * BUCKET
    h = build_horizons(CFG, as_of_bucket=as_of, metrics_by_bucket=hist)
    four, one = h["4h"], h["1h"]
    assert four["complete"] and one["complete"]
    assert four["window_start"] == cx.iso(as_of - 47 * BUCKET) and four["window_end"] == one["window_end"]
    assert four["volume_notional_usd"] == pytest.approx(48e6)
    assert four["taker_delta_notional_usd_sum"] == pytest.approx(48 * 1e5)
    assert four["baseline_days"]["volume_notional_usd_sum"] >= 20
    assert four["volume_ratio"] == pytest.approx(1.0)
    del hist[as_of - 30 * BUCKET]
    h = build_horizons(CFG, as_of_bucket=as_of, metrics_by_bucket=hist)
    assert h["4h"]["complete"] is False and h["1h"]["complete"] is True   # 1h does not need that bucket
    assert h["4h"]["liquidations"]["buckets_missing"] is True


def test_market_block_window_and_stale_context_is_not_interpreted():
    n = int(timedelta(days=31, hours=24) / BUCKET)
    hist = dict(_taker_hist(n, T0))
    as_of = T0 + (n - 1) * BUCKET
    tape = {"as_of": as_of, "metrics": hist, "oi": {}}
    stale = {"context_1h": dict(C(0.92, 0.08, 0.9), window_end=cx.iso(as_of)),   # one bucket behind
             "context_4h": None, "open": {}, "last_ended": {}}
    block = market_block(CFG, {}, stale, tape, window_hours=8, episodes=[])
    assert block["window"]["price_complete"] and block["window"]["window_end"] == cx.iso(as_of + BUCKET)
    assert block["interpretation"]["1h"]["kind"] == it.DATA_MISSING
    fresh = dict(stale, context_1h=dict(C(0.92, 0.08, 0.9), window_end=cx.iso(as_of + BUCKET)))
    assert market_block(CFG, {}, fresh, tape, window_hours=8, episodes=[])["interpretation"]["1h"]["label"] == "short_exit"
    eps = [{"event_type": "PRICE_OI_CONTRACTION_DOWN", "opened_bucket": as_of - 3 * BUCKET,
            "last_bucket": as_of - 2 * BUCKET, "triggered_at": as_of - BUCKET, "terminal_at": None},
           {"event_type": "PRICE_OI_CONTRACTION_UP", "opened_bucket": as_of - timedelta(hours=9),
            "last_bucket": as_of - timedelta(hours=9), "triggered_at": as_of - timedelta(hours=9),
            "terminal_at": None}]
    events = market_block(CFG, {}, fresh, tape, window_hours=8, episodes=eps)["events"]
    assert [e["event_type"] for e in events] == ["PRICE_OI_CONTRACTION_DOWN"]    # only inside the window
    assert market_block(CFG, {}, fresh, None, window_hours=8, episodes=eps)["complete"] is False


# ---- recorded-tape dry run (pure) ----------------------------------------------------------------
def _synthetic_tape(days, *, start=T0, seed=3, mixed_calm=False):
    import random
    rng = random.Random(seed)
    out, oi_rows, price, oi = {}, [], 100.0, 1000.0
    for i in range(days * 288):
        b = start + i * BUCKET
        move = rng.gauss(0, 0.001)
        m = {"c:volume_notional_usd_sum": 1e6 * (1 + rng.random()), "c:taker_delta_notional_usd_sum": move * 1e9}
        for j, ex in enumerate(EXS):
            v = (move + (0.0003 if j == 0 else -0.0003)) if mixed_calm else move
            m.update({metric_key(ex, "kline_open"): price, metric_key(ex, "kline_close"): price * (1 + v),
                      metric_key(ex, "kline_high"): price * (1 + abs(v) + 0.0005),
                      metric_key(ex, "kline_low"): price * (1 - abs(v) - 0.0005)})
        price *= 1 + move
        out[b] = m
        oi *= 1 + rng.gauss(0, 0.001)
        for ex in EXS:
            oi_rows.append({"exchange": ex, "ts": b, "oi_raw": oi, "oi_unit": "base", "contract_value": None})
    return out, oi_rows


def test_dry_run_counts_every_sample_and_reports_the_divergence_gate():
    from beta.dry_run import run_dry_run, sample_grid
    from test_beta_context_4h_interpretation import IDENT
    metrics, oi_rows = _synthetic_tape(4)
    end = max(metrics)
    samples = sample_grid(end - timedelta(hours=6), end, 12)
    rep = run_dry_run(CFG, sample_buckets=samples, metrics_by_bucket=metrics, oi_rows=oi_rows,
                      liquidation_episodes=[], identity=IDENT, code_version="t",
                      tiers={"none_below_days": 3, "low_below_days": 7, "building_below_days": 30})
    assert rep["status"] == "PRODUCTION_MATURITY_RULES" and rep["samples"] == len(samples)
    assert sum(v["n"] for v in rep["frequencies"]["1h"].values()) == len(samples)
    assert set(rep["frequencies"]["4h"]) == {"insufficient"}       # 4 days of history is not mature
    prov = run_dry_run(CFG, sample_buckets=samples, metrics_by_bucket=metrics, oi_rows=oi_rows,
                       liquidation_episodes=[], identity=IDENT, code_version="t",
                       tiers={"none_below_days": 3, "low_below_days": 7, "building_below_days": 30},
                       ignore_maturity=True)
    assert prov["status"] == "PROVISIONAL_RANKS_IGNORE_MATURITY"
    assert "insufficient" not in prov["frequencies"]["1h"]
    from beta.dry_run import RENDER_CATEGORIES
    for r in (rep, prov):
        assert sum(r["kinds"]["1h"].values()) == r["samples"] == sum(r["kinds"]["4h"].values())
        cats = [x["category"] for x in r["rendered_catchup_ru"]]
        assert len(cats) == len(set(cats)) and set(cats) <= set(RENDER_CATEGORIES)
        assert all(assert_descriptive(x["ru"], "ru") for x in r["rendered_catchup_ru"])
    assert "degraded" in [x["category"] for x in rep["rendered_catchup_ru"]]     # immature ranks
    for h in ("1h", "4h"):
        for key, ex in prov["examples"][h].items():
            assert ex and all(assert_descriptive(e["ru"], "ru") for e in ex)


def test_dry_run_calm_mixed_venue_signs_are_counted_but_not_labelled():
    from beta.dry_run import run_dry_run, sample_grid
    from test_beta_context_4h_interpretation import IDENT
    metrics, oi_rows = _synthetic_tape(4, mixed_calm=True)
    end = max(metrics)
    rep = run_dry_run(CFG, sample_buckets=sample_grid(end - timedelta(hours=12), end, 12),
                      metrics_by_bucket=metrics, oi_rows=oi_rows, liquidation_episodes=[], identity=IDENT,
                      code_version="t", tiers={"none_below_days": 3, "low_below_days": 7,
                                               "building_below_days": 30}, ignore_maturity=True)
    flat = rep["calm_mixed_venue_signs_not_labelled"]
    labelled = {h: rep["venues_diverge"][h]["n"] for h in ("1h", "4h")}
    for h in ("1h", "4h"):
        for case in rep["venues_diverge"][h]["cases"]:
            assert case["price_band"] in ("up", "down")            # only after an unusual aggregate move
            assert {"oi", "taker", "by_venue", "rendered_ru"} <= set(case)
        assert rep["mixed_venue_signs_passed_gate"].get(h, 0) >= labelled[h]
    assert sum(flat.values()) + sum(labelled.values()) >= 1
