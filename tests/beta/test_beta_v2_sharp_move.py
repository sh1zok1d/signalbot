"""Sharp-move event fallback (BETA_EVENT_CORRIDOR_TEMPORAL_REPAIR_DESIGN_V1 §10).

SHARP_MOVE_EVENT_CONDITIONING = DISABLED_PENDING_VALIDATION: the sharp-move statistic divides by
the 1h rangecast scale with every CPI/FOMC column at 0, live and in the nightly calibration, through
one function. The corridor keeps its event term (and its event-zone fallback). Synthetic bars and
calendar entries; the corridor snapshot reads 2022 repository archives (training data) only."""
import inspect
import json
import re
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from beta import decision_format as df
from beta import market_alerts as ma
from beta import rangecast as rc
from beta.hist_series import BAR_MS, BARS_PER_DAY, Bars

UTC = timezone.utc
T0 = datetime(2026, 9, 1, tzinfo=UTC)
BETA = {"const": 0.2, "log_r1h": 0.45, "log_r4h": 0.2, "log_r24h": 0.1, "log_r7d": 0.05, "season": 0.6,
        "weekend": -0.15, "event_cpi": 1.034, "event_fomc": 0.989}           # event terms of the local fit
MODEL = {"horizons": {"1h": {"beta": [BETA[f] for f in rc.FEATURES],
                             "season": [0.1 * np.sin(h / 24 * 2 * np.pi) for h in range(24)]}}}


def ms(dt):
    return int(dt.timestamp() * 1000)


def bars(n=2400, *, seed=5, sig=0.001, calm_from=None, move_pct=None):
    rng = np.random.default_rng(seed)
    s = np.full(n, sig)
    if calm_from is not None:
        s[calm_from:] = sig / 4                                   # a calmer recent regime
    close = 60000 * np.exp(np.cumsum(rng.normal(0, s)))
    if move_pct is not None:                                       # the last 15 minutes carry the move
        close[n - 3:] = close[n - 4] * (1 + move_pct / 100)
    wig = np.abs(rng.normal(0, s))
    return Bars(t0=ms(T0), open=close.copy(), high=close * (1 + wig), low=close * (1 - wig), close=close,
                volume=np.ones(n), quote=np.ones(n), taker_buy_quote=np.full(n, 0.5), oi=np.ones(n))


def with_move(model, thr):
    return {**model, "move": {"threshold": thr, "episodes_per_day": 0.33, "statistic": rc.MOVE_STATISTIC}}


def k0_flag(b, j, kind, r_ms):
    """The 1h event flag the detector used to read for the anchor at bar j (corridor semantics K0)."""
    return bool(rc.event_in_window(np.array([b.times[j] + BAR_MS]), [r_ms], rc.HORIZON_MS["1h"])[0])


# ---- 6. the discontinuity: same market state, only the release moves -------------------------
OFFSETS = [-61, -60, -45, -5, 0, 5, 15, 20, 59, 60, 61]           # now − r, minutes
OLD_FLAG_ON = {-5, 0, 5, 15}                                       # E ∈ (r − 45m, r + 15m], now = E + 40 s


@pytest.mark.parametrize("kind", ["CPI", "FOMC"])
def test_no_event_only_threshold_discontinuity_around_a_release(kind):
    b = bars(move_pct=-1.2)
    i, j = b.n - 1, b.n - 1 - rc.MOVE_WINDOW_BARS
    now = datetime.fromtimestamp(b.end_ms / 1000, UTC) + timedelta(seconds=40)
    move = abs(b.close[i] / b.close[j] - 1) * 100
    new = rc.move_ratio_at(MODEL, b, i)
    old, flags = {}, {}
    for d in OFFSETS:
        r_ms = ms(now - timedelta(minutes=d))
        flags[d] = k0_flag(b, j, kind, r_ms)
        old[d] = move / rc.scale_at(MODEL, b, j, "1h", events={kind: [r_ms]})      # the pre-fix statistic
    # the points do cross the old flag's edges, so the old statistic jumped there ...
    assert {d for d, f in flags.items() if f} == OLD_FLAG_ON
    jump = np.exp(BETA[f"event_{kind.lower()}"])
    for d in OFFSETS:
        assert old[d] == pytest.approx(new / (jump if d in OLD_FLAG_ON else 1.0), rel=1e-12)
    # ... while the sharp-move statistic and decision are one value at every point
    for factor, alerts in ((0.9, True), (1.1, False)):
        model = with_move(MODEL, new * factor)
        got = {d: bool(ma.detect_move({}, b, [], now=now, model=model)) for d in OFFSETS}
        assert set(got.values()) == {alerts}, got                  # EVENT_ONLY_THRESHOLD_DISCONTINUITY = NONE
    assert "events" not in inspect.signature(ma.detect_move).parameters
    assert "events" not in inspect.signature(rc.move_ratio).parameters
    assert "events" not in inspect.signature(rc.sharp_move_threshold).parameters


# ---- 7A. live == calibration: one statistic, one function --------------------------------------
def test_live_move_ratio_equals_the_calibration_move_ratio():
    b = bars(2700, calm_from=2300)
    full = rc.move_ratio(b, MODEL, logs=rc.past_log_ranges(b))
    checked = 0
    for i in range(2020, b.n):
        live = rc.move_ratio_at(MODEL, b, i)
        if np.isfinite(full[i]):
            assert live == pytest.approx(full[i], rel=1e-12), i
            checked += 1
        else:
            assert live is None
    assert checked > 600
    # the detector's payload carries that same number
    now = datetime.fromtimestamp(b.end_ms / 1000, UTC) + timedelta(seconds=40)
    out = ma.detect_move({}, b, [], now=now, model=with_move(MODEL, 1e-9))
    assert out[0]["payload"]["ratio"] == pytest.approx(full[-1], rel=1e-12)


def test_detector_and_calibration_both_go_through_move_ratio_and_sharp_move_scale(monkeypatch):
    calls = {"move_ratio": 0, "sharp_move_scale": 0}
    real_ratio, real_scale = rc.move_ratio, rc.sharp_move_scale

    def ratio_spy(*a, **k):
        calls["move_ratio"] += 1
        return real_ratio(*a, **k)

    def scale_spy(*a, **k):
        calls["sharp_move_scale"] += 1
        return real_scale(*a, **k)
    monkeypatch.setattr(rc, "move_ratio", ratio_spy)
    monkeypatch.setattr(rc, "sharp_move_scale", scale_spy)
    b = bars(2400)
    now = datetime.fromtimestamp(b.end_ms / 1000, UTC) + timedelta(seconds=40)
    ma.detect_move({}, b, [], now=now, model=with_move(MODEL, 1.0))
    assert calls == {"move_ratio": 1, "sharp_move_scale": 1}
    rc.sharp_move_threshold(b, MODEL, logs=rc.past_log_ranges(b))
    assert calls == {"move_ratio": 2, "sharp_move_scale": 2}


# ---- 7B/C. the CPI / FOMC flag does not move the sharp-move scale -------------------------------
@pytest.mark.parametrize("kind", ["CPI", "FOMC"])
def test_event_flag_has_no_effect_on_the_sharp_move_scale(kind):
    b = bars(2400)
    logs = rc.past_log_ranges(b)
    idx = np.arange(2100, 2400)
    r_ms = int(b.times[2200] + BAR_MS + 30 * 60_000)              # flags the 1h anchors 2189 … 2200
    on = rc.design(b, idx, "1h", logs=logs, season=MODEL["horizons"]["1h"]["season"], events={kind: [r_ms]})
    col = rc.FEATURES.index(f"event_{kind.lower()}")
    assert on[:, col].sum() == 12                                  # the corridor's K0 flag is on there
    beta = np.asarray(MODEL["horizons"]["1h"]["beta"])
    k0 = np.exp(on @ beta)
    zeroed = on.copy()
    zeroed[:, [rc.FEATURES.index("event_cpi"), rc.FEATURES.index("event_fomc")]] = 0.0
    move_scale = rc.sharp_move_scale(b, idx, MODEL, logs=logs)
    assert move_scale == pytest.approx(np.exp(zeroed @ beta), rel=1e-12)   # the scale as before, minus the event term
    flagged = on[:, col] == 1
    assert k0[flagged] == pytest.approx(move_scale[flagged] * np.exp(BETA[f"event_{kind.lower()}"]), rel=1e-12)
    assert k0[~flagged] == pytest.approx(move_scale[~flagged], rel=1e-12)


# ---- 7D. the volatility / time-of-day / weekend conditioning stays -----------------------------
def test_non_event_conditioning_still_moves_the_sharp_move_scale():
    wild, calm = bars(2400), bars(2400, calm_from=2200)
    i = 2399
    s_wild = rc.sharp_move_scale(wild, np.array([i]), MODEL, logs=rc.past_log_ranges(wild))[0]
    s_calm = rc.sharp_move_scale(calm, np.array([i]), MODEL, logs=rc.past_log_ranges(calm))[0]
    assert s_calm < 0.8 * s_wild                                   # a calmer recent past, a smaller scale
    s = rc.sharp_move_scale(wild, np.arange(2100, 2400), MODEL, logs=rc.past_log_ranges(wild))
    assert np.ptp(np.log(s)) > 0.05                                # not a constant scale
    # the same move is a bigger ratio in the calmer state
    b1, b2 = bars(2400, move_pct=-1.0), bars(2400, calm_from=2200, move_pct=-1.0)
    assert rc.move_ratio_at(MODEL, b2, 2399) > rc.move_ratio_at(MODEL, b1, 2399)


# ---- 7E. the threshold: the same procedure on the new statistic, and only with it ------------------
def test_threshold_is_built_by_the_unchanged_procedure_on_the_event_neutral_statistic():
    assert (rc.MOVE_QUANTILES, rc.MOVE_TARGET_EPISODES_PER_DAY, rc.MOVE_DECLUSTER_BARS, rc.MOVE_WINDOW_BARS) == \
        ((0.99, 0.995, 0.998, 0.999, 0.9995), 0.35, 24, 3)
    b = bars(2016 + 40 * BARS_PER_DAY, seed=9)
    logs = rc.past_log_ranges(b)
    thr = rc.sharp_move_threshold(b, MODEL, logs=logs)
    r = rc.move_ratio(b, MODEL, logs=logs)
    fin = r[np.isfinite(r)]
    days = fin.size / BARS_PER_DAY
    cands = []
    for q in rc.MOVE_QUANTILES:
        t = float(np.quantile(fin, q))
        eps = rc._episodes(np.nan_to_num(r, nan=0.0) >= t, rc.MOVE_DECLUSTER_BARS) / days
        cands.append((abs(np.log(max(eps, 1e-6) / rc.MOVE_TARGET_EPISODES_PER_DAY)), q, t))
    _, q, t = min(cands)
    assert thr["quantile"] == q and thr["threshold"] == pytest.approx(t, rel=1e-12)
    assert thr["statistic"] == rc.MOVE_STATISTIC == "MOVE15_OVER_1H_SCALE_EVENT_NEUTRAL_V1"


def test_a_threshold_built_on_another_statistic_is_never_used():
    b = bars(2400, move_pct=-3.0)
    now = datetime.fromtimestamp(b.end_ms / 1000, UTC) + timedelta(seconds=40)
    good = with_move(MODEL, 0.5)
    assert ma.detect_move({}, b, [], now=now, model=good)
    for stale in ({k: v for k, v in good["move"].items() if k != "statistic"},          # built before this change
                  {**good["move"], "statistic": "SOMETHING_ELSE"}):
        assert ma.detect_move({}, b, [], now=now, model={**MODEL, "move": stale}) == []


# ---- 7F/G. the corridor is untouched: K0 inside, unchanged outside -----------------------------
def test_the_corridor_keeps_its_event_term():
    b = bars(2400)
    r_ms = int(b.end_ms + 20 * 60_000)
    k0 = rc.scale_at(MODEL, b, b.n - 1, "1h", events={"CPI": [r_ms]})
    plain = rc.scale_at(MODEL, b, b.n - 1, "1h", events={})
    assert k0 == pytest.approx(plain * np.exp(BETA["event_cpi"]), rel=1e-12)


SNAPSHOT_2022 = {   # fit_range_model on 2022-01..04 repository archives, computed with the pre-change code
    "1h": [-0.9674920927, 0.2077040769, 0.1601374265, 0.1199870712, 0.2830154289, 0.6316443726, -0.1495276296,
           0.8081977883, 0.9919294261],
    "4h": [-0.8985671183, 0.1271818809, 0.1129127748, 0.0711263442, 0.3747698943, 0.7730516818, -0.2543147567,
           0.3175493678, 0.717907877],
    "24h": [-0.1974403575, 0.0422648638, 0.066830292, -0.0656179145, 0.407200531, 0.5760905111, -0.4804978203,
            -0.1263848873, 0.1603154423],
    "k80": {"1h": 1.1400315454, "4h": 1.1956716911, "24h": 1.1277702606},
    "half_width_pct": {"1h": 0.9804384252, "4h": 1.5946452481, "24h": 3.2696952445},
}


def test_the_generic_corridor_fit_and_forecast_are_unchanged():
    from beta import hist_series as hs
    from beta import history_data as hd
    from beta.calendar_events import event_times_ms, load_calendar
    from v2_fakes import repo_vision_zips
    b = hs.bars_from_rows(hd.rows_from_local_zips(repo_vision_zips(["2022-01", "2022-02", "2022-03", "2022-04"])))
    m = rc.fit_range_model(b, events=event_times_ms(load_calendar()))
    for h in ("1h", "4h", "24h"):
        assert m["horizons"][h]["beta"] == pytest.approx(SNAPSHOT_2022[h], abs=1e-8), h
        assert rc.quantile_at(m["horizons"][h]["q_max"], 0.8) == pytest.approx(SNAPSHOT_2022["k80"][h], abs=1e-8)
    fc = rc.forecast(m, b, price=float(b.close[-1]), events={})
    for h, x in fc["horizons"].items():
        assert x["half_width_pct"] == pytest.approx(SNAPSHOT_2022["half_width_pct"][h], abs=1e-8), h
    assert m["move"]["statistic"] == rc.MOVE_STATISTIC


# ---- 5/8. the copy: no pooled frequency inside the release's 1h zone ---------------------------
R = datetime(2026, 10, 14, 12, 30, tzinfo=UTC)
FREQ = re.compile(r"раз в|once every", re.I)


def move_payload(zones):
    return {"at": (R + timedelta(minutes=15)).isoformat(), "start": R.isoformat(), "open": 62000.0, "close": 61000.0,
            "move_pct": -1.61, "ratio": 3.0, "every_days": 3.0, "event_zone": zones,
            "corridor_1h": {"lower": 60500.0, "upper": 61500.0, "half_width_pct": 0.8},
            "near": [{"kind": "PDL", "kinds": ["PDL"], "low": 60800.0, "high": 60800.0, "edge": 60800.0,
                      "distance_pct": -0.33, "members": [{"kind": "PDL", "price": 60800.0}]}]}


def plain(html):
    return re.sub(r"<[^>]+>", "", html)


@pytest.mark.parametrize("lang", ["ru", "en"])
def test_move_alert_in_an_event_zone_has_no_frequency_research_line_or_number_claims(lang):
    z = {h: [{"kind": "FOMC", "at": R.isoformat()}] for h in ("1h", "4h", "24h")}
    text = plain(df.format_alert("move", move_payload(z), lang))
    assert ("резкое движение −1,61%" if lang == "ru" else "sharp move −1.61%") in text   # the fact and its size
    assert ("62 000 → 61 000" if lang == "ru" else "62,000 → 61,000") in text
    assert ("вокруг публикации обычная калибровка" if lang == "ru" else "around the release, the usual corridor") in text.lower()
    assert not FREQ.search(text), text                             # MOVE_FREQUENCY_COPY = SUPPRESSED
    assert not re.search(r"×|4 из 5|4 of 5|4 out of 5|80\s*%|вероятн|probab|Проверено|Tested|1,76|1\.76", text), text
    assert "60 500" not in text and "60,500" not in text           # no corridor either


@pytest.mark.parametrize("lang", ["ru", "en"])
def test_move_alert_outside_the_1h_zone_keeps_the_generic_frequency(lang):
    for zones in ({}, {"24h": [{"kind": "CPI", "at": (R + timedelta(hours=20)).isoformat()}]}):
        text = plain(df.format_alert("move", move_payload(zones), lang))
        assert ("примерно раз в 3,0 дн." if lang == "ru" else "about once every 3.0 days") in text, zones
        assert "🔬" not in text                     # research lines come only from the evidence recorded with the alert
        from beta.research_evidence import _match, live_findings
        at = int(datetime.fromisoformat(move_payload(zones)["at"]).timestamp() * 1000)
        h03 = _match(live_findings()["H03"], key="H03_IMPULSE", at_ms=at, sources={},
                     values={"window_min": 15, "ret_pct": -1.6, "top_pct": 1.0}).to_dict()
        text = plain(df.format_alert("move", {**move_payload(zones), "evidence": [h03]}, lang))
        from beta.research_render import line as rline
        assert plain(rline(h03, lang)) in text and "🔬" in text and "(H03)" not in text


# ---- end to end on PostgreSQL: a real move right after a CPI release ----------------------------
from beta_fakes import CFG, ON_PUSH, TEST_DSN, Clock, run          # noqa: E402

PG_R = datetime(2026, 5, 12, 12, 30, tzinfo=UTC)                   # CPI in config/beta_calendar.yaml


class _Sender:
    def __init__(self):
        self.sent = []

    async def send(self, *, chat_id, html, buttons=None):
        self.sent.append((chat_id, html, buttons))
        return len(self.sent)


@pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)")
def test_end_to_end_a_move_in_the_first_15_minutes_after_a_release():
    """[r, r + 15m) is the window the old K0 flag inflated ×2.8. The live path (build_decision →
    detect_move) now judges it on the event-neutral statistic, and the push carries no pooled
    frequency, research line, corridor or multiplier."""
    from beta.decision import build_decision, reset_cache
    from beta.delivery import run_notify_once
    from beta.history_stats import run_history_build
    from beta_fakes import fresh_pool
    from storage.beta_v0_store import BetaStore
    from test_beta_v2_pg import DAY, _handler, _join, _rows, _seed

    assert DAY.date() == PG_R.date()

    async def body():
        reset_cache()
        pool = await fresh_pool()
        store = BetaStore(pool)
        seed = await _seed(pool, touch_at_minute=-1, minutes=12 * 60 + 30)        # flat 1m tail to 12:30 UTC
        base = seed["base"]
        recs = [("binance", "BTCUSDT", PG_R + timedelta(minutes=m), base * (1 - 0.002 * m), base * (1 - 0.002 * m),
                 base * (1 - 0.002 * (m + 1)), base * (1 - 0.002 * (m + 1)), 10.0, 5.0, "live") for m in range(15)]
        async with pool.acquire() as c:                                           # −3% in [12:30, 12:45)
            await c.executemany("""INSERT INTO klines_1m (exchange, symbol, ts, open, high, low, close, volume,
                                       taker_buy_volume, source) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)""", recs)
        assert (await run_history_build(store, CFG, now=DAY + timedelta(hours=2)))["status"] == "OK"
        owner, ru, en = 900000000001, 900000000111, 900000000222
        now = PG_R + timedelta(minutes=15, seconds=40)
        h = _handler(pool, owner, Clock(now))
        async with store.connect() as conn:
            for uid in (ru, en):
                await conn.allowlist_add(uid)
        msgs = {ru: await _join(h, ru, 10, "ru"), en: await _join(h, en, 20, "en")}
        async with store.connect() as conn:
            for uid in (ru, en):
                await conn.mark_privacy_notice_seen(uid, 4)
        cap: dict = {}
        async with store.connect() as conn:
            blk = await build_decision(conn, CFG, now=now, capture=cap)
        b, model = cap["bars"], cap["model"]
        assert model["move"]["statistic"] == rc.MOVE_STATISTIC and set(blk["event_zone"]) == {"1h", "4h", "24h"}
        i = b.n - 1
        j = i - rc.MOVE_WINDOW_BARS
        assert k0_flag(b, j, "CPI", ms(PG_R))                                     # the old flag was on here
        new = rc.move_ratio_at(model, b, i)
        assert new >= model["move"]["threshold"]
        s = _Sender()
        r = await run_notify_once(store, CFG, ON_PUSH, sender=s, clock=Clock(now))
        moves = [(cid, plain(html)) for cid, html, _ in s.sent if "15 минут" in plain(html) or "15 minutes" in plain(html)]
        assert sorted(cid for cid, _ in moves) == [ru, en], r
        for _, text in moves:
            assert re.search(r"(резкое движение|sharp move) −3[,.]0\d?%", text), text
            assert not FREQ.search(text), text                                    # MOVE_FREQUENCY_COPY = SUPPRESSED
            assert not re.search(r"×|4 из 5|4 of 5|4 out of 5|80\s*%|вероятн|probab|Проверено|Tested|1,76|1\.76",
                                 text), text
            assert "вокруг публикации обычная калибровка" in text.lower() or \
                "around the release, the usual corridor" in text.lower()
        rows = await _rows(pool, "SELECT payload FROM beta_market_alerts WHERE kind='move'")
        assert len(rows) == 1
        stored = json.loads(rows[0]["payload"]) if isinstance(rows[0]["payload"], str) else rows[0]["payload"]
        assert stored["ratio"] == pytest.approx(new, rel=1e-9)                  # live = calibration statistic
        k = 100
        for uid in (ru, en):
            for cmd in ("/btc", "/catchup"):
                k += 1
                out = await h.handle(msgs[uid](cmd, k))
                text = plain(out[-1].html)
                assert not FREQ.search(text) and "×" not in text, (cmd, text)
        await pool.close()
    run(body())
