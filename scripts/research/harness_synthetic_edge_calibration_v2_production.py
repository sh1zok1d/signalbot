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
import sys
import time
import weakref
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
    COVERAGE_ADEQUATE,
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
from scripts.research.harness_synthetic_edge_calibration_v2_inherited_ladder import (
    AMENDMENT_003_JSON_REL,
    AMENDMENT_003_MD_REL,
    AMENDMENT_004_JSON_REL,
    AMENDMENT_004_MD_REL,
    FINAL_OVERALL_ID,
    FROZEN_AMENDMENT_003_SHA256,
    FROZEN_AMENDMENT_004_SHA256,
    V2InheritedLadderAuthorityError,
    V2VisibilityStatisticUnavailable,
    assert_v2_inherited_ladder_authority_intact,
    derive_all_v2_inherited_conclusions,
    derive_v2_final_overall_mechanical_conclusion,
    derive_v2_inherited_conclusions_needed,
    frozen_final_overall_terminal_labels,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

# --- Execution-authoritative source paths ------------------------------------

V2_POLICY_REL = "scripts/research/harness_synthetic_edge_calibration_v2_rank_policy.py"
V2_INHERITED_LADDER_REL = (
    "scripts/research/harness_synthetic_edge_calibration_v2_inherited_ladder.py"
)
V2_PRODUCTION_REL = (
    "scripts/research/harness_synthetic_edge_calibration_v2_production.py"
)
V2_POLICY_FREEZE_ARTIFACT_REL = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_IMPLEMENTATION_FREEZE.json"
)
# Stable path every future V2 execution freeze commits its artifact to. This
# path (and the schema string below) is the ONLY freeze-identifying constant
# this module hardcodes: the freeze commit's own SHA is NEVER hardcoded here
# (see AUTHORITY SELF-REFERENCE DESIGN below), so a new freeze requires no
# edit to this file. Historical freeze documents that used a different path
# (e.g. the 614295d- and c1d6acc-era freezes) remain valid historical
# evidence; they are simply not consulted by this runtime, which only ever
# looks for a freeze at this stable path.
CANONICAL_V2_EXECUTION_FREEZE_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_EXECUTION_FREEZE.json"
)
V2_EXECUTION_FREEZE_SCHEMA = "harness_synthetic_edge_calibration_v2_execution_freeze"

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

# Historical V2 rank-policy fixture identity. Not sufficient execution ARM
# authority. Kept as a named historical dependency of the 33/33 freeze.
FROZEN_V2_POLICY_REVIEWED_IMPLEMENTATION_HEAD = (
    "a310837bab4ee60c7495cca3bdb476abdc58a041"
)
FROZEN_V2_POLICY_REVIEWED_IMPLEMENTATION_TREE = (
    "b15c4102b01514ff73e1728aec072eda9b528815"
)
FROZEN_V2_POLICY_FREEZE_HEAD = "f96197d109fc22c12e4c8ba19715d67c65187c0e"
FROZEN_V2_POLICY_FREEZE_TREE = "ec169d8bd73896308ce4dcf1d5d5fd218cd55bd5"
FROZEN_ORIGINAL_PREREG_HEAD = "ada237edc330b44bc412332e263f124757919e93"
FROZEN_ORIGINAL_PREREG_TREE = "ba1c0873879b7ea8556c3e238f8b962b91da6dc2"
FROZEN_AMENDMENT_001_HEAD = "d8f0a996bc4341d0cbe01a1a061130b889ed5e75"
FROZEN_AMENDMENT_001_TREE = "09dca9b1240a43d5de9de0dadf32d27e00e7eaea"

# NOTE: no FROZEN_V2_33_33_FREEZE_* / FROZEN_V2_33_33_IMPLEMENTATION_* SHA
# constants exist here. Earlier revisions of this module hardcoded a specific
# freeze commit and a specific implementation commit as execution authority.
# Because this file (V2_PRODUCTION_REL) is itself one of the two
# execution-authoritative implementation sources any freeze must byte-bind,
# hardcoding a freeze's SHA inside this file made every freeze self-defeating
# the moment it needed to bind THIS file's own (necessarily new) bytes:
# editing the constant changed the file, which invalidated the freeze that
# was just made, which required another freeze, which required another edit.
# See AUTHORITY SELF-REFERENCE DESIGN below: the freeze commit F is always
# derived structurally as the immediate parent of the ARM commit under
# evaluation, and the implementation commit I is always derived structurally
# as F's own immediate parent -- never hardcoded, never caller-selected.
#
# The stable, never-changing scientific/historical anchors below ARE safe to
# hardcode: none of them are this file's own bytes, so none of them create
# the cycle above.
FROZEN_CANONICAL_V2_PLAN_SHA256 = (
    "7fa12fd3b939cd210a69da37659fd1013a1dba43aca4c06abb6f5a6442a33800"
)
FROZEN_CANONICAL_WORLD_COUNT = 3200

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
    "amendment_002_status": "REJECTED_HISTORICAL_AUTHORITY",
    "amendment_002_governs_executable_science": False,
}

V2_ARM_REQUIRED_BINDING_KEYS = (
    "freeze_parent_head",
    "freeze_parent_tree",
    "freeze_artifact_path",
    "freeze_artifact_sha256",
    "freeze_artifact_size",
    "reviewed_implementation_head",
    "reviewed_implementation_tree",
    "v2_policy_sha256",
    "v2_policy_size",
    "canonical_v2_plan_sha256",
    "canonical_world_count",
    "original_prereg_head",
    "original_prereg_tree",
    "amendment_001_head",
    "amendment_001_tree",
    "amendment_003_md_sha256",
    "amendment_003_json_sha256",
    "amendment_004_md_sha256",
    "amendment_004_json_sha256",
)

V2_ARM_ALLOWED_KEYS = frozenset(V2_ARM_REQUIRED_LITERALS) | frozenset(
    V2_ARM_REQUIRED_BINDING_KEYS
)

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


# =============================================================================
# AUTHORITY SELF-REFERENCE DESIGN
#
# Target topology:  IMPLEMENTATION I -> FREEZE F -> ARM A -> SESSION
#
# Given ARM commit A, F is ALWAYS derived structurally as A's own immediate
# parent, and I is ALWAYS derived structurally as F's own immediate parent.
# Neither F's nor I's identity is ever hardcoded in this file or accepted
# from a caller: this file is itself one of the two execution-authoritative
# implementation sources any freeze must byte-bind, so hardcoding a specific
# F (or I) here would mean every new freeze invalidates itself the moment it
# needs to bind this file's own necessarily-changed bytes. See
# ``_authenticate_v2_execution_freeze`` for the structural, non-self-attested
# validation that makes a caller-selected/forged F impossible to pass.
# =============================================================================


def _commit_parent_count(repo_root: Path, commit: str) -> int:
    """Number of parents ``commit`` has (0 for a root commit, 2+ for a merge)."""
    raw = _git(repo_root, "cat-file", "-p", commit)
    return sum(
        1 for line in raw.decode("utf-8", "replace").splitlines() if line.startswith("parent ")
    )


def _authenticate_v2_execution_freeze(
    repo_root: Path, freeze_commit: str
) -> dict[str, Any] | None:
    """Structurally authenticate ``freeze_commit`` as a valid V2 execution freeze.

    ``freeze_commit``'s identity is never hardcoded or caller-trusted:
    callers derive it as the exact immediate parent of the ARM commit under
    evaluation. This proves, entirely from immutable git objects reachable
    from that one commit, that it legitimately freezes its own immediate
    parent as the approved V2 execution runtime. The freeze document's
    *content* is never trusted merely for being internally self-consistent:
    the two execution-authoritative implementation blobs are independently
    re-read and re-hashed at the freeze's structural parent.

    Returns the authenticated freeze payload, or ``None`` for any failure --
    this never raises; callers translate ``None`` into refusal.
    """
    if not _commit_exists(repo_root, freeze_commit):
        return None
    if _commit_parent_count(repo_root, freeze_commit) != 1:
        return None
    implementation_head = _parent_sha_of(repo_root, freeze_commit)
    if implementation_head is None or not _commit_exists(repo_root, implementation_head):
        return None
    implementation_tree = (
        _git(repo_root, "rev-parse", f"{implementation_head}^{{tree}}")
        .decode("ascii").strip().lower()
    )

    freeze = _load_commit_json(repo_root, freeze_commit, CANONICAL_V2_EXECUTION_FREEZE_PATH)
    if freeze is None:
        return None
    if freeze.get("schema") != V2_EXECUTION_FREEZE_SCHEMA:
        return None

    reviewed = freeze.get("reviewed_implementation")
    if not isinstance(reviewed, Mapping):
        return None
    if reviewed.get("head") != implementation_head:
        return None
    if reviewed.get("tree") != implementation_tree:
        return None

    # The two execution-authoritative implementation files: re-read and
    # re-hash at `implementation_head` from git objects, never trusted from
    # the freeze document's own self-report.
    sources = freeze.get("execution_authoritative_implementation_sources")
    if not isinstance(sources, list):
        return None
    by_path: dict[str, Mapping[str, Any]] = {}
    for entry in sources:
        if not isinstance(entry, Mapping):
            return None
        path = entry.get("path")
        if path not in (V2_INHERITED_LADDER_REL, V2_PRODUCTION_REL):
            continue
        by_path[path] = entry
    if set(by_path) != {V2_INHERITED_LADDER_REL, V2_PRODUCTION_REL}:
        return None
    for path, entry in by_path.items():
        real_blob = _commit_blob(repo_root, implementation_head, path)
        if real_blob is None:
            return None
        if entry.get("sha256") != _sha256_bytes(real_blob):
            return None
        if entry.get("size_bytes") != len(real_blob):
            return None
        real_blob_id = (
            _git(repo_root, "rev-parse", f"{implementation_head}:{path}")
            .decode("ascii").strip().lower()
        )
        if str(entry.get("git_blob") or "").strip().lower() != real_blob_id:
            return None

    # Scientific/historical authority chain. These identities never change
    # across freeze generations -- they are not this file's own bytes -- so
    # comparing against the stable hardcoded constants is not circular.
    method = freeze.get("methodology_authority")
    if not isinstance(method, Mapping):
        return None
    for label, expected_head, expected_tree in (
        ("original_prereg", FROZEN_ORIGINAL_PREREG_HEAD, FROZEN_ORIGINAL_PREREG_TREE),
        ("amendment_001", FROZEN_AMENDMENT_001_HEAD, FROZEN_AMENDMENT_001_TREE),
    ):
        entry = method.get(label)
        if not isinstance(entry, Mapping):
            return None
        if entry.get("head") != expected_head or entry.get("tree") != expected_tree:
            return None

    a002 = method.get("amendment_002")
    if not isinstance(a002, Mapping):
        return None
    if a002.get("status") != "REJECTED_HISTORICAL_AUTHORITY":
        return None
    if a002.get("governs_executable_science") is not False:
        return None

    a003 = method.get("amendment_003")
    if not isinstance(a003, Mapping):
        return None
    if a003.get("governs_executable_science") is not True:
        return None

    a004 = method.get("amendment_004")
    if not isinstance(a004, Mapping):
        return None
    if a004.get("governs_executable_science") is not True:
        return None
    if a004.get("amends") != "AMENDMENT_003":
        return None

    # Rank-policy authority: also a stable, never-changing historical
    # dependency of every V2 execution freeze.
    policy = freeze.get("v2_rank_policy_authority")
    if not isinstance(policy, Mapping):
        return None
    if policy.get("reviewed_implementation_head") != FROZEN_V2_POLICY_REVIEWED_IMPLEMENTATION_HEAD:
        return None
    if policy.get("reviewed_implementation_tree") != FROZEN_V2_POLICY_REVIEWED_IMPLEMENTATION_TREE:
        return None
    if policy.get("freeze_head") != FROZEN_V2_POLICY_FREEZE_HEAD:
        return None
    if policy.get("freeze_tree") != FROZEN_V2_POLICY_FREEZE_TREE:
        return None

    # Canonical plan / world count: recomputed live at the freeze commit
    # from the frozen V1 grid + V2 policy source (never from the freeze
    # document's self-report), and cross-checked against the freeze's own
    # declared values and the stable, never-changing constants.
    plan_entry = freeze.get("canonical_v2_plan")
    if not isinstance(plan_entry, Mapping):
        return None
    if plan_entry.get("sha256") != FROZEN_CANONICAL_V2_PLAN_SHA256:
        return None
    if plan_entry.get("world_count") != FROZEN_CANONICAL_WORLD_COUNT:
        return None
    live_plan = canonical_v2_plan(repo_root, freeze_commit)
    if live_plan["sha256"] != FROZEN_CANONICAL_V2_PLAN_SHA256:
        return None

    # Visibility limitation must remain fail-closed; a freeze may not claim
    # to have resolved it.
    visibility = freeze.get("visibility_limitation")
    if not isinstance(visibility, Mapping):
        return None
    if visibility.get("status") != "UNRESOLVED_FAIL_CLOSED":
        return None

    # A freeze must not itself claim execution/result authority.
    state = freeze.get("production_state")
    if isinstance(state, Mapping):
        for key in (
            "production_armed",
            "production_executed",
            "result_minted",
            "world_records_created",
            "authority_consumed",
            "arm_created",
            "execution_authorized",
            "canonical_3200_run_started",
        ):
            if key in state and state.get(key) is not False:
                return None

    # A freeze commit must not itself carry an ARM or protected artifacts.
    if _commit_blob(repo_root, freeze_commit, CANONICAL_V2_ARM_PATH) is not None:
        return None
    if _v2_protected_artifacts_present_at(repo_root, freeze_commit):
        return None

    return freeze


def _implementation_bytes_match_freeze(
    repo_root: Path, commit: str, freeze: Mapping[str, Any], implementation_head: str
) -> bool:
    """ARM-commit blobs must equal the authenticated freeze's implementation."""
    sources = freeze.get("execution_authoritative_implementation_sources")
    if not isinstance(sources, list):
        return False
    by_path = {}
    for entry in sources:
        if not isinstance(entry, Mapping):
            return False
        path = entry.get("path")
        if path not in (V2_INHERITED_LADDER_REL, V2_PRODUCTION_REL):
            continue
        by_path[path] = entry
    if set(by_path) != {V2_INHERITED_LADDER_REL, V2_PRODUCTION_REL}:
        return False
    for path, entry in by_path.items():
        arm_blob = _commit_blob(repo_root, commit, path)
        impl_blob = _commit_blob(repo_root, implementation_head, path)
        if arm_blob is None or impl_blob is None:
            return False
        if arm_blob != impl_blob:
            return False
        if _sha256_bytes(arm_blob) != entry.get("sha256"):
            return False
        if len(arm_blob) != entry.get("size_bytes"):
            return False
        arm_blob_id = (
            _git(repo_root, "rev-parse", f"{commit}:{path}").decode("ascii").strip().lower()
        )
        recorded_blob_id = str(entry.get("git_blob") or "").strip().lower()
        if arm_blob_id != recorded_blob_id:
            return False
    return True


def _payload_field_equals(payload: Mapping[str, Any], key: str, expected: Any) -> bool:
    """Exact required-field match. Booleans are not interchangeable with 0/1."""
    if key not in payload:
        return False
    actual = payload[key]
    if isinstance(expected, bool) or isinstance(actual, bool):
        return actual is expected
    if isinstance(expected, int) or isinstance(actual, int):
        return type(actual) is type(expected) and actual == expected
    return actual == expected


def required_v2_arm_binding_fields(repo_root: Path, freeze_commit: str) -> dict[str, Any]:
    """Derive ARM binding fields from an already-authenticated execution freeze.

    ``freeze_commit`` is caller-derived (the ARM's own structural parent),
    never a module-level constant.
    """
    freeze = _authenticate_v2_execution_freeze(repo_root, freeze_commit)
    if freeze is None:
        _refuse("candidate freeze commit does not authenticate as a valid V2 execution freeze")
    implementation_head = _parent_sha_of(repo_root, freeze_commit)
    implementation_tree = (
        _git(repo_root, "rev-parse", f"{implementation_head}^{{tree}}")
        .decode("ascii").strip().lower()
    )
    freeze_tree = (
        _git(repo_root, "rev-parse", f"{freeze_commit}^{{tree}}").decode("ascii").strip().lower()
    )
    freeze_blob = _commit_blob(repo_root, freeze_commit, CANONICAL_V2_EXECUTION_FREEZE_PATH)
    if freeze_blob is None:
        _refuse("authenticated freeze artifact vanished between checks")
    policy_sha256, policy_size = _v2_policy_digest_at(repo_root, freeze_commit)
    plan = canonical_v2_plan(repo_root, freeze_commit)
    if plan["sha256"] != FROZEN_CANONICAL_V2_PLAN_SHA256:
        _refuse("canonical V2 plan identity drifted from the authenticated freeze")
    return {
        "freeze_parent_head": freeze_commit,
        "freeze_parent_tree": freeze_tree,
        "freeze_artifact_path": CANONICAL_V2_EXECUTION_FREEZE_PATH,
        "freeze_artifact_sha256": _sha256_bytes(freeze_blob),
        "freeze_artifact_size": len(freeze_blob),
        "reviewed_implementation_head": implementation_head,
        "reviewed_implementation_tree": implementation_tree,
        "v2_policy_sha256": policy_sha256,
        "v2_policy_size": policy_size,
        "canonical_v2_plan_sha256": FROZEN_CANONICAL_V2_PLAN_SHA256,
        "canonical_world_count": FROZEN_CANONICAL_WORLD_COUNT,
        "original_prereg_head": FROZEN_ORIGINAL_PREREG_HEAD,
        "original_prereg_tree": FROZEN_ORIGINAL_PREREG_TREE,
        "amendment_001_head": FROZEN_AMENDMENT_001_HEAD,
        "amendment_001_tree": FROZEN_AMENDMENT_001_TREE,
        "amendment_003_md_sha256": FROZEN_AMENDMENT_003_SHA256[AMENDMENT_003_MD_REL],
        "amendment_003_json_sha256": FROZEN_AMENDMENT_003_SHA256[AMENDMENT_003_JSON_REL],
        "amendment_004_md_sha256": FROZEN_AMENDMENT_004_SHA256[AMENDMENT_004_MD_REL],
        "amendment_004_json_sha256": FROZEN_AMENDMENT_004_SHA256[AMENDMENT_004_JSON_REL],
    }


def _loaded_runtime_bytes() -> dict[str, bytes]:
    """Bytes of the production modules this process is actually executing."""
    ladder_mod = sys.modules[
        "scripts.research.harness_synthetic_edge_calibration_v2_inherited_ladder"
    ]
    return {
        V2_PRODUCTION_REL: Path(__file__).read_bytes(),
        V2_INHERITED_LADDER_REL: Path(ladder_mod.__file__).read_bytes(),
    }


def _assert_executed_runtime_bound_to_commit(repo_root: Path, commit: str) -> None:
    """Refuse live execution if imported modules differ from authorized git blobs.

    ``repo_root`` is only the git object store for the authorized commit.
    The executing files are this process's imported modules. A caller-supplied
    repo_root that differs from the live checkout is not a skip: imported
    bytes are still compared to the authorized blobs. Mismatch refuses.
    """
    loaded = _loaded_runtime_bytes()
    for rel, bytes_ in loaded.items():
        blob = _commit_blob(repo_root, commit, rel)
        if blob is None or blob != bytes_:
            _refuse(
                "loaded runtime bytes do not match authorized git objects at "
                f"{commit}:{rel}"
            )


def _v2_arm_payload_authorizes_at_commit(
    repo_root: Path, commit: str, payload: Mapping[str, Any]
) -> bool:
    """Verify an ARM payload against tracked git objects at ``commit``.

    The trusted execution freeze is structurally derived as this ARM
    commit's own immediate parent, then independently authenticated from
    git objects (``_authenticate_v2_execution_freeze``) -- never hardcoded,
    never caller-selected. Payload fields must match that authenticated
    freeze; they are not themselves authority. The older rank-policy freeze
    artifact is not sufficient execution authority.
    """
    if not isinstance(payload, Mapping):
        return False
    if set(payload) != V2_ARM_ALLOWED_KEYS:
        return False
    for key, expected in V2_ARM_REQUIRED_LITERALS.items():
        if not _payload_field_equals(payload, key, expected):
            return False

    if _commit_parent_count(repo_root, commit) != 1:
        return False
    parent = _parent_sha_of(repo_root, commit)
    if parent is None:
        return False

    freeze = _authenticate_v2_execution_freeze(repo_root, parent)
    if freeze is None:
        return False
    implementation_head = _parent_sha_of(repo_root, parent)
    if implementation_head is None:
        return False

    try:
        expected_bindings = required_v2_arm_binding_fields(repo_root, parent)
    except SyntheticExecutionNotAuthorized:
        return False
    for key, expected in expected_bindings.items():
        if not _payload_field_equals(payload, key, expected):
            return False

    if not _implementation_bytes_match_freeze(repo_root, commit, freeze, implementation_head):
        return False

    policy_sha256, policy_size = _v2_policy_digest_at(repo_root, commit)
    if payload["v2_policy_sha256"] != policy_sha256:
        return False
    if payload["v2_policy_size"] != policy_size:
        return False

    tcb = v1_tcb_digests_at(repo_root, commit)
    for role, expected in FROZEN_V1_TCB_SHA256.items():
        if tcb.get(role) != expected:
            return False

    plan = canonical_v2_plan(repo_root, commit)
    if plan["sha256"] != FROZEN_CANONICAL_V2_PLAN_SHA256:
        return False
    if payload["canonical_v2_plan_sha256"] != FROZEN_CANONICAL_V2_PLAN_SHA256:
        return False
    if payload["canonical_world_count"] != FROZEN_CANONICAL_WORLD_COUNT:
        return False
    if plan["payload"]["v1_planned_worlds"] != FROZEN_CANONICAL_WORLD_COUNT:
        return False
    if len(planned_production_jobs()) != FROZEN_CANONICAL_WORLD_COUNT:
        return False

    try:
        assert_v2_inherited_ladder_authority_intact(repo_root, commit)
    except (V2InheritedLadderAuthorityError, SyntheticExecutionNotAuthorized):
        return False

    if _v2_protected_artifacts_present_at(repo_root, commit):
        return False
    return True


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
    """Evaluate one frozen-grid world under the frozen V2 policy. Refuses unless armed.

    Pre-existing technical debt (unchanged from the 33/33 freeze HEAD): this
    direct entrypoint does not require a committed reservation. Session
    entrypoints do. This unit does not redesign that lifecycle split.
    """
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
    _assert_executed_runtime_bound_to_commit(repo_root, "HEAD")
    world = simulate_dgp(scenario_id=str(scenario_id), n_rows=int(n_rows), world_index=int(world_index))
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
    _assert_executed_runtime_bound_to_commit(repo_root, "HEAD")
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


def establish_v2_durable_reservation(repo_root: Path, arm_commit: str) -> str:
    """Durably commit a reservation as a new commit on top of current HEAD.

    Required ordering, enforced by construction: this function verifies ARM
    authority and plan/policy/TCB (via ``assert_v2_reservation_available`` ->
    ``verify_historical_v2_execution_authority``), THEN establishes the
    durable reservation. ``open_v2_production_session`` refuses unless this
    has already run and its result is committed -- scientific execution is
    therefore impossible before a durable reservation exists.

    Guarantee level (stated precisely, not oversold): within one shared git
    repository/checkout, this is airtight -- ``assert_v2_reservation_available``
    is re-verified immediately before writing, and git's own commit/ref
    locking (a second concurrent ``git commit`` in the same repository either
    waits or fails outright) means only one reservation can ever land as
    HEAD's own next commit; a losing concurrent caller's git operation fails
    and is converted to a clean refusal here, before either process could
    have proceeded to open a session. Across independent, not-yet-synchronized
    clones (no shared filesystem, communication only via eventual git
    push/fetch), this repository-local check cannot detect a concurrent
    reservation attempt in a *different* clone before both begin scientific
    computation -- that residual race requires operational discipline (a
    single authoritative execution host or clone, or an external distributed
    lock/CI concurrency guard) beyond what git commits alone can provide.
    Even in that scenario, only one reservation/evidence/RESULT chain can
    ever become part of the single shared canonical remote history (the
    other's push is rejected as non-fast-forward and must not be force-pushed
    or auto-rebased-and-retried) -- wasted duplicate computation is possible,
    a duplicate *authoritative* RESULT is not.
    """
    repo_root = Path(repo_root)
    assert_v2_reservation_available(repo_root, arm_commit)
    status = _git(repo_root, "status", "--porcelain", "--untracked-files=all").decode(
        "utf-8", "surrogateescape"
    )
    if status.strip():
        _refuse("worktree is not clean before establishing a durable reservation")
    reservation = v2_durable_reservation_document(repo_root, arm_commit)
    reservation_path = repo_root / CANONICAL_V2_RESERVATION_PATH
    _atomic_replace_bytes(reservation_path, canonical_json_bytes(reservation))
    _git(repo_root, "add", "--", CANONICAL_V2_RESERVATION_PATH)
    _git(repo_root, "commit", "-m", "v2 production reservation")
    head = _git(repo_root, "rev-parse", "HEAD").decode("ascii").strip().lower()
    committed = _load_commit_json(repo_root, head, CANONICAL_V2_RESERVATION_PATH)
    if committed != reservation:
        _refuse_integrity("committed reservation does not match the established reservation identity")
    return head


def _verify_v2_reservation_committed(
    repo_root: Path, arm_commit: str, bound: Mapping[str, Any]
) -> dict[str, Any]:
    """Refuse unless a durable reservation matching ``bound`` is tracked at HEAD."""
    reservation = _load_commit_json(repo_root, "HEAD", CANONICAL_V2_RESERVATION_PATH)
    if reservation is None:
        _refuse(
            "no durable V2 production reservation is committed at HEAD; "
            "call establish_v2_durable_reservation before opening a session"
        )
    if reservation.get("run_identity") != bound["run_identity"]:
        _refuse("committed reservation does not match this ARM's run identity")
    if reservation.get("arm_commit") != bound["arm_commit"]:
        _refuse("committed reservation does not match this ARM commit")
    if reservation.get("canonical_v2_plan_sha256") != bound["canonical_v2_plan_sha256"]:
        _refuse("committed reservation does not match the canonical V2 plan")
    if reservation.get("v2_policy_sha256") != bound["v2_policy_sha256"]:
        _refuse("committed reservation does not match the frozen V2 policy")
    if reservation.get("authorization_consumed") is not False:
        _refuse("committed reservation authorization is already consumed")
    return reservation


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
) -> dict[str, str]:
    """Apply the frozen coverage-before-detection precedence to every one of
    the 33 required conclusions.

    The inherited detection conclusion for every id is now derived
    INTERNALLY from authenticated evidence via the approved 33/33 methodology
    binding (``AMENDMENT_003`` + ``AMENDMENT_004``,
    GO_FOR_33_33_IMPLEMENTATION_BINDING, BLOCKERS=0/MAJORS=0). There is no
    caller-supplied scientific mapping, override, callback, strategy object,
    or environment-variable input of any kind: this function's only inputs
    are the evidence records themselves and frozen, hash-pinned repository
    authority. Raises ``V2VisibilityStatisticUnavailable`` if the evidence
    would require deriving one of the 5 conclusion ids that the frozen V2
    policy fixture cannot currently supply an input for (see that
    exception's docstring in
    ``harness_synthetic_edge_calibration_v2_inherited_ladder`` --
    IMPLEMENTATION_REQUIRES_NEW_SCIENTIFIC_CHOICE = YES, not a defect here).
    """
    coverage_status = derive_v2_required_coverage_status(records)
    # Only request a raw inherited value for ids whose coverage is ADEQUATE:
    # frozen mechanical_conclusion_v2 never reads the inherited value when
    # coverage is INSUFFICIENT (it returns MECHANICAL_INSUFFICIENT_IDENTIFIABILITY
    # first), so a coverage-inadequate run must not be masked by an unrelated
    # visibility-statistic refusal for an id that was never going to be
    # consulted anyway.
    needed = [
        cid
        for cid, coverage in coverage_status.items()
        if structurally_complete
        and coverage == COVERAGE_ADEQUATE
        and cid != FINAL_OVERALL_ID
    ]
    inherited = derive_v2_inherited_conclusions_needed(
        records, needed, structurally_complete=structurally_complete
    )
    conclusions: dict[str, str] = {}
    for conclusion_id, coverage in coverage_status.items():
        if conclusion_id == FINAL_OVERALL_ID:
            continue
        if structurally_complete and coverage == COVERAGE_ADEQUATE:
            if conclusion_id not in inherited:
                _refuse(f"ADEQUATE conclusion {conclusion_id} missing derived value")
            inherited_value = inherited[conclusion_id]
            if inherited_value is None:
                _refuse(f"ADEQUATE conclusion {conclusion_id} derived None")
            if not isinstance(inherited_value, str) or inherited_value == "":
                _refuse(
                    f"ADEQUATE conclusion {conclusion_id} derived invalid value {inherited_value!r}"
                )
        else:
            inherited_value = "NOT_CLAIMABLE"
        conclusions[conclusion_id] = mechanical_conclusion_v2(
            structurally_complete=structurally_complete,
            coverage_for_conclusion=coverage,
            inherited_detection_conclusion=inherited_value,
        )
    conclusions[FINAL_OVERALL_ID] = derive_v2_final_overall_mechanical_conclusion(
        records, structurally_complete=structurally_complete
    )
    final_label = conclusions[FINAL_OVERALL_ID]
    if final_label is None or final_label == "":
        _refuse("canonical FINAL_OVERALL produced None/empty")
    allowed = frozen_final_overall_terminal_labels()
    if final_label not in allowed:
        _refuse(f"canonical FINAL_OVERALL produced unknown label {final_label!r}")
    return conclusions


# =============================================================================
# MAJOR repair: authorize once at session start; each world executes only
# through that validated session. The session is an operational optimization
# only -- mint/historical-verification below never trusts it and always
# independently re-establishes authority from git objects.
#
# GENUINE-SESSION HARDENING: a session is authorization *evidence*, not a
# caller-visible bearer token. ``eq=False`` makes session identity fall back
# to plain object identity (``id()``) instead of dataclass structural
# equality, so a copied/reconstructed object with identical field values is
# NOT the same session. ``_SESSION_REGISTRY`` is a module-private
# WeakKeyDictionary keyed by that identity, populated ONLY by
# ``open_v2_production_session``/the internal mint helper below, storing a
# snapshot of the fields as issued. ``_require_genuine_session`` rejects
# anything that (a) is not literally the object the registry knows about, or
# (b) has been mutated (including via ``object.__setattr__`` bypassing
# ``frozen=True``) since issuance. This defends against callers who do not go
# through the intended API; it does not (and cannot, in pure Python) defend
# against an adversary with arbitrary code execution in the same interpreter,
# who could reach into the registry directly -- that matches Python's actual
# security ceiling and is not a gap specific to this design.
# =============================================================================

_SESSION_REGISTRY: "weakref.WeakKeyDictionary[Any, dict[str, Any]]" = weakref.WeakKeyDictionary()


@dataclasses.dataclass(frozen=True, eq=False)
class V2ProductionSession:
    repo_root: Path
    arm_commit: str
    run_identity: str
    canonical_v2_plan_sha256: str
    v2_policy_sha256: str
    opened_at: float


def _snapshot_session_fields(session: "V2ProductionSession") -> dict[str, Any]:
    return {
        "arm_commit": session.arm_commit,
        "run_identity": session.run_identity,
        "canonical_v2_plan_sha256": session.canonical_v2_plan_sha256,
        "v2_policy_sha256": session.v2_policy_sha256,
    }


def _issue_v2_production_session(repo_root: Path, bound: Mapping[str, Any]) -> V2ProductionSession:
    """Construct AND register a session. The only way a session ever becomes
    genuine: every legitimate entrypoint (open_v2_production_session, and the
    internal mint/historical-verification helpers) must go through this."""
    session = V2ProductionSession(
        repo_root=repo_root,
        arm_commit=bound["arm_commit"],
        run_identity=bound["run_identity"],
        canonical_v2_plan_sha256=bound["canonical_v2_plan_sha256"],
        v2_policy_sha256=bound["v2_policy_sha256"],
        opened_at=time.time(),
    )
    _SESSION_REGISTRY[session] = _snapshot_session_fields(session)
    return session


def _require_genuine_session(session: Any) -> V2ProductionSession:
    if not isinstance(session, V2ProductionSession):
        _refuse("not a genuine V2 production session")
    snapshot = _SESSION_REGISTRY.get(session)
    if snapshot is None:
        _refuse("session was not issued by open_v2_production_session")
    if _snapshot_session_fields(session) != snapshot:
        _refuse("session fields were tampered with after issuance")
    _assert_executed_runtime_bound_to_commit(session.repo_root, session.arm_commit)
    return session


def open_v2_production_session(
    repo_root: Path | None = None, arm_commit: str = "HEAD"
) -> V2ProductionSession:
    """Authorize once: verify TCB, historical ARM authority, AND that a
    durable reservation is already committed at HEAD, in that order, before
    any scientific computation is possible through the returned session.

    ``arm_commit="HEAD"`` is only valid before a reservation has been
    committed on top of the ARM (i.e. HEAD is still literally the ARM
    commit). Once ``establish_v2_durable_reservation`` has committed a
    reservation as a child of the ARM, HEAD is the reservation commit, not
    the ARM commit, and the caller must pass the ARM commit hash explicitly.
    """
    repo_root = repo_root or _repo_root()
    commit = arm_commit
    if commit == "HEAD":
        commit = _git(repo_root, "rev-parse", "HEAD").decode("ascii").strip().lower()
    assert_v1_tcb_intact(repo_root, commit)
    bound = verify_historical_v2_execution_authority(repo_root, commit)
    _assert_executed_runtime_bound_to_commit(repo_root, bound["arm_commit"])
    _verify_v2_reservation_committed(repo_root, commit, bound)
    return _issue_v2_production_session(repo_root, bound)


def evaluate_v2_world_in_session(
    session: V2ProductionSession, scenario_id: str, n_rows: int, world_index: int
) -> WorldRecordV2:
    session = _require_genuine_session(session)
    _assert_executed_runtime_bound_to_commit(session.repo_root, session.arm_commit)
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
    session = _require_genuine_session(session)
    _assert_executed_runtime_bound_to_commit(session.repo_root, session.arm_commit)
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
    # Mint never trusts a caller-supplied session: it independently
    # re-establishes authority above and issues its own internal session
    # (registered like any other) purely to reuse the same per-world
    # evaluation code path.
    session = _issue_v2_production_session(repo_root, bound)
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
) -> dict[str, Any]:
    """Derive an authoritative V2 RESULT from full canonical evidence.

    Never called with a real ARM by this unit (none exists in the
    repository). Requires historical ARM authority independent of ambient
    HEAD, requires exactly the canonical 3200-world set, independently
    authenticates every world record, and derives aggregation/conclusion/final
    conclusion internally -- no caller-supplied aggregate, digest, mapping,
    or conclusion of any kind can become authority. Same evidence + same
    frozen authority always yields the same conclusions bytes.
    """
    world_records = mint_v2_world_records(repo_root, arm_commit, evidence)
    jobs = canonical_v2_production_jobs()
    structurally_complete = len(evidence) == len(jobs)
    aggregates = derive_v2_cell_aggregates(evidence)
    conclusions = derive_v2_mechanical_conclusions(
        evidence, structurally_complete=structurally_complete
    )
    final_overall = conclusions[FINAL_OVERALL_ID]
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
        "final_overall_conclusion": final_overall,
        "v1_attempt_status": "INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM",
        "v1_3087_subset_claimable": False,
    }


def verify_historical_v2_result(
    repo_root: Path,
    arm_commit: str,
    world_records: Mapping[str, Any],
    result: Mapping[str, Any],
) -> bool:
    """Recompute and compare a persisted RESULT/WORLD_RECORDS pair from scratch.

    Works from a clean clone or any later descendant checkout: authority is
    established solely via ``verify_historical_v2_execution_authority``
    (commit-parameterized, ambient-HEAD independent), and every world record
    -- and every one of the 33 conclusions, and the final overall conclusion
    -- is independently RECOMPUTED from the frozen DGP/policy/ladder, never
    trusted from the payload. There is no caller-supplied scientific mapping
    parameter: a stored conclusion can only verify by matching what this
    function derives fresh from evidence + frozen authority. Mutating any one
    of the 33 stored conclusion values, or the stored final conclusion,
    causes this to return False even if every ordinary payload hash the
    caller could recompute (world-records digest, evidence bytes) is left
    untouched.
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
    # Historical verification never trusts a caller-supplied session either;
    # it re-establishes authority above (via verify_historical_v2_execution_authority)
    # and issues its own internal session purely to reuse the per-world path.
    session = _issue_v2_production_session(repo_root, bound)
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
        records, structurally_complete=structurally_complete
    )
    if not _canonical_equal_json(recomputed_conclusions, result.get("conclusions")):
        return False
    recomputed_final = derive_v2_final_overall_mechanical_conclusion(
        records, structurally_complete=structurally_complete
    )
    stored_conclusions = result.get("conclusions")
    if not isinstance(stored_conclusions, Mapping):
        return False
    nested_final = stored_conclusions.get(FINAL_OVERALL_ID)
    top_final = result.get("final_overall_conclusion")
    if nested_final is None or top_final is None:
        return False
    if nested_final != recomputed_final:
        return False
    if top_final != recomputed_final:
        return False
    if recomputed_conclusions.get(FINAL_OVERALL_ID) != recomputed_final:
        return False
    return True


def _canonical_equal_json(left: Any, right: Any) -> bool:
    return canonical_json_bytes(_jsonable(left)) == canonical_json_bytes(_jsonable(right))
