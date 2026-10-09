"""Design locks for the forecast prototype. No market probability is fit here."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from scripts.research.range_position_4h_forecast_prototype_v1 import constants as K
from scripts.research.range_position_4h_forecast_prototype_v1 import evaluate, support
from scripts.research.range_position_4h_forecast_prototype_v1.eligibility import phase_residue
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
    )
    assert result["implementation_ok"] is True
    assert result["probabilities_computed_on_market"] is False
    monday = _ms("2024-12-30T00:00:00")
    sunday = _ms("2024-12-29T23:00:00")
    _x, _y, admitted, ready, _names = evaluate.build_training_matrix(
        close_ms, x, y, segment, monday, ("BINANCE_2020_2024",),
    )
    assert sunday in admitted.tolist()
    assert _ms("2024-12-29T23:15:00") not in close_ms.tolist()
    assert int(ready.max()) <= monday
    matched = [row for row in result["folds"] if row["block_start_ms"] == monday]
    assert matched
    assert matched[0]["max_train_label_available_at_ms"] <= monday
    assert matched[0]["n_train"] == int(admitted.shape[0])


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


def test_a_second_census_rewrite_is_refused(monkeypatch):
    monkeypatch.setattr("sys.argv", ["support", "--rewrite-a1"])
    with pytest.raises(SystemExit, match="CENSUS_REWRITE_REFUSED"):
        support.main()
