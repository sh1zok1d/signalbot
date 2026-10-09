"""Synthetic checks for the decision-value design. No market panel is loaded."""

from __future__ import annotations

import datetime as dt
import hashlib
from pathlib import Path

import numpy as np

from scripts.research.formation_width_decision_value_v1 import constants as K
from scripts.research.formation_width_decision_value_v1 import model
from scripts.research.formation_width_incremental_predictive_value_v1 import constants as PREV


ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / "docs" / "research" / "FORMATION_WIDTH_DECISION_VALUE_V1_DESIGN.md"
UTC = dt.timezone.utc


def test_design_hash_and_frozen_choices():
    assert hashlib.sha256(DESIGN.read_bytes()).hexdigest() == K.DESIGN_SHA256
    assert K.TEST_FOLDS == PREV.TEST_FOLDS
    assert K.PRIMARY_QUANTILE == 0.75
    assert K.BINANCE_SEED == 20261112
    assert K.BYBIT_SEED == 20261113
    assert K.BOOT_DRAWS == 2000
    assert K.HISTORICAL_PRACTICAL_RHO_APPLIED is False
    assert K.PRODUCT_LABELS_ADOPTED is False
    assert K.PRODUCT_INTEGRATION_CANDIDATE is False


def test_scoring_source_has_no_magnitude_bar():
    source = (ROOT / "scripts/research/formation_width_decision_value_v1/model.py").read_text()
    assert "0.10" not in source
    assert "label_high" not in source
    assert "0.95" not in source
    body = source.split("def interpret", 1)[1]
    assert "descriptive_cuts[" not in body
    assert "DESCRIPTIVE_QUANTILES" not in body


def test_auroc_of_a_perfect_ranking_is_one():
    score = np.asarray([0.1, 0.2, 0.8, 0.9])
    label = np.asarray([0.0, 0.0, 1.0, 1.0])
    assert model.auroc(score, label) == 1.0


def test_width_improves_the_upper_quartile_decision():
    stamps = _daily_stamps("2020-01-01", "2024-12-31")
    rng = np.random.default_rng(19)
    width = rng.normal(size=len(stamps))
    rv = rng.normal(size=len(stamps))
    activity = width + 0.05 * rng.normal(size=len(stamps))
    scored = model.evaluate_surface(
        stamps, rv, width, activity, _weeks(stamps), venue_start="2020-01-01", seed=5, draws=40,
    )
    assert scored["brier_gain"] > 0.0
    assert scored["net"] > 0.0
    assert scored["auroc_change"] > 0.0
    assert scored["n_correct_changes"] + scored["n_harmful_changes"] == scored["n_changed"]
    assert scored["n_upgrade"] + scored["n_downgrade"] == scored["n_changed"]
    assert scored["route_input"] is True
    assert all(cut["route_input"] is False for cut in scored["descriptive_cuts"])
    assert "interval" not in scored["descriptive_cuts"][0]
    assert scored["decomposition"]["role"] == "descriptive_only"


def test_threshold_uses_training_probabilities_only():
    rng = np.random.default_rng(3)
    rv = rng.normal(size=400)
    width = rng.normal(size=400)
    activity = width + rng.normal(size=400)
    train = np.arange(0, 300)
    test = np.arange(300, 400)
    first = model._one_cut(rv, width, activity, train, test, 0.75)
    activity2 = activity.copy()
    activity2[test] = activity2[test] + 10.0
    second = model._one_cut(rv, width, activity2, train, test, 0.75)
    assert first["tau_baseline"] == second["tau_baseline"]
    assert first["tau_candidate"] == second["tau_candidate"]
    assert first["threshold_activity"] == second["threshold_activity"]


def test_interpretation_uses_sign_and_intervals_only():
    def venue(net, brier, net_lo, brier_lo, net_hi=1.0, brier_hi=1.0, ok=True):
        return {
            "net": net,
            "brier_gain": brier,
            "interval": {
                "net": {"lo": net_lo, "hi": net_hi, "interpretable": ok},
                "brier": {"lo": brier_lo, "hi": brier_hi, "interpretable": ok},
            },
        }

    both = model.interpret(venue(0.02, 0.01, 0.01, 0.001), venue(0.01, 0.02, 0.001, 0.001))
    assert both["code"] == model.CODE_CONSISTENT
    assert both["enter_forecast_architecture"] is False
    assert both["future_validation_decided"] is False
    mixed = model.interpret(venue(0.02, 0.01, -0.01, 0.001), venue(0.01, 0.02, 0.001, 0.001))
    assert mixed["code"] == model.CODE_UNCERTAIN
    quiet = model.interpret(venue(-0.01, -0.02, -0.03, -0.04), venue(-0.01, 0.0, -0.02, -0.01))
    assert quiet["code"] == model.CODE_LITTLE
    split = model.interpret(venue(0.02, 0.01, 0.001, 0.001), venue(-0.02, 0.01, -0.03, 0.001))
    assert split["code"] == model.CODE_HETEROGENEOUS
    blind = model.interpret(
        venue(0.02, 0.01, None, 0.001, ok=False),
        venue(0.01, 0.02, 0.001, 0.001),
    )
    assert blind["code"] == model.CODE_NOT_INTERPRETABLE


def test_this_module_does_not_load_the_evaluator():
    import sys

    assert "scripts.research.formation_width_decision_value_v1.evaluate" not in sys.modules


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
