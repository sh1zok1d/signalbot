"""R03 design locks. Synthetic bars only; no pinned market data is opened."""

from __future__ import annotations

import ast
import datetime as dt
import inspect

import numpy as np

from scripts.research.owner_cards_r03 import constants as K
from scripts.research.owner_cards_r03 import evaluate as E
from scripts.research.owner_cards_r03 import outcomes as O
from scripts.research.owner_cards_r03 import states as S
from scripts.research.owner_cards_r03 import support as SP
from scripts.research.owner_cards_r03 import windows as W


def test_constants_locked():
    K.assert_locked()
    assert K.MIN_MEANINGFUL_EFFECT == 0.5
    assert all(h["DIRECTION"] in ("POSITIVE", "NEGATIVE", "TWO_SIDED") for h in K.HYPOTHESES)


def test_support_never_imports_outcomes():
    tree = ast.parse(inspect.getsource(SP))
    names = {n.names[0].name for n in ast.walk(tree) if isinstance(n, ast.Import)}
    froms = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    for name in ("outcomes", "evaluate", "execute"):
        assert name not in names and not any(name in (m or "") for m in froms)
    # states.py and support.py never touch the BTC target arrays
    for mod in (S, SP):
        src = inspect.getsource(mod)
        assert "high" not in src.replace("highly", "") and "window_log_range" not in src


def test_local_windows_follow_dst():
    summer = W.window_for("NY_0930_60", dt.date(2024, 7, 8))[0]
    winter = W.window_for("NY_0930_60", dt.date(2024, 1, 8))[0]
    assert (summer - W.date_ms(dt.date(2024, 7, 8))) // 60000 == 13 * 60 + 30
    assert (winter - W.date_ms(dt.date(2024, 1, 8))) // 60000 == 14 * 60 + 30
    assert W.last_friday_of_month(2024, 2) == dt.date(2024, 2, 23)
    assert W.last_friday_of_month(2021, 12) == dt.date(2021, 12, 31)


def test_calendar_units_are_label_blind_and_in_bounds():
    units = S.build_units("R03-A1", "DISCOVERY")
    assert len(units) == 260 and all(len(u["STATE"]) == 1 and len(u["COMPARATOR"]) == 4 for u in units)
    t0s = [w[0] for u in units for w in u["STATE"] + u["COMPARATOR"]]
    assert min(t0s) >= K.DISCOVERY_START_MS and max(t0s) + 3_600_000 <= K.DISCOVERY_END_MS
    assert all(W.utc_date(w[0]).weekday() == 4 for u in units for w in u["STATE"])
    closures = [{"EVENT_DATE": "2024-01-15", "EVENT_TYPE": "FULL_DAY_CLOSURE"}]
    c2 = S.build_units("R03-C2", "DISCOVERY", nyse=closures)
    assert "2024-W03" not in {u["UNIT_ID"] for u in c2}
    c3 = S.build_units("R03-C3", "DISCOVERY", nyse=closures)
    assert len(c3) == 1 and len(c3[0]["COMPARATOR"]) == 4
    assert S.build_units("R03-C3", "REPLICATION", nyse=closures) == []


def test_trailing_quantile_state_is_past_only():
    values = np.arange(400, dtype=float)
    state, defined = S.trailing_quantile_states(values, 0.8, 180)
    assert not defined[:180].any() and defined[180:].all()
    assert state[180:].all()  # a rising series is always above its trailing P80
    values2 = values.copy()
    values2[300:] = -1.0  # a future change never affects earlier states
    state2, _ = S.trailing_quantile_states(values2, 0.8, 180)
    assert np.array_equal(state[:300], state2[:300])


def _bars(n_days=30, step=60000, seed=0):
    rng = np.random.default_rng(seed)
    n = n_days * 86_400_000 // step
    t = K.DISCOVERY_START_MS + np.arange(n) * step
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.0005, n)))
    h = c * np.exp(np.abs(rng.normal(0, 0.0003, n)))
    lo = c * np.exp(-np.abs(rng.normal(0, 0.0003, n)))
    return {"open_ms": t, "high": h, "low": lo, "close": c}


def test_window_range_is_granularity_free_and_fails_closed_on_gaps():
    b1 = _bars()
    bars1 = O.Bars(b1, 60000)
    # 5m aggregation of the same bars gives the same hour range
    t5 = b1["open_ms"][::5]
    h5 = b1["high"].reshape(-1, 5).max(axis=1)
    l5 = b1["low"].reshape(-1, 5).min(axis=1)
    c5 = b1["close"].reshape(-1, 5)[:, -1]
    bars5 = O.Bars({"open_ms": t5, "high": h5, "low": l5, "close": c5}, 300000)
    t0 = K.DISCOVERY_START_MS + 5 * 3_600_000
    assert abs(bars1.window_log_range(t0, 60) - bars5.window_log_range(t0, 60)) < 1e-12
    keep = np.ones(b1["open_ms"].size, dtype=bool)
    keep[5 * 60 + 7] = False
    gapped = O.Bars({k: v[keep] for k, v in b1.items()}, 60000)
    assert np.isnan(gapped.window_log_range(t0, 60))
    assert np.isfinite(gapped.window_log_range(t0 + 3_600_000, 60))


def test_signflip_holm_and_classification():
    rng = np.random.default_rng(3)
    null = rng.normal(0, 1, 150)
    assert E.signflip_p(null, 2000, 1)["P_TWO_SIDED"] > 0.05
    strong = rng.normal(0.8, 1, 150)
    assert E.signflip_p(strong, 2000, 1)["P_TWO_SIDED"] < 0.01
    holm = E.holm({"a": 0.001, "b": 0.03, "c": 0.4}, 0.05)
    assert holm["a"]["REJECT"] and not holm["b"]["REJECT"] and not holm["c"]["REJECT"]
    assert E.classify(integrity=True, statistical=True, practical=True, epoch_status="PASS", assessable=False) == "PROMISING_PROTOTYPE"
    assert E.classify(integrity=True, statistical=True, practical=False, epoch_status="PASS", assessable=False) == "NO_INCREMENTAL_STRUCTURE"
    assert E.classify(integrity=True, statistical=True, practical=True, epoch_status="FAIL_HETEROGENEOUS_UNEXPLAINED", assessable=True) == "HETEROGENEOUS_UNEXPLAINED"
    assert E.classify(integrity=True, statistical=True, practical=True, epoch_status="FAIL_HETEROGENEOUS_UNEXPLAINED", assessable=False) == "PROMISING_PROTOTYPE"
    assert not E.practical_gate(0.6, "NEGATIVE")["PASS"] and E.practical_gate(-0.6, "NEGATIVE")["PASS"]
    assert E.nuisance_wording(0.6, 0.1)["WORDING"] == "REFLECTS_GENERAL_VOLATILITY_REGIME"


def test_unit_screen_uses_holm_alpha():
    units = [{"STATE": [0], "COMPARATOR": [0, 0, 0, 0]}] * 260
    assert SP.unit_screen(units, 2)["MDE_STRESS"] < 0.5 < SP.unit_screen(units[:60], 2)["MDE_STRESS"]
    assert SP.unit_screen(units, 4)["MDE_STRESS"] > SP.unit_screen(units, 1)["MDE_STRESS"]
