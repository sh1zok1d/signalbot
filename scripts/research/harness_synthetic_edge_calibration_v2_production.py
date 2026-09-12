"""V2 production driver: canonical plan derivation + ARM-authorization runtime.

This module implements ONLY the execution layer that the frozen V2
rank-degeneracy fixture (``harness_synthetic_edge_calibration_v2_rank_policy``)
intentionally does not provide: a canonical production plan mechanically
inherited from the frozen V1 grid, a thin production orchestration layer, and
a runtime ARM-authorization function analogous in role to
``harness_synthetic_edge_calibration_v1_production.production_monte_carlo_arm_authorized``.

It does NOT reimplement V2 scientific or classification semantics. Every
per-world classification decision is delegated verbatim to the frozen
fixture's own private inner function
(``harness_synthetic_edge_calibration_v2_rank_policy._evaluate_v2_world_inner``)
so this module can never drift from the reviewed, frozen semantics without
that drift being visible as a diff to the frozen fixture file itself (which
this module never imports privately-mutates and never modifies).

At the HEAD this module is introduced on, there is NO real V2 production ARM
artifact anywhere in the repository. Every entrypoint below therefore refuses
before doing anything: ``v2_production_arm_authorized()`` is False, so
``run_canonical_v2_production_grid`` / ``evaluate_v2_production_world`` /
``mint_v2_result`` all raise ``V2ProductionNotArmed``. This unit does not run
the 3200-world grid, does not mint RESULT/WORLD_RECORDS, and does not consume
authority.
"""

from __future__ import annotations

import dataclasses
import json
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from scripts.research.harness_synthetic_edge_calibration_v1_lib import (
    FEATURE_IDS,
    SyntheticExecutionNotAuthorized,
    simulate_dgp,
)
from scripts.research.harness_synthetic_edge_calibration_v1_production import (
    _atomic_replace_bytes,
    _commit_blob,
    _commit_exists,
    _fsync_directory,
    _git,
    _jsonable,
    _load_commit_json,
    _parent_sha_of,
    _repo_root,
    _sha256_bytes,
    canonical_json_bytes,
    frozen_production_grid,
    planned_jobs_sha256,
    planned_production_jobs,
)
from scripts.research.harness_synthetic_edge_calibration_v2_rank_policy import (
    CANDIDATE_UNDEFINED_ON_INVALID_WORLD,
    COVERAGE_INSUFFICIENT,
    NOT_ERA_SCOPED,
    WORLD_INVALID,
    CandidateWorldRecord,
    ChronologyLookaheadError,
    FitInspection,
    NonidentifiabilityRecord,
    UndefinedCoverageDenominator,
    WorldRecordV2,
    _evaluate_v2_world_inner,
    aggregate_v2_records,
    evaluate_cell_coverage,
    frozen_required_coverage_map,
    mechanical_conclusion_v2,
    required_coverage_for_conclusion,
    world_baseline_coverage_verdict,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

# --- Execution-authoritative source paths ------------------------------------

V2_POLICY_REL = "scripts/research/harness_synthetic_edge_calibration_v2_rank_policy.py"
V2_FREEZE_ARTIFACT_REL = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_IMPLEMENTATION_FREEZE.json"
)

V1_TCB_PATHS = {
    "lib": "scripts/research/harness_synthetic_edge_calibration_v1_lib.py",
    "runner": "scripts/research/harness_synthetic_edge_calibration_v1.py",
    "auth": "scripts/research/harness_synthetic_edge_calibration_v1_auth.py",
    "production": "scripts/research/harness_synthetic_edge_calibration_v1_production.py",
    "worker": "scripts/research/harness_synthetic_edge_calibration_v1_worker.py",
}

FROZEN_V1_TCB_SHA256 = {
    "lib": "12230dcad714e3a06d3f57de69b78fedcab088be950af3d06f959366f01d6c51",
    "runner": "0a5e577cc3797b018e9912865b7c3e385908764dc6cb36a6555626205855432a",
    "auth": "0e174ac6b73530ec28501b0c076e0cad7874ab31bb1ed6941e4b525d12e35507",
    "production": "9e784ecdcbd53ae4128d803d9325c8ff0f6db49ce70a0a63b13c4fc6a548a4ed",
    "worker": "9aee03fdae012f9054c59adc4cea8072b88493521456fb6141ced926961c886e",
}

FROZEN_REVIEWED_IMPLEMENTATION_HEAD = "a310837bab4ee60c7495cca3bdb476abdc58a041"
FROZEN_REVIEWED_IMPLEMENTATION_TREE = "b15c4102b01514ff73e1728aec072eda9b528815"
FROZEN_V2_POLICY_FREEZE_HEAD = "f96197d109fc22c12e4c8ba19715d67c65187c0e"
FROZEN_V2_POLICY_FREEZE_TREE = "ec169d8bd73896308ce4dcf1d5d5fd218cd55bd5"
FROZEN_ORIGINAL_PREREG_HEAD = "ada237edc330b44bc412332e263f124757919e93"
FROZEN_ORIGINAL_PREREG_TREE = "ba1c0873879b7ea8556c3e238f8b962b91da6dc2"
FROZEN_AMENDMENT_001_HEAD = "d8f0a996bc4341d0cbe01a1a061130b889ed5e75"
FROZEN_AMENDMENT_001_TREE = "09dca9b1240a43d5de9de0dadf32d27e00e7eaea"

# --- Canonical V2 authority artifact paths (none of these exist at this HEAD) -

CANONICAL_V2_ARM_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_PRODUCTION_ARM.json"
)
CANONICAL_V2_RESULT_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_RESULT.json"
)
CANONICAL_V2_WORLD_RECORDS_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_WORLD_RECORDS.json"
)
CANONICAL_V2_RESERVATION_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_RESERVATION.json"
)
CANONICAL_V2_CLAIM_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_CLAIM.json"
)

PROTECTED_V2_AUTHORITY_PATHS = (
    CANONICAL_V2_RESULT_PATH,
    CANONICAL_V2_WORLD_RECORDS_PATH,
    CANONICAL_V2_RESERVATION_PATH,
    CANONICAL_V2_CLAIM_PATH,
)

V2_ARM_REQUIRED_LITERALS = {
    "schema": "harness_synthetic_edge_calibration_v2_production_arm",
    "status": "ARMED_FOR_ONE_CANONICAL_V2_PRODUCTION_EXECUTION",
    "authorized_run_count": 1,
    "authorization_consumed": False,
    "descendant_implementation_change_authorized": False,
    "real_market_data_access_authorized": False,
    "other_hypothesis_authorized": False,
    "b2_06_scientific_execution_authorized": False,
    "validation_2025_authorized": False,
    "oos_2026_authorized": False,
}

V2_DURABLE_PARTIAL_KIND = "V2_DURABLE_PARTIAL_WORLD_EVIDENCE"
V2_DURABLE_PARTIAL_RECORD_KIND = "V2_DURABLE_PARTIAL_WORLD_EVIDENCE_RECORD"
V2_DURABLE_PARTIAL_IDENTITY_NAME = "V2_STORE_IDENTITY.json"

V2_WORLD_RECORDS_SCHEMA = "harness_synthetic_edge_calibration_v2_world_records"
V2_RESULT_SCHEMA = "harness_synthetic_edge_calibration_v2_result"


class V2ProductionNotArmed(SyntheticExecutionNotAuthorized):
    """V2 production Monte Carlo is not armed by a verified parent-authorizing ARM."""


class V2ProductionIntegrityError(SyntheticExecutionNotAuthorized):
    """V2 canonical world-set, plan, or policy identity integrity failed closed."""


def _refuse(detail: str) -> None:
    raise SyntheticExecutionNotAuthorized(f"SYNTHETIC_EXECUTION_NOT_AUTHORIZED: {detail}")


def _refuse_integrity(detail: str) -> None:
    """Structural/world-set/checkpoint integrity failures (not authorization)."""
    raise V2ProductionIntegrityError(f"SYNTHETIC_EXECUTION_NOT_AUTHORIZED: {detail}")


# --- V1 TCB integrity (recomputed at runtime, not just at review time) -------


def v1_tcb_digests_at(repo_root: Path, commit: str) -> dict[str, str]:
    digests: dict[str, str] = {}
    for role, rel in V1_TCB_PATHS.items():
        blob = _commit_blob(repo_root, commit, rel)
        if blob is None:
            _refuse(f"V1 TCB file missing from {commit}: {rel}")
        digests[role] = _sha256_bytes(blob)
    return digests


def assert_v1_tcb_intact(repo_root: Path | None = None, commit: str = "HEAD") -> None:
    repo_root = repo_root or _repo_root()
    digests = v1_tcb_digests_at(repo_root, commit)
    for role, expected in FROZEN_V1_TCB_SHA256.items():
        if digests.get(role) != expected:
            _refuse(f"V1 TCB hash drifted for {role}")


# --- Canonical V2 plan: FROZEN_V1_PRODUCTION_GRID + FROZEN_V2_RANK_POLICY ----


def canonical_v2_production_jobs() -> tuple[tuple[str, int, int], ...]:
    """The canonical V2 world set is exactly V1's frozen planned jobs, reused verbatim.

    V2 changes only the identifiability/BLIND interpretation of each world's
    outcome; it does not define a new job list, ordering, N set, or seed
    derivation. Reusing ``planned_production_jobs()`` directly (rather than
    re-deriving an equivalent list) makes reordering, dropping, duplicating,
    or otherwise mutating the canonical world set structurally impossible
    without also mutating the frozen, hash-pinned V1 production module.
    """
    return planned_production_jobs()


def _v2_policy_digest_at(repo_root: Path, commit: str) -> tuple[str, int]:
    blob = _commit_blob(repo_root, commit, V2_POLICY_REL)
    if blob is None:
        _refuse(f"V2 policy source missing from {commit}: {V2_POLICY_REL}")
    return _sha256_bytes(blob), len(blob)


def _v2_freeze_artifact_digest_at(repo_root: Path, commit: str) -> tuple[str, int]:
    blob = _commit_blob(repo_root, commit, V2_FREEZE_ARTIFACT_REL)
    if blob is None:
        _refuse(f"V2 freeze artifact missing from {commit}: {V2_FREEZE_ARTIFACT_REL}")
    return _sha256_bytes(blob), len(blob)


def canonical_v2_plan(repo_root: Path | None = None, commit: str = "HEAD") -> dict[str, Any]:
    """Deterministically bind FROZEN_V1_PRODUCTION_GRID + FROZEN_V2_RANK_POLICY.

    Changing only the V2 policy identity, or only the V1 grid identity,
    changes this plan's sha256 -- both are embedded in the canonical payload
    below, and neither is invented: ``frozen_production_grid()`` /
    ``planned_production_jobs()`` are reused unmodified from the frozen,
    hash-pinned V1 production module.
    """
    repo_root = repo_root or _repo_root()
    v1_grid = frozen_production_grid()
    v1_jobs = planned_production_jobs()
    policy_sha256, policy_size = _v2_policy_digest_at(repo_root, commit)
    payload = {
        "schema": "harness_synthetic_edge_calibration_v2_canonical_production_plan",
        "schema_version": "1.0.0",
        "v1_frozen_grid": v1_grid,
        "v1_planned_worlds": len(v1_jobs),
        "v1_planned_jobs_sha256": planned_jobs_sha256(v1_jobs),
        "v2_policy_path": V2_POLICY_REL,
        "v2_policy_sha256": policy_sha256,
        "v2_policy_size": policy_size,
    }
    digest = _sha256_bytes(canonical_json_bytes(payload))
    return {"payload": payload, "sha256": digest}


def canonical_v2_world_count() -> int:
    return len(canonical_v2_production_jobs())


# --- ARM runtime authorization ------------------------------------------------


def _v2_protected_artifacts_present_at(repo_root: Path, commit: str) -> bool:
    return any(_commit_blob(repo_root, commit, rel) is not None for rel in PROTECTED_V2_AUTHORITY_PATHS)


def _v2_arm_payload_authorizes_at_commit(
    repo_root: Path, commit: str, payload: Mapping[str, Any]
) -> bool:
    """Verify an ARM payload against the exact git object bytes at ``commit``.

    Scope: ``commit`` must be an examinable ref (in practice always ``HEAD`` of
    the checkout under test -- callers evaluate authorization by checking out
    the commit in question and asking whether *that* HEAD is authorized, the
    same pattern the required test matrix uses).
    """
    if not isinstance(payload, Mapping):
        return False
    for key, expected in V2_ARM_REQUIRED_LITERALS.items():
        if payload.get(key) != expected:
            return False
    parent = _parent_sha_of(repo_root, commit)
    if parent is None:
        return False
    parent_tree = _git(repo_root, "rev-parse", f"{parent}^{{tree}}").decode("ascii").strip().lower()
    if str(payload.get("freeze_parent_head") or "").strip().lower() != parent:
        return False
    if str(payload.get("freeze_parent_tree") or "").strip().lower() != parent_tree:
        return False

    freeze_sha256, freeze_size = _v2_freeze_artifact_digest_at(repo_root, parent)
    if payload.get("freeze_artifact_sha256") != freeze_sha256:
        return False
    if payload.get("freeze_artifact_size") != freeze_size:
        return False

    policy_sha256, policy_size = _v2_policy_digest_at(repo_root, commit)
    if payload.get("v2_policy_sha256") != policy_sha256:
        return False
    if payload.get("v2_policy_size") != policy_size:
        return False

    tcb = v1_tcb_digests_at(repo_root, commit)
    for role, expected in FROZEN_V1_TCB_SHA256.items():
        if tcb.get(role) != expected:
            return False

    plan = canonical_v2_plan(repo_root, commit)
    if payload.get("canonical_v2_plan_sha256") != plan["sha256"]:
        return False
    if payload.get("canonical_world_count") != len(canonical_v2_production_jobs()):
        return False

    if payload.get("original_prereg_head") != FROZEN_ORIGINAL_PREREG_HEAD:
        return False
    if payload.get("original_prereg_tree") != FROZEN_ORIGINAL_PREREG_TREE:
        return False
    if payload.get("amendment_001_head") != FROZEN_AMENDMENT_001_HEAD:
        return False
    if payload.get("amendment_001_tree") != FROZEN_AMENDMENT_001_TREE:
        return False

    if _v2_protected_artifacts_present_at(repo_root, commit):
        return False
    return True


def v2_production_arm_authorized(repo_root: Path | None = None) -> bool:
    repo_root = repo_root or _repo_root()
    payload = _load_commit_json(repo_root, "HEAD", CANONICAL_V2_ARM_PATH)
    if payload is None:
        return False
    try:
        return _v2_arm_payload_authorizes_at_commit(repo_root, "HEAD", payload)
    except SyntheticExecutionNotAuthorized:
        return False


def inspect_v2_production_arm_state(repo_root: Path | None = None) -> dict[str, Any]:
    repo_root = repo_root or _repo_root()
    payload = _load_commit_json(repo_root, "HEAD", CANONICAL_V2_ARM_PATH)
    return {
        "present": payload is not None,
        "authorized": bool(payload is not None and v2_production_arm_authorized(repo_root)),
    }


def v2_production_identity(repo_root: Path | None = None) -> dict[str, Any]:
    repo_root = repo_root or _repo_root()
    try:
        armed = bool(v2_production_arm_authorized(repo_root))
    except SyntheticExecutionNotAuthorized:
        armed = False
    return {
        "v2_production_arm_authorized": armed,
        "canonical_world_count": canonical_v2_world_count(),
        "canonical_v2_plan_sha256": canonical_v2_plan(repo_root)["sha256"],
        "production_calibration_executed": False,
        "production_result_minted": False,
        "world_records_created": False,
        "execution_reserved": False,
        "execution_claimed": False,
        "authorization_consumed": False,
        "v1_attempt_status": "INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM",
        "v1_3087_subset_claimable": False,
    }


# --- Thin production orchestration: delegates ALL classification to the -----
# --- frozen fixture's own private inner function, verbatim. -----------------


def _production_evaluate_one_world(
    world: Mapping[str, Any], *, scenario: str, n_rows: int, world_index: int
) -> WorldRecordV2:
    """Evaluate one world exactly as the frozen fixture's public API would.

    This calls ``_evaluate_v2_world_inner`` -- the exact function object the
    frozen fixture's own ``evaluate_v2_world`` calls after its production-N
    guard passes -- with the same "no fixture-only injection" defaults the
    public wrapper uses. The only code duplicated here is the wrapper's
    guard-adjacent exception-to-``WORLD_INVALID`` conversion glue (not
    classification logic); ``test_harness_synthetic_edge_calibration_v2_production.py``
    proves this glue is byte-for-byte equivalent to the fixture's own wrapper
    across every non-production N reachable through the fixture's public API.
    """
    try:
        return _evaluate_v2_world_inner(
            world,
            scenario=scenario,
            n_rows=n_rows,
            world_index=world_index,
            zero_e1_features=frozenset(),
            zero_e1_baseline=False,
            force_candidate_reason=None,
            force_selected_candidate=None,
            feature_overrides=None,
        )
    except ChronologyLookaheadError:
        world_id = str(world.get("world_identity", f"{scenario}|{n_rows}|{world_index}"))
        return WorldRecordV2(
            world_id=world_id,
            scenario=scenario,
            N=n_rows,
            world_index=world_index,
            world_state=WORLD_INVALID,
            L=None,
            selection_state=None,
            selected_candidate=None,
            taxonomy=None,
            baseline_failure=FitInspection(ok=False, first_failing_era=NOT_ERA_SCOPED),
            candidates={
                cid: CandidateWorldRecord(
                    candidate_id=cid,
                    state=CANDIDATE_UNDEFINED_ON_INVALID_WORLD,
                    detected=None,
                )
                for cid in FEATURE_IDS
            },
        )


def evaluate_v2_production_world(
    scenario_id: str, n_rows: int, world_index: int, *args: Any, **kwargs: Any
) -> WorldRecordV2:
    """Evaluate one frozen-grid world under the frozen V2 policy. Refuses unless armed."""
    if args or kwargs:
        _refuse("caller arguments cannot authorize V2 production evaluation")
    repo_root = _repo_root()
    assert_v1_tcb_intact(repo_root)
    job = (str(scenario_id), int(n_rows), int(world_index))
    if job not in set(canonical_v2_production_jobs()):
        _refuse("world is not a frozen V2 canonical production-grid identity")
    if v2_production_arm_authorized(repo_root) is not True:
        raise V2ProductionNotArmed(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: v2_production_arm_authorized=false"
        )
    world = simulate_dgp(scenario_id=scenario_id, n_rows=int(n_rows), world_index=int(world_index))
    return _production_evaluate_one_world(
        world, scenario=str(scenario_id), n_rows=int(n_rows), world_index=int(world_index)
    )


def run_canonical_v2_production_grid(*args: Any, **kwargs: Any) -> tuple[WorldRecordV2, ...]:
    """Execute the canonical 3200-world V2 calibration. Refuses unless armed."""
    if args or kwargs:
        _refuse("caller arguments cannot authorize the canonical V2 production grid")
    repo_root = _repo_root()
    assert_v1_tcb_intact(repo_root)
    if v2_production_arm_authorized(repo_root) is not True:
        raise V2ProductionNotArmed(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: v2_production_arm_authorized=false"
        )
    records = []
    for scenario_id, n_rows, world_index in canonical_v2_production_jobs():
        records.append(evaluate_v2_production_world(scenario_id, n_rows, world_index))
    return tuple(records)



# =============================================================================
# BLOCKER 1: historical execution-authority verification (commit-parameterized,
# not ambient-HEAD-relative). Reuses the same generic
# _v2_arm_payload_authorizes_at_commit primitive v2_production_arm_authorized()
# uses -- this is an additional entrypoint onto it, not a second
# implementation.
# =============================================================================


def verify_historical_v2_execution_authority(
    repo_root: Path, arm_commit: str
) -> dict[str, Any]:
    """Prove ``arm_commit`` was correctly armed, using git objects at that commit.

    Ambient current HEAD is irrelevant: this neither requires nor implies HEAD
    equals ``arm_commit``. This does not grant live authorization at HEAD; it
    only proves a specific historical commit was (and, by git immutability,
    remains) a legitimate ARM.
    """
    commit = str(arm_commit or "").strip().lower()
    if not _commit_exists(repo_root, commit):
        _refuse("historical ARM commit does not exist in git")
    payload = _load_commit_json(repo_root, commit, CANONICAL_V2_ARM_PATH)
    if payload is None:
        _refuse("historical commit is not armed")
    if not _v2_arm_payload_authorizes_at_commit(repo_root, commit, payload):
        _refuse("historical V2 ARM topology is not authorized")
    parent = _parent_sha_of(repo_root, commit)
    parent_tree = _git(repo_root, "rev-parse", f"{parent}^{{tree}}").decode("ascii").strip().lower()
    arm_tree = _git(repo_root, "rev-parse", f"{commit}^{{tree}}").decode("ascii").strip().lower()
    bound = {
        "arm_commit": commit,
        "arm_tree": arm_tree,
        "freeze_parent_head": parent,
        "freeze_parent_tree": parent_tree,
        "canonical_v2_plan_sha256": payload["canonical_v2_plan_sha256"],
        "v2_policy_sha256": payload["v2_policy_sha256"],
    }
    bound["run_identity"] = v2_run_identity(bound)
    return bound


def v2_run_identity(bound: Mapping[str, Any]) -> str:
    """Durable run identity from an exact historically-verified bound only."""
    payload = {
        "schema": "harness_synthetic_edge_calibration_v2_run_identity",
        "arm_commit": bound["arm_commit"],
        "arm_tree": bound["arm_tree"],
        "freeze_parent_head": bound["freeze_parent_head"],
        "canonical_v2_plan_sha256": bound["canonical_v2_plan_sha256"],
        "v2_policy_sha256": bound["v2_policy_sha256"],
    }
    return _sha256_bytes(canonical_json_bytes(payload))


# =============================================================================
# BLOCKER 2: durable reservation / claim / consumption.
#
# Reservation and claim are, like V1's own already-frozen
# durable_reservation_document/durable_claim_document, pure identity
# derivations from an exact historically-verified bound -- they do not
# self-attest anything. Durability comes from committing the derived payload
# to git as an immediate/reachable descendant of the ARM: once one process's
# reservation commit lands, it is a tracked, immutable git object, and every
# later authorization check (this module's existing
# _v2_protected_artifacts_present_at, extended to the reservation/claim paths)
# fails closed against it. A concurrent second attempt racing to commit the
# same reservation is resolved the same way git itself resolves any
# concurrent write to a shared ref: whichever commit is pushed/merged first
# durably wins, and the loser's authorization check sees the artifact already
# present and refuses. This module does not invent a distributed lock beyond
# that -- it matches the guarantee level V1's own already-reviewed
# reservation/claim design provides.
# =============================================================================


def v2_durable_reservation_document(repo_root: Path, arm_commit: str) -> dict[str, Any]:
    """Reservation identity from an exact historically-verified bound only."""
    bound = verify_historical_v2_execution_authority(repo_root, arm_commit)
    return {
        "schema": "harness_synthetic_edge_calibration_v2_production_reservation",
        "schema_version": "1.0.0",
        "run_identity": bound["run_identity"],
        "arm_commit": bound["arm_commit"],
        "arm_tree": bound["arm_tree"],
        "canonical_v2_plan_sha256": bound["canonical_v2_plan_sha256"],
        "v2_policy_sha256": bound["v2_policy_sha256"],
        "authorization_consumed": False,
    }


def v2_durable_claim_document(repo_root: Path, arm_commit: str) -> dict[str, Any]:
    """Claim identity: the same tracked run identity as the reservation."""
    reservation = v2_durable_reservation_document(repo_root, arm_commit)
    return {
        "schema": "harness_synthetic_edge_calibration_v2_production_claim",
        "schema_version": "1.0.0",
        "run_identity": reservation["run_identity"],
        "arm_commit": reservation["arm_commit"],
        "reservation_sha256": _sha256_bytes(canonical_json_bytes(reservation)),
        "authorization_consumed": False,
        "production_calibration_executed": False,
        "result_minted": False,
    }


def assert_v2_reservation_available(repo_root: Path, arm_commit: str) -> None:
    """Fail closed if arm_commit is not legitimate, or a reservation/claim/
    result/world-records artifact already exists at current HEAD."""
    verify_historical_v2_execution_authority(repo_root, arm_commit)
    if _v2_protected_artifacts_present_at(repo_root, "HEAD"):
        _refuse("a V2 reservation/claim/result/world-records artifact already exists")


# =============================================================================
# Durable partial (checkpoint) world evidence store: local, untracked,
# crash-safe cache. NOT scientific authority by itself -- every cached record
# must be independently re-authenticated (recomputed and compared) against
# frozen execution before it may enter WORLD_RECORDS/RESULT. Reuses V1's own
# atomic-write primitives verbatim (generic; no V1-specific content).
# =============================================================================


class V2DurablePartialWorldStore:
    """Append-safe per-world evidence cache. Never RESULT / WORLD_RECORDS / ARM."""

    def __init__(self, path: Path, *, run_identity: str, arm_commit: str) -> None:
        self.path = Path(path)
        self.worlds_dir = self.path / "worlds"
        self.identity_path = self.path / V2_DURABLE_PARTIAL_IDENTITY_NAME
        self.run_identity = str(run_identity)
        self.arm_commit = str(arm_commit)

    @classmethod
    def open(cls, path: Path, *, run_identity: str, arm_commit: str) -> "V2DurablePartialWorldStore":
        store = cls(Path(path), run_identity=run_identity, arm_commit=arm_commit)
        store._ensure_identity()
        return store

    def _identity_payload(self) -> dict[str, Any]:
        return {
            "kind": V2_DURABLE_PARTIAL_KIND,
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
        if existing.get("kind") != V2_DURABLE_PARTIAL_KIND:
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
            raise SyntheticExecutionNotAuthorized(
                "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: durable partial store payload is torn or malformed"
            ) from exc
        if not isinstance(payload, dict):
            _refuse("durable partial store payload is malformed")
        return payload

    def _world_path(self, world_identity: str) -> Path:
        digest = _sha256_bytes(world_identity.encode("utf-8"))
        return self.worlds_dir / f"{digest}.json"

    def checkpoint_completed_world(self, record: WorldRecordV2, job: tuple[str, int, int]) -> None:
        job = (str(job[0]), int(job[1]), int(job[2]))
        owned = _worldrecord_to_dict(record)
        payload = {
            "kind": V2_DURABLE_PARTIAL_RECORD_KIND,
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

    def load_structurally_valid_cached(self) -> dict[tuple[str, int, int], WorldRecordV2]:
        """UNTRUSTED cached records. Structural checks only -- not scientific authority."""
        completed: dict[tuple[str, int, int], WorldRecordV2] = {}
        for path in sorted(self.worlds_dir.glob("*.json")):
            if path.name.endswith(".tmp"):
                continue
            payload = self._load_json(path)
            if payload.get("kind") != V2_DURABLE_PARTIAL_RECORD_KIND:
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


# =============================================================================
# WorldRecordV2 <-> plain-dict serialization (needed for durable checkpoints,
# WORLD_RECORDS, and RESULT payloads). Structural glue only -- no
# classification logic.
# =============================================================================


def _worldrecord_to_dict(record: WorldRecordV2) -> dict[str, Any]:
    return _jsonable(dataclasses.asdict(record))


def _worldrecord_from_dict(payload: Mapping[str, Any]) -> WorldRecordV2:
    candidates = {}
    for cid, crec in dict(payload.get("candidates") or {}).items():
        crec = dict(crec)
        nonident = crec.get("nonidentifiability")
        candidates[cid] = CandidateWorldRecord(
            candidate_id=crec["candidate_id"],
            state=crec["state"],
            detected=crec.get("detected"),
            nonidentifiability=(
                NonidentifiabilityRecord(**nonident) if isinstance(nonident, Mapping) else None
            ),
            gates=crec.get("gates"),
            mean_ae_improvement=crec.get("mean_ae_improvement"),
        )
    baseline_failure = payload.get("baseline_failure")
    return WorldRecordV2(
        world_id=payload["world_id"],
        scenario=payload["scenario"],
        N=payload["N"],
        world_index=payload["world_index"],
        world_state=payload["world_state"],
        L=payload.get("L"),
        selection_state=payload.get("selection_state"),
        selected_candidate=payload.get("selected_candidate"),
        taxonomy=payload.get("taxonomy"),
        candidates=candidates,
        baseline_failure=(FitInspection(**baseline_failure) if isinstance(baseline_failure, Mapping) else None),
    )


# =============================================================================
# BLOCKER 4: complete mechanical V2 aggregation. Wires the frozen fixture's
# own already-reviewed aggregation pipeline (aggregate_v2_records,
# CellAggregateV2.result_schema, evaluate_cell_coverage,
# required_coverage_for_conclusion, mechanical_conclusion_v2) onto the real
# canonical evidence. No aggregation/coverage/precedence logic is
# reimplemented here -- only orchestration over already-frozen functions.
# =============================================================================


def derive_v2_cell_aggregates(records: Sequence[WorldRecordV2]) -> dict[str, dict[str, Any]]:
    cells = aggregate_v2_records(records)
    return {f"{scenario}|{n}": cell.result_schema() for (scenario, n), cell in cells.items()}


def derive_v2_coverage_verdicts(records: Sequence[WorldRecordV2]) -> dict[str, dict[str, str]]:
    cells = aggregate_v2_records(records)
    return {f"{scenario}|{n}": evaluate_cell_coverage(cell) for (scenario, n), cell in cells.items()}


def derive_v2_baseline_coverage_verdicts(records: Sequence[WorldRecordV2]) -> dict[str, str]:
    cells = aggregate_v2_records(records)
    out: dict[str, str] = {}
    for (scenario, n), cell in cells.items():
        try:
            out[f"{scenario}|{n}"] = world_baseline_coverage_verdict(
                world_valid_count=cell.world_valid_count, planned_worlds=cell.planned_worlds
            )
        except UndefinedCoverageDenominator:
            out[f"{scenario}|{n}"] = COVERAGE_INSUFFICIENT
    return out


def derive_v2_required_coverage_status(records: Sequence[WorldRecordV2]) -> dict[str, str]:
    candidate_verdicts_by_cell = derive_v2_coverage_verdicts(records)
    baseline_verdicts_by_cell = derive_v2_baseline_coverage_verdicts(records)
    return {
        conclusion_id: required_coverage_for_conclusion(
            conclusion_id,
            candidate_verdicts_by_cell=candidate_verdicts_by_cell,
            baseline_verdicts_by_cell=baseline_verdicts_by_cell,
        )
        for conclusion_id in frozen_required_coverage_map()
    }


def derive_v2_mechanical_conclusions(
    records: Sequence[WorldRecordV2],
    *,
    structurally_complete: bool,
    inherited_detection_conclusions: Mapping[str, str],
) -> dict[str, str]:
    """Apply the frozen coverage-before-detection precedence to every one of
    the 33 required conclusions.

    ``inherited_detection_conclusions`` MUST be supplied by a separately
    frozen, independently reviewed mapping from conclusion id to the exact
    original V1-methodology verdict string for that conclusion (see
    ``KNOWN_LIMITATIONS`` in the accompanying doc: this repair unit does not
    invent that mapping from the human-readable ``inherited_claim`` prose in
    ``frozen_required_coverage_map()`` -- doing so would itself be an
    unreviewed scientific choice).
    """
    coverage_status = derive_v2_required_coverage_status(records)
    conclusions: dict[str, str] = {}
    for conclusion_id, coverage in coverage_status.items():
        if conclusion_id not in inherited_detection_conclusions:
            _refuse(f"missing inherited detection conclusion for {conclusion_id}")
        conclusions[conclusion_id] = mechanical_conclusion_v2(
            structurally_complete=structurally_complete,
            coverage_for_conclusion=coverage,
            inherited_detection_conclusion=inherited_detection_conclusions[conclusion_id],
        )
    return conclusions


# =============================================================================
# MAJOR repair: authorize once at session start; each world executes only
# through that validated session. The session is an operational optimization
# only -- mint/historical-verification below never trusts it and always
# independently re-establishes authority from git objects.
# =============================================================================


@dataclasses.dataclass(frozen=True)
class V2ProductionSession:
    repo_root: Path
    arm_commit: str
    run_identity: str
    canonical_v2_plan_sha256: str
    v2_policy_sha256: str
    opened_at: float


def open_v2_production_session(
    repo_root: Path | None = None, arm_commit: str = "HEAD"
) -> V2ProductionSession:
    repo_root = repo_root or _repo_root()
    commit = arm_commit
    if commit == "HEAD":
        commit = _git(repo_root, "rev-parse", "HEAD").decode("ascii").strip().lower()
    assert_v1_tcb_intact(repo_root, commit)
    bound = verify_historical_v2_execution_authority(repo_root, commit)
    return V2ProductionSession(
        repo_root=repo_root,
        arm_commit=bound["arm_commit"],
        run_identity=bound["run_identity"],
        canonical_v2_plan_sha256=bound["canonical_v2_plan_sha256"],
        v2_policy_sha256=bound["v2_policy_sha256"],
        opened_at=time.time(),
    )


def evaluate_v2_world_in_session(
    session: V2ProductionSession, scenario_id: str, n_rows: int, world_index: int
) -> WorldRecordV2:
    job = (str(scenario_id), int(n_rows), int(world_index))
    if job not in set(canonical_v2_production_jobs()):
        _refuse("world is not a frozen V2 canonical production-grid identity")
    world = simulate_dgp(scenario_id=scenario_id, n_rows=int(n_rows), world_index=int(world_index))
    return _production_evaluate_one_world(
        world, scenario=str(scenario_id), n_rows=int(n_rows), world_index=int(world_index)
    )


def run_canonical_v2_production_grid_in_session(
    session: V2ProductionSession, *, durable_partial: V2DurablePartialWorldStore | None = None
) -> tuple[WorldRecordV2, ...]:
    records = []
    cached = durable_partial.load_structurally_valid_cached() if durable_partial is not None else {}
    for job in canonical_v2_production_jobs():
        if job in cached:
            rec = cached[job]
        else:
            rec = evaluate_v2_world_in_session(session, *job)
            if durable_partial is not None:
                durable_partial.checkpoint_completed_world(rec, job)
        records.append(rec)
    return tuple(records)


# =============================================================================
# BLOCKER 3 / SS7: WORLD_RECORDS + RESULT mint, and historical result
# verification. Never invoked with a real ARM by this unit (none exists).
# =============================================================================


def mint_v2_world_records(
    repo_root: Path, arm_commit: str, evidence: Sequence[WorldRecordV2]
) -> dict[str, Any]:
    """Derive canonical WORLD_RECORDS. Independently authenticates every record."""
    bound = verify_historical_v2_execution_authority(repo_root, arm_commit)
    jobs = canonical_v2_production_jobs()
    if len(evidence) != len(jobs):
        _refuse_integrity("evidence set does not match canonical world count")
    session = V2ProductionSession(
        repo_root=repo_root,
        arm_commit=bound["arm_commit"],
        run_identity=bound["run_identity"],
        canonical_v2_plan_sha256=bound["canonical_v2_plan_sha256"],
        v2_policy_sha256=bound["v2_policy_sha256"],
        opened_at=time.time(),
    )
    for record, job in zip(evidence, jobs):
        recomputed = evaluate_v2_world_in_session(session, *job)
        if record != recomputed:
            _refuse_integrity("caller-supplied world record does not match frozen execution")
    serialized = [_worldrecord_to_dict(rec) for rec in evidence]
    records_bytes = canonical_json_bytes(serialized)
    return {
        "schema": V2_WORLD_RECORDS_SCHEMA,
        "schema_version": "1.0.0",
        "run_identity": bound["run_identity"],
        "arm_commit": bound["arm_commit"],
        "canonical_v2_plan_sha256": bound["canonical_v2_plan_sha256"],
        "record_count": len(serialized),
        "records": serialized,
        "records_sha256": _sha256_bytes(records_bytes),
        "records_size": len(records_bytes),
    }


def mint_v2_result(
    repo_root: Path,
    arm_commit: str,
    evidence: Sequence[WorldRecordV2],
    *,
    inherited_detection_conclusions: Mapping[str, str],
) -> dict[str, Any]:
    """Derive an authoritative V2 RESULT from full canonical evidence.

    Never called with a real ARM by this unit (none exists in the
    repository). Requires historical ARM authority independent of ambient
    HEAD, requires exactly the canonical 3200-world set, independently
    authenticates every world record, and derives aggregation/conclusion
    internally -- no caller-supplied aggregate, digest, or conclusion can
    become authority.
    """
    world_records = mint_v2_world_records(repo_root, arm_commit, evidence)
    jobs = canonical_v2_production_jobs()
    structurally_complete = len(evidence) == len(jobs)
    aggregates = derive_v2_cell_aggregates(evidence)
    conclusions = derive_v2_mechanical_conclusions(
        evidence,
        structurally_complete=structurally_complete,
        inherited_detection_conclusions=inherited_detection_conclusions,
    )
    return {
        "schema": V2_RESULT_SCHEMA,
        "schema_version": "1.0.0",
        "run_identity": world_records["run_identity"],
        "arm_commit": world_records["arm_commit"],
        "canonical_v2_plan_sha256": world_records["canonical_v2_plan_sha256"],
        "world_records_sha256": world_records["records_sha256"],
        "world_records_size": world_records["records_size"],
        "world_records_count": world_records["record_count"],
        "cell_aggregates": aggregates,
        "conclusions": conclusions,
        "v1_attempt_status": "INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM",
        "v1_3087_subset_claimable": False,
    }


def verify_historical_v2_result(
    repo_root: Path,
    arm_commit: str,
    world_records: Mapping[str, Any],
    result: Mapping[str, Any],
    *,
    inherited_detection_conclusions: Mapping[str, str],
) -> bool:
    """Recompute and compare a persisted RESULT/WORLD_RECORDS pair from scratch.

    Works from a clean clone or any later descendant checkout: authority is
    established solely via ``verify_historical_v2_execution_authority``
    (commit-parameterized, ambient-HEAD independent), and every world record
    is independently recomputed from the frozen DGP/policy, never trusted
    from the payload.
    """
    bound = verify_historical_v2_execution_authority(repo_root, arm_commit)
    if world_records.get("run_identity") != bound["run_identity"]:
        return False
    if world_records.get("canonical_v2_plan_sha256") != bound["canonical_v2_plan_sha256"]:
        return False
    serialized = world_records.get("records")
    if not isinstance(serialized, list):
        return False
    records_bytes = canonical_json_bytes(serialized)
    if world_records.get("records_sha256") != _sha256_bytes(records_bytes):
        return False
    if world_records.get("records_size") != len(records_bytes):
        return False
    jobs = canonical_v2_production_jobs()
    if len(serialized) != len(jobs):
        return False
    session = V2ProductionSession(
        repo_root=repo_root,
        arm_commit=bound["arm_commit"],
        run_identity=bound["run_identity"],
        canonical_v2_plan_sha256=bound["canonical_v2_plan_sha256"],
        v2_policy_sha256=bound["v2_policy_sha256"],
        opened_at=time.time(),
    )
    records: list[WorldRecordV2] = []
    for raw, job in zip(serialized, jobs):
        record = _worldrecord_from_dict(raw)
        recomputed = evaluate_v2_world_in_session(session, *job)
        if record != recomputed:
            return False
        records.append(record)
    if result.get("run_identity") != bound["run_identity"]:
        return False
    if result.get("world_records_sha256") != world_records["records_sha256"]:
        return False
    if result.get("world_records_count") != world_records["record_count"]:
        return False
    recomputed_aggregates = derive_v2_cell_aggregates(records)
    if not _canonical_equal_json(recomputed_aggregates, result.get("cell_aggregates")):
        return False
    structurally_complete = len(records) == len(jobs)
    recomputed_conclusions = derive_v2_mechanical_conclusions(
        records,
        structurally_complete=structurally_complete,
        inherited_detection_conclusions=inherited_detection_conclusions,
    )
    if not _canonical_equal_json(recomputed_conclusions, result.get("conclusions")):
        return False
    return True


def _canonical_equal_json(left: Any, right: Any) -> bool:
    return canonical_json_bytes(_jsonable(left)) == canonical_json_bytes(_jsonable(right))
