"""Path bits, within-endpoint arms, overlap, and the frozen estimator."""

from __future__ import annotations

import math
from itertools import product
from pathlib import Path

import numpy as np
import pytest

from scripts.research.level_acceptance_path_discovery_v1 import constants as K
from scripts.research.level_acceptance_path_discovery_v1.claim import conjunction
from scripts.research.level_acceptance_path_discovery_v1.cohort import decision_ms, geometry_status
from scripts.research.level_acceptance_path_discovery_v1.evaluate import refuse_if_recorded
from scripts.research.level_acceptance_path_discovery_v1.inference import bh_adjust, fit_rows, freeze_scales
from scripts.research.level_acceptance_path_discovery_v1.overlap import overlap_audit
from scripts.research.level_acceptance_path_discovery_v1.path import (
    approach_displacement,
    assign_contrast,
    beyond_break_edge,
    end_position_x,
    path_record,
    state_of,
)
from scripts.research.level_post_touch_reaction_discovery_v1.late import late_label
from scripts.research.level_post_touch_reaction_discovery_v1.reactions import early_status, end_position

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "scripts" / "research" / "level_acceptance_path_discovery_v1"
J = 20
ZONE_LOW = 100.0
ZONE_HIGH = 101.0
X = 0.01
BREAK_UP = ZONE_HIGH * (1.0 + X)
REJECT_DOWN = ZONE_LOW * (1.0 - X)


def _touch(**overrides):
    row = {
        "touch_number": 1,
        "open_ms": K.EVENT_START_MS,
        "window_ok_48": True,
        "side": 1,
        "x_primary": 0.01,
        "sigma": 0.002,
    }
    row.update(overrides)
    return row


def _cell(coef=0.05, n_treated=120, n_reference=120, q=0.01, ci=(0.02, 0.08)):
    return {
        "coef": coef,
        "n": n_treated + n_reference,
        "n_treated": n_treated,
        "n_reference": n_reference,
        "q": q,
        "ci95": list(ci),
        "overlap_pass": True,
    }


def _slice(name, coef, n=80, n_treated=40, n_reference=40):
    return {
        "slice": name, "coef": coef, "n": n,
        "n_treated": n_treated, "n_reference": n_reference,
    }


def _passing_parts():
    epochs = [_slice(str(year), 0.04) for year in range(2020, 2025)]
    loyo = [_slice(f"omit_{year}", 0.04, n=200, n_treated=100, n_reference=100) for year in range(2020, 2025)]
    families = [
        _slice("DAY", 0.04, n=200, n_treated=100, n_reference=100),
        _slice("WEEK", 0.03, n=80, n_treated=40, n_reference=40),
        _slice("MONTH", None, n=5, n_treated=3, n_reference=2),
    ]
    sides = [
        _slice("resistance", 0.04, n=100, n_treated=50, n_reference=50),
        _slice("support", 0.05, n=100, n_treated=50, n_reference=50),
    ]
    return epochs, loyo, families, sides


def test_clocks_horizon_and_outcome_blind_preflight():
    assert K.EVENT_START == "2020-02-01T00:00:00+00:00"
    assert K.EVENT_END.startswith("2025-01-01")
    assert K.REACTION_MS == 15 * 60 * 1000
    assert K.EARLY_START_OFFSET == 1 and K.EARLY_STOP_OFFSET == 3
    assert K.LATE_START_OFFSET == 3 and K.LATE_STOP_OFFSET == 49
    assert K.LATE_STOP_OFFSET == 1 + K.HORIZON
    assert K.HORIZON == 48
    assert K.ARM_MIN_N == 100 and K.OVERLAP_SHARE_MIN == 0.50
    assert K.PRACTICAL_SCALE == 0.03 and K.FDR_Q == 0.10
    assert K.BOOT_SEED == 20261018 and K.BOOT_DRAWS == 2000
    assert K.BOOT_MIN_VALID_FRAC == 0.9
    assert decision_ms(1_000) - 1_000 == K.REACTION_MS
    text = (PACKAGE / "preflight.py").read_text()
    assert "late_label" not in text
    assert "LATE_BREAK" not in text
    for path in PACKAGE.glob("*.py"):
        body = path.read_text().lower()
        for banned in ("taker", "oi.jsonl", "funding", "flow_features", "load_bound_oi"):
            assert banned not in body, (path.name, banned)


def test_first_touch_geometry_window():
    assert geometry_status(_touch()) == "LEGITIMATE"
    assert geometry_status(_touch(touch_number=2)) == "NOT_FIRST"
    assert geometry_status(_touch(touch_number=3)) == "NOT_FIRST"
    assert geometry_status(_touch(open_ms=K.EVENT_START_MS - K.BAR_MS)) == "OUTSIDE_WINDOW"
    assert geometry_status(_touch(open_ms=K.EVENT_END_MS)) == "OUTSIDE_WINDOW"
    assert geometry_status(None) == "NO_TOUCH"


def test_unresolved_at_d_ignores_the_touch_bar_and_starts_the_late_window_at_j3():
    high = np.full(80, 100.8)
    low = np.full(80, 100.2)
    high[J] = BREAK_UP + 5
    low[J] = REJECT_DOWN - 5
    assert early_status(high, low, J, 1, ZONE_LOW, ZONE_HIGH, X) == "UNRESOLVED"
    high[J + 1] = BREAK_UP
    assert early_status(high, low, J, 1, ZONE_LOW, ZONE_HIGH, X) == "EARLY_BREAK"
    high[J + 1] = 100.8
    low[J + 2] = REJECT_DOWN
    assert early_status(high, low, J, 1, ZONE_LOW, ZONE_HIGH, X) == "EARLY_REJECT"
    high[J + 1] = BREAK_UP
    low[J + 1] = REJECT_DOWN
    assert early_status(high, low, J, 1, ZONE_LOW, ZONE_HIGH, X) == "EARLY_AMBIGUOUS"
    high[:] = 100.8
    low[:] = 100.2
    high[J + 3] = BREAK_UP
    assert early_status(high, low, J, 1, ZONE_LOW, ZONE_HIGH, X) == "UNRESOLVED"
    assert late_label(high, low, J, 1, ZONE_LOW, ZONE_HIGH, X) == "BREAK"
    high[J + 3] = 100.8
    low[J + 48] = REJECT_DOWN
    assert late_label(high, low, J, 1, ZONE_LOW, ZONE_HIGH, X) == "REJECT"
    low[J + 48] = 100.2
    low[J + 49] = REJECT_DOWN
    assert late_label(high, low, J, 1, ZONE_LOW, ZONE_HIGH, X) == "NEITHER"


def test_break_side_indicator_uses_a_strict_zone_edge():
    assert beyond_break_edge(ZONE_HIGH + 0.1, 1, ZONE_LOW, ZONE_HIGH) == 1
    assert beyond_break_edge(ZONE_HIGH, 1, ZONE_LOW, ZONE_HIGH) == 0
    assert beyond_break_edge(ZONE_HIGH - 0.1, 1, ZONE_LOW, ZONE_HIGH) == 0
    assert beyond_break_edge(ZONE_LOW - 0.1, -1, ZONE_LOW, ZONE_HIGH) == 1
    assert beyond_break_edge(ZONE_LOW, -1, ZONE_LOW, ZONE_HIGH) == 0
    assert beyond_break_edge(ZONE_LOW + 0.1, -1, ZONE_LOW, ZONE_HIGH) == 0
    assert beyond_break_edge(math.nan, 1, ZONE_LOW, ZONE_HIGH) is None


def test_eight_sequences_partition_the_four_states_for_both_sides():
    expected = {
        (0, 0, 0): "NEVER_OUTSIDE",
        (0, 0, 1): "LATE_OR_RECROSS_OUTSIDE",
        (0, 1, 0): "REENTERED",
        (0, 1, 1): "PERSISTENT_OUTSIDE",
        (1, 0, 0): "REENTERED",
        (1, 0, 1): "LATE_OR_RECROSS_OUTSIDE",
        (1, 1, 0): "REENTERED",
        (1, 1, 1): "PERSISTENT_OUTSIDE",
    }
    assert set(expected) == set(product((0, 1), repeat=3))
    seen = {}
    open_ms = J * K.BAR_MS
    for bits, state in expected.items():
        assert state_of(*bits) == state
        seen.setdefault(state, set()).add(bits)
        contrast, indicator = assign_contrast(state)
        if bits[2] == 0:
            assert contrast == "REENTRY_MEMORY"
            assert indicator == (1 if state == "REENTERED" else 0)
        else:
            assert contrast == "PERSISTENCE_MEMORY"
            assert indicator == (1 if state == "PERSISTENT_OUTSIDE" else 0)
        for side, inside, outside in ((1, 100.5, 101.5), (-1, 100.5, 99.0)):
            close = np.full(40, inside)
            close[J + 3] = 10.0 if side > 0 else 10_000.0
            for offset, bit in enumerate(bits):
                close[J + offset] = outside if bit else inside
            recorded = path_record(close, 0, open_ms, side, ZONE_LOW, ZONE_HIGH, X)
            assert recorded["sequence"] == f"{bits[0]}{bits[1]}{bits[2]}"
            assert recorded["state"] == state
            assert recorded["contrast"] == contrast
            assert recorded["state_indicator"] == indicator
            assert recorded["B0"] == bits[0] and recorded["B2"] == bits[2]
    assert set(seen) == set(K.STATES)
    assert sum(len(v) for v in seen.values()) == 8


def test_end_position_matches_the_parent_formula_and_displacement_is_price_only():
    assert end_position_x(105.0, 1, ZONE_LOW, ZONE_HIGH, X) == end_position(105.0, 1, ZONE_LOW, ZONE_HIGH, X)
    assert end_position_x(99.0, -1, ZONE_LOW, ZONE_HIGH, X) == end_position(99.0, -1, ZONE_LOW, ZONE_HIGH, X)
    up = (105.0 - ZONE_HIGH) / (ZONE_HIGH * X)
    assert math.isclose(end_position_x(105.0, 1, ZONE_LOW, ZONE_HIGH, X), up)
    down = (ZONE_LOW - 99.0) / (ZONE_LOW * X)
    assert math.isclose(end_position_x(99.0, -1, ZONE_LOW, ZONE_HIGH, X), down)
    open_ms = J * K.BAR_MS
    open_ = np.full(40, 100.0)
    close = np.full(40, 100.0)
    open_[J - 12] = 100.0
    close[J - 1] = math.exp(0.02) * 100.0
    close[J] = 50.0
    got = approach_displacement(open_, close, 0, open_ms, 1)
    assert math.isclose(got, 0.02)
    got_support = approach_displacement(open_, close, 0, open_ms, -1)
    assert math.isclose(got_support, -0.02)


def test_overlap_gate_is_common_support_and_arm_size():
    rng = np.random.default_rng(0)
    left = rng.normal(0.0, 1.0, 180)
    right = rng.normal(0.05, 1.0, 180)
    near = overlap_audit(left, right, contrast="REENTRY_MEMORY")
    assert near["arm_n_pass"] and near["overlap_pass"]
    assert near["overlap_width"] > 0.0
    far = overlap_audit(left, rng.normal(12.0, 0.05, 180), contrast="PERSISTENCE_MEMORY")
    assert far["arm_n_pass"] and not far["overlap_pass"]
    assert "COMPARISON_INFORMATION_LIMITED_NO_OVERLAP" in far["block_reasons"]
    small = overlap_audit(left[:40], right[:40], contrast="REENTRY_MEMORY")
    assert not small["arm_n_pass"]
    assert "ARM_N_BELOW_MINIMUM" in small["block_reasons"]
    assert small["standardized_difference"] is not None


def test_state_indicator_is_not_standardized_and_week_bootstrap_returns_an_interval():
    rows = []
    for i in range(40):
        state = i % 2
        rows.append({
            "state": state,
            "y": 0.2 + 0.4 * state,
            "family": "DAY",
            "support": 0.0,
            "vol_tercile": 0,
            "epoch": "2021",
            "time_block": 0,
            "disp": 0.01,
            "END_POSITION_X": 0.5,
            "cluster": i % 8,
        })
    scales = {"END_POSITION_X": {"mean": 0.0, "sd": 1.0}, "disp": {"mean": 0.0, "sd": 1.0}}
    point = fit_rows(rows, scales, draws=0)
    assert math.isclose(point["coef"], 0.4)
    assert point["n_treated"] == 20 and point["n_reference"] == 20
    rng = np.random.default_rng(1)
    varied = []
    for i in range(160):
        state = int(rng.integers(0, 2))
        varied.append({
            "state": state,
            "y": 1.0 if rng.random() < 0.30 + 0.20 * state else 0.0,
            "family": str(rng.choice(["DAY", "WEEK", "MONTH"])),
            "support": float(rng.integers(0, 2)),
            "vol_tercile": int(rng.integers(0, 3)),
            "epoch": str(rng.choice(list(K.EPOCHS))),
            "time_block": int(rng.integers(0, 4)),
            "disp": float(rng.normal()),
            "END_POSITION_X": float(rng.normal()),
            "cluster": int(i // 10),
        })
    fitted = fit_rows(varied, freeze_scales(varied), draws=40, seed=K.stream_seed(0, 0))
    assert fitted["coef"] is not None
    assert fitted["bootstrap_valid"] >= 36
    assert fitted["ci95"][0] < fitted["ci95"][1]
    assert fitted["n_treated"] > 0 and fitted["n_reference"] > 0


def test_fdr_loyo_and_family_rule():
    adjusted = bh_adjust([0.01, 0.20])
    assert math.isclose(adjusted[0], 0.02)
    assert math.isclose(adjusted[1], 0.20)
    epochs, loyo, families, sides = _passing_parts()
    assert conjunction(_cell(), epochs, loyo, families, sides)["pass"]
    flipped = list(epochs)
    flipped[0] = _slice("2020", -0.02)
    assert "epochs" not in conjunction(_cell(), flipped, loyo, families, sides)["failed"]
    flipped[1] = _slice("2021", -0.02)
    assert "epochs" in conjunction(_cell(), flipped, loyo, families, sides)["failed"]
    loyo_flip = list(loyo)
    loyo_flip[0] = _slice("omit_2020", -0.01, n=200, n_treated=100, n_reference=100)
    assert "loyo" in conjunction(_cell(), epochs, loyo_flip, families, sides)["failed"]
    loyo_missing = list(loyo)
    loyo_missing[0] = _slice("omit_2020", None, n=200, n_treated=100, n_reference=100)
    assert "loyo" in conjunction(_cell(), epochs, loyo_missing, families, sides)["failed"]
    opposite = [
        _slice("DAY", 0.04, n=200, n_treated=100, n_reference=100),
        _slice("WEEK", -0.03, n=80, n_treated=40, n_reference=40),
        families[2],
    ]
    assert "family" in conjunction(_cell(), epochs, loyo, opposite, sides)["failed"]
    week_missing = [
        families[0],
        _slice("WEEK", None, n=80, n_treated=40, n_reference=40),
        families[2],
    ]
    assert "family" not in conjunction(_cell(), epochs, loyo, week_missing, sides)["failed"]
    assert K.exposure(2)["lofo_cells"] == 0


def test_refuse_second_run(tmp_path):
    recorded = tmp_path / "result.json"
    recorded.write_text("{}\n")
    with pytest.raises(SystemExit, match="REFUSING_RERUN"):
        refuse_if_recorded(recorded, tmp_path / "missing.md")


def test_pseudo_path_uses_the_same_state_function():
    """The control price is classified by the same bits. It does not get its own taxonomy."""
    bits = (1, 0, 0)
    assert state_of(*bits) == "REENTERED"
    assert assign_contrast("REENTERED") == ("REENTRY_MEMORY", 1)
    assert assign_contrast("PERSISTENT_OUTSIDE") == ("PERSISTENCE_MEMORY", 1)
    assert "FALSE_BREAK" not in K.STATES
    assert "ACCEPTANCE" not in K.STATES
