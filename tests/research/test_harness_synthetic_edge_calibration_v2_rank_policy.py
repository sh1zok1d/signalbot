"""Fixture-only tests for V2 rank-degeneracy policy.

Tiny synthetic worlds and constructed aggregates only. These tests must not
run the frozen 3200-world grid, mint RESULT/WORLD_RECORDS, create ARM, or
consume V1 authority.
"""

from __future__ import annotations

import hashlib
import inspect
from pathlib import Path

import numpy as np
import pytest

from scripts.research import harness_synthetic_edge_calibration_v1_lib as lib
from scripts.research import harness_synthetic_edge_calibration_v1_production as prod
from scripts.research import harness_synthetic_edge_calibration_v2_rank_policy as v2

REPO = Path(__file__).resolve().parents[2]

FROZEN_LIB_SHA256 = "12230dcad714e3a06d3f57de69b78fedcab088be950af3d06f959366f01d6c51"
FROZEN_RUNNER_SHA256 = "0a5e577cc3797b018e9912865b7c3e385908764dc6cb36a6555626205855432a"
FROZEN_AUTH_SHA256 = "0e174ac6b73530ec28501b0c076e0cad7874ab31bb1ed6941e4b525d12e35507"
FROZEN_PRODUCTION_SHA256 = "9e784ecdcbd53ae4128d803d9325c8ff0f6db49ce70a0a63b13c4fc6a548a4ed"
FROZEN_WORKER_SHA256 = "9aee03fdae012f9054c59adc4cea8072b88493521456fb6141ced926961c886e"
FROZEN_WORKER_SIZE = 3994

ORIGINAL_COVERAGE_EXCEPTIONS = {
    ("SMALL|2500", "F01"): (0.65, 0.75),
    ("TINY_NOISY|5000", "F01"): (0.60, 0.70),
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rank_safe_world(n_rows: int = 50, scenario: str = "EASY") -> dict:
    """Synthetic arrays with era-local rank for intercept+X1+X2+Fj."""
    width = n_rows // 5
    pattern_x1 = np.array([-2.0, -1.5, -0.4, 0.3, 0.8, 1.2, 1.6, 2.0, -0.2, 0.5], dtype=np.float64)
    pattern_x2 = np.array([-2.0, -1.4, -0.3, 0.2, 0.7, 1.1, -1.2, 1.8, 0.1, -0.6], dtype=np.float64)
    pattern_s = np.array([0.0, 1.0, 0.0, 1.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0], dtype=np.float64)
    x1 = np.empty(n_rows, dtype=np.float64)
    x2 = np.empty(n_rows, dtype=np.float64)
    s = np.empty(n_rows, dtype=np.float64)
    for i in range(5):
        slc = slice(i * width, (i + 1) * width)
        x1[slc] = np.resize(pattern_x1, width)
        x2[slc] = np.resize(pattern_x2, width)
        s[slc] = np.resize(pattern_s, width)
    y = (0.20 * x1 - 0.15 * x2 + 0.25 * s + 0.01 * np.arange(n_rows, dtype=np.float64)).astype(
        np.float64
    )
    return {
        "Y": y,
        "X1": x1,
        "X2": x2,
        "S": s,
        "world_identity": lib.world_identity(scenario, n_rows, 0),
    }


def _eval(world, **kwargs):
    params = {
        "scenario": "EASY",
        "n_rows": int(np.asarray(world["Y"]).shape[0]),
        "world_index": 0,
    }
    params.update(kwargs)
    return v2.evaluate_v2_world(world, **params)


def _candidate_record(
    cid: str,
    state: str,
    *,
    detected: bool | None = False,
    reason: str | None = None,
    gates: dict | None = None,
) -> v2.CandidateWorldRecord:
    rec = v2.CandidateWorldRecord(candidate_id=cid, state=state, detected=detected, gates=gates)
    if reason:
        rec.nonidentifiability = v2.NonidentifiabilityRecord(
            candidate_id=cid,
            scenario="EASY",
            N=50,
            world_id="w",
            reason=reason,
            first_failing_era="E2" if reason == v2.REASON_RANK_DEFICIENT else v2.NOT_ERA_SCOPED,
        )
    return rec


def _world_record(
    *,
    world_id: str,
    world_state: str,
    L: int | None,
    taxonomy: str | None = None,
    selection_state: str | None = None,
    selected: str | None = None,
    nonidentifiable: tuple[str, ...] = (),
    scenario: str = "EASY",
    n: int = 50,
    gates: dict | None = None,
) -> v2.WorldRecordV2:
    rec = v2.WorldRecordV2(
        world_id=world_id,
        scenario=scenario,
        N=n,
        world_index=0,
        world_state=world_state,
        L=L,
        selection_state=selection_state,
        selected_candidate=selected,
        taxonomy=taxonomy,
    )
    for cid in lib.FEATURE_IDS:
        if world_state == v2.WORLD_INVALID:
            rec.candidates[cid] = _candidate_record(
                cid, v2.CANDIDATE_UNDEFINED_ON_INVALID_WORLD, detected=None
            )
        elif cid in nonidentifiable:
            rec.candidates[cid] = _candidate_record(
                cid, v2.CANDIDATE_NOT_IDENTIFIABLE, detected=None, reason=v2.REASON_RANK_DEFICIENT
            )
        else:
            rec.candidates[cid] = _candidate_record(
                cid,
                v2.CANDIDATE_IDENTIFIABLE,
                detected=bool(gates and gates.get("STRICT_PASS")),
                gates=gates,
            )
    return rec


def test_a_baseline_rank_deficient_is_world_invalid():
    world = _rank_safe_world()
    rec = _eval(world, zero_e1_baseline=True)
    assert rec.world_state == v2.WORLD_INVALID
    assert rec.L is None
    assert rec.taxonomy is None
    assert rec.baseline_failure is not None
    assert rec.baseline_failure.reason == v2.REASON_RANK_DEFICIENT
    assert rec.baseline_failure.first_failing_era == "E2"
    for cid in lib.FEATURE_IDS:
        assert rec.candidates[cid].state == v2.CANDIDATE_UNDEFINED_ON_INVALID_WORLD
        assert rec.candidates[cid].detected is None


def test_b_one_distractor_rank_deficient_world_remains_valid():
    world = _rank_safe_world()
    rec = _eval(world, zero_e1_features={"F04"})
    assert rec.world_state == v2.WORLD_VALID
    assert rec.candidates["F04"].state == v2.CANDIDATE_NOT_IDENTIFIABLE
    assert rec.candidates["F04"].detected is None
    for cid in lib.FEATURE_IDS:
        if cid == "F04":
            continue
        assert rec.candidates[cid].state == v2.CANDIDATE_IDENTIFIABLE
        assert rec.candidates[cid].detected is not None
    assert rec.L == 9


def test_c_f03_rank_deficient_is_not_false_negative():
    world = _rank_safe_world()
    rec = _eval(world, zero_e1_features={"F03"})
    assert rec.world_state == v2.WORLD_VALID
    f03 = rec.candidates["F03"]
    assert f03.state == v2.CANDIDATE_NOT_IDENTIFIABLE
    assert f03.detected is None
    assert f03.detected is not False
    assert rec.taxonomy != "NO_DISCOVERY" or rec.L < 10
    cell = v2.CellAggregateV2(scenario="EASY", N=50)
    cell.add(rec)
    assert cell.candidate_non_identifiable_count["F03"] == 1
    assert cell.candidate_detection_count["F03"] == 0
    assert cell.candidate_identifiable_count["F03"] == 0


def test_d_multiple_candidates_rank_deficient_correct_L():
    world = _rank_safe_world()
    rec = _eval(world, zero_e1_features={"F04", "F05", "F06"})
    assert rec.world_state == v2.WORLD_VALID
    assert rec.L == 7
    for cid in ("F04", "F05", "F06"):
        assert rec.candidates[cid].state == v2.CANDIDATE_NOT_IDENTIFIABLE
    for cid in ("F01", "F02", "F03", "F07", "F08", "F09", "F10"):
        assert rec.candidates[cid].state == v2.CANDIDATE_IDENTIFIABLE


def test_e_all_ten_nonidentifiable_is_L0_no_candidate_not_no_discovery():
    world = _rank_safe_world()
    rec = _eval(world, zero_e1_features=set(lib.FEATURE_IDS))
    assert rec.world_state == v2.WORLD_VALID
    assert rec.L == 0
    assert rec.selection_state == v2.SELECTION_NO_CANDIDATE
    assert rec.taxonomy is None
    assert rec.taxonomy != "NO_DISCOVERY"
    cell = v2.CellAggregateV2(scenario="EASY", N=50)
    cell.add(rec)
    schema = cell.result_schema()
    assert schema["worlds_with_zero_identifiable_candidates"] == 1
    assert schema["BLIND"]["pooled"]["BLIND_WORLD_COUNT"] == 0
    assert schema["BLIND"]["pooled"]["NO_DISCOVERY"] == 0


def test_f_L1_world():
    world = _rank_safe_world()
    rec = _eval(world, zero_e1_features=set(lib.FEATURE_IDS) - {"F09"})
    assert rec.world_state == v2.WORLD_VALID
    assert rec.L == 1
    assert rec.candidates["F09"].state == v2.CANDIDATE_IDENTIFIABLE
    assert rec.selection_state == v2.SELECTION_SELECTED


def test_g_L10_world():
    world = _rank_safe_world()
    rec = _eval(world)
    assert rec.world_state == v2.WORLD_VALID
    assert rec.L == 10
    for cid in lib.FEATURE_IDS:
        assert rec.candidates[cid].state == v2.CANDIDATE_IDENTIFIABLE


def test_h_L_distribution_reconciliation():
    records = [
        _world_record(world_id="inv", world_state=v2.WORLD_INVALID, L=None),
        _world_record(world_id="l0", world_state=v2.WORLD_VALID, L=0, nonidentifiable=lib.FEATURE_IDS),
        _world_record(world_id="l1", world_state=v2.WORLD_VALID, L=1, taxonomy="NO_DISCOVERY", selection_state=v2.SELECTION_SELECTED),
        _world_record(world_id="l10a", world_state=v2.WORLD_VALID, L=10, taxonomy="TRUE_DISCOVERY", selection_state=v2.SELECTION_SELECTED, selected="F03"),
        _world_record(world_id="l10b", world_state=v2.WORLD_VALID, L=10, taxonomy="NO_DISCOVERY", selection_state=v2.SELECTION_SELECTED),
    ]
    cell = v2.aggregate_v2_records(records)[("EASY", 50)]
    schema = cell.result_schema()
    assert schema["world_valid_count"] == 4
    assert schema["world_invalid_count"] == 1
    assert sum(schema["L_distribution"].values()) == schema["world_valid_count"]
    assert schema["L_distribution"]["L=0"] == 1
    assert schema["L_distribution"]["L=1"] == 1
    assert schema["L_distribution"]["L=10"] == 2


def test_i_pooled_blind_reconciles_to_L_strata():
    gates_pass = {k: False for k in (
        "primary_positive", "material_relative_mae", "bootstrap_positive",
        "placebo_separation", "era_stability", "support_sanity",
        "MODEL_DETECTED", "STRICT_PASS_EX_MATERIALITY", "STRICT_PASS",
    )}
    gates_f03 = dict(gates_pass)
    gates_f03.update({"STRICT_PASS": True, "STRICT_PASS_EX_MATERIALITY": True})
    records = [
        _world_record(
            world_id="l1t",
            world_state=v2.WORLD_VALID,
            L=1,
            taxonomy="TRUE_DISCOVERY",
            selection_state=v2.SELECTION_SELECTED,
            selected="F03",
            nonidentifiable=tuple(c for c in lib.FEATURE_IDS if c != "F03"),
            gates=gates_f03,
        ),
        _world_record(
            world_id="l2p",
            world_state=v2.WORLD_VALID,
            L=2,
            taxonomy="PROXY_DISCOVERY",
            selection_state=v2.SELECTION_SELECTED,
            selected="F01",
            nonidentifiable=tuple(c for c in lib.FEATURE_IDS if c not in {"F01", "F02"}),
            gates=gates_f03,
        ),
        _world_record(
            world_id="l3n",
            world_state=v2.WORLD_VALID,
            L=3,
            taxonomy="NO_DISCOVERY",
            selection_state=v2.SELECTION_SELECTED,
        ),
        _world_record(
            world_id="l0",
            world_state=v2.WORLD_VALID,
            L=0,
            selection_state=v2.SELECTION_NO_CANDIDATE,
            nonidentifiable=lib.FEATURE_IDS,
        ),
    ]
    cell = v2.aggregate_v2_records(records)[("EASY", 50)]
    schema = cell.result_schema()
    pooled = schema["BLIND"]["pooled"]
    by_l = schema["BLIND"]["by_L"]
    assert pooled["BLIND_WORLD_COUNT"] == 3
    assert pooled["TRUE_DISCOVERY"] == 1
    assert pooled["PROXY_DISCOVERY"] == 1
    assert pooled["NO_DISCOVERY"] == 1
    assert by_l[1]["TRUE_DISCOVERY"] == 1
    assert by_l[2]["PROXY_DISCOVERY"] == 1
    assert by_l[3]["NO_DISCOVERY"] == 1
    assert schema["BLIND"]["reconciliation_status"]["all_fields_reconcile"] is True
    assert pooled["BLIND_WORLD_COUNT"] == schema["world_valid_count"] - schema["worlds_with_zero_identifiable_candidates"]


def test_j_rank_failure_record_includes_diagnostics():
    world = _rank_safe_world()
    rec = _eval(world, zero_e1_features={"F04"})
    payload = rec.candidates["F04"].nonidentifiability.to_dict()
    assert payload["candidate_id"] == "F04"
    assert payload["scenario"] == "EASY"
    assert payload["N"] == 50
    assert payload["world_id"]
    assert payload["reason"] == v2.REASON_RANK_DEFICIENT
    assert payload["first_failing_era"] == "E2"
    assert payload["design_nrows"] == 10
    assert payload["design_ncols"] == 4
    assert payload["design_rank"] == 3
    assert payload["required_rank"] == 4


def test_k_first_failing_era_deterministic():
    world = _rank_safe_world()
    a = _eval(world, zero_e1_features={"F08"})
    b = _eval(world, zero_e1_features={"F08"})
    assert a.candidates["F08"].nonidentifiability.first_failing_era == "E2"
    assert a.candidates["F08"].nonidentifiability.first_failing_era == (
        b.candidates["F08"].nonidentifiability.first_failing_era
    )
    assert v2.choose_first_failing_era(["E5", "E2", "E4"]) == "E2"
    assert v2.choose_first_failing_era([v2.NOT_ERA_SCOPED]) == v2.NOT_ERA_SCOPED


def test_l_reason_precedence_deterministic():
    assert v2.CLOSED_REASON_TAXONOMY == (
        v2.REASON_RANK_DEFICIENT,
        v2.REASON_NONFINITE_FIT_OR_PREDICTION,
        v2.REASON_DESIGN_SHAPE_INVALID,
        v2.REASON_NONFINITE_AE_OR_RELATIVE_MAE,
        v2.REASON_NONFINITE_BOOTSTRAP,
        v2.REASON_NONFINITE_PLACEBO,
        v2.REASON_NONFINITE_VISIBILITY,
    )
    assert v2.choose_reason_by_precedence(
        [v2.REASON_NONFINITE_PLACEBO, v2.REASON_RANK_DEFICIENT, v2.REASON_DESIGN_SHAPE_INVALID]
    ) == v2.REASON_DESIGN_SHAPE_INVALID
    assert v2.choose_reason_by_precedence(
        [v2.REASON_NONFINITE_BOOTSTRAP, v2.REASON_NONFINITE_AE_OR_RELATIVE_MAE]
    ) == v2.REASON_NONFINITE_AE_OR_RELATIVE_MAE
    empty_y = np.array([], dtype=np.float64)
    insp = v2.inspect_design_window(empty_y, empty_y, empty_y, empty_y, scored_era="E2")
    assert insp.reason == v2.REASON_DESIGN_SHAPE_INVALID
    world = _rank_safe_world()
    rec = _eval(
        world,
        force_candidate_reason={"F10": v2.REASON_NONFINITE_BOOTSTRAP},
    )
    assert rec.candidates["F10"].nonidentifiability.reason == v2.REASON_NONFINITE_BOOTSTRAP
    assert rec.candidates["F10"].nonidentifiability.first_failing_era == v2.NOT_ERA_SCOPED


def test_m_insufficient_coverage_overrides_detection_success():
    conclusion = v2.mechanical_conclusion_v2(
        structurally_complete=True,
        coverage_for_conclusion=v2.COVERAGE_INSUFFICIENT,
        inherited_detection_conclusion="EASY_ORACLE_POWER_PASS",
    )
    assert conclusion == v2.MECHANICAL_INSUFFICIENT_IDENTIFIABILITY
    assert conclusion != "EASY_ORACLE_POWER_PASS"
    structural = v2.mechanical_conclusion_v2(
        structurally_complete=False,
        coverage_for_conclusion=v2.COVERAGE_INSUFFICIENT,
        inherited_detection_conclusion="EASY_ORACLE_POWER_PASS",
    )
    assert structural == v2.MECHANICAL_STRUCTURAL_INCOMPLETE


def test_n_null_conclusion_blocked_if_one_required_candidate_lacks_coverage():
    verdicts = {cid: v2.COVERAGE_ADEQUATE for cid in lib.FEATURE_IDS}
    verdicts["F07"] = v2.COVERAGE_INSUFFICIENT
    assert v2.null_claim_blocked_by_coverage(verdicts) is True
    status = v2.required_coverage_for_conclusion(
        "NULL_FALSE_POSITIVE_CONCLUSION",
        candidate_verdicts_by_cell={"NULL|5000": verdicts},
        baseline_verdicts_by_cell={"NULL|5000": v2.COVERAGE_ADEQUATE},
    )
    assert status == v2.COVERAGE_INSUFFICIENT
    all_ok = {cid: v2.COVERAGE_ADEQUATE for cid in lib.FEATURE_IDS}
    assert v2.null_claim_blocked_by_coverage(all_ok) is False
    assert (
        v2.required_coverage_for_conclusion(
            "NULL_FALSE_POSITIVE_CONCLUSION",
            candidate_verdicts_by_cell={"NULL|5000": all_ok},
            baseline_verdicts_by_cell={"NULL|5000": v2.COVERAGE_ADEQUATE},
        )
        == v2.COVERAGE_ADEQUATE
    )


def test_o_f01_small_2500_threshold_is_075():
    table = v2.frozen_coverage_thresholds_flat()
    assert table[("SMALL|2500", "F01")] == 0.75


def test_p_f01_tiny_noisy_5000_threshold_is_070():
    table = v2.frozen_coverage_thresholds_flat()
    assert table[("TINY_NOISY|5000", "F01")] == 0.70


def test_q_no_other_threshold_changed():
    changes = v2.amended_threshold_changes()
    assert changes == ORIGINAL_COVERAGE_EXCEPTIONS
    assert v2.coverage_table_entry_count() == 80
    original = v2.original_coverage_table()
    amended = v2.frozen_coverage_table()
    for cell, by_fid in original.items():
        for fid, before in by_fid.items():
            after = amended[cell][fid]
            if (cell, fid) in ORIGINAL_COVERAGE_EXCEPTIONS:
                assert after == ORIGINAL_COVERAGE_EXCEPTIONS[(cell, fid)][1]
            else:
                assert after == before


def test_r_blind_not_claimed_invariant_to_L():
    world = _rank_safe_world()
    rec = _eval(world)
    cell = v2.CellAggregateV2(scenario="EASY", N=50)
    cell.add(rec)
    schema = cell.result_schema()
    assert schema["BLIND"]["blind_not_claimed_invariant_to_L"] is True
    assert v2.implementation_identity()["blind_not_claimed_invariant_to_L"] is True


def test_s_zero_identifiable_per_cell_identity():
    records = [
        _world_record(world_id="a", world_state=v2.WORLD_VALID, L=0, nonidentifiable=lib.FEATURE_IDS),
        _world_record(world_id="b", world_state=v2.WORLD_VALID, L=0, nonidentifiable=lib.FEATURE_IDS),
        _world_record(world_id="c", world_state=v2.WORLD_VALID, L=10, taxonomy="NO_DISCOVERY", selection_state=v2.SELECTION_SELECTED),
    ]
    cell = v2.aggregate_v2_records(records)[("EASY", 50)]
    schema = cell.result_schema()
    assert schema["worlds_with_zero_identifiable_candidates"] == schema["L_distribution"]["L=0"] == 2


def test_t_world_invalid_excluded_from_L_distribution():
    records = [
        _world_record(world_id="inv1", world_state=v2.WORLD_INVALID, L=None),
        _world_record(world_id="inv2", world_state=v2.WORLD_INVALID, L=None),
        _world_record(world_id="ok", world_state=v2.WORLD_VALID, L=10, taxonomy="NO_DISCOVERY", selection_state=v2.SELECTION_SELECTED),
    ]
    cell = v2.aggregate_v2_records(records)[("EASY", 50)]
    schema = cell.result_schema()
    assert schema["world_invalid_count"] == 2
    assert schema["world_valid_count"] == 1
    assert sum(schema["L_distribution"].values()) == 1
    assert schema["L_distribution"]["L=10"] == 1
    with pytest.raises(ValueError, match="WORLD_INVALID L is undefined"):
        v2.add_l(v2.empty_l_distribution(), None)


def test_not_identifiable_is_neither_detected_nor_not_detected():
    world = _rank_safe_world()
    rec = _eval(world, zero_e1_features={"F02"})
    assert rec.candidates["F02"].detected is None
    assert rec.candidates["F02"].state != "FALSE"
    assert rec.candidates["F02"].gates is None


def test_blind_never_reintroduces_nonidentifiable():
    world = _rank_safe_world()
    rec = _eval(world, zero_e1_features={"F01", "F02", "F08"})
    assert rec.selected_candidate not in {"F01", "F02", "F08"}
    for cid in ("F01", "F02", "F08"):
        assert rec.candidates[cid].state == v2.CANDIDATE_NOT_IDENTIFIABLE


def test_coverage_uses_world_valid_not_planned_worlds():
    with pytest.raises(v2.UndefinedCoverageDenominator):
        v2.candidate_coverage_verdict(
            candidate_identifiable_count=400,
            world_valid_count=0,
            threshold=0.90,
        )
    verdict = v2.candidate_coverage_verdict(
        candidate_identifiable_count=150,
        world_valid_count=400,
        threshold=0.50,
    )
    assert verdict == v2.COVERAGE_INSUFFICIENT
    adequate = v2.candidate_coverage_verdict(
        candidate_identifiable_count=400,
        world_valid_count=400,
        threshold=0.90,
    )
    assert adequate == v2.COVERAGE_ADEQUATE


def test_required_coverage_map_is_exact_33():
    assert v2.required_coverage_map_count() == 33
    mapping = v2.frozen_required_coverage_map()
    assert "FINAL_OVERALL_MECHANICAL_CONCLUSION" in mapping
    assert "NULL_FALSE_POSITIVE_CONCLUSION" in mapping
    assert "VISIBILITY_FLOOR" in mapping
    assert mapping["VISIBILITY_FLOOR"]["world_baseline_only"] is True
    assert mapping["VISIBILITY_FLOOR"]["candidates"] == []


def test_oracle_f03_coverage_blocks_dependent_conclusion():
    status = v2.required_coverage_for_conclusion(
        "EASY_ORACLE_POWER",
        candidate_verdicts_by_cell={"EASY|5000": {"F03": v2.COVERAGE_INSUFFICIENT}},
        baseline_verdicts_by_cell={"EASY|5000": v2.COVERAGE_ADEQUATE},
    )
    assert status == v2.COVERAGE_INSUFFICIENT
    ok = v2.required_coverage_for_conclusion(
        "EASY_ORACLE_POWER",
        candidate_verdicts_by_cell={"EASY|5000": {"F03": v2.COVERAGE_ADEQUATE}},
        baseline_verdicts_by_cell={"EASY|5000": v2.COVERAGE_ADEQUATE},
    )
    assert ok == v2.COVERAGE_ADEQUATE


def test_selective_cell_combine_forbidden():
    v2.refuse_selective_cell_combine(prior_attempt_id=None, selective_cells=["EASY|5000"])
    with pytest.raises(v2.SelectiveCellCombineForbidden):
        v2.refuse_selective_cell_combine(
            prior_attempt_id="attempt-1",
            selective_cells=["TINY_NOISY|5000"],
        )


def test_production_grid_forbidden():
    with pytest.raises(v2.ProductionGridForbidden):
        v2.run_frozen_production_grid()
    with pytest.raises(v2.ProductionGridForbidden):
        v2.assert_not_production_grid(n_rows=5000)
    with pytest.raises(v2.ProductionGridForbidden):
        v2.assert_not_production_grid(planned_worlds=3200)
    with pytest.raises(v2.ProductionGridForbidden):
        v2.draw_fixture_world(scenario="EASY", n_rows=5000)


def test_wilson_matches_v1_lib():
    ours = lib.wilson_interval(380, 400)
    assert ours["lower"] == lib.wilson_interval(380, 400)["lower"]
    v2_verdict = v2.candidate_coverage_verdict(
        candidate_identifiable_count=380,
        world_valid_count=400,
        threshold=0.90,
    )
    assert v2_verdict == v2.COVERAGE_ADEQUATE
    assert lib.WILSON_Z == v2.WILSON_Z == 1.959963984540054


def test_v1_tcb_hashes_unchanged():
    assert _sha(REPO / prod.LIB_REL) == FROZEN_LIB_SHA256
    assert _sha(REPO / prod.RUNNER_REL) == FROZEN_RUNNER_SHA256
    assert _sha(REPO / prod.AUTH_REL) == FROZEN_AUTH_SHA256
    assert _sha(REPO / prod.PRODUCTION_REL) == FROZEN_PRODUCTION_SHA256
    worker = REPO / prod.WORKER_REL
    assert _sha(worker) == FROZEN_WORKER_SHA256
    assert worker.stat().st_size == FROZEN_WORKER_SIZE


def test_v1_scientific_constants_and_definitions_unchanged():
    assert lib.ROOT_SEED == 20260908
    assert lib.RHO == 0.90
    assert lib.FEATURE_IDS == tuple(f"F{i:02d}" for i in range(1, 11))
    assert lib.TRUE_FEATURES == frozenset({"F03"})
    assert lib.PROXY_FEATURES == frozenset({"F01", "F02", "F08"})
    assert lib.MATERIALITY_GATE == 0.02
    assert lib.PRODUCTION_BOOTSTRAP_REPLICATES == 500
    assert lib.PRODUCTION_PLACEBO_REPLICATES == 999
    assert lib.PRODUCTION_VISIBILITY_REPLICATES == 500
    assert lib.PRODUCTION_PLANNED_TOTAL_WORLDS == 3200
    src = inspect.getsource(lib.simulate_dgp)
    assert "rng.standard_normal(n)" in src
    assert "standard_t(5" in src
    feat_src = inspect.getsource(lib.candidate_features)
    assert "f01[1:] = s[:-1]" in feat_src
    assert "s * (x1 > 0.0)" in feat_src
    fit_src = inspect.getsource(lib.fit_lstsq)
    assert "matrix_rank" in fit_src
    assert "lstsq" in fit_src
    assert "pinv" not in fit_src
    assert "ridge" not in fit_src
    assert "design is not full rank" in fit_src


def test_v1_lib_fixture_world_still_runs():
    config = lib.FixtureExecutionConfig(
        n_rows=50,
        scenario_id="EASY",
        world_index=0,
        visibility_replicates=3,
        bootstrap_replicates=3,
        placebo_replicates=3,
        block_rows=5,
    )
    payload = lib.evaluate_fixture_world(config)
    assert "candidates" in payload
    assert len(payload["candidates"]) == 10


def test_dgp_fixture_draw_is_deterministic():
    a = v2.draw_fixture_world(scenario="EASY", n_rows=50, world_index=0)
    b = v2.draw_fixture_world(scenario="EASY", n_rows=50, world_index=0)
    np.testing.assert_array_equal(a["Y"], b["Y"])
    np.testing.assert_array_equal(a["S"], b["S"])
    assert int(a["world_seed"]) == int(b["world_seed"])


def test_implementation_identity_is_fixture_only():
    ident = v2.implementation_identity()
    assert ident["implementation_exists"] is True
    assert ident["fixture_only"] is True
    assert ident["synthetic_execution_authorized"] is False
    assert ident["v2_production_arm_authorized"] is False
    assert ident["production_calibration_executed"] is False
    assert ident["result_mint_authorized"] is False
    assert ident["authority_consumed"] is False
    assert ident["next_required_step"] == "INDEPENDENT_IMPLEMENTATION_REVIEW"
    assert ident["coverage_table_entries"] == 80
    assert ident["required_coverage_map_count"] == 33
