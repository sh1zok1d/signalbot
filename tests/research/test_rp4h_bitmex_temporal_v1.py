"""RANGE_POSITION_4H_BITMEX_TEMPORAL_REPLICATION_V1: frozen hashes, canonical missingness, parent parity, routes.

Synthetic data only; the canonical BitMEX file is hashed, never parsed for prices here."""
import json
import math

import numpy as np
import pytest
from scipy import stats

from scripts.research.rp4h_bitmex_temporal_v1 import constants as K
from scripts.research.rp4h_bitmex_temporal_v1 import evaluate as E
from scripts.research.rp4h_bitmex_temporal_v1 import grid as G
from scripts.research.rp4h_bitmex_temporal_v1 import parent as P

T0 = 1_514_764_800_000  # 2018-01-01T00:00:00Z


def _series(n=4000, seed=1, drop=()):
    rng = np.random.default_rng(seed)
    close = 9000 * np.exp(np.cumsum(rng.normal(0, 0.002, n)))
    high = close * np.exp(np.abs(rng.normal(0, 0.001, n)))
    low = close * np.exp(-np.abs(rng.normal(0, 0.001, n)))
    keep = np.ones(n, dtype=bool)
    keep[list(drop)] = False
    t = T0 + np.arange(n, dtype=np.int64) * K.BAR_MS
    return {"open_ms": t[keep], "high": high[keep], "low": low[keep], "close": close[keep],
            "trades": np.ones(int(keep.sum()), dtype=np.int64)}


def test_design_and_series_hashes_are_frozen():
    assert G.sha256(E.DESIGN_PATH) == K.DESIGN_SHA256
    auth = json.loads((G.ROOT / K.AUTHORITY).read_text())
    assert auth["canonical_jsonl_gz_sha256"] == K.SERIES_SHA256
    assert G.sha256(G.ROOT / K.SERIES) == K.SERIES_SHA256
    assert auth["gaps"]["missing_bucket_count"] == K.GAP_COUNT
    assert auth["coverage"]["zero_trade_buckets_retained_as_official_source_bins"] is True


def test_zero_trade_rows_are_bars_and_absent_timestamps_are_holes():
    lines = [json.dumps({"open_time_ms": T0 + k * K.BAR_MS, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0,
                         "trades": 0 if k == 1 else 3}) for k in (0, 1, 3)]
    s = G.parse_rows(lines)
    assert s["open_ms"].tolist() == [T0, T0 + K.BAR_MS, T0 + 3 * K.BAR_MS]       # the zero-trade row is kept
    g = G.place(s)
    assert g["holes"] == 1 and np.isnan(g["close"][2]) and g["close"][1] == 1.0
    assert G.missing_opens(s["open_ms"]).tolist() == [T0 + 2 * K.BAR_MS]


def test_gap_census_refuses_any_other_gap(monkeypatch):
    s = _series(n=600, drop=(300,))
    monkeypatch.setattr(K, "FIRST_OPEN_MS", int(s["open_ms"][0]))
    monkeypatch.setattr(K, "LAST_OPEN_MS", int(s["open_ms"][-1]))
    monkeypatch.setattr(K, "SURFACE_END_MS", int(s["open_ms"][-1]) + K.BAR_MS)
    monkeypatch.setattr(K, "GAP_FIRST_OPEN_MS", T0 + 301 * K.BAR_MS)       # wrong place
    monkeypatch.setattr(K, "GAP_LAST_OPEN_MS", T0 + 301 * K.BAR_MS)
    monkeypatch.setattr(K, "GAP_COUNT", 1)
    with pytest.raises(SystemExit, match="GAP_CENSUS_MISMATCH"):
        G.preflight_census(s)


def test_anchor_phase_before_2020_uses_floor_modulo():
    opens = T0 + np.arange(30, dtype=np.int64) * K.BAR_MS
    m = G.anchor_mask(opens)
    t_close = opens[m] + K.BAR_MS
    assert m.sum() == 10
    assert np.all((t_close // 60_000) % 15 == 0)                              # T at :00/:15/:30/:45


def _sample(series, end_ms):
    old = K.SURFACE_END_MS
    try:
        K.SURFACE_END_MS = end_ms
        return E.build_sample(series)
    finally:
        K.SURFACE_END_MS = old


def test_sample_formulas_match_hand_computation_and_are_past_only():
    s = _series()
    end = int(s["open_ms"][-1]) + K.BAR_MS
    a = _sample(s, end)
    k = 7
    i = int((a["close_ms"][k] - K.BAR_MS - T0) // K.BAR_MS)
    hi, lo, cl = s["high"], s["low"], s["close"]
    w_hi, w_lo = hi[i - 47:i + 1].max(), lo[i - 47:i + 1].min()
    assert a["rp"][k] == pytest.approx((cl[i] - w_lo) / (w_hi - w_lo))
    assert a["ret4"][k] == pytest.approx(math.log(cl[i] / cl[i - 48]))
    assert a["rv4"][k] == pytest.approx(math.sqrt(sum(math.log(cl[x] / cl[x - 1]) ** 2 for x in range(i - 47, i + 1))))
    assert a["r1"][k] == pytest.approx(math.log(cl[i + 12] / cl[i]))
    assert a["ret1h"][k] == pytest.approx(math.log(cl[i] / cl[i - 12]))
    assert a["ret15"][k] == pytest.approx(math.log(cl[i] / cl[i - 3]))
    s2 = {c: v.copy() for c, v in s.items()}
    for c in ("high", "low", "close"):
        s2[c][i + 1:] *= 1.07                                                  # every bar after the anchor
    b = _sample(s2, end)
    m = np.flatnonzero(b["close_ms"] == a["close_ms"][k])[0]
    for c in ("rp", "ret4", "rv4", "width", "ret1h", "ret15"):
        assert b[c][m] == pytest.approx(a[c][k]), c
    assert b["r1"][m] == pytest.approx(a["r1"][k] + math.log(1.07))


def test_a_hole_drops_anchors_whose_window_path_or_target_touches_it():
    hole = 2000
    s = _series(drop=(hole,))
    a = _sample(s, int(T0 + 4000 * K.BAR_MS))
    i = (a["close_ms"] - K.BAR_MS - T0) // K.BAR_MS
    assert not np.any((i - 48 <= hole) & (i >= hole))
    assert not np.any(i + 12 == hole)


def test_vendored_parent_matches_reference_and_scipy():
    rng = np.random.default_rng(4)
    x = np.round(rng.normal(size=400), 1)
    y = 0.2 * x + rng.normal(size=400)
    z = 0.4 * x + rng.normal(size=400)
    assert np.allclose(P.average_ranks_fast(x), P.ref_average_ranks(x))
    assert np.allclose(P.average_ranks_fast(x), stats.rankdata(x))
    assert P.spearman(x, y) == pytest.approx(stats.spearmanr(x, y)[0])
    assert P.partial_rank(y, x, [z])["rho"] == pytest.approx(P.ref_partial_spearman(x, y, z)["rho"], abs=1e-12)


def _ci(lo, hi, valid=2000):
    return {"lo": lo, "hi": hi, "valid": valid, "draws": 2000}


@pytest.mark.parametrize("raw,raw_ci,prim,prim_ci,route,flags", [
    (-0.05, _ci(-0.06, -0.04), -0.03, _ci(-0.04, -0.02), K.ROUTE_SUPPORTED, []),
    (-0.01, _ci(-0.03, 0.01), -0.03, _ci(-0.04, -0.02), K.ROUTE_SUPPORTED, []),
    (-0.05, _ci(-0.06, -0.04), -0.01, _ci(-0.02, 0.01), K.ROUTE_RAW_ONLY, []),
    (-0.05, _ci(-0.06, -0.04), 0.01, _ci(-0.01, 0.02), K.ROUTE_RAW_ONLY, []),
    (-0.01, _ci(-0.03, 0.01), -0.01, _ci(-0.03, 0.01), K.ROUTE_COMPATIBLE, []),
    (-0.01, _ci(-0.03, 0.01), 0.01, _ci(-0.01, 0.03), K.ROUTE_NOT, []),
    (0.01, _ci(-0.01, 0.03), -0.02, _ci(-0.03, -0.01), K.ROUTE_NOT, []),
    (-0.05, _ci(-0.06, -0.04), 0.02, _ci(0.01, 0.03), K.ROUTE_NOT, [K.FLAG_OPPOSES]),
    (-0.05, _ci(-0.06, -0.04, 1800), -0.03, _ci(-0.04, -0.02), K.ROUTE_UNAVAILABLE, []),
])
def test_frozen_route_order(raw, raw_ci, prim, prim_ci, route, flags):
    assert E.assign_route(raw, raw_ci, prim, prim_ci) == (route, flags)


def test_run_refuses_without_go_and_when_scored(monkeypatch, tmp_path):
    monkeypatch.setattr("sys.argv", ["evaluate", "run"])
    with pytest.raises(SystemExit, match="needs --go"):
        E.main()
    marker = tmp_path / "r.json"
    marker.write_text("{}")
    monkeypatch.setattr(E, "RESULT_JSON", marker)
    with pytest.raises(SystemExit, match="REFUSING_RERUN"):
        E.run()
