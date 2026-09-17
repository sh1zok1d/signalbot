"""V3 canonical reservation, durable execution, WORLD_RECORDS, and RESULT.

Mechanical authorization/execution plumbing only. Scientific semantics remain
exactly those frozen in ``harness_synthetic_edge_calibration_v3_confirmatory.py``.
Caller kwargs cannot redefine the grid, feature, B, Wilson mapping, or estimand.

Reservation is the one-shot consumption event. Byte-identical resume of the
same reserved world identities is allowed via the untracked durable partial
store. Scientific rerun, replacement, reseed, and a second reservation are
forbidden.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import multiprocessing
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from scripts.research.harness_synthetic_edge_calibration_v1_lib import world_identity
from scripts.research.harness_synthetic_edge_calibration_v1_production import (
    _atomic_replace_bytes,
    _git,
    _jsonable,
    apply_worker_blas_thread_limits,
    canonical_json_bytes,
)
from scripts.research.harness_synthetic_edge_calibration_v1_production import (
    _refuse_production_durability_hooks,
)
from scripts.research.harness_synthetic_edge_calibration_v3_authority import (
    ACCEPTED_IMPLEMENTATION_HEAD,
    ACCEPTED_IMPLEMENTATION_TREE,
    CANONICAL_V3_ARM_PATH,
    CANONICAL_V3_RESERVATION_PATH,
    CANONICAL_V3_RESULT_PATH,
    CANONICAL_V3_WORLD_RECORDS_PATH,
    FROZEN_ACCEPTANCE,
    FROZEN_B,
    FROZEN_FEATURE_ID,
    FROZEN_N_ROWS,
    FROZEN_PLANNED_WORLDS,
    FROZEN_PREREG_JSON_SHA256,
    FROZEN_SCENARIOS,
    FROZEN_V3_RUN_IDENTITY,
    FROZEN_WILSON_Z,
    FROZEN_WORLD_INDEX_END,
    FROZEN_WORLD_INDEX_START,
    FROZEN_WORLDS_PER_CELL,
    IMPLEMENTATION_FREEZE_HEAD,
    IMPLEMENTATION_FREEZE_TREE,
    LIFECYCLE_RESERVED,
    V3ExecutionNotAuthorized,
    _sha256_bytes,
    assert_v3_executed_bytes_bound,
    authenticate_v3_arm,
    authenticate_v3_arm_binding,
    canonical_v3_jobs,
    inspect_v3_reservation_readiness,
    v3_protected_artifacts_present,
)
from scripts.research.harness_synthetic_edge_calibration_v3_confirmatory import (
    BootstrapEvidence,
    V3WorldRecord,
    aggregate_verdict,
    evaluate_v3_world,
    is_fresh_v3_world_index,
    one_sided_wilson_bounds,
)

V3_RESERVATION_SCHEMA = "harness_synthetic_edge_calibration_v3_production_reservation"
V3_WORLD_RECORDS_SCHEMA = "harness_synthetic_edge_calibration_v3_world_records"
V3_RESULT_SCHEMA = "harness_synthetic_edge_calibration_v3_result"
V3_DURABLE_PARTIAL_KIND = "V3_DURABLE_PARTIAL_WORLD_EVIDENCE"
V3_DURABLE_PARTIAL_RECORD_KIND = "V3_DURABLE_PARTIAL_WORLD_EVIDENCE_RECORD"
V3_DURABLE_PARTIAL_REL = (
    "artifacts/research/harness_synthetic_edge_calibration_v3/"
    "durable_partial_world_evidence"
)
V3_DURABLE_PARTIAL_IDENTITY_NAME = "V3_STORE_IDENTITY.json"
V3_EXECUTION_WORKERS_ENV = "HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_EXECUTION_WORKERS"
ARM_ARTIFACT_SHA256 = "33354b488fea49909540a149c3de9f404342d8fc9c99dbfe43764943ec122822"


def _repo_root() -> Path:
    from scripts.research import harness_synthetic_edge_calibration_v3_authority as auth

    return auth._repo_root()


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _refuse(detail: str) -> None:
    raise V3ExecutionNotAuthorized(f"SYNTHETIC_EXECUTION_NOT_AUTHORIZED: {detail}")


def _refuse_integrity(detail: str) -> None:
    raise V3ExecutionNotAuthorized(f"SYNTHETIC_EXECUTION_NOT_AUTHORIZED: {detail}")


def resolve_v3_execution_workers(workers: object | None = None) -> int:
    if workers is None:
        raw = os.environ.get(V3_EXECUTION_WORKERS_ENV, "1")
        try:
            workers = int(str(raw).strip() or "1")
        except (TypeError, ValueError):
            _refuse("workers must be a positive int")
    if type(workers) is not int or workers < 1:
        _refuse("workers must be a positive int")
    return workers


def authenticate_v3_pre_reservation(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Step 1: fail closed before any reservation is written."""
    from scripts.research.harness_synthetic_edge_calibration_v3_authority import (
        _reject_caller_kwargs,
    )

    _reject_caller_kwargs(args, kwargs)
    assert_v3_executed_bytes_bound()
    ready = inspect_v3_reservation_readiness()
    bound = authenticate_v3_arm()
    if bound["run_identity"] != FROZEN_V3_RUN_IDENTITY:
        _refuse("ARM run identity is not the frozen V3 run identity")
    if ready["run_identity"] != FROZEN_V3_RUN_IDENTITY:
        _refuse("reservation-readiness run identity is not the frozen V3 run identity")
    if bound["freeze_parent_head"] != IMPLEMENTATION_FREEZE_HEAD:
        _refuse("ARM freeze parent HEAD is not the frozen implementation-freeze HEAD")
    if bound["freeze_parent_tree"] != IMPLEMENTATION_FREEZE_TREE:
        _refuse("ARM freeze parent tree is not the frozen implementation-freeze tree")
    jobs = canonical_v3_jobs()
    if len(jobs) != FROZEN_PLANNED_WORLDS:
        _refuse("canonical job count is not 1600")
    return {
        "status": "V3_PRE_RESERVATION_AUTHENTICATED",
        "arm_commit": bound["arm_commit"],
        "run_identity": bound["run_identity"],
        "freeze_parent_head": bound["freeze_parent_head"],
        "freeze_parent_tree": bound["freeze_parent_tree"],
        "canonical_world_count": FROZEN_PLANNED_WORLDS,
        "lifecycle": bound["lifecycle"],
        "authorization_consumed": False,
    }


def _arm_tree(repo_root: Path, arm_commit: str) -> str:
    return (
        _git(repo_root, "rev-parse", f"{arm_commit}^{{tree}}")
        .decode("ascii")
        .strip()
        .lower()
    )


def v3_durable_reservation_document(repo_root: Path | None = None) -> dict[str, Any]:
    repo_root = repo_root or _repo_root()
    bound = authenticate_v3_arm_binding()
    jobs = canonical_v3_jobs()
    jobs_payload = {"jobs": [list(job) for job in jobs]}
    arm_sha = str(bound.get("arm_artifact_sha256") or "")
    if arm_sha != ARM_ARTIFACT_SHA256:
        _refuse("ARM artifact SHA256 is not the frozen one-shot ARM")
    body = {
        "accepted_implementation_head": ACCEPTED_IMPLEMENTATION_HEAD,
        "accepted_implementation_tree": ACCEPTED_IMPLEMENTATION_TREE,
        "arm_artifact_sha256": arm_sha,
        "arm_commit": bound["arm_commit"],
        "arm_tree": _arm_tree(repo_root, bound["arm_commit"]),
        "authorization_consumed": True,
        "b2_06_scientific_execution_authorized": False,
        "bootstrap_replicates": FROZEN_B,
        "canonical_v3_plan_sha256": FROZEN_V3_RUN_IDENTITY,
        "canonical_world_count": FROZEN_PLANNED_WORLDS,
        "default_v4": False,
        "feature_id": FROZEN_FEATURE_ID,
        "freeze_parent_head": IMPLEMENTATION_FREEZE_HEAD,
        "freeze_parent_tree": IMPLEMENTATION_FREEZE_TREE,
        "jobs_sha256": _sha256_bytes(canonical_json_bytes(jobs_payload)),
        "lifecycle": LIFECYCLE_RESERVED,
        "n_rows": FROZEN_N_ROWS,
        "not_a_result": True,
        "not_an_execution": True,
        "one_shot": True,
        "run_identity": FROZEN_V3_RUN_IDENTITY,
        "scenarios": list(FROZEN_SCENARIOS),
        "schema": V3_RESERVATION_SCHEMA,
        "schema_version": "1.0.0",
        "world_index_end": FROZEN_WORLD_INDEX_END,
        "world_index_start": FROZEN_WORLD_INDEX_START,
        "worlds_per_cell": FROZEN_WORLDS_PER_CELL,
    }
    identity = _sha256_bytes(canonical_json_bytes(body))
    return {**body, "reservation_identity": identity}


def establish_v3_durable_reservation(repo_root: Path | None = None) -> dict[str, Any]:
    """Create exactly one tracked reservation. This consumes the one-shot ARM."""
    repo_root = repo_root or _repo_root()
    authenticate_v3_pre_reservation()
    if v3_protected_artifacts_present():
        _refuse("a V3 reservation/evidence artifact already exists")
    status = _git(repo_root, "status", "--porcelain", "--untracked-files=all").decode(
        "utf-8", "surrogateescape"
    )
    if status.strip():
        _refuse("worktree is not clean before establishing a durable reservation")
    reservation = v3_durable_reservation_document(repo_root)
    path = repo_root / CANONICAL_V3_RESERVATION_PATH
    _atomic_replace_bytes(path, canonical_json_bytes(reservation))
    _git(repo_root, "add", "--", CANONICAL_V3_RESERVATION_PATH)
    message = (
        "research(v3): consume one-shot ARM with canonical reservation\n\n"
        "Bind frozen run identity "
        f"{FROZEN_V3_RUN_IDENTITY} / ARM {reservation['arm_commit']}. "
        "Do not execute worlds in this commit.\n"
    )
    _git(repo_root, "commit", "-m", message)
    head = _git(repo_root, "rev-parse", "HEAD").decode("ascii").strip().lower()
    committed = json.loads(
        _git(repo_root, "show", f"{head}:{CANONICAL_V3_RESERVATION_PATH}").decode("utf-8")
    )
    if committed != reservation:
        _refuse_integrity("committed reservation does not match the established reservation identity")
    reservation["reservation_commit"] = head
    reservation["reservation_tree"] = (
        _git(repo_root, "rev-parse", f"{head}^{{tree}}").decode("ascii").strip().lower()
    )
    return reservation


def load_committed_v3_reservation(repo_root: Path | None = None) -> dict[str, Any]:
    repo_root = repo_root or _repo_root()
    raw = _git(repo_root, "show", f"HEAD:{CANONICAL_V3_RESERVATION_PATH}")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
        _refuse("committed V3 reservation is not valid JSON")
    if not isinstance(payload, dict):
        _refuse("committed V3 reservation is not an object")
    return payload


def verify_v3_reservation_committed(repo_root: Path | None = None) -> dict[str, Any]:
    repo_root = repo_root or _repo_root()
    bound = authenticate_v3_arm_binding()
    reservation = load_committed_v3_reservation(repo_root)
    expected = v3_durable_reservation_document(repo_root)
    if reservation != expected:
        _refuse("committed reservation does not match frozen ARM/run identity/grid")
    if reservation.get("run_identity") != bound["run_identity"]:
        _refuse("committed reservation run identity does not match ARM")
    if reservation.get("arm_commit") != bound["arm_commit"]:
        _refuse("committed reservation ARM commit does not match live ARM")
    if reservation.get("authorization_consumed") is not True:
        _refuse("committed reservation must record one-shot consumption")
    if reservation.get("lifecycle") != LIFECYCLE_RESERVED:
        _refuse("committed reservation lifecycle is not RESERVED")
    return reservation


def _worldrecord_to_dict(record: V3WorldRecord) -> dict[str, Any]:
    payload = _jsonable(dataclasses.asdict(record))
    payload["run_identity"] = FROZEN_V3_RUN_IDENTITY
    return payload


def _worldrecord_from_dict(payload: Mapping[str, Any]) -> V3WorldRecord:
    raw = dict(payload)
    raw.pop("run_identity", None)
    evidence_raw = raw.get("bootstrap_evidence")
    evidence = None
    if isinstance(evidence_raw, Mapping):
        evidence = BootstrapEvidence(
            b_hat=float(evidence_raw["b_hat"]),
            theta_star=np.asarray(evidence_raw["theta_star"], dtype=np.float64),
            se_hat=float(evidence_raw["se_hat"]),
            t_obs=float(evidence_raw["t_obs"]),
            t_star=np.asarray(evidence_raw["t_star"], dtype=np.float64),
            p_one_sided=float(evidence_raw["p_one_sided"]),
        )
    era_effects = dict(raw.get("era_effects") or {})
    return V3WorldRecord(
        scenario=str(raw["scenario"]),
        n_rows=int(raw["n_rows"]),
        world_index=int(raw["world_index"]),
        world_id=str(raw["world_id"]),
        feature_id=str(raw["feature_id"]),
        world_valid=bool(raw["world_valid"]),
        validity_guard_failed=raw.get("validity_guard_failed"),
        validity_reason=raw.get("validity_reason"),
        world_seed_int=None if raw.get("world_seed_int") is None else int(raw["world_seed_int"]),
        support_count=None if raw.get("support_count") is None else int(raw["support_count"]),
        support_fraction=raw.get("support_fraction"),
        support_run_count=None
        if raw.get("support_run_count") is None
        else int(raw["support_run_count"]),
        effective_n=raw.get("effective_n"),
        theta_hat=raw.get("theta_hat"),
        raw_conditional_effect=raw.get("raw_conditional_effect"),
        unconditional_effect=raw.get("unconditional_effect"),
        era_effects=era_effects,
        b_hat=raw.get("b_hat"),
        se_hat=raw.get("se_hat"),
        t_obs=raw.get("t_obs"),
        p_one_sided=raw.get("p_one_sided"),
        p_margin_to_alpha=raw.get("p_margin_to_alpha"),
        bootstrap_evidence=evidence,
        relative_mae_improvement=raw.get("relative_mae_improvement"),
        detected=raw.get("detected"),
    )


def _records_equivalent(left: V3WorldRecord, right: V3WorldRecord) -> bool:
    return canonical_json_bytes(_worldrecord_to_dict(left)) == canonical_json_bytes(
        _worldrecord_to_dict(right)
    )


class V3DurablePartialWorldStore:
    """Append-safe per-world cache. Never RESULT / WORLD_RECORDS / ARM."""

    def __init__(self, path: Path, *, run_identity: str, arm_commit: str) -> None:
        self.path = Path(path)
        self.worlds_dir = self.path / "worlds"
        self.identity_path = self.path / V3_DURABLE_PARTIAL_IDENTITY_NAME
        self.run_identity = str(run_identity)
        self.arm_commit = str(arm_commit)

    @classmethod
    def open(cls, path: Path, *, run_identity: str, arm_commit: str) -> "V3DurablePartialWorldStore":
        store = cls(Path(path), run_identity=run_identity, arm_commit=arm_commit)
        store._ensure_identity()
        return store

    def _identity_payload(self) -> dict[str, Any]:
        return {
            "kind": V3_DURABLE_PARTIAL_KIND,
            "schema_version": 1,
            "not_a_production_result": True,
            "not_canonical_world_records": True,
            "authorization_consumed": False,
            "run_identity": self.run_identity,
            "arm_commit": self.arm_commit,
        }

    def _ensure_identity(self) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        self.worlds_dir.mkdir(parents=True, exist_ok=True)
        wanted = self._identity_payload()
        if not self.identity_path.is_file():
            if list(self.worlds_dir.glob("*.json")):
                _refuse("durable partial worlds exist without a store identity")
            _atomic_replace_bytes(self.identity_path, canonical_json_bytes(wanted))
            return
        existing = self._load_json(self.identity_path)
        if existing.get("kind") != V3_DURABLE_PARTIAL_KIND:
            _refuse("durable partial store identity kind is not canonical")
        if existing.get("authorization_consumed") is True:
            _refuse("durable partial store must not consume one-shot authority")
        for key in ("run_identity", "arm_commit"):
            if existing.get(key) != wanted[key]:
                _refuse("durable partial store does not match frozen execution identity")

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        raw = path.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise V3ExecutionNotAuthorized(
                "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: durable partial store payload is torn or malformed"
            ) from exc
        if not isinstance(payload, dict):
            _refuse("durable partial store payload is malformed")
        return payload

    def _world_path(self, world_id: str) -> Path:
        digest = hashlib.sha256(world_id.encode("utf-8")).hexdigest()
        return self.worlds_dir / f"{digest}.json"

    def checkpoint_completed_world(
        self, record: V3WorldRecord, job: tuple[str, int, int]
    ) -> None:
        job = (str(job[0]), int(job[1]), int(job[2]))
        owned = _worldrecord_to_dict(record)
        payload = {
            "kind": V3_DURABLE_PARTIAL_RECORD_KIND,
            "schema_version": 1,
            "completion_status": "COMPLETE",
            "run_identity": self.run_identity,
            "arm_commit": self.arm_commit,
            "scenario_id": job[0],
            "n_rows": job[1],
            "world_index": job[2],
            "record": owned,
            "record_sha256": _sha256_bytes(canonical_json_bytes(owned)),
        }
        target = self._world_path(record.world_id)
        if target.is_file():
            existing = self._load_json(target)
            if existing.get("record_sha256") != payload["record_sha256"]:
                _refuse_integrity("duplicate persisted world identity")
            return
        _atomic_replace_bytes(target, canonical_json_bytes(payload))

    def load_structurally_valid_cached(self) -> dict[tuple[str, int, int], V3WorldRecord]:
        completed: dict[tuple[str, int, int], V3WorldRecord] = {}
        for path in sorted(self.worlds_dir.glob("*.json")):
            if path.name.endswith(".tmp"):
                continue
            payload = self._load_json(path)
            if payload.get("kind") != V3_DURABLE_PARTIAL_RECORD_KIND:
                _refuse_integrity("durable partial world record kind is not canonical")
            if payload.get("completion_status") != "COMPLETE":
                _refuse_integrity("durable partial world record is not complete")
            if payload.get("run_identity") != self.run_identity:
                _refuse_integrity("durable partial world record does not match frozen run identity")
            job = (str(payload["scenario_id"]), int(payload["n_rows"]), int(payload["world_index"]))
            record_dict = payload.get("record")
            if not isinstance(record_dict, dict):
                _refuse_integrity("durable partial world record body is missing")
            if payload.get("record_sha256") != _sha256_bytes(canonical_json_bytes(record_dict)):
                _refuse_integrity("durable partial world record digest mismatch")
            if job in completed:
                _refuse_integrity("duplicate persisted world identity")
            completed[job] = _worldrecord_from_dict(record_dict)
        return completed


def _require_canonical_job(scenario_id: str, n_rows: int, world_index: int) -> tuple[str, int, int]:
    job = (str(scenario_id), int(n_rows), int(world_index))
    if job not in set(canonical_v3_jobs()):
        _refuse("world is not a frozen V3 canonical production-grid identity")
    if int(n_rows) != FROZEN_N_ROWS:
        _refuse("caller n_rows cannot override frozen n_rows=5000")
    if str(scenario_id) not in FROZEN_SCENARIOS:
        _refuse("caller scenario is not a frozen canonical scenario")
    if not is_fresh_v3_world_index(int(world_index)):
        _refuse("world_index is outside frozen 10000..10399")
    expected_id = world_identity(str(scenario_id), int(n_rows), int(world_index))
    _ = expected_id
    return job


def evaluate_canonical_v3_world(scenario_id: str, n_rows: int, world_index: int) -> V3WorldRecord:
    _require_canonical_job(scenario_id, n_rows, world_index)
    verify_v3_reservation_committed()
    return evaluate_v3_world(str(scenario_id), int(n_rows), int(world_index))


def _eval_job(job: tuple[str, int, int]) -> tuple[tuple[str, int, int], dict[str, Any]]:
    apply_worker_blas_thread_limits()
    rec = evaluate_v3_world(job[0], job[1], job[2])
    return job, _worldrecord_to_dict(rec)


def run_canonical_v3_grid_in_session(
    *,
    durable_partial: V3DurablePartialWorldStore | None = None,
    workers: int | None = None,
) -> tuple[V3WorldRecord, ...]:
    _refuse_production_durability_hooks()
    apply_worker_blas_thread_limits()
    reservation = verify_v3_reservation_committed()
    jobs = canonical_v3_jobs()
    cached = durable_partial.load_structurally_valid_cached() if durable_partial is not None else {}
    missing = [job for job in jobs if job not in cached]
    workers_n = resolve_v3_execution_workers(workers)
    computed: dict[tuple[str, int, int], V3WorldRecord] = {}
    done = 0
    total_missing = len(missing)
    _log(
        f"V3 canonical grid: {len(cached)} cached, {total_missing} missing, workers={workers_n}"
    )
    if missing:
        if workers_n == 1:
            for job in missing:
                rec = evaluate_v3_world(*job)
                computed[job] = rec
                if durable_partial is not None:
                    durable_partial.checkpoint_completed_world(rec, job)
                done += 1
                if done % 50 == 0 or done == total_missing:
                    _log(f"V3 canonical grid progress {done}/{total_missing}")
        else:
            ctx = multiprocessing.get_context("spawn")
            with ctx.Pool(processes=workers_n) as pool:
                for job, payload in pool.imap_unordered(_eval_job, missing, chunksize=1):
                    rec = _worldrecord_from_dict(payload)
                    computed[job] = rec
                    if durable_partial is not None:
                        durable_partial.checkpoint_completed_world(rec, job)
                    done += 1
                    if done % 50 == 0 or done == total_missing:
                        _log(f"V3 canonical grid progress {done}/{total_missing}")
    records: list[V3WorldRecord] = []
    for job in jobs:
        rec = cached[job] if job in cached else computed[job]
        if rec.scenario != job[0] or rec.n_rows != job[1] or rec.world_index != job[2]:
            _refuse_integrity("world record identity drifted from reserved job")
        if rec.feature_id != FROZEN_FEATURE_ID:
            _refuse_integrity("world record feature_id is not frozen F03")
        records.append(rec)
    if len(records) != FROZEN_PLANNED_WORLDS:
        _refuse_integrity("canonical evidence set is not 1600 worlds")
    _ = reservation
    return tuple(records)


def open_default_v3_durable_store(repo_root: Path | None = None) -> V3DurablePartialWorldStore:
    repo_root = repo_root or _repo_root()
    reservation = verify_v3_reservation_committed()
    return V3DurablePartialWorldStore.open(
        repo_root / V3_DURABLE_PARTIAL_REL,
        run_identity=reservation["run_identity"],
        arm_commit=reservation["arm_commit"],
    )


def derive_v3_cell_aggregates(records: Sequence[V3WorldRecord]) -> dict[str, dict[str, Any]]:
    by_cell: dict[str, list[V3WorldRecord]] = {cell: [] for cell in FROZEN_SCENARIOS}
    for rec in records:
        if rec.scenario not in by_cell:
            _refuse_integrity(f"unexpected scenario in evidence: {rec.scenario}")
        by_cell[rec.scenario].append(rec)
    aggregates: dict[str, dict[str, Any]] = {}
    for cell, expected in FROZEN_ACCEPTANCE.items():
        cell_records = by_cell[cell]
        attempted = len(cell_records)
        valid = sum(1 for rec in cell_records if rec.world_valid)
        invalid = attempted - valid
        detected = sum(
            1 for rec in cell_records if rec.world_valid and rec.detected is True
        )
        structurally_complete = attempted == FROZEN_WORLDS_PER_CELL
        planned = FROZEN_WORLDS_PER_CELL
        if structurally_complete:
            lower, upper = one_sided_wilson_bounds(detected, planned, z=FROZEN_WILSON_Z)
            verdict = aggregate_verdict(cell, detected, planned)
        else:
            lower, upper = (None, None)
            verdict = "INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM"
        invalid_by_guard: dict[str, int] = {}
        for rec in cell_records:
            if rec.world_valid:
                continue
            guard = rec.validity_guard_failed or "UNKNOWN"
            invalid_by_guard[guard] = invalid_by_guard.get(guard, 0) + 1
        aggregates[cell] = {
            "attempted": attempted,
            "planned": planned,
            "valid": valid,
            "invalid": invalid,
            "detected": detected,
            "not_detected": planned - detected if structurally_complete else attempted - detected,
            "rate": (detected / planned) if structurally_complete else None,
            "wilson_lower": lower,
            "wilson_upper": upper,
            "wilson_z": FROZEN_WILSON_Z,
            "frozen_target": dict(expected),
            "verdict": verdict,
            "structurally_complete": structurally_complete,
            "invalid_by_guard": invalid_by_guard,
        }
    return aggregates


def derive_v3_mechanical_conclusion(
    records: Sequence[V3WorldRecord],
) -> dict[str, Any]:
    aggregates = derive_v3_cell_aggregates(records)
    structurally_complete = len(records) == FROZEN_PLANNED_WORLDS and all(
        cell["structurally_complete"] for cell in aggregates.values()
    )
    cell_verdicts = {cell: aggregates[cell]["verdict"] for cell in FROZEN_SCENARIOS}
    if not structurally_complete:
        overall = "INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM"
        claimable = False
    else:
        overall = {
            "EASY": cell_verdicts["EASY"],
            "MODERATE": cell_verdicts["MODERATE"],
            "NULL": cell_verdicts["NULL"],
            "NONSTATIONARY_TRAP": cell_verdicts["NONSTATIONARY_TRAP"],
        }
        claimable = all(verdict == "PASS" for verdict in cell_verdicts.values())
    return {
        "structurally_complete": structurally_complete,
        "cell_verdicts": cell_verdicts,
        "final_mechanical_conclusion": overall,
        "methodology_claimable": claimable,
        "incomplete_execution": not structurally_complete,
        "v3_rerun_authorized": False,
        "default_v4": False,
        "b2_06_scientific_execution_authorized": False,
        "market_execution_authorized": False,
    }


def mint_v3_world_records_payload(
    records: Sequence[V3WorldRecord],
    *,
    operational_execution: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    reservation = verify_v3_reservation_committed()
    jobs = canonical_v3_jobs()
    if len(records) != len(jobs):
        _refuse_integrity("evidence set does not match canonical world count")
    workers_n = resolve_v3_execution_workers()
    apply_worker_blas_thread_limits()
    recomputed: dict[tuple[str, int, int], V3WorldRecord] = {}
    if workers_n == 1:
        for job in jobs:
            recomputed[job] = evaluate_v3_world(*job)
    else:
        ctx = multiprocessing.get_context("spawn")
        with ctx.Pool(processes=workers_n) as pool:
            for job, payload in pool.imap_unordered(_eval_job, jobs, chunksize=1):
                recomputed[job] = _worldrecord_from_dict(payload)
    authenticated: list[V3WorldRecord] = []
    for record, job in zip(records, jobs):
        fresh = recomputed[job]
        if not _records_equivalent(record, fresh):
            _refuse_integrity("caller-supplied world record does not match frozen execution")
        authenticated.append(fresh)
    serialized = [_worldrecord_to_dict(rec) for rec in authenticated]
    records_bytes = canonical_json_bytes(serialized)
    payload: dict[str, Any] = {
        "schema": V3_WORLD_RECORDS_SCHEMA,
        "schema_version": "1.0.0",
        "run_identity": reservation["run_identity"],
        "reservation_identity": reservation["reservation_identity"],
        "arm_commit": reservation["arm_commit"],
        "canonical_v3_plan_sha256": reservation["canonical_v3_plan_sha256"],
        "accepted_implementation_head": ACCEPTED_IMPLEMENTATION_HEAD,
        "freeze_parent_head": IMPLEMENTATION_FREEZE_HEAD,
        "record_count": len(serialized),
        "records": serialized,
        "records_sha256": _sha256_bytes(records_bytes),
        "records_size": len(records_bytes),
    }
    if operational_execution is not None:
        payload["operational_execution"] = {
            **dict(operational_execution),
            "not_scientific_authority": True,
        }
    return payload


def mint_v3_result_payload(
    world_records: Mapping[str, Any],
    records: Sequence[V3WorldRecord],
) -> dict[str, Any]:
    reservation = verify_v3_reservation_committed()
    if world_records.get("run_identity") != reservation["run_identity"]:
        _refuse("WORLD_RECORDS run identity does not match reservation")
    if world_records.get("reservation_identity") != reservation["reservation_identity"]:
        _refuse("WORLD_RECORDS reservation identity does not match reservation")
    serialized = world_records.get("records")
    if not isinstance(serialized, list):
        _refuse("WORLD_RECORDS records missing")
    records_bytes = canonical_json_bytes(serialized)
    if world_records.get("records_sha256") != _sha256_bytes(records_bytes):
        _refuse("WORLD_RECORDS inner records_sha256 mismatch")
    if world_records.get("records_size") != len(records_bytes):
        _refuse("WORLD_RECORDS inner records_size mismatch")
    aggregates = derive_v3_cell_aggregates(records)
    conclusion = derive_v3_mechanical_conclusion(records)
    return {
        "schema": V3_RESULT_SCHEMA,
        "schema_version": "1.0.0",
        "run_identity": reservation["run_identity"],
        "reservation_identity": reservation["reservation_identity"],
        "arm_commit": reservation["arm_commit"],
        "arm_artifact_sha256": ARM_ARTIFACT_SHA256,
        "canonical_v3_plan_sha256": reservation["canonical_v3_plan_sha256"],
        "freeze_parent_head": IMPLEMENTATION_FREEZE_HEAD,
        "freeze_parent_tree": IMPLEMENTATION_FREEZE_TREE,
        "accepted_implementation_head": ACCEPTED_IMPLEMENTATION_HEAD,
        "accepted_implementation_tree": ACCEPTED_IMPLEMENTATION_TREE,
        "prereg_json_sha256": FROZEN_PREREG_JSON_SHA256,
        "world_records_sha256": None,  # filled by persist after file bytes exist
        "world_records_inner_sha256": world_records["records_sha256"],
        "world_records_inner_size": world_records["records_size"],
        "world_records_count": world_records["record_count"],
        "cell_aggregates": aggregates,
        "conclusions": conclusion,
        "final_mechanical_conclusion": conclusion["final_mechanical_conclusion"],
        "methodology_claimable": conclusion["methodology_claimable"],
        "incomplete_execution": conclusion["incomplete_execution"],
        "v3_rerun_authorized": False,
        "default_v4": False,
        "b2_06_scientific_execution_authorized": False,
        "market_execution_authorized": False,
    }


def persist_v3_world_records(payload: Mapping[str, Any], repo_root: Path | None = None) -> dict[str, Any]:
    repo_root = repo_root or _repo_root()
    path = repo_root / CANONICAL_V3_WORLD_RECORDS_PATH
    if path.exists():
        _refuse("canonical V3 WORLD_RECORDS already exist")
    body = canonical_json_bytes(payload)
    _atomic_replace_bytes(path, body)
    return {
        "path": CANONICAL_V3_WORLD_RECORDS_PATH,
        "sha256": _sha256_bytes(body),
        "size": len(body),
        "inner_records_sha256": payload["records_sha256"],
        "inner_records_size": payload["records_size"],
    }


def persist_v3_result(
    payload: Mapping[str, Any],
    world_records_file: Mapping[str, Any],
    repo_root: Path | None = None,
) -> dict[str, Any]:
    repo_root = repo_root or _repo_root()
    path = repo_root / CANONICAL_V3_RESULT_PATH
    if path.exists():
        _refuse("canonical V3 RESULT already exists")
    filled = dict(payload)
    filled["world_records_sha256"] = world_records_file["sha256"]
    filled["world_records_size"] = world_records_file["size"]
    filled["world_records_path"] = CANONICAL_V3_WORLD_RECORDS_PATH
    body = canonical_json_bytes(filled)
    _atomic_replace_bytes(path, body)
    return {
        "path": CANONICAL_V3_RESULT_PATH,
        "sha256": _sha256_bytes(body),
        "size": len(body),
        "payload": filled,
    }


def mint_result_from_persisted_world_records(repo_root: Path | None = None) -> dict[str, Any]:
    repo_root = repo_root or _repo_root()
    reservation = verify_v3_reservation_committed()
    wr_path = repo_root / CANONICAL_V3_WORLD_RECORDS_PATH
    if not wr_path.is_file():
        _refuse("V3 RESULT cannot be minted before authenticated WORLD_RECORDS")
    wr_raw = wr_path.read_bytes()
    world_records = json.loads(wr_raw.decode("utf-8"))
    serialized = world_records.get("records")
    if not isinstance(serialized, list):
        _refuse("WORLD_RECORDS records missing")
    records = [_worldrecord_from_dict(item) for item in serialized]
    result_payload = mint_v3_result_payload(world_records, records)
    wr_file = {
        "path": CANONICAL_V3_WORLD_RECORDS_PATH,
        "sha256": _sha256_bytes(wr_raw),
        "size": len(wr_raw),
    }
    _ = reservation
    return persist_v3_result(result_payload, wr_file, repo_root)


def execute_canonical_v3_production() -> dict[str, Any]:
    """Reserved-grid execution + WORLD_RECORDS + RESULT. No caller overrides."""
    _refuse_production_durability_hooks()
    repo_root = _repo_root()
    if (repo_root / CANONICAL_V3_WORLD_RECORDS_PATH).exists() or (
        repo_root / CANONICAL_V3_RESULT_PATH
    ).exists():
        _refuse("canonical V3 WORLD_RECORDS/RESULT already exist")
    reservation = verify_v3_reservation_committed()
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    store = open_default_v3_durable_store()
    records = run_canonical_v3_grid_in_session(durable_partial=store)
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    wr_payload = mint_v3_world_records_payload(
        records,
        operational_execution={"started_at_utc": started, "ended_at_utc": ended},
    )
    wr_file = persist_v3_world_records(wr_payload)
    result_payload = mint_v3_result_payload(wr_payload, records)
    result_file = persist_v3_result(result_payload, wr_file)
    return {
        "reservation_identity": reservation["reservation_identity"],
        "run_identity": reservation["run_identity"],
        "started_at_utc": started,
        "ended_at_utc": ended,
        "records": records,
        "world_records_file": wr_file,
        "result_file": result_file,
        "aggregates": result_file["payload"]["cell_aggregates"],
        "conclusion": result_file["payload"]["conclusions"],
    }


def verify_persisted_v3_result(repo_root: Path | None = None) -> bool:
    """Reassemble RESULT from WORLD_RECORDS + frozen aggregate machinery."""
    repo_root = repo_root or _repo_root()
    reservation = verify_v3_reservation_committed()
    wr_path = repo_root / CANONICAL_V3_WORLD_RECORDS_PATH
    result_path = repo_root / CANONICAL_V3_RESULT_PATH
    wr_raw = wr_path.read_bytes()
    result_raw = result_path.read_bytes()
    world_records = json.loads(wr_raw.decode("utf-8"))
    result = json.loads(result_raw.decode("utf-8"))
    if _sha256_bytes(wr_raw) != result.get("world_records_sha256"):
        return False
    if world_records.get("run_identity") != reservation["run_identity"]:
        return False
    serialized = world_records.get("records")
    if not isinstance(serialized, list):
        return False
    records = [_worldrecord_from_dict(item) for item in serialized]
    recomputed_aggregates = derive_v3_cell_aggregates(records)
    recomputed_conclusion = derive_v3_mechanical_conclusion(records)
    if canonical_json_bytes(recomputed_aggregates) != canonical_json_bytes(
        result.get("cell_aggregates")
    ):
        return False
    if canonical_json_bytes(recomputed_conclusion) != canonical_json_bytes(
        result.get("conclusions")
    ):
        return False
    if result.get("final_mechanical_conclusion") != recomputed_conclusion[
        "final_mechanical_conclusion"
    ]:
        return False
    return True


if __name__ == "__main__":
    outcome = execute_canonical_v3_production()
    report = {
        "reservation_identity": outcome["reservation_identity"],
        "run_identity": outcome["run_identity"],
        "started_at_utc": outcome["started_at_utc"],
        "ended_at_utc": outcome["ended_at_utc"],
        "world_records_file": {
            key: outcome["world_records_file"][key]
            for key in ("path", "sha256", "size", "inner_records_sha256", "inner_records_size")
            if key in outcome["world_records_file"]
        },
        "result_file": {
            key: outcome["result_file"][key] for key in ("path", "sha256", "size")
        },
        "aggregates": {
            cell: {
                key: value[key]
                for key in (
                    "attempted",
                    "valid",
                    "invalid",
                    "detected",
                    "rate",
                    "wilson_lower",
                    "wilson_upper",
                    "verdict",
                )
            }
            for cell, value in outcome["aggregates"].items()
        },
        "conclusion": outcome["conclusion"],
    }
    print(json.dumps(report, sort_keys=True, indent=2))

