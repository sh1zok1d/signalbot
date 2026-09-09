"""Production durability, aggregation, and result persistence for the frozen harness.

This layer sits above frozen scientific primitives. It does not change RNG, DGP,
gates, Wilson, taxonomy, or mechanical-conclusion semantics. It does not weaken
FixtureExecutionConfig.

Production Monte Carlo remains unarmed. Canonical execution, when later armed by a
separate unit, must cross a fresh Python interpreter boundary and re-verify exact
HEAD/tree plus execution-authority bytes inside that process.

Run identity is a pure function of tracked authority at the exact execution
commit. Local untracked reservation files cannot mint a distinct run/result.
This module does not claim global process exclusion.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from scripts.research.harness_synthetic_edge_calibration_v1_lib import (
    FEATURE_IDS,
    PRODUCTION_BLOCK_ROWS,
    PRODUCTION_BOOTSTRAP_REPLICATES,
    PRODUCTION_PLACEBO_REPLICATES,
    PRODUCTION_PLANNED_TOTAL_WORLDS,
    PRODUCTION_PRIMARY_N,
    PRODUCTION_SMALL_N,
    PRODUCTION_VISIBILITY_REPLICATES,
    PRODUCTION_WORLDS_PER_CELL,
    ROOT_SEED,
    UNIT_ID,
    IncompleteWorld,
    SyntheticExecutionNotAuthorized,
    ae_metrics,
    candidate_features,
    compose_gates,
    era_mean_improvements,
    expanding_era_predictions,
    materiality_fraction_of_attainable,
    mechanical_conclusion,
    namespace_seed,
    pcg64_generator,
    placebo_q95,
    power_verdict,
    prediction_bootstrap,
    scenario_by_id,
    scored_mask,
    select_blind,
    simulate_dgp,
    small_band,
    specificity_verdict,
    support_diagnostics,
    taxonomy_flags,
    taxonomy_of,
    visibility_from_residuals,
    wilson_interval,
    world_identity,
    world_seed,
)
from scripts.research.lib.research_harness import CodeIdentityError, verify_git_freeze

DURABILITY_ID = "HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_DURABILITY_V1"
LIB_REL = "scripts/research/harness_synthetic_edge_calibration_v1_lib.py"
RUNNER_REL = "scripts/research/harness_synthetic_edge_calibration_v1.py"
AUTH_REL = "scripts/research/harness_synthetic_edge_calibration_v1_auth.py"
PRODUCTION_REL = "scripts/research/harness_synthetic_edge_calibration_v1_production.py"
EXECUTION_AUTHORITY_PATHS = (LIB_REL, RUNNER_REL, AUTH_REL, PRODUCTION_REL)
FROZEN_REVIEWED_LIB_SHA256 = (
    "12230dcad714e3a06d3f57de69b78fedcab088be950af3d06f959366f01d6c51"
)
PREREG_JSON_REL = "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.json"
PREREG_MD_REL = "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.md"
CANONICAL_AUTHORIZATION_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_EXECUTION_AUTHORIZATION.json"
)
CANONICAL_RESERVATION_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_RESERVATION.json"
)
CANONICAL_CLAIM_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_EXECUTION_CLAIM.json"
)
CANONICAL_RESULT_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_RESULT.json"
)
CANONICAL_PARTIAL_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_PARTIAL.json"
)
CANONICAL_DURABILITY_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_DURABILITY.json"
)
CANONICAL_ARM_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_ARM.json"
)
FROZEN_GRID_LITERALS = {
    "planned_worlds": 3200,
    "worlds_per_cell": 400,
    "scenario_ids": [
        "NULL",
        "EASY",
        "MODERATE",
        "SMALL",
        "TINY_NOISY",
        "NONSTATIONARY_TRAP",
    ],
    "root_seed": 20260908,
    "primary_n_rows": 5000,
    "small_sensitivity_n": [2500, 10000],
    "bootstrap_replicates": 500,
    "placebo_replicates": 999,
    "visibility_replicates": 500,
    "block_rows": 50,
}
ORACLE_NULL_FPR_MAX = 0.05
BLIND_NULL_FPR_MAX = 0.10
TRAP_STRICT_EX_MAX = 0.20
ORACLE_EASY_MIN = 0.90
ORACLE_MODERATE_MIN = 0.70
BLIND_EASY_USEFUL_MIN = 0.80
BLIND_MODERATE_USEFUL_MIN = 0.50
WORKER_FLAG = "--fresh-process-worker"
R1_PROBE_MODE = "r1-probe"
WORKER_MODE = "worker"
# Stdlib-only isolated bootstrap. Repo root is import-active only after this
# pre-import authority verification succeeds. Do not import numpy or the
# production package before the shadow/authority checks below.
ISOLATED_CHILD_BOOTSTRAP = """
import hashlib
import stat
import subprocess
import sys
from pathlib import Path

FROZEN_LIB = "12230dcad714e3a06d3f57de69b78fedcab088be950af3d06f959366f01d6c51"
FROZEN_PREREG_JSON = "78fcddf03ce84a0369a955d5b571c2423129d12b22e35f77eab26d6ac5eff708"
FROZEN_PREREG_MD = "a54c838d2b4903f039b4fd39d79198415ce095f5a9726fc51949cbb47153e5a3"
LIB_REL = "scripts/research/harness_synthetic_edge_calibration_v1_lib.py"
RUNNER_REL = "scripts/research/harness_synthetic_edge_calibration_v1.py"
AUTH_REL = "scripts/research/harness_synthetic_edge_calibration_v1_auth.py"
PRODUCTION_REL = "scripts/research/harness_synthetic_edge_calibration_v1_production.py"
PREREG_JSON_REL = "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.json"
PREREG_MD_REL = "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.md"
AUTHORITY = (LIB_REL, RUNNER_REL, AUTH_REL, PRODUCTION_REL, PREREG_JSON_REL, PREREG_MD_REL)
FORBIDDEN_ROOT_SHADOWS = ("numpy", "yaml")
ALLOWED_ROOT_PY = {"main.py"}

def refuse(detail):
    print("SYNTHETIC_EXECUTION_NOT_AUTHORIZED: " + detail, file=sys.stderr)
    raise SystemExit(2)

def git(root, *args):
    proc = subprocess.run(
        ["git", "-C", str(root), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        refuse("pre-import git " + " ".join(args) + " failed")
    return proc.stdout

root = Path(sys.argv[1]).resolve()
mode = sys.argv[2]
top = Path(git(root, "rev-parse", "--show-toplevel").decode().strip()).resolve()
if top != root:
    refuse("supplied root is not the git top-level")
head = git(root, "rev-parse", "HEAD").decode("ascii").strip().lower()
if len(head) != 40 or any(ch not in "0123456789abcdef" for ch in head):
    refuse("git HEAD is not an exact 40-hex commit")
tree = git(root, "rev-parse", "HEAD^{tree}").decode("ascii").strip().lower()
if len(tree) != 40 or any(ch not in "0123456789abcdef" for ch in tree):
    refuse("git tree identity is invalid")
status = git(root, "status", "--porcelain", "--untracked-files=all").decode("utf-8", "surrogateescape")
if status.strip():
    refuse("working tree is not clean")
flagged = git(root, "ls-files", "-v", "-z")
for raw_entry in flagged.split(bytes([0])):
    if not raw_entry:
        continue
    tag = chr(raw_entry[0])
    if tag == "S" or tag.islower():
        refuse("tracked file uses skip-worktree/assume-unchanged")
for rel in AUTHORITY:
    if rel.startswith("/") or ".." in Path(rel).parts:
        refuse("invalid git path")
    path = root / rel
    if path.is_symlink() or not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
        refuse("execution authority worktree is not a regular file: " + rel)
    exists = subprocess.run(
        ["git", "-C", str(root), "cat-file", "-e", "HEAD:" + rel],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if exists.returncode != 0:
        refuse("execution authority missing from HEAD: " + rel)
    blob = git(root, "cat-file", "blob", "HEAD:" + rel)
    if path.read_bytes() != blob:
        refuse("worktree bytes differ from HEAD for " + rel)
    digest = hashlib.sha256(blob).hexdigest()
    if rel == LIB_REL and digest != FROZEN_LIB:
        refuse("HEAD scientific lib is not the frozen reviewed implementation")
    if rel == PREREG_JSON_REL and digest != FROZEN_PREREG_JSON:
        refuse("HEAD prereg JSON is not the frozen reviewed blob")
    if rel == PREREG_MD_REL and digest != FROZEN_PREREG_MD:
        refuse("HEAD prereg MD is not the frozen reviewed blob")
for name in FORBIDDEN_ROOT_SHADOWS:
    for candidate in (root / (name + ".py"), root / (name + ".pyc"), root / (name + ".so"), root / name):
        if candidate.exists():
            refuse("repo-root module shadow is not allowed execution authority: " + name)
for child in root.iterdir():
    if child.suffix == ".py" and child.name not in ALLOWED_ROOT_PY:
        refuse("repo-root module shadow is not allowed execution authority: " + child.name)
sys.path.insert(0, str(root))
from scripts.research.harness_synthetic_edge_calibration_v1_production import _isolated_child_main
raise SystemExit(_isolated_child_main(mode))
"""
R1_PROBE_GATE_ARGS = {
    "mean_ae_improvement": 0.05,
    "relative_mae_improvement": 0.03,
    "bootstrap_positive": True,
    "placebo_separation": True,
    "era_improvements": {"E2": 0.1, "E3": 0.1, "E4": 0.1, "E5": -0.01},
    "candidate_positive_count": 50,
}


class ProductionNotArmed(SyntheticExecutionNotAuthorized):
    """Production Monte Carlo is not armed by this durability unit."""


class ProductionIntegrityError(SyntheticExecutionNotAuthorized):
    """World-set or result identity integrity failed closed."""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _refuse(detail: str) -> None:
    raise SyntheticExecutionNotAuthorized(
        f"SYNTHETIC_EXECUTION_NOT_AUTHORIZED: {detail}"
    )


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    """Deterministic JSON: sorted keys, indent 2, trailing newline, no NaN."""
    return (
        json.dumps(
            payload,
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.generic):
        return _jsonable(value.item())
    if isinstance(value, np.ndarray):
        return _jsonable(value.tolist())
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(val) for key, val in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return str(value)


def frozen_production_grid() -> dict[str, Any]:
    """Derive the production grid from frozen literals and independently check constants."""
    from scripts.research.harness_synthetic_edge_calibration_v1_lib import (
        frozen_production_authority,
        load_frozen_prereg,
    )

    prereg = load_frozen_prereg()
    live = frozen_production_authority()
    derived = {
        "planned_worlds": int(live["planned_total_worlds"]),
        "worlds_per_cell": int(live["worlds_per_primary_scenario"]),
        "scenario_ids": [item["id"] for item in prereg["scenarios"]],
        "root_seed": int(live["root_seed"]),
        "primary_n_rows": int(live["primary_N"]),
        "small_sensitivity_n": list(live["small_sensitivity_N"]),
        "bootstrap_replicates": int(live["bootstrap_replicates"]),
        "placebo_replicates": int(live["placebo_replicates"]),
        "visibility_replicates": int(live["visibility_replicates"]),
        "block_rows": int(live["block_rows"]),
    }
    if derived != FROZEN_GRID_LITERALS:
        _refuse("derived production grid is not the frozen literal authority")
    if (
        derived["planned_worlds"] != PRODUCTION_PLANNED_TOTAL_WORLDS
        or derived["worlds_per_cell"] != PRODUCTION_WORLDS_PER_CELL
        or derived["root_seed"] != ROOT_SEED
        or derived["primary_n_rows"] != PRODUCTION_PRIMARY_N
        or derived["small_sensitivity_n"] != list(PRODUCTION_SMALL_N)
        or derived["bootstrap_replicates"] != PRODUCTION_BOOTSTRAP_REPLICATES
        or derived["placebo_replicates"] != PRODUCTION_PLACEBO_REPLICATES
        or derived["visibility_replicates"] != PRODUCTION_VISIBILITY_REPLICATES
        or derived["block_rows"] != PRODUCTION_BLOCK_ROWS
    ):
        _refuse("production grid drifted from frozen module constants")
    return dict(derived)


def planned_production_jobs() -> tuple[tuple[str, int, int], ...]:
    grid = frozen_production_grid()
    jobs: list[tuple[str, int, int]] = []
    worlds = int(grid["worlds_per_cell"])
    primary_n = int(grid["primary_n_rows"])
    for scenario_id in grid["scenario_ids"]:
        for world_index in range(worlds):
            jobs.append((str(scenario_id), primary_n, world_index))
    for extra_n in [int(n) for n in grid["small_sensitivity_n"]]:
        for world_index in range(worlds):
            jobs.append(("SMALL", extra_n, world_index))
    if len(jobs) != PRODUCTION_PLANNED_TOTAL_WORLDS:
        _refuse("production world plan is not 3200 identities")
    if jobs[0] != ("NULL", 5000, 0) or jobs[-1] != ("SMALL", 10000, 399):
        _refuse("production world plan identity order drifted")
    return tuple(jobs)


def _git(repo_root: Path, *args: str) -> bytes:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        _refuse(f"git {' '.join(args)} failed")
    return proc.stdout


def _head_sha(repo_root: Path) -> str:
    return _git(repo_root, "rev-parse", "HEAD").decode("ascii").strip().lower()


def _tree_sha(repo_root: Path) -> str:
    return _git(repo_root, "rev-parse", "HEAD^{tree}").decode("ascii").strip().lower()


def _head_blob(repo_root: Path, git_path: str) -> bytes | None:
    if git_path.startswith("/") or ".." in Path(git_path).parts:
        _refuse("invalid git path")
    exists = subprocess.run(
        ["git", "-C", str(repo_root), "cat-file", "-e", f"HEAD:{git_path}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if exists.returncode != 0:
        return None
    return _git(repo_root, "cat-file", "blob", f"HEAD:{git_path}")


def _commit_blob(repo_root: Path, commit: str, git_path: str) -> bytes | None:
    if git_path.startswith("/") or ".." in Path(git_path).parts:
        _refuse("invalid git path")
    exists = subprocess.run(
        ["git", "-C", str(repo_root), "cat-file", "-e", f"{commit}:{git_path}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if exists.returncode != 0:
        return None
    return _git(repo_root, "cat-file", "blob", f"{commit}:{git_path}")


def _parent_sha(repo_root: Path) -> str | None:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD^"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout.decode("ascii").strip().lower()


def _commit_tree_sha(repo_root: Path, commit: str) -> str:
    return _git(repo_root, "rev-parse", f"{commit}^{{tree}}").decode("ascii").strip().lower()


def _authority_digests_at(repo_root: Path, commit: str) -> dict[str, str]:
    digests: dict[str, str] = {}
    mapping = {
        "lib": LIB_REL,
        "runner": RUNNER_REL,
        "auth": AUTH_REL,
        "production": PRODUCTION_REL,
        "prereg_json": PREREG_JSON_REL,
        "prereg_md": PREREG_MD_REL,
    }
    for key, rel in mapping.items():
        blob = _commit_blob(repo_root, commit, rel)
        if blob is None:
            _refuse(f"execution authority missing from {commit}: {rel}")
        digests[key] = _sha256_bytes(blob)
    durability = _commit_blob(repo_root, commit, CANONICAL_DURABILITY_PATH)
    if durability is not None:
        digests["durability"] = _sha256_bytes(durability)
    return digests


def production_monte_carlo_arm_authorized(repo_root: Path | None = None) -> bool:
    """ARM in commit C_arm authorizes its parent execution commit C_exec.

    This is constructible: the ARM artifact is not a fixed point of its own
    commit/tree. A descendant of C_arm is not armed. This PR does not add a
    live ARM artifact.
    """
    root = repo_root or _repo_root()
    blob = _head_blob(root, CANONICAL_ARM_PATH)
    if blob is None:
        return False
    try:
        payload = json.loads(blob.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    if payload.get("production_monte_carlo_arm_authorized") is not True:
        return False
    parent = _parent_sha(root)
    if parent is None:
        return False
    authorized_commit = str(payload.get("authorized_execution_commit") or "").strip().lower()
    authorized_tree = str(payload.get("authorized_execution_tree") or "").strip().lower()
    if authorized_commit != parent:
        return False
    if authorized_tree != _commit_tree_sha(root, parent):
        return False
    listed = payload.get("execution_authority_sha256")
    if not isinstance(listed, dict):
        return False
    try:
        actual = _authority_digests_at(root, parent)
    except SyntheticExecutionNotAuthorized:
        return False
    required = ("lib", "runner", "auth", "production", "prereg_json", "prereg_md")
    if any(key not in listed for key in required):
        return False
    for key, digest in listed.items():
        if actual.get(key) != str(digest).strip().lower():
            return False
    for rel in EXECUTION_AUTHORITY_PATHS:
        head_bytes = _head_blob(root, rel)
        parent_bytes = _commit_blob(root, parent, rel)
        if head_bytes is None or parent_bytes is None or head_bytes != parent_bytes:
            return False
    return True


def _executing_file(rel: str) -> Path:
    names = {
        LIB_REL: "harness_synthetic_edge_calibration_v1_lib.py",
        RUNNER_REL: "harness_synthetic_edge_calibration_v1.py",
        AUTH_REL: "harness_synthetic_edge_calibration_v1_auth.py",
        PRODUCTION_REL: "harness_synthetic_edge_calibration_v1_production.py",
    }
    return Path(__file__).resolve().with_name(names[rel])


def verify_executed_production_authority(repo_root: Path | None = None) -> dict[str, str]:
    """Re-verify exact HEAD/tree and execution bytes. Call inside the fresh process."""
    root = repo_root or _repo_root()
    head = _head_sha(root)
    try:
        freeze = verify_git_freeze(root, head)
    except CodeIdentityError as exc:
        raise SyntheticExecutionNotAuthorized(
            f"SYNTHETIC_EXECUTION_NOT_AUTHORIZED: executed checkout is not a clean verified freeze ({exc})"
        ) from exc
    tree = _tree_sha(root)
    if freeze.code_sha != head or freeze.tree_oid != tree:
        _refuse("verified freeze identity drifted from HEAD")
    bound: dict[str, str] = {"head_sha": head, "tree_sha": tree}
    for rel in EXECUTION_AUTHORITY_PATHS:
        head_bytes = _head_blob(root, rel)
        if head_bytes is None:
            _refuse(f"execution authority missing from HEAD: {rel}")
        worktree = root / rel
        if worktree.is_symlink() or not worktree.is_file():
            _refuse(f"execution authority worktree is not a regular file: {rel}")
        worktree_bytes = worktree.read_bytes()
        executing_bytes = _executing_file(rel).read_bytes()
        if worktree_bytes != head_bytes:
            _refuse(f"worktree bytes differ from HEAD for {rel}")
        if executing_bytes != head_bytes:
            _refuse(f"executed bytes differ from HEAD for {rel}")
        digest = _sha256_bytes(head_bytes)
        if rel == LIB_REL and digest != FROZEN_REVIEWED_LIB_SHA256:
            _refuse("HEAD scientific lib is not the frozen reviewed implementation")
        bound[rel] = digest
    for rel, expected_key in (
        (PREREG_JSON_REL, "prereg_json_sha256"),
        (PREREG_MD_REL, "prereg_md_sha256"),
    ):
        blob = _head_blob(root, rel)
        if blob is None:
            _refuse(f"frozen prereg missing from HEAD: {rel}")
        if (root / rel).read_bytes() != blob:
            _refuse(f"worktree prereg bytes differ from HEAD for {rel}")
        bound[expected_key] = _sha256_bytes(blob)
    auth_blob = _head_blob(root, CANONICAL_AUTHORIZATION_PATH)
    if auth_blob is not None:
        bound["authorization_sha256"] = _sha256_bytes(auth_blob)
    return bound


def _bound_from_commit_blobs(repo_root: Path, commit: str) -> dict[str, str]:
    """Authority digests from git objects at an exact commit. No worktree authority."""
    commit = str(commit).strip().lower()
    bound: dict[str, str] = {
        "head_sha": commit,
        "tree_sha": _commit_tree_sha(repo_root, commit),
    }
    for rel in EXECUTION_AUTHORITY_PATHS:
        blob = _commit_blob(repo_root, commit, rel)
        if blob is None:
            _refuse(f"execution authority missing from {commit}: {rel}")
        digest = _sha256_bytes(blob)
        if rel == LIB_REL and digest != FROZEN_REVIEWED_LIB_SHA256:
            _refuse("commit scientific lib is not the frozen reviewed implementation")
        bound[rel] = digest
    for rel, expected_key in (
        (PREREG_JSON_REL, "prereg_json_sha256"),
        (PREREG_MD_REL, "prereg_md_sha256"),
    ):
        blob = _commit_blob(repo_root, commit, rel)
        if blob is None:
            _refuse(f"frozen prereg missing from {commit}: {rel}")
        bound[expected_key] = _sha256_bytes(blob)
    auth_blob = _commit_blob(repo_root, commit, CANONICAL_AUTHORIZATION_PATH)
    if auth_blob is not None:
        bound["authorization_sha256"] = _sha256_bytes(auth_blob)
    return bound


def _run_identity_from_bound(bound: Mapping[str, str]) -> str:
    payload = {
        "durability_id": DURABILITY_ID,
        "unit_id": UNIT_ID,
        "head_sha": bound["head_sha"],
        "tree_sha": bound["tree_sha"],
        "lib_sha256": bound[LIB_REL],
        "runner_sha256": bound[RUNNER_REL],
        "auth_sha256": bound[AUTH_REL],
        "production_sha256": bound[PRODUCTION_REL],
        "prereg_json_sha256": bound["prereg_json_sha256"],
        "prereg_md_sha256": bound["prereg_md_sha256"],
        "grid": frozen_production_grid(),
        "authorization_sha256": bound.get("authorization_sha256"),
        "result_path": CANONICAL_RESULT_PATH,
        "reservation_path": CANONICAL_RESERVATION_PATH,
        "claim_path": CANONICAL_CLAIM_PATH,
    }
    return _sha256_bytes(canonical_json_bytes(payload))


def canonical_run_identity(repo_root: Path | None = None) -> str:
    """Durable run identity from tracked execution-commit authority only."""
    root = repo_root or _repo_root()
    return _run_identity_from_bound(verify_executed_production_authority(root))


def _optional_head_sha256(repo_root: Path, git_path: str) -> str | None:
    blob = _head_blob(repo_root, git_path)
    if blob is None:
        return None
    return _sha256_bytes(blob)


def durable_reservation_document(repo_root: Path | None = None) -> dict[str, Any]:
    """Reservation identity is a function of tracked commit authority only."""
    root = repo_root or _repo_root()
    bound = verify_executed_production_authority(root)
    return {
        "schema_version": "1.0",
        "durability_id": DURABILITY_ID,
        "unit_id": UNIT_ID,
        "canonical_path": CANONICAL_RESERVATION_PATH,
        "run_identity": canonical_run_identity(root),
        "execution_head": bound["head_sha"],
        "execution_tree": bound["tree_sha"],
        "authority_sha256": {
            "lib": bound[LIB_REL],
            "runner": bound[RUNNER_REL],
            "auth": bound[AUTH_REL],
            "production": bound[PRODUCTION_REL],
        },
        "prereg_json_sha256": bound["prereg_json_sha256"],
        "prereg_md_sha256": bound["prereg_md_sha256"],
        "authorization_sha256": bound.get("authorization_sha256"),
        "lifecycle": "TRACKED_IDENTITY_UNARMED",
        "automatic_retry_authorized": False,
        "global_process_exclusion_claimed": False,
        "production_monte_carlo_arm_authorized": False,
    }


def durable_claim_document(repo_root: Path | None = None) -> dict[str, Any]:
    """Claim identity is the same tracked run identity as the reservation."""
    reservation = durable_reservation_document(repo_root)
    return {
        "schema_version": "1.0",
        "durability_id": DURABILITY_ID,
        "unit_id": UNIT_ID,
        "canonical_path": CANONICAL_CLAIM_PATH,
        "run_identity": reservation["run_identity"],
        "execution_head": reservation["execution_head"],
        "execution_tree": reservation["execution_tree"],
        "reservation_sha256": _sha256_bytes(canonical_json_bytes(reservation)),
        "lifecycle": "TRACKED_IDENTITY_UNARMED",
        "automatic_retry_authorized": False,
        "global_process_exclusion_claimed": False,
        "production_monte_carlo_arm_authorized": False,
        "production_calibration_executed": False,
        "final_result_minted": False,
    }


def evaluate_production_candidate(
    world: Mapping[str, Any],
    feature_id: str,
    *,
    scenario_id: str,
    n_rows: int,
    world_index: int,
) -> dict[str, Any]:
    """Orchestrate frozen primitives for one candidate. Does not use FixtureExecutionConfig."""
    n = int(n_rows)
    features = candidate_features(world)
    feature = features[feature_id]
    y = world["Y"]
    x1 = world["X1"]
    x2 = world["X2"]
    s = world["S"]
    reasons: list[str] = []
    try:
        preds = expanding_era_predictions(y, x1, x2, feature, n)
        mask = scored_mask(n)
        metrics = ae_metrics(y, preds["BASE_PRED"], preds["CAND_PRED"], mask)
        ae_imp_full = np.full(n, np.nan, dtype=np.float64)
        ae_imp_full[mask] = np.abs(y[mask] - preds["BASE_PRED"][mask]) - np.abs(
            y[mask] - preds["CAND_PRED"][mask]
        )
        diag = support_diagnostics(s, ae_imp_full, mask, n)
        era_imp = era_mean_improvements(y, preds["BASE_PRED"], preds["CAND_PRED"], n)
        cand_pos = int(np.sum(feature[mask] == 1.0))
        identity = str(world.get("world_identity", world_identity(scenario_id, n, world_index)))
        wseed = int(world_seed(identity))
        vis = visibility_from_residuals(
            y - preds["BASE_PRED"],
            s,
            n,
            replicates=PRODUCTION_VISIBILITY_REPLICATES,
            block_rows=PRODUCTION_BLOCK_ROWS,
            rng=pcg64_generator(namespace_seed(wseed, "VISIBILITY")),
        )
        boot = prediction_bootstrap(
            ae_imp_full,
            n,
            replicates=PRODUCTION_BOOTSTRAP_REPLICATES,
            block_rows=PRODUCTION_BLOCK_ROWS,
            rng=pcg64_generator(namespace_seed(wseed, "BOOTSTRAP", feature_id)),
        )
        if boot["world_invalid"]:
            reasons.append("bootstrap_invalid")
        plac = placebo_q95(
            world=world,
            feature=feature,
            n_rows=n,
            replicates=PRODUCTION_PLACEBO_REPLICATES,
            rng=pcg64_generator(namespace_seed(wseed, "PLACEBO", feature_id)),
        )
        if plac["world_invalid"]:
            reasons.append("placebo_invalid")
        placebo_sep = (
            (not plac["placebo_invalid"])
            and np.isfinite(plac["placebo_q95"])
            and metrics["MEAN_AE_IMPROVEMENT"] > plac["placebo_q95"]
        )
        scenario = scenario_by_id(scenario_id)
        materiality_fraction = materiality_fraction_of_attainable(
            metrics["RELATIVE_MAE_IMPROVEMENT"],
            float(scenario.get("asymptotic_max_relative_mae_improvement_approx", 0.0)),
        )
        gates = compose_gates(
            mean_ae_improvement=metrics["MEAN_AE_IMPROVEMENT"],
            relative_mae_improvement=metrics["RELATIVE_MAE_IMPROVEMENT"],
            bootstrap_positive=bool(boot["bootstrap_positive"]),
            placebo_separation=bool(placebo_sep),
            era_improvements=era_imp,
            candidate_positive_count=cand_pos,
        )
    except IncompleteWorld as exc:
        return {
            "feature_id": feature_id,
            "valid": False,
            "invalid_reasons": (str(exc),),
            "stays_in_denominator": True,
        }
    return {
        "feature_id": feature_id,
        "valid": not reasons,
        "invalid_reasons": tuple(reasons),
        "MEAN_AE_IMPROVEMENT": metrics["MEAN_AE_IMPROVEMENT"],
        "RELATIVE_MAE_IMPROVEMENT": metrics["RELATIVE_MAE_IMPROVEMENT"],
        "gates": gates,
        "diagnostics": diag,
        "visibility": vis,
        "bootstrap": boot,
        "placebo": plac,
        "era_improvements": era_imp,
        "candidate_positive_count": cand_pos,
        "train_end_by_score_era": preds["train_end_by_score_era"],
        "MATERIALITY_FRACTION_OF_ATTAINABLE": materiality_fraction,
        "stays_in_denominator": True,
    }


def evaluate_production_world(
    scenario_id: str,
    n_rows: int,
    world_index: int,
    *args: Any,
    **kwargs: Any,
) -> dict[str, Any]:
    """Evaluate one frozen-grid world. Refuses unless a later unit has armed Monte Carlo."""
    if args or kwargs:
        _refuse("caller arguments cannot authorize production evaluation")
    root = _repo_root()
    verify_executed_production_authority(root)
    if (scenario_id, int(n_rows), int(world_index)) not in set(planned_production_jobs()):
        _refuse("world is not a frozen production-grid identity")
    if production_monte_carlo_arm_authorized(root) is not True:
        raise ProductionNotArmed(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: production_monte_carlo_arm_authorized=false"
        )
    identity = world_identity(scenario_id, int(n_rows), int(world_index))
    try:
        world = simulate_dgp(
            scenario_id=scenario_id,
            n_rows=int(n_rows),
            world_index=int(world_index),
        )
        rows = []
        any_invalid = False
        reasons: list[str] = []
        for feature_id in FEATURE_IDS:
            ev = evaluate_production_candidate(
                world,
                feature_id,
                scenario_id=scenario_id,
                n_rows=int(n_rows),
                world_index=int(world_index),
            )
            if not ev["valid"]:
                any_invalid = True
                reasons.extend(ev["invalid_reasons"])
            rows.append(ev)
        oracle = next(row for row in rows if row["feature_id"] == "F03")
        selected_ex = select_blind(rows, gate="STRICT_PASS_EX_MATERIALITY")
        selected_strict = select_blind(rows, gate="STRICT_PASS")
        label = taxonomy_of(None if selected_ex == "NO_CANDIDATE" else selected_ex)
        oracle_gates = oracle.get("gates") or {}
        return _jsonable(
            {
                "scenario_id": scenario_id,
                "n_rows": int(n_rows),
                "world_index": int(world_index),
                "world_identity": identity,
                "world_seed": int(world_seed(identity)),
                "valid": not any_invalid,
                "invalid_reasons": tuple(reasons),
                "oracle_F03": oracle,
                "candidates": rows,
                "selected_STRICT_PASS_EX_MATERIALITY": selected_ex,
                "selected_STRICT_PASS": selected_strict,
                "taxonomy": label,
                "taxonomy_flags": taxonomy_flags(label),
                "visibility": oracle.get("visibility"),
                "materiality": {
                    "RELATIVE_MAE_IMPROVEMENT": oracle.get("RELATIVE_MAE_IMPROVEMENT"),
                    "MATERIALITY_FRACTION_OF_ATTAINABLE": oracle.get(
                        "MATERIALITY_FRACTION_OF_ATTAINABLE"
                    ),
                    "STRICT_PASS": oracle_gates.get("STRICT_PASS"),
                    "STRICT_PASS_EX_MATERIALITY": oracle_gates.get(
                        "STRICT_PASS_EX_MATERIALITY"
                    ),
                },
                "train_end_by_score_era": oracle.get("train_end_by_score_era"),
                "stays_in_denominator": True,
            }
        )
    except IncompleteWorld as exc:
        return _jsonable(
            {
                "scenario_id": scenario_id,
                "n_rows": int(n_rows),
                "world_index": int(world_index),
                "world_identity": identity,
                "world_seed": int(world_seed(identity)),
                "valid": False,
                "invalid_reasons": (str(exc),),
                "stays_in_denominator": True,
            }
        )


def _cell_records(
    records: Sequence[Mapping[str, Any]], scenario_id: str, n_rows: int
) -> list[Mapping[str, Any]]:
    return [
        rec
        for rec in records
        if rec.get("scenario_id") == scenario_id and int(rec.get("n_rows", -1)) == n_rows
    ]


def _require_unique_planned_set(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    jobs = planned_production_jobs()
    planned = set(jobs)
    by_identity: dict[str, Mapping[str, Any]] = {}
    by_job: dict[tuple[str, int, int], Mapping[str, Any]] = {}
    for rec in records:
        identity = str(rec.get("world_identity", ""))
        job = (
            str(rec.get("scenario_id")),
            int(rec.get("n_rows", -1)),
            int(rec.get("world_index", -1)),
        )
        expected_identity = world_identity(*job)
        if identity != expected_identity:
            raise ProductionIntegrityError(
                "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: world identity does not match job"
            )
        if job not in planned:
            raise ProductionIntegrityError(
                "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: extra world is not in the planned production set"
            )
        digest = _sha256_bytes(canonical_json_bytes(_jsonable(dict(rec))))
        if identity in by_identity:
            prior = _sha256_bytes(canonical_json_bytes(_jsonable(dict(by_identity[identity]))))
            if prior != digest:
                raise ProductionIntegrityError(
                    "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: conflicting duplicate world identity"
                )
            raise ProductionIntegrityError(
                "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: duplicate world identity"
            )
        if job in by_job:
            raise ProductionIntegrityError(
                "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: duplicate world identity"
            )
        by_identity[identity] = rec
        by_job[job] = rec
    missing = [job for job in jobs if job not in by_job]
    invalid_records = [rec for rec in records if rec.get("valid") is not True]
    return {
        "by_job": by_job,
        "missing": missing,
        "invalid_records": invalid_records,
        "incomplete_execution": bool(missing) or bool(invalid_records),
        "planned_world_count": len(jobs),
        "observed_world_count": len(by_job),
    }


def _wilson_arm(records: Sequence[Mapping[str, Any]], predicate) -> dict[str, Any]:
    n = len(records)
    successes = sum(1 for rec in records if predicate(rec))
    if n <= 0:
        interval = {
            "n": 0.0,
            "successes": 0.0,
            "phat": 0.0,
            "center": 0.0,
            "lower": 0.0,
            "upper": 0.0,
        }
    else:
        interval = wilson_interval(successes, n)
    return {
        "successes": successes,
        "n": n,
        "interval": interval,
        "incomplete_cell": n != PRODUCTION_WORLDS_PER_CELL,
    }


def _oracle_model_detected(rec: Mapping[str, Any]) -> bool:
    gates = ((rec.get("oracle_F03") or {}).get("gates")) or {}
    return gates.get("MODEL_DETECTED") is True


def _oracle_strict_ex(rec: Mapping[str, Any]) -> bool:
    gates = ((rec.get("oracle_F03") or {}).get("gates")) or {}
    return gates.get("STRICT_PASS_EX_MATERIALITY") is True


def _oracle_strict(rec: Mapping[str, Any]) -> bool:
    gates = ((rec.get("oracle_F03") or {}).get("gates")) or {}
    return gates.get("STRICT_PASS") is True


def _oracle_visible(rec: Mapping[str, Any]) -> bool:
    vis = rec.get("visibility") or (rec.get("oracle_F03") or {}).get("visibility") or {}
    return vis.get("GROUND_TRUTH_VISIBLE") is True


def aggregate_planned_worlds(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate exactly the planned 3200-world set. Invalid worlds stay in the denominator."""
    frozen_production_grid()
    integrity = _require_unique_planned_set(records)
    records = list(records)
    nulls = _cell_records(records, "NULL", 5000)
    easys = _cell_records(records, "EASY", 5000)
    moderates = _cell_records(records, "MODERATE", 5000)
    traps = _cell_records(records, "NONSTATIONARY_TRAP", 5000)
    small_5000 = _cell_records(records, "SMALL", 5000)
    small_2500 = _cell_records(records, "SMALL", 2500)
    small_10000 = _cell_records(records, "SMALL", 10000)

    oracle_null = _wilson_arm(nulls, _oracle_model_detected)
    blind_null = _wilson_arm(
        nulls, lambda rec: bool((rec.get("taxonomy_flags") or {}).get("ANY_EDGE_DECLARED"))
    )
    trap_ex = _wilson_arm(traps, _oracle_strict_ex)
    easy_oracle = _wilson_arm(easys, _oracle_model_detected)
    moderate_oracle = _wilson_arm(moderates, _oracle_model_detected)
    easy_useful = _wilson_arm(
        easys, lambda rec: bool((rec.get("taxonomy_flags") or {}).get("USEFUL_DISCOVERY"))
    )
    moderate_useful = _wilson_arm(
        moderates, lambda rec: bool((rec.get("taxonomy_flags") or {}).get("USEFUL_DISCOVERY"))
    )
    small_oracle_5000 = _wilson_arm(small_5000, _oracle_model_detected)
    small_oracle_2500 = _wilson_arm(small_2500, _oracle_model_detected)
    small_oracle_10000 = _wilson_arm(small_10000, _oracle_model_detected)
    easy_visibility = _wilson_arm(easys, _oracle_visible)
    easy_strict = _wilson_arm(easys, _oracle_strict)
    easy_strict_ex = _wilson_arm(easys, _oracle_strict_ex)
    true_discovery = _wilson_arm(
        records, lambda rec: bool((rec.get("taxonomy_flags") or {}).get("TRUE_DISCOVERY"))
    )

    incomplete = bool(integrity["incomplete_execution"])

    def _spec(arm: dict[str, Any], maximum: float) -> str:
        return specificity_verdict(arm["interval"], maximum) if arm["n"] else "INDETERMINATE"

    def _pow(arm: dict[str, Any], minimum: float) -> str:
        return power_verdict(arm["interval"], minimum) if arm["n"] else "INDETERMINATE"

    oracle_null_v = _spec(oracle_null, ORACLE_NULL_FPR_MAX)
    blind_null_v = _spec(blind_null, BLIND_NULL_FPR_MAX)
    trap_v = _spec(trap_ex, TRAP_STRICT_EX_MAX)
    easy_oracle_v = _pow(easy_oracle, ORACLE_EASY_MIN)
    moderate_oracle_v = _pow(moderate_oracle, ORACLE_MODERATE_MIN)
    easy_useful_v = _pow(easy_useful, BLIND_EASY_USEFUL_MIN)
    moderate_useful_v = _pow(moderate_useful, BLIND_MODERATE_USEFUL_MIN)
    visibility_upper = float(easy_visibility["interval"]["upper"]) if easy_visibility["n"] else None
    model_upper = float(easy_oracle["interval"]["upper"]) if easy_oracle["n"] else None
    materiality_only = bool(
        easy_strict_ex["successes"] > easy_strict["successes"]
        and easy_strict_ex["n"] == PRODUCTION_WORLDS_PER_CELL
    )

    invalid_by_cell: dict[str, Any] = {}
    total_invalid = 0
    reason_counts: dict[str, int] = {}
    for scenario_id, n_rows in (
        ("NULL", 5000),
        ("EASY", 5000),
        ("MODERATE", 5000),
        ("SMALL", 5000),
        ("TINY_NOISY", 5000),
        ("NONSTATIONARY_TRAP", 5000),
        ("SMALL", 2500),
        ("SMALL", 10000),
    ):
        cell = _cell_records(records, scenario_id, n_rows)
        invalid = [rec for rec in cell if rec.get("valid") is False]
        total_invalid += len(invalid)
        reasons: dict[str, int] = {}
        for rec in invalid:
            for reason in rec.get("invalid_reasons") or ():
                reasons[str(reason)] = reasons.get(str(reason), 0) + 1
                reason_counts[str(reason)] = reason_counts.get(str(reason), 0) + 1
        invalid_by_cell[f"{scenario_id}|{n_rows}"] = {
            "invalid_count": len(invalid),
            "planned": PRODUCTION_WORLDS_PER_CELL,
            "observed": len(cell),
            "reasons": reasons,
        }

    conclusion = mechanical_conclusion(
        incomplete_execution=incomplete,
        oracle_null_specificity=oracle_null_v,
        blind_null_specificity=blind_null_v,
        trap_specificity=trap_v,
        easy_oracle_power=easy_oracle_v,
        moderate_oracle_power=moderate_oracle_v,
        easy_blind_useful=easy_useful_v,
        moderate_blind_useful=moderate_useful_v,
        visibility_wilson_upper=visibility_upper,
        model_detection_wilson_upper=model_upper,
        materiality_only_failure=materiality_only,
    )
    return {
        "planned_world_count": integrity["planned_world_count"],
        "observed_world_count": integrity["observed_world_count"],
        "incomplete_execution": incomplete,
        "missing_jobs": [list(job) for job in integrity["missing"]],
        "arms": {
            "ORACLE_NULL_MODEL_DETECTED": {
                **oracle_null,
                "verdict": oracle_null_v,
                "threshold": ORACLE_NULL_FPR_MAX,
            },
            "BLIND_NULL_ANY_EDGE_DECLARED": {
                **blind_null,
                "verdict": blind_null_v,
                "threshold": BLIND_NULL_FPR_MAX,
            },
            "NONSTATIONARY_TRAP_STRICT_PASS_EX_MATERIALITY": {
                **trap_ex,
                "verdict": trap_v,
                "threshold": TRAP_STRICT_EX_MAX,
            },
            "ORACLE_EASY_MODEL_DETECTED": {
                **easy_oracle,
                "verdict": easy_oracle_v,
                "threshold": ORACLE_EASY_MIN,
            },
            "ORACLE_MODERATE_MODEL_DETECTED": {
                **moderate_oracle,
                "verdict": moderate_oracle_v,
                "threshold": ORACLE_MODERATE_MIN,
            },
            "BLIND_EASY_USEFUL_DISCOVERY": {
                **easy_useful,
                "verdict": easy_useful_v,
                "threshold": BLIND_EASY_USEFUL_MIN,
            },
            "BLIND_MODERATE_USEFUL_DISCOVERY": {
                **moderate_useful,
                "verdict": moderate_useful_v,
                "threshold": BLIND_MODERATE_USEFUL_MIN,
            },
            "SMALL_ORACLE_MODEL_DETECTED_N5000": {
                **small_oracle_5000,
                "band": small_band(small_oracle_5000["interval"])
                if small_oracle_5000["n"]
                else "INDETERMINATE",
            },
            "SMALL_ORACLE_MODEL_DETECTED_N2500": {
                **small_oracle_2500,
                "band": small_band(small_oracle_2500["interval"])
                if small_oracle_2500["n"]
                else "INDETERMINATE",
            },
            "SMALL_ORACLE_MODEL_DETECTED_N10000": {
                **small_oracle_10000,
                "band": small_band(small_oracle_10000["interval"])
                if small_oracle_10000["n"]
                else "INDETERMINATE",
            },
            "TRUE_DISCOVERY_RATE": {
                **true_discovery,
                "band": small_band(true_discovery["interval"])
                if true_discovery["n"]
                else "INDETERMINATE",
                "descriptive_only": True,
            },
            "VISIBILITY_FLOOR_EASY_ORACLE": easy_visibility,
            "MODEL_FLOOR_EASY_ORACLE": easy_oracle,
            "MATERIALITY_ONLY_DIAGNOSTIC": {
                "strict_ex": easy_strict_ex,
                "strict": easy_strict,
                "materiality_only_failure": materiality_only,
            },
        },
        "invalid_counts_by_cell": invalid_by_cell,
        "invalid_counts_total": {"invalid_count": total_invalid, "reasons": reason_counts},
        "verdicts": {
            "oracle_null_specificity": oracle_null_v,
            "blind_null_specificity": blind_null_v,
            "trap_specificity": trap_v,
            "easy_oracle_power": easy_oracle_v,
            "moderate_oracle_power": moderate_oracle_v,
            "easy_blind_useful": easy_useful_v,
            "moderate_blind_useful": moderate_useful_v,
        },
        "mechanical_conclusion": conclusion,
        "real_market_data_access_authorized": False,
        "b2_06_scientific_execution_authorized": False,
        "validation_2025_authorized": False,
        "oos_2026_authorized": False,
    }


def canonical_world_set_bytes(records):
    integrity = _require_unique_planned_set(records)
    jobs = planned_production_jobs()
    ordered = [integrity["by_job"][job] for job in jobs if job in integrity["by_job"]]
    return canonical_json_bytes({"worlds": [_jsonable(dict(rec)) for rec in ordered]})


def world_set_sha256(records):
    return _sha256_bytes(canonical_world_set_bytes(records))


def _bind_result_core(*, records, repo_root):
    """Private non-authoritative core builder. Callers must go through mint_final_result."""
    bound = verify_executed_production_authority(repo_root)
    aggregates = aggregate_planned_worlds(records)
    reservation = durable_reservation_document(repo_root)
    claim = durable_claim_document(repo_root)
    return {
        "schema_version": "1.0",
        "unit_id": UNIT_ID,
        "durability_id": DURABILITY_ID,
        "execution_head": bound["head_sha"],
        "execution_tree": bound["tree_sha"],
        "authority_paths": list(EXECUTION_AUTHORITY_PATHS),
        "authority_sha256": {
            "lib": bound[LIB_REL],
            "runner": bound[RUNNER_REL],
            "auth": bound[AUTH_REL],
            "production": bound[PRODUCTION_REL],
        },
        "prereg_json_sha256": bound["prereg_json_sha256"],
        "prereg_md_sha256": bound["prereg_md_sha256"],
        "frozen_lib_sha256": bound[LIB_REL],
        "authorization_sha256": bound.get("authorization_sha256"),
        "reservation_sha256": _sha256_bytes(canonical_json_bytes(reservation)),
        "claim_sha256": _sha256_bytes(canonical_json_bytes(claim)),
        "run_identity": canonical_run_identity(repo_root),
        "world_set_sha256": world_set_sha256(records),
        "planned_world_count": aggregates["planned_world_count"],
        "observed_world_count": aggregates["observed_world_count"],
        "aggregates": _jsonable(aggregates),
        "mechanical_conclusion": aggregates["mechanical_conclusion"],
        "real_market_data_access_authorized": False,
        "b2_06_scientific_execution_authorized": False,
        "validation_2025_authorized": False,
        "oos_2026_authorized": False,
        "production_monte_carlo_arm_authorized": False,
        "production_calibration_executed": False,
        "verdicts": aggregates["verdicts"],
        "wilson_intervals": {
            name: arm.get("interval")
            for name, arm in aggregates.get("arms", {}).items()
            if isinstance(arm, Mapping) and "interval" in arm
        },
        "persistence": {
            "canonical_result_path": CANONICAL_RESULT_PATH,
            "uncommitted_worktree_write_is_not_authority": True,
            "verify_from_git_object_at_claim_commit": True,
        },
    }


def bind_result_document(*args, **kwargs):
    """Removed public binder. Caller-supplied aggregates cannot mint a RESULT."""
    _refuse("caller-supplied aggregates cannot mint a production RESULT")


def mint_final_result(records, *args, **kwargs):
    if args or kwargs:
        _refuse("caller arguments cannot authorize a production RESULT")
    root = _repo_root()
    verify_executed_production_authority(root)
    if production_monte_carlo_arm_authorized(root) is not True:
        raise ProductionNotArmed(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: production RESULT cannot be minted while unarmed"
        )
    aggregates = aggregate_planned_worlds(records)
    if (
        aggregates["incomplete_execution"]
        or aggregates["observed_world_count"] != PRODUCTION_PLANNED_TOTAL_WORLDS
        or aggregates["mechanical_conclusion"] == "INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM"
    ):
        _refuse("incomplete execution cannot mint a final RESULT")
    core = _bind_result_core(records=records, repo_root=root)
    core_bytes = canonical_json_bytes(_jsonable(core))
    return {
        "core": core,
        "core_sha256": _sha256_bytes(core_bytes),
        "core_size": len(core_bytes),
    }


def verify_bound_result_document(document, records, *args, **kwargs):
    if args or kwargs:
        _refuse("caller arguments cannot authorize result verification")
    if not isinstance(document, Mapping) or "core" not in document:
        raise ProductionIntegrityError(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: result envelope is missing core"
        )
    if set(document.keys()) != {"core", "core_sha256", "core_size"}:
        raise ProductionIntegrityError(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: result envelope is not the canonical core envelope"
        )
    core = document["core"]
    if not isinstance(core, Mapping):
        raise ProductionIntegrityError(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: result envelope is missing core"
        )
    core_bytes = canonical_json_bytes(_jsonable(dict(core)))
    if document.get("core_sha256") != _sha256_bytes(core_bytes):
        raise ProductionIntegrityError(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: core digest tamper detected"
        )
    if document.get("core_size") != len(core_bytes):
        raise ProductionIntegrityError(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: core size tamper detected"
        )
    expected = _bind_result_core(records=records, repo_root=_repo_root())
    expected_bytes = canonical_json_bytes(_jsonable(expected))
    if core.get("run_identity") != expected["run_identity"]:
        raise ProductionIntegrityError(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: run_identity tamper detected"
        )
    if core.get("world_set_sha256") != expected["world_set_sha256"]:
        raise ProductionIntegrityError(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: world_set_sha256 tamper detected"
        )
    if core.get("reservation_sha256") != expected["reservation_sha256"]:
        raise ProductionIntegrityError(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: reservation digest is not tracked authority"
        )
    if core.get("claim_sha256") != expected["claim_sha256"]:
        raise ProductionIntegrityError(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: claim digest is not tracked authority"
        )
    if core.get("aggregates") != expected["aggregates"]:
        raise ProductionIntegrityError(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: aggregates were not derived from the world set"
        )
    if core_bytes != expected_bytes:
        raise ProductionIntegrityError(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: core payload tamper detected"
        )


def persist_partial_worlds(records, *args, **kwargs):
    if args or kwargs:
        _refuse("caller arguments cannot authorize partial persistence")
    root = _repo_root()
    bound = verify_executed_production_authority(root)
    payload = {
        "schema_version": "1.0",
        "status": "PARTIAL_NOT_RESULT",
        "unit_id": UNIT_ID,
        "canonical_path": CANONICAL_PARTIAL_PATH,
        "run_identity": canonical_run_identity(root),
        "execution_head": bound["head_sha"],
        "execution_tree": bound["tree_sha"],
        "grid": frozen_production_grid(),
        "observed_world_count": len(records),
        "planned_world_count": PRODUCTION_PLANNED_TOTAL_WORLDS,
        "world_set_sha256": _sha256_bytes(
            canonical_json_bytes({"worlds": [_jsonable(dict(rec)) for rec in records]})
        ),
        "final_result_minted": False,
        "automatic_retry_authorized": False,
        "records": _jsonable(list(records)),
    }
    raw = canonical_json_bytes(payload)
    payload["partial_sha256"] = _sha256_bytes(raw)
    payload["partial_size"] = len(raw)
    return payload


def recover_partial_from_tracked_authority(*args, **kwargs):
    """Recover a committed partial from git objects at HEAD (claim/result commit).

    Persistence is commit-mediated. An uncommitted worktree write of the
    canonical partial/result path is not executable authority. The artifact's
    execution identity is the named execution commit, which must be an
    ancestor of HEAD; current HEAD may be a later claim/result commit.
    """
    if args or kwargs:
        _refuse("caller arguments cannot supply recovery/digest/grid/result authority")
    root = _repo_root()
    verify_executed_production_authority(root)
    blob = _head_blob(root, CANONICAL_PARTIAL_PATH)
    if blob is None:
        _refuse("tracked recovery authority/partial artifact is absent")
    try:
        payload = json.loads(blob.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SyntheticExecutionNotAuthorized(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: malformed tracked partial artifact"
        ) from exc
    if payload.get("canonical_path") != CANONICAL_PARTIAL_PATH:
        _refuse("partial artifact path is not canonical")
    exec_head = str(payload.get("execution_head") or "").strip().lower()
    exec_tree = str(payload.get("execution_tree") or "").strip().lower()
    if not exec_head or not exec_tree:
        _refuse("partial artifact is missing execution commit/tree")
    ancestor = subprocess.run(
        ["git", "-C", str(root), "merge-base", "--is-ancestor", exec_head, "HEAD"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if ancestor.returncode != 0:
        _refuse("partial artifact execution commit is not an ancestor of HEAD")
    try:
        expected_tree = _commit_tree_sha(root, exec_head)
        expected_identity = _run_identity_from_bound(_bound_from_commit_blobs(root, exec_head))
    except SyntheticExecutionNotAuthorized as exc:
        raise SyntheticExecutionNotAuthorized(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: partial artifact execution identity is not tracked authority"
        ) from exc
    if exec_tree != expected_tree:
        _refuse("partial artifact execution tree does not match the named execution commit")
    if payload.get("run_identity") != expected_identity:
        _refuse("partial artifact run_identity does not match the named execution identity")
    if payload.get("grid") != frozen_production_grid():
        _refuse("partial artifact grid identity is not frozen authority")
    records = payload.get("records")
    if not isinstance(records, list):
        _refuse("partial artifact world-set identity is missing")
    expected_world_set = _sha256_bytes(
        canonical_json_bytes({"worlds": [_jsonable(dict(rec)) for rec in records]})
    )
    if payload.get("world_set_sha256") != expected_world_set:
        _refuse("partial artifact world-set identity mismatch")
    body = {key: value for key, value in payload.items() if key not in {"partial_sha256", "partial_size"}}
    raw = canonical_json_bytes(body)
    if payload.get("partial_sha256") != _sha256_bytes(raw):
        _refuse("partial artifact digest mismatch")
    if payload.get("partial_size") != len(raw):
        _refuse("partial artifact size mismatch")
    if payload.get("final_result_minted") is True:
        _refuse("partial artifact must not claim a final RESULT")
    return payload


def _isolated_child_env():
    env = {
        key: value
        for key, value in os.environ.items()
        if "AUTHORIZ" not in key.upper()
        and key
        not in {
            "PYTHONPATH",
            "PYTHONHOME",
            "PYTHONUSERBASE",
            "PYTHONSAFEPATH",
            "PYTHONSTARTUP",
        }
    }
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _spawn_isolated_child(mode, repo_root=None):
    root = (repo_root or _repo_root()).resolve()
    return subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-P",
            "-c",
            ISOLATED_CHILD_BOOTSTRAP,
            str(root),
            mode,
        ],
        cwd=str(root),
        env=_isolated_child_env(),
        check=False,
        capture_output=True,
        text=True,
    )


def spawn_canonical_production_process(*args, **kwargs):
    """Canonical production path: isolated interpreter, then re-verify, then refuse if unarmed."""
    if args or kwargs:
        _refuse("caller arguments cannot authorize production execution")
    proc = _spawn_isolated_child(WORKER_MODE)
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    if proc.stdout:
        sys.stdout.write(proc.stdout)
    return int(proc.returncode)


def spawn_isolated_r1_probe(*args, **kwargs):
    """Test-only isolated probe. Cannot authorize or run production Monte Carlo."""
    if args or kwargs:
        _refuse("caller arguments cannot authorize the R1 probe")
    return _spawn_isolated_child(R1_PROBE_MODE)


def r1_probe_fingerprint():
    if __name__ != "scripts.research.harness_synthetic_edge_calibration_v1_production":
        _refuse("R1 probe must run as the canonical package module")
    verify_executed_production_authority()
    gates = compose_gates(**R1_PROBE_GATE_ARGS)
    return {
        "module": __name__,
        "compose_gates": _jsonable(gates),
        "wilson_0_400": _jsonable(wilson_interval(0, 400)),
        "frozen_lib_sha256": FROZEN_REVIEWED_LIB_SHA256,
        "production_monte_carlo_arm_authorized": False,
        "production_calibration_executed": False,
        "sys_path0": sys.path[0],
    }


def _isolated_child_main(mode):
    try:
        if __name__ != "scripts.research.harness_synthetic_edge_calibration_v1_production":
            print(
                "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: child module is not the canonical package",
                file=sys.stderr,
            )
            return 2
        if mode == R1_PROBE_MODE:
            print(canonical_json_bytes(r1_probe_fingerprint()).decode("utf-8"), end="")
            return 0
        if mode == WORKER_MODE:
            return fresh_process_worker_main()
        print("SYNTHETIC_EXECUTION_NOT_AUTHORIZED: unknown isolated child mode", file=sys.stderr)
        return 2
    except SyntheticExecutionNotAuthorized as exc:
        print(str(exc), file=sys.stderr)
        return 2


def fresh_process_worker_main():
    """Runs only inside a fresh isolated interpreter. Re-verifies then fail-closes while unarmed."""
    root = _repo_root()
    verify_executed_production_authority(root)
    frozen_production_grid()
    planned_production_jobs()
    if production_monte_carlo_arm_authorized(root) is not True:
        print(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: production_monte_carlo_arm_authorized=false",
            file=sys.stderr,
        )
        return 2
    _refuse("armed production Monte Carlo is not part of this durability unit")
    return 2


def production_durability_identity():
    return {
        "stage": "production_durability_unarmed",
        "unit_id": UNIT_ID,
        "durability_id": DURABILITY_ID,
        "production_monte_carlo_arm_authorized": False,
        "production_calibration_executed": False,
        "production_result_minted": False,
        "fresh_process_required": True,
        "durable_run_identity": True,
        "global_process_exclusion_claimed": False,
        "real_market_data_access_authorized": False,
        "b2_06_scientific_execution_authorized": False,
        "validation_2025_authorized": False,
        "oos_2026_authorized": False,
        "real_data_path": False,
        "monte_carlo_armed": False,
        "authorization_consumed": False,
        "synthetic_execution_authorized": False,
        "canonical_paths": {
            "reservation": CANONICAL_RESERVATION_PATH,
            "claim": CANONICAL_CLAIM_PATH,
            "result": CANONICAL_RESULT_PATH,
            "partial": CANONICAL_PARTIAL_PATH,
            "durability": CANONICAL_DURABILITY_PATH,
            "arm": CANONICAL_ARM_PATH,
        },
    }


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    print("SYNTHETIC_EXECUTION_NOT_AUTHORIZED", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
