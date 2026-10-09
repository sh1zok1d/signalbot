"""Synthetic checks for the prospective design. No forward endpoint is scored."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

import pytest

from scripts.research.formation_width_activity_confirmation_v1.support import information_forecast
from scripts.research.formation_width_activity_prospective_v1 import constants as K
from scripts.research.formation_width_activity_prospective_v1 import evaluate
from scripts.research.formation_width_activity_prospective_v1 import forecast


ROOT = Path(__file__).resolve().parents[2]
UTC = dt.timezone.utc
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


def _walk_keys(obj, prefix=""):
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield f"{prefix}.{key}" if prefix else str(key)
            yield from _walk_keys(value, str(key))
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk_keys(item, prefix)


def test_constants_keep_the_frozen_claim():
    assert K.PRACTICAL_REFERENCE == 0.10
    assert K.PROSPECTIVE_START == "2026-10-10T00:00:00Z"
    assert K.FIRST_DECISION_TIME == "2026-10-10T01:00:00Z"
    assert K.ANCHOR == "UTC_00"
    assert K.FORMATION_BARS == 12 and K.HORIZON_BARS == 12
    assert K.BOOT_SEED == 20261109
    assert K.BOOT_DRAWS == 2000
    assert K.SPENDING_RHO == 1.0
    assert K.ALPHA == 0.05
    assert K.DATASET_ID == "BINANCE_UM_LIVE_FORWARD"
    assert K.COLUMN == "CANDLES"
    assert K.DISCOVERY_POINT == pytest.approx(0.10245095315584887)
    assert K.CROSS_VENUE_POINT == pytest.approx(0.09903883442772482)
    assert K.CROSS_VENUE_POINT != K.PRACTICAL_REFERENCE
    start = dt.datetime(2026, 10, 10, tzinfo=UTC)
    closed = dt.datetime(2026, 10, 9, 2, 0, tzinfo=UTC)
    assert start > closed


def test_evaluator_refuses_before_any_panel():
    source = (ROOT / "scripts/research/formation_width_activity_prospective_v1/evaluate.py").read_text()
    assert "information_forecast" not in source
    assert "realized_variation" not in source
    assert "partial_spearman" not in source
    assert "log_returns" not in source
    assert "load_" not in source
    assert "beta_hist" not in source
    assert "klines" not in source
    with pytest.raises(SystemExit, match=K.REFUSAL_BEFORE_GO):
        evaluate.main()


def test_forecast_module_does_not_score_a_forward_endpoint():
    source = (ROOT / "scripts/research/formation_width_activity_prospective_v1/forecast.py").read_text()
    assert "realized_variation" not in source
    assert "partial_spearman" not in source
    assert "log_returns" not in source
    assert "future_return_pairs" not in source
    assert "beta_hist" not in source
    assert "klines" not in source


def test_checkpoint_rule_ignores_historical_points():
    body = "\n".join(
        Path(forecast.__file__).read_text().split(f"def {name}")[1].split("\ndef ")[0]
        for name in ("_maturity_n", "_terminal_n", "_first_look", "_admit_between", "select_schedule")
    )
    assert "0.10245095315584887" not in body
    assert "0.09903883442772482" not in body
    assert "DISCOVERY_POINT" not in body
    assert "CROSS_VENUE_POINT" not in body


def test_spec_matches_the_compiler_and_stays_outcome_blind():
    spec = json.loads((ROOT / "docs/research/FORMATION_WIDTH_ACTIVITY_PROSPECTIVE_V1_SPEC.json").read_text())
    design_sha = hashlib.sha256(
        (ROOT / "docs/research/FORMATION_WIDTH_ACTIVITY_PROSPECTIVE_V1_DESIGN.md").read_bytes()
    ).hexdigest()
    assert spec == forecast.build_spec(design_sha)
    assert spec["outcome_read"] is False
    assert spec["future_association_read"] is False
    assert spec["accrued_analysis_n"] == 0
    assert spec["this_unit_scores_the_forward_endpoint"] is False
    assert spec["owner_go_required_for_first_checkpoint"] is True
    assert spec["l3_authorized"] is False
    assert spec["product_integration_candidate"] is False
    assert spec["context_not_a_prior"]["used_as_prior"] is False
    assert spec["context_not_a_prior"]["used_to_choose_checkpoints"] is False
    assert spec["lag_placebo"]["route_input"] is False
    assert spec["lag_placebo"]["option"] == "A"
    assert spec["stability"]["route_input"] is False
    assert spec["inference"]["always_valid_sequence"] is False
    assert spec["inference"]["seed"] == 20261109
    keys = " ".join(_walk_keys(spec)).lower()
    for part in FORBIDDEN_KEY_PARTS:
        assert part not in keys
    support = (ROOT / "docs/research/FORMATION_WIDTH_ACTIVITY_PROSPECTIVE_V1_SUPPORT.md").read_text()
    assert support == forecast.render_support(spec)
    assert "outcome_read = false" in support


def test_schedule_drops_meaningless_early_looks():
    spec = forecast.build_spec("pending")
    admitted = [row["raw_n"] for row in spec["checkpoints"]]
    assert admitted == [1095, 1825, 2190]
    assert spec["schedule"]["first_look_n"] == 1095
    assert spec["schedule"]["maturity_n"] == 1825
    assert spec["schedule"]["terminal_n"] == 2190
    reasons = {row["raw_n"]: row["reason"] for row in spec["rejected_candidates"]}
    assert reasons[90] == "SINGLE_LOOK_POWER_BELOW_MINIMUM"
    assert reasons[180] == "SINGLE_LOOK_POWER_BELOW_MINIMUM"
    assert reasons[365] == "SINGLE_LOOK_POWER_BELOW_MINIMUM"
    assert reasons[730] == "SEQUENTIAL_INCREMENT_POWER_BELOW_MINIMUM"
    assert reasons[1460] == "SEQUENTIAL_INCREMENT_POWER_BELOW_MINIMUM"
    increments = [row["incremental_alpha"] for row in spec["checkpoints"]]
    assert sum(increments) == pytest.approx(0.05)
    assert all(row["sequential_power_lower_clears_zero"] >= 0.50 for row in spec["checkpoints"])
    assert spec["checkpoints"][0]["expected_formation_date"] == "2029-10-13"
    assert spec["checkpoints"][-1]["expected_formation_date"] == "2032-10-16"
    assert spec["checkpoints"][1]["mde80"] <= 0.10
    assert spec["checkpoints"][0]["mde80"] > 0.10
    assert spec["checkpoints"][0]["magnitude_stop_allowed"] is False
    assert spec["checkpoints"][1]["magnitude_stop_allowed"] is True
    assert spec["checkpoints"][2]["terminal"] is True


def test_forecast_function_is_the_confirmation_forecaster():
    sizes = forecast.balanced_week_sizes(1095)
    direct = information_forecast(sizes, K.PHI)
    row = forecast.forecast_row(1095)
    assert row["effective_n"] == pytest.approx(direct["effective_n"])
    assert row["fisher_se"] == pytest.approx(direct["fisher_se"])
    assert direct["practical_bar"] == 0.10
    assert direct["dependence_model"] == "AR1_WITHIN_ISO_WEEK_USING_WIDTH_LAG_THEN_KISH"


def test_spending_is_stricter_when_information_time_is_early():
    early = forecast.cumulative_alpha(0.25)
    late = forecast.cumulative_alpha(0.75)
    assert early == pytest.approx(0.05 * 0.25)
    assert late > early
    assert forecast.cumulative_alpha(1.0) == pytest.approx(0.05)
    assert forecast.cumulative_alpha(0.0) == 0.0


def test_routes_on_synthetic_intervals():
    reference = K.PRACTICAL_REFERENCE
    assert forecast.decide(False, False, True, 0.20, 0.11, 0.30) == K.ROUTE_MAGNITUDE
    assert forecast.decide(False, False, True, 0.12, 0.04, 0.20) == K.ACTION_CONTINUE
    assert forecast.decide(False, False, True, 0.04, 0.01, 0.08) == K.ACTION_CONTINUE
    assert forecast.decide(False, True, True, 0.04, 0.01, 0.08) == K.ROUTE_NOT
    assert forecast.decide(True, True, True, 0.12, 0.04, 0.20) == K.ROUTE_POSITIVE
    assert forecast.decide(True, True, True, 0.02, -0.01, 0.12) == K.ROUTE_INCONCLUSIVE
    assert forecast.decide(True, True, True, 0.04, 0.01, 0.09) == K.ROUTE_NOT
    assert forecast.decide(True, True, False, 0.20, 0.11, 0.30) == K.ROUTE_INCONCLUSIVE
    assert forecast.decide(False, True, False, 0.20, 0.11, 0.30) == K.ACTION_CONTINUE
    assert forecast.decide(True, True, True, 0.099, 0.05, 0.15) == K.ROUTE_POSITIVE
    assert forecast.decide(True, True, True, 0.100, 0.05, 0.15) == K.ROUTE_POSITIVE
    assert forecast.interim_label(True, 0.099, 0.04, 0.15) == K.ROUTE_POSITIVE
    assert forecast.interim_label(True, 0.20, reference, 0.30) is None
    assert forecast.interim_label(True, 0.04, 0.01, 0.08) is None
    with pytest.raises(SystemExit):
        evaluate.main()
