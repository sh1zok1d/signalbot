"""Window, RV, pairing, gate, and refusal tests. No market transition is read here."""

import ast
from pathlib import Path

import numpy as np
import pytest

from scripts.research.level_first_touch_resolution_confirmation_v1.cohort import first_touch_status
from scripts.research.level_touch_degradation_v1 import constants as PARENT
from scripts.research.level_volatility_transition_discovery_v1 import claim, inference, rv, windows
from scripts.research.level_volatility_transition_discovery_v1 import constants as K
from scripts.research.level_volatility_transition_discovery_v1.evaluate import refuse_if_recorded

PKG = Path(__file__).resolve().parents[2] / "scripts" / "research" / "level_volatility_transition_discovery_v1"


def _closes_from_returns(returns: np.ndarray, start: float = 100.0) -> np.ndarray:
    close = np.empty(returns.shape[0] + 1)
    close[0] = start
    for i, r in enumerate(returns):
        close[i + 1] = close[i] * np.exp(r)
    return close


def test_parent_identity_and_surface():
    assert K.EVENT_START_MS == PARENT.EVENT_START_MS
    assert K.EVENT_END_MS == PARENT.SURFACE_END_MS
    assert PARENT.EVENT_START == "2020-02-01"
    assert PARENT.SURFACE_END == "2025-01-01"
    assert K.LEVEL_KINDS == ("PMH", "PML", "PWH", "PWL", "PDH", "PDL")
    assert K.BOOT_SEED == 20261024
    assert K.WINDOW_BARS == 12
    assert not K.COMPRESSION_SUBGROUP
    assert K.ALTERNATIVE_HORIZONS == ()
    assert not K.RANGE_4H_ENDPOINT
    assert not K.ADJUSTED_SENSITIVITY
    touch = {
        "touch_number": 2, "open_ms": K.EVENT_START_MS, "window_ok_48": True,
        "side": 1, "x_primary": 0.01,
    }
    assert first_touch_status(touch, event_start_ms=K.EVENT_START_MS, event_end_ms=K.EVENT_END_MS) == "NOT_FIRST"
    late = dict(touch, touch_number=1, open_ms=K.EVENT_END_MS)
    assert first_touch_status(late, event_start_ms=K.EVENT_START_MS, event_end_ms=K.EVENT_END_MS) == "OUTSIDE_WINDOW"


def test_windows_exclude_the_touch_bar_and_do_not_overlap():
    s = windows.spans(100)
    pre = set(range(s["pre_return_lo"], s["pre_return_hi"] + 1))
    post = set(range(s["post_return_lo"], s["post_return_hi"] + 1))
    assert pre == set(range(88, 100))
    assert post == set(range(101, 113))
    assert 100 not in pre and 100 not in post
    assert pre.isdisjoint(post)
    assert s["pre_close_lo"] == 87
    assert s["post_close_hi"] == 112
    close = np.full(200, 100.0)
    close[99] = 50.0  # close_{j-1}; changes the excluded touch return only if close_j stays
    close[100] = 180.0
    pre_r, post_r, touch = rv.assigned_returns(close, 100)
    assert pre_r.shape == (12,)
    assert post_r.shape == (12,)
    assert np.isfinite(touch)
    assert touch == pytest.approx(np.log(180.0 / 50.0))
    assert not np.any(np.isclose(pre_r, touch))
    assert not np.any(np.isclose(post_r, touch))
    # The touch-bar return uses close[j-1]. Moving only that close leaves post returns unchanged
    # when close[j] and everything after it stay put, and changes the last pre return.
    calm = np.full(200, 100.0)
    calm[100:] = np.linspace(100.0, 112.0, 100)
    moved = calm.copy()
    moved[99] = 40.0
    pre_a, post_a, _ = rv.assigned_returns(calm, 100)
    pre_b, post_b, _ = rv.assigned_returns(moved, 100)
    assert np.allclose(post_a, post_b)
    assert not np.allclose(pre_a, pre_b)


def test_incomplete_path_is_unusable_and_not_filled():
    close = np.full(40, 100.0)
    assert not windows.path_flags(close, 12)["complete"]
    assert windows.path_flags(close, 13)["complete"]
    close[20] = np.nan
    flags = windows.path_flags(close, 25)
    assert not flags["complete"]
    assert rv.event_transition(close, 25) is None
    close[20] = 0.0
    assert not windows.path_flags(close, 25)["complete"]


def test_rv_formula_zero_and_signed_transition():
    # r_j = log(close[j] / close[j-1]) = returns[j-1].
    returns = np.zeros(30)
    returns[0:12] = 0.01
    returns[12] = 5.0
    returns[13:25] = 0.02
    close = _closes_from_returns(returns)
    j = 13
    pre_r, post_r, touch = rv.assigned_returns(close, j)
    assert pre_r.shape == (12,)
    assert np.allclose(pre_r, 0.01)
    assert np.allclose(post_r, 0.02)
    assert touch == pytest.approx(5.0)
    got = rv.event_transition(close, j)
    assert got["rv_pre"] == pytest.approx(0.01)
    assert got["rv_post"] == pytest.approx(0.02)
    assert got["transition"] == pytest.approx(np.log(2.0))
    returns[13:25] = 0.005
    close = _closes_from_returns(returns)
    got = rv.event_transition(close, j)
    assert got["transition"] < 0.0
    flat = np.full(40, 100.0)
    assert windows.path_flags(flat, j)["complete"]
    assert rv.realized(np.zeros(12)) is None
    assert rv.event_transition(flat, j) is None


def test_pair_delta_and_week_bootstrap_are_atomic():
    weeks = np.array([1, 1, 2, 2, 3])
    deltas = np.array([0.2, 0.0, -0.1, 0.1, 0.05])
    first = inference.bootstrap_mean(weeks, deltas, draws=400, seed=K.BOOT_SEED)
    second = inference.bootstrap_mean(weeks, deltas, draws=400, seed=K.BOOT_SEED)
    assert first["delta"] == pytest.approx(float(np.mean(deltas)))
    assert first["ci95"] == second["ci95"]
    assert first["p"] == second["p"]
    assert first["ci95"][0] < first["delta"] < first["ci95"][1]
    constant = np.full(8, 0.25)
    fitted = inference.bootstrap_mean(np.arange(8), constant, draws=100, seed=7)
    assert fitted["delta"] == pytest.approx(0.25)
    assert fitted["ci95"][0] == pytest.approx(0.25)
    assert fitted["ci95"][1] == pytest.approx(0.25)
    assert fitted["p"] == 0.0


def test_information_gate_and_practical_scale():
    years = {str(y): 100 for y in K.YEARS}
    assert claim.support_gate(800, 150, years)["pass"]
    assert not claim.support_gate(799, 150, years)["pass"]
    assert not claim.support_gate(800, 149, years)["pass"]
    thin = dict(years)
    thin["2023"] = 99
    thin["2024"] = 99
    assert not claim.support_gate(800, 150, thin)["pass"]
    assert K.PRACTICAL_LOG == pytest.approx(np.log(1.10))
    assert claim.statistical_pass(np.log(1.10), (0.01, 0.2))
    assert not claim.statistical_pass(np.log(1.09), (0.01, 0.2))
    assert not claim.statistical_pass(np.log(1.20), (-0.01, 0.2))


def _epoch(name, n, delta):
    return {"name": name, "n": n, "delta": delta}


def test_year_family_side_and_loyo_rules():
    full = 0.2
    five = [_epoch(y, 100, full) for y in K.YEARS]
    five[4] = _epoch(2024, 100, -0.5)
    assert claim.year_stability(full, five)["pass"]
    four = five[:4]
    four[3] = _epoch(2023, 100, -np.log(1.10))
    assert not claim.year_stability(full, four)["pass"]
    four[3] = _epoch(2023, 100, -np.log(1.09))
    assert claim.year_stability(full, four)["pass"]
    three = [_epoch(y, 100, full) for y in (2020, 2021, 2022)]
    assert claim.year_stability(full, three)["pass"]
    three[2] = _epoch(2022, 100, -0.01)
    assert not claim.year_stability(full, three)["pass"]
    assert not claim.year_stability(full, three[:2])["pass"]
    loyo = [_epoch(f"omit_{y}", 400, full) for y in K.YEARS]
    assert claim.loyo_stability(full, loyo)["pass"]
    loyo[0] = _epoch("omit_2020", 400, -0.01)
    assert not claim.loyo_stability(full, loyo)["pass"]
    scale = float(np.log(1.10))
    families = [_epoch("DAY", 50, scale), _epoch("WEEK", 50, -scale), _epoch("MONTH", 10, -1.0)]
    assert not claim.family_stability(families)["pass"]
    families[1] = _epoch("WEEK", 50, -scale + 1e-6)
    assert claim.family_stability(families)["pass"]
    sides = [_epoch("resistance", 100, scale), _epoch("support", 100, -scale)]
    assert not claim.side_stability(sides)["pass"]
    sides[1] = _epoch("support", 100, -0.01)
    assert claim.side_stability(sides)["pass"]


def test_routes():
    common = dict(
        delta=float(np.log(1.2)), ci=(0.1, 0.2), ci_withheld=False,
        epochs=[_epoch(y, 120, 0.2) for y in K.YEARS],
        families=[_epoch("DAY", 80, 0.2), _epoch("WEEK", 80, 0.2), _epoch("MONTH", 10, 0.2)],
        sides=[_epoch("resistance", 120, 0.2), _epoch("support", 120, 0.2)],
        loyo=[_epoch(f"omit_{y}", 400, 0.2) for y in K.YEARS],
        loyo_ran=True, artifact=False, pre_gate=True, usable_gate=True,
        blocked_key_level=False, blocked_vol_cell=False,
    )
    assert claim.decide(**common)["routing"] == "LEVEL_VOLATILITY_TRANSITION_STRUCTURE_PRESENT"
    assert claim.decide(**common)["candidate_class"] == "LEVEL_VOLATILITY_TRANSITION_CANDIDATE"
    unstable = dict(common, epochs=[_epoch(y, 120, -0.2) for y in K.YEARS])
    assert claim.decide(**unstable)["routing"] == "STRUCTURE_PRESENT_BUT_UNSTABLE"
    small = dict(common, delta=0.01, ci=(-0.01, 0.02))
    assert claim.decide(**small)["routing"] == "NO_INCREMENTAL_LEVEL_VOLATILITY_TRANSITION"
    thin = dict(common, usable_gate=False)
    assert claim.decide(**thin)["routing"] == "VOLATILITY_TRANSITION_INFORMATION_INSUFFICIENT"
    blocked = dict(common, blocked_key_level=True)
    assert claim.decide(**blocked)["routing"] == "BLOCKED_REOPENING_KEY_LEVEL_RANGE"
    cell = dict(common, blocked_vol_cell=True)
    assert claim.decide(**cell)["routing"] == "BLOCKED_REOPENING_VOLATILITY_TRANSITION_CELL"


def test_preflight_sources_cannot_compute_a_transition():
    for name in ("preflight.py", "cohort.py", "windows.py"):
        text = (PKG / name).read_text()
        assert "from .rv" not in text
        assert "VOL_TRANSITION" not in text
        assert "np.log" not in text
        assert "sqrt" not in text
        assert "tercile" not in text.lower()
    assert K.RANGE_4H_ENDPOINT is False
    tree = ast.parse((PKG / "evaluate.py").read_text())
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and (node.module or "").endswith("analyze"):
            raise AssertionError("evaluate imports analyze at module level")
    assert "from .rv import" in (PKG / "analyze.py").read_text()


def test_rerun_refusal(tmp_path):
    recorded = tmp_path / "RESULT.json"
    recorded.write_text("{}\n")
    with pytest.raises(SystemExit, match="REFUSING_RERUN"):
        refuse_if_recorded(recorded, tmp_path / "missing.md")
