from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from scripts.research.b2_01_volatility_transition_lib import (
    D_LAGS,
    GATE_NAMES,
    HORIZONS,
    MISSING_STATE,
    REQUIRED_SNAPSHOT,
    WARMUP_START_MS,
    W_WINDOWS,
    _placebo_candidate_prediction,
    _walk_forward_forecasts,
    canonical_event_id,
    determine_promotion_gates,
    load_prereg,
    paired_loss_summary,
    promotion_gate_contract,
    rolling_midrank_percentile,
    validate_1m_frame,
    validate_prereg,
)
from scripts.research.lib.research_harness import (
    SupportMismatchError,
    fail_closed_gate_conjunction,
)

BAR_MS = 60_000
GRID_MS = 15 * BAR_MS


def _synthetic_1m(n: int = 120) -> dict[str, np.ndarray]:
    open_ms = WARMUP_START_MS + np.arange(n, dtype=np.int64) * BAR_MS
    return {
        "open_time_ms": open_ms,
        "available_at_ms": open_ms + BAR_MS,
        "close": np.linspace(100.0, 101.0, n, dtype=np.float64),
    }


def _all_true_cell(w: int, d: int, h: int, *, year_ok: bool = True) -> dict:
    return {
        "W": w,
        "D": d,
        "H": h,
        "per_cell_gates": {
            "primary_positive": True,
            "material_relative_mae": True,
            "bootstrap_positive": True,
            "placebo_separation": True,
            "transition_ordering": True,
        },
        "year_stability_pass": year_ok,
    }


def test_machine_readable_prereg_matches_implementation_constants():
    prereg = load_prereg()
    validate_prereg(prereg)
    assert prereg["dataset"]["snapshot_id"] == REQUIRED_SNAPSHOT
    assert tuple(prereg["feature_windows_minutes"]) == W_WINDOWS
    assert tuple(prereg["transition_lags_minutes"]) == D_LAGS
    assert tuple(prereg["horizons_minutes"]) == HORIZONS
    assert tuple(
        prereg["promotion_gate_contract"]["required_gate_names"]
    ) == GATE_NAMES


def test_validate_1m_frame_accepts_only_canonical_bar_end_availability():
    frame = _synthetic_1m()
    validate_1m_frame(frame)

    forged = {k: v.copy() for k, v in frame.items()}
    forged["available_at_ms"][10] += 1
    with pytest.raises(Exception, match="bar_end_exclusive"):
        validate_1m_frame(forged)


def test_validate_1m_frame_rejects_noncontiguous_source_bucket_identity():
    frame = _synthetic_1m()
    frame["open_time_ms"][50] += BAR_MS
    frame["available_at_ms"][50] += BAR_MS
    with pytest.raises(Exception, match="contiguous 1m grid"):
        validate_1m_frame(frame)


def test_midrank_excludes_current_and_future_records():
    x = np.asarray([1.0, 2.0, 3.0, 4.0, 999.0], dtype=np.float64)
    out = rolling_midrank_percentile(x, window=3)
    assert out[3] == pytest.approx(1.0)

    changed_future = x.copy()
    changed_future[4] = -999.0
    out2 = rolling_midrank_percentile(changed_future, window=3)
    assert out2[3] == pytest.approx(out[3])

    ties = rolling_midrank_percentile(
        np.asarray([5.0, 5.0, 5.0, 5.0], dtype=np.float64),
        window=3,
    )
    assert ties[3] == pytest.approx(0.5)


def test_walk_forward_baseline_remains_stronger_than_candidate_history():
    target = np.arange(8, dtype=np.float64)
    level = np.zeros(8, dtype=np.int16)
    transition = np.asarray(
        [MISSING_STATE, MISSING_STATE, 0, 0, 0, 0, 0, 0],
        dtype=np.int16,
    )

    base, cand, eligible = _walk_forward_forecasts(
        target,
        level,
        transition,
        h_steps=1,
        baseline_min_count=3,
        candidate_min_count=2,
        ref_steps=6,
    )

    # At i=4, t=0..3 are mature. Baseline must use all four same-level
    # records, including the two whose transition state is unavailable.
    assert eligible[4]
    assert base[4] == pytest.approx(1.5)
    assert cand[4] == pytest.approx(2.5)


def test_walk_forward_joint_maturity_fails_closed():
    target = np.arange(8, dtype=np.float64)
    level = np.zeros(8, dtype=np.int16)
    transition = np.asarray(
        [MISSING_STATE, MISSING_STATE, MISSING_STATE, 0, 0, 0, 0, 0],
        dtype=np.int16,
    )
    base, cand, eligible = _walk_forward_forecasts(
        target,
        level,
        transition,
        h_steps=1,
        baseline_min_count=3,
        candidate_min_count=2,
        ref_steps=6,
    )
    # At i=4 baseline has enough history, candidate has only one joint record.
    assert not eligible[4]
    assert np.isnan(base[4])
    assert np.isnan(cand[4])


def test_walk_forward_cannot_use_unmatured_training_outcome():
    target = np.arange(10, dtype=np.float64)
    level = np.zeros(10, dtype=np.int16)
    transition = np.zeros(10, dtype=np.int16)

    base1, cand1, _ = _walk_forward_forecasts(
        target,
        level,
        transition,
        h_steps=2,
        baseline_min_count=1,
        candidate_min_count=1,
        ref_steps=8,
    )
    changed = target.copy()
    changed[3] = 1_000_000.0  # Not mature for decision i=4 when H=2.
    base2, cand2, _ = _walk_forward_forecasts(
        changed,
        level,
        transition,
        h_steps=2,
        baseline_min_count=1,
        candidate_min_count=1,
        ref_steps=8,
    )
    assert base2[4] == pytest.approx(base1[4])
    assert cand2[4] == pytest.approx(cand1[4])


def test_same_support_event_id_forgery_is_rejected():
    with pytest.raises(SupportMismatchError, match="supports differ"):
        paired_loss_summary(
            {"event-a": 1.0},
            {"event-a": 1.0, "forged-extra-event": 0.0},
        )


def test_canonical_event_id_binds_snapshot_timeframe_and_dimensions():
    event = canonical_event_id(WARMUP_START_MS + GRID_MS, 60, 60, 30)
    assert REQUIRED_SNAPSHOT in event
    assert "|1m|" in event
    assert "W=60" in event and "D=60" in event and "H=30" in event
    assert canonical_event_id(WARMUP_START_MS + GRID_MS, 120, 60, 30) != event


def test_placebo_prediction_does_not_read_unmatured_or_future_label_source():
    n = 9
    t_ms = WARMUP_START_MS + GRID_MS + np.arange(n, dtype=np.int64) * GRID_MS
    target = np.arange(n, dtype=np.float64)
    level = np.zeros(n, dtype=np.int16)
    transition = np.asarray([0, 1, 0, 1, 0, 1, 0, 1, 0], dtype=np.int16)

    kwargs = dict(
        i=6,
        replicate=7,
        t_ms=t_ms,
        target=target,
        level_state=level,
        transition_state=transition,
        w_min=60,
        d_min=60,
        h_min=30,  # h_steps=2, so source j must be <=4.
        ref_steps=6,
        candidate_min_count=1,
    )
    p1 = _placebo_candidate_prediction(**kwargs)

    changed = transition.copy()
    changed[5] = 2  # Unmatured source at T.
    changed[7:] = 2  # Strictly future records; keep evaluation state i=6 fixed.
    p2 = _placebo_candidate_prediction(
        **{**kwargs, "transition_state": changed}
    )
    assert p2 == pytest.approx(p1)


def test_single_magic_cell_or_single_wd_pair_cannot_promote():
    gates, selected = determine_promotion_gates([
        _all_true_cell(60, 60, 30),
    ])
    assert selected == []
    assert not fail_closed_gate_conjunction(gates, promotion_gate_contract())

    gates, selected = determine_promotion_gates([
        _all_true_cell(60, 60, 30),
        _all_true_cell(60, 60, 60),
    ])
    assert selected == []
    assert not fail_closed_gate_conjunction(gates, promotion_gate_contract())


def test_same_adjacent_h_pair_must_pass_on_second_wd_pair():
    cells = [
        _all_true_cell(60, 60, 30),
        _all_true_cell(60, 60, 60),
        _all_true_cell(120, 120, 30),
        _all_true_cell(120, 120, 60),
    ]
    gates, selected = determine_promotion_gates(cells)
    assert len(selected) == 4
    assert fail_closed_gate_conjunction(gates, promotion_gate_contract())


def test_year_instability_blocks_otherwise_qualifying_neighborhood():
    cells = [
        _all_true_cell(60, 60, 30),
        _all_true_cell(60, 60, 60),
        _all_true_cell(120, 120, 30),
        _all_true_cell(120, 120, 60, year_ok=False),
    ]
    gates, selected = determine_promotion_gates(cells)
    assert selected == []
    assert not fail_closed_gate_conjunction(gates, promotion_gate_contract())


def test_missing_mandatory_gate_input_is_non_promotion():
    contract = promotion_gate_contract()
    gates = {name: True for name in GATE_NAMES}
    del gates["placebo_separation"]
    assert not fail_closed_gate_conjunction(gates, contract)
