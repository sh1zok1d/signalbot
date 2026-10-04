"""DH3: point-in-time features, controls, retests, lead score, range outcomes and classification
on synthetic data (offline; no market data)."""

from __future__ import annotations

import ast
import math
from pathlib import Path

import numpy as np
import pytest

from beta.hist_series import Bars
from scripts.research.dh1 import events as E1
from scripts.research.dh3 import aggtrades as A
from scripts.research.dh3 import constants as K
from scripts.research.dh3 import features as FT
from scripts.research.dh3 import outcomes as O

REPO = Path(__file__).resolve().parents[2]
T0 = K._ms("2021-03-01")


def _bars(close, seed=7):
    rng = np.random.default_rng(seed)
    n = close.size
    q = rng.uniform(1e6, 2e6, n)
    return Bars(t0=T0, open=np.r_[close[0], close[:-1]], high=close * 1.0015, low=close * 0.9985, close=close.copy(),
                volume=q / close, quote=q, taker_buy_quote=q * rng.uniform(0.3, 0.7, n), oi=np.full(n, np.nan))


def _walk(n, seed=1, vol=0.0015):
    rng = np.random.default_rng(seed)
    return 30000.0 * np.exp(np.cumsum(rng.normal(0, vol, n)))


def test_range_outcome_and_base_lags_are_point_in_time():
    c = _walk(2000)
    b = _bars(c)
    sigma = E1.rolling_sigma(b.close)
    j = 1000
    r = O.range_4h(b, j)
    assert r == pytest.approx(math.log((b.high[j + 1:j + 49].max() - b.low[j + 1:j + 49].min()) / b.close[j]))
    row = FT.base(b, j, sigma, "BTC", "RANGE_4H")
    b2 = _bars(c.copy())
    for arr in (b2.close, b2.high, b2.low):
        arr[j + 1:] *= 1.1
    row2 = FT.base(b2, j, E1.rolling_sigma(b2.close), "BTC", "RANGE_4H")
    for key in ("RV", "LAG", "ABS_RET1", "TREND24", "X", "HOUR_BLOCK"):
        assert row[key] == row2[key], key
    assert FT.base(b, j, sigma, "BTC", "CONT_FIRST_4H", d=-1)["LAG"] == pytest.approx(
        -math.log(b.close[j - 12] / b.close[j - 60]))


def test_hourly_grid_lands_on_the_hour():
    b = _bars(_walk(3000))
    js = FT.hourly_js(b, T0, T0 + 3000 * 300_000)
    assert js and all(E1.decision_ms(b, j) % 3_600_000 == 0 for j in js)
    assert all(E1.decision_ms(b, j) + 48 * 300_000 <= T0 + 3000 * 300_000 for j in js)


def test_session_events_have_real_and_control_levels_on_the_right_side():
    b = _bars(_walk(288 * 20, seed=3))
    rows = FT.session_events(b, "ETH", T0, T0 + 288 * 20 * 300_000, np.random.default_rng(0))
    assert {r["S"] for r in rows} == {0, 1}
    assert {r["SESSION"] for r in rows} <= {"ASIA", "EU", "US"}
    for r in rows:
        j = r["J"]
        assert (b.high[j] >= r["LEVEL"]) if r["SIDE"] > 0 else (b.low[j] <= r["LEVEL"])


def test_key_level_controls_and_retests():
    b = _bars(_walk(288 * 75, seed=11))
    end = T0 + 288 * 75 * 300_000
    rows = FT.key_level_events(b, "BTC", T0 + 288 * 35 * 300_000, end, np.random.default_rng(1))
    assert {r["S"] for r in rows} == {0, 1} and {r["TYPE_GROUP"] for r in rows} <= {"DAY", "WEEK", "MONTH", "POC"}
    rt = FT.retest_events(b, "BTC", T0 + 288 * 35 * 300_000, end)
    firsts = [r for r in rt if r["S"] == 0]
    seconds = [r for r in rt if r["S"] == 1]
    assert firsts and all(r["TYPE"] in ("PDH", "PDL") for r in rt)
    for r in seconds:                     # a retest comes after a first touch of the same level on the same day
        assert any(f["LEVEL"] == r["LEVEL"] and f["J"] < r["J"] for f in firsts)


def test_lead_score_sign_follows_the_leader():
    rng = np.random.default_rng(5)
    base_r = rng.normal(0, 1e-4, 3601)
    leader = 30000 * np.exp(np.cumsum(base_r))
    follower = np.r_[leader[0], leader[0], leader[:-2]]            # follows two seconds later
    assert A.lead_score(leader, follower) > 0                       # first argument (perp) leads
    assert A.lead_score(follower, leader) < 0
    hour = 0
    times = np.array([0, 1500, 2500, 7_200], dtype=np.int64)
    grid = A.second_grid(times, np.array([1.0, 2.0, 3.0, 4.0]), hour)
    assert grid[0] == 1.0 and grid[1] == 2.0 and grid[2] == 3.0 and grid[5] == 3.0 and grid[7] == 4.0 and grid[-1] == 4.0


def test_range_classification_uses_the_range_bar():
    from scripts.research.dh3 import evaluate as V
    bar = K.RANGE_BAR
    c = {"BAR": bar, "ADJUSTED_SHIFT": 0.20, "CI95": [0.15, 0.25], "SKILL": 0.01,
         "HETEROGENEITY": {"STATUS": "PASS"}, "HETEROGENEITY_SYMBOL": {"STATUS": "PASS"}}
    dec = {"HET_EPOCH": "NOT_ASSESSABLE", "HET_SYMBOL": "NOT_ASSESSABLE"}
    assert V.classify_discovery(c, 0.001, dec) == "PROMISING_PROTOTYPE"
    assert V.classify_discovery({**c, "ADJUSTED_SHIFT": 0.08, "CI95": [0.06, 0.10]}, 0.001, dec) == "NO_INCREMENTAL_STRUCTURE"
    assert V.classify_discovery({**c, "ADJUSTED_SHIFT": 0.05, "CI95": [-0.10, 0.20]}, 0.4, dec) == "INCONCLUSIVE"
    assert V.classify_discovery({**c, "SKILL": -0.001}, 0.001, dec) == "NO_INCREMENTAL_STRUCTURE"


def test_feasibility_reads_no_outcome_and_design_is_locked():
    K.assert_locked()
    for mod in ("feasibility.py", "features.py", "data.py", "aggtrades.py"):
        src = (REPO / "scripts/research/dh3" / mod).read_text()
        names = {a.name for n in ast.walk(ast.parse(src)) if isinstance(n, ast.ImportFrom) for a in n.names}
        assert "outcomes" not in names and "evaluate" not in names, mod
    assert sum(1 for h in K.HYPOTHESES if h["ENDPOINT"] == "RANGE_4H") == 9


def test_evaluator_refuses_without_preregistration(tmp_path, monkeypatch):
    from scripts.research.dh3 import evaluate as V
    monkeypatch.setattr(V, "PREREG", tmp_path / "none.json")
    with pytest.raises(RuntimeError, match="no preregistration"):
        V.verify("DISCOVERY")
