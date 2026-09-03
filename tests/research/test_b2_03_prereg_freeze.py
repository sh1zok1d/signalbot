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
        "20260904 | replicate_index | W_minutes | H_minutes | T_ms | baseline_stratum_id"
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


# --- Repair unit: complete per-cell promotion contract + anti-rescue repair ---


def test_b2_03_per_cell_gates_are_structurally_complete_in_json():
    """All five per-cell gates must carry an actual, exact machine-readable
    definition, not a bare boolean and not a loose substring match. Every
    condition string is pinned by exact equality so that a future change to
    an operator (e.g. `> 0` -> `>= 0`) or to the underlying statistic (e.g.
    the bootstrap lower bound swapped for a different 95% statistic) breaks
    this test."""
    gates = _freeze()["promotion_gate_contract"]["per_cell_gates"]
    assert set(gates) == {
        "primary_positive",
        "material_relative_mae",
        "bootstrap_positive",
        "placebo_separation",
        "morphology_ordering",
    }

    assert gates["primary_positive"] == {
        "scope": "pooled_and_side_symmetric",
        "pooled_condition": "pooled mean AE improvement > 0",
        "up_condition": "UP mean AE improvement > 0",
        "down_condition": "DOWN mean AE improvement > 0",
        "requires_all_finite": True,
    }

    assert gates["material_relative_mae"] == {
        "scope": "pooled_only",
        "pooled_condition": "relative MAE improvement >= 0.02",
        "relative_mae_improvement_definition": "1 - mean(CAND_AE)/mean(BASE_AE)",
    }

    assert gates["bootstrap_positive"] == {
        "scope": "pooled_only",
        "pooled_condition": (
            "95% UTC-week block-bootstrap lower bound for mean AE improvement > 0"
        ),
    }

    assert gates["placebo_separation"] == {
        "scope": "pooled_only",
        "pooled_condition": "true mean AE improvement > placebo_q95",
        "placebo_q95_definition": (
            "95th percentile of the frozen 100 causal permutation replicates "
            "(controls.permutation_replicates)"
        ),
    }

    assert gates["morphology_ordering"] == {
        "scope": "pooled_and_side_symmetric",
        "definition": (
            "BASE_RESIDUAL = Y_H - BASE_PRED; "
            "MORPHOLOGY_SEPARATION(subset) = median(BASE_RESIDUAL | "
            "MORPHOLOGY_STATE=HIGH, subset) - median(BASE_RESIDUAL | "
            "MORPHOLOGY_STATE=LOW, subset)"
        ),
        "same_scored_support_required": True,
        "pooled_condition": "MORPHOLOGY_SEPARATION(pooled) > 0",
        "up_condition": "MORPHOLOGY_SEPARATION(direction=UP) > 0",
        "down_condition": "MORPHOLOGY_SEPARATION(direction=DOWN) > 0",
        "requires_all_finite": True,
    }


def test_b2_03_md_pins_exact_per_cell_gate_clauses():
    """The Markdown must carry the same operative semantics as the JSON gate
    contract, pinned exactly enough that a changed operator or a changed
    statistic (e.g. bootstrap lower bound -> another 95% statistic) breaks
    this test, not merely a missing keyword."""
    md = MD.read_text(encoding="utf-8")

    assert (
        "- `primary_positive`: **pooled** mean AE improvement `> 0` **and** "
        "**`UP`** mean AE improvement `> 0` **and** **`DOWN`** mean AE improvement "
        "`> 0`; all three finite (§20.1)." in md
    )
    assert (
        "- `material_relative_mae`: pooled relative MAE improvement `>= 0.02`, "
        "where relative MAE improvement `= 1 - mean(CAND_AE)/mean(BASE_AE)` on "
        "the pooled scored support (§15)." in md
    )
    assert (
        "- `bootstrap_positive`: pooled 95% UTC-week block-bootstrap lower "
        "bound for mean AE improvement `> 0` (§18)." in md
    )
    assert (
        "- `placebo_separation`: pooled true mean AE improvement `>` placebo "
        "q95, where placebo q95 is the 95th percentile of the frozen 100 "
        "causal permutation replicates (§17) on the pooled scored support." in md
    )
    assert (
        "- `morphology_ordering`: **pooled** `MORPHOLOGY_SEPARATION > 0` "
        "**and** **`UP`** `MORPHOLOGY_SEPARATION > 0` **and** **`DOWN`** "
        "`MORPHOLOGY_SEPARATION > 0` (§16); all three finite, all three "
        "computed on the exact same scored support as the candidate/baseline "
        "comparison for that cell (§20.1)." in md
    )


def test_b2_03_anti_rescue_side_symmetry_does_not_add_a_ninth_gate():
    freeze = _freeze()
    contract = freeze["promotion_gate_contract"]
    anti_rescue = contract["anti_rescue_side_symmetry"]
    assert anti_rescue["applies_to_gates"] == ["primary_positive", "morphology_ordering"]
    assert anti_rescue["adds_new_gate_name"] is False
    assert anti_rescue["creates_direction_specific_promotion_path"] is False
    assert anti_rescue["pooled_cell_remains_primary_statistical_unit"] is True
    # Still exactly the frozen eight gate names -- no ninth gate introduced.
    assert len(contract["required_gate_names"]) == 8
    assert "up_only" not in contract["required_gate_names"]
    assert "down_only" not in contract["required_gate_names"]


def test_b2_03_md_no_longer_claims_pooling_alone_blocks_one_sided_rescue():
    md = MD.read_text(encoding="utf-8")
    # The repaired document must state the anti-rescue mechanism explicitly
    # rather than the retired (false) claim that pooling by itself prevents
    # a one-sided rescue.
    assert "does not, by itself, block this" in md
    assert "### 20.1 Anti-rescue side-symmetry subconditions" in md
    # Self-red-team item 11 must reflect the strengthened gates, not bare pooling.
    assert (
        "`primary_positive` requires pooled **and** `UP` **and** `DOWN` mean AE "
        "improvement each `> 0` and finite" in md
    )


def test_b2_03_reporting_contract_includes_up_down_partitions():
    reporting = _freeze()["reporting_contract"]
    assert "up" in reporting["per_cell_side_partition_minimum"]
    assert "down" in reporting["per_cell_side_partition_minimum"]
    for side in ("up", "down"):
        fields = reporting["per_cell_side_partition_minimum"][side]
        assert "N" in fields
        assert "mean_ae_improvement" in fields
        assert f"morphology_separation_{side}" in fields

    md = MD.read_text(encoding="utf-8")
    assert "`UP N`; `DOWN N`" in md
    assert "MORPHOLOGY_SEPARATION_UP" in md
    assert "MORPHOLOGY_SEPARATION_DOWN" in md


def test_b2_03_morphology_separation_formula_has_pooled_up_down_variants():
    md = MD.read_text(encoding="utf-8")
    assert "MORPHOLOGY_SEPARATION_POOLED" in md
    assert "MORPHOLOGY_SEPARATION_UP" in md
    assert "MORPHOLOGY_SEPARATION_DOWN" in md
    assert "exact same scored support used by the candidate/baseline comparison" in md


def test_b2_03_canonical_event_id_serialization_is_frozen():
    serialization = _freeze()["event_identity"]["canonical_serialization"]
    assert serialization["format"] == (
        "snapshot_id|1m|5m|1h|W_minutes|direction|window_start_ms|window_end_ms|T_ms|H_minutes"
    )
    assert serialization["delimiter"] == "|"
    assert serialization["field_order"] == [
        "snapshot_id",
        "source_timeframe",
        "derived_timeframe",
        "decision_grid",
        "W_minutes",
        "direction",
        "window_start_ms",
        "window_end_ms",
        "T_ms",
        "H_minutes",
    ]
    assert serialization["timestamp_representation"] == "integer UTC epoch milliseconds"
    assert serialization["window_start_ms_definition"] == "T_ms - W_minutes*60000"
    assert serialization["window_end_ms_definition"] == "T_ms"
    assert serialization["no_alternate_repr_permitted"] is True

    md = MD.read_text(encoding="utf-8")
    assert "### 6.1 Frozen canonical event-ID serialization" in md
    # The Markdown literal must be byte-for-byte identical to
    # event_identity.canonical_serialization.format above: no spaces around
    # "|", no quote characters around the fixed timeframe/grid segments.
    assert (
        "CANONICAL_EVENT_ID = "
        "snapshot_id|1m|5m|1h|W_minutes|direction|window_start_ms|window_end_ms|T_ms|H_minutes"
        in md
    )
    assert 'CANONICAL_EVENT_ID = snapshot_id | "1m"' not in md
    assert '"1m" | "5m"' not in md


def test_b2_03_canonical_event_id_rejects_alternative_serializations():
    """An alias/alternative serialization (e.g. ISO timestamps, a repr()/tuple
    form, or a differently-ordered field list) must not silently satisfy the
    frozen contract -- the frozen format is the only permitted one."""
    serialization = _freeze()["event_identity"]["canonical_serialization"]

    # ISO-8601 timestamps are explicitly not the frozen representation.
    assert serialization["timestamp_representation"] != "ISO-8601"
    assert "ISO" not in serialization["timestamp_representation"]

    # A Python tuple/dict repr is explicitly excluded.
    assert serialization["no_alternate_repr_permitted"] is True

    # Field order is exact and would not tolerate e.g. H_minutes before T_ms.
    reordered = list(serialization["field_order"])
    reordered[-1], reordered[-2] = reordered[-2], reordered[-1]
    assert reordered != serialization["field_order"]


def test_b2_03_baseline_stratum_id_serialization_is_frozen():
    controls = _freeze()["controls"]
    stratum = controls["baseline_stratum_id_serialization"]
    assert stratum["format"] == "W_minutes|direction|DISPLACEMENT_MAG_STATE|VOL_STATE"
    assert stratum["delimiter"] == "|"
    assert stratum["field_order"] == [
        "W_minutes",
        "direction",
        "DISPLACEMENT_MAG_STATE",
        "VOL_STATE",
    ]

    seed_primitive = controls["seed_derivation_primitive"]
    assert "SHA-256" in seed_primitive["description"]
    assert "first 16 hex digits" in seed_primitive["description"]
    assert seed_primitive["no_alternate_hash_permitted"] is True
    assert controls["current_T_representation"].startswith(
        "T_ms: integer UTC epoch milliseconds"
    )

    md = MD.read_text(encoding="utf-8")
    assert "### 17.1 Frozen baseline-stratum-ID serialization" in md
    assert "### 17.2 Frozen per-replicate seed derivation" in md
    # Byte-for-byte identical to controls.baseline_stratum_id_serialization.format:
    # no spaces around "|".
    assert (
        "BASELINE_STRATUM_ID = W_minutes|direction|DISPLACEMENT_MAG_STATE|VOL_STATE" in md
    )
    assert "BASELINE_STRATUM_ID = W_minutes | direction" not in md


def test_b2_03_pre_vol_60_boundary_is_pinned_to_exactly_60_returns():
    vol_boundary = _freeze()["baseline_context"]["vol_boundary"]
    assert vol_boundary["return_count"] == 60
    assert vol_boundary["anchor"] == "close(T-60m)"
    assert vol_boundary["last_return_bar_end_exclusive"] == "T"
    assert vol_boundary["bar_coverage"] == "[T-60m, T)"

    pre_vol_formula = _freeze()["baseline_context"]["formulas"]["PRE_VOL_60"]
    assert "sum_{i=1..60}" in pre_vol_formula
    assert "close_0=close(T-60m)" in pre_vol_formula

    md = MD.read_text(encoding="utf-8")
    assert "Freeze exactly 60 one-minute returns per decision time" in md
    assert "no 59-return or 61-return interpretation" in md


def test_b2_03_existing_retention_ceremony_and_outcome_flags_unaffected_by_repair():
    freeze = _freeze()
    assert freeze["outcome_access_authorized"] is False
    assert freeze["validation_2025_authorized"] is False
    assert freeze["oos_2026_authorized"] is False
    assert freeze["durable_retention_integration"]["canonical_slot"] == "B2-03"
    # Frozen surface/design constants preserved verbatim by this repair.
    assert freeze["search_surface_primary_cells"] == 15
    assert freeze["forecast"]["baseline_min_count"] == 80
    assert freeze["forecast"]["candidate_min_count"] == 40
    assert freeze["controls"]["permutation_replicates"] == 100
    assert freeze["controls"]["bootstrap_replicates"] == 2000
