from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from scripts.research import b2_02_boundary_interaction_path_lib as lib
from scripts.research.lib.batch02_source_policy import (
    validate_batch02_source_tree,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
RESEARCH_DIR = REPO_ROOT / "scripts" / "research"
PREREG = (
    REPO_ROOT
    / "docs"
    / "research"
    / "B2_02_BOUNDARY_INTERACTION_PATH_PREREG.json"
)


def _small_frame(n: int = 10) -> dict[str, np.ndarray]:
    open_ms = (
        lib.WARMUP_START_MS
        + np.arange(n, dtype=np.int64) * lib.BAR_MS
    )
    close = 100.0 + np.arange(n, dtype=np.float64) * 0.01
    opn = np.concatenate(([100.0], close[:-1]))
    high = np.maximum(opn, close) + 0.05
    low = np.minimum(opn, close) - 0.05
    return {
        "open_time_ms": open_ms,
        "available_at_ms": open_ms + lib.BAR_MS,
        "open": opn,
        "high": high,
        "low": low,
        "close": close,
    }


def _cell(L: int, H: int, passed: bool, stable: bool) -> dict:
    gates = {
        name: passed
        for name in lib.PER_CELL_GATE_NAMES
    }
    return {
        "L": L,
        "H": H,
        "per_cell_gates": gates,
        "year_stability_pass": stable,
    }


def test_prereg_constants_match_implementation_freeze():
    freeze = json.loads(PREREG.read_text(encoding="utf-8"))
    assert freeze["formulation_id"] == lib.HYPOTHESIS_ID
    assert freeze["dataset"]["dataset_id"] == lib.DATASET_ID
    assert freeze["dataset"]["snapshot_id"] == lib.REQUIRED_SNAPSHOT
    assert tuple(freeze["prior_range_lookbacks_minutes"]) == lib.LOOKBACKS
    assert tuple(freeze["horizons_minutes"]) == lib.HORIZONS
    assert freeze["chronology"]["path_observation_minutes"] == lib.PATH_MIN
    assert freeze["forecast"]["training_lookback_days"] == lib.TRAIN_DAYS
    assert freeze["forecast"]["baseline_min_count"] == lib.BASELINE_MIN_COUNT
    assert freeze["forecast"]["candidate_min_count"] == lib.CANDIDATE_MIN_COUNT
    assert tuple(
        freeze["promotion_gate_contract"]["required_gate_names"]
    ) == lib.GATE_NAMES
    assert freeze["search_surface_primary_cells"] == 12
    assert freeze["outcome_access_authorized"] is False
    assert freeze["validation_2025_authorized"] is False
    assert freeze["oos_2026_authorized"] is False


def test_aggregate_1m_to_5m_uses_complete_buckets_and_availability():
    frame = _small_frame(10)
    five = lib.aggregate_1m_to_5m(frame)
    assert len(five["close"]) == 2
    assert five["open"][0] == frame["open"][0]
    assert five["close"][0] == frame["close"][4]
    assert five["high"][0] == np.max(frame["high"][:5])
    assert five["low"][0] == np.min(frame["low"][:5])
    assert five["available_at_ms"][0] == lib.WARMUP_START_MS + 5 * lib.BAR_MS


def test_context_and_path_states_are_causal_same_L():
    base = lib.DEV_START_MS
    events = []
    for i, value in enumerate((1.0, 2.0, 3.0, 4.0)):
        t0 = base + i * lib.DAY_MS
        events.append(
            {
                "L": 60,
                "side": "UPPER",
                "direction": 1,
                "T0": t0,
                "T": t0 + lib.PATH_MS,
                "T_index": i,
                "breach_mag": value,
                "pre_vol": value,
                "pre_drift": value,
                "residence": value / 4.0,
                "terminal_extension": value,
                "max_extension": value,
                "path_efficiency": value / 10.0,
            }
        )
    states = lib.attach_states(events)
    assert states[0]["breach_state"] == lib.STATE_MISSING
    assert states[0]["path_state"] == lib.STATE_MISSING
    assert states[1]["breach_state"] == lib.STATE_HIGH
    assert states[1]["pre_vol_state"] == lib.STATE_HIGH
    assert states[1]["pre_drift_state"] == lib.STATE_HIGH
    assert states[1]["path_state"] == lib.STATE_HIGH


def test_event_identity_binds_timeframes_and_horizon():
    event = {
        "L": 120,
        "side": "LOWER",
        "T0": 123,
        "T": 456,
    }
    identity = lib._event_id(event, 60)
    assert identity.split("|") == [
        lib.REQUIRED_SNAPSHOT,
        "1m",
        "5m",
        "120",
        "LOWER",
        "123",
        "456",
        "60",
    ]


def test_training_maturity_respects_horizon(monkeypatch):
    monkeypatch.setattr(lib, "N_PLACEBO", 5)
    monkeypatch.setattr(lib, "N_BOOT", 20)
    monkeypatch.setattr(
        lib,
        "_target_scale",
        lambda close, H: np.ones(len(close), dtype=np.float64),
    )

    frame5 = {
        "close": 100.0 + np.arange(800, dtype=np.float64) * 0.01,
    }
    events = []
    for i in range(100):
        t = lib.DEV_START_MS + i * lib.PATH_MS
        events.append(
            {
                "L": 60,
                "side": "UPPER",
                "direction": 1,
                "T0": t - lib.PATH_MS,
                "T": t,
                "T_index": i * lib.PATH_BARS,
                "breach_state": 1,
                "pre_vol_state": 1,
                "pre_drift_state": 1,
                "path_state": 1,
            }
        )

    c30 = lib.evaluate_cell(frame5, events, 60, 30)
    c60 = lib.evaluate_cell(frame5, events, 60, 60)
    assert c30["N"] == 20
    assert c60["N"] == 19
    assert len(c30["event_ids"]) == c30["N"]
    assert all(event_id.endswith("|30") for event_id in c30["event_ids"])


def test_promotion_requires_same_adjacent_h_pair_on_two_L_values():
    cells = [
        _cell(L, H, passed=(L in {60, 120} and H in {30, 60}), stable=(L in {60, 120} and H in {30, 60}))
        for L in lib.LOOKBACKS
        for H in lib.HORIZONS
    ]
    gates, selected = lib.determine_promotion_gates(cells)
    assert gates == {
        "primary_positive": True,
        "material_relative_mae": True,
        "bootstrap_positive": True,
        "placebo_separation": True,
        "path_ordering": True,
        "horizon_robustness": True,
        "parameter_robustness": True,
        "year_stability": True,
    }
    assert selected == [
        {"L": 60, "H": 30},
        {"L": 60, "H": 60},
        {"L": 120, "H": 30},
        {"L": 120, "H": 60},
    ]


def test_actual_future_b2_source_tree_passes_canonical_policy():
    visited = validate_batch02_source_tree(
        RESEARCH_DIR,
        repo_root=REPO_ROOT,
    )
    names = {path.name for path in visited}
    assert "b2_02_boundary_interaction_path.py" in names
    assert "b2_02_boundary_interaction_path_lib.py" in names
