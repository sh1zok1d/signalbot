"""Synthetic checks for the impulse-precursor discovery. No market series is loaded."""

from __future__ import annotations

import math

import numpy as np
import pytest

from scripts.research.impulse_precursors_discovery_v1 import constants as K
from scripts.research.impulse_precursors_discovery_v1.evaluate import calendar_fields, loss_block, walk_forward
from scripts.research.impulse_precursors_discovery_v1.frame import build_frame, geometric_impulse, label_available_at
from scripts.research.impulse_precursors_discovery_v1.model import ImplementationInvalid, assign_verdict, fit_logistic
from scripts.research.impulse_precursors_discovery_v1.states import cell_masks, score_cell
from scripts.research.level_race_forecast_v1.b0 import race_raw


def _series(n: int, seed: int = 7) -> dict:
    rng = np.random.default_rng(seed)
    open_ms = K.SURFACE_START_MS + np.arange(n, dtype=np.int64) * np.int64(K.BAR_MS)
    shock = rng.normal(0.0, 0.001, size=n)
    close = 100.0 * np.exp(np.cumsum(shock))
    high = close * (1.0 + np.abs(rng.normal(0.0, 0.0004, size=n)))
    low = close * (1.0 - np.abs(rng.normal(0.0, 0.0004, size=n)))
    quote = rng.uniform(1.0, 2.0, size=n)
    return {"open_ms": open_ms, "high": high, "low": low, "close": close, "quote": quote}


def test_design_hash_and_search_counts_are_pinned():
    from hashlib import sha256
    from pathlib import Path
    digest = sha256(Path(K.DESIGN).read_bytes()).hexdigest()
    assert digest == K.DESIGN_SHA256
    assert K.PRIMARY_K == 1.5
    assert K.DIAGNOSTIC_K == (1.0, 2.0)
    assert len(K.CANDIDATE_FEATURES) == 20
    assert "accel" not in K.CANDIDATE_FEATURES
    frame = build_frame(_series(900, seed=11))
    cells = cell_masks(frame)
    assert len(cells) == 70
    assert sum(cell["cell"].startswith("joint|") for cell in cells) == 6


def test_geometric_probability_matches_existing_race_and_is_constant():
    sigma = 0.001
    close = 100.0
    sigma_4h = sigma * math.sqrt(48)
    upper = close * math.exp(K.PRIMARY_K * sigma_4h)
    lower = close * math.exp(-K.PRIMARY_K * sigma_4h)
    p_up, p_down, _neither = race_raw(close, upper, lower, sigma, 48)
    assert geometric_impulse(close, sigma, K.PRIMARY_K) == pytest.approx(p_up + p_down)
    assert geometric_impulse(50_000.0, 0.004, K.PRIMARY_K) == pytest.approx(p_up + p_down, abs=1e-10)


def test_barrier_order_gap_and_lookahead():
    bars = _series(420, seed=3)
    frame = build_frame(bars)
    # Both indexes close on the 15m grid (index % 3 == 2). The anchor's 4h path ends at i.
    i = 338
    anchor_i = 290
    decision = int(bars["open_ms"][i] + K.BAR_MS)
    anchor = int(bars["open_ms"][anchor_i] + K.BAR_MS)
    assert decision in set(frame["close_ms"].tolist())
    row = np.flatnonzero(frame["close_ms"] == decision)[0]
    arow = np.flatnonzero(frame["close_ms"] == anchor)[0]
    mutated = {key: np.array(value, copy=True) for key, value in bars.items()}
    level = float(mutated["close"][i])
    mutated["close"][i + 1:i + 49] = level
    mutated["high"][i + 1:i + 49] = level * 1.0001
    mutated["low"][i + 1:i + 49] = level * 0.9999
    mutated["high"][i + 10] = level * 2.0
    mutated["low"][i + 10] = level * 0.5
    changed = build_frame(mutated)
    assert int(bars["open_ms"][i] + K.BAR_MS) not in set(changed["close_ms"].tolist())
    assert changed["counts"]["ambiguous"] >= 1
    other = np.flatnonzero(changed["close_ms"] == anchor)[0]
    assert np.allclose(frame["features"][arow], changed["features"][other])
    quiet = {key: np.array(value, copy=True) for key, value in bars.items()}
    quiet["high"][i + 1:i + 49] = quiet["close"][i] * 1.0001
    quiet["low"][i + 1:i + 49] = quiet["close"][i] * 0.9999
    quiet["close"][i + 1:i + 49] = quiet["close"][i]
    neither = build_frame(quiet)
    nrow = np.flatnonzero(neither["close_ms"] == int(bars["open_ms"][i] + K.BAR_MS))
    assert nrow.size == 1
    assert neither["y"][nrow[0]] == 0.0
    gapped = {key: np.array(value, copy=True) for key, value in bars.items()}
    gapped["open_ms"][i + 5] += np.int64(K.BAR_MS)
    gapped_frame = build_frame(gapped)
    assert int(bars["open_ms"][i] + K.BAR_MS) not in set(gapped_frame["close_ms"].tolist())
    past = {key: np.array(value, copy=True) for key, value in bars.items()}
    past["close"][i - 3] *= 1.05
    past["high"][i - 3] = max(past["high"][i - 3], past["close"][i - 3])
    past["low"][i - 3] = min(past["low"][i - 3], past["close"][i - 3])
    shifted = build_frame(past)
    srow = np.flatnonzero(shifted["close_ms"] == int(bars["open_ms"][i] + K.BAR_MS))[0]
    assert not np.allclose(frame["features"][row], shifted["features"][srow])


def _quiet_future(bars: dict, i: int) -> dict:
    out = {key: np.array(value, copy=True) for key, value in bars.items()}
    level = float(out["close"][i])
    out["high"][i + 1:i + 49] = level * 1.0001
    out["low"][i + 1:i + 49] = level * 0.9999
    out["close"][i + 1:i + 49] = level
    return out


def test_up_and_down_first_are_distinct():
    bars = _series(420, seed=5)
    i = 320
    level = float(bars["close"][i])
    lifted = _quiet_future(bars, i)
    lifted["high"][i + 4] = level * 1.5
    lifted["low"][i + 4] = level * 0.999
    up_frame = build_frame(lifted)
    row = np.flatnonzero(up_frame["close_ms"] == int(bars["open_ms"][i] + K.BAR_MS))[0]
    assert up_frame["direction"][row] == 1
    dropped = _quiet_future(bars, i)
    dropped["low"][i + 4] = level * 0.5
    dropped["high"][i + 4] = level * 1.001
    down_frame = build_frame(dropped)
    drow = np.flatnonzero(down_frame["close_ms"] == int(bars["open_ms"][i] + K.BAR_MS))[0]
    assert down_frame["direction"][drow] == -1


def test_label_is_available_only_after_the_four_hour_window():
    monday = np.int64(1_578_268_800_000)  # 2020-01-06T00:00:00Z
    admitted = monday - np.int64(K.HORIZON_BARS) * np.int64(K.BAR_MS)
    excluded = admitted + np.int64(K.DECISION_MS)
    available = label_available_at(np.array([admitted, excluded]))
    assert int(available[0]) == int(monday)
    assert int(available[1]) > int(monday)
    fields = calendar_fields(np.array([admitted, excluded, monday]))
    assert fields["monday_ms"][2] == monday


def test_walk_forward_does_not_train_on_an_unresolved_label():
    bars = _series(20_000, seed=9)
    frame = build_frame(bars)
    fitted = walk_forward(frame, min_rows=80, min_weeks=2)
    scored = fitted["scored"]
    assert int(scored.sum()) > 100
    y = frame["y"][scored]
    block = loss_block(y, fitted["p_b0"][scored], fitted["p_b1"][scored], fitted["p_candidate"][scored], frame["p_geom"][scored])
    assert block["n"] == int(scored.sum())
    assert math.isfinite(block["delta_brier"])
    for fold in fitted["folds"]:
        assert fold["n_train"] >= 80
        assert fold["n_train_weeks"] >= 2


def test_verdict_rules_do_not_read_auroc_or_diagnostic_k():
    promising = assign_verdict(-0.01, -0.01, -0.001, -0.001, 0.9, -0.01, -0.002, 2000, True)
    weak = assign_verdict(-0.01, -0.01, 0.001, -0.001, 0.9, -0.01, -0.002, 2000, True)
    none = assign_verdict(0.01, -0.01, -0.001, -0.001, 0.9, -0.01, -0.002, 2000, True)
    invalid = assign_verdict(-0.01, -0.01, -0.001, -0.001, 0.9, -0.01, -0.002, 10, True)
    assert promising == K.ROUTE_PROMISING
    assert weak == K.ROUTE_WEAK
    assert none == K.ROUTE_NO
    assert invalid == K.ROUTE_INVALID
    assert score_cell(0.02, [{"n": 200, "delta": 0.01}, {"n": 200, "delta": 0.01}, {"n": 200, "delta": 0.01}, {"n": 200, "delta": -0.01}], 1000) == pytest.approx(0.015)
    assert score_cell(0.02, [{"n": 200, "delta": 0.01}], 1000) == 0.0


def test_singular_design_is_invalid_without_a_fallback():
    x = np.column_stack([np.ones(40), np.ones(40)])
    y = np.array([0.0, 1.0] * 20)
    with pytest.raises(ImplementationInvalid):
        fit_logistic(x, y)
