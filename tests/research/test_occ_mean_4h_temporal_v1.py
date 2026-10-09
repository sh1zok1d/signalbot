"""OCC_MEAN_4H_TEMPORAL_REPLICATION_V1: identity with the discovery formula and Unit A's sample, algebra, routes.

Synthetic data only; the canonical BitMEX file is never parsed for prices here."""
import numpy as np
import pytest

from scripts.research.directional_state_search_v2 import features as DF
from scripts.research.occ_mean_4h_temporal_v1 import constants as K
from scripts.research.occ_mean_4h_temporal_v1 import evaluate as E
from scripts.research.rp4h_bitmex_temporal_v1 import constants as KA
from scripts.research.rp4h_bitmex_temporal_v1 import evaluate as EA

T0 = 1_514_764_800_000  # 2018-01-01


def _series(n=4000, seed=2, drop=()):
    rng = np.random.default_rng(seed)
    close = 9000 * np.exp(np.cumsum(rng.normal(0, 0.002, n)))
    high = close * np.exp(np.abs(rng.normal(0, 0.001, n)))
    low = close * np.exp(-np.abs(rng.normal(0, 0.001, n)))
    keep = np.ones(n, dtype=bool)
    keep[list(drop)] = False
    t = T0 + np.arange(n, dtype=np.int64) * KA.BAR_MS
    return {"open_ms": t[keep], "high": high[keep], "low": low[keep], "close": close[keep],
            "trades": np.ones(int(keep.sum()), dtype=np.int64)}


@pytest.fixture
def sample(monkeypatch):
    s = _series(drop=(2000,))
    monkeypatch.setattr(KA, "SURFACE_END_MS", int(s["open_ms"][-1]) + KA.BAR_MS)
    return s, E.occ_sample(s)


def test_sample_is_unit_a_sample_and_occ_is_the_discovery_formula(sample):
    series, s = sample
    a = EA.build_sample(series)
    assert np.array_equal(a["close_ms"], s["close_ms"]) and np.allclose(a["rp"], s["rp"])
    g = s["_grid"]
    k = 37
    i = int(s["idx"][k])
    hi, lo = g["high"][i - 47:i + 1].max(), g["low"][i - 47:i + 1].min()
    p = (g["close"][i - 47:i] - lo) / (hi - lo)                      # 47 prior closes; the current close excluded
    assert s["occ"][k] == pytest.approx(p.mean())
    assert s["occ"][k] == pytest.approx(DF.occupancy(g, np.array([i]))["OCC_MEAN_4H"][0])
    assert not np.any((s["idx"] - 48 <= 2000) & (s["idx"] >= 2000)) and not np.any(s["idx"] + 12 == 2000)


def test_occ_is_past_only(monkeypatch):
    s1 = _series()
    monkeypatch.setattr(KA, "SURFACE_END_MS", int(s1["open_ms"][-1]) + KA.BAR_MS)
    a = E.occ_sample(s1)
    s2 = {c: v.copy() for c, v in s1.items()}
    for c in ("high", "low", "close"):
        s2[c][2500:] *= 1.08
    b = E.occ_sample(s2)
    m = a["idx"] < 2500
    assert np.allclose(a["occ"][m], b["occ"][m])


def test_identity_audit_algebra(sample):
    _, s = sample
    ida = E.identity_audit(s)
    assert ida["max_abs_algebra_residual"] < 1e-9
    assert 0.0 < ida["r2_rank_occ_on_B1"] < 1.0 and ida["r2_rank_occ_on_B0"] <= ida["r2_rank_occ_on_B1"] + 1e-12


def _ci(lo, hi, valid=2000):
    return {"lo": lo, "hi": hi, "valid": valid, "draws": 2000}


@pytest.mark.parametrize("pts,cis,route,flags", [
    ({"primary_b1": 0.01, "b0": 0.02}, {"primary_b1": _ci(0.002, 0.02), "b0": _ci(0.01, 0.03)}, K.ROUTE_SUPPORTED, []),
    ({"primary_b1": 0.01, "b0": -0.01}, {"primary_b1": _ci(0.002, 0.02), "b0": _ci(-0.02, 0.0)}, K.ROUTE_SUPPORTED, []),
    ({"primary_b1": 0.002, "b0": 0.02}, {"primary_b1": _ci(-0.005, 0.01), "b0": _ci(0.01, 0.03)}, K.ROUTE_LOCAL_PATH, []),
    ({"primary_b1": -0.01, "b0": 0.02}, {"primary_b1": _ci(-0.02, -0.002), "b0": _ci(0.01, 0.03)}, K.ROUTE_LOCAL_PATH,
     [K.FLAG_PRIMARY_OPPOSES]),
    ({"primary_b1": 0.002, "b0": 0.01}, {"primary_b1": _ci(-0.005, 0.01), "b0": _ci(-0.001, 0.02)}, K.ROUTE_NOT, []),
    ({"primary_b1": -0.01, "b0": -0.02}, {"primary_b1": _ci(-0.02, -0.002), "b0": _ci(-0.03, -0.01)}, K.ROUTE_NOT,
     [K.FLAG_PRIMARY_OPPOSES]),
    ({"primary_b1": 0.01, "b0": 0.02}, {"primary_b1": _ci(0.002, 0.02, 1800), "b0": _ci(0.01, 0.03)}, K.ROUTE_INVALID, []),
    ({"primary_b1": None, "b0": 0.02}, {"primary_b1": _ci(None, None, 0), "b0": _ci(0.01, 0.03)}, K.ROUTE_INVALID, []),
])
def test_frozen_route_order(pts, cis, route, flags):
    assert E.assign_route(pts, cis) == (route, flags)


def test_point_estimates_match_parent_partial(sample):
    _, s = sample
    from scripts.research.rp4h_bitmex_temporal_v1.parent import partial_rank, spearman
    assert E.estimate(s, None, ()) == pytest.approx(spearman(s["occ"], s["r1"]))
    ctrl = dict(K.ESTIMANDS)[K.PRIMARY]
    assert E.estimate(s, None, ctrl) == pytest.approx(partial_rank(s["r1"], s["occ"], [s[c] for c in ctrl])["rho"])
    assert ctrl == ("rp", "ret4", "rv4", "ret1h", "ret15")


def test_run_refuses_without_go_unfrozen_and_when_scored(monkeypatch, tmp_path):
    monkeypatch.setattr("sys.argv", ["evaluate", "run"])
    with pytest.raises(SystemExit, match="needs --go"):
        E.main()
    monkeypatch.setattr(K, "DESIGN_SHA256", "PENDING")
    with pytest.raises(SystemExit, match="DESIGN_HASH_UNSET"):
        E.assert_design_frozen()
    marker = tmp_path / "r.json"
    marker.write_text("{}")
    monkeypatch.setattr(E, "RESULT_JSON", marker)
    with pytest.raises(SystemExit, match="REFUSING_RERUN"):
        E.run()
