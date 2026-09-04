from __future__ import annotations

import json
import math
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MD = REPO_ROOT / "docs" / "research" / "B2_04_MODERATE_PULLBACK_STRUCTURE_PREREG.md"
JSON = REPO_ROOT / "docs" / "research" / "B2_04_MODERATE_PULLBACK_STRUCTURE_PREREG.json"
INVENTORY = REPO_ROOT / "docs" / "research" / "V2_FORMULATION_INVENTORY.md"
SCRIPTS = REPO_ROOT / "scripts" / "research"


def _freeze() -> dict:
    return json.loads(JSON.read_text(encoding="utf-8"))


def test_b2_04_hypothesis_id_and_h04_posthoc_untested_provenance():
    freeze = _freeze()
    assert freeze["formulation_id"] == "B2-04_MODERATE_PULLBACK_STRUCTURE"
    assert freeze["primary_family"] == "F1"
    provenance = freeze["posthoc_provenance"]
    assert provenance["kind"] == "explicit_POSTHOC_UNTESTED_child"
    assert provenance["h04_verdict"] == "H04_REJECTED_SPECIFIC_CLAIM"
    assert provenance["moderate_band_residual_status"] == "POSTHOC_UNTESTED"
    assert provenance["moderate_band_residual_is_positive_evidence_for_b2_04"] is False
    assert provenance["h04_attractive_L_not_selected"] is True

    md = MD.read_text(encoding="utf-8")
    assert "B2-04_MODERATE_PULLBACK_STRUCTURE" in md
    assert "POSTHOC_UNTESTED" in md
    assert "H04_REJECTED_SPECIFIC_CLAIM" in md
    assert "It is **not** positive evidence for B2-04." in md


def test_b2_04_moderate_domain_and_surfaces_are_exactly_h04_inherited():
    freeze = _freeze()
    construction = freeze["event_construction"]
    assert construction["P_minutes"] == 60
    assert construction["L_minutes"] == [240, 480, 960]
    assert freeze["horizons_minutes"] == [15, 30, 60, 120, 240]
    assert freeze["search_surface_primary_cells"] == 15
    assert freeze["no_depth_search_dimension"] is True
    assert construction["moderate_domain_interval"] == "[0.25,0.40)"
    assert construction["moderate_domain_lo_inclusive"] == 0.25
    assert construction["moderate_domain_hi_exclusive"] == 0.40
    assert construction["shallow_primary_cells"] is False
    assert construction["deep_primary_cells"] is False
    assert construction["refractory_minutes"] == 60
    assert construction["recovery_does_not_decide_existence"] is True

    md = MD.read_text(encoding="utf-8")
    assert "`L = {240, 480, 960}`" in md
    assert "`H = {15, 30, 60, 120, 240}`" in md
    assert "`[0.25, 0.40)`" in md
    assert "`P = 60`" in md


def test_b2_04_has_exactly_one_structural_property_and_forbids_b2_03_features():
    freeze = _freeze()
    prop = freeze["structural_property"]
    assert prop["family"] == "INTRA_PULLBACK_RECOVERY"
    assert prop["count"] == 1
    assert prop["name"] == "RECOVERY_FRACTION"
    assert prop["formulas"]["RECOVERY_FRACTION"] == (
        "(MAX_ADVERSE - FINAL_DEPTH) / MAX_ADVERSE"
    )
    assert prop["invariants"]["FINAL_DEPTH_equals_h04_pullback_depth"] is True
    assert prop["uses_high_low"] is False
    assert prop["d_and_trend_ret_frozen_at_T"] is True

    forbidden = freeze["novelty_boundary"]["b2_03_features_forbidden"]
    assert forbidden == [
        "DISTRIBUTEDNESS",
        "PATH_EFFICIENCY",
        "DIRECTIONAL_BAR_SHARE",
        "COUNTERMOVE_SHALLOWNESS",
    ]
    candidate_match = freeze["forecast"]["candidate_match"]
    for feature in forbidden:
        assert feature not in candidate_match
        assert feature not in freeze["forecast"]["baseline_match"]
    assert freeze["novelty_boundary"]["b2_03_outcome_surface_not_used_to_tune_b2_04"] is True
    assert freeze["directional_prior"]["exhaustion_sign_flip_rescue_forbidden"] is True
    assert freeze["directional_prior"]["statement"] == (
        "higher RECOVERY_FRACTION corresponds to stronger subsequent "
        "trend-direction continuation"
    )


def test_b2_04_canonical_event_id_is_not_t_only():
    identity = _freeze()["event_identity"]
    serialization = identity["canonical_serialization"]
    assert serialization["format"] == (
        "snapshot_id|1m|15m|15m|L_minutes|direction|pullback_start_ms|T_ms|H_minutes"
    )
    assert serialization["field_order"] == [
        "snapshot_id",
        "source_timeframe",
        "derived_timeframe",
        "decision_grid",
        "L_minutes",
        "direction",
        "pullback_start_ms",
        "T_ms",
        "H_minutes",
    ]
    assert serialization["pullback_start_ms_definition"] == "T_ms - 60*60000"
    assert serialization["no_alternate_repr_permitted"] is True
    assert identity["deduplication_on_T_only_forbidden"] is True
    assert identity["baseline_and_candidate_share_identity"] is True

    md = MD.read_text(encoding="utf-8")
    assert (
        "CANONICAL_EVENT_ID = "
        "snapshot_id|1m|15m|15m|L_minutes|direction|pullback_start_ms|T_ms|H_minutes"
        in md
    )


def test_b2_04_baseline_candidate_and_support_are_same_support_stratum_median():
    forecast = _freeze()["forecast"]
    assert forecast["family"] == "same_support_stratum_median"
    assert forecast["training_lookback_days"] == 365
    assert forecast["training_outcome_rule"] == "training_T + H <= current_T"
    assert forecast["baseline_min_count"] == 20
    assert forecast["candidate_min_count"] == 10
    assert forecast["baseline_match"] == ["L", "DIRECTION", "DEPTH_HALF"]
    assert forecast["candidate_match"] == [
        "L",
        "DIRECTION",
        "DEPTH_HALF",
        "RECOVERY_STATE",
    ]
    assert forecast["same_support_required"] is True
    assert forecast["fallback"] == "none"
    assert forecast["support_feasibility"]["h04_post_refractory_moderate_N"] == {
        "240": 2511,
        "480": 1691,
        "960": 892,
    }
    assert _freeze()["baseline_context"]["moderate_boolean_only_forbidden"] is True
    assert _freeze()["recovery_representation"]["states"] == ["LOW", "HIGH"]
    assert _freeze()["recovery_representation"]["no_full_sample_quantiles"] is True


def test_b2_04_eight_gates_seeds_and_anti_rescue_are_frozen():
    freeze = _freeze()
    contract = freeze["promotion_gate_contract"]
    assert contract["required_gate_names"] == [
        "primary_positive",
        "material_relative_mae",
        "bootstrap_positive",
        "placebo_separation",
        "structure_ordering",
        "horizon_robustness",
        "parameter_robustness",
        "year_stability",
    ]
    assert contract["gate_count"] == 8
    assert contract["hidden_ninth_gate_forbidden"] is True
    assert freeze["per_cell_thresholds"]["relative_mae_improvement_min"] == 0.02
    controls = freeze["controls"]
    assert controls["permutation_seed"] == 20260906
    assert controls["permutation_replicates"] == 100
    assert controls["bootstrap_seed"] == 20260907
    assert controls["bootstrap_replicates"] == 2000
    assert controls["bootstrap_block"] == "UTC_week"
    assert freeze["verdicts"] == [
        "B2_04_PROMOTED_CANDIDATE",
        "B2_04_CLOSED_NO_PROMOTION",
    ]
    assert freeze["anti_rescue"]["attempts_in_current_v2"] == 1
    assert "B2-04 child-of-child" in freeze["anti_rescue"]["forbidden_after_failure"]
    assert freeze["anti_rescue"]["failure_closes_h04_child_path_in_current_v2"] is True


def test_b2_04_per_cell_gates_are_structurally_complete():
    gates = _freeze()["promotion_gate_contract"]["per_cell_gates"]
    assert set(gates) == {
        "primary_positive",
        "material_relative_mae",
        "bootstrap_positive",
        "placebo_separation",
        "structure_ordering",
    }
    assert gates["primary_positive"]["pooled_condition"] == (
        "pooled mean AE improvement > 0"
    )
    assert gates["primary_positive"]["up_condition"] == "UP mean AE improvement > 0"
    assert gates["primary_positive"]["down_condition"] == (
        "DOWN mean AE improvement > 0"
    )
    assert gates["material_relative_mae"]["pooled_condition"] == (
        "relative MAE improvement >= 0.02"
    )
    assert gates["structure_ordering"]["pooled_condition"] == (
        "STRUCTURE_SEPARATION(pooled) > 0"
    )
    assert "DISTRIBUTEDNESS" not in json.dumps(gates)


def test_b2_04_outcome_boundary_and_durable_slot_are_unopened():
    freeze = _freeze()
    assert freeze["outcome_access_authorized"] is False
    assert freeze["validation_2025_authorized"] is False
    assert freeze["oos_2026_authorized"] is False
    assert freeze["real_core_data_accessed_by_this_unit"] is False
    assert freeze["implementation_exists"] is False
    retention = freeze["durable_retention_integration"]
    assert retention["canonical_slot"] == "B2-04"
    assert retention["created_by_this_unit"] is False
    assert retention["ceremony"] == [
        "verify_batch02_code",
        "prepare_batch02_evidence_reservation",
        "prepare_batch02_retained_run",
        "load_authorized_parquet_table",
        "evaluate",
        "persist_batch02_retained_result",
        "archive_batch02_result",
    ]
    assert "PRE_CLAIM_OPERATIONAL_ABORT" in retention["execution_host_preflight"]

    md = MD.read_text(encoding="utf-8")
    assert "2025 validation = UNTOUCHED" in md
    assert "2026 OOS = UNTOUCHED" in md
    assert "`outcome_access_authorized = false`" in md
    assert "Protected production slot: **`B2-04`**" in md


def test_b2_04_this_pr_has_no_runner_or_result_artifact():
    forbidden_scripts = sorted(SCRIPTS.glob("b2_04_*.py"))
    assert forbidden_scripts == []
    result_json = (
        REPO_ROOT / "docs" / "research" / "B2_04_MODERATE_PULLBACK_STRUCTURE_RESULT.json"
    )
    result_md = (
        REPO_ROOT / "docs" / "research" / "B2_04_MODERATE_PULLBACK_STRUCTURE_RESULT.md"
    )
    assert not result_json.exists()
    assert not result_md.exists()
    assert _freeze()["implementation_paths_forbidden_in_this_unit"] == [
        "scripts/research/b2_04_*.py"
    ]


def test_b2_04_inventory_file_is_not_modified_by_this_unit():
    text = INVENTORY.read_text(encoding="utf-8")
    assert "B2-04_MODERATE_PULLBACK_STRUCTURE" in text
    assert "explicit `POSTHOC_UNTESTED` child" in text
    # This unit must not rewrite inventory admission or add a second child.
    assert "No second moderate-depth child is admitted." in text


def test_b2_04_recovery_fraction_equals_h04_pullback_depth_at_final_step():
    """Algebraic identity only. No market parquet."""

    def recovery_path(d: int, origin: float, closes: list[float], trend_ret: float):
        adverses = [
            -d * math.log(close / origin) / abs(trend_ret) for close in closes
        ]
        final_depth = adverses[-1]
        signed_pb = d * math.log(closes[-1] / origin)
        h04_depth = -signed_pb / abs(trend_ret)
        max_adverse = max(adverses)
        recovery = (max_adverse - final_depth) / max_adverse
        return adverses, final_depth, h04_depth, max_adverse, recovery

    up_closes = [99.0, 97.0, 97.5, 98.0]
    _, final_up, h04_up, max_up, rec_up = recovery_path(+1, 100.0, up_closes, 0.10)
    assert math.isclose(final_up, h04_up, rel_tol=0.0, abs_tol=1e-15)
    assert max_up >= final_up > 0.0
    assert 0.0 <= rec_up <= 1.0
    assert rec_up > 0.0

    down_closes = [101.0, 103.0, 102.5, 102.0]
    _, final_dn, h04_dn, max_dn, rec_dn = recovery_path(-1, 100.0, down_closes, -0.10)
    assert math.isclose(final_dn, h04_dn, rel_tol=0.0, abs_tol=1e-15)
    assert max_dn >= final_dn > 0.0
    assert 0.0 <= rec_dn <= 1.0
    assert rec_dn > 0.0

    no_recovery = [99.0, 98.5, 98.0, 97.0]
    _, final_nr, h04_nr, max_nr, rec_nr = recovery_path(+1, 100.0, no_recovery, 0.12)
    assert math.isclose(final_nr, h04_nr, rel_tol=0.0, abs_tol=1e-15)
    assert math.isclose(max_nr, final_nr, rel_tol=0.0, abs_tol=1e-15)
    assert math.isclose(rec_nr, 0.0, rel_tol=0.0, abs_tol=1e-15)
