"""Design locks for the forecast prototype. No market probability is fit here."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from scripts.research.range_position_4h_forecast_prototype_v1 import constants as K
from scripts.research.range_position_4h_forecast_prototype_v1 import evaluate
from scripts.research.range_position_4h_forecast_prototype_v1.eligibility import phase_residue
from scripts.research.range_position_4h_forecast_prototype_v1.folds import assign_folds
from scripts.research.range_position_4h_forecast_prototype_v1.model import (
    ImplementationInvalid,
    apply_scaler,
    assign_route,
    brier,
    fit_logistic,
    fit_scaler,
    log_loss,
    predict,
)

ROOT = Path(__file__).resolve().parents[2]


def _sha(path: str) -> str:
    digest = hashlib.sha256()
    with (ROOT / path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_frozen_files_match_the_pinned_hashes():
    assert _sha(K.DESIGN) == K.DESIGN_SHA256
    assert _sha(K.DESIGN_JSON) == K.DESIGN_JSON_SHA256
    assert _sha(K.SUPPORT) == K.SUPPORT_SHA256
    assert _sha(K.FOLDS) == K.FOLDS_SHA256


def test_design_json_matches_the_code_bounds():
    doc = json.loads((ROOT / K.DESIGN_JSON).read_text(encoding="utf-8"))
    assert doc["penalty"] == "none"
    assert doc["max_iterations"] == K.MAX_ITERATIONS
    assert doc["gradient_tolerance"] == K.GRADIENT_TOLERANCE
    assert doc["bootstrap_seed"] == K.BOOT_SEED
    assert doc["bootstrap_refit"] is False
    assert doc["min_train_rows"] == K.MIN_TRAIN_ROWS
    assert doc["min_train_weeks"] == K.MIN_TRAIN_WEEKS
    assert doc["venue_dummy"] is False
    assert doc["grids_stitched"] is False
    assert doc["e1_objects_requested"] is False
    assert doc["model_metrics_authorized"] is False
    assert doc["baseline_features"] == list(K.BASELINE_FEATURES)


def test_census_has_no_model_metric_and_matches_the_replication_masks():
    support = json.loads((ROOT / K.SUPPORT).read_text(encoding="utf-8"))
    assert support["model_metrics_computed"] is False
    assert support["probabilities_computed"] is False
    assert support["coefficients_computed"] is False
    assert support["p_up_computed"] is False
    assert support["brier_computed"] is False
    assert support["logloss_computed"] is False
    assert support["segments"]["BITMEX_2016_2019"]["n_feature_eligible"] == 127303
    assert support["segments"]["BINANCE_2025_2026"]["n_feature_eligible"] == 61016
    assert support["segments"]["BITMEX_2016_2019"]["first_labeled_t"] == "2016-05-13T16:00:00Z"
    assert support["segments"]["BINANCE_2020_2024"]["first_labeled_t"] == "2020-01-01T04:15:00Z"
    assert support["segments"]["BINANCE_2025_2026"]["first_labeled_t"] == "2025-01-01T04:15:00Z"
    folds = json.loads((ROOT / K.FOLDS).read_text(encoding="utf-8"))
    assert folds["model_metrics_computed"] is False
    for segment in folds["segments"].values():
        for row in segment["primary_15m"]["test_folds"]:
            assert row["n_train"] >= K.MIN_TRAIN_ROWS
            assert row["n_train_weeks"] >= K.MIN_TRAIN_WEEKS


def test_shared_monday_excludes_the_late_2024_anchors():
    folds = json.loads((ROOT / K.FOLDS).read_text(encoding="utf-8"))
    core_folds = folds["segments"]["BINANCE_2020_2024"]["primary_15m"]["test_folds"]
    modern_first = folds["segments"]["BINANCE_2025_2026"]["primary_15m"]["test_folds"][0]
    late = core_folds[-1]
    assert late["block_start"] == modern_first["block_start"]
    support = json.loads((ROOT / K.SUPPORT).read_text(encoding="utf-8"))
    core_n = support["segments"]["BINANCE_2020_2024"]["n_labeled"]
    assert modern_first["n_train"] == core_n - late["n_test"]


def test_expanding_week_never_trains_on_its_own_block():
    start = np.datetime64("2020-01-06T00:00:00")
    stamps = []
    for week in range(30):
        monday = start + np.timedelta64(week * 7, "D")
        for step in range(4):
            stamps.append(monday + np.timedelta64(step * 15, "m"))
    close_ms = np.asarray(stamps, dtype="datetime64[ms]").astype(np.int64)
    schedule = assign_folds(close_ms, min_rows=8, min_weeks=4)
    assert schedule["n_test_weeks"] > 0
    for row in schedule["test_folds"]:
        assert row["n_train"] < close_ms.size
        assert row["block_start"].endswith("T00:00:00Z")


def test_phase_residue_is_a_fifteen_minute_close():
    opens = np.arange(0, 12, dtype=np.int64) * K.BAR_MS + K.PARENT_EPOCH_MS
    mask = phase_residue(opens)
    closes = opens[mask] + K.BAR_MS
    assert np.all(closes % 900_000 == 0)
    assert np.any(mask)


def test_scaler_uses_only_the_training_rows():
    train = np.array([[0.0, 1.0], [2.0, 3.0]])
    future = np.array([[100.0, -100.0]])
    mu, sd = fit_scaler(train)
    scaled_future = apply_scaler(future, mu, sd)
    mu_leaky, _ = fit_scaler(np.vstack([train, future]))
    assert not np.allclose(mu, mu_leaky)
    assert scaled_future.shape == (1, 2)


def test_unpenalized_logistic_recovers_a_positive_direction_on_synthetic_rows():
    rng = np.random.default_rng(0)
    x = rng.normal(size=(600, 2))
    truth = np.array([0.3, 1.1])
    latent = -0.2 + x @ truth
    prob = 1.0 / (1.0 + np.exp(-latent))
    y = (rng.random(600) < prob).astype(np.float64)
    mu, sd = fit_scaler(x)
    beta = fit_logistic(apply_scaler(x, mu, sd), y)
    assert beta.shape == (3,)
    assert beta[2] > 0.0
    pred = predict(apply_scaler(x, mu, sd), beta)
    assert np.all((pred > 0.0) & (pred < 1.0))
    assert brier(y, pred) < brier(y, np.full(y.shape, y.mean()))
    assert np.isfinite(log_loss(y, pred))


def test_a_zero_scale_is_invalid():
    with pytest.raises(ImplementationInvalid):
        fit_scaler(np.ones((5, 1)))


def test_routes_follow_the_frozen_table():
    assert assign_route(-0.01, -0.01, -0.001, 0.8, 2000, True) == K.ROUTE_SUPPORTED
    assert assign_route(-0.01, -0.01, 0.001, 0.8, 2000, True) == K.ROUTE_UNCERTAIN
    assert assign_route(-0.01, -0.01, -0.001, -0.2, 2000, True) == K.ROUTE_UNCERTAIN
    assert assign_route(0.01, -0.01, -0.001, 0.8, 2000, True) == K.ROUTE_NONE
    assert assign_route(-0.01, 0.01, -0.001, 0.8, 2000, True) == K.ROUTE_NONE
    assert assign_route(-0.01, -0.01, -0.001, 0.8, 1899, True) == K.ROUTE_INVALID
    assert assign_route(-0.01, -0.01, -0.001, 0.8, 2000, False) == K.ROUTE_INVALID


def test_the_market_fit_waits_for_the_owner():
    assert K.OWNER_GO is False
    with pytest.raises(SystemExit, match="AWAITING_OWNER_GO"):
        evaluate.main()
