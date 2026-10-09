"""Synthetic checks for the predictive-value design. No market panel is loaded."""

from __future__ import annotations

import datetime as dt
import hashlib
from pathlib import Path

import numpy as np

from scripts.research.formation_width_incremental_predictive_value_v1 import constants as K
from scripts.research.formation_width_incremental_predictive_value_v1 import model


ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / "docs" / "research" / "FORMATION_WIDTH_INCREMENTAL_PREDICTIVE_VALUE_V1_DESIGN.md"
UTC = dt.timezone.utc


def test_design_hash_pin():
    digest = hashlib.sha256(DESIGN.read_bytes()).hexdigest()
    assert digest == K.DESIGN_SHA256


def test_folds_and_seeds_are_the_frozen_ones():
    assert K.TEST_FOLDS == (
        ("2021-01-01", "2022-01-01"),
        ("2022-01-01", "2023-01-01"),
        ("2023-01-01", "2024-01-01"),
        ("2024-01-01", "2025-01-01"),
    )
    assert K.BINANCE_SEED == 20261110
    assert K.BYBIT_SEED == 20261111
    assert K.BOOT_DRAWS == 2000
    assert K.QUANTILE_LO == 0.025
    assert K.QUANTILE_HI == 0.975
    assert K.HISTORICAL_PRACTICAL_RHO_APPLIED is False
    assert K.BINANCE_EXPECTED_N == 1820
    assert K.BYBIT_EXPECTED_N == 1613


def test_training_midranks_are_not_the_insertion_map():
    train = np.asarray([1.0, 2.0, 2.0, 4.0], dtype=np.float64)
    mid = model.train_rank_scores(train)
    insertion = model.insertion_rank_scores(train)
    assert not np.allclose(mid, insertion)
    assert np.allclose(mid * 5.0, [1.0, 2.5, 2.5, 4.0])


def test_test_score_ignores_other_test_points():
    train = np.asarray([1.0, 2.0, 4.0, 8.0], dtype=np.float64)
    first = model.apply_train_rank_scores(train, np.asarray([3.0, 100.0]))
    second = model.apply_train_rank_scores(train, np.asarray([3.0, -100.0]))
    assert first[0] == second[0]
    assert first[1] == 1.0
    below = model.apply_train_rank_scores(train, np.asarray([-1.0]))
    assert below[0] == 1.0 / 5.0


def test_baseline_and_candidate_share_the_activity_score():
    stamps = _daily_stamps("2020-01-01", "2024-12-31")
    rng = np.random.default_rng(11)
    width = rng.uniform(0.2, 0.8, size=len(stamps))
    rv = rng.uniform(0.2, 0.8, size=len(stamps))
    activity = width.copy()
    scored = model.evaluate_surface(
        stamps, rv, width, activity, _weeks(stamps), venue_start="2020-01-01", seed=7, draws=50,
    )
    assert scored["delta_mse"] > 0.0
    assert scored["mse_candidate"] < scored["mse_baseline"]
    assert all(fold["n_test"] >= K.MIN_TEST for fold in scored["folds"])
    assert scored["folds"][0]["n_train"] < scored["folds"][-1]["n_train"]


def test_constant_paired_loss_interval_is_the_point():
    differences = np.full(70, 0.02, dtype=np.float64)
    weeks = [(2021, index // 7) for index in range(70)]
    samples = model.block_bootstrap_means(differences, weeks, draws=40, seed=3)
    assert np.allclose(samples, 0.02)
    interval = model._interval(samples)
    assert np.isclose(interval["lo"], 0.02)
    assert np.isclose(interval["hi"], 0.02)


def test_larger_weeks_keep_their_weight():
    differences = np.asarray([0.0, 0.0, 0.0, 1.0], dtype=np.float64)
    weeks = [(2021, 1), (2021, 1), (2021, 1), (2021, 2)]
    samples = model.block_bootstrap_means(differences, weeks, draws=1, seed=0)
    assert samples.shape == (1,)
    assert 0.0 <= float(samples[0]) <= 1.0


def test_year_2020_is_train_only():
    stamps = _daily_stamps("2020-01-01", "2024-12-31")
    masks = model.fold_masks(stamps, "2020-04-01")
    test_ids = np.concatenate([test for _train, test, _start, _end in masks])
    assert stamps[test_ids].min() >= model.day_ms("2021-01-01")
    assert masks[0][0].size < masks[-1][0].size
    first_train = stamps[masks[0][0]]
    assert first_train.min() >= model.day_ms("2020-04-01")
    assert first_train.max() < model.day_ms("2021-01-01")


def test_interpretation_labels_are_frozen():
    def venue(point, lo, hi):
        return {"delta_mse": point, "interval": {"lo": lo, "hi": hi, "interpretable": lo is not None}}

    both = model.interpret(venue(0.02, 0.01, 0.03), venue(0.01, 0.005, 0.02))
    assert both["code"] == model.CODE_BOTH_POSITIVE
    assert both["future_validation_decided"] is False
    negative = model.interpret(venue(-0.02, -0.03, -0.01), venue(-0.01, -0.02, -0.001))
    assert negative["code"] == model.CODE_BOTH_NEGATIVE
    mixed = model.interpret(venue(0.02, -0.01, 0.03), venue(0.01, 0.005, 0.02))
    assert mixed["code"] == model.CODE_POINTS_POSITIVE
    quiet = model.interpret(venue(-0.02, -0.03, 0.01), venue(-0.01, -0.02, 0.001))
    assert quiet["code"] == model.CODE_POINTS_NOT_POSITIVE
    disagree = model.interpret(venue(0.02, 0.01, 0.03), venue(-0.01, -0.02, -0.001))
    assert disagree["code"] == model.CODE_DISAGREE
    blind = model.interpret(venue(0.02, None, None), venue(0.01, 0.0, 0.2))
    assert blind["code"] == model.CODE_NOT_INTERPRETABLE


def test_scoring_source_does_not_apply_the_historical_bar():
    import sys

    source = (ROOT / "scripts/research/formation_width_incremental_predictive_value_v1/model.py").read_text()
    assert "HISTORICAL_PRACTICAL_RHO" not in source
    assert "0.10" not in source
    evaluator = (ROOT / "scripts/research/formation_width_incremental_predictive_value_v1/evaluate.py").read_text()
    assert "def main" in evaluator
    assert "formation_width_incremental_predictive_value_v1.evaluate" not in sys.modules


def _daily_stamps(start: str, end: str) -> np.ndarray:
    left = dt.date.fromisoformat(start)
    right = dt.date.fromisoformat(end)
    stamps = []
    day = left
    while day <= right:
        stamp = dt.datetime(day.year, day.month, day.day, tzinfo=UTC)
        stamps.append(int(stamp.timestamp() * 1000))
        day += dt.timedelta(days=1)
    return np.asarray(stamps, dtype=np.int64)


def _weeks(stamps: np.ndarray) -> list[tuple[int, int]]:
    out = []
    for value in stamps:
        stamp = dt.datetime.fromtimestamp(int(value) / 1000.0, tz=UTC)
        iso = stamp.isocalendar()
        out.append((int(iso.year), int(iso.week)))
    return out
