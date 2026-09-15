"""Focused tests for the V2 confirmatory-power repair.

Proves frozen V1 bootstrap/placebo execution, MODEL_DETECTED power identity,
unchanged STRICT_PASS/materiality/Wilson floors, and byte-identical canonical
V2 artifacts. Disposable confirmatory proof is NOT canonical calibration.
"""

from __future__ import annotations

import hashlib
import inspect
from pathlib import Path
from unittest import mock

import numpy as np

from scripts.research import harness_synthetic_edge_calibration_v1_lib as lib
from scripts.research import harness_synthetic_edge_calibration_v1_production as prod
from scripts.research import harness_synthetic_edge_calibration_v2_inherited_ladder as ladder
from scripts.research import harness_synthetic_edge_calibration_v2_rank_policy as v2

REPO = Path(__file__).resolve().parents[2]

CANONICAL_WORLD_RECORDS = (
    REPO
    / "docs"
    / "research"
    / "HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_WORLD_RECORDS.json"
)
CANONICAL_VISIBILITY = (
    REPO
    / "docs"
    / "research"
    / "HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_VISIBILITY.json"
)
CANONICAL_RESULT = (
    REPO
    / "docs"
    / "research"
    / "HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_RESULT.json"
)

FROZEN_WORLD_RECORDS_SHA256 = "d372eb00d4f6df9b4f8a2b0dcb22b051d95787ddeb8494a3c0efc31561e39821"
FROZEN_VISIBILITY_SHA256 = "9be8dceb07d8fc43b01ef8630d4ad9f52e7401fd6f095b3c7a5bf364701c8b65"
FROZEN_RESULT_SHA256 = "761cc9afc59265bfb94afecbd293082c274abf3affce3d9693f463442326c1e0"

PASS, FAIL = "PASS", "FAIL"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _valid_boot(**overrides):
    out = {
        "bootstrap_positive": False,
        "bootstrap_invalid": False,
        "bootstrap_q025": 0.01,
        "world_invalid": False,
        "stays_in_denominator": True,
    }
    out.update(overrides)
    return out


def _valid_plac(**overrides):
    out = {
        "placebo_q95": -1.0,
        "placebo_invalid": False,
        "world_invalid": False,
        "stays_in_denominator": True,
    }
    out.update(overrides)
    return out


def _rank_safe_world(n_rows: int = 50, scenario: str = "EASY") -> dict:
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


def _make_record(scenario, n, idx, *, detected=False, gates=None, state="CANDIDATE_IDENTIFIABLE"):
    cands = {}
    for cid in v2.FEATURE_IDS:
        det = bool(detected and cid == "F03")
        cands[cid] = v2.CandidateWorldRecord(
            candidate_id=cid,
            state=state,
            detected=det if state == "CANDIDATE_IDENTIFIABLE" else None,
            gates=dict(gates) if (gates is not None and cid == "F03") else {
                "STRICT_PASS": det,
                "STRICT_PASS_EX_MATERIALITY": det,
                "MODEL_DETECTED": det,
            },
        )
    return v2.WorldRecordV2(
        world_id=f"{scenario}|{n}|{idx}",
        scenario=scenario,
        N=n,
        world_index=idx,
        world_state="WORLD_VALID",
        L=10,
        selection_state="SELECTED",
        selected_candidate="F03" if detected else None,
        taxonomy="TRUE_DISCOVERY" if detected else "NO_DISCOVERY",
        candidates=cands,
    )


def test_bootstrap_and_placebo_are_executed_not_hardcoded():
    boot_calls = []
    plac_calls = []

    def boot_stub(ae_imp_full, n_rows, *, replicates, block_rows, rng):
        boot_calls.append(
            {
                "replicates": replicates,
                "block_rows": block_rows,
                "rng_type": type(rng).__name__,
                "bit_generator": type(rng.bit_generator).__name__,
            }
        )
        assert replicates == lib.PRODUCTION_BOOTSTRAP_REPLICATES
        assert block_rows == lib.PRODUCTION_BLOCK_ROWS
        assert type(rng.bit_generator).__name__ == "PCG64"
        return _valid_boot(bootstrap_positive=True)

    def plac_stub(*, world, feature, n_rows, replicates, rng):
        plac_calls.append(
            {
                "replicates": replicates,
                "rng_type": type(rng).__name__,
                "bit_generator": type(rng.bit_generator).__name__,
            }
        )
        assert replicates == lib.PRODUCTION_PLACEBO_REPLICATES
        assert type(rng.bit_generator).__name__ == "PCG64"
        return _valid_plac()

    world = _rank_safe_world()
    with mock.patch.object(v2, "prediction_bootstrap", side_effect=boot_stub), mock.patch.object(
        v2, "placebo_q95", side_effect=plac_stub
    ):
        rec = v2.evaluate_v2_world(world, scenario="EASY", n_rows=50, world_index=0)
    assert rec.world_state == v2.WORLD_VALID
    assert rec.L == 10
    assert len(boot_calls) == 10
    assert len(plac_calls) == 10
    inner = inspect.getsource(v2._evaluate_v2_world_inner)
    assert "bootstrap_positive=False" not in inner
    assert "placebo_separation=False" not in inner
    assert 'confirmatory["bootstrap_positive"]' in inner
    assert 'confirmatory["placebo_separation"]' in inner


def test_rng_semantics_match_frozen_v1_on_one_candidate():
    world = lib.simulate_dgp(scenario_id="EASY", n_rows=50, world_index=0)
    n = 50
    cid = "F03"
    feature = lib.candidate_features(world)[cid]
    y = np.asarray(world["Y"], dtype=np.float64)
    preds = lib.expanding_era_predictions(y, world["X1"], world["X2"], feature, n)
    metrics = lib.ae_metrics(y, preds["BASE_PRED"], preds["CAND_PRED"], lib.scored_mask(n))
    got = v2._frozen_v1_confirmatory_pair(
        world=world,
        feature=feature,
        feature_id=cid,
        n_rows=n,
        world_index=0,
        scenario="EASY",
        preds=preds,
        y=y,
        mean_ae_improvement=metrics["MEAN_AE_IMPROVEMENT"],
    )
    assert got["ni_reason"] is None

    mask = lib.scored_mask(n)
    ae_imp_full = np.full(n, np.nan, dtype=np.float64)
    ae_imp_full[mask] = np.abs(y[mask] - preds["BASE_PRED"][mask]) - np.abs(
        y[mask] - preds["CAND_PRED"][mask]
    )
    identity = str(world.get("world_identity", lib.world_identity("EASY", n, 0)))
    wseed = int(lib.world_seed(identity))
    boot = lib.prediction_bootstrap(
        ae_imp_full,
        n,
        replicates=lib.PRODUCTION_BOOTSTRAP_REPLICATES,
        block_rows=lib.PRODUCTION_BLOCK_ROWS,
        rng=lib.pcg64_generator(lib.namespace_seed(wseed, "BOOTSTRAP", cid)),
    )
    plac = lib.placebo_q95(
        world=world,
        feature=feature,
        n_rows=n,
        replicates=lib.PRODUCTION_PLACEBO_REPLICATES,
        rng=lib.pcg64_generator(lib.namespace_seed(wseed, "PLACEBO", cid)),
    )
    assert boot["bootstrap_q025"] == got["bootstrap_q025"]
    assert plac["placebo_q95"] == got["placebo_q95"]
    assert boot["bootstrap_positive"] is got["bootstrap_positive"]
    expected_sep = (
        (not plac["placebo_invalid"])
        and np.isfinite(plac["placebo_q95"])
        and metrics["MEAN_AE_IMPROVEMENT"] > plac["placebo_q95"]
    )
    assert expected_sep is got["placebo_separation"]

    v1 = prod.evaluate_production_candidate(
        world, cid, scenario_id="EASY", n_rows=n, world_index=0
    )
    assert v1["gates"]["bootstrap_positive"] is got["bootstrap_positive"]
    assert v1["gates"]["placebo_separation"] is got["placebo_separation"]
    assert v1["gates"]["MODEL_DETECTED"] == (
        bool(metrics["MEAN_AE_IMPROVEMENT"] > 0.0)
        and got["bootstrap_positive"]
        and got["placebo_separation"]
    )


def test_model_detected_can_become_true_and_false():
    world = _rank_safe_world()
    with mock.patch.object(
        v2, "prediction_bootstrap", return_value=_valid_boot(bootstrap_positive=True)
    ), mock.patch.object(v2, "placebo_q95", return_value=_valid_plac(placebo_q95=-1.0)):
        rec_true = v2.evaluate_v2_world(world, scenario="EASY", n_rows=50, world_index=0)
    f03 = rec_true.candidates["F03"]
    assert f03.state == v2.CANDIDATE_IDENTIFIABLE
    assert f03.gates["primary_positive"] is True
    assert f03.gates["bootstrap_positive"] is True
    assert f03.gates["placebo_separation"] is True
    assert f03.gates["MODEL_DETECTED"] is True
    assert f03.detected is True

    with mock.patch.object(
        v2, "prediction_bootstrap", return_value=_valid_boot(bootstrap_positive=False)
    ), mock.patch.object(v2, "placebo_q95", return_value=_valid_plac(placebo_q95=-1.0)):
        rec_false = v2.evaluate_v2_world(world, scenario="EASY", n_rows=50, world_index=0)
    f03b = rec_false.candidates["F03"]
    assert f03b.gates["bootstrap_positive"] is False
    assert f03b.gates["MODEL_DETECTED"] is False
    assert f03b.detected is False
    assert f03b.gates["STRICT_PASS"] is False


def test_strict_pass_and_two_percent_materiality_unchanged():
    era = {"E2": 0.1, "E3": 0.1, "E4": 0.1, "E5": -0.01}
    below = lib.compose_gates(
        mean_ae_improvement=0.05,
        relative_mae_improvement=0.019999,
        bootstrap_positive=True,
        placebo_separation=True,
        era_improvements=era,
        candidate_positive_count=50,
    )
    assert lib.MATERIALITY_GATE == 0.02
    assert below["MODEL_DETECTED"] is True
    assert below["STRICT_PASS_EX_MATERIALITY"] is True
    assert below["STRICT_PASS"] is False
    assert below["material_relative_mae"] is False
    at = lib.compose_gates(
        mean_ae_improvement=0.05,
        relative_mae_improvement=0.02,
        bootstrap_positive=True,
        placebo_separation=True,
        era_improvements=era,
        candidate_positive_count=50,
    )
    assert at["STRICT_PASS"] is True
    src = inspect.getsource(lib.compose_gates)
    assert "MATERIALITY_GATE" in src
    assert lib.MATERIALITY_GATE == 0.02


def test_oracle_power_reads_model_detected_not_strict_pass():
    records = []
    for i in range(250):
        rec = _make_record(
            "EASY",
            5000,
            i,
            detected=True,
            gates={
                "MODEL_DETECTED": True,
                "STRICT_PASS": False,
                "STRICT_PASS_EX_MATERIALITY": True,
            },
        )
        records.append(rec)
    got = ladder.derive_v2_inherited_conclusion("EASY_ORACLE_POWER", records)
    expected = lib.power_verdict(lib.wilson_interval(250, 250), 0.90)
    assert got == expected == PASS
    mat = ladder.derive_v2_inherited_conclusion("MATERIALITY_ONLY_DIAGNOSTIC", records)
    assert mat == "MATERIALITY_ONLY_DIAGNOSTIC"


def test_easy_and_moderate_power_thresholds_unchanged():
    assert prod.ORACLE_EASY_MIN == 0.90
    assert prod.ORACLE_MODERATE_MIN == 0.70
    auth = ladder.load_v2_inherited_ladder_authority()
    conclusions = auth["conclusions"]
    assert conclusions["EASY_ORACLE_POWER"]["threshold"] == 0.9
    assert conclusions["MODERATE_ORACLE_POWER"]["threshold"] == 0.7
    assert "wilson_lower" in conclusions["EASY_ORACLE_POWER"]["operator"]
    assert "wilson_lower" in conclusions["MODERATE_ORACLE_POWER"]["operator"]
    assert "MODEL_DETECTED" in conclusions["EASY_ORACLE_POWER"]["input_statistic"]
    assert "MODEL_DETECTED" in conclusions["MODERATE_ORACLE_POWER"]["input_statistic"]
    assert "MODEL_DETECTED" in conclusions["MODEL_FLOOR"]["input_statistic"]


def test_null_and_trap_protections_not_weakened():
    auth = ladder.load_v2_inherited_ladder_authority()
    conclusions = auth["conclusions"]
    assert conclusions["NULL_ORACLE_FPR"]["threshold"] == 0.05
    assert "specificity_verdict" in conclusions["NULL_ORACLE_FPR"]["frozen_operator_function"]
    assert "MODEL_DETECTED" in conclusions["NULL_ORACLE_FPR"]["input_statistic"]
    assert conclusions["NONSTATIONARY_TRAP_ORACLE_SPECIFICITY"]["threshold"] == 0.2
    assert (
        conclusions["NONSTATIONARY_TRAP_ORACLE_SPECIFICITY"]["numerator"].find(
            "STRICT_PASS_EX_MATERIALITY"
        )
        >= 0
    )
    trap_records = []
    for i in range(250):
        rec = _make_record(
            "NONSTATIONARY_TRAP",
            5000,
            i,
            detected=True,
            gates={
                "MODEL_DETECTED": True,
                "STRICT_PASS": False,
                "STRICT_PASS_EX_MATERIALITY": False,
            },
        )
        trap_records.append(rec)
    trap = ladder.derive_v2_inherited_conclusion(
        "NONSTATIONARY_TRAP_ORACLE_SPECIFICITY", trap_records
    )
    expected = lib.specificity_verdict(lib.wilson_interval(0, 250), 0.20)
    assert trap == expected == PASS
    null_records = [_make_record("NULL", 5000, i, detected=False) for i in range(250)]
    null = ladder.derive_v2_inherited_conclusion("NULL_ORACLE_FPR", null_records)
    assert null == lib.specificity_verdict(lib.wilson_interval(0, 250), 0.05) == PASS


def test_identifiability_semantics_unchanged():
    world = _rank_safe_world()
    with mock.patch.object(
        v2, "prediction_bootstrap", return_value=_valid_boot(bootstrap_positive=True)
    ), mock.patch.object(v2, "placebo_q95", return_value=_valid_plac()):
        rec = v2.evaluate_v2_world(
            world, scenario="EASY", n_rows=50, world_index=0, zero_e1_features={"F02"}
        )
    assert rec.world_state == v2.WORLD_VALID
    assert rec.candidates["F02"].state == v2.CANDIDATE_NOT_IDENTIFIABLE
    assert rec.candidates["F02"].detected is None
    assert rec.candidates["F02"].nonidentifiability.reason == v2.REASON_RANK_DEFICIENT
    identifiable = [
        cid for cid, cand in rec.candidates.items() if cand.state == v2.CANDIDATE_IDENTIFIABLE
    ]
    assert rec.L == len(identifiable) == 9
    with mock.patch.object(
        v2,
        "prediction_bootstrap",
        return_value={
            "bootstrap_positive": False,
            "bootstrap_invalid": True,
            "bootstrap_q025": float("nan"),
            "world_invalid": True,
            "stays_in_denominator": True,
        },
    ), mock.patch.object(v2, "placebo_q95") as plac:
        rec_ni = v2.evaluate_v2_world(world, scenario="EASY", n_rows=50, world_index=0)
        plac.assert_not_called()
    assert rec_ni.world_state == v2.WORLD_VALID
    for cid in lib.FEATURE_IDS:
        assert rec_ni.candidates[cid].state == v2.CANDIDATE_NOT_IDENTIFIABLE
        assert rec_ni.candidates[cid].detected is None
        assert rec_ni.candidates[cid].nonidentifiability.reason == v2.REASON_NONFINITE_BOOTSTRAP


def test_canonical_v2_artifacts_remain_byte_identical():
    assert _sha(CANONICAL_WORLD_RECORDS) == FROZEN_WORLD_RECORDS_SHA256
    assert _sha(CANONICAL_VISIBILITY) == FROZEN_VISIBILITY_SHA256
    assert _sha(CANONICAL_RESULT) == FROZEN_RESULT_SHA256
    result = CANONICAL_RESULT.read_text(encoding="utf-8")
    assert "METHODOLOGY_POWER_REPAIR_REQUIRED_BEFORE_B2_06" in result
    src_rank = inspect.getsource(v2)
    src_ladder = inspect.getsource(ladder)
    assert "mint_v2_result" not in src_rank
    assert "mint_v2_result" not in src_ladder
    assert "assemble_v2_result_payload_with_visibility" not in src_rank
    assert "assemble_v2_result_payload_with_visibility" not in src_ladder


def test_disposable_confirmatory_path_reachable_not_canonical():
    """Disposable proof only. Not a 3200-world calibration and not a RESULT."""
    found = None
    for world_index in range(5):
        world = lib.simulate_dgp(scenario_id="EASY", n_rows=50, world_index=world_index)
        n = 50
        cid = "F03"
        feature = lib.candidate_features(world)[cid]
        y = np.asarray(world["Y"], dtype=np.float64)
        preds = lib.expanding_era_predictions(y, world["X1"], world["X2"], feature, n)
        metrics = lib.ae_metrics(y, preds["BASE_PRED"], preds["CAND_PRED"], lib.scored_mask(n))
        confirmatory = v2._frozen_v1_confirmatory_pair(
            world=world,
            feature=feature,
            feature_id=cid,
            n_rows=n,
            world_index=world_index,
            scenario="EASY",
            preds=preds,
            y=y,
            mean_ae_improvement=metrics["MEAN_AE_IMPROVEMENT"],
        )
        if confirmatory["ni_reason"] is not None:
            continue
        gates = lib.compose_gates(
            mean_ae_improvement=metrics["MEAN_AE_IMPROVEMENT"],
            relative_mae_improvement=metrics["RELATIVE_MAE_IMPROVEMENT"],
            bootstrap_positive=bool(confirmatory["bootstrap_positive"]),
            placebo_separation=bool(confirmatory["placebo_separation"]),
            era_improvements=lib.era_mean_improvements(
                y, preds["BASE_PRED"], preds["CAND_PRED"], n
            ),
            candidate_positive_count=int(np.sum(feature[lib.scored_mask(n)] == 1.0)),
        )
        v1 = prod.evaluate_production_candidate(
            world, cid, scenario_id="EASY", n_rows=n, world_index=world_index
        )
        assert v1["gates"]["MODEL_DETECTED"] is gates["MODEL_DETECTED"]
        assert v1["gates"]["bootstrap_positive"] is gates["bootstrap_positive"]
        assert v1["gates"]["placebo_separation"] is gates["placebo_separation"]
        assert v1["gates"]["STRICT_PASS"] is gates["STRICT_PASS"]
        if gates["MODEL_DETECTED"] is True:
            found = {
                "world_index": world_index,
                "MODEL_DETECTED": True,
                "STRICT_PASS": gates["STRICT_PASS"],
                "canonical": False,
            }
            break
    assert found is not None
    assert found["canonical"] is False
    assert found["MODEL_DETECTED"] is True
