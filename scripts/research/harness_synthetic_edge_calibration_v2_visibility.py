"""V2 GROUND_TRUTH_VISIBLE plumbing from frozen pre-outcome V1 authority.

This module derives the already-defined per-world visibility diagnostic that
the frozen V2 inherited ladder requires, without re-evaluating V2 candidates
and without modifying canonical WORLD_RECORDS.

Authority (pre-outcome, uniquely determining):

- V1 prereg §10: BASE_RESIDUAL = Y-BASE_PRED;
  VISIBILITY_STAT = mean(BASE_RESIDUAL|S=1) - mean(BASE_RESIDUAL|S=0);
  500 era-local 50-row block-bootstrap replicates; GROUND_TRUTH_VISIBLE = q025 > 0;
  any invalid replicate => not visible.
- Frozen ``visibility_from_residuals`` / ``expanding_era_predictions`` (feature=None
  yields the same BASE_PRED as V1, which fits X1,X2 only).
- V1 production ``evaluate_production_candidate`` RNG:
  PCG64(namespace_seed(world_seed(world_identity), "VISIBILITY")).
- Amendment_003 VISIBILITY_FLOOR: GROUND_TRUTH_VISIBLE rate on EASY|5000,
  denominator world_valid_count, floor binds iff wilson_upper < 0.50.
- Amendment_003 TINY_NOISY_ORACLE_DIAGNOSTIC: visibility leg then model leg,
  same floor operator, TINY_NOISY|5000.

production.py and inherited_ladder.py are ARM-bound live bytes and are not
modified here. Result derivation consumes authenticated visibility evidence
through this module. Canonical RESULT is not minted by this unit.
"""

from __future__ import annotations

import json
import math
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from scripts.research.harness_synthetic_edge_calibration_v1_lib import (
    PRODUCTION_BLOCK_ROWS,
    PRODUCTION_VISIBILITY_REPLICATES,
    SyntheticExecutionNotAuthorized,
    expanding_era_predictions,
    mechanical_conclusion,
    namespace_seed,
    pcg64_generator,
    simulate_dgp,
    visibility_from_residuals,
    wilson_interval,
    world_identity,
    world_seed,
)
from scripts.research.harness_synthetic_edge_calibration_v1_production import (
    _atomic_replace_bytes,
    _jsonable,
    _parent_sha_of,
    _sha256_bytes,
    canonical_json_bytes,
)
from scripts.research.harness_synthetic_edge_calibration_v2_inherited_ladder import (
    FINAL_OVERALL_ID,
    VISIBILITY_BLOCKED_IDS,
    _comb,
    derive_v2_inherited_conclusions_needed,
    frozen_final_overall_terminal_labels,
)
from scripts.research.harness_synthetic_edge_calibration_v2_production import (
    CANONICAL_V2_WORLD_RECORDS_PATH,
    derive_v2_cell_aggregates,
    derive_v2_required_coverage_status,
    verify_historical_v2_execution_authority,
)
from scripts.research.harness_synthetic_edge_calibration_v2_rank_policy import (
    COVERAGE_ADEQUATE,
    MECHANICAL_INSUFFICIENT_IDENTIFIABILITY,
    MECHANICAL_STRUCTURAL_INCOMPLETE,
    WORLD_VALID,
    WorldRecordV2,
    aggregate_v2_records,
    mechanical_conclusion_v2,
    required_coverage_for_conclusion,
)

CANONICAL_V2_VISIBILITY_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_VISIBILITY.json"
)
V2_VISIBILITY_SCHEMA = "harness_synthetic_edge_calibration_v2_visibility_evidence"
VISIBILITY_FLOOR_THRESHOLD = 0.50
ARM_HEAD = "18ebb4c5629e1717a6633ee6bd63cda7c0bb65ea"
FREEZE_HEAD = "2523b389e10585c81e18a69f43cc1e38fface41f"
IMPLEMENTATION_HEAD = "baf9f23045f4c19418eaaf3a9a7a1b69e21aff98"
PLAN_SHA = "7fa12fd3b939cd210a69da37659fd1013a1dba43aca4c06abb6f5a6442a33800"
RUN_IDENTITY = "2088e76f99685c36e65387117b6f8a49482b3b68939f01d827023e0d36991818"
WORLD_RECORDS_SHA256 = "d372eb00d4f6df9b4f8a2b0dcb22b051d95787ddeb8494a3c0efc31561e39821"
INNER_RECORDS_SHA256 = "763a8ce802b7b5efa133ebe3132103cbb96c86d83c7c2dacc992147c8ee4ef66"


class V2VisibilityPlumbingError(SyntheticExecutionNotAuthorized):
    """Visibility evidence is missing, unbound, or not the frozen V1 statistic."""


def _refuse(detail: str) -> None:
    raise V2VisibilityPlumbingError(f"SYNTHETIC_EXECUTION_NOT_AUTHORIZED: {detail}")


def derive_v2_world_visibility_record(
    *, scenario_id: str, n_rows: int, world_index: int
) -> dict[str, Any]:
    """GROUND_TRUTH_VISIBLE for one frozen world identity. No candidate evaluation."""
    world = simulate_dgp(
        scenario_id=str(scenario_id), n_rows=int(n_rows), world_index=int(world_index)
    )
    identity = str(world["world_identity"])
    expected = world_identity(str(scenario_id), int(n_rows), int(world_index))
    if identity != expected:
        _refuse(f"DGP world_identity {identity!r} != frozen identity {expected!r}")
    y = np.asarray(world["Y"], dtype=np.float64)
    x1 = np.asarray(world["X1"], dtype=np.float64)
    x2 = np.asarray(world["X2"], dtype=np.float64)
    s = np.asarray(world["S"], dtype=np.float64)
    n = int(n_rows)
    preds = expanding_era_predictions(y, x1, x2, None, n)
    vis = visibility_from_residuals(
        y - preds["BASE_PRED"],
        s,
        n,
        replicates=PRODUCTION_VISIBILITY_REPLICATES,
        block_rows=PRODUCTION_BLOCK_ROWS,
        rng=pcg64_generator(namespace_seed(int(world_seed(identity)), "VISIBILITY")),
    )
    q025 = vis.get("visibility_q025")
    q025_out = None
    if isinstance(q025, (int, float)) and math.isfinite(float(q025)):
        q025_out = float(q025)
    return {
        "world_id": identity,
        "GROUND_TRUTH_VISIBLE": bool(vis["GROUND_TRUTH_VISIBLE"]),
        "visibility_invalid": bool(vis["visibility_invalid"]),
        "visibility_q025": q025_out,
    }


def _visibility_job(
    spec: tuple[int, str, int, int, str],
) -> tuple[int, dict[str, Any]]:
    index, scenario_id, n_rows, world_index, expected_id = spec
    computed = derive_v2_world_visibility_record(
        scenario_id=scenario_id, n_rows=n_rows, world_index=world_index
    )
    if computed["world_id"] != expected_id:
        raise V2VisibilityPlumbingError(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: reconstructed world_id "
            f"{computed['world_id']!r} != canonical {expected_id!r}"
        )
    return index, computed


def _world_records_file_and_inner_sha256(payload: Mapping[str, Any], raw: bytes) -> tuple[str, str]:
    file_sha = _sha256_bytes(raw)
    inner = canonical_json_bytes(payload["records"])
    return file_sha, _sha256_bytes(inner)


def load_canonical_world_records_payload(repo_root: Path) -> tuple[dict[str, Any], bytes]:
    path = Path(repo_root) / CANONICAL_V2_WORLD_RECORDS_PATH
    raw = path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        _refuse("canonical WORLD_RECORDS payload is not an object")
    return payload, raw


def build_v2_visibility_evidence(
    repo_root: Path,
    world_records_payload: Mapping[str, Any],
    world_records_raw: bytes,
    *,
    progress: Any | None = None,
) -> dict[str, Any]:
    """Derive visibility for every WORLD_RECORDS identity. Does not write WORLD_RECORDS."""
    records = world_records_payload.get("records")
    if not isinstance(records, list) or len(records) != 3200:
        _refuse("canonical WORLD_RECORDS must contain exactly 3200 records")
    file_sha, inner_sha = _world_records_file_and_inner_sha256(world_records_payload, world_records_raw)
    if file_sha != WORLD_RECORDS_SHA256:
        _refuse("WORLD_RECORDS bytes are not the immutable canonical artifact")
    if inner_sha != INNER_RECORDS_SHA256:
        _refuse("WORLD_RECORDS inner records_sha256 is not the immutable canonical digest")
    if world_records_payload.get("arm_commit") != ARM_HEAD:
        _refuse("WORLD_RECORDS ARM binding mismatch")
    if world_records_payload.get("canonical_v2_plan_sha256") != PLAN_SHA:
        _refuse("WORLD_RECORDS plan binding mismatch")
    if world_records_payload.get("run_identity") != RUN_IDENTITY:
        _refuse("WORLD_RECORDS run_identity mismatch")
    freeze = _parent_sha_of(Path(repo_root), ARM_HEAD)
    impl = _parent_sha_of(Path(repo_root), freeze) if freeze else None
    if freeze != FREEZE_HEAD or impl != IMPLEMENTATION_HEAD:
        _refuse("ARM topology does not match frozen freeze/implementation heads")
    bound = verify_historical_v2_execution_authority(Path(repo_root), ARM_HEAD)
    if bound["run_identity"] != RUN_IDENTITY:
        _refuse("historical run_identity mismatch")
    specs = [
        (
            i,
            str(rec["scenario"]),
            int(rec["N"]),
            int(rec["world_index"]),
            str(rec["world_id"]),
        )
        for i, rec in enumerate(records)
    ]
    worlds: list[dict[str, Any] | None] = [None] * len(specs)
    workers = os.cpu_count() or 1
    done = 0
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(_visibility_job, spec) for spec in specs]
        for fut in as_completed(futs):
            index, computed = fut.result()
            worlds[index] = computed
            done += 1
            if progress is not None and done % 50 == 0:
                progress(done, len(specs))
    if any(row is None for row in worlds):
        _refuse("visibility derivation missed one or more worlds")
    worlds_bytes = canonical_json_bytes(worlds)
    payload = {
        "schema": V2_VISIBILITY_SCHEMA,
        "schema_version": "1.0.0",
        "arm_commit": ARM_HEAD,
        "freeze_head": FREEZE_HEAD,
        "implementation_head": IMPLEMENTATION_HEAD,
        "canonical_v2_plan_sha256": PLAN_SHA,
        "run_identity": RUN_IDENTITY,
        "world_records_sha256": file_sha,
        "inner_records_sha256": inner_sha,
        "world_count": 3200,
        "visibility_replicates": PRODUCTION_VISIBILITY_REPLICATES,
        "visibility_block_rows": PRODUCTION_BLOCK_ROWS,
        "visibility_rng": 'PCG64(namespace_seed(world_seed(world_identity), "VISIBILITY"))',
        "baseline_definition": "expanding_era_predictions BASE_PRED from X1,X2 only (feature=None)",
        "worlds": worlds,
        "worlds_sha256": _sha256_bytes(worlds_bytes),
        "worlds_size": len(worlds_bytes),
    }
    return _jsonable(payload)


def authenticate_v2_visibility_evidence(
    evidence: Mapping[str, Any],
    world_records_payload: Mapping[str, Any],
    world_records_raw: bytes,
) -> dict[str, bool]:
    """Refuse unless evidence is bound to the immutable canonical WORLD_RECORDS identities."""
    if not isinstance(evidence, Mapping):
        _refuse("visibility evidence is not an object")
    if evidence.get("schema") != V2_VISIBILITY_SCHEMA:
        _refuse("visibility evidence schema is not canonical")
    for key, expected in (
        ("arm_commit", ARM_HEAD),
        ("freeze_head", FREEZE_HEAD),
        ("implementation_head", IMPLEMENTATION_HEAD),
        ("canonical_v2_plan_sha256", PLAN_SHA),
        ("run_identity", RUN_IDENTITY),
        ("world_count", 3200),
        ("visibility_replicates", PRODUCTION_VISIBILITY_REPLICATES),
        ("visibility_block_rows", PRODUCTION_BLOCK_ROWS),
    ):
        if evidence.get(key) != expected:
            _refuse(f"visibility evidence {key} mismatch")
    file_sha, inner_sha = _world_records_file_and_inner_sha256(world_records_payload, world_records_raw)
    if evidence.get("world_records_sha256") != file_sha:
        _refuse("visibility evidence WORLD_RECORDS digest mismatch")
    if evidence.get("inner_records_sha256") != inner_sha:
        _refuse("visibility evidence inner records digest mismatch")
    if file_sha != WORLD_RECORDS_SHA256 or inner_sha != INNER_RECORDS_SHA256:
        _refuse("canonical WORLD_RECORDS digest is not the immutable artifact")
    worlds = evidence.get("worlds")
    records = world_records_payload.get("records")
    if not isinstance(worlds, list) or not isinstance(records, list):
        _refuse("visibility worlds / WORLD_RECORDS records missing")
    if len(worlds) != 3200 or len(records) != 3200:
        _refuse("visibility world count is not 3200")
    ids = [row.get("world_id") for row in worlds]
    rec_ids = [row.get("world_id") for row in records]
    if ids != rec_ids:
        _refuse("visibility world_id sequence does not match canonical WORLD_RECORDS order")
    if len(set(ids)) != 3200:
        _refuse("visibility world_id uniqueness failed")
    worlds_bytes = canonical_json_bytes(worlds)
    if evidence.get("worlds_sha256") != _sha256_bytes(worlds_bytes):
        _refuse("visibility worlds_sha256 mismatch")
    if evidence.get("worlds_size") != len(worlds_bytes):
        _refuse("visibility worlds_size mismatch")
    visible: dict[str, bool] = {}
    for row in worlds:
        if not isinstance(row, Mapping):
            _refuse("visibility world row is malformed")
        if "GROUND_TRUTH_VISIBLE" not in row:
            _refuse("visibility world row missing GROUND_TRUTH_VISIBLE")
        if row.get("visibility_invalid") is True and row.get("GROUND_TRUTH_VISIBLE") is True:
            _refuse("invalid replicate cannot be GROUND_TRUTH_VISIBLE")
        visible[str(row["world_id"])] = bool(row["GROUND_TRUTH_VISIBLE"])
    return visible


def write_v2_visibility_evidence(repo_root: Path, evidence: Mapping[str, Any]) -> Path:
    path = Path(repo_root) / CANONICAL_V2_VISIBILITY_PATH
    _atomic_replace_bytes(path, canonical_json_bytes(evidence))
    return path


def _cell(cells: Mapping[tuple[str, int], Any], scenario: str, n_rows: int):
    return cells.get((scenario, n_rows))


def _visibility_rate(
    cell: Any, visible: Mapping[str, bool]
) -> tuple[int, int]:
    successes = 0
    n = 0
    for rec in cell.worlds:
        if rec.world_state != WORLD_VALID:
            continue
        n += 1
        if rec.world_id not in visible:
            _refuse(f"visibility missing for WORLD_VALID {rec.world_id}")
        if visible[rec.world_id] is True:
            successes += 1
    if n != cell.world_valid_count:
        _refuse("WORLD_VALID count does not match visibility denominator")
    return successes, n


def _floor_label(wilson_upper: float) -> str:
    if wilson_upper < VISIBILITY_FLOOR_THRESHOLD:
        return "VISIBILITY_FLOOR"
    return "ABOVE_MEASURED_FLOOR"


def _model_floor_label(wilson_upper: float, *, visibility_binds: bool) -> str:
    if visibility_binds:
        return "ABOVE_MEASURED_FLOOR"
    if wilson_upper < VISIBILITY_FLOOR_THRESHOLD:
        return "MODEL_FLOOR"
    return "ABOVE_MEASURED_FLOOR"


@dataclass(frozen=True)
class _VisibilityInherited:
    labels: dict[str, str]
    easy_visibility_wilson_upper: float


def derive_visibility_blocked_inherited(
    records: Sequence[WorldRecordV2], visible: Mapping[str, bool]
) -> _VisibilityInherited:
    """Amendment_003 visibility-dependent ids from authenticated GROUND_TRUTH_VISIBLE."""
    cells = aggregate_v2_records(records)
    easy = _cell(cells, "EASY", 5000)
    tiny = _cell(cells, "TINY_NOISY", 5000)
    if easy is None or tiny is None:
        _refuse("required EASY|5000 or TINY_NOISY|5000 cell missing")
    easy_s, easy_n = _visibility_rate(easy, visible)
    tiny_s, tiny_n = _visibility_rate(tiny, visible)
    if easy_n <= 0 or tiny_n <= 0:
        _refuse("visibility denominator is empty")
    easy_upper = wilson_interval(easy_s, easy_n)["upper"]
    tiny_upper = wilson_interval(tiny_s, tiny_n)["upper"]
    vis_label = _floor_label(easy_upper)
    ident = easy.candidate_identifiable_count.get("F03", 0)
    det = easy.candidate_detection_count.get("F03", 0)
    if ident <= 0:
        _refuse("MODEL_FLOOR identifiable denominator is empty")
    model_upper = wilson_interval(det, ident)["upper"]
    model_label = _model_floor_label(model_upper, visibility_binds=vis_label == "VISIBILITY_FLOOR")
    tiny_ident = tiny.candidate_identifiable_count.get("F03", 0)
    tiny_det = tiny.candidate_detection_count.get("F03", 0)
    if tiny_ident <= 0:
        _refuse("TINY_NOISY model-leg identifiable denominator is empty")
    tiny_model_upper = wilson_interval(tiny_det, tiny_ident)["upper"]
    if tiny_upper < VISIBILITY_FLOOR_THRESHOLD:
        tiny_label = "VISIBILITY_FLOOR"
    elif tiny_model_upper < VISIBILITY_FLOOR_THRESHOLD:
        tiny_label = "MODEL_FLOOR"
    else:
        tiny_label = "ABOVE_MEASURED_FLOOR"
    return _VisibilityInherited(
        labels={
            "VISIBILITY_FLOOR": vis_label,
            "MODEL_FLOOR": model_label,
            "TINY_NOISY_ORACLE_DIAGNOSTIC": tiny_label,
            "TINY_NOISY_CONCLUSION": tiny_label,
            "ORACLE_F03_TINY_NOISY": tiny_label,
        },
        easy_visibility_wilson_upper=float(easy_upper),
    )


def derive_v2_final_overall_with_visibility(
    records: Sequence[WorldRecordV2],
    *,
    structurally_complete: bool,
    visible: Mapping[str, bool],
) -> str:
    if not structurally_complete:
        return mechanical_conclusion(
            incomplete_execution=True,
            oracle_null_specificity="PASS",
            blind_null_specificity="PASS",
            trap_specificity="PASS",
            easy_oracle_power="PASS",
            moderate_oracle_power="PASS",
            easy_blind_useful="PASS",
            moderate_blind_useful="PASS",
        )
    blocked = derive_visibility_blocked_inherited(records, visible)
    from scripts.research.harness_synthetic_edge_calibration_v2_inherited_ladder import (
        _derive_raw_values,
    )  # noqa: PLC0415 — local import keeps ARM-bound module unedited

    cells = aggregate_v2_records(records)
    raw = _derive_raw_values(cells)
    null_gate = raw["NULL_PER_CANDIDATE_FPR"]
    trap_folded = _comb(raw["NONSTATIONARY_TRAP_ORACLE_SPECIFICITY"], null_gate)
    model_upper = None
    model_cell = cells.get(("EASY", 5000))
    if model_cell is not None:
        ident = model_cell.candidate_identifiable_count.get("F03", 0)
        if ident > 0:
            model_upper = wilson_interval(
                model_cell.candidate_detection_count.get("F03", 0), ident
            )["upper"]
    return mechanical_conclusion(
        incomplete_execution=False,
        oracle_null_specificity=raw["NULL_ORACLE_FPR"],
        blind_null_specificity=raw["NULL_BLIND_FPR"],
        trap_specificity=trap_folded,
        easy_oracle_power=raw["EASY_ORACLE_POWER"],
        moderate_oracle_power=raw["MODERATE_ORACLE_POWER"],
        easy_blind_useful=raw["EASY_BLIND_USEFUL_DISCOVERY"],
        moderate_blind_useful=raw["MODERATE_BLIND_USEFUL_DISCOVERY"],
        visibility_wilson_upper=blocked.easy_visibility_wilson_upper,
        model_detection_wilson_upper=model_upper,
        materiality_only_failure=bool(raw["_materiality_only_failure_bool"]),
    )


def derive_v2_mechanical_conclusions_with_visibility(
    records: Sequence[WorldRecordV2],
    *,
    structurally_complete: bool,
    visible: Mapping[str, bool],
) -> dict[str, str]:
    """Frozen mechanical conclusions consuming authenticated GROUND_TRUTH_VISIBLE."""
    from scripts.research.harness_synthetic_edge_calibration_v2_inherited_ladder import (
        _coverage_inputs_for_records,
    )

    coverage_status = derive_v2_required_coverage_status(records)
    needed = [
        cid
        for cid, coverage in coverage_status.items()
        if structurally_complete
        and coverage == COVERAGE_ADEQUATE
        and cid != FINAL_OVERALL_ID
        and cid not in VISIBILITY_BLOCKED_IDS
    ]
    inherited = derive_v2_inherited_conclusions_needed(
        records, needed, structurally_complete=structurally_complete
    )
    if structurally_complete and any(
        coverage_status.get(cid) == COVERAGE_ADEQUATE for cid in VISIBILITY_BLOCKED_IDS
    ):
        inherited.update(derive_visibility_blocked_inherited(records, visible).labels)
    conclusions: dict[str, str] = {}
    for conclusion_id, coverage in coverage_status.items():
        if conclusion_id == FINAL_OVERALL_ID:
            continue
        if structurally_complete and coverage == COVERAGE_ADEQUATE:
            inherited_value = inherited[conclusion_id]
        else:
            inherited_value = "NOT_CLAIMABLE"
        conclusions[conclusion_id] = mechanical_conclusion_v2(
            structurally_complete=structurally_complete,
            coverage_for_conclusion=coverage,
            inherited_detection_conclusion=inherited_value,
        )
    candidate_verdicts, baseline_verdicts = _coverage_inputs_for_records(records)
    coverage_final = required_coverage_for_conclusion(
        FINAL_OVERALL_ID,
        candidate_verdicts_by_cell=candidate_verdicts,
        baseline_verdicts_by_cell=baseline_verdicts,
    )
    if not structurally_complete:
        conclusions[FINAL_OVERALL_ID] = MECHANICAL_STRUCTURAL_INCOMPLETE
    elif coverage_final != COVERAGE_ADEQUATE:
        conclusions[FINAL_OVERALL_ID] = MECHANICAL_INSUFFICIENT_IDENTIFIABILITY
    else:
        label = derive_v2_final_overall_with_visibility(
            records, structurally_complete=True, visible=visible
        )
        allowed = frozen_final_overall_terminal_labels()
        if label not in allowed:
            _refuse(f"canonical FINAL_OVERALL produced unknown label {label!r}")
        conclusions[FINAL_OVERALL_ID] = label
    return conclusions


def assemble_v2_result_payload_with_visibility(
    repo_root: Path,
    arm_commit: str,
    world_records: Mapping[str, Any],
    records: Sequence[WorldRecordV2],
    *,
    visible: Mapping[str, bool],
) -> dict[str, Any]:
    """RESULT payload plumbing. Does not write RESULT and is not invoked by this unit."""
    from scripts.research.harness_synthetic_edge_calibration_v2_production import (
        V2_RESULT_SCHEMA,
        canonical_v2_production_jobs,
    )

    bound = verify_historical_v2_execution_authority(Path(repo_root), arm_commit)
    jobs = canonical_v2_production_jobs()
    structurally_complete = len(records) == len(jobs)
    aggregates = derive_v2_cell_aggregates(records)
    conclusions = derive_v2_mechanical_conclusions_with_visibility(
        records, structurally_complete=structurally_complete, visible=visible
    )
    return {
        "schema": V2_RESULT_SCHEMA,
        "schema_version": "1.0.0",
        "run_identity": bound["run_identity"],
        "arm_commit": bound["arm_commit"],
        "canonical_v2_plan_sha256": bound["canonical_v2_plan_sha256"],
        "world_records_sha256": world_records["records_sha256"],
        "world_records_size": world_records["records_size"],
        "world_records_count": world_records["record_count"],
        "cell_aggregates": aggregates,
        "conclusions": conclusions,
        "final_overall_conclusion": conclusions[FINAL_OVERALL_ID],
        "v1_attempt_status": "INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM",
        "v1_3087_subset_claimable": False,
    }
