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

from pathlib import Path
from typing import Any, Mapping, Sequence

from scripts.research.harness_synthetic_edge_calibration_v1_lib import (
    FEATURE_IDS,
    SyntheticExecutionNotAuthorized,
    simulate_dgp,
)
from scripts.research.harness_synthetic_edge_calibration_v1_production import (
    _commit_blob,
    _git,
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
    NOT_ERA_SCOPED,
    WORLD_INVALID,
    CandidateWorldRecord,
    ChronologyLookaheadError,
    FitInspection,
    WorldRecordV2,
    _evaluate_v2_world_inner,
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


class V2ProductionNotArmed(SyntheticExecutionNotAuthorized):
    """V2 production Monte Carlo is not armed by a verified parent-authorizing ARM."""


class V2ProductionIntegrityError(SyntheticExecutionNotAuthorized):
    """V2 canonical world-set, plan, or policy identity integrity failed closed."""


def _refuse(detail: str) -> None:
    raise SyntheticExecutionNotAuthorized(f"SYNTHETIC_EXECUTION_NOT_AUTHORIZED: {detail}")


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


def mint_v2_result(
    evidence: Sequence[WorldRecordV2], *args: Any, **kwargs: Any
) -> dict[str, Any]:
    """Derive an authoritative V2 RESULT from full canonical evidence. Not reachable.

    Never called by this unit. Requires ARM authorization (always False here)
    and requires every supplied record to be recomputed and match exactly --
    no caller-supplied aggregate or world record can become scientific
    authority.
    """
    if args or kwargs:
        _refuse("caller arguments cannot authorize RESULT minting")
    repo_root = _repo_root()
    if v2_production_arm_authorized(repo_root) is not True:
        raise V2ProductionNotArmed(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: v2_production_arm_authorized=false"
        )
    jobs = canonical_v2_production_jobs()
    if len(evidence) != len(jobs):
        _refuse("evidence set does not match canonical world count")
    for record, job in zip(evidence, jobs):
        recomputed = evaluate_v2_production_world(*job)
        if record != recomputed:
            _refuse("caller-supplied world record does not match frozen execution")
    _refuse("RESULT minting is not implemented in this unit")
