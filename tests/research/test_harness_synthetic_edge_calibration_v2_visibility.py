"""Focused tests for V2 GROUND_TRUTH_VISIBLE plumbing.

Does not rerun canonical V2 candidate evaluation, mint RESULT, or modify
WORLD_RECORDS. Disposable worlds only, except identity/digest checks against
the immutable canonical WORLD_RECORDS artifact.
"""

from __future__ import annotations

import copy
import hashlib
import inspect
import json
from pathlib import Path
from unittest import mock

import numpy as np
import pytest

from scripts.research.harness_synthetic_edge_calibration_v1_lib import (
    PRODUCTION_BLOCK_ROWS,
    PRODUCTION_VISIBILITY_REPLICATES,
    expanding_era_predictions,
    namespace_seed,
    pcg64_generator,
    simulate_dgp,
    visibility_from_residuals,
    world_identity,
    world_seed,
)
from scripts.research.harness_synthetic_edge_calibration_v1_production import (
    _jsonable,
    canonical_json_bytes,
)
from scripts.research.harness_synthetic_edge_calibration_v2_inherited_ladder import (
    FINAL_OVERALL_ID,
    VISIBILITY_BLOCKED_IDS,
)
from scripts.research.harness_synthetic_edge_calibration_v2_production import (
    CANONICAL_V2_WORLD_RECORDS_PATH,
    _worldrecord_from_dict,
)
from scripts.research import harness_synthetic_edge_calibration_v2_visibility as vis
from scripts.research.harness_synthetic_edge_calibration_v2_rank_policy import (
    FEATURE_IDS,
    CandidateWorldRecord,
    WorldRecordV2,
)

REPO = Path(__file__).resolve().parents[2]
HISTORICAL_EVIDENCE_COMMIT = "8917c776ac8c148828bfab4395fd84890ff3c847"
HEAD_WORLD_RECORDS_SHA256 = (
    "e8667f930a4acc7fb5dd26fa62414a8f4b359121336902aac651cb76f4e50dbf"
)
HEAD_VISIBILITY_SHA256 = (
    "ed1c17f0e2eb8f04ed917a7c84811d10a0d152f770a9315d2ade1cac1be93f9b"
)
HEAD_RESULT_SHA256 = (
    "ffce3daa24eb9039526d6de4b11a6ac43cfd36803058fe21827f1cd1f839100b"
)
RESULT_REL = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_RESULT.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _historical_world_records():
    from tests.research.historical_stage import blob_bytes

    raw = blob_bytes(HISTORICAL_EVIDENCE_COMMIT, CANONICAL_V2_WORLD_RECORDS_PATH)
    payload = json.loads(raw.decode("utf-8"))
    return payload, raw


def _historical_json(rel: str):
    from tests.research.historical_stage import blob_bytes

    raw = blob_bytes(HISTORICAL_EVIDENCE_COMMIT, rel)
    return json.loads(raw.decode("utf-8")), raw


def _make_record(scenario, n, idx, *, world_id=None, detected_f03=False):
    cands = {}
    for cid in FEATURE_IDS:
        det = bool(detected_f03 and cid == "F03")
        cands[cid] = CandidateWorldRecord(
            candidate_id=cid,
            state="CANDIDATE_IDENTIFIABLE",
            detected=det,
            gates={"STRICT_PASS": det, "STRICT_PASS_EX_MATERIALITY": det},
        )
    return WorldRecordV2(
        world_id=world_id or world_identity(scenario, n, idx),
        scenario=scenario,
        N=n,
        world_index=idx,
        world_state="WORLD_VALID",
        L=1,
        selection_state="SELECTED",
        selected_candidate="F03" if detected_f03 else None,
        taxonomy="TRUE_DISCOVERY" if detected_f03 else "NO_DISCOVERY",
        candidates=cands,
    )


def test_frozen_formula_constants_and_rng_namespace():
    src = inspect.getsource(vis.derive_v2_world_visibility_record)
    assert "PRODUCTION_VISIBILITY_REPLICATES" in src
    assert "PRODUCTION_BLOCK_ROWS" in src
    assert '"VISIBILITY"' in src
    assert "expanding_era_predictions" in src
    assert PRODUCTION_VISIBILITY_REPLICATES == 500
    assert PRODUCTION_BLOCK_ROWS == 50
    assert vis.VISIBILITY_FLOOR_THRESHOLD == 0.50


def test_baseline_is_x1_x2_only_no_candidate_feature():
    captured = {}

    def wrapped(y, x1, x2, feature, n_rows):
        captured["feature"] = feature
        return expanding_era_predictions(y, x1, x2, feature, n_rows)

    with mock.patch.object(vis, "expanding_era_predictions", wrapped):
        rec = vis.derive_v2_world_visibility_record(
            scenario_id="EASY", n_rows=5000, world_index=0
        )
    assert captured["feature"] is None
    assert rec["world_id"] == world_identity("EASY", 5000, 0)


def test_visibility_uses_exact_rng_namespace():
    captured = {}
    real_ns = namespace_seed

    def wrapped(world_seed_int, namespace, *context):
        captured["namespace"] = namespace
        captured["seed"] = world_seed_int
        return real_ns(world_seed_int, namespace, *context)

    with mock.patch.object(vis, "namespace_seed", wrapped):
        vis.derive_v2_world_visibility_record(scenario_id="EASY", n_rows=5000, world_index=1)
    identity = world_identity("EASY", 5000, 1)
    assert captured["namespace"] == "VISIBILITY"
    assert captured["seed"] == int(world_seed(identity))


def test_invalid_replicate_is_not_visible():
    world = simulate_dgp(scenario_id="EASY", n_rows=5000, world_index=0)
    y = np.asarray(world["Y"], dtype=np.float64)
    x1 = np.asarray(world["X1"], dtype=np.float64)
    x2 = np.asarray(world["X2"], dtype=np.float64)
    preds = expanding_era_predictions(y, x1, x2, None, 5000)
    s = np.zeros(5000, dtype=np.float64)
    out = visibility_from_residuals(
        y - preds["BASE_PRED"],
        s,
        5000,
        replicates=PRODUCTION_VISIBILITY_REPLICATES,
        block_rows=PRODUCTION_BLOCK_ROWS,
        rng=pcg64_generator(namespace_seed(int(world_seed(str(world["world_identity"]))), "VISIBILITY")),
    )
    assert out["visibility_invalid"] is True
    assert out["GROUND_TRUTH_VISIBLE"] is False


def test_per_world_visibility_is_deterministic():
    a = vis.derive_v2_world_visibility_record(scenario_id="EASY", n_rows=5000, world_index=0)
    b = vis.derive_v2_world_visibility_record(scenario_id="EASY", n_rows=5000, world_index=0)
    assert a == b
    assert canonical_json_bytes(a) == canonical_json_bytes(b)


def test_isolated_two_world_derivation_is_byte_identical_across_runs():
    jobs = (("EASY", 5000, 0), ("NULL", 5000, 0))
    first = [
        vis.derive_v2_world_visibility_record(scenario_id=s, n_rows=n, world_index=i)
        for s, n, i in jobs
    ]
    second = [
        vis.derive_v2_world_visibility_record(scenario_id=s, n_rows=n, world_index=i)
        for s, n, i in jobs
    ]
    assert canonical_json_bytes(first) == canonical_json_bytes(second)


def test_source_does_not_evaluate_v2_candidates():
    src = inspect.getsource(vis)
    assert "_evaluate_v2_world_inner" not in src
    assert "evaluate_v2_world_in_session" not in src
    assert "candidate_features" not in src
    assert "select_blind" not in src


def test_visibility_cannot_alter_world_record_outcomes():
    records = [
        _make_record("EASY", 5000, i, detected_f03=True) for i in range(3)
    ] + [
        _make_record("TINY_NOISY", 5000, i, detected_f03=True) for i in range(3)
    ]
    before = copy.deepcopy(records)
    visible = {rec.world_id: True for rec in records}
    vis.derive_visibility_blocked_inherited(records, visible)
    assert records == before


def _stub_evidence(payload):
    stub_worlds = [
        {
            "world_id": rec["world_id"],
            "GROUND_TRUTH_VISIBLE": False,
            "visibility_invalid": False,
            "visibility_q025": 0.0,
        }
        for rec in payload["records"]
    ]
    return {
        "schema": vis.V2_VISIBILITY_SCHEMA,
        "schema_version": "1.0.0",
        "arm_commit": vis.ARM_HEAD,
        "freeze_head": vis.FREEZE_HEAD,
        "implementation_head": vis.IMPLEMENTATION_HEAD,
        "canonical_v2_plan_sha256": vis.PLAN_SHA,
        "run_identity": vis.RUN_IDENTITY,
        "world_records_sha256": vis.WORLD_RECORDS_SHA256,
        "inner_records_sha256": vis.INNER_RECORDS_SHA256,
        "world_count": 3200,
        "visibility_replicates": 500,
        "visibility_block_rows": 50,
        "worlds": stub_worlds,
        "worlds_sha256": hashlib.sha256(canonical_json_bytes(stub_worlds)).hexdigest(),
        "worlds_size": len(canonical_json_bytes(stub_worlds)),
    }


def test_authenticate_refuses_binding_mismatches():
    payload, raw = _historical_world_records()
    evidence = _stub_evidence(payload)
    vis.authenticate_v2_visibility_evidence(evidence, payload, raw)
    bad_arm = dict(evidence)
    bad_arm["arm_commit"] = "0" * 40
    with pytest.raises(vis.V2VisibilityPlumbingError):
        vis.authenticate_v2_visibility_evidence(bad_arm, payload, raw)
    bad_plan = dict(evidence)
    bad_plan["canonical_v2_plan_sha256"] = "0" * 64
    with pytest.raises(vis.V2VisibilityPlumbingError):
        vis.authenticate_v2_visibility_evidence(bad_plan, payload, raw)
    bad_run = dict(evidence)
    bad_run["run_identity"] = "0" * 64
    with pytest.raises(vis.V2VisibilityPlumbingError):
        vis.authenticate_v2_visibility_evidence(bad_run, payload, raw)
    bad_wr = dict(evidence)
    bad_wr["world_records_sha256"] = "0" * 64
    with pytest.raises(vis.V2VisibilityPlumbingError):
        vis.authenticate_v2_visibility_evidence(bad_wr, payload, raw)


def test_authenticate_refuses_missing_duplicate_reordered_world_ids():
    payload, raw = _historical_world_records()
    evidence = _stub_evidence(payload)
    stub_worlds = evidence["worlds"]

    def _ev(worlds):
        body = dict(evidence)
        body["worlds"] = worlds
        body["worlds_sha256"] = hashlib.sha256(canonical_json_bytes(worlds)).hexdigest()
        body["worlds_size"] = len(canonical_json_bytes(worlds))
        return body

    with pytest.raises(vis.V2VisibilityPlumbingError):
        vis.authenticate_v2_visibility_evidence(_ev(stub_worlds[:-1]), payload, raw)
    dup = list(stub_worlds)
    dup[-1] = dict(dup[0])
    with pytest.raises(vis.V2VisibilityPlumbingError):
        vis.authenticate_v2_visibility_evidence(_ev(dup), payload, raw)
    reordered = list(stub_worlds)
    reordered[0], reordered[1] = reordered[1], reordered[0]
    with pytest.raises(vis.V2VisibilityPlumbingError):
        vis.authenticate_v2_visibility_evidence(_ev(reordered), payload, raw)


def test_canonical_world_records_bytes_unchanged():
    from tests.research.historical_stage import blob_sha256

    assert blob_sha256(HISTORICAL_EVIDENCE_COMMIT, CANONICAL_V2_WORLD_RECORDS_PATH) == vis.WORLD_RECORDS_SHA256
    payload, _raw = _historical_world_records()
    assert hashlib.sha256(canonical_json_bytes(payload["records"])).hexdigest() == vis.INNER_RECORDS_SHA256
    assert len(payload["records"]) == 3200
    assert _sha256(REPO / CANONICAL_V2_WORLD_RECORDS_PATH) == HEAD_WORLD_RECORDS_SHA256


def test_result_plumbing_assemble_does_not_write():
    src = inspect.getsource(vis.assemble_v2_result_payload_with_visibility)
    assert "derive_v2_mechanical_conclusions_with_visibility" in src
    assert "_atomic_replace_bytes" not in src
    assert "write_bytes" not in src
    assert VISIBILITY_BLOCKED_IDS


def test_canonical_result_authenticates_against_world_records_and_visibility():
    payload, raw = _historical_world_records()
    evidence, _ev_raw = _historical_json(vis.CANONICAL_V2_VISIBILITY_PATH)
    visible = vis.authenticate_v2_visibility_evidence(evidence, payload, raw)
    records = [_worldrecord_from_dict(row) for row in payload["records"]]
    result, _res_raw = _historical_json(RESULT_REL)
    assert result["arm_commit"] == vis.ARM_HEAD
    assert result["canonical_v2_plan_sha256"] == vis.PLAN_SHA
    assert result["run_identity"] == vis.RUN_IDENTITY
    assert result["world_records_count"] == 3200
    assert result["world_records_sha256"] == vis.INNER_RECORDS_SHA256
    from tests.research.historical_stage import blob_sha256

    assert blob_sha256(HISTORICAL_EVIDENCE_COMMIT, CANONICAL_V2_WORLD_RECORDS_PATH) == vis.WORLD_RECORDS_SHA256
    assert blob_sha256(HISTORICAL_EVIDENCE_COMMIT, vis.CANONICAL_V2_VISIBILITY_PATH) == (
        "9be8dceb07d8fc43b01ef8630d4ad9f52e7401fd6f095b3c7a5bf364701c8b65"
    )
    recomputed = vis.derive_v2_mechanical_conclusions_with_visibility(
        records, structurally_complete=True, visible=visible
    )
    assert canonical_json_bytes(_jsonable(recomputed)) == canonical_json_bytes(
        _jsonable(result["conclusions"])
    )
    assert result["final_overall_conclusion"] == recomputed[FINAL_OVERALL_ID]
    assert result["conclusions"][FINAL_OVERALL_ID] == recomputed[FINAL_OVERALL_ID]
    assert _sha256(REPO / RESULT_REL) == HEAD_RESULT_SHA256
    assert _sha256(REPO / vis.CANONICAL_V2_VISIBILITY_PATH) == HEAD_VISIBILITY_SHA256


def test_visibility_artifact_reconciles_canonical_world_ids_if_present():
    payload, raw = _historical_world_records()
    evidence, _ev_raw = _historical_json(vis.CANONICAL_V2_VISIBILITY_PATH)
    visible = vis.authenticate_v2_visibility_evidence(evidence, payload, raw)
    assert len(visible) == 3200
    assert list(visible) == [rec["world_id"] for rec in payload["records"]]
    from tests.research.historical_stage import blob_sha256

    assert blob_sha256(HISTORICAL_EVIDENCE_COMMIT, CANONICAL_V2_WORLD_RECORDS_PATH) == vis.WORLD_RECORDS_SHA256
