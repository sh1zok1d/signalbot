"""Synthetic checks for prospective amendment A1. No forward endpoint is scored."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.research.formation_width_activity_prospective_v1 import amendment_a1 as A1
from scripts.research.formation_width_activity_prospective_v1 import constants as K
from scripts.research.formation_width_activity_prospective_v1 import evaluate
from scripts.research.formation_width_activity_prospective_v1 import forecast


ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_KEY_PARTS = (
    "spearman",
    "partial",
    "rho",
    "activity",
    "displacement",
    "future_rv",
    "log_return",
    "y_future",
    "outcome_association",
)


def _walk_keys(obj):
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield str(key)
            yield from _walk_keys(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk_keys(item)


def _active():
    return A1.build_spec(A1.amendment_sha256())


def test_tail_spends_sum_to_the_split_budget():
    spec = _active()
    lower = sum(row["lower_tail_spend"]["incremental"] for row in spec["checkpoints"])
    upper = sum(row["upper_tail_spend"]["incremental"] for row in spec["checkpoints"])
    assert lower == pytest.approx(0.025)
    assert upper == pytest.approx(0.025)
    assert lower + upper == pytest.approx(0.05)
    assert spec["overall_decisive_error_budget"] == 0.05
    assert spec["lower_tail_budget"] == 0.025
    assert spec["upper_tail_budget"] == 0.025
    assert spec["spending_formula"] == "A(t)=0.025*t"
    for row in spec["checkpoints"]:
        assert row["lower_tail_spend"]["incremental"] == pytest.approx(row["upper_tail_spend"]["incremental"])
        assert row["lower_quantile"] == pytest.approx(row["lower_tail_spend"]["incremental"])
        assert row["upper_quantile"] == pytest.approx(1.0 - row["upper_tail_spend"]["incremental"])


def test_parent_per_side_budget_is_not_the_active_contract():
    parent = json.loads(
        (ROOT / "docs/research/FORMATION_WIDTH_ACTIVITY_PROSPECTIVE_V1_SPEC.json").read_text()
    )
    assert parent["inference"]["alpha_per_onesided_family"] == 0.05
    with pytest.raises(RuntimeError, match="not the active contract"):
        A1.require_active_contract(parent)
    active = json.loads(
        (ROOT / "docs/research/FORMATION_WIDTH_ACTIVITY_PROSPECTIVE_V1_AMENDMENT_A1.json").read_text()
    )
    A1.require_active_contract(active)
    assert active == _active()
    assert "alpha_per_onesided_family" not in json.dumps(active)


def test_schedule_is_the_recomputed_grid():
    spec = _active()
    assert [row["raw_n"] for row in spec["checkpoints"]] == [1460, 2920]
    assert spec["schedule"]["first_look_n"] == 1460
    assert spec["schedule"]["maturity_n"] == 2920
    assert spec["schedule"]["terminal_n"] == 2920
    assert spec["checkpoints"][0]["magnitude_stop_allowed"] is False
    assert spec["checkpoints"][1]["magnitude_stop_allowed"] is True
    assert spec["checkpoints"][1]["mde80"] <= 0.10
    assert spec["checkpoints"][0]["mde80"] > 0.10
    assert spec["checkpoints"][0]["sequential_power_at_reference"] >= 0.50
    assert spec["checkpoints"][0]["expected_formation_date"] == "2030-10-14"
    assert spec["checkpoints"][1]["expected_formation_date"] == "2034-10-19"
    assert spec["min_sequential_power_role"] == "MINIMUM_INFORMATION_THRESHOLD"
    assert spec["positive_relation_uses_extra_family"] is False
    assert spec["accrued_analysis_n"] == 0
    assert spec["outcome_read"] is False
    assert spec["future_association_read"] is False


def test_selector_does_not_read_historical_points():
    source = Path(A1.__file__).read_text()
    body = source.split("def select_schedule")[1].split("def _role")[0]
    attempt = source.split("def _try_schedule")[1].split("def _annotate_attempt")[0]
    assert "0.10245095315584887" not in body
    assert "0.09903883442772482" not in body
    assert "DISCOVERY_POINT" not in body
    assert "CROSS_VENUE_POINT" not in body
    assert "0.10245095315584887" not in attempt
    assert "0.09903883442772482" not in attempt


def test_routes_use_one_lower_bound():
    assert A1.decide(False, False, True, 0.20, 0.10, 0.30) == K.ROUTE_MAGNITUDE
    assert A1.decide(True, True, True, 0.08, 0.04, 0.15) == K.ROUTE_POSITIVE
    assert A1.decide(True, True, True, 0.099, 0.04, 0.16) == K.ROUTE_POSITIVE
    assert A1.decide(True, True, True, 0.04, 0.01, 0.09) == K.ROUTE_NOT
    assert A1.decide(False, False, True, 0.04, 0.01, 0.05) == K.ACTION_CONTINUE
    assert A1.decide(False, False, True, 0.12, 0.04, 0.20) == K.ACTION_CONTINUE
    assert A1.state_before_first_look(0, 1460) == K.ROUTE_IMMATURE
    assert A1.state_before_first_look(1459, 1460) == K.ROUTE_IMMATURE
    with pytest.raises(RuntimeError):
        A1.state_before_first_look(1460, 1460)


def test_parent_design_file_is_unchanged_and_evaluator_still_refuses():
    design = (ROOT / "docs/research/FORMATION_WIDTH_ACTIVITY_PROSPECTIVE_V1_DESIGN.md").read_bytes()
    assert hashlib.sha256(design).hexdigest() == "d07b83ca9baea11d0af16424da6f7a7a29d43a2a61b6d850d974c8ed80da9612"
    source = (ROOT / "scripts/research/formation_width_activity_prospective_v1/amendment_a1.py").read_text()
    assert "beta_hist" not in source
    assert "klines" not in source
    assert "partial_spearman" not in source
    assert "realized_variation" not in source
    evaluator = (ROOT / "scripts/research/formation_width_activity_prospective_v1/evaluate.py").read_text()
    assert "load_" not in evaluator
    with pytest.raises(SystemExit, match=K.REFUSAL_BEFORE_GO):
        evaluate.main()
    keys = " ".join(_walk_keys(_active())).lower()
    for part in FORBIDDEN_KEY_PARTS:
        assert part not in keys


def test_parent_spec_still_matches_the_parent_compiler():
    parent = json.loads(
        (ROOT / "docs/research/FORMATION_WIDTH_ACTIVITY_PROSPECTIVE_V1_SPEC.json").read_text()
    )
    assert parent == forecast.build_spec(forecast.design_sha256())
    assert [row["raw_n"] for row in parent["checkpoints"]] == [1095, 1825, 2190]
