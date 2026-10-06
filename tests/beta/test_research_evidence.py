"""Research evidence integration (owner task 2026-10-04): the engine recognises the frozen states of
closed research units live, words them by status, keeps the hierarchy and the NOT_CONFIRMED veto,
never fabricates evidence from a missing or stale source, and never changes forecasts or gating.
Offline; synthetic data and the committed research code only."""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from beta import research_evidence as RE
from beta import research_states as RS
from beta.hist_series import BAR_MS, Bars
from beta.research_link import load_findings, validate

UTC = timezone.utc
HOUR = 3_600_000
DAY = 86_400_000
T0 = int(datetime(2026, 9, 1, tzinfo=UTC).timestamp() * 1000)
CUTS = RE.load_cuts()
FINDINGS = load_findings()
BY_ID = {f["id"]: f for f in FINDINGS}
LIVE_IDS = {"D7", "D2", "DH3-P3", "DH3-V3", "D12", "DH3-P1", "DH3-O2", "DH3-L3", "DH3-S1", "DH3-V2", "R03-C1",
            "H03", "H02", "DH1-L2", "DH2-L1", "DH2-L3", "DH3-P2", "DH3-L1", "DH3-L2", "DH3-O1", "DH3-O3", "DH3-V1",
            "DH3-S3", "DH2-B2", "MARKET-02", "MARKET-01", "H05", "H04", "R03-A1", "R03-A4", "R03-C2-C4", "H01"}


# ---- helpers ------------------------------------------------------------------------------------
def bars(close, *, t0=T0, spread=0.0005, quote=1e6):
    close = np.asarray(close, dtype=float)
    n = close.size
    op = np.r_[close[0], close[:-1]]
    hi = np.maximum(op, close) * (1 + spread)
    lo = np.minimum(op, close) * (1 - spread)
    q = np.full(n, float(quote))
    return Bars(t0=t0, open=op, high=hi, low=lo, close=close, volume=q / close, quote=q,
                taker_buy_quote=q / 2, oi=np.full(n, np.nan))


def walk(n, *, seed=1, vol=0.001, start=60000.0):
    rng = np.random.default_rng(seed)
    return start * np.exp(np.cumsum(rng.normal(0, vol, n)))


def src(*names, reason=None):
    return {n: {"present": True, "as_of": "2026-10-01T00:00:00+00:00", "reason": reason} for n in names}


def ids(ev):
    return {m["finding_id"] for m in ev["matches"]}


def evaluate(**kw):
    return RE.evaluate(RE.EvidenceInputs(**kw), cuts=CUTS)


# ---- registry and frozen cuts ---------------------------------------------------------------------
def test_live_blocks_are_valid_and_cover_exactly_the_audited_live_findings():
    assert validate(FINDINGS) == []
    live = {f["id"] for f in FINDINGS if f.get("live")}
    assert live == LIVE_IDS
    assert not (live & set(RE.NOT_LIVE))                        # D11, DIVERGENCE, … stay in /research
    assert BY_ID["C012"]["status"] == "UNDERPOWERED" and "live" not in BY_ID["C012"]
    for fid in live:                                            # every live state has a matcher and sources
        assert BY_ID[fid]["live"]["state"] in RE.STATE_SOURCES, fid


def test_an_underpowered_finding_can_never_be_live_evidence():
    from beta.research_link import validate_live
    bad = {**BY_ID["DH3-P1"], "id": "X", "status": "UNDERPOWERED"}
    assert any("can never be live evidence" in p for p in validate_live(bad))
    assert "X" not in RE.live_findings([bad])


def test_the_frozen_cut_points_come_from_the_research_surfaces_and_reproduce_their_states():
    body = json.loads(RE.CUTS_PATH.read_text())
    prereg = (RE.CUTS_PATH.parent.parent / "docs/research/DH3_PREREG.json").read_bytes()
    assert body["dh3_prereg_sha256"] == hashlib.sha256(prereg).hexdigest()
    assert body["outcomes_read"] is False
    assert all(c["MATCH"] for c in body["recount_checks"].values())      # the cut reproduces each recorded N
    assert body["recount_checks"]["DH3-P3"]["RECOUNT_N_STATE"] == 7109
    for name in ("P1_QUIET_RANGE_MAX", "P1_DOI4_MIN", "P2_DOI1_MAX", "P3_CROWD_Z_LONG_MIN", "P3_CROWD_Z_SHORT_MAX",
                 "L1_DEPTH_RATIO_MAX", "L2_ASYM_BID_HEAVY_MIN", "L2_ASYM_ASK_HEAVY_MAX", "L3_RECOVERY_MAX",
                 "O1_IMPLIED_REALIZED_MIN", "O2_DVOL_JUMP_MIN", "S3_LARGE_PRINTS_Q67", "S_STRESS_HOUR_LOG_RANGE_MIN"):
        assert math.isfinite(CUTS[name]), name


# ---- each live state matches the right market, and not the wrong one --------------------------------
def _hourly_bars(n_hours=40, *, quiet=False, seed=2):
    c = walk(n_hours * 12 + 400, seed=seed, vol=0.00005 if quiet else 0.002)
    return bars(c, spread=0.00002 if quiet else 0.001)


def _now(b):
    return b.t0 + b.n * BAR_MS + 60_000 - (b.t0 + b.n * BAR_MS) % HOUR


def test_oi_build_up_in_a_quiet_market_matches_p1_and_a_flat_oi_does_not():
    b = _hourly_bars(quiet=True)
    now = b.end_ms - b.end_ms % HOUR + 60_000
    j = RS.last_hour_index(b, now)
    oi = np.full(b.n, 80000.0)
    rising = oi.copy()
    rising[j] = rising[j - 48] * math.exp(CUTS["P1_DOI4_MIN"] + 0.01)
    ev = evaluate(now_ms=now, bars=b, oi=rising, sources=src("oi", "bars"))
    m = [x for x in ev["matches"] if x["finding_id"] == "DH3-P1"]
    assert m and m[0]["status"] == "WEAK" and m[0]["sample_size"] == 12397
    assert "13%" in m[0]["historical_effect"]["ru"] and m[0]["topic"] == "RANGE_4H"
    assert "DH3-P1" not in ids(evaluate(now_ms=now, bars=b, oi=oi, sources=src("oi", "bars")))
    loud = _hourly_bars(quiet=False)
    assert "DH3-P1" not in ids(evaluate(now_ms=now, bars=loud, oi=rising, sources=src("oi", "bars")))


def test_crowd_positioning_matches_p3_on_both_arms_with_their_own_numbers():
    b = _hourly_bars(n_hours=800, seed=4)
    now = b.end_ms - b.end_ms % HOUR + 60_000
    j = RS.last_hour_index(b, now)
    rng = np.random.default_rng(1)
    ls = 1.5 + rng.normal(0, 0.05, b.n)
    for k in range(1, 10):                                       # the other hours of the window: neutral
        ls[j - 12 * k] = 1.5
    for arm, shift, effect in (("CROWD_LONG", +0.3, "48% против 54%"), ("CROWD_SHORT", -0.3, "54% против 48%")):
        x = ls.copy()
        x[j] = 1.5 + shift
        ev = evaluate(now_ms=now, bars=b, ls=x, sources=src("ls_ratio", "bars"))
        m = next(x for x in ev["matches"] if x["finding_id"] == "DH3-P3")
        assert m["live_state"]["arm"] == arm and m["status"] == "DISCOVERY" and effect in m["historical_effect"]["ru"]
    x = ls.copy()
    x[j] = 1.5
    assert "DH3-P3" not in ids(evaluate(now_ms=now, bars=b, ls=x, sources=src("ls_ratio", "bars")))


def test_dvol_states_match_o1_o2_o3_only_when_they_hold():
    b = _hourly_bars(n_hours=40, seed=6)
    now = b.end_ms - b.end_ms % HOUR + 60_000
    T = now - 60_000
    base = {T - (k + 1) * HOUR: 50.0 for k in range(30)}
    calm = evaluate(now_ms=now, bars=b, dvol_at=base, sources=src("dvol", "bars"))
    assert not ({"DH3-O2"} & ids(calm))
    jump = dict(base)
    jump[T - HOUR] = 50.0 * math.exp(CUTS["O2_DVOL_JUMP_MIN"] + 0.02)
    ev = evaluate(now_ms=now, bars=b, dvol_at=jump, sources=src("dvol", "bars"))
    assert "DH3-O2" in ids(ev)
    m = next(x for x in ev["matches"] if x["finding_id"] == "DH3-O2")
    assert m["status"] == "WEAK" and "10%" in m["historical_effect"]["ru"]


def test_book_states_match_l1_l2_and_a_snapshot_older_than_ten_minutes_is_not_used():
    b = _hourly_bars(n_hours=200, seed=8)
    now = b.end_ms - b.end_ms % HOUR + 60_000
    T = RS.decision_ms(b, RS.last_hour_index(b, now))
    snaps = np.arange(b.t0, T + 1, 300_000) - 30_000                 # 30 s before each bar close, up to T
    snaps = snaps[snaps > b.t0]
    k = snaps.size - 1                                               # the snapshot used at T
    flat = np.full(snaps.size, 1e8)
    bid = flat.copy()
    bid[k] = 3e8                                                     # bid-heavy at T
    book = RS.book_on_grid(snaps, bid, flat, b.t0, b.n)
    ev = evaluate(now_ms=now, bars=b, book=book, sources=src("depth", "bars"))
    m = next(x for x in ev["matches"] if x["finding_id"] == "DH3-L2")
    assert m["live_state"]["arm"] == "BID_HEAVY" and m["status"] == "NOT_CONFIRMED"
    assert m["interpretation_direction"] == "REFUTES" and "49,5% против 49,7%" in m["historical_effect"]["ru"]
    assert "DH3-L1" not in ids(ev)
    thin = flat.copy()
    thin[k] = 3e7
    assert "DH3-L1" in ids(evaluate(now_ms=now, bars=b, book=RS.book_on_grid(snaps, thin, thin, b.t0, b.n),
                                    sources=src("depth", "bars")))
    keep = snaps <= T - 11 * 60_000                                  # the newest snapshot is 11+ minutes old at T
    old = RS.book_on_grid(snaps[keep], bid[keep], flat[keep], b.t0, b.n)
    ev = evaluate(now_ms=now, bars=b, book=old, sources=src("depth", "bars"))
    assert not ({"DH3-L1", "DH3-L2"} & ids(ev))
    assert {"DH3-L1", "DH3-L2"} <= {u["finding_id"] for u in ev["unavailable"]}


def test_stress_hours_match_s1_s3_from_their_stored_features():
    b = _hourly_bars(n_hours=10, seed=3)
    now = b.end_ms - b.end_ms % HOUR + 60_000
    hour = now - 60_000 - HOUR
    row = {"hour_ms": hour, "perp_log_range": CUTS["S_STRESS_HOUR_LOG_RANGE_MIN"] + 0.01, "status": "OK",
           "lead_score": -0.2, "n_large_perp": 60}
    ev = evaluate(now_ms=now, bars=b, stress=[row], sources=src("stress", "bars"))
    s1 = next(x for x in ev["matches"] if x["finding_id"] == "DH3-S1")
    assert s1["live_state"]["arm"] == "SPOT_LED" and "уже" in s1["historical_effect"]["ru"]
    assert "DH3-S3" in ids(ev)
    calm = {**row, "perp_log_range": CUTS["S_STRESS_HOUR_LOG_RANGE_MIN"] - 0.001}
    assert not ({"DH3-S1", "DH3-S3"} & ids(evaluate(now_ms=now, bars=b, stress=[calm], sources=src("stress", "bars"))))
    perp = {**row, "lead_score": 0.3, "n_large_perp": 10}
    ev = evaluate(now_ms=now, bars=b, stress=[perp], sources=src("stress", "bars"))
    assert next(x for x in ev["matches"] if x["finding_id"] == "DH3-S1")["live_state"]["arm"] == "PERP_LED"
    assert "DH3-S3" not in ids(ev)


def test_d2_matches_only_after_a_day_above_its_trailing_p90():
    b = _hourly_bars(n_hours=30, seed=2)
    now = b.end_ms - b.end_ms % DAY + 6 * HOUR
    today = now - now % DAY
    days = [(today - (300 - k) * DAY, 0.02 + 0.001 * (k % 7)) for k in range(300)]
    hot = days + [(today, 0.05)]
    ev = evaluate(now_ms=now, bars=b, daily_rv=hot, sources=src("bars_daily", "bars"))
    m = next(x for x in ev["matches"] if x["finding_id"] == "D2")
    assert m["status"] == "CONFIRMED" and "4,0% против 2,6%" in m["historical_effect"]["ru"]
    assert datetime.fromisoformat(m["valid_until"]) == datetime.fromtimestamp((today + 5 * 60_000) / 1000, UTC) + timedelta(hours=24)
    cool = days + [(today, 0.021)]
    assert "D2" not in ids(evaluate(now_ms=now, bars=b, daily_rv=cool, sources=src("bars_daily", "bars")))


def test_d7_matches_only_when_the_view_shows_the_d7_hour():
    b = _hourly_bars(n_hours=5)
    now = b.end_ms - b.end_ms % HOUR + 60_000
    end = datetime.fromtimestamp((now - 60_000) / 1000, UTC)
    shown = {"shown": True, "hour_start": (end - timedelta(hours=1)).isoformat(), "hour_end": end.isoformat()}
    assert "D7" in ids(evaluate(now_ms=now, bars=b, regime=shown, sources=src("bars", "d7")))
    assert "D7" not in ids(evaluate(now_ms=now, bars=b, regime={**shown, "shown": False}, sources=src("bars", "d7")))


def test_an_extreme_15_minute_impulse_matches_h03_and_a_normal_one_does_not():
    c = walk(31 * 288 + 12, seed=11, vol=0.0008)
    n = c.size - c.size % 3
    c = c[:n]
    quiet = bars(c, t0=T0)
    t15, _ = RS.grid15_closes(quiet)
    now = int(t15[-1]) + 60_000
    assert "H03" not in ids(evaluate(now_ms=now, bars=quiet, sources=src("bars")))
    c2 = c.copy()
    c2[-3:] = c2[-4] * np.array([1.006, 1.012, 1.02])
    ev = evaluate(now_ms=now, bars=bars(c2, t0=T0), sources=src("bars"))
    m = next(x for x in ev["matches"] if x["finding_id"] == "H03")
    assert m["status"] == "NOT_CONFIRMED" and m["live_state"]["arm"] == "UP" and "move_alert" in m["surfaces"]


def test_a_taker_skew_matches_h05_from_complete_buckets_only():
    n = RS.REF_STEPS_15 + 10
    rng = np.random.default_rng(2)
    total = np.full(n, 100.0)
    buy = 50 + rng.normal(0, 3, n)
    buy[-1] = 95.0
    end = T0 + n * RS.GRID15_MS
    flow = {"bucket_ms": T0 + np.arange(n, dtype=np.int64) * RS.GRID15_MS, "buy": buy, "total": total}
    ev = evaluate(now_ms=end + 60_000, flow15=flow, sources=src("flow15"))
    m = next(x for x in ev["matches"] if x["finding_id"] == "H05")
    assert m["live_state"]["arm"] == "BUY" and m["status"] == "NOT_CONFIRMED"
    buy2 = buy.copy()
    buy2[-1] = np.nan                                            # the last bucket is incomplete
    ev = evaluate(now_ms=end + 60_000, flow15={**flow, "buy": buy2}, sources=src("flow15"))
    assert "H05" not in ids(ev)


def test_market_01_02_need_the_impulse_the_oi_expansion_and_their_own_continuation_arm():
    c = walk(31 * 288 + 20, seed=13, vol=0.0007)
    oi = np.full(c.size, 80000.0) * np.exp(np.cumsum(np.random.default_rng(5).normal(0, 0.0005, c.size)))
    t = c.size - 1
    c[t - 12:t - 5] = c[t - 13] * np.linspace(1.0, 1.02, 7)        # a 30m impulse ending at t-6
    c[t - 5:] = c[t - 6] * np.linspace(1.0, 1.006, 6)            # continuation over the next 30m
    oi[t] = oi[t - 6] * 1.02
    b = bars(c)
    ev = evaluate(now_ms=b.end_ms + 60_000, bars=b, oi=oi, sources=src("bars", "oi"))
    assert "MARKET-02" in ids(ev) and "MARKET-01" not in ids(ev)
    c2 = c.copy()
    c2[t - 5:] = c2[t - 6]                                       # stalls
    ev = evaluate(now_ms=b.end_ms + 60_000, bars=bars(c2), oi=oi, sources=src("bars", "oi"))
    assert "MARKET-01" in ids(ev)


def test_level_touch_states_and_the_alert_evidence():
    c = walk(288 * 10, seed=17, vol=0.0008)
    b = bars(c)
    lvl = float(np.nanmax(b.high[-288 * 2:-288])) * 1.0001
    payload = {"at": datetime.fromtimestamp((b.end_ms - 60_000) / 1000, UTC).isoformat(), "level_kind": "PDH",
               "level": lvl, "side": 1}
    alone = RE.for_level_touch(None, b, payload, levels=[{"kind": "PDH", "price": lvl}], now_ms=b.end_ms)
    assert {m["finding_id"] for m in alone} <= {"DH3-V2", "DH2-L3"} and "DH3-V2" in {m["finding_id"] for m in alone}
    zone = RE.for_level_touch(None, b, payload, levels=[{"kind": "PDH", "price": lvl}, {"kind": "ROUND", "price": lvl * 1.001}],
                              now_ms=b.end_ms)
    assert "DH1-L2" in {m["finding_id"] for m in zone}
    far = RE.for_level_touch(None, b, payload, levels=[{"kind": "PDH", "price": lvl}, {"kind": "ROUND", "price": lvl * 1.01}],
                             now_ms=b.end_ms)
    assert "DH1-L2" not in {m["finding_id"] for m in far}


def test_calendar_states():
    sat = int(datetime(2026, 10, 3, 10, tzinfo=UTC).timestamp() * 1000)
    ev = evaluate(now_ms=sat, weekend=True, sources=src("calendar"))
    assert "R03-C1" in ids(ev)
    fri = int(datetime(2026, 10, 2, 6, tzinfo=UTC).timestamp() * 1000)
    ev = evaluate(now_ms=fri, events=[{"kind": "EXPIRY_WEEKLY"}], sources=src("calendar"))
    assert {"R03-A1", "R03-A4", "R03-C2-C4"} <= ids(ev)
    tue = int(datetime(2026, 9, 29, 6, tzinfo=UTC).timestamp() * 1000)
    assert not ({"R03-C1", "R03-A1", "R03-C2-C4", "D12"} & ids(evaluate(now_ms=tue, sources=src("calendar"))))
    after_dst = int(datetime(2026, 11, 3, 9, tzinfo=UTC).timestamp() * 1000)       # US clocks changed 2026-11-01
    assert "D12" in ids(evaluate(now_ms=after_dst, sources=src("calendar")))


# ---- a missing or stale source never becomes evidence ------------------------------------------------
def test_a_missing_observable_is_unavailable_never_fabricated():
    b = _hourly_bars(n_hours=40, quiet=True)
    now = b.end_ms - b.end_ms % HOUR + 60_000
    ev = evaluate(now_ms=now, bars=b, sources=src("bars"))
    un = {u["finding_id"]: u["reason"] for u in ev["unavailable"]}
    for fid in ("DH3-P1", "DH3-P3", "DH3-O2", "DH3-L2", "DH3-S1", "DH2-B2", "D2", "D7", "H05"):
        assert fid not in ids(ev) and fid in un, fid
    assert un["DH3-P3"].startswith("NO_DATA") and {x["finding_id"] for x in ev["not_live"]} == set(RE.NOT_LIVE)


def test_a_stale_or_unchecked_source_is_not_current_evidence():
    b = _hourly_bars(quiet=True)
    now = b.end_ms - b.end_ms % HOUR + 60_000
    j = RS.last_hour_index(b, now)
    oi = np.full(b.n, 80000.0)
    oi[j] = oi[j - 48] * math.exp(CUTS["P1_DOI4_MIN"] + 0.01)
    for reason in ("STALE", "DEFINITION_PENDING", "DEFINITION_FAILED"):
        ev = evaluate(now_ms=now, bars=b, oi=oi, sources={**src("bars"), **src("oi", reason=reason)})
        assert "DH3-P1" not in ids(ev)
        assert next(u for u in ev["unavailable"] if u["finding_id"] == "DH3-P1")["reason"].startswith(reason)


# ---- wording by status ------------------------------------------------------------------------------
def _m(fid, key, **kw):
    f = RE.live_findings()[fid]
    return RE._match(f, key=key, values=kw.pop("values", {}), at_ms=kw.pop("at", T0), sources={}, **kw).to_dict()


@pytest.mark.parametrize("lang", ["ru", "en"])
def test_wording_by_status(lang):
    from beta.research_render import line
    d2 = line(_m("D2", "D2_HIGH_RV_DAY", values={"rv_pct": 4.1, "p90_pct": 3.2}), lang)
    assert ("Проверено на двух биржах" if lang == "ru" else "Tested on two venues") in d2 and d2.endswith("(D2).")
    p3 = line(_m("DH3-P3", "P3_CROWD", arm="CROWD_LONG", values={"z": 1.6}), lang)
    assert ("Гипотеза" if lang == "ru" else "Hypothesis") in p3
    assert ("не подтверждено" if lang == "ru" else "not confirmed") in p3
    assert "Проверено" not in p3 and "Tested" not in p3                     # a discovery is never «Проверено»
    p1 = line(_m("DH3-P1", "P1_LEVERAGE_LOADING", values={"doi4_pct": 0.9, "range4_pct": 0.5}), lang)
    assert ("ниже нашего порога практической величины" if lang == "ru" else "below our materiality bar") in p1
    l2 = line(_m("DH3-L2", "L2_BOOK_SKEW", arm="BID_HEAVY", values={"bid_usd": 3e8, "ask_usd": 1e8}), lang)
    assert ("эффекта не нашла" if lang == "ru" else "found no effect") in l2
    assert not re.search(r"рост вероятен|вероятно рост|likely to rise|buy|купи", l2, re.I)


def test_every_live_state_template_renders_with_its_values():
    from beta.research_render import state_text
    sample = {"doi4_pct": 1.0, "range4_pct": 0.4, "doi1_pct": -3.0, "z": 1.5, "ratio": 2.0, "dvol": 55.0,
              "jump_pct": 2.0, "corr": 0.3, "ratio_pct": 80.0, "bid_usd": 2e8, "ask_usd": 1e8, "recovery_pct": 70.0,
              "move_end": "10:15", "hour": "09:00", "range_pct": 2.1, "n": 40, "kind": "PDH", "price": 64000.0,
              "side": 1, "window_min": 15, "ret_pct": 0.8, "top_pct": 3.0, "lookback_min": 60, "lookback_h": 8,
              "depth_pct": 30.0, "imbalance_pct": 40.0, "impulse_pct": 1.1, "continuation": 0.5, "rv_pct": 4.0,
              "p90_pct": 3.0, "hour_start": "09:00", "hour_end": "10:00", "kinds": ["PDH", "ROUND"], "days_ago": 1}
    arms = {"P3_CROWD": ("CROWD_LONG", "CROWD_SHORT"), "L2_BOOK_SKEW": ("BID_HEAVY", "ASK_HEAVY"),
            "S1_STRESS_LEADER": ("SPOT_LED", "PERP_LED"), "H05_TAKER_SKEW": ("BUY", "SELL"),
            "R03_US_OPEN_CLOSE": ("MONDAY_OPEN", "FRIDAY_CLOSE")}
    for fid, f in RE.live_findings().items():
        key = f["live"]["state"]
        for arm in arms.get(key, (None,)):
            for lang in ("ru", "en"):
                text = state_text(_m(fid, key, arm=arm, values=sample), lang)
                assert "{" not in text and text != key, (fid, arm, lang, text)


# ---- hierarchy, veto, limits ---------------------------------------------------------------------------
def test_the_hierarchy_resolves_a_topic_conflict_and_a_surface_shows_at_most_two():
    now = datetime.fromtimestamp(T0 / 1000, UTC) + timedelta(minutes=30)
    ms = [_m("DH3-P1", "P1_LEVERAGE_LOADING", values={"doi4_pct": 1, "range4_pct": 0.3}),     # WEAK, RANGE_4H
          _m("DH3-S1", "S1_STRESS_LEADER", arm="SPOT_LED", values={"hour": "09:00", "range_pct": 2}),  # WEAK, RANGE_4H
          _m("DH3-L1", "L1_THIN_BOOK", values={"ratio_pct": 70}),                              # NOT_CONF, RANGE_4H
          _m("DH3-P3", "P3_CROWD", arm="CROWD_LONG", values={"z": 1.6}),                      # DISCOVERY, DIRECTION
          _m("DH3-L2", "L2_BOOK_SKEW", arm="BID_HEAVY", values={"bid_usd": 2e8, "ask_usd": 1e8}),
          _m("D2", "D2_HIGH_RV_DAY", values={"rv_pct": 4, "p90_pct": 3})]                     # CONFIRMED, RANGE_24H
    ev = {"matches": ms}
    sel = RE.select(ev, "btc", limit=2, now=now)
    assert [m["finding_id"] for m in sel] == ["D2", "DH3-P3"]            # CONFIRMED first, then DISCOVERY
    risk = RE.select(ev, "risk", limit=2, now=now, topics=("RANGE_4H", "RANGE_24H"))
    assert [m["finding_id"] for m in risk] == ["D2", "DH3-P1"]          # one per topic: P1 (WEAK) over L1 (NOT_CONF)
    assert len(RE.select(ev, "details", limit=99, now=now)) == 3       # one per topic even in a full list
    from beta.research_render import details_text
    full = details_text(ev, "ru", now=now)
    assert all(f"<b>{m['finding_id']}</b>" in full for m in ms)        # Details shows the extended set


def test_a_not_confirmed_finding_vetoes_a_supporting_claim_of_the_same_mechanism():
    p1 = {**BY_ID["DH3-P1"], "live": {**BY_ID["DH3-P1"]["live"], "mechanism": "same"}}
    p2 = {**BY_ID["DH3-P2"], "live": {**BY_ID["DH3-P2"]["live"], "mechanism": "same"}}
    b = _hourly_bars(quiet=True)
    now = b.end_ms - b.end_ms % HOUR + 60_000
    j = RS.last_hour_index(b, now)
    oi = np.full(b.n, 80000.0)
    oi[j] = oi[j - 48] * math.exp(CUTS["P1_DOI4_MIN"] + 0.01)
    oi[j - 12] = oi[j] * math.exp(-CUTS["P2_DOI1_MAX"] + 0.01)          # a sharp one-hour drop as well
    ev = RE.evaluate(RE.EvidenceInputs(now_ms=now, bars=b, oi=oi, sources=src("oi", "bars")), findings=[p1, p2],
                     cuts=CUTS)
    by = {m["finding_id"]: m for m in ev["matches"]}
    assert by["DH3-P1"]["vetoed_by"] == "DH3-P2"
    shown = RE.select(ev, "btc", limit=2, now=datetime.fromtimestamp(now / 1000, UTC))
    assert [m["finding_id"] for m in shown] == ["DH3-P2"]


def test_the_main_surface_limit_is_capped_at_two_in_config():
    from beta.config import BetaConfig, BetaConfigError
    cfg = BetaConfig.load()
    assert cfg.section("decision")["research_evidence"]["main_surface_max"] <= 2
    raw = json.loads(json.dumps(cfg.raw, default=dict))
    raw["decision"]["research_evidence"]["main_surface_max"] = 3
    with pytest.raises(BetaConfigError):
        BetaConfig.from_mapping(raw)


def test_provenance_is_kept_and_the_result_is_json_safe():
    b = _hourly_bars(quiet=True)
    now = b.end_ms - b.end_ms % HOUR + 60_000
    j = RS.last_hour_index(b, now)
    oi = np.full(b.n, 80000.0)
    oi[j] = oi[j - 48] * math.exp(CUTS["P1_DOI4_MIN"] + 0.01)
    sources = {**src("bars"), "oi": {"present": True, "as_of": "2026-10-04T09:55:00+00:00", "reason": None}}
    ev = evaluate(now_ms=now, bars=b, oi=oi, sources=sources)
    m = next(x for x in ev["matches"] if x["finding_id"] == "DH3-P1")
    assert {"source": "oi", "as_of": "2026-10-04T09:55:00+00:00"} in m["provenance"]
    assert m["record"] == "docs/research/DH3_RESULT.md"
    from beta.history_stats import json_safe
    assert json.loads(json.dumps(json_safe(ev))) == json_safe(ev)


# ---- forecasts and gating are untouched ------------------------------------------------------------
def test_evidence_never_changes_the_decision_block_numbers():
    import copy
    from beta.decision import _zone_conditionals
    b = _hourly_bars(n_hours=60, seed=3)
    block = {"available": True, "as_of": datetime.fromtimestamp(b.end_ms / 1000, UTC).isoformat(),
             "corridor": {"horizons": {"4h": {"lower": 1.0, "upper": 2.0, "half_width_pct": 1.0, "scale_pct": 0.5}}},
             "levels": {"above": [{"low": 1, "high": 1, "edge": 1, "distance_pct": 0.5, "kinds": ["PDH", "ROUND"],
                                   "members": [{"kind": "PDH", "price": 61000.0}, {"kind": "ROUND", "price": 61000.0}],
                                   "touch": {"4h": 0.3, "24h": 0.6}}], "below": [], "all": []}}
    before = copy.deepcopy(block)
    RE.evaluate(RE.EvidenceInputs(now_ms=b.end_ms, bars=b, levels=block["levels"]["all"], sources=src("bars")),
                cuts=CUTS)
    _zone_conditionals(b, block, now=datetime.fromtimestamp(b.end_ms / 1000, UTC))
    assert block == before


def test_alert_evidence_never_changes_the_push_decision_or_identity():
    import asyncio
    from beta.config import BetaConfig
    from beta.market_alerts import _decide_and_record, attach_evidence

    class Conn:
        def __init__(self):
            self.rows = []

        def transaction(self):
            class T:
                async def __aenter__(s):
                    return s

                async def __aexit__(s, *a):
                    return False
            return T()

        async def count_market_pushes(self, **kw):
            return 0

        async def insert_market_alert(self, **kw):
            self.rows.append(kw)
            return len(self.rows)

    cfg = BetaConfig.load()
    now = datetime(2026, 10, 2, 9, tzinfo=UTC)
    payload = {"at": now.isoformat(), "level_kind": "PDH", "level": 64000.0, "side": 1}
    block = {"as_of": now.isoformat(), "evidence": {"matches": []},
             "levels": {"all": [{"kind": "PDH", "price": 64000.0}, {"kind": "ROUND", "price": 64000.0}]}}
    out = []
    for with_evidence in (False, True):
        cand = {"kind": "level", "key": "level:PDH:2026-10-02", "payload": dict(payload)}
        if with_evidence:
            attach_evidence(cand, block, {"bars": None})
            assert {m["finding_id"] for m in cand["payload"]["evidence"]} == {"DH3-V2", "DH1-L2"}
        conn = Conn()
        res = asyncio.run(_decide_and_record(conn, cfg, cand, now=now, push_on=True))
        out.append((res, conn.rows[0]["decision"], conn.rows[0]["suppression_reason"], conn.rows[0]["alert_key"]))
    assert out[0] == out[1]


# ---- read-only feeds ---------------------------------------------------------------------------------
def test_depth_band_is_exact_or_absent_never_partial():
    from beta.research_feeds import depth_band
    mid = 60000.0
    bids = [[str(mid - 0.5 - k * 1.0), "1"] for k in range(1000)]          # reaches ~1.7 %
    asks = [[str(mid + 0.5 + k * 0.1), "2"] for k in range(1000)]          # reaches ~0.17 %
    row = depth_band({"bids": bids, "asks": asks, "T": 1})
    assert row["bid1_usd"] == pytest.approx(sum(float(p) for p, _ in bids if float(p) >= mid * 0.99))
    assert row["ask1_usd"] is None and row["ask_reach_pct"] < 1.0


def test_feed_parsers_keep_only_published_rows_outside_protected_windows():
    from beta import research_feeds as RF
    now = int(datetime(2026, 10, 4, 12, 7, tzinfo=UTC).timestamp() * 1000)
    t = now - now % 300_000
    oi = RF.parse_oi_hist([{"timestamp": t - 600_000, "sumOpenInterest": "80000", "sumOpenInterestValue": "5e9"},
                           {"timestamp": t, "sumOpenInterest": "80010"}])
    ls = RF.parse_ls_ratio([{"timestamp": t - 600_000, "longShortRatio": "1.9"}, {"timestamp": t - 1, "longShortRatio": "2"}])
    rows = RF.merge_metrics(oi, ls, now_ms=now)
    assert [r["ts_ms"] for r in rows] == [t - 600_000]                    # label t is not published until t + 5m
    held = int(datetime(2026, 8, 20, tzinfo=UTC).timestamp() * 1000)
    assert RF.merge_metrics({held: {"oi_base": 1.0}}, {}, now_ms=now) == []   # E1 holdout: never stored
    dv = RF.parse_dvol({"result": {"data": [[t - 3 * 3_600_000 - t % 3_600_000, 50, 51, 49, 50.5],
                                            [now - now % 3_600_000, 50, 51, 49, 50.7]]}}, now_ms=now)
    assert len(dv) == 1                                                   # the open hour is not stored
    sp = RF.parse_spot_klines([[t - 300_000, "1", "2", "0.5", "1.5", "10", t - 1, "15", 7, "4", "6", "0"],
                               [t, "1", "2", "0.5", "1.5", "10", t + 299_999, "15", 7, "4", "6", "0"]], now_ms=now)
    assert [r["open_time_ms"] for r in sp] == [t - 300_000]


def test_the_rest_tail_is_used_only_after_its_definition_check_passes():
    from beta.research_feeds import definition_check
    vis = [{"ts_ms": T0 + k * BAR_MS, "oi_base": 80000.0 + k, "ls_account_ratio": 1.5 + k * 1e-4} for k in range(300)]
    same = definition_check(vis, vis)
    assert same["oi_base"]["status"] == "OK" and same["ls_account_ratio"]["status"] == "OK"
    shifted = [{**r, "ts_ms": r["ts_ms"] + BAR_MS} for r in vis]
    assert definition_check(shifted, vis)["oi_base"]["status"] == "FAILED"   # a label offset is a failure
    assert definition_check(vis[:20], vis)["oi_base"]["status"] == "PENDING"


def test_feed_and_stress_units_are_wired_and_never_enabled_by_install():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2] / "deploy"
    assert "--beta-feeds-once" in (root / "signalbot-beta-feeds.service").read_text()
    assert "--beta-stress-once" in (root / "signalbot-beta-stress.service").read_text()
    assert "*:00/5:40 UTC" in (root / "signalbot-beta-feeds.timer").read_text()
    install = (root / "install_beta_units.sh").read_text()
    assert "signalbot-beta-feeds.timer" in install and "signalbot-beta-stress.timer" in install
    assert "systemctl enable" not in install and "systemctl start" not in install
    from runtime.beta_cli import BETA_COMMAND_FLAGS
    assert {"beta_feeds_once", "beta_stress_once"} <= set(BETA_COMMAND_FLAGS)


def test_feeds_use_public_market_data_endpoints_only():
    from pathlib import Path
    text = (Path(__file__).resolve().parents[2] / "beta" / "research_feeds.py").read_text()
    for host in re.findall(r"https://([a-z0-9.\-]+)", text):
        assert host in ("fapi.binance.com", "data-api.binance.vision", "www.deribit.com"), host
    for forbidden in ("X-MBX-APIKEY", "signature", "/fapi/v1/order", "/fapi/v2/account", "listenKey", "api_key"):
        assert forbidden not in text


# ---- collection vs presentation (docs/RESEARCH_EVIDENCE_DEPLOY_PLAN_V1.md PREREQ-2) ----------------------
def _with_research(**kw):
    from beta.config import BetaConfig
    base = BetaConfig.load()
    d = base.section("decision")
    return base.with_overrides(decision={**d, "research_evidence": {**d["research_evidence"], **kw}})


def test_the_presentation_env_switch_can_only_turn_presentation_off():
    from beta.config import research_presentation_enabled
    on, off = _with_research(enabled=True), _with_research(enabled=False)
    for raw, want in ((None, True), ("", True), ("1", True), ("true", True), ("0", False), ("false", False),
                      ("maybe", False)):                                  # an unrecognised value fails closed
        env = {} if raw is None else {"BETA_RESEARCH_EVIDENCE_ENABLED": raw}
        assert research_presentation_enabled(on, env) is want, raw
        assert research_presentation_enabled(off, env) is False, raw     # the env never turns it on


def test_collection_is_gated_only_by_its_own_flags_and_never_applies_the_schema(monkeypatch):
    import asyncio
    import main
    from beta import research_feeds as RF
    from beta.config import BetaConfig
    from runtime.beta_cli import run_beta_cli_command
    calls = []

    async def job(store, *, now, expected_role=None):
        calls.append(expected_role)
        return {"status": "OK"}
    monkeypatch.setattr(RF, "run_feeds_job", job)
    monkeypatch.setattr(RF, "run_stress_job", job)

    class Db:                      # any other DB access (e.g. init_beta_v0_schema) fails the test
        def beta_store(self):
            return object()

        def __getattr__(self, name):
            raise AssertionError(f"DB touched: {name}")

    def cli(flag, cfg, env):
        monkeypatch.setattr(BetaConfig, "load", classmethod(lambda cls, *a, **k: cfg))
        return asyncio.run(run_beta_cli_command(main.parse_args([flag, "--beta-json"]), db=Db(), env=env))
    env = {"BETA_ENABLED": "1", "BETA_FEEDS_EXPECTED_DB_ROLE": "signalbot_beta_feeds"}
    for flag in ("--beta-feeds-once", "--beta-stress-once"):
        assert cli(flag, _with_research(enabled=False), env)["status"] == "OK"             # presentation off
        assert cli(flag, _with_research(enabled=True), {**env, "BETA_RESEARCH_EVIDENCE_ENABLED": "0"})["status"] == "OK"
        assert cli(flag, _with_research(enabled=True), env)["status"] == "OK"
    assert calls == ["signalbot_beta_feeds"] * 6
    assert cli("--beta-feeds-once", _with_research(feeds_enabled=False), env)["status"] == "DISABLED"
    assert cli("--beta-stress-once", _with_research(stress_hours_enabled=False), env)["status"] == "DISABLED"
    assert cli("--beta-feeds-once", _with_research(), {"BETA_ENABLED": "0"})["status"] == "DISABLED"
    assert len(calls) == 6
