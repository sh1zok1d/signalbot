"""DH2: pooled events, within-coin terciles, design and governance on synthetic data (offline)."""

from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pytest

from scripts.research.dh1 import constants as K1
from scripts.research.dh1 import events as E1
from scripts.research.dh2 import constants as K
from scripts.research.dh2 import data as D
from scripts.research.dh2 import events as E

REPO = Path(__file__).resolve().parents[2]
T0 = K._ms("2021-03-01")


def _bars(close, seed=7):
    from beta.hist_series import Bars
    rng = np.random.default_rng(seed)
    n = close.size
    q = rng.uniform(1e6, 2e6, n)
    return Bars(t0=T0, open=np.r_[close[0], close[:-1]], high=close * 1.001, low=close * 0.999, close=close.copy(),
                volume=q / close, quote=q, taker_buy_quote=q * rng.uniform(0.3, 0.7, n), oi=np.full(n, np.nan))


def _walk(n, seed=1, vol=0.0015, p0=3000.0):
    rng = np.random.default_rng(seed)
    return p0 * np.exp(np.cumsum(rng.normal(0, vol, n)))


def _spot(b, seed=3):
    rng = np.random.default_rng(seed)
    q = rng.uniform(2e5, 4e5, b.n)
    return {"quote": q, "taker_buy_quote": q * rng.uniform(0.2, 0.8, b.n)}


EPOCHS = [("2021", "2021-01-01", "2022-01-01")]


def test_level_events_drop_round_numbers_and_are_point_in_time():
    c = _walk(288 * 75, seed=11)
    b = _bars(c)
    start, end = K._ms("2021-04-15"), K._ms("2021-05-15")
    ev = E.level_events(b, _spot(b), "ETH", start, end, EPOCHS)
    assert ev and all(e["TYPE"] in K.LEVEL_TYPES and e["SYMBOL"] == "ETH" for e in ev)
    target = ev[len(ev) // 2]
    j = target["J"]
    b2 = _bars(c.copy())
    for arr in (b2.close, b2.high, b2.low):
        arr[j + 1:] *= 1.07
    again = {(e["J"], e["SIDE"]): e for e in E.level_events(b2, _spot(b2), "ETH", start, end, EPOCHS)}[(j, target["SIDE"])]
    for key in ("TYPE", "LEVEL", "RV", "LAG", "PERP_IMB", "SPOT_CONFIRMED_APPROACH", "STALE_LEVEL"):
        assert again[key] == target[key], key


def test_move_events_match_the_dh1_rule():
    n = 2500
    c = _walk(n, seed=5, vol=0.0005, p0=30000.0)
    c[1500:] *= 1.02
    c[2100:] *= 0.98
    b = _bars(c)
    spot = _spot(b)
    old = K1.SURFACES["DISCOVERY"]
    K1.SURFACES["DISCOVERY"] = {**old, "EVENT_START": "2021-03-01", "END": "2021-04-01"}
    try:
        dh1 = E1.move_events(b, spot, "DISCOVERY")
    finally:
        K1.SURFACES["DISCOVERY"] = old
    dh2 = E.move_events(b, spot, "BTC", K._ms("2021-03-01"), K._ms("2021-04-01"), EPOCHS)
    assert [e["J"] for e in dh1] == [e["J"] for e in dh2] and len(dh2) >= 2
    for a, z in zip(dh1, dh2):
        for key in ("DIR", "RATIO", "X", "LAG", "PERP_IMB", "SPOT_SHARE_HIGH_MOVE", "HOUR_BLOCK"):
            assert a[key] == z[key], key


def test_terciles_are_within_each_coin_and_design_has_coin_effects():
    rows = []
    for sym, scale in (("BTC", 1.0), ("DOGE", 10.0)):
        for k in range(30):
            rows.append({"SYMBOL": sym, "EPOCH": "2021", "WEEK": k, "HOUR_BLOCK": k % 6, "RV": scale * (k + 1),
                         "LAG": float(k), "PERP_IMB": float(k % 7), "TYPE_GROUP": "DAY", "STALE_LEVEL": k % 2 == 0,
                         "SPOT_CONFIRMED_APPROACH": True})
    h = K.HYPOTHESIS_BY_ID["DH2-L3"]
    out = E.cell_rows(rows, h)
    for sym in ("BTC", "DOGE"):
        t = [r["RV_TERCILE"] for r in out if r["SYMBOL"] == sym]
        assert sorted(set(t)) == [0, 1, 2] and t.count(0) == 10
    X, labels, _ = E.design_matrix(out, h)
    assert "SYMBOL=DOGE" in labels and labels[:2] == ["INTERCEPT", "S"]


def test_plan_requests_no_protected_object_and_feasibility_reads_no_outcome():
    plan = D.planned()
    assert all(mo <= "2024-12" for _, mo, _ in plan["UM"] + plan["SPOT"])
    assert {s for s, _, _ in plan["UM"]} == {"ETH", "XRP", "BNB", "DOGE", "SOL"}
    assert ("BNB", "2020-03") in {(s, mo) for s, mo, _ in plan["UM"]} and ("BNB", "2020-02") not in {(s, mo) for s, mo, _ in plan["UM"]}
    src = (REPO / "scripts/research/dh2/feasibility.py").read_text()
    names = {a.name for n in ast.walk(ast.parse(src)) if isinstance(n, ast.ImportFrom) for a in n.names}
    assert "outcomes" not in names and "evaluate" not in names
    assert "outcomes" not in (REPO / "scripts/research/dh2/events.py").read_text()


def test_evaluator_refuses_without_a_preregistration(tmp_path, monkeypatch):
    from scripts.research.dh2 import evaluate as V
    monkeypatch.setattr(V, "PREREG", tmp_path / "none.json")
    with pytest.raises(RuntimeError, match="no preregistration"):
        V.verify("DISCOVERY")


def test_design_locked():
    K.assert_locked()
    assert [h["SOURCE"] for h in K.HYPOTHESES] == ["DH1-L1", "DH1-L3", "DH1-B2"]
    assert "ROUND_UP" not in K.LEVEL_TYPES and K.SYMBOLS[0] == "BTC"
