"""ADAPTIVE_OCCUPANCY_TIMESCALE_V1: OCC_L definition, schedule, selection order, no leakage of a block's outcomes,
venue isolation, routes and refusals. Synthetic data only."""
import numpy as np
import pytest

from scripts.research.adaptive_occupancy_v1 import constants as K
from scripts.research.adaptive_occupancy_v1 import evaluate as E
from scripts.research.adaptive_occupancy_v1 import walkforward as WF
from scripts.research.adaptive_occupancy_v1.features import occ_l
from scripts.research.adaptive_occupancy_v1.surfaces import rp_identity
from scripts.research.directional_state_search_v2.features import occupancy

T0 = 1_514_764_800_000  # 2018-01-01 (Monday)
Q = 900_000


def _bars(n, seed=0):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.002, n)))
    high = close * np.exp(np.abs(rng.normal(0, 0.001, n)))
    low = close * np.exp(-np.abs(rng.normal(0, 0.001, n)))
    return {"high": high, "low": low, "close": close}


def test_occ_4h_is_dss_v2_f2a():
    b = _bars(3000)
    idx = np.arange(47, 3000, 3)
    assert np.allclose(occ_l(b["high"], b["low"], b["close"], idx, 4), occupancy(b, idx)["OCC_MEAN_4H"], atol=1e-14)


def test_occ_l_definition_past_only_and_undefined_cases():
    b = _bars(400, 1)
    i = 300
    for h in K.LOOKBACK_HOURS:
        n = 12 * h
        hi, lo = b["high"][i - n + 1:i + 1].max(), b["low"][i - n + 1:i + 1].min()
        want = np.mean((b["close"][i - n + 1:i] - lo) / (hi - lo))
        assert occ_l(b["high"], b["low"], b["close"], np.array([i]), h)[0] == pytest.approx(want, abs=1e-14)
        b2 = {k: v.copy() for k, v in b.items()}
        b2["close"][i + 1:] *= 1.5                                  # the future
        b2["close"][i] = 0.5 * (b2["high"][i] + b2["low"][i])       # the current close, inside its own bar
        assert occ_l(b2["high"], b2["low"], b2["close"], np.array([i]), h)[0] == pytest.approx(want, abs=1e-14)
    assert np.isnan(occ_l(b["high"], b["low"], b["close"], np.array([10]), 1))      # 11 < 12 bars of history
    flat = {k: np.ones(200) for k in ("high", "low", "close")}
    assert np.isnan(occ_l(flat["high"], flat["low"], flat["close"], np.array([150]), 2))
    holed = {k: v.copy() for k, v in b.items()}
    holed["high"][295] = np.nan
    assert np.isnan(occ_l(holed["high"], holed["low"], holed["close"], np.array([i]), 1))


def test_rp_identity_detects_a_shifted_bar_index():
    b = _bars(600, 2)
    bar = np.arange(60, 600, 3)
    w = bar[:, None] + np.arange(-47, 1)[None, :]
    rp = (b["close"][bar] - b["low"][w].min(axis=1)) / (b["high"][w].max(axis=1) - b["low"][w].min(axis=1))
    assert rp_identity(b, bar, rp) < 1e-14 and rp_identity(b, bar - 1, rp) > 1e-3


@pytest.fixture
def small(monkeypatch):
    monkeypatch.setattr(K, "MEMORIES_WEEKS", (2, 4, 8))
    monkeypatch.setattr(K, "INNER_BLOCKS", 2)
    monkeypatch.setattr(K, "BLOCK_DAYS", 7)
    rng = np.random.default_rng(3)
    per = 16 * 7 * 96                                               # 16 weeks of 15-minute anchors per venue
    starts = (T0 + K.HOUR_MS, T0 + 20 * K.WEEK_MS + K.HOUR_MS)
    n = 2 * per
    rows = {"close_ms": np.concatenate([s + np.arange(per, dtype=np.int64) * Q for s in starts]),
            "venue": np.repeat(np.array([0, 1], dtype=np.int64), per), "rp": rng.uniform(0, 1, n),
            "ret4": rng.normal(0, 0.01, n), "rv4": rng.uniform(0.005, 0.02, n), "ret1h": rng.normal(0, 0.005, n),
            "ret15": rng.normal(0, 0.003, n), "r1": rng.normal(0, 1, n), "bar": np.arange(n, dtype=np.int64) * 3}
    rows["era"] = np.where(rows["venue"] == 0, 0, np.where(np.arange(n) < per + per // 2, 1, 2)).astype(np.int64)
    for h in K.LOOKBACK_HOURS:
        rows[f"OCC_{h}H"] = np.clip(rows["rp"] + rng.normal(0, 0.1 * h, n), 0, 1)
    eta = 0.6 * (0.5 - rows["OCC_2H"]) * (rows["venue"] == 0) + 0.6 * (0.5 - rows["OCC_8H"]) * (rows["venue"] == 1)
    y = (rng.uniform(size=n) < 1 / (1 + np.exp(-eta))).astype(float)
    return rows, y


def test_schedule_per_venue_starts_on_mondays_after_enough_history(small):
    rows, _ = small
    s = WF.schedule(rows)
    assert set(s) == {0, 1}
    for v, sv in s.items():
        need = (2 * 7 + 2 * 7) * K.DAY_MS
        assert sv["first_outer_ms"] >= sv["first_ms"] + need
        assert np.datetime64(sv["first_outer_ms"], "ms").astype("datetime64[D]").astype(int) % 7 == 4   # Monday
        assert np.all(np.diff(sv["grid_starts"]) == 7 * K.DAY_MS)
        assert sv["grid_starts"][0] == sv["first_outer_ms"] - 2 * 7 * K.DAY_MS
    assert s[1]["first_outer_ms"] > s[0]["last_ms"]


def test_memory_eligibility():
    first = T0
    blk = WF.block_ms()
    for S in (T0 + 50 * K.WEEK_MS, T0 + 80 * K.WEEK_MS, T0 + 130 * K.WEEK_MS):
        el = WF.eligible_memories(S, first)
        assert el == [m for m in K.MEMORIES_WEEKS if S - K.INNER_BLOCKS * blk - m * K.WEEK_MS >= first]
    assert WF.eligible_memories(T0 + 50 * K.WEEK_MS, first) == [26]


def test_choose_order():
    c = {(26, "OCC_4H"): (0.25, 0.70), (52, "OCC_2H"): (0.25, 0.70), (104, "OCC_2H"): (0.25, 0.70),
         (26, "NO_OCC"): (0.2500001, 0.6)}
    assert WF.choose(c) == (104, "OCC_2H")                          # tie: longer memory, then shorter lookback
    c[(26, "NO_OCC")] = (0.25, 0.70)
    assert WF.choose(c) == (26, "NO_OCC")                           # tie: NO_OCC first
    c[(52, "OCC_12H")] = (0.25, 0.69)
    assert WF.choose(c) == (52, "OCC_12H")                          # Brier tie broken by log loss
    c[(26, "OCC_1H")] = (0.2499, 0.9)
    assert WF.choose(c) == (26, "OCC_1H")                           # Brier first


def test_a_block_never_sees_its_own_outcomes(small):
    rows, y = small
    s = WF.schedule(rows)
    base = E.evaluate_predictions(rows, s, y, log_models=False)
    for v in (0, 1):
        S = int(s[v]["outer_starts"][2])
        blk = WF.block_ms()
        inv = rows["venue"] == v
        m = inv & (rows["close_ms"] > S - K.HOUR_MS)                 # every label not realized by S (and later)
        y2 = y.copy()
        y2[m] = 1 - y2[m]
        alt = E.evaluate_predictions(rows, s, y2, log_models=False)
        tgt = inv & (rows["close_ms"] >= S) & (rows["close_ms"] < S + blk)
        for name in E.MODELS:
            assert np.allclose(base["preds"][name][tgt], alt["preds"][name][tgt]), name
        k = [i for i, b in enumerate(base["sel"]["log"]) if b["outer_start_ms"] == S][0]
        for key in ("selected_memory_weeks", "selected_config", "inner_brier"):
            assert base["sel"]["log"][k][key] == alt["sel"]["log"][k][key]


def test_the_label_realized_exactly_at_the_block_start_is_used(small):
    rows, y = small
    s = WF.schedule(rows)
    S = int(s[0]["outer_starts"][2])
    assert WF.realized_by(np.array([S - K.HOUR_MS, S - K.HOUR_MS + Q]), S).tolist() == [True, False]


def test_venues_never_train_on_each_other(small):
    rows, y = small
    s = WF.schedule(rows)
    base = E.evaluate_predictions(rows, s, y, log_models=False)
    y2 = y.copy()
    y2[rows["venue"] == 0] = 1 - y2[rows["venue"] == 0]
    alt = E.evaluate_predictions(rows, s, y2, log_models=False)
    v1 = (rows["venue"] == 1) & base["om"]
    for name in E.MODELS:
        assert np.allclose(base["preds"][name][v1], alt["preds"][name][v1]), name


def test_outer_predictions_complete_and_selector_log(small):
    rows, y = small
    s = WF.schedule(rows)
    ev = E.evaluate_predictions(rows, s, y)
    for name in E.MODELS:
        assert np.isfinite(ev["preds"][name][ev["om"]]).all()
    log = ev["sel"]["log"]
    assert len(log) == sum(int(sv["outer_starts"].size) for sv in s.values())
    for b in log:
        assert b["selected_config"] in K.CONFIGS and b["selected_memory_weeks"] in b["eligible_memories"]
        assert b["train_end_ms"] == b["outer_start_ms"] and b["inner_interval_ms"][1] == b["outer_start_ms"]
        assert b["model"]["beta_occ"] is None or np.isfinite(b["model"]["beta_occ"])
    ad = ev["preds"]["ADAPTIVE"]
    for b in log:                                                   # ADAPTIVE = the chosen frozen model's prediction
        v = {n: k for k, n in K.VENUES.items()}[b["venue"]]
        m = (rows["venue"] == v) & (rows["close_ms"] >= b["outer_start_ms"]) & (rows["close_ms"] < b["outer_end_ms"])
        pick = ev["grid"]["preds"][(b["selected_memory_weeks"], b["selected_config"])][m]
        assert np.array_equal(ad[m], pick)


def test_planted_occupancy_is_selected(small):
    rows, y = small
    ev = E.evaluate_predictions(rows, WF.schedule(rows), y, log_models=False)
    share = E.selection_share(ev["sel"]["log"])
    assert share["NO_OCC"] < 0.5


def test_feature_digest_never_reads_the_outcome(small):
    rows, _ = small
    a = E.feature_digest(rows)
    rows["r1"] = -rows["r1"]
    rows["y"] = np.zeros(rows["r1"].size)
    assert E.feature_digest(rows) == a
    rows["OCC_3H"] = rows["OCC_3H"] + 1e-9
    assert E.feature_digest(rows) != a


def test_synthetic_outcomes(small):
    rows, _ = small
    a = E.synthetic_y(rows, None, None, 1)
    assert np.array_equal(a, E.synthetic_y(rows, None, None, 1)) and 0.45 < a.mean() < 0.55
    eras = rows["era"]
    same = (eras[1:] == eras[:-1])
    assert np.mean(a[1:][same] == a[:-1][same]) > 0.7             # 15-minute anchors share 3 of 4 hourly quarters
    b = E.synthetic_y(rows, "OCC_2H", "OCC_8H", 1)
    assert b.shape == a.shape and set(np.unique(b)) <= {0.0, 1.0}


def _d(point, lo, hi, valid=2000):
    return {"point": point, "lo": lo, "hi": hi, "valid": valid}


@pytest.mark.parametrize("b,l,slope,want", [
    (_d(-1e-5, -2e-5, -1e-6), _d(-1e-5, -2e-5, 0), 0.8, K.ROUTE_SUPPORTED),
    (_d(-1e-5, -2e-5, -1e-6), _d(1e-6, 0, 2e-6), 0.8, K.ROUTE_UNCERTAIN),     # log loss contradicts
    (_d(-1e-5, -2e-5, -1e-6), _d(-1e-5, -2e-5, 0), -0.1, K.ROUTE_UNCERTAIN),  # anti-calibrated
    (_d(-1e-5, -2e-5, 1e-6), _d(-1e-5, -2e-5, 0), 0.8, K.ROUTE_UNCERTAIN),
    (_d(1e-6, -1e-5, 1e-5), _d(0, 0, 0), 0.8, K.ROUTE_NONE),
    (_d(0.0, -1e-5, 1e-5), _d(0, 0, 0), 0.8, K.ROUTE_NONE),
    (_d(2e-5, 1e-6, 3e-5), _d(0, 0, 0), 0.8, K.ROUTE_WORSE),
])
def test_routes(b, l, slope, want):
    assert E.route(b, l, slope) == want
    assert E.route(_d(-1, -2, -0.5, 1899), l, slope) == K.ROUTE_INVALID


def test_adaptation_qualifier():
    assert E.adaptation_vs_static(_d(-1, -2, -0.1)) == "ADAPTIVE_BETTER_THAN_STATIC_OCC4"
    assert E.adaptation_vs_static(_d(1, 0.1, 2)) == "ADAPTIVE_WORSE_THAN_STATIC_OCC4"
    assert E.adaptation_vs_static(_d(0, -1, 1)) == "ADAPTIVE_NOT_DISTINGUISHED_FROM_STATIC_OCC4"


def test_run_refuses(monkeypatch, tmp_path):
    monkeypatch.setattr("sys.argv", ["evaluate", "run"])
    with pytest.raises(SystemExit, match="needs --go"):
        E.main()
    for name in ("RESULT_JSON", "RESULT_MD"):
        monkeypatch.setattr(E, name, tmp_path / f"missing_{name}")
    monkeypatch.setattr(E, "JOURNAL_DIR", tmp_path / "journal")
    monkeypatch.setattr(K, "DESIGN_SHA256", "PENDING")
    with pytest.raises(SystemExit, match="PINS_UNSET"):
        E.run()
    (tmp_path / "journal").mkdir()
    (tmp_path / "journal" / "ATTEMPT.json").write_text("{}")
    with pytest.raises(SystemExit, match="REFUSING_RERUN"):
        E.run()


def test_the_attempt_journal_is_write_once(monkeypatch, tmp_path):
    monkeypatch.setattr(E, "JOURNAL_DIR", tmp_path / "journal")
    E.write_attempt()
    with pytest.raises(FileExistsError):
        E.write_attempt()


def test_imported_machinery_matches_the_frozen_values():
    E.assert_shared()
