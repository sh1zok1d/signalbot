"""LEVEL_RACE_FORECAST_V1: B0 series, landmark clocks, T15 display rule, HIST cells and ladder.

No market data is read here.
"""

from __future__ import annotations

import math
from types import SimpleNamespace

import numpy as np
import pytest

from scripts.research.level_race_forecast_v1 import b0 as B0
from scripts.research.level_race_forecast_v1 import constants as K
from scripts.research.level_race_forecast_v1 import events as EV
from scripts.research.level_race_forecast_v1 import hist as H
from scripts.research.level_touch_degradation_v1 import constants as K352


def test_landmark_clocks_match_the_352_window():
    assert K.WINDOW_BARS == K352.HOLD_BARS_PRIMARY == 48
    assert K.TAU == {"T0": 48, "T15": 46}   # j+1..j+48 from close j; j+3..j+48 from close j+2


@pytest.mark.parametrize("pos", [99.0, 100.0, 101.3])
@pytest.mark.parametrize("tau", [1, 12, 46, 48, 500])
def test_b0_is_a_distribution(pos, tau):
    p = B0.race_raw(pos, 102.0, 98.0, 0.003, tau)
    assert all(0 <= v <= 1 for v in p)
    assert sum(p) == pytest.approx(1.0, abs=1e-9)


def test_b0_symmetry_and_limits():
    up, dn, ne = B0.race_raw(100.0, 102.0, 100.0 ** 2 / 102.0, 0.003, 48)
    assert up == pytest.approx(dn, abs=1e-12)
    lo = 98.0
    x = (math.log(101.0) - math.log(lo)) / (math.log(103.0) - math.log(lo))
    up, dn, ne = B0.race_raw(101.0, 103.0, lo, 0.01, 1e6)
    assert ne < 1e-9 and up == pytest.approx(x, abs=1e-9)
    up, dn, ne = B0.race_raw(100.0, 110.0, 90.0, 0.001, 1)
    assert ne > 0.999999


def test_b0_out_of_corridor_and_floor():
    assert B0.race_raw(103.0, 102.0, 98.0, 0.003, 48) == (1.0, 0.0, 0.0)
    assert B0.race_raw(97.0, 102.0, 98.0, 0.003, 48) == (0.0, 1.0, 0.0)
    p = B0.race(103.0, 102.0, 98.0, 0.003, 48)
    assert min(p) == pytest.approx(K.PROB_FLOOR / (1 + 2 * K.PROB_FLOOR))
    assert sum(p) == pytest.approx(1.0)


def test_b0_against_fixed_seed_simulation():
    rng = np.random.default_rng(20261008)
    sigma, tau, steps = 0.003, 48, 2400
    lo, hi, start = math.log(98.8), math.log(101.0), math.log(100.0)
    n = 20000
    dt = tau / steps
    x = np.full(n, start)
    state = np.zeros(n, dtype=int)  # 0 alive, 1 up, 2 down
    for _ in range(steps):
        alive = state == 0
        x[alive] += rng.normal(0.0, sigma * math.sqrt(dt), alive.sum())
        state[alive & (x >= hi)] = 1
        state[alive & (x <= lo)] = 2
    sim = (np.mean(state == 1), np.mean(state == 2), np.mean(state == 0))
    up, dn, ne = B0.race_raw(100.0, 101.0, 98.8, sigma, tau)
    # discrete monitoring misses some crossings; 2400 steps keep the bias near 1 pp
    assert up == pytest.approx(sim[0], abs=0.025)
    assert dn == pytest.approx(sim[1], abs=0.025)
    assert ne == pytest.approx(sim[2], abs=0.025)


def _touch(side=1, j=10):
    return {"episode_id": "PDH:1:0", "j": j, "side": side, "struct_side": 1, "family": "DAY",
            "zone_low": 99.85, "zone_high": 100.15, "x_primary": 0.004, "sigma": 0.002,
            "week": 1, "year": 2021}


def _bars(n=80, base=100.0):
    close = np.full(n, base)
    return SimpleNamespace(high=close + 0.05, low=close - 0.05, close=close.copy())


def test_t15_row_only_when_unresolved_on_j1_j2():
    t = _touch()
    b = _bars()
    rows = EV.landmark_rows(b, [t])
    assert [r["landmark"] for r in rows] == ["T0", "T15"]
    assert rows[1]["tau"] == 46 and rows[0]["tau"] == 48
    up = 100.15 * 1.004
    b2 = _bars(); b2.high[12] = up + 0.01                      # BREAK barrier on j+2
    assert [r["landmark"] for r in EV.landmark_rows(b2, [t])] == ["T0"]
    b3 = _bars(); b3.high[11] = up + 0.01; b3.low[11] = 99.85 * 0.996 - 0.01   # AMBIGUOUS on j+1
    assert [r["landmark"] for r in EV.landmark_rows(b3, [t])] == ["T0"]
    b4 = _bars(); b4.high[13] = up + 0.01                      # j+3 is not early
    assert [r["landmark"] for r in EV.landmark_rows(b4, [t])] == ["T0", "T15"]


def test_orientation_maps_beyond_to_the_approach_direction():
    b = _bars()
    b.close[10] = 100.1
    r_up = EV.landmark_rows(b, [_touch(side=1)])[0]
    r_dn = EV.landmark_rows(b, [_touch(side=-1)])[0]
    assert r_up["beyond_is_up"] and not r_dn["beyond_is_up"]
    assert r_up["b0_beyond"] == pytest.approx(r_dn["b0_back"])
    assert r_up["p_up"] == r_dn["p_up"] and r_up["p_dn"] == r_dn["p_dn"]


def test_outcomes_use_the_original_window():
    t = _touch()
    b = _bars(); b.high[58] = 100.15 * 1.004 + 0.01            # j+48
    rows = EV.attach_outcomes(b, EV.landmark_rows(b, [t]), [t])
    assert [r["outcome"] for r in rows] == ["BEYOND", "BEYOND"]
    b = _bars(); b.high[59] = 100.15 * 1.004 + 0.01            # j+49 is outside
    rows = EV.attach_outcomes(b, EV.landmark_rows(b, [t]), [t])
    assert [r["outcome"] for r in rows] == ["NEITHER", "NEITHER"]


def test_bands_and_cells():
    assert K.BAND_EDGES == (0.35, 0.55)
    assert [H.band_of(v) for v in (0.0, 0.3499, 0.35, 0.5499, 0.55, 1.0)] == ["F1", "F1", "F2", "F2", "F3", "F3"]
    keys = H.all_cell_keys()
    assert sum(k.startswith("T0|") for k in keys) == 6
    assert sum(k.startswith("T15|") and "|ANY|" not in k for k in keys) == 18


def _row(lm, fam, side, b0b, outcome, week):
    return {"landmark": lm, "family": fam, "struct_side": side, "b0_beyond": b0b, "b0_back": (1 - b0b) * 0.8,
            "b0_neither": 1 - b0b - (1 - b0b) * 0.8, "outcome": outcome, "week": week}


def test_ladder_pools_sides_then_low_n_and_counts_ambiguous():
    rows = [_row("T0", "DAY", 1, 0.45, "BEYOND" if i % 2 else "BACK", i) for i in range(40)]
    rows += [_row("T0", "DAY", 1, 0.45, "AMBIGUOUS", 1)]
    rows += [_row("T15", "WEEK", 1, 0.6, "NEITHER", i) for i in range(20)]
    rows += [_row("T15", "WEEK", -1, 0.6, "BACK", i) for i in range(15)]
    rows += [_row("T15", "MONTH", 1, 0.2, "BACK", i) for i in range(5)]
    t = H.build_table(rows, provenance={})
    assert t["ladder"]["T0|DAY|H"]["level"] == "CELL"
    assert t["cells"]["T0|DAY|H"]["n"] == 40 and t["cells"]["T0|DAY|H"]["ambiguous"] == 1
    assert t["ladder"]["T15|WEEK|H|F3"] == {"level": "POOLED_SIDE", "source": "T15|WEEK|ANY|F3"}
    assert t["cells"]["T15|WEEK|ANY|F3"]["n"] == 35
    assert t["ladder"]["T15|MONTH|H|F1"]["level"] == "LOW_N"
    assert t["ladder"]["T0|MONTH|L"]["level"] == "LOW_N"
    c = t["cells"]["T0|DAY|H"]
    lo, hi = c["diff_ci95_pp"]["BEYOND"]
    assert lo <= c["diff_pp"]["BEYOND"] <= hi and c["k_pp"]["BEYOND"] >= 0
    assert H.build_table(rows, provenance={})["table_sha256"] == t["table_sha256"]
    assert H.lookup(t, _row("T15", "MONTH", 1, 0.2, None, 0)) is None


def test_two_head_recovers_offsets_on_synthetic_rows():
    from scripts.research.level_race_forecast_v1 import model as M
    rng = np.random.default_rng(1)
    rows = []
    for i in range(6000):
        b = rng.uniform(0.2, 0.5)
        n_ = rng.uniform(0.05, 0.2)
        p0 = np.array([b, 1 - b - n_, n_])
        # truth: resolve logit +0.5 over B0, BEYOND|resolve logit +0.4 over B0
        pr = M.sigmoid(M.logit(np.array([1 - n_]))[0] + 0.5)
        pb = M.sigmoid(M.logit(np.array([b / (1 - n_)]))[0] + 0.4)
        u = rng.uniform()
        y = "NEITHER" if u > pr else ("BEYOND" if rng.uniform() < pb else "BACK")
        rows.append({"landmark": "T0", "family": "DAY", "struct_side": 1, "sigma": 0.002,
                     "b0_beyond": p0[0], "b0_back": p0[1], "b0_neither": p0[2], "outcome": y})
    m = M.fit_two_head(rows, ("1",), ("1",), 0.0005, edges=(0.001, 0.003))
    assert m.beta_r[0] == pytest.approx(0.5, abs=0.12)
    assert m.beta_b[0] == pytest.approx(0.4, abs=0.12)
    P = m.predict(rows)
    assert np.allclose(P.sum(axis=1), 1.0)


def test_weighted_logit_equals_repeated_rows():
    from scripts.research.level_race_forecast_v1 import model as M
    rng = np.random.default_rng(2)
    X = np.column_stack([np.ones(200), rng.normal(size=200)])
    y = (rng.uniform(size=200) < 0.4).astype(float)
    w = rng.integers(0, 3, size=200).astype(float)
    pen = np.array([False, True])
    a = M.fit_logit(X, np.zeros(200), y, 0.01, pen, w=w)
    keep = w > 0
    b = M.fit_logit(np.repeat(X[keep], w[keep].astype(int), axis=0), np.zeros(int(w.sum())),
                    np.repeat(y[keep], w[keep].astype(int)), 0.01, pen)
    assert np.allclose(a, b, atol=1e-6)


def test_metrics_basic_shapes():
    from scripts.research.level_race_forecast_v1 import metrics as MT
    rng = np.random.default_rng(3)
    P = rng.dirichlet([2, 2, 1], size=300)
    y = np.array([rng.choice(3, p=p) for p in P])
    wk = np.repeat(np.arange(60), 5)
    out = MT.evaluate(P, y, wk, {"SELF": P}, MT.WeekBoot(wk, draws=50), slope_ci=True)
    assert out["ll_gain_vs_SELF"] == 0.0 and out["n"] == 300
    assert abs(out["heads"]["R"]["recal_b"] - 1) < 0.6
    assert MT.auc(np.array([0.1, 0.9]), np.array([0, 1])) == 1.0
