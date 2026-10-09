"""RP4H_TREND_REGIME_MODULATION_V1: sample, regime variable, estimands, routes. Synthetic data only."""
import math

import numpy as np
import pytest

from scripts.research.rp4h_bitmex_temporal_v1.parent import partial_rank
from scripts.research.rp4h_trend_regime_v1 import constants as K
from scripts.research.rp4h_trend_regime_v1 import evaluate as E
from scripts.research.rp4h_trend_regime_v1 import sample as S


def _bars(n=2400, seed=5):
    rng = np.random.default_rng(seed)
    close = 30000 * np.exp(np.cumsum(rng.normal(0, 0.002, n)))
    high = close * np.exp(np.abs(rng.normal(0, 0.001, n)))
    low = close * np.exp(-np.abs(rng.normal(0, 0.001, n)))
    return {"open_ms": K.SURFACE_START_MS + np.arange(n, dtype=np.int64) * K.BAR_MS, "high": high, "low": low, "close": close}


def test_core_sample_ts_formula_and_past_only(monkeypatch):
    b = _bars()
    monkeypatch.setattr(K, "SURFACE_END_MS", int(b["open_ms"][-1]) + K.BAR_MS)
    s = S.core_sample(b, need_24h=True)
    i = int(s["idx"][10])
    r = np.diff(np.log(b["close"][i - 288:i + 1]))
    assert s["ts"][10] == pytest.approx(abs(math.log(b["close"][i] / b["close"][i - 288])) / math.sqrt((r * r).sum()))
    assert np.all(((b["open_ms"][s["idx"]] - S.PHASE_ORIGIN_MS) // K.BAR_MS) % 3 == 2) and s["idx"].min() >= 288
    b2 = {k: v.copy() for k, v in b.items()}
    b2["close"][1500:] *= 1.1
    s2 = S.core_sample(b2, need_24h=True)
    m = s["idx"] < 1500
    assert np.allclose(s["ts"][m], s2["ts"][: m.sum()]) and np.allclose(s["rp"][m], s2["rp"][: m.sum()])


def test_estimands_match_direct_partials():
    rng = np.random.default_rng(1)
    n = 3000
    s = {k: rng.normal(size=n) for k in ("rp", "ret4", "rv4", "ret1h", "ret15", "ts")}
    s["r1"] = -0.1 * s["rp"] * (s["ts"] < 0) + rng.normal(size=n)
    edges = E.tercile_edges(s["ts"])
    terc = E.terciles(s["ts"], edges)
    e = E.estimands(s, np.arange(n), terc)
    t1 = np.flatnonzero(terc == 0)
    assert e["rho_t1_b0"] == pytest.approx(partial_rank(s["r1"][t1], s["rp"][t1], [s["ret4"][t1], s["rv4"][t1]])["rho"])
    assert e["delta_b0"] == pytest.approx(e["rho_t3_b0"] - e["rho_t1_b0"])
    assert e["rho_t1_b0"] < e["rho_t3_b0"]                      # the planted effect lives only in low TS


def _ci(lo, hi, valid=2000):
    return {"lo": lo, "hi": hi, "valid": valid, "draws": 2000, "se": 0.01}


@pytest.mark.parametrize("d,c,route", [
    (0.02, _ci(0.005, 0.035), K.ROUTE_DISCOVERED),
    (-0.02, _ci(-0.035, -0.005), K.ROUTE_OPPOSITE),
    (0.01, _ci(-0.005, 0.025), K.ROUTE_NONE),
    (0.02, _ci(0.005, 0.035, 1800), K.ROUTE_INVALID),
    (None, _ci(None, None, 0), K.ROUTE_INVALID),
])
def test_route_order(d, c, route):
    assert E.assign_route(d, c) == route


def test_run_refuses(monkeypatch, tmp_path):
    monkeypatch.setattr("sys.argv", ["evaluate", "run"])
    with pytest.raises(SystemExit, match="needs --go"):
        E.main()
    monkeypatch.setattr(K, "DESIGN_SHA256", "PENDING")
    with pytest.raises(SystemExit, match="DESIGN_HASH_UNSET"):
        E.assert_design_frozen()
    m = tmp_path / "r.json"
    m.write_text("{}")
    monkeypatch.setattr(E, "RESULT_JSON", m)
    with pytest.raises(SystemExit, match="REFUSING_RERUN"):
        E.run()
