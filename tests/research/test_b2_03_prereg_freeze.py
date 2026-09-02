from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MD = REPO_ROOT / "docs" / "research" / "B2_03_IMPULSE_MORPHOLOGY_PREREG.md"
JSON = REPO_ROOT / "docs" / "research" / "B2_03_IMPULSE_MORPHOLOGY_PREREG.json"


def _freeze() -> dict:
    return json.loads(JSON.read_text(encoding="utf-8"))


def test_b2_03_prereg_stays_outcome_blind_and_surface_is_finite():
    freeze = _freeze()
    assert freeze["outcome_access_authorized"] is False
    assert freeze["validation_2025_authorized"] is False
    assert freeze["oos_2026_authorized"] is False
    assert freeze["search_surface_primary_cells"] == 15
    assert freeze["impulse_windows_minutes"] == [15, 30, 60]
    assert freeze["horizons_minutes"] == [15, 30, 60, 120, 240]


def test_b2_03_scored_identity_binds_grid_window_and_horizon():
    fields = _freeze()["event_identity"]["fields"]
    assert fields == [
        "snapshot_id",
        "source_timeframe",
        "derived_timeframe",
        "decision_grid",
        "W",
        "direction",
        "window_start",
        "window_end",
        "T",
        "H",
    ]


def test_b2_03_novelty_boundary_does_not_reuse_h03_extremeness():
    novelty = _freeze()["novelty_boundary"]
    assert novelty["h03_verdict"] == "H03_REJECTED_SPECIFIC_CLAIM"
    assert novelty["h03_q_values_not_reused"] == [0.90, 0.95, 0.98]
    assert novelty["magnitude_admission_threshold"] == "none"
    assert novelty["w_inherited_as_fixed_path_scale_family"] is True
    assert novelty["w_not_chosen_from_h03_cell"] is True


def test_b2_03_decision_grid_is_hourly_with_no_magnitude_trigger():
    chronology = _freeze()["chronology"]
    assert chronology["decision_times"] == "UTC hourly boundaries only, 00:00..23:00"
    assert chronology["no_magnitude_trigger"] is True
    assert chronology["last_legal_T_by_horizon_minutes"] == {
        "15": "2024-12-31T23:00:00Z",
        "30": "2024-12-31T23:00:00Z",
        "60": "2024-12-31T22:00:00Z",
        "120": "2024-12-31T21:00:00Z",
        "240": "2024-12-31T19:00:00Z",
    }


def test_b2_03_event_construction_is_not_gated_by_morphology_availability():
    construction = _freeze()["event_construction"]
    assert construction["not_gated_by_morphology_availability"] is True
    assert construction["unavailable_morphology_policy"].startswith(
        "record remains a constructed event"
    )
    assert "never deleted from population" in construction["unavailable_morphology_policy"]


def test_b2_03_morphology_descriptor_and_undefined_policy_are_joint():
    morphology = _freeze()["morphology_descriptor"]
    assert morphology["reference_days"] == 30
    assert "both candidate and baseline" in morphology["undefined_policy"]
    assert set(morphology["formulas"]) == {
        "TV",
        "DISTRIBUTEDNESS",
        "PATH_EFFICIENCY",
        "DIRECTIONAL_BAR_SHARE",
        "COUNTERMOVE_SHALLOWNESS",
    }
    assert morphology["exhaustion_alternative_preregistered"] is False


def test_b2_03_forecast_uses_90d_and_joint_same_support():
    forecast = _freeze()["forecast"]
    assert forecast["training_lookback_days"] == 90
    assert forecast["baseline_min_count"] == 80
    assert forecast["candidate_min_count"] == 40
    assert forecast["same_support_required"] is True
    assert "both" in forecast["joint_unavailability"]


def test_b2_03_placebo_and_promotion_contract_are_frozen():
    freeze = _freeze()
    controls = freeze["controls"]
    assert controls["permutation_seed"] == 20260904
    assert controls["permutation_replicates"] == 100
    assert controls["permutation_seed_derivation"] == (
        "20260904 | replicate_index | W | H | current_T | baseline_stratum_id"
    )
    assert controls["bootstrap_seed"] == 20260905
    assert controls["bootstrap_replicates"] == 2000
    assert freeze["promotion_gate_contract"]["required_gate_names"] == [
        "primary_positive",
        "material_relative_mae",
        "bootstrap_positive",
        "placebo_separation",
        "morphology_ordering",
        "horizon_robustness",
        "parameter_robustness",
        "year_stability",
    ]

    md = MD.read_text(encoding="utf-8")
    assert "preceding 90 calendar days" in md
    assert "joint eligibility predicate" in md
    assert "H03_REJECTED_SPECIFIC_CLAIM" in md


def test_b2_03_durable_retention_integration_targets_pr99_ceremony():
    retention = _freeze()["durable_retention_integration"]
    assert retention["ceremony"] == [
        "verify_batch02_code",
        "prepare_batch02_evidence_reservation",
        "prepare_batch02_retained_run",
        "load_authorized_parquet_table",
        "persist_batch02_retained_result",
        "archive_batch02_result",
    ]
    assert retention["historical_path_forbidden"] == [
        "prepare_batch02_run",
        "persist_batch02_result",
    ]
    assert retention["canonical_slot"] == "B2-03"
    assert retention["created_by_this_unit"] is False
