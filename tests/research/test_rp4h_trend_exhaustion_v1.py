"""RP4H_TREND_EXHAUSTION_INTERACTION_V1 adequacy machinery: exact parity with the Unit-1 estimator, the vectorized
partial, the fast bootstrap, routes, past-only TS and noise scale, DGP. Synthetic data only."""
import numpy as np
import pytest

from scripts.research.rp4h_bitmex_temporal_v1.parent import partial_rank
from scripts.research.rp4h_trend_exhaustion_v1 import constants as K
from scripts.research.rp4h_trend_exhaustion_v1 import dgp
from scripts.research.rp4h_trend_exhaustion_v1 import estimator as E
from scripts.research.rp4h_trend_exhaustion_v1 import surfaces as S
from scripts.research.directional_state_search_v2.features import spa_family


@pytest.fixture
def rows():
    rng = np.random.default_rng(1)
    n = 6000
    r = {"rp": rng.uniform(0, 1, n), "ts": np.abs(rng.normal(0, 1, n)), "ret4": rng.normal(0, 0.01, n),
         "rv4": rng.uniform(0.005, 0.02, n), "ret1h": rng.normal(0, 0.004, n), "ret15": rng.normal(0, 0.002, n)}
    r["week"] = 202001 + np.arange(n) // 300
    r["bar"] = 300 + np.arange(n) * 3
    r["n_bars"] = int(r["bar"].max()) + 20
    r["scale"] = rng.uniform(0.5, 2.0, r["n_bars"])
    return r


def test_vectorized_partial_equals_unit1_interaction(rows):
    rng = np.random.default_rng(2)
    Y = rng.normal(size=(rows["rp"].size, 3))
    p = E.Partial(E.product_term(rows["rp"], rows["ts"]), [rows[c] for c in K.PRIMARY_CONTROLS], rows["week"])
    v = p.rho(p.residual_y(Y))
    for j in range(3):
        assert v[j] == pytest.approx(E.interaction_point(rows, Y[:, j]), abs=1e-12)
        prod = E.product_term(rows["rp"], rows["ts"])
        assert v[j] == pytest.approx(partial_rank(Y[:, j], prod, [rows[c] for c in K.PRIMARY_CONTROLS])["rho"], abs=1e-12)


def test_fast_bootstrap_with_unit_counts_returns_the_point(rows):
    rng = np.random.default_rng(3)
    Y = rng.normal(size=(rows["rp"].size, 2))
    p = E.Partial(E.product_term(rows["rp"], rows["ts"]), [rows[c] for c in K.PRIMARY_CONTROLS], rows["week"])
    ey = p.residual_y(Y)
    ci = E.fast_ci(np.ones((5, p.W)), p.week_sums(ey))
    assert np.allclose(ci["lo"], p.rho(ey)) and np.allclose(ci["hi"], p.rho(ey))


@pytest.mark.parametrize("pt,lo,hi,want", [(-0.01, -0.02, -0.001, K.ROUTE_SUPPORTED), (-0.01, -0.02, 0.003, K.ROUTE_UNCERTAIN),
                                           (0.002, -0.01, 0.01, K.ROUTE_NOT), (0.02, 0.001, 0.03, K.ROUTE_OPPOSES)])
def test_routes(pt, lo, hi, want):
    assert E.route(pt, lo, hi, 2000) == want
    assert E.route(pt, lo, hi, 1899) == K.ROUTE_INVALID


def test_ts_is_unit1_formula_and_undefined_with_a_hole():
    rng = np.random.default_rng(4)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.002, 1000)))
    ts = S.ts_on_grid(close)
    f = spa_family(close)
    i = 700
    r = np.diff(np.log(close[i - 288:i + 1]))
    assert ts[i] == pytest.approx(abs(np.log(close[i] / close[i - 288])) / np.sqrt((r * r).sum()), rel=1e-12)
    assert ts[i] == pytest.approx(abs(f["RET_24H"][i]) / f["RV_24H"][i], rel=1e-12)
    assert np.isnan(ts[287]) and np.isfinite(ts[288])
    holed = close.copy()
    holed[650] = np.nan
    t2 = S.ts_on_grid(holed)
    assert np.isnan(t2[650:939]).all() and np.isfinite(t2[939]) and t2[600] == pytest.approx(ts[600])


def test_noise_scale_is_past_of_every_affected_anchor():
    rng = np.random.default_rng(5)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.002, 600)))
    s = S.vol_scale(close)
    k = 400
    c2 = close.copy()
    c2[k - 12:] *= np.exp(np.cumsum(rng.normal(0, 0.05, 600 - (k - 12))))      # change bars >= k-12
    assert S.vol_scale(c2)[k] == pytest.approx(s[k])


def test_dgp_overlap_scale_and_determinism(rows):
    sig = dgp.signals(rows)
    for g in sig.values():
        assert abs(g.mean()) < 1e-9 and g.std() == pytest.approx(1.0)
    s, sigma = dgp.noise_parts(rows, True)
    a = dgp.latent(rows, sig, s, sigma, 0.0, 0.0, (1, 2, 3, 4))
    assert np.array_equal(a, dgp.latent(rows, sig, s, sigma, 0.0, 0.0, (1, 2, 3, 4)))
    many = np.column_stack([dgp.latent(rows, sig, s, sigma, 0.0, 0.0, (1, 2, 3, r)) for r in range(300)])
    ratio = many.std(axis=1) / sigma
    assert abs(ratio.mean() - 1) < 0.01 and np.quantile(np.abs(ratio - 1), 0.99) < 0.15
    c = np.corrcoef(many[0], many[1])[0, 1]                         # anchors 3 bars apart share 9 of 12 bars
    assert 0.55 < c < 0.95
