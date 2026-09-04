from __future__ import annotations

import json
import math
import subprocess
from datetime import datetime, timedelta, timezone
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
    assert provenance["h04_all_45_cells_directionally_wrong"] is False
    assert provenance["h04_characterization"] == (
        "H04's broad preregistered pullback-continuation mechanism did not "
        "satisfy its full promotion contract. Local effects, including a "
        "moderate-depth residual, existed but did not form the required "
        "robust depth neighborhood and remain POSTHOC_UNTESTED."
    )
    assert "did not satisfy" in md
    assert "directionally correct at any of the 45" not in md
    assert "not** directionally correct at any of the 45" not in md


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
    base = identity["canonical_base_serialization"]
    score = identity["canonical_score_serialization"]
    assert base["format"] == (
        "snapshot_id|1m|15m|15m|L_minutes|direction|pullback_start_ms|T_ms"
    )
    assert score["format"] == (
        "snapshot_id|1m|15m|15m|L_minutes|direction|pullback_start_ms|T_ms|H_minutes"
    )
    assert score["definition"] == (
        "CANONICAL_SCORE_RECORD_ID = CANONICAL_BASE_EVENT_ID|H_minutes"
    )
    assert identity["refractory_identity"] == "CANONICAL_BASE_EVENT_ID"
    assert identity["deduplication_on_T_only_forbidden"] is True
    assert identity["baseline_and_candidate_share_identity"] is True

    md = MD.read_text(encoding="utf-8")
    assert (
        "CANONICAL_BASE_EVENT_ID = "
        "snapshot_id|1m|15m|15m|L_minutes|direction|pullback_start_ms|T_ms"
        in md
    )
    assert (
        "CANONICAL_EVENT_ID = "
        "snapshot_id|1m|15m|15m|L_minutes|direction|pullback_start_ms|T_ms|H_minutes"
        in md
    )


def test_b2_04_event_lifecycle_separates_construction_from_scoring():
    life = _freeze()["event_lifecycle"]
    assert life["stages"] == [
        "CONSTRUCT_EVENT",
        "REFRACTORY",
        "IMMUTABLE_EVENT_POPULATION",
        "DERIVE_CAUSAL_FEATURES_AT_T",
        "CREATE_H_SPECIFIC_SCORE_RECORD",
        "SAME_SUPPORT_FORECAST_COMPARISON",
    ]
    assert life["refractory_before_recovery_scoring"] is True
    assert life["refractory_before_target_attachment"] is True
    assert life["refractory_horizon_independent"] is True
    assert life["candidate_feature_cannot_change_refractory_winner"] is True
    assert life["recovery_availability_cannot_change_refractory_winner"] is True
    assert life["target_availability_cannot_change_refractory_winner"] is True
    assert life["REFRACTORY"]["uses_recovery"] is False
    assert life["REFRACTORY"]["uses_target"] is False
    assert life["REFRACTORY"]["uses_H"] is False
    forbidden = life["CONSTRUCT_EVENT"]["forbidden_inputs"]
    assert "RECOVERY_FRACTION" in forbidden
    assert "Y_H" in forbidden
    assert "H" in forbidden
    construction = _freeze()["event_construction"]
    assert construction["not_gated_by_recovery_availability"] is True
    assert construction["not_gated_by_target_availability"] is True
    assert construction["not_gated_by_horizon"] is True


def test_b2_04_baseline_contains_continuous_final_depth_not_depth_half():
    freeze = _freeze()
    forecast = freeze["forecast"]
    baseline = freeze["baseline_context"]
    recovery = freeze["recovery_representation"]
    assert forecast["family"] == "same_support_ols_within_L_DIRECTION"
    assert forecast["estimator"] == "ordinary_least_squares"
    assert forecast["fit_equation_baseline"] == "Y_H = a + b * FINAL_DEPTH"
    assert forecast["fit_equation_candidate"] == (
        "Y_H = a + b * FINAL_DEPTH + c * RECOVERY_FRACTION"
    )
    assert forecast["design_matrix_baseline"] == ["intercept", "FINAL_DEPTH"]
    assert forecast["design_matrix_candidate"] == [
        "intercept",
        "FINAL_DEPTH",
        "RECOVERY_FRACTION",
    ]
    assert forecast["baseline_match"] == ["L", "DIRECTION", "FINAL_DEPTH"]
    assert forecast["candidate_match"] == [
        "L",
        "DIRECTION",
        "FINAL_DEPTH",
        "RECOVERY_FRACTION",
    ]
    assert forecast["information_difference"] == (
        "candidate adds RECOVERY_FRACTION only"
    )
    assert forecast["training_lookback_days"] == 365
    assert forecast["training_min_count"] == 30
    assert forecast["pseudoinverse_forbidden"] is True
    assert forecast["fallback"] == "none"
    assert baseline["DEPTH_HALF_forbidden"] is True
    assert baseline["method"] == "continuous_causal_FINAL_DEPTH"
    assert recovery["primary_representation"] == "RECOVERY_FRACTION"
    assert recovery["transform"] == "identity"
    assert recovery["states_not_used_in_primary_candidate"] is True
    assert "DEPTH_HALF" not in forecast["baseline_match"]
    assert "DEPTH_HALF" not in forecast["candidate_match"]
    assert "RECOVERY_STATE" not in forecast["candidate_match"]
    assert freeze["forecast"]["support_feasibility"][
        "h04_post_refractory_moderate_N"
    ] == {"240": 2511, "480": 1691, "960": 892}

    md = MD.read_text(encoding="utf-8")
    assert "DEPTH_HALF` control is **forbidden**" in md
    assert "Y_H = a + b * FINAL_DEPTH + c * RECOVERY_FRACTION" in md


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
    assert controls["permutation_strata"] == ["L", "DIRECTION"]
    assert "DEPTH_HALF" not in controls["permutation_strata"]
    assert controls["baseline_stratum_id_serialization"]["format"] == (
        "L_minutes|direction"
    )
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
    assert contract["year_stability"] == (
        "every promotion-neighborhood cell (the adjacent-H pair at both "
        "promoting L values) has positive pooled mean AE improvement in "
        ">=4/5 development years (2020,2021,2022,2023,2024); no year exclusions"
    )
    md = MD.read_text(encoding="utf-8")
    assert "every cell in the promotion neighborhood" in md
    assert "ISO_week_year * 100 + ISO_week" in md


def test_b2_04_last_legal_T_is_strictly_before_2025_and_max_on_15m_grid():
    freeze = _freeze()
    chronology = freeze["chronology"]
    expected = {
        "15": "2024-12-31T23:30:00Z",
        "30": "2024-12-31T23:15:00Z",
        "60": "2024-12-31T22:45:00Z",
        "120": "2024-12-31T21:45:00Z",
        "240": "2024-12-31T19:45:00Z",
    }
    assert chronology["last_legal_T_by_horizon_minutes"] == expected
    assert chronology["last_legal_T_rule"].startswith(
        "T + H < 2025-01-01T00:00:00Z"
    )
    end = datetime(2025, 1, 1, tzinfo=timezone.utc)
    grid = timedelta(minutes=15)
    for h_text, stamp in expected.items():
        h = timedelta(minutes=int(h_text))
        last_t = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        next_t = last_t + grid
        assert last_t + h < end
        assert next_t + h >= end
        assert (last_t + h).isoformat() != end.isoformat()
    md = MD.read_text(encoding="utf-8")
    for stamp in expected.values():
        assert f"`{stamp}`" in md
    assert "`close(T+H)` at exactly `2025-01-01T00:00:00Z` is illegal" in md


def test_b2_04_bootstrap_week_id_uses_iso_week_year():
    week_id = _freeze()["controls"]["bootstrap_week_id"]
    assert "ISO week-numbering year" in week_id
    assert "not the Gregorian calendar year" in week_id
    # Boundary example: 2024-12-30 is ISO week 1 of ISO year 2025.
    boundary = datetime(2024, 12, 30, tzinfo=timezone.utc)
    iso = boundary.isocalendar()
    assert iso.year == 2025
    assert iso.week == 1
    assert iso.year * 100 + iso.week != boundary.year * 100 + iso.week


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


def test_b2_04_prereg_unit_shipped_no_runner_and_no_result_artifact():
    """The frozen prohibition is unit-scoped (`..._forbidden_in_this_unit`).

    The preregistration unit shipped no implementation; that historical fact
    is recorded in the frozen JSON and in Git history. A later, separate
    implementation unit is explicitly contemplated by the same freeze
    (`durable_retention_integration.ceremony`, MD section 19), so this guard
    pins what remains live: the frozen text still scopes the prohibition to
    the preregistration unit, no B2-04 *result* artifact may exist before an
    authorized run, and any implementation that does exist must be exactly
    the canonical runner/library pair -- never a third script and never a
    result document.
    """
    assert _freeze()["implementation_paths_forbidden_in_this_unit"] == [
        "scripts/research/b2_04_*.py"
    ]
    assert _freeze()["implementation_exists"] is False

    result_json = (
        REPO_ROOT / "docs" / "research" / "B2_04_MODERATE_PULLBACK_STRUCTURE_RESULT.json"
    )
    result_md = (
        REPO_ROOT / "docs" / "research" / "B2_04_MODERATE_PULLBACK_STRUCTURE_RESULT.md"
    )
    assert not result_json.exists()
    assert not result_md.exists()

    # The canonical retained-run artifact path
    # (artifacts/b2_04_moderate_pullback_structure/..._DEV_RESULTS.json) is
    # NOT checked for filesystem absence here: persist_batch02_retained_result
    # deliberately leaves that local canonical artifact in place after a
    # legitimate future authorized run (BATCH02_DURABLE_EVIDENCE_RETENTION_V1
    # section 8 -- the local artifact must be preserved, never deleted), so a
    # filesystem-absence check here would fail this long-lived suite the
    # moment a real run ever happens, for a reason unrelated to prereg
    # integrity. The durable fact this test protects -- no B2-04 result is
    # *committed to source control* -- is instead checked against Git's
    # tracked-file state, which persistence never touches (the whole
    # `artifacts/` tree is gitignored; see .gitignore) and which is exactly
    # what "shipped by this unit" means.
    tracked = subprocess.run(  # noqa: S603 - fixed argv, no shell, test-only
        ["git", "ls-files", "artifacts/b2_04_moderate_pullback_structure"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert tracked.strip() == ""

    implementation = sorted(path.name for path in SCRIPTS.glob("b2_04_*.py"))
    assert implementation in (
        [],
        [
            "b2_04_moderate_pullback_structure.py",
            "b2_04_moderate_pullback_structure_lib.py",
        ],
    )


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
    assert math.isclose(rec_up, 1.0 - final_up / max_up, rel_tol=0.0, abs_tol=1e-15)

    # Same FINAL_DEPTH, different MAX_ADVERSE => different recovery.
    # Recovery is therefore not a function of FINAL_DEPTH alone.
    same_final = 0.30
    rec_a = 1.0 - same_final / 0.32
    rec_b = 1.0 - same_final / 0.39
    assert rec_a != rec_b
    assert 0.0 <= rec_a < rec_b <= 1.0
    assert _freeze()["structural_property"]["invariants"][
        "recovery_not_function_of_final_depth_alone"
    ] is True


def test_b2_04_post_run_artifact_presence_does_not_break_this_suite():
    """Repair regression test: a legitimate future retained run leaves the
    canonical local DEV_RESULTS.json artifact on disk on purpose
    (BATCH02_DURABLE_EVIDENCE_RETENTION_V1 section 8 -- the local canonical
    artifact must be preserved, never deleted). This suite must keep passing
    when that artifact exists locally; it must only ever fail if a B2-04
    result were committed to Git.

    This test creates a synthetic placeholder file at the real canonical
    path -- never touching real CORE data, never claiming outcome access,
    and cleaned up in a `finally` block -- to prove the invariant mechanism
    (a Git-tracked-file check, not a filesystem-existence check) actually
    tolerates local post-run artifacts.
    """
    canonical_path = (
        REPO_ROOT
        / "artifacts"
        / "b2_04_moderate_pullback_structure"
        / "B2_04_MODERATE_PULLBACK_STRUCTURE_DEV_RESULTS.json"
    )
    assert not canonical_path.exists(), (
        "test seam precondition: no real result artifact must already exist"
    )
    canonical_path.parent.mkdir(parents=True, exist_ok=True)
    canonical_path.write_text(
        json.dumps({"synthetic_test_seam_placeholder": True}),
        encoding="utf-8",
    )
    try:
        # Untracked/gitignored: this placeholder must be invisible to Git.
        tracked = subprocess.run(
            ["git", "ls-files", "artifacts/b2_04_moderate_pullback_structure"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        assert tracked.strip() == ""
        # The long-lived suite's post-run guard must still pass with the
        # placeholder present.
        test_b2_04_prereg_unit_shipped_no_runner_and_no_result_artifact()
    finally:
        canonical_path.unlink(missing_ok=True)
        try:
            canonical_path.parent.rmdir()
        except OSError:
            pass
    assert not canonical_path.exists()
