"""Range model V2 candidate (beta/rangecast_v2.py, not wired) and its evaluation guards.

Synthetic bars only (tests/beta/v2_fakes.py); nothing here reads market data or the network.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "beta"))
from v2_fakes import synthetic_rows  # noqa: E402

from beta import hist_series as hs  # noqa: E402
from beta import rangecast as rc  # noqa: E402
from beta import rangecast_v2 as v2  # noqa: E402

UTC = timezone.utc


@pytest.fixture(scope="module")
def bars():
    rows, _ = synthetic_rows(datetime(2025, 1, 1, tzinfo=UTC), 140, seed=5)
    return hs.bars_from_rows(rows)


@pytest.fixture(scope="module")
def models(bars):
    return {lvl: v2.fit_range_model_v2(bars, events={}, level=lvl) for lvl in ("L1", "L2", "L3")}


def _anchor(bars):
    i = bars.last_complete_index() - 400
    return i - (i % 12) + 11          # a bar closing on the full hour


def test_features_use_only_bars_up_to_the_anchor(bars):
    F = v2.bar_features(bars)
    k = bars.n - 2000
    other = hs.Bars(t0=bars.t0, **{c: getattr(bars, c).copy() for c in hs.COLUMNS}, oi=bars.oi.copy())
    rng = np.random.default_rng(1)
    for c in ("open", "high", "low", "close", "volume"):
        getattr(other, c)[k + 1:] *= rng.uniform(0.5, 1.5, bars.n - k - 1)
    G = v2.bar_features(other)
    for n in F:
        np.testing.assert_array_equal(np.nan_to_num(F[n][:k + 1], nan=-9), np.nan_to_num(G[n][:k + 1], nan=-9), err_msg=n)


def test_touch_chances_fall_with_distance_and_stay_in_bounds(bars, models):
    i = _anchor(bars)
    d = [0.05, 0.1, 0.25, 0.5, 1, 2, 4, 8]
    for lvl, m in models.items():
        for h in ("1h", "4h", "24h"):
            st = v2.state_at(m, bars, i, h, events={})
            assert st is not None
            for side in (1, -1):
                p = [v2.touch_probability_v2(m, h, st, side, x) for x in d]
                assert all(a >= b for a, b in zip(p, p[1:])), (lvl, h, side, p)
                assert all(v2.PROB_MIN <= x <= v2.PROB_MAX for x in p)
            assert v2.touch_probability_v2(m, h, st, 1, 0.0) == 1.0


def test_neither_is_coherent_with_the_two_single_chances(bars, models):
    i = _anchor(bars)
    for lvl, m in models.items():
        mh = m["horizons"]["4h"]
        st = {k: np.array([v]) for k, v in v2.state_at(m, bars, i, "4h", events={}).items()}
        for du in (0.3, 1.0, 2.5):
            for dd in (0.3, 1.0, 2.5):
                n = float(v2.neither_prob(mh, st, np.array([du]), np.array([dd]))[0])
                pu = float(v2.touch_prob(mh, st, "up", np.array([du]))[0])
                pd_ = float(v2.touch_prob(mh, st, "down", np.array([dd]))[0])
                assert max(1 - pu - pd_, v2.PROB_MIN) - 1e-12 <= n <= 1 - max(pu, pd_) + 1e-12, (lvl, du, dd)


def test_single_request_path_equals_the_vectorized_path(bars, models):
    """state_at (a 30-day slice, the live form) gives the numbers the evaluation harness scores."""
    F = v2.bar_features(bars)
    i = _anchor(bars)
    for lvl, m in models.items():
        for h in ("1h", "4h", "24h"):
            mh = m["horizons"][h]
            cal = v2.calendar_columns(bars, np.array([i]), h, {})
            vec = v2.state(mh, {k: v[[i]] for k, v in F.items()}, cal)
            one = v2.state_at(m, bars, i, h, events={})
            for k in vec:
                assert one[k] == pytest.approx(float(vec[k][0]), rel=1e-9, abs=1e-12), (lvl, h, k)


def test_the_l1_view_reads_with_the_production_functions(bars, models):
    m = models["L1"]
    view = v2.as_v1_model(m)
    i = _anchor(bars)
    for h in ("1h", "4h", "24h"):
        S = v2.state_at(m, bars, i, h, events={})["S"]
        for d in (0.1, 0.3, 0.7, 1.5, 3.0):
            p2 = v2.touch_probability_v2(m, h, {"S": S}, 1, d)
            p1 = rc.touch_probability(view, h, S, d)
            if p2 <= 0.99:
                assert p1 == pytest.approx(p2, abs=1e-12), (h, d)
        pu, pd_ = rc.touch_probability(view, h, S, 1.0), rc.touch_probability(view, h, S, 0.8)
        n1 = rc.neither_probability(view, h, S, 1.0, 0.8, p_up=pu, p_down=pd_)
        n2 = float(v2.neither_prob(m["horizons"][h], {"S": np.array([S])}, np.array([1.0]), np.array([0.8]))[0])
        if max(pu, pd_) <= 0.99:
            assert n1 == pytest.approx(n2, abs=1e-12)
    stops = rc.stop_stats(view, v2.forecast_v2(m, bars, price=float(bars.close[-1]), events={}), 0.5)
    assert set(stops) == {"1h", "4h", "24h"}


def test_forecast_v2_has_the_keys_every_surface_reads(bars, models):
    price = float(bars.close[bars.last_complete_index()])
    f2 = v2.forecast_v2(models["L1"], bars, price=price, events={})
    f1 = rc.forecast(rc.fit_range_model(bars, events={}, holdout_days=30), bars, price=price, events={})
    assert set(f2) == set(f1)
    for h, x in f2["horizons"].items():
        assert set(x) == set(f1["horizons"][h])
        assert x["lower"] < price < x["upper"] and x["typical_move_pct"] > 0


def test_features_are_clipped_to_their_training_range(models):
    mh = models["L1"]["horizons"]["4h"]
    n0 = mh["features"][0]
    lo, hi = mh["clip"][n0]
    base = {n: np.array([np.mean(mh["clip"][n])]) for n in mh["features"]}
    cal = {"dow": np.array([2]), "hour": np.array([10]), "weekend": np.array([0.0]), "event_cpi": np.array([0.0]),
           "event_fomc": np.array([0.0])}
    at_hi = v2.state(mh, {**base, n0: np.array([hi])}, cal)["S"][0]
    beyond = v2.state(mh, {**base, n0: np.array([hi + 50.0])}, cal)["S"][0]
    assert beyond == pytest.approx(at_hi) and lo < hi


def test_weighted_quantiles_reduce_to_plain_quantiles():
    x = np.random.default_rng(3).normal(size=5001)
    q = [0.01, 0.25, 0.5, 0.75, 0.99]
    # equal weights: the Hazen plotting position (k − 0.5) / n, numpy's method='hazen'
    np.testing.assert_allclose(v2.weighted_quantiles(x, q, np.ones(x.size)), np.quantile(x, q, method="hazen"),
                               atol=1e-12)
    np.testing.assert_array_equal(v2.weighted_quantiles(x, q, None), np.quantile(x, q))


def test_recency_weights_change_the_fit(bars):
    a = v2.fit_range_model_v2(bars, events={}, level="L1")
    b = v2.fit_range_model_v2(bars, events={}, level="L1", half_life_days=20.0)
    assert a["horizons"]["4h"]["beta"] != b["horizons"]["4h"]["beta"]
    json.dumps(b)                                     # JSON-ready, as the statistics row needs


def test_the_candidate_is_not_wired_into_the_product():
    pat = re.compile(r"rangecast_v2")
    offenders = [str(p.relative_to(ROOT)) for d in ("beta", "runtime", "storage") for p in (ROOT / d).rglob("*.py")
                 if p.name != "rangecast_v2.py" and pat.search(p.read_text(encoding="utf-8"))]
    assert offenders == []
