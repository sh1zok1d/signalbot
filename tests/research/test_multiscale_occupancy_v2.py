"""MULTISCALE_ADAPTIVE_OCCUPANCY_V2 synthetic engine: surrogate vs exact IRLS, bootstrap equivalence, no leakage,
venue isolation, DGP, the frozen selection rule and adequacy criterion. Synthetic data only."""
import numpy as np
import pytest

from scripts.research.adaptive_b1_forecast_v1 import metrics as MT
from scripts.research.adaptive_b1_forecast_v1 import model as M1
from scripts.research.adaptive_occupancy_v1 import constants as K1
from scripts.research.multiscale_occupancy_v2 import constants as K
from scripts.research.multiscale_occupancy_v2 import data as D
from scripts.research.multiscale_occupancy_v2 import dgp
from scripts.research.multiscale_occupancy_v2 import engine as EN
from scripts.research.multiscale_occupancy_v2 import exact as EX
from scripts.research.multiscale_occupancy_v2 import study as ST

T0 = 1_514_764_800_000  # 2018-01-01 (Monday)
Q = 900_000


@pytest.fixture
def small(monkeypatch):
    monkeypatch.setattr(K1, "MEMORIES_WEEKS", (2, 4, 8))
    monkeypatch.setattr(K1, "INNER_BLOCKS", 2)
    monkeypatch.setattr(K1, "BLOCK_DAYS", 7)
    rng = np.random.default_rng(5)
    per = 16 * 7 * 96
    starts = (T0 + K1.HOUR_MS, T0 + 20 * K1.WEEK_MS + K1.HOUR_MS)
    n = 2 * per
    rows = {"close_ms": np.concatenate([s + np.arange(per, dtype=np.int64) * Q for s in starts]),
            "venue": np.repeat(np.array([0, 1], dtype=np.int64), per), "rp": rng.uniform(0, 1, n),
            "ret4": rng.normal(0, 0.01, n), "rv4": rng.uniform(0.010, 0.012, n), "ret1h": rng.normal(0, 0.005, n),
            "ret15": rng.normal(0, 0.003, n), "bar": np.arange(n, dtype=np.int64) * 3}
    # light tails, as in the real features (the +-5 clip binds on ~0.06 % of real rows), so that the comparison with
    # exact IRLS measures the one-step approximation rather than training-side clipping
    rows["era"] = np.where(rows["venue"] == 0, 0, np.where(np.arange(n) < per + per // 2, 1, 2)).astype(np.int64)
    for i, h in enumerate(K1.LOOKBACK_HOURS):
        rows[f"OCC_{h}H"] = np.clip(0.5 + rng.normal(0, 0.15, n) + 0.05 * i * (rows["rp"] - 0.5), 0, 1)
    g = EN.build_geometry(rows, ewma_weeks=4)
    eta = 0.03 * (rows["OCC_2H"] - 0.5) / 0.15            # study-scale signal (|eta| << 1)
    Y = (rng.uniform(size=(n, 3)) < 1 / (1 + np.exp(-eta))[:, None]).astype(float)
    return rows, g, Y


def _block(g, v, k):
    S = int(g.sched[v]["outer_starts"][k])
    return S, np.arange(g.idx_lt(v, S), g.idx_lt(v, S + EN.WF1.block_ms()))


def test_exact_fit_is_the_frozen_b1_model():
    rng = np.random.default_rng(0)
    x = rng.normal(size=(5000, 5))
    y = (rng.uniform(size=5000) < 1 / (1 + np.exp(-(0.1 + 0.3 * x[:, 0])))).astype(float)
    a, b = EX.fit(x, y, [1.0] * 5), M1.fit(x, y)
    assert np.allclose(a["beta"], b["beta"], atol=1e-10) and np.allclose(a["mu"], b["mu"])


@pytest.mark.parametrize("spec_args", [("JOINT", "TRAIL", 52, 1e3), ("JOINT", "EWMA", 26, 1.0),
                                       ("OFFSET", "TRAIL", 104, 1e4), ("OFFSET", "EWMA", 26, 1e3),
                                       ("JOINT", "EXPANDING", 0, 1e3)])
def test_surrogate_matches_exact_irls(small, spec_args):
    rows, g, Y = small
    spec = EN.v2_spec(*spec_args)
    if spec.memory == "EWMA":
        spec = EN.Spec(spec.name, spec.structure, spec.cols, spec.lam, "EWMA", g.ewma_weeks)
    oc = EN.outcome_cums(g, Y)
    for v in (0, 1):
        S, ix = _block(g, v, 2)
        fb = EN.fit_std(g, oc, v, S, EN.b1_spec())
        f = EN.fit_std(g, oc, v, S, spec) if spec.structure == "STD" else EN.fit_offset(g, oc, v, S, spec, fb)
        ps = EN._sig(EN.eta_std(g, f, ix) if spec.structure == "STD" else EN.eta_offset(g, f, ix))
        for r in range(Y.shape[1]):
            pe = EX.predict_block(g, Y[:, r], v, S, spec, ix)
            d = np.abs(ps[:, r] - pe)
            assert d.mean() < 0.01 * pe.std() and d.max() < 0.05 * pe.std()


def test_bootstrap_equals_frozen_boot_diffs(small):
    rows, g, Y = small
    acc = EN.evaluate_batch(g, Y[:, :1], [EN.v2_spec("OFFSET", "TRAIL", 52, 1e3)], with_v1=False)["acc"]
    C = EN.boot_counts(g.week_ids.size, 2000, K.BOOT_SEED)
    cnt = EN.week_counts(g)
    bp = EN.boot_pair(C, cnt, acc.brier["STATIC_OCC4"], acc.brier["B1"])
    # rebuild row-level losses through the frozen function on the same week grid
    om = g.outer
    wk = MT.weeks_of(g.t[om])
    la = np.repeat(acc.brier["STATIC_OCC4"][:, 0] / cnt, cnt.astype(int))
    lb = np.repeat(acc.brier["B1"][:, 0] / cnt, cnt.astype(int))
    ref = MT.boot_diffs({"a": la, "b": lb}, [("a", "b")], np.sort(wk), seed=K.BOOT_SEED)["a-b"]
    assert bp["point"][0] == pytest.approx(ref["point"], abs=1e-15)
    assert bp["lo"][0] == pytest.approx(ref["lo"], abs=1e-12) and bp["hi"][0] == pytest.approx(ref["hi"], abs=1e-12)


def test_no_outcome_after_the_block_start_reaches_its_fits(small):
    rows, g, Y = small
    specs = [EN.b1_spec(), EN.static_spec(), EN.v2_spec("JOINT", "TRAIL", 52, 1e3),
             EN.Spec("V2|JOINT|EWMA_4|1000", "STD", EN.v2_spec("JOINT", "TRAIL", 52, 1e3).cols,
                     EN.v2_spec("JOINT", "TRAIL", 52, 1e3).lam, "EWMA", g.ewma_weeks)] + EN.v1_specs()
    for v in (0, 1):
        S, ix = _block(g, v, 3)
        Y2 = Y.copy()
        m = (rows["venue"] == v) & (g.t > S - K1.HOUR_MS)
        Y2[m] = 1 - Y2[m]
        o1, o2 = EN.outcome_cums(g, Y), EN.outcome_cums(g, Y2)
        for sp in specs:
            if sp.v1_full_window and S - sp.weeks * K1.WEEK_MS < g.sched[v]["first_ms"]:
                continue
            a, b = EN.fit_std(g, o1, v, S, sp), EN.fit_std(g, o2, v, S, sp)
            assert np.allclose(a["beta"], b["beta"]) and np.allclose(a["b0"], b["b0"]), sp.name
        fb1, fb2 = EN.fit_std(g, o1, v, S, EN.b1_spec()), EN.fit_std(g, o2, v, S, EN.b1_spec())
        sp = EN.v2_spec("OFFSET", "TRAIL", 104, 1e3)
        assert np.allclose(EN.fit_offset(g, o1, v, S, sp, fb1)["gamma"], EN.fit_offset(g, o2, v, S, sp, fb2)["gamma"])


def test_venues_never_train_on_each_other(small):
    rows, g, Y = small
    Y2 = Y.copy()
    Y2[rows["venue"] == 0] = 1 - Y2[rows["venue"] == 0]
    specs = [EN.v2_spec("OFFSET", "TRAIL", 52, 1e3), EN.v2_spec("JOINT", "TRAIL", 104, 1e4)]
    a = EN.evaluate_batch(g, Y, specs, with_v1=True)["acc"]
    b = EN.evaluate_batch(g, Y2, specs, with_v1=True)["acc"]
    v1w = np.unique(g.row_week[(rows["venue"] == 1) & g.outer])
    for m in ("B1", "STATIC_OCC4", "V1") + tuple(s.name for s in specs):
        assert np.allclose(a.brier[m][v1w], b.brier[m][v1w]), m


def test_dgp_is_deterministic_and_switches_scales(small):
    rows, g, _ = small
    sig = dgp.residual_signals(rows, g.X)
    for h in K1.LOOKBACK_HOURS:
        for era in range(3):
            m = rows["era"] == era
            assert abs(sig[h][m].mean()) < 1e-9 and sig[h][m].std() == pytest.approx(1.0)
            d = np.column_stack([np.ones(int(m.sum())), g.X[m][:, EN.B1_IDX]])
            assert np.max(np.abs(d.T @ sig[h][m])) < 1e-6 * m.sum()
    s = dgp.signal(rows, sig, "SWITCHING_OCC_2H_8H", 0.011, K.KAPPA)
    odd = dgp.periods(rows, 52) % 2 == 1
    assert np.allclose(s[~odd], 0.011 / K.KAPPA[2] * sig[2][~odd])
    assert np.all(dgp.signal(rows, sig, "NULL", 0.011, K.KAPPA) == 0)
    a = dgp.outcomes(rows, sig, "NULL_DRIFT", 0.0, K.KAPPA, [(1, 1, 99, 0), (1, 1, 99, 1)], 0.025)
    b = dgp.outcomes(rows, sig, "NULL_DRIFT", 0.0, K.KAPPA, [(1, 1, 99, 0)], 0.025)
    assert np.array_equal(a[:, 0], b[:, 0]) and not np.array_equal(a[:, 0], a[:, 1])


def test_feature_rows_carry_no_outcome():
    rows = {k: np.zeros(3) for k in D.FEATURES + D.OUTCOME_KEYS}
    out = D.strip_outcomes(rows)
    assert not set(D.OUTCOME_KEYS) & set(out)


def _fake_stage(values: dict, models: list) -> dict:
    res = {}
    for sc, lv in ST.levels():
        res[f"{sc}@{lv:g}"] = {m: dict(values.get((m, sc, lv), {"p_support": 0.0, "p_beat": 0.3,
                                                                  "d_brier_mean": 1e-5})) for m in models}
    return {"results": res}


def test_selection_rule_eligibility_score_and_ties():
    names = [s.name for s in ST.candidates(include_reference=False)]
    a, b, c = "V2|OFFSET|TRAIL_52|1000", "V2|OFFSET|EWMA_26|10000", "V2|JOINT|TRAIL_104|10000"
    v = {(a, "SWITCHING_OCC_2H_8H", 1.0): {"p_support": 0.5, "p_beat": 0.9, "d_brier_mean": -1},
         (a, "SWITCHING_OCC_2H_8H", 2.0): {"p_support": 0.9, "p_beat": 0.9, "d_brier_mean": -1},
         (b, "SWITCHING_OCC_2H_8H", 1.0): {"p_support": 0.48, "p_beat": 0.9, "d_brier_mean": -1},
         (b, "SWITCHING_OCC_2H_8H", 2.0): {"p_support": 0.9, "p_beat": 0.9, "d_brier_mean": -1},
         (b, "CONSTANT_OCC_4H", 2.0): {"p_support": 0.9, "p_beat": 0.9, "d_brier_mean": -1},
         (c, "SWITCHING_OCC_2H_8H", 2.0): {"p_support": 1.0, "p_beat": 1.0, "d_brier_mean": -1},
         (c, "NULL", 0.0): {"p_support": 0.06, "p_beat": 0.3, "d_brier_mean": 0}}
    sel = ST.select(_fake_stage(v, names + [n.replace("TRAIL_52", "EXPANDING") for n in names]))
    assert sel["selected"] == b                  # c is ineligible (NULL false support); b wins a's tie band on secondary
    assert set(sel["band"]) == {a, b}


def test_adequacy_criterion():
    nm = "V2|OFFSET|TRAIL_52|1000"
    good = {}
    for sc, lv in ST.levels():
        good[(nm, sc, lv)] = {"p_support": 0.9 if sc not in ST.NULLS else 0.02, "p_beat": 0.95 if sc not in ST.NULLS else 0.3,
                              "d_brier_mean": -1e-5, "p_support_cw": 0.9 if sc not in ST.NULLS else 0.02}
    st = _fake_stage(good, [nm, "V1"])
    assert ST.adequacy(st, nm)["verdict"] == K.VERDICT_PASS
    st["results"]["CONSTANT_OCC_4H@2"][nm]["p_support"] = 0.79
    a = ST.adequacy(st, nm)
    assert a["verdict"] == K.VERDICT_FAIL and not a["C4_power_2x"]["pass"] and a["C1_null_false_support"]["pass"]
