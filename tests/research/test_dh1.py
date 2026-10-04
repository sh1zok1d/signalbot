"""DH1: data aggregation, point-in-time events, outcomes and inference on synthetic data.

Offline: no network and no market data are read.
"""

from __future__ import annotations

import ast
import datetime as dt
import gzip
import io
import json
from pathlib import Path

import numpy as np
import pytest

from beta.hist_series import Bars
from scripts.research.dh1 import constants as K
from scripts.research.dh1 import data as D
from scripts.research.dh1 import events as E
from scripts.research.dh1 import outcomes as O
from scripts.research.dh1 import stats as S

REPO = Path(__file__).resolve().parents[2]
T0 = K._ms("2021-03-01")


def _bars(close: np.ndarray, spread: float = 0.001, t0: int = T0) -> Bars:
    n = close.size
    rng = np.random.default_rng(7)
    q = rng.uniform(1e6, 2e6, n)
    return Bars(t0=t0, open=np.r_[close[0], close[:-1]], high=close * (1 + spread), low=close * (1 - spread),
                close=close.copy(), volume=q / close, quote=q, taker_buy_quote=q * rng.uniform(0.3, 0.7, n),
                oi=np.full(n, np.nan))


def _walk(n: int, seed: int = 1, vol: float = 0.002) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return 30000.0 * np.exp(np.cumsum(rng.normal(0, vol, n)))


def _spot(b: Bars, seed: int = 3) -> dict:
    rng = np.random.default_rng(seed)
    q = rng.uniform(2e5, 4e5, b.n)
    return {"quote": q, "taker_buy_quote": q * rng.uniform(0.2, 0.8, b.n)}


def test_rolling_sigma_matches_direct_std():
    c = _walk(400)
    sg = E.rolling_sigma(c, window=50)
    r = np.log(c[1:] / c[:-1])
    e = 200
    assert sg[e] == pytest.approx(np.std(r[e - 50:e], ddof=1), rel=1e-9)
    assert np.isnan(sg[10])


def test_aggregate_1m_to_5m_keeps_complete_bins_only():
    t = np.r_[np.arange(0, 5), np.arange(5, 9)] * K.MINUTE_MS + T0   # second bin misses one minute
    o = np.arange(9, dtype=float) + 1
    out = D.aggregate_1m_to_5m(t, o, o + 0.5, o - 0.5, o + 0.1, np.ones(9), np.full(9, 10.0), np.full(9, 4.0))
    assert out["open_ms"].tolist() == [T0]
    assert out["open"][0] == 1 and out["close"][0] == pytest.approx(5.1)
    assert out["high"][0] == 5.5 and out["low"][0] == 0.5
    assert out["quote"][0] == 50 and out["taker_buy_quote"][0] == 20


def test_bitmex_day_aggregation_uses_xbtusd_and_taker_side():
    rows = ["timestamp,symbol,side,size,price,tickDirection,trdMatchID,grossValue,homeNotional,foreignNotional",
            "2018-01-01D00:00:01.000000000,XBTUSD,Buy,10,100,x,a,0,0.1,10",
            "2018-01-01D00:01:00.000000000,ETHH18,Buy,10,5,x,b,0,1,5",
            "2018-01-01D00:02:00.000000000,XBTUSD,Sell,20,90,x,c,0,0.2,20",
            "2018-01-01D00:05:00.000000000,XBTUSD,Buy,30,95,x,d,0,0.3,30"]
    payload = gzip.compress(("\n".join(rows) + "\n").encode())
    out, n = D.aggregate_bitmex_day(payload, dt.date(2018, 1, 1))
    assert n == 3 and len(out) == 2
    t, o, h, lo, c, vol, quote, tbq, trades = out[0]
    assert (o, h, lo, c, quote, tbq, trades) == (100.0, 100.0, 90.0, 90.0, 30.0, 10.0, 2)
    assert out[1][0] - t == K.BAR_MS and out[1][7] == 30.0


def test_dedupe_keeps_the_most_important_type():
    touches = [(10, "PDH", 101.0, 1), (10, "ROUND_UP", 100.9, 1), (10, "PWH", 101.0, 1), (10, "PDL", 90.0, -1)]
    out = E.dedupe_touches(touches)
    assert out == [(10, "PDL", 90.0, -1), (10, "PWH", 101.0, 1)]


def test_stale_level_rule():
    c = np.full(400, 100.0)
    b = _bars(c, spread=0.0005)
    assert E.stale(b, 350, 100.0) is False
    assert E.stale(b, 350, 105.0) is True
    assert E.stale(b, 100, 105.0) is None          # not enough history


def test_barrier_outcome_directions_ties_and_no_hit():
    c = np.full(120, 100.0)
    b = _bars(c, spread=0.0)
    b.high[20], b.low[30] = 102.0, 98.0            # up first, then down
    assert O.barrier(b, 10, +1, 0.01) == 1.0
    assert O.barrier(b, 10, -1, 0.01) == 0.0
    b2 = _bars(c, spread=0.0)
    assert O.barrier(b2, 10, +1, 0.01) == 0.5      # neither within 4h
    b3 = _bars(c, spread=0.0)
    b3.high[20], b3.low[20] = 102.0, 98.0
    assert O.barrier(b3, 10, +1, 0.01) == 0.5      # both in the same bar
    b4 = _bars(c, spread=0.0)
    b4.high[70] = 102.0                            # beyond 4h: not counted
    assert O.barrier(b4, 10, +1, 0.01) == 0.5


def test_level_hold_matches_product_metric():
    c = np.full(120, 100.0)
    b = _bars(c)
    b.close[10 + K.HOLD_BARS] = 101.0
    assert O.level_hold(b, 10, 100.5, +1) == 1.0
    assert O.level_hold(b, 10, 100.5, -1) == 0.0
    b.close[10 + K.HOLD_BARS] = np.nan
    assert O.level_hold(b, 10, 100.5, +1) is None


def test_move_events_direction_refractory_and_point_in_time():
    n = 2000
    c = _walk(n, seed=5, vol=0.0005)
    c[1500:] *= 1.02                               # one sharp 5m jump at bar 1500
    b = _bars(c)
    spot = _spot(b)
    ev = _moves(b, spot)
    hits = [e for e in ev if 1498 <= e["J"] <= 1502]
    assert len(hits) == 1 and hits[0]["DIR"] == 1 and hits[0]["J"] == 1500
    assert all(abs(a["J"] - z["J"]) > K.MOVE_REFRACTORY_BARS for a, z in zip(ev, ev[1:]))
    # changing the future does not change the event's features
    b2 = _bars(c.copy())
    b2.close[1501:] *= 0.9
    b2.high[1501:] *= 0.9
    b2.low[1501:] *= 0.9
    ev2 = _moves(b2, spot)
    same = [e for e in ev2 if e["J"] == 1500][0]
    for key in ("RATIO", "X", "LAG", "PERP_IMB", "SPOT_CONFIRMED_MOVE", "SPOT_SHARE_HIGH_MOVE", "RV", "HOUR_BLOCK"):
        assert same[key] == hits[0][key], key


def _moves(b: Bars, spot: dict) -> list:
    old = K.SURFACES["DISCOVERY"]
    K.SURFACES["DISCOVERY"] = {**old, "EVENT_START": "2021-03-01", "END": "2021-04-01"}
    try:
        return E.move_events(b, spot, "DISCOVERY")
    finally:
        K.SURFACES["DISCOVERY"] = old


def test_level_events_are_point_in_time():
    n = 288 * 75
    c = _walk(n, seed=11, vol=0.0015)
    b = _bars(c)
    spot = _spot(b)
    old = K.SURFACES["DISCOVERY"]
    K.SURFACES["DISCOVERY"] = {**old, "EVENT_START": "2021-04-15", "END": "2021-05-15"}
    try:
        ev = E.level_events(b, spot, "DISCOVERY")
        assert ev, "synthetic walk should touch some levels"
        target = ev[len(ev) // 2]
        j = target["J"]
        b2 = _bars(c.copy())
        b2.close[j + 1:] *= 1.05
        b2.high[j + 1:] *= 1.05
        b2.low[j + 1:] *= 1.05
        ev2 = {(e["J"], e["SIDE"]): e for e in E.level_events(b2, spot, "DISCOVERY")}
        again = ev2[(j, target["SIDE"])]
        for key in ("TYPE", "LEVEL", "RV", "LAG", "PERP_IMB", "SPOT_CONFIRMED_APPROACH", "CONFLUENT_LEVEL", "STALE_LEVEL"):
            assert again[key] == target[key], key
    finally:
        K.SURFACES["DISCOVERY"] = old


def test_lpm_bootstrap_recovers_a_planted_effect_and_holm():
    rng = np.random.default_rng(0)
    n = 6000
    s = rng.integers(0, 2, n)
    nuis = rng.integers(0, 3, n)
    y = (rng.random(n) < 0.45 + 0.08 * s + 0.05 * (nuis == 2)).astype(float)
    X = np.column_stack([np.ones(n), s, nuis == 1, nuis == 2]).astype(float)
    rows = [{"WEEK": k // 20, "EPOCH": ("A", "B", "C")[k * 3 // n]} for k in range(n)]
    cid = S.cluster_ids(rows)
    xtx, xty, arms = S.aggregates(X, y, cid)
    beta = S.solve(xtx.sum(0), xty.sum(0))[S.S_COL]
    draws = S.bootstrap_beta(xtx, xty, 500, np.random.default_rng(1))
    assert beta == pytest.approx(0.08, abs=0.03)
    assert S.boot_p(draws) < 0.01
    adj = S.holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert adj["a"] == pytest.approx(0.03) and adj["c"] == pytest.approx(0.06) and adj["b"] == pytest.approx(0.06)
    bss = S.crossfit_bss(X, y, [r["EPOCH"] for r in rows])
    assert bss > 0
    het = S.het_test(xtx, xty, arms, S.cluster_epochs(rows, cid), ["A", "B", "C"], beta, np.random.default_rng(2),
                     se_draws=100, perms=200)
    assert het["STATUS"] in ("PASS", "PASS_MAGNITUDE_VARIES_BY_EPOCH")


def test_feasibility_never_imports_outcomes_and_inventories_avoid_protected_years():
    src = (REPO / "scripts/research/dh1/feasibility.py").read_text()
    imported = {a.name for n in ast.walk(ast.parse(src)) if isinstance(n, ast.ImportFrom) for a in n.names}
    assert "outcomes" not in imported and "evaluate" not in imported
    for mod in ("events.py", "data.py", "stats.py"):
        text = (REPO / "scripts/research/dh1" / mod).read_text()
        assert "import outcomes" not in text and "from . import outcomes" not in text
    spot = json.loads(D.SPOT_INVENTORY.read_text())
    assert all(o["MONTH"] <= "2024-12" for o in spot["OBJECTS"]) and len(spot["OBJECTS"]) == 89
    assert all(o["CHECKSUM_VERIFICATION"] == "VERIFIED" for o in spot["OBJECTS"])
    with pytest.raises(RuntimeError):
        D._refuse_protected(dt.date(2025, 1, 1))


def test_design_constants_locked():
    K.assert_locked()
    assert K.PRACTICAL_BAR == 0.03 and K.BARRIER_FRACTION == 0.5 and K.HOLD_BARS == 48
    assert {h["CARD"] for h in K.HYPOTHESES} == set(K.CARDS)


def _cell(shift, ci, bss, het="PASS"):
    return {"ADJUSTED_SHIFT": shift, "CI95": ci, "BRIER_SKILL": bss, "HETEROGENEITY": {"STATUS": het}}


def test_classification_rules():
    from scripts.research.dh1 import evaluate as V
    assert V.classify_discovery(_cell(0.05, [0.02, 0.08], 0.001), 0.01, True) == "PROMISING_PROTOTYPE"
    assert V.classify_discovery(_cell(0.05, [0.02, 0.08], 0.001, "FAIL_HETEROGENEOUS_UNEXPLAINED"), 0.01, True) \
        == "HETEROGENEOUS_UNEXPLAINED"
    assert V.classify_discovery(_cell(0.05, [0.02, 0.08], 0.001, "FAIL_HETEROGENEOUS_UNEXPLAINED"), 0.01, False) \
        == "PROMISING_PROTOTYPE"
    assert V.classify_discovery(_cell(0.05, [0.02, 0.08], -0.001), 0.01, True) == "NO_INCREMENTAL_STRUCTURE"
    assert V.classify_discovery(_cell(0.02, [0.01, 0.029], 0.001), 0.01, True) == "NO_INCREMENTAL_STRUCTURE"
    assert V.classify_discovery(_cell(0.01, [-0.02, 0.025], 0.0), 0.5, True) == "NO_INCREMENTAL_STRUCTURE"
    assert V.classify_discovery(_cell(0.02, [-0.01, 0.05], 0.0), 0.2, True) == "INCONCLUSIVE"
    assert V.classify_replication(_cell(0.04, [0.01, 0.07], 0.001), 0.01, 0.05, True, True) == "SUPPORTED_UNCONDITIONAL"
    assert V.classify_replication(_cell(-0.04, [-0.07, -0.01], 0.001), 0.01, 0.05, True, True) == "REPLICATION_FAILED"
    assert V.classify_replication(_cell(0.02, [-0.02, 0.06], 0.0), 0.3, 0.05, False, True) == "REPLICATION_INCONCLUSIVE"
    assert V.classify_replication(_cell(0.02, [-0.02, 0.06], 0.0), 0.3, 0.05, True, True) == "REPLICATION_FAILED"
    assert V.DISPLAY["SUPPORTED_UNCONDITIONAL"] == "Проверено" and V.DISPLAY["PROMISING_PROTOTYPE"] == "Гипотеза"
    assert "NO_INCREMENTAL_STRUCTURE" not in V.DISPLAY


def test_evaluator_refuses_without_a_committed_preregistration(tmp_path, monkeypatch):
    from scripts.research.dh1 import evaluate as V
    monkeypatch.setattr(V, "PREREG", tmp_path / "missing.json")
    with pytest.raises(RuntimeError, match="no preregistration"):
        V.verify("DISCOVERY")
