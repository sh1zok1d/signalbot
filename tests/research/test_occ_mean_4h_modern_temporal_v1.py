"""OCC_MEAN_4H_MODERN_TEMPORAL_REPLICATION_V1: identity with Unit B's surface and sample, the OCC unit's estimands
and the discovery formula; frozen route order. Synthetic data only; no Vision object is downloaded here."""
import numpy as np
import pytest

from scripts.research.directional_state_search_v2 import features as DF
from scripts.research.occ_mean_4h_modern_temporal_v1 import constants as K
from scripts.research.occ_mean_4h_modern_temporal_v1 import evaluate as E
from scripts.research.occ_mean_4h_temporal_v1 import constants as KO
from scripts.research.occ_mean_4h_temporal_v1 import evaluate as EO
from scripts.research.rp4h_binance_2025_2026_temporal_v1 import constants as KB
from scripts.research.rp4h_binance_2025_2026_temporal_v1 import evaluate as EB


def _series(n=3000, seed=4, drop=()):
    rng = np.random.default_rng(seed)
    close = 60000 * np.exp(np.cumsum(rng.normal(0, 0.002, n)))
    high = close * np.exp(np.abs(rng.normal(0, 0.001, n)))
    low = close * np.exp(-np.abs(rng.normal(0, 0.001, n)))
    keep = np.ones(n, dtype=bool)
    keep[list(drop)] = False
    t = KB.SURFACE_START_MS + np.arange(n, dtype=np.int64) * KB.BAR_MS
    return {"open_ms": t[keep], "high": high[keep], "low": low[keep], "close": close[keep]}


def test_shared_contract_is_imported_not_copied():
    assert E.bootstrap is EO.bootstrap and E.estimate is EO.estimate and E.build_sample is EB.build_sample
    assert E.occupancy is DF.occupancy and E.assert_census is EB.assert_census
    assert dict(KO.ESTIMANDS)[K.PRIMARY] == ("rp", "ret4", "rv4", "ret1h", "ret15")
    assert (KO.BOOT_DRAWS, KO.BOOT_SEED, KO.MIN_VALID_DRAWS) == (2000, 20261117, 1900)


def test_sample_is_unit_b_sample_with_the_discovery_occ(monkeypatch):
    s0 = _series(drop=(1500,))
    monkeypatch.setattr(KB, "SURFACE_END_MS", int(s0["open_ms"][-1]) + KB.BAR_MS)
    s = E.occ_sample(s0)
    b = EB.build_sample(s0)
    assert np.array_equal(s["close_ms"], b["close_ms"])
    g = s["_grid"]
    k = 21
    i = int(s["idx"][k])
    hi, lo = g["high"][i - 47:i + 1].max(), g["low"][i - 47:i + 1].min()
    assert s["occ"][k] == pytest.approx(((g["close"][i - 47:i] - lo) / (hi - lo)).mean())
    assert not np.any((s["idx"] - 48 <= 1500) & (s["idx"] >= 1500)) and not np.any(s["idx"] + 12 == 1500)


def _ci(lo, hi, valid=2000):
    return {"lo": lo, "hi": hi, "valid": valid, "draws": 2000}


@pytest.mark.parametrize("p,c,route", [
    (0.01, _ci(0.002, 0.02), K.ROUTE_SUPPORTED),
    (0.01, _ci(-0.002, 0.02), K.ROUTE_COMPATIBLE),
    (-0.002, _ci(-0.01, 0.006), K.ROUTE_NOT),
    (0.0, _ci(-0.01, 0.01), K.ROUTE_NOT),
    (-0.01, _ci(-0.02, -0.001), K.ROUTE_OPPOSES),
    (0.01, _ci(0.002, 0.02, 1899), K.ROUTE_INVALID),
    (None, _ci(None, None, 0), K.ROUTE_INVALID),
])
def test_frozen_route_order(p, c, route):
    assert E.assign_route({K.PRIMARY: p}, {K.PRIMARY: c}) == route
    assert route in K.STATUS


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
