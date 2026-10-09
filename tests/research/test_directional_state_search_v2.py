"""DIRECTIONAL_STATE_SEARCH_V2: formulas, past-only invariance, bootstrap mechanics. Synthetic data only."""
import math

import numpy as np
import pytest

from scripts.research.directional_state_search_v2 import constants as K
from scripts.research.directional_state_search_v2 import features as F
from scripts.research.directional_state_search_v2 import stats as S


def _bars(n=3000, seed=3):
    rng = np.random.default_rng(seed)
    close = 30000 * np.exp(np.cumsum(rng.normal(0, 0.002, n)))
    high = close * np.exp(np.abs(rng.normal(0, 0.001, n)))
    low = close * np.exp(-np.abs(rng.normal(0, 0.001, n)))
    quote = rng.uniform(1e6, 5e6, n)
    tbq = quote * np.clip(0.5 + 40 * np.diff(np.log(close), prepend=np.log(close[0])) + rng.normal(0, 0.05, n), 0, 1)
    t = K.SURFACE_START_MS + np.arange(n, dtype=np.int64) * K.BAR_MS
    return {"open_ms": t, "open": close, "high": high, "low": low, "close": close, "quote": quote, "tbq": tbq}


def _all_states(b, idx):
    out = {}
    for k, v in {**F.spa_family(b["close"]), **F.flow_family(b)}.items():
        out[k] = v[idx]
    for fn in (F.occupancy, F.countermove, F.rejection):
        out.update(fn(b, idx))
    return out


def test_states_are_past_only():
    b = _bars()
    idx = np.arange(300, 2900, 7)
    a = _all_states(b, idx)
    cut = 1500
    b2 = {k: v.copy() for k, v in b.items()}
    for c in ("open", "high", "low", "close"):
        b2[c][cut + 1:] *= 1.05
    b2["quote"][cut + 1:] *= 3.0
    b2["tbq"][cut + 1:] = b2["quote"][cut + 1:] * 0.9
    z = _all_states(b2, idx)
    m = idx <= cut
    for k in a:
        assert np.allclose(a[k][m], z[k][m], equal_nan=True), k


def test_spa_and_upfrac_formulas():
    b = _bars(600)
    s = F.spa_family(b["close"])
    i = 500
    r = np.diff(np.log(b["close"][i - 288:i + 1]))
    rp, rn = (r[r > 0] ** 2).sum(), (r[r < 0] ** 2).sum()
    assert s["SPA_24H"][i] == pytest.approx((rp - rn) / (rp + rn))
    assert s["UPFRAC_24H"][i] == pytest.approx(((r > 0).sum() - (r < 0).sum()) / ((r > 0).sum() + (r < 0).sum()))
    assert s["RV_24H"][i] == pytest.approx(math.sqrt(rp + rn))
    assert s["RET_24H"][i] == pytest.approx(math.log(b["close"][i] / b["close"][i - 288]))
    assert np.isnan(s["SPA_24H"][287])


def test_occupancy_excludes_the_current_close():
    b = _bars(600)
    i = np.array([400])
    o = F.occupancy(b, i)
    hi, lo = b["high"][353:401].max(), b["low"][353:401].min()
    p = (b["close"][353:400] - lo) / (hi - lo)
    assert o["OCC_MEAN_4H"][0] == pytest.approx(p.mean())
    assert o["OCC_THIRDS_4H"][0] == pytest.approx((p >= 2 / 3).mean() - (p <= 1 / 3).mean())


def test_countermove_hand_computation():
    b = _bars(800)
    i = 700
    o = F.countermove(b, np.array([i]))["CMD_UP_24H"][0]
    h = np.log(b["high"][i - 287:i + 1]).reshape(6, 48)
    l = np.log(b["low"][i - 287:i + 1]).reshape(6, 48)
    dd = [max(np.maximum.accumulate(h[s])[k] - l[s][k] for k in range(48)) for s in range(6)]
    ru = [max(h[s][k] - np.minimum.accumulate(l[s])[k] for k in range(48)) for s in range(6)]
    want = (np.mean(np.log(ru[4:6])) - np.mean(np.log(ru[0:2]))) - (np.mean(np.log(dd[4:6])) - np.mean(np.log(dd[0:2])))
    assert o == pytest.approx(want)


def test_flow_response_formulas():
    b = _bars(800)
    s = F.flow_family(b)
    i = 700
    r = np.diff(np.log(b["close"][i - 288:i + 1]))
    f = (2 * b["tbq"] - b["quote"])[i - 287:i + 1]
    rec, pri = slice(240, 288), slice(0, 240)
    lam = lambda rr, ff: (rr * ff).sum() / (ff * ff).sum()
    want = np.sign(f[rec].sum()) * math.log(lam(r[rec], f[rec]) / lam(r[pri], f[pri]))
    assert s["FLOW_RESPONSE_CHANGE_4H"][i] == pytest.approx(want)
    side = lambda rr, ff, m: lam(rr[m], ff[m])
    rr, pr = r[rec], r[pri]
    fr, fp = f[rec], f[pri]
    want2 = math.log(side(rr, fr, fr > 0) / side(rr, fr, fr < 0)) - math.log(side(pr, fp, fp > 0) / side(pr, fp, fp < 0))
    assert s["SIDE_ASYM_CHANGE_4H"][i] == pytest.approx(want2)
    assert s["IMB_4H"][i] == pytest.approx(f[rec].sum() / b["quote"][i - 47:i + 1].sum())


def test_wall_decay_on_a_scripted_path():
    # positions: contact, retreat to depth 0.6, contact, retreat to depth 0.3, contact -> log(0.3/0.6)
    depth = np.array([[0.0, 0.6, 0.6, 0.0, 0.3, 0.3, 0.0]])
    contact = depth == 0.0
    retreat = depth >= 0.3
    assert F._wall_decay(contact, retreat, depth)[0] == pytest.approx(math.log(0.3 / 0.6))
    # a re-touch without a retreat close does not start a new episode
    contact2 = np.array([[True, False, True, False, True]])
    retreat2 = np.array([[False, False, False, True, False]])
    depth2 = np.array([[0.0, 0.1, 0.0, 0.5, 0.0]])
    assert np.isnan(F._wall_decay(contact2, retreat2, depth2)[0])


def test_block_bootstrap_point_equals_partial_rank_and_is_seeded():
    rng = np.random.default_rng(5)
    n = 4000
    z = rng.normal(size=n)
    x = 0.5 * z + rng.normal(size=n)
    y = 0.1 * x + 0.3 * z + rng.normal(size=n)
    blocks = np.repeat(np.arange(40), 100)
    inv, w = S.week_index(blocks)
    draws = S.boot_matrix(w)
    est = S.estimate(y, x, [z], inv, w, draws)
    assert est["point"] == pytest.approx(S.partial_rank(y, x, [z])["rho"], abs=1e-12)
    raw = S.estimate(y, x, [], inv, w, draws)
    assert raw["point"] == pytest.approx(S.spearman(x, y), abs=1e-12)
    assert est["lo"] < est["point"] < est["hi"] and est["valid"] == K.BOOT_DRAWS
    assert np.array_equal(draws, S.boot_matrix(w))


def test_session_clock_is_dst_aware_and_calendar_pinned():
    import datetime as dt
    from scripts.research.directional_state_search_v2 import session as SS
    days = SS.trading_days()
    assert len(days) == 1258 and dt.date(2024, 3, 29) not in days and dt.date(2024, 11, 29) in days   # Good Friday; early close kept
    assert SS.ny_ms(dt.date(2020, 7, 1), 10, 0) == 1_593_612_000_000          # 14:00Z in EDT
    assert SS.ny_ms(dt.date(2020, 1, 2), 10, 0) == 1_577_977_200_000          # 15:00Z in EST
    t = SS.ny_ms(dt.date(2020, 1, 2), 10, 0)
    assert ((t - K.PHASE_ORIGIN_MS) // 60_000) % 15 == 0                       # on the 15-minute anchor grid


def test_placebo_statistic_matches_the_clock_formula():
    from scripts.research.directional_state_search_v2 import session as SS
    b = _bars(2000)
    i = np.array([1500])
    p = SS.placebo_states(b["close"], i)
    want = math.log(b["close"][1500] / b["close"][1494]) / SS._rv_ending(b["close"], 1494)
    assert p["US_OPEN_DRIVE"][0] == pytest.approx(want)
    want2 = math.log(b["close"][1500] / b["close"][1422]) / SS._rv_ending(b["close"], 1422)
    assert p["SESSION_HANDOFF"][0] == pytest.approx(want2)


def test_holm_and_frozen_ranking_rule():
    from scripts.research.directional_state_search_v2 import evaluate as E
    assert E.holm({"a": 0.01, "b": 0.04}) == {"a": 0.02, "b": 0.04}
    def ev(point, lo, hi, z, same):
        return {"state": "s", "incremental": {"point": point, "lo": lo, "hi": hi, "z": z}, "years_same_sign_as_incremental": same}
    objs = {"F1a": ev(0.010, 0.005, 0.015, 4.5, 5), "F2a": ev(-0.020, -0.03, -0.01, -5.0, 3),
            "F4a": ev(0.030, 0.02, 0.04, 6.0, 4), "F7a": ev(0.011, 0.006, 0.016, 4.0, 4), "F6a": ev(0.2, -0.1, 0.5, 1.0, 5)}
    r = E.rank(objs, 3.85)
    assert r["top3"] == ["F4a", "F1a", "F7a"]                                  # F2a unstable; F6a interval spans zero


def test_run_refuses_without_go_and_when_scored(monkeypatch, tmp_path):
    from scripts.research.directional_state_search_v2 import evaluate as E
    monkeypatch.setattr("sys.argv", ["evaluate", "run"])
    with pytest.raises(SystemExit, match="needs --go"):
        E.main()
    marker = tmp_path / "r.json"
    marker.write_text("{}")
    monkeypatch.setattr(E, "RESULT_JSON", marker)
    with pytest.raises(SystemExit, match="REFUSING_RERUN"):
        E.run()
