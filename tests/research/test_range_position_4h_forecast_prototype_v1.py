"""Design locks for the forecast prototype. No market probability is fit here."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from scripts.research.range_position_4h_forecast_prototype_v1 import constants as K
from scripts.research.range_position_4h_forecast_prototype_v1 import evaluate, market, support
from scripts.research.range_position_4h_forecast_prototype_v1.eligibility import (
    local_returns,
    phase_residue,
    replication_eligible,
)
from scripts.research.range_position_4h_incremental_replication_v1.grid import features
from scripts.research.range_position_4h_forecast_prototype_v1.folds import assign_folds, label_available_at
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
    assert _sha(K.AMENDMENT_A1) == K.AMENDMENT_A1_SHA256
    assert _sha(K.SUPPORT) == K.SUPPORT_SHA256
    assert _sha(K.FOLDS) == K.FOLDS_SHA256
    assert _sha(K.ADAPTER_MANIFEST) == K.ADAPTER_MANIFEST_SHA256


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
    assert late["block_start"] == modern_first["block_start"] == "2024-12-30T00:00:00Z"
    support = json.loads((ROOT / K.SUPPORT).read_text(encoding="utf-8"))
    core_n = support["segments"]["BINANCE_2020_2024"]["n_labeled"]
    assert modern_first["n_train"] == core_n - late["n_test"] - modern_first["n_excluded_by_label_lag"]
    assert modern_first["max_train_label_available_at"] <= modern_first["block_start"]
    assert 0 <= modern_first["n_excluded_by_label_lag"] <= 3


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
    with pytest.raises(SystemExit, match="AWAITING_OWNER_GO"):
        evaluate.run_market()


def _ms(text: str) -> int:
    return int(np.datetime64(text).astype("datetime64[ms]").astype(np.int64))


def test_sunday_boundary_admits_2300_and_drops_the_later_quarter_hours():
    monday = _ms("2024-12-30T00:00:00")
    expected = {
        "2024-12-29T23:00:00": True,
        "2024-12-29T23:15:00": False,
        "2024-12-29T23:30:00": False,
        "2024-12-29T23:45:00": False,
    }
    stamps = np.array([_ms(text) for text in expected], dtype=np.int64)
    available = label_available_at(stamps)
    for text, stamp, ready in zip(expected, stamps, available):
        assert (int(ready) <= monday) is expected[text]
        assert int(ready) == int(stamp) + K.HORIZON * K.BAR_MS
    x = np.column_stack([
        np.linspace(-0.02, 0.02, 4),
        np.linspace(0.01, 0.04, 4),
        np.linspace(-0.01, 0.01, 4),
        np.linspace(-0.005, 0.005, 4),
        np.linspace(0.2, 0.8, 4),
    ])
    y = np.array([0.0, 1.0, 0.0, 1.0])
    segment = np.array(["BINANCE_2020_2024"] * 4)
    fitted_x, _fitted_y, admitted, admitted_ready, _names = evaluate.build_training_matrix(
        stamps, x, y, segment, monday, ("BINANCE_2020_2024",),
    )
    assert admitted.tolist() == [_ms("2024-12-29T23:00:00")]
    assert int(admitted_ready.max()) == monday
    assert fitted_x.shape == (1, 5)
    hourly = stamps[stamps % K.HOUR_MS == 0]
    assert hourly.tolist() == [_ms("2024-12-29T23:00:00")]
    hourly_x, _hourly_y, hourly_admitted, hourly_ready, _hourly_names = evaluate.build_training_matrix(
        hourly, x[:1], y[:1], segment[:1], monday, ("BINANCE_2020_2024",),
    )
    assert hourly_admitted.tolist() == [_ms("2024-12-29T23:00:00")]
    assert int(hourly_ready.max()) <= monday
    assert hourly_x.shape == (1, 5)
    with pytest.raises(ImplementationInvalid, match="LABEL_AVAILABILITY_VIOLATION"):
        evaluate.build_training_matrix(
            stamps, x, y, segment, monday, ("BINANCE_2020_2024",), admit_mask=np.ones(4, dtype=bool),
        )


def test_every_committed_block_has_the_label_available_before_monday():
    folds = json.loads((ROOT / K.FOLDS).read_text(encoding="utf-8"))
    assert folds["label_availability_rule"] == "T + HORIZON * BAR_MS <= block_start"
    assert folds["horizon"] == 12
    assert folds["bar_ms"] == 300000
    checked = 0
    for segment in folds["segments"].values():
        for cadence in ("primary_15m", "secondary_hourly"):
            block = segment[cadence]
            for row in block["test_folds"] + block["warmup_weeks"]:
                if not row["n_train"]:
                    continue
                assert row["max_train_label_available_at"] <= row["block_start"]
                assert 0 <= row["n_excluded_by_label_lag"] <= 3
                if cadence == "secondary_hourly":
                    assert row["n_excluded_by_label_lag"] == 0
                checked += 1
    proof = folds["label_availability"]
    assert proof["violations"] == 0
    assert proof["max_train_label_available_at_le_block_start"] is True
    assert proof["blocks_checked"] == checked
    assert proof["label_lag_ms"] == K.HORIZON * K.BAR_MS


def test_the_2025_block_trains_on_binance_rows_only():
    monday = _ms("2024-12-30T00:00:00")
    close_ms = np.array([
        _ms("2019-12-29T23:00:00"),
        _ms("2024-12-29T23:00:00"),
        _ms("2024-12-29T23:15:00"),
        _ms("2024-12-29T23:30:00"),
        _ms("2024-12-29T23:45:00"),
        _ms("2024-12-30T00:15:00"),
    ], dtype=np.int64)
    names = np.array([
        "BITMEX_2016_2019",
        "BINANCE_2020_2024",
        "BINANCE_2020_2024",
        "BINANCE_2020_2024",
        "BINANCE_2020_2024",
        "BINANCE_2025_2026",
    ])
    x = np.column_stack([
        np.linspace(-0.02, 0.02, 6),
        np.linspace(0.01, 0.03, 6),
        np.linspace(-0.01, 0.01, 6),
        np.linspace(-0.004, 0.004, 6),
        np.linspace(0.1, 0.9, 6),
    ])
    y = np.array([1.0, 0.0, 1.0, 0.0, 1.0, 0.0])
    allowed = evaluate.TRAIN_SOURCES["BINANCE_2025_2026"]
    assert "BITMEX_2016_2019" not in allowed
    _x, _y, admitted, ready, admitted_names = evaluate.build_training_matrix(
        close_ms, x, y, names, monday, allowed,
    )
    assert admitted.tolist() == [_ms("2024-12-29T23:00:00")]
    assert admitted_names.tolist() == ["BINANCE_2020_2024"]
    assert int(ready.max()) <= monday
    bitmex_and_sunday = np.array([True, True, False, False, False, False])
    with pytest.raises(ImplementationInvalid, match="TRAINING_SOURCE_VIOLATION"):
        evaluate.build_training_matrix(
            close_ms, x, y, names, monday, allowed, admit_mask=bitmex_and_sunday,
        )


def test_hourly_walk_forward_keeps_sunday_2300_and_drops_later_quarter_hours():
    rng = np.random.default_rng(4)
    origin = np.datetime64("2024-11-04T00:00:00")
    stamps = []
    for week in range(9):
        monday = origin + np.timedelta64(week * 7, "D")
        stamps.append(monday - np.timedelta64(1, "h"))
        for hour in range(4):
            stamps.append(monday + np.timedelta64(hour, "h"))
    close_ms = np.asarray(stamps, dtype="datetime64[ms]").astype(np.int64)
    assert np.all(close_ms % K.HOUR_MS == 0)
    n = int(close_ms.shape[0])
    position = rng.uniform(0.05, 0.95, size=n)
    x = np.column_stack([rng.normal(scale=0.01, size=(n, 4)), position])
    logit = 1.5 * (position - 0.5)
    y = (rng.random(n) < 1.0 / (1.0 + np.exp(-logit))).astype(np.float64)
    segment = np.array(["BINANCE_2020_2024"] * n)
    result = evaluate.evaluate_frame(
        [{
            "name": "BINANCE_2020_2024",
            "train_close_ms": close_ms,
            "train_y": y,
            "train_x": x,
            "train_segment": segment,
            "test_close_ms": close_ms,
            "test_y": y,
            "test_x": x,
        }],
        draws=K.BOOT_DRAWS,
        seed=0,
        min_rows=8,
        min_weeks=2,
        cadence="secondary_hourly",
        audit_rows=True,
    )
    assert result["implementation_ok"] is True
    assert result["diagnostic_only"] is True
    assert result["route"] is None
    assert result["probabilities_computed_on_market"] is False
    monday = _ms("2024-12-30T00:00:00")
    sunday = _ms("2024-12-29T23:00:00")
    matched = [row for row in result["folds"] if row["block_start_ms"] == monday]
    assert matched
    admitted = matched[0]["train_close_ms"]
    assert sunday in admitted.tolist()
    assert matched[0]["max_train_label_available_at_ms"] == monday
    assert np.all(matched[0]["train_label_available_at_ms"] <= monday)
    assert np.intersect1d(admitted, matched[0]["test_close_ms"]).size == 0


def test_walk_forward_keeps_bitmex_out_of_the_2025_training_matrix():
    rng = np.random.default_rng(3)
    binance_close, binance_x, binance_y = _series(6, 6, "2024-11-04T00:00:00", rng)
    bitmex_close = np.array([_ms("2019-06-03T00:00:00")], dtype=np.int64)
    bitmex_x = np.array([[0.01, 0.02, -0.01, 0.004, 0.2]])
    train_close = np.concatenate([bitmex_close, binance_close])
    train_x = np.vstack([bitmex_x, binance_x])
    train_y = np.concatenate([np.array([1.0]), binance_y])
    train_segment = np.array(["BITMEX_2016_2019"] + ["BINANCE_2020_2024"] * binance_close.shape[0])
    result = evaluate.evaluate_frame(
        [{
            "name": "BINANCE_2025_2026",
            "train_close_ms": train_close,
            "train_y": train_y,
            "train_x": train_x,
            "train_segment": train_segment,
            "test_close_ms": binance_close,
            "test_y": binance_y,
            "test_x": binance_x,
            "allowed_train_segments": ("BINANCE_2020_2024", "BINANCE_2025_2026"),
        }],
        draws=K.BOOT_DRAWS,
        seed=0,
        min_rows=12,
        min_weeks=2,
    )
    assert result["implementation_ok"] is True
    assert result["probabilities_computed_on_market"] is False
    for row in result["folds"]:
        assert row["train_segments"] == ["BINANCE_2020_2024"]
        assert row["max_train_label_available_at_ms"] <= row["block_start_ms"]


def _series(n_weeks: int, per_week: int, origin: str, rng: np.random.Generator):
    origin_ms = np.datetime64(origin)
    stamps = []
    for week in range(n_weeks):
        monday = origin_ms + np.timedelta64(week * 7, "D")
        for step in range(per_week):
            stamps.append(monday + np.timedelta64(15 * step, "m"))
    close_ms = np.asarray(stamps, dtype="datetime64[ms]").astype(np.int64)
    n = int(close_ms.shape[0])
    other = rng.normal(scale=0.01, size=(n, 4))
    position = rng.uniform(0.05, 0.95, size=n)
    x = np.column_stack([other, position])
    logit = -0.4 + 2.2 * (position - 0.5)
    y = (rng.random(n) < 1.0 / (1.0 + np.exp(-logit))).astype(np.float64)
    return close_ms, x, y


def test_walk_forward_on_synthetic_rows_stores_probabilities_and_obeys_the_lag():
    rng = np.random.default_rng(1)
    close_ms, x, y = _series(12, 8, "2020-01-06T00:00:00", rng)
    segment = np.array(["BINANCE_2020_2024"] * close_ms.shape[0])
    result = evaluate.evaluate_frame(
        [{
            "name": "BINANCE_2020_2024",
            "train_close_ms": close_ms,
            "train_y": y,
            "train_x": x,
            "train_segment": segment,
            "test_close_ms": close_ms,
            "test_y": y,
            "test_x": x,
        }],
        draws=K.BOOT_DRAWS,
        seed=0,
        min_rows=24,
        min_weeks=3,
    )
    assert result["implementation_ok"] is True
    assert result["market_series_loaded"] is False
    assert result["probabilities_computed_on_market"] is False
    assert result["regularization_added"] is False
    assert result["fallback_fit"] is False
    assert result["refit_inside_bootstrap"] is False
    assert result["route"] in {K.ROUTE_SUPPORTED, K.ROUTE_UNCERTAIN, K.ROUTE_NONE}
    assert result["bootstrap"]["valid_draws"] == K.BOOT_DRAWS
    stored = result["stored_probabilities"]
    assert np.all((stored["p_candidate"] > 0.0) & (stored["p_candidate"] < 1.0))
    assert brier(stored["y"], stored["p_candidate"]) == pytest.approx(result["pooled"]["brier_candidate"])
    assert log_loss(stored["y"], stored["p_candidate"]) == pytest.approx(result["pooled"]["logloss_candidate"])
    for row in result["folds"]:
        assert row["max_train_label_available_at_ms"] <= row["block_start_ms"]
        assert row["train_segments"] == ["BINANCE_2020_2024"]
    assert result["illustrative"]
    assert set(result["illustrative"][0]) >= {"p_at_0_1", "p_at_0_5", "p_at_0_9"}


def test_synthetic_failure_ends_invalid_without_a_fallback():
    rng = np.random.default_rng(2)
    close_ms, x, y = _series(8, 6, "2020-01-06T00:00:00", rng)
    y[:] = 0.0
    segment = np.array(["BITMEX_2016_2019"] * close_ms.shape[0])
    failed = evaluate.evaluate_frame(
        [{
            "name": "BITMEX_2016_2019",
            "train_close_ms": close_ms,
            "train_y": y,
            "train_x": x,
            "train_segment": segment,
            "test_close_ms": close_ms,
            "test_y": y,
            "test_x": x,
        }],
        draws=20,
        seed=0,
        min_rows=12,
        min_weeks=2,
    )
    assert failed["route"] == K.ROUTE_INVALID
    assert failed["fallback_fit"] is False
    assert failed["regularization_added"] is False
    assert failed["probabilities_computed_on_market"] is False
    assert "stored_probabilities" not in failed
    assert failed["reason"] in {"SINGULAR_HESSIAN", "LOGISTIC_DID_NOT_CONVERGE"}
    x[0, 0] = np.nan
    y[:] = (np.arange(y.shape[0]) % 2).astype(np.float64)
    nan_result = evaluate.evaluate_frame(
        [{
            "name": "BITMEX_2016_2019",
            "train_close_ms": close_ms,
            "train_y": y,
            "train_x": x,
            "train_segment": segment,
            "test_close_ms": close_ms,
            "test_y": y,
            "test_x": x,
        }],
        draws=20,
        seed=0,
        min_rows=12,
        min_weeks=2,
    )
    assert nan_result["route"] == K.ROUTE_INVALID
    assert nan_result["reason"] == "NON_FINITE_TRAINING_VALUE"


def test_a_repeated_bootstrap_block_repeats_its_rows_and_does_not_fit():
    groups = [np.array([0, 1]), np.array([2, 3, 4])]
    assert evaluate.resample_rows(groups, np.array([0, 0])).tolist() == [0, 1, 0, 1]
    source = (ROOT / "scripts/research/range_position_4h_forecast_prototype_v1/evaluate.py").read_text(encoding="utf-8")
    start = source.index("def _bootstrap_losses")
    end = source.index("def calibration_coefficients")
    assert "fit_logistic" not in source[start:end]
    assert "load_rows" not in source
    assert "load_binance_perp_5m" not in source


def test_pre_a1_census_hashes_stay_the_rewrite_guard():
    assert support.PRE_A1_SUPPORT_SHA256 == "8400e2f20abb79ea074ce2ea93614c1675987c7ef55282060b43c9c0e576abc4"
    assert support.PRE_A1_FOLDS_SHA256 == "ec7a94e1f5c24928c756eda5ead050beb4c67da5f233784bb3fe1b98550e1bb5"


def _features(close_ms: np.ndarray, rng: np.random.Generator):
    n = int(close_ms.shape[0])
    position = rng.uniform(0.05, 0.95, size=n)
    x = np.column_stack([rng.normal(scale=0.01, size=(n, 4)), position])
    logit = 1.4 * (position - 0.5)
    y = (rng.random(n) < 1.0 / (1.0 + np.exp(-logit))).astype(np.float64)
    return x, y


def _boundary_clock():
    origin = np.datetime64("2024-11-04T00:00:00")
    boundary = np.datetime64("2024-12-30T00:00:00")
    stamps = []
    for week in range(10):
        monday = origin + np.timedelta64(week * 7, "D")
        if monday == boundary:
            for minute in (23 * 60, 23 * 60 + 15, 23 * 60 + 30, 23 * 60 + 45):
                stamps.append(monday - np.timedelta64(1, "D") + np.timedelta64(minute, "m"))
        for step in range(8):
            stamps.append(monday + np.timedelta64(15 * step, "m"))
    return np.asarray(stamps, dtype="datetime64[ms]").astype(np.int64)


def _run(train_close, train_x, train_y, train_names, test_close, test_x, test_y, name, cadence, allowed=None):
    segment = {
        "name": name,
        "train_close_ms": train_close,
        "train_y": train_y,
        "train_x": train_x,
        "train_segment": train_names,
        "test_close_ms": test_close,
        "test_y": test_y,
        "test_x": test_x,
    }
    if allowed is not None:
        segment["allowed_train_segments"] = allowed
    return evaluate.evaluate_frame(
        [segment],
        draws=K.BOOT_DRAWS,
        seed=0,
        min_rows=8,
        min_weeks=2,
        cadence=cadence,
        audit_rows=True,
    )


def _fold_at(result, block_start_ms: int) -> dict:
    return next(row for row in result["folds"] if row["block_start_ms"] == block_start_ms)


def _coef(result, block_start_ms: int):
    fold = _fold_at(result, block_start_ms)
    for row in result["coefficients"]:
        if row["iso_year"] == fold["iso_year"] and row["iso_week"] == fold["iso_week"] and row["segment"] == fold["segment"]:
            return row
    raise AssertionError("missing coefficients")


def _block_probability(result, block_start_ms: int):
    fold = _fold_at(result, block_start_ms)
    stored = result["stored_probabilities"]
    mask = np.isin(stored["close_ms"], fold["test_close_ms"])
    return stored["p_candidate"][mask], stored["p_climatology"][mask]


@pytest.mark.parametrize("cadence", ["primary_15m", "secondary_hourly"])
def test_scorer_training_matrix_obeys_the_sunday_boundary(cadence):
    rng = np.random.default_rng(7)
    close_ms = _boundary_clock()
    x, y = _features(close_ms, rng)
    names = np.array(["BINANCE_2020_2024"] * close_ms.shape[0])
    monday = _ms("2024-12-30T00:00:00")
    quarters = [_ms(f"2024-12-29T{minute}:00") for minute in ("23:15", "23:30", "23:45")]
    sunday = _ms("2024-12-29T23:00:00")
    result = _run(close_ms, x, y, names, close_ms, x, y, "BINANCE_2020_2024", cadence)
    assert result["implementation_ok"] is True
    assert result["probabilities_computed_on_market"] is False
    assert result["cadence"] == cadence
    if cadence == "primary_15m":
        assert result["route_applies"] is True
        assert result["route"] in {K.ROUTE_SUPPORTED, K.ROUTE_UNCERTAIN, K.ROUTE_NONE}
    else:
        assert result["diagnostic_only"] is True
        assert result["route"] is None
    fold = _fold_at(result, monday)
    train = fold["train_close_ms"]
    assert sunday in train.tolist()
    for quarter in quarters:
        assert quarter not in train.tolist()
    assert fold["max_train_label_available_at_ms"] == monday
    assert np.all(fold["train_label_available_at_ms"] <= monday)
    assert np.all(train < monday)
    assert np.intersect1d(train, fold["test_close_ms"]).size == 0
    assert np.all(fold["test_close_ms"] >= monday)
    assert fold["climatology_rate"] == pytest.approx(float(fold["train_y"].mean()))
    assert fold["baseline_mean"] == pytest.approx(fold["train_x"][:, :4].mean(axis=0))
    assert fold["baseline_std"] == pytest.approx(fold["train_x"][:, :4].std(axis=0))
    assert fold["rp_mean"] == pytest.approx(float(fold["train_x"][:, 4].mean()))
    _candidate, climatology = _block_probability(result, monday)
    assert np.allclose(climatology, fold["climatology_rate"])
    if cadence == "secondary_hourly":
        assert np.all(train % K.HOUR_MS == 0)
        assert np.all(fold["test_close_ms"] % K.HOUR_MS == 0)
    previous = None
    for row in result["folds"]:
        if previous is not None:
            assert row["n_train"] >= previous["n_train"]
            assert np.all(np.isin(previous["train_close_ms"], row["train_close_ms"]))
        previous = row
    flipped_late = y.copy()
    flipped_late[np.isin(close_ms, quarters)] = 1.0 - flipped_late[np.isin(close_ms, quarters)]
    late = _run(close_ms, x, flipped_late, names, close_ms, x, flipped_late, "BINANCE_2020_2024", cadence)
    late_fold = _fold_at(late, monday)
    assert late_fold["climatology_rate"] == pytest.approx(fold["climatology_rate"])
    assert _coef(late, monday)["candidate"] == pytest.approx(_coef(result, monday)["candidate"])
    assert _block_probability(late, monday)[0] == pytest.approx(_block_probability(result, monday)[0])
    flipped_sunday = y.copy()
    flipped_sunday[close_ms == sunday] = 1.0 - flipped_sunday[close_ms == sunday]
    used = _run(close_ms, x, flipped_sunday, names, close_ms, x, flipped_sunday, "BINANCE_2020_2024", cadence)
    assert _fold_at(used, monday)["climatology_rate"] != pytest.approx(fold["climatology_rate"])
    perturbed = x.copy()
    target = int(fold["test_close_ms"][0])
    perturbed[np.flatnonzero(close_ms == target)[0], 0] += 50.0
    shifted = _run(close_ms, perturbed, y, names, close_ms, perturbed, y, "BINANCE_2020_2024", cadence)
    shifted_fold = _fold_at(shifted, monday)
    assert shifted_fold["baseline_mean"] == pytest.approx(fold["baseline_mean"])
    assert shifted_fold["climatology_rate"] == pytest.approx(fold["climatology_rate"])
    assert _coef(shifted, monday)["baseline"] == pytest.approx(_coef(result, monday)["baseline"])


@pytest.mark.parametrize("cadence", ["primary_15m", "secondary_hourly"])
def test_scorer_keeps_the_2025_block_on_binance_and_off_bitmex(cadence):
    rng = np.random.default_rng(8)
    close_ms = _boundary_clock()
    x, y = _features(close_ms, rng)
    monday = _ms("2024-12-30T00:00:00")
    bitmex_t = _ms("2019-06-03T00:00:00")
    train_close = np.concatenate([np.array([bitmex_t], dtype=np.int64), close_ms])
    train_x = np.vstack([np.array([[0.02, 0.01, -0.01, 0.003, 0.4]]), x])
    train_y = np.concatenate([np.array([0.0]), y])
    train_names = np.concatenate([
        np.array(["BITMEX_2016_2019"]),
        np.where(close_ms < monday, "BINANCE_2020_2024", "BINANCE_2025_2026"),
    ])
    test = close_ms >= monday
    allowed = ("BINANCE_2020_2024", "BINANCE_2025_2026")
    result = _run(
        train_close, train_x, train_y, train_names, close_ms[test], x[test], y[test],
        "BINANCE_2025_2026", cadence, allowed,
    )
    assert result["implementation_ok"] is True
    assert result["probabilities_computed_on_market"] is False
    fold = _fold_at(result, monday)
    assert fold["train_segments"] == ["BINANCE_2020_2024"]
    assert bitmex_t not in fold["train_close_ms"].tolist()
    assert _ms("2024-12-29T23:00:00") in fold["train_close_ms"].tolist()
    for minute in ("23:15", "23:30", "23:45"):
        assert _ms(f"2024-12-29T{minute}:00") not in fold["train_close_ms"].tolist()
    assert np.all(fold["train_close_ms"] < monday)
    assert np.all(fold["test_close_ms"] >= monday)
    assert np.intersect1d(fold["train_close_ms"], fold["test_close_ms"]).size == 0
    assert fold["max_train_label_available_at_ms"] == monday
    previous = None
    for row in result["folds"]:
        assert "BITMEX_2016_2019" not in row["train_segments"]
        if previous is not None:
            assert np.all(np.isin(previous["train_close_ms"], row["train_close_ms"]))
        previous = row
    train_y_flipped = train_y.copy()
    train_y_flipped[0] = 1.0
    flipped = _run(
        train_close, train_x, train_y_flipped, train_names, close_ms[test], x[test], y[test],
        "BINANCE_2025_2026", cadence, allowed,
    )
    assert _fold_at(flipped, monday)["climatology_rate"] == pytest.approx(fold["climatology_rate"])
    assert _block_probability(flipped, monday)[0] == pytest.approx(_block_probability(result, monday)[0])
    if cadence == "primary_15m":
        assert result["route_applies"] is True
    else:
        assert result["route"] is None


def test_an_unknown_cadence_is_invalid():
    rng = np.random.default_rng(9)
    close_ms, x, y = _series(6, 6, "2020-01-06T00:00:00", rng)
    names = np.array(["BINANCE_2020_2024"] * close_ms.shape[0])
    result = _run(close_ms, x, y, names, close_ms, x, y, "BINANCE_2020_2024", "daily")
    assert result["route"] == K.ROUTE_INVALID
    assert result["reason"] == "UNKNOWN_CADENCE"
    assert result["fallback_fit"] is False


def test_a_second_census_rewrite_is_refused(monkeypatch):
    monkeypatch.setattr("sys.argv", ["support", "--rewrite-a1"])
    with pytest.raises(SystemExit, match="CENSUS_REWRITE_REFUSED"):
        support.main()


def _price_grid(origin: int, n: int, hole: int | None = None) -> dict:
    opened = int(origin) + np.arange(n, dtype=np.int64) * K.BAR_MS
    close = 10000.0 + np.arange(n, dtype=np.float64) * 0.5
    high = close + 2.0
    low = close - 1.0
    if hole is not None:
        close = close.copy()
        high = high.copy()
        low = low.copy()
        close[hole] = np.nan
        high[hole] = np.nan
        low[hole] = np.nan
    return {"grid_open": opened, "high": high, "low": low, "close": close}


def _three_tables() -> dict:
    specs = {
        "BITMEX_2016_2019": _price_grid(K.BITMEX_END_MS - 120 * K.BAR_MS, 100),
        "BINANCE_2020_2024": _price_grid(K.CORE_START_MS, 90),
        "BINANCE_2025_2026": _price_grid(K.BINANCE_START_MS, 90),
    }
    tables = {}
    for name, grid in specs.items():
        mask = replication_eligible(
            grid["grid_open"], grid["high"], grid["low"], grid["close"], market.SURFACE_END[name],
        )
        tables[name] = market.adapt_segment(name, grid, mask)
    return tables


def test_three_synthetic_adapters_build_the_frame_without_scoring(monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("scorer")

    monkeypatch.setattr(evaluate, "evaluate_frame", boom)
    tables = _three_tables()
    core = tables["BINANCE_2020_2024"]
    grid = _price_grid(K.CORE_START_MS, 90)
    feat = features(grid["high"], grid["low"], grid["close"])
    ret_1h, ret_15m = local_returns(grid["close"])
    mask = core["labeled_mask"]
    expected = np.column_stack([
        feat["ret4"][mask], feat["rv4"][mask], ret_1h[mask], ret_15m[mask], feat["rp"][mask],
    ])
    assert np.array_equal(core["x"], expected)
    assert market.FEATURE_ORDER == K.CANDIDATE_FEATURES
    flat = _price_grid(K.CORE_START_MS, 90)
    flat["close"] = np.full(90, 10000.0)
    flat["high"] = flat["close"] + 2.0
    flat["low"] = flat["close"] - 1.0
    zeros = market.adapt_segment("BINANCE_2020_2024", flat)
    assert zeros["n_zero"] > 0
    assert zeros["close_ms"].size == 0
    segments, counts = market.validate_and_construct(tables)
    by_name = {segment["name"]: segment for segment in segments}
    assert set(by_name) == set(market.SEGMENT_ORDER)
    assert set(by_name["BITMEX_2016_2019"]["train_segment"]) == {"BITMEX_2016_2019"}
    assert set(by_name["BINANCE_2020_2024"]["train_segment"]) == {"BINANCE_2020_2024"}
    assert set(by_name["BINANCE_2025_2026"]["train_segment"]) == {"BINANCE_2020_2024", "BINANCE_2025_2026"}
    for segment in segments:
        assert "allowed_train_segments" not in segment
    stitched = _price_grid(K.CORE_START_MS - 30 * K.BAR_MS, 90)
    with pytest.raises(ImplementationInvalid, match="SEGMENT_CLOCK"):
        market.adapt_segment("BINANCE_2020_2024", stitched)
    with pytest.raises(ImplementationInvalid, match="COVERAGE_MISMATCH"):
        market.score_prepared(segments, counts, market.MarketExecution())
    assert counts["total_rows"] != K.EXPECTED_TOTAL_TEST_ROWS


@pytest.mark.parametrize("name,origin,n", [
    ("BITMEX_2016_2019", K.BITMEX_END_MS - 120 * K.BAR_MS, 100),
    ("BINANCE_2020_2024", K.CORE_START_MS, 90),
    ("BINANCE_2025_2026", K.BINANCE_START_MS, 90),
])
def test_each_synthetic_adapter_rejects_a_different_eligibility_mask(name, origin, n):
    grid = _price_grid(origin, n)
    mask = replication_eligible(
        grid["grid_open"], grid["high"], grid["low"], grid["close"], market.SURFACE_END[name],
    )
    table = market.adapt_segment(name, grid, mask)
    assert table["close_ms"].size > 0
    bad = mask.copy()
    bad[0] = not bool(bad[0])
    with pytest.raises(ImplementationInvalid, match="ELIGIBILITY_DIVERGED"):
        market.adapt_segment(name, grid, bad)


def test_a_mismatched_sha256_is_invalid(tmp_path):
    path = tmp_path / "series.jsonl"
    payload = b"not the pinned series"
    path.write_bytes(payload)
    with pytest.raises(ImplementationInvalid, match="HASH_MISMATCH"):
        market.require_digest(path, K.BITMEX_SHA256)
    market.require_digest(path, hashlib.sha256(payload).hexdigest())
    with pytest.raises(ImplementationInvalid, match="CORE_SNAPSHOT_MISMATCH"):
        market.assert_core_snapshot("0" * 64)
    market.assert_core_snapshot(K.CORE_SNAPSHOT)


def test_training_sources_cannot_be_replaced_from_market_input():
    tables = _three_tables()
    tables["BINANCE_2025_2026"]["allowed_train_segments"] = ("BITMEX_2016_2019",)
    with pytest.raises(ImplementationInvalid, match="TRAINING_SOURCE_OVERRIDE"):
        market.construct_segments(tables)
    with pytest.raises(ImplementationInvalid, match="TRAINING_SOURCE_OVERRIDE"):
        market.train_sources_for("BINANCE_2025_2026", {"BINANCE_2025_2026": ("BITMEX_2016_2019",)})
    with pytest.raises(ImplementationInvalid, match="TRAINING_SOURCE_OVERRIDE"):
        market.reject_overrides({"allowed_train_segments": ("BITMEX_2016_2019", "BINANCE_2020_2024")})
    clean = _three_tables()
    leaked = clean["BINANCE_2020_2024"]
    leaked["close_ms"] = leaked["close_ms"].copy()
    leaked["close_ms"][0] = K.BITMEX_END_MS - K.BAR_MS
    with pytest.raises(ImplementationInvalid, match="SEGMENT_CLOCK"):
        market.construct_segments(clean)
    assert market.train_sources_for("BINANCE_2025_2026") == ("BINANCE_2020_2024", "BINANCE_2025_2026")


def test_duplicate_timestamps_are_invalid():
    tables = _three_tables()
    bitmex = tables["BITMEX_2016_2019"]
    bitmex["close_ms"] = np.concatenate([bitmex["close_ms"], bitmex["close_ms"][:1]])
    bitmex["x"] = np.vstack([bitmex["x"], bitmex["x"][:1]])
    bitmex["y"] = np.concatenate([bitmex["y"], bitmex["y"][:1]])
    with pytest.raises(ImplementationInvalid, match="DUPLICATE_TIMESTAMP"):
        market.construct_segments(tables)


def test_a_missing_bar_stays_missing_and_a_non_finite_label_is_invalid():
    hole = 70
    grid = _price_grid(K.BINANCE_START_MS, 90, hole=hole)
    table = market.adapt_segment("BINANCE_2025_2026", grid)
    hole_t = int(grid["grid_open"][hole] + K.BAR_MS)
    assert np.isnan(grid["close"][hole])
    assert hole_t not in set(table["close_ms"].tolist())
    assert grid["close"][hole] != grid["close"][hole - 1]
    tables = _three_tables()
    tables["BITMEX_2016_2019"]["x"] = tables["BITMEX_2016_2019"]["x"].copy()
    tables["BITMEX_2016_2019"]["x"][0, 0] = np.inf
    with pytest.raises(ImplementationInvalid, match="NON_FINITE_LABELED_VALUE"):
        market.construct_segments(tables)


def test_fold_counts_must_match_the_pinned_coverage():
    market.assert_pinned_census_coverage()
    market.validate_coverage(market.expected_coverage())
    shifted = market.expected_coverage()
    shifted["BITMEX_2016_2019"] = {"test_rows": 113211, "test_weeks": 171}
    with pytest.raises(ImplementationInvalid, match="COVERAGE_MISMATCH"):
        market.validate_coverage(shifted)
    weeks = market.expected_coverage()
    weeks["BINANCE_2025_2026"] = {"test_rows": 60999, "test_weeks": 91}
    weeks["total_weeks"] = 504
    with pytest.raises(ImplementationInvalid, match="COVERAGE_MISMATCH"):
        market.validate_coverage(weeks)
    _segments, counts = market.validate_and_construct(_three_tables())
    with pytest.raises(ImplementationInvalid, match="COVERAGE_MISMATCH"):
        market.validate_coverage(counts)
    support_doc = json.loads((ROOT / K.SUPPORT).read_text(encoding="utf-8"))
    assert support_doc["segments"]["BITMEX_2016_2019"]["primary_test_rows"] == 113210
    assert support_doc["segments"]["BINANCE_2020_2024"]["primary_test_rows"] == 162084
    assert support_doc["segments"]["BINANCE_2025_2026"]["primary_test_rows"] == 60999
    assert K.EXPECTED_TOTAL_TEST_ROWS == 336293
    assert K.EXPECTED_TOTAL_TEST_WEEKS == 505


def test_frozen_parameters_cannot_be_overridden_on_the_market_path():
    market.reject_overrides(None)
    market.reject_overrides({})
    market.reject_overrides({"min_train_rows": 1000, "bootstrap_seed": K.BOOT_SEED, "horizon": 12, "bar_ms": 300000})
    for options in (
        {"min_train_rows": 10},
        {"min_train_weeks": 1},
        {"bootstrap_draws": 10},
        {"bootstrap_seed": 0},
        {"horizon": 11},
        {"bar_ms": 60_000},
        {"penalty": "l2"},
    ):
        with pytest.raises(ImplementationInvalid, match="FROZEN_PARAMETER_OVERRIDE"):
            market.reject_overrides(options)
    parsed = market.options_from_argv(["--bootstrap-seed", "1", "--min-train-rows", "1000"])
    with pytest.raises(ImplementationInvalid, match="FROZEN_PARAMETER_OVERRIDE"):
        market.reject_overrides(parsed)
    with pytest.raises(ImplementationInvalid, match="FROZEN_PARAMETER_OVERRIDE"):
        market.options_from_argv(["--C", "1"])
    market.assert_protocol_locked()


def test_the_guard_exits_before_prices_features_or_the_scorer(monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("market load")

    monkeypatch.setattr(support, "_bitmex_grid", boom)
    monkeypatch.setattr(support, "_core_grid", boom)
    monkeypatch.setattr(support, "_modern_grid", boom)
    monkeypatch.setattr(market, "options_from_argv", boom)
    monkeypatch.setattr(market, "begin_attempt", boom)
    monkeypatch.setattr(evaluate, "evaluate_frame", boom)
    monkeypatch.setattr("sys.argv", ["evaluate", "--bootstrap-seed", "0", "--min-train-rows", "1"])
    with pytest.raises(SystemExit, match="AWAITING_OWNER_GO"):
        market.load_pinned_grids()
    with pytest.raises(SystemExit, match="AWAITING_OWNER_GO"):
        market.execute_pinned_market_fit({"bootstrap_seed": 0})
    with pytest.raises(SystemExit, match="AWAITING_OWNER_GO"):
        evaluate.main()
    with pytest.raises(SystemExit, match="AWAITING_OWNER_GO"):
        evaluate.run_market()


def test_provenance_flags_follow_execution_not_the_caller():
    execution = market.MarketExecution()
    report = market.build_report(
        execution,
        {
            "route": K.ROUTE_INVALID,
            "implementation_ok": False,
            "reason": "NON_FINITE_TEST_VALUE",
            "pooled": {"brier_candidate": np.float64(0.25)},
        },
        market_series_loaded=True,
        probabilities_computed_on_market=True,
        model_metrics_computed=True,
        evidence_class="LIVE_VALIDATED",
    )
    assert report["market_series_loaded"] is False
    assert report["probabilities_computed_on_market"] is False
    assert report["model_metrics_computed"] is False
    assert report["market_fit_executed"] is False
    assert report["evidence_class"] == "RETROSPECTIVE_FORECAST_PROTOTYPE"
    assert report["claim_ceiling"] == "RETROSPECTIVE_FORECAST_PROTOTYPE"
    assert report["product_ready"] is False
    assert report["live_validated"] is False
    assert report["prospective"] is False
    assert report["route"] == K.ROUTE_INVALID
    assert report["reason"] == "NON_FINITE_TEST_VALUE"
    assert report["primary"]["pooled"]["brier_candidate"] == 0.25
    json.dumps(report)
    with pytest.raises(ImplementationInvalid, match="PROVENANCE_OVERRIDE"):
        execution.mark_loaded(object())
    with pytest.raises(ImplementationInvalid, match="PROVENANCE_OVERRIDE"):
        execution.mark_scored(market._SCORE_TOKEN)
    execution.mark_loaded(market._LOAD_TOKEN)
    loaded = market.build_report(execution)
    assert loaded["market_series_loaded"] is True
    assert loaded["probabilities_computed_on_market"] is False
    assert loaded["model_metrics_computed"] is False
    execution.mark_scored(market._SCORE_TOKEN)
    scored = market.build_report(execution, {"route": K.ROUTE_NONE, "implementation_ok": True})
    assert scored["probabilities_computed_on_market"] is True
    assert scored["model_metrics_computed"] is True
    assert scored["evidence_class"] == "RETROSPECTIVE_FORECAST_PROTOTYPE"
    fresh = evaluate.evaluate_frame([], draws=1, seed=0, min_rows=1, min_weeks=1)
    assert fresh["market_series_loaded"] is False
    assert fresh["probabilities_computed_on_market"] is False


def test_owner_go_false_does_not_run_a_market_fit(monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("market load")

    monkeypatch.setattr(evaluate, "evaluate_frame", boom)
    assert K.OWNER_GO is False
    with pytest.raises(SystemExit, match="AWAITING_OWNER_GO"):
        market.execute_pinned_market_fit()
    report = market.build_report(market.MarketExecution())
    assert report["market_fit_executed"] is False
    assert report["model_metrics_computed"] is False
    assert not (ROOT / "docs/research/RANGE_POSITION_4H_FORECAST_PROTOTYPE_V1_MARKET_RESULT.json").exists()
    manifest = json.loads((ROOT / K.ADAPTER_MANIFEST).read_text(encoding="utf-8"))
    assert manifest["evidence_class"] == "RETROSPECTIVE_FORECAST_PROTOTYPE"
    assert manifest["claim_ceiling"] == "RETROSPECTIVE_FORECAST_PROTOTYPE"
    assert manifest["owner_go"] is False
    assert manifest["market_fit_executed"] is False
    assert manifest["market_series_loaded"] is False
    assert manifest["probabilities_computed_on_market"] is False
    assert manifest["model_metrics_computed"] is False
    assert manifest["product_ready"] is False
    assert manifest["live_validated"] is False
    assert manifest["prospective"] is False
    assert manifest["expected_primary"]["total_test_rows"] == 336293
    assert manifest["expected_primary"]["total_test_weeks"] == 505
    assert manifest["sources"]["BITMEX_2016_2019"]["sha256"] == K.BITMEX_SHA256
    assert manifest["sources"]["BINANCE_2020_2024"]["snapshot"] == K.CORE_SNAPSHOT
    assert manifest["sources"]["BINANCE_2025_2026"]["sha256"] == K.BINANCE_SHA256
    assert manifest["amendment_a1_sha256"] == K.AMENDMENT_A1_SHA256


def test_amendment_a1_hash_is_pinned(tmp_path):
    market.assert_amendment_pinned()
    bad = tmp_path / "amendment.md"
    bad.write_text("changed\n", encoding="utf-8")
    with pytest.raises(ImplementationInvalid, match="AMENDMENT_HASH_MISMATCH"):
        market.assert_amendment_pinned(bad)


def _manual_row(close_ms: int) -> dict:
    return {
        "close_ms": np.array([close_ms], dtype=np.int64),
        "x": np.ones((1, 5), dtype=np.float64),
        "y": np.ones(1, dtype=np.float64),
    }


@pytest.mark.parametrize("name,surface_end,surface_start", [
    ("BITMEX_2016_2019", K.BITMEX_END_MS, None),
    ("BINANCE_2020_2024", K.CORE_END_MS, K.CORE_START_MS),
    ("BINANCE_2025_2026", K.BINANCE_END_MS, K.BINANCE_START_MS),
])
def test_segment_clock_uses_the_open_and_keeps_the_bar_that_closes_on_the_end(name, surface_end, surface_start):
    last_open = surface_end - K.BAR_MS
    kept = market.adapt_segment(name, _price_grid(last_open, 1))
    assert kept["name"] == name
    assert int(kept["close_ms"].size) == 0
    market.validate_labeled_table(name, _manual_row(surface_end))
    with pytest.raises(ImplementationInvalid, match="SEGMENT_CLOCK"):
        market.adapt_segment(name, _price_grid(surface_end, 1))
    with pytest.raises(ImplementationInvalid, match="SEGMENT_CLOCK"):
        market.validate_labeled_table(name, _manual_row(surface_end + K.BAR_MS))
    if surface_start is not None:
        market.adapt_segment(name, _price_grid(surface_start, 1))
        with pytest.raises(ImplementationInvalid, match="SEGMENT_CLOCK"):
            market.adapt_segment(name, _price_grid(surface_start - K.BAR_MS, 1))


def _fixture_tables() -> dict:
    rng = np.random.default_rng(1)
    origins = {
        "BITMEX_2016_2019": "2019-09-02T00:00:00",
        "BINANCE_2020_2024": "2020-01-06T00:00:00",
        "BINANCE_2025_2026": "2025-01-06T00:00:00",
    }
    tables = {}
    for name, origin in origins.items():
        close_ms, matrix, target = _series(12, 16, origin, rng)
        tables[name] = {"close_ms": close_ms, "x": matrix, "y": target, "name": name}
    return tables


def _watch_scorer(monkeypatch):
    calls = []
    real = evaluate.evaluate_frame

    def wrapped(*args, **kwargs):
        calls.append(kwargs.get("cadence"))
        return real(*args, **kwargs)

    monkeypatch.setattr(evaluate, "evaluate_frame", wrapped)
    return calls


def test_numpy_scorer_payload_survives_json(tmp_path):
    journal = tmp_path / "success"
    report = market.execute_fixture_sequence(
        _fixture_tables(), journal, draws=K.BOOT_DRAWS, seed=0, min_rows=8, min_weeks=2,
    )
    text = (journal / "RESULT.json").read_text(encoding="utf-8")
    loaded = json.loads(text)
    assert loaded["evidence_class"] == "RETROSPECTIVE_FORECAST_PROTOTYPE"
    assert loaded["market_series_loaded"] is False
    assert loaded["probabilities_computed_on_market"] is False
    assert loaded["implementation_ok"] is True
    assert loaded["hourly_diagnostic_ran"] is True
    assert loaded["hourly"]["diagnostic_only"] is True
    assert loaded["hourly"]["route"] is None
    pooled = loaded["primary"]["pooled"]
    for key in (
        "brier_climatology", "brier_baseline", "brier_candidate",
        "logloss_climatology", "logloss_baseline", "logloss_candidate",
        "delta_brier", "delta_logloss",
    ):
        assert isinstance(pooled[key], float)
    bootstrap = loaded["primary"]["bootstrap"]
    for key in ("brier_lo", "brier_hi", "logloss_lo", "logloss_hi"):
        assert isinstance(bootstrap[key], float)
    assert loaded["primary"]["auroc_candidate"] is not None
    assert isinstance(loaded["primary"]["calibration_slope"], float)
    assert loaded["primary"]["reliability"]
    assert loaded["primary"]["segment_losses"]
    assert loaded["primary"]["era"]
    stored = loaded["primary"]["stored_probabilities"]
    y = np.asarray(stored["y"], dtype=np.float64)
    p_clim = np.asarray(stored["p_climatology"], dtype=np.float64)
    p_base = np.asarray(stored["p_baseline"], dtype=np.float64)
    p_cand = np.asarray(stored["p_candidate"], dtype=np.float64)
    assert brier(y, p_clim) == pytest.approx(pooled["brier_climatology"])
    assert brier(y, p_base) == pytest.approx(pooled["brier_baseline"])
    assert brier(y, p_cand) == pytest.approx(pooled["brier_candidate"])
    assert log_loss(y, p_base) == pytest.approx(pooled["logloss_baseline"])
    assert log_loss(y, p_cand) == pytest.approx(pooled["logloss_candidate"])
    assert pooled["delta_brier"] == pytest.approx(pooled["brier_candidate"] - pooled["brier_baseline"])
    assert loaded["hashes"]["amendment_a1_sha256"] == K.AMENDMENT_A1_SHA256
    assert loaded["hashes"]["adapter_manifest_sha256"] == K.ADAPTER_MANIFEST_SHA256
    assert report["route"] == loaded["route"]
    artifact = Path("/opt/cursor/artifacts")
    artifact.mkdir(parents=True, exist_ok=True)
    (artifact / "synthetic_forecast_result.json").write_text(text, encoding="utf-8")


def test_fixture_sequence_persists_then_refuses_a_rerun(monkeypatch, tmp_path):
    calls = _watch_scorer(monkeypatch)
    journal = tmp_path / "sequence"
    report = market.execute_fixture_sequence(
        _fixture_tables(), journal, draws=K.BOOT_DRAWS, seed=0, min_rows=8, min_weeks=2,
    )
    assert calls == ["primary_15m", "secondary_hourly"]
    assert report["implementation_ok"] is True
    assert report["hourly_diagnostic_ran"] is True
    assert (journal / "ATTEMPT.json").is_file()
    assert json.loads((journal / "ATTEMPT.json").read_text(encoding="utf-8"))["status"] == "STARTED"
    with pytest.raises(SystemExit, match="REFUSING_RERUN"):
        market.execute_fixture_sequence(
            _fixture_tables(), journal, draws=K.BOOT_DRAWS, seed=0, min_rows=8, min_weeks=2,
        )
    assert calls == ["primary_15m", "secondary_hourly"]
    assert json.loads((journal / "RESULT.json").read_text(encoding="utf-8"))["route"] == report["route"]


def test_primary_invalid_is_persisted_and_hourly_does_not_run(monkeypatch, tmp_path):
    calls = _watch_scorer(monkeypatch)
    journal = tmp_path / "invalid"
    tables = _fixture_tables()
    for table in tables.values():
        table["x"] = np.ones_like(table["x"])
    report = market.execute_fixture_sequence(
        tables, journal, draws=K.BOOT_DRAWS, seed=0, min_rows=8, min_weeks=2,
    )
    assert calls == ["primary_15m"]
    assert report["route"] == K.ROUTE_INVALID
    assert report["implementation_ok"] is False
    assert report["reason"] == "SCALER_DEGENERATE"
    assert report["stopped_before_hourly"] is True
    assert report["hourly_diagnostic_ran"] is False
    assert "hourly" not in report
    stored = json.loads((journal / "RESULT.json").read_text(encoding="utf-8"))
    assert stored["route"] == K.ROUTE_INVALID
    assert stored["reason"] == "SCALER_DEGENERATE"
    assert stored["hourly_diagnostic_ran"] is False
    assert stored["market_fit_executed"] is False
    with pytest.raises(SystemExit, match="REFUSING_RERUN"):
        market.execute_fixture_sequence(
            _fixture_tables(), journal, draws=K.BOOT_DRAWS, seed=0, min_rows=8, min_weeks=2,
        )
    assert calls == ["primary_15m"]
    artifact = Path("/opt/cursor/artifacts")
    artifact.mkdir(parents=True, exist_ok=True)
    (artifact / "synthetic_forecast_primary_invalid.json").write_text(
        (journal / "RESULT.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )


def test_an_interrupted_attempt_refuses_without_reading_a_result(monkeypatch, tmp_path):
    def boom(*_args, **_kwargs):
        raise AssertionError("scorer")

    monkeypatch.setattr(evaluate, "evaluate_frame", boom)
    journal = tmp_path / "interrupted"
    journal.mkdir()
    (journal / "ATTEMPT.json").write_text("", encoding="utf-8")
    with pytest.raises(SystemExit, match="REFUSING_RERUN"):
        market.execute_fixture_sequence(
            _fixture_tables(), journal, draws=1, seed=0, min_rows=1, min_weeks=1,
        )
    assert not (journal / "RESULT.json").exists()
