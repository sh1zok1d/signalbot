"""SEED-0001 exploratory outcome evaluator. Offline, synthetic paths only."""
import json
from pathlib import Path

import numpy as np
import pytest

from scripts.research import seed0001_exploratory_outcomes as X
from scripts.research import seed0001_regular_divergence_lib as L

REPO = Path(__file__).resolve().parents[2]
T0 = 1_700_000_000_000 // 3_600_000 * 3_600_000


def _minutes(n, base=100.0):
    t = T0 + np.arange(n, dtype=np.int64) * X.MINUTE_MS
    return {"t": t, "high": np.full(n, base + 0.5), "low": np.full(n, base - 0.5), "close": np.full(n, base)}


def _ep(entry=100.0, stop=98.0):
    return {"EPISODE_ID": "X", "DECISION_TIME_MS": T0, "ENTRY_REF_PRICE": entry, "STOP_PRICE": stop}


def test_bracket_target_stop_same_minute_and_timeout():
    hi, lo = np.full(10, 100.5), np.full(10, 99.5)
    assert X.bracket(hi, lo, 100.0, 98.0, 1) == "NEUTRAL"
    h = hi.copy(); h[3] = 102.0
    assert X.bracket(h, lo, 100.0, 98.0, 1) == "WIN"          # high >= E + R
    lw = lo.copy(); lw[2] = 97.9
    assert X.bracket(h, lw, 100.0, 98.0, 1) == "LOSS"         # stop first
    lw = lo.copy(); lw[3] = 97.0
    assert X.bracket(h, lw, 100.0, 98.0, 1) == "LOSS"         # same minute counts as the stop
    lw = lo.copy(); lw[1] = 98.0
    assert X.bracket(h, lw, 100.0, 98.0, 1) == "WIN"          # touching S exactly is not a stop
    assert X.bracket(h, lo, 100.0, 98.0, 2) == "NEUTRAL"      # 102 < E + 2R = 104


def test_episode_outcomes_window_and_descriptive_paths():
    m = _minutes(96 * 60 + 10)
    m["high"][100] = 102.5                                    # +1R at minute 100
    m["low"][3000] = 97.0                                     # stop at minute 3000, after the 48h window
    m["close"][48 * 60 - 1] = 101.0
    m["close"][96 * 60 - 1] = 99.0
    out = X.episode_outcomes(m, _ep())
    assert out["Y1_48H_WLN"] == "WIN" and out["Y1_48H"] == 1
    assert out["Y2_48H_WLN"] == "NEUTRAL" and out["Y2_96H_WLN"] == "LOSS"
    assert out["FWD_RET_48H"] == pytest.approx(0.01) and out["FWD_R_48H"] == pytest.approx(0.5)
    assert out["FWD_R_96H"] == pytest.approx(-0.5)
    assert out["MFE_R_48H"] == pytest.approx(1.25) and out["MAE_R_48H"] == pytest.approx(0.25)
    assert out["MAE_R_96H"] == pytest.approx(1.5)


def test_missing_minute_makes_the_window_unavailable():
    m = _minutes(96 * 60)
    keep = np.ones(m["t"].size, dtype=bool)
    keep[500] = False
    m = {k: v[keep] for k, v in m.items()}
    out = X.episode_outcomes(m, _ep())
    assert out["Y1_48H"] is None and out["Y1_48H_WLN"] == "UNAVAILABLE" and out["FWD_R_96H"] is None


def test_outcome_window_never_reaches_the_protected_surface():
    t = np.array([L.PROTECTED_START_MS - 3_600_000], dtype=np.int64)
    with pytest.raises(X.OutcomeWindowError, match="protected"):
        X.window_slice(t, L.PROTECTED_START_MS - 47 * 3_600_000, 48)


def test_ols_cr1_matches_statsmodels_cluster_covariance():
    sm = pytest.importorskip("statsmodels.api")
    rng = np.random.default_rng(1)
    n = 300
    Xd = np.column_stack([np.ones(n), rng.normal(size=(n, 3))])
    y = Xd @ np.array([0.2, 0.5, -0.3, 0.1]) + rng.normal(size=n)
    g = rng.integers(0, 40, size=n)
    mine = X.ols_cr1(Xd, y, g)
    ref = sm.OLS(y, Xd).fit(cov_type="cluster", cov_kwds={"groups": g})
    np.testing.assert_allclose(mine["beta"], ref.params)
    np.testing.assert_allclose(mine["V"], ref.cov_params(), rtol=1e-10)


def test_holm_rule_needs_both():
    assert X.holm(0.01, 0.04)["REJECT_BOTH"] is True
    assert X.holm(0.03, 0.04)["REJECT_BOTH"] is False
    assert X.holm(0.01, 0.06)["REJECT_BOTH"] is False
    h = X.holm(0.02, 0.01)
    assert h["P2_HOLM"] == pytest.approx(0.02) and h["P1_HOLM"] == pytest.approx(0.02)


def _synthetic_eps(n=240, seed=3):
    rng = np.random.default_rng(seed)
    arms = rng.choice(list("ABCD"), size=n, p=[0.15, 0.3, 0.15, 0.4])
    eps = []
    for k in range(n):
        eps.append({"ARM": str(arms[k]), "WEEK_BLOCK": int(k // 6), "EPOCH": X.EPOCHS[min(3, k * 4 // n)],
                    "RV24": float(rng.uniform(0.003, 0.01)), "TOD_HOUR_UTC": int(rng.integers(0, 24)),
                    "DECLINE_ATR": float(rng.uniform(3, 6)), "NETFLOW24": float(rng.normal(0, 0.05)),
                    "RISK_ATR": float(rng.uniform(0.3, 2)), "RISK_FRACTION": 0.01})
    y = (rng.random(n) < np.where(arms == "A", 0.7, 0.45)).astype(float)
    return eps, y


def test_bootstrap_and_epoch_analysis_are_deterministic():
    eps, y = _synthetic_eps()
    weeks = [e["WEEK_BLOCK"] for e in eps]
    a = X.cluster_bootstrap(eps, y, weeks, resamples=200, seed=7)
    b = X.cluster_bootstrap(eps, y, weeks, resamples=200, seed=7)
    assert a == b and a["USED"] + a["SKIPPED"] == 200
    lo, hi = a["P1_CI95_PERCENTILE"]
    assert lo < hi
    e1 = X.epoch_analysis(eps, y, draws=50, seed=5)
    e2 = X.epoch_analysis(eps, y, draws=50, seed=5)
    assert e1 == e2
    assert 0 < e1["A_VS_B"]["P_HETEROGENEITY"] <= 1


def test_adjusted_model_contrasts_and_rates():
    eps, y = _synthetic_eps()
    res = X.adjusted_model(eps, y, [e["WEEK_BLOCK"] for e in eps])
    assert set(res["ADJUSTED_RATES"]) == set("ABCD")
    p1 = res["P1_A_VS_B"]
    assert p1["CI95_CR1_T"][0] < p1["ESTIMATE"] < p1["CI95_CR1_T"][1]
    rates = res["ADJUSTED_RATES"]
    assert rates["A"] - rates["B"] == pytest.approx(p1["ESTIMATE"])


def test_permit_freezes_the_plan_before_opening():
    permit = json.loads((REPO / X.PERMIT_REL).read_text())
    assert permit["CONFIRMATORY"] is False and permit["FEASIBILITY_VERDICT_CHANGED"] is False
    assert permit["CLASSIFICATION_FIXED_BEFORE_OUTCOMES"] == "INCONCLUSIVE_DISCOVERY"
    assert permit["PROTECTED_2025_2026_AUTHORIZED"] is False and permit["RERUN_AUTHORIZED"] is False
    plan = permit["ANALYSIS_PLAN"]
    assert "4999 resamples" in plan["INTERVALS"]["WEEK_CLUSTER_BOOTSTRAP"]
    assert "seed 20261004" in plan["INTERVALS"]["WEEK_CLUSTER_BOOTSTRAP"]
    assert X.BOOTSTRAP_RESAMPLES == 4999 and X.BOOTSTRAP_SEED == 20261004
    assert X.EPOCH_PERMUTATIONS == 2000 and X.EPOCH_SEED == 20261003
