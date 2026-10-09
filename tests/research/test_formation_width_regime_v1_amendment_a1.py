"""Synthetic checks for amendment A1. No market panel and no future association."""

from __future__ import annotations

import math

import numpy as np
import pytest

from scripts.research.formation_width_regime_v1 import amendment_a1 as A1
from scripts.research.formation_width_regime_v1 import constants as K
from scripts.research.formation_width_regime_v1 import evaluate
from scripts.research.formation_width_regime_v1.census import _path_complete
from scripts.research.opening_range_object_v1 import constants as PARENT

FORM = 48


def _endpoint(**kwargs):
    base = {
        "foundation_clears": False,
        "year_unstable": False,
        "incremental_formation_clears": False,
        "foundation_abs": 0.20,
        "lag_placebo_abs": 0.01,
    }
    base.update(kwargs)
    return base


def _both(**kwargs):
    return {"ACTIVITY": _endpoint(**kwargs), "DISPLACEMENT": _endpoint(**kwargs)}


def test_formation_returns_do_not_overlap_the_future_window():
    formation = A1.formation_return_pairs(FORM)
    future = A1.future_return_pairs(FORM)
    prev = A1.prev_hour_return_pairs(FORM)
    assert len(formation) == 12
    assert len(future) == 12
    assert len(prev) == 12
    assert A1.returns_are_disjoint(FORM)
    assert formation[-1] == (FORM + 10, FORM + 11)
    assert future[0] == (FORM + 11, FORM + 12)
    assert prev[-1] == (FORM - 2, FORM - 1)
    assert A1.formation_close_span(FORM) == (FORM - 1, 13)
    shared = {right for _, right in formation} & {left for left, _ in future}
    assert shared == {FORM + 11}


def test_log_return_values_use_only_the_declared_pairs():
    close = np.arange(1, 120, dtype=np.float64)
    got = A1.log_returns(close, A1.formation_return_pairs(FORM))
    expected = np.array([
        math.log(close[right] / close[left])
        for left, right in A1.formation_return_pairs(FORM)
    ])
    assert got == pytest.approx(expected)
    future = A1.log_returns(close, A1.future_return_pairs(FORM))
    assert future[0] == pytest.approx(math.log(close[FORM + 12] / close[FORM + 11]))
    assert A1.realized_variation(np.array([3.0, 4.0])) == pytest.approx(5.0)
    # The future return is not one of the formation returns.
    assert not np.any(np.isclose(got, future[0]))


def test_rv_formation_span_is_complete_only_when_the_boundary_close_is_positive():
    close = np.full(PARENT.BARS_PER_DAY, 100.0)
    start, count = A1.formation_close_span(0)
    assert _path_complete(close, start, count) is False
    close = np.full(2 * PARENT.BARS_PER_DAY, 100.0)
    form = PARENT.BARS_PER_DAY
    start, count = A1.formation_close_span(form)
    assert _path_complete(close, start, count) is True
    close[form - 1] = np.nan
    assert _path_complete(close, start, count) is False
    close[form - 1] = 100.0
    close[form + 5] = 0.0
    assert _path_complete(close, start, count) is False


def test_partial_spearman_residualizes_one_covariate():
    v = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    y = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    z = np.array([2.0, 1.0, 4.0, 3.0, 6.0, 5.0])
    same = A1.partial_spearman(v, y, z)
    assert same["degenerate"] is False
    assert same["rho"] == pytest.approx(1.0)
    assert same["covariate"] == "RV_FORMATION"
    collinear = A1.partial_spearman(v, y, v)
    assert collinear["degenerate"] is True
    assert collinear["rho"] is None
    opposite = A1.partial_spearman(v, v[::-1], z)
    assert opposite["rho"] == pytest.approx(-1.0)


def test_route_uses_rv_formation_and_ignores_prev_only_as_a_rejection():
    present = _both(
        foundation_clears=True,
        incremental_formation_clears=True,
    )
    assert A1.assign_route(present, information_limited=False)["route"] == A1.ROUTE_PRESENT
    redundant = _both(foundation_clears=True, incremental_formation_clears=False)
    assert A1.assign_route(redundant, information_limited=False)["route"] == A1.ROUTE_REDUNDANT
    none = _both(foundation_clears=False, incremental_formation_clears=True)
    assert A1.assign_route(none, information_limited=False)["route"] == A1.ROUTE_NO_DETECTABLE
    unstable = _both(foundation_clears=True, year_unstable=True, incremental_formation_clears=True)
    assert A1.assign_route(unstable, information_limited=False)["route"] == A1.ROUTE_UNSTABLE
    assert A1.assign_route(present, information_limited=True)["route"] == A1.ROUTE_INFORMATION_LIMITED
    with pytest.raises(RuntimeError):
        A1.assign_route(
            {"ACTIVITY": _endpoint(rv_prev_clears=True), "DISPLACEMENT": _endpoint()},
            information_limited=False,
        )


def test_rv_prev_clear_cannot_promote_or_demote_the_route():
    redundant = _both(foundation_clears=True, incremental_formation_clears=False)
    route = A1.assign_route(redundant, information_limited=False)
    assert route["route"] == A1.ROUTE_REDUNDANT
    assert route["incremental_covariate"] == "RV_FORMATION"
    assert route["rv_prev_role"] == A1.RV_PREV_ROLE
    present = _both(foundation_clears=True, incremental_formation_clears=True)
    assert A1.assign_route(present, information_limited=False)["route"] == A1.ROUTE_PRESENT


def test_lag_placebo_blocks_the_state_reading_without_changing_redundancy():
    blocked = _both(
        foundation_clears=True,
        incremental_formation_clears=True,
        foundation_abs=0.20,
        lag_placebo_abs=0.20,
    )
    got = A1.assign_route(blocked, information_limited=False)
    assert got["route"] == A1.ROUTE_NOT_SPECIFIC
    assert got["interpretable_as_current_state"] is False
    still_redundant = _both(
        foundation_clears=True,
        incremental_formation_clears=False,
        foundation_abs=0.20,
        lag_placebo_abs=0.90,
    )
    assert A1.assign_route(still_redundant, information_limited=False)["route"] == A1.ROUTE_REDUNDANT


def test_cell_clear_uses_the_frozen_scale():
    assert A1.cell_clears(0.10, True) is True
    assert A1.cell_clears(0.09, True) is False
    assert A1.cell_clears(0.20, False) is False
    assert K.PRACTICAL_ABS_RHO == 0.10
    assert K.BOOT_SEED == 20261107
    assert A1.DRAW_ORDER == (
        "FOUNDATION_ACTIVITY",
        "FOUNDATION_DISPLACEMENT",
        "INCREMENTAL_ACTIVITY_RV_FORMATION",
        "INCREMENTAL_DISPLACEMENT_RV_FORMATION",
    )


def test_outcome_evaluator_refuses_before_owner_go():
    with pytest.raises(SystemExit) as exc:
        evaluate.main()
    assert str(exc.value) == "REFUSING_OUTCOME_BEFORE_OWNER_GO"


def test_official_a1_support_is_outcome_blind_and_refuses_a_second_write():
    import hashlib
    import json
    from pathlib import Path

    payload = json.loads(
        Path("docs/research/FORMATION_WIDTH_REGIME_V1_AMENDMENT_A1_SUPPORT.json").read_text(encoding="utf-8")
    )
    digest = hashlib.sha256(
        Path("scripts/research/formation_width_regime_v1/amendment_a1.py").read_bytes()
    ).hexdigest()
    assert payload["outcome_read"] is False
    assert payload["future_association_read"] is False
    assert payload["information_authorizes_outcome"] is False
    assert payload["a1_analysis_sample"] == 1820
    assert payload["a1_iso_weeks"] == 262
    assert payload["sample_n_changed"] is False
    assert payload["counts"]["analysis_missing_rv_formation"] == 0
    assert payload["counts"]["rv_formation_complete"] == 1820
    assert payload["design_sha256"] == (
        "64407200533eec23abe63391f546ba83c3fae69c30d4a4f83a6d468300985ae6"
    )
    assert payload["code_digest"] == digest
    with pytest.raises(SystemExit) as exc:
        A1.write_support({"outcome_read": False, "future_association_read": False})
    assert str(exc.value) == K.REFUSAL_RERUN


def test_support_payload_rejects_a_future_association():
    with pytest.raises(RuntimeError):
        A1.assert_support_only({
            "outcome_read": False,
            "future_association_read": False,
            "activity_rho": 0.2,
        })
