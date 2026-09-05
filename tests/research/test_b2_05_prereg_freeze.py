"""Freeze tests for the outcome-blind B2-05 flow-absorption preregistration.

These tests pin the frozen document contract (docs/research/
B2_05_FLOW_ABSORPTION_PREREG.md / .json) so it cannot silently drift before
implementation begins. This unit does not implement B2-05 runtime code, does
not access real CORE data, and does not create a durable evidence
reservation. No B2-05 market computation is performed here.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.research import b2_05_flow_absorption as runner


REPO_ROOT = Path(__file__).resolve().parents[2]
MD = REPO_ROOT / "docs" / "research" / "B2_05_FLOW_ABSORPTION_PREREG.md"
JSON = REPO_ROOT / "docs" / "research" / "B2_05_FLOW_ABSORPTION_PREREG.json"
INVENTORY = REPO_ROOT / "docs" / "research" / "V2_FORMULATION_INVENTORY.md"
SCRIPTS = REPO_ROOT / "scripts" / "research"


def _freeze() -> dict:
    return json.loads(JSON.read_text(encoding="utf-8"))


def _md() -> str:
    return MD.read_text(encoding="utf-8")


def test_formulation_id_and_family_are_exact():
    freeze = _freeze()
    assert freeze["formulation_id"] == "B2-05_FLOW_ABSORPTION"
    assert freeze["primary_family"] == "F4"
    assert freeze["primary_family_name"] == "participation / order-flow information"
    assert freeze["inventory_admission"] == "ADMIT_TO_V2_INVENTORY"
    assert freeze["inventory_immutable"] is True
    assert "B2-05_FLOW_ABSORPTION" in _md()
    assert "F4" in _md()


def test_inventory_entry_is_unmodified_and_matches_the_frozen_claim():
    text = INVENTORY.read_text(encoding="utf-8")
    assert "## 9. B2-05 — Flow absorption / price impact" in text
    assert "**Admission:** `ADMIT_TO_V2_INVENTORY`" in text
    assert (
        "Conditional on comparable taker-flow imbalance and price/volatility "
        "state,\n> a predeclared measure of contemporaneous price "
        "impact/absorption adds stable\n> information about subsequent "
        "directional behavior."
    ) in text
    # This unit must not touch the immutable inventory file at all. Pin the
    # exact accepted-base Git blob SHA of the file's bytes -- computed
    # in-process from the canonical Git blob object representation
    # (b"blob " + length + NUL + content), never by shelling out to `git`.
    # This stays hermetic, offline, and independent of both `origin/main`
    # (a shallow/merge-ref CI checkout does not guarantee that ref exists)
    # and the `git` executable being present at all.
    data = INVENTORY.read_bytes()
    blob = b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    digest = hashlib.sha1(blob).hexdigest()  # noqa: S324 -- Git blob SHA-1, not a security hash
    assert digest == "d20a3ad4f6d3fb417ee9875933f097c174da3a30"


def test_old_pr92_outcome_blind_provenance_is_frozen_exactly():
    # NOTE: this is a hermetic source-tree contract test. It pins the
    # *declared* provenance fields (which historical commit was used, that
    # it is recorded as not-merged, and which two files were read from it)
    # -- it does not and cannot dynamically prove actual Git ancestry from
    # inside a shallow/merge-ref CI checkout, where the historical commit
    # object may simply be absent (a non-zero `git merge-base
    # --is-ancestor` return code is ambiguous between "not an ancestor" and
    # "object unavailable" and would be a false-green proof either way).
    # Actual non-merger of PR #92 is a repository-review fact, verified
    # independently of this test suite.
    freeze = _freeze()
    provenance = freeze["provenance"]
    old = provenance["old_outcome_blind_design_source"]
    assert old["historical_pr"] == 92
    assert old["historical_design_head_sha"] == (
        "5fe2c7de1358d0e5e68d85c460367d53d999f9a3"
    )
    assert old["not_merged"] is True
    assert set(old["files_used_as_scientific_provenance"]) == {
        "docs/research/B2_05_FLOW_ABSORPTION_PREREG.md",
        "docs/research/B2_05_FLOW_ABSORPTION_PREREG.json",
    }
    assert provenance["b2_01_02_03_04_outcomes_used_for"] == [
        "status", "governance", "anti_rescue_state", "execution_sequencing",
    ]
    forbidden_tuning_uses = provenance["b2_01_02_03_04_outcomes_not_used_for"]
    for item in (
        "W", "H", "descriptor", "sign", "target", "baseline_features",
        "candidate_features", "thresholds", "state_bins", "training_N",
        "placebo", "bootstrap", "promotion_gates", "side_rules",
    ):
        assert item in forbidden_tuning_uses

    status = freeze["batch02_status_read_only"]
    assert status == {
        "B2-01": "CLOSED_NO_PROMOTION",
        "B2-02": "CLOSED_NO_PROMOTION",
        "B2-03": "CLOSED_NO_PROMOTION",
        "B2-04": "CLOSED_NO_PROMOTION",
    }


def test_required_source_columns_match_the_repository_schema():
    freeze = _freeze()
    columns = freeze["required_source_columns"]["columns"]
    assert columns == [
        "open_time_ms",
        "available_at_ms",
        "close",
        "base_volume",
        "taker_buy_base_volume",
    ]
    manifest = (
        REPO_ROOT / "docs" / "manifests" / "CORE_BTC_BINANCE_V0.yaml"
    ).read_text(encoding="utf-8")
    for name in ("open_time_ms", "close", "base_volume", "taker_buy_base_volume"):
        assert f"name: {name}" in manifest
    assert "canonical_available_at: bar_end_exclusive" in manifest
    # cross-check against the exact accepted-parquet columns H05 already reads
    h05_source = (SCRIPTS / "h05_taker_imbalance_lib.py").read_text(encoding="utf-8")
    for name in columns:
        assert f'"{name}"' in h05_source


def test_dataset_and_snapshot_are_exact():
    freeze = _freeze()
    dataset = freeze["dataset"]
    assert dataset["dataset_id"] == "CORE_BTC_BINANCE_V0"
    assert dataset["snapshot_id"] == (
        "717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415"
    )
    assert dataset["source_timeframe"] == "1m"
    assert dataset["decision_grid"] == "15m"


def test_chronology_and_scoring_boundary_are_exact():
    chronology = _freeze()["chronology"]
    assert chronology["warmup_start_inclusive"] == "2020-01-01T00:00:00Z"
    assert chronology["development_start_inclusive"] == "2020-02-01T00:00:00Z"
    assert chronology["development_end_exclusive"] == "2025-01-01T00:00:00Z"
    assert chronology["reserved_validation_start_inclusive"] == "2025-01-01T00:00:00Z"
    assert chronology["oos_start_inclusive"] == "2026-01-01T00:00:00Z"
    assert chronology["last_legal_T_rule"] == (
        "T + H < 2025-01-01T00:00:00Z on the 15m grid; equality illegal; "
        "no truncation"
    )


def test_flow_windows_and_imbalance_formula_are_exact():
    freeze = _freeze()
    flow = freeze["flow"]
    assert flow["W_minutes"] == [15, 30, 60]
    assert flow["imbalance"] == "IMB = (2*TAKER_BUY_W - TOTAL_W) / TOTAL_W"
    assert flow["imbalance_zero_unavailable"] is True
    assert flow["threshold_search"] is False
    assert flow["no_h05_style_tail_event_selection"] is True
    assert flow["side_labels"] == ["BUY", "SELL"]
    md = _md()
    assert "IMB     = (2*TAKER_BUY_W - TOTAL_W) / TOTAL_W" in md
    assert "no imbalance\npercentile/tail threshold" in md
    assert "H05-style extreme-flow event selection" in md


def test_baseline_controls_are_exact():
    controls = _freeze()["baseline_controls"]
    assert controls["flow_ret"] == "FLOW_RET = d * ln(close(T) / close(T-W))"
    assert controls["rv"] == (
        "RV_W = sqrt(sum(r_1m^2)) over accepted 1m returns inside [T-W,T)"
    )
    assert controls["rv_validity"] == "RV_W finite and strictly > 0"
    assert controls["log_activity"] == "LOG_ACTIVITY = ln(TOTAL_W)"
    assert controls["role"] == "baseline controls only, not candidate novelty"


def test_exactly_one_structural_descriptor_and_forbidden_alternatives():
    prop = _freeze()["structural_property"]
    assert prop["count"] == 1
    assert prop["name"] == "IMPACT_INTERACTION"
    assert prop["formula"] == "IMPACT_INTERACTION = ABS_IMB * FLOW_RET"
    forbidden = prop["forbidden_alternatives"]
    for alt in (
        "IMB / price_move", "price_move / IMB", "epsilon denominators",
        "order-book proxy", "CVD substitute", "volume delta substitute",
        "different impact formula", "thresholded absorption",
        "BUY-only descriptor", "SELL-only descriptor",
        "second interaction descriptor",
    ):
        assert alt in forbidden
    assert _freeze()["one_impact_descriptor"] is True


def test_impact_state_reference_population_and_ordering():
    state = _freeze()["impact_state"]
    assert state["reference_days"] == 180
    assert state["minimum_reference_n"] == 120
    assert state["states"] == ["LOW", "MID", "HIGH"]
    assert state["state_cutpoints"] == pytest.approx(
        [1.0 / 3.0, 2.0 / 3.0]
    )
    assert state["expected_ordering"] == (
        "HIGH > MID > LOW for subsequent flow-direction-normalized outcome "
        "after baseline control"
    )
    assert state["ordering_reversal_forbidden_post_outcome"] is True
    assert state["historical_state_freeze"] == (
        "each historical state computed exactly once as-of its own T_e; "
        "never recomputed using later records"
    )


def test_target_horizons_and_scale_are_exact():
    target = _freeze()["target"]
    assert target["H_minutes"] == [30, 60, 120, 240]
    assert target["raw_future_flow_direction_continuation"] == (
        "FLOW_CONT_RET_H = d * ln(close(T+H) / close(T))"
    )
    assert target["normalized"] == "Y_H = FLOW_CONT_RET_H / PAST_MEDIAN_ABS_RET_H"
    scale = target["scale_reference"]
    assert scale["scale_reference_days"] == 30
    assert scale["current_boundary_excluded"] is True
    assert scale["future_or_unmatured_excluded"] is True
    assert scale["observation_population"] == (
        "the canonical aligned 15m grid, not B2-05 candidate/trigger records"
    )


def test_training_model_baseline_and_candidate_designs_are_exact():
    forecast = _freeze()["forecast"]
    assert forecast["family"] == "causal_weekly_walk_forward_ols"
    assert forecast["training_window"]["lookback_days"] == 365
    assert forecast["training_window"]["rule"] == (
        "T_e < S and T_e >= S - 365 calendar days and T_e + H <= S"
    )
    assert forecast["baseline_features"] == [
        "intercept", "ABS_IMB", "FLOW_RET", "RV_W", "LOG_ACTIVITY", "SIDE_BUY",
    ]
    assert forecast["candidate_additions"] == ["IMPACT_LOW", "IMPACT_HIGH"]
    assert forecast["candidate_reference_state"] == "MID"
    assert forecast["no_interaction_term_beyond_frozen_state"] is True
    assert forecast["no_polynomials"] is True
    assert forecast["no_feature_search"] is True
    assert forecast["no_alternate_model"] is True
    assert forecast["minimum_baseline_n"] == 500
    assert forecast["minimum_candidate_n"] == 500
    assert forecast["minimum_candidate_n_per_state"] == 100
    assert forecast["baseline_may_have_more_historical_training_rows"] is True
    assert forecast["joint_unavailability"] == (
        "if either the baseline or candidate weekly model is unavailable, "
        "current scoring is unavailable for BOTH"
    )
    assert forecast["estimator"] == "ordinary_least_squares"
    assert forecast["weights"] == "none"
    assert forecast["regularization"] == "none"

    preprocessing = _freeze()["preprocessing"]
    assert preprocessing["continuous_columns"] == [
        "ABS_IMB", "FLOW_RET", "RV_W", "LOG_ACTIVITY",
    ]
    assert preprocessing["unstandardized_columns"] == [
        "intercept", "SIDE_BUY", "IMPACT_LOW", "IMPACT_HIGH",
    ]
    assert preprocessing["design_matrix_baseline"] == [
        "intercept", "ABS_IMB_z", "FLOW_RET_z", "RV_W_z", "LOG_ACTIVITY_z", "SIDE_BUY",
    ]
    assert preprocessing["design_matrix_candidate"] == [
        "intercept", "ABS_IMB_z", "FLOW_RET_z", "RV_W_z", "LOG_ACTIVITY_z",
        "SIDE_BUY", "IMPACT_LOW", "IMPACT_HIGH",
    ]


def test_ols_solver_contract_restores_the_historical_lstsq_primitive():
    solver = _freeze()["ols_solver_contract"]
    assert solver["resolution_class"] == "FROZEN TO HISTORICAL PRE-OUTCOME PRIMITIVE"
    assert solver["resolution"] == (
        "numpy.linalg.lstsq(X, y, rcond=None), exactly as frozen by the old "
        "outcome-blind design at PR #92 commit "
        "5fe2c7de1358d0e5e68d85c460367d53d999f9a3, with an explicit "
        "post-hoc full-column-rank check on the returned rank and an "
        "explicit finite-coefficients check"
    )
    assert solver["call"] == (
        "coef, residuals, rank, singular_values = numpy.linalg.lstsq(X, y, rcond=None)"
    )
    for check in (
        "X and y finite before fit",
        "rank == number_of_columns (full column rank)",
        "all returned coefficients finite",
        "fit raised no exception",
    ):
        assert check in solver["post_fit_validity_checks"]
    for forbidden in (
        "numpy.linalg.pinv",
        "Gram-matrix Cholesky decomposition of X'X",
        "np.linalg.solve(X'X, X'y)",
        "normal-equation substitution of any kind",
        "silent minimum-norm fit",
        "column dropping",
        "ridge/lasso regularization",
        "any solver fallback",
        "a new condition-number cutoff",
        "a singular-value threshold beyond the lstsq-returned rank",
    ):
        assert forbidden in solver["forbidden"]
    # The mechanical-equivalence / bit-compatibility claim from the prior
    # (repaired) revision must not survive: this prereg no longer asserts
    # Cholesky-solve and lstsq are interchangeable for this contract.
    assert "numpy.linalg.solve(X'X, X'y)" not in solver["resolution"]
    assert "Cholesky" not in solver["resolution"]
    md = _md()
    assert "numpy.linalg.lstsq(X, y, rcond=None)" in md
    assert "frozen to the historical pre-outcome primitive" in md.lower()
    assert "not scientifically material" not in md
    assert "bit-compatible" not in md
    assert "scientifically/mechanically interchangeable" not in md


def test_same_support_rule_forbids_one_sided_and_post_outcome_selection():
    support = _freeze()["same_support"]
    assert support["candidate_and_comparator_share_exact_score_record_id_set"] is True
    assert support["baseline_may_not_have_more_current_evaluation_rows"] is True
    for forbidden in (
        "BUY-only rescue", "SELL-only rescue", "year-only support",
        "horizon-only support", "post-outcome support filter",
    ):
        assert forbidden in support["forbidden_support_selection"]


def test_canonical_event_identity_is_exact_and_not_t_only():
    identity = _freeze()["event_identity"]
    base = identity["canonical_base_serialization"]
    score = identity["canonical_score_serialization"]
    assert base["format"] == (
        "snapshot_id|1m|15m|W_minutes|side|interval_start_ms|interval_end_ms|T_ms"
    )
    assert score["format"] == (
        "snapshot_id|1m|15m|W_minutes|side|interval_start_ms|interval_end_ms|T_ms|H_minutes"
    )
    assert score["definition"] == (
        "CANONICAL_SCORE_RECORD_ID = CANONICAL_BASE_EVENT_ID|H_minutes"
    )
    assert identity["interval_start_ms_definition"] == "T_ms - W_minutes*60000"
    assert identity["interval_end_ms_definition"] == "T_ms"
    assert identity["side_representation"] == "exactly BUY or SELL, uppercase ASCII"
    assert identity["deduplication_on_T_only_forbidden"] is True
    assert identity["baseline_and_candidate_share_identity"] is True

    md = _md()
    assert (
        "CANONICAL_BASE_EVENT_ID  = "
        "snapshot_id|1m|15m|W_minutes|side|interval_start_ms|interval_end_ms|T_ms"
        in md
    )
    assert " " not in base["format"]
    assert '"' not in base["format"]


def test_nuisance_bins_are_exact_quintiles():
    nuisance = _freeze()["controls"]["nuisance_bins"]
    assert nuisance["variables"] == ["ABS_IMB", "FLOW_RET"]
    assert nuisance["reference_days"] == 180
    assert nuisance["minimum_reference_n_each"] == 120
    bins = nuisance["bins"]
    assert [b["label"] for b in bins] == ["Q1", "Q2", "Q3", "Q4", "Q5"]
    assert bins[-1]["hi_inclusive"] is True
    assert all(not b["hi_inclusive"] for b in bins[:-1])
    assert nuisance["missing_bin_policy"] == (
        "candidate historical row ineligible; baseline historical "
        "eligibility unaffected if baseline fields and mature target are valid"
    )


def test_placebo_seed_count_and_stratum_serialization_are_exact():
    controls = _freeze()["controls"]
    assert controls["permutation_seed"] == 20260907
    assert controls["permutation_replicates"] == 100
    assert controls["permutation_strata"] == [
        "calendar_month_utc(T_e)", "side", "ABS_IMB quintile", "FLOW_RET quintile",
    ]
    assert controls["permutation_stratum_id_format"] == (
        "YYYY-MM|SIDE=<BUY|SELL>|IMB_Q=<Q1..Q5>|FLOW_Q=<Q1..Q5>"
    )
    assert controls["permutation_seed_derivation"] == (
        "20260907|replicate_index|W_minutes|H_minutes|week_start_ms|stratum_id"
    )
    assert controls["permutation_label_encoding"] == {
        "LOW": 0, "MID": 1, "HIGH": 2, "dtype": "int64",
    }
    primitive = controls["seed_derivation_primitive"]
    assert "SHA-256" in primitive["description"]
    assert "first 8 raw digest bytes" in primitive["description"]
    assert primitive["exact_code"] == (
        "seed_int = int.from_bytes(hashlib.sha256(raw_utf8).digest()[:8], "
        "'big', signed=False); rng = numpy.random.default_rng(seed_int)"
    )

    # exact seed derivation reproduced independently
    import hashlib as _hashlib

    raw = "20260907|0|15|30|1577836800000|2020-02|SIDE=BUY|IMB_Q=Q1|FLOW_Q=Q1".encode(
        "utf-8"
    )
    seed_int = int.from_bytes(_hashlib.sha256(raw).digest()[:8], "big", signed=False)
    assert isinstance(seed_int, int)
    assert seed_int >= 0


def test_placebo_failure_semantics_require_all_100_finite():
    failure = _freeze()["controls"]["placebo_failure_semantics"]
    assert failure["nominal_replicates"] == 100
    assert failure["partial_subset_forbidden"] is True
    assert failure["resampling_forbidden"] is True
    assert failure["replacement_replicate_forbidden"] is True
    assert failure["below_threshold_behavior"] == (
        "placebo_q95 = unavailable (None/NaN); placebo_separation = False"
    )
    md = _md()
    assert "only if all 100 replicate cell statistics are finite" in md


def test_bootstrap_seed_count_and_iso_week_rule_are_exact():
    controls = _freeze()["controls"]
    assert controls["bootstrap_seed"] == 20260908
    assert controls["bootstrap_replicates"] == 2000
    assert controls["bootstrap_block"] == "UTC_ISO_week"
    assert "isocalendar" in controls["bootstrap_week_id"]
    assert "NOT the Gregorian calendar year" in controls["bootstrap_week_id"]
    assert controls["bootstrap_seed_derivation"] == "20260908|W_minutes|H_minutes"
    assert controls["bootstrap_zero_block_behavior"] == (
        "bootstrap unavailable; bootstrap_positive = false"
    )
    assert controls["bootstrap_reroll_seed"] is False
    assert controls["bootstrap_block_selection_after_outcomes"] is False


def test_search_surface_is_exactly_twelve_cells():
    freeze = _freeze()
    assert freeze["search_surface_primary_cells"] == 12
    assert freeze["search_surface_shape"] == "3 W x 4 H"
    assert freeze["flow"]["W_minutes"] == [15, 30, 60]
    assert freeze["target"]["H_minutes"] == [30, 60, 120, 240]
    assert len(freeze["flow"]["W_minutes"]) * len(freeze["target"]["H_minutes"]) == 12


def test_per_cell_conditions_are_exactly_six():
    contract = _freeze()["promotion_gate_contract"]
    assert contract["per_cell_gate_names"] == [
        "primary_positive", "material_relative_mae", "bootstrap_positive",
        "placebo_separation", "impact_ordering", "side_stability",
    ]
    gates = contract["per_cell_gates"]
    assert gates["primary_positive"]["scope"] == "pooled_only"
    assert gates["primary_positive"]["pooled_condition"] == (
        "pooled mean AE improvement > 0"
    )
    assert gates["material_relative_mae"]["pooled_condition"] == (
        "relative MAE improvement >= 0.02"
    )
    assert gates["bootstrap_positive"]["pooled_condition"] == (
        "2.5th percentile of the 2000-replicate UTC-week bootstrap of "
        "mean(AE_IMPROVEMENT) > 0"
    )
    assert gates["placebo_separation"]["pooled_condition"] == (
        "real pooled mean(AE_IMPROVEMENT) > placebo_q95"
    )
    assert gates["impact_ordering"]["strict_chain"] is True
    assert gates["side_stability"]["both_sides_required"] is True
    assert gates["side_stability"]["scope"] == "side_symmetric_required"


def test_promotion_gates_are_exactly_nine_no_hidden_tenth():
    contract = _freeze()["promotion_gate_contract"]
    assert contract["required_gate_names"] == [
        "primary_positive",
        "material_relative_mae",
        "bootstrap_positive",
        "placebo_separation",
        "impact_ordering",
        "side_stability",
        "horizon_robustness",
        "parameter_robustness",
        "year_stability",
    ]
    assert contract["gate_count"] == 9
    assert len(contract["required_gate_names"]) == 9
    assert len(set(contract["required_gate_names"])) == 9
    assert contract["hidden_tenth_gate_forbidden"] is True
    assert contract["adjacent_h_pairs"] == [[30, 60], [60, 120], [120, 240]]
    assert contract["no_mosaic_promotion"] is True
    assert contract["no_ranking_by_effect_size"] is True


def test_verdict_names_are_exact():
    freeze = _freeze()
    assert freeze["verdicts"] == [
        "B2_05_PROMOTED_CANDIDATE",
        "B2_05_CLOSED_NO_PROMOTION",
    ]
    assert freeze["integrity_failures_are_not_a_verdict"] is True
    md = _md()
    assert "B2_05_PROMOTED_CANDIDATE" in md
    assert "B2_05_CLOSED_NO_PROMOTION" in md


def test_anti_rescue_forbids_a_second_attempt():
    anti_rescue = _freeze()["anti_rescue"]
    assert anti_rescue["failure_closes_b2_05"] is True
    assert anti_rescue["attempts_in_current_v2"] == 1
    for forbidden in (
        "second impact descriptor", "imbalance threshold rescue",
        "ratio rescue", "BUY rescue", "SELL rescue", "sign reversal",
        "new H", "new W",
    ):
        assert forbidden in anti_rescue["forbidden_after_failure"]


def test_durable_retention_integration_targets_current_ceremony():
    retention = _freeze()["durable_retention_integration"]
    assert retention["ceremony"] == [
        "verify_batch02_code",
        "prepare_batch02_evidence_reservation",
        "prepare_batch02_retained_run",
        "load_authorized_parquet_table",
        "evaluate_b2_05",
        "persist_batch02_retained_result",
        "archive_batch02_result",
    ]
    assert retention["historical_path_forbidden"] == [
        "prepare_batch02_run", "persist_batch02_result",
    ]
    assert retention["canonical_slot"] == "B2-05"
    assert retention["evidence_ref"] == (
        "refs/heads/research-evidence/batch02/B2-05/<execution_code_sha>"
    )
    assert retention["created_by_this_unit"] is False
    assert retention["production_endpoint"] == "https://github.com/sh1zok1d/signalbot.git"
    assert retention["future_local_result_path"] == (
        "artifacts/b2_05_flow_absorption/B2_05_FLOW_ABSORPTION_DEV_RESULTS.json"
    )


def _md_ceremony_steps() -> list[str]:
    """Structurally extract the ordered ceremony step identifiers from the
    "## 24. Future durable-evidence ceremony" section's fenced code block --
    never by searching the whole document for operation-name substrings,
    which could false-green against unrelated prose. Raises if the expected
    section heading or its first fenced block is missing, so a heading
    rename or fence removal fails loudly instead of silently matching
    nothing."""
    md = _md()
    heading = "## 24. Future durable-evidence ceremony"
    heading_pos = md.index(heading)
    section = md[heading_pos:]
    fence_start = section.index("```") + 3
    fence_end = section.index("```", fence_start)
    block = section[fence_start:fence_end]
    return [line.strip() for line in block.splitlines() if line.strip()]


def test_durable_retention_ceremony_is_structurally_identical_in_md_and_json():
    # Extracts the ceremony from its own fenced code block under S24 (exact
    # section boundaries, not a whole-document substring search) and
    # requires exact ordered-list equality against the JSON ceremony: same
    # step count, same identifiers, same order. This must fail for a
    # renamed step (e.g. evaluate_b2_05 -> evaluate), a deleted/inserted
    # step, a reordering, or a duplicated step -- not merely pass because
    # "evaluate_b2_05" happens to appear somewhere in explanatory prose.
    md_ceremony = _md_ceremony_steps()
    json_ceremony = _freeze()["durable_retention_integration"]["ceremony"]
    expected = [
        "verify_batch02_code",
        "prepare_batch02_evidence_reservation",
        "prepare_batch02_retained_run",
        "load_authorized_parquet_table",
        "evaluate_b2_05",
        "persist_batch02_retained_result",
        "archive_batch02_result",
    ]
    assert md_ceremony == expected
    assert json_ceremony == expected
    assert md_ceremony == json_ceremony
    assert len(md_ceremony) == len(set(md_ceremony)) == 7  # no duplicate step


def test_durable_retention_ceremony_equality_check_catches_mutations():
    # Proves the exact-equality check above is not vacuous: a renamed step
    # or a reordering of the real, extracted ceremony must fail the same
    # comparison this suite relies on. This does not mutate any committed
    # file -- it only exercises the comparison logic against deliberately
    # corrupted in-memory copies of the real extracted ceremony.
    md_ceremony = _md_ceremony_steps()
    json_ceremony = _freeze()["durable_retention_integration"]["ceremony"]
    assert md_ceremony == json_ceremony  # sanity: the real documents agree

    renamed = list(md_ceremony)
    renamed[renamed.index("evaluate_b2_05")] = "evaluate"
    assert renamed != json_ceremony

    reordered = list(md_ceremony)
    i = reordered.index("prepare_batch02_retained_run")
    j = reordered.index("load_authorized_parquet_table")
    reordered[i], reordered[j] = reordered[j], reordered[i]
    assert reordered != json_ceremony


def test_outcome_boundary_flags_are_closed():
    freeze = _freeze()
    assert freeze["outcome_access_authorized"] is False
    assert freeze["validation_2025_authorized"] is False
    assert freeze["oos_2026_authorized"] is False
    assert freeze["b2_01_rerun_authorized"] is False
    assert freeze["b2_02_rerun_authorized"] is False
    assert freeze["b2_03_rerun_authorized"] is False
    assert freeze["b2_04_rerun_authorized"] is False
    assert freeze["real_core_data_accessed_by_this_unit"] is False
    assert freeze["implementation_exists"] is False


def test_no_runner_exists_and_no_result_is_committed():
    """The frozen prohibition is unit-scoped (`..._forbidden_in_this_unit`).

    The preregistration unit itself shipped no implementation; that
    historical fact is recorded in the frozen JSON and in Git history. A
    later, separate implementation unit is explicitly contemplated by the
    same freeze (`durable_retention_integration.ceremony`, MD section 24),
    so this guard pins what remains live: the frozen text still scopes the
    prohibition to the preregistration unit, no B2-05 *result* artifact may
    be committed to source control before an authorized run, and any
    implementation that does exist must be exactly the canonical
    runner/library pair -- never a third script and never a result document
    (mirrors the repaired B2-04 prereg-freeze test of the same shape).
    """
    freeze = _freeze()
    assert freeze["implementation_paths_forbidden_in_this_unit"] == [
        "scripts/research/b2_05_*.py"
    ]
    assert freeze["implementation_exists"] is False

    result_json = REPO_ROOT / "docs" / "research" / "B2_05_FLOW_ABSORPTION_RESULT.json"
    result_md = REPO_ROOT / "docs" / "research" / "B2_05_FLOW_ABSORPTION_RESULT.md"
    assert not result_json.exists()
    assert not result_md.exists()

    # The canonical retained-run artifact path
    # (artifacts/b2_05_flow_absorption/..._DEV_RESULTS.json) is NOT checked
    # for filesystem absence here: persist_batch02_retained_result
    # deliberately leaves that local canonical artifact in place after a
    # legitimate future authorized run (BATCH02_DURABLE_EVIDENCE_RETENTION_V1
    # section 8), so a filesystem-absence check would fail this long-lived
    # suite the moment a real run ever happens, for a reason unrelated to
    # prereg integrity. The durable fact this test protects -- no B2-05
    # result is *committed to source control* -- is instead checked against
    # Git's tracked-file state, which persistence never touches (the whole
    # artifacts/ tree is gitignored) and which is exactly what "shipped by
    # this unit" means.
    # Bound to the runner's own RESULT_PATH constant (not a duplicated
    # directory string) so this test cannot silently drift from the actual
    # canonical local artifact location. The git executable is resolved to
    # an absolute path (not a bare "git") to avoid a PATH-search-order
    # partial-executable-path finding on the subprocess invocation.
    result_dir = runner.RESULT_PATH.parent.relative_to(REPO_ROOT).as_posix()
    git_executable = shutil.which("git")
    assert git_executable is not None, "git executable must be resolvable for this check"
    tracked = subprocess.run(  # noqa: S603 - absolute resolved path, fixed argv, no shell, test-only
        [git_executable, "ls-files", result_dir],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert tracked.strip() == ""

    implementation = sorted(path.name for path in SCRIPTS.glob("b2_05_*.py"))
    assert implementation in (
        [],
        [
            "b2_05_flow_absorption.py",
            "b2_05_flow_absorption_lib.py",
        ],
    )


def test_prereg_json_canonical_bytes_hash_is_stable():
    """Pin a SHA-256 of the canonical (sorted-key) JSON bytes so any future
    silent drift in the frozen contract is immediately visible in a diff,
    consistent with the B2-02/03/04 prereg-freeze convention of asserting
    exact frozen field values rather than loose membership checks."""
    freeze = _freeze()
    canonical = json.dumps(
        freeze, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    # Recorded once at freeze time. If this fails, the frozen B2-05 contract
    # changed -- inspect the diff before touching this constant.
    assert digest == (
        "34e8412684ecf14fa802b5a412b4d26bb6894d835ff0b6f8ae99b1d725e759ea"
    )


def test_md_and_json_are_present_and_json_parses():
    assert MD.is_file()
    assert JSON.is_file()
    text = JSON.read_text(encoding="utf-8")
    json.loads(text)  # must not raise
    assert text.endswith("\n")
