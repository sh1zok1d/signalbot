"""RANGE_POSITION_4H_TIME_DISJOINT_REPLICATION_V1: formulas, past-only features, E1 guard, routes (synthetic data only)."""
import json
import math

import numpy as np
import pytest
from scipy import stats

from scripts.research.rp4h_time_disjoint_v1 import run as R

T0 = R._ms("2021-03-01T00:00:00")


def _walk(n=3000, seed=1):
    rng = np.random.default_rng(seed)
    close = 30000 * np.exp(np.cumsum(rng.normal(0, 0.002, n)))
    high = close * np.exp(np.abs(rng.normal(0, 0.001, n)))
    low = close * np.exp(-np.abs(rng.normal(0, 0.001, n)))
    return {"open_ms": T0 + np.arange(n, dtype=np.int64) * R.BAR, "open": close, "high": high, "low": low, "close": close}


def _rows(panel, n):
    g = R.to_grid(panel, T0, T0 + n * R.BAR)
    return g, R.features(g, T0 + n * R.BAR)


def test_anchor_phase_and_range_position_bounds():
    p = _walk()
    _, rows = _rows(p, 3000)
    assert rows["T_MS"].size > 0
    assert np.all(rows["T_MS"] % (15 * 60_000) == 0)               # T at :00/:15/:30/:45
    assert np.all((rows["RP4H"] >= 0) & (rows["RP4H"] <= 1))


def test_features_are_past_only_and_target_is_future():
    p = _walk()
    _, base = _rows(p, 3000)
    k = 40
    t = base["T_MS"][k]
    j = int((t - T0) // R.BAR) - 1                                  # anchor bar index
    q = {c: v.copy() for c, v in p.items()}
    q["close"][j + 1:] *= 1.05                                      # change every bar after the anchor bar
    q["high"][j + 1:] *= 1.05
    q["low"][j + 1:] *= 1.05
    _, alt = _rows(q, 3000)
    m = np.flatnonzero(alt["T_MS"] == t)[0]
    for c in ("RP4H", "RET_4H", "RV_4H", "RANGE_WIDTH_4H", "RET_1H_LAG", "RET_15M_LAG", "RP4H_PREV"):
        assert alt[c][m] == pytest.approx(base[c][k]), c
    assert alt["R_1H"][m] == pytest.approx(base["R_1H"][k] + math.log(1.05))


def test_formulas_match_hand_computation():
    p = _walk()
    g, rows = _rows(p, 3000)
    k = 10
    i = int((rows["T_MS"][k] - T0) // R.BAR) - 1
    hi, lo, cl = g["high"], g["low"], g["close"]
    w_hi, w_lo = hi[i - 47:i + 1].max(), lo[i - 47:i + 1].min()
    assert rows["RP4H"][k] == pytest.approx((cl[i] - w_lo) / (w_hi - w_lo))
    assert rows["RET_4H"][k] == pytest.approx(math.log(cl[i] / cl[i - 48]))
    rv = math.sqrt(sum(math.log(cl[x] / cl[x - 1]) ** 2 for x in range(i - 47, i + 1)))
    assert rows["RV_4H"][k] == pytest.approx(rv)
    assert rows["R_1H"][k] == pytest.approx(math.log(cl[i + 12] / cl[i]))
    p_hi, p_lo = hi[i - 48:i].max(), lo[i - 48:i].min()
    assert rows["RP4H_PREV"][k] == pytest.approx((cl[i - 1] - p_lo) / (p_hi - p_lo))


def test_missing_bar_drops_every_anchor_that_needs_it():
    p = _walk()
    _, base = _rows(p, 3000)
    drop = 1500
    keep = np.ones(3000, dtype=bool)
    keep[drop] = False
    q = {c: v[keep] for c, v in p.items()}
    _, alt = _rows(q, 3000)
    idx = (alt["T_MS"] - T0) // R.BAR - 1
    assert not np.any((idx - 48 <= drop) & (idx >= drop))          # window or path contains the hole
    assert not np.any(idx + 12 == drop)                            # horizon bar is the hole
    assert alt["T_MS"].size < base["T_MS"].size


def test_bitmex_zero_trade_buckets_are_missing():
    lines = [json.dumps({"open_time_ms": T0 + k * R.BAR, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0,
                         "trades": 0 if k == 1 else 5}) for k in range(3)]
    panel = R.parse_bitmex_lines(lines)
    assert panel["open_ms"].tolist() == [T0, T0 + 2 * R.BAR]


def test_average_ranks_and_partial_spearman_match_reference():
    rng = np.random.default_rng(3)
    x = np.round(rng.normal(size=500), 1)                           # ties
    y = x * 0.3 + rng.normal(size=500)
    z = x * 0.5 + rng.normal(size=500)
    assert np.allclose(R.average_ranks(x), stats.rankdata(x, method="average"))
    assert R.partial_spearman(x, y, []) == pytest.approx(stats.spearmanr(x, y)[0])
    rx, ry, rz = (stats.rankdata(v) for v in (x, y, z))
    rxy, rxz, ryz = np.corrcoef(rx, ry)[0, 1], np.corrcoef(rx, rz)[0, 1], np.corrcoef(ry, rz)[0, 1]
    ref = (rxy - rxz * ryz) / math.sqrt((1 - rxz ** 2) * (1 - ryz ** 2))
    assert R.partial_spearman(x, y, [z]) == pytest.approx(ref)
    assert R.partial_spearman(x, y, [x]) is None                     # degenerate residual


def test_e1_holdout_objects_are_never_planned():
    keys = R.recent_objects()
    names = [k for k, _, _ in keys]
    assert not any("2026-08.zip" in k and "monthly" in k for k in names)
    for d in range(16, 26):
        assert not any(f"2026-08-{d:02d}" in k for k in names)
    assert any("2026-08-15" in k for k in names) and any("2026-08-26" in k for k in names)
    assert all(not R.overlaps_e1(s, e) for _, s, e in keys)
    assert R.overlaps_e1(R._ms("2026-08-25T17:00:00"), R._ms("2026-08-25T17:05:00"))
    assert not R.overlaps_e1(R._ms("2026-08-25T17:20:00"), R._ms("2026-08-25T17:25:00"))


def _boot(raw, prim, valid=2000):
    return {"RAW": {"VALID_DRAWS": valid, "CI95": raw}, "PRIMARY": {"VALID_DRAWS": valid, "CI95": prim}}


@pytest.mark.parametrize("point,boot,expected", [
    ({"RAW": -0.05, "PRIMARY": -0.03}, _boot([-0.06, -0.04], [-0.04, -0.02]), "SUPPORTED"),
    ({"RAW": -0.05, "PRIMARY": -0.01}, _boot([-0.06, -0.04], [-0.02, 0.01]), "RAW_ONLY"),
    ({"RAW": -0.01, "PRIMARY": 0.0}, _boot([-0.03, 0.01], [-0.02, 0.02]), "COMPATIBLE_UNCERTAIN"),
    ({"RAW": 0.01, "PRIMARY": -0.03}, _boot([-0.01, 0.03], [-0.04, -0.02]), "NOT_REPLICATED"),
    ({"RAW": -0.05, "PRIMARY": 0.02}, _boot([-0.06, -0.04], [0.01, 0.03]), "INCREMENTAL_SIGN_OPPOSES"),
    ({"RAW": -0.05, "PRIMARY": -0.03}, _boot([-0.06, -0.04], [-0.04, -0.02], valid=1800), "ESTIMATE_UNAVAILABLE"),
])
def test_routes(point, boot, expected):
    assert R.route(point, boot) == expected


def test_overall_and_labels():
    assert R.overall("SUPPORTED", "SUPPORTED") == "TIME_DISJOINT_REPLICATED_BOTH"
    assert R.overall("SUPPORTED", "RAW_ONLY") == "TIME_DISJOINT_REPLICATED_ONE"
    assert R.overall("NOT_REPLICATED", "SUPPORTED") == "TIME_DISJOINT_CONFLICT"
    assert R.overall("RAW_ONLY", "COMPATIBLE_UNCERTAIN") == "TIME_DISJOINT_NOT_REPLICATED"
    assert R.overall("ESTIMATE_UNAVAILABLE", "SUPPORTED") == "UNAVAILABLE"
    assert R.economic_label([-0.001, 0.002]) == "SIGN_ONLY"
    assert R.economic_label([0.0001, 0.002]) == "MEAN_SHIFT_PRESENT"
    assert R.label([-0.02, -0.01], "S", "A", "O") == "S"


def test_bootstrap_is_deterministic_and_runs_on_synthetic_rows():
    p = _walk(n=9000, seed=5)
    _, rows = _rows(p, 9000)
    old_b = R.B
    try:
        R.B = 30
        a, b = R.bootstrap(rows), R.bootstrap(rows)
    finally:
        R.B = old_b
    assert a == b and a["RAW"]["VALID_DRAWS"] == 30
