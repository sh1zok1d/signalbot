"""ADAPTIVE_B1_FORECAST_V1: model, schedule, no leakage of a block's outcomes, routes. Synthetic data only."""
import numpy as np
import pytest

from scripts.research.adaptive_b1_forecast_v1 import constants as K
from scripts.research.adaptive_b1_forecast_v1 import evaluate as E
from scripts.research.adaptive_b1_forecast_v1 import model as M
from scripts.research.adaptive_b1_forecast_v1 import walkforward as WF

T0 = 1_514_764_800_000  # 2018-01-01 (Monday)


@pytest.fixture
def small(monkeypatch):
    monkeypatch.setattr(K, "MEMORIES_WEEKS", (2, 4, 8))
    monkeypatch.setattr(K, "INNER_BLOCKS", 2)
    monkeypatch.setattr(K, "BLOCK_DAYS", 7)
    rng = np.random.default_rng(3)
    n = 16 * 7 * 96                                     # 16 weeks of 15-minute anchors
    rows = {"close_ms": T0 + 3_600_000 + np.arange(n, dtype=np.int64) * 900_000,
            "rp": rng.uniform(0, 1, n), "ret4": rng.normal(0, 0.01, n), "rv4": rng.uniform(0.005, 0.02, n),
            "ret1h": rng.normal(0, 0.005, n), "ret15": rng.normal(0, 0.003, n), "era": np.zeros(n, dtype=np.int64),
            "bar": np.arange(n, dtype=np.int64) * 3}
    y = (rng.uniform(size=n) < 1 / (1 + np.exp(-(0.8 * (0.5 - rows["rp"]))))).astype(float)
    return rows, y


def test_logistic_recovers_a_planted_slope():
    rng = np.random.default_rng(0)
    x = rng.normal(size=(20000, 5))
    y = (rng.uniform(size=20000) < 1 / (1 + np.exp(-(0.2 + 1.0 * x[:, 0])))).astype(float)
    m = M.fit(x, y)
    assert m["beta"][1] == pytest.approx(1.0 * x[:, 0].std(), rel=0.08) and abs(m["beta"][2]) < 0.05


def test_schedule_starts_on_monday_after_enough_history(small):
    rows, _ = small
    s = WF.schedule(rows["close_ms"])
    first = int(rows["close_ms"][0])
    need = (8 * 7 + 2 * 7) * K.DAY_MS
    assert s["first_outer_ms"] >= first + need
    assert np.datetime64(s["first_outer_ms"], "ms").astype("datetime64[D]").astype(int) % 7 == 4   # Monday (1970-01-01 = Thu)
    assert np.all(np.diff(s["grid_starts"]) == 7 * K.DAY_MS)


def test_a_block_never_sees_its_own_outcomes(small):
    rows, y = small
    s = WF.schedule(rows["close_ms"])
    base = E.evaluate_predictions(rows, s, y, log_coefs=False)
    k = 1
    S = int(s["outer_starts"][k])
    blk = s["block_ms"]
    m = (rows["close_ms"] > S - K.HOUR_MS) & (rows["close_ms"] < S + blk)        # targets not realized by S
    y2 = y.copy()
    y2[m] = 1 - y2[m]
    alt = E.evaluate_predictions(rows, s, y2, log_coefs=False)
    tgt = (rows["close_ms"] >= S) & (rows["close_ms"] < S + blk)
    for name in ("CLIM", "STATIC", "FIXED_2", "FIXED_4", "FIXED_8", "ADAPTIVE"):
        assert np.allclose(base["preds"][name][tgt], alt["preds"][name][tgt]), name
    assert base["sel"]["log"][k]["selected_memory_weeks"] == alt["sel"]["log"][k]["selected_memory_weeks"]


def test_synthetic_outcomes_share_overlapping_noise(small):
    rows, _ = small
    a = E.synthetic_y(rows, 0.0, 0.0, 1)
    b = E.synthetic_y(rows, 0.0, 0.0, 1)
    assert np.array_equal(a, b) and 0.45 < a.mean() < 0.55
    assert np.mean(a[1:] == a[:-1]) > 0.7                  # anchors 15 minutes apart share 3 of 4 hourly quarters


def _d(point, lo, hi, valid=2000):
    return {"point": point, "lo": lo, "hi": hi, "valid": valid}


@pytest.mark.parametrize("b,l,want", [
    (_d(-1e-5, -2e-5, -1e-6), _d(-1e-5, -2e-5, 0), "SUPPORTED"),
    (_d(-1e-5, -2e-5, -1e-6), _d(1e-6, 0, 2e-6), "UNCERTAIN"),     # log loss contradicts
    (_d(-1e-5, -2e-5, 1e-6), _d(-1e-5, -2e-5, 0), "UNCERTAIN"),
    (_d(1e-6, -1e-5, 1e-5), _d(0, 0, 0), "NONE"),
    (_d(2e-5, 1e-6, 3e-5), _d(0, 0, 0), "WORSE"),
])
def test_routes(b, l, want):
    assert E.route(b, l, K.P2) == K.P2[want]
    assert E.route(_d(-1, -2, -0.5, 1800), l, K.P2) == K.ROUTE_INVALID


def test_run_refuses(monkeypatch, tmp_path):
    monkeypatch.setattr("sys.argv", ["evaluate", "run"])
    with pytest.raises(SystemExit, match="needs --go"):
        E.main()
    monkeypatch.setattr(K, "DESIGN_SHA256", "PENDING")
    with pytest.raises(SystemExit, match="DESIGN_HASH_UNSET"):
        E.assert_frozen()
    m = tmp_path / "r.json"
    m.write_text("{}")
    monkeypatch.setattr(E, "RESULT_JSON", m)
    with pytest.raises(SystemExit, match="REFUSING_RERUN"):
        E.run()
