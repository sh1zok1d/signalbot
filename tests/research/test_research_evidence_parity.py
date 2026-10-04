"""Parity of the live research-evidence state functions (beta/research_states.py, beta/research_feeds.py)
with the frozen research implementations they reproduce: the same inputs give the same states, so a
live state can only mean what the research state meant. Offline; synthetic data only."""
from __future__ import annotations

import numpy as np
import pytest

from beta import research_states as RS
from beta.hist_series import BAR_MS, Bars
from datetime import datetime, timezone

UTC = timezone.utc
DAY = 86_400_000
T0 = int(datetime(2026, 9, 1, tzinfo=UTC).timestamp() * 1000)


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


def test_state_functions_are_the_research_functions():
    from scripts.research.dh1 import events as E1
    from scripts.research.dh3 import aggtrades as A3
    from scripts.research.dh3 import features as F3
    c = walk(3000, seed=4)
    c[[50, 700, 1500]] = np.nan
    b = bars(c)
    assert np.allclose(RS.rolling_sigma(b.close), E1.rolling_sigma(b.close), equal_nan=True)
    for a, z in ((100, 147), (1460, 1510), (2900, 2999)):
        assert RS.window_log_range(b, a, z) == F3._window_range(b, a, z)
    for j, lvl in ((500, 61000.0), (2500, 59000.0)):
        assert RS.stale_level(b, j, lvl) == E1.stale(b, j, lvl)
    rng = np.random.default_rng(7)
    t = np.sort(rng.integers(0, 3_600_000, 5000)).astype(np.int64)
    p, s = 60000 + np.cumsum(rng.normal(0, 3, 5000)), 60000 + np.cumsum(rng.normal(0, 3, 5000))
    from beta import research_feeds as RF
    assert np.array_equal(RF.second_grid(t, p, 0), A3.second_grid(t, p, 0))
    assert RF.lead_score(RF.second_grid(t, p, 0), RF.second_grid(t, s, 0)) == \
        A3.lead_score(A3.second_grid(t, p, 0), A3.second_grid(t, s, 0))


def test_sharp_moves_are_the_dh1_rule():
    from scripts.research.dh2 import events as E2
    c = walk(4000, seed=9, vol=0.0015)
    c[2000:2004] = c[1999] * np.array([1.004, 1.009, 1.016, 1.017])     # one sharp 15-minute move
    b = bars(c)
    spot = {"quote": np.full(b.n, 1e6), "taker_buy_quote": np.full(b.n, 5e5)}
    research = [(e["J"], e["DIR"]) for e in E2.move_events(b, spot, "BTC", T0, T0 + b.n * BAR_MS, [("A", "2026-01-01", "2027-01-01")])]
    live = [(i, d) for i, d, _r in RS.sharp_moves(b, RS.rolling_sigma(b.close))
            if T0 + (i + 1) * BAR_MS + 48 * BAR_MS <= T0 + b.n * BAR_MS and i + 48 < b.n]
    assert live == research and any(j in (2001, 2002, 2003) for j, _ in live)


def test_retests_are_the_dh3_v3_rule():
    from scripts.research.dh3 import features as F3
    b = bars(walk(288 * 40, seed=21, vol=0.0012))
    rows = [r for r in F3.retest_events(b, "BTC", T0, T0 + b.n * BAR_MS) if r["S"] == 1]
    assert rows, "the synthetic path has retests"
    sigma = RS.rolling_sigma(b.close)
    for r in rows:
        j = r["J"]
        day = (T0 + j * BAR_MS) // DAY * DAY
        first, last = (day - T0) // BAR_MS, (day + DAY - T0) // BAR_MS - 1
        side = 1 if r["TYPE"] == "PDH" else -1
        assert RS.retest_state(b, sigma, r["LEVEL"], side, int(first), int(last))["retest"] == j


def test_h_series_percentiles_are_the_research_midrank():
    from scripts.research import h03_extreme_impulse_lib as H03
    rng = np.random.default_rng(3)
    v = np.abs(rng.normal(0, 1, 3500))
    v[100] = np.nan
    assert RS.midrank(v[-2881:-1], v[-1]) == pytest.approx(H03.rolling_midrank_percentile(v, 2880)[-1])


def test_failed_breakouts_are_the_h02_rule():
    from scripts.research import h02_failed_breakout_mean_reversion_lib as H02
    b = bars(walk(600, seed=5, vol=0.002))
    frame = {"high": b.high, "low": b.low, "open": b.open, "close": b.close}
    for L in (60, 120, 240):
        ev = H02.classify_events(frame, L)
        for i in range(60, b.n):
            st = RS.h02_state(b, i)
            if ev["failed"][i]:
                assert st is not None, (L, i)


def test_stress_features_are_computed_as_the_research_did():
    from beta import research_feeds as RF
    from scripts.research.dh3 import aggtrades as A3
    rng = np.random.default_rng(4)
    hour = 0
    t = np.sort(rng.integers(0, 3_600_000, 3000)).astype(np.int64)
    p = 60000 + np.cumsum(rng.normal(0, 2, 3000))
    q = np.where(rng.random(3000) < 0.01, 30.0, 0.1)
    feats = RF.stress_features({"t": t, "p": p, "q": q}, {"t": t, "p": p + 1, "q": q}, hour)
    assert feats["status"] == "OK" and feats["n_large_perp"] == int(np.sum(p * q >= 1e6))
    assert feats["lead_score"] == A3.lead_score(A3.second_grid(t, p, hour), A3.second_grid(t, p + 1, hour))
    few = RF.stress_features({"t": t[:50], "p": p[:50], "q": q[:50]}, {"t": t, "p": p, "q": q}, hour)
    assert few["status"] == "INSUFFICIENT_TRADES" and few["lead_score"] is None
