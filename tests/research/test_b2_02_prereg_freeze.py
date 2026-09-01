from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MD = REPO_ROOT / "docs" / "research" / "B2_02_BOUNDARY_INTERACTION_PATH_PREREG.md"
JSON = REPO_ROOT / "docs" / "research" / "B2_02_BOUNDARY_INTERACTION_PATH_PREREG.json"


def _freeze() -> dict:
    return json.loads(JSON.read_text(encoding="utf-8"))


def test_b2_02_prereg_stays_outcome_blind_and_surface_is_finite():
    freeze = _freeze()
    assert freeze["outcome_access_authorized"] is False
    assert freeze["validation_2025_authorized"] is False
    assert freeze["oos_2026_authorized"] is False
    assert freeze["search_surface_primary_cells"] == 12
    assert freeze["prior_range_lookbacks_minutes"] == [60, 120, 240]
    assert freeze["horizons_minutes"] == [30, 60, 120, 240]


def test_b2_02_scored_identity_binds_timeframes_and_horizon():
    fields = _freeze()["event_identity"]["fields"]
    assert fields == [
        "snapshot_id",
        "source_timeframe",
        "derived_timeframe",
        "L",
        "side",
        "T0",
        "T",
        "H",
    ]


def test_b2_02_path_clock_and_last_legal_boundary_are_frozen():
    chronology = _freeze()["chronology"]
    assert chronology["path_observation_minutes"] == 30
    assert chronology["last_legal_T0"] == "2024-12-31T19:25:00Z"
    assert chronology["last_legal_T"] == "2024-12-31T19:55:00Z"
    assert "T0+25m,T" in chronology["path_bar_clock"]


def test_b2_02_baseline_reference_and_formulas_are_exact():
    baseline = _freeze()["baseline_context"]
    assert baseline["reference_days"] == 30
    assert "same L" in baseline["reference_population"]
    assert "sides pooled" in baseline["reference_population"]
    assert "PRE_VOL" in baseline["formulas"]
    assert "PRE_DRIFT" in baseline["formulas"]
    assert baseline["empty_reference"].startswith("UNAVAILABLE_FOR_DECISION")


def test_b2_02_path_descriptor_reference_and_undefined_policy_are_joint():
    path = _freeze()["path_descriptor"]
    assert path["reference_days"] == 30
    assert "same L" in path["reference_population"]
    assert "full 30m path known strictly before current T" in path["reference_population"]
    assert "both candidate and baseline" in path["undefined_policy"]
    assert set(path["formulas"]) == {
        "RESIDENCE",
        "TERMINAL_EXTENSION",
        "MAX_EXTENSION",
        "PATH_EFFICIENCY",
    }


def test_b2_02_forecast_uses_90d_and_joint_same_support():
    forecast = _freeze()["forecast"]
    assert forecast["training_lookback_days"] == 90
    assert forecast["baseline_min_count"] == 80
    assert forecast["candidate_min_count"] == 40
    assert forecast["same_support_required"] is True
    assert "both candidate and baseline" in forecast["joint_unavailability"]


def test_b2_02_placebo_and_promotion_contract_are_frozen():
    freeze = _freeze()
    controls = freeze["controls"]
    assert controls["permutation_seed"] == 20260902
    assert controls["permutation_replicates"] == 100
    assert controls["permutation_seed_derivation"] == (
        "20260902 | replicate_index | L | H | decision_time_T | stratum_id"
    )
    assert freeze["promotion_gate_contract"]["required_gate_names"] == [
        "primary_positive",
        "material_relative_mae",
        "bootstrap_positive",
        "placebo_separation",
        "path_ordering",
        "horizon_robustness",
        "parameter_robustness",
        "year_stability",
    ]

    md = MD.read_text(encoding="utf-8")
    assert "preceding **90 calendar days**" in md
    assert "joint eligibility predicate" in md
    assert "source_timeframe=1m | derived_timeframe=5m" in md
