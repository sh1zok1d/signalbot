"""Synthetic and identity tests for LEVEL_FLOW_RESPONSE_STATE_DISCOVERY_V1.

No market resolution rate by state is computed here.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from scripts.research.level_flow_response_state_discovery_v1 import constants as K
from scripts.research.level_flow_response_state_discovery_v1.analyze import y_of
from scripts.research.level_flow_response_state_discovery_v1.claim import conjunction, specificity_label
from scripts.research.level_flow_response_state_discovery_v1.cluster import (
    adjusted_rand,
    assign_nearest,
    describe_centroid,
    fit_kmeans,
    fit_scaler,
    select_k,
    state_name,
    transform,
)
from scripts.research.level_flow_response_state_discovery_v1.cohort import _annotate
from scripts.research.level_flow_response_state_discovery_v1.inference import (
    bh_adjust,
    columns_for,
    fit_rows,
    year_dummies,
)
from scripts.research.level_flow_response_state_discovery_v1.oi import FORBIDDEN_NAME, load_bound_oi
from scripts.research.level_positioning_flow_discovery_v1.features import flow_features, oi_features_from_prints
from scripts.research.level_touch_degradation_v1.outcomes import classify
from scripts.research.owner_cards_r03 import data as RD

BAR = 300_000


def test_core_and_oi_identity(monkeypatch):
    assert RD.btc_dataset_digest() == K.CORE_ZIP_LIST_SHA256
    opened = []
    real_open = Path.open

    def wrapped(self, *args, **kwargs):
        opened.append(self.name)
        if self.name == FORBIDDEN_NAME:
            raise AssertionError("funding opened")
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", wrapped)
    series, meta = load_bound_oi()
    assert meta["funding_jsonl_opened"] is False
    assert series.sha256 == K.OI_JSONL_SHA256
    assert series.git_snapshot_id == K.OI_SNAPSHOT_ID
    assert np.all(series.available_at_ms == series.period_start_ms + 300_000)
    assert int(series.period_start_ms[-1]) < K.SURFACE_END_MS
    assert K.EVENT_END_MS == K.SURFACE_END_MS
    assert not any(name.endswith("funding.jsonl") for name in opened)


def test_x5_orientation_and_touch_bar_excluded():
    n = 16
    open_ = np.full(n, 100.0)
    close = np.full(n, 100.0)
    close[11] = 110.0
    quote = np.full(n, 10.0)
    taker = np.full(n, 8.0)
    quote[12] = 999.0
    taker[12] = 0.0
    t0 = K.EVENT_START_MS - 12 * BAR
    decision = t0 + 12 * BAR
    up = flow_features(open_, close, quote, taker, t0, decision, 1)
    down = flow_features(open_, close, quote, taker, t0, decision, -1)
    progress_up = _annotate(up)["ORIENTED_PRICE_PROGRESS_60M"]
    progress_down = _annotate(down)["ORIENTED_PRICE_PROGRESS_60M"]
    assert progress_up == pytest.approx(np.log(110.0 / 100.0))
    assert progress_down == pytest.approx(-progress_up)
    assert up["ORIENTED_TAKER_IMBALANCE_60M"] == pytest.approx(0.6)
    assert down["ORIENTED_TAKER_IMBALANCE_60M"] == pytest.approx(-0.6)
    sell = flow_features(open_, close, quote, np.full(n, 2.0), t0, decision, 1)
    assert sell["ORIENTED_TAKER_IMBALANCE_60M"] < 0
    dead_quote = quote.copy()
    dead_taker = taker.copy()
    dead_quote[:12] = 0.0
    dead_taker[:12] = 0.0
    failed = flow_features(open_, close, dead_quote, dead_taker, t0, decision, 1)
    assert failed["ORIENTED_TAKER_IMBALANCE_60M"] is None
    assert failed["disp"] is not None
    prints = np.array([100, 100, 100, 100, 100, 100, 100, 100, 100, 101, 102, 103, 110], dtype=float)
    oi = oi_features_from_prints(prints)
    assert oi["OI_CHANGE_60M"] == pytest.approx(np.log(1.1))
    assert oi["OI_RECENT_ACCELERATION"] > 0


def test_robust_scaler_clip_and_zero_iqr():
    raw = np.column_stack([
        np.linspace(-2, 2, 51),
        np.linspace(0, 1, 51),
        np.linspace(-1, 1, 51),
        np.linspace(0.2, 0.8, 51),
        np.linspace(-0.5, 0.5, 51),
    ])
    raw[0, 0] = 100.0
    scaler = fit_scaler(raw)
    z, outside = transform(raw, scaler)
    assert np.all(np.abs(z) <= K.CLIP + 1e-12)
    assert int(outside[0]) >= 1
    flat = raw.copy()
    flat[:, 2] = 3.0
    with pytest.raises(ValueError, match="degenerate IQR"):
        fit_scaler(flat)


def test_k_selection_and_canonical_labels():
    chosen = select_k([
        {"k": 3, "passes_size": True, "silhouette": 0.40, "median_ari": 0.80},
        {"k": 4, "passes_size": True, "silhouette": 0.40, "median_ari": 0.90},
        {"k": 5, "passes_size": False, "silhouette": 0.80, "median_ari": 0.90},
        {"k": 6, "passes_size": True, "silhouette": 0.50, "median_ari": 0.70},
    ])
    assert chosen["k"] == 3
    assert select_k([
        {"k": 3, "passes_size": True, "silhouette": 0.2, "median_ari": 0.5},
    ]) is None
    rng = np.random.default_rng(7)
    a = rng.normal(loc=-3.0, scale=0.05, size=(40, 5))
    b = rng.normal(loc=3.0, scale=0.05, size=(40, 5))
    z = np.vstack([a, b, a + np.array([0, 0, 0, 0, 6.0])])
    # Force a 3-means fit and check determinism plus lex order.
    first = fit_kmeans(z, 3)
    second = fit_kmeans(z, 3)
    assert first is not None and second is not None
    assert np.array_equal(first["labels"], second["labels"])
    cents = first["centroids"]
    order = sorted(range(3), key=lambda i: tuple(float(v) for v in cents[i]))
    assert order == [0, 1, 2]
    again = assign_nearest(z, cents)
    assert np.array_equal(again, first["labels"])
    assert state_name(0) == "STATE_1"
    assert adjusted_rand(first["labels"], first["labels"]) == pytest.approx(1.0)
    text = describe_centroid([1.0, 0.0, -1.0, 0.1, -0.8])
    assert "absorption" not in text.lower()
    assert "expansion" in text


def test_outcomes_fdr_and_state_contrast():
    high = np.array([100.0, 120.0, 100.0])
    low = np.array([99.0, 100.0, 99.0])
    assert classify(high, low, 0, 1, 100.0, 101.0, 0.01, 1) == "BREAK"
    assert classify(np.array([100.0, 100.0, 100.0]), np.array([99.0, 99.5, 99.5]), 0, 1, 100.0, 101.0, 0.01, 1) == "NEITHER"
    assert y_of("BREAK", "RESOLVE_4H") == 1.0
    assert y_of("NEITHER", "RESOLVE_4H") == 0.0
    assert y_of("NEITHER", "BREAK_GIVEN_RESOLVED") is None
    assert y_of("AMBIGUOUS", "RESOLVE_4H") is None
    rng = np.random.default_rng(11)
    rows = []
    for i in range(240):
        state = "STATE_1" if i < 120 else "STATE_2"
        rows.append({
            "y": 1.0 if state == "STATE_1" else 0.0,
            "state": state,
            "family": ("DAY", "WEEK", "MONTH")[int(rng.integers(0, 3))],
            "support": float(rng.integers(0, 2)),
            "vol_tercile": int(rng.integers(0, 3)),
            "year": int(rng.integers(2021, 2025)),
            "time_block": int(rng.integers(0, 4)),
            "rel_volume": float(rng.normal(1.2, 0.3)),
            "cluster": int(rng.integers(0, 20)),
        })
    activity = {"mean": 1.2, "sd": 0.2}
    cell = fit_rows(rows, "STATE_1", activity, draws=0)
    assert cell["coef"] is not None and cell["coef"] > 0.05
    assert cell["n"] == 240
    assert "disp_z" not in cell["columns"]
    assert "OI_CHANGE_60M" not in cell["columns"]
    assert year_dummies(rows)[0] == "y2022"
    qs = bh_adjust([0.01, 0.04, None])
    assert qs[0] <= qs[1] <= qs[2]
    rule = conjunction(
        {"coef": 0.04, "q": 0.05, "ci95": (0.01, 0.07), "n": 200, "n_state": 120},
        [{"coef": 0.02, "n": 40}] * 5,
        [{"coef": 0.03, "n": 160}] * 5,
        [{"coef": 0.03, "n": 150, "dropped_share": 0.02}],
        0.8,
    )
    assert rule["pass"]
    stacked = {"delta": 0.05, "ci95": (0.02, 0.08), "beta_real": 0.06, "beta_pseudo": 0.01}
    assert specificity_label({"coef": 0.04}, stacked) == "LEVEL_STATE_CANDIDATE"
    cols = columns_for(rows, stacked=True)
    assert cols[:4] == ["intercept", "state", "real", "state_x_real"]
